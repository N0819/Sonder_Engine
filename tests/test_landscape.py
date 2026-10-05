"""A level of detail for distant landscapes (`world/landscape.py`).

The owner, 2026-10-05: "all I wanted it for was distant landscapes. like 5
or so rooms of distance or more", and "go ahead" to the plan UNBUILT_WORLD
§2.40 records: places, not people; far starts past the next room, detail by
measured distance where the world measures it, otherwise two to four rooms
off the place and what is big on it and five or more its outline; a far
place named only once the mind knows it. Hand-made scenes; the names are
illustrations, not the rule.
"""

from __future__ import annotations

import copy

from agents import composer
from world.landscape import far_places, near_field
from world.scene_memo import scene_read_pass


def _valley(**over):
    """A yard looking east down a line of open fields: orchard, meadow (an
    oak on it), mill field (a mill fronting it), river bank, far hill."""
    def field(name, prev, nxt, **room):
        adj = []
        if prev:
            adj.append({"to": prev, "barrier": "open", "dir": "w"})
        if nxt:
            adj.append({"to": nxt, "barrier": "open", "dir": "e"})
        return {"name": name, "desc": ".", "exposure": "open", "adjacent": adj, **room}
    rooms = {
        "yard": field("The Yard", None, "orchard"),
        "orchard": field("The Orchard", "yard", "meadow"),
        "meadow": field("The Meadow", "orchard", "mill_field", anchors={
            "oak": {"desc": "a great spreading oak", "dir": "n",
                    "height": "full", "footprint": "large"},
            "stone": {"desc": "a mossy stone", "dir": "s", "height": "floor",
                      "footprint": "point"}}),
        "mill_field": field("The Mill Field", "meadow", "riverbank"),
        "riverbank": field("The River Bank", "mill_field", "far_hill"),
        "far_hill": field("The Far Hill", "riverbank", None),
        "mill": {"name": "The Mill", "desc": ".", "exposure": "enclosed",
                 "adjacent": [{"to": "mill_field", "barrier": "closed_door", "dir": "s"}]},
    }
    rooms["mill_field"]["adjacent"].append({"to": "mill", "barrier": "closed_door", "dir": "n"})
    sc = {"rooms": rooms, "positions": {"Ada": "yard"}, "stations": {},
          "entities": {}, "day_phase": "afternoon", "weather": {"air": "clear"}}
    sc.update(over)
    return sc


def _places(sc, who="Ada", **kw):
    with scene_read_pass(sc):
        return far_places(sc, who, **kw)


def _lines(sc, who="Ada", **kw):
    percepts = composer.landscape_percepts(_places(sc, who, **kw))
    return [composer.render_landscape_line(line)
            for _rep, line in composer.landscape_lines(percepts)]


ALL = {r: "" for r in _valley()["rooms"]}


# --------------------------------------------------------------------------
# The near field is never answered
# --------------------------------------------------------------------------

def test_the_room_and_every_room_one_edge_off_are_never_far():
    places = {p["room"] for p in _places(_valley(), known=ALL)}
    assert "yard" not in places and "orchard" not in places
    assert {"meadow", "mill_field", "riverbank", "far_hill", "mill"} <= places


def test_a_wall_declared_from_the_far_side_still_makes_a_room_near():
    sc = _valley()
    sc["rooms"]["meadow"]["adjacent"].append({"to": "yard", "barrier": "wall"})
    assert "meadow" in near_field(sc, "yard")
    assert "meadow" not in {p["room"] for p in _places(sc)}


def test_a_scene_with_no_far_ground_is_silent():
    sc = _valley()
    for rid in sc["rooms"]:
        sc["rooms"][rid].pop("exposure", None)
    assert _places(sc) == []


# --------------------------------------------------------------------------
# Places, not people; declared, never guessed
# --------------------------------------------------------------------------

