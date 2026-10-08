"""More room is for an answer thinking crowded out.

The length escalation in `complete_validated_json` re-asks a truncated answer
once with one stage's worth more room, on the premise that a reasoning model
bills its thinking as output and the thinking squeezed the answer out. A stop
whose budget went to the ANSWER breaks that premise, and more room only buys
a longer runaway.

Measured on the Brackwater run (chat 166, 2026-10-07, capture 6416, turn
4592): the narrator closed a whole page, wrote it again into the grammar's
optional `text`, and went on into `<fragment>1</fragment>` ...
`<fragment>5521</fragment>` until the 50,000-token cap -- 238.8 s, 138,724
characters of answer against a 33,466-character trace. It was re-asked at
70,000 and answered in 10,893 output tokens: the fresh sample rescued the
beat, never the room. `providers.answer_ran_away` now tells the two stops
apart on the provider's own word (its finish reason and its reasoning-token
count), and a runaway is re-asked at its own budget.
"""

import json
import time

import pytest

from llm import llm_quality
from llm import providers

#: The measured shape, shortened: a page that closed whole, then a second
#: copy in `text` running into a tag loop, cut off mid-string by the cap.
RUNAWAY = ('{"prose": "<p>Hester came in behind her.</p>", "text": "Hester came '
           'in behind her.\\n\\n'
           + "".join(f"<fragment>{i}</fragment>" for i in range(1, 80)))
#: A narrator answer that thinking crowded out: the object barely begun.
CROWDED_OUT = '{"prose": "<p>Hester came'
PAGE = json.dumps({"prose": "<p>Hester came through the threshold behind her.</p>",
                   "new_specifics": []})


class _Provider:
    """Stands in for `llm_quality.chat_complete` AND for what the provider
    reports about each answer: its finish reason and its output-token spend,
    set on this context exactly where a real completion sets them."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        if not self.answers:
            raise AssertionError("chat_complete called more times than scripted")
        text, finish, output, reasoning = self.answers.pop(0)
        providers._capture_finish_reason(finish)
        providers.last_output_spend.set(
            None if output is None else {"output": output, "reasoning": reasoning})
        return text


@pytest.fixture(autouse=True)
def _clean_provider_slots():
    yield
    providers._capture_finish_reason(None)
    providers.last_output_spend.set(None)


def _script(monkeypatch, answers, ceiling=50000):
    llm = _Provider(answers)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    # The ceiling is read from the settings table; the owner's install runs
    # at 50,000, which is where the measured runaway stopped.
    monkeypatch.setattr(providers, "max_output_tokens", lambda: ceiling)
    return llm


def _narrate(**kwargs):
    return llm_quality.complete_validated_json(
        role="narrator", step_key="narrator", system="sys", payload={"x": 1},
        **kwargs)


def _stop(finish, output, reasoning):
    providers._capture_finish_reason(finish)
    providers.last_output_spend.set({"output": output, "reasoning": reasoning})
    return providers.answer_ran_away()


def test_a_runaway_answer_is_asked_again_at_its_own_budget(monkeypatch):
    llm = _script(monkeypatch, [(RUNAWAY, "length", 50000, 8200),
                                (PAGE, "stop", 10893, 9000)])

    out = _narrate()

    assert "threshold" in out["prose"]
    assert len(llm.calls) == 2, "one re-ask, not a ladder"
    assert llm.calls[1]["max_tokens"] == llm.calls[0]["max_tokens"], (
        "a runaway is not short of room; the re-ask keeps the budget")
    assert llm.calls[1]["token_ceiling"] is None, (
        "no ceiling past the configured one")
    assert llm.calls[1]["system"] == "sys"
    assert llm.calls[1]["user"] == llm.calls[0]["user"], (
        "the original request, never a repair prompt")


def test_an_answer_thinking_crowded_out_still_gets_more_room(monkeypatch):
    llm = _script(monkeypatch, [(CROWDED_OUT, "length", 50000, 49600),
                                (PAGE, "stop", 52000, 51000)])

    _narrate()

    assert llm.calls[1]["max_tokens"] == 70000
    assert llm.calls[1]["token_ceiling"] == 70000


def test_a_long_answer_under_a_small_budget_still_gets_more_room(monkeypatch):
    """A deliberately small call that the answer simply outgrew has written
    nothing past what a stage writes; the escalation is its remedy."""
    llm = _script(monkeypatch, [(CROWDED_OUT, "length", 1000, 0),
                                (PAGE, "stop", 1200, 0)])

    _narrate(max_tokens=1000)

    assert llm.calls[1]["max_tokens"] == 21000


def test_an_unmeasured_stop_escalates_as_it_always_did(monkeypatch):
    """A provider that does not split reasoning out has not said where the
    budget went, and silence is not evidence of a runaway."""
    llm = _script(monkeypatch, [(RUNAWAY, "length", 50000, None),
                                (PAGE, "stop", 900, None)])

    _narrate()

    assert llm.calls[1]["max_tokens"] == 70000


def test_the_runaway_re_ask_is_visible_in_the_live_turn_view(monkeypatch):
    _script(monkeypatch, [(RUNAWAY, "length", 50000, 8200),
                          (PAGE, "stop", 10893, 9000)])
    seen = []
    token = providers.generation_event_sink.set(seen.append)
    try:
        _narrate()
    finally:
        providers.generation_event_sink.reset(token)

    assert [e["type"] for e in seen] == ["generation_reset"]
    assert "ran away" in seen[0]["reason"]
    assert "same budget" in seen[0]["reason"]


def test_a_lost_runaway_says_so_rather_than_asking_for_more_room(monkeypatch):
    _script(monkeypatch, [(RUNAWAY, "length", 50000, 8200)] * 2)

    with pytest.raises(RuntimeError) as exc:
        _narrate(repair_attempts=0)

    msg = str(exc.value)
    assert "RESPONSE TRUNCATED" in msg
    assert "ran away" in msg
    assert "Max output tokens" not in msg, (
        "raising the ceiling is the wrong advice for an answer that ran away")


class TestTheProvidersWordDecides:
    """`answer_ran_away` answers from the finish reason and the reported
    reasoning tokens, never from the answer's text."""

    def test_the_measured_runaway_reads_as_one(self):
        assert _stop("length", 50000, 8200)

    def test_a_normal_stop_is_never_a_runaway(self):
        assert not _stop("stop", 50000, 8200)

    def test_an_answer_thinking_crowded_out_is_not(self):
        assert not _stop("length", 50000, 49600)

    def test_more_thinking_than_answer_is_not(self):
        """An answer past one stage's worth that still spent less than the
        thinking did: the thinking may be what ran out the budget."""
        assert not _stop("length", 50000, 26000)

    def test_a_call_capped_at_one_stages_worth_is_never_read_as_one(self):
        """At the default ceiling the answer cannot pass one stage's worth,
        so the stop escalates exactly as before."""
        cap = providers.MAX_OUTPUT_TOKENS_DEFAULT
        assert not _stop("length", cap, 0)

    def test_a_silent_provider_is_unmeasured_not_a_runaway(self):
        assert not _stop("length", 50000, None)
        providers._capture_finish_reason("length")
        providers.last_output_spend.set(None)
        assert not providers.answer_ran_away()

    def test_the_bound_widens_with_the_storys_language(self):
        """Japanese spends about twice the tokens for the same answer, and
        every budget in the engine is widened by the pack's own factor."""
        from language_runtime import language_scope

        with language_scope("ja"):
            assert not _stop("length", 50000, 14000)   # 36k answer, under 40k
            assert _stop("length", 50000, 8200)        # 41.8k answer


