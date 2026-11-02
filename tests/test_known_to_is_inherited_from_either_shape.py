"""Who was told the truth carries onto a superseding disguise -- on the
commit's own call path, and in whichever shape either row was written.

KNOWN_TO IS INHERITED (`commit_entities._supersede_disguises`): a superseding
row that does not restate its audience is saying nothing, not "nobody knows
any more" -- the chat 74 defect, where the one character who had been told
was the only one fooled.

Two defects, one measured by the review and one found fixing it (2026-11-01):

  * THE INHERITANCE NEVER RAN. `commit_world_entities` hands the helper the
    transaction's sqlite3 CONNECTION, which has `execute` but no
    `fetchall`/`fetchone`, and the helper fetched from the object it was
    given behind a `hasattr` guard written for a recording test stub -- so
    on every live beat the guard skipped the read and nothing was carried.
    Reproduced through `commit_world_entities` on a scratch database: a
    state-shaped superseding row came back with `known_to: []` and the row
    naming The Doctor deactivated. The review's own repro (`checks.py` §3)
    passed a cursor, which is why it saw the rule work.
  * ONE SHAPE OF TWO (persist_scene_entities F10). The reader
    (`story.scene.disguises_from_rows`) takes a field from `state` OR the
    payload's top level; the writer read and wrote `state` only, so a flat
    superseding row inherited nothing even with a cursor. 0 of 30 disguise
    rows in the owner's corpus are flat.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_world_entities
from story.scene import active_disguises


def _ctx(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0.0)")
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 3, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="t", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=3, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}}
    return ctx


def _told(temp_db, chat_id, payload):
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,1)",
        ("told", chat_id, "Hinami", "physical_disguise", 100.0,
         json.dumps(payload)))


def _commit(ctx, cond):
    commit_world_entities(ctx, 0, prepared={"diff": {"conditions": {
        "new": [dict(cond, started_at_seconds=200.0)]}}})
    return active_disguises(ctx.chat.id)["hinami"]


STATE_TOLD = {"subject_id": "Hinami", "kind": "physical_disguise",
              "state": {"presented_appearance": "an old form",
                        "known_to": ["The Doctor"]}}


def test_a_superseding_row_inherits_on_the_commits_own_path(temp_db):
    ctx = _ctx(temp_db)
    _told(temp_db, ctx.chat.id, STATE_TOLD)
    live = _commit(ctx, {"subject_id": "Hinami", "kind": "physical_disguise",
                         "state": {"presented_appearance": "a new form"}})
    assert live["presented_appearance"] == "a new form"
    assert live["known_to"] == ["The Doctor"], \
        "the told observer is fooled again"


def test_a_flat_superseding_row_inherits(temp_db):
    ctx = _ctx(temp_db)
    _told(temp_db, ctx.chat.id, STATE_TOLD)
    live = _commit(ctx, {"subject_id": "Hinami", "kind": "physical_disguise",
                         "presented_appearance": "a new form"})
    assert live["presented_appearance"] == "a new form"
    assert live["known_to"] == ["The Doctor"]


def test_a_flat_superseded_row_hands_its_audience_on(temp_db):
    ctx = _ctx(temp_db)
    _told(temp_db, ctx.chat.id, {
        "subject_id": "Hinami", "kind": "physical_disguise",
        "presented_appearance": "an old form", "known_to": ["Marta"]})
    live = _commit(ctx, {"subject_id": "Hinami", "kind": "physical_disguise",
                         "state": {"presented_appearance": "a new form"}})
    assert live["known_to"] == ["Marta"]


def test_a_row_that_names_its_own_audience_keeps_it(temp_db):
    """Authoritative in either shape, including when it names a smaller
    one."""
    ctx = _ctx(temp_db)
    _told(temp_db, ctx.chat.id, STATE_TOLD)
    live = _commit(ctx, {"subject_id": "Hinami", "kind": "physical_disguise",
                         "presented_appearance": "a new form",
                         "known_to": ["Marta"]})
    assert live["known_to"] == ["Marta"]


def test_an_ending_inherits_nothing(temp_db):
    ctx = _ctx(temp_db)
    _told(temp_db, ctx.chat.id, STATE_TOLD)
    commit_world_entities(ctx, 0, prepared={"diff": {"conditions": {
        "new": [{"subject_id": "Hinami", "kind": "physical_disguise",
                 "active": 0}]}}})
    assert "hinami" not in active_disguises(ctx.chat.id)
