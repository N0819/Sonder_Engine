"""The prose encoder's check and repair (agents/director_repair.py).

The encoder writes a beat in one call and one call can stop short, skip an
act or write a ledger wrong: on the owner's traffic (2026-09-24) 3 of about
16 resolve calls encoded 0-2 events of a 2,852-5,104 character account. The
pass checks the draft sentence by sentence, event by event and write by
write, and has ONE encoder call repair exactly what a confident check found,
with the whole draft -- the ledgers as completed so far -- in front of it.

Pinned here: sentences stay whole and lossless; each event is attributed to
its sentences by code, so the draft call is untouched; each check is
anchored on the thing it judges; only a confident yes builds a job; answers
bind to their job by id; recovered events land where Jev places them; and
the pass never costs the player the beat -- only their own Stop propagates.
"""

from __future__ import annotations

import pytest

import agents.director as director
from agents import director_repair as repair
from llm import decisions
from llm.providers import Aborted

from tests.test_director_orchestration import _action_interp, _fake_agent, _make_ctx, _steps


# ---- sentences ------------------------------------------------------------

def test_sentences_are_lossless_and_keep_a_quotation_whole():
    prose = ("The doors shut. He calls out: 'That's just her! It's fine.' "
             "Then 'em lads wave.\nThe rotor turns.")
    units = repair.sentences(prose)
    assert "".join(u["text"] for u in units) == prose
    texts = [u["text"].strip() for u in units]
    assert texts[0] == "The doors shut."
    # A quotation with stops inside is one sentence with its frame...
    assert texts[1] == "He calls out: 'That's just her! It's fine.'"
    # ...and a stray `'em` opens nothing, so the rest is not folded into it.
    assert texts[2] == "Then 'em lads wave."
    assert texts[3] == "The rotor turns."
    assert [u["id"] for u in units] == ["s1", "s2", "s3", "s4"]


PROSE3 = ("Mara climbs the stair into the lamp room. The wind rises against the glass. "
          "\"The lamp is cold,\" she calls down.")


def _draft():
    return [
        {"source_entity_id": "character:1",
         "event": "Mara climbs the stair into the lamp room.",
         "speech": False, "item_names": ["Mara"],
         "transforms": [{"item": "Mara", "patch": {"positions": {"Mara": "lamp_room"}}}]},
        {"source_entity_id": "character:1", "event": "The lamp is cold.",
         "speech": True, "item_names": ["Mara"], "transforms": []},
    ]


def test_code_attributes_each_event_to_the_sentences_it_comes_from():
    units = repair.sentences(PROSE3)
    assert repair.attribute(_draft(), units) == [["s1"], ["s3"]]
    assert repair.citations(_draft(), units) == {"s1": [0], "s2": [], "s3": [1]}
    # An event with no text of its own comes from nowhere.
    assert repair.attribute([{"event": ""}], units) == [[]]


def test_the_repair_call_reads_addresses_and_none_survive():
    units = repair.sentences("Mara climbs. She waves.")
    assert repair.numbered(units) == "[s1] Mara climbs. [s2] She waves."
    events = [{"event": "[s2] She waves.", "speech": False,
               "transforms": [{"item": "Mara", "patch": {"poses": {"Mara": {"detail": "[s2] waving"}}}}]}]
    clean = repair.strip_markers(events)
    assert clean[0]["event"] == "She waves."
    assert clean[0]["transforms"][0]["patch"]["poses"]["Mara"]["detail"] == "waving"


# ---- what is asked ------------------------------------------------------------

