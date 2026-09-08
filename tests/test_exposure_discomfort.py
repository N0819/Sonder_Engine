"""The weather reaches the body as discomfort (review 2026-09-07 D20).

Comfort is the world's deterministic PLEASURE floor: a featherbed and a hearth
reach `resolve_hedonic` whether or not a model thought to mention them. Pain
had a world-side floor for injury and for bad air and nothing at all for the
sky, so a character bare-armed in freezing rain felt exactly what the one at
the hearth felt unless the model said so.

`world/exposure.py` is that floor, built on A88's axes: it reads what a body's
own room gets of the weather, what the body has bare, and how spent it is, and
it asserts nothing it was not told. Two rules it must keep are pinned here
because breaking either would be silent: it never reaches `charge`, and it is
capped at DISCOMFORT_CEILING (0.3, comfort's own ceiling) because it does NOT
habituate -- see the module docstring for why that is deferred rather than
missing.
"""

from __future__ import annotations

from mind import psychology_runtime
from world.exposure import DISCOMFORT_CEILING, discomfort_level

FREEZING_RAIN = {"sky": "storm", "precipitation": "rain", "intensity": "heavy",
                 "wind": "gale", "temperature": "freezing"}
#: A sky well short of the ceiling, so the comparative tests below measure a
#: difference rather than two numbers that both saturated.
COLD_DRIZZLE = {"sky": "overcast", "precipitation": "drizzle",
                "intensity": "light", "wind": "breeze", "temperature": "cold"}
_KEEP = object()


def _scene(weather=_KEEP, attire=None, rooms=None):
    return {
        "weather": dict(COLD_DRIZZLE) if weather is _KEEP else weather,
        "rooms": rooms or {
            "yard": {"name": "Courtyard", "desc": "Flagstones.",
                     "exposure": "open"},
            "porch": {"name": "Porch", "desc": "A covered step.",
                      "exposure": "sheltered"},
            "hall": {"name": "Great Hall", "desc": "Stone and fire.",
                     "exposure": "enclosed"},
        },
        "positions": {"Mira": "yard"},
        "attire": attire if attire is not None else {},
    }


def _bare(*regions):
    return {"Mira": {"regions": {r: {"garments": []} for r in regions}}}


def _dressed(*regions):
    return {"Mira": {"regions": {r: {"garments": ["a wool coat"]}
                                 for r in regions}}}


class TestWhatTheWeatherCosts:
    def test_a_bare_body_in_freezing_rain_feels_it(self):
        level, source = discomfort_level(_scene(FREEZING_RAIN, attire=_bare(
            "head", "torso", "arms", "hands", "waist", "groin", "legs",
            "feet")), "Mira")
        assert level > 0.0
        assert "freezing" in source and "rain" in source

    def test_and_the_same_body_at_the_hearth_does_not(self):
        """The whole point of the item, in one comparison."""
        scene = _scene(attire=_bare("torso", "arms"))
        scene["positions"]["Mira"] = "hall"
        assert discomfort_level(scene, "Mira") == (0.0, "")

    def test_cover_is_relief_and_not_immunity(self):
        naked = discomfort_level(_scene(attire=_bare(
            "head", "torso", "arms", "legs")), "Mira")[0]
        clad = discomfort_level(_scene(attire=_dressed(
            "head", "torso", "arms", "legs")), "Mira")[0]
        assert 0.0 < clad < naked

    def test_a_story_that_never_wrote_clothing_down_is_not_a_naked_story(self):
        """Rule 3. A body with no attire entry takes the fully clothed
        reading, because the failure direction that matters here is inventing
        pain the fiction never established."""
        unwritten = discomfort_level(_scene(attire={}), "Mira")[0]
        clad = discomfort_level(_scene(attire=_dressed(
            "head", "torso", "arms", "legs")), "Mira")[0]
        assert unwritten == clad

    def test_a_porch_is_half_of_it(self):
        scene = _scene(attire=_bare("torso", "arms"))
        yard = discomfort_level(scene, "Mira")[0]
        scene["positions"]["Mira"] = "porch"
        porch = discomfort_level(scene, "Mira")[0]
        assert 0.0 < porch < yard

    def test_a_spent_body_feels_it_more(self):
        scene = _scene(attire=_bare("torso", "arms"))
        rested = discomfort_level(scene, "Mira", {"stamina": 1.0})[0]
        spent = discomfort_level(scene, "Mira", {"stamina": 0.1})[0]
        assert spent > rested

    def test_mild_weather_costs_nothing_at_all(self):
        scene = _scene({"sky": "fair", "precipitation": "none",
                        "temperature": "mild", "wind": "breeze"},
                       attire=_bare("torso", "arms", "legs"))
        assert discomfort_level(scene, "Mira") == (0.0, "")

    def test_a_scene_with_no_weather_asserts_nothing(self):
        assert discomfort_level(_scene(weather=None), "Mira") == (0.0, "")


