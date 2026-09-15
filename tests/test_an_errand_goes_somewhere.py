"""Where you stand is not where you go.

`charter_move.errands` picked the nearest commons a body could reach, and the
nearest room is the one it is standing in: a crew whose net-loft was itself a
commons was sent to the loft every social phase and never crossed the quay to
the inn the plan said they drank in (scratch play 2026-09-14, chat 7 -- three
evenings, no crew in the taproom, no word carried between the two houses).
An errand's target is never the body's own room.
"""

from world.charter_move import errands


def _town():
    bodies = {"hand": {"place": "net_loft", "available": True}}
    reach = {("hand", "net_loft"): 0, ("hand", "taproom"): 2,
             ("hand", "quay"): 1}
    return bodies, reach


def test_a_body_in_a_commons_goes_to_another_commons_in_the_evening():
    bodies, reach = _town()
    out = errands(bodies, {}, {}, {}, ["quay"], reach, seed=1, rate=1.0,
                  hours=1000.0, commons=["net_loft", "taproom"],
                  phase="evening")
    assert out == {"hand": "taproom"}


def test_a_body_whose_only_commons_is_its_own_room_stays_home():
    bodies, reach = _town()
    out = errands(bodies, {}, {}, {}, ["quay"], reach, seed=1, rate=1.0,
                  hours=1000.0, commons=["net_loft"], phase="evening")
    assert out == {}


def test_the_working_day_keeps_its_own_room_answer():
    """Measured on twin_towns(40) in famine: sending every rolled body
    elsewhere by day scattered the people who were picking each other up,
    and a quarter of catastrophe formed no signed tie where it had formed
    nine. The night out goes somewhere; the day may stay."""
    bodies, reach = _town()
    out = errands(bodies, {}, {}, {}, ["net_loft", "quay"], reach, seed=1,
                  rate=1.0, hours=1000.0, commons=[], phase="morning")
    assert out == {"hand": "net_loft"}


def test_a_posted_body_finishes_its_errand_before_the_post_recalls_it():
    """The footman sent to the card room was re-dispatched to his post by
    the next window's bill before he had left the landing, and the errand
    the commit had just landed vanished (scratch play 2026-09-14, chat 9)."""
    from world.charter_move import relocate
    bodies = {"footman": {"place": "landing", "berth": "landing", "available": True,
                          "errand": {"to": "card_room", "purpose": "a message"},
                          "walk": {"target": "card_room", "route": ["landing", "card_room"],
                                   "leg": 0, "credit": 0.0, "held": False}}}
    out, _t, _w = relocate(bodies, {"footman_post": "footman"},
                           {"footman_post": {"place": "landing"}}, None, hours=0.01)
    assert out["footman"]["walk"]["target"] == "card_room"
    assert out["footman"]["errand"]["to"] == "card_room"
    # Arrived (no walk), the post recalls him as before.
    bodies["footman"].pop("walk"); bodies["footman"]["place"] = "card_room"
    out, _t, _w = relocate(bodies, {"footman_post": "footman"},
                           {"footman_post": {"place": "landing"}}, None, hours=4.0)
    assert out["footman"].get("walk", {}).get("target") in ("landing", None)
    assert out["footman"]["place"] in ("landing", "card_room")
