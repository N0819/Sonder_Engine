"""What the walls give back.

The owner (2026-09-15): "quieter spaces should allow for some pretty long
reaching echoes like an abandoned building." A room's `surface` sets its
absorption; a bare room's reverberant field is added to the direct one
(`spatial_sound_field.room_reverberation`), it leaks through the room's
openings, it smears words when it dominates, it takes the direction off a
sound from beyond, and a long bare room gives a sharp sound back. A body's
tread is a source, and it crosses a floor as impact."""
from __future__ import annotations

from world.spatial import (ECHO_SPAN_PACES, FLOOR_IMPACT_DB, TREAD_LEVEL, TREAD_RUN_DB,
                           hear_level, room_reverberation, sound_bearing_via,
                           spatial_rel_between, tread_events)
from world.spatial import distant_sounds, normalize_sensory_event


def _chain(n, surface=None, extent=10, quiet=None):
    rooms = {}
    for i in range(n):
        adj = []
        if i > 0:
            adj.append({"to": f"r{i-1}", "barrier": "open_door", "dir": "w"})
        if i < n - 1:
            adj.append({"to": f"r{i+1}", "barrier": "open_door", "dir": "e"})
        r = {"name": f"r{i}", "extent": {"w": extent, "d": 6}, "anchors": {},
             "adjacent": adj, "exposure": "enclosed"}
        if surface:
            r["surface"] = surface
        if quiet:
            r["quiet"] = quiet
        rooms[f"r{i}"] = r
    return rooms


def _reach(volume, surface=None, quiet=None):
    for k in range(1, 8):
        sc = {"rooms": _chain(8, surface, quiet=quiet),
              "positions": {"A": "r0", "B": f"r{k}"},
              "stations": {"A": {"cell": [5, 3]}, "B": {"cell": [5, 3]}}, "entities": {}}
        if hear_level(spatial_rel_between(sc, "B", "A"), volume) == "none":
            return k - 1
    return 7


def test_a_plain_room_does_not_ring_and_a_bare_one_does():
    sc = {"rooms": {"hall": {"name": "hall", "extent": {"w": 20, "d": 20}, "anchors": {}, "adjacent": []},
                    "cell": {"name": "cell", "extent": {"w": 6, "d": 6}, "anchors": {}, "adjacent": [],
                             "surface": "bare"}}}
    assert room_reverberation(sc, "hall") is None
    sc["rooms"]["hall"]["surface"] = "bare"
    hall = room_reverberation(sc, "hall")
    assert hall["rt60"] >= 2.0 and hall["word"] == "cavernous" and hall["echo"]
    cell = room_reverberation(sc, "cell")
    assert cell["gain_db"] > 0 and not cell["echo"], cell
    sc["rooms"]["hall"]["surface"] = "furnished"
    assert room_reverberation(sc, "hall") is None, "an ordinary room keeps today's model"


def test_a_voice_carries_further_through_bare_rooms():
    assert _reach("normal", "bare") > _reach("normal"), (_reach("normal", "bare"), _reach("normal"))
    assert _reach("whisper", "bare", quiet="dead") >= _reach("whisper", quiet="dead")


def test_the_ring_smears_a_shout_across_a_bare_hall():
    def hall(surface):
        rooms = {"hall": {"name": "hall", "extent": {"w": 24, "d": 12}, "anchors": {}, "adjacent": [],
                          "exposure": "enclosed"}}
        if surface:
            rooms["hall"]["surface"] = surface
        return {"rooms": rooms, "positions": {"A": "hall", "B": "hall"},
                "stations": {"A": {"cell": [1, 6]}, "B": {"cell": [22, 6]}}, "entities": {}}
    plain = spatial_rel_between(hall(None), "B", "A")
    bare = spatial_rel_between(hall("bare"), "B", "A")
    assert hear_level(plain, "shout") == "full"
    assert bare.get("reverberant") is True
    assert hear_level(bare, "shout") == "fragment", "the words smear in the ring"


def test_in_a_bare_room_a_sound_from_beyond_comes_from_everywhere():
    sc = {"rooms": _chain(2, "bare"), "positions": {"A": "r0", "B": "r1"},
          "stations": {"A": {"cell": [5, 3]}, "B": {"cell": [5, 3]}}, "entities": {},
          "orientation": {"B": {"facing": "n"}}}
    rec = sound_bearing_via(sc, "B", "r0", room="r1")
    assert rec and rec.get("reverberant") and "walls" in rec["phrase"]
    plain = {**sc, "rooms": _chain(2)}
    rec = sound_bearing_via(plain, "B", "r0", room="r1")
    assert rec and not rec.get("reverberant")


