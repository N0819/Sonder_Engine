"""Names and story text are never looked up in the UI catalog.

`el()` ran every string child and every title/aria-label through `t()` before
the node existed, and the mutation observer translated whatever the page
added outside a `translate="no"` subtree (frontend audit 2026-11-01,
frontend_core F8). So any story, character, persona or speaker name, memory
gist or key phrase that happened to equal a catalog key was shown translated
-- a story named "Tavern" was listed and headed as 酒場 under the ja pack, and
a key phrase "Map" read 地図. A name inside a composed label ("Rename Tavern")
was caught by the template's capture translation the same way.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP

JA = {
    "Tavern": "酒場", "Map": "地図", "Rename": "名前を変更", "Close": "閉じる",
    "Rename {name}": "{name} の名前を変更", "Open {name}": "{name} を開く",
    "Rename ${chat.name}": "${chat.name} の名前を変更",
    "Open ${chat.name}": "${chat.name} を開く",
    "No story selected": "物語が選択されていません",
}


def _harness(page: Page) -> None:
    """`t()` and `el()` as the SPA loads them, under a small ja catalog."""
    from pathlib import Path
    js = Path(__file__).resolve().parents[1] / "static" / "js"
    core = (js / "i18n-core.js").read_text(encoding="utf-8")
    utils = (js / "utils.js").read_text(encoding="utf-8")
    utils = utils[utils.index("const S = {"):utils.index("function watchUILanguage(")]
    components = (js / "components.js").read_text(encoding="utf-8")
    components = components[components.index("function txt("):components.index("// ---- Modal ----")]
    page.set_content("<!doctype html><body></body>")
    page.add_script_tag(content=core)
    page.add_script_tag(content=utils + "\n" + components)
    page.evaluate("(c) => { S.uiCatalog = c; S.uiTemplateRules = null; }", JA)


def test_an_opted_out_element_keeps_its_attributes_as_written(page: Page) -> None:
    _harness(page)
    got = page.evaluate("""() => {
        const name = el("span", {translate: "no", title: "Tavern"}, "Tavern");
        const chrome = el("button", {title: "Close"}, "Close");
        return {nameTitle: name.title, nameText: name.textContent,
                chromeTitle: chrome.title, chromeText: chrome.textContent};
    }""")
    assert got == {"nameTitle": "Tavern", "nameText": "Tavern",
                   "chromeTitle": "閉じる", "chromeText": "閉じる"}


def _spa(page: Page, ui_base_url: str) -> None:
    boot = dict(BOOTSTRAP, chats=[{"id": 5, "name": "Tavern"}], ui_messages=JA,
                ui_language="ja")
    story = {"chat": {"id": 5, "name": "Tavern"}, "participants": [],
             "turns": [{"id": 50, "idx": 0, "player_input": "", "prose": "Smoke and dice.",
                        "stale": False, "frame_id": None}],
             "lorebook": None, "lorebooks": [], "frames": []}

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        body = (boot if path == "/api/bootstrap" else story if path == "/api/chats/5"
                else {"enabled": False, "bodies": []} if path.endswith("/vitals") else {})
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", handle)
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof S !== 'undefined' && !!S.boot")


def test_a_story_named_like_a_label_is_listed_and_headed_by_its_name(
        page: Page, ui_base_url: str) -> None:
    _spa(page, ui_base_url)
    label = page.locator("#sidelist .story-item .item-label")
    expect(label).to_have_text("Tavern")
    expect(label).to_have_attribute("title", "Tavern")
    # The words around the name are translated; the name is not.
    rename = page.locator("#sidelist .story-item button.story-action").first
    expect(rename).to_have_attribute("aria-label", "Tavern の名前を変更")
    expect(rename).to_have_attribute("title", "名前を変更")
    expect(page.locator("#sidelist .story-item")).to_have_attribute("aria-label", "Tavern を開く")
    # With no story open, the header is the page's own words, translated.
    expect(page.locator("#chatname")).to_have_text("物語が選択されていません")

    page.locator("#sidelist .story-item").click()
    expect(page.locator("#msgs")).to_contain_text("Smoke and dice.")
    expect(page.locator("#chatname")).to_have_text("Tavern")
    expect(page.locator("#chatname")).to_have_attribute("title", "Tavern")
