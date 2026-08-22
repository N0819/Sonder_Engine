"""Capture deterministic WP10 host authentication review images."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp10" / "screenshots"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def status(page, setup_required: bool) -> None:
    page.route(
        "**/api/auth/status",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"authenticated": False, "setup_required": setup_required}),
        ),
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        url = f"http://{host}:{port}/static/login.html"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            login = browser.new_page(viewport={"width": 1440, "height": 900})
            status(login, False)
            login.goto(url)
            login.get_by_role("heading", name="Sign in").wait_for()
            login.get_by_label("Username", exact=True).last.fill("storyteller")
            login.get_by_label("Password", exact=True).fill("password")
            login.screenshot(path=OUTPUT / "login-1440.png")

            setup = browser.new_page(viewport={"width": 1440, "height": 900})
            status(setup, True)
            setup.goto(url)
            setup.get_by_role("heading", name="Create your host account").wait_for()
            setup.screenshot(path=OUTPUT / "setup-1440.png")

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            status(mobile, False)
            mobile.goto(url)
            mobile.get_by_role("heading", name="Sign in").wait_for()
            mobile.screenshot(path=OUTPUT / "login-390.png")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
