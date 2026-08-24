"""Source contracts for WP-05 live-story state tools."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "static" / "js" / "ui-next" / "story-tools"
MODULES = ("shared.js", "cast.js", "conditions.js", "frames.js", "multiplayer.js")


def test_live_story_tools_are_native_release_coherent_modules():
    missing = [name for name in MODULES if not (TOOLS / name).is_file()]
    assert missing == []
    for name in MODULES:
        assert 'export const MODULE_RELEASE = "alpha98-ui9-ff279a1d1d7f";' in (TOOLS / name).read_text(
            encoding="utf-8"
        )

    family = (TOOLS.parent / "live-story-tools.js").read_text(encoding="utf-8")
    for name in MODULES[1:]:
        assert f'./story-tools/{name}?release=alpha98-ui9-ff279a1d1d7f' in family


def test_cast_uses_authoritative_membership_position_and_colour_routes():
    source = (TOOLS / "cast.js").read_text(encoding="utf-8")
    for contract in (
        "/api/chats/${chatId}",
        "/api/chats/${chatId}/positions",
        "/characters/${characterId}/position",
        "/characters/${characterId}/dialogue_color",
        '"DELETE"',
        '"POST"',
        "dialogue_colors",
    ):
        assert contract in source


def test_conditions_keep_disabled_empty_loading_and_unavailable_distinct():
    source = (TOOLS / "conditions.js").read_text(encoding="utf-8")
    assert "/api/chats/${chatId}/vitals" in source
    for state in ("loading", "disabled", "empty", "offline", "error", "ready"):
        assert f'"{state}"' in source
    assert 'setAttribute("role", "progressbar")' in source
    assert 'setAttribute("aria-valuenow"' in source
    assert "is_player" in source


def test_frames_and_multiplayer_use_guarded_server_authority():
    frames = (TOOLS / "frames.js").read_text(encoding="utf-8")
    multiplayer = (TOOLS / "multiplayer.js").read_text(encoding="utf-8")
    for contract in (
        "/api/chats/${chatId}/frames",
        "/api/chats/${chatId}/personas",
        "/personas/${personaId}/station",
        "services.storyTools.openFrame",
    ):
        assert contract in frames
    for contract in (
        "/api/chats/${chatId}/personas",
        "/api/chats/${chatId}/guest_invites",
        '"DELETE"',
        '"POST"',
        "invite.code",
    ):
        assert contract in multiplayer
    assert "localState" not in multiplayer
    assert "sessionStorage" not in multiplayer


def test_live_story_tools_avoid_legacy_and_unsafe_dom_bridges():
    paths = [TOOLS / name for name in MODULES]
    paths.append(TOOLS.parent / "live-story-tools.js")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "window.S",
        ".innerHTML",
        "setInterval(",
        "MutationObserver",
        ".click()",
        "prompt(",
        "confirm(",
        "insertAdjacentHTML",
    ):
        assert forbidden not in combined
