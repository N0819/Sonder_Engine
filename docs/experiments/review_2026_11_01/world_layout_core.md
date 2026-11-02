# Audit: `world/layout_arrange.py` (the arrangement-first core) and `world/layout_solver.py` (the lab search / fallback + shared materializer)

Auditor scope as briefed. Working tree at `84f3de23` (clean). Read-only; one test run (cProfile of
the 22 s core test); every other measurement is a `.venv/bin/python` snippet kept in
`<review scratch>/layout_audit/`
(`det.py`, `specs.py`, `specs2.py`, `part.py`, `spots.py`, `doors.py`, `climb_budget.py`,
`backtrack.py`, `bound_share.py`, `timeit_shrine.py`, `base_hash.py`, `base_outl.py`).

## Scope read

Read in full, line by line:
- `world/layout_arrange.py` 1-5169 (constants block 105-677 included; every method of `Leaf`, `_Table`, `_Storey`, `_Building`; `arrange`, `solve_arranged`).
- `world/layout_solver.py` 1-3479. The lab search (646-1734), `_materialize`/`_finish`/`solve`/`solve_with` (1736-1846), doors/windows/zones/furnishing (1849-2570) and `check` (3440-3479) read closely. The grounds (2572-3437, `_things_at_doors`, `_doors_onto_their_ground`, `_grounds`) read in full but checked only for the brief's defect classes, not branch-by-branch -- treat their placement semantics as skimmed.

