"""The Writers' Room's fill asks only what is missing, and asks it once
(`story/room_frontier.py`, `agents/story_planner.py`).

Measured on the Brackwater run (chat 166, 2026-10-07): 21 background fill
jobs made 371 model calls (9.50M prompt tokens, 2.10M response, 11,881 s),
a fill was in flight at every kept commit from turn 6 to turn 30, 17 of the
21 had no open planning need, and nothing any of them made reached a page or
a mind. The frontier read SHORT when nothing was missing:

* at the tide chapel every room within two hops had been furnished, and the
  measure counted only the plan's unfurnished stubs -- two rooms short;
* on the Grebe under way the deck was joined to nothing (the vessel stood in
  no room) -- two rooms short of a room that has no way out;
* in a town whose five charters held 45 named people it counted only the one
  unrendered authored plan -- one person short.

And the commit tail re-asked the same unchanged question every beat, so the
Room answered "nothing to build" again and again. Replayed on the run's own
checkpoints (turns 6-30) the corrected measure reads 0/0 on every one, and a
fill is wanted only while the run's one need, `need_f545555c7f7a2326`, is open
(filed at turn 16, filled at turn 24).
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from core.db import wget_for_frame, wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm import providers
from story import mandates as md
from story import room_frontier as rf
from agents import story_planner as sp

PLAYER = "The Stranger"


def _story(db, rooms=None, positions=None, *, turns=3, entities=None):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Fill gate", "A port at dusk.", time.time()))
    wset(cid, "scene", {"location": "Port", "rooms": rooms or {
        "quay": {"name": "Quay", "desc": "Wet stone and rope.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates to the rafters.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"},
                                   {"to": "loft", "barrier": "open"}]},
        "loft": {"name": "Loft", "desc": "Sacking and dust.",
                 "adjacent": [{"to": "warehouse", "barrier": "open"}]},
    }, "positions": positions or {PLAYER: "quay"}, "entities": entities or {},
        "attire": {}})
    turn_id = None
    for i in range(turns):
        turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                        "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    return cid, turn_id


def _town(db, cid, bodies):
    """A charter, stored and read back through the engine's own reader."""
    db.wset(cid, "charters", {"items": {"harbour_office": {"state": {
        "bodies": bodies}}}})


def _beat(db, cid, idx):
    """The commit of beat ``idx``: its turn row is the newest, as it is when
    the commit tail runs in play."""
    row = db.q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (cid, idx),
               one=True)
    turn_id = row["id"] if row else db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=cid, name="Fill gate", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx, player_input="",
                      created=time.time(), frame_id=None),
        cast=[], input="")


