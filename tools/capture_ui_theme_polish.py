"""Capture deterministic review evidence for Settings and shared control polish."""

from __future__ import annotations

import json
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, sync_playwright

from capture_ui_library import route_case, wait_for_case
from capture_ui_settings import BOOTSTRAP


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp17" / "screenshots"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_root():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(_QuietHandler, directory=str(ROOT)),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _fulfill(route: Route, payload: object, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False),
    )


def _settings_routes(page: Page) -> None:
    extensions = {
        "extensions": [
            {
                "id": "campaign",
                "name": "Campaign (demo)",
                "version": "0.1.0",
                "description": "Adds campaign structure and persistent campaign context.",
                "provenance": "local",
                "trust": "code",
                "disclosures": ["Read story state", "Write extension-owned story data"],
                "enabled": False,
                "updatable": False,
                "capabilities": {"ui": {"api": 2}},
            },
            {
                "id": "directive",
                "name": "Directive",
                "version": "0.8.2",
                "description": "Adds mission tools and Director connections.",
                "provenance": "git:local",
                "trust": "code",
                "disclosures": ["Read story state", "Register story tools"],
                "enabled": True,
                "updatable": True,
                "capabilities": {"ui": {"api": 2}},
            },
        ],
        "load_errors": [],
        "safe_mode": False,
        "ext_api": 2,
        "host_capabilities": ["ui"],
    }

    def handler(route: Route) -> None:
        request = route.request
        path = urlparse(request.url).path
        if path == "/api/bootstrap":
            payload = {
                **BOOTSTRAP,
                "exemplars": [
                    "Rain worried the station glass while the last train waited.",
                    "The city held its breath, then let the signal pass.",
                ],
                "exemplar_bounds": {"max_count": 4, "max_chars": 2000},
            }
            _fulfill(route, payload)
            return
        if path == "/api/extensions":
            _fulfill(route, extensions)
            return
        if path == "/api/maintenance/checkpoints":
            _fulfill(route, {
                "checkpoints": 128,
                "legacy": 7,
                "bytes": 340_000_000,
                "legacy_bytes": 210_000_000,
                "progress": {"running": False},
            })
            return
        if path == "/api/memory/embeddings":
            _fulfill(route, {
                "model_key": "openai:text-embedding-3-small",
                "total": 263,
                "current": 252,
                "stale": 11,
                "progress": {"running": False},
            })
            return
        if path == "/api/chats/5/living_world":
            _fulfill(route, {"living_world": {}, "approaches": []})
            return
        if path == "/api/chats/5/world":
            _fulfill(route, {"rooms": {}, "positions": {}})
            return
        if request.method in {"POST", "PUT", "DELETE"}:
            _fulfill(route, {"ok": True})
            return
        _fulfill(route, {})

    page.route("**/api/**", handler)


def _ready(page: Page) -> None:
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    page.wait_for_function("document.fonts.status === 'loaded'")
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )


def _capture(page: Page, name: str) -> None:
    page.screenshot(path=OUTPUT / f"{name}.png", animations="disabled")


def _stage_at_top(locator) -> None:
    locator.evaluate("node => node.scrollIntoView({block: 'start', inline: 'nearest'})")


def _goto_settings(page: Page, base_url: str, section: str) -> None:
    response = page.goto(f"{base_url}/static/ui-next.html#/settings/{section}")
    if response is not None and not response.ok:
        raise RuntimeError(f"Settings failed to load: {section}")
    _ready(page)


def capture_settings(base_url: str, browser) -> None:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    _settings_routes(page)

    _goto_settings(page, base_url, "experience")
    page.get_by_role("searchbox", name="Search settings").fill("theme")
    _capture(page, "settings-search-1440")
    page.get_by_role("searchbox", name="Search settings").fill("")

    custom = page.locator("[data-custom-theme-editor]")
    custom.scroll_into_view_if_needed()
    _capture(page, "custom-theme-editor-1440")

    page.get_by_role("button", name="Use Neon Circuit theme").click()
    page.locator('[data-theme-choice="neon-circuit"]').scroll_into_view_if_needed()
    _capture(page, "neon-circuit-1440")

    page.get_by_role("button", name="Use Modern Slate theme").click()
    page.locator('[data-theme-choice="modern-slate"]').scroll_into_view_if_needed()
    _capture(page, "modern-slate-1440")

    custom.scroll_into_view_if_needed()
    page.get_by_role("button", name="Edit Accent color").click()
    page.get_by_role("dialog", name="Choose Accent color").wait_for()
    _capture(page, "custom-color-dialog-1440")
    page.get_by_role("button", name="Cancel", exact=True).click()

    _goto_settings(page, base_url, "content")
    _stage_at_top(page.get_by_text("Narrator voice examples", exact=True))
    _capture(page, "narrator-tabs-1440")

    _goto_settings(page, base_url, "add-ons")
    page.get_by_text("Campaign (demo)", exact=True).wait_for()
    _capture(page, "add-ons-1440")

    _goto_settings(page, base_url, "maintenance")
    page.get_by_text("7 of 128 checkpoints use the legacy format.", exact=True).wait_for()
    _capture(page, "maintenance-1440")

    page.set_viewport_size({"width": 390, "height": 844})
    _goto_settings(page, base_url, "experience")
    custom = page.locator("[data-custom-theme-editor]")
    custom.scroll_into_view_if_needed()
    _capture(page, "custom-theme-editor-390")
    page.get_by_role("button", name="Edit Accent color").click()
    page.get_by_role("dialog", name="Choose Accent color").wait_for()
    _capture(page, "custom-color-dialog-390")
    page.get_by_role("button", name="Cancel", exact=True).click()

    _goto_settings(page, base_url, "content")
    _stage_at_top(page.get_by_text("Narrator voice examples", exact=True))
    _capture(page, "narrator-tabs-390")

    page.set_viewport_size({"width": 844, "height": 390})
    _goto_settings(page, base_url, "content")
    _stage_at_top(page.get_by_text("Narrator voice examples", exact=True))
    _capture(page, "narrator-tabs-844x390")
    page.close()


def capture_library(base_url: str, browser) -> None:
    for name, width, height in (
        ("library-controls-1440", 1440, 900),
        ("library-controls-390", 390, 844),
    ):
        page = browser.new_page(viewport={"width": width, "height": height})
        route_case(page, "normal", "en")
        response = page.goto(f"{base_url}/static/ui-next.html#/library")
        if response is None or not response.ok:
            raise RuntimeError(f"Library failed to load: {name}")
        wait_for_case(page, "normal")
        page.wait_for_function("document.fonts.status === 'loaded'")
        page.evaluate(
            "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
        )
        _capture(page, name)
        page.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        capture_settings(base_url, browser)
        capture_library(base_url, browser)
        browser.close()
    print(f"Wrote theme-polish screenshots to {OUTPUT}")


if __name__ == "__main__":
    main()
