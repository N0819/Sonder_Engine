"""Private choice and feeling continuity across the real model/commit boundary."""

from copy import deepcopy
import json
import time

import pytest

from agents.character import _private_continuity, _prune_seeded_psychology
from agents.common import _merge_character_results
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.schemas import validate_llm_output, validate_llm_output_strict
from persist.commit import prepare_memory_commit
from story.character_schema import default_character_data


def _decision():
    """A beat as `compile_bare` writes it (`agents/character_bare.py`), with
    the mood the affect pass gives: the mind chose the LESS urgent pull --
    it listens, and holds back the stronger urge to snap."""
    return {
        "appraisal": {},
        "active_state": {
            "affect": {"surface": {"label": "restrained", "valence": -0.2,
                                     "arousal": 0.4}},
            "mood": "restrained",
            "wants": [
                {"want": "listen before judging", "urgency": 0.3, "serves": "situational"},
                {"want": "snap at the visitor", "urgency": 0.9, "serves": "situational"},
            ],
            "enacted_want": 0, "suppressed_want": 1,
            "active_concerns": [], "stress": {"coping_mode": ""}, "hedonic": {"released": False},
        },
        "sequence": [{"type": "speech", "text": "Tell me what happened."}],
        "manifest": {"surface_demeanor": "", "tells": []},
        "decision_continuity": {
            "chosen": "listen before judging", "suppressed": "snap at the visitor",
            "why": "The visitor may have useful evidence.",
            "uncertainty": "Whether the story is true."},
        "intent_ops": [], "belief_updates": [], "association_updates": [],
        "mind_model_updates": [], "relationship_updates": [], "remember_lines": [],
        "memory_effects": [], "salience": 0.2,
    }


def _bare_reply():
    """What the model writes for the beat above (`character_bare`)."""
    return {"want": "listen before judging", "held_back": "snap at the visitor",
            "hinge": "The visitor may have useful evidence.",
            "unsure": "Whether the story is true.",
            "sequence": [{"say": "Tell me what happened.", "to": "the visitor", "how": "evenly",
                          "why": "I need their account"}],
            "demeanor": "", "tells": [], "notebook": [], "changes": [], "note": ""}


def _validated(raw):
    result, warnings = validate_llm_output("character", raw)
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


def test_the_compiled_choice_validates_and_carries_the_actual_choice():
    result = _validated(_decision())
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
    # Concerns reach the mind in its notebook (`on_your_mind`), not in
    # `self.active_state`; the cleared ones are not reseeded from the card.
    assert "active_concerns" not in own["active_state"]
    assert "on_your_mind" not in own["notebook"]
    assert "earlier_this_beat" not in own
    assert "The visitor may have useful evidence." not in json.dumps(
        {k: v for k, v in captured.items() if k != "self"})


@pytest.mark.parametrize("previous_concerns", [[], ["a pending worry"]])
def test_an_omission_preserves_concerns_instead_of_reseeding(story, previous_concerns):
    _, _, commit = story
    result = _validated({"active_state": {"mood": "calm"}, "sequence": []})
    assert result["active_state"].get("active_concerns") is None
    state, _ = commit(result, {"active_state": {"active_concerns": previous_concerns}})
    assert state["active_state"]["active_concerns"] == previous_concerns


def test_explicit_clear_survives_a_later_round_that_omits_it_and_commit(story):
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
    empty["active_state"]["wants"] = []
    empty["active_state"].pop("enacted_want")
    empty["active_state"].pop("suppressed_want")
    empty["decision_continuity"] = {key: "" for key in ("chosen", "suppressed", "why", "uncertainty")}
    merged = _merge_character_results(earlier, _validated(empty))
    state, _ = commit(merged, previous)
    assert "decision_continuity" not in state


def test_an_omitted_decision_keeps_its_original_turn_stamp(story):
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
        raw["active_state"]["affect"]["undercurrent"] = None
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
    # Feelings are given afresh each round (mind/affect_pass.py), never
    # carried as an earlier round's proposal.
    assert "feelings" not in prior
    assert set(captured["self"]["feelings"]) == {"now", "beneath", "mood"}
    assert prior["decision"] == own["decision_continuity"]
    assert prior["active_concerns"] == []
    assert [e["note"] for e in captured["self"]["notebook"]["on_your_mind"]] == ["settled concern"]
    assert "FOREIGN PRIVATE SECRET" not in json.dumps(captured)
    assert "DISCARDED REROLL" not in json.dumps(captured)
    assert ctx._extra["beat_declared"] == before


