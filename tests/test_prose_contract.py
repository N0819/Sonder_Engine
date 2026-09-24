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


def test_an_unreserved_new_place_is_built_after_and_bound_by_the_decision_model(
        temp_db, monkeypatch):
    """The room contract is the heaviest sheet and is never inside the
    encoder. A place the Director did not reserve is built once the encoder
    names it, in the prose's words, and a decision-model CHOICE binds it to
    the room the author minted. A room grant alone no longer starts the
    author: a grant is as ready for a place described as for one entered
    (owner, 2026-09-23: "The designer does not need to redo rooms it has
    already made")."""
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
    assert rooms["ran"] == "serial"
    assert rooms["bindings"] == {"the gallery": "lighthouse_gallery"}


def test_the_encoder_is_told_what_of_a_held_place_is_its_own():
    """A doorway, and nothing else of a place the world holds; a place it
    does not hold is named new: for the room author."""
    from llm import prompts
    en = prompts.unified_specialist_prompt(["poses"])
    ja = prompts.unified_specialist_prompt(["poses"], "ja")
    assert "A place the world holds is built already" in en
    assert "write that edge alone" in en
    assert "世界が既に持っている場所は作り終えています" in ja


def test_a_room_grant_with_nothing_to_build_starts_no_designer(temp_db, monkeypatch):
    """Round-4 replays (2026-09-23): the designer redrew rooms the world held
    on six of seven runs, 73-163 s a beat, because a room grant started it
    whatever the beat entered. Nothing reserved, nothing planned, nothing
    named new: no designer."""
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", _jev({"rooms", "positions"}))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara crosses the lamp room."},
        "director_rooms": _designed({"lighthouse_gallery": GALLERY}),
        "director_specialist": _walk_events(),
    }))
    director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    assert "director_rooms" not in _steps(calls)


def test_the_designer_keeps_what_it_built_and_leaves_what_stands():
    scene = {"rooms": {"lamp_room": {"name": "Lamp Room", "adjacent": []}}}
    answer = {"rooms": {
        "gallery": {"name": "Gallery", "adjacent": [{"to": "lamp_room", "barrier": "open"}]},
        "lamp_room": {"desc": "rewritten", "anchors": {"lens": {}},
                      "adjacent": [{"to": "gallery", "barrier": "open"},
                                   {"to": "stair", "barrier": "open"}]},
        "stair_stub": {"desc": "planned, developed now"}}}
    warned = []
    kept = director_prose.keep_new_places(
        answer, dict(scene, rooms=dict(scene["rooms"], stair_stub={})),
        develop={"stair_stub"}, warn=warned.append)["rooms"]
    assert kept["gallery"]["name"] == "Gallery"
    assert kept["lamp_room"] == {"adjacent": [{"to": "gallery", "barrier": "open"}]}
    assert kept["stair_stub"] == {"desc": "planned, developed now"}
    assert len(warned) == 1


def test_the_encoder_may_turn_a_doorway_and_build_nothing():
    scene = {"rooms": {"parlour": {"adjacent": [{"to": "treatment_room"}]},
                       "treatment_room": {}}}
    events = [{"event": "She shuts the treatment-room door.", "transforms": [
        {"item": "door", "patch": {"rooms": {
            "parlour": {"desc": "redrawn", "adjacent": [
                {"to": "treatment_room", "barrier": "closed_door", "dir": "n"}]},
            "new_attic": {"name": "Attic", "adjacent": []}}}}]}]
    warned = []
    out = director_prose.doorway_edits_only(events, scene, warn=warned.append)
    assert out[0]["transforms"] == [{"item": "door", "patch": {"rooms": {
        "parlour": {"adjacent": [{"to": "treatment_room", "barrier": "closed_door"}]}}}}]
    assert warned and "new_attic" in warned[0]


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


def test_the_encoder_is_told_silence_ends_a_contact(temp_db):
    """Playerless Aldermill (2026-09-23): Emory's hold on the ledger aged out
    on a beat whose other contact_ops made the engine read her silence as a
    release -- the causal contact hand was told to supply a continuing
    contact, the encoder's core never was."""
    from llm import prompts
    core = prompts.unified_specialist_prompt(["contact_ops"])
    assert "reads every standing contact you leave unmentioned as ended" in core


