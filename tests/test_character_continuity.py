"""Private choice and feeling continuity across the real model/commit boundary."""

from copy import deepcopy
import json
import time

import pytest

from agents.character import _private_continuity, _prune_seeded_psychology
from agents.character_kernel import compile_character_kernel
from agents.common import _merge_character_results
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.schemas import validate_llm_output, validate_llm_output_strict
from persist.commit import prepare_memory_commit
from story.character_schema import default_character_data


def _decision():
    return {
        "state": {
            "appraisal": {},
            "active": {
                "affect": {"surface": {"label": "restrained", "valence": -0.2,
                                         "arousal": 0.4}},
                "wants": [
                    {"id": "w1", "want": "snap at the visitor", "urgency": 0.9,
                     "serves": "situational", "conflicts_with": "w2"},
                    {"id": "w2", "want": "listen before judging", "urgency": 0.3,
                     "serves": "situational"},
                ],
                "active_concerns": [], "stress": {}, "hedonic": {},
            },
            "decision": {"enact": "w2", "suppress": "w1",
                         "hinge": "The visitor may have useful evidence.",
                         "uncertainty": "Whether the story is true."},
        },
        "sequence": [{"type": "speech", "text": "Tell me what happened."}],
        "manifest": {},
        "updates": {"intentions": [], "projects": [], "drive": None,
                    "beliefs": [], "associations": [], "people": [],
                    "relationships": [],
                    "memory": {"keep": [], "reinterpret": [], "effects": []}},
        "effects": [], "interaction": {}, "salience": 0.2,
    }


def _validated(raw):
    compiled, warnings = compile_character_kernel(raw)
    assert warnings == []
    result, warnings = validate_llm_output("character", compiled)
    assert warnings == []
    return result


@pytest.fixture
def story(temp_db):
    now = time.time()
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Private continuity", "", now))
    sheet = default_character_data("Mara")
    sheet["initial_state"]["active_concerns"] = ["the visitor may be in danger"]
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", now, sheet["identity"]["uid"]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    scene = {
        "location": "Hall", "time": "now",
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {"Mara": "hall"},
        "entities": {}, "attire": {}, "overlays": {},
    }
    temp_db.wset(chat_id, "scene", scene)

    def context(previous=None, index=1):
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,))
        cast[0] = dict(cast[0])
        cast[0]["cstate"] = json.dumps(previous or {})
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, index, "Listen.", now))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Private continuity", persona_id=None,
                          lorebook_id=None, scenario="", created=now),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=index,
                          player_input="Listen.", created=now),
            cast=cast, input="Listen.")
        ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": []}}
        ctx.director_resolve = {"dialogue_log": []}
        ctx.perception_act = {"views": {str(char_id): "The visitor waits."}}
        ctx.perception_outcome = {
            "views": {str(char_id): "The visitor remains nearby."},
            "episodes": {str(char_id): "The visitor remained nearby."},
            "episode_meta": {}}
        return ctx

    def commit(result, previous=None, index=1):
        ctx = context(previous, index)
        ctx.character_results = {char_id: result}
        prepared = prepare_memory_commit(ctx, scene=scene)
        state = json.loads(next(row[2] for row in prepared["state_updates"]
                                if row[1] == char_id))
        return state, prepared

    return char_id, context, commit


def test_kernel_needs_one_surface_label_and_carries_the_actual_choice():
    report = validate_llm_output_strict("character_kernel", _decision())
    assert report.valid
    result = _validated(report.output)
    assert result["active_state"]["mood"] == "restrained"
    assert result["decision_continuity"] == {
        "chosen": "listen before judging", "suppressed": "snap at the visitor",
        "why": "The visitor may have useful evidence.",
        "uncertainty": "Whether the story is true."}
    assert "baseline" not in result["active_state"]["affect"]