def test_each_check_is_anchored_on_what_it_judges():
    units = repair.sentences(PROSE3)
    questions, about = repair.battery(units, _draft(), ["positions", "poses"])
    # One per sentence; the sentence nothing comes from is compared with its
    # neighbours' events -- carried in the question, not named for lookup.
    assert about["ev:s2"] == {"kind": "event", "sentence": "s2"}
    ask = questions["ev:s2"]["instructions"]
    assert "The wind rises against the glass." in ask
    assert '"Mara climbs the stair into the lamp room."' in ask and '"The lamp is cold."' in ask
    # One per existing write; a missing-ledger question only where the event
    # writes nothing to that record -- whether a write exists is code's fact.
    assert {k for k in about if k.startswith("led:")} == {
        "led:e1:poses", "led:e2:positions", "led:e2:poses"}
    assert about["bad:e1:0:positions"] == {"kind": "fix", "event": "e1", "index": 0,
                                           "channel": "positions"}
    # What the record holds is the encoder card's own contract; the event
    # and its write ride in the question.
    wrong = questions["bad:e1:0:positions"]["instructions"]
    assert "positions names the room each body ends the beat in" in wrong
    assert '{"Mara": "lamp_room"}' in wrong and "Mara climbs the stair" in wrong
    assert "It writes nothing to the poses record" in questions["led:e1:poses"]["instructions"]
    assert all(q["type"] == "noul" for q in questions.values())
    state = repair.jev_state(units, _draft(), {})
    assert "e1 (cites s1)" in state and "e2 (cites s3)" in state


def test_only_a_confident_yes_builds_a_job():
    about = {"ev:s2": {"kind": "event", "sentence": "s2"},
             "led:e1:poses": {"kind": "ledger", "event": "e1", "channel": "poses"},
             "bad:e1:0:positions": {"kind": "fix", "event": "e1", "index": 0,
                                    "channel": "positions"},
             "bad:e2:0:poses": {"kind": "fix", "event": "e2", "index": 0, "channel": "poses"},
             "led:e1:positions": {"kind": "ledger", "event": "e1", "channel": "positions"}}
    answers = {"ev:s2": {"noul": 0.97}, "led:e1:poses": {"noul": 0.42},
               "bad:e1:0:positions": {"noul": 0.91}, "bad:e2:0:poses": {"noul": 0.62},
               "led:e1:positions": {"noul": 0.99}}
    confident, unsure = repair.findings(about, answers)
    assert {f["key"] for f in confident} == {"ev:s2", "bad:e1:0:positions", "led:e1:positions"}
    # Between 0.5 and a check's threshold is logged, never acted on.
    assert [f["key"] for f in unsure] == ["bad:e2:0:poses"]
    native = [{"ref": "e2", "index": 0, "channel": "sensory_events", "detail": "no room"}]
    draft = _draft()
    draft[1]["transforms"] = [{"item": "Mara", "patch": {"sensory_events": [{"kind": "sound"}]}}]
    jobs = repair.plan_jobs(native, confident, draft)
    # Certain first; a ledger job on a write already being fixed is one job,
    # whichever of the two findings scored higher.
    assert [(j["id"], j["kind"]) for j in jobs] == [("j1", "fix"), ("j2", "event"), ("j3", "fix")]
    assert jobs[0]["reason"] == "no room"
    assert jobs[2]["write"] == {"Mara": "lamp_room"}


def test_consecutive_missing_sentences_are_one_job():
    """Chat 154 turn 4398's second roll: one line of dialogue ran across six
    sentences and none was encoded -- a job each would invite it written
    six times."""
    found = [{"kind": "event", "sentence": s, "p": p}
             for s, p in (("s3", 0.9), ("s2", 0.85), ("s4", 0.95), ("s7", 0.99))]
    jobs = repair.plan_jobs([], found, _draft())
    assert [(j["id"], j["sentences"]) for j in jobs] == [
        ("j1", ["s7"]), ("j2", ["s2", "s3", "s4"])]
    assert jobs[1]["p"] == 0.95 and jobs[1]["sentence"] == "s2"
    units = repair.sentences("A. B happens. C happens. D happens. E. F. G happens.")
    view = repair._job_view(jobs[1], units)
    assert view == {"id": "j2", "kind": "event", "sentences": ["s2", "s3", "s4"],
                    "text": "B happens. C happens. D happens."}


