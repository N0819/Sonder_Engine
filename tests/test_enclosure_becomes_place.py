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
a body standing in one of them.

THE MIGRATION SENTENCE THAT USED TO END THIS DOCSTRING IS GONE, deliberately.
It said a holder with no interior rooms is left exactly as it was, "which is
the entire migration story for every scene already on disk" -- true while the
only producer of interior rooms was a clause in a prompt, and the reason this
whole feature never fired: measured over the author's 80 stored scene rows,
FOUR carried a standing `mode: interior` record over a holder with no inside,
and every one of them left a body in its holder's own exterior room forever.
`materialize_enclosure_interiors` mints that inside now, at both merge sites,
so existence has a deterministic floor and the card supplies the richer
topology on top of it. The never-converted class survives as five gates, each
with its own test in `tests/test_interior_materialization.py`; the ledger form
(`mode: "inside"`) and every carriage mode are held by the neighbouring tests
here and by `tests/test_body_enclosure_channels.py`, both unmodified.
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
        rooms["vessel_antechamber"] = {
            "name": "Antechamber", "desc": "A close passage.",
            "parent_entity": HOLDER_ID,
            "adjacent": [{"to": "hall", "barrier": "open_door"}],
        }
        rooms["vessel_core"] = {
            "name": "Core", "desc": "Deeper still.",
            "parent_entity": HOLDER_ID,
            "adjacent": [{"to": "vessel_antechamber", "barrier": "membrane"}],
        }
        entities[HOLDER_ID]["interior_rooms"] = ["vessel_antechamber", "vessel_core"]
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
        assert merged["positions"][OCCUPANT] == "vessel_antechamber"
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
        assert merged["positions"][OCCUPANT] == "vessel_antechamber"

    def test_two_disagreeing_stations_answer_by_a_stated_rule(self):
        """Two standing interior rows naming different stations is the ledger
        disagreeing with itself, and nothing in the scene decides which is
        right. The first row listed wins -- an answer, not an artefact of
        where in a list a row happened to land."""
        merged = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("Antechamber"),
                             _interior_contact("Core")]), {})
        assert merged["positions"][OCCUPANT] == "vessel_antechamber"

    def test_the_record_is_resolved_through_entity_identity(self):
        """The record names the entity id; positions are keyed by the display
        name. Spelling equality has never been enough here."""
        merged = merge_scene_with_diff(_scene(holder_ref=HOLDER), {})
        assert merged["positions"][OCCUPANT] == "vessel_antechamber"
        assert merged["contained"] == {}

    def test_the_relation_becomes_inside_source(self):
        merged = merge_scene_with_diff(_scene(), {})
        rel = spatial_rel_between(merged, OCCUPANT, HOLDER)
        assert rel.get("inside_source") is True


class TestWhatIsNeverConverted:
    def test_a_holder_with_no_interior_is_given_one(self):
        """THE PIN THAT INVERTED, and it says so out loud.

        Until 2026-08-25 this asserted the opposite -- a holder with no
        interior rooms left exactly as it was, ledger record intact -- as a
        no-regression pin whose own docstring said it existed so a later
        change to this floor could not hide behind the file. This is that
        change. Nothing produced interior rooms except a prompt clause, so the
        conversion above had no on-ramp: measured read-only over the author's
        80 stored scene rows, four carry this exact shape and four bodies
        stand in their holder's own room forever.

        The five gates that keep every OTHER class untouched have their own
        tests in tests/test_interior_materialization.py.
        """
        before = merge_scene_with_diff(_scene(interior=False), {})
        minted = HOLDER_ID + "_interior"
        assert before["contained"] == {}
        assert before["positions"][OCCUPANT] == minted
        assert before["positions"][HOLDER] == "hall"
        room = before["rooms"][minted]
        assert room["parent_entity"] == HOLDER_ID
        assert room["light"] == "dark"
        assert room["dock_exit"] is True
        assert [e for e in room["adjacent"]
                if e.get("to") == "hall" and e.get("barrier") == "membrane"]

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


