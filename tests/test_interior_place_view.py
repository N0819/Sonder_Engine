"""What an occupant of a body-place perceives, and what the world perceives of it.

The adversarial half of the enclosure handoff. Once `place_enclosed_bodies`
converts a carry record into a real position inside the holder, every channel
in the perception layer is answering a scene shape that nothing on main could
previously PRODUCE. The machinery under it was built and tested first --
`_body_interior_holder` reads the room form, `membrane` is outside both the
sight and the ambient barrier sets, `hiding_holders_of` walks either
expression -- so most of what is pinned here is the room form finally being
reachable rather than newly correct.

The two directions that must both hold, and the reason the file exists:

  * SUBTRACTED OUTWARD. The world does not see into the enclosure, and the
    occupant does not see out of it. Sight is symmetric here on purpose -- a
    body shut inside something can no more watch the room than the room can
    watch it, and that direction is the easier one to forget.
  * NEVER SUBTRACTED INWARD. The occupant is still told, in their own view,
    that they are inside a named body and where in it they are; the holder is
    still told what it is holding. Touch is the one channel an enclosure
    leaves open, and taking it away because the shape changed would be a mind
    concluding LESS about its own situation -- the forbidden direction.
"""

from __future__ import annotations

from world.spatial import (
    ambient_scope,
    containment_conceals,
    containment_facts,
    hiding_holders_of,
    interior_occupants,
    merge_scene_with_diff,
    spatial_rel_between,
    visible_adjacent_rooms,
)
from world.survival import is_sealed_in

OCCUPANT = "Wren"
CO_OCCUPANT = "Bly"
HOLDER = "Vessel"
HOLDER_ID = "vessel_entity"
BYSTANDER = "Corin"


def _placed(*, co_occupant=False):
    """The post-handoff shape, produced by the handoff rather than by hand."""
    scene = {
        "location": "Somewhere", "time": "now",
        "rooms": {
            "hall": {"name": "Hall", "desc": "A hall.", "adjacent": []},
            "vessel_antechamber": {
                "name": "Antechamber", "desc": "A close passage.",
                "parent_entity": HOLDER_ID,
                "adjacent": [{"to": "hall", "barrier": "open_door"}],
            },
        },
        "positions": {OCCUPANT: "hall", HOLDER: "hall", BYSTANDER: "hall"},
        "entities": {
            HOLDER_ID: {"name": HOLDER, "kind": "person", "aliases": [],
                        "interior_rooms": ["vessel_antechamber"]},
        },
        "attire": {HOLDER: {}, OCCUPANT: {}, BYSTANDER: {}},
        "scales": {OCCUPANT: 0.05},
        "contained": {OCCUPANT: {"in": HOLDER_ID, "mode": "interior"}},
        "contacts": [],
    }
    if co_occupant:
        scene["positions"][CO_OCCUPANT] = "hall"
        scene["attire"][CO_OCCUPANT] = {}
        scene["scales"][CO_OCCUPANT] = 0.05
        scene["contained"][CO_OCCUPANT] = {"in": HOLDER_ID, "mode": "interior"}
    merged = merge_scene_with_diff(scene, {})
    # The shape under test is the ROOM form and only the room form: the
    # assertions below are worth nothing if a leftover ledger record is
    # answering them.
    assert merged["contained"] == {}
    assert merged["positions"][OCCUPANT] == "vessel_antechamber"
    return merged


class TestTheRelation:
    """COMPAT PINS, and named as such so a later reader does not over-credit
    them. `spatial_rel_between` and `hiding_holders_of` already read the room
    form correctly; what changed is that a merge can now PRODUCE this shape.
    These assert the machinery still answers once something reaches it."""

    def test_the_holder_is_what_the_occupant_is_inside(self):
        sc = _placed()
        assert spatial_rel_between(sc, OCCUPANT, HOLDER).get(
            "inside_source") is True

    def test_a_body_across_the_enclosure_is_not_the_enclosure(self):
        """These were byte-identical once: the body around you and a window
        across the room returned the same relation."""
        sc = _placed()
        near = spatial_rel_between(sc, OCCUPANT, HOLDER)
        far = spatial_rel_between(sc, OCCUPANT, BYSTANDER)
        assert near != far
        assert far.get("enclosed_from_source") is True

    def test_hiding_holders_reads_the_room_form_with_no_ledger(self):
        sc = _placed()
        assert hiding_holders_of(sc, OCCUPANT) == [HOLDER_ID]


class TestSubtractedOutward:
    """COMPAT PINS likewise: `containment_conceals`, `visible_adjacent_rooms`
    and `ambient_scope` all treated `membrane` as opaque before this landing.
    The newly correct behaviour in this file is `containment_facts` and
    `interior_occupants` (below) and `is_sealed_in` (last class)."""

    def test_the_world_cannot_see_in(self):
        sc = _placed()
        assert containment_conceals(sc, BYSTANDER, OCCUPANT) is True

    def test_the_occupant_cannot_see_out(self):
        """The easier direction to forget, and the one a lenient guard grants
        for free."""
        sc = _placed()
        assert containment_conceals(sc, OCCUPANT, BYSTANDER) is True

    def test_the_holder_does_not_see_what_it_contains(self):
        """The holder is not inside its own enclosure. What it has instead of
        sight is touch."""
        sc = _placed()
        assert containment_conceals(sc, HOLDER, OCCUPANT) is True

    def test_the_exterior_room_is_not_visible_from_inside(self):
        """A membrane is walked through and never seen through, so the
        doorway out is not a view out."""
        sc = _placed()
        seen = visible_adjacent_rooms(sc, "vessel_antechamber")
        assert {r["room_id"] for r in seen} == set()
        # The same call over an ordinary open doorway does answer, so the
        # emptiness above is the membrane and not a mis-keyed read.
        assert [r["room_id"] for r in visible_adjacent_rooms(sc, "hall")] == []
        sc["rooms"]["hall"]["adjacent"] = [{"to": "yard",
                                            "barrier": "open_door"}]
        sc["rooms"]["yard"] = {"name": "Yard", "adjacent": []}
        assert [r["room_id"] for r in visible_adjacent_rooms(sc, "hall")] \
            == ["yard"]

    def test_the_interior_is_closed_to_the_world(self):
        sc = _placed()
        _rooms, open_to_world = ambient_scope(sc, "vessel_antechamber")
        assert open_to_world is False


