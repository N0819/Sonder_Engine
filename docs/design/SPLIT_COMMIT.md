# Split plan — `commit.py`

Status: PROPOSED. Companion to [`DESIGN_MODULE_LAYOUT.md`](DESIGN_MODULE_LAYOUT.md).

8,197 lines · 132 top-level defs · 30 module-level constants. 14 new modules
plus `commit.py`; every line accounted for exactly once (ranges sum to 8,197,
verified).

## The section markers are 12 seams and 2 lies

The file carries 14 labelled sections and they were the head start. Two are
load-bearing mistakes:

- **`commit.py:3626 # ---- Mapping commit ----` labels the wrong block.** It
  heads the address-form / name-roster code (3628–3830). The real mapping commit
  is at 5291–5730, sitting unlabelled under `# ---- Background-presence
  tracking ----`.
- **`commit.py:928 # ---- Room registry ----` is the widest lie in the file.**
  It nominally covers 928–2808: room registry, the entire attire subsystem, and
  scene preparation. Three modules are carved out of that one label. An
  implementer trusting the markers would produce a 1,880-line "registry" module.

## Modules

| module | lines | owns |
| --- | --- | --- |
| `commit_common.py` | 370 | Leaf helpers used by more than one domain: scalar utilities, entity-id canonicalisation, the name/address roster. Under target deliberately — this is the module that makes the graph acyclic. |
| `commit_place_graph.py` | 264 | The durable per-mind place graph and the route/dead-end experience it records. |
| `commit_destruction.py` | 400 | Single- and multi-book destruction cascades: what a destruction dooms, who hears, when. |
| `commit_room_registry.py` | 431 | Room identity across frames — the `room_registry` projection, mint dedup, renames, retirement, dangling-exit pruning. |
| `commit_attire.py` | 851 | The mutable clothing ledger: authored notes, shed/worn garment entities, the validated attire diff. |
| `commit_scene_state.py` | 682 | The prepared post-turn scene — book anchoring, ground/weather advance, the pre-lock build, the scene commit. |
| `commit_mechanics.py` | 331 | In-transaction sweeps over time and channel: transit/news arrivals and expiry, the world-event spine, carriers, cast changes. |
| `commit_entities.py` | 486 | The `world_entities` projection, the awareness gate, disguise supersession. |
| `commit_background.py` | 1457 | Unregistered presences: identity folding, per-beat tracking, deterministic reactor selection, promotion to cast. |
| `commit_mapping.py` | 472 | Lore/book mapping commit: proposed book ops, canon fallback ops, the off-screen event normaliser feeding it. |
| `commit_ledgers.py` | 293 | The two world-KV debt ledgers — pending obligations and world pressure. Same shape, same overdue/stall discipline. |
| `commit_memory.py` | 1452 | Pre-lock memory preparation: what each mind may remember, and the psychology/relationship/mind-model deltas riding with it. |
| `commit_memory_write.py` | 212 | The durable memory write and its out-of-band consolidation twin. |
| `commit.py` (stays) | ~580 | Facade, the per-turn commit lock, four thin tail domains, and the top-level atomic commit orchestrator. |

`normalize_offscreen_events` (1043–1077) sits inside the registry block and
belongs to mapping — moving it is correct and makes `commit_room_registry.py`
two non-contiguous ranges.

## The transaction boundary

The outer transaction opens at `commit.py:7920` and closes at 8025.
`db.transaction()` is re-entrant, with depth in `db._local.tx_depth` — a
**thread-local in `db.py`**, not a global of `commit.py`. Outermost acquires the
write lock and `BEGIN IMMEDIATE`; nested becomes `SAVEPOINT`.

**Module identity is irrelevant to this mechanism.** Moving a function to
another file cannot change its depth, its ordering, or whether it is inside the
block — only the call site can, and no call site moves. `_prepare_turn_commit`
and `_commit_all_locked` both stay in `commit.py`, unchanged, calling the same
function objects in the same order; the only difference is that names resolve
through facade imports instead of local defs.

