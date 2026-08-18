"""Scene weather — one sky, per-room exposure, and deterministic drift.

Before this module `scene["weather"]` was read by two features and written by
nothing. These tests pin the three properties that make the field real rather
than decorative:

  * ONE sky for the scene, and how much of it a room gets is a property of the
    ROOM. Two rooms under the same sky must never disagree about the weather;
    they may disagree entirely about how much of it reaches them.
  * an unrecognised room gets NO weather. The exposure fallback is a keyword
    pass over prose, so it is wrong sometimes by construction -- it has to be
    wrong in the direction of a dry cellar, never a rainy one.
  * drift is deterministic. The same chat at the same elapsed time has the same
    sky in a fresh process, after a restart, and on a rerolled turn.
"""

from __future__ import annotations

import pytest

from world.weather import (advance_weather, normalize_weather, room_exposure,
                     weather_depth, weather_for_room, weather_words)


def _scene(weather=None, rooms=None):
    return {
        "weather": weather,
        "rooms": rooms or {
            "yard": {"name": "Courtyard", "desc": "Flagstones, a well."},
            "cellar": {"name": "Wine Cellar", "desc": "Racks and cold stone."},
            "porch": {"name": "Porch", "desc": "A covered step by the door."},
            "odd": {"name": "Zzyx", "desc": "Indeterminate."},
        },
    }


# --- vocabulary ------------------------------------------------------------

def test_unknown_terms_never_reach_the_scene():
    """Model output lands here, and an unrecognised sky would travel on into a
    cache key, an image prompt and a sound query as a word nothing can act
    on."""
    out = normalize_weather({"sky": "apocalyptic", "precipitation": "frogs",
                             "wind": "unquiet", "temperature": "spicy"})
    assert out["sky"] == "fair"
    assert out["precipitation"] == "none"
    assert out["wind"] == "still"
    assert out["temperature"] == "mild"
    # And with a sky to keep, an unreadable word keeps it rather than clearing
    # it: a term this vocabulary cannot read is not evidence of fair weather.
    storm = {"sky": "storm", "precipitation": "rain", "intensity": "heavy",
             "wind": "gale", "temperature": "cold"}
    assert normalize_weather({"sky": "apocalyptic"}, storm) == \
        dict(storm, thundersnow=False)


def test_a_bare_string_is_accepted():
    """Which is what a model hands you about a third of the time."""
    out = normalize_weather("heavy rain, gale, cold")
    assert out["precipitation"] == "rain"
    assert out["intensity"] == "heavy"
    assert out["wind"] == "gale"
    assert out["temperature"] == "cold"


def test_half_written_states_are_reconciled():
    # Falling water with no strength...
    assert normalize_weather({"precipitation": "rain"})["intensity"] == "moderate"
    # ...and a strength with nothing falling.
    assert normalize_weather({"intensity": "heavy"})["intensity"] == "none"


def test_nothing_in_means_nothing_out():
    assert normalize_weather(None) == {}
    assert normalize_weather({}) == {}
    assert weather_for_room(_scene(), "yard") == {}


# --- exposure --------------------------------------------------------------

def test_authored_exposure_beats_the_keyword_fallback():
    scene = _scene(rooms={"hall": {"name": "Great Hall", "desc": "Open to the sky.",
                                   "exposure": "enclosed"}})
    assert room_exposure(scene, "hall") == "enclosed"


def test_exposure_is_derived_when_unauthored():
    scene = _scene()
    assert room_exposure(scene, "yard") == "open"
    assert room_exposure(scene, "cellar") == "enclosed"
    assert room_exposure(scene, "porch") == "sheltered"


def test_an_unrecognised_room_is_treated_as_indoors():
    """The fallback must be wrong in the direction of a dry cellar."""
    assert room_exposure(_scene(), "odd") == "enclosed"
    assert room_exposure(_scene(), "nonexistent") == "enclosed"


# --- one sky, many rooms ---------------------------------------------------

def test_one_sky_reaches_rooms_differently():
    scene = _scene({"sky": "storm", "precipitation": "rain", "intensity": "heavy"})
    yard = weather_for_room(scene, "yard")
    cellar = weather_for_room(scene, "cellar")
    porch = weather_for_room(scene, "porch")

    # Same weather...
    assert yard["sky"] == cellar["sky"] == porch["sky"] == "storm"
    # ...different amounts of it.
    assert yard["sky_visible"] and not cellar["sky_visible"] and not porch["sky_visible"]
    assert yard["falls_on_you"]
    assert not porch["falls_on_you"]        # covered
    assert not cellar["falls_on_you"]


