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
    settings: dict[str, object] | None = None,
) -> None:
    bootstrap_payload = bootstrap or BOOTSTRAP
    settings_payload = settings if settings is not None else bootstrap_payload
    page.set_viewport_size(
        {"width": width, "height": height or (900 if width >= 1000 else 844)}
    )
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(bootstrap_payload)
        ),
    )
    page.route(
        "**/api/settings",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(settings_payload)
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


def test_experience_connects_reading_sound_effects_and_interface_language(
    page: Page, ui_base_url: str
) -> None:
    """Catches an appearance-only Experience panel that omits current preferences."""
    bootstrap = {
        **BOOTSTRAP,
        "ui_language": "en",
        "language_packs": [
            {"id": "en", "name": "English", "native_name": "English", "ui": True},
            {"id": "ja", "name": "Japanese", "native_name": "日本語", "ui": True},
        ],
    }
    writes: list[dict[str, object]] = []

    def language(route) -> None:
        writes.append(route.request.post_data_json)
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "language": "ja"}),
        )

    page.route("**/api/ui-language", language)
    _open_settings(page, ui_base_url, bootstrap=bootstrap)

    page.get_by_role("combobox", name="Story text size").select_option("19")
    expect(page.locator("html")).to_have_attribute("data-prose-size", "19")
    page.get_by_role("combobox", name="Visual effects").select_option("off")
    expect(page.locator("html")).to_have_attribute("data-effects", "off")
    page.get_by_role("slider", name="Sound volume").fill("0.35")
    page.get_by_role("checkbox", name="Mute story sound").check()
    page.get_by_role("combobox", name="Interface language").select_option("ja")
    page.get_by_role("button", name="Apply interface language").click()

    expect(page.get_by_text("Language saved. Reload Sonder to apply it everywhere.", exact=True)).to_be_visible()
    stored = page.evaluate("JSON.parse(localStorage.getItem('sonder.ui-next') || '{}')")
    assert stored["appearance"]["proseSize"] == "19"
    assert stored["appearance"]["effects"] == "off"
    assert stored["panes"]["atmosphere"] == {
        "muted": True,
        "volume": 0.35,
        "chime": False,
    }
    assert writes == [{"language": "ja"}]


def test_experience_preferences_have_visible_effects_and_only_supported_density_modes(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url)

    density = page.get_by_role("combobox", name="Interface density")
    expect(density.locator("option")).to_have_count(2)
    row = density.locator("xpath=ancestor::*[contains(@class, 'ui-settings__field-head')]")
    comfortable = row.evaluate("node => node.getBoundingClientRect().height")
    density.select_option("compact")
    compact = row.evaluate("node => node.getBoundingClientRect().height")
    assert compact < comfortable

    preview = page.locator("[data-prose-size-preview]")
    expect(preview).to_be_visible()
    prose_size = page.get_by_role("combobox", name="Story text size")
    prose_size.select_option("15")
    small = preview.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")
    prose_size.select_option("21")
    large = preview.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")
    assert (small, large) == (15, 21)

    effects = page.get_by_role("combobox", name="Visual effects")
    effects.select_option("full")
    full = page.locator("html").evaluate(
        "node => getComputedStyle(node).getPropertyValue('--ui-motion-default').trim()"
    )
    effects.select_option("reduced")
    reduced = page.locator("html").evaluate(
        "node => getComputedStyle(node).getPropertyValue('--ui-motion-default').trim()"
    )
    effects.select_option("off")
    off = page.locator("html").evaluate(
        "node => getComputedStyle(node).getPropertyValue('--ui-motion-default').trim()"
    )
    assert full != reduced
    assert off == "0ms"


def test_settings_wheel_intent_reaches_the_detail_from_surrounding_chrome(
    page: Page, ui_base_url: str
) -> None:
    for width, height in ((1440, 900), (1024, 600), (390, 844), (844, 390)):
        page.goto("about:blank")
        _open_settings(page, ui_base_url, width=width, height=height)
        content = page.locator("[data-settings-content]")
        geometry = content.evaluate(
            "node => { node.scrollTop = 0; return { client: node.clientHeight, scroll: node.scrollHeight, top: node.scrollTop }; }"
        )
        assert geometry["scroll"] > geometry["client"], (width, height, geometry)

        page.get_by_role("navigation", name="Settings categories").hover()
        page.mouse.wheel(0, 600)
        page.wait_for_function(
            "document.querySelector('[data-settings-content]').scrollTop > 0",
            timeout=1500,
        )
        assert content.evaluate("node => node.scrollTop") > 0, (width, height)
        for _ in range(8):
            page.mouse.wheel(0, 600)
        expect(page.get_by_role("button", name="Reset Experience")).to_be_visible()


def test_settings_detail_is_keyboard_scrollable_and_the_only_scroll_owner(
    page: Page, ui_base_url: str
) -> None:
    for width, height in ((1440, 900), (1024, 600), (390, 844), (844, 390)):
        page.goto("about:blank")
        _open_settings(page, ui_base_url, width=width, height=height)
        content = page.locator("[data-settings-content]")
        content.evaluate("node => { node.scrollTop = 0; }")

        expect(content).to_have_attribute("tabindex", "0")
        page.get_by_role("link", name="Experience", exact=True).focus()
        page.keyboard.press("PageDown")
        page.wait_for_function(
            "document.querySelector('[data-settings-content]').scrollTop > 0",
            timeout=1500,
        )
        for _ in range(8):
            page.keyboard.press("PageDown")
        scroll_state = page.evaluate(
            """() => ({
              detail: document.querySelector('[data-settings-content]').scrollTop,
              workspace: document.querySelector('.ui-shell__workspace').scrollTop,
              page: document.documentElement.scrollTop,
            })"""
        )
        assert scroll_state["detail"] > 0, (width, height, scroll_state)
        assert scroll_state["workspace"] == 0, (width, height, scroll_state)
        assert scroll_state["page"] == 0, (width, height, scroll_state)


