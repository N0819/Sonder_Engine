import json
import time

from agents.character_kernel import (
    bind_current_evidence_to_memory,
    compact_character_evidence,
    compile_character_kernel,
    expand_character_evidence,
    is_character_kernel_output,
)
from llm.schemas import validate_llm_output, validate_llm_output_strict
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import prepare_memory_commit
from story.character_schema import default_character_data


def _kernel_shell():
    """A deliberately empty answer with every required structural lane."""
    return {
        "state": {
            "appraisal": {
                "goal_relevance": "", "expectation": "", "emotion": "",
                "uncertainty": "", "novelty": 0.0,
                "controllability": 0.5, "coping_potential": 0.5,
                "norm_compatibility": 0.0, "self_congruence": 0.0,
                "intrinsic_pleasantness": 0.0, "present_evidence": [],
                "memory_modulation": {}, "somatic_impact": {},
                "goal_impacts": [],
            },
            "active": {
                "mood": "", "affect": {}, "wants": [],
                "active_concerns": [], "stress": {}, "hedonic": {},
            },
            "decision": {
                "enact": "", "suppress": "", "hinge": "",
                "uncertainty": "",
            },
        },
        "sequence": [],
        "manifest": {},
        "updates": {
            "intentions": [], "projects": [], "drive": None,
            "beliefs": [], "associations": [], "people": [],
            "relationships": [],
            "memory": {"keep": [], "reinterpret": [], "effects": []},
        },
        "effects": [],
        "interaction": {},
        "salience": 0.5,
    }


def test_compact_character_schema_accepts_the_small_contract():
    raw = _kernel_shell()
    raw["state"]["decision"]["hinge"] = "nothing presses a choice"
    raw["salience"] = 0.4

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid is True
    assert report.output["salience"] == 0.4


def test_compiler_expands_all_update_and_effect_lanes():
    raw = {
        "state": {
            "appraisal": {"emotion": "wary"},
            "active": {
                "mood": "held taut",
                "wants": [
                    {"id": "w1", "want": "ask"},
                    {"id": "w2", "want": "leave"},
                ],
            },
            "decision": {
                "enact": "w1", "suppress": "w2",
                "hinge": "an answer matters more than distance",
                "uncertainty": "whether he will answer",
            },
        },
        "sequence": [{"type": "speech", "text": "Who sent you?"}],
        "manifest": {"surface_demeanor": "still"},
        "updates": {
            "intentions": [
                {"op": "add", "intent": "learn who sent him"}],
            "projects": [
                {"op": "adopt", "project": "trace the letter"}],
            "drive": {"essence": "protect the witness"},
            "beliefs": [
                {"belief": "he is stalling", "operation": "weaken",
                 "emotional_charge": -0.2, "evidence": []}],
            "associations": [
                {"cue": "wax seal", "operation": "extinguish",
                 "evidence": []}],
            "people": [
                {"about_entity": "runner", "kind": "goal",
                 "claim": "escape"}],
            "relationships": [
                {"target_entity": "runner", "trust_delta": -0.05}],
            "memory": {
                "keep": [
                    {"quote": "Who sent you?", "why": "the answer matters"}],
                "reinterpret": [
                    {"memory_ref": "m:1", "now_reads": "staged"}],
                "effects": [
                    {"memory_ref": "m:2", "changed": "made me ask"}],
            },
        },
        "effects": [
            {"type": "follow", "op": "start", "target": "runner"},
            {"type": "contact_end", "op": "remove", "contact_ref": "c:1"},
            {"type": "material", "op": "deposit", "substance": "ash"},
        ],
        "interaction": {"addresses": ["runner"], "expects_response": True},
        "salience": 0.8,
    }

    compiled, warnings = compile_character_kernel(raw)

    assert warnings == []
    assert compiled["appraisal"]["emotion"] == "wary"
    assert compiled["active_state"]["enacted_want"] == 0
    assert compiled["active_state"]["suppressed_want"] == 1
    assert all("choice" not in want for want in compiled["active_state"]["wants"])
    assert compiled["intent_ops"][0]["op"] == "add"
    assert compiled["project_ops"][0]["project"] == "trace the letter"
    assert compiled["drive_shift"]["essence"] == "protect the witness"
    assert compiled["belief_updates"][0]["belief"] == "he is stalling"
    assert compiled["belief_updates"][0]["operation"] == "weaken"
    assert compiled["belief_updates"][0]["emotional_charge"] == -0.2
    assert compiled["association_updates"][0]["cue"] == "wax seal"
    assert compiled["association_updates"][0]["operation"] == "extinguish"
    assert compiled["mind_model_updates"][0]["claim"] == "escape"
    assert compiled["relationship_updates"][0]["target_entity"] == "runner"
    assert compiled["remember_lines"][0]["quote"] == "Who sent you?"
    assert compiled["memory_disputes"][0]["memory_ref"] == "m:1"
    assert compiled["memory_effects"][0]["memory_ref"] == "m:2"
    assert compiled["follow_op"]["target"] == "runner"
    assert compiled["contact_ops"][0]["contact_ref"] == "c:1"
    assert compiled["material_effects"][0]["substance"] == "ash"

    normalized, schema_warnings = validate_llm_output("character", compiled)
    assert not schema_warnings
    assert normalized["sequence"][0]["text"] == "Who sent you?"


