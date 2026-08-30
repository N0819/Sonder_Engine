"""Clothing is not a surface that touches, and a thing is not someone.

Every fixture in this file is a shape RECORDED IN PLAY, not one invented for
the test: chat 98 (the Enterprise-D alpha-shift run) turns 22 and 27, copied
out of that run's own checkpoints and committed `state_diff.contact_ops`. The
two defects they pin were both found by reading live pipeline output after
their guards' unit tests passed, so the shape is the thing worth pinning.

Turn 22, verbatim from the committed diff:

    {"op": "add", "actor": "Sabine Oyelaran", "actor_part": "uniform",
     "target": "combadge", "target_part": "", "relation": "surface",
     "motion": "settled", "detail": "worn on chest"}

That was ACCEPTED, stored as `contact:1c66c459972fe61b635f`, and composed
into the player's own view as

    "You feel someone against your uniform: steady pressure, weight and
     shared warmth, continuous while the contact holds."

-- a person invented out of a worn badge, in physical contact with the player,
while she stood alone in a lift. The narrator invented nothing; it was handed
that sentence by the composed view.

Turn 27, verbatim: two adds naming the same two parties and the same two
parts, differing ONLY in `manner` ('stand' and 'settle'). The placement floor
refused 'stand' and reported it correctly. 'settle' passed every floor and
committed as `contact:a5396920aab42700ae5c`. The floor was defeated by a
synonym rather than crossed by prose.
"""

import copy

from world.spatial import (_endpoint_is_worn_clothing,
                           _part_is_clothing,
                           apply_contact_ops,
                           contact_endpoint_is_body,
                           contact_sensation,
                           contact_thing_label)


# --- recorded, chat 98 turn 22 (checkpoint 22 = the scene the turn ran on) --
RUN98_TURN22_SCENE = {
    "attire": {
        "Sabine Oyelaran": {
            "wearing": ["combadge", "civilian clothing"],
            "state": ["immaculate", "properly fitted"],
            "regions": {"torso": {"garments": [
                {"name": "combadge", "attaches": True, "state": "worn",
                 "description": "Starfleet delta shield communicator badge in "
                                "silver and gold, pinned to the left chest of "
                                "the uniform.", "condition": "", "covers": []},
                {"name": "civilian clothing", "attaches": False,
                 "state": "worn", "description": "", "condition": "",
                 "covers": []},
            ], "beneath": ""}},
        },
    },
    "entities": {
        "standard_starfleet_duty_uniform_teal_science_division_shoulders_"
        "sabine_oyelaran": {
            "name": "standard Starfleet duty uniform "
                    "(teal science division shoulders)",
            "kind": "object",
            "description": "standard Starfleet duty uniform (teal science "
                           "division shoulders), taken off",
            "aliases": ["standard Starfleet duty uniform "
                        "(teal science division shoulders)"],
            "portable": True, "container": False, "interior_rooms": [],
            "state": {"clothing": True, "worn_by": "Sabine Oyelaran",
                      "shed": True},
        },
    },
    "positions": {"Sabine Oyelaran": "turbolift"},
    "contacts": [],
}

RUN98_TURN22_OP = {
    "op": "add", "actor": "Sabine Oyelaran", "actor_part": "uniform",
    "target": "combadge", "target_part": "", "target_interior": "",
    "relation": "surface", "motion": "settled", "detail": "worn on chest",
}

# The record as it was actually STORED, read back out of checkpoint 23. This
# is what the render floor has to hold against: it already exists on disk in
# real saves, and no write-time refusal can reach backwards for it.
RUN98_TURN22_STORED_CONTACT = {
    "actor": "Sabine Oyelaran", "actor_part": "uniform",
    "target": "combadge", "target_part": "", "target_interior": "",
    "manner": "touch", "relation": "surface", "motion": "settled",
    "detail": "worn on chest", "unasserted": 0,
    "contact_id": "contact:1c66c459972fe61b635f",
}

# --- recorded, chat 98 turn 27 --------------------------------------------
RUN98_TURN27_SCENE = {
    "attire": {
        "Sabine Oyelaran": {"wearing": ["combadge", "civilian clothing"],
                            "state": [], "regions": {}},
        "Data": {"wearing": [
            "gold and black Starfleet operations division uniform",
            "commbadge",
            "Starfleet uniform jumpsuit, operations gold shoulders",
            "black undertunic", "combadge",
            "two gold rank pips and one black"], "state": [], "regions": {}},
    },
    "entities": {},
    "positions": {"Sabine Oyelaran": "main_bridge", "Data": "main_bridge"},
    "contacts": [],
}

