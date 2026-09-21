"""The weather reaches the minds standing in it, and a canopy is cover.

TWO THINGS, ONE CHANGE. Measured 2026-09-20:

`composer.py` contained the word "weather" zero times, `perception.py` once in
a comment, and `agents/character.py` and `agents/common.py` not at all. The
scene holds `{sky, precipitation, intensity, wind, temperature}` and
`world.weather.weather_for_room` had already reduced it per room and per
channel -- `weather_visible`, `visible_reach`, `falls_on_you`, `wind_reaches`,
`sky_visible` -- for the Director, the light field, the noise floor and the
image overlay. No mind read one of them. A character standing in a freezing
thundersnow gale was told that the room was dim and that it was loud.

And exposure was a property of the ROOM alone, so a market square is `open` and
every body in it stands in the rain, including the one under the stall canopy
(the owner's point: "we should have room for shade structures in open spaces").
The finer truth the scene already held is the STATION -- a body stands AT an
anchor, and some anchors are cover.

NO MODEL ANYWHERE IN THIS (the owner's ruling): a model declares the weather
and declares a structure when it is minted. Everything after that is
arithmetic over the scene.
"""

import pytest

from agents import composer, perception
from world.weather import anchor_exposure, exposure_at, weather_for_room


STORM = {"sky": "storm", "precipitation": "snow", "intensity": "heavy",
         "wind": "gale", "temperature": "freezing"}


def _square(**over):
    """An open market square: a canopied stall, and a bare well head."""
    scene = {
        "weather": dict(STORM),
        "rooms": {"square": {
            "name": "Market Square",
            "desc": "The open cobbled hub, traded on every third morning.",
            "adjacent": [],
            "anchors": {
                "stall": {"desc": "a striped stall canopy"},
                "well": {"desc": "a stone well head"},
            },
        }},
        "positions": {"Sal": "square", "Emory": "square"},
        "stations": {"Sal": {"at": "stall"}, "Emory": {"at": "well"}},
        "entities": {}, "contained": {}, "contacts": [],
    }
    scene.update(over)
    return scene


def _said(percepts, channel=None):
    return " ".join(
        p.data.get("desc") or p.data.get("clause") or ""
        for p in percepts if channel is None or p.channel == channel)


def _for(scene, who, room="square"):
    return composer.weather_percepts(weather_for_room(scene, room, who))


class TestAShadeStructureIsCover:
    """`open` -> `sheltered` at the station, and nothing else moves."""

    def test_an_anchor_that_covers_says_so(self):
        assert anchor_exposure({"desc": "a striped stall canopy"}) == "sheltered"
        assert anchor_exposure({"desc": "a stone well head"}) == ""
        assert anchor_exposure(None) == ""

    def test_an_authored_exposure_outranks_the_words(self):
        """The rung order the room already uses, for the same reason: the words
        are a fallback for scenes that have no field, never an override of one."""
        assert anchor_exposure({"exposure": "enclosed",
                                "desc": "a stone well head"}) == "enclosed"
        assert anchor_exposure({"exposure": "open",
                                "desc": "a striped stall canopy"}) == "open"

    def test_two_bodies_in_one_square_get_different_skies(self):
        scene = _square()
        assert exposure_at(scene, "square") == "open"
        assert exposure_at(scene, "square", "Sal") == "sheltered"
        assert exposure_at(scene, "square", "Emory") == "open"

    def test_cover_subtracts_and_never_adds(self):
        """A structure standing in a place is shade, not a building: it may put
        something between a body and the sky and may do nothing else. It cannot
        open a cellar, and it cannot take a body already under a portico and
        call it indoors."""
        cellar = _square()
        cellar["rooms"]["square"]["exposure"] = "enclosed"
        assert exposure_at(cellar, "square", "Sal") == "enclosed"
        sheltered = _square()
        sheltered["rooms"]["square"]["exposure"] = "sheltered"
        assert exposure_at(sheltered, "square", "Sal") == "sheltered"
        # An anchor declaring `enclosed` still only shelters: a thing you can
        # walk INSIDE of is a room, with its own exposure.
        deep = _square()
        deep["rooms"]["square"]["anchors"]["stall"] = {"exposure": "enclosed"}
        assert exposure_at(deep, "square", "Sal") == "sheltered"

    def test_no_subject_is_still_the_room_s_question(self):
        """Every existing caller asks about a room and must get what it always
        got, or this is a behaviour change to the light field and the overlay."""
        scene = _square()
        for who in ("", None, "Nobody"):
            assert exposure_at(scene, "square", who) == "open"


