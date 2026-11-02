"""A draft is attributed to its sentences once, however many readers ask.

`director_repair.attribute` scores every (event, sentence) pair by trigram
share and, for the sentences an event may hold whole, a longest-common-run
search (`_holds`, `difflib.SequenceMatcher`). One check-and-repair pass asked
it of the SAME draft from every reader -- `citations`, `battery`,
`jev_state`, `declared_gaps`, `bridge`, `explain_wrong`, each repair call's
`_draft` and sources, `place`, the re-check, `_declared_left`: 7 calls a
stage with no jobs, 18 with jobs and retries. Measured by the audit of
2026-11-01 (`agents_director_floors` E1) on a 3,354-character account (36
sentences, 17 events): 71 ms a call, 0.5-1.3 s of CPU a stage. Remembered by
the texts it reads, the answer is computed once per version of the draft
and handed to every reader unchanged.
"""

from __future__ import annotations

from agents import director, director_repair as repair
from llm import decisions

PROSE = ("Odalys sets the brass astrolabe down on the chart table. "
         "\"The bearings drifted overnight,\" she says. "
         "She turns toward the companionway.")


def _declaring():
    return {"identity_index": {"character:7": "Odalys"}, "event_inputs": [
        {"entity_id": "character:7", "authority_mode": "autonomous", "events": [
            {"event_id": "t:0:action", "type": "action",
             "attempt": "set the astrolabe down",
             "observable": "sets the brass astrolabe down"},
            {"event_id": "t:1:speech", "type": "speech",
             "text": "The bearings drifted overnight."},
            {"event_id": "t:2:action", "type": "action", "attempt": "go below",
             "observable": "turns toward the companionway"}]}]}


def _first_only():
    return [{"source_entity_id": "character:7", "source_event_id": "t:0:action",
             "event": "Odalys sets the brass astrolabe down on the chart table.",
             "speech": False, "item_names": ["astrolabe"], "transforms": []}]


class _Ctx(dict):
    language = "en"

    def __init__(self):
        super().__init__()
        self.warnings = []

    def add_warning(self, text):
        self.warnings.append(text)


def test_each_version_of_a_draft_is_attributed_once(monkeypatch):
    """Every reader in the pass asks; each version of the draft -- the
    encoder's, the repaired one, a declared act's own words -- is worked out
    once. Before: the same event and sentence were weighed 11 times in this
    one pass."""
    repair._attribution.cache_clear()
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, q: {
        key: {"type": "noul", "noul": 0.02} for key in q})

    def repair_call(role, step_key, system, payload, **kw):
        job = payload["jobs"][0]
        return {"answers": [{"id": job["id"], "after": "e1", "events": [
            {"source_entity_id": "character:7", "source_event_id": act["event_id"],
             "event": act["act"], "speech": act["event_id"].endswith("speech"),
             "transforms": []} for act in job["declared"]]}]}

    monkeypatch.setattr(director, "_agent_json", repair_call)
    real, asked = repair.attribute, []

    def recording(events, units):
        asked.append((tuple(str((e or {}).get("event") or (e or {}).get("observable") or "")
                            for e in events or []),
                      tuple((u["id"], u["text"]) for u in units or ())))
        return real(events, units)

    monkeypatch.setattr(repair, "attribute", recording)
    units = repair.sentences(PROSE)
    events, _record = repair.check_and_repair(
        _Ctx(), "resolve", {}, units, _first_only(), ["poses"], [], {}, None, None,
        base_payload=_declaring())
    assert [e["source_event_id"] for e in events] == [
        "t:0:action", "t:1:speech", "t:2:action"]
    info = repair._attribution.cache_info()
    assert len(asked) > len(set(asked)), "the pass asks of one draft more than once"
    assert info.misses == len(set(asked)), "each version of the draft is worked out once"
    assert info.hits + info.misses == len(asked)


def test_every_reader_gets_its_own_answer():
    """Remembered, never shared: a reader that edits its answer edits no
    other reader's."""
    units = repair.sentences(PROSE)
    first = repair.attribute(_first_only(), units)
    first[0].append("s9")
    assert repair.attribute(_first_only(), units) == [["s1"]]
