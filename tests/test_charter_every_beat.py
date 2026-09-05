"""The Charter advances EVERY BEAT, by that beat's own elapsed time.

Its whole intention is semi-cheap off-screen simulation (owner, 2026-09-05),
and it was not doing it. `schedule_charter_ticks` opened on the epoch's
`opportunity`, and `world/offscreen.epoch_reasons` declares one on exactly
four things: the opening beat, a change of the scene's top-level location, a
crossed in-world HOUR, or a due event. An evening at an inn crosses none of
them -- measured in
`docs/experiments/PLAY_2026_09_05_caravanserai.md` PB12: forty bodies,
fifteen turns, nobody moved at all.

What is separated here is a FREE deterministic walk from PAID off-screen
work. The epoch gate stays exactly where it is for the rungs that cost a
model call (`offscreen.schedule_profile_ticks`, the stochastic and dormant
actor ticks); the walk, which has no provider seam anywhere in its module,
now runs on the beat.
"""
import threading
import time
import types

from core.db import transaction, wget, wset
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import (CHARTER_BUDGET_SECONDS, registry_for,
                                   save_registry)
from world.charter_runtime import schedule_charter_ticks
from world.offscreen import advance_epoch


ROOMS = ["hall", "yard", "stable", "loft", "cellar", "well"]
EDGES = [("hall", "yard"), ("yard", "stable"), ("stable", "loft"),
         ("loft", "cellar"), ("cellar", "well")]


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Every beat", "", time.time()))


def _scene():
    rooms = {name: {"name": name, "adjacent": []} for name in ROOMS}
    for a, b in EDGES:
        rooms[a]["adjacent"].append({"to": b, "barrier": "open_door"})
        rooms[b]["adjacent"].append({"to": a, "barrier": "open_door"})
    return {"location": "caravanserai", "rooms": rooms, "positions": {}}


def _charter(bodies=2):
    """A house with a post at one end and its people asleep at the other.

    `well` is five rooms from `hall`, which at `WALK_ROOMS_PER_HOUR` = 6 is
    fifty minutes of walking -- far enough that no single short beat can
    cover it, which is the point of the accumulation test.
    """
    people = {}
    for index in range(bodies):
        people["body_%d" % index] = {
            "place": "hall", "berth": "hall",
            "competence": {"draw": 1},
        }
    charter = normalize_charter({
        "key": "house",
        "upkeeps": {
            "water": {"place": "well", "level": 1.0, "floor": 0.2,
                      "drift_per_hour": 0.05, "service_per_hour": 1.0},
            # No post serves the thatch, so it only ever drifts: the ledger
            # whose fractions the short-beat test is about.
            "thatch": {"place": "loft", "level": 1.0, "floor": 0.2,
                       "drift_per_hour": 0.4, "service_per_hour": 1.0},
        },
        "posts": {"well_post": {"place": "well", "serves": ["water"],
                                "requires": {"draw": 1}}},
        "bodies": people,
        "priority": ["water", "thatch"],
        "scene": _scene(),
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _seed(db, cid, bodies=2, window_hours=1.0):
    db.wset(cid, "scene", _scene())
    save_registry(cid, {"items": {"house": {
        "state": _charter(bodies), "last_elapsed_seconds": 0.0,
        "window_hours": window_hours,
    }}})


def _ctx(cid, idx):
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(idx=idx, id=idx, frame_id=None))


class _Inline:
    """Run every submitted charter job in the caller's thread, immediately.

    The job path is exercised for real -- `_produce` reads its own registry
    copy and lands it -- so idempotence and the landing guards are tested,
    not stubbed out.
    """

    def __init__(self, monkeypatch):
        self.keys = []
        self.results = []
        monkeypatch.setattr("world.charter_runtime.jobs.submit", self)
        monkeypatch.setattr("world.charter_runtime.jobs.status",
                            lambda cid, key: "absent")

    def __call__(self, chat_id, key, fn, base_turn=None):
        self.keys.append(key)
        job = types.SimpleNamespace(cancelled=threading.Event())
        self.results.append(fn(job))
        return job


def _beat(db, cid, idx, *, from_seconds, to_seconds, location="caravanserai",
          previous_location=None, mode=None):
    """One committed beat: the epoch domain, then the charter schedule.

    Exactly the order `persist/commit.py` runs them in -- `advance_epoch`
    inside the transaction, `schedule_charter_ticks` on its result after.
    """
    db.qi("INSERT OR IGNORE INTO turns(chat_id,idx,player_input,created,"
          "frame_id) VALUES(?,?,?,?,?)", (cid, idx, "", time.time(), None))
    scene = dict(_scene(), location=location)
    previous = dict(_scene(),
                    location=previous_location or location)
    diff = {"time": {"mode": mode}} if mode else {}
    prepared = {
        "scene": scene, "prev_scene": previous,
        "prev_clock": {"elapsed_seconds": from_seconds},
        "clock": {"elapsed_seconds": to_seconds},
        "diff": diff,
    }
    with transaction():
        epoch = advance_epoch(_ctx(cid, idx), prepared, {})
    schedule_charter_ticks(_ctx(cid, idx), epoch)
    return epoch


def _clock_hours(cid):
    return registry_for(cid)["items"]["house"]["state"]["clock_hours"]


def _places(cid):
    bodies = registry_for(cid)["items"]["house"]["state"]["bodies"]
    return {key: body["place"] for key, body in sorted(bodies.items())}


# --------------------------------------------------------------- the rule

def test_a_beat_that_crosses_no_hour_advances_the_charter(temp_db,
                                                          monkeypatch):
    cid = _chat(temp_db)
    _seed(temp_db, cid)
    inline = _Inline(monkeypatch)

    # Baseline beat: the registry is seeded at elapsed 0, so the first beat
    # sets the mark. The second is the one that must advance.
    _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=0.0)
    epoch = _beat(temp_db, cid, 2, from_seconds=0.0, to_seconds=120.0)

    assert epoch["reasons"] == [], "no hour, no move: this is not an epoch"
    assert epoch["opportunity"] is False
    assert epoch["charter_scheduled"] is True
    assert _clock_hours(cid) == round(120.0 / 3600.0, 10) or \
        abs(_clock_hours(cid) - 120.0 / 3600.0) < 1e-9


