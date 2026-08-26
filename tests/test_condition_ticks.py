"""A condition that acts while it lasts, and a ledger the Director can see.

`world_conditions` shipped with a `next_tick` column and an
`idx_world_conditions_due` index over it, and nothing ever wrote either.
Measured read-only on the author's engine.db, 2026-08-25: 444 rows across 50
chats, 363 active, 360 of those with NO `expires_at` and therefore unable to
end by any mechanism the engine had; `next_tick` NULL in all 444; and 131
ACTIVE rows carrying an authored `tick_interval_seconds` (values 0, 5, 10, 15,
20, 30, 45, 60, 300) that no reader anywhere consumed. `llm/schemas.py` stated
the open question in its own comment -- build the due-tick sweep, or drop the
field, the column and the index. These tests are the build.

Two behaviours, and they are separate on purpose:

* pass (c1) of `world.mechanics.mechanics_sweep` fires due ticks against the
  SIMULATION clock and persists cadence through `next_tick`;
* `agents.director_floors._conditions_view` puts every live row -- with its
  `condition_id` -- into the Director's payload, which is Reason 1 of the
  WAKING block generalized: a hand cannot end an id it was never shown.

What a tick may do is deliberately narrow, because the engine must never
learn what any particular condition MEANS. It may move a survival vital the
scene ALREADY tracks, and it may re-announce one clause. It may not create
the vitals ledger: `world/survival.py` says absence is the off switch, and a
tick that seeded the table would start a hunger clock in stories that never
enabled survival -- 131 active rows already carry intervals, so that would
have fired broadly on landing.
"""

from __future__ import annotations

import json
import time

import pytest

from persist.checkpoints import ensure_checkpoint, restore_checkpoint
from persist.commit import (commit_scene, commit_transit_sweep,
                            commit_world_entities, prepare_scene_commit)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.scene import active_condition_rows, condition_exit_owner
from world.mechanics import mechanics_sweep


# --------------------------------------------------------------------------
# Harness (the shapes tests/test_mechanics_sweep.py uses)
# --------------------------------------------------------------------------

def _make_chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Ticks", None, "", time.time()),
    )


def _make_ctx(temp_db, chat_id, *, turn_idx, diff):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "wait", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Ticks", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="wait", created=time.time()),
        cast=[], input="wait",
    )
    ctx.director_resolve = {
        "resolved_event": "Time passes.", "dialogue_log": [],
        "state_diff": diff,
    }
    return ctx


def _scene(vitals=None):
    scene = {
        "location": "Kessler Tower", "time": "night",
        "rooms": {"hold": {"name": "Hold", "desc": "A hold.", "adjacent": []}},
        "entities": {}, "positions": {"Mara": "hold"},
        "attire": {}, "overlays": {},
    }
    if vitals is not None:
        scene["vitals"] = vitals
    return scene


def _cond(condition_id="c1", *, subject="Mara", kind="flooding",
          next_tick=None, expires_at=None, payload=None, started_at=0.0):
    return {
        "condition_id": condition_id, "subject_id": subject, "kind": kind,
        "started_at": started_at, "expires_at": expires_at,
        "next_tick": next_tick,
        "payload": json.dumps(payload or {}, ensure_ascii=False),
    }


def _sweep(scene, conditions, elapsed):
    return mechanics_sweep(scene, {"elapsed_seconds": elapsed}, "f1", [],
                           conditions=conditions, turn_idx=3)


def _ticks(event_ops):
    return [op for op in event_ops if op[0] == "tick_condition"]


# --------------------------------------------------------------------------
# Pass (c1): the tick engine, pure (no database)
# --------------------------------------------------------------------------

