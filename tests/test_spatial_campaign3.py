"""Geometry regressions from the play campaign of 2026-09-05.

Bearings, extents and reach, from the five runs merged on `writers-room`:
`docs/experiments/PLAY_2026_09_05C_multitude.md` (PM1, PM2, PM3, PM15),
`..._rush.md` (PR11, PR13), `..._solitude.md` (PS17, PS19) and
`..._masque.md` (PX11).

Each test names the finding and the beat it was measured on, so the next
reader can see the rule was earned rather than guessed.
"""
from __future__ import annotations

from world.spatial import (
    _opening_view_cap,
    extent_clamp,
    guessed_room_sizes,
    layout_rooms,
    normalize_scene_bearings,
    proximity_rel,
    sight_passes,
    visual_level_between,
)


# ---------------------------------------------------------------------------
# PM1 / PM2 -- a vertical way out is not on a wall
# ---------------------------------------------------------------------------

def _hall_and_gallery(**over):
    """The hearing at Vaunt's Yard as turn 0 built it: a hall with a stair up
    to a gallery and the tall yard doors, both authored on the south wall."""
    scene = {
        "rooms": {
            "guild_hall": {
                "name": "the guild hall", "size": "large", "light": "lit",
                "anchors": {"factors_table": {"desc": "the long table",
                                              "dir": "n"}},
                "adjacent": [
                    {"to": "gallery", "barrier": "open", "dir": "s",
                     "vertical": "up", "name": "a narrow wooden stair"},
                    {"to": "yard", "barrier": "closed_door", "dir": "s",
                     "name": "the tall yard doors"},
                ],
            },
            "gallery": {
                "name": "the gallery", "size": "small", "light": "lit",
                "anchors": {"gallery_rail": {"desc": "a waist-high oak "
                                             "railing", "dir": "n"}},
                "adjacent": [{"to": "guild_hall", "barrier": "open"}],
            },
            "yard": {"name": "the yard",
                     "adjacent": [{"to": "guild_hall",
                                   "barrier": "closed_door"}]},
        },
        "positions": {"Ottoline Sarr": "gallery", "Maren Vaunt": "guild_hall"},
        "stations": {"Ottoline Sarr": {"at": "gallery_rail", "near": []},
                     "Maren Vaunt": {"at": "factors_table", "near": []}},
    }
    scene.update(over)
    return scene


def _edge(scene, room, to):
    return next(e for e in scene["rooms"][room]["adjacent"] if e["to"] == to)


def test_a_stair_and_a_doorway_on_one_bearing_both_keep_it():
    """PM1, multitude turn 0. The establish put the gallery stair and the
    yard doors both on `s`, one of them `vertical: up`. The collision pass
    grouped by `dir` alone, found two on `s`, and stripped the bearing from
    both edges and both reciprocals -- so the doorway that really was on
    that wall lost the one fact placing it."""
    scene = _hall_and_gallery()
    normalize_scene_bearings(scene)

    assert _edge(scene, "guild_hall", "gallery")["dir"] == "s"
    assert _edge(scene, "guild_hall", "gallery")["vertical"] == "up"
    assert _edge(scene, "guild_hall", "yard")["dir"] == "s"
    # The reciprocals the pass writes carry it too.
    assert _edge(scene, "gallery", "guild_hall")["dir"] == "n"
    assert _edge(scene, "yard", "guild_hall")["dir"] == "n"


def test_two_stairs_the_same_way_up_one_wall_still_collide():
    """The other half of PM1's rule: two verticals of the same sense on one
    bearing are the ambiguity the collision pass exists for."""
    scene = _hall_and_gallery()
    scene["rooms"]["loft"] = {"name": "the loft",
                              "adjacent": [{"to": "guild_hall",
                                            "barrier": "open"}]}
    scene["rooms"]["guild_hall"]["adjacent"].append(
        {"to": "loft", "barrier": "open", "dir": "s", "vertical": "up"})
    normalize_scene_bearings(scene)

    assert "dir" not in _edge(scene, "guild_hall", "gallery")
    assert "dir" not in _edge(scene, "guild_hall", "loft")
    # ...and the doorway that really is on that wall is untouched by their
    # quarrel, which is the whole of PM1.
    assert _edge(scene, "guild_hall", "yard")["dir"] == "s"


def test_a_gallery_sees_the_floor_it_overlooks():
    """PM2, multitude turns 10-11. Every act on the lit hall floor rendered
    "moves, too little of it to make out" beside a sentence saying lamps lit
    the room. Probed offline there was no configuration that worked: with no
    bearing the large-room branch capped at `shapes`, and with a bearing a
    body more than one sector off the axis capped at `none`."""
    scene = _hall_and_gallery()
    normalize_scene_bearings(scene)

    assert _opening_view_cap(scene, "guild_hall", "Maren Vaunt",
                             "gallery") == "full"
    assert _opening_view_cap(scene, "gallery", "Ottoline Sarr",
                             "guild_hall") == "full"
    assert visual_level_between(scene, "Ottoline Sarr", "Maren Vaunt") == "full"
    assert visual_level_between(scene, "Maren Vaunt", "Ottoline Sarr") == "full"


