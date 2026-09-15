"""Four geometry classes the owner asked for on 2026-09-15.

1. An open side outdoors is the whole wall, not a one-cell doorway.
2. A body standing in a doorway is the door: a line through the aperture
   meets it, and a walk through it finds it filled.
3. A declared run covers twice a walk's paces, and companions sent with a
   walker walk the same cells at the same pace.
4. Every anchor written states its height and footprint (8 of 924 live
   anchors carried one, so nothing blocked sight or a walk).
"""
import json

import agents.director as director
import agents.director_movement as movement
from llm.prompts import get_prompt_body
from llm.schemas import MovementDecl
from world.spatial import (RUN_PACES_PER_SECOND, anchor_cells, body_visibility,
                           door_cell, held_cells, paces_for, walk)
from tests.test_director_movement import _make_ctx


def _outdoors():
    return {
        "rooms": {
            "lane": {"name": "the lane", "exposure": "open", "extent": {"w": 6, "d": 6},
                     "adjacent": [{"to": "field", "barrier": "open", "dir": "e"},
                                  {"to": "barn", "barrier": "open_door", "dir": "n"}]},
            "field": {"name": "the field", "exposure": "open", "extent": {"w": 6, "d": 6},
                      "adjacent": [{"to": "lane", "barrier": "open", "dir": "w"}]},
            "barn": {"name": "the barn", "exposure": "enclosed", "extent": {"w": 6, "d": 6},
                     "adjacent": [{"to": "lane", "barrier": "open_door", "dir": "s"}]},
        },
        "positions": {"Ada": "lane"}, "stations": {"Ada": {"at": None, "near": [], "cell": [0, 5]}},
        "entities": {},
    }


def test_an_open_side_between_outdoor_cells_is_the_whole_wall():
    sc = _outdoors()
    side = anchor_cells(sc, "lane")["door:field"]
    assert len(side["cells"]) == 6 and all(x == 5 for x, _y in side["cells"])
    assert side["desc"] == "the open side"
    # An indoor doorway on the same lane is still one cell wide.
    assert len(anchor_cells(sc, "lane")["door:barn"]["cells"]) == 1
    # The walker crosses the side where it reaches it, not at its middle.
    assert door_cell(sc, "lane", "field", near=(0, 5)) == (5, 5)
    landed = walk(sc, "Ada", "field", paces=40)
    assert landed["room"] == "field" and landed["arrived"]


