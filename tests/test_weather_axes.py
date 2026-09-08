"""Weather is a NAME the story owns plus AXES the engine owns (review A88).

The defect: `world/weather.py` was a closed Earth vocabulary -- five skies
crossed with five falls -- so a sandstorm, an ashfall and a rain of blood all
normalised to `sky: storm` with the particulate LOST, and the deterministic
drift then read `_SKY_FALL["storm"]` and rolled ordinary rain over them once
an in-story hour.

Measured over both bench copies before the change (24 stored weather records,
four drift windows each): the old drift invented a fall over a dry sky in 13
of 96 windows, and replaced the story's own declared fall with a different one
in 29 more. Every other answer on that corpus -- the composed sight and sound
words, per-room exposure, the ground ledger, the lightning verdict and the sun
light at every phase -- is byte-identical across the change; only the new axis
keys appear and `thundersnow` folds into `electrical`.

These pin the class rather than the corpus: that a fiction may have a weather
this engine has never heard of, and that everything downstream of it reads an
axis.
"""

from __future__ import annotations

from world.weather import (advance_weather, ground_after, has_lightning,
                           is_falling, normalize_weather, weather_for_room,
                           weather_words)


ASHFALL = {
    "sky": "an ash-choked pall", "precipitation": "ashfall",
    "precipitation_kind": "particulate", "intensity": "heavy",
    "cloud": "covered", "air": "hazy", "wind": "wind", "temperature": "hot",
}


def _scene(weather):
    return {
        "weather": weather,
        "rooms": {
            "yard": {"name": "Courtyard", "desc": "Flagstones, a well.",
                     "exposure": "open"},
            "cellar": {"name": "Wine Cellar", "desc": "Racks and cold stone.",
                       "exposure": "enclosed"},
        },
    }


class TestAFictionMayHaveItsOwnWeather:
    def test_the_name_survives_normalisation(self):
        out = normalize_weather(ASHFALL)
        assert out["sky"] == "an ash-choked pall"
        assert out["precipitation"] == "ashfall"
        assert out["precipitation_kind"] == "particulate"
        assert out["air"] == "hazy"

    def test_the_drift_carries_the_name_and_moves_only_the_amount(self):
        """The defect in one assertion. Twenty-four windows of drift, and the
        ash is still ash in every one of them."""
        seen = set()
        for hour in range(1, 25):
            after = advance_weather(ASHFALL, hour * 3600, seed="ash:1")
            assert after["precipitation"] == "ashfall", after
            assert after["precipitation_kind"] == "particulate", after
            seen.add(after["intensity"])
        # ...and the amount is what actually moves, so the sky is still alive.
        assert len(seen) > 1, seen

    def test_a_dry_sky_never_starts_dropping_something(self):
        """The other half: the drift has no table of weathers to pick from,
        so a story that declared a clear sky keeps one until it says
        otherwise."""
        dry = {"sky": "a sky of two suns", "precipitation": "none",
               "temperature": "hot"}
        for hour in range(1, 40):
            after = advance_weather(dry, hour * 3600, seed="two-suns")
            assert after["precipitation"] == "none", after
            assert not is_falling(after), after

    def test_the_engine_renames_only_its_own_words(self):
        """A sky wearing a word the engine minted may be kept in step with
        the axes the drift just moved; a story's own word is never rewritten.
        """
        mine = advance_weather({"sky": "overcast", "precipitation": "rain",
                                "intensity": "light"}, 3600 * 9, seed="k")
        assert mine["sky"] in ("clear", "fair", "overcast", "fog", "storm")
        theirs = advance_weather(ASHFALL, 3600 * 9, seed="k")
        assert theirs["sky"] == "an ash-choked pall"


