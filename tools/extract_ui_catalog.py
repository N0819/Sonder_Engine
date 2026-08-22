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
# Authenticated laboratories are development/evidence fixtures, not
# player-facing product surfaces. They are intentionally English-only and must
# not create false translation debt for installed language packs.
DEVELOPMENT_HTML_FILES = frozenset((
    "ui-next-lab.html",
    "ui-next-runtime.html",
))
DEVELOPMENT_JS_FILES = frozenset((
    "ui-next/lab.js",
    "ui-next/runtime-harness.js",
))
_REPLACEMENT_CATALOG_BLOCK = re.compile(
    r"UI_CATALOG_START.*?(.*?)\s*//\s*UI_CATALOG_END",
    re.DOTALL,
)
HTML_FILES = tuple(sorted(
    path for path in (ROOT / "static").glob("*.html")
    if path.name not in DEVELOPMENT_HTML_FILES
))
JS_FILES = tuple(sorted(
    path for path in (ROOT / "static" / "js").rglob("*.js")
    if path.relative_to(ROOT / "static" / "js").as_posix()
    not in DEVELOPMENT_JS_FILES
))
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


#: Past this, a candidate is far more likely to be a runaway regex capture
#: than authored copy, and is refused outright.
_CAPTURE_CEILING = 2000

#: Past this, a candidate is unusual enough to name in the run's output so a
#: maintainer can look at it -- but it is still published, because long help
#: text is copy a reader needs translated most.
_LONG_MESSAGE = 500

_LONG_MESSAGES: set[str] = set()


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
    if any(marker in value for marker in (
            " function ", " const ", " => ",
            "document.", "querySelector", "addEventListener", "return ",
            "/api/", "await ", " // ", "$(\"")):
        return None
    # A LENGTH ceiling used to stand here, at 500 characters, on the reasoning
    # that "real interface messages are deliberately concise". Measured
    # 2026-08-18 it rejected five strings and every one of them was interface
    # copy: the attire picker's explanation of why a garment covers regions,
    # the player-authority setting's account of what full authorship means, the
    # backdrop-continuity setting's account of what editing the first image
    # buys, and the repair model's account of shape-versus-content. Long help
    # text is the copy a reader most needs in their own language, and it was
    # the only copy structurally excluded from every pack.
    #
    # The ceiling was never the real guard anyway -- the markers above are.
    # It survives only as a WARNING, because a runaway regex capture is a real
    # failure mode and a silent 4KB blob in the catalog is worse than a noisy
    # one. Anything past 2,000 characters is far outside authored copy and is
    # still refused.
    if len(value) > _CAPTURE_CEILING:
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
    # Recorded LAST, so the report names only what is actually published. The
    # code guards above (the `;` count, `var(--`, the code markers) are what
    # rejects a runaway capture; length is not a guard here, it is a flag.
    if len(value) > _LONG_MESSAGE:
        _LONG_MESSAGES.add(value)
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
    # `FRIENDLY_STEP_LABELS` was named here too and has never been in this
    # file -- it is a table in `static/js/chat.js`, harvested by the ordinary
    # JS string sweep. A promise about a table that is not there is the same
    # shape as the one this comment block exists to prevent.
    "agents/runtime.py": {"STEP_LABELS"},
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

#: THE BROWSER HAS NO ANALOGUE OF `READER_FACING_TABLES`, DELIBERATELY.
#:
#: The rule above rejects a bare lowercase token with no space or punctuation.
#: Audit FRONTEND-23 read that as the bug -- "`episode` appears zero times in
#: `en/ui.json`" -- and it is not. Measured 2026-08-18, 688 distinct strings in
#: `static/js` are rejected by it, and 683 are CSS custom properties, MIME
#: types, event names, class names and route fragments. The other five are
#: members of six module-level tables (`MEM_CATS_FALLBACK`, `MEM_PROV_FALLBACK`,
#: `ATTIRE_REGIONS`, `EXTRA_PART_ASPECTS`, `LORE_INHERITANCE_MODES`,
#: `DEFAULT_LORE_LINK_TYPES`) whose elements ARE rendered as dropdown labels --
#: and every one of them is a stored enum value: `memories.category`,
#: `memories.provenance`, an attire region key, a lorebook `relation_type`.
#:
#: `Design.md` § Story and interface language packs states the rule those fall
#: under: "the stored protocol stays canonical English -- schema keys, enum
#: values, step ids and ledger vocabulary are never translated, which is what
#: lets one deterministic engine read objects written by any language."
#: `tools/project_check.py`'s `canonical_language_tokens` enforces it, and
#: translating these five is exactly what it refuses.
#:
#: So the filter is the rule, implemented. What IS wrong is one layer up and
#: not this tool's to fix: the interface shows a reader `alternate_version` and
#: `reference_only` in ENGLISH TOO. That is a missing label, not a missing
#: translation, and giving each enum an authored label with the enum as its
#: `value` is a browser change. Recorded in `docs/UNBUILT.md`.


#: `\uXXXX` and `\xXX` were NOT unescaped here, and the catalog key is what
#: `t()` looks up at runtime. So a source string written `"\u201cthe door
#: gives way\u201d"` was harvested with the six literal characters `\u201c` in
#: it, while the browser called `t()` with the real curly quote -- the key
#: could never match, and three of this catalog's longest help texts were
#: untranslatable in every pack while looking translated in the JSON. Found
#: 2026-08-18. Template placeholders stay verbatim so an explicit ``t(`...`)``
#: call can use them; a backslash escape does not, because the string the
#: browser passes to `t()` is the EVALUATED one and the key has to be it.
_JS_ESCAPES = (
    (r"\n", "\n"), (r"\t", "\t"), (r"\r", "\r"), (r"\/", "/"),
    (r'\"', '"'), (r"\'", "'"),
)
_JS_CODEPOINT = re.compile(
    r"\\u\{([0-9a-fA-F]+)\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})")


def _unescape_js(raw: str) -> str:
    """Enough JS unescaping for authored UI strings."""
    value = _JS_CODEPOINT.sub(
        lambda m: chr(int(next(g for g in m.groups() if g is not None), 16)),
        raw)
    for escape, literal in _JS_ESCAPES:
        value = value.replace(escape, literal)
    return value.replace("\\\\", "\\")


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
        relative = path.relative_to(ROOT / "static" / "js")
        if len(relative.parts) > 1:
            sources = _REPLACEMENT_CATALOG_BLOCK.findall(source)
        else:
            sources = (source,)
            found.update(_option_labels(source))
        for catalog_source in sources:
            for raw in _javascript_strings(catalog_source):
                message = _message(_unescape_js(raw))
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
    for message in sorted(_LONG_MESSAGES):
        print(f"  long ({len(message)} chars): {message[:80]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
