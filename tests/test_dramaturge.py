"""The Dramaturge (`agents/dramaturge.py`), its proposals
(`story/room_proposals.py`) and the deliberation the Story Planner runs
over them (`agents/story_planner.deliberate`). Every model call is a
scripted stub.
"""
from __future__ import annotations

import json
import threading
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
# When it runs: on pacing alone, in the player's frame; the dial only tunes
# ---------------------------------------------------------------------------
#
# Owner, 2026-10-08: "It was never meant to be surprise only, it was meant to
# suggest story directions." Until then the pass ran only under a grant whose
# limits carried a numeric `surprise`, and none of the 68 grants in a copy of
# the owner's database did, so it had never run in any story. These tests
# restate the rule the deleted `test_the_dramaturge_runs_only_under_the_dial_
# and_at_its_pace` pinned: the pacing is the gate, the dial is a setting.

def _beat(db, cid, idx, *, frame_id=None, narrate=True):
    """The commit of beat ``idx`` in ``frame_id``: its turn row is the
    newest, as it is when the commit tail runs in play. A bubble's beat
    carries no narration (`agents/offscreen_beat.py`)."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    row = db.q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (cid, idx), one=True)
    if row:
        tid = row["id"]
    else:
        tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                    "VALUES(?,?,?,?,?)",
                    (cid, idx, "" if not narrate else "I wait (beat %d)." % idx,
                     time.time(), frame_id))
        if narrate:
            sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                        (tid, "narrator", "Narrator", 9))
            db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                  (sid, json.dumps({"prose": "Gulls over the quay (beat %d)." % idx}),
                   time.time()))
    return PipelineContext(
        chat=ChatData(id=cid, name="D", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=tid, chat_id=cid, idx=idx, player_input="",
                      created=time.time(), frame_id=frame_id), cast=[], input="")


def _wait(job, seconds=10.0):
    deadline = time.time() + seconds
    while job.state in ("pending", "running") and time.time() < deadline:
        time.sleep(0.02)
    return job


def _pass_job(cid):
    """The Dramaturge job a reply queued, running or done. `jobs.drain` is
    not a wait: it CANCELS first, and a cancelled pass writes nothing."""
    from core import jobs
    for job in jobs.active_jobs(cid) + list(reversed(jobs.history(cid))):
        if job.key == sp.DRAMATURGE_JOB_KEY:
            return job
    return None


def _bubble(db, cid):
    return db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) "
                 "VALUES(?,?,?,?,?)", (cid, "away", 1, "spatial", time.time()))


def test_the_dramaturge_suggests_on_its_pacing_with_no_grant_at_all(temp_db, scripted):
    """No grant, so no dial: the pass comes anyway, at `SURPRISE_DEFAULT`,
    once the frame has played `BEATS_PER_PROPOSAL` beats past its opening,
    and then every `BEATS_PER_PROPOSAL` beats after the last pass."""
    from core import jobs
    cid = _story(temp_db)
    assert md.active_mandates(cid, None) == []
    assert md.granted_surprise(cid, None) is None
    assert md.surprise_dial(cid, None) == md.SURPRISE_DEFAULT
    assert md.beats_per_proposal(cid, None) == md.BEATS_PER_PROPOSAL
    pace = md.BEATS_PER_PROPOSAL
    # One interval past the opening, not at it: the opening beat is the
    # Room's own plan landing.
    assert sp.schedule_room_work(_beat(temp_db, cid, 0)) is None
    assert sp.schedule_room_work(_beat(temp_db, cid, pace - 1)) is None
    script = scripted(dramaturge=[{"none_needed": True,
                                   "note": "The story carries itself."}])
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, pace)))
    assert job.key == sp.DRAMATURGE_JOB_KEY
    assert job.state == "done", (job.state, job.error)
    assert job.result["dial"] == md.SURPRISE_DEFAULT and job.result["none_needed"]
    assert script.payloads["dramaturge"][0]["dial"] == md.SURPRISE_DEFAULT
    assert script.payloads["dramaturge"][0]["pacing_beats"] == pace
    assert "player_asks" not in script.payloads["dramaturge"][0]
    assert rp.last_pass_turn(cid, None) == pace
    assert room.messages(cid, None)[-1]["role"] == "dramaturge"
    # Under one interval since the pass: nothing. One interval on: due.
    assert sp.schedule_room_work(_beat(temp_db, cid, 2 * pace - 1)) is None
    scripted(dramaturge=[{"none_needed": True}])
    job = sp.schedule_room_work(_beat(temp_db, cid, 2 * pace))
    assert job is not None and job.key == sp.DRAMATURGE_JOB_KEY
    jobs.drain(timeout=5.0)


def test_a_story_already_past_its_first_interval_is_asked_at_its_next_commit(
        temp_db, monkeypatch):
    """Every story written before the pass ran by default has played well
    past one interval and never had a pass: its next commit queues one, from
    that beat (review F9: this used to ask `pass_due` alone, so a scheduler
    reading the wrong pace or beat would still have passed)."""
    from core import jobs
    cid = _story(temp_db)
    for idx in range(3, 30):
        _beat(temp_db, cid, idx)
    assert rp.last_pass_turn(cid, None) is None
    seen = {}

    def captured(chat_id, frame_id, **kwargs):
        seen.update(kwargs, chat_id=chat_id, frame_id=frame_id)
        return {"skipped": "captured"}
    monkeypatch.setattr(sp, "run_dramaturge_pass", captured)
    job = sp.schedule_room_work(_beat(temp_db, cid, 30))
    assert job is not None and job.key == sp.DRAMATURGE_JOB_KEY
    assert _wait(job).state == "done", (job.state, job.error)
    assert seen["chat_id"] == cid and seen["base_turn"] == 30
    assert rp.pass_due(cid, None, 30, md.BEATS_PER_PROPOSAL) == (True, "")
    # And the opening alone is never due, at any pace.
    fresh = _story(temp_db, turns=1)
    assert rp.pass_due(fresh, None, 0, 1)[0] is False
    jobs.drain(timeout=5.0)


def test_a_grants_own_numbers_tune_the_dial_and_the_pace(temp_db):
    """A grant's `surprise` and `beats_per_proposal` are the player's word on
    how bold and how often -- low numbers included -- and a grant naming
    neither leaves the defaults standing. Neither one licenses anything."""
    cid = _story(temp_db)
    md.grant_mandate(cid, None, text="You may plan rooms.",
                     capabilities=["plan_rooms"])
    assert md.surprise_dial(cid, None) == md.SURPRISE_DEFAULT
    assert md.beats_per_proposal(cid, None) == md.BEATS_PER_PROPOSAL
    md.grant_mandate(cid, None, text="Hold to what I asked for.",
                     capabilities=["plan_rooms"], limits={"surprise": 0})
    assert md.granted_surprise(cid, None) == 0
    assert md.surprise_dial(cid, None) == 0
    md.grant_mandate(cid, None, text="Then go wild.",
                     capabilities=["plan_rooms"], limits={"surprise": 9})
    assert md.surprise_dial(cid, None) == md.SURPRISE_MAX
    # A pace named with no dial beside it is still the player's pace.
    md.grant_mandate(cid, None, text="Only every ten beats.",
                     capabilities=["plan_rooms"],
                     limits={"beats_per_proposal": 10})
    assert md.beats_per_proposal(cid, None) == 10
    md.grant_mandate(cid, None, text="No, every beat.",
                     capabilities=["plan_rooms"], limits={"beats_per_proposal": 1})
    assert md.beats_per_proposal(cid, None) == md.BEATS_PER_PROPOSAL_MIN


def test_a_pacing_of_zero_is_off_and_the_players_ask_still_runs(temp_db, scripted):
    """(review F8) Suggesting needs no grant, so a grant is the player's one
    way to stop it: a pace of 0 is OFF, and it wins over any other standing
    grant's pace. It used to be clamped to every beat -- a pass and a
    deliberation at every commit, six times the default, for the player who
    asked for none. Their own ask still reaches the Dramaturge, and a grant
    that only sets how the room works permits nothing."""
    from core import jobs
    cid = _story(temp_db)
    md.grant_mandate(cid, None, text="Suggest every four beats.",
                     capabilities=["plan_rooms"], limits={"beats_per_proposal": 4})
    md.grant_mandate(cid, None, text="No, suggest nothing I do not ask for.",
                     capabilities=["plan_rooms"], limits={"beats_per_proposal": 0})
    assert md.beats_per_proposal(cid, None) == 0
    assert md.BEATS_PER_PROPOSAL_OFF == 0
    assert rp.pass_due(cid, None, 30, 0)[0] is False
    for idx in range(3, 3 * md.BEATS_PER_PROPOSAL + 1):
        assert sp.schedule_room_work(_beat(temp_db, cid, idx)) is None, idx
    script = scripted(
        story_planner=[{"reply": "The Dramaturge is thinking about it.",
                        "to_dramaturge": "One complication, please."}],
        dramaturge=[{"none_needed": True, "note": "Asked, and answered."}])
    sp.planner_reply(cid, None, "Give me one complication.")
    job = _wait(_pass_job(cid))
    assert job.state == "done", (job.state, job.error)
    asked = script.payloads["dramaturge"][0]
    assert asked["player_asks"] == "One complication, please."
    assert asked["pacing_beats"] == 0
    # A grant that only sets how the room works is still a grant, and
    # permits nothing; one that permits nothing and sets nothing is refused.
    row = md.grant_mandate(cid, None, text="No suggestions unless I ask.",
                           capabilities=[], limits={"beats_per_proposal": 0})
    assert row["capabilities"] == [] and row["limits"] == {"beats_per_proposal": 0}
    assert md.coverage(cid, None, ["plan_entity"])["ok"] is False
    with pytest.raises(ValueError):
        md.grant_mandate(cid, None, text="Nothing at all.", capabilities=[])
    jobs.drain(timeout=5.0)


def test_a_live_bubbles_commit_never_queues_a_pass(temp_db, monkeypatch, scripted):
    """A live causality bubble's beats carry no player line and no
    narration, so a pass queued from its commit read an empty stream and
    spent the era's shared pacing row (review, 2026-10-08). Its commit
    queues none; and a pass asked from its panel -- a viewer can switch to
    its frame pill -- reads, paces and speaks in its era's frame."""
    import world.spatial_frames as spatial_frames
    cid = _story(temp_db)
    bubble = _bubble(temp_db, cid)
    for idx in range(3, 11):
        _beat(temp_db, cid, idx, frame_id=bubble, narrate=False)
    monkeypatch.setattr(spatial_frames, "is_bubble_frame", lambda c, f: True)
    assert sp.schedule_room_work(_beat(temp_db, cid, 10, frame_id=bubble)) is None
    assert rp.last_pass_turn(cid, bubble) is None      # the era's row, untouched
    script = scripted(dramaturge=[{"none_needed": True, "note": "Seen it."}])
    report = sp.run_dramaturge_pass(cid, bubble)
    assert report["none_needed"]
    stream = script.payloads["dramaturge"][0]["stream"]
    assert stream and all(b["narration"] for b in stream)   # the player's beats
    assert room.messages(cid, None)[-1]["text"] == "Seen it."
    assert room.messages(cid, bubble) == []
    assert rp.last_pass_turn(cid, None) == 2            # the player's own newest beat


def test_a_bubbles_beats_do_not_bring_the_pass_early(temp_db, monkeypatch):
    """Turn rows are numbered across the chat, and a live bubble inserts its
    beats into that numbering; the pacing counts the frame's OWN beats, the
    same count as the fill's back-off."""
    from core import jobs
    cid = _story(temp_db)
    bubble = _bubble(temp_db, cid)
    pace = md.BEATS_PER_PROPOSAL
    # The player's beats 0-2, then a bubble beat after each player beat.
    idx = 3
    player_beats = 3
    while player_beats < pace:
        _beat(temp_db, cid, idx, frame_id=bubble, narrate=False)
        _beat(temp_db, cid, idx + 1)
        idx, player_beats = idx + 2, player_beats + 1
    # Chat-wide, more than one interval has passed; the player has played
    # one beat short of it.
    assert idx - 1 >= pace
    due, why = rp.pass_due(cid, None, idx - 1, pace)
    assert not due and "%d of %d" % (pace - 1, pace) in why
    monkeypatch.setattr(sp, "run_dramaturge_pass",
                        lambda *a, **k: {"skipped": "captured"})
    assert sp.schedule_room_work(_beat(temp_db, cid, idx - 1)) is None
    # The player's next beat is the interval.
    _beat(temp_db, cid, idx, frame_id=bubble, narrate=False)
    job = sp.schedule_room_work(_beat(temp_db, cid, idx + 1))
    assert job is not None and job.key == sp.DRAMATURGE_JOB_KEY
    jobs.drain(timeout=5.0)


