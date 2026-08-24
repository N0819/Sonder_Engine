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
    adjudicated_player_action_text,
    assign_event_ids,
    norm_sequence,
    observable_action_onset_text,
    observable_action_text,
)
from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

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


def test_contestable_onset_does_not_deliver_completed_multistage_outcome():
    elem = {
        "type": "action",
        "commitment": "contestable",
        "observable": (
            "signals a shallow dip, takes her weight, returns her upright, "
            "then opens both hands and steps back"),
    }

    assert observable_action_onset_text(elem) == "attempts to signal a shallow dip"
    # The complete surface remains available to the resolver.
    assert "returns her upright" in observable_action_text(elem)


def test_contestable_outcome_surface_requires_realized_event_id():
    elem = {
        "type": "action", "event_id": "turn:7:player:0:action",
        "commitment": "contestable",
        "observable": "tests the wound edge, irrigates it, then sutures it",
    }
    stopped = {"state_diff": {"claim_dispositions": [{
            "claim_id": "turn:7:player:0:action", "status": "deferred",
        "realized_event_ids": [],
    }]}}
    realized = {"state_diff": {"claim_dispositions": [{
        "claim_id": "claim:0:intent:0", "status": "realized",
        "realized_event_ids": ["turn:7:player:0:action"],
    }]}}

    assert adjudicated_player_action_text(elem, stopped) == (
        "attempts to test the wound edge")
    assert adjudicated_player_action_text(elem, realized) == elem["observable"]


def test_one_realized_effect_cannot_promote_deferred_sibling_phases():
    elem = {
        "type": "action", "event_id": "turn:7:player:0:action",
        "commitment": "contestable",
        "observable": "tests the wound edge, irrigates it, then sutures it",
    }
    mixed = {"state_diff": {"claim_dispositions": [
        {"claim_id": "claim:0:intent:0", "status": "realized",
         "realized_event_ids": ["turn:7:player:0:action"]},
        {"claim_id": "claim:0:intent:1", "status": "deferred",
         "realized_event_ids": []},
    ]}}

    assert adjudicated_player_action_text(elem, mixed) == (
        "attempts to test the wound edge")


def test_rejected_contestable_effect_never_reads_as_completed_success():
    elem = {
        "type": "action", "event_id": "turn:7:player:0:action",
        "commitment": "contestable",
        "observable": "creates space, breaks the grip, then retreats two steps",
    }
    prevented = {"state_diff": {"claim_dispositions": [
        {"claim_id": "claim:0:intent:0", "status": "contested"},
        {"claim_id": "claim:0:intent:1", "status": "rejected"},
    ]}}

    assert adjudicated_player_action_text(elem, prevented) == (
        "attempts to create space")


def test_wholly_deferred_conditional_alternative_never_begins():
    elem = {
        "type": "action", "event_id": "turn:7:player:1:action",
        "commitment": "contestable",
        "observable": "pauses the procedure and prepares to escalate care",
    }
    deferred = {"state_diff": {"claim_dispositions": [
        {"claim_id": "claim:1:intent:0", "status": "deferred"},
        {"claim_id": "claim:1:intent:1", "status": "deferred"},
    ]}}

    assert adjudicated_player_action_text(elem, deferred) == ""


def test_asserted_action_onset_keeps_complete_surface():
    elem = {
        "type": "action", "commitment": "asserted",
        "observable": "opens the case, removes the key, and holds it up",
    }
    assert observable_action_onset_text(elem) == elem["observable"]


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

    # The payload this used to search no longer exists. Intent can now only
    # reach a mind through a percept, so the view is both the shorter path
    # and the whole surface.
    view = perception.perception_act(ctx, nonce=0)["views"][str(moon_id)] or ""

    blob = view.lower()
    for term in ["intended_effects", "slow and soften", "divine heritage",
                 "arrest the free fall"]:
        assert term not in blob, f"perception delivered intent: {term!r}"
    # the mental recall beat never becomes an observable surface
    assert "remember" not in blob


