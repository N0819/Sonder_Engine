"""A mind reflects on what happened, not on what it meant to do.

The defect the split closes: the character loops run BEFORE
director_resolve, so a mind wrote its memory of a beat -- remember_lines,
belief_updates, mind_model_updates, relationship_updates, memory_effects --
from its PRE-RESOLUTION view: from intent, before it knew whether the act
landed or how anyone answered. perception_outcome then handed it a scrubbed
view of the resolved beat and nothing ever re-asked it. Live example:
Elyra's mind-model update about Hinami was authored before Hinami collapsed
onto her. Salience, agency attribution and theory-of-mind all encoded the
guess, and retrieval searches on that salience forever after.

The split (design note 23, `character_reflection` setting, default OFF and
byte-identical off): CONDUCT stays pre-resolve -- perceive, appraise,
weigh, decide, act -- and REFLECTION runs after perception_outcome, beside
the narrator, reading that mind's OWN scrubbed outcome view and nothing
else. The engine computes the expectation gap (code grades predictions --
the model's own surprise introspection measured 0.65 novelty mid-plateau
and 0.15 at an actual climax); the mind answers with what it keeps: the
seven update fields, a review of its own choice, an explicit refusal
channel for beliefs it saw contradicted and held anyway, and ponder --
which never once fired in 3,083 stored results as a discouraged sequence
type -- as a typed field with an occasion.
"""

from __future__ import annotations

import json
import time

import agents.character as character_module
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData
from prompts import DEFAULT_PROMPTS


# ---- The sheets: recomposition, never a rewrite ---------------------------

class TestTheSheets:
    def test_the_monolith_is_a_byte_identical_recomposition(self):
        import prompts

        assert DEFAULT_PROMPTS["character"] == (
            prompts._CHARACTER_HEAD + prompts._CHARACTER_PROC_MINDMODELS
            + prompts._CHARACTER_MID + prompts._CHARACTER_REFLECT_LAW
            + prompts._CHARACTER_TAIL + prompts._CHARACTER_OUT_REFLECT
            + prompts._CHARACTER_OUT_TAIL)

    def test_split_off_serves_the_shipped_sheet(self, temp_db):
        from prompts import character_conduct_prompt, get_prompt

        assert character_conduct_prompt() == get_prompt("character")

    def test_split_on_sheds_the_writing_law_and_says_where_it_went(
            self, temp_db):
        from prompts import character_conduct_prompt

        temp_db.set_setting("character_reflection", "on")
        conduct = character_conduct_prompt()
        mono = DEFAULT_PROMPTS["character"]
        assert len(conduct) < len(mono)
        for marker in ("SELF/WORLD BELIEF LEARNING", "READING A MEMORY "
                      "DIFFERENTLY", "MEMORY EFFECTS:", "RELATIONSHIPS: R"):
            assert marker in mono
            assert marker not in conduct, marker
        assert "AFTER THE BEAT, YOU REFLECT" in conduct
        # The decision procedure's update step became its reading half.
        assert "3. Update relevant mind models" not in conduct
        assert "Read your mind models as tentative hypotheses" in conduct

    def test_the_reflection_sheet_reuses_the_law_verbatim(self):
        import prompts

        reflection = DEFAULT_PROMPTS["character_reflection"]
        # Segment reuse, not a paraphrase: the exact bytes of the writing
        # law and its output spec appear in both sheets, so the two paths
        # cannot drift about what a belief update or a dispute is.
        assert prompts._CHARACTER_REFLECT_LAW in reflection
        assert prompts._CHARACTER_OUT_REFLECT in reflection
        assert prompts._CHARACTER_REFLECT_LAW in DEFAULT_PROMPTS["character"]
        # And ponder is a first-class field with an occasion here, not a
        # discouraged exception.
        assert "PONDER:" in reflection
        assert "never use it as a default turn action" not in reflection


# ---- The engine grades predictions ----------------------------------------

