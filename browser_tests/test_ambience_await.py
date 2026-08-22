"""How the ambience poll loop describes the way a search actually ended.

The live report (chat 65): "still searching for ambience" thrown for scenes
that had never genned ambience -- a message describing the opposite of the
state. `awaitAmbience` collapsed four distinct endings into that one phrase:

* the server answered `absent` (nothing queued any more: the work was called
  off, or retired without a product) -- NOT still searching;
* the room's signature changed under the poll (a new beat, an offscreen tick)
  -- a different search now matters, this one is obsolete;
* the poll budget ran out while the server was honestly still `pending` --
  the only ending the words fit;
* the server recorded an error -- which already had its own message.

Worse than the wording: every one of them landed in the same catch, and the
catch blacklisted the signature for the session (`AMB.failed`), so one
mislabelled toast made that room permanently silent in the tab -- the second
live symptom ("not genning for older scenes"). These tests pin the
classification: each ending must say what actually happened, and only a
definitive server verdict may give up on the room.

Every route is fulfilled from the test; the timeout case runs on Playwright's
clock so 75 virtual seconds of polling cost milliseconds.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page

from .test_backdrop_commission import BOOTSTRAP

TURN_ID = 5
SIG = "d" * 24
OTHER_SIG = "e" * 24


def _amb_state(**over) -> dict:
    state = {
        "enabled": True, "configured": True, "source": "freesound",
        "room": "Fountain Plaza", "room_id": "fountain_plaza",
        "signature": SIG, "pinned": False, "gain": 1.0,
        "ready": False, "silent": False, "reason": "",
        "status": "pending", "error": None, "error_kind": None,
        "url": None, "layers": [], "token": None, "track": None,
    }
    state.update(over)
    return state


def _mock(page: Page, get_state: dict) -> list[str]:
    posted: list[str] = []

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body: dict = BOOTSTRAP
        elif path.startswith("/api/turns/") and path.endswith("/ambience"):
            if route.request.method == "POST":
                posted.append(path)
                body = _amb_state(status="pending")
            else:
                body = get_state
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    return posted


def _boot(page: Page, ui_base_url: str, get_state: dict) -> list[str]:
    posted = _mock(page, get_state)
    page.goto(f"{ui_base_url}/static/index.html")
    page.wait_for_function("typeof resolveAmbience === 'function'")
    return posted


def _resolve_and_wait(page: Page, timeout: int = 10000) -> None:
    page.evaluate(
        """([turnId, sig]) => {
          window.__done = false;
          resolveAmbience(turnId, sig).then(() => { window.__done = true; });
        }""",
        [TURN_ID, SIG],
    )
    page.wait_for_function("window.__done === true", timeout=timeout)


def _toasts(page: Page) -> list[dict]:
    return page.evaluate(
        """() => [...document.querySelectorAll('#toasts .toast')].map(t => ({
             cls: t.className, text: t.textContent }))"""
    )


def test_a_search_that_is_not_running_is_not_called_still_searching(
    page: Page, ui_base_url: str
) -> None:
    """The reported toast. The POST queued work; by the first poll the queue
    had retired it with nothing produced (`absent`). The message said "still
    searching" -- the precise opposite -- and the room was blacklisted for the
    session on the strength of it."""
    _boot(page, ui_base_url, _amb_state(status="absent"))
    _resolve_and_wait(page)

    toasts = _toasts(page)
    assert toasts, "a search that was called off must say so, not stay silent"
    assert all("still searching" not in t["text"] for t in toasts), (
        "a retired search described itself as still running: %r" % toasts)
    assert any("called off" in t["text"] for t in toasts), toasts
    assert all("warn" in t["cls"] for t in toasts), (
        "being called off is not a failure of the room: %r" % toasts)
    assert not page.evaluate("AMB.failed.has('%s')" % SIG), (
        "a search that was merely called off blacklisted the room for the "
        "session -- this is how one wrong toast became 'ambience no longer "
        "gens here'"
    )


def test_a_room_that_changed_under_the_poll_fails_nothing(
    page: Page, ui_base_url: str
) -> None:
    """Mid-poll the turn's signature moved (a fresh beat, an offscreen tick
    touching the live scene). The old search is obsolete, not broken: no toast,
    and above all no blacklist of a signature that is not even current."""
    _boot(page, ui_base_url,
          _amb_state(signature=OTHER_SIG, status="pending"))
    _resolve_and_wait(page)

    assert _toasts(page) == [], (
        "an obsolete search raised a toast about the room it no longer "
        "describes: %r" % _toasts(page))
    assert not page.evaluate("AMB.failed.has('%s')" % SIG)


def test_running_out_of_patience_does_not_give_up_on_the_room(
    page: Page, ui_base_url: str
) -> None:
    """The one ending "still searching" honestly fits: the poll budget (75s)
    elapsed with the server still `pending`. The resolution keeps running
    server-side and usually lands -- the in-code measurement is ~27s for the
    query-writing model call alone -- so blacklisting here converts SLOW into
    PERMANENTLY ABSENT. The toast may say it is taking long; the blacklist may
    not happen."""
    _boot(page, ui_base_url, _amb_state(status="pending"))
    page.clock.install()
    page.evaluate(
        """([turnId, sig]) => {
          window.__done = false;
          resolveAmbience(turnId, sig).then(() => { window.__done = true; });
        }""",
        [TURN_ID, SIG],
    )
    # 30 polls x 2.5s, advanced in poll-sized steps so each timer's fetch can
    # complete before the next one is due.
    #
    # The step is bounded by PROGRESS, not by a fixed number of iterations
    # with a fixed real-time nap. Each poll needs its fetch to settle before
    # the next timer is due, and 25ms of wall clock is a promise about the
    # machine rather than about the code: on a shared CI runner it is
    # sometimes not enough, and the run ends with the budget unspent, no
    # toast, and a failure that reproduces nowhere. (Measured 2026-08-19: this
    # test failed once in GitHub Actions and passed three consecutive local
    # runs on the same commit.) Extra iterations are harmless -- a poll
    # schedules the next one only after its own fetch resolves, so
    # fast-forwarding while nothing is pending advances no timer.
    for _ in range(160):
        if page.evaluate("window.__done === true"):
            break
        page.clock.fast_forward(2600)
        page.wait_for_timeout(25)
    page.wait_for_function("window.__done === true", timeout=15000)

    toasts = _toasts(page)
    assert toasts, "75 quiet seconds then nothing at all reads as broken"
    assert all("warn" in t["cls"] for t in toasts), (
        "a search still honestly running was reported as a failure: %r" % toasts)
    assert not page.evaluate("AMB.failed.has('%s')" % SIG), (
        "a slow search was blacklisted for the session; when it lands seconds "
        "later the room stays silent anyway"
    )


def test_a_concluded_empty_search_names_the_outcome_and_the_remedy(
    page: Page, ui_base_url: str
) -> None:
    """The search genuinely concluded with nothing (`AmbienceNotFound`). That
    is an outcome the reader can act on -- reroll tries different terms -- not
    a malfunction, so it arrives as a calm 'warn' naming the remedy, rather
    than an error dressed in a Python type name. The session does give up on
    the room (retrying deterministically finds nothing again); reroll bypasses
    that on purpose."""
    _boot(page, ui_base_url, _amb_state(
        status="error",
        error="AmbienceNotFound: No ambience found for: plaza fountain water",
        error_kind="notfound",
    ))
    _resolve_and_wait(page)

    toasts = _toasts(page)
    assert toasts
    assert all("warn" in t["cls"] for t in toasts), (
        "an empty result is not a malfunction: %r" % toasts)
    assert any("reroll" in t["text"].lower() for t in toasts), (
        "the one remedy the reader has was never named: %r" % toasts)
    assert all("AmbienceNotFound" not in t["text"] for t in toasts), (
        "a Python exception name reached the reader: %r" % toasts)
    assert page.evaluate("AMB.failed.has('%s')" % SIG), (
        "an identical search would find the identical nothing; the session "
        "must not retry it on every scroll"
    )
