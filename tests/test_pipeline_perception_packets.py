"""The inspector projects archived evidence without rewriting a saved turn."""

import json

import pytest

from web.pipeline_views import saved_perception_packets


def observation(text, phase, **metadata):
    return {"phase": phase, "channel": "sight", "observed": {"text": text},
            **metadata}


def test_saved_stage_uses_the_same_packet_as_cognition():
    from agents.composer import perception_packet

    rows = [observation('A voice says, "Wait."', "event", channel="hearing",
                        actor="a voice", fidelity="partial", id="speech:1"),
            observation("Her cheeks look pinker.", "change", actor="the woman"),
            observation("She is beside the door.", "state", actor="the woman"),
            observation('A voice says, "Wait."', "event", channel="hearing",
                        actor="a voice", fidelity="partial", id="speech:2")]
    view = "\n".join(row["observed"]["text"] for row in rows)
    content = json.dumps({"views": {"player": view},
                          "observations": {"player": rows}})
    packet = saved_perception_packets(content)["player"]
    assert packet == perception_packet(rows, fallback_view=view)
    assert [row["id"] for row in packet["events"]] == ["speech:1", "speech:2"]
    assert [row["order"] for row in packet["events"]] == [1, 2]
    assert len(packet["changes_noticed"]) == len(packet["current_state"]) == 1


def test_each_observer_reads_only_their_own_admitted_evidence():
    safe = "Someone shifts nearby."
    removed = "The concealed person opens the safe."
    content = json.dumps({
        "views": {"player": safe, "72": removed, "73": None},
        "observations": {
            "player": [observation(safe, "event"), observation(removed, "event")],
            "72": [observation(removed, "event")],
            "73": [observation(removed, "event")],
            "not_in_views": [observation(removed, "event")]}})
    packets = saved_perception_packets(content)
    assert list(packets) == ["player", "72", "73"]
    assert removed not in json.dumps(packets["player"])
    assert removed in json.dumps(packets["72"])
    assert packets["73"] == {"events": [], "changes_noticed": [], "current_state": []}


def test_old_paragraphs_remain_context_and_old_actor_metadata_stays_scrubbed():
    safe = "A voice calls from the doorway."
    tail = "The room feels cold."
    content = json.dumps({
        "views": {"player": safe + "\n" + tail, "72": "An undivided old view."},
        "observations": {"player": [
            {"channel": "hearing", "actor": "Secret identity",
             "observed": {"text": safe}}]}})
    packets = saved_perception_packets(content)
    assert "actor" not in packets["player"]["events"][0]
    assert packets["player"]["unstructured_context"][0]["observed"]["text"] == tail
    assert packets["72"]["events"] == []
    assert packets["72"]["unstructured_context"][0]["observed"]["text"] == "An undivided old view."


@pytest.mark.parametrize("content", ["broken JSON", "null", "[]", "42",
                                        '{"views": []}', '{"views": {}}'])
def test_non_perception_output_has_no_display_projection(content):
    assert saved_perception_packets(content) is None


def test_manually_edited_observations_do_not_break_the_drawer():
    content = json.dumps({"views": {"player": "Still readable.", "72": "Older text."},
                          "observations": {
                              "player": [None, 3, {"phase": [], "observed": {"text": "Still readable."}}],
                              "72": 42}})
    packets = saved_perception_packets(content)
    for observer, text in [("player", "Still readable."), ("72", "Older text.")]:
        assert packets[observer]["events"] == []
        assert packets[observer]["unstructured_context"][0]["observed"]["text"] == text


@pytest.mark.parametrize("malformed_text", [42, ["a voice"]])
def test_non_string_observation_text_cannot_swallow_the_saved_paragraph(malformed_text):
    view = str(malformed_text)
    content = json.dumps({"views": {"player": view}, "observations": {
        "player": [observation(malformed_text, "event")]}})
    packet = saved_perception_packets(content)["player"]
    assert packet["events"] == []
    assert packet["unstructured_context"][0]["observed"]["text"] == view


def test_pipeline_api_projects_each_variant_and_never_rewrites_storage(temp_db, monkeypatch):
    from web import app

    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Inspector test", "", 1.0))
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                         (chat_id, 0, 1.0))
    step_id = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                         (turn_id, "perception_act", "Perception", 1))
    contents = ['{ "views": {"player": "Earlier prose."} }',
                json.dumps({"views": {"player": "A bell rings."},
                            "observations": {"player": [observation("A bell rings.", "event")]}}),
                "manually broken JSON"]
    for index, content in enumerate(contents):
        temp_db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,?)",
                   (step_id, content, float(index), int(index == 1)))
    # This stored turn is being inspected, not resumed. Keep the test scoped to
    # the endpoint's archive projection rather than the plan builder.
    monkeypatch.setattr(app, "_latest_turn_in_frame", lambda *args: None)
    before = [dict(row) for row in temp_db.q("SELECT * FROM variants ORDER BY id")]

    response = app.pipeline_get(turn_id)

    variants = response["steps"][0]["variants"]
    assert [variant["content"] for variant in variants] == contents
    assert variants[0]["perception_packets"]["player"]["unstructured_context"]
    assert variants[1]["perception_packets"]["player"]["events"][0]["order"] == 1
    assert "perception_packets" not in variants[2]
    assert [dict(row) for row in temp_db.q("SELECT * FROM variants ORDER BY id")] == before
