"""The Director's judgement of whose mind matters this beat is the loop's to
order speakers by, never a flag in the mind's own payload.

`decision.deep_tom_requested` was `cid in flow.tom_triggers` -- the
Director's reading of the WHOLE beat, acts this mind never perceived
included -- handed to the mind on every call, under no section of either
pack's card (grep: zero hits in `language_packs/`), so the model was left to
guess what an unexplained `true` meant (review 2026-11-01,
agents_character_background F15). `agents/loops.py` keeps reading
`tom_triggers` for speaker order; the payload no longer carries it.
"""

from __future__ import annotations

from copy import deepcopy

from tests.test_character_continuity import story  # noqa: F401 -- the fixture


def test_a_mind_named_in_tom_triggers_is_not_told_so(temp_db, story, monkeypatch):
    import agents.character as character
    from llm import decisions
    from tests.test_character_bare import _answer
    char_id, context, _commit = story
    ctx = context(None, 1)
    ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": [char_id]}}
    sent = []

    def model(role, step_key, system, payload, **kwargs):
        sent.append(deepcopy(payload))
        return {"want": "listen", "held_back": "", "hinge": "", "unsure": "",
                "sequence": [{"do": "listens"}], "demeanor": "", "tells": [],
                "notebook": [], "changes": [], "note": ""}

    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: _answer([])(questions))
    monkeypatch.setattr(character, "_agent_json", model)
    character.character_step(ctx, char_id, 1)
    assert "deep_tom_requested" not in (sent[0].get("decision") or {})