def test_sheltering_from_rain_is_watching_it_fall():
    """Standing out of the rain and watching it come down is what a porch IS.
    `sky_visible` is rightly false there -- the sky overhead is a roof -- but
    the weather a metre beyond the eaves is the whole scene, and sight was the
    only channel treating a porch as a sealed room."""
    scene = _scene({"precipitation": "rain", "intensity": "heavy"})
    porch = weather_for_room(scene, "porch")
    yard = weather_for_room(scene, "yard")
    cellar = weather_for_room(scene, "cellar")

    assert porch["sky_visible"] is False        # unchanged: no sky overhead
    assert porch["weather_visible"] is True     # ...but the rain is right there
    assert yard["weather_visible"] is True
    assert cellar["weather_visible"] is False   # indoors is indoors

    # And it is seen in a smaller quantity, at the edges rather than all round.
    assert yard["visible_reach"] == 1.0
    assert 0 < porch["visible_reach"] < 1.0
    assert cellar["visible_reach"] == 0.0


def test_a_dry_sky_is_not_visible_weather():
    """Fair weather has nothing to draw. Only falling weather, or a storm sky
    that can flash, counts as something to see."""
    scene = _scene({"sky": "fair", "precipitation": "none", "intensity": "none"})
    assert weather_for_room(scene, "yard")["weather_visible"] is False
    storm = _scene({"sky": "storm", "precipitation": "none", "intensity": "none"})
    assert weather_for_room(storm, "yard")["weather_visible"] is True
    assert weather_for_room(storm, "porch")["weather_visible"] is True


def test_heavy_weather_is_audible_indoors_but_never_visible():
    """The most recognisable indoor ambience there is; a cellar that ignored a
    downpour would sound wrong."""
    scene = _scene({"precipitation": "rain", "intensity": "heavy"})
    cellar = weather_for_room(scene, "cellar")
    assert cellar["audible"] is True
    assert cellar["sky_visible"] is False


def test_drizzle_does_not_carry_indoors():
    scene = _scene({"precipitation": "drizzle", "intensity": "light"})
    assert weather_for_room(scene, "cellar")["audible"] is False
    assert weather_for_room(scene, "yard")["audible"] is True


def test_wind_reaches_a_porch_but_not_a_cellar():
    scene = _scene({"sky": "overcast", "wind": "gale"})
    assert weather_for_room(scene, "porch")["wind_reaches"] is True
    assert weather_for_room(scene, "cellar")["wind_reaches"] is False


def test_words_are_empty_where_the_weather_does_not_reach():
    scene = _scene({"sky": "overcast", "precipitation": "drizzle", "intensity": "light"})
    assert weather_words(weather_for_room(scene, "cellar"), "sight") == []
    assert "drizzle" in " ".join(weather_words(weather_for_room(scene, "yard"), "sight"))


def test_sight_and_sound_are_separate_channels():
    """One undifferentiated word list put "heavy rain outside" into an image
    prompt for a windowless room, and repainted its cached backdrop for
    weather it could only hear. The channels reach different distances through
    the same wall, so callers must say which sense they mean."""
    scene = _scene({"sky": "storm", "precipitation": "rain", "intensity": "heavy"})
    cellar = weather_for_room(scene, "cellar")
    assert weather_words(cellar, "sight") == []
    assert "rain" in " ".join(weather_words(cellar, "sound"))


def test_thunder_carries_where_nothing_else_does():
    scene = _scene({"sky": "storm", "precipitation": "rain", "intensity": "heavy"})
    # Graded by depth rather than said at full strength everywhere (see
    # test_thunder_arrives_at_the_distance_it_travelled) -- but it still gets
    # into a cellar, which is the whole claim here.
    assert any("thunder" in word
               for word in weather_words(weather_for_room(scene, "cellar"), "sound"))
    calm = _scene({"sky": "overcast", "precipitation": "rain", "intensity": "heavy"})
    assert not any("thunder" in word
                   for word in weather_words(weather_for_room(calm, "cellar"), "sound"))


# --- drift -----------------------------------------------------------------

def test_drift_is_deterministic_for_the_same_chat_and_clock():
    """A rerolled turn must not produce a different sky."""
    start = normalize_weather({"sky": "overcast"})
    first = advance_weather(start, 7 * 3600, seed="chat:12")
    again = advance_weather(start, 7 * 3600, seed="chat:12")
    assert first == again


def test_different_chats_drift_differently():
    start = normalize_weather({"sky": "overcast"})
    runs = {tuple(sorted(advance_weather(start, h * 3600, seed="chat:%d" % c).items()))
            for c in range(6) for h in (3, 9)}
    assert len(runs) > 1


def test_a_short_beat_does_not_move_the_weather():
    """An ordinary conversational turn is not a change in the weather."""
    start = normalize_weather({"sky": "storm", "precipitation": "rain",
                               "intensity": "heavy"})
    assert advance_weather(start, 400, seed="chat:1") == start


def test_drift_stays_inside_the_vocabulary():
    weather = normalize_weather({"sky": "fair"})
    for hour in range(1, 60):
        weather = advance_weather(weather, hour * 3600, seed="chat:3")
        assert weather == normalize_weather(weather)


