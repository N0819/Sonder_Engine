"""Presentation and behavior contracts for the WP10 host auth replacement."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


def test_sign_in_uses_reference_frame_and_credential_semantics(
    page: Page, ui_base_url: str
) -> None:
    page.route(
        "**/api/auth/status",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"authenticated": False, "setup_required": False}),
        ),
    )
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{ui_base_url}/static/login.html")

    expect(page.get_by_role("heading", name="Sign in", level=1)).to_be_visible()
    expect(page.get_by_text("Welcome back", exact=True)).to_be_visible()
    card = page.locator("#login-form")
    expect(card.get_by_label("Username", exact=True)).to_have_attribute("autocomplete", "username")
    expect(card.get_by_label("Password", exact=True)).to_have_attribute("autocomplete", "current-password")
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    assert card.evaluate("node => node.getBoundingClientRect().width") == 430


def test_first_host_setup_is_single_purpose_and_mobile_safe(
    page: Page, ui_base_url: str
) -> None:
    page.route(
        "**/api/auth/status",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"authenticated": False, "setup_required": True}),
        ),
    )
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{ui_base_url}/static/login.html")

    expect(page.get_by_role("heading", name="Create your host account", level=1)).to_be_visible()
    expect(page.get_by_label("New password", exact=True)).to_have_attribute("autocomplete", "new-password")
    expect(page.get_by_label("Confirm password", exact=True)).to_have_attribute("autocomplete", "new-password")
    geometry = page.locator("#setup-form").evaluate(
        """node => ({
          width: node.getBoundingClientRect().width,
          viewport: document.documentElement.clientWidth,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          button: node.querySelector('button').getBoundingClientRect().height,
        })"""
    )
    assert geometry["width"] <= geometry["viewport"] - 24
    assert geometry["overflow"] == 0
    assert geometry["button"] >= 44
