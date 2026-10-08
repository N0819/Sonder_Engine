"""A near claim never undoes a walk.

`director_movement._reconcile_near_group_positions` settles a disagreement
between `positions` and the decoration `stations` puts on them, and where a
group disagrees and nobody is under way it resolves to the player's room.
Measured over every stored beat (2026-10-07): it fired 15 times on the
scratch play db and moved a body that had just walked once -- scratch story
166 turn 4596, where the pilot crossed onto the bridge by her own
declaration and a stale claim pulled her back into the chapel. A body the
travel record says walked is in no group, exactly as a follower the carry
held is (`walkers_this_beat`).
"""

from __future__ import annotations

import inspect

from agents import director
from agents.director import _reconcile_near_group_positions, walkers_this_beat

PLAYER, PILOT, FIGURE = "Tamsin Coyle", "Hester Gale", "Ricuock Fenendon"


class _Ctx(dict):
    def __getattr__(self, key):
        return self.get(key)


def _chapel_and_bridge():
    return {"rooms": {
        "tide_chapel": {"name": "Tide Chapel", "anchors": {"threshold": {"desc": "the door"}},
                        "adjacent": [{"to": "rope_bridge", "barrier": "open"}]},
        "rope_bridge": {"name": "the rope bridge",
                        "anchors": {"bridge_midspan": {"desc": "midspan"}},
                        "adjacent": [{"to": "tide_chapel", "barrier": "open"}]}},
        "positions": {PLAYER: "tide_chapel", PILOT: "tide_chapel",
                      FIGURE: "rope_bridge"}}


def _beat():
    diff = {"positions": {PILOT: "rope_bridge"}, "stations": {
        PILOT: {"at": "bridge_midspan", "near": [FIGURE]},
        FIGURE: {"at": "bridge_midspan", "near": [PILOT, PLAYER]}}}
    out = {"travel": {"advanced": [{"subject": PILOT, "from": "tide_chapel",
                                    "to": "rope_bridge", "underway": False}],
                      "arrived": [PILOT], "interrupted": [], "held": []}}
    return diff, out


def test_the_walker_is_not_pulled_back_to_the_player():
    diff, out = _beat()
    ctx = _Ctx(warnings=[], director_interpret={}, cast=[])
    _reconcile_near_group_positions(ctx, _chapel_and_bridge(), diff, PLAYER,
                                    held=walkers_this_beat(out, PLAYER))
    assert diff["positions"][PILOT] == "rope_bridge"


def test_without_the_hold_the_repair_pulls_her_back():
    """The control: this is the beat the repair got wrong."""
    diff, _out = _beat()
    ctx = _Ctx(warnings=[], director_interpret={}, cast=[])
    _reconcile_near_group_positions(ctx, _chapel_and_bridge(), diff, PLAYER)
    assert diff["positions"][PILOT] == "tide_chapel"


def test_the_player_is_never_one_of_the_walkers():
    out = {"travel": {"advanced": [{"subject": PLAYER}, {"subject": PILOT}],
                      "arrived": [PLAYER]}}
    assert walkers_this_beat(out, PLAYER) == {PILOT}
    assert walkers_this_beat({}, PLAYER) == set()


def test_the_resolve_hands_the_repair_its_walkers():
    source = inspect.getsource(director.director_resolve)
    assert "held=_held | walkers_this_beat(out, p_name)" in source
