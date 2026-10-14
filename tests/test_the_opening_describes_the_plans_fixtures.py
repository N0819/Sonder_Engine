"""The opening describes a laid-out room's fixtures; it never makes them again.

Home 11 (chat 174, reviewed 2026-10-13): the opening was handed the plan's
rooms with no word of what stood in them, so it furnished the shrine's
rooms afresh -- a second nest of futons beside the plan's `futon_nest`,
closets and shelves under new ids -- and each copy, placed by its seed,
stood in the plan's own furniture; Tamamo, stationed at the copy, stood in
a stack of boxes. The opening's brief now carries each laid-out room's
storey and standing fixtures (`structure.planned_room_brief(fixtures=True)`),
and its own output is held to the plan (`structure.hold_planned_fixtures`).
Hand-made plans; the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy

from world.structure import hold_planned_fixtures, planned_fixture_brief

SITE = {"plan": "layout:shrine", "x": 0, "y": 0, "elev_m": 0.0}
PLAN_ANCHORS = {
    "futon_nest": {"desc": "a nest of futons", "cell": [0, 0], "extent": {"w": 2, "d": 2},
                   "dir": "w", "footprint": "large", "height": "floor"},
    "writing_boxes": {"desc": "stacked writing boxes", "cell": [5, 0], "extent": {"w": 1, "d": 3},
                      "dir": "e", "footprint": "run", "height": "waist"},
}


def _spec(**extra):
    spec = {"purpose": "a sleeping room", "site": dict(SITE), "level": 2,
            "extent": {"w": 6, "d": 5}, "anchors": copy.deepcopy(PLAN_ANCHORS)}
    spec.update(extra)
    return spec


def _scene():
    room = {"name": "the Roost", "planned": True, "site": dict(SITE), "level": 2,
            "extent": {"w": 6, "d": 5}, "exposure": "enclosed",
            "anchors": copy.deepcopy(PLAN_ANCHORS), "adjacent": []}
    return {"rooms": {"roost": room}, "positions": {}, "stations": {}, "entities": {}}


def test_the_opening_is_told_a_laid_out_rooms_storey_and_its_fixtures():
    brief = planned_fixture_brief(_spec())
    assert brief["level"] == 2
    assert brief["anchors"]["futon_nest"] == {
        "desc": "a nest of futons", "dir": "w", "cell": [0, 0], "extent": {"w": 2, "d": 2},
        "height": "floor"}
    # a room no solve laid out is told nothing more, so every other brief
    # stays what it was
    assert planned_fixture_brief(_spec(site=None)) == {}


def test_the_brief_keeps_its_old_shape_unless_the_opening_asks(temp_db, monkeypatch):
    from world import structure
    monkeypatch.setattr(structure, "_planned_specs",
                        lambda cid: {"roost": ("the Roost", _spec())})
    plain = structure.planned_room_brief(1, {}, ["roost"])
    assert "anchors" not in plain["roost"] and "level" not in plain["roost"]
    opened = structure.planned_room_brief(1, {}, ["roost"], fixtures=True)
    assert opened["roost"]["level"] == 2 and set(opened["roost"]["anchors"]) == set(PLAN_ANCHORS)
    assert {k: v for k, v in opened["roost"].items() if k not in ("anchors", "level")} == plain["roost"]


def test_a_plan_fixture_spelled_another_way_is_written_under_the_plans_id():
    out = {
        "rooms": {"roost": {"desc": "Her roost.", "anchors": {
            "Futon Nest": {"desc": "a heap of silk futons", "dir": "n", "height": "waist"}}}},
        "positions": {"Tamamo": "roost"},
        "stations": {"Tamamo": {"at": "Futon Nest", "near": []}},
        "poses": {"Tamamo": {"posture": "lying", "support": "Futon Nest"}},
        "contact_ops": [{"op": "add", "actor": "Tamamo", "target": "Futon Nest",
                         "manner": "rest", "relation": "surface", "motion": "settled"}],
    }
    warnings = hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    anchors = out["rooms"]["roost"]["anchors"]
    assert set(anchors) == {"futon_nest"}
    assert anchors["futon_nest"]["desc"] == "a heap of silk futons"
    assert anchors["futon_nest"]["height"] == "waist", "its height is the describing hand's"
    assert "dir" not in anchors["futon_nest"], "its wall is the plan's"
    assert out["stations"]["Tamamo"]["at"] == "futon_nest"
    assert out["poses"]["Tamamo"]["support"] == "futon_nest"
    assert out["contact_ops"][0]["target"] == "futon_nest"
    assert any("'Futon Nest' is the plan's 'futon_nest'" in w for w in warnings)


def test_the_plans_place_stands_against_the_describing_write():
    from world.spatial import anchor_cells, merge_scene_with_diff
    out = {"rooms": {"roost": {"desc": "Her roost.", "anchors": {
        "writing_boxes": {"desc": "lacquered boxes of letters", "cell": [2, 2],
                          "extent": {"w": 2, "d": 1}, "dir": "s", "footprint": "small"}}}}}
    hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    assert out["rooms"]["roost"]["anchors"]["writing_boxes"] == {"desc": "lacquered boxes of letters"}
    merged = merge_scene_with_diff(_scene(), {"rooms": out["rooms"]})
    rec = anchor_cells(merged, "roost")["writing_boxes"]
    assert rec["cells"] == [(5, 0), (5, 1), (5, 2)] and rec["desc"] == "lacquered boxes of letters"


def test_a_new_fixture_in_a_laid_out_room_is_stood_clear_and_pinned():
    """No designer follows the opening into a room it describes, so the
    place the packer finds is written, kept or moved: the read-time seed
    never chooses it again."""
    from world.spatial import anchor_cells, merge_scene_with_diff
    for i in range(30):
        aid = f"chest_{i}"
        out = {"rooms": {"roost": {"desc": "Her roost.", "anchors": {
            aid: {"desc": "a chest", "dir": "w", "footprint": "small", "height": "waist"}}}}}
        warnings = hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
        written = out["rooms"]["roost"]["anchors"][aid]
        assert "offset" in written or "cell" in written, (aid, written)
        merged = merge_scene_with_diff(_scene(), {"rooms": out["rooms"]})
        placed = anchor_cells(merged, "roost")
        mine = set(placed[aid]["cells"])
        assert not mine & set(placed["futon_nest"]["cells"]), (aid, mine)
        assert not warnings


def test_a_room_no_solve_laid_out_is_left_as_the_director_wrote_it():
    out = {"rooms": {"roost": {"desc": "Her roost.", "anchors": {
        "Futon Nest": {"desc": "a heap of silk futons", "dir": "n"}}}},
        "stations": {"Tamamo": {"at": "Futon Nest"}}, "positions": {"Tamamo": "roost"}}
    before = copy.deepcopy(out)
    assert hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec(site=None))}) == []
    assert out == before
    assert hold_planned_fixtures(_scene(), out, {}) == [] and out == before


def test_the_opening_is_handed_the_fixtures_and_its_own_answer_is_held_to_them(temp_db, monkeypatch):
    """Through the establish itself, its model scripted: the payload's
    `planned_rooms` carries the roost's storey and fixtures, and the diff
    the commit merges holds the plan's id where the model re-spelled it --
    the body's station with it."""
    import json
    import time

    import agents.director as director
    from core.db import wset
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_persona_data
    from world import structure

    monkeypatch.setattr(structure, "_planned_specs", lambda cid: {"roost": ("the Roost", _spec())})
    monkeypatch.setattr(structure, "planned_room_ids", lambda cid: {"roost"})
    persona = default_persona_data("Nia")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Nia", json.dumps(persona), "{}", persona["identity"]["uid"]))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Shrine", persona_id, "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 0, "", time.time()))
    wset(chat_id, "scene", _scene())
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Shrine", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=0, player_input="",
                      created=time.time()),
        cast=[], input="")
    seen = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        seen["planned"] = payload.get("planned_rooms")
        return {"location": "the roost",
                "rooms": {"roost": {"name": "the Roost", "desc": "Her roost under the eaves.",
                                    "adjacent": [], "anchors": {
                                        "futon-nest": {"desc": "a heap of silk futons",
                                                       "dir": "n", "height": "waist"}}}},
                "entities": {}, "positions": {"Nia": "roost"},
                "stations": {"Nia": {"at": "futon-nest", "near": []}}, "attire": {}}

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    monkeypatch.setattr(director, "validate_llm_output", lambda step, value: (value, []))
    result = director.director_establish(ctx, nonce=0)
    assert seen["planned"]["roost"]["level"] == 2
    assert set(seen["planned"]["roost"]["anchors"]) == set(PLAN_ANCHORS)
    rooms = result["state_diff"]["rooms"]
    assert set(rooms["roost"]["anchors"]) == {"futon_nest"}
    assert "dir" not in rooms["roost"]["anchors"]["futon_nest"]
    assert result["state_diff"]["stations"]["Nia"]["at"] == "futon_nest"
    assert any("is the plan's 'futon_nest'" in w for w in ctx.warnings)