def test_no_body_and_no_carried_lamp_is_read():
    sc = _valley(day_phase="night", weather={"air": "clear", "moon": "full"})
    sc["positions"].update({"Ben": "meadow", "lantern": "meadow"})
    sc["entities"]["lantern"] = {"name": "a lantern", "light_source": "bright",
                                 "light_radius": "room", "state": {"lit": True}}
    sc["contained"] = {"lantern": {"in": "Ben", "mode": "held"}}
    sc["entities"]["moon"] = {"name": "The Moon", "kind": "celestial",
                              "light_source": "dim", "light_radius": "room"}
    sc["positions"]["moon"] = "meadow"
    text = " ".join(_lines(sc, known=ALL))
    assert "Ben" not in text and "lantern" not in text and "Moon" not in text
    assert not any(p["lights"] for p in _places(sc, known=ALL))


def test_a_room_is_ground_only_by_what_it_declares():
    """The keyword guess would call a "Staircase Landing" open ground; an
    outlook is a sightline, and prose may not open one."""
    sc = _valley()
    sc["rooms"]["meadow"].pop("exposure")
    sc["rooms"]["meadow"]["name"] = "The Staircase Landing"
    rooms = {p["room"] for p in _places(sc, known=ALL)}
    assert "meadow" not in rooms and "mill_field" not in rooms


# --------------------------------------------------------------------------
# The grain: rooms off, or metres where the world measured them
# --------------------------------------------------------------------------

def test_two_to_four_rooms_off_is_the_place_and_what_is_big_on_it():
    by = {p["room"]: p for p in _places(_valley(), known=ALL)}
    assert by["meadow"]["hops"] == 2 and by["meadow"]["grain"] == "mid"
    assert by["meadow"]["big"] == ["a great spreading oak"]       # never the stone
    assert by["far_hill"]["hops"] == 5 and by["far_hill"]["grain"] == "outline"


def _measured(edge_metres):
    sc = _valley()
    for rid in ("yard", "orchard", "meadow", "mill_field", "riverbank"):
        sc["rooms"][rid]["extent"] = {"w": 40, "d": 20}      # 30 m east-west
        for e in sc["rooms"][rid]["adjacent"]:
            if e["barrier"] == "open":
                e["distance"] = edge_metres
    return sc


def test_a_measured_path_is_graded_by_its_metres_not_its_rooms():
    # 15 + 4 x 30 + 5 x 2 m: the far hill is five rooms off and 145 m away
    by = {p["room"]: p for p in _places(_measured("2 m"), known=ALL)}
    assert by["far_hill"]["hops"] == 5 and by["far_hill"]["tier"] == "mid"
    # ...and with 200 m between each field, 1,135 m away: its outline
    by = {p["room"]: p for p in _places(_measured("200 m"), known=ALL)}
    assert by["meadow"]["tier"] == "outline" and by["far_hill"]["tier"] == "outline"


def test_fog_hides_a_measured_place_past_what_it_lets_through():
    sc = _measured("200 m")
    sc["weather"] = {"air": "thick"}                          # fog: 0.8 km
    rooms = {p["room"] for p in _places(sc, known=ALL)}
    assert "meadow" in rooms                                   # 445 m
    assert "far_hill" not in rooms                             # 1,135 m


# --------------------------------------------------------------------------
# Named only once known; the way out named only where the view named it
# --------------------------------------------------------------------------

def test_a_known_place_is_named_and_an_unknown_one_described():
    text = _lines(_valley(), known={"meadow": "the long meadow"})[0]
    assert "the long meadow" in text
    assert "The Mill Field" not in text and "The Far Hill" not in text
    assert "open ground" in text


def test_the_way_out_is_named_only_where_the_view_named_it():
    lines = _lines(_valley(), known=ALL, via_names={"orchard": "The Orchard"})
    assert lines[0].startswith("To the east, past The Orchard, you can see")
    assert _lines(_valley(), known=ALL)[0].startswith("To the east, you can see")


# --------------------------------------------------------------------------
# A window looks one way; a building ends the line
# --------------------------------------------------------------------------

def test_a_window_looks_out_along_its_own_bearing_only():
    sc = _valley()
    sc["rooms"]["kitchen"] = {"name": "Kitchen", "desc": ".", "exposure": "enclosed",
                              "adjacent": [{"to": "yard", "barrier": "window", "dir": "e"}]}
    sc["positions"]["Ada"] = "kitchen"
    assert {p["room"] for p in _places(sc, known=ALL)} >= {"orchard", "meadow"}
    sc["rooms"]["kitchen"]["adjacent"][0]["dir"] = "w"
    assert _places(sc, known=ALL) == []
    del sc["rooms"]["kitchen"]["adjacent"][0]["dir"]   # no bearing: no cone to place
    assert _places(sc, known=ALL) == []


