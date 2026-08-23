"""Capture deterministic WP09 New Story review images."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp09" / "screenshots"

BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "personas": [{"id": 3, "name": "Mina Vale", "sheet": "{}"}],
    "characters": [{"id": 7, "name": "Orin Pike", "sheet": "{}"}],
    "lorebooks": [{"id": 9, "name": "The Rain Atlas"}],
    "providers": [{"id": 2, "name": "Local", "kind": "openai"}],
    "agent_models": {"default": {"provider": "Local", "model": "small"}},
    "language_packs": [{"id": "en", "name": "English", "native_name": "English", "story": True}],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def routes(page) -> None:
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP)),
    )
    page.route(
        "**/api/library?*",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "items": [],
                    "facets": {"types": {}, "scopes": {}},
                    "page": {"offset": 0, "limit": 100, "returned": 0, "total": 0},
                    "query": {},
                }
            ),
        ),
    )


def open_choice(page, url: str) -> None:
    page.goto(f"{url}/static/ui-next.html#/library")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    page.get_by_role("button", name="New story", exact=True).first.click()
    page.get_by_role("heading", name="Choose how to begin").wait_for()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        url = f"http://{host}:{port}"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            routes(page)
            open_choice(page, url)
            page.screenshot(path=OUTPUT / "new-story-choice-1440.png")

            page.get_by_role("button", name="Describe a story").click()
            page.get_by_label("Story name").fill("The Rain Ledger")
            page.get_by_label("Opening situation").fill("A courier arrives at a station where every clock has stopped.")
            page.screenshot(path=OUTPUT / "new-story-details-1440.png")
            page.get_by_role("button", name="Choose story material").click()
            page.get_by_label("Player persona").select_option("3")
            page.get_by_text("Orin Pike", exact=True).click()
            page.get_by_text("The Rain Atlas", exact=True).click()
            location = page.locator("details.ui-lived-location")
            location.locator("summary").click()
            location.get_by_role("checkbox", name="Prepare a lived location").check()
            location.get_by_label("Location brief").fill("A rain station where couriers live between routes")
            location.get_by_label("Recent history").select_option("168")
            page.get_by_label("History route for Orin Pike").select_option("resident")
            location.scroll_into_view_if_needed()
            page.screenshot(path=OUTPUT / "new-story-lived-location-1440.png")
            page.locator(".ui-new-story__asset-grid").scroll_into_view_if_needed()
            page.screenshot(path=OUTPUT / "new-story-assets-1440.png")
            page.get_by_role("button", name="Review story").click()
            page.screenshot(path=OUTPUT / "new-story-review-1440.png")

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            routes(mobile)
            open_choice(mobile, url)
            mobile.screenshot(path=OUTPUT / "new-story-choice-390.png")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