def test_a_laid_out_room_written_under_another_spelling_is_held_to_its_plan():
    """The opening's room keys are folded onto the plan's at commit; a room
    it spelled its own way skipped the hold entirely (review of
    2026-10-13)."""
    out = {"rooms": {"Roost": {"name": "the Roost", "desc": "Her roost.", "anchors": {
        "Futon Nest": {"desc": "a heap of silk futons"}}}},
        "positions": {"Tamamo": "Roost"},
        "stations": {"Tamamo": {"at": "Futon Nest"}}}
    hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    assert set(out["rooms"]["Roost"]["anchors"]) == {"futon_nest"}
    assert out["stations"]["Tamamo"]["at"] == "futon_nest"


def test_a_station_keyed_by_name_beside_a_position_keyed_by_id_is_folded_too():
    """The hold runs before positions are canonicalized: a body whose
    position the model keyed by an id kept its station on the old spelling,
    and the merge left it standing at nothing (review of 2026-10-13)."""
    out = {"rooms": {"roost": {"desc": "Her roost.", "anchors": {
        "Futon Nest": {"desc": "a heap of silk futons"}}}},
        "positions": {"character:player": "roost"},
        "stations": {"Nia": {"at": "Futon Nest"}},
        "poses": {"Nia": {"posture": "lying", "support": "Futon Nest"}}}
    hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    assert out["stations"]["Nia"]["at"] == "futon_nest"
    assert out["poses"]["Nia"]["support"] == "futon_nest"


