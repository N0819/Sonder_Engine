"""A body interior's EXISTENCE is a derivation. Something has to mint it.

W3 built the whole consumption side of "a body that has taken another body
inside is a place" -- `place_enclosed_bodies`, the `interior_rooms` index, the
membrane enclosure default, the derived doorway, `is_sealed_in` reading the
passable-barrier set -- and shipped exactly one producer: a clause in a prompt
asking a model to author the rooms. So the road had no entrance. Measured
read-only against the author's corpus 2026-08-25, over all 80 stored scene
rows: two (chats 88, 89) carry a `mode: interior` record whose holder has zero
interior rooms, and two more (86, 87) mint that record on their very next
merge from a standing interior contact. Four scenes, four bodies standing in
their holder's own exterior room, forever.

The scene already states every fact the floor needs: that the enclosure
stands, whose inside it is, where that body is, and -- for a body -- that the
way in is opaque. `materialize_enclosure_interiors` derives the room from
those, and the card's authored stations are a richer topology laid on a floor
that never depended on anyone remembering.

THE FIVE GATES ARE THE MIGRATION STORY, each with its own test below: only
`mode: interior`, only an unambiguous holder, only a BODY (and the reason is
the firewall, not taxonomy -- see `test_a_non_body_holder_is_never_minted_for`),
only a holder the scene places, and only a holder with no interior rooms yet.
"""

from __future__ import annotations

import copy
import json

from world.spatial import (
    materialize_enclosure_interiors,
    merge_scene_with_diff,
    effective_light,
    spatial_rel_between,
)
from world.survival import is_sealed_in

OCCUPANT = "Wren"
HOLDER = "Vessel"
HOLDER_ID = "vessel_entity"
MINTED = HOLDER_ID + "_interior"
OUTSIDER = "Bystander"


def _scene(*, mode="interior", contacts=None, occupant_room="hall",
           holder_ref=HOLDER_ID, record=True, spec=None, kind="person",
           body=True, placed=True, interior_rooms=False):
    """One ordinary room, a positioned body holder with NO inside, and an
    occupant recorded as being within it.

    `holder_ref` writes the containment record against the entity id while
    `positions` is keyed by the display name -- the live shape.
    """
    rooms = {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}}
    entities = {HOLDER_ID: {"name": HOLDER, "kind": kind, "aliases": []}}
    if spec is not None:
        entities[HOLDER_ID]["interior_spec"] = spec
    if interior_rooms:
        rooms["vessel_core"] = {
            "name": "Core", "desc": "Deeper still.",
            "parent_entity": HOLDER_ID, "adjacent": [],
        }
    scene = {
        "location": "Somewhere", "time": "now",
        "rooms": rooms,
        "positions": {OCCUPANT: occupant_room, OUTSIDER: "hall"},
        "entities": entities,
        # `_is_body_entity`: a body is the thing that wears something and the
        # thing that has a size relative to its own baseline.
        "attire": {OCCUPANT: {}, OUTSIDER: {}},
        "scales": {OCCUPANT: 0.05},
        "contacts": list(contacts or []),
        "contained": {},
    }
    if body:
        scene["attire"][HOLDER] = {}
    if placed:
        scene["positions"][HOLDER] = "hall"
    if record:
        scene["contained"] = {OCCUPANT: {"in": holder_ref, "mode": mode}}
    return scene


def _interior_contact(region):
    return {
        "actor": OCCUPANT, "actor_part": "body",
        "target": HOLDER, "target_part": "torso",
        "relation": "interior", "target_interior": region,
        "manner": "enveloped",
    }


def _interiors_of(scene):
    return {rid for rid, room in (scene.get("rooms") or {}).items()
            if isinstance(room, dict)
            and room.get("parent_entity") == HOLDER_ID}


