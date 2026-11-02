"""A lot's building stands on the storeys its plan gives, and the rest of the
lot's expansion is held to what the engine knows.

* STOREYS (audit of 2026-11-01, agents_runtime_loops_mapping F14). The
  architect is told the lot's `storeys` and whether a storey lies below the
  ground, and `planned_rooms_of` accepted any integer `level` from the answer:
  a lot planned `storeys: 1` with no cellar was planted with levels -1..4,
  no note, so the lot's own record and the building on it disagreed and the
  layout tier laid out a tower. A room outside the storeys the plan gives --
  or `LOT_STOREYS_MAX` of them where it gives none -- is set aside and said,
  and what only it reached goes with it.
* SLEEPERS (audit of 2026-11-01, world_layout_bridge_structure F10).
  `deal_berths` built a list of one slot per bed from the answer's unbounded
  `sleeps`, and put every sleeper past the beds into the last room, silently:
  twelve bodies over beds for 2 + 2 + 1 berthed eight in the one-bed garret,
  and "sleeps": 100000000 built a hundred-million-element list in the job's
  thread. Now dealt by arithmetic, and the overflow is said.
* ONE LOCK (agents_runtime_loops_mapping F4, agents_director_prose_movement_
  rooms F6). The "plan moved" re-check, the planting and the charter
  registry's read-modify-write in `deal_berths` ran as three separate writes,
  the last outside any transaction: a commit's charter flush landing between
  the read and the save was overwritten, and two expansions of one lot could
  both pass the re-check and both plant.
* THE BEAT'S BRIEF (agents_director_prose_movement_rooms F5). A lot the
  rooms-in-view job expanded after the beat's payload was built kept its LOT
  brief in the beat -- the whole building's purpose in one room -- and a lot
  the beat could not expand left no trace of it.
"""

from __future__ import annotations

import copy
import time
import tracemalloc

import pytest

from agents import director_lots
from world.lots import LOT_STOREYS_MAX


STREET = ("the Lane", {"purpose": "a village lane", "exposure": "open",
                       "adjacent": [{"to": "cottage", "dir": "n"}]})


def _cottage(lot):
    return ("the Cottage", {
        "purpose": "a labourer's cottage", "exposure": "enclosed",
        "far_look": "a low thatched cottage", "lot": lot,
        "adjacent": [{"to": "lane", "dir": "s", "barrier": "a plank door"}]})


def _rows(lot):
    return {uid: {"name": name, "planned": copy.deepcopy(spec)}
            for uid, (name, spec) in {"lane": STREET,
                                       "cottage": _cottage(lot)}.items()}


def _tower(top=4):
    """An answer that climbs from a cellar to storey `top`, one room each,
    each storey reached by a stair from the one below."""
    rooms = [{"id": "kitchen", "name": "the Kitchen", "purpose": "cooking",
              "level": 0, "entry": True,
              "joins": [{"to": "s1", "vertical": "up"}]},
             {"id": "cellar", "name": "the Cellar", "purpose": "keeping",
              "level": -1, "joins": [{"to": "kitchen", "vertical": "up"}]}]
    for level in range(1, top + 1):
        room = {"id": f"s{level}", "name": f"Storey {level}",
                "purpose": "sleeping", "level": level}
        if level < top:
            room["joins"] = [{"to": f"s{level + 1}", "vertical": "up"}]
        rooms.append(room)
    return {"rooms": rooms}


def _levels(rooms):
    return sorted(spec["level"] for spec in rooms.values())


def test_a_one_storey_lot_with_no_cellar_plants_its_ground_storey_only():
    rooms, notes, _ = director_lots.planned_rooms_of(
        "cottage", _rows({"storeys": 1}), _tower(), turn_idx=3)
    assert _levels(rooms) == [0]
    said = " ".join(notes)
    assert "cellar" in said and "s1" in said and "s4" in said


def test_a_cellar_and_the_storeys_the_plan_gives_are_kept():
    rooms, notes, _ = director_lots.planned_rooms_of(
        "cottage", _rows({"storeys": 2, "cellar": True}), _tower(), turn_idx=3)
    assert _levels(rooms) == [-1, 0, 1]
    assert "s2" in " ".join(notes)


def test_a_lot_whose_plan_gives_no_storeys_is_held_to_the_named_ceiling():
    rooms, notes, _ = director_lots.planned_rooms_of(
        "cottage", _rows({}), _tower(top=LOT_STOREYS_MAX), turn_idx=3)
    assert _levels(rooms) == list(range(0, LOT_STOREYS_MAX))
    said = " ".join(notes)
    assert f"s{LOT_STOREYS_MAX}" in said and "cellar" in said


# ---- sleepers ----------------------------------------------------------------

def _registry(n, lot="inn"):
    return {"items": {"household": {"state": {"bodies": {
        f"b{k:02d}": {"berth": lot, "place": lot} for k in range(n)}}}}}


def _patched(monkeypatch, registry):
    import world.charter_runtime as charter_runtime
    monkeypatch.setattr(charter_runtime, "registry_for_update",
                        lambda cid, frame_id=None: registry)
    monkeypatch.setattr(charter_runtime, "save_registry",
                        lambda cid, reg, frame_id=None: None)


