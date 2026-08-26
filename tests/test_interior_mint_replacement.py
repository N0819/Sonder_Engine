"""An authored chain may replace the engine's own one-room mint. Only that.

THE GAP W9 LEFT, and the reason a filled card would still have helped nobody:
`materialize_enclosure_interiors` mints the authored chain only for a holder
with NO interior rooms (its gate 5), and a live story that needs a chain may
already stand on the engine's own minimal mint. Measured read-only against
the author's corpus 2026-08-25 at a2bc44f, over EVERY stored scene rather
than one story's branches: 7 scenes store a `contained` record (41, 44, 52,
60, 61, 88, 89) of which 2 use `mode: interior`, and 38 scenes carry a room
with a `parent_entity`. Exactly TWO of those rooms are the engine's own mint
-- chats 90 and 91, `<eid>_interior`, occupant standing inside. Every other
interior room in the corpus carries a story-written `desc` (vessels, lift
cars, a police box, and a second card's authored interior in chats 42/43/44),
so the replacement is permanently inert for all of them by its own key-set
test, whatever their cards later declare. The scope of this pass is the mint,
not the interior.

THE ONE STATE IN WHICH THE CARD BEATS THE SCENE, and it loses nothing by
construction: `_mint_minimal_interior` derives its room entirely from the
enclosure record, so an untouched stub restates a fact the record still
entails and carries nothing else. The moment the story writes ANYTHING on it
-- a description, a crossing time, an `exposure`, a `size`, a second room --
that is lived topology and the card does not get to overwrite it. Chat 91 is
the case that proves the difference is not academic: its stub carries
`exposure: "enclosed"` and `size: "tight"`, Director-declared room fields
merged onto a room the engine minted.

CLASS VOCABULARY ONLY IN THIS FILE.
"""

import copy
import hashlib
import json

from world.spatial import (merge_scene_with_diff,
                           replace_engine_minted_interiors)

HOLDER_EID = "vessel_one"
HOLDER = "The Vessel"
OCCUPANT = "Traveller"
MINT_ID = "vessel_one_interior"

SPEC = [
    {"name": "Mouth", "desc": "The way in.", "light": "dark"},
    {"name": "Throat", "desc": "A tight passage.", "light": "dark",
     "barrier": "membrane", "transit_seconds": 8.0},
    {"name": "Hold", "desc": "Deep and slow.", "light": "dark",
     "barrier": "membrane", "transit_seconds": 10800.0},
]


def _minted_room(name, **extra):
    """Exactly what `_mint_minimal_interior` writes, plus whatever the story
    has since written on it."""
    room = {
        "name": name,
        "desc": "",
        "light": "dark",
        "parent_entity": HOLDER_EID,
        "adjacent": [{"to": "outside", "barrier": "membrane",
                      "distance": "near"}],
        "dock_exit": True,
    }
    room.update(extra)
    return room


def _scene(*, mint_name="Throat", spec=SPEC, occupied=True, mint_extra=None,
           extra_rooms=None):
    """The chat-90 shape: a mint standing, the occupant inside it, a moving
    interior contact naming the same region, and the containment ledger
    already popped."""
    rooms = {
        "outside": {"name": "Outside", "desc": "A hall.",
                    "adjacent": [{"to": MINT_ID, "barrier": "membrane",
                                  "distance": "near"}]},
        MINT_ID: _minted_room(mint_name, **(mint_extra or {})),
    }
    rooms.update(extra_rooms or {})
    positions = {HOLDER: "outside"}
    if occupied:
        positions[OCCUPANT] = MINT_ID
    scene = {
        "location": "Nowhere",
        "rooms": rooms,
        "entities": {
            HOLDER_EID: {"name": HOLDER, "kind": "person", "aliases": [],
                         "interior_rooms": [MINT_ID], "state": {}},
        },
        "positions": positions,
        "contacts": [{
            "actor": OCCUPANT, "target": HOLDER, "relation": "interior",
            "target_interior": mint_name, "target_part": "",
            "motion": "moving", "manner": "press", "detail": "",
        }],
        "contained": {},
        "poses": {}, "stations": {}, "overlays": {}, "substances": [],
        # `_is_body_entity` reads exactly these two tables.
        "attire": {HOLDER: {"worn": []}, OCCUPANT: {"worn": []}},
        "scales": {},
    }
    if spec is not None:
        scene["entities"][HOLDER_EID]["interior_spec"] = copy.deepcopy(spec)
    return scene


