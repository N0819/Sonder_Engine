"""A stream that restarts mid-answer is read from its restart.

An aggregator that retries a generation upstream streams both attempts: a
fragment, then the whole answer again from its first brace. Measured on
NanoGPT's z-ai/glm-5.2:thinking (real-turn replay round 2, 2026-09-23): the
narrator's `{"{"prose": ...}` and a character's `{"effect{"effects":[]...}`,
each killing its beat. The answer is the object that runs to the end of the
text; an inner object that stops short of it is never taken.
"""

import pytest

from llm.llm_quality import strict_json_parse


def test_a_fragment_then_the_whole_answer_reads_as_the_answer():
    raw = '{"{"prose": "<p>The frame fights you.</p>", "new_specifics": []}'
    assert strict_json_parse(raw) == {
        "prose": "<p>The frame fights you.</p>", "new_specifics": []}
    raw = '{"effect{"effects": [], "sequence": [{"type": "speech"}]}'
    assert strict_json_parse(raw)["sequence"] == [{"type": "speech"}]


def test_a_truncated_answer_is_not_mistaken_for_its_inner_object():
    with pytest.raises(RuntimeError):
        strict_json_parse('{"state": {"mood": "calm"}, "sequence": [')


def test_a_whole_answer_is_read_as_before():
    assert strict_json_parse('{"a": {"b": 1}}') == {"a": {"b": 1}}
