"""A view names its ways out, and what sight reaches past them.

Two subtractions the engine was making that nothing had asked for.

`world/spatial_geometry.py` mints a door pseudo-anchor for every adjacency
edge and `perception._visible_features` drops it as `implicit`, on the stated
grounds that "the exits digest already carries them" -- but that digest
(`director._egocentric_exits`) is assembled for the Director and reaches no
observer at all. The doorway was minted and thrown away, and no view in this
engine had ever named one.

`composer.presence_percepts` meanwhile grew a cross-room tier for BODIES,
because an interviewer watching through observation glass was receiving the
cell and not the woman standing in it. The PLACE never got the same lift, so
a mind could see a person through an open door and never the room they stood
in. Measured live (chat 114 turn 10): a player pushed open the doors of a
police box and looked inside, the Director minted the console room in the
same beat, and her view carried the man stepping aside and nothing whatever
of the room -- for a craft whose entire point is what you see from the
threshold.

Both are delivered here as ONE percept, because a boundary is part of a
room's standing state exactly as its furniture is. What must never follow is
a doorway that out-resolves walking through it, or a shut door that names
what is behind it -- the leak this whole layer has to avoid.

Database-independent: pure scene, percept and render contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import composer
from agents.perception import _visible_openings


def _scene(rooms, positions=None):
    return {"rooms": rooms, "entities": {}, "positions": positions or {},
            "stations": {}}


def _pair(barrier="open_door", far_light="lit", near_light="lit",
          dirs=(None, None), far_anchors=None, near_anchors=None,
          at_door=False):
    """A hall and a vault sharing one doorway, declared from both sides."""
    near = {"name": "Hall", "light": near_light, "notes": "",
            "adjacent": [{"to": "vault", "barrier": barrier,
                          "name": "the iron door"}]}
    far = {"name": "Vault", "light": far_light, "notes": "",
           "adjacent": [{"to": "hall", "barrier": barrier,
                         "name": "the iron door"}]}
    if dirs[0]:
        near["adjacent"][0]["dir"] = dirs[0]
    if dirs[1]:
        far["adjacent"][0]["dir"] = dirs[1]
    if near_anchors:
        near["anchors"] = near_anchors
    if far_anchors:
        far["anchors"] = far_anchors
    sc = _scene({"hall": near, "vault": far}, {"Ada": "hall"})
    if at_door:
        # Somebody looking through a doorway is standing at it. Off in the
        # middle of the room the line into the next one clips the wall, which
        # is the geometry working rather than the layer failing.
        sc["stations"]["Ada"] = {"at": "door:vault"}
    return sc


def _states(rows):
    return {r["desc"]: r.get("state") for r in rows}


class TestTheWayOutIsNamed:
    """A boundary is a fact about the room. It arrives whether or not sight
    crosses it, and whether or not anyone authored geometry."""

    def test_an_open_door_is_named(self):
        rows = _visible_openings(_pair(), "Ada", "hall")
        assert [r["desc"] for r in rows] == ["the iron door"]

    def test_a_shut_door_is_still_named(self):
        rows = _visible_openings(_pair(barrier="closed_door"), "Ada", "hall")
        assert _states(rows) == {"the iron door": "blind"}

    def test_a_wall_is_not_a_way_out(self):
        rows = _visible_openings(_pair(barrier="wall"), "Ada", "hall")
        assert rows == []

    def test_the_edges_own_name_beats_the_generic_phrasing(self):
        """"the iron door" is what somebody wrote; "the open doorway" is what
        the engine says when nobody did."""
        sc = _pair()
        assert _visible_openings(sc, "Ada", "hall")[0]["desc"] == "the iron door"
        sc["rooms"]["hall"]["adjacent"][0].pop("name")
        assert _visible_openings(sc, "Ada", "hall")[0]["desc"] \
            == "the open doorway"

    def test_a_room_with_no_authored_geometry_still_has_exits(self):
        """The furniture layer is opt-in because it changes an existing
        sentence. A way out is a new one, and every room has ways out."""
        sc = _pair()
        assert "anchors" not in sc["rooms"]["hall"]
        assert _visible_openings(sc, "Ada", "hall")


class TestAShutDoorNamesNothingBeyondIt:
    """The leak this layer must not open. What room lies behind a closed door
    is not a fact the observer holds."""

    def test_a_closed_door_withholds_the_room(self):
        rows = _visible_openings(_pair(barrier="closed_door"), "Ada", "hall")
        assert "room_name" not in rows[0]
        assert "Vault" not in composer._render_openings(rows)

    def test_a_membrane_withholds_the_room(self):
        rows = _visible_openings(_pair(barrier="membrane"), "Ada", "hall")
        assert "room_name" not in rows[0]

    def test_an_unlit_room_withholds_its_name(self):
        """You see what is lit. An unlit room beyond is darkness, not a
        named place. The near room is `dim` rather than `lit` because
        `effective_light` spills a LIT room's light through an open door and
        would lift the far one to dim -- borrowed light is a real rule and
        this test is not about defeating it."""
        rows = _visible_openings(
            _pair(far_light="dark", near_light="dim"), "Ada", "hall")
        assert _states(rows) == {"the iron door": "dark"}
        assert "room_name" not in rows[0]
        assert "Vault" not in composer._render_openings(rows)

    def test_darkness_goes_unremarked_when_the_observer_is_also_in_it(self):
        """A black doorway in a lit room is a thing a body sees. Standing in
        the dark yourself, every exit is dark -- saying so about each is news
        about the night, not about the room."""
        rows = _visible_openings(
            _pair(far_light="dark", near_light="dark"), "Ada", "hall")
        assert _states(rows) == {"the iron door": "bare"}
        assert "darkness" not in composer._render_openings(rows).casefold()


class TestWhatSightReachesPastIt:
    def test_a_lit_room_through_an_open_door_is_named(self):
        rows = _visible_openings(_pair(), "Ada", "hall")
        assert rows[0]["room_name"] == "Vault"
        assert "Vault" in composer._render_openings(rows)

    def test_the_far_rooms_notes_arrive_with_it(self):
        sc = _pair()
        sc["rooms"]["vault"]["notes"] = "Deeper than the hall."
        rows = _visible_openings(sc, "Ada", "hall")
        assert rows[0]["room_notes"] == "Deeper than the hall."
        assert "Deeper than the hall." in composer._render_openings(rows)

    def test_furniture_beyond_arrives_when_the_geometry_can_place_it(self):
        sc = _pair(
            dirs=("e", "w"), at_door=True,
            near_anchors={"bench": {"desc": "a low bench", "dir": "n",
                                    "height": "waist", "opacity": "opaque"}},
            far_anchors={"altar": {"desc": "a stone altar", "dir": "c",
                                   "height": "waist", "opacity": "opaque"}})
        rows = _visible_openings(sc, "Ada", "hall", sweep=True)
        assert [f["desc"] for f in rows[0].get("features") or ()] \
            == ["a stone altar"]
        assert "a stone altar" in composer._render_openings(rows)

    def test_furniture_beyond_is_absent_without_a_bearing_to_place_it(self):
        """`observer_field` lays a neighbour out from the edge's bearing. With
        none, the room is still named -- it degrades to the threshold rather
        than failing. 107 of the 185 multi-edge rooms in the live corpus carry
        no bearing at all, so a layer that required one would be dark for most
        of them."""
        sc = _pair(
            at_door=True,
            far_anchors={"altar": {"desc": "a stone altar", "dir": "c",
                                   "height": "waist", "opacity": "opaque"}})
        rows = _visible_openings(sc, "Ada", "hall", sweep=True)
        assert rows[0]["room_name"] == "Vault"
        assert "features" not in rows[0]

    def test_a_glimpse_never_claims_a_distance_it_did_not_measure(self):
        """The distance vocabulary -- close by, across the room -- is measured
        WITHIN one room. Spending it on the far side of a threshold would
        state a distance nobody took."""
        sc = _pair(
            dirs=("e", "w"), at_door=True,
            far_anchors={"altar": {"desc": "a stone altar", "dir": "c",
                                   "height": "waist", "opacity": "opaque"}})
        rendered = composer._render_openings(
            _visible_openings(sc, "Ada", "hall", sweep=True))
        assert "a stone altar" in rendered
        assert "across the room" not in rendered
        assert "close by" not in rendered

    def test_a_glance_never_out_resolves_standing_there(self):
        """The whole grain rule in one assertion: every field a glimpse
        delivers is one the room's own environment percept delivers too."""
        sc = _pair(dirs=("e", "w"), at_door=True)
        sc["rooms"]["vault"]["notes"] = "Deeper than the hall."
        row = _visible_openings(sc, "Ada", "hall", sweep=True)[0]
        assert set(row) <= {"desc", "state", "room_name", "room_notes",
                            "features"}


