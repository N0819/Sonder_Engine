"""A line typed for the story on screen is played into that story and no other.

`openChat` names the story being opened in `S.chatId` before its fetch lands,
and Send posts to `S.chatId` (frontend audit 2026-11-01, frontend_core F2).
Two windows let the two disagree: a switch that FAILS left `S.chatId` on the
story that failed while the page went on showing the old one, and a switch
still IN FLIGHT does the same until its answer arrives. A line typed in either
window landed in the story nobody was looking at.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def _payload(chat_id: int, name: str, prose: str) -> dict:
    return {"chat": {"id": chat_id, "name": name}, "participants": [],
            "turns": [{"id": chat_id * 10, "idx": 0, "player_input": "",
                       "prose": prose, "stale": False, "frame_id": None}],
            "lorebook": None, "lorebooks": [], "frames": []}


class _Server:
    def __init__(self, page: Page, nine: str):
        self.nine = nine          # "fails" | "holds"
        self.held = []
        self.posts = []
        page.route("**/api/**", self.handle)

    def handle(self, route) -> None:
        request = route.request
        path = urlparse(request.url).path
        if request.method == "POST" and path.endswith("/turns"):
            self.posts.append(path)
            route.fulfill(status=200, content_type="application/x-ndjson",
                          body=json.dumps({"type": "done", "turn_id": 71}) + "\n")
            return
        if path == "/api/chats/9":
            if self.nine == "fails":
                route.fulfill(status=500, content_type="application/json",
                              body=json.dumps({"detail": "Story 9 could not be read"}))
            else:
                self.held.append(route)
            return
        if path == "/api/bootstrap":
            body = dict(BOOTSTRAP, chats=[{"id": 7, "name": "Harbour"},
                                          {"id": 9, "name": "Tavern"}])
        elif path == "/api/chats/7":
            body = _payload(7, "Harbour", "Gulls over the harbour.")
        elif path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def test_after_a_failed_switch_the_line_goes_to_the_story_on_screen(
        page: Page, ui_base_url: str) -> None:
    server = _Server(page, "fails")
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof S !== 'undefined' && !!S.boot")
    page.evaluate("() => openChat(7)")
    expect(page.locator("#msgs")).to_contain_text("Gulls over the harbour.")

    page.evaluate("() => openChat(9).catch(() => {})")
    expect(page.locator(".toast")).to_have_count(0)  # the caller decides how to say it
    page.wait_for_function("() => S.chatId === 7")
    expect(page.locator("#chatname")).to_have_text("Harbour")

    page.fill("#input", "I watch the gulls.")
    page.click("#send")
    page.wait_for_function("() => !S.busy")
    assert server.posts == ["/api/chats/7/turns"]


def test_a_line_sent_while_another_story_loads_waits_in_the_composer(
        page: Page, ui_base_url: str) -> None:
    server = _Server(page, "holds")
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof S !== 'undefined' && !!S.boot")
    page.evaluate("() => openChat(7)")
    expect(page.locator("#msgs")).to_contain_text("Gulls over the harbour.")

    page.evaluate("() => { window.__opening = openChat(9); }")
    page.wait_for_function("() => S.chatId === 9")
    page.fill("#input", "I watch the gulls.")
    page.click("#send")
    page.wait_for_timeout(300)
    assert server.posts == []
    expect(page.locator("#input")).to_have_value("I watch the gulls.")

    server.held[0].fulfill(status=200, content_type="application/json",
                           body=json.dumps(_payload(9, "Tavern", "Smoke and dice.")))
    expect(page.locator("#msgs")).to_contain_text("Smoke and dice.")
    # Still the reader's to send, now that they can see where it would go.
    expect(page.locator("#input")).to_have_value("I watch the gulls.")