def test_a_row_with_an_interval_and_no_next_tick_is_scheduled_not_fired():
    """CADENCE IS THE SWEEP'S, NOT THE WRITER'S. All 444 corpus rows carry a
    NULL `next_tick`, so every existing interval-bearing row meets this pass
    uninitialized. It is scheduled from the clock it is first SEEN on and
    fires nothing that beat -- an initialization that also fired would
    charge a row for every second of story that happened before the sweep
    existed."""
    scene = _scene({"Mara": {"air": 1.0}})
    _, ops, notices, _ = _sweep(
        scene, [_cond(payload={"tick_interval_seconds": 10,
                               "tick": {"vitals": {"air": -0.1}}})], 500.0)
    assert _ticks(ops) == [("tick_condition", "c1", 510.0)]
    assert scene["vitals"]["Mara"]["air"] == 1.0
    assert notices == []


def test_due_ticks_batch_against_the_clock_and_move_a_tracked_vital():
    """Four fires (t=100,110,120,130) inside one beat: the story clock is
    free to jump, so a tick must be able to fire more than once per beat.
    The percept is announced ONCE regardless of the fire count -- a clause
    repeated four times is the same fact four times."""
    scene = _scene({"Mara": {"air": 1.0, "stamina": 1.0}})
    _, ops, notices, _ = _sweep(
        scene,
        [_cond(next_tick=100.0,
               payload={"tick_interval_seconds": 10,
                        "tick": {"vitals": {"stamina": -0.05},
                                 "percept": "water at the knees"}})],
        135.0)
    assert _ticks(ops) == [("tick_condition", "c1", 140.0)]
    assert abs(scene["vitals"]["Mara"]["stamina"] - 0.8) < 1e-9
    assert sum("water at the knees" in n for n in notices) == 1


def test_a_vital_move_is_clamped_into_range():
    scene = _scene({"Mara": {"stamina": 0.1}})
    _sweep(scene,
           [_cond(next_tick=0.0,
                  payload={"tick_interval_seconds": 10,
                           "tick": {"vitals": {"stamina": -0.2}}})],
           100.0)
    assert scene["vitals"]["Mara"]["stamina"] == 0.0


def test_a_tick_never_fires_at_or_past_the_row_s_own_expiry():
    """Pass (c1) runs before pass (c2) so a final due tick lands before the
    expiry closes the row -- but not one tick beyond it."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _, ops, _, _ = _sweep(
        scene,
        [_cond(next_tick=100.0, expires_at=120.0,
               payload={"tick_interval_seconds": 10,
                        "tick": {"vitals": {"stamina": -0.1}}})],
        200.0)
    assert _ticks(ops) == [("tick_condition", "c1", 120.0)]
    assert abs(scene["vitals"]["Mara"]["stamina"] - 0.8) < 1e-9
    assert ("expire_condition", "c1") in ops


def test_the_fire_cap_catches_up_and_does_not_lag():
    """THE CAP MUST CATCH UP. With the story clock free to jump hours in one
    beat (`read_time_diff`, alpha 9.8.2), carrying the capped cadence forward
    as `next_tick + fires*interval` would leave `next_tick` permanently
    behind the clock and re-hit the cap on every beat for the rest of the
    story. The row is re-based on the clock instead."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _, ops, _, _ = _sweep(
        scene,
        [_cond(next_tick=0.0,
               payload={"tick_interval_seconds": 1,
                        "tick": {"percept": "still burning"}})],
        100000.0)
    assert _ticks(ops) == [("tick_condition", "c1", 100001.0)]


def test_an_interval_of_zero_is_not_a_cadence():
    """48 of the 131 active interval-bearing corpus rows spell `0`, the
    commonest authored value. Zero is not "tick constantly": it is a field
    filled in with nothing, and a divisor of zero besides."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    for interval in (0, -5, "soon", None):
        _, ops, notices, _ = _sweep(
            scene, [_cond(payload={"tick_interval_seconds": interval,
                                   "tick": {"percept": "x"}})], 500.0)
        assert _ticks(ops) == [], interval
        assert notices == [], interval


def test_a_vital_the_survival_ledger_does_not_track_is_dropped():
    """THE GUARD SUBTRACTS. `state_diff.conditions` is open model text, so a
    tick may name anything; only the four keys `world.survival.VITALS`
    defines can move, and an unknown one is dropped rather than invented."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _sweep(scene,
           [_cond(next_tick=0.0,
                  payload={"tick_interval_seconds": 10,
                           "tick": {"vitals": {"morale": -0.5,
                                               "stamina": -0.1}}})],
           10.0)
    assert "morale" not in scene["vitals"]["Mara"]
    assert abs(scene["vitals"]["Mara"]["stamina"] - 0.8) < 1e-9


