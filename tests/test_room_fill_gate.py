"""The Writers' Room's fill plants ahead of a developed area, and asks each
question once (`story/room_frontier.py`, `agents/story_planner.py`).

Measured on the Brackwater run (chat 166, 2026-10-07): 21 background fill
jobs made 371 model calls (9.50M prompt tokens, 2.10M response, 11,881 s), a
fill was in flight at every kept commit from turn 6 to turn 30, and the
commit tail re-asked the same unchanged question every beat, so the Room
answered "nothing to build" again and again. The morning of 2026-10-08
answered that twice: a fill asks each question once and backs off
(`fill_signature`, `fill_due`), and the frontier stopped reading a developed
area as short -- every room the world held counted as ready and every
charter body as a person ahead -- so a fill was wanted only while the run's
one need was open (beats 16-23), and a developed area never asked the Room
to plant ahead again.

The owner restored planting ahead the same day ("I just hope we didn't
lobotomize it and remove the world's ability to be proactive"): rooms ahead
are the plan's stubs within reach, so a developed area is short of them;
people ahead are authored person plans, so a story that has met the people
planned for it is short of them; and the back-off is what holds the cost.
Replayed on the run's checkpoints with every answer landing before the next
beat, the restored gate queues 12 fills when every answer is empty and 8
when every answer publishes, against 21 in the run and 4 under the
morning's gate. Kept from the morning: an exit into nothing is short, a room
with no way out is not (the Grebe, F92), and a charter's bodies are reported
beside the count, never subtracted from it. And because a planting fill that
lands is counted in the hour, an open need is held only to the fills that
answered needs: replayed with every answer publishing, four planting fills
at beats 6-11 would otherwise have spent the hour and the run's one need
would never have been asked.

The review of that restoration found three more places where the gate broke
its own rule, each held here. A need filed while a planting fill ran was
joined to it by the next commit and carried by none of its passes, so each
pass now reads the open needs afresh. A player who kept walking re-asked a
people-only question every beat, because the question named the room and
people are counted frame-wide; the room is part of it now only while rooms
are short or a need is open. And with no fill grant the status row claimed
open planning needs when none was open; it now names what waits on the
grant, and only while it does.

The re-review found three more, held here too. A player walking a developed
area still re-asked at every step (6 fills in 7 beats), so planting ahead is
keyed without the room at all -- only an open need keeps it (R2-1). The
needs' hourly line counted fills that merely CARRIED a need, so planting
spent it; a fill's record now names only the needs its packages answered or
closed (R2-2). And the memo filed each pass's question with the frontier
the fill began with; each pass re-measures, and the question the frontier
was left at is filed with the answer (R2-3). Planting-only questions are now
asked as one sketch call (`story/room_sketch.py`,
`tests/test_planting_ahead_is_one_sketch.py`); the stub here answers a
sketch's call apart from the loop's, so a loop's script reads the same
whichever tier asks first.
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


#: What a planting sketch answers when a test wants the full loop to take
#: the question (`story/room_sketch.py`: "escalate" hands it on).
ESCALATE = {"escalate": "the story needs more here than a sketch can say"}


class Script:
    """The stubbed Planner: one scripted answer per call of the full loop,
    every payload and every call's role and arguments kept. A planting
    sketch's call (`payload["kind"] == "sketch"`) is answered by ``sketch``
    instead -- by default an answer that plants nothing -- so a loop's
    script reads the same whichever tier is asked first."""

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


def _queued_fill(ctx):
    """The fill job ``ctx``'s commit queued, or None -- whatever else the
    commit tail queued beside it (a Dramaturge pass, a bible fold)."""
    job = sp.schedule_room_work(ctx)
    return job if job is not None and job.key == sp.FILL_JOB_KEY else None


def _fill_payloads(script):
    """The payloads the stubbed model was shown by the full fill loop, and
    nothing else."""
    return [p for p in script.payloads if isinstance(p, dict)
            and (p.get("task") or {}).get("kind") == "fill"]


def _sketch_payloads(script):
    """The payloads the stubbed model was shown by a planting sketch."""
    return [p for p in script.payloads if isinstance(p, dict)
            and p.get("kind") == "sketch"]


def _asks(script):
    """One payload per time a fill was ASKED, whichever tier answered: a
    sketch's one call, or the first step of a loop that no sketch call
    came just before (a loop the grants sent straight there, or a need's)."""
    out, previous = [], None
    for p in script.payloads:
        if not isinstance(p, dict):
            continue
        task = p.get("task") or {}
        if p.get("kind") == "sketch":
            out.append(p)
        elif task.get("kind") == "fill" and not task.get("resumed") \
                and p["budget"]["step"] == 1 \
                and not (previous or {}).get("kind") == "sketch":
            out.append(p)
        previous = p
    return out


def _grant_fills(cid):
    return md.grant_mandate(cid, None, text="Fill in what the story needs.",
                            capabilities=["identity_fills", "plan_entity",
                                          "create_people", "close_need"])


def _grant_planting(cid, *more, limits=None):
    """Fills, rooms and people: what planting ahead needs."""
    return md.grant_mandate(cid, None, text="Plan ahead of me as I explore.",
                            capabilities=["identity_fills", "plan_rooms",
                                          "plan_entity", "create_people",
                                          "close_need", *more],
                            limits=limits)


# ---------------------------------------------------------------------------
# The measure: what the plan holds ahead, and a developed area is short of it
# ---------------------------------------------------------------------------

def _plant_ahead(cid, rooms):
    """Planned rooms joined to the port, as a published plan leaves them."""
    from world.structure import plant_structure
    plant_structure(cid, {"key": "port", "name": "Port"}, rooms)


def test_a_developed_area_is_short_of_rooms_ahead(temp_db):
    """The tide chapel, Brackwater beats 9-11: every room within reach
    furnished and none a stub. What stands ahead is what the plan holds and
    nobody has furnished, so a developed area is short of it -- the Room's
    prompt to plan beyond it (owner ruling, 2026-10-08) -- and the furnished
    rooms are named as the ground the plan goes on from."""
    cid, _ = _story(temp_db)
    report = rf.frontier_report(cid, None)
    assert report["reachable"] == ["loft", "warehouse"]
    assert report["rooms_ahead"] == []
    assert report["rooms_developed"] == ["loft", "warehouse"]
    assert report["rooms_short"] == rf.FRONTIER_ROOMS_MIN
    # Planned rooms beyond the developed ground answer it; one three hops
    # out does not stand within reach and does not count.
    _plant_ahead(cid, {
        "ropewalk": {"name": "Ropewalk", "adjacent": [{"to": "quay"}]},
        "chandlery": {"name": "Chandlery", "adjacent": [{"to": "warehouse"}]},
        "far_light": {"name": "Far Light", "adjacent": [{"to": "chandlery"}]},
    })
    report = rf.frontier_report(cid, None)
    assert report["rooms_ahead"] == ["chandlery", "ropewalk"]
    assert report["rooms_developed"] == ["loft", "warehouse"]
    assert report["rooms_short"] == 0


def test_a_charters_people_are_reported_and_never_stand_in_for_planned_people(
        temp_db):
    """A town's people are the offscreen simulator's. Its named, living,
    off-stage bodies are reported for the Room to weigh -- not the dead, the
    departed, a body on loan to a scene (`leased`) or an authored person's
    own body (that person is the cast's) -- and the people short are
    counted from authored person plans alone."""
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
    assert report["bodies_ahead"] == {"harbour_office": 2}
    assert report["identities_ahead"] == []
    assert report["identities_short"] == rf.FRONTIER_IDENTITIES_MIN


def test_one_unmet_plan_in_a_peopled_town_is_one_person_short(temp_db):
    """Brackwater's beats 23-30: one unrendered plan (Selwick) in a town of
    45 named people. The town rides beside the count for the Room to weigh
    -- it may answer that the story needs nobody new, and the back-off then
    holds the question -- and the count is the plans."""
    from world.planned_entities import add_planned_entity
    cid, _ = _story(temp_db)
    add_planned_entity(cid, {"kind": "person", "name": "Selwick",
                             "brief": {"where": "warehouse"}})
    _town(temp_db, cid, {"b1": {"name": "Tamsin Rook", "place": "quay"}})
    report = rf.frontier_report(cid, None)
    assert report["identities_ahead"] == ["Selwick"]
    assert report["bodies_ahead"] == {"harbour_office": 1}
    assert report["identities_short"] == rf.FRONTIER_IDENTITIES_MIN - 1


def test_an_exit_into_nothing_is_short_whatever_the_plan_holds_ahead(temp_db):
    """A reachable room neither the scene nor the plan holds is missing now:
    it counts when nothing is planned ahead, and it still counts when the
    plan holds all the frontier wants along the other ways out."""
    cid, _ = _story(temp_db, rooms={
        "quay": {"name": "Quay", "desc": "Wet stone.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"},
                              {"to": "the_far_stair", "barrier": "open"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    })
    report = rf.frontier_report(cid, None)
    assert report["rooms_unheld"] == ["the_far_stair"]
    assert report["rooms_developed"] == ["warehouse"]
    assert report["rooms_short"] == rf.FRONTIER_ROOMS_MIN
    _plant_ahead(cid, {
        "ropewalk": {"name": "Ropewalk", "adjacent": [{"to": "quay"}]},
        "chandlery": {"name": "Chandlery", "adjacent": [{"to": "warehouse"}]},
    })
    report = rf.frontier_report(cid, None)
    assert len(report["rooms_ahead"]) == rf.FRONTIER_ROOMS_MIN
    assert report["rooms_unheld"] == ["the_far_stair"]
    assert report["rooms_short"] == 1


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
    cid, _ = _story(temp_db)                # developed, no plan: both short
    _grant_fills(cid)
    script = scripted({"reply": "Nothing to build this pass."})
    job = sp.schedule_room_work(_beat(temp_db, cid, 2))
    assert job is not None and job.key == sp.FILL_JOB_KEY
    _wait(job)
    assert job.result["published"] == []
    # Asked once: one call, of whichever tier the grants send it to.
    assert len(_asks(script)) == len(script.payloads) == 1
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
    assert len(_asks(script)) == 2
    jobs.drain(timeout=1.0)


def test_a_new_need_or_a_new_room_while_a_need_is_open_asks_the_fill_again(
        temp_db, scripted):
    """A need is answered where the story reached for it, so while one is
    open the player's room is part of the question; planting alone is not
    (`test_walking_a_developed_area_waits_out_the_back_off`)."""
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
    # The player walks on while the need is open: a new room is a new
    # question.
    scene = temp_db.wget(cid, "scene")
    scene["positions"][PLAYER] = "warehouse"
    temp_db.wset(cid, "scene", scene)
    job = sp.schedule_room_work(_beat(temp_db, cid, 4))
    assert job is not None
    _wait(job)
    assert script.payloads[-1]["task"]["frontier"]["player_room"] == "warehouse"
    assert len(script.payloads) == 3
    jobs.drain(timeout=1.0)


def test_a_people_only_question_is_not_asked_afresh_in_every_room(
        temp_db, scripted):
    """How many PEOPLE the frontier is short of is counted frame-wide and
    does not move with the player, so the room the player stands in is part
    of the question only when rooms are short or a need is open. Keyed on
    the room, a people-only question was new each time the player walked on,
    and an answer that lands nothing counts against no hourly line -- the
    review's probe (2026-10-08) asked 7 fills in 8 beats on one unchanged
    people-only question, with `fills_this_hour` at 0 throughout. Walked
    through three rooms with every answer empty, it is asked once and then
    only as the back-off runs."""
    from core import jobs
    cid, _ = _story(temp_db)
    # A planned room beside each of the three: two stand within reach of
    # wherever the player is, so no room is short -- only people are.
    _plant_ahead(cid, {
        "ropewalk": {"name": "Ropewalk", "adjacent": [{"to": "quay"}]},
        "chandlery": {"name": "Chandlery", "adjacent": [{"to": "warehouse"}]},
        "sail_loft": {"name": "Sail Loft", "adjacent": [{"to": "loft"}]},
    })
    _grant_fills(cid)
    script = scripted()                     # every answer: nothing to build
    walk = ["quay", "warehouse", "loft", "warehouse", "quay", "warehouse",
            "loft"]
    asked = []
    for beat, where in enumerate(walk, start=2):
        scene = temp_db.wget(cid, "scene")
        scene["positions"][PLAYER] = where
        temp_db.wset(cid, "scene", scene)
        report = rf.frontier_report(cid, None)
        assert report["player_room"] == where
        assert report["rooms_short"] == 0 and not report["open_need_uids"]
        assert report["identities_short"] == rf.FRONTIER_IDENTITIES_MIN
        job = _queued_fill(_beat(temp_db, cid, beat))
        if job is not None:
            _wait(job)
            asked.append(beat)
    # Asked at once, then as the back-off ran: two beats after the first
    # empty answer, four after the second.
    assert asked == [2, 2 + rf.FILL_RETRY_BEATS, 2 + 3 * rf.FILL_RETRY_BEATS]
    assert len(_asks(script)) == 3
    jobs.drain(timeout=5.0)


def test_a_developed_area_asks_the_room_to_plant_beyond_it_on_the_back_off(
        temp_db, scripted):
    """THE OWNER'S RULE (2026-10-08): a developed area still prompts the Room
    to plant beyond it, on the back-off. No need is open and the town holds
    its people and two planned ones -- the morning's gate queued nothing here
    -- but every room within reach is furnished, so the fill is asked, shown
    the developed ground it plans beyond, and backed off while its answers
    land nothing. Planned rooms ahead answer the question for good."""
    from core import jobs
    from world.planned_entities import add_planned_entity
    cid, _ = _story(temp_db)
    _town(temp_db, cid, {"b1": {"name": "Tamsin Rook", "place": "quay"},
                         "b2": {"name": "Ada Kell", "place": "warehouse"}})
    for name in ("Selwick", "Abel Gale"):
        add_planned_entity(cid, {"kind": "person", "name": name,
                                 "brief": {"where": "warehouse"}})
    _grant_fills(cid)
    script = scripted()                     # every answer: nothing to build
    job = _queued_fill(_beat(temp_db, cid, 2))
    assert job is not None
    _wait(job)
    task = _fill_payloads(script)[0]["task"]
    assert task["needs"] == []
    assert task["frontier"]["rooms_short"] == rf.FRONTIER_ROOMS_MIN
    assert task["frontier"]["rooms_developed"] == ["loft", "warehouse"]
    assert task["frontier"]["identities_short"] == 0
    assert task["frontier"]["bodies_ahead"] == {"harbour_office": 2}
    # Unchanged, it waits out the back-off; then it is asked again.
    assert _queued_fill(_beat(temp_db, cid, 3)) is None
    job = _queued_fill(_beat(temp_db, cid, 2 + rf.FILL_RETRY_BEATS))
    assert job is not None
    _wait(job)
    assert len(_fill_payloads(script)) == 2
    # The Room's plan lands: the frontier holds what it wants ahead, and no
    # beat asks again -- whatever the back-off says.
    _plant_ahead(cid, {
        "ropewalk": {"name": "Ropewalk", "adjacent": [{"to": "quay"}]},
        "chandlery": {"name": "Chandlery", "adjacent": [{"to": "warehouse"}]},
    })
    assert not sp._fill_wanted(rf.frontier_report(cid, None))
    assert _queued_fill(_beat(temp_db, cid, 40)) is None
    assert len(_fill_payloads(script)) == 2
    jobs.drain(timeout=5.0)


def test_with_the_default_line_planting_never_takes_an_open_needs_place(
        temp_db, scripted):
    """With no number the player stated, the hour is held per kind of
    question. On the Brackwater replay with every answer publishing, four
    planting fills spent the default four by beat 11 -- in a run whose clock
    never passed one story hour -- so the need open from beat 16 would never
    have been asked under one shared count. An open need is held to the fills
    that answered needs; planting ahead to every fill that landed."""
    from core import jobs
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db)
    md.grant_mandate(cid, None, text="Fill in what the story needs.",
                     capabilities=["identity_fills", "close_need"])
    assert not md.fill_limit_stated(cid, None)
    for n in range(md.FILLS_PER_STORY_HOUR):
        rf.record_fill(cid, None, turn_idx=2, package_uid="pkg_plant_%d" % n, needs=())
    # The default hour went to planting ahead: more planting waits...
    assert sp._fill_wanted(rf.frontier_report(cid, None))
    script = scripted()
    assert _queued_fill(_beat(temp_db, cid, 3)) is None
    # ...and a need is asked at once all the same.
    need, _ = file_planning_need(cid, {"kind": "thing",
                                       "surface": {"name": "the sealed letter"}})
    job = _queued_fill(_beat(temp_db, cid, 3))
    assert job is not None
    _wait(job)
    asked = _fill_payloads(script)
    assert [n["uid"] for n in asked[-1]["task"]["needs"]] == [need["uid"]]
    jobs.drain(timeout=5.0)


def test_a_number_the_player_states_holds_planting_and_needs_together(
        temp_db, scripted):
    """"Your number is the total" (owner, 2026-10-08). A grant that states
    its own `fills_per_hour` holds planting ahead and open needs together:
    one planting fill landed at a stated line of one, and a need filed after
    it waits for the hour, where the per-kind line would have asked it."""
    from core import jobs
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db)
    md.grant_mandate(cid, None, text="One fill an hour.",
                     capabilities=["identity_fills", "close_need"],
                     limits={"fills_per_hour": 1})
    assert md.fill_limit_stated(cid, None)
    rf.record_fill(cid, None, turn_idx=2, package_uid="pkg_plant", needs=())
    script = scripted()
    file_planning_need(cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
    assert _queued_fill(_beat(temp_db, cid, 3)) is None
    assert _fill_payloads(script) == []
    jobs.drain(timeout=5.0)


# ---------------------------------------------------------------------------
# A need filed while a fill runs joins its next pass
# ---------------------------------------------------------------------------

def _clock_step():
    return {"calls": [{"tool": "inspect_clock", "args": {}}]}


def _package_uid(payload):
    """The uid of the package the transcript last showed, as the stubbed
    Planner reads it to go on with the package it opened."""
    for entry in reversed(payload.get("transcript") or []):
        result = entry.get("result") or {}
        if isinstance(result, dict) and result.get("uid"):
            return result["uid"]
    return None


def test_a_need_filed_while_a_planting_fill_runs_reaches_its_next_pass(
        temp_db, scripted, monkeypatch):
    """The fill holds the chat's one fill slot (`FILL_JOB_KEY`, deduped per
    chat), so a need filed while a planting fill runs is JOINED to it by the
    next commit rather than queued beside it. Its task was built when it
    started, with no needs, and every pass carried that same task: the
    review's probe (2026-10-08) showed the tasks [[], [need]] across two
    jobs and the need first asked a beat late -- about three beats behind a
    fill as long as the run's longest, 29 minutes. Each pass re-reads the
    open needs, and the memo files the question the pass that carried the
    need was asked, so the next commit does not ask it again at once."""
    from core import jobs
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db)                # developed, no plan: planting
    _grant_fills(cid)
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 2)
    inside, release = threading.Event(), threading.Event()

    def blocked(payload):
        inside.set()
        assert release.wait(10.0)
        return _clock_step()
    script = scripted(blocked, _clock_step(),          # pass 1 stops on steps
                      {"reply": "Nothing to build for it yet."}, sketch=ESCALATE)
    job = _queued_fill(_beat(temp_db, cid, 2))
    assert job is not None and inside.wait(10.0)
    # Beat 3 files a need while the planting fill is blocked in its first
    # pass, and its commit joins the fill in flight.
    need, _ = file_planning_need(cid, {"kind": "thing",
                                       "surface": {"name": "the sealed letter"}})
    assert _queued_fill(_beat(temp_db, cid, 3)) is job
    release.set()
    _wait(job)
    tasks = [p["task"] for p in _fill_payloads(script)]
    assert [[n["uid"] for n in t["needs"]] for t in tasks] == [
        [], [], [need["uid"]]]
    assert tasks[-1]["resumed"]["pass"] == 2
    # The question the second pass carried has its answer: unchanged at the
    # next commit, it waits out the back-off instead of being asked again.
    assert _queued_fill(_beat(temp_db, cid, 4)) is None
    assert len(_fill_payloads(script)) == 3
    jobs.drain(timeout=5.0)


