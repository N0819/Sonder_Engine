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


class TestOneEntityPerCharterBody:
    """The owner, 2026-09-23: one entity per charter body. Chat 153's
    storekeeper stood as a scene `fixture` beside his own charter body for
    eighteen turns; every move for his name landed on the fixture."""

    def _twin_scene(self):
        sc = _scene("yard")
        sc["entities"].pop("inn_keeper")
        sc["entities"]["tam_fixture"] = {"name": "Tam", "kind": "fixture"}
        sc["positions"] = {"tam_fixture": "lane", "lamp": "taproom"}
        return sc

    def test_a_second_record_of_a_body_is_bound_to_it(self):
        from world.charter_place import heal_unbound_twins
        sc = self._twin_scene()
        healed = heal_unbound_twins(_registry(), sc)
        assert healed == [{"entity_id": "tam_fixture", "charter": "inn",
                           "body": "tam", "name": "Tam"}]
        ent = sc["entities"]["tam_fixture"]
        assert ent["charter_ref"] == {"charter": "inn", "body": "tam"}
        assert ent["kind"] == "person"
        # ...and the lease then governs it: outside the aperture, released.
        out = lease_scene_bodies(_registry(), sc, {"taproom"})
        assert out["released"] == ["tam_fixture"]

    def test_a_body_already_carried_and_an_unrelated_thing_are_left_alone(self):
        from world.charter_place import heal_unbound_twins
        sc = _scene("yard")
        sc["entities"]["tam_fixture"] = {"name": "Tam", "kind": "fixture"}
        assert heal_unbound_twins(_registry(), sc) == []
        assert "charter_ref" not in sc["entities"]["lamp"]
        assert "charter_ref" not in sc["entities"]["tam_fixture"]


def test_a_charter_person_minted_as_a_fixture_binds_to_the_body():
    """Prevention: a hand wrote a charter person as `kind: fixture` out of
    view; the reserved charter figure makes the mint that person."""
    from agents.director import _bind_minted_entities_to_present_figures
    sd = {"entities": {"gushiga_toriki": {"name": "Gushiga Toriki", "kind": "fixture"}},
          "positions": {"gushiga_toriki": "moonlit_beach"}}
    figures = [{"name": "Gushiga Toriki", "aliases": [], "charter": "yonaha_store",
                "body": "storekeeper:0001", "plan": "charter:yonaha_store/storekeeper:0001",
                "kind": "person", "room": "konbini_front", "reserved": True}]
    bindings = _bind_minted_entities_to_present_figures(
        {"entities": {}, "rooms": {}}, sd, figures, fallback_room="moonlit_beach")
    ent = sd["entities"]["gushiga_toriki"]
    assert ent["charter_ref"] == {"charter": "yonaha_store", "body": "storekeeper:0001"}
    assert ent["kind"] == "person" and bindings



def test_a_present_charter_body_in_contact_is_stood_in_the_scene():
    """Playerless Aldermill (2026-09-23): the miller's palm on the sluice lever
    was in the resolve's contact_ops and in no committed scene -- he was laid
    into the working scene only, so the merge dropped his contact."""
    from agents.director import _stand_touching_figures
    sc = {"positions": {"Emory Vane": "sluice_house"}, "entities": {}}
    sd = {"contact_ops": [{"op": "add", "actor": "Master Miller Waerton",
                           "actor_part": "palm", "target": "sluice_lever"}]}
    figs = [{"name": "Master Miller Waerton", "room": "sluice_house",
             "charter": "aldermill", "body": "miller"},
            {"name": "Tam", "room": "yard", "charter": "aldermill", "body": "tam"}]
    assert _stand_touching_figures(
        sc, sd, figs, declared_rooms={"Master Miller Waerton": "mill_race"}
    ) == ["Master Miller Waerton"]
    # Keyed by the name the contact op speaks, so hygiene can place it; and
    # standing where the beat put it, not at its post.
    ent = sd["entities"]["Master Miller Waerton"]
    assert ent["kind"] == "person"
    assert ent["charter_ref"] == {"charter": "aldermill", "body": "miller"}
    assert sd["positions"]["Master Miller Waerton"] == "mill_race"
    # A body the diff already stands is left alone on a second pass.
    assert _stand_touching_figures(sc, sd, figs) == []