def test_choice_commit_and_next_character_payload(story, monkeypatch):
    """A stronger impulse must not replace the less urgent chosen restraint."""
    import agents.character as character
    char_id, context, commit = story
    state, _ = commit(_validated(_decision()))
    active = state["active_state"]
    assert active["goal"] == "listen before judging"
    assert active["wants"][active["enacted_want"]]["want"] == "listen before judging"
    assert active["active_concerns"] == []
    assert state["decision_continuity"]["suppressed"] == "snap at the visitor"
    assert state["decision_continuity"]["turn"] == 1
    captured = {}

    def answer(role, step_key, system, payload, **kwargs):
        captured.update(deepcopy(payload))
        return {"sequence": []}

    monkeypatch.setattr(character, "_agent_json", answer)
    character.character_step(context(state, 2), char_id, 0)
    own = captured["self"]
    assert own["decision_continuity"] == state["decision_continuity"]
    assert own["active_state"]["active_concerns"] == []
    assert "earlier_this_beat" not in own
    assert "The visitor may have useful evidence." not in json.dumps(
        {k: v for k, v in captured.items() if k != "self"})


@pytest.mark.parametrize("previous_concerns", [[], ["a pending worry"]])
def test_legacy_omission_preserves_concerns_instead_of_reseeding(story, previous_concerns):
    _, _, commit = story
    result = _validated({"active_state": {"mood": "calm"}, "sequence": []})
    assert result["active_state"].get("active_concerns") is None
    state, _ = commit(result, {"active_state": {"active_concerns": previous_concerns}})
    assert state["active_state"]["active_concerns"] == previous_concerns


def test_explicit_clear_survives_a_later_legacy_round_and_commit(story):
    _, _, commit = story
    first = _validated(_decision())
    later = _validated({"active_state": {"mood": "calm"}, "sequence": []})
    merged = _merge_character_results(first, later)
    state, _ = commit(merged, {"active_state": {"active_concerns": ["old worry"]}})
    assert state["active_state"]["active_concerns"] == []
    assert state["decision_continuity"] == {"turn": 1, **first["decision_continuity"]}


def test_explicit_empty_decision_clears_instead_of_restoring_an_earlier_one(story):
    _, _, commit = story
    previous = {"decision_continuity": {"turn": 0, "why": "old rationale"}}
    earlier = _validated(_decision())
    empty = _decision()
    empty["state"]["active"]["wants"] = []
    empty["state"]["decision"] = {key: "" for key in ("enact", "suppress", "hinge", "uncertainty")}
    merged = _merge_character_results(earlier, _validated(empty))
    state, _ = commit(merged, previous)
    assert "decision_continuity" not in state


def test_legacy_omitted_decision_keeps_its_original_turn_stamp(story):
    _, _, commit = story
    note = {"turn": 0, "chosen": "listen", "why": "need evidence"}
    state, _ = commit(_validated({"active_state": {"mood": "calm"}}),
                      {"decision_continuity": note})
    assert state["decision_continuity"] == note


@pytest.mark.parametrize("explicit_clear", [True, False])
def test_undercurrent_clear_or_decay_survives_schema_rounds_and_commit(story, explicit_clear):
    _, _, commit = story
    previous = {"active_state": {"affect": {
        "surface": {"label": "anxious", "valence": -0.4, "arousal": 0.3},
        "undercurrent": {"label": "fear", "valence": -0.5, "arousal": 0.4,
                         "source": "the visitor suspects me", "serves": "i1"},
        "baseline": {"valence": 0, "arousal": 0}}}}
    raw = _decision()
    if explicit_clear:
        raw["state"]["active"]["affect"]["undercurrent"] = None
    first = _validated(raw)
    if explicit_clear:
        assert "undercurrent" in first["active_state"]["affect"]
    later = _validated({"active_state": {"mood": "anxious"}})
    merged = _merge_character_results(first, later)
    state, _ = commit(merged, previous)
    undercurrent = state["active_state"]["affect"]["undercurrent"]
    assert (undercurrent is None) is explicit_clear
    if not explicit_clear:
        assert undercurrent["source"] == "the visitor suspects me"
        assert -0.5 < undercurrent["valence"] < 0


