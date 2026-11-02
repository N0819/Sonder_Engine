"""A mind never takes another mind's private reasoning for its own.

`character_step` read the model's thinking off `providers.last_reasoning`
-- a context-wide "last call" record -- after its call, with nothing
clearing it first. The interaction loop runs its minds one after another in
one context, and three provider paths never write the record (the Anthropic
stream, the Anthropic blocking branch, a claude_cli call that streams no
thinking), so a mind on one of them read the PREVIOUS speaker's trace: its
read-back state quoted it as "YOUR OWN THINKING", and with
`character_thoughts_kept` on it was filed as this mind's own thought and
handed back to it for turns (review 2026-11-01, mind_affect_psychology F1
and llm_providers_quality F1, the mechanism reproduced on a fake Anthropic
stream). The record is cleared before this mind's own call.
"""

from __future__ import annotations

from copy import deepcopy

from tests.test_character_continuity import story  # noqa: F401 -- the fixture

ANOTHER_MIND = "A private: I will betray B at dawn"


def _reply():
    return {"want": "hear the visitor out", "held_back": "send them away",
            "hinge": "they may know something", "unsure": "whether it is true",
            "sequence": [{"say": "Tell me what happened.", "to": "the visitor",
                          "how": "evenly", "why": "I need to know"}],
            "demeanor": "calm", "tells": [], "notebook": [], "changes": [],
            "note": "hearing the visitor out"}


def test_a_call_that_returns_no_thinking_leaves_this_mind_none(temp_db, story, monkeypatch):
    import agents.character as character
    from llm import decisions, providers
    from tests.test_character_bare import _answer
    temp_db.set_setting("character_thoughts_kept", "5")
    char_id, context, _commit = story
    states = []

    def decide(state, questions):
        states.append(str(state))
        return _answer([])(questions)

    monkeypatch.setattr(decisions, "OVERRIDE", decide)
    # The previous speaker's call left its trace; this mind's provider path
    # writes none.
    monkeypatch.setattr(character, "_agent_json",
                        lambda role, step_key, system, payload, **kw: deepcopy(_reply()))
    providers.last_reasoning.set(ANOTHER_MIND)
    try:
        result = character.character_step(context(None, 1), char_id, 1)
    finally:
        providers.last_reasoning.set(None)
    assert not result.get("_thought"), "another mind's thinking filed as this one's"
    assert not any(ANOTHER_MIND in state for state in states)


def test_this_minds_own_thinking_still_reaches_its_read_back(temp_db, story, monkeypatch):
    import agents.character as character
    from llm import decisions, providers
    from tests.test_character_bare import _answer
    temp_db.set_setting("character_thoughts_kept", "5")
    char_id, context, _commit = story
    states = []

    def decide(state, questions):
        states.append(str(state))
        return _answer([])(questions)

    def model(role, step_key, system, payload, **kw):
        providers.last_reasoning.set("The visitor is lying about the road.")
        return deepcopy(_reply())

    monkeypatch.setattr(decisions, "OVERRIDE", decide)
    monkeypatch.setattr(character, "_agent_json", model)
    providers.last_reasoning.set(ANOTHER_MIND)
    try:
        result = character.character_step(context(None, 1), char_id, 1)
    finally:
        providers.last_reasoning.set(None)
    assert result.get("_thought") == ["The visitor is lying about the road."]
    assert not any(ANOTHER_MIND in state for state in states)