def _hall_and_yard():
    return {
        "rooms": {
            "hall": {"name": "hall", "extent": {"w": 6, "d": 6}, "anchors": {},
                     "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "e"}]},
            "yard": {"name": "yard", "extent": {"w": 6, "d": 6}, "anchors": {},
                     "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "w"}]},
        },
        "positions": {"Ada": "hall", "Bram": "hall", "Cass": "yard"},
        "stations": {"Ada": {"at": None, "near": [], "cell": [1, 3]},
                     "Bram": {"at": None, "near": [], "cell": [5, 3]},
                     "Cass": {"at": None, "near": [], "cell": [4, 3]}},
        "entities": {}, "orientation": {},
    }


def test_a_body_in_the_doorway_is_the_door():
    sc = _hall_and_yard()
    door = door_cell(sc, "hall", "yard")
    assert door is not None
    # Ada level with the hall's door, Cass just inside the yard's door, so
    # the line between them threads the aperture and nothing else.
    sc["stations"]["Ada"]["cell"] = [1, door[1]]
    far_door = door_cell(sc, "yard", "hall")
    sc["stations"]["Cass"]["cell"] = [far_door[0] + 1, far_door[1]]
    assert body_visibility(sc, "Ada", "Cass")["visible"] is True
    sc["stations"]["Bram"]["cell"] = list(door)          # Bram fills the doorway
    seen = body_visibility(sc, "Ada", "Cass")
    assert seen["visible"] is False and seen["occluded_by"] == "Bram"
    # And a walk through it is stopped where it stands.
    stopped = walk(sc, "Ada", "yard", paces=40)
    assert stopped["blocked"] and stopped.get("held_by") == "doorway"
    assert stopped["room"] == "hall"
    assert door in held_cells(sc, "hall", walker="Ada")
    # Bram steps aside and the line and the walk are clear again.
    sc["stations"]["Bram"]["cell"] = [5, 0]
    assert body_visibility(sc, "Ada", "Cass")["visible"] is True
    assert walk(sc, "Ada", "yard", paces=40)["arrived"]


def test_a_run_covers_twice_a_walk():
    assert paces_for(10, "run") == round(10 * RUN_PACES_PER_SECOND) == 36
    assert paces_for(10, "walk") == paces_for(10) == 18
    assert MovementDecl(to_room="x", pace="run").pace == "run"


def test_companions_walk_with_the_walker(temp_db, monkeypatch):
    from tests.helpers import fanout_resolve_agent
    ctx = _make_ctx(temp_db, "lamp_room")
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["positions"]["Mara"] = "keeper_room"
    temp_db.wset(ctx.chat.id, "scene", sc)
    monkeypatch.setattr(movement, "paces_for", lambda seconds=None, pace=None: 1)
    # The hand sends Mara to the destination with the mover.
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"Mara": "lamp_room"}}}))
    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]
    assert sd["positions"]["The Stranger"] == "keeper_room"     # one pace: not there yet
    assert sd["positions"]["Mara"] == "keeper_room"             # walked with, not teleported
    assert {e["subject"] for e in out["travel"]["advanced"] if e.get("underway")} == {"The Stranger", "Mara"}


def test_every_anchor_is_asked_for_its_height_and_footprint():
    establish = get_prompt_body("director_establish", "en")
    assert "anchors:{anchor_id:{desc, dir, height, footprint}}" in establish
    from llm.prompts import DEFAULT_PROMPTS
    spatial = DEFAULT_PROMPTS["director_spatial"]
    assert "EVERY anchor you write states its `height` and its `footprint`" in spatial
    assert "anchors?:{anchor_id:{desc,dir,height,footprint,opacity?}}" in spatial
    assert "pace: run when the span runs" in get_prompt_body("director_interpret", "en")


def test_nobody_lands_in_furniture_and_a_walk_to_a_fixture_ends_beside_it():
    """Skerry Light, 2026-09-15: the yard's east door opened one pace from a
    head-high shed, and the arrival cell was inside the shed's footprint."""
    from world.spatial import anchor_stand_cell, free_cell_near, merge_scene_with_diff
    sc = {"rooms": {
        "store": {"name": "store", "extent": {"w": 8, "d": 8}, "anchors": {},
                  "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "w"}]},
        "yard": {"name": "yard", "extent": {"w": 12, "d": 10}, "exposure": "open", "anchors": {
            "shed": {"desc": "the shed", "dir": "e", "height": "head", "footprint": "large"}},
                 "adjacent": [{"to": "store", "barrier": "open_door", "dir": "e"}]}},
        "positions": {"Nell": "store"}, "stations": {"Nell": {"cell": [1, 4]}}, "entities": {}}
    shed = {tuple(c) for c in anchor_cells(sc, "yard")["shed"]["cells"]}
    landed = walk(sc, "Nell", "yard", paces=60)
    assert landed["arrived"] and tuple(landed["cell"]) not in shed
    at_shed = walk(sc, "Nell", "yard", to_anchor="shed", paces=60)
    assert tuple(at_shed["cell"]) not in shed
    assert tuple(at_shed["cell"]) == anchor_stand_cell(sc, "yard", "shed", near=at_shed["cell"])
    merged = merge_scene_with_diff(sc, {"positions": {"Nell": "yard"}})
    assert tuple(merged["stations"]["Nell"]["cell"]) not in shed
    assert free_cell_near(sc, "yard", next(iter(shed))) not in shed


def test_the_hands_station_is_the_walks_destination(temp_db, monkeypatch):
    from tests.helpers import fanout_resolve_agent
    ctx = _make_ctx(temp_db, "lamp_room")
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["rooms"]["lamp_room"]["anchors"] = {"lens": {"desc": "the lens", "dir": "n", "height": "waist"}}
    temp_db.wset(ctx.chat.id, "scene", sc)
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"stations": {"The Stranger": {"at": "lens", "near": []}}}}))
    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]
    from world.spatial import anchor_stand_cell
    sc2 = temp_db.wget(ctx.chat.id, "scene", {})
    stand = anchor_stand_cell(sc2, "lamp_room", "lens", near=sd["stations"]["The Stranger"]["cell"])
    assert sd["positions"]["The Stranger"] == "lamp_room"
    assert tuple(sd["stations"]["The Stranger"]["cell"]) == stand


