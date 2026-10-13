"""A rejoined thread's composer says it has ended (`syncComposerToFrame`).

The server refuses a beat played into a frame whose split is over
(`turn_new`, 2026-10-13); chat 166 turn 4583 was a player line played into a
bubble frame that had already rejoined. The page keeps the frame's pill so its
history reads, and its composer says where to play on instead of taking a
line the server will refuse.
"""
import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def _turn(tid, idx, frame_id, prose):
    return {"id": tid, "idx": idx, "player_input": "", "prose": prose,
            "stale": False, "frame_id": frame_id}


CHAT = {
    "chat": {"id": 7, "name": "Home"},
    "participants": [],
    "turns": [_turn(70, 0, None, "Morning at the shrine."),
              _turn(71, 1, 12, "Tamamo crosses the court."),
              _turn(72, 2, None, "You stretch.")],
    "lorebook": None,
    "lorebooks": [],
    "frames": [
        {"id": None, "kind": "present", "label": "Present", "ordinal": 0,
         "merged_turn_idx": None},
        {"id": 12, "kind": "spatial", "label": "Bubble — Tamamo", "ordinal": 0,
         "parent_frame_id": None, "split_turn_idx": 0, "merged_turn_idx": 1},
    ],
}


def test_a_rejoined_threads_composer_says_it_has_ended(page: Page, ui_base_url: str) -> None:
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    boot = dict(BOOTSTRAP, chats=[{"id": 7, "name": "Home"}])

    def api(route):
        path = urlparse(route.request.url).path
        body = (boot if path == "/api/bootstrap"
                else CHAT if path == "/api/chats/7"
                else {"enabled": False, "bodies": []} if path.endswith("/vitals")
                else {})
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", api)
    page.goto(ui_base_url + "/static/index.html")
    page.evaluate("() => openChat(7)")
    expect(page.locator("#framebar")).to_contain_text("Bubble — Tamamo")
    expect(page.locator("#input")).to_be_enabled()

    page.evaluate("() => switchFrame(12)")
    expect(page.locator("#msgs")).to_contain_text("Tamamo crosses the court.")
    expect(page.locator("#input")).to_be_disabled()
    expect(page.locator("#send")).to_be_disabled()
    expect(page.locator("#input")).to_have_attribute(
        "placeholder", "This thread has ended. Switch to another thread to play on.")

    page.evaluate("() => switchFrame(null)")
    expect(page.locator("#input")).to_be_enabled()
    expect(page.locator("#send")).to_be_enabled()
    expect(page.locator("#input")).not_to_have_attribute(
        "placeholder", "This thread has ended. Switch to another thread to play on.")

    # ...and a story closed while the ended thread was showing leaves no
    # dead composer behind (review of 2026-10-13)
    page.evaluate("() => switchFrame(12)")
    expect(page.locator("#input")).to_be_disabled()
    page.evaluate("() => { S.chat = null; renderChat(); }")
    expect(page.locator("#input")).to_be_enabled()
    expect(page.locator("#send")).to_be_enabled()
    assert not errors, errors