class TestTheBoundaryRidesTheRoomsStandingState:
    def test_a_door_that_opens_is_a_room_that_changed(self):
        """Dedupe: an unchanged doorway is furniture and re-renders as
        nothing; one that opens is news."""
        shut = composer.environment_percept(
            "hall", "Hall", "", "lit",
            openings=_visible_openings(_pair(barrier="closed_door"),
                                       "Ada", "hall"))
        open_ = composer.environment_percept(
            "hall", "Hall", "", "lit",
            openings=_visible_openings(_pair(), "Ada", "hall"))
        assert shut.dedupe_key != open_.dedupe_key

    def test_a_room_with_no_openings_composes_exactly_as_before(self):
        """Byte-identity for every story that has none: no key, no sentence,
        no change to the dedupe signature."""
        bare = composer.environment_percept("hall", "Hall", "", "lit")
        same = composer.environment_percept("hall", "Hall", "", "lit",
                                            openings=[])
        assert bare.dedupe_key == same.dedupe_key
        assert "openings" not in bare.data and "openings" not in same.data
        assert composer._render_standing(bare) == composer._render_standing(same)

    def test_the_sentence_reaches_the_rendered_view(self):
        percept = composer.environment_percept(
            "hall", "Hall", "", "lit",
            openings=_visible_openings(_pair(), "Ada", "hall"))
        assert "Vault" in composer._render_standing(percept)
