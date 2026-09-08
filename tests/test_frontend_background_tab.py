"""What the reading view must still get right while its tab is hidden.

A75 and A76 (review 2026-09-07). The two effect layers -- the ambience bed and
the weather overlay -- both keep state that a hidden tab changes the rules for,
and both got it wrong in the same shape: a clock that stops while the thing it
was driving does not.

`requestAnimationFrame` does not fire in a hidden tab. Audio does not stop
there, and neither does the `timeupdate` that STARTS a loop handover, so a
crossfade begun while hidden froze half-done and completed on tab return by
promoting an element that had already played to its end -- a layer silent until
the room changed. Timers, the other way round, keep running while hidden
(throttled, not stopped), so a lightning flash scheduled by one fired its
thunder at a tab nobody was looking at, and a thunderclap owed to a flash
already drawn survived the weather being torn down entirely.

The frontend has no bundler and the browser tier is optional, so what this tier
can hold is the shape of the rule in the source. What a browser tier would have
to check is written into each test.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AMBIENCE = (ROOT / "static/js/ambience.js").read_text(encoding="utf-8")
WEATHER = (ROOT / "static/js/weather-fx.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def test_an_ambience_fade_runs_on_a_clock_a_hidden_tab_still_turns():
    """A75. Both fades -- the whole-mix crossfade and the per-layer loop seam
    -- ride one clock, and it is not the frame clock.

    A browser tier would drive it: start a bed, hide the tab across a loop
    point (or fake `document.hidden` and stop dispatching frames), and assert
    that when the tab returns the layer is playing and not paused at zero.
    """
    code = "\n".join(line for line in AMBIENCE.splitlines()
                     if not line.lstrip().startswith("//"))
    assert "requestAnimationFrame" not in code

    clock = _between(AMBIENCE, "function ambienceFadeClock(step)",
                     "// Whatever a handover missed")
    assert "setTimeout(tick, AMB_FADE_TICK_MS)" in clock

    for fade in ("function ambienceFadeMix(incoming, outgoing)",
                 "function crossLoop(entry)"):
        block = _between(AMBIENCE, fade, "\n}\n")
        assert "ambienceFadeClock(now => {" in block, fade
        assert "return true;" in block, fade          # keep going
        assert "return false;" in block, fade         # and a real ending


def test_a_finished_handover_leaves_the_layer_sounding():
    """A75, the self-heal half. A promoted element that ran out underneath a
    slow handover is exactly the silence the seam exists to prevent, and the
    `ended` listener cannot cover it: that listener only fires for the element
    that is currently leading.
    """
    heal = _between(AMBIENCE, "function ambienceEnsureSounding(entry)",
                    "// Crossfades a whole MIX")
    assert "if (!audio || (!audio.paused && !audio.ended)) return;" in heal
    assert "audio.volume = ambienceLevel(entry.index);" in heal
    assert "audio.play()" in heal

    swap = _between(AMBIENCE, "function crossLoop(entry)", "\n}\n")
    assert swap.index("entry.crossing = false;") < swap.index("ambienceEnsureSounding(entry);")
    mix = _between(AMBIENCE, "function ambienceFadeMix(incoming, outgoing)", "\n}\n")
    assert "for (const entry of incoming) ambienceEnsureSounding(entry);" in mix


def test_weather_effects_are_re_armed_only_through_their_single_gate():
    """A76. Returning to a tab is not news about the effects level, reduced
    motion, or whether the browser can draw any of this -- and all three are
    asked in `weatherFxApply`. Re-arming the lightning below it meant effects
    switched off while the tab was hidden came back to a flashing, thundering
    sky nothing else on screen was drawing.

    A browser tier would drive it: set effects to off, hide and re-show the
    tab, and assert no `.wfx-flash` is added and no thunder oneshot is asked
    for.
    """
    handler = _between(WEATHER, 'document.addEventListener("visibilitychange"',
                       "// Re-apply when the effects level changes")
    assert "weatherFxApply(WFX.weather);" in handler
    assert "weatherFxScheduleFlash" not in handler
    assert "weatherFxSetPlayState();" in handler

    # And nothing schedules a flash for a tab that cannot show one.
    schedule = _between(WEATHER, "function weatherFxScheduleFlash(storm)",
                        "function weatherFxFlash()")
    assert "if (!storm || document.hidden) return;" in schedule


def test_layers_built_while_hidden_are_born_paused():
    """A76. The pause used to be applied only to the layers that existed when
    the tab was hidden, so weather arriving for a new room while hidden built
    three infinite composited animations -- the exact cost this file exists to
    avoid. One function answers "should these be running", and both the build
    and the visibility handler ask it.
    """
    assert WEATHER.count("function weatherFxSetPlayState()") == 1
    state = _between(WEATHER, "function weatherFxSetPlayState()",
                     "// --- lifecycle")
    assert 'const state = document.hidden ? "paused" : "running";' in state
    assert 'for (const inner of layer.querySelectorAll(".wfx-layer"))' in state

    build = _between(WEATHER, "function weatherFxBuild(kind, weather)",
                     "function weatherFxClearLayers()")
    assert "weatherFxSetPlayState();" in build


def test_every_weather_timer_is_tracked_so_a_teardown_takes_it_with_it():
    """A76. Thunder is scheduled up to six and a half seconds after the flash
    that earns it, and a reader can walk indoors, turn effects off or leave the
    story inside that gap. Nothing but a tracked timer can be cancelled.

    A browser tier would drive it: force a flash, call `weatherFxApply(null)`
    inside the thunder delay, and assert no oneshot is ever requested.
    """
    # `weatherFxLater` is the only place a timeout is started, and
    # `weatherFxCancel`/`weatherFxClearTimers` the only places one is cleared.
    body = "\n".join(
        line for line in WEATHER.splitlines()
        if not line.lstrip().startswith("//")
    )
    assert body.count("setTimeout(") == 1
    assert body.count("clearTimeout(") == 2

    stop = _between(WEATHER, "function weatherFxStop()", "// The engine's own answer")
    assert "weatherFxClearTimers();" in stop

    thunder = _between(WEATHER, "function weatherFxThunder()",
                       "// Called by backdrops.js")
    assert "weatherFxLater(" in thunder


def test_a_stop_leaves_no_strike_in_the_document():
    """A76, the cost of tracking the bolt timer. Its callback is not a
    follow-on effect, it is the strike's TEARDOWN -- `weatherFxBolt` writes an
    SVG into `#weather-bolt` and arms an 800 ms timer to take it out again. A
    stop landing inside that window now cancels the timer, so cancelling
    without doing its work would leave the SVG in the document forever: the
    exact cost the comment above the timer names, and worse than the untracked
    timer it replaced, which at least still fired.

    `#weather-bolt` is a body child of its own, not inside `WFX.host`, so
    `weatherFxClearLayers` does not reach it.

    A browser tier would drive it: force a flash with a bolt, call
    `weatherFxApply(null)` within 800 ms, and assert `#weather-bolt` is empty
    and carries no `flash` class.
    """
    # One teardown, reachable from the stop path: stop -> clearTimers ->
    # clearBolt, and the timer runs the same function rather than a copy.
    stop = _between(WEATHER, "function weatherFxStop()", "// The engine's own answer")
    assert "weatherFxClearTimers();" in stop

    clear = _between(WEATHER, "function weatherFxClearTimers()",
                     "// Marks per tile")
    assert "WFX.boltTimer = null;" in clear
    assert "weatherFxClearBolt();" in clear

    teardown = _between(WEATHER, "function weatherFxClearBolt()",
                        "// Marks per tile")
    assert "if (!WFX.boltEl) return;" in teardown
    assert 'WFX.boltEl.classList.remove("flash");' in teardown
    assert 'WFX.boltEl.innerHTML = "";' in teardown

    bolt = _between(WEATHER, "function weatherFxBolt()", "// Thunder follows the flash")
    assert "weatherFxLater(weatherFxClearBolt, 800)" in bolt
    # The SVG is written in exactly one place, and emptied in exactly one, so
    # the teardown covers every strike there can be.
    assert WEATHER.count("WFX.boltEl.innerHTML =\n") == 1
    assert WEATHER.count('WFX.boltEl.innerHTML = "";') == 1
