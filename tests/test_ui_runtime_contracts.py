"""Source contracts for the replacement runtime boundary."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"
MODULES = (
    "release.js",
    "bootstrap.js",
    "api.js",
    "errors.js",
    "store.js",
    "router.js",
    "localization.js",
    "content.js",
    "tasks.js",
    "notices.js",
    "diagnostics.js",
    "storage.js",
    "credentials.js",
    "save-policy.js",
    "extensions.js",
    "extensions-v1.js",
    "destinations.js",
    "inspector-host.js",
    "navigation-state.js",
    "shortcuts.js",
    "go-to.js",
    "extension-host.js",
    "shell.js",
    "play-runtime.js",
    "play-view.js",
    "prose.js",
    "story-tools-registry.js",
    "story-tools-runtime.js",
    "story-tools-view.js",
)


def test_runtime_modules_have_one_literal_release_and_no_classic_bridge():
    missing = [name for name in MODULES if not (RUNTIME / name).is_file()]
    assert missing == []

    releases: set[str] = set()
    combined = ""
    for name in MODULES:
        text = (RUNTIME / name).read_text(encoding="utf-8")
        combined += f"\n/* {name} */\n{text}"
        match = re.search(r'export const MODULE_RELEASE = "([^"]+)";', text)
        assert match, name
        releases.add(match.group(1))

    assert releases == {"wp05.1"}
    assert "setInterval(" not in combined
    assert "MutationObserver" not in combined
    assert "window.S " not in combined
    assert "window.S=" not in combined
    assert "clickLegacy" not in combined
    assert ".click()" not in combined
    assert ".innerHTML" not in combined
    assert "console." not in combined


def test_v1_adapter_is_the_only_runtime_global_assignment():
    assignments: list[tuple[str, str]] = []
    for path in RUNTIME.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"(?:window|globalThis)\.([A-Za-z_$][\w$]*)\s*=(?!=)", text
        ):
            assignments.append((path.name, match.group(1)))
    assert assignments == [("extensions-v1.js", "Sonder")]


def test_runtime_entry_names_the_versioned_graph_and_no_classic_assets():
    html = (ROOT / "static" / "ui-next.html").read_text(encoding="utf-8")
    assert "?release=wp05.1" in html
    assert 'data-ui-next-version="wp05.1"' in html
    assert "/static/js/app.js" not in html
    assert "/static/js/utils.js" not in html
    assert "/static/js/extensions.js" not in html
    assert "/static/styles.css" not in html


def test_catalog_excludes_only_named_replacement_laboratories():
    source = (ROOT / "tools/extract_ui_catalog.py").read_text(encoding="utf-8")
    assert '"ui-next-lab.html"' in source
    assert '"ui-next-runtime.html"' in source
    assert '"ui-next/lab.js"' in source
    assert "rglob(\"*.js\")" in source


def test_credential_helper_has_no_persistence_or_navigation_surface():
    source = (RUNTIME / "credentials.js").read_text(encoding="utf-8")
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "location." not in source
    assert "history." not in source


def test_v1_fixture_uses_only_the_public_registry_contract():
    source = (
        ROOT / "browser_tests/fixtures/ui_v1_extension.js"
    ).read_text(encoding="utf-8")
    assert "window.Sonder" in source
    assert "querySelector" not in source
    assert "getElementById" not in source
    assert "window.S " not in source
