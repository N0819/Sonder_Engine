"""The prose contract (agents/director_prose.py), end to end with stub models.

What is pinned is the ARCHITECTURE the contract exists for:

- the Director writes prose and nothing else; one encoder, assembled from
  the channels the decision model selected, writes the ordered events;
- the encoder's sheet carries exactly the selected channels' chunks;
- its events become the same ledger rows and the same folded `state_diff`
  the causal contract produced, through the same bind/validate/fold;
- the decision model failing grants every channel (fail-open);
- a tool the encoder names as missing buys ONE widened call, whose answer
  replaces the first;
- the causal contract stays the default.
"""

from __future__ import annotations

import pytest

import agents.director as director
from agents import director_prose
from llm import decisions

from tests.test_director_orchestration import (
    _action_interp,
    _fake_agent,
    _make_ctx,
    _steps,
)


POSITIONS_CHUNK = "A CHARACTER'S DECLARED DIRECTION IS THEIRS"
ATTIRE_CHUNK = "CLOTHING TRACKING"


@pytest.fixture
def prose_contract(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    asked = []

    def answer(state, questions):
        asked.append({"state": state, "questions": dict(questions)})
        return {key: {"type": "noul",
                      "noul": 0.95 if key in ("positions", "poses") else 0.02}
                for key in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    return asked


def _walk_events():
    return {
        "events": [
            {"source_entity_id": "character:1", "source_event_id": "x",
             "event": "Mara climbs the stair into the lamp room.",
             "observable": "climbs the stair", "speech": False,
             "targets": ["lamp_room"], "seconds": 20, "movement": None,
             "commitment": "asserted", "item_names": ["Mara"],
             "transforms": [{"item": "Mara",
                             "patch": {"positions": {"Mara": "lamp_room"}}}]},
            {"source_entity_id": "character:1", "source_event_id": "x",
             "event": "The lamp is cold.", "speech": True,
             "targets": ["The Stranger"], "volume": "loud", "seconds": 2,
             "commitment": "asserted", "item_names": ["Mara"],
             "transforms": []},
        ],
        "missing_tools": [], "missing_referents": [], "notes": [],
    }


def test_resolve_runs_author_then_one_encoder(temp_db, monkeypatch,
                                             prose_contract):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs the stair into the lamp "
                                    "room. \"The lamp is cold,\" she calls down."},
        "director_specialist": _walk_events(),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    # Two model calls: the author, then ONE encoder. No hand is called.
    assert _steps(calls) == ["director_prose", "director_specialist"]
    assert calls[0]["role"] == "director"
    assert calls[1]["role"] == "director_specialist"
    # The author's sheet is the prose sheet, not the causal one.
    assert "Convert event_inputs into ordered event ledgers" not in calls[0]["system"]
    assert '{"prose":' in calls[0]["system"]
    # The encoder got the prose and exactly the selected tools.
    sheet = calls[1]["system"]
    assert POSITIONS_CHUNK in sheet
    assert ATTIRE_CHUNK not in sheet
    assert calls[1]["payload"]["prose"].startswith("Mara climbs")
    assert calls[1]["payload"]["granted_tools"] == ["positions", "poses"]
    # Jev judged the prose.
    assert "Mara climbs the stair" in prose_contract[0]["state"]
    # The events became ordered rows; position is chronology.
    rows = out["ledgers"]
    assert [row["chrono_id"] for row in rows] == [1, 2]
    assert rows[0]["categories"] == ["positions"]
    assert "speech" in rows[1]["categories"]
    # The existing fold produced the engine input.
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"
    record = out["orchestration"]["prose_contract"]
    assert record["prose"].startswith("Mara climbs")
    assert record["jev"]["selected"] == ["positions", "poses"]
    assert out["orchestration"]["specialists"]["spatial"]["ran"] is True


def test_decision_model_failure_grants_every_channel(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")

    def boom(state, questions):
        raise decisions.DecisionError("unreachable")

    monkeypatch.setattr(decisions, "OVERRIDE", boom)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": _walk_events(),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    # The room author also runs (every channel is granted) on its own
    # thread, so find the encoder's call by its key, not its position.
    sheet = next(c for c in calls if c["step_key"] == "director_specialist")["system"]
    assert POSITIONS_CHUNK in sheet and ATTIRE_CHUNK in sheet
    assert out["orchestration"]["prose_contract"]["jev"]["failed"]
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"


def test_a_missing_tool_buys_one_widened_call_that_replaces_the_first(
        temp_db, monkeypatch, prose_contract):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "poses" else 0.0}
        for key in questions})
    first = {"events": [{"source_entity_id": "character:1",
                         "event": "Mara climbs into the lamp room.",
                         "item_names": ["Mara"], "transforms": []}],
             "missing_tools": ["positions"]}
    answers = iter([first, _walk_events()])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": lambda payload: next(answers),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist",
                             "director_specialist"]
    assert POSITIONS_CHUNK not in calls[1]["system"]
    assert POSITIONS_CHUNK in calls[2]["system"]
    # Replaced, not merged: the second answer's two events are the beat.
    assert [row["chrono_id"] for row in out["ledgers"]] == [1, 2]
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"
    encoder = out["orchestration"]["prose_contract"]["encoder"]
    assert encoder["missing_tools"] == ["positions"]
    assert "positions" in encoder["widened_to"]