def test_settings_search_results_keep_their_own_wheel_scrolling(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url, width=1024, height=600)
    page.get_by_role("searchbox", name="Search settings").fill("e")
    results = page.locator(".ui-settings__search-results")
    expect(results).to_be_visible()
    page.locator("[data-settings-content]").evaluate("node => { node.scrollTop = 0; }")
    geometry = results.evaluate(
        "node => ({ client: node.clientHeight, scroll: node.scrollHeight })"
    )
    assert geometry["scroll"] > geometry["client"], geometry

    results.hover()
    page.mouse.wheel(0, 300)
    page.wait_for_function(
        "document.querySelector('.ui-settings__search-results').scrollTop > 0",
        timeout=1500,
    )
    assert page.locator("[data-settings-content]").evaluate("node => node.scrollTop") == 0
    results.get_by_role("button").first.focus()
    page.keyboard.press("PageDown")
    assert page.locator("[data-settings-content]").evaluate("node => node.scrollTop") == 0


def test_settings_native_controls_meet_desktop_and_touch_target_minimums(
    page: Page, ui_base_url: str
) -> None:
    for width, height, minimum in ((1440, 900, 36), (390, 844, 44), (844, 390, 44)):
        page.goto("about:blank")
        _open_settings(page, ui_base_url, width=width, height=height)
        sizes = page.locator(
            "[data-settings-content] select, .ui-settings__header input[type='search']"
        ).evaluate_all("nodes => nodes.map(node => node.getBoundingClientRect().height)")
        assert sizes and min(sizes) >= minimum, (width, height, sizes)


def test_settings_search_icon_stays_centered_at_every_control_height(
    page: Page, ui_base_url: str
) -> None:
    for width, height in ((1440, 900), (390, 844), (844, 390)):
        page.goto("about:blank")
        _open_settings(page, ui_base_url, width=width, height=height)
        geometry = page.locator(".ui-settings__search").evaluate(
            """node => {
              const field = node.querySelector('input').getBoundingClientRect();
              const icon = node.querySelector('.ui-icon').getBoundingClientRect();
              return {
                fieldCenter: field.top + field.height / 2,
                iconCenter: icon.top + icon.height / 2,
              };
            }"""
        )
        assert abs(geometry["fieldCenter"] - geometry["iconCenter"]) <= 0.5, (
            width,
            height,
            geometry,
        )


def test_empty_settings_status_collapses_to_the_shared_section_rhythm(
    page: Page, ui_base_url: str
) -> None:
    page.route(
        "**/api/extensions",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"extensions": [], "load_errors": [], "ext_api": 2}),
        ),
    )
    _open_settings(page, ui_base_url, category="add-ons")
    page.wait_for_function(
        "document.querySelector('[data-extension-count]')?.dataset.extensionCount === '0'"
    )
    geometry = page.locator(".ui-settings__section").evaluate(
        """node => {
          const head = node.querySelector('.ui-settings__section-head').getBoundingClientRect();
          const status = node.querySelector('.ui-settings__connection-status');
          const group = node.querySelector('.ui-settings__group').getBoundingClientRect();
          return {
            gap: group.top - head.bottom,
            statusDisplay: getComputedStyle(status).display,
            statusHeight: status.getBoundingClientRect().height,
          };
        }"""
    )
    assert geometry["statusDisplay"] == "none", geometry
    assert geometry["statusHeight"] == 0, geometry
    assert 17 <= geometry["gap"] <= 19, geometry


def test_shared_settings_selects_use_compact_glass_control_geometry(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url)
    density = page.get_by_role("combobox", name="Interface density")
    comfortable = density.evaluate(
        """node => {
          const style = getComputedStyle(node);
          return {
            height: node.getBoundingClientRect().height,
            radius: parseFloat(style.borderRadius),
            fontSize: parseFloat(style.fontSize),
            appearance: style.appearance,
            paddingRight: parseFloat(style.paddingRight),
            background: style.backgroundColor,
          };
        }"""
    )
    assert comfortable["height"] == 36, comfortable
    assert 3 <= comfortable["radius"] <= 4, comfortable
    assert comfortable["fontSize"] == 13, comfortable
    assert comfortable["appearance"] == "none", comfortable
    assert comfortable["paddingRight"] >= 32, comfortable
    assert comfortable["background"] != "rgba(0, 0, 0, 0)", comfortable

    density.select_option("compact")
    compact_height = density.evaluate("node => node.getBoundingClientRect().height")
    assert compact_height == 32


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


def test_settings_search_reaches_an_aliased_control_and_restores_focus(
    page: Page, ui_base_url: str
) -> None:
    """Catches category-only search or aliases that cannot restore a control."""
    _open_settings(page, ui_base_url)

    search = page.get_by_role("searchbox", name="Search settings")
    search.fill("api key")
    result = page.get_by_role("button", name=re.compile("Provider credentials"))
    expect(result).to_be_visible()
    result.click()

    expect(page).to_have_url(re.compile(r"#/settings/ai-connections\?control=providers$"))
    expect(page.get_by_role("heading", name="AI Connections", level=2)).to_be_visible()
    expect(page.get_by_role("button", name="Add provider")).to_be_focused()


def test_experience_retires_legacy_themes_and_keeps_the_mapped_curated_palette(
    page: Page, ui_base_url: str
) -> None:
    page.add_init_script(
        """(() => {
          localStorage.setItem('sonder.ui.next.theme.v1', 'ash-brass');
          localStorage.setItem('sonder.ui-next', JSON.stringify({
            version: 2,
            appearance: { theme: 'ash-brass', legacyTheme: 'tavern' },
            navigation: {}, panes: {}, drafts: {},
          }));
        })()"""
    )
    _open_settings(page, ui_base_url)

    expect(page.locator("html")).to_have_attribute("data-theme", "ash-brass")
    expect(page.get_by_role("combobox", name="Legacy themes")).to_have_count(0)
    expect(page.get_by_text(re.compile(r"legacy theme", re.I))).to_have_count(0)
    assert page.locator("html").get_attribute("data-legacy-theme") is None
    for label in (
        "Carbon Signal",
        "Ash and Brass",
        "Midnight Ink",
        "Parchment Night",
        "Neon Circuit",
        "Modern Slate",
    ):
        expect(page.get_by_role("button", name=f"Use {label} theme")).to_be_visible()

    page.get_by_role("button", name="Use Ash and Brass theme").click()
    stored = page.evaluate(
        "JSON.parse(localStorage.getItem('sonder.ui-next') || '{}').appearance"
    )
    assert stored == {"theme": "ash-brass"}


