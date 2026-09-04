"""A vehicle's inside is an inside, on both spellings, and its door follows it.

`spatial_transit` is built for exactly this -- its own docstring names "lift
cars, turbolifts, a ship, a police box" -- and all of it hangs on
`parent_entity`, with `entities[eid].interior_rooms` as the second spelling of
the same fact. For a month `sync_entity_interior_rooms` derived the second
only for BODIES, because a body's interior is the one that LEAKS when the
index is missed and widening it was a behaviour change nobody had asked for.

The cost of that scoping, measured on the live corpus: every non-body
interior in the story went unindexed, so `apply_transit_dock_edges` could move a
body's inside and never a vehicle's. Chat 114's TARDIS console room had
neither spelling and its doorway was welded to a beach in Okinawa.

The two readers UNBUILT named as the reason to wait are pinned here, because
"measured rather than feared" is the whole argument for the widening:

  * the Director's destruction-specialist gate, which already fires on a
    `kind` in (vehicle, building, structure, ship, boat) and so does not
    change at all for the holders whose kind names them;
  * the commit-side room-removal protection set, where being un-prunable is
    the behaviour an interior wants.

Database-independent: pure scene contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from world.spatial import (apply_transit_dock_edges, merge_scene_with_diff,
                           sync_entity_interior_rooms)


def _scene(kind="vehicle", at="beach", hatch="open"):
    return {
        "rooms": {
            "beach": {"name": "Shore", "light": "lit", "adjacent": []},
            "gallifrey": {"name": "Gallifrey", "light": "lit", "adjacent": []},
            "tardis_console_room": {
                "name": "Console Room", "light": "lit",
                "parent_entity": "tardis",
                "adjacent": [{"to": "beach", "barrier": "open_door"}]},
        },
        "entities": {"tardis": {
            "name": "The TARDIS", "kind": kind, "container": True,
            "interior_rooms": [], "state": {"hatch": hatch}}},
        "positions": {"tardis": at}, "stations": {},
    }


def _exterior_edges(scene):
    return [e for e in scene["rooms"]["tardis_console_room"]["adjacent"]
            if e.get("to") != "tardis_console_room"]


class TestBothSpellingsAgreeForEveryHolder:
    def test_a_vehicle_indexes_its_interior(self):
        sc = _scene()
        assert sync_entity_interior_rooms(sc) is True
        assert sc["entities"]["tardis"]["interior_rooms"] \
            == ["tardis_console_room"]

    def test_a_holder_tagged_object_indexes_it_too(self):
        """The delta the widening actually makes. A lift car tagged `object`
        is the population the corpus measurement found unindexed."""
        sc = _scene(kind="object")
        assert sync_entity_interior_rooms(sc) is True
        assert sc["entities"]["tardis"]["interior_rooms"] \
            == ["tardis_console_room"]

    def test_it_is_idempotent(self):
        sc = _scene()
        sync_entity_interior_rooms(sc)
        assert sync_entity_interior_rooms(sc) is False
        assert sc["entities"]["tardis"]["interior_rooms"] \
            == ["tardis_console_room"]

    def test_it_is_add_only(self):
        """A stale id names a room that may simply be absent this beat, and
        the list is read as a protection set at commit."""
        sc = _scene()
        sc["entities"]["tardis"]["interior_rooms"] = ["a_room_sealed_away"]
        sync_entity_interior_rooms(sc)
        assert sc["entities"]["tardis"]["interior_rooms"] == [
            "a_room_sealed_away", "tardis_console_room"]

    def test_a_holder_with_no_interior_is_untouched(self):
        sc = _scene()
        sc["rooms"]["tardis_console_room"].pop("parent_entity")
        assert sync_entity_interior_rooms(sc) is False
        assert sc["entities"]["tardis"]["interior_rooms"] == []

    def test_the_merge_derives_it(self):
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["entities"]["tardis"]["interior_rooms"] \
            == ["tardis_console_room"]


class TestTheDoorwayFollowsTheHolder:
    """What the index was blocking. `apply_transit_dock_edges` walks rooms carrying
    `parent_entity`, so this worked on the field alone -- but nothing was
    writing the field for a vehicle, and the two spellings disagreeing is how
    an interior ends up real to half the engine."""

    def test_a_docked_hold_opens_where_the_holder_stands(self):
        sc = merge_scene_with_diff(_scene(at="beach"), {})
        apply_transit_dock_edges(sc)
        assert [e["to"] for e in _exterior_edges(sc)] == ["beach"]

    def test_flying_the_holder_moves_its_doorway(self):
        """The behaviour the live TARDIS could not have: the box lands
        somewhere else and its doors open onto the new place, not the old."""
        sc = merge_scene_with_diff(_scene(at="beach"), {})
        apply_transit_dock_edges(sc)
        sc["positions"]["tardis"] = "gallifrey"
        apply_transit_dock_edges(sc)
        assert [e["to"] for e in _exterior_edges(sc)] == ["gallifrey"]

    def test_a_shut_hatch_closes_the_door_without_severing_it(self):
        sc = merge_scene_with_diff(_scene(hatch="closed"), {})
        apply_transit_dock_edges(sc)
        edges = _exterior_edges(sc)
        assert [e["to"] for e in edges] == ["beach"]
        assert edges[0]["barrier"] == "closed_door"


class TestTheTwoReadersUnbuiltNamed:
    def _destructible(self, entities):
        """`director_scopes`' gate, restated: a kind that names it, or an
        indexed interior."""
        return any(
            isinstance(e, dict) and (
                str(e.get("kind") or "").strip().casefold() in (
                    "vehicle", "building", "structure", "ship", "boat")
                or e.get("interior_rooms"))
            for e in entities.values())

    def test_a_vehicle_was_already_through_the_destruction_gate(self):
        """So indexing it changes that reader by nothing at all -- which is
        why the widening's blast radius is smaller than its list of readers
        suggests."""
        sc = _scene(kind="vehicle")
        assert self._destructible(sc["entities"]) is True
        sync_entity_interior_rooms(sc)
        assert self._destructible(sc["entities"]) is True

    def test_an_object_holder_is_where_the_gate_newly_fires(self):
        """The whole measured delta: five stories on the live corpus, all of
        them one shelter elevator tagged `object`."""
        sc = _scene(kind="object")
        assert self._destructible(sc["entities"]) is False
        sync_entity_interior_rooms(sc)
        assert self._destructible(sc["entities"]) is True

    def test_an_interior_is_protected_from_the_map_reclaiming_it(self):
        """The commit-side protection set reads this list. A room inside a
        holder is not a stray for mapping to prune while the holder stands."""
        sc = merge_scene_with_diff(_scene(), {})
        protected = set()
        for ent in sc["entities"].values():
            protected.update(str(r) for r in (ent.get("interior_rooms") or []))
        assert "tardis_console_room" in protected