def test_a_body_in_view_is_a_source_the_encoder_can_name():
    """Round 3 (2026-09-23): a hand's sacks on the scale were filed as Sal's
    own act because the identity index held no key for him."""
    payload = {"identity_index": {"character:1": "Sal Weatherby"},
               "present_figures": [{"name": "Godenric Brampenford"},
                                   {"name": "Sal Weatherby"}]}
    index = director_prose.identities_with_figures(payload)
    assert index == {"character:1": "Sal Weatherby",
                     "Godenric Brampenford": "Godenric Brampenford"}
    # The resolve hands the figures on its extras, not the payload; a figure
    # standing elsewhere (reserved) is no source this beat.
    index = director_prose.identities_with_figures(
        {"identity_index": {"character:1": "Sal Weatherby"}},
        {"present_figures": [{"name": "Master Wimelard"},
                             {"name": "Aldodin", "reserved": True}]})
    assert index == {"character:1": "Sal Weatherby",
                     "Master Wimelard": "Master Wimelard"}


def test_a_figure_that_acts_on_screen_is_stood():
    from agents.director import _stand_touching_figures
    sd = {}
    figs = [{"name": "Godenric Brampenford", "room": "mill_yard",
             "charter": "aldermill", "body": "hand"}]
    assert _stand_touching_figures(
        {"positions": {"Sal Weatherby": "mill_yard"}}, sd, figs,
        acting=["character:1", "Godenric Brampenford"]) == ["Godenric Brampenford"]
    assert sd["positions"] == {"Godenric Brampenford": "mill_yard"}


def test_a_declared_target_in_the_declarers_words_names_its_body(monkeypatch):
    """Round 3 (2026-09-23) t20: Sal turned to one hand by description and the
    account turned her to another."""
    seen = {"the elderly miller journeyman": ["Kenoreth Bramterwell"],
            "the stones": []}
    monkeypatch.setattr(director, "_bodies_addressed_as",
                        lambda ctx, sc, speaker, forms: seen.get(forms[0], []))
    groups = [{"entity_id": "character:1", "events": [
        {"targets": ["the elderly miller journeyman", "the stones"]},
        {"targets": []}]}]
    director._name_declared_targets(None, {}, groups,
                                    {"character:1": "Sal Weatherby"})
    first, second = groups[0]["events"]
    assert first["target_bodies"] == ["Kenoreth Bramterwell"]
    assert first["targets"] == ["the elderly miller journeyman", "the stones"]
    assert "target_bodies" not in second


def test_a_missing_referent_buys_the_tools_that_make_it(temp_db, monkeypatch,
                                                        prose_contract):
    """Playerless Aldermill round 4 (2026-09-23) t21: the encoder reported
    'corner post' as missing and nothing followed -- the palm on it was
    dropped at the merge. A referent is made with `entities` and stood with
    `positions`, so the one widening pass is granted both."""
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "poses" else 0.0}
        for key in questions})
    first = dict(_walk_events(), missing_referents=["corner post"])
    first["events"][0]["transforms"] = []
    second = _walk_events()
    answers = iter([first, second])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara sets her palm on the corner post."},
        "director_specialist": lambda payload: next(answers),
    }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    specialist = [c for c in calls if c["step_key"] == "director_specialist"]
    assert len(specialist) == 2
    granted = specialist[1]["payload"]["granted_tools"]
    assert "entities" in granted and "positions" in granted
    assert specialist[1]["payload"]["previous_events"] == first["events"]
    encoder = out["orchestration"]["prose_contract"]["encoder"]
    assert encoder["missing_referents"] == ["corner post"]


def test_a_quoted_line_is_a_line_and_a_reported_one_keeps_its_verb():
    """Round 5 (2026-09-23) idx 18/22: a quoted line carrying `act` rendered
    as "sayss Aye, I've got an eye on the apron,." beside the line itself."""
    prose = ('Robkinet leans over the rail. "Aye, I\'ve got an eye on the '
             'apron," he says. Sal asks him what happened at the weir.')
    events = [
        {"speech": True, "act": "says", "event": "Aye, I've got an eye on the apron,"},
        {"speech": True, "act": "ask", "event": "what happened at the weir"},
    ]
    out = director_prose.quoted_lines_keep_their_words(events, prose)
    assert "act" not in out[0]
    assert out[1]["act"] == "ask"
    assert "act" in events[0]          # copied, never mutated


def test_a_line_split_around_its_tag_is_still_a_line():
    """Round 7 (2026-09-23) idx 6: the prose quoted the deputy's words in two
    spans around "he added"; the encoder joined them, the act survived, and
    Sal's view read "addeds Still crossing for now ..." beside the line."""
    prose = ('"Still crossing for now," he added, gruff and practical. '
             '"Long as the drift gets kept off the timbers."')
    events = [{"speech": True, "act": "added", "event":
               "Still crossing for now. Long as the drift gets kept off the timbers."},
              {"speech": True, "act": "added", "event":
               "Still crossing for now, and the bar stays up."}]
    out = director_prose.quoted_lines_keep_their_words(events, prose)
    assert "act" not in out[0]
    assert out[1]["act"] == "added"    # words the prose never quoted stay a report