RUN98_TURN27_OPS = [
    {"op": "add", "actor": "Sabine Oyelaran", "actor_part": "shoulder",
     "target": "Data", "target_part": "shoulder", "manner": "stand",
     "relation": "surface", "motion": "settled"},
    {"op": "add", "actor": "Sabine Oyelaran", "actor_part": "shoulder",
     "target": "Data", "target_part": "shoulder", "manner": "settle",
     "relation": "surface", "motion": "settled"},
]


def _apply(scene, ops):
    scene = copy.deepcopy(scene)
    report = []
    apply_contact_ops(scene, copy.deepcopy(ops), report=report)
    return scene, report


# ---------------------------------------------------------------------------
# D-K / D-L: a worn garment is not a party to a contact
# ---------------------------------------------------------------------------

def test_recorded_worn_garment_endpoint_never_reaches_the_ledger():
    scene, report = _apply(RUN98_TURN22_SCENE, [RUN98_TURN22_OP])
    assert scene["contacts"] == []
    assert any("combadge" in line and "worn garment" in line
               for line in report), report


def test_the_refusal_says_what_was_missing():
    _, report = _apply(RUN98_TURN22_SCENE, [RUN98_TURN22_OP])
    line = next(line for line in report if "worn garment" in line)
    # The Director is told which channel owns the fact, exactly as the
    # placement and whole-body refusals already do.
    assert "detail" in line and "layer between two surfaces" in line


def test_the_stored_record_renders_no_sentence_at_all():
    # The render floor, for records written before the refusal existed. This
    # is the exact clause the player was handed, and it must not be produced.
    clause = contact_sensation(
        RUN98_TURN22_STORED_CONTACT, you="Sabine Oyelaran",
        scene=RUN98_TURN22_SCENE,
        label_for=lambda other: "someone")
    assert clause == ""


def test_a_worn_garment_is_recognised_from_the_wardrobe_ledger_alone():
    # No garment vocabulary, no word list: the scene's own ledger is the whole
    # evidence, so this holds for any wardrobe any story authors.
    assert _endpoint_is_worn_clothing(RUN98_TURN22_SCENE, "combadge")
    assert not _endpoint_is_worn_clothing(
        RUN98_TURN22_SCENE, "Sabine Oyelaran")


def test_a_part_slot_naming_a_shed_garment_is_clothing_not_anatomy():
    # 'uniform' resolves against her own shed clothing entity -- the garment
    # came off sixteen turns earlier and is a thing lying in another room.
    # Whether or not she is wearing it, it is not a place on her body.
    assert _part_is_clothing(RUN98_TURN22_SCENE, "Sabine Oyelaran", "uniform")
    assert not _part_is_clothing(
        RUN98_TURN22_SCENE, "Sabine Oyelaran", "shoulder")


def test_a_garment_part_slot_records_the_contact_against_the_body():
    # Cleared rather than refused: the contact may be real and written one
    # layer out, and an empty part is the ledger's own way of saying the whole
    # body is what touches.
    scene, report = _apply(RUN98_TURN22_SCENE, [
        dict(RUN98_TURN22_OP, target="Data", target_part="hand",
             manner="press")])
    assert len(scene["contacts"]) == 1
    assert scene["contacts"][0]["actor_part"] == ""
    assert any("clothing rather than a place on their body" in line
               for line in report), report


# ---------------------------------------------------------------------------
# D-L: a thing is not someone
# ---------------------------------------------------------------------------

def test_a_scene_thing_is_named_rather_than_minted_into_a_person():
    label = contact_thing_label(
        RUN98_TURN22_SCENE,
        "standard_starfleet_duty_uniform_teal_science_division_shoulders_"
        "sabine_oyelaran")
    assert label == ("standard Starfleet duty uniform "
                     "(teal science division shoulders)")


def test_a_body_is_never_vouched_for_as_a_thing():
    # The identity floor must still own every party that is a body -- this is
    # what keeps "someone" the answer for a person the observer cannot place.
    assert contact_thing_label(RUN98_TURN22_SCENE, "Sabine Oyelaran") == ""
    assert contact_thing_label(RUN98_TURN22_SCENE, "a stranger") == ""


