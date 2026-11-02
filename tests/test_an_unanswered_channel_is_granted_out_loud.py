"""A channel the decision model left unanswered is granted, out loud -- never
read as a confident "no".

`select_channels` FAILS OPEN: when the decision model cannot answer, every
candidate is granted, a larger encoder sheet rather than a lost change. But a
reply that came back WITHOUT one of the keys it was asked (models split and
drop keyed answers) was read through `decisions.probability(None)`, which is
0.0 -- so the one channel left out was refused as untouched, silently, and its
change could not be written (review 2026-11-01, llm_schemas_prompts F7;
`decisions.unanswered` names the class). The missing channel now fails open
like the rest of the call: it is selected, `record["unanswered"]` lists it and
the stage warns. A channel the model answered "no" is still refused.
"""

from __future__ import annotations

from types import SimpleNamespace

from agents import director_prose
from llm import decisions

PROSE = "Mara shifts her weight and settles against the rail."
OMITTED = "poses"
REFUSED = "attire"


def _select(monkeypatch, *, omit):
    warnings = []
    asked = []

    def jev(state, questions):
        asked.append(dict(questions))
        return {key: {"type": "noul", "noul": 0.0}
                for key in questions if key not in omit}

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    ctx = SimpleNamespace(language="en", add_warning=warnings.append)
    selected, record = director_prose.select_channels(
        ctx, "resolve", PROSE, {"identity_index": {}}, facts={})
    assert asked and OMITTED in asked[0] and REFUSED in asked[0]
    return selected, record, warnings


def test_a_channel_left_unanswered_is_granted_and_said(monkeypatch):
    selected, record, warnings = _select(monkeypatch, omit={OMITTED})
    assert OMITTED in selected
    assert record["unanswered"] == [OMITTED]
    assert any(OMITTED in w and "unanswered" in w and "fail-open" in w
               for w in warnings), warnings


def test_a_channel_answered_no_is_still_refused(monkeypatch):
    selected, record, _warnings = _select(monkeypatch, omit={OMITTED})
    assert REFUSED not in selected
    assert REFUSED not in (record.get("unanswered") or [])
    assert record["probabilities"][REFUSED] == 0.0


def test_a_full_answer_grants_nothing_unasked_and_says_nothing(monkeypatch):
    selected, record, warnings = _select(monkeypatch, omit=set())
    assert OMITTED not in selected and REFUSED not in selected
    assert "unanswered" not in record
    assert not any("unanswered" in w for w in warnings), warnings
