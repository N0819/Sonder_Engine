"""A pose detail is prose; possession is a ledger. Reconciling the two.

THE CLASS. `scene.poses[x]["detail"]` is free text that qualifies an
arrangement. It is the one scene field nothing re-derives: written once,
rendered verbatim into every view that can see the body -- the body's own
interoception line included -- and standing until some later beat happens to
overwrite it. When that prose says a body is CARRYING something it stops being
only an arrangement and becomes a possession claim, and possession is what
`inventory_ops` is for. Nothing reconciled them, so a thing could change hands
in the transfer ledger and go on being held in the pose prose for the rest of
the story.

MEASURED, chat 98. The establishing beat minted no entity for the object the
whole opening was about and wrote its entire existence into one line of pose
detail. Four beats later the Director resolved a complete transfer of it from
one body to another. `derive_inventory_placements` placed nothing (correctly:
the scene had no record of the thing) and said nothing (the defect). The pose
detail did not move. Five beats after she let go, that body's own composed
view still read "... -- holding <it> against chest", in the interoception
channel and in every other observer's sight line, and the narrator wrote it
into the prose twice. The narrator was not remembering; it was being told.

The two shapes below marked RECORDED are copied from that run's stored
variants -- the pose record from the turn-3 commit's scene, the op from the
turn-4 `director_resolve` `state_diff` -- so the field names the fix reads are
pinned against what the engine actually writes rather than against an invented
fixture.

No story nouns anywhere else: bodies are bodies, things are things.
"""

from world.spatial import (
    invalidate_transferred_pose_details,
    merge_scene_with_diff,
    pose_facts,
)

GIVER = "BODY_ONE"
TAKER = "BODY_TWO"
THIRD = "BODY_THREE"
THING = "thing_one"


def scene(detail="holding thing_one against chest", **over):
    sc = {
        "rooms": {"room_a": {"name": "Room A", "adjacent": []}},
        "positions": {GIVER: "room_a", TAKER: "room_a", THIRD: "room_a"},
        "entities": {},
        "attire": {GIVER: {}, TAKER: {}, THIRD: {}},
        "poses": {
            GIVER: {"posture": "standing", "support": "floor",
                    "relative_to": "", "relation": "", "constraint": "",
                    "detail": detail},
        },
    }
    sc.update(over)
    return sc


def op(**over):
    row = {"op": "transfer", "object_id": THING, "from_id": GIVER,
           "to_id": TAKER, "relation": "held", "details": {}}
    row.update(over)
    return row


# --- RECORDED SHAPES ------------------------------------------------------
#
# Verbatim from chat 98. If either of these stops matching what the engine
# writes, the fix reads a key nothing fills and is inert while its own
# invented fixtures go on passing -- the exact way a self-view repair for
# speech shipped dead because it read `quote` where the engine writes `text`.

#: `scene.poses["<a body>"]` as committed on turn 3.
RECORDED_POSE = {"posture": "standing", "support": "deck", "relative_to": "",
                 "relation": "", "constraint": "",
                 "detail": "holding padd against chest"}

#: `state_diff.inventory_ops[0]` as resolved on turn 4.
RECORDED_OP = {"op": "transfer", "object_id": "padd",
               "from_id": "A_GIVER", "to_id": "A_TAKER",
               "relation": "held", "details": {}}


def test_recorded_pose_and_op_still_have_the_fields_the_fix_reads():
    assert set(RECORDED_POSE) >= {"posture", "support", "detail"}
    assert set(RECORDED_OP) >= {"object_id", "from_id", "to_id"}
    recorded = scene(detail=RECORDED_POSE["detail"])
    recorded["poses"] = {"A_GIVER": dict(RECORDED_POSE)}
    recorded["positions"] = {"A_GIVER": "room_a", "A_TAKER": "room_a"}
    recorded["attire"] = {"A_GIVER": {}, "A_TAKER": {}}
    retired = invalidate_transferred_pose_details(
        recorded, [dict(RECORDED_OP)])
    assert retired == [("A_GIVER", "padd")]
    assert recorded["poses"]["A_GIVER"]["detail"] == ""


# --- the retirement -------------------------------------------------------