class TestTheFloor:
    def test_one_room_is_minted_and_the_occupant_stands_in_it(self):
        """The whole landing in one assertion: a record that entailed an
        inside now HAS one, in the same merge that read the record."""
        merged = merge_scene_with_diff(_scene(), {})
        assert _interiors_of(merged) == {MINTED}
        assert merged["positions"][OCCUPANT] == MINTED
        assert merged["positions"][HOLDER] == "hall"
        assert merged["contained"] == {}

    def test_the_minted_room_is_dark_prose_free_and_the_dock(self):
        """`normalize_light("") == "lit"`, so an unstated light is a lit body
        interior -- a perception lie. Stated explicitly instead. The desc is
        deliberately empty (the `materialize_planned_fringe` precedent): a
        later declaration merges description onto it by id."""
        merged = merge_scene_with_diff(_scene(), {})
        room = merged["rooms"][MINTED]
        assert room["light"] == "dark"
        assert room["desc"] == ""
        assert room["parent_entity"] == HOLDER_ID
        assert room["dock_exit"] is True
        assert effective_light(merged, MINTED) == "dark"

    def test_the_way_in_is_derived_and_opaque(self):
        """Never authored here: `sync_entity_interior_rooms` indexes the room,
        `infer_body_enclosures` defaults the body opaque, and the dock rewrite
        turns that into the edge. All three inside the SAME merge."""
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["entities"][HOLDER_ID]["interior_rooms"] == [MINTED]
        assert merged["entities"][HOLDER_ID]["enclosure"] == "membrane"
        edges = [e for e in merged["rooms"][MINTED]["adjacent"]
                 if e.get("to") == "hall"]
        assert edges and edges[0]["barrier"] == "membrane"

    def test_a_body_that_can_walk_out_is_not_suffocating(self):
        """`is_sealed_in` reads the passable-barrier set, and `membrane` is in
        it. Without the doorway derived in the same merge the end-of-merge air
        block would start a countdown on a body with a way out."""
        merged = merge_scene_with_diff(_scene(), {})
        assert is_sealed_in(merged, OCCUPANT) is False

    def test_a_shut_way_in_does_seal(self):
        merged = merge_scene_with_diff(_scene(), {})
        shut = merge_scene_with_diff(
            merged, {"entities": {HOLDER_ID: {"state": {"hatch": "closed"}}}})
        assert is_sealed_in(shut, OCCUPANT) is True

    def test_the_merge_reaches_a_fixpoint_immediately(self):
        """`dock_exit` is stamped AT MINT for this. Left to
        `apply_transit_dock_edges` to stamp on the following merge, the same
        scene serializes two different ways on consecutive empty-diff merges
        -- measured against chat 88."""
        merged = merge_scene_with_diff(_scene(), {})
        again = merge_scene_with_diff(copy.deepcopy(merged), {})
        assert json.dumps(again, sort_keys=True, default=str) == \
            json.dumps(merged, sort_keys=True, default=str)

    def test_the_pass_is_idempotent(self):
        merged = merge_scene_with_diff(_scene(), {})
        snapshot = copy.deepcopy(merged)
        assert materialize_enclosure_interiors(merged) == []
        assert merged == snapshot


class TestTheNameComesFromTheLedger:
    def test_a_standing_interior_contact_names_the_room(self):
        """The beat already wrote the region down. The region and the room are
        one fact under two names, so the engine invents no noun."""
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("the close dark")]), {})
        assert merged["rooms"][MINTED]["name"] == "the close dark"

    def test_with_no_declared_region_the_holder_names_it(self):
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["rooms"][MINTED]["name"] == "Inside %s" % HOLDER

    def test_an_overlong_region_is_capped_rather_than_dropped(self):
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("region " * 40)]), {})
        name = merged["rooms"][MINTED]["name"]
        assert 0 < len(name) <= 60
        assert name.startswith("region")

    def test_the_minted_room_answers_the_station_hint_next_merge(self):
        """W3's `_interior_station_hint` resolves a region against a room by
        NAME, so the room the floor minted is the one a later beat's contact
        routes to -- with no new code."""
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("the close dark")]), {})
        merged["positions"][OCCUPANT] = "hall"
        merged["contained"] = {OCCUPANT: {"in": HOLDER, "mode": "interior"}}
        again = merge_scene_with_diff(merged, {})
        assert again["positions"][OCCUPANT] == MINTED