def test_a_per_tick_step_is_clamped_so_one_tick_cannot_empty_a_body():
    """A model authoring `-1.0` per tick against a five-second cadence would
    kill a body in one beat. The per-tick magnitude is capped; the cadence,
    not the size of one step, is how a condition gets to be lethal."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _sweep(scene,
           [_cond(next_tick=0.0,
                  payload={"tick_interval_seconds": 10,
                           "tick": {"vitals": {"stamina": -1.0}}})],
           0.0)
    assert abs(scene["vitals"]["Mara"]["stamina"] - 0.75) < 1e-9


def test_a_subject_the_vitals_table_does_not_name_is_skipped_and_said():
    """Condition subjects are free model text and some rows carry scene uids
    (docs/UNBUILT.md 1.65). The table EXISTS here, so a name that matches
    nothing in it is a miss worth reporting -- a mechanism that silently
    never fires is this table's whole failure history."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _, _, notices, _ = _sweep(
        scene,
        [_cond(subject="ent_7f2", next_tick=0.0,
               payload={"tick_interval_seconds": 10,
                        "tick": {"vitals": {"stamina": -0.1}}})],
        10.0)
    assert scene["vitals"]["Mara"]["stamina"] == 1.0
    assert any("ent_7f2" in n for n in notices)


def test_a_tick_never_creates_the_vitals_ledger():
    """ABSENCE IS THE OFF SWITCH (world/survival.py:227-231,
    world/spatial_merge.py:1219-1222). Nothing but an explicit write creates
    the vitals table, and a tick must not be the exception: 131 active
    corpus rows carry intervals, so a seeding tick would have started a
    hunger clock in every story that never enabled survival. The cadence
    still advances and the percept is still announced -- only the vital move
    is dropped, in silence, because the setting being off is not a failure."""
    scene = _scene()
    _, ops, notices, _ = _sweep(
        scene,
        [_cond(next_tick=0.0,
               payload={"tick_interval_seconds": 10,
                        "tick": {"vitals": {"stamina": -0.1},
                                 "percept": "the cold does not let up"}})],
        30.0)
    assert "vitals" not in scene
    assert _ticks(ops) == [("tick_condition", "c1", 40.0)]
    assert any("the cold does not let up" in n for n in notices)


def test_an_interval_with_no_declared_effects_only_advances_the_cadence():
    """The 131 legacy rows are exactly this shape. A cadence with nothing
    declared under it is a no-op that keeps its place in time; inventing an
    effect from the bare interval would be the engine authoring fiction."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _, ops, notices, _ = _sweep(
        scene, [_cond(next_tick=0.0,
                      payload={"tick_interval_seconds": 30})], 95.0)
    assert _ticks(ops) == [("tick_condition", "c1", 120.0)]
    assert notices == []
    assert scene["vitals"]["Mara"]["stamina"] == 1.0


def test_the_tick_pass_reads_a_state_nested_tick_block_too():
    """Condition fields are spelled at the payload root or inside `state`
    everywhere else in this table (`_condition_state`); the tick block is
    read from both, for the same reason."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _, ops, _, _ = _sweep(
        scene,
        [_cond(next_tick=0.0,
               payload={"state": {"tick_interval_seconds": 10,
                                  "tick": {"vitals": {"stamina": -0.1}}}})],
        10.0)
    assert _ticks(ops) == [("tick_condition", "c1", 20.0)]
    assert abs(scene["vitals"]["Mara"]["stamina"] - 0.8) < 1e-9


