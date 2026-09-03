"""The Story Planner (`agents/story_planner.py`), the mandates it writes
(`story/mandates.py`) and the frontier it keeps (`story/room_frontier.py`).

Every model call is a scripted stub: the loop, the grant grammar, the
authority check at validate and publish, the fill job and its budget, and
the firewall are all proven without a provider.
"""
from __future__ import annotations

import json
import time

import pytest

from core.db import wget_for_frame, wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm import providers
from story import mandates as md
from story import room_conversation as room
from story import room_frontier as rf
from story.plot_packages import (draft_operation, get_package, new_package,
                                 publish_package, validate_package)
from agents import story_planner as sp

PLAYER = "The Stranger"


def _story(db, *, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Planner", "A port at dusk.", time.time()))
    wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone and rope.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates to the rafters.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}})
    turn_id = None
    for i in range(turns):
        turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                        "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    return cid, turn_id


def _ctx(db, cid, turn_id, idx):
    return PipelineContext(
        chat=ChatData(id=cid, name="Planner", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx, player_input="",
                      created=time.time(), frame_id=None),
        cast=[], input="")


class Script:
    """The stubbed model: one scripted answer per call. An entry is a dict
    or a callable of the payload; it records every payload it was shown."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.payloads = []
        self.systems = []

    def __call__(self, role, system, user, **kw):
        assert role == sp.PLANNER_ROLE
        payload = json.loads(user)
        self.payloads.append(payload)
        self.systems.append(system)
        if not self.steps:
            return json.dumps({"reply": "nothing more"})
        step = self.steps.pop(0)
        if callable(step):
            step = step(payload)
        return json.dumps(step)


@pytest.fixture
def scripted(monkeypatch):
    def install(*steps):
        script = Script(*steps)
        monkeypatch.setattr(providers, "chat_complete", script)
        return script
    return install


def _last_uid(payload):
    for entry in reversed(payload.get("transcript") or []):
        result = entry.get("result") or {}
        if isinstance(result, dict) and result.get("uid"):
            return result["uid"]
    return None


def _grant_all(cid, caps, **limits):
    return md.grant_mandate(cid, None, text="You may " + ", ".join(caps),
                            capabilities=caps, limits=limits or None)


# ---------------------------------------------------------------------------
# Seating, role, prompts
# ---------------------------------------------------------------------------

def test_the_role_exists_and_both_packs_carry_the_prompts(temp_db):
    from llm.prompts import get_prompt
    assert "story_planner" in providers.ROLES
    for lang in ("en", "ja"):
        assert len(get_prompt("story_planner", lang)) > 500
        assert len(get_prompt("charter_planner", lang)) > 300


def test_the_app_seats_the_planner_and_a_test_can_unseat_it():
    import web.app  # noqa: F401  (seating happens at import)
    sp.seat()
    assert room.planner_seated()
    assert room.PLANNER is sp.planner_reply
    sp.unseat()
    assert not room.planner_seated()


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

def test_a_reply_runs_tools_then_answers_and_writes_status(temp_db, scripted):
    cid, _ = _story(temp_db)
    script = scripted(
        {"calls": [{"tool": "inspect_clock", "args": {}}]},
        {"reply": "The port stands at turn two.", "status_line": "One matter is being weighed.",
         "questions": ["May the room plan a harbour master?"]},
    )
    out = sp.run_planner(cid, None, text="What time is it?")
    assert out["reply"] == "The port stands at turn two."
    assert out["calls"] == 1 and out["steps"] == 2 and out["stopped"] is None
    shown = script.payloads[1]["transcript"]
    assert shown[0]["tool"] == "inspect_clock" and shown[0]["result"]["turn_idx"] == 2
    assert script.payloads[0]["player_says"] == "What time is it?"
    assert script.payloads[0]["budget"]["steps"] == sp.PLANNER_STEPS_PER_REPLY
    status = room.status(cid, None)
    assert status["line"] == "One matter is being weighed."
    assert [q["text"] for q in status["questions"]] == ["May the room plan a harbour master?"]
    # Through the seam: the envelope the panel reads.
    sp.seat()
    try:
        scripted({"reply": "Still dusk."})
        env = room.converse(cid, None, "And now?")
    finally:
        sp.unseat()
    assert env["seated"] and env["replies"][0]["role"] == "planner"
    assert env["replies"][0]["text"] == "Still dusk."


def test_spend_is_the_real_stop_and_the_ceilings_are_safety(temp_db, scripted,
                                                            monkeypatch):
    """Owner, 2026-09-03: the bounds were too strict. Steps and calls per
    reply are safety ceilings an order of magnitude above the work; what
    stops a reply is the spend the player granted (a default when no grant
    names one), and the Planner says so."""
    cid, _ = _story(temp_db)
    assert sp.PLANNER_STEPS_PER_REPLY >= 40 and sp.PLANNER_TOOL_CALLS_PER_REPLY >= 200
    scripted(*[{"calls": [{"tool": "inspect_clock", "args": {}}] * 8}] * 60)
    out = sp.run_planner(cid, None, text="loop")
    assert out["stopped"] == "spend_reply" and out["calls"] == md.CALLS_PER_REPLY
    assert out["reply"] == sp.SPENT_LINE
    assert rf.spend_this_hour(cid, None, 2) == md.CALLS_PER_REPLY
    # A grant may raise spend up to the engine's ceiling, never past it.
    md.grant_mandate(cid, None, text="Spend freely", capabilities=["plan_rooms"],
                     limits={"calls_per_reply": 10_000, "calls_per_hour": 10_000})
    assert md.spend_limits(cid, None) == {"calls_per_reply": md.CALLS_PER_REPLY_CAP,
                                          "calls_per_hour": md.CALLS_PER_STORY_HOUR_CAP}
    # With spend out of the way the safety ceilings hold, lowered here so
    # the test does not script two hundred calls.
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 5)
    scripted(*[{"calls": [{"tool": "inspect_clock", "args": {}}]}] * 20)
    out = sp.run_planner(cid, None, text="loop")
    assert out["stopped"] == "steps" and out["steps"] == 5
    assert out["reply"] == sp.BOUNDED_LINE
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 40)
    monkeypatch.setattr(sp, "PLANNER_TOOL_CALLS_PER_REPLY", 16)
    scripted(*[{"calls": [{"tool": "inspect_clock", "args": {}}] * 8}] * 20)
    out = sp.run_planner(cid, None, text="loop")
    assert out["stopped"] == "calls" and out["calls"] == 16


def test_the_hour_spend_stops_the_room_and_the_grant_is_cited(temp_db, scripted):
    cid, _ = _story(temp_db)
    row = md.grant_mandate(cid, None, text="Ten calls an hour",
                           capabilities=["plan_rooms"], limits={"calls_per_hour": 10})
    scripted(*[{"calls": [{"tool": "inspect_clock", "args": {}}] * 8}] * 10)
    out = sp.run_planner(cid, None, text="loop")
    assert out["stopped"] == "spend_hour" and out["calls"] == 10
    assert out["reply"] == sp.HOUR_SPENT_LINE
    assert "spend stop under %s" % row["uid"] in out["notes"]
    # Nothing left this hour: the next reply stops before a step.
    scripted({"reply": "never asked"})
    out = sp.run_planner(cid, None, text="again")
    assert out["stopped"] == "spend_hour" and out["steps"] == 0


def test_a_background_task_resumes_in_passes_and_a_reply_shows_progress(
        temp_db, scripted, monkeypatch):
    cid, _ = _story(temp_db)
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 2)
    script = scripted(
        {"calls": [{"tool": "inspect_clock", "args": {}}], "status_line": "Reading the port."},
        {"calls": [{"tool": "inspect_clock", "args": {}}], "status_line": "Still reading."},
        {"calls": [{"tool": "inspect_clock", "args": {}}]},
        {"reply": "Done in two passes."},
    )
    out = sp._run_task(cid, None, {"kind": "fill", "needs": []}, base_turn=2)
    assert out["passes"] == 2 and out["reply"] == "Done in two passes."
    assert out["stopped"] is None and out["steps"] == 4
    assert script.payloads[0]["budget"]["regime"] == "task"
    assert "resumed" not in script.payloads[0]["task"]
    assert script.payloads[2]["task"]["resumed"]["pass"] == 2
    assert script.payloads[2]["task"]["resumed"]["last_stopped"] == "steps"
    # The interactive regime rewrites the status row every step the model
    # names one, so the panel's watch shows a long reply working.
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 40)
    lines = []
    original = sp.write_status

    def spy(*args, **kwargs):
        lines.append(kwargs.get("line"))
        return original(*args, **kwargs)
    monkeypatch.setattr(sp, "write_status", spy)
    scripted({"calls": [{"tool": "inspect_clock", "args": {}}], "status_line": "Step one."},
             {"reply": "ok", "status_line": "Step two."})
    out = sp.run_planner(cid, None, text="hi")
    assert out["regime"] == "reply" and lines[:2] == ["Step one.", "Step two."]


def test_the_bible_rides_the_system_block_and_the_window_waits_for_the_fold(
        temp_db, scripted):
    from story import room_bible as rb
    cid, _ = _story(temp_db)
    rb.add_entry(cid, None, "wants", "The player asked for a harbour (beat 1).", ["turn:1"])
    ids = [room.add_message(cid, None, "player", "line %d" % n)["id"] for n in range(45)]
    script = scripted({"reply": "ok"})
    sp.run_planner(cid, None, text="hi")
    assert "STORY BIBLE" in script.systems[0] and "asked for a harbour" in script.systems[0]
    shown = [m["id"] for m in script.payloads[0]["conversation"]]
    # Every unfolded line is still shown (45 lines, none folded), past the
    # thirty-line window and up to the hard cap.
    assert len(shown) == 45 and shown[-1] == ids[-1]
    # Once the fold has read the oldest lines, the window is the window.
    row = rb.bible(cid, None)
    row["folded_through"] = ids[14]
    from core.db import wset_for_frame
    wset_for_frame(cid, rb.BIBLE_KEY, row, None)
    script = scripted({"reply": "ok"})
    sp.run_planner(cid, None, text="hi")
    shown = [m["id"] for m in script.payloads[0]["conversation"]]
    assert shown[0] == ids[15] and len(shown) == 30


def test_a_bad_tool_call_is_an_error_the_model_sees_not_a_crash(temp_db, scripted):
    cid, _ = _story(temp_db)
    script = scripted(
        {"calls": [{"tool": "drop_table", "args": {}},
                   {"tool": "search_lore", "args": {"sql": "x"}},
                   {"tool": "retire_package", "args": {"uid": "plot:x"}}]},
        {"reply": "ok"})
    out = sp.run_planner(cid, None, text="try")
    assert out["reply"] == "ok"
    results = [e["result"] for e in script.payloads[1]["transcript"]]
    assert "no tool" in results[0]["error"]
    assert "takes no argument" in results[1]["error"]
    assert "host action" in results[2]["error"]


# ---------------------------------------------------------------------------
# Grants: the player's words become rows; the rows gate the writes
# ---------------------------------------------------------------------------

def test_a_grant_in_the_players_words_becomes_a_mandate(temp_db, scripted):
    cid, _ = _story(temp_db)
    scripted({"grants": [
        {"text": "You may plan people for the port, two at most",
         "scope": "the port", "capabilities": ["plan_entity", "create_people"],
         "limits": {"people": 2, "nonsense": 9}, "expires_turn": 40},
        {"text": "and fly", "capabilities": ["levitate"]},
    ], "reply": "Recorded."})
    out = sp.run_planner(cid, None, text="You may plan people for the port, two at most.")
    rows = out["mandates"]
    assert len(rows) == 1
    row = rows[0]
    assert row["text"].startswith("You may plan people")
    assert row["scope"] == "the port" and row["status"] == "active"
    assert row["capabilities"] == ["plan_entity", "create_people"]
    assert row["limits"] == {"people": 2} and row["expires_turn"] == 40
    assert row["uid"].startswith("mandate_")
    assert any("no such room capability" in n for n in out["notes"])
    # A fill TASK cannot grant itself anything.
    scripted({"grants": [{"text": "x", "capabilities": ["surprise"]}], "reply": "done"})
    sp.run_planner(cid, None, task={"kind": "fill", "needs": []})
    assert len(room.mandates(cid, None)) == 1


def test_a_planner_package_publishes_only_under_a_covering_mandate(temp_db):
    cid, _ = _story(temp_db)
    pkg = new_package(cid, title="Harbour", created_by="story_planner")
    draft_operation(cid, pkg["uid"], {
        "op": "plan_rooms", "structure": {"key": "harbour", "name": "Harbour"},
        "rooms": {"harbour_pier": {"name": "Pier", "adjacent": [{"to": "quay"}]}}})
    verdict = validate_package(cid, pkg["uid"])
    assert not verdict["ok"]
    assert any("no standing mandate permits plan_rooms" in e for e in verdict["errors"])
    grant = _grant_all(cid, ["plan_rooms"])
    verdict = validate_package(cid, pkg["uid"])
    assert verdict["ok"], verdict
    # Revoked between validation and publish: the write is refused and the
    # refusal cites the standing state.
    room.revoke_mandate(cid, grant["uid"])
    with pytest.raises(ValueError, match="no standing mandate permits plan_rooms"):
        publish_package(cid, pkg["uid"], expected_revision=get_package(cid, pkg["uid"])["revision"])
    _grant_all(cid, ["plan_rooms"])
    out = publish_package(cid, pkg["uid"], expected_revision=get_package(cid, pkg["uid"])["revision"])
    assert out["published_turn"] == 2


def test_a_host_package_needs_no_grant(temp_db):
    cid, _ = _story(temp_db)
    pkg = new_package(cid, title="Host's own")
    draft_operation(cid, pkg["uid"], {"op": "post_artifact", "room": "quay",
                                      "description": "a bill"})
    assert validate_package(cid, pkg["uid"])["ok"]
    assert publish_package(cid, pkg["uid"], expected_revision=2)["published_turn"] == 2


def test_authority_flags_and_sealing_need_their_own_capabilities(temp_db):
    from story.plot_packages import package_requirements
    cid, _ = _story(temp_db)
    pkg = new_package(cid, title="Sealed", spoiler_policy="sealed",
                      authority={"may_create_people": True, "may_schedule_harm": True},
                      created_by="story_planner")
    draft_operation(cid, pkg["uid"], {"op": "plan_entity", "name": "Ned Pike",
                                      "role": "pilot", "brief": {"where": "quay"}})
    assert package_requirements(get_package(cid, pkg["uid"])) == [
        "plan_entity", "create_people", "schedule_harm", "surprise"]
    _grant_all(cid, ["plan_entity", "create_people"])
    verdict = validate_package(cid, pkg["uid"])
    assert any("schedule_harm, surprise" in e for e in verdict["errors"])
    pkg2 = new_package(cid, title="Cited", authority={"mandate_uid": "mandate_nobody"},
                       created_by="story_planner")
    draft_operation(cid, pkg2["uid"], {"op": "plan_entity", "name": "Ada Pike",
                                       "role": "pilot", "brief": {"where": "quay"}})
    verdict = validate_package(cid, pkg2["uid"])
    assert any("mandate_nobody, which is not active" in e for e in verdict["errors"])


def test_the_planner_sees_a_withdrawal_and_its_publish_is_refused(temp_db, scripted):
    cid, _ = _story(temp_db)
    grant = _grant_all(cid, ["post_artifact"])
    script = scripted(
        {"calls": [{"tool": "new_package", "args": {"title": "Bills"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {"op": "post_artifact", "room": "quay",
                                               "description": "a notice"}}}]},
        lambda p: {"calls": [{"tool": "validate_package", "args": {"uid": _last_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 2}}]},
        {"reply": "Posted."})
    out = sp.run_planner(cid, None, text="Post a notice on the quay.")
    assert out["published"] and out["reply"] == "Posted."
    assert get_package(cid, out["published"][0])["provenance"]["created_by"] == "story_planner"
    room.revoke_mandate(cid, grant["uid"])
    script = scripted(
        {"calls": [{"tool": "new_package", "args": {"title": "More bills"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {"op": "post_artifact", "room": "quay",
                                               "description": "another"}}}]},
        lambda p: {"calls": [{"tool": "validate_package", "args": {"uid": _last_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 2}}]},
        {"reply": "I cannot: the grant was withdrawn."})
    out = sp.run_planner(cid, None, text="Post another.")
    assert out["published"] == []
    withdrawn = script.payloads[0]["withdrawn"]
    assert withdrawn and withdrawn[0]["uid"] == grant["uid"] and withdrawn[0]["status"] == "revoked"
    results = [e["result"] for e in script.payloads[-1]["transcript"]]
    assert results[2]["ok"] is False
    assert any("no standing mandate permits post_artifact" in e for e in results[2]["errors"])
    # Publish is refused on the failed validation; and were the validation
    # stale-but-passing, the seam re-checks the grant itself (the direct
    # test above).
    assert "validate" in results[3]["refused"]


def test_expiry_and_the_fill_limit(temp_db):
    cid, _ = _story(temp_db)
    assert md.fill_limit(cid, None) is None
    md.grant_mandate(cid, None, text="fill freely", capabilities=["identity_fills"],
                     limits={"fills_per_hour": 99})
    assert md.fill_limit(cid, None) == md.FILLS_PER_STORY_HOUR_CAP
    short = md.grant_mandate(cid, None, text="briefly", capabilities=["plan_rooms"],
                             expires_turn=1)
    assert [m["uid"] for m in md.active_mandates(cid, None)] != [short["uid"]]
    assert md.coverage(cid, None, ["plan_rooms"])["missing"] == ["plan_rooms"]
    assert md.coverage(cid, None, ["identity_fills"])["ok"]
    assert "expired" in md.citation(cid, None, [short["uid"]])
    with pytest.raises(ValueError, match="at least one capability"):
        md.grant_mandate(cid, None, text="nothing", capabilities=[])


# ---------------------------------------------------------------------------
# The frontier and the fill job
# ---------------------------------------------------------------------------

def test_the_frontier_counts_what_stands_ahead(temp_db):
    from world.structure import plant_structure
    cid, _ = _story(temp_db)
    report = rf.frontier_report(cid, None)
    assert report["player_room"] == "quay"
    assert report["rooms_ahead"] == [] and report["rooms_short"] == rf.FRONTIER_ROOMS_MIN
    assert report["identities_short"] == rf.FRONTIER_IDENTITIES_MIN
    plant_structure(cid, {"key": "port", "name": "Port"}, {
        "custom_house": {"name": "Custom House", "adjacent": [{"to": "quay"}]},
        "bonded_store": {"name": "Bonded Store", "adjacent": [{"to": "custom_house"}]},
        "far_light": {"name": "Far Light", "adjacent": [{"to": "bonded_store"}]},
    })
    from world.planned_entities import add_planned_entity
    add_planned_entity(cid, {"kind": "person", "name": "Tamsin Reed",
                             "brief": {"where": "custom_house"}})
    report = rf.frontier_report(cid, None)
    # Two hops from the quay: the custom house and the bonded store; the
    # far light is three away and does not count.
    assert report["rooms_ahead"] == ["bonded_store", "custom_house"]
    assert report["rooms_short"] == 0
    assert report["identities_ahead"] == ["Tamsin Reed"]
    assert report["identities_short"] == rf.FRONTIER_IDENTITIES_MIN - 1


def test_the_fill_job_waits_for_a_grant_then_runs_under_the_hour_budget(
        temp_db, scripted):
    from core import jobs
    from world.planning_needs import file_planning_need, open_planning_needs
    cid, turn_id = _story(temp_db)
    need, _ = file_planning_need(cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
    ctx = _ctx(temp_db, cid, turn_id, 2)
    # No grant: nothing runs, the status row asks.
    assert sp.schedule_room_work(ctx) is None
    assert sp.WAITING_LINE in [q["text"] for q in room.status(cid, None)["questions"]]
    assert wget_for_frame(cid, rf.FRONTIER_KEY, None, {})["measured_turn"] == 2
    # Granted, one fill an hour: the job runs the Planner, which closes the
    # need through a package.
    md.grant_mandate(cid, None, text="You may answer needs and close them",
                     capabilities=["identity_fills", "close_need"],
                     limits={"fills_per_hour": 1})
    script = scripted(
        {"calls": [{"tool": "new_package", "args": {"title": "The letter"}}]},
        lambda p: {"calls": [{"tool": "draft_operation", "args": {
            "uid": _last_uid(p), "operation": {"op": "close_need", "need_uid": need["uid"],
                                               "reason": "the story moved on"}}}]},
        lambda p: {"calls": [{"tool": "validate_package", "args": {"uid": _last_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 2}}]},
        {"reply": "The letter is accounted for."})
    job = sp.schedule_room_work(ctx)
    assert job is not None and job.key == sp.FILL_JOB_KEY
    deadline = time.time() + 15.0
    while job.state in ("pending", "running") and time.time() < deadline:
        time.sleep(0.02)
    assert job.state == "done", (job.state, job.error)
    assert job.result["published"]
    assert script.payloads[0]["task"]["needs"][0]["uid"] == need["uid"]
    assert "player_says" not in script.payloads[0]
    assert open_planning_needs(cid, None) == []
    assert room.messages(cid, None)[-1]["role"] == "planner"
    assert rf.fills_this_hour(cid, None, 2) == 1
    # The hour's budget is spent: the next commit queues nothing.
    assert sp.schedule_room_work(ctx) is None
    jobs.drain(timeout=1.0)


def test_a_rewound_story_refuses_the_fill(temp_db, scripted):
    cid, _ = _story(temp_db)
    scripted({"reply": "never asked"})
    out = sp.run_fill(cid, None, base_turn=9)
    assert out["skipped"] == "rewound"
    # And a write inside a running job is refused when the story rewinds
    # under it, whatever the model asks for.
    _grant_all(cid, ["post_artifact"])
    script = scripted(
        {"calls": [{"tool": "new_package", "args": {"title": "Bills"}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 1}}]},
        {"reply": "unreached"})
    out = sp.run_planner(cid, None, text=None, task={"kind": "fill", "needs": []},
                         base_turn=9)
    assert out["stopped"] == "rewound" and out["reply"] == sp.REWOUND_LINE
    assert out["published"] == []


# ---------------------------------------------------------------------------
# The Charter Planner delegation
# ---------------------------------------------------------------------------

def test_the_charter_planner_returns_a_request_or_conflicts(temp_db, scripted):
    cid, _ = _story(temp_db)
    script = scripted(
        {"request": {"name": "The Mill", "brief": "A tide mill.", "population": 6,
                     "topology": "one yard", "junk": "dropped",
                     "required_rooms": [{"name": "Wheelhouse", "connect_to": "quay"}]},
         "conflicts": [], "report": "Planned a mill on the quay."},
        {"request": {}, "conflicts": ["the brief names a room that is nowhere"],
         "report": "Could not plan it."})
    out = sp.charter_planner(cid, None, {"purpose": "a tide mill on the quay"})
    assert set(out["request"]) == {"name", "brief", "population", "topology", "required_rooms"}
    assert out["conflicts"] == [] and out["report"].startswith("Planned")
    shown = script.payloads[0]
    assert shown["brief"]["purpose"] == "a tide mill on the quay"
    assert "search_lore" in shown and "inspect_reserved_identities" in shown
    out = sp.charter_planner(cid, None, {"purpose": "a lighthouse on the moon"})
    assert out["request"] == {} and out["conflicts"]
    assert sp.charter_planner(cid, None, {})["error"]


def test_the_delegation_is_once_per_reply_and_lands_as_a_request(temp_db, scripted):
    cid, _ = _story(temp_db)
    script = scripted(
        {"calls": [{"tool": sp.CHARTER_PLANNER_TOOL, "args": {"brief": {"purpose": "a mill"}}},
                   {"tool": sp.CHARTER_PLANNER_TOOL, "args": {"brief": {"purpose": "a mill"}}}]},
        {"request": {"name": "The Mill", "brief": "A tide mill."}, "conflicts": [],
         "report": "ok"},
        {"reply": "A mill is planned."})
    out = sp.run_planner(cid, None, text="Plan a mill.")
    results = [e["result"] for e in script.payloads[-1]["transcript"]]
    assert results[0]["request"]["name"] == "The Mill"
    assert "once per reply" in results[1]["refused"]
    assert out["calls"] == 2
    assert sp.CHARTER_PLANNER_TOOL in script.systems[0]
    assert "tools" not in script.payloads[0]


# ---------------------------------------------------------------------------
# The firewall
# ---------------------------------------------------------------------------

def test_a_planner_reply_cannot_reach_a_mind(temp_db, scripted):
    from story.scene import recent_events_for_observer
    cid, _ = _story(temp_db)
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                         ("Mara Quill", json.dumps({"name": "Mara Quill"}), time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (cid, char_id, "active", json.dumps({"mood": "calm"})))
    temp_db.qi("INSERT INTO memories(chat_id,char_id,turn_idx,kind,content) "
               "VALUES(?,?,?,?,?)", (cid, char_id, 1, "episodic", "The tide came in."))
    temp_db.qi("INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
               (cid, None, "Wren walked the quay."))

    def snapshot():
        return {
            "chars": [dict(r) for r in temp_db.q(
                "SELECT char_id, status, state, sheet FROM chat_chars WHERE chat_id=?", (cid,))],
            "memories": [dict(r) for r in temp_db.q(
                "SELECT char_id, turn_idx, kind, content FROM memories WHERE chat_id=?", (cid,))],
            "known": temp_db.wget(cid, "known", {}),
            "relationships": [dict(r) for r in temp_db.q(
                "SELECT key, value FROM world WHERE chat_id=? AND key LIKE 'relationships:%'",
                (cid,))],
            "view": recent_events_for_observer(cid, "Mara Quill", n=5, frame_id=None),
        }
    before = snapshot()
    _grant_all(cid, ["plan_entity", "create_people", "post_artifact"])
    secret = "The verger did it and Mara must never know."
    scripted(
        {"calls": [{"tool": "new_package", "args": {"title": "Verger", "premise": secret}}]},
        lambda p: {"calls": [
            {"tool": "draft_operation", "args": {"uid": _last_uid(p), "operation": {
                "op": "plan_entity", "name": "Verger Hale", "role": "verger",
                "brief": {"where": "warehouse", "truths": secret}}}},
            {"tool": "draft_operation", "args": {"uid": _last_uid(p), "operation": {
                "op": "post_artifact", "room": "quay", "description": "a bill"}}}]},
        lambda p: {"calls": [{"tool": "validate_package", "args": {"uid": _last_uid(p)}}]},
        lambda p: {"calls": [{"tool": "publish_package", "args": {
            "uid": _last_uid(p), "expected_revision": 3}}]},
        {"reply": secret, "status_line": "A matter at the chapel is in motion."})
    out = sp.run_planner(cid, None, text="Plan the verger.")
    assert out["published"]
    assert snapshot() == before
    haystack = json.dumps([dict(r) for r in temp_db.q(
        "SELECT content FROM events WHERE chat_id=?", (cid,))])
    haystack += json.dumps(temp_db.wget(cid, "scene"))
    haystack += json.dumps(temp_db.q("SELECT state FROM chat_chars WHERE chat_id=?", (cid,))[0]["state"])
    assert "verger did it" not in haystack.casefold()
    # The status the panel shows carries the label and state, never the truth.
    status = room.status(cid, None)
    assert status["in_motion"][0]["label"] == "Verger"
    assert "verger did it" not in json.dumps(status).casefold()


def test_the_planners_fixed_lines_are_in_both_catalogs():
    """English is the message id: the panel renders a stored line through
    the catalog, so each fixed line the Planner can say is harvested (from
    `static/js/writers_room.js`) and translated."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    en = json.loads((root / "language_packs" / "en" / "ui.json").read_text("utf-8"))
    ja = json.loads((root / "language_packs" / "ja" / "ui.json").read_text("utf-8"))
    script = (root / "static" / "js" / "writers_room.js").read_text("utf-8")
    for line in (sp.BOUNDED_LINE, sp.NO_STATUS_LINE, sp.WAITING_LINE, sp.REWOUND_LINE,
                 sp.SPENT_LINE, sp.HOUR_SPENT_LINE, sp.DISAGREEMENT_LINE):
        assert line in en and line in script
        assert ja.get(line) not in (None, line)


