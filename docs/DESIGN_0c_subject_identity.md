# 0c design note — subject identity and the G3 liveness gate

Status: measurement written up. **No route chosen. Not reviewed, not agreed.**

Anchored to `Sonder_Engine_working/spatial.py`, sha256
`107d04263d4db204ddeb586e28c1624c35f7dc7036f7d61cc90273fa44820f8f` (255,382 B).
Bodies extracted by AST in a sandbox, collected to `_runs/d86c1ce9f24f54bb/live.txt`
(5,047 B, sha256 `c66ce88fd299743feeaee453e5b8e6655bc02ec58ee79403a2fe9dd51d167e71`)
and read back as bytes. Every line number below is a coordinate **in that version**.
If spatial.py moves, re-derive before quoting one.

---

## 1. What makes a spelling "live"

`_SUBJECT_KEYED`, spatial.py 2981–2982, six entries exactly:

    positions, scales, attire, stations, contained, following

`_live_subject_spellings`, spatial.py 2985–3020, harvests **exactly ten positions**
and nothing else. Every harvested string is `str(value or "").strip().casefold()`,
empties dropped.

**Six KEY positions** — the dict *keys* of `positions`, `scales`, `attire`,
`stations`, `contained`, `following`. Each guarded by `isinstance(table, dict)`.

**Four VALUE positions** —

| position | what it names |
|---|---|
| `contained[*]["in"]` | the container |
| `following[*]["target"]` | the followed |
| `contacts[*]["actor"]` | one party to a contact |
| `contacts[*]["target"]` | the other |

`contacts` is a **list**, is **not** in `_SUBJECT_KEYED`, and its keys are
therefore never harvested; only those two fields reach the set.

**Explicitly excluded**, by the function's own docstring and by the code:
`stations[*]["at"]` (an anchor, not a subject) and `positions` **values**
(rooms — "naming a place is not naming somebody").

**Never consulted at all:** `world_conditions.subject_id`,
`standing_intentions.who`, `world_entities`, `world_placements`,
`room_registry`, the cast and persona tables. The function reads the scene
dict and stops.

---

## 2. The caller list

Tree-wide grep returned two hits: the definition at spatial.py:2985 and one
call at spatial.py:3066, inside `canonical_subject_map`.

**The caller list is `canonical_subject_map` alone — not wider.** Liveness is
not a general engine concept. It is one private predicate of one function, and
nothing else in the tree asks whether a spelling is live.

---

## 3. The gates, in order (`canonical_subject_map`, 3023–3088)

| gate | line | test |
|---|---|---|
| G1 name uniqueness | 3068–3069 | `len(hits) != 1` → skip. Two entities sharing a name fold nothing. |
| G2 self-evidence | 3070–3071 | `name.casefold() == str(eid).strip().casefold()` → skip. |
| **G3 liveness** | **3072–3073** | **`name.casefold() not in live` → skip.** |
| alias rule | 3075–3078 | alias folds only if exactly one entity claims it and it is not itself somebody's name |
| G4 cross-name filter | 3080–3081 | drop any key that is another entity's name |

G3's stated purpose, from the comment at 3057–3064: the defect being repaired
is TWO RECORDS FOR ONE BEING, and folding on identity alone previously broke
eleven tests — carried lights, derived stations, destruction cascades. G3 is
the brake that stopped that. It is load-bearing and it has a measured
regression history.

---

## 4. The circularity, for ledger-free kinds

For a subject kind that owns no scene ledger — a **faction**, a **crowd**, a
**room in `room_registry`'s namespace** — the six KEY positions are
unreachable *by construction*: such a subject has no position, no scale, no
attire, no station, is not contained and does not follow.

So G3 can be satisfied only through the four VALUE positions — and every one of
those is an assertion **some other subject** makes about its relation to this
one.

**(a) Identity flickers on a third party's state.** A faction is
canonicalisable this turn because somebody happens to be in contact with it,
and not next turn when that contact lapses — with no change whatever to the
faction's own record. A room is live only while something is `contained` "in"
it. These are accidental doors, not identity assertions.

**(b) Minting is circular.** If 0c mints subject ids for ledger-free kinds and
expects `normalize_scene_subjects` / `canonical_subject_map` to canonicalise
their spellings, the expectation closes on itself: to be folded you must be
live; to be live you must appear in a ledger you are not eligible for.

**(c) Therefore the 0c identity gate cannot be liveness.** Whatever decides
"these two spellings name one subject" for a faction must be a *different*
predicate from the one at spatial.py:3072.

---

## 5. Three candidate routes. None chosen.

### Route A — mint into a subject-keyed ledger

Give ledger-free kinds a row in one of the six, or add a seventh ledger to
`_SUBJECT_KEYED`, so G3 is satisfied by construction.