def test_two_beats_advance_twice_by_their_own_elapsed_times(temp_db,
                                                            monkeypatch):
    cid = _chat(temp_db)
    _seed(temp_db, cid)
    inline = _Inline(monkeypatch)

    _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=0.0)
    _beat(temp_db, cid, 2, from_seconds=0.0, to_seconds=120.0)
    after_first = _clock_hours(cid)
    _beat(temp_db, cid, 3, from_seconds=120.0, to_seconds=420.0)

    assert abs(after_first - 120.0 / 3600.0) < 1e-9
    assert abs(_clock_hours(cid) - 420.0 / 3600.0) < 1e-9


def test_rerunning_one_beat_does_not_advance_the_town_twice(temp_db,
                                                            monkeypatch):
    """A reroll or a rerun-from-stage re-commits the same beat. The beat's
    identity is stable over that, so the second pass is refused."""
    cid = _chat(temp_db)
    _seed(temp_db, cid)
    inline = _Inline(monkeypatch)

    _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=0.0)
    first = _beat(temp_db, cid, 2, from_seconds=0.0, to_seconds=120.0)
    advanced_once = _clock_hours(cid)
    again = _beat(temp_db, cid, 2, from_seconds=0.0, to_seconds=120.0)

    assert again["beat_id"] == first["beat_id"]
    assert _clock_hours(cid) == advanced_once


def test_an_hour_crossing_beat_advances_once_not_once_per_trigger(
        temp_db, monkeypatch):
    """A real epoch and a beat coincide constantly -- every hour crossed is
    both. The town advances for the elapsed time, once, because the BEAT is
    what schedules and the epoch only says whether the paid rungs also
    fire."""
    cid = _chat(temp_db)
    _seed(temp_db, cid)
    inline = _Inline(monkeypatch)

    _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=0.0)
    epoch = _beat(temp_db, cid, 2, from_seconds=0.0, to_seconds=3600.0,
                  previous_location="road")

    assert "time" in epoch["reasons"] and "location" in epoch["reasons"]
    assert epoch["opportunity"] is True
    # Once. Two triggers, one hour of simulated time.
    assert abs(_clock_hours(cid) - 1.0) < 1e-9
    assert len([k for k in inline.keys if k.startswith("charter:")]) == 2


