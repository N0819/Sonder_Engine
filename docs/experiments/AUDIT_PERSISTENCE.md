# Audit record — `core/`, `language_runtime/`, and the non-commit `persist/`

Status: EVIDENCE. Companion to
[`AUDIT_COMMIT.md`](AUDIT_COMMIT.md) (the sibling `commit_*` modules) and
[`AUDIT_SPATIAL.md`](AUDIT_SPATIAL.md), in the same register.

Scope, read end to end: `core/db.py` (1,696), `core/frames.py` (220),
`core/jobs.py` (209), `core/logging_utils.py` (117), `core/outofband.py`
(276), `core/pipeline_context.py` (312), `core/updates.py` (394),
`core/__init__.py` (6); `language_runtime/__init__.py` (606);
`persist/checkpoints.py` (1,149), `persist/chat_archive.py` (1,115),
`persist/pipeline_trace.py` (413). The `commit_*` modules were read only as
far as needed to check what checkpoints and archives must carry.

Findings are **flagged, never fixed** — no source file was edited for this
audit. `docs/UNBUILT.md` is deliberately untouched (parallel work in
flight); the entries that belong there are marked.

Line numbers are as of `4f33b17` (2026-08-18). The live `engine.db` was read
`mode=ro` only, to compare its schema against `db.py` and to count rows; it
was never written.

---

## 1. Audit findings

### 1.1 The column sweep — what a durable path drops

Method: every table and column was enumerated by building the schema in a
temporary database and reading `PRAGMA table_info`, then each column was
traced through the five durable paths — archive export
(`chat_archive.export_chat`), archive import (`chat_archive.import_chat`),
checkpoint snapshot (`checkpoints.snapshot_state`), checkpoint restore
(`checkpoints._restore_checkpoint_body` → `insert_world_tables`), and
branch/clone (`web/app.py`'s `turn_branch` + `_remap_cp_blob`). The full
matrix is §2.3. Eight losses:

---

**F1 — `relationship_events` is dropped by branching, and its checkpoint
copies keep the SOURCE chat's ids.** Two halves of one gap.

*The live table.* `web/app.py:4972–4977` builds the branch's
`world_tables` from a hardcoded eight-name tuple —
`world_entities, world_placements, world_conditions, scheduled_events,
world_events, room_registry, fiction_worlds, fiction_locations`.
`relationship_events` is not in it, and `insert_world_tables`
(`persist/checkpoints.py:434–445`) reads `b.get("relationship_events") or []`,
so it inserts nothing. Repo-wide grep: the string `relationship_events`
appears in `persist/chat_archive.py`, `persist/checkpoints.py` and
`mind/memory.py`, and **nowhere in `web/app.py`**. A branched chat starts
with an empty stance ledger.

*The checkpoint blobs.* `snapshot_state` DOES include the table
(`checkpoints.py:134–141`), so every checkpoint the branch copies carries
it — and `_remap_cp_blob` (`web/app.py:849–1032`) remaps `memories`,
`memory_summaries`, `chars`, `char_frames`, `frames`, `chat_personas`,
`lorebooks`, `lorebook_links`, `world`, `world_entities`, `world_events`
and `room_registry`, and never touches `relationship_events`. Proved on a
temp database:

```
blob rel_events after the branch's own remap:
  [{'frame_id': 1, 'char_id': 1, 'target': 'Mora', 'note': 'she lied', ...}]
        # frame_idmap said {1: 2}; char_idmap said {1: 777}
branch rows before restore: 0
branch rows after restore:
  [{'chat_id': 2, 'frame_id': 1, 'char_id': 1, 'note': 'she lied'}]
frame 1 belongs to chat 1        # the branch's own frame is 2
```

So the ledger is invisible in a fresh branch and then **appears wholesale on
the first reroll**, stamped with a frame row belonging to another chat.
`relationship_events.char_id` has no FK, so nothing objects; on a
cross-install import the same unremapped `frame_id` hits
`frames(id)`'s FK and aborts the whole restore instead.

Why it matters: `checkpoints.py:126–133` states the contract this breaks —
"a rewind past the argument must take the reason for it too, or a character
goes on holding a grudge about a thing that no longer happened." The v28
migration comment (`db.py:1366–1376`) records that 5,638 recorded reasons
were being destroyed before this table existed; branching destroys them
again, and rerolling resurrects the wrong ones.

---

**F2 — the portable archive carries every memory's embedding vectors and the
import throws them away, re-embedding the entire bank.**
`export_chat` calls `dump_chat_memories(cid)` with the default
`inline_vectors=True` (`chat_archive.py:233`), which emits base64
`embedding`/`cue_embedding` per row (`mind/memory.py:3672–3681`) —
deliberately, and `dump_chat_memories`' own docstring says why:
"a portable ARCHIVE is imported into a DIFFERENT database, where no such
store exists, so it must carry the vectors with it **or the import
re-embeds the whole bank (expensive, and a provider hiccup during it
silently downgrades every vector to the crc32 fallback)**."

`import_chat` then builds its own memory projection by naming 21 keys
(`chat_archive.py:839–871`). `embedding`, `cue_embedding`,
`embedding_model`, `embedding_dim` and `vkey` are not among them.
`prepare_chat_memory_restore` therefore sees `full_blob is None` for every
row, files each as `mode: "legacy"`, and hands the lot to
`prepare_memories_batch` (`mind/memory.py:3739–3750`) — one provider
embedding batch over the whole bank, on the import path, with the crc32
fallback one network error away.

Why it matters: the archive pays the size cost of inlining the vectors and
the import pays the provider cost of not using them. `docs/guides/DATABASE.md`
states the intended behaviour as fact: "the archive's own top-level
`memories` keep their vectors INLINE, because the importing database has
no store to resolve against." They are kept; they are not read.

---

**F3 — the same projection drops `encoding_valence` / `encoding_arousal`.**
Same list, `chat_archive.py:839–871`. `dump_chat_memories` emits both
(`memory.py:3666–3667`) and `prepare_chat_memory_restore` reads both
(`memory.py:3724–3725`), defaulting to `0.0` when absent — so an
export→import round trip silently resets every memory's post-appraisal
affect to neutral while leaving the carried-in affect intact.

`docs/guides/DATABASE.md` says the opposite in as many words: "Since **v24**,
`memories.valence/arousal` are the resolved affect carried into an event and
`encoding_valence/encoding_arousal` are the resolved post-appraisal affect in
which it was encoded; **all four follow the existing
snapshot/archive/portable-bank paths.**" Two follow the archive path. The
checkpoint and branch paths pass the dump dict through verbatim and are
correct, which is why nothing has noticed. `tests/test_memory_psychology_
integration.py:211` asserts the DUMP carries it; nothing asserts the import
does.

The projection's own comment two lines below the gap (`chat_archive.py:862–865`)
argues carefully for carrying `importance` and `disputed` because "neither is
re-derivable from the row's text". Neither is an encoding valence.

---

**F4 — `dump_lorebook` drops `embedding_model` / `embedding_dim`, so every
restore, branch and import un-stamps the whole lore bank.**
`mind/memory.py:3915–3933` emits 16 keys including `embedding`, and not the
two v26 columns. `restore_lorebook` feeds the bytes back through
`add_lore`/`update_lore` with `embedding=` set, and both then write
`embedding_model = NULL` on purpose (`memory.py:4122–4131`, `4156–4161`:
"A caller-supplied vector arrives from a restore or an import, which carries
the bytes but not the stamp"). Measured on a temp database:

```
before:        {'embedding_model': 'real:model:768', 'embedding_dim': 4}
dump keys:     [... 'embedding', 'entry_uid', 'importance', ...]   # no model
after restore: {'embedding_model': None, 'embedding_dim': 4}
```

The premise is true of the dump and false of the row: `dump_lorebook` has
`r["embedding_model"]` in hand and does not carry it. So a single reroll on a
chat re-runs `_restore_books` → `restore_lorebook` and returns every entry in
every touched book to the exact state the v26 migration was built to end.
That migration's comment (`db.py:1311–1335`) is the strongest statement of
cost in the file: 1,061 of 1,418 live entries silently on the crc32 fallback,
invisible to `rebuild_embeddings`, `embedding_bank_status` and
`_warn_stranded_embeddings` "because it appeared in none of those instruments
and the question could not be asked about lore at all." `dump_chat_memories`
carries both stamps for memories (`memory.py:3684–3685`); lore is the
asymmetry.

---

**F5 — `transit_edges` round-trips through nothing, and two documents say it
does.** `db.py:763–769`: "The tables are kept (and still tolerated by
import/checkpoint plumbing) **so existing exports keep restoring**."
`docs/guides/DATABASE.md`: "kept only so old imports restore — removal is
planned." Verified by grep: outside `core/db.py`, `transit_edges` appears in
exactly one place in the runtime, `web/app.py:3033` — the chat DELETE list.
It is absent from `snapshot_state`, `insert_world_tables`,
`export_chat`'s nine-table tuple (`chat_archive.py:255–265`), `import_chat`'s
matching tuple (`chat_archive.py:909–919`) and the branch tuple. Its two
siblings, `fiction_worlds` and `fiction_locations`, are in all of them.
An old export containing `transit_edges` rows does not restore them. Both
comments should say "and transit_edges was never wired in", or the table
should be dropped.

---

**F6 — `fiction_worlds.created_turn_id` / `retired_turn_id` are snapshotted
by neither checkpoint nor restore.** `checkpoints.py:151–155` projects five
of seven columns; `insert_world_tables:466–472` inserts the same five. The
archive carries them (`dict(row)`) and then hands the rows to the same
`insert_world_tables`, which discards them. Deprecated table, no runtime
reader — recorded for completeness rather than as a defect to chase.

---

**F7 — `memories.access_count` / `last_accessed` survive no durable path.**
Absent from `dump_chat_memories`, so a reroll, a branch and an import all
reset them to `0` / `NULL`. `mind/memory.py:848` calls the field "written
and unread", and for the ENGINE that is exactly right (`_IMPORTANCE_*`
deliberately refuses a popularity loop). It is not right for the
instruments: `tools/remember_lines.py:158,170–173` reads `access_count > 0`
as "did this memory come back", and `tools/salience_replay.py:34` copies the
database precisely because `search_memories` bumps it. Any reroll silently
zeroes the denominator those tools measure against — the exact hazard
`AGENTS.md`'s fire-rate row warns about ("Always state the DENOMINATOR").

