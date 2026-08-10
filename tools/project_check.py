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
OPS_MENTIONED_BUT_NOT_OWNED: dict[str, set[str]] = {}

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
        annotation = (getattr(field, "annotation", None)
                      or getattr(field, "outer_type_", None))
        for nested in _models_within(annotation):
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

    for stage, model in schemas.SCHEMA_MAP.items():
        text = prompts.DEFAULT_PROMPTS.get(stage)
        if not isinstance(text, str):
            continue
        allowed = OPS_MENTIONED_BUT_NOT_OWNED.get(stage, set())
        missing = sorted(set(OPS_NAME.findall(text))
                         - _field_names(model) - allowed)
        for name in missing:
            errors.append(
                f"the {stage!r} prompt asks for {name!r} and "
                f"{model.__name__} has no such field, so validation will drop "
                "every one the model sends"
            )


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
