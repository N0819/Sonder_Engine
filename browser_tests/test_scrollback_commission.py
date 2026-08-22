"""Whether scrolling BACK to an undrawn room still commissions its picture.

The reported defect (live, chat 65): older scenes whose rooms were never drawn
stop generating -- scrolling up leaves the newest room's backdrop standing and
nothing is ever paid for. `test_backdrop_commission.py` pins the forward case
(a fresh turn arriving, repeat notifications about one turn); this file pins
the reader travelling backwards through history, which that suite never
exercises and which is exactly where the report came from.

Unlike its sibling, this drives a REAL transcript: actual `.turn` elements in
`#msgs`, the real IntersectionObserver via `observeVisibleTurn`, and real
scrolling -- because the suspected mechanism is geometry. The quick pass clears
the newest room's picture (the back-scrolled room has none), `clearBackdrop`
restyles every `.prose` in the transcript, the reflow moves content under the
viewport, and the observer's next notification can therefore be about a
NEIGHBOURING turn -- which, through the `pendingTurn` guard, cancels the dwell
clock of the turn the reader is actually looking at. Driving the callback by
hand cannot produce that sequence; only layout can.
"""

from __future__ import annotations

import base64
import json
from urllib.parse import urlparse

from playwright.sync_api import Page

from .test_backdrop_commission import BOOTSTRAP

# Turns 1..8 sit in the plaza, which has never been drawn. Turns 9..12 sit in
# the market, whose picture is on disk -- the situation live chat 65 was in
# (fountain_plaza turns behind an eastern_market present).
PLAZA_TURNS = list(range(1, 9))
MARKET_TURNS = list(range(9, 13))
PLAZA_SIG = "a" * 24
MARKET_SIG = "c" * 24

# A real, decodable picture: showBackdrop() decodes before it fades, so a 404
# here would silently skip the paint this test needs to trigger the reflow.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _turn_backdrop(turn_id: int) -> dict:
    plaza = turn_id in PLAZA_TURNS
    return {
        "enabled": True, "configured": True,
        "room": "Fountain Plaza" if plaza else "Eastern Market",
        "room_id": "fountain_plaza" if plaza else "eastern_market",
        "signature": PLAZA_SIG if plaza else MARKET_SIG,
        "ready": not plaza,
        "status": "absent" if plaza else "ready",
        "error": None,
        "url": None if plaza else "/bd.png",
        "weather": {},
    }


def _mock_api(page: Page) -> list[str]:
    posted: list[str] = []

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/bd.png":
            route.fulfill(status=200, content_type="image/png", body=PNG)
            return
        if path == "/api/bootstrap":
            body: dict = BOOTSTRAP
        elif path.startswith("/api/turns/") and path.endswith("/backdrop"):
            turn_id = int(path.split("/")[3])
            if route.request.method == "POST":
                posted.append(path)
                body = dict(_turn_backdrop(turn_id), status="pending")
            else:
                body = _turn_backdrop(turn_id)
        elif path.startswith("/api/turns/") and path.endswith("/ambience"):
            # Ambience is off in this fixture; an empty payload is what its
            # module treats as "disabled" and it stands down.
            body = {}
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    page.route("**/bd.png", handle)
    return posted


def _build_transcript(page: Page) -> None:
    """Real turn elements, the real observer -- the same shapes renderChat
    builds, minus the app state a canned story would need."""
    page.evaluate(
        """([plazaTurns, marketTurns]) => {
          const M = document.querySelector('#msgs');
          M.innerHTML = '';
          const entries = [];
          for (const id of plazaTurns.concat(marketTurns)) {
            const prose = ('Turn ' + id + '. ').repeat(40)
              + 'Lorem ipsum dolor sit amet. '.repeat(60);
            const d = el('div', { class: 'turn' },
                         el('div', { class: 'prose' }, prose));
            M.append(d);
            entries.push({ el: d, prose, turnId: id });
          }
          observeVisibleTurn(M, entries);
          M.scrollTo({ top: M.scrollHeight, behavior: 'instant' });
          window.__turnEls = new Map(entries.map(e => [e.turnId, e.el]));
        }""",
        [PLAZA_TURNS, MARKET_TURNS],
    )


def test_scrolling_back_to_an_undrawn_room_commissions_it(
    page: Page, ui_base_url: str
) -> None:
    """The live report: with the newest room's picture up, scrolling back to a
    room that was never drawn must commission it once the reader settles there.
    The previously-shown backdrop staying up is not the failure; nothing ever
    being PAID FOR is."""
    posted = _mock_api(page)
    page.goto(f"{ui_base_url}/static/index.html")
    page.wait_for_function("typeof observeVisibleTurn === 'function'")
    _build_transcript(page)

    # The newest room's picture arrives first -- the state the reader starts in.
    page.wait_for_function(
        "document.body.classList.contains('has-backdrop')", timeout=8000)
    assert posted == [], "a room already on disk must never be re-commissioned"

    # The reader scrolls back to the plaza and stops there.
    page.evaluate(
        "id => window.__turnEls.get(id).scrollIntoView("
        "{ block: 'center', behavior: 'instant' })",
        PLAZA_TURNS[2],
    )
    # BD_SETTLE_MS (220) + the clear's reflow + BD_DWELL_MS (2000), with slack:
    # the dwell must survive whatever notifications the reflow produces.
    page.wait_for_timeout(4500)

    plaza_posts = [p for p in posted
                   if int(p.split("/")[3]) in PLAZA_TURNS]
    assert plaza_posts, (
        "scrolling back to an undrawn room never commissioned its backdrop: "
        "posts seen: %r" % posted
    )
    market_posts = [p for p in posted
                    if int(p.split("/")[3]) in MARKET_TURNS]
    assert market_posts == [], (
        "the already-drawn room was re-commissioned on scroll-back: %r"
        % market_posts
    )


def test_settling_at_a_room_boundary_still_commissions(
    page: Page, ui_base_url: str
) -> None:
    """The adversarial geometry: the reader stops where the undrawn plaza and
    the drawn market share the viewport. The quick pass for the plaza clears
    the market's picture and reflows the transcript; if that reflow makes the
    market turn the observer's best, its quick pass re-shows the picture and
    reflows back -- and every flip re-arms the OTHER turn's clocks through the
    `pendingTurn` guard, cancelling a dwell that then never fires."""
    posted = _mock_api(page)
    page.goto(f"{ui_base_url}/static/index.html")
    page.wait_for_function("typeof observeVisibleTurn === 'function'")
    _build_transcript(page)

    page.wait_for_function(
        "document.body.classList.contains('has-backdrop')", timeout=8000)
    posted.clear()

    # Stop with the LAST plaza turn at the top of the view, so the first
    # market turn fills the rest of it.
    page.evaluate(
        "id => window.__turnEls.get(id).scrollIntoView("
        "{ block: 'start', behavior: 'instant' })",
        PLAZA_TURNS[-1],
    )
    page.wait_for_timeout(6000)

    assert posted, (
        "settling at the boundary of an undrawn room commissioned nothing: "
        "the clear/show reflow cycle kept cancelling the dwell"
    )
