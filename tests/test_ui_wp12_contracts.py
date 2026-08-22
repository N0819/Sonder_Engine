from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_curated_theme_files_are_semantic_and_genre_neutral():
    theme_root = ROOT / "static" / "css" / "ui" / "themes"
    for theme in ("carbon-signal", "ash-brass", "midnight-ink", "parchment-night"):
        source = (theme_root / f"{theme}.css").read_text(encoding="utf-8")
        assert f'data-theme="{theme}"' in source or theme == "carbon-signal"
        assert "--ui-color-canvas:" in source
        assert "url(" not in source


def test_reference_extensions_cover_v1_and_v2_without_private_host_helpers():
    cohesion = json.loads((ROOT / "extensions" / "cohesion-demo" / "manifest.json").read_text(encoding="utf-8"))
    overlay = json.loads((ROOT / "extensions" / "overlay-demo" / "manifest.json").read_text(encoding="utf-8"))
    campaign = json.loads((ROOT / "extensions" / "campaign-demo" / "manifest.json").read_text(encoding="utf-8"))
    assert cohesion["ext_api"] == 1
    assert overlay["ext_api"] == 1 and overlay["capabilities"]["ui"]["api"] == 2
    assert campaign["ext_api"] == 1 and campaign["capabilities"]["ui"]["api"] == 2

    overlay_entry = (ROOT / "extensions" / "overlay-demo" / "ui" / "index.js").read_text(encoding="utf-8")
    campaign_entry = (ROOT / "extensions" / "campaign-demo" / "ui" / "index.js").read_text(encoding="utf-8")
    assert "registerDestination" in overlay_entry
    assert "registerDestination" in campaign_entry
    assert "registerView" not in overlay_entry + campaign_entry
    assert "registerTopBarButton" not in overlay_entry + campaign_entry

    cohesion_panel = (ROOT / "extensions" / "cohesion-demo" / "ui" / "panel.js").read_text(encoding="utf-8")
    assert "window.el" not in cohesion_panel
    assert "window.txt" not in cohesion_panel


def test_reference_extension_css_uses_owned_prefixes_and_replacement_tokens():
    paths = [
        ROOT / "extensions" / "cohesion-demo" / "ui" / "panel.css",
        ROOT / "extensions" / "overlay-demo" / "ui" / "overlay.css",
        ROOT / "extensions" / "campaign-demo" / "ui" / "campaign.css",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for legacy in ("var(--bg", "var(--fg", "var(--bd", "var(--acc", "var(--card"):
        assert legacy not in combined
    assert "var(--ui-color-" in combined


def test_v2_renderable_slots_have_destination_specific_consumers():
    host = (ROOT / "static" / "js" / "ui-next" / "extension-host.js").read_text(encoding="utf-8")
    for kind, destination in (
        ("play-tool", "play"),
        ("library-type", "library"),
        ("addon-settings", "settings"),
        ("destination", "settings"),
    ):
        assert f'"{kind}": "{destination}"' in host or f'{kind}: "{destination}"' in host