def test_freezing_turns_rain_to_snow():
    """The one place temperature changes what falls rather than how it feels."""
    seen = set()
    for hour in range(1, 40):
        out = advance_weather({"sky": "storm", "temperature": "freezing"},
                              hour * 3600, seed="chat:9", cold=True)
        seen.add(out["precipitation"])
    assert "rain" not in seen
    assert seen & {"snow", "sleet"}


# --- what the presentation features see ------------------------------------

def test_indoor_rooms_keep_their_cached_backdrop_through_a_storm():
    """The economics: a cellar is not a new picture because it started raining
    over the city, but the courtyard is."""
    from dressing.backdrops import visual_signature
    dry = _scene()
    wet = _scene({"sky": "storm", "precipitation": "rain", "intensity": "heavy"})
    assert visual_signature(dry, "cellar") == visual_signature(wet, "cellar")
    assert visual_signature(dry, "yard") != visual_signature(wet, "yard")


def test_audible_weather_does_move_the_ambience_key_indoors():
    """...and the sound bed is the opposite case, because the cellar hears it."""
    from dressing.ambience import acoustic_signature
    dry = _scene()
    wet = _scene({"sky": "storm", "precipitation": "rain", "intensity": "heavy"})
    assert acoustic_signature(dry, "cellar") != acoustic_signature(wet, "cellar")


def test_weather_reaches_the_image_prompt_and_the_sound_query():
    from dressing.ambience import compose_query, room_soundscape
    from dressing.backdrops import compose_prompt, room_projection
    wet = _scene({"sky": "storm", "precipitation": "rain", "intensity": "heavy"})
    assert "rain" in compose_prompt(room_projection(wet, "yard"))
    assert "rain" in compose_query(room_soundscape(wet, "yard"))


def test_a_starship_deck_is_not_open_to_the_sky():
    """The keyword fallback runs against a live corpus full of starships,
    where a "deck" is a floor number and a "dock" is a hangar. Guessing open
    here puts rain inside a spacecraft."""
    scene = _scene(rooms={
        "d10": {"name": "Corridor, Deck 10", "desc": "Standard deck plating."},
        "bay": {"name": "Shuttle Dock", "desc": "Launch clamps and a bay door."},
    })
    assert room_exposure(scene, "d10") == "enclosed"
    assert room_exposure(scene, "bay") == "enclosed"


# --- how deep in you are ---------------------------------------------------

def _house():
    """A courtyard, a hall off it through an open doorway, a parlour behind a
    closed door, and a vault behind another."""
    return {
        "weather": {"precipitation": "rain", "intensity": "heavy"},
        "rooms": {
            "yard": {"name": "Courtyard", "desc": "Flagstones.",
                     "adjacent": [{"to": "hall", "barrier": "open_door"}]},
            "hall": {"name": "Entrance Hall", "desc": "Boots and coats.",
                     "exposure": "enclosed",
                     "adjacent": [{"to": "yard", "barrier": "open_door"},
                                  {"to": "parlour", "barrier": "closed_door"}]},
            "parlour": {"name": "Parlour", "desc": "A fire.",
                        "exposure": "enclosed",
                        "adjacent": [{"to": "hall", "barrier": "closed_door"},
                                     {"to": "vault", "barrier": "closed_door"}]},
            "vault": {"name": "Vault", "desc": "Iron shelving.",
                      "exposure": "enclosed",
                      "adjacent": [{"to": "parlour", "barrier": "closed_door"}]},
            # Joined to the map, but only through solid wall: sound has no
            # path, which is a real statement that it is sealed -- unlike a
            # room with no edges at all, which is just unmapped.
            "sealed": {"name": "Sealed Room", "desc": "Behind the vault wall.",
                       "exposure": "enclosed",
                       "adjacent": [{"to": "vault", "barrier": "wall"}]},
        },
    }


def test_an_open_doorway_is_not_a_layer():
    """A hall open to the courtyard is as close to the rain as the courtyard,
    so it gets the unmuffled sound."""
    house = _house()
    assert weather_depth(house, "hall") == 0
    assert weather_for_room(house, "hall")["muffling"] == ""


def test_each_closed_boundary_muffles_one_more_step():
    house = _house()
    assert weather_depth(house, "parlour") == 1
    assert weather_depth(house, "vault") == 2
    assert weather_for_room(house, "parlour")["muffling"] == "muffled"
    assert weather_for_room(house, "vault")["muffling"] == "faint"


def test_deeper_rooms_are_quieter_as_well_as_different():
    house = _house()
    levels = [weather_for_room(house, r)["gain"]
              for r in ("yard", "hall", "parlour", "vault")]
    assert levels == sorted(levels, reverse=True)
    assert levels[0] == 1.0 and levels[-1] < 0.3


def test_a_muffled_room_asks_for_a_different_recording():
    """Not the same clip turned down: "muffled rain" and "heavy rain" are
    different field recordings, and a library has both."""
    house = _house()
    assert "muffled rain" in " ".join(
        weather_words(weather_for_room(house, "parlour"), "sound"))
    assert "rain heavy" in " ".join(
        weather_words(weather_for_room(house, "yard"), "sound"))