- **Before the lock** (slow preparation): scene, mapping and memory preparation
  plus their whole helper webs — `commit_scene_state`, `commit_destruction`
  (prepare half), `commit_room_registry` (prepare half), `commit_attire`,
  `commit_mapping` (prepare half), `commit_memory`, `commit_place_graph`,
  `commit_background` (claims only).
- **Inside**: transit, world events, scene, entities, cast, paradox, spatial,
  mapping, offscreen plans, crowds, offscreen epoch, memories, carriers,
  background presences, narration person, obligations, world pressure, authored
  events, pending, extensions — in that exact order.
- **After, out of band**: `schedule_memory_consolidation` → `jobs.py`,
  `auto_promote_background_characters`, offscreen ticks, artifact wording,
  `dispatch_turn_committed`, and the blocking `_consolidate_committed_memories`
  twin.

**No proposed boundary crosses the line.** Three functions (`commit_scene:2765`,
`commit_transit_sweep:2828`, `commit_memories:7628`) carry a `prepared or
prepare_*(ctx)` fallback for standalone callers; in every case the fallback line
**precedes** that function's own `with transaction():`, so even on the fallback
path preparation stays outside. That relationship is intra-function and survives
a verbatim move untouched.

## Module-level state

**Only one genuinely mutable global exists**: `_COMMIT_LOCKS` (321, a
`WeakValueDictionary`) with its `_COMMIT_LOCKS_GUARD`, written only by
`_commit_lock`, whose only caller is `commit_all`. All three stay in
`commit.py`. **No boundary touches them.**

Everything else module-level is a frozen constant, verified by regex sweep for
`.add(`/`.append(`/subscript-assignment against each name. **No global is
written by more than one proposed module.**

## Import graph

Acyclic, six tiers. `commit_common` and `commit_place_graph` are leaves; nine
modules import only `commit_common`; `commit_scene_state` adds attire,
destruction and room registry; `commit_mechanics` adds scene state;
`commit_memory` adds background and place graph; `commit_memory_write` adds
memory; `commit.py` imports all fourteen.

**No extracted module references any symbol retained in `commit.py`** — the
dependency is strictly `commit.py → extracted`, never back.

`commit.py:43` imports the private `_merge_entity` from `spatial`; under the
split it goes to `commit_entities.py` alone. The 46 deferred function-body
imports travel **with their functions, verbatim** — they are the existing
cycle-breakers, and hoisting `from agents.common import …` in `commit_memory.py`
or `commit_attire.py` would create a real cycle.

## Facade

`commit.py` keeps its **entire existing top-level import block (1–56)
unchanged** — `_is_empty_view` is a contract name reachable only through it,
several tests monkeypatch `commit.<imported-name>`, and pruning it is a
"while I'm here" cleanup the rules forbid. It leaves ~40 now-unused imports;
`tools/project_check.py` flags used-but-unbound names, never unused ones, so
this is inert. Say why in the facade comment or the next reader reads it as
debt.

Then re-export every moved symbol — not merely the 61 in the contract — so
`getattr(commit, …)` and `commit.__dict__[…]`
(`tests/test_background_dialogue_ownership.py:72`) keep working. Explicit
imports, not `import *`: `project_check`'s undefined-name check skips any module
containing a star-import. Do **not** add `__all__`; there is none today and
adding one changes `import *` semantics.

All 61 contract names map to a home; unmapped: none.

## Execution order

Leaf-first: 1 `commit_common` · 2 `commit_place_graph` · 3 `commit_destruction` ·
4 `commit_room_registry` · 5 `commit_attire` · 6 `commit_entities` ·
7 `commit_ledgers` · 8 `commit_mapping` · 9 `commit_background` ·
10 `commit_scene_state` · 11 `commit_mechanics` · 12 `commit_memory` ·
13 `commit_memory_write` · 14 tooling + docs.

