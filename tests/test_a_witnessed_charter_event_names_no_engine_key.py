"""What a bystander takes away from a town's event is what a bystander saw.

`_scheduled_row` put `_event_surface(event)` -- built from the event's body
KEYS -- on the objective carrier rail as `witnessed`, and `story.carriers`
stores that string verbatim as the claim of every cast member standing in the
room: "warden:0001 caused harm to cook:0003", or, with an authored registry
keyed by name, "ilse gave aid to raul" -- a name the cast member learned
through no channel (audit world_charter_core F2). The same class
`carrier_entries` already fixed for charter-held news. The surface is now
built in the words anyone in the room could use (the body's post, never its
key or its name), and the parties ride beside it as structured refs for a
reader that knows whom it is rendering for."""
import json
import time

from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import advance_snapshot, normalize_registry


def _state():
    state = normalize_charter({
        "key": "chapel",
        "upkeeps": {}, "posts": {
            "warden": {"place": "nave", "serves": [], "requires": {}},
            "cook": {"place": "kitchen", "serves": [], "requires": {}}},
        "bodies": {"ilse": {"place": "nave", "name": "Ilse Varn",
                            "home_post": "warden"},
                   "raul": {"place": "nave", "name": "Raul Ferro",
                            "home_post": "cook"}}})
    state["roster"] = seed_roster(state["bodies"])
    state["needs"] = seed_needs(state["bodies"])
    state["carried_events"] = [{
        "kind": "aid_given", "at_hours": 0.5, "place": "nave",
        "about": "ilse", "actor": "ilse", "body": "ilse",
        "subject": "raul"}]
    return state


def test_the_witnessed_surface_carries_no_key_and_no_unmet_name(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Chapel", "", time.time()))
    registry = normalize_registry({"items": {"chapel": {
        "state": _state(), "last_elapsed_seconds": 0.0,
        "window_hours": 1.0}}})
    _after, rows, _produced = advance_snapshot(
        registry, elapsed_seconds=3600.0, epoch_id="beat-1", base_turn=1,
        cid=cid, frame_id=None)
    aid = [json.loads(row["payload"]) for row in rows
           if json.loads(row["payload"])["charter_event"]["kind"]
           == "aid_given"]
    assert aid, "the carried act is scheduled"
    witnessed = aid[0]["witnessed"]
    assert witnessed
    for spelling in ("ilse", "raul", "Ilse", "Raul", "Varn", "Ferro"):
        assert spelling not in witnessed, witnessed
    parties = aid[0].get("parties") or {}
    assert parties.get("actor") == {"charter": "chapel", "body": "ilse"}
    assert parties.get("toward") == {"charter": "chapel", "body": "raul"}
