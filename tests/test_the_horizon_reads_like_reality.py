"""The horizon reads like reality (UNBUILT_WORLD §2.40's vista defects, and
UNBUILT_CHARACTERS §1.178).

Found by the landscape survey of 2026-10-05, each probed on the engine's
own readers: a view of the horizon that a blind card still had, that a
building standing in the field never hid, that showed a town's daytime roofs
at midnight, that hid a village below a tower as if it had sunk past the
curve of the earth -- and that English memory never kept at all.
"""

from __future__ import annotations

import copy

from tests.test_vistas import RANGE, TOWN, _yard
from world.vistas import (looked_vistas, normalize_vista, obstructed,
                          visible_vistas, vista_verdict, what_a_look_finds)
from world.weather import room_exposure


def _names(sc, who="Ren", senses=None):
    return [v["name"] for v, _ in visible_vistas(sc, who, senses=senses)]


# (a) a room looks out by what it DECLARES, never by a guess from its name ------

def test_an_outdoor_place_looks_out_by_what_it_declares():
    """The keyword guess (`weather.room_exposure`) calls this trail open; it
    also calls a tavern's staircase landing and a shrine's roost open
    (measured 2026-10-05), and an outlook is a sightline prose may not
    open. Declared, it sees the horizon; the planner declares it."""
    sc = _yard()
    sc["rooms"]["trail"] = {"name": "The Ridge Trail", "desc": "A path along the ridge.",
                            "adjacent": []}
    sc["positions"]["Ren"] = "trail"
    assert room_exposure(sc, "trail") == "open"
    assert _names(sc) == []
    sc["rooms"]["trail"]["exposure"] = "open"
    assert _names(sc) == ["the Kurogane range", "the valley town"]


def test_a_cabin_inside_a_vehicle_sees_no_horizon_without_a_window():
    sc = _yard()
    sc["rooms"]["console"] = {"name": "Console Room", "desc": "A lamplit console room.",
                              "exposure": "sheltered", "parent_entity": "tardis",
                              "adjacent": []}
    sc["entities"]["tardis"] = {"name": "the TARDIS"}
    sc["positions"]["Ren"] = "console"
    assert room_exposure(sc, "console") == "enclosed"
    assert _names(sc) == []


# (b) a building standing in the field is in front of the ridge ---------------

def _field_with_mill(mill_inside):
    field_site = {"plan": "p", "x": 0, "y": 0} if mill_inside else {"plan": "p", "x": 0, "y": 10}
    field_extent = {"w": 20, "d": 60} if mill_inside else {"w": 20, "d": 50}
    return {"rooms": {
        "field": {"name": "Field", "desc": ".", "exposure": "open", "extent": field_extent,
                  "site": field_site, "adjacent": []},
        "mill": {"name": "Mill", "desc": ".", "exposure": "enclosed",
                 "extent": {"w": 6, "d": 6}, "site": {"plan": "p", "x": 7, "y": 2},
                 "adjacent": []},
        "mill_loft": {"name": "Mill loft", "desc": ".", "exposure": "enclosed", "level": 1,
                      "extent": {"w": 6, "d": 6}, "site": {"plan": "p", "x": 7, "y": 2},
                      "adjacent": []}},
        "entities": {}, "positions": {"Ren": "field"},
        "stations": {"Ren": {"cell": [10, 55 if mill_inside else 45]}},
        "weather": {"air": "clear"}, "day_phase": "afternoon"}


def test_a_mill_standing_in_the_field_hides_the_low_ridge_behind_it():
    from world.site_plan import EYE_M
    ridge = normalize_vista({"name": "a low ridge", "bearing": "n", "distance_km": 20,
                             "height_m": 150})
    assert obstructed(_field_with_mill(False), "Ren", ridge, EYE_M["standing"])
    assert obstructed(_field_with_mill(True), "Ren", ridge, EYE_M["standing"])


# (c) a lit town at night is its lights, not its daytime roofs ----------------

