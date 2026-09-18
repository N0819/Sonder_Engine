"""The Writers' Room is asked before the story starts.

`docs/design/DESIGN_ROOM_PRELUDE.md`. Two things are pinned here, and they
are different claims:

1. THE PAUSE. A launch that takes the prelude creates the story and stops --
   no location generated, no turn written, the pending launch kept whole on
   the chat -- and `begin` runs the rest from what was stored rather than
   from anything the browser still holds.
2. THE DESIGN. The inhabited place a story opens on is designed by the Room,
   a piece at a time, through its own tools -- not asked for as one JSON
   object from the `utility` role. The plan is checked against the closure
   that will land it before it can be submitted, and a pass that submits
   nothing fails the generation rather than falling back to the call it
   replaces.
"""

from __future__ import annotations

import copy
import time

import pytest

from core import db
from story import prelude


@pytest.fixture()
def chat(temp_db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("A story", "A wet street outside a shut parlour.", time.time()))
    return cid


# -- the pause --------------------------------------------------------------

def test_a_pending_setup_holds_the_story_at_the_door(chat):
    assert prelude.awaiting_begin(chat) is False
    prelude.record_setup(chat, "greeting", {"char_id": 1, "persona_id": 2})
    assert prelude.awaiting_begin(chat) is True
    assert prelude.pending_setup(chat)["kind"] == "greeting"
    assert prelude.pending_setup(chat)["args"]["char_id"] == 1


def test_a_story_that_has_a_turn_is_not_waiting_whatever_the_row_says(chat):
    """The turn is the fact; the setup row is a claim about it.

    A launch that wrote turn 0 and then failed before clearing its setup
    would otherwise hold a running story at the door for good -- and the
    composer would stay hidden behind a begin button that has nothing left
    to do."""
    prelude.record_setup(chat, "greeting", {"char_id": 1})
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (chat, 0, "", time.time()))
    assert prelude.awaiting_begin(chat) is False


def test_begin_refuses_a_story_with_no_launch_waiting(chat):
    with pytest.raises(ValueError):
        prelude.begin_story(chat)


def test_the_setup_survives_a_begin_that_failed(chat, monkeypatch):
    """Cleared only on success, because the failed-setup path is what picks
    a broken launch up and it needs the arguments to retry with."""
    prelude.record_setup(chat, "greeting", {"char_id": 7, "persona_id": 3})

    def boom(*a, **k):
        raise RuntimeError("the model was down")

    monkeypatch.setattr("story.greetings.start_story", boom)
    with pytest.raises(RuntimeError):
        prelude.begin_story(chat)
    assert prelude.pending_setup(chat)["args"]["char_id"] == 7


# -- what the player said ---------------------------------------------------

def test_the_prelude_reads_the_players_lines_and_not_the_rooms(chat):
    from story import room_conversation as room

    room.add_message(chat, None, "planner", "What do you want from this one?")
    room.add_message(chat, None, "player", "Rain, and a place that is closing.")
    room.add_message(chat, None, "planner", "Understood.")
    assert prelude.player_wants(chat) == ["Rain, and a place that is closing."]


def test_a_line_typed_after_the_story_began_is_not_a_prelude_line(chat):
    """A prelude ends when the player says go. Everything after it is
    ordinary room conversation about a story that is already running, and
    handing it back to the opening plan as a launch instruction would make
    the room's whole later history rewrite the story's ground."""
    from story import room_conversation as room

    room.add_message(chat, None, "player", "Start it on the docks.")
    prelude.record_prelude(chat, began=time.time())
    time.sleep(0.01)
    room.add_message(chat, None, "player", "Now have someone knock.")
    assert prelude.player_wants(chat) == ["Start it on the docks."]


# -- the location is designed, not requested ---------------------------------

def test_the_quick_start_routes_the_town_to_the_room_and_not_to_utility():
    """Owner, 2026-09-17: designing a charter location and its map is the
    Writers' Room's work, and the one-shot `utility` JSON call it replaces is
    "wildly inefficient in comparison to the writers room multi tool call
    planing and execution". Both quick starts pass the Room as the planner;
    neither reaches `propose_town`'s own model call any more."""
    import inspect

    from story import greetings, prelude as prelude_module

    for source in (inspect.getsource(greetings.start_story),
                   inspect.getsource(prelude_module.begin_story)):
        assert "room_town_planner" in source
        assert "town_planner=" in source