class Script:
    """The stubbed Planner: one scripted answer per call, every payload kept."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.payloads = []

    def __call__(self, role, system, user, **kw):
        self.payloads.append(json.loads(user))
        if not self.steps:
            return json.dumps({"reply": "Nothing to build this pass."})
        step = self.steps.pop(0)
        return json.dumps(step(self.payloads[-1]) if callable(step) else step)


@pytest.fixture
def scripted(monkeypatch):
    def install(*steps):
        script = Script(*steps)
        monkeypatch.setattr(providers, "chat_complete", script)
        return script
    return install


def _wait(job, seconds=15.0):
    deadline = time.time() + seconds
    while job.state in ("pending", "running") and time.time() < deadline:
        time.sleep(0.02)
    assert job.state == "done", (job.state, job.error)
    return job


def _grant_fills(cid):
    return md.grant_mandate(cid, None, text="Fill in what the story needs.",
                            capabilities=["identity_fills", "plan_entity",
                                          "create_people", "close_need"])


# ---------------------------------------------------------------------------
# The measure: a shortfall is something missing, never something finished
# ---------------------------------------------------------------------------

def test_a_furnished_room_within_reach_is_ready_ahead(temp_db):
    """The tide chapel: every room in reach furnished, none a stub. The old
    measure read that as two rooms short; a furnished room is the most
    prepared a room can be."""
    cid, _ = _story(temp_db)
    report = rf.frontier_report(cid, None)
    assert report["reachable"] == ["loft", "warehouse"]
    assert report["rooms_ahead"] == []          # no stub stands ahead...
    assert report["rooms_short"] == 0           # ...and nothing is missing


def test_the_frontier_is_not_short_when_its_rooms_and_people_are_there(temp_db):
    """Rooms in reach and a town full of people: no shortfall of either.
    A charter's people are counted when they could still be met -- named,
    living, not departed, not on stage now (`leased`), and not an authored
    person's own body (that person is the cast's)."""
    cid, _ = _story(temp_db)
    _town(temp_db, cid, {
        "b1": {"name": "Tamsin Rook", "place": "quay"},
        "b2": {"name": "Ada Kell", "place": "warehouse"},
        "b3": {"name": "Odo Pell", "place": "quay", "condition": "dead"},
        "b4": {"name": "Wen Hale", "place": "quay", "departed": True},
        "b5": {"name": "Ivo Marsh", "place": "quay", "leased": "scene"},
        "b6": {"name": "Mara Quill", "place": "quay",
               "resident_seed_id": "cast:7"},
    })
    report = rf.frontier_report(cid, None)
    assert report["rooms_short"] == 0
    assert report["bodies_ahead"] == {"harbour_office": 2}
    assert report["identities_ahead"] == []     # no authored plan stands ahead...
    assert report["identities_short"] == 0      # ...and the town has its people


def test_one_unmet_plan_in_a_peopled_town_is_not_a_shortfall(temp_db):
    """Brackwater's turns 23-30: one unrendered plan (Selwick) in a town of
    45 named people read one person short, and the Room said "nothing to
    build" to it twice."""
    from world.planned_entities import add_planned_entity
    cid, _ = _story(temp_db)
    add_planned_entity(cid, {"kind": "person", "name": "Selwick",
                             "brief": {"where": "warehouse"}})
    assert rf.frontier_report(cid, None)["identities_short"] == 1
    _town(temp_db, cid, {"b1": {"name": "Tamsin Rook", "place": "quay"}})
    report = rf.frontier_report(cid, None)
    assert report["identities_ahead"] == ["Selwick"]
    assert report["identities_short"] == 0


def test_an_exit_into_nothing_is_the_room_the_frontier_is_short_of(temp_db):
    cid, _ = _story(temp_db, rooms={
        "quay": {"name": "Quay", "desc": "Wet stone.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"},
                              {"to": "the_far_stair", "barrier": "open"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    })
    report = rf.frontier_report(cid, None)
    assert report["rooms_unheld"] == ["the_far_stair"]
    assert report["rooms_short"] == rf.FRONTIER_ROOMS_MIN - 1


def test_no_way_out_is_not_a_room_shortfall(temp_db):
    """The Grebe, turns 16-22: the player on the deck of a boat that stood
    in no room, so nothing was in reach. No package can plan rooms "ahead"
    of a room with no way out; what the story reached for there was already
    a planning need."""
    cid, _ = _story(temp_db, rooms={
        "deck": {"name": "Deck", "desc": "Tarred planks.",
                 "parent_entity": "the_boat", "adjacent": []},
        "channel": {"name": "Channel", "desc": "Black water.", "adjacent": []},
    }, positions={PLAYER: "deck"},
        entities={"the_boat": {"name": "the boat", "kind": "vehicle",
                               "interior_rooms": ["deck"]}})
    report = rf.frontier_report(cid, None)
    assert report["player_room"] == "deck" and report["player_holder"] == "the_boat"
    assert report["reachable"] == [] and report["rooms_short"] == 0
    assert report["rooms_unmeasured"] == "no way out of the player's room"


def test_a_player_in_no_room_has_nothing_ahead_to_measure(temp_db):
    cid, _ = _story(temp_db, positions={"Somebody Else": "quay"})
    report = rf.frontier_report(cid, None)
    assert report["player_room"] is None and report["rooms_short"] == 0
    assert report["rooms_unmeasured"] == "the player stands in no room"


# ---------------------------------------------------------------------------
# The gate: a question is asked once, then backs off
# ---------------------------------------------------------------------------

def test_a_fill_is_not_asked_again_while_its_question_is_unchanged(
        temp_db, scripted):
    """Nothing changed since the fill answered "nothing to build": the next
    commit queues nothing, and the back-off decides when it is asked again."""
    from core import jobs
    cid, _ = _story(temp_db)                # no plan, no town: people short
    _grant_fills(cid)
    script = scripted({"reply": "Nothing to build this pass."})
    job = sp.schedule_room_work(_beat(temp_db, cid, 2))
    assert job is not None and job.key == sp.FILL_JOB_KEY
    _wait(job)
    assert job.result["published"] == []
    assert len(script.payloads) == 1
    assert script.payloads[0]["task"]["kind"] == "fill"
    memo = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fill_memo"]
    assert [(m["turn"], m["misses"]) for m in memo] == [(2, 1)]
    # The same question at the same commit and one beat later: nothing is
    # queued and nothing is spent (the fill's model is never called).
    assert sp.schedule_room_work(_beat(temp_db, cid, 2)) is None
    assert sp.schedule_room_work(_beat(temp_db, cid, 3)) is None
    assert len(script.payloads) == 1
    # The back-off has run: the same question is asked again.
    job = sp.schedule_room_work(_beat(temp_db, cid, 2 + rf.FILL_RETRY_BEATS))
    assert job is not None and job.key == sp.FILL_JOB_KEY
    _wait(job)
    assert len(script.payloads) == 2
    jobs.drain(timeout=1.0)


def test_a_new_need_or_a_new_player_room_asks_the_fill_again(temp_db, scripted):
    from core import jobs
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db)
    _grant_fills(cid)
    script = scripted()                     # every answer: nothing to build
    _wait(sp.schedule_room_work(_beat(temp_db, cid, 2)))
    assert sp.schedule_room_work(_beat(temp_db, cid, 3)) is None
    # A beat reaches for something no plan holds: a new question, asked at
    # once, with the need in the task.
    need, _ = file_planning_need(cid, {"kind": "thing",
                                       "surface": {"name": "the sealed letter"}})
    job = sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert job is not None
    _wait(job)
    assert [n["uid"] for n in script.payloads[-1]["task"]["needs"]] == [need["uid"]]
    assert sp.schedule_room_work(_beat(temp_db, cid, 3)) is None
    # The player walks on: a new room is a new question.
    scene = temp_db.wget(cid, "scene")
    scene["positions"][PLAYER] = "warehouse"
    temp_db.wset(cid, "scene", scene)
    job = sp.schedule_room_work(_beat(temp_db, cid, 4))
    assert job is not None
    _wait(job)
    assert script.payloads[-1]["task"]["frontier"]["player_room"] == "warehouse"
    assert len(script.payloads) == 3
    jobs.drain(timeout=1.0)


