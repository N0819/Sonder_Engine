"""`world_entities` is a projection of the merged scene, including the things
the commit itself mints and folds after the beat's diff was written.

`commit_world_entities` projected `diff.entities` and deleted
`diff.remove_entities`, nothing else. Several passes of the commit add or
remove scene entities without writing either list: a planned thing stood up
where somebody stands (`materialize_plans_in_sight`), a cast body given its
record (`ensure_cast_entities`, which heals the standing scene in place), a
shed garment folded into its twin or reclaimed on re-wear (the attire folds),
and the merge's own key fold, which re-keys an id-keyed record onto its
display name -- after which the projection fell back to the raw diff and
UPSERTed a row for the folded-away id. `_mint_shed_garments` states the rule
the others broke: "an entity minted only here would live in the runtime scene
and be absent from the normalized table -- the one divergence Phase 3a exists
to prevent."

Measured (review 2026-11-01, persist_scene_entities F4): 11 of 1,069 rows in
9 chats named no entity any scene of their chat holds, one a folded twin; 85
of 1,208 scene entities in 25 chats had no row (that half is mostly the world
editor, F3, which is not this file's).
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_world_entities


def _ctx(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Test", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 4, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=4, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"resolved_event": "A quiet beat.",
                            "dialogue_log": [], "state_diff": {}}
    return ctx


def _row(temp_db, cid, eid):
    return temp_db.q("SELECT * FROM world_entities WHERE chat_id=? AND "
                     "entity_id=?", (cid, eid), one=True)


def _seed_row(temp_db, cid, eid, ent):
    temp_db.qi("INSERT INTO world_entities(entity_id,chat_id,kind,subtype,"
               "name,payload,created_turn_id) VALUES(?,?,?,?,?,?,?)",
               (eid, cid, ent.get("kind", "object"), "", ent.get("name", ""),
                json.dumps(ent), None))


LAMP = {"name": "Brass lamp", "kind": "object"}
TARDIS = {"name": "The TARDIS", "kind": "vehicle"}


def test_a_thing_the_commit_stood_up_gets_its_row(temp_db):
    ctx = _ctx(temp_db)
    cid = ctx.chat.id
    prev = {"entities": {"lamp": LAMP}}
    merged = {"entities": {"lamp": LAMP, "plan_tardis": TARDIS}}
    commit_world_entities(ctx, 0, prepared={
        "diff": {}, "prev_scene": prev, "scene": merged})
    row = _row(temp_db, cid, "plan_tardis")
    assert row is not None, "a planned thing stood up by the commit has no row"
    assert row["kind"] == "vehicle"


def test_a_record_the_commit_healed_into_the_scene_gets_its_row(temp_db):
    """`ensure_cast_entities` writes the cast record into the standing scene
    itself, so it is in `prev_scene` as well as the merged one; what is
    missing is the ROW."""
    ctx = _ctx(temp_db)
    cid = ctx.chat.id
    body = {"name": "Hinami", "kind": "person"}
    commit_world_entities(ctx, 0, prepared={
        "diff": {}, "prev_scene": {"entities": {"Hinami": body}},
        "scene": {"entities": {"Hinami": body}}})
    assert _row(temp_db, cid, "Hinami") is not None


def test_a_record_the_commit_folded_away_loses_its_row(temp_db):
    ctx = _ctx(temp_db)
    cid = ctx.chat.id
    jacket = {"name": "jacket", "kind": "object",
              "state": {"clothing": True, "shed": True, "worn_by": "Nia"}}
    _seed_row(temp_db, cid, "jacket_nia", jacket)
    _seed_row(temp_db, cid, "lamp", LAMP)
    commit_world_entities(ctx, 0, prepared={
        "diff": {}, "prev_scene": {"entities": {"jacket_nia": jacket,
                                                "lamp": LAMP}},
        "scene": {"entities": {"lamp": LAMP}}})
    assert _row(temp_db, cid, "jacket_nia") is None, \
        "a garment reclaimed on re-wear kept its row forever"
    assert _row(temp_db, cid, "lamp") is not None


def test_an_id_the_merge_folded_onto_a_name_mints_no_phantom(temp_db):
    ctx = _ctx(temp_db)
    cid = ctx.chat.id
    bramwell = {"name": "Bramwell", "kind": "person"}
    _seed_row(temp_db, cid, "Bramwell", bramwell)
    merged = {"name": "Bramwell", "kind": "person",
              "description": "a broad man in a leather apron"}
    commit_world_entities(ctx, 0, prepared={
        "diff": {"entities": {"char_9f13": {"name": "Bramwell",
                                            "description": merged[
                                                "description"]}}},
        "prev_scene": {"entities": {"Bramwell": bramwell}},
        "scene": {"entities": {"Bramwell": merged}}})
    assert _row(temp_db, cid, "char_9f13") is None, \
        "the folded-away id got a phantom row"
    row = _row(temp_db, cid, "Bramwell")
    assert json.loads(row["payload"])["description"] == merged["description"]


def test_a_direct_caller_without_a_merged_scene_is_unchanged(temp_db):
    """No merged scene, no scene-only changes to project: the diff alone, as
    before."""
    ctx = _ctx(temp_db)
    cid = ctx.chat.id
    commit_world_entities(ctx, 0, prepared={
        "diff": {"entities": {"lamp": LAMP}}})
    assert _row(temp_db, cid, "lamp") is not None
