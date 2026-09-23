"""The prose contract (agents/director_prose.py), end to end with stub models.

What is pinned is the ARCHITECTURE the contract exists for:

- the Director writes prose and nothing else; one encoder, assembled from
  the channels the decision model selected, writes the ordered events;
- the encoder's sheet carries exactly the selected channels' chunks;
- its events become the same ledger rows and the same folded `state_diff`
  the causal contract produced, through the same bind/validate/fold;
- the decision model failing grants every channel (fail-open);
- a tool the encoder names as missing buys ONE widened call, whose answer
  replaces the first;
- the causal contract stays the default.
"""

from __future__ import annotations

import pytest

import agents.director as director
from agents import director_prose
from llm import decisions

from tests.test_director_orchestration import (
    _action_interp,
    _fake_agent,
    _make_ctx,
    _steps,
)


POSITIONS_CHUNK = "A CHARACTER'S DECLARED DIRECTION IS THEIRS"
ATTIRE_CHUNK = "CLOTHING TRACKING"


@pytest.fixture
def prose_contract(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    asked = []

    def answer(state, questions):
        asked.append({"state": state, "questions": dict(questions)})
        return {key: {"type": "noul",
                      "noul": 0.95 if key in ("positions", "poses") else 0.02}
                for key in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    return asked


def _walk_events():
    return {
        "events": [
            {"source_entity_id": "character:1", "source_event_id": "x",
             "event": "Mara climbs the stair into the lamp room.",
             "observable": "climbs the stair", "speech": False,
             "targets": ["lamp_room"], "seconds": 20, "movement": None,
             "commitment": "asserted", "item_names": ["Mara"],
             "transforms": [{"item": "Mara",
                             "patch": {"positions": {"Mara": "lamp_room"}}}]},
            {"source_entity_id": "character:1", "source_event_id": "x",
             "event": "The lamp is cold.", "speech": True,
             "targets": ["The Stranger"], "volume": "loud", "seconds": 2,
             "commitment": "asserted", "item_names": ["Mara"],
             "transforms": []},
        ],
        "missing_tools": [], "missing_referents": [], "notes": [],
    }


def test_resolve_runs_author_then_one_encoder(temp_db, monkeypatch,
                                             prose_contract):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs the stair into the lamp "
                                    "room. \"The lamp is cold,\" she calls down."},
        "director_specialist": _walk_events(),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    # Two model calls: the author, then ONE encoder. No hand is called.
    assert _steps(calls) == ["director_prose", "director_specialist"]
    assert calls[0]["role"] == "director"
    assert calls[1]["role"] == "director_specialist"
    # The author's sheet is the prose sheet, not the causal one.
    assert "Convert event_inputs into ordered event ledgers" not in calls[0]["system"]
    assert '{"prose":' in calls[0]["system"]
    # The encoder got the prose and exactly the selected tools.
    sheet = calls[1]["system"]
    assert POSITIONS_CHUNK in sheet
    assert ATTIRE_CHUNK not in sheet
    assert calls[1]["payload"]["prose"].startswith("Mara climbs")
    assert calls[1]["payload"]["granted_tools"] == ["positions", "poses"]
    # Jev judged the prose.
    assert "Mara climbs the stair" in prose_contract[0]["state"]
    # The events became ordered rows; position is chronology.
    rows = out["ledgers"]
    assert [row["chrono_id"] for row in rows] == [1, 2]
    assert rows[0]["categories"] == ["positions"]
    assert "speech" in rows[1]["categories"]
    # The existing fold produced the engine input.
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"
    record = out["orchestration"]["prose_contract"]
    assert record["prose"].startswith("Mara climbs")
    assert record["jev"]["selected"] == ["positions", "poses"]
    assert out["orchestration"]["specialists"]["spatial"]["ran"] is True


def test_decision_model_failure_grants_every_channel(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")

    def boom(state, questions):
        raise decisions.DecisionError("unreachable")

    monkeypatch.setattr(decisions, "OVERRIDE", boom)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": _walk_events(),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    sheet = calls[1]["system"]
    assert POSITIONS_CHUNK in sheet and ATTIRE_CHUNK in sheet
    assert out["orchestration"]["prose_contract"]["jev"]["failed"]
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"


def test_a_missing_tool_buys_one_widened_call_that_replaces_the_first(
        temp_db, monkeypatch, prose_contract):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "poses" else 0.0}
        for key in questions})
    first = {"events": [{"source_entity_id": "character:1",
                         "event": "Mara climbs into the lamp room.",
                         "item_names": ["Mara"], "transforms": []}],
             "missing_tools": ["positions"]}
    answers = iter([first, _walk_events()])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": lambda payload: next(answers),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist",
                             "director_specialist"]
    assert POSITIONS_CHUNK not in calls[1]["system"]
    assert POSITIONS_CHUNK in calls[2]["system"]
    # Replaced, not merged: the second answer's two events are the beat.
    assert [row["chrono_id"] for row in out["ledgers"]] == [1, 2]
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"
    encoder = out["orchestration"]["prose_contract"]["encoder"]
    assert encoder["missing_tools"] == ["positions"]
    assert "positions" in encoder["widened_to"]


