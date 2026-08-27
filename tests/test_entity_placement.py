"""Placement derived from the transfer ledger.

THE CLASS: an entity has no location field. Its room is `scene["positions"]`
and nothing else, and the hand that mints entities cannot write that channel --
`entities` belongs to one specialist, `positions` to another, they run in
parallel on disjoint scopes, and a stray `positions` key from the wrong hand is
dropped by validation before assembly sees it. So a thing minted mid-beat is
nowhere, permanently: excluded from co-presence by construction, unperceivable,
unreachable. Measured across the live corpus: the single-hand opening stage
places 96.5% of what it mints, the orchestrated fan-out 5.8%, and nearly all of
that 5.8% is bodies.

The evidence to place them was already being written into `inventory_ops`, by
the right hand, on the right beat, into a channel with no reader anywhere in
persist/ or world/. These tests hold the derivation that reads it, the two
evidence classes that used to acquit a placement that never happened, and the
floor that reports what is still nowhere afterwards.

No story nouns: rooms are room ids, bodies are bodies, things are things.
"""

from agents.director import _evidence_present, _unplaced_minted_entities
from world.spatial import (
    hiding_holders_of,
    merge_scene_with_diff,
    resolve_placement_target,
    room_of,
)

BODY = "BODY_ONE"
OTHER = "BODY_TWO"
THING = "thing_1"


def scene():
    """Two rooms, a body in each. `attire` is what makes a body a body --
    `_is_body_entity` derives it rather than reading a `kind` label."""
    return {
        "rooms": {"room_a": {"name": "Room A", "adjacent": []},
                  "room_b": {"name": "Room B", "adjacent": []}},
        "positions": {BODY: "room_a", OTHER: "room_b"},
        "entities": {},
        "attire": {BODY: {}, OTHER: {}},
    }


def mint(**over):
    thing = {"name": "a thing", "kind": "object", "portable": True,
             "aliases": []}
    thing.update(over)
    return {"entities": {THING: thing}}


def op(**over):
    row = {"op": "place", "object_id": THING}
    row.update(over)
    return row


# --- the derivation ------------------------------------------------------

def test_a_thing_transferred_to_a_room_ends_the_beat_in_that_room():
    """THE CENTRAL CLAIM. Mint plus a transfer op naming a room; before the
    derivation existed this committed with the thing in no room at all."""
    sd = dict(mint(), inventory_ops=[op(from_id=BODY, to_id="room_a",
                                        relation="on")])
    merged = merge_scene_with_diff(scene(), sd)
    assert room_of(merged, THING) == "room_a"


def test_a_destination_naming_the_rooms_display_name_still_resolves():
    """A destination is model-written: the id and the room's own name are the
    same place, and refusing one of them would leave the thing nowhere."""
    sd = dict(mint(), inventory_ops=[op(to_id="Room A")])
    assert room_of(merge_scene_with_diff(scene(), sd), THING) == "room_a"


def test_a_destination_that_resolves_to_nothing_places_nothing():
    """A bare noun for a surface the world has no record of. REFUSING is the
    point: writing the token into `positions` is the category error
    `repair_entity_positions` exists to clean up after."""
    sd = dict(mint(), inventory_ops=[op(to_id="some unrecorded surface")])
    merged = merge_scene_with_diff(scene(), sd)
    assert room_of(merged, THING) is None
    assert "some unrecorded surface" not in merged["positions"].values()


def test_a_null_endpoint_is_silence_and_never_an_erasure():
    """The standing `_merge_entity` doctrine: nothing is unplaced by this."""
    sc = scene()
    sc["entities"] = {THING: {"name": "a thing", "kind": "object"}}
    sc["positions"][THING] = "room_b"
    sd = {"inventory_ops": [op(op="take", to_id=None, from_id=None)]}
    assert room_of(merge_scene_with_diff(sc, sd), THING) == "room_b"


def test_a_destination_the_scene_places_lends_the_thing_its_room():
    """Set down ON something the world does know: the thing is in that
    thing's room. A destination that is itself nowhere lends nothing."""
    sc = scene()
    sc["entities"] = {"fixture_1": {"name": "a fixture", "kind": "furniture"}}
    sc["positions"]["fixture_1"] = "room_b"
    sd = dict(mint(), inventory_ops=[op(to_id="a fixture")])
    assert room_of(merge_scene_with_diff(sc, sd), THING) == "room_b"

    sc = scene()
    sc["entities"] = {"fixture_1": {"name": "a fixture", "kind": "furniture"}}
    sd = dict(mint(), inventory_ops=[op(to_id="a fixture")])
    assert room_of(merge_scene_with_diff(sc, sd), THING) is None