def test_the_giver_stops_carrying_what_the_ledger_moved():
    sc = scene()
    assert invalidate_transferred_pose_details(sc, [op()]) == [(GIVER, THING)]
    assert sc["poses"][GIVER]["detail"] == ""


def test_the_body_s_own_arrangement_survives_the_retirement():
    """A transfer is a fact about the thing, not about the body. Posture,
    support and the relation fields are the body's own and are untouched."""
    sc = scene()
    sc["poses"][GIVER]["relative_to"] = TAKER
    sc["poses"][GIVER]["relation"] = "facing"
    invalidate_transferred_pose_details(sc, [op()])
    pose = sc["poses"][GIVER]
    assert pose["posture"] == "standing"
    assert pose["support"] == "floor"
    assert pose["relative_to"] == TAKER
    assert pose["relation"] == "facing"


def test_the_taker_keeps_their_own_carriage_prose():
    sc = scene(detail="")
    sc["poses"][TAKER] = {"posture": "standing", "support": "floor",
                          "relative_to": "", "relation": "", "constraint": "",
                          "detail": "holding thing_one against chest"}
    assert invalidate_transferred_pose_details(sc, [op()]) == []
    assert sc["poses"][TAKER]["detail"] == "holding thing_one against chest"


def test_a_third_body_claiming_the_thing_lets_go_of_it():
    """One thing is in one place. The op said where; it was not here."""
    sc = scene(detail="")
    sc["poses"][THIRD] = {"posture": "standing", "support": "floor",
                          "relative_to": "", "relation": "", "constraint": "",
                          "detail": "thing_one held in both hands"}
    assert invalidate_transferred_pose_details(sc, [op()]) == [(THIRD, THING)]
    assert sc["poses"][THIRD]["detail"] == ""


def test_a_transfer_naming_no_destination_leaves_a_third_body_alone():
    """A null endpoint is silence, never an erasure -- the standing doctrine
    of every other pass over this ledger."""
    sc = scene(detail="")
    sc["poses"][THIRD] = {"posture": "standing", "support": "floor",
                          "relative_to": "", "relation": "", "constraint": "",
                          "detail": "thing_one held in both hands"}
    assert invalidate_transferred_pose_details(
        sc, [op(to_id="", from_id="")]) == []
    assert sc["poses"][THIRD]["detail"] == "thing_one held in both hands"


def test_a_giver_named_by_the_ledger_lets_go_with_no_destination():
    sc = scene()
    assert invalidate_transferred_pose_details(
        sc, [op(to_id="")]) == [(GIVER, THING)]
    assert sc["poses"][GIVER]["detail"] == ""


def test_a_detail_that_does_not_name_the_thing_stands():
    sc = scene(detail="breathing hard, shoulders held square")
    assert invalidate_transferred_pose_details(sc, [op()]) == []
    assert sc["poses"][GIVER]["detail"] == "breathing hard, shoulders held square"


def test_a_detail_naming_the_thing_without_carriage_vocabulary_stands():
    """Watching a thing, or standing beside one, is not a claim to be holding
    it. Only the vocabulary that says a pose depends on something being held
    or touched makes the prose answerable to the transfer ledger."""
    sc = scene(detail="eyes on thing_one")
    assert invalidate_transferred_pose_details(sc, [op()]) == []
    assert sc["poses"][GIVER]["detail"] == "eyes on thing_one"


def test_the_thing_must_be_named_on_a_word_boundary():
    sc = scene(detail="holding a thing_one_replica against chest")
    assert invalidate_transferred_pose_details(sc, [op()]) == []


def test_an_underscored_id_matches_the_prose_spelling_of_it():
    """An id is written `a_thing`; prose says "a thing". One thing, both
    spellings, because a different hand wrote each."""
    sc = scene(detail="holding thing one against chest")
    assert invalidate_transferred_pose_details(sc, [op()]) == [(GIVER, THING)]


def test_a_recorded_thing_is_matched_by_its_name_and_its_aliases():
    sc = scene(detail="carrying the small grey slab")
    sc["entities"] = {THING: {"name": "a slab", "kind": "object",
                              "aliases": ["small grey slab"],
                              "portable": True}}
    assert invalidate_transferred_pose_details(sc, [op()]) == [(GIVER, THING)]
    assert sc["poses"][GIVER]["detail"] == ""


