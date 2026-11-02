"""The interpret builds its world views once per beat.

The fold (`_run_specialists`) reads two keys of the extras it is handed --
`identity_index` and `entity_interiors` -- both the encoder's own. It was
handed `_interpret_extras(out)`, which rebuilt the three DB-backed condition
views, the sightlines and the exits a second time on every beat the encoder
wrote anything (review 2026-11-01, director core E4). Same answer, half the
work.
"""

from __future__ import annotations

import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp, encoder_event


def test_the_condition_views_are_built_once_on_a_beat_the_encoder_wrote(
        temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input="I sit down.")
    ctx.director_interpret = None
    built = []
    real = director._conditions_view
    monkeypatch.setattr(director, "_conditions_view",
                        lambda *a, **k: built.append(1) or real(*a, **k))

    def fake(role, step_key, system, payload, **kw):
        if step_key == "director_prose":
            return {"prose": "The Stranger sits down on the bench."}
        if step_key == "director_specialist":
            return {"events": [encoder_event(
                "The Stranger sits down on the bench.",
                transforms=[{"item": "The Stranger", "patch": {"poses": {
                    "The Stranger": {"posture": "sitting"}}}}])]}
        return {}
    monkeypatch.setattr(director, "_agent_json", fake)

    out = director.director_interpret(ctx, nonce=0)

    assert (out.get("state_assertions") or {}).get("poses"), "a hand folded"
    assert len(built) == 1, len(built)