def test_a_destination_that_is_a_body_writes_a_carrier_relation():
    """Not a position. Where it then is follows from where the holder is, so
    a holder who walks takes it along instead of leaving it behind."""
    sd = dict(mint(), inventory_ops=[op(op="give", to_id=BODY,
                                        relation="held")])
    merged = merge_scene_with_diff(scene(), sd)
    assert (merged.get("contained") or {}).get(THING, {}).get("in") == BODY
    assert room_of(merged, THING) == room_of(merged, BODY)


def test_body_ness_is_derived_from_evidence_not_from_a_kind_label():
    """`kind` is free text a model writes. Two destinations carrying the SAME
    label are treated oppositely on the evidence that one of them wears
    something -- the `_is_body_entity` precedent, generalised."""
    sc = scene()
    sc["entities"] = {
        "one": {"name": "one", "kind": "thing"},
        "two": {"name": "two", "kind": "thing"},
    }
    sc["positions"].update({"one": "room_b", "two": "room_b"})
    sc["attire"]["two"] = {}
    assert resolve_placement_target(sc, "one")[0] == "anchor"
    assert resolve_placement_target(sc, "two") == ("carrier", "two")


def test_a_declared_placement_outranks_the_derivation():
    """The spatial specialist still owns `positions` and the contact
    specialist still owns `containment`. This speaks only where they did
    not -- otherwise the fan-out's ownership race is back."""
    sd = dict(mint(), positions={THING: "room_b"},
              inventory_ops=[op(op="give", to_id=BODY)])
    merged = merge_scene_with_diff(scene(), sd)
    assert merged["positions"][THING] == "room_b"
    assert THING not in (merged.get("contained") or {})


def test_reaching_a_place_ends_a_carry():
    """Left standing, the old carrier relation drags the thing back to the
    holder's room on the next derivation."""
    sc = scene()
    sc["entities"] = {THING: {"name": "a thing", "kind": "object"}}
    sc["contained"] = {THING: {"in": BODY, "mode": "pocket"}}
    sd = {"inventory_ops": [op(from_id=BODY, to_id="room_b")]}
    merged = merge_scene_with_diff(sc, sd)
    assert THING not in (merged.get("contained") or {})
    assert room_of(merged, THING) == "room_b"


def test_the_derivation_writes_one_spelling_per_being():
    """`positions` is keyed by whatever the writer reached for. A second
    spelling puts one thing in two rooms at once."""
    sc = scene()
    sc["entities"] = {THING: {"name": "a thing", "kind": "object"}}
    sc["positions"]["a thing"] = "room_b"
    sd = {"inventory_ops": [op(to_id="room_a")]}
    merged = merge_scene_with_diff(sc, sd)
    assert merged["positions"]["a thing"] == "room_a"
    assert THING not in merged["positions"]


def test_a_thing_the_scene_does_not_know_is_not_conjured_into_a_room():
    """A transfer op naming an object with no entity record places nothing:
    a bare key in `positions` is a body-shaped hole, not a thing."""
    sd = {"inventory_ops": [op(object_id="never_minted", to_id="room_a")]}
    merged = merge_scene_with_diff(scene(), sd)
    assert "never_minted" not in merged["positions"]


def test_a_bodiless_thing_is_never_given_a_room():
    """`scene.is_ubiquitous_entity` calls a position on one a category
    error, and the merge prunes it -- so do not write one."""
    sd = dict(mint(ubiquitous=True), inventory_ops=[op(to_id="room_a")])
    assert room_of(merge_scene_with_diff(scene(), sd), THING) is None


def test_the_verb_is_never_read():
    """Where a thing ENDED UP is the only question. A verb vocabulary would
    reject the words the fiction actually reaches for."""
    for verb in ("place", "drop", "stow", "sets down upon", ""):
        sd = dict(mint(), inventory_ops=[op(op=verb, to_id="room_a")])
        assert room_of(merge_scene_with_diff(scene(), sd), THING) == "room_a"


