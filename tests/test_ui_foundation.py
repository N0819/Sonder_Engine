"""Source contracts for the isolated replacement visual foundation."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "static" / "css" / "ui"
JS = ROOT / "static" / "js" / "ui"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_foundation_has_explicit_responsibility_boundaries():
    required = [
        CSS / "reset.css",
        CSS / "tokens.css",
        CSS / "typography.css",
        CSS / "components.css",
        CSS / "utilities.css",
        JS / "appearance-preflight.js",
        JS / "appearance.js",
        JS / "accessibility.js",
        JS / "components" / "focus.js",
        JS / "components" / "overlay.js",
        JS / "components" / "roving-focus.js",
        JS / "components" / "live-region.js",
        ROOT / "static" / "ui-next-lab.html",
    ]
    assert not [str(path.relative_to(ROOT)) for path in required if not path.is_file()]


def test_tokens_pin_the_bible_geometry_type_motion_and_layers():
    tokens = _read(CSS / "tokens.css")
    required_pairs = {
        "--ui-space-0": "0px",
        "--ui-space-1": "2px",
        "--ui-space-2": "4px",
        "--ui-space-3": "6px",
        "--ui-space-4": "8px",
        "--ui-space-5": "12px",
        "--ui-space-6": "16px",
        "--ui-space-7": "20px",
        "--ui-space-8": "24px",
        "--ui-space-9": "32px",
        "--ui-space-10": "40px",
        "--ui-space-11": "48px",
        "--ui-radius-sm": "3px",
        "--ui-radius-md": "4px",
        "--ui-radius-lg": "5px",
        "--ui-control-compact": "32px",
        "--ui-control-default": "36px",
        "--ui-control-prominent": "40px",
        "--ui-target-touch": "44px",
        "--ui-motion-fast": "120ms",
        "--ui-motion-default": "180ms",
        "--ui-motion-slow": "260ms",
        "--ui-prose-size": "17px",
        "--ui-prose-leading": "1.7",
        "--ui-prose-measure": "720px",
    }
    for name, value in required_pairs.items():
        assert re.search(rf"{re.escape(name)}\s*:\s*{re.escape(value)}\s*;", tokens), name
    for band in ("base", "raised", "sticky", "dropdown", "overlay", "modal", "toast"):
        assert f"--ui-z-{band}:" in tokens


def test_curated_themes_are_local_semantic_overrides():
    names = (
        "carbon-signal",
        "ash-brass",
        "midnight-ink",
        "parchment-night",
        "neon-circuit",
        "modern-slate",
    )
    for name in names:
        text = _read(CSS / "themes" / f"{name}.css")
        assert f'[data-theme="{name}"]' in text
        assert "--ui-color-canvas:" in text
        assert "--ui-color-interactive:" in text
        assert "url(" not in text.lower()

    for entry in (
        ROOT / "static" / "ui-next.html",
        ROOT / "static" / "ui-next-runtime.html",
        ROOT / "static" / "ui-next-lab.html",
        ROOT / "static" / "login.html",
        ROOT / "static" / "guest.html",
    ):
        html = _read(entry)
        for name in names:
            assert f"/static/css/ui/themes/{name}.css" in html, (entry.name, name)


def test_modern_slate_is_strictly_warm_neutral_with_no_blue_lean():
    text = _read(CSS / "themes" / "modern-slate.css")
    colors = re.findall(r"rgb\(\s*(\d+)\s+(\d+)\s+(\d+)", text)
    assert len(colors) >= 15
    for red, green, blue in colors:
        channels = tuple(map(int, (red, green, blue)))
        assert channels[0] >= channels[1] >= channels[2], channels
        assert channels[0] - channels[2] <= 8, channels
    assert "--ui-color-interactive: rgb(" in text
    assert "--ui-color-focus-outer: var(--ui-color-interactive-strong)" in text


def test_custom_theme_entry_and_preflight_use_only_fixed_semantic_properties():
    custom_css = _read(CSS / "themes" / "custom.css")
    module = _read(JS / "custom-theme.js")
    preflight = _read(JS / "appearance-preflight.js")
    properties = (
        "background", "panel", "text", "muted", "accent", "attention", "success", "danger"
    )
    for role in properties:
        assert f"--ui-custom-{role}" in custom_css
        assert f"--ui-custom-{role}" in module
        assert f"--ui-custom-{role}" in preflight
    assert '[data-theme="custom"]' in custom_css
    assert "url(" not in custom_css.lower()
    assert "innerHTML" not in module
    for entry in (
        "ui-next.html", "ui-next-runtime.html", "ui-next-lab.html", "login.html", "guest.html"
    ):
        assert "/static/css/ui/themes/custom.css" in _read(ROOT / "static" / entry)


def test_components_are_scoped_and_consume_semantic_tokens():
    text = _read(CSS / "components.css")
    assert not re.search(r"(?m)^\s*(button|input|select|textarea|details|\.card)(?:\s|,|\{|:)", text)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", text)
    for family in (
        "button", "field", "toggle", "segmented", "tabs", "menu", "list-row",
        "card", "cluster", "dialog", "sheet", "notice", "task", "skeleton", "empty",
    ):
        assert f".ui-{family}" in text
    assert ":where(.ui-app, .ui-lab) select" in text
    assert "appearance: none" in text


def test_replacement_entries_are_head_safe_and_legacy_free():
    for name in ("ui-next.html", "ui-next-lab.html", "ui-next-runtime.html"):
        html = _read(ROOT / "static" / name)
        assert '/static/js/ui/appearance-preflight.js' in html
        assert html.index("appearance-preflight.js") < html.index("tokens.css")
        assert "themes.css" not in html
        assert "styles.css" not in html
        assert "/static/js/app.js" not in html
        assert "window.S" not in html

    extractor = _read(ROOT / "tools" / "extract_ui_catalog.py")
    assert '"ui-next-lab.html"' in extractor
    assert '"ui-next-runtime.html"' in extractor
    assert "if path.name not in DEVELOPMENT_HTML_FILES" in extractor


def test_foundation_has_no_polling_or_external_asset_dependency():
    paths = [*CSS.rglob("*.css"), *JS.rglob("*.js")]
    text = "\n".join(_read(path) for path in paths)
    assert "setInterval(" not in text
    assert "MutationObserver" not in text
    # The SVG DOM namespace is an identifier, not a network request.
    without_svg_namespace = text.replace("http://www.w3.org/2000/svg", "")
    assert not re.search(r"https?://", without_svg_namespace)


def test_accessibility_vocabulary_and_reduced_motion_are_complete():
    tokens = _read(CSS / "tokens.css")
    accessibility = _read(JS / "accessibility.js")
    for setting in (
        "solidSurfaces", "highContrast", "strongFocus", "reducedMotion",
        "largeUi", "largeProse", "roomyTargets", "statusMarkers",
    ):
        assert setting in accessibility
    assert "prefers-reduced-motion: reduce" in tokens
    assert 'data-a11y-reduced-motion="true"' in tokens