def test_a_line_framed_in_its_sentence_is_the_quotation():
    """The owner's chat 120 idx 8 (2026-09-23, Ling 3.0 Flash): the spoken
    event held the prose's whole sentence around the player's line, the
    player-speech floor dropped it as invented, and Vexara never heard the
    question. The quotation is the line; the outward step around it is its
    own event, in the order the event wrote it."""
    line = "Nnn... D-do you like what you see?"
    prose = (f'Hinami looks up at Vexara and asks, her voice thin and '
             f'shaking: "{line}" Her breath catches.')
    framed = {"source_entity_id": "persona:10", "speech": True, "act": "",
              "event": f'Hinami, lying bare on the bed, looks up at Vexara and '
                       f'asks, her voice thin and shaking: "{line}"',
              "observable": "Hinami asks, her voice thin and shaking",
              "targets": ["Vexara"], "volume": "quiet", "seconds": 3}
    warned = []
    out = director_prose.spoken_words_are_the_quotation(
        [framed], prose, warn=warned.append)
    assert [e["speech"] for e in out] == [False, True]
    step, said = out
    assert said["event"] == line and said["observable"] == ""
    assert said["volume"] == "quiet" and said["targets"] == ["Vexara"]
    assert step["event"].startswith("Hinami, lying bare on the bed, looks up")
    assert step["observable"] == "Hinami asks, her voice thin and shaking"
    assert "volume" not in step and "seconds" not in step
    assert warned and "kept as its own event" in warned[0]
    assert framed["event"].endswith(f'"{line}"')        # copied, never mutated
    rows, _ = director_prose.ledger_from_events(out)
    assert rows[1]["categories"] == ["speech"] and rows[1]["event"] == line


def test_the_players_input_says_what_their_line_is_on_interpret():
    """The owner's chat 137 idx 46 (round 5): the prose was "," and the
    encoder framed the player's line inside the declaration's narration.
    The input is ground truth for the player's words, so on interpret its
    quotations stand beside the prose's; on resolve only the prose speaks."""
    from types import SimpleNamespace
    ctx = SimpleNamespace(input='You squirm. "Ahh... This is really tight."')
    framed = {"source_entity_id": "persona:10", "speech": True,
              "event": 'Hinami squirms. "Ahh... This is really tight."',
              "observable": "Hinami squirms"}
    quoting = director_prose.quotation_authority(ctx, "interpret", ",")
    out = director_prose.spoken_words_are_the_quotation([framed], quoting)
    assert [(e["speech"], e["event"]) for e in out] == [
        (False, "Hinami squirms."), (True, "Ahh... This is really tight.")]
    assert director_prose.quotation_authority(ctx, "resolve", ",") == ","
    assert director_prose.quotation_authority(SimpleNamespace(), "interpret", "A.") == "A."


def test_a_journey_sets_off_before_its_end_is_built():
    """The owner's chat 153 idx 22-24 (round 7, 2026-09-23): the TARDIS left
    the beach for Kansai and the encoder wrote no transit -- "no destination
    room is named in the prose, so no transit state was written" -- because
    the sheet said setting off was in_transit "with the destination named".
    The engine never required it (`spatial_transit._transit_state`), so the
    ship stayed docked on the beach while the page flew it through the
    vortex, and once it stood it inside its own console room."""
    from llm import prompts
    en = prompts.unified_specialist_prompt(["entities"])
    ja = prompts.unified_specialist_prompt(["entities"], "ja")
    assert ("naming `destination_room` when the world holds the place it is "
            "bound for and leaving it out when it does not yet") in en
    assert "with the destination named" not in en
    assert "まだ持っていなければ書きません――旅は行き先が作られる前に出発し" in ja


def test_every_position_the_encoder_wrote_is_a_stated_crossing():
    """Both stages' records, the later write winning, keys folded -- what the
    floor reads to judge a stated crossing as a declared one (chat 126 idx 9)."""
    interpret = {"events": [{"transforms": [
        {"item": "Hinami", "patch": {"positions": {"Hinami": "treatment_room"}}}]}]}
    resolve = {"events": [
        {"transforms": [{"item": "Mirelle", "patch": {
            "positions": {"Mirelle Sulmirath": "treatment_room"}}}]},
        {"transforms": [{"item": "Hinami", "patch": {
            "positions": {"Hinami": "wash_room"}, "poses": {}}}]},
        "not an event"]}
    assert director_prose.declared_moves(interpret, resolve, None) == {
        "hinami": "wash_room", "mirelle sulmirath": "treatment_room"}