**Cost.** The six existing ledgers carry embodiment semantics — a faction has
no room, no scale, no attire — so writing one there makes every consumer of
that ledger read a non-embodied subject as embodied. A seventh ledger avoids
that, but requires auditing every consumer that *iterates* `_SUBJECT_KEYED`
rather than naming a ledger literally, and it makes presence-in-the-registry
its own evidence of liveness, which is precisely the self-evidence G2 exists
to refuse.

**Falsifier / next measurement.** Census: how much code iterates
`_SUBJECT_KEYED` versus naming a ledger literally. If iteration is rare, A is
cheap; if it is the norm, A is a tree-wide change.

### Route B — widen G3 to accept a registry

Liveness becomes "live in a ledger **or** present in an identity registry".

**Cost.** G3's value depends entirely on the witness being *independent* of
`scene["entities"]` — which is the same dict the fold is already reading. A
registry populated from that dict re-creates the eleven-test regression the
comment at 3057–3064 records. It also changes behaviour for ledger-**backed**
kinds: an entity present in the registry with no ledger row would now fold,
where today it does not. That is a behaviour change to a function with a
measured regression history, so it needs the full suite, not a unit test.

**Priced 2026-08-08. Measured, not argued.**

`SELECT COUNT(*)` against the `engine` reference database: **`world_placements`
is 0 rows.** Its schema is `PRIMARY KEY(chat_id, subject_id)` — it is the table
whose key shape 0c wants, and nothing has ever written to it.

It is not merely unwritten, it is **deliberately decommissioned and guarded**.
`tests/test_world_authority_consolidation.py` (9,574 B, sha256
`8cd2325e79fbebcffe24ba4da4abcae815852acd0d9e4cb9c54fbb54478eeaee`) states the
authority model in its module docstring — "`world_placements` is decommissioned
dead data (no runtime writer or reader; kept only so old snapshots/exports
restore)" — and pins it with `test_world_placements_have_no_runtime_writer`,
which commits a full beat and asserts the table is still empty, commented "If a
runtime writer reappears, the authority model has forked and this must fail."

**So Route B on `world_placements` is not widening onto an existing witness. It
is standing up a never-written table, and its first cost is deleting or
inverting a passing regression guard that exists specifically to catch that.**

**The obvious substitute does not rescue the route.** `room_registry` is
populated: 256 rows, 238 live, 93 distinct `room_uid` over 256 distinct
`(chat_id, room_uid)` pairs — the key is per-chat and collides across chats. As
a subject-id key its spellings are clean: 0 rows contain a space, **0 contain a
colon** (so the `<kind>:<tail>` spelling is unoccupied), 13 of 256 contain some
character outside `[a-z0-9_]`. But the same test module names its writers —
"maintained as a deterministic projection of EVERY scene write (`commit_scene`
and, now, the manual world editor)" — corroborated by
`test_world_put_syncs_room_registry_with_manual_scene_edit`, which calls
`app.world_put` and asserts registry rows appear and retire. **That is a
projection of the scene blob, not a witness independent of it**, and
independence is what G3's value rests on. Rooms project from `scene["rooms"]`
rather than `scene["entities"]`, so the dependence is a degree weaker than for
entity kinds; whether that degree is enough is **not measured** and is not
claimed here.

**Residual falsifiers.** (1) The writer roster above is read from test
docstrings and one test body, not from a tree-wide census of `INSERT`/`UPDATE`
sites against `room_registry`; a fourth writer would change the reading.
Settled by a grep of write sites, collected to a file and read back as bytes.
(2) "Usable as a subject id" is scored on colon/whitespace/charset properties,
not against `_NODE_ID`'s actual regex, whose bytes were not read when this was
written.

### Route C — decouple identity from scene liveness

`canonical_subject_map` keeps doing scene-local dedup, unchanged. 0c mints
subject ids in a layer that never consults the scene, and the fold becomes a
**consumer** of those ids rather than a producer of identity.

**Cost.** Two identity mechanisms coexist through the migration, and every
reader that resolves via `same_subject` or `canonical_subject_map` keeps
resolving ledger-backed kinds only until it is moved. The backfill is the 60
live `(chat_id, subject_id)` pairs `_NODE_ID` currently refuses. It is the
only route that does not edit the regression-loaded function.

**Falsifier / next measurement.** Enumerate the readers of `same_subject` and
`canonical_subject_map`. If that list is short, the migration cost is small
and C dominates on risk.

---

## 6. Carried limits

- `normalize_scene_subjects`' docstring names `contacts` alongside the keyed
  ledgers. `contacts` is a list, is not in `_SUBJECT_KEYED`, and reaches the
  fold only through `actor`/`target` values. The prose overstates the roster.
- `same_subject` has no ambiguity guard: `_entity_named` returns the first
  match, so two entities sharing a name fold nothing under G1 but still
  compare `same_subject` True.
- The fold is scene-local and writes to no table. Nothing here persists an
  identity decision; that is what 0c is for.