def test_a_call_the_loop_cannot_run_is_reported_not_dropped(temp_db, monkeypatch):
    """Measured live (chat 111, 2026-09-03): three steps of calls spelled
    with `name` for the tool key were skipped silently and the model, seeing
    an empty transcript, repeated them. A misspelled key is accepted; a call
    with no tool at all comes back in the transcript as an error."""
    from agents import story_planner as sp
    from llm import providers
    seen = []
    answers = iter([
        {"calls": [{"name": "inspect_needs", "args": {}}, {"args": {}}, "junk"]},
        {"calls": [], "reply": "done"},
    ])
    def script(role, system, user, **kw):
        import json
        seen.append(json.loads(user))
        return json.dumps(next(answers))
    monkeypatch.setattr(providers, "chat_complete", script)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Room", "", 0.0))
    out = sp.run_planner(cid, None, text="hello")
    transcript = seen[1]["transcript"]
    assert [t["tool"] for t in transcript] == ["inspect_needs", None, None]
    assert all("error" in t["result"] for t in transcript[1:])
    assert out["calls"] == 1 and out["reply"] == "done"


def test_the_same_sentence_granted_twice_is_one_mandate(temp_db):
    """A model re-emits a grant on every step of a reply it is still working
    (chat 111, 2026-09-03: two rows for one sentence). The store answers
    the same row for the same active sentence and scope."""
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Room", "", 0.0))
    a = md.grant_mandate(cid, None, text="You may plan rooms ahead of me.",
                         capabilities=["plan_rooms"], scope="the town")
    b = md.grant_mandate(cid, None, text="you may plan rooms ahead of me.",
                         capabilities=["plan_rooms"], scope="The town")
    assert a["uid"] == b["uid"]
    assert len(md.active_mandates(cid, None)) == 1
    c = md.grant_mandate(cid, None, text="You may plan rooms ahead of me.",
                         capabilities=["plan_rooms"], scope="the harbour")
    assert c["uid"] != a["uid"]


