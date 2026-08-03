"""The live memory benchmark's statistics must mean what they claim."""

from tools import benchmark_memory_temporal as bench


def test_score_requires_exact_delivered_citations():
    case = {"terms": (("alley",),), "basis": {"memory"}}
    answer = {"answer": "In the alley.", "temporal_basis": "memory",
              "provenance": "witnessed", "citations": ["event:real"]}
    assert bench._score(case, answer, {"event:real"})["passed"]
    assert not bench._score(case, answer, {"event:other"})["passed"]


def test_present_boundary_case_requires_a_current_citation():
    case = {"terms": (("stable",),), "basis": {"current", "both"},
            "needs_current": True}
    answer = {"answer": "It is stable now.", "temporal_basis": "current",
              "provenance": "witnessed", "citations": ["event:old"]}
    score = bench._score(case, answer, {"event:old", "current:35:0"})
    assert not score["checks"]["current_cited"]
    answer["citations"] = ["current:35:0"]
    assert bench._score(case, answer,
                        {"event:old", "current:35:0"})["passed"]


def test_retrieval_score_counts_raw_rows_and_overlapping_windows(monkeypatch):
    monkeypatch.setattr(bench, "q", lambda *args, **kwargs: {
        "start_turn_idx": 0, "end_turn_idx": 9})
    context = {
        "recalled_old_memories": [
            {"turn_idx": 50, "score": 2.0},
            {"turn_idx": 2, "score": 1.0}],
        "earlier_in_my_life": [
            {"summary_id": "summary:autobiographical:9"}],
    }
    score = bench._retrieval_score(
        {"turn_ranges": ((0, 4),)}, context, 38, 35)
    assert score["hit"]
    assert score["first_relevant_raw_rank"] == 2
    assert score["raw_reciprocal_rank"] == 0.5
    assert score["relevant_earlier_windows"] == 1