# --- the firewall --------------------------------------------------------

def test_a_concealed_carry_stays_concealed_and_an_open_one_does_not():
    """The one genuine expansion available here is reading "handed to
    someone" as "lying in that room". The carrier relation is what keeps the
    two apart: the op's own word becomes the containment mode, and every mode
    outside the open set conceals."""
    hidden = merge_scene_with_diff(
        scene(), dict(mint(), inventory_ops=[op(op="give", to_id=BODY,
                                                relation="pocket")]))
    assert hiding_holders_of(hidden, THING) == [BODY]

    open_carry = merge_scene_with_diff(
        scene(), dict(mint(), inventory_ops=[op(op="give", to_id=BODY,
                                                relation="held")]))
    assert hiding_holders_of(open_carry, THING) == []


def test_an_unvouched_relation_falls_to_the_ledgers_own_default():
    """One ledger, one default. A competing default here is how two paths
    start disagreeing about the same fact."""
    merged = merge_scene_with_diff(
        scene(), dict(mint(), inventory_ops=[op(op="give", to_id=BODY)]))
    assert (merged["contained"][THING]["mode"]
            == merge_scene_with_diff(
                scene(), {"containment": {THING: {"in": BODY}}}
            )["contained"][THING]["mode"])


def test_a_transfer_op_never_derives_an_interior_place():
    """`mode: interior` mints rooms and moves bodies into them. A transfer op
    is evidence of carriage and never of that."""
    merged = merge_scene_with_diff(
        scene(), dict(mint(), inventory_ops=[op(op="give", to_id=BODY,
                                                relation="interior")]))
    assert merged["contained"][THING]["mode"] != "interior"
    assert not [r for r in merged["rooms"].values()
                if isinstance(r, dict) and r.get("parent_entity")]


def test_placement_gives_no_channel_to_an_observer_who_has_none():
    """Placement is a world fact; DELIVERY is still the gate's decision. A
    presence in another room, and a presence in the same room as a thing that
    is pocketed, both still have no channel to it."""
    from agents.common import _check_presence_knowledge_channel

    named = mint(name="brass token", aliases=[])
    elsewhere = merge_scene_with_diff(
        scene(), dict(named, inventory_ops=[op(to_id="room_a")]))
    assert room_of(elsewhere, THING) == "room_a"
    assert _check_presence_knowledge_channel(
        OTHER, "the brass token is missing", elsewhere,
        {"sketch": {}}, "")

    pocketed = merge_scene_with_diff(
        scene(), dict(named, inventory_ops=[op(op="give", to_id=BODY,
                                               relation="pocket")]))
    assert room_of(pocketed, THING) == "room_a"
    assert _check_presence_knowledge_channel(
        "WITNESS", "the brass token is missing", pocketed,
        {"sketch": {"station_room": "room_a"}}, "")

    # ...and the gate is discriminating rather than uniformly deaf: standing
    # in the room the thing was openly set down in IS a channel. That is what
    # placement buys, and it is the whole of what it buys.
    assert _check_presence_knowledge_channel(
        "WITNESS", "the brass token is missing", elsewhere,
        {"sketch": {"station_room": "room_a"}}, "") == []


# --- the detector that used to acquit the omission -----------------------

def _present(sd, category, subject, sc):
    return _evidence_present(sd, {"category": category, "subject": subject},
                             None, scene=sc)


def test_a_mint_alone_does_not_acquit_a_placement():
    """Minting the noun WAS the evidence that placing it happened. The two
    categories a placement is naturally filed under were the two that
    acquitted it while the thing was nowhere."""
    sc = scene()
    assert not _present(mint(), "entities", THING, sc)
    assert _present(dict(mint(), positions={THING: "room_a"}),
                    "entities", THING, sc)


def test_a_transfer_op_acquits_only_when_its_destination_resolves():
    unresolvable = dict(mint(), inventory_ops=[op(to_id="a bare noun")])
    resolvable = dict(mint(), inventory_ops=[op(to_id="room_a")])
    sc = scene()
    assert not _present(unresolvable, "inventory", THING, sc)
    assert not _present(unresolvable, "entities", THING, sc)
    assert _present(resolvable, "inventory", THING, sc)
    assert _present(resolvable, "entities", THING, sc)


