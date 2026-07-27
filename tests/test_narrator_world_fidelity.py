"""Regression tests for the Fable-review F1-F4 narrator world-fidelity
backstops (docs/FABLE_REVIEW_FOLLOWUPS.md):

F1 — event ordering: a quoted response must not render before the event it
answers; the narrator receives the pipeline's own numbered event_order and
_check_event_order fires on a verbatim position inversion.

F2 — position continuity: a cast character narrated in a room differing from
this beat's committed position, with no movement this beat, fires
_check_position_fidelity.

F3 — portal state: a shut portal rendered open (or vice versa) fires
_check_portal_fidelity; _visible_portal_states derives the payload from
entity link/hatch state and door adjacency barriers.

F4 — quote attribution: a quoted line whose nearest preceding actor
reference is a DIFFERENT speaker fires _check_quote_attribution; a trailing
attribution naming the true speaker clears it, and a mismatched-gender
pronoun in between makes it decline to call.
"""

import json
import time

from agents.common import (
    _check_event_order,
    _check_portal_fidelity,
    _check_position_fidelity,
    _check_quote_attribution,
)
from agents.narration import (
    _ordered_beat_events,
    _position_delta_payload,
    _visible_portal_states,
)
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


# ---- F1: event order ----

def _events(*pairs):
    out = []
    for i, (actor, quote) in enumerate(pairs, 1):
        out.append({"n": i, "actor": actor, "kind": "speech", "quote": quote})
    return out


def test_event_order_inversion_fires():
    # The NPC's answer renders BEFORE the player's question (impostor t6).
    order = _events(("Ilya", "Where were you at midnight?"),
                    ("Sir Julian", "In the library, as always."))
    prose = ('"In the library, as always," Julian says. Ilya leans in. '
             '"Where were you at midnight?"')
    warnings = _check_event_order(prose, order)
    assert len(warnings) == 1
    assert warnings[0].startswith("Dialogue rendered out of order")
    assert "In the library" in warnings[0]


def test_event_order_correct_order_passes():
    order = _events(("Ilya", "Where were you at midnight?"),
                    ("Sir Julian", "In the library, as always."))
    prose = ('Ilya leans in. "Where were you at midnight?" '
             '"In the library, as always," Julian says.')
    assert _check_event_order(prose, order) == []


def test_event_order_player_line_precedes_npc_answer():
    # The spec's own test hint: a beat where an NPC line answers the player's
    # line -- the player's line's prose position must precede the NPC line's.
    order = _events(("Player", "Who locked the console?"),
                    ("Vorne", "I did. On my own authority."))
    backwards = ('"I did. On my own authority," Vorne says, before I can '
                 'finish asking: "Who locked the console?"')
    warnings = _check_event_order(backwards, order)
    assert len(warnings) == 1
    forwards = ('"Who locked the console?" '
                '"I did. On my own authority," Vorne says.')
    assert _check_event_order(forwards, order) == []


def test_event_order_missing_quotes_are_skipped():
    # Echo-stripped player lines simply don't match; no crash, no warning.
    order = _events(("Player", "a line the echo strip removed"),
                    ("Vorne", "Understood."))
    assert _check_event_order('"Understood," Vorne says.', order) == []
    assert _check_event_order("", order) == []
    assert _check_event_order("prose", None) == []


# ---- F4: quote attribution ----

def test_wrong_nearest_actor_fires():
    # Enterprise t4: Vorne's line renders right after the anonymous woman.
    order = [{"n": 1, "actor": "Vorne", "kind": "speech",
              "quote": "Fine. But when you get the wrong door slammed in "
                       "your face, don't say I didn't warn you."}]
    prose = ("The unfamiliar woman pulls her hands back from the console, "
             "crossing her arms. \"Fine. But when you get the wrong door "
             "slammed in your face, don't say I didn't warn you.\"")
    order.append({"n": 2, "actor": "the unfamiliar woman", "kind": "speech",
                  "quote": "I second that."})
    warnings = _check_quote_attribution(prose, order)
    assert len(warnings) == 1
    assert warnings[0].startswith("Quote attributed to wrong speaker")
    assert "Vorne" in warnings[0]


def test_trailing_attribution_clears():
    order = [{"n": 1, "actor": "Vorne", "kind": "speech",
              "quote": "Don't say I didn't warn you."},
             {"n": 2, "actor": "the unfamiliar woman", "kind": "speech",
              "quote": "I second that."}]
    prose = ("The unfamiliar woman crosses her arms. \"Don't say I didn't "
             "warn you,\" Vorne says.")
    assert _check_quote_attribution(prose, order) == []


