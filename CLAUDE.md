# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Start here

This repo already maintains detailed docs for coding agents. Read them before making non-trivial changes:

1. [`AGENTS.md`](AGENTS.md) — edit routing table (which files to touch for which change), core invariants, source-of-truth order, and safe change workflow. **Read this first for any behavioral change.**
2. [`docs/PIPELINE.md`](docs/PIPELINE.md) — exact opening-turn and normal-turn execution flow, stage-by-stage.
3. [`docs/CODE_MAP.md`](docs/CODE_MAP.md) — generated index of modules, functions, routes, DB tables, and frontend sections. Regenerate with `make map`; do not hand-edit.
4. [`docs/DATABASE.md`](docs/DATABASE.md) — schema, write helpers (`q`/`qi`/`qtx`/`transaction`/`wget`/`wset`), and the schema-change checklist.
5. [`docs/TESTING.md`](docs/TESTING.md) — fast/full/browser tiers, dependency constraints, and CI policy.
6. [`Design.md`](Design.md) — product philosophy, architecture, a verified conformance table (built / partial / not built), and structural debt. Its status rows were checked against source; keep them that way by editing the row in the same commit as the behaviour.
7. [`docs/UNBUILT.md`](docs/UNBUILT.md) — the single register of unfinished work: known defects, the roadmap, deferred audit findings, and every design-note residual. No other document keeps its own status list. Delete an entry in the commit that lands it; add the corresponding row to `Design.md`.
8. [`agents/README.md`](agents/README.md) — how to add a new pipeline stage.

Do not duplicate content from these files in explanations; point to them instead.

## Commands

```bash
make run        # start the local server (uvicorn app:app --reload, port 8008)
make test-fast  # broad Python suite without database-backed slow tests
make test-full  # every Python regression test
make test       # alias for test-full
make test-browser # optional real Chromium behavior tests
make map        # regenerate docs/CODE_MAP.md
make structure  # run tools/project_check.py (duplicate-symbol, patch-debris, empty-test, stale-map checks)
make compile    # python -m compileall on all source
make check-fast # compile + structure/map freshness + test-fast
make check      # compile + map + structure + test-full — run this before considering a change done
```

Single test:

```bash
python -m pytest tests/test_spatial.py::test_name -q
```

Run commands from the repository root — the app uses top-level imports (`from db import q`), so it is not an installed package. Python 3.11+.

The default SQLite database is `engine.db`; override with `ENGINE_DB` before importing `db.py`. Database-backed tests request the `temp_db` fixture (`tests/conftest.py`), which calls `db.configure()` on a temp file and cleans up WAL/SHM afterward; those tests belong to the full tier. Fast-tier tests must stay database-independent and must never rely on another test initializing `engine.db`.

## Architecture

Sonder Engine is a local multi-agent interactive-fiction system. Its defining goal: produce coherent interactive fiction without granting fictional minds (character agents) access to information they did not legitimately perceive, learn, remember, or infer. Objective truth, perception, memory, inference, belief, and narration are treated as distinct information layers that must not collapse into one context.

A turn runs through a `PipelineContext` (`pipeline_context.py`) and is executed by `agents/runtime.py`. Every stage's output is saved as a `steps`/`variants` row pair (one active variant per step), which is what makes reroll, rerun-from-stage, and manual editing possible.

**Opening turn** (`turn.idx == 0`): `mapping_stage → director_establish → perception_establish → narrator → commit`

**Normal turn** (plan built dynamically from `director_interpret.flow`):
```
director_interpret → mapping_stage|mapping_quick → perception_act
    → [reaction_loop if contested physical reactions] → [interaction_loop | parallel character:<id> steps]
    → director_resolve → background_react → perception_outcome → narrator → commit
```

Key ownership boundaries (see `AGENTS.md` for the full table):
- The **Director** (`agents/director.py`) owns objective causality — interprets player input and resolves outcomes — but not character psychology or narration, and must not silently replace the player's declared speech/action.
- **Perception** (`agents/perception.py`) is a stateless filter deciding what each observer legitimately receives; its structured observations are re-derived from the final scrubbed prose view, not trusted from model output, so the second representation cannot expand the information budget.
- **Character agents** (`agents/character.py`, `agents/loops.py`) declare behavior from private perception/memory/relationships only; they never decide their own success. `psychology_runtime.py` deterministically persists bounded stress, current-event pain/pleasure, beliefs, and learned associations from those permitted inputs.
- **`agents/background.py`** gives at most one named, unregistered background presence a single stateless reaction per beat — no persistent memory or psychology (that requires promotion to a real character). Deterministically gated by `commit.py`'s `pick_background_reactor`, which returns `None` (no LLM call) for the large majority of turns.
- The **Narrator** (`agents/narration.py`) renders only the player-facing slice and cannot originate new player conduct or reveal unperceived facts.
- **`commit.py`** is the sole persistence boundary — model output is provisional until deterministic commit code validates it. Slow lore/memory preparation happens before the write lock, then all primary turn mutations commit inside one outer transaction. Any domain failure rolls the entire turn back; only reconstructible autobiographical-summary consolidation runs afterward.

