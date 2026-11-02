"""The Writers' Room's deliberation and reply record what happened, and
nothing a missing answer did not say (audit 2026-11-01,
agents_narration_planner F4, F10, F19, E1).

* `deliberate` marked EVERY proposal accepted without a package uid as
  implemented by the round's FIRST published package.
* The Dramaturge's `revise` read an unreadable answer as a withdrawal.
* The interactive reply ran with the rewind guard off while its comment said
  the guard covered that thread.
* The Room's per-step payload put the per-step `budget` and the rewritten
  `status` before the static task and the transcript, so a provider's prefix
  cache could hold almost none of it.
"""
from __future__ import annotations

import json
import time

import pytest

from core.db import wset
from llm import providers
from story import mandates as md
from story import room_conversation as room
from story import room_proposals as rp
from agents import dramaturge as dg
from agents import story_planner as sp

PLAYER = "The Stranger"


def _story(db, *, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Room", "A port at dusk.", time.time()))
    wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone and rope.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates to the rafters.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}})
    for i in range(turns):
        tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,?,?,?)", (cid, i, "I walk the quay.", time.time()))
        sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                    (tid, "narrator", "Narrator", 9))
        db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
              (sid, json.dumps({"prose": "The tide climbs (beat %d)." % i}),
               time.time()))
    return cid


class Script:
    def __init__(self, **by_role):
        self.by_role = {k: list(v) for k, v in by_role.items()}
        self.payloads = {k: [] for k in by_role}
        self.raw = {k: [] for k in by_role}

    def __call__(self, role, system, user, **kw):
        self.raw.setdefault(role, []).append(user)
        payload = json.loads(user)
        self.payloads.setdefault(role, []).append(payload)
        steps = self.by_role.setdefault(role, [])
        if not steps:
            return json.dumps({"reply": "nothing more", "none_needed": True})
        step = steps.pop(0)
        if callable(step):
            step = step(payload)
        return step if isinstance(step, str) else json.dumps(step)


@pytest.fixture
def scripted(monkeypatch):
    def install(**by_role):
        script = Script(**by_role)
        monkeypatch.setattr(providers, "chat_complete", script)
        return script
    return install


def _grant(cid):
    return md.grant_mandate(cid, None, text="Do what the story needs.",
                            capabilities=["post_artifact", "schedule_event",
                                          "plan_entity", "create_people"])


def _last_uid(payload):
    for entry in reversed(payload.get("transcript") or []):
        result = entry.get("result") or {}
        if isinstance(result, dict) and result.get("uid"):
            return result["uid"]


# ---------------------------------------------------------------------------
# F4 -- a package implements the proposal it was built for, and no other
# ---------------------------------------------------------------------------

def test_one_package_does_not_implement_two_accepted_proposals(temp_db, scripted):
    cid = _story(temp_db)
    _grant(cid)
    storm = rp.file_proposal(cid, None, kind="pressure", title="A storm",
                             wants_true="A storm closes the harbour.", why_now="now")
    rival = rp.file_proposal(cid, None, kind="arrival", title="A rival",
                             wants_true="A rival trader arrives.", why_now="now")
    scripted(story_planner=[
        {"calls": [{"tool": "new_package", "args": {"title": "The storm",
                                                     "premise": "p"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {
                "op": "schedule_event", "summary": "a storm closes the harbour",
                "due_in_turns": 1}}}]},
        lambda p: {"calls": [{"tool": "validate_package",
                              "args": {"uid": _last_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 2}}]},
        {"verdicts": [
            {"proposal_uid": storm["uid"], "verdict": "accept",
             "reason": "storms are this coast's", "package_uid": None},
            {"proposal_uid": rival["uid"], "verdict": "accept",
             "reason": "natural; needs a grant to plan a person",
             "package_uid": None}],
         "reply": "The storm is planted; a rival needs your word."},
    ])
    report = sp.deliberate(cid, None, [storm, rival], dial=2, turn_idx=2)
    assert len(report["published"]) == 1
    rival_row = rp.get_proposal(cid, None, rival["uid"])
    assert rival_row["status"] == "accepted", rival_row
    assert rival_row["package_uid"] == ""
    assert rival["uid"] not in report["implemented"]


