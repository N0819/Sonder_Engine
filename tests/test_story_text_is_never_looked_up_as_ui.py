"""Names and story text reach the page without passing through the UI catalog.

`el()` translated every title/aria-label before the element existed -- even on
an element that opted out with `translate: "no"` -- and the observer
translated any text it saw outside such a subtree (frontend audit 2026-11-01,
frontend_core F8). A story named "Tavern" was listed and headed as 酒場 under
the ja pack, a persona "Player" read プレイヤー, a memory key phrase "Map"
read 地図. Driven in a browser in
`browser_tests/test_story_text_is_never_looked_up_as_ui.py`; these are the
default-tier pins of each surface the audit named.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
COMPONENTS = (STATIC / "js" / "components.js").read_text(encoding="utf-8")
APP = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
CHAT = (STATIC / "js" / "chat.js").read_text(encoding="utf-8")
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    at = source.index(start)
    return source[at:source.index(end, at)]


def test_an_opted_out_element_keeps_its_chrome_attributes_as_written():
    body = _between(COMPONENTS, "function el(", "// ---- Modal ----")
    assert 'const optedOut = attrs.translate === "no"' in body
    assert '!optedOut && ["title", "aria-label", "placeholder", "alt"].includes(k)' in body


def test_the_story_list_shows_names_as_written():
    side = _between(APP, "function renderChatSidebar(", "function failedSetupRow(")
    assert 'class: "item-label",\n      translate: "no",' in side
    for label in ("Open {name}", "Rename {name}", "Export {name}", "Delete {name}",
                  "Actions for {name}"):
        assert f't("{label}", {{ name: chat.name }})' in side, label
    # No name is composed into a label the catalog would look up whole.
    assert "${chat.name}" not in side


def test_character_and_persona_lists_show_names_as_written():
    for name, who in (("renderCharacterSidebar", "character"),
                      ("renderPersonaSidebar", "persona")):
        side = _between(APP, f"function {name}(", "\n}\n")
        assert f'el("span", {{ class: "item-label", translate: "no", title: {who}.name }}' in side
        assert "${" + who + ".name}" not in side, name


def test_the_header_holds_the_story_name_outside_the_catalog():
    assert '<span id="chatname" translate="no"' in INDEX
    render = _between(CHAT, "function renderChat()", "function beginStory()")
    assert '$("#chatname").textContent = t("No story selected");' in render


def test_memory_and_relationship_text_is_story_text():
    summary = _between(CHAT, "function renderMemorySummary()", "function sortedMems(")
    assert 'class: "memory-summary-text", translate: "no"' in summary
    assert 'el("span", { class: "chip", translate: "no" }, p)' in summary
    assert 'translate: "no",\n                style: "margin-top:4px"' in summary
    card = _between(CHAT, "function memoryCard(m)", "\n}\n")
    assert 'class: "memory-gist-line",\n        translate: "no",' in card
    rel = _between(CHAT, "async function relationshipModal(", "// ---- Memory browser ----")
    assert 'el("b", { translate: "no" }, name.replace(/_/g, " "))' in rel


def test_a_speaker_tooltip_and_a_frame_label_are_story_text():
    assert 'el("span", { class: "said", translate: "no", title: span.speaker })' in CHAT
    bar = _between(CHAT, "function renderFrameBar()", "function switchFrame(")
    assert 'translate: "no",' in bar
    assert 't("Present")' in bar
