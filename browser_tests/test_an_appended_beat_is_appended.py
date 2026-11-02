"""A beat that was appended is appended to the transcript, not rebuilt with it.

After every beat `openChat` fetched only the new turns (`?since_turn_id=`) and
then `renderChat` threw the whole transcript away and painted every turn again
-- prose, dialogue tint, buttons, observer (frontend audit 2026-11-01,
frontend_core E3). Measured on a 300-turn story in Chromium: 80-130 ms of main
thread per beat, growing with the story. The appended turns are added now, and
the turn that was last is redrawn once, because its reroll arrows and its
Delete belong to the newest turn only. Anything that rewrites a turn already on
the page -- a reroll, an edit, a delete -- still rebuilds whole.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def _turn(tid, idx, prose):
    return {"id": tid, "idx": idx, "player_input": "", "prose": prose,
            "stale": False, "frame_id": None}


def _story(*turns):
    return {"chat": {"id": 1, "name": "First"}, "participants": [], "turns": list(turns),
            "lorebook": None, "lorebooks": [], "frames": []}


class _Server:
    def __init__(self, page: Page):
        self.reads = []
        page.route("**/api/**", self.handle)

    def handle(self, route) -> None:
        request = route.request
        url = urlparse(request.url)
        path = url.path
        if request.method == "POST" and path in ("/api/chats/1/turns", "/api/turns/12/reroll"):
            route.fulfill(status=200, content_type="application/x-ndjson",
                          body=json.dumps({"type": "done", "turn_id": 13}) + "\n")
            return
        if path == "/api/bootstrap":
            body = dict(BOOTSTRAP, chats=[{"id": 1, "name": "First"}])
        elif path == "/api/chats/1":
            self.reads.append(url.query)
            if "since_turn_id=12" in url.query:
                body = dict(_story(_turn(13, 3, "Gulls rise.")), turns_since=12)
            else:
                body = _story(_turn(10, 0, "Dawn."), _turn(11, 1, "Rain."), _turn(12, 2, "Tide."))
        elif path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def test_a_new_beat_keeps_the_turns_already_on_the_page(page: Page, ui_base_url: str) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    server = _Server(page)
    page.goto(ui_base_url + "/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#msgs .turn")).to_have_count(3)
    page.evaluate("() => document.querySelectorAll('#msgs .turn').forEach(n => { n.__kept = true; })")
    expect(page.locator("#msgs .turn").nth(2).locator("button[title='Reroll']")).to_have_count(1)

    page.get_by_label("Story input").fill("I watch the gulls.")
    page.locator("#send").click()
    expect(page.locator("#msgs .turn")).to_have_count(4)
    expect(page.locator("#msgs .turn").nth(3)).to_contain_text("Gulls rise.")
    assert server.reads[-1] == "since_turn_id=12"

    kept = page.evaluate("() => [...document.querySelectorAll('#msgs .turn')].map(n => !!n.__kept)")
    # The two turns that did not change are the same nodes; the one that WAS
    # last is redrawn (it gives up the newest turn's controls); the new one is new.
    assert kept == [True, True, False, False]
    expect(page.locator("#msgs .turn").nth(2).locator("button[title='Reroll']")).to_have_count(0)
    expect(page.locator("#msgs .turn").nth(3).locator("button[title='Reroll']")).to_have_count(1)
    expect(page.locator("#msgs .turn button[title='Reroll']")).to_have_count(1)
    assert errors == []


def test_a_rewrite_still_rebuilds_the_whole_transcript(page: Page, ui_base_url: str) -> None:
    _Server(page)
    page.goto(ui_base_url + "/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#msgs .turn")).to_have_count(3)
    page.evaluate("() => document.querySelectorAll('#msgs .turn').forEach(n => { n.__kept = true; })")

    page.evaluate("() => runReroll(12)")
    page.wait_for_function("() => !S.busy")
    page.wait_for_function(
        "() => [...document.querySelectorAll('#msgs .turn')].every(n => !n.__kept)")
