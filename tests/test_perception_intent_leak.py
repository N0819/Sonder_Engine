"""Regression tests for the action-INTENT leak found during live play
(Elevator Adventure, chat 23 / turn 15 -- Hinami carving protective runes
beside Dr. Moon, who is flat on the elevator floor).

The perception PROMPT was already correct ("never add meaning, name intent")
and the perception LLM obeyed it -- its free-text view of Hinami was clean and
observable. The leak came entirely from the deterministic delivery backstops,
which pasted the director's raw `attempt` strings into every observer's view:

    "Hinami remember the rune crafting her mother taught her. Hinami channel
     divine heritage and scratch sloppy runes of slow and soften into the
     elevator wall. Hinami slamming all the spiritual energy she can muster..."

Those attempts are the actor's OWN intent-laden framing. Delivered to Dr. Moon
they leak (a) the runes' PURPOSE ("slow and soften"), (b) Hinami's private
nature ("divine heritage"), and (c) a purely mental act ("remember ... her
mother taught her") that nobody can perceive at all.

The fix: every action element carries an intent-free `observable` surface;
observers are delivered THAT, never the raw attempt, and a mental beat
(observable "") is delivered to no one. Note these observers RECOGNIZE each
other (known both ways) -- the identity floor is intentionally satisfied so
these assertions isolate the intent surface, not name recognition.
"""

from __future__ import annotations

import json
import time

from agents.common import (
    assign_event_ids,
    norm_sequence,
    observable_action_text,
)
from character_schema import default_character_data, default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData

# The intent/purpose/cognition terms that must NEVER reach an observer's view.
FORBIDDEN = ["slow and soften", "divine heritage", "remember the rune",
             "spiritual energy", "arrest the free fall"]

# Raw player sequence as the director decomposed the turn-15 input: a mental
# recall (verb recall / stage preparation), claws (physical, plain), the carve
# (physical, intent in attempt + authored observable), the discharge.
ELEVATOR_SEQUENCE = [
    {"type": "action",
     "attempt": "remember the rune crafting her mother taught her",
     "verb": "recall", "stage": "preparation", "visibility": "overt"},
    {"type": "action", "attempt": "extending her claws",
     "verb": "extend", "stage": "immediate", "visibility": "overt",
     "observable": "extends her claws"},
    {"type": "action",
     "attempt": "channel divine heritage and scratch sloppy runes of slow "
                "and soften into the elevator wall",
     "verb": "carve", "stage": "contact", "visibility": "overt",
     "targets": ["entity_shelter_elevator"],
     "observable": "gouges rough marks into the steel wall with her claws",
     "intended_effects": [{"kind": "imbue the wall with slowing magic to "
                                   "arrest the free fall"}]},
    {"type": "action",
     "attempt": "slamming all the spiritual energy she can muster into the "
                "carved runes",
     "verb": "discharge", "stage": "sustained", "visibility": "overt",
     "targets": ["entity_shelter_elevator"],
     "observable": "presses both palms flat against the marks"},
]


# --- unit: the centralized observable policy -------------------------------

def test_norm_sequence_suppresses_mental_act():
    """A mental verb (recall) with no authored surface -> observable "" so it
    is delivered to no observer."""
    out = {"sequence": [
        {"type": "action",
         "attempt": "remember the rune crafting her mother taught her",
         "verb": "recall"}]}
    norm_sequence(out)
    elem = out["sequence"][0]
    assert elem["observable"] == ""
    assert observable_action_text(elem) == ""


def test_norm_sequence_mental_by_leading_verb_without_verb_field():
    """Weak model leaves `verb` unset: the leading token still classifies the
    act as mental, so it is not surfaced."""
    out = {"sequence": [
        {"type": "action",
         "attempt": "decide to run for the stairwell"}]}
    norm_sequence(out)
    assert out["sequence"][0]["observable"] == ""


def test_norm_sequence_keeps_authored_observable():
    out = {"sequence": [ELEVATOR_SEQUENCE[2]]}
    norm_sequence(out)
    elem = out["sequence"][0]
    assert elem["observable"] == (
        "gouges rough marks into the steel wall with her claws")
    surface = observable_action_text(elem)
    assert "divine heritage" not in surface
    assert "slow and soften" not in surface


def test_norm_sequence_physical_without_observable_falls_back_to_attempt():
    """A plain physical act with no intent and no authored surface still gets
    delivered -- no regression for ordinary actions."""
    out = {"sequence": [
        {"type": "action", "attempt": "push through the door", "verb": "push"}]}
    norm_sequence(out)
    assert out["sequence"][0]["observable"] == "push through the door"


def test_observable_action_text_legacy_element_falls_back_to_attempt():
    """An element predating the field (key absent, e.g. an un-normalized
    character declaration) falls back to attempt rather than vanishing."""
    assert observable_action_text(
        {"attempt": "wave hello"}) == "wave hello"
    # explicit empty -> suppressed
    assert observable_action_text(
        {"attempt": "wave hello", "observable": ""}) == ""


