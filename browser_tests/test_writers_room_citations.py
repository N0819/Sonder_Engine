"""A demoted claim is shown as a proposal, in a real browser.

`story/room_citations.py` demotes a claim that names no row the reply read:
it keeps its sentence and loses the authority it was borrowing. That is a
contract about what the READER sees, so the panel is where it is proven --
a string assertion cannot tell "rendered among the assertions with a note"
from "rendered among the proposals", and the difference between those two is
the entire mechanism.

Measured 2026-09-05, the caravanserai run: a recap said a character was
"feigning sleep while listening intently" when his ledger said watchful and
hooded, and the panel showed that sentence exactly as it showed the ones the
ledgers did say.

Fully mocked at the network boundary; the stream is the NDJSON the room
route speaks.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP, _chat_payload


ROOM_THREAD = {"messages": [], "mandates": [], "status": None, "seated": True,
               "page": 60, "message_chars": 4000}

REPLY = "A courier is in motion; he is late by now, and a third may follow."

#: What `check_claims` returned for that reply: one claim naming a row the
#: reply read, one naming a row it did not, and one offered as a proposal.
CITATIONS = {
    "claims": [
        {"text": "A courier is in motion", "cites": ["plot:courier"],
         "proposal": False, "verdict": "supported", "missing": [],
         "uncited": False},
        {"text": "He is late", "cites": ["plot:lateness"], "proposal": False,
         "verdict": "unsupported", "missing": ["plot:lateness"],
         "uncited": False},
        {"text": "A third may follow", "cites": [], "proposal": True,
         "verdict": "proposal", "missing": []},
    ],
    "rows_read": 4,
    "stated_nothing": False,
    "asserted": ["A courier is in motion"],
    "proposed": ["He is late", "A third may follow"],
    "unsupported": ["He is late"],
}


def _stream(citations) -> str:
    events = [
        {"type": "room_message",
         "message": {"id": 1, "role": "player", "text": "what is going on?"}},
        {"type": "token", "delta": REPLY},
        {"type": "room_done",
         "message": {"id": 1, "role": "player", "text": "what is going on?"},
         "replies": [{"id": 2, "role": "planner", "text": REPLY}],
         "error": None, "citations": citations, "mandates": [],
         "status": {"line": "A courier is on the road.", "questions": []},
         "seated": True},
    ]
    return "".join(json.dumps(e) + "\n" for e in events)


def _open_the_room(page: Page, ui_base_url: str, citations) -> None:
    def api(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body = dict(BOOTSTRAP, chats=[{"id": 1, "name": "The road"}])
        elif path.endswith("/room"):
            body = ROOM_THREAD
        elif path.endswith("/room/status"):
            body = ROOM_THREAD["status"]
        elif path.startswith("/api/chats/") and path.count("/") == 3:
            body = _chat_payload(1, "The road", "Dust and a long light.")
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", api)
    # Registered second, so it wins the more general pattern above.
    page.route("**/room/messages/stream", lambda route: route.fulfill(
        status=200, content_type="application/x-ndjson",
        body=_stream(citations)))

    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof roomOpen === 'function'")
    page.evaluate("() => { S.chatId = 1; }")
    page.click("#room-tab")
    page.fill("#room-input", "what is going on?")
    page.click("#room-send")
    page.wait_for_function("() => !document.querySelector('.room-live')")


def _claim_class(page: Page, text: str) -> str:
    return page.evaluate(
        """text => {
          const nodes = [...document.querySelectorAll('.room-claim')];
          const found = nodes.find(n => n.textContent.includes(text));
          return found ? found.className : "";
        }""", text)


def test_a_claim_naming_a_row_the_reply_read_is_shown_as_an_assertion(
        page: Page, ui_base_url: str) -> None:
    _open_the_room(page, ui_base_url, CITATIONS)
    expect(page.locator(".room-citations")).to_be_visible()
    assert "stated" in _claim_class(page, "A courier is in motion")


def test_a_claim_naming_no_row_is_shown_among_the_proposals(
        page: Page, ui_base_url: str) -> None:
    """THE DEMOTION, as the reader meets it. Not an assertion with a warning
    hung off it -- a proposal, in the proposals' clothes, with the one word
    that says how it got there."""
    _open_the_room(page, ui_base_url, CITATIONS)
    demoted = _claim_class(page, "He is late")
    assert "proposed" in demoted and "stated" not in demoted
    marker = page.locator(".room-claim", has_text="He is late")
    expect(marker).to_contain_text("no row")
    # A claim the room OFFERED as a proposal is a proposal too, and is not
    # marked as though something went wrong with it.
    volunteered = page.locator(".room-claim", has_text="A third may follow")
    assert "proposed" in _claim_class(page, "A third may follow")
    expect(volunteered).not_to_contain_text("no row")


def test_the_reply_itself_is_never_edited(page: Page, ui_base_url: str) -> None:
    """An unsupported claim is demoted, never deleted: the room keeps every
    sentence it wrote, including the one that lost its authority."""
    _open_the_room(page, ui_base_url, CITATIONS)
    expect(page.locator(".room-msg.planner .room-text")).to_have_text(REPLY)


def test_a_reply_that_enumerated_nothing_shows_no_accounting(
        page: Page, ui_base_url: str) -> None:
    """There is no claim to mark, and a badge on every reply would read as a
    verdict on the prose rather than a note about the accounting."""
    _open_the_room(page, ui_base_url, {
        "claims": [], "rows_read": 0, "stated_nothing": True,
        "asserted": [], "proposed": [], "unsupported": []})
    expect(page.locator(".room-citations")).to_have_count(0)