class TestExpectationGap:
    def test_a_matched_expectation_scores_low(self):
        result = {"appraisal": {"expectation": "she will pull away from me"},
                  "response_candidates": []}
        gap = character_module.expectation_gap(
            result, "She pulls away from you sharply, stepping back.")
        assert gap is not None and gap["score"] <= 0.35

    def test_a_divergent_outcome_scores_high(self):
        result = {"appraisal": {"expectation": "she will pull away from me"},
                  "response_candidates": []}
        gap = character_module.expectation_gap(
            result, "The ceiling collapses; dust fills the corridor as "
                    "alarms begin to sound.")
        assert gap["score"] >= 0.6
        assert gap["expected"] == ["she will pull away from me"]

    def test_no_declared_expectation_is_not_a_surprise(self):
        assert character_module.expectation_gap(
            {"appraisal": {}}, "anything at all") is None
        assert character_module.expectation_gap(
            {"appraisal": {"expectation": "x y z"}}, "") is None

    def test_the_selected_candidates_expected_outcome_counts(self):
        result = {"appraisal": {},
                  "response_candidates": [
                      {"selected": False, "expected_outcome": "irrelevant"},
                      {"selected": True,
                       "expected_outcome": "the door opens quietly"}]}
        gap = character_module.expectation_gap(
            result, "The door opens quietly onto the landing.")
        assert gap["score"] <= 0.35


# ---- One mind's reflection ------------------------------------------------

def _reflection_ctx(temp_db, *, stash=True, view="Hinami collapses "
                    "against you, trembling, her breath ragged."):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Elyra", json.dumps(default_character_data("Elyra")), "{}",
         time.time(), "char_elyra"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 5, "test", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=5,
                      player_input="test", created=time.time()),
        cast=[], input="test")
    ctx.character_results = {char_id: {
        "name": "Elyra",
        "sequence": [{"type": "speech", "text": "Hold still, pet."},
                     {"type": "action", "attempt": "press deeper"}],
        "appraisal": {"expectation": "she will melt into it"},
        "response_candidates": [
            {"response": "press deeper", "selected": True,
             "expected_outcome": "she melts and stays quiet",
             "serves": ["ia2"]},
            {"response": "pause and check on her", "selected": False,
             "serves": ["ia3"]}],
    }}
    ctx.perception_outcome = {
        "views": {str(char_id): view, "player": "SECRET PLAYER VIEW"},
        "observations": {str(char_id): [
            {"observation_id": f"current:{char_id}:0", "channel": "sight",
             "observed": {"text": view}}]},
    }
    ctx.director_resolve = {
        "resolved_event": "OMNISCIENT RESOLUTION TEXT",
        "state_diff": {"secret": True}}
    if stash:
        ctx[f"_reflection_stash:{char_id}"] = {
            "name": "Elyra", "role": "character_major",
            "memory_context": {"recent_episodes": [
                {"memory_ref": "event:abc123", "gist": "she flinched once"}]},
            "memory_internal": {},
            "active_hypotheses": [{"i_suspect": "she is braver than she acts"}],
            "learned_beliefs": [], "relationships": {}, "mind_models": {},
            "absorption": 0.2,
        }
    return ctx, char_id


class TestReflectionStep:
    def test_the_payload_is_the_minds_own_slice_and_nothing_more(
            self, temp_db, monkeypatch):
        ctx, cid = _reflection_ctx(temp_db)
        captured = {}

        def fake(role, step_key, system, payload, **kwargs):
            captured.update(role=role, step_key=step_key, payload=payload,
                            system=system)
            return {"mind_model_updates": []}

        monkeypatch.setattr(character_module, "_agent_json", fake)
        out = character_module.reflection_step(ctx, cid, nonce=0)

        assert captured["step_key"] == "character_reflection"
        assert captured["role"] == "character_major"
        payload = captured["payload"]
        # Its entitlement: own outcome view + observations, own conduct,
        # own ledgers, own recalled memories, the engine-computed gap.
        assert payload["outcome"]["view"].startswith("Hinami collapses")
        assert payload["conduct"]["candidates"][0]["expected_outcome"]
        assert payload["memory"]["recalled"][0]["memory_ref"] == "event:abc123"
        assert payload["reflection"]["expectation_gap"]["score"] >= 0.0
        # The firewall: never the Director's resolution, never another
        # mind's view.
        flat = json.dumps(payload)
        assert "OMNISCIENT RESOLUTION TEXT" not in flat
        assert "SECRET PLAYER VIEW" not in flat
        # The gap rides the stored output for measurement.
        assert out["expectation_gap"]["score"] == \
            payload["reflection"]["expectation_gap"]["score"]
        assert out["char_id"] == cid

    def test_a_mind_with_no_outcome_view_does_not_reflect(
            self, temp_db, monkeypatch):
        ctx, cid = _reflection_ctx(temp_db, view="")
        called = []
        monkeypatch.setattr(character_module, "_agent_json",
                            lambda *a, **k: called.append(1) or {})
        out = character_module.reflection_step(ctx, cid, nonce=0)
        assert not called
        assert "no outcome view" in out["skipped"]

    def test_evidence_is_grounded_against_outcome_observations(
            self, temp_db, monkeypatch):
        """The same citation floor conduct's updates lived under, pointed
        at the outcome: an update citing an observation that was never
        delivered is stripped by the existing grounding pass."""
        ctx, cid = _reflection_ctx(temp_db)

        def fake(role, step_key, system, payload, **kwargs):
            return {"mind_model_updates": [{
                "about_entity": "Hinami", "kind": "emotion",
                "claim": "overwhelmed", "confidence": 0.8,
                "evidence": [{"event_id": f"current:{cid}:99",
                              "fact": "invented"}],
                "alternatives": [],
            }]}

        monkeypatch.setattr(character_module, "_agent_json", fake)
        out = character_module.reflection_step(ctx, cid, nonce=0)
        updates = out.get("mind_model_updates") or []
        assert not updates or not any(
            e.get("event_id") == f"current:{cid}:99"
            for u in updates for e in (u.get("evidence") or []))