def test_the_story_hours_spend_still_stops_the_pass(temp_db, scripted):
    """Suggesting needs no grant, but a grant's hourly spend still stops it,
    at the commit tail and again inside the job."""
    from story.room_frontier import record_spend
    cid = _story(temp_db)
    md.grant_mandate(cid, None, text="Spend at most one call an hour.",
                     capabilities=["plan_rooms"], limits={"calls_per_hour": 1})
    record_spend(cid, None, turn_idx=2, calls=1, who="planner")
    script = scripted(dramaturge=[{"none_needed": True}])
    assert sp.schedule_room_work(_beat(temp_db, cid, md.BEATS_PER_PROPOSAL)) is None
    assert sp.run_dramaturge_pass(cid, None) == {"skipped": "spend_hour"}
    assert script.payloads["dramaturge"] == []
    assert rp.last_pass_turn(cid, None) is None


def test_a_failed_pass_has_still_had_its_turn(temp_db, scripted):
    """The pass is recorded before the Dramaturge is called: a provider that
    refused is asked again at the pacing, never at every commit -- which,
    now the pass needs no grant, would be every commit of every story."""
    cid = _story(temp_db)
    pace = md.BEATS_PER_PROPOSAL

    def refuse(_payload):
        raise RuntimeError("HTTP 402 in_flight_budget_exhausted")
    scripted(dramaturge=[refuse])
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, pace)))
    assert job.state == "failed" and "402" in job.error
    assert rp.last_pass_turn(cid, None) == pace
    assert sp.schedule_room_work(_beat(temp_db, cid, pace + 1)) is None


def _decides(monkeypatch, share=0.9, asked=None):
    """The decision model answering every question with ``share`` (or
    raising it, when it is an exception), each request kept in ``asked``."""
    from llm import decisions

    def answer(state, questions):
        if asked is not None:
            asked.append({"state": state, "questions": dict(questions)})
        if isinstance(share, BaseException):
            raise share
        return {key: {"type": "noul", "noul": share} for key in questions}
    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    return asked


def _no_pacing_pass(monkeypatch):
    """The Dramaturge's own pass is not what the test is about: never due."""
    monkeypatch.setattr(rp, "pass_due", lambda *a, **k: (False, "not under test"))


def _job(cid, key):
    """The newest job under ``key``, running or done."""
    from core import jobs
    for job in jobs.active_jobs(cid) + list(reversed(jobs.history(cid))):
        if job.key == key:
            return job
    return None


def test_suggesting_needs_no_grant_and_acting_on_it_still_does(temp_db, scripted,
                                                              monkeypatch):
    """With no grant at all the pass runs and files its suggestion; when the
    story comes near it the Planner judges it, and the package that would
    act on it is refused at validation and at publish: nothing reaches the
    world, the proposal stays accepted, the draft the task could never
    publish is retired when it ends, and the Planner's line and its
    question for the grant are what the player sees."""
    from story.plot_packages import list_packages
    cid = _story(temp_db)
    scene_before = temp_db.wget(cid, "scene")
    _decides(monkeypatch, 0.9)

    def last_uid(p):
        for e in reversed(p.get("transcript") or []):
            r = e.get("result") or {}
            if isinstance(r, dict) and r.get("uid"):
                return r["uid"]

    asked = "May the room post a creditor's bill on the quay?"
    script = scripted(
        dramaturge=[{"proposals": [{
            "kind": "pressure", "title": "A bill on the quay",
            "wants_true": "A creditor's bill is nailed at the quay.",
            "why_now": "The player has idled three beats."}],
            "note": "Something is gathering at the waterline."}],
        story_planner=[
            {"calls": [{"tool": "new_package", "args": {"title": "The bill",
                                                        "premise": "p"}}]},
            lambda p: {"calls": [{"tool": "draft_operation", "args": {
                "uid": last_uid(p), "operation": {
                    "op": "post_artifact", "room": "quay",
                    "description": "a creditor's bill"}}}]},
            lambda p: {"calls": [{"tool": "validate_package",
                                  "args": {"uid": last_uid(p)}}]},
            lambda p: {"calls": [{"tool": "publish_package", "args": {
                "uid": last_uid(p), "expected_revision": 2}}]},
            lambda p: {"verdicts": [{"proposal_uid": rp.proposals(cid, None)[0]["uid"],
                                     "verdict": "accept",
                                     "reason": "A creditor posts a bill."}],
                       "reply": "A bill would fit the quay; I need your leave to post it.",
                       "questions": [asked]},
        ])
    report = sp.run_dramaturge_pass(cid, None)
    assert report["dial"] == md.SURPRISE_DEFAULT
    assert report["deliberation"] is None and len(report["awaiting"]) == 1
    assert script.payloads.get("story_planner") == []
    # The story comes near it on the beat AFTER the one it was written from
    # (review R3-4: it is never asked about its own beats).
    _beat(temp_db, cid, 3)
    follow = sp.run_direction_follow_up(cid, None)
    assert list(follow["due"].values()) == ["touched"]
    deliberation = follow["deliberations"][0]
    assert deliberation["published"] == []
    shown = [e for p in script.payloads["story_planner"]
             for e in p.get("transcript") or []]
    refusals = json.dumps([e["result"] for e in shown
                           if e["tool"] in ("validate_package", "publish_package")])
    assert "no standing mandate permits post_artifact" in refusals
    assert [p["status"] for p in list_packages(cid)] == ["retired"]
    assert room.status(cid, None)["in_motion"] == []
    assert temp_db.wget(cid, "scene") == scene_before
    proposal = rp.proposals(cid, None)[0]
    assert proposal["status"] == "accepted" and not proposal["package_uid"]
    roles = [m["role"] for m in room.messages(cid, None)]
    assert roles[-2:] == ["dramaturge", "planner"]
    assert asked in [q["text"] for q in room.status(cid, None)["questions"]]


def _last_uid(payload):
    for entry in reversed(payload.get("transcript") or []):
        result = entry.get("result") or {}
        if isinstance(result, dict) and result.get("uid"):
            return result["uid"]


def _drafting(prop, title, *, publish=False):
    """A deliberation that accepts ``prop`` and drafts a bill for it: open,
    draft, validate, then (``publish``) publish, then the verdict."""
    steps = [
        {"calls": [{"tool": "new_package", "args": {"title": title, "premise": "p"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {"op": "post_artifact", "room": "quay",
                                               "description": "a bill"}}}]},
        lambda p: {"calls": [{"tool": "validate_package", "args": {"uid": _last_uid(p)}}]},
    ]
    if publish:
        steps.append(lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 2}}]})
    steps.append({"verdicts": [{"proposal_uid": prop["uid"], "verdict": "accept",
                                "reason": "A creditor posts bills."}],
                  "reply": "It fits.", "questions": ["May the room post a bill?"]})
    return steps


def test_a_task_retires_the_drafts_it_opened_that_no_grant_covers(temp_db, scripted):
    """(review F3) Drafting needs no grant; validating and publishing do,
    and only the host may retire a draft. With no grant, each deliberation
    that set out to carry an accepted proposal out left a draft that could
    never publish -- shown as in motion, counted against `PACKAGES_CAP`,
    past which the room can open nothing at all. The task that opened such
    a draft retires it when it ends, with the refusal as its note. A draft
    the grants cover is left for the work to go on, and the host's own
    drafts are never the room's to close."""
    from story.plot_packages import get_package, list_packages, new_package
    cid = _story(temp_db)
    hosts = new_package(cid, title="The host's own notes", premise="p")
    for i in range(3):
        prop = rp.file_proposal(cid, None, kind="pressure", title="Bill %d" % i,
                                wants_true="A bill %d is nailed up." % i, why_now="idle")
        scripted(story_planner=_drafting(prop, "The bill %d" % i))
        assert len(sp.deliberate(cid, None, [prop], turn_idx=2)["published"]) == 0
    by_title = {p["title"]: p["status"] for p in list_packages(cid)}
    assert by_title == {"The host's own notes": "draft", "The bill 0": "retired",
                        "The bill 1": "retired", "The bill 2": "retired"}
    assert [m["uid"] for m in room.status(cid, None)["in_motion"]] == [hosts["uid"]]
    retired = [p for p in list_packages(cid) if p["status"] == "retired"][0]
    note = get_package(cid, retired["uid"])["provenance"]["history"][-1]["note"]
    assert "no standing mandate permits post_artifact" in note
    # Granted, the same work is the room's to finish: its draft stands.
    md.grant_mandate(cid, None, text="You may post bills.", capabilities=["post_artifact"])
    prop = rp.file_proposal(cid, None, kind="pressure", title="Bill 3",
                            wants_true="A bill 3 is nailed up.", why_now="idle")
    scripted(story_planner=_drafting(prop, "The bill 3"))
    sp.deliberate(cid, None, [prop], turn_idx=2)
    assert {p["title"]: p["status"] for p in list_packages(cid)}["The bill 3"] == "draft"


def test_a_proposal_a_cut_short_deliberation_left_waiting_is_judged_at_its_bound(
        temp_db, scripted, monkeypatch):
    """Measured on the 2026-10-08 Brackwater pass: its second round could not
    be asked, so both proposals stayed `open`, and only a pass's own were
    ever handed on -- they would have stood on the status row as in motion
    for good. A deliberation now TAKES what it judges (`taken_turn`): one it
    leaves pending is not taken again at the next commit, whatever the beat
    looks like -- a dead provider would be asked at every commit -- and is
    judged once it has waited its bound again, so it is never dropped."""
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    _decides(monkeypatch, 0.9)
    left = rp.file_proposal(cid, None, kind="arrival", title="A clerk arrives",
                            wants_true="A guild clerk comes down to the quay.",
                            why_now="now", turn_idx=2)

    def refuse(_payload):
        raise RuntimeError("HTTP 402 in_flight_budget_exhausted")
    script = scripted(story_planner=[
        refuse,
        {"verdicts": [{"proposal_uid": left["uid"], "verdict": "refuse",
                       "reason": "The guild keeps no clerk here.",
                       "contradiction": "no guild office"}],
         "reply": "No clerk; the guild has no office here."}])
    failed = _wait(sp.schedule_room_work(_beat(temp_db, cid, 3)))
    assert failed.key == sp.DIRECTION_JOB_KEY and failed.state == "failed"
    held = rp.get_proposal(cid, None, left["uid"])
    assert held["status"] == "open" and held["taken_turn"] == 3 and not held["due"]
    bound = rp.direction_wait_beats(md.BEATS_PER_PROPOSAL)
    for idx in range(4, 3 + bound):
        assert sp.schedule_room_work(_beat(temp_db, cid, idx)) is None, idx
    assert len(script.payloads["story_planner"]) == 1
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, 3 + bound)))
    assert job.state == "done", (job.state, job.error)
    assert job.result["due"] == {left["uid"]: "waited"}
    assert script.payloads["story_planner"][1]["task"]["proposals"][0]["uid"] == left["uid"]
    assert rp.get_proposal(cid, None, left["uid"])["status"] == "refused"
    assert rp.pending_proposals(cid, None) == []


def test_a_pass_that_finds_nothing_answers_no_question(temp_db, scripted):
    """The status row's questions are what the room is waiting on; a pass
    that found nothing needed wrote the row bare and emptied them."""
    cid = _story(temp_db)
    # A dial the pass no longer needs, so the gate it had let it run too:
    # under that gate this is where the questions went.
    _dial(cid, 2)
    sp.write_status(cid, None, line="A courier is expected.",
                    questions=["May the room plan the harbour master?"], turn_idx=2)
    scripted(dramaturge=[{"none_needed": True, "note": "Nothing yet."}])
    assert sp.run_dramaturge_pass(cid, None)["none_needed"]
    status = room.status(cid, None)
    assert [q["text"] for q in status["questions"]] == [
        "May the room plan the harbour master?"]


