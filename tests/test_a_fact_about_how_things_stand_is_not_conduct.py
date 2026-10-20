"""Words addressed to the telling are not a body's conduct.

Measured on chat 178 t23. The owner wrote: "You left the plates and cups
downstairs (write a note to the encoder so that it can fix the position of the
dinnerware and have hinami no longer carrying it). You sit on the bed next to
her." There was nowhere for a correction to go: one take had Hinami write a
note "for the encoder" in-world, and the kept take walked her down to the
kitchen and back -- which Mellisande, upstairs, saw and remembered, though the
walk was never a positions write. Chat 176 t12 had the same class from the
other side: an assertion about Mellisande's hunger, granted by the default
`world_author` rung, was dropped as "not an outward physical action".

Under the player-authority ladder an assertion that sets how things stand is
AUTHORSHIP (`story.scene.PLAYER_AUTHORITY_GRANTS`, the `world` grant). The
route built for it: the encoder marks such an event `standing`
(`UnifiedEvent.standing`, asked for by the interpret-stage piece of its card),
its writes are applied through the channel that owns them, and the row leaves
the player's sequence -- no act, so no observer perceives one and the page
never narrates one. A rung that does not grant authorship refuses it whole.
"""

from __future__ import annotations

import json

import pytest

import agents.director as director
from agents.common import norm_sequence
from agents.director import normalize_causal_ledger
from agents.director_prose import (is_standing, ledger_from_events,
                                   standing_is_authorship)
from llm.prompts import prose_contract_text, unified_specialist_prompt
from llm.schemas import validate_llm_output
from story.scene import set_player_authority
from tests.director_fakes import BASE_SCENE, _fake_agent, _make_ctx

INDEX = {"persona:10": "Hinami", "character:83": "Mellisande"}


def _inputs(mode="world_author"):
    return [{"entity_id": "persona:10", "authority_mode": mode,
             "events": [{"type": "raw_input", "event_id": "turn:4701:primary:raw"}]}]


def _dishes_downstairs():
    """What the owner's note at chat 178 t23 sets: the dinnerware is in the
    kitchen and Hinami carries none of it."""
    return {"source_entity_id": "persona:10",
            "source_event_id": "turn:4701:primary:raw",
            "event": "The plates and cups are downstairs in the kitchen, where "
                     "Hinami left them.",
            "observable": "", "standing": True, "item_names": ["the mug"],
            "transforms": [{"item": "the mug", "patch": {"inventory_ops": [
                {"op": "transfer", "object_id": "dcbe62951d944991",
                 "from_id": "Hinami", "to_id": "cottage_kitchen"}]}}]}


def _sits_beside():
    return {"source_entity_id": "persona:10",
            "source_event_id": "turn:4701:primary:raw",
            "event": "Hinami sits on the spare room bed beside Mellisande.",
            "observable": "sits on the bed beside Mellisande",
            "item_names": ["Hinami"],
            "transforms": [{"item": "Hinami", "patch": {"poses": {"Hinami": {
                "posture": "seated", "support": "spare_room_bed"}}}}]}


def test_the_encoders_answer_may_say_an_event_is_standing():
    parsed, warnings = validate_llm_output(
        "director_specialist", {"events": [_dishes_downstairs()]})
    assert not warnings
    assert parsed["events"][0]["standing"] is True
    assert is_standing(parsed["events"][0])
    assert not is_standing(_sits_beside())


def test_authorship_keeps_a_standing_fact():
    warnings = []
    kept, refused = standing_is_authorship(
        [_dishes_downstairs(), _sits_beside()], _inputs(), INDEX,
        warn=warnings.append)
    assert kept == [_dishes_downstairs(), _sits_beside()]
    assert refused == [] and warnings == []


