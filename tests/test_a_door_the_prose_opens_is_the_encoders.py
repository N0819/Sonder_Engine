"""A door's state is world state, and a granted channel is never dropped.

Measured on the owner's chat 177 (2026-10-19). Under the room author
(`prose_contract_room_agent`, on by default) every room channel was stripped
from the encoder whether or not the author ran -- and it runs only for a
place reserved or developed. At turn 19 the decision model granted `rooms`
at 0.74, nothing was reserved or entered, no author ran, and "Mellisande
shoves open the sticking door of the second room and enters" wrote no barrier
and raised no warning. At turn 20 the second room's design wrote the same
door `closed_door` again, and it stayed shut behind three bodies to the end.
Across chats 175-178 the encoder held `rooms` in none of 302 calls.

The rule: the encoder holds every room channel it is granted (and may ask for
one), with the core card's doorway paragraph -- never the room-building
chunk -- as its instructions under a room author; whatever of a held place it
writes beyond a doorway is dropped AND SAID; and no room design opens or
shuts a door the world holds.
"""

from __future__ import annotations

import copy

import agents.director as director
from agents import director_prose
from llm import decisions

from tests.director_fakes import BASE_SCENE, _action_interp, _fake_agent, _make_ctx


#: The room-building chunk's own heading (`encoder.rooms`).
ROOM_CHUNK = "ROOM CREATION"


def _doored_scene(barrier="closed_door"):
    """The base lighthouse with a door between the keeper's room and the
    lamp room, standing `barrier` on both sides."""
    scene = copy.deepcopy(BASE_SCENE)
    scene["rooms"]["keeper_room"]["adjacent"] = [{"to": "lamp_room", "barrier": barrier}]
    scene["rooms"]["lamp_room"]["adjacent"] = [{"to": "keeper_room", "barrier": barrier}]
    return scene


def _granting(granted):
    def answer(state, questions):
        return {key: {"type": "noul", "noul": 0.95 if key in granted else 0.02}
                for key in questions}
    return answer


def _obedient_encoder(payload):
    """An encoder that writes the door only with the tool for it in hand --
    the measured behaviour: across chats 175-178 it wrote a doorway in 5 of
    145 beats, never once holding `rooms` -- and otherwise asks for it."""
    door = {"item": "lamp-room door", "patch": {"rooms": {"keeper_room": {
        "adjacent": [{"to": "lamp_room", "barrier": "open_door"}]}}}}
    held = "rooms" in (payload.get("granted_tools") or [])
    return {"events": [{
        "source_entity_id": "character:1", "source_event_id": "x",
        "event": "Mara shoves the lamp-room door open.",
        "observable": "shoves the lamp-room door open", "speech": False,
        "targets": ["lamp_room"], "seconds": 3, "movement": None,
        "commitment": "asserted", "item_names": ["lamp-room door"],
        "transforms": [door] if held else []}],
        "missing_tools": [] if held else ["rooms"],
        "missing_referents": [], "notes": []}