def test_intention_reason_reaches_next_call_with_bound_memory_evidence(story, monkeypatch):
    import agents.character as character
    char_id, context, commit = story
    result = _validated(_decision())
    result["intent_ops"] = [{
        "op": "add", "intent": "Learn the visitor's account",
        "why": "A fair judgment needs the missing account.",
        "evidence": [{"event_id": f"current:{char_id}:0", "fact": "The visitor waited."}]}]
    state, prepared = commit(result)
    intent = state["interior"]["intentions"][0]
    transition = intent["last_transition"]
    episode = next(row for row in prepared["memory_batch"]["prepared"]
                   if row.get("category") == "episode")
    assert transition["evidence"][0]["event_id"] == episode["event_key"]
    assert transition["why"] == "A fair judgment needs the missing account."
    captured = {}

    def answer(role, step_key, system, payload, **kwargs):
        captured.update(deepcopy(payload))
        return {"sequence": []}

    monkeypatch.setattr(character, "_agent_json", answer)
    character.character_step(context(state, 2), char_id, 0)
    carried = next(row for row in captured["self"]["intentions"] if row["id"] == intent["id"])
    assert carried["last_transition"]["why"] == transition["why"]


def test_low_salience_indirect_communication_has_own_durable_memory(story):
    _, _, commit = story
    result = _validated(_decision())
    result["sequence"] = [{"type": "communication", "act": "question",
                           "content": "whether the bridge is passable"}]
    state, prepared = commit(result)
    memories = [row for row in prepared["memory_batch"]["prepared"]
                if row.get("category") == "self"]
    assert len(memories) == 1
    assert "whether the bridge is passable" in memories[0]["content"]


def test_repeated_round_payload_separates_proposals_and_only_its_own_mind(story, monkeypatch):
    import agents.character as character
    char_id, context, _ = story
    state = {"active_state": {"mood": "calm", "active_concerns": ["settled concern"]}}
    ctx = context(state)
    own = _validated(_decision())
    ctx._extra["beat_declared"] = {
        char_id: own,
        char_id + 99: {"decision_continuity": {"why": "FOREIGN PRIVATE SECRET"},
                       "active_state": {"mood": "secret mood"}}}
    ctx.character_results = {char_id: {"decision_continuity": {"why": "DISCARDED REROLL"}}}
    before = deepcopy(ctx._extra["beat_declared"])
    captured = {}

    def answer(role, step_key, system, payload, **kwargs):
        captured.update(deepcopy(payload))
        return {"sequence": []}

    monkeypatch.setattr(character, "_agent_json", answer)
    character.character_step(ctx, char_id, 1)
    prior = captured["self"]["earlier_this_beat"]
    assert prior["status"] == "proposed_before_resolution"
    assert prior["feelings"]["surface"]["label"] == "restrained"
    assert prior["decision"] == own["decision_continuity"]
    assert prior["active_concerns"] == []
    assert captured["self"]["active_state"]["active_concerns"] == ["settled concern"]
    assert "FOREIGN PRIVATE SECRET" not in json.dumps(captured)
    assert "DISCARDED REROLL" not in json.dumps(captured)
    assert ctx._extra["beat_declared"] == before


def test_private_projection_has_no_stale_result_or_extra_internal_fields():
    assert _private_continuity({"character_results": {7: _validated(_decision())}}, 7, {}) == {}
    result = _validated(_decision())
    result["active_state"]["affect"]["surface"]["secret"] = "NOT A FEELING"
    result["active_state"]["active_concerns"] = [str(n) for n in range(8)]
    result["decision_continuity"]["why"] = "x" * 500
    prior = _private_continuity({"beat_declared": {"7": result}}, 7, {})["earlier_this_beat"]
    assert len(prior["decision"]["why"]) == 240
    assert len(prior["active_concerns"]) == 8
    assert "secret" not in prior["feelings"]["surface"]


def test_revised_authored_belief_does_not_reappear_as_its_old_card_copy(monkeypatch):
    monkeypatch.setattr("agents.character.payload_legacy", lambda key: False)
    psych = {"self_model": {
        "beliefs": [{"belief": "Strangers always lie"}, {"belief": "Honor matters"}],
        "protected_beliefs": ["Strangers always lie", "Honor matters"]}}
    fresh = deepcopy(psych)
    _prune_seeded_psychology(fresh, {})
    assert fresh == psych
    _prune_seeded_psychology(psych, {"beliefs": [{
        "belief": "Some strangers tell the truth", "authored_belief": "Strangers always lie",
        "protected": True}]})
    assert psych["self_model"]["beliefs"] == [{"belief": "Honor matters"}]
    assert psych["self_model"]["protected_beliefs"] == ["Honor matters"]