def test_a_fill_is_counted_against_the_needs_it_answered(
        temp_db, scripted, monkeypatch):
    """The hour's ledger names the needs a fill's published packages
    ANSWERED or CLOSED: a need that joined a planting fill -- handed by its
    sketch to the full loop -- and was closed by the loop's second pass is
    a need's fill, counted against the line an open need is held to
    (`fills_this_hour(needs_only=True)`)."""
    from world.planning_needs import file_planning_need, open_planning_needs
    cid, _ = _story(temp_db)
    _grant_fills(cid)
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 5)
    filed = {}

    def a_beat_lands(payload):
        # A beat commits under the first pass and files a need.
        filed["need"], _ = file_planning_need(
            cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
        return _clock_step()
    script = scripted(
        a_beat_lands, _clock_step(), _clock_step(), _clock_step(),
        _clock_step(),                                  # pass 1 stops on steps
        {"calls": [{"tool": "new_package", "args": {"title": "The letter"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _package_uid(p), "operation": {
                "op": "close_need", "need_uid": filed["need"]["uid"],
                "reason": "the story moved on"}}}]},
        lambda p: {"calls": [{"tool": "validate_package",
                              "args": {"uid": _package_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _package_uid(p), "expected_revision": 2}}]},
        {"reply": "The letter is accounted for."}, sketch=ESCALATE)
    out = sp.run_fill(cid, None, base_turn=2)
    assert out["published"] and out["passes"] == 2
    assert [n["uid"] for n in _fill_payloads(script)[-1]["task"]["needs"]] \
        == [filed["need"]["uid"]]
    assert open_planning_needs(cid, None) == []
    fills = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fills"]
    assert fills[-1]["needs"] == [filed["need"]["uid"]]
    assert rf.fills_this_hour(cid, None, 2, needs_only=True) == 1


# ---------------------------------------------------------------------------
# The re-review of the restoration (2026-10-08): R2-1, R2-2, R2-3
# ---------------------------------------------------------------------------

def _walk_to(db, cid, room):
    scene = db.wget(cid, "scene")
    scene["positions"][PLAYER] = room
    db.wset(cid, "scene", scene)


def test_walking_a_developed_area_waits_out_the_back_off(temp_db, scripted):
    """R2-1. PLANTING AHEAD IS FRONTIER-WIDE: a question with no need open
    is the same question wherever the player walks. The room was part of it
    while rooms were short, so a player walking a furnished area -- every
    room within reach developed, no stub ahead -- asked a whole fill at
    every step: 6 fills in 7 beats on the review's probe, `fills_this_hour`
    at 0 throughout, because an answer that lands nothing counts against no
    hourly line. Asked once, then only as the back-off runs."""
    from core import jobs
    from world.planned_entities import add_planned_entity
    cid, _ = _story(temp_db)
    for name in ("Selwick", "Abel Gale"):           # nobody short: rooms only
        add_planned_entity(cid, {"kind": "person", "name": name,
                                 "brief": {"where": "warehouse"}})
    _grant_planting(cid)
    script = scripted()                     # every answer: nothing
    asked = []
    for beat, where in enumerate(["quay", "warehouse", "loft", "warehouse",
                                  "quay", "warehouse", "loft"], start=2):
        _walk_to(temp_db, cid, where)
        report = rf.frontier_report(cid, None)
        assert report["rooms_short"] == rf.FRONTIER_ROOMS_MIN
        assert report["identities_short"] == 0 and not report["open_need_uids"]
        job = _queued_fill(_beat(temp_db, cid, beat))
        if job is not None:
            _wait(job)
            asked.append(beat)
    assert asked == [2, 2 + rf.FILL_RETRY_BEATS, 2 + 3 * rf.FILL_RETRY_BEATS]
    assert rf.fills_this_hour(cid, None, 8) == 0
    assert len(_asks(script)) == 3
    jobs.drain(timeout=5.0)


def test_a_need_a_planting_fill_declined_does_not_spend_the_needs_line(
        temp_db, scripted):
    """R2-2. The needs' line counts fills that ANSWERED a need, never fills
    that merely carried one. With the default line spent but one, a fill carrying a standing
    need plants a person and declines the need with a reason: that landed
    on the planting line alone, so a need filed the next beat is a new
    question asked at once. Counted as a need's fill (the carried rule), it
    spent the needs' line, and the new need waited out the story hour."""
    from core import jobs
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db)
    # The engine's default line (no number the player stated): the needs'
    # line is held apart from planting's only then ("Your number is the
    # total", owner 2026-10-08). N-1 planting fills already landed, so the
    # fill below spends planting's last one.
    md.grant_mandate(cid, None, text="Fill in what the story needs, people included.",
                     capabilities=["identity_fills", "plan_entity",
                                   "create_people", "close_need"])
    for n in range(md.FILLS_PER_STORY_HOUR - 1):
        rf.record_fill(cid, None, turn_idx=1, package_uid="pkg_prior_%d" % n, needs=())
    standing, _ = file_planning_need(cid, {"kind": "thing",
                                           "surface": {"name": "the ledger"}})
    script = scripted(
        {"calls": [{"tool": "new_package", "args": {"title": "The ferryman"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _package_uid(p), "operation": {
                "op": "plan_entity", "kind": "person", "name": "Orrin Vane",
                "role": "ferryman", "brief": {"where": "quay"}}}}]},
        lambda p: {"calls": [{"tool": "validate_package",
                              "args": {"uid": _package_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _package_uid(p), "expected_revision": 2}}]},
        {"reply": "A ferryman is planted; the ledger cannot be answered yet."})
    job = _queued_fill(_beat(temp_db, cid, 2))
    assert job is not None
    _wait(job)
    assert job.result["published"]
    fills = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fills"]
    assert fills[-1]["needs"] == []
    assert rf.fills_this_hour(cid, None, 3, needs_only=True) == 0
    assert rf.fills_this_hour(cid, None, 3) == md.FILLS_PER_STORY_HOUR
    fresh, _ = file_planning_need(cid, {"kind": "thing",
                                        "surface": {"name": "the bell rope"}})
    job = _queued_fill(_beat(temp_db, cid, 3))
    assert job is not None
    _wait(job)
    asked = _fill_payloads(script)[-1]["task"]["needs"]
    assert {n["uid"] for n in asked} == {standing["uid"], fresh["uid"]}
    jobs.drain(timeout=5.0)


