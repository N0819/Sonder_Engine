"""The settings panels write what the host meant and say what happened.

Audit 2026-11-01, in a real browser over a mocked API:

* `frontend_settings_world` F4 -- picking another language while a turn ran:
  the story's refusal (409) went into a toast the very next line reloaded
  away, and the interface switched anyway, so the story kept English and
  nothing on screen said so.
* F5 -- an emptied number field saved 0: promotion switched off, "max
  managed" fell to the server's floor of 1. The panel's own rule ("an emptied
  field saves what it showed, never 0") covered two of its number fields.
* F13 -- the Freesound key could never be cleared; `PUT /api/ambience` has
  always taken `clear_key`, and nothing sent it.
* E3 -- one global switch re-downloaded the whole bootstrap (~1.23 MB on the
  owner's install) and re-translated the page; the route's answer already
  says everything the panel needs.
* `frontend_lorebooks_editors` F2 -- "Update" ran an extension's new code
  with no consent and no look at what the new version asks for.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP, _chat_payload


def _mount(page: Page, bootstrap: dict, answers: dict, writes: list, seen: list) -> None:
    """`answers` maps "METHOD /path" (or "/path" for a GET) to a JSON body,
    or to (status, body)."""
    def handle(route) -> None:
        request = route.request
        path = urlparse(request.url).path
        seen.append(f"{request.method} {path}")
        if request.method != "GET":
            writes.append((request.method, path,
                           json.loads(request.post_data) if request.post_data else {}))
        key = f"{request.method} {path}" if request.method != "GET" else path
        if path == "/api/bootstrap":
            answer = bootstrap
        else:
            answer = answers.get(key, {})
        if callable(answer):
            answer = answer()
        status, body = answer if isinstance(answer, tuple) else (200, answer)
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", handle)


def _with_a_provider(**extra) -> dict:
    return {**BOOTSTRAP,
            "providers": [{"id": 3, "name": "openrouter", "kind": "openrouter",
                           "base_url": "https://openrouter.ai/api/v1", "api_key": "",
                           "has_key": True, "enabled": 1}],
            "provider_presets": {"openrouter": {"base_url": "https://openrouter.ai/api/v1"}},
            "roles": ["default"], "role_fallbacks": {},
            "agent_models": {"default": {"provider": 3, "model": "z-ai/glm-5.2"}},
            **extra}


def _story_bootstrap(**extra) -> dict:
    return {**BOOTSTRAP, "chats": [{"id": 1, "name": "First"}], **extra}


def _open_first(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")


def test_a_refused_story_language_is_shown_and_nothing_switches(
        page: Page, ui_base_url: str) -> None:
    writes, seen = [], []
    chat = _chat_payload(1, "First", "settled prose")
    chat["chat"]["story_language"] = "en"
    boot = _story_bootstrap(
        language_packs=[{"id": "en", "name": "English", "native_name": "English", "story": True},
                        {"id": "ja", "name": "Japanese", "native_name": "日本語", "story": True}],
        ui_language="en", active_preset="Default")
    _mount(page, boot, {
        "/api/chats/1": chat,
        "/api/chats/1/vitals": {"enabled": False, "bodies": []},
        "/api/default_prompts": {"prompts": {}},
        "PUT /api/chats/1/language": (409, {"detail": "This chat still has an active "
                                                      "pipeline; wait for it to finish."}),
        "PUT /api/ui-language": {"language": "ja"},
    }, writes, seen)
    _open_first(page, ui_base_url)
    page.evaluate("() => { window.__notReloaded = true; }")
    page.locator("#b-prompts").click()
    language = page.locator("#modal select").nth(1)
    expect(language).to_have_value("en")
    language.select_option("ja")

    expect(page.locator("#toasts")).to_contain_text("This story kept its language")
    expect(page.locator("#toasts")).to_contain_text("active pipeline")
    page.wait_for_timeout(500)
    assert page.evaluate("() => window.__notReloaded === true"), "the page reloaded"
    assert not [w for w in writes if w[1] == "/api/ui-language"], writes
    expect(language).to_have_value("en")


def test_an_emptied_number_saves_what_it_showed(page: Page, ui_base_url: str) -> None:
    writes, seen = [], []
    _mount(page, _story_bootstrap(), {
        "/api/chats/1": _chat_payload(1, "First", "settled prose"),
        "/api/chats/1/vitals": {"enabled": False, "bodies": []},
        "/api/chats/1/dialogue_config": {
            "style": "natural", "min_lines": 1, "max_lines": 4, "variance": 0.6,
            "autonomy": 50, "promote_after_addressed": 3, "max_bubbles": 3,
            "bubble_radius": 3},
        "/api/chats/1/background_config": {"scene_life": "ambient", "max_managed": 6,
                                           "max_reactors": 2},
        "/api/chats/1/charters": {"charters": {"items": {}}, "warnings": []},
    }, writes, seen)
    _open_first(page, ui_base_url)
    page.locator("#b-dlg").click()
    expect(page.locator("#modaltitle")).to_have_text("Dialogue config")
    for label in ("turns till auto-promotion", "max managed", "max reactors",
                  "min lines", "max lines", "variance"):
        page.locator("#modal tr", has_text=label).locator("input").fill("")
    page.locator("#modal").get_by_role("button", name="Save", exact=True).click()
    expect(page.locator("#toasts")).to_contain_text("Dialogue config saved.")

    dialogue = next(w[2] for w in writes if w[1] == "/api/chats/1/dialogue_config")
    background = next(w[2] for w in writes if w[1] == "/api/chats/1/background_config")
    assert dialogue["promote_after_addressed"] == 3        # was 0: promotion off
    assert (dialogue["min_lines"], dialogue["max_lines"], dialogue["variance"]) == (1, 4, 0.6)
    assert (background["max_managed"], background["max_reactors"]) == (6, 2)


def test_the_freesound_key_can_be_cleared(page: Page, ui_base_url: str) -> None:
    writes, seen = [], []
    ambience = {"enabled": True, "source": "freesound", "configured": True,
                "library": "/tmp/lib", "has_key": True,
                "licenses": ["Creative Commons 0", "Attribution"]}
    _mount(page, _with_a_provider(ambience=ambience,
                                  research={"provider": "", "providers": [], "has_key": False}), {
        "PUT /api/ambience": {**ambience, "has_key": False, "configured": False},
    }, writes, seen)
    page.goto(f"{ui_base_url}/static/index.html")
    page.locator("#b-api").click()
    expect(page.locator("#modaltitle")).to_have_text("API connections")
    row = page.locator("#modal .row").filter(
        has=page.locator("input[type=password][placeholder*='blank keeps it']"))
    row.get_by_role("button", name="Clear key").click()
    expect(page.locator("#toasts")).to_contain_text("Freesound key cleared.")
    assert ("PUT", "/api/ambience", {"clear_key": True}) in writes
    # The field says what is stored now, from the server's answer.
    expect(page.locator("#modal input[type=password][placeholder='Freesound API key']")) \
        .to_have_count(1)


def test_a_global_switch_is_saved_without_reloading_the_bootstrap(
        page: Page, ui_base_url: str) -> None:
    writes, seen = [], []
    _mount(page, _with_a_provider(affect_habituation=False), {
        "PUT /api/affect_habituation": {"enabled": True},
    }, writes, seen)
    page.goto(f"{ui_base_url}/static/index.html")
    page.locator("#b-api").click()
    expect(page.locator("#modaltitle")).to_have_text("API connections")
    boots = seen.count("GET /api/bootstrap")
    page.get_by_label("Let a held peak wear off").check()
    expect(page.locator("#toasts")).to_contain_text("A held peak will wear off")
    assert seen.count("GET /api/bootstrap") == boots
    assert page.evaluate("() => S.boot.affect_habituation") is True


def test_an_extension_update_asks_first_and_runs_again_only_when_enabled(
        page: Page, ui_base_url: str) -> None:
    writes, seen = [], []
    state = {"enabled": True, "version": "1.0",
             "disclosures": ["Runs code in the engine's own process"]}

    def ext():
        return {"id": "lamps", "name": "Lamps", "version": state["version"],
                "enabled": state["enabled"], "trust": "code",
                "disclosures": list(state["disclosures"]),
                "provenance": "git:https://example.invalid/lamps@main",
                "source_url": "https://example.invalid/lamps", "updatable": True}

    def updated():
        # The server leaves an updated extension switched off (lane L2), and
        # answers with the NEW version's row.
        state.update(enabled=False, version="2.0", disclosures=[
            "Runs code in the engine's own process", "Writes into a character's own state"])
        return {**ext(), "updated": True, "previous_version": "1.0"}

    _mount(page, BOOTSTRAP, {
        "/api/extensions": lambda: {"extensions": [ext()], "load_errors": [], "safe_mode": False},
        "/api/extensions/updates": {"updates": [{"id": "lamps", "update": True,
                                                 "latest": "abc123", "checkable": True}]},
        "POST /api/extensions/lamps/update": updated,
        "POST /api/extensions/lamps/enable": {"id": "lamps", "enabled": True, "error": None},
    }, writes, seen)
    page.goto(f"{ui_base_url}/static/index.html")
    page.locator("#b-extensions").click()
    page.locator("#modal").get_by_role("button", name="Check for updates").click()
    page.locator("#modal").get_by_role("button", name="Update", exact=True).click()

    # Consent first: nothing is fetched before the host agrees.
    overlay = page.locator(".confirm-overlay")
    expect(overlay).to_contain_text("switched off")
    assert not [w for w in writes if w[1] == "/api/extensions/lamps/update"], writes
    overlay.get_by_role("button", name="Update", exact=True).click()

    # Then the NEW version's asks, and running it again is the host's act.
    overlay = page.locator(".confirm-overlay")
    expect(overlay).to_contain_text("Writes into a character's own state")
    overlay.get_by_role("button", name="Cancel").click()
    expect(page.locator("#modal").get_by_role("button", name="Enable")).to_be_visible()
    assert not [w for w in writes if w[1] == "/api/extensions/lamps/enable"], writes
