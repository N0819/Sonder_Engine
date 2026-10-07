"""What stands between hides what is behind it -- by height, buildings and
ground alike.

The owner, 2026-10-07, designing the mid range after a look up at a bell
loft two rooms off found nothing (scratch story 166): "we need to handle
occlusion by both landscape and buildings", and "nothing can be made out and
similar place holders are quite frustrating". Off a site plan a building only
ever ENDED a line and ground was flat; on a plan open ground hid nothing.
Now a far place shows whole, shows its top over what stands nearer, or is
hidden -- and a hidden place keeps WHAT hid it, which is what a look aimed at
it is told. Hand-made scenes; the names are illustrations, not the rule.
"""
from __future__ import annotations

from world.landscape import far_places
from world.scene_memo import scene_read_pass


def _room(name, exposure, adjacent, **more):
    return {"name": name, "desc": ".", "exposure": exposure, "adjacent": adjacent, **more}


def _storeys(scene, front, count, via_dir):
    """`count` storeys over `front`, each reached by a stair up from the one
    below: the building's height is what stands on its front room."""
    below = front
    for n in range(1, count):
        rid = f"{front}_up{n}"
        scene["rooms"][below]["adjacent"].append(
            {"to": rid, "barrier": "open", "vertical": "up", "dir": via_dir})
        scene["rooms"][rid] = _room(f"Storey {n}", "enclosed", [
            {"to": below, "barrier": "open", "vertical": "down", "dir": via_dir}], level=n)
        below = rid
    return scene


def _scene(rooms, who, where, **over):
    sc = {"rooms": rooms, "positions": {who: where}, "stations": {}, "entities": {},
          "day_phase": "afternoon", "weather": {"air": "clear"}}
    sc.update(over)
    return sc


def _places(sc, who, hidden=None):
    with scene_read_pass(sc):
        return {p["room"]: p for p in far_places(sc, who, hidden=hidden)}


# --------------------------------------------------------------------------
# Ground that rises, off a plan
# --------------------------------------------------------------------------

def _dyke(target_storeys=1):
    """A yard, a dyke a storey high, the flats beyond it, and a building
    standing on the flats -- all in a line, east."""
    rooms = {
        "yard": _room("The Yard", "open", [{"to": "dyke", "barrier": "open", "dir": "e"}]),
        "dyke": _room("The Dyke", "open", [{"to": "yard", "barrier": "open", "dir": "w"},
                                           {"to": "flats", "barrier": "open", "dir": "e"}],
                      level=1),
        "flats": _room("The Flats", "open", [{"to": "dyke", "barrier": "open", "dir": "w"},
                                             {"to": "hall", "barrier": "closed_door", "dir": "e"}]),
        "hall": _room("The Hall", "enclosed", [{"to": "flats", "barrier": "closed_door", "dir": "w"}]),
    }
    return _storeys(_scene(rooms, "Ada", "yard"), "hall", target_storeys, "e")


def test_a_dyke_hides_a_low_building_behind_it():
    hidden = []
    seen = _places(_dyke(1), "Ada", hidden=hidden)
    assert "hall" not in seen
    cover = next(h for h in hidden if h["room"] == "hall")["hidden_by"]
    assert cover["kind"] == "ground" and cover["room"] == "dyke"


def test_a_tall_building_shows_its_top_over_the_dyke():
    seen = _places(_dyke(3), "Ada")
    assert seen["hall"]["shows"] == "top" and seen["hall"]["over"] == "ground"


def test_an_eye_on_the_dyke_sees_over_it():
    sc = _dyke(1)
    sc["positions"]["Ada"] = "dyke"
    sc["rooms"]["yard"]["adjacent"] = []          # nothing behind is asked about
    seen = _places(sc, "Ada")
    assert seen["hall"]["shows"] == "whole"


# --------------------------------------------------------------------------
# The buildings in the angle of a corner, off a plan
# --------------------------------------------------------------------------