def test_compiler_keeps_legacy_character_outputs_unchanged():
    legacy = {"active_state": {"mood": "calm"}, "sequence": []}

    assert is_character_kernel_output(legacy) is False
    compiled, warnings = compile_character_kernel(legacy)

    assert compiled == legacy
    assert compiled is not legacy
    assert warnings == []


def test_compiler_reports_unknown_rows_and_resolves_singletons_deterministically():
    """The first experimental list remains readable but is no longer offered."""
    raw = {
        "state": {"active": {"wants": [
            {"want": "one", "choice": "enact"},
            {"want": "two", "choice": "enact"},
        ]}},
        "updates": [
            {"type": "drive", "essence": "first"},
            {"type": "mystery", "value": 1},
            {"type": "drive", "essence": "last"},
        ],
        "effects": [{"type": "unknown"}],
    }

    compiled, warnings = compile_character_kernel(raw)

    assert compiled["active_state"]["enacted_want"] == 0
    assert compiled["drive_shift"]["essence"] == "last"
    assert any("several enacted wants" in warning for warning in warnings)
    assert any("unknown updates kind 'mystery'" in warning for warning in warnings)
    assert any("unknown effects kind 'unknown'" in warning for warning in warnings)
    assert any("several drive_shift rows" in warning for warning in warnings)


def test_evidence_handles_round_trip_without_touching_sequence_ids():
    payload = {
        "perception": {"observations": [
            {"observation_id": "current:77:0", "observed": {"text": "a bell"}},
        ]},
        "memory": {
            "recent_episodes": [
                {"memory_ref": "event:very-long-hash", "gist": "old bell"},
            ],
            "recalled_old_memories": [
                {"memory_ref": "event:very-long-hash", "gist": "same bell"},
            ],
            "where_i_came_from": {
                "summary_id": "summary:long-hash", "summary": "a tower"},
        },
    }

    compacted, resolver = compact_character_evidence(payload)

    assert compacted["perception"]["observations"][0]["observation_id"] == "o1"
    assert compacted["memory"]["recent_episodes"][0]["memory_ref"] == "m1"
    assert compacted["memory"]["recalled_old_memories"][0]["memory_ref"] == "m1"
    assert compacted["memory"]["where_i_came_from"]["summary_id"] == "s1"

    answer = {
        "state": {"appraisal": {
            "present_evidence": [{"event_id": "o1", "fact": "a bell"}],
            "memory_modulation": {
                "evidence": [{"event_id": "m1", "fact": "old bell"}],
            },
        }},
        "sequence": [{"type": "action", "event_id": "o1", "attempt": "turn"}],
        "updates": {
            "relationships": [{
                "target_entity": "bell keeper",
                "trigger_event_ids": ["o1"],
            }],
            "memory": {"effects": [{"memory_ref": "m1"}]},
        },
    }
    expanded = expand_character_evidence(answer, resolver)

    evidence = expanded["state"]["appraisal"]
    assert evidence["present_evidence"][0]["event_id"] == "current:77:0"
    assert evidence["memory_modulation"]["evidence"][0]["event_id"] == "event:very-long-hash"
    assert expanded["updates"]["relationships"][0]["trigger_event_ids"] == [
        "current:77:0"]
    assert expanded["updates"]["memory"]["effects"][0]["memory_ref"] == (
        "event:very-long-hash")
    assert expanded["sequence"][0]["event_id"] == "o1"