def test_a_pass_that_finds_nothing_keeps_the_line_only_while_something_is_in_motion(
        temp_db, scripted):
    """The line says what the room has in motion. Kept whole by a pass that
    found nothing, a deliberation's line outlived the package it described
    and was read back as the next pass's `status_line` (review F5,
    2026-10-08); it stands while something is in motion and gives way when
    nothing is."""
    from story.plot_packages import new_package
    cid = _story(temp_db)
    sp.write_status(cid, None, line="Building the bill on the quay.", turn_idx=2)
    assert room.status(cid, None)["in_motion"] == []
    script = scripted(dramaturge=[{"none_needed": True, "note": "Nothing yet."},
                                  {"none_needed": True, "note": "Still nothing."}])
    sp.run_dramaturge_pass(cid, None)
    assert room.status(cid, None)["line"] == sp.NO_STATUS_LINE
    # Something in motion: the line that says so stands, and is what the
    # next pass reads.
    new_package(cid, title="The ledger", premise="p")
    sp.write_status(cid, None, line="A ledger is being drawn up.", turn_idx=2)
    sp.run_dramaturge_pass(cid, None)
    assert room.status(cid, None)["line"] == "A ledger is being drawn up."
    assert script.payloads["dramaturge"][1]["status_line"] == "A ledger is being drawn up."


def test_a_background_task_answers_no_question(temp_db, scripted):
    """A deliberation is a task, and nobody spoke to it: the questions the
    room is waiting on stand beside what it asks. A grant scoped to a
    standing question therefore outlives the task."""
    cid = _story(temp_db)
    sp.write_status(cid, None, questions=["May the room plan the harbour master?"],
                    turn_idx=2)
    question = room.status(cid, None)["questions"][0]
    md.grant_mandate(cid, None, text="Yes, plan him.", capabilities=["plan_entity"],
                     request=question["uid"])
    prop = rp.file_proposal(cid, None, kind="arrival", title="A clerk arrives",
                            wants_true="A guild clerk comes down to the quay.",
                            why_now="now")
    scripted(story_planner=[
        {"verdicts": [{"proposal_uid": prop["uid"], "verdict": "accept",
                       "reason": "The guild sends clerks."}],
         "reply": "A clerk would come.",
         "questions": ["May the room send the clerk?"]}])
    sp.deliberate(cid, None, [prop], turn_idx=2)
    assert [q["text"] for q in room.status(cid, None)["questions"]] == [
        "May the room plan the harbour master?", "May the room send the clerk?"]
    assert [m["text"] for m in md.active_mandates(cid, None)] == ["Yes, plan him."]


def _asked(cid, frame_id=None):
    return [(q.get("source"), q["text"]) for q in room.status(cid, frame_id)["questions"]]


def _texts(cid, frame_id=None):
    return [q["text"] for q in room.status(cid, frame_id)["questions"]]


