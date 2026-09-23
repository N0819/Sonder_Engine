"""An edge's doorway renders as what it is, never as its engine id.

Playerless Aldermill round 4 (2026-09-23): "against the door:mill race" and
"the door:mill race's iron bars" in seven views and five memories -- the
implicit `door:<room>` anchor spliced like a minted noun.
"""
from agents.composer import _pose_referent


def _scene():
    return {"rooms": {
        "mill_yard": {"name": "Mill Yard", "anchors": {},
                      "adjacent": [{"to": "mill_race", "barrier": "bars", "dir": "n"}]},
        "mill_race": {"name": "Mill Race", "anchors": {},
                      "adjacent": [{"to": "mill_yard", "barrier": "bars", "dir": "s"}]}},
        "positions": {"Sal": "mill_yard"}, "entities": {}}


def test_a_doorway_referent_is_its_description():
    out = _pose_referent(_scene(), "Sal", {}, [], "door:mill_race", is_self=True)
    assert out and "door:" not in out and "_" not in out