---

**F8 — `world_entities.retired_turn_id` (carried over from `AUDIT_COMMIT.md`
F1.3, now half-closed).** The column comment has been rewritten to
"VESTIGIAL: no writer, and by design" (`db.py:686–695`) and the guard was
verified. But `room_registry`'s own comment still ends "a removed/destroyed
room keeps its row (retire-not-delete) so 'the ship that sank here' stays
retrievable identity, **mirroring world_entities**" (`db.py:745–747`) —
mirroring a column that the file now says has never had a writer. One of the
two comments moved and the other did not. Same class as the `lorebooks`
comment that was corrected in the same pass (`db.py:143–150`).

---

### 1.2 Dead code, and a feature that is entirely dead

**F9 — `core/updates.py` cannot self-update, and has not been able to since
the module layout split.** `REPO_ROOT = os.path.dirname(os.path.abspath(
__file__))` (`updates.py:37`) resolved to the repository root while
`updates.py` sat at the top level. Commit `a6d823f` ("Eighty-one modules
leave the root") moved it into `core/`, so `REPO_ROOT` is now
`<repo>/core`. `_is_git_repo()` (`updates.py:118–131`) compares
`git rev-parse --show-toplevel` — which from `core/` still answers the
repository root — against `REPO_ROOT`, they differ, and it returns False.
Run against this checkout:

```
REPO_ROOT= /home/nathan/Documents/Sonder_Engine/core
is_git_repo= False
check_updates() = {'ok': False,
  'error': "This install is not a git checkout, so it can't self-update."}
```

Both routes (`web/app.py:1895,1899`) return that error unconditionally. The
module docstring still says the git work is "scoped to the repo root (the
directory containing this file)" — a sentence that was true and is now
self-contradictory.