def test_a_task_restates_only_its_own_questions(temp_db, scripted, monkeypatch):
    """WHO ASKED DECIDES WHO MAY TAKE IT OFF (review F4 and D, 2026-10-08). A
    background task's list replaces only what THAT task asked before -- a
    fill its last fill's, a deliberation its own over the same proposals --
    and keeps what the player was asked in a reply, the engine's own asks
    and every other task's; a reply restates the row. Until then a task
    replaced the whole row (and a grant scoped to the player's question
    lapsed with it), then for a day only added (and six filled the row),
    then replaced "the last task's" -- so the second deliberation took the
    first one's grant ask off, and the next fill took both."""
    from world.planning_needs import file_planning_need
    cid = _story(temp_db)
    scripted(story_planner=[{"reply": "I can plan him if you like.",
                             "questions": ["May the room plan the harbour master?"]}])
    sp.run_planner(cid, None, text="Who runs this harbour?")
    file_planning_need(cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
    monkeypatch.setattr(sp, "run_dramaturge_pass", lambda *a, **k: {"skipped": "x"})
    sp.schedule_room_work(_beat(temp_db, cid, 3))          # no fill grant: it asks
    for title, asked in (("A clerk arrives", "May the room send the clerk?"),
                         ("A bell rings", "May the room ring the bell?")):
        prop = rp.file_proposal(cid, None, kind="arrival", title=title,
                                wants_true="%s at the quay." % title, why_now="now")
        scripted(story_planner=[{"verdicts": [{"proposal_uid": prop["uid"],
                                               "verdict": "accept", "reason": "fits"}],
                                 "reply": "It fits.", "questions": [asked]}])
        sp.deliberate(cid, None, [prop], turn_idx=3)
    assert _asked(cid) == [("engine", sp.WAITING_LINE),
                           ("reply", "May the room plan the harbour master?"),
                           ("task", "May the room send the clerk?"),
                           ("task", "May the room ring the bell?")]
    # A fill is one task however often it runs: the next fill's list
    # replaces the last fill's, and nothing any other task asked.
    for asked in ("Where is the letter kept?", "Who sealed the letter?"):
        scripted(story_planner=[{"reply": "", "questions": [asked]}])
        sp._run_task(cid, None, {"kind": "fill", "needs": []}, base_turn=3)
    assert _asked(cid) == [("engine", sp.WAITING_LINE),
                           ("reply", "May the room plan the harbour master?"),
                           ("task", "May the room send the clerk?"),
                           ("task", "May the room ring the bell?"),
                           ("task", "Who sealed the letter?")]
    # A reply restates the row: what it does not restate was answered.
    scripted(story_planner=[{"reply": "Then I will wait on the bell.",
                             "questions": ["May the room ring the bell?",
                                           sp.WAITING_LINE]}])
    sp.run_planner(cid, None, text="Forget the harbour master.")
    assert _asked(cid) == [("engine", sp.WAITING_LINE),
                           ("reply", "May the room ring the bell?")]
    # A reply that says nothing about the questions has answered none.
    scripted(story_planner=[{"reply": "The tide is turning."}])
    sp.run_planner(cid, None, text="What is the tide doing?")
    assert _asked(cid) == [("engine", sp.WAITING_LINE),
                           ("reply", "May the room ring the bell?")]


def test_the_engines_own_asks_go_first_so_a_full_row_cannot_cut_them(
        temp_db, scripted, monkeypatch):
    """The row keeps `STATUS_QUESTIONS_CAP` questions. The fill's waiting
    line and a returned proposal's question are the engine's, written ahead
    of every model question; appended after a full row, the cap cut them on
    every commit (review F4). The waiting line is withdrawn once nothing is
    waiting on a grant."""
    from world.planning_needs import file_planning_need
    cid = _story(temp_db)
    full = ["May the room do thing %d?" % i for i in range(sp.STATUS_QUESTIONS_CAP)]
    scripted(story_planner=[{"reply": "Six things to ask you.", "questions": full}])
    sp.run_planner(cid, None, text="What do you need from me?")
    assert len(_asked(cid)) == sp.STATUS_QUESTIONS_CAP
    file_planning_need(cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
    monkeypatch.setattr(sp, "run_dramaturge_pass", lambda *a, **k: {"skipped": "x"})
    sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert _texts(cid)[0] == sp.WAITING_LINE
    prop = rp.file_proposal(cid, None, kind="reversal", title="The guild turns",
                            wants_true="The guild calls in its debt.", why_now="now")
    scripted(story_planner=[{"reply": "Thinking."}, {"reply": "Still thinking."}])
    assert sp.deliberate(cid, None, [prop], turn_idx=3)["returned"] == [prop["uid"]]
    settle = "Settle the returned proposal: The guild turns"
    assert _texts(cid)[:2] == [sp.WAITING_LINE, settle]
    asked = _asked(cid)
    assert asked[:2] == [("engine", sp.WAITING_LINE), ("engine", settle)]
    assert len(asked) == sp.STATUS_QUESTIONS_CAP
    # The need answered by other means, nothing is waiting: withdrawn.
    monkeypatch.setattr(sp, "_fill_wanted", lambda report: False)
    sp.schedule_room_work(_beat(temp_db, cid, 4))
    assert sp.WAITING_LINE not in _texts(cid)
    assert _asked(cid)[0] == ("engine", settle)


def test_a_quiet_proposal_is_never_in_motion(temp_db):
    """`quiet` is the record that a pass found nothing needed; the
    deliberation never judges one, so it must not wait on the Planner, show
    on the status row as something in motion, or outlive the cap."""
    cid = _story(temp_db)
    quiet = rp.file_proposal(cid, None, kind="quiet", title="Nothing yet",
                             wants_true="", why_now="")
    assert quiet["status"] == "open" and not rp.awaits_planner(quiet)
    assert rp.pending_proposals(cid, None) == []
    status = sp.write_status(cid, None, turn_idx=2)
    assert status["in_motion"] == []
    for i in range(rp.PROPOSALS_CAP + 2):
        rp.file_proposal(cid, None, kind="quiet", title="Still nothing %d" % i,
                         wants_true="", why_now="")
    assert len(rp.proposals(cid, None)) == rp.PROPOSALS_CAP


def test_the_planner_hands_the_player_ask_to_the_dramaturge_out_of_band(temp_db, scripted):
    """With no grant at all: asking for direction needs none."""
    from core import jobs
    cid = _story(temp_db)
    assert md.active_mandates(cid, None) == []
    script = scripted(story_planner=[{"reply": "The Dramaturge is thinking about it.",
                                      "to_dramaturge": "Something to unsettle the quay."}],
                      dramaturge=[{"none_needed": True,
                                   "note": "I have looked; the quay is enough."}])
    env = sp.planner_reply(cid, None, "Give me a complication.")
    assert env["reply"].startswith("The Dramaturge is thinking")
    assert env["dramaturge"] is None
    job = _wait(_pass_job(cid))
    assert job.state == "done", (job.state, job.error)
    jobs.drain(timeout=5.0)
    roles = [m["role"] for m in room.messages(cid, None)]
    assert roles[-1] == "dramaturge"
    asked = script.payloads["dramaturge"][0]
    assert asked["player_asks"] == "Something to unsettle the quay."
    assert asked["dial"] == md.SURPRISE_DEFAULT


# ---------------------------------------------------------------------------
# A pass in flight: an ask beside it, a reroll under it (review, 2026-10-08)
# ---------------------------------------------------------------------------

def _blocked(note, proposal=None):
    """A Dramaturge answer that waits to be released: the pass is in flight
    while the test acts beside it."""
    started, release = threading.Event(), threading.Event()

    def answer(payload):
        started.set()
        release.wait(5)
        out = {"note": note, "none_needed": proposal is None}
        if proposal is not None:
            out["proposals"] = [dict(proposal, why_now=payload["stream"][-1]["narration"])]
        return out
    return answer, started, release


def test_an_ask_made_while_a_pass_runs_is_answered_when_it_finishes(temp_db, scripted):
    """(review F1) The pacing pass and the player's ask share
    `DRAMATURGE_JOB_KEY`, and `core.jobs.submit` joins a job in flight: an
    ask made while a pacing pass ran -- minutes, with its deliberation --
    was never read, and the pacing pass's note looked like the answer. Kept
    on the room's row, it is answered by one more pass when the running one
    is done."""
    from core import jobs
    cid = _story(temp_db)
    slow, started, release = _blocked("The pacing pass.")
    script = scripted(
        dramaturge=[slow, {"none_needed": True, "note": "The asked pass."}],
        story_planner=[{"reply": "The Dramaturge is thinking about it.",
                        "to_dramaturge": "A complication at the quay, please."}])
    job = sp.schedule_room_work(_beat(temp_db, cid, md.BEATS_PER_PROPOSAL))
    assert job is not None and job.key == sp.DRAMATURGE_JOB_KEY
    assert started.wait(5)
    env = sp.planner_reply(cid, None, "Give me a complication.")
    assert env["reply"].startswith("The Dramaturge is thinking")
    release.set()
    assert _wait(job).state == "done", (job.state, job.error)
    asks = [p.get("player_asks") for p in script.payloads["dramaturge"]]
    assert asks == [None, "A complication at the quay, please."]
    notes = [m["text"] for m in room.messages(cid, None) if m["role"] == "dramaturge"]
    assert notes == ["The pacing pass.", "The asked pass."]
    assert rp.waiting_briefs(cid, None) == []
    jobs.drain(timeout=5.0)


def test_a_reroll_cancels_the_pass_in_flight_and_it_files_nothing(temp_db, scripted):
    """(review F2) A same-beat reroll restores that beat's checkpoint and
    leaves the turn index where it was, so the rewind guard cannot see it: a
    pass still running filed the DISCARDED beat's direction into the
    rerolled timeline, and a deliberation could build on it. The restore
    cancels the pass, and a cancelled pass writes nothing. THE PACING IS
    RE-ARMED (an owner question): the pass's record rolls back, and the
    rerolled beat is asked again, as itself."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    for idx in range(3, pace):
        _beat(temp_db, cid, idx)
    ensure_checkpoint(cid, pace)              # the world before beat `pace`
    slow, started, release = _blocked("Read off the discarded beat.", {
        "kind": "pressure", "title": "The coat's pockets",
        "wants_true": "The coat holds a second receipt."})
    script = scripted(dramaturge=[slow, {"none_needed": True,
                                         "note": "Read off the rerolled beat."}])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert started.wait(5)
    restore_checkpoint(cid, pace)             # the player rerolls the beat
    release.set()
    assert _wait(job).state == "cancelled", (job.state, job.error)
    assert rp.proposals(cid, None) == []
    assert script.payloads.get("story_planner", []) == []
    assert "Read off the discarded beat." not in [m["text"] for m in room.messages(cid, None)]
    assert rp.last_pass_turn(cid, None) is None
    rerolled = _wait(sp.schedule_room_work(_beat(temp_db, cid, pace)))
    assert rerolled is not job and rerolled.state == "done"
    assert room.messages(cid, None)[-1]["text"] == "Read off the rerolled beat."
    jobs.drain(timeout=5.0)


def test_a_reroll_does_not_unsay_the_ask_the_cancelled_pass_was_to_answer(
        temp_db, scripted):
    """The ask is the conversation's, not the beat's -- the thread it was
    made in is not in the checkpoint either -- so the restore that cancels
    the pass it joined leaves it waiting, and the rerolled beat's pass
    answers it."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    for idx in range(3, pace):
        _beat(temp_db, cid, idx)
    ensure_checkpoint(cid, pace)
    slow, started, release = _blocked("Read off the discarded beat.")
    script = scripted(
        dramaturge=[slow, {"none_needed": True, "note": "Answered after the reroll."}],
        story_planner=[{"reply": "The Dramaturge is thinking about it.",
                        "to_dramaturge": "Something to unsettle the quay."}])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert started.wait(5)
    sp.planner_reply(cid, None, "Give me a complication.")
    restore_checkpoint(cid, pace)
    release.set()
    assert _wait(job).state == "cancelled", (job.state, job.error)
    rerolled = _wait(sp.schedule_room_work(_beat(temp_db, cid, pace)))
    assert rerolled.state == "done", (rerolled.state, rerolled.error)
    assert script.payloads["dramaturge"][-1].get("player_asks") == \
        "Something to unsettle the quay."
    assert room.messages(cid, None)[-1]["text"] == "Answered after the reroll."
    assert rp.waiting_briefs(cid, None) == []
    jobs.drain(timeout=5.0)


def test_a_restore_leaves_the_waiting_asks_as_they_stand(temp_db):
    """Both directions of "the conversation is not in the checkpoint": an ask
    made after the snapshot survives the restore, and an ask a pass answered
    after the snapshot does not come back from it to be answered twice."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    rp.ask_brief(cid, None, "An ask the next pass answered.", turn_idx=2)
    ensure_checkpoint(cid, 2)                       # the snapshot holds it
    assert rp.take_briefs(cid, None) == ["An ask the next pass answered."]
    rp.ask_brief(cid, None, "An ask made after the snapshot.", turn_idx=2)
    restore_checkpoint(cid, 2)
    assert [b["text"] for b in rp.waiting_briefs(cid, None)] == [
        "An ask made after the snapshot."]


def test_a_cancelled_pass_hands_back_the_ask_it_took(temp_db, scripted):
    """A pass takes the asks waiting at its start; cancelled before it
    answered them, it hands them back -- its one write -- and the next
    pass answers them."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    ensure_checkpoint(cid, 2)
    slow, started, release = _blocked("Never posted.")
    script = scripted(
        dramaturge=[slow, {"none_needed": True, "note": "Answered at last."}],
        story_planner=[{"reply": "The Dramaturge is thinking about it.",
                        "to_dramaturge": "A stranger on the quay."}])
    sp.planner_reply(cid, None, "Who else is here?")
    assert started.wait(5)
    assert script.payloads["dramaturge"][0]["player_asks"] == "A stranger on the quay."
    assert rp.waiting_briefs(cid, None) == []        # taken by the pass
    restore_checkpoint(cid, 2)
    release.set()
    assert _wait(_pass_job(cid)).state == "cancelled"
    assert [b["text"] for b in rp.waiting_briefs(cid, None)] == ["A stranger on the quay."]
    assert "Never posted." not in [m["text"] for m in room.messages(cid, None)]
    report = sp.run_dramaturge_pass(cid, None)        # the next pass
    assert report["asked"] == "A stranger on the quay."
    assert script.payloads["dramaturge"][-1]["player_asks"] == "A stranger on the quay."
    assert room.messages(cid, None)[-1]["text"] == "Answered at last."
    assert rp.waiting_briefs(cid, None) == []
    jobs.drain(timeout=5.0)


def test_a_reroll_cancels_the_fill_in_flight_and_it_writes_nothing(
        temp_db, scripted, monkeypatch):
    """The fill reads the frontier the beat left and answers it through a
    package: the same class as the pass, cancelled by the same restore,
    and writing nothing once it is -- no package, no line, no answer for
    the back-off."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from story.plot_packages import list_packages
    from world.planning_needs import file_planning_need
    cid = _story(temp_db)
    file_planning_need(cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
    md.grant_mandate(cid, None, text="You may answer needs and close them",
                     capabilities=["identity_fills", "close_need"],
                     limits={"fills_per_hour": 4})
    ensure_checkpoint(cid, 3)
    started, release = threading.Event(), threading.Event()

    def slow(_payload):
        started.set()
        release.wait(5)
        return {"calls": [{"tool": "new_package",
                           "args": {"title": "The letter", "premise": "p"}}]}
    script = scripted(story_planner=[slow, {"reply": "A letter waits at the quay."}])
    monkeypatch.setattr(sp, "run_dramaturge_pass", lambda *a, **k: {"skipped": "x"})
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job is not None and job.key == sp.FILL_JOB_KEY
    assert started.wait(5)
    restore_checkpoint(cid, 3)
    release.set()
    assert _wait(job).state == "cancelled", (job.state, job.error)
    assert list_packages(cid) == []
    assert len(script.payloads["story_planner"]) == 1
    assert [m for m in room.messages(cid, None) if m["role"] == "planner"] == []
    jobs.drain(timeout=5.0)


# ---------------------------------------------------------------------------
# The lazy direction follow-up (owner, 2026-10-08: "save heavy plans for when
# the actors near them")
# ---------------------------------------------------------------------------

def _suggestion(cid, title="A bill on the quay", turn_idx=2):
    return rp.file_proposal(cid, None, kind="pressure", title=title,
                            wants_true="A creditor's bill is nailed at the quay.",
                            why_now="The player keeps to the waterfront.",
                            turn_idx=turn_idx)


def _refusal(uid, reason="No creditor keeps an office here."):
    return {"verdicts": [{"proposal_uid": uid, "verdict": "refuse", "reason": reason,
                          "contradiction": "no creditor"}],
            "reply": reason}


def test_a_pacing_pass_suggests_and_leaves_the_judging_to_the_follow_up(
        temp_db, scripted):
    """The Planner's deliberation -- six calls and more -- ran in the pacing
    pass's own job, every six beats, over directions the story might never
    come near. The pass now files its suggestion, shows it in motion, and
    asks the Planner nothing; the follow-up judges it later."""
    from core import jobs
    cid = _story(temp_db)
    script = scripted(dramaturge=[{"proposals": [{
        "kind": "pressure", "title": "A bill on the quay",
        "wants_true": "A creditor's bill is nailed at the quay.",
        "why_now": "The player keeps to the waterfront."}],
        "note": "Something gathers at the waterline."}])
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, md.BEATS_PER_PROPOSAL)))
    assert job.key == sp.DRAMATURGE_JOB_KEY and job.state == "done", (job.state, job.error)
    prop = rp.proposals(cid, None)[0]
    assert job.result["awaiting"] == [prop["uid"]] and job.result["deliberation"] is None
    assert script.payloads.get("story_planner", []) == []
    assert prop["status"] == "open" and not prop["due"] and prop["taken_turn"] is None
    assert [m["uid"] for m in room.status(cid, None)["in_motion"]] == [prop["uid"]]
    jobs.drain(timeout=5.0)


def test_a_suggestion_the_beat_brings_near_is_deliberated_at_that_commit(
        temp_db, scripted, monkeypatch):
    """At each commit of the player's frame the decision model is asked, of
    the beat just played, whether it brings the story near each pending
    suggestion -- its title, what it wants true and why now -- and one it
    does is judged then, out of band. The beat is read once."""
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    prop = _suggestion(cid)
    asked = _decides(monkeypatch, 0.9, asked=[])
    script = scripted(story_planner=[_refusal(prop["uid"])])
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, 3)))
    assert job.key == sp.DIRECTION_JOB_KEY and job.state == "done", (job.state, job.error)
    assert job.result["due"] == {prop["uid"]: "touched"}
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "refused"
    assert script.payloads["story_planner"][0]["task"]["proposals"][0]["uid"] == prop["uid"]
    [request] = asked
    assert "Gulls over the quay (beat 3)." in request["state"]
    assert "(beat 2)" not in request["state"]
    question = request["questions"]["near:" + prop["uid"]]
    assert question["type"] == "noul"
    for part in ("A bill on the quay", "nailed at the quay", "keeps to the waterfront"):
        assert part in question["instructions"]
    assert rp.follow_up_turn(cid, None) == 3


def test_a_suggestion_the_story_does_not_near_waits_then_is_deliberated_at_its_bound(
        temp_db, scripted, monkeypatch):
    """A suggestion the decision model never reads as neared is judged anyway
    once it has waited `DIRECTION_WAIT_INTERVALS` pacing intervals of the
    frame's own beats: a lazy step has a bounded wait, so nothing is dropped
    (owner, 2026-10-08). Each beat is read once, by itself."""
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    prop = _suggestion(cid, turn_idx=2)
    asked = _decides(monkeypatch, 0.1, asked=[])
    script = scripted(story_planner=[_refusal(prop["uid"])])
    bound = rp.direction_wait_beats(md.beats_per_proposal(cid, None))
    assert bound == rp.DIRECTION_WAIT_INTERVALS * md.BEATS_PER_PROPOSAL
    for idx in range(3, 2 + bound):
        job = _wait(sp.schedule_room_work(_beat(temp_db, cid, idx)))
        assert job.key == sp.DIRECTION_JOB_KEY and job.state == "done", idx
        assert not job.result.get("due"), idx
    assert script.payloads.get("story_planner", []) == []
    assert ["(beat %d)" % idx in a["state"] and "(beat %d)" % (idx - 1) not in a["state"]
            for idx, a in zip(range(3, 2 + bound), asked)] == [True] * (bound - 1)
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, 2 + bound)))
    assert job.result["due"] == {prop["uid"]: "waited"}
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "refused"


def test_the_bound_holds_when_the_decision_model_cannot_answer(
        temp_db, scripted, monkeypatch):
    """Nothing waits on the decision model: refused, unreachable or not
    configured at all, the bound alone decides -- and with none configured
    no job is queued for it before the bound."""
    from llm import decisions
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    prop = _suggestion(cid, turn_idx=2)
    _decides(monkeypatch, decisions.DecisionError("jev 503: unavailable"))
    later = []
    script = scripted(story_planner=[_refusal(prop["uid"]),
                                     lambda p: _refusal(later[0])])
    bound = rp.direction_wait_beats(md.beats_per_proposal(cid, None))
    for idx in range(3, 2 + bound):
        job = _wait(sp.schedule_room_work(_beat(temp_db, cid, idx)))
        assert job.result.get("decision") == "unavailable" and not job.result.get("due")
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, 2 + bound)))
    assert job.result["due"] == {prop["uid"]: "waited"}
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "refused"
    # No decision model in the story at all.
    monkeypatch.setattr(decisions, "OVERRIDE", None)
    assert not decisions.configured()
    second = _suggestion(cid, title="A bell on the quay", turn_idx=2 + bound)
    later.append(second["uid"])
    assert sp.schedule_room_work(_beat(temp_db, cid, 3 + bound)) is None
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, 2 + 2 * bound)))
    assert job.key == sp.DIRECTION_JOB_KEY and job.result["due"] == {second["uid"]: "waited"}
    assert rp.get_proposal(cid, None, second["uid"])["status"] == "refused"
    assert len(script.payloads["story_planner"]) == 2


def test_a_players_ask_is_deliberated_at_once_never_lazily(temp_db, scripted):
    """The player asked for direction and is waiting on the answer: what the
    Dramaturge files for it is due at once and judged without waiting on a
    commit or on the decision model, which this story does not have."""
    from core import jobs
    from llm import decisions
    cid = _story(temp_db)
    assert not decisions.configured()
    script = scripted(
        story_planner=[{"reply": "The Dramaturge is thinking about it.",
                        "to_dramaturge": "A complication at the quay, please."},
                       lambda p: _refusal(p["task"]["proposals"][0]["uid"])],
        dramaturge=[{"proposals": [{"kind": "pressure", "title": "A bill on the quay",
                                    "wants_true": "A creditor's bill is nailed at the quay.",
                                    "why_now": "The player asked for a complication."}],
                     "note": "A creditor, perhaps."}])
    sp.planner_reply(cid, None, "Give me a complication.")
    assert _wait(_job(cid, sp.DRAMATURGE_JOB_KEY)).state == "done"
    follow = _wait(_job(cid, sp.DIRECTION_JOB_KEY))
    assert follow.state == "done", (follow.state, follow.error)
    prop = rp.proposals(cid, None)[0]
    assert follow.result["deliberations"][0]["refused"] == [prop["uid"]]
    assert prop["status"] == "refused" and not prop["due"]
    assert script.payloads["story_planner"][1]["task"]["kind"] == "deliberate"
    jobs.drain(timeout=5.0)


def test_a_reroll_of_the_beat_a_deliberation_read_cancels_it_and_asks_again(
        temp_db, scripted, monkeypatch):
    """The follow-up read the beat the player rerolled, so the restore cancels
    it: its verdict never lands, and the suggestion is back as it stood
    before the beat -- untaken -- for the rerolled beat to be asked about."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    prop = _suggestion(cid)
    _decides(monkeypatch, 0.9)
    started, release = threading.Event(), threading.Event()

    def slow(_payload):
        started.set()
        release.wait(5)
        return _refusal(prop["uid"], "Judged off the discarded beat.")
    script = scripted(story_planner=[slow, _refusal(prop["uid"])])
    ensure_checkpoint(cid, 3)
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job.key == sp.DIRECTION_JOB_KEY and started.wait(5)
    restore_checkpoint(cid, 3)
    release.set()
    assert _wait(job).state == "cancelled", (job.state, job.error)
    held = rp.get_proposal(cid, None, prop["uid"])
    assert held["status"] == "open" and held["taken_turn"] is None
    assert "Judged off the discarded beat." not in [m["text"] for m in room.messages(cid, None)]
    again = _wait(sp.schedule_room_work(_beat(temp_db, cid, 3)))
    assert again is not job and again.state == "done", (again.state, again.error)
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "refused"
    assert len(script.payloads["story_planner"]) == 2


def test_a_reroll_of_a_later_beat_leaves_an_earlier_beats_deliberation_running(
        temp_db, scripted, monkeypatch):
    """(review B) Restoring checkpoint N takes the story back to before beat
    N: a deliberation queued at an earlier beat read nothing it throws away,
    and cancelling it -- as the restore did -- lost the judgement with
    nothing to ask for it again."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    prop = _suggestion(cid)
    _decides(monkeypatch, 0.9)
    started, release = threading.Event(), threading.Event()

    def slow(_payload):
        started.set()
        release.wait(5)
        return _refusal(prop["uid"])
    scripted(story_planner=[slow])
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job.key == sp.DIRECTION_JOB_KEY and started.wait(5)
    ensure_checkpoint(cid, 4)                  # the player starts beat 4
    _beat(temp_db, cid, 4)
    restore_checkpoint(cid, 4)                 # and rerolls it
    release.set()
    assert _wait(job).state == "done", (job.state, job.error)
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "refused"


# ---------------------------------------------------------------------------
# The second review of 2026-10-08
# ---------------------------------------------------------------------------

def test_a_task_retires_only_the_drafts_its_own_calls_opened(temp_db, scripted):
    """(review A) The floor diffed the package ledger, and every Planner draft
    has one author, so a draft a panel reply opened while a deliberation ran
    -- the player asking for a storm, the reply asking for the grant scoped
    to that package -- was retired when the deliberation ended, and the
    grant the player then gave lapsed on arrival. A task retires only what
    its own `new_package` calls opened."""
    from story.plot_packages import get_package, list_packages
    from story.room_tools import run_tool
    cid = _story(temp_db)
    prop = rp.file_proposal(cid, None, kind="pressure", title="A bill",
                            wants_true="A bill is nailed up.", why_now="idle")
    seen = {}

    def a_reply_lands_while_the_task_runs(_payload):
        out = run_tool(cid, "new_package", {"title": "The storm the player asked for",
                                            "premise": "p"}, actor="story_planner")
        seen["reply"] = out["uid"]
        run_tool(cid, "draft_operation", {"uid": out["uid"], "operation": {
            "op": "post_artifact", "room": "quay", "description": "a storm notice"}},
            actor="story_planner")
        return {"calls": [{"tool": "new_package", "args": {"title": "The bill",
                                                          "premise": "p"}}]}
    scripted(story_planner=[
        a_reply_lands_while_the_task_runs,
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {"op": "post_artifact", "room": "quay",
                                               "description": "a bill"}}}]},
        {"verdicts": [{"proposal_uid": prop["uid"], "verdict": "accept",
                       "reason": "A creditor posts bills."}], "reply": "It fits."}])
    sp.deliberate(cid, None, [prop], turn_idx=2)
    by_title = {p["title"]: p["status"] for p in list_packages(cid)}
    assert by_title == {"The storm the player asked for": "draft", "The bill": "retired"}
    md.grant_mandate(cid, None, text="Yes, post the storm notice.",
                     capabilities=["post_artifact"], request=seen["reply"])
    assert [m["text"] for m in md.active_mandates(cid, None)] == ["Yes, post the storm notice."]
    assert get_package(cid, seen["reply"])["status"] == "draft"


def test_a_reroll_of_a_later_beat_leaves_an_earlier_beats_pass_running(temp_db, scripted):
    """(review B) The restore cancelled every Room job whatever beat it read:
    rerolling beat 7 killed the pass queued at beat 6, which read nothing the
    restore discards. Only a job that read a discarded beat is cancelled
    (`core.jobs.cancel_from`)."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    for idx in range(3, pace):
        _beat(temp_db, cid, idx)
    slow, started, release = _blocked("Read off beat six.", {
        "kind": "pressure", "title": "The coat's pockets",
        "wants_true": "The coat holds a second receipt."})
    scripted(dramaturge=[slow])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert started.wait(5)
    ensure_checkpoint(cid, pace + 1)           # the player starts the next beat
    _beat(temp_db, cid, pace + 1)
    restore_checkpoint(cid, pace + 1)          # and rerolls it
    release.set()
    assert _wait(job).state == "done", (job.state, job.error)
    assert [p["title"] for p in rp.proposals(cid, None)] == ["The coat's pockets"]
    assert "Read off beat six." in [m["text"] for m in room.messages(cid, None)]
    jobs.drain(timeout=5.0)


def test_a_cancelled_pass_does_not_hand_back_an_ask_it_already_answered(
        temp_db, scripted, monkeypatch):
    """(review C) The answer is the Dramaturge's line in the thread, and no
    restore takes the thread back: a pass cancelled after its answer landed
    handed the ask back anyway, and the next commit answered it a second time
    at the cost of a second pass. Cancelled before it answered, a pass still
    hands its ask back (`test_a_cancelled_pass_hands_back_the_ask_it_took`)."""
    import types
    cid = _story(temp_db)
    job = types.SimpleNamespace(cancelled=threading.Event())
    rp.ask_brief(cid, None, "A complication at the quay, please.", turn_idx=2)
    # The restore lands just after the answer: where the follow-up is queued,
    # or -- where the pass deliberated in its own job -- in that deliberation.
    monkeypatch.setattr(sp, "_queue_follow_up",
                        lambda *a, **k: job.cancelled.set(), raising=False)
    scripted(
        dramaturge=[{"proposals": [{"kind": "pressure", "title": "A bill",
                                    "wants_true": "A bill is nailed up.",
                                    "why_now": "idle"}],
                     "note": "Answer one: a creditor's bill."}],
        story_planner=[lambda p: (job.cancelled.set(), {"reply": "Weighing it."})[1]])
    report = sp.run_dramaturge_pass(cid, None, job=job)
    assert report["cancelled"]
    assert "Answer one: a creditor's bill." in [m["text"] for m in room.messages(cid, None)]
    assert rp.waiting_briefs(cid, None) == []


def _two_round_grant_ask(cid, scripted):
    """A deliberation over two proposals: round 1 accepts the first and asks
    for the grant to carry it out, as the Planner's card says, and sends the
    second back; round 2 refuses the second and asks nothing."""
    p1 = rp.file_proposal(cid, None, kind="pressure", title="A bill",
                          wants_true="A bill is nailed up.", why_now="idle")
    p2 = rp.file_proposal(cid, None, kind="arrival", title="A clerk",
                          wants_true="A clerk comes down.", why_now="now")
    ask = "May the room post the bill? It needs post_artifact."
    scripted(
        story_planner=[
            {"verdicts": [{"proposal_uid": p1["uid"], "verdict": "accept", "reason": "fits"},
                          {"proposal_uid": p2["uid"], "verdict": "revise",
                           "reason": "the guild keeps no clerk", "contradiction": "no office"}],
             "reply": "The bill fits; I need your leave. The clerk needs work.",
             "questions": [ask]},
            {"verdicts": [{"proposal_uid": p2["uid"], "verdict": "refuse",
                           "reason": "still no office", "contradiction": "no office"}],
             "reply": "No clerk."}],
        dramaturge=[{"revision": {"wants_true": "A clerk's letter arrives.",
                                  "why_now": "now"}, "note": "Then a letter."}])
    report = sp.deliberate(cid, None, [p1, p2], turn_idx=2)
    assert report["rounds"] == 2 and report["refused"] == [p2["uid"]]
    return p1, p2, ask


def test_a_deliberations_grant_ask_stands_through_its_later_rounds(temp_db, scripted):
    """(review D) Every round of one deliberation adds to one list of
    questions: round 2 judged only the second proposal, asked nothing, and
    replaced "the last task's" questions -- its own first round's -- so the
    accepted proposal waited on a grant nobody had been asked for."""
    cid = _story(temp_db)
    p1, _p2, ask = _two_round_grant_ask(cid, scripted)
    assert rp.get_proposal(cid, None, p1["uid"])["status"] == "accepted"
    assert _asked(cid) == [("task", ask)]


def test_no_other_task_takes_a_deliberations_question_off(temp_db, scripted):
    """(review D) A task's questions are keyed by WHICH task asked: the next
    fill ended with none, replaced the deliberation's grant ask, and the
    grant the player had scoped to that question lapsed with it."""
    cid = _story(temp_db)
    prop = rp.file_proposal(cid, None, kind="pressure", title="A bill",
                            wants_true="A bill is nailed up.", why_now="idle")
    ask = "May the room post the bill? It needs post_artifact."
    scripted(story_planner=[{"verdicts": [{"proposal_uid": prop["uid"],
                                           "verdict": "accept", "reason": "fits"}],
                             "reply": "It fits; I need your leave.", "questions": [ask]}])
    sp.deliberate(cid, None, [prop], turn_idx=2)
    q_uid = [q["uid"] for q in room.status(cid, None)["questions"] if q["text"] == ask][0]
    md.grant_mandate(cid, None, text="Yes, post it.", capabilities=["post_artifact"],
                     request=q_uid)
    assert len(md.active_mandates(cid, None)) == 1
    scripted(story_planner=[{"reply": "Nothing to build."}])
    sp._run_task(cid, None, {"kind": "fill", "needs": []}, base_turn=2)
    assert ask in _texts(cid)
    assert [m["text"] for m in md.active_mandates(cid, None)] == ["Yes, post it."]


def test_a_deliberations_question_leaves_once_every_proposal_it_judged_settles(
        temp_db, scripted):
    """(review D) The grant ask stands while the proposal it serves is
    accepted and unbuilt; once that proposal has landed -- or been refused,
    withdrawn or returned -- nothing about it is left to answer, and the
    question goes with the row's next write."""
    cid = _story(temp_db)
    prop = rp.file_proposal(cid, None, kind="pressure", title="A bill",
                            wants_true="A bill is nailed up.", why_now="idle")
    ask = "May the room post the bill? It needs post_artifact."
    scripted(story_planner=[{"verdicts": [{"proposal_uid": prop["uid"],
                                           "verdict": "accept", "reason": "fits"}],
                             "reply": "It fits; I need your leave.", "questions": [ask]}])
    sp.deliberate(cid, None, [prop], turn_idx=2)
    sp.write_status(cid, None, turn_idx=2)
    assert rp.get_proposal(cid, None, prop["uid"])["status"] == "accepted"
    assert ask in _texts(cid)
    rp.settle_proposal(cid, None, prop["uid"], "implemented", package_uid="plot:bill")
    sp.write_status(cid, None, turn_idx=3)
    assert ask not in _texts(cid)


def test_the_engine_keeps_one_returned_ask_naming_each_returned_proposal_once(
        temp_db, scripted):
    """(review E) Each deliberation that returned a proposal asked a new
    question naming its titles, and only a reply took them off: past six
    they filled the row, cut the question the player had been asked in
    conversation -- the grant scoped to it lapsing -- and the newest
    returned ask was cut on write. Now one engine ask names every returned
    proposal the player has not answered, each once, and the engine never
    holds more than `ENGINE_QUESTIONS_CAP` rows."""
    cid = _story(temp_db)
    scripted(story_planner=[{"reply": "I can plan him.",
                             "questions": ["May the room plan the harbour master?"]}])
    sp.run_planner(cid, None, text="Who runs the harbour?")
    q_uid = room.status(cid, None)["questions"][0]["uid"]
    md.grant_mandate(cid, None, text="Yes, plan him.", capabilities=["plan_entity"],
                     request=q_uid)
    titles = []
    for i in range(sp.STATUS_QUESTIONS_CAP + 1):
        prop = rp.file_proposal(cid, None, kind="pressure", title="Turn %d" % i,
                                wants_true="Thing %d happens." % i, why_now="now")
        scripted(story_planner=[{"reply": "Thinking."}, {"reply": "Still thinking."}])
        assert sp.deliberate(cid, None, [prop], turn_idx=2)["returned"] == [prop["uid"]]
        titles.append(prop["title"])
    engine = [q for q in room.status(cid, None)["questions"] if q["source"] == "engine"]
    assert [q["text"] for q in engine] == [sp.RETURNED_QUESTION % "; ".join(titles)]
    assert "May the room plan the harbour master?" in _texts(cid)
    assert [m["text"] for m in md.active_mandates(cid, None)] == ["Yes, plan him."]
    # Answered in conversation, it leaves, and the next return starts afresh.
    scripted(story_planner=[{"reply": "Let those go.",
                             "questions": ["May the room plan the harbour master?"]}])
    sp.run_planner(cid, None, text="Drop the returned ones.")
    prop = rp.file_proposal(cid, None, kind="pressure", title="Turn 9",
                            wants_true="Thing 9 happens.", why_now="now")
    scripted(story_planner=[{"reply": "Thinking."}, {"reply": "Still thinking."}])
    sp.deliberate(cid, None, [prop], turn_idx=2)
    assert [q["text"] for q in room.status(cid, None)["questions"]
            if q["source"] == "engine"] == [sp.RETURNED_QUESTION % "Turn 9"]
    # However many kinds of ask the engine grows, half the row stays the
    # Planner's.
    rows = sp._question_rows([{"text": "Engine ask %d" % i, "source": "engine"}
                              for i in range(5)]
                             + ["Model question %d" % i for i in range(5)])
    assert [r["source"] for r in rows].count("engine") == sp.ENGINE_QUESTIONS_CAP
    assert len(rows) == sp.STATUS_QUESTIONS_CAP


def test_the_rerolled_commit_starts_its_own_pass_while_the_cancelled_one_finishes(
        temp_db, scripted):
    """(review F) The restore cancels the pass, but the pass holds its slot
    until its model call returns, and the rerolled beat's commit joined it:
    the rerolled beat was never asked. A submit never joins a cancelled job."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    for idx in range(3, pace):
        _beat(temp_db, cid, idx)
    ensure_checkpoint(cid, pace)
    slow, started, release = _blocked("Read off the discarded beat.")
    scripted(dramaturge=[slow, {"none_needed": True,
                                "note": "Read off the rerolled beat."}])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert started.wait(5)
    restore_checkpoint(cid, pace)
    rerolled = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert rerolled is not job
    assert _wait(rerolled).state == "done", (rerolled.state, rerolled.error)
    release.set()
    assert _wait(job).state == "cancelled"
    notes = [m["text"] for m in room.messages(cid, None) if m["role"] == "dramaturge"]
    assert notes == ["Read off the rerolled beat."]
    assert rp.last_pass_turn(cid, None) == pace
    jobs.drain(timeout=5.0)


def test_the_opening_clears_the_questions_asked_before_the_story(temp_db, scripted):
    """(review G) Nobody is there to answer between the prelude and the first
    beat, and the prelude expects the player may simply begin: the opening
    clears the questions the Room asked before the story, as it always did,
    and keeps the engine's own asks. Left standing, the prelude's question
    rode every task payload for the whole story -- the class chat 126 found."""
    cid = _story(temp_db, turns=0, narrations=False)
    ask = "A hamlet of forty souls, or a working fen port of a few hundred?"
    scripted(story_planner=[{"reply": "Before we begin: what kind of place?",
                             "questions": [ask]},
                            {"reply": "The quay is ready."}])
    sp.run_prelude(cid, None, passage="A port at dusk.")
    assert _texts(cid) == [ask]
    sp.ask_question(cid, None, sp.WAITING_LINE)
    sp.run_opening_plan(cid, None, passage="A port at dusk.")
    assert _asked(cid) == [("engine", sp.WAITING_LINE)]


def test_a_retired_draft_takes_its_status_line_with_it(temp_db, scripted):
    """(review H) The line says what the room has in motion. A fill whose one
    draft the floor retired left its "drafting" line standing over nothing,
    and the next Dramaturge pass read it back as `status_line` -- the class
    review F5 fixed for a pass that found nothing."""
    from world.planning_needs import file_planning_need
    cid = _story(temp_db)
    file_planning_need(cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
    md.grant_mandate(cid, None, text="You may answer needs.",
                     capabilities=["identity_fills", "answer_need"],
                     limits={"fills_per_hour": 4})
    scripted(story_planner=[
        {"calls": [{"tool": "new_package", "args": {"title": "The letter", "premise": "p"}}],
         "status_line": "Drafting the sealed letter's notice."},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {"op": "post_artifact", "room": "quay",
                                               "description": "a notice"}}}]},
        {"reply": "I drafted a notice; it needs your leave."}])
    sp.run_fill(cid, None, base_turn=2)
    status = room.status(cid, None)
    assert status["in_motion"] == []
    assert status["line"] == sp.NO_STATUS_LINE


# ---------------------------------------------------------------------------
# The third review of 2026-10-08
# ---------------------------------------------------------------------------

def _hears(monkeypatch, word, asked):
    """The decision model answering yes only to a passage carrying ``word``;
    every passage it is asked kept in ``asked``."""
    from llm import decisions

    def answer(state, questions):
        asked.append(state)
        share = 0.9 if word in state else 0.1
        return {key: {"type": "noul", "noul": share} for key in questions}
    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    return asked


def _narrate(db, cid, idx, prose):
    """Beat ``idx`` as it was played again: its narration is now ``prose``."""
    db.qi("UPDATE variants SET content=? WHERE active=1 AND step_id IN ("
          "SELECT s.id FROM steps s JOIN turns t ON t.id=s.turn_id "
          "WHERE t.chat_id=? AND t.idx=? AND s.key='narrator')",
          (json.dumps({"prose": prose}), cid, idx))


def _held(started, release, answer):
    """A Planner answer that waits to be released."""
    def call(payload):
        started.set()
        release.wait(5)
        return answer(payload) if callable(answer) else answer
    return call


def test_a_reroll_of_a_beat_a_looping_follow_up_read_cancels_it(
        temp_db, scripted, monkeypatch):
    """(review R3-1) The follow-up loops until nothing is due, and each round
    reads the beats played since. Queued at beat 3, it read beat 4 and began
    judging what beat 4 brought near; the restore decided by the beat the job
    was QUEUED from, so a reroll of beat 4 left it writing what it built on
    the discarded beat into the rerolled timeline. It decides by what the job
    READ. The verdict its first round reached from beat 3 stands (R3-2)."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    first = _suggestion(cid, title="A bill on the quay", turn_idx=2)
    second = _suggestion(cid, title="A bell in the fog", turn_idx=2)
    rp.mark_due(cid, None, {first["uid"]: "asked"})
    _hears(monkeypatch, "(beat 4)", [])
    s1, r1, s2, r2 = (threading.Event() for _ in range(4))
    scripted(story_planner=[
        _held(s1, r1, _refusal(first["uid"])),
        _held(s2, r2, _refusal(second["uid"], "Judged off the discarded beat."))])
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job.key == sp.DIRECTION_JOB_KEY and s1.wait(5)
    ensure_checkpoint(cid, 4)                       # the player starts beat 4
    assert sp.schedule_room_work(_beat(temp_db, cid, 4)) is job   # its commit joins
    assert job.base_turn == 3
    r1.set()
    assert s2.wait(5)                     # the next round read beat 4 and judges
    assert rp.follow_up_turn(cid, None) == 4
    restore_checkpoint(cid, 4)                      # the player rerolls beat 4
    r2.set()
    assert _wait(job).state == "cancelled", (job.state, job.error)
    assert job.read_turn == 4
    held = rp.get_proposal(cid, None, second["uid"])
    assert held["status"] == "open" and held["taken_turn"] is None and not held["due"]
    assert "Judged off the discarded beat." not in [
        m["text"] for m in room.messages(cid, None)]
    assert rp.get_proposal(cid, None, first["uid"])["status"] == "refused"


def test_a_reroll_of_the_beat_a_passs_later_round_read_cancels_it(temp_db, scripted):
    """(review R3-1) A pass answers, with one more round, an ask made while
    it ran -- and that round reads the beats played since. Queued at the
    pacing beat, its asked round read the next beat; a reroll of that beat
    left its answer, written off the discarded beat, landing in the rerolled
    timeline. Cancelled, it files nothing, the ask it took waits again, and
    the rerolled beat's own pass answers it."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    for idx in range(3, pace):
        _beat(temp_db, cid, idx)
    slow1, started1, release1 = _blocked("The pacing pass.")
    slow2, started2, release2 = _blocked("Answered off the discarded beat.", {
        "kind": "pressure", "title": "The coat's pockets",
        "wants_true": "The coat holds a second receipt."})
    script = scripted(
        dramaturge=[slow1, slow2, {"none_needed": True, "note": "Answered again."}],
        story_planner=[{"reply": "Thinking.",
                        "to_dramaturge": "A complication, please."}])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert job.key == sp.DRAMATURGE_JOB_KEY and job.base_turn == pace
    assert started1.wait(5)
    ensure_checkpoint(cid, pace + 1)            # the player starts the next beat
    _beat(temp_db, cid, pace + 1)
    sp.planner_reply(cid, None, "Give me a complication.")   # and asks during it
    release1.set()
    assert started2.wait(5)                     # the asked round read that beat
    restore_checkpoint(cid, pace + 1)           # the player rerolls it
    release2.set()
    assert _wait(job).state == "cancelled", (job.state, job.error)
    assert job.read_turn == pace + 1
    assert rp.proposals(cid, None) == []
    assert "Answered off the discarded beat." not in [
        m["text"] for m in room.messages(cid, None)]
    assert [b["text"] for b in rp.waiting_briefs(cid, None)] == ["A complication, please."]
    rerolled = _wait(sp.schedule_room_work(_beat(temp_db, cid, pace + 1)))
    assert rerolled is not job and rerolled.state == "done", (
        rerolled.state, rerolled.error)
    assert script.payloads["dramaturge"][-1]["player_asks"] == "A complication, please."
    assert room.messages(cid, None)[-1]["text"] == "Answered again."
    jobs.drain(timeout=5.0)


def _spared_follow_up(temp_db, scripted, monkeypatch):
    """A follow-up queued at beat 3, judging the player's ask, while beat 4
    is played -- narrating a bell the decision model hears as nearing the
    pending suggestion -- and rerolled; the old narration stands until the
    replay replaces it. Returns what the test reads."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    first = _suggestion(cid, title="A bill on the quay", turn_idx=2)
    second = _suggestion(cid, title="A bell in the fog", turn_idx=2)
    rp.mark_due(cid, None, {first["uid"]: "asked"})
    asked = _hears(monkeypatch, "bell tolls", [])
    started, release = threading.Event(), threading.Event()
    scripted(story_planner=[_held(started, release, _refusal(first["uid"])),
                            _refusal(second["uid"], "Judged off beat four.")])
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job.key == sp.DIRECTION_JOB_KEY and started.wait(5)
    ensure_checkpoint(cid, 4)
    _beat(temp_db, cid, 4)
    _narrate(temp_db, cid, 4, "A bell tolls out in the fog (beat 4, as first played).")
    restore_checkpoint(cid, 4)                   # rerolled while beat 3's judging runs
    assert not job.cancelled.is_set()
    return cid, first, second, asked, job, release


def test_a_job_a_restore_spares_finishes_its_work_and_never_reads_the_discarded_beat(
        temp_db, scripted, monkeypatch):
    """(review R3-1) A job that read only beats a restore keeps is spared
    (review B) -- but its next round read the beat being played again, its
    old narration standing until the replay replaced it, and judged what
    that discarded beat brought near. It finishes the deliberation it is in
    and starts no other; the replayed beat's commit has it read afresh."""
    cid, first, second, asked, job, release = _spared_follow_up(
        temp_db, scripted, monkeypatch)
    release.set()                     # beat 3's judging ends before the replay
    assert _wait(job).state == "done", (job.state, job.error)
    assert rp.get_proposal(cid, None, first["uid"])["status"] == "refused"
    held = rp.get_proposal(cid, None, second["uid"])
    assert held["status"] == "open" and held["taken_turn"] is None
    assert not any("as first played" in s for s in asked)
    assert job.result["spared"] and len(job.result["deliberations"]) == 1
    assert job.read_turn == 3 and job.read_limit == 3
    _narrate(temp_db, cid, 4, "Gulls over the quay (beat 4, played again).")
    replay = _wait(sp.schedule_room_work(_beat(temp_db, cid, 4)))
    assert replay is not job and replay.state == "done", (replay.state, replay.error)
    assert "played again" in asked[-1]
    assert rp.get_proposal(cid, None, second["uid"])["status"] == "open"


def test_the_replayed_beats_commit_hands_a_spared_job_the_new_beat(
        temp_db, scripted, monkeypatch):
    """(review R3-1) The replayed beat's own commit joins the job the
    restore spared, and hands it the beat as played again: one follow-up at
    a time still, and the replay is read at once, never the discarded beat."""
    cid, first, second, asked, job, release = _spared_follow_up(
        temp_db, scripted, monkeypatch)
    _narrate(temp_db, cid, 4, "A bell tolls out in the fog (beat 4, played again).")
    assert sp.schedule_room_work(_beat(temp_db, cid, 4)) is job
    release.set()
    assert _wait(job).state == "done", (job.state, job.error)
    assert not job.result.get("spared") and len(job.result["deliberations"]) == 2
    assert job.result["due"] == {second["uid"]: "touched"}
    assert rp.get_proposal(cid, None, second["uid"])["status"] == "refused"
    beat_four = [s for s in asked if "(beat 4" in s]
    assert len(beat_four) == 1 and "played again" in beat_four[0]


def test_rerolling_the_beat_after_a_pacing_pass_keeps_its_suggestions(temp_db, scripted):
    """(review R3-2) The next beat's snapshot is taken as it starts, and the
    pacing pass queued a beat earlier can still be filing then. A reroll of
    that next beat spared the pass -- it read nothing the restore discards --
    and rolled its suggestions back, while its note stood in the thread and
    its pacing stayed spent: gone until the next pass. What a spared job
    wrote from kept beats is kept, and the row shows it in motion."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    for idx in range(3, pace):
        _beat(temp_db, cid, idx)
    slow, started, release = _blocked("Something gathers at the waterline.", {
        "kind": "pressure", "title": "The coat's pockets",
        "wants_true": "The coat holds a second receipt."})
    scripted(dramaturge=[slow])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))    # the pacing beat
    assert job.key == sp.DRAMATURGE_JOB_KEY and started.wait(5)
    ensure_checkpoint(cid, pace + 1)                          # the next beat starts
    _beat(temp_db, cid, pace + 1)
    release.set()                                             # the pass files during it
    assert _wait(job).state == "done", (job.state, job.error)
    restore_checkpoint(cid, pace + 1)                         # and it is rerolled
    [kept] = rp.proposals(cid, None)
    assert kept["title"] == "The coat's pockets" and kept["status"] == "open"
    assert kept["filed_turn"] == pace and not kept["due"] and kept["taken_turn"] is None
    assert rp.last_pass_turn(cid, None) == pace
    assert rp.pass_due(cid, None, pace + 1, pace)[0] is False
    status = room.status(cid, None)
    assert [m["uid"] for m in status["in_motion"]] == [kept["uid"]]
    assert status["line"] == sp.IN_MOTION_LINE
    jobs.drain(timeout=5.0)


def test_rerolling_the_beat_after_an_asked_pass_keeps_its_answer_due_at_once(
        temp_db, scripted):
    """(review R3-2) The same timing for a pass the player asked for: its
    answer stood in the thread and its suggestion rolled back, never judged.
    It comes back as the pass filed it, due at once; the deliberation that
    took it up while the discarded beat was in play read that beat and is
    cancelled; and the rerolled beat's commit has it judged."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    slow, started, release = _blocked("A creditor, perhaps.", {
        "kind": "pressure", "title": "A bill on the quay",
        "wants_true": "A creditor's bill is nailed at the quay."})
    judging, judged = threading.Event(), threading.Event()
    scripted(story_planner=[
        {"reply": "The Dramaturge is thinking about it.",
         "to_dramaturge": "A complication at the quay, please."},
        _held(judging, judged, lambda p: _refusal(
            p["task"]["proposals"][0]["uid"], "Judged off the discarded beat.")),
        lambda p: _refusal(p["task"]["proposals"][0]["uid"])],
        dramaturge=[slow])
    sp.planner_reply(cid, None, "Give me a complication.")
    assert started.wait(5)                          # the pass reads beat 2
    ensure_checkpoint(cid, 3)                       # the player starts beat 3
    _beat(temp_db, cid, 3)
    release.set()                                   # the answer lands during it
    assert judging.wait(5)                          # and its judging begins
    follow = _job(cid, sp.DIRECTION_JOB_KEY)
    restore_checkpoint(cid, 3)                      # beat 3 is rerolled
    judged.set()
    assert _wait(follow).state == "cancelled", (follow.state, follow.error)
    [kept] = rp.proposals(cid, None)
    assert kept["status"] == "open" and kept["due"] == "asked"
    assert kept["taken_turn"] is None and kept["filed_turn"] == 2
    assert "Judged off the discarded beat." not in [
        m["text"] for m in room.messages(cid, None)]
    again = _wait(sp.schedule_room_work(_beat(temp_db, cid, 3)))
    assert again.key == sp.DIRECTION_JOB_KEY and again.state == "done", (
        again.state, again.error)
    assert rp.get_proposal(cid, None, kept["uid"])["status"] == "refused"
    jobs.drain(timeout=5.0)


