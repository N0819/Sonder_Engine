"""Narrator presentation separates delivered events from scene evidence."""

import json
import time

from agents import narration
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _row(number, text, phase, *, channel="sight", actor="", kind="action"):
    return {
        "observation_id": f"current:player:{number}",
        "channel": channel, "phase": phase, "actor": actor, "kind": kind,
        "observed": {"text": text}, "standing": phase == "state",
    }


def _view(rows):
    return " ".join(row["observed"]["text"] for row in rows)


def _ctx(temp_db, rows, *, turn_idx=3):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Presentation", "", time.time()))
    scene = {
        "rooms": {"hall": {"name": "Hall", "light": "lit"}},
        "positions": {"Player": "hall"},
    }
    temp_db.wset(chat_id, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Presentation", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=turn_idx,
                      player_input="", created=time.time()),
        cast=[], input="")
    ctx["_player_room"] = "hall"
    ctx._extra["outcome_scene"] = scene
    stage = "perception_establish" if turn_idx == 0 else "perception_outcome"
    ctx[stage] = {
        "views": {"player": _view(rows)},
        "observations": {"player": rows},
    }
    return ctx


def test_events_changes_and_state_are_disjoint_and_lossless():
    events = [
        _row(i, f"{'Alice' if i % 2 else 'Bob'} moves marker {i}.", "event",
             actor="Alice" if i % 2 else "Bob")
        for i in range(12)
    ]
    rows = [
        _row(12, "A brass lamp illuminates the hall.", "state"),
        _row(13, "The unfamiliar person's cheeks are flushed.", "change"),
        *events,
    ]
    fields = narration._narrator_perception_fields(rows, _view(rows))
    assert fields["present_scene"] == rows[0]["observed"]["text"]
    assert fields["changes_noticed"] == rows[1]["observed"]["text"]
    assert [event["text"] for event in fields["current_events"]] == [
        row["observed"]["text"] for row in events]
    assert [event["order"] for event in fields["current_events"]] == list(range(1, 13))
    assert [event["actor"] for event in fields["current_events"]] == [
        row["actor"] for row in events]
    for row in rows:
        assert json.dumps(fields).count(row["observed"]["text"]) == 1


def test_noticed_change_does_not_gain_a_chronological_event_number():
    change = _row(0, "The door is now open.", "change")
    assert narration._render_observed_events([change]) == ""
    fields = narration._narrator_perception_fields([change], _view([change]))
    assert fields["current_events"] == []
    assert fields["changes_noticed"] == "The door is now open."


def test_event_records_keep_speaker_type_and_degraded_delivery_explicit():
    rows = [
        _row(0, "Bob raises the latch.", "event", actor="Bob"),
        _row(1, 'Alice says: "Only if you hold the door."', "event",
             actor="Alice", channel="hearing", kind="speech"),
        _row(2, "Something moves beyond the doorway.", "event"),
    ]
    rows[-1].update(fidelity="ambiguous", ambiguity=0.75)
    events = narration._narrator_perception_fields(rows, _view(rows))["current_events"]
    assert events[0]["actor"] == "Bob" and events[0]["kind"] == "action"
    assert events[1] == {
        "order": 2, "actor": "Alice", "kind": "speech", "channel": "hearing",
        "fidelity": "rendered", "ambiguity": 0.15,
        "text": 'Alice says: "Only if you hold the door."',
    }
    assert events[2]["fidelity"] == "ambiguous"
    assert events[2]["ambiguity"] == 0.75
    assert "actor" not in events[2]
    assert [event["order"] for event in events] == [1, 2, 3]


def test_legacy_observations_keep_their_standing_boundary():
    rows = [
        {"observed": {"text": "The hall is quiet."}, "standing": True},
        {"observed": {"text": "A voice calls from outside."}},
    ]
    fields = narration._narrator_perception_fields(rows, _view(rows))
    assert fields["present_scene"] == "The hall is quiet."
    assert fields["current_events"][0]["text"] == "A voice calls from outside."
    assert fields["current_events"][0]["kind"] == "observation"
    assert "actor" not in fields["current_events"][0]
    assert fields["changes_noticed"] == ""


def test_unstructured_archive_is_not_given_invented_event_timing():
    legacy_view = 'Alice opens the gate. A voice says: "Follow me."'
    fields = narration._narrator_perception_fields([], legacy_view)
    assert fields == {
        "present_scene": "", "current_events": [], "changes_noticed": "",
        "unstructured_context": legacy_view,
    }


def test_scrubbed_rows_and_private_metadata_cannot_reenter_packet():
    safe = _row(0, 'You hear a voice say: "Stay by the door."', "event",
                channel="hearing", actor="a voice", kind="speech")
    safe["private_grounds"] = "SECRET_INTENT"
    safe["observed"]["private_vitals"] = "SECRET_VITALS"
    unsafe = _row(1, "SECRET_REMOVED_NAME opens the door.", "event")
    fields = narration._narrator_perception_fields([safe, unsafe], _view([safe]))
    encoded = json.dumps(fields)
    assert "SECRET" not in encoded
    assert fields["current_events"][0]["actor"] == "a voice"


def test_partial_archived_observations_keep_unstructured_safe_view_remainder():
    rows = [
        {"observed": {"text": "A lamp burns."}, "standing": True},
        {"observed": {"text": "SECRET_NAME moves. A door closes."}},
    ]
    fields = narration._narrator_perception_fields(
        rows, "A lamp burns. A door closes.")
    assert fields["present_scene"] == "A lamp burns."
    assert fields["unstructured_context"] == "A door closes."
    assert fields["current_events"] == []
    assert "SECRET_NAME" not in json.dumps(fields)


