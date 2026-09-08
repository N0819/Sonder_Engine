"""One predicate decides what counts as a model's private trace (B31/A28).

The blocking reader (`_reasoning_text`) and the stream reader
(`_delta_reasoning`) each have to answer "is this key a reasoning trace?".
A28 measured what happens when they answer it separately: the stream read a
two-spelling list (`reasoning`, `reasoning_content`) while the blocking path
read by what the key says it is, so a `reasoning_details` block was kept on
one transport and dropped on the other. The joining still differs by
transport -- a stream's fragments keep their whitespace, a whole message is
stripped -- but what the two look AT is one fact, held in one place.
"""

from llm import providers


def test_both_transports_read_the_same_key_predicate(monkeypatch):
    # Redefining the one predicate must move both readers. If either keeps
    # its own copy, one of these assertions still sees the old answer.
    monkeypatch.setattr(providers, "_is_reasoning_key",
                        lambda key: str(key) == "cogitation")
    assert providers._delta_reasoning({"cogitation": "a", "reasoning": "b"}) == "a"
    assert providers._reasoning_text({"cogitation": "a", "reasoning": "b"}) == "a"


def test_the_predicate_reads_what_the_key_says_it_is():
    for key in ("reasoning", "reasoning_content", "reasoning_details",
                "thinking"):
        assert providers._is_reasoning_key(key), key
    for key in ("content", "role", "tool_calls", "refusal"):
        assert not providers._is_reasoning_key(key), key


def test_the_readers_still_differ_only_in_how_they_join():
    # A stream fragment's whitespace is part of the trace; a whole message is
    # stripped and its blocks are one per line.
    assert providers._delta_reasoning({"reasoning": " and"}) == " and"
    assert providers._reasoning_text({"reasoning": " and "}) == "and"
    blocks = {"reasoning_details": [{"text": "first"}, {"text": "second"}]}
    assert providers._delta_reasoning(blocks) == "first\nsecond"
    assert providers._reasoning_text(blocks) == "first\nsecond"
