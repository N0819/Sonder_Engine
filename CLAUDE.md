# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Start here

This repo already maintains detailed docs for coding agents. Read them before making non-trivial changes:

1. [`AGENTS.md`](AGENTS.md) — edit routing table (which files to touch for which change), core invariants, source-of-truth order, and safe change workflow. **Read this first for any behavioral change.**
2. [`docs/guides/PIPELINE.md`](docs/guides/PIPELINE.md) — exact opening-turn and normal-turn execution flow, stage-by-stage.
3. [`docs/CODE_MAP.md`](docs/CODE_MAP.md) — generated index of modules, functions, routes, DB tables, and frontend sections. Regenerate with `make map`; do not hand-edit.
4. [`docs/guides/DATABASE.md`](docs/guides/DATABASE.md) — schema, write helpers (`q`/`qi`/`qtx`/`transaction`/`wget`/`wset`), and the schema-change checklist.
5. [`docs/guides/TESTING.md`](docs/guides/TESTING.md) — fast/full/browser tiers, dependency constraints, and CI policy.
6. [`Design.md`](Design.md) — product philosophy, architecture, a verified conformance table (built / partial / not built), and structural debt. Its status rows were checked against source; keep them that way by editing the row in the same commit as the behaviour.
7. [`docs/UNBUILT.md`](docs/UNBUILT.md) — the register of unfinished work: known defects, the roadmap, deferred audit findings, and every design-note residual. It is *meant* to be the only status list and is not: `Design.md`'s conformance table, each design note's `Status:` header, `docs/guides/FEATURES.md`'s `(partial)` markers and `docs/design/OFFSCREEN_WORLD_COMPLETION.md`'s per-item tags are four more. When they disagree, fix `UNBUILT.md` first. Delete an entry in the commit that lands it; add the corresponding row to `Design.md`.
8. [`docs/README.md`](docs/README.md) — the documentation index. `docs/guides/` is authority, `docs/design/` is argument, `docs/experiments/` is evidence, `docs/archive/` is superseded.
9. [`agents/README.md`](agents/README.md) — how to add a new pipeline stage.

Do not duplicate content from these files in explanations; point to them instead.

## Commands

```bash
make run        # start the local server (uvicorn web.app:app --reload, port 8008)
make serve      # the same server with no file watcher — for playing, not developing
make test-full  # every Python regression test, in parallel (run this freely; pytest reports the count)
make test       # alias for test-full
make test JOBS=0  # the same, serially -- reach for it when a failure's output is confusing
make test-serial # always serial, same thing under its own name
make test-lf    # last-failed first, then the rest — the fix-verify loop
make test-fast  # NOT a tier to check your own work with; deselects every
                #   database-backed test file, including the persistence and
                #   firewall suites (see docs/guides/TESTING.md)
make test-browser # optional real Chromium behavior tests
make map        # regenerate docs/CODE_MAP.md
make structure  # run tools/project_check.py (duplicate-symbol, patch-debris, empty-test,
                #   prompt/schema-op drift, prompt/example time-channel vocabulary,
                #   specialist + prose-author chunk ownership,
                #   supported-Python agreement across pyproject/launchers/CI, machine
                #   paths in runnable files, docs naming files or imports that do not
                #   resolve, uncleared turn-scoped contextvars, new package import
                #   cycles, stale map)
make compile    # compileall over ENGINE_SOURCE_ROOTS (tools/project_check.py --source-roots)
make check-fast # compile + structure/map freshness + full suite
make check      # compile + map + structure + full suite — run this before considering a change done
```

**`make check` runs whatever `python` resolves to, which is very unlikely to be
the stack that ships.** Measured 2026-08-18: the system interpreter carried
Pydantic 1.10.14 / NumPy 1.26.4 while `.venv` — what both launchers build, what
every player runs, and what `constraints.txt` pins — carried Pydantic 2.11.7 /
NumPy 2.2.6. Two defects were live in that gap at once and the suite was green
through both, including one that silently discarded every list-valued Director
channel on the shipped major. Before believing a green run means the engine
works:

```bash
python3.12 -m venv /tmp/sonder-ci && \
  /tmp/sonder-ci/bin/pip install -c constraints.txt -r requirements-dev.txt && \
  /tmp/sonder-ci/bin/python -m pytest -q
```