The check was added on purpose: its own docstring says
`--is-inside-work-tree` "is too permissive here: a copied install nested
anywhere below an unrelated checkout would pass". The move turned that guard
against the engine's own directory. This belongs in `docs/UNBUILT.md`.

**F10 — most of `core/logging_utils.py` is dead.** `measure_step` (line 72),
`StepMetrics` (22) and `TurnMetrics` (45) have no caller anywhere in the
repository outside that file — grepped `-w` over every `*.py`, zero hits in
`agents/`, `web/`, `persist/`, `tools/` or `tests/`. That is 58 of 117 lines,
including `StepMetrics.token_count`, `variant_count` and `warnings`, which
nothing has ever set. Only `log_llm_call` is live (`llm/providers.py:2021`).
The module docstring — "Structured logging for pipeline observability" —
describes the design that `PipelineContext.llm_calls` and
`agents/storage.ENGINE_NOTES_KEY` replaced; see `pipeline_context.py:186–197`,
which records that the stderr line "dies with the process" and is why the
durable ledger exists.

**F11 — `core/jobs.py`'s `is_stale` has no caller, and asks the opposite
question to every real consumer.** The module docstring states the contract
(`jobs.py:9–12`): "A job carries the turn it was scheduled FROM
(`base_turn`). A result computed against turn N is not automatically valid at
turn N+3, and **`is_stale` is how a consumer refuses it**." Grepped `-w`:
`is_stale` appears in `core/jobs.py` and `tests/test_jobs_queue.py`, nowhere
else.