def test_player_self_act_is_retained_beside_observed_events():
    row = _row(0, "Someone closes the door.", "event")
    fields = narration._narrator_perception_fields(
        [row], _view([row]), [{"actor": "Player", "action": "raises a hand"}])
    events = fields["current_events"]
    assert events[0] == {"order": 1, "actor": "Player", "kind": "action",
                         "source": "reconciled_player_action", "text": "raises a hand"}
    assert events[1]["order"] == 2
    assert events[1]["text"] == "Someone closes the door."


def test_primary_payload_carries_each_sentence_once_and_keeps_full_fidelity_view(
        temp_db, monkeypatch):
    rows = [
        _row(0, "A lamp illuminates the hall.", "state"),
        _row(1, "The unfamiliar person's face is flushed.", "change"),
        _row(2, "The unfamiliar person raises one hand.", "event"),
        _row(3, 'You hear a voice say: "Wait by the door."', "event",
             channel="hearing", actor="a voice", kind="speech"),
    ]
    seen = {}

    def generate(payload, view, *args, **kwargs):
        seen.update(payload=payload, view=view, facts=kwargs["fidelity_facts"])
        return {"prose": "<p>Quiet.</p>", "new_specifics": []}, [], []

    monkeypatch.setattr(narration, "_generate_narration", generate)
    narration.narrator(_ctx(temp_db, rows), "test")
    payload = seen["payload"]
    assert payload["present_scene"] == rows[0]["observed"]["text"]
    assert payload["changes_noticed"] == rows[1]["observed"]["text"]
    for row in rows:
        delivered = [payload["present_scene"], payload["changes_noticed"],
                     *(event["text"] for event in payload["current_events"])]
        assert delivered.count(row["observed"]["text"]) == 1
    assert all("this_beat" not in entry
               for entry in payload["sensory_channels"].values())
    assert seen["view"] == _view(rows)
    assert seen["facts"]["observations"] == rows


def test_opening_and_extra_player_use_their_own_partition(temp_db, monkeypatch):
    rows = [_row(0, "A red curtain hangs here.", "state")]
    ctx = _ctx(temp_db, rows, turn_idx=0)
    captures = []

    def generate(payload, view, *args, **kwargs):
        captures.append((payload, view))
        return {"prose": "<p>Quiet.</p>", "new_specifics": []}, [], []

    monkeypatch.setattr(narration, "_generate_narration", generate)
    narration.narrator(ctx, "test")
    assert captures[-1][0]["present_scene"] == rows[0]["observed"]["text"]
    assert captures[-1][0]["current_events"] == []

    extra = [
        _row(0, "A blue curtain hangs here.", "state"),
        _row(1, "A bell rings above you.", "event", channel="hearing"),
    ]
    ctx.extra_players = [{"persona_id": 4, "name": "Companion", "input": ""}]
    ctx["perception_establish"]["views"]["extra:4"] = _view(extra)
    ctx["perception_establish"]["observations"]["extra:4"] = extra
    narration.narrator_extra(ctx, "test")
    payload, view = captures[-1]
    assert payload["present_scene"] == extra[0]["observed"]["text"]
    assert payload["current_events"][0]["text"] == "A bell rings above you."
    assert "red curtain" not in json.dumps(payload)
    assert view == _view(extra)


def test_exact_delivered_dialogue_tokens_still_use_full_view(monkeypatch):
    rows = [
        _row(0, "A gate stands open.", "state"),
        _row(1, 'You hear a voice say: "Wait by the door."', "event",
             channel="hearing"),
    ]
    seen = {}

    def call(role, model, prompt, payload, **kwargs):
        seen.update(payload)
        return {"prose": "<p>The voice answers: {{L1}}</p>", "new_specifics": []}

    monkeypatch.setattr(narration, "_agent_json", call)
    view = _view(rows)
    out, _, _ = narration._generate_narration(
        narration._narrator_perception_fields(rows, view), view, [], [])
    assert seen["dialogue_lines"] == [
        {"token": "{{L1}}", "line": "Wait by the door."}]
    assert '"Wait by the door."' in out["prose"]
    assert "{{L1}}" not in out["prose"]


def test_legacy_primary_and_extra_context_is_not_mislabeled_as_standing(
        temp_db, monkeypatch):
    ctx = _ctx(temp_db, [])
    legacy = 'A figure opens the gate. A voice says: "Follow me."'
    ctx["perception_outcome"]["views"]["player"] = legacy
    captures = []

    def generate(payload, view, *args, **kwargs):
        captures.append((payload, view))
        return {"prose": "<p>Quiet.</p>", "new_specifics": []}, [], []

    monkeypatch.setattr(narration, "_generate_narration", generate)
    narration.narrator(ctx, "test")
    payload, view = captures[-1]
    assert payload["unstructured_context"] == view == legacy
    assert payload["present_scene"] == ""
    assert payload["current_events"] == []

    extra_view = 'A figure shuts the window. A voice says: "Stay there."'
    ctx.extra_players = [{"persona_id": 4, "name": "Companion", "input": ""}]
    ctx["perception_outcome"]["views"]["extra:4"] = extra_view
    narration.narrator_extra(ctx, "test")
    payload, view = captures[-1]
    assert payload["unstructured_context"] == view == extra_view
    assert payload["present_scene"] == ""
    assert payload["current_events"] == []
    assert "Follow me" not in json.dumps(payload)