class TestItReadsTheAxisAndNeverTheName:
    def test_a_fall_the_engine_was_given_no_kind_for_is_not_a_soaking(self):
        """A88's rule, one layer down: `other` means the story named a fall
        and said nothing about what it does, so nothing about wetness is
        asserted from it. Only the temperature and the wind still count."""
        scene = _scene({"sky": "wrongness", "precipitation": "the fall",
                        "intensity": "heavy", "temperature": "mild",
                        "wind": "still"},
                       attire=_bare("torso", "arms", "legs"))
        assert discomfort_level(scene, "Mira") == (0.0, "")

    def test_a_particulate_fall_does_not_wet_a_body(self):
        ash = _scene({"sky": "an ash-choked pall", "precipitation": "ashfall",
                      "precipitation_kind": "particulate",
                      "intensity": "heavy", "temperature": "cold",
                      "wind": "still"},
                     attire=_bare("torso", "arms", "legs"))
        rain = _scene({"sky": "overcast", "precipitation": "rain",
                       "precipitation_kind": "liquid", "intensity": "heavy",
                       "temperature": "cold", "wind": "still"},
                      attire=_bare("torso", "arms", "legs"))
        assert 0.0 < discomfort_level(ash, "Mira")[0] \
            < discomfort_level(rain, "Mira")[0]

    def test_the_story_s_own_noun_reaches_the_character_s_state(self):
        scene = _scene({"sky": "a bruise of a sky",
                        "precipitation": "a slow fall of blood",
                        "precipitation_kind": "liquid", "intensity": "heavy",
                        "temperature": "cold"},
                       attire=_bare("torso", "arms", "legs"))
        assert "a slow fall of blood" in discomfort_level(scene, "Mira")[1]


class TestHowItReachesTheBody:
    def test_it_floors_the_pain_level_with_its_source(self):
        out = psychology_runtime.resolve_hedonic(
            {}, {}, {}, {}, elapsed_units=1,
            ambient_discomfort=0.3, discomfort_source="standing out in freezing")
        assert out["pain"] > 0.0
        assert out["source"] == "standing out in freezing"

    def test_a_grounded_appraisal_outranks_it_as_the_named_cause(self):
        out = psychology_runtime.resolve_hedonic(
            {}, {"somatic_impact": {"pain": 0.9, "why": "a knife"}}, {}, {},
            elapsed_units=1, ambient_discomfort=0.3,
            discomfort_source="standing out in freezing")
        assert out["source"] == "a knife"

    def test_charge_is_invariant_under_pure_ambient_discomfort(self):
        """The rule comfort keeps on the other side, and for the same reason:
        the weather is a resolved state a body is in, not an unresolved drive
        demanding release. A refactor folding it into `drive` would
        manufacture saturated bodies out of standing in the rain."""
        without = psychology_runtime.resolve_hedonic(
            {}, {}, {}, {}, elapsed_units=1)
        with_chill = psychology_runtime.resolve_hedonic(
            {}, {}, {}, {}, elapsed_units=1, ambient_discomfort=0.3,
            discomfort_source="standing out in freezing")
        assert with_chill["charge"] == without["charge"]

    def test_it_passes_through_pain_sensitivity(self):
        stoic = psychology_runtime.resolve_hedonic(
            {}, {}, {"pain_sensitivity": 0.0}, {}, elapsed_units=1,
            ambient_discomfort=0.3, discomfort_source="out in it")
        raw = psychology_runtime.resolve_hedonic(
            {}, {}, {"pain_sensitivity": 1.0}, {}, elapsed_units=1,
            ambient_discomfort=0.3, discomfort_source="out in it")
        assert raw["pain"] > stoic["pain"] > 0.0

    def test_a_sourceless_number_does_nothing(self):
        """Same discipline comfort keeps: an unattributed floor is a number
        nobody can explain in the character's own state."""
        out = psychology_runtime.resolve_hedonic(
            {}, {}, {}, {}, elapsed_units=1, ambient_discomfort=0.3,
            discomfort_source="")
        assert out["pain"] == 0.0

    def test_the_ceiling_holds_however_bad_the_sky_gets(self):
        worst = discomfort_level(_scene(attire=_bare(
            "head", "torso", "arms", "hands", "waist", "groin", "legs",
            "feet")), "Mira", {"stamina": 0.0})[0]
        assert worst <= DISCOMFORT_CEILING
        out = psychology_runtime.resolve_hedonic(
            {}, {}, {"pain_sensitivity": 1.0}, {}, elapsed_units=1,
            ambient_discomfort=99.0, discomfort_source="out in it")
        assert out["pain"] <= DISCOMFORT_CEILING

    def test_it_never_mutates_the_scene(self):
        import copy
        scene = _scene(attire=_bare("torso", "arms"))
        before = copy.deepcopy(scene)
        discomfort_level(scene, "Mira")
        assert scene == before
