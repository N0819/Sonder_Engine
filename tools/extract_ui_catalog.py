"""Build/check the English source-message catalog for browser surfaces.

English source strings are gettext-style message ids. Code may retain them as
fallbacks, but a story/UI language pack must provide the same key set. This
scanner is intentionally overinclusive: an unused label in a catalog is cheap;
an untranslated reader-visible sentence is not.
"""

from __future__ import annotations

import argparse
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
UI_PATH = ROOT / "language_packs" / "en" / "ui.json"
HTML_FILES = tuple(sorted((ROOT / "static").glob("*.html")))
JS_FILES = tuple(sorted((ROOT / "static" / "js").glob("*.js")))
#: The engine's own modules, which since the 2026-08-18 layout change live in
#: subsystem packages rather than at the repository root.
SUBSYSTEM_PACKAGES = ("core", "llm", "world", "mind", "story",
                      "dressing", "persist", "web")
PY_FILES = tuple(sorted(
    path
    for pkg in SUBSYSTEM_PACKAGES
    for path in (ROOT / pkg).glob("*.py")
    if path.name not in {"prompts.py"}
)) + tuple(sorted((ROOT / "agents").rglob("*.py")))
#: `rglob` under `agents/`, matching `generate_code_map.source_paths` and
#: `project_check.engine_python_paths`. `agents/` has no subpackage today, so
#: the three agreed by accident; the day one is added, a `glob` catalogue
#: silently stops seeing the strings in it and the missing UI text looks like
#: a translation gap rather than a harvest gap.
ATTRS = frozenset(("title", "aria-label", "placeholder", "alt"))


def _skip_trivia(source: str, i: int) -> int:
    """Advance past whitespace and comments."""
    size = len(source)
    while i < size:
        if source[i].isspace():
            i += 1
        elif source.startswith("//", i):
            end = source.find("\n", i)
            i = size if end < 0 else end + 1
        elif source.startswith("/*", i):
            end = source.find("*/", i)
            i = size if end < 0 else end + 2
        else:
            break
    return i


def _read_literal(source: str, i: int):
    """Read one quoted literal starting at `i`; return (body, index_after)."""
    quote, start = source[i], i + 1
    i += 1
    escaped = False
    while i < len(source):
        current = source[i]
        if escaped:
            escaped = False
        elif current == "\\":
            escaped = True
        elif current == quote:
            return source[start:i], i + 1
        i += 1
    return None, i


def _javascript_strings(source: str):
    """Yield actual JS string/template bodies, skipping comments and regexes.

    The old regex started a "string" at quote characters inside comments or
    regular-expression literals and sometimes closed it hundreds of lines
    later. That polluted the public translation catalog with source code and
    made translation completeness impossible to measure.
    """
    i, size = 0, len(source)
    previous = ""
    while i < size:
        char = source[i]
        nxt = source[i + 1] if i + 1 < size else ""
        if char.isspace():
            i += 1
            continue
        if char == "/" and nxt == "/":
            end = source.find("\n", i + 2)
            i = size if end < 0 else end + 1
            continue
        if char == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            i = size if end < 0 else end + 2
            continue
        if char in "\"'`":
            quote, start = char, i + 1
            i += 1
            escaped = False
            while i < size:
                current = source[i]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    body = source[start:i]
                    i += 1
                    previous = "string"
                    # `"a " + "b"` is ONE message at runtime -- `el()` and
                    # `t()` see the joined text -- but the scanner stored only
                    # the halves, so the longest explanatory strings in the
                    # settings and editor panels could never match. Consume
                    # the whole run and yield it once: the halves are
                    # mid-sentence fragments nothing ever looks up, and
                    # emitting them too would demand a translation for each.
                    joined, cursor = body, i
                    while True:
                        after = _skip_trivia(source, cursor)
                        if after >= size or source[after] != "+":
                            break
                        after = _skip_trivia(source, after + 1)
                        if after >= size or source[after] != quote:
                            break
                        piece, after = _read_literal(source, after)
                        if piece is None:
                            break
                        joined += piece
                        cursor = after
                    yield joined
                    i = cursor
                    break
                i += 1
            continue
        if char == "/" and (not previous or previous[-1:] in "=(:,![{;?"
                            or previous in {"return", "case", "throw"}):
            # JavaScript regex literal. Track [] so a slash inside a class is
            # not mistaken for the terminator.
            i += 1
            escaped = False
            in_class = False
            while i < size:
                current = source[i]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == "[":
                    in_class = True
                elif current == "]":
                    in_class = False
                elif current == "/" and not in_class:
                    i += 1
                    while i < size and source[i].isalpha():
                        i += 1
                    previous = "regex"
                    break
                i += 1
            continue
        if char.isalpha() or char in "_$":
            start = i
            i += 1
            while i < size and (source[i].isalnum() or source[i] in "_$"):
                i += 1
            previous = source[start:i]
            continue
        previous = char
        i += 1