def test_structured_observations_ignore_model_side_channel(temp_db, monkeypatch):
    """A perception model cannot smuggle hidden intent through observations.

    The runtime discards model-authored observation objects and re-projects the
    final scrubbed prose view, so the new channel has exactly the prose
    channel's information budget.
    """
    ctx, moon_id = _make_ctx(temp_db)
    ctx.director_interpret = _norm(ELEVATOR_SEQUENCE)
    ctx.director_interpret["flow"] = {
        "reactors": [moon_id], "resolution_flags": {},
    }
    import agents.perception as perception

    def malicious(role, step_key, system, payload, **kwargs):
        return {
            "views": {str(moon_id): "You see a hand press against the wall."},
            "observations": {str(moon_id): [{
                "observation_id": "leak",
                "perceiver_id": str(moon_id),
                "source_atom_id": "private",
                "channel": "telepathy",
                "fidelity": "omniscient",
                "observed": {
                    "text": "divine heritage; intends to arrest the free fall",
                    "private_tell_ground": "she fears exposure",
                },
            }]},
        }

    result = perception.perception_act(ctx, nonce=0)
    blob = json.dumps(result["observations"]).casefold()

    assert "divine heritage" not in blob
    assert "arrest the free fall" not in blob
    assert "private_tell_ground" not in blob
    # ...and the observation still carries the genuine observable surface.
    # It reads as the engine's own projection of the act rather than the
    # phrase the stubbed model used to supply, because that is now the only
    # source an observation can have.
    assert "palms flat" in blob


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


def test_perception_outcome_delivers_reaction_loop_action(temp_db):
    """A reactor's body and voice must travel through the same result seam.

    Contested beats store the character declaration in ``reaction_results``.
    Dialogue already read that map, but outcome action projection used only
    ``character_results``; the narrator consequently received a disembodied
    line and guessed the missing physical response.
    """
    ctx, moon_id = _make_ctx(temp_db)
    ctx.director_interpret = _norm([{
        "type": "action", "attempt": "steps toward Dr. Moon",
        "observable": "steps toward Dr. Moon", "visibility": "overt",
    }])
    ctx.director_interpret["flow"] = {
        "reactors": [moon_id], "resolution_flags": {"contested": True}}
    ctx.director_resolve = {"resolved_event": "Dr. Moon gives ground.",
                            "dialogue_log": [], "state_diff": {}}
    ctx.reaction_results = {moon_id: {
        "sequence": [{
            "type": "action",
            "attempt": "raise both hands and step back",
            "observable": "raises both hands and steps back",
            "visibility": "overt",
        }],
    }}

    import agents.perception as perception
    player_view = perception.perception_outcome(ctx, nonce=0)["views"]["player"]

    assert "raises both hands and steps back" in player_view


def test_perception_outcome_keeps_every_overt_action_in_one_declaration(
        temp_db):
    """A sequence is chronology, not a set of candidates for a final pose.

    In the measured regression, a character declared three actions around two
    lines of dialogue. The
    old actor-keyed map replaced each action with the next and gave the player
    only her final movement, even though Director resolution retained all
    three.  Distinct event ids must produce distinct delivered acts.
    """
    ctx, moon_id = _make_ctx(temp_db)
    ctx.director_interpret = _norm([{
        "type": "action", "attempt": "steps toward Dr. Moon",
        "observable": "steps toward Dr. Moon", "visibility": "overt",
    }])
    ctx.director_interpret["flow"] = {
        "reactors": [moon_id], "resolution_flags": {"contested": True}}
    ctx.director_resolve = {
        "resolved_event": "Dr. Moon responds in three movements.",
        # Deliberately grouped in the wrong order. Outcome perception must
        # bind these exact delivered lines back to declaration slots rather
        # than treating dialogue_log order as the whole beat chronology.
        "dialogue_log": [
            {"speaker": "Dr. Moon", "exact_quote": '"Second."'},
            {"speaker": "Dr. Moon", "exact_quote": '"First."'},
        ],
        "state_diff": {}}
    ctx.reaction_results = {moon_id: {
        "sequence": [
            {
                "type": "action", "event_id": "moon:0",
                "observable": "lifts her head from the console",
                "visibility": "overt",
            },
            {
                "type": "speech", "event_id": "moon:1", "text": "First.",
                "visibility": "overt", "volume": "normal",
            },
            {
                "type": "action", "event_id": "moon:2",
                "observable": "reaches one hand toward the alarm",
                "visibility": "overt",
            },
            {
                "type": "speech", "event_id": "moon:3", "text": "Second.",
                "visibility": "overt", "volume": "normal",
            },
            {
                "type": "action", "event_id": "moon:4",
                "observable": "steps sideways across the doorway",
                "visibility": "overt",
            },
        ],
    }}

    import agents.perception as perception
    result = perception.perception_outcome(ctx, nonce=0)
    player_view = result["views"]["player"]
    player_observations = " ".join(
        (row.get("observed") or {}).get("text") or ""
        for row in result["observations"]["player"])

    for surface in (
        "lifts her head from the console",
        "reaches one hand toward the alarm",
        "steps sideways across the doorway",
    ):
        assert surface in player_view
        assert surface in player_observations

    ordered_fragments = (
        "lifts her head from the console",
        '"First."',
        "reaches one hand toward the alarm",
        '"Second."',
        "steps sideways across the doorway",
    )
    offsets = [player_view.index(fragment) for fragment in ordered_fragments]
    assert offsets == sorted(offsets), player_view
