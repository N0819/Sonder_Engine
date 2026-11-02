"""A sentence the page builds around a value is looked up whole, with the value filled in after.

`"literal " + variable` is a runtime string no catalog key can equal: the
extractor harvests only the literal fragment, and `t()` sees only the joined
result (frontend audit 2026-11-01, frontend_core F11). Probed against the ja
pack, every one of these stayed English -- "Hinami is deciding what to do",
"12 memories recalled", "Turn 12", "Map unavailable: …", "NSFW: ON" (while
"NSFW: OFF" translated, so the button changed language when pressed) -- and
"Rebuilding Hinami's earlier eras" came out half-translated as
"Hinami's earlier erasを再構築中". The catalog's own "is deciding what to do"
entry could never fire.

Each is now translated BEFORE anything is joined to it -- one `{var}` key,
the value interpolated after the lookup, or an existing key with the value
appended -- so a name is never looked up. A character's step label is rebuilt
from its KEY and name for the same reason:
the server formats "Character · <name>" from a template the catalog holds
unformatted, so it was translated only by accident, through an unrelated
settings.js template.

The new keys reach the language packs through `tools/extract_ui_catalog.py`;
these pins hold the composition itself.
"""

from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "static" / "js"
SOURCES = {name: (JS / name).read_text(encoding="utf-8")
           for name in ("chat.js", "app.js", "components.js", "utils.js")}

#: (file, the joined string no key could equal, what replaced it). Two forms,
#: both translating BEFORE anything is joined: a sentence whose value sits
#: inside it is one `{var}` key; a complete phrase with a value after it (or a
#: name before it, where the catalog's entry was written for that) keeps its
#: existing key and has the value appended -- "ターン 12", "Hinami 何をすべきか".
CASES = [
    ("chat.js", '" is deciding what to do"', 't("is deciding what to do")'),
    ("chat.js", '(mems.length === 1 ? "memory" : "memories")', '"{n} memories recalled"'),
    ("chat.js", '"Turn " + t', 't("Turn") + " " + turnIdx'),
    ("chat.js", '"Summary through turn "', '"Summary through turn {n}"'),
    ("chat.js", '"last: turn " +', 't("last: turn") + " " + r.last_interaction_turn'),
    ("chat.js", '"last shift triggered by event " +', 't("last shift triggered by event {event}"'),
    ("chat.js", '" hasn\'t formed any tracked opinions', 't("hasn\'t formed any tracked opinions of anyone yet.")'),
    ("chat.js", '"How " + p.name', 't("How {name} currently feels'),
    ("chat.js", '"Adds to " + p.name', 't("Adds to {name}\'s existing memories'),
    ("chat.js", '"Source: " + d.source', 't("Source:") + " " + d.source'),
    ("chat.js", '"Reading " + f.name', 't("Reading {file}…"'),
    ("chat.js", '"Loaded " + f.name', 't("Loaded {file} ✓"'),
    ("chat.js", '"⇉ ran concurrently with " +', 't("⇉ ran concurrently with {steps}"'),
    ("chat.js", '"Map unavailable: " +', 't("Map unavailable:") + " " +'),
    ("chat.js", '"Load error: " +', 't("Load error:") + " " +'),
    ("chat.js", '"Search error: " +', 't("Search error:") + " " +'),
    ("chat.js", '"Error: " + e.message', 't("Error:") + " " + e.message'),
    ("chat.js", '"  (stale)"', 't("(stale)")'),
    ("chat.js", '${name + "\'s earlier eras"}', 't("Rebuilding {name}\'s earlier eras"'),
    ("chat.js", '${name + "\'s memory"}', 't("Consolidating {name}\'s memory"'),
    ("app.js", '"NSFW: " + (S.nsfw ? "ON" : "OFF")', '"NSFW: ON"'),
    ("components.js", '(attachBox.checked ? "worn at: " : "covers: ")', '"worn at: {regions}"'),
    ("components.js", 'region + " zones still covered:"', 'region + " " + t("zones still covered:")'),
    ("utils.js", '"Could not reach the server. "\n', 't("Could not reach the server.") + " "'),
]


@pytest.mark.parametrize("name,joined,composed", CASES,
                         ids=[case[2][:40] for case in CASES])
def test_the_sentence_is_one_catalog_key(name, joined, composed):
    source = SOURCES[name]
    assert joined not in source, f"{name} still joins {joined!r}"
    assert composed in source, f"{name} lacks {composed!r}"


def test_a_characters_step_is_labelled_from_its_key():
    chat = SOURCES["chat.js"]
    helper = chat[chat.index("function stepLabel("):]
    helper = helper[:helper.index("\n}\n")]
    assert 'String(key).startsWith("character:")' in helper
    assert 't("Character · {name}", { name })' in helper
    # Every place a step's label is shown goes through it.
    assert '(parallel ? "⇉ " : "▸ ") + stepLabel(key, label)' in chat
    assert 'h.textContent = "✓ " + stepLabel(ev.key, ev.label);' in chat
    assert "stepLabel(s.key, s.label)" in chat
