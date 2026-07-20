"""Regression tests for the speech-concealment leak found during live play:

agents/perception.py's deterministic dialogue-injection backstops
(perception_act's hear_level loop and perception_outcome's npc_dlog loop)
used to inject EVERY speech/dialogue_log entry into every in-range
perceiver's view based purely on physical distance, with no check of
visibility/conceal_from at all -- unlike the exactly parallel action-
handling code path, which already excluded visibility:'concealed'
elements. A concealed comm call or whispered aside was therefore
guaranteed to reach every hearing-range perceiver, including whoever it
was declared concealed from.

Fix: speech sequence elements and dialogue_log entries now carry their
own visibility/conceal_from (schemas.py), agents/director.py
deterministically stamps dialogue_log entries with the concealment of
their originating declaration (never trusting the director model to
transcribe it correctly), and both perception.py backstops skip
concealed entries -- exactly mirroring the pre-existing action_elems /
last_overt_by_actor concealment filters.
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_director_ctx(temp_db, character_results=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(default_character_data("Reya")), "{}", time.time(), "char_reya"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "day",
        "rooms": {"room1": {"name": "Room 1", "adjacent": []}},
        "positions": {"The Stranger": "room1", "Reya": "room1"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "whisper to my contact", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="whisper to my contact",
                      created=time.time()),
        cast=cast, input="whisper to my contact",
    )
    ctx.director_interpret = {
        "sequence": [{"type": "speech", "text": "The shipment arrives at midnight.",
                      "volume": "normal", "tone": "hushed",
                      "visibility": "concealed", "conceal_from": [char_id]}],
        "speech": None, "action": None,
        "flow": {"reactors": [char_id], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    if character_results:
        ctx.character_results = {char_id: character_results}
    return ctx, char_id


def test_director_resolve_stamps_concealment_from_player_sequence(temp_db, monkeypatch):
    """The director model's dialogue_log entry omits visibility/conceal_from
    (as live models reliably do) -- director_resolve must stamp it anyway,
    from the player's own declared sequence element, not trust the model."""
    import agents.director as director

    ctx, char_id = _make_director_ctx(temp_db)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "The Stranger", "exact_quote": '"The shipment arrives at midnight."',
            "volume": "normal", "intended_target": None, "tone": "hushed",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    entry = next(d for d in out["dialogue_log"] if "midnight" in d["exact_quote"])
    assert entry["visibility"] == "concealed"
    assert char_id in entry["conceal_from"]


def test_director_resolve_stamps_volume_from_player_sequence(temp_db, monkeypatch):
    """Live play (chat 10, turn 22) found a sibling bug to the concealment
    leak: the director model transcribed a whisper into dialogue_log as
    volume:'normal', which would let hear_level() carry a 200-meter-shaft
    whisper as if spoken normally. The same deterministic backstop that
    protects visibility/conceal_from must also protect volume."""
    import agents.director as director

    ctx, char_id = _make_director_ctx(temp_db)
    ctx.director_interpret["sequence"][0]["volume"] = "whisper"
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "The Stranger", "exact_quote": '"The shipment arrives at midnight."',
            "volume": "normal", "intended_target": None, "tone": "hushed",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    entry = next(d for d in out["dialogue_log"] if "midnight" in d["exact_quote"])
    assert entry["volume"] == "whisper"


def test_director_resolve_stamps_concealment_from_character_sequence(temp_db, monkeypatch):
    """Same backstop for an NPC's own concealed speech declaration."""
    import agents.director as director

    ctx, char_id = _make_director_ctx(
        temp_db,
        character_results={
            "name": "Reya", "speech": None, "action": None,
            "sequence": [{"type": "speech", "text": "Don't tell the Doctor.",
                          "volume": "normal", "tone": "low",
                          "visibility": "concealed", "conceal_from": ["the_doctor"]}],
        },
    )
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "Reya", "exact_quote": '"Don\'t tell the Doctor."',
            "volume": "normal", "intended_target": None, "tone": "low",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    entry = next(d for d in out["dialogue_log"] if "tell the Doctor" in d["exact_quote"])
    assert entry["visibility"] == "concealed"
    assert "the_doctor" in entry["conceal_from"]


def test_perception_act_does_not_inject_concealed_speech(temp_db, monkeypatch):
    """Reproduces the live leak (turn 130, chat 10): a concealed speech
    sequence element must never reach a perceiver's view via perception_
    act's deterministic hear_level backstop, regardless of physical
    proximity."""
    import agents.perception as perception

    ctx, char_id = _make_director_ctx(temp_db)
    ctx["_player_room"] = "room1"

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        return {"views": {str(p["id"]): f"You are in {p['room_name']}."
                          for p in payload["perceivers"]}}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)

    result = perception.perception_act(ctx, nonce=0)

    for pid, view in result["views"].items():
        assert "midnight" not in (view or ""), (
            f"concealed speech leaked into perceiver {pid}'s view via the "
            "deterministic hear_level backstop"
        )


def test_perception_outcome_does_not_inject_concealed_dialogue(temp_db, monkeypatch):
    """Same reproduction at the outcome stage: a dialogue_log entry marked
    visibility:'concealed' must never reach a perceiver's view via
    perception_outcome's deterministic npc_dlog backstop."""
    import agents.perception as perception

    ctx, char_id = _make_director_ctx(temp_db)
    ctx.director_resolve = {
        "resolved_event": "A quiet exchange passes unnoticed.",
        "dialogue_log": [{
            "speaker": "Reya", "exact_quote": '"The shipment arrives at midnight."',
            "volume": "normal", "intended_target": None, "tone": "hushed",
            "visibility": "concealed", "conceal_from": ["The Stranger"],
        }],
    }

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        return {"views": {str(p["id"]): f"You are in {p['room_name']}."
                          for p in payload["perceivers"]}}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)

    result = perception.perception_outcome(ctx, nonce=0)

    for pid, view in result["views"].items():
        assert "midnight" not in (view or ""), (
            f"concealed dialogue_log entry leaked into perceiver {pid}'s view "
            "via the deterministic npc_dlog backstop"
        )


