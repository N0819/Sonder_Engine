"""A confirm or prompt answers the control that has focus, and keeps focus.

`_confirmOverlay` (components.js) put one keydown listener on the document
that confirmed on ANY Enter (frontend audit 2026-11-01, frontend_core F3). The
listener runs before a focused button's own activation, so a keyboard reader
who moved to Cancel -- or to "Not now" on the paid embeddings rebuild -- and
pressed Enter confirmed the delete. Nothing trapped focus either, so Tab
walked out to the sidebar behind the overlay, and Enter there confirmed the
dialog AND opened that story.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def _page(page: Page, ui_base_url: str) -> None:
    def handle(route) -> None:
        path = urlparse(route.request.url).path
        body = (dict(BOOTSTRAP, chats=[{"id": 7, "name": "Harbour"}])
                if path == "/api/bootstrap" else {})
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", handle)
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof S !== 'undefined' && !!S.boot")


def _ask(page: Page, call: str) -> None:
    page.evaluate("call => { window.__answer = 'pending';"
                  " eval(call).then(value => { window.__answer = value; }); }", call)
    expect(page.locator(".confirm-overlay")).to_be_visible()
    # The overlay focuses its own first control on the next frame.
    page.wait_for_function(
        "() => document.querySelector('.confirm-overlay').contains(document.activeElement)")


def _answer(page: Page):
    page.wait_for_function("() => window.__answer !== 'pending'")
    return page.evaluate("() => window.__answer")


def test_enter_on_cancel_cancels(page: Page, ui_base_url: str) -> None:
    _page(page, ui_base_url)
    _ask(page, "confirmModal('Delete story?', {danger: true, confirmLabel: 'Delete'})")
    page.locator(".confirm-overlay button", has_text="Cancel").focus()
    page.keyboard.press("Enter")
    assert _answer(page) is False
    expect(page.locator(".confirm-overlay")).to_have_count(0)


def test_enter_on_the_primary_confirms(page: Page, ui_base_url: str) -> None:
    _page(page, ui_base_url)
    _ask(page, "confirmModal('Delete story?', {danger: true, confirmLabel: 'Delete'})")
    page.keyboard.press("Enter")          # focus starts on the primary button
    assert _answer(page) is True


def test_enter_in_a_prompt_field_submits_it(page: Page, ui_base_url: str) -> None:
    _page(page, ui_base_url)
    _ask(page, "promptModal('Rename story:', 'Harbour')")
    page.keyboard.press("End")
    page.keyboard.type(" at dusk")
    page.keyboard.press("Enter")
    assert _answer(page) == "Harbour at dusk"


def test_enter_on_a_prompts_cancel_cancels(page: Page, ui_base_url: str) -> None:
    _page(page, ui_base_url)
    _ask(page, "promptModal('Rename story:', 'Harbour')")
    page.locator(".confirm-overlay button", has_text="Cancel").focus()
    page.keyboard.press("Enter")
    assert _answer(page) is None


def test_tab_stays_inside_the_dialog(page: Page, ui_base_url: str) -> None:
    _page(page, ui_base_url)
    _ask(page, "confirmModal('Delete story?', {danger: true, confirmLabel: 'Delete'})")
    for key in ["Tab", "Tab", "Tab", "Shift+Tab", "Shift+Tab", "Shift+Tab", "Shift+Tab"]:
        page.keyboard.press(key)
        assert page.evaluate(
            "() => document.querySelector('.confirm-overlay').contains(document.activeElement)"), key
    page.keyboard.press("Escape")
    assert _answer(page) is False


def test_enter_behind_the_dialog_neither_confirms_nor_acts(page: Page, ui_base_url: str) -> None:
    """Focus can still be put behind the overlay by script; Enter there must
    not confirm the dialog and must not activate what it lands on."""
    _page(page, ui_base_url)
    _ask(page, "confirmModal('Delete story?', {danger: true, confirmLabel: 'Delete'})")
    page.evaluate("() => document.querySelector('#sidelist .story-item').focus()")
    page.keyboard.press("Enter")
    page.wait_for_timeout(150)
    assert page.evaluate("() => window.__answer") == "pending"
    assert page.evaluate("() => S.chatId") is None
    assert page.evaluate(
        "() => document.querySelector('.confirm-overlay').contains(document.activeElement)")