def test_a_thinner_widened_answer_never_replaces_the_first(temp_db, monkeypatch,
                                                          prose_contract):
    """Chat 153 turn 23: re-asked for one added tool, the encoder returned
    only the events that tool touched. The re-ask now sees its first answer,
    and a replacement with fewer events than the first loses."""
    first = dict(_walk_events(), missing_tools=["sensory_events"])
    thin = {"events": _walk_events()["events"][:1]}
    answers = iter([first, thin])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": lambda payload: next(answers),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert calls[2]["payload"]["previous_events"] == first["events"]
    assert [row["chrono_id"] for row in out["ledgers"]] == [1, 2]
    assert "widen_rejected" in out["orchestration"]["prose_contract"]["encoder"]


def test_a_relocation_the_encoder_wrote_buys_positions(temp_db, monkeypatch,
                                                      prose_contract):
    """Code closes the known dependency the decision model missed: an event
    whose core `movement` names a room needs `positions` (chat 153 turn 8:
    positions scored 0.43, the step into the console room never moved
    anyone)."""
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "poses" else 0.0}
        for key in questions})
    moved = {"events": [{"source_entity_id": "character:1",
                         "event": "Mara climbs into the lamp room.",
                         "movement": {"to_room": "lamp_room", "mover": "Mara",
                                      "arrives": True},
                         "item_names": ["Mara"], "transforms": []}]}
    answers = iter([moved, _walk_events()])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": lambda payload: next(answers),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert POSITIONS_CHUNK in calls[2]["system"]
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"
    assert director_prose.implied_tools(moved["events"]) == ["positions"]


def test_a_destination_the_scene_lacks_buys_rooms():
    """Chat 137 turn 45: with no `rooms`, the encoder put a swallowed body
    at a character id -- the interior was not a room yet. A destination the
    scene does not hold, and this answer does not create, implies `rooms`."""
    scene = {"rooms": {"keeper_room": {}, "lamp_room": {}}}
    into_body = [{"transforms": [{"item": "Hinami", "patch": {
        "positions": {"Hinami": "char_mirelle"}}}]}]
    assert director_prose.implied_tools(into_body, scene) == ["rooms"]
    created = [{"transforms": [{"item": "Hinami", "patch": {
        "rooms": {"mirelle_stomach": {"parent_entity": "char_mirelle"}},
        "positions": {"Hinami": "mirelle_stomach"}}}]}]
    assert director_prose.implied_tools(created, scene) == []
    known = [{"transforms": [{"item": "Mara", "patch": {
        "positions": {"Mara": "lamp_room"}}}]}]
    assert director_prose.implied_tools(known, scene) == []


def test_a_room_is_never_a_positions_key():
    """Chat 137 turn 52: a room keyed into positions (placed in itself)
    passed every floor. Engine floor, both contracts."""
    from agents.common import drop_room_keyed_positions
    warnings = []
    kept = drop_room_keyed_positions(
        {"stomach": "stomach", "Hinami": "stomach", "red tin": "keeper_room"},
        {"stomach", "keeper_room"}, warn=warnings.append)
    assert kept == {"Hinami": "stomach", "red tin": "keeper_room"}
    assert len(warnings) == 1


