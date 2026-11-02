"""A channel the prose Director retired is dropped out loud, never committed.

`obligations` was retired 2026-10-02 (the owner): what a mind owes is that
mind's own to keep and strike in its notebook, never a Director ledger. It
was retired only by not being ASKED -- `candidate_channels` skips it, so its
chunk never ships -- while an encoder that wrote it anyway was dispatched to
its owner (`social` still holds the channel) and committed, without a word
(audit of 2026-11-01, `agents_director_prose_movement_rooms` F16). The stage
says what it drops, as it does for a channel no owner holds.
"""

from __future__ import annotations

import agents.director as director
from llm import decisions

from tests.director_fakes import _action_interp, _fake_agent, _make_ctx


def test_an_obligation_the_encoder_writes_is_dropped_and_said(temp_db, monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "poses" else 0.0}
        for key in questions})
    owes = {"events": [{
        "source_entity_id": "character:1", "event": "Mara promises to mend the lamp.",
        "item_names": ["Mara"], "transforms": [
            {"item": "Mara", "patch": {"obligations": [
                {"op": "open", "who": "Mara", "what": "mend the lamp"}]}},
            {"item": "Mara", "patch": {"poses": {"Mara": {"posture": "standing"}}}}]}]}
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": "Mara promises to mend the lamp."},
        "director_specialist": owes,
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert not (out.get("state_diff") or {}).get("obligations")
    assert out["orchestration"]["prose_contract"]["retired_channels"] == ["obligations"]
    assert any("obligations" in w and "retired" in w for w in ctx.warnings)
    assert out["state_diff"]["poses"]["Mara"]["posture"] == "standing"
