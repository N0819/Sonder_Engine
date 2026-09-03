"""A thinking model's trace has a channel of its own.

`token_sink` carries player-facing prose, and `_sse_openai` says outright that
a model's private thinking is not that -- which is right for the story, where
the reader is a player. The Writers' Room is the case the rule does not cover:
its reader is the AUTHOR, who is the host, and showing an author the room's
working is the ordinary thing an assistant does.

So the trace gets a second sink rather than a relaxation of the first. Every
existing caller arms neither and is unchanged.
"""
import inspect

from llm import providers


def test_the_two_sinks_are_separate_contextvars():
    assert providers.reasoning_sink is not providers.token_sink
    assert providers.reasoning_sink.get() is None, "armed by nobody by default"


def test_both_streaming_branches_feed_it():
    for fn in (providers._sse_openai, providers._sse_openai_async):
        src = inspect.getsource(fn)
        assert "_think_sink = reasoning_sink.get()" in src, fn.__name__
        assert "_think_sink(_r)" in src, fn.__name__


def test_the_trace_never_reaches_the_prose_sink():
    """The story path must not start narrating a model's thinking, which is
    the failure the separation exists to make impossible."""
    import re
    for fn in (providers._sse_openai, providers._sse_openai_async):
        src = inspect.getsource(fn)
        # the prose sink is fed only from the content delta; the trace
        # variable must never be handed to it (`_think_sink` is not it)
        assert not re.search(r"(?<!_think_)\bsink\(_r\)", src), fn.__name__


def test_the_lookup_is_hoisted_out_of_the_delta_loop():
    """One contextvar read per response, not per token."""
    for fn in (providers._sse_openai, providers._sse_openai_async):
        src = inspect.getsource(fn)
        assert src.count("reasoning_sink.get()") == 1, fn.__name__


def test_an_armed_sink_receives_the_trace(monkeypatch):
    seen = []
    token = providers.reasoning_sink.set(seen.append)
    try:
        sink = providers.reasoning_sink.get()
        assert sink is not None
        sink("weighing the harbour plan")
    finally:
        providers.reasoning_sink.reset(token)
    assert seen == ["weighing the harbour plan"]
    assert providers.reasoning_sink.get() is None
