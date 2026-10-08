"""Planting ahead is one compact call that files light plans, and the full
Planner keeps every question a sketch cannot answer (`story/room_sketch.py`,
`agents/story_planner.run_fill`).

The owner, 2026-10-08: "Can we do lighter weight planning potentially? And
save heavy plans for when the actors near them?" -- and the same day, "We
aren't trying to remove functionality, just make it more efficient." A fill
job on the Brackwater run averaged about 17 model calls, 77% of its steps
re-reading the world. A planting-only question (no need open, no player's
line waiting) is now ONE call handed everything it may use, which answers
with rooms, people and -- only when granted and paced -- one local event
near the actors; code checks every name, join, room and grant and files one
package through the plot-package machinery. Whatever the sketch cannot say,
whatever code refuses and whatever does not validate goes to the full loop,
with the reason.
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
                ("Sketch", "A port at dusk.", time.time()))
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
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    return cid


def _beat(db, cid, idx):
    row = db.q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (cid, idx),
               one=True)
    turn_id = row["id"] if row else db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=cid, name="Sketch", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx, player_input="",
                      created=time.time(), frame_id=None),
        cast=[], input="")


def _grant(cid, *caps, limits=None):
    return md.grant_mandate(cid, None, text="Plan ahead of me: %s." % ", ".join(caps),
                            capabilities=list(caps), limits=limits)


PLANTING = ("identity_fills", "plan_rooms", "plan_entity", "create_people")


class Script:
    """The stubbed model: a sketch's call (`payload["kind"] == "sketch"`) is
    answered by ``sketch``, the full loop's calls by ``steps`` in order;
    every payload, role and argument is kept."""

    def __init__(self, *steps, sketch=None):
        self.steps = list(steps)
        self.sketch = sketch
        self.payloads = []
        self.calls = []

    def __call__(self, role, system, user, **kw):
        payload = json.loads(user)
        self.payloads.append(payload)
        self.calls.append({"role": role, "system": system, **kw})
        if isinstance(payload, dict) and payload.get("kind") == "sketch":
            answer = self.sketch if self.sketch is not None else {
                "reply": "Nothing would fit this story ahead yet."}
            return json.dumps(answer(payload) if callable(answer) else answer)
        if not self.steps:
            return json.dumps({"reply": "Nothing to build this pass."})
        step = self.steps.pop(0)
        return json.dumps(step(payload) if callable(step) else step)


@pytest.fixture
def scripted(monkeypatch):
    def install(*steps, sketch=None):
        script = Script(*steps, sketch=sketch)
        monkeypatch.setattr(providers, "chat_complete", script)
        return script
    return install


def _wait(job, seconds=15.0):
    deadline = time.time() + seconds
    while job.state in ("pending", "running") and time.time() < deadline:
        time.sleep(0.02)
    assert job.state == "done", (job.state, job.error)
    return job


def _fill(db, cid, beat):
    """The fill beat ``beat``'s commit queued, run to its end; None when
    the commit queued none."""
    job = sp.schedule_room_work(_beat(db, cid, beat))
    if job is None or job.key != sp.FILL_JOB_KEY:
        return None
    return _wait(job)


def _sketches(script):
    return [p for p in script.payloads if p.get("kind") == "sketch"]


def _loops(script):
    return [p for p in script.payloads if (p.get("task") or {}).get("kind") == "fill"]


def _packages(cid, status=None):
    from story.plot_packages import list_packages
    return [p for p in list_packages(cid) if status is None or p["status"] == status]


ROOMS = [{"name": "Ropewalk", "purpose": "where rope is laid out along the quay",
          "joins": "quay", "way": "a gap between the stacked nets"},
         {"name": "Chandlery", "purpose": "tar, twine and lamp oil for the boats",
          "joins": "Warehouse", "way": "a low door"}]
PEOPLE = [{"name": "Orrin Vane", "role": "ropemaker", "where": "Ropewalk"},
          {"name": "Bel Harrow", "role": "chandler", "where": "chandlery",
           "look": "tar to the elbows"}]


# ---------------------------------------------------------------------------
# One call, one package
# ---------------------------------------------------------------------------

def test_a_planting_question_is_one_call_that_files_one_package(temp_db, scripted):
    """A developed area short of rooms and people: one model call, handed
    the ground within reach, the counts and the grants, answers with light
    plans, and code files them as ONE published package -- the plans stand
    ahead, the fill counts on the planting line, the question backs off as
    answered, and the reply is the Planner's line in the thread."""
    from story import room_conversation as room
    from world.planned_entities import planned_entities
    cid = _story(temp_db)
    _grant(cid, *PLANTING)
    # JSON's null written out as a word, as a model that quotes every value
    # writes it, is an empty field: no open exit to fill, no look, no ask.
    script = scripted(sketch={"rooms": [dict(ROOMS[0], fills="null", vertical="null"),
                                        ROOMS[1]],
                              "people": [dict(PEOPLE[0], look="null"), PEOPLE[1]],
                              "event": None, "escalate": "null",
                              "title": "The rope and the tar",
                              "reply": "Two working rooms off the quay, and "
                                       "the two who keep them."})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch" and job.result["calls"] == 1
    assert len(script.payloads) == 1 and _loops(script) == []
    shown = script.payloads[0]
    assert [r["id"] for r in shown["area"]["rooms"]] == ["quay", "loft", "warehouse"]
    assert shown["area"]["rooms"][0]["state"] == "here"
    assert shown["frontier"]["rooms_short"] == rf.FRONTIER_ROOMS_MIN
    assert shown["frontier"]["identities_short"] == rf.FRONTIER_IDENTITIES_MIN
    assert shown["granted"] == {"rooms": True, "people": True, "harm": False}
    assert shown["event"]["may"] is False
    published = _packages(cid, "published")
    assert len(published) == 1 and published[0]["title"] == "The rope and the tar"
    assert published[0]["operations"] == ["plan_rooms", "plan_entity", "plan_entity"]
    report = rf.frontier_report(cid, None)
    assert report["rooms_ahead"] == ["chandlery", "ropewalk"]
    assert report["rooms_short"] == 0 and report["identities_short"] == 0
    plans = {p["name"]: p for p in planned_entities(cid, None).values()}
    assert plans["Orrin Vane"]["brief"]["where"] == "ropewalk"
    assert not plans["Orrin Vane"].get("look")
    assert plans["Bel Harrow"]["brief"]["where"] == "chandlery"
    row = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})
    assert row["fills"][-1]["needs"] == [] and rf.fills_this_hour(cid, None, 2) == 1
    # Filed as answered: the question asked, and the one the frontier was
    # left at -- the question the next commit would compute.
    assert [m["misses"] for m in row["fill_memo"]] == [0, 0]
    assert row["spend"][-1]["who"] == "sketch" and row["spend"][-1]["calls"] == 1
    assert room.messages(cid, None)[-1]["text"].startswith("Two working rooms")
    # Nothing is short now: the next commit asks nothing at all.
    assert _fill(temp_db, cid, 3) is None


