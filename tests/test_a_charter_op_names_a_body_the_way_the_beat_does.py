"""A charter op names a body by its display name and the surgery keys it.

The social hand, shown a house by name, wrote {op: errand, body: "Lianw
Brabw"} for `footman:0001` (scratch play 2026-09-14, chat 9 turn 7); the
surgeries knew keys alone and would have refused the errand the hand had just
been enabled to write.
"""

import copy

from world.charter import normalize_charter
from world.charter_ops import apply_charter_ops


def _registry():
    charter = normalize_charter({
        "key": "assembly",
        "posts": {"footman": {"place": "landing", "serves": []},
                  "master": {"place": "ballroom", "serves": []}},
        "bodies": {
            "footman:0001": {"name": "Lianw Brabw", "place": "landing",
                             "berth": "landing", "available": True,
                             "home_post": "footman"},
            "master:0001": {"name": "Mr Pellew", "place": "ballroom",
                            "berth": "ballroom", "available": True,
                            "home_post": "master"},
        },
    })
    return {"version": 1, "items": {"assembly": {"state": charter}}}


def test_an_errand_by_display_name_reaches_the_keyed_body():
    registry = _registry()
    rows = apply_charter_ops(registry, [
        {"op": "errand", "body": "Lianw Brabw", "to": "card_room",
         "purpose": "deliver a message"}], by="test", turn_idx=7)
    assert rows[0]["result"]["body"] == "footman:0001"
    body = registry["items"]["assembly"]["state"]["bodies"]["footman:0001"]
    assert body["errand"]["to"] == "card_room"


def test_a_key_stays_a_key_and_an_unknown_name_is_refused():
    registry = _registry()
    rows = apply_charter_ops(registry, [
        {"op": "errand", "body": "footman:0001", "to": "card_room",
         "charter": "assembly"}], by="test", turn_idx=7)
    assert rows[0]["result"]["body"] == "footman:0001"
    try:
        apply_charter_ops(copy.deepcopy(registry), [
            {"op": "errand", "body": "Nobody Here", "to": "card_room",
             "charter": "assembly"}], by="test", turn_idx=7)
    except ValueError as exc:
        assert "Nobody Here" in str(exc)
    else:
        raise AssertionError("an unknown name was accepted")
