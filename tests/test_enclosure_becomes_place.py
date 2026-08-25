"""A body that has taken another body inside is a PLACE, and its inside is rooms.

THE THIRD PATH. The engine has always had two accounts of one body being
within another. The `contained` ledger is one: the occupant has no place of
their own and derives their holder's, every merge. A room whose
`parent_entity` is the holder is the other: the occupant stands somewhere,
and that somewhere travels with the body around it. Every consequence of the
second was built and tested long before this file existed -- the doorway is
derived from the holder's own state, `membrane` is opaque open or shut,
ambient scope stops at the boundary, the composer renders the inside like any
room. What did not exist was the ROUTE from the first into the second.

Measured, chat 88, fifteen consecutive audited turns: the holder entity
carried `interior_rooms: []` and `container: false`; `scene.rooms` held ONE
room with `adjacent: []`; `scene.positions` put BOTH bodies in it; the whole
interior was four free-text keys on the entity blob that no spatial query
reads; and `world.engine_notices` for the latest turn was literally
`["spatial specialist: not_mine"]`. The occupant's composed view ran four
sentences, because there was no room to compose.

The conversion here is deterministic and CONDITIONAL. Existence of the place
is not a judgment -- `mode: interior` plus a holder that HAS interior rooms is
a body standing in one of them. Topology is authored content and stays with
the producer that owns it. A holder with no interior rooms is left exactly as
it was, which is the entire migration story for every scene already on disk.
"""

from __future__ import annotations

import copy

from world.spatial import (
    merge_scene_with_diff,
    place_enclosed_bodies,
    spatial_rel_between,
)

OCCUPANT = "Wren"
HOLDER = "Vessel"
HOLDER_ID = "vessel_entity"


def _scene(*, interior=True, mode="interior", contacts=None,
           occupant_room="hall", holder_ref=HOLDER_ID):
    """One ordinary room, a positioned body-holder, and an occupant recorded
    as being inside it.

    `holder_ref` writes the containment record against the entity ID while
    `positions` is keyed by the display name -- the live shape, and the one
    that has produced five separate defects from a single `==`.
    """
    rooms = {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}}
    entities = {
        HOLDER_ID: {"name": HOLDER, "kind": "person", "aliases": [],
                    "interior_rooms": []},
    }
    if interior:
        rooms["vessel_throat"] = {
            "name": "Throat", "desc": "A close passage.",
            "parent_entity": HOLDER_ID,
            "adjacent": [{"to": "hall", "barrier": "open_door"}],
        }
        rooms["vessel_core"] = {
            "name": "Core", "desc": "Deeper still.",
            "parent_entity": HOLDER_ID,
            "adjacent": [{"to": "vessel_throat", "barrier": "membrane"}],
        }
        entities[HOLDER_ID]["interior_rooms"] = ["vessel_throat", "vessel_core"]
    scene = {
        "location": "Somewhere", "time": "now",
        "rooms": rooms,
        "positions": {OCCUPANT: occupant_room, HOLDER: "hall"},
        "entities": entities,
        # `_is_body_entity`: bodies are the things that wear something and the
        # things that have a size relative to their own baseline.
        "attire": {HOLDER: {}, OCCUPANT: {}},
        "scales": {OCCUPANT: 0.05},
        "contained": {OCCUPANT: {"in": holder_ref, "mode": mode}},
        "contacts": list(contacts or []),
    }
    return scene


def _interior_contact(station):
    return {
        "actor": OCCUPANT, "actor_part": "body",
        "target": HOLDER, "target_part": "torso",
        "relation": "interior", "target_interior": station,
        "manner": "enveloped",
    }


class TestTheHandoff:
    def test_the_occupant_is_placed_at_the_entry_room(self):
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["positions"][OCCUPANT] == "vessel_throat"
        assert merged["contained"] == {}

    def test_the_place_is_not_the_holders_own_room(self):
        """The measured baseline in one assertion: both bodies in one room."""
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["positions"][HOLDER] == "hall"
        assert merged["positions"][OCCUPANT] != merged["positions"][HOLDER]

    def test_a_standing_interior_contact_names_the_station(self):
        """`target_interior` and the interior room are one fact under two
        names, so the ledger the beat already wrote decides WHERE inside."""
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("Core")]), {})
        assert merged["positions"][OCCUPANT] == "vessel_core"

    def test_the_station_hint_matches_the_room_key_too(self):
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("vessel_core")]), {})
        assert merged["positions"][OCCUPANT] == "vessel_core"

    def test_an_unresolvable_station_falls_back_to_the_entry(self):
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("somewhere unnamed")]), {})
        assert merged["positions"][OCCUPANT] == "vessel_throat"

    def test_the_record_is_resolved_through_entity_identity(self):
        """The record names the entity id; positions are keyed by the display
        name. Spelling equality has never been enough here."""
        merged = merge_scene_with_diff(_scene(holder_ref=HOLDER), {})
        assert merged["positions"][OCCUPANT] == "vessel_throat"
        assert merged["contained"] == {}

    def test_the_relation_becomes_inside_source(self):
        merged = merge_scene_with_diff(_scene(), {})
        rel = spatial_rel_between(merged, OCCUPANT, HOLDER)
        assert rel.get("inside_source") is True


