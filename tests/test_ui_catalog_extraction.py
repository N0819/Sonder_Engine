"""What `tools/extract_ui_catalog.py` may harvest, and what it must not.

The catalog key IS the runtime lookup: `utils.t(source)` reads
`S.uiCatalog[source]`, so a key that differs from the string the browser
actually passes can never match, however well it is translated. Two failures of
that shape landed together, in opposite directions.

TOO LITTLE. A `len(value) > 500` cutoff sat at the top of `_message`, on the
reasoning that "real interface messages are deliberately concise". Measured
2026-08-18 it rejected five strings and every one was interface copy -- the
attire picker's account of why a garment covers regions, the player-authority
setting's account of what full authorship means, the backdrop-continuity
setting's, and the repair model's. Long help text is the copy a reader most
needs in their own language, and it was the only copy structurally excluded
from every pack. The code markers beside it were always the real guard.

WRONG. `\\uXXXX` escapes were not unescaped, so a source string written
`"\\u201cthe door gives way\\u201d"` was harvested with six literal characters
where the browser has one curly quote. The key could not match at runtime.

And one refutation, pinned here because the shape recurs: audit FRONTEND-23
read `_message`'s `[a-z0-9_.:/-]+` rejection as a bug because "`episode`
appears zero times in `en/ui.json`". It is not a bug. `episode` is a stored
`memories.category` value, and `Design.md` states the rule: the stored protocol
stays canonical English -- schema keys, enum values, step ids and ledger
vocabulary are never translated, which is what lets one deterministic engine
read objects written by any language.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "_extract_ui_catalog", ROOT / "tools" / "extract_ui_catalog.py")
extract = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("_extract_ui_catalog", extract)
_spec.loader.exec_module(extract)


LONG_HELP = (
    "Who decides what your declaration achieved. Under full authorship — the "
    "default — writing “the door gives way” makes it so, and the engine "
    "encodes it. " + ("Hard mode keeps your words exactly as you wrote them. " * 8)
)


def test_long_help_text_is_published():
    assert len(LONG_HELP) > 500
    assert extract._message(LONG_HELP) == " ".join(LONG_HELP.split())


def test_a_runaway_capture_is_still_refused():
    # The ceiling that remains is a capture guard, not a length preference.
    assert extract._message("A sentence. " * 400) is None


def test_a_javascript_unicode_escape_becomes_the_character_the_browser_sees():
    assert extract._unescape_js(r"writing “the door gives way”") == (
        "writing “the door gives way”")
    assert extract._unescape_js(r"a \x2D b") == "a - b"
    assert extract._unescape_js(r"\u{1F600}") == "\U0001F600"


def test_placeholders_survive_unescaping():
    # An explicit t(`...`) call keeps its own template, so the placeholder has
    # to reach the catalog verbatim.
    assert extract._unescape_js(r"${count} of ${total}") == "${count} of ${total}"


def test_a_stored_enum_value_is_not_interface_copy():
    for enum in ("episode", "witnessed", "torso", "reference_only",
                 "alternate_version"):
        assert extract._message(enum) is None, enum


def test_an_enum_in_label_position_is_still_admitted():
    # The escape hatch stays open: a string the extractor can SEE sitting in a
    # dropdown's label slot is judged as copy, which is what `label_position`
    # is for.
    assert extract._message("terse / natural / chatty", label_position=True)


def test_every_named_reader_facing_table_exists_in_its_module():
    # `FRIENDLY_STEP_LABELS` was named under `agents/runtime.py` and has never
    # been in that file -- it is a table in `static/js/chat.js`. A promise
    # about a table that is not there is the failure this registry exists to
    # prevent.
    for relative, names in extract.READER_FACING_TABLES.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        for name in names:
            assert f"\n{name} = " in source, (relative, name)