def _message(value: str, label_position: bool = False) -> str | None:
    value = " ".join(str(value or "").split())
    if len(value) < 2 or not any(ch.isalpha() for ch in value):
        return None
    # A regex scanner can see a quote in a JS comment/regex as the start of a
    # string and close it much later. Never publish captured source code in the
    # catalog endpoint; real interface messages are deliberately concise.
    # These markers reject a candidate as captured SOURCE. Two of them were
    # matching ordinary prose and silently dropping real messages: " let "
    # appears in "Leave blank to let OpenRouter choose", and "?." now appears
    # inside legitimate template literals like
    # `Could not load the app: ${e?.message || e}`. Both are re-scoped to the
    # shapes that only occur in code.
    if len(value) > 500 or any(marker in value for marker in (
            " function ", " const ", " => ",
            "document.", "querySelector", "addEventListener", "return ",
            "/api/", "await ", " // ", "$(\"")):
        return None
    # `let x =` is code; "to let OpenRouter choose" is not.
    if re.search(r"\blet\s+[A-Za-z_$][\w$]*\s*=", value):
        return None
    # Optional chaining is code UNLESS it sits inside a ${...} placeholder,
    # where it is just how the message interpolates a value.
    stripped_placeholders = re.sub(r"\$\{[^}]*\}", "", value)
    if "?." in stripped_placeholders:
        return None
    # A leading "/" or "#" is a path or selector. A leading "." is usually a
    # class selector -- but ". Saving stores a story-local override." is a
    # sentence fragment appended to another string, so a following space and
    # capital letter mark it as prose.
    if value.startswith((("/", "#"))) or "\\b" in value:
        return None
    if value.startswith(".") and not re.match(r"\.\s+[A-Z]", value):
        return None
    if value.count(";") >= 2 or (":" in value and "var(--" in value):
        return None
    # Machine vocabulary with no whitespace/capitalization is normally a
    # route, key, class, enum, or event name. Human one-word labels start with
    # a capital or contain punctuation/space and remain eligible.
    #
    # `label_position` overrides this: the character editor's tier dropdown
    # reads "background / recurring / major/antagonist" and the voice dropdown
    # "terse / natural / chatty" -- all of them lowercase, all of them on
    # screen, and all of them rejected here as if they were enum values. They
    # are enum LABELS, and the only thing that distinguishes the two is where
    # the string sits, not how it looks.
    if not label_position and re.fullmatch(r"[a-z0-9_.:/-]+", value):
        return None
    return value


class _HTMLMessages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.messages = set()

    def handle_starttag(self, _tag, attrs):
        for name, value in attrs:
            if name in ATTRS:
                message = _message(value)
                if message:
                    self.messages.add(message)

    def handle_data(self, data):
        message = _message(data)
        if message:
            self.messages.add(message)


