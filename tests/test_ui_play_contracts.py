"""Source contracts for the WP-04 replacement Play workflow."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"
PLAY_MODULES = ("play-runtime.js", "play-view.js", "prose.js")


def test_play_sources_are_release_coherent_native_modules():
    missing = [name for name in PLAY_MODULES if not (RUNTIME / name).is_file()]
    assert missing == []

    releases = set()
    combined = ""
    for name in PLAY_MODULES:
        source = (RUNTIME / name).read_text(encoding="utf-8")
        combined += source
        match = re.search(r'export const MODULE_RELEASE = "([^"]+)";', source)
        assert match, name
        releases.add(match.group(1))

    assert releases == {"alpha98-ui15-5b0f039aae29"}
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
    ):
        assert forbidden not in combined


def test_play_uses_owned_story_drafts_and_current_server_routes():
    runtime = (RUNTIME / "play-runtime.js").read_text(encoding="utf-8")
    bootstrap = (RUNTIME / "bootstrap.js").read_text(encoding="utf-8")

    assert 'getDraft("story"' in runtime
    assert 'setDraft("story"' in runtime
    assert "/api/chats/" in runtime
    assert "/turns" in runtime
    assert "/abort" in runtime
    assert "/reroll" in runtime
    assert "/narration" in runtime
    assert "/export" in runtime
    assert "isCurrent" in runtime
    assert "frameId" in runtime
    assert "registry?.emitEvent?.(`turn:${event.type}`" in runtime
    for module in ("play-runtime.js", "play-view.js", "prose.js"):
        assert f'"./{module}?release=alpha98-ui15-5b0f039aae29"' in bootstrap


def test_play_entry_declares_semantic_transcript_composer_and_styles():
    html = (ROOT / "static" / "ui-next.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "ui" / "play.css")
    view = (RUNTIME / "play-view.js")

    assert css.is_file()
    assert view.is_file()
    assert "/static/css/ui/play.css?release=alpha98-ui15-5b0f039aae29" in html
    source = view.read_text(encoding="utf-8")
    for contract in (
        "data-play-transcript",
        "data-play-composer",
        "data-play-send",
        "data-play-stop",
        "data-play-progress",
        "New turn",
    ):
        assert contract in source


def test_prose_renderer_never_parses_model_output_as_html():
    source = (RUNTIME / "prose.js").read_text(encoding="utf-8")

    assert "createTextNode" in source
    assert "replaceChildren" in source
    assert "innerHTML" not in source
    assert "DOMParser" not in source
    assert "speech" in source
    assert "emphasis" in source.lower()


def test_play_css_owns_measure_scrollback_and_mobile_composer_geometry():
    source = (ROOT / "static" / "css" / "ui" / "play.css").read_text(
        encoding="utf-8"
    )

    assert "--play-reading-measure" in source
    assert "content-visibility: auto" in source
    assert "contain-intrinsic-size" in source
    assert "env(safe-area-inset-bottom)" in source
    assert "container-type" in source
    assert "position: sticky" in source
    assert "44px" in source
    assert "!important" not in source
