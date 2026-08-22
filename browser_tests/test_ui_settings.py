"""Reference-first browser contracts for the replacement Settings surface."""

from __future__ import annotations

import json
import re

from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


def _open_settings(
    page: Page,
    ui_base_url: str,
    *,
    width: int = 1440,
    height: int | None = None,
    category: str = "experience",
    bootstrap: dict[str, object] | None = None,
) -> None:
    page.set_viewport_size(
        {"width": width, "height": height or (900 if width >= 1000 else 844)}
    )
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(bootstrap or BOOTSTRAP)
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/settings/{category}")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )


def test_experience_ports_reference_frame_and_applies_local_preferences(
    page: Page, ui_base_url: str
) -> None:
    """Catches a return to the generic Settings placeholder or inert controls."""
    _open_settings(page, ui_base_url)

    expect(page.get_by_role("heading", name="Sonder preferences", level=1)).to_be_visible()
    categories = page.get_by_role("navigation", name="Settings categories")
    expect(categories.get_by_role("link")).to_have_count(6)
    expect(categories.get_by_role("link", name="Experience", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(page.get_by_role("heading", name="Experience", level=2)).to_be_visible()

    shell = page.locator("[data-settings-shell]")
    geometry = shell.evaluate(
        """node => {
          const box = node.getBoundingClientRect();
          const nav = node.querySelector('[data-settings-categories]').getBoundingClientRect();
          return { left: box.left, top: box.top, navWidth: nav.width };
        }"""
    )
    assert abs(geometry["left"] - 72) <= 1
    assert abs(geometry["top"] - 0) <= 1
    assert abs(geometry["navWidth"] - 240) <= 1

    page.get_by_role("button", name="Use Ash and Brass theme").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "ash-brass")
    expect(page.locator(".ui-settings__theme-readout")).to_have_text("Ash and Brass")
    stored = page.evaluate(
        "JSON.parse(localStorage.getItem('sonder.ui-next') || '{}').appearance?.theme"
    )
    assert stored == "ash-brass"

    page.get_by_role("checkbox", name="Reduced motion").check()
    expect(page.locator("html")).to_have_attribute("data-a11y-reduced-motion", "true")

    page.get_by_role("checkbox", name="Accessibility Mode").check()
    expect(page.get_by_role("checkbox", name="Solid surfaces")).to_be_checked()
    expect(page.get_by_role("checkbox", name="Roomy controls")).to_be_checked()
    page.get_by_role("checkbox", name="Solid surfaces").uncheck()
    expect(page.get_by_role("checkbox", name="Accessibility Mode")).not_to_be_checked()


def test_mobile_settings_uses_reference_horizontal_category_staging(
    page: Page, ui_base_url: str
) -> None:
    """Catches desktop sidebar leakage or clipped controls on the phone surface."""
    _open_settings(page, ui_base_url, width=390)

    expect(page).to_have_url(re.compile(r"#/settings/experience$"))
    categories = page.get_by_role("navigation", name="Settings categories")
    expect(categories).to_be_visible()
    geometry = page.evaluate(
        """() => {
          const nav = document.querySelector('[data-settings-categories]');
          const content = document.querySelector('[data-settings-content]');
          const selected = nav.querySelector('[aria-current="page"]');
          return {
            navWidth: nav.getBoundingClientRect().width,
            navScroll: nav.scrollWidth,
            contentLeft: content.getBoundingClientRect().left,
            selectedHeight: selected.getBoundingClientRect().height,
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          };
        }"""
    )
    assert geometry["navWidth"] == 390
    assert geometry["navScroll"] > geometry["navWidth"]
    assert abs(geometry["contentLeft"]) <= 1
    assert geometry["selectedHeight"] >= 44
    assert geometry["overflow"] <= 1
    expect(page.get_by_role("button", name="Use Parchment Night theme")).to_be_visible()


def test_advanced_ports_the_reference_launcher_panel(
    page: Page, ui_base_url: str
) -> None:
    """Catches replacement of the supplied Advanced ledger with generic cards."""
    _open_settings(page, ui_base_url, width=1024, height=600, category="advanced")

    expect(page.get_by_role("heading", name="Advanced", level=2)).to_be_visible()
    expect(page.get_by_text("Prompts, diagnostics, and raw story data", exact=True)).to_be_visible()
    launchers = page.locator("[data-settings-launcher]")
    expect(launchers).to_have_count(4)
    for label in (
        "Prompt editor",
        "Turn details",
        "Raw story data",
        "Raw clothing data",
    ):
        expect(page.get_by_role("button", name=re.compile(f"^{label}"))).to_be_visible()
    expect(
        page.get_by_text("Advanced tools change engine-facing data.", exact=True)
    ).to_be_visible()


def test_ai_connections_ports_provider_ledger_and_tests_the_current_connection(
    page: Page, ui_base_url: str
) -> None:
    """Catches an inert provider card or a synthetic legacy-button bridge."""
    bootstrap = {
        **BOOTSTRAP,
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
            }
        ],
        "provider_presets": {
            "anthropic": "https://api.anthropic.com",
            "ollama": "http://localhost:11434/v1",
        },
        "agent_models": {
            "default": {"provider": 7, "model": "claude-sonnet-4-5"}
        },
    }
    page.route(
        "**/api/providers/7/models",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {"models": ["claude-sonnet-4-5", "claude-haiku-4-5"]}
            ),
        ),
    )
    _open_settings(
        page,
        ui_base_url,
        category="ai-connections",
        bootstrap=bootstrap,
    )

    expect(page.get_by_role("heading", name="AI Connections", level=2)).to_be_visible()
    expect(
        page.locator(".ui-settings__provider-row strong", has_text="Anthropic")
    ).to_be_visible()
    expect(page.get_by_text("Key saved", exact=True)).to_be_visible()
    expect(page.get_by_text("claude-sonnet-4-5", exact=True)).to_be_visible()
    page.get_by_role("button", name="Test Anthropic connection").click()
    expect(
        page.get_by_text("Connection works. 2 models available.", exact=True)
    ).to_be_visible()


