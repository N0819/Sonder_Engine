"""Source contracts for WP-05 Story Tools and contextual Play state."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"
STORY_TOOL_MODULES = (
    "story-tools-registry.js",
    "story-tools-runtime.js",
    "story-tools-view.js",
)
TOOL_IDS = (
    "cast",
    "world",
    "style",
    "dialogue",
    "attire",
    "backdrops",
    "ambience",
    "conditions",
    "frames",
    "multiplayer",
)


def test_story_tool_platform_is_a_release_coherent_native_module_family():
    missing = [name for name in STORY_TOOL_MODULES if not (RUNTIME / name).is_file()]
    assert missing == []

    releases = set()
    for name in STORY_TOOL_MODULES:
        source = (RUNTIME / name).read_text(encoding="utf-8")
        match = re.search(r'export const MODULE_RELEASE = "([^"]+)";', source)
        assert match, name
        releases.add(match.group(1))
    assert releases == {"alpha98-ui10-c14a4cf8dabd"}

    bootstrap = (RUNTIME / "bootstrap.js").read_text(encoding="utf-8")
    for module in STORY_TOOL_MODULES:
        assert f'"./{module}?release=alpha98-ui10-c14a4cf8dabd"' in bootstrap


def test_story_tool_registry_names_every_current_story_surface_once():
    source = (RUNTIME / "story-tools-registry.js").read_text(encoding="utf-8")
    match = re.search(r"STORY_TOOL_IDS\s*=\s*Object\.freeze\(\[([^\]]+)", source)
    assert match
    assert tuple(re.findall(r'"([a-z-]+)"', match.group(1))) == TOOL_IDS
    assert len(set(TOOL_IDS)) == len(TOOL_IDS)


def test_story_tool_routes_are_stable_and_inspector_content_is_mounted():
    router = (RUNTIME / "router.js").read_text(encoding="utf-8")
    inspector = (RUNTIME / "inspector-host.js").read_text(encoding="utf-8")
    view = (RUNTIME / "story-tools-view.js").read_text(encoding="utf-8")

    assert 'play: Object.freeze(["story-tools"])' in router
    assert "preserveLayers" in router
    assert "mountStoryTools" in inspector
    assert "dataset.storyTools" in view
    assert "dataset.storyToolList" in view
    assert "dataset.storyToolPanel" in view


def test_story_tool_runtime_owns_requests_by_story_frame_tool_and_sequence():
    source = (RUNTIME / "story-tools-runtime.js").read_text(encoding="utf-8")

    for contract in (
        "chatId",
        "frameId",
        "toolId",
        "sequence",
        "isCurrent",
        "story-tools:",
        "AbortController",
    ):
        assert contract in source


def test_story_tools_have_no_classic_or_hidden_bridge_mechanisms():
    paths = [RUNTIME / name for name in STORY_TOOL_MODULES]
    paths.extend(
        [
            RUNTIME / "inspector-host.js",
            ROOT / "static" / "css" / "ui" / "story-tools.css",
        ]
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for forbidden in (
        "window.S ",
        "window.S=",
        "clickLegacy",
        "MutationObserver",
        "setInterval(",
        ".click()",
        ".innerHTML",
        "prompt(",
        "confirm(",
        "display:none!important",
        "display: none !important",
    ):
        assert forbidden not in combined


def test_story_tool_css_declares_bounded_inspector_and_mobile_sheet_contracts():
    source = (ROOT / "static" / "css" / "ui" / "story-tools.css").read_text(
        encoding="utf-8"
    )

    assert "container-type" in source
    assert '--ui-shell-inspector: 352px' in source
    assert '--ui-shell-inspector: 232px' in source
    assert '--ui-shell-inspector: 80px' in source
    assert "44px" in source
    assert "env(safe-area-inset-bottom)" in source
    assert "overflow-x: hidden" in source
    assert "!important" not in source