def test_fractional_walk_credit_accumulates_into_real_movement(temp_db,
                                                               monkeypatch):
    """A two-minute beat buys a thirtieth of an hour. At six rooms an hour
    that is 0.2 of a room -- below the one-room threshold `charter_move`
    spends at, so it must CARRY. If it floored, a body would never move
    again on short beats however many of them passed."""
    cid = _chat(temp_db)
    _seed(temp_db, cid, bodies=1, window_hours=4.0)
    inline = _Inline(monkeypatch)

    assert _places(cid) == {"body_0": "hall"}
    _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=0.0)
    elapsed = 0.0
    for idx in range(2, 22):           # twenty short beats, 120s each
        _beat(temp_db, cid, idx, from_seconds=elapsed,
              to_seconds=elapsed + 120.0)
        elapsed += 120.0

    walked = _places(cid)["body_0"]
    assert walked != "hall", (
        "twenty two-minute beats is forty minutes of walking; a body that "
        "is still where it started has had its credit floored away")
    travelled = registry_for(cid)["items"]["house"]["state"].get("travelled")
    assert (travelled or {}).get("body_0", 0) >= 3


def test_the_paid_offscreen_rungs_still_wait_for_a_real_epoch(temp_db,
                                                              monkeypatch):
    """The separation, stated as a test: the free walk runs on the beat, the
    rungs that cost a model call keep the epoch gate they were given."""
    from world import offscreen

    cid = _chat(temp_db)
    _seed(temp_db, cid)
    inline = _Inline(monkeypatch)
    temp_db.wset(cid, "dialogue_config", {"offscreen_life": "stochastic"})

    _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=0.0)
    plain = _beat(temp_db, cid, 2, from_seconds=0.0, to_seconds=120.0)
    assert plain["charter_scheduled"] is True
    # The paid rung refuses on the SAME beat the free walk ran on, and it
    # refuses at the epoch gate -- before it ever reaches its own ceiling.
    assert offscreen.schedule_profile_ticks(_ctx(cid, 2), plain) is None
    assert "profile_opportunity" not in plain
    assert plain["stochastic_fired"] == 0

    crossed = _beat(temp_db, cid, 3, from_seconds=120.0, to_seconds=3700.0)
    assert crossed["opportunity"] is True


def test_a_story_with_no_charter_is_untouched(temp_db, monkeypatch):
    """The one refusal that remains, and it must cost nothing: no charter,
    no job, no world row written beyond the beat stamp itself."""
    cid = _chat(temp_db)
    temp_db.wset(cid, "scene", _scene())
    inline = _Inline(monkeypatch)

    epoch = _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=120.0)

    assert inline.keys == []
    assert epoch["charter_skip"] == "no_charters"
    assert registry_for(cid)["items"] == {}


def test_an_untended_ledger_drifts_the_same_in_slices_as_in_one_piece(
        temp_db):
    """The other half of the fractions question, and the one that would be
    the more serious defect: a walk's credit is explicitly carried, but a
    per-hour LEDGER has no carry of its own -- it just has to be linear. If
    any of them rounded per window, half an hour taken in fifteen slices
    would land somewhere else than half an hour taken whole."""
    from world.charter_runtime import advance_snapshot, normalize_registry

    wset(_chat(temp_db), "scene", _scene())

    def _drift(steps):
        cid = _chat(temp_db)
        wset(cid, "scene", _scene())
        registry = normalize_registry({"items": {"house": {
            "state": _charter(1), "last_elapsed_seconds": 0.0,
            "window_hours": 4.0}}})
        for index in range(steps):
            registry, _rows, _p = advance_snapshot(
                registry, elapsed_seconds=1800.0 * (index + 1) / steps,
                epoch_id="slice-%d-%d" % (steps, index), base_turn=1,
                cid=cid, frame_id=None, scene=_scene())
        return registry["items"]["house"]["state"]["upkeeps"]["thatch"][
            "level"]

    whole = _drift(1)
    sliced = _drift(15)

    assert whole < 1.0, "an untended thatch must fall in half an hour"
    assert abs(whole - sliced) < 1e-9, (
        "half an hour in fifteen slices landed at %r, whole at %r: a "
        "per-hour quantity is rounding per window" % (sliced, whole))