def test_a_joined_need_a_fill_declined_is_asked_when_its_back_off_runs(
        temp_db, scripted, monkeypatch):
    """R2-2, the joined case. A planting fill publishes in its first pass, a
    need joins it, and the second pass declines the need: the fill answered
    no need, so the need is asked again as soon as its own question's
    back-off has run -- not refused for the rest of the story hour on a line
    the planting spent."""
    from core import jobs
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db)
    # The engine's default line: the needs' line is held apart from
    # planting's only with no number the player stated (owner, 2026-10-08).
    _grant_planting(cid)
    for n in range(md.FILLS_PER_STORY_HOUR - 1):
        rf.record_fill(cid, None, turn_idx=1, package_uid="pkg_prior_%d" % n, needs=())
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 5)
    filed = {}

    def plant_and_a_beat_lands(payload):
        filed["need"], _ = file_planning_need(
            cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
        return {"calls": [{"tool": "new_package", "args": {"title": "Ahead"}}]}
    script = scripted(
        plant_and_a_beat_lands,
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _package_uid(p), "operation": {
                "op": "plan_entity", "kind": "person", "name": "Orrin Vane",
                "role": "ferryman", "brief": {"where": "quay"}}}}]},
        lambda p: {"calls": [{"tool": "validate_package",
                              "args": {"uid": _package_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _package_uid(p), "expected_revision": 2}}]},
        _clock_step(),                                  # pass 1 stops on steps
        {"reply": "The letter cannot be answered yet."}, sketch=ESCALATE)
    job = _queued_fill(_beat(temp_db, cid, 2))
    assert job is not None
    _wait(job)
    assert job.result["published"] and job.result["passes"] == 2
    assert wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fills"][-1]["needs"] == []
    # Its question was answered at beat 2, so beat 3 waits; beat 4 asks.
    assert _queued_fill(_beat(temp_db, cid, 3)) is None
    job = _queued_fill(_beat(temp_db, cid, 2 + rf.FILL_RETRY_BEATS))
    assert job is not None
    _wait(job)
    assert [n["uid"] for n in _fill_payloads(script)[-1]["task"]["needs"]] \
        == [filed["need"]["uid"]]
    jobs.drain(timeout=5.0)