def test_modern_slate_renders_warm_white_interaction_without_blue(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url)
    page.get_by_role("button", name="Use Modern Slate theme").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "modern-slate")
    colors = page.locator("html").evaluate(
        """node => {
          const style = getComputedStyle(node);
          return ['--ui-color-canvas', '--ui-color-surface-solid',
            '--ui-color-interactive', '--ui-color-interactive-strong',
            '--ui-color-success', '--ui-color-danger', '--ui-color-info']
            .map(name => style.getPropertyValue(name).trim());
        }"""
    )
    parsed = []
    for color in colors:
        match = re.search(r"rgba?\((\d+),?\s+(\d+),?\s+(\d+)", color)
        assert match, color
        channels = tuple(map(int, match.groups()))
        assert channels[0] >= channels[1] >= channels[2], channels
        assert channels[0] - channels[2] <= 8, channels
        parsed.append(channels)
    assert parsed[2][0] >= 200


def test_advanced_prompt_editor_uses_current_presets_and_explicit_save(
    page: Page, ui_base_url: str
) -> None:
    """Catches an inert Advanced launcher or a prompt editor backed by legacy DOM."""
    bootstrap = {
        **BOOTSTRAP,
        "default_prompts": {"director": "Default director sheet"},
        "prompt_presets": {
            "Focused": {"language": "en", "prompts": {"director": "Focused sheet"}}
        },
        "active_preset": "Focused",
        "language_packs": [{"id": "en", "name": "English"}],
    }
    writes: dict[str, object] = {}

    def save(route) -> None:
        writes["preset"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "name": "Focused", "language": "en"}),
        )

    page.route("**/api/prompt_presets", save)
    _open_settings(page, ui_base_url, category="advanced", bootstrap=bootstrap)

    page.get_by_role("button", name=re.compile("^Prompt editor")).click()
    expect(page).to_have_url(re.compile(r"#/settings/advanced\?tool=prompts$"))
    editor = page.get_by_role("textbox", name="Director prompt")
    expect(editor).to_have_value("Focused sheet")
    editor.fill("Revised focused sheet")
    page.get_by_role("button", name="Save prompt preset").click()
    expect(page.get_by_text("Prompt preset saved.", exact=True)).to_be_visible()
    assert writes["preset"] == {
        "name": "Focused",
        "language": "en",
        "prompts": {"director": "Revised focused sheet"},
    }


def test_advanced_prompt_editor_activates_and_stages_preset_deletion(
    page: Page, ui_base_url: str
) -> None:
    """Catches loss of the current preset lifecycle during modal replacement."""
    bootstrap = {
        **BOOTSTRAP,
        "default_prompts": {"director": "Default director sheet"},
        "prompt_presets": {
            "Focused": {"language": "en", "prompts": {"director": "Focused sheet"}},
            "Spare": {"language": "en", "prompts": {"director": "Spare sheet"}},
        },
        "active_preset": "Focused",
        "language_packs": [{"id": "en", "name": "English"}],
    }
    writes: list[tuple[str, object]] = []

    def active(route) -> None:
        writes.append(("active", route.request.post_data_json))
        route.fulfill(content_type="application/json", body=json.dumps({"ok": True}))

    def remove(route) -> None:
        writes.append(("delete", route.request.method))
        route.fulfill(content_type="application/json", body=json.dumps({"ok": True}))

    page.route("**/api/active_preset", active)
    page.route("**/api/prompt_presets/Spare", remove)
    _open_settings(page, ui_base_url, category="advanced", bootstrap=bootstrap)
    page.get_by_role("button", name=re.compile("^Prompt editor")).click()

    page.get_by_role("combobox", name="Prompt preset", exact=True).select_option("Spare")
    page.get_by_role("button", name="Use selected preset").click()
    expect(page.get_by_text("Spare is now the active prompt preset.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Delete selected preset").click()
    expect(page.get_by_text("The engine's built-in Default remains available.", exact=False)).to_be_visible()
    page.get_by_role("button", name="Confirm delete Spare").click()
    expect(page).to_have_url(re.compile(r"preset=Default"))
    assert writes == [("active", {"name": "Spare"}), ("delete", "DELETE")]


def test_advanced_raw_story_editor_validates_and_saves_the_current_story(
    page: Page, ui_base_url: str
) -> None:
    """Catches a raw-data launcher that falls back to the classic modal."""
    bootstrap = {**BOOTSTRAP, "chats": [{"id": 5, "title": "The Glass District"}]}
    writes: list[dict[str, object]] = []
    page.route(
        re.compile(r".*/api/chats/5/world$"),
        lambda route: (
            writes.append(route.request.post_data_json)
            or route.fulfill(content_type="application/json", body=json.dumps({"rooms": {"atrium": {}}}))
            if route.request.method == "PUT"
            else route.fulfill(content_type="application/json", body=json.dumps({"rooms": {"atrium": {}}}))
        ),
    )
    _open_settings(page, ui_base_url, category="advanced", bootstrap=bootstrap)

    page.get_by_role("button", name=re.compile("^Raw story data")).click()
    expect(page).to_have_url(re.compile(r"#/settings/advanced\?tool=story-data$"))
    editor = page.get_by_role("textbox", name="Raw story data JSON")
    expect(editor).to_have_value(re.compile(r'"atrium"'))
    editor.fill("not json")
    page.get_by_role("button", name="Save raw story data").click()
    expect(page.get_by_text("Enter valid JSON before saving.", exact=True)).to_be_visible()
    editor.fill('{"rooms":{"atrium":{"name":"Atrium"}}}')
    page.get_by_role("button", name="Save raw story data").click()
    expect(page.get_by_text("Raw story data saved.", exact=True)).to_be_visible()
    assert writes == [{"rooms": {"atrium": {"name": "Atrium"}}}]


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
    server_settings = dict(bootstrap)

    def provider_route(route) -> None:
        writes["provider"] = route.request.post_data_json
        provider = {
            "id": 11,
            "name": "Anthropic",
            "kind": "anthropic",
            "base_url": "https://api.anthropic.com",
            "has_key": True,
            "prompt_cache": True,
            "prompt_cache_default": True,
            "prompt_cache_locked": False,
        }
        server_settings["providers"] = [provider]
        route.fulfill(
            content_type="application/json",
            body=json.dumps(provider),
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
        server_settings["agent_models"] = route.request.post_data_json
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
        settings=server_settings,
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
            body=json.dumps({"ok": True, "embeddings_role_changed": False}),
        )

    def effort_route(route) -> None:
        writes["efforts"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "reasoning_effort": {}}),
        )

    page.route("**/api/agent_models", models_route)
    page.route("**/api/reasoning_effort", effort_route)
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    page.get_by_text("Advanced model assignments", exact=True).click()
    page.get_by_role("combobox", name="Provider for Director").select_option("")
    page.get_by_role("button", name="Save model assignments").click()

    expect(page.get_by_text("Model assignments saved.", exact=True)).to_be_visible()
    assert writes["models"] == {
        "default": {"provider": 7, "model": "claude-sonnet-4-5", "temperature": 0.7},
        "embeddings": {"provider": 8, "model": "openai/text-embedding-3-small"},
    }
    assert writes["efforts"] == {"efforts": {}}