def test_a_stood_figures_contact_survives_the_merge():
    """Round 3 (2026-09-23) t7: the stood miller's lever hold was emitted and
    the body stood, and the committed contacts still lacked it."""
    from agents.director import _stand_touching_figures
    from world.spatial import merge_scene_with_diff
    sc = {"rooms": {"sluice_house": {"name": "Sluice House",
                                     "fixtures": ["lever"]}},
          "positions": {"Emory Vane": "sluice_house"}, "entities": {},
          "contacts": []}
    sd = {"contact_ops": [{"op": "add", "actor": "Master Miller Waerton",
                           "actor_part": "hands", "target": "Emory Vane",
                           "target_part": "shoulder", "manner": "grip"}]}
    figs = [{"name": "Master Miller Waerton", "room": "sluice_house",
             "charter": "aldermill", "body": "miller"}]
    _stand_touching_figures(sc, sd, figs)
    merged = merge_scene_with_diff(sc, sd)
    assert any(c.get("actor") == "Master Miller Waerton"
               for c in merged.get("contacts") or [])


def test_one_body_under_two_spellings_gets_one_record():
    """Playerless Aldermill round 5 (2026-09-23): the declarations called a
    mill hand "Miller Robkinet Flourbrooks", the present figures "Robkinet
    Flourbrooks". Keyed by name, the floor either missed him or would have
    stood him twice; keyed by his charter identity, he is one record that
    answers to both."""
    from agents.director import _stand_touching_figures
    ref = {"charter": "aldermill_mill", "body": "mill_hand:0002"}
    figs = [{"name": "Robkinet Flourbrooks", "room": "weir", **ref},
            {"name": "Miller Robkinet Flourbrooks", "room": "weir", **ref}]
    sc = {"positions": {"Emory Vane": "weir"}, "entities": {}}
    sd = {"contact_ops": [
        {"op": "add", "actor": "Miller Robkinet Flourbrooks", "actor_part": "hands",
         "target": "windlass", "manner": "grip"},
        {"op": "add", "actor": "Robkinet Flourbrooks", "actor_part": "boot",
         "target": "windlass", "manner": "press"}]}
    assert _stand_touching_figures(sc, sd, figs) == ["Miller Robkinet Flourbrooks"]
    assert list(sd["entities"]) == ["Miller Robkinet Flourbrooks"]
    record = sd["entities"]["Miller Robkinet Flourbrooks"]
    assert record["charter_ref"] == ref
    assert "Robkinet Flourbrooks" in record["aliases"]
    assert sd["positions"] == {"Miller Robkinet Flourbrooks": "weir"}


def test_a_released_record_is_placed_again_under_its_own_key():
    """The lease strips a released body's rows and keeps its record; coming
    back into view under another spelling, it is placed under that record."""
    from agents.director import _stand_touching_figures
    ref = {"charter": "aldermill_mill", "body": "mill_hand:0002"}
    sc = {"positions": {"Emory Vane": "weir"}, "entities": {
        "Miller Robkinet Flourbrooks": {"name": "Miller Robkinet Flourbrooks",
                                        "kind": "person", "aliases": [],
                                        "charter_ref": ref}}}
    sd = {"contact_ops": [{"op": "add", "actor": "Robkinet Flourbrooks",
                           "actor_part": "hands", "target": "windlass",
                           "manner": "grip"}]}
    figs = [{"name": "Robkinet Flourbrooks", "room": "weir", **ref}]
    _stand_touching_figures(sc, sd, figs)
    assert list(sd["entities"]) == ["Miller Robkinet Flourbrooks"]
    assert sd["positions"] == {"Miller Robkinet Flourbrooks": "weir"}
    assert sd["entities"]["Miller Robkinet Flourbrooks"]["aliases"] == [
        "Robkinet Flourbrooks"]