CI does this on every push and CI is the authority; the local gate is a fast
approximation of it, and the approximation is exactly as wide as the difference
between two dependency resolutions. Details and the two structural guards that
now hold the class: [`docs/guides/TESTING.md`](docs/guides/TESTING.md).

Single test:

```bash
python -m pytest tests/test_spatial.py::test_name -q
```

Run commands from the repository root — the app uses absolute package imports (`from core.db import q`) rooted there, so it is still not an installed package. Engine modules live in eight subsystem packages (`core llm world mind story dressing persist web`) plus `agents/`; the grouping and its limits are in [`docs/design/DESIGN_MODULE_LAYOUT.md`](docs/design/DESIGN_MODULE_LAYOUT.md). Python 3.11-3.13 (the pinned `pydantic-core` has no wheel above 3.13; both launchers enforce the range).

The default SQLite database is `engine.db`; override with `ENGINE_DB` before importing `core/db.py`. Database-backed tests request the `temp_db` fixture (`tests/conftest.py`), which calls `db.configure()` on a temp file and cleans up WAL/SHM afterward; those tests belong to the full tier. The old rule here — that a fast-tier test must stay database-independent and must never rely on another test initializing `engine.db` — describes a hazard `conftest.py` removed at the root: `_redirect_default_database()` runs at conftest IMPORT, before any test module is imported, pointing `db.DB` at a scratch file and calling `db.init()` on it. So no test in either tier can reach the developer's `engine.db`, and none has to arrange its own initialization. What survives is the part that was always about the test rather than the database: prefer a pure constant or an explicit stub to a runtime settings/prompt lookup when settings behaviour is not what the test covers, so a test says what it depends on.

## Architecture

Sonder Engine is a local multi-agent interactive-fiction system. Its defining goal: produce coherent interactive fiction without granting fictional minds (character agents) access to information they did not legitimately perceive, learn, remember, or infer. Objective truth, perception, memory, inference, belief, and narration are treated as distinct information layers that must not collapse into one context.

**The firewall restricts the FLOW of knowledge, not knowledge itself.** A mind may know anything it has a channel to; what it may not do is acquire a fact that reached it through no channel. It is a GAP — two people do not share a head — rather than a rule bolted on top, which is why nearly every guard SUBTRACTS. Three consequences, each previously got wrong: **inference is the product, not the risk** (never harden a guard by making minds conclude less); **a leak is an engine failure, never a model's** (the deterministic floor must not depend on a model cooperating, and a warning means the system WORKED — nothing crossed); and **firewall integrity is an invariant, not a model-selection criterion**. The gap is kept because it is generative: deception, dramatic irony and a mind acting on a false belief all require the distance to be real. Full statement in `AGENTS.md` § Information boundaries and `Design.md` § What the firewall is.

A turn runs through a `PipelineContext` (`core/pipeline_context.py`) and is executed by `agents/runtime.py`. Every stage's output is saved as a `steps`/`variants` row pair (one active variant per step), which is what makes reroll, rerun-from-stage, and manual editing possible.

**Opening turn** (`turn.idx == 0`): `mapping_stage → director_establish → perception_establish → narrator → commit`

**Normal turn** (`agents/runtime.py`'s `build_plan`, built dynamically from `director_interpret.flow` plus the chat's `autonomy` and the awareness gate):
```
director_interpret → mapping_stage|mapping_quick → perception_act
    → [reaction_loop if contested physical reactions] → [interaction_loop | parallel character:<id> steps]
    → director_resolve → background_react → perception_outcome → narrator
    → [narrator_extra if the chat has extra players] → commit
```
A plan step is one `steps`/`variants` row; the Director's six specialist calls are sub-calls *inside* `director_interpret`/`director_resolve`, not steps of their own.