def test_every_job_quotes_the_prose_that_decides_it():
    """A flagged write is shown with the sentences its event encodes: the
    prose decides the mistake, not the draft, which can repeat it (chat 154
    turn 4398: fixes shown by reference copied the draft's beach route)."""
    units = repair.sentences(PROSE3)
    sources = dict(zip(repair.refs_of(_draft()), repair.attribute(_draft(), units)))
    fix = {"id": "j1", "kind": "fix", "event": "e1", "index": 0, "channel": "positions",
           "write": {"Mara": "lamp_room"}}
    view = repair._job_view(fix, units, sources)
    assert view["sentences"] == ["s1"]
    assert view["text"] == "Mara climbs the stair into the lamp room."
    ledger = {"id": "j2", "kind": "ledger", "event": "e2", "channel": "obligations"}
    assert repair._job_view(ledger, units, sources)["text"] == \
        "\"The lamp is cold,\" she calls down."


def _flag(event="e1", index=0, channel="positions"):
    return {"kind": "fix", "event": event, "index": index, "channel": channel,
            "key": f"bad:{event}:{index}:{channel}", "p": 0.9}


def test_a_write_on_the_wrong_event_is_moved_by_code_and_still_checked():
    """Jev says the change happens at another event, and which: code moves
    the write, and its fix job follows it -- a move alone once put a ship's
    transit on the right event still carrying a wrong route."""
    explained = {"bad:e1:0:positions": {"elsewhere": 0.8, "to_event": "e2", "to_event_p": 0.9}}
    events, left, moved = repair.act_on_explanations(_draft(), [_flag()], explained)
    assert moved == [{"from": "e1", "to": "e2", "channel": "positions", "p": 0.9}]
    assert events[0]["transforms"][0]["patch"] == {}
    assert events[1]["transforms"] == [{"item": "Mara", "patch": {"positions": {"Mara": "lamp_room"}}}]
    assert [(f["event"], f["index"], f["channel"]) for f in left] == [("e2", 0, "positions")]
    assert "It was on e1" in left[0]["reason"]
    job = repair.plan_jobs([], left, events)[0]
    assert job["event"] == "e2" and job["write"] == {"Mara": "lamp_room"}


def test_a_move_needs_both_answers_sure():
    for answer in ({"elsewhere": 0.8, "to_event": "e2", "to_event_p": 0.6},   # where: unsure
                   {"elsewhere": 0.3, "to_event": "e2", "to_event_p": 0.95},  # whether: no
                   {"elsewhere": 0.9, "to_event": "e1", "to_event_p": 0.95}):  # its own event
        events, left, moved = repair.act_on_explanations(
            _draft(), [_flag()], {"bad:e1:0:positions": answer})
        assert moved == [] and left == [_flag()] and events == _draft()


def test_explaining_asks_whether_and_where_a_change_happens_instead(monkeypatch):
    seen = {}

    def jev(state, questions):
        seen.update(questions)
        return {"elsewhere:bad:e1:0:positions": {"type": "noul", "noul": 0.7},
                "at:bad:e1:0:positions": {"choice": "e2", "confidence": 0.9}}

    monkeypatch.setattr(decisions, "OVERRIDE", jev)

    class Ctx:
        language = "en"

    units = repair.sentences(PROSE3)
    out = repair.explain_wrong(Ctx(), units, _draft(), [_flag()], ["positions", "poses"], {}, {})
    assert out == {"bad:e1:0:positions": {"elsewhere": 0.7, "to_event": "e2", "to_event_p": 0.9}}
    assert seen["elsewhere:bad:e1:0:positions"]["type"] == "noul"
    assert "different event" in seen["elsewhere:bad:e1:0:positions"]["instructions"]
    assert list(seen["at:bad:e1:0:positions"]["criteria"]) == ["e2"]


def test_an_uncited_gap_between_two_missing_sentences_joins_them():
    found = [{"kind": "event", "sentence": "s2", "p": 0.7},
             {"kind": "event", "sentence": "s6", "p": 0.8}]
    cited = {"s1": [0], "s2": [], "s3": [], "s4": [], "s5": [], "s6": [], "s7": [1]}
    joined = repair.bridge(found, cited)
    jobs = repair.plan_jobs([], joined, _draft())
    assert [j["sentences"] for j in jobs] == [["s2", "s3", "s4", "s5", "s6"]]
    # A gap holding an encoded sentence is not bridged.
    cited["s4"] = [1]
    assert [j["sentences"] for j in repair.plan_jobs([], repair.bridge(found, cited), _draft())] == [
        ["s6"], ["s2"]]


