"""Static validation for the build-free Sonder SVG icon family."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPRITE = ROOT / "static" / "assets" / "icons" / "sonder-icons.svg"


def test_icon_sprite_is_local_safe_and_inventoried():
    text = SPRITE.read_text(encoding="utf-8")
    assert "<script" not in text.lower()
    assert "http://" not in text.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert "https://" not in text
    assert "currentColor" in text
    inventory = (ROOT / "docs" / "design" / "sonder-ui-replacement" / "ICON_INVENTORY.md")
    assert inventory.is_file()


def test_every_icon_has_consistent_geometry_and_unique_name():
    root = ET.parse(SPRITE).getroot()
    symbols = root.findall("{http://www.w3.org/2000/svg}symbol")
    ids = [symbol.attrib.get("id", "") for symbol in symbols]
    assert len(ids) >= 50
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"icon-[a-z0-9-]+", icon_id) for icon_id in ids)
    assert all(symbol.attrib.get("viewBox") == "0 0 24 24" for symbol in symbols)


def test_icon_helper_is_explicit_and_accessible():
    text = (ROOT / "static" / "js" / "ui" / "icons.js").read_text(encoding="utf-8")
    assert "createIcon" in text
    assert "setIconButton" in text
    assert "aria-label" in text
    assert "aria-hidden" in text
    assert "querySelectorAll" not in text
    assert "MutationObserver" not in text