def test_bare_attribution_around_a_line_is_dropped():
    """A tag with no outward motion is the speaker's name, which the row
    already carries: the line alone survives, after or before its tag."""
    prose = '"Keep it shut," Mara says. 「黙って」とミラが言う。'
    events = [{"speech": True, "event": '"Keep it shut," Mara says.',
               "observable": ""},
              {"speech": True, "event": "ミラが言う「黙って」", "observable": ""}]
    out = director_prose.spoken_words_are_the_quotation(events, prose)
    assert [e["event"] for e in out] == ["Keep it shut,", "黙って"]


def test_a_line_that_quotes_someone_keeps_its_words():
    """Two readings are refused: a line quoting another is its own words
    (its inner quotation is not the prose's), and a reported line (`act`)
    only mentions what it quotes."""
    prose = ('Mara says, "Yesterday you said \'Break the lock\', but I won\'t." '
             'Ivo asks what "the weir" means.')
    events = [{"speech": True, "event":
               "Yesterday you said \"Break the lock\", but I won't."},
              {"speech": True, "act": "asks", "event": 'what "the weir" means'},
              {"speech": True, "event": "Keep it shut."}]
    out = director_prose.spoken_words_are_the_quotation(events, prose)
    assert out == events


def test_jev_is_told_what_is_already_owed(temp_db, monkeypatch):
    """Round 7 (2026-09-23) idx 7-22: Jev is asked whether a passage fulfils
    "one already owed" and was never told what was, so the miller's order,
    carried out three times, stayed open fifteen beats."""
    from types import SimpleNamespace
    seen = []

    def jev(state, questions):
        seen.append(state)
        return {key: {"type": "noul", "noul": 0.9 if key == "obligations" else 0.0}
                for key in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    ctx = SimpleNamespace(language="en", add_warning=lambda message: None)
    owed = [{"who": "Emory Vane",
             "what": "Slap it thick along the underside of the neck"}]
    selected, _record = director_prose.select_channels(
        ctx, "resolve", "Emory works tallow into the underside of the neck.",
        {"identity_index": {}}, facts={}, owed=owed)
    assert ("ALREADY OWED: Emory Vane: Slap it thick along the underside "
            "of the neck") in seen[0]
    assert "obligations" in selected


def test_a_past_act_is_not_conjugated_again():
    from agents.common import communication_verb
    assert communication_verb({"act": "added"}) == "added"
    assert communication_verb({"act": "heed"}) == "heeds"
    assert communication_verb({"act": "add"}) == "adds"


def test_an_inflected_act_is_conjugated_once():
    from agents.common import communication_act, communication_awaits_reply, communication_verb
    assert communication_verb({"act": "says"}) == "says"
    assert communication_verb({"act": "said"}) == "says"
    assert communication_verb({"act": "answers"}) == "answers"
    assert communication_verb({"act": "mutters"}) == "mutters"
    assert communication_verb({"act": "mutter"}) == "mutters"
    assert communication_act({"act": "asks"}) == "ask"
    assert communication_awaits_reply({"act": "asks"})


def test_the_encoder_is_told_the_observable_follows_the_prose():
    """Round 5 (2026-09-23) idx 14: three rows' `observable` fields were the
    charter voices' declared acts verbatim -- "kicks the iron dog free" --
    where the prose had resolved them otherwise, and the declared attempt,
    not the resolution, reached the page."""
    from llm import prompts
    core = prompts.unified_specialist_prompt(["poses"])
    assert "where the prose resolved an attempt otherwise, the observable follows the prose" in core


def test_the_places_row_is_the_worlds_not_the_first_speakers():
    """Round 5 (2026-09-23) idx 10: the synthetic places row borrowed the
    first event's source and credited a mill hand with the river."""
    events = [{"source_entity_id": "Miller Robkinet Flourbrooks",
               "source_event_id": "turn:10:figure:0:0:action", "event": "x"}]
    row = director_prose.room_event({"rooms": {"river_alder": {"name": "River Alder"}}},
                                    events)
    assert row["source_entity_id"] == director_prose.ROOM_EVENT_SOURCE
    assert row["source_event_id"] == ""


def test_a_voice_aims_its_line_at_the_body_its_words_name(monkeypatch):
    """Round 5 (2026-09-23): charter voices aimed lines at "the short" --
    sixteen epithet warnings, and every debt they opened owed to no one."""
    named = {"the short": ["Emory Vane"], "the crowd": ["A", "B"]}
    monkeypatch.setattr(director, "_bodies_addressed_as",
                        lambda ctx, sc, speaker, forms: named.get(forms[0], []))
    decl = {"name": "Kenend Anvilforder",
            "dialogue_log_entry": {"exact_quote": "Aye.", "intended_target": "the short"},
            "sequence": [{"type": "speech", "text": "Aye.",
                          "targets": ["the short", "the crowd", "the anvil"]}],
            "charter_act": {"act": "greet", "other": "the short"}}
    director._name_voice_targets(None, {}, decl)
    assert decl["dialogue_log_entry"]["intended_target"] == "Emory Vane"
    assert decl["sequence"][0]["targets"] == ["Emory Vane", "the crowd", "the anvil"]
    assert decl["charter_act"]["other"] == "Emory Vane"


def test_an_act_no_tool_records_is_still_an_event():
    """Chat 126 replay (2026-09-23) idx 5: the player's blush was folded into
    the speech event as a `conditions` transform ("awareness: dazed") that
    alignment dropped, and no row carried it -- the woman beside her could
    not see it. The overlays chunk said a brief reaction rides the row's
    observable; the encoder, never granted overlays, never read it."""
    from llm import prompts
    en = prompts.unified_specialist_prompt(["poses"])
    ja = prompts.unified_specialist_prompt(["poses"], "ja")
    assert "whether or not a tool records it -- minds perceive events, never transforms" in en
    assert "no tool owns it" in en and "no tool asked for" in en
    assert "心が知覚するのは event であって transform ではありません" in ja
    assert "それを持つ tool もありません" in ja


def test_volume_is_the_speakers_and_muffling_is_the_worlds():
    """Chat 137 replay (2026-09-23) idx 46: "her voice muffled by the
    surrounding flesh" was encoded as the player's volume `mutter`; the line
    then reached nobody, and the body she was inside was never asked."""
    from llm import prompts
    en = prompts.unified_specialist_prompt(["poses"])
    ja = prompts.unified_specialist_prompt(["poses"], "ja")
    assert "whatever muffles or carries it afterward is the world's" in en
    assert "その後で音をくぐもらせたり運んだりするものは世界の側のもの" in ja


def test_a_place_the_world_holds_is_already_designed():
    """Chat 153 and 137 replays (2026-09-23): the designer redrafted rooms the
    world already held whenever the router granted `rooms` -- the TARDIS
    console room at both stages (40.5 s + 50.6 s) and Mirelle's throat on four
    beats, one rewrite setting it `quiet: dead` and deafening her to the body
    inside it."""
    from llm import prompts
    en = prompts.room_author_prompt()
    ja = prompts.room_author_prompt("ja")
    assert "It is already designed, and the prose describing it" in en
    assert "submit at once with nothing drafted" in en
    assert "それは既に設計されており" in ja
    assert "何も draft せずにすぐ submit してください" in ja


def test_an_answer_without_prose_goes_to_the_repair_ladder():
    """Chat 126 replay, round 4 (NanoGPT z-ai/glm-5.2:thinking, 2026-09-23):
    the author answered `{}`, which validated because `prose` had a default,
    and the beat died on "returned no prose" instead of being asked again.
    The repair it goes to now is shown the real shape, not `{}`."""
    from llm.schemas import output_example, validate_llm_output_strict
    assert not validate_llm_output_strict("director_prose", {}).valid
    assert not validate_llm_output_strict("director_prose", {"prose": ""}).valid
    # Round 5, chat 137 idx 46: the whole prose was "," -- no account.
    assert not validate_llm_output_strict("director_prose", {"prose": ","}).valid
    assert not validate_llm_output_strict("director_prose", {"prose": " -- . "}).valid
    assert validate_llm_output_strict("director_prose", {"prose": "Mara climbs."}).valid
    assert validate_llm_output_strict("director_prose", {"prose": "ミラが登る。"}).valid
    example = output_example("director_prose")
    assert example["prose"] and validate_llm_output_strict("director_prose", example).valid


def test_a_places_text_never_describes_who_is_in_it():
    """Chat 153 replay (2026-09-23) idx 23: the designer's redraft of the
    console room wrote "Hinami stands here, six golden tails flared" into the
    doorway's anchor -- her own view then narrated her -- and "Gushiga
    Toriki's cuff garment and trousers" into the console's, carrying a
    storekeeper's name to a man who never learned it. Both tripped the
    composer; both are text that is wrong the moment anyone moves."""
    from llm import prompts
    en = prompts.room_author_prompt()
    ja = prompts.room_author_prompt("ja")
    assert "a place's text describe a person, what one is doing, or whose anything is" in en
    assert "場所の文も、人物や、その人がしていること、何かが誰のものかを描いてはいけません" in ja