def test_a_lit_town_at_night_shows_its_lights_not_its_roofs():
    from agents.composer import vista_percepts
    town = dict(TOWN, desc="red tile roofs and a white church spire")
    day = _yard(day_phase="afternoon", vistas=[RANGE, town])
    night = _yard(day_phase="night", weather={"air": "clear", "moon": "none"},
                  vistas=[RANGE, town])
    (by_day,) = [p.data["desc"] for p in vista_percepts(visible_vistas(day, "Ren"))
                 if "town" in p.data["desc"]]
    (by_night,) = [p.data["desc"] for p in vista_percepts(visible_vistas(night, "Ren"))
                   if "town" in p.data["desc"]]
    assert "church spire" in by_day
    assert "church spire" not in by_night and "light" in by_night


# (d) a card whose sight is absent sees no horizon ----------------------------

def test_a_blind_card_sees_no_horizon():
    blind = [{"channel": "sight", "acuity": "blind"}]
    assert _names(_yard(), senses=blind) == []
    assert _names(_yard()) == ["the Kurogane range", "the valley town"]


def test_the_composed_view_hands_the_card_to_the_horizon():
    from agents.perception import _composer_standing_percepts
    blind = [{"channel": "sight", "acuity": "blind"}]
    p = {"room": "yard", "room_name": "Yard", "sense_card": blind}
    percepts = _composer_standing_percepts(_yard(), p, "Ren", [], {}, {})
    assert not [q for q in percepts if q.kind == "ambient" and q.channel == "sight"]


# (e) a look is the view's news, and the next beat does not repeat it ---------

def test_a_vista_looked_at_is_not_announced_again_next_beat():
    from agents import composer
    sc = _yard()
    looked = looked_vistas(sc, ["the_kurogane_range"])
    beat = composer.vista_percepts(visible_vistas(sc, "Ren"), looked=[
        (v, what_a_look_finds(sc, "Ren", v)) for v in looked])
    first = composer.render_view(beat, mode="player", language="en")
    assert "Kurogane" in first.text
    later = composer.vista_percepts(visible_vistas(sc, "Ren"))
    for lang in ("en", "ja"):
        prev = composer.render_view(beat, mode="player", language=lang)
        again = composer.render_view(later, mode="player", language=lang,
                                     prev_standing=frozenset(prev.standing_keys))
        assert "Kurogane" not in again.text, lang


# (f, g) a village below the eye is seen; a town down the valley stays below --

def test_a_village_below_a_tower_is_seen_and_one_past_the_curve_is_not():
    village = normalize_vista({"name": "the village below", "bearing": "s",
                               "distance_km": 1.0, "height_m": 20})
    assert vista_verdict(village, eye_m=60.0) is None
    assert vista_verdict(village, eye_m=1.6) is None
    hull_down = normalize_vista({"name": "a low islet", "bearing": "s",
                                 "distance_km": 40.0, "height_m": 5})
    assert vista_verdict(hull_down, eye_m=1.6) == "below"


def test_a_town_down_the_valley_keeps_its_depth():
    town = normalize_vista({"name": "the town", "bearing": "s", "distance_km": 14,
                            "height_m": -300})
    assert town["height_m"] == -300
    assert vista_verdict(town, eye_m=1.6) is None


# (h) "look south" is a look -------------------------------------------------

def test_a_look_by_compass_word_finds_what_stands_that_way():
    sc = _yard()
    assert [v["name"] for v in looked_vistas(sc, ["south"], name="Ren")] == ["the valley town"]
    assert [v["name"] for v in looked_vistas(sc, ["N"], name="Ren")] == ["the Kurogane range"]


def test_a_look_by_compass_word_never_names_what_is_not_in_view():
    """A compass word carries no knowledge of what stands that way: from a
    windowless room, in fog, or to a blind eye, a look south finds nothing
    and names nothing -- it was told the town's name and remembered it
    (review 2026-10-05). A look that NAMES the vista is the actor's own
    knowledge and still finds that it cannot be made out."""
    from agents import composer
    sc = _yard()
    sc["positions"]["Ren"] = "hall"                  # a closed room
    assert looked_vistas(sc, ["south"], name="Ren") == []
    sc = _yard(weather={"air": "thick"})              # fog hides the town
    assert looked_vistas(sc, ["south"], name="Ren") == []
    blind = [{"channel": "sight", "acuity": "blind"}]
    assert looked_vistas(_yard(), ["south"], name="Ren", senses=blind) == []
    named = looked_vistas(sc, ["the valley town"], name="Ren")
    lines = composer.vista_percepts([], looked=[
        (v, what_a_look_finds(sc, "Ren", v)) for v in named])
    assert "nothing can be made out" in lines[0].data["desc"]