def test_a_tread_is_heard_in_its_room_and_through_a_timber_floor():
    rooms = {
        "parlour": {"name": "Parlour", "extent": {"w": 8, "d": 8}, "anchors": {}, "adjacent": [],
                    "exposure": "enclosed"},
        "bedroom": {"name": "Bedroom", "extent": {"w": 8, "d": 8}, "anchors": {}, "adjacent": [],
                    "exposure": "enclosed", "over": ["parlour"], "floor": "timber"},
        "cellar": {"name": "Cellar", "extent": {"w": 8, "d": 8}, "anchors": {}, "adjacent": [],
                   "exposure": "enclosed"}}
    rooms["parlour"]["over"] = ["cellar"]
    rooms["parlour"]["floor"] = "stone"
    sc = {"rooms": rooms, "positions": {"Ware": "bedroom", "Nell": "parlour", "Cook": "cellar"},
          "stations": {"Ware": {"cell": [4, 4]}, "Nell": {"cell": [4, 4]}, "Cook": {"cell": [4, 4]}},
          "entities": {}}
    events = tread_events(sc, {"Ware": "run"})
    assert [e["room"] for e in events] == ["bedroom", "parlour"]
    own, below = events
    assert own["level"] == TREAD_LEVEL["run"] and own["source"] == "Ware" and own["tread"]
    assert below["db"] == FLOOR_IMPACT_DB["timber"] + TREAD_RUN_DB
    assert below["detail"] == "running footsteps overhead"
    kept = normalize_sensory_event(below, rooms)
    assert kept and kept.get("tread") and kept["detail"] == below["detail"]
    # The parlour hears it where it is (the composer's ambient percept);
    # the cellar, a stone floor further down, hears it by the far flood or
    # not at all -- and here not at all: the run is not on the cellar's
    # own floor, and a stone floor over the cellar carries no tread.
    assert distant_sounds(sc, "Cook", room="cellar", events=events) == []
    walked = tread_events(sc, {"Nell": "walk"})
    assert [e["room"] for e in walked] == ["parlour", "cellar"]
    assert walked[1]["db"] == FLOOR_IMPACT_DB["stone"]


def test_a_long_bare_room_gives_a_sharp_sound_back():
    rooms = {"nave": {"name": "nave", "extent": {"w": ECHO_SPAN_PACES + 4, "d": 8}, "anchors": {},
                      "adjacent": [], "surface": "bare"},
             "vestry": {"name": "vestry", "extent": {"w": 6, "d": 6}, "anchors": {}, "adjacent": [],
                        "surface": "bare"}}
    assert normalize_sensory_event({"room": "nave", "level": "loud", "detail": "a door slams"}, rooms).get("echo")
    assert not normalize_sensory_event({"room": "vestry", "level": "loud", "detail": "a door slams"}, rooms).get("echo")


def test_the_page_hears_footfalls_overhead_and_the_place_giving_a_sound_back():
    from agents import composer
    rooms = {"parlour": {"name": "Parlour", "extent": {"w": 8, "d": 8}, "anchors": {}, "adjacent": []},
             "bedroom": {"name": "Bedroom", "extent": {"w": 8, "d": 8}, "anchors": {}, "adjacent": [],
                         "over": ["parlour"], "floor": "timber"},
             "nave": {"name": "nave", "extent": {"w": ECHO_SPAN_PACES + 4, "d": 8}, "anchors": {},
                      "adjacent": [], "surface": "bare"}}
    sc = {"rooms": rooms, "positions": {"Ware": "bedroom"}, "stations": {"Ware": {"cell": [4, 4]}},
          "entities": {}}
    below = [normalize_sensory_event(e, rooms) for e in tread_events(sc, {"Ware": "walk"})][1]
    heard = composer.ambient_percepts([dict(below, desc=below["detail"])], "parlour", order_key=0)
    assert heard and heard[0].data["desc"] == "footsteps overhead"
    slam = normalize_sensory_event({"room": "nave", "level": "loud", "detail": "A door slams."}, rooms)
    heard = composer.ambient_percepts([dict(slam, desc=slam["detail"])], "nave", order_key=0)
    assert heard[0].data["desc"].endswith("and the place gives it back")
