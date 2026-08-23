"""Static validation for the build-free Sonder SVG icon family."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPRITE = ROOT / "static" / "assets" / "icons" / "sonder-icons.svg"
FILLED_REPLACEMENT_ICONS = {
    "icon-settings",
    "icon-unlink",
    "icon-resize",
    "icon-theme",
    "icon-retry",
    "icon-offline",
    "icon-duplicate",
}


def test_icon_sprite_is_local_safe_and_inventoried():
    text = SPRITE.read_text(encoding="utf-8")
    assert "<script" not in text.lower()
    assert "http://" not in text.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert "https://" not in text
    assert "currentColor" in text
    inventory = (ROOT / "docs" / "design" / "sonder-ui-replacement" / "ICON_INVENTORY.md")
    assert inventory.is_file()


def test_every_icon_has_safe_square_geometry_and_unique_name():
    root = ET.parse(SPRITE).getroot()
    symbols = root.findall("{http://www.w3.org/2000/svg}symbol")
    ids = [symbol.attrib.get("id", "") for symbol in symbols]
    assert len(ids) >= 50
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"icon-[a-z0-9-]+", icon_id) for icon_id in ids)
    for symbol in symbols:
        view_box = symbol.attrib.get("viewBox", "").split()
        assert len(view_box) == 4, symbol.attrib.get("id")
        _, _, width, height = (float(value) for value in view_box)
        assert width > 0 and height > 0, symbol.attrib.get("id")
        assert width == height, symbol.attrib.get("id")


def test_icon_helper_is_explicit_and_accessible():
    text = (ROOT / "static" / "js" / "ui" / "icons.js").read_text(encoding="utf-8")
    assert "createIcon" in text
    assert "setIconButton" in text
    assert "aria-label" in text
    assert "aria-hidden" in text
    assert "querySelectorAll" not in text
    assert "MutationObserver" not in text


def test_filled_replacement_icons_do_not_inherit_the_outline_icon_stroke():
    root = ET.parse(SPRITE).getroot()
    symbols = {
        symbol.attrib.get("id", ""): symbol
        for symbol in root.findall("{http://www.w3.org/2000/svg}symbol")
    }
    assert {
        icon_id for icon_id in FILLED_REPLACEMENT_ICONS
        if symbols[icon_id].attrib.get("stroke") != "none"
    } == set()