class TestTheFiveGates:
    def test_carriage_modes_are_never_minted_for(self):
        """Gate 1. Cargo has no inside to stand in."""
        for mode in ("held", "carried", "pocket", "container", "riding",
                     "mounted", "worn", "inside"):
            merged = merge_scene_with_diff(_scene(mode=mode), {})
            assert _interiors_of(merged) == set(), mode
            assert merged["positions"][OCCUPANT] == "hall", mode

    def test_an_ambiguous_holder_is_no_holder(self):
        """Gate 2. The room form is keyed by entity id, so folding two beings
        into one would build an inside for the wrong body."""
        scene = _scene(holder_ref=HOLDER)
        scene["entities"]["vessel_twin"] = {
            "name": HOLDER, "kind": "person", "aliases": []}
        assert materialize_enclosure_interiors(scene) == []
        assert _interiors_of(scene) == set()

    def test_a_holder_absent_from_entities_is_untouched(self):
        """Gate 2, the other half."""
        scene = _scene(holder_ref="Nobody At All")
        assert materialize_enclosure_interiors(scene) == []
        assert _interiors_of(scene) == set()

    def test_a_non_body_holder_is_never_minted_for(self):
        """Gate 3, AND THE REASON IS THE FIREWALL, NOT TAXONOMY.
        `sync_entity_interior_rooms` and `infer_body_enclosures` are both
        body-scoped, so an interior minted for a lift car is never indexed and
        never defaulted opaque -- `apply_transit_dock_edges` would derive an
        `open_door`, and an occupant `containment_hides` was concealing becomes
        one visible from the room outside. That is information EXPANSION."""
        merged = merge_scene_with_diff(
            _scene(kind="vehicle", body=False), {})
        assert _interiors_of(merged) == set()
        assert merged["entities"][HOLDER_ID].get("enclosure") in (None, "")

    def test_a_non_body_holder_with_a_card_spec_is_still_refused(self):
        """The spec is not a licence: the gate is about what the engine can
        guarantee about the way in, not about who authored what."""
        scene = _scene(kind="vehicle", body=False,
                       spec=[{"name": "Cargo Bay"}])
        assert materialize_enclosure_interiors(scene) == []
        assert _interiors_of(scene) == set()

    def test_an_unplaced_holder_is_not_minted_for(self):
        """Gate 4. An interior that is nowhere has no exterior to travel with.

        Called directly rather than through the merge, because merge hygiene
        drops a record whose holder the scene does not place at all
        (`normalize_scene_containment`) and that rule is not this one's."""
        scene = _scene(placed=False)
        assert materialize_enclosure_interiors(scene) == []
        assert _interiors_of(scene) == set()

    def test_a_holder_that_already_has_an_inside_gains_nothing(self):
        """Gate 5. Scene topology beats the card and beats the floor."""
        merged = merge_scene_with_diff(_scene(interior_rooms=True), {})
        assert _interiors_of(merged) == {"vessel_core"}
        assert merged["positions"][OCCUPANT] == "vessel_core"

    def test_scene_rooms_beat_an_authored_spec(self):
        merged = merge_scene_with_diff(
            _scene(interior_rooms=True, spec=[{"name": "Entry Passage"}]), {})
        assert _interiors_of(merged) == {"vessel_core"}


class TestTheSecondCallSite:
    """A scene whose ONLY enclosure evidence is a standing interior CONTACT.

    `contained` is empty on disk; `derive_containment_from_contacts` mints the
    record LATE in the merge, at the second `place_enclosed_bodies` site. This
    is the live shape of chats 86 and 87, and with a producer at the first
    site alone both stories wait a whole beat for a floor the engine already
    had every fact to build.
    """

    def test_a_contact_only_enclosure_is_materialized_in_the_same_merge(self):
        scene = _scene(record=False,
                       contacts=[_interior_contact("the close dark")])
        assert scene["contained"] == {}
        merged = merge_scene_with_diff(scene, {})
        assert _interiors_of(merged) == {MINTED}
        assert merged["positions"][OCCUPANT] == MINTED
        assert merged["rooms"][MINTED]["name"] == "the close dark"
        assert merged["contained"] == {}

    def test_and_its_doorway_is_opaque_in_that_same_merge(self):
        merged = merge_scene_with_diff(
            _scene(record=False,
                   contacts=[_interior_contact("the close dark")]), {})
        edges = [e for e in merged["rooms"][MINTED]["adjacent"]
                 if e.get("to") == "hall"]
        assert edges and edges[0]["barrier"] == "membrane"
        assert is_sealed_in(merged, OCCUPANT) is False


SPEC = [
    {"name": "Entry Passage", "desc": "A close, yielding passage.",
     "light": "dark"},
    {"name": "Middle Chamber", "desc": "It widens here.", "light": "dim",
     "barrier": "membrane"},
    {"name": "Deep Hold", "desc": "The furthest the inside goes."},
]