def test_drizzle_stops_at_the_doorway():
    house = _house()
    house["weather"] = {"precipitation": "drizzle", "intensity": "light"}
    assert weather_for_room(house, "hall")["audible"] is True
    assert weather_for_room(house, "parlour")["audible"] is False


def test_a_sealed_room_hears_nothing():
    house = _house()
    assert weather_depth(house, "sealed") is None
    scoped = weather_for_room(house, "sealed")
    assert scoped["audible"] is False and scoped["gain"] == 0.0
    assert weather_words(scoped, "sound") == []


def test_depth_changes_the_ambience_key_but_not_the_backdrop_key():
    """Two rooms at different depths under one downpour want different sound
    and the same (weatherless) picture."""
    from dressing.ambience import acoustic_signature
    from dressing.backdrops import visual_signature
    house = _house()
    assert acoustic_signature(house, "hall") != acoustic_signature(house, "vault")
    # Neither indoor room shows weather, so the depth difference must leave the
    # PICTURE key untouched -- only their own descriptions separate them.
    dry = {**house, "weather": None}
    assert visual_signature(house, "vault") == visual_signature(dry, "vault")
    assert visual_signature(house, "hall") == visual_signature(dry, "hall")


def test_an_unmapped_room_is_not_assumed_sealed():
    """Absence of adjacency data is a gap in the map, not a statement that a
    room is airtight -- so a downpour is still heard, muffled."""
    scene = _scene({"precipitation": "rain", "intensity": "heavy"})
    cellar = weather_for_room(scene, "cellar")     # fixture has no adjacency
    assert cellar["audible"] is True
    assert cellar["muffling"] == "muffled"


def test_a_starship_never_acquires_weather():
    """No sky was established, so there is nothing to drift, nothing to hear
    and nothing to draw. Stellar weather would be its own phenomenon, not this
    one wearing a different word."""
    from dressing.ambience import compose_query, room_soundscape
    ship = {
        "rooms": {
            "d10": {"name": "Corridor, Deck 10", "desc": "Deck plating.",
                    "adjacent": [{"to": "bay", "barrier": "open_door"}]},
            "bay": {"name": "Shuttle Dock", "desc": "Launch clamps.",
                    "adjacent": [{"to": "d10", "barrier": "open_door"}]},
        },
    }
    for room in ("d10", "bay"):
        assert weather_for_room(ship, room) == {}
        assert weather_words(weather_for_room(ship, room), "sound") == []
        assert "rain" not in compose_query(room_soundscape(ship, room))


def test_a_bearing_only_edge_does_not_make_a_room_mapped():
    """Live scenes carry adjacency entries that record an opening without a
    destination. Reading those as a map made a room "provably sealed" when it
    was only undescribed, and silenced a downpour outside it."""
    scene = _scene({"precipitation": "rain", "intensity": "heavy"},
                   rooms={"lounge": {"name": "Lounge", "desc": "A long bar.",
                                     "adjacent": [{"barrier": "open", "dir": "aft"}]}})
    assert weather_for_room(scene, "lounge")["audible"] is True


# --- going underground -----------------------------------------------------

def _cave():
    """A hillside, then a mouth, then three chambers deeper in. Walking in
    should take the rain from present, to muffled, to faint, to gone."""
    def room(name, desc, edges, exposure=None):
        out = {"name": name, "desc": desc,
               "adjacent": [{"to": t, "barrier": b} for t, b in edges]}
        if exposure:
            out["exposure"] = exposure
        return out
    return {
        "weather": {"sky": "overcast", "precipitation": "rain", "intensity": "heavy"},
        "rooms": {
            "hill": room("Hillside", "Wet bracken.", [("mouth", "open")], "open"),
            "mouth": room("Cave Mouth", "A dripping overhang.",
                          [("hill", "open"), ("first", "closed_door")], "sheltered"),
            "first": room("First Chamber", "Cave walls, running water.",
                          [("mouth", "closed_door"), ("deep", "closed_door")], "enclosed"),
            "deep": room("Deep Chamber", "Cave dark, still air.",
                         [("first", "closed_door"), ("sump", "closed_door")], "enclosed"),
            "sump": room("The Sump", "Cave bottom, far below.",
                         [("deep", "closed_door")], "enclosed"),
        },
    }


def test_walking_into_a_cave_muffles_the_rain_then_silences_it():
    cave = _cave()
    got = [(r, weather_for_room(cave, r)["muffling"],
            weather_for_room(cave, r)["audible"])
           for r in ("hill", "mouth", "first", "deep", "sump")]
    assert [g[1:] for g in got] == [
        ("", True),         # standing in it
        ("", True),         # under the overhang, still right there
        ("muffled", True),  # one boundary in
        ("faint", True),    # two
        ("", False),        # too deep to hear at all
    ]


def test_the_level_drops_as_you_go_deeper():
    cave = _cave()
    gains = [weather_for_room(cave, r)["gain"]
             for r in ("hill", "mouth", "first", "deep", "sump")]
    assert gains == sorted(gains, reverse=True)
    assert gains[-1] == 0.0


