"""Focused browser contracts for the grouped Settings overview."""

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


def _open_overview(
    page: Page,
    ui_base_url: str,
    *,
    width: int = 1440,
    height: int = 900,
    bootstrap: dict[str, object] | None = None,
) -> list[str]:
    calls: list[str] = []
    page.set_viewport_size({"width": width, "height": height})
    page.on("request", lambda request: calls.append(request.url) if "/api/" in request.url else None)
    page.add_init_script(
        """
        localStorage.setItem('sonder.ui-next', JSON.stringify({
          version: 2,
          appearance: {theme: 'modern-slate', proseSize: '19', density: 'compact', effects: 'reduced'},
          navigation: {},
          panes: {atmosphere: {muted: true, volume: 0.4, chime: false}},
          drafts: {}
        }));
        localStorage.setItem('sonder.ui.next.theme.v1', 'modern-slate');
        localStorage.setItem('sonder.ui.next.prose.v1', '19');
        localStorage.setItem('sonder.ui.next.effects.v1', 'reduced');
        localStorage.setItem('sonder.ui.next.accessibility.v1', JSON.stringify({
          mode: false, strongFocus: true, reducedMotion: true
        }));
        """
    )

    def bootstrap_route(route) -> None:
        route.fulfill(content_type="application/json", body=json.dumps(bootstrap or BOOTSTRAP))

    page.route("**/api/bootstrap", bootstrap_route)
    if page.url.startswith(ui_base_url):
        page.goto("about:blank")
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/settings")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )
    return calls


def test_overview_projects_owned_state_without_settings_side_effects(
    page: Page, ui_base_url: str
) -> None:
    calls = _open_overview(page, ui_base_url)

    expect(page.get_by_role("heading", name="Sonder preferences", level=1)).to_be_visible()
    groups = page.locator("[data-settings-overview-group]")
    expect(groups).to_have_count(4)
    assert groups.locator("h2").all_text_contents() == [
        "Connections", "Appearance", "Story & host", "Advanced"
    ]
    rows = page.locator("[data-settings-overview-row]")
    expect(rows).to_have_count(13)
    expect(page.get_by_role("link", name="AI Connections")).to_have_attribute(
        "href", "#/settings/ai-connections"
    )
    expect(page.get_by_text("2 providers · claude-sonnet-4-5", exact=True)).to_be_visible()
    expect(page.get_by_text("Modern Slate", exact=True)).to_be_visible()
    expect(page.get_by_text("Large · Compact", exact=True)).to_be_visible()
    expect(page.get_by_text("Reduced effects · Sound muted", exact=True)).to_be_visible()
    expect(page.get_by_text("2 accessibility overrides", exact=True)).to_be_visible()
    expect(page.get_by_text("1 enabled · 2 installed", exact=True)).to_be_visible()
    assert not any("/api/extensions" in call or "/api/providers" in call for call in calls)


def test_overview_rows_are_single_links_and_turn_details_is_unavailable_without_story(
    page: Page, ui_base_url: str
) -> None:
    _open_overview(page, ui_base_url)

    for row in page.locator("[data-settings-overview-row]").all():
        assert row.locator("button, input, select, textarea").count() == 0
    unavailable = page.locator('[data-settings-overview-row="turn-details"]')
    expect(unavailable).to_have_attribute("aria-disabled", "true")
    expect(unavailable).to_contain_text("Open a Story first")
    assert unavailable.get_attribute("tabindex") is None
    assert unavailable.get_attribute("href") is None
    assert page.locator("[data-settings-categories]").count() == 0

    page.get_by_role("link", name="Theme").press("Enter")
    expect(page).to_have_url(re.compile(r"#/settings/experience\?control=themes$"))
    expect(page.get_by_role("navigation", name="Settings categories")).to_be_visible()
    expect(page.get_by_role("link", name="Settings overview")).to_be_visible()

    page.get_by_role("link", name="Settings overview").click()
    page.get_by_role("link", name="Model assignments").click()
    expect(page).to_have_url(
        re.compile(r"#/settings/ai-connections\?control=models$")
    )
    assignments = page.get_by_text("Advanced model assignments", exact=True)
    expect(assignments).to_be_focused()
    expect(assignments.locator("xpath=ancestor::details")).to_have_attribute("open", "")


def test_global_settings_destination_and_shortcut_open_the_overview(
    page: Page, ui_base_url: str
) -> None:
    _open_overview(page, ui_base_url)
    page.locator('[data-core-destination="play"]').click()
    expect(page).to_have_url(re.compile(r"#/play$"))
    page.locator('[data-core-destination="settings"]').click()
    expect(page).to_have_url(re.compile(r"#/settings$"))
    expect(page.locator("[data-settings-overview]")).to_be_visible()

    page.locator('[data-core-destination="play"]').click()
    page.keyboard.press("Control+,")
    expect(page).to_have_url(re.compile(r"#/settings$"))
    expect(page.locator("[data-settings-overview]")).to_be_visible()


def test_overview_search_and_back_restore_the_launching_row(
    page: Page, ui_base_url: str
) -> None:
    _open_overview(page, ui_base_url, height=620)
    content = page.locator("[data-settings-content]")
    content.evaluate("node => { node.scrollTop = 420; }")
    launcher = page.get_by_role("link", name="Story imports & backups")
    launcher.focus()
    launcher.press("Enter")
    expect(page).to_have_url(re.compile(r"#/library/stories$"))
    page.go_back()
    expect(page).to_have_url(re.compile(r"#/settings$"))
    expect(launcher).to_be_focused()
    assert content.evaluate("node => node.scrollTop") >= 200

    page.get_by_role("searchbox", name="Search settings").fill("provider credentials")
    page.get_by_role("button", name=re.compile("Provider credentials")).click()
    expect(page).to_have_url(
        re.compile(r"#/settings/ai-connections\?control=providers$")
    )


def test_overview_responsive_geometry_has_one_scroll_owner_and_no_overflow(
    page: Page, ui_base_url: str
) -> None:
    for width, height in ((1440, 900), (1024, 768), (390, 844), (360, 800), (844, 390)):
        _open_overview(page, ui_base_url, width=width, height=height)
        geometry = page.locator("[data-settings-overview]").evaluate(
            """node => ({
              documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
              overviewOverflow: node.scrollWidth - node.clientWidth,
              targetHeights: [...node.querySelectorAll('[data-settings-overview-row]')]
                .filter(row => row.matches('a[href]')).map(row => row.getBoundingClientRect().height),
              contentOverflowY: getComputedStyle(node.closest('[data-settings-content]')).overflowY,
            })"""
        )
        assert geometry["documentOverflow"] <= 1
        assert geometry["overviewOverflow"] <= 1
        assert min(geometry["targetHeights"]) >= 44
        assert geometry["contentOverflowY"] == "auto"
