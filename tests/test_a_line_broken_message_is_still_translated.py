"""A UI message the page writes across lines, or with padding, is still found in the catalog.

The catalog's keys are whitespace-collapsed -- `extract_ui_catalog._message`
joins every run of whitespace into one space and trims -- while the translator
looked a string up exactly as the page built it. So a message with a line
break never matched although the ja pack holds it: the 🎧 button's two-line
tooltip, the lore generator's placeholder (frontend audit 2026-11-01,
frontend_lorebooks_editors F11; asked for by lane L15b). On a miss the
translator now asks once more with the whitespace collapsed, and gives the
original padding back.

Two things it must NOT do, both pinned below: collapse a string the catalog
only maps to itself (the English pack is all such entries, and the newline in
an English tooltip has to survive), or re-translate a string that is already
a translation.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "static" / "js" / "i18n-core.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

LORE = ("Describe the lore entries to generate.\n\n"
        "Example: Create entries for the capital's districts, "
        "government, defenses, major factions, and local customs.")
# Built exactly as ambience.js builds the 🎧 tooltip.
AMBIENCE = "Room ambience: on — “Hum”\nClick for sound options"

_HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const [, , core, en, ja, sources] = process.argv;
const ctx = vm.createContext({ Node: { ELEMENT_NODE: 1, TEXT_NODE: 3 } });
vm.runInContext(fs.readFileSync(core, "utf8"), ctx);
const out = {};
for (const [lang, path] of [["en", en], ["ja", ja]]) {
  const catalog = JSON.parse(fs.readFileSync(path, "utf8"));
  const rules = ctx.i18nCompileTemplates(catalog);
  out[lang] = JSON.parse(sources).map(source => ctx.i18nTranslate(catalog, rules, source));
}
process.stdout.write(JSON.stringify(out));
"""


def _translate(*sources: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="i18n-ws-") as tmp:
        harness = Path(tmp) / "harness.js"
        harness.write_text(_HARNESS, encoding="utf-8")
        run = subprocess.run(
            ["node", str(harness), str(CORE),
             str(ROOT / "language_packs" / "en" / "ui.json"),
             str(ROOT / "language_packs" / "ja" / "ui.json"),
             json.dumps(list(sources))],
            capture_output=True, text=True, check=True, timeout=60)
    return json.loads(run.stdout)


def test_a_message_written_across_lines_is_translated():
    got = _translate(LORE, AMBIENCE)
    lore, ambience = got["ja"]
    assert lore.startswith("生成するロアエントリを記述してください。")
    assert ambience.startswith("部屋の雰囲気：")
    assert ambience.endswith("サウンドオプションはこちらをクリック")


def test_a_message_the_catalog_maps_to_itself_keeps_its_line_breaks():
    got = _translate(LORE, AMBIENCE)
    assert got["en"] == [LORE, AMBIENCE]


def test_padding_comes_back_around_the_translation():
    got = _translate(" Delete", "Delete\n")
    assert got["ja"] == [" 削除", "削除\n"]
    assert got["en"] == [" Delete", "Delete\n"]


def test_a_translation_with_padding_is_not_translated_again():
    got = _translate(" 削除 ", "地図を表示できません:  boom")
    assert got["ja"][0] == " 削除 "


def test_a_value_written_across_lines_is_never_collapsed_into_a_template():
    """Whitespace is collapsed only where it is the catalog's own text. A
    template's capture is what the page interpolated -- here an error with a
    traceback -- and no placeholder matches across a line; the retry keeps
    that rule rather than quietly flattening the message."""
    source = "Character generation failed: boom\nTraceback (most recent call last)"
    got = _translate(source, "Character generation failed:  boom")
    assert got["ja"][0] == source
    # A single line needs no retry: the template takes the value as written,
    # its leading space included.
    assert got["ja"][1] == "キャラクターの生成に失敗しました： boom"
