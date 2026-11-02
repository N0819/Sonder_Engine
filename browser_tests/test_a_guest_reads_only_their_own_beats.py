"""The guest page, driven: what a joined guest reads, and when it changes.

Four findings of the frontend audit of 2026-11-01 (frontend_core), all on the
one standalone page a guest has:

* F1 -- the stale note printed the earliest stale step's LABEL, and a
  character's step is labelled with that character's true name.
* F7 -- every beat the guest had no render for (beats before they joined,
  another era's beats) said "Waiting for this beat to resolve…" forever, so
  the one beat that really was pending looked like fifty that never would.
* F9 -- a line the guest sent vanished until a beat took it, and a guest who
  thought it had failed and sent again silently REPLACED it.
* F10 -- one failed poll (a server restart, one 502 from a proxy) stopped the
  live view for good; only a revoked session should.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect


def _turn(idx, prose="", player_input=None, stale_from=None, **extra):
    return {"idx": idx, "player_input": player_input, "prose": prose,
            "stale": bool(stale_from), "stale_from": stale_from,
            "prose_stale": False, **extra}


def _state(turns, **extra):
    return {"chat_name": "Harbour", "persona_name": "Ash", "turns": turns,
            "next_idx": (turns[-1]["idx"] + 1) if turns else 0, **extra}


class _Guest:
    """Serves `/api/guest/state` from a script of answers, the last repeating."""

    def __init__(self, page: Page, answers, catalog=None):
        self.answers = list(answers)
        self.state_calls = 0
        self.sent = []
        self.catalog = catalog or {}
        page.route("**/api/**", self.handle)

    def handle(self, route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/ui":
            body = {"language": "ja" if self.catalog else "en",
                    "messages": self.catalog}
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(body))
            return
        if path == "/api/guest/input":
            self.sent.append(json.loads(route.request.post_data or "{}"))
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"ok": True}))
            return
        if path == "/api/guest/state":
            self.state_calls += 1
            status, body = (self.answers.pop(0) if len(self.answers) > 1
                            else self.answers[0])
            route.fulfill(status=status, content_type="application/json",
                          body=json.dumps(body))
            return
        route.fulfill(status=404, content_type="application/json",
                      body=json.dumps({"detail": "Not found"}))


def test_a_stale_note_names_no_stage(page: Page, ui_base_url: str) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _Guest(page, [(200, _state([_turn(
        0, "The hooded woman nods.",
        stale_from={"ord": 3, "key": "character:12",
                    "label": "Character · Mirelle Sulmirath"})]))])

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator("#msgs")).to_contain_text("The hooded woman nods.")
    expect(page.locator(".stale-note")).to_contain_text("Partly out of date")
    text = page.locator("body").inner_text()
    assert "Mirelle" not in text
    assert "character:12" not in text
    assert errors == []


def test_only_a_beat_that_can_still_arrive_is_waiting(page: Page, ui_base_url: str) -> None:
    _Guest(page, [(200, _state([
        _turn(0),                                   # before the guest joined
        _turn(1, "The tide turns."),
        _turn(2, player_input="I wait by the rail."),  # theirs, no render
        _turn(3),                                   # the newest: may arrive
    ]))])

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator("#msgs")).to_contain_text("The tide turns.")
    expect(page.locator(".waiting")).to_have_count(1)
    expect(page.locator(".turn").last.locator(".waiting")).to_have_count(1)
    # The guest's own line is never dropped, even on a beat with no render.
    expect(page.locator("#msgs")).to_contain_text("I wait by the rail.")
    # A beat that will never have a render for this guest is not a row.
    expect(page.locator(".turn")).to_have_count(3)


def test_the_server_may_say_which_beats_are_pending(page: Page, ui_base_url: str) -> None:
    """When `guest_state` says per turn whether a render can still arrive, the
    page takes its word over the newest-beat rule."""
    _Guest(page, [(200, _state([
        _turn(0, pending=True),
        _turn(1, "The tide turns."),
        _turn(2, pending=False),
    ]))])

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator("#msgs")).to_contain_text("The tide turns.")
    expect(page.locator(".waiting")).to_have_count(1)
    expect(page.locator(".turn").first.locator(".waiting")).to_have_count(1)


def test_a_sent_line_shows_as_queued_until_a_beat_takes_it(page: Page, ui_base_url: str) -> None:
    before = _state([_turn(0, "Dawn over the harbour.")])
    after = _state([_turn(0, "Dawn over the harbour."),
                    _turn(1, "The door holds.", player_input="I check the door.")])
    guest = _Guest(page, [(200, before), (200, before), (200, after)])

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator("#msgs")).to_contain_text("Dawn over the harbour.")
    page.fill("#input", "I check the door.")
    page.click("#send-btn")

    queued = page.locator(".queued")
    expect(queued).to_have_count(1)
    expect(queued).to_contain_text("I check the door.")
    assert guest.sent == [{"idx": 1, "input": "I check the door."}]

    # The beat that took it arrives: the line is its pin now, not a queue row.
    page.evaluate("() => refresh()")
    expect(page.locator("#msgs")).to_contain_text("The door holds.")
    expect(page.locator(".queued")).to_have_count(0)
    expect(page.locator(".turn .pin")).to_have_text(["I check the door."])


def test_a_line_the_server_holds_is_shown_after_a_reload(page: Page, ui_base_url: str) -> None:
    """The server's own record of an unserved declaration, when it sends one,
    is what the page shows -- a reload must not lose the queued line."""
    _Guest(page, [(200, _state([_turn(0, "Dawn over the harbour.")],
                               pending_input=[{"idx": 1, "input": "I check the door."}]))])

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator(".queued")).to_contain_text("I check the door.")


def test_one_failed_poll_does_not_end_the_live_view(page: Page, ui_base_url: str) -> None:
    first = _state([_turn(0, "Dawn over the harbour.")])
    later = _state([_turn(0, "Dawn over the harbour."), _turn(1, "Gulls.")])
    guest = _Guest(page, [(200, first), (502, {"detail": "Bad gateway"}), (200, later)])
    page.clock.install()

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator("#msgs")).to_contain_text("Dawn over the harbour.")

    page.clock.run_for(10_000)
    expect(page.locator("#head-sub")).to_contain_text("Connection lost")
    assert guest.state_calls == 2

    # Still polling -- on a longer interval while the server is not answering.
    page.clock.run_for(60_000)
    expect(page.locator("#msgs")).to_contain_text("Gulls.")
    expect(page.locator("#head-sub")).to_contain_text("playing as Ash")


def test_a_revoked_session_stops_the_poll(page: Page, ui_base_url: str) -> None:
    first = _state([_turn(0, "Dawn over the harbour.")])
    guest = _Guest(page, [(200, first), (401, {"detail": "Unauthorized"})])
    page.clock.install()

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator("#msgs")).to_contain_text("Dawn over the harbour.")
    page.clock.run_for(10_000)
    expect(page.locator("#head-sub")).not_to_contain_text("playing as")
    calls = guest.state_calls
    page.clock.run_for(300_000)
    page.wait_for_timeout(200)
    assert guest.state_calls == calls
    # The last view stays up: a revoked guest can still read what they had.
    expect(page.locator("#msgs")).to_contain_text("Dawn over the harbour.")


def test_a_guests_own_words_are_never_translated(page: Page, ui_base_url: str) -> None:
    """i18n.js walks the whole page; a guest who typed "Continue" read 続ける."""
    _Guest(page, [(200, _state([_turn(0, "Continue", player_input="Continue")]))],
           catalog={"Continue": "続ける", "Send": "送信"})

    page.goto(ui_base_url + "/static/guest.html")
    expect(page.locator("#send-btn")).to_have_text("送信")
    expect(page.locator(".turn .pin")).to_have_text("Continue")
    expect(page.locator(".turn .prose")).to_have_text("Continue")