def test_correct_nearest_actor_passes():
    order = [{"n": 1, "actor": "Vorne", "kind": "speech",
              "quote": "Don't say I didn't warn you."},
             {"n": 2, "actor": "the unfamiliar woman", "kind": "speech",
              "quote": "I second that."}]
    prose = ("Vorne pulls his hands back from the console. \"Don't say I "
             "didn't warn you.\" The unfamiliar woman nods once. "
             "\"I second that.\"")
    assert _check_quote_attribution(prose, order) == []


def test_mismatched_pronoun_between_declines_to_call():
    # "Vorne nods. She says, '...'" -- the pronoun re-points the reader away
    # from Vorne (he/him), so the check must not call it.
    order = [{"n": 1, "actor": "Mara", "kind": "speech",
              "quote": "We hold the line here."},
             {"n": 2, "actor": "Vorne", "kind": "speech",
              "quote": "Agreed."}]
    prose = 'Vorne nods. She says, "We hold the line here."'
    pronouns = {"Vorne": {"subject": "he", "object": "him",
                          "possessive": "his"},
                "Mara": {"subject": "she", "object": "her",
                         "possessive": "hers"}}
    assert _check_quote_attribution(prose, order,
                                    actor_pronouns=pronouns) == []


def test_no_actor_reference_makes_no_call():
    order = [{"n": 1, "actor": "Vorne", "kind": "speech",
              "quote": "Nothing goes out without my order."}]
    prose = 'A voice cuts through: "Nothing goes out without my order."'
    assert _check_quote_attribution(prose, order) == []


# ---- F2: position continuity ----

_ROOMS = {"tardis": "TARDIS", "street": "Bethnal Green Road"}


def test_unmoved_character_in_wrong_room_fires():
    # DW t7: the Doctor sprinted up the road last beat; this beat's prose
    # quietly returns him to the TARDIS doorway with no movement event.
    facts = [{"name": "The Doctor", "room_id": "street", "moved": False}]
    prose = "The Doctor stands in the TARDIS doorway, watching the rain."
    warnings = _check_position_fidelity(prose, facts, _ROOMS)
    assert len(warnings) == 1
    assert warnings[0].startswith("Character placed in wrong room")
    assert "Doctor" in warnings[0] and "TARDIS" in warnings[0]


def test_moved_character_is_exempt():
    facts = [{"name": "The Doctor", "room_id": "tardis", "moved": True}]
    prose = "The Doctor steps back in the TARDIS doorway."
    assert _check_position_fidelity(prose, facts, _ROOMS) == []


def test_character_in_own_room_passes():
    facts = [{"name": "The Doctor", "room_id": "tardis", "moved": False}]
    prose = "The Doctor waits in the TARDIS, hand on the console."
    assert _check_position_fidelity(prose, facts, _ROOMS) == []


def test_look_verbs_do_not_trip_position_check():
    facts = [{"name": "The Doctor", "room_id": "street", "moved": False}]
    prose = "The Doctor glances at the TARDIS, then keeps walking."
    assert _check_position_fidelity(prose, facts, _ROOMS) == []


def test_quoted_speech_is_exempt_from_position_check():
    facts = [{"name": "The Doctor", "room_id": "street", "moved": False}]
    prose = 'Rose grins. "The Doctor is in the TARDIS, probably."'
    assert _check_position_fidelity(prose, facts, _ROOMS) == []


# ---- F3: portal state ----

def test_shut_portal_rendered_open_fires():
    # DW t9 shuts the double doors; t12 renders "through the open doors".
    portals = {"double doors": "shut"}
    prose = "Through the open double doors, the streetlights flicker."
    warnings = _check_portal_fidelity(prose, portals)
    assert len(warnings) == 1
    assert warnings[0].startswith("Portal state contradicts the scene")


def test_generic_doors_entry_catches_bare_reference():
    portals = {"doors": "shut"}
    prose = "Through the open doors, the street is loud again."
    assert len(_check_portal_fidelity(prose, portals)) == 1


def test_portal_state_matching_prose_passes():
    portals = {"double doors": "shut"}
    prose = "The double doors stay shut against the wind."
    assert _check_portal_fidelity(prose, portals) == []
    portals = {"double doors": "open"}
    prose = "The open double doors let the cold in."
    assert _check_portal_fidelity(prose, portals) == []


