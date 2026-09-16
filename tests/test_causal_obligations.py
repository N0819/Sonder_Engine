"""Social debts survive causal routing and commit once in event order."""

from copy import deepcopy

import pytest

from agents import director
from llm.prompts import specialist_prompt
from llm.schemas import validated_specialist_patch_channels
from persist import commit
from tests.test_director_orchestration import _fake_agent, _make_ctx


def _op(verb="open", what="bring the report"):
    return {"op": verb, "who": "The Stranger", "what": what, "kind": "promise"}


def _output(stage, operations, *, commitment="asserted", phase="onset"):
    rows = [{"chrono_id": index, "event_id": f"{stage}:{index}",
             "commitment": commitment, "phase": phase}
            for index in range(1, len(operations) + 1)]
    history = [{"chrono_id": row["chrono_id"], "item_id": 1, "specialist": "social",
                "patch": {"obligations": [op]}} for row, op in zip(rows, operations)]
    steps = [{"chrono_id": row["chrono_id"], "stage": stage, "patch": {},
              "events": [row["event_id"]]} for row in rows]
    return {"ledgers": deepcopy(rows), "sequence": rows,
            "obligations": deepcopy(operations),
            "orchestration": {"transform_history": history},
            "state_assertions" if stage == "interpret" else "state_diff": {"causal_steps": steps}}


def test_obligation_patch_has_a_social_owner_and_preserves_its_metadata():
    assert director.manifest_category_targets("obligations") == {("channel", "obligations")}
    assert "obligations" in director.SPECIALISTS["social"]["channels"]
    clean, dropped = validated_specialist_patch_channels("director_social", {"obligations": [_op()]})
    assert clean["obligations"] == [_op()]
    assert not dropped
    assert "OBLIGATIONS:" in specialist_prompt("social", {"obligations"})


@pytest.mark.parametrize("stage", ["interpret", "resolve"])
def test_current_specialist_pipeline_keeps_debts_outside_scene_state(temp_db, monkeypatch, stage):
    calls = []
    rows = [{"chrono_id": 1, "item_ids": [1], "item_names": ["The Stranger"],
             "source_entity_id": "persona:primary", "event": "I promise to bring the report.",
             "commitment": "asserted", "resolution_notes": "The speaker promises to bring the report.",
             "categories": ["speech", "obligations"]}]
    responses = {f"director_{stage}": {"ledgers": rows}, "director_social": {
        "results": [{"status": "encoded", "settled": {}, "transforms": [
            {"item": "The Stranger", "patch": {"obligations": [_op()]}}]}]}}
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, interp={"sequence": []}, player_input="I promise to bring the report.")
    temp_db.wset(ctx.chat.id, "pending_obligations", [{"id": "old", "who": "Mara", "what": "answer", "opened_turn": 0}])
    out = getattr(director, f"director_{stage}")(ctx, 0)
    assert out["obligations"][0]["what"] == "bring the report"
    state = out["state_assertions" if stage == "interpret" else "state_diff"]
    assert "obligations" not in state
    assert all("obligations" not in step["patch"] for step in state["causal_steps"])
    assert any(row["patch"].get("obligations") for row in out["orchestration"]["transform_history"])
    payload = next(call["payload"] for call in calls if call["step_key"] == "director_social")
    assert payload["pending_obligations"][0]["id"] == "old"


def test_asserted_onset_open_then_resolve_discharge_is_not_duplicated(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op()])
    ctx.director_resolve = _output("resolve", [_op("discharge")])
    expected = [_op(), _op("discharge")]
    assert commit.causal_obligation_ops(ctx) == expected
    result = commit.commit_obligations(ctx, 0)
    assert result["opened"] == 1 and result["discharged"] == 1 and result["open"] == 0
    assert temp_db.wget(ctx.chat.id, "pending_obligations") == []


def test_multiple_chronological_open_close_open_operations_all_reach_commit(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op(), _op("discharge"), _op()])
    ctx.director_resolve = {"obligations": []}
    result = commit.commit_obligations(ctx, 0)
    assert (result["opened"], result["discharged"], result["open"]) == (2, 1, 1)


def test_causal_debts_with_overlapping_words_remain_distinct_and_discharge_exactly(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op(what="bring the lamp"), _op(what="bring the lamp and book")])
    ctx.director_resolve = _output("resolve", [_op("discharge", what="bring the lamp")])
    result = commit.commit_obligations(ctx, 0)
    assert (result["opened"], result["discharged"], result["open"]) == (2, 1, 1)
    assert temp_db.wget(ctx.chat.id, "pending_obligations")[0]["what"] == "bring the lamp and book"


def test_causal_discharge_with_wrong_id_cannot_fall_back_to_matching_words(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op()])
    ctx.director_resolve = _output("resolve", [{**_op("discharge"), "id": "missing"}])
    result = commit.commit_obligations(ctx, 0)
    assert result["discharged"] == 0 and result["open"] == 1


def test_legacy_substring_match_is_preserved(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = {}
    ctx.director_resolve = {"obligations": [_op(what="bring the lamp and book"), _op("discharge", what="bring the lamp")]}
    assert commit.commit_obligations(ctx, 0)["open"] == 0


def test_contestable_or_authority_downgraded_input_does_not_open_a_debt(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op()], commitment="contestable")
    ctx.director_resolve = {"obligations": []}
    assert commit.causal_obligation_ops(ctx) == []
    assert commit.commit_obligations(ctx, 0)["opened"] == 0


def test_final_program_is_authority_and_empty_allowlist_never_falls_back(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op()])
    ctx.director_resolve = _output("resolve", [_op(what="bring the lamp")])
    assert commit.causal_obligation_ops(ctx, causal_program=[]) == []
    assert commit.causal_obligation_ops(ctx, causal_program=[{
        "stage": "resolve", "chrono_id": 1}]) == [_op(what="bring the lamp")]


def test_later_asserted_completion_survives_final_program_even_if_not_in_onset(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op()], phase="completion")
    ctx.director_interpret["onset_state_assertions"] = {"causal_steps": []}
    ctx.director_resolve = {"obligations": []}
    assert commit.causal_obligation_ops(ctx, causal_program=[{
        "stage": "interpret", "chrono_id": 1}]) == [_op()]
    assert commit.causal_obligation_ops(ctx, causal_program=[]) == []


def test_explicitly_blocked_disposition_is_not_a_committed_debt(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = _output("interpret", [_op()])
    ctx.director_resolve = {"obligations": [], "sequence_dispositions": [
        {"event_id": "interpret:1", "status": "blocked"}]}
    assert commit.causal_obligation_ops(ctx) == []


def test_legacy_resolve_ops_remain_readable_but_legacy_interpret_is_not_invented(temp_db):
    ctx = _make_ctx(temp_db)
    ctx.director_interpret = {"obligations": [_op(what="not a legacy input channel")]}
    ctx.director_resolve = {"obligations": [_op()]}
    assert commit.causal_obligation_ops(ctx) == [_op()]
