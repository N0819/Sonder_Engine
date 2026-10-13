"""AN ANSWER IS NEVER CUT AT ITS FIRST BRACE (`llm_quality._answer_goes_on`).

Measured, Home 10 (chat 173, capture 6087, 2026-10-12): after the fourth
step of `sequence` the model wrote `}],` where it meant `},{`. The answer's
object therefore closed at character 1138 of 1,841, and the text went on --
`],"demeanor":...,"tells":...,"changes":...,"note":...,"notebook":[...]}`.
The reader took the first balanced object and dropped the rest without a
word: Tamamo's beat committed four steps, an empty note and no notebook, and
the capture row said ok with an empty error. The room designer's captures
5697 and 6055 lost their notes the same way. Those three are every such
answer among the 5,327 captured; the thirteen other answers read out of
surrounding text -- a whole object in prose, or followed by stray closers or
markup -- read exactly as they did.

Now an answer whose object closed early and goes on is mended whole
(`llm/json_mend.py`, the whole text and then its first brace to its last),
on every rung of the ladder and for every caller outside it; where no mend
reads it whole, the object stands as it closed -- as before -- and the loss
is said. A key an object names twice is said too (7 of the 5,327).
"""
from __future__ import annotations

import json

import pytest

from core.pipeline_context import current_exchange_sink, current_warning_sink
from llm import llm_quality

STEPS = ('{"do": "sets the cup down", "why": "to free her hands"}, '
         '{"say": "Stay a while.", "to": "Hinami", "why": "she means it"}')
REST = ('"demeanor": "composed", "tells": ["tails low"], "changes": ["calmer"], '
        '"note": "kept", "notebook": [{"id": "visits", "about": "her visits", '
        '"sure": "likely"}]')
#: Capture 6087's shape, in words of its own: the list's last item closed
#: with `}],` where `},{` was meant, so the next step's members land in the
#: answer's own object, which closes early, and the answer goes on after it.
SLIP = ('{"want": "to be heard", "sequence": [' + STEPS + '], '
        '"ponder": "the sound of her laugh", "why": "it stays with her"}], ' + REST + '}')
#: The same slip followed by a value no mend may touch (a word without its
#: quotes): nothing reads it whole.
UNMENDABLE_SLIP = ('{"want": "to be heard", "sequence": [' + STEPS + ']}], '
                   '"demeanor": composed, "note": "kept"}')
#: Unparseable and unmendable from its first character.
BROKEN = '{"sequence": [{"do": sets the cup down}]}'


class _Scripted:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        if not self.responses:
            raise AssertionError("chat_complete called more times than scripted")
        return self.responses.pop(0)


@pytest.fixture
def seen():
    warnings, rows = [], []
    w = current_warning_sink.set(warnings.append)
    r = current_exchange_sink.set(rows.append)
    yield warnings, rows
    current_exchange_sink.reset(r)
    current_warning_sink.reset(w)


def _ladder(monkeypatch, responses, candidates=1):
    from llm import providers
    llm = _Scripted(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: candidates)
    monkeypatch.setattr(providers, "max_output_tokens", lambda: 20000)
    # the cheap patch rung is a model call of its own; these cases are about
    # the rungs that READ an answer
    monkeypatch.setattr(llm_quality, "_targeted_field_patch", lambda *a, **k: None)
    return llm


def _run():
    return llm_quality.complete_validated_json(
        role="character_major", step_key="character_bare", system="THE SHEET",
        payload={"x": 1}, temperature=0.4)


# -------------------------------------------------------------- the read itself


class TestTheAnswerGoesOn:
    @pytest.mark.parametrize("text", [
        SLIP,
        '{"a": 1}, "b": 2}',                       # a comma, then a key
        '{"a": 1}]"b": 2}',                        # stray closers, then a key
        '{"a": {"x": 1}}], {"y": 2}, "b": 3}',     # an item left behind, then a key
    ])
    def test_a_member_after_the_close_is_more_of_the_answer(self, text):
        _value, _notes, goes_on = llm_quality._read_json(text)
        assert goes_on

    @pytest.mark.parametrize("text", [
        '{"a": 1} and that is all.',               # prose
        '{"a": 1}\nI used {} for the empty case.', # commentary quoting JSON
        '{"a": 1}\n{}',                            # a stray object
        '{"a": 1}]}',                              # stray closers alone
        'Sure, {"a": 1}',                          # a preamble ending in a comma
        'Here is the answer:\n```json\n{"a": 1}\n```\nDone.',
    ])
    def test_an_object_in_prose_or_before_stray_text_reads_as_it_did(self, text):
        assert llm_quality.strict_json_parse(text) == {"a": 1}

    @pytest.mark.parametrize("text", [
        '{"a": 1} and that is all.', '{"a": 1}\nI used {} for the empty case.',
        '{"a": 1}\n{}', '{"a": 1}]}', 'Sure, {"a": 1}'])
    def test_and_none_of_them_is_read_as_going_on(self, text):
        assert not llm_quality._read_json(text)[2]

    def test_a_restart_is_still_read_from_its_restart(self):
        text = '{"{"prose": "<p>The frame fights you.</p>"}'
        assert llm_quality.strict_json_parse(text) == {"prose": "<p>The frame fights you.</p>"}

    def test_outside_the_ladder_the_answer_is_read_whole(self):
        assert llm_quality.strict_json_parse(SLIP)["note"] == "kept"
        assert llm_quality.strict_json_parse("Here it is:\n" + SLIP)["notebook"]

    def test_the_rooms_reader_reads_it_whole_too(self):
        from agents.common import jparse
        assert jparse(SLIP)["note"] == "kept"

    def test_what_no_mend_reads_whole_stands_as_it_closed(self):
        value = llm_quality.strict_json_parse(UNMENDABLE_SLIP)
        assert value["sequence"] and "note" not in value, "what it returned before"