def test_first_experiment_aliases_do_not_reverse_learning_at_compile():
    raw = {
        "state": {},
        "updates": [
            {"type": "belief", "belief": "the door is safe",
             "op": "weaken", "charge": -0.4},
            {"type": "association", "cue": "blue flame",
             "op": "break"},
        ],
    }

    compiled, warnings = compile_character_kernel(raw)

    assert warnings == []
    assert compiled["belief_updates"] == [{
        "belief": "the door is safe", "operation": "weaken",
        "emotional_charge": -0.4,
    }]
    assert compiled["association_updates"] == [{
        "cue": "blue flame", "operation": "extinguish",
    }]


def test_intention_rows_require_the_field_their_operation_can_address():
    add_raw = _kernel_shell()
    add_raw["updates"]["intentions"] = [{"op": "add"}]
    existing_raw = _kernel_shell()
    existing_raw["updates"]["intentions"] = [
        {"op": "progress", "intent": "ask"}]
    missing_add = validate_llm_output_strict("character_kernel", add_raw)
    missing_existing = validate_llm_output_strict(
        "character_kernel", existing_raw)

    assert missing_add.valid is False
    assert any("intent is required for add" in error
               for error in missing_add.errors)
    assert missing_existing.valid is False
    assert any("id is required for progress" in error
               for error in missing_existing.errors)


def test_kernel_canonicalizes_unambiguous_json_only_update_spellings():
    raw = _kernel_shell()
    raw["updates"]["intentions"] = [{
        "operation": "progress", "intention_id": "intent:1",
        "why": "the witness finally answered",
    }]
    raw["updates"]["people"] = [{
        "about": "runner", "type": "goal", "reading": "escape",
        "confidence": 0.7,
    }]
    raw["updates"]["relationships"] = [{
        "target": "runner", "axis": "trust", "delta": -0.05,
    }]

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid is True
    assert report.output["updates"]["intentions"][0]["op"] == "progress"
    assert report.output["updates"]["intentions"][0]["id"] == "intent:1"
    assert report.output["updates"]["people"][0]["about_entity"] == "runner"
    assert report.output["updates"]["people"][0]["claim"] == "escape"
    assert report.output["updates"]["relationships"][0] == {
        "target_entity": "runner",
        "trust_delta": -0.05,
        "warmth_delta": 0.0,
        "fear_delta": 0.0,
        "respect_delta": 0.0,
        "suspicion_delta": 0.0,
        "trigger_event_ids": [],
    }


def test_kernel_lifts_top_level_effects_closed_inside_updates():
    raw = _kernel_shell()
    raw.pop("effects")
    raw["updates"]["effects"] = [{
        "type": "contact_end", "op": "remove", "contact_ref": "c:1",
    }]

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid is True
    assert report.output["effects"] == [{
        "type": "contact_end", "op": "remove", "contact_ref": "c:1",
    }]
    assert "effects" not in report.output["updates"]