def _corner(house_dir="se", turn="e", target_storeys=1):
    """North up a lane, then the way turns (east by default) across a square
    to a chapel; a house stands at the lane's corner, on the compass the
    edge gives it."""
    rooms = {
        "yard": _room("The Yard", "open", [{"to": "lane", "barrier": "open", "dir": "n"}]),
        "lane": _room("The Lane", "open", [{"to": "yard", "barrier": "open", "dir": "s"},
                                           {"to": "square", "barrier": "open", "dir": turn}]),
        "square": _room("The Square", "open", [{"to": "lane", "barrier": "open", "dir": "w"},
                                               {"to": "chapel", "barrier": "closed_door",
                                                "dir": turn}]),
        "chapel": _room("The Chapel", "enclosed",
                        [{"to": "square", "barrier": "closed_door", "dir": "w"}]),
        "house": _room("The House", "enclosed", [{"to": "lane", "barrier": "closed_door"}]),
    }
    edge = {"to": "house", "barrier": "closed_door"}
    if house_dir:
        edge["dir"] = house_dir
    rooms["lane"]["adjacent"].append(edge)
    return _storeys(_scene(rooms, "Ada", "yard"), "chapel", target_storeys, "e")


def test_the_house_in_the_corner_hides_what_is_round_it():
    hidden = []
    seen = _places(_corner(), "Ada", hidden=hidden)
    assert "chapel" not in seen
    cover = next(h for h in hidden if h["room"] == "chapel")["hidden_by"]
    assert cover["kind"] == "building" and cover["room"] == "house"


def test_a_tower_round_the_corner_shows_over_the_roofs():
    seen = _places(_corner(target_storeys=3), "Ada")
    assert seen["chapel"]["shows"] == "top" and seen["chapel"]["over"] == "building"


def test_a_house_the_world_never_placed_hides_nothing():
    """No compass on its edge: what the world does not say stands between,
    does not."""
    assert _places(_corner(house_dir=None), "Ada")["chapel"]["shows"] == "whole"


def test_a_house_on_the_outside_of_the_corner_hides_nothing():
    assert _places(_corner(house_dir="nw"), "Ada")["chapel"]["shows"] == "whole"


def test_a_straight_way_has_no_corner():
    assert _places(_corner(turn="n"), "Ada")["chapel"]["shows"] == "whole"


# --------------------------------------------------------------------------
# On a plan: the ground of a higher open place
# --------------------------------------------------------------------------

def _ridge(elev):
    plan = "p"

    def room(name, exposure, x, elev_m, adjacent):
        return {"name": name, "desc": ".", "exposure": exposure, "extent": {"w": 10, "d": 6},
                "site": {"plan": plan, "x": x, "y": 0, "elev_m": elev_m},
                "adjacent": adjacent}
    rooms = {
        "yard": room("The Yard", "open", 0, 0.0, [{"to": "ridge", "barrier": "open", "dir": "e"}]),
        "ridge": room("The Ridge", "open", 10, elev,
                      [{"to": "yard", "barrier": "open", "dir": "w"},
                       {"to": "field", "barrier": "open", "dir": "e"}]),
        "field": room("The Field", "open", 20, 0.0,
                      [{"to": "ridge", "barrier": "open", "dir": "w"},
                       {"to": "barn", "barrier": "closed_door", "dir": "e"}]),
        "barn": room("The Barn", "enclosed", 30, 0.0,
                     [{"to": "field", "barrier": "closed_door", "dir": "w"}]),
    }
    return _scene(rooms, "Ada", "yard", stations={"Ada": {"cell": [5, 3]}})


def test_on_a_plan_a_ridge_hides_the_barn_behind_it():
    hidden = []
    seen = _places(_ridge(10.0), "Ada", hidden=hidden)
    assert "barn" not in seen
    cover = next(h for h in hidden if h["room"] == "barn")["hidden_by"]
    assert cover["kind"] == "ground" and cover["room"] == "ridge"


def test_on_a_plan_flat_ground_hides_nothing():
    assert _places(_ridge(0.0), "Ada")["barn"]["shows"] == "whole"


# --------------------------------------------------------------------------
# What else hides a far place, kept for a look
# --------------------------------------------------------------------------

def test_the_dark_is_what_hides_an_unlit_place_at_night():
    hidden = []
    seen = _places(_dyke(3) | {"day_phase": "night"}, "Ada", hidden=hidden)
    assert "hall" not in seen
    assert next(h for h in hidden if h["room"] == "hall")["hidden_by"]["kind"] == "dark"


def test_the_weather_is_what_hides_a_place_past_its_reach():
    sc = _dyke(3) | {"weather": {"air": "thick"}}
    for room in sc["rooms"].values():
        for edge in room["adjacent"]:
            if not edge.get("vertical"):
                edge["distance"] = "400 m"
        room["extent"] = {"w": 4, "d": 4}
    hidden = []
    seen = _places(sc, "Ada", hidden=hidden)
    assert "hall" not in seen
    cover = next(h for h in hidden if h["room"] == "hall")["hidden_by"]
    assert cover["kind"] == "air" and cover["air"] == "fog"


