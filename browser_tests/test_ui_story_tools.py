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
            `${base}/static/js/ui-next/story-tools-registry.js?release=alpha98-ui10-0415f377b12f`
          );
          const router = await import(`${base}/static/js/ui-next/router.js?release=alpha98-ui10-0415f377b12f`);
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
    target_heights = sheet.locator("button:visible").evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect().height)"
    )
    assert target_heights and min(target_heights) >= 44, target_heights

    page.go_back()
    expect(sheet).to_be_hidden()
    expect(opener).to_be_focused()


def test_story_tools_modes_change_information_density_and_persist(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    inspector = page.get_by_role("complementary", name="Story tools")
    resize = inspector.get_by_role("button", name="Resize context panel")
    first = inspector.locator("[data-story-tool='cast']")

    expect(page.locator("html")).to_have_attribute("data-inspector-size", "expanded")
    expect(first.locator(".ui-story-tools__label")).to_be_visible()
    expect(first.locator(".ui-story-tools__detail")).to_be_visible()

    resize.click()
    expect(page.locator("html")).to_have_attribute("data-inspector-size", "compact")
    expect(first.locator(".ui-story-tools__label")).to_be_visible()
    expect(first.locator(".ui-story-tools__detail")).to_be_hidden()

    resize.click()
    expect(page.locator("html")).to_have_attribute("data-inspector-size", "rail")
    expect(first.locator(".ui-story-tools__label")).to_be_hidden()
    assert first.evaluate("node => node.getBoundingClientRect().width") <= 72
    assert first.get_attribute("title") == "Cast"

    page.reload()
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    expect(page.locator("html")).to_have_attribute("data-inspector-size", "rail")


def test_story_tool_detail_replaces_list_and_uses_distinct_svg_icons(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    inspector = page.get_by_role("complementary", name="Story tools")
    hrefs = {
        tool: inspector.locator(f"[data-story-tool='{tool}'] use").first.get_attribute("href")
        for tool in ("conditions", "frames", "multiplayer")
    }
    assert hrefs == {
        "conditions": "/static/assets/icons/sonder-icons.svg?release=alpha98-ui10-0415f377b12f#icon-conditions",
        "frames": "/static/assets/icons/sonder-icons.svg?release=alpha98-ui10-0415f377b12f#icon-frames",
        "multiplayer": "/static/assets/icons/sonder-icons.svg?release=alpha98-ui10-0415f377b12f#icon-multiplayer",
    }
    assert inspector.locator(
        "[data-story-tool='cast'] > .ui-icon:last-child use"
    ).get_attribute("href").endswith("#icon-chevron-right")

    inspector.get_by_role("button", name="World", exact=True).click()
    expect(inspector.locator("[data-story-tool-list]")).to_be_visible()
    expect(inspector.locator("[data-story-tool='cast'] .ui-story-tools__label")).to_be_hidden()
    expect(inspector.get_by_role("button", name="All tools")).to_be_visible()
    panel = inspector.locator("[data-story-tool-panel]")
    geometry = panel.evaluate(
        "node => ({ top: node.getBoundingClientRect().top, bottom: node.getBoundingClientRect().bottom, viewport: innerHeight })"
    )
    assert geometry["top"] < geometry["viewport"]
    inspector.get_by_role("button", name="All tools").click()
    expect(inspector.locator("[data-story-tool-list]")).to_be_visible()


def test_dialogue_tool_owns_charter_summary_and_diagnostics(
    page: Page, ui_base_url: str
) -> None:
    page.route("**/api/chats/1/dialogue_config", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({
            "style": "natural", "min_lines": 0, "max_lines": 3, "variance": 0.2,
            "autonomy": 50, "initial_parallel_reactors": 1,
            "promote_after_addressed": 2, "max_offscreen_actors": 1,
            "offscreen_life": "inert", "offscreen_life_levels": ["inert"],
        }),
    ))
    page.route("**/api/chats/1/background_config", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({"scene_life": "off", "max_managed": 6, "max_reactors": 1}),
    ))
    page.route("**/api/chats/1/living_world", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({"living_world": {}, "approaches": []}),
    ))
    page.route("**/api/chats/1/charters", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({
            "charters": {"items": {"archive": {"name": "Lantern Archive", "bodies": {"keeper": {}}}}},
            "character_history_routes": {"7": {"mode": "resident"}},
            "character_journey_histories": {},
            "warnings": ["One post has no room."],
        }),
    ))
    page.route("**/api/chats/1/charters/diagnostics", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({"beliefs": 2, "obligations": ["Keep the lamps lit"]}),
    ))
    page.route("**/api/chats/1/lorebooks", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({"lorebooks": []}),
    ))
    _open(page, ui_base_url)
    inspector = page.get_by_role("complementary", name="Story tools")
    inspector.get_by_role("button", name="Dialogue", exact=True).click()
    expect(inspector.get_by_role("heading", name="Institutions and upkeep")).to_be_visible()
    expect(inspector.get_by_text("1 institution · 1 resident body · 1 Character history route", exact=True)).to_be_visible()
    expect(inspector.get_by_text("One post has no room.", exact=True)).to_be_visible()
    inspector.get_by_text("Load Charter diagnostics", exact=True).click()
    expect(inspector.get_by_text("Keep the lamps lit", exact=False)).to_be_visible()