def test_ai_connections_exposes_memory_search_model_and_rebuild_route(
    page: Page, ui_base_url: str
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "providers": [
            {"id": 7, "name": "Anthropic", "kind": "anthropic", "has_key": True},
            {"id": 8, "name": "OpenRouter", "kind": "openrouter", "has_key": True},
        ],
        "provider_presets": {},
        "roles": ["default", "director", "embeddings"],
        "agent_models": {
            "default": {"provider": 7, "model": "claude-sonnet-4-5"},
            "director": {"provider": 7, "model": "claude-opus-4-1"},
            "embeddings": {"provider": 8, "model": "openai/text-embedding-3-small"},
        },
    }
    writes: list[dict] = []

    def models(route) -> None:
        writes.append(route.request.post_data_json)
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "embeddings_role_changed": True}),
        )

    page.route("**/api/agent_models", models)
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    expect(page.get_by_text("Memory search model (embeddings)", exact=True)).to_be_visible()
    expect(page.get_by_text(
        "Finds related memories by meaning. Choose a compatible vector or embedding model.",
        exact=True,
    )).to_be_visible()
    page.get_by_role("combobox", name="Memory search provider").select_option("8")
    page.get_by_role("textbox", name="Memory search model").fill(
        "perplexity/pplx-embed-v1-0.6b"
    )
    page.get_by_role("button", name="Save memory search model").click()

    expect(page.get_by_text(
        "Stored memory search vectors must be rebuilt for the new model.", exact=True
    )).to_be_visible()
    assert writes == [{
        "default": {"provider": 7, "model": "claude-sonnet-4-5"},
        "director": {"provider": 7, "model": "claude-opus-4-1"},
        "embeddings": {"provider": 8, "model": "perplexity/pplx-embed-v1-0.6b"},
    }]
    page.get_by_role("button", name="Review memory search").click()
    expect(page).to_have_url(re.compile(r"#/settings/maintenance$"))
    expect(page.get_by_role("heading", name="Maintenance", level=2)).to_be_visible()


def test_server_confirmed_memory_and_backdrop_values_survive_settings_navigation(
    page: Page, ui_base_url: str
) -> None:
    """A successful PUT must replace the stale startup projection with server truth."""
    bootstrap = {
        **BOOTSTRAP,
        "providers": [
            {"id": 8, "name": "NanoGPT", "kind": "nanogpt", "has_key": True}
        ],
        "provider_presets": {},
        "roles": ["default", "embeddings"],
        "agent_models": {
            "default": {"provider": 8, "model": "glm-5.2"},
            "embeddings": {"provider": 8, "model": "old-embedding-model"},
        },
        "max_output_tokens": 20000,
        "max_output_tokens_bounds": {"min": 1024, "max": 128000, "default": 20000},
        "image_model": {"provider": 8, "model": "old-image-model"},
        "backdrops_enabled": False,
        "backdrop_continuity": False,
        "ambience": {"enabled": False, "source": "local", "library": "", "has_key": False},
        "ambience_licenses": [],
    }
    server_settings = dict(bootstrap)

    def save_models(route) -> None:
        server_settings["agent_models"] = route.request.post_data_json
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "embeddings_role_changed": True}),
        )

    def save_image(route) -> None:
        body = route.request.post_data_json
        server_settings["image_model"] = body
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "image_model": body}),
        )

    def save_backdrops(route) -> None:
        body = route.request.post_data_json
        server_settings["backdrops_enabled"] = body["enabled"]
        server_settings["backdrop_continuity"] = body["continuity"]
        route.fulfill(content_type="application/json", body=json.dumps(body))

    page.route("**/api/agent_models", save_models)
    page.route("**/api/image_model", save_image)
    page.route("**/api/backdrops", save_backdrops)
    _open_settings(
        page,
        ui_base_url,
        category="ai-connections",
        bootstrap=bootstrap,
        settings=server_settings,
    )

    page.get_by_role("textbox", name="Memory search model").fill("text-embedding-3-small")
    page.get_by_role("button", name="Save memory search model").click()
    expect(page.get_by_text(
        "Stored memory search vectors must be rebuilt for the new model.", exact=True
    )).to_be_visible()

    page.get_by_role("combobox", name="Backdrop image model").fill("gpt-image-2")
    page.get_by_role("checkbox", name="Generate backdrops for new rooms").check()
    page.get_by_role("checkbox", name="Keep room images visually consistent").check()
    page.get_by_role("button", name="Save backdrop settings").click()
    expect(page.get_by_text("Backdrop settings saved.", exact=True)).to_be_visible()

    page.get_by_role("link", name="Content", exact=True).click()
    page.get_by_role("link", name="AI Connections", exact=True).click()

    expect(page.get_by_role("textbox", name="Memory search model")).to_have_value(
        "text-embedding-3-small"
    )
    expect(page.get_by_role("combobox", name="Backdrop image model")).to_have_value(
        "gpt-image-2"
    )
    expect(page.get_by_role("checkbox", name="Generate backdrops for new rooms")).to_be_checked()
    expect(page.get_by_role(
        "checkbox", name="Keep room images visually consistent"
    )).to_be_checked()