def test_a_grant_that_permits_nothing_never_lifts_a_spend_cap(temp_db):
    """(review R3-3) Every grant that permits something is a licence to work
    and carries spend: one naming no number leaves the room unlimited. A
    grant that permits nothing -- the Dramaturge's off switch, a dial, a
    pace -- is no licence, and it lifted the hourly and per-reply caps the
    player had set, so fills, deliberations and replies ran uncapped. It
    lifts nothing; a spend number it names only ever lowers."""
    cid = _story(temp_db)
    capped = md.grant_mandate(cid, None, text="Fill in who is about, at most 60 an hour.",
                              capabilities=["identity_fills"],
                              limits={"calls_per_hour": 60, "calls_per_reply": 20})
    assert md.spend_limits(cid, None) == {"calls_per_reply": 20, "calls_per_hour": 60}
    for text, limits in (("Suggest nothing I did not ask for.", {"beats_per_proposal": 0}),
                         ("Be bolder.", {"surprise": 4}),
                         ("Only every ten beats.", {"beats_per_proposal": 10}),
                         ("Spend as much as you like.", {"calls_per_hour": 500})):
        md.grant_mandate(cid, None, text=text, capabilities=[], limits=limits)
        assert md.spend_limits(cid, None) == {"calls_per_reply": 20,
                                              "calls_per_hour": 60}, text
    assert md.spend_citation(cid, None, "calls_per_hour") == capped["uid"]
    lower = md.grant_mandate(cid, None, text="No more than 30 an hour.",
                             capabilities=[], limits={"calls_per_hour": 30})
    assert md.spend_limits(cid, None)["calls_per_hour"] == 30
    assert md.spend_citation(cid, None, "calls_per_hour") == lower["uid"]
    # A licence naming no number still leaves the room unlimited, as it always
    # has -- under a ceiling the player named.
    md.grant_mandate(cid, None, text="Plan rooms freely.", capabilities=["plan_rooms"])
    assert md.spend_limits(cid, None) == {"calls_per_reply": None, "calls_per_hour": 30}


