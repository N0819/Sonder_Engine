"""Capture deterministic WP11 guest entry and Play review images."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp11" / "screenshots"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def respond(route, status: int, payload: dict) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))


def state() -> dict:
    return {
        "chat_name": "Ash and Lantern",
        "persona_name": "Mara",
        "next_idx": 3,
        "turns": [
            {
                "player_input": "I push open the blue door.",
                "prose": "Rain whispers against the lantern glass. Beyond the threshold, the old observatory waits in a hush of dust and amber light.",
                "stale": False,
                "stale_from": None,
            },
            {
                "player_input": "I call into the dark.",
                "prose": "A chair scrapes somewhere above. Then a careful voice answers, close enough to hear but not yet close enough to see.",
                "stale": False,
                "stale_from": None,
            },
        ],
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        url = f"http://{host}:{port}/static/guest.html"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            join = browser.new_page(viewport={"width": 430, "height": 932})
            join.route("**/api/guest/state", lambda route: respond(route, 403, {"detail": "Guest session required"}))
            join.goto(f"{url}?code=ashen7q")
            join.get_by_role("heading", name="Enter your join code").wait_for()
            join.screenshot(path=OUTPUT / "guest-join-430.png")

            play = browser.new_page(viewport={"width": 430, "height": 932})
            play.route("**/api/guest/state", lambda route: respond(route, 200, state()))
            play.goto(url)
            play.get_by_text("Rain whispers against the lantern glass.", exact=False).wait_for()
            play.get_by_label("Your action or speech").fill("I climb the narrow stairs.")
            play.screenshot(path=OUTPUT / "guest-play-mobile.png")

            desktop = browser.new_page(viewport={"width": 1440, "height": 900})
            desktop.route("**/api/guest/state", lambda route: respond(route, 200, state()))
            desktop.goto(url)
            desktop.get_by_text("Rain whispers against the lantern glass.", exact=False).wait_for()
            desktop.screenshot(path=OUTPUT / "guest-play-1440.png")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