def test_the_memo_files_the_question_the_next_commit_asks(
        temp_db, scripted, monkeypatch):
    """R2-3. Each pass re-measures the frontier. Pass 1 of a planting fill
    plants two rooms ahead (rooms short 2 -> 0) while a beat files a need;
    pass 2 carries the need and declines it. Its question was built with the
    frontier the fill began with, so the memo held a question the next
    commit no longer asked, and a second fill was queued at once to ask the
    need the Room had just declined."""
    from core import jobs
    from world.planned_entities import add_planned_entity
    from world.planning_needs import file_planning_need
    cid, _ = _story(temp_db)
    for name in ("Selwick", "Abel Gale"):
        add_planned_entity(cid, {"kind": "person", "name": name,
                                 "brief": {"where": "warehouse"}})
    _grant_planting(cid)
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 5)

    def plant_and_a_beat_lands(payload):
        file_planning_need(cid, {"kind": "thing",
                                 "surface": {"name": "the sealed letter"}})
        return {"calls": [{"tool": "new_package", "args": {"title": "Ahead"}}]}
    script = scripted(
        plant_and_a_beat_lands,
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _package_uid(p), "operation": {
                "op": "plan_rooms", "structure": {"key": "port", "name": "Port"},
                "rooms": {"ropewalk": {"name": "Ropewalk", "purpose": "rope is laid",
                                       "adjacent": [{"to": "quay"}]},
                          "chandlery": {"name": "Chandlery", "purpose": "tar and twine",
                                        "adjacent": [{"to": "warehouse"}]}}}}}]},
        lambda p: {"calls": [{"tool": "validate_package",
                              "args": {"uid": _package_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _package_uid(p), "expected_revision": 2}}]},
        _clock_step(),                                  # pass 1 stops on steps
        {"reply": "The letter cannot be answered yet."}, sketch=ESCALATE)
    job = _queued_fill(_beat(temp_db, cid, 2))
    assert job is not None
    _wait(job)
    assert job.result["published"] and job.result["passes"] == 2
    report = rf.frontier_report(cid, None)
    assert report["rooms_short"] == 0 and report["open_need_uids"]
    # Pass 2 was shown the frontier as pass 1 left it, not as it began...
    assert _fill_payloads(script)[-1]["task"]["frontier"]["rooms_short"] == 0
    # ...and the question it was asked IS the one beat 3 asks: it waits.
    assert _queued_fill(_beat(temp_db, cid, 3)) is None
    assert len(_fill_payloads(script)) == 6
    jobs.drain(timeout=5.0)