def test_the_planner_is_handed_the_towns_payload_and_its_plan_is_used(
        chat, monkeypatch):
    """THE WIRING, exercised rather than grepped for.

    The string test above passed while this was broken. `room_town_planner`
    was a factory over the closure and `_plan_lived_location` called it WITH
    the closure to get the model call, so the Room ran with `closure_inputs`
    as its payload -- no brief, no lore, no constraints -- designed fourteen
    rooms out of nothing over 249 seconds, and handed back a plan that
    `propose_town` then tried to CALL: `TypeError: 'dict' object is not
    callable`, live on chat 149, 2026-09-17. Nothing short of running the
    seam catches that, because every name in it was spelled correctly.
    """
    from world import charter_runtime

    seen = {}
    town = {"name": "Vaunt's Yard", "structure": {"key": "waterfront"},
            "rooms": {"quay": {"name": "The quay", "purpose": "landing"}},
            "charters": []}

    def planner(payload, closure=None):
        seen["payload"] = copy.deepcopy(payload)
        seen["closure"] = copy.deepcopy(closure)
        return copy.deepcopy(town)

    monkeypatch.setattr("world.charter_generate.close_plan",
                        lambda plan, **kwargs: {"charters": {},
                                                "rooms": plan["rooms"],
                                                "structure": plan["structure"],
                                                "name": plan["name"]})
    row = db.q("SELECT * FROM chats WHERE id=?", (chat,), one=True)
    artifact = charter_runtime._plan_lived_location(
        chat,
        {"lore": ["a tidal river town"], "brief": "a customs house",
         "generate_history": False, "horizon_hours": 0.0,
         "population": 12},
        row, planner)

    # The payload is the TOWN's, the one the one-shot would have been sent.
    assert seen["payload"]["author_brief"] == "a customs house"
    assert seen["payload"]["lore"] == ["a tidal river town"]
    assert seen["payload"]["population"] == 12
    # And the closure arrives beside it, not in place of it.
    assert seen["closure"]["population"] == 12
    assert seen["closure"]["chat_id"] == chat
    # What it returned is what was planned.
    assert artifact["town"]["name"] == "Vaunt's Yard"


def test_the_room_drafts_the_prehistory_too(chat, monkeypatch):
    """The prehistory was a SECOND one-shot `utility` call, and on chat 149
    (2026-09-17) it is what actually failed a launch the Room had already
    designed correctly: a thinking-only model refused `reasoning_effort=
    'none'` with HTTP 400, then four calls spent the whole 4,000-token budget
    on traces and returned no content at all."""
    from world import charter_generate, charter_runtime

    history = {"eras": [{"name": "The permit years", "summary": "..."}],
               "interventions": [{"id": "i1", "op": "upkeep_shock",
                                  "at_hours": 40, "cause": "a storm"}]}

    def planner(payload, closure=None):
        assert closure["wants_history"] is True
        assert closure["horizon_hours"] == 720
        return {"name": "Vaunt's Yard", "structure": {"key": "waterfront"},
                "rooms": {"quay": {"name": "The quay"}}, "charters": [],
                "prehistory": copy.deepcopy(history)}

    def refuse(*a, **k):
        raise AssertionError("propose_history was called; the Room drafted one")

    monkeypatch.setattr(charter_generate, "propose_history", refuse)
    seen = {}

    def fake_close(plan, **kwargs):
        seen["history"] = kwargs.get("history")
        seen["plan_keys"] = sorted(plan)
        return {"charters": {}, "rooms": plan["rooms"],
                "structure": plan["structure"], "name": plan["name"]}

    monkeypatch.setattr(charter_generate, "close_plan", fake_close)
    row = db.q("SELECT * FROM chats WHERE id=?", (chat,), one=True)
    charter_runtime._plan_lived_location(
        chat, {"lore": [], "brief": "a port", "generate_history": True,
               "horizon_hours": 720}, row, planner)

    assert seen["history"] == history
    # And the carry key never reaches the closure as part of the plan.
    assert "prehistory" not in seen["plan_keys"]


def test_the_prehistory_carry_key_has_one_spelling():
    from story import location_design
    from world import charter_runtime

    assert location_design.PREHISTORY_KEY == charter_runtime._ROOM_PREHISTORY_KEY


def test_a_launch_that_wants_months_cannot_submit_without_them(chat):
    from story import location_design

    location_design.open_draft(chat, {"wants_history": True,
                                      "horizon_hours": 720})
    location_design.set_skeleton(chat, name="Yard", structure={"key": "w"},
                                 rooms={"quay": {"name": "Quay"}})
    location_design.set_charter(chat, {"key": "harbour"})
    result = location_design.check(chat)
    assert result["ok"] is False
    assert any("prehistory" in e for e in result["errors"])


def test_a_launch_that_wants_no_months_is_not_asked_for_any(chat):
    """A horizon of zero means the place exists and has not been lived
    through yet; the Room must not draft a past nobody asked to simulate."""
    from story import location_design

    location_design.open_draft(chat, {"wants_history": False})
    location_design.set_skeleton(chat, name="Yard", structure={"key": "w"},
                                 rooms={"quay": {"name": "Quay"}})
    location_design.set_charter(chat, {"key": "harbour"})
    result = location_design.check(chat)
    assert not any("prehistory" in e for e in result["errors"])


