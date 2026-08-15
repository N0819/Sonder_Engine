# Agent package

Each file owns one clear part of the turn pipeline:

- `director.py` — scene establishment, input interpretation, and objective resolution.
- `mapping.py` — lorebook routing and retrieval.
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

1. Put the implementation in the closest role module, or create a new focused module.
2. Add its structured output contract to `schemas.py` (including `SCHEMA_MAP`, keyed by step id) and prompt to `prompts.py`.
3. Register the fixed step in `runtime.STEP_HANDLERS` (or call `register_step()` from an extension).
4. Insert it into `runtime.build_plan()` and/or `runtime.establishment_plan()`.
5. Give it a field on `PipelineContext` (`pipeline_context.py`) if later stages read its output.
6. Add persistence logic in `commit.py` only when the stage owns durable output.
7. Re-export it from `agents/__init__.py` when external callers need it.
8. Add a focused regression test, then run `make check`.

Keep role modules one-directional: they may import `common.py`, but `common.py`
should never import a role module — that direction holds today and is the one
worth defending. Role modules importing each other is discouraged rather than
prevented, and `loops.py → character.py` and `background.py → perception.py`
already do. `runtime.py` should stay the only module that knows the plan;
step ids themselves are also named in `schemas.SCHEMA_MAP` and
`pipeline_context.py`, which is why steps 2 and 5 exist. Keep plan placement
explicit even when dispatch is registered dynamically.

Adding a second representation of perceived information is security-sensitive.
It must be a projection of the already-permitted view, not a parallel model
channel fed from Director truth. Exercise the adversarial leak tests whenever a
character payload or perception result gains fields.
