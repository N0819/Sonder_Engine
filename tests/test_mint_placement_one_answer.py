"""One answer to "where does a thing this beat minted stand" (review
2026-09-07 B15).

The placement rule had two implementations at two times: the Director's
evidence pass and its unplaced warning read a mint with no `positions` entry
as nowhere -- routing a repair the objects hand cannot perform, because the
hand that owns `entities` cannot write `positions` -- while
`commit_scene_state._place_orphan_mints` stood the same thing in the room the
beat resolved the player into, after the beat was over. Measured live, chat
117 turn 78: `conduit_joints` was reported beyond perception and committed
into riser 13 in the same beat.

The rule that now holds: the placement is made in the Director's
deterministic floor, on the diff, so the omission audit, the warning, the
mid-turn merge and the commit read the same answer -- and which mints need a
room is asked of one function (`director_floors.unplaced_mints_needing_a_room`)
rather than listed twice.
"""

import time

import pytest

from agents.director import (_evidence_present, _unplaced_minted_entities,
                             place_unplaced_mints,
                             unplaced_mints_needing_a_room)
from world.spatial import merge_scene_with_diff


def _scene():
    return {"rooms": {"hall": {"name": "Hallway"},
                      "kitchen": {"name": "Kitchen"}},
            "positions": {"Wren": "kitchen"},
            "entities": {},
            "contained": {}}


def _diff():
    return {"positions": {"Wren": "kitchen"},
            "entities": {"kitchen_sink_tap": {"name": "kitchen sink tap",
                                              "kind": "fixture"}}}


def _omission():
    return {"category": "entities", "subject": "kitchen_sink_tap"}


def test_the_beat_places_its_own_mint_and_the_evidence_pass_then_sees_it():
    sc, sd = _scene(), _diff()
    # Before: three readers say nowhere -- the omission audit, the warning,
    # and the merge every later stage is composed from.
    assert _evidence_present(sd, _omission(), scene=sc) is False
    assert _unplaced_minted_entities(sc, sd) == ["kitchen_sink_tap"]

    assert place_unplaced_mints(sc, sd, "kitchen") == ["kitchen_sink_tap"]

    assert sd["positions"]["kitchen_sink_tap"] == "kitchen"
    assert _evidence_present(sd, _omission(), scene=sc) is True
    assert _unplaced_minted_entities(sc, sd) == []


def test_a_beat_that_cannot_say_where_it_is_places_nothing():
    """Inventing a room for a thing is worse than leaving it nowhere, and the
    warning is what stands in its place."""
    sc, sd = _scene(), _diff()
    assert place_unplaced_mints(sc, sd, "") == []
    assert place_unplaced_mints(sc, sd, None) == []
    assert "kitchen_sink_tap" not in sd["positions"]
    assert _unplaced_minted_entities(sc, sd) == ["kitchen_sink_tap"]


@pytest.mark.parametrize("record", [
    {"name": "the station voice", "kind": "computer", "ubiquitous": True},
    {"name": "the shaft", "kind": "portal",
     "state": {"link": ["hall", "kitchen"]}},
    {"name": "the crate", "kind": "object", "state": {"transit": "lift"}},
])
def test_the_classes_with_no_room_by_construction_are_not_given_one(record):
    sc, sd = _scene(), _diff()
    sd["entities"] = {"thing": record}
    assert unplaced_mints_needing_a_room(sc, sd) == []
    assert place_unplaced_mints(sc, sd, "kitchen") == []


def test_a_body_is_placed_by_the_machinery_that_walks_it_not_by_this_floor():
    """A body the scene already dresses is a body: it is walked into rooms by
    the movement machinery, and standing it in the beat's room would be a step
    nothing took."""
    sc, sd = _scene(), _diff()
    sc["attire"] = {"stranger": {"torso": [{"item": "a wet coat"}]}}
    sd["entities"] = {"stranger": {"name": "a stranger", "kind": "person"}}
    assert place_unplaced_mints(sc, sd, "kitchen") == []
    assert "stranger" not in sd["positions"]


