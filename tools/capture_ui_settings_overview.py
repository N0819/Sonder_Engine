"""Capture deterministic review evidence for the grouped Settings overview."""

from __future__ import annotations

import json
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp18" / "screenshots"
NAVIGATION_OUTPUT = (
    ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp19" / "screenshots"
)
BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [
        {"id": 7, "name": "Anthropic", "kind": "anthropic", "has_key": True},
        {"id": 8, "name": "Local", "kind": "ollama", "has_key": False},
    ],
    "agent_models": {"default": {"provider": 7, "model": "claude-sonnet-4-5"}},
    "language_packs": [],
    "extensions": [
        {"id": "campaign", "name": "Campaign (demo)", "enabled": True},
        {"id": "overlay", "name": "Overlay (demo)", "enabled": False},
    ],
    "extension_errors": [],
    "extension_lanes": [],
}


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_root():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(_QuietHandler, directory=str(ROOT))
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


def route_api(route: Route) -> None:
    if route.request.url.endswith("/api/bootstrap"):
        route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP))
        return
    route.fulfill(content_type="application/json", body="{}")


def ready(page) -> None:
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    page.wait_for_function("document.fonts.status === 'loaded'")
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )


def capture(browser, base_url: str, name: str, width: int, height: int) -> None:
    page = browser.new_page(viewport={"width": width, "height": height})
    page.route("**/api/**", route_api)
    response = page.goto(f"{base_url}/static/ui-next.html#/settings")
    if response is None or not response.ok:
        raise RuntimeError(f"Settings overview failed to load: {name}")
    ready(page)
    page.screenshot(path=OUTPUT / f"{name}.png", animations="disabled")
    page.close()


def capture_navigation_transition(browser, base_url: str) -> None:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.route("**/api/**", route_api)
    page.goto(f"{base_url}/static/ui-next.html#/settings")
    ready(page)
    page.get_by_role("link", name="AI Connections").click()
    page.get_by_role("heading", name="AI Connections", exact=True).wait_for()
    page.screenshot(
        path=NAVIGATION_OUTPUT / "overview-to-detail-1440.png",
        animations="disabled",
    )
    page.go_back()
    page.locator('[data-settings-overview-row="theme"]').wait_for()
    page.screenshot(
        path=NAVIGATION_OUTPUT / "overview-return-1440.png",
        animations="disabled",
    )
    page.close()


def capture_detail_navigation(
    browser,
    base_url: str,
    name: str,
    width: int,
    height: int,
    *,
    category: str,
    expand_group: str | None = None,
) -> None:
    page = browser.new_page(viewport={"width": width, "height": height})
    page.route("**/api/**", route_api)
    response = page.goto(f"{base_url}/static/ui-next.html#/settings/{category}")
    if response is None or not response.ok:
        raise RuntimeError(f"Settings detail failed to load: {name}")
    ready(page)
    if expand_group:
        page.get_by_role("button", name=expand_group, exact=True).click()
    page.screenshot(path=NAVIGATION_OUTPUT / f"{name}.png", animations="disabled")
    page.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    NAVIGATION_OUTPUT.mkdir(parents=True, exist_ok=True)
    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        capture(browser, base_url, "overview-1440", 1440, 900)
        capture(browser, base_url, "overview-1024", 1024, 768)
        capture(browser, base_url, "overview-390", 390, 844)
        capture(browser, base_url, "overview-844x390", 844, 390)
        capture_navigation_transition(browser, base_url)
        capture_detail_navigation(
            browser, base_url, "desktop-1440", 1440, 900, category="experience"
        )
        capture_detail_navigation(
            browser, base_url, "tablet-1024", 1024, 768, category="ai-connections"
        )
        capture_detail_navigation(
            browser, base_url, "mobile-390", 390, 844, category="experience"
        )
        capture_detail_navigation(
            browser,
            base_url,
            "mobile-story-host-390",
            390,
            844,
            category="experience",
            expand_group="Story & host",
        )
        capture_detail_navigation(
            browser,
            base_url,
            "landscape-844x390",
            844,
            390,
            category="advanced",
        )
        capture_detail_navigation(
            browser,
            base_url,
            "tablet-short-1024x600",
            1024,
            600,
            category="advanced",
        )
        browser.close()
    print(f"Wrote Settings overview screenshots to {OUTPUT}")
    print(f"Wrote Settings navigation screenshots to {NAVIGATION_OUTPUT}")


if __name__ == "__main__":
    main()