def test_a_body_anywhere_below_is_in_the_cone_of_an_opening_overhead():
    """The cone models a hole in a WALL. An opening in the CEILING has the
    whole floor under it, so the answer must not depend on where below the
    body stands."""
    scene = _hall_and_gallery()
    scene["rooms"]["guild_hall"]["anchors"]["benches"] = {
        "desc": "the witness benches", "dir": "e"}
    normalize_scene_bearings(scene)
    for anchor in ("factors_table", "benches"):
        scene["stations"]["Maren Vaunt"] = {"at": anchor, "near": []}
        assert visual_level_between(
            scene, "Ottoline Sarr", "Maren Vaunt") == "full"


def test_a_storey_is_not_laid_out_on_the_floor_below_it():
    """The same rule where PM1's fix would otherwise have created a new
    defect: with the bearing kept, a vertical neighbour would be embedded on
    the plane by the sight field and by the layout lint (F67 of
    DEBUG_RUN_2026_09_04). A room reached by going up is not beside you."""
    scene = _hall_and_gallery()
    normalize_scene_bearings(scene)

    assert sight_passes(scene, "guild_hall",
                        _edge(scene, "guild_hall", "gallery")) is None
    placed = layout_rooms(scene, "guild_hall")
    assert "gallery" not in placed["offsets"]
    assert not placed["collisions"]


# ---------------------------------------------------------------------------
# PM3 -- a fixture with length is not a point
# ---------------------------------------------------------------------------

def _trestle_scene(footprint=None):
    anchor = {"desc": "a long scarred trestle table set crosswise", "dir": "n"}
    if footprint:
        anchor["footprint"] = footprint
    return {
        "rooms": {"guild_hall": {
            "name": "the guild hall", "size": "large",
            "extent": {"w": 14, "d": 8},
            "anchors": {"factors_table": anchor},
            "adjacent": [],
        }},
        "positions": {"Ottoline Sarr": "guild_hall",
                      "Devereux Hallam": "guild_hall"},
        "stations": {"Ottoline Sarr": {"at": "factors_table", "near": []},
                     "Devereux Hallam": {"at": "factors_table", "near": []}},
    }


def test_two_bodies_at_one_long_table_are_not_at_each_others_ear():
    """PM3, multitude turn 2. The player leaned in and dropped her voice "so
    that it would go no further than the head of the table"; the far man's
    view carried the whisper whole and he acted on it the next beat. All
    three parties stood `at: factors_table`, so the ledger read every pair as
    within arm's reach of every other -- fourteen paces of oak collapsed to
    one point."""
    assert proximity_rel(_trestle_scene("run"),
                         "Ottoline Sarr", "Devereux Hallam") == "near"


def test_an_ordinary_fixture_still_puts_two_bodies_within_reach():
    """Pure subtraction: only a `run` has length. A hearth, a counter or a
    door is a thing two bodies stand at each other's elbow at, and every
    other footprint answers exactly what it always did."""
    for footprint in (None, "point", "small", "large"):
        assert proximity_rel(_trestle_scene(footprint),
                             "Ottoline Sarr", "Devereux Hallam") \
            == "within_reach"


def test_a_writer_saying_they_are_close_still_decides():
    """A `near` link is a positive statement somebody made about this pair.
    The run rule subtracts an ASSUMPTION, never a measurement."""
    scene = _trestle_scene("run")
    scene["stations"]["Ottoline Sarr"]["near"] = ["Devereux Hallam"]
    assert proximity_rel(scene, "Ottoline Sarr",
                         "Devereux Hallam") == "within_reach"


def test_two_bodies_placed_on_the_long_table_are_measured_not_assumed():
    """And where the map has actually PINNED them, the cell rule answers
    first and says which end of the table each one is at."""
    scene = _trestle_scene("run")
    scene["stations"]["Ottoline Sarr"]["cell"] = [1, 1]
    scene["stations"]["Devereux Hallam"]["cell"] = [12, 1]
    assert proximity_rel(scene, "Ottoline Sarr",
                         "Devereux Hallam") == "across"
    scene["stations"]["Devereux Hallam"]["cell"] = [2, 1]
    assert proximity_rel(scene, "Ottoline Sarr",
                         "Devereux Hallam") == "within_reach"


# ---------------------------------------------------------------------------
# PS17 / PS19 -- what an extent decides, and what a clamp says
# ---------------------------------------------------------------------------