def test_an_event_telling_several_sentences_is_attributed_to_each():
    units = repair.sentences("The ship groans. The sound deepens. Then the floor gives a "
                             "long, rolling lurch beneath them as the ship breaks free. "
                             "He does not move yet.")
    events = [{"event": "The ship groans, the sound deepening; the floor gives a long, "
                        "rolling lurch beneath them as the ship breaks free."},
              {"event": "The Doctor, who does not move, watches the rotor."}]
    assert repair.attribute(events, units) == [["s1", "s2", "s3"], ["s4"]]


# ---- applying ------------------------------------------------------------------

def test_answers_bind_by_job_id_not_position():
    draft = _draft()
    draft[1]["transforms"] = [{"item": "Mara", "patch": {"poses": {"Mara": {"posture": "lying"}}}}]
    jobs = [{"id": "j1", "kind": "fix", "event": "e1", "index": 0, "channel": "positions",
             "write": {"Mara": "lamp_room"}},
            {"id": "j2", "kind": "fix", "event": "e2", "index": 0, "channel": "poses",
             "write": {"Mara": {"posture": "lying"}}}]
    answers = [  # returned in the other order
        {"id": "j2", "transforms": [{"item": "Mara", "patch": {"poses": {"Mara": {"posture": "standing"}}}}]},
        {"id": "j1", "transforms": [{"item": "Mara", "patch": {"positions": {"Mara": "stair"}}}]},
        {"id": "j9", "transforms": []},
    ]
    events, report = repair.apply_answers(draft, [], jobs, answers, {})
    assert events[0]["transforms"] == [{"item": "Mara", "patch": {"positions": {"Mara": "stair"}}}]
    assert events[1]["transforms"] == [{"item": "Mara", "patch": {"poses": {"Mara": {"posture": "standing"}}}}]
    assert report["unknown"] == ["j9"] and report["unanswered"] == []


def test_a_wrong_write_is_replaced_removed_or_moved():
    draft = _draft()
    job = {"id": "j1", "kind": "fix", "event": "e1", "index": 0, "channel": "positions",
           "write": {"Mara": "lamp_room"}}
    removed, _ = repair.apply_answers(draft, [], [job], [{"id": "j1", "remove": True}], {})
    assert removed[0]["transforms"] == []
    moved, _ = repair.apply_answers(draft, [], [job], [{"id": "j1", "move_to": "e2"}], {})
    assert moved[0]["transforms"] == []
    assert moved[1]["transforms"] == [{"item": "Mara", "patch": {"positions": {"Mara": "lamp_room"}}}]
    kept, report = repair.apply_answers(draft, [], [job], [{"id": "j1", "none": "it is right"}], {})
    assert kept == draft and report["declined"] == {"j1": "it is right"}


def test_a_recovered_event_goes_where_jev_places_it(monkeypatch):
    units = repair.sentences(PROSE3)
    draft = _draft()
    groups = {"j1": {"sentence": "s2", "after": "",
                     "events": [{"event": "The wind rises against the glass."}]}}

    class Ctx:
        language = "en"

    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, q: {
        "place:j1": {"type": "choice", "choice": "after_e1", "confidence": 0.9}})
    slots, placed = repair.place(Ctx(), units, draft, groups)
    assert slots == {"j1": 0} and placed["j1"]["choice"] == "after_e1"
    events, _ = repair.apply_answers(
        draft, units, [{"id": "j1", "kind": "event", "sentence": "s2"}],
        [{"id": "j1", "events": [{"event": "The wind rises against the glass."}]}], slots)
    assert [e["event"] for e in events] == [
        "Mara climbs the stair into the lamp room.", "The wind rises against the glass.",
        "The lamp is cold."]
    # Unsure, Jev's placement gives way to the encoder's `after`.
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, q: {
        "place:j1": {"type": "choice", "choice": "before_e1", "confidence": 0.3}})
    groups["j1"]["after"] = "e2"
    slots, _ = repair.place(Ctx(), units, draft, groups)
    assert slots == {"j1": 1}


# ---- never the beat ---------------------------------------------------------------

class _Ctx(dict):
    language = "en"

    def __init__(self):
        super().__init__()
        self.warnings = []

    def add_warning(self, text):
        self.warnings.append(text)


