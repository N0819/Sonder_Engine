"""Regression tests for consciousness-gated perception (awareness Phase 1).

Found in live play (Elevator Adventure, turns 18-22): the player-character was
unconscious after a crash, yet her player-facing perception view was generated
every turn as full first-person SIGHTED prose -- she "perceived" a lobby reveal
while knocked out. Root cause: consciousness existed nowhere as structured
state, perception hard-coded the player as awake/engaged, and the deterministic
injection backstops stuffed dialogue/actions into every view unconditionally.

Fix: an `awareness` world_condition (level unconscious|sedated|asleep|dazed),
Director-owned, read at perception and planning time. A non-awake mind is
EXCLUDED from the perception LLM call and every deterministic backstop, and
receives only a content-free residue; it is dropped from reactor planning; and
character_step no-ops for it. Fail-open: absent condition => awake, behavior
byte-identical to before.
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data, default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData
from scene import (
    NON_AWAKE_GATED,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
)

FORBIDDEN_SCENE_TOKENS = ["condemned", "corridor", "flashlight", "Dr. Moon",
                          "elevator", "lobby", "boarded"]


def _residue_like(view):
    v = (view or "").lower()
    return any(lead in v for lead in ("darkness", "under, below waking",
                                      "floating dark"))


# --- unit: scene.py awareness readers --------------------------------------

def test_awareness_of_defaults_awake():
    assert awareness_of({}, "Hinami") == "awake"


def test_apply_awareness_diff_sets_and_clears():
    diff = {"conditions": {"c1": [{
        "condition_id": "c1", "subject_id": "Hinami", "kind": "awareness",
        "state": {"level": "unconscious", "cause": "crash"}}]}}
    amap = apply_awareness_diff({}, diff)
    assert awareness_of(amap, "Hinami") == "unconscious"
    # re-emitting with active:0 wakes them this beat
    wake = {"conditions": {"c1": [{
        "condition_id": "c1", "subject_id": "Hinami", "kind": "awareness",
        "active": 0, "state": {"level": "unconscious"}}]}}
    assert awareness_of(apply_awareness_diff(amap, wake), "Hinami") == "awake"


def test_unknown_level_degrades_to_dazed():
    diff = {"conditions": {"c1": [{
        "condition_id": "c1", "subject_id": "X", "kind": "awareness",
        "state": {"level": "flabbergasted"}}]}}
    assert awareness_of(apply_awareness_diff({}, diff), "X") == "dazed"
    assert "dazed" not in NON_AWAKE_GATED  # dazed stays in the LLM call


# --- integration harness ----------------------------------------------------

def _make_ctx(temp_db, unconscious_player=False, extra_awake=None):
    sheet = default_persona_data("Hinami")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(sheet), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Elevator", "", time.time(), persona_id))

    def add_char(name, uid):
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}", time.time(), uid))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, cid, "active", "{}"))
        return cid

    moon_id = add_char("Dr. Moon", "char_dr_moon")
    extra_id = add_char(extra_awake, f"char_{extra_awake}") if extra_awake else None

    positions = {"Hinami": "room1", "Dr. Moon": "room1"}
    if extra_awake:
        positions[extra_awake] = "room1"
    temp_db.wset(chat_id, "scene", {
        "location": "the elevator", "time": "night",
        "rooms": {"room1": {"name": "Elevator car", "adjacent": []}},
        "positions": positions, "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {"Dr. Moon": ["Hinami"], "Hinami": ["Dr. Moon"]})

    if unconscious_player:
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
            "started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)",
            ("cond_aware_hinami", chat_id, "Hinami", "awareness", 0.0, None, None,
             json.dumps({"condition_id": "cond_aware_hinami", "subject_id": "Hinami",
                         "kind": "awareness",
                         "state": {"level": "unconscious",
                                   "cause": "struck in the elevator crash, bleeding"}}), 1))

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Elevator", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "room1"
    return ctx, chat_id, moon_id, extra_id


def _stub(monkeypatch, views):
    """Stub the perception LLM; returns exactly `views` regardless of payload,
    so any leak in the result is the deterministic backstop's doing."""
    import agents.perception as perception

    def fake(role, step_key, system, payload, **kw):
        # record which perceivers the LLM was actually asked about
        fake.asked = [str(p["id"]) for p in payload.get("perceivers", [])]
        return {"views": dict(views)}

    fake.asked = []
    monkeypatch.setattr(perception, "_agent_json", fake)
    return fake


def _resolve(**kw):
    base = {"resolved_event": "Dr. Moon sweeps her flashlight across the "
                              "condemned lobby beyond the buckled doors.",
            "dialogue_log": [{"speaker": "Dr. Moon",
                              "exact_quote": "Condemned. Every corridor is boarded.",
                              "volume": "normal", "intended_target": "Hinami"}]}
    base.update(kw)
    return base


def test_unconscious_player_gets_residue_not_scene(temp_db, monkeypatch):
    import agents.perception as perception
    ctx, chat_id, moon_id, _ = _make_ctx(temp_db, unconscious_player=True)
    ctx.director_interpret = {"sequence": [], "flow": {"reactors": [moon_id]}}
    ctx.director_resolve = _resolve()
    # Even if the model tried to hand back a full player view, it is dropped:
    fake = _stub(monkeypatch, {"player": "You see the condemned lobby and Dr. Moon."})

    view = perception.perception_outcome(ctx, nonce=0)["views"]["player"]

    assert "player" not in fake.asked, "unconscious player must be excluded from the LLM call"
    assert _residue_like(view), f"expected residue, got {view!r}"
    low = view.lower()
    for tok in FORBIDDEN_SCENE_TOKENS:
        assert tok.lower() not in low, f"scene detail {tok!r} leaked into residue: {view!r}"
    assert "condemned" not in low  # the reveal never reaches an unconscious mind


