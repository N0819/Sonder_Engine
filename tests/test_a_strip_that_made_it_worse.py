"""The JSON-mode recovery ladder must not end on a request the endpoint refuses.

`_strip_extended` drops the reasoning controls on the 400-retry path, and the
reason is measured: a provider whose model refuses the requested EFFORT
hard-400s rather than ignoring it ("Supported values are: high, max" on
nanogpt's GLM), so a call that would otherwise die is rescued by dropping it.

The opposite provider exists. OpenRouter's `google/gemini-3.8-flash` answers a
request with reasoning removed with `HTTP 400: "Reasoning is mandatory for this
endpoint and cannot be disabled."` So the ladder's LAST rung -- the one whose
whole job is to be the one that always works -- was categorically invalid
there, and the call died on an error with nothing to do with what it was
recovering from. Measured live 2026-09-20: it killed a story run outright.

The fix reads no provider prose and learns nothing. It adds one rung that puts
the reasoning controls back, and lets ORDER cover both directions: a provider
that hates the effort value succeeds on the stripped rung and never reaches the
restored one; a provider that requires reasoning fails the stripped rung and is
caught by it.
"""

from __future__ import annotations

from llm.providers import _json_mode_recovery_stages

PROV = {"kind": "openrouter"}


def _rungs(body):
    return [stage for stage, _refused
            in _json_mode_recovery_stages(dict(body), PROV, "m")]


BODY = {"model": "m", "messages": [], "reasoning_effort": "low",
        "top_k": 40, "response_format": {"type": "json_schema",
                                         "json_schema": {}}}


class TestTheLadderEndsSomewhereValid:
    def test_the_stripped_rung_still_comes_first(self):
        """The nanogpt case keeps its rescue, and keeps it BEFORE the
        restore -- a provider that rejects the effort value must never reach
        a rung that sends it again."""
        rungs = _rungs(BODY)
        stripped = next(i for i, r in enumerate(rungs)
                        if "reasoning_effort" not in r)
        restored = next(i for i, r in enumerate(rungs)
                        if i > stripped and "reasoning_effort" in r)
        assert stripped < restored

    def test_the_last_rung_puts_reasoning_back(self):
        last = _rungs(BODY)[-1]
        assert last["reasoning_effort"] == "low"
        assert "response_format" not in last
        assert "top_k" not in last, "the extended samplers stay stripped"

    def test_a_body_that_asked_for_no_reasoning_grows_no_rung(self):
        """Nothing to restore, so nothing to retry: the rung costs a request
        only where it can help."""
        plain = {k: v for k, v in BODY.items() if k != "reasoning_effort"}
        assert all("reasoning_effort" not in r for r in _rungs(plain))
        assert len(_rungs(plain)) == len(_rungs(BODY)) - 1

    def test_the_reasoning_dict_spelling_is_restored_too(self):
        body = dict(BODY)
        body.pop("reasoning_effort")
        body["reasoning"] = {"effort": "low"}
        assert _rungs(body)[-1]["reasoning"] == {"effort": "low"}


class TestItCostsNothingWhereItCouldNotHelp:
    """`test_json_object_400_fallback` caught this: a provider that rejects
    the effort VALUE ('none' on nanogpt's GLM) 400s on every rung, and an
    unconditional restore spent a fourth request proving it again.

    The rung is for a provider that REQUIRES reasoning, and "reasoning
    disabled" is precisely what such a provider refuses -- so restoring a
    disabling value can never turn a 400 into a 200."""

    def test_a_reasoning_off_role_grows_no_rung(self):
        """The early rungs still carry the body as written -- the question is
        whether a FOURTH one gets added to restore a value that cannot help."""
        off = _rungs(dict(BODY, reasoning_effort="none"))
        on = _rungs(dict(BODY, reasoning_effort="high"))
        assert len(off) == len(on) - 1
        assert "reasoning_effort" not in off[-1]

    def test_the_openrouter_spelling_of_off_is_also_skipped(self):
        """`_apply_reasoning_effort` writes `reasoning: {enabled: False}` for
        OpenRouter where it writes `reasoning_effort: 'none'` elsewhere; the
        same value in two spellings has to be read the same way."""
        body = dict(BODY)
        body.pop("reasoning_effort")
        body["reasoning"] = {"enabled": False}
        rungs = _rungs(body)
        assert "reasoning" not in rungs[-1]
        assert len(rungs) == len(_rungs(dict(BODY, reasoning_effort="high"))) - 1

    def test_an_enabled_effort_still_gets_its_rung(self):
        assert _rungs(dict(BODY, reasoning_effort="high"))[-1][
            "reasoning_effort"] == "high"