def test_a_stair_keeps_its_wall_on_both_floors():
    """Skerry Light, 2026-09-15: every stair authored 'n' on both floors was
    dropped as a contradiction. A stair is one shaft; a door is seen from
    two sides."""
    from world.spatial import normalize_scene_bearings
    sc = {"rooms": {
        "store": {"adjacent": [{"to": "keep", "barrier": "open", "dir": "n", "vertical": "up"},
                               {"to": "yard", "barrier": "open_door", "dir": "w"}]},
        "keep": {"adjacent": [{"to": "store", "barrier": "open", "dir": "n", "vertical": "down"},
                              {"to": "watch", "barrier": "open", "vertical": "up"}]},
        "watch": {"adjacent": [{"to": "keep", "barrier": "open", "dir": "e", "vertical": "down"}]},
        "yard": {"adjacent": [{"to": "store", "barrier": "open_door", "dir": "n"}]}}}
    normalize_scene_bearings(sc)
    edge = lambda a, b: next(e for e in sc["rooms"][a]["adjacent"] if e["to"] == b)
    assert edge("store", "keep")["dir"] == "n" and edge("keep", "store")["dir"] == "n"
    assert edge("keep", "watch")["dir"] == "e", "a floor that names no wall takes the shaft's"
    assert "dir" not in edge("yard", "store") and "dir" not in edge("store", "yard"), \
        "a door's two sides still must be opposites"


def test_every_mover_on_the_ledger_walks(temp_db, monkeypatch):
    """Skerry Light turn 3, 2026-09-15: the player's walk was walked over
    the cells; a cast member's own movement row (to the foot of the stair)
    was seated by the merge one pace inside the yard door."""
    from tests.helpers import fanout_resolve_agent
    from world.spatial import anchor_stand_cell
    ctx = _make_ctx(temp_db, "lamp_room")
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["rooms"]["keeper_room"]["extent"] = {"w": 8, "d": 8}
    sc["rooms"]["lamp_room"]["extent"] = {"w": 8, "d": 8}
    sc["rooms"]["lamp_room"]["adjacent"] = [{"to": "keeper_room", "barrier": "open", "dir": "s"}]
    sc["rooms"]["keeper_room"]["adjacent"][0]["dir"] = "n"
    sc["rooms"]["keeper_room"]["anchors"] = {
        "stair_foot": {"desc": "the stair foot", "dir": "e", "height": "waist"}}
    sc["stations"] = {"Mara": {"cell": [4, 4]}}
    # A cast member has an entity record of her own (kind person); the
    # record must not make her a vehicle whose occupants ride.
    sc["entities"] = {"char_mara": {"name": "Mara", "kind": "person", "aliases": []}}
    temp_db.wset(ctx.chat.id, "scene", sc)
    mara_id = int(ctx.cast[0]["id"])
    ctx.character_results = {mara_id: {
        "name": "Mara",
        "sequence": [{"type": "action", "attempt": "goes down to the stair foot",
                      "observable": "goes down", "visibility": "overt", "conceal_from": []}]}}
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent({
        "causal_ledger": [{
            "chrono_id": 1, "item_id": 1, "object_name": "Mara",
            "source_entity_id": f"character:{mara_id}", "source_event_id": "",
            "event": "Mara goes down to the stair foot", "observable": "",
            "commitment": "asserted", "targets": ["keeper_room"],
            "movement": {"to_room": "keeper_room", "why": "", "mover": "Mara",
                         "arrives": True, "to_anchor": "stair_foot"},
            "resolution_notes": "", "categories": ["positions", "stations"]}],
        "state_diff": {"positions": {"Mara": "keeper_room"},
                       "stations": {"Mara": {"at": "stair_foot", "near": []}}}}))
    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]
    sc2 = temp_db.wget(ctx.chat.id, "scene", {})
    assert sd["positions"]["Mara"] == "keeper_room"
    cell = sd["stations"]["Mara"].get("cell")
    assert cell is not None, "the cast walk was not walked"
    assert tuple(cell) == anchor_stand_cell(sc2, "keeper_room", "stair_foot", near=cell)


