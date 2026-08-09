"""The Director gets what was said and done, not what was nearly said.

An interaction round carried each character's ENTIRE decision output into the
resolve payload. Measured on chat 67 turn 48: 10,791 chars for a single round,
of which the conduct is about 2,400 — appraisal 1,981, active_state 1,105,
response_candidates 1,029, mind_model_updates 768, plus every memory/evidence/
belief internal and the per-mind `delivered_views`. Across 40 recent loops the
projection cuts 300,771 chars to 74,405, 75%, ~1,414 tokens a beat.

The size is the smaller half. `response_candidates` is what a character WEIGHED
AND DID NOT DO, and CLAUDE.md draws the line it crosses: the Director owns
objective causality and does NOT own character psychology. A stage adjudicating
what happened should not be reading what was nearly said — and it was, on every
beat with an interaction loop.
"""

from __future__ import annotations

from agents.director import _round_conduct


def _round():
    return {
        "round": 0, "speaker": "Veronica", "speaker_id": 57,
        "delivered_views": {"player": "a long perception view"},
        "result": {
            "name": "Veronica",
            "speech": "Rest well.",
            "speech_volume": "normal",
            "action": "She banks the hearth fire.",
            "sequence": [{"type": "speech", "text": "Rest well."}],
            "appraisal": "She is worried and hiding it",
            "active_state": {"mood": "guarded"},
            "response_candidates": ["ask what happened", "say nothing at all"],
            "mind_model_updates": [{"about": "Hinami", "belief": "exhausted"}],
            "observations_used": [{"event_id": "x", "fact": "y"}],
            "memory_effects": ["remembered the stairs"],
        },
    }


class TestWhatSurvives:
    def test_the_conduct_is_kept(self):
        """Ordering a beat needs who spoke and what they did — and the speech
        authority guards check `dialogue_log` against exactly this."""
        out = _round_conduct([_round()])[0]
        assert out["speaker"] == "Veronica"
        assert out["result"]["speech"] == "Rest well."
        assert out["result"]["action"] == "She banks the hearth fire."
        assert out["result"]["sequence"]


class TestWhatMustNotSurvive:
    def test_options_a_character_rejected_do_not_reach_the_adjudicator(self):
        """The one that is not about tokens. A stage deciding what HAPPENED
        must not see what nearly happened."""
        out = _round_conduct([_round()])[0]
        assert "response_candidates" not in out["result"]

    def test_private_interiority_is_dropped(self):
        out = _round_conduct([_round()])[0]["result"]
        for field in ("appraisal", "active_state", "mind_model_updates",
                      "observations_used", "memory_effects"):
            assert field not in out, f"{field} is the character's, not the Director's"

    def test_delivered_views_are_dropped(self):
        """Each mind's own perception object, carried per round. The Director
        is entitled to omniscience so this is not a leak — it is bulk, and it
        is bulk that grows with the cast."""
        assert "delivered_views" not in _round_conduct([_round()])[0]


class TestItSurvivesRealisticJunk:
    def test_a_round_without_a_result_does_not_crash(self):
        assert _round_conduct([{"round": 0, "speaker": "X"}])[0]["result"] == {}

    def test_non_dict_entries_are_skipped(self):
        assert _round_conduct(["nonsense", None, _round()]) != []

    def test_empty_and_none_are_empty(self):
        assert _round_conduct(None) == []
        assert _round_conduct([]) == []

    def test_empty_conduct_fields_are_not_carried(self):
        """An absent field and a field present-but-empty must not differ in the
        payload, or the shape shifts beat to beat and stops caching."""
        entry = _round()
        entry["result"]["speech"] = ""
        assert "speech" not in _round_conduct([entry])[0]["result"]