def test_a_new_grant_is_a_new_question():
    report = {"open_need_uids": ["need_a"], "player_room": "quay",
              "rooms_short": 0, "identities_short": 1}
    assert rf.fill_signature(report, ["m1"]) == rf.fill_signature(report, ["m1"])
    assert rf.fill_signature(report, ["m1"]) != rf.fill_signature(report, ["m1", "m2"])
    # Which stubs or plans stand ahead is not the question; whether anything
    # is missing is.
    assert rf.fill_signature(dict(report, identities_ahead=["Abel Gale"]), ["m1"]) \
        == rf.fill_signature(report, ["m1"])
    assert rf.fill_signature(dict(report, identities_short=0), ["m1"]) \
        != rf.fill_signature(report, ["m1"])


def test_an_empty_answer_backs_off_longer_and_an_open_need_is_still_asked(temp_db):
    """Each consecutive answer that landed nothing doubles the wait, up to a
    ceiling -- so an open need keeps being asked for as long as it is open,
    less often the longer the Room has nothing for it, never not at all."""
    cid, _ = _story(temp_db)
    sig = "a" * 16
    assert rf.fill_due(cid, None, sig, 5) == (True, "")
    waits = []
    turn = 5
    for _ in range(6):
        rf.record_fill_asked(cid, None, sig, turn_idx=turn, published=False)
        wait = rf.fill_wait_beats(
            wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fill_memo"][-1]["misses"])
        waits.append(wait)
        due, why = rf.fill_due(cid, None, sig, turn + wait - 1)
        assert not due and "next ask at beat %d" % (turn + wait) in why
        assert rf.fill_due(cid, None, sig, turn + wait)[0]
        turn += wait
    assert waits == [rf.FILL_RETRY_BEATS, 2 * rf.FILL_RETRY_BEATS,
                     4 * rf.FILL_RETRY_BEATS, 8 * rf.FILL_RETRY_BEATS,
                     rf.FILL_RETRY_BEATS_CAP, rf.FILL_RETRY_BEATS_CAP]
    # An answer that landed something ends the run of empty ones.
    rf.record_fill_asked(cid, None, sig, turn_idx=turn, published=True)
    assert rf.fill_due(cid, None, sig, turn + rf.FILL_RETRY_BEATS)[0]
    assert not rf.fill_due(cid, None, sig, turn + rf.FILL_RETRY_BEATS - 1)[0]


def test_a_question_asked_in_a_timeline_the_story_left_is_asked_again(temp_db):
    cid, _ = _story(temp_db)
    rf.record_fill_asked(cid, None, "b" * 16, turn_idx=9, published=False)
    assert rf.fill_due(cid, None, "b" * 16, 5) == (True, "")


def test_a_failed_fill_is_an_empty_answer_for_the_back_off(temp_db, monkeypatch):
    """The Brackwater fill F18 ended on HTTP 402. A failure re-asked on the
    very next commit is what an exhausted provider makes expensive."""
    cid, _ = _story(temp_db)
    _grant_fills(cid)

    def _dead(*a, **k):
        raise RuntimeError("HTTP 402: insufficient credit")
    monkeypatch.setattr(sp, "_run_task", _dead)
    with pytest.raises(RuntimeError, match="402"):
        sp.run_fill(cid, None, base_turn=2)
    memo = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fill_memo"]
    assert [m["misses"] for m in memo] == [1]


def test_a_fill_cancelled_before_it_ran_is_not_an_answer(temp_db, scripted):
    """A job cancelled before its first pass ran nothing: it is filed as a
    cancellation with nothing published, and the memo learns nothing from
    it. `_run_task` used to fall out of its loop holding None and fail the
    job on `out["passes"]`."""
    cid, _ = _story(temp_db)
    _grant_fills(cid)
    script = scripted()

    class _Cancelled:
        cancelled = threading.Event()
    _Cancelled.cancelled.set()
    out = sp._run_task(cid, None, {"kind": "fill", "needs": []}, base_turn=2,
                       job=_Cancelled())
    assert out["stopped"] == "cancelled" and out["published"] == []
    assert out["passes"] == 0
    result = sp.run_fill(cid, None, base_turn=2, job=_Cancelled())
    assert result["stopped"] == "cancelled" and result["published"] == []
    assert script.payloads == []
    assert "fill_memo" not in wget_for_frame(cid, rf.FRONTIER_KEY, None, {})


def test_the_memo_forgets_the_oldest_question_past_its_cap(temp_db):
    cid, _ = _story(temp_db)
    for n in range(rf.FILL_MEMO_KEPT + 3):
        rf.record_fill_asked(cid, None, "%016x" % n, turn_idx=n, published=False)
    memo = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fill_memo"]
    assert len(memo) == rf.FILL_MEMO_KEPT
    assert memo[0]["sig"] == "%016x" % 3 and memo[-1]["sig"] == "%016x" % (
        rf.FILL_MEMO_KEPT + 2)


# ---------------------------------------------------------------------------
# The ledger: a write made inside another writer's window survives it
# ---------------------------------------------------------------------------

def test_the_ledger_keeps_a_write_made_inside_another_writers_window(
        temp_db, monkeypatch):
    """Four writers share the `room_frontier` row -- the commit tail's
    measure, the fill, the Dramaturge pass and the panel's reply -- from
    four threads. A writer that read before another's write and saved after
    it erased it. Here the measure holds its read open while a spend lands
    from another thread: both survive, because the spend waits for the
    measure's write instead of being overwritten by it."""
    cid, _ = _story(temp_db)
    reading, release = threading.Event(), threading.Event()
    real_row = rf._row

    def slow_row(cid_, frame_id):
        row = real_row(cid_, frame_id)
        if threading.current_thread().name == "measure":
            reading.set()
            release.wait(5.0)
        return row

    monkeypatch.setattr(rf, "_row", slow_row)
    measure = threading.Thread(
        name="measure", target=rf.record_measure,
        args=(cid, None, {"rooms_short": 0, "identities_short": 0}),
        kwargs={"turn_idx": 4})
    measure.start()
    assert reading.wait(5.0)
    spend = threading.Thread(
        name="spend", target=rf.record_spend, args=(cid, None),
        kwargs={"turn_idx": 4, "calls": 7, "who": "planner"})
    spend.start()
    time.sleep(0.5)                 # the spend now waits on the measure
    release.set()
    measure.join(5.0)
    spend.join(5.0)
    assert not measure.is_alive() and not spend.is_alive()
    row = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})
    assert row["measured_turn"] == 4
    assert [s["calls"] for s in row.get("spend") or []] == [7]