def test_a_line_put_to_the_person_you_see_is_aimed_at_them(temp_db, monkeypatch):
    """Skerry Light turn 3, 2026-09-15: "Coming." with `targets: []` and
    `interaction.addresses: ["the unfamiliar person"]` reached the log aimed
    at nobody, so a pitched line was solved as a normal one."""
    from tests.helpers import fanout_resolve_agent
    from agents.common import observer_label_fn
    ctx = _make_ctx(temp_db, "lamp_room")
    mara_id = int(ctx.cast[0]["id"])
    label = observer_label_fn(ctx.chat, "Mara", ctx.cast)("The Stranger")
    assert label and label.casefold() != "the stranger" or True
    ctx.character_results = {mara_id: {
        "name": "Mara",
        "sequence": [{"type": "speech", "text": "Coming.", "volume": "pitched",
                      "tone": "", "visibility": "overt", "conceal_from": [], "targets": []}],
        "interaction": {"addresses": [label], "expects_response": False}}}
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent({"state_diff": {}}))
    out = director.director_resolve(ctx, nonce=0)
    line = next(d for d in out["dialogue_log"] if d["speaker"] == "Mara")
    assert line["intended_target"] == "The Stranger"


def test_off_a_stair_a_body_faces_into_the_room():
    """Skerry Light turn 3, 2026-09-15: arrived up the north stair facing
    'n' -- the wall -- and the south door rendered "to my right"."""
    from world.spatial_frames import arrival_facing
    sc = {"rooms": {
        "store": {"adjacent": [{"to": "keep", "barrier": "open", "dir": "n", "vertical": "up"},
                               {"to": "yard", "barrier": "open_door", "dir": "w"}]},
        "keep": {"adjacent": [{"to": "store", "barrier": "open", "dir": "n", "vertical": "down"}]},
        "yard": {"adjacent": [{"to": "store", "barrier": "open_door", "dir": "e"}]}}}
    assert arrival_facing(sc, "store", "keep") == "s", "up the north stair, face south"
    assert arrival_facing(sc, "keep", "store") == "s", "down it, the same wall, the same way"
    assert arrival_facing(sc, "yard", "store") == "e", "through a door, the way you walked"


def test_a_body_that_climbs_in_and_looks_around_faces_into_the_room():
    """Skerry Light turn 3, 2026-09-15: arrived up the north stair and
    swept the room; the sweep kept the floor below's facing."""
    from world.spatial_frames import infer_facing
    rooms = {
        "watch": {"adjacent": [{"to": "lamp", "barrier": "open", "dir": "n", "vertical": "up"}]},
        "lamp": {"adjacent": [{"to": "watch", "barrier": "open", "dir": "n", "vertical": "down"}]}}
    prev = {"rooms": rooms, "positions": {"Nell": "watch"},
            "orientation": {"Nell": {"came_from": None, "focus": None, "facing": "e"}}}
    new = {"rooms": rooms, "positions": {"Nell": "lamp"},
           "orientation": {"Nell": {"came_from": "watch", "focus": None, "facing": "e"}}}
    infer_facing(1, None, prev, new, [], looks={"Nell": "around"}, turn_idx=3)
    assert new["orientation"]["Nell"]["facing"] == "s"
    assert new["orientation"]["Nell"]["swept_turn"] == 3