@pytest.mark.parametrize("mode", ["actor_only", "explicit_outcomes"])
def test_a_rung_without_authorship_refuses_it_whole(mode):
    warnings = []
    kept, refused = standing_is_authorship(
        [_dishes_downstairs(), _sits_beside()], _inputs(mode), INDEX,
        warn=warnings.append)
    assert kept == [_sits_beside()], "never re-filed as something done"
    assert [row["mode"] for row in refused] == [mode]
    assert warnings


def test_the_row_carries_it_and_only_where_it_is_so():
    rows, _transforms = ledger_from_events([_dishes_downstairs(), _sits_beside()])
    assert rows[0].get("standing") is True
    assert "standing" not in rows[1]
    out = normalize_causal_ledger({"ledgers": rows}, {"persona:10": "world_author"},
                                  INDEX)
    assert out["sequence"][0].get("standing") is True
    assert "standing" not in out["sequence"][1]
    # ...and through the sequence's own normalisation.
    norm_sequence(out)
    assert [bool(row.get("standing")) for row in out["sequence"]] == [True, False]


# ---------------------------------------------------------------------------
# End to end: the interpretation keeps the writes and drops the act
# ---------------------------------------------------------------------------

def _standing_beat(temp_db, monkeypatch, mode=None):
    ctx = _make_ctx(temp_db, player_input=(
        'You were sitting on the cot all along (a note for whoever keeps the '
        'story). "Quiet night."'))
    if mode:
        set_player_authority(ctx.chat["id"], mode)
    events = [
        {"source_entity_id": "persona:primary",
         "event": "The Stranger is seated on the cot, as she has been.",
         "observable": "", "standing": True, "item_names": ["The Stranger"],
         "transforms": [{"item": "The Stranger", "patch": {"poses": {
             "The Stranger": {"posture": "seated", "support": "cot"}}}}]},
        {"source_entity_id": "persona:primary", "event": "Quiet night.",
         "speech": True, "item_names": [], "transforms": []},
    ]
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": 'The Stranger is seated on the cot, as she '
                                    'has been. She says, "Quiet night."'},
        "director_specialist": {"events": events},
    }))
    return ctx, director.director_interpret(ctx, nonce=0)


@pytest.mark.usefixtures("prose_director")
def test_a_standing_fact_is_state_and_never_an_act(temp_db, monkeypatch):
    _ctx, out = _standing_beat(temp_db, monkeypatch)
    assert [row.get("type") for row in out["sequence"]] == ["speech"]
    assert not out.get("action")
    assert [row["event"] for row in out["standing_assertions"]] == [
        "The Stranger is seated on the cot, as she has been."]
    onset = out.get("onset_state_assertions") or out.get("state_assertions") or {}
    assert onset["poses"]["The Stranger"]["posture"] == "seated"
    # No claim is made of it: it is authorship, already settled by the rung.
    assert not [claim for claim in out["flow"]["authority_claims"]
                if "cot" in json.dumps(claim)]


@pytest.mark.usefixtures("prose_director")
def test_actor_only_keeps_neither_the_fact_nor_an_act(temp_db, monkeypatch):
    _ctx, out = _standing_beat(temp_db, monkeypatch, mode="actor_only")
    assert [row.get("type") for row in out["sequence"]] == ["speech"]
    assert "seated" not in json.dumps(out.get("state_assertions") or {})
    assert out["orchestration"]["prose_contract"]["standing_refused"]


# ---------------------------------------------------------------------------
# The encoder is told, at interpret only
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_interpret_piece_rides_the_interpret_sheet_only(language):
    piece = prose_contract_text("encoder_interpret", language).strip()
    assert piece and "standing" in piece
    interpret = unified_specialist_prompt(["poses"], language, [],
                                          stage="interpret")
    resolve = unified_specialist_prompt(["poses"], language, [],
                                        stage="resolve")
    assert piece.splitlines()[0] in interpret
    assert piece.splitlines()[0] not in resolve
    assert piece.splitlines()[0] not in unified_specialist_prompt(
        ["poses"], language, [])
