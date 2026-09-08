"""A computed rhythm report instead of a banned-word list (review D11/B29).

THE DEFECT: narrator.txt carried two enumerations -- five adverbs and eight
gestures -- and the tell simply moved to words no list held ("steady" 48
times, "unyielding" 11). It moved because the tell was never in the words.
What recurs is SHAPE: sentences all one length, a participial phrase hung off
every second comma, every line of dialogue announced before it is spoken,
four beats closing the same way. Measured over chat 117's 124 narrator proses,
30.1% of sentences closed on a trailing participial phrase and 90.3% of
quoted sentences put the attribution before the line -- and the same
measurement over chat 114 reads 7.8% and 49.9%, so the report discriminates
between stories rather than restating a constant.

So the narrator is handed the measurement of its own last few pages, and
nothing is banned. `repeated_closer` is the one derived judgment and it is
unanimity, not a threshold: every prose in the window closing the same way.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

import agents.narration as narration
from agents.common import _closer_class, _rhythm_report


PARTICIPIAL = ("The lamp guttered on the sill, throwing long shadows. "
               "She crossed the room, saying nothing at all.")
PLAIN = "The lamp guttered. She crossed the room. The door was shut."
LED = 'She said, "Sit down." He did not move.'
TRAILED = '"Sit down," she said. He did not move.'
DIALOGUE_CLOSE = 'He looked up. "Then we go tonight."'


class TestTheShapes:
    def test_a_trailing_participial_phrase_is_counted_by_its_morphology(self):
        """Not by a list of participles: a list is a promise that English can
        be enumerated, and B29 measured that promise failing."""
        report = _rhythm_report([PARTICIPIAL])
        assert report["trailing_participial_sentences"] == 2
        assert _rhythm_report([PLAIN])["trailing_participial_sentences"] == 0

    def test_the_attribution_is_counted_by_where_the_quote_sits(self):
        assert _rhythm_report([LED])["attribution_before_the_quote"] == 1
        assert _rhythm_report([TRAILED])["attribution_before_the_quote"] == 0
        assert _rhythm_report([TRAILED])["quoted_sentences"] == 1

    def test_the_length_spread_is_the_measurement_and_not_a_verdict(self):
        report = _rhythm_report(["He ran. The long grey corridor bent away "
                                 "from him and kept on bending."])
        spread = report["words_per_sentence"]
        assert spread["shortest"] == 2
        assert spread["longest"] == 12
        assert spread["shortest"] <= spread["median"] <= spread["longest"]

    def test_three_closer_classes_and_no_fourth(self):
        assert _closer_class(DIALOGUE_CLOSE.split(". ")[-1]) == "dialogue"
        assert _closer_class("She crossed the room, saying nothing.") \
            == "participial"
        assert _closer_class("The door was shut.") == "statement"
        assert _closer_class("   ") == ""


class TestTheOneJudgment:
    def test_unanimity_is_reported_and_a_mixed_window_is_not(self):
        """Every prose in the window closing the same way -- a state, not a
        threshold. Nine of chat 117's 120 windows were in it."""
        same = _rhythm_report([PLAIN, PLAIN, PLAIN, PLAIN])
        assert same["repeated_closer"] == "statement"
        assert same["closers"] == ["statement"] * 4

        mixed = _rhythm_report([PLAIN, PARTICIPIAL, DIALOGUE_CLOSE])
        assert "repeated_closer" not in mixed
        assert mixed["closers"] == ["statement", "participial", "dialogue"]

    def test_one_prose_alone_is_not_a_pattern(self):
        assert "repeated_closer" not in _rhythm_report([PLAIN])

    def test_the_draft_being_written_can_join_the_window(self):
        """The warning is about the page just written, not about history the
        narrator can no longer do anything about."""
        assert "repeated_closer" not in _rhythm_report([PLAIN, PLAIN,
                                                        PARTICIPIAL])
        joined = _rhythm_report([PLAIN, PLAIN, PLAIN], PLAIN)
        assert joined["repeated_closer"] == "statement"


class TestTheEmptyCase:
    def test_nothing_to_measure_returns_no_report_at_all(self):
        """Empty, never a shell of zeroes: an empty field is a key the model
        reads and discards, and one carrying `sentences: 0` argues for a rule
        with no referent."""
        assert _rhythm_report([]) == {}
        assert _rhythm_report(["", "   "]) == {}
        assert _rhythm_report(None) == {}


class TestThePayload:
    """The report reaches the stage it was measured for, and only when there
    is a page behind it. Same absent-when-empty routing as
    `overused_phrases`, which it sits beside."""

    def _ctx(self, temp_db, proses):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        for i, prose in enumerate(proses):
            tid = temp_db.qi(
                "INSERT INTO turns(chat_id,idx,player_input,created) "
                "VALUES(?,?,?,?)", (cid, i, "hi", time.time()))
            sid = temp_db.qi(
                "INSERT INTO steps(turn_id,key,ord) VALUES(?,?,?)",
                (tid, "narrator", 0))
            temp_db.qi(
                "INSERT INTO variants(step_id,content,created,active) "
                "VALUES(?,?,?,1)",
                (sid, json.dumps({"prose": prose}), time.time()))
        scene = {"rooms": {"r1": {"name": "Hall", "notes": "a hall"}},
                 "positions": {"Player": "r1"}, "entities": {}}
        temp_db.wset(cid, "scene", scene)
        ctx = PipelineContext(
            chat=ChatData(id=cid, name="Test", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=99, chat_id=cid, idx=len(proses) + 1,
                          player_input="hi", created=time.time()),
            cast=[{"id": 1,
                   "sheet": json.dumps(default_character_data("Mara")),
                   "cstate": "{}", "status": "active"}],
            input="I push through the door.")
        ctx._extra["outcome_scene"] = scene
        ctx["_player_room"] = "r1"
        ctx["director_interpret"] = {"sequence": [], "speech": None}
        ctx["perception_outcome"] = {"views": {"player": "The hall is quiet."}}
        ctx["perception_establish"] = {
            "views": {"player": "The hall is quiet."}}
        return ctx

    def _run(self, temp_db, monkeypatch, proses):
        captured = {}

        def _fake_agent_json(step_key, model_key, prompt, payload, **kw):
            captured["payload"] = payload
            return {"prose": PLAIN, "new_specifics": []}

        monkeypatch.setattr(narration, "_agent_json", _fake_agent_json)
        monkeypatch.setattr(narration, "validate_llm_output",
                            lambda key, out: (out, []))
        ctx = self._ctx(temp_db, proses)
        narration.narrator(ctx, 0)
        return captured["payload"], ctx.warnings

    def test_the_report_rides_the_payload_and_the_repeat_is_warned(
            self, temp_db, monkeypatch):
        payload, warnings = self._run(
            temp_db, monkeypatch, [PLAIN, PLAIN, PLAIN])
        assert payload["rhythm_report"]["sentences"] == 9
        assert payload["rhythm_report"]["closers"] == ["statement"] * 3
        assert any("closes the same way" in w for w in warnings)

    def test_a_story_with_no_page_yet_carries_no_key(
            self, temp_db, monkeypatch):
        payload, warnings = self._run(temp_db, monkeypatch, [])
        assert "rhythm_report" not in payload
        assert not [w for w in warnings if "closes the same way" in w]
