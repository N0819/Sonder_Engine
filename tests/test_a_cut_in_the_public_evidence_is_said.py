"""The public evidence a beat files for the charter's witnesses is cut at two
named numbers, and a cut is said.

`_resolve_beat_view` kept the first 20 public sources (`public_sources[:20]`)
and `_ground_public_evidence` the first 12 grounded records
(`grounded[:12]`), both bare literals, both silent -- though the grounding's
docstring and AGENTS.md promise "every legitimate source receives a
deterministic fallback record". Sources come player speech first, then each
declarer's speech, then actions, so on a crowded beat the actions go first
and the town's bodies never witness them (review 2026-11-01, director floors
F14; director core F16 is the second number). The numbers are the owner's:
they are named here and kept, and a beat that hits either now says so.
"""

from __future__ import annotations

from agents import director
from agents.director import (PUBLIC_SOURCES_SHOWN, _ground_public_evidence,
                             _resolve_beat_view)


def _crowded_beat(n):
    interp = {"sequence": [
        {"type": "action", "attempt": f"moves crate {i}",
         "observable": f"moves crate {i}", "visibility": "overt",
         "conceal_from": [], "targets": []}
        for i in range(n)]}
    return _resolve_beat_view({"resolved_event": "", "dialogue_log": []},
                              [], {}, [], "Rowan", interp)


def test_both_cuts_keep_their_numbers_and_are_said():
    view = _crowded_beat(25)
    assert len(view["public_sources"]) == PUBLIC_SOURCES_SHOWN == 20
    out = {"dialogue_log": [], "public_evidence": []}
    said = []
    _ground_public_evidence(out, view, warn=said.append)
    assert len(out["public_evidence"]) == director.PUBLIC_EVIDENCE_KEPT == 12
    assert [w for w in said if "5" in w and "PUBLIC_SOURCES_SHOWN" in w], said
    assert [w for w in said if "8" in w and "PUBLIC_EVIDENCE_KEPT" in w], said


def test_a_beat_under_both_numbers_says_nothing():
    view = _crowded_beat(3)
    out = {"dialogue_log": [], "public_evidence": []}
    said = []
    _ground_public_evidence(out, view, warn=said.append)
    assert len(out["public_evidence"]) == 3 and said == []