def test_events_become_rows_with_one_handle_per_thing():
    rows, transforms = director_prose.ledger_from_events([
        {"source_entity_id": "character:1", "event": "Mara lifts the tin.",
         "item_names": ["red tin"],
         "transforms": [{"item": "red tin", "patch": {"inventory_ops": [
             {"op": "transfer", "object_id": "tin", "to_id": "Mara"}]}}]},
        {"source_entity_id": "character:1", "event": "Keep it.",
         "speech": True, "item_names": [], "transforms": []},
        {"source_entity_id": "character:1", "event": "She sets down the Red Tin.",
         "look": "bench", "item_names": ["Red Tin"],
         "transforms": [{"item": "Red Tin", "patch": {
             "inventory_ops": [{"op": "transfer", "object_id": "tin",
                                "to_id": "room"}],
             "contact_ops": [{"op": "remove", "actor": "Mara"}]}}]},
    ])
    assert [row["chrono_id"] for row in rows] == [1, 2, 3]
    # One handle per thing, case-folded; the speaker stands in on a
    # thing-less spoken row.
    assert rows[0]["item_ids"] == rows[2]["item_ids"] == [1]
    assert rows[1]["item_names"] == ["character:1"]
    assert rows[0]["categories"] == ["inventory_ops"]
    assert rows[1]["categories"] == ["speech"]
    assert rows[2]["categories"] == ["inventory_ops", "contact_ops", "attention"]
    assert len(transforms[3]) == 1 and set(transforms[3][0]["patch"]) == {
        "inventory_ops", "contact_ops"}


def test_dispatch_splits_one_transform_across_its_owners(temp_db):
    class Ctx(dict):
        pass
    ctx = Ctx()
    rows, transforms = director_prose.ledger_from_events([
        {"source_entity_id": "character:1", "event": "Mara sets it down.",
         "item_names": ["tin"], "transforms": [{"item": "tin", "patch": {
             "inventory_ops": [{"op": "transfer"}],
             "contact_ops": [{"op": "remove"}]}}]}])
    ctx[director_prose.CTX_KEY] = {"transforms": transforms,
                                   "channels": ["inventory_ops"]}
    plan, answer_for = director_prose.dispatch(ctx, "resolve")
    assert plan["objects"]["scope"] == ["inventory_ops"]
    # contact_ops was written though not granted: still the encoder's work.
    assert plan["contact"]["scope"] == ["contact_ops"]
    assert plan["body"]["run"] is False
    objects = answer_for("objects", {"ledger_items": rows})
    contact = answer_for("contact", {"ledger_items": rows})
    assert objects["results"][0]["transforms"][0]["patch"] == {
        "inventory_ops": [{"op": "transfer"}]}
    assert contact["results"][0]["transforms"][0]["patch"] == {
        "contact_ops": [{"op": "remove"}]}
    assert objects["results"][0]["status"] == "encoded"