def test_ai_connections_stages_provider_connection_and_default_model_save(
    page: Page, ui_base_url: str
) -> None:
    """Catches credential loss, skipped connection tests, or unsaved model choice."""
    bootstrap = {
        **BOOTSTRAP,
        "provider_presets": {
            "anthropic": "https://api.anthropic.com",
            "ollama": "http://localhost:11434/v1",
        },
        "agent_models": {},
    }
    writes: dict[str, object] = {}

    def provider_route(route) -> None:
        writes["provider"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "id": 11,
                    "name": "Anthropic",
                    "kind": "anthropic",
                    "base_url": "https://api.anthropic.com",
                    "has_key": True,
                    "prompt_cache": True,
                    "prompt_cache_default": True,
                    "prompt_cache_locked": False,
                }
            ),
        )

    def models_route(route) -> None:
        route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {"models": ["claude-sonnet-4-5", "claude-haiku-4-5"]}
            ),
        )

    def defaults_route(route) -> None:
        writes["agent_models"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "embeddings_role_changed": False}),
        )

    page.route("**/api/providers", provider_route)
    page.route("**/api/providers/11/models", models_route)
    page.route("**/api/agent_models", defaults_route)
    _open_settings(
        page,
        ui_base_url,
        category="ai-connections",
        bootstrap=bootstrap,
    )

    page.get_by_role("button", name="Add provider").click()
    page.get_by_role("combobox", name="Provider", exact=True).select_option("anthropic")
    page.get_by_label("API key", exact=True).fill("test-key")
    page.get_by_role("button", name="Connect and test").click()
    model = page.get_by_role("combobox", name="Default model")
    expect(model).to_be_visible()
    expect(page.get_by_text("No AI provider is connected.", exact=True)).to_be_hidden()
    expect(page.get_by_text("Not selected", exact=True)).to_be_hidden()
    model.select_option("claude-haiku-4-5")
    page.get_by_role("button", name="Save default model").click()

    expect(
        page.locator(".ui-settings__provider-row strong", has_text="Anthropic")
    ).to_be_visible()
    expect(
        page.locator(".ui-settings__group code", has_text="claude-haiku-4-5")
    ).to_be_visible()
    assert writes["provider"] == {
        "name": "Anthropic",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key": "test-key",
    }
    assert writes["agent_models"] == {
        "default": {"provider": 11, "model": "claude-haiku-4-5"}
    }