def test_a_cave_asks_for_a_reverberant_recording():
    """Rain arriving into a cave comes with the cave on it."""
    cave = _cave()
    words = " ".join(weather_words(weather_for_room(cave, "first"), "sound"))
    assert "muffled rain" in words and "echoing" in words


def test_a_bunker_hears_nothing_even_unmapped():
    """The map is what normally answers this, but an unmapped bunker must not
    fall back to "an ordinary room one layer in" -- rain inside a mountain is a
    worse error than silence in a cellar."""
    scene = _scene({"precipitation": "rain", "intensity": "heavy"},
                   rooms={"b": {"name": "Bunker", "desc": "Concrete and bare bulbs."},
                          "c": {"name": "Cave System", "desc": "Deep below the ridge."}})
    for room in ("b", "c"):
        scoped = weather_for_room(scene, room)
        assert scoped["audible"] is False
        assert scoped["gain"] == 0.0
        assert weather_words(scoped, "sound") == []


class TestGroundState:
    """What the weather leaves behind. Weather that changes nothing is
    scenery; an hour of heavy rain should leave a yard muddy, and it should
    still be muddy when the sky clears."""

    def _yard(self, precipitation="rain", intensity="heavy", temperature="mild"):
        return _scene({"sky": "overcast", "precipitation": precipitation,
                       "intensity": intensity, "temperature": temperature})

    def test_rain_walks_the_ground_down_its_ladder(self):
        from world.weather import ground_after
        scene = self._yard()
        state, seen = {}, []
        for _ in range(6):
            state = ground_after(state, weather_for_room(scene, "yard"), "seasonal")
            seen.append(state["state"])
        assert seen[0] == "damp ground"
        assert "standing puddles" in seen
        assert seen[-1] == "churned mud"

    def test_it_dries_slower_than_it_soaks(self):
        """A puddle that vanished the moment the rain stopped would read as a
        bug, not as weather."""
        from world.weather import ground_after
        wet, dry = self._yard(), _scene({"precipitation": "none"})
        state = {}
        for _ in range(6):
            state = ground_after(state, weather_for_room(wet, "yard"), "seasonal")
        soaked = state["level"]
        state = ground_after(state, weather_for_room(dry, "yard"), "seasonal")
        assert 0 < state["level"] < soaked
        assert state["state"]                      # still something underfoot

    def test_snow_has_its_own_ladder(self):
        from world.weather import ground_after
        scene = self._yard(precipitation="snow", intensity="moderate",
                           temperature="freezing")
        state, seen = {}, []
        for _ in range(7):
            state = ground_after(state, weather_for_room(scene, "yard"), "seasonal")
            seen.append(state["state"])
        assert seen[0] == "a dusting of snow"
        assert seen[-1] == "snowdrifts"
        assert not any("mud" in s for s in seen)

    def test_freezing_rain_lays_ice_not_water(self):
        from world.weather import ground_after
        scene = self._yard(temperature="freezing")
        state = ground_after({}, weather_for_room(scene, "yard"), "seasonal")
        assert state["kind"] == "ice"

    def test_a_sheltered_floor_stays_dry_under_a_downpour(self):
        """What matters is whether anything is landing HERE."""
        from world.weather import ground_after
        scene = self._yard()
        assert ground_after({}, weather_for_room(scene, "porch"), "seasonal",
                            exposed=False) == {}
        assert ground_after({}, weather_for_room(scene, "cellar"), "seasonal",
                            exposed=False) == {}

    def test_calm_weather_leaves_no_mark_at_all(self):
        """The host's choice: weather as scenery. And anything already on the
        ground drains rather than being stranded mid-puddle."""
        from world.weather import ground_after
        scene = self._yard()
        assert ground_after({}, weather_for_room(scene, "yard"), "calm") == {}
        stranded = {"kind": "wet", "level": 6, "state": "churned mud"}
        after = ground_after(stranded, weather_for_room(scene, "yard"), "calm")
        assert after["level"] < 6

    def test_severity_only_caps_the_sky_when_calm(self):
        from world.weather import severity_intensity_cap
        assert severity_intensity_cap("calm") == "light"
        for other in ("seasonal", "harsh", "catastrophic"):
            assert severity_intensity_cap(other) == "heavy"


