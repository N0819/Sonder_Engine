#!/usr/bin/env python3
"""Lightweight repository-shape checks that require no external linter."""

from __future__ import annotations

import ast
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
