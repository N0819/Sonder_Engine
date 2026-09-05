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
    assert shown[0]["tool"] == "inspect_clock" and shown[0]["result"] == {"in_payload": "clock"}
    assert script.payloads[1]["clock"]["turn_idx"] == 2
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


# ---------------------------------------------------------------------------
# What balloons: the thread and the transcript (measured 2026-09-04, chat 114)
# ---------------------------------------------------------------------------

def _big(chars, tag):
    return {"tag": tag, "rows": ["x" * 100] * (chars // 104)}


def test_a_dump_trims_the_largest_read_result_before_evicting_the_neighbours(
        temp_db, monkeypatch):
    """Chat 114, step 5 (2026-09-04): a 13k `inspect_rooms` echo at step 4 (11k here, under the tool cap)
    evicted seven smaller results from steps 1-3 -- the packages and plans
    the Planner had just read -- because the transcript fell off whole
    entries newest-first. Now the largest ALREADY-READ result is cut to a
    head before any entry is evicted; the newest step, which the model has
    not read yet, stays whole."""
    from story.room_tools import TOOL_INDEX
    small = ["inspect_packages", "inspect_plans", "inspect_charters", "inspect_events",
             "inspect_needs", "inspect_structures", "inspect_contradictions"]
    for name in small:
        monkeypatch.setitem(TOOL_INDEX[name], "handler",
                            lambda cid_, frame_id, _t=name, **kw: _big(3000, _t))
    monkeypatch.setitem(TOOL_INDEX["inspect_rooms"], "handler",
                        lambda cid_, frame_id, **kw: _big(11000, "rooms"))
    seen = []
    answers = iter([
        {"calls": [{"tool": n, "args": {}} for n in small[:3]]},
        {"calls": [{"tool": n, "args": {}} for n in small[3:5]]},
        {"calls": [{"tool": n, "args": {}} for n in small[5:]]},
        {"calls": [{"tool": "inspect_rooms", "args": {}}]},
        {"reply": "done"},
    ])

    def script(role, system, user, **kw):
        seen.append(json.loads(user))
        return json.dumps(next(answers))
    monkeypatch.setattr(providers, "chat_complete", script)
    cid, _ = _story(temp_db)
    sp.run_planner(cid, None, text="Plan the tenement.")
    shown = seen[4]["transcript"]
    assert len(json.dumps(shown, ensure_ascii=False)) <= sp.PLANNER_TRANSCRIPT_CHARS
    # Every neighbour is still there, in order, with its call intact.
    assert [e["tool"] for e in shown] == small + ["inspect_rooms"]
    # The dump the model has not read yet is whole; what it trimmed is the
    # largest of what the model already read, cut to a head that says how
    # much is gone.
    assert shown[-1]["result"]["tag"] == "rooms"
    trimmed = [e for e in shown if "trimmed" in e["result"]]
    assert trimmed and all(e["tool"] in small for e in trimmed)
    for e in trimmed:
        assert len(e["result"]["head"]) == sp.PLANNER_TRIM_HEAD_CHARS
        assert e["result"]["trimmed"] > 0
    # Not every neighbour had to go: the trim stops when the transcript fits.
    assert any("trimmed" not in e["result"] for e in shown[:-1])


def test_the_trim_reaches_the_newest_step_only_when_nothing_older_is_left():
    """One step that alone outgrows the transcript is trimmed too, largest
    first; eviction is the last resort and takes the oldest."""
    transcript = [{"tool": "a", "args": {}, "result": _big(9000, "a"), "step": 1},
                  {"tool": "b", "args": {}, "result": _big(9000, "b"), "step": 1},
                  {"tool": "c", "args": {}, "result": _big(9000, "c"), "step": 1}]
    shown, whole = sp._shown_transcript(transcript, cap=20_000)
    assert [e["tool"] for e in shown] == ["a", "b", "c"]
    assert sum("trimmed" in e["result"] for e in shown) == 1
    assert whole == {i for i, e in enumerate(shown) if "trimmed" not in e["result"]}
    # A cap no head fits under evicts, oldest first.
    shown, whole = sp._shown_transcript(transcript, cap=sp.PLANNER_TRIM_HEAD_CHARS * 2)
    assert [e["tool"] for e in shown] == ["c"]


def test_an_identical_call_is_a_pointer_while_its_answer_is_still_in_view(
        temp_db, monkeypatch):
    """Chat 114 called `inspect_clock` five times per reply and `inspect_rooms`
    three; each echo was a full copy. A repeat of a call whose answer is
    unchanged and still shown is answered with the step to look at; a repeat
    whose answer moved, or whose earlier copy fell out of view, is shown
    again in full."""
    from story.room_tools import TOOL_INDEX
    state = {"n": 0}

    def needs(cid_, frame_id, **kw):
        return {"needs": ["rope"] * state["n"]}
    monkeypatch.setitem(TOOL_INDEX["inspect_needs"], "handler", needs)
    monkeypatch.setitem(TOOL_INDEX["inspect_rooms"], "handler",
                        lambda cid_, frame_id, **kw: _big(11000, "rooms"))
    seen = []
    answers = iter([
        {"calls": [{"tool": "inspect_needs", "args": {}},
                   {"tool": "inspect_needs", "args": {"kind": "room"}}]},
        {"calls": [{"tool": "inspect_needs", "args": {}}]},          # same -> pointer
        lambda p: state.update(n=1) or {"calls": [{"tool": "inspect_needs", "args": {}}]},  # moved
        {"calls": [{"tool": "inspect_rooms", "args": {}}] * 2},        # twice in one step
        {"reply": "done"},
    ])

    def script(role, system, user, **kw):
        payload = json.loads(user)
        seen.append(payload)
        step = next(answers)
        return json.dumps(step(payload) if callable(step) else step)
    monkeypatch.setattr(providers, "chat_complete", script)
    cid, _ = _story(temp_db)
    sp.run_planner(cid, None, text="hi")
    t = seen[4]["transcript"]
    assert [e["tool"] for e in t] == ["inspect_needs"] * 4 + ["inspect_rooms"] * 2
    assert t[0]["result"] == {"needs": []} and t[1]["result"] == {"needs": []}
    assert t[2]["result"] == {"see_step": 1}
    assert t[3]["result"] == {"needs": ["rope"]}
    assert t[4]["result"]["tag"] == "rooms" and t[5]["result"] == {"see_step": 4}


def test_a_repeat_of_a_call_that_fell_out_of_view_is_shown_again(temp_db, monkeypatch):
    """The pointer is only offered when the referent is still shown whole:
    a re-read of a trimmed or evicted result is a fair request."""
    from story.room_tools import TOOL_INDEX
    monkeypatch.setitem(TOOL_INDEX["inspect_rooms"], "handler",
                        lambda cid_, frame_id, **kw: _big(11000, "rooms"))
    monkeypatch.setitem(TOOL_INDEX["inspect_charters"], "handler",
                        lambda cid_, frame_id, **kw: _big(11000, "charters"))
    monkeypatch.setattr(sp, "PLANNER_TRANSCRIPT_CHARS", 15_000)
    seen = []
    answers = iter([
        {"calls": [{"tool": "inspect_rooms", "args": {}}]},
        {"calls": [{"tool": "inspect_charters", "args": {}}]},   # rooms is trimmed now
        {"calls": [{"tool": "inspect_rooms", "args": {}}]},      # so this is a re-read
        {"reply": "done"},
    ])

    def script(role, system, user, **kw):
        seen.append(json.loads(user))
        return json.dumps(next(answers))
    monkeypatch.setattr(providers, "chat_complete", script)
    cid, _ = _story(temp_db)
    sp.run_planner(cid, None, text="hi")
    assert "trimmed" in seen[2]["transcript"][0]["result"]
    last = seen[3]["transcript"][-1]
    assert last["tool"] == "inspect_rooms" and "see_step" not in last["result"]


def test_the_payload_keyed_tools_answer_with_a_pointer_not_a_copy(temp_db, scripted):
    """`inspect_clock` and `inspect_packages` return what every payload
    already carries under `clock` and `packages`, rebuilt each step; the
    echo is the key to read, and a refusal is still a refusal."""
    cid, _ = _story(temp_db)
    script = scripted(
        {"calls": [{"tool": "inspect_clock", "args": {}},
                   {"tool": "new_package", "args": {"title": "Bell"}},
                   {"tool": "inspect_packages", "args": {"status": "draft"}},
                   {"tool": "inspect_packages", "args": {"junk": 1}}]},
        {"reply": "done"})
    sp.run_planner(cid, None, text="hi")
    t = script.payloads[1]["transcript"]
    assert t[0]["result"] == {"in_payload": "clock"}
    assert script.payloads[1]["clock"]["turn_idx"] == 2
    assert t[2]["result"] == {"in_payload": "packages"}
    assert script.payloads[1]["packages"][0]["title"] == "Bell"
    assert "error" in t[3]["result"]
    from story.room_tools import tool_manifest
    keyed = {t["name"]: t.get("payload_key") for t in tool_manifest()}
    assert keyed["inspect_clock"] == "clock" and keyed["inspect_packages"] == "packages"
    assert keyed["inspect_rooms"] is None


def test_the_thread_shows_the_players_words_whole_and_the_rooms_older_lines_folded(
        temp_db, scripted, monkeypatch):
    """Chat 114 (2026-09-04): 20.2k of a 22.2k `conversation` key was the
    Planner's own prior replies, shown whole on every step. The bible is the
    memory that folds them; the thread carries each older room line as its
    first sentence, the newest line in each voice whole (a follow-up needs
    its referent), and the player's every word."""
    cid, _ = _story(temp_db)
    long_reply = ("The room planned the harbour. " + "It spread the wharf over "
                  "three rooms and seated a clerk. " * 40)
    first_id = room.add_message(cid, None, "player", "Plan a harbour for me.")["id"]
    room.add_message(cid, None, "planner", long_reply)
    room.add_message(cid, None, "player", "Now the tenement? A poor one.")
    room.add_message(cid, None, "planner", "A tenement it is! Four floors. Nine doors.")
    room.add_message(cid, None, "dramaturge", "Proposed: a fire on the third floor. Why now.")
    room.add_message(cid, None, "planner", "The fire is refused; the floor is stone.")
    script = scripted({"reply": "ok"})
    sp.run_planner(cid, None, text="hi")
    conv = script.payloads[0]["conversation"]
    texts = [m["text"] for m in conv]
    assert texts[0] == "Plan a harbour for me." and texts[2] == "Now the tenement? A poor one."
    assert texts[1] == "The room planned the harbour."
    assert conv[1]["folded_chars"] == len(long_reply.strip()) - len(texts[1])
    assert texts[3] == "A tenement it is!" and conv[3]["folded_chars"] > 0
    # The newest line in each voice is whole.
    assert texts[4] == "Proposed: a fire on the third floor. Why now."
    assert texts[5] == "The fire is refused; the floor is stone." and "folded_chars" not in conv[5]
    assert all("folded_chars" not in m for m in conv if m["role"] == "player")
    # A sentence-less line folds to the head cap.
    room.add_message(cid, None, "planner", "x" * 2000)
    room.add_message(cid, None, "planner", "Last word.")
    script = scripted({"reply": "ok"})
    sp.run_planner(cid, None, text="hi")
    conv = script.payloads[0]["conversation"]
    assert len(conv[-2]["text"]) == sp.PLANNER_FOLDED_LINE_CHARS
    # The chars cap evicts the OLDEST lines whole, beside the line window.
    monkeypatch.setattr(sp, "PLANNER_HISTORY_CHARS", 300)
    script = scripted({"reply": "ok"})
    sp.run_planner(cid, None, text="hi")
    conv = script.payloads[0]["conversation"]
    assert len(json.dumps(conv, ensure_ascii=False)) <= 300
    assert conv[-1]["text"] == "Last word." and conv[0]["id"] > first_id


# ---------------------------------------------------------------------------
# What the reply states, and what it read to know it
# ---------------------------------------------------------------------------
#
# `story/room_citations.py` had the contract and the check, and nothing
# emitted a claim -- so every reply read `stated_nothing`, which is honest
# and is not a pass. These hold the emitting end: the room is GIVEN the
# contract, and what it answers under it reaches the panel's envelope.


def test_the_planner_is_given_the_citation_contract(temp_db, scripted):
    """The sentence the room is held to is the one it is shown, because both
    are `room_citations.CONTRACT_TEXT` and there is only the one string."""
    from story.room_citations import CONTRACT_TEXT

    cid, _turn_id = _story(temp_db)
    script = scripted({"reply": "ok"})
    sp.run_planner(cid, None, text="what is going on?")
    assert CONTRACT_TEXT in script.systems[0]


def test_the_reply_enumerates_what_it_stated(temp_db, scripted):
    """The envelope carries `claims`; nothing is judged here. The check runs
    where the ledger of rows read lives, which for a streamed reply is a
    worker thread and never this one."""
    cid, _turn_id = _story(temp_db)
    scripted({"reply": "Two crates are bonded.",
              "claims": [{"text": "Two crates are bonded",
                          "cites": ["plot:crates"]},
                         {"text": "A third may be coming", "proposal": True}]})
    out = sp.run_planner(cid, None, text="what is going on?")
    assert out["claims"] == [
        {"text": "Two crates are bonded", "cites": ["plot:crates"],
         "proposal": False},
        {"text": "A third may be coming", "cites": [], "proposal": True}]


def test_a_claim_naming_a_row_the_reply_read_stands_and_one_naming_none_is_demoted(
        temp_db, scripted):
    """End to end through the seam the panel uses, with the REAL Planner
    seated: the room reads a row, states two things, and only the one it
    can name a row for keeps its authority. The other keeps its sentence."""
    cid, _turn_id = _story(temp_db)
    scripted(
        {"calls": [{"tool": "new_package",
                    "args": {"title": "The courier", "premise": "someone comes"}}]},
        lambda p: {"reply": "A courier is in motion; he is late by now.",
                   "claims": [
                       {"text": "A courier is in motion",
                        "cites": [_last_uid(p)]},
                       {"text": "He is late", "cites": ["plot:lateness"]}]},
    )
    room.seat_planner(sp.planner_reply)
    try:
        out = room.converse(cid, None, "what is going on?")
    finally:
        room.seat_planner(None)

    found = out["citations"]
    assert found["asserted"] == ["A courier is in motion"]
    assert found["unsupported"] == ["He is late"]
    # THE DEMOTION, which is the whole enforcement: the sentence survives,
    # among the proposals rather than among the things the world says.
    assert found["proposed"] == ["He is late"]
    assert not found["stated_nothing"]
    assert "he is late by now" in out["replies"][-1]["text"]