Key ownership boundaries (see `AGENTS.md` for the full table):
- The **Director** (`agents/director.py`) owns objective causality — interprets player input and resolves outcomes — but not character psychology or narration, and must not silently replace the player's declared speech/action. It is no longer one mind: each Director stage fans out to a prose author plus six scoped specialists (`SPECIALISTS` in `agents/director_scopes.py` — `body`, `social`, `contact`, `objects`, `spatial`, `offscreen`), each owning a subset of `state_diff` channels, and the deterministic orchestrator keeps every cross-channel judgment on the MERGED diff. The monolith is GONE: there is no `DEFAULT_PROMPTS["director_resolve"]`. `director_fanout_mode` chooses only CONCURRENCY (parallel default), never a different set of hands. Full contract in `AGENTS.md` § Director orchestration and design note 19.
- **Perception** (`agents/perception.py`) is **deterministic** — there is no `perception` model role in `providers.ROLES` and the module imports no model seam at all. It filters what each observer legitimately receives, and `agents/composer.py` composes every view from a typed IR; the structured observations are re-derived from the rendered view (`composer.observations_from_render`), so the second representation cannot expand the information budget.
- **Character agents** (`agents/character.py`, `agents/loops.py`) declare behavior from private perception/memory/relationships only; they never decide their own success. `mind/psychology_runtime.py` deterministically persists bounded stress, current-event pain/pleasure, beliefs, and learned associations from those permitted inputs.
- **`agents/background.py`** gives named, unregistered background presences a stateless reaction per beat — no persistent memory or psychology (that requires promotion to a real character). Deterministically gated by `persist/commit_background.py`'s `pick_background_reactors`, which returns `[]` (no LLM call) for the large majority of turns; the cap is the chat's `background_config.max_reactors` (default 1, hard ceiling 3), and `pick_background_reactor` is only a single-winner wrapper. Above `scene_life: ambient`/`full` the stage instead runs the scene-manager path (`scene_life`, `docs/design/BACKGROUND_LIFE_DESIGN.md`), which returns the same shape.
- The **Narrator** (`agents/narration.py`) renders only the player-facing slice and cannot originate new player conduct or reveal unperceived facts.
- **`persist/commit.py`** is the sole persistence boundary — model output is provisional until deterministic commit code validates it. Slow lore/memory preparation happens before the write lock, then all primary turn mutations commit inside one outer transaction. Any domain failure rolls the entire turn back; reconstructible autobiographical-summary consolidation is scheduled afterward as an out-of-band job (`schedule_memory_consolidation` → `core/jobs.py`), never inside the turn's wall clock. Since the 2026-08 split the domain code lives in thirteen `commit_*` modules (`commit_common`, `commit_place_graph`, `commit_destruction`, `commit_room_registry`, `commit_attire`, `commit_entities`, `commit_ledgers`, `commit_mapping`, `commit_background`, `commit_scene_state`, `commit_mechanics`, `commit_memory`, `commit_memory_write`); `persist/commit.py` keeps the per-turn lock, the thin tail domains, `commit_all`/`_commit_all_locked`, and a facade that re-exports every moved name — private names included — so `from persist.commit import X` stays the universal import path. The package root is part of it: there is no top-level `commit` module and never was one after the move, so the bare spelling raises `ModuleNotFoundError`. **A test that monkeypatches must patch the module that DEFINES the function it wants intercepted**, not the facade: a moved function resolves names in its own module's globals, and a patch on `commit.<name>` whose reader moved is silently inert (see `docs/experiments/AUDIT_COMMIT.md`).

`agents/__init__.py` is a compatibility facade. The enforced direction is one-way: role modules import `agents/common.py`, and `common.py` imports no role module. Role modules importing *each other* is discouraged but real and untested — `loops.py → character.py` and `background.py → perception.py` both do it — so do not assume that graph is clean. `runtime.py` owns the plan and the `STEP_HANDLERS` registry, but it is not the only place a stage is named: `runtime.STEP_LABELS` (the reader-facing phase name, harvested into the language packs), `schemas.SCHEMA_MAP` and `core/pipeline_context.py`'s fields enumerate them too — four registries, not three. Adding a stage is a checklist, in `agents/README.md`.

Physical-world authority (consolidated in movement/space Phase 3a): the frame-scoped `world.scene` JSON blob is the single runtime source of truth for live rooms/positions/entity state; `room_registry` is the single cross-frame ledger of room identity/retirement; the normalized `world_entities` table is a derived projection of the scene commit. `world_placements` is decommissioned; `fiction_worlds` and `fiction_locations` are deprecated import-compatibility tables, and `transit_edges` is not — it is in no archive, no checkpoint and no restore path, so an old export carrying rows loses them silently. Every scene writer must keep the registry projection in sync — check both the commit path and restore path before adding one (see `docs/guides/DATABASE.md`).

