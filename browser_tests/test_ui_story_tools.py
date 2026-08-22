"""Real-browser contracts for the WP-05 Story Tool platform."""

from __future__ import annotations

import json
import re

from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [{"id": 1, "name": "The Lantern Archive"}],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


def _story() -> dict:
    return {
        "chat": {"id": 1, "name": "The Lantern Archive"},
        "frames": [{"id": None, "label": "Present"}],
        "turns": [],
        "cast": [],
        "dialogue_colors": {},
    }


def _open(page: Page, ui_base_url: str, *, width: int = 1280) -> None:
    page.set_viewport_size({"width": width, "height": 800 if width > 700 else 844})
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP)),
    )
    page.route(
        "**/api/chats/1",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(_story())),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/play?chat=1")
    assert response is not None and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    expect(page.get_by_role("heading", name="The Lantern Archive", level=2)).to_be_visible()


def test_story_tool_registry_and_route_parser_are_exact(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const registry = await import(
            `${base}/static/js/ui-next/story-tools-registry.js?release=wp05.1`
          );
          const router = await import(`${base}/static/js/ui-next/router.js?release=wp05.1`);
          const route = router.parseHashRoute(
            "#/play/story-tools?chat=17&tool=conditions"
          );
          return {
            ids: registry.STORY_TOOL_IDS,
            route: {
              valid: route.valid,
              destination: route.destination,
              segments: route.segments,
              query: route.query,
              canonicalHash: route.canonicalHash,
            },
            missing: registry.resolveStoryTool("missing").id,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "ids": [
            "cast",
            "world",
            "style",
            "dialogue",
            "attire",
            "backdrops",
            "ambience",
            "conditions",
            "frames",
            "multiplayer",
        ],
        "route": {
            "valid": True,
            "destination": "play",
            "segments": ["story-tools"],
            "query": {"chat": "17", "tool": "conditions"},
            "canonicalHash": "#/play/story-tools?chat=17&tool=conditions",
        },
        "missing": "cast",
    }


def test_desktop_story_tools_select_route_without_resetting_play_state(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    composer = page.get_by_role("textbox", name="What do you do or say?")
    composer.fill("A private draft")
    transcript = page.locator("[data-play-transcript]")
    before = transcript.evaluate("node => node.scrollTop")

    inspector = page.get_by_role("complementary", name="Story tools")
    expect(inspector.locator("[data-story-tool-list] button")).to_have_count(10)
    inspector.get_by_role("button", name="World", exact=True).click()

    expect(page).to_have_url(re.compile(r"#/play/story-tools\?chat=1&tool=world$"))
    expect(inspector.get_by_role("heading", name="World", exact=True)).to_be_visible()
    expect(composer).to_have_value("A private draft")
    assert transcript.evaluate("node => node.scrollTop") == before


def test_mobile_story_tools_are_staged_and_back_owned(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url, width=390)
    opener = page.get_by_role("button", name="Open context panel")
    opener.click()
    sheet = page.get_by_role("dialog", name="Story tools")
    expect(sheet).to_be_visible()
    expect(sheet.locator("[data-story-tool-list] button")).to_have_count(10)

    sheet.get_by_role("button", name="Conditions", exact=True).click()
    expect(sheet.get_by_role("heading", name="Conditions", exact=True)).to_be_visible()
    expect(page).to_have_url(re.compile(r"tool=conditions"))

    page.go_back()
    expect(sheet).to_be_hidden()
    expect(opener).to_be_focused()

