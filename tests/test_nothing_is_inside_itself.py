"""A thing is never inside its own interior.

THE CASE (the owner, chat 151, 2026-09-20): "The tardis followed them into the
tardis."

A thing with an interior can be CARRIED, and a carried thing's position is
derived from its holder (`derive_contained_positions`) -- so a holder who walks
into that thing's own interior takes it in with them. The police box was
recorded `held` by the Doctor (the binding defect
`causal_program.bind_items` carried until the same day), he stepped through its
doors, and `positions.the_tardis` became `tardis_console_room`: a room whose
`parent_entity` is `the_tardis`.

IT IS A PARADOX AND NOT A PREFERENCE. Every reader downstream is entitled to
assume the containment graph is acyclic: `apply_transit_dock_edges` derives a
doorway FROM the thing's exterior room, so a thing standing in its own interior
has the door derived out of the room it leads into, and `containment_chain`
would walk forever but for its own guard. `_hiding_holders` is cycle-safe
because a cycle there was already known to be possible; the POSITION graph had
no equivalent.

WHERE IT GOES IS ITS OWN DOORWAY'S ANSWER: a box whose door opens onto the
beach is on the beach. That is the same edge the dock pass already computed, so
it is a derivation rather than a guess -- and with no way out to read, the
position is dropped rather than invented, because unplaced is recoverable and a
wrong room is not.
"""

import copy
import json

import pytest

from world.spatial import (evict_self_contained_entities,
                           merge_scene_with_diff)


def _scene(**over):
    """A ship on a beach whose console room opens onto it."""
    scene = {
        "rooms": {
            "beach": {"name": "Beach", "adjacent": []},
            "console": {"name": "Console Room", "parent_entity": "ship",
                        "adjacent": [{"to": "beach", "barrier": "open_door"}]},
        },
        "positions": {"Doc": "console", "ship": "console"},
        "entities": {"ship": {"name": "The Ship", "container": True,
                              "interior_rooms": ["console"],
                              "state": {"hatch": "open"}}},
        "stations": {}, "contained": {}, "contacts": [],
    }
    scene.update(over)
    return scene


class TestTheShipGoesBackOutside:
    def test_a_thing_in_its_own_interior_is_evicted(self):
        assert evict_self_contained_entities(_scene()) == \
            [("ship", "console", "beach")]

    def test_it_goes_where_its_own_door_leads(self):
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["positions"]["ship"] == "beach"

    def test_the_body_inside_stays_inside(self):
        """The half that must not move: they DID step in, and that is correct.
        Only the thing that cannot be where it is gets moved."""
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["positions"]["Doc"] == "console"

    def test_with_no_way_out_the_position_is_dropped_not_invented(self):
        """An interior nothing has docked has no exterior to read. Unplaced is
        recoverable; a wrong room is not."""
        scene = _scene()
        scene["rooms"]["console"]["adjacent"] = []
        assert evict_self_contained_entities(scene) == [("ship", "console", "")]
        assert "ship" not in scene["positions"]

    def test_it_is_transitive(self):
        """The one-level test is the easy half: a car on a ferry's vehicle deck
        inside the car is the same error one hop out."""
        scene = {
            "rooms": {
                "quay": {"name": "Quay", "adjacent": []},
                "deck": {"name": "Vehicle Deck", "parent_entity": "ferry",
                         "adjacent": [{"to": "quay", "barrier": "open_door"}]},
                "cabin": {"name": "Car Cabin", "parent_entity": "car",
                          "adjacent": [{"to": "deck", "barrier": "open_door"}]},
            },
            "positions": {"ferry": "quay", "car": "cabin"},
            "entities": {
                "ferry": {"name": "Ferry", "interior_rooms": ["deck"],
                          "state": {"hatch": "open"}},
                "car": {"name": "Car", "interior_rooms": ["cabin"],
                        "state": {"hatch": "open"}},
            },
            "stations": {}, "contained": {}, "contacts": [],
        }
        assert evict_self_contained_entities(scene) == [("car", "cabin", "deck")]

    def test_a_thing_parked_inside_ANOTHER_thing_is_left_alone(self):
        """A car on a ferry's deck is ordinary and must not be evicted -- the
        test is the thing's OWN interior, never any interior."""
        scene = {
            "rooms": {
                "quay": {"name": "Quay", "adjacent": []},
                "deck": {"name": "Vehicle Deck", "parent_entity": "ferry",
                         "adjacent": [{"to": "quay", "barrier": "open_door"}]},
            },
            "positions": {"ferry": "quay", "car": "deck"},
            "entities": {"ferry": {"name": "Ferry", "interior_rooms": ["deck"],
                                   "state": {"hatch": "open"}},
                         "car": {"name": "Car"}},
            "stations": {}, "contained": {}, "contacts": [],
        }
        assert evict_self_contained_entities(scene) == []

    def test_an_ordinary_scene_is_untouched(self):
        scene = _scene(positions={"Doc": "beach", "ship": "beach"})
        assert evict_self_contained_entities(scene) == []
        assert scene["positions"] == {"Doc": "beach", "ship": "beach"}

    @pytest.mark.parametrize("scene", [{}, {"rooms": {}}, {"positions": {}}])
    def test_a_malformed_scene_raises_nothing(self, scene):
        assert evict_self_contained_entities(scene) == []

    def test_it_is_idempotent(self):
        scene = _scene()
        first = merge_scene_with_diff(scene, {})
        again = merge_scene_with_diff(copy.deepcopy(first), {})
        assert again["positions"]["ship"] == "beach"
        assert evict_self_contained_entities(copy.deepcopy(again)) == []


class TestARoomIsNotAdjacentToItself:
    """The same corruption one step on. With a thing inside its own interior,
    `apply_transit_dock_edges` derives the doorway FROM that interior, so the
    door comes to lead into the room it leads out of. Measured in the owner's
    scene: `tardis_console_room.adjacent` read `[{to: "tardis_console_room"}]`.
    """

    def test_a_self_edge_is_dropped(self):
        scene = _scene()
        scene["rooms"]["console"]["adjacent"] = [
            {"to": "console", "barrier": "open_door", "distance": "near"}]
        evict_self_contained_entities(scene)
        assert scene["rooms"]["console"]["adjacent"] == []

    def test_a_self_edge_is_never_a_way_out(self):
        """The eviction must not answer "it goes back into the room it is
        wrongly inside of"."""
        scene = _scene()
        scene["rooms"]["console"]["adjacent"] = [
            {"to": "console", "barrier": "open_door"}]
        assert evict_self_contained_entities(scene) == [("ship", "console", "")]
        assert "ship" not in scene["positions"]

    def test_real_edges_beside_a_self_edge_survive(self):
        scene = _scene()
        scene["rooms"]["console"]["adjacent"] = [
            {"to": "console", "barrier": "open_door"},
            {"to": "beach", "barrier": "open_door", "distance": "near"}]
        assert evict_self_contained_entities(scene) == [("ship", "console", "beach")]
        assert [e["to"] for e in scene["rooms"]["console"]["adjacent"]] == ["beach"]