def test_a_sketch_that_planted_part_of_what_was_short_waits_out_the_back_off(
        temp_db, scripted):
    """A sketch is one call, so no later pass re-measures the frontier: the
    question it LEFT -- rooms planted, people still short -- is filed with
    its answer (review 2026-10-08, R2-3), and the next commit waits out the
    back-off rather than asking at once a question whose answer just came.
    Filed under the question it was asked alone, the moved shortfall read as
    a new question and the next commit asked a second sketch straight
    away."""
    cid = _story(temp_db)
    _grant(cid, *PLANTING)
    script = scripted(sketch={"rooms": ROOMS,
                              "reply": "Two working rooms off the quay."})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch" and job.result["published"]
    report = rf.frontier_report(cid, None)
    assert report["rooms_short"] == 0
    assert report["identities_short"] == rf.FRONTIER_IDENTITIES_MIN
    script.sketch = None                    # from here: nothing would fit
    assert _fill(temp_db, cid, 3) is None
    assert len(_sketches(script)) == 1
    job = _fill(temp_db, cid, 2 + rf.FILL_RETRY_BEATS)
    assert job is not None and job.result["tier"] == "sketch"
    assert len(_sketches(script)) == 2


def test_the_sketch_rides_the_planners_role_at_no_heavier_than_low_effort(
        temp_db, scripted, monkeypatch):
    """The sketch reuses the Story Planner's role and routing and asks it
    for `SKETCH_REASONING_EFFORT` as a CEILING: a heavier or unset role is
    asked for low, a lighter one keeps its own."""
    from story import room_sketch
    cid = _story(temp_db)
    _grant(cid, *PLANTING)
    script = scripted()
    _fill(temp_db, cid, 2)
    assert script.calls[0]["role"] == sp.PLANNER_ROLE
    assert script.calls[0]["reasoning_effort"] == room_sketch.SKETCH_REASONING_EFFORT
    for own, asked in (("", "low"), ("medium", "low"), ("high", "low"),
                       ("low", "low"), ("minimal", "minimal"), ("off", "off")):
        monkeypatch.setattr(providers, "reasoning_effort_for", lambda role, o=own: o)
        assert room_sketch.sketch_effort(sp.PLANNER_ROLE) == asked, own