def test_failed_settings_write_keeps_the_draft_and_raises_a_persistent_engine_notice(
    page: Page, ui_base_url: str
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "providers": [
            {"id": 8, "name": "NanoGPT", "kind": "nanogpt", "has_key": True}
        ],
        "provider_presets": {},
        "roles": ["default", "embeddings"],
        "agent_models": {
            "default": {"provider": 8, "model": "glm-5.2"},
            "embeddings": {"provider": 8, "model": "old-embedding-model"},
        },
        "max_output_tokens": 20000,
        "max_output_tokens_bounds": {"min": 1024, "max": 128000, "default": 20000},
    }
    page.route("**/api/agent_models", lambda route: route.abort("connectionrefused"))
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    model = page.get_by_role("textbox", name="Memory search model")
    model.fill("text-embedding-3-small")
    page.get_by_role("button", name="Save memory search model").click()

    expect(model).to_have_value("text-embedding-3-small")
    notice = page.locator("[data-shell-notice-host] [data-tone='error']")
    expect(notice).to_contain_text("Sonder could not reach the engine")
    expect(notice).to_contain_text("not confirmed")
    dismiss = page.get_by_role("button", name=re.compile(r"Dismiss notification:"))
    dismiss_box = dismiss.bounding_box()
    viewport = page.viewport_size
    assert dismiss_box is not None
    assert viewport is not None
    assert dismiss_box["x"] >= 0
    assert dismiss_box["x"] + dismiss_box["width"] <= viewport["width"]
    assert notice.evaluate("element => element.scrollWidth <= element.clientWidth")
    expect(page.get_by_text("Memory search model saved.", exact=True)).to_have_count(0)


def test_content_projects_existing_narrator_voice_and_server_bounds(
    page: Page, ui_base_url: str
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "exemplars": ["Rain hissed against the copper roof."],
        "exemplar_bounds": {"max_count": 2, "max_chars": 80},
    }
    _open_settings(page, ui_base_url, category="content", bootstrap=bootstrap)

    expect(page.get_by_role("tab")).to_have_count(2)
    editor = page.locator(".ui-settings__exemplars textarea")
    expect(editor).to_have_count(1)
    expect(editor).to_have_value("Rain hissed against the copper roof.")
    expect(editor).to_have_attribute("maxlength", "80")


def test_ai_connections_edits_role_samplers_and_ordered_backup_models(
    page: Page, ui_base_url: str
) -> None:
    """Catches preservation-only handling of generation defaults and fallbacks."""
    bootstrap = {
        **BOOTSTRAP,
        "providers": [
            {"id": 7, "name": "Anthropic", "kind": "anthropic", "has_key": True},
            {"id": 8, "name": "OpenRouter", "kind": "openrouter", "has_key": True},
        ],
        "provider_presets": {},
        "roles": ["default"],
        "sampler_keys": ["temperature", "top_p"],
        "default_samplers": {"temperature": 0.7, "top_p": 1.0},
        "agent_models": {
            "default": {
                "provider": 7,
                "model": "claude-sonnet-4-5",
                "temperature": 0.7,
                "fallbacks": [{"provider": 8, "model": "anthropic/claude-sonnet-4"}],
            }
        },
        "reasoning_effort_levels": ["off", "low", "medium", "high"],
    }
    writes: dict[str, object] = {}

    def models(route) -> None:
        writes["models"] = route.request.post_data_json
        route.fulfill(content_type="application/json", body=json.dumps({"ok": True}))

    page.route("**/api/agent_models", models)
    page.route(
        "**/api/reasoning_effort",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps({"ok": True})),
    )
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    page.get_by_text("Advanced model assignments", exact=True).click()
    page.get_by_text("Sampling and backup models for Default", exact=True).click()
    page.get_by_role("spinbutton", name="Temperature for Default").fill("0.45")
    page.get_by_role("textbox", name="Backup 1 model for Default").fill(
        "anthropic/claude-haiku-4"
    )
    page.get_by_role("button", name="Add backup model for Default").click()
    page.get_by_role("combobox", name="Backup 2 provider for Default").select_option("7")
    page.get_by_role("textbox", name="Backup 2 model for Default").fill("claude-haiku-4-5")
    page.get_by_role("button", name="Save model assignments").click()

    expect(page.get_by_text("Model assignments saved.", exact=True)).to_be_visible()
    assert writes["models"] == {
        "default": {
            "provider": 7,
            "model": "claude-sonnet-4-5",
            "temperature": 0.45,
            "top_p": 1,
            "fallbacks": [
                {"provider": 8, "model": "anthropic/claude-haiku-4"},
                {"provider": 7, "model": "claude-haiku-4-5"},
            ],
        }
    }


def test_ai_connections_saves_openrouter_privacy_and_upstream_routing(
    page: Page, ui_base_url: str
) -> None:
    """Catches omission of the provider-retention and fallback routing controls."""
    bootstrap = {
        **BOOTSTRAP,
        "providers": [{"id": 8, "name": "OpenRouter", "kind": "openrouter", "has_key": True}],
        "provider_presets": {},
        "roles": ["default"],
        "agent_models": {"default": {"provider": 8, "model": "anthropic/claude-sonnet-4"}},
        "openrouter_routing": {"only": ["anthropic"], "data_collection": "deny"},
    }
    writes: list[dict[str, object]] = []

    def routing(route) -> None:
        writes.append(route.request.post_data_json)
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "routing": route.request.post_data_json}),
        )

    page.route("**/api/openrouter_routing", routing)
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    page.get_by_role("textbox", name="OpenRouter allowed upstreams").fill(
        "anthropic, amazon-bedrock"
    )
    page.get_by_role("checkbox", name="Never fall back to another OpenRouter upstream").check()
    page.get_by_role("combobox", name="OpenRouter routing preference").select_option("latency")
    page.get_by_role("button", name="Save OpenRouter routing").click()

    expect(page.get_by_text("OpenRouter routing saved.", exact=True)).to_be_visible()
    assert writes == [
        {
            "only": ["anthropic", "amazon-bedrock"],
            "ignore": [],
            "data_collection": "deny",
            "allow_fallbacks": False,
            "sort": "latency",
        }
    ]


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
    page.route(
        "**/api/providers/8/image_models",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"models": [{"id": "flux-ultra"}, {"id": "flux-pro"}]}),
        ),
    )
    page.route("**/api/backdrops", record("backdrops", {"enabled": True, "continuity": True}))
    page.route("**/api/ambience", record("ambience", bootstrap["ambience"]))
    _open_settings(page, ui_base_url, category="ai-connections", bootstrap=bootstrap)

    page.get_by_role("button", name="Discover image models").click()
    expect(page.get_by_text("2 image models available. Type to filter the list.", exact=True)).to_be_visible()
    page.get_by_role("combobox", name="Backdrop image model").fill("flux-ultra")
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