def test_an_empty_or_malformed_ledger_changes_nothing():
    for ops in (None, [], [None], ["not an op"], [{}], [{"object_id": ""}]):
        sc = scene()
        assert invalidate_transferred_pose_details(sc, ops) == []
        assert sc["poses"][GIVER]["detail"] == "holding thing_one against chest"


# --- through the merge, and out into what a mind is told ------------------


def test_the_merge_runs_the_reconciliation_and_reports_it():
    report = []
    merged = merge_scene_with_diff(
        scene(), {"inventory_ops": [op()]}, inventory_report=report)
    assert merged["poses"][GIVER]["detail"] == ""
    assert any("carriage clause" in note for note in report)


def test_the_view_every_mind_is_given_stops_saying_it():
    """The end of the chain the defect was measured at: what `pose_facts`
    hands the composer, for the giver and for everyone watching."""
    before = merge_scene_with_diff(scene(), {})
    after = merge_scene_with_diff(scene(), {"inventory_ops": [op()]})
    watchers = [GIVER, TAKER, THIRD]
    for who in watchers:
        assert any("holding thing_one" in fact
                   for fact in pose_facts(before, who, watchers))
        assert not any("holding thing_one" in fact
                       for fact in pose_facts(after, who, watchers))


def test_this_beat_s_own_pose_prose_is_answerable_to_this_beat_s_ledger():
    """Unlike the scale-change retirement's `stated` exemption. The two halves
    come from different hands on disjoint scopes -- `poses` from the spatial
    specialist, `inventory_ops` from the objects specialist -- so neither is
    the later word, and the channel built to say where a thing is outranks
    prose that mentions it."""
    merged = merge_scene_with_diff(
        scene(detail=""),
        {"poses": {GIVER: {"posture": "standing", "support": "floor",
                           "detail": "holding thing_one against chest"}},
         "inventory_ops": [op()]})
    assert merged["poses"][GIVER]["detail"] == ""
    assert merged["poses"][GIVER]["posture"] == "standing"


# --- the refusal, said out loud ------------------------------------------


def test_a_transfer_of_an_unrecorded_thing_now_mints_it_and_records_it():
    """This used to be refused audibly, which was the half of the answer
    available before the transfer could mint. It mints now, so the handover
    is RECORDED rather than merely reported: the taker holds the thing, and
    the audible refusal has nothing left to refuse."""
    report = []
    merged = merge_scene_with_diff(
        scene(), {"inventory_ops": [op()]}, inventory_report=report)
    assert merged["entities"][THING]["kind"] == "object"
    assert merged["contained"][THING]["in"] == TAKER
    assert not any("no entity record" in note for note in report)


def test_a_transfer_naming_a_BODY_is_still_refused_and_still_says_so():
    """The refusal survives where it is still a refusal. A body is never
    minted over -- `_merge_entity`'s own docstring records a registered
    character turned into "an object named The Doctor" -- so an op whose
    object is a person places nothing, mints nothing, and is audible."""
    report = []
    sc = scene()
    sc["positions"]["a person"] = "room_a"
    merged = merge_scene_with_diff(
        sc, {"inventory_ops": [op(object_id="a person")]},
        inventory_report=report)
    assert "a person" not in merged.get("entities", {})
    assert (merged.get("contained") or {}).get("a person") is None
    assert any("a person" in note for note in report)


def test_a_transfer_of_a_recorded_thing_reports_no_refusal():
    report = []
    sc = scene()
    sc["entities"] = {THING: {"name": "a thing", "kind": "object",
                              "aliases": [], "portable": True}}
    merged = merge_scene_with_diff(
        sc, {"inventory_ops": [op()]}, inventory_report=report)
    assert not any("no entity record" in note for note in report)
    # ...and the placement it was always able to make still happens.
    assert (merged.get("contained") or {}).get(THING, {}).get("in") == TAKER


def test_the_report_is_optional_and_absence_changes_nothing():
    with_report, without = [], None
    a = merge_scene_with_diff(scene(), {"inventory_ops": [op()]},
                              inventory_report=with_report)
    b = merge_scene_with_diff(scene(), {"inventory_ops": [op()]},
                              inventory_report=without)
    assert a == b
