"""_recent_self_lines feeds a character agent its own recent verbatim lines so
it can avoid repeating itself unawares (the 'Dr. Moon says keep moving three
turns running' loop) and vary/escalate instead."""

from __future__ import annotations

import json

from agents.character import _recent_self_lines


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("T", "", 0.0))


def _turn_with_dialogue(db, chat_id, idx, dialogue_log):
    tid = db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                (chat_id, idx, 0.0))
    sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                (tid, "director_resolve", "", 0))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps({"dialogue_log": dialogue_log}), 0.0))


def test_recent_self_lines_returns_own_lines_oldest_first(temp_db):
    chat_id = _chat(temp_db)
    _turn_with_dialogue(temp_db, chat_id, 0, [
        {"speaker": "Dr. Moon", "exact_quote": "Keep walking."},
        {"speaker": "Hinami", "exact_quote": "Where are we going?"},
    ])
    _turn_with_dialogue(temp_db, chat_id, 1, [
        {"speaker": "Dr. Moon", "exact_quote": "Keep moving."},
    ])

    lines = _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=2)
    assert [x["said"] for x in lines] == ["Keep walking.", "Keep moving."]
    # Another speaker's lines are never attributed to this character.
    assert all("Where are we going?" != x["said"] for x in lines)


def test_recent_self_lines_excludes_current_and_future_turns(temp_db):
    chat_id = _chat(temp_db)
    _turn_with_dialogue(temp_db, chat_id, 5, [
        {"speaker": "Dr. Moon", "exact_quote": "Earlier line."},
    ])
    _turn_with_dialogue(temp_db, chat_id, 6, [
        {"speaker": "Dr. Moon", "exact_quote": "This beat's line."},
    ])
    # Deciding turn 6: its own not-yet-committed line must not appear.
    lines = _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=6)
    assert [x["said"] for x in lines] == ["Earlier line."]


def test_recent_self_lines_empty_when_none(temp_db):
    chat_id = _chat(temp_db)
    assert _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=0) == []
    assert _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=None) == []


class TestSelfLineRefrain:
    """AVOID SELF-REPETITION targets repeated CONTENT and explicitly exempts a
    consistent register. A template walks through that exemption: measured
    live, one character opened nine consecutive lines the same way and closed
    six of eight the same way, with genuinely fresh content between every
    time. Every line passed the content test; the page read as a stuck record.

    The skeleton is therefore computed rather than left to the character to
    notice about itself, and widening the line window made it MORE important,
    not less -- more examples of a shape read as stronger evidence of the
    register the rule blesses.
    """

    def _lines(self, *said):
        return [{"turn": i, "said": s} for i, s in enumerate(said)]

    def test_a_shared_opening_and_closing_are_reported(self):
        from agents.character import _self_line_refrain

        out = _self_line_refrain(self._lines(
            "Mmm... consumed, my sweet? Yet you stay open for me, pet.",
            "Mmm... mercy, my little fox? Yet that racing pulse says otherwise, pet.",
            "Mmm... mercy, you say? Yet your breath gives you away, pet.",
            "Mmmm... just having fun, my sweet?",
        ))

        assert out["opening"]["word"] == "mm"
        assert out["closing"]["word"] == "pet"
        assert out["opening"]["of"] == 4

    def test_a_near_miss_spelling_is_the_same_opening(self):
        """'Mmm' and 'Mmmm' is exactly the variation that feels like variety
        and is not."""
        from agents.character import _self_line_tokens

        assert _self_line_tokens("Mmm... yes")[0] == \
            _self_line_tokens("Mmmmmm... yes")[0]

    def test_a_varied_speaker_reports_nothing(self):
        from agents.character import _self_line_refrain

        assert _self_line_refrain(self._lines(
            "Get down.",
            "The hatch is sealed, I checked it twice.",
            "Why would she leave the light on?",
            "Move, now.",
        )) is None

    def test_a_shared_word_in_a_minority_of_lines_is_not_a_template(self):
        from agents.character import _self_line_refrain

        assert _self_line_refrain(self._lines(
            "Well, that is done, pet.",
            "The door is open.",
            "Nobody came through here.",
            "I checked the seal myself.",
        )) is None

    def test_too_few_lines_to_judge_reports_nothing(self):
        from agents.character import _self_line_refrain

        assert _self_line_refrain(self._lines("Mmm... yes, pet.",
                                              "Mmm... no, pet.")) is None

    def test_plain_strings_are_accepted_as_well_as_records(self):
        from agents.character import _self_line_refrain

        out = _self_line_refrain(["Mmm... one, pet.", "Mmm... two, pet.",
                                  "Mmm... three, pet."])
        assert out["opening"]["word"] == "mm"

    def test_total_on_junk(self):
        from agents.character import _self_line_refrain

        assert _self_line_refrain(None) is None
        assert _self_line_refrain([]) is None
        assert _self_line_refrain([{}, {}, {}]) is None
        assert _self_line_refrain(["", "   ", None]) is None


