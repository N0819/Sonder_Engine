"""A silent beat keeps NO copy of what its prose invented.

The empty-input guard in `director_interpret` (chat 59 t154: an empty box,
and the Director restating the player's turn-150 line verbatim) emptied
`sequence`, `speech`, `action(s)`, `contact_assertions` and
`state_assertions` -- and left the same invention standing in every other
representation of the declaration (review 2026-11-01, director core F1):

  * `ledgers` / `causal_ledger`, which the resolve compiles into the
    committed `state_diff.speech` (`speech_transforms`), charges to the clock
    (`beat_time_from_spans`) and hands the charter voices
    (`background._provisional_beat`);
  * the prose record, which `director_prose.already_happened` hands the
    resolve's author and encoder as "what the player's side already put into
    the world this beat" -- so the resolve was told she said it;
  * `movement`, taken from the invented rows before the guard ran;
  * with another player declaring, `_all_causal_sequence`, from which the
    interpret's own fold took its spans and wrote the invented transforms
    back into the assertions the guard had just emptied.

A guard that removes a declaration removes every representation of it, in
one place. The other player's declaration is a declaration, and stays.
"""

from __future__ import annotations

import agents.director as director
from agents import director_prose

from tests.director_fakes import _action_interp, _fake_agent, _make_ctx, encoder_event


INVENTED_LINE = "Kaa Sama, your cooking is too good."


def _restating(resolve_events=None):
    """The Director restating stale conduct on an empty input: interpret
    prose telling the player speak and walk, an encoder filing both as the
    player's rows; then a quiet resolve."""
    turns = {"prose": 0, "encoder": 0}

    def prose(payload):
        turns["prose"] += 1
        if turns["prose"] == 1:
            return {"prose": f'The Stranger says, "{INVENTED_LINE}" and walks '
                             "up into the lamp room."}
        return {"prose": "The keeper's room is quiet."}

    def encoder(payload):
        turns["encoder"] += 1
        if turns["encoder"] == 1:
            return {"events": [
                encoder_event(INVENTED_LINE, speech=True, seconds=4),
                encoder_event("The Stranger walks up into the lamp room.",
                              seconds=600,
                              movement={"mover": "self", "to_room": "lamp_room"},
                              transforms=[{"item": "The Stranger", "patch": {
                                  "positions": {"The Stranger": "lamp_room"}}}]),
            ] + list(_extra_rows)}
        return {"events": list(resolve_events or [
            encoder_event("The keeper's room is quiet.", source="world")])}
    _extra_rows = []
    return _fake_agent([], {"director_prose": prose,
                            "director_specialist": encoder}), _extra_rows


def _silent_beat(temp_db):
    ctx = _make_ctx(temp_db, interp=_action_interp(), player_input="")
    ctx.director_interpret = None
    return ctx


def test_a_silent_beat_keeps_no_row_no_prose_and_no_walk_it_invented(
        temp_db, monkeypatch, prose_director):
    ctx = _silent_beat(temp_db)
    agent, _ = _restating()
    monkeypatch.setattr(director, "_agent_json", agent)

    out = director.director_interpret(ctx, nonce=0)

    assert out["sequence"] == []
    assert out["ledgers"] == [], "the invented rows stood in `ledgers`"
    assert out["causal_ledger"] == [], "the invented rows stood in `causal_ledger`"
    assert out.get("movement") is None, "the invented walk stood as `movement`"
    record = out["orchestration"]["prose_contract"]
    assert record["prose"] == "", "the stale prose stood on the record"
    assert not [e for e in record.get("events") or []
                if str(e.get("source_entity_id") or "") == "persona:primary"]
    positions = (out.get("state_assertions") or {}).get("positions") or {}
    assert "The Stranger" not in positions

    ctx.director_interpret = out
    assert director_prose.already_happened(ctx) == "", \
        "the resolve was told the player said and did what she never did"


def test_the_resolve_of_a_silent_beat_commits_no_line_she_never_said(
        temp_db, monkeypatch, prose_director):
    ctx = _silent_beat(temp_db)
    agent, _ = _restating()
    monkeypatch.setattr(director, "_agent_json", agent)
    ctx.director_interpret = director.director_interpret(ctx, nonce=0)

    resolved = director.director_resolve(ctx, nonce=0)

    spoken = [str(row.get("event") or row.get("text") or row)
              for row in (resolved.get("state_diff") or {}).get("speech") or []]
    assert not [line for line in spoken if "Kaa Sama" in line], spoken
    # And the clock is not charged the ten minutes of the walk she never took.
    block = (resolved.get("state_diff") or {}).get("time") or {}
    assert "600" not in str(block), block


def test_another_players_declaration_survives_the_primary_players_silence(
        temp_db, monkeypatch, prose_director):
    ctx = _silent_beat(temp_db)
    ctx.extra_players = [{"persona_id": 99, "name": "Bob", "input": "I wave.",
                          "idle": False}]
    agent, extra = _restating()
    extra.append(encoder_event("Bob waves.", source="persona:99", seconds=2))
    monkeypatch.setattr(director, "_agent_json", agent)

    out = director.director_interpret(ctx, nonce=0)

    kept = [str(row.get("source_entity_id")) for row in out["ledgers"]]
    assert kept == ["persona:99"], kept
    assert [str(row.get("source_entity_id")) for row in out["causal_ledger"]] \
        == ["persona:99"]
    assert [str(row.get("actor")) for row in
            (out.get("other_players") or {}).get("99", {}).get("sequence") or []] \
        == ["persona:99"]
    positions = (out.get("state_assertions") or {}).get("positions") or {}
    assert "The Stranger" not in positions, \
        "the fold wrote the primary player's invented walk back from the spans"
    assert out["orchestration"]["prose_contract"]["prose"] == ""
    ctx.director_interpret = out
    happened = director_prose.already_happened(ctx)
    assert "Bob waves." in happened and "Kaa Sama" not in happened, happened