def test_ai_connections_edits_provider_without_requiring_the_saved_key(
    page: Page, ui_base_url: str
) -> None:
    """Catches secret readback assumptions or blank-key credential erasure."""
    provider = {
        "id": 7,
        "name": "Anthropic",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com",
        "has_key": True,
        "prompt_cache": True,
        "prompt_cache_default": True,
        "prompt_cache_locked": False,
    }
    bootstrap = {
        **BOOTSTRAP,
        "providers": [provider],
        "provider_presets": {"anthropic": "https://api.anthropic.com"},
        "agent_models": {
            "default": {"provider": 7, "model": "claude-sonnet-4-5"}
        },
    }
    writes: list[dict[str, object]] = []

    def save_route(route) -> None:
        body = route.request.post_data_json
        writes.append(body)
        route.fulfill(
            content_type="application/json",
            body=json.dumps({**provider, **body}),
        )

    page.route("**/api/providers/7", save_route)
    page.route(
        "**/api/providers/7/models",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"models": ["claude-sonnet-4-5"]}),
        ),
    )
    _open_settings(
        page,
        ui_base_url,
        category="ai-connections",
        bootstrap=bootstrap,
    )

    page.get_by_role("button", name="Edit Anthropic connection").click()
    key = page.get_by_label("API key", exact=True)
    expect(key).to_have_value("")
    expect(key).to_have_attribute("placeholder", "Leave blank to keep saved key")
    page.get_by_label("Endpoint", exact=True).fill("https://gateway.example/v1")
    page.get_by_role("button", name="Save and test").click()

    expect(
        page.get_by_text("Connection works. 1 model available.", exact=True)
    ).to_be_visible()
    assert writes == [
        {
            "name": "Anthropic",
            "kind": "anthropic",
            "base_url": "https://gateway.example/v1",
            "api_key": "",
        }
    ]


def test_ai_connections_saves_prompt_cache_and_response_limit(
    page: Page, ui_base_url: str
) -> None:
    """Catches optimistic cache state or a disconnected generation ceiling."""
    provider = {
        "id": 7,
        "name": "Anthropic",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com",
        "has_key": True,
        "prompt_cache": True,
        "prompt_cache_default": True,
        "prompt_cache_locked": False,
    }
    bootstrap = {
        **BOOTSTRAP,
        "providers": [provider],
        "provider_presets": {"anthropic": "https://api.anthropic.com"},
        "agent_models": {
            "default": {"provider": 7, "model": "claude-sonnet-4-5"}
        },
        "max_output_tokens": 20000,
        "max_output_tokens_bounds": {"min": 1024, "max": 128000, "default": 20000},
    }
    writes: dict[str, object] = {}

    def cache_route(route) -> None:
        writes["cache"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "prompt_cache": True}),
        )

    def limit_route(route) -> None:
        writes["limit"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "value": 32000}),
        )

    page.route("**/api/providers/7/prompt_cache", cache_route)
    page.route("**/api/max_output_tokens", limit_route)
    _open_settings(
        page,
        ui_base_url,
        category="ai-connections",
        bootstrap=bootstrap,
    )

    cache = page.get_by_role("checkbox", name="Cache repeated prompts for Anthropic")
    expect(cache).to_be_checked()
    cache.uncheck()
    expect(cache).to_be_checked()
    expect(page.get_by_text("Prompt caching remains on for Anthropic.", exact=True)).to_be_visible()

    limit = page.get_by_role("spinbutton", name="Maximum output tokens")
    expect(limit).to_have_value("20000")
    limit.fill("32000")
    page.get_by_role("button", name="Save response limit").click()
    expect(limit).to_have_value("32000")
    expect(page.get_by_text("Response limit saved: 32,000 tokens.", exact=True)).to_be_visible()

    assert writes == {"cache": {"enabled": False}, "limit": {"value": "32000"}}