The three real consumers each hand-roll the check and all three ask the
inverse question. `jobs.is_stale` (line 199–201) returns
`current_turn > job.base_turn` — "the story moved on". `offscreen.
land_profile_ticks:1500`, `offscreen.land_agent_tick:1863` and
`artifacts.land_artifact_wording:550` all test `current < base_turn` /
`posted_turn > base_turn` — "the story rolled **back** underneath the job",
which is the failure their comments describe ("a story rewound past
`base_turn` no longer …"). The helper is not merely unused; the one rule it
encodes is not the rule anybody needed.

Also test-only in the same module: `status` (166), `history` (177),
`active_jobs` (182), `cancel_chat` (156), `Job.result` (53) and
`Job.as_dict` (60) — no non-test caller for any of them. `_HISTORY` is
therefore a capped-per-chat, uncapped-in-chats table nothing reads.

**F12 — `PipelineContext._fiction_model` and `._simulation_clock` are dead
fields** (`pipeline_context.py:171–172`). Grepped `-w` across every `*.py`:
zero references outside the dataclass declaration, in either attribute or
`ctx["…"]` string form. Their two siblings (`_player_room`, `_books`, and
`_persona`) are live, which is what makes the pair look load-bearing.

**F13 — `compact_checkpoints` reports a hardcoded `"error": ""`.**
`checkpoints.py:860`. No code path assigns it (grepped
`report["error"]` — one hit, the initializer), and the caller that actually
records a failure writes `_COMPACT_STATE["error"]` from its own `except`
instead (`checkpoints.py:963`). Exactly the shape `AUDIT_COMMIT.md` flagged
for `commit_all`'s `"errors": []`: a field that is always empty is
indistinguishable from a field that is never checked.

---

### 1.3 Migrations

**F14 — the v22→v23 table rebuild is the one rebuild without the
crash-resumability guard, and its three siblings document why they have it.**
`db.py:1268` opens with `CREATE TABLE IF NOT EXISTS memory_summaries_v23(`.
The other three recreate-copy-swap migrations all open with a scratch drop —
`db.py:1094` (`DROP TABLE IF EXISTS world_entities_new`), `1172`
(`scheduled_events_new`), `1344` (`world_events_new`) — and v14 says why in
the comment above it: "Drop any leftover scratch table so re-running this
migration after a crash mid-copy doesn't collide with a half-populated
`*_new` table."

Consequence, and it is not symmetric with the others: on a re-run after a
crash between the INSERT…SELECT and the DROP, `CREATE TABLE IF NOT EXISTS` is
a no-op against the half-populated scratch table, the INSERT then violates
`UNIQUE(chat_id, char_id, scope, end_turn_idx)`, and SQLite raises
`IntegrityError` — which is **not** an `OperationalError`, so `init()`'s
`harmless` filter (`db.py:1642–1646`, `"duplicate column" | "already exists"`)
does not swallow it. The database is then stuck below v23 forever, failing on
every start. The scratch name is also the only one of the four not suffixed
`_new`, which is why a pattern grep for the guard misses it.

**F15 — `_backfill_resource_uids` is a data backfill that runs outside the
version gate, on every open, and it is load-bearing because five of seven
lorebook writers do not set the column.** `db.py:1650` calls it
unconditionally after the migration loop, on both the fresh and migrated
branches. It full-scans `characters`, `personas`, `lorebooks` and
`lore_entries` for `NULL OR ''` and stamps what it finds.

The `is_fresh_db` comment twelve lines above (`db.py:1631–1640`) is explicit
that this shape is the hazard being avoided: running migrations against a
fresh schema "was previously 'safe' only because every statement happened to
be a harmless duplicate-column/already-exists no-op … that stops being true
the moment any future migration does something non-idempotent (**a data
backfill**, an UPDATE, a DROP)." The backfill sits directly below that
comment, outside the gate it argues for.

It is not removable as written, because the uid rule has two representations.
Two writers set `resource_uid` explicitly (`persist/commit_mapping.py:139–141`,
`persist/commit_entities.py:400–401`); five do not —
`memory.ensure_chat_canon_book` (`memory.py:4076`), `story/importers.py:1340`,
`:1449`, `:2442`, and `web/app.py:2590`. A book minted by one of those five
carries a NULL uid until the next process start. Live evidence, read-only:
**2 of 200 rows in `engine.db`'s `lorebooks` currently have a NULL
`resource_uid`** (characters 0/51, personas 0/17, lore_entries 0/2586 — the
other three tables' writers all stamp). Exporting such a chat before a restart
ships `resource_uid: null`, and `_import_book_uid` (`chat_archive.py:1104`)
then mints a fresh one, so the book cannot be matched back to its original on
re-import.

*Schema drift check (clean).* The live `engine.db` (v29) was diffed
column-by-column against a database built from `SCHEMA` + `MIGRATIONS`: no
table and no column differs. Only column ORDER differs on `chats`,
`memories` and `memory_summaries`, because `SCHEMA` declares those inline
while the migrations append them. No production code uses positional row
access on those tables, so this is currently harmless — but it means an
`INSERT … VALUES(…)` without a column list would behave differently on a
fresh install than on a migrated one.

---

### 1.4 A configurable value nothing reads

**F16 — a language pack's `fallback` is parsed, validated, published, and
never consulted.** `language_runtime/__init__.py:154–155` normalizes it,
`:236` stores it, `:118` publishes it through `public()` to
`/api/languages`, and `:272–274` rejects a pack whose fallback names a pack
that is not installed. The only resolution path,
`language_pack()` (`:345–356`), does something else entirely: exact id →
the id's base prefix (`key.split("-", 1)[0]`) → `DEFAULT_LANGUAGE`. It never
reads `pack.fallback`. Grepped `-w` across the repo: no reader outside this
module (the other `fallback` hits are `providers.EmbeddingBatch.fallback`,
an unrelated field).

Live: `language_packs/ja/manifest.json` declares `"fallback": "en"`, which is
what the base-prefix rule would have done anyway, so the field is currently
indistinguishable from working. A pack declaring
`"fallback": "zh-hans"` on `zh-hant` would pass validation and resolve to
`zh` → `en` regardless. Either the resolver should consult it or the
manifest key should go.

---

### 1.5 Two representations of one rule, free to drift

**F17 — sibling world-KV ledgers disagree about whether they are per-era.**
`db.py:24–47`'s `FRAME_SCOPED_WORLD_KEYS` lists `pending_obligations` and
`background_presences`. It does not list:

* **`world_pressures`** — written and read by the same module and the same
  commit domain as `pending_obligations`, with the same shape
  (`commit_ledgers.py:28/129` for obligations, `:150/299` for pressures;
  caps 12 and 8; both surfaced into the next resolve payload). One is
  per-era, one is chat-global, and nothing says why.
* **`background_claims`** (`world/background_claims.py:243–426`) — the
  claims an unregistered presence invents, while the presences themselves
  (`background_presences`) are frame-scoped. A claim records what a body
  standing in one era said.
* **`engine_notices`** (`commit_mechanics.py:183`, `commit_destruction.py:403–411`,
  read at `agents/director.py:531` and `:2549`) — "a fuse fired at your
  location" carried to the next beat. Location is per-era; the notice is not.

Live counts, read-only: `world_pressures` 40 rows, `background_claims` 1,
`engine_notices` 50 — all with zero frame-suffixed variants, against
`pending_obligations` 50 / `background_presences` 60+3.

The set's own comment states the test — "Only these `world` keys … hold
genuinely diegetic-era-specific state … Chat-global keys … are cross-frame
CONTRACTS, not per-era state." All three above are per-era state by that
test. Note that a third spelling also exists and is correct:
`world/paradox.py:174–214` keys `paradoxes` by frame INSIDE the value. Three
mechanisms, one question.

**F18 — `ChatArchiveData` declares 20 of its 27 collections and relies on
`extra = "allow"` for the other seven.** `chat_archive.py:84–137`. Missing
from the declaration: `world_entities`, `world_placements`,
`world_conditions`, `scheduled_events`, `room_registry`, `fiction_worlds`,
`fiction_locations` — every normalized world table except `world_events` and
`relationship_events`. They survive today (verified on the installed
Pydantic 1.10.14: `room_registry` and `world_entities` both come back out of
`_model_dump`) purely because `Config.extra = "allow"` (`:135–136`).

The comment on `memory_vectors` (`:93–97`) argues the opposite rule as if it
applied: "Declared, because an undeclared field validates cleanly and is
then silently dropped by `extra="ignore"` — the failure that kept `stations`
inert for 45 scenes." Under `extra="allow"` nothing is dropped; under
`extra="ignore"` seven tables would vanish from every import at once, in
silence. One line of Config stands between the archive and that.

Separately: `relationship_events` is the one declared list omitted from the
`_legacy_null_list` pre-validator (`:110–124`). Every other list is
null-tolerant. The class docstring records that this exact intolerance is
invisible on Pydantic 1 and 400s the whole archive on Pydantic 2; only
Pydantic 1 is installed here, so the consequence is reasoned from the
module's own documented divergence rather than executed.

**F19 — `StepTaggedWarnings` does not catch "every spelling", and says it
does.** `pipeline_context.py:47–79`. The docstring's argument for tagging in
the container rather than at ~40 call sites is: "Tagging here catches every
spelling, **including the ones not written yet**." It overrides `append` and
`extend` only. `list.__iadd__` is the C-level extend and does **not**
dispatch to a subclass's Python `extend` — confirmed:

```python
class L(list):
    def append(self, x): print("append called", x); super().append(x)
    def extend(self, xs): print("extend called"); [self.append(x) for x in xs]
L() .__iadd__(["a"])   # prints nothing; the item lands untagged
```

`insert`, slice assignment and `__setitem__` are the same. Each silently
desynchronises `notes` from the list, so `for_step` returns a warning under
no step and the pipeline drawer shows it nowhere. No production site
currently uses `+=` (grepped) — this is a live trap for the next writer, not
a live defect, and it is a trap precisely because the docstring says it is
closed.

---

### 1.6 Silent tolerance of missing, empty or unknown values

**F20 — `checkpoint_storage_status` and `_candidate_blob` disagree about what
"legacy" means, and the disagreement can wedge the maintenance panel.**
`checkpoints.py:729` classifies a checkpoint as legacy when its FIRST memory
entry has a truthy `embedding`. `_candidate_blob:471–474` refuses to move a
vector unless BOTH `embedding` and `cue_embedding` decode
(`if full is None or cue is None: continue # nothing safe to move`). A store
whose memories carry a full vector and no cue vector therefore reports
`legacy > 0` forever, and `start_compaction` (`:969–993`) starts a run that
moves nothing, reports `rewritten: 0`, and is immediately eligible to be
started again. The two predicates should be one.

The same probe reads only `mems[:1]`, so a checkpoint whose first memory is
unembedded reports as already-compacted and `start_compaction` refuses with
"nothing to convert" while its remaining inline vectors stand.

**F21 — a lorebook link that fails to restore is dropped in silence.**
`mind/memory.py:4118–4120`: `except Exception: pass` around
`add_lorebook_link`. A restore that loses a typed relationship between two
books reports nothing at any layer.

**F22 — a malformed preserved setting silently rolls back.**
`checkpoints.py:314–316`: `_preserved_settings` does
`except (TypeError, ValueError): continue`, so a `world` row whose JSON will
not parse is simply left out of the carry-across and the checkpoint's older
value wins. Every key on that list is a reader-facing dial whose whole reason
for existing is that a reroll must not move it (`PRESERVED_SETTING_KEYS`,
`:483–536`).

**F23 — `_restore_books` returns `{}` and restores nothing when the chat
currently owns no books.** `checkpoints.py:189–190`. A chat whose books were
all deleted since the checkpoint restores its world, memories and entities
and none of its lore, and the caller cannot tell the difference between "no
books to restore" and "the snapshot had none": both are an empty map, and the
empty map also skips the canon rebind and the managed-link replacement below
it.

---

### 1.7 Comments describing behaviour the code no longer has

**F24 — `core/outofband.py`'s docstring says `jobs.py` has not landed.**
`outofband.py:26–35`: "**Not a replacement for `jobs.py`** (branch
`agent-engine`) … **It is not merged, so importing it is not available**;
copying it here would fork the one module whose entire purpose is to stop
this pattern being forked … so that when `jobs.py` lands, this module is the
single seam to delete rather than two hand-written queues to reconcile."

`core/jobs.py` has landed — it is 209 lines in the same package, imported by
`world/offscreen.py`, `persist/commit_memory_write.py`,
`story/artifacts.py` and `persist/checkpoints.py:302`. The seam was not
deleted, and the two modules now duplicate the same primitive: `Job` vs
`Work`, both with `state` in `pending|running|done|failed|cancelled`, both
with a cooperative `cancelled` Event, both with a 32-entry cap
(`jobs._HISTORY_LIMIT` and `outofband.ERROR_LIMIT`, whose comment says
"`jobs.py` caps its history at the same 32" — so the two files already know
about each other). This is a merge that was designed, argued for in prose,
and not performed; it belongs in `docs/UNBUILT.md`.

**F25 — `checkpoint_storage_status`'s docstring claims it avoids a full
parse.** `checkpoints.py:711–714`: "Cheap: one scan of sizes plus a probe of
each blob's first memory entry **rather than a full parse**." The body
(`:722–725`) re-selects the entire blob per row and calls
`json.loads(blob["blob"])` on it before taking `.get("memories")[:1]`. Every
checkpoint in the database is fully fetched and fully parsed. On the corpus
this module's own comments describe — 4.4 GB, 94.5% of it checkpoints — that
is the whole store, and `start_compaction` calls it on every click before
deciding whether to do anything.

**F26 — `db.py:747`'s "mirroring world_entities"** — see F8.

---

### 1.8 Tests that assert on source layout, or against the wrong object

**F27 — `tests/test_relationship_events.py:185–192` asserts a substring count
of a module's source text.**

```python
def test_the_archive_exports_and_imports_it(self):
    source = inspect.getsource(chat_archive)
    assert source.count('"relationship_events",') >= 2
```

The class it lives in is named `TestItSurvivesTheThingsTheGateRequires` and
its docstring states the risk exactly: "The architectural completion gate
asks that relationships 'survive checkpoint, reroll, **branch**,
archive/import and deletion as applicable'. **Both paths enumerate their
tables BY NAME, so a new one is invisible to them until it is listed** — an
export would silently lose the whole ledger and a rewind would leave a
character holding a grudge about a thing that no longer happened. Neither
failure raises anything."

There are not two by-name enumerations; there are four —
`chat_archive.export_chat`, `chat_archive.import_chat`,
`web/app.py`'s branch `world_tables` tuple, and `web/app.py`'s `chat_del`
table list. The table is listed in two of the four. The test counts
occurrences in the two files it thought to look at, and F1 is what the other
two cost. (`chat_del` is covered by the `ON DELETE CASCADE` on
`relationship_events.chat_id`, so only the branch actually loses data.)

**F28 — `tests/test_archive_fidelity.py:114–166` validates the checkpoint
remapper against a hand-built blob rather than a real one.**
`test_checkpoint_cross_install_ids_are_remapped_fail_closed` constructs a
seven-key dict literal and asserts `_remap_cp_blob` remaps all of it. It
never calls `snapshot_state`, so every section `snapshot_state` has gained
since the fixture was written — `relationship_events` among them — is
invisible to the one test whose name promises cross-install id safety. A
fixture built from `snapshot_state(chat_id)` would have failed on F1 the day
it landed.

**F29 — every test in `tests/test_updates.py` monkeypatches the one value
that is wrong.** `:37` and `:84,98` stub `_is_git_repo` outright; `:52`,
`:66` and `:240` stub `REPO_ROOT` to a `tmp_path`. The suite proves that
`_is_git_repo` compares correctly given a `REPO_ROOT`, and never that
`REPO_ROOT` names a git worktree root — which is the property the module
layout split broke (F9). Nine tests, all green, feature entirely dead.

**F30 — `tests/test_world_events_roundtrip.py:128` names a migration one off
from the one it exercises.** `test_v26_migration_adds_frame_scope_and_chat_
partition` sets `schema_meta.value='26'`, which makes `init()` run
`MIGRATIONS[25]` — the **v26→v27** list. The test is correct; the name will
send the next reader to the wrong entry.

---

## 2. What the code actually does — checked against the docs

Sources checked: `docs/guides/DATABASE.md`, `docs/guides/PIPELINE.md`,
`AGENTS.md` (routing table, § Persistence boundaries, § Source-of-truth
order), `CLAUDE.md` § Architecture, `docs/experiments/AUDIT_COMMIT.md`.

### 2.1 `core/`

**`core/db.py`** — the whole persistence substrate in one file: the
`active_frame_id` contextvar and the frame-scoped key rewrite
(`_scoped_world_key` / `parse_scoped_world_key`, with the reset discipline
argued in the header comment), `SCHEMA` (37 tables + FTS), `MIGRATIONS` (28
lists, v1→v29), thread-local connections with WAL + `synchronous=NORMAL`
(benchmarked in the comment at 175× per commit), a re-entrant
`transaction()` that takes a process-wide `_write_lock` at the outermost
level and SAVEPOINTs below it, `q`/`qi`/`qtx`, `data_version()` (the exact
"has another connection committed" test), and `wget`/`wset` plus the
explicit-frame `wget_for_frame`/`wset_for_frame`. `_execute_retry` backs off
on lock errors for autocommit writes and for `BEGIN IMMEDIATE`; a write
inside an open transaction is not retried, which is right — the lock is
already held. `init()` distinguishes a genuinely fresh file from a
version-less one BEFORE `executescript`, stamps a fresh database at
`SCHEMA_VERSION` and skips migrations entirely, and the comment records the
negative-index bug that made the old loop run `MIGRATIONS[-1]` first.
DATABASE.md's § Write helpers and § Runtime database selection are accurate
clause by clause. Findings: F14, F15, F8/F26.

**`core/frames.py`** — the visibility RULE and nothing else, as its docstring
says: `get_frame` (with `None` synthesising the implicit present),
`list_frames`, `create_frame` (rejecting `kind="present"`, requiring
`split_turn_idx` for a spatial split), `frame_ordinal`, `is_memory_visible`
and `is_recognized_in_frame`. `is_memory_visible` checks spatial splits
FIRST and fails CLOSED on a `NULL` `turn_idx` across an unmerged split, then
applies the ordinal rule, then two traveller clauses — and the comment
explaining why the second is needed (the present has no row, so
`get_frame(None)` has an empty traveller list, so a returned time traveller
could recall nothing) is a genuinely load-bearing piece of reasoning. Matches
DATABASE.md's `frames` / `chat_char_frames` entries. No findings.

**`core/jobs.py`** — out-of-band work: `submit` dedupes on `(chat_id, key)`,
copies the contextvar context in the PARENT (so the story language survives
the thread hop) and immediately clears the turn-scoped half of that copy in
the child (`_clear_turn_scoped_context`, `:99–108` — `token_sink`,
`generation_event_sink`, `call_ledger_sink`, `cancel_event`,
`current_warning_sink`, `current_step_key`). A job never raises into the
caller; `_finish` uses an identity check so a late finisher cannot evict its
own successor. All correct. Findings: F11.

**`core/outofband.py`** — the same primitive for `backdrops`/`ambience`:
`KeyedLocks` (a waiter counts itself in under the guard before acquiring, so
the entry can be dropped at zero without racing — the fix the old
"pruning it would race with the waiters" comment could not make), `Work`,
`stopped`, and `Queue` with supersede-not-join semantics for explicit
`force`/`reroll`. Sound. Findings: F24.

**`core/pipeline_context.py`** — `current_step_key` and
`current_warning_sink` contextvars, `note_step_warning`,
`StepTaggedWarnings`, the `ChatData`/`TurnData` row adapters, and
`PipelineContext` with its dict-like `get`/`__getitem__`/`__setitem__`/
`__contains__` over declared fields, `character:<id>`/`reaction:<id>` keys
and an `_extra` bag. `note_llm_call` and `warnings_for_step` both attribute
by contextvar, which `AGENTS.md`'s pipeline-drawer row requires ("Warning
attribution is by contextvar, never by list position"). Findings: F12, F19.

**`core/logging_utils.py`** — `logger`, and `log_llm_call`. Findings: F10.

**`core/updates.py`** — git-based self-update: `_git` (SIGTERM-then-SIGKILL,
so git can clear its own `.lock` files), `_remote_tip` via `ls-remote` so a
check that has nothing to fetch takes no locks, `_sync_if_needed`,
`_incoming_tags` + `_github_releases` for release notes, and an
`--ff-only` install that refuses a dirty tree. Every one of those decisions
is right and none of them run. Findings: F9.

### 2.2 `language_runtime/`

One module. `_load_pack` validates a pack directory hard: id/dirname match,
schema version, direction, adapter name, `output_token_scale` in [1.0, 4.0],
unique card names, complete `_STORY_COVERAGE` and `_STORY_CARDS` for a story
pack, a non-empty `common` prompt policy, authoring defaults, system prompts.
`installed_language_packs` additionally cross-checks every story pack's
system-prompt keys and typed card LEAF PATHS against the English reference,
and every UI pack's message catalogue — then caches both success and failure
(`_pack_failure`), which is what keeps `linguistic()` off a full tree rescan.
`language_pack` is the forgiving read path, `require_language_pack` the strict
authoring path, `language_scope`/`story_language_scope` the contextvar
discipline that stopped every out-of-turn model call resolving to English.
`_linguistic_cached` is `lru_cache`d under the same lock the pack map is
rebuilt under. `AGENTS.md`'s language row — "protocol keys/enums remain
canonical; a story-capable pack must cover deterministic recognition and
rendering, never silently fall back to English guards" — is accurate to this
code. Findings: F16, plus one operational note: `_pack_failure` is only
cleared by `refresh=True`, and the only callers passing it are
`tests/test_language_packs.py` and `tools/project_check.py`. In a running
server a half-written pack drop wedges every language read for the life of
the process, with no route to clear it. Recorded here rather than as a
numbered finding because the caching itself is deliberate and documented.

### 2.3 `persist/checkpoints.py`, `chat_archive.py`, `pipeline_trace.py`

**`checkpoints.py`** — `snapshot_state` assembles the pre-turn blob (world KV
verbatim including frame suffixes, chat_chars state+status, chat_char_frames,
frames, chat_personas, owned+attached+reachable lorebooks with entries and
links, memories by content address, summaries, and eight normalized world
tables). `restore_checkpoint` forces `active_frame_id=None` for the whole
restore (so an already-resolved storage key is not scoped a second time),
cancels ONLY the consolidation job, and runs `_restore_checkpoint_body`:
embedding work first, outside the lock; `_preserved_settings` read before the
wipe and written after; one transaction for everything else. `_restore_frames`
deliberately updates-and-inserts rather than delete-and-reinsert, because
`turns`/`memories`/`chat_personas` reference `frames(id)` with
`ON DELETE SET NULL` and a delete would null out every pre-checkpoint turn's
era. `_restore_books` matches snapshot books by id → origin → name, deletes
chat-owned books no snapshot book maps onto, rebinds canon, and replaces the
managed link subgraph. `insert_world_tables` is the single writer for the
normalized tables and degrades an unmappable `room_registry.owning_book_id`
to NULL rather than FK-failing. `compact_checkpoints` verifies every
candidate field-by-field against its original — including resolving each
vector reference back to the exact bytes — before writing anything, per
story, and discards the story on the first discrepancy. `ensure_checkpoint`
does a cheap existence check outside the lock and the authoritative one
inside. `refresh_checkpoint` patches only the three lore sections, because a
checkpoint is a PRE-turn snapshot. All of that matches DATABASE.md's
§ `memory_vectors` and `AGENTS.md`'s § Persistence boundaries.

**`chat_archive.py`** — `ChatArchiveData`/`ChatImportRequest` (LenientModel,
`extra="allow"`, null-list tolerance), `ArchiveRemappers` as the injected
seam that keeps `app.py` out of the import graph, `export_chat` (version 4:
chat row, frames, turns→steps→variants, world KV, participants, memories,
summaries, events, checkpoints, nine normalized tables, chat_personas,
turn_player_inputs, books+entries+links, embedded character/persona
resources, then the deduped `memory_vectors` the checkpoints reference), and
`import_chat` — one transaction from the `chats` insert to the last
checkpoint, with resource matching by `resource_uid`, deferred
self-referential FKs (frame parents, book parents), frame-scoped world-key
rewriting, and per-table id remaps. `reasoning` is deliberately not portable
and says so at length (`:640–652`). `branched_from` is deliberately not
portable and says so (`:566–567`). Findings: F2, F3, F18.

**`pipeline_trace.py`** — `export_pipeline_trace` (hash-only by default,
`include_content` and `include_all_variants` both explicit opt-ins),
`validate_pipeline_trace` (envelope, digest over everything but
`trace_sha256`, deterministic `(ord, id)` step order, exactly one active
variant per step, per-variant content digests), `replay_pipeline_trace` (a
generator of the persisted event sequence, never a re-execution),
`dump/load/write` with an atomic `os.replace`. Self-contained: it imports
`core.db.q` and nothing else from the engine, which is what lets
`tools/pipeline_trace.py` replay without engine startup. Consistent with
`AGENTS.md`'s trace row. No findings; note only that `variants.reasoning` is
excluded here as well as from the archive, silently rather than by comment.

### 2.4 Column coverage — every table, every path

`E` = archive export, `I` = archive import, `S` = checkpoint snapshot,
`R` = checkpoint restore, `B` = branch/clone.
`—` = intentionally out of scope. `✗` = a gap, with the finding number.

| Table | E | I | S | R | B | Columns a path drops |
| --- | --- | --- | --- | --- | --- | --- |
| `schema_meta` | — | — | — | — | — | global |
| `providers`, `settings`, `host_sessions` | — | — | — | — | — | global / host config |
| `characters`, `personas` | ✓ | ✓ | — | — | ✓ | export omits `name`/`created` (rederived from the sheet); resources are library rows, not chat rows |
| `lorebooks` | ✓ | ✓ | ✓ | ✓ | ✓ | snapshot omits `resource_uid` (survives, `_restore_books` UPDATEs a column list); branch mints a fresh uid deliberately |
| `lore_entries` | ✓ | ✓ | ✓ | ✓ | ✓ | **`embedding_model`, `embedding_dim` — F4**, dropped by all five (`dump_lorebook` never emits them) |
| `lorebook_links` | ✓ | ✓ | ✓ | ✓ | ✓ | `id`, `created` reassigned on restore (correct) |
| `chat_lorebooks` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `lore_gen_jobs` | — | — | — | — | — | authoring scratch, deliberately excluded (DATABASE.md agrees) |
| `chats` | ✓ | ✓ | — | — | ✓ | `branched_from` deliberately not portable; `id`/`created` reassigned |
| `chat_chars` | ✓ | ✓ | partial | partial | ✓ | snapshot carries `state`+`status` only; `sheet` and `dialogue_color` are authoring, deliberately not rolled back |
| `chat_char_frames` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `chat_personas` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `turn_player_inputs` | ✓ | ✓ | — | — | ✓ | turn-scoped; removed with the turn |
| `frames` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `turns` | ✓ | ✓ | — | — | ✓ | turn-scoped |
| `steps` | ✓ | ✓ | — | — | ✓ | — |
| `variants` | ✓ | ✓ | — | — | ✓ | `reasoning` deliberately not portable (E/I); branch carries it |
| `events` | ✓ | ✓ | — | — | ✓ | — |
| `memories` | ✓ | ✗ | ✓ | ✓ | ✓ | **import drops `encoding_valence`, `encoding_arousal` — F3**; **import drops `embedding`/`cue_embedding`/`embedding_model`/`embedding_dim`, forcing a full re-embed — F2**; **`access_count`, `last_accessed` dropped by all five — F7** |
| `memory_vectors` | ✓ | ✓ | by reference | by reference | same DB | append-only, never GC'd (DATABASE.md correct) |
| `memory_summaries` | ✓ | ✓ | ✓ | ✓ | ✓ | `id` reassigned; `support` carried (v25) |
| `world` (KV) | ✓ | ✓ | ✓ | ✓ | ✓ | frame suffixes remapped on I and B; `PRESERVED_SETTING_KEYS` overlaid after restore |
| `checkpoints` | ✓ | ✓ | — | — | ✓ | blob remapped by `_remap_cp_blob` — see F1 for what it misses |
| `world_events` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `relationship_events` | ✓ | ✓ | ✓ | ✓ | **✗** | **F1** — absent from the branch tuple and from `_remap_cp_blob` |
| `world_entities` | ✓ | ✓ | ✓ | ✓ | ✓ | `retired_turn_id` round-trips and has no writer — F8 |
| `world_placements` | ✓ | ✓ | ✓ | ✓ | ✓ | decommissioned; round-trip kept for old blobs (correct) |
| `world_conditions` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `scheduled_events` | ✓ | ✓ | ✓ | ✓ | ✓ | frame refs in payload remapped by `_remap_scheduled_event_frames` |
| `room_registry` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `fiction_worlds` | ✓ | partial | partial | partial | partial | **`created_turn_id`, `retired_turn_id` — F6** |
| `fiction_locations` | ✓ | ✓ | ✓ | ✓ | ✓ | deprecated |
| `transit_edges` | **✗** | **✗** | **✗** | **✗** | **✗** | **F5** — in no path but chat deletion |
| `guest_grants` | — | — | — | — | — | correctly excluded: credential hashes |
| FTS shadow tables | — | — | — | — | — | maintained by triggers / `_upsert_memory` |

Columns written and never read (this slice): `world_entities.retired_turn_id`
(F8, already on record); `memories.access_count` / `last_accessed` (written by
`search_memories:2137`, read only by `tools/remember_lines.py` — and reset by
every durable path, F7).

### 2.5 Documentation verdicts

*Right, checked clause by clause:* DATABASE.md § Write helpers, § Runtime
database selection, § `memory_vectors` (both rules, and the
`dump_chat_memories(inline_vectors=…)` distinction), the `chat_chars` /
`chat_char_frames` / `frames` / `chat_personas` / `turn_player_inputs`
entries, the `world`-blob paragraph, the `room_registry` and
`world_placements` authority statements, the `lore_gen_jobs`
not-exported/not-checkpointed decision, the per-story-card-override
paragraph, and the offscreen frame-scoped-world-key paragraph. AGENTS.md's
§ Persistence boundaries and § Source-of-truth order are accurate to
`checkpoints.py` and `chat_archive.py`.

*Wrong — the code is right and the guide should change:*

* DATABASE.md, `memories`: "**all four** follow the existing
  snapshot/archive/portable-bank paths." Two of the four do not follow the
  archive import path (F3).
* DATABASE.md, § `memory_vectors`: "the archive's own top-level `memories`
  keep their vectors INLINE, because the importing database has no store to
  resolve against." They are kept and then discarded by the import (F2).
* DATABASE.md, `fiction_worlds`/`fiction_locations`/`transit_edges`: "kept
  only so old imports restore." True of the first two, false of the third
  (F5). `core/db.py:763–769` repeats the same claim.

*Wrong — code comments, correcting them is behaviour-adjacent:*
`core/db.py:747` ("mirroring world_entities", F26/F8);
`core/updates.py:5–6` ("scoped to the repo root (the directory containing
this file)", F9); `core/outofband.py:26–35` ("It is not merged", F24);
`persist/checkpoints.py:713` ("rather than a full parse", F25);
`core/jobs.py:11` ("`is_stale` is how a consumer refuses it", F11);
`core/pipeline_context.py:55` ("catches every spelling, including the ones
not written yet", F19).

*Described but not built:* the language-pack `fallback` chain (F16); the
`outofband.py` → `jobs.py` merge (F24). Both belong in `docs/UNBUILT.md`
once the parallel work on that file settles, along with F9 (self-update
dead).

---

## 3. Unverified suspicions

Recorded separately because I could not prove them from this slice.

* **`_pack_failure` has no in-process recovery.** The negative cache is
  cleared only by `installed_language_packs(refresh=True)`, whose only
  callers are a test and `tools/project_check.py`. I have not confirmed
  there is no route or reload that reaches it indirectly, so this is a
  suspicion rather than a finding — but if it holds, a half-written pack
  drop makes every language read raise until the server restarts.
* **`db.close_connection()` inside an open transaction would strand
  `_write_lock`.** It sets `_local.tx_depth = 0` without releasing the
  outermost acquisition (`db.py:1424–1432`). I found no caller that does
  this (`configure()` is the only production caller and is test-facing), so
  it is a latent hazard rather than a live one.
* **Frame-scoping omissions beyond F17.** `ambience_pins`, `living_world`,
  `survival_track_npcs` and `presence_id_namespace` are also chat-global
  world keys. Whether each of those is genuinely a cross-frame contract
  needs the owning subsystem's judgment, which is outside this slice.
* **New columns on SCHEMA-created tables have no migration path by
  construction.** Tables created only by `SCHEMA` (`frames`, `room_registry`,
  `relationship_events`, `memory_vectors`, `chat_personas`,
  `turn_player_inputs`, `guest_grants`, `host_sessions`, `lore_gen_jobs`)
  would silently never gain a column added after their introduction unless
  someone remembers to write the `ALTER`. The live `engine.db` is currently
  clean on every one of them, so this has not yet bitten; I have not
  reconstructed the git history that would prove it never can.
