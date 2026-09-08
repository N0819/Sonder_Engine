"""A folded mint's key is gone from the whole beat, not just from the scene
(review 2026-09-07 A67).

`_fold_duplicate_mints` redirects a mint naming a thing the scene already
holds onto the record that exists -- the room ledger's `dedup_minted_rooms`
floor, applied to entities. It did that to the merged scene's `entities` and
`positions` and stopped there. Everything else this beat commits still named
the key it had just retired:

* the PREPARED DIFF, which `commit_world_entities` projects into
  `world_entities` row by row. The folded key had no merged entity behind it,
  so `_projected` fell back to the raw diff entry and INSERTed a phantom
  normalized row -- and `_entity_alias_map` reads those rows, so the phantom
  could then be picked as the canonical anchor for the thing it was folded
  into;
* every MERGED LEDGER the beat's own merge had already written it into: a
  station, a pose's `relative_to`, a contact's `target`, a containment's
  `in`.

The rule that now holds: the fold produces renames, and
`_apply_entity_renames` -- the sibling of
`commit_room_registry._apply_room_renames` -- rewrites every reference to a
folded key in the diff and in the scene, wherever it sits. Stated as a class
rather than per channel: the key was minted by THIS beat, so any string in
this beat's output equal to it is a reference to the thing it was folded into.
"""

from __future__ import annotations

import time

from persist import commit
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Buzzers", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 2, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Buzzers", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=2, player_input="",
                      created=time.time()),
        cast=[], input="")


def _standing():
    """Flat 4B, 2026-09-05 turn 2: a buzzer already sounding in the hallway."""
    return {"name": "door buzzer", "kind": "device",
            "aliases": ["intercom_buzzer"], "state": {"running": True}}


def _prev():
    return {"rooms": {"hallway": {"name": "Hallway"}},
            "positions": {"Wren": "hallway", "door_buzzer": "hallway"},
            "entities": {"door_buzzer": _standing()}}


def _merged(prev):
    """The scene as the beat's own merge left it: the mint landed everywhere
    a subject-keyed ledger takes a subject."""
    return {
        "rooms": dict(prev["rooms"]),
        "positions": {**prev["positions"], "intercom_buzzer": "hallway"},
        "entities": {**prev["entities"],
                     "intercom_buzzer": {"name": "intercom buzzer",
                                         "kind": "device"}},
        "stations": {"intercom_buzzer": {"at": "hallway", "near": ["Wren"]},
                     "Wren": {"at": "hallway", "near": ["intercom_buzzer"]}},
        "poses": {"Wren": {"posture": "standing",
                           "relative_to": "intercom_buzzer"}},
        "contained": {"intercom_buzzer": {"in": "Wren", "mode": "held"}},
        "contacts": [{"actor": "Wren", "target": "intercom_buzzer",
                      "manner": "grip"}],
    }


def _diff():
    return {"entities": {"intercom_buzzer": {"name": "intercom buzzer",
                                             "kind": "device"}},
            "positions": {"intercom_buzzer": "hallway"},
            "inventory_ops": [{"op": "transfer", "object_id": "some_note",
                               "from_id": "Wren",
                               "to_id": "intercom_buzzer"}]}


def test_the_diff_no_longer_names_the_folded_key(temp_db):
    ctx = _ctx(temp_db)
    prev, diff = _prev(), _diff()
    sc = _merged(prev)

    folded = commit._fold_duplicate_mints(ctx, ctx.chat.id, sc, prev, diff)

    assert folded == [("intercom_buzzer", "door_buzzer")]
    # The phantom `world_entities` row's whole source.
    assert "intercom_buzzer" not in diff["entities"]
    assert "door_buzzer" in diff["entities"]
    assert "intercom_buzzer" not in diff["positions"]
    assert diff["inventory_ops"][0]["to_id"] == "door_buzzer"


def test_the_merged_ledgers_no_longer_name_it(temp_db):
    ctx = _ctx(temp_db)
    prev, diff = _prev(), _diff()
    sc = _merged(prev)

    commit._fold_duplicate_mints(ctx, ctx.chat.id, sc, prev, diff)

    assert "intercom_buzzer" not in sc["entities"]
    assert "intercom_buzzer" not in sc["positions"]
    assert "intercom_buzzer" not in sc["stations"]
    assert sc["stations"]["Wren"]["near"] == ["door_buzzer"]
    assert sc["poses"]["Wren"]["relative_to"] == "door_buzzer"
    assert "intercom_buzzer" not in sc["contained"]
    assert sc["contained"]["door_buzzer"]["in"] == "Wren"
    assert sc["contacts"][0]["target"] == "door_buzzer"


def test_the_survivors_own_entry_wins_wherever_the_two_meet(temp_db):
    """A rename that lands two entries on one key keeps the standing one: the
    mint's fields were already folded onto the survivor by the loop above, so
    what is left is a leftover reference, and dropping it is what "there is
    one of these" means. Order must not decide it -- a dict may carry the mint
    before or after the record it folds into."""
    ctx = _ctx(temp_db)
    prev = _prev()
    sc = _merged(prev)
    sc["stations"] = {"intercom_buzzer": {"at": "hallway", "near": []},
                      "door_buzzer": {"at": "front_step", "near": []}}
    diff = _diff()
    diff["positions"] = {"intercom_buzzer": "hallway",
                         "door_buzzer": "front_step"}

    commit._fold_duplicate_mints(ctx, ctx.chat.id, sc, prev, diff)

    assert sc["stations"] == {"door_buzzer": {"at": "front_step", "near": []}}
    assert diff["positions"] == {"door_buzzer": "front_step"}


def test_a_room_answering_to_the_same_token_is_not_renamed(temp_db):
    """The walk matches a bare string, so the room ledger is left to
    `_apply_room_renames`: room ids and entity ids are different namespaces
    and a fold in one must not reach into the other."""
    ctx = _ctx(temp_db)
    prev, diff = _prev(), _diff()
    sc = _merged(prev)
    sc["rooms"]["intercom_buzzer"] = {"name": "a room that shares the token"}
    diff["rooms"] = {"intercom_buzzer": {"name": "a room"}}
    diff["remove_rooms"] = ["intercom_buzzer"]

    commit._fold_duplicate_mints(ctx, ctx.chat.id, sc, prev, diff)

    assert "intercom_buzzer" in sc["rooms"]
    assert "intercom_buzzer" in diff["rooms"]
    assert diff["remove_rooms"] == ["intercom_buzzer"]
