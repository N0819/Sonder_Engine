"""Real-browser contracts for the WP-03 replacement application shell."""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


def _open_shell(page: Page, ui_base_url: str, *, hash_value: str = "#/play") -> None:
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps(BOOTSTRAP),
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html{hash_value}")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )


def test_shell_exposes_three_destinations_and_truthful_empty_play(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url)

    primary = page.get_by_role("navigation", name="Primary")
    expect(primary.get_by_role("link")).to_have_count(3)
    for name in ("Play", "Library", "Settings"):
        expect(primary.get_by_role("link", name=name, exact=True)).to_be_visible()

    expect(page.get_by_role("main")).to_be_visible()
    expect(page.get_by_role("heading", name="Play", level=1)).to_be_focused()
    expect(page.get_by_text("Choose a story to begin.", exact=True)).to_be_visible()
    assert page.get_by_text("Provider", exact=True).count() == 0


def test_destination_navigation_refresh_and_history_preserve_orientation(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url)

    page.get_by_role("link", name="Library", exact=True).click()
    expect(page).to_have_url("#/library")
    expect(page.get_by_role("heading", name="Library", level=1)).to_be_focused()

    page.reload()
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )
    expect(page).to_have_url("#/library")
    expect(page.get_by_role("heading", name="Library", level=1)).to_be_visible()

    page.get_by_role("link", name="Settings", exact=True).click()
    page.go_back()
    expect(page).to_have_url("#/library")
    expect(page.get_by_role("heading", name="Library", level=1)).to_be_visible()


def test_go_to_is_keyboard_owned_and_does_not_fire_while_typing(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url)

    page.keyboard.press("Control+K")
    dialog = page.get_by_role("dialog", name="Go To")
    expect(dialog).to_be_visible()
    search = dialog.get_by_role("searchbox", name="Find a destination")
    expect(search).to_be_focused()
    search.fill("settings")
    search.press("Enter")
    expect(page).to_have_url("#/settings")

    typing_probe = page.locator("[data-shell-typing-probe]")
    typing_probe.focus()
    typing_probe.press("Control+K")
    expect(dialog).not_to_be_visible()


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 360, "height": 800},
        {"width": 390, "height": 844},
        {"width": 430, "height": 932},
        {"width": 768, "height": 1024},
        {"width": 844, "height": 390},
        {"width": 1024, "height": 600},
        {"width": 1024, "height": 768},
        {"width": 1280, "height": 800},
        {"width": 1440, "height": 900},
        {"width": 640, "height": 360},
    ],
)
def test_shell_matrix_has_no_horizontal_overflow_or_hidden_destination(
    page: Page, ui_base_url: str, viewport: dict[str, int]
) -> None:
    page.set_viewport_size(viewport)
    _open_shell(page, ui_base_url)

    geometry = page.evaluate(
        """() => ({
          pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          layout: document.documentElement.dataset.layoutState,
          destinations: [...document.querySelectorAll('[data-core-destination]')].map(node => ({
            name: node.dataset.coreDestination,
            width: node.getBoundingClientRect().width,
            height: node.getBoundingClientRect().height,
          })),
        })"""
    )
    assert geometry["pageOverflow"] <= 1
    assert geometry["layout"] in {"compact", "medium", "wide", "expansive"}
    assert [item["name"] for item in geometry["destinations"]] == [
        "play",
        "library",
        "settings",
    ]
    assert all(item["width"] > 0 and item["height"] >= 44 for item in geometry["destinations"])
