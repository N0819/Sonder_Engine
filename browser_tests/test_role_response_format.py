"""The models panel's per-role response format.

A role's format sits beside its reasoning effort: the enforced grammar, the
advisory flag, or nothing. The prose encoder's unset row goes without the
grammar by a measured default (`providers.ROLE_DEFAULT_FORMATS`), so that
row names the default it inherits -- an inheritance nobody can see is a
trap -- and a choice made in the panel is what the save sends.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def _bootstrap() -> dict:
    return {
        **BOOTSTRAP,
        "providers": [{"id": 3, "name": "openrouter", "kind": "openrouter",
                       "base_url": "https://openrouter.ai/api/v1", "api_key": "",
                       "enabled": 1}],
        "provider_presets": {"openrouter": {"base_url": "https://openrouter.ai/api/v1"}},
        "roles": ["default", "director_specialist", "narrator"],
        "role_fallbacks": {},
        "agent_models": {"default": {"provider": 3, "model": "z-ai/glm-5.2"}},
        "reasoning_effort_levels": ["off", "minimal", "low", "medium", "high"],
        "response_format": {"narrator": "json_object"},
        "response_format_levels": ["json_schema", "json_object", "none"],
        "response_format_defaults": {"director_specialist": "none"},
    }


def test_each_role_shows_its_format_and_the_save_sends_the_choice(
        page: Page, ui_base_url: str) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    puts: dict[str, dict] = {}
    boot = _bootstrap()

    def handle(route) -> None:
        request = route.request
        path = urlparse(request.url).path
        if request.method == "PUT":
            puts[path] = json.loads(request.post_data or "{}")
        body = boot if path == "/api/bootstrap" else {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", handle)
    page.goto(f"{ui_base_url}/static/index.html")
    expect(page.locator("#send")).to_be_visible()
    page.locator("#b-api").click()
    expect(page.locator("#modaltitle")).to_have_text("API connections")

    formats = page.locator("#modal select[title='Response format']")
    expect(formats).to_have_count(3)
    encoder = page.locator("#modal .card", has_text="director_specialist") \
        .locator("select[title='Response format']")
    narrator = page.locator("#modal .card", has_text="narrator") \
        .locator("select[title='Response format']")
    # The inherited, measured default is named on the row that has one.
    expect(encoder.locator("option").first).to_have_text("format: none (measured default)")
    expect(encoder).to_have_value("")
    expect(narrator).to_have_value("json_object")

    encoder.select_option("json_schema")
    page.get_by_role("button", name="Save all").click()
    expect(page.locator("#modal")).to_be_hidden()
    assert puts["/api/response_format"] == {
        "formats": {"director_specialist": "json_schema", "narrator": "json_object"}}
    assert errors == []