Supporting service seams are explicit: `web/auth_routes.py` owns typed host-auth routes and cookie transport; `persist/chat_archive.py` owns portable chat import/export; `persist/pipeline_trace.py` owns privacy-conscious persisted-history export/replay; `world/spatial_orientation.py` owns bearing math. It is one of the fourteen siblings behind the `world/spatial.py` FACADE, not a seam you import directly — `tools/project_check.py` enforces that for `world.spatial`, `agents.director` and `persist.commit` alike: a caller imports the facade, and only a test that PATCHES or introspects a sibling may name it.

Frontend (`static/js/`) uses browser globals, not ES modules. `theme-init.js` loads in the document head; the remaining order is `utils.js → components.js → editors.js → lorebooks.js → backdrops.js → ambience.js → weather-fx.js → chime.js → chat.js → settings.js → themes.js → app.js` (`static/index.html`). Never rename a shared JS function without grepping every file.

## Working in this repo

- Reproduce a bug with a focused test before fixing; fix the earliest stage where data first becomes wrong rather than compensating downstream (e.g., in the Narrator).
- **Investigating a turn means reading EVERY stage's output for that turn, not the stage the symptom appeared in.** A defect surfaces where it is RENDERED, which is almost never where it ORIGINATED, so the guilty-looking stage is the one least likely to be guilty. Pull the active variant of every step — `director_interpret`, `mapping_*`, `perception_act`, `interaction_loop`, `director_resolve`, `background_react`, `perception_outcome`, `narrator`, `commit` — plus the committed `state_diff`, the scene before and after, and the relevant `world` rows, and read them AGAINST each other before forming a hypothesis. The Director's six specialists have no steps of their own, so their work is only visible as their channels inside the merged `state_diff` (`attire`/`poses` for `body`, `positions`/`rooms` for `spatial`, and so on) — read the channel when you suspect the specialist. Measured, all in chats 74-76: a hotel employee who was Hinami's shed `utility_sash` (origin `background_react`, symptom in narrator prose); an attire ledger holding three contradictory `bare at the` notes (origin the body specialist's `state_diff.attire`, symptom in the ledger panel); a door narrated open that `state_diff.rooms` had recorded `closed_door` (origin narrator, symptom in prose); and a player's declared step into a lift that never committed, leaving two characters conversing from different rooms for a whole beat (origin `state_diff.positions`, symptom in dialogue). Three of those four were first misattributed by reading only the stage the symptom was in.
- New persistent fields need: schema/migration in `core/db.py`, read/commit code, portable archive handling in `persist/chat_archive.py`, checkpoint snapshot+restore, branch/clone ID remapping in `web/app.py` if applicable, and a regression test (full checklist in `docs/guides/DATABASE.md`).
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
- Avoid broad rewrites of `agents/runtime.py` or `web/app.py` without dedicated tests — these are orchestration seams affecting reruns, variants, streaming, and commits. `mind/memory.py` was one until 2026-08-19; it is now a FACADE over twelve `mind/memory_*` siblings (`docs/design/SPLIT_MEMORY.md`), holding no code of its own. The same monkeypatch rule as `persist/commit.py` applies to it: patch the module that DEFINES the reader, never the facade — `tools/project_check.py` enforces it, and found seven inert patches that passed on registration.
- Psychology changes must preserve the information firewall: a character may
  receive its own interoception/body state and its final scrubbed observations,
  never another character's vitals or raw Director event. Run the adversarial
  perception and self-knowledge tests when adding any new cognition field.
