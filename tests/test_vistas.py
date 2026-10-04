"""Vistas: what stands on the horizon (`world/vistas.py`).

The owner, 2026-10-04: terrain "and seeing terrain in the distance like
mountains", then "go ahead". Prior art says far scenery is a view-only
layer (TADS 3 `Distant`, Skyrim's distant land) hidden by weather, night
and nearer things (Discworld MUD's terrain rooms). Hand-made scenes; the
names are illustrations, not the rule.
"""

from __future__ import annotations

import copy

from world.vistas import (air_from_weather, normalize_vista, scene_vistas,
                          visible_vistas, vista_verdict)

RANGE = {"name": "the Kurogane range", "bearing": "north", "distance_km": 30,
         "height_m": 2400, "desc": "snow on its saddle"}
TOWN = {"name": "the valley town", "bearing": "s", "distance_km": 4,
        "height_m": 0, "lit": True}


def _yard(**scene):
    sc = {"rooms": {
        "yard": {"name": "Yard", "desc": "Open ground.", "exposure": "open",
                 "extent": {"w": 10, "d": 10}, "adjacent": [
                     {"to": "hall", "barrier": "closed_door", "dir": "s"}]},
        "hall": {"name": "Hall", "desc": "A hall.", "exposure": "enclosed",
                 "extent": {"w": 6, "d": 4}, "adjacent": [
                     {"to": "yard", "barrier": "closed_door", "dir": "n"}]}},
        "entities": {}, "positions": {"Ren": "yard"},
        "vistas": [RANGE, TOWN], "day_phase": "afternoon",
        "weather": {"air": "clear"}}
    sc.update(scene)
    return sc


def _names(sc, who="Ren"):
    return [v["name"] for v, _ in visible_vistas(sc, who)]


def test_a_vista_needs_a_name_and_a_bearing():
    assert normalize_vista(RANGE)["bearing"] == "n"
    assert normalize_vista({"name": "x"}) is None
    assert normalize_vista({"bearing": "n"}) is None
    assert [v["id"] for v in scene_vistas(_yard())] == ["the_kurogane_range", "the_valley_town"]


def test_the_air_is_the_thicker_of_what_it_holds_and_what_falls():
    assert air_from_weather({"air": "thick"}) == "fog"
    assert air_from_weather({"air": "clear", "precipitation": "rain",
                             "precipitation_kind": "liquid", "intensity": "heavy"}) == "heavy_rain"
    assert air_from_weather({"air": "hazy", "precipitation": "snow",
                             "precipitation_kind": "frozen", "intensity": "heavy"}) == "heavy_snow"


def test_fog_hides_the_range_and_rain_is_gentler_than_fog():
    vista = normalize_vista(RANGE)
    assert vista_verdict(vista, air="clear") is None
    assert vista_verdict(vista, air="fog") == "air"
    near = normalize_vista(dict(RANGE, distance_km=1.5))
    assert vista_verdict(near, air="heavy_rain") is None
    assert vista_verdict(near, air="fog") == "air"


def test_open_air_sees_the_horizon_and_a_closed_room_sees_none_of_it():
    sc = _yard()
    assert _names(sc) == ["the Kurogane range", "the valley town"]
    sc["positions"]["Ren"] = "hall"
    assert _names(sc) == []


def test_a_window_shows_only_its_own_side():
    sc = _yard()
    sc["rooms"]["hall"]["adjacent"].append({"to": "yard", "barrier": "window", "dir": "s"})
    sc["rooms"]["hall"]["adjacent"] = [e for e in sc["rooms"]["hall"]["adjacent"]
                                       if e["barrier"] == "window"]
    sc["positions"]["Ren"] = "hall"
    assert _names(sc) == ["the valley town"]


def test_a_dark_night_keeps_only_what_is_lit_and_a_moon_leaves_a_silhouette():
    sc = _yard(day_phase="night", weather={"air": "clear", "moon": "none"})
    assert _names(sc) == ["the valley town"]
    sc["weather"]["moon"] = "full"
    seen = dict((v["name"], how) for v, how in visible_vistas(sc, "Ren"))
    assert seen == {"the Kurogane range": "silhouette", "the valley town": "clear"}


def test_which_way_a_body_faces_does_not_hide_the_horizon():
    """Live, Larch Hill (2026-10-04): at the south windows looking for the
    town, Ren's facing read north-west -- derived from the man beside her --
    and the lit town was withheld as behind her."""
    sc = _yard(orientation={"Ren": {"facing": "n"}})
    assert _names(sc) == ["the Kurogane range", "the valley town"]