class TestEverythingDownstreamReadsTheAxis:
    def test_footing_comes_off_the_kind_and_carries_the_name(self):
        scene = _scene(ASHFALL)
        state = {}
        seen = []
        for _ in range(7):
            state = ground_after(state, weather_for_room(scene, "yard"),
                                 "seasonal")
            seen.append(state["state"])
        assert seen[0] == "a dusting of ashfall"
        assert seen[-1] == "drifts of ashfall"
        # ...and the name rides the ledger, so a floor still reads while the
        # sky that made it has cleared.
        assert state["name"] == "ashfall"

    def test_a_fall_with_no_stated_kind_leaves_nothing_underfoot(self):
        """`other` is the honest answer for a fall a story named without
        saying what it does, and the honest consequence is silence rather
        than a guess at mud."""
        scene = _scene({"sky": "wrongness", "precipitation": "the fall",
                        "intensity": "heavy"})
        assert weather_for_room(scene, "yard")["precipitation_kind"] == "other"
        assert ground_after({}, weather_for_room(scene, "yard"),
                            "seasonal") == {}

    def test_lightning_is_an_axis_and_not_a_noun(self):
        lit = normalize_weather(dict(ASHFALL, electrical=True))
        assert has_lightning(lit)
        scoped = dict(lit, exposure="open", audible=True, falls_on_you=True)
        assert "thunder" in weather_words(scoped, channel="sound")

    def test_the_sight_words_carry_the_story_s_own_sky(self):
        scene = _scene(ASHFALL)
        words = weather_words(weather_for_room(scene, "yard"), "sight")
        assert "an ash-choked pall sky" in words
        assert "heavy ashfall" in words

    def test_a_covered_sky_dims_the_day_whatever_it_is_called(self):
        """`day_cycle.DIMMING_SKIES` listed three English words, so a story
        under an ash-choked pall got broad daylight."""
        from world.day_cycle import sun_light
        assert sun_light("midday", normalize_weather(ASHFALL)) == "dim"
        assert sun_light("midday", normalize_weather(
            {"sky": "a sky of two suns", "precipitation": "none"})) == "lit"

    def test_the_cellar_still_gets_none_of_it(self):
        scene = _scene(ASHFALL)
        scoped = weather_for_room(scene, "cellar")
        assert scoped["exposure"] == "enclosed"
        assert not scoped["falls_on_you"]
        assert not scoped["weather_visible"]


class TestEveryStoredStoryStillReads:
    """The ruling's own requirement: a stored Earth word maps to its axes
    once, at read. Verified across both bench copies (213 stored scene blobs,
    24 of them carrying weather) with every non-drift answer byte-identical;
    these are the four the corpus happened not to exercise."""

    def test_a_stored_storm_is_electrical_and_covered(self):
        out = normalize_weather({"sky": "storm", "precipitation": "rain",
                                 "intensity": "heavy"})
        assert out["electrical"] is True
        assert out["cloud"] == "covered"
        assert out["precipitation_kind"] == "liquid"

    def test_a_stored_fog_is_thick_air(self):
        out = normalize_weather({"sky": "fog", "precipitation": "none"})
        assert out["air"] == "thick"
        assert out["electrical"] is False

    def test_a_stored_blizzard_is_still_silent(self):
        out = normalize_weather({"sky": "storm", "precipitation": "snow",
                                 "intensity": "heavy"})
        assert out["electrical"] is False
        assert out["precipitation_kind"] == "frozen"

    def test_a_stored_thundersnow_flag_becomes_the_axis(self):
        out = normalize_weather({"sky": "storm", "precipitation": "snow",
                                 "intensity": "heavy", "thundersnow": True})
        assert out["electrical"] is True
        assert "thundersnow" not in out


def test_a_name_longer_than_the_limit_is_truncated_not_refused():
    """NAME_LIMIT is a cap and is named as one: a name reaches an image
    prompt, a sound query and a cache key. A story never loses its weather to
    a length -- it loses the tail of a sentence somebody put in a name."""
    from world.weather import NAME_LIMIT
    out = normalize_weather({"sky": "x" * (NAME_LIMIT + 40),
                             "precipitation": "none"})
    assert len(out["sky"]) == NAME_LIMIT
