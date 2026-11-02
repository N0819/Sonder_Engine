"""Every writer of a charter body's room leaves the old room behind.

A station names an anchor or a cell of ONE room; a walk and the errand riding
it are a route from where the body WAS. `charter_move._advance` and
`place_body` cleared them on a room change, and the other writers did not:
after a Writers' Room `move_body` the old room's cell was snapped onto the new
room's grid (`charter_place` rule i) and a stale errand rode on (audit
world_charter_behaviours F13, measured: `{'place': 'cellar', 'station':
{'cell': [7, 2]}, 'errand': {'to': 'yard'}}`). One helper,
`charter_move.set_place`, is the room's writer for every fiat move."""
from world.charter import normalize_charter
from world.charter_enrol import depart_guests
from world.charter_harm import apply_harm
from world.charter_intervene import apply_due
from world.charter_runtime import sync_minds_to_scene, transfer_person
from world.charter_surgery import move_body


def _walker(**extra):
    return dict({"place": "yard", "berth": "yard",
                 "station": {"cell": [7, 2]},
                 "walk": {"target": "gate", "route": ["yard", "gate"],
                          "leg": 0, "credit": 0.0, "held": False},
                 "errand": {"to": "gate", "purpose": "fetch the warden"}},
                **extra)


def _left_behind(body):
    return [field for field in ("station", "walk", "errand")
            if body.get(field)]


def _charter(**body):
    return normalize_charter({
        "key": "inn", "upkeeps": {}, "posts": {},
        "scene": {"rooms": {"yard": {"name": "Yard", "adjacent": [
            {"to": "gate"}, {"to": "cellar"}]},
            "gate": {"name": "Gate", "adjacent": [{"to": "yard"}]},
            "cellar": {"name": "Cellar", "adjacent": [{"to": "yard"}]}}},
        "bodies": {"tam": _walker(**body)}})


def test_the_helper_drops_station_walk_and_errand_on_a_room_change():
    from world.charter_move import set_place
    body = _walker()
    set_place(body, "cellar")
    assert body["place"] == "cellar" and _left_behind(body) == []


def test_an_authored_move_leaves_the_old_room_behind():
    charter = _charter()
    move_body(charter, body="tam", room="cellar")
    assert _left_behind(charter["bodies"]["tam"]) == []


def test_a_lair_relocation_leaves_the_old_room_behind():
    charter = _charter()
    charter["interventions"] = [{"id": "r", "op": "relocate", "to": "cellar",
                                 "at_hours": 0.0}]
    charter, _events = apply_due(charter, 1.0)
    body = charter["bodies"]["tam"]
    assert body["place"] == "cellar" and _left_behind(body) == []


def test_a_body_gone_missing_leaves_its_room_behind():
    charter = _charter()
    charter, _events = apply_harm(charter, "tam", by="wolf", at_hours=1.0,
                                  outcome="missing")
    assert _left_behind(charter["bodies"]["tam"]) == []


def test_a_departed_guest_leaves_its_room_behind():
    charter = _charter(guest=True, guest_until=1.0)
    charter, departed = depart_guests(charter, 2.0)
    assert departed == ["tam"]
    assert _left_behind(charter["bodies"]["tam"]) == []


def test_a_bound_body_following_the_scene_leaves_the_old_room_behind():
    charter = _charter()
    charter["bindings"] = {"tam": {"char_id": 1, "name": "Tam"}}
    sync_minds_to_scene(charter, {"rooms": charter["scene"]["rooms"],
                                  "positions": {"Tam": "cellar"}}, "inn")
    body = charter["bodies"]["tam"]
    assert body["place"] == "cellar" and _left_behind(body) == []


def test_a_transfer_with_a_place_leaves_the_old_room_behind():
    registry = {"items": {"inn": {"state": _charter()},
                          "mill": {"state": normalize_charter(
                              {"key": "mill", "upkeeps": {}, "posts": {},
                               "bodies": {}})}}}
    transfer_person(registry, "tam", "mill", place="cellar")
    body = registry["items"]["mill"]["state"]["bodies"]["tam"]
    assert body["place"] == "cellar" and _left_behind(body) == []