def test_the_mood_is_given_in_the_packet_and_the_engine_writes_it_back(story, monkeypatch):
    """The owner, 2026-09-26: the mood is "fed to the character in it's packet"
    and updated "post character actions". The bare reply carries no mood at
    all; the engine's is written, and commit keeps it for the next call."""
    import agents.character as character
    from llm import decisions
    char_id, context, commit = story
    ctx = context({"active_state": {"active_concerns": ["the visitor may be in danger"]}})
    asked = []

    def jev(state, questions):
        asked.append(state)

        def pick(key, criteria):
            for needle, choice in (("dim:tension", "s4"), ("mood:anger", "strong"), ("weight", "strong"),
                                   ("act_against_values", "strong")):
                if needle in key and choice in criteria:
                    return choice
            for neutral in ("neutral", "neither", "none", "s2", "nobody"):
                if neutral in criteria:
                    return neutral
            return next(iter(criteria))
        return {k: {"type": "choice", "probabilities": {pick(k, q["criteria"]): 1.0}} for k, q in questions.items()}

    captured = {}

    def answer(role, step_key, system, payload, **kwargs):
        captured.update(deepcopy(payload))
        return _bare_reply()

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    monkeypatch.setattr(character, "_agent_json", answer)
    result = character.character_step(ctx, char_id, 1)
    feelings = captured["self"]["feelings"]
    assert set(feelings) == {"now", "beneath", "mood"} and isinstance(feelings["mood"], list)
    # the mood is asked before the call, and again on the character's own
    # acts after it
    assert sum("WHAT YOU JUST DID" in str(state) for state in asked) == 1
    given = result["active_state"]["affect"]
    assert given["surface"]["label"]
    assert result["active_state"]["mood"] == given["surface"]["label"]
    assert result["_affect_pass"]["asked"] and result["_affect_pass"]["mood_coords"]
    state, _ = commit(result, index=2)
    assert state["active_state"]["mood_coords"] == result["_affect_pass"]["mood_coords"]


def test_the_memories_a_beat_mints_keep_what_it_made_the_mind_feel(story):
    """The owner, 2026-09-29: a memory's mood "should be a stored value made
    at memory formation not one derived every turn" -- the beat's feelings
    from perception and from what the mind did, stored. The episode keeps
    what perception stirred, the row of its own acts what those acts made it
    feel, and a recalled memory read afresh this beat is handed to the write
    phase to keep that reading."""
    char_id, _context, commit = story
    result = _validated(_decision())
    result["_affect_pass"] = {
        "mood_coords": {"tension": 0.3}, "mood_habits": {}, "mood_clock": 12.5,
        "formed": {"perceived": {"felt": {"dread": 0.6}, "strength": 0.7, "at": 12.5},
                   "acted": {"felt": {"shame": 0.4}, "strength": 0.4, "at": 12.5}},
        "looks": {"t1:7:episode": {"felt": {"nostalgia": 0.5}, "strength": 0.5, "at": 12.5, "why": "unfelt"}}}
    state, prepared = commit(result, index=3)
    kept = {row["category"]: json.loads(row["feelings"])
            for row in prepared["memory_batch"]["prepared"] if row["feelings"]}
    assert kept["episode"]["moment"] == {"felt": {"dread": 0.6}, "strength": 0.7, "at": 12.5,
                                         "turn": 3, "key": "3:perceived"}
    assert kept["self"]["moment"]["felt"] == {"shame": 0.4} and kept["self"]["moment"]["key"] == "3:acted"
    assert [(c, ref, look["turn"], look["why"]) for _chat, c, ref, look in prepared["memory_looks"]] == [
        (char_id, "t1:7:episode", 3, "unfelt")]
    # the beat's layers ride to commit only; the state keeps the mood alone
    assert state["active_state"]["mood_coords"] == {"tension": 0.3}
    assert "formed" not in state["active_state"] and "looks" not in state["active_state"]


def test_a_beat_no_pass_reached_mints_rows_that_keep_nothing(story):
    """No affect pass, no guessed feeling: the rows are read the first time
    they are recalled (`affect_pass.why_read`)."""
    _char_id, _context, commit = story
    _state, prepared = commit(_validated(_decision()), index=4)
    assert all(not row["feelings"] for row in prepared["memory_batch"]["prepared"])
    assert prepared["memory_looks"] == []


def test_private_projection_has_no_stale_result_or_extra_internal_fields():
    assert _private_continuity({"character_results": {7: _validated(_decision())}}, 7, {}) == {}
    result = _validated(_decision())
    result["active_state"]["affect"]["surface"]["secret"] = "NOT A FEELING"
    result["active_state"]["active_concerns"] = [str(n) for n in range(8)]
    result["decision_continuity"]["why"] = "x" * 500
    prior = _private_continuity({"beat_declared": {"7": result}}, 7, {})["earlier_this_beat"]
    assert len(prior["decision"]["why"]) == 240
    assert len(prior["active_concerns"]) == 8
    assert "feelings" not in prior and "NOT A FEELING" not in json.dumps(prior)


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


# --- archived rows ------------------------------------------------------------
# Stored variants from before the bare contract are still read through
# `CharacterOutput` (reroll, rerun-from-stage, the archive). Moved here from
# the full card's belief tests when the kernel was deleted (2026-09-27).

def test_archived_belief_update_defaults_still_read_partial_rows():
    report = validate_llm_output_strict("character", {"belief_updates": [{
        "belief": "The north stair is safe to use.", "operation": "revise",
        "emotional_charge": 0.1,
    }]})

    assert report.valid, report.errors
    update = report.output["belief_updates"][0]
    assert update["confidence"] == 0.5
    assert update["target_belief"] == ""
    assert update["evidence"] == []


def test_archived_wants_keep_their_existing_text_acceptance():
    text = "A legacy desire. " * 100
    report = validate_llm_output_strict("character", {
        "active_state": {"wants": [{"want": text}]},
    })

    assert report.valid, report.errors
    assert report.output["active_state"]["wants"][0]["want"] == text
