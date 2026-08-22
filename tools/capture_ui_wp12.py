"""Capture deterministic WP12 theme and extension compatibility evidence."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

from capture_ui_settings import BOOTSTRAP


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp12" / "screenshots"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


EXTENSIONS = {
    "extensions": [
        {
            "id": "cohesion-demo",
            "name": "Cohesion",
            "version": "0.1.0",
            "description": "A classic-script compatibility fixture.",
            "provenance": "local:bundled",
            "trust": "code",
            "capabilities": {"ui": {"js": "ui/panel.js"}},
            "disclosures": ["Read story state", "Register a contained settings view"],
            "enabled": True,
        },
        {
            "id": "overlay-demo",
            "name": "Overlay",
            "version": "0.2.0",
            "description": "A native module destination fixture.",
            "provenance": "local:bundled",
            "trust": "code",
            "capabilities": {"ui": {"api": 2, "module": "ui/index.js"}},
            "disclosures": ["Read story state", "Register a contained destination"],
            "enabled": True,
        },
        {
            "id": "campaign-demo",
            "name": "Campaign",
            "version": "0.3.0",
            "description": "A native module Play tool fixture.",
            "provenance": "local:bundled",
            "trust": "code",
            "capabilities": {"ui": {"api": 2, "module": "ui/index.js"}},
            "disclosures": ["Read story state", "Write extension-owned story data"],
            "enabled": False,
        },
    ],
    "load_errors": [],
    "safe_mode": False,
    "ext_api": 1,
    "host_capabilities": ["ui-v1", "ui-v2"],
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.route(
                "**/api/bootstrap",
                lambda route: route.fulfill(
                    content_type="application/json", body=json.dumps(BOOTSTRAP)
                ),
            )
            page.route(
                "**/api/extensions",
                lambda route: route.fulfill(
                    content_type="application/json", body=json.dumps(EXTENSIONS)
                ),
            )
            root = f"http://{host}:{port}/static/ui-next.html"
            page.goto(f"{root}#/settings/experience")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            for slug, label in (
                ("carbon-signal", "Carbon Signal"),
                ("ash-brass", "Ash and Brass"),
                ("midnight-ink", "Midnight Ink"),
                ("parchment-night", "Parchment Night"),
            ):
                page.get_by_role("button", name=f"Use {label} theme").click()
                page.screenshot(path=OUTPUT / f"settings-theme-{slug}-1440.png", full_page=True)

            page.get_by_role("combobox", name="Legacy themes").select_option("tavern")
            page.screenshot(path=OUTPUT / "settings-theme-legacy-tavern-1440.png", full_page=True)

            page.goto(f"{root}#/settings/add-ons")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_text("Extension UI API 2", exact=False).first.wait_for()
            page.screenshot(path=OUTPUT / "settings-add-ons-v1-v2-1440.png", full_page=True)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
