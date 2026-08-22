"""Capture deterministic reference-review images for the replacement Settings UI."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp08" / "screenshots"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
    "providers": [
        {
            "id": 7,
            "name": "Anthropic",
            "kind": "anthropic",
            "base_url": "https://api.anthropic.com",
            "has_key": True,
            "prompt_cache": True,
            "prompt_cache_default": True,
            "prompt_cache_locked": False,
        },
        {
            "id": 8,
            "name": "OpenRouter",
            "kind": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "has_key": True,
            "prompt_cache": False,
            "prompt_cache_default": False,
            "prompt_cache_locked": False,
        },
    ],
    "provider_presets": {
        "anthropic": "https://api.anthropic.com",
        "openrouter": "https://openrouter.ai/api/v1",
    },
    "roles": ["default", "director", "narrator", "embeddings"],
    "agent_models": {
        "default": {"provider": 7, "model": "claude-sonnet-4-5"},
        "director": {"provider": 7, "model": "claude-opus-4-1"},
        "embeddings": {"provider": 8, "model": "openai/text-embedding-3-small"},
    },
    "reasoning_effort": {"director": "high"},
    "reasoning_effort_levels": ["off", "minimal", "low", "medium", "high"],
    "max_output_tokens": 20000,
    "max_output_tokens_bounds": {"min": 1024, "max": 128000, "default": 20000},
    "image_model": {"provider": 8, "model": "flux-pro", "size": "1536x1024"},
    "backdrops_enabled": True,
    "backdrop_continuity": False,
    "ambience": {
        "enabled": True,
        "source": "freesound",
        "library": "",
        "has_key": True,
        "licenses": ["Creative Commons 0", "Attribution"],
    },
    "ambience_licenses": [
        "Creative Commons 0",
        "Attribution",
        "Attribution NonCommercial",
    ],
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
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.route(
                "**/api/bootstrap",
                lambda route: route.fulfill(
                    content_type="application/json", body=json.dumps(BOOTSTRAP)
                ),
            )
            page.route(
                "**/api/extensions",
                lambda route: route.fulfill(
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "extensions": [
                                {
                                    "id": "directive",
                                    "name": "Directive",
                                    "version": "0.8.2",
                                    "description": "Adds campaign and mission tools to Sonder stories.",
                                    "provenance": "git:local",
                                    "trust": "code",
                                    "disclosures": [
                                        "Read story state",
                                        "Write extension-owned story data",
                                        "Register story tools",
                                    ],
                                    "enabled": True,
                                    "updatable": True,
                                }
                            ],
                            "load_errors": [],
                            "safe_mode": False,
                            "ext_api": 1,
                            "host_capabilities": ["ui"],
                        }
                    ),
                ),
            )
            page.route(
                "**/api/maintenance/checkpoints",
                lambda route: route.fulfill(
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "checkpoints": 128,
                            "legacy": 7,
                            "bytes": 340_000_000,
                            "legacy_bytes": 210_000_000,
                            "progress": {"running": False},
                        }
                    ),
                ),
            )
            page.goto(
                f"http://{host}:{port}/static/ui-next.html#/settings/ai-connections"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.screenshot(path=OUTPUT / "settings-ai-1440.png")

            page.get_by_text("Advanced model assignments", exact=True).click()
            page.locator(".ui-settings__model-assignments").scroll_into_view_if_needed()
            page.screenshot(path=OUTPUT / "settings-ai-models-1440.png")

            page.get_by_text("Scene backdrops", exact=True).scroll_into_view_if_needed()
            page.screenshot(path=OUTPUT / "settings-ai-media-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/content")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.screenshot(path=OUTPUT / "settings-content-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/add-ons")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_text("Directive", exact=True).wait_for()
            page.screenshot(path=OUTPUT / "settings-add-ons-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/maintenance")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_text("7 of 128 checkpoints use the legacy format.", exact=True).wait_for()
            page.screenshot(path=OUTPUT / "settings-maintenance-1440.png")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
