"""What a plan MEANS reaches the Director; whether the story can reach a plan
is said at preview; and the opening sees the plan.

Chat 115 (2026-09-04): the Writers' Room planned a lift car
(`auxiliary_lift_car`) beside the Director-minted lift the cast already stood
in (`room_elevator_interior`), pointed a `scheduled_consequence` at the
planned one, and nothing reconciled the two -- a package reached the Director
only through seams (planned rooms, figures, due events), never as meaning.
Separately, an opening Director received the scenario, cast and lore but
nothing of the plan, so it minted its own rooms beside the planned ones.

Three rules, each with its unit tests and a payload-shape test per Director
stage:

  * `director_note` (`story/plot_packages.py`): the room's note to the
    Director, capped at `DIRECTOR_NOTE_CHARS`, scoped by rooms and by the
    package clock, read into every Director payload as `author_notes` and
    written into no ledger.
  * the reach warning (`plot_packages._reach_warning`): a package whose
    rooms are all further than `room_frontier.FRONTIER_DEPTH_HOPS` from
    where the cast stands is warned, by graph distance, naming the nearest
    occupied room and the hop count.
  * `planned_rooms` at the opening (`director._opening_planned_rooms`): the
    brief for every planned room, uncapped, absent without a plan.

The scene and plan below are chat 115's shape as measured on a copy of the
owner's database: the cast in a lift interior whose one exit is a corridor,
the corridor opening on the planned lift car, and the plan's shaft hanging
off it. `auxiliary_lift_car` is TWO hops from the cast -- exactly the
frontier depth -- so the consequence the live package pointed there would
NOT have been warned; the lobby the same package posted a bill in is FOUR.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest

from story.plot_packages import (
    DIRECTOR_NOTE_CHARS, OPERATIONS, active_director_notes, draft_operation,
    edit_package, fire_due_clocks, get_package, new_package, package_requirements,
    preview_package, publish_package, validate_package)
from story.room_frontier import FRONTIER_DEPTH_HOPS
from world.structure import plant_structure

import agents.director as director

PLAYER = "Sarah Moon"
CAST = "Hinami"

#: Chat 115's live rooms, as measured: the lift interior (an inside, its holder
#: standing in the corridor), and the corridor already opening on the planned
#: lift car.
LIFT_SCENE = {
    "location": "Site sublevel",
    "rooms": {
        "room_elevator_interior": {
            "name": "Shelter lift interior", "desc": "Steel walls, one lamp.",
            "parent_entity": "elevator_shelter",
            "adjacent": [{"to": "corridor_sublevel_f", "barrier": "open_door"}]},
        "corridor_sublevel_f": {
            "name": "Sublevel F corridor", "desc": "Smoke along the ceiling.",
            "adjacent": [{"to": "room_elevator_interior", "barrier": "open_door"},
                         {"to": "auxiliary_lift_car", "barrier": "open"}]},
    },
    "positions": {PLAYER: "room_elevator_interior", CAST: "room_elevator_interior",
                  "elevator_shelter": "corridor_sublevel_f"},
    "entities": {"elevator_shelter": {"name": "Shelter lift", "kind": "vehicle"}},
    "attire": {},
}

#: The plan: the room's lift car and the shaft hanging off it.
SHAFT = {
    "structure": {"key": "auxiliary_shelter", "name": "Auxiliary Shelter"},
    "rooms": {
        "auxiliary_lift_car": {
            "name": "Auxiliary lift car", "purpose": "the escape lift",
            "adjacent": [{"to": "corridor_sublevel_f"}, {"to": "deep_shelter_shaft"}]},
        "deep_shelter_shaft": {
            "name": "Deep shelter shaft", "purpose": "the shaft the car falls down",
            "adjacent": [{"to": "auxiliary_lift_car"}, {"to": "condemned_shelter_lobby"}]},
        "condemned_shelter_lobby": {
            "name": "Condemned shelter lobby", "purpose": "the sealed lobby below",
            "adjacent": [{"to": "deep_shelter_shaft"}]},
    },
}
#: Hops from the cast's room, as measured on chat 115 and re-derived from the
#: fixture above: interior -> corridor -> lift car -> shaft -> lobby.
HOPS_TO_LIFT_CAR = 2
HOPS_TO_LOBBY = 4

NOTE = ("The auxiliary lift car planned here IS the lift the cast is standing "
        "in: when the consequence fires, it is their car that falls.")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _story(db, *, scenario="", scene=None, plan=True, turns=3, cast=True):
    persona_id = db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                       (PLAYER, json.dumps({"identity": {"name": PLAYER}})))
    cid = db.qi("INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
                ("Sublevel", persona_id, scenario, time.time()))
    if cast:
        from story.character_schema import default_character_data
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (CAST, json.dumps(default_character_data(CAST)), "{}", time.time(),
             f"char_{uuid.uuid4().hex[:8]}"))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
              (cid, char_id, "active", "{}"))
    if scene is not None:
        db.wset(cid, "scene", json.loads(json.dumps(scene)))
    if plan:
        plant_structure(cid, SHAFT["structure"], SHAFT["rooms"])
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid, persona_id


def _package(cid, ops, **fields):
    pkg = new_package(cid, title="Lift Failure", premise="The car falls.")
    if fields:
        edit_package(cid, pkg["uid"], fields)
    for op in ops:
        draft_operation(cid, pkg["uid"], op)
    return pkg["uid"]


def _publish(cid, uid):
    verdict = validate_package(cid, uid)
    assert verdict["ok"], verdict["errors"]
    return publish_package(cid, uid, expected_revision=get_package(cid, uid)["revision"])


def _reach_warnings(preview):
    return [w for w in preview["warnings"] if "cannot reach" in w]


def _ctx(db, cid, persona_id, *, idx, scenario="", interp=None):
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    cast = db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "I look around.", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Sublevel", persona_id=persona_id,
                      lorebook_id=None, scenario=scenario, created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx,
                      player_input="I look around.", created=time.time()),
        cast=cast, input="I look around.")
    if interp is not None:
        ctx.director_interpret = interp
    return ctx


def _interp():
    return {
        "sequence": [{"type": "action", "attempt": "brace against the wall",
                      "commitment": "asserted", "targets": [],
                      "visibility": "overt", "conceal_from": []}],
        "speech": None, "action": {"attempt": "brace against the wall"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


def _capture(monkeypatch, run, systems=None):
    """Every payload `run()` hands a model, keyed by step; the system sheet
    of each into ``systems`` when given. The Director's own answer rules for
    every hand, so every specialist is dispatched and has a payload to check
    (see test_director_payload_shows_its_ledgers)."""
    from agents.director import SPECIALISTS
    systems = systems if systems is not None else {}
    sent = []

    def fake(role, step_key, system, payload, **kw):
        sent.append((step_key, payload))
        systems[step_key] = system
        if step_key == "director_resolve":
            return {"ledger_notes": {name: f"{name}: settled" for name in SPECIALISTS}}
        return {}

    monkeypatch.setattr(director, "_agent_json", fake)
    monkeypatch.setattr(director, "validate_llm_output", lambda step, value: (value, []))
    try:
        run()
    except Exception:
        # A stage may fail downstream of its model call on a skeletal
        # fixture; what it sent is the question, and an empty capture fails
        # the assertion rather than passing vacuously.
        pass
    return {step: payload for step, payload in sent}


# ---------------------------------------------------------------------------
# 1. The operation
# ---------------------------------------------------------------------------

class TestDirectorNote:
    def test_the_shape_and_the_cap(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _package(cid, [])
        with pytest.raises(ValueError, match="what the plan means"):
            draft_operation(cid, uid, {"op": "director_note", "text": "   "})
        with pytest.raises(ValueError, match="at most %d characters" % DIRECTOR_NOTE_CHARS):
            draft_operation(cid, uid, {"op": "director_note",
                                       "text": "x" * (DIRECTOR_NOTE_CHARS + 1)})
        draft_operation(cid, uid, {"op": "director_note", "text": "  what  it means ",
                                   "rooms": "auxiliary_lift_car", "clock": "c1"})
        op = get_package(cid, uid)["operations"][0]
        assert op == {"op": "director_note", "text": "what it means",
                      "rooms": ["auxiliary_lift_car"], "clock": "c1"}
        # The table entry names its seam and is short; the mandate vocabulary
        # and the requirements grammar both know the kind.
        assert OPERATIONS["director_note"]["long"] is False
        assert "author_notes" in OPERATIONS["director_note"]["seam"]
        assert "director_note" in package_requirements(get_package(cid, uid))
        from story.mandates import MANDATE_CAPABILITIES
        assert "director_note" in MANDATE_CAPABILITIES

    def test_a_note_scoped_to_a_room_nobody_holds_is_refused(self, temp_db):
        cid, _ = _story(temp_db, scene=LIFT_SCENE)
        uid = _package(cid, [{"op": "director_note", "text": NOTE,
                              "rooms": ["nowhere_at_all"]}])
        preview = preview_package(cid, uid)
        assert any("exists nowhere" in e for e in preview["errors"])
        # A room the package itself plants is somewhere.
        uid = _package(cid, [
            {"op": "plan_rooms", "structure": {"key": "annex", "name": "Annex"},
             "rooms": {"annex_hall": {"name": "Annex hall",
                                      "adjacent": [{"to": "corridor_sublevel_f"}]}}},
            {"op": "director_note", "text": NOTE, "rooms": ["annex_hall"]}])
        assert preview_package(cid, uid)["errors"] == []

    def test_a_note_is_read_from_the_next_turn_and_by_scope(self, temp_db):
        cid, _ = _story(temp_db, scene=LIFT_SCENE, turns=3)
        uid = _package(cid, [
            {"op": "director_note", "text": "everywhere: the shelter is lost"},
            {"op": "director_note", "text": NOTE, "rooms": ["auxiliary_lift_car"]}])
        out = _publish(cid, uid)
        assert out["published_turn"] == 2
        assert [a["result"] for a in out["applied"]] == [
            {"delivered_from_turn": 3}, {"delivered_from_turn": 3}]
        # Never the turn it was published in.
        assert active_director_notes(cid, None, 2, {"auxiliary_lift_car"}) == []
        # Beside the lift car: both. Nowhere near it: the unscoped one only.
        assert active_director_notes(cid, None, 3, {"corridor_sublevel_f",
                                                    "auxiliary_lift_car"}) == [
            "everywhere: the shelter is lost", NOTE]
        assert active_director_notes(cid, None, 3, {"condemned_shelter_lobby"}) == [
            "everywhere: the shelter is lost"]
        assert active_director_notes(cid, None, 3, None) == [
            "everywhere: the shelter is lost"]

    def test_a_clocked_note_applies_once_its_clock_is_due(self, temp_db):
        cid, _ = _story(temp_db, scene=LIFT_SCENE, turns=3)
        uid = _package(cid, [
            {"op": "director_note", "text": NOTE, "clock": "c_fall"}],
            clocks=[{"id": "c_fall", "label": "the cable shears", "due_turns": 1}])
        out = _publish(cid, uid)
        assert out["applied"][0]["result"] == {"deferred": "c_fall"}
        assert active_director_notes(cid, None, 3, None) == []
        fired = fire_due_clocks(cid, 3)
        assert fired["fired"] == [(uid, "c_fall")]
        assert active_director_notes(cid, None, 3, None) == [NOTE]
        assert get_package(cid, uid)["operations"][0]["applied"] == {
            "delivered_from_turn": 4}

    def test_a_package_published_before_the_opening_is_seen_by_the_opening(self, temp_db):
        """A story with no turn stands before its opening: the package is
        published at turn -1 and turn 0 is the next turn."""
        cid, _ = _story(temp_db, turns=0)
        uid = _package(cid, [{"op": "director_note", "text": NOTE}])
        out = _publish(cid, uid)
        assert out["published_turn"] == -1 and out["visible_from_turn"] == 0
        assert active_director_notes(cid, None, 0, None) == [NOTE]

    def test_a_note_writes_nothing_a_mind_reads(self, temp_db):
        cid, _ = _story(temp_db, scene=LIFT_SCENE)
        before = {
            "scene": temp_db.wget(cid, "scene"),
            "events": [dict(r) for r in temp_db.q(
                "SELECT content FROM events WHERE chat_id=?", (cid,))],
            "lore": [dict(r) for r in temp_db.q("SELECT content FROM lore_entries")],
            "chars": [dict(r) for r in temp_db.q(
                "SELECT state FROM chat_chars WHERE chat_id=?", (cid,))],
        }
        uid = _package(cid, [{"op": "director_note", "text": NOTE}])
        _publish(cid, uid)
        after = {
            "scene": temp_db.wget(cid, "scene"),
            "events": [dict(r) for r in temp_db.q(
                "SELECT content FROM events WHERE chat_id=?", (cid,))],
            "lore": [dict(r) for r in temp_db.q("SELECT content FROM lore_entries")],
            "chars": [dict(r) for r in temp_db.q(
                "SELECT state FROM chat_chars WHERE chat_id=?", (cid,))],
        }
        assert after == before
        rows = [dict(r) for r in temp_db.q(
            "SELECT key, value FROM world WHERE chat_id=?", (cid,))]
        holders = [r["key"] for r in rows if "their car that falls" in str(r["value"])]
        assert holders == ["plot_packages"]


# ---------------------------------------------------------------------------
# 2. Reach
# ---------------------------------------------------------------------------

class TestReach:
    def test_chat_115s_consequence_stood_at_the_frontier_depth(self, temp_db):
        """Honest about the measurement: the lift car is exactly
        FRONTIER_DEPTH_HOPS from the cast, so the consequence pointed at it
        is warned only if the frontier is ever narrowed below two."""
        cid, _ = _story(temp_db, scene=LIFT_SCENE)
        uid = _package(cid, [
            {"op": "scheduled_consequence", "clock": "c1",
             "summary": "the cable snaps", "room": "auxiliary_lift_car"}],
            clocks=[{"id": "c1", "label": "shear", "due_turns": 3}])
        preview = preview_package(cid, uid)
        assert preview["errors"] == []
        assert bool(_reach_warnings(preview)) == (HOPS_TO_LIFT_CAR > FRONTIER_DEPTH_HOPS)

    def test_a_package_naming_only_a_far_room_is_warned_with_room_and_hops(self, temp_db):
        cid, _ = _story(temp_db, scene=LIFT_SCENE)
        uid = _package(cid, [
            {"op": "post_artifact", "room": "condemned_shelter_lobby",
             "description": "a scorched plate", "text": "DO NOT ENTER"}])
        preview = preview_package(cid, uid)
        assert preview["errors"] == [], preview["errors"]
        warnings = _reach_warnings(preview)
        assert len(warnings) == 1, preview["warnings"]
        assert "'condemned_shelter_lobby'" in warnings[0]
        assert "%d hops" % HOPS_TO_LOBBY in warnings[0]
        assert "'room_elevator_interior'" in warnings[0]
        assert "reaches %d" % FRONTIER_DEPTH_HOPS in warnings[0]
        # A WARNING: the package still validates.
        assert validate_package(cid, uid)["ok"]
        assert HOPS_TO_LOBBY > FRONTIER_DEPTH_HOPS

    def test_one_room_in_reach_is_enough(self, temp_db):
        """Chat 115's second package named both the lift car and the lobby;
        the nearer one is what the rule reads."""
        cid, _ = _story(temp_db, scene=LIFT_SCENE)
        uid = _package(cid, [
            {"op": "scheduled_consequence", "clock": "c1",
             "summary": "the cable snaps", "room": "auxiliary_lift_car"},
            {"op": "post_artifact", "room": "condemned_shelter_lobby",
             "description": "a scorched plate"}],
            clocks=[{"id": "c1", "label": "shear", "due_turns": 3}])
        assert _reach_warnings(preview_package(cid, uid)) == [] or \
            HOPS_TO_LIFT_CAR > FRONTIER_DEPTH_HOPS

    def test_rooms_the_package_plants_join_the_graph(self, temp_db):
        cid, _ = _story(temp_db, scene=LIFT_SCENE)
        near = _package(cid, [
            {"op": "plan_rooms", "structure": {"key": "annex", "name": "Annex"},
             "rooms": {"annex_hall": {"name": "Annex hall",
                                      "adjacent": [{"to": "corridor_sublevel_f"}]}}}])
        assert _reach_warnings(preview_package(cid, near)) == []
        far = _package(cid, [
            {"op": "plan_rooms", "structure": {"key": "annex", "name": "Annex"},
             "rooms": {"sump": {"name": "Sump",
                                "adjacent": [{"to": "condemned_shelter_lobby"}]}}}])
        warnings = _reach_warnings(preview_package(cid, far))
        assert len(warnings) == 1
        assert "'sump'" in warnings[0] and "%d hops" % (HOPS_TO_LOBBY + 1) in warnings[0]

    def test_no_route_at_all_says_so(self, temp_db):
        scene = json.loads(json.dumps(LIFT_SCENE))
        scene["rooms"]["island"] = {"name": "Island", "desc": "Cut off.", "adjacent": []}
        cid, _ = _story(temp_db, scene=scene)
        uid = _package(cid, [{"op": "post_artifact", "room": "island",
                              "description": "a bill"}])
        warnings = _reach_warnings(preview_package(cid, uid))
        assert len(warnings) == 1 and "no route" in warnings[0]
        assert "room_elevator_interior" in warnings[0]

    def test_nothing_to_judge_is_not_warned(self, temp_db):
        # No room named.
        cid, _ = _story(temp_db, scene=LIFT_SCENE)
        uid = _package(cid, [{"op": "director_note", "text": NOTE}])
        assert _reach_warnings(preview_package(cid, uid)) == []
        # Nobody placed anywhere.
        cid, _ = _story(temp_db, scene={"rooms": LIFT_SCENE["rooms"], "positions": {}})
        uid = _package(cid, [{"op": "post_artifact", "room": "condemned_shelter_lobby",
                              "description": "a bill"}])
        assert _reach_warnings(preview_package(cid, uid)) == []


# ---------------------------------------------------------------------------
# 3. The Director payloads, stage by stage
# ---------------------------------------------------------------------------

def test_the_opening_is_handed_every_planned_room_and_the_notes_in_scope(
        temp_db, monkeypatch):
    scenario = "Sarah and Hinami are in the auxiliary lift car when the lights fail."
    cid, persona_id = _story(temp_db, scenario=scenario, turns=0)
    uid = _package(cid, [
        {"op": "director_note", "text": NOTE, "rooms": ["deep_shelter_shaft"]},
        {"op": "director_note", "text": "far: the lobby is sealed",
         "rooms": ["condemned_shelter_lobby"]},
        {"op": "director_note", "text": "everywhere: Code Yellow"}])
    _publish(cid, uid)
    ctx = _ctx(temp_db, cid, persona_id, idx=0, scenario=scenario)
    sent = _capture(monkeypatch, lambda: director.director_establish(ctx, nonce=0))
    payload = sent["director_establish"]
    # EVERY planned room, by id, with the plan's purpose and exits.
    assert set(payload["planned_rooms"]) == set(SHAFT["rooms"])
    car = payload["planned_rooms"]["auxiliary_lift_car"]
    assert car["purpose"] == "the escape lift"
    assert {e["to"] for e in car["exits"]} == {"corridor_sublevel_f", "deep_shelter_shaft"}
    # The notes in scope: the scenario names the lift car, the shaft is
    # planned beside it, the lobby is two planned hops further.
    assert payload["author_notes"] == [NOTE, "everywhere: Code Yellow"]


def test_an_opening_with_no_plan_and_no_note_carries_neither_key(temp_db, monkeypatch):
    cid, persona_id = _story(temp_db, plan=False, turns=0)
    ctx = _ctx(temp_db, cid, persona_id, idx=0)
    bare = _capture(monkeypatch, lambda: director.director_establish(ctx, nonce=0))
    payload = bare["director_establish"]
    assert "planned_rooms" not in payload and "author_notes" not in payload
    # And a note adds exactly its own key: the two keys are the whole change.
    cid2, persona_id2 = _story(temp_db, plan=False, turns=0)
    _publish(cid2, _package(cid2, [{"op": "director_note", "text": NOTE}]))
    ctx2 = _ctx(temp_db, cid2, persona_id2, idx=0)
    noted = _capture(monkeypatch, lambda: director.director_establish(ctx2, nonce=0))
    assert set(noted["director_establish"]) - set(payload) == {"author_notes"}


def test_the_opening_brief_is_uncapped(temp_db, monkeypatch):
    """Measured: chat 114 carries 49 planned rooms (63,544 bytes of brief);
    every one reaches the opening. Sixty here, well past any cap a reader
    might assume."""
    cid, persona_id = _story(temp_db, plan=False, turns=0)
    rooms = {f"cell_{i:02d}": {"name": f"Cell {i}", "purpose": "a cell",
                                "adjacent": [{"to": f"cell_{(i + 1) % 60:02d}"}]}
             for i in range(60)}
    plant_structure(cid, {"key": "block", "name": "Block"}, rooms)
    ctx = _ctx(temp_db, cid, persona_id, idx=0)
    sent = _capture(monkeypatch, lambda: director.director_establish(ctx, nonce=0))
    assert len(sent["director_establish"]["planned_rooms"]) == 60


def test_interpret_carries_the_notes_in_reach_and_hands_them_on(temp_db, monkeypatch):
    cid, persona_id = _story(temp_db, scene=LIFT_SCENE, turns=3)
    # Scope is IN OR BESIDE: the corridor is beside the lift interior the
    # cast stands in; the planned lift car is two hops out, so a note about
    # it that is to apply from inside the live lift names that room too, or
    # names none (chat 115's note would have).
    _publish(cid, _package(cid, [
        {"op": "director_note", "text": NOTE, "rooms": ["corridor_sublevel_f"]},
        {"op": "director_note", "text": "two hops: the car",
         "rooms": ["auxiliary_lift_car"]},
        {"op": "director_note", "text": "far: the lobby is sealed",
         "rooms": ["condemned_shelter_lobby"]}]))
    ctx = _ctx(temp_db, cid, persona_id, idx=3)
    sent = _capture(monkeypatch, lambda: director.director_interpret(ctx, nonce=0))
    assert sent["director_interpret"]["author_notes"] == [NOTE]
    # No note in reach: no key, so the payload is the one it always was.
    cid2, persona_id2 = _story(temp_db, scene=LIFT_SCENE, turns=3)
    _publish(cid2, _package(cid2, [
        {"op": "director_note", "text": "far", "rooms": ["condemned_shelter_lobby"]}]))
    ctx2 = _ctx(temp_db, cid2, persona_id2, idx=3)
    bare = _capture(monkeypatch, lambda: director.director_interpret(ctx2, nonce=0))
    assert "author_notes" not in bare["director_interpret"]
    assert set(sent["director_interpret"]) - set(bare["director_interpret"]) == {
        "author_notes"}


def test_resolve_carries_the_notes_to_the_author_and_the_placing_hands(
        temp_db, monkeypatch):
    cid, persona_id = _story(temp_db, scene=LIFT_SCENE, turns=3)
    _publish(cid, _package(cid, [
        {"op": "director_note", "text": NOTE,
         "rooms": ["room_elevator_interior", "auxiliary_lift_car"]},
        {"op": "director_note", "text": "everywhere: Code Yellow"}]))
    ctx = _ctx(temp_db, cid, persona_id, idx=3, interp=_interp())
    systems = {}
    sent = _capture(monkeypatch, lambda: director.director_resolve(ctx, nonce=0),
                    systems)
    assert sent["director_resolve"]["author_notes"] == [NOTE, "everywhere: Code Yellow"]
    # The hands that place and bind things see it; the hands that dress,
    # speak and touch do not -- a note is about the plan, not a body.
    assert sent["director_objects"]["author_notes"] == [NOTE, "everywhere: Code Yellow"]
    assert sent["director_spatial"]["author_notes"] == [NOTE, "everywhere: Code Yellow"]
    for hand in ("director_body", "director_social", "director_contact"):
        assert "author_notes" not in sent[hand]
    # And the prose author's sheet loads the duty on such a beat.
    assert "AN AUTHOR'S NOTE SAYS WHAT THE PLAN MEANS" in systems["director_resolve"]


def test_resolve_without_a_note_is_unchanged(temp_db, monkeypatch):
    cid, persona_id = _story(temp_db, scene=LIFT_SCENE, turns=3)
    ctx = _ctx(temp_db, cid, persona_id, idx=3, interp=_interp())
    systems = {}
    sent = _capture(monkeypatch, lambda: director.director_resolve(ctx, nonce=0),
                    systems)
    for step, payload in sent.items():
        assert "author_notes" not in payload, step
    # The duty chunk stays out of the sheet, as every gated duty does when
    # the beat carries no work for it.
    assert "AN AUTHOR'S NOTE SAYS WHAT THE PLAN MEANS" not in systems["director_resolve"]


def test_the_prompts_teach_the_key_where_it_is_delivered():
    """The clause travels with the key, in both packs: every Director surface
    that can receive `author_notes` says what a note is and what it never
    licenses, and the opening prompt says where to place an opening the plan
    already holds a room for."""
    from language_runtime import installed_language_packs
    for pack in installed_language_packs(refresh=True).values():
        card = pack.card("system_prompts")
        assert "author_notes" in card["prompts"]["director_establish"]
        assert "planned_rooms" in card["prompts"]["director_establish"]
        assert "author_notes" in card["prompts"]["director_interpret"]
        assert "director_note" in card["prompts"]["story_planner"]
        sheet = dict((k, t) for k, t in card["prose_author_sheet"] if k)
        assert "author_notes" in sheet["author_notes"]