def _shared_room(**room):
    scene = {"rooms": {"vault": {"name": "Deep Cistern Vault", **room}},
             "positions": {"a": "vault", "b": "vault", "c": "vault"}}
    return scene


def test_a_room_with_an_extent_is_not_a_room_of_unauthored_size():
    """PS17, solitude turns 4 and 5. One beat told the host "the extent
    decides, and the size word should agree with it"; the next told them a
    room holding three "has no authored size; perception is grading it
    'vast' by default" -- about a room carrying `extent: {w: 10, d: 14}`.
    Engine advice contradicting itself about one field in consecutive
    beats."""
    assert guessed_room_sizes(_shared_room(extent={"w": 10, "d": 14})) == []
    # A room with neither is still reported: that one really was guessed.
    rows = guessed_room_sizes(_shared_room())
    assert [r["room"] for r in rows] == ["vault"]
    # An extent the world cannot read decides nothing, so the row stands.
    assert guessed_room_sizes(_shared_room(extent="quite big"))


def test_a_clamped_extent_can_be_reported_back_to_whoever_wrote_it():
    """PS19, solitude. The Writers' Room told the host "28 paces wide by 16
    paces deep" and "32 paces wide by 18 paces deep" while the rows it had
    just written held `{w: 24, d: 16}` and `{w: 24, d: 18}` -- two
    differently-sized terraces the same width, and nothing said so."""
    note = extent_clamp({"w": 28, "d": 16})
    assert note["requested"]["w"] == 28 and note["stored"]["w"] == 24
    assert note["sides"] == ["w"]
    assert note["max"] == 24 and note["min"] == 2
    # Both sides, either way past the range.
    both = extent_clamp({"w": 32, "d": 1})
    assert both["sides"] == ["w", "d"]
    assert both["stored"] == {"w": 24, "d": 2}


def test_rounding_a_pace_is_not_a_clamp():
    """Paces are whole and nobody needs telling that 3.4 of them is 3. Only
    a measurement the ceiling moved is worth reporting."""
    assert extent_clamp({"w": 12, "d": 16}) is None
    assert extent_clamp({"width": 3.4, "depth": 11.6}) is None
    assert extent_clamp({"w": 24, "d": 2}) is None
    assert extent_clamp("a big room") is None


# ---------------------------------------------------------------------------
# PX11 -- a body's path is made of doorways it may cross
# ---------------------------------------------------------------------------

def _masque_scene():
    """The masque's ground floor: two two-hop routes from the reception room
    to the servants' passage, one through the music room's panelled door and
    one through the locked governor's study."""
    def room(name, edges):
        return {"name": name,
                "adjacent": [{"to": t, "barrier": b} for t, b in edges]}
    return {"rooms": {
        "reception_room": room("the reception room",
                               [("governors_study", "closed_door"),
                                ("music_room", "open_door")]),
        "governors_study": room("the governor's study",
                                [("reception_room", "closed_door"),
                                 ("servants_passage", "open_door")]),
        "music_room": room("the music room",
                           [("reception_room", "open_door"),
                            ("servants_passage", "closed_door")]),
        "servants_passage": room("the servants' passage", []),
    }}


def test_a_declared_walk_takes_the_least_obstructed_route():
    """PX11, masque turn 14. The walk was routed through the locked study --
    the room the whole plot turned on, which had refused the player two
    beats earlier -- because the router minimised hops and broke the tie on
    the room id. The obstacle held when it was pushed on and was walked
    through when it was not."""
    from agents.director import _door_route, declared_walk_leg

    scene = _masque_scene()
    assert _door_route(scene, "reception_room", "servants_passage") == \
        ["music_room", "servants_passage"]
    assert declared_walk_leg(scene, "reception_room", "servants_passage") == \
        ("music_room", "servants_passage", False)


def test_a_route_that_crosses_fewer_shut_doors_wins_over_a_shorter_one():
    """The general rule, one step out from the live case: fewest shut doors
    first, so a longer walk on open doorways beats a short one through two
    locked ones."""
    from agents.director import _door_route

    def room(name, edges):
        return {"name": name,
                "adjacent": [{"to": t, "barrier": b} for t, b in edges]}
    scene = {"rooms": {
        "start": room("start", [("vault", "closed_door"),
                                ("corridor", "open_door")]),
        "vault": room("vault", [("goal", "closed_door")]),
        "corridor": room("corridor", [("landing", "open_door")]),
        "landing": room("landing", [("goal", "closed_door")]),
        "goal": room("goal", []),
    }}
    assert _door_route(scene, "start", "goal") == \
        ["corridor", "landing", "goal"]


