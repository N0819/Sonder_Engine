# Split plan — `world/spatial.py`

Status: PROPOSED. Companion to [`DESIGN_MODULE_LAYOUT.md`](DESIGN_MODULE_LAYOUT.md),
which carries the rules every step here obeys (verbatim moves, one module per
commit, flag-never-fix).

8,451 lines · 199 top-level defs · 97 module-level constants. Verified by AST:
199/199 defs and 97/97 constants assigned to exactly one module, no duplicates,
no orphans, resulting graph acyclic by DFS. **Nothing stays** — `world/spatial.py`
becomes a pure facade of ~340 lines.

## Corrections the code forced on the guessed clustering

- **Senses is one module, not three.** Sight, sound, scent and comms bottom out
  on the same `spatial_rel` + barrier + light primitives and share
  `can_perceive_onset`. Splitting them yields sub-300-line fragments with heavy
  mutual traffic.
- **Passability splits in two.** Barrier *vocabulary* is a zero-dependency leaf;
  room-graph *walking* sits three layers up, above light and containment.
- **"Normalisation helpers" is not a cluster.** What exists instead is an
  identity layer (`_ci_get`, `same_subject`, `room_of`, `_entity_named`,
  `canonical_subject_map`) that 9 of 13 modules reach into. Extracting it is
  what makes the whole split acyclic.
- **Contact prose splits from contact vocabulary.** `_clean_contact` calls
  `contact_manner_kind`/`_is_anatomical_part`, which sit 1,900 lines lower among
  the phrase renderers. Left alone this is a hard cycle.

## Modules

| module | ~lines | owns |
| --- | --- | --- |
| `world/spatial_identity.py` | 388 | What a name in a scene refers to — ledger lookup, entity resolution, subject canonicalisation, room-id normalisation. **Leaf.** |
| `world/spatial_barriers.py` | 400 | Barrier vocabulary and the four class sets saying what a barrier passes. **Leaf.** |
| `world/spatial_geometry.py` | 929 | Where a body stands and which way it faces — anchors, stations, facing, proximity, sides/arcs, poses, room size, egocentric frame. |
| `world/spatial_light.py` | 201 | Illumination — the ladder, source aggregation with radius falloff, per-room and per-position light, the light→sight ceiling. |
| `world/spatial_routing.py` | 870 | Walks over the room graph — edge distance, `spatial_rel`, adjacency, passable routes, sprint reach, corridor sightlines. |
| `world/spatial_senses.py` | 1229 | What reaches a perceiver — comms, sight grading, hearing with its material ladder and bearing, scent, perceiver acuity. |
| `world/spatial_containment.py` | 644 | Relative scale and enclosure — how big a body is, what encloses it, what that hides, what a size change breaks. |
| `world/spatial_contacts.py` | 1150 | The contact ledger — part/region identity, manner/relation/motion classification, cleaning, op application. |
| `world/spatial_contact_migration.py` | 321 | Converting contact prose the Director wrote into entity `state` into real contact records. Optional; see resistance. |
| `world/spatial_substance.py` | 593 | Substances on and in bodies — placement, pooling, absorption, consumption, transfer, speech impediment. |
| `world/spatial_prose.py` | 325 | Reader-facing contact phrase renderers and the aggregate `spatial_facts` bundle. |
| `world/spatial_transit.py` | 363 | `parent_entity`-linked rooms — derived dock edges, inferred body enclosures, nesting-aware ambient scope. |
| `world/spatial_merge.py` | 1015 | The deterministic scene merge — room/entity field merging, follow ops, structural repair, `merge_scene_with_diff`. |

Full symbol-by-symbol assignment with line numbers is reproduced in the
implementer brief; the boundary decisions that are *not* mechanical are below.

## Four cycles the naive line-order split would have produced

Each was real; each is pre-empted by moving one symbol against file order.

1. `geometry ↔ senses` — `effective_station → crossing_of` against
   `_opening_view_cap → effective_station`. **Fix:** `crossing_of` +
   `THRESHOLD_CROSSING_BEATS` move up into geometry; `crossing_visible_from`
   stays in senses.
2. `contacts ↔ prose` — `_clean_contact → contact_manner_kind` and
   `contact_phrase → _MOMENTARY_SET`. **Fix:** the 11 contact *classification*
   symbols at 6149–6286 move up into contacts; only the three *rendering*
   symbols stay in prose.
3. `light ↔ barriers` if merged — via `light_at → proximity_rel → …
   → normalize_barrier`. **Fix:** light stays its own module.
4. `routing ↔ senses` if `_LIGHT_SIGHT`/`SIGHT_LEVELS` moved to senses, against
   the existing `senses → routing` edge. **Fix:** they stay in light. This is
   the least obvious cycle in the file.

## Module-level state

**There is none, and this is the plan's luckiest fact.** Verified three ways:
no `global` statement anywhere (AST scan for `ast.Global`: 0 hits); no
module-level constant is ever mutated (scan for subscript-stores and in-place
method calls whose receiver is a module-level name: 0 hits); no caches, memo
dicts or `lru_cache`. All 97 module-level names are read-only constants.

Two constants are evaluated at import time from another top-level name — the
only import-order hazards:

- `_SENSE_LADDERS` (2005) reads `SIGHT_LEVELS`, which lands in a *different*
  module. Safe as specified, but inverting the direction gives a `NameError` at
  **import** time rather than a test failure. Flag it in the senses commit.
- `_MOMENTARY_SET` (3896) reads `CONTACT_MOMENTARY_MANNERS`; both in contacts.

## Execution order

Leaf-first. Steps 1–2 independent; 3 and 4 independent; 6 and 7 independent.

