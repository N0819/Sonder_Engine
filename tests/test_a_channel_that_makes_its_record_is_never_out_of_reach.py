"""A channel whose op makes its own record is never out of the encoder's reach.

`director_prose._RECORD_FACTS` keeps a channel off the decision model's
battery when the world holds none of the records it is about -- measured on
chat 153, the model said yes to them on beats with none. Right for a channel
whose every op names a record that already exists (a claim ratified, a thing
destroyed); wrong for one that MAKES its record: `crowd_ops` raises a crowd
with an empty `crowd_id`, `courier_ops` sends on a claim the sender makes up,
`telling_ops` passes on a `claim` no event backs, `artifact_ops` posts an
invented bill. The gate also took them out of `encode`'s requestable tools,
so a beat where onlookers first gather could not encode its crowd even when
the encoder asked for `crowd_ops` -- the request was dropped without a
record (audit of 2026-11-01, `agents_director_prose_movement_rooms` F4).

A channel that makes its record stays requestable whatever the world holds;
the question stays gated, as measured. A channel that only acts on a record
the world must already hold is gated whole, as before.
"""

from __future__ import annotations

import pytest

import agents.director as director
from agents import director_prose
from llm import decisions

from tests.director_fakes import _action_interp, _fake_agent, _make_ctx, _steps

NO_RECORDS = {"crowds_present": False, "couriers_present": False,
              "reports_carried": False, "unratified_claims_present": False,
              "notices_in_scene": False, "destructible_entity": False}


@pytest.mark.parametrize("channel", ["crowd_ops", "courier_ops", "telling_ops",
                                     "artifact_ops"])
def test_a_channel_that_makes_its_record_is_requestable_with_none_held(channel):
    assert channel not in director_prose.candidate_channels("resolve", NO_RECORDS)
    assert channel in director_prose.candidate_channels(
        "resolve", NO_RECORDS, requestable=True)


@pytest.mark.parametrize("channel", ["ratified_claims", "contradicted_claims",
                                     "destruction"])
def test_a_channel_about_a_record_the_world_must_hold_stays_gated(channel):
    assert channel not in director_prose.candidate_channels(
        "resolve", NO_RECORDS, requestable=True)


def test_the_first_crowd_a_beat_raises_widens_the_encoder(temp_db, monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "poses" else 0.0}
        for key in questions})
    first = {"events": [{"source_entity_id": "world", "event": "Onlookers gather.",
                         "item_names": ["onlookers"], "transforms": []}],
             "missing_tools": ["crowd_ops"]}
    second = {"events": [{"source_entity_id": "world", "event": "Onlookers gather.",
                          "item_names": ["onlookers"], "transforms": [
                              {"item": "onlookers", "patch": {"crowd_ops": [
                                  {"op": "set", "crowd_id": "", "room": "keeper_room",
                                   "band": "a handful", "composition": "fishermen",
                                   "mood": "curious"}]}}]}]}
    answers = iter([first, second])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Onlookers gather at the keeper's door."},
        "director_specialist": lambda payload: next(answers),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist",
                             "director_specialist"]
    assert "crowd_ops" in calls[1]["payload"]["requestable_tools"]
    encoder = out["orchestration"]["prose_contract"]["encoder"]
    assert encoder["missing_tools"] == ["crowd_ops"]
    assert "crowd_ops" in encoder["widened_to"]