def test_a_suggestion_is_asked_only_about_the_beats_after_it_was_written(
        temp_db, scripted, monkeypatch):
    """(review R3-4) A new suggestion was asked about every beat since the
    follow-up last read -- the beats its pass wrote it from, which its own
    `why_now` describes. The answer confirmed itself, and it was judged a beat
    after it was filed: the lazy saving gone. It is asked only about the
    beats played after the newest one its pass read."""
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    first = _suggestion(cid, title="A bill on the quay", turn_idx=2)
    asked = _decides(monkeypatch, 0.9, asked=[])
    scripted(story_planner=[_refusal(first["uid"]),
                            lambda p: _refusal(p["task"]["proposals"][0]["uid"])])
    assert _wait(sp.schedule_room_work(_beat(temp_db, cid, 3))).state == "done"
    assert rp.follow_up_turn(cid, None) == 3
    for idx in (4, 5, 6):                          # nothing pending: nothing asked
        sp.schedule_room_work(_beat(temp_db, cid, idx))
    assert len(asked) == 1
    second = _suggestion(cid, title="A bell in the fog", turn_idx=6)
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, 7)))
    assert job.key == sp.DIRECTION_JOB_KEY and job.state == "done", (job.state, job.error)
    request = asked[-1]
    assert list(request["questions"]) == ["near:" + second["uid"]]
    assert "(beat 7)" in request["state"]
    assert all("(beat %d)" % i not in request["state"] for i in (4, 5, 6))


