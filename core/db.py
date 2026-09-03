"""Database layer. Current schema version is SCHEMA_VERSION (see below); migrations run in order from any older version on open."""

import contextvars, re, sqlite3, json, os, time, threading, uuid
from contextlib import contextmanager

from core.paths import INSTALL_ROOT

# The diegetic frame the CURRENT pipeline run is executing in -- set once
# per turn in agents/runtime.py._run_pipeline from the turn row's own
# frame_id (never from ambient world-KV state), reset in that same
# function's `finally` block exactly like providers.py's cancel_event/
# token_sink contextvars already are. That reset discipline is what makes
# this safe: a generator's `.set()` mutates whatever context is actually
# driving its `next()` calls (confirmed empirically -- generators do NOT
# get an isolated Context the way asyncio Tasks do), so every entry point
# that sets this MUST reset it in `finally`, covering the abort/exception
# paths too, not just the happy path.
active_frame_id = contextvars.ContextVar("active_frame_id", default=None)

# Only these `world` keys (plus this prefix) hold genuinely diegetic-era-
# specific state -- who's known, the scene, relationships, etc. Chat-
# global keys (fiction_model, dialogue_config, fixed_points, paradox...)
# are deliberately NOT in this set: they're cross-frame contracts, not
# per-era state, and must resolve to the same row regardless of which
# frame is currently executing.
FRAME_SCOPED_WORLD_KEYS = {
    "scene", "known", "simulation_clock", "pending", "background_presences",
    "offscreen_log", "offscreen_epoch", "offscreen_plans",
    # Institution/upkeep simulation. Definitions are author-owned elsewhere;
    # this is the clocked state they produce in one era.
    "charters",
    "standing_intentions",
    # Crowd blobs. Per-era like the scene they stand in: a branch that never
    # went to the market must not inherit the market's throng.
    "crowds",
    # Couriers on the road. Per-era for the same reason, and frame-scoping is
    # also the whole rewind/branch/archive story: checkpoints snapshot the
    # world table verbatim, so a restore puts the rider back where he was,
    # and a branch that never dispatched him has no rider.
    "couriers",
    # Notices and bills nailed up in rooms. Per-era exactly like the road:
    # a rewind takes the bill off the wall, and a branch that never posted
    # it has a bare post.
    "artifacts",
    # What a beat reached for that no plan holds (`world/planning_needs.py`).
    # Per-era like the scene the door was opened in: a branch that never
    # walked through it has nothing to plan.
    "planning_needs",
    # ROOM CONVERSATION (story/room_conversation.py): the standing mandates
    # the player granted the Writers' Room and the room's spoiler-safe
    # status. Per-era like the plans they license: a branch that never
    # granted the room a harbour has no harbour mandate.
    "room_mandates", "room_status",
    # KNOWLEDGE CIRCLES a character joined or left DURING the story
    # (mind/knowledge_circles.py), overlaying the sheet's authored circles for
    # the knowledge gate. Per-era like the initiation that granted them.
    "knowledge_circles",
    # The prepared frontier's measure and the identity-fill and spend
    # ledgers (story/room_frontier.py). Per-era like the rooms it counts
    # ahead of.
    "room_frontier",
    # The story bible (story/room_bible.py): the room's narrative memory,
    # folded from the thread. Per-era like the thread it folds -- a branch
    # remembers what was said up to its point and nothing after.
    "room_bible",
    # The Dramaturge's proposals and the Planner's verdicts on them
    # (story/room_proposals.py). Per-era like the packages they lead to.
    "room_proposals",
    # -- Plot package store (story/plot_packages.py) --------------------
    # The Writers' Room's packages: drafts, what was published and when.
    # Per-era like the scene: a branch that never published a package
    # holds no package, and a rewind past a publish takes it back with
    # what it placed.
    "plot_packages",
    # -- end plot package store ------------------------------------------
    # The PLAYER's carrier envelope (`carriers.PERSONA_STATE_KEY`). Per-era
    # for exactly the reason the three keys above it are, and it was the one
    # carrier home that was not: a cast member's reports ride the frame-scoped
    # `chat_chars`/`chat_char_frames` state, and a persona has no such row, so
    # a single world row served every era at once. What the player witnessed
    # in one era survived a rewind or a branch and could be sent onward by
    # `couriers.run_couriers` from an era that never produced it.
    "persona_carrier_state",
    "pending_obligations",
    "shadow_profile", "lore_cache", "active_books",
    # {subject_id: {turn, room, elapsed_seconds}} -- who was co-present with
    # the player, per era like the scene it is read from. Written by
    # commit_scene, read by gaps.interim_for; keyed by SUBJECT ID from birth
    # (see gaps.LAST_SEEN_KEY).
    "subject_last_seen",
}
#: Prefixes whose every key is per-era. `relationships:` because a stance is
#: held by a mind that exists in one frame and may not exist in another.
#:
#: `extf:` is the frame-scoped half of an extension's own state, and it is a
#: SECOND prefix rather than a flag on the first because the prefix IS the
#: scoping mechanism here -- a key cannot be scoped without changing, so a
#: per-key flag would have to rewrite the key anyway, and a story already
#: holding `ext:<id>` would need a migration to gain one. A campaign layer
#: genuinely wants both: its installation and its package provenance span
#: eras, and its mission state does not. See `api.state` / `api.frame_state`.
FRAME_SCOPED_WORLD_PREFIXES = ("relationships:", "extf:")

_FRAME_KEY_SEP = "\x1efr"  # unlikely-to-collide separator; not valid in ordinary key text


def _is_frame_scoped_world_key(key):
    return key in FRAME_SCOPED_WORLD_KEYS or any(
        key.startswith(p) for p in FRAME_SCOPED_WORLD_PREFIXES
    )


def _scoped_world_key(key):
    """Redirects a frame-scoped key to a frame-specific storage row when
    a pipeline run has an active frame set. Present (frame_id None) and
    non-scoped keys are untouched -- this is what makes frameless chats
    behave with zero change: the active_frame_id contextvar defaults to
    None everywhere outside a pipeline run that explicitly set it."""
    frame_id = active_frame_id.get()
    if frame_id is None or not _is_frame_scoped_world_key(key):
        return key
    return f"{key}{_FRAME_KEY_SEP}{frame_id}"


def parse_scoped_world_key(key):
    """Inverse of _scoped_world_key: splits a stored key back into
    (base_key, frame_id) if it's frame-scoped, else (key, None). Needed
    wherever raw world rows are read/rewritten outside the normal
    wget/wset path -- e.g. branch cloning, which must remap the frame_id
    embedded in a key to the NEW chat's own corresponding frame id."""
    if _FRAME_KEY_SEP in key:
        base, _, frame_str = key.rpartition(_FRAME_KEY_SEP)
        try:
            return base, int(frame_str)
        except ValueError:
            return key, None
    return key, None