def test_content_saves_current_story_content_permissions_and_explains_local_data(
    page: Page, ui_base_url: str
) -> None:
    """Catches an inert Content placeholder or invented global data controls."""
    bootstrap = {
        **BOOTSTRAP,
        "nsfw_enabled": False,
        "attire_beneath": False,
        "auto_promote": False,
        "affect_habituation": False,
    }
    writes: dict[str, object] = {}

    def record(name: str):
        def route_handler(route) -> None:
            writes[name] = route.request.post_data_json
            route.fulfill(
                content_type="application/json",
                body=json.dumps({"enabled": route.request.post_data_json["enabled"]}),
            )

        return route_handler

    page.route("**/api/nsfw", record("nsfw"))
    page.route("**/api/attire_beneath", record("attire"))
    page.route("**/api/auto_promote", record("promote"))
    page.route("**/api/affect_habituation", record("habituation"))
    _open_settings(page, ui_base_url, category="content", bootstrap=bootstrap)

    expect(page.get_by_role("heading", name="Content", level=2)).to_be_visible()
    expect(page.get_by_text("Your stories stay on this Sonder host.", exact=True)).to_be_visible()
    page.get_by_role("checkbox", name="Allow adult story content").check()
    page.get_by_role("checkbox", name="Use underneath descriptions from cards").check()
    page.get_by_role("checkbox", name="Allow stories to promote recurring extras").check()
    page.get_by_role("checkbox", name="Let sustained peak emotion settle").check()
    page.get_by_role("button", name="Save content preferences").click()

    expect(page.get_by_text("Content preferences saved.", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Manage story exports and deletion")).to_have_attribute(
        "href", "#/library/stories"
    )
    assert writes == {
        "nsfw": {"enabled": True},
        "attire": {"enabled": True},
        "promote": {"enabled": True},
        "habituation": {"enabled": True},
    }


def test_narrator_voice_uses_one_keyboard_tabbed_editor_and_saves_all_slots(
    page: Page, ui_base_url: str
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "exemplars": ["First voice.", "Second voice.", "Third voice.", "Fourth voice."],
        "exemplar_bounds": {"max_count": 4, "max_chars": 2000},
    }
    writes: list[dict[str, object]] = []

    def save(route) -> None:
        writes.append(route.request.post_data_json)
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"exemplars": route.request.post_data_json["exemplars"]}),
        )

    page.route("**/api/exemplars", save)
    _open_settings(page, ui_base_url, category="content", bootstrap=bootstrap)

    tabs = page.get_by_role("tab")
    expect(tabs).to_have_count(4)
    editor = page.locator(".ui-settings__exemplars textarea")
    expect(editor).to_have_count(1)
    expect(editor).to_have_value("First voice.")
    expect(editor).to_have_attribute("aria-labelledby", "narrator-example-tab-1")
    expect(page.get_by_role("tab", name="Example 1", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )

    page.get_by_role("tab", name="Example 2", exact=True).click()
    expect(editor).to_have_value("Second voice.")
    editor.fill("Edited second voice.")

    page.get_by_role("tab", name="Example 2", exact=True).press("ArrowRight")
    expect(page.get_by_role("tab", name="Example 3", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(editor).to_have_value("Third voice.")
    editor.fill("Edited third voice.")

    page.get_by_role("tab", name="Example 3", exact=True).press("End")
    expect(page.get_by_role("tab", name="Example 4", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(editor).to_have_value("Fourth voice.")

    page.get_by_role("tab", name="Example 4", exact=True).press("Home")
    expect(page.get_by_role("tab", name="Example 1", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(editor).to_have_value("First voice.")

    page.get_by_role("button", name="Save narrator voice").click()
    expect(page.get_by_text("Narrator voice saved.", exact=True)).to_be_visible()
    assert writes == [{
        "exemplars": [
            "First voice.",
            "Edited second voice.",
            "Edited third voice.",
            "Fourth voice.",
        ]
    }]


def test_content_renders_living_world_built_and_effective_depth_from_server_truth(
    page: Page, ui_base_url: str
) -> None:
    """Catches a copied ladder that presents an unbuilt or ceiling-capped tier as active."""
    bootstrap = {**BOOTSTRAP, "chats": [{"id": 5, "title": "The Glass District"}]}
    writes: list[dict[str, object]] = []
    report = {
        "living_world": {"routine_residue": "ceiling", "rumor_ledger": "ceiling"},
        "approaches": [
            {
                "approach": "routine_residue",
                "label": "Routine and residue",
                "value": "ceiling",
                "effective": "floor",
                "cost": "floor: free; ceiling: one call",
                "depths": [
                    {"value": "floor", "description": "Rooms drift on the clock.", "built": True, "requires": "deterministic", "permitted": True},
                    {"value": "ceiling", "description": "Places advance social life.", "built": False, "requires": "stochastic", "permitted": True},
                ],
            },
            {
                "approach": "rumor_ledger",
                "label": "Rumor ledger",
                "value": "ceiling",
                "effective": "floor",
                "cost": "floor: free; ceiling: one small call",
                "depths": [
                    {"value": "floor", "description": "News travels with witnesses.", "built": True, "requires": "deterministic", "permitted": True},
                    {"value": "ceiling", "description": "Posted notices get wording.", "built": True, "requires": "stochastic", "permitted": False},
                ],
            },
        ],
    }

    def living_world(route) -> None:
        if route.request.method == "PUT":
            writes.append(route.request.post_data_json)
            route.fulfill(content_type="application/json", body=json.dumps({"ok": True, "living_world": route.request.post_data_json["living_world"]}))
        else:
            route.fulfill(content_type="application/json", body=json.dumps(report))

    page.route(re.compile(r".*/api/chats/5/living_world$"), living_world)
    _open_settings(page, ui_base_url, category="content", bootstrap=bootstrap)

    expect(page.get_by_text(re.compile("witnessing, telling, reading, and carrying"))).to_be_visible()
    expect(page.get_by_text("Runs as Floor — Ceiling is not built yet.", exact=True)).to_be_visible()
    expect(page.get_by_text("Runs as Floor — the story's off-screen limit does not permit Ceiling.", exact=True)).to_be_visible()
    page.get_by_role("combobox", name="Routine and residue depth").select_option("floor")
    page.get_by_role("button", name="Save living world settings").click()
    expect(page.get_by_text("Living world settings saved.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Open Institution tools").click()
    expect(page).to_have_url(re.compile(r"#/play/story-tools\?chat=5&tool=dialogue$"))
    assert writes == [{"living_world": {"routine_residue": "floor", "rumor_ledger": "ceiling"}}]


def test_add_ons_discloses_permissions_and_runs_current_extension_lifecycle(
    page: Page, ui_base_url: str
) -> None:
    """Catches a cosmetic extension list or consent shown after enablement."""
    enabled = {"value": False}
    writes: list[tuple[str, str]] = []

    def listing(route) -> None:
        route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "extensions": [
                        {
                            "id": "sample",
                            "name": "Sample Extension",
                            "version": "1.2.0",
                            "description": "Adds a story tool.",
                            "provenance": "git:https://example.invalid/sample",
                            "trust": "code",
                            "capabilities": {"ui": {"api": 2}},
                            "disclosures": ["Read story state", "Run code in the engine process"],
                            "enabled": enabled["value"],
                            "updatable": True,
                        }
                    ],
                    "load_errors": [],
                    "safe_mode": False,
                    "ext_api": 1,
                    "host_capabilities": ["ui"],
                }
            ),
        )

    def enable(route) -> None:
        writes.append((route.request.method, route.request.url.rsplit("/", 1)[-1]))
        enabled["value"] = True
        route.fulfill(content_type="application/json", body=json.dumps({"id": "sample", "enabled": True}))

    def updates(route) -> None:
        route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {"updates": [{"id": "sample", "update": True, "latest": "2.0.0", "checkable": True}]}
            ),
        )

    page.route(re.compile(r".*/api/extensions$"), listing)
    page.route("**/api/extensions/sample/enable", enable)
    page.route("**/api/extensions/updates", updates)
    _open_settings(page, ui_base_url, category="add-ons")

    expect(page.get_by_role("heading", name="Add-ons", level=2)).to_be_visible()
    expect(page.locator(".ui-settings__extension-list")).to_have_attribute("data-extension-count", "1")
    expect(page.get_by_text("Sample Extension", exact=True)).to_be_visible()
    expect(page.get_by_text(re.compile(r"Extension UI API 2"))).to_be_visible()
    page.get_by_role("button", name="Enable Sample Extension").click()
    expect(page.get_by_text("Nothing has reviewed this code.", exact=True)).to_be_visible()
    expect(
        page.locator(".ui-settings__extension-consent").get_by_text(
            "Read story state", exact=True
        )
    ).to_be_visible()
    page.get_by_role("button", name="Confirm enable Sample Extension").click()
    expect(page.get_by_text("Enabled", exact=True)).to_be_visible()

    page.get_by_role("button", name="Check for extension updates").click()
    expect(page.get_by_role("button", name="Update Sample Extension")).to_be_visible()
    assert writes == [("POST", "enable")]


def test_add_on_demo_qualifier_stays_in_title_not_actions_and_actions_have_bounds(
    page: Page, ui_base_url: str
) -> None:
    page.route(
        re.compile(r".*/api/extensions$"),
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({
                "extensions": [{
                    "id": "campaign",
                    "name": "Campaign (demo)",
                    "version": "0.1.0",
                    "enabled": False,
                    "trust": "code",
                    "capabilities": {"ui": {"api": 2}},
                    "disclosures": [],
                }],
                "load_errors": [],
                "safe_mode": False,
                "ext_api": 2,
            }),
        ),
    )
    _open_settings(page, ui_base_url, category="add-ons")

    expect(page.get_by_text("Campaign (demo)", exact=True)).to_be_visible()
    enable = page.get_by_role("button", name="Enable Campaign", exact=True)
    remove = page.get_by_role("button", name="Remove Campaign", exact=True)
    expect(enable).to_be_visible()
    expect(remove).to_be_visible()
    expect(page.get_by_role("button", name=re.compile(r"demo", re.I))).to_have_count(0)
    border = enable.evaluate(
        """node => {
          const style = getComputedStyle(node);
          return { width: parseFloat(style.borderTopWidth), color: style.borderTopColor };
        }"""
    )
    # Chromium snaps a half-CSS-pixel border to one device pixel at DPR 1.
    assert 0 < border["width"] <= 1, border
    assert border["color"] != "rgba(0, 0, 0, 0)", border

    enable.click()
    expect(page.get_by_role("button", name="Confirm enable Campaign", exact=True)).to_be_visible()


def test_maintenance_category_uses_its_dedicated_wrench_icon(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url)
    maintenance = page.get_by_role("link", name="Maintenance", exact=True)
    href = maintenance.locator("use").get_attribute("href")
    assert href is not None and href.endswith("#icon-maintenance"), href


def test_add_ons_stages_install_and_preserves_story_data_on_removal(
    page: Page, ui_base_url: str
) -> None:
    """Catches installation without consent or removal wording that implies data loss."""
    installed = {"value": False}
    writes: dict[str, object] = {}

    def listing(route) -> None:
        rows = []
        if installed["value"]:
            rows.append(
                {
                    "id": "sample",
                    "name": "Sample Extension",
                    "version": "1.0.0",
                    "enabled": False,
                    "trust": "code",
                    "disclosures": [],
                }
            )
        route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "extensions": rows,
                    "load_errors": [],
                    "safe_mode": False,
                    "ext_api": 1,
                    "host_capabilities": [],
                }
            ),
        )

    def install(route) -> None:
        writes["install"] = route.request.post_data_json
        installed["value"] = True
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"extension": {"id": "sample", "enabled": False}}),
        )

    def remove(route) -> None:
        writes["remove"] = route.request.method
        installed["value"] = False
        route.fulfill(content_type="application/json", body=json.dumps({"removed": True}))

    page.route(re.compile(r".*/api/extensions$"), listing)
    page.route("**/api/extensions/install", install)
    page.route("**/api/extensions/sample", remove)
    _open_settings(page, ui_base_url, category="add-ons")

    page.get_by_role("textbox", name="Extension source").fill(
        "https://example.invalid/sample.git"
    )
    page.get_by_role("button", name="Install extension").click()
    expect(
        page.get_by_text(
            "Nothing has reviewed this code. Installation copies it to this Sonder host; it still will not run until you enable it.",
            exact=True,
        )
    ).to_be_visible()
    page.get_by_role("button", name="Confirm install extension").click()
    expect(page.get_by_text("Sample Extension", exact=True)).to_be_visible()

    page.get_by_role("button", name="Remove Sample Extension").click()
    expect(
        page.get_by_text(
            "Its files will be deleted. Story data it owns is kept so reinstalling can recover it.",
            exact=True,
        )
    ).to_be_visible()
    page.get_by_role("button", name="Confirm remove Sample Extension").click()
    expect(page.get_by_text("No extensions are installed.", exact=True)).to_be_visible()
    assert writes == {
        "install": {"source": "https://example.invalid/sample.git"},
        "remove": "DELETE",
    }