def _interior(scene):
    return {rid: room for rid, room in (scene.get("rooms") or {}).items()
            if (room or {}).get("parent_entity") == HOLDER_EID}


def _where(scene):
    return (scene.get("positions") or {}).get(OCCUPANT)


def _fingerprint(scene):
    return hashlib.sha256(json.dumps(
        scene, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _contact(scene):
    for row in scene.get("contacts") or []:
        if str(row.get("relation") or "") == "interior":
            return row
    return {}


class TestTheAuthoredChainReachesAStandingMint:

    def test_the_stub_is_replaced_by_the_whole_chain(self):
        scene = _scene()
        assert replace_engine_minted_interiors(scene) == [HOLDER_EID]

        interior = _interior(scene)
        assert MINT_ID not in interior
        assert [room["name"] for room in interior.values()] == [
            "Mouth", "Throat", "Hold"]

    def test_the_occupant_lands_in_the_station_the_ledger_named(self):
        """The mint is named out of the same ledger the card's station is,
        so the match is by name and casefolded -- chat 90 stores its mint's
        name as `throat` against a card that would write `Throat`."""
        scene = _scene(mint_name="throat")
        replace_engine_minted_interiors(scene)
        here = _where(scene)
        assert here != MINT_ID, "the occupant was left in the retired room"
        assert (scene["rooms"][here] or {})["name"] == "Throat"

    def test_the_contact_ledger_follows_the_body(self):
        scene = _scene(mint_name="throat")
        replace_engine_minted_interiors(scene)
        row = _contact(scene)
        # `_interior_station_hint` reads this on the next merge, so a row
        # still naming the room behind them would drag them back.
        assert row["target_interior"] == "Throat"
        # The cross op's own never-carry rule.
        assert row.get("target_part") == ""

    def test_nothing_still_points_at_the_retired_room(self):
        scene = _scene()
        replace_engine_minted_interiors(scene)
        for rid, room in scene["rooms"].items():
            for edge in room.get("adjacent") or []:
                assert edge.get("to") != MINT_ID, (
                    f"{rid} still names the retired room")
        assert MINT_ID not in (
            scene["entities"][HOLDER_EID].get("interior_rooms") or [])

    def test_nobody_is_ever_without_a_room(self):
        scene = _scene()
        before = len(scene["positions"])
        replace_engine_minted_interiors(scene)
        assert len(scene["positions"]) == before
        assert _where(scene) in scene["rooms"]

    def test_an_empty_mint_is_replaced_with_nobody_to_move(self):
        """Nothing to lose, so the name need not match anything."""
        scene = _scene(mint_name="Somewhere Else", occupied=False)
        assert replace_engine_minted_interiors(scene) == [HOLDER_EID]
        assert [r["name"] for r in _interior(scene).values()] == [
            "Mouth", "Throat", "Hold"]


class TestSceneTopologyStillBeatsTheCard:
    """Four refusals, each one a thing the story has said that the card does
    not get to delete."""

    def _unchanged(self, scene):
        before = _fingerprint(scene)
        assert replace_engine_minted_interiors(scene) == []
        assert _fingerprint(scene) == before

    def test_no_authored_spec_changes_nothing(self):
        self._unchanged(_scene(spec=None))

    def test_a_described_stub_is_lived_topology(self):
        self._unchanged(_scene(mint_extra={"desc": "Warm and close."}))

    def test_a_timed_stub_is_lived_topology(self):
        self._unchanged(_scene(mint_extra={"transit_seconds": 30}))

    def test_a_declared_room_field_is_lived_topology(self):
        """Chat 91's exact shape, read from the corpus 2026-08-25: the
        Director merged `exposure` and `size` onto a room the engine minted.
        A field-by-field check would pass this room and delete both."""
        self._unchanged(_scene(
            mint_name="Passage",
            mint_extra={"exposure": "enclosed", "size": "tight"}))

    def test_a_second_interior_room_is_a_chain_the_story_grew(self):
        self._unchanged(_scene(extra_rooms={
            "vessel_one_deeper": {"name": "Deeper", "desc": "",
                                  "light": "dark",
                                  "parent_entity": HOLDER_EID,
                                  "adjacent": []}}))

    def test_a_non_body_holder_is_refused(self):
        """The firewall bound `materialize_enclosure_interiors` gate 3
        states, unchanged: an interior minted for a non-body is never
        indexed and never defaulted opaque."""
        scene = _scene()
        scene["attire"] = {}
        self._unchanged(scene)

    def test_an_occupied_mint_whose_name_matches_no_station_is_left_alone(
            self):
        """The engine cannot map the lived position onto the chain. Both
        available answers are worse than doing nothing -- dropping them at
        the way in carries a body OUTWARD from where the story put it, and
        inventing a destination is anatomy nobody wrote."""
        self._unchanged(_scene(mint_name="Somewhere The Card Never Names"))


class TestTheFixpoint:
    """A non-fixpoint merge serializes one scene two different ways on
    consecutive empty-diff merges -- the failure W8 measured."""

    def test_replacement_is_idempotent(self):
        scene = _scene()
        replace_engine_minted_interiors(scene)
        once = _fingerprint(scene)
        assert replace_engine_minted_interiors(scene) == []
        assert _fingerprint(scene) == once

    def test_a_sole_authored_station_does_not_replace_itself_forever(self):
        """The one shape that is structurally identical to the engine's own
        mint: one station, no desc, no crossing time. Only the name guard
        keeps this a fixpoint."""
        sole = [{"name": "Throat"}]
        scene = _scene(spec=sole, mint_name="Throat")
        assert replace_engine_minted_interiors(scene) == []

        renamed = _scene(spec=sole, mint_name="Gullet")
        assert replace_engine_minted_interiors(renamed) == []  # refusal 4
        empty = _scene(spec=sole, mint_name="Gullet", occupied=False)
        assert replace_engine_minted_interiors(empty) == [HOLDER_EID]
        once = _fingerprint(empty)
        assert replace_engine_minted_interiors(empty) == []
        assert _fingerprint(empty) == once

    def test_two_consecutive_clockless_merges_agree(self):
        first = merge_scene_with_diff(_scene(), {})
        second = merge_scene_with_diff(copy.deepcopy(first), {})
        assert _fingerprint(first) == _fingerprint(second)


class TestThroughTheWholeMerge:

    def test_the_chain_appears_and_then_runs_on_the_clock(self):
        """The point of the landing: after one authoring act, every later
        transition is derived with no player input and no per-beat model."""
        merged = merge_scene_with_diff(_scene(), {}, clock_seconds=0.0)
        here = _where(merged)
        assert merged["rooms"][here]["name"] == "Throat"
        # The stamp is laid at the first clocked merge; the bound is the
        # card's own 8 seconds.
        assert (merged.get("room_since") or {})[OCCUPANT]["room"] == here

        carried = merge_scene_with_diff(
            copy.deepcopy(merged), {}, clock_seconds=10.0)
        assert merged["rooms"][_where(carried)]["name"] == "Hold"

    def test_the_way_out_survives_the_replacement(self):
        """The exterior's dock edge pointed at the room this pass retires;
        without the rewrite the occupant is behind a doorway to nowhere, and
        `is_sealed_in` would start an air countdown on a body with a way
        out."""
        merged = merge_scene_with_diff(_scene(), {}, clock_seconds=0.0)
        entry = next(rid for rid, room in _interior(merged).items()
                     if room["name"] == "Mouth")
        outward = [edge for edge in merged["rooms"][entry].get("adjacent") or []
                   if edge.get("to") == "outside"]
        assert outward, "the way in and out was not re-derived onto the chain"
        assert not any(
            edge.get("to") == MINT_ID
            for room in merged["rooms"].values()
            for edge in room.get("adjacent") or [])

    def test_a_scene_with_no_spec_is_byte_identical_through_the_merge(self):
        """Nothing stamps `interior_spec` from a sheet with an empty
        `embodiment.interior`, and 0 of the 79 stored sheets carry one -- so
        every scene on disk is untouched by this landing."""
        scene = _scene(spec=None)
        once = merge_scene_with_diff(copy.deepcopy(scene), {})
        twice = merge_scene_with_diff(copy.deepcopy(once), {})
        assert _fingerprint(once) == _fingerprint(twice)
        assert MINT_ID in _interior(once)
