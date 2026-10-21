"""A spoken line reaches a mind through the hearing rule and nothing else.

Measured on the tavern probe (2026-10-20, chat 2 turn 8). The player called
across the taproom "Hollis! Two more of the dark, when you've a minute!",
and the encoder filed, besides the speech event, a `sensory_events` row ON
that speech event: {source: "Tamsin Reed", level: loud, detail: "a woman's
voice calling out across the taproom over the fiddle for two more dark
ales"}. Her own outcome view read it back to her as a stranger's voice; the
man beside her got her line and then the stranger's voice saying it again;
and the sound field carries a sound's `detail` whole through its room and
as a character beyond it, so the line's content ("for two more dark ales")
reached ears a wall or a din had kept the words from.

The class, typed: a sound filed on a SPOKEN event, made by that event's own
speaker, is the line's voice, which the hearing rule carries -- dropped at
the merge with a warning naming it. A sound filed on an ACT -- a shot, a
slammed door, a cough, a laugh that is not a line -- is the only channel it
has, and stays; so does a sound on a spoken event made by something else.
"""

from __future__ import annotations

import pytest

import agents.director as director
from agents.director_prose import a_line_is_heard_never_sounded, ledger_from_events
from tests.director_fakes import _fake_agent, _make_ctx

INDEX = {"persona:3": "Tamsin Reed", "character:1": "Davey Mott"}

THE_CALL = ("a woman's voice calling out across the taproom over the fiddle "
            "for two more dark ales")


def _event(text, *, speech, source="persona:3", sounds=(), extra=None):
    patch = {}
    if sounds:
        patch["sensory_events"] = [dict(row) for row in sounds]
    if extra:
        patch.update(extra)
    return {"source_entity_id": source, "source_event_id": "turn:8:primary:raw",
            "event": text, "observable": "" if speech else text,
            "speech": speech, "targets": [], "item_names": ["Tamsin Reed"],
            "transforms": [{"item": "Tamsin Reed", "patch": patch}] if patch else []}


def _sound(source, detail, level="loud"):
    return {"kind": "sound", "room": "gull_taproom", "level": level,
            "source": source, "detail": detail}


def test_the_speakers_own_voice_filed_on_her_line_is_dropped():
    """Chat 2 turn 8, as the encoder wrote it."""
    line = _event("Hollis! Two more of the dark, when you've a minute!",
                  speech=True, sounds=[_sound("Tamsin Reed", THE_CALL)])
    warned = []
    out, refused = a_line_is_heard_never_sounded([line], INDEX, warn=warned.append)
    assert out[0]["transforms"] == []
    assert out[0]["event"] == line["event"] and out[0]["speech"] is True
    assert [(who, row["detail"]) for who, row in refused] == [("Tamsin Reed", THE_CALL)]
    assert len(warned) == 1 and "Tamsin Reed" in warned[0]
    # ...so the merge files no signal for it.
    rows, transforms = ledger_from_events(out)
    assert "sensory_events" not in rows[0]["categories"]
    assert transforms[1] == []


def test_an_acts_own_sound_stays_and_so_does_a_sound_made_by_something_else():
    """A shot, a cough, a moan: filed on the body's ACT, the sound field is
    the only channel they have (round 2's musket report leads its maker's
    own view). And a gas jet hissing under somebody's line (the rival story,
    turn 4) is not that line's voice."""
    shot = _event("Tamsin fires the musket into the air.", speech=False,
                  sounds=[_sound("Tamsin Reed", "a flat crack of musket fire")])
    cough = _event("Tamsin coughs.", speech=False,
                   sounds=[_sound("Tamsin Reed", "a wet, ragged cough", "audible")])
    under = _event("The line sits well in the voice.", speech=True,
                   source="character:1",
                   sounds=[_sound("gas_bracket", "a soft, momentary hiss from the gas jet",
                                  "faint")])
    out, refused = a_line_is_heard_never_sounded([shot, cough, under], INDEX)
    assert out == [shot, cough, under]
    assert refused == []


def test_only_the_voice_leaves_its_transform():
    """The line's other writes stay, and another body's sound on the same
    line stays: one transform loses exactly the speaker's own row."""
    line = _event("Mmm--", speech=True, source="character:1",
                  sounds=[_sound("Davey Mott", "a low, slurred hum"),
                          _sound("Tamsin Reed", "a broken sound, half gasp", "faint")],
                  extra={"poses": {"Davey Mott": {"posture": "seated"}}})
    out, refused = a_line_is_heard_never_sounded([line], INDEX)
    (transform,) = out[0]["transforms"]
    assert transform["patch"]["poses"] == {"Davey Mott": {"posture": "seated"}}
    assert [row["detail"] for row in transform["patch"]["sensory_events"]] == [
        "a broken sound, half gasp"]
    assert [who for who, _row in refused] == ["Davey Mott"]


def test_the_speaker_is_known_by_her_key_as_by_her_name():
    line = _event("Haaa~", speech=True, sounds=[_sound("persona:3", 'a trembling "Haaa~"')])
    out, refused = a_line_is_heard_never_sounded([line], INDEX)
    assert out[0]["transforms"] == [] and len(refused) == 1


@pytest.mark.usefixtures("prose_director")
def test_the_interpretation_files_no_signal_for_the_players_own_line(temp_db, monkeypatch):
    """End to end through the interpret stage: the merged onset diff holds
    the act's sound and not the line's voice, and the stage's record says
    what it dropped."""
    ctx = _make_ctx(temp_db, player_input=(
        'She knocks her mug on the table and calls up the stair: "Quiet night!"'))
    voice = "a woman's voice calling up the stair that it is a quiet night"
    knock = "a mug knocked hard on the boards"
    events = [
        {"source_entity_id": "persona:primary", "event": "She knocks her mug on the table.",
         "observable": "knocks her mug on the table", "item_names": ["The Stranger"],
         "transforms": [{"item": "The Stranger", "patch": {"sensory_events": [
             {"kind": "sound", "room": "keeper_room", "level": "audible",
              "source": "The Stranger", "detail": knock}]}}]},
        {"source_entity_id": "persona:primary", "event": "Quiet night!",
         "speech": True, "volume": "loud", "item_names": ["The Stranger"],
         "transforms": [{"item": "The Stranger", "patch": {"sensory_events": [
             {"kind": "sound", "room": "keeper_room", "level": "loud",
              "source": "The Stranger", "detail": voice}]}}]},
    ]
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": 'The Stranger knocks her mug on the table and '
                                    'calls up the stair, "Quiet night!"'},
        "director_specialist": {"events": events},
    }))
    out = director.director_interpret(ctx, nonce=0)
    onset = out.get("onset_state_assertions") or out.get("state_assertions") or {}
    details = [row.get("detail") for row in onset.get("sensory_events") or []]
    assert knock in details
    assert voice not in details
    refused = out["orchestration"]["prose_contract"]["voices_refused"]
    assert [row["sound"]["detail"] for row in refused] == [voice]
    assert any("own voice" in warning for warning in ctx.warnings)