def test_backstop_injection_gated_for_unconscious(temp_db, monkeypatch):
    """The deterministic dialogue/action injection must not fire for a non-awake
    perceiver even when the LLM returns nothing."""
    import agents.perception as perception
    ctx, chat_id, moon_id, _ = _make_ctx(temp_db, unconscious_player=True)
    ctx.director_interpret = {"sequence": [], "flow": {"reactors": [moon_id]}}
    ctx.director_resolve = _resolve()
    _stub(monkeypatch, {})  # empty -> forces deterministic path

    view = perception.perception_outcome(ctx, nonce=0)["views"]["player"]
    assert "Condemned" not in view and "boarded" not in view.lower()
    assert _residue_like(view)


def test_fail_open_awake_player_unchanged(temp_db, monkeypatch):
    """No awareness condition => the player is a normal perceiver in the call."""
    import agents.perception as perception
    ctx, chat_id, moon_id, _ = _make_ctx(temp_db, unconscious_player=False)
    ctx.director_interpret = {"sequence": [], "flow": {"reactors": [moon_id]}}
    ctx.director_resolve = _resolve()
    fake = _stub(monkeypatch, {"player": "You are in the elevator car."})

    view = perception.perception_outcome(ctx, nonce=0)["views"]["player"]
    assert "player" in fake.asked
    # the awake player receives Dr. Moon's injected line
    assert "Condemned" in view


def test_build_plan_drops_unconscious_reactor(temp_db):
    from agents.runtime import build_plan
    ctx, chat_id, moon_id, _ = _make_ctx(temp_db, unconscious_player=False)
    # knock DR. MOON out
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)",
        ("c_moon", chat_id, "Dr. Moon", "awareness", 0.0, None, None,
         json.dumps({"subject_id": "Dr. Moon", "kind": "awareness",
                     "state": {"level": "unconscious"}}), 1))
    interp = {"flow": {"reactors": [moon_id], "resolution_flags": {}}}
    plan = build_plan(interp, ctx.cast, chat_id=chat_id)
    assert not any(step[0] == f"character:{moon_id}" for step in plan)
    assert not any(step[0] == "interaction_loop" for step in plan)


def test_character_step_noop_for_unconscious(temp_db):
    from agents.character import character_step
    ctx, chat_id, moon_id, _ = _make_ctx(temp_db, unconscious_player=False)
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)",
        ("c_moon", chat_id, "Dr. Moon", "awareness", 0.0, None, None,
         json.dumps({"subject_id": "Dr. Moon", "kind": "awareness",
                     "state": {"level": "unconscious"}}), 1))
    res = character_step(ctx, moon_id, nonce=0)
    assert res.get("_awareness_gated") is True
    assert res["sequence"] == [] and not res.get("speech")


def test_director_floor_flags_untracked_knockout():
    from agents.director import _untracked_unconsciousness_subjects
    flagged = _untracked_unconsciousness_subjects(
        "The blast knocks Hinami out cold against the wall.",
        [], {}, ["Hinami", "Dr. Moon"])
    assert flagged == ["Hinami"]
    # already-tracked awareness condition suppresses the flag
    tracked = {"c": [{"subject_id": "Hinami", "kind": "awareness",
                      "state": {"level": "unconscious"}}]}
    assert _untracked_unconsciousness_subjects(
        "Hinami is knocked out cold.", [], tracked, ["Hinami"]) == []
    # an unrelated (non-awareness) condition on the subject does NOT suppress it
    wound = {"c": [{"subject_id": "Hinami", "kind": "wound"}]}
    assert _untracked_unconsciousness_subjects(
        "Hinami is knocked out cold.", [], wound, ["Hinami"]) == ["Hinami"]


def test_director_floor_does_not_flag_conscious_bystander():
    """The precision fix (Elevator Adventure, chat 23 latest turn): the
    resolved_event narrates the PLAYER unconscious while a fully-conscious
    Dr. Moon tends her in the same passage. The floor must flag ONLY the
    fallen subject, never the bystander whose name co-occurs with the cue.
    """
    from agents.director import _untracked_unconsciousness_subjects
    names = ["Hinami", "Dr. Moon"]

    # The exact live text that mislabeled Dr. Moon: the cue "unconscious"
    # attaches to "anomaly" (Hinami), and "Dr. Moon" sits across a real
    # sentence break -> neither is Dr. Moon's, and Hinami is already tracked.
    live = ("Freeing both hands, she kneels directly into the plaster dust "
            "beside the unconscious anomaly. Dr. Moon presses both palms "
            "firmly over the heaviest bloodstain on Hinami's side.")
    tracked = {"c": [{"subject_id": "Hinami", "kind": "awareness",
                      "state": {"level": "unconscious"}}]}
    assert _untracked_unconsciousness_subjects(live, [], tracked, names) == []

    # Same sentence, bystander named alongside the fallen one: flag Hinami only.
    assert _untracked_unconsciousness_subjects(
        "Dr. Moon kneels beside Hinami, who lies unconscious.",
        [], {}, names) == ["Hinami"]

    # Bystander is closer in raw distance but not the grammatical subject:
    # "Dr. Moon watches as Hinami slumps unconscious" -> closest subject wins.
    assert _untracked_unconsciousness_subjects(
        "Dr. Moon watches helplessly as Hinami slumps unconscious.",
        [], {}, names) == ["Hinami"]

    # A transitive knockout of the bystander IS still caught (name adjacent
    # to the cue) -- precision, not blanket suppression of Dr. Moon.
    assert _untracked_unconsciousness_subjects(
        "The falling beam knocks Dr. Moon out cold.",
        [], {}, names) == ["Dr. Moon"]
