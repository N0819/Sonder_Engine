# Agent package

Each file owns one clear part of the turn pipeline:

- `director.py` — scene establishment, input interpretation, and objective resolution.
- `mapping.py` — the world-context compiler (`compile_world_context`): lorebook
  routing and retrieval, deterministic; it never invents, it records a
  planning need.
- `perception.py` — opening, action-onset, and outcome observer views. Fully
  deterministic: there is no `perception` model role, and this module imports no
  model seam.
- `composer.py` — the view renderer perception calls down into: percept builders
  and `render_view` over a typed IR, plus `observations_from_render`, which is
  where the structured observations are re-derived from the final scrubbed view.
- `character.py` — one character's private decision step, including appraisal
  proposals consumed by deterministic live-psychology commit code.
- `background.py` — background presences, two paths: the batched scene manager
  (`scene_life`, one call voicing every managed presence in a room) when
  enabled, otherwise one stateless reaction for a single deterministically
  selected, named presence.
- `loops.py` — physical reactions, dialogue rounds, and deterministic micro-perception.
- `narration.py` — player-facing prose.
- `common.py` — shared normalization, delivery, lore, and validation helpers.
- `storage.py` — step and active-variant persistence.
- `runtime.py` — plans, streaming, cancellation, resume, reruns, and dispatch.
- `__init__.py` — compatibility facade for existing `from agents import ...` imports.

## Adding an agent stage

This checklist is for an ENGINE stage. A third-party stage needs none of it:
`extension_runtime`'s `api.add_stage(key, anchor=..., handler=...)` registers
the handler and its plan position in one call, and the resulting `ext:` step
inherits schemas-free persistence, one-active-variant, reroll, branches and the
pipeline drawer on its own. See [`docs/guides/EXTENSIONS.md`](../docs/guides/EXTENSIONS.md).

1. Put the implementation in the closest role module, or create a new focused module.
2. Add its structured output contract to `llm/schemas.py` (including `SCHEMA_MAP`, keyed by step id) and prompt to `llm/prompts.py`.
3. Register the fixed step in `runtime.STEP_HANDLERS`.
4. Give it a reader-facing name in `runtime.STEP_LABELS`. This is the step
   easiest to skip and the only one whose omission is visible to a player:
   `step_label()` falls back to the raw step key, so a stage with no entry
   shows its id in the turn-status bar and the pipeline drawer, in every
   language. `tools/extract_ui_catalog.py` harvests this table, so the label
   also has to be translated before `make structure` will pass.
5. Insert it into `runtime.build_plan()` and/or `runtime.establishment_plan()`.
6. Give it a field on `PipelineContext` (`core/pipeline_context.py`) if later stages read its output.
7. Add persistence logic in `persist/commit.py` only when the stage owns durable output.
8. Re-export it from `agents/__init__.py` when external callers need it.
9. Add a focused regression test, then run `make check`.

Keep role modules one-directional: they may import `common.py`, but `common.py`
should never import a role module — that direction holds today and is the one
worth defending. Role modules importing each other is discouraged rather than
prevented, and `loops.py → character.py` and `background.py → perception.py`
already do. `runtime.py` should stay the only module that knows the plan;
a step id is nevertheless named in FOUR registries — `runtime.STEP_HANDLERS`,
`runtime.STEP_LABELS`, `schemas.SCHEMA_MAP` and `core/pipeline_context.py` —
which is why steps 2, 4 and 6 exist. Keep plan placement
explicit even when dispatch is registered dynamically.

One consequence of the extension splice hook that is easy to miss: **the anchor
vocabulary is the core step keys**, and extensions name them from outside the
tree. Renaming a core step therefore breaks every extension anchored on it, in
a way nothing in this repo will catch. Treat a step id as a published name.

Adding a second representation of perceived information is security-sensitive.
It must be a projection of the already-permitted view, not a parallel model
channel fed from Director truth. Exercise the adversarial leak tests whenever a
character payload or perception result gains fields.
