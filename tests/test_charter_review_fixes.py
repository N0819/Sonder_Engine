"""Review 2026-09-07 A12/A13/A25: a comm reaches the one body its address
resolves to, a continued walk is priced like a dispatched one, and a
generated need names the upkeep that feeds it.
"""
from world.charter_needs import needs_template
from world.charter_observe import body_receives_evidence


def test_sustenance_draws_on_the_upkeep_that_makes_what_the_town_eats():
    template = needs_template(None, {"bake": {}, "forge": {}}, {"flows": {
        "f1": {"good": "bread", "kind": "produce", "lots_per_hour": 1,
               "requires_upkeep": "bake"},
        "f2": {"good": "bread", "kind": "consume", "lots_per_hour": 2},
        "f3": {"good": "nails", "kind": "produce", "lots_per_hour": 1,
               "requires_upkeep": "forge"},
    }})
    assert template["sustenance"]["fed_by"] == "bake"
    assert template["health"].get("fed_by", "") == ""
    authored = needs_template({"health": {"fed_by": "infirmary"}}, {}, {})
    assert authored["health"]["fed_by"] == "infirmary"
    assert needs_template(None, {}, {})["sustenance"].get("fed_by", "") == ""


def test_a_comm_is_delivered_to_its_resolved_endpoint_and_to_nobody_else():
    scene = {"rooms": {"tower": {"adjacent": []}, "yard": {"adjacent": []}},
             "positions": {"actor": "yard", "b1": "tower", "b2": "tower"}}
    line = {"kind": "speech", "actor": "actor", "medium": "comm",
            "target": "Lieutenant", "volume": "normal", "exact_quote": "Report."}
    body = {"place": "tower", "name": "Lieutenant Venn"}
    # No resolved endpoint: the title alone is not an address.
    assert not body_receives_evidence(scene, "b1", body, (), {}, line)
    assert body_receives_evidence(scene, "b1", body, (), {}, line,
                                  comm_endpoint="b1")
    assert not body_receives_evidence(scene, "b2", dict(body, name="Lieutenant Ash"),
                                      (), {}, line, comm_endpoint="b1")


def test_a_continued_walk_is_priced_by_the_doorway_not_the_flat_room():
    from world.charter_move import continue_walks
    scene = {"rooms": {
        "a": {"adjacent": [{"to": "b", "barrier": "open", "distance": "adjacent"}]},
        "b": {"adjacent": [{"to": "a", "barrier": "open", "distance": "adjacent"},
                           {"to": "c", "barrier": "open", "distance": "adjacent"}]},
        "c": {"adjacent": [{"to": "b", "barrier": "open", "distance": "adjacent"}]},
    }, "positions": {}}
    bodies = {"w": {"place": "a", "available": True,
                    "walk": {"route": ["a", "b", "c"], "leg": 0, "credit": 0.0}}}
    flat, _t, _w = continue_walks(dict(bodies), 0.02)            # 72 seconds
    priced, _t, _w = continue_walks(dict(bodies), 0.02, scene=scene)
    assert flat["w"]["place"] == "a", "the flat price is ten minutes a doorway"
    assert priced["w"]["place"] in ("b", "c"), "a doorway costs its seconds"
