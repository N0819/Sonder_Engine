"""The Dramaturge (`agents/dramaturge.py`), its proposals
(`story/room_proposals.py`) and the deliberation the Story Planner runs
over them (`agents/story_planner.deliberate`). Every model call is a
scripted stub.
"""
from __future__ import annotations

import json
import time

import pytest

from core.db import FRAME_SCOPED_WORLD_KEYS, wset
from llm import providers
from story import mandates as md
from story import room_conversation as room
from story import room_proposals as rp
from agents import dramaturge as dg
from agents import story_planner as sp

PLAYER = "The Stranger"


def _story(db, *, turns=3, narrations=True):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Dramaturge", "A port at dusk.", time.time()))
    wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone and rope.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates to the rafters.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}})
    for i in range(turns):
        tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                    (cid, i, "I walk the quay (beat %d)." % i, time.time()))
        if narrations:
            sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                        (tid, "narrator", "Narrator", 9))
            db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                  (sid, json.dumps({"prose": "The tide climbs the quay stones (beat %d)."
                                    % i, "secret": "the verger did it"}), time.time()))
    return cid


class Script:
    """Answers per role, in order; records every payload by role."""

    def __init__(self, **by_role):
        self.by_role = {k: list(v) for k, v in by_role.items()}
        self.payloads = {k: [] for k in by_role}
        self.systems = {k: [] for k in by_role}

    def __call__(self, role, system, user, **kw):
        payload = json.loads(user)
        self.payloads.setdefault(role, []).append(payload)
        self.systems.setdefault(role, []).append(system)
        steps = self.by_role.setdefault(role, [])
        if not steps:
            return json.dumps({"reply": "nothing more", "none_needed": True})
        step = steps.pop(0)
        if callable(step):
            step = step(payload)
        return json.dumps(step)


@pytest.fixture
def scripted(monkeypatch):
    def install(**by_role):
        script = Script(**by_role)
        monkeypatch.setattr(providers, "chat_complete", script)
        return script
    return install


def _dial(cid, value=2, beats=None):
    limits = {"surprise": value}
    if beats is not None:
        limits["beats_per_proposal"] = beats
    return md.grant_mandate(cid, None, text="Surprise me a little.",
                            capabilities=["plan_entity", "post_artifact",
                                          "schedule_event", "create_people"],
                            limits=limits)


# ---------------------------------------------------------------------------
# Role, stream, the one tool
# ---------------------------------------------------------------------------

def test_the_role_exists_and_the_stream_is_what_the_player_saw(temp_db):
    from llm.prompts import get_prompt
    assert "dramaturge" in providers.ROLES
    for lang in ("en", "ja"):
        assert len(get_prompt("dramaturge", lang)) > 500
        assert len(get_prompt("bible_fold", lang)) > 300
    assert rp.PROPOSALS_KEY in FRAME_SCOPED_WORLD_KEYS
    cid = _story(temp_db, turns=4)
    stream = dg.player_visible_stream(cid, None, beats=3)
    assert [b["beat"] for b in stream] == [1, 2, 3]
    assert stream[-1]["player"].startswith("I walk the quay")
    assert "tide climbs" in stream[-1]["narration"]
    # Only the prose the player read: nothing else of the narrator's record.
    assert "verger" not in json.dumps(stream)


