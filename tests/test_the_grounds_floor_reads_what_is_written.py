"""The grounds floor judges the building the plan will hold, never another.

Design A6 (Home 10, chat 173, 2026-10-13): the floor that refuses grounds
which do not hold together reads the scene a solve WOULD write before it is
written. That preview stays honest only while it is built by the very
functions the writer and the beat's readers use -- one rule, two readers:
`structure.solved_plan_row` and `made_plan_row` are what
`write_planned_layout` writes, and `solved_scene` lays them on the fringe's
own stubs (`_planned_stub`, `_edges_declared_to`). A field added to the
writer and not to the preview fails here first.
"""
from __future__ import annotations

import copy
import json

from world.structure import (made_plan_row, materialize_planned_fringe, registry_rows,
                             solved_plan_row, solved_scene, write_planned_layout)

from tests.test_a_stair_is_a_room import _chat, _expected, _plant, _solve

_GEOMETRY = ("site", "extent", "shape", "level", "parts", "exposure")
_EDGE = ("dir", "cell", "offset", "width", "barrier", "vertical", "way")


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _look(scene, uid):
    room = scene["rooms"][uid]
    return {"geometry": {k: room.get(k) for k in _GEOMETRY},
            "anchors": {aid: {k: a.get(k) for k in ("cell", "extent", "offset", "dir", "height")}
                        for aid, a in (room.get("anchors") or {}).items()},
            "edges": {str(e["to"]): {k: e.get(k) for k in _EDGE}
                      for e in room.get("adjacent") or () if isinstance(e, dict)}}


def test_the_rows_the_floor_reads_are_the_rows_the_writer_writes(temp_db):
    cid = _chat(temp_db)
    _plant(cid)
    before = {uid: entry["planned"] for uid, entry in registry_rows(cid).items()}
    kept = copy.deepcopy(before)
    solve = _solve()
    preview = {uid: (made_plan_row(s) if s.get("room") is not None
                     else solved_plan_row(before[uid], s)) for uid, s in solve.items()}
    # solved_plan_row never touches the plan it is handed
    assert _canon(before) == _canon(kept)
    assert write_planned_layout(cid, solve, expected=_expected(cid))
    written = {uid: entry["planned"] for uid, entry in registry_rows(cid).items()}
    for uid, row in preview.items():
        assert _canon(row) == _canon(written[uid]), uid


def test_the_preview_is_the_scene_a_beat_reads_off_the_written_plan(temp_db):
    cid = _chat(temp_db)
    _plant(cid)
    assert write_planned_layout(cid, _solve(), expected=_expected(cid))
    rows = {uid: (str(entry["name"] or uid), entry["planned"])
            for uid, entry in registry_rows(cid).items()}
    preview = solved_scene(rows)
    # the beat's reader: the fringe, a body standing in every planned room
    live = {"rooms": {}, "positions": {}}
    for uid in rows:
        live, _added = materialize_planned_fringe(cid, {"rooms": live["rooms"],
                                                        "positions": {f"b_{uid}": uid}})
    for uid in rows:
        if uid in live["rooms"]:
            assert _look(preview, uid) == _look(live, uid), uid


def _farm_solve(temp_db):
    """The farm's ground, solved and not yet written -- a composite garden,
    a round oak, a window onto the ground, and an oak whose row declares no
    way back to the garden (two plan ops, `made_edges`): the rows the floor
    judges, which the stair fixture above has none of (a review of
    2026-10-14)."""
    from world import layout_bridge as lb
    from world.structure import _planned_specs, provisional_room_ids
    from tests.test_a_building_stands_in_its_grounds import (RELATE, SORT, _farm_chat,
                                                             _grounds_on, _plant_farm, _stub_scene)
    sort, relate = copy.deepcopy(SORT), copy.deepcopy(RELATE)
    # a window onto the ground: the kitchen's, on the wall facing the garden
    next(r for r in sort["rooms"] if r["id"] == "kitchen")["windows"] = [
        {"id": "kitchen_window", "name": "the kitchen window", "faces": "the garden"}]
    next(r for r in relate["rooms"] if r["id"] == "kitchen")["windows"] = [
        {"id": "kitchen_window", "side": "e"}]
    cid = _farm_chat(temp_db)
    _plant_farm(cid)
    # a second op re-plans the oak with no way back: the garden's row still
    # declares its way to the oak, the oak's none
    _plant_farm(cid, only={"tree"}, change={"tree": {"adjacent": []}})
    _grounds_on(cid)
    specs = _planned_specs(cid)
    scene = _stub_scene(specs, desc=("pond",))
    (b,) = [x for x in lb.plan_buildings(specs, scene, held_open=provisional_room_ids(cid),
                                         grounds=True) if "hall" in x["rooms"]]
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    layout, refused = lb.solve_for(b, spec)
    assert refused == []
    solved, _report = lb.planned_layout(b, spec, layout)
    return cid, b, solved


def test_the_ground_rows_the_floor_reads_are_the_rows_the_writer_writes(temp_db):
    cid, b, solved = _farm_solve(temp_db)
    before = {uid: entry["planned"] for uid, entry in registry_rows(cid).items()}
    kept = copy.deepcopy(before)
    preview = {uid: (made_plan_row(s) if s.get("room") is not None
                     else solved_plan_row(before[uid], s)) for uid, s in solved.items()}
    assert _canon(before) == _canon(kept)
    assert write_planned_layout(cid, solved,
                                expected={**b["specs"], **(b.get("ground_specs") or {})})
    written = {uid: entry["planned"] for uid, entry in registry_rows(cid).items()}
    for uid, row in preview.items():
        assert _canon(row) == _canon(written[uid]), uid
    # what the floor judges is in what was compared
    assert written["garden"].get("parts"), "the garden is laid round the house"
    assert written["tree"]["layout"].get("made_edges") == ["garden"]
    assert any(e.get("barrier") == "window" for e in written["garden"].get("adjacent") or ()), \
        "a window onto the ground is compared"
    assert any(isinstance(e, dict) and e.get("to") == "garden" and e.get("cell") is not None
               for e in written["tree"]["adjacent"])


def test_the_ground_preview_is_the_scene_a_beat_reads(temp_db):
    cid, b, solved = _farm_solve(temp_db)
    assert write_planned_layout(cid, solved,
                                expected={**b["specs"], **(b.get("ground_specs") or {})})
    rows = {uid: (str(entry["name"] or uid), entry["planned"])
            for uid, entry in registry_rows(cid).items()}
    preview = solved_scene(rows)
    live = {"rooms": {}, "positions": {}}
    for uid in rows:
        live, _added = materialize_planned_fringe(cid, {"rooms": live["rooms"],
                                                        "positions": {f"b_{uid}": uid}})
    compared = [uid for uid in rows if uid in live["rooms"]]
    assert {"garden", "tree", "well", "path"} <= set(compared)
    for uid in compared:
        assert _look(preview, uid) == _look(live, uid), uid