def test_a_verdict_on_a_proposal_a_restore_rolled_back_is_skipped(temp_db, scripted):
    """(review R3-5) A verdict naming a proposal the row no longer holds -- a
    restore rolled it back while the Planner judged it -- raised a TypeError,
    failed the job and skipped the rest of the deliberation. It is skipped,
    said in the report, and the verdicts beside it land."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    stays = _suggestion(cid, title="A bill on the quay", turn_idx=2)
    ensure_checkpoint(cid, 3)
    gone = _suggestion(cid, title="A storm off the point", turn_idx=3)

    def judged_across_a_restore(_payload):
        restore_checkpoint(cid, 3)           # beat 3, which it was written from, rerolled
        return {"verdicts": [
            {"proposal_uid": gone["uid"], "verdict": "refuse", "reason": "No storm.",
             "contradiction": "calm sea"},
            {"proposal_uid": stays["uid"], "verdict": "refuse",
             "reason": "No creditor keeps an office here.", "contradiction": "no creditor"}],
            "reply": "Neither fits."}
    scripted(story_planner=[judged_across_a_restore])
    report = sp.deliberate(cid, None, [gone, stays], turn_idx=2)
    assert report["vanished"] == [gone["uid"]] and report["refused"] == [stays["uid"]]
    assert rp.get_proposal(cid, None, gone["uid"]) is None
    assert rp.get_proposal(cid, None, stays["uid"])["status"] == "refused"


def test_a_beat_is_read_once_narrated_and_only_when_the_decision_model_answered(
        temp_db, scripted, monkeypatch):
    """(review R3-6) The turn row exists from the moment the player sends a
    line, so a follow-up that came round while the beat ran read the line
    alone and marked the beat read: its narration was never asked about. A
    failed decision call marked its beats read too. A beat is read once it is
    narrated, and counts as read only once the decision model answered."""
    from llm import decisions
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    first = _suggestion(cid, title="A bill on the quay", turn_idx=2)
    second = _suggestion(cid, title="A bell in the fog", turn_idx=2)
    rp.mark_due(cid, None, {first["uid"]: "asked"})
    asked = _hears(monkeypatch, "the bell", [])
    started, release = threading.Event(), threading.Event()
    scripted(story_planner=[_held(started, release, _refusal(first["uid"])),
                            _refusal(second["uid"])])
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job.key == sp.DIRECTION_JOB_KEY and started.wait(5)
    # Beat 4's line is sent while the judging runs; nothing has narrated it.
    tid = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                     "VALUES(?,?,?,?)", (cid, 4, "I listen.", time.time()))
    release.set()
    assert _wait(job).state == "done", (job.state, job.error)
    assert rp.follow_up_turn(cid, None) == 3
    assert not any("I listen." in s for s in asked)
    # Its narration lands and the beat commits: asked about now.
    sid = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                     (tid, "narrator", "Narrator", 9))
    temp_db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
               (sid, json.dumps({"prose": "Out in the fog, the bell tolls (beat 4)."}),
                time.time()))
    again = _wait(sp.schedule_room_work(_beat(temp_db, cid, 4)))
    assert again.result["due"] == {second["uid"]: "touched"}
    assert "> I listen.\nOut in the fog, the bell tolls (beat 4)." in asked[-1]
    # A decision call that fails reads nothing: its beat is asked with the next.
    _suggestion(cid, title="A lamp at the window", turn_idx=4)
    _decides(monkeypatch, decisions.DecisionError("jev 503: unavailable"))
    failed = _wait(sp.schedule_room_work(_beat(temp_db, cid, 5)))
    assert failed.result["decision"] == "unavailable"
    assert rp.follow_up_turn(cid, None) == 4
    retried = _decides(monkeypatch, 0.1, asked=[])
    assert _wait(sp.schedule_room_work(_beat(temp_db, cid, 6))).state == "done"
    assert "(beat 5)" in retried[-1]["state"] and "(beat 6)" in retried[-1]["state"]
    assert rp.follow_up_turn(cid, None) == 6


def test_a_failed_pass_hands_back_the_players_ask_and_waits_its_pacing(
        temp_db, scripted):
    """(review R3-7) A pass that took the player's ask and whose provider
    then failed dropped the ask for good: asks were handed back only on a
    cancel, so nothing waited and the next commit queued nothing. It is
    handed back; and so a dead provider is not asked at every commit, a pass
    takes it up again at the pacing -- the default pace when the passes are
    off -- or when the player asks again."""
    from core import jobs
    cid = _story(temp_db)

    def provider_down(_payload):
        raise RuntimeError("HTTP 402 in_flight_budget_exhausted")
    script = scripted(
        story_planner=[{"reply": "The Dramaturge is thinking about it.",
                        "to_dramaturge": "A complication at the quay, please."}],
        dramaturge=[provider_down, {"none_needed": True, "note": "Answered at last."}])
    sp.planner_reply(cid, None, "Give me a complication.")
    job = _wait(_pass_job(cid))
    assert job.state == "failed" and "402" in job.error
    [waiting] = rp.waiting_briefs(cid, None)
    assert waiting["text"] == "A complication at the quay, please."
    assert waiting["failed_turn"] == 2
    assert "dramaturge" not in [m["role"] for m in room.messages(cid, None)]
    pace = md.BEATS_PER_PROPOSAL
    for idx in range(3, 2 + pace):                 # not at every commit
        assert sp.schedule_room_work(_beat(temp_db, cid, idx)) is None, idx
    # With the passes off it waits the default pace; asked again, it is due.
    assert not rp.briefs_due(cid, None, 1 + pace, 0)
    assert rp.briefs_due(cid, None, 2 + pace, 0)
    again = _wait(sp.schedule_room_work(_beat(temp_db, cid, 2 + pace)))
    assert again.key == sp.DRAMATURGE_JOB_KEY and again.state == "done", (
        again.state, again.error)
    assert script.payloads["dramaturge"][-1]["player_asks"] == \
        "A complication at the quay, please."
    assert room.messages(cid, None)[-1]["text"] == "Answered at last."
    assert rp.waiting_briefs(cid, None) == []
    rp.hand_back_briefs(cid, None, ["Another ask."], failed_turn=2 + pace)
    assert not rp.briefs_due(cid, None, 2 + pace, pace)
    rp.ask_brief(cid, None, "Another ask.", turn_idx=2 + pace)     # asked again
    assert rp.briefs_due(cid, None, 2 + pace, pace)
    jobs.drain(timeout=5.0)


def test_the_status_line_never_says_nothing_is_in_motion_beside_a_suggestion(
        temp_db, scripted):
    """(review R3-8) A pacing pass files its suggestion and writes no line,
    and with no line standing the row read "The room has nothing in
    motion." beside the suggestion it listed in motion -- for up to two
    pacing intervals, judging being lazy. The row says something is in
    motion while something is, and nothing when nothing is."""
    from core import jobs
    cid = _story(temp_db)
    scripted(dramaturge=[{"proposals": [{
        "kind": "pressure", "title": "A bill on the quay",
        "wants_true": "A creditor's bill is nailed at the quay.",
        "why_now": "The player keeps to the waterfront."}],
        "note": "Something gathers at the waterline."}])
    job = _wait(sp.schedule_room_work(_beat(temp_db, cid, md.BEATS_PER_PROPOSAL)))
    assert job.state == "done", (job.state, job.error)
    status = room.status(cid, None)
    assert status["in_motion"] and status["line"] != sp.NO_STATUS_LINE
    assert status["line"] == sp.IN_MOTION_LINE
    assert sp.write_status(cid, None, line=sp.NO_STATUS_LINE)["line"] == sp.IN_MOTION_LINE
    [prop] = rp.proposals(cid, None)
    rp.settle_proposal(cid, None, prop["uid"], "withdrawn")
    status = sp.write_status(cid, None)
    assert status["in_motion"] == [] and status["line"] == sp.NO_STATUS_LINE
    jobs.drain(timeout=5.0)


def test_both_packs_ask_whether_the_story_nears_a_suggestion():
    """The follow-up's question is a card in both packs, as the engine's other
    decision-model questions are (`jev_questions.direction_neared`), with the
    suggestion's title, what it wants true and why now filled in."""
    from llm.prompts import jev_question
    for lang in ("en", "ja"):
        text = jev_question("direction_neared", lang, title="TITLE",
                            wants_true="WANTS", why_now="WHY")
        assert "TITLE" in text and "WANTS" in text and "WHY" in text, lang
        assert "{" not in text, lang
    assert ("Does the passage bring the story near what this direction is about?"
            in jev_question("direction_neared", "en"))