def test_a_building_between_hides_a_low_skyline_and_not_a_peak_over_it():
    """A one-storey hall about 35 m to the north stands 2.3 degrees over the
    eye: a 150 m ridge 20 km off rises 0.35 degrees and is hidden; a 2400 m
    range 30 km off rises 4.5 degrees and is seen over the roof. Its TOP
    must clear, not its foot (prior art: a strict base test hides a range
    half behind a ridge)."""
    sc = _yard()
    sc["rooms"]["yard"].update(extent={"w": 10, "d": 50}, site={"plan": "p", "x": 0, "y": 0})
    sc["rooms"]["hall"]["site"] = {"plan": "p", "x": 2, "y": -4}
    sc["stations"] = {"Ren": {"cell": [4, 45]}}
    low = dict(RANGE, name="a low ridge", height_m=150, distance_km=20)
    sc["vistas"] = [low, RANGE]
    assert _names(sc) == ["the Kurogane range"]
    # standing right under a two-storey wall, even the range is behind it
    sc["rooms"]["upper"] = {"name": "Upper", "desc": ".", "exposure": "enclosed", "level": 1,
                            "extent": {"w": 6, "d": 4}, "adjacent": [],
                            "site": {"plan": "p", "x": 2, "y": -4}}
    sc["stations"]["Ren"]["cell"] = [4, 0]
    assert _names(sc) == []


def test_the_view_reaches_the_page_in_the_packs_own_words():
    from agents.composer import vista_percepts
    percepts = vista_percepts(visible_vistas(_yard(), "Ren"))
    texts = [p.data["desc"] for p in percepts]
    assert texts[0] == "To the north, the Kurogane range: snow on its saddle."
    assert all(p.kind == "ambient" and p.channel == "sight" for p in percepts)


def test_the_director_is_shown_the_horizon():
    from agents.director import causal_world_index
    index = causal_world_index(_yard())
    assert [v["name"] for v in index["vistas"]] == ["the Kurogane range", "the valley town"]


def test_the_writers_room_sets_the_horizon(temp_db):
    from story.plot_packages import OPERATIONS
    import json
    import time
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Shrine", "", time.time()))
    temp_db.wset(cid, "scene", {"rooms": {}, "positions": {}})
    shaped = OPERATIONS["set_vistas"]["shape"]({"vistas": [RANGE, {"name": "nothing"}]})
    assert [v["name"] for v in shaped["vistas"]] == ["the Kurogane range"]
    OPERATIONS["set_vistas"]["apply"](cid, None, shaped, 0)
    OPERATIONS["set_vistas"]["apply"](cid, None, OPERATIONS["set_vistas"]["shape"](
        {"vistas": [dict(RANGE, desc="cloud on the peaks")]}), 0)
    scene = temp_db.wget(cid, "scene")
    assert [v["desc"] for v in scene["vistas"]] == ["cloud on the peaks"]


def test_a_glassed_room_sees_out_its_own_windows_and_no_other_way():
    """A watch cabin glassed on its north side over open air, with no room
    beyond the glass: live, the Larch Hill opening built a 'glassed-in
    watch cabin' whose only edges were a stair and a shut balcony door, so
    nothing on the horizon could ever be seen from it (2026-10-04)."""
    sc = _yard()
    sc["rooms"]["cabin"] = {"name": "Cabin", "desc": ".", "exposure": "enclosed",
                            "windows": ["n"], "adjacent": []}
    sc["positions"]["Ren"] = "cabin"
    assert _names(sc) == ["the Kurogane range"]


def test_the_schema_keeps_a_rooms_windows():
    from llm.schemas import RoomDef
    room = RoomDef(name="Cabin", desc=".", windows=["n", "e"])
    dumped = room.model_dump(exclude_none=True) if hasattr(room, "model_dump") else room.dict(exclude_none=True)
    assert dumped["windows"] == ["n", "e"]



def test_the_storeys_over_a_kitchen_are_its_ceiling_not_a_wall_before_its_window():
    """Live, Larch Hill (2026-10-04): the rooms stacked over the kitchen were
    read as a column standing in front of its south window, at 87 degrees."""
    sc = _yard()
    sc["rooms"]["yard"].update(extent={"w": 8, "d": 8}, site={"plan": "p", "x": 0, "y": 4})
    sc["rooms"]["hall"].update(extent={"w": 4, "d": 4}, windows=["s"],
                               site={"plan": "p", "x": 2, "y": 0})
    sc["rooms"]["hall"]["adjacent"] = []
    sc["rooms"]["loft"] = {"name": "Loft", "desc": ".", "exposure": "enclosed", "level": 1,
                           "extent": {"w": 4, "d": 4}, "adjacent": [],
                           "site": {"plan": "p", "x": 2, "y": 0}}
    sc["positions"]["Ren"] = "hall"
    assert _names(sc) == ["the valley town"]
