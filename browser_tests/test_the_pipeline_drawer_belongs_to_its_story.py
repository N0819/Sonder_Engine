"""The pipeline drawer closes with its story, and shows one turn at a time.

Frontend audit 2026-11-01, frontend_core F5 and F16; the wiring is pinned in
`tests/test_the_pipeline_drawer_belongs_to_its_story.py`.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def _story(chat_id: int, name: str, prose: str) -> dict:
    return {"chat": {"id": chat_id, "name": name}, "participants": [],
            "turns": [{"id": chat_id * 10, "idx": 0, "player_input": "", "prose": prose,
                       "stale": False, "frame_id": None}],
            "lorebook": None, "lorebooks": [], "frames": []}


def _pipeline(label: str) -> dict:
    return {"steps": [{"id": 1, "key": "narrator", "label": label, "ord": 1, "stale": False,
                       "variants": [{"id": 1, "active": True, "content": "{}"}]}],
            "editable": True, "resumable": False, "perceivers": {}}


class _Server:
    def __init__(self, page: Page, slow_first_open: bool = False):
        self.slow_first_open = slow_first_open
        self.held = []
        page.route("**/api/**", self.handle)

    def handle(self, route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/turns/10/pipeline" and self.slow_first_open and not self.held:
            self.held.append(route)
            return
        if path == "/api/bootstrap":
            body = dict(BOOTSTRAP, chats=[{"id": 1, "name": "First"},
                                          {"id": 2, "name": "Second"}])
        elif path == "/api/chats/1":
            body = _story(1, "First", "Story one.")
        elif path == "/api/chats/2":
            body = _story(2, "Second", "Story two.")
        elif path == "/api/turns/10/pipeline":
            body = _pipeline("Narrator · turn ten")
        elif path == "/api/turns/11/pipeline":
            body = _pipeline("Narrator · turn eleven")
        elif path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def test_a_story_switch_closes_the_drawer(page: Page, ui_base_url: str) -> None:
    _Server(page)
    page.goto(ui_base_url + "/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#msgs")).to_contain_text("Story one.")
    page.locator(".turn .tbtns button[title='Pipeline']").first.dispatch_event("click")
    expect(page.locator("#drawer")).to_be_visible()
    expect(page.locator("#drawer")).to_contain_text("Narrator · turn ten")

    page.get_by_label("Open Second").click()
    expect(page.locator("#msgs")).to_contain_text("Story two.")
    expect(page.locator("#drawer")).to_be_hidden()


def test_two_quick_opens_show_only_the_second_turn(page: Page, ui_base_url: str) -> None:
    server = _Server(page, slow_first_open=True)
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof S !== 'undefined' && !!S.boot")
    page.evaluate("() => { openPipeline(10); }")
    page.evaluate("() => openPipeline(11)")
    expect(page.locator("#drawer")).to_contain_text("Narrator · turn eleven")
    server.held[0].fulfill(status=200, content_type="application/json",
                           body=json.dumps(_pipeline("Narrator · turn ten")))
    page.wait_for_timeout(300)
    expect(page.locator("#drawer .step")).to_have_count(1)
    expect(page.locator("#drawer")).not_to_contain_text("turn ten")