# ---------------------------------------------------------------------------
# Escalation keeps every capability
# ---------------------------------------------------------------------------

def test_a_sketch_that_says_escalate_hands_the_question_to_the_full_loop(
        temp_db, scripted):
    """The sketch knows what it cannot say: it plans nothing, says why, and
    the full loop takes the same question with the reason in its task."""
    cid = _story(temp_db)
    _grant(cid, *PLANTING)
    why = "the warehouse wants its guild, with posts and people"
    script = scripted(sketch={"escalate": why})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "escalated" and job.result["escalated"] == why
    assert len(_sketches(script)) == 1
    assert _loops(script)[0]["task"]["escalated"] == why
    assert _packages(cid, "published") == []
    memo = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fill_memo"]
    assert [m["misses"] for m in memo] == [1]


def test_what_code_refuses_in_a_sketch_goes_to_the_full_loop_and_lands_nothing(
        temp_db, scripted):
    """Every name, join and room is checked before anything is drafted: a
    person under a name the world holds, or a room joined to a room out of
    reach, refuses the WHOLE sketch -- a package lands all of it or none --
    and the loop takes the question with the reasons. A sketch whose
    package does not validate is retired with the reason and handed on the
    same way."""
    from story.plot_packages import get_package
    from world.planned_entities import add_planned_entity
    from world.structure import plant_structure
    cid = _story(temp_db)
    add_planned_entity(cid, {"kind": "person", "name": "Selwick",
                             "brief": {"where": "warehouse"}})
    plant_structure(cid, {"key": "port", "name": "Port"}, {
        "far_light": {"name": "Far Light", "adjacent": [{"to": "pier_end"}]},
        "pier_end": {"name": "Pier End", "adjacent": [{"to": "far_light"}]}})
    _grant(cid, *PLANTING, "arrival")
    script = scripted(sketch={
        "rooms": [{"name": "Lamp Store", "purpose": "oil for the far light",
                   "joins": "far_light", "way": "a ladder"}],
        "people": [{"name": "Selwick", "role": "clerk", "where": "quay"}]})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "escalated"
    reason = _loops(script)[0]["task"]["escalated"]
    assert "'Selwick' is a name the world already holds" in reason
    assert "'Lamp Store' joins 'far_light', which is not a room within reach" in reason
    assert _packages(cid) == [] or all(p["status"] != "published" for p in _packages(cid))
    # A sketch that passes code and fails the package's own validation.
    cid = _story(temp_db)
    _grant(cid, *PLANTING, "arrival")
    script = scripted(sketch={"event": {"op": "arrival", "who": "Nobody Known",
                                        "room": "quay"}})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "escalated"
    assert "the package does not validate" in _loops(script)[0]["task"]["escalated"]
    [retired] = _packages(cid)
    assert retired["status"] == "retired"
    history = get_package(cid, retired["uid"])["provenance"]["history"]
    assert "sketch handed to the full planner" in history[-1]["note"]


