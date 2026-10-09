"""A reroll gives the Writers' Room back the turn it took from a discarded beat.

The review of 2026-10-08 (round 4, R4-1 and R4-2 and its probes A-G3) found
the Room losing work across a reroll in ordinary timing: a Dramaturge pass
that had read the next beat lost its suggestion while its pacing stayed
spent, an asked pass lost the player's ask, a spared deliberation returned
as a disagreement what it had accepted, and a follow-up kept a reading whose
conclusion was rolled back. Each case below is one of those timings.
"""
from __future__ import annotations

import json
import threading
import time

from story import mandates as md
from story import room_conversation as room
from story import room_proposals as rp
from agents import dramaturge as dg
from agents import story_planner as sp

from tests.test_dramaturge import (_beat, _blocked, _held, _hears, _job, _narrate,
                                   _no_pacing_pass, _pass_job, _refusal, _story,
                                   _suggestion, _wait, scripted)  # noqa: F401

ASK = "A complication at the quay, please."
COAT = {"kind": "pressure", "title": "The coat's pockets",
        "wants_true": "The coat holds a second receipt.",
        "why_now": "The player keeps the coat close."}
BILL = {"kind": "pressure", "title": "A bill on the quay",
        "wants_true": "A creditor's bill is nailed at the quay.", "why_now": "Asked."}


def _line(db, cid, idx, line="I check the coat."):
    """The player sends beat ``idx``'s line: the row stands, nothing has
    answered it yet."""
    return db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                 (cid, idx, line, time.time()))


def _lore_then(held_events=None):
    """A first step that looks up lore, held until released."""
    started, release = held_events or (threading.Event(), threading.Event())

    def step(_payload):
        started.set()
        release.wait(5)
        return {"calls": [{"tool": "search_lore", "args": {"query": "coat"}}]}
    return step, started, release


def _pacing_story(db):
    cid = _story(db)
    for idx in range(3, md.BEATS_PER_PROPOSAL):
        _beat(db, cid, idx)
    return cid


# ---------------------------------------------------------------------------
# A beat in play is not read
# ---------------------------------------------------------------------------

def test_a_line_still_being_answered_is_neither_read_nor_counted(temp_db):
    """The turn row stands from the moment the player sends a line; until
    the narrator answers it the beat is in play. The stream leaves it out,
    line and read horizon alike, and a pass is recorded at the beat before
    it. A beat further down that ended with no narration is kept."""
    from core import jobs
    cid = _story(temp_db)                                   # beats 0-2, narrated
    _line(temp_db, cid, 3)
    assert [b["beat"] for b in dg.player_visible_stream(cid, None)] == [0, 1, 2]
    assert dg.newest_answered_beat(cid, None) == 2
    job = jobs.Job(cid, "probe", 0)
    dg.player_visible_stream(cid, None, job=job)
    assert job.read_turn == 2
    _beat(temp_db, cid, 4)                                  # the next beat answered
    assert [b["beat"] for b in dg.player_visible_stream(cid, None)][-2:] == [3, 4]
    assert dg.newest_answered_beat(cid, None) == 4


def test_a_pacing_pass_that_saw_the_next_beats_line_keeps_its_suggestion(
        temp_db, scripted):
    """(probe G) The pacing pass at beat 6 looks up lore first, and the player
    sends beat 7's line meanwhile. Its second step read that line and so read
    beat 7 -- and the reroll of beat 7, which keeps the line, dropped the
    suggestion and left the pacing spent. It read beat 6, files from it, and
    the reroll keeps what it filed: the pass had its turn."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _pacing_story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    step1, s1, r1 = _lore_then()
    scripted(dramaturge=[step1, {"proposals": [COAT],
                                 "note": "Something gathers at the waterline."}])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert job.key == sp.DRAMATURGE_JOB_KEY and s1.wait(5)
    ensure_checkpoint(cid, pace + 1)
    _line(temp_db, cid, pace + 1)                           # the player starts beat 7
    r1.set()
    assert _wait(job).state == "done", (job.state, job.error)
    assert job.read_turn == pace
    restore_checkpoint(cid, pace + 1)                       # beat 7 rerolled
    [kept] = rp.proposals(cid, None)
    assert kept["title"] == "The coat's pockets" and kept["filed_turn"] == pace
    assert rp.last_pass_turn(cid, None) == pace
    assert rp.pass_due(cid, None, pace + 1, pace)[0] is False
    jobs.drain(timeout=5.0)


def test_a_pass_running_at_the_reroll_of_a_line_it_never_read_is_spared(
        temp_db, scripted):
    """(probe G2) As above, with the reroll arriving while the second step
    thinks: the pass read only beat 6, so the restore spares it, and what it
    files after the restore stands -- the pacing it spent is spent."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _pacing_story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    step1, s1, r1 = _lore_then()
    s2, r2 = threading.Event(), threading.Event()

    def step2(_payload):
        s2.set()
        r2.wait(5)
        return {"proposals": [COAT], "note": "Something gathers at the waterline."}
    scripted(dramaturge=[step1, step2])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert job.key == sp.DRAMATURGE_JOB_KEY and s1.wait(5)
    ensure_checkpoint(cid, pace + 1)
    _line(temp_db, cid, pace + 1)
    r1.set()
    assert s2.wait(5)
    restore_checkpoint(cid, pace + 1)
    assert not job.cancelled.is_set() and jobs.spared(job)
    r2.set()
    assert _wait(job).state == "done", (job.state, job.error)
    [kept] = rp.proposals(cid, None)
    assert kept["filed_turn"] == pace
    assert rp.last_pass_turn(cid, None) == pace
    jobs.drain(timeout=5.0)