def test_a_pass_reads_lore_and_nothing_else_then_files_typed_proposals(temp_db, scripted):
    cid = _story(temp_db)
    _dial(cid, 3)
    script = scripted(dramaturge=[
        {"calls": [{"tool": "search_lore", "args": {"query": "harbour guild"}},
                   {"tool": "inspect_rooms", "args": {}},
                   {"tool": "publish_package", "args": {"uid": "plot:x"}}]},
        {"proposals": [
            {"kind": "pressure", "title": "The tide bill", "wants_true": "The harbour guild calls in a debt.",
             "why_now": "The player has lingered three beats.", "must_not_contradict": "The quay is empty of guildsmen."},
            {"kind": "quiet", "title": "Nothing yet"},
            {"kind": "nonsense", "title": "x", "wants_true": "y"},
            {"kind": "arrival", "title": "No wants", "wants_true": ""}],
         "note": "Something stirs at the harbour.", "none_needed": False},
    ])
    out = dg.propose(cid, None, dial=3)
    payload = script.payloads["dramaturge"][0]
    assert payload["dial"] == 3 and "stream" in payload and payload["kinds"][0] == "pressure"
    from story.room_bible import render_block
    assert render_block(cid, None) == ""  # an empty bible adds no block
    assert "setups, unpaid" not in script.systems["dramaturge"][0]
    shown = script.payloads["dramaturge"][1]["transcript"]
    assert shown[0]["tool"] == "search_lore" and "error" not in shown[0]["result"]
    assert "reads lore and nothing else" in shown[1]["result"]["refused"]
    assert "reads lore and nothing else" in shown[2]["result"]["refused"]
    assert out["calls"] == 1 and out["note"] == "Something stirs at the harbour."
    assert [p["kind"] for p in out["proposals"]] == ["pressure", "quiet"]
    # Four offered, three read (the per-pass cap), one of those refused for
    # its kind; the fourth is never reached.
    assert len(out["refused"]) == 1
    assert len(out["proposals"]) + len(out["refused"]) == dg.DRAMATURGE_PROPOSALS_PER_PASS
    rows = rp.proposals(cid, None)
    assert rows[0]["status"] == "open" and rows[0]["dial"] == 3
    # The same kind and title while pending is the same proposal.
    again = rp.file_proposal(cid, None, kind="pressure", title="the tide bill",
                             wants_true="other words", why_now="x")
    assert again["uid"] == rows[0]["uid"]


def test_the_dial_and_the_bible_reach_the_dramaturge(temp_db, scripted):
    from story import room_bible as rb
    cid = _story(temp_db)
    rb.add_entry(cid, None, "voice", "The player asked for slow dread (beat 1).", ["turn:1"])
    script = scripted(dramaturge=[{"none_needed": True, "note": ""}])
    out = dg.propose(cid, None, dial=0)
    assert out["none_needed"] and out["proposals"] == []
    assert script.payloads["dramaturge"][0]["dial"] == 0
    assert "slow dread" in script.systems["dramaturge"][0]
    assert "holds to the target" in script.payloads["dramaturge"][0]["dial_scale"]


# ---------------------------------------------------------------------------
# The deliberation
# ---------------------------------------------------------------------------

def test_a_proposal_is_refused_with_the_contradiction_named(temp_db, scripted):
    cid = _story(temp_db)
    _dial(cid, 2)
    prop = rp.file_proposal(cid, None, kind="revelation", title="The dead verger",
                            wants_true="The verger returns alive.", why_now="now")
    script = scripted(story_planner=[
        {"verdicts": [{"proposal_uid": prop["uid"], "verdict": "refuse",
                       "reason": "The verger was buried at beat 40.",
                       "contradiction": "the player saw the burial"}],
         "reply": "The verger cannot return; the player saw him buried."},
    ])
    report = sp.deliberate(cid, None, [prop], dial=2, turn_idx=2)
    assert report["refused"] == [prop["uid"]] and report["rounds"] == 1
    row = rp.get_proposal(cid, None, prop["uid"])
    assert row["status"] == "refused"
    assert row["judgements"][-1]["contradiction"] == "the player saw the burial"
    task = script.payloads["story_planner"][0]["task"]
    assert task["kind"] == "deliberate" and task["proposals"][0]["uid"] == prop["uid"]
    assert script.payloads["story_planner"][0]["budget"]["regime"] == "task"
    assert room.messages(cid, None)[-1]["role"] == "planner"