def test_a_building_is_seen_and_ends_the_line_unless_the_eye_is_over_its_roof():
    sc = _valley()
    sc["rooms"]["far_barn"] = {"name": "Far Barn", "desc": ".", "exposure": "enclosed",
                               "adjacent": [{"to": "riverbank", "barrier": "wall", "dir": "w"},
                                            {"to": "beyond", "barrier": "open_door", "dir": "e"}]}
    sc["rooms"]["beyond"] = {"name": "Beyond", "desc": ".", "exposure": "open",
                             "adjacent": [{"to": "far_barn", "barrier": "open_door", "dir": "w"}]}
    sc["rooms"]["riverbank"]["adjacent"].append({"to": "far_barn", "barrier": "wall", "dir": "e"})
    rooms = {p["room"] for p in _places(sc, known=ALL)}
    assert "far_barn" in rooms and "beyond" not in rooms


# --------------------------------------------------------------------------
# By night: lights, and the side they shine from
# --------------------------------------------------------------------------

def test_a_dark_night_shows_only_what_is_lit_on_the_side_facing_the_eye():
    sc = _valley(day_phase="night", weather={"air": "clear", "moon": "none"})
    sc["rooms"]["mill"]["light"] = "lit"
    sc["rooms"]["mill"]["windows"] = ["s"]          # facing the field, toward the yard's side
    text = " ".join(_lines(sc, known=ALL))
    assert "a light" in text and "oak" not in text and "open ground" not in text
    sc["rooms"]["mill"]["windows"] = ["e"]          # in the wall facing away from the yard
    sc["rooms"]["mill"]["adjacent"] = [{"to": "mill_field", "barrier": "wall", "dir": "s"}]
    assert not any(p["lights"] for p in _places(sc, known=ALL))


# --------------------------------------------------------------------------
# Keys: one per place, stable along a walk
# --------------------------------------------------------------------------

def test_walking_along_the_path_does_not_re_announce_a_place():
    """Keyed by the place and what is seen of it, never by the way the eye
    reached it: a step along the path changes no key -- except where the
    place came into more detail (five rooms off to four), which is news."""
    def seen(sc):
        return {p.data["landscape"]["id"]: (p.dedupe_key, p.data["landscape"]["grain"])
                for p in composer.landscape_percepts(_places(sc, known=ALL))}
    sc = _valley()
    before = seen(sc)
    sc["positions"]["Ada"] = "orchard"
    after = seen(sc)
    same_grain = [k for k in set(before) & set(after) if before[k][1] == after[k][1]]
    assert same_grain and all(before[k][0] == after[k][0] for k in same_grain)
    changed = [k for k in set(before) & set(after) if before[k][1] != after[k][1]]
    assert changed and all(before[k][0] != after[k][0] for k in changed)


# --------------------------------------------------------------------------
# Added to a view, never the whole of one
# --------------------------------------------------------------------------

def test_a_far_line_never_stands_in_for_the_room():
    """A first sighting beside an unchanged roll-call: the roll-call rule and
    the empty-view floor both decide on the NEAR spans, so the far line is
    kept and the room is still re-rendered around it."""
    presence = composer.Percept(kind="presence", channel="sight", source_label="Ben",
                                fidelity="full",
                                data={"tier": "near", "known": True, "body": "b1"},
                                salience=0.35, dedupe_key="presence:b1:x")
    far = composer.landscape_percepts(_places(_valley(), known=ALL))
    view = composer.render_view([presence] + far, mode="player",
                                prev_standing={presence.dedupe_key}, language="en")
    assert "Ben" not in view.text and "you can see" in view.text
    assert composer.near_text(view) == ""


def test_japanese_says_the_same_line():
    far = composer.landscape_percepts(_places(_valley(), known={"meadow": "長い草地"}))
    text = composer.render_view(far, mode="character", language="ja").text
    assert "長い草地" in text and "東の方に" in text and "見える" in text