def test_interpret_runs_the_same_contract(temp_db, monkeypatch, prose_contract):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "The Stranger says, \"Quiet night.\""},
        "director_specialist": {"events": [
            {"source_entity_id": "persona:primary", "event": "Quiet night.",
             "speech": True, "item_names": ["The Stranger"],
             "transforms": []}]},
    }))
    ctx = _make_ctx(temp_db, player_input='"Quiet night."')
    out = director.director_interpret(ctx, nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist"]
    assert "input side of the beat" in calls[0]["system"]
    assert out["orchestration"]["prose_contract"]["stage"] == "interpret"
    assert any("speech" in (row.get("categories") or [])
               for row in out.get("ledgers") or [])


def test_authority_is_read_on_the_prose_and_never_retries(temp_db, monkeypatch,
                                                         prose_contract):
    """The prose Director keeps two limits; the readings that enforce them
    under the causal contract read its prose here, warn, and never call the
    causal Director back to rewrite."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room. "
                                    "\"I never liked this lighthouse,\" "
                                    "Mara mutters to herself."},
        "director_specialist": _walk_events(),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert "director_resolve" not in _steps(calls)
    assert _steps(calls) == ["director_prose", "director_specialist"]
    assert out.get("player_act_warnings"), (
        "an undeclared character line in the prose went unreported")


def test_the_resolve_is_told_what_the_player_already_did(temp_db, monkeypatch,
                                                         prose_contract):
    """Asserted human input is absent from event_inputs (it already entered
    the world). The causal Director only routed and never needed it; an
    author does, or it writes past it -- chat 153 turn 26, a player-asserted
    landing written over as continued flight. Both the author and the
    encoder receive it."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "The ship touches down."},
        "director_specialist": _walk_events(),
    }))
    interp = _action_interp()
    interp["causal_ledger"] = [
        {"chrono_id": 1, "event": "The Stranger feels the ship begin to land.",
         "commitment": "asserted", "categories": []},
        {"chrono_id": 2, "event": "The Stranger tries to force the door.",
         "commitment": "contestable", "categories": []},
    ]
    ctx = _make_ctx(temp_db, interp=interp)
    director.director_resolve(ctx, nonce=0)
    author, encoder = calls[0]["payload"], calls[1]["payload"]
    assert author["already_happened"] == "The Stranger feels the ship begin to land."
    assert encoder["already_happened"] == author["already_happened"]
    assert "already_happened" in calls[0]["system"]
    assert "already_happened" in calls[1]["system"]


def test_interpret_prose_is_what_already_happened(temp_db):
    ctx = _make_ctx(temp_db, interp={
        "orchestration": {"prose_contract": {"prose": "Hinami grips the bar."}},
        "causal_ledger": [{"event": "ignored", "commitment": "asserted"}]})
    assert director_prose.already_happened(ctx) == "Hinami grips the bar."


ROOM_CHUNK = "ROOM CREATION"


def _designed(rooms):
    """A room designer that drafts each room whole and submits."""
    calls = [{"tool": "draft_room", "args": {"room_id": rid, "room": room}}
             for rid, room in rooms.items()]
    return {"calls": calls + [{"tool": "submit", "args": {}}], "done": True}
GALLERY = {"name": "Lighthouse Gallery", "desc": "A ring of iron walkway.",
           "adjacent": [{"to": "lamp_room", "barrier": "open", "distance": "near"}]}


def _gallery_encoder(ref):
    return {"events": [
        {"source_entity_id": "character:1", "event": "Mara steps out onto the gallery.",
         "item_names": ["Mara"],
         "movement": {"to_room": "new:" + ref, "mover": "Mara", "arrives": True},
         "transforms": [{"item": "Mara",
                         "patch": {"positions": {"Mara": "new:" + ref}}}]}]}


def _jev(granted, bind_to=None):
    def answer(state, questions):
        out = {}
        for key, q in questions.items():
            if q["type"] == "choice":
                out[key] = {"type": "choice", "choice": bind_to or "none",
                            "confidence": 0.9}
            else:
                out[key] = {"type": "noul", "noul": 0.95 if key in granted else 0.0}
        return out
    return answer


def test_places_are_minted_in_parallel_and_bound_by_the_decision_model(
        temp_db, monkeypatch):
    """The room contract is the heaviest sheet; it runs beside the encoder,
    not inside it. The encoder names the new place in the prose's words and a
    decision-model CHOICE binds it to the room the author minted."""
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE",
                        _jev({"rooms", "positions"}, bind_to="lighthouse_gallery"))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara steps out onto the gallery."},
        "director_rooms": _designed({"lighthouse_gallery": GALLERY}),
        "director_specialist": _gallery_encoder("the gallery"),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    by_key = {c["step_key"]: c for c in calls}
    assert set(by_key) == {"director_prose", "director_rooms", "director_specialist"}
    assert ROOM_CHUNK in by_key["director_rooms"]["system"]
    assert ROOM_CHUNK not in by_key["director_specialist"]["system"]
    assert by_key["director_specialist"]["payload"]["places_authored_elsewhere"] is True
    assert "lighthouse_gallery" in out["state_diff"]["rooms"]
    assert out["state_diff"]["positions"]["Mara"] == "lighthouse_gallery"
    assert out["ledgers"][0]["event"] == "The places this beat establishes."
    rooms = out["orchestration"]["prose_contract"]["room_author"]
    assert rooms["ran"] == "parallel"
    assert rooms["bindings"] == {"the gallery": "lighthouse_gallery"}


