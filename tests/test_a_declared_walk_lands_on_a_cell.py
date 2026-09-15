"""A declared walk lands where the beat's paces carry it, on a cell.

The resolve used to put a walker in the destination room and nowhere in
it. Now the open route is walked over the cells (`world/spatial_walk`):
the body arrives just inside the door, or at the feature the declaration
named, or is left mid-way with the walk recorded as under way so silence
carries it on next beat.
"""
import agents.director as director
import agents.director_movement as movement
from tests.test_director_movement import _make_ctx


def test_an_open_adjacent_walk_arrives_inside_the_door_on_a_cell(temp_db, monkeypatch):
    from world.spatial import inside_the_door
    ctx = _make_ctx(temp_db, "lamp_room")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})
    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]
    assert sd["positions"]["The Stranger"] == "lamp_room"
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    assert sd["stations"]["The Stranger"]["cell"] == list(inside_the_door(sc, "lamp_room", "keeper_room"))
    assert not any("under way" in w for w in ctx.warnings)


def test_a_walk_the_paces_do_not_finish_is_under_way(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, "lamp_room")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})
    monkeypatch.setattr(movement, "paces_for", lambda seconds=None: 1)
    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]
    assert sd["positions"]["The Stranger"] == "keeper_room"
    assert "cell" in sd["stations"]["The Stranger"]
    advanced = out["travel"]["advanced"]
    assert advanced and advanced[0]["subject"] == "The Stranger"
    assert advanced[0]["underway"] and advanced[0]["destination"] == "lamp_room"
    assert any("Walk under way" in w for w in ctx.warnings)


def test_a_walk_under_way_continues_in_silence_and_arrives(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, "lamp_room")
    ctx.director_interpret["movement"] = None
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["approach"] = {"The Stranger": {"to_room": "lamp_room", "turn": 0}}
    temp_db.wset(ctx.chat.id, "scene", sc)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})
    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]
    assert sd["positions"]["The Stranger"] == "lamp_room"
    assert "cell" in sd["stations"]["The Stranger"]
    assert "The Stranger" in out["travel"]["arrived"]


def test_the_beats_span_sets_the_budget():
    class _Ctx:
        chat = {"id": 1}
    assert movement.beat_seconds(_Ctx(), {}) == movement.UNCLAIMED_BEAT_SECONDS
    assert movement.beat_seconds(_Ctx(), {"time": {"duration_seconds": 45}}) == 45.0
