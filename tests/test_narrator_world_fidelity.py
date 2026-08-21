"""Regression tests for the Fable-review F1-F4 narrator world-fidelity
backstops (adversarial review, alpha3.3; all closed):

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
    _check_action_direction,
    _check_quote_attribution,
)
from language_runtime import linguistic

from agents.narration import (
    _ordered_beat_events,
    _position_delta_payload,
    _visible_portal_states,
)
from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


# ---- F1: event order ----

def _enforceable():
    """The prefixes the ACTIVE story pack calls enforceable.

    Not `narration._ENFORCEABLE_PREFIXES`, which every one of these files used
    to import: that constant is bound once at import from the ENGLISH pack and
    is a compatibility view for tests and audits, while the three live checks
    read the active pack at use time (`narration.py:991, 1016, 1138`). Scoring
    against the eagerly-bound copy is scoring against an object no story
    evaluates -- `AUDIT_DIRECTOR.md` finding 4's shape, one module over.
    """
    return linguistic("agents.narration", "_ENFORCEABLE_PREFIXES")


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
    # The street is visible from the shop, so its edge and the portal-link
    # touching it are both perceivable. Passing the set is not optional:
    # `visible_rooms` is what decides whether a door into an unseen room is
    # withheld, and it used to default to "do not filter".
    portals = _visible_portal_states(scene, "shop", {"shop", "street"})
    assert portals["front double doors"] == "shut"
    assert portals["escape pod hatch"] == "shut"
    assert portals["door to Street"] == "shut"
    # Every visible door-state agrees -> the generic entry exists.
    assert portals["doors"] == "shut"
    # Mixed states -> no generic entry.
    scene["entities"]["front_doors"]["state"]["link"]["phase"] = "open"
    portals = _visible_portal_states(scene, "shop", {"shop", "street"})
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


# ---- F5: a character's physical act is an event, not scenery ----
#
# The fixture is a plain one -- one character lowers a lantern into a well
# shaft while the player watches -- chosen so the assertions turn on the
# MECHANISM (act vs speech, overt vs concealed, seen vs unseen, direction) and
# nothing else. The defect these cover was found in play on a very different
# scene; none of that belongs in a regression test.

_SEEN = {"rooms": {"yard": {"name": "Well Yard"}},
         "positions": {"Mara": "yard", "Player": "yard"}}


def _lowering_round(visibility="overt"):
    return [{"round": 0, "speaker_id": 1, "speaker": "Mara",
             "result": {"sequence": [
                 {"type": "action",
                  # `attempt` is private: intent, appraisal, what she is
                  # watching for. None of it may reach the narrator.
                  "attempt": "lower the lantern to read the water level while "
                             "checking whether the rope will hold my weight",
                  "observable": "slowly lowers the lantern into the well shaft",
                  "visibility": visibility},
                 {"type": "speech", "text": "It goes down further than I "
                                            "thought."},
             ]}}]


def test_npc_act_enters_the_event_record(temp_db):
    # The defect this closes: for every character except the player,
    # event_order was speech-only, so the beat's actual physical event never
    # reached the narrator as an event at all.
    ctx = _mk_ctx(temp_db, _SEEN)
    ctx.director_interpret = {"sequence": []}
    ctx.interaction_loop = {"rounds": _lowering_round()}
    view = ('The lantern sinks away from you into the shaft. '
            'You hear Mara says: "It goes down further than I thought."')
    events = _ordered_beat_events(
        ctx, "Player", view, {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}},
        scene=_SEEN, p_room="yard")
    assert [(e["actor"], e["kind"]) for e in events] == [
        ("Mara", "action"), ("Mara", "speech")]
    # Declaration order is preserved: the act caused the line.
    assert [e["n"] for e in events] == [1, 2]
    assert "lowers the lantern" in events[0]["action"]
    # The OBSERVABLE surface, never the private attempt: no intent leaks.
    assert "rope" not in events[0]["action"]
    assert "weight" not in events[0]["action"]


def test_concealed_act_stays_out_of_the_event_record(temp_db):
    ctx = _mk_ctx(temp_db, _SEEN)
    ctx.director_interpret = {"sequence": []}
    ctx.interaction_loop = {"rounds": _lowering_round(visibility="concealed")}
    view = 'You hear Mara says: "It goes down further than I thought."'
    events = _ordered_beat_events(
        ctx, "Player", view, {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}},
        scene=_SEEN, p_room="yard")
    assert [e["kind"] for e in events] == ["speech"]


def test_unseen_actor_act_stays_out_of_the_event_record(temp_db):
    # Same act, but the player cannot perceive the actor -- another room, no
    # sight line. The line still arrives (it is audible and IS in the view);
    # the act must not, or the narrator learns something unperceived.
    scene = {"rooms": {"yard": {"name": "Well Yard"},
                       "cellar": {"name": "Cellar", "barrier": "wall"}},
             "positions": {"Mara": "cellar", "Player": "yard"}}
    ctx = _mk_ctx(temp_db, scene)
    ctx.director_interpret = {"sequence": []}
    ctx.interaction_loop = {"rounds": _lowering_round()}
    view = 'You hear Mara says: "It goes down further than I thought."'
    events = _ordered_beat_events(
        ctx, "Player", view, {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}},
        scene=scene, p_room="yard")
    assert [e["kind"] for e in events] == ["speech"]


def test_act_omitted_without_a_scene_fails_closed(temp_db):
    # No scene/room to judge perception with -> no act is listed. A thin beat
    # is recoverable; a leaked one is not.
    ctx = _mk_ctx(temp_db, _SEEN)
    ctx.director_interpret = {"sequence": []}
    ctx.interaction_loop = {"rounds": _lowering_round()}
    view = 'You hear Mara says: "It goes down further than I thought."'
    events = _ordered_beat_events(
        ctx, "Player", view, {"Mara"},
        {"Mara": {"appearance": "", "aliases": []}})
    assert [e["kind"] for e in events] == ["speech"]


def _act(actor, action):
    return [{"n": 1, "actor": actor, "kind": "action", "action": action}]


def test_reversed_direction_fires_and_is_enforceable():
    order = _act("Mara", "slowly lowers the lantern into the well shaft")
    prose = "Mara lifts the lantern clear of the shaft, rope creaking."
    warnings = _check_action_direction(prose, order)
    assert len(warnings) == 1
    assert warnings[0].startswith("Physical direction reversed")
    assert warnings[0].startswith(_enforceable())


def test_direction_rendered_correctly_passes():
    order = _act("Mara", "slowly lowers the lantern into the well shaft")
    prose = "The lantern lowers past the lip of the well, light shrinking."
    assert _check_action_direction(prose, order) == []


def test_missing_act_warns_but_does_not_buy_a_rewrite():
    # The observed failure: the motion simply never appeared on the page.
    order = _act("Mara", "slowly lowers the lantern into the well shaft")
    prose = ("Mara's mouth tightens. The rope creaks in her fist and the yard "
             "smells suddenly of wet stone.")
    warnings = _check_action_direction(prose, order)
    assert len(warnings) == 1
    assert warnings[0].startswith("Physical act from event_order may be missing")
    # Deliberately NOT enforceable: correct prose can render a descent with no
    # directional verb in it at all.
    assert not warnings[0].startswith(_enforceable())


def test_direction_check_ignores_ordinary_prose():
    # Neither the act nor the page names a direction -> nothing to judge.
    order = _act("Mara", "sets the mug down on the table")
    prose = "Mara sets the mug down, the ceramic clicking against the wood."
    assert _check_action_direction(prose, order) == []
    # The tightened vocabulary must not read a rose-gold light, a rising heat
    # or a dropped voice as a body being moved.
    order2 = _act("Mara", "lowers the lantern into the shaft")
    prose2 = ("Rose-gold light drifts up the shaft as heat rises off the "
              "stones. Her voice drops. The lantern lowers out of sight.")
    assert _check_action_direction(prose2, order2) == []


def test_speech_only_record_is_unaffected():
    order = [{"n": 1, "actor": "Mara", "kind": "speech", "quote": "I lifted it."}]
    assert _check_action_direction("Mara says she lowered it.", order) == []


def _bg_ctx(temp_db, scene, action, quote="STOP WHERE YOU ARE."):
    ctx = _mk_ctx(temp_db, scene)
    ctx.director_interpret = {"sequence": []}
    ctx["background_react"] = {
        "fired": True, "name": "A Machine",
        "reactions": [{
            "name": "A Machine",
            "dialogue_log_entry": {"speaker": "A Machine",
                                   "exact_quote": quote,
                                   "visibility": "overt"},
            "action": action,
        }],
        "selected": ["A Machine"],
    }
    return ctx


def test_background_presence_act_enters_the_event_record(temp_db):
    # A background presence's act has a different SHAPE from a character's
    # declared sequence -- one prose string on the reaction, no
    # observable/visibility pair -- so the `_seq_events` path cannot see it and
    # it was collected nowhere.
    scene = {"rooms": {"yard": {"name": "Yard"}},
             "positions": {"Player": "yard", "A Machine": "yard"}}
    action = "Its lens swivels and locks on you, the weapon holding its aim."
    ctx = _bg_ctx(temp_db, scene, action)
    view = 'You hear A Machine says: "STOP WHERE YOU ARE."'
    events = _ordered_beat_events(
        ctx, "Player", view, {"A Machine"},
        {"A Machine": {"appearance": "", "aliases": []}},
        scene=scene, p_room="yard")
    assert [e["kind"] for e in events] == ["speech", "action"]
    assert events[1]["actor"] == "A Machine"
    assert events[1]["action"] == action


def test_background_act_from_an_unseen_presence_is_withheld(temp_db):
    # The line is audible through the wall and IS in the view; the act is not
    # perceptible and must not be listed.
    scene = {"rooms": {"yard": {"name": "Yard"},
                       "vault": {"name": "Vault", "barrier": "wall"}},
             "positions": {"Player": "yard", "A Machine": "vault"}}
    ctx = _bg_ctx(temp_db, scene, "Its lens swivels and locks on you.")
    view = 'You hear A Machine says: "STOP WHERE YOU ARE."'
    events = _ordered_beat_events(
        ctx, "Player", view, {"A Machine"},
        {"A Machine": {"appearance": "", "aliases": []}},
        scene=scene, p_room="yard")
    assert [e["kind"] for e in events] == ["speech"]


def test_background_act_survives_a_reaction_with_no_line(temp_db):
    # A presence that only ACTS still emits an event. Nothing about the act
    # depends on it having spoken.
    scene = {"rooms": {"yard": {"name": "Yard"}},
             "positions": {"Player": "yard", "A Machine": "yard"}}
    ctx = _bg_ctx(temp_db, scene, "It rolls a half-meter closer.", quote="")
    events = _ordered_beat_events(
        ctx, "Player", "The yard is quiet.", {"A Machine"},
        {"A Machine": {"appearance": "", "aliases": []}},
        scene=scene, p_room="yard")
    assert [e["kind"] for e in events] == ["action"]
    assert "half-meter closer" in events[0]["action"]


# A background presence is not cast, and the scene places it under a scene
# ENTITY id when it places it at all -- so the name-keyed room lookup comes
# back empty for one the scene places nowhere, and for one whose name two
# entities answer to (chat 78's cell holds a guard at each of two corner
# stations). The room-level fallback under this gate then reads an unknown
# room as the PLAYER'S OWN, so an act from behind a one-way window arrived at
# the narrator as an enforced fact. The tests below use placements the lookup
# cannot answer; with the presence sitting in `positions` under its own name
# the broken gate and the repaired one agree and the defect is invisible.

def _yard_and_vault(**positions):
    return {"rooms": {"yard": {"name": "Yard"},
                      "vault": {"name": "Vault", "barrier": "wall"}},
            "positions": {"Player": "yard", **positions},
            "entities": {}}


_HEARD = 'You hear A Machine says: "STOP WHERE YOU ARE."'


def _bg_events(ctx, scene):
    return _ordered_beat_events(
        ctx, "Player", _HEARD, {"A Machine"},
        {"A Machine": {"appearance": "", "aliases": []}},
        scene=scene, p_room="yard")


def test_background_act_is_gated_by_the_room_the_stage_voiced_it_at(temp_db):
    # The background stage resolves where the presence stands to decide what
    # it perceives, and now records that room on the reaction. Same act, same
    # scene, two rooms: co-present is listed, walled off is not.
    scene = _yard_and_vault()
    action = "Its lens swivels and locks on you, the weapon holding its aim."

    ctx = _bg_ctx(temp_db, scene, action)
    ctx["background_react"]["reactions"][0]["room"] = "yard"
    assert [e["kind"] for e in _bg_events(ctx, scene)] == ["speech", "action"]

    ctx = _bg_ctx(temp_db, scene, action)
    ctx["background_react"]["reactions"][0]["room"] = "vault"
    assert [e["kind"] for e in _bg_events(ctx, scene)] == ["speech"]


def test_background_act_falls_back_to_the_stored_station_room(temp_db):
    # A reaction replayed from a stored turn predates the stage recording its
    # room, so the resolver answers from the presence's own record instead.
    scene = _yard_and_vault()
    ctx = _bg_ctx(temp_db, scene, "Its lens swivels and locks on you.")
    temp_db.wset(ctx.chat.id, "background_presences",
                 {"A Machine": {"sketch": {"station_room": "vault"}}})
    assert [e["kind"] for e in _bg_events(ctx, scene)] == ["speech"]

    ctx = _bg_ctx(temp_db, scene, "Its lens swivels and locks on you.")
    temp_db.wset(ctx.chat.id, "background_presences",
                 {"A Machine": {"sketch": {"station_room": "yard"}}})
    assert [e["kind"] for e in _bg_events(ctx, scene)] == ["speech", "action"]


def test_background_act_from_an_unplaceable_presence_is_withheld(temp_db):
    # Nothing places this body: no position, no entity, no station room, no
    # room on the reaction. The gate's contract is that it fails CLOSED, and
    # for background presences it did the exact opposite.
    scene = _yard_and_vault()
    ctx = _bg_ctx(temp_db, scene, "Its lens swivels and locks on you.")
    assert [e["kind"] for e in _bg_events(ctx, scene)] == ["speech"]


def test_a_silent_sight_channel_carries_no_standing_sight():
    """The manifest said `status: silent, why: no light reaches this room` and
    listed `["storm sky", "heavy rain", "light: dark"]` as standing content on
    the same channel, because `sight_standing` was assembled BEFORE
    `sight_status` was decided and `light: {light}` was appended
    unconditionally. `weather_words`' sight arm gates on room EXPOSURE, never
    on light, so any exposed room at night produced it.

    Not a leak -- the storm is legitimately the player's, and it still arrives
    on hearing and touch. But SENSORY CHANNELS is the one payload field the
    narrator prompt is told to read as authoritative, and it contradicted
    itself there."""
    from agents.narration import _sensory_channels_manifest

    scene = {
        "rooms": {"yard": {"name": "Yard", "adjacent": [],
                           "light": "dark", "outdoor": True}},
        "positions": {"Hinami": "yard"},
        "entities": {}, "contacts": [], "attire": {}, "overlays": {},
        "weather": {"sky": "storm", "precipitation": "rain",
                    "intensity": "heavy", "wind": "gale"},
    }
    manifest = _sensory_channels_manifest(
        scene, "Hinami", "", [], set(), {}, "yard")
    sight = manifest["sight"]

    assert sight["status"] == "silent"
    assert "standing" not in sight
    # The other two channels still carry the storm, which is the whole reason
    # this is a contradiction rather than a subtraction.
    assert manifest["hearing"]["status"] == "live"


def test_a_lit_room_still_lists_its_standing_sight():
    from agents.narration import _sensory_channels_manifest

    scene = {
        "rooms": {"yard": {"name": "Yard", "adjacent": [], "light": "lit"}},
        "positions": {"Hinami": "yard"},
        "entities": {}, "contacts": [], "attire": {}, "overlays": {},
    }
    sight = _sensory_channels_manifest(
        scene, "Hinami", "", [], set(), {}, "yard")["sight"]

    assert sight["status"] == "live"
    assert "light: lit" in sight["standing"]