class TestReflectionLoop:
    def test_every_mind_that_acted_reflects_and_failure_is_fail_open(
            self, temp_db, monkeypatch):
        ctx, cid = _reflection_ctx(temp_db)
        # A second mind whose reflection call dies.
        other = cid + 1000
        ctx.character_results[other] = {
            "name": "Bo", "sequence": [{"type": "speech", "text": "hm"}],
            "appraisal": {}, "response_candidates": []}
        ctx.perception_outcome["views"][str(other)] = "You watch it happen."
        ctx.perception_outcome["observations"][str(other)] = []

        def fake(role, step_key, system, payload, **kwargs):
            if payload["self"]["name"] == "Bo":
                raise RuntimeError("provider 500")
            # Cite the observation the payload actually delivered -- the
            # grounding floor strips a keep with no delivered evidence.
            oid = payload["outcome"]["observations"][0]["observation_id"]
            return {"remember_lines": [{
                "quote": "Hold still, pet.", "why": "it worked",
                "evidence": [{"event_id": oid, "fact": "heard it"}]}]}

        monkeypatch.setattr(character_module, "_agent_json", fake)
        result = character_module.reflection_loop(ctx, nonce=0)

        assert cid in ctx.reflection_results
        assert other not in ctx.reflection_results
        assert str(other) in result["skipped"]
        assert any("stands on conduct alone" in w for w in ctx.warnings)
        assert result["reflections"][str(cid)]["remember_lines"]


# ---- Commit: the overlay and what persists --------------------------------

def _commit_ctx(temp_db):
    ctx, cid = _reflection_ctx(temp_db)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (ctx.chat.id,))
    ctx.cast = cast
    temp_db.wset(ctx.chat.id, "scene", {
        "rooms": {"room": {"name": "Room"}},
        "positions": {"Elyra": "room"},
        "entities": {}, "attire": {}, "overlays": {}})
    ctx.director_resolve = {"summary": "s", "resolved_event": "e",
                            "dialogue_log": []}
    # Conduct authored a PRE-outcome guess; reflection authored the
    # post-outcome cognition.
    ctx.character_results[cid]["mind_model_updates"] = [{
        "about_entity": "Hinami", "kind": "goal",
        "claim": "PRE-OUTCOME GUESS", "confidence": 0.5,
        "evidence": [], "alternatives": []}]
    ctx.character_results[cid]["active_state"] = {}
    return ctx, cid


