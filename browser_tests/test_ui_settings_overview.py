"""Focused browser contracts for single-method Settings navigation."""

from __future__ import annotations

import json
import re

from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [
        {"id": 7, "name": "Anthropic", "kind": "anthropic", "has_key": True},
        {"id": 8, "name": "Local", "kind": "ollama", "has_key": False},
    ],
    "agent_models": {"default": {"provider": 7, "model": "claude-sonnet-4-5"}},
    "language_packs": [],
    "extensions": [
        {"id": "campaign", "name": "Campaign (demo)", "enabled": True},
        {"id": "overlay", "name": "Overlay (demo)", "enabled": False},
    ],
    "extension_errors": [],
    "extension_lanes": [],
}


def _open_navigation(
    page: Page,
    ui_base_url: str,
    *,
    width: int = 1440,
    height: int = 900,
    bootstrap: dict[str, object] | None = None,
) -> list[str]:
    calls: list[str] = []
    page.set_viewport_size({"width": width, "height": height})
    page.on(
        "request",
        lambda request: calls.append(request.url) if "/api/" in request.url else None,
    )
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(bootstrap or BOOTSTRAP)
        ),
    )
    if page.url.startswith(ui_base_url):
        page.goto("about:blank")
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/settings")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )
    return calls


def test_settings_root_projects_one_grouped_navigation_and_theme_panel(
    page: Page, ui_base_url: str
) -> None:
    calls = _open_navigation(page, ui_base_url)

    navigation = page.get_by_role("navigation", name="Settings categories")
    expect(navigation.locator("[data-settings-navigation-group]")).to_have_count(4)
    expect(navigation.locator("[data-settings-navigation-row]")).to_have_count(13)
    expect(page.locator("[data-settings-overview]")).to_have_count(0)
    expect(page.get_by_role("link", name="Settings overview")).to_have_count(0)
    expect(navigation.get_by_role("link", name="Theme", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(page.get_by_role("heading", name="Theme", level=2)).to_be_visible()
    expect(navigation.get_by_role("link", name="AI Connections")).to_contain_text(
        "2 providers · claude-sonnet-4-5"
    )
    assert not any("/api/extensions" in call or "/api/providers" in call for call in calls)


def test_navigation_rows_open_real_panels_without_a_second_launcher(
    page: Page, ui_base_url: str
) -> None:
    _open_navigation(page, ui_base_url)
    navigation = page.get_by_role("navigation", name="Settings categories")

    turn_details = navigation.locator('[data-settings-navigation-row="turn-details"]')
    expect(turn_details).to_have_attribute("aria-disabled", "true")
    expect(turn_details).to_contain_text("Open a Story first")

    navigation.get_by_role("link", name="Model assignments").click()
    expect(page).to_have_url(
        re.compile(r"#/settings/ai-connections\?control=models$")
    )
    expect(page.get_by_role("heading", name="Model assignments", level=2)).to_be_visible()
    expect(page.locator("[data-settings-launcher]")).to_have_count(0)


def test_global_settings_destination_and_shortcut_open_theme_detail(
    page: Page, ui_base_url: str
) -> None:
    _open_navigation(page, ui_base_url)
    page.locator('[data-core-destination="play"]').click()
    expect(page).to_have_url(re.compile(r"#/play$"))
    page.locator('[data-core-destination="settings"]').click()
    expect(page).to_have_url(re.compile(r"#/settings$"))
    expect(page.get_by_role("heading", name="Theme", level=2)).to_be_visible()

    page.locator('[data-core-destination="play"]').click()
    page.keyboard.press("Control+,")
    expect(page).to_have_url(re.compile(r"#/settings$"))
    expect(page.get_by_role("heading", name="Theme", level=2)).to_be_visible()


def test_settings_search_opens_the_matching_real_panel(
    page: Page, ui_base_url: str
) -> None:
    _open_navigation(page, ui_base_url, height=620)

    page.get_by_role("searchbox", name="Search settings").fill("provider credentials")
    page.get_by_role("button", name=re.compile("Provider credentials")).click()
    expect(page).to_have_url(
        re.compile(r"#/settings/ai-connections\?control=providers$")
    )
    expect(page.get_by_role("heading", name="AI Connections", level=2)).to_be_visible()
    expect(page.get_by_role("button", name="Add provider")).to_be_focused()


def test_settings_navigation_has_one_scroll_owner_and_no_outer_overflow(
    page: Page, ui_base_url: str
) -> None:
    for width, height in (
        (1440, 900),
        (1440, 720),
        (1024, 600),
        (390, 844),
        (844, 390),
    ):
        _open_navigation(page, ui_base_url, width=width, height=height)
        geometry = page.evaluate(
            """() => {
              const navigation = document.querySelector('[data-settings-categories]');
              const content = document.querySelector('[data-settings-content]');
              const visibleTargets = [...navigation.querySelectorAll('a[href], button:not(:disabled)')]
                .filter(node => node.getClientRects().length);
              return {
                documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                navigationOverflowY: getComputedStyle(navigation).overflowY,
                contentOverflowY: getComputedStyle(content).overflowY,
                targetHeights: visibleTargets.map(node => node.getBoundingClientRect().height),
                workspaceScroll: document.querySelector('.ui-shell__workspace').scrollTop,
                documentScroll: document.documentElement.scrollTop,
                shellTop: document.querySelector('[data-settings-shell]').getBoundingClientRect().top,
              };
            }"""
        )
        assert geometry["documentOverflow"] <= 1, (width, height, geometry)
        assert geometry["navigationOverflowY"] not in {"auto", "scroll"}, geometry
        assert geometry["contentOverflowY"] == "auto", geometry
        minimum_target = 36 if width >= 1100 else 44
        assert min(geometry["targetHeights"]) >= minimum_target, geometry
        assert geometry["workspaceScroll"] == 0, geometry
        assert geometry["documentScroll"] == 0, geometry
        assert abs(geometry["shellTop"]) <= 1, geometry