def test_a_thing_the_scene_already_places_is_acquitted_by_any_touch():
    """The tightening is about location, not about mints. A state change to
    something that already stands somewhere is fully encoded."""
    sc = scene()
    sc["entities"] = {THING: {"name": "a thing", "kind": "object"}}
    sc["positions"][THING] = "room_b"
    assert _present(mint(state={"lit": True}), "entities", THING, sc)


def test_the_classifier_keeps_its_old_answer_with_no_scene():
    """A caller holding no scene degrades to the behaviour it had, never to
    a wrong one."""
    assert _evidence_present(mint(), {"category": "entities",
                                      "subject": THING}, None)


def test_removal_and_the_roomless_classes_are_not_reported_as_unplaced():
    sc = scene()
    assert _present({"remove_entities": [THING]}, "entities", THING, sc)
    assert _present(mint(ubiquitous=True), "entities", THING, sc)
    assert _present(mint(state={"link": ["room_a", "room_b"]}),
                    "entities", THING, sc)


# --- the floor -----------------------------------------------------------

def test_the_floor_reports_a_thing_this_beat_left_nowhere():
    sc = scene()
    assert _unplaced_minted_entities(
        sc, dict(mint(), inventory_ops=[op(to_id="a bare noun")])) == [THING]
    assert _unplaced_minted_entities(
        sc, dict(mint(), inventory_ops=[op(to_id="room_a")])) == []
    assert _unplaced_minted_entities(sc, dict(mint(), positions={
        THING: "room_a"})) == []


def test_the_floor_checks_portable_things_too():
    """The opening stage's equivalent exempts every `portable` entity because
    "inventory is not `positions`". That ground now has a floor under it, so
    the exemption buys nothing here."""
    sc = scene()
    assert _unplaced_minted_entities(sc, mint(portable=True)) == [THING]


def test_the_floor_is_scoped_to_what_this_beat_named():
    """A thing left nowhere ten beats ago is not this beat's omission, and
    re-reporting it every beat turns the warning into noise."""
    sc = scene()
    sc["entities"] = {"older_thing": {"name": "older", "kind": "object"}}
    assert _unplaced_minted_entities(sc, {"positions": {BODY: "room_b"}}) == []


def test_the_floor_exempts_what_has_no_room_by_construction():
    sc = scene()
    for over in ({"ubiquitous": True},
                 {"state": {"link": ["room_a", "room_b"]}},
                 {"state": {"transit": {"phase": "in_flight"}}}):
        assert _unplaced_minted_entities(sc, mint(**over)) == []
    assert _unplaced_minted_entities(
        sc, dict(mint(), remove_entities=[THING])) == []


def test_both_readers_are_actually_wired_into_the_resolve_stage():
    """The two seam-side halves have call sites a green suite would not
    otherwise notice losing: the evidence classifier only tightens when it is
    HANDED the scene, and the floor only reports if something calls it. Both
    are single keyword/one-line wirings, so assert the wiring itself."""
    import inspect

    from agents import director

    source = inspect.getsource(director)
    calls = [line for line in source.splitlines()
             if "_evidence_present(" in line and "def " not in line
             and "import" not in line]
    assert calls
    assert all("scene=" in line for line in calls), calls
    assert "_unplaced_minted_entities(" in inspect.getsource(
        director.director_resolve)


def test_the_floor_measures_the_merged_outcome():
    """It asks `room_of` of the merged scene rather than re-deriving the
    placement rules, so it cannot drift away from what the merge does."""
    sc = scene()
    sd = dict(mint(), inventory_ops=[op(op="give", to_id=BODY,
                                        relation="pocket")])
    assert _unplaced_minted_entities(sc, sd) == []
    assert room_of(merge_scene_with_diff(sc, sd), THING) == "room_a"


# --- placement derived from who HANDLED the thing ------------------------
#
# The transfer ledger above answers only for a beat that wrote one. The
# larger class is a thing minted with NO transfer at all -- the objects hand
# names it, cannot write `positions`, and nothing else has any reason to
# mention it. Measured over the audited 15-beat run and the two before it:
# every minted entity committed with `room: None`. The evidence is in the
# merge anyway: who touched it and which room they are in, where a station
# says it was set down, and the origin a transfer named when its destination
# resolved to nothing.


