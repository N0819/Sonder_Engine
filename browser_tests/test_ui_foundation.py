"""Real-browser contracts for the replacement G1 component foundation."""

from __future__ import annotations

from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect


LAB = "/static/ui-next-lab.html"


def _open_lab(page: Page, ui_base_url: str) -> tuple[list[str], list[str]]:
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    response = page.goto(f"{ui_base_url}{LAB}")
    assert response is not None and response.ok
    expect(page.locator("html")).to_have_attribute("data-ui-next-ready", "true")
    return console_errors, page_errors


def test_component_lab_boots_without_api_or_browser_errors(page: Page, ui_base_url: str):
    requests: list[str] = []
    page.on("request", lambda request: requests.append(urlparse(request.url).path))
    console_errors, page_errors = _open_lab(page, ui_base_url)

    expect(page.get_by_role("heading", name="Component laboratory", level=1)).to_be_visible()
    expect(page.get_by_role("main")).to_be_visible()
    assert not any(path.startswith("/api/") for path in requests)
    assert console_errors == []
    assert page_errors == []


@pytest.mark.parametrize(
    "theme",
    [
        "carbon-signal",
        "ash-brass",
        "midnight-ink",
        "parchment-night",
        "neon-circuit",
        "modern-slate",
    ],
)
def test_all_curated_themes_apply_semantic_color_roles(page: Page, ui_base_url: str, theme: str):
    _open_lab(page, ui_base_url)
    button = page.locator(f'[data-theme-choice="{theme}"]')
    button.click()
    expect(page.locator("html")).to_have_attribute("data-theme", theme)
    expect(button).to_have_attribute("aria-pressed", "true")
    colors = page.evaluate("""() => {
      const style = getComputedStyle(document.documentElement);
      return [style.getPropertyValue('--ui-color-canvas'), style.getPropertyValue('--ui-color-interactive')];
    }""")
    assert all(color.strip().startswith("rgb") for color in colors)


def test_reduced_motion_is_stamped_before_component_module_boot(page: Page, ui_base_url: str):
    page.emulate_media(reduced_motion="reduce")
    _open_lab(page, ui_base_url)
    assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--ui-motion-default').trim()") == "0ms"
    expect(page.locator("html")).to_have_attribute("data-system-reduced-motion", "true")


def test_accessibility_mode_applies_coherent_preset_then_allows_granular_change(page: Page, ui_base_url: str):
    _open_lab(page, ui_base_url)
    page.get_by_label("Accessibility Mode").check()
    root = page.locator("html")
    for attribute in (
        "data-a11y-solid", "data-a11y-high-contrast", "data-a11y-strong-focus",
        "data-a11y-reduced-motion", "data-a11y-large-ui", "data-a11y-large-prose",
        "data-a11y-roomy-targets", "data-a11y-status-markers",
    ):
        expect(root).to_have_attribute(attribute, "true")
    page.get_by_label("Solid surfaces").uncheck()
    expect(root).to_have_attribute("data-a11y-solid", "false")
    expect(page.get_by_label("Accessibility Mode")).not_to_be_checked()
    expect(root).to_have_attribute("data-a11y-high-contrast", "true")


def test_tabs_use_roving_focus_and_arrow_activation(page: Page, ui_base_url: str):
    _open_lab(page, ui_base_url)
    summary = page.get_by_role("tab", name="Summary")
    cast = page.get_by_role("tab", name="Cast")
    summary.focus()
    page.keyboard.press("ArrowRight")
    expect(cast).to_be_focused()
    expect(cast).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("tabpanel", name="Cast")).to_be_visible()
    page.keyboard.press("End")
    expect(page.get_by_role("tab", name="World")).to_be_focused()


