"""D9 (review 2026-09-07): the page is told how long the beat is.

Measured in the descent run: four consecutive beats of one bare corridor
written at full scene length, and a ten-minute window rendered at
two-minute grain. The Director already declares the span -- `state_diff.time`
carries `mode` ('action' | 'time_skip') and `duration_seconds`, and
`world.mechanics` owns that vocabulary -- and no narrator field carried it,
so the writer had nothing to distinguish a beat to SUMMARISE from a beat to
play as a scene.

`beat_time` is the data half; the sheet paragraph telling the narrator what
to do with a `time_skip` landed 2026-09-08 and is pinned at the foot of this
file, in both packs. The field is read verbatim from the resolve
and is ABSENT rather than guessed -- no time block, no `beat_time`; a
malformed one (the shape is a dict by schema and a scalar in the wild) is
not read at all; a block that declares its span only by endpoints carries
no duration, because turning endpoints into an advance is
`world.mechanics.read_time_diff`'s arithmetic and it needs a clock this
payload does not hold.
"""

from __future__ import annotations

import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from language_runtime import raw_card


def _payload(temp_db, monkeypatch, resolve):
    """The narrator payload for one ordinary beat with this resolve."""
    import agents.narration as narration

    player = "The Stranger"
    scene = {"attire": {}, "positions": {player: "room_a"},
             "rooms": {"room_a": {"name": "Room A", "notes": "a corridor"}},
             "entities": {}}
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Clock", "", time.time()))
    temp_db.wset(cid, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Clock", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=3, player_input="I walk on.",
                      created=time.time()),
        cast=[], input="I walk on.")
    ctx._extra["outcome_scene"] = scene
    ctx["_player_room"] = "room_a"
    ctx["director_interpret"] = {"sequence": [], "speech": None}
    ctx["perception_outcome"] = {"views": {"player": "The corridor is bare."}}
    if resolve is not None:
        ctx["director_resolve"] = resolve
    captured = {}

    def _fake_agent_json(step_key, model_key, prompt, payload, **kw):
        captured["payload"] = payload
        return {"prose": "You walk on.", "new_specifics": []}

    monkeypatch.setattr(narration, "_agent_json", _fake_agent_json)
    monkeypatch.setattr(narration, "validate_llm_output",
                        lambda key, out: (out, []))
    narration.narrator(ctx, 0)
    return captured["payload"]


def test_a_declared_span_reaches_the_page(temp_db, monkeypatch):
    payload = _payload(temp_db, monkeypatch, {
        "resolved_event": "You walk the corridor.",
        "state_diff": {"time": {"mode": "time_skip", "duration_seconds": 600,
                                "explicit": True,
                                "display_advance": "ten minutes later"}}})
    assert payload["beat_time"] == {"mode": "time_skip",
                                    "duration_seconds": 600.0}


def test_an_action_beat_says_so(temp_db, monkeypatch):
    """The other half of the same distinction: an `action` beat is a scene,
    and the field says which kind of beat this is rather than only how long
    a skip was."""
    payload = _payload(temp_db, monkeypatch, {
        "resolved_event": "", "state_diff": {
            "time": {"mode": "action", "duration_seconds": 8}}})
    assert payload["beat_time"] == {"mode": "action", "duration_seconds": 8.0}


def test_no_time_block_no_field(temp_db, monkeypatch):
    """ABSENT, not empty: a key the model must read and discard argues for a
    rule with no referent, which is the reason `authored_body_parts` and
    `co_present_positions` are absent when they have nothing to say."""
    assert "beat_time" not in _payload(temp_db, monkeypatch, {
        "resolved_event": "", "state_diff": {}})
    assert "beat_time" not in _payload(temp_db, monkeypatch, {
        "resolved_event": "", "state_diff": {"positions": {}}})
    assert "beat_time" not in _payload(temp_db, monkeypatch, None)


def test_a_scalar_time_block_is_not_read(temp_db, monkeypatch):
    """`state_diff.time` is a dict by schema and has arrived as a bare
    string in the wild. A shape this cannot read yields no field at all --
    it never yields a `mode` of "later"."""
    for odd in ("later", 600, ["time_skip"], None):
        payload = _payload(temp_db, monkeypatch, {
            "resolved_event": "", "state_diff": {"time": odd}})
        assert "beat_time" not in payload, odd


def test_a_span_with_no_duration_carries_only_its_mode(temp_db, monkeypatch):
    """Endpoints are not a duration here. `read_time_diff` turns a block's
    absolutes into an advance and needs the story clock to do it; this
    payload has no clock, so it reports what the block SAID and nothing it
    would have had to compute."""
    payload = _payload(temp_db, monkeypatch, {
        "resolved_event": "", "state_diff": {
            "time": {"mode": "time_skip", "start_seconds": 100,
                     "end_seconds": 700}}})
    assert payload["beat_time"] == {"mode": "time_skip"}

    # And a duration with no mode is still a duration.
    payload = _payload(temp_db, monkeypatch, {
        "resolved_event": "", "state_diff": {
            "time": {"duration_seconds": "45"}}})
    assert payload["beat_time"] == {"duration_seconds": 45.0}

    # A block that says nothing this field can carry yields no field.
    payload = _payload(temp_db, monkeypatch, {
        "resolved_event": "", "state_diff": {
            "time": {"display_advance": "a while later"}}})
    assert "beat_time" not in payload


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_the_sheet_says_what_a_skipped_span_is(lang):
    """The other half of D9, landed 2026-09-08: the field is announced.

    A payload key no sentence explains is a field a reader may or may not
    honour. The paragraph states the distinction rather than the beats it was
    written for -- a skipped span is summary, an acted beat is a scene, and
    neither licenses an event the numbered deliveries do not carry.
    """
    text = raw_card(lang)["prompts"]["narrator"]
    assert "beat_time" in text
    assert "time_skip" in text and "duration_seconds" in text
    assert ("SUMMARY" in text) if lang == "en" else ("要約" in text)