# --------------------------------------------------------------------------
# Memory keeps what is new
# --------------------------------------------------------------------------

def test_memory_keeps_a_far_place_once_and_never_as_the_gist_of_where_one_stood():
    env = composer.Percept(kind="environment", channel="sight", source_label="",
                           fidelity="full", data={"room_name": "The Yard"}, salience=0.2,
                           dedupe_key="environment:yard:x")
    far = composer.landscape_percepts(_places(_valley(), known={"meadow": "The Meadow"}))
    content, gist, entities = composer.render_episode([env] + far, language="en")
    assert "I could see" in content and "The Meadow" in entities
    assert "The Yard" in gist
    again, _g, _e = composer.render_episode(
        [env] + far, language="en",
        prev_standing=frozenset(p.dedupe_key for p in [env] + far))
    assert again == ""


# --------------------------------------------------------------------------
# From a height, over what stands between, on a plan
# --------------------------------------------------------------------------

def _lookout(cell):
    """A balcony on top of a three-storey tower; the tower's ground floor
    opens south onto a foot BEHIND the tower from the balcony, and west
    onto a yard beside it."""
    plan = "p"

    def room(name, exposure, x, y, elev, adjacent, w=6, d=4):
        return {"name": name, "desc": ".", "exposure": exposure, "extent": {"w": w, "d": d},
                "site": {"plan": plan, "x": x, "y": y, "elev_m": elev}, "adjacent": adjacent}
    return {"rooms": {
        "balcony": room("Balcony", "open", 0, 0, 6.0,
                        [{"to": "cabin", "barrier": "closed_door", "dir": "s"}], d=6),
        "cabin": room("Cabin", "enclosed", 0, 6, 6.0,
                      [{"to": "loft", "barrier": "open", "vertical": "down", "dir": "s"}]),
        "loft": room("Loft", "enclosed", 0, 6, 3.0,
                     [{"to": "store", "barrier": "open", "vertical": "down", "dir": "s"}]),
        "store": room("Store", "enclosed", 0, 6, 0.0,
                      [{"to": "foot", "barrier": "open_door", "dir": "s"},
                       {"to": "yard", "barrier": "open_door", "dir": "w"}]),
        "foot": room("The Foot", "open", 0, 10, 0.0,
                     [{"to": "store", "barrier": "open_door", "dir": "n"}]),
        "yard": room("The Yard", "open", -7, 6, 0.0,
                     [{"to": "store", "barrier": "open_door", "dir": "e"}])},
        "positions": {"Ren": "balcony"}, "stations": {"Ren": {"cell": list(cell)}},
        "entities": {}, "day_phase": "afternoon", "weather": {"air": "clear"}}


def test_a_height_sees_the_ground_below_over_what_stands_between():
    """From the balcony the tower's own storeys stand between the eye and
    the foot behind it, at every cell; the yard beside the tower is in plain
    view below."""
    known = {"foot": "", "yard": ""}
    for cell in ((0, 5), (2, 3), (5, 5)):
        rooms = {p["room"] for p in _places(_lookout(cell), who="Ren", known=known)}
        assert "foot" not in rooms, cell
    lines = _lines(_lookout((0, 5)), who="Ren", known=known)
    assert lines and lines[0].startswith("Below you") and "The Yard" in lines[0]


# --------------------------------------------------------------------------
# Through perception's own builder
# --------------------------------------------------------------------------

def test_the_composed_view_carries_the_far_line_and_names_its_way_out():
    """The way out is named because the near field named it in the same
    view (`_visible_openings` fills `via_names`), and the places past it by
    what this mind knows; a blind card gets none of it."""
    from agents.perception import _composer_standing_percepts
    sc = _valley()
    p = {"room": "yard", "room_name": "The Yard", "known_places": {"meadow": ""}}
    with scene_read_pass(sc):
        percepts = _composer_standing_percepts(sc, p, "Ada", [], {}, {})
    far = [q for q in percepts if composer.is_landscape(q)]
    assert far
    text = composer.render_view(percepts, mode="character", language="en").text
    assert "To the east, past The Orchard, you can see The Meadow" in text
    blind = dict(p, sense_card=[{"channel": "sight", "acuity": "blind"}])
    with scene_read_pass(sc):
        percepts = _composer_standing_percepts(sc, blind, "Ada", [], {}, {})
    assert not [q for q in percepts if composer.is_landscape(q)]