def test_a_null_root_spelling_does_not_mask_the_state_spelling():
    """`_condition_field` reads the root spelling first and `state` second.
    Reading "the key is present" rather than "the key has a value" makes a
    payload that lists every field and nulls the ones it has nothing to say
    about hide the value it DID fill in. 0 of 444 corpus rows are in that
    shape today, so this is latent -- and the helper's whole stated purpose
    is that a reader knowing one spelling must not ignore half the rows."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    _, ops, notices, _ = _sweep(
        scene,
        [_cond(next_tick=100.0,
               payload={"tick_interval_seconds": None, "tick": None,
                        "state": {"tick_interval_seconds": 10,
                                  "tick": {"vitals": {"stamina": -0.1},
                                           "percept": "water at the ankles"}}})],
        120.0)
    assert _ticks(ops) == [("tick_condition", "c1", 130.0)]
    assert scene["vitals"]["Mara"]["stamina"] == pytest.approx(0.7)
    assert any("water at the ankles" in n for n in notices)


def test_tick_notices_are_capped_and_an_unnamed_subject_is_said_once():
    """A sibling of `director_floors._CONDITIONS_VIEW_CAP`, which had none.
    One corpus chat carries 24 active rows (engine.db 2026-08-25), and these
    notices restage EVERY beat for as long as the processes run, so an
    uncapped sweep spends the beat's whole notice budget on the world
    repeating itself. The truncation is SAID, and rows naming the same body
    the vitals ledger cannot match collapse to one line rather than N."""
    scene = _scene({"Mara": {"stamina": 1.0}})
    conds = [
        _cond(f"c{n}", next_tick=0.0,
              payload={"tick_interval_seconds": 10,
                       "tick": {"percept": f"process {n} continues"}})
        for n in range(12)
    ]
    _, _, notices, _ = _sweep(scene, conds, 10.0)
    assert len(notices) == 9          # 8 processes + the truncation line
    assert "4 further standing condition" in notices[-1]

    conds = [
        _cond(f"c{n}", subject="ent_7f2", next_tick=0.0,
              payload={"tick_interval_seconds": 10,
                       "tick": {"vitals": {"stamina": -0.1}}})
        for n in range(3)
    ]
    _, _, notices, _ = _sweep(_scene({"Mara": {"stamina": 1.0}}), conds, 10.0)
    assert len([n for n in notices if "ent_7f2" in n]) == 1


def test_the_sweep_counts_dict_keeps_exactly_its_three_keys():
    """`counts` is what pass (a) fired; `ticked` is a count of ops the
    CALLER applies, and belongs to whoever applies them -- the same split
    `scheduled` and `expired` already live under."""
    scene = _scene()
    _, _, _, counts = _sweep(
        scene, [_cond(payload={"tick_interval_seconds": 10})], 10.0)
    assert set(counts) == {"fired", "news_fired", "consequences_fired"}


# --------------------------------------------------------------------------
# The commit path
# --------------------------------------------------------------------------

def test_next_tick_initializes_on_one_turn_and_advances_on_the_next(temp_db):
    """End to end. Turn 1 sees a NULL `next_tick` and schedules it; turn 2
    fires the ticks that came due, moves the tracked vital, stages the
    clause on `engine_notices` and reports `ticked`."""
    cid = _make_chat(temp_db)
    temp_db.wset(cid, "scene", _scene({"Mara": {"air": 1.0}}))
    temp_db.wset(cid, "simulation_clock",
                 {"elapsed_seconds": 1000.0, "display": "now"})
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        ("hold_flooding", cid, "Mara", "flooding", 0.0, None, None,
         json.dumps({"tick_interval_seconds": 15,
                     "tick": {"vitals": {"air": -0.05},
                              "percept": "the water is still rising"}}), 1),
    )

    ctx1 = _make_ctx(temp_db, cid, turn_idx=1, diff={})
    prepared1 = prepare_scene_commit(ctx1)
    r1 = commit_transit_sweep(ctx1, 0, prepared=prepared1)
    commit_scene(ctx1, 0, prepared=prepared1)
    row = temp_db.q("SELECT * FROM world_conditions WHERE chat_id=?",
                    (cid,), one=True)
    assert row["next_tick"] == 1015.0
    assert r1["ticked"] == 1
    assert temp_db.wget(cid, "scene", {})["vitals"]["Mara"]["air"] == 1.0

    ctx2 = _make_ctx(temp_db, cid, turn_idx=2,
                     diff={"time": {"end_seconds": 1060.0}})
    prepared2 = prepare_scene_commit(ctx2)
    r2 = commit_transit_sweep(ctx2, 0, prepared=prepared2)
    commit_scene(ctx2, 0, prepared=prepared2)
    row = temp_db.q("SELECT * FROM world_conditions WHERE chat_id=?",
                    (cid,), one=True)
    assert row["next_tick"] == 1075.0            # 1015, 1030, 1045, 1060
    assert r2["ticked"] == 1
    sc = temp_db.wget(cid, "scene", {})
    assert abs(sc["vitals"]["Mara"]["air"] - 0.8) < 1e-9
    assert any("the water is still rising" in n
               for n in temp_db.wget(cid, "engine_notices", []))


def test_rerun_of_the_same_turn_produces_an_identical_world(temp_db):
    """Reroll safety for the new column and the new payload stamps: both
    derive only from the simulation clock and the turn index, so restoring
    the pre-turn checkpoint and re-running the identical turn must come out
    byte-identical."""
    cid = _make_chat(temp_db)
    temp_db.wset(cid, "scene", _scene({"Mara": {"air": 1.0}}))
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 1000.0})
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        ("hold_flooding", cid, "Mara", "flooding", 0.0, None, 1000.0,
         json.dumps({"tick_interval_seconds": 15,
                     "tick": {"vitals": {"air": -0.05}}}), 1),
    )
    # Seeded because checkpoint restore always (re)writes this key; without
    # it the post-restore world would differ by its mere existence.
    temp_db.wset(cid, "lore_cache", [])

    def dump():
        return {
            "world": {r["key"]: r["value"] for r in temp_db.q(
                "SELECT key, value FROM world WHERE chat_id=?", (cid,))},
            "conditions": [dict(r) for r in temp_db.q(
                "SELECT * FROM world_conditions WHERE chat_id=? "
                "ORDER BY condition_id", (cid,))],
        }

    diff = {"time": {"end_seconds": 1090.0},
            "conditions": {"hold_flooding": [
                {"condition_id": "hold_flooding", "subject_id": "Mara",
                 "kind": "flooding", "severity": 0.4}]}}

    ctx = _make_ctx(temp_db, cid, turn_idx=4, diff=diff)
    ensure_checkpoint(cid, 4)
    prepared = prepare_scene_commit(ctx)
    commit_transit_sweep(ctx, 0, prepared=prepared)
    commit_world_entities(ctx, 0, prepared=prepared)
    commit_scene(ctx, 0, prepared=prepared)
    first = dump()

    restore_checkpoint(cid, 4)
    # Same turn row re-used on a rerun (a reroll keeps the turn id).
    ctx2 = PipelineContext(chat=ctx.chat, turn=ctx.turn, cast=[], input="wait")
    ctx2.director_resolve = {
        "resolved_event": "Time passes.", "dialogue_log": [],
        "state_diff": json.loads(json.dumps(diff)),
    }
    prepared2 = prepare_scene_commit(ctx2)
    commit_transit_sweep(ctx2, 0, prepared=prepared2)
    commit_world_entities(ctx2, 0, prepared=prepared2)
    commit_scene(ctx2, 0, prepared=prepared2)
    assert dump() == first


# --------------------------------------------------------------------------
# The write path
# --------------------------------------------------------------------------

def _write_condition(temp_db, cid, turn_idx, cond, clock=500.0):
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": clock})
    ctx = _make_ctx(temp_db, cid, turn_idx=turn_idx,
                    diff={"conditions": {cond["condition_id"]: [cond]}})
    commit_world_entities(ctx, 0)
    return ctx


def test_a_written_condition_is_stamped_with_when_it_was_last_asserted(temp_db):
    """Idleness is only measurable if assertion is recorded. Nothing in the
    corpus records it, which is why "has anyone mentioned this in the last
    thirty turns" was an unanswerable question about 360 immortal rows.

    ONE stamp, in turns, because one is what `_conditions_view` reads. The
    simulation-second twin was dropped in the repair pass: the view already
    carries `age_seconds`, so the second clock number was a persisted field
    nothing read."""
    cid = _make_chat(temp_db)
    temp_db.wset(cid, "scene", _scene())
    cond = {"condition_id": "k1", "subject_id": "Mara", "kind": "chilled"}
    ctx = _write_condition(temp_db, cid, 7, cond, clock=610.0)

    row = temp_db.q("SELECT payload FROM world_conditions WHERE chat_id=?",
                    (cid,), one=True)
    stored = json.loads(row["payload"])
    assert stored["last_asserted_turn_idx"] == 7
    assert "last_asserted_at_seconds" not in stored
    # The stage variant's own diff dict is never mutated: it is the stored
    # record of what the model said, not a scratchpad for the commit.
    assert "last_asserted_turn_idx" not in cond

    _write_condition(temp_db, cid, 19, dict(cond), clock=980.0)
    stored = json.loads(temp_db.q(
        "SELECT payload FROM world_conditions WHERE chat_id=?",
        (cid,), one=True)["payload"])
    assert stored["last_asserted_turn_idx"] == 19
    assert "last_asserted_at_seconds" not in stored


def test_a_re_emission_authors_an_expiry_and_never_the_cadence(temp_db):
    """THE SAME NOTHING-EVER-ENDS CLASS, on the UPDATE branch -- and the
    ownership line that keeps the repair from re-opening it.

    `expires_at`: the insert always read `expires_at_seconds`; the update
    named only subject_id/kind/payload/active, so a Director granting a
    standing condition an end on re-emission had that end silently discarded
    and the row stayed immortal. COALESCE, so a re-emission that authors no
    expiry keeps the row's own -- the guard subtracts.

    `next_tick`: NEVER, on either branch. CADENCE IS OWNED BY THE SWEEP
    (world/mechanics.py pass (c1)), which schedules a row from the clock it
    first SEES it on. A writer-set value past any reachable clock freezes
    that row's cadence forever -- `_tick_conditions` loops `while t <=
    elapsed`, so it emits no op, and nothing surfaces `next_tick` to any
    reader who could repair it -- and a far-past one burns the 500-fire cap
    every beat. Measured read-only 2026-08-25: 0 of 444 corpus rows author
    `next_tick_seconds` and no prompt in either language pack teaches it."""
    cid = _make_chat(temp_db)
    temp_db.wset(cid, "scene", _scene())
    base = {"condition_id": "k1", "subject_id": "Mara", "kind": "chilled"}
    _write_condition(temp_db, cid, 1,
                     dict(base, next_tick_seconds=600.0))
    row = temp_db.q("SELECT * FROM world_conditions WHERE chat_id=?",
                    (cid,), one=True)
    assert row["expires_at"] is None
    assert row["next_tick"] is None      # the INSERT does not take it either

    _write_condition(temp_db, cid, 2,
                     dict(base, expires_at_seconds=900.0,
                          next_tick_seconds=999999.0))
    row = temp_db.q("SELECT * FROM world_conditions WHERE chat_id=?",
                    (cid,), one=True)
    assert row["expires_at"] == 900.0
    assert row["next_tick"] is None

    _write_condition(temp_db, cid, 3, dict(base))
    row = temp_db.q("SELECT * FROM world_conditions WHERE chat_id=?",
                    (cid,), one=True)
    assert row["expires_at"] == 900.0 and row["next_tick"] is None


# --------------------------------------------------------------------------
# Which floor owns an exit, and the view
# --------------------------------------------------------------------------

def test_condition_exit_owner_names_the_floor_that_can_already_end_a_row():
    """The composition contract, stated as a predicate. A gated awareness row
    is ended by `director_floors._awareness_exits`; a restraint by the
    RELEASE floors; a disguise or transformation by the standing-body
    supersession at the write. Everything else -- including a NON-gated
    `dazed`, which no floor touches -- is owned by nobody, and is precisely
    the class that stands forever."""
    assert condition_exit_owner("awareness", {"state": {"level": "asleep"}}) \
        == "awareness_floor"
    assert condition_exit_owner("unconscious", {}) == "awareness_floor"
    assert condition_exit_owner("awareness", {"state": {"level": "dazed"}}) \
        is None
    assert condition_exit_owner("physical_restraint", {}) == "restraint_floor"
    assert condition_exit_owner("bound", {}) == "restraint_floor"
    assert condition_exit_owner("physical_disguise", {}) == "standing_body"
    assert condition_exit_owner("physical_transformation", {}) \
        == "standing_body"
    assert condition_exit_owner("flooding", {}) is None
    assert condition_exit_owner("", {}) is None


def test_active_condition_rows_returns_every_live_row_with_its_payload(
        temp_db):
    cid = _make_chat(temp_db)
    for n, active in (("a", 1), ("b", 1), ("c", 0)):
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,"
            "kind,started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (n, cid, "Mara", "flooding", {"a": 20.0, "b": 10.0,
                                          "c": 0.0}[n],
             None, None, json.dumps({"severity": 0.5}), active),
        )
    rows = active_condition_rows(cid)
    assert [r["condition_id"] for r in rows] == ["b", "a"]   # story's order
    assert rows[0]["payload"]["severity"] == 0.5
    assert rows[0]["subject"] == "Mara"


def test_the_conditions_view_shows_every_live_row_and_who_owns_its_exit(
        temp_db):
    """The Director has never once ended an awareness condition in real
    play, and the WAKING block's first reason was that it was never shown
    one. This is that reason generalized to the whole table: 360 active rows
    with no expiry, none of whose ids any payload carried."""
    from agents.director import _conditions_view

    cid = _make_chat(temp_db)
    rows = [("flood", "flooding", 0.0, None,
             {"tick_interval_seconds": 15, "last_asserted_turn_idx": 4}),
            ("nap", "awareness", 10.0, None, {"state": {"level": "asleep"}}),
            ("flare", "fire", 20.0, 900.0, {})]
    for condition_id, kind, started, expires, payload in rows:
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,"
            "kind,started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (condition_id, cid, "Mara", kind, started, expires, None,
             json.dumps(payload), 1),
        )

    view = _conditions_view(cid, {"elapsed_seconds": 800.0}, turn_idx=12)
    by_id = {row["condition_id"]: row for row in view}
    assert set(by_id) == {"flood", "nap", "flare"}
    assert by_id["flood"]["expires_in_seconds"] is None
    assert by_id["flood"]["tick_interval_seconds"] == 15
    assert by_id["flood"]["last_asserted_turns_ago"] == 8
    assert by_id["flood"]["exit_owner"] is None
    assert by_id["nap"]["exit_owner"] == "awareness_floor"
    assert by_id["flare"]["expires_in_seconds"] == 100.0
    assert by_id["flare"]["age_seconds"] == 780


def test_the_body_specialist_is_the_hand_that_sees_the_conditions_ledger(
        temp_db):
    """`director_scopes` gives the `conditions` channel to `body`, so it is
    the hand that must re-assert or end a row -- and the only one entitled to
    the ledger."""
    from types import SimpleNamespace

    from agents import director

    cid = _make_chat(temp_db)
    view = {"source": "resolved_beat", "player": "Mara", "cast": [],
            "declared_actions": [], "dice": {}, "prose": "Water rises.",
            "dialogue": [], "manifest": []}
    extras = {"active_conditions": [{"condition_id": "flood"}]}
    ctx = SimpleNamespace(chat={"id": cid})

    body = director._specialist_payload("body", ctx, _scene(), view, extras)
    assert body["active_conditions"] == [{"condition_id": "flood"}]
    spatial = director._specialist_payload("spatial", ctx, _scene(), view,
                                           extras)
    assert "active_conditions" not in spatial
