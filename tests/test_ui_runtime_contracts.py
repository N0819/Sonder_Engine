"""Source contracts for the replacement runtime boundary."""

from __future__ import annotations

import hashlib
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
    "library-runtime.js",
    "library-view.js",
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
    "atmosphere-runtime.js",
)

IMMUTABLE_UI_ROOTS = (
    ROOT / "static" / "js" / "ui-next",
    ROOT / "static" / "js" / "ui",
    ROOT / "static" / "css" / "ui",
)
IMMUTABLE_UI_FILES = (ROOT / "static" / "assets" / "icons" / "sonder-icons.svg",)
RELEASE_TOKEN = re.compile(rb"alpha98-ui\d+(?:-[0-9a-f]{12})?")


def _immutable_ui_fingerprint() -> str:
    paths = [
        path
        for root in IMMUTABLE_UI_ROOTS
        for path in root.rglob("*")
        if path.is_file()
    ]
    paths.extend(IMMUTABLE_UI_FILES)
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda candidate: candidate.relative_to(ROOT).as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        normalized = RELEASE_TOKEN.sub(b"__UI_RELEASE__", path.read_bytes())
        digest.update(normalized.replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()[:12]


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

    assert len(releases) == 1
    release = releases.pop()
    assert re.fullmatch(r"alpha98-ui\d+-[0-9a-f]{12}", release)
    assert release.rsplit("-", 1)[1] == _immutable_ui_fingerprint()
    graph_releases = {
        match.group(1)
        for path in RUNTIME.rglob("*.js")
        if (
            match := re.search(
                r'export const MODULE_RELEASE = "([^"]+)";',
                path.read_text(encoding="utf-8"),
            )
        )
    }
    assert graph_releases == {release}
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
    release_source = (RUNTIME / "release.js").read_text(encoding="utf-8")
    release = re.search(r'export const MODULE_RELEASE = "([^"]+)";', release_source)
    assert release
    assert f"?release={release.group(1)}" in html
    assert f'data-ui-next-version="{release.group(1)}"' in html
    assert "/static/js/app.js" not in html
    assert "/static/js/utils.js" not in html
    assert "/static/js/extensions.js" not in html
    assert "/static/styles.css" not in html


def test_every_replacement_entry_and_server_release_reference_is_coherent():
    release_source = (RUNTIME / "release.js").read_text(encoding="utf-8")
    release = re.search(r'export const MODULE_RELEASE = "([^"]+)";', release_source)
    assert release
    sources = [
        *(ROOT / "static").glob("ui-next*.html"),
        ROOT / "static" / "login.html",
        ROOT / "static" / "guest.html",
        ROOT / "web" / "app.py",
        *RUNTIME.rglob("*.js"),
    ]
    references = {
        match
        for path in sources
        for match in re.findall(
            r"alpha98-ui\d+(?:-[0-9a-f]{12})?",
            path.read_text(encoding="utf-8"),
        )
    }
    assert references == {release.group(1)}

    entry_sources = [
        *(ROOT / "static").glob("ui-next*.html"),
        ROOT / "static" / "login.html",
        ROOT / "static" / "guest.html",
    ]
    entry_references = {
        match
        for path in entry_sources
        for match in re.findall(
            r"[?&]release=([A-Za-z0-9.-]+)",
            path.read_text(encoding="utf-8"),
        )
    }
    assert entry_references == {release.group(1)}


def test_every_icon_sprite_request_uses_the_immutable_ui_release():
    release_source = (RUNTIME / "release.js").read_text(encoding="utf-8")
    release = re.search(r'export const MODULE_RELEASE = "([^"]+)";', release_source)
    assert release
    sources = [
        ROOT / "static" / "ui-next.html",
        *(ROOT / "static" / "js" / "ui").rglob("*.js"),
        *RUNTIME.rglob("*.js"),
    ]
    references = [
        line.strip()
        for path in sources
        for line in path.read_text(encoding="utf-8").splitlines()
        if "sonder-icons.svg" in line
    ]
    assert references
    assert all("sonder-icons.svg?release=" in line for line in references)
    assert all(
        release.group(1) in line or "${MODULE_RELEASE}" in line
        for line in references
    )


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