def test_a_thinner_widened_answer_never_replaces_the_first(temp_db, monkeypatch,
                                                          prose_contract):
    """Chat 153 turn 23: re-asked for one added tool, the encoder returned
    only the events that tool touched. The re-ask now sees its first answer,
    and a replacement with fewer events than the first loses."""
    first = dict(_walk_events(), missing_tools=["sensory_events"])
    thin = {"events": _walk_events()["events"][:1]}
    answers = iter([first, thin])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": lambda payload: next(answers),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert calls[2]["payload"]["previous_events"] == first["events"]
    assert [row["chrono_id"] for row in out["ledgers"]] == [1, 2]
    assert "widen_rejected" in out["orchestration"]["prose_contract"]["encoder"]


def test_events_become_rows_with_one_handle_per_thing():
    rows, transforms = director_prose.ledger_from_events([
        {"source_entity_id": "character:1", "event": "Mara lifts the tin.",
         "item_names": ["red tin"],
         "transforms": [{"item": "red tin", "patch": {"inventory_ops": [
             {"op": "transfer", "object_id": "tin", "to_id": "Mara"}]}}]},
        {"source_entity_id": "character:1", "event": "Keep it.",
         "speech": True, "item_names": [], "transforms": []},
        {"source_entity_id": "character:1", "event": "She sets down the Red Tin.",
         "look": "bench", "item_names": ["Red Tin"],
         "transforms": [{"item": "Red Tin", "patch": {
             "inventory_ops": [{"op": "transfer", "object_id": "tin",
                                "to_id": "room"}],
             "contact_ops": [{"op": "remove", "actor": "Mara"}]}}]},
    ])
    assert [row["chrono_id"] for row in rows] == [1, 2, 3]
    # One handle per thing, case-folded; the speaker stands in on a
    # thing-less spoken row.
    assert rows[0]["item_ids"] == rows[2]["item_ids"] == [1]
    assert rows[1]["item_names"] == ["character:1"]
    assert rows[0]["categories"] == ["inventory_ops"]
    assert rows[1]["categories"] == ["speech"]
    assert rows[2]["categories"] == ["inventory_ops", "contact_ops", "attention"]
    assert len(transforms[3]) == 1 and set(transforms[3][0]["patch"]) == {
        "inventory_ops", "contact_ops"}


