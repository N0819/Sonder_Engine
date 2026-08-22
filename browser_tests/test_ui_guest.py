"""Presentation and recovery contracts for the WP11 guest replacement."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


def _json(route, status: int, payload: dict) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))


def _guest_state() -> dict:
    return {
        "chat_name": "Ash and Lantern",
        "persona_name": "Mara",
        "next_idx": 2,
        "turns": [
            {
                "player_input": "I push open the blue door.",
                "prose": "Rain whispers against the lantern glass.",
                "stale": False,
                "stale_from": None,
            }
        ],
    }


def test_guest_join_matches_the_reference_mobile_composition(
    page: Page, ui_base_url: str
) -> None:
    page.route("**/api/guest/state", lambda route: _json(route, 403, {"detail": "Guest session required"}))
    page.set_viewport_size({"width": 430, "height": 932})
    page.goto(f"{ui_base_url}/static/guest.html?code=ashen7q")

    expect(page.get_by_role("heading", name="Enter your join code", level=1)).to_be_visible()
    expect(page.get_by_text("Join a story", exact=True).first).to_be_visible()
    expect(page.get_by_label("Join code", exact=True)).to_have_value("ASHEN7Q")
    expect(page.get_by_role("button", name="Join story")).to_be_visible()
    geometry = page.locator("#join-card").evaluate(
        """node => ({
          width: node.getBoundingClientRect().width,
          left: node.getBoundingClientRect().left,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          button: node.querySelector('button').getBoundingClientRect().height,
        })"""
    )
    assert geometry["width"] == 406
    assert geometry["left"] == 12
    assert geometry["overflow"] == 0
    assert geometry["button"] >= 44


def test_guest_send_failure_is_inline_and_preserves_the_draft(
    page: Page, ui_base_url: str
) -> None:
    page.route("**/api/guest/state", lambda route: _json(route, 200, _guest_state()))
    page.route("**/api/guest/input", lambda route: _json(route, 409, {"detail": "The story moved on. Try again."}))
    page.goto(f"{ui_base_url}/static/guest.html")

    expect(page.get_by_text("Rain whispers against the lantern glass.")).to_be_visible()
    composer = page.get_by_label("Your action or speech")
    composer.fill("I wait beneath the awning.")
    page.get_by_role("button", name="Send").click()

    expect(page.locator("#send-status")).to_have_text("The story moved on. Try again.")
    expect(composer).to_have_value("I wait beneath the awning.")
    expect(page.get_by_text("Rain whispers against the lantern glass.")).to_be_visible()


def test_connection_loss_keeps_transcript_and_draft_with_recovery(
    page: Page, ui_base_url: str
) -> None:
    online = {"value": True}

    def state_route(route) -> None:
        if online["value"]:
            _json(route, 200, _guest_state())
        else:
            _json(route, 403, {"detail": "Guest session required"})

    page.route("**/api/guest/state", state_route)
    page.set_viewport_size({"width": 430, "height": 932})
    page.goto(f"{ui_base_url}/static/guest.html")
    composer = page.get_by_label("Your action or speech")
    geometry = page.evaluate(
        """() => ({
          viewport: [innerWidth, innerHeight],
          body: document.body.getBoundingClientRect().toJSON(),
          header: document.querySelector('header').getBoundingClientRect().toJSON(),
          play: document.querySelector('#play-screen').getBoundingClientRect().toJSON(),
          transcript: document.querySelector('#msgs').getBoundingClientRect().toJSON(),
          composer: document.querySelector('.ui-guest-composer').getBoundingClientRect().toJSON(),
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        })"""
    )
    assert geometry["overflow"] == 0, geometry
    assert geometry["composer"]["bottom"] == geometry["viewport"][1], geometry
    assert geometry["composer"]["height"] <= 120, geometry
    composer.fill("Keep this draft")
    online["value"] = False
    page.evaluate("refresh()")

    expect(page.locator("#connection-status")).to_contain_text("Connection lost")
    expect(page.get_by_role("button", name="Reconnect")).to_be_visible()
    expect(page.get_by_text("Rain whispers against the lantern glass.")).to_be_visible()
    expect(composer).to_have_value("Keep this draft")