def test_open_portal_rendered_shut_fires():
    portals = {"cargo hatch": "open"}
    prose = "The cargo hatch stays sealed no matter what he tries."
    assert len(_check_portal_fidelity(prose, portals)) == 1


def test_unmentioned_portal_is_silent():
    portals = {"double doors": "shut"}
    prose = "Rain hammers the windows."
    assert _check_portal_fidelity(prose, portals) == []


# ---- payload builders ----

def test_visible_portal_states_from_link_hatch_and_edges():
    scene = {
        "rooms": {
            "shop": {"name": "Shop", "adjacent": [
                {"to": "street", "barrier": "closed_door", "distance": "near"},
            ]},
            "street": {"name": "Street", "adjacent": []},
            "pod_interior": {"name": "Pod Interior", "parent_entity": "pod"},
        },
        "positions": {"pod": "shop"},
        "entities": {
            "front_doors": {"name": "front double doors", "kind": "door",
                            "state": {"link": {"rooms": ["shop", "street"],
                                               "phase": "closed"}}},
            "pod": {"name": "escape pod", "kind": "vehicle",
                    "state": {"transit": {"phase": "docked",
                                          "hatch": "closed"}}},
        },
    }
    portals = _visible_portal_states(scene, "shop")
    assert portals["front double doors"] == "shut"
    assert portals["escape pod hatch"] == "shut"
    assert portals["door to Street"] == "shut"
    # Every visible door-state agrees -> the generic entry exists.
    assert portals["doors"] == "shut"
    # Mixed states -> no generic entry.
    scene["entities"]["front_doors"]["state"]["link"]["phase"] = "open"
    portals = _visible_portal_states(scene, "shop")
    assert portals["front double doors"] == "open"
    assert "doors" not in portals


def _mk_ctx(temp_db, scene, outcome_scene=None, cast_names=("Mara",)):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    cast = []
    for name in cast_names:
        sheet = default_character_data(name)
        cast.append({"id": len(cast) + 1, "sheet": json.dumps(sheet),
                     "cstate": "{}", "status": "active"})
    temp_db.wset(chat_id, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=3, player_input="hi",
                      created=time.time()),
        cast=cast, input="hi")
    if outcome_scene is not None:
        ctx._extra["outcome_scene"] = outcome_scene
    return ctx


