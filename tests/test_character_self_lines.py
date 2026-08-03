"""_recent_self_lines feeds a character agent its own recent verbatim lines so
it can avoid repeating itself unawares (the 'Dr. Moon says keep moving three
turns running' loop) and vary/escalate instead."""

from __future__ import annotations

import json
import time

from agents.character import _recent_self_lines, _recent_self_moves
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


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


def _turn_with_move(db, chat_id, idx, char_id, result):
    tid = db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                (chat_id, idx, 0.0))
    sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                (tid, "interaction_loop", "", 0))
    content = {"character_results": {str(char_id): result}}
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps(content), 0.0))


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


def test_recent_self_moves_is_one_semantic_row_per_turn(temp_db):
    chat_id = _chat(temp_db)
    _turn_with_move(temp_db, chat_id, 4, 17, {
        "response_candidates": [{
            "response": "offer Saturn or dragons and let her choose",
            "selected": True,
        }],
        "active_state": {"goal": "suggest a post-shrine destination"},
        "sequence": [
            {"type": "speech", "text": "Saturn, or dragons?"},
            {"type": "speech", "text": "Your pick."},
        ],
        "interaction": {"expects_response": True},
    })

    moves = _recent_self_moves(chat_id, 17, current_turn_idx=5)

    assert moves == [{
        "turn": 4,
        "move": "offer Saturn or dragons and let her choose",
        "goal": "suggest a post-shrine destination",
        "said": ["Saturn, or dragons?", "Your pick."],
        "expected_answer": True,
    }]


def test_recent_self_moves_uses_turns_not_line_count(temp_db):
    """Four chatty lines in one beat must not evict older move continuity."""
    chat_id = _chat(temp_db)
    for idx in range(1, 13):
        _turn_with_move(temp_db, chat_id, idx, 17, {
            "response_candidates": [{
                "response": f"selected conversational move {idx}",
                "selected": True,
            }],
            "sequence": [
                {"type": "speech", "text": f"line {idx}.{part}"}
                for part in range(4)
            ],
        })

    moves = _recent_self_moves(chat_id, 17, current_turn_idx=13)

    assert [move["turn"] for move in moves] == list(range(1, 13))
    assert sum(len(move["said"]) for move in moves) == 24


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


class TestSemanticMoveRepetition:
    """The confirmed chat-38 failure changed nouns while repeating the job."""

    def test_turn_138_destination_substitution_is_caught(self):
        from agents.character import _first_repeated_move

        previous = [{
            "turn": 137,
            "move": (
                "acknowledge comment lightly, express interest in meeting "
                "after shrine, propose varied destination, and continue walking"
            ),
        }]
        draft = {"response_candidates": [{
            "response": (
                "Affirm interest in meeting her mother and propose entirely "
                "new post-shrine destination to break repetition"
            ),
            "selected": True,
        }]}

        repeated = _first_repeated_move(draft, previous)

        assert repeated["turn"] == 137
        assert "propose varied destination" in repeated["move"]

    def test_a_new_conversational_job_passes(self):
        from agents.character import _first_repeated_move

        previous = [{
            "turn": 137,
            "move": "offer a post-shrine destination and let her choose",
        }]
        draft = {"response_candidates": [{
            "response": "ask what the unfamiliar bell beside the shrine means",
            "selected": True,
        }]}

        assert _first_repeated_move(draft, previous) is None

    def test_short_register_phrases_do_not_false_positive(self):
        from agents.character import _first_repeated_move

        previous = [{"turn": 1, "move": "nod warmly"}]
        draft = {"response_candidates": [{
            "response": "nod once", "selected": True,
        }]}

        assert _first_repeated_move(draft, previous) is None