def test_a_new_grant_is_a_new_question():
    report = {"open_need_uids": ["need_a"], "player_room": "quay",
              "rooms_short": 0, "identities_short": 1}
    assert rf.fill_signature(report, ["m1"]) == rf.fill_signature(report, ["m1"])
    assert rf.fill_signature(report, ["m1"]) != rf.fill_signature(report, ["m1", "m2"])
    # Which stubs or plans stand ahead is not the question; how short the
    # frontier is, is.
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


def test_a_failed_fill_is_an_empty_answer_for_the_back_off(
        temp_db, scripted, monkeypatch):
    """The Brackwater fill F18 ended on HTTP 402. A failure re-asked on the
    very next commit is what an exhausted provider makes expensive -- in
    either tier: the sketch's one call, or the loop it handed the question
    to."""
    cid, _ = _story(temp_db)
    _grant_fills(cid)

    def _dead(*a, **k):
        raise RuntimeError("HTTP 402: insufficient credit")
    monkeypatch.setattr(providers, "chat_complete", _dead)
    with pytest.raises(RuntimeError, match="402"):
        sp.run_fill(cid, None, base_turn=2)
    memo = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fill_memo"]
    assert [m["misses"] for m in memo] == [1]
    # Handed on by the sketch, the loop fails: the same empty answer.
    scripted(sketch=ESCALATE)
    monkeypatch.setattr(sp, "_run_task", _dead)
    with pytest.raises(RuntimeError, match="402"):
        sp.run_fill(cid, None, base_turn=2)
    memo = wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["fill_memo"]
    assert [m["misses"] for m in memo] == [2]


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
# With no fill grant, the status row says what waits on one
# ---------------------------------------------------------------------------