class TestABlizzardIsNotAThunderstorm:
    """Live failure, story "The Blizzard": the sky was
    `{sky: storm, precipitation: snow, intensity: heavy, wind: gale,
    temperature: freezing}` and the screen flashed with lightning, because
    everything downstream read "storm" as "electrical storm".

    Thundersnow is real. It is also rare enough that having it every time a
    blizzard blows is worse than never having it -- a reader watching bolts
    play over a whiteout is being told something false about the weather they
    are standing in.
    """

    BLIZZARD = {"sky": "storm", "precipitation": "snow", "intensity": "heavy",
                "wind": "gale", "temperature": "freezing"}

    def test_the_blizzard_does_not_flash(self):
        from world.weather import has_lightning
        assert not has_lightning(self.BLIZZARD)

    def test_but_thundersnow_does(self):
        """Rare, not forbidden. Derived from the precipitation, every blizzard
        flashes; forbidden outright, none ever can -- so it is a property of
        the sky, rolled by the drift or declared by a beat."""
        from world.weather import has_lightning, normalize_weather
        lit = normalize_weather(dict(self.BLIZZARD, thundersnow=True))
        assert lit["thundersnow"] is True
        assert has_lightning(lit)

    def test_the_flag_only_survives_where_it_means_something(self):
        """On a rainstorm it is redundant, on a clear sky meaningless -- and
        left to linger it would keep lightning over a sky that stopped
        snowing."""
        from world.weather import normalize_weather
        for sky, falling in (("storm", "rain"), ("clear", "none"),
                             ("overcast", "rain")):
            out = normalize_weather(
                {"sky": sky, "precipitation": falling, "thundersnow": True})
            assert out["thundersnow"] is False, (sky, falling)

    def test_thundersnow_is_heard_as_well_as_seen(self):
        from world.weather import weather_words
        scoped = dict(self.BLIZZARD, thundersnow=True, exposure="open",
                      audible=True, falls_on_you=True, weather_visible=True)
        assert "thunder" in weather_words(scoped, channel="sound")

    def test_the_drift_makes_it_rare_and_repeatable(self):
        """Seeded like every other drift: a reroll cannot conjure it and a
        replay cannot lose it."""
        from world.weather import advance_weather, DRIFT_SECONDS, THUNDERSNOW_ODDS
        lit = [step for step in range(1, 91)
               if advance_weather(self.BLIZZARD, DRIFT_SECONDS * step,
                                  seed="blizzard:46").get("thundersnow")]
        # Rare enough to stay an event, common enough to be worth building.
        assert 0 < len(lit) < 90 // (THUNDERSNOW_ODDS - 4)
        again = [step for step in range(1, 91)
                 if advance_weather(self.BLIZZARD, DRIFT_SECONDS * step,
                                    seed="blizzard:46").get("thundersnow")]
        assert lit == again
        # A different story gets a different storm.
        other = [step for step in range(1, 91)
                 if advance_weather(self.BLIZZARD, DRIFT_SECONDS * step,
                                    seed="elsewhere:1").get("thundersnow")]
        assert other != lit

    def test_a_rainstorm_is_never_marked_thundersnow_by_the_drift(self):
        from world.weather import advance_weather, DRIFT_SECONDS
        rainy = dict(self.BLIZZARD, precipitation="rain", temperature="cool")
        for step in range(1, 40):
            after = advance_weather(rainy, DRIFT_SECONDS * step, seed="s")
            if after["precipitation"] not in ("snow", "sleet"):
                assert not after["thundersnow"], after

    def test_sleet_does_not_either(self):
        from world.weather import has_lightning
        assert not has_lightning(dict(self.BLIZZARD, precipitation="sleet"))

    def test_rain_and_hail_still_do(self):
        """Hail comes out of exactly the convective storms that throw
        lightning, so it is deliberately not on the unlit list."""
        from world.weather import has_lightning
        for falling in ("rain", "hail", "none"):
            assert has_lightning(dict(self.BLIZZARD, precipitation=falling)), falling

    def test_a_sky_that_is_not_a_storm_never_does(self):
        from world.weather import has_lightning
        for sky in ("clear", "fair", "overcast", "fog"):
            assert not has_lightning({"sky": sky, "precipitation": "rain"})

    def test_junk_is_not_a_storm(self):
        from world.weather import has_lightning
        assert not has_lightning(None)
        assert not has_lightning({})

    def test_nobody_hears_thunder_in_a_blizzard(self):
        """The audible half of the same mistake: `weather_words` put "thunder"
        into the sound of any storm sky, through walls and into cellars."""
        from world.weather import weather_words
        scoped = dict(self.BLIZZARD, exposure="open", audible=True,
                      falls_on_you=True, weather_visible=True)
        assert "thunder" not in weather_words(scoped, channel="sound")
        raining = dict(scoped, precipitation="rain")
        assert "thunder" in weather_words(raining, channel="sound")

    def test_a_freezing_sky_keeps_snowing_as_it_drifts(self):
        """The lightning was the bug; this is the thing next to it that was
        already right, pinned so it stays that way. Storm's own precipitation
        table offers rain and hail, and only the freezing conversion keeps a
        blizzard from turning into a downpour an hour in."""
        from world.weather import advance_weather
        after = advance_weather(self.BLIZZARD, 60 * 60 * 6, seed="blizzard:1")
        assert after["precipitation"] in ("snow", "sleet", "none")
        assert after["temperature"] == "freezing"