# --- norm_sequence concealment normalization (interpret -> perception_act path) ---
# These cover the SECOND leak found during the Meridian demo run: norm_sequence
# rebuilt speech elements WITHOUT visibility/conceal_from, so a line the director
# marked concealed was re-emitted overt and leaked at the onset perception pass;
# and weaker models mark a concealed ACTION but leave the co-declared SPEECH overt.

from agents.common import norm_sequence


def _run(seq):
    out = {"sequence": [dict(e) for e in seq]}
    norm_sequence(out)
    return out["sequence"]


def _speech(seq):
    return next(e for e in seq if e["type"] == "speech")


def test_explicit_concealed_speech_survives_normalization():
    seq = _run([
        {"type": "speech", "text": "secret", "volume": "whisper",
         "visibility": "concealed", "conceal_from": ["k", "v"]},
    ])
    sp = _speech(seq)
    assert sp["visibility"] == "concealed"
    assert sp["conceal_from"] == ["k", "v"]


def test_concealed_action_propagates_to_undermarked_speech():
    seq = _run([
        {"type": "action", "attempt": "open private channel", "visibility": "concealed",
         "conceal_from": ["k", "v"], "targets": ["a"]},
        {"type": "speech", "text": "secret", "volume": "whisper"},
    ])
    sp = _speech(seq)
    assert sp["visibility"] == "concealed"
    assert sp["conceal_from"] == ["k", "v"]


def test_backstop_subtracts_addressee_from_conceal_from():
    # addressee 'a' is both the action target and mistakenly in conceal_from;
    # the intended listener must not be made deaf.
    seq = _run([
        {"type": "action", "attempt": "aside", "visibility": "concealed",
         "conceal_from": ["k", "v", "a"], "targets": ["a"]},
        {"type": "speech", "text": "secret", "volume": "normal"},
    ])
    sp = _speech(seq)
    assert sp["visibility"] == "concealed"
    assert "a" not in sp["conceal_from"]
    assert sp["conceal_from"] == ["k", "v"]


def test_explicit_loud_speech_stays_public_despite_concealed_action():
    # loud decoy line alongside a concealed act must NOT be over-concealed.
    seq = _run([
        {"type": "action", "attempt": "palm the vial", "visibility": "concealed",
         "conceal_from": ["k"], "targets": []},
        {"type": "speech", "text": "nothing to see here", "volume": "loud"},
    ])
    sp = _speech(seq)
    assert sp["visibility"] == "overt"
    assert sp["conceal_from"] == []


def test_explicitly_overt_speech_stays_public():
    seq = _run([
        {"type": "action", "attempt": "hide vial", "visibility": "concealed",
         "conceal_from": ["k"], "targets": []},
        {"type": "speech", "text": "open statement", "volume": "normal", "visibility": "overt"},
    ])
    assert _speech(seq)["visibility"] == "overt"


def test_no_concealed_action_leaves_speech_overt():
    seq = _run([{"type": "speech", "text": "hello", "volume": "normal"}])
    assert _speech(seq)["visibility"] == "overt"


def test_union_of_multiple_concealed_actions():
    # declaration order is not preserved by norm_sequence, so the backstop must
    # union conceal_from across ALL concealed actions, not just an adjacent one.
    seq = _run([
        {"type": "action", "attempt": "act1", "visibility": "concealed", "conceal_from": ["k"], "targets": []},
        {"type": "speech", "text": "secret", "volume": "mutter"},
        {"type": "action", "attempt": "act2", "visibility": "concealed", "conceal_from": ["v"], "targets": []},
    ])
    sp = _speech(seq)
    assert sp["visibility"] == "concealed"
    assert set(sp["conceal_from"]) == {"k", "v"}


def test_no_internal_raw_keys_leak_into_output():
    seq = _run([
        {"type": "speech", "text": "hi", "volume": "whisper",
         "visibility": "concealed", "conceal_from": ["k"]},
    ])
    for e in seq:
        assert "_raw_vis" not in e and "_raw_vol" not in e


# --- Cross-LLM robustness: SpeechVolume enum coercion ---
# background_react (and any speech-bearing step) used to hard-crash when a
# weaker model emitted an out-of-enum volume like "quiet"/"low"/"softly";
# these now coerce via normalize_speech_volume instead of ValidationError.

from schemas import validate_llm_output_strict as _vlos, SpeechElement, DialogueLogEntry


def test_speech_element_coerces_unknown_volume():
    assert SpeechElement(text="hi", volume="quiet").volume.value == "mutter"
    assert SpeechElement(text="hi", volume="bellowing").volume.value == "normal"
    assert DialogueLogEntry(speaker="x", exact_quote="q", volume="softly").volume.value == "mutter"


def test_director_interpret_out_of_enum_volume_does_not_crash():
    report = _vlos("director_interpret", {
        "kind": "dialogue", "sequence": [], "speech": "hello",
        "speech_volume": "hushed", "flow": {},
    })
    assert report.valid, report.errors
    assert report.output["speech_volume"] in ("whisper", "mutter", "normal", "loud", "shout")