def test_a_thing_a_body_is_holding_is_not_stood_on_the_floor():
    """A held thing whose holder has no room of his own is still held (review
    2026-09-07 B15).

    The merge derives a carried thing's room from its carrier only when some
    carrier in the chain resolves to one; when none does, the thing comes back
    from the unplaced list. Standing it in the beat's room then makes
    `contained` and `positions` two records of one fact, free to disagree -- a
    vial in the courier's hand rendered as lying on the floor for anyone to
    see and take. Asserted at BOTH call shapes, because the skip was carried
    by the commit's pass alone and the whole point of the shared function is
    that one answer serves both.
    """
    sc, sd = _scene(), _diff()
    sc["contained"] = {"vial": "courier"}
    sc["entities"] = {"courier": {"name": "the courier", "kind": "person"}}
    sd["entities"] = {"vial": {"name": "a glass vial", "kind": "object"}}

    # It has no room -- nothing resolves the courier to one -- and it is
    # still not this floor's to place.
    assert _unplaced_minted_entities(sc, sd) == ["vial"]
    assert unplaced_mints_needing_a_room(sc, sd) == []
    assert place_unplaced_mints(sc, sd, "kitchen") == []
    assert "vial" not in sd["positions"]

    # The commit's shape: the scene the beat ends with, handed in as `merged`.
    merged = merge_scene_with_diff(sc, sd)
    assert unplaced_mints_needing_a_room(None, sd, merged=merged) == []


def test_a_held_thing_is_skipped_under_any_label_it_answers_to():
    """`contained` is keyed by whatever the beat called the thing, so the id,
    the name and the aliases are all asked (review 2026-09-07 B15)."""
    for key in ("vial", "A Glass Vial", "the phial"):
        sc, sd = _scene(), _diff()
        sc["contained"] = {key: "courier"}
        sc["entities"] = {"courier": {"name": "the courier", "kind": "person"}}
        sd["entities"] = {"vial": {"name": "a glass vial", "kind": "object",
                                   "aliases": ["the phial"]}}
        assert unplaced_mints_needing_a_room(sc, sd) == [], key
        assert place_unplaced_mints(sc, sd, "kitchen") == [], key


def test_the_findings_own_shapes_are_untouched_by_the_carried_skip():
    """A thing nobody is holding is still placed: `conduit_joints` (chat 117
    turn 78) and `kitchen_sink_tap` are fixtures with no `contained` entry,
    and a transfer op whose destination resolves to nothing writes no
    containment either (review 2026-09-07 B15)."""
    sc, sd = _scene(), _diff()
    sc["contained"] = {"lantern": "Wren"}
    assert place_unplaced_mints(sc, sd, "kitchen") == ["kitchen_sink_tap"]
    assert sd["positions"]["kitchen_sink_tap"] == "kitchen"


def test_an_interior_the_merge_indexes_onto_the_mint_is_read_from_the_merge():
    """A vehicle's `interior_rooms` is written onto the entity BY THE MERGE,
    so the diff's own record says nothing about it and only the merged one
    does -- the commit read the merged record and the Director's list did
    not, which is the same two-answers shape one field down."""
    sc, sd = _scene(), _diff()
    sd["entities"] = {"lift_car": {"name": "the lift car", "kind": "vehicle"}}
    sd["rooms"] = {"lift_car_interior": {"name": "Lift Car",
                                         "parent_entity": "lift_car"}}
    assert unplaced_mints_needing_a_room(sc, sd) == []


def test_the_commit_finds_nothing_left_to_place_once_the_beat_has_placed_it(
        temp_db):
    """The two sites agree, and the placement is made once: the commit's
    orphan pass is the backstop for a diff that never met the floor."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist import commit

    sc, sd = _scene(), _diff()
    assert place_unplaced_mints(sc, sd, "kitchen") == ["kitchen_sink_tap"]

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Mint", "", time.time()))
    temp_db.wset(cid, "scene", _scene())
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Mint", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": sd}
    scene_after = commit.prepare_scene_commit(ctx)["scene"]

    assert scene_after["positions"]["kitchen_sink_tap"] == "kitchen"
    assert not [n for n in temp_db.wget(cid, "engine_notices", [])
                if "minted with no room" in n]
