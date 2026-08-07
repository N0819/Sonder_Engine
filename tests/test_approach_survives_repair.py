"""A deliberate deletion is indistinguishable from an omission.

`_guard_approach_is_not_arrival` refuses a position for a mover whose own
declaration says `arrives: false`. It works by DELETING the position from the
resolve's diff -- and `_reconcile_resolution`, which runs afterwards, scans the
beat's prose for anything the diff fails to encode and merges a repair delta
back in. A refusal looks exactly like a gap. So the prose kept re-supplying the
position the guard had just removed, and the guard's own warning went out in
the same step that shipped the move.

Live, chat 63 turn 165. The player wrote:

    "Anyways... good night." You walk towards the shoji leading to the
    upstairs opening it.

`director_interpret` read it exactly right -- `movement.arrives: false`, the
walk staged `approach`, asserted effects "shoji opened" and "stairs revealed",
no stepping through. The guard fired and both its warnings are on the turn:
"No position committed this beat" and "Position unchanged -- moving closer to
somewhere is not being there". The committed scene put her upstairs regardless,
and the persisted resolve variant carries the position in the same record whose
warnings say it was removed.

Opening a door is not walking through it. The guard now runs last.
"""

from __future__ import annotations

import agents.director as director


class _Ctx:
    def __init__(self):
        self.warnings = []


SCENE = {
    "positions": {"Hinami": "shrine_interior_first_floor"},
    "rooms": {
        "shrine_interior_first_floor": {"adjacent": [
            {"to": "shrine_interior_upstairs", "barrier": "open"}]},
        "shrine_interior_upstairs": {"adjacent": [
            {"to": "shrine_interior_first_floor", "barrier": "open"}]},
    },
}
INTERP = {"movement": {"to_room": "shrine_interior_upstairs", "mover": "self",
                       "arrives": False,
                       "why": "heading up to rest for the night"}}


def _diff(room="shrine_interior_upstairs"):
    return {"positions": {"Hinami": room}}


def test_the_guard_refuses_the_position():
    """The behaviour that always worked, pinned so the reorder cannot lose
    it.
    """
    ctx = _Ctx()
    sd = _diff()
    director._guard_approach_is_not_arrival(ctx, INTERP, sd, SCENE, "Hinami")
    assert "Hinami" not in sd["positions"]
    assert any("Approach is not arrival" in w for w in ctx.warnings)


def test_the_guard_runs_after_the_repair_pass_not_before():
    """THE REPRODUCTION, as a structural fact rather than a mock of the whole
    resolve. The guard's call site must come after `_reconcile_resolution`,
    because that pass re-encodes whatever the prose says and the diff lacks --
    which, once the guard has fired, includes the guard's own refusal.
    """
    import inspect

    src = inspect.getsource(director.director_resolve)
    guard = src.index("_guard_approach_is_not_arrival(ctx, interp")
    repair = src.index("_reconcile_resolution(ctx, out")
    assert guard > repair, (
        "the approach guard runs before the repair pass, which re-adds the "
        "position it deleted")


def test_the_guard_is_handed_the_diff_that_ships():
    """It must mutate `out["state_diff"]` -- the object that gets persisted --
    and not a local that reconciliation has since replaced.
    """
    import inspect

    src = inspect.getsource(director.director_resolve)
    call = src[src.index("_guard_approach_is_not_arrival(ctx, interp"):]
    assert 'out["state_diff"]' in call.split(")")[0], call.split(")")[0]


def test_a_reasserted_position_is_removed_again():
    """Idempotence, which is what makes running last sufficient: whatever put
    the position back, the guard takes it out.
    """
    ctx = _Ctx()
    sd = _diff()
    director._guard_approach_is_not_arrival(ctx, INTERP, sd, SCENE, "Hinami")
    sd["positions"]["Hinami"] = "shrine_interior_upstairs"  # the repair delta
    director._guard_approach_is_not_arrival(ctx, INTERP, sd, SCENE, "Hinami")
    assert "Hinami" not in sd["positions"]


def test_a_move_to_a_room_the_declaration_never_named_is_still_refused():
    """Live, the repair put her in `shrine_interior_second_floor_sleeping_
    quarters` while the declaration named `shrine_interior_upstairs`. The
    guard keys on the mover having moved AT ALL, not on the destination
    matching -- otherwise a renamed room walks straight past it.
    """
    ctx = _Ctx()
    sd = _diff("shrine_interior_second_floor_sleeping_quarters")
    director._guard_approach_is_not_arrival(ctx, INTERP, sd, SCENE, "Hinami")
    assert "Hinami" not in sd["positions"]


def test_an_arrival_is_left_alone():
    """The guard reads the declaration, not the prose. `arrives: true` is the
    player saying they got there, and it must commit.
    """
    ctx = _Ctx()
    sd = _diff()
    interp = {"movement": {**INTERP["movement"], "arrives": True}}
    director._guard_approach_is_not_arrival(ctx, interp, sd, SCENE, "Hinami")
    assert sd["positions"]["Hinami"] == "shrine_interior_upstairs"
    assert ctx.warnings == []