def test_a_doorway_declared_from_the_room_beyond_is_kept_clear_by_the_opening():
    """The packing trial merged the laid-out room alone, so a doorway into it
    declared only from the far room's side was no doorway to it, and a new
    chest was pinned on its step (review of 2026-10-13)."""
    from world.spatial import (anchor_cells, doorway_clearance, effective_anchors,
                               merge_scene_with_diff, room_grid)
    scene = _scene()
    scene["rooms"]["yard"] = {"name": "the Yard", "desc": "A yard.", "adjacent": [], "level": 2}
    for i in range(60):
        aid = f"chest_{i}"
        out = {"rooms": {
            "roost": {"desc": "Her roost.", "anchors": {
                aid: {"desc": "a chest", "dir": "s", "footprint": "small", "height": "waist"}}},
            "yard": {"adjacent": [{"to": "roost", "barrier": "open_door", "dir": "n"}]}}}
        hold_planned_fixtures(copy.deepcopy(scene), out, {"roost": ("the Roost", _spec())})
        merged = merge_scene_with_diff(copy.deepcopy(scene), {"rooms": out["rooms"]})
        placed = anchor_cells(merged, "roost")
        assert placed.get("door:yard"), "the yard's way in is a doorway of the roost"
        clear = doorway_clearance(room_grid(merged, "roost"), effective_anchors(merged, "roost"), placed)
        assert not set(map(tuple, placed[aid]["cells"])) & set(map(tuple, clear)), aid



