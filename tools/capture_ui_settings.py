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
    "chats": [{"id": 5, "title": "The Glass District"}],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "language_packs": [{"id": "en", "name": "English"}],
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
    "default_prompts": {"director": "Adjudicate the player's action against established world state."},
    "prompt_presets": {
        "Measured": {
            "language": "en",
            "prompts": {"director": "Resolve only what this beat establishes. Preserve uncertainty."},
        }
    },
    "active_preset": "Measured",
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
            page.route(
                "**/api/memory/embeddings",
                lambda route: route.fulfill(
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "model_key": "openai:text-embedding-3-small",
                            "total": 263,
                            "current": 252,
                            "stale": 11,
                            "progress": {"running": False},
                        }
                    ),
                ),
            )
            page.route(
                "**/api/chats/5/living_world",
                lambda route: route.fulfill(
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "living_world": {
                                "routine_residue": "ceiling",
                                "rumor_ledger": "ceiling",
                            },
                            "approaches": [
                                {
                                    "approach": "routine_residue",
                                    "label": "Routine and residue",
                                    "value": "ceiling",
                                    "effective": "floor",
                                    "cost": "floor: free; ceiling: one call per familiar place",
                                    "depths": [
                                        {"value": "floor", "description": "Rooms drift on the clock while unwatched.", "built": True, "requires": "deterministic", "permitted": True},
                                        {"value": "ceiling", "description": "Familiar places advance their social life.", "built": False, "requires": "stochastic", "permitted": True},
                                    ],
                                },
                                {
                                    "approach": "rumor_ledger",
                                    "label": "Rumor ledger",
                                    "value": "ceiling",
                                    "effective": "floor",
                                    "cost": "floor: free; ceiling: one small call per posted artifact",
                                    "depths": [
                                        {"value": "floor", "description": "News travels inside actual witnesses.", "built": True, "requires": "deterministic", "permitted": True},
                                        {"value": "ceiling", "description": "Notices receive posted wording.", "built": True, "requires": "stochastic", "permitted": False},
                                    ],
                                },
                            ],
                        }
                    ),
                ),
            )
            page.route(
                "**/api/chats/5/world",
                lambda route: route.fulfill(
                    content_type="application/json",
                    body=json.dumps({"rooms": {"atrium": {"name": "Atrium"}}, "positions": {"Player": "atrium"}}),
                ),
            )
            page.goto(
                f"http://{host}:{port}/static/ui-next.html#/settings/experience"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.locator("[data-settings-content]").evaluate(
                "node => { node.scrollTop = 0; }"
            )
            page.screenshot(path=OUTPUT / "settings-1440.png")
            page.get_by_role("navigation", name="Settings categories").hover()
            page.mouse.wheel(0, 10_000)
            page.wait_for_function(
                "document.querySelector('[data-settings-content]').scrollTop > 0"
            )
            page.screenshot(path=OUTPUT / "settings-experience-scrolled-1440.png")

            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(
                f"http://{host}:{port}/static/ui-next.html#/settings/experience"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.locator("[data-settings-content]").evaluate(
                "node => { node.scrollTop = 0; }"
            )
            page.screenshot(path=OUTPUT / "settings-390.png")
            page.get_by_role("navigation", name="Settings categories").hover()
            page.mouse.wheel(0, 10_000)
            page.wait_for_function(
                "document.querySelector('[data-settings-content]').scrollTop > 0"
            )
            page.screenshot(path=OUTPUT / "settings-experience-scrolled-390.png")

            page.set_viewport_size({"width": 1024, "height": 600})
            page.goto(
                f"http://{host}:{port}/static/ui-next.html#/settings/experience"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.locator("[data-settings-content]").evaluate(
                "node => { node.scrollTop = 0; }"
            )
            page.get_by_role("navigation", name="Settings categories").hover()
            page.mouse.wheel(0, 10_000)
            page.wait_for_function(
                "document.querySelector('[data-settings-content]').scrollTop > 0"
            )
            page.screenshot(path=OUTPUT / "settings-experience-scrolled-1024x600.png")

            page.set_viewport_size({"width": 1440, "height": 900})
            page.goto(
                f"http://{host}:{port}/static/ui-next.html#/settings/ai-connections"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.screenshot(path=OUTPUT / "settings-ai-1440.png")

            page.goto(
                f"http://{host}:{port}/static/ui-next.html#/settings/ai-connections?control=models"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.get_by_role("heading", name="Model assignments", level=2).wait_for()
            page.screenshot(path=OUTPUT / "settings-ai-models-1440.png")

            page.goto(
                f"http://{host}:{port}/static/ui-next.html#/settings/ai-connections"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.get_by_text("Scene backdrops", exact=True).scroll_into_view_if_needed()
            page.screenshot(path=OUTPUT / "settings-ai-media-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/content")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.screenshot(path=OUTPUT / "settings-content-1440.png")
            page.get_by_text("Living world", exact=True).scroll_into_view_if_needed()
            page.screenshot(path=OUTPUT / "settings-content-living-world-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/add-ons")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_text("Directive", exact=True).wait_for()
            page.screenshot(path=OUTPUT / "settings-add-ons-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/maintenance")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_text("7 of 128 checkpoints use the legacy format.", exact=True).wait_for()
            page.screenshot(path=OUTPUT / "settings-maintenance-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/advanced?tool=prompts")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_role("textbox", name="Director prompt").wait_for()
            page.screenshot(path=OUTPUT / "settings-advanced-prompts-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/advanced?tool=story-data")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_role("textbox", name="Raw story data JSON").wait_for()
            page.screenshot(path=OUTPUT / "settings-advanced-story-data-1440.png")

            page.goto(f"http://{host}:{port}/static/ui-next.html#/settings/experience")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.get_by_role("searchbox", name="Search settings").fill("api key")
            page.get_by_role("button", name="Provider credentials · AI Connections").wait_for()
            page.screenshot(path=OUTPUT / "settings-search-1440.png")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