def test_a_fully_open_route_is_still_taken_whole():
    """The unchanged case: nothing shut on the way means no contest and no
    stopping short."""
    from agents.director import declared_walk_leg

    scene = _masque_scene()
    for edge in scene["rooms"]["music_room"]["adjacent"]:
        if edge["to"] == "servants_passage":
            edge["barrier"] = "open_door"
    assert declared_walk_leg(scene, "reception_room", "servants_passage") == \
        ("servants_passage", None, False)


def test_a_walk_with_no_route_at_all_is_still_a_wall():
    from agents.director import declared_walk_leg

    scene = _masque_scene()
    scene["rooms"]["balcony"] = {"name": "the balcony", "adjacent": []}
    assert declared_walk_leg(scene, "reception_room", "balcony") == \
        ("reception_room", None, True)


# ---------------------------------------------------------------------------
# PM15 -- the room a body arrives in is a room it can touch something in
# ---------------------------------------------------------------------------

class _MovingCtx:
    """The barest `PipelineContext` surface `_beat_rooms` reads."""

    def __init__(self, to_room):
        self._to_room = to_room

    def declared_movement(self):
        return {"to_room": self._to_room, "why": "the player said so"}


def test_the_contact_hand_can_name_the_room_it_is_walking_into():
    """PM15, multitude turn 10. The player moved `guild_hall -> gallery` and
    gripped the rail; the hand answered "gallery rail not in entity_names or
    anchors" while `gallery.anchors.gallery_rail` read "a waist-high oak
    railing overlooking the floor below", and the contact landed on an
    unnamed referent that composed as "something's surface"."""
    from agents.director import _anchor_names

    scene = _hall_and_gallery()
    scene["positions"]["Ottoline Sarr"] = "guild_hall"
    named = _anchor_names(scene, ["Ottoline Sarr"], _MovingCtx("gallery"))

    assert "gallery" in named
    assert named["gallery"]["gallery_rail"] == "a waist-high oak railing"
    assert "guild_hall" in named        # and the room she is leaving


def test_the_declaration_names_the_room_before_the_interpret_is_written():
    """The interpret's own specialists read the declaration, not a finished
    `director_interpret` row, so the destination has to reach them from the
    view they are handed."""
    from agents.director import _anchor_names

    scene = _hall_and_gallery()
    scene["positions"]["Ottoline Sarr"] = "guild_hall"
    view = {"declaration": {"movement": {"to_room": "gallery"}}}
    named = _anchor_names(scene, ["Ottoline Sarr"], None, view)

    assert "gallery_rail" in named.get("gallery", {})


def test_a_beat_with_no_movement_scopes_exactly_as_it_did():
    from agents.director import _anchor_names

    scene = _hall_and_gallery()
    scene["positions"]["Ottoline Sarr"] = "guild_hall"
    assert set(_anchor_names(scene, ["Ottoline Sarr"], None)) == {"guild_hall"}


# ---------------------------------------------------------------------------
# PR13 -- a planned crossing may carry its cost on the edge
# ---------------------------------------------------------------------------

def test_a_planned_edge_can_say_the_crossing_is_not_a_step():
    """PR13, rush. The Room authored the escape to Number 16 with a
    director_note about "an 18-inch void with a four-foot drop", and the
    EDGE it wrote was `{"to": "roof", "bearing": "e"}` -- no barrier, no
    vertical, nothing. A four-foot drop and an open doorway were the same
    object to the graph, and the crossing took one beat while carrying a
    child."""
    from story.plot_packages import _plan_edge

    assert _plan_edge({"to": "roof", "bearing": "e",
                       "distance": "far"})["distance"] == "far"
    # The world's own vocabulary, numbers and units included...
    assert _plan_edge({"to": "roof", "distance": "40 m"})["distance"] == "far"
    # ...and a word it cannot read is not a measurement, so it falls to the
    # default every consumer already assumed rather than reaching the graph.
    assert _plan_edge({"to": "roof", "distance": "treacherous"})["distance"] \
        == "near"
    assert "distance" not in _plan_edge({"to": "roof", "bearing": "e"})


# ---------------------------------------------------------------------------
# PR11 -- a declared walk finishes without being re-declared
# ---------------------------------------------------------------------------

def test_a_long_crossing_completes_over_the_beats_it_costs():
    """PR11, rush turns 7-13. A body climbing between two rooms held its
    narrated count at "Four -- Five -- Six" over six beats and its committed
    position never left the landing it started on.

    What the engine HAS is pinned here: a walk the player declared once is
    advanced a leg at a time by `_travel_continues`, a `far` edge costs
    `_LONG_EDGE_BEATS` and then completes, and no re-declaration is needed.
    What it does not have is the same for a body whose crossing was never a
    declared `movement` -- see `docs/UNBUILT.md`."""
    from agents.director import _still_crossing, _LONG_EDGE_BEATS

    assert _still_crossing("far", 1) is True
    assert _still_crossing("far", _LONG_EDGE_BEATS) is False
    assert _still_crossing("near", 1) is False