class TestTheDirectorWritesTheVividWord:
    """Live failure, story "The Blizzard", turn 2. The Director reported the
    weather correctly and in full, in the words anyone would reach for:

        {"sky": "blizzard", "precipitation": "heavy snow", "intensity":
         "severe", "wind": "gale-force", "temperature": "sub-zero"}

    Not one of the five was in the closed vocabulary, so each fell to its
    default -- and every default is the MILDEST reading of its field. The
    declaration normalised to a calm spring day and, being a declaration,
    replaced the blizzard that was actually blowing. The player stood in an
    open clearing in a whiteout with the snow overlay off, the gale gone from
    the room's sound, and five later beats inheriting the calm.

    Scrolling back through that story is what made it visible: the sky changes
    at turn 2 while the prose is still a whiteout.
    """

    DECLARED = {"sky": "blizzard", "precipitation": "heavy snow",
                "intensity": "severe", "wind": "gale-force",
                "temperature": "sub-zero", "thundersnow": False}
    BLOWING = {"sky": "storm", "precipitation": "snow", "intensity": "heavy",
               "wind": "gale", "temperature": "freezing"}

    def test_the_blizzard_survives_being_described(self):
        from world.weather import normalize_weather
        assert normalize_weather(self.DECLARED) == \
            dict(self.BLOWING, thundersnow=False)

    def test_and_survives_being_written_over_itself(self):
        from world.weather import normalize_weather
        assert normalize_weather(self.DECLARED, self.BLOWING) == \
            dict(self.BLOWING, thundersnow=False)

    def test_a_declaration_is_a_report_not_a_restatement(self):
        """A beat that noticed the wind rise says so and says nothing else.
        Replacing the sky wholesale made every partial report a forecast."""
        from world.weather import normalize_weather
        risen = normalize_weather({"wind": "gale"},
                                  dict(self.BLOWING, wind="breeze"))
        assert risen == dict(self.BLOWING, thundersnow=False)

    def test_the_storm_can_still_actually_end(self):
        """The point is not that weather never clears -- it is that clearing
        has to be something a beat SAID, not something a vocabulary miss did."""
        from world.weather import normalize_weather
        cleared = normalize_weather(
            {"sky": "clear", "precipitation": "none", "wind": "still"},
            self.BLOWING)
        assert cleared["sky"] == "clear"
        assert cleared["precipitation"] == "none"
        assert cleared["intensity"] == "none"
        assert cleared["wind"] == "still"
        # Unmentioned, so it keeps what it had: the air does not warm up
        # because the snow stopped.
        assert cleared["temperature"] == "freezing"

    def test_the_earliest_word_in_the_phrase_wins(self):
        """"gale-force wind" names a gale and qualifies it with the noun.
        Scanning the vocabulary in its own order instead answered `wind`."""
        from world.weather import normalize_weather
        assert normalize_weather({"wind": "gale-force wind"})["wind"] == "gale"
        both = normalize_weather({"precipitation": "heavy snow",
                                  "intensity": "heavy snow"})
        assert both["precipitation"] == "snow" and both["intensity"] == "heavy"

    def test_a_beat_reporting_the_wind_does_not_put_the_lightning_out(self):
        from world.weather import normalize_weather
        lit = dict(self.BLOWING, thundersnow=True)
        assert normalize_weather({"wind": "gale"}, lit)["thundersnow"] is True


def test_the_renderer_mirrors_the_lightning_rule():
    """Two implementations of one rule, so they are checked against each other:
    a sky that flashes with no thunder to follow it is the worse half of this
    bug, not the better one."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]
              / "static/js/weather-fx.js").read_text(encoding="utf-8")
    assert "function weatherFxStormy(" in source
    assert 'weather.precipitation === "snow"' in source
    assert 'weather.precipitation === "sleet"' in source
    # ...and the scheduler re-checks it on every flash, not only on the first.
    assert source.count("weatherFxStormy(") >= 3
    # ...and it honours the flag rather than banning snow outright.
    assert "weather.thundersnow" in source


def test_snow_does_not_render_as_a_grid():
    """Snow read as a lattice: a snowflake is a distinct round blob, so the eye
    finds the same little constellation repeating, where a rain streak blurs
    into its neighbours. Three causes, all fixed here."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]
              / "static/js/weather-fx.js").read_text(encoding="utf-8")
    # 1. Its own, larger tiles -- and sizes that are not multiples of each
    #    other, so the layers' repeats never come back into phase.
    assert "WFX_LAYERS_SNOW" in source
    for size in ("317", "233", "179"):
        assert size in source
    # 2. Marks scaled by tile AREA. Every layer used to carry the same count at
    #    a different size, which made the small tile three times the density of
    #    the large one.
    assert "WFX_DENSITY_TILE" in source
    assert "spec.size * spec.size" in source
    # 3. Layers offset inside their own tiles, so the repeats do not stack.
    assert "backgroundPosition" in source


