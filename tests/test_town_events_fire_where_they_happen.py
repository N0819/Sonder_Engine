"""A town event happens in the town, and lands in front of whoever is there.

The charter is one per era (`db.ERA_WORLD_KEYS`), but its events were stamped
with the frame whose commit ticked it, and each fired only in that frame.
Measured on the playerless Aldermill runs (2026-09-23): the same two events
fired once in each bubble, and Sal's frame recorded a mill-floor event while
she stood in the market square. A town event now fires in the frame whose
people are standing where it happens, on that frame's clock; nobody there, it
is the era's record.

And a place's generated past is history, never due: every presimulated row
was due at or before the story's first second, so each one fired at the
opening commit as though it happened then -- 179 to 373 rows per chat, and
134 to 278 "witnessings" of events up to thirty days old (the owner's chats
115, 122, 123, 150-153).
"""
import json
import time

from core.db import q, wget_for_frame, wset_for_frame
from core.frames import create_frame
from world.charter_runtime import _scheduled_row, land_presim
from world.mechanics import _fire_due_events

EVENT = {"kind": "upkeep_out_of_band", "upkeep": "sluice", "place": "mill_race",
         "at_hours": 2.0}


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Aldermill", "", time.time()))


def _bubbles(db):
    cid = _chat(db)
    emory = create_frame(cid, label="Emory", ordinal=0, kind="spatial",
                         split_turn_idx=1)
    sal = create_frame(cid, label="Sal", ordinal=0, kind="spatial",
                       split_turn_idx=2)
    return cid, emory, sal


class TestTheEventIsTheTowns:
    def test_a_bubbles_tick_mints_the_row_the_present_would(self, temp_db):
        cid, emory, sal = _bubbles(temp_db)
        present = _scheduled_row(cid, None, 3, "e7", "mill", EVENT, 100.0)
        for frame in (emory, sal):
            row = _scheduled_row(cid, frame, 3, "e7", "mill", EVENT, 100.0)
            assert row["event_id"] == present["event_id"]
            assert json.loads(row["payload"])["frame_id"] is None

    def test_another_era_keeps_its_own_stamp(self, temp_db):
        cid = _chat(temp_db)
        past = create_frame(cid, label="Before", ordinal=-1, kind="past")
        row = _scheduled_row(cid, past, 3, "e7", "mill", EVENT, 100.0)
        assert json.loads(row["payload"])["frame_id"] == past


class TestAPlacesPastIsHistory:
    def test_presimulated_rows_land_as_history(self, temp_db):
        cid = _chat(temp_db)
        land_presim(cid, None, {"items": {}}, [dict(EVENT, charter="mill")],
                    now_seconds=0.0)
        rows = q("SELECT status, seed FROM scheduled_events WHERE chat_id=?",
                 (cid,))
        assert [(r["status"], r["seed"]) for r in rows] == [
            ("history", "charter:mill:presim")]

    def test_the_migration_retires_pending_presim_and_keeps_what_fired(self, temp_db):
        from core import db
        cid = _chat(temp_db)
        for event_id, seed, status in (("a", "charter:mill:presim", "pending"),
                                       ("b", "charter:mill:presim", "fired"),
                                       ("c", "charter:mill:e7", "pending")):
            temp_db.qi(
                "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
                "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
                (event_id, cid, 0.0, "consequence", "mill_race", "{}", seed,
                 status))
        for stmt in db.MIGRATIONS[39]:
            temp_db.qi(stmt)
        got = {r["event_id"]: r["status"] for r in q(
            "SELECT event_id, status FROM scheduled_events WHERE chat_id=?",
            (cid,))}
        assert got == {"a": "history", "b": "fired", "c": "pending"}


def _row(event_id, where, *, stamp=None, due=10.0, seed="charter:mill:e7"):
    return {"event_id": event_id, "kind": "consequence", "due_at": due,
            "seed": seed, "location_id": where,
            "payload": json.dumps({"frame_id": stamp, "where": where,
                                   "what": "the sluice fails", "base_turn": 0})}


EMORY, SAL = 1, 2
TOWN = {"frames": {None, EMORY, SAL}, "claims": {"mill_race": EMORY},
        "root": None}


def _fire(frame, rows, *, town=TOWN, presence_rooms=()):
    ops, notices, _counts, _ids = _fire_due_events(
        {}, 60.0, frame, rows, turn_idx=5, town=town,
        presence_rooms=presence_rooms)
    return ops, notices