def test_a_respelled_room_is_packed_as_the_planned_room_it_is():
    """Packed under the diff's spelling, the room was a default grid with
    none of the plan's fixtures: a new chest was pinned on the futon nest
    (second review of 2026-10-13)."""
    from world.spatial import anchor_cells, merge_scene_with_diff
    for i in range(30):
        aid = f"chest_{i}"
        out = {"rooms": {"Roost": {"name": "the Roost", "desc": "Her roost.", "anchors": {
            aid: {"desc": "a chest", "dir": "w", "footprint": "small", "height": "waist"}}}}}
        hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
        merged = merge_scene_with_diff(_scene(), {"rooms": {"roost": out["rooms"]["Roost"]}})
        placed = anchor_cells(merged, "roost")
        assert not set(map(tuple, placed[aid]["cells"])) & set(map(tuple, placed["futon_nest"]["cells"])), aid


def test_a_body_whose_position_spells_the_room_another_way_is_folded_too():
    out = {"rooms": {"Roost": {"name": "the Roost", "desc": "Her roost.", "anchors": {
        "Futon Nest": {"desc": "a heap of silk futons"}}}},
        "positions": {"Tamamo": "roost"},
        "stations": {"Tamamo": {"at": "Futon Nest"}}}
    hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    assert out["stations"]["Tamamo"]["at"] == "futon_nest"


def test_the_room_free_fold_never_repoints_another_rooms_fixture():
    """A body placed nowhere the hold can find was given every laid-out
    room's folds -- one standing at the parlour's own 'Futon Nest' among
    them."""
    out = {"rooms": {"roost": {"desc": "Her roost.", "anchors": {
                         "Futon Nest": {"desc": "a heap of silk futons"}}},
                     "parlour": {"name": "the Parlour", "desc": "A parlour.", "anchors": {
                         "Futon Nest": {"desc": "a guest futon"}}}},
           "positions": {"character:guest": "parlour"},
           "stations": {"Guest": {"at": "Futon Nest"}}}
    hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    assert out["stations"]["Guest"]["at"] == "Futon Nest"


def test_two_planned_rooms_one_name_resolve_the_way_the_commit_folds():
    """The commit folds a mint onto the FIRST scene room sharing a spelling;
    the hold refused the spelling outright and held nothing."""
    scene = _scene()
    scene["rooms"]["roost_b"] = dict(scene["rooms"]["roost"])
    specs = {"roost": ("the Roost", _spec()), "roost_b": ("the Roost", _spec())}
    out = {"rooms": {"the_roost": {"name": "the Roost", "desc": "Her roost.", "anchors": {
        "Futon Nest": {"desc": "a heap of silk futons"}}}}}
    hold_planned_fixtures(scene, out, specs)
    assert set(out["rooms"]["the_roost"]["anchors"]) == {"futon_nest"}


def test_ground_the_solve_laid_reads_as_ground_everywhere_the_plan_is_drawn():
    from web.storey_plan import room_look
    scene = {"rooms": {"lawn": {"name": "the Lawn", "extent": {"w": 4, "d": 4}}},
             "positions": {}}
    look = room_look(scene, "lawn", {"layout": {"plan": "layout:x", "grounds": "open"}})
    assert look["ground"] is True
    # an outbuilding the solve laid is a roofed room, never ground (third
    # review of 2026-10-13)
    shed = room_look(scene, "lawn", {"layout": {"plan": "layout:x", "grounds": "outbuilding"}})
    assert shed["ground"] is False


