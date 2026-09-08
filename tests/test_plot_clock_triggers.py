"""A package clock that advances on what HAPPENED, not on the calendar
(D15, review 2026-09-07; owner ruling 2026-09-08).

THE CLASS. A consequence that arrives because two turns passed is a
calendar; a consequence that arrives because the world wrote three events of
a kind, in a place, is a story. A clock may now carry `segments` and
`advance_on`, and it ticks on `world_events.kind` -- the ONE vocabulary the
world writes, which is why the item was deferred: keyed on the wrong one a
clock never ticks and never says so. So every path here also asserts that
the engine SAYS SO -- at validation, in the projection the panel reads, and
in the Room's contradiction lint.
"""
from __future__ import annotations

import json
import time

from story.plot_packages import (draft_operation, edit_package,
                                 fire_due_clocks, get_package, new_package,
                                 package_projection, preview_package,
                                 publish_package, validate_package,
                                 world_event_kinds)

PLAYER = "Wren Ashby"


def _scene():
    def room(name, *exits):
        return {"name": name, "desc": name + ".",
                "adjacent": [{"to": e, "barrier": "open_door"} for e in exits]}
    return {"location": "Port", "rooms": {
        "quay": room("Quay", "warehouse"),
        "warehouse": room("Warehouse", "quay"),
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}}


def _story(db, *, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Triggers", "A port at dusk.", time.time()))
    db.wset(cid, "scene", _scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    ids = [db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, i, "", time.time()))
           for i in range(turns)]
    return cid, ids


def _turn(db, cid, idx):
    return db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, idx, "", time.time()))


def _event(db, cid, turn_id, kind, *, room="", at=0.0):
    """One objective event, written exactly as
    `commit_mechanics.commit_world_event_spine` writes it."""
    eid = "we:%s:%s:%s" % (kind, room, time.time_ns())
    db.qi("INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,"
          "occurred_at,duration_seconds,kind,location_id,payload,seed,"
          "committed) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (eid, cid, turn_id, None, at, 0.0, kind, room,
           json.dumps({"what": "something happened"}), None, time.time()))
    return eid


def _pkg(cid, clocks, ops):
    pkg = new_package(cid, title="The Tide Turns", premise="p")
    edit_package(cid, pkg["uid"], {"clocks": clocks})
    for op in ops:
        draft_operation(cid, pkg["uid"], op)
    return pkg["uid"]


def _publish(cid, uid):
    validate_package(cid, uid)
    return publish_package(cid, uid,
                           expected_revision=get_package(cid, uid)["revision"])


def _clock(cid, uid):
    return get_package(cid, uid)["clocks"][0]


# ---------------------------------------------------------------------------
# The shape survives the store
# ---------------------------------------------------------------------------

def test_a_trigger_is_not_flattened_by_normalisation(temp_db):
    cid, _ = _story(temp_db)
    uid = _pkg(cid, [{"id": "c1", "label": "suspicion", "segments": 3,
                      "advance_on": [{"event_kind": "consequence",
                                      "location_id": "quay"}]}], [])
    clock = _clock(cid, uid)
    assert clock["advance_on"] == [{"event_kind": "consequence",
                                    "location_id": "quay"}]
    assert clock["segments"] == 3 and clock["filled"] == 0
    # And a clock that names no trigger carries none of the machinery.
    other = _pkg(cid, [{"id": "c2", "due_turns": 2}], [])
    assert "advance_on" not in _clock(cid, other)


# ---------------------------------------------------------------------------
# It ticks on what the world wrote
# ---------------------------------------------------------------------------