# ---------------------------------------------------------------------------
# A pass that read a discarded beat gives its turn back
# ---------------------------------------------------------------------------

def test_a_pass_whose_answer_was_read_from_a_rerolled_beat_gives_its_turn_back(
        temp_db, scripted):
    """(R4-1) Beat 7 is played to its narration while the pacing pass looks
    up lore, and the pass's second step reads it: its suggestion is about
    beat 7, and a reroll of beat 7 drops it. The pass's turn goes with it,
    so the replayed beat is asked again, as itself; kept, the record stood
    and the story waited a whole interval for its next suggestion."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _pacing_story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    step1, s1, r1 = _lore_then()
    scripted(dramaturge=[step1, {"proposals": [COAT],
                                 "note": "Something gathers at the waterline."}])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert job.key == sp.DRAMATURGE_JOB_KEY and s1.wait(5)
    ensure_checkpoint(cid, pace + 1)
    _beat(temp_db, cid, pace + 1)                           # beat 7, narrated
    r1.set()
    assert _wait(job).state == "done", (job.state, job.error)
    [filed] = rp.proposals(cid, None)
    assert filed["filed_turn"] == pace + 1 and job.read_turn == pace + 1
    restore_checkpoint(cid, pace + 1)                       # beat 7 rerolled
    assert rp.proposals(cid, None) == []
    assert rp.last_pass_turn(cid, None) is None             # the story's first pass
    assert rp.pass_due(cid, None, pace + 1, pace)[0]
    scripted(dramaturge=[{"none_needed": True, "note": "Quiet, for now."}])
    again = sp.schedule_room_work(_beat(temp_db, cid, pace + 1))   # the replay
    assert again is not None and again.key == sp.DRAMATURGE_JOB_KEY
    assert _wait(again).state == "done", (again.state, again.error)
    assert rp.last_pass_turn(cid, None) == pace + 1
    jobs.drain(timeout=5.0)


def test_a_pass_the_reroll_cancels_before_it_answers_gives_its_turn_back(
        temp_db, scripted):
    """(R4-1, probe G2's narrated timing) The second step has read beat 7's
    narration when beat 7 is rerolled: the pass is cancelled and files
    nothing. Its record was made before the snapshot, so the restore left it
    standing; the pass gives it back as it hands back an ask."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _pacing_story(temp_db)
    pace = md.BEATS_PER_PROPOSAL
    step1, s1, r1 = _lore_then()
    s2, r2 = threading.Event(), threading.Event()

    def step2(_payload):
        s2.set()
        r2.wait(5)
        return {"proposals": [COAT], "note": "Something gathers at the waterline."}
    scripted(dramaturge=[step1, step2])
    job = sp.schedule_room_work(_beat(temp_db, cid, pace))
    assert job.key == sp.DRAMATURGE_JOB_KEY and s1.wait(5)
    ensure_checkpoint(cid, pace + 1)
    _beat(temp_db, cid, pace + 1)
    r1.set()
    assert s2.wait(5) and job.read_turn == pace + 1
    restore_checkpoint(cid, pace + 1)
    assert job.cancelled.is_set() and job.cancelled_from == pace + 1
    r2.set()
    _wait(job)
    assert rp.proposals(cid, None) == []
    assert rp.last_pass_turn(cid, None) is None
    assert rp.pass_due(cid, None, pace + 1, pace)[0]
    jobs.drain(timeout=5.0)


def test_a_turn_given_back_before_the_restore_stays_given_back(temp_db):
    """The cancelled pass's give-back can land before the restore's own
    transaction. The restore starts from the log as it stood, so the entry
    the snapshot still holds does not come back with it."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    first = rp.record_pass(cid, None, 0)
    rp.land_pass(cid, None, first["pass"], 0)
    second = rp.record_pass(cid, None, 2)                   # running at the snapshot
    ensure_checkpoint(cid, 3)
    _beat(temp_db, cid, 3)
    assert rp.give_back_pass(cid, None, second["pass"])
    restore_checkpoint(cid, 3)
    assert rp.last_pass_turn(cid, None) == 0
    assert [e["pass"] for e in rp._row(cid, None)["pass_log"]] == [first["pass"]]
    assert not rp.give_back_pass(cid, None, second["pass"])   # once is all


def test_a_pass_log_reads_a_row_written_before_it_was_kept(temp_db):
    """A row from before the log reads as its one recorded pass, and a pass
    recorded on it is numbered past it."""
    from core.db import wset_for_frame
    cid = _story(temp_db)
    wset_for_frame(cid, rp.PROPOSALS_KEY,
                   {"proposals": [], "last_pass_turn": 4, "passes": 3}, None)
    assert rp.last_pass_turn(cid, None) == 4
    assert rp._row(cid, None)["pass_log"] == [{"pass": 3, "turn": 4, "read": None}]
    entry = rp.record_pass(cid, None, 6)
    assert entry["pass"] == 4 and rp.last_pass_turn(cid, None) == 6


# ---------------------------------------------------------------------------
# The player's ask
# ---------------------------------------------------------------------------

def test_an_ask_whose_answer_was_read_from_a_rerolled_beat_waits_again(
        temp_db, scripted):
    """(R4-1, probe G3) The pass the player asked for reads beat 3, played
    while it looked up lore, and answers from it. The reroll of beat 3
    drops the answer, and the ask -- the conversation's, its answer gone --
    waits again, due at once; it used to be answered in the thread and gone
    from the room."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    step1, s1, r1 = _lore_then()
    judging, judged = threading.Event(), threading.Event()
    scripted(story_planner=[{"reply": "The Dramaturge is thinking about it.",
                             "to_dramaturge": ASK},
                            _held(judging, judged, lambda p: _refusal(
                                p["task"]["proposals"][0]["uid"],
                                "Judged off the discarded beat."))],
             dramaturge=[step1, {"proposals": [BILL], "note": "A creditor, perhaps."}])
    sp.planner_reply(cid, None, "Give me a complication.")
    assert s1.wait(5)
    ensure_checkpoint(cid, 3)
    _beat(temp_db, cid, 3)                                  # beat 3, narrated
    r1.set()
    assert _wait(_pass_job(cid)).state == "done"
    [filed] = rp.proposals(cid, None)
    assert filed["filed_turn"] == 3 and rp.answered_asks(filed) == [ASK]
    assert judging.wait(5)
    follow = _job(cid, sp.DIRECTION_JOB_KEY)
    restore_checkpoint(cid, 3)                              # beat 3 rerolled
    judged.set()
    _wait(follow)
    assert rp.proposals(cid, None) == []
    assert [b["text"] for b in rp.waiting_briefs(cid, None)] == [ASK]
    assert rp.briefs_due(cid, None, 3, md.BEATS_PER_PROPOSAL)
    jobs.drain(timeout=5.0)


def test_a_suggestion_that_stands_answers_the_ask_its_cancelled_pass_took(
        temp_db, scripted):
    """(probe F) The asked pass files its suggestion from beat 2, then reads
    beat 3 and is cancelled by its reroll. The suggestion stands -- filed
    from a kept beat -- due as asked, and the ask is not handed back as well:
    it was answered twice, at the cost of a pass and a deliberation. The
    pass's turn stands with it."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    s1, r1, s2, r2 = (threading.Event() for _ in range(4))

    def step1(_payload):
        s1.set()
        r1.wait(5)
        return {"proposals": [BILL],
                "calls": [{"tool": "search_lore", "args": {"query": "creditor"}}],
                "note": "A creditor, perhaps."}

    def step2(_payload):
        s2.set()
        r2.wait(5)
        return {"note": "Still thinking.", "none_needed": True}
    scripted(story_planner=[{"reply": "The Dramaturge is thinking about it.",
                             "to_dramaturge": ASK}],
             dramaturge=[step1, step2])
    sp.planner_reply(cid, None, "Give me a complication.")
    assert s1.wait(5)
    ensure_checkpoint(cid, 3)
    _beat(temp_db, cid, 3)
    r1.set()
    assert s2.wait(5)
    job = _pass_job(cid)
    restore_checkpoint(cid, 3)
    r2.set()
    _wait(job)
    [kept] = rp.proposals(cid, None)
    assert kept["filed_turn"] == 2 and kept["due"] == "asked"
    assert rp.waiting_briefs(cid, None) == []
    assert rp.last_pass_turn(cid, None) == 2
    jobs.drain(timeout=5.0)


def test_an_ask_made_again_while_a_failing_pass_runs_is_due_at_once(
        temp_db, scripted):
    """(probe D) The player asks again, in the same words, while the pass
    that took the first ask is failing. The failed copy was put in front of
    the fresh one, carrying the failed beat, and the player's new ask waited
    a pacing interval behind it. The fresh ask stands as asked."""
    from core import jobs
    cid = _story(temp_db)
    entered, release = threading.Event(), threading.Event()

    def provider_down(_payload):
        entered.set()
        release.wait(5)
        raise RuntimeError("HTTP 402 in_flight_budget_exhausted")
    scripted(story_planner=[{"reply": "Thinking.", "to_dramaturge": ASK},
                            {"reply": "Thinking again.", "to_dramaturge": ASK}],
             dramaturge=[provider_down])
    sp.planner_reply(cid, None, "Give me a complication.")
    assert entered.wait(5)
    sp.planner_reply(cid, None, "Give me a complication, please!")
    release.set()
    _wait(_pass_job(cid))
    [waiting] = rp.waiting_briefs(cid, None)
    assert waiting["text"] == ASK and "failed_turn" not in waiting
    assert rp.briefs_due(cid, None, 3, md.BEATS_PER_PROPOSAL)
    jobs.drain(timeout=5.0)


# ---------------------------------------------------------------------------
# The deliberation and the follow-up
# ---------------------------------------------------------------------------

def test_a_spared_deliberation_never_returns_what_it_had_concluded(
        temp_db, scripted, monkeypatch):
    """(R4-2, probe E) A follow-up queued at beat 3 judges two suggestions.
    Round 1 accepts the first while beat 4 is in play; during round 2 the
    player rerolls beat 4. The job read only beat 3, so the restore spares
    it, and rolls the acceptance back -- a verdict that acted is not kept.
    The end of the rounds returned that suggestion to the player as a
    disagreement the room never had. It stays pending, to be judged again."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    p = _suggestion(cid, title="A bill on the quay", turn_idx=2)
    q = _suggestion(cid, title="A bell in the fog", turn_idx=2)
    rp.mark_due(cid, None, {p["uid"]: "asked", q["uid"]: "asked"})
    s1, r1, s2, r2 = (threading.Event() for _ in range(4))
    scripted(story_planner=[
        _held(s1, r1, {"verdicts": [{"proposal_uid": p["uid"], "verdict": "accept",
                                     "reason": "A creditor posts bills."}],
                       "reply": "The bill fits the quay."}),
        _held(s2, r2, _refusal(q["uid"]))])
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job.key == sp.DIRECTION_JOB_KEY and s1.wait(5)
    ensure_checkpoint(cid, 4)
    _beat(temp_db, cid, 4)
    r1.set()
    assert s2.wait(5)
    assert rp.get_proposal(cid, None, p["uid"])["status"] == "accepted"
    restore_checkpoint(cid, 4)
    assert not job.cancelled.is_set()
    r2.set()
    assert _wait(job).state == "done", (job.state, job.error)
    row = rp.get_proposal(cid, None, p["uid"])
    texts = [m["text"] for m in room.messages(cid, None)]
    assert row["status"] in rp.PENDING_STATUSES
    assert sp.DISAGREEMENT_LINE not in texts
    assert not any(qn["source"] == "engine" and "return" in qn["text"].casefold()
                   for qn in room.status(cid, None)["questions"])


def test_a_reroll_of_the_next_beat_has_the_follow_up_read_again(
        temp_db, scripted, monkeypatch):
    """(probe A) A busy follow-up reads beat 4 -- which brings the story near
    the second suggestion -- only after beat 5 has started, marks it, takes
    it, and is cancelled by the reroll of beat 5. The restore kept the
    reading and rolled back what it concluded, so beat 4 was never asked
    about again and the suggestion waited its bound. The reading goes with
    its conclusion; the replayed commit reads beat 4 again and judges it."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    cid = _story(temp_db)
    _no_pacing_pass(monkeypatch)
    first = _suggestion(cid, title="A bill on the quay", turn_idx=2)
    second = _suggestion(cid, title="A bell in the fog", turn_idx=2)
    rp.mark_due(cid, None, {first["uid"]: "asked"})
    _hears(monkeypatch, "bell tolls", [])
    s1, r1, s2, r2 = (threading.Event() for _ in range(4))
    scripted(story_planner=[_held(s1, r1, _refusal(first["uid"])),
                            _held(s2, r2, _refusal(second["uid"],
                                                   "Judged off beat five."))])
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job.key == sp.DIRECTION_JOB_KEY and s1.wait(5)
    ctx4 = _beat(temp_db, cid, 4)
    _narrate(temp_db, cid, 4, "Out in the fog, the bell tolls (beat 4).")
    assert sp.schedule_room_work(ctx4) is job
    ensure_checkpoint(cid, 5)
    tid5 = _line(temp_db, cid, 5, "I listen.")
    r1.set()
    assert s2.wait(5)
    assert rp.follow_up_turn(cid, None) == 4
    sid = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                     (tid5, "narrator", "Narrator", 9))
    temp_db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
               (sid, json.dumps({"prose": "Gulls over the quay (beat 5)."}), time.time()))
    restore_checkpoint(cid, 5)
    r2.set()
    assert _wait(job).state == "cancelled", (job.state, job.error)
    assert rp.follow_up_turn(cid, None) != 4
    _narrate(temp_db, cid, 5, "Gulls over the quay (beat 5, played again).")
    scripted(story_planner=[_refusal(second["uid"])])
    again = sp.schedule_room_work(_beat(temp_db, cid, 5))
    assert again is not None
    _wait(again)
    assert rp.get_proposal(cid, None, second["uid"])["status"] == "refused"


def test_a_spared_asked_pass_leaves_its_judging_to_the_replayed_commit(
        temp_db, scripted, monkeypatch):
    """(probe B) The player's ask is in the Dramaturge's hands while beat 3
    is played and rerolled; the pass read only beat 2, so it is spared, and
    it files during the replay. It queued a FRESH follow-up for its answer,
    which carried no read limit and read beat 3's old narration -- the
    discarded one. It queues none: what it filed waits due as asked, and the
    replayed beat's commit has it judged, reading the beat as replayed."""
    from core import jobs
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    began = time.time()
    cid = _story(temp_db)
    _suggestion(cid, title="A bell in the fog", turn_idx=2)
    asked = _hears(monkeypatch, "bell tolls", [])
    slow, started, release = _blocked("A creditor, perhaps.", dict(BILL))
    scripted(story_planner=[
        {"reply": "The Dramaturge is thinking about it.", "to_dramaturge": ASK},
        lambda p: {"verdicts": [{"proposal_uid": x["uid"], "verdict": "refuse",
                                 "reason": "no", "contradiction": "x"}
                                for x in p["task"]["proposals"]], "reply": "No."}],
        dramaturge=[slow])
    sp.planner_reply(cid, None, "Give me a complication.")
    assert started.wait(5)                                  # read through beat 2
    ensure_checkpoint(cid, 3)
    _beat(temp_db, cid, 3)
    _narrate(temp_db, cid, 3, "Out in the fog, the bell tolls (beat 3, as first played).")
    restore_checkpoint(cid, 3)
    pass_job = _pass_job(cid)
    assert not pass_job.cancelled.is_set() and jobs.spared(pass_job)
    release.set()
    assert _wait(pass_job).state == "done", (pass_job.state, pass_job.error)
    assert pass_job.result["deliberation"] == "due"
    # Job history is the process's, and chat ids restart with each database.
    assert not [j for j in jobs.active_jobs(cid) + list(jobs.history(cid))
                if j.key == sp.DIRECTION_JOB_KEY and j.submitted >= began]
    [bill] = [p for p in rp.proposals(cid, None) if p["title"] == "A bill on the quay"]
    assert bill["due"] == "asked"
    _narrate(temp_db, cid, 3, "Out in the fog, the bell tolls (beat 3, played again).")
    follow = sp.schedule_room_work(_beat(temp_db, cid, 3))  # the replayed commit
    assert follow is not None and follow.key == sp.DIRECTION_JOB_KEY
    assert _wait(follow).state == "done", (follow.state, follow.error)
    assert rp.get_proposal(cid, None, bill["uid"])["status"] == "refused"
    assert not any("as first played" in s for s in asked)
    jobs.drain(timeout=5.0)
