"""A scheduled row due on a TURN NUMBER is never windowed on the story
clock.

world_offscreen_time F16 (audit 2026-11-01, assessed): `scheduled_events.
due_at` holds a turn index for `authored_event` rows
(`story.authored_events.mint_authored_events`: `turn_idx + due_in`) and story
seconds for every other kind. The gap's legacy fallback windows fired rows by
`due_at` in SECONDS with no kind filter, so it was saved only by the owner
filters below it -- one owned authored row away from turn 5 reading as five
seconds into the story.
"""

from __future__ import annotations

from tests.test_gaps import _make_chat, _scene
from world.gaps import LAST_SEEN_KEY, gap_for


def test_a_fired_authored_row_is_not_an_event_of_the_window(temp_db):
    cid = _make_chat(temp_db)
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 500.0})
    for event_id, kind in (("authored_t5", "authored_event"),
                           ("arrival", "transit_arrival")):
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            (event_id, cid, 300.0 if kind != "authored_event" else 105.0,
             kind, "hall", "{}", "s", "fired"))
    temp_db.wset(cid, LAST_SEEN_KEY,
                 {"hall": {"turn": 2, "room": "hall", "elapsed_seconds": 100.0}})
    rec = gap_for(cid, "room", "hall", 2, 6, scene=_scene())
    assert [e["event_id"] for e in rec["events"]] == ["arrival"]