class TestSpentIntentionCannotSteer:
    def _intentions(self):
        return [
            {"id": "i1", "intent": "show her the universe",
             "status": "dormant", "progress": 1.0,
             "last_progress_turn": 37},
            {"id": "i2", "intent": "inspect the new shrine bell",
             "status": "active", "progress": 0.2,
             "last_progress_turn": 138},
        ]

    def test_detects_spent_refs_in_wants_and_selected_response(self):
        from agents.character import _nonsteering_intention_refs

        result = {
            "active_state": {"wants": [
                {"want": "offer another destination", "serves": "i1"},
            ]},
            "response_candidates": [{
                "response": "offer Calufrax", "serves": ["i1"],
                "selected": True,
            }],
        }

        assert _nonsteering_intention_refs(
            result, self._intentions(), turn_idx=138) == ["i1"]

    def test_live_intention_is_allowed(self):
        from agents.character import _nonsteering_intention_refs

        result = {
            "active_state": {"wants": [
                {"want": "inspect the bell", "serves": "i2"},
            ]},
            "response_candidates": [{
                "response": "ask about the bell", "serves": ["i2"],
                "selected": True,
            }],
        }

        assert _nonsteering_intention_refs(
            result, self._intentions(), turn_idx=138) == []

    def test_surviving_spent_refs_are_sanitized(self):
        from agents.character import _sanitize_nonsteering_intention_refs

        result = {
            "active_state": {
                "goal": "offer another destination after the shrine",
                "wants": [{
                    "want": "offer another destination after the shrine",
                    "serves": "i1",
                }],
            },
            "response_candidates": [{
                "response": "offer Calufrax", "serves": ["i1", "drive"],
                "selected": True,
            }],
        }

        cleaned = _sanitize_nonsteering_intention_refs(result, ["i1"])

        assert cleaned["active_state"]["wants"][0]["serves"] == "situational"
        assert cleaned["active_state"]["goal"] == ""
        assert cleaned["response_candidates"][0]["serves"] == ["drive"]


def test_character_step_combines_move_and_spent_intention_rewrite(
        temp_db, monkeypatch):
    """The live Doctor shape gets one bounded decision-level rewrite."""
    import agents.character as character

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Semantic repeat", "", time.time()),
    )
    sheet = default_character_data("The Doctor")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("The Doctor", json.dumps(sheet), "{}", time.time(), "doctor-repeat"),
    )
    cstate = {
        "interior": {"intentions": [{
            "id": "i1", "intent": "show Hinami the universe",
            "status": "dormant", "progress": 1.0,
            "last_progress_turn": 37,
        }]},
        "active_state": {"mood": "bright", "goal": "offer a destination"},
    }
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(cstate)),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "Shrine", "time": "day",
        "rooms": {"clearing": {"name": "Shrine Clearing", "adjacent": []}},
        "positions": {"The Doctor": "clearing"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    repeated_move = (
        "acknowledge comment lightly, express interest in meeting after shrine, "
        "propose varied destination, and continue walking"
    )
    _turn_with_move(temp_db, chat_id, 137, char_id, {
        "response_candidates": [{
            "response": repeated_move, "selected": True,
        }],
        "active_state": {"goal": "propose a post-shrine destination"},
        "sequence": [{"type": "speech", "text": "Saturn or dragons?"}],
    })
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 138, "We're close.", time.time()),
    )
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Semantic repeat", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=138,
                      player_input="We're close.", created=time.time()),
        cast=cast, input="We're close.",
    )
    ctx.director_interpret = {
        "speech": "We're close.",
        "flow": {"reactors": [char_id], "tom_triggers": []},
    }
    ctx.perception_act = {
        "views": {str(char_id): 'Hinami says, "We\'re close."'},
        "observations": {str(char_id): []},
    }
    calls = []

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        calls.append(payload)
        if len(calls) == 1:
            return {
                "response_candidates": [{
                    "response": (
                        "Affirm interest in meeting her mother and propose "
                        "entirely new post-shrine destination to break repetition"
                    ),
                    "serves": ["i1"], "selected": True,
                }],
                "active_state": {
                    "mood": "bright", "goal": "offer another destination",
                    "wants": [{
                        "want": "offer another destination", "urgency": 0.8,
                        "serves": "i1",
                    }],
                },
                "sequence": [{
                    "type": "speech",
                    "text": "After the shrine, the archives of Calufrax?",
                }],
            }
        return {
            "response_candidates": [{
                "response": "ask about the unfamiliar bell now visible at the shrine",
                "serves": ["situational"], "selected": True,
            }],
            "active_state": {
                "mood": "curious", "goal": "understand the unfamiliar bell",
                "wants": [{
                    "want": "ask about the unfamiliar bell", "urgency": 0.7,
                    "serves": "situational",
                }],
            },
            "sequence": [{
                "type": "speech", "text": "What's that bell for?",
            }],
        }

    monkeypatch.setattr(character, "_agent_json", fake_agent_json)

    result = character.character_step(ctx, char_id, nonce=0)

    assert len(calls) == 2
    assert calls[0]["self"]["recent_self_moves"][0]["move"] == repeated_move
    assert calls[0]["self"]["steering_intention_ids"] == []
    assert calls[1]["move_correction"]["turn"] == 137
    assert "continuous excited riff or rant" in (
        calls[1]["move_correction"]["instruction"])
    assert calls[1]["intention_correction"]["nonsteering_ids"] == ["i1"]
    assert result["speech"] == "What's that bell for?"