def test_kernel_lifts_other_top_level_fields_closed_inside_updates():
    raw = _kernel_shell()
    interaction = raw.pop("interaction")
    salience = raw.pop("salience")
    raw["updates"]["interaction"] = interaction
    raw["updates"]["salience"] = salience

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid is True
    assert report.output["interaction"]["yields_floor"] is True
    assert report.output["salience"] == 0.5
    assert "interaction" not in report.output["updates"]
    assert "salience" not in report.output["updates"]


def test_kernel_recovers_self_labelled_values_from_punctuation_keys():
    raw = _kernel_shell()
    raw["state"]["decision"].pop("hinge")
    raw["state"]["decision"][" "] = "hinge is: the answer matters now"
    raw["state"]["active"].pop("hedonic")
    raw["state"]["active"][","] = {"released": True}

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid is True
    assert report.output["state"]["decision"]["hinge"] == (
        "the answer matters now")
    assert report.output["state"]["active"]["hedonic"] == {
        "released": True}


def test_kernel_canonicalizes_goal_impact_lane_and_aim_id():
    raw = _kernel_shell()
    raw["state"]["appraisal"].pop("goal_impacts")
    raw["state"]["appraisal"]["goals_impacts"] = [{
        "id": "i1", "impact": 0.4, "why": "the door opens",
    }]

    report = validate_llm_output_strict("character_kernel", raw)
    compiled, warnings = compile_character_kernel(report.output)
    stable, schema_warnings = validate_llm_output("character", compiled)

    assert report.valid is True
    assert warnings == []
    assert schema_warnings == []
    assert stable["appraisal"]["goal_impacts"][0]["serves"] == "i1"
    assert "goals_impacts" not in stable["appraisal"]


def test_kernel_rejects_a_misnested_decision_instead_of_defaulting_it_away():
    raw = _kernel_shell()
    raw["state"]["active"]["decision"] = raw["state"].pop("decision")

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid is False
    assert any("state.decision" in error for error in report.errors)


def test_commit_binds_current_evidence_to_the_episode_memory_in_place():
    result = {
        "appraisal": {
            "present_evidence": [{"event_id": "current:7:0"}],
            "memory_modulation": {"evidence": [{"event_id": "event:past"}]},
        },
        "belief_updates": [{
            "belief": "the bell is near",
            "evidence": [{"event_id": "current:7:1"}],
        }],
        "relationship_updates": [{
            "target_entity": "keeper",
            "trigger_event_ids": ["current:7:0", "event:past"],
        }],
        "sequence": [{"type": "action", "event_id": "current:phase:0"}],
    }

    returned = bind_current_evidence_to_memory(result, "event:this-episode")

    assert returned is result
    assert result["appraisal"]["present_evidence"][0]["event_id"] == "event:this-episode"
    assert result["appraisal"]["memory_modulation"]["evidence"][0]["event_id"] == "event:past"
    assert result["belief_updates"][0]["evidence"][0]["event_id"] == "event:this-episode"
    assert result["relationship_updates"][0]["trigger_event_ids"] == [
        "event:this-episode", "event:past"]
    assert result["sequence"][0]["event_id"] == "current:phase:0"


def test_commit_keeps_current_ids_when_no_episode_was_minted():
    result = {"belief_updates": [{
        "belief": "the bell is near", "evidence": [{"event_id": "current:7:1"}],
    }]}

    bind_current_evidence_to_memory(result, "")

    assert result["belief_updates"][0]["evidence"][0]["event_id"] == "current:7:1"


