#!/usr/bin/env python3
"""Lightweight repository-shape checks that require no external linter."""

from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

from generate_code_map import OUTPUT, ROOT, generate

FORBIDDEN_PATCH_MARKERS = (
    "Replace the entire",
    "Insert this BEFORE",
    "Add after build_plan",
    "---- PATCH ",
)


def check_duplicate_python_symbols(errors: list[str]) -> None:
    for path in sorted(list(ROOT.glob("*.py")) + list((ROOT / "agents").rglob("*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        symbols: dict[str, list[int]] = defaultdict(list)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols[node.name].append(node.lineno)
        for name, lines in symbols.items():
            if len(lines) > 1:
                errors.append(
                    f"{path.relative_to(ROOT)} defines top-level symbol {name!r} "
                    f"more than once at lines {lines}"
                )


def check_patch_debris(errors: list[str]) -> None:
    paths = (list(ROOT.glob("*.py")) + list((ROOT / "agents").rglob("*.py"))
             + list((ROOT / "static" / "js").glob("*.js")))
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_PATCH_MARKERS:
            if marker in text:
                errors.append(f"{path.relative_to(ROOT)} still contains patch marker {marker!r}")


def check_empty_tests(errors: list[str]) -> None:
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if not path.read_text(encoding="utf-8").strip():
            errors.append(f"{path.relative_to(ROOT)} is empty")


#: An `_ops` name a prompt may mention without owning it. Kept explicit and
#: tiny: an entry here is a promise that the stage is DESCRIBING another
#: stage's field rather than asking for one, and every addition should be
#: justified in the same breath as it is made.
OPS_MENTIONED_BUT_NOT_OWNED: dict[str, set[str]] = {
    # The spatial specialist's stations/poses chunks name contact_ops
    # precisely to DISCLAIM it ("Stations are not contact: contact_ops says
    # what a body is AGAINST...") -- contact is the contact specialist's
    # channel, and the shared segments reference it to draw that boundary.
    "director_spatial": {"contact_ops"},
}

#: Prompt ids validated against another stage's model: the orchestrated
#: prose author's lean sheet is the SAME step (same schema, same step key)
#: as the monolithic resolve, under a different prompt id.
PROMPT_MODEL_ALIASES = {
    "director_resolve_lean": "director_resolve",
}

OPS_NAME = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)*_ops)\b")


def _models_within(annotation) -> list:
    """Every Pydantic model reachable through a type annotation.

    `list[CrowdOp]`, `Optional[StateDiff]` and bare `StateDiff` all have to
    yield their model, because the field a prompt names is often two levels
    down -- `state_diff.crowd_ops` lives on `StateDiff`, not on the stage's
    own output model.
    """
    from pydantic import BaseModel

    found, stack = [], [annotation]
    while stack:
        candidate = stack.pop()
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            found.append(candidate)
        stack.extend(getattr(candidate, "__args__", ()) or ())
    return found


def _field_names(model, seen: set | None = None) -> set:
    seen = set() if seen is None else seen
    if model in seen:
        return set()
    seen.add(model)
    names = set()
    fields = (getattr(model, "model_fields", None)
              or getattr(model, "__fields__", {}))
    for name, field in fields.items():
        names.add(name)
        # BOTH, not the first truthy one. A forward-referenced field keeps an
        # unresolved `ForwardRef` in `.annotation` long after
        # `update_forward_refs()` has put the real class in `.outer_type_` --
        # so preferring `.annotation` made every forward-referenced nested
        # model invisible here, and this check silently stopped covering it.
        # Found by `DirectorInterpret.state_assertions: Optional["StateDiff"]`,
        # which is exactly the shape the check exists for.
        for source in (getattr(field, "annotation", None),
                       getattr(field, "outer_type_", None)):
            for nested in _models_within(source):
                names |= _field_names(nested, seen)
    return names


def check_prompt_schema_ops(errors: list[str]) -> None:
    """Every `_ops` field a prompt asks for must exist on that stage's model.

    A prompt and a schema are two spellings of one contract, and this project's
    own rule is that where two spellings of a thing can exist, they should be
    folded rather than trusted to stay level. Nothing folded them, and the same
    defect landed three times in two days:

      * `entry_ops` asked for by the lore prompt, `entries` opened by the
        reader. Shipped, reported by a user against alpha 7.2, fixed in 7.2.1.
      * `offscreen_plan_ops` printed OUTSIDE `state_diff` by a stray brace in
        the resolve prompt's shape line, while `offscreen.apply_plan_ops`
        opens `state_diff.offscreen_plan_ops`.
      * `project_ops` asked for by name in three places in the character
        prompt, with no such field on `CharacterOutput`. Pydantic dropped every
        op, silently, and "has ever held a project: 0 of 14 banks" was the
        cost -- an entire tier of psychology that could be asked for, answered,
        and never heard.

    Each cost a measurement or a user to find. This finds them for nothing, and
    it is deliberately narrow: `_ops` fields are where the pattern actually
    bites, because they are the fields a prompt has to name in prose AND print
    in a shape, which is two chances to drift.

    Verified against the real defect rather than assumed -- at the commit
    before the fix, this reports `character MISSING ['project_ops']`.
    """
    sys.path.insert(0, str(ROOT))
    try:
        import prompts
        import schemas
    except Exception as exc:  # pragma: no cover - import failure is its own error
        errors.append(f"could not check prompt/schema ops drift: {exc}")
        return

    checks = [(stage, stage) for stage in schemas.SCHEMA_MAP]
    checks += [(pid, stage) for pid, stage in PROMPT_MODEL_ALIASES.items()]
    for pid, stage in checks:
        model = schemas.SCHEMA_MAP.get(stage)
        text = prompts.DEFAULT_PROMPTS.get(pid)
        if model is None or not isinstance(text, str):
            continue
        allowed = OPS_MENTIONED_BUT_NOT_OWNED.get(pid, set())
        missing = sorted(set(OPS_NAME.findall(text))
                         - _field_names(model) - allowed)
        for name in missing:
            errors.append(
                f"the {pid!r} prompt asks for {name!r} and "
                f"{model.__name__} has no such field, so validation will drop "
                "every one the model sends"
            )


def check_specialist_prompt_chunks(errors: list[str]) -> None:
    """The orchestrated Director's scoping is only real if the prompts are
    CHUNKED to match it (design note 19, hierarchical gating): a specialist's
    sheet is core + one chunk per channel in the granted scope, and scope
    selects chunks with no other logic. An unchunked prompt silently defeats
    the mechanism -- a specialist whose instructions all live in its core
    loads everything on every beat while appearing scoped. Three files spell
    the ownership (agents/director.SPECIALISTS, prompts.
    SPECIALIST_PROMPT_SPECS, schemas.SPECIALIST_CHANNELS); this holds them
    level and enforces the chunk structure:

      * every channel a specialist owns has a chunk, and no chunk exists for
        a channel it does not own (an orphan means a channel changed hands
        and its instructions did not);
      * the three registries agree on channels per specialist;
      * a specialist's CORE never names its own channels (word-boundary
        match): channel-specific instruction lives in chunks ONLY. This is
        the honest approximation of "no channel-specific instruction in the
        core" -- it cannot see a paraphrase, and that limitation is
        accepted and recorded in design note 19 rather than papered over
        with a semantic check that would pass for the wrong reason.
    """
    sys.path.insert(0, str(ROOT))
    try:
        import prompts
        import schemas
        from agents import director
    except Exception as exc:  # pragma: no cover - import failure is its own error
        errors.append(f"could not check specialist prompt chunks: {exc}")
        return

    prompt_specs = getattr(prompts, "SPECIALIST_PROMPT_SPECS", {})
    runtime_specs = getattr(director, "SPECIALISTS", {})
    schema_channels = getattr(schemas, "SPECIALIST_CHANNELS", {})

    if set(prompt_specs) != set(runtime_specs):
        errors.append(
            "specialist registries disagree: prompts.SPECIALIST_PROMPT_SPECS "
            f"has {sorted(prompt_specs)} but agents/director.SPECIALISTS has "
            f"{sorted(runtime_specs)}")
        return

    for name, runtime in sorted(runtime_specs.items()):
        owned = set(runtime.get("channels") or ())
        prompt_spec = prompt_specs.get(name) or {}
        chunks = set((prompt_spec.get("chunks") or {}).keys())
        order = list(prompt_spec.get("order") or ())
        step_key = runtime.get("step_key")
        schema_owned = set(schema_channels.get(step_key) or ())

        for missing in sorted(owned - chunks):
            errors.append(
                f"specialist {name!r} owns channel {missing!r} but its "
                "prompt has no chunk for it -- the scoped sheet can never "
                "teach that channel and every grant of it loads nothing")
        for orphan in sorted(chunks - owned):
            errors.append(
                f"specialist {name!r} prompt carries a chunk for "
                f"{orphan!r}, a channel it does not own -- the channel "
                "changed hands and its instructions did not")
        if owned != schema_owned:
            errors.append(
                f"specialist {name!r} channels disagree with schemas."
                f"SPECIALIST_CHANNELS[{step_key!r}]: {sorted(owned)} vs "
                f"{sorted(schema_owned)}")
        if set(order) != chunks:
            errors.append(
                f"specialist {name!r} chunk order {order} does not cover "
                f"exactly its chunks {sorted(chunks)} -- an unordered chunk "
                "never loads")

        core = str(prompt_spec.get("core") or "")
        for channel in sorted(owned):
            if re.search(r"(?<![\w.])%s\b" % re.escape(channel), core):
                errors.append(
                    f"specialist {name!r} core names its own channel "
                    f"{channel!r} -- channel-specific instruction belongs "
                    "in that channel's chunk, or scoping silently stops "
                    "meaning anything")

        # The same `_ops` drift check the stage prompts get, against the
        # FULLY assembled sheet: every _ops name the sheet can ask for must
        # exist on this specialist's model, or validation silently drops
        # every one the model sends (the project_ops lesson, one level in).
        model = schemas.SCHEMA_MAP.get(step_key)
        if model is not None:
            sheet = core + "".join(
                str(chunk) for chunk in
                (prompt_spec.get("chunks") or {}).values())
            allowed = OPS_MENTIONED_BUT_NOT_OWNED.get(step_key, set())
            for op_name in sorted(set(OPS_NAME.findall(sheet))
                                  - _field_names(model) - allowed):
                errors.append(
                    f"specialist {name!r} sheet asks for {op_name!r} and "
                    f"{model.__name__} has no such field, so validation "
                    "will drop every one the model sends")


def check_generated_map(errors: list[str]) -> None:
    expected = generate()
    actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if actual != expected:
        errors.append("docs/CODE_MAP.md is stale; run python tools/generate_code_map.py")


def main() -> int:
    errors: list[str] = []
    check_duplicate_python_symbols(errors)
    check_patch_debris(errors)
    check_empty_tests(errors)
    check_prompt_schema_ops(errors)
    check_specialist_prompt_chunks(errors)
    check_generated_map(errors)

    if errors:
        print("Project structure checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Project structure checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