# --------------------------------------------------------------------------
# What the review of 2026-10-05 found (21 confirmed), pinned
# --------------------------------------------------------------------------

def _tower_beside_fields():
    """A roof walk on top of a two-storey tower in a field; the field south
    of the tower and a garden north of it; no site plan."""
    return {"rooms": {
        "roof": {"name": "Roof Walk", "desc": ".", "exposure": "open", "level": 2,
                 "adjacent": [{"to": "upper", "barrier": "open", "vertical": "down", "dir": "s"}]},
        "upper": {"name": "Upper Room", "desc": ".", "exposure": "enclosed", "level": 1,
                  "adjacent": [{"to": "lower", "barrier": "open", "vertical": "down", "dir": "s"}]},
        "lower": {"name": "Lower Room", "desc": ".", "exposure": "enclosed", "level": 0,
                  "adjacent": [{"to": "field", "barrier": "open_door", "dir": "s"},
                               {"to": "garden", "barrier": "open_door", "dir": "n"}]},
        "field": {"name": "The Field", "desc": ".", "exposure": "open",
                  "adjacent": [{"to": "lower", "barrier": "open_door", "dir": "n"}]},
        "garden": {"name": "The Garden", "desc": ".", "exposure": "open",
                   "adjacent": [{"to": "lower", "barrier": "open_door", "dir": "s"}]}},
        "positions": {"Ren": "roof"}, "stations": {}, "entities": {},
        "day_phase": "afternoon", "weather": {"air": "clear"}}


def test_on_top_of_a_tower_the_ground_all_round_is_below_and_beside_it_only_its_own_side():
    sc = _tower_beside_fields()
    rooms = {p["room"] for p in _places(sc, who="Ren", known=ALL)}
    assert {"field", "garden"} <= rooms                # the eye is over every roof
    sc["rooms"]["balcony"] = {"name": "Balcony", "desc": ".", "exposure": "open", "level": 1,
                              "adjacent": [{"to": "upper", "barrier": "closed_door", "dir": "n"}]}
    sc["positions"]["Ren"] = "balcony"                 # south of the tower, under its roof
    rooms = {p["room"] for p in _places(sc, who="Ren", known=ALL)}
    assert "field" in rooms and "garden" not in rooms  # the tower hides what is behind it


def test_a_cellar_under_a_trapdoor_is_no_building_standing_on_the_ground():
    sc = _valley()
    sc["rooms"]["cellar"] = {"name": "Cellar", "desc": ".", "exposure": "enclosed",
                             "adjacent": [{"to": "meadow", "barrier": "closed_door",
                                           "vertical": "up"}]}
    sc["rooms"]["meadow"]["adjacent"].append({"to": "cellar", "barrier": "closed_door",
                                               "vertical": "down"})
    assert "cellar" not in {p["room"] for p in _places(sc, known=ALL)}


def test_an_open_sided_room_shows_only_the_light_that_burns_in_it():
    sc = _valley(day_phase="night", weather={"air": "clear", "moon": "none"})
    sc["rooms"]["riverbank"]["adjacent"].append({"to": "lamp_room", "barrier": "open"})
    sc["rooms"]["lamp_room"] = {"name": "Lamp Room", "desc": ".", "exposure": "sheltered",
                                "light": "lit",
                                "adjacent": [{"to": "riverbank", "barrier": "open"}]}
    sc["entities"]["beacon"] = {"name": "the beacon", "light_source": "bright",
                                "light_radius": "room", "state": {"lit": False}}
    sc["positions"]["beacon"] = "lamp_room"
    assert not any(p["lights"] for p in _places(sc, known=ALL))
    sc["entities"]["beacon"]["state"]["lit"] = True
    assert any(p["lights"] for p in _places(sc, known=ALL))


def test_a_height_never_looks_into_another_locale():
    sc = _tower_beside_fields()
    sc["rooms"]["garden"]["locale"] = "elsewhere"
    assert "garden" not in {p["room"] for p in _places(sc, who="Ren", known=ALL)}


