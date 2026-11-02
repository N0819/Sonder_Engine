"""The page hears how a turn ended, and follows a turn whose stream broke.

Frontend audit 2026-11-01, frontend_core F4 and F6, driven through the real
Send button. The logic is unit-tested under node in
`tests/test_a_run_ends_the_way_its_stream_says.py`; this is the same two
endings in a browser, end to end through `streamPost`.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def _turn(tid, idx, prose, player_input=""):
    return {"id": tid, "idx": idx, "player_input": player_input, "prose": prose,
            "stale": False, "frame_id": None}


def _story(*turns):
    return {"chat": {"id": 1, "name": "First"}, "participants": [], "turns": list(turns),
            "lorebook": None, "lorebooks": [], "frames": []}


class _Server:
    def __init__(self, page: Page, stream: list[dict], statuses=None, after=None):
        self.stream = stream
        self.statuses = list(statuses or [])
        self.after = after
        self.status_reads = 0
        page.route("**/api/**", self.handle)

    def handle(self, route) -> None:
        request = route.request
        url = urlparse(request.url)
        path = url.path
        if request.method == "POST" and path == "/api/chats/1/turns":
            body = "".join(json.dumps(event) + "\n" for event in self.stream)
            route.fulfill(status=200, content_type="application/x-ndjson", body=body)
            return
        if path == "/api/turns/11/status":
            self.status_reads += 1
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            route.fulfill(status=200, content_type="application/json", body=json.dumps(status))
            return
        if path == "/api/bootstrap":
            body = dict(BOOTSTRAP, chats=[{"id": 1, "name": "First"}])
        elif path == "/api/chats/1":
            body = (self.after if (self.after and "since_turn_id" in url.query)
                    else _story(_turn(10, 0, "settled prose")))
        elif path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _open(page: Page, ui_base_url: str) -> None:
    page.goto(ui_base_url + "/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#msgs")).to_contain_text("settled prose")
    page.evaluate("() => { window.__chimes = 0; chimePlay = () => { window.__chimes++; }; }")


def test_a_pipeline_error_in_the_stream_gives_the_line_back(page: Page, ui_base_url: str) -> None:
    _Server(page, [
        {"type": "step_start", "key": "director_interpret", "label": "Director · interpret"},
        {"type": "error", "error": "Out of credit", "error_type": "RuntimeError", "fatal": True},
    ])
    _open(page, ui_base_url)
    page.get_by_label("Story input").fill("Open the door.")
    page.locator("#send").click()

    expect(page.locator(".toast.err")).to_contain_text("Out of credit")
    expect(page.get_by_label("Story input")).to_have_value("Open the door.")
    expect(page.locator("#send")).to_be_enabled()
    assert page.evaluate("() => window.__chimes") == 0


def test_a_stream_that_breaks_is_followed_to_the_finished_turn(page: Page, ui_base_url: str) -> None:
    server = _Server(
        page,
        # The server accepted the beat and began it; then the connection went.
        [{"type": "step_start", "key": "director_interpret", "label": "Director · interpret"}],
        statuses=[{"running": True, "committed": False},
                  {"running": False, "committed": True}],
        after=_story(_turn(11, 1, "The door gives.", "Open the door.")),
    )
    _open(page, ui_base_url)
    page.get_by_label("Story input").fill("Open the door.")
    page.locator("#send").click()

    expect(page.locator("#turnstatus-phase")).to_contain_text("following this beat")
    expect(page.locator("#stop")).to_be_visible()
    expect(page.locator("#send")).to_be_disabled()

    expect(page.locator("#msgs")).to_contain_text("The door gives.", timeout=10_000)
    expect(page.locator("#stop")).to_be_hidden()
    expect(page.get_by_label("Story input")).to_have_value("")
    assert server.status_reads >= 2
    assert page.evaluate("() => window.__chimes") == 1