def test_sleepers_past_the_beds_are_berthed_and_said(monkeypatch):
    registry = _registry(12)
    _patched(monkeypatch, registry)
    notes = []
    moved = director_lots.deal_berths(
        1, "inn", {"inn__room_a": 2, "inn__room_b": 2, "inn__garret": 1},
        notes=notes)
    berths = [b["berth"] for b in
              registry["items"]["household"]["state"]["bodies"].values()]
    assert moved == 12
    assert berths.count("inn__room_a") == 2 and berths.count("inn__room_b") == 2
    # the overflow policy is unchanged (the last sleeping room) -- but said
    assert berths.count("inn__garret") == 8
    said = " ".join(notes)
    assert "7" in said and "inn__garret" in said


def test_a_room_said_to_sleep_a_vast_number_builds_no_list(monkeypatch):
    registry = _registry(3)
    _patched(monkeypatch, registry)
    tracemalloc.start()
    try:
        moved = director_lots.deal_berths(1, "inn", {"inn__hall": 10 ** 6})
        _now, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert moved == 3
    assert peak < 200_000, peak


# ---- one lock ---------------------------------------------------------------------

STORE = ("the General Store", {
    "purpose": "the general store", "exposure": "enclosed",
    "lot": {"storeys": 1},
    "adjacent": [{"to": "street", "dir": "s", "barrier": "a shop door"}]})
SHOP = {"rooms": [
    {"id": "shop", "name": "the Shop", "purpose": "selling", "level": 0,
     "entry": True, "joins": [{"to": "back", "side": "n"}]},
    {"id": "back", "name": "the Back Room", "purpose": "sleeping",
     "level": 0, "sleeps": 2}]}


def _chat(db):
    from world.structure import plant_structure
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Lots", "A village.", time.time()))
    plant_structure(cid, {"key": "village", "name": "The Village"}, {
        "street": dict(copy.deepcopy(STREET[1]), name="the Street",
                       adjacent=[{"to": "store", "dir": "n"}]),
        "store": dict(copy.deepcopy(STORE[1]), name=STORE[0])})
    return cid


def test_the_recheck_the_planting_and_the_berths_share_one_transaction(
        temp_db, monkeypatch):
    from core import db
    import world.charter_runtime as charter_runtime
    import world.structure as structure

    cid = _chat(temp_db)
    seen = []
    real_rows, real_plant = structure.registry_rows, structure.plant_structure
    real_read = charter_runtime.registry_for_update
    real_save = charter_runtime.save_registry

    def depth():
        return int(getattr(db._local, "tx_depth", 0))

    def rows(c):
        seen.append(("rows", depth()))
        return real_rows(c)

    def plant(*a, **k):
        seen.append(("plant", depth()))
        return real_plant(*a, **k)

    def read(c, frame_id=None):
        seen.append(("berth read", depth()))
        return dict(_registry(2, lot="store"))

    def save(c, reg, frame_id=None):
        seen.append(("berth save", depth()))

    def architect(step, system, payload):
        seen.append(("call", depth()))
        return copy.deepcopy(SHOP)

    monkeypatch.setattr(structure, "registry_rows", rows)
    monkeypatch.setattr(structure, "plant_structure", plant)
    monkeypatch.setattr(charter_runtime, "registry_for_update", read)
    monkeypatch.setattr(charter_runtime, "save_registry", save)
    planted = director_lots.expand_lot(cid, "store", {}, call=architect,
                                       language_id="en", turn_idx=2)
    assert planted and planted[0] == "store"
    # the model call holds no lock; from the re-check after it on, every step
    # -- the re-read of the plan, the planting, the registry's read and save
    # -- is inside one open transaction
    called = [what for what, _d in seen].index("call")
    assert seen[called][1] == 0
    tail = seen[called + 1:]
    assert tail[0][0] == "rows"
    assert [what for what, _d in tail if what != "rows"] == [
        "plant", "berth read", "berth save"]
    assert all(d >= 1 for _what, d in tail), tail


# ---- the beat's brief -------------------------------------------------------------

def test_a_lot_the_job_expanded_gives_the_beat_its_entrys_brief(temp_db):
    cid = _chat(temp_db)
    stale = {"store": {"name": "the General Store",
                       "purpose": "the general store",
                       "exits": [{"to": "street", "name": "the Street"}]}}
    # the rooms-in-view job expanded it after the beat's payload was built
    assert director_lots.expand_lot(
        cid, "store", {}, call=lambda s, y, p: copy.deepcopy(SHOP),
        language_id="en", turn_idx=2)
    asked = []
    develop = director_lots.expand_entered_lots(
        cid, stale, {"rooms": {}}, "en",
        call=lambda s, y, p: asked.append(s) or copy.deepcopy(SHOP), turn_idx=3)
    assert asked == []                          # nothing left to expand
    assert develop["store"]["purpose"] == "selling"
    assert "store__back" in {e["to"] for e in develop["store"]["exits"]}


def test_a_lot_the_beat_could_not_expand_is_said(temp_db):
    from core.pipeline_context import current_warning_sink

    cid = _chat(temp_db)
    brief = {"store": {"name": "the General Store",
                       "purpose": "the general store", "exits": []}}
    warnings = []
    token = current_warning_sink.set(warnings.append)
    try:
        develop = director_lots.expand_entered_lots(
            cid, brief, {"rooms": {}}, "en",
            call=lambda s, y, p: {"rooms": "none"}, turn_idx=3)
    finally:
        current_warning_sink.reset(token)
    assert develop["store"]["purpose"] == "the general store"
    assert any("store" in w for w in warnings), warnings
