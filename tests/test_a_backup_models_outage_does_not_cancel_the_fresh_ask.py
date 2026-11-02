"""A configured backup model that is down does not cost the beat its fresh ask.

The owner's ruling (2026-10-09, D5 of the Brackwater run): one fresh attempt
of the original request before a beat with a malformed answer aborts. The
gate on it read `last_provider_error is None`, and every rung wrote that --
the role's fallback candidates included. So a host who had configured a
backup model lost the very beat the ruling keeps: the primary answered
malformed twice, the backup's host returned 503, and the stage raised
"all providers failed" although the primary had answered both times; with
no backup configured the same beat was rescued (review 2026-11-01,
llm_providers_quality F3, scripted: `role_candidate_count=2` and a 503 on
the third call -> `RAISED`, calls `[(0, None), (0, 0.0), (1, 0.0)]`).

The fresh ask goes to the PRIMARY, so only the primary route's own outage
says it would fail; a backup's outage says nothing about it.
"""
from __future__ import annotations

import json

import pytest

from llm import llm_quality
from llm.providers import LLMError

GOOD = json.dumps({"events": [{
    "source_entity_id": "character:1", "source_event_id": "",
    "event": "Mara lifts the key", "observable": "", "speech": False,
    "targets": [], "movement": None, "commitment": "asserted",
    "item_names": ["key"],
    "transforms": [{"item": "key", "patch": {"inventory_ops": [
        {"op": "transfer", "object_id": "key", "from_id": "table",
         "to_id": "Mara", "relation": "held"}]}}]}],
    "missing_tools": [], "missing_referents": [], "notes": []})

#: Unparseable, and nothing a mend may touch: a value without its quotes.
UNMENDABLE = ('{"events": [{"event": Mara lifts the key}], '
              '"missing_tools": [], "missing_referents": [], "notes": []}')


class _Scripted:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append((kwargs.get("candidate_offset"),
                           kwargs.get("temperature")))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _ladder(monkeypatch, responses, candidates):
    llm = _Scripted(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count",
                        lambda role: candidates)
    return llm


def _run():
    return llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist",
        system="THE ENCODER SHEET", payload={"prose": "Mara lifts the key."},
        temperature=0.2)


def test_a_backup_that_is_down_still_leaves_the_fresh_ask(monkeypatch):
    llm = _ladder(monkeypatch, [
        UNMENDABLE,                                     # the primary
        UNMENDABLE,                                     # its rebuild
        LLMError("HTTP 503: fallback host down", 503, True),   # the backup
        GOOD,                                           # the fresh ask
    ], candidates=2)
    out = _run()
    assert out["events"][0]["event"] == "Mara lifts the key"
    assert llm_quality.answered_by.get() == "fresh"
    assert llm.calls[-1][0] == 0, "the fresh ask goes to the primary"


def test_without_a_backup_the_same_beat_is_kept_as_before(monkeypatch):
    _ladder(monkeypatch, [UNMENDABLE, UNMENDABLE, GOOD], candidates=1)
    _run()
    assert llm_quality.answered_by.get() == "fresh"


def test_the_primary_route_s_own_outage_still_skips_it(monkeypatch):
    """The rebuild on the primary itself erroring is the primary failing:
    no fresh ask is sent to a route that just refused, and the stage says
    which provider failed."""
    llm = _ladder(monkeypatch, [
        UNMENDABLE,
        LLMError("HTTP 503: primary host down", 503, True),
    ], candidates=1)
    with pytest.raises(RuntimeError, match="primary host down"):
        _run()
    assert len(llm.calls) == 2


def test_a_backup_outage_with_no_rescue_still_names_it(monkeypatch):
    """The final message keeps the backup's error when nothing validated."""
    _ladder(monkeypatch, [
        UNMENDABLE, UNMENDABLE,
        LLMError("HTTP 503: fallback host down", 503, True),
        UNMENDABLE,
    ], candidates=2)
    with pytest.raises(RuntimeError, match="fallback host down"):
        _run()