def test_with_no_fill_grant_the_status_row_names_what_waits_and_no_other(
        temp_db):
    """The status row asks the player for a fill grant when a fill is wanted
    and none is held. It said the room had OPEN PLANNING NEEDS whatever was
    wanted, so with planting ahead restored it said so in every developed
    area and chartered town with no need open (chat 114, beats 0-4) -- and
    the Room reads the same row back as its own `status`. The row names
    what actually waits: an open need, or the frontier the Room would plant.
    Each is said once, ahead of the Room's own questions, the other takes
    its place when it becomes the true one, both are withdrawn when nothing
    waits, and the questions the Room asked itself are left alone."""
    from world.planned_entities import add_planned_entity
    from world.planning_needs import close_planning_need, file_planning_need
    from story import room_conversation as room
    cid, _ = _story(temp_db)                # developed, no plan: both short
    own = "Which way does the tide run tonight?"
    sp.write_status(cid, None, questions=[own], turn_idx=0)

    def asked():
        return [qn["text"] for qn in room.status(cid, None)["questions"]]

    # Beats 1-5, inside one Dramaturge pacing window, so nothing else that
    # the commit tail queues writes the row while it is read.
    sp.schedule_room_work(_beat(temp_db, cid, 1))
    assert asked() == [sp.WAITING_TO_PLANT_LINE, own]
    sp.schedule_room_work(_beat(temp_db, cid, 2))
    assert asked() == [sp.WAITING_TO_PLANT_LINE, own]
    # A need opens: that is what waits now, said in the planting line's place.
    need, _ = file_planning_need(cid, {"kind": "thing",
                                       "surface": {"name": "the sealed letter"}})
    sp.schedule_room_work(_beat(temp_db, cid, 3))
    sp.schedule_room_work(_beat(temp_db, cid, 3))
    assert asked() == [sp.WAITING_LINE, own]
    # It closes, and the frontier is still short.
    close_planning_need(cid, need["uid"], "the story moved on")
    sp.schedule_room_work(_beat(temp_db, cid, 4))
    assert asked() == [sp.WAITING_TO_PLANT_LINE, own]
    # The plan holds what the frontier wants: nothing waits, nothing is said.
    _plant_ahead(cid, {
        "ropewalk": {"name": "Ropewalk", "adjacent": [{"to": "quay"}]},
        "chandlery": {"name": "Chandlery", "adjacent": [{"to": "warehouse"}]},
    })
    for name in ("Selwick", "Abel Gale"):
        add_planned_entity(cid, {"kind": "person", "name": name,
                                 "brief": {"where": "warehouse"}})
    assert not sp._fill_wanted(rf.frontier_report(cid, None))
    sp.schedule_room_work(_beat(temp_db, cid, 5))
    assert asked() == [own]


