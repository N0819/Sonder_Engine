"""Being inside something and being HIDDEN by it are two facts.

`parent_entity` says where a body IS. The barrier on the interior's way out
says whether it can be SEEN. For a month those were the same question by
accident, because the spatial hand's prompt said "AN OCCUPIED BODY IS A PLACE"
and named nothing else, so `parent_entity` was in practice only ever set on
flesh -- whose interiors are joined to the world by `membrane`, which hides.

Widening that instruction to every holder (2026-09-04) ended the accident on
the same day. Measured live, chat 115 turn 1: an ordinary personnel elevator,
doors standing open onto a corridor, was correctly marked as an interior and
then SEALED its occupant away -- `visual_level_between` "none" in both
directions between two people one open door apart, so neither could see the
other, and a shout across the threshold reached its listener only over the
site's emergency PA, which was the one channel left.

The discriminator is the engine's own barrier vocabulary rather than any guess
about what the holder is made of. A holder whose inside opens on `open_door`
hides nobody; one joined by `membrane` or a shut door hides as it always did.

The opposite error is pinned too, by `test_interior_hides_its_own_exterior`:
an occupant of a TARDIS with its doors open can see out AND is still inside
it, so the police box's own exterior description must still be withheld.

Database-independent: pure scene contracts.
"""
from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from world import spatial
from world.spatial import _body_interior_holder, hiding_holders_of

_LIFT = {
    "rooms": {
        "corridor": {"name": "Corridor", "light": "lit",
                     "adjacent": [{"to": "car", "barrier": "open_door"}]},
        "car": {"name": "Lift Car", "light": "lit", "parent_entity": "lift",
                "adjacent": [{"to": "corridor", "barrier": "open_door"}]},
    },
    "positions": {"Rider": "car", "Runner": "corridor", "lift": "corridor"},
    "entities": {"lift": {"name": "Shelter Lift", "kind": "fixture",
                          "container": True, "interior_rooms": ["car"]}},
    "contained": {}, "contacts": [], "attire": {}, "overlays": {},
    "comms": {"site_pa": {"name": "Site PA", "rooms": ["corridor", "car"],
                          "carriers": [], "mode": "duplex", "live": True}},
}


def _with_barrier(barrier):
    sc = copy.deepcopy(_LIFT)
    for rid in ("corridor", "car"):
        for edge in sc["rooms"][rid]["adjacent"]:
            edge["barrier"] = barrier
    return sc


class TestAnOpenEnclosureHidesNobody:
    def test_they_can_see_each_other_through_the_open_doors(self):
        """Both rooms lit, so this is about the enclosure and nothing else --
        a dim room on either side would legitimately grade one direction to
        `shapes`, which is the light rule rather than this one."""
        sc = _with_barrier("open_door")
        assert spatial.visual_level_between(sc, "Runner", "Rider") == "full"
        assert spatial.visual_level_between(sc, "Rider", "Runner") == "full"

    def test_nothing_conceals_them_from_one_another(self):
        sc = _with_barrier("open_door")
        assert spatial.containment_conceals(sc, "Runner", "Rider") is False
        assert hiding_holders_of(sc, "Rider") == []

    def test_the_rider_is_still_inside_the_lift(self):
        """The structural half, which must NOT move: where you are is
        `parent_entity`, not the state of the door."""
        sc = _with_barrier("open_door")
        assert _body_interior_holder(sc, "Rider") == "lift"

    def test_shutting_the_doors_conceals_again(self):
        sc = _with_barrier("closed_door")
        assert hiding_holders_of(sc, "Rider") == ["lift"]
        assert spatial.visual_level_between(sc, "Runner", "Rider") == "none"

    def test_a_membrane_conceals_as_it_always_did(self):
        """The shape a body's interior is written in."""
        sc = _with_barrier("membrane")
        assert hiding_holders_of(sc, "Rider") == ["lift"]
        assert spatial.containment_conceals(sc, "Runner", "Rider") is True


class TestAChannelDoesNotCarryWhatAlreadyCarries:
    """`comms_link` already refused to tag a voice heard in the SAME room --
    "a channel exists to reach somewhere a voice does not already go". The
    rule was right and the test was too narrow: it asked whether the rooms
    were one, when the question is whether the voice already arrives."""

    def _tag(self, sc):
        link = spatial.comms_link(sc, "car", "corridor",
                                  speaker_name="Rider", observer_name="Runner")
        return (link or {}).get("name")

    def test_an_open_door_is_not_the_public_address_system(self):
        assert self._tag(_with_barrier("open_door")) is None

    def test_a_shut_door_still_needs_the_channel(self):
        assert self._tag(_with_barrier("closed_door")) == "Site PA"

    def test_a_wall_still_needs_the_channel(self):
        assert self._tag(_with_barrier("wall")) == "Site PA"

    def test_one_room_is_still_never_tagged(self):
        sc = _with_barrier("open_door")
        assert spatial.comms_link(sc, "car", "car", speaker_name="Rider",
                                  observer_name="Runner") is None


class TestAPoseFieldSpelledNone:
    """A model writing `"constraint": "none"` means the field does not apply.
    The pose composer prints `constraint` as a clause, so the string reached
    the page: "You are running, none -- lunging forward in mid-stride"
    (chat 115 t1; chat 69 carries the same shape, 2 of 105 pose records)."""

    def test_a_null_token_constraint_is_empty(self):
        from world.spatial import _clean_pose
        pose = _clean_pose({"posture": "running", "constraint": "none",
                            "detail": "lunging forward"})
        assert pose["constraint"] == ""
        assert pose["posture"] == "running"

    def test_a_real_constraint_survives(self):
        from world.spatial import _clean_pose
        assert _clean_pose({"posture": "lying", "constraint": "wrists bound"}
                           )["constraint"] == "wrists bound"

    def test_the_whole_pose_is_not_discarded(self):
        from world.spatial import _clean_pose
        assert _clean_pose({"constraint": "none"}) is None
        assert _clean_pose({"posture": "standing", "constraint": "n/a"}
                           )["posture"] == "standing"
