"""The resolve's span report judges the resolve's own records.

Both stages number their chronology from 1. The interpret's records keep
their interpret ids (`from_event`) when its assertions are merged into the
resolve's diff, so the resolve's coherency report
(`director_evidence.span_result_findings`) read interpret record k as
resolve span k's. Measured on the owner's chat 177 turn 22: resolve spans
1-3 were `speech`, `attention`, `speech`, and the report filed
"written_by_non_owner (objects) inventory_ops[0]", "(spatial)
poses.Mellisande", "(objects) inventory_ops[1]" -- exactly the interpret's
rows 1-3. And `speech` is the one channel the ENGINE compiles (no owner by
design), so every line was reported `unowned_channel` (turn 21). Both went
to the next beat's Director as corrections (review 2026-11-01, director
core F7).
"""

from __future__ import annotations

from agents.director import SPECIALISTS, span_owners, span_result_findings


def _dispatch():
    return {name: {"channels": list(spec["channels"]), "ran": True,
                   "events_resolved": []}
            for name, spec in SPECIALISTS.items()}


INTERPRET_ROW = {"op": "take", "item": "cup", "to_id": "The Stranger", "from_event": 1}


def _merged():
    return {
        # the interpret's record, citing ITS chrono 1, merged in
        "inventory_ops": [dict(INTERPRET_ROW)],
        # the resolve's own record for its span 1
        "poses": {"Mara": {"posture": "standing", "from_event": 1}},
        # the engine's compiled speech
        "speech": [{"speaker": "Mara", "event": "Who's there?", "from_event": 1}],
    }


def test_an_interpret_record_is_not_read_as_the_resolve_span_with_its_number():
    spans = [{"event_id": 1, "categories": ["poses"], "category": "poses"}]
    onset = {"inventory_ops": [dict(INTERPRET_ROW)]}
    findings = span_result_findings(_merged(), spans, _dispatch(), span_owners,
                                    exclude=onset)
    assert findings == [], findings


def test_the_engines_compiled_speech_is_no_hands_unowned_write():
    spans = [{"event_id": 1, "categories": ["poses"], "category": "poses"}]
    findings = span_result_findings(
        {k: v for k, v in _merged().items() if k != "inventory_ops"},
        spans, _dispatch(), span_owners)
    assert [f["kind"] for f in findings] == [], findings


def test_a_resolve_record_a_non_owner_wrote_is_still_reported():
    """The report keeps its teeth for the resolve's own records."""
    spans = [{"event_id": 1, "categories": ["poses"], "category": "poses"}]
    sd = {"inventory_ops": [{"op": "drop", "item": "lamp", "from_event": 1}],
          "poses": {"Mara": {"posture": "standing", "from_event": 1}}}
    findings = span_result_findings(sd, spans, _dispatch(), span_owners,
                                    exclude={})
    assert [(f["kind"], f["hand"]) for f in findings] == [
        ("written_by_non_owner", "objects")], findings
