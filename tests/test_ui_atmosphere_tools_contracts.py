"""Source contracts for WP-05 Play atmosphere and media controls."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"
TOOLS = RUNTIME / "story-tools"


def test_atmosphere_modules_are_release_coherent_and_runtime_owned():
    modules = (
        RUNTIME / "atmosphere-runtime.js",
        TOOLS / "backdrops.js",
        TOOLS / "ambience.js",
    )
    assert [path.name for path in modules if not path.is_file()] == []
    for path in modules:
        assert 'export const MODULE_RELEASE = "alpha98-ui6-ff8a9b712a2d";' in path.read_text(
            encoding="utf-8"
        )
    bootstrap = (RUNTIME / "bootstrap.js").read_text(encoding="utf-8")
    assert '"./atmosphere-runtime.js?release=alpha98-ui6-ff8a9b712a2d"' in bootstrap
    assert "createAtmosphereRuntime" in bootstrap


def test_backdrops_use_current_turn_contract_without_idle_polling():
    source = (TOOLS / "backdrops.js").read_text(encoding="utf-8")
    for contract in (
        "services.atmosphere.loadBackdrop",
        '"GET"',
        '"POST"',
        "Check status",
        "Generate backdrop",
        'request("POST", true)',
    ):
        assert contract in source
    assert "setInterval(" not in source
    assert "setTimeout(" not in source


def test_ambience_uses_current_resolve_pin_oneshot_and_media_contracts():
    source = (TOOLS / "ambience.js").read_text(encoding="utf-8")
    for contract in (
        "services.atmosphere.loadAmbience",
        "/api/chats/${chatId}/ambience/pins",
        "/api/chats/${chatId}/ambience/pin",
        "/api/chats/${chatId}/ambience/oneshot/thunder",
        "services.atmosphere.setMuted",
        "services.atmosphere.setVolume",
        "services.atmosphere.setChime",
        "services.atmosphere.unlock",
    ):
        assert contract in source
    assert "setInterval(" not in source
    assert "setTimeout(" not in source


def test_atmosphere_runtime_owns_visibility_audio_tokens_and_completion_chime():
    source = (RUNTIME / "atmosphere-runtime.js").read_text(encoding="utf-8")
    for contract in (
        "visibilitychange",
        "documentRef.hidden",
        "payload?.token",
        "new target.Audio",
        "pause()",
        "composer.status",
        'previousStatus === "running"',
        "completionChime",
        "localState.setRecord",
        "/api/turns/${turnId}/${kind}",
    ):
        assert contract in source
    for forbidden in (
        "setInterval(",
        "MutationObserver",
        "window.S",
        ".innerHTML",
        ".click()",
    ):
        assert forbidden not in source


def test_play_atmosphere_is_a_non_reflowing_effects_aware_stage():
    view = (RUNTIME / "play-view.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "ui" / "play.css").read_text(
        encoding="utf-8"
    )
    for contract in (
        "data-play-atmosphere",
        "data-play-backdrop",
        "data-play-weather",
        "state.atmosphere",
        "ui-play__audio-cluster",
        "services.atmosphere.setMuted",
        "services.atmosphere.setVolume",
    ):
        assert contract in view
    assert "position: absolute" in css
    assert ".ui-play__atmosphere" in css
    assert ':root[data-effects="off"]' in css
    assert "prefers-reduced-motion: reduce" in css
    assert "pointer-events: none" in css


def test_atmosphere_family_has_no_classic_or_automatic_polling_bridge():
    paths = (
        RUNTIME / "atmosphere-runtime.js",
        TOOLS / "backdrops.js",
        TOOLS / "ambience.js",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "window.S ",
        "window.S=",
        "clickLegacy",
        "setInterval(",
        "MutationObserver",
        "prompt(",
        "confirm(",
    ):
        assert forbidden not in combined