def _run(temp_db, monkeypatch, granted, scene=None):
    temp_db.set_setting("prose_contract_repair", "0")
    monkeypatch.setattr(decisions, "OVERRIDE", _granting(granted))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara shoves the lamp-room door open."},
        "director_specialist": _obedient_encoder,
    }))
    ctx = _make_ctx(temp_db, scene=scene or _doored_scene(), interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    return out, calls, ctx


def _barrier(out, room, to):
    for edge in ((out["state_diff"].get("rooms") or {}).get(room) or {}).get("adjacent") or []:
        if edge.get("to") == to:
            return edge.get("barrier")
    return None


def test_a_granted_door_reaches_the_encoder_when_no_author_runs(temp_db, monkeypatch):
    """Chat 177 turn 19's shape: `rooms` granted, a door in a held place
    opened, nothing reserved or developed, so no room author runs."""
    out, calls, _ctx = _run(temp_db, monkeypatch, {"rooms", "positions"})
    encoder = [c for c in calls if c["step_key"] == "director_specialist"]
    assert "director_rooms" not in [c["step_key"] for c in calls]
    assert "rooms" in encoder[0]["payload"]["granted_tools"]
    # ...told what of it is its own -- a doorway -- and not handed the
    # room-building sheet, which is the author's.
    assert encoder[0]["payload"]["places_authored_elsewhere"] is True
    assert "write that edge alone" in encoder[0]["system"]
    assert ROOM_CHUNK not in encoder[0]["system"]
    assert _barrier(out, "keeper_room", "lamp_room") == "open_door"


def test_a_door_the_grant_missed_can_be_asked_for(temp_db, monkeypatch):
    """`rooms` not granted: the encoder names it missing, and the widening
    grants it -- it used to be neither held nor requestable."""
    out, calls, _ctx = _run(temp_db, monkeypatch, {"positions"})
    encoder = [c for c in calls if c["step_key"] == "director_specialist"]
    assert "rooms" in encoder[0]["payload"]["requestable_tools"]
    assert len(encoder) == 2
    assert "rooms" in encoder[1]["payload"]["granted_tools"]
    assert ROOM_CHUNK not in encoder[1]["system"]
    assert _barrier(out, "keeper_room", "lamp_room") == "open_door"


def test_what_the_encoder_writes_of_a_held_place_beyond_a_door_is_said():
    """Chat 175 turn 6: `lane_end: {light: dim}` vanished without a word."""
    scene = {"rooms": {"parlour": {"adjacent": [{"to": "hall"}]}, "hall": {}}}
    events = [{"event": "The parlour dims.", "transforms": [
        {"item": "parlour", "patch": {"rooms": {"parlour": {
            "light": "dim",
            "adjacent": [{"to": "hall", "barrier": "closed_door"},
                         {"to": "nowhere", "barrier": "open"}]}}}}]}]
    warned = []
    out = director_prose.doorway_edits_only(events, scene, warn=warned.append)
    assert out[0]["transforms"] == [{"item": "parlour", "patch": {"rooms": {
        "parlour": {"adjacent": [{"to": "hall", "barrier": "closed_door"}]}}}}]
    assert len(warned) == 1
    assert "light" in warned[0] and "'nowhere'" in warned[0]


def test_a_room_design_never_opens_or_shuts_a_held_door():
    """What a doorway IS stays the design's; whether a door in it stands
    open or shut, or fastened, is the world's."""
    scene = {"rooms": {
        "landing": {"adjacent": [{"to": "spare_room", "barrier": "open_door"},
                                 {"to": "bedchamber", "barrier": "locked_door"},
                                 {"to": "stair", "barrier": "closed_door"}]},
        "spare_room": {}, "bedchamber": {}, "stair": {}}}
    design = {"rooms": {
        # Chat 177 turn 20: the developed room re-installed `closed_door`.
        "spare_room": {"name": "The Second Room", "adjacent": [
            {"to": "landing", "barrier": "closed_door", "name": "the second room's door",
             "material": "wood"}]},
        "landing": {"adjacent": [
            # A held door keeps the world's word, whatever word the design uses.
            {"to": "bedchamber", "barrier": "closed_door"},
            # An opening where a door stood is what the doorway IS: kept.
            {"to": "stair", "barrier": "open"},
            # A doorway to a place being built has no standing state.
            {"to": "new_attic", "barrier": "closed_door"}]}}}
    warned = []
    out = director_prose.doors_keep_their_state(design, scene, warn=warned.append)
    spare = out["rooms"]["spare_room"]["adjacent"][0]
    assert "barrier" not in spare
    assert spare["name"] == "the second room's door" and spare["material"] == "wood"
    landing = {e["to"]: e for e in out["rooms"]["landing"]["adjacent"]}
    assert "barrier" not in landing["bedchamber"]
    assert landing["stair"]["barrier"] == "open"
    assert landing["new_attic"]["barrier"] == "closed_door"
    assert len(warned) == 2
    # Merged onto the world, the doors stand as they stood -- as the same
    # world merged with nothing stands them.
    from world.spatial import merge_scene_with_diff
    merged = merge_scene_with_diff(copy.deepcopy(scene), {"rooms": out["rooms"]})
    still = merge_scene_with_diff(copy.deepcopy(scene), {})
    by_to = {e["to"]: e["barrier"] for e in merged["rooms"]["landing"]["adjacent"]}
    was = {e["to"]: e["barrier"] for e in still["rooms"]["landing"]["adjacent"]}
    assert by_to["spare_room"] == "open_door" == was["spare_room"]
    assert by_to["bedchamber"] == was["bedchamber"]
    assert by_to["stair"] == "open"


def test_a_prepared_design_installs_without_shutting_a_held_door(temp_db, monkeypatch):
    """The between-turns design is built into the scene the beat opens on;
    its door keeps the state the world holds."""
    from agents import director_rooms
    scene = {"rooms": {
        "landing": {"name": "Landing", "adjacent": [
            {"to": "spare_room", "barrier": "open_door"}]},
        "spare_room": {"name": "spare room", "planned": True, "adjacent": [
            {"to": "landing", "barrier": "open_door"}]}},
        "positions": {"Mara": "landing"}}
    design = {"spare_room": {"name": "The Second Room", "desc": "Cold.", "adjacent": [
        {"to": "landing", "barrier": "closed_door", "name": "the door"}]}}
    monkeypatch.setattr(director_rooms, "predevelopment_enabled", lambda: True)
    monkeypatch.setattr(director_rooms, "rooms_to_build", lambda *a, **k: ["spare_room"])
    monkeypatch.setattr(director_rooms, "_install_test",
                        lambda scene, cache, targets, briefs: (copy.deepcopy(design), {}))
    monkeypatch.setattr("world.structure.planned_room_brief", lambda *a, **k: {})
    chat_id = _make_ctx(temp_db).chat.id
    temp_db.wset(chat_id, director_rooms.PREPARED_KEY,
                 {"spare_room": {"room": design["spare_room"]}})
    built, installed = director_rooms.install_prepared_rooms(chat_id, scene, body="Mara")
    assert installed and "barrier" not in installed["spare_room"]["adjacent"][0]
    edge = built["rooms"]["spare_room"]["adjacent"][0]
    assert edge["barrier"] == "open_door" and edge["name"] == "the door"


def test_the_core_says_a_doorway_is_the_encoders_granted_or_not():
    from llm.prompts import unified_specialist_prompt
    en = unified_specialist_prompt([], "en", [])
    ja = unified_specialist_prompt([], "ja", [])
    assert "the one thing of it that is yours, rooms granted or not, is a doorway" in en
    assert "rooms が付与されていてもいなくても" in ja


def test_the_check_does_not_judge_a_doorway_by_the_building_chunk(monkeypatch):
    """Held under a room author, `rooms` is a doorway; the repair's checks ask
    by the sheet's own definitions, and the room-building chunk's opening
    ("ROOM CREATION: if anyone moves to a room that does not yet exist...")
    is not its rule -- asked by it, every event of a beat with a door in it
    would be judged for a room it never had to build."""
    from agents import director_repair as repair
    asked = []

    def answer(state, questions):
        asked.extend(questions)
        return {key: {"type": "noul", "noul": 0.02} for key in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", answer)

    class Ctx(dict):
        language = "en"
        warnings = []

        def add_warning(self, text):
            self.warnings.append(text)

    units = repair.sentences("Mara shoves the lamp-room door open.")
    draft = [{"source_entity_id": "character:1", "source_event_id": "x",
              "event": "Mara shoves the lamp-room door open.", "speech": False,
              "item_names": ["door"], "transforms": [{"item": "door", "patch": {"rooms": {
                  "keeper_room": {"adjacent": [{"to": "lamp_room", "barrier": "open_door"}]}}}}]}]
    payload = {"identity_index": {"character:1": "Mara"}, "event_inputs": []}
    repair.check_and_repair(Ctx(), "resolve", {}, units, draft, ["rooms", "poses"], [],
                            {}, None, None, rooms_elsewhere=True, base_payload=payload)
    assert asked and not [key for key in asked if key.endswith(":rooms")]
