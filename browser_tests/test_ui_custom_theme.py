"""Safe custom-theme contracts for the replacement interface."""

from __future__ import annotations

import json

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


def _open_settings(page: Page, ui_base_url: str, *, width: int = 1440) -> None:
    page.set_viewport_size({"width": width, "height": 900 if width >= 1000 else 844})
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(BOOTSTRAP)
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/settings/experience")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )


def test_custom_theme_module_enforces_schema_contrast_and_fixed_properties(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const theme = await import(`${base}/static/js/ui/custom-theme.js?contract=1`);
          const palette = { ...theme.DEFAULT_CUSTOM_THEME, accent: '#80e4e8' };
          const serialized = theme.serializeCustomTheme(palette);
          const parsed = theme.parseCustomTheme(serialized);
          const written = {};
          theme.applyCustomTheme({ style: { setProperty: (name, value) => {
            written[name] = value;
          } } }, parsed);
          const rejects = [
            JSON.stringify({ version: 2, colors: palette }),
            JSON.stringify({ version: 1, colors: { ...palette, css: 'body{}' } }),
            JSON.stringify({ version: 1, colors: { ...palette, accent: 'url(x)' } }),
            JSON.stringify({ version: 1, colors: { ...palette, '--evil': '#ffffff' } }),
            '<style>body{display:none}</style>',
          ].map(value => {
            try { theme.parseCustomTheme(value); return false; }
            catch (_) { return true; }
          });
          const invalid = theme.validateCustomTheme({ ...palette, text: '#101010' });
          return {
            roles: theme.CUSTOM_THEME_ROLES.map(role => role.id),
            normalized: theme.normalizeHex('#abc'),
            rgb: theme.rgbToHex({ red: 128, green: 228, blue: 232 }),
            parsed,
            written,
            rejects,
            invalid: { valid: invalid.valid, errors: invalid.errors },
            contrast: theme.contrastRatio('#FFFFFF', '#000000'),
          };
        }""",
        ui_base_url,
    )
    assert result["roles"] == [
        "background", "panel", "text", "muted", "accent", "attention", "success", "danger"
    ]
    assert result["normalized"] == "#AABBCC"
    assert result["rgb"] == "#80E4E8"
    assert result["parsed"]["accent"] == "#80E4E8"
    assert list(result["written"]) == [
        "--ui-custom-background",
        "--ui-custom-panel",
        "--ui-custom-text",
        "--ui-custom-muted",
        "--ui-custom-accent",
        "--ui-custom-attention",
        "--ui-custom-success",
        "--ui-custom-danger",
    ]
    assert result["rejects"] == [True, True, True, True, True]
    assert result["invalid"]["valid"] is False
    assert any("Primary text" in error for error in result["invalid"]["errors"])
    assert result["contrast"] == 21


def test_custom_theme_preflight_applies_only_a_valid_fixed_palette(
    page: Page, ui_base_url: str
) -> None:
    palette = {
        "background": "#090D10",
        "panel": "#141B20",
        "text": "#EEF3F2",
        "muted": "#AEB9B7",
        "accent": "#80E4E8",
        "attention": "#D0A75B",
        "success": "#76C29A",
        "danger": "#DC747D",
    }
    payload = json.dumps({"version": 1, "colors": palette})
    page.add_init_script(
        f"""(() => {{
          localStorage.setItem('sonder.ui.next.theme.v1', 'custom');
          localStorage.setItem('sonder.ui.next.custom-theme.v1', JSON.stringify({payload}));
        }})()"""
    )
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    state = page.locator("html").evaluate(
        """node => ({
          theme: node.dataset.theme,
          accent: node.style.getPropertyValue('--ui-custom-accent'),
          properties: [...node.style].filter(name => name.startsWith('--ui-custom-')),
          evil: node.style.getPropertyValue('--evil'),
        })"""
    )
    assert state == {
        "theme": "custom",
        "accent": "#80E4E8",
        "properties": [
            "--ui-custom-background", "--ui-custom-panel", "--ui-custom-text",
            "--ui-custom-muted", "--ui-custom-accent", "--ui-custom-attention",
            "--ui-custom-success", "--ui-custom-danger",
        ],
        "evil": "",
    }

    invalid = {**palette, "text": "#101010", "accent": "#111111"}
    invalid["--evil"] = "#FFFFFF"
    page.evaluate(
        """payload => localStorage.setItem(
          'sonder.ui.next.custom-theme.v1', JSON.stringify(payload)
        )""",
        {"version": 1, "colors": invalid},
    )
    page.reload()
    rejected = page.locator("html").evaluate(
        """node => ({
          text: node.style.getPropertyValue('--ui-custom-text'),
          accent: node.style.getPropertyValue('--ui-custom-accent'),
          evil: node.style.getPropertyValue('--evil'),
        })"""
    )
    assert rejected == {"text": "#EEF3F2", "accent": "#80E4E8", "evil": ""}


def test_custom_theme_editor_syncs_hex_rgb_and_persists_after_reload(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url)
    expect(page.get_by_role("heading", name="Custom Theme", exact=True)).to_be_visible()
    expect(page.locator("[data-custom-theme-swatch]")).to_have_count(8)

    page.get_by_role("button", name="Edit Accent color", exact=True).click()
    dialog = page.get_by_role("dialog", name="Choose Accent color")
    expect(dialog).to_be_visible()
    hex_field = dialog.get_by_role("textbox", name="Hex color")
    hex_field.fill("#80e4e8")
    expect(dialog.get_by_role("spinbutton", name="Red")).to_have_value("128")
    expect(dialog.get_by_role("spinbutton", name="Green")).to_have_value("228")
    expect(dialog.get_by_role("spinbutton", name="Blue")).to_have_value("232")
    expect(dialog.get_by_label("Color", exact=True)).to_have_value("#80e4e8")
    dialog.get_by_role("button", name="Save color").click()
    expect(dialog).to_be_hidden()

    page.get_by_role("button", name="Use Custom Theme", exact=True).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "custom")
    stored = page.evaluate(
        "JSON.parse(localStorage.getItem('sonder.ui.next.custom-theme.v1'))"
    )
    assert stored["version"] == 1
    assert stored["colors"]["accent"] == "#80E4E8"

    page.reload()
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    expect(page.locator("html")).to_have_attribute("data-theme", "custom")
    accent = page.locator("html").evaluate(
        "node => getComputedStyle(node).getPropertyValue('--ui-color-interactive').trim()"
    )
    assert accent == "#80E4E8"


def test_custom_theme_invalid_color_cannot_replace_saved_state_and_mobile_fits(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url, width=390)
    original = page.evaluate(
        "localStorage.getItem('sonder.ui.next.custom-theme.v1')"
    )
    opener = page.get_by_role("button", name="Edit Primary text color", exact=True)
    opener.click()
    dialog = page.get_by_role("dialog", name="Choose Primary text color")
    dialog.get_by_role("textbox", name="Hex color").fill("#101010")
    expect(dialog.locator(".ui-settings__color-error")).to_contain_text("Primary text")
    expect(dialog.get_by_role("button", name="Save color")).to_be_disabled()
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()
    expect(opener).to_be_focused()
    assert page.evaluate(
        "localStorage.getItem('sonder.ui.next.custom-theme.v1')"
    ) == original

    geometry = page.evaluate(
        """() => ({
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          targets: [...document.querySelectorAll('[data-custom-theme-editor] button')]
            .map(node => node.getBoundingClientRect().height),
        })"""
    )
    assert geometry["overflow"] <= 1
    assert geometry["targets"] and min(geometry["targets"]) >= 44

    page.get_by_role("button", name="Reset Custom Theme", exact=True).click()
    expect(page.get_by_text("Custom theme reset to its safe defaults.", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Import theme JSON", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Export theme JSON", exact=True)).to_be_visible()


def test_custom_theme_import_export_round_trip_rejects_extra_fields(
    page: Page, ui_base_url: str
) -> None:
    _open_settings(page, ui_base_url)
    colors = {
        "background": "#090D10",
        "panel": "#141B20",
        "text": "#EEF3F2",
        "muted": "#AEB9B7",
        "accent": "#8AE8EB",
        "attention": "#D0A75B",
        "success": "#76C29A",
        "danger": "#DC747D",
    }
    file_input = page.get_by_label("Custom theme JSON file")
    file_input.set_input_files({
        "name": "theme.json",
        "mimeType": "application/json",
        "buffer": json.dumps({"version": 1, "colors": colors}).encode(),
    })
    expect(page.get_by_text(
        "Custom theme JSON imported. Choose Use Custom Theme to save it.", exact=True
    )).to_be_visible()
    page.get_by_role("button", name="Use Custom Theme", exact=True).click()
    before = page.evaluate(
        "localStorage.getItem('sonder.ui.next.custom-theme.v1')"
    )
    assert json.loads(before)["colors"]["accent"] == "#8AE8EB"

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export theme JSON", exact=True).click()
    assert download_info.value.suggested_filename == "sonder-custom-theme.json"

    malicious = {"version": 1, "colors": {**colors, "css": "body{display:none}"}}
    file_input.set_input_files({
        "name": "bad-theme.json",
        "mimeType": "application/json",
        "buffer": json.dumps(malicious).encode(),
    })
    expect(page.locator("[data-custom-theme-validation]")).to_contain_text(
        "exactly the eight recognized color roles"
    )
    assert page.evaluate(
        "localStorage.getItem('sonder.ui.next.custom-theme.v1')"
    ) == before