def test_an_operation_may_spell_its_kind_as_kind_and_a_refusal_names_the_shape(temp_db):
    """Four live drafts were refused with a message that named neither the
    key the kind goes under nor the fields (chat 111, 2026-09-03)."""
    from story.plot_packages import (OPERATION_FIELDS, OPERATIONS,
                                     draft_operation, new_package,
                                     preview_package)
    from story.room_tools import TOOL_INDEX
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Room", "", 0.0))
    pkg = new_package(cid, title="Morning", premise="p")
    # An empty package validates with a warning that says it changes nothing.
    assert any("no operations" in w for w in preview_package(cid, pkg["uid"])["warnings"])
    pkg = draft_operation(cid, pkg["uid"], {
        "kind": "plan_entity", "name": "Marta", "brief": {"where": "hall"}})
    assert pkg["operations"][0]["op"] == "plan_entity"
    assert pkg["operations"][0]["kind"] == "person"
    with pytest.raises(ValueError) as exc:
        draft_operation(cid, pkg["uid"], {"rooms": {"hall": {}}})
    assert "`op` names its kind" in str(exc.value)
    assert set(OPERATION_FIELDS) == set(OPERATIONS)
    description = TOOL_INDEX["draft_operation"]["description"]
    assert all(kind in description for kind in OPERATIONS)