# ------------------------------------------------------------- the budget

def test_the_budget_is_named_per_context_and_the_beat_is_the_owners_cap():
    assert CHARTER_BUDGET_SECONDS["beat"] == 10.0
    assert CHARTER_BUDGET_SECONDS["time_skip"] == 60.0
    assert CHARTER_BUDGET_SECONDS["presim"] is None


def test_a_declared_time_skip_takes_the_skip_budget_not_the_beats(
        temp_db, monkeypatch):
    """The context is decided by what the beat IS, never by how much time
    has piled up: an ordinary beat after a long pause is still ordinary."""
    cid = _chat(temp_db)
    _seed(temp_db, cid)
    inline = _Inline(monkeypatch)

    _beat(temp_db, cid, 1, from_seconds=0.0, to_seconds=0.0)
    ordinary = _beat(temp_db, cid, 2, from_seconds=0.0, to_seconds=36000.0)
    assert ordinary["charter_context"] == "beat"
    assert ordinary["charter_budget_seconds"] == 10.0

    declared = _beat(temp_db, cid, 3, from_seconds=36000.0,
                     to_seconds=72000.0, mode="time_skip")
    assert declared["charter_context"] == "time_skip"
    assert declared["charter_budget_seconds"] == 60.0


def test_a_spent_budget_stops_the_walk_without_losing_the_hours(temp_db):
    """When the budget binds, the charters it did not reach keep their own
    `last_elapsed_seconds`, so the next advance sees the whole delta."""
    from world.charter_runtime import advance_snapshot, normalize_registry

    cid = _chat(temp_db)
    registry = normalize_registry({"items": {
        "a": {"state": _charter(1), "last_elapsed_seconds": 0.0,
              "window_hours": 1.0},
        "b": {"state": _charter(1), "last_elapsed_seconds": 0.0,
              "window_hours": 1.0},
    }})
    wset(cid, "scene", _scene())

    advanced, _rows, _produced = advance_snapshot(
        registry, elapsed_seconds=7200.0, epoch_id="beat-x", base_turn=1,
        cid=cid, frame_id=None, scene=_scene(),
        # Already spent: nothing may be begun.
        budget_seconds=1e-9)

    assert [item["last_elapsed_seconds"]
            for item in advanced["items"].values()] == [0.0, 0.0]
    assert all(item["state"]["clock_hours"] == 0.0
               for item in advanced["items"].values())


def test_the_charter_furthest_behind_is_advanced_first(temp_db):
    """Fixed alphabetical order would starve the same institution every beat
    once a budget started biting."""
    from world.charter_runtime import _catchup_order, normalize_registry

    registry = normalize_registry({"items": {
        "aaa": {"state": _charter(1), "last_elapsed_seconds": 3600.0},
        "zzz": {"state": _charter(1), "last_elapsed_seconds": 60.0},
    }})

    assert [key for key, _item in _catchup_order(registry)] == ["zzz", "aaa"]


def test_a_beat_stamp_rides_the_row_the_epoch_already_travelled_in(temp_db):
    """No new persistent field: the beat's identity is stamped on the
    frame-scoped `offscreen_epoch` row, which the checkpoint, branch remap
    and portable archive already carry."""
    cid = _chat(temp_db)
    _seed(temp_db, cid)

    with transaction():
        advance_epoch(_ctx(cid, 4), {
            "scene": _scene(), "prev_scene": _scene(),
            "prev_clock": {"elapsed_seconds": 0.0},
            "clock": {"elapsed_seconds": 120.0},
        }, {})

    stored = wget(cid, "offscreen_epoch", {})
    assert stored["beat_id"].startswith("beat_")
    assert stored["beat_elapsed_seconds"] == 120.0
    assert stored["beat_context"] == "beat"