def test_a_doorway_into_a_respelled_room_from_beyond_is_kept_clear():
    from world.spatial import (anchor_cells, doorway_clearance, effective_anchors,
                               merge_scene_with_diff, room_grid)
    scene = _scene()
    scene["rooms"]["yard"] = {"name": "the Yard", "desc": "A yard.", "adjacent": [], "level": 2}
    for i in range(40):
        aid = f"chest_{i}"
        out = {"rooms": {
            "Roost": {"name": "the Roost", "desc": "Her roost.", "anchors": {
                aid: {"desc": "a chest", "dir": "s", "footprint": "small", "height": "waist"}}},
            "yard": {"adjacent": [{"to": "Roost", "barrier": "open_door", "dir": "n"}]}}}
        hold_planned_fixtures(copy.deepcopy(scene), out, {"roost": ("the Roost", _spec())})
        room = copy.deepcopy(out["rooms"]["Roost"])
        yard = copy.deepcopy(out["rooms"]["yard"])
        yard["adjacent"][0]["to"] = "roost"
        merged = merge_scene_with_diff(copy.deepcopy(scene), {"rooms": {"roost": room, "yard": yard}})
        placed = anchor_cells(merged, "roost")
        clear = doorway_clearance(room_grid(merged, "roost"), effective_anchors(merged, "roost"), placed)
        assert not set(map(tuple, placed[aid]["cells"])) & set(map(tuple, clear)), aid


def test_an_op_naming_another_rooms_own_fixture_is_left_alone():
    out = {"rooms": {"roost": {"desc": "Her roost.", "anchors": {
                         "Futon Nest": {"desc": "a heap of silk futons"}}},
                     "parlour": {"name": "the Parlour", "desc": "A parlour.", "anchors": {
                         "Futon Nest": {"desc": "a guest futon"}}}},
           "contact_ops": [{"op": "add", "actor": "Guest", "target": "Futon Nest", "manner": "rest",
                            "relation": "surface", "motion": "settled"}]}
    hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    assert out["contact_ops"][0]["target"] == "Futon Nest"


def test_a_rooms_name_never_captures_another_held_rooms_bodies():
    scene = _scene()
    scene["rooms"]["den"] = dict(scene["rooms"]["roost"], name="the Den")
    specs = {"roost": ("the Roost", _spec()), "den": ("the Den", _spec())}
    out = {"rooms": {"roost": {"name": "Den", "desc": "Her roost.", "anchors": {
                         "Futon Nest": {"desc": "silk futons"}}},
                     "den": {"desc": "The den.", "anchors": {
                         "futon-nest": {"desc": "a den futon"}}}},
           "positions": {"Kit": "den"},
           "stations": {"Kit": {"at": "futon-nest"}}}
    hold_planned_fixtures(scene, out, specs)
    assert out["stations"]["Kit"]["at"] == "futon_nest"


def test_an_op_in_the_held_room_folds_with_its_body():
    """A body lying on the held room's re-spelled fixture, where another
    room also holds that spelling: its station and pose were folded and its
    contact and substance ops were not, so it lay on one thing and touched
    another (fourth review of 2026-10-13)."""
    out = {"rooms": {"roost": {"desc": "Her roost.", "anchors": {
                         "Futon Nest": {"desc": "a heap of silk futons"}}},
                     "parlour": {"name": "the Parlour", "desc": "A parlour.", "anchors": {
                         "Futon Nest": {"desc": "a guest futon"}}}},
           "positions": {"Kit": "roost"},
           "stations": {"Kit": {"at": "Futon Nest"}},
           "poses": {"Kit": {"posture": "lying", "support": "Futon Nest"}},
           "contact_ops": [{"op": "add", "actor": "Kit", "target": "Futon Nest", "manner": "rest",
                            "relation": "surface", "motion": "settled"}],
           "substance_ops": [{"op": "add", "source": "Futon Nest", "target": "Kit",
                              "substance": "dust"}]}
    hold_planned_fixtures(_scene(), out, {"roost": ("the Roost", _spec())})
    assert out["stations"]["Kit"]["at"] == "futon_nest"
    assert out["poses"]["Kit"]["support"] == "futon_nest"
    assert out["contact_ops"][0]["target"] == "futon_nest"
    assert out["substance_ops"][0]["source"] == "futon_nest"