#: An explicit `ENGINE_DB` is taken VERBATIM -- tests point it at relative
#: temp paths and must keep resolving them against their own cwd. Only the
#: DEFAULT is anchored, and it has to be: unset, `"engine.db"` is cwd-relative,
#: so launching from anywhere but the install root silently creates a SECOND
#: empty database beside the process and the player's stories appear to have
#: vanished. Masked until now only because both launchers `cd` first and pytest
#: runs from the root. `or` rather than a default argument, so an empty
#: `ENGINE_DB=` falls through to the anchored path instead of naming the cwd.
DB = os.environ.get("ENGINE_DB") or os.path.join(INSTALL_ROOT, "engine.db")
SCHEMA_VERSION = 35

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS providers(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'generic',
    base_url TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS characters(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    sheet TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT '{}',
    created REAL NOT NULL,
    resource_uid TEXT
);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_characters_resource_uid
    ON characters(resource_uid) WHERE resource_uid IS NOT NULL;

CREATE TABLE IF NOT EXISTS personas(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    sheet TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT '{}',
    resource_uid TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_personas_resource_uid
    ON personas(resource_uid) WHERE resource_uid IS NOT NULL;

CREATE TABLE IF NOT EXISTS lorebooks(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    chat_id INTEGER REFERENCES chats(id) ON DELETE CASCADE,
    origin_id INTEGER,
    book_type TEXT NOT NULL DEFAULT 'general',
    summary TEXT NOT NULL DEFAULT '',
    resource_uid TEXT,
    parent_id INTEGER REFERENCES lorebooks(id) ON DELETE CASCADE,
    scope_world_id TEXT,
    scope_location_id TEXT,
    inheritance_mode TEXT NOT NULL DEFAULT 'inherit',
    -- THE BOOK'S COMPARTMENT, as a JSON list, inherited by every entry that
    -- does not override it. Set at the book because that is where the answer
    -- actually lives -- one book is one setting or one organisation -- and
    -- because an empty field fails silently: per-entry tagging means one
    -- forgotten entry tells a barista the Foundation exists. One decision,
    -- in one place, is the difference between a secret and a leak.
    default_circles TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL DEFAULT 0,
    anchor_entity_id TEXT,
    -- A destroyed vehicle/building's book is RETIRED (marked with the turn
    -- that destroyed it), never deleted -- its lore stays retrievable history
    -- ("the ship that sank here"). NULL = live. Written only by the
    -- destruction path. It does NOT mirror world_entities.retired_turn_id,
    -- which this comment used to claim: that column has never had a writer,
    -- because the entity table is a projection of the live scene and a
    -- projection keeps no history. The book IS the history.
    retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_lorebooks_chat ON lorebooks(chat_id);
CREATE INDEX IF NOT EXISTS idx_lorebooks_origin ON lorebooks(origin_id);
CREATE INDEX IF NOT EXISTS idx_lorebooks_parent ON lorebooks(parent_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lorebooks_resource_uid
    ON lorebooks(resource_uid) WHERE resource_uid IS NOT NULL;
-- idx_lorebooks_anchor is NOT created here: executescript(SCHEMA) always
-- runs before the version-gated MIGRATIONS below, so on an existing
-- database that predates anchor_entity_id, an index on that column here
-- would fail immediately -- the column doesn't exist yet until the v9->
-- v10 migration's ALTER TABLE runs. And the fresh path skips migrations
-- entirely, so the migration alone cannot cover it either (fresh
-- databases went without this index from the fresh-path change until
-- LATE_SCHEMA existed). It lives in LATE_SCHEMA below, which init()
-- runs AFTER the migration chain on BOTH paths.

CREATE TABLE IF NOT EXISTS lorebook_links(
    id INTEGER PRIMARY KEY,
    source_book_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    target_book_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL DEFAULT 'related',
    label TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    bidirectional INTEGER NOT NULL DEFAULT 1,
    follow_for_retrieval INTEGER NOT NULL DEFAULT 1,
    weight REAL NOT NULL DEFAULT 0.75,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL,
    CHECK(source_book_id <> target_book_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lorebook_link ON lorebook_links(source_book_id, target_book_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_lorebook_links_source ON lorebook_links(source_book_id);
CREATE INDEX IF NOT EXISTS idx_lorebook_links_target ON lorebook_links(target_book_id);

CREATE TABLE IF NOT EXISTS chat_lorebooks(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    origin_id INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(chat_id, lorebook_id)
);

CREATE TABLE IF NOT EXISTS lore_entries(
    id INTEGER PRIMARY KEY,
    lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    keys TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'other',
    canon_locked INTEGER NOT NULL DEFAULT 0,
    turn_added INTEGER,
    embedding BLOB,
    title TEXT,
    knowledge_tag TEXT,
    knowledge_range TEXT,
    knowledge_locations TEXT,
    -- WHICH COMPARTMENTS MAY KNOW THIS, as a JSON list. Empty means public:
    -- anyone who clears the depth tag. Non-empty means only a character who
    -- belongs to one of the named circles, which is the difference between
    -- "hard to know" and "kept secret" -- a clandestine organisation's
    -- existence is not esoteric, it is COMPARTMENTED, and depth alone cannot
    -- say so.
    --
    -- NULL means INHERIT the book (lorebooks.default_circles); an explicit
    -- list overrides it, and an explicit EMPTY list is a deliberate "this one
    -- is public" -- a secret that has leaked into rumour. Those three states
    -- must stay distinguishable, which is why this column is nullable rather
    -- than defaulted: under a NOT NULL DEFAULT '[]' an entry could join a
    -- different compartment but could never leave its book's.
    circles TEXT,
    entry_uid TEXT,
    importance REAL NOT NULL DEFAULT 0.5,
    aliases TEXT NOT NULL DEFAULT '[]',
    scope TEXT NOT NULL DEFAULT '{}',
    relations TEXT NOT NULL DEFAULT '{}',
    source_notes TEXT NOT NULL DEFAULT '',
    -- Which model produced `embedding`. `memories` has carried these
    -- two since the first rebuild existed; lore had neither, so it
    -- appeared in no instrument built for "my embedding model
    -- changed" and 1,061 entries sat on the crc32 fallback unnoticed.
    embedding_model TEXT,
    embedding_dim INTEGER
);
CREATE INDEX IF NOT EXISTS idx_lore_entries_book ON lore_entries(lorebook_id);
CREATE INDEX IF NOT EXISTS idx_lore_entries_category ON lore_entries(category);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_entries_uid
    ON lore_entries(entry_uid) WHERE entry_uid IS NOT NULL;

CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(
    content, keys, content='lore_entries', content_rowid='id'
);

-- External-content FTS stays in sync only through these triggers. They
-- lived ONLY in the v4->v5 migration list, which was fine while every
-- database walked the migration chain -- and silently wrong from the
-- moment init() started stamping fresh files straight to SCHEMA_VERSION:
-- a database born on the fresh path had ZERO triggers, so lore_fts
-- stayed empty and search_lore's keyword term (mind/memory.py
-- _kw_scores("lore_fts", ...), the 0.35 weight) scored 0.0 for every
-- entry, forever. Defined here IF NOT EXISTS so BOTH paths get them; the
-- columns they reference (lore_entries.content/keys, memories.content)
-- have existed since v1, so this is correct on the oldest database the
-- chain accepts. The v30->v31 migration rebuilds the index content for
-- databases that lived through the triggerless era.
-- tests/test_schema_integrity_fresh_vs_migrated.py holds the fresh and
-- migrated schemas equal so nothing else drifts into migration-only
-- existence.
CREATE TRIGGER IF NOT EXISTS lore_ai AFTER INSERT ON lore_entries BEGIN
    INSERT INTO lore_fts(rowid, content, keys)
    VALUES (new.id, new.content, new.keys);
END;
CREATE TRIGGER IF NOT EXISTS lore_ad AFTER DELETE ON lore_entries BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, content, keys)
    VALUES ('delete', old.id, old.content, old.keys);
END;
CREATE TRIGGER IF NOT EXISTS lore_au AFTER UPDATE ON lore_entries BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, content, keys)
    VALUES ('delete', old.id, old.content, old.keys);
    INSERT INTO lore_fts(rowid, content, keys)
    VALUES (new.id, new.content, new.keys);
END;

-- Resumable lorebook-tree generation. A generation run is many model calls
-- (one structure call, then one call per batch of outlined entries), and
-- every one of them can be lost to a dropped connection, an exhausted
-- provider retry budget, a browser refresh, or a server restart -- which
-- previously threw away every completed call with it. Each unit of
-- completed work is written here instead, so a resume re-runs only what
-- never finished.
--
-- This is authoring scratch state, NOT fiction canon: nothing here is
-- exported, checkpointed, branch-remapped, or read by the pipeline. The
-- lore itself only exists once the user applies the plan, which writes
-- ordinary lorebooks/lore_entries rows. Rows are pruned on job creation
-- (latest few per book) and cascade away with the book.
CREATE TABLE IF NOT EXISTS lore_gen_jobs(
    id INTEGER PRIMARY KEY,
    lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    -- running|interrupted|failed|ready|applied|cancelled
    status TEXT NOT NULL DEFAULT 'running',
    -- structure|entries|done
    stage TEXT NOT NULL DEFAULT 'structure',
    -- The generation request (brief, mode, depth, entry_target, flags), kept
    -- verbatim so a resume reproduces the same request without the client
    -- having to still have the form on screen.
    params TEXT NOT NULL DEFAULT '{}',
    -- The plan accumulated so far: analysis + book_ops + link_ops + whatever
    -- entry_ops have been generated by completed batches.
    plan TEXT NOT NULL DEFAULT '{}',
    -- {"outline": [{..., "state": "pending|done|failed"}], "stage_errors": []}
    progress TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    -- Per-process token. A 'running' row whose owner is not the live process
    -- was orphaned by a restart/crash; that is detected exactly, with no
    -- staleness timeout to tune.
    owner TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lore_gen_jobs_book
    ON lore_gen_jobs(lorebook_id, status);

CREATE TABLE IF NOT EXISTS chats(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    persona_id INTEGER REFERENCES personas(id) ON DELETE SET NULL,
    lorebook_id INTEGER REFERENCES lorebooks(id) ON DELETE SET NULL,
    scenario TEXT NOT NULL DEFAULT '',
    -- Chat ids this chat was branched out of, nearest ancestor first. Read
    -- ONLY by backdrops.py, to find already-generated room images in the
    -- chat this one split from instead of paying to redraw a room the
    -- player already saw. Deliberately a denormalized id list rather than a
    -- parent_chat_id foreign key: the backdrop files are named by raw chat
    -- id and outlive the chat row (chat_del deletes rows, not pictures), so
    -- a lineage that survives an ancestor's deletion keeps finding them
    -- where a cascaded-null parent pointer would lose them. Ids are local to
    -- one database, so import must not carry them across -- see chat_import.
    branched_from TEXT NOT NULL DEFAULT '[]',
    created REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_chars(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    char_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active',
    state TEXT NOT NULL DEFAULT '{}',
    -- Optional per-story authored card. Runtime state remains separate in
    -- state; NULL follows the reusable characters.sheet resource.
    sheet TEXT,
    -- The colour this character's spoken lines are tinted in the transcript.
    -- PRESENTATION, not story state, and deliberately not part of `sheet`:
    -- the sheet is sent to the model, and a mind has no business knowing what
    -- colour it is rendered in. Empty means "derive it" -- `dialogue_colors`
    -- computes a stable hue from the authored psychology, so the common case
    -- stores nothing at all and only a host's explicit pick is persisted.
    -- Restored like `sheet` rather than like `state`: a checkpoint rolls back
    -- what happened in the story, never how the host configured it.
    dialogue_color TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(chat_id, char_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_chars_status ON chat_chars(status);

-- Per-frame override of a character's status/state -- a character
-- genuinely can be simultaneously alive in the past and dead in the
-- future. NOT NULL frame_id: the present (frame_id NULL everywhere
-- else) always reads chat_chars directly, no override row involved.
-- A frame with no override row here for a character falls back to the
-- base chat_chars row -- a character's baseline mood/stance is a
-- reasonable starting point for an era nobody's touched yet, unlike
-- world state (scene/known), where "blank" genuinely is the right
-- first-visit default.
CREATE TABLE IF NOT EXISTS chat_char_frames(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    char_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    frame_id INTEGER NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active',
    state TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(chat_id, char_id, frame_id)
);

-- Additional simultaneously-controlled personas beyond chats.persona_id's
-- single "primary" player. chats.persona_id and every codepath that reads
-- it are untouched -- this is purely additive multiplayer support layered
-- on top, so single-player chats are unaffected.
CREATE TABLE IF NOT EXISTS chat_personas(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active',
    -- This persona's current "station" -- which frame they're playing
    -- in. NULL = present, same convention as turns.frame_id/memories.
    -- frame_id. Lets two attached players be genuinely eras apart:
    -- turn creation and _load_extra_players both filter by station, so
    -- a persona stationed in the future is never folded into a turn
    -- being created in the past, and vice versa. Same-frame co-op (both
    -- stationed in the same frame, including both NULL/present) is the
    -- degenerate case that reduces to today's behavior exactly.
    frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,
    PRIMARY KEY(chat_id, persona_id)
);

-- An extra persona's declared action for a specific upcoming beat, keyed by
-- chat+turn INDEX rather than turn_id: the turn row for that index may not
-- exist yet when an extra player submits (they can declare ahead of the
-- primary player's request, which is what makes same-beat resolution
-- possible -- whichever request actually creates the turn picks up
-- everything already declared for that index and resolves them together
-- in one director_interpret call).
CREATE TABLE IF NOT EXISTS turn_player_inputs(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    turn_idx INTEGER NOT NULL,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    input TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL,
    UNIQUE(chat_id, turn_idx, persona_id)
);
CREATE INDEX IF NOT EXISTS idx_turn_player_inputs_lookup
    ON turn_player_inputs(chat_id, turn_idx);

-- Remote-join grants for the "invite a friend" feature. Only hashes of
-- the join code and session token are stored (never the plaintext),
-- since a local SQLite file can be read by anything else on the host
-- machine that has filesystem access. code_hash is single-use: consumed
-- (never re-checked once redeemed_at is set) rather than deleted, so the
-- grant row -- and the token it minted -- can still be looked up and
-- revoked after redemption.
CREATE TABLE IF NOT EXISTS guest_grants(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    code_expires REAL NOT NULL,
    redeemed_at REAL,
    token_hash TEXT,
    token_expires REAL,
    revoked INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guest_grants_chat
    ON guest_grants(chat_id);
-- Every guest-auth request looks a row up by one of these two hashes;
-- without the indexes each lookup was a full table scan.
CREATE INDEX IF NOT EXISTS idx_guest_grants_code_hash
    ON guest_grants(code_hash);
CREATE INDEX IF NOT EXISTS idx_guest_grants_token_hash
    ON guest_grants(token_hash);

-- Host login sessions for the username+password host account. Only the
-- SHA-256 hash of each session token is stored (same rationale as
-- guest_grants: a readable engine.db must never yield a working
-- credential). Rows past `expires` are simply ignored on lookup.
CREATE TABLE IF NOT EXISTS host_sessions(
    id INTEGER PRIMARY KEY,
    token_hash TEXT NOT NULL,
    created REAL NOT NULL,
    expires REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_host_sessions_token
    ON host_sessions(token_hash);

-- A frame is a contiguous run of turns declared to occur at one diegetic
-- era, distinct from play order (turns.idx). NULL frame_id (on turns and
-- memories) means "the present" -- the chat's original, implicit era --
-- so ordinary chats that never time-travel need no frame row at all.
-- `ordinal` is directly comparable to the present's implicit ordinal of
-- 0: negative for the past, positive for the future, by convention only
-- (not enforced). `travelers` lists char_ids who keep full memory
-- continuity in this frame instead of the native ordinal cutoff.
-- `nonexistent_cast` lists char_ids natives of this frame must not
-- recognize/know yet (or anymore), independent of world.known's
-- accumulated play-order truth.
CREATE TABLE IF NOT EXISTS frames(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    label TEXT NOT NULL DEFAULT '',
    ordinal INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'other',
    travelers TEXT NOT NULL DEFAULT '[]',
    nonexistent_cast TEXT NOT NULL DEFAULT '[]',
    created REAL NOT NULL,
    parent_frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,
    split_turn_idx INTEGER,
    merged_turn_idx INTEGER
);
CREATE INDEX IF NOT EXISTS idx_frames_chat ON frames(chat_id, ordinal);

CREATE TABLE IF NOT EXISTS turns(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    player_input TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL,
    frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,
    UNIQUE(chat_id, idx)
);
CREATE INDEX IF NOT EXISTS idx_turns_chat_idx ON turns(chat_id, idx);

CREATE TABLE IF NOT EXISTS steps(
    id INTEGER PRIMARY KEY,
    turn_id INTEGER NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    ord INTEGER NOT NULL DEFAULT 0,
    stale INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_steps_turn_ord ON steps(turn_id, ord);
CREATE INDEX IF NOT EXISTS idx_steps_key ON steps(key);

CREATE TABLE IF NOT EXISTS variants(
    id INTEGER PRIMARY KEY,
    step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 0,
    reasoning TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_variants_step ON variants(step_id);
CREATE INDEX IF NOT EXISTS idx_variants_active ON variants(step_id, active);

-- Content-addressed bodies for the debug capture. One row per DISTINCT blob:
-- a 44KB Director sheet is stored once and referenced by every call that sent
-- it, and a payload key that did not change between beats costs nothing the
-- second time. `body` is NULL in hash_only mode, which is the default -- the
-- hash still proves WHICH text was sent without the text leaving the machine.
CREATE TABLE IF NOT EXISTS llm_blobs(
    hash  TEXT PRIMARY KEY,
    bytes INTEGER NOT NULL,
    body  TEXT
);

-- One row per provider call, INCLUDING the sub-calls that have no step of
-- their own -- the Director's six specialists are the reason this table
-- exists rather than another column on `variants`. `seq` is the turn-local
-- order the calls were STARTED in, which is what makes a chronological
-- reading of a turn possible across a fan-out.
CREATE TABLE IF NOT EXISTS llm_capture(
    id            INTEGER PRIMARY KEY,
    turn_id       INTEGER NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    step_key      TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT '',
    requested     TEXT NOT NULL DEFAULT '',
    served        TEXT NOT NULL DEFAULT '',
    started       REAL NOT NULL DEFAULT 0,
    duration      REAL NOT NULL DEFAULT 0,
    ok            INTEGER NOT NULL DEFAULT 1,
    error         TEXT NOT NULL DEFAULT '',
    system_hash   TEXT,
    payload_hashes TEXT NOT NULL DEFAULT '{}',
    response_hash TEXT,
    reasoning_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_capture_turn ON llm_capture(turn_id, seq);

CREATE TABLE IF NOT EXISTS memories(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    char_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    turn_idx INTEGER,
    kind TEXT NOT NULL DEFAULT 'episodic',
    category TEXT NOT NULL DEFAULT 'episode',
    provenance TEXT NOT NULL DEFAULT 'witnessed',
    salience REAL NOT NULL DEFAULT 0.5,
    content TEXT NOT NULL,
    gist TEXT NOT NULL DEFAULT '',
    key_phrases TEXT NOT NULL DEFAULT '[]',
    entities TEXT NOT NULL DEFAULT '[]',
    location TEXT NOT NULL DEFAULT '',
    emotional_context TEXT NOT NULL DEFAULT '',
    valence REAL NOT NULL DEFAULT 0.0,
    arousal REAL NOT NULL DEFAULT 0.0,
    -- Resolved affect after this event was appraised. valence/arousal above
    -- remain the affect carried INTO the event; together they preserve the
    -- direction of emotional encoding instead of conflating before and after.
    encoding_valence REAL NOT NULL DEFAULT 0.0,
    encoding_arousal REAL NOT NULL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 1.0,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed REAL,
    -- The TURN a recall reached this row on, not the wall clock. `last_accessed`
    -- answers "when did somebody's computer touch this" and cannot answer the
    -- question that decides how much memory is worth delivering: how far BACK a
    -- mind reached when it reached. Depth is `last_accessed_turn - turn_idx`,
    -- and without the first term it is unobtainable -- a row retrieved while
    -- fresh and a row retrieved three hundred beats later look identical
    -- afterwards. NULL means never reached since this column existed.
    last_accessed_turn INTEGER,
    embedding BLOB,
    cue_embedding BLOB,
    embedding_model TEXT NOT NULL DEFAULT '',
    embedding_dim INTEGER,
    archived INTEGER NOT NULL DEFAULT 0,
    event_key TEXT NOT NULL DEFAULT '',
    frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,
    -- How central this memory BECAME, as against `salience`, which records how
    -- much it mattered when it was formed and is never revised. NULL means
    -- "never revised", and every reader falls back to salience, so a bank that
    -- has never been touched behaves exactly as before.
    importance REAL,
    -- The character's own later re-reading of a memory they still hold as
    -- experience. A witnessed memory stays autobiographically true -- "I saw
    -- this" -- while its INTERPRETATION becomes contested, which is what
    -- deception, disguise and misidentification actually do to a mind.
    -- JSON: {"turn_idx": n, "reading": "...", "count": k}, '' when undisputed.
    --
    -- Deliberately a column on the row rather than an edge to another memory
    -- id: checkpoint restore is delete-and-reinsert, so every row id changes,
    -- and an id-keyed edge would be shredded by the first rollback. Stored
    -- here it rides the existing dump/restore round-trip verbatim.
    disputed TEXT NOT NULL DEFAULT '',
    -- The simulation-clock reading, in seconds of fiction time, at the moment
    -- this row was written. STORED rather than derived, and that is the whole
    -- point of the column: an age computed as
    -- `(now_turn - turn_idx) * (now_elapsed / now_turn)` reads off a MOVING
    -- denominator, so re-running one turn with a different declared duration
    -- silently re-ages every memory in the bank -- including rows from beats
    -- that never changed -- and a branched chat reads the same memory at two
    -- different ages. A stored reading is LOCAL: it rolls back with its own
    -- row, because the write path deletes and re-mints a re-run turn's rows
    -- and the clock itself is a frame-scoped `world` key that is not on the
    -- checkpoint preserved-list.
    --
    -- NULL means "no reading", not "zero": rows with no place in play order
    -- (prestory seeds, imported banks, a character's history carried in from
    -- another story) have no clock to have been read, and every reader falls
    -- back to qualitative phrasing for them.
    encoded_at_seconds REAL
);
CREATE INDEX IF NOT EXISTS idx_memories_chat_char ON memories(chat_id, char_id);

-- Embedding vectors, stored ONCE and addressed by content.
--
-- A checkpoint used to carry every memory's two float32 vectors inline, and
-- since a checkpoint is a full snapshot of the bank, the same vector was
-- re-stored on every turn for the life of the story. Measured on the live
-- database: checkpoints were 94.5% of a 4.4 GB file, `memories` was 98.9% of
-- each checkpoint, and the two vector fields were 96.9% of that. One story
-- held 40,224 memory copies across 118 checkpoints and only 529 distinct by
-- (char_id, content) -- 76x redundancy, 1.00 GB of vectors that need 13 MB.
--
-- The key is `memory.vector_address`: sha1 over the vector BYTES themselves,
-- prefixed `v1:`. It was briefly sha1(char_id, content) instead, on the
-- reasoning that a vector is a pure function of the memory. It is -- but not
-- of its content: `_memory_document` also folds in turn, location, category,
-- key_phrases, entities, gist, provenance and emotional_context, so two rows
-- can share content and hold different vectors, and that address collapsed
-- them. Addressing on bytes makes a collision impossible by construction
-- rather than by assumption, and still deduplicates 69x.
--
-- APPEND-ONLY, and never garbage-collected when a memory is deleted. A
-- checkpoint that predates the deletion still references the vector, and a
-- rollback that cannot restore one is a worse failure than a few kilobytes of
-- orphaned rows.
CREATE TABLE IF NOT EXISTS memory_vectors(
    vkey TEXT PRIMARY KEY,
    embedding BLOB,
    cue_embedding BLOB,
    embedding_model TEXT NOT NULL DEFAULT '',
    embedding_dim INTEGER,
    created REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_turn ON memories(turn_id);
CREATE INDEX IF NOT EXISTS idx_memories_chronology ON memories(chat_id, char_id, turn_idx, id);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(chat_id, char_id, category);
CREATE INDEX IF NOT EXISTS idx_memories_event_key ON memories(chat_id, char_id, event_key);
CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_event ON memories(chat_id, char_id, event_key) WHERE event_key <> '';

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, content='memories', content_rowid='id'
);

-- Sync triggers for memories_fts, here for the same reason as the
-- lore_fts triggers above (migration-only objects never reach a fresh
-- database). memories_fts itself has no reader (docs/UNBUILT.md 1.35);
-- it is kept in sync rather than dropped so the eventual drop can be its
-- own deliberate migration instead of a side effect of this repair.
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content)
    VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO memories_fts(rowid, content)
    VALUES (new.id, new.content);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS memory_retrieval_fts USING fts5(
    memory_id UNINDEXED,
    chat_id UNINDEXED,
    char_id UNINDEXED,
    gist,
    content,
    key_phrases,
    entities,
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS memory_summaries(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    char_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    scope TEXT NOT NULL DEFAULT 'autobiographical',
    start_turn_idx INTEGER NOT NULL DEFAULT 0,
    end_turn_idx INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    key_phrases TEXT NOT NULL DEFAULT '[]',
    unresolved_threads TEXT NOT NULL DEFAULT '[]',
    -- JSON: one entry per clause of `summary`, as
    -- [{"claim": str, "support_refs": [event_key, ...],
    --   "epistemic_origin": "what_i_experienced"|"what_i_was_told"|
    --                       "what_i_concluded"|""}].
    -- Derived host-side from the window's own memories at consolidation, so
    -- it costs no model call and cannot be argued with. A clause with an
    -- EMPTY support_refs is the point: summaries cannot reinforce durable
    -- belief, but they do move appraisal and speech, and until now a
    -- consolidator sentence with nothing behind it left no trace when it did.
    support TEXT NOT NULL DEFAULT '[]',
    embedding BLOB,
    embedding_model TEXT NOT NULL DEFAULT '',
    embedding_dim INTEGER,
    updated REAL NOT NULL,
    -- One row per WINDOW, not one per character. The key was
    -- (chat_id, char_id, scope) until v23, so a character's autobiography was
    -- a single row overwritten on every consolidation -- which meant the
    -- summary layer could not be searched, because there was nothing to search
    -- BETWEEN. Every summary already carried a maintained `embedding`
    -- (computed on write, re-embedded on a model change, carried through every
    -- archive and checkpoint) that no retrieval path had ever read.
    --
    -- `end_turn_idx` completes the key so consolidation APPENDS a window and
    -- re-running the same consolidation still updates in place rather than
    -- duplicating.
    UNIQUE(chat_id, char_id, scope, end_turn_idx)
);
CREATE INDEX IF NOT EXISTS idx_memory_summaries_window
    ON memory_summaries(chat_id, char_id, scope, end_turn_idx);

CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    content TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_chat ON events(chat_id);
CREATE INDEX IF NOT EXISTS idx_events_turn ON events(turn_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_events_chat_turn
    ON events(chat_id, turn_id) WHERE turn_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS world(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY(chat_id, key)
);

CREATE TABLE IF NOT EXISTS checkpoints(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    turn_idx INTEGER NOT NULL,
    blob TEXT NOT NULL,
    created REAL NOT NULL,
    UNIQUE(chat_id, turn_idx)
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_chat ON checkpoints(chat_id, turn_idx);

-- ROOM CONVERSATION (story/room_conversation.py): the player's thread with
-- the Writers' Room, per story and era. Author-side, so it is carried by a
-- branch (web/app.turn_branch) and an archive (persist/chat_archive) and is
-- NOT in the turn checkpoint: a reroll unsays a beat, never a conversation.
-- frame_id NULL is the present, as everywhere else.
CREATE TABLE IF NOT EXISTS room_messages(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,
    turn_idx INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_room_messages_thread ON room_messages(chat_id, frame_id, id);

-- LORE OVERLAYS (mind/memory_lore_entries.py): one story's deviation from one
-- LIBRARY lore entry. A library book is attached to a story BY REFERENCE
-- (chat_lorebooks points at the library row; nothing is copied), and what the
-- story changes about an entry -- a hand edit, a canon lock, the room's
-- supersession -- is this row, merged over the library row at read time. A
-- NULL field inherits the library value; a non-NULL one overrides it. Per
-- story and per era like the scene: a branch that never edited the entry
-- reads the library. Replaces the per-chat "(chat copy)" of every attached
-- book, measured 2026-09-03 at 1,681 of 2,044 copied entries byte-identical
-- to their origin.
CREATE TABLE IF NOT EXISTS lore_overlays(
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    frame_id INTEGER REFERENCES frames(id) ON DELETE CASCADE,
    entry_id INTEGER NOT NULL REFERENCES lore_entries(id) ON DELETE CASCADE,
    keys TEXT,
    content TEXT,
    category TEXT,
    title TEXT,
    knowledge_tag TEXT,
    knowledge_range TEXT,
    knowledge_locations TEXT,
    circles TEXT,
    canon_locked INTEGER,
    embedding BLOB,
    embedding_model TEXT,
    embedding_dim INTEGER,
    disposition TEXT NOT NULL DEFAULT 'story_edit',
    source_notes TEXT NOT NULL DEFAULT '',
    turn_idx INTEGER,
    created REAL NOT NULL
);
-- One overlay per story, era and entry. COALESCE because a UNIQUE index
-- treats two NULL frame ids as distinct, and the present era is NULL.
CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_overlays_scope
    ON lore_overlays(chat_id, entry_id, COALESCE(frame_id, 0));
CREATE INDEX IF NOT EXISTS idx_lore_overlays_chat ON lore_overlays(chat_id, frame_id);

CREATE TABLE IF NOT EXISTS world_events(
    event_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,
    occurred_at REAL NOT NULL,
    duration_seconds REAL NOT NULL DEFAULT 0,
    kind TEXT NOT NULL,
    location_id TEXT,
    payload TEXT NOT NULL,
    seed TEXT,
    committed REAL NOT NULL,
    PRIMARY KEY(chat_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_world_events_chat_time ON world_events(chat_id, occurred_at);

CREATE TABLE IF NOT EXISTS relationship_events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,
    char_id INTEGER NOT NULL,
    target TEXT NOT NULL,
    axis TEXT NOT NULL,
    delta REAL NOT NULL,
    triggers TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    provenance TEXT NOT NULL DEFAULT '',
    turn_idx INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_relationship_events_pair
    ON relationship_events(chat_id, char_id, target);

CREATE TABLE IF NOT EXISTS world_entities(
    entity_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    subtype TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL,
    created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    -- VESTIGIAL: no writer, and by design. This table is a projection of the
    -- live scene, so a removed entity's row is deleted with the thing it
    -- projects; existence-over-time is room_registry's ledger and the
    -- destroyed thing's lore stays in its RETIRED lorebook. Kept rather than
    -- dropped only because every archive, checkpoint and branch-remap path
    -- round-trips the column, and a rebuild migration on live stories is not
    -- worth removing a NULL. Guarded by scene_lint and by
    -- test_the_entity_projection_never_retires_a_row.
    retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    PRIMARY KEY(chat_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_world_entities_chat_kind ON world_entities(chat_id, kind);

-- DECOMMISSIONED (movement/space Phase 3a): no runtime writer or reader.
-- Positions/containment live solely in the frame-scoped scene blob
-- (scene.positions + rooms' parent_entity). Kept, like fiction_worlds
-- below, only so old snapshots/exports keep restoring; the lone runtime
-- statements touching it are legacy-row cleanups on entity removal.
CREATE TABLE IF NOT EXISTS world_placements(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    container_id TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(chat_id, subject_id)
);
CREATE INDEX IF NOT EXISTS idx_world_placements_container ON world_placements(chat_id, container_id);

CREATE TABLE IF NOT EXISTS world_conditions(
    condition_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    started_at REAL NOT NULL,
    expires_at REAL,
    next_tick REAL,
    payload TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(chat_id, condition_id)
);
CREATE INDEX IF NOT EXISTS idx_world_conditions_due ON world_conditions(chat_id, active, next_tick);

CREATE TABLE IF NOT EXISTS scheduled_events(
    event_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    due_at REAL NOT NULL,
    kind TEXT NOT NULL,
    location_id TEXT,
    payload TEXT NOT NULL,
    seed TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    PRIMARY KEY(chat_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_scheduled_events_due ON scheduled_events(chat_id, status, due_at);

-- Normalized room-identity registry (movement/space Phase 2; Phase 3a made
-- it the SOLE cross-frame ledger of room identity/existence-over-time/
-- retirement). The frame-scoped scene JSON blob under `world` is the sole
-- authority for LIVE rooms/positions; this table is a deterministic
-- projection of every scene write (commit_scene in the same commit domain;
-- the manual world editor via commit.sync_room_registry_with_scene) and is
-- what dedup and destruction read. room_uid is the room's stable canonical
-- key (the scene rooms-dict key, per-chat unique, matching the v14
-- composite-key convention). owning_book_id scopes dedup (a vehicle's
-- anchored book, else the location/canon book); parent_entity is the
-- enclosing entity for interior rooms. retired_turn_id NULL = live; a
-- removed/destroyed room keeps its row (retire-not-delete) so "the ship
-- that sank here" stays retrievable identity. This is where retirement is
-- REAL: world_entities has the same column and no writer for it (see the
-- VESTIGIAL note above it), because that table is a projection of the live
-- scene and loses a row with the thing it projects. Existence-over-time is
-- this table's job precisely because it is not that projection.
CREATE TABLE IF NOT EXISTS room_registry(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    room_uid TEXT NOT NULL,
    owning_book_id INTEGER REFERENCES lorebooks(id) ON DELETE SET NULL,
    parent_entity TEXT,
    name TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '[]',
    payload TEXT NOT NULL DEFAULT '{}',
    created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    PRIMARY KEY(chat_id, room_uid)
);
CREATE INDEX IF NOT EXISTS idx_room_registry_book
    ON room_registry(owning_book_id) WHERE owning_book_id IS NOT NULL;

-- DEPRECATED (movement/space Phase 2): fiction_worlds, fiction_locations,
-- and transit_edges are a dead macro-geography schema -- nothing in the
-- runtime pipeline reads or writes them. Their roles are absorbed by the
-- unified model: macro geography = upper lorebook-tree books; macro
-- transit = portal links (entity.state.link) + scheduled_events latency.
-- The tables are kept so existing exports keep restoring, and only TWO of the
-- three actually are: `fiction_worlds` and `fiction_locations` are in
-- `chat_archive.WORLD_TABLES` and in the checkpoint blob. `transit_edges` is
-- named in exactly one place outside this file -- the chat-deletion sweep in
-- `web/app.py` -- so nothing snapshots, exports, imports or restores it, and
-- an old archive carrying rows loses them on import. Dropping all three is
-- Phase 3.
CREATE TABLE IF NOT EXISTS fiction_worlds(
    world_id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    parent_world_id TEXT REFERENCES fiction_worlds(world_id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'world',
    payload TEXT NOT NULL,
    created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fiction_worlds_chat ON fiction_worlds(chat_id);

CREATE TABLE IF NOT EXISTS fiction_locations(
    location_id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    world_id TEXT NOT NULL REFERENCES fiction_worlds(world_id) ON DELETE CASCADE,
    parent_location_id TEXT REFERENCES fiction_locations(location_id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'location',
    name TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fiction_locations_parent ON fiction_locations(parent_location_id);
CREATE INDEX IF NOT EXISTS idx_fiction_locations_world ON fiction_locations(world_id);

CREATE TABLE IF NOT EXISTS transit_edges(
    edge_id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    from_world_id TEXT NOT NULL,
    from_location_id TEXT,
    to_world_id TEXT NOT NULL,
    to_location_id TEXT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""

MIGRATIONS = [
    # v1 -> v2
    [
        "ALTER TABLE lorebooks ADD COLUMN chat_id INTEGER",
        "ALTER TABLE lorebooks ADD COLUMN origin_id INTEGER",
        "ALTER TABLE lorebooks ADD COLUMN book_type TEXT DEFAULT 'general'",
        "ALTER TABLE lorebooks ADD COLUMN summary TEXT DEFAULT ''",
        "ALTER TABLE lore_entries ADD COLUMN category TEXT DEFAULT 'other'",
        "ALTER TABLE lore_entries ADD COLUMN title TEXT",
        "ALTER TABLE lore_entries ADD COLUMN knowledge_tag TEXT",
        "ALTER TABLE lore_entries ADD COLUMN knowledge_range TEXT",
        "ALTER TABLE lore_entries ADD COLUMN knowledge_locations TEXT",
    ],
    # v2 -> v3
    [
        "CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name)",
        "CREATE INDEX IF NOT EXISTS idx_lorebooks_chat ON lorebooks(chat_id)",
        "CREATE INDEX IF NOT EXISTS idx_lore_entries_book ON lore_entries(lorebook_id)",
        "CREATE INDEX IF NOT EXISTS idx_lore_entries_category ON lore_entries(category)",
        "CREATE INDEX IF NOT EXISTS idx_turns_chat_idx ON turns(chat_id, idx)",
        "CREATE INDEX IF NOT EXISTS idx_steps_turn_ord ON steps(turn_id, ord)",
        "CREATE INDEX IF NOT EXISTS idx_memories_chat_char ON memories(chat_id, char_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_chat ON events(chat_id)",
        "CREATE INDEX IF NOT EXISTS idx_checkpoints_chat ON checkpoints(chat_id, turn_idx)",
    ],
    # v3 -> v4
    [
        "ALTER TABLE memories ADD COLUMN turn_idx INTEGER",
        "ALTER TABLE memories ADD COLUMN category TEXT NOT NULL DEFAULT 'episode'",
        "ALTER TABLE memories ADD COLUMN gist TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE memories ADD COLUMN key_phrases TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE memories ADD COLUMN entities TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE memories ADD COLUMN location TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE memories ADD COLUMN emotional_context TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE memories ADD COLUMN valence REAL NOT NULL DEFAULT 0.0",
        "ALTER TABLE memories ADD COLUMN arousal REAL NOT NULL DEFAULT 0.0",
        "ALTER TABLE memories ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0",
        "ALTER TABLE memories ADD COLUMN access_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE memories ADD COLUMN last_accessed REAL",
        "ALTER TABLE memories ADD COLUMN cue_embedding BLOB",
        "ALTER TABLE memories ADD COLUMN embedding_model TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE memories ADD COLUMN embedding_dim INTEGER",
        "ALTER TABLE memories ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE memories ADD COLUMN event_key TEXT NOT NULL DEFAULT ''",
        "CREATE INDEX IF NOT EXISTS idx_memories_chronology ON memories(chat_id,char_id,turn_idx,id)",
        "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(chat_id,char_id,category)",
        "CREATE INDEX IF NOT EXISTS idx_memories_event_key ON memories(chat_id,char_id,event_key)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_event ON memories(chat_id,char_id,event_key) WHERE event_key <> ''",
        "CREATE VIRTUAL TABLE IF NOT EXISTS memory_retrieval_fts USING fts5(memory_id UNINDEXED, chat_id UNINDEXED, char_id UNINDEXED, gist, content, key_phrases, entities, tokenize='unicode61 remove_diacritics 2')",
        "CREATE TABLE IF NOT EXISTS memory_summaries(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE, char_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE, scope TEXT NOT NULL DEFAULT 'autobiographical', start_turn_idx INTEGER NOT NULL DEFAULT 0, end_turn_idx INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT '', key_phrases TEXT NOT NULL DEFAULT '[]', unresolved_threads TEXT NOT NULL DEFAULT '[]', embedding BLOB, embedding_model TEXT NOT NULL DEFAULT '', embedding_dim INTEGER, updated REAL NOT NULL, UNIQUE(chat_id,char_id,scope))",
    ],
    # v4 -> v5
    [
        "DROP TRIGGER IF EXISTS lore_ai",
        "DROP TRIGGER IF EXISTS lore_ad",
        "DROP TRIGGER IF EXISTS lore_au",
        "DROP TRIGGER IF EXISTS memories_ai",
        "DROP TRIGGER IF EXISTS memories_ad",
        "DROP TRIGGER IF EXISTS memories_au",
        """CREATE TRIGGER lore_ai AFTER INSERT ON lore_entries BEGIN
            INSERT INTO lore_fts(rowid, content, keys)
            VALUES (new.id, new.content, new.keys);
        END""",
        """CREATE TRIGGER lore_ad AFTER DELETE ON lore_entries BEGIN
            INSERT INTO lore_fts(lore_fts, rowid, content, keys)
            VALUES ('delete', old.id, old.content, old.keys);
        END""",
        """CREATE TRIGGER lore_au AFTER UPDATE ON lore_entries BEGIN
            INSERT INTO lore_fts(lore_fts, rowid, content, keys)
            VALUES ('delete', old.id, old.content, old.keys);
            INSERT INTO lore_fts(rowid, content, keys)
            VALUES (new.id, new.content, new.keys);
        END""",
        """CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content)
            VALUES (new.id, new.content);
        END""",
        """CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
        END""",
        """CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
            INSERT INTO memories_fts(rowid, content)
            VALUES (new.id, new.content);
        END""",
        "INSERT INTO lore_fts(lore_fts) VALUES('rebuild')",
        "INSERT INTO memories_fts(memories_fts) VALUES('rebuild')",
    ],
    # v5 -> v6
    [
        "INSERT INTO lore_fts(lore_fts) VALUES('rebuild')",
        "INSERT INTO memories_fts(memories_fts) VALUES('rebuild')",
    ],
    # v6 -> v7
    [
        "ALTER TABLE characters ADD COLUMN resource_uid TEXT",
        "ALTER TABLE personas ADD COLUMN resource_uid TEXT",
        "ALTER TABLE lorebooks ADD COLUMN resource_uid TEXT",
        "ALTER TABLE lore_entries ADD COLUMN entry_uid TEXT",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_characters_resource_uid "
        "ON characters(resource_uid) WHERE resource_uid IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_personas_resource_uid "
        "ON personas(resource_uid) WHERE resource_uid IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_lorebooks_resource_uid "
        "ON lorebooks(resource_uid) WHERE resource_uid IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_entries_uid "
        "ON lore_entries(entry_uid) WHERE entry_uid IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_events_chat_turn "
        "ON events(chat_id, turn_id) WHERE turn_id IS NOT NULL",
    ],
    # v7 -> v8
    [
        "ALTER TABLE lorebooks ADD COLUMN parent_id INTEGER REFERENCES lorebooks(id) ON DELETE CASCADE",
        "ALTER TABLE lorebooks ADD COLUMN scope_world_id TEXT",
        "ALTER TABLE lorebooks ADD COLUMN scope_location_id TEXT",
        "ALTER TABLE lorebooks ADD COLUMN inheritance_mode TEXT NOT NULL DEFAULT 'inherit'",
        "ALTER TABLE lorebooks ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
        "CREATE INDEX IF NOT EXISTS idx_lorebooks_parent ON lorebooks(parent_id)",
        "CREATE TABLE IF NOT EXISTS world_events("
        "event_id TEXT PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,"
        "occurred_at REAL NOT NULL,"
        "duration_seconds REAL NOT NULL DEFAULT 0,"
        "kind TEXT NOT NULL,"
        "location_id TEXT,"
        "payload TEXT NOT NULL,"
        "seed TEXT,"
        "committed REAL NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_world_events_chat_time ON world_events(chat_id, occurred_at)",
        "CREATE TABLE IF NOT EXISTS world_entities("
        "entity_id TEXT PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "kind TEXT NOT NULL,"
        "subtype TEXT NOT NULL DEFAULT '',"
        "name TEXT NOT NULL DEFAULT '',"
        "payload TEXT NOT NULL,"
        "created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,"
        "retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL)",
        "CREATE INDEX IF NOT EXISTS idx_world_entities_chat_kind ON world_entities(chat_id, kind)",
        "CREATE TABLE IF NOT EXISTS world_placements("
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "subject_id TEXT NOT NULL,"
        "relation TEXT NOT NULL,"
        "container_id TEXT NOT NULL,"
        "detail TEXT NOT NULL DEFAULT '{}',"
        "PRIMARY KEY(chat_id, subject_id))",
        "CREATE INDEX IF NOT EXISTS idx_world_placements_container ON world_placements(chat_id, container_id)",
        "CREATE TABLE IF NOT EXISTS world_conditions("
        "condition_id TEXT PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "subject_id TEXT NOT NULL,"
        "kind TEXT NOT NULL,"
        "started_at REAL NOT NULL,"
        "expires_at REAL,"
        "next_tick REAL,"
        "payload TEXT NOT NULL,"
        "active INTEGER NOT NULL DEFAULT 1)",
        "CREATE INDEX IF NOT EXISTS idx_world_conditions_due ON world_conditions(chat_id, active, next_tick)",
        "CREATE TABLE IF NOT EXISTS scheduled_events("
        "event_id TEXT PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "due_at REAL NOT NULL,"
        "kind TEXT NOT NULL,"
        "location_id TEXT,"
        "payload TEXT NOT NULL,"
        "seed TEXT NOT NULL,"
        "status TEXT NOT NULL DEFAULT 'pending')",
        "CREATE INDEX IF NOT EXISTS idx_scheduled_events_due ON scheduled_events(chat_id, status, due_at)",
        "CREATE TABLE IF NOT EXISTS fiction_worlds("
        "world_id TEXT PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "parent_world_id TEXT REFERENCES fiction_worlds(world_id) ON DELETE SET NULL,"
        "name TEXT NOT NULL,"
        "kind TEXT NOT NULL DEFAULT 'world',"
        "payload TEXT NOT NULL,"
        "created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,"
        "retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL)",
        "CREATE INDEX IF NOT EXISTS idx_fiction_worlds_chat ON fiction_worlds(chat_id)",
        "CREATE TABLE IF NOT EXISTS fiction_locations("
        "location_id TEXT PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "world_id TEXT NOT NULL REFERENCES fiction_worlds(world_id) ON DELETE CASCADE,"
        "parent_location_id TEXT REFERENCES fiction_locations(location_id) ON DELETE CASCADE,"
        "kind TEXT NOT NULL DEFAULT 'location',"
        "name TEXT NOT NULL,"
        "payload TEXT NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_fiction_locations_parent ON fiction_locations(parent_location_id)",
        "CREATE INDEX IF NOT EXISTS idx_fiction_locations_world ON fiction_locations(world_id)",
        "CREATE TABLE IF NOT EXISTS transit_edges("
        "edge_id TEXT PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "from_world_id TEXT NOT NULL,"
        "from_location_id TEXT,"
        "to_world_id TEXT NOT NULL,"
        "to_location_id TEXT,"
        "kind TEXT NOT NULL,"
        "payload TEXT NOT NULL)",
    ],
    # v8 -> v9
    [
        "CREATE TABLE IF NOT EXISTS lorebook_links("
        "id INTEGER PRIMARY KEY,"
        "source_book_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,"
        "target_book_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,"
        "relation_type TEXT NOT NULL DEFAULT 'related',"
        "label TEXT NOT NULL DEFAULT '',"
        "notes TEXT NOT NULL DEFAULT '',"
        "bidirectional INTEGER NOT NULL DEFAULT 1,"
        "follow_for_retrieval INTEGER NOT NULL DEFAULT 1,"
        "weight REAL NOT NULL DEFAULT 0.75,"
        "sort_order INTEGER NOT NULL DEFAULT 0,"
        "created REAL NOT NULL,"
        "CHECK(source_book_id <> target_book_id))",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_lorebook_link "
        "ON lorebook_links(source_book_id, target_book_id, relation_type)",
        "CREATE INDEX IF NOT EXISTS idx_lorebook_links_source "
        "ON lorebook_links(source_book_id)",
        "CREATE INDEX IF NOT EXISTS idx_lorebook_links_target "
        "ON lorebook_links(target_book_id)",
        "ALTER TABLE lore_entries ADD COLUMN importance REAL NOT NULL DEFAULT 0.5",
        "ALTER TABLE lore_entries ADD COLUMN aliases TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE lore_entries ADD COLUMN scope TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE lore_entries ADD COLUMN relations TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE lore_entries ADD COLUMN source_notes TEXT NOT NULL DEFAULT ''",
    ],
    # v9 -> v10
    [
        # Mobile ("vehicle" book_type) lorebooks: anchor_entity_id links a
        # lorebook to a world_entities row. commit_scene's sync_anchored_
        # books reparents the book to wherever that entity's room maps to
        # whenever the entity moves, so its lore -- and its child books,
        # which travel with it via ordinary parent_id lineage -- follows
        # the vehicle instead of staying pinned to wherever it started.
        "ALTER TABLE lorebooks ADD COLUMN anchor_entity_id TEXT",
        "CREATE INDEX IF NOT EXISTS idx_lorebooks_anchor ON lorebooks(anchor_entity_id) "
        "WHERE anchor_entity_id IS NOT NULL",
    ],
    # v10 -> v11
    [
        # Temporal frames: NULL frame_id means "the present" (the chat's
        # original, implicit era), so existing turns/memories need no
        # backfill -- they're correctly "present" by leaving the column
        # NULL. The `frames` table itself is created unconditionally by
        # SCHEMA above (CREATE TABLE IF NOT EXISTS runs on every startup,
        # new-table creation doesn't need the migration path at all --
        # only ALTER TABLE on pre-existing tables does).
        "ALTER TABLE turns ADD COLUMN frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL",
        "ALTER TABLE memories ADD COLUMN frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL",
    ],
    # v11 -> v12
    [
        # Concurrent multi-frame play: a persona's "station" (which frame
        # they're playing in). NULL = present, same convention as every
        # other frame_id column.
        "ALTER TABLE chat_personas ADD COLUMN frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL",
    ],
    # v12 -> v13
    [
        # Spatial (not temporal) frame splits: a "spatial" frame shares
        # its parent's ordinal (same diegetic "now", just decoupled) --
        # parent_frame_id/split_turn_idx/merged_turn_idx are what let
        # is_memory_visible tell a spatial split apart from an ordinary
        # past/future frame and apply incomparability instead of the
        # ordinal rule while the split is unresolved.
        "ALTER TABLE frames ADD COLUMN parent_frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL",
        "ALTER TABLE frames ADD COLUMN split_turn_idx INTEGER",
        "ALTER TABLE frames ADD COLUMN merged_turn_idx INTEGER",
    ],
    # v13 -> v14
    [
        # world_entities.entity_id / world_conditions.condition_id were a
        # bare GLOBAL primary key, but the ids the model coins ("rifle",
        # "tardis") are only unique within a chat. That made a same-named
        # entity in a second chat collide: commit's unscoped SELECT/UPDATE
        # would silently mutate the FIRST chat's row (cross-story leak),
        # and an INSERT of a colliding id would hit the global PK and fail.
        # Repartition both tables on the composite key (chat_id, id) so the
        # id space is per-chat, matching how paradox.py and checkpoints.py
        # already query them. SQLite can't ALTER a primary key in place, so
        # recreate-copy-swap. Nothing declares a FK referencing either
        # table, so the drop/rename is safe. All columns copied here have
        # existed since these tables were introduced (this same MIGRATIONS
        # list), so an older db reaching v14 already has every one of them.
        # Drop any leftover scratch table so re-running this migration after a
        # crash mid-copy doesn't collide with a half-populated *_new table.
        "DROP TABLE IF EXISTS world_entities_new",
        "CREATE TABLE world_entities_new("
        "entity_id TEXT NOT NULL,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "kind TEXT NOT NULL,"
        "subtype TEXT NOT NULL DEFAULT '',"
        "name TEXT NOT NULL DEFAULT '',"
        "payload TEXT NOT NULL,"
        "created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,"
        "retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,"
        "PRIMARY KEY(chat_id, entity_id))",
        "INSERT INTO world_entities_new(entity_id,chat_id,kind,subtype,name,payload,"
        "created_turn_id,retired_turn_id) SELECT entity_id,chat_id,kind,subtype,name,"
        "payload,created_turn_id,retired_turn_id FROM world_entities",
        "DROP TABLE world_entities",
        "ALTER TABLE world_entities_new RENAME TO world_entities",
        "CREATE INDEX IF NOT EXISTS idx_world_entities_chat_kind ON world_entities(chat_id, kind)",
        # The same scratch-table clearance the entity rebuild above got, and
        # for the same reason -- omitted here, one rebuild later in the same
        # list. Worse than the entity case would have been: this CREATE has no
        # IF NOT EXISTS, so against leftover wreckage it fails with "already
        # exists", which `init()` swallows as harmless. The copy then lands on
        # the half-populated table and the RENAME installs it.
        "DROP TABLE IF EXISTS world_conditions_new",
        "CREATE TABLE world_conditions_new("
        "condition_id TEXT NOT NULL,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "subject_id TEXT NOT NULL,"
        "kind TEXT NOT NULL,"
        "started_at REAL NOT NULL,"
        "expires_at REAL,"
        "next_tick REAL,"
        "payload TEXT NOT NULL,"
        "active INTEGER NOT NULL DEFAULT 1,"
        "PRIMARY KEY(chat_id, condition_id))",
        "INSERT INTO world_conditions_new(condition_id,chat_id,subject_id,kind,started_at,"
        "expires_at,next_tick,payload,active) SELECT condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active FROM world_conditions",
        "DROP TABLE world_conditions",
        "ALTER TABLE world_conditions_new RENAME TO world_conditions",
        "CREATE INDEX IF NOT EXISTS idx_world_conditions_due ON world_conditions(chat_id, active, next_tick)",
    ],
    # v14 -> v15
    [
        # Book retirement marker for single-book destruction (see the
        # lorebooks table comment). The room_registry TABLE itself is
        # created unconditionally by SCHEMA above (new tables never need
        # the migration path -- only ALTER TABLE on pre-existing tables
        # and data backfills do).
        "ALTER TABLE lorebooks ADD COLUMN retired_turn_id INTEGER "
        "REFERENCES turns(id) ON DELETE SET NULL",
        # Migrate the Phase-1 DERIVED lore_entries room registry (category
        # 'layout', entry_uid 'room:<book_id>:<room_key>') into the
        # normalized room_registry table that supersedes it. Only identity
        # (room key + owning book) is recoverable from the uid here;
        # name/aliases/parent_entity are left at defaults and self-heal on
        # the next commit, which rewrites every LIVE room's row from the
        # scene. INSERT OR IGNORE: a same-key room registered under two
        # books keeps the first row -- also rewritten next commit.
        "INSERT OR IGNORE INTO room_registry"
        "(chat_id, room_uid, owning_book_id, parent_entity, name, aliases, payload)"
        " SELECT lb.chat_id,"
        " substr(le.entry_uid, 6 + instr(substr(le.entry_uid, 6), ':')),"
        " le.lorebook_id, NULL, '', '[]', '{}'"
        " FROM lore_entries le JOIN lorebooks lb ON lb.id = le.lorebook_id"
        " WHERE le.category='layout' AND le.entry_uid LIKE 'room:%'"
        " AND lb.chat_id IS NOT NULL",
        # The lore-entry encoding is superseded; the rows were derived
        # bookkeeping (rewritten every commit), never authored lore.
        "DELETE FROM lore_entries WHERE category='layout' "
        "AND entry_uid LIKE 'room:%'",
    ],
    # v15 -> v16
    [
        # scheduled_events.event_id was a bare GLOBAL primary key -- the
        # same defect v14 fixed for world_entities/world_conditions.
        # Runtime-minted ids hash the chat id in (stable_event_key), so
        # they never collide across chats organically, but export/import
        # keeps event ids verbatim (deliberately, to stay consistent with
        # the un-remapped world KV and checkpoint blobs) -- so importing a
        # chat with PENDING events into the same install hit the global PK
        # and aborted the whole import. Repartition on (chat_id, event_id),
        # matching v14's recreate-copy-swap pattern; every runtime query
        # already scopes by chat_id. Drop leftover scratch first so a crash
        # mid-copy stays re-runnable.
        "DROP TABLE IF EXISTS scheduled_events_new",
        "CREATE TABLE scheduled_events_new("
        "event_id TEXT NOT NULL,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "due_at REAL NOT NULL,"
        "kind TEXT NOT NULL,"
        "location_id TEXT,"
        "payload TEXT NOT NULL,"
        "seed TEXT NOT NULL,"
        "status TEXT NOT NULL DEFAULT 'pending',"
        "PRIMARY KEY(chat_id, event_id))",
        "INSERT INTO scheduled_events_new(event_id,chat_id,due_at,kind,"
        "location_id,payload,seed,status) SELECT event_id,chat_id,due_at,"
        "kind,location_id,payload,seed,status FROM scheduled_events",
        "DROP TABLE scheduled_events",
        "ALTER TABLE scheduled_events_new RENAME TO scheduled_events",
        "CREATE INDEX IF NOT EXISTS idx_scheduled_events_due "
        "ON scheduled_events(chat_id, status, due_at)",
    ],
    # v16 -> v17
    [
        # Branch lineage, so a branched chat can find its ancestors' already
        # generated backdrops. Existing chats migrate to '[]': their branch
        # points are only recorded in the "name ⎇idx" label, which is a
        # display string and not a reliable id, so backfilling would be
        # guesswork. They simply keep generating as before.
        "ALTER TABLE chats ADD COLUMN branched_from TEXT NOT NULL DEFAULT '[]'",
    ],
    # v17 -> v18
    [
        # Resumable lorebook-tree generation jobs. See the SCHEMA comment on
        # lore_gen_jobs: pure authoring scratch state, so there is nothing to
        # backfill -- pre-existing installs simply have no interrupted runs
        # on record and start recording them from here on.
        "CREATE TABLE IF NOT EXISTS lore_gen_jobs("
        "id INTEGER PRIMARY KEY,"
        "lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,"
        "status TEXT NOT NULL DEFAULT 'running',"
        "stage TEXT NOT NULL DEFAULT 'structure',"
        "params TEXT NOT NULL DEFAULT '{}',"
        "plan TEXT NOT NULL DEFAULT '{}',"
        "progress TEXT NOT NULL DEFAULT '{}',"
        "error TEXT NOT NULL DEFAULT '',"
        "owner TEXT NOT NULL DEFAULT '',"
        "attempts INTEGER NOT NULL DEFAULT 0,"
        "created REAL NOT NULL,"
        "updated REAL NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_lore_gen_jobs_book "
        "ON lore_gen_jobs(lorebook_id, status)",
    ],
    # v18 -> v19
    [
        "ALTER TABLE chat_chars ADD COLUMN sheet TEXT",
    ],
    # v19 -> v20
    [
        # A thinking model's reasoning trace, kept beside the output it
        # produced. Diagnostic only: it is a model talking to itself and has
        # been through none of the checks the answer has, so nothing may read
        # it as content. Empty for models that do not expose one.
        "ALTER TABLE variants ADD COLUMN reasoning TEXT NOT NULL DEFAULT ''",
    ],
    # v20 -> v21
    [
        # Two questions a memory row could not answer. Both default to the
        # pre-existing behaviour, so no backfill: a NULL importance reads as
        # the row's salience, and an empty dispute reads as undisputed.
        "ALTER TABLE memories ADD COLUMN importance REAL",
        "ALTER TABLE memories ADD COLUMN disputed TEXT NOT NULL DEFAULT ''",
    ],
    # v21 -> v22
    [
        # Content-addressed embedding storage; see the SCHEMA comment. The
        # table starts empty and fills as checkpoints are written or compacted
        # (`checkpoints.compact_checkpoints`), so nothing needs backfilling for the
        # engine to keep working -- an existing checkpoint still carries its
        # vectors inline and restores from them exactly as before.
        "CREATE TABLE IF NOT EXISTS memory_vectors("
        "vkey TEXT PRIMARY KEY,"
        "embedding BLOB,"
        "cue_embedding BLOB,"
        "embedding_model TEXT NOT NULL DEFAULT '',"
        "embedding_dim INTEGER,"
        "created REAL NOT NULL)",
    ],
    # v22 -> v23
    [
        # Summary WINDOWS. The old key was (chat_id, char_id, scope), so a
        # character's autobiography was one row overwritten on every
        # consolidation -- which is why the summary layer could not be
        # searched: there was nothing to search between. Each row already
        # carried a maintained embedding no retrieval path had ever read.
        #
        # A rebuild rather than an ALTER: SQLite cannot drop a UNIQUE declared
        # inline on CREATE TABLE (it owns an implicit auto-index). Existing
        # rows copy across unchanged and become each character's first window.
        # Drop any leftover scratch table first, exactly as the three other
        # recreate-copy-swap migrations do: a crash between the CREATE and the
        # RENAME leaves a half-populated table, and IF NOT EXISTS adopts it
        # instead of building a fresh one -- so the copy below re-inserts an id
        # it has already written, the migration dies on the UNIQUE, and the
        # database stays at the old version with no way forward.
        "DROP TABLE IF EXISTS memory_summaries_v23",
        "CREATE TABLE IF NOT EXISTS memory_summaries_v23("
        "id INTEGER PRIMARY KEY,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "char_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,"
        "scope TEXT NOT NULL DEFAULT 'autobiographical',"
        "start_turn_idx INTEGER NOT NULL DEFAULT 0,"
        "end_turn_idx INTEGER NOT NULL DEFAULT 0,"
        "summary TEXT NOT NULL DEFAULT '',"
        "key_phrases TEXT NOT NULL DEFAULT '[]',"
        "unresolved_threads TEXT NOT NULL DEFAULT '[]',"
        "embedding BLOB,"
        "embedding_model TEXT NOT NULL DEFAULT '',"
        "embedding_dim INTEGER,"
        "updated REAL NOT NULL,"
        "UNIQUE(chat_id, char_id, scope, end_turn_idx))",
        "INSERT INTO memory_summaries_v23("
        "id, chat_id, char_id, scope, start_turn_idx, end_turn_idx, summary,"
        "key_phrases, unresolved_threads, embedding, embedding_model,"
        "embedding_dim, updated) "
        "SELECT id, chat_id, char_id, scope, start_turn_idx, end_turn_idx,"
        "summary, key_phrases, unresolved_threads, embedding, embedding_model,"
        "embedding_dim, updated FROM memory_summaries",
        "DROP TABLE memory_summaries",
        "ALTER TABLE memory_summaries_v23 RENAME TO memory_summaries",
        "CREATE INDEX IF NOT EXISTS idx_memory_summaries_window"
        " ON memory_summaries(chat_id, char_id, scope, end_turn_idx)",
    ],
    # v23 -> v24
    [
        "ALTER TABLE memories ADD COLUMN encoding_valence REAL NOT NULL DEFAULT 0.0",
        "ALTER TABLE memories ADD COLUMN encoding_arousal REAL NOT NULL DEFAULT 0.0",
    ],
    # v24 -> v25
    [
        # Per-clause provenance for consolidated summaries. Existing rows keep
        # '[]' -- an empty support set on an old summary means "never
        # derived", not "nothing supports it", and `memory.summary_support`
        # returns [] for both because the difference is unknowable after the
        # fact. Backfilling it would require the window's memories, which
        # consolidation has already archived.
        "ALTER TABLE memory_summaries ADD COLUMN support TEXT NOT NULL DEFAULT '[]'",
    ],
    # v25 -> v26
    [
        # WHICH MODEL EMBEDDED THIS ENTRY. `memories` and `memory_summaries`
        # have carried these two columns for as long as there has been a
        # rebuild, and every instrument built for "my embedding model changed"
        # -- `rebuild_embeddings`, `embedding_bank_status`,
        # `_warn_stranded_embeddings` -- keys on them. `lore_entries` had
        # neither, so it appeared in none of those instruments and the
        # question could not be asked about lore at all.
        #
        # What that cost, measured on a live corpus: 1,061 of 1,418 lore
        # entries were carrying the crc32 hashing fallback -- byte-identical
        # to `providers.cheap_embed` of their own text, verified on a sample
        # of 40 out of 40 -- because `add_lore` called `embed_texts`, which
        # discards the model stamp, rather than `embed_texts_meta`, which
        # reports it. They had never been embedded semantically at all, and
        # `search_lore` scored every one of them 0.0 on its 0.65 vector term
        # while ranking them plausibly enough on keywords that nothing looked
        # broken for 165 turns.
        #
        # NULL means "not yet determined" rather than "no model": the backfill
        # that stamps existing rows is a separate, resumable pass, because
        # deciding what embedded a row means recomputing a hash per row and a
        # migration is the wrong place to do work that can fail halfway.
        "ALTER TABLE lore_entries ADD COLUMN embedding_model TEXT",
        "ALTER TABLE lore_entries ADD COLUMN embedding_dim INTEGER",
    ],
    # v26 -> v27
    [
        # Activate the previously dormant objective-event spine without
        # inheriting its two persistence defects: a global event id collides
        # on same-install import, and no frame column makes an event from one
        # era visible in another. The table has no runtime rows in released
        # builds, but the copy keeps hand-authored/experimental rows intact.
        "DROP TABLE IF EXISTS world_events_new",
        "CREATE TABLE world_events_new("
        "event_id TEXT NOT NULL,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,"
        "frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,"
        "occurred_at REAL NOT NULL,"
        "duration_seconds REAL NOT NULL DEFAULT 0,"
        "kind TEXT NOT NULL,"
        "location_id TEXT,"
        "payload TEXT NOT NULL,"
        "seed TEXT,"
        "committed REAL NOT NULL,"
        "PRIMARY KEY(chat_id, event_id))",
        "INSERT INTO world_events_new(event_id,chat_id,turn_id,frame_id,"
        "occurred_at,duration_seconds,kind,location_id,payload,seed,committed) "
        "SELECT event_id,chat_id,turn_id,NULL,occurred_at,duration_seconds,"
        "kind,location_id,payload,seed,committed FROM world_events",
        "DROP TABLE world_events",
        "ALTER TABLE world_events_new RENAME TO world_events",
        "CREATE INDEX IF NOT EXISTS idx_world_events_chat_time "
        "ON world_events(chat_id, occurred_at)",
    ],
    # v27 -> v28
    [
        # Why a stance is where it is. The scalar graph keeps ONE
        # `salient_event` string and overwrites it on every update, so the
        # reason a character stopped trusting somebody survived exactly until
        # the next time their feelings moved at all.
        #
        # Measured before building: 98.8% of the 5,704 stance movements in the
        # live corpus already carry `trigger_event_ids`. The model was saying
        # why the whole time and the seam was throwing it away -- 5,638
        # recorded reasons destroyed. This is an append-only ledger of what
        # was already being said.
        "CREATE TABLE IF NOT EXISTS relationship_events("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
        "frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL,"
        "char_id INTEGER NOT NULL,"
        "target TEXT NOT NULL,"
        "axis TEXT NOT NULL,"
        "delta REAL NOT NULL,"
        "triggers TEXT NOT NULL DEFAULT '',"
        "note TEXT NOT NULL DEFAULT '',"
        "provenance TEXT NOT NULL DEFAULT '',"
        "turn_idx INTEGER NOT NULL DEFAULT 0,"
        "created REAL NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_relationship_events_pair "
        "ON relationship_events(chat_id, char_id, target)",
    ],
    # v28 -> v29
    [
        # Per-story dialogue colour. No backfill and none possible: '' is the
        # live default and means "derive from the card", which is what every
        # existing row wants. A stored value only ever comes from a host
        # picking one.
        "ALTER TABLE chat_chars ADD COLUMN "
        "dialogue_color TEXT NOT NULL DEFAULT ''",
    ],
    # v29 -> v30
    [
        # `persona_carrier_state` joined FRAME_SCOPED_WORLD_KEYS above, so its
        # storage row is now per-era. The rows already written are not: one
        # bare row per chat, holding whatever every era of that story put in
        # it. Re-key each held report by the era that ACQUIRED it -- a report
        # records `acquired_turn`, and a turn records its frame, so the era is
        # recoverable rather than guessed.
        #
        # A frame_id of NULL is the present, whose storage key is the bare one
        # (see _scoped_world_key), so the present's reports need no move: the
        # UPDATE below just stops the bare row from also answering for the
        # other eras. A report whose `acquired_turn` names no surviving turn
        # (a rewind deleted it) stays with the present rather than being
        # dropped -- the safe direction, since the present is the era the
        # player is most likely standing in.
        "INSERT OR REPLACE INTO world(chat_id,key,value) "
        "SELECT w.chat_id, "
        "       'persona_carrier_state' || char(30) || 'fr' || t.frame_id, "
        "       json_set(w.value, '$.carried_reports', "
        "                json_group_array(json(r.value))) "
        "FROM world w "
        "JOIN json_each(w.value, '$.carried_reports') r "
        "JOIN turns t ON t.chat_id = w.chat_id "
        "            AND t.idx = json_extract(r.value, '$.acquired_turn') "
        "WHERE w.key = 'persona_carrier_state' "
        "  AND json_valid(w.value) "
        "  AND json_type(w.value, '$.carried_reports') = 'array' "
        "  AND t.frame_id IS NOT NULL "
        "GROUP BY w.chat_id, t.frame_id",
        "UPDATE world "
        "   SET value = json_set(value, '$.carried_reports', ("
        "        SELECT json_group_array(json(r.value)) "
        "          FROM json_each(world.value, '$.carried_reports') r "
        "         WHERE (SELECT t.frame_id FROM turns t "
        "                 WHERE t.chat_id = world.chat_id "
        "                   AND t.idx = json_extract(r.value, '$.acquired_turn')"
        "               ) IS NULL)) "
        " WHERE key = 'persona_carrier_state' "
        "   AND json_valid(value) "
        "   AND json_type(value, '$.carried_reports') = 'array'",
    ],
    # v30 -> v31
    [
        # Databases created between the fresh-path change (init() stamping a
        # new file straight to SCHEMA_VERSION, skipping migrations) and the
        # FTS sync triggers joining SCHEMA were born with NO triggers at
        # all: every lore row written in that era never reached lore_fts,
        # so search_lore's keyword term scored 0.0 for every entry.
        # executescript(SCHEMA) has just re-created the triggers (IF NOT
        # EXISTS, and it always runs before this list); this rebuild
        # backfills the index content the missing triggers never wrote.
        # Idempotent: a long-migrated database that always had its triggers
        # rebuilds to the same content it already held.
        "INSERT INTO lore_fts(lore_fts) VALUES('rebuild')",
        "INSERT INTO memories_fts(memories_fts) VALUES('rebuild')",
    ],
    # v31 -> v32
    [
        # How deep a recall reached, in beats, which nothing recorded before.
        # Deliberately NOT backfilled from `last_accessed`: that is a wall
        # clock, there is no sound way to map it onto a turn index, and a
        # guessed depth would be worse than a missing one -- this column exists
        # to answer a measurement question, and inventing its first month of
        # data would poison the answer.
        "ALTER TABLE memories ADD COLUMN last_accessed_turn INTEGER",
    ],
    # v32 -> v33
    [
        # Compartments: WHO may know a fact, which no column could express.
        # Depth (`knowledge_tag`) says how hard something is to know; it
        # cannot say that a clandestine organisation's existence is withheld
        # from everyone outside it. Authors had already noticed the gap and
        # were improvising compartment names INTO the depth field -- across
        # the stories on disk `knowledge_tag` holds `site-17`,
        # `starfleet_protocol`, `priya_private`, `concord_boarders` and
        # `blackwood_sanatorium/west_wing/access` beside common/scholarly/
        # esoteric -- and every one of those evaluated to "no access" and
        # reached nobody, silently.
        "ALTER TABLE lore_entries ADD COLUMN circles TEXT",
        "ALTER TABLE lorebooks ADD COLUMN default_circles TEXT NOT NULL DEFAULT '[]'",
        # `knowledge_for_character` no longer selects on `category='knowledge'`:
        # reachability is a PROPERTY (an explicit depth tag) rather than a
        # category, because 974 entries across every OTHER category already
        # carried a tag and were unreachable because of it. The entries that
        # were reachable purely BY category and carry no tag would go dark
        # under the new rule, so they are given the tier the old code
        # defaulted them to. This is the one place that default may be
        # applied; after it, an untagged entry means Director-only on purpose.
        "UPDATE lore_entries SET knowledge_tag='common' "
        "WHERE category='knowledge' AND (knowledge_tag IS NULL OR knowledge_tag='')",
    ],
    # v33 -> v34
    [
        # When a memory was formed, in seconds of fiction time. Minds were
        # measuring their own past in BEATS -- turn indices, engine
        # vocabulary -- because it was the only working unit the payload
        # offered them (94 stamped recalls across 54 character calls in one
        # instrumented run, and characters reasoning in it: "the same
        # declaration about the door lock ten beats ago"). A beat is a frame
        # of construction, not a duration anybody in the fiction can feel.
        "ALTER TABLE memories ADD COLUMN encoded_at_seconds REAL",
        # EXISTING ROWS ARE LEFT NULL, DELIBERATELY.
        #
        # The obvious backfill -- turn_idx * UNCLAIMED_BEAT_SECONDS -- was
        # written first and then measured, and it fails the standard this
        # change exists to enforce. It is a rate off a fixed denominator, which
        # is exactly the derivation the stored column replaces: a chat that
        # actually ran at ~18s/beat comes back "about 9 minutes ago" for a
        # memory 30 seconds old -- an 18x error delivered as a confident
        # number -- and where the estimate overshoots the live clock the
        # interval goes negative and the legacy bank silently reads as
        # unplaceable anyway. `mind/memory_time`'s own docstring is the rule it
        # breaks: a confident wrong age is worse than an honest shrug.
        #
        # So a row written before this column existed carries no reading, says
        # so, and its readers keep the qualitative phrasing they already had.
        # New rows carry a measurement from the first beat after the migration.
        # A bank therefore dates precisely what it can and declines the rest,
        # which is also how a memory actually behaves.
        #
        # The replacement for the estimate is a stored per-turn clock history,
        # not a better rate: `mind/memory_time.turn_clock_reading` is the seam
        # that would read one, and nothing downstream changes when it lands.
    ],
    # v34 -> v35
    [
        # llm_blobs and llm_capture are created by SCHEMA, which runs on every
        # path before this chain, so there is no DDL to repeat here. The bump
        # exists so a database that predates the debug capture is
        # distinguishable from one that simply has never captured anything --
        # an empty llm_capture means "nothing recorded", and on a v34 file it
        # would have meant "cannot record".
    ],
]

# DDL that must run AFTER the migration chain, on every path -- init()
# executes it last. Two constraints force this third location into
# existence: executescript(SCHEMA) always runs BEFORE the version-gated
# MIGRATIONS, so an index on a column a migration adds cannot live in
# SCHEMA (on a pre-v10 database the column does not exist yet); and the
# fresh path skips MIGRATIONS entirely, so it cannot live only in a
# migration either -- that is exactly how the fresh and migrated schemas
# drifted apart (see the FTS trigger comment in SCHEMA). Everything here
# must be idempotent, and must reference only columns that exist once the
# chain has run.
LATE_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_lorebooks_anchor ON lorebooks(anchor_entity_id)
    WHERE anchor_entity_id IS NOT NULL;
"""

_local = threading.local()
_write_lock = threading.RLock()

_LOCK_MESSAGES = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
)

def _is_locked_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(item in message for item in _LOCK_MESSAGES)

def _execute_retry(c, sql, args=(), timeout=30.0):
    deadline = time.monotonic() + timeout
    delay = 0.025

    while True:
        try:
            return c.execute(sql, args)
        except sqlite3.OperationalError as exc:
            if not _is_locked_error(exc) or time.monotonic() >= deadline:
                raise

            time.sleep(delay)
            delay = min(delay * 1.75, 0.5)

def close_connection():
    c = getattr(_local, "conn", None)
    if c is not None:
        try:
            c.close()
        finally:
            _local.conn = None
            _local.db_path = None
            _local.tx_depth = 0

def configure(path: str):
    """Change databases safely, primarily for tests."""
    global DB

    close_connection()
    DB = path
    # A new database invalidates every cached read of the old one, even if
    # the path is reused (tests reconfigure onto fresh files freely).
    bump_world_epoch()

def conn():
    c = getattr(_local, "conn", None)
    current_path = getattr(_local, "db_path", None)

    if c is not None and current_path != DB:
        close_connection()
        c = None

    if c is None:
        c = sqlite3.connect(
            DB,
            timeout=30.0,
            check_same_thread=False,
        )
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        # NORMAL, not SQLite's default FULL. Under FULL every commit fsyncs,
        # and a turn issues dozens of autocommit writes before the outer
        # transaction even opens -- per-character memory access counts,
        # settings, the offscreen log, the presence ledger. Benchmarked on this
        # filesystem: FULL 3.49 ms per commit, NORMAL 0.02 ms. 175x, paid
        # dozens of times a turn.
        #
        # In WAL mode NORMAL is still crash-consistent: the database cannot
        # corrupt, and a rollback-journal-style torn write is not possible.
        # What is traded is durability of the last few commits across a power
        # cut or kernel panic -- not a process crash, which loses nothing. For
        # a local single-player engine that is the right side of the trade, and
        # it changes nothing about commit.py's atomicity: a turn that fails
        # still rolls back whole.
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        _local.conn = c
        _local.db_path = DB
        _local.tx_depth = 0

    return c

@contextmanager
def transaction():
    c = conn()
    depth = int(getattr(_local, "tx_depth", 0))
    outermost = depth == 0
    savepoint = f"sp_{depth}_{threading.get_ident()}"

    if outermost:
        _write_lock.acquire()
        try:
            _execute_retry(c, "BEGIN IMMEDIATE")
        except Exception:
            _write_lock.release()
            raise
    else:
        c.execute(f"SAVEPOINT {savepoint}")

    _local.tx_depth = depth + 1

    try:
        yield c

        if outermost:
            c.commit()
        else:
            c.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception:
        if outermost:
            c.rollback()
        else:
            c.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            c.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise
    finally:
        _local.tx_depth = depth
        if outermost:
            # Re-invalidate world-row read tokens for rows written inside
            # this transaction, now that the writes are visible (or rolled
            # back -- a spurious bump only costs one re-fetch). See wset.
            for gen_key in getattr(_local, "pending_world_bumps", None) or ():
                _world_write_gen[gen_key] = \
                    _world_write_gen.get(gen_key, 0) + 1
            _local.pending_world_bumps = None
            _write_lock.release()

def data_version():
    """A counter that changes when ANOTHER connection commits.

    SQLite guarantees two readings from the same connection differ if and only
    if some other connection committed in between; this connection's own writes
    never move it. Connections here are thread-local, so "another connection"
    means any other request, pipeline thread or background job.

    That makes this the exact test for "is a snapshot I built a moment ago
    still current" -- which a turn-id comparison is not, because lorebook
    edits, character-sheet edits, memory edits and background world writes all
    change checkpointed state without inserting a turn row.
    """
    return conn().execute("PRAGMA data_version").fetchone()[0]


def q(sql, args=(), one=False):
    c = conn()
    rows = c.execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows

def qi(sql, args=()):
    c = conn()
    depth = int(getattr(_local, "tx_depth", 0))

    if depth:
        cur = c.execute(sql, args)
        return cur.lastrowid

    with _write_lock:
        try:
            cur = _execute_retry(c, sql, args)
            c.commit()
            return cur.lastrowid
        except Exception:
            c.rollback()
            raise

def qtx(sql, args=()):
    if int(getattr(_local, "tx_depth", 0)) <= 0:
        raise RuntimeError("qtx() must be called inside transaction()")

    cur = conn().execute(sql, args)
    return cur.lastrowid

class SchemaVersionTooNew(RuntimeError):
    """The database file was written by a NEWER engine than this one.

    The migration loop is `range(current, SCHEMA_VERSION)` -- empty when
    current is ahead -- so before this guard a too-new file opened
    silently and stayed at its stamped version while an older binary
    wrote under assumptions the newer schema had already repartitioned
    (v13->v14 moved world_entities/world_conditions onto (chat_id, id):
    an older binary writing that file uses the wrong key space). Failing
    loudly at open is the only safe behaviour."""


class UnstampedDatabaseError(RuntimeError):
    """The file already contains tables but has no schema_meta at all.

    Every engine-produced database has carried schema_meta since the
    oldest supported version, so this file is a partial copy, a
    corrupted database, or ENGINE_DB pointed at some other program's
    file. Adopting it (the pre-guard behaviour: executescript(SCHEMA)
    over the wreckage, then an unconditional SCHEMA_VERSION stamp) is
    worse than refusing: the false stamp permanently destroys the one
    fact -- "this database never migrated" -- that a later repair would
    need."""


#: `ALTER TABLE <t> ADD COLUMN <col> ...` -- the one migration statement
#: shape whose idempotence used to depend on string-matching the error
#: message ("duplicate column"). Matched here so the migration loop can
#: ask the schema itself (PRAGMA table_xinfo) instead of the message.
_ADD_COLUMN_RE = re.compile(
    r'^\s*ALTER\s+TABLE\s+"?(\w+)"?\s+ADD\s+COLUMN\s+"?(\w+)"?',
    re.IGNORECASE,
)


def _column_addition_already_applied(c, stmt):
    """True when stmt is an ADD COLUMN whose column already exists.

    DDL runs in autocommit, so a crash mid-migration-list leaves the
    earlier statements applied with the version not advanced; the re-run
    must then skip what already landed. That used to ride on catching
    "duplicate column" in the error text; introspection answers the same
    question deterministically, without depending on SQLite's message
    wording."""
    m = _ADD_COLUMN_RE.match(stmt)
    if not m:
        return False
    table, column = m.group(1), m.group(2)
    try:
        cols = {row[1] for row in c.execute(f'PRAGMA table_xinfo("{table}")')}
    except sqlite3.OperationalError:
        return False
    return column in cols


def _get_schema_version(c):
    row = c.execute(
        "SELECT value FROM schema_meta WHERE key='version'"
    ).fetchone()
    return int(row["value"]) if row else 0

def _set_schema_version(c, version):
    c.execute(
        "INSERT INTO schema_meta(key, value) VALUES('version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(version),),
    )

def _backfill_resource_uids(c):
    tables = (
        ("characters", "resource_uid", "char"),
        ("personas", "resource_uid", "persona"),
        ("lorebooks", "resource_uid", "book"),
        ("lore_entries", "entry_uid", "entry"),
    )
    for table, column, prefix in tables:
        rows = c.execute(
            f"SELECT id FROM {table} WHERE {column} IS NULL OR {column}=''"
        ).fetchall()
        for row in rows:
            value = f"{prefix}_{uuid.uuid4().hex}"
            c.execute(
                f"UPDATE {table} SET {column}=? WHERE id=?",
                (value, row["id"]),
            )

def _migrate_chat_copies_to_overlays(c):
    """Convert every "(chat copy)" of a LIBRARY book into a reference plus
    overlays, once.

    Until 2026-09-03 attaching a library book duplicated its whole subtree
    into chat-owned copies marked with `origin_id`. Measured on the owner's
    database: 143 copies, 2,044 copied entries, 1,681 of them byte-identical
    to their origin, 363 edited or added in-story, 5 copies whose origin was
    gone. This pass, per copy whose origin is a live library book:

      * an entry identical (keys + content) to an origin entry is dropped;
      * an entry that differs but matches an origin entry by title, else by
        keys, becomes an overlay on that origin entry (disposition
        `migrated_copy`, the copy's own vector carried);
      * an entry matching nothing was added in-story and MOVES to the chat's
        canon book (minted here if the chat has none);
      * every reference to the copy -- the attachment, room-registry
        ownership, links, a chat-owned child's parent -- is re-pointed at the
        origin, and the copy is deleted (cascade takes what is left).

    A copy whose origin no longer exists, or whose origin is another chat's
    book, or which IS the chat's canon (bind_lore used to duplicate a library
    book as canon), stays a chat-owned book: `origin_id` is cleared so it is
    never read as a copy again. Returns the counts, for the caller's log.
    """
    rows = c.execute(
        "SELECT id, chat_id, origin_id, name FROM lorebooks "
        "WHERE chat_id IS NOT NULL AND origin_id IS NOT NULL").fetchall()
    report = {"copies": len(rows), "converted": 0, "kept_own": 0,
              "dropped": 0, "overlaid": 0, "moved": 0}
    if not rows:
        return report
    now = time.time()
    for copy in rows:
        origin = c.execute(
            "SELECT id, chat_id FROM lorebooks WHERE id=?",
            (copy["origin_id"],)).fetchone()
        chat = c.execute("SELECT id, name, lorebook_id FROM chats WHERE id=?",
                         (copy["chat_id"],)).fetchone()
        if (origin is None or origin["chat_id"] is not None or chat is None
                or chat["lorebook_id"] == copy["id"]):
            c.execute("UPDATE lorebooks SET origin_id=NULL WHERE id=?", (copy["id"],))
            report["kept_own"] += 1
            continue
        cid, oid = copy["chat_id"], origin["id"]
        origin_entries = c.execute(
            "SELECT * FROM lore_entries WHERE lorebook_id=?", (oid,)).fetchall()
        by_text = {}
        by_title = {}
        by_keys = {}
        for e in origin_entries:
            by_text.setdefault((e["keys"] or "", e["content"] or ""), e["id"])
            if (e["title"] or "").strip():
                by_title.setdefault(e["title"].strip().casefold(), []).append(e["id"])
            if (e["keys"] or "").strip():
                by_keys.setdefault(e["keys"].strip().casefold(), []).append(e["id"])
        canon = chat["lorebook_id"]
        for e in c.execute("SELECT * FROM lore_entries WHERE lorebook_id=?",
                           (copy["id"],)).fetchall():
            if (e["keys"] or "", e["content"] or "") in by_text:
                report["dropped"] += 1
                continue
            target = None
            title = (e["title"] or "").strip().casefold()
            keys = (e["keys"] or "").strip().casefold()
            if title and len(by_title.get(title) or []) == 1:
                target = by_title[title][0]
            elif keys and len(by_keys.get(keys) or []) == 1:
                target = by_keys[keys][0]
            if target is not None:
                c.execute(
                    "INSERT OR IGNORE INTO lore_overlays("
                    "chat_id, frame_id, entry_id, keys, content, category, title,"
                    " knowledge_tag, knowledge_range, knowledge_locations, circles,"
                    " canon_locked, embedding, embedding_model, embedding_dim,"
                    " disposition, source_notes, turn_idx, created"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, None, target, e["keys"], e["content"], e["category"],
                     e["title"], e["knowledge_tag"], e["knowledge_range"],
                     e["knowledge_locations"], e["circles"], e["canon_locked"],
                     e["embedding"], e["embedding_model"], e["embedding_dim"],
                     "migrated_copy",
                     "migrated 2026-09 from the story's copy of %s"
                     % (copy["name"] or "a library book"),
                     e["turn_added"], now))
                report["overlaid"] += 1
                continue
            if canon is None:
                canon = c.execute(
                    "INSERT INTO lorebooks(name,chat_id,book_type,summary,resource_uid)"
                    " VALUES(?,?,?,?,?)",
                    (f"{chat['name']} \u2014 canon", cid, "general",
                     "Chat canon: facts, events and specifics established "
                     "during this chat.", f"book_{uuid.uuid4().hex}")).lastrowid
                c.execute("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, cid))
            c.execute("UPDATE lore_entries SET lorebook_id=?, source_notes=? WHERE id=?",
                      (canon, "; ".join(x for x in (
                          (e["source_notes"] or "").strip(),
                          "moved 2026-09 from the story's copy of %s"
                          % (copy["name"] or "a library book")) if x),
                       e["id"]))
            report["moved"] += 1
        # Re-point every reference at the origin, then drop the copy.
        att = c.execute(
            "SELECT enabled FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?",
            (cid, copy["id"])).fetchone()
        if att is not None:
            c.execute("DELETE FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?",
                      (cid, copy["id"]))
            c.execute(
                "INSERT OR IGNORE INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled)"
                " VALUES(?,?,NULL,?)", (cid, oid, att["enabled"]))
        c.execute("UPDATE room_registry SET owning_book_id=? "
                  "WHERE chat_id=? AND owning_book_id=?", (oid, cid, copy["id"]))
        for col, other in (("source_book_id", "target_book_id"),
                           ("target_book_id", "source_book_id")):
            for link in c.execute(
                    f"SELECT id, {other} AS other, relation_type FROM lorebook_links"
                    f" WHERE {col}=?", (copy["id"],)).fetchall():
                dup = c.execute(
                    f"SELECT 1 FROM lorebook_links WHERE {col}=? AND {other}=? "
                    f"AND relation_type=?", (oid, link["other"], link["relation_type"])
                ).fetchone()
                if dup or link["other"] == oid:
                    c.execute("DELETE FROM lorebook_links WHERE id=?", (link["id"],))
                else:
                    c.execute(f"UPDATE lorebook_links SET {col}=? WHERE id=?",
                              (oid, link["id"]))
        c.execute("UPDATE lorebooks SET parent_id=? WHERE parent_id=? AND chat_id=?",
                  (oid, copy["id"], cid))
        c.execute("DELETE FROM lorebooks WHERE id=?", (copy["id"],))
        report["converted"] += 1
    return report


def _establish_time_of_day_from_variant(content):
    """The standing time of day a stored `director_establish` variant named.

    Restates the live rule (`world.mechanics.normalize_time_of_day` and
    `persist.commit_scene_state._establish_time_of_day`) rather than importing
    it, for two reasons that point the same way: `core` sits underneath
    `world` and `persist`, and a recovery pass is FROZEN against the shape it
    was written for -- it must keep reading a 2026-08 archive the same way
    after the live reader has moved on.

    The clock's own label leads and the scene's `time` follows -- the same
    precedence and the same reason as the live reader: both are filled in 80
    of 80 corpus openings, and in the 17 that disagree it is `time` that
    holds the situation ("Immediate aftermath of a containment breach",
    "now") while the clock beside it holds "08:42:15 AM".
    """
    try:
        est = json.loads(content or "")
    except (TypeError, ValueError):
        return ""
    if not isinstance(est, dict):
        return ""
    clock = est.get("simulation_clock")
    for value in (clock.get("display") if isinstance(clock, dict) else None,
                  est.get("time")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _opening_time_of_day(c, chat_id, frame_id):
    """The opening's time of day for one chat, preferring its own era's."""
    sql = ("SELECT v.content AS content FROM variants v "
           "JOIN steps s ON s.id=v.step_id "
           "JOIN turns t ON t.id=s.turn_id "
           "WHERE t.chat_id=? AND s.key='director_establish' "
           "AND s.stale=0 AND v.active=1")
    # Earliest turn, active variant: the opening, and only the opening.
    order = " ORDER BY t.idx ASC, v.id DESC LIMIT 1"
    if frame_id is not None:
        # AN ERA THAT RAN NO OPENING OF ITS OWN GETS NOTHING, and telling it
        # nothing is the right answer rather than the fallback's cost.
        #
        # This inherited the story's earliest opening, on the reasoning that a
        # split or a branch is the same world at another time. Measured, it is
        # every frame-scoped row in the corpus -- 3 of 3 -- and what they
        # inherit is not a neutral hour: all three plus the frameless base take
        # one era's plot countdown as their standing time of day, onto clocks
        # whose elapsed_seconds are 2143 / 1630 / 1975 / 142. A frame is a
        # different moment BY CONSTRUCTION; that is what makes it a frame. So
        # the one thing its opening cannot supply is when it is.
        #
        # The subtracting branch is also the rule this change applies
        # everywhere else: it removed "now" from five defaults on exactly the
        # ground that a story which has not said what time it is says nothing.
        row = c.execute(sql + " AND t.frame_id=?" + order,
                        (chat_id, frame_id)).fetchone()
        return _establish_time_of_day_from_variant(row["content"]) if row else ""
    row = c.execute(sql + order, (chat_id,)).fetchone()
    return _establish_time_of_day_from_variant(row["content"]) if row else ""


def _stamp_clock_display(c, chat_id, frame_id, label):
    """Put the recovered time of day on the clock's own label.

    `elapsed_seconds` IS NEVER TOUCHED. The numeric clock works and is what
    every windowed thing in the engine compares against; only the reader-
    facing label was carrying the wrong kind of statement.
    """
    key = "simulation_clock" if frame_id is None \
        else f"simulation_clock{_FRAME_KEY_SEP}{frame_id}"
    row = c.execute("SELECT value FROM world WHERE chat_id=? AND key=?",
                    (chat_id, key)).fetchone()
    if row is None:
        return                      # no clock yet; the next commit writes one
    try:
        clock = json.loads(row["value"])
    except (TypeError, ValueError):
        return
    if not isinstance(clock, dict) or clock.get("display") == label:
        return
    clock["display"] = label
    c.execute("UPDATE world SET value=? WHERE chat_id=? AND key=?",
              (json.dumps(clock), chat_id, key))


def _recover_scene_time_of_day(c, chat_id=None, *, only_pre_split=False):
    """Give every stored scene a `time_of_day`, recovering the one its own
    opening named.

    WHY THERE IS ANYTHING TO RECOVER. `scene.time` held two incompatible
    kinds of statement at once: a standing time of day, written once by
    `director_establish`, and a per-beat PASSAGE PHRASE ("moments later"),
    written over it by every resolved beat -- and written as an ERASURE when
    the beat carried an empty one. Measured on the author's 81-chat corpus
    2026-08-25: 63 openings named a time of day a reader could act on, and 6
    live scenes still held one. The openings are still on disk as active,
    non-stale `director_establish` variants in 80 of the 81 chats, so what
    was overwritten comes back with a single join.

    Idempotent, and keyed on the KEY rather than the value: a scene that
    already carries `time_of_day` is never revisited, so a story that has
    since moved on from its opening is not dragged back to it. A chat whose
    opening cannot be found (an import carrying no establish step) gets the
    key with an EMPTY value -- a story that has not said what time it is --
    which is also what stops this from re-querying it on every open.
    """
    where = "(key=? OR key LIKE ?)"
    args = ["scene", f"scene{_FRAME_KEY_SEP}%"]
    if chat_id is not None:
        where += " AND chat_id=?"
        args.append(chat_id)
    rows = c.execute(
        f"SELECT chat_id, key, value FROM world WHERE {where}", args
    ).fetchall()
    for row in rows:
        try:
            scene = json.loads(row["value"])
        except (TypeError, ValueError):
            continue
        if not isinstance(scene, dict) or "time_of_day" in scene:
            continue
        # `only_pre_split` narrows this to rows that ACTUALLY carry the old
        # shape, for callers that are not the migration. The migration wants
        # the empty key everywhere -- its presence is what stops it re-querying
        # every scene on every open. A checkpoint restore does not: it rewrites
        # every world row this chat owns, including other frames', so stamping
        # a key onto a scene that never held the corrupt field would let
        # restoring one era touch another era's row. That is the leak
        # `test_restoring_mid_a_framed_turn_does_not_clobber_the_present`
        # exists to catch, and it caught it.
        if only_pre_split and "time" not in scene:
            continue
        _, frame_id = parse_scoped_world_key(row["key"])
        label = _opening_time_of_day(c, row["chat_id"], frame_id)
        scene["time_of_day"] = label
        # The corrupt field goes with the split rather than sitting beside
        # its replacement: what is in it is a passage phrase in most stories,
        # a bare boolean in one, and a stale copy is how a reader finds its
        # way back to the wrong answer.
        scene.pop("time", None)
        c.execute("UPDATE world SET value=? WHERE chat_id=? AND key=?",
                  (json.dumps(scene), row["chat_id"], row["key"]))
        if label:
            _stamp_clock_display(c, row["chat_id"], frame_id, label)


def recover_scene_time_of_day(chat_id=None, *, only_pre_split=False):
    """`_recover_scene_time_of_day` for callers holding no connection -- the
    archive import path, whose freshly written chat carries a scene from
    before the split and the opening that can repair it."""
    with transaction() as c:
        _recover_scene_time_of_day(c, chat_id,
                                    only_pre_split=only_pre_split)


def init():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row

    # Checked BEFORE executescript creates schema_meta (CREATE TABLE IF
    # NOT EXISTS would otherwise mask this) -- distinguishes a genuinely
    # brand-new database file from an existing one whose version row is
    # merely missing/zero.
    is_fresh_db = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    ).fetchone() is None

    # Both refusals below run BEFORE executescript(SCHEMA) touches the
    # file: a database we are about to refuse must not be altered first.
    if is_fresh_db:
        # "No schema_meta" only means "brand new" when the file is
        # genuinely empty. A file that already has tables but no version
        # stamp is a partial copy, corruption, or a foreign database --
        # executescript(SCHEMA) would adopt whatever shape those tables
        # have (every CREATE is IF NOT EXISTS) and the unconditional
        # stamp below would then assert, falsely and permanently, that
        # the file is fully migrated.
        preexisting = [
            row["name"]
            for row in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        if preexisting:
            c.close()
            raise UnstampedDatabaseError(
                f"{DB!r} already contains tables ({', '.join(preexisting[:8])}"
                f"{', ...' if len(preexisting) > 8 else ''}) but no "
                "schema_meta version stamp. This is not an engine-created "
                "database; refusing to adopt or migrate it. If ENGINE_DB "
                "points at the wrong file, fix the path; if the database is "
                "a damaged copy, restore from a complete one."
            )
    else:
        current = _get_schema_version(c)
        if current > SCHEMA_VERSION:
            c.close()
            raise SchemaVersionTooNew(
                f"{DB!r} is at schema version {current}, but this engine "
                f"only understands up to {SCHEMA_VERSION}. It was written "
                "by a newer engine; opening it here could corrupt it. "
                "Update the engine (or open a database this version "
                "created)."
            )

    # Only past both guards may the file be touched at all -- even
    # PRAGMA journal_mode=WAL is a persistent file-header write, and a
    # database we refuse must come out byte-identical.
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")   # see conn(), same reasoning
    c.execute("PRAGMA foreign_keys=ON")

    c.executescript(SCHEMA)
    c.commit()

    if is_fresh_db:
        # SCHEMA above is always the CURRENT, fully up-to-date structure
        # -- a brand-new database needs none of the incremental ALTER
        # TABLE migrations below, which exist only to bring an OLDER,
        # already-populated database up to date. Running them anyway
        # was previously "safe" only because every statement happened to
        # be a harmless duplicate-column/already-exists no-op against
        # the just-created schema; that stops being true the moment any
        # future migration does something non-idempotent (a data
        # backfill, an UPDATE, a DROP). It was also running out of
        # order: `MIGRATIONS[i-1]` for the loop's first iteration
        # (current=0) evaluates to `MIGRATIONS[-1]` -- Python's negative
        # indexing wraps to the LAST (most recent) migration, so it ran
        # FIRST rather than being skipped, silently correct only by luck.
        _set_schema_version(c, SCHEMA_VERSION)
    else:
        # `current` was read (and bounds-checked) above, before SCHEMA ran.
        for i in range(current, SCHEMA_VERSION):
            if 0 <= i - 1 < len(MIGRATIONS):
                for stmt in MIGRATIONS[i - 1]:
                    # DDL autocommits, so a crash mid-list leaves earlier
                    # statements applied with the version not advanced;
                    # re-runnability is what recovers that. ADD COLUMN
                    # idempotence is decided by introspection rather than
                    # by string-matching "duplicate column" in the error.
                    if _column_addition_already_applied(c, stmt):
                        continue
                    try:
                        c.execute(stmt)
                    except sqlite3.OperationalError as e:
                        # The remaining crash-recovery swallow: a CREATE
                        # without IF NOT EXISTS re-run over its own
                        # earlier success (today only the v4->v5 trigger
                        # block, whose DROP-first makes even this inert).
                        if "already exists" not in str(e).lower():
                            raise
                _set_schema_version(c, i + 1)

    # After the chain on BOTH paths: see LATE_SCHEMA's own comment.
    c.executescript(LATE_SCHEMA)

    _backfill_resource_uids(c)
    # Chat copies of library books become references plus overlays. Idempotent
    # (a copy converted is a copy gone) and gated on the copies' existence, so
    # a fresh file and a converted one both do nothing here.
    _migrate_chat_copies_to_overlays(c)
    # After the chain and on both paths, like the backfill above: a fresh file
    # has no scenes to repair, and an existing one is repaired exactly once
    # (see the function -- the key's presence is the gate).
    _recover_scene_time_of_day(c)
    c.commit()
    c.close()

def get_setting(k, d=None):
    r = q("SELECT value FROM settings WHERE key=?", (k,), one=True)
    return r["value"] if r else d

def set_setting(k, v):
    qi(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (k, v),
    )

def wget(chat_id, key, d=None):
    storage_key = _scoped_world_key(key)
    r = q("SELECT value FROM world WHERE chat_id=? AND key=?", (chat_id, storage_key), one=True)
    return json.loads(r["value"]) if r else d

# ---- world-row read tokens -------------------------------------------------
# Process-local change counters that let a reader cache a parsed world row
# and know, for the price of two dict lookups, whether the stored row can
# have changed since. Motivating measurement (2026-08-28, generated market
# town, 307 bodies): the `charters` row is 41.4MB, one fetch+parse+normalize
# costs ~0.95s on the joined shape (~2.3s on the split shape), and a single
# turn read it 21 times with zero intervening writes -- 13.5-20s of a 352s
# turn spent re-deriving one unchanged object.
#
# `wset` is the write chokepoint for world rows, so it bumps the per-row
# counter. Writes that do NOT go through `wset` -- configure() swapping
# databases, checkpoint restore's whole-chat DELETE, story reset, an
# extension deleting a row -- bump the coarse epoch instead, which
# invalidates every cached row at once. Both directions of the race are
# safe: a spurious bump only costs the next reader a re-fetch. What this
# scheme cannot see is another PROCESS writing the same database file
# (e.g. tools/scene_lint.py against a live server); the engine already
# assumes single-process ownership of its file everywhere else.
_world_epoch = 0
_world_write_gen = {}

def bump_world_epoch():
    """Invalidate every world-row read token (see block comment above)."""
    global _world_epoch
    _world_epoch += 1
    _world_write_gen.clear()

def world_read_token(chat_id, key):
    """``(storage_key, token)`` for caching a parsed world row.

    Frame-scoped like `wget`: the ambient active_frame_id decides which
    storage row `key` names, so the caller must ask under the same frame
    it reads under. The token compares equal to a later call's token only
    if no tracked write has landed on that row in between.
    """
    storage_key = _scoped_world_key(key)
    return storage_key, (
        _world_epoch, _world_write_gen.get((int(chat_id), storage_key), 0))

def wset(chat_id, key, val):
    storage_key = _scoped_world_key(key)
    qi(
        "INSERT INTO world(chat_id,key,value) VALUES(?,?,?) "
        "ON CONFLICT(chat_id,key) DO UPDATE SET value=excluded.value",
        (chat_id, storage_key, json.dumps(val)),
    )
    # After the write, not before: a reader between the bump and the write
    # would otherwise cache the OLD row under the NEW token. Bumping after
    # means the worst interleaving caches new data under an old token --
    # which only costs that reader's successor a re-fetch.
    gen_key = (int(chat_id), storage_key)
    _world_write_gen[gen_key] = _world_write_gen.get(gen_key, 0) + 1
    if int(getattr(_local, "tx_depth", 0)) > 0:
        # Inside a transaction the row is invisible to other connections
        # until the outermost commit, so a reader on another thread inside
        # that window would cache the OLD row under the NEW token and keep
        # serving it after the commit. transaction() re-bumps these keys on
        # the way out -- commit or rollback, both directions are safe.
        pending = getattr(_local, "pending_world_bumps", None)
        if pending is None:
            pending = _local.pending_world_bumps = set()
        pending.add(gen_key)

def wget_for_frame(chat_id, key, frame_id, d=None):
    """wget scoped to an EXPLICIT frame_id rather than the ambient
    active_frame_id contextvar -- for code that must read/write a
    frame's storage while some OTHER frame is the pipeline's actual
    active one (e.g. spatial_frames.py's split/merge, which runs inside
    one frame's commit but has to seed or reconcile a SIBLING frame's
    scoped keys too)."""
    token = active_frame_id.set(frame_id)
    try:
        return wget(chat_id, key, d)
    finally:
        active_frame_id.reset(token)

def wset_for_frame(chat_id, key, val, frame_id):
    token = active_frame_id.set(frame_id)
    try:
        wset(chat_id, key, val)
    finally:
        active_frame_id.reset(token)