def test_a_failing_check_keeps_the_draft_and_a_stop_still_stops(monkeypatch):
    units = repair.sentences("Mara climbs.")
    draft = _draft()[:1]

    def broken(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(repair, "_check_and_repair", broken)
    ctx = _Ctx()
    events, record = repair.check_and_repair(ctx, "resolve", {}, units, draft, ["positions"],
                                             [], {}, {}, {})
    assert events == draft and "boom" in record["failed"]
    assert any("draft kept as encoded" in w for w in ctx.warnings)

    def stopped(*a, **k):
        raise Aborted("user stop")

    monkeypatch.setattr(repair, "_check_and_repair", stopped)
    with pytest.raises(Aborted):
        repair.check_and_repair(_Ctx(), "resolve", {}, units, draft, ["positions"], [], {}, {}, {})


# ---- end to end -----------------------------------------------------------------

PROSE = ("Mara climbs the stair into the lamp room. "
         "\"The lamp is cold,\" she calls down.")


def _encoder_skips_the_line(payload):
    return {"events": [
        {"source_entity_id": "character:1", "source_event_id": "x",
         "event": "Mara climbs the stair into the lamp room.", "speech": False,
         "item_names": ["Mara"], "commitment": "asserted",
         "transforms": [{"item": "Mara", "patch": {"positions": {"Mara": "lamp_room"}}}]},
    ], "missing_tools": [], "missing_referents": [], "notes": []}


def _repair_answers(payload):
    job = payload["jobs"][0]
    return {"answers": [{"id": job["id"], "events": [
        {"source_entity_id": "character:1", "source_event_id": "x",
         "event": "The lamp is cold.", "speech": True, "targets": ["The Stranger"],
         "volume": "loud", "item_names": ["Mara"],
         "commitment": "asserted", "transforms": []}], "after": "e1"}], "notes": []}


def test_a_line_the_draft_dropped_is_recovered(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    temp_db.set_setting(repair.REPAIR_SETTING, "1")

    def jev(state, questions):
        out = {}
        for key in questions:
            if key == "ev:s2":
                out[key] = {"type": "noul", "noul": 0.96}
            elif key.startswith(("ev:", "led:", "bad:")):
                out[key] = {"type": "noul", "noul": 0.03}
            else:  # routing, for the beat and for the missing sentence
                out[key] = {"type": "noul", "noul": 0.95 if key in ("positions", "poses") else 0.02}
        return out

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": PROSE},
        "director_specialist": _encoder_skips_the_line,
        "director_repair": _repair_answers,
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert _steps(calls) == ["director_prose", "director_specialist", "director_repair"]
    # The draft is the encoder's ordinary call, untouched.
    assert calls[1]["payload"]["prose"] == PROSE
    repair_call = calls[2]
    assert "REPAIR." in repair_call["system"]
    assert repair_call["payload"]["prose"].startswith("[s1] Mara climbs")
    assert repair_call["payload"]["jobs"] == [{"id": "j1", "kind": "event", "sentences": ["s2"],
                                               "text": "\"The lamp is cold,\" she calls down."}]
    # The completed ledgers ride along: the whole draft, by reference, with
    # the sentences code attributed each event to.
    draft = repair_call["payload"]["draft"]
    assert draft[0]["ref"] == "e1" and draft[0]["sources"] == ["s1"]
    assert draft[0]["transforms"][0]["patch"]["positions"] == {"Mara": "lamp_room"}
    rows = out["ledgers"]
    assert [row["chrono_id"] for row in rows] == [1, 2]
    assert "speech" in rows[1]["categories"]
    record = out["orchestration"]["prose_contract"]["repair"]
    assert record["jobs"][0]["kind"] == "event" and record["applied"]["applied"] == ["j1"]


def test_off_by_default_nothing_changes(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, q: {
        key: {"type": "noul", "noul": 0.95 if key == "positions" else 0.02} for key in q})
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": PROSE},
        "director_specialist": _encoder_skips_the_line,
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist"]
    assert calls[1]["payload"]["prose"] == PROSE
    assert "repair" not in out["orchestration"]["prose_contract"]