class TestSegmentsFill:
    def test_a_clock_fires_when_the_world_fills_its_segments(self, temp_db):
        from story.authored_events import due_authored_events
        cid, _turn_ids = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_watch", "label": "the watch notices",
                          "segments": 2,
                          "advance_on": [{"event_kind": "consequence"}]}],
                   [{"op": "scheduled_consequence", "clock": "clock_watch",
                     "summary": "the watch comes to the quay", "room": "quay"}])
        out = _publish(cid, uid)
        assert out["applied"][0]["result"] == {"deferred": "clock_watch"}

        # A beat with no event of the kind: nothing moves.
        t3 = _turn(temp_db, cid, 3)
        _event(temp_db, cid, t3, "transit_arrival", room="quay")
        assert fire_due_clocks(cid, 3, turn_id=t3)["fired"] == []
        assert _clock(cid, uid)["filled"] == 0

        # One matching event: one segment, persisted -- and NOT a history
        # note. The counter is the record; see the HISTORY_CAP test below.
        t4 = _turn(temp_db, cid, 4)
        _event(temp_db, cid, t4, "consequence", room="warehouse")
        result = fire_due_clocks(cid, 4, turn_id=t4)
        assert result["advanced"] == [(uid, "clock_watch", 1)]
        assert result["fired"] == []
        assert _clock(cid, uid)["filled"] == 1
        assert [h["action"] for h in
                get_package(cid, uid)["provenance"]["history"]][-1] \
            == "published"

        # The second fills it, and it fires in the same pass -- the beat's
        # own events are already in `world_events` when the tail runs.
        t5 = _turn(temp_db, cid, 5)
        _event(temp_db, cid, t5, "consequence", room="quay")
        result = fire_due_clocks(cid, 5, turn_id=t5)
        assert result["fired"] == [(uid, "clock_watch")]
        pkg = get_package(cid, uid)
        assert pkg["clocks"][0]["fired_turn"] == 5
        assert pkg["operations"][0]["applied"]
        assert [d["summary"] for d in due_authored_events(cid, 6)] == [
            "the watch comes to the quay (at quay)"]
        # And it does not fire twice.
        assert fire_due_clocks(cid, 6)["fired"] == []

    def test_an_event_is_counted_once_however_often_the_tail_runs(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_c", "segments": 4,
                          "advance_on": [{"event_kind": "consequence"}]}], [])
        _publish(cid, uid)
        t3 = _turn(temp_db, cid, 3)
        _event(temp_db, cid, t3, "consequence", room="quay")
        _event(temp_db, cid, t3, "consequence", room="warehouse")
        assert fire_due_clocks(cid, 3, turn_id=t3)["advanced"] == [
            (uid, "clock_c", 2)]
        # The double call the ruling names: the same beat again counts none.
        assert fire_due_clocks(cid, 3, turn_id=t3)["advanced"] == []
        assert _clock(cid, uid)["filled"] == 2
        # And a later beat does not recount them either.
        t4 = _turn(temp_db, cid, 4)
        assert fire_due_clocks(cid, 4, turn_id=t4)["advanced"] == []
        assert _clock(cid, uid)["filled"] == 2

    def test_a_long_run_of_ticks_does_not_evict_the_authored_record(
            self, temp_db):
        """TICKING IS NOT PROVENANCE (D15 rework, 2026-09-08).

        A clock watching a kind the world writes often advances on nearly
        every beat -- chat 114 wrote 52 `consequence` rows in 14 turns --
        and `HISTORY_CAP` is 40, so a note per tick pushed the package's
        whole authored record (created, edited, validated, published) out
        of `provenance['history']` and left the panel's window showing
        nothing else. The counter is the record; it persists across the
        reload, and the history keeps what a person did.
        """
        from story.plot_packages import HISTORY_CAP
        cid, _ = _story(temp_db)
        beats = HISTORY_CAP + 5
        uid = _pkg(cid, [{"id": "clock_long", "segments": beats + 1,
                          "advance_on": [{"event_kind": "consequence"}]}], [])
        _publish(cid, uid)
        for i in range(beats):
            idx = 3 + i
            tid = _turn(temp_db, cid, idx)
            _event(temp_db, cid, tid, "consequence", room="quay")
            assert fire_due_clocks(cid, idx, turn_id=tid)["advanced"] == [
                (uid, "clock_long", 1)]
        pkg = get_package(cid, uid)
        assert pkg["clocks"][0]["filled"] == beats      # the counter persists
        actions = [h["action"] for h in pkg["provenance"]["history"]]
        assert "published" in actions
        assert len(actions) < HISTORY_CAP

    def test_a_clock_is_never_more_than_full(self, temp_db):
        """Five matching events on one beat against two segments is 2/2, not
        5/2 -- the overshoot says nothing (the clock is due and fires in the
        same pass) and the panel cannot mean it (D15 rework)."""
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_f", "segments": 2,
                          "advance_on": [{"event_kind": "consequence"}]}], [])
        _publish(cid, uid)
        t3 = _turn(temp_db, cid, 3)
        for _ in range(5):
            _event(temp_db, cid, t3, "consequence", room="quay")
        result = fire_due_clocks(cid, 3, turn_id=t3)
        assert result["advanced"] == [(uid, "clock_f", 2)]
        assert result["fired"] == [(uid, "clock_f")]
        clock = _clock(cid, uid)
        assert (clock["filled"], clock["segments"]) == (2, 2)
        shown = package_projection(get_package(cid, uid))["clocks"][0]
        assert (shown["filled"], shown["segments"]) == (2, 2)

    def test_a_located_trigger_counts_only_that_room(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_q", "segments": 2,
                          "advance_on": [{"event_kind": "consequence",
                                          "location_id": "quay"}]}], [])
        _publish(cid, uid)
        t3 = _turn(temp_db, cid, 3)
        _event(temp_db, cid, t3, "consequence", room="warehouse")
        _event(temp_db, cid, t3, "consequence", room="quay")
        assert fire_due_clocks(cid, 3, turn_id=t3)["advanced"] == [
            (uid, "clock_q", 1)]

    def test_events_from_before_the_package_published_do_not_count(self, temp_db):
        cid, turn_ids = _story(temp_db)
        _event(temp_db, cid, turn_ids[0], "consequence", room="quay")
        _event(temp_db, cid, turn_ids[1], "consequence", room="quay")
        uid = _pkg(cid, [{"id": "clock_p", "segments": 1,
                          "advance_on": [{"event_kind": "consequence"}]}], [])
        _publish(cid, uid)   # published at turn 2
        t3 = _turn(temp_db, cid, 3)
        assert fire_due_clocks(cid, 3, turn_id=t3)["fired"] == []
        assert _clock(cid, uid)["filled"] == 0

    def test_a_rewind_past_the_fire_unfills_the_clock(self, temp_db):
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint
        cid, _ = _story(temp_db)
        ensure_checkpoint(cid, 2)
        uid = _pkg(cid, [{"id": "clock_r", "segments": 1,
                          "advance_on": [{"event_kind": "consequence"}]}], [])
        _publish(cid, uid)
        t3 = _turn(temp_db, cid, 3)
        _event(temp_db, cid, t3, "consequence", room="quay")
        assert fire_due_clocks(cid, 3, turn_id=t3)["fired"] == [(uid, "clock_r")]
        restore_checkpoint(cid, 2)
        pkg = get_package(cid, uid)
        assert pkg is None or pkg["status"] == "draft"
        assert world_event_kinds(cid) == {}