def test_a_shapeless_output_is_reported_and_the_loop_goes_on(temp_db, monkeypatch):
    """GLM 5.2, live (chat 111, 2026-09-03): a step drafting a whole package
    ran past the token ceiling; its truncated JSON parsed to {"text": ...},
    the loop read "no calls" as done and told the player the room had
    stopped at its budget. Now the model is told, and the next step runs.
    Arguments written beside the tool name are the arguments."""
    from agents import story_planner as sp
    from llm import providers
    seen = []
    answers = iter([
        {"text": "{\"calls\": [{\"tool\": \"draft_op"},
        {"calls": [{"tool": "inspect_needs", "frame": "x"}]},
        {"calls": [], "reply": "done"},
    ])
    def script(role, system, user, **kw):
        seen.append(json.loads(user)); return json.dumps(next(answers))
    monkeypatch.setattr(providers, "chat_complete", script)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Room", "", 0.0))
    out = sp.run_planner(cid, None, text="hello")
    assert out["reply"] == "done" and out["steps"] == 3
    first = seen[1]["transcript"][0]
    assert first["tool"] is None and "cut off" in first["result"]["error"]
    called = seen[2]["transcript"][-1]
    assert called["tool"] == "inspect_needs" and called["args"] == {"frame": "x"}


def test_a_round_that_judged_and_said_nothing_did_not_stop_at_a_budget(
        temp_db, scripted, monkeypatch):
    """Bench, chat 114: a deliberation round answered verdicts with no reply
    and the thread told the player the room had stopped at its budget. A
    task that finishes unstopped posts no line; a reply owes the player a
    truthful one."""
    cid, _ = _story(temp_db)
    scripted({"verdicts": [{"proposal_uid": "prop_x", "verdict": "accept",
                            "reason": "fits"}]})
    out = sp._run_task(cid, None, {"kind": "deliberate", "round": 1, "rounds": 2,
                                   "dial": 2, "proposals": []}, base_turn=2)
    assert out["stopped"] is None
    assert out["reply"] == ""
    assert out["verdicts"][0]["verdict"] == "accept"
    scripted({"status_line": "Reading."})
    out = sp.run_planner(cid, None, text="anything there?")
    assert out["stopped"] is None
    assert out["reply"] == sp.SILENT_LINE
    assert sp.BOUNDED_LINE not in out["reply"]