# §1.178: English memory keeps what was seen far off and heard this beat -------

def test_english_memory_keeps_the_horizon_a_look_and_a_beats_sound():
    from agents import composer
    sc = _yard()
    standing = composer.vista_percepts(visible_vistas(sc, "Ren"))
    content, _gist, _ents = composer.render_episode(standing, language="en")
    assert "Kurogane" in content
    content, _gist, _ents = composer.render_episode(
        standing, language="en", prev_standing=frozenset(p.dedupe_key for p in standing))
    assert content == ""                      # the same horizon is not news
    looked = looked_vistas(sc, ["the_kurogane_range"])
    beat = composer.vista_percepts(visible_vistas(sc, "Ren"), looked=[
        (v, what_a_look_finds(sc, "Ren", v)) for v in looked])
    content, _gist, _ents = composer.render_episode(
        beat, language="en", prev_standing=frozenset(p.dedupe_key for p in standing))
    assert "Kurogane" in content
    hiss = composer.Percept(kind="ambient", channel="hearing", source_label="",
                            fidelity="full", data={"desc": "Steam hisses from the pipe."},
                            salience=0.5, order_key=1, dedupe_key="ambient:hiss")
    content, _gist, _ents = composer.render_episode([hiss], language="en")
    assert "hisses" in content


def test_the_sky_on_the_skin_is_said_with_one_stop():
    """"The air is mild.." in every outdoor view and memory: the pack writes
    the clause as a whole sentence and the sensation renderer added a stop
    (seen 2026-10-05)."""
    from agents import composer
    from world.weather import weather_for_room
    sc = {"rooms": {"yard": {"name": "Yard", "desc": ".", "exposure": "open"}},
          "positions": {"Ren": "yard"}, "entities": {}, "day_phase": "afternoon",
          "weather": {"air": "clear", "temperature": "mild"}}
    percepts = composer.weather_percepts(weather_for_room(sc, "yard", "Ren"))
    view = composer.render_view(percepts, mode="character", language="en").text
    memory = composer.render_episode(percepts, language="en")[0]
    assert view == "The air is mild." and memory == "The air is mild."


def test_vistas_on_one_bearing_read_nearest_first_and_beyond_each_other():
    """Kirinoura (scratch chat 167, 2026-10-05): the river, the fields across
    it and the hills closing the valley were three standing lines in a row,
    each opening "To the south,". One bearing, nearest first, each one after
    the first beyond the one before it."""
    from agents import composer
    sc = _yard(vistas=[
        {"name": "the wooded hills", "bearing": "s", "distance_km": 5, "height_m": 300},
        {"name": "the slow river", "bearing": "s", "distance_km": 0.8, "height_m": 0},
        dict(RANGE),
        {"name": "the rice fields", "bearing": "s", "distance_km": 1.5, "height_m": 0}])
    lines = [p.data["desc"] for p in composer.vista_percepts(visible_vistas(sc, "Ren"))]
    assert lines[0].startswith("To the south, the slow river")
    # Named in the line itself: a standing line is said alone on a later
    # beat, and "Beyond it" then leaned on nothing (review, 2026-10-05).
    assert lines[1].startswith("Beyond the slow river, the rice fields")
    assert lines[2].startswith("Beyond the rice fields, the wooded hills")
    assert lines[3].startswith("To the north, the Kurogane range")
    # A vista whose distance nobody gave is beyond nothing -- and stays so
    # once stored, read back through every later normalization (review
    # round 2, 2026-10-05: the stored 10 km default read as given).
    sc["vistas"].append({"name": "a cairn", "bearing": "s", "height_m": 2})
    lines = [p.data["desc"] for p in composer.vista_percepts(visible_vistas(sc, "Ren"))]
    assert "To the south, a cairn." in lines
    stored = normalize_vista({"name": "a cairn", "bearing": "s", "height_m": 2})
    assert normalize_vista(stored)["distance_given"] is False
    # A vista stored before the flag holds the default as if authored.
    assert normalize_vista({"name": "x", "bearing": "s", "distance_km": 10.0})["distance_given"] is False
    assert normalize_vista({"name": "x", "bearing": "s", "distance_km": 3.0})["distance_given"] is True