class TestItLandsWhereSomebodyStands:
    def test_it_fires_in_front_of_the_people_standing_there(self):
        ops, notices = _fire(EMORY, [_row("e", "mill_race")],
                             presence_rooms={"mill_race"})
        assert ops == [("status", "e", "fired")]
        assert notices and "the sluice fails" in notices[0]

    def test_another_frames_room_is_left_for_that_frame(self):
        assert _fire(SAL, [_row("e", "mill_race")]) == ([], [])

    def test_nobody_there_it_is_the_eras_record_and_nobody_is_told(self):
        ops, notices = _fire(SAL, [_row("e", "weir")],
                             presence_rooms={"weir"})
        assert ops == [("status", "e", "fired"), ("record_in", "e", None)]
        assert notices == []

    def test_a_row_a_bubble_stamped_before_the_era_did_still_comes_due(self):
        ops, _ = _fire(EMORY, [_row("e", "mill_race", stamp=SAL)])
        assert ops == [("status", "e", "fired")]

    def test_not_yet_due_is_not_fired(self):
        assert _fire(EMORY, [_row("e", "mill_race", due=90.0)]) == ([], [])

    def test_a_directors_fuse_stays_the_frames_own(self):
        fuse = _row("f", "mill_race", stamp=SAL, seed="living_world:t3")
        assert _fire(EMORY, [fuse]) == ([], [])

    def test_a_one_frame_story_keeps_the_frame_rule(self):
        assert _fire(SAL, [_row("e", "mill_race")], town=None) == ([], [])
        ops, _ = _fire(None, [_row("e", "mill_race")], town=None)
        assert ops == [("status", "e", "fired")]


ROOMS = {"mill_race": {"adjacent": [{"to": "mill_floor", "barrier": "open"}]},
         "mill_floor": {"adjacent": [{"to": "mill_race", "barrier": "open"},
                                     {"to": "market", "barrier": "open"}]},
         "market": {"adjacent": [{"to": "mill_floor", "barrier": "open"}]},
         "weir": {"adjacent": []}}


class TestWhoStandsWhere:
    def test_a_one_frame_story_reads_nothing_more(self, temp_db):
        from persist.commit import town_for_sweep
        assert town_for_sweep(_chat(temp_db), None, {"rooms": ROOMS}) is None

    def test_each_rooms_claimant_the_committing_frame_first(self, temp_db, monkeypatch):
        from persist.commit import town_for_sweep
        from world import spatial_bubbles
        cid, emory, sal = _bubbles(temp_db)
        people = {emory: ["Emory Vane"], sal: ["Sal Weatherby"], None: []}
        monkeypatch.setattr(spatial_bubbles, "frame_body_names",
                            lambda chat_id, frame_id: people[frame_id])
        emory_scene = {"rooms": ROOMS, "positions": {"Emory Vane": "mill_race"}}
        wset_for_frame(cid, "scene", {"rooms": ROOMS, "positions": {
            "Sal Weatherby": "market"}}, sal)
        town = town_for_sweep(cid, emory, emory_scene)
        assert town["frames"] == {None, emory, sal} and town["root"] is None
        assert town["claims"]["mill_race"] == emory
        assert town["claims"]["mill_floor"] == emory     # both attend it; this commit's
        assert town["claims"]["market"] == sal
        assert "weir" not in town["claims"]
        assert town["presence_rooms"] == {"mill_race"}


class TestEachFrameHasItsOwnNotices:
    def test_a_bubbles_notices_do_not_overwrite_the_presents(self, temp_db):
        cid, emory, _sal = _bubbles(temp_db)
        wset_for_frame(cid, "engine_notices", ["the present's"], None)
        wset_for_frame(cid, "engine_notices", ["Emory's"], emory)
        assert wget_for_frame(cid, "engine_notices", None) == ["the present's"]
        assert wget_for_frame(cid, "engine_notices", emory) == ["Emory's"]


class TestTheRecordIsWhereItWasRecorded:
    def test_the_spine_writes_the_event_under_its_own_frame(self, temp_db):
        import types
        from persist.commit import commit_world_event_spine
        cid, emory, _sal = _bubbles(temp_db)
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, 4, "", time.time(), emory))
        ctx = types.SimpleNamespace(
            chat=types.SimpleNamespace(id=cid),
            turn=types.SimpleNamespace(id=turn_id, frame_id=emory))
        from core.db import transaction
        fired = {"event_id": "e", "kind": "consequence", "location_id": "weir",
                 "occurred_at": 10.0, "payload": "{}", "seed": "charter:mill:e7"}
        with transaction():          # as commit_all runs it
            commit_world_event_spine(ctx, {"fired_events": [
                dict(fired, frame_id=None),
                dict(fired, event_id="f", location_id="mill_race")]})
        got = {json.loads(r["payload"])["source_event_id"]: r["frame_id"]
               for r in q("SELECT payload, frame_id FROM world_events "
                          "WHERE chat_id=?", (cid,))}
        assert got == {"e": None, "f": emory}