def test_the_review_closes_with_the_history_the_room_drafted(chat, monkeypatch):
    """The gap this note named in § 4a, closed by the same change: the launch
    closes with the history, so a review that closed without one was
    answering a slightly different question."""
    from story import location_design

    seen = {}

    def fake_close(plan, **kwargs):
        seen["history"] = kwargs.get("history")
        return {"charters": {}}

    monkeypatch.setattr("world.charter_generate.close_plan", fake_close)
    location_design.open_draft(chat, {"wants_history": True})
    location_design.set_skeleton(chat, name="Yard", structure={"key": "w"},
                                 rooms={"quay": {"name": "Quay"}})
    location_design.set_charter(chat, {"key": "harbour"})
    location_design.set_history(chat, eras=[{"name": "The permit years"}])
    location_design.check(chat)
    assert seen["history"]["eras"] == [{"name": "The permit years"}]


def test_the_shape_has_one_statement():
    """The Room and the one-shot are held to the same specification, because
    two copies of it would drift into a plan the Room wrote correctly and the
    closure refused."""
    from world import charter_generate

    assert charter_generate.plan_specification() is charter_generate._PLAN_SYSTEM


def test_a_pass_with_no_submitted_plan_raises_rather_than_falling_back(
        chat, monkeypatch):
    """Falling back to the one-shot would keep alive the thing this replaces.
    The caller is a location generation, which already keeps the story and
    offers a retry when it fails."""
    from agents import story_planner

    monkeypatch.setattr(story_planner, "run_planner",
                        lambda *a, **k: {"reply": "I had a look.", "calls": 3,
                                         "steps": 2, "stopped": "steps"})
    with pytest.raises(ValueError) as caught:
        story_planner.run_location_plan(
            chat, None, payload={"author_brief": "a port", "lore": []})
    assert "did not submit" in str(caught.value)


def test_the_draft_is_cleared_whatever_happened(chat, monkeypatch):
    from agents import story_planner
    from story import location_design

    monkeypatch.setattr(story_planner, "run_planner",
                        lambda *a, **k: {"reply": "", "calls": 0, "steps": 0})
    with pytest.raises(ValueError):
        story_planner.run_location_plan(
            chat, None, payload={"author_brief": "a port", "lore": []})
    assert location_design.is_open(chat) is False


def test_the_room_drafts_a_plan_in_pieces(chat, monkeypatch):
    """The whole point of the change: a map laid out over several calls and
    one institution per call, rather than one object asked for at once."""
    from agents import story_planner
    from story import location_design

    drafted = {}

    def fake_planner(cid, frame_id, *, task=None, regime=None, **kwargs):
        location_design.set_skeleton(
            cid, name="Vaunt's Yard", structure={"key": "waterfront"})
        location_design.set_skeleton(
            cid, rooms={"quay": {"name": "The quay", "purpose": "landing"}})
        location_design.set_skeleton(
            cid, rooms={"office": {"name": "Harbour office",
                                   "purpose": "permits"}})
        location_design.set_charter(chat, {"key": "harbour", "name": "Harbour"})
        drafted["plan"] = location_design.draft(cid)["plan"]
        # Submitted through the module rather than the tool, so the test is
        # about the drafting and not about the closure.
        row = location_design.draft(cid)
        row["checked"] = True
        location_design.save_draft(cid, row)
        location_design.submit(cid)
        return {"reply": "done", "calls": 6, "steps": 4}

    monkeypatch.setattr(story_planner, "run_planner", fake_planner)
    plan = story_planner.run_location_plan(
        chat, None, payload={"author_brief": "a port", "lore": []})
    assert plan["name"] == "Vaunt's Yard"
    assert sorted(plan["rooms"]) == ["office", "quay"]
    assert [c["key"] for c in plan["charters"]] == ["harbour"]


def test_redrafting_replaces_rather_than_duplicates(chat):
    from story import location_design

    location_design.open_draft(chat, {})
    location_design.set_skeleton(chat, rooms={"quay": {"name": "Quay"}})
    location_design.set_skeleton(chat, rooms={"quay": {"name": "The long quay"}})
    location_design.set_charter(chat, {"key": "harbour", "name": "Harbour"})
    location_design.set_charter(chat, {"key": "harbour", "name": "Harbourmaster"})
    plan = location_design.draft(chat)["plan"]
    assert plan["rooms"]["quay"]["name"] == "The long quay"
    assert [c["name"] for c in plan["charters"]] == ["Harbourmaster"]


def test_a_draft_that_cannot_close_cannot_be_submitted(chat):
    from story import location_design

    location_design.open_draft(chat, {})
    with pytest.raises(ValueError) as caught:
        location_design.submit(chat)
    assert "does not close" in str(caught.value)