class TestWhatIsNeverConverted:
    def test_a_holder_with_no_interior_is_untouched(self):
        """THE MIGRATION FLOOR, and it PASSES ON MAIN -- a no-regression pin,
        not a reproduction. Every stored scene holds contained-but-not-placed
        bodies; nothing about them may move until an interior exists."""
        before = merge_scene_with_diff(_scene(interior=False), {})
        # `in` reads as the display name because `normalize_scene_subjects`
        # folds every subject-keyed ledger onto the entity's own name -- that
        # is the standing merge behaviour, and this pin includes it verbatim
        # so a later change to it cannot hide behind this file.
        assert before["contained"] == {OCCUPANT: {"in": HOLDER,
                                                  "mode": "interior"}}
        assert before["positions"][OCCUPANT] == "hall"
        assert before["positions"][HOLDER] == "hall"

    def test_carriage_modes_are_never_placed(self):
        """Cargo has no inside to stand in. `interior` is the one mode
        CONTAINMENT_MODES documents as a body within a body's own interior."""
        for mode in ("pocket", "held", "carried", "container", "riding"):
            merged = merge_scene_with_diff(_scene(mode=mode), {})
            assert merged["contained"].get(OCCUPANT, {}).get("mode") == mode, mode
            assert merged["positions"][OCCUPANT] == "hall", mode

    def test_an_unplaced_holder_is_not_converted(self):
        """An interior that is nowhere has no exterior to travel with, so the
        ledger entry -- which at least says who holds whom -- is left standing.

        Called directly rather than through the merge, because merge hygiene
        drops a record whose holder the scene does not place at all
        (`normalize_scene_containment`), and that rule is not this one's."""
        scene = _scene()
        scene["positions"].pop(HOLDER)
        assert place_enclosed_bodies(scene) == []
        assert OCCUPANT in scene["contained"]
        assert scene["positions"][OCCUPANT] == "hall"


class TestOneTruth:
    def test_a_redundant_record_beside_a_real_position_is_dropped(self):
        """A body cannot be both standing inside and carried by the same
        holder. Leaving both lets the carry derivation drag them back out."""
        scene = _scene(occupant_room="vessel_core")
        merged = merge_scene_with_diff(scene, {})
        assert merged["contained"] == {}
        assert merged["positions"][OCCUPANT] == "vessel_core"

    def test_idempotent(self):
        merged = merge_scene_with_diff(_scene(), {})
        snapshot = copy.deepcopy(merged)
        assert place_enclosed_bodies(merged) == []
        assert merged == snapshot

    def test_getting_out_is_an_ordinary_relocation(self):
        """Nothing re-contains. Once placed, walking out is a position write
        like any other -- the carry ledger is no longer holding the leash."""
        merged = merge_scene_with_diff(_scene(), {})
        out = merge_scene_with_diff(merged, {"positions": {OCCUPANT: "hall"}})
        assert out["positions"][OCCUPANT] == "hall"
        assert out["contained"] == {}
        assert spatial_rel_between(out, OCCUPANT, HOLDER).get(
            "inside_source") is not True


class TestTheIndexAndTheOpacity:
    def test_a_parented_room_indexes_itself_on_its_entity(self):
        """One fact written twice, and only one spelling was ever derived.
        The half that missed it includes the one function that makes a body's
        inside opaque by default."""
        scene = _scene()
        scene["entities"][HOLDER_ID].pop("interior_rooms")
        merged = merge_scene_with_diff(scene, {})
        assert set(merged["entities"][HOLDER_ID]["interior_rooms"]) == {
            "vessel_throat", "vessel_core"}

    def test_an_unindexed_body_interior_still_defaults_to_membrane(self):
        """A leak OUTWARD if it does not: the room outside looks straight in."""
        scene = _scene()
        scene["entities"][HOLDER_ID]["interior_rooms"] = []
        merged = merge_scene_with_diff(scene, {})
        assert merged["entities"][HOLDER_ID].get("enclosure") == "membrane"
        edge = [e for e in merged["rooms"]["vessel_throat"]["adjacent"]
                if e.get("to") == "hall"]
        assert edge and edge[0]["barrier"] == "membrane"

    def test_a_vehicle_interior_keeps_its_see_through_doorway(self):
        """Scoped to bodies. A lift car is not a mass and its open hatch is
        an open hatch."""
        scene = _scene()
        scene["attire"].pop(HOLDER)
        scene["entities"][HOLDER_ID]["kind"] = "vehicle"
        merged = merge_scene_with_diff(scene, {})
        assert merged["entities"][HOLDER_ID].get("enclosure") in (None, "")
