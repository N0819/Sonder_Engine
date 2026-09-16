"""A loop reroll replaces discarded declarations, then merges only its new rounds."""

from copy import deepcopy

import pytest

from agents import loops
from llm.schemas import CharacterOutput
from tests.test_beat_reissue import _Ctx, TestTheLoopOwnsTheChannel as _LoopHarness


def _discarded():
    return {
        "sequence": [{"type": "speech", "text": "A discarded line."}],
        "active_state": {"active_concerns": ["A discarded concern."]},
        "decision_continuity": {"chosen": "A discarded choice."},
    }


@pytest.mark.parametrize("first_kind", ["omitted", "clear", "replace"])
def test_rerolled_interaction_preserves_only_this_runs_earlier_round(
        monkeypatch, first_kind):
    calls = []
    _LoopHarness()._install(monkeypatch, calls)
    ctx = _Ctx(reactors=[1, 2])
    ctx.character_results = {cid: _discarded() for cid in (1, 2, 99)}
    ctx._extra["beat_declared"] = {1: _discarded()}
    reaction = {88: {"decision_continuity": {"chosen": "A valid reaction."}}}
    ctx.reaction_results = deepcopy(reaction)
    initial = {}
    if first_kind == "clear":
        initial = {"active_concerns": [], "decision_continuity": {}}
    elif first_kind == "replace":
        initial = {
            "active_concerns": ["Inspect the lock."],
            "decision_continuity": {"chosen": "Ask about the lock."},
        }
    seen = []

    def declare(ctx, cid, nonce):
        seen.append(deepcopy(ctx._extra["beat_declared"]))
        calls.append(cid)
        active = {"mood": "alert"}
        choice = {}
        if len(calls) == 1:
            if "active_concerns" in initial:
                active["active_concerns"] = initial["active_concerns"]
            if "decision_continuity" in initial:
                choice["decision_continuity"] = initial["decision_continuity"]
        return CharacterOutput(
            sequence=[{"type": "speech", "text": f"Fresh line {len(calls)}."}],
            active_state=active,
            interaction={"expects_response": True, "urgency": 0.9,
                         "conversation_complete_for_me": False},
            **choice,
        ).model_dump()

    monkeypatch.setattr(loops, "character_step", declare)
    output = loops.interaction_loop(ctx, nonce=0)

    assert calls == [1, 2, 1]
    assert seen[0] == {}
    assert set(output["character_results"]) == {"1", "2"}
    assert ctx.reaction_results == reaction
    held = ctx.character_results[1]
    assert held == ctx._extra["beat_declared"][1]
    assert [row["text"] for row in held["sequence"]] == [
        "Fresh line 1.", "Fresh line 3."]
    assert held["active_state"]["active_concerns"] == initial.get("active_concerns")
    if first_kind == "omitted":
        assert held["decision_continuity"] is None
    elif first_kind == "clear":
        assert not any(held["decision_continuity"].values())
    else:
        assert held["decision_continuity"]["chosen"] == "Ask about the lock."
    assert held["decision_continuity"] == seen[2][1]["decision_continuity"]


@pytest.mark.parametrize("exit_kind", ["disabled", "no_reactors", "already_reacted"])
def test_interaction_no_call_reroll_clears_discarded_results(monkeypatch, exit_kind):
    calls = []
    _LoopHarness()._install(monkeypatch, calls)
    ctx = _Ctx(reactors=[1])
    ctx.character_results = {1: _discarded(), 99: _discarded()}
    ctx._extra["beat_declared"] = {1: _discarded()}
    if exit_kind == "disabled":
        monkeypatch.setattr(loops, "dialogue_config", lambda cid: {
            "max_character_calls": 0,
        })
    elif exit_kind == "no_reactors":
        ctx.director_interpret["flow"]["reactors"] = []
    else:
        ctx.reaction_results = {1: {"decision_continuity": {
            "chosen": "A valid reaction.",
        }}}
    reactions = deepcopy(ctx.reaction_results)

    output = loops.interaction_loop(ctx, nonce=0)

    assert calls == []
    assert output["calls"] == 0
    assert output["character_results"] == {}
    assert ctx.character_results == {}
    assert ctx._extra["beat_declared"] == {}
    assert ctx.reaction_results == reactions


@pytest.mark.parametrize("exit_kind", ["no_contest", "disabled", "no_reactors"])
def test_reaction_no_call_reroll_replaces_only_its_own_results(monkeypatch, exit_kind):
    ctx = _Ctx(reactors=[1])
    ctx.reaction_results = {1: _discarded(), 99: _discarded()}
    ctx.character_results = {2: {"decision_continuity": {"chosen": "Valid act."}}}
    interaction = deepcopy(ctx.character_results)
    monkeypatch.setattr(loops, "reaction_config", lambda cid: {"enabled": True})
    monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_drop_absent", lambda ctx, ids: ids)
    if exit_kind != "no_contest":
        ctx.director_interpret["flow"]["resolution_flags"] = {"contested": True}
    if exit_kind == "disabled":
        monkeypatch.setattr(loops, "reaction_config", lambda cid: {"enabled": False})
    elif exit_kind == "no_reactors":
        ctx.director_interpret["flow"]["reactors"] = []

    output = loops.reaction_loop(ctx, nonce=0)

    assert output["calls"] == 0
    assert output["reaction_results"] == {}
    assert ctx.reaction_results == {}
    assert ctx.character_results == interaction


def test_reaction_reroll_drops_unselected_stale_reactors(monkeypatch):
    ctx = _Ctx(reactors=[1, 2])
    ctx.director_interpret["flow"]["reactors"] = [1]
    ctx.director_interpret["flow"]["resolution_flags"] = {"contested": True}
    ctx.perception_act = {"views": {"1": "The door opens."}}
    ctx.reaction_results = {1: _discarded(), 2: _discarded()}
    monkeypatch.setattr(loops, "reaction_config", lambda cid: {"enabled": True})
    monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_drop_absent", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_requires_director_resolution", lambda result: False)
    fresh = CharacterOutput(active_state={"mood": "alert"}).model_dump()
    monkeypatch.setattr(loops, "character_step", lambda *args: deepcopy(fresh))

    output = loops.reaction_loop(ctx, nonce=0)

    assert output["calls"] == 1
    assert ctx.reaction_results == {1: fresh}
    assert output["reaction_results"] == {"1": fresh}
    assert ctx.reaction_results[1]["decision_continuity"] is None
    assert ctx.reaction_results[1]["active_state"]["active_concerns"] is None