def test_snow_marks_hold_one_density_across_layers():
    """The maths behind (2), checked rather than trusted: three tile sizes must
    come out at the same marks-per-area or the layers disagree about how hard
    it is snowing."""
    reference, density = 110, 34          # WFX_DENSITY_TILE, heavy
    for sizes in ((317, 233, 179), (150, 110, 80)):
        per_area = [
            max(2, round(density * size * size / (reference * reference)))
            * reference * reference / (size * size)
            for size in sizes
        ]
        assert max(per_area) - min(per_area) < 0.5, sizes


def test_snow_does_not_all_fall_one_way():
    """Three layers sliding down one identical vector reads as a sheet of
    wallpaper being pulled, not as snow. Rain is deliberately exempt: it falls
    hard and straight, and swaying it would be a lie about how rain behaves."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]
              / "static/js/weather-fx.js").read_text(encoding="utf-8")
    css = (Path(__file__).resolve().parents[1]
           / "static/styles.css").read_text(encoding="utf-8")
    # A second, composed transform -- not a replacement for the fall.
    assert "wfx-drift" in source and ".wfx-drift{" in css
    assert "@keyframes wfx-sway" in css
    # `alternate` is what makes the sway seamless: it returns to zero at the end
    # of every period by definition.
    assert "animation-direction:alternate" in css
    # Rain has no sway spec at all, so the wrapper is never built for it.
    assert "spec.sway ? el(" in source
    # The rotation uses the `rotate` PROPERTY: an inline transform would simply
    # be overridden by the sway animation.
    assert "drift.style.rotate" in source
    # Reduced motion stops the drift as well as the fall.
    assert "@media (prefers-reduced-motion:reduce){.wfx-drift{animation:none}}" in css


def test_the_snow_layers_never_fall_back_into_step():
    """Periods that divide each other would re-sync the depths on a cycle,
    which is the thing being fixed reappearing more slowly."""
    from fractions import Fraction
    periods = [Fraction(str(p)) for p in (8.3, 11.7, 15.1)]
    for i, a in enumerate(periods):
        for b in periods[i + 1:]:
            assert (a / b).denominator > 3, (a, b)


def test_rain_falls_faster_than_it_drifts():
    """Measured against the first pass, which read as drifting rather than
    falling: a raindrop crosses a window faster than anything else the eye is
    used to tracking. Snow is deliberately unchanged."""
    from pathlib import Path
    import re
    source = (Path(__file__).resolve().parents[1]
              / "static/js/weather-fx.js").read_text(encoding="utf-8")
    block = re.search(r"const WFX_FALL_S = \{(.+?)\};", source, re.S).group(1)
    rain = re.search(r"rain: \{ light: ([\d.]+), moderate: ([\d.]+), heavy: ([\d.]+)",
                     block)
    snow = re.search(r"snow: \{ light: ([\d.]+), moderate: ([\d.]+), heavy: ([\d.]+)",
                     block)
    for got, want in zip(rain.groups(), ("0.88", "0.62", "0.44")):
        assert got == want, (got, want)
    # Snow untouched at its original pace.
    assert snow.groups() == ("9", "7", "5.5")
    # And rain is still faster than snow at every intensity, by a wide margin.
    for r, s in zip(rain.groups(), snow.groups()):
        assert float(r) < float(s)


def test_thunder_arrives_at_the_distance_it_travelled():
    """Found by driving the pipeline by hand: a cellar behind two closed doors
    reported `faint rain` and a full-strength `thunder` in the same breath --
    two distances at once. Thunder does carry where the weather does not, which
    is why it is never silenced; it is graded one rung softer instead."""
    from world.weather import weather_for_room, weather_words
    scene = {
        "weather": {"sky": "storm", "precipitation": "rain", "intensity": "heavy"},
        "rooms": {
            "yard": {"name": "Yard", "exposure": "open",
                     "adjacent": [{"to": "hall", "barrier": "closed_door"}]},
            "hall": {"name": "Hall", "exposure": "enclosed",
                     "adjacent": [{"to": "yard", "barrier": "closed_door"},
                                  {"to": "cellar", "barrier": "closed_door"}]},
            "cellar": {"name": "Cellar", "exposure": "enclosed",
                       "adjacent": [{"to": "hall", "barrier": "closed_door"}]},
        },
        "positions": {},
    }
    heard = {rid: weather_words(weather_for_room(scene, rid), channel="sound")
             for rid in ("yard", "hall", "cellar")}
    assert "thunder" in heard["yard"]
    assert "distant thunder" in heard["hall"]
    assert "muffled thunder" in heard["cellar"]
    # Never silenced by depth: the clap is exactly what reaches a cellar when
    # the rain does not.
    assert any("thunder" in w for w in heard["cellar"])


def test_a_snowing_storm_still_says_nothing_at_any_depth():
    from world.weather import weather_for_room, weather_words
    scene = {
        "weather": {"sky": "storm", "precipitation": "snow", "intensity": "heavy",
                    "temperature": "freezing"},
        "rooms": {"yard": {"name": "Yard", "exposure": "open", "adjacent": []}},
        "positions": {},
    }
    assert not any("thunder" in w
                   for w in weather_words(weather_for_room(scene, "yard"),
                                          channel="sound"))
