"""The opening is planned before the Director runs
(`docs/design/DESIGN_OPENING_PLAN.md`, owner decisions 2026-09-16).

Measured on the owner's chat 126: the Story Planner drafted the parlor's
rooms at turn -1, asked for `request_location`, nobody answered, the package
never published, and the opening minted its own rooms beside the plan. What
holds now: the launch mints a standing opening mandate, the planner runs one
bounded pass that cannot ask and cannot request a location, `place_at_opening`
says where each present body stands, a package published then is visible to
turn 0, and the establish stage places bodies where the plan put them.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import wget
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm import providers
from story import mandates as md
from story import opening_plan as op
from story import room_conversation as room
from story.plot_packages import (
    OPERATIONS, authority_errors, draft_operation, get_package, new_package,
    publish_package, validate_package,
)
from agents import story_planner as sp

PLAYER = "The Stranger"     # the default persona: no persona row needed
CAST = "Mirelle"


def _chat(db, *, scenario="A parlor in the supernatural quarter.", cast=True):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Opening", scenario, time.time()))
    if cast:
        char = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                     (CAST, json.dumps({"identity": {"name": CAST}}), time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
              (cid, char))
    return cid


def _rooms_op():
    return {"op": "plan_rooms",
            "structure": {"key": "parlor", "name": "The Parlor"},
            "rooms": {
                "reception": {"name": "Reception Parlor",
                              "purpose": "where clients are received",
                              "access": "public",
                              "adjacent": [{"to": "treatment", "barrier": "closed_door",
                                            "bearing": "north"}],
                              "frontier": []},
                "treatment": {"name": "Treatment Room",
                              "purpose": "where the proprietor works",
                              "access": "by invitation",
                              "adjacent": [{"to": "reception", "barrier": "closed_door",
                                            "bearing": "south"}],
                              "frontier": []},
            }}


def _planner_package(cid, ops):
    pkg = new_package(cid, title="The opening", premise="Where it starts.",
                      created_by="story_planner")
    for one in ops:
        draft_operation(cid, pkg["uid"], one)
    return pkg["uid"]


def _ctx(cid, idx=0):
    return PipelineContext(
        chat=ChatData(id=cid, name="Opening", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=idx, player_input="",
                      created=time.time(), frame_id=None),
        cast=[], input="")


# ---------------------------------------------------------------------------
# The vocabulary and the operation
# ---------------------------------------------------------------------------

def test_the_capability_and_the_operation_exist():
    assert "place_at_opening" in md.MANDATE_CAPABILITIES
    assert "place_at_opening" in OPERATIONS and not OPERATIONS["place_at_opening"]["long"]
    assert set(op.OPENING_CAPABILITIES) == {"plan_rooms", "place_at_opening",
                                            "director_note"}
    # A charter is an option the player takes, never one the planner assumes.
    assert "request_location" not in op.OPENING_CAPABILITIES
    assert "plan_entity" not in op.OPENING_CAPABILITIES


def test_a_placement_names_a_present_body_and_a_room_the_plan_holds(temp_db):
    cid = _chat(temp_db)
    op.mint_opening_mandate(cid)
    uid = _planner_package(cid, [
        _rooms_op(),
        {"op": "place_at_opening", "who": "Nobody Here", "room": "reception"},
        {"op": "place_at_opening", "who": CAST, "room": "the_moon"},
    ])
    verdict = validate_package(cid, uid)
    assert not verdict["ok"]
    joined = " ".join(verdict["errors"])
    assert "nobody present is called 'Nobody Here'" in joined
    assert "'the_moon', which exists nowhere" in joined
    # The present bodies are named in the refusal, so the planner can
    # correct the spelling rather than guess again.
    assert PLAYER in joined and CAST in joined


def test_a_placement_publishes_at_turn_minus_one_and_lands_the_row(temp_db):
    cid = _chat(temp_db)
    op.mint_opening_mandate(cid)
    uid = _planner_package(cid, [
        _rooms_op(),
        {"op": "place_at_opening", "who": PLAYER, "room": "reception",
         "at": "just inside the entrance door"},
        {"op": "place_at_opening", "who": CAST.lower(), "room": "reception"},
        {"op": "director_note", "text": "The parlor is Mirelle's; the treatment "
                                        "room stays shut until she opens it."},
    ])
    verdict = validate_package(cid, uid)
    assert verdict["ok"], verdict["errors"]
    out = publish_package(cid, uid, expected_revision=get_package(cid, uid)["revision"])
    # No turn row yet: published at -1, visible to the opening.
    assert out["published_turn"] == -1 and out["visible_from_turn"] == 0
    placed = op.opening_placements(cid)
    assert placed == {
        PLAYER: {"room": "reception", "at": "just inside the entrance door"},
        CAST: {"room": "reception", "at": ""},     # the display spelling wins
    }
    # The mandate the engine minted covers exactly this package and lapses
    # with the opening.
    rows = md.active_mandates(cid, None, turn_idx=0)
    assert [r["scope"] for r in rows] == [op.OPENING_MANDATE_SCOPE]
    assert md.active_mandates(cid, None, turn_idx=1) == []


def test_the_opening_mandate_refuses_a_location_request(temp_db):
    cid = _chat(temp_db)
    op.mint_opening_mandate(cid)
    uid = _planner_package(cid, [
        {"op": "request_location", "request": {"name": "The Quarter",
                                               "brief": "a district"}},
    ])
    errors = authority_errors(cid, None, get_package(cid, uid))
    assert errors and "request_location" in errors[0]


def test_minting_the_mandate_twice_is_one_row(temp_db):
    cid = _chat(temp_db)
    a = op.mint_opening_mandate(cid)
    b = op.mint_opening_mandate(cid)
    assert a["uid"] == b["uid"]
    assert len(md.active_mandates(cid, None, turn_idx=0)) == 1


# ---------------------------------------------------------------------------
# The regime
# ---------------------------------------------------------------------------

class Script:
    def __init__(self, *steps):
        self.steps = list(steps)
        self.payloads = []

    def __call__(self, role, system, user, **kw):
        assert role == sp.PLANNER_ROLE
        payload = json.loads(user)
        self.payloads.append(payload)
        if not self.steps:
            return json.dumps({"reply": "nothing more"})
        step = self.steps.pop(0)
        return json.dumps(step(payload) if callable(step) else step)


@pytest.fixture
def scripted(monkeypatch):
    def install(*steps):
        script = Script(*steps)
        monkeypatch.setattr(providers, "chat_complete", script)
        return script
    return install


def test_the_opening_regime_asks_nothing_and_runs_one_pass(temp_db, scripted):
    cid = _chat(temp_db)
    script = scripted(
        {"calls": [{"tool": "inspect_rooms", "args": {}}],
         "questions": ["Is the parlor a charter?"], "reply": None},
        {"reply": "The parlor is planned.", "status_line": "The opening is planned.",
         "questions": ["Shall I make it an institution?"]},
    )
    row = sp.run_opening_plan(cid, None, passage="You step into a parlor.")
    assert row["error"] == "" and row["stopped"] is None
    assert row["calls"] == 1 and row["steps"] == 2
    # Neither question reached the status row; both are noted.
    assert room.status(cid)["questions"] == []
    assert [n for n in row["notes"] if n.startswith("question not asked")] and \
        len([n for n in row["notes"] if "question not asked" in n]) == 2
    # The task the planner saw: the passage, who is present, the regime.
    task = script.payloads[0]["task"]
    assert task["kind"] == "opening" and task["passage"] == "You step into a parlor."
    assert task["present"] == [PLAYER, CAST]
    assert script.payloads[0]["budget"]["regime"] == "opening"
    assert script.payloads[0]["budget"]["steps"] == sp.OPENING_STEPS
    # The reply is the planner's own line in the room thread.
    assert any(m["text"] == "The parlor is planned." and m["role"] == "planner"
               for m in room.messages(cid))


def test_a_plan_that_fails_never_fails_the_launch(temp_db, monkeypatch):
    cid = _chat(temp_db)

    def boom(*a, **k):
        raise RuntimeError("no provider")
    monkeypatch.setattr(sp, "run_planner", boom)
    row = sp.run_opening_plan(cid, None, passage="x")
    assert row["error"].startswith("RuntimeError")
    assert row["published"] == [] and row["placements"] == {}
    assert wget(cid, op.OPENING_PLAN_KEY, {})["error"] == row["error"]


# ---------------------------------------------------------------------------
# The reader: the establish stage places bodies where the plan put them
# ---------------------------------------------------------------------------

def test_the_establish_stage_moves_a_placed_body_to_the_plans_room(temp_db):
    from agents.director import _enforce_opening_placements, _opening_rooms

    cid = _chat(temp_db)
    op.mint_opening_mandate(cid)
    uid = _planner_package(cid, [
        _rooms_op(),
        {"op": "place_at_opening", "who": PLAYER, "room": "reception"},
        {"op": "place_at_opening", "who": CAST, "room": "treatment"},
    ])
    validate_package(cid, uid)
    publish_package(cid, uid, expected_revision=get_package(cid, uid)["revision"])
    ctx = _ctx(cid)
    # The opening's rooms are the plan's, before any string match.
    assert _opening_rooms(ctx) == ["reception", "treatment"]
    # The Director minted a like room beside the plan and put the player in
    # it, and left the cast member nowhere.
    out = {"rooms": {"velvet_parlor": {"name": "Velvet Parlor", "desc": "Silk."}},
           "positions": {"the stranger": "velvet_parlor"}}
    _enforce_opening_placements(ctx, out)
    assert out["positions"] == {"the stranger": "reception", CAST: "treatment"}
    assert [w for w in ctx.warnings if "opening placement" in w
            and "'velvet_parlor'" in w]
    # A placement naming a room nothing holds is left alone, and said.
    op.record_placement(cid, None, PLAYER, "attic")
    out2 = {"rooms": {}, "positions": {PLAYER: "reception"}}
    _enforce_opening_placements(_ctx(cid), out2)
    assert out2["positions"][PLAYER] == "reception"


def test_without_a_plan_the_opening_reads_as_it_always_did(temp_db):
    from agents.director import _enforce_opening_placements, _opening_rooms

    cid = _chat(temp_db, cast=False)
    ctx = _ctx(cid)
    assert _opening_rooms(ctx) == []
    out = {"rooms": {}, "positions": {PLAYER: "somewhere"}}
    _enforce_opening_placements(ctx, out)
    assert out["positions"] == {PLAYER: "somewhere"} and ctx.warnings == []


# ---------------------------------------------------------------------------
# The two launches plan before the turn row exists
# ---------------------------------------------------------------------------

def test_the_scenario_launch_plans_on_the_first_turn_only(temp_db, monkeypatch):
    from web import app as app_module

    cid = _chat(temp_db, scenario="A parlor.")
    seen = []

    def fake_plan(cid_, frame_id=None, *, passage):
        seen.append((passage, temp_db.q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=?",
                                        (cid_,), one=True)["n"]))
        return {}
    monkeypatch.setattr(sp, "run_opening_plan", fake_plan)
    app_module._plan_opening(cid, None, "I open the door.")
    assert seen == [("A parlor.\n\nI open the door.", 0)]


def test_the_greeting_launch_plans_before_the_turn_row(temp_db, monkeypatch):
    from story import greetings, importers

    monkeypatch.setattr(greetings, "extract_greeting",
                        lambda sheet, prose: {"knowledge_seeds": [], "time": "now"})
    monkeypatch.setattr(greetings, "_run_pipeline", lambda cid, tid: iter(()))
    seen = []

    def fake_plan(cid_, frame_id=None, *, passage):
        seen.append((passage, temp_db.q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=?",
                                        (cid_,), one=True)["n"]))
        return {}
    monkeypatch.setattr(sp, "run_opening_plan", fake_plan)
    char_id, _ = importers.import_character(
        {"name": "Mirelle", "description": "a proprietor",
         "first_mes": "\"Welcome, {{user}},\" she says from the bench."},
        reinterpret=False)
    persona_id, _ = importers.import_persona({"name": "Hinami"}, reinterpret=False)
    chat_id, tid = greetings.start_story(char_id, persona_id)
    assert len(seen) == 1
    passage, turns_then = seen[0]
    assert turns_then == 0 and "Hinami" in passage
    assert temp_db.q("SELECT idx FROM turns WHERE id=?", (tid,), one=True)["idx"] == 0


def test_a_placement_may_be_drafted_before_the_rooms_it_names(temp_db):
    """A PACKAGE LANDS ALL AT ONCE, SO ITS ROOMS EXIST FOR ALL OF IT.

    Measured on chat 131 (2026-09-16). The opening planner drafted two
    `place_at_opening` at `reception`, then a `plan_rooms` planting
    `reception`, and the preview -- which taught itself about planted rooms
    only from `plan_rooms` operations it had already walked past -- refused
    both placements with "exists nowhere and this package does not plant".
    That sentence is false: the package plants it, two operations later. The
    planner then spent seventeen calls and sixteen steps drafting, removing
    and re-drafting rooms it had already got right, and stopped without
    publishing a package that was correct from revision four.
    """
    cid = _chat(temp_db)
    op.mint_opening_mandate(cid)
    # The order chat 131 drafted in: who stands where, THEN the rooms.
    uid = _planner_package(cid, [
        {"op": "place_at_opening", "who": PLAYER, "room": "reception"},
        {"op": "place_at_opening", "who": CAST, "room": "treatment"},
        {"op": "director_note", "text": "The parlor is Mirelle's."},
        _rooms_op(),
    ])
    verdict = validate_package(cid, uid)
    assert verdict["ok"], verdict["errors"]
    publish_package(cid, uid, expected_revision=get_package(cid, uid)["revision"])
    assert op.opening_placements(cid) == {
        PLAYER: {"room": "reception", "at": ""},
        CAST: {"room": "treatment", "at": ""},
    }


def test_a_placement_at_a_room_nobody_plants_is_still_refused(temp_db):
    """The widening is package-wide, not a blanket pass: a room neither the
    world nor this package holds is still nowhere."""
    cid = _chat(temp_db)
    op.mint_opening_mandate(cid)
    uid = _planner_package(cid, [
        {"op": "place_at_opening", "who": PLAYER, "room": "the_moon"},
        _rooms_op(),
    ])
    verdict = validate_package(cid, uid)
    assert not verdict["ok"]
    assert "'the_moon', which exists nowhere" in " ".join(verdict["errors"])


def test_the_row_records_what_the_room_did(temp_db, scripted):
    """A planner exchange is captured against a turn, and the opening plan
    runs before turn 0 exists, so its calls leave no trace anywhere else.
    Chat 131 spent seventeen calls and published nothing, and the only
    record of what it had been doing was the package's own revision
    history. The row carries a tool-by-tool trace now, refusals included.
    """
    cid = _chat(temp_db)
    scripted(
        {"calls": [{"tool": "inspect_rooms", "args": {}},
                   {"tool": "no_such_tool", "args": {}}], "reply": None},
        {"calls": [{"tool": "new_package",
                    "args": {"title": "Opening", "premise": "p"}}],
         "reply": None},
        {"reply": "done."},
    )
    row = sp.run_opening_plan(cid, None, passage="You step into a parlor.")
    tools = [t["tool"] for t in row["trace"]]
    assert tools == ["inspect_rooms", "no_such_tool", "new_package"]
    failed = [t for t in row["trace"] if t.get("error") or t.get("refused")]
    assert [t["tool"] for t in failed] == ["no_such_tool"]
    # And it survives onto the stored row, not just the return value.
    assert wget(cid, op.OPENING_PLAN_KEY, {})["trace"] == row["trace"]


def test_the_room_can_read_minds_before_the_first_beat(temp_db):
    """`inspect_minds` is the first tool the opening planner reaches for,
    and it ran before any turn row existed. A belief's decay is measured in
    turns elapsed, and the subtraction coerced a `turn_idx` of None: chat
    132 logged "story planner tool inspect_minds failed: int() argument
    must be a string ... not 'NoneType'" and the Room spent a call working
    around a tool that should have answered. Before the first beat, nothing
    has elapsed."""
    from mind.theory_of_mind import mind_models_for_payload
    from story.room_tools import run_tool

    models = {"m1": {"hypotheses": [{"kind": "goal", "confidence": 0.8,
                                     "claim": "she is waiting for someone",
                                     "last_updated_turn": 0}]}}
    # The call that raised, with no turn index at all.
    assert mind_models_for_payload(models, None) is not None

    cid = _chat(temp_db)
    assert not temp_db.q("SELECT id FROM turns WHERE chat_id=?", (cid,))
    out = run_tool(cid, "inspect_minds", {}, frame_id=None,
                   actor="story_planner")
    assert out["turn_idx"] is None and isinstance(out["minds"], list)