class TestTheAuthoredTopology:
    def test_the_stations_are_minted_in_order(self):
        merged = merge_scene_with_diff(_scene(spec=SPEC), {})
        ids = [HOLDER_ID + "_entry_passage", HOLDER_ID + "_middle_chamber",
               HOLDER_ID + "_deep_hold"]
        assert _interiors_of(merged) == set(ids)
        assert [merged["rooms"][rid]["name"] for rid in ids] == [
            "Entry Passage", "Middle Chamber", "Deep Hold"]
        assert merged["rooms"][ids[1]]["desc"] == "It widens here."
        assert merged["rooms"][ids[1]]["light"] == "dim"
        # An unstated light is dark, not lit.
        assert merged["rooms"][ids[2]]["light"] == "dark"

    def test_the_chain_is_symmetric_and_the_first_station_is_the_dock(self):
        merged = merge_scene_with_diff(_scene(spec=SPEC), {})
        first = HOLDER_ID + "_entry_passage"
        second = HOLDER_ID + "_middle_chamber"
        third = HOLDER_ID + "_deep_hold"
        assert merged["rooms"][first]["dock_exit"] is True
        assert "dock_exit" not in merged["rooms"][second]
        forward = [e for e in merged["rooms"][first]["adjacent"]
                   if e.get("to") == second]
        back = [e for e in merged["rooms"][second]["adjacent"]
                if e.get("to") == first]
        assert forward and back
        assert forward[0]["barrier"] == "membrane"
        assert back[0]["barrier"] == "membrane"
        assert [e for e in merged["rooms"][third]["adjacent"]
                if e.get("to") == second]

    def test_the_occupant_stands_at_the_first_station(self):
        merged = merge_scene_with_diff(_scene(spec=SPEC), {})
        assert merged["positions"][OCCUPANT] == HOLDER_ID + "_entry_passage"

    def test_a_declared_region_routes_past_the_entry(self):
        """W3's `_interior_station_hint` doing the work unchanged: the beat
        said which region, and the mint made that region a room."""
        merged = merge_scene_with_diff(
            _scene(spec=SPEC, contacts=[_interior_contact("Middle Chamber")]),
            {})
        assert merged["positions"][OCCUPANT] == HOLDER_ID + "_middle_chamber"

    def test_a_bare_string_list_is_a_linear_tract(self):
        merged = merge_scene_with_diff(
            _scene(spec=["Entry Passage", "Deep Hold"]), {})
        assert _interiors_of(merged) == {HOLDER_ID + "_entry_passage",
                                         HOLDER_ID + "_deep_hold"}

    def test_a_nameless_station_is_dropped_and_the_rest_survive(self):
        merged = merge_scene_with_diff(
            _scene(spec=[{"name": "Entry Passage"}, {"desc": "no name"},
                         {"name": "Deep Hold"}]), {})
        assert _interiors_of(merged) == {HOLDER_ID + "_entry_passage",
                                         HOLDER_ID + "_deep_hold"}

    def test_more_stations_than_the_cap_are_truncated(self):
        merged = merge_scene_with_diff(
            _scene(spec=[{"name": "Station %d" % n} for n in range(12)]), {})
        assert len(_interiors_of(merged)) == 8

    def test_an_unreadable_passage_word_falls_to_the_stated_default(self):
        """`normalize_barrier` answers `wall` for a word it has not been
        taught, which would seal a passage the author wrote as a way through.
        Inside a body the stated default answers instead."""
        merged = merge_scene_with_diff(
            _scene(spec=[{"name": "Entry Passage"},
                         {"name": "Deep Hold", "barrier": "sphincter"}]), {})
        edges = [e for e in merged["rooms"][HOLDER_ID + "_entry_passage"]
                 ["adjacent"] if e.get("to") == HOLDER_ID + "_deep_hold"]
        assert edges and edges[0]["barrier"] == "membrane"

    def test_an_authored_interior_also_reaches_a_fixpoint(self):
        merged = merge_scene_with_diff(_scene(spec=SPEC), {})
        again = merge_scene_with_diff(copy.deepcopy(merged), {})
        assert json.dumps(again, sort_keys=True, default=str) == \
            json.dumps(merged, sort_keys=True, default=str)


class TestNothingAnyMindReceivesGrew:
    def test_the_occupant_reads_as_enclosed_from_the_room_outside(self):
        """The direction that matters. A membrane is not in the see-through
        set, so materializing an enclosure that `containment_hides` was
        already concealing adds representation, never an information claim."""
        merged = merge_scene_with_diff(_scene(), {})
        rel = spatial_rel_between(merged, OUTSIDER, OCCUPANT)
        assert rel.get("source_enclosed") is True

    def test_the_occupant_is_inside_its_holder(self):
        merged = merge_scene_with_diff(_scene(), {})
        assert spatial_rel_between(merged, OCCUPANT, HOLDER).get(
            "inside_source") is True


class TestGettingOutStillWorks:
    def test_a_declared_exit_releases_the_body_from_the_minted_room(self):
        """`release_declared_departures` is untouched by this landing, and the
        rooms the floor minted persist -- a place a body has left is still a
        place."""
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("the close dark")]), {})
        out = merge_scene_with_diff(merged, {"positions": {OCCUPANT: "hall"}})
        assert out["positions"][OCCUPANT] == "hall"
        assert out["contained"] == {}
        assert MINTED in out["rooms"]

    def test_and_nothing_mints_a_second_inside_when_they_go_back(self):
        merged = merge_scene_with_diff(_scene(), {})
        out = merge_scene_with_diff(merged, {"positions": {OCCUPANT: "hall"}})
        back = merge_scene_with_diff(
            out, {"containment": {OCCUPANT: {"in": HOLDER_ID,
                                             "mode": "interior"}}})
        assert _interiors_of(back) == {MINTED}
        assert back["positions"][OCCUPANT] == MINTED