def test_a_full_status_row_still_carries_the_ask_for_a_grant(temp_db):
    """The row holds `STATUS_QUESTIONS_CAP` questions and the ask was said
    LAST, so with the Room's own questions filling the row the cap cut it
    and the player was never asked at all (probe 2026-10-08; the Dramaturge
    lane's review found the same of `WAITING_LINE`). The engine's ask is
    said first, the Room's questions keep their order behind it, and the
    row is not rewritten while nothing changes."""
    from story import room_conversation as room
    cid, _ = _story(temp_db)                # developed, no plan: both short
    own = ["Question %d?" % i for i in range(sp.STATUS_QUESTIONS_CAP)]
    sp.write_status(cid, None, questions=own, turn_idx=0)

    def asked():
        return [qn["text"] for qn in room.status(cid, None)["questions"]]

    sp.schedule_room_work(_beat(temp_db, cid, 1))
    assert asked() == [sp.WAITING_TO_PLANT_LINE] + own[:-1]
    written = room.status(cid, None)["updated_turn"]
    sp.schedule_room_work(_beat(temp_db, cid, 2))
    assert asked() == [sp.WAITING_TO_PLANT_LINE] + own[:-1]
    assert room.status(cid, None)["updated_turn"] == written


def test_a_fill_grant_withdraws_the_line_that_asked_for_one(temp_db, scripted):
    """The line says the room holds NO grant. Once one is held it is false,
    whether or not a fill runs at that commit -- here none does, the hour's
    one fill having landed already."""
    from core import jobs
    from story import room_conversation as room
    cid, _ = _story(temp_db)
    sp.schedule_room_work(_beat(temp_db, cid, 2))
    assert [qn["text"] for qn in room.status(cid, None)["questions"]] == [
        sp.WAITING_TO_PLANT_LINE]
    md.grant_mandate(cid, None, text="One fill an hour.",
                     capabilities=["identity_fills", "plan_rooms"],
                     limits={"fills_per_hour": 1})
    rf.record_fill(cid, None, turn_idx=2, package_uid="pkg_plant", needs=())
    script = scripted()
    assert _queued_fill(_beat(temp_db, cid, 3)) is None
    assert room.status(cid, None)["questions"] == []
    assert _fill_payloads(script) == []
    jobs.drain(timeout=5.0)


