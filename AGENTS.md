# Editing Guide for Coding Agents

This file is the operational map for changing Sonder Engine safely. It is written for both human contributors and AI coding agents.

## First-pass orientation

Before editing behavior:

1. Read `docs/PIPELINE.md` for execution order and ownership boundaries.
2. Search `docs/CODE_MAP.md` for the handler or function involved.
3. Read the relevant schema in `schemas.py` before changing any model output.
4. Read the corresponding commit function before adding fields that should persist.
5. Find the nearest regression test and run the narrow test first.

Regenerate the structural map after moving or adding functions:

```bash
python tools/generate_code_map.py
python tools/project_check.py
```

## Edit routing

| Change | Primary files | Usually inspect too |
|---|---|---|
| Player input interpretation | `agents/director.py` (`director_interpret`) | `schemas.py`, `prompts.py`, pipeline tests |
| Flow planning, resume, or streaming | `agents/runtime.py` (`build_plan`, `_run_pipeline`) | `agents/storage.py`, `checkpoints.py`, pipeline tests |
| Opening scene generation | `agents/director.py`, `agents/perception.py` | `scene.py`, `spatial.py`, `commit.py` |
| Perception or information leakage | `agents/perception.py`, `agents/common.py` delivery helpers | `spatial.py`, `scene.py`, `schemas.py`, perception tests |
| Character decisions or dialogue | `agents/character.py`, `agents/loops.py` | `memory.py`, `scene.py`, `prompts.py` |
| Background (unregistered) presence reactions | `agents/background.py`, `commit.py` (`pick_background_reactor`) | `agents/perception.py` (merge into dialogue_log), `prompts.py`, `schemas.py` |
| Objective action resolution | `agents/director.py` (`director_resolve`) | `schemas.py`, `spatial.py`, `commit.py` |
| Narration | `agents/narration.py` (`narrator`) | narrator prompt in `prompts.py`, output validation |
| Persistence or rollback | `commit.py`, `checkpoints.py` | `db.py`, `memory.py`, restore tests |
| Lore retrieval or hierarchy | `memory.py`, `agents/mapping.py` | `app.py`, lore tests |
| Character/persona format | `character_schema.py` | `importers.py`, editor UI, schema tests |
| Provider behavior | `providers.py` | `app.py` provider routes, `prompt_cache.py` |
| API behavior | `app.py` | matching file in `static/js/` |
| Browser UI | `static/index.html`, `static/js/`, CSS | matching API route in `app.py` |
| Database shape | `db.py` | migrations, snapshot/export/restore code, tests |

## Core invariants

These are architectural guarantees, not stylistic preferences.

### Information boundaries

- A character may use only its perception, memory, knowledge configuration, relationships, private history, and explicit inferences.
- Objective world state must not be copied into a character context merely with an instruction to ignore unavailable details.
- Perception of an action onset and perception of its resolved outcome are separate passes.
- The Narrator should render the player-facing view, not an omniscient reconstruction of every private agent result.

### Authority boundaries

- The player owns the declaration of player speech, thought, and attempted action.
- The Director interprets and resolves declarations; it must not silently replace the player’s declared content.
- Character agents declare behavior but do not author objective success.
- Model output is provisional until deterministic commit code validates and persists it.

### Persistence boundaries

- `steps` and `variants` preserve inspectable intermediate outputs; exactly one active variant should exist per materialized step.
- A checkpoint is established before a pipeline run mutates durable state.
- Stable event identifiers should prevent duplicate memories and duplicate persistence on reruns.
- Primary turn effects are atomic: a commit-domain failure must roll back every durable effect from that turn. Slow provider work belongs in preparation before the outer write transaction.
- New persistent fields require an explicit owner, snapshot/export behavior, restore behavior, and a regression test.

## Source-of-truth order

When several representations disagree, resolve the conflict deliberately rather than updating all copies blindly.

1. **SQLite rows and `world` keys** are the durable runtime state.
2. **Active step variants** are the inspectable result of the current turn.
3. **`PipelineContext`** is the in-memory working state for one execution.
4. **Pydantic schemas** define accepted structured model output.
5. **Prompts** describe desired behavior but do not override deterministic validation.
6. **`Design.md`** describes intended architecture; verify implementation before assuming it is current.

The current architecture still has overlapping physical representations (`world.scene` and normalized world tables). Read the relevant commit and restore paths before changing either.

## Safe change workflow

1. Reproduce the problem with a focused test or saved payload.
2. Identify the earliest stage where the data first becomes wrong.
3. Fix that stage rather than compensating in the Narrator or UI.
4. Validate the structured output in `schemas.py` when possible.
5. Keep persistence deterministic in `commit.py`.
6. Run the focused tests, then `make check`.

Avoid broad rewrites of `agents/runtime.py`, `app.py`, or `memory.py` unless the change has dedicated tests. These files contain orchestration seams; seemingly local edits can affect reruns, variants, streaming, and commits.

## Large-file landmarks

### `agents/`

- `director.py`: scene establishment, interpretation, and resolution
- `mapping.py`: lore routing and retrieval
- `perception.py`: opening, action-onset, and outcome views
- `character.py`: one character decision
- `background.py`: one-beat, stateless reaction for a named background presence with no character sheet (deterministically gated by `commit.py`'s `pick_background_reactor`)
- `loops.py`: deterministic micro-perception, reactions, and dialogue rounds
- `narration.py`: player-facing prose
- `common.py`: shared normalization and delivery helpers
- `storage.py`: steps and variants
- `runtime.py`: dispatch, plans, streaming, resume, and reruns
- `__init__.py`: compatibility exports for `from agents import ...`

### `app.py`

- Bootstrap/settings
- Lorebook tree and links
- Providers
- Characters and personas
- Lorebooks
- Chats, export/import, and branches
- Memories
- Turns, rerolls, checkpoints, resume, and async streaming

### `memory.py`

- Lorebook hierarchy and graph resolution
- Chat lorebook attachment resolution
- Memory normalization and hybrid retrieval
- Summaries and consolidation
- Snapshot/restore
- Lore entries
- Relationships
- Vector index

### Frontend

The UI uses browser globals rather than ES modules. Script order in `static/index.html` matters:

`utils.js → components.js → editors.js → lorebooks.js → chat.js → settings.js → app.js`

Do not rename a shared function without searching every JavaScript file.

## Test organization

- `test_pipeline_safety.py`: materialization, recent-event, and commit failure behavior.
- `test_spatial.py`: room/barrier/hearing/visibility and scene-diff behavior.
- `test_memory_*`: retrieval, deduplication, commit, and restore.
- `test_lore*`: lorebook graph, stability, and restore.
- `test_character_schema.py` and importer tests: resource formats.
- `test_theory_of_mind.py`, `test_tom_normalization.py`, and `test_ability_isolation.py`: private cognition boundaries.

Add a test next to the subsystem it protects. A bug involving leaked dialogue or private knowledge belongs in a perception/cognition test, not only in a narrator snapshot.