def test_maintenance_checks_updates_and_stages_checkpoint_conversion(
    page: Page, ui_base_url: str
) -> None:
    """Catches automatic destructive maintenance or disconnected legacy controls."""
    writes: list[tuple[str, object]] = []
    page.route(
        "**/api/updates/check",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "ok": True,
                    "branch": "interface",
                    "current": "abc1234",
                    "behind": 2,
                    "ahead": 0,
                    "dirty": False,
                    "up_to_date": False,
                    "commits": [{"hash": "def5678", "subject": "Update interface"}],
                    "releases": None,
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
                    "checkpoints": 12,
                    "legacy": 3,
                    "bytes": 40_000_000,
                    "legacy_bytes": 25_000_000,
                    "progress": {"running": False},
                }
            ),
        ),
    )

    def install(route) -> None:
        writes.append(("install", route.request.post_data_json))
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"ok": True, "updated": True, "current": "def5678"}),
        )

    def compact(route) -> None:
        writes.append(("compact", route.request.post_data_json))
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"started": True, "total": 3}),
        )

    page.route("**/api/updates/install", install)
    page.route("**/api/maintenance/checkpoints/compact", compact)
    _open_settings(page, ui_base_url, category="maintenance")

    expect(page.get_by_role("heading", name="Maintenance", level=2)).to_be_visible()
    expect(page.get_by_text("3 of 12 checkpoints use the legacy format.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Check for Sonder updates").click()
    expect(page.get_by_text("2 updates are available.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Install update").click()
    expect(page.get_by_text("The running server will need a restart.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Confirm install update").click()
    expect(page.get_by_text("Update installed. Restart the Sonder server, then reload this page.", exact=True)).to_be_visible()

    page.get_by_role("button", name="Convert legacy checkpoints").click()
    expect(page.get_by_text("Rollback history will be rewritten into the current storage format.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Confirm checkpoint conversion").click()
    expect(page.get_by_text("Checkpoint conversion started for 3 checkpoints.", exact=True)).to_be_visible()
    assert writes == [("install", {}), ("compact", {})]


def test_maintenance_exposes_redacted_diagnostics_and_stages_embedding_rebuild(
    page: Page, ui_base_url: str
) -> None:
    """Catches missing logs/repair ownership or an automatic paid rebuild."""
    writes: list[dict[str, object]] = []
    page.route(
        "**/api/maintenance/checkpoints",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"checkpoints": 0, "legacy": 0, "progress": {"running": False}}),
        ),
    )
    page.route(
        re.compile(r".*/api/memory/embeddings$"),
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "model_key": "openai:text-embedding-3-small",
                    "total": 42,
                    "current": 31,
                    "stale": 11,
                    "progress": {"running": False},
                }
            ),
        ),
    )

    def rebuild(route) -> None:
        writes.append(route.request.post_data_json)
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"started": True, "total": 11}),
        )

    page.route("**/api/memory/embeddings/rebuild", rebuild)
    _open_settings(page, ui_base_url, category="maintenance")

    expect(page.get_by_text("11 memories need updated search vectors.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Rebuild memory search").click()
    expect(page.get_by_text("This may use the configured embeddings provider.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Confirm rebuild memory search").click()
    expect(page.get_by_text("Memory search rebuild started for 11 memories.", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Download redacted diagnostics")).to_be_visible()
    assert writes == [{}]


def test_maintenance_routes_portable_backups_to_owned_story_exports(
    page: Page, ui_base_url: str
) -> None:
    """Keeps backup promises attached to the per-story export that actually owns them."""
    _open_settings(page, ui_base_url, category="maintenance")

    expect(page.get_by_text("Portable story backups", exact=True)).to_be_visible()
    backup = page.get_by_role("link", name="Manage portable story backups")
    expect(backup).to_have_attribute("href", "#/library/stories")


def test_maintenance_stages_host_sign_out_before_destroying_session(
    page: Page, ui_base_url: str
) -> None:
    writes: list[dict[str, object]] = []

    def logout(route) -> None:
        writes.append(route.request.post_data_json)
        route.fulfill(content_type="application/json", body=json.dumps({"ok": True}))

    page.route("**/api/auth/logout", logout)
    page.route("**/login", lambda route: route.fulfill(body="signed out"))
    _open_settings(page, ui_base_url, category="maintenance")

    page.get_by_role("button", name="Sign out").click()
    expect(page.get_by_text("Sign out of this host session?", exact=True)).to_be_visible()
    assert writes == []
    page.get_by_role("button", name="Confirm sign out").click()
    page.wait_for_url("**/login")
    assert writes == [{}]


def test_mobile_advanced_keeps_prompt_tools_without_horizontal_overflow(
    page: Page, ui_base_url: str
) -> None:
    """Protects compact Settings from dropping or clipping Advanced functionality."""
    _open_settings(page, ui_base_url, width=390, height=844, category="advanced")

    page.get_by_role("button", name="Prompt editor").click()
    expect(page.get_by_role("heading", name="Advanced", level=2)).to_be_visible()
    expect(page.get_by_role("combobox", name="Prompt preset", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Save prompt preset")).to_be_visible()
    geometry = page.evaluate(
        """() => ({
          viewport: document.documentElement.clientWidth,
          scroll: document.documentElement.scrollWidth,
          main: document.querySelector('.ui-settings__content')?.getBoundingClientRect().width,
        })"""
    )
    assert geometry["viewport"] == 390
    assert geometry["scroll"] <= geometry["viewport"]
    assert geometry["main"] <= geometry["viewport"]