# ---------------------------------------------------------------------------
# D-N: one claim, however many wordings
# ---------------------------------------------------------------------------

def test_a_refused_placement_is_not_rescued_by_its_synonym():
    scene, report = _apply(RUN98_TURN27_SCENE, RUN98_TURN27_OPS)
    assert scene["contacts"] == []
    assert any("dropped 'stand'" in line for line in report), report
    assert any("different claim" in line for line in report), report


def test_the_same_claim_stated_once_and_legally_still_stands():
    # The floor must SUBTRACT the refused claim and nothing else: a genuine
    # shoulder-to-shoulder contact with no placement wording beside it is a
    # contact, and both parties still feel it.
    scene, _ = _apply(RUN98_TURN27_SCENE, [RUN98_TURN27_OPS[1]])
    assert len(scene["contacts"]) == 1
    clause = contact_sensation(scene["contacts"][0], you="Sabine Oyelaran",
                               scene=scene, label_for=lambda other: str(other))
    assert clause == ("You feel Data's shoulder against your shoulder: "
                      "steady pressure, weight and shared warmth, continuous "
                      "while the contact holds")


def test_the_order_of_the_two_wordings_does_not_decide_the_outcome():
    scene, _ = _apply(RUN98_TURN27_SCENE, list(reversed(RUN98_TURN27_OPS)))
    assert scene["contacts"] == []


# ---------------------------------------------------------------------------
# D-L's other half: the touched THING rendered as a person.
#
# Stated exactly, because the difference matters. Chat 98 recorded six object
# contacts -- turn 9 hand->bar.surface, turn 16 hand->engineers_table.surface,
# turn 17 right hand->glass.exterior, turn 38 hand->table.surface,
# padd->table.surface and hand->padd.edge -- and replaying each one through
# the clause builder produces "You feel someone's surface against your hand
# it". FIVE of the six never reached a view in the run itself: none of those
# objects was ever minted as a scene entity, so none had a position, so
# contact hygiene pruned the record as cross-room before perception saw it.
# The one that DID reach a view was turn 22's, whose other party was a worn
# badge that had just been given a position.
#
# So this is not "six leaks in one run"; it is one leak and five records that
# a different, upstream gap happened to swallow. It is fixed here anyway, for
# the reason the register itself gives: a floor must not depend on a second
# defect to look correct. Both tiers under the display map are exercised
# below -- the entity name where the scene established the thing, and the
# body/thing split where it did not.
# ---------------------------------------------------------------------------

RUN98_TURN9_OP = {
    "op": "add", "actor": "Sabine Oyelaran", "actor_part": "hand",
    "target": "bar", "target_part": "surface", "manner": "rest",
    "relation": "surface", "motion": "settled",
}


def _identity_floor(scene, display_map):
    """The chain `agents/perception.py` builds, in the same order."""
    def label(other):
        return (display_map.get(str(other))
                or contact_thing_label(scene, other)
                or ("someone" if contact_endpoint_is_body(scene, other)
                    else "something"))
    return label


def test_a_touched_thing_the_scene_will_not_vouch_for_is_not_a_person():
    scene, _ = _apply(RUN98_TURN22_SCENE, [RUN98_TURN9_OP])
    clause = contact_sensation(
        scene["contacts"][0], you="Sabine Oyelaran", scene=scene,
        label_for=_identity_floor(scene, {}))
    assert "someone" not in clause
    assert clause.startswith("You feel something's surface against your hand")


def test_an_unplaceable_body_is_still_someone():
    # The floor must not be widened into a leak the other way: a person the
    # observer cannot name is still a person, and the scene says so because
    # bodies are the things that wear something.
    scene = copy.deepcopy(RUN98_TURN27_SCENE)
    scene, _ = _apply(scene, [
        {"op": "add", "actor": "Data", "actor_part": "hand",
         "target": "Sabine Oyelaran", "target_part": "wrist",
         "manner": "grip", "relation": "surface", "motion": "settled"}])
    clause = contact_sensation(
        scene["contacts"][0], you="Sabine Oyelaran", scene=scene,
        label_for=_identity_floor(scene, {}))
    assert clause == ("You feel someone's hand against your wrist: "
                      "steady pressure, weight and shared warmth, continuous "
                      "while the contact holds")