def test_memory_commit_persists_current_evidence_as_the_episode_key(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Kernel", "", time.time()))
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(),
         sheet["identity"]["uid"]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "ring the bell", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Kernel", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="ring the bell", created=time.time()),
        cast=cast,
        input="ring the bell",
    )
    ctx.director_resolve = {"dialogue_log": []}
    ctx.perception_outcome = {
        "views": {str(char_id): "A brass bell rings beside you."},
        "episodes": {str(char_id): "The brass bell rang beside me."},
        "episode_meta": {},
    }
    ctx.character_results = {char_id: {
        "active_state": {"mood": "alert", "wants": []},
        "appraisal": {},
        "sequence": [],
        "belief_updates": [{
            "belief": "the bell is within reach",
            "confidence": 0.8,
            "evidence": [{"event_id": f"current:{char_id}:0",
                          "fact": "the bell rang beside me"}],
        }],
    }}
    scene = {
        "location": "Belfry", "time": "now",
        "rooms": {"belfry": {"name": "Belfry", "adjacent": []}},
        "positions": {"Mara": "belfry"},
        "entities": {}, "attire": {}, "overlays": {},
    }

    prepared = prepare_memory_commit(ctx, scene=scene)

    episode = next(row for row in prepared["memory_batch"]["prepared"]
                   if row.get("char_id") == char_id
                   and row.get("category") == "episode")
    state = json.loads(next(row[2] for row in prepared["state_updates"]
                            if row[1] == char_id))
    belief = next(item for item in state["interior"]["beliefs"]
                  if item["belief"] == "the bell is within reach")
    assert belief["last_evidence"][0]["event_id"] == episode["event_key"]


class TestAFieldFoldedIntoUpdatesIsStillTheField:
    """A character's conversation control and salience arrived nested.

    Measured on glm-5.2, beats 1199 and 1419 of the owner's own stories: the
    writer did not close `updates` before the fields that follow it, so a
    complete `interaction` block and a `salience` of 0.85 were emitted one
    level down. The adapter read only the top level, so the beat kept its
    nine mind operations and silently lost who the character was addressing,
    whether it expected an answer, and how much the beat was worth
    remembering. Nothing warned: `{}` and `0.5` are both legal values.
    """

    def _folded(self):
        raw = _kernel_shell()
        interaction = {
            "addresses": ["Hinami"], "expects_response": True,
            "yields_floor": True, "urgency": 0.6,
            "conversation_complete_for_me": False,
        }
        raw["updates"]["interaction"] = interaction
        raw["updates"]["salience"] = 0.85
        raw["updates"]["effects"] = [
            {"type": "follow", "op": "stop"}]
        raw.pop("interaction", None)
        raw.pop("salience", None)
        raw.pop("effects", None)
        return raw, interaction

    def test_the_nested_field_reaches_the_top_level(self):
        raw, interaction = self._folded()
        compiled, warnings = compile_character_kernel(raw)
        assert compiled["interaction"] == interaction
        assert compiled["salience"] == 0.85
        assert any("interaction" in w for w in warnings), warnings

    def test_the_lift_does_not_leave_a_copy_behind(self):
        """`updates` owns a closed set of lanes. A field left in both places
        is a second representation free to disagree with the first."""
        raw, _ = self._folded()
        compile_character_kernel(raw)
        # the caller's own object must not be mutated either
        assert "interaction" in raw["updates"]

    def test_a_correctly_placed_field_is_never_overwritten(self):
        """The recovery must be invisible to a writer that closed the object."""
        raw = _kernel_shell()
        raw["interaction"]["addresses"] = ["Mara"]
        raw["salience"] = 0.2
        raw["updates"]["interaction"] = {"addresses": ["WRONG"]}
        raw["updates"]["salience"] = 0.99
        compiled, _warnings = compile_character_kernel(raw)
        assert compiled["interaction"]["addresses"] == ["Mara"]
        assert compiled["salience"] == 0.2

    def test_the_memory_lane_of_the_same_name_is_untouched(self):
        """`updates.memory.effects` is memory influence; `effects` at the top
        is completed physical consequence. They share a spelling and nothing
        else, so the lift must not confuse them."""
        raw, _ = self._folded()
        raw["updates"]["memory"]["effects"] = [{
            "memory_ref": "event:abc", "use": "recognised the room",
            "disposition": "integrated", "changed": "knew the way out"}]
        compiled, _warnings = compile_character_kernel(raw)
        assert len(compiled["memory_effects"]) == 1
        assert compiled["memory_effects"][0]["memory_ref"] == "event:abc"
        # `type` is the lane discriminator and is consumed by the compile
        assert compiled["follow_op"] == {"op": "stop"}


