"""Source contracts for the replacement Library surface."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"


def test_library_modules_are_in_the_wp06_release_graph():
    bootstrap = (RUNTIME / "bootstrap.js").read_text(encoding="utf-8")
    html = (ROOT / "static" / "ui-next.html").read_text(encoding="utf-8")
    for name in ("library-runtime.js", "library-view.js"):
        source = (RUNTIME / name).read_text(encoding="utf-8")
        assert 'export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";' in source
        assert name in bootstrap
    assert 'data-ui-next-version="alpha98-ui15-5b0f039aae29"' in html
    assert "/static/css/ui/library.css?release=alpha98-ui15-5b0f039aae29" in html


def test_library_runtime_owns_projection_requests_and_bounded_local_state():
    source = (RUNTIME / "library-runtime.js").read_text(encoding="utf-8")
    assert '"/api/library?' in source
    assert 'channel: "library-projection"' in source
    assert "isCurrent:" in source
    assert "limit" in source
    assert "100" in source
    assert "MAX_FAVORITES = 20" in source
    assert "MAX_RECENTS = 50" in source
    assert "setRecord(\"panes\"" in source
    for forbidden in (
        "localStorage", "sessionStorage", "sheet", "memory", "api_key",
        "password", "MutationObserver", "setInterval(", "confirm(", "prompt(",
    ):
        assert forbidden not in source


def test_library_view_is_semantic_bounded_and_classic_independent():
    source = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    assert "slice(0, 100)" in source
    assert "dataset.libraryLedger" in source
    assert "aria-current" in source
    assert "Not used" in source
    assert "Used in" in source
    assert "Unavailable item" in source
    for forbidden in (
        "#sidelist", "hostState", "window.S", "MutationObserver", ".click()",
        ".innerHTML", "confirm(", "prompt(", "setInterval(",
    ):
        assert forbidden not in source


def test_library_route_contract_keeps_names_out_of_stable_identity():
    source = (RUNTIME / "library-runtime.js").read_text(encoding="utf-8")
    assert re.search(r"ITEM_ID\s*=.*story.*character.*persona.*lore", source)
    assert "canonicalHash" in source
    assert "item.name" not in source
    assert "story_name" not in source