def test_a_new_place_named_as_minted_binds_without_asking(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    asked = []

    def jev(state, questions):
        asked.extend(q["type"] for q in questions.values())
        return _jev({"rooms", "positions"})(state, questions)

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara steps out onto the gallery."},
        "director_rooms": _designed({"lighthouse_gallery": GALLERY}),
        "director_specialist": _gallery_encoder("The Lighthouse Gallery"),
    }))
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    assert out["state_diff"]["positions"]["Mara"] == "lighthouse_gallery"
    assert "choice" not in asked


def test_an_unforeseen_place_runs_the_room_author_after(temp_db, monkeypatch):
    """The decision model did not grant rooms; the encoder named a new place
    anyway. The author still writes it whole, serially."""
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE",
                        _jev({"positions"}, bind_to="lighthouse_gallery"))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara steps out onto the gallery."},
        "director_rooms": _designed({"lighthouse_gallery": GALLERY}),
        "director_specialist": _gallery_encoder("the gallery"),
    }))
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist", "director_rooms"]
    assert out["state_diff"]["positions"]["Mara"] == "lighthouse_gallery"
    assert out["orchestration"]["prose_contract"]["room_author"]["ran"] == "serial"


def _gallery_placed(eid=None):
    transforms = [{"item": "Mara", "patch": {"positions": {"Mara": "lighthouse_gallery"}}}]
    if eid:
        transforms.append({"item": "brass telescope", "patch": {"entities": {
            eid: {"name": "brass telescope", "description": "A brass telescope on a tripod."}}}})
    return {"events": [
        {"source_entity_id": "character:1", "event": "Mara steps out onto the gallery.",
         "item_names": ["Mara"],
         "movement": {"to_room": "lighthouse_gallery", "mover": "Mara", "arrives": True},
         "transforms": transforms}]}


def _dup_jev(duplicate):
    def answer(state, questions):
        out = {}
        for key, q in questions.items():
            if key.startswith("dup_"):
                out[key] = {"type": "noul", "noul": 0.9 if duplicate else 0.1}
            else:
                out[key] = {"type": "noul",
                            "noul": 0.95 if key in ("positions",) else 0.0}
        return out
    return answer


PLACES = [{"name": "Lighthouse Gallery", "size": "small", "shape": "round"}]


def test_the_directors_three_fields_reserve_a_room_both_workers_use(
        temp_db, monkeypatch):
    """The Director names a new place in three simple fields; code reserves
    its id before either worker starts, so the encoder places into it at once
    while the room author fleshes it out -- keeping the Director's size and
    shape over its own."""
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", _dup_jev(False))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara steps out onto the gallery.",
                           "places": PLACES},
        "director_rooms": _designed({"lighthouse_gallery": dict(GALLERY, size="vast",
                                                                  shape="rectangle")}),
        "director_specialist": _gallery_placed(),
    }))
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    by_key = {c["step_key"]: c for c in calls}
    reserved = {"lighthouse_gallery": {"name": "Lighthouse Gallery",
                                       "size": "small", "shape": "round"}}
    assert by_key["director_specialist"]["payload"]["new_places"] == reserved
    assert by_key["director_rooms"]["payload"]["reserved_places"] == reserved
    room = out["state_diff"]["rooms"]["lighthouse_gallery"]
    assert (room["size"], room["shape"]) == ("small", "round")
    assert out["state_diff"]["positions"]["Mara"] == "lighthouse_gallery"
    assert out["orchestration"]["prose_contract"]["room_author"]["ran"] == "parallel"


def test_a_reserved_room_the_author_left_out_still_stands(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", _dup_jev(False))
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": "Mara steps out onto the gallery.",
                           "places": PLACES},
        "director_rooms": {"calls": [{"tool": "submit", "args": {}}]},
        "director_specialist": _gallery_placed(),
    }))
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    room = out["state_diff"]["rooms"]["lighthouse_gallery"]
    assert room["name"] == "Lighthouse Gallery" and room["size"] == "small"
    assert out["state_diff"]["positions"]["Mara"] == "lighthouse_gallery"