# --- integration: the deterministic delivery paths -------------------------

def _norm(seq):
    out = {"sequence": [dict(e) for e in seq]}
    norm_sequence(out)
    out["sequence"] = assign_event_ids(out["sequence"], "turn:1:player")
    return out


def _make_ctx(temp_db):
    """Hinami (player) + Dr. Moon, co-located, KNOWN to each other."""
    sheet = default_persona_data("Hinami")
    sheet["embodiment"]["visible"]["summary"] = (
        "Hinami, a fox-eared young woman with golden tails.")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(sheet), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Elevator", "", time.time(), persona_id))
    csheet = default_character_data("Dr. Moon")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Dr. Moon", json.dumps(csheet), "{}", time.time(), "char_dr_moon"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "the elevator", "time": "night",
        "rooms": {"room1": {"name": "Elevator car", "adjacent": []}},
        "positions": {"Hinami": "room1", "Dr. Moon": "room1"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known",
                 {"Dr. Moon": ["Hinami"], "Hinami": ["Dr. Moon"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "carve runes", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Elevator", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="carve runes", created=time.time()),
        cast=cast, input="carve runes")
    ctx["_player_room"] = "room1"
    return ctx, char_id


def _stub_clean_view(monkeypatch, moon_id, view_text):
    """Stub the perception LLM to return the clean, correctly-filtered view the
    real model produced -- so any leak in the result comes from the
    deterministic backstop, which is what we are testing."""
    import agents.perception as perception

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        views = {}
        for p in payload["perceivers"]:
            pid = str(p["id"])
            views[pid] = view_text if pid == str(moon_id) else (
                f"You are in {p['room_name']}.")
        return {"views": views}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)
    return perception


def test_perception_act_delivers_observable_not_intent(temp_db, monkeypatch):
    ctx, moon_id = _make_ctx(temp_db)
    ctx.director_interpret = _norm(ELEVATOR_SEQUENCE)
    ctx.director_interpret["flow"] = {"reactors": [moon_id],
                                      "resolution_flags": {}}
    clean = ("You are flat on the elevator floor. In front of you a young "
             "woman scratches marks into the steel wall and presses her "
             "hands to them.")
    perception = _stub_clean_view(monkeypatch, moon_id, clean)

    view = perception.perception_act(ctx, nonce=0)["views"][str(moon_id)]

    low = view.lower()
    for term in FORBIDDEN:
        assert term not in low, f"intent leaked into observer view: {term!r} in {view!r}"
    # the mental "remember" beat reaches no one
    assert "remember" not in low


def test_perception_act_payload_is_intent_free(temp_db, monkeypatch):
    """Belt-and-suspenders: the perception LLM must not even RECEIVE the intent
    (no intended_effects, no intent-laden attempt, no mental beat)."""
    ctx, moon_id = _make_ctx(temp_db)
    ctx.director_interpret = _norm(ELEVATOR_SEQUENCE)
    ctx.director_interpret["flow"] = {"reactors": [moon_id],
                                      "resolution_flags": {}}
    seen = {}

    import agents.perception as perception

    def capture(role, step_key, system, payload, **kwargs):
        seen["payload"] = payload
        return {"views": {str(moon_id): "You are in Elevator car."}}

    monkeypatch.setattr(perception, "_agent_json", capture)
    perception.perception_act(ctx, nonce=0)

    blob = json.dumps(seen["payload"]).lower()
    for term in ["intended_effects", "slow and soften", "divine heritage",
                 "arrest the free fall"]:
        assert term not in blob, f"perception input carried intent: {term!r}"
    # the mental recall beat is dropped from the observer-facing sequence
    onset_seq = seen["payload"]["declared_act"]["sequence"]
    assert all("remember" not in json.dumps(e).lower() for e in onset_seq)


def test_perception_outcome_delivers_observable_not_intent(temp_db, monkeypatch):
    ctx, moon_id = _make_ctx(temp_db)
    ctx.director_interpret = _norm(ELEVATOR_SEQUENCE)
    ctx.director_interpret["flow"] = {"reactors": [moon_id],
                                      "resolution_flags": {}}
    ctx.director_resolve = {"resolved_event": "The elevator's fall slows.",
                            "dialogue_log": []}
    clean = ("A decelerating force presses you to the floor. The young woman "
             "keeps her palms against the scratched wall.")
    perception = _stub_clean_view(monkeypatch, moon_id, clean)

    view = perception.perception_outcome(ctx, nonce=0)["views"][str(moon_id)]

    low = view.lower()
    for term in FORBIDDEN:
        assert term not in low, f"intent leaked into outcome view: {term!r} in {view!r}"