class TestTheSpendIsTheProvidersOwnCount:

    def test_openrouter_reports_reasoning_under_completion_details(self):
        usage = {"completion_tokens": 50000,
                 "completion_tokens_details": {"reasoning_tokens": 8200}}
        assert providers._reasoning_tokens(usage) == 8200

    def test_the_responses_dialect_is_read_too(self):
        usage = {"output_tokens": 900,
                 "output_tokens_details": {"reasoning_tokens": 700}}
        assert providers._reasoning_tokens(usage) == 700

    def test_a_provider_that_splits_nothing_out_is_unmeasured(self):
        assert providers._reasoning_tokens({"output_tokens": 900}) is None
        assert providers._reasoning_tokens(None) is None
        assert providers._reasoning_tokens(
            {"completion_tokens_details": {"reasoning_tokens": "x"}}) is None

    def test_a_logged_call_leaves_its_spend_on_the_context(self):
        providers._log_usage(
            "narrator", "z-ai/glm-5.2", time.time(),
            {"prompt_tokens": 12540, "completion_tokens": 50000,
             "completion_tokens_details": {"reasoning_tokens": 8200}})
        assert providers.last_output_spend.get() == {
            "output": 50000, "reasoning": 8200}

    def test_the_stream_the_pipeline_runs_records_it(self, monkeypatch):
        """The streaming branch is the one every engine turn runs."""
        lines = [b"data: " + json.dumps(c).encode() for c in (
            {"choices": [{"delta": {"content": '{"prose": "<p>a'}}]},
            {"choices": [{"delta": {}, "finish_reason": "length"}]},
            {"choices": [], "usage": {
                "prompt_tokens": 10, "completion_tokens": 30000,
                "completion_tokens_details": {"reasoning_tokens": 1000}}},
        )] + [b"data: [DONE]"]

        class FakeResp:
            status_code = 200

            def iter_lines(self):
                return iter(lines)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(
            providers, "_session",
            lambda: type("S", (), {"post": lambda *a, **k: FakeResp()})())
        providers._sse_openai("u", {}, {}, lambda d: None,
                              role="narrator", model="m")
        assert providers.response_truncated()
        assert providers.last_output_spend.get() == {
            "output": 30000, "reasoning": 1000}
        assert providers.answer_ran_away()

    def test_a_new_completion_starts_unmeasured(self, monkeypatch):
        """A call that dies before its usage arrives must not inherit the
        previous call's spend, or a stale runaway reading could cost a
        crowded-out answer its room."""
        monkeypatch.setattr(providers, "resolve_role_candidates",
                            lambda role: [({"kind": "openai",
                                            "base_url": "http://x",
                                            "api_key": "", "name": "p"},
                                           "m", {})])

        def refuse(*a, **k):
            raise providers.LLMError("HTTP 400: no", 400, False)

        monkeypatch.setattr(
            providers, "_session", lambda: type("S", (), {"post": refuse})())
        providers.last_output_spend.set({"output": 50000, "reasoning": 0})
        with pytest.raises(Exception):
            providers._chat_complete_once(
                "narrator", "sys", "user", None, True, 100, None)
        assert providers.last_output_spend.get() is None