# --------------------------------------------------------------------------
# A look aimed far off is answered -- and never with a placeholder
# --------------------------------------------------------------------------

def _looked(sc, who, looks, known=None):
    from agents import composer
    from world.landscape import looked_far
    with scene_read_pass(sc):
        found = looked_far(sc, who, looks, known=known)
    return found, [p.data["desc"] for p in composer.landscape_look_percepts(found)]


def test_a_look_at_a_storey_is_a_look_at_its_building_and_is_answered():
    """Live, scratch story 166 turn 4589: a look up at the bell loft over the
    chapel, two rooms off, reached no view at all."""
    sc = _corner(house_dir=None, target_storeys=2)
    sc["rooms"]["chapel_up1"]["name"] = "the bell loft"
    found, lines = _looked(sc, "Ada", ["chapel_up1"])
    assert [f["room"] for f in found] == ["chapel"] and found[0]["place"]
    assert lines == [lines[0]] and "where the bell loft is" in lines[0], lines
    assert "two-storey building" in lines[0]


def test_a_look_at_a_hidden_place_names_what_stands_between():
    found, lines = _looked(_corner(), "Ada", ["The Chapel"])
    assert found[0]["hidden_by"]["kind"] == "building"
    assert lines == ["Toward The Chapel, the roofs nearer in stand between you and it."]
    _found, lines = _looked(_corner(), "Ada", ["chapel"], known={"house": "the cooper's house"})
    assert lines == ["Toward The Chapel, the cooper's house stands between you and it."]


def test_a_look_from_a_closed_room_meets_its_walls():
    sc = _corner()
    sc["rooms"]["cellar"] = _room("The Cellar", "enclosed",
                                  [{"to": "yard", "barrier": "closed_door", "dir": "s"}])
    sc["positions"]["Ada"] = "cellar"
    _found, lines = _looked(sc, "Ada", ["chapel"])
    assert lines == ["Toward The Chapel, the walls around you stand between you and it."]


def test_a_compass_look_finds_only_what_is_in_view():
    """North up the lane, then east twice: the chapel bears northeast. A
    compass word carries no knowledge of what is hidden that way."""
    found, _lines = _looked(_corner(target_storeys=3), "Ada", ["northeast"])
    assert "chapel" in [f["room"] for f in found], "its top shows: it is in view"
    found, _lines = _looked(_corner(), "Ada", ["northeast"])
    assert "chapel" not in [f["room"] for f in found]
    assert all(f["place"] for f in found)


def test_no_answer_is_a_placeholder():
    """The owner, 2026-10-07: "nothing can be made out and similar place
    holders are quite frustrating"."""
    import json
    from pathlib import Path
    for lang in ("en", "ja"):
        templates = json.loads(Path(f"language_packs/{lang}/cards/compositor.json")
                               .read_text(encoding="utf-8"))["templates"]
        assert "vista_unseen" not in templates
        for key in ("vista_unseen_walls", "vista_unseen_air", "vista_unseen_dark",
                    "vista_unseen_curve", "vista_unseen_nearer",
                    "far_look_hidden_building", "far_look_hidden_ground",
                    "far_look_hidden_air", "far_look_hidden_dark",
                    "far_look_hidden_walls", "far_look_hidden_around",
                    "landscape_top_over_building", "landscape_top_over_ground"):
            assert key in templates, (lang, key)
            assert "nothing can be made out" not in templates[key]


def test_the_view_composes_far_looks_as_events():
    import inspect
    from agents import perception
    source = inspect.getsource(perception)
    assert "composer.landscape_look_percepts(found)" in source
    assert 'p["own_looks"] = _own_looks(' in source


def test_a_room_that_declares_no_ground_is_seen_where_its_building_is():
    """The bell loft was planned with no exposure (scratch story 166): it sat
    off every walk, and a look at it must still find the chapel it tops."""
    sc = _corner(house_dir=None)
    sc["rooms"]["loft"] = {"name": "the bell loft", "desc": ".", "level": 1,
                           "adjacent": [{"to": "chapel", "vertical": "down"}]}
    sc["rooms"]["chapel"]["adjacent"].append({"to": "loft", "vertical": "up"})
    found, lines = _looked(sc, "Ada", ["loft"])
    assert [f["room"] for f in found] == ["chapel"] and found[0]["place"]
    assert "where the bell loft is" in lines[0]