# ---------------------------------------------------------------------------
# The card says what a fill is, in both packs
# ---------------------------------------------------------------------------

def test_the_planner_card_says_what_a_fill_is_in_both_packs():
    """`fill` appeared nowhere in the Planner's card, and three Brackwater
    fills (28 calls) answered the player's turn-4 line all over again."""
    from llm.prompts import get_prompt
    en = get_prompt("story_planner", "en")
    ja = get_prompt("story_planner", "ja")
    assert "THE FILL." in en and "is not answered again" in en
    # The keys the task carries, verbatim in both packs (the protocol guard
    # in `make structure` holds the same spans).
    for token in ('"fill"', '"needs"', '"frontier"', '"rooms_short"',
                  '"identities_short"', '"bodies_ahead"'):
        assert token in en and token in ja, token


def test_a_bubbles_commit_neither_measures_nor_fills(temp_db, monkeypatch):
    """A live causality bubble's commit runs the commit tail too. Its scene
    is cut to its own subjects, so the frontier read "the player stands in
    no room", overwrote the era's measure and asked the era's open needs
    under a second signature with a back-off of its own (review of the
    2026-10-08 landing). The player frame's commit asks; the bubble's does
    not."""
    import world.spatial_frames as spatial_frames
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db, positions={PLAYER: "quay"})
    _grant_fills(cid)
    file_planning_need(cid, {"kind": "thing",
                             "surface": {"name": "the sealed letter"}})
    bubble = temp_db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) VALUES(?,?,?,?,?)",
        (cid, "away", 1, "spatial", time.time()))
    measured = []
    monkeypatch.setattr(rf, "record_measure",
                        lambda *a, **k: measured.append(a))
    beat = _beat(temp_db, cid, 2)
    ctx = PipelineContext(chat=beat.chat, cast=[], input="", turn=TurnData(
        id=beat.turn.id, chat_id=cid, idx=2, player_input="",
        created=time.time(), frame_id=bubble))
    # The same commit in the player's frame would queue the fill.
    monkeypatch.setattr(spatial_frames, "is_bubble_frame", lambda c, f: False)
    assert sp.schedule_room_work(ctx) is not None and measured
    from core import jobs
    jobs.drain(timeout=5.0)
    measured.clear()
    monkeypatch.setattr(spatial_frames, "is_bubble_frame", lambda c, f: True)
    assert sp.schedule_room_work(_beat_in(ctx, 3)) is None
    assert measured == []