1. `spatial_identity` · 2. `spatial_barriers` · 3. `spatial_transit` ·
4. `spatial_containment` · 5. `spatial_contacts` ·
6. `spatial_contact_migration` · 7. `spatial_substance` ·
8. `spatial_geometry` · 9. `spatial_light` · 10. `spatial_routing` ·
11. `spatial_senses` · 12. `spatial_prose` · 13. `spatial_merge`

Per step: create the file (docstring, import header, symbols cut verbatim in
current order, each carrying the comment block above it) → delete those lines →
add the `from <new> import (...)` block at the **top** of `world/spatial.py`
(`_SENSE_LADDERS` and `_MOMENTARY_SET` evaluate at import) → `make map` →
`make check` → commit.

`AGENTS.md`'s routing table names `world/spatial.py` in thirteen rows, each citing
specific symbols. Update each row in the step that moves its symbols —
`CLAUDE.md`'s rule is that the doc row lands in the same commit as the change.
`docs/guides/ENGINEERING.md:274` and `Design.md:256,595` also name the file.

## Facade

296 names from the 13 new modules plus 11 from `spatial_orientation` = **307
re-exported**. All 134 contract names covered (set-difference verified empty),
including all 20 private ones. Keep `from schemas import
NON_ENTITY_FIELD_KEYS, is_derived_entity_name` — those are attributes of
`spatial` today.

Two live attribute accesses the import census missed, both covered:
`spatial._VALID_BARRIERS` (`tests/test_crowds.py:258`) and
`spatial._clean_contact` (`tests/test_continuous_contact_sensation.py:507,
515, 532, 544`).

**Zero monkeypatching of `spatial`** repo-wide (`setattr(spatial`,
`monkeypatch.setattr("spatial"…`, `patch.object(spatial`: no hits). This file
is free of the hazard that shapes the other two plans. Re-check before
executing if new tests have landed.

Note: `tools/project_check.py`'s duplicate-symbol check is **per-file**, not
cross-file, and `from X import Y` defines no top-level `FunctionDef`. The
one-symbol-one-module rule still holds for correctness — two definitions would
silently diverge — just not because that check enforces it.

## Resistance

1. **`derive_scene_stations` straddles geometry and contacts.** It derives a
   station from a standing contact, which is the only reason a 929-line module
   about anchors imports the 1,150-line contact ledger. The alternative closes a
   cycle. Accept the edge.
2. **`world/spatial_light.py` is 201 lines and cannot be grown.** The only legal merge
   is into geometry (~1,130 lines). Take it if you prefer twelve modules to a
   small one; the layering reads better with light named.
3. **`SIGHT_LEVELS`/`_LIGHT_SIGHT` look like senses and must not go there** —
   see cycle 4.
4. **`corridor_sightlines`, `visible_adjacent_rooms`, `sprint_reach` are sight
   functions living in routing.** They are there because they are multi-room
   graph walks; moving them puts senses at ~1,780 lines. Clean future seam:
   `spatial_topology` (310) and `spatial_reach` (549).
5. **Eleven functions are themselves too long** and are not to be touched:
   `merge_scene_with_diff` 318, `apply_contact_ops` 318, `sprint_reach` 175,
   `apply_transit_dock_edges` 165, `contact_sensation` 144,
   `visible_adjacent_rooms` 143, `hear_level` 138,
   `contacts_from_entity_state` 137, `_resolved_substance_add` 122,
   `_clean_contact` 108, `derive_scene_stations` 104.
6. **Six deferred function-local imports must stay deferred** — lines 489,
   1869, 1962, 5040, 6497, 6704, 8395. They break real cycles with
   `character_schema`, `language_runtime`, `scene` and `survival`. Hoisting any
   during the move produces a circular import.
7. **`import re` is shared today and must be re-declared per module** (six need
   it). A missed one raises `NameError` at *call* time, not import time — which
   is why every step runs the full tier.
8. **No mutual recursion anywhere.** Checked.

## Defects noticed — do not fix here

- **`_SCENT_BARRIERS` is a declared vocabulary its own function ignores.**
  `spatial.py:263` defines it under 14 lines of comment; `scent_level`
  (265–319) never reads it, restating the rule inline as literal tuples at 313
  and 315. Two representations of one rule, free to drift.
  `tests/test_comms_channels.py:518` guards the constant, which decides nothing.
  `AGENTS.md:64` documents it as gating scent "the same way `_SIGHT_BARRIERS`
  gates sight" — true of the latter, false of this one.
- **Ten symbols have no caller anywhere in the repo**: `comms_reach`,
  `owned_region`, `CONTACT_MANNERS`, `CONTAINMENT_MODES`, `_reverse_dir`,
  `CONTAINER_ENCLOSURES`, `_SOUND_BARRIER_PHRASES`, `_SECTOR_PHRASES`,
  `would_create_containment_cycle`, `validate_operations`. Every one is in the
  facade contract, so **none may be deleted as part of this split**.
- **`spatial.py:1884` claims a use that does not exist** — "English
  compatibility views for tests and audits" above two constants no test or audit
  reads. Stale pre-language-pack literals, kept as a claim rather than a check.
- **`would_create_containment_cycle` reads a decommissioned table's shape** —
  it walks `placements[id]["container_id"]`, the `world_placements` record
  structure, which `CLAUDE.md` states is decommissioned.
- **`_phrase_table` re-resolves the language pack on every call and swallows
  every exception.** `sound_bearing` triggers three fresh lookups per
  invocation, each `except Exception: return {}`. A pack misconfiguration
  degrades silently to empty phrases — `CLAUDE.md`'s "an empty one fails
  silently", in the compositor rather than in psychology.
- **`spatial.py:1885–1893` shadows by convention, not by language** —
  `_sound_barrier_phrases`/`_SOUND_BARRIER_PHRASES` differ only in case, as do
  the sector pair. Both pairs must stay together.