def test_drafting_clears_the_last_review(chat):
    """A plan edited after its check has to be checked again, or `submit`
    would land something no closure ever saw."""
    from story import location_design

    location_design.open_draft(chat, {})
    row = location_design.draft(chat)
    row["checked"] = True
    location_design.save_draft(chat, row)
    location_design.set_charter(chat, {"key": "harbour"})
    assert location_design.draft(chat)["checked"] is False


def test_the_tools_refuse_outside_a_location_pass(chat):
    from story import location_design

    for call in (lambda: location_design.set_skeleton(chat, name="x"),
                 lambda: location_design.set_charter(chat, {"key": "k"}),
                 lambda: location_design.check(chat),
                 lambda: location_design.submit(chat)):
        with pytest.raises(ValueError) as caught:
            call()
        assert "no location is being designed" in str(caught.value)


def test_the_four_tools_are_on_the_table():
    from story.room_tools import TOOL_INDEX

    for name in ("draft_location", "draft_charter", "draft_history",
                 "review_location", "submit_location"):
        assert name in TOOL_INDEX, name


# -- the opening plan hears it ----------------------------------------------

def test_the_opening_task_carries_what_the_player_asked_for(chat):
    from agents import story_planner
    from story import room_conversation as room

    room.add_message(chat, None, "player", "Open it in the rain.")
    task = story_planner._opening_task(chat, None, "A shut parlour.")
    assert task["player_said"] == ["Open it in the rain."]


def test_the_opening_task_is_unchanged_when_nobody_said_anything(chat):
    from agents import story_planner

    task = story_planner._opening_task(chat, None, "A shut parlour.")
    assert "player_said" not in task


# -- the regimes are budgeted ------------------------------------------------

def test_the_two_new_regimes_have_their_own_budgets():
    """A regime the wall/steps tables do not name silently inherits the
    background task's ten minutes, which is not a launch's budget."""
    import inspect

    from agents import story_planner

    source = inspect.getsource(story_planner.run_planner)
    for regime in ("prelude", "location"):
        assert 'regime == "%s"' % regime in source, regime
    # The prelude is one question; the location design is the largest piece
    # of authoring the engine does in one pass.
    assert story_planner.PRELUDE_WALL_SECONDS < story_planner.OPENING_WALL_SECONDS
    assert story_planner.LOCATION_WALL_SECONDS > story_planner.OPENING_WALL_SECONDS


def test_neither_launch_pass_asks_a_question_of_nobody():
    """The prelude is the one regime with somebody to answer it. The
    location pass runs inside the launch, behind a progress line."""
    import inspect

    from agents import story_planner

    source = inspect.getsource(story_planner.run_planner)
    assert 'regime in ("opening", "location")' in source


# -- the line the engine speaks ----------------------------------------------

def test_the_fallback_question_is_spelled_the_same_in_both_places():
    """English is the message id (`story/room_conversation`'s module note):
    the line is STORED in English and translated on render through the UI
    catalog, and the catalog only holds what the harvester found in
    `static/js/`. So the JS copy and the Python constant have to be the same
    string, character for character, or a Japanese reader gets the English."""
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1]
          / "static/js/writers_room.js").read_text(encoding="utf-8")
    assert prelude.PRELUDE_FALLBACK_LINE in js


def test_both_packs_carry_the_fallback_question():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for pack in ("en", "ja"):
        catalog = json.loads(
            (root / "language_packs" / pack / "ui.json").read_text(
                encoding="utf-8"))
        assert prelude.PRELUDE_FALLBACK_LINE in catalog, pack


# -- the launch cut ----------------------------------------------------------

def test_the_greeting_launch_stops_before_it_builds_anything(monkeypatch,
                                                             temp_db):
    """The cut is above the ground and below the story's identity: the cast
    and the language are settled by the launch screen, the place is not."""
    import inspect

    from story import greetings

    source = inspect.getsource(greetings.start_story)
    body = source.split("if prelude:", 1)
    assert len(body) == 2, "start_story has no prelude cut"
    before, after = body
    # Everything that decides WHO and WHAT LANGUAGE is above the cut.
    assert "set_story_language" in before
    assert "seed_mutual_recognition" in before
    # Everything that builds the GROUND is below it.
    assert "generate_lived_location" in after
    assert "run_opening_plan" in after
    assert "_seed_minds" in after


def test_a_prelude_start_is_not_a_failed_setup(monkeypatch, temp_db):
    """A story waiting on its own author is the one state between created
    and running that is neither a failure nor a story; the library reads
    the failure mark to tell them apart."""
    import inspect

    from story import greetings

    source = inspect.getsource(greetings.start_story)
    cut = source.split("if prelude:", 1)[1].split("return cid, None")[0]
    assert "QUICK_START_FAILURE_KEY" in cut