Read the parts that touch the two modules:
- `world/layout_bridge.py` 125-200 (constants), 2080-2290 (`_arranged`, `_unturned`, `_fell_back`, `solve_spec`, `solve_for`, `lab_solve_for`), 2990-3060 and 3140-3175, 3300-3345 (`planned_layout`'s report).
- `agents/director_layout.py` 89-101, 190-230, 240-420 (`lay_out`), 620-746 (`lay_out_buildings`).
- `core/jobs.py` 95-140 (job threads).
- Docs: `docs/UNBUILT_WORLD.md` §2.43 (3616-4000), `docs/design/DESIGN_LAYOUT_TIER.md` 1040-1130, `AGENTS.md:525`, `Design.md:573`.
- Tests: `tests/test_layout_solver.py` 1-160 and 485-510; `tests/test_the_core_never_lays_worse_than_the_lab.py` 90-260; `tests/test_a_stair_is_climbed_from_its_foot.py` 67-97; `tests/test_a_stair_is_climbed_and_its_landing_reached.py` 66-96, 255-300.

## Findings

### F1 — The core's fallback (and every warning either solver writes) is never logged or filed: "the layout says so" reaches nobody — SILENT-NOOP

Where:
- `world/layout_bridge.py:2094-2104` `_arranged` turns ANY exception from the core (budget, `ValueError`, and also a programming error such as `KeyError`/`TypeError`) into `(None, why)`.
- `world/layout_bridge.py:2136-2141` `_fell_back` puts `why` only on `layout.warnings`:
  ```python
  layout.warnings.append(f"the arrangement core's layout did not stand -- {why}; laid by {by}")
  ```
- `world/layout_bridge.py:3027-3029` `planned_layout` copies them into `report["warnings"]`:
  ```python
  out, report = {}, {"plan": building["plan"], "moved": [], "unplaced": [],
                     "stated": [], "described": [], "marks": [], "restored": [],
                     "split": [], "warnings": list(layout.warnings)}
  ```
  and NOTHING reads `report["warnings"]` (grep: the only occurrence in the repo is this write).
- `agents/director_layout.py:712-741` files the run entry (`signature, turn, plan, moved, unplaced, restored, marks, seconds, grounds*, places_dropped, brief`) and logs one `info` line -- neither carries the warnings. No `logger` exists in `layout_bridge`, `layout_arrange` or `layout_solver`.
- When the core raised AND the lab refuses, `solve_for` returns the lab's refusals with no word of the core at all (`world/layout_bridge.py:2211-2213`), so the filed `reasons` and the "refused" log line never say the core gave up or why.

Scenario: a plan whose core solve passes `ARRANGE_WORK_BUDGET` (or hits a bug -- a `KeyError` in `_fix_flight`, say) is laid by the lab's four seeds; the house the story gets is the old search's (which the owner's own measurement found failing 8-16 of 23 sensible checks), and the only trace is a string on a `Layout` object that is discarded after `planned_layout`. The same drop swallows the core's own notes -- asks given way, "storey 0 was laid larger than its own rooms need", "cannot be climbed foot to head", the cavern turned: 13 warnings on the shrine baseline's core layout (measured, `timeit_shrine.py`), all lost. The module docstring (`layout_arrange.py:68-72`: "the bridge lays the building with the lab's own search ... saying so") and the design note ("lays it instead, with a warning on the layout") are true only of the in-memory object.

Verified: traced `_arranged -> solve_for -> lay_out -> lay_out_buildings -> planned_layout -> _file_run`; grep for every reader of `report["warnings"]`, `layout.warnings`, `logger` in the three modules. The test `test_a_building_the_core_cannot_lay_is_laid_by_the_lab_and_says_so` checks only `layout.warnings` on the returned object, so it passes while production drops it. CONFIRMED.

Fix: in `lay_out_buildings`, log `report["warnings"]` (at `warning` level for the "arrangement core ... did not stand" line) and file them in the run entry (`entry["warnings"] = report["warnings"][:12]`); in `solve_for`, carry `why` into the both-refused return (e.g. append it to the refusals or to the attempts) so a refused run says the core gave up. Test: `temp_db`, monkeypatch `layout_bridge.solve_arranged` to raise, run `lay_out_buildings` with canned answers, assert the `layout_tier_runs` entry names the core's failure.

### F2 — A work-budget expiry during an optional improvement pass discards a complete layout the core already found — WRONG-SCENE

Where: `world/layout_arrange.py:4317-4323` (`_climb`):
```python
for kind in self._turns(kinds[sid]):
    ...
    try:
        again, n2 = self._lay_kinds(b, first, ups, downs, k2, tower)
    except ValueError:
        continue
```
`ArrangeBudget` is a `RuntimeError` (`:680`), raised from `_Storey._tick` (`:1156-1157`) against the building-wide meter, so it escapes `_climb` even though `best` already holds a full chain that `_climb` would otherwise keep with the note "it cannot be climbed foot to head" (`:4336-4339`). The same class: the crushed/severe grow pass `world/layout_arrange.py:4152-4166` (`_carry(... LOOKAHEAD_GROW ...)` with a valid-but-crushed `best` in hand) and the notched pass `:4434-4459` (gated by `NOTCH_WORK` on the plain ground's own work, never on the budget left).

Scenario: a building whose first pass ends within one re-lay of 2.0 M entries (the merchant's house builds 1.32 M; the inn without its office builds 0.87 M on its upper floor alone, per the `NARROW_WORK` comment) and has a straight flight both rooms meet at one end: the U-turn re-lay passes the budget, the whole core result is thrown away, and the lab's search lays the house -- silently, per F1.

Verified (`climb_budget.py`): on the test plan `STACKED` the first `_lay_kinds` finishes a chain at 27,393 entries; with `ARRANGE_WORK_BUDGET = 27,393 + 1,000`, `solve_arranged` raises `ArrangeBudget` from inside `_climb`'s re-lay (`marks == [(27393, True)]`, traceback through `_lay_kinds -> _carry -> ... -> _tick`). CONFIRMED mechanism; no field building measured hitting it (PLAUSIBLE in the field).

Fix: in the three optional passes, catch `ArrangeBudget` when a `best` chain exists and keep it, with a warning that the pass was cut short (the budget bounds work; it should not invalidate a found layout). Test: the `STACKED` spec with the budget patched to first-pass work + epsilon returns a layout (straight flight, the "cannot be climbed" note) instead of raising.

### F3 — An outside door and an inner doorway open from one cell on the core path; the "never two doorways from one cell" rule skips outside doors — WRONG-SCENE

Where: `world/layout_solver.py:1998-2025` builds `held` (cells a doorway opens from) and avoids it for inner doors when `apart`; the outside-door loop `:2068-2108` never consults it:
```python
for target, side, kind in sorted(items, key=lambda t: t[0] in things):
    ...
    else:
        pos = cells[len(cells) // 2]
```
The docstring (`:1966-1972`) states the rule without that exception: "A ROOM NEVER OPENS TWO DOORWAYS FROM ONE CELL where the wall has another."

Scenario (built, `doors.py`): a 2-pace corridor (`CORRIDOR_WIDTH`) with two rooms off its east side in order and a door onto a yard at its south end. Core layout: corridor `Rect(4,0,2,6)`; the doorway to `r1` at `(5,5)` and the yard door at `(5,5)` -- while `(4,5)`, the other cell of the south wall, is free. 4 of 6 variants of that plan clash on the core path (2 on the lab path, which never had the rule). Any 1-2-cell outside wall (corridors, closets, entries, washrooms -- `SMALL_PURPOSES`) puts `pos` on a corner cell that an inner doorway may already hold.

Verified: `doors.py` output `((0, 'corr', (5, 5)), ['r1', 'yard'])` and the door list. Not in any register (grep "two doorways", "one cell"). CONFIRMED.

Fix: in the outside-door loop, when `apart`, prefer `cells` not in `held[(lv, rid)]` (fall back to all), then `hold(...)` the chosen cell. Test: the corridor plan above; assert no room cell carries two doorways where its wall had a free cell.

### F4 — The lab's search (the core's fallback) lays the same plan differently in different processes: set-iteration order under hash randomisation — STALE-DOC (determinism)

Where:
- `world/layout_solver.py:814` (part storey placement in `_place_blocks`):
  ```python
  side_to = max(set(toward), key=toward.count)
  ```
  a tie between two asked walls is broken by the iteration order of a set of one-letter strings, which `PYTHONHASHSEED` randomises per process.
- `world/layout_solver.py:1235-1259` `_shaft_spots` collects `(kind, Rect)` in a set and sorts by `(x, y, w)` only; spots tying on those (a `spiral` 2x2 and a `ladder` 2x1 at one corner) keep set order, and `_search` starts from `options[len(options) // 2]` (`:1707`).

Scenario: the same building, laid by `lab_solve_for` after a server restart (or on a db-copy replay, or by the lab tool), stands its upper part-storey against the other wall. Measured (`part.py`, `det.py`, plan `BIG_GROUND` with two ladders asked from `n` and `s`): the level-1 outline is `(2,4,6,5)` under hash seeds 1, 2, 4, 6 and `(2,0,6,5)` under 3, 5; the full lab layout hashes `497d035581` vs `07d99a7a6d` across six seeds. `_shaft_spots` order measured varying (seed 2 starts on the spiral, seeds 1/3/4 on the ladder) though that plan's final layout converged. The core is stable (same hash on 3 plans x up to 6 seeds), and the four lab baselines re-solve identically across 3 seeds (`base_hash.py`), so the baselines are not exposed. Claims this falsifies: `layout_bridge.py:2226` "Each seed is deterministic, so a building solves the same way every time"; `AGENTS.md:525` "re-solves its baselines cell for cell" holds for the baselines but not as a property of the search. `tests/test_layout_solver.py:138-139` (`test_the_layout_is_the_same_every_time`) solves one plan twice in ONE process with the lab, so it cannot see this, and never runs the core.

Verified: CONFIRMED (snippets above; `PYTHONHASHSEED=1..8` on `max(set(['n','s']), key=...)` returns both answers).

Fix: `max(sorted(set(toward)), key=toward.count)` (or rank ties by `_SIDES`); sort spots by `(x, y, w, d, kind)`. Test: run `_prepare` of the tie plan in two subprocesses with different `PYTHONHASHSEED` and compare outlines (a subprocess test, like the existing hash-seed tests in `tests/test_charter_run.py`).

### F5 — `_place_fixtures` never backtracks: the docstring's search is greedy, its alternatives and budget unreachable — DEAD / STALE-DOC

Where: `world/layout_solver.py:2362` ("Fixtures by relation, backtracking.") and `:2503-2558`:
```python
for r in cands[:10]:
    ...
    if go(i + 1):
        return True
    ...
layout.unplaced.append({...})
return go(i + 1)
```
A level with no candidate records the fixture unplaced and continues, so `go` returns `False` only once `budget[0] < 0` -- after 3,000 calls, and a room makes exactly fixtures + 1. The first candidate is always kept; candidates 2-10 and the budget are dead.

Scenario: an early, larger fixture takes the cells that a later one needed where a second-ranked spot would have fitted both; the later one is reported unplaced instead of the search trying the alternative it was written to try. Verified (`backtrack.py`, `sys.setprofile` counting `go` frames): over the shrine baseline's 17 furnished rooms, calls == fixtures + 1 in every room, including the roost with 2 fixtures unplaced. CONFIRMED (no backtracking); the furniture actually lost to it is PLAUSIBLE -- §2.43's "more furniture left out than the old search (70 pieces over 14 shrine runs against 49)" may partly be this.

Fix: the owner's call, because either changes behaviour: make a level that finds no candidate return `False` (true backtracking under the existing budget; it will change the lab's baselines), or rewrite the docstring as a greedy placement and delete the dead loop. Test: a room where the greedy first placement blocks the second fixture and another spot fits both.

### F6 — `_support_hint` reads the farthest storey of a shaft below the ground, not the next — WRONG-SCENE (minor)

Where: `world/layout_arrange.py:4672-4675`:
```python
up = [v for v in sh.levels if v > lv] if lv >= 0 else [v for v in sh.levels if v < lv]
...
nxt = up[0]
```
`sh.levels` is sorted ascending (`layout_solver.py:586`), so for `lv < 0` `up[0]` is the deepest storey. For a stacked shaft `[-3, -2, -1]` first laid on storey -1, the hint reads the `-3` room's asked wall (the `-3/-2` flight) instead of the `-2` room's (the `-2/-1` flight) and prices the wrong side of the hall, steering which storey -1 the beam keeps. Above the ground the list's first element is the nearest, so only deep cellars are affected.

Verified: traced list order (`_shafts` sorts `levels`; the comprehension preserves it). CONFIRMED mechanism, PLAUSIBLE impact (needs a three-storey cellar shaft).

Fix: `nxt = max(up) if lv < 0 else min(up)`. Test: a plan with one shaft `-1 -> -2 -> -3` whose two flights ask different walls; assert the hint follows the `-2` room's wall.

### F7 — Dead code in both modules — DEAD

Verified by grep over the whole repo (`world agents tools tests extensions`), CONFIRMED each:
- `world/layout_solver.py:1851-1854` `_solid()` always returns `set()` ("Stairs are rooms of their own now"), yet six call sites still filter on it (`:1976`, `:2084`, `:2151`, `:2190`, `:2227`, `:2326`) -- every `avoid`/`solid` test is a no-op.
- `world/layout_solver.py:224-227` `Rect.flush` and `:229-230` `Rect.inset`: no caller (every `.flush(` hit in the repo is a file or compressor flush).
- `world/layout_solver.py:1833-1846` `solve_with(own_outlines=False)` and `Division.outlines = None` ("or None to keep `_place_blocks`' own", `:1472-1473`): the only caller, `solve_arranged` (`layout_arrange.py:5169`), always passes `own_outlines=True` and the only core always returns outlines.
- `world/layout_arrange.py:997-1004` `_Table.at()` has no caller; its cache field `_at` (`:986`) and the two resets `core._at = None` (`:2009`, `:2019`) are dead with it.
- `world/layout_arrange.py:1130`, `:1150` `_Storey.work` is incremented and never read; the comment says it is `_Building.work`, but `_Building.work` (`:3003-3007`) reads `self.meter.total` -- and that property is never read either (the one test that needs the count reads `self.meter.total` directly, `tests/test_the_core_never_lays_worse_than_the_lab.py:242`).

Fix: delete them (and for `_solid`, the filters). No test needed beyond the suite.

### F8 — `layout_solver`'s module docstring says nothing in the engine calls it — STALE-DOC

Where: `world/layout_solver.py:3-4`:
```
PROTOTYPE (branch layout-solver-test, 2026-10-03). Nothing in the turn pipeline
calls this module; `tools/layout_lab` drives it and renders what it produces.
```
Since 2026-10-10 the tier is on for every story: `world/layout_bridge.py:133-135` imports `solve`, `check`, `purpose_key`, `fixture_footprint`, `STAIRS` and more, and `world/layout_arrange.py:86-89` imports 24 names, the materializer seam `solve_with` among them. The module is now the core's fallback AND the materializer every engine layout goes through. The docstring's design (OUTLINE FIRST, `_place_blocks` sizing every storey) also describes only the lab path. CONFIRMED by grep. Fix: restate the module as "the lab's search (the core's fallback) and the shared materializer"; point to `layout_arrange` for the engine's division.

### F9 — The budget's stated time bound is measured 1.7x short; the meter does not count the work that dominates — STALE-DOC

Where: `world/layout_arrange.py:558-560`:
```
A table entry costs 30 to 50 us and, while its storey is laid, about 550 bytes: the budget is about 1.1 GB and 60 to 100 s of the core at the worst.
```
Measured (`bound_share.py`, same session): the shrine baseline 78,106 entries in 2.3 s (29 us/entry); the test plan `TOP_HEAVY` 313,935 entries in 22-26 s (70-83 us/entry), 74% of its entries in the bound tables (`ltable`). `_combine`'s pair reads -- the real cost of a bound table -- are not counted, so at the TOP_HEAVY rate 2.0 M entries is about 140-166 s before the fallback starts (then four lab seeds, about 45 s). Separately, padded and notched tables re-count their core's entries: `etable` ticks `core` (`:2060`) and then ticks `out`, which copies every core entry (`:2072-2073`, `:2093`; `_notched` the same at `:1807-1808`, `:1840`). The machine was shared with other auditors; the ratio between the two plans, measured minutes apart, is the evidence. CONFIRMED.

Fix: restate the measured range in the comment (and, if the owner wants the bound to mean time, count `_combine` reads as work); the double count is self-consistent with the calibrated constants, so note it rather than change it.

### F10 — Minor stale statements — STALE-DOC

- `world/layout_arrange.py:56-57` (module docstring, point 4): "the hall at most `LANDING_MAX` paces longer than its flight" -- since phase 2 a hall may take a landing past the cap at `LANDING_OVER_COST`, up to `LANDING_OVER_CEILING` times its least area (`:134-161`, `_hall_past`).
- `world/layout_arrange.py:61-65` (point 5) lists the give-way order without `way` and `end`, which `RELAX_ORDER` (`:643`) places first and between `side` and `landed`.
- `Design.md:573`: "`world.layout_solver` places every room, stair, doorway, window and fixture" -- since 2026-10-19 `world.layout_arrange` places rooms and stairs; the solver materializes doors, windows and fixtures (and rooms only on the fallback).
- `agents/director_layout.py:89-91` (`LAYOUT_TIER_PER_RUN`): "about 11 s of solve (the owner's preferred shrine: 11.1 s ...)" is the lab's figure; the core lays that shrine in 2.3 s (measured).

## Efficiency

Where the tier runs: not per beat. `lay_out_buildings` runs inside the rooms-in-view job thread (`director_rooms._predevelop_run`) and at story launch (`lay_out_opening_ground`), at most `LAYOUT_TIER_PER_RUN = 1` building per run, once per building until re-planned. A beat with nothing to lay pays only the plan read. Typical cost of one building, measured here: 3-4 model calls (brief, architect lore, sort, relate) plus the core (shrine 2.3 s, 78k entries; `TOP_HEAVY` 22-26 s, 314k entries; the merchant's house about 44-100 s per §2.43) plus `_unturned`'s re-finish (0.35 s) plus, on fallback, four lab seeds (11.2 s each on the shrine here, about 45 s).

E1 — The bound tables (`ltable`) dominate a bound-heavy building. `world/layout_arrange.py:1956-2022`. Profile of `test_a_top_heavy_house_grows_its_ground_and_says_so` (one test run, cProfile): `ltable` 39.8 of 46.7 s cumulative (85%); `_combine` 53,134 calls from `ltable` against 36 from `etable`, 15.8 s self; `dict.get` 24.3 M calls (8.2 s); `cuts()` 9.1 s cumulative from `ltable` alone (`:1979`, uncapped), most of it `_cross` (6.6 s) computing touch variants that `ltable` throws away (it reads only `(axis, A)`). Bound tables are also rebuilt per storey family (`make`, `:3468-3477`) though they read no pin, and every node pads `PAD_MAX` x 2 entries per entry (`:2011-2018`), which densifies every parent's `_combine`. Options, each to be measured against the 126-case gate: (a) give `ltable` the cached down-sets directly instead of `cuts()` (`_cross` skipped; the bound stays a lower bound, possibly looser) -- up to ~20% on this plan; (b) key bound tables per storey rather than per family; (c) the O(M^2) prefix-minimum the earth branch already uses (`:1996-2008`) in place of the pad loop. The shrine is etable-bound (bounds 7.6% of its entries), so the gain is building-dependent.

E2 — The lab's search recomputes pure functions of the spec ~10^5-10^6 times per seed. `world/layout_solver.py:627-643` `_joins` (scans every room's joins each call: 224k calls, 4.7 s = 20% of a profiled seed), `:436-444` `purpose_key` (1.04 M calls, 3.6 s = 16%), `:361-368` `fixture_footprint` (391k calls, 2.5 s = 11%, mostly `_score`'s longest-fixture generator `:1304`). All are constant for a solve: precompute per room on `_Prepared`. Together about 47% of the profiled seed; cProfile inflates call-heavy small functions, so the wall-time gain is less -- measure, but a third off each of the fallback's four seeds (and the lab tool's) is plausible. Cheap.

E3 — A cancelled layout job keeps solving. `core.jobs.cancel_from` cancels the rooms-in-view job on a reroll or restore, but `lay_out_buildings` checks `jobs.is_cancelled` only between buildings (`agents/director_layout.py:670`); the core (`_Storey._tick`, `layout_arrange.py:1146-1159`) and `lab_solve_for`'s seed loop (`layout_bridge.py:2248`) never do, so a cancelled job burns up to the budget plus four lab seeds of pure-Python CPU in a daemon thread of the server process, competing for the GIL with the beat that replaced it (the write itself is correctly skipped, `structure.write_planned_layout`). Fix: hand `_Meter` a cancel predicate checked in `_tick`, and check between seeds. Not registered (§2.43 registers only the opening's latency).

E4 — The grounds pass rebuilds the same sets per candidate rectangle (runs on every solve, core and lab, inside `_finish`). `world/layout_solver.py:3126-3128` `free()` calls `aprons(door)` -- a pass over every door -- for every rectangle tried by `_things_at_doors` and the feature placers; `:3327` scores a thing "by nothing" with `-min(... for t in taken | house)`, building the union set at every scanned position. Hoist `aprons()` per feature and the union per feature. Unmeasured; a site of ~40x40 positions x ~500 cells per thing.

E5 — `_LAST_DIVISION` is one slot for the whole process (`layout_arrange.py:5146-5169`). Layout jobs of two chats run in concurrent threads (`core/jobs.py:131`), so a second solve between `solve_for`'s core call and `_unturned`'s `face=False` call (`layout_bridge.py:2120`) evicts the entry and the building is arranged a second time (2.3 s shrine, up to about 100 s merchant). Correctness is safe (the key is the whole spec JSON). A small dict keyed by spec JSON would remove the repeat.

E6 — `_Table.seal` prunes keyed entries to the module `KEY_CAP` (12) (`layout_arrange.py:1018-1022`), not the storey's `key_cap`, which is `KEY_CAP_LARGE` (4) on a large or narrowed storey (`:1132`, `:1172`). `_combine` bounds its reads by the storey's cap but keeps entries inserted before the bound tightened, so keyed tables on exactly the expensive storeys hold up to 12 extents per shape where 4 were meant. Pass the cap to `seal`. Unmeasured.

E7 — Test-only: `tests/test_layout_solver.py:498-500` solves `huge` twice (`solve(huge).outlines` then `check(solve(huge))`), a third of that 11 s test.

## Already registered

- `docs/UNBUILT_WORLD.md` §2.43, "The arrangement-first core: what is left": *Two slow buildings* (farmhouse 29 s, merchant about 100 s; the plain ground's DP dominates; `lay_out` solves it twice) -- E1/E3 add the bound-table share and the cancellation gap, not the slowness itself.
- §2.43: *More furniture left out than the old search* (70 against 49 pieces). F5 is a possible contributing cause not named there.
- §2.43: *A manor of 35 rooms* is laid by neither path.
- §2.43: *The regression gate lives outside the repository* (the 126 cases). Relevant to E1's measurement and to F4 (no cross-process determinism test exists).
- §2.43: *Rules set in the rounds, the owner's to overrule* -- every price and budget is a named constant (so F9 proposes restating, not choosing, a number).
- §2.43, "The lab's look": `layout_solver._spine_h` names every leftover `spare:0:`. A consequence not written there: `_absorb` reads the storey from that id (`layout_solver.py:1172`), so a spine-made spare above the ground is read as storey 0 and escapes the upper-storey landing cap.
- §2.43: *Spare floor below the roof goes to a stair hall* (`_absorb` caps a landing only above the ground) -- lab path.
- §2.43: *The opening waits for the solve* (+4 to +23 s a building) and the grounds' *cost* bullet (at most `GROUND_DROP_ROUNDS + 1` rounds of `LAYOUT_SOLVE_SEEDS` solves).

## Structure notes

Module-level mutable state and its writers (question 1):
- `layout_arrange._PAST` (`:749`): written by `_hall_past` on a miss (`:775`), read only there; callers `Leaf._hall_cost` (`over` halls) and `_Building._fix_flight`. Never cleared. A pure memo of `(fw, fd, w, h, across)` and module constants, bounded by the domain (`M <= 48` on the only path that sets `over`, so under ~50k entries). Safe across stories and threads (dict ops are atomic; a race computes twice). Latent hazard: a test that monkeypatches `LANDING_MAX`, `LANDING_OVER_CEILING`, `STRAIGHT_RUN`, `SHORT_LANDING` or `HALL_MIN_ACROSS` reads stale entries left by an earlier test in the same worker; none does today.
- `layout_arrange._LAST_DIVISION` (`:5146`): one slot, written by `solve_arranged` whenever it arranges (`:5167`), read only by `solve_arranged(face=False)` (`:5158-5160`), never cleared. Keyed by the full spec JSON, so a stale or foreign entry can only miss, never mislay -- no corruption; see E5 for the cost of a miss.
- `layout_solver._ROUND_CELLS` (`:294`): pure memo of `room_grid` by `(w, d)`; safe.
- `_BIT`, `_SIDE_OF`, `_OPPBIT`, `RELAX_COST` and the solver's tables (`FIXTURE_SIZES`, `PURPOSE_AREA`, `STAIRS`, `USE_SPACE`, ...): never written anywhere (grep). No `global`/`nonlocal` rebind in either module.
- Per-solve state lives on `_Building` (`meter`, `_families`, `_strict`, `_narrow_try`, `side_override`, `warnings`) and is discarded with it; `_families` is reset per block and the first storey's families dropped after its outlines are taken. Family sharing (`make`, `:3468-3477`) was checked against every leaf attribute the shared tables read; the key covers them (`_kept_key` covers the one dimension `_kept` can bind).

Determinism (question 2): the core is deterministic across processes as far as read and measured (no `random`, no `hash()`, every set either sorted or of ints/int tuples whose hashes are not randomised; same layout under up to 6 hash seeds on 3 plans). The lab path is not (F4). `test_the_layout_is_the_same_every_time` covers only the lab, one plan, one process.

Budget and termination (question 3): every path is bounded -- the DP by memo plus `_Meter` (`ARRANGE_WORK_BUDGET` per building, `NARROW_WORK`/`NARROW_WORK_OPEN` per storey, mid-solve narrowing), give-way by `RELAX_LINEAR` + halving + give-back, `_climb` by `len(kinds)` rounds, the lab by fixed tries, furnishing by a budget it never reaches (F5), the grounds by the site. On expiry the core raises `ArrangeBudget`, the bridge falls back to four lab seeds, and the fallback is silent (F1); an expiry inside an optional pass discards a found layout (F2). `INF`, `PRUNE_MARGIN`, `LEAF_MARGIN` checked: no division by zero or `log` of a non-positive value is reachable.

Units (question 4): paces throughout (one cell = one pace); `area_m2` converted at `PACE_M = 0.75` (`_stated_area`). The pace length is stored four times (`layout_solver.PACE_M`, `site_plan.PACE_M`, `vistas._PACE_M`, `spatial_sound_field.PACE_M`), free to disagree. `LARGE_BUILDING = 24` (`layout_arrange.py:524`) restates `layout_bridge.LAYOUT_TIER_MAX_ROOMS = 24`. Corner cells: F3.

Stairs (question 5): the flight is ONE `Rect` fixed once, on the storey that lays the shaft first (`_fix_flight` -> `_State.flights`), and pinned on every other storey; each storey's landing is that storey's own hall minus the flight (the hall above may keep the hall below's landing through `keeps`/`KEPT_LANDING_COST`). No landing is stored. The foot/head of a straight flight is, however, decided twice: by the core (`_fix_flight`'s reach, `_ends_needed`, `_unclimbed` via `_reached`) and again by the materializer for enclosed flights (`layout_solver._stair_doorways`, by doorway paces; the one persisted as `well["foot"]`/`["head"]`), with a third copy of the reach rule in `tests/test_a_stair_is_climbed_and_its_landing_reached.py:_climbable`. They agree by construction on the plans measured; nothing checks it.

Duplicates between the two modules (question 6): `_place_blocks` (`layout_solver.py:674-841`) vs `_Building.place_blocks` (`layout_arrange.py:4808-4925`) -- same job, the core's version evolved (`_joined_rooms`, `_slide`, plan order, cavern sides), with the `crowds` closure, the `3`-pace apart gap and the default-side map `{"n": "e", "s": "e", "e": "n", "w": "n"}` copied verbatim (the map a third time in `_block_side`); `_flight_ends` exists twice with different signatures and returns (`layout_solver.py:1864` takes a dict, returns `(a, b)`; `layout_arrange.py:2795` takes a `Rect`, returns `{bit: cells}`); the home block when no entrance is named is the LARGEST OUTLINE in the lab (`:700`) but the block with MOST ROOMS in the core (`:3000-3001`); the cells a window needs are counted in `_window_landing` (`:3065-3097`, count parsed under try/except) and in `relations` (`:3209-3228`, bare `int()`) by two slightly different rules; `_sealed`/`_reached` import `_shared_wall` inside the function although the module already imports from `layout_solver` at the top.

Monoliths in miniature: `layout_solver._grounds` (568 lines), `_place_fixtures` (210), `_place_doors` (155), `_things_at_doors` (138); `_Storey._cross` (164); `_Building.storey` (156), `place_blocks` (118), `relations` (107).

Natural seams for the split program:
- `layout_arrange` constants (`:105-677`, 570 lines of named rules with their case histories) -> `layout_rules.py`.
- `_Storey` (1,563 lines): tables and meter (`_Table`, `_tick`, `_narrow`, `_read`, `_sig`); cuts and touch demands (`cuts`, `_downsets`, `_grown`, `_cross`, `_loose_pair`, `_min_shared`, `_flight_at_end`); wishes, pads and notches (`leaf_extra`, `_wins`, `_split`, `_win_extra`, `pad_sides`, `_ledge`, `_notch_sides`, `_notched`, `_lost_sides`); the relative DP (`leaf_table`, `_combine`, `ltable`, `etable`, `rel_at`, `rel_core_at`, `place_at`, `place`); dug storeys (`_earth_rel`, `_hall_rects`, `_earth_abs`); the pinned DP (`holds_pins`, `_check`, `GE`, `GE_core`, `G`, `place_abs`).
- `_Building` (2,166 lines): storey problems (`relations`, `_corridor_runs`, `storey`, `make`, `_kept_key`); giving way (`_relaxations`, `_door_keys`, `_conflicted`, `_note`, `_relaxed`, `_give_way`, `_holds`, `_words`); laying storeys (`_M_free`, `lay_free`, `lay_region`, `_lay_next`, `_support_hint`, `_lay_one`, `_sheer_box`); stairs (`_fix_flight`, `_ends_needed`, `_climb`, `_unclimbed`, `_end_combos`, `_settle`); the block beam (`lay_block`, `_lay_kinds`, `_carry`, `_grounds`, `_chains`, `_weigh`, `_crushed`, `_crowded`, `_missed`, `_notch_wanted`); block placement (`place_blocks`, `_joined_rooms`, `_slide`, `_cave_side`).
- `layout_solver` (3,479 lines): the lab search (`:646-1734`), the shared materializer (`:1736-2570`), the grounds (`:2572-3437`), `check`.

## Docs checked

- `AGENTS.md:525` -- the core is called first by `solve_for`, its fallback is `lab_solve_for` (four seeds), budgets `ARRANGE_WORK_BUDGET`/`NARROW_WORK`, seam `solve_with`: HOLDS. "`layout_solver.solve` ... re-solves its baselines cell for cell": HOLDS for the four baselines in one process and across 3 hash seeds (measured); not a property of the search (F4).
- `Design.md:573` -- "`world.layout_solver` places every room, stair, doorway, window and fixture": STALE since the core (F10). "Anything unsolved writes nothing (`solve_for`: the arrangement core once, and where it fails the old search on up to `LAYOUT_SOLVE_SEEDS` seeds ...)": HOLDS.
- `docs/design/DESIGN_LAYOUT_TIER.md:1052` and `:1077-1084` -- "the old four-seed search lays it instead, with a warning on the layout": HOLDS literally; the warning reaches nothing (F1). "counted rather than clocked, so the fallback is deterministic": HOLDS. "with the same house every time": HOLDS for the core (measured).
- `layout_arrange.py` docstring: "one deterministic solve" HOLDS; "saying so" (`:72`) does not (F1); point 4 (F10); "Units are paces" HOLDS.
- `layout_arrange.py:554-566` `ARRANGE_WORK_BUDGET` time bound: off by about 1.7x on a measured plan (F9).
- `layout_solver.py:3-4` "Nothing in the turn pipeline calls this module": STALE (F8).
- `layout_solver.py:2362` "backtracking": FALSE (F5).
- `layout_solver.py:1966-1972` "A ROOM NEVER OPENS TWO DOORWAYS FROM ONE CELL where the wall has another": FALSE for outside doors (F3).
- `layout_bridge.py:2226` "Each seed is deterministic, so a building solves the same way every time": FALSE across processes (F4).
- `layout_arrange.py:1130` comment tying `_Storey.work` to `_Building.work`: misleading; both unread (F7).
- `agents/director_layout.py:89-91` "about 11 s of solve" for the shrine: the lab's figure; the core is 2.3 s (F10).
- `solve_arranged` docstring "the seed is read by nothing here": HOLDS (`p.rng` is unused downstream of `_prepare` on the core path).