# ---------------------------------------------------------------------------
# A clock that never ticks SAYS SO
# ---------------------------------------------------------------------------

class TestItSaysSo:
    def test_a_clock_with_no_due_and_no_trigger_is_refused(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_n", "label": "nothing"}], [])
        assert any("has no due" in e and "advance_on" in e
                   for e in preview_package(cid, uid)["errors"])

    def test_a_trigger_on_something_no_event_records_is_refused(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_a", "segments": 1,
                          "advance_on": [{"event_kind": "consequence",
                                          "actor": "Osric Fell"}]}], [])
        errors = preview_package(cid, uid)["errors"]
        assert any("also names actor" in e for e in errors)

    def test_a_trigger_naming_no_kind_is_refused(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_k", "segments": 1,
                          "advance_on": [{"location_id": "quay"}]}], [])
        assert any("names the event_kind" in e
                   for e in preview_package(cid, uid)["errors"])

    def test_a_kind_this_world_has_never_written_is_warned_about(self, temp_db):
        cid, turn_ids = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_w", "segments": 1,
                          "advance_on": [{"event_kind": "stock_low"}]}], [])
        # A YOUNG WORLD IS NOT EVIDENCE (D15 rework, 2026-09-08). With
        # `world_events` still empty the validator cannot tell this clock
        # from one waiting on the kind the engine writes on every
        # consequence, so it says nothing; what the author gets is the fact
        # itself, an empty `event_kinds`.
        assert not any("never ticks" in w
                       for w in preview_package(cid, uid)["warnings"])
        assert world_event_kinds(cid) == {}
        # Once the world has written something, the warning names it -- the
        # vocabulary is read off the world, never kept as a list here.
        _event(temp_db, cid, turn_ids[1], "consequence", room="quay")
        assert any("never ticks" in w
                   for w in preview_package(cid, uid)["warnings"])
        assert any("'stock_low'" in w and "consequence" in w
                   for w in preview_package(cid, uid)["warnings"])
        assert world_event_kinds(cid) == {"consequence": 1}
        # And a clock on the kind the world does write is not warned about.
        good = _pkg(cid, [{"id": "clock_g", "segments": 1,
                           "advance_on": [{"event_kind": "consequence"}]}], [])
        assert not any("never ticks" in w
                       for w in preview_package(cid, good)["warnings"])

    def test_the_projection_shows_how_far_a_clock_has_got(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_s", "segments": 3,
                          "advance_on": [{"event_kind": "consequence"}]}], [])
        _publish(cid, uid)
        t3 = _turn(temp_db, cid, 3)
        _event(temp_db, cid, t3, "consequence", room="quay")
        fire_due_clocks(cid, 3, turn_id=t3)
        shown = package_projection(get_package(cid, uid))["clocks"][0]
        assert shown["filled"] == 1 and shown["segments"] == 3
        assert shown["advance_on"] == [{"event_kind": "consequence"}]

    def test_the_room_reports_a_clock_waiting_on_an_unwritten_event(self, temp_db):
        from story.room_tools import run_tool
        cid, turn_ids = _story(temp_db)
        _event(temp_db, cid, turn_ids[1], "consequence", room="quay")
        uid = _pkg(cid, [{"id": "clock_u", "segments": 2,
                          "advance_on": [{"event_kind": "harbour_fire"}]}], [])
        _publish(cid, uid)
        rows = run_tool(cid, "inspect_contradictions")["dangling"]
        waiting = [r for r in rows
                   if r["kind"] == "clock_waits_on_unwritten_event"]
        assert waiting == [{"kind": "clock_waits_on_unwritten_event",
                            "package": uid, "clock": "clock_u",
                            "waits_on": ["harbour_fire"], "filled": 0,
                            "segments": 2, "world_writes": ["consequence"]}]
        # The tool that lists events tells the author what to wait on.
        assert run_tool(cid, "inspect_events")["event_kinds"] == {
            "consequence": 1}

    def test_the_room_says_nothing_against_a_world_that_has_written_nothing(
            self, temp_db):
        """The same clock, in a world with no `world_events` row at all: the
        lint is silent, because an empty spine is a young story and not a
        wrong clock (D15 rework). Chat 117 wrote 9 rows across 123 turns, so
        this state persists for dozens of beats at the start of a story."""
        from story.room_tools import run_tool
        cid, _ = _story(temp_db)
        uid = _pkg(cid, [{"id": "clock_y", "segments": 2,
                          "advance_on": [{"event_kind": "harbour_fire"}]}], [])
        _publish(cid, uid)
        rows = run_tool(cid, "inspect_contradictions")["dangling"]
        assert not [r for r in rows
                    if r["kind"] == "clock_waits_on_unwritten_event"]
        assert run_tool(cid, "inspect_events")["event_kinds"] == {}

    def test_a_clock_the_world_can_still_fill_is_not_reported(self, temp_db):
        from story.room_tools import run_tool
        cid, turn_ids = _story(temp_db)
        _event(temp_db, cid, turn_ids[1], "consequence", room="quay")
        uid = _pkg(cid, [{"id": "clock_ok", "segments": 2,
                          "advance_on": [{"event_kind": "consequence"}]}], [])
        _publish(cid, uid)
        rows = run_tool(cid, "inspect_contradictions")["dangling"]
        assert not [r for r in rows
                    if r["kind"] == "clock_waits_on_unwritten_event"]
