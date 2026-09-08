"""The author's register reaches the stage that writes the page (review D10).

`style_guide.tone` is one sentence the author wrote about how their story
reads. It rode the Director's payload -- where it shapes what the engine
INVENTS, and where nobody writes prose -- and never reached the narrator, so
the only style input the page ever had was the install-wide `exemplars` list
and every story on one machine was written toward the same few samples.

A REGISTER STATEMENT, NOT A GENRE SWITCH: it says how the page sounds, grants
no fact and overrides nothing the view carries. Absent when unset, which is
the `narration_tense` routing one field up -- a story whose author expressed
no opinion must get exactly the payload it got before this field existed.
"""

from __future__ import annotations

import json
import time

from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from story.scene import normalize_style_guide

import agents.narration as narration


DRAFT = ("You push through the door. The corridor beyond stretches away "
         "into a grey light. Your hand finds the rail and holds it.")


def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Test", "", time.time()))


def _ctx(temp_db, *, guide=None, idx=3):
    cid = _chat(temp_db)
    if guide is not None:
        wset(cid, "style_guide", normalize_style_guide(guide))
    scene = {"rooms": {"r1": {"name": "Hall", "notes": "a hall"}},
             "positions": {"Player": "r1"}, "entities": {}}
    temp_db.wset(cid, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=idx, player_input="hi",
                      created=time.time()),
        cast=[{"id": 1, "sheet": json.dumps(default_character_data("Mara")),
               "cstate": "{}", "status": "active"}],
        input="I push through the door.")
    ctx._extra["outcome_scene"] = scene
    ctx["_player_room"] = "r1"
    ctx["director_interpret"] = {"sequence": [], "speech": None}
    ctx["perception_outcome"] = {"views": {"player": "The hall is quiet."}}
    ctx["perception_establish"] = {"views": {"player": "The hall is quiet."}}
    return ctx


def _payload(temp_db, monkeypatch, *, guide=None, idx=3):
    captured = {}

    def _fake_agent_json(step_key, model_key, prompt, payload, **kw):
        captured["payload"] = payload
        return {"prose": DRAFT, "new_specifics": []}

    monkeypatch.setattr(narration, "_agent_json", _fake_agent_json)
    monkeypatch.setattr(narration, "validate_llm_output",
                        lambda key, out: (out, []))
    narration.narrator(_ctx(temp_db, guide=guide, idx=idx), 0)
    return captured["payload"]


TONE = "Dry, procedural, close to the body. Short sentences."


def test_an_authored_tone_reaches_the_narrator(temp_db, monkeypatch):
    payload = _payload(temp_db, monkeypatch, guide={"tone": TONE})
    assert payload["register"] == TONE


def test_a_story_that_said_nothing_carries_no_key(temp_db, monkeypatch):
    """Absence is the contract, not an empty string: an always-present blank
    key teaches the model to skip it and invites it to choose."""
    assert "register" not in _payload(temp_db, monkeypatch)
    assert "register" not in _payload(temp_db, monkeypatch,
                                      guide={"avoid": "no guns"})


def test_it_reaches_the_opening_turn_too(temp_db, monkeypatch):
    """The scene-opening beat is where a register is established, so it is
    the one beat this must not miss."""
    payload = _payload(temp_db, monkeypatch, guide={"tone": TONE}, idx=0)
    assert payload["scene_opening"] is True
    assert payload["register"] == TONE


def test_the_dial_is_read_fresh_so_it_can_be_turned_mid_story(temp_db):
    """Same standing as the tense dial beside it: read per turn through
    `style_guide`, so an edit applies to the next beat without a restart."""
    cid = _chat(temp_db)
    assert narration._story_register(cid) == ""
    wset(cid, "style_guide", normalize_style_guide({"tone": TONE}))
    assert narration._story_register(cid) == TONE
    wset(cid, "style_guide", normalize_style_guide({"tone": "  "}))
    assert narration._story_register(cid) == ""