class TestCommitOverlay:
    def test_reflection_wins_the_moved_fields_and_stages_its_ponder(
            self, temp_db, monkeypatch):
        import commit

        ctx, cid = _commit_ctx(temp_db)
        ctx.reflection_results = {cid: {
            "mind_model_updates": [{
                "about_entity": "Hinami", "kind": "emotion",
                "claim": "POST-OUTCOME READING", "confidence": 0.8,
                "evidence": [], "alternatives": []}],
            "remember_lines": [],
            "ponder": {"query": "where have I seen that flinch before",
                       "why": "it contradicts how she talks"},
            "choice_review": {"verdict": "vindicated",
                              "why": "she stayed with it"},
        }}
        monkeypatch.setattr(commit, "add_memories_batch",
                            lambda memories=None, *, prepared_batch=None: [])
        prepared = commit.prepare_memory_commit(ctx)

        claims = [u.get("claim") for _, _, s in prepared["state_updates"]
                  for u in []]  # state holds the applied models
        state = json.loads(prepared["state_updates"][0][2])
        assert state["last_choice_review"]["verdict"] == "vindicated"
        assert state["memory_ponder"]["query"].startswith("where have I seen")
        flat = json.dumps(state)
        assert "PRE-OUTCOME GUESS" not in flat
        assert "POST-OUTCOME READING" in flat

    def test_without_a_reflection_the_conduct_result_stands(
            self, temp_db, monkeypatch):
        import commit

        ctx, cid = _commit_ctx(temp_db)
        monkeypatch.setattr(commit, "add_memories_batch",
                            lambda memories=None, *, prepared_batch=None: [])
        prepared = commit.prepare_memory_commit(ctx)
        state = json.loads(prepared["state_updates"][0][2])
        assert "PRE-OUTCOME GUESS" in json.dumps(state)
        assert "last_choice_review" not in state


# ---- The pipeline plan ----------------------------------------------------

class TestThePlan:
    def test_off_is_the_shipped_plan(self, temp_db):
        from agents.runtime import build_plan

        keys = [k for k, _ in build_plan({"flow": {}}, [], chat_id=None)]
        assert "reflection_loop" not in keys

    def test_on_reflects_after_the_outcome_and_beside_the_narrator(
            self, temp_db):
        from agents.runtime import build_plan

        temp_db.set_setting("character_reflection", "on")
        keys = [k for k, _ in build_plan({"flow": {}}, [], chat_id=None)]
        assert "reflection_loop" in keys
        assert keys.index("reflection_loop") \
            > keys.index("perception_outcome")
        assert keys.index("reflection_loop") + 1 == keys.index("narrator")

    def test_rehydration_rebuilds_the_results_map(self, temp_db):
        from agents.runtime import _rehydrate_loop_results

        ctx, cid = _reflection_ctx(temp_db)
        ctx.reflection_results = {}
        _rehydrate_loop_results(ctx, "reflection_loop", {
            "reflections": {str(cid): {"remember_lines": [],
                                       "char_id": cid}},
            "skipped": {}})
        assert cid in ctx.reflection_results


# ---- The next beat knows how the last choice sat --------------------------

def test_conduct_payload_carries_the_last_choice_review(temp_db, monkeypatch):
    ctx, cid = _reflection_ctx(temp_db)
    temp_db.qi(
        "UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
        (json.dumps({"last_choice_review": {
            "verdict": "regret", "why": "pushed too hard", "turn": 4}}),
         ctx.chat.id, cid))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (ctx.chat.id,))
    ctx.cast = cast
    temp_db.wset(ctx.chat.id, "scene", {
        "rooms": {"room": {"name": "Room"}}, "positions": {"Elyra": "room"},
        "entities": {}, "attire": {}, "overlays": {}})
    ctx.director_interpret = {"flow": {"reactors": [cid],
                                       "tom_triggers": []}}
    ctx.character_results = {}
    captured = {}

    def fake(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake)
    character_module.character_step(ctx, cid, nonce=0)
    review = captured["payload"].get("last_choice_review")
    assert review and review["verdict"] == "regret"


class TestTheSwitchIsFindable:
    """A switch a host can only reach by editing the database is a switch
    that becomes folklore. Both of these shipped default-off and neither had
    a way to see or change it -- and `affect_habituation` was live in a real
    story with no visible off.
    """

    def test_both_flags_are_exposed_to_the_client(self):
        import re

        src = open("app.py", encoding="utf-8").read()
        boot = src[src.index("def bootstrap"):]
        for key in ("character_reflection", "affect_habituation"):
            assert re.search(rf'"{key}":', boot), key

    def test_both_flags_have_an_endpoint(self):
        src = open("app.py", encoding="utf-8").read()
        assert '@app.put("/api/character_reflection")' in src
        assert '@app.put("/api/affect_habituation")' in src

    def test_the_panel_offers_both_and_says_what_they_cost(self):
        js = open("static/js/settings.js", encoding="utf-8").read()
        assert "/api/character_reflection" in js
        assert "/api/affect_habituation" in js
        # The reflection toggle must state its price -- it buys thinking,
        # not speed, and a host who is not told that will read the extra
        # seconds as a regression.
        assert "15–25 seconds more per turn" in js
        # And habituation must say it is not retroactive.
        assert "will not reach" in js
