# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Start here

This repo already maintains detailed docs for coding agents. Read them before making non-trivial changes:

1. [`AGENTS.md`](AGENTS.md) — edit routing table (which files to touch for which change), core invariants, source-of-truth order, and safe change workflow. **Read this first for any behavioral change.**
2. [`docs/PIPELINE.md`](docs/PIPELINE.md) — exact opening-turn and normal-turn execution flow, stage-by-stage.
3. [`docs/CODE_MAP.md`](docs/CODE_MAP.md) — generated index of modules, functions, routes, DB tables, and frontend sections. Regenerate with `python tools/generate_code_map.py`; do not hand-edit.
4. [`docs/DATABASE.md`](docs/DATABASE.md) — schema, write helpers (`q`/`qi`/`qtx`/`transaction`/`wget`/`wset`), and the schema-change checklist.
5. [`Design.md`](Design.md) — product philosophy, full architecture, known weaknesses, and roadmap. Verify against actual code before trusting it as current.
6. [`agents/README.md`](agents/README.md) — how to add a new pipeline stage.

Do not duplicate content from these files in explanations; point to them instead.

## Commands

```bash
make run        # start the local server (uvicorn app:app --reload, port 8008)
make test       # pytest -q
make map        # regenerate docs/CODE_MAP.md
make structure  # run tools/project_check.py (duplicate-symbol, patch-debris, empty-test, stale-map checks)
make compile    # python -m compileall on all source
make check      # compile + map + structure + test — run this before considering a change done
```

Single test:

```bash
pytest tests/test_spatial.py::test_name -q
```

Run commands from the repository root — the app uses top-level imports (`from db import q`), so it is not an installed package. Python 3.11+.

The default SQLite database is `engine.db`; override with `ENGINE_DB` before importing `db.py`. Tests use the `temp_db` fixture (`tests/conftest.py`), which calls `db.configure()` on a temp file and cleans up WAL/SHM afterward — never point tests at the real `engine.db`.

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
- **Perception** (`agents/perception.py`) is a stateless filter deciding what each observer legitimately receives; it must not invent intent or leak hidden state.
- **Character agents** (`agents/character.py`, `agents/loops.py`) declare behavior from private perception/memory/relationships only; they never decide their own success.
- **`agents/background.py`** gives at most one named, unregistered background presence a single stateless reaction per beat — no persistent memory or psychology (that requires promotion to a real character). Deterministically gated by `commit.py`'s `pick_background_reactor`, which returns `None` (no LLM call) for the large majority of turns.
- The **Narrator** (`agents/narration.py`) renders only the player-facing slice and cannot originate new player conduct or reveal unperceived facts.
- **`commit.py`** is the sole persistence boundary — model output is provisional until deterministic commit code validates it. Slow lore/memory preparation happens before the write lock, then all primary turn mutations commit inside one outer transaction. Any domain failure rolls the entire turn back; only reconstructible autobiographical-summary consolidation runs afterward.

`agents/__init__.py` is a compatibility facade; role modules (`director.py`, `perception.py`, `character.py`, etc.) may import `agents/common.py` but never each other, and `runtime.py` is the only module aware of every built-in stage.

The repo has two overlapping physical world representations — the JSON `world.scene` blob and normalized `world_*`/`fiction_*` tables — that are not yet reconciled. Check both the commit path and restore path before changing either (see `docs/DATABASE.md`).

Frontend (`static/js/`) uses browser globals, not ES modules; script load order in `static/index.html` matters (`utils.js → components.js → editors.js → lorebooks.js → chat.js → settings.js → app.js`). Never rename a shared JS function without grepping every file.

## Working in this repo

- Reproduce a bug with a focused test before fixing; fix the earliest stage where data first becomes wrong rather than compensating downstream (e.g., in the Narrator).
- New persistent fields need: schema/migration in `db.py`, read/commit code, export/import payload, checkpoint snapshot+restore, ID remapping in `app.py` if applicable, and a regression test (full checklist in `docs/DATABASE.md`).
- Avoid broad rewrites of `agents/runtime.py`, `app.py`, or `memory.py` without dedicated tests — these are orchestration seams affecting reruns, variants, streaming, and commits.
- Run `make check` before considering a change complete; it will catch a stale `docs/CODE_MAP.md`, duplicate top-level symbols, and leftover patch-debris markers as hard failures.