`agents/__init__.py` is a compatibility facade; role modules (`director.py`, `perception.py`, `character.py`, etc.) may import `agents/common.py` but never each other, and `runtime.py` is the only module aware of every built-in stage.

Physical-world authority (consolidated in movement/space Phase 3a): the frame-scoped `world.scene` JSON blob is the single runtime source of truth for live rooms/positions/entity state; `room_registry` is the single cross-frame ledger of room identity/retirement; the normalized `world_entities` table is a derived projection of the scene commit. `world_placements` is decommissioned; `fiction_worlds`, `fiction_locations`, and `transit_edges` are deprecated import-compatibility tables. Every scene writer must keep the registry projection in sync — check both the commit path and restore path before adding one (see `docs/DATABASE.md`).

Supporting service seams are explicit: `auth_routes.py` owns typed host-auth routes and cookie transport; `chat_archive.py` owns portable chat import/export; `pipeline_trace.py` owns privacy-conscious persisted-history export/replay; `spatial_orientation.py` owns bearing math and is re-exported through `spatial.py`.

Frontend (`static/js/`) uses browser globals, not ES modules. `theme-init.js` loads in the document head; the remaining order is `utils.js → components.js → editors.js → lorebooks.js → backdrops.js → chat.js → settings.js → themes.js → app.js`. Never rename a shared JS function without grepping every file.

## Working in this repo

- Reproduce a bug with a focused test before fixing; fix the earliest stage where data first becomes wrong rather than compensating downstream (e.g., in the Narrator).
- New persistent fields need: schema/migration in `db.py`, read/commit code, portable archive handling in `chat_archive.py`, checkpoint snapshot+restore, branch/clone ID remapping in `app.py` if applicable, and a regression test (full checklist in `docs/DATABASE.md`).
- Attached characters may have a per-story authored card in
  `chat_chars.sheet`; `scene.active_cast` resolves it over the reusable
  `characters.sheet`. Keep that configuration separate from `chat_chars.state`,
  preserve it in archives/branches, and never permit a card edit to rekey the
  in-story identity name or uid.
- Character and persona cards keep three physical domains distinct:
  `embodiment.visible.summary` is stable body appearance,
  `initial_outfit` is authored starting clothing, and `scene.attire` is the
  mutable story ledger. `scene.seed_initial_attire` seeds a non-empty outfit
  once at scene creation or first attachment/promotion; no card read or edit
  may overwrite clothing already changed in the story.
- Avoid broad rewrites of `agents/runtime.py`, `app.py`, or `memory.py` without dedicated tests — these are orchestration seams affecting reruns, variants, streaming, and commits.
- Psychology changes must preserve the information firewall: a character may
  receive its own interoception/body state and its final scrubbed observations,
  never another character's vitals or raw Director event. Run the adversarial
  perception and self-knowledge tests when adding any new cognition field.
- **Author psychology with great care, and fill every field — an empty one
  fails silently.** These parameters do not error, do not warn at runtime, and
  do not show up in any test; they show up as a character who behaves wrongly
  fifty beats later, by which time the cause looks like a model problem.
  Measured cases, all from the maze arms
  ([`docs/MAZE_ARMS.md`](docs/MAZE_ARMS.md),
  [`docs/DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](docs/DESIGN_PSYCHOLOGY_AS_PRESSURE.md)):
  - **`psychology.drive` empty is the worst of them.** A sheet with rich
    traits, values and goals but `{"essence": "", "expression": "", "taboo":
    ""}` reads as complete and is not. Every motivation then lives in
    `initial_state.goals`, and goals are built to be completable and
    abandonable — so when they decay the character simply stops wanting
    things. A courier walked sixteen optimal rooms to his destination and
    turned away, because nothing underneath the spent goals wanted it. A drive
    survives goal decay; author one that cannot be satisfied, or it becomes a
    goal wearing the word.
  - **It fails invisibly because `serves: "drive"` stays valid against an
    empty drive.** The character emitted drive-serving wants for 150 beats
    against three empty strings, and nothing anywhere objected.
    `importers.character_import_warnings` catches this, but only on the import
    path — a card built or edited any other way gets no warning.
  - **Phrase `values` as trade-offs that name what yields** ("speed over
    thoroughness"), not as a flat list of virtues or prohibitions. A flat list
    has no ranking, so it cannot be traded against anything and operates as a
    constraint set. Bare prohibitions invert: `"never breaking stride"` was
    read by its own character as an argument *against* running.
  - **Authoring is not retraction.** A sheet edit does not remove a
    disposition the character has already lived — the phrase above survived in
    69 of his 222 memories after it was deleted from the sheet, and he kept
    writing more. Fix a sheet before a long run, not during one.
  - Treat sheet-authored values as *unproven until observed in conduct*. Two
    separate correct sheet edits have so far failed to change behaviour.
- Run `make check` before considering a change complete; it will catch a stale `docs/CODE_MAP.md`, duplicate top-level symbols, and leftover patch-debris markers as hard failures.
- Never commit `engine.db*`, `*.sqlite*`, `backdrops/`, `__pycache__/`, Python bytecode, or content-bearing `*.trace.json` diagnostics.
