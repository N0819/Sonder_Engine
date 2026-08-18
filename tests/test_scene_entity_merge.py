"""A partial entity diff must not erase the rest of the entity record.

Found live auditing chat "Elevator Adventure branch 41" (turn 91). The
Director sent a pose-only update for two entities that had been committed
correctly one turn earlier. Both came back gutted, and every later turn
read the corrupted values back:

    "Blue Police Box"  kind vehicle,   container, interior_rooms [tardis_interior_001]
        -> "Tardis 001"     kind object, not a container, no interior
    "The Doctor"       kind character, aliases [Doctor, Theta Sigma, John Smith]
        -> "The Doctor 10"  kind object, empty description

Two causes compounding: `merge_scene_with_diff` replaced entities wholesale
(`entities.update(diff)`) where rooms got `_merge_room`, and validation had
already filled every absent field -- so the replacement looked complete,
including a `name` invented from the dict key by `_fill_entity_names`.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

from persist import commit
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.schemas import is_derived_entity_name, validate_llm_output_strict
from world.spatial import merge_scene_with_diff

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reproject_world_entities as reproject  # noqa: E402


def _scene():
    return {
        "rooms": {
            "west_chamber": {"name": "West Passage Widening", "adjacent": []},
            "tardis_interior_001": {"name": "TARDIS Interior",
                                    "parent_entity": "tardis_001",
                                    "adjacent": []},
        },
        "entities": {
            "tardis_001": {
                "name": "Blue Police Box", "kind": "vehicle",
                "description": "A battered blue police box.",
                "aliases": ["tardis", "box", "police box"],
                "container": True, "interior_rooms": ["tardis_interior_001"],
                "state": {"transit": {"phase": "docked"}, "materializing": True},
            },
            "the_doctor_10": {
                "name": "The Doctor", "kind": "character",
                "description": "A lean, energetic figure in a pinstripe suit.",
                "aliases": ["Doctor", "Theta Sigma", "John Smith"],
                "state": {"pose": "standing"},
            },
        },
        "positions": {"tardis_001": "west_chamber",
                      "The Doctor": "west_chamber"},
    }


def _pose_only_diff():
    """The exact shape the live Director sent: state, nothing else."""
    raw = {"resolved_event": "The Doctor steps closer.",
           "state_diff": {"entities": {
               "the_doctor_10": {"state": {"pose": "stepping closer"}},
               "tardis_001": {"state": {"materializing": False}}}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.valid, report.errors
    return report.output["state_diff"]


def test_pose_only_diff_keeps_the_whole_entity():
    merged = merge_scene_with_diff(_scene(), _pose_only_diff())

    doctor = merged["entities"]["the_doctor_10"]
    assert doctor["name"] == "The Doctor"
    assert doctor["kind"] == "character"
    assert doctor["description"].startswith("A lean")
    assert doctor["aliases"] == ["Doctor", "Theta Sigma", "John Smith"]

    tardis = merged["entities"]["tardis_001"]
    assert tardis["name"] == "Blue Police Box"
    assert tardis["kind"] == "vehicle"
    assert tardis["container"] is True
    assert tardis["interior_rooms"] == ["tardis_interior_001"]


def test_the_update_itself_still_lands():
    merged = merge_scene_with_diff(_scene(), _pose_only_diff())
    assert merged["entities"]["the_doctor_10"]["state"]["pose"] == \
        "stepping closer"
    # Sibling state keys survive a partial state write -- the TARDIS keeps
    # the transit block the dock-edge derivation reads...
    tardis_state = merged["entities"]["tardis_001"]["state"]
    assert tardis_state["transit"] == {"phase": "docked"}
    # ...while the key the diff DID carry is applied, false included.
    assert tardis_state["materializing"] is False


def test_a_deliberate_change_still_wins():
    """Silence is not an erasure, but an authored value is not silence."""
    diff = {"entities": {"the_doctor_10": {
        "name": "The Doctor (disguised)", "kind": "character",
        "description": "Now in a stolen lab coat.", "aliases": ["Smith"]}}}
    doctor = merge_scene_with_diff(_scene(), diff)["entities"]["the_doctor_10"]
    assert doctor["name"] == "The Doctor (disguised)"
    assert doctor["description"] == "Now in a stolen lab coat."
    assert doctor["aliases"] == ["Smith"]


def test_a_brand_new_entity_is_unaffected():
    diff = {"entities": {"sonic_screwdriver": {
        "name": "Sonic Screwdriver", "kind": "object", "portable": True}}}
    merged = merge_scene_with_diff(_scene(), diff)
    assert merged["entities"]["sonic_screwdriver"]["portable"] is True
    assert merged["entities"]["sonic_screwdriver"]["name"] == "Sonic Screwdriver"


def test_derived_name_detection():
    # The forms _fill_entity_names can invent, for the keys that hit live.
    assert is_derived_entity_name("the_doctor_10", "The Doctor 10")
    assert is_derived_entity_name("tardis_001", "Tardis 001")
    assert is_derived_entity_name("41b518dc08c3436f", "Object", kind="object")
    # A real name is not a placeholder, even on the same key.
    assert not is_derived_entity_name("the_doctor_10", "The Doctor")
    assert not is_derived_entity_name("tardis_001", "Blue Police Box")


# ---------------------------------------------------------------------------
# The same defect one layer down: the blob was repaired, its projection was
# not. `commit_world_entities` wrote the RAW validated diff into
# world_entities, so every default-filled field the merge above treats as
# silence landed on the durable row as an assertion. Measured on the live
# engine.db (480 rows, 471 of them still present in their scene blob):
#
#     15 rows named literally 'Object'   (3.1%)
#     19 rows whose name disagrees with the blob's
#     24 rows whose kind disagrees with the blob's
#
# and 12 of the 15 'Object' rows have a real name in the blob beside them --
# Hinami, The TARDIS, A Dalek, Green Tea Mochi, Plain Steel Spanner. The
# TARDIS row also reads kind='object' where the blob says 'vehicle', which is
# the field commit_world_entities' own vehicle-lorebook branch keys on.
# ---------------------------------------------------------------------------


def _chat_with_committed_scene(temp_db):
    """The world as the turn BEFORE the pose-only diff left it: the scene
    blob and its world_entities projection agreeing about both entities."""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Elevator Adventure branch 41", "", time.time()))
    scene = _scene()
    temp_db.wset(chat_id, "scene", scene)
    for entity_id, ent in scene["entities"].items():
        temp_db.qi(
            "INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,"
            "payload) VALUES(?,?,?,?,?,?)",
            (entity_id, chat_id, ent["kind"], "", ent["name"],
             json.dumps(ent, ensure_ascii=False)))
    return chat_id


def _ctx_for(temp_db, chat_id, state_diff):
    idx = 92 + temp_db.q("SELECT COUNT(*) c FROM turns WHERE chat_id=?",
                         (chat_id,), one=True)["c"]
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "wait", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Elevator Adventure branch 41",
                      persona_id=None, lorebook_id=None, scenario="",
                      created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx,
                      player_input="wait", created=time.time()),
        cast=[], input="wait")
    ctx.director_resolve = {"resolved_event": "The Doctor steps closer.",
                            "dialogue_log": [], "state_diff": state_diff}
    return ctx


def _row(temp_db, chat_id, entity_id):
    return temp_db.q(
        "SELECT kind,subtype,name,payload FROM world_entities "
        "WHERE chat_id=? AND entity_id=?", (chat_id, entity_id), one=True)


def test_pose_only_diff_does_not_gut_the_durable_row(temp_db):
    """The projection must not undo the repair the blob already has.

    `merge_scene_with_diff` refuses a validator-derived name and reads a
    schema default as silence; `commit_world_entities` then wrote the raw
    diff straight over the row, so the same pose-only beat that left the
    blob saying "Blue Police Box"/vehicle left world_entities saying
    "Tardis 001"/object. Two authorities, one of them repaired.
    """
    chat_id = _chat_with_committed_scene(temp_db)
    ctx = _ctx_for(temp_db, chat_id, _pose_only_diff())

    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_world_entities(ctx, "n1", prepared=prepared)

    tardis = _row(temp_db, chat_id, "tardis_001")
    assert tardis["name"] == "Blue Police Box"
    assert tardis["kind"] == "vehicle"
    payload = json.loads(tardis["payload"])
    assert payload["interior_rooms"] == ["tardis_interior_001"]
    assert payload["container"] is True
    # ...and the update the beat actually carried still landed.
    assert payload["state"]["materializing"] is False
    assert payload["state"]["transit"] == {"phase": "docked"}

    doctor = _row(temp_db, chat_id, "the_doctor_10")
    assert doctor["name"] == "The Doctor"
    assert doctor["kind"] == "character"
    assert json.loads(doctor["payload"])["aliases"] == \
        ["Doctor", "Theta Sigma", "John Smith"]


def test_a_direct_caller_gets_the_same_row(temp_db):
    """A caller that prepared no scene must not be the way back in.

    Reruns, replays and the narrower tests call this domain on its own, and
    with no merged scene to project the raw diff was the only thing here --
    which is precisely the corruption above.
    """
    chat_id = _chat_with_committed_scene(temp_db)
    ctx = _ctx_for(temp_db, chat_id, _pose_only_diff())

    commit.commit_world_entities(ctx, "n1")

    tardis = _row(temp_db, chat_id, "tardis_001")
    assert tardis["name"] == "Blue Police Box"
    assert tardis["kind"] == "vehicle"
    assert json.loads(tardis["payload"])["interior_rooms"] == \
        ["tardis_interior_001"]


def test_a_deliberate_rename_still_reaches_the_row(temp_db):
    """The guard is against a placeholder, never against the Director.

    A refusal wide enough to hold a real rename would freeze every entity's
    identity at whatever the first beat happened to call it.
    """
    chat_id = _chat_with_committed_scene(temp_db)
    ctx = _ctx_for(temp_db, chat_id, {"entities": {"tardis_001": {
        "name": "Scorched Police Box", "kind": "vehicle",
        "description": "Blistered down one side."}}})

    commit.commit_world_entities(ctx, "n1")

    tardis = _row(temp_db, chat_id, "tardis_001")
    assert tardis["name"] == "Scorched Police Box"
    assert json.loads(tardis["payload"])["description"] == \
        "Blistered down one side."
    # The rename is not an erasure of everything it did not mention.
    assert json.loads(tardis["payload"])["interior_rooms"] == \
        ["tardis_interior_001"]


def test_a_nameless_newcomer_still_gets_a_name(temp_db):
    """The fallback's own purpose survives the guard.

    `_fill_entity_names` exists so a missing name neither fails the turn nor
    shows the player a generated id like "10Ae6B6A11324780". An entity with
    no prior row has no real name to protect, so the placeholder stands and
    is corrected the moment anything names the thing.
    """
    chat_id = _chat_with_committed_scene(temp_db)
    raw = {"resolved_event": "A shape resolves out of the dark.",
           "state_diff": {"entities": {"41b518dc08c3436f": {
               "kind": "object", "state": {"held_by": "The Doctor"}}}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.valid, report.errors
    ctx = _ctx_for(temp_db, chat_id, report.output["state_diff"])

    commit.commit_world_entities(ctx, "n1")
    assert _row(temp_db, chat_id, "41b518dc08c3436f")["name"] == "Object"

    # ...and the first real name displaces it, on the row as in the blob.
    ctx2 = _ctx_for(temp_db, chat_id, {"entities": {"41b518dc08c3436f": {
        "name": "Sonic Screwdriver", "kind": "object"}}})
    commit.commit_world_entities(ctx2, "n2")
    row = _row(temp_db, chat_id, "41b518dc08c3436f")
    assert row["name"] == "Sonic Screwdriver"
    assert json.loads(row["payload"])["state"] == {"held_by": "The Doctor"}


# ---------------------------------------------------------------------------
# The sweep for rows already written. The fix above heals an entity the next
# time a beat touches it, which covers every story still being played and
# nothing in a story that has stopped -- and the mochi in chat 38 is never
# going to be picked up again. tools/reproject_world_entities.py re-derives
# the projection from the blob it is a projection of. Against the author's
# engine.db it moves 68 of 480 rows and takes 'Object' from 15 to 3; the 3 it
# leaves are named 'Object' in the blob too, so there is nothing to repair
# them to.
# ---------------------------------------------------------------------------


def _chat_with_row_and_blob(temp_db, row, blob_entity, *, frames=()):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Swept", "", time.time()))
    temp_db.qi(
        "INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,"
        "payload) VALUES(?,?,?,?,?,?)",
        ("41b518dc08c3436f", chat_id, row["kind"], "", row["name"],
         json.dumps(row.get("payload", {}), ensure_ascii=False)))
    temp_db.qi("INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
               (chat_id, "scene",
                json.dumps({"entities": {"41b518dc08c3436f": blob_entity}})))
    for i, entity in enumerate(frames, start=1):
        temp_db.qi(
            "INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
            (chat_id, f"scene\x1efr{i}",
             json.dumps({"entities": {"41b518dc08c3436f": entity}})))
    return chat_id


def _swept(temp_db, chat_id):
    con = sqlite3.connect(temp_db.DB)
    try:
        report = reproject.collect(con, chat=chat_id)
        reproject.apply(con, report["diverged"])
        after = reproject.collect(con, chat=chat_id)
    finally:
        con.close()
    assert not after["diverged"], "the sweep did not settle in one pass"
    return report


def test_the_sweep_repairs_a_row_the_blob_can_name(temp_db):
    """A story that has stopped never gets the beat that would heal it.

    Twelve of the fifteen live rows named 'Object' have a real name sitting
    in the blob beside them -- Hinami, The TARDIS, A Dalek -- so this is a
    re-derivation, not a guess about what the thing was called.
    """
    blob = {"name": "The TARDIS", "kind": "vehicle",
            "interior_rooms": ["tardis_interior_001"]}
    chat_id = _chat_with_row_and_blob(
        temp_db, {"name": "Object", "kind": "object"}, blob)

    _swept(temp_db, chat_id)

    row = _row(temp_db, chat_id, "41b518dc08c3436f")
    assert row["name"] == "The TARDIS"
    assert row["kind"] == "vehicle"
    assert json.loads(row["payload"])["interior_rooms"] == \
        ["tardis_interior_001"]


def test_the_sweep_never_mints_a_placeholder(temp_db):
    """A repair that could create the defect it repairs is not a repair.

    An id rekey can leave the durable row holding the better spelling, so the
    blob wins on every field except a name it would only be handing back a
    placeholder for.
    """
    chat_id = _chat_with_row_and_blob(
        temp_db, {"name": "Blue Police Box", "kind": "vehicle"},
        {"name": "Object", "kind": "vehicle"})

    _swept(temp_db, chat_id)

    assert _row(temp_db, chat_id, "41b518dc08c3436f")["name"] == \
        "Blue Police Box"


def test_frames_that_disagree_are_skipped_not_guessed(temp_db):
    """`scene` is frame-scoped and `world_entities` is not.

    One table, several blobs -- three of them live in the author's corpus.
    Which frame is authoritative is a question the engine answers per run,
    and a sweep that picked one would be deciding it by accident.
    """
    chat_id = _chat_with_row_and_blob(
        temp_db, {"name": "Object", "kind": "object"},
        {"name": "The TARDIS", "kind": "vehicle"},
        frames=({"name": "A Police Box", "kind": "vehicle"},))

    con = sqlite3.connect(temp_db.DB)
    try:
        report = reproject.collect(con, chat=chat_id)
    finally:
        con.close()

    assert not report["diverged"]
    assert [a["entity_id"] for a in report["ambiguous"]] == \
        ["41b518dc08c3436f"]
    assert _row(temp_db, chat_id, "41b518dc08c3436f")["name"] == "Object"
