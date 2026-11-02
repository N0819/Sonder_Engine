"""The rebuild is told what is wrong with the object it is handed.

When the targeted field patch does not validate, the ladder kept the PATCHED
object for the rebuild but left `report` -- the error list -- as the
UNPATCHED object's (review 2026-11-01, llm_providers_quality F11). So an
answer failing on fields X and Y, whose patch fixed X and left Y, sent the
rebuild an object where X is right with an error list saying X is wrong and
nothing about anything the patch broke; and the thinner-rebuild check
(`_unshrunk`) then pruned the pre-patch error paths -- the repaired X -- from
the kept answer. Object and errors now travel as one pair.
"""
from __future__ import annotations

import json

from llm import llm_quality

FIRST = json.dumps({"events": [{"event": "Mara waits", "seconds": "a while",
                                "until_hour": "dusk"}],
                    "missing_tools": [], "missing_referents": [], "notes": []})
REBUILT = json.dumps({"events": [{"event": "Mara waits", "seconds": 30,
                                  "until_hour": 18}],
                      "missing_tools": [], "missing_referents": [], "notes": []})


def test_the_rebuild_payload_names_only_what_the_patch_left(monkeypatch):
    sent = []

    def fake(role, system, user, **kwargs):
        sent.append((role, json.loads(user)))
        if role == "repair":
            # The patch fixes `seconds` and leaves `until_hour` as it was.
            return json.dumps({"events.0.seconds": 30})
        if len(sent) == 1:
            return FIRST
        return REBUILT

    monkeypatch.setattr(llm_quality, "chat_complete", fake)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="SHEET",
        payload={"prose": "Mara waits."}, temperature=0.2)

    rebuild = [payload for role, payload in sent
               if isinstance(payload, dict) and "previous_parsed_output" in payload]
    assert rebuild, [role for role, _ in sent]
    handed = rebuild[0]
    assert handed["previous_parsed_output"]["events"][0]["seconds"] == 30
    errors = handed["validation_errors"]
    assert any(e.startswith("events.0.until_hour") for e in errors), errors
    assert not any(e.startswith("events.0.seconds") for e in errors), (
        "the rebuild was told a field the patch had fixed is wrong")
    assert out["events"][0]["seconds"] == 30