def test_position_delta_payload_reports_unmoved_and_moved(temp_db):
    committed = {
        "rooms": {"bridge": {"name": "Bridge"},
                  "ready_room": {"name": "Ready Room"}},
        "positions": {"Mara": "bridge", "Player": "bridge"},
    }
    ctx = _mk_ctx(temp_db, committed, outcome_scene=committed)
    chat = {"id": ctx.chat.id}
    payload, facts, room_names = _position_delta_payload(
        ctx, chat, "Player", "bridge", {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    assert payload["Mara"]["moved"] is False
    assert payload["Mara"]["room"] == "Bridge"
    assert facts == [{"name": "Mara", "room_id": "bridge", "moved": False}]
    assert room_names["ready_room"] == "Ready Room"

    moved_scene = json.loads(json.dumps(committed))
    moved_scene["positions"]["Mara"] = "ready_room"
    ctx2 = _mk_ctx(temp_db, committed, outcome_scene=moved_scene)
    payload2, facts2, _ = _position_delta_payload(
        ctx2, {"id": ctx2.chat.id}, "Player", "bridge", {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    # S3-A4: Mara LEFT the player's room (bridge -> ready_room).  The
    # player has not perceived her destination, so she must not appear in
    # the position delta payload with her new room name.
    assert "Mara" not in payload2
    assert facts2 == []


def test_position_delta_payload_gates_on_sight(temp_db):
    """S3-A4 (second half): co-location was the whole gate, so a character who
    walked into the player's PITCH-DARK room still arrived in the payload with
    moved=True -- and the F2 check then enforces prose agreement with a body
    the player never perceived. Sight now decides inclusion; light in the room
    is what makes the same beat perceptible or not."""
    dark = {
        "rooms": {"bridge": {"name": "Bridge", "light": "dark"},
                  "ready_room": {"name": "Ready Room"}},
        "positions": {"Mara": "ready_room", "Player": "bridge"},
    }
    entered = json.loads(json.dumps(dark))
    entered["positions"]["Mara"] = "bridge"
    ctx = _mk_ctx(temp_db, dark, outcome_scene=entered)
    payload, facts, _ = _position_delta_payload(
        ctx, {"id": ctx.chat.id}, "Player", "bridge", {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    assert payload == {} and facts == []

    # Same beat with the lights on: she is plainly visible and must still be
    # narrated -- over-denial here would break ordinary co-present narration.
    lit = json.loads(json.dumps(dark))
    lit["rooms"]["bridge"].pop("light")
    lit_entered = json.loads(json.dumps(lit))
    lit_entered["positions"]["Mara"] = "bridge"
    ctx = _mk_ctx(temp_db, lit, outcome_scene=lit_entered)
    payload, facts, _ = _position_delta_payload(
        ctx, {"id": ctx.chat.id}, "Player", "bridge", {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    assert payload["Mara"]["moved"] is True
    assert facts == [{"name": "Mara", "room_id": "bridge", "moved": True}]
    # No sight line into the ready room -> the origin is withheld even though
    # the arrival itself is perceived.
    assert payload["Mara"]["prev_room"] is None


def test_position_delta_payload_names_origin_only_when_visible(temp_db):
    """The origin room's DISPLAY NAME is a second, separate perception: seeing
    someone come through a door tells you nothing about the room behind it.
    An open sight line makes it the player's to know."""
    base = {
        "rooms": {
            "bridge": {"name": "Bridge", "adjacent": [
                {"to": "ready_room", "barrier": "open", "distance": "near"}]},
            "ready_room": {"name": "Ready Room", "adjacent": [
                {"to": "bridge", "barrier": "open", "distance": "near"}]},
        },
        "positions": {"Mara": "ready_room", "Player": "bridge"},
    }
    entered = json.loads(json.dumps(base))
    entered["positions"]["Mara"] = "bridge"
    ctx = _mk_ctx(temp_db, base, outcome_scene=entered)
    payload, _, _ = _position_delta_payload(
        ctx, {"id": ctx.chat.id}, "Player", "bridge", {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    assert payload["Mara"]["prev_room"] == "Ready Room"

    # A wall between them carries the same movement with no visible origin.
    walled = json.loads(json.dumps(base))
    for rid, other in (("bridge", "ready_room"), ("ready_room", "bridge")):
        walled["rooms"][rid]["adjacent"] = [
            {"to": other, "barrier": "wall", "distance": "near"}]
    walled_entered = json.loads(json.dumps(walled))
    walled_entered["positions"]["Mara"] = "bridge"
    ctx = _mk_ctx(temp_db, walled, outcome_scene=walled_entered)
    payload, _, _ = _position_delta_payload(
        ctx, {"id": ctx.chat.id}, "Player", "bridge", {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    assert payload["Mara"]["moved"] is True
    assert payload["Mara"]["prev_room"] is None


def test_position_delta_payload_skips_rear_arc_entrant(temp_db):
    """A body in the player's rear blind spot delivers no new visual detail
    (spatial.entity_arc), so a character who slipped in behind them is not a
    fact the narrator may be held to."""
    rooms = {"taproom": {"name": "the Taproom", "anchors": {
        "bar": {"desc": "the long oak bar", "dir": "n"},
        "door": {"desc": "the front door", "dir": "e"}}},
        "yard": {"name": "the Yard"}}
    prev = {"rooms": rooms, "positions": {"Player": "taproom",
                                          "Creeper": "yard"},
            "stations": {"Player": {"at": "bar"}, "Creeper": {"at": "door"}},
            "orientation": {"Player": {"facing": "w"}}}
    now = json.loads(json.dumps(prev))
    now["positions"]["Creeper"] = "taproom"
    ctx = _mk_ctx(temp_db, prev, outcome_scene=now, cast_names=("Creeper",))
    payload, facts, _ = _position_delta_payload(
        ctx, {"id": ctx.chat.id}, "Player", "taproom", {"Creeper"},
        {"Creeper": {"appearance": "", "aliases": []}})
    assert payload == {} and facts == []

    # Turn to face the door and the same arrival is seen.
    now["orientation"]["Player"]["facing"] = "e"
    ctx = _mk_ctx(temp_db, prev, outcome_scene=now, cast_names=("Creeper",))
    payload, _, _ = _position_delta_payload(
        ctx, {"id": ctx.chat.id}, "Player", "taproom", {"Creeper"},
        {"Creeper": {"appearance": "", "aliases": []}})
    assert payload["Creeper"]["moved"] is True


def test_narrator_payload_builds_with_visible_adjacent_rooms(temp_db, monkeypatch):
    """Crash regression: the narrator built its visible-room set with
    ``set(visible_adjacent_rooms(...))``, but that helper returns room RECORDS
    ({room_id, room_name, barrier, description}) -- ``TypeError: unhashable
    type: 'dict'`` on every awake, non-establishment turn whose room had a
    sight-permitting adjacency. The payload must build, and portal_states must
    stay scoped (S3-A5) to the rooms the player can see."""
    import agents.narration as narration

    scene = {
        "rooms": {
            "r1": {"name": "Hall", "notes": "a hall", "adjacent": [
                {"to": "r2", "barrier": "open"},
                {"to": "r3", "barrier": "wall"}]},
            "r2": {"name": "Kitchen", "notes": "a kitchen", "adjacent": [
                {"to": "r1", "barrier": "open"}]},
            "r3": {"name": "Cellar", "adjacent": [
                {"to": "r1", "barrier": "wall"}]},
        },
        "positions": {"Player": "r1", "kitchen_door": "r2",
                      "cellar_door": "r3"},
        "entities": {
            "kitchen_door": {"name": "kitchen door", "kind": "door",
                             "state": {"open": True}},
            "cellar_door": {"name": "cellar door", "kind": "door",
                            "state": {"open": False}},
        },
    }
    ctx = _mk_ctx(temp_db, scene, outcome_scene=scene, cast_names=())
    # The director resolves the player's room onto the context; the persona
    # here has no positions entry of its own.
    ctx["_player_room"] = "r1"
    ctx["director_interpret"] = {"sequence": [], "speech": None}
    ctx["perception_outcome"] = {"views": {"player": "The hall is quiet."}}

    captured = {}

    def _fake_agent_json(step_key, model_key, prompt, payload, **kw):
        captured["payload"] = payload
        return {"prose": "The hall stays quiet.", "new_specifics": []}

    monkeypatch.setattr(narration, "_agent_json", _fake_agent_json)
    monkeypatch.setattr(narration, "validate_llm_output",
                        lambda key, out: (out, []))

    out = narration.narrator(ctx, 0)
    assert out["prose"]
    portals = captured["payload"].get("portal_states") or {}
    # Visible through the open doorway; the walled-off cellar's door is not.
    assert portals.get("kitchen door") == "open"
    assert "cellar door" not in portals


def test_ordered_beat_events_order_and_view_filter(temp_db):
    ctx = _mk_ctx(temp_db, {"rooms": {}, "positions": {}})
    ctx.director_interpret = {"sequence": [
        {"type": "speech", "text": "Who locked the console?"},
        {"type": "action", "attempt": "step to the console",
         "observable": "steps to the console"},
    ]}
    ctx.interaction_loop = {"rounds": [
        {"round": 0, "speaker_id": 1, "speaker": "Mara",
         "result": {"sequence": [
             {"type": "speech", "text": "I did. On my own authority."},
             # Not delivered to the player's view -> must be filtered out.
             {"type": "speech", "text": "A line the player never heard."},
         ]}},
    ]}
    view = ('Mara squares up. "I did. On my own authority."')
    events = _ordered_beat_events(
        ctx, "Player", view, {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    kinds = [(e["actor"], e["kind"]) for e in events]
    assert kinds == [("Player", "speech"), ("Player", "action"),
                     ("Mara", "speech")]
    assert [e["n"] for e in events] == [1, 2, 3]
    assert events[2]["quote"] == "I did. On my own authority."
    # The undelivered line is absent (info barrier).
    assert all("never heard" not in str(e.get("quote")) for e in events)


def test_ordered_beat_events_unrecognized_speaker_gets_label(temp_db):
    ctx = _mk_ctx(temp_db, {"rooms": {}, "positions": {}})
    ctx.director_interpret = {"sequence": []}
    ctx.interaction_loop = {"rounds": [
        {"round": 0, "speaker_id": 1, "speaker": "Mara",
         "result": {"sequence": [
             {"type": "speech", "text": "You should not be here."},
         ]}},
    ]}
    view = 'A woman in a gray uniform speaks: "You should not be here."'
    events = _ordered_beat_events(
        ctx, "Player", view, set(),  # player does NOT recognize Mara
        {"Mara": {"appearance": "Mara, a woman in a gray uniform.",
                  "aliases": []}})
    assert len(events) == 1
    # The binding uses the appearance-derived anonymous label, never the
    # canonical name the player has not learned.
    assert "Mara" not in events[0]["actor"]
    assert "woman" in events[0]["actor"]