def anchored():
    """The same two rooms, with an anchor declared in one of them."""
    sc = scene()
    sc["rooms"]["room_b"]["anchors"] = {"anchor_1": {"desc": "an anchor"}}
    return sc


def touch(**over):
    row = {"op": "add", "actor": BODY, "target": THING,
           "manner": "holds", "relation": "surface"}
    row.update(over)
    return row


def test_a_thing_a_body_took_hold_of_ends_the_beat_in_that_bodys_room():
    merged = merge_scene_with_diff(scene(), dict(mint(), contact_ops=[touch()]))
    assert room_of(merged, THING) == "room_a"


def test_either_endpoint_of_the_contact_answers():
    """Which side of the contact the thing is written on is the model's
    wording, not a fact about the world."""
    merged = merge_scene_with_diff(
        scene(), dict(mint(), contact_ops=[touch(actor=THING, target=OTHER)]))
    assert room_of(merged, THING) == "room_b"


def test_a_standing_contact_places_a_thing_the_beat_only_now_minted():
    sc = scene()
    sc["contacts"] = [{"actor": OTHER, "target": THING, "manner": "holds",
                       "relation": "surface"}]
    assert room_of(merge_scene_with_diff(sc, mint()), THING) == "room_b"


def test_an_ended_contact_places_nothing():
    """Letting go is evidence of not holding. The two ops that END a contact
    place nothing, and this beat's ops are read before the standing ledger so
    the ending is what is seen."""
    for op_name in ("remove", "clear"):
        merged = merge_scene_with_diff(
            scene(), dict(mint(), contact_ops=[touch(op=op_name)]))
        assert room_of(merged, THING) is None, op_name


def test_a_station_lends_the_room_that_declares_its_anchor():
    """Where it was SET DOWN. An anchor is a feature of exactly one room, so
    it answers 'which room' for a thing that has no position yet -- the one
    moment nothing else can."""
    merged = merge_scene_with_diff(
        anchored(), dict(mint(), stations={THING: {"at": "anchor_1"}}))
    assert room_of(merged, THING) == "room_b"


def test_a_station_near_a_body_lends_that_bodys_room():
    merged = merge_scene_with_diff(
        scene(), dict(mint(), stations={THING: {"at": None, "near": [OTHER]}}))
    assert room_of(merged, THING) == "room_b"


def test_a_transfer_whose_destination_resolves_to_nothing_falls_to_its_origin():
    """The destination has already been offered to the transfer derivation and
    declined by it; the ORIGIN is a second, independent fact in the same row."""
    merged = merge_scene_with_diff(
        scene(), dict(mint(), inventory_ops=[
            op(from_id=OTHER, to_id="a surface nothing knows")]))
    assert room_of(merged, THING) == "room_b"


def test_evidence_that_resolves_to_nothing_places_nothing():
    for diff in (dict(mint(), contact_ops=[touch(actor="NOBODY")]),
                 dict(mint(), stations={THING: {"at": "no_such_anchor"}}),
                 dict(mint(), inventory_ops=[op(from_id="NOBODY")]),
                 mint()):
        assert room_of(merge_scene_with_diff(scene(), diff), THING) is None


def test_a_declared_position_outranks_the_derivation():
    """The same `declared=` subtraction the transfer derivation takes: an
    explicit write by the hand that owns the channel always wins."""
    merged = merge_scene_with_diff(
        scene(), dict(mint(), contact_ops=[touch()],
                      positions={THING: "room_b"}))
    assert room_of(merged, THING) == "room_b"


def test_a_declared_containment_outranks_it_too():
    merged = merge_scene_with_diff(
        scene(), dict(mint(), contact_ops=[touch()],
                      containment={THING: {"in": OTHER, "mode": "pocket"}}))
    assert merged["contained"].get(THING, {}).get("in") == OTHER
    assert room_of(merged, THING) == "room_b"


def test_a_carrier_relation_from_the_transfer_ledger_outranks_it():
    """It YIELDS to the pass that runs before it. A thing handed to a body is
    carried, not lying in that body's room, and the carrier relation is what
    keeps a pocketed thing out of sight."""
    merged = merge_scene_with_diff(
        scene(), dict(mint(), contact_ops=[touch(actor=OTHER)],
                      inventory_ops=[op(op="give", to_id=BODY,
                                        relation="pocket")]))
    assert merged["contained"].get(THING, {}).get("in") == BODY
    assert hiding_holders_of(merged, THING)