def _beat_in(ctx, idx):
    """`ctx`'s frame, one beat on."""
    return PipelineContext(chat=ctx.chat, cast=[], input="", turn=TurnData(
        id=ctx.turn.id, chat_id=ctx.chat.id, idx=idx, player_input="",
        created=time.time(), frame_id=ctx.turn.frame_id))


def test_a_bubbles_beats_do_not_shorten_the_back_off(temp_db):
    """Turn rows are numbered across the chat, and a live bubble inserts its
    beats into that numbering: counted as this frame's beats, they ran the
    wait down early, and a fill answered after a bubble's row was filed
    above the player's own beat."""
    cid, _ = _story(temp_db)
    bubble = temp_db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) VALUES(?,?,?,?,?)",
        (cid, "away", 1, "spatial", time.time()))
    sig = "c" * 16
    rf.record_fill_asked(cid, None, sig, turn_idx=5, published=True)
    for idx, frame in ((6, bubble), (7, None)):
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                   "VALUES(?,?,?,?,?)", (cid, idx, "", time.time(), frame))
    # Two chat-wide beats since the answer, one of them the bubble's.
    assert not rf.fill_due(cid, None, sig, 7)[0]
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
               (cid, 8, "", time.time()))
    assert rf.fill_due(cid, None, sig, 8)[0]
    # The frame's own newest beat, never the bubble's row above it.
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
               "VALUES(?,?,?,?,?)", (cid, 9, "", time.time(), bubble))
    assert rf.frame_turn_idx(cid, None) == 8
    assert rf.frame_turn_idx(cid, bubble) == 9
