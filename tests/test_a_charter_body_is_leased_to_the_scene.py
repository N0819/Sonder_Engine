"""A charter body the scene stands is on loan while it is in the aperture.

Owner's rule (2026-09-14): a charter body moves seamlessly from being
animated on screen by a model to being handled by the charter off screen,
and owning its position outright would make beat-scale motion rigid. So:
in the aperture the scene keeps the row, the registry mirrors the room and
the runtime keeps its hands off; outside it the room goes back to the
charter and the scene lets go.
"""
from world.charter import normalize_charter
from world.charter_move import place_body, walk
from world.charter_place import lease_scene_bodies


def _registry():
    inn = normalize_charter({
        "key": "inn",
        "upkeeps": {"custom": {"place": "taproom", "level": 1.0, "floor": 0.2,
                               "drift_per_hour": 0.0, "service_per_hour": 1.0}},
        "posts": {"keep": {"place": "taproom", "serves": ["custom"],
                           "requires": {"keep": 1}}},
        "bodies": {"tam": {"place": "taproom", "name": "Tam",
                           "competence": {"keep": 1}}},
        "priority": ["custom"],
    })
    return {"items": {"inn": {"state": inn}}}


def _scene(room):
    return {"rooms": {"taproom": {"name": "Taproom", "adjacent": []},
                      "yard": {"name": "Yard", "adjacent": []},
                      "lane": {"name": "Lane", "adjacent": []}},
            "entities": {"inn_keeper": {"name": "Tam", "kind": "person",
                                        "charter_ref": {"charter": "inn",
                                                        "body": "tam"}},
                         "lamp": {"name": "a lamp", "kind": "thing"}},
            "positions": {"inn_keeper": room, "lamp": "taproom"},
            "stations": {"inn_keeper": {"at": "bar"}}, "poses": {},
            "orientation": {}}


class TestTheLeaseDecision:
    def test_in_the_aperture_the_scene_keeps_it_and_the_registry_mirrors(self):
        out = lease_scene_bodies(_registry(), _scene("yard"), {"taproom", "yard"})
        assert out == {"moves": [{"charter": "inn", "body": "tam",
                                  "name": "inn_keeper", "room": "yard",
                                  "leased": True}],
                       "released": []}

    def test_outside_it_the_body_goes_back_to_the_charter(self):
        out = lease_scene_bodies(_registry(), _scene("lane"), {"taproom", "yard"})
        assert out["moves"] == [{"charter": "inn", "body": "tam",
                                 "name": "inn_keeper", "room": "lane",
                                 "leased": False}]
        assert out["released"] == ["inn_keeper"]

    def test_a_thing_and_an_unplaced_body_are_left_alone(self):
        sc = _scene("yard")
        sc["positions"].pop("inn_keeper")
        assert lease_scene_bodies(_registry(), sc, {"taproom"}) == {
            "moves": [], "released": []}

    def test_a_body_the_registry_no_longer_holds_is_left_alone(self):
        reg = _registry()
        reg["items"]["inn"]["state"]["bodies"] = {}
        assert lease_scene_bodies(reg, _scene("lane"), {"taproom"}) == {
            "moves": [], "released": []}


class TestTheRuntimeHonoursTheLease:
    def test_the_placer_sets_and_clears_the_flag(self):
        reg = _registry()
        place_body(reg, "inn", "tam", "yard", leased=True)
        body = reg["items"]["inn"]["state"]["bodies"]["tam"]
        assert body["place"] == "yard" and body["leased"] is True
        place_body(reg, "inn", "tam", "lane", leased=False)
        assert body["place"] == "lane" and "leased" not in body
        place_body(reg, "inn", "tam", "taproom")
        assert body["place"] == "taproom" and "leased" not in body

    def test_a_leased_body_is_not_walked(self):
        bodies = {"tam": {"key": "tam", "place": "yard", "available": True,
                          "leased": True},
                  "wat": {"key": "wat", "place": "yard", "available": True}}
        moved, _travelled, _walked = walk(bodies, {"tam": "lane", "wat": "lane"},
                                          None, hours=4.0)
        assert "walk" not in moved["tam"] and moved["tam"]["place"] == "yard"
        assert moved["wat"]["place"] == "lane" or moved["wat"].get("walk")

    def test_the_flag_survives_the_write_chokepoint(self):
        state = normalize_charter({
            "key": "inn", "upkeeps": {}, "posts": {},
            "bodies": {"tam": {"place": "yard", "leased": True},
                       "wat": {"place": "yard"}}})
        assert state["bodies"]["tam"]["leased"] is True
        assert "leased" not in state["bodies"]["wat"]