class TestTheWayOut:
    """A DECLARED POSITION IS A DECLARED ACT, and the engine may not undo it.

    The case above walks out of a contact-free interior, which is the rare
    one: an enclosure that is worth having is expressed in BOTH ledgers at
    once, and the contact row is the half this landing deliberately keeps
    alive across the boundary. Measured in this worktree before the fix, with
    the fixture one line below: t0 places the occupant inside; a diff writing
    `positions: {occupant: exterior}` came back with the occupant inside
    again, every beat, forever -- `derive_containment_from_contacts` re-minted
    a record from the surviving interior row and `place_enclosed_bodies` read
    it straight back in. Two derivations feeding each other, with a declared
    act caught between them.

    The rule is one sentence and it is not about enclosure: a position this
    beat DECLARED is the story speaking, and a derivation may not overwrite
    it. So a body declared into a room that is not inside its holder has left
    -- and the two ledgers that still say otherwise are the stale ones.
    """

    def test_a_declared_exit_survives_a_standing_interior_contact(self):
        placed = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("Antechamber")]), {})
        assert placed["positions"][OCCUPANT] == "vessel_antechamber"
        out = merge_scene_with_diff(placed,
                                    {"positions": {OCCUPANT: "hall"}})
        assert out["positions"][OCCUPANT] == "hall"
        assert out["contained"] == {}

    def test_the_stale_interior_row_is_retired_with_the_body(self):
        """Not the position, the CONTACT. Leaving the row standing makes the
        exit last exactly one beat, because the next merge mints from it."""
        placed = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("Antechamber")]), {})
        out = merge_scene_with_diff(placed,
                                    {"positions": {OCCUPANT: "hall"}})
        assert [row for row in out["contacts"]
                if str(row.get("relation")) == "interior"] == []

    def test_the_exit_still_holds_a_beat_later(self):
        placed = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("Antechamber")]), {})
        out = merge_scene_with_diff(placed,
                                    {"positions": {OCCUPANT: "hall"}})
        settled = merge_scene_with_diff(out, {})
        assert settled["positions"][OCCUPANT] == "hall"
        assert settled["contained"] == {}
        assert spatial_rel_between(settled, OCCUPANT, HOLDER).get(
            "inside_source") is not True

    def test_a_declared_exit_releases_the_ledger_before_it_ever_places(self):
        """The same rule one beat earlier: the record has not been converted
        yet and the beat declares the occupant elsewhere. Nothing places
        them, because nothing may."""
        out = merge_scene_with_diff(_scene(),
                                    {"positions": {OCCUPANT: "hall"}})
        assert out["positions"][OCCUPANT] == "hall"
        assert out["contained"] == {}

    def test_moving_deeper_is_not_an_exit(self):
        """A declared position INSIDE the holder is not a departure: the
        release is scoped to a room the holder's interior does not hold."""
        placed = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("Antechamber")]), {})
        deeper = merge_scene_with_diff(
            placed, {"positions": {OCCUPANT: "vessel_core"}})
        assert deeper["positions"][OCCUPANT] == "vessel_core"
        assert [row for row in deeper["contacts"]
                if str(row.get("relation")) == "interior"]

    def test_the_holder_moving_does_not_evict_its_occupant(self):
        """The declaration names the HOLDER, and the interior travels with
        it. Nothing about the occupant was declared, so nothing releases."""
        placed = merge_scene_with_diff(
            _scene(contacts=[_interior_contact("Antechamber")]), {})
        placed["rooms"]["yard"] = {"name": "Yard", "desc": "Out.",
                                   "adjacent": []}
        moved = merge_scene_with_diff(placed,
                                      {"positions": {HOLDER: "yard"}})
        assert moved["positions"][OCCUPANT] == "vessel_antechamber"
        assert moved["positions"][HOLDER] == "yard"

    def test_a_carriage_ledger_is_not_released_by_a_declared_position(self):
        """Scoped to the PLACE form, which is the class this landing created.
        A body in a pocket cannot walk out of it, and the carry derivation
        that says so is untouched -- the migration floor again."""
        scene = _scene(interior=False, mode="pocket")
        scene["rooms"]["yard"] = {"name": "Yard", "desc": "Out.",
                                  "adjacent": [{"to": "hall",
                                                "barrier": "open_door"}]}
        out = merge_scene_with_diff(scene,
                                    {"positions": {OCCUPANT: "yard"}})
        assert out["contained"][OCCUPANT]["mode"] == "pocket"
        assert out["positions"][OCCUPANT] == "hall"


class TestTheIndexAndTheOpacity:
    def test_a_parented_room_indexes_itself_on_its_entity(self):
        """One fact written twice, and only one spelling was ever derived.
        The half that missed it includes the one function that makes a body's
        inside opaque by default."""
        scene = _scene()
        scene["entities"][HOLDER_ID].pop("interior_rooms")
        merged = merge_scene_with_diff(scene, {})
        assert set(merged["entities"][HOLDER_ID]["interior_rooms"]) == {
            "vessel_antechamber", "vessel_core"}

    def test_an_unindexed_body_interior_still_defaults_to_membrane(self):
        """A leak OUTWARD if it does not: the room outside looks straight in."""
        scene = _scene()
        scene["entities"][HOLDER_ID]["interior_rooms"] = []
        merged = merge_scene_with_diff(scene, {})
        assert merged["entities"][HOLDER_ID].get("enclosure") == "membrane"
        edge = [e for e in merged["rooms"]["vessel_antechamber"]["adjacent"]
                if e.get("to") == "hall"]
        assert edge and edge[0]["barrier"] == "membrane"

    def test_a_non_body_parented_room_is_not_indexed(self):
        """SCOPED, and the scope is the migration story. The index this pass
        maintains is read by `infer_body_enclosures` -- which is body-scoped
        already -- and by two things that are not: the Director's destruction
        specialist gate and the commit-side room-removal protection set.
        Measured read-only against the author's live corpus while this landing
        was being repaired: 53 rooms carry `parent_entity`, 15 of them across
        13 chats were NOT indexed on their entity, and every one of those 15
        belongs to a NON-body -- lift cars, turbolifts, a ship, a police box.
        Indexing them would have flipped a Director specialist on in five
        stories and made six stories' interiors un-prunable, with nothing
        asking for either. So the derivation serves the class that needs it,
        and the corpus is left exactly as it was."""
        scene = _scene()
        scene["attire"].pop(HOLDER)
        scene["entities"][HOLDER_ID]["kind"] = "vehicle"
        scene["entities"][HOLDER_ID]["interior_rooms"] = []
        merged = merge_scene_with_diff(scene, {})
        assert merged["entities"][HOLDER_ID]["interior_rooms"] == []

    def test_a_vehicle_interior_keeps_its_see_through_doorway(self):
        """Scoped to bodies. A lift car is not a mass and its open hatch is
        an open hatch."""
        scene = _scene()
        scene["attire"].pop(HOLDER)
        scene["entities"][HOLDER_ID]["kind"] = "vehicle"
        merged = merge_scene_with_diff(scene, {})
        assert merged["entities"][HOLDER_ID].get("enclosure") in (None, "")
