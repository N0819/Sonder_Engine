"""Database layer. Current schema version is SCHEMA_VERSION (see below); migrations run in order from any older version on open."""

import contextvars, sqlite3, json, os, time, threading, uuid
from contextlib import contextmanager

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
    "offscreen_log", "standing_intentions", "shadow_profile", "lore_cache",
    "active_books",
}
FRAME_SCOPED_WORLD_PREFIXES = ("relationships:",)

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

DB = os.environ.get("ENGINE_DB", "engine.db")
SCHEMA_VERSION = 16

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
    sort_order INTEGER NOT NULL DEFAULT 0,
    anchor_entity_id TEXT,
    -- Mirrors world_entities.retired_turn_id: a destroyed vehicle/building's
    -- book is RETIRED (marked with the turn that destroyed it), never
    -- deleted -- its lore stays retrievable history ("the ship that sank
    -- here"). NULL = live. Written only by commit.py's destruction path.
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
-- v10 migration's ALTER TABLE runs, which is also where this index is
-- created (in the correct order, after the column exists). Fresh
-- installs still get both: they run every migration from v0 up too.

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
    entry_uid TEXT,
    importance REAL NOT NULL DEFAULT 0.5,
    aliases TEXT NOT NULL DEFAULT '[]',
    scope TEXT NOT NULL DEFAULT '{}',
    relations TEXT NOT NULL DEFAULT '{}',
    source_notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_lore_entries_book ON lore_entries(lorebook_id);
CREATE INDEX IF NOT EXISTS idx_lore_entries_category ON lore_entries(category);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_entries_uid
    ON lore_entries(entry_uid) WHERE entry_uid IS NOT NULL;

CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(
    content, keys, content='lore_entries', content_rowid='id'
);

CREATE TABLE IF NOT EXISTS chats(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    persona_id INTEGER REFERENCES personas(id) ON DELETE SET NULL,
    lorebook_id INTEGER REFERENCES lorebooks(id) ON DELETE SET NULL,
    scenario TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_chars(
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    char_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active',
    state TEXT NOT NULL DEFAULT '{}',
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
    active INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_variants_step ON variants(step_id);
CREATE INDEX IF NOT EXISTS idx_variants_active ON variants(step_id, active);

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
    confidence REAL NOT NULL DEFAULT 1.0,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed REAL,
    embedding BLOB,
    cue_embedding BLOB,
    embedding_model TEXT NOT NULL DEFAULT '',
    embedding_dim INTEGER,
    archived INTEGER NOT NULL DEFAULT 0,
    event_key TEXT NOT NULL DEFAULT '',
    frame_id INTEGER REFERENCES frames(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_chat_char ON memories(chat_id, char_id);
CREATE INDEX IF NOT EXISTS idx_memories_turn ON memories(turn_id);
CREATE INDEX IF NOT EXISTS idx_memories_chronology ON memories(chat_id, char_id, turn_idx, id);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(chat_id, char_id, category);
CREATE INDEX IF NOT EXISTS idx_memories_event_key ON memories(chat_id, char_id, event_key);
CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_event ON memories(chat_id, char_id, event_key) WHERE event_key <> '';

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, content='memories', content_rowid='id'
);

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
    embedding BLOB,
    embedding_model TEXT NOT NULL DEFAULT '',
    embedding_dim INTEGER,
    updated REAL NOT NULL,
    UNIQUE(chat_id, char_id, scope)
);

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

CREATE TABLE IF NOT EXISTS world_events(
    event_id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    occurred_at REAL NOT NULL,
    duration_seconds REAL NOT NULL DEFAULT 0,
    kind TEXT NOT NULL,
    location_id TEXT,
    payload TEXT NOT NULL,
    seed TEXT,
    committed REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_world_events_chat_time ON world_events(chat_id, occurred_at);

CREATE TABLE IF NOT EXISTS world_entities(
    entity_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    subtype TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL,
    created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
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
-- that sank here" stays retrievable identity, mirroring world_entities.
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
-- The tables are kept (and still tolerated by import/checkpoint plumbing)
-- so existing exports keep restoring; dropping them is Phase 3.
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
]

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
            _write_lock.release()

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

def init():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")

    # Checked BEFORE executescript creates schema_meta (CREATE TABLE IF
    # NOT EXISTS would otherwise mask this) -- distinguishes a genuinely
    # brand-new database file from an existing one whose version row is
    # merely missing/zero.
    is_fresh_db = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    ).fetchone() is None

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
        current = _get_schema_version(c)
        for i in range(current, SCHEMA_VERSION):
            if 0 <= i - 1 < len(MIGRATIONS):
                for stmt in MIGRATIONS[i - 1]:
                    try:
                        c.execute(stmt)
                    except sqlite3.OperationalError as e:
                        msg = str(e).lower()
                        harmless = "duplicate column" in msg or "already exists" in msg
                        if not harmless:
                            raise
                _set_schema_version(c, i + 1)

    _backfill_resource_uids(c)
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

def wset(chat_id, key, val):
    storage_key = _scoped_world_key(key)
    qi(
        "INSERT INTO world(chat_id,key,value) VALUES(?,?,?) "
        "ON CONFLICT(chat_id,key) DO UPDATE SET value=excluded.value",
        (chat_id, storage_key, json.dumps(val)),
    )

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