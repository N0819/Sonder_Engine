"""Executable integrity checks for the UI replacement control plane.

The break these catch is a requirement family or row disappearing during
import/decomposition, especially a family containing digits such as A11Y.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = (
    ROOT
    / "docs"
    / "design"
    / "sonder-ui-replacement"
    / "REQUIREMENTS_TRACEABILITY.md"
)
ROW = re.compile(
    r"^\| `(?P<id>[A-Z][A-Z0-9]+-\d{2})` \|"
    r" (?P<requirement>.*?) \|"
    r" (?P<surfaces>.*?) \|"
    r" (?P<owners>.*?) \|"
    r" (?P<gate>.*?) \|"
    r" (?P<disposition>.*?) \|"
    r" (?P<evidence>.*?) \|"
    r" (?P<status>.*?) \|$"
)
EXPECTED_FAMILIES = {
    "A11Y": 14,
    "ARCH": 14,
    "AUTH": 6,
    "EXT": 7,
    "GOV": 10,
    "IA": 10,
    "ICON": 10,
    "LIB": 16,
    "ONB": 8,
    "PLAY": 16,
    "RESP": 12,
    "SAVE": 8,
    "SET": 14,
    "THEME": 13,
    "VER": 12,
}


def _rows() -> list[dict[str, str]]:
    text = MATRIX.read_text(encoding="utf-8")
    return [match.groupdict() for line in text.splitlines() if (match := ROW.match(line))]


def test_every_reference_requirement_survives_import_with_an_owner():
    rows = _rows()
    ids = [row["id"] for row in rows]
    assert len(ids) == 170
    assert len(set(ids)) == 170

    families: dict[str, int] = {}
    for requirement_id in ids:
        family = requirement_id.rsplit("-", 1)[0]
        families[family] = families.get(family, 0) + 1
    assert families == EXPECTED_FAMILIES

    for row in rows:
        owners = re.findall(r"WP-(\d{2})", row["owners"])
        assert owners, f"{row['id']} has no work-package owner"
        assert all(0 <= int(owner) <= 14 for owner in owners), row
        assert re.fullmatch(r"G[0-8](?:, G[0-8])*", row["gate"]), row
        assert row["status"] in {"open", "closed"}, row


def test_arch_12_records_the_approved_no_global_bridge_amendment():
    arch_12 = next(row for row in _rows() if row["id"] == "ARCH-12")
    assert "No single general-purpose compatibility bridge" in arch_12["requirement"]
    assert arch_12["disposition"] == "amended"
    assert arch_12["status"] == "closed"


def test_only_qualified_program_gates_close_current_requirements():
    rows = _rows()
    closed = {row["id"] for row in rows if row["status"] == "closed"}
    g1_icon_requirements = {f"ICON-{number:02d}" for number in range(1, 11)}
    g2_shell_requirements = {
        "IA-01",
        "IA-02",
        "IA-03",
        "IA-04",
        "IA-05",
        "IA-07",
        "IA-09",
        *(f"ARCH-{number:02d}" for number in range(1, 10)),
        "ARCH-14",
    }
    wp04_play_core_requirements = {
        "PLAY-01",
        "PLAY-02",
        "PLAY-03",
        "PLAY-05",
        "PLAY-06",
        "PLAY-11",
        "PLAY-12",
        "PLAY-14",
        "PLAY-16",
    }
    wp05_story_tools_requirements = {
        "PLAY-04",
        "PLAY-07",
        "PLAY-08",
        "PLAY-09",
        "PLAY-10",
        "PLAY-13",
        "PLAY-15",
    }
    qualified = {
        "GOV-02",
        "GOV-03",
        "GOV-04",
        "ARCH-12",
    } | (
        g1_icon_requirements
        | g2_shell_requirements
        | wp04_play_core_requirements
        | wp05_story_tools_requirements
    )
    assert closed <= qualified
