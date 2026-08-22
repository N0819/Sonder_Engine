"""Reference-first browser contracts for the replacement Settings surface."""

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
    "providers": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


def _open_settings(
    page: Page,
    ui_base_url: str,
    *,
    width: int = 1440,
    height: int | None = None,
    category: str = "experience",
) -> None:
    page.set_viewport_size(
        {"width": width, "height": height or (900 if width >= 1000 else 844)}
    )
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(BOOTSTRAP)
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/settings/{category}")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )


def test_experience_ports_reference_frame_and_applies_local_preferences(
    page: Page, ui_base_url: str
) -> None:
    """Catches a return to the generic Settings placeholder or inert controls."""
    _open_settings(page, ui_base_url)

    expect(page.get_by_role("heading", name="Sonder preferences", level=1)).to_be_visible()
    categories = page.get_by_role("navigation", name="Settings categories")
    expect(categories.get_by_role("link")).to_have_count(6)
    expect(categories.get_by_role("link", name="Experience", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(page.get_by_role("heading", name="Experience", level=2)).to_be_visible()

    shell = page.locator("[data-settings-shell]")
    geometry = shell.evaluate(
        """node => {
          const box = node.getBoundingClientRect();
          const nav = node.querySelector('[data-settings-categories]').getBoundingClientRect();
          return { left: box.left, top: box.top, navWidth: nav.width };
        }"""
    )
    assert abs(geometry["left"] - 72) <= 1
    assert abs(geometry["top"] - 0) <= 1
    assert abs(geometry["navWidth"] - 240) <= 1

    page.get_by_role("button", name="Use Ash and Brass theme").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "ash-brass")
    expect(page.locator(".ui-settings__theme-readout")).to_have_text("Ash and Brass")
    stored = page.evaluate(
        "JSON.parse(localStorage.getItem('sonder.ui-next') || '{}').appearance?.theme"
    )
    assert stored == "ash-brass"

    page.get_by_role("checkbox", name="Reduced motion").check()
    expect(page.locator("html")).to_have_attribute("data-a11y-reduced-motion", "true")

    page.get_by_role("checkbox", name="Accessibility Mode").check()
    expect(page.get_by_role("checkbox", name="Solid surfaces")).to_be_checked()
    expect(page.get_by_role("checkbox", name="Roomy controls")).to_be_checked()
    page.get_by_role("checkbox", name="Solid surfaces").uncheck()
    expect(page.get_by_role("checkbox", name="Accessibility Mode")).not_to_be_checked()


def test_mobile_settings_uses_reference_horizontal_category_staging(
    page: Page, ui_base_url: str
) -> None:
    """Catches desktop sidebar leakage or clipped controls on the phone surface."""
    _open_settings(page, ui_base_url, width=390)

    expect(page).to_have_url(re.compile(r"#/settings/experience$"))
    categories = page.get_by_role("navigation", name="Settings categories")
    expect(categories).to_be_visible()
    geometry = page.evaluate(
        """() => {
          const nav = document.querySelector('[data-settings-categories]');
          const content = document.querySelector('[data-settings-content]');
          const selected = nav.querySelector('[aria-current="page"]');
          return {
            navWidth: nav.getBoundingClientRect().width,
            navScroll: nav.scrollWidth,
            contentLeft: content.getBoundingClientRect().left,
            selectedHeight: selected.getBoundingClientRect().height,
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          };
        }"""
    )
    assert geometry["navWidth"] == 390
    assert geometry["navScroll"] > geometry["navWidth"]
    assert abs(geometry["contentLeft"]) <= 1
    assert geometry["selectedHeight"] >= 44
    assert geometry["overflow"] <= 1
    expect(page.get_by_role("button", name="Use Parchment Night theme")).to_be_visible()


def test_advanced_ports_the_reference_launcher_panel(
    page: Page, ui_base_url: str
) -> None:
    """Catches replacement of the supplied Advanced ledger with generic cards."""
    _open_settings(page, ui_base_url, width=1024, height=600, category="advanced")

    expect(page.get_by_role("heading", name="Advanced", level=2)).to_be_visible()
    expect(page.get_by_text("Prompts, diagnostics, and raw story data", exact=True)).to_be_visible()
    launchers = page.locator("[data-settings-launcher]")
    expect(launchers).to_have_count(4)
    for label in (
        "Prompt editor",
        "Turn details",
        "Raw story data",
        "Raw clothing data",
    ):
        expect(page.get_by_role("button", name=re.compile(f"^{label}"))).to_be_visible()
    expect(
        page.get_by_text("Advanced tools change engine-facing data.", exact=True)
    ).to_be_visible()
