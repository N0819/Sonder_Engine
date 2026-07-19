#!/usr/bin/env python3
"""Regenerate docs/CODE_MAP.md from the current source tree.

The output is intentionally structural rather than interpretive: module imports,
large top-level functions, FastAPI routes, database tables, and frontend section
markers. Keep durable architectural explanations in AGENTS.md and docs/PIPELINE.md.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "CODE_MAP.md"

MODULE_PURPOSES = {
    "agents": "Backward-compatible facade for the role-specific agent package.",
    "agents.character": "Private character decision agent.",
    "agents.common": "Shared normalization, lore, delivery, and perception helpers.",
    "agents.director": "Scene establishment, player interpretation, and objective resolution.",
    "agents.loops": "Reaction loops, interaction rounds, and deterministic micro-perception.",
    "agents.mapping": "Lore routing, cached recall, and retrieval staging.",
    "agents.narration": "Player-facing narration agent.",
    "agents.perception": "Opening, action-onset, and outcome observer views.",
    "agents.runtime": "Pipeline plans, dispatch, streaming, cancellation, resume, and reruns.",
    "agents.storage": "Step and active-variant persistence helpers.",
    "app": "FastAPI application, resource CRUD, import/export, turn control, and streaming endpoints.",
    "character_schema": "Versioned character/persona defaults, normalization, accessors, and export payloads.",
    "checkpoints": "Whole-chat snapshots and checkpoint restore orchestration.",
    "commit": "Validated persistence of scene, entities, cast, lore, relationships, events, and memories.",
    "db": "SQLite schema, migrations, connection management, transactions, and key/value world access.",
    "importers": "Native and AI-assisted character, persona, and lorebook import/generation.",
    "llm_quality": "Strict JSON parsing, schema validation, and model-assisted repair.",
    "logging_utils": "Structured timing and observability helpers.",
    "memory": "Lorebook graph, memory retrieval/consolidation, relationships, and vector search.",
    "pipeline_context": "Typed mutable context passed through a turn pipeline.",
    "prompt_cache": "Provider-specific prompt-cache helpers.",
    "prompts": "Default system prompts and prompt preset access.",
    "providers": "Provider selection, retries, streaming, cancellation, model listing, and embeddings.",
    "scene": "Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge.",
    "schemas": "Pydantic output contracts and semantic validation for agent payloads.",
    "spatial": "Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic.",
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def source_paths() -> list[Path]:
    paths = list(ROOT.glob("*.py"))
    agents_dir = ROOT / "agents"
    if agents_dir.exists():
        paths.extend(agents_dir.rglob("*.py"))
    return sorted(paths)


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def display_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def resolve_import(path: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    current = module_name(path).split(".")
    package = current if path.name == "__init__.py" else current[:-1]
    keep = max(0, len(package) - (node.level - 1))
    parts = package[:keep]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts) or None


def md(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def parse_module(path: Path, local_modules: set[str]) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    local_roots = {name.split(".")[0] for name in local_modules}
    imports: set[str] = set()
    functions: list[tuple[str, int, int, bool]] = []
    classes: list[tuple[str, int, int]] = []
    routes: list[tuple[str, str, str, int]] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                if root_name in local_roots:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imported = resolve_import(path, node)
            if imported and imported.split(".")[0] in local_roots:
                imports.add(imported)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            functions.append((
                node.name,
                node.lineno,
                end - node.lineno + 1,
                isinstance(node, ast.AsyncFunctionDef),
            ))
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if not isinstance(func, ast.Attribute) or func.attr not in HTTP_METHODS:
                    continue
                if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                    continue
                route_path = decorator.args[0].value
                routes.append((func.attr.upper(), str(route_path), node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            classes.append((node.name, node.lineno, end - node.lineno + 1))

    return {
        "imports": sorted(imports),
        "functions": functions,
        "classes": classes,
        "routes": routes,
        "lines": len(path.read_text(encoding="utf-8").splitlines()),
    }


def database_tables() -> list[tuple[str, list[str]]]:
    text = (ROOT / "db.py").read_text(encoding="utf-8")
    match = re.search(r'SCHEMA\s*=\s*"""(.*?)"""', text, re.S)
    if not match:
        return []
    tables: list[tuple[str, list[str]]] = []
    pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\);",
        re.I | re.S,
    )
    for table_match in pattern.finditer(match.group(1)):
        columns: list[str] = []
        for line in table_match.group(2).splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(("PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CHECK", "CONSTRAINT")):
                continue
            columns.append(line.split()[0].rstrip(","))
        tables.append((table_match.group(1), columns))
    return tables


def js_map(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    text = path.read_text(encoding="utf-8")
    sections: list[tuple[int, str]] = []
    functions: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        section = re.match(r"\s*//\s*-{2,}\s*(.*?)\s*-*\s*$", line)
        if section and section.group(1):
            sections.append((line_no, section.group(1)))
        function = re.match(r"\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", line)
        if function:
            functions.append((line_no, function.group(1)))
    return sections, functions


def generate() -> str:
    paths = source_paths()
    local_modules = {module_name(path) for path in paths}
    modules = [(path, parse_module(path, local_modules)) for path in paths]
    lines: list[str] = [
        "# Generated Code Map",
        "",
        "> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.",
        "",
        "## Python modules",
        "",
        "| Module | Lines | Purpose | Local dependencies |",
        "|---|---:|---|---|",
    ]
    for path, info in modules:
        name = module_name(path)
        lines.append(
            f"| `{display_path(path)}` | {info['lines']} | {md(MODULE_PURPOSES.get(name, ''))} | "
            f"{', '.join(f'`{dependency}`' for dependency in info['imports']) or '—'} |"
        )

    lines += ["", "## Largest top-level functions", ""]
    for path, info in modules:
        largest = sorted(info["functions"], key=lambda item: item[2], reverse=True)[:8]
        if not largest:
            continue
        lines += [f"### `{display_path(path)}`", "", "| Function | Start | Size |", "|---|---:|---:|"]
        for name, start, size, is_async in largest:
            prefix = "async " if is_async else ""
            lines.append(f"| `{prefix}{name}()` | {start} | {size} lines |")
        lines.append("")

    route_rows = []
    for path, info in modules:
        route_rows.extend(
            (method, route, func, line, display_path(path))
            for method, route, func, line in info["routes"]
        )
    if route_rows:
        lines += ["## FastAPI routes", "", "| Method | Path | Handler | Source |", "|---|---|---|---|"]
        for method, route, func, line, source in sorted(route_rows, key=lambda item: (item[1], item[0])):
            lines.append(f"| {method} | `{md(route)}` | `{func}()` | `{source}:{line}` |")
        lines.append("")

    lines += ["## Database tables", "", "| Table | Columns |", "|---|---|"]
    for table, columns in database_tables():
        lines.append(f"| `{table}` | {', '.join(f'`{column}`' for column in columns)} |")
    lines.append("")

    js_paths = sorted((ROOT / "static" / "js").glob("*.js"))
    if js_paths:
        lines += ["## Frontend JavaScript", ""]
        for path in js_paths:
            sections, functions = js_map(path)
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            lines += [f"### `static/js/{path.name}` ({line_count} lines)", ""]
            if sections:
                lines.append("Sections: " + "; ".join(f"{name} (`:{line}`)" for line, name in sections) + ".")
                lines.append("")
            if functions:
                lines.append("Declared functions: " + ", ".join(f"`{name}()`" for _, name in functions) + ".")
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generate(), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