def _python_text(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append("${" + ast.unparse(value.value) + "}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _python_text(node.left), _python_text(node.right)
        return left + right if left is not None and right is not None else None
    return None


#: Module-level tables whose STRING VALUES are shown to the reader.
#:
#: Named explicitly rather than swept, because most Python strings in this
#: repo are prompts, log lines or protocol and must never enter the catalog.
#: Each entry here is a promise that the table's values are interface copy.
READER_FACING_TABLES = {
    "agents/runtime.py": {"FRIENDLY_STEP_LABELS", "STEP_LABELS"},
    "world/living_world.py": {"LIVING_WORLD_DESCRIPTIONS"},
    "story/scene.py": {"OFFSCREEN_LIFE_DESCRIPTIONS"},
    "mind/affect.py": {"CAPACITY_DESCRIPTIONS"},
}


def _table_strings(tree, wanted):
    """Every string literal inside the named module-level assignments."""
    found = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {getattr(target, "id", None) for target in node.targets}
        if not (names & wanted):
            continue
        for inner in ast.walk(node.value):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                found.add(inner.value)
    return found


def _python_messages() -> set[str]:
    found = set()
    exception_names = {
        "HTTPException", "RuntimeError", "ValueError", "KeyError",
        "PermissionError", "FileNotFoundError",
    }
    for path in PY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        for value in _table_strings(tree, READER_FACING_TABLES.get(relative, set())):
            message = _message(value)
            if message:
                found.add(message)
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                name = getattr(node.exc.func, "id", None) \
                    or getattr(node.exc.func, "attr", None)
                if name in exception_names and node.exc.args:
                    candidates.append(node.exc.args[0])
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) \
                    or getattr(node.func, "attr", None)
                if name == "HTTPException":
                    if len(node.args) > 1:
                        candidates.append(node.args[1])
                    candidates.extend(
                        kw.value for kw in node.keywords if kw.arg == "detail")
                elif name == "JSONResponse":
                    # auth_routes.py returns its errors this way rather than
                    # raising, so every sign-in message was invisible here.
                    for argument in list(node.args) + [
                            kw.value for kw in node.keywords]:
                        if not isinstance(argument, ast.Dict):
                            continue
                        for key, value in zip(argument.keys, argument.values):
                            if (isinstance(key, ast.Constant)
                                    and key.value in ("detail", "error")):
                                candidates.append(value)
            for candidate in candidates:
                message = _message(_python_text(candidate) or "")
                if message:
                    found.add(message)
    return found


#: Where a JS string is a user-visible LABEL regardless of its casing: the
#: second half of a `["value", "label"]` option pair, and an `<option>`'s text.
OPTION_LABEL = (
    re.compile(r'\[\s*"[^"]*"\s*,\s*"([^"]+)"\s*\]'),
    re.compile(r'el\(\s*"option"[^)]*?\}\s*,\s*"([^"]+)"\s*\)'),
)


def _option_labels(source: str) -> set[str]:
    found = set()
    for pattern in OPTION_LABEL:
        for match in pattern.finditer(source):
            message = _message(match.group(1), label_position=True)
            if message:
                found.add(message)
    return found


def source_messages() -> list[str]:
    found = _python_messages()
    for path in HTML_FILES:
        parser = _HTMLMessages()
        parser.feed(path.read_text(encoding="utf-8"))
        found.update(parser.messages)
    for path in JS_FILES:
        source = path.read_text(encoding="utf-8")
        found.update(_option_labels(source))
        for raw in _javascript_strings(source):
            # Enough JS unescaping for authored UI strings. Keep template
            # placeholders verbatim so explicit t(`...`) calls can use them.
            value = (raw.replace(r"\n", "\n")
                     .replace(r"\t", "\t")
                     .replace(r"\r", "\r")
                     .replace(r"\/", "/")
                     .replace(r'\"', '"')
                     .replace(r"\'", "'")
                     .replace(r"\\", "\\"))
            message = _message(value)
            if message:
                found.add(message)
    return sorted(found, key=lambda item: (item.casefold(), item))


def catalog() -> dict[str, str]:
    return {"language.name": "English", **{
        message: message for message in source_messages()
    }}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = catalog()
    if args.check:
        actual = json.loads(UI_PATH.read_text(encoding="utf-8"))
        if actual != expected:
            print("English UI catalog is stale; run tools/extract_ui_catalog.py")
            return 1
        print(f"English UI catalog covers {len(expected) - 1} source messages.")
        return 0
    UI_PATH.write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(expected) - 1} source messages to {UI_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