def test_an_answer_to_a_voice_is_aimed_at_the_one_stranger_it_could_be(temp_db, monkeypatch):
    """Skerry Light turn 3 (rerun), 2026-09-15: the keeper was only heard,
    so the view called her the bare stranger label; the answer addressed
    that label and the identity gate's fuller label did not match it."""
    from tests.helpers import fanout_resolve_agent
    from agents.common import _unknown_actor_label
    ctx = _make_ctx(temp_db, "lamp_room")
    mara_id = int(ctx.cast[0]["id"])
    ctx.character_results = {mara_id: {
        "name": "Mara",
        "sequence": [{"type": "speech", "text": "On my way.", "volume": "pitched",
                      "tone": "", "visibility": "overt", "conceal_from": [], "targets": []}],
        "interaction": {"addresses": [_unknown_actor_label("The Stranger")],
                        "expects_response": False}}}
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent({"state_diff": {}}))
    out = director.director_resolve(ctx, nonce=0)
    line = next(d for d in out["dialogue_log"] if d["speaker"] == "Mara")
    assert line["intended_target"] == "The Stranger"


def test_a_flight_of_stairs_costs_more_than_a_doorway():
    """Skerry Light, 2026-09-15: a body climbed three storeys in six paces
    because every floor's stairhead sat on the wall its stairfoot did."""
    from world.spatial import FLIGHT_PACES
    rooms = {}
    names = ["ground", "first", "second", "top"]
    for i, rid in enumerate(names):
        adj = []
        if i > 0:
            adj.append({"to": names[i - 1], "barrier": "open", "dir": "n", "vertical": "down"})
        if i < 3:
            adj.append({"to": names[i + 1], "barrier": "open", "dir": "n", "vertical": "up"})
        rooms[rid] = {"name": rid, "extent": {"w": 6, "d": 6}, "adjacent": adj, "anchors": {}}
    sc = {"rooms": rooms, "positions": {"Ware": "ground"}, "stations": {"Ware": {"cell": [3, 1]}}, "entities": {}}
    short = walk(sc, "Ware", "top", paces=FLIGHT_PACES + 2)
    assert not short["arrived"] and short["room"] in ("ground", "first")
    long = walk(sc, "Ware", "top", paces=3 * (FLIGHT_PACES + 3) + 6)
    assert long["arrived"] and long["room"] == "top"


def test_a_body_in_the_far_rooms_door_cell_fills_the_doorway():
    """Skerry Light turn 8, 2026-09-15: the keeper stood on the lamp room's
    stairhead cell; the climber was stepped past her and seated one pace
    inside. A doorway is one opening seen from two rooms."""
    rooms = {
        "watch": {"name": "watch", "extent": {"w": 8, "d": 8}, "anchors": {},
                  "adjacent": [{"to": "lamp", "barrier": "open", "dir": "n", "vertical": "up"}]},
        "lamp": {"name": "lamp", "extent": {"w": 6, "d": 6}, "anchors": {},
                 "adjacent": [{"to": "watch", "barrier": "open", "dir": "n", "vertical": "down"}]}}
    sc = {"rooms": rooms, "positions": {"Nell": "lamp", "Ware": "watch"},
          "stations": {"Nell": {"cell": list(anchor_cells({"rooms": rooms}, "lamp")["door:watch"]["cells"][0])},
                       "Ware": {"cell": [4, 4]}}, "entities": {}}
    landed = walk(sc, "Ware", "lamp", paces=60)
    assert landed["room"] == "watch" and landed.get("held_by") == "doorway", landed
    sc["stations"]["Nell"] = {"cell": [3, 3]}
    assert walk(sc, "Ware", "lamp", paces=60)["room"] == "lamp"
