"""A location generated mid-story lands at the story's own instant.

`presim_registry` stamped every institution it lived `last_elapsed_seconds =
0.0`, which is "the story began at this instant" -- true only at turn 0. A
location added halfway through a story (`generate_lived_location` from
Dialogue Config or the lorebook workspace, or a planner `presimulate` package)
then had the whole story's elapsed time to re-live on its first beat:
reproduced, a town landed after 50 h of story advanced +50.02 h on one
60-second beat and fired its history as pending events (audit
world_charter_core F4). Landing stamps the clock it lands at; the history
rows are dated against each institution's OWN end clock."""
import json
import time

from charter_worlds import small_town
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import (advance_snapshot, land_presim,
                                   normalize_registry, presim_registry,
                                   registry_for)


def _town():
    town = normalize_charter(small_town())
    town["roster"] = seed_roster(town["bodies"])
    town["needs"] = seed_needs(town["bodies"])
    return town


def test_a_town_landed_at_fifty_hours_lives_only_the_next_beat(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Late town", "", time.time()))
    story_now = 50 * 3600.0
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": story_now})
    generated = normalize_registry({"items": {"town": {
        "state": _town(), "window_hours": 4.0}}})
    lived, events = presim_registry(generated, horizon_hours=24.0,
                                    active_tail_hours=0.0)
    landed = land_presim(cid, None, lived, events, now_seconds=story_now)
    assert landed.get("reason") is None
    stored = registry_for(cid)
    assert stored["items"]["town"]["last_elapsed_seconds"] == story_now
    before = float(stored["items"]["town"]["state"]["clock_hours"])
    after, rows, _produced = advance_snapshot(
        stored, elapsed_seconds=story_now + 60.0, epoch_id="beat-1",
        base_turn=1, cid=cid, frame_id=None)
    lived_hours = float(after["items"]["town"]["state"]["clock_hours"]) \
        - before
    assert lived_hours < 0.1, lived_hours
    for row in temp_db.q("SELECT due_at, status FROM scheduled_events "
                         "WHERE chat_id=?", (cid,)):
        if row["status"] == "pending":
            assert float(row["due_at"]) >= story_now


def test_landing_reads_the_story_clock_when_not_told_it(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Late town", "", time.time()))
    story_now = 7 * 3600.0
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": story_now})
    generated = normalize_registry({"items": {"town": {
        "state": _town(), "window_hours": 4.0}}})
    lived, events = presim_registry(generated, horizon_hours=8.0,
                                    active_tail_hours=0.0)
    land_presim(cid, None, lived, events)
    assert registry_for(cid)["items"]["town"]["last_elapsed_seconds"] \
        == story_now