class TestVerbatimReissueIsCaughtDeterministically:
    """recent_self_lines and the prompt rule are advisory, and advice is not a
    guarantee: measured live, a character was handed its own previous line in
    that very field and returned it word for word on the next beat. The window
    worked; nothing checked the answer.

    Distinct from the refrain check, which catches a reused sentence SHAPE
    carrying fresh content. Each is blind to the other's failure.
    """

    LINE = "Time machine means the nebulae can wait centuries. Your mingling plan?"

    def test_an_exact_reissue_is_caught(self):
        from agents.character import _first_verbatim_repeat

        assert _first_verbatim_repeat([self.LINE], [self.LINE]) == self.LINE

    def test_punctuation_and_case_are_not_variation(self):
        from agents.character import _first_verbatim_repeat

        disguised = ("TIME MACHINE means the nebulae can wait centuries! "
                     "Your mingling plan")
        assert _first_verbatim_repeat([disguised], [self.LINE]) == self.LINE

    def test_a_genuinely_new_line_passes(self):
        from agents.character import _first_verbatim_repeat

        assert _first_verbatim_repeat(
            ["Right, the console room then."], [self.LINE]) is None

    def test_a_short_echoed_fragment_is_not_a_reissue(self):
        """Echoing a few words is speech, not a stuck record."""
        from agents.character import _first_verbatim_repeat

        assert _first_verbatim_repeat(
            ["East it is."], ["Century? Tempting. East it is."]) is None

    def test_the_refrain_check_does_not_cover_this_case(self):
        """Guarding the regression: these two catch different things, and the
        template detector is silent on a plain verbatim repeat between two
        lines that share no opener or closer."""
        from agents.character import _self_line_refrain, _first_verbatim_repeat

        window = [{"said": "Century? Tempting. East it is."},
                  {"said": self.LINE}]
        assert _self_line_refrain(window) is None
        assert _first_verbatim_repeat([self.LINE],
                                      [w["said"] for w in window]) == self.LINE

    def test_speech_is_read_from_either_shape(self):
        from agents.character import _speech_texts

        assert _speech_texts({"sequence": [{"type": "speech", "text": "hi"},
                                           {"type": "action"}]}) == ["hi"]
        assert _speech_texts({"speech": "hello"}) == ["hello"]
        assert _speech_texts({"sequence": []}) == []

    def test_total_on_junk(self):
        from agents.character import _first_verbatim_repeat, _speech_texts

        assert _first_verbatim_repeat([], ["x"]) is None
        assert _first_verbatim_repeat(["x"], []) is None
        assert _first_verbatim_repeat(None, None) is None
        assert _first_verbatim_repeat(["  "], ["  "]) is None
        assert _speech_texts(None) == []
        assert _speech_texts("not a dict") == []
