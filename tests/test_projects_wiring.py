"""Projects, end to end: adopted in play -> commit -> back into the mind.

`tests/test_projects.py` covers the MECHANISM thoroughly -- the cap, the
displacement receipt, satisfaction criteria, tolerance of barren stretches,
weighting, the adoption deliberation, probation. Every one of those calls
`affect` directly.

Nothing covered the WIRING, and the wiring is what an unrelated change
breaks. A project is EARNED, not authored: the character emits
`project_ops: adopt` mid-play, `commit.py` applies the ops and rebuilds
`interior` from scratch each beat, and `agents/character.py` hands the
result back as `self.projects` on the next one. Three seams, none of them
exercised by the mechanism tests, and a break in any of them is silent --
the character still speaks, still sounds right, and simply never comes to
have a life's work.

A note on evidence, because the obvious query misleads. `engine.db` holds
zero adopted projects, and that is NOT the tier lying idle: the arms it was
built for and proved in ran on scratch databases, and the chats in the live
corpus predate it or never ran long enough to want one. The tier's real
evidence is the maze arms -- it is what carried NPCs through a maze without
touching their drives, which is the whole argument for a tier between the
eternal and the completable. What follows from that is simply that the live
database cannot catch a regression here, so these tests have to.
"""

from __future__ import annotations

import json
import time

from affect import apply_project_ops
from character_schema import default_character_data

SHRINE = "Every run ends at the shrine"
CRITERION = "the shrine road is walked end to end by someone other than me"


def test_a_project_can_be_adopted_in_play():
    """The intended surface: earned through an op, not read off a card."""
    live, former, warn = apply_project_ops(
        [], [], [{"op": "adopt", "project": SHRINE, "about": "world",
                  "satisfied_when": CRITERION}], 10)

    assert [p["project"] for p in live] == [SHRINE]
    assert former == []
    assert not [w for w in warn if "deliberation" in w]


def test_a_task_wearing_the_word_is_still_refused():
    """The floor under adoption. "Reach the shrine" restates itself as its
    own ending, which is a task; a project states what would end it OTHER
    than doing it once."""
    live, _former, warn = apply_project_ops(
        [], [], [{"op": "adopt", "project": "Reach the shrine",
                  "satisfied_when": "I reach the shrine"}], 10)

    assert live == []
    assert warn


def test_an_adopted_project_survives_the_commit_rebuild(temp_db):
    """`_interior_out` is rebuilt from scratch every beat, so both ledgers
    have to be carried through it explicitly -- the comment in `commit.py`
    says a beat would otherwise erase them. This is that, exercised: adopt,
    then run a beat that emits NO project ops at all."""
    live, former, _w = apply_project_ops(
        [], [], [{"op": "adopt", "project": SHRINE, "about": "world",
                  "satisfied_when": CRITERION}], 10)

    still_live, still_former, _w2 = apply_project_ops(live, former, [], 11)

    assert [p["project"] for p in still_live] == [SHRINE], (
        "a silent beat erased a project nobody closed")
    assert still_former == []


def test_the_character_payload_carries_what_they_adopted(temp_db, monkeypatch):
    """The seam that matters most, because its failure is invisible: what
    the mind is actually handed on the beat after it committed to
    something."""
    import agents.character as character
    from pipeline_context import ChatData, PipelineContext, TurnData

    adopted, _f, _w = apply_project_ops(
        [], [], [{"op": "adopt", "project": SHRINE, "about": "world",
                  "satisfied_when": CRITERION}], 10)
    assert adopted, "fixture is meaningless if the adoption itself failed"

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Rill", json.dumps(default_character_data("Rill")), "{}",
         time.time(), "u_rill"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active",
         json.dumps({"interior": {"projects": adopted, "former_projects": []}})))
    temp_db.wset(chat_id, "scene", {
        "location": "Road", "time": "day",
        "rooms": {"road": {"name": "Road", "adjacent": []}},
        "positions": {"Rill": "road", "The Stranger": "road"},
        "entities": {}, "attire": {}, "overlays": {}})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 11, "hello", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=11,
                      player_input="hello", created=time.time()),
        cast=cast, input="hello")
    ctx.perception_act = {"views": {str(char_id): "The road is quiet."}}

    seen = {}

    def fake(role, key, system, payload, **kw):
        seen["payload"] = payload
        return {"sequence": [], "speech": None, "action": None}

    monkeypatch.setattr(character, "_agent_json", fake)
    character.character_step(ctx, cast[0]["id"], nonce=0)

    assert "payload" in seen, "the character stage never ran"
    payload = seen["payload"]
    blob = json.dumps(payload)
    assert SHRINE in blob, (
        "the project never reached the mind that adopted it -- "
        f"payload keys: {sorted(payload)}")