class TestNeverSubtractedInward:
    def test_the_occupant_is_told_where_they_are(self):
        """Their own situation, in their own view. Deleting it because the
        expression changed is a mind concluding LESS."""
        facts = " ".join(containment_facts(_placed(), OCCUPANT, [HOLDER]))
        assert HOLDER in facts
        assert "Antechamber" in facts
        assert "inside" in facts.casefold()

    def test_the_occupant_is_never_handed_a_raw_entity_id(self):
        """An engine handle is not a name anybody in the fiction has heard."""
        facts = " ".join(containment_facts(_placed(), OCCUPANT, [HOLDER]))
        assert HOLDER_ID not in facts

    def test_the_holder_is_told_what_it_contains(self):
        facts = " ".join(containment_facts(_placed(), HOLDER, [OCCUPANT]))
        assert OCCUPANT in facts

    def test_interior_occupants_answers_the_place_form(self):
        sc = _placed()
        assert interior_occupants(sc, HOLDER) == [OCCUPANT]
        assert interior_occupants(sc, OCCUPANT) == []

    def test_a_bystander_is_told_nothing_about_the_inside(self):
        """The firewall subtracts: being near the holder is not being near
        what the holder contains."""
        facts = " ".join(
            containment_facts(_placed(), BYSTANDER, [HOLDER, OCCUPANT]))
        assert OCCUPANT not in facts


class TestWhatTheHolderIsToldItHolds:
    """The same two rules as the occupant's side, applied to the holder's.

    `positions` does not only key bodies. It legitimately keys objects,
    fixtures and unregistered presences BY ENTITY ID -- that is the live
    shape, and `_display_name` exists in this module because of it. The
    occupant's fact was routed through it and the holder's was not, so the
    holder's own facts could hand a mind an engine handle and call an object
    somebody who "goes where you go".
    """

    def _with_an_object_inside(self):
        sc = _placed()
        sc["entities"]["carried_lamp_7f3a"] = {
            "name": "brass lamp", "kind": "object", "aliases": [],
            "portable": True}
        sc["positions"]["carried_lamp_7f3a"] = "vessel_antechamber"
        return sc

    def test_an_object_in_the_interior_is_not_named_as_an_occupant(self):
        """An occupant of a body is a body. The enclosure vocabulary is
        body-scoped everywhere else it is asked (`infer_body_enclosures`,
        `_body_interior_holder`), and this is the one place it was not."""
        sc = self._with_an_object_inside()
        assert interior_occupants(sc, HOLDER) == [OCCUPANT]
        facts = " ".join(containment_facts(sc, HOLDER, [OCCUPANT]))
        assert "brass lamp" not in facts

    def test_the_holder_is_never_handed_a_raw_entity_id(self):
        sc = self._with_an_object_inside()
        facts = " ".join(containment_facts(sc, HOLDER, [OCCUPANT]))
        assert "carried_lamp_7f3a" not in facts

    def test_an_id_keyed_occupant_is_named_by_what_the_story_calls_them(self):
        """The same defect with a BODY in it, which is the one that reaches
        prose: a positions map keyed by entity id, and a mind told a handle."""
        sc = _placed()
        sc["entities"]["stray_bly_id"] = {
            "name": CO_OCCUPANT, "kind": "person", "aliases": []}
        sc["positions"]["stray_bly_id"] = "vessel_antechamber"
        sc["attire"][CO_OCCUPANT] = {}
        facts = " ".join(containment_facts(sc, HOLDER, [OCCUPANT]))
        assert "stray_bly_id" not in facts
        assert CO_OCCUPANT in facts


class TestCoOccupants:
    def test_two_bodies_in_one_interior_perceive_each_other(self):
        """Nothing is between them, and the wall around them is around them
        both."""
        sc = _placed(co_occupant=True)
        assert sc["positions"][CO_OCCUPANT] == "vessel_antechamber"
        assert containment_conceals(sc, OCCUPANT, CO_OCCUPANT) is False
        assert containment_conceals(sc, CO_OCCUPANT, OCCUPANT) is False

    def test_the_world_still_sees_neither(self):
        sc = _placed(co_occupant=True)
        assert containment_conceals(sc, BYSTANDER, CO_OCCUPANT) is True


class TestTheAirClock:
    def test_a_passable_membrane_is_not_a_seal(self):
        """`is_sealed_in` counted only `open`/`open_door` as a way out, which
        is a hand-written subset of the one set that answers "can a body go
        this way". A body that can walk out is not suffocating, however
        little it can see."""
        assert is_sealed_in(_placed(), OCCUPANT) is False

    def test_a_scene_with_no_vitals_table_is_untouched(self):
        """Nothing here starts a hunger or air clock by itself: the table is
        created only by an explicit write."""
        sc = _placed()
        assert "vitals" not in sc