def test_one_accepted_proposal_and_one_package_still_pair(temp_db, scripted):
    """The case the default was written for stays: one accepted, one built."""
    cid = _story(temp_db)
    _grant(cid)
    prop = rp.file_proposal(cid, None, kind="arrival", title="A bill on the quay",
                            wants_true="A creditor's bill is nailed at the quay.",
                            why_now="now")
    scripted(story_planner=[
        {"calls": [{"tool": "new_package", "args": {"title": "The bill",
                                                     "premise": "p"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {
                "op": "post_artifact", "room": "quay",
                "description": "a creditor's bill"}}}]},
        lambda p: {"calls": [{"tool": "validate_package",
                              "args": {"uid": _last_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 2}}]},
        {"verdicts": [{"proposal_uid": prop["uid"], "verdict": "accept",
                       "reason": "a bill is what a creditor does"}],
         "reply": "A bill will be found at the quay."},
    ])
    report = sp.deliberate(cid, None, [prop], dial=2, turn_idx=2)
    row = rp.get_proposal(cid, None, prop["uid"])
    assert row["status"] == "implemented"
    assert row["package_uid"] == report["published"][0]


# ---------------------------------------------------------------------------
# F10 -- an unreadable revision is no answer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    "not json at all",                       # cut off, or prose
    json.dumps({"note": "Hm."}),             # neither key
    json.dumps({"revision": {}, "withdraw": False}),   # both present, both empty
])
def test_an_unreadable_revision_leaves_the_proposal_standing(temp_db, scripted,
                                                             answer):
    cid = _story(temp_db)
    prop = rp.file_proposal(cid, None, kind="reversal", title="The tide lies",
                            wants_true="The tide tables were forged.",
                            why_now="now")
    row = rp.judge_proposal(cid, None, prop["uid"], verdict="revise",
                            reason="too sudden")
    assert row["status"] == "revised"
    scripted(dramaturge=[answer])
    out, note = dg.revise(cid, None, row, row["judgements"][-1], dial=2,
                          turn_idx=2)
    assert out["status"] == "revised", out
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "revised"
    assert note == ""


def test_an_explicit_withdrawal_still_withdraws(temp_db, scripted):
    cid = _story(temp_db)
    prop = rp.file_proposal(cid, None, kind="reversal", title="The tide lies",
                            wants_true="The tide tables were forged.",
                            why_now="now")
    row = rp.judge_proposal(cid, None, prop["uid"], verdict="revise",
                            reason="too sudden")
    scripted(dramaturge=[{"withdraw": "it cannot be made natural",
                          "note": "I withdraw it."}])
    out, note = dg.revise(cid, None, row, row["judgements"][-1], dial=2,
                          turn_idx=2)
    assert out["status"] == "withdrawn" and note == "I withdraw it."


# ---------------------------------------------------------------------------
# F19 -- the reply's writes are held to the story it started on
# ---------------------------------------------------------------------------

def test_a_reply_publishes_nothing_onto_a_story_rewound_under_it(temp_db, scripted):
    cid = _story(temp_db, turns=6)
    _grant(cid)

    def rewind_then_publish(payload):
        # The player rewinds two beats while the room is still working.
        temp_db.qi("DELETE FROM turns WHERE chat_id=? AND idx>=4", (cid,))
        return {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(payload), "expected_revision": 2}}]}

    scripted(story_planner=[
        {"calls": [{"tool": "new_package", "args": {"title": "Fog",
                                                     "premise": "p"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {
                "op": "schedule_event", "summary": "fog rolls in",
                "due_in_turns": 1}}}]},
        lambda p: {"calls": [{"tool": "validate_package",
                              "args": {"uid": _last_uid(p)}}]},
        rewind_then_publish,
        {"reply": "Done."},
    ])
    out = sp.planner_reply(cid, None, "Plant some weather.")
    from story.plot_packages import list_packages
    assert [p["status"] for p in list_packages(cid)] == ["draft"]
    assert out["reply"] == sp.REWOUND_LINE


# ---------------------------------------------------------------------------
# E1 -- what holds still goes first
# ---------------------------------------------------------------------------

def test_the_payload_puts_what_holds_still_before_what_moves(temp_db):
    cid = _story(temp_db)
    payload = sp._payload(cid, None, text="Plan the harbour.", task={"kind": "x"},
                          transcript=[{"tool": "inspect_clock", "args": {},
                                       "result": {}, "step": 1}],
                          step=2, calls_left=10, seconds_left=100.0, turn_idx=2)
    keys = list(payload)
    static = ["story", "capabilities", "limits", "task", "player_says"]
    volatile = ["clock", "mandates", "status", "frontier", "packages",
                "pending_proposals", "budget"]
    for key in static:
        assert keys.index(key) < keys.index("transcript"), keys
    for key in volatile:
        assert keys.index(key) > keys.index("transcript"), keys
    assert keys[-1] == "budget", keys
