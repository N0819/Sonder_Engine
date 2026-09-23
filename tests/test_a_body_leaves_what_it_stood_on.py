"""A body that walks out of a room leaves behind what it was standing on.

Playerless Aldermill round 7 (2026-09-23), idx 23: Sal walked from the wharf
into the market square and her view read "You are in Aldermill Market Square
... You are standing on the wharf deck." -- the pose kept its support across
the room change, because the rule that spends a mover's pose DETAIL left the
support alone. The posture travels; the ground does not, unless what she
stood on came with her.
"""
from world.spatial import release_moved_body_supports


def _scene(**positions):
    return {
        "rooms": {"river_wharf": {}, "market_square": {}},
        "positions": dict(positions),
        "poses": {"Sal Weatherby": {"posture": "standing",
                                    "support": "wharf deck"}},
        "entities": {},
    }


def test_the_wharf_deck_stays_on_the_wharf():
    scene = _scene(**{"Sal Weatherby": "market_square"})
    released = release_moved_body_supports(
        scene, {"Sal Weatherby": "river_wharf"})
    assert released == [("Sal Weatherby", "wharf deck", "river_wharf")]
    assert scene["poses"]["Sal Weatherby"] == {"posture": "standing",
                                               "support": ""}


def test_what_came_with_her_still_holds_her():
    scene = _scene(**{"Sal Weatherby": "market_square", "cart": "market_square"})
    scene["poses"]["Sal Weatherby"]["support"] = "cart"
    assert release_moved_body_supports(
        scene, {"Sal Weatherby": "river_wharf", "cart": "river_wharf"}) == []
    assert scene["poses"]["Sal Weatherby"]["support"] == "cart"


def test_a_support_this_beat_wrote_is_about_where_she_arrived():
    scene = _scene(**{"Sal Weatherby": "market_square"})
    scene["poses"]["Sal Weatherby"]["support"] = "cobbles"
    assert release_moved_body_supports(
        scene, {"Sal Weatherby": "river_wharf"}, stated=["Sal Weatherby"]) == []
    assert scene["poses"]["Sal Weatherby"]["support"] == "cobbles"


def test_a_body_that_stayed_keeps_its_ground():
    scene = _scene(**{"Sal Weatherby": "river_wharf"})
    assert release_moved_body_supports(
        scene, {"Sal Weatherby": "river_wharf"}) == []
    assert scene["poses"]["Sal Weatherby"]["support"] == "wharf deck"
