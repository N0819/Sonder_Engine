# Agent package

Each file owns one clear part of the turn pipeline:

- `director.py` — scene establishment, input interpretation, and objective resolution.
- `mapping.py` — lorebook routing and retrieval.
- `perception.py` — opening, action-onset, and outcome observer views.
- `character.py` — one character's private decision step.
- `loops.py` — physical reactions, dialogue rounds, and deterministic micro-perception.
- `narration.py` — player-facing prose.
- `common.py` — shared normalization, delivery, lore, and validation helpers.
- `storage.py` — step and active-variant persistence.
- `runtime.py` — plans, streaming, cancellation, resume, reruns, and dispatch.
- `__init__.py` — compatibility facade for existing `from agents import ...` imports.

## Adding an agent stage

1. Put the implementation in the closest role module, or create a new focused module.
2. Add its structured output contract to `schemas.py` and prompt to `prompts.py`.
3. Register the fixed step in `runtime.STEP_HANDLERS` (or call `register_step()` from an extension).
4. Insert it into `runtime.build_plan()` and/or `runtime.establishment_plan()`.
5. Add persistence logic in `commit.py` only when the stage owns durable output.
6. Re-export it from `agents/__init__.py` when external callers need it.
7. Add a focused regression test, then run `make check`.

Keep role modules one-directional: they may import `common.py`, but `common.py`
should never import a role module. `runtime.py` is the only module that should
know every built-in stage. Keep plan placement explicit even when dispatch is registered dynamically.