def test_a_body_is_never_placed_by_this_derivation():
    """Body-ness is derived from attire and scale, never read off a `kind`
    label -- and a body is placed by its own machinery, where misplacing it
    costs more than leaving a thing nowhere."""
    sc = scene()
    sc["attire"]["thing_1"] = {}
    merged = merge_scene_with_diff(sc, dict(mint(), contact_ops=[touch()]))
    assert room_of(merged, THING) is None


def test_the_classes_with_no_room_by_construction_stay_nowhere():
    for over in ({"ubiquitous": True},
                 {"state": {"link": ["room_a", "room_b"]}},
                 {"state": {"transit": {"phase": "in_flight"}}}):
        merged = merge_scene_with_diff(
            scene(), dict(mint(**over), contact_ops=[touch()]))
        assert room_of(merged, THING) is None, over


def test_a_thing_that_is_already_somewhere_is_never_moved():
    """Nothing is UNPLACED or RELOCATED here; this writes a room where there
    was none."""
    sc = scene()
    sc["entities"][THING] = {"name": "a thing", "kind": "object"}
    sc["positions"][THING] = "room_b"
    merged = merge_scene_with_diff(sc, dict(mint(), contact_ops=[touch()]))
    assert room_of(merged, THING) == "room_b"


def test_the_derivation_is_scoped_to_what_this_beat_named():
    """A thing left nowhere ten beats ago is not this beat's to relocate, and
    a scene-wide sweep would move things on evidence that has gone stale."""
    sc = scene()
    sc["entities"]["thing_2"] = {"name": "an older thing", "kind": "object"}
    sc["contacts"] = [{"actor": BODY, "target": "thing_2",
                       "manner": "holds", "relation": "surface"}]
    merged = merge_scene_with_diff(sc, dict(mint(), contact_ops=[touch()]))
    assert room_of(merged, THING) == "room_a"
    assert room_of(merged, "thing_2") is None


def test_a_concealed_handler_lends_no_room():
    """THE FIREWALL LINE. A position in a room is perceptible to everyone in
    it, so lending a thing the room of a body who is himself shut inside
    something would show a pocketed thing to the whole room while its holder
    stays hidden. A concealed handler lends nothing."""
    sc = scene()
    sc["entities"]["container_1"] = {"name": "a container", "kind": "object"}
    sc["positions"]["container_1"] = "room_a"
    sc["contained"] = {BODY: {"in": "container_1", "mode": "container"}}
    assert hiding_holders_of(sc, BODY)
    merged = merge_scene_with_diff(sc, dict(mint(), contact_ops=[touch()]))
    assert room_of(merged, THING) is None


def test_handler_placement_gives_no_channel_to_an_observer_who_has_none():
    """Placement is a world fact; DELIVERY is still the gate's decision. A
    body in the other room gains nothing from a thing placed here, and the
    gate is discriminating rather than uniformly deaf."""
    from agents.common import _check_presence_knowledge_channel

    named = mint(name="brass token", aliases=[])
    merged = merge_scene_with_diff(scene(), dict(named,
                                                 contact_ops=[touch()]))
    assert room_of(merged, THING) == "room_a"
    assert _check_presence_knowledge_channel(
        OTHER, "the brass token is missing", merged,
        {"sketch": {"station_room": "room_b"}}, "")
    assert _check_presence_knowledge_channel(
        "WITNESS", "the brass token is missing", merged,
        {"sketch": {"station_room": "room_a"}}, "") == []


def test_the_floor_stops_reporting_what_the_derivation_now_places():
    """The floor measures the merged OUTCOME, so the two halves agree by
    construction rather than by a second copy of the placement rules."""
    sd = dict(mint(), contact_ops=[touch()])
    assert _unplaced_minted_entities(scene(), sd) == []
    assert _unplaced_minted_entities(scene(), mint()) == [THING]


def test_the_minted_derivation_is_wired_into_the_merge():
    """One call in one merge, and a green suite would not otherwise notice it
    going away: assert the wiring, and that it runs AFTER the transfer
    derivation it yields to."""
    import inspect

    source = inspect.getsource(merge_scene_with_diff)
    assert "derive_minted_entity_placements(" in source
    assert (source.index("derive_inventory_placements(")
            < source.index("derive_minted_entity_placements("))