def test_ai_connections_saves_advanced_role_models_without_flattening_configs(
    page: Page, ui_base_url: str
) -> None:
    """Catches a cosmetic role disclosure or loss of untouched role settings."""
    bootstrap = {
        **BOOTSTRAP,
        "providers": [
            {"id": 7, "name": "Anthropic", "kind": "anthropic", "base_url": "", "has_key": True},
            {"id": 8, "name": "OpenRouter", "kind": "openrouter", "base_url": "", "has_key": True},
        ],
        "provider_presets": {},
        "roles": ["default", "director", "embeddings"],
        "agent_models": {
            "default": {"provider": 7, "model": "claude-sonnet-4-5", "temperature": 0.7},
            "director": {"provider": 7, "model": "claude-opus-4-1", "top_p": 0.9},
            "embeddings": {"provider": 8, "model": "openai/text-embedding-3-small"},
        },
        "reasoning_effort": {"director": "high"},
        "reasoning_effort_levels": ["off", "minimal", "low", "medium", "high"],
        "max_output_tokens": 20000,
        "max_output_tokens_bounds": {"min": 1024, "max": 128000, "default": 20000},
    }
    writes: dict[str, object] = {}

    def models_route(route) -> None:
        writes["models"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "embeddings_role_changed": True}),
        )

    def effort_route(route) -> None:
        writes["efforts"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "reasoning_effort": {"embeddings": "low"}}),
        )

    page.route("**/api/agent_models", models_route)
    page.route("**/api/reasoning_effort", effort_route)
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    page.get_by_text("Advanced model assignments", exact=True).click()
    page.get_by_role("combobox", name="Provider for Director").select_option("")
    page.get_by_role("combobox", name="Provider for Embeddings").select_option("8")
    page.get_by_role("textbox", name="Model for Embeddings").fill("perplexity/pplx-embed-v1-0.6b")
    page.get_by_role("combobox", name="Reasoning effort for Embeddings").select_option("low")
    page.get_by_role("button", name="Save model assignments").click()

    expect(page.get_by_text("Model assignments saved.", exact=True)).to_be_visible()
    expect(page.get_by_text("Memory vectors need rebuilding for the new embeddings model.", exact=True)).to_be_visible()
    assert writes["models"] == {
        "default": {"provider": 7, "model": "claude-sonnet-4-5", "temperature": 0.7},
        "embeddings": {"provider": 8, "model": "perplexity/pplx-embed-v1-0.6b"},
    }
    assert writes["efforts"] == {"efforts": {"embeddings": "low"}}


def test_ai_connections_saves_backdrop_and_ambience_sources(
    page: Page, ui_base_url: str
) -> None:
    """Catches media controls that lose saved secrets or bypass their current APIs."""
    bootstrap = {
        **BOOTSTRAP,
        "providers": [
            {"id": 8, "name": "NanoGPT", "kind": "nanogpt", "base_url": "", "has_key": True}
        ],
        "provider_presets": {},
        "agent_models": {},
        "roles": ["default"],
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
    writes: dict[str, object] = {}

    def record(name: str, body: dict[str, object]):
        def route_handler(route) -> None:
            writes[name] = route.request.post_data_json
            route.fulfill(content_type="application/json", body=json.dumps(body))

        return route_handler

    page.route("**/api/image_model", record("image", {"ok": True}))
    page.route("**/api/backdrops", record("backdrops", {"enabled": True, "continuity": True}))
    page.route("**/api/ambience", record("ambience", bootstrap["ambience"]))
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    page.get_by_role("textbox", name="Backdrop image model").fill("flux-ultra")
    page.get_by_role("checkbox", name="Keep room images visually consistent").check()
    page.get_by_role("button", name="Save backdrop settings").click()
    expect(page.get_by_text("Backdrop settings saved.", exact=True)).to_be_visible()

    key = page.get_by_label("Freesound API key", exact=True)
    expect(key).to_have_value("")
    expect(key).to_have_attribute("placeholder", "Leave blank to keep saved key")
    page.get_by_role("checkbox", name="Allow NonCommercial sounds").check()
    page.get_by_role("button", name="Save ambience settings").click()
    expect(page.get_by_text("Ambience settings saved.", exact=True)).to_be_visible()

    assert writes["image"] == {"provider": 8, "model": "flux-ultra", "size": "1536x1024"}
    assert writes["backdrops"] == {"enabled": True, "continuity": True}
    assert writes["ambience"] == {
        "enabled": True,
        "source": "freesound",
        "library": "",
        "freesound_key": "",
        "licenses": ["Creative Commons 0", "Attribution", "Attribution NonCommercial"],
    }