def test_an_open_need_or_a_waiting_player_line_takes_the_full_loop(
        temp_db, scripted):
    """The sketch is for planting ahead and nothing else: a question with a
    need open, or with the player's line waiting unanswered in the thread,
    is the full loop's, exactly as before."""
    from story import room_conversation as room
    from world.planning_needs import close_planning_need, file_planning_need
    cid = _story(temp_db)
    _grant(cid, *PLANTING, "close_need")
    script = scripted()
    _fill(temp_db, cid, 2)
    assert len(_sketches(script)) == 1 and _loops(script) == []
    need, _ = file_planning_need(cid, {"kind": "thing",
                                       "surface": {"name": "the sealed letter"}})
    job = _fill(temp_db, cid, 3)
    assert job.result["tier"] == "loop" and len(_sketches(script)) == 1
    assert [n["uid"] for n in _loops(script)[-1]["task"]["needs"]] == [need["uid"]]
    close_planning_need(cid, need["uid"], "the story moved on")
    room.add_message(cid, None, "player", "Is there a way down to the water?",
                     turn_idx=4)
    job = _fill(temp_db, cid, 4 + rf.FILL_RETRY_BEATS)
    assert job.result["tier"] == "loop" and len(_sketches(script)) == 1


def test_a_shortfall_the_grants_keep_from_a_sketch_goes_straight_to_the_full_loop(
        temp_db, scripted):
    """The frontier is short of rooms and the standing grants allow people
    and events but not rooms: a sketch could not answer the shortfall, so
    the question goes to the loop -- which may plant what it can and ask the
    player for the rest, as it always could -- without the call. A local
    event the grants allow is never the reason a sketch runs."""
    from world.planned_entities import add_planned_entity
    cid = _story(temp_db)
    for name in ("Selwick", "Abel Gale"):           # rooms short, people not
        add_planned_entity(cid, {"kind": "person", "name": name,
                                 "brief": {"where": "warehouse"}})
    _grant(cid, "identity_fills", "plan_entity", "create_people",
           "schedule_event")
    script = scripted()
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "escalated" and _sketches(script) == []
    reason = _loops(script)[0]["task"]["escalated"]
    assert "short of rooms" in reason and "grants" in reason


def test_a_sketch_answer_that_cannot_be_read_goes_to_the_full_loop(
        temp_db, scripted):
    """A field the card shapes as a list of objects that arrives as
    anything else is refused, never read as nothing planned -- and an
    answer carrying none of the keys is no answer at all."""
    cid = _story(temp_db)
    _grant(cid, *PLANTING)
    script = scripted(sketch={"rooms": {"Ropewalk": {"joins": "quay"}}})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "escalated"
    assert "'rooms' could not be read" in _loops(script)[0]["task"]["escalated"]
    cid = _story(temp_db)
    _grant(cid, *PLANTING)
    script = scripted(sketch={"calls": [{"tool": "inspect_rooms"}]})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "escalated"
    assert "could not be read" in _loops(script)[0]["task"]["escalated"]


# ---------------------------------------------------------------------------
# What a sketched room joins
# ---------------------------------------------------------------------------