def test_a_building_keeps_one_key_whichever_door_the_walk_reached():
    sc = _valley()
    sc["rooms"]["mill"]["adjacent"].append({"to": "riverbank", "barrier": "closed_door", "dir": "e"})
    sc["rooms"]["riverbank"]["adjacent"].append({"to": "mill", "barrier": "closed_door", "dir": "w"})
    key_from = {}
    for here in ("yard", "orchard"):
        sc["positions"]["Ada"] = here
        for p in composer.landscape_percepts(_places(sc, known=ALL)):
            if p.data["landscape"]["ground"] == "building":
                key_from[here] = p.dedupe_key
    assert key_from["yard"] == key_from["orchard"]


def test_the_words_say_what_stands_where():
    sc = _valley(day_phase="evening", weather={"air": "clear", "moon": "full"})
    sc["rooms"]["mill"]["light"] = "lit"
    sc["rooms"]["mill"]["windows"] = ["s", "w"]
    line = _lines(sc, known={"mill": ""})[0]
    assert "a light at a building where The Mill is" in line     # never "The Mill is with a light"
    line = _lines(_valley(), known=ALL)[0]
    assert "with a great spreading oak" in line and "and on it" not in line
    assert line.count("far off") == 1
    sc = _valley()
    sc["rooms"]["meadow"]["exposure"] = "sheltered"
    sc["positions"]["Ada"] = "far_hill"
    text = " ".join(_lines(sc))
    assert "a sheltered place with a great spreading oak" in text and "roofed" not in text


def test_a_memory_of_a_view_from_above_is_the_minds_own():
    lead = composer.landscape_percepts(_places(_tower_beside_fields(), who="Ren", known=ALL))
    content, _gist, _ents = composer.render_episode(lead, language="en")
    assert content.startswith("Below me") and "Below you" not in content


def test_far_sight_trails_a_memory_and_is_its_gist_only_when_it_is_all_there_is():
    env = composer.Percept(kind="environment", channel="sight", source_label="",
                           fidelity="full", data={"room_name": "The Yard"}, salience=0.2,
                           dedupe_key="environment:yard:x")
    far = composer.landscape_percepts(_places(_valley(), known=ALL))
    content, gist, _e = composer.render_episode(far + [env], language="en")
    assert content.startswith("I was in The Yard") and gist.startswith("I was in The Yard")
    content, gist, _e = composer.render_episode(far, language="en")
    assert gist.startswith("To the east")
    for lang in ("en", "ja"):
        content, gist, _e = composer.render_episode(far + [env], language=lang)
        assert "Yard" in gist, lang


def test_an_ambient_line_has_no_episode_signature_and_a_beats_sound_is_kept():
    hiss = composer.ambient_percepts(
        [{"kind": "sound", "room": "hall", "detail": "steam hisses from a pipe"}], "hall")
    assert hiss and all(composer.episode_signature(p) == "" for p in hiss)
    content, _g, _e = composer.render_episode(hiss, language="en")
    assert "steam hisses" in content
    again, _g, _e = composer.render_episode(
        hiss, language="en", prev_standing=frozenset(p.dedupe_key for p in hiss))
    assert again == ""


def test_memory_files_only_what_the_view_shows_and_indexes_every_name_it_says():
    sc = _valley()
    sc["rooms"]["riverbank"]["anchors"] = {"elm": {"desc": "a lone elm", "dir": "n",
                                                   "height": "full", "footprint": "small"}}
    far = composer.landscape_percepts(_places(sc, known=ALL))
    view = composer.render_view(far, mode="character", language="en").text
    riverbank = [p for p in far if "elm" in str(p.data["landscape"]["big"])]
    held = frozenset(p.dedupe_key for p in far if p not in riverbank)
    content, _g, entities = composer.render_episode(far, language="en", prev_standing=held)
    assert ("elm" in view) == ("elm" in content)
    full, _g, entities = composer.render_episode(far, language="en")
    for name in ("The Meadow", "The Mill Field"):
        assert name in entities
    _c, _g, ja_entities = composer.render_episode(far, language="ja")
    assert set(ja_entities) == set(entities)