def test_both_cards_say_the_dramaturge_needs_no_grant():
    """The Planner's card told it to ask how much the player wanted to be
    surprised instead of handing the brief whenever no grant carried the
    dial -- the same gate as the code, in words. Both packs, the keys
    verbatim (the protocol guard in `make structure` holds the same spans)."""
    from llm.prompts import get_prompt
    planner = {lang: get_prompt("story_planner", lang) for lang in ("en", "ja")}
    dramaturge = {lang: get_prompt("dramaturge", lang) for lang in ("en", "ja")}
    assert "no grant carries the dial" not in planner["en"]
    assert "Asking it needs no grant" in planner["en"]
    # The old instruction in Japanese, both halves of it: hand the brief only
    # under a dial, and otherwise ask how much they want to be surprised
    # (review F9: the token checks below would pass with it back in place).
    assert "驚きのダイヤルを含む権限委任があるときは" not in planner["ja"]
    assert "どれだけ驚かされたいかをプレイヤーに尋ねてください" not in planner["ja"]
    assert "依頼に権限委任は要らず" in planner["ja"]
    for lang in ("en", "ja"):
        for token in ('"to_dramaturge"', '"surprise"'):
            assert token in planner[lang], (lang, token)
        for token in ('"dial"', '"pacing_beats"', '"player_asks"'):
            assert token in dramaturge[lang], (lang, token)
    assert "the middle of the scale until they do" in dramaturge["en"]


def _cards(name):
    from llm.prompts import get_prompt
    return {lang: get_prompt(name, lang) for lang in ("en", "ja")}


def test_the_dramaturge_card_reads_player_asks_as_the_planners_brief():
    """(review F7) `player_asks` is the Planner's `to_dramaturge`, not the
    player's line: read as their own words, any constraint the Planner added
    became the player's stated target, which the low end of the dial holds
    the Dramaturge to. Their own words are in the room's conversation."""
    card = _cards("dramaturge")
    assert "is what the player asked the room for in words" not in card["en"]
    assert "the Story Planner's brief of what the player asked the room for" in card["en"]
    assert "the player's own words are in the room's conversation" in card["en"]
    assert "それがプレイヤーが言葉でルームに求めたことです" not in card["ja"]
    assert "ストーリープランナーがまとめた依頼" in card["ja"]
    assert "プレイヤー自身の言葉はルームの会話にあります" in card["ja"]


def test_the_dramaturge_card_files_one_direction_once():
    """The first live pass (Brackwater, 2026-10-08) filed one direction
    twice: the coat's unopened pockets as a pressure, then as a revelation.
    Kind-and-title identity cannot see that, so the card states the class."""
    card = _cards("dramaturge")
    assert ("Each proposal is a different direction: one circumstance seen two "
            "ways is one proposal, filed once, under the kind that fits it best."
            in card["en"])
    assert "提案はそれぞれ別の方向です。ひとつの状況を二通りに見たものはひとつの提案" in card["ja"]


def test_the_planner_card_asks_for_the_grant_and_opens_no_package_it_cannot_validate():
    """(review F3) Accepting is judging and carrying out is acting: when the
    standing grants do not cover what an accepted proposal needs, the
    Planner asks for that grant by name and opens no package that cannot
    validate. `_retire_stranded` is the floor under the clause."""
    card = _cards("story_planner")
    assert ("when they do not cover what carrying it out would need, accept it "
            "all the same, ask the player in \"questions\" for that grant by name, "
            "and open no package that cannot validate" in card["en"])
    assert "検証を通りえないパッケージは開かないでください" in card["ja"]
    assert '"questions" でプレイヤーに求め' in card["ja"]


def test_the_planner_card_says_a_player_can_turn_the_suggestions_off():
    """(review F8) A grant is the player's one way to stop the Dramaturge's
    own passes, and it needs no capability: the Planner is told so."""
    card = _cards("story_planner")
    assert '"beats_per_proposal" 0 in its limits, with no capability needed' in card["en"]
    assert '"beats_per_proposal" を 0 にし、能力は要りません' in card["ja"]


# ---------------------------------------------------------------------------
# The firewall
# ---------------------------------------------------------------------------

def test_neither_agent_reaches_a_mind(temp_db, scripted, monkeypatch):
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
    # And the deliberation the follow-up runs over it, the decision model's
    # question included: author work, read by no mind. Asked of the beat
    # played after the suggestion (review R3-4).
    _decides(monkeypatch, 0.9)
    _beat(temp_db, cid, 3)
    follow = sp.run_direction_follow_up(cid, None)
    assert follow["deliberations"] and follow["due"]
    assert snapshot() == before
    assert "smuggler" not in json.dumps(room.status(cid, None)).casefold()
    assert "smuggler" not in json.dumps(temp_db.wget(cid, "scene")).casefold()


def test_the_new_fixed_lines_are_in_both_catalogs():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    en = json.loads((root / "language_packs" / "en" / "ui.json").read_text("utf-8"))
    ja = json.loads((root / "language_packs" / "ja" / "ui.json").read_text("utf-8"))
    script = (root / "static" / "js" / "writers_room.js").read_text("utf-8")
    for line in (sp.SPENT_LINE, sp.HOUR_SPENT_LINE, sp.DISAGREEMENT_LINE,
                 sp.IN_MOTION_LINE):
        assert line in en and line in script
        assert ja.get(line) not in (None, line)