def test_dialog_contains_focus_closes_with_escape_and_restores_opener(page: Page, ui_base_url: str):
    _open_lab(page, ui_base_url)
    opener = page.get_by_role("button", name="Open confirmation dialog")
    opener.click()
    dialog = page.get_by_role("dialog", name="Delete this draft?")
    expect(dialog).to_be_visible()
    expect(page.get_by_role("button", name="Close dialog")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(page.get_by_role("button", name="Delete draft")).to_be_focused()
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(opener).to_be_focused()


def test_validation_error_is_related_to_the_field(page: Page, ui_base_url: str):
    _open_lab(page, ui_base_url)
    page.get_by_role("button", name="Validate example").click()
    field = page.get_by_label("Story name")
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-invalid", "true")
    described_by = field.get_attribute("aria-describedby") or ""
    assert "story-name-help" in described_by
    assert "story-name-error" in described_by
    expect(page.locator("#story-name-error")).to_contain_text("Enter a story name")


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900},
    {"width": 1024, "height": 768},
    {"width": 390, "height": 844},
    {"width": 360, "height": 640},
    {"width": 844, "height": 390},
])
def test_lab_has_no_horizontal_page_overflow(page: Page, ui_base_url: str, viewport: dict[str, int]):
    page.set_viewport_size(viewport)
    _open_lab(page, ui_base_url)
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1
    expect(page.get_by_role("button", name="Review connected characters")).to_be_visible()


def test_200_percent_zoom_equivalent_keeps_primary_actions_reachable(page: Page, ui_base_url: str):
    # A 1280x720 display at 200% browser zoom exposes a 640x360 CSS-pixel viewport.
    page.set_viewport_size({"width": 640, "height": 360})
    _open_lab(page, ui_base_url)
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1
    expect(page.get_by_role("button", name="Review connected characters")).to_be_visible()
    expect(page.get_by_role("button", name="Open confirmation dialog")).to_be_visible()


def test_mobile_targets_are_at_least_44_css_pixels(page: Page, ui_base_url: str):
    page.set_viewport_size({"width": 390, "height": 844})
    _open_lab(page, ui_base_url)
    targets = page.locator("button:visible, input:visible, select:visible, textarea:visible").evaluate_all(
        "elements => elements.map(element => ({label: element.getAttribute('aria-label') || element.textContent.trim(), width: element.getBoundingClientRect().width, height: element.getBoundingClientRect().height}))"
    )
    undersized = [target for target in targets if target["height"] < 43.5 or target["width"] < 43.5]
    assert undersized == []


def test_every_sprite_icon_keeps_fill_and_stroke_inside_its_viewbox(
    page: Page, ui_base_url: str
):
    _open_lab(page, ui_base_url)
    measurements = page.evaluate(
        """async () => {
          const source = await fetch('/static/assets/icons/sonder-icons.svg?release=alpha98-ui10-c14a4cf8dabd').then(response => response.text());
          const sprite = new DOMParser().parseFromString(source, 'image/svg+xml');
          const host = document.createElement('div');
          host.style.cssText = 'position:fixed;inset:0 auto auto 0;display:flex;visibility:hidden';
          const rows = [];
          for (const symbol of sprite.querySelectorAll('symbol')) {
            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            const viewBox = symbol.viewBox.baseVal;
            svg.setAttribute('viewBox', symbol.getAttribute('viewBox'));
            svg.setAttribute('width', '96');
            svg.setAttribute('height', '96');
            for (const name of ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit']) {
              if (symbol.hasAttribute(name)) svg.setAttribute(name, symbol.getAttribute(name));
            }
            for (const child of symbol.children) svg.append(child.cloneNode(true));
            host.append(svg);
            rows.push({ id: symbol.id, svg, viewBox });
          }
          document.body.append(host);
          const measurements = rows.map(({ id, svg, viewBox }) => {
            const bounds = svg.getBBox();
            const stroked = [...svg.querySelectorAll('*')].some(node => getComputedStyle(node).stroke !== 'none');
            const strokeWidth = stroked ? Math.max(
              Number.parseFloat(getComputedStyle(svg).strokeWidth) || 0,
              ...[...svg.querySelectorAll('*')].map(node => Number.parseFloat(getComputedStyle(node).strokeWidth) || 0),
            ) : 0;
            const inset = {
              left: bounds.x - strokeWidth / 2 - viewBox.x,
              top: bounds.y - strokeWidth / 2 - viewBox.y,
              right: viewBox.x + viewBox.width - (bounds.x + bounds.width + strokeWidth / 2),
              bottom: viewBox.y + viewBox.height - (bounds.y + bounds.height + strokeWidth / 2),
            };
            return { id, inset };
          });
          host.remove();
          return measurements;
        }""",
    )
    clipped = [
        row
        for row in measurements
        if min(row["inset"].values()) < -0.01
    ]
    assert clipped == []
