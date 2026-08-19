"""How the backdrop poll loop describes the way a generation actually ended.

backdrops.js is the module ambience.js was copied from, and `awaitBackdrop`
carries the same classification defect its twin was reported for (chat 65),
with different wording:

* a signature that changed under the poll broke the loop -- and because the
  DRIFTED state still said `pending`, the very next line threw "still
  generating after several minutes" three seconds in, and blacklisted the old
  signature for the session;
* a queue that retired the work with nothing produced (`absent`) fell through
  SILENTLY -- no picture, no message, nothing: a paid feature that reads as
  broken;
* running out of the poll budget while honestly still `pending` blacklisted a
  generation the server was still working on, converting slow into
  permanently blank.

Same rules as the ambience twin: each ending says what happened, and only a
definitive server verdict gives up on the room for the session.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page

from test_backdrop_commission import BOOTSTRAP

TURN_ID = 7
SIG = "f" * 24
OTHER_SIG = "0" * 24


def _bd_state(**over) -> dict:
    state = {
        "enabled": True, "configured": True,
        "room": "Fountain Plaza", "room_id": "fountain_plaza",
        "signature": SIG, "ready": False, "status": "pending",
        "error": None, "url": None, "weather": {},
    }
    state.update(over)
    return state


def _boot(page: Page, ui_base_url: str, get_state: dict) -> None:
    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body: dict = BOOTSTRAP
        elif path.startswith("/api/turns/") and path.endswith("/backdrop"):
            body = (_bd_state(status="pending")
                    if route.request.method == "POST" else get_state)
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    page.goto(f"{ui_base_url}/static/index.html")
    page.wait_for_function("typeof generateBackdrop === 'function'")


def _generate_and_wait(page: Page, timeout: int = 12000) -> None:
    page.evaluate(
        """([turnId, sig]) => {
          window.__done = false;
          generateBackdrop(turnId, sig).then(() => { window.__done = true; });
        }""",
        [TURN_ID, SIG],
    )
    page.wait_for_function("window.__done === true", timeout=timeout)


def _toasts(page: Page) -> list[dict]:
    return page.evaluate(
        """() => [...document.querySelectorAll('#toasts .toast')].map(t => ({
             cls: t.className, text: t.textContent }))"""
    )


def test_a_generation_called_off_says_so_instead_of_nothing(
    page: Page, ui_base_url: str
) -> None:
    """The queue retired the work with no image and no error (`absent`). The
    reader dwelt on the room, authorised a paid generation, and the module said
    nothing at all -- silence indistinguishable from the feature being broken.
    It must say the work was called off, calmly, and must not give up on the
    room (asking again is explicitly allowed after a cancellation)."""
    _boot(page, ui_base_url, _bd_state(status="absent"))
    _generate_and_wait(page)

    toasts = _toasts(page)
    assert toasts, "a paid pass that produced nothing must say what happened"
    assert any("called off" in t["text"] for t in toasts), toasts
    assert all("warn" in t["cls"] for t in toasts), (
        "being called off is not a failure of the room: %r" % toasts)
    assert not page.evaluate("BD.failed.has('%s')" % SIG)


def test_a_room_that_changed_under_the_poll_fails_nothing(
    page: Page, ui_base_url: str
) -> None:
    """The drifted state still said `pending`, so the old code fell through to
    "still generating after several minutes" THREE SECONDS in -- a message
    wrong about both the time elapsed and the state -- and blacklisted a
    signature the turn no longer even wants."""
    _boot(page, ui_base_url,
          _bd_state(signature=OTHER_SIG, status="pending"))
    _generate_and_wait(page)

    assert _toasts(page) == [], (
        "an obsolete generation raised a toast about the room it no longer "
        "describes: %r" % _toasts(page))
    assert not page.evaluate("BD.failed.has('%s')" % SIG)


def test_running_out_of_patience_does_not_give_up_on_the_room(
    page: Page, ui_base_url: str
) -> None:
    """210 seconds of honest `pending` used to blacklist the signature -- but
    the queue entry is still active, a later POST would simply JOIN it, and
    the image usually lands. Slow must not become permanently blank; the toast
    may say it is taking long, the blacklist may not happen."""
    _boot(page, ui_base_url, _bd_state(status="pending"))
    page.clock.install()
    page.evaluate(
        """([turnId, sig]) => {
          window.__done = false;
          generateBackdrop(turnId, sig).then(() => { window.__done = true; });
        }""",
        [TURN_ID, SIG],
    )
    # 70 polls x 3s, advanced poll-sized so each timer's fetch completes.
    #
    # Bounded by PROGRESS rather than by a fixed iteration count with a fixed
    # real-time nap, for the reason its twin in `test_ambience_await.py`
    # carries at length: 20ms of wall clock is a promise about the machine,
    # not about the code, and a shared runner that misses it ends the loop
    # with the budget unspent and no toast. Extra iterations are harmless --
    # a poll schedules the next only after its own fetch resolves, so
    # fast-forwarding while nothing is pending advances no timer. Fixed here
    # at the same time as the ambience one because it is the same loop; the
    # ambience one is simply the one that happened to be observed failing.
    for _ in range(320):
        if page.evaluate("window.__done === true"):
            break
        page.clock.fast_forward(3100)
        page.wait_for_timeout(20)
    page.wait_for_function("window.__done === true", timeout=15000)

    toasts = _toasts(page)
    assert toasts, "minutes of silence then nothing at all reads as broken"
    assert all("warn" in t["cls"] for t in toasts), (
        "a generation still honestly running was reported as a failure: %r"
        % toasts)
    assert not page.evaluate("BD.failed.has('%s')" % SIG), (
        "a slow generation was blacklisted; when it lands moments later the "
        "room stays blank anyway"
    )