class TestTheSkyReachesTheBody:
    def test_standing_in_it_you_are_told_it_is_snowing(self):
        said = _said(_for(_square(), "Emory"))
        assert "snow" in said.lower()

    def test_and_what_it_is_doing_to_you(self):
        """Sight and skin, separately, because they fail separately."""
        percepts = _for(_square(), "Emory")
        skin = _said(percepts, "touch").lower()
        assert "landing on you" in skin
        assert "gale" in skin
        assert "freezing" in skin

    def test_under_the_canopy_the_weather_is_beyond_your_cover(self):
        """The seam's own reading: standing out of it and watching it fall is
        what sheltering IS. So the snow is still seen and no longer lands."""
        percepts = _for(_square(), "Sal")
        sight = _said(percepts, "sight").lower()
        skin = _said(percepts, "touch").lower()
        assert "snow" in sight and "beyond" in sight
        assert "landing on you" not in skin
        # A canopy is not a wall: the wind and the cold still reach.
        assert "gale" in skin and "freezing" in skin

    def test_a_cellar_is_told_nothing(self):
        scene = _square()
        scene["rooms"]["square"]["exposure"] = "enclosed"
        assert _for(scene, "Emory") == []

    def test_a_clear_still_sky_is_not_an_event(self):
        """Cloud alone is a colour, not something happening -- the axis
        `weather_for_room` already draws. Nothing falling, nothing electrical
        and air you can see through says nothing to sight."""
        scene = _square(weather={"sky": "clear", "precipitation": "none",
                                 "intensity": "none", "wind": "still",
                                 "temperature": "mild"})
        assert _said(_for(scene, "Emory"), "sight") == ""

    def test_hearing_is_not_this_seam_s(self):
        """`spatial_sound_field` already folds rain and wind into the
        soundscape. One fact with two voices can only disagree with itself."""
        assert all(p.channel != "hearing" for p in _for(_square(), "Emory"))

    def test_no_number_reaches_the_page(self):
        """An intensity word, a `visible_reach` fraction and a `gain` are the
        engine's bookkeeping. A bystander has access to none of them."""
        said = _said(_for(_square(), "Sal")) + _said(_for(_square(), "Emory"))
        assert not any(ch.isdigit() for ch in said), said

    def test_the_marked_intensities_are_said_and_the_default_is_not(self):
        """`normalize_weather` returns `intensity: "moderate"` for a
        precipitation nobody graded, so rendering that word states a thing no
        author said. Light and heavy are marked, and are what a body remarks
        on."""
        def sight(how):
            scene = _square(weather=dict(STORM, intensity=how))
            return _said(_for(scene, "Emory"), "sight").lower()
        assert "light snow" in sight("light")
        assert "heavy snow" in sight("heavy")
        for unmarked in ("moderate", ""):
            said = sight(unmarked)
            assert "snow" in said and "moderate" not in said, unmarked
        # `intensity: "none"` is not an unmarked grade, it is the absence of
        # precipitation -- `normalize_weather`'s own reading -- so there is
        # nothing falling for sight to name.
        assert "snow" not in sight("none")

    def test_the_sky_takes_an_article_that_agrees_with_every_name(self):
        """`sky` is authored free text, so a template carrying "a {sky}" reads
        "a overcast sky" on the commonest value in the corpus. The definite
        article agrees with all of them."""
        for name in ("overcast", "storm", "fair", "iron-grey"):
            said = _said(_for(_square(weather=dict(STORM, sky=name)), "Emory"),
                         "sight").lower()
            assert f"the {name} sky" in said, name

    def test_a_held_sky_is_furniture_and_a_turning_one_is_news(self):
        """The dedupe contract this whole `ambient` family states: keyed on the
        state, never on the sentence composed from it."""
        first = _for(_square(), "Emory")[0]
        assert first.dedupe_key == _for(_square(), "Emory")[0].dedupe_key
        cleared = _square(weather=dict(STORM, precipitation="rain"))
        assert _for(cleared, "Emory")[0].dedupe_key != first.dedupe_key


class TestItIsWiredAndSpeaksBothLanguages:
    def test_perception_delivers_it(self):
        """A producer nothing calls is the defect this replaces, one layer
        along."""
        import inspect
        source = inspect.getsource(perception)
        assert "weather_percepts" in source
        assert "weather_for_room(sc, room, name)" in source

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_both_packs_can_say_it(self, language):
        from language_runtime import installed_language_packs
        templates = installed_language_packs()[language].card(
            "compositor")["templates"]
        for key in ("weather_overhead", "weather_overhead_plain",
                    "weather_beyond", "weather_on_you", "weather_wind",
                    "weather_air"):
            assert templates[key], (language, key)