# ---------------------------------------------------------------------------
# The card says what a fill is, in both packs
# ---------------------------------------------------------------------------

def test_the_planner_card_says_a_fill_plants_ahead_in_both_packs():
    """`fill` appeared nowhere in the Planner's card, and three Brackwater
    fills (28 calls) answered the player's turn-4 line all over again. The
    morning's card then told a fill to stop when nothing was missing; the
    owner's ruling makes planting ahead the fill's standing work, with
    building nothing still a complete answer."""
    from llm.prompts import get_prompt
    en = get_prompt("story_planner", "en")
    ja = get_prompt("story_planner", "ja")
    fill_en = next(line for line in en.splitlines() if line.startswith("THE FILL."))
    assert "is not answered again" in fill_en
    assert "plant ahead" in fill_en and "standing work" in fill_en
    assert "say so in one step and stop" not in fill_en
    assert "先回りして植えて" in ja
    # The keys the task carries, verbatim in both packs (the protocol guard
    # in `make structure` holds the same spans).
    for token in ('"fill"', '"needs"', '"frontier"', '"rooms_short"',
                  '"identities_short"', '"rooms_ahead"', '"identities_ahead"',
                  '"rooms_developed"', '"bodies_ahead"', '"rooms_unheld"',
                  '"rooms_unmeasured"'):
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