# ------------------------------------------------------------------- the ladder


class TestEveryRungReadsItWhole:
    def test_the_first_answer(self, monkeypatch, seen):
        warnings, rows = seen
        llm = _ladder(monkeypatch, [SLIP])
        out = _run()
        assert out["note"] == "kept" and out["notebook"] and out["tells"] == ["tails low"]
        assert len(llm.calls) == 1, "no model call buys it back"
        assert llm_quality.answered_by.get() == "mended"
        assert any("closed early" in w for w in warnings)
        assert any("read whole by mending" in w for w in warnings)
        # it stood, and its row says how it was read -- the row for 6087 said
        # ok with an empty error while the read had dropped half the answer
        (row,) = rows
        assert row["ok"] is True and "read:" in row["error"] and "mending" in row["error"]

    def test_behind_a_preamble(self, monkeypatch, seen):
        llm = _ladder(monkeypatch, ["Here is Tamamo's beat:\n\n" + SLIP + "\n\nThat is all."])
        assert _run()["note"] == "kept"
        assert len(llm.calls) == 1

    def test_the_re_ask_with_room(self, monkeypatch, seen):
        llm = _ladder(monkeypatch, ['{"sequence": [{"do": "sets the cu', SLIP])
        assert _run()["note"] == "kept"
        assert llm_quality.answered_by.get() == "room_reask"
        assert len(llm.calls) == 2

    def test_the_re_ask_after_an_empty_object(self, monkeypatch, seen):
        _ladder(monkeypatch, ["{}", SLIP])
        assert _run()["note"] == "kept"
        assert llm_quality.answered_by.get() == "stall_reask"

    def test_the_rebuild(self, monkeypatch, seen):
        _ladder(monkeypatch, ['{"want": "to be heard"}', SLIP])
        assert _run()["note"] == "kept"
        assert llm_quality.answered_by.get() == "rebuild"

    def test_a_fallback_candidate(self, monkeypatch, seen):
        _ladder(monkeypatch, ['{"want": "a"}', '{"want": "b"}', SLIP], candidates=2)
        assert _run()["note"] == "kept"
        assert llm_quality.answered_by.get() == "fallback:1"

    def test_the_fresh_ask(self, monkeypatch, seen):
        _ladder(monkeypatch, [BROKEN, BROKEN, SLIP])
        assert _run()["note"] == "kept"
        assert llm_quality.answered_by.get() == "fresh"

    def test_what_no_mend_reads_whole_stands_as_it_closed_and_says_so(self, monkeypatch, seen):
        warnings, rows = seen
        llm = _ladder(monkeypatch, [UNMENDABLE_SLIP])
        out = _run()
        assert out["sequence"] and out["note"] == "", "the object as it closed, as before"
        assert len(llm.calls) == 1
        assert any("rest is left out" in w for w in warnings)
        assert "left out" in rows[0]["error"], "the row no longer says nothing"


class TestAKeyNamedTwiceIsSaid:
    def test_the_later_value_stands_and_the_step_says_so(self, monkeypatch, seen):
        warnings, rows = seen
        twice = ('{"sequence": [{"do": "waits", "why": "x"}], "note": "first", '
                 '"note": "second"}')
        _ladder(monkeypatch, [twice])
        assert _run()["note"] == "second"
        assert any("names 'note' twice" in w for w in warnings)
        assert rows[0]["ok"] is True and "names 'note' twice" in rows[0]["error"]

    def test_an_answer_that_names_nothing_twice_says_nothing(self, monkeypatch, seen):
        warnings, rows = seen
        _ladder(monkeypatch, [json.dumps({"sequence": [{"do": "waits"}], "note": "n"})])
        _run()
        assert not warnings and rows[0]["error"] == ""