class TestEveryEvidenceSpellingNamesTheSameId:
    """Provenance was lost on every lane but one, and nothing said so.

    The compact wire hands the model short handles (`o7`) and the engine
    restores canonical ids after the call. That restoration only ever
    traversed evidence written as rows carrying `event_id`. Measured over 20
    stored beats of the owner's stories replayed through glm-5.2, the compact
    contract drew 88 bare strings and 37 lists of strings against 4 row lists:
    152 of 206 ids stayed call-local handles. `relationship_updates` was the
    one lane unaffected, because it cites `trigger_event_ids`, which the
    traversal did list -- 29 of 29 canonical against 0 of 152 elsewhere.

    It is silent twice over. `schemas._evidence_slot` files a bare `o7` as a
    real `event_id`, and a joined `o5,o6,o7` fails its id pattern on the
    commas and is filed as prose `fact`. Both become provenance pointing at
    nothing. The 65 KB contract cited canonical ids directly and never met it.
    """

    HANDLES = {"o5": "current:77:5", "o6": "current:77:6",
               "o7": "current:77:7", "m1": "event:deadbeef"}

    def _expand(self, row):
        out = expand_character_evidence({"mind_model_updates": [row]},
                                        self.HANDLES)
        return out["mind_model_updates"][0]

    def test_a_bare_string_is_a_citation(self):
        assert self._expand({"evidence": "o7"})["evidence"] == "current:77:7"

    def test_a_list_of_strings_is_a_citation(self):
        assert self._expand(
            {"evidence": ["o5", "o6"]})["evidence"] == [
                "current:77:5", "current:77:6"]

    def test_a_row_carrying_event_id_still_works(self):
        row = self._expand(
            {"evidence": [{"event_id": "o7", "fact": "she spoke"}]})
        assert row["evidence"][0]["event_id"] == "current:77:7"
        assert row["evidence"][0]["fact"] == "she spoke"

    def test_a_joined_run_names_every_id_in_it(self):
        """Writers join handles into one string. Commas fail the id pattern
        downstream, so the whole run is filed as prose unless it is split."""
        assert self._expand({"evidence": "o5,o6,o7"})["evidence"] == [
            "current:77:5", "current:77:6", "current:77:7"]
        assert self._expand({"evidence": ["o5, o6", "m1"]})["evidence"] == [
            "current:77:5", "current:77:6", "event:deadbeef"]

    def test_prose_is_not_an_id_and_is_left_alone(self):
        """`fact` is a legitimate evidence slot; only ids are rewritten."""
        prose = "the sound from the east corridor"
        assert self._expand({"evidence": prose})["evidence"] == prose

    def test_an_unissued_handle_passes_through(self):
        """The expansion stays fail-safe: a handle that was never issued is
        left as written rather than dropped or guessed at."""
        assert self._expand({"evidence": "o99"})["evidence"] == "o99"

    def test_a_partial_run_is_not_split(self):
        """Splitting on a run that is not wholly handles would shred prose."""
        mixed = "o5 and something she said"
        assert self._expand({"evidence": mixed})["evidence"] == mixed

    def test_the_episode_rekey_reaches_the_same_spellings(self):
        """`bind_current_evidence_to_memory` shares the blind spot: a belief
        citing this beat must point at the episode minted for it, whichever
        way the citation was spelled."""
        for row, expected in (
                ({"evidence": "current:77:7"}, "event:MINTED"),
                ({"evidence": ["current:77:5", "event:old"]},
                 ["event:MINTED", "event:old"]),
                ({"evidence": [{"event_id": "current:77:7"}]},
                 [{"event_id": "event:MINTED"}]),
        ):
            out = bind_current_evidence_to_memory(
                {"belief_updates": [dict(row)]}, "event:MINTED")
            assert out["belief_updates"][0]["evidence"] == expected