Steps 1–2 commute; 3–9 commute among themselves. 10 must follow 3, 4, 5;
11 follows 10; 12 follows 2 and 9; 13 follows 12.

**Monkeypatch repoints, in the same commit as their step:**

| step | repoint |
| --- | --- |
| 4 | `tests/test_dw_audit_scene.py:55` → `commit_room_registry.persona_name` |
| 6 | `tests/test_awareness_not_from_speech.py:66,103` → `commit_entities.get_scene` |
| 12 | `tests/test_own_conduct_memory.py:58`, `tests/test_memory_affect.py:42`, `tests/test_character_contract_slim.py:65` → `commit_memory.prepare_memories_batch` |
| 13 | `tests/test_consolidation_out_of_band.py:103,136,180` → `commit_memory_write.maybe_consolidate_character_memory`; `tests/test_commit_tail_producers.py:118` → `commit_memory_write._consolidate_committed_memories` |

**Step 14 is not optional.** `tools/project_check.py:878`'s
`check_extension_imports` matches on the first path component, so `import
commit_memory` from an extension bypasses the deep-import guard entirely until
`EXTENSION_DEEP_IMPORTS` (line 648) lists the 14 new names. The split otherwise
opens a hole in an existing invariant. Also: a `MODULE_PURPOSES` entry per
module in `tools/generate_code_map.py:34`, the `AGENTS.md` routing table, and
the `commit.py` sentence in `CLAUDE.md`'s architecture section.

## Resistance

1. **Monkeypatching through the facade is the real cost.** Six test files patch
   an attribute on the `commit` module that moved code reads from its own
   globals. Five fail loudly. One does not:
   `tests/test_commit_tail_producers.py:113–119` installs a raising stub and
   asserts **by absence** that it never runs — after step 13 the patch is inert,
   the test is green, and it can never again catch the regression it was written
   for. This is a general hazard: any future test patching `commit.<anything>`
   will silently miss.
2. **`prepare_memory_commit` is 1,264 lines in one function** — 15% of the file,
   indivisible under the verbatim rule. It is what forces `commit_memory.py` to
   1,452 lines and forces memory into two modules.
3. **`commit_background.py` will not divide.** Tracking and promotion look like
   two modules; nine helpers are called from both halves. Any split needs a
   third module and still leaves boundaries no reader would predict.
4. **Two title lists with a comment insisting they stay distinct**
   (`commit.py:3859–3863`). By nature `_NAME_TITLE_PREFIXES`/`strip_name_titles`
   /`name_in_roster` are roster code belonging in `commit_common`; the comment
   wins, and both stay in background.
5. **Three `prepared or prepare_*(ctx)` fallbacks** reach across the pre-lock
   boundary from inside an in-transaction module, so `commit_mechanics` must
   import `commit_scene_state` and `commit_memory_write` must import
   `commit_memory` purely for a path the turn pipeline never takes.

## Defects noticed — do not fix here

- **`commit.py:3626` labels the wrong block** (see above). Two of fourteen
  navigation aids point at the wrong domain.
- **`commit.py:8–20`: seven imported names are never used and nothing imports
  them from `commit`** — `dump_chat_memories`, `restore_chat_memories`,
  `dump_lorebook`, `restore_lorebook`, `knowledge_for_character`,
  `get_relationships`, `save_relationships`. Dead re-export surface.
- **`commit.py:3859–3863`: a correctness-critical instruction with no
  enforcement.** The comment states that merging the two title sets "would
  silently make mention-detection stricter for short names". No test asserts
  they are disjoint or separately sourced. The failure it describes would be
  silent exactly as described.
- **`tools/project_check.py:878` matches on the first dotted component.**
  Correct today because `commit` is one module; a latent hole the moment any
  `commit_*` module exists, and the kind of guard whose whole value is that
  nobody notices it is off.
- **`tests/test_commit_tail_producers.py:113–119` asserts by absence.** The stub
  raises if reached, so the test proves nothing about its own wiring; if the
  patch target stops being the object the tail calls, it is green and blind.