def test_a_sketched_room_fills_an_open_exit_rather_than_standing_beside_it(
        temp_db, scripted):
    """An exit that leads nowhere is shown to the sketch as an open exit of
    its room, and a place that takes it is planted under the exit's own id
    -- the way that led nowhere now leads there -- never as a second room
    beside the hole."""
    cid = _story(temp_db, rooms={
        "quay": {"name": "Quay", "desc": "Wet stone.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"},
                              {"to": "the_far_stair", "barrier": "open"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    })
    _grant(cid, *PLANTING)
    script = scripted(sketch={"rooms": [
        {"name": "The Far Stair", "purpose": "worn steps down to the mud",
         "joins": "quay", "way": "worn steps", "vertical": "down",
         "fills": "the_far_stair"}]})
    _fill(temp_db, cid, 2)
    quay = next(r for r in script.payloads[0]["area"]["rooms"] if r["id"] == "quay")
    assert quay["open_exits"] == ["the_far_stair"]
    report = rf.frontier_report(cid, None)
    assert "rooms_unheld" not in report
    assert report["rooms_ahead"] == ["the_far_stair"]


# ---------------------------------------------------------------------------
# Local events: granted, paced, near the actors
# ---------------------------------------------------------------------------

def test_a_sketched_event_is_granted_paced_and_near_the_actors(temp_db, scripted):
    """The owner: "The planner is also supposed to plan events locally to
    some level to keep things interesting if allowed." The sketch is offered
    the local-drama kinds the grants allow, places one near the people of
    the story, and files it beside the plans; the next is not offered for
    `LOCAL_EVENT_BEATS` of this frame's beats, and one planned anyway is
    left out while the rest lands. An event out of reach of everybody in
    the story is refused, and the question goes to the loop."""
    from story.plot_packages import get_package
    cid = _story(temp_db)
    _grant(cid, *PLANTING, "schedule_event", "arrival")
    event = {"op": "schedule_event", "room": "warehouse",
             "summary": "a bell starts ringing on the warehouse roof"}
    script = scripted(sketch={"rooms": ROOMS[:1], "event": event})
    job = _fill(temp_db, cid, 2)
    shown = script.payloads[0]["event"]
    assert shown["may"] is True and set(shown["kinds"]) == {"arrival", "schedule_event"}
    assert "clock" not in shown["kinds"]["arrival"]
    assert "due_in_turns?" in shown["kinds"]["arrival"]
    assert shown["where"][0] == "quay"
    assert job.result["event"] == "schedule_event"
    [pkg] = _packages(cid, "published")
    ops = get_package(cid, pkg["uid"])["operations"]
    assert [op["op"] for op in ops] == ["plan_rooms", "schedule_event"]
    assert ops[1]["summary"].endswith("(at Warehouse)")
    assert rf.sketched_event_wait(cid, None, 2) == rf.LOCAL_EVENT_BEATS
    # Within the pacing window -- the question's own back-off run, the
    # event's not -- not offered, and one planned anyway is left out while
    # the room lands.
    later = 2 + rf.FILL_RETRY_BEATS
    assert later - 2 < rf.LOCAL_EVENT_BEATS
    script.sketch = {"rooms": [{"name": "Net Loft", "purpose": "nets mended",
                                "joins": "loft", "way": "a hatch"}],
                     "event": event}
    job = _fill(temp_db, cid, later)
    assert script.payloads[-1]["event"]["may"] is False
    assert job.result["event"] is None and job.result["published"]
    assert any("left out" in note for note in job.result["notes"])
    # Out of reach of everybody: refused, handed on.
    cid = _story(temp_db)
    from world.structure import plant_structure
    plant_structure(cid, {"key": "port", "name": "Port"}, {
        "chandlery": {"name": "Chandlery", "adjacent": [{"to": "loft"}]},
        "far_light": {"name": "Far Light", "adjacent": [{"to": "chandlery"}]}})
    _grant(cid, *PLANTING, "schedule_event")
    script = scripted(sketch={"event": dict(event, room="far_light")})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "escalated"
    assert "not within" in _loops(script)[0]["task"]["escalated"]


def test_a_harmful_event_needs_its_own_grant(temp_db, scripted):
    """Harm is an act, not a flag (`plot_packages.operation_harms`): an
    incident that names somebody hurt is offered its `harms` field only
    under `schedule_harm`, refused without it, and filed with it."""
    from story.plot_packages import get_package
    harm = {"op": "incident", "room": "quay", "summary": "a stack of nets falls",
            "shock": 0, "harms": [{"charter": "harbour_office", "body": "b1",
                                   "outcome": "hurt"}]}
    for granted in (False, True):
        cid = _story(temp_db)
        temp_db.wset(cid, "charters", {"items": {"harbour_office": {"state": {
            "bodies": {"b1": {"name": "Tamsin Rook", "place": "quay"}}}}}})
        _grant(cid, *PLANTING, "incident", *(["schedule_harm"] if granted else []))
        script = scripted(sketch={"event": harm})
        job = _fill(temp_db, cid, 2)
        offered = script.payloads[0]["event"]["kinds"]["incident"]
        assert ("harms?" in offered) is granted
        if granted:
            [pkg] = _packages(cid, "published")
            assert get_package(cid, pkg["uid"])["authority"]["may_schedule_harm"]
        else:
            assert job.result["tier"] == "escalated"
            assert "harm" in _loops(script)[0]["task"]["escalated"]


# ---------------------------------------------------------------------------
# A sketch the story moved under files nothing
# ---------------------------------------------------------------------------

def test_a_sketch_whose_job_was_cancelled_or_whose_story_rewound_files_nothing(
        temp_db, scripted):
    """The guards the loop keeps on its writes hold the sketch too: a job
    cancelled while the call ran, or a story rewound under it, lands no
    package and teaches the back-off nothing."""
    cid = _story(temp_db)
    _grant(cid, *PLANTING)

    class _Job:
        cancelled = threading.Event()

    def cancel_then_plant(payload):
        _Job.cancelled.set()
        return {"rooms": ROOMS}
    scripted(sketch=cancel_then_plant)
    out = sp.run_fill(cid, None, base_turn=2, job=_Job())
    assert out["stopped"] == "cancelled" and out["published"] == []
    assert _packages(cid) == []
    assert "fill_memo" not in wget_for_frame(cid, rf.FRONTIER_KEY, None, {})

    def rewind_then_plant(payload):
        temp_db.qi("DELETE FROM turns WHERE chat_id=? AND idx>0", (cid,))
        return {"rooms": ROOMS}
    scripted(sketch=rewind_then_plant)
    out = sp.run_fill(cid, None, base_turn=2)
    assert out["stopped"] == "rewound" and _packages(cid) == []
    assert "fill_memo" not in wget_for_frame(cid, rf.FRONTIER_KEY, None, {})


# ---------------------------------------------------------------------------
# The cards
# ---------------------------------------------------------------------------

def test_what_the_player_said_reaches_the_sketch(temp_db, scripted):
    """WHAT THE PLAYER SAID BOUNDS WHAT A SKETCH PLANS, as it bounds the full
    loop. Code checks only which capabilities are granted; a grant's scope is
    the planner's to honour. A sketch shown only the capabilities planted the
    cliff-top chapel a grant scoped to the harbour had ruled out (review of
    the 2026-10-08 landing): the grants' own words and scope, and the
    player's recent lines to the room, ride its payload."""
    from story import room_conversation as room
    cid = _story(temp_db)
    md.grant_mandate(cid, None, text="Plan ahead as I explore, but keep it to the harbour.",
                     capabilities=list(PLANTING), scope="the harbour only")
    room.add_message(cid, None, "player", "Leave the town above the cliff alone.",
                     turn_idx=1)
    # The Room answered, so no player line is waiting: the sketch takes it.
    room.add_message(cid, None, "planner", "Understood: the harbour only.", turn_idx=1)
    script = scripted(sketch={"rooms": [], "people": [], "event": None,
                              "escalate": None, "title": "Nothing past the harbour",
                              "reply": "Nothing past the harbour yet."})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch"
    said = script.payloads[0]["player_said"]
    assert {"text": "Plan ahead as I explore, but keep it to the harbour.",
            "scope": "the harbour only"} in said["grants"]
    assert said["lines"][-1] == "Leave the town above the cliff alone."


def test_the_sketch_card_states_its_answer_in_both_packs():
    """A new card in both packs, the answer's keys verbatim in each (the
    protocol guard in `make structure` holds the same spans), and the full
    Planner's card saying what a task carrying "escalated" is."""
    from llm.prompts import get_prompt
    for lang in ("en", "ja"):
        card = get_prompt("room_sketch", lang)
        for token in ('"area"', '"open_exits"', '"frontier"', '"rooms_short"',
                      '"identities_short"', '"planned_ahead"', '"reserved_names"',
                      '"voice"', '"recent"', '"granted"', '"harm"', '"player_said"', '"rooms"',
                      '"joins"', '"way"', '"fills"', '"people"', '"where"',
                      '"event"', '"may"', '"kinds"', '"due_in_turns"',
                      '"escalate"', '"reply"', '"title"'):
            assert token in card, (lang, token)
        assert '"escalated"' in get_prompt("story_planner", lang)