def test_an_accepted_proposal_is_implemented_through_a_package(temp_db, scripted):
    from story.plot_packages import list_packages
    cid = _story(temp_db)
    _dial(cid, 2)
    prop = rp.file_proposal(cid, None, kind="arrival", title="A bill on the quay",
                            wants_true="A creditor's bill is nailed at the quay.", why_now="now")

    def last_uid(p):
        for e in reversed(p.get("transcript") or []):
            r = e.get("result") or {}
            if isinstance(r, dict) and r.get("uid"):
                return r["uid"]
    scripted(story_planner=[
        {"calls": [{"tool": "new_package", "args": {"title": "The bill", "premise": "p"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": last_uid(p), "operation": {"op": "post_artifact", "room": "quay",
                                              "description": "a creditor's bill"}}}]},
        lambda p: {"calls": [{"tool": "validate_package", "args": {"uid": last_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": last_uid(p), "expected_revision": 2}}]},
        lambda p: {"verdicts": [{"proposal_uid": prop["uid"], "verdict": "accept",
                                 "reason": "A bill is what a creditor does."}],
                   "reply": "A bill will be found at the quay."},
    ])
    report = sp.deliberate(cid, None, [prop], dial=2, turn_idx=2)
    assert report["implemented"] == [prop["uid"]] and report["published"]
    row = rp.get_proposal(cid, None, prop["uid"])
    assert row["status"] == "implemented" and row["package_uid"] == report["published"][0]
    assert list_packages(cid)[0]["status"] == "published"
    # The publish left a deterministic bible line, no call.
    from story import room_bible as rb
    assert any("published" in e["text"] for e in rb.entries(cid, None, "decided"))
    # The status row projects the proposal spoiler-safely: kind and title only.
    status = room.status(cid, None)
    assert all("creditor's bill is nailed" not in json.dumps(i) for i in status["in_motion"])


def test_a_revision_round_then_a_disagreement_is_returned_to_the_player(temp_db, scripted):
    cid = _story(temp_db)
    _dial(cid, 4)
    prop = rp.file_proposal(cid, None, kind="reversal", title="The harbour master turns",
                            wants_true="The harbour master betrays the guild.", why_now="now")
    script = scripted(
        story_planner=[
            {"verdicts": [{"proposal_uid": prop["uid"], "verdict": "revise",
                           "reason": "No harbour master exists; the post is empty."}],
             "reply": "There is no harbour master to turn."},
            {"verdicts": [{"proposal_uid": prop["uid"], "verdict": "revise",
                           "reason": "Still nobody holds the post."}],
             "reply": "Still nobody to turn."},
        ],
        dramaturge=[
            {"revision": {"wants_true": "A clerk of the guild turns instead.",
                          "why_now": "now"}, "note": "Then let it be the clerk."},
            {"revision": {"wants_true": "The clerk's brother turns."},
             "note": "The brother, then."},
        ])
    report = sp.deliberate(cid, None, [prop], dial=4, turn_idx=2)
    assert report["rounds"] == sp.DELIBERATION_ROUNDS
    assert report["returned"] == [prop["uid"]]
    row = rp.get_proposal(cid, None, prop["uid"])
    assert row["status"] == "returned" and row["revision"] == 2
    assert row["wants_true"] == "The clerk's brother turns."
    roles = [m["role"] for m in room.messages(cid, None)]
    assert roles[-1] == "room" and room.messages(cid, None)[-1]["text"] == sp.DISAGREEMENT_LINE
    assert "dramaturge" in roles
    assert script.payloads["dramaturge"][0]["task"] == "revise_or_withdraw"
    assert any("Settle the returned proposal" in q["text"]
               for q in room.status(cid, None)["questions"])


def test_a_withdrawn_revision_settles_the_proposal(temp_db, scripted):
    cid = _story(temp_db)
    _dial(cid, 2)
    prop = rp.file_proposal(cid, None, kind="pressure", title="Drought",
                            wants_true="The wells run dry.", why_now="now")
    scripted(story_planner=[{"verdicts": [{"proposal_uid": prop["uid"], "verdict": "revise",
                                           "reason": "It rained all week."}],
                             "reply": "It rained."}],
             dramaturge=[{"withdraw": "A drought after a week of rain is not this story.",
                          "note": "Withdrawn."}])
    report = sp.deliberate(cid, None, [prop], dial=2, turn_idx=2)
    assert report["withdrawn"] == [prop["uid"]] and report["returned"] == []
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "withdrawn"


# ---------------------------------------------------------------------------
# When it runs: the dial as the grant, the pacing budget, the player's ask
# ---------------------------------------------------------------------------

def test_the_dramaturge_runs_only_under_the_dial_and_at_its_pace(temp_db, scripted):
    from core import jobs
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    cid = _story(temp_db)
    tid = temp_db.q("SELECT id FROM turns WHERE chat_id=? AND idx=2", (cid,), one=True)["id"]

    def ctx(idx):
        return PipelineContext(
            chat=ChatData(id=cid, name="D", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=tid, chat_id=cid, idx=idx, player_input="",
                          created=time.time(), frame_id=None), cast=[], input="")
    assert md.surprise_dial(cid, None) is None
    assert sp.run_dramaturge_pass(cid, None) == {"skipped": "no dial"}
    assert sp.schedule_room_work(ctx(2)) is None
    _dial(cid, 1, beats=3)
    assert md.surprise_dial(cid, None) == 1 and md.beats_per_proposal(cid, None) == 3
    scripted(dramaturge=[{"none_needed": True, "note": "The story carries itself."}])
    job = sp.schedule_room_work(ctx(2))
    assert job is not None and job.key == sp.DRAMATURGE_JOB_KEY
    deadline = time.time() + 10.0
    while job.state in ("pending", "running") and time.time() < deadline:
        time.sleep(0.02)
    assert job.state == "done", (job.state, job.error)
    assert job.result["none_needed"] and job.result["dial"] == 1
    assert rp.last_pass_turn(cid, None) == 2
    assert room.messages(cid, None)[-1]["role"] == "dramaturge"
    # Two beats later is under the pacing budget: nothing is queued.
    assert sp.schedule_room_work(ctx(4)) is None
    # Three beats later it is due again.
    scripted(dramaturge=[{"none_needed": True}])
    job = sp.schedule_room_work(ctx(5))
    assert job is not None and job.key == sp.DRAMATURGE_JOB_KEY
    jobs.drain(timeout=2.0)


def test_the_planner_hands_the_player_ask_to_the_dramaturge_out_of_band(temp_db, scripted):
    from core import jobs
    cid = _story(temp_db)
    _dial(cid, 2)
    scripted(story_planner=[{"reply": "The Dramaturge is thinking about it.",
                             "to_dramaturge": "Something to unsettle the quay."}],
             dramaturge=[{"none_needed": True, "note": "I have looked; the quay is enough."}])
    env = sp.planner_reply(cid, None, "Give me a complication.")
    assert env["reply"].startswith("The Dramaturge is thinking")
    assert env["dramaturge"] is None
    jobs.drain(timeout=5.0)
    roles = [m["role"] for m in room.messages(cid, None)]
    assert roles[-1] == "dramaturge"


# ---------------------------------------------------------------------------
# The firewall
# ---------------------------------------------------------------------------

def test_neither_agent_reaches_a_mind(temp_db, scripted):
    from story.scene import recent_events_for_observer
    cid = _story(temp_db)
    _dial(cid, 4)
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                         ("Mara Quill", json.dumps({"name": "Mara Quill"}), time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (cid, char_id, "active", json.dumps({"mood": "calm"})))
    temp_db.qi("INSERT INTO memories(chat_id,char_id,turn_idx,kind,content) "
               "VALUES(?,?,?,?,?)", (cid, char_id, 1, "episodic", "The tide came in."))

    def snapshot():
        return {
            "chars": [dict(r) for r in temp_db.q(
                "SELECT char_id, status, state, sheet FROM chat_chars WHERE chat_id=?", (cid,))],
            "memories": [dict(r) for r in temp_db.q(
                "SELECT char_id, turn_idx, kind, content FROM memories WHERE chat_id=?", (cid,))],
            "known": temp_db.wget(cid, "known", {}),
            "view": recent_events_for_observer(cid, "Mara Quill", n=5, frame_id=None),
        }
    before = snapshot()
    secret = "Mara's brother is the smuggler and she must never know."
    scripted(dramaturge=[{"proposals": [{"kind": "revelation", "title": "A family matter",
                                         "wants_true": secret, "why_now": "now"}],
                          "note": "A family matter is in motion."}],
             story_planner=[{"verdicts": [], "reply": "Weighing it."}] * 3)
    report = sp.run_dramaturge_pass(cid, None)
    assert report["proposals"]
    assert snapshot() == before
    assert "smuggler" not in json.dumps(room.status(cid, None)).casefold()
    assert "smuggler" not in json.dumps(temp_db.wget(cid, "scene")).casefold()


def test_the_new_fixed_lines_are_in_both_catalogs():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    en = json.loads((root / "language_packs" / "en" / "ui.json").read_text("utf-8"))
    ja = json.loads((root / "language_packs" / "ja" / "ui.json").read_text("utf-8"))
    script = (root / "static" / "js" / "writers_room.js").read_text("utf-8")
    for line in (sp.SPENT_LINE, sp.HOUR_SPENT_LINE, sp.DISAGREEMENT_LINE):
        assert line in en and line in script
        assert ja.get(line) not in (None, line)