def test_dispatch_splits_one_transform_across_its_owners(temp_db):
    class Ctx(dict):
        pass
    ctx = Ctx()
    rows, transforms = director_prose.ledger_from_events([
        {"source_entity_id": "character:1", "event": "Mara sets it down.",
         "item_names": ["tin"], "transforms": [{"item": "tin", "patch": {
             "inventory_ops": [{"op": "transfer"}],
             "contact_ops": [{"op": "remove"}]}}]}])
    ctx[director_prose.CTX_KEY] = {"transforms": transforms,
                                   "channels": ["inventory_ops"]}
    plan, answer_for = director_prose.dispatch(ctx, "resolve")
    assert plan["objects"]["scope"] == ["inventory_ops"]
    # contact_ops was written though not granted: still the encoder's work.
    assert plan["contact"]["scope"] == ["contact_ops"]
    assert plan["body"]["run"] is False
    objects = answer_for("objects", {"ledger_items": rows})
    contact = answer_for("contact", {"ledger_items": rows})
    assert objects["results"][0]["transforms"][0]["patch"] == {
        "inventory_ops": [{"op": "transfer"}]}
    assert contact["results"][0]["transforms"][0]["patch"] == {
        "contact_ops": [{"op": "remove"}]}
    assert objects["results"][0]["status"] == "encoded"


def test_interpret_runs_the_same_contract(temp_db, monkeypatch, prose_contract):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "The Stranger says, \"Quiet night.\""},
        "director_specialist": {"events": [
            {"source_entity_id": "persona:primary", "event": "Quiet night.",
             "speech": True, "item_names": ["The Stranger"],
             "transforms": []}]},
    }))
    ctx = _make_ctx(temp_db, player_input='"Quiet night."')
    out = director.director_interpret(ctx, nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist"]
    assert "input side of the beat" in calls[0]["system"]
    assert out["orchestration"]["prose_contract"]["stage"] == "interpret"
    assert any("speech" in (row.get("categories") or [])
               for row in out.get("ledgers") or [])


def test_authority_is_read_on_the_prose_and_never_retries(temp_db, monkeypatch,
                                                         prose_contract):
    """The prose Director keeps two limits; the readings that enforce them
    under the causal contract read its prose here, warn, and never call the
    causal Director back to rewrite."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room. "
                                    "\"I never liked this lighthouse,\" "
                                    "Mara mutters to herself."},
        "director_specialist": _walk_events(),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert "director_resolve" not in _steps(calls)
    assert _steps(calls) == ["director_prose", "director_specialist"]
    assert out.get("player_act_warnings"), (
        "an undeclared character line in the prose went unreported")


def test_the_resolve_is_told_what_the_player_already_did(temp_db, monkeypatch,
                                                         prose_contract):
    """Asserted human input is absent from event_inputs (it already entered
    the world). The causal Director only routed and never needed it; an
    author does, or it writes past it -- chat 153 turn 26, a player-asserted
    landing written over as continued flight. Both the author and the
    encoder receive it."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "The ship touches down."},
        "director_specialist": _walk_events(),
    }))
    interp = _action_interp()
    interp["causal_ledger"] = [
        {"chrono_id": 1, "event": "The Stranger feels the ship begin to land.",
         "commitment": "asserted", "categories": []},
        {"chrono_id": 2, "event": "The Stranger tries to force the door.",
         "commitment": "contestable", "categories": []},
    ]
    ctx = _make_ctx(temp_db, interp=interp)
    director.director_resolve(ctx, nonce=0)
    author, encoder = calls[0]["payload"], calls[1]["payload"]
    assert author["already_happened"] == "The Stranger feels the ship begin to land."
    assert encoder["already_happened"] == author["already_happened"]
    assert "already_happened" in calls[0]["system"]
    assert "already_happened" in calls[1]["system"]


def test_interpret_prose_is_what_already_happened(temp_db):
    ctx = _make_ctx(temp_db, interp={
        "orchestration": {"prose_contract": {"prose": "Hinami grips the bar."}},
        "causal_ledger": [{"event": "ignored", "commitment": "asserted"}]})
    assert director_prose.already_happened(ctx) == "Hinami grips the bar."


def test_the_causal_contract_stays_the_default(temp_db, monkeypatch):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": {"ledgers": []}}))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    director.director_resolve(ctx, nonce=0)
    assert _steps(calls)[0] == "director_resolve"
    assert "director_prose" not in _steps(calls)