- **Author psychology with great care, and fill every field — an empty one
  fails silently.** These parameters do not error, do not warn at runtime, and
  do not show up in any test; they show up as a character who behaves wrongly
  fifty beats later, by which time the cause looks like a model problem.
  Measured cases, all from the maze arms
  ([`docs/experiments/MAZE_ARMS.md`](docs/experiments/MAZE_ARMS.md),
  [`docs/design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](docs/design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md)):
  - **`psychology.drive` empty is the worst of them.** A sheet with rich
    traits, values and goals but `{"essence": "", "expression": "", "taboo":
    ""}` reads as complete and is not. Every motivation then lives in
    `initial_state.goals`, and goals are built to be completable and
    abandonable — so when they decay the character simply stops wanting
    things. A courier walked sixteen optimal rooms to his destination and
    turned away, because nothing underneath the spent goals wanted it. A drive
    survives goal decay; author one that cannot be satisfied, or it becomes a
    goal wearing the word.
  - **The tier that answers this is `projects`, and it is NOT yours to
    author** (`docs/design/DESIGN_LONG_TERM_GOALS.md`, built:
    `affect.apply_project_ops`, `tests/test_projects.py`). A drive is eternal
    and PLACELESS — it cannot name a room, so it cannot be walked to. An
    intention names a room and is built to be completable, abandonable and
    swept when dormant. A project is the tier between: durable but not
    eternal, able to name a place, and immune to the three ways the courier's
    aims died — satisfied by one instance, decayed by a barren stretch,
    abandoned along with the tactic that served it. It BIASES appraisal
    rather than competing in the beat auction, which is how the shrine kept
    losing (intention weight 0.8 against drive-serving wants at 1.0, nine
    beats running). Capped at two, because scarcity is what makes "what is
    this person about right now" have an answer at all.
    **Projects FORM DYNAMICALLY.** The character adopts one mid-play through
    `project_ops`, under an adoption deliberation that refuses a task wearing
    the word and a probation that lapses if nothing serves it. That is the
    design, not a gap in it: a life's work a character arrives at is worth
    more than one assigned to them, and giving one up must be a legible act
    with a stated reason. `psychology.projects` on a card is a seeding
    tolerance, NOT the authoring surface — when writing a sheet, put the work
    into the drive and let the project be earned. Provenance, because it is
    the argument for the tier: projects were built during the maze arms to
    get NPCs to actually solve a maze, and to carry the ordinary long
    intentions a life has — take the injured one to a doctor, go home, go to
    the bar — and they are **what made NPCs pass the maze without any
    alteration to their drives**. (Owner's measurement from the arms;
    `docs/experiments/MAZE_ARMS.md` records A15's boundary-review result but
    not this one, so it is not re-derivable from that table.)
  - **It fails invisibly because `serves: "drive"` stays valid against an
    empty drive.** The character emitted drive-serving wants for 150 beats
    against three empty strings, and nothing anywhere objected.
    `character_card_warnings` catches this. It ran on the import path alone
    until 2026-08-18; it now runs on all ten surfaces that hand back a card
    — blank-card creation, AI generation, hand edit, the per-story card
    override, promotion confirm, psychology fill, appearance fill, interior
    fill, import and the greeting launch — because nothing about the answer
    depends on where the sheet came from. `importers.character_import_warnings` is an alias
    kept for the import path's own readers.
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
- **Fix the CLASS, not the instance. A live case is evidence, never the
  specification.** Nearly every defect here is found in one chat, and the
  temptation is to write the fix that chat needs — a rule shaped around fox
  ears, a guard that names one room, a prompt clause telling the model what
  *this* character's disguise means. That fix is invisible the moment the
  story changes, and it lies in the worst way: the test passes and the
  behaviour is still wrong for everyone else. State the rule in the
  vocabulary the ENGINE has — a disguise conceals features or it conceals
  identity, an edge named as an opening is not a wall, a line cannot be
  concealed from its own addressee — and let the live case be the thing that
  proves the rule was missing.
  - **Prompt text especially.** A prompt is read by every story, so an
    example drawn from one of them narrows what the model thinks the field
    is for. Name the distinction, never the instance: "covers what a body is
    recognised by — face, build, bearing, voice" holds for a mask, a
    uniform, an illusion and a glamour alike; "hides fox ears" holds for one
    character in one chat.
  - **Comments and commit messages are the exception, and should stay
    specific.** Citing chat 74 turn 2532, a measured 4-of-13, or the exact
    string that broke is how the next reader knows the rule was earned
    rather than guessed. Evidence is particular; rules are general; do not
    let the particular leak from the first into the second.
- Run `make check` before considering a change complete; it will catch a stale `docs/CODE_MAP.md`, duplicate top-level symbols, and leftover patch-debris markers as hard failures.
- Never commit `engine.db*`, `*.sqlite*`, `backdrops/`, `__pycache__/`, Python bytecode, or content-bearing `*.trace.json` diagnostics.
