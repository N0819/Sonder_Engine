"""Source contracts for the WP-03 replacement application shell."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"
SHELL_MODULES = (
    "shell.js",
    "navigation-state.js",
    "destinations.js",
    "inspector-host.js",
    "shortcuts.js",
    "go-to.js",
    "extension-host.js",
)


def test_shell_sources_are_explicit_release_coherent_modules():
    missing = [name for name in SHELL_MODULES if not (RUNTIME / name).is_file()]
    assert missing == []

    releases = set()
    for name in SHELL_MODULES:
        source = (RUNTIME / name).read_text(encoding="utf-8")
        match = re.search(r'export const MODULE_RELEASE = "([^"]+)";', source)
        assert match, name
        releases.add(match.group(1))

    assert releases == {"alpha98-ui2-d5cf750f8b7e"}


def test_application_entry_uses_the_semantic_shell_and_no_classic_assets():
    html = (ROOT / "static" / "ui-next.html").read_text(encoding="utf-8")

    assert 'data-ui-next-entry="application"' in html
    assert 'data-ui-next-version="alpha98-ui2-d5cf750f8b7e"' in html
    assert '/static/css/ui/shell.css?release=alpha98-ui2-d5cf750f8b7e' in html
    assert '/static/js/ui-next/main.js?release=alpha98-ui2-d5cf750f8b7e' in html
    assert '<nav ' in html
    assert '<main ' in html
    assert 'data-ui-region="inspector"' in html
    assert 'data-ui-region="overlays"' in html
    assert 'data-ui-region="notices"' in html
    assert 'data-ui-region="tasks"' in html

    for forbidden in (
        "/static/styles.css",
        "/static/themes.css",
        "/static/js/app.js",
        "/static/js/utils.js",
        "/static/js/extensions.js",
    ):
        assert forbidden not in html


def test_shell_declares_exactly_three_core_destinations_and_four_layout_states():
    destinations = (RUNTIME / "destinations.js").read_text(encoding="utf-8")
    shell = (RUNTIME / "shell.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "ui" / "shell.css").read_text(
        encoding="utf-8"
    )

    match = re.search(
        r"CORE_DESTINATIONS\s*=\s*Object\.freeze\(\[([^\]]+)", destinations
    )
    assert match
    assert re.findall(r'"([a-z-]+)"', match.group(1)) == [
        "play",
        "library",
        "settings",
    ]
    assert "global-settings" not in shell
    for state in ("compact", "medium", "wide", "expansive"):
        assert f'"{state}"' in shell
        assert f'[data-layout-state="{state}"]' in css


def test_shell_has_no_legacy_or_hidden_compatibility_mechanisms():
    paths = [RUNTIME / name for name in SHELL_MODULES]
    paths.append(ROOT / "static" / "css" / "ui" / "shell.css")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for forbidden in (
        "window.S ",
        "window.S=",
        "clickLegacy",
        "MutationObserver",
        "setInterval(",
        ".click()",
        ".innerHTML",
        "!important",
        "position: absolute; left: -",
        "position:absolute;left:-",
    ):
        assert forbidden not in combined


def test_shell_owns_navigation_focus_scroll_shortcuts_and_extension_hosts():
    navigation = (RUNTIME / "navigation-state.js").read_text(encoding="utf-8")
    shortcuts = (RUNTIME / "shortcuts.js").read_text(encoding="utf-8")
    go_to = (RUNTIME / "go-to.js").read_text(encoding="utf-8")
    extension_host = (RUNTIME / "extension-host.js").read_text(encoding="utf-8")

    assert "scrollRegions" in navigation
    assert "focusIdentity" in navigation
    assert "localState" in navigation
    assert "contenteditable" in shortcuts.lower()
    assert "isComposing" in shortcuts
    assert "collision" in shortcuts.lower()
    assert "aria-activedescendant" in go_to
    assert "focusReturn" in go_to
    assert "registry.run" in extension_host
    assert "legacy-view" in extension_host
    assert "unregister" in extension_host.lower()
