"""Behavioral tests for the reproducible UI replacement source inventory.

The breaks named here are a source seam disappearing from the generated
inventory, output order changing between runs, or a current capability losing
its replacement owner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def ui_fixture(tmp_path: Path) -> Path:
    (tmp_path / "web").mkdir()
    (tmp_path / "static" / "js").mkdir(parents=True)
    (tmp_path / "language_packs" / "en").mkdir(parents=True)
    (tmp_path / "web" / "app.py").write_text(
        '@app.get("/api/bootstrap")\n'
        "def bootstrap():\n    return {}\n\n"
        '@app.put("/api/extensions/{eid}/state")\n'
        "def state(eid: str):\n    return {}\n",
        encoding="utf-8",
    )
    (tmp_path / "static" / "index.html").write_text(
        '<!doctype html><link rel="stylesheet" href="/static/styles.css">'
        '<main id="story"><button id="send">Send</button></main>'
        '<script src="/static/js/app.js"></script>',
        encoding="utf-8",
    )
    (tmp_path / "static" / "js" / "app.js").write_text(
        "const S = {};\n"
        "function openChat() {}\n"
        "window.Sonder = {};\n"
        'document.getElementById("send");\n'
        'document.querySelector("#story");\n',
        encoding="utf-8",
    )
    (tmp_path / "static" / "styles.css").write_text(
        ':root { --surface: #111; }\n'
        'html[data-theme="carbon"] { --surface: #101820; }\n',
        encoding="utf-8",
    )
    (tmp_path / "language_packs" / "en" / "ui.json").write_text(
        json.dumps({"nav": {"play": "Play"}, "send": "Send"}),
        encoding="utf-8",
    )
    return tmp_path


def test_collect_inventory_finds_real_source_boundaries(ui_fixture: Path):
    from tools.ui_replacement_inventory import collect_inventory

    inventory = collect_inventory(ui_fixture)

    assert inventory["routes"] == [
        {"method": "GET", "path": "/api/bootstrap", "source": "web/app.py:1"},
        {
            "method": "PUT",
            "path": "/api/extensions/{eid}/state",
            "source": "web/app.py:5",
        },
    ]
    assert inventory["entries"] == [
        {
            "dom_ids": ["send", "story"],
            "path": "static/index.html",
            "scripts": ["/static/js/app.js"],
            "styles": ["/static/styles.css"],
        }
    ]
    assert inventory["browser_globals"] == [
        {"kind": "classic-const", "name": "S", "source": "static/js/app.js:1"},
        {"kind": "classic-function", "name": "openChat", "source": "static/js/app.js:2"},
        {"kind": "window", "name": "Sonder", "source": "static/js/app.js:3"},
    ]
    assert inventory["dom_references"] == [
        {"id": "send", "source": "static/js/app.js:4"},
        {"id": "story", "source": "static/js/app.js:5"},
    ]
    assert inventory["themes"] == ["carbon"]
    assert inventory["css_custom_properties"] == ["--surface"]
    assert inventory["ui_catalog_keys"] == ["nav.play", "send"]
    assert inventory["extension_routes"] == [
        {"method": "PUT", "path": "/api/extensions/{eid}/state", "source": "web/app.py:5"}
    ]


def test_write_artifacts_is_deterministic_and_capabilities_are_owned(
    ui_fixture: Path,
):
    from tools.ui_replacement_inventory import write_artifacts

    output = ui_fixture / "docs" / "design" / "sonder-ui-replacement"
    write_artifacts(
        ui_fixture,
        output,
        baseline_head="baseline-sha",
        candidate_head="candidate-sha",
    )
    first = {path.name: path.read_bytes() for path in output.rglob("*") if path.is_file()}
    write_artifacts(
        ui_fixture,
        output,
        baseline_head="baseline-sha",
        candidate_head="candidate-sha",
    )
    second = {path.name: path.read_bytes() for path in output.rglob("*") if path.is_file()}

    assert second == first
    inventory = json.loads((output / "baseline" / "source-inventory.json").read_text())
    assert inventory["baseline_head"] == "baseline-sha"
    assert inventory["candidate_head"] == "candidate-sha"

    ledger = (output / "CAPABILITY_LEDGER.md").read_text(encoding="utf-8")
    rows = [line for line in ledger.splitlines() if line.startswith("| `CAP-")]
    assert len(rows) >= 35
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[3].startswith("WP-")
        assert cells[4] in {"required", "presentation-only"}
        assert cells[5] in {"preserve", "adapt", "rebuild", "replace", "remove-at-cutover"}

