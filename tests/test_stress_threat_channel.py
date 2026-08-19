"""The aversive half of the stress model had never run.

`resolve_stress` weights `threat` at 0.55 — the single largest term in strain —
and derived it from `appraisal["goal_impacts"]`. `affect.appraise` returns the
beat's impacts NORMALISED under `"impacts"`, and returns no key by that name at
all. So the loop never iterated, threat was 0.0 on every beat of every story,
and `overloaded` — which is strain-only — could not fire.

Measured live before the fix: 33 characters carry a resolved stress block,
`overloaded` had fired ZERO times ever, and strain never reached half its
threshold. Characters could be excited and could not be threatened.

The caller and the callee agreed about a payload's shape and were both wrong
about it, silently, for the life of the feature. So the channel is now an
explicit named argument: the next omission is a TypeError rather than a zero.
"""

from __future__ import annotations

import inspect

from mind import affect, psychology_runtime

PROFILE = {}
HEDONIC = {"charge": 0.0}
DREAD = [{"serves": "goal", "impact": -0.8, "certainty": 0.9}]


def _activation(**kw):
    return psychology_runtime.resolve_stress(
        {}, kw.pop("appraisal", {}), PROFILE, HEDONIC, 1, **kw
    ).get("activation", 0.0)


def test_a_threatening_beat_now_raises_activation():
    calm = _activation(appraisal={})
    threatened = _activation(appraisal={}, goal_impacts=DREAD)
    assert threatened > calm, (
        "threat is 55%% of strain and moved nothing: %r vs %r"
        % (threatened, calm))


def test_the_channel_appraise_actually_returns_is_read():
    """The exact defect. `appraise` is the only producer, and this is the
    shape it produces — a dict with `impacts`, and no `goal_impacts` key."""
    produced = affect.appraise(DREAD, lambda *_a, **_k: 1.0)
    assert "impacts" in produced and "goal_impacts" not in produced
    assert _activation(appraisal=produced) > _activation(appraisal={})


def test_the_old_spelling_still_works_for_an_older_caller():
    assert _activation(appraisal={"goal_impacts": DREAD}) \
        > _activation(appraisal={})


def test_a_beat_that_helps_a_goal_is_not_a_threat():
    """Threat is the aversive half only: a positive impact must not raise it,
    or every good outcome would read as strain."""
    good = [{"serves": "goal", "impact": 0.8, "certainty": 0.9}]
    assert _activation(appraisal={}, goal_impacts=good) \
        == _activation(appraisal={})


def test_the_channel_is_a_named_argument_not_a_dict_key():
    """A named argument is what makes the next omission loud."""
    sig = inspect.signature(psychology_runtime.resolve_stress)
    param = sig.parameters.get("goal_impacts")
    assert param is not None
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_the_live_caller_passes_it_explicitly():
    from persist import commit_memory

    source = inspect.getsource(commit_memory)
    assert "goal_impacts=appraisal_out.get(\"impacts\")" in source, (
        "the commit path stopped passing the impacts it just computed")