def _furnished_gallery():
    return _designed({"lighthouse_gallery": dict(GALLERY, anchors={
        "telescope": {"desc": "a brass telescope on its tripod", "dir": "n"}})})


def test_a_furnishing_the_encoder_also_made_is_removed_from_the_room(
        temp_db, monkeypatch):
    """Both workers can write the same object at once. The encoder's is the
    one the beat used; the designer's copy goes when the designer itself, in
    its short reconcile call, names it as the same thing."""
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", _dup_jev(False))
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_rooms_reconcile": {"duplicates": [
            {"room": "lighthouse_gallery", "feature": "telescope",
             "same_as": "telescope_1"}]},
        "director_prose": {"prose": "Mara steps out onto the gallery, to the "
                                    "brass telescope.", "places": PLACES},
        "director_rooms": _furnished_gallery(),
        "director_specialist": _gallery_placed(eid="telescope_1"),
    }))
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    room = out["state_diff"]["rooms"]["lighthouse_gallery"]
    assert "telescope" not in (room.get("anchors") or {})
    reconcile = out["orchestration"]["prose_contract"]["room_author"]["reconcile"]
    assert reconcile["removed"][0]["kept"] == "telescope_1"


def test_a_feature_the_designer_does_not_name_is_kept(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", _dup_jev(False))
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_rooms_reconcile": {"duplicates": []},
        "director_prose": {"prose": "Two brass telescopes stand on the gallery.",
                           "places": PLACES},
        "director_rooms": _furnished_gallery(),
        "director_specialist": _gallery_placed(eid="telescope_1"),
    }))
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    assert "telescope" in out["state_diff"]["rooms"]["lighthouse_gallery"]["anchors"]


def test_a_transform_filed_under_the_wrong_thing_still_accounts_for_every_thing(
        temp_db, monkeypatch, prose_contract):
    """The encoder's `item` is a label, the patch is the effect. Filed under
    the room while moving a body, the write stands and nothing is left
    "neither changed nor accounted for" (56 of 61 alignment warnings across
    91 audited beats were this label, every write valid)."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": {"events": [
            {"source_entity_id": "character:1", "event": "Mara climbs into the lamp room.",
             "item_names": ["Lamp Room", "Mara"],
             "transforms": [{"item": "Lamp Room",
                             "patch": {"positions": {"Mara": "lamp_room"}}}]}]},
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert out["state_diff"]["positions"]["Mara"] == "lamp_room"
    assert not [w for w in ctx.warnings if "neither changed nor accounted for" in w]


def test_the_encoder_defaults_to_reasoning_off_and_a_setting_wins(temp_db):
    import json
    from llm import providers
    temp_db.set_setting("reasoning_effort", json.dumps({"default": "high"}))
    assert providers.reasoning_effort_for("director_specialist") == "off"
    assert providers.reasoning_effort_for("director_rooms") == "high"
    temp_db.set_setting("reasoning_effort", json.dumps(
        {"default": "high", "director_specialist": "low"}))
    assert providers.reasoning_effort_for("director_specialist") == "low"


def test_the_director_is_handed_each_persons_pronouns(temp_db, monkeypatch,
                                                      prose_contract):
    """A Director that writes prose writes pronouns. The playerless Aldermill
    run (2026-09-23) wrote Sal Weatherby, she/her on her card, as "he" on
    every beat: the payload carried names alone."""
    import json
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara climbs into the lamp room."},
        "director_specialist": _walk_events(),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    row = dict(ctx.cast[0])
    sheet = json.loads(row["sheet"])
    sheet.setdefault("identity", {})["pronouns"] = {
        "subject": "she", "object": "her", "possessive": "her"}
    row["sheet"] = json.dumps(sheet)
    ctx.cast = [row]
    director.director_resolve(ctx, nonce=0)
    author, encoder = calls[0]["payload"], calls[1]["payload"]
    assert author["pronouns"]["Mara"]["subject"] == "she"
    assert encoder["pronouns"] == author["pronouns"]
    assert "pronouns" in calls[0]["system"]


def test_the_causal_contract_stays_the_default(temp_db, monkeypatch):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": {"ledgers": []}}))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    director.director_resolve(ctx, nonce=0)
    assert _steps(calls)[0] == "director_resolve"
    assert "director_prose" not in _steps(calls)
