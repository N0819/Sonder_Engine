"""Scent on the room graph: a ledger with memory, not a field with a path.

The three properties that make scent a different mechanic from sound, each
pinned here because each one is what a story is actually buying:

  * it ACCUMULATES while a body stands somewhere;
  * it LINGERS after the body has gone, which is what a trail IS;
  * it is stopped by a shut door where a noise would carry.

Prior art and the reasoning for the shape: `docs/CREDITS.md` (Dwarf Fortress
miasma, Brogue's Dijkstra maps, the roguelike scent map) and
`docs/guides/RESEARCH.md` (turbulent plume tracking).
"""

from __future__ import annotations

import pytest

from world.spatial import (SCENT_FLOOR, SCENT_LEVELS, SCENT_PASS,
                           advance_scents, scent_at, scent_edges,
                           scent_gradient, scent_word)


def rooms(barrier="open_door", exposure="enclosed"):
    """a -- b -- c, the middle joint being the barrier under test."""
    return {"rooms": {
        "a": {"name": "a", "exposure": exposure,
              "adjacent": [{"to": "b", "barrier": "open_door"}]},
        "b": {"name": "b", "exposure": exposure,
              "adjacent": [{"to": "a", "barrier": "open_door"},
                           {"to": "c", "barrier": barrier}]},
        "c": {"name": "c", "exposure": exposure,
              "adjacent": [{"to": "b", "barrier": barrier}]}}}


def stand(scene, beats, room="a", kind="breath", level="faint"):
    for _ in range(beats):
        scene["scents"] = advance_scents(
            scene, [{"room": room, "kind": kind, "level": level}])
    return scene


def leave(scene, beats):
    for _ in range(beats):
        scene["scents"] = advance_scents(scene, [])
    return scene


def strength(scene, room, kind="breath"):
    return scent_at(scene, room).get(kind, 0.0)


def test_a_body_standing_somewhere_makes_the_room_smell_of_it():
    sc = stand(rooms(), 1)
    first = strength(sc, "a")
    assert first > SCENT_FLOOR
    assert strength(stand(rooms(), 3), "a") > first, "it accumulates"


def test_the_trail_outlives_the_body_that_left_it():
    """THE WHOLE MECHANIC. A sound exists in its beat; a smell is memory.
    Dwarf Fortress's miasma keeps spreading after its source is removed, and
    this is the same property: a hunter follows where you WERE."""
    sc = leave(stand(rooms(), 3), 6)
    assert strength(sc, "a") > SCENT_FLOOR, "the trail died with the body"
    # And it does not last for ever -- a trail that never fades is a map.
    assert strength(leave(sc, 40), "a") == 0.0


def test_it_bleeds_one_room_at_a_time_rather_than_flooding():
    """A gas goes where the air goes, and slowly. One beat, one room -- the
    lag is what stops a diffusion looking like a flood."""
    sc = rooms()
    sc["scents"] = advance_scents(
        sc, [{"room": "a", "kind": "breath", "level": "strong"}])
    assert strength(sc, "a") > 0 and strength(sc, "b") == 0.0
    sc["scents"] = advance_scents(sc, [])
    assert strength(sc, "b") > 0, "it never left the room it was made in"
    assert strength(sc, "b") < strength(sc, "a")


def test_a_shut_door_stops_a_trail_that_a_noise_would_cross():
    """The orders differ from the sound model's and that is the point: a
    shut door costs sound 6 dB and stops bulk air almost entirely."""
    assert SCENT_PASS["closed_door"] < SCENT_PASS["open_door"] / 5
    through = leave(stand(rooms("open_door"), 4), 3)
    shut = leave(stand(rooms("closed_door"), 4), 3)
    assert strength(through, "c") > 0.0
    assert strength(shut, "c") == 0.0
    # The shut door does not seal the room it is IN, only the way on.
    assert strength(shut, "b") > 0.0


def test_an_open_room_loses_its_air_and_a_sealed_one_holds_it():
    sealed = leave(stand(rooms(exposure="enclosed"), 3), 5)
    open_air = leave(stand(rooms(exposure="open"), 3), 5)
    assert strength(sealed, "a") > strength(open_air, "a")


def test_a_body_is_told_a_word_and_never_a_direction():
    """A nose does not give you a bearing. `scent_at` names no room but the
    one you are standing in, and `scent_word` is the whole of what a body
    receives -- the strength is the engine's."""
    sc = stand(rooms(), 3)
    assert scent_word(strength(sc, "a")) in SCENT_LEVELS
    assert scent_word(SCENT_FLOOR) is None
    assert set(scent_at(sc, "a")) == {"breath"}


def test_the_gradient_points_back_at_where_the_body_was():
    """The hunter's read, and the reason this is Brogue's Dijkstra map
    rather than a percept: it NAMES ROOMS, because it answers where a thing
    walks and nothing here is delivered to anybody."""
    sc = leave(stand(rooms(), 4), 3)
    pull = scent_gradient(sc, "b", "breath")
    assert pull["a"] > pull.get("b", 0.0)


def test_a_wall_is_not_a_way_and_an_undescribed_door_is_shut():
    sc = {"rooms": {
        "a": {"name": "a", "adjacent": [{"to": "b", "barrier": "wall"},
                                        {"to": "c"}]},
        "b": {"name": "b", "adjacent": [{"to": "a", "barrier": "wall"}]},
        "c": {"name": "c", "adjacent": [{"to": "a"}]}}}
    edges = scent_edges(sc, "a")
    assert "b" not in edges, "a wall passes no air"
    # An edge with NO barrier written on it is an open way through -- the
    # plan schema says so ("omit for an open way through") and
    # `normalize_barrier` answers `open`. What gets nothing is a barrier the
    # table does not name, which is `unknown`, `separated` and anything that
    # normalizes to `wall`.
    assert edges["c"] == pytest.approx(SCENT_PASS["open"])
    sealed = {"rooms": {
        "a": {"name": "a", "adjacent": [{"to": "b", "barrier": "unknown"},
                                        {"to": "c", "barrier": "window"}]},
        "b": {"name": "b", "adjacent": []}, "c": {"name": "c", "adjacent": []}}}
    assert scent_edges(sealed, "a") == {}, (
        "glass passes light and some sound and no air; an unknown way "
        "through is not assumed to be one")


class TestOnlyACreatureGivenANoseHasOne:
    """The gate both senses got the day they were built: on 2026-09-06 the
    hearing channel was handed to every creature that existed, including one
    the Writers' Room had filed as "blind, deaf... tracking prey only by
    warm exhaled carbon dioxide". A sense nobody wrote is a sense the
    creature does not have."""

    def _scene(self):
        return leave(stand(rooms(), 4), 2)

    def _registry(self, senses):
        return {"items": {"thing": {"state": {
            "creature": {"prey": ["unposted"], "senses": senses},
            "bodies": {"x": {"place": "b", "available": True}}}}}}

    def test_a_creature_with_no_nose_smells_nothing(self):
        from world.charter_runtime import scent_for_creatures

        for senses in ({}, {"range_rooms": 3}, {"scent": False},
                       {"hearing": True}):
            out = scent_for_creatures(self._registry(senses), self._scene())
            assert out["items"]["thing"]["state"]["smelled"] == {}, senses

    def test_a_creature_with_a_nose_is_drawn_to_where_the_body_was(self):
        from world.charter_predation import _pull
        from world.charter_runtime import scent_for_creatures

        out = scent_for_creatures(
            self._registry({"scent": True}), self._scene())
        state = out["items"]["thing"]["state"]
        smelled = state["smelled"]
        assert smelled.get("a"), "the trail into the next room was not read"
        assert all(isinstance(v, int) for v in smelled.values())
        # Both senses land on one scale, so the walk never has to ask which
        # one told it.
        state["overheard"] = {"c": 1}
        assert _pull(state)["a"] == smelled["a"] and _pull(state)["c"] == 1


class TestSurgeAndCast:
    """The behaviour the plume literature finds and trained agents
    rediscover (`docs/guides/RESEARCH.md` s1.8): SURGE while the odour is
    there, CAST across the neighbourhood when it is not.

    Measured before this existed (`docs/UNBUILT.md` s1.141): a body walking
    a five-room corridor and pulling the door shut behind them left the
    hunter at r2 reading `{r2: 0.169, r1: 0.117, r3: 0.165}` -- its own room
    the local maximum, no uphill step, and nothing to do about it ever
    again. One door defeated a sense that is supposed to be the HARD one to
    shake.
    """

    def _corridor(self, shut_behind=None):
        rooms = {}
        for i in range(5):
            adj = []
            if i:
                adj.append({"to": "r%d" % (i - 1), "barrier":
                            "closed_door" if shut_behind == i else "open_door"})
            if i < 4:
                adj.append({"to": "r%d" % (i + 1), "barrier":
                            "closed_door" if shut_behind == i + 1
                            else "open_door"})
            rooms["r%d" % i] = {"name": "r%d" % i, "exposure": "enclosed",
                                "adjacent": adj}
        return {"rooms": rooms}

    def _neighbours(self):
        return {"r%d" % i: [r for r in ("r%d" % (i - 1), "r%d" % (i + 1))
                            if r in {"r%d" % n for n in range(5)}]
                for i in range(5)}

    def _states(self, place="r2", senses=None):
        return {"thing": {
            "creature": {"prey": ["unposted"],
                         "senses": senses or {"scent": True,
                                              "range_rooms": 2}},
            "bodies": {"x": {"place": place, "available": True}}}}

    def _hunt(self, states, pull):
        from world.charter_predation import hunt_moves

        return hunt_moves(states, "thing", {}, {}, self._neighbours(), 1,
                          0.5, noises=pull)

    def test_it_surges_while_the_trail_is_live(self):
        """Nothing new: an uphill step is walked, and casting is not
        entered while there is one."""
        states = self._states()
        assert self._hunt(states, {"r3": 3}) == {"x": "r3"}
        assert states["thing"].get("casting") == {}

    def test_a_trail_that_ends_here_makes_it_search_instead_of_stop(self):
        states = self._states()
        moved = self._hunt(states, {"r2": 2})   # the pull names its OWN room
        assert moved, "the hunter stood still where the trail ran out"
        assert moved["x"] in ("r1", "r3")
        assert states["thing"]["casting"]["x"]["beats"] == 1

    def test_casting_widens_and_never_paces_the_same_two_doorways(self):
        states = self._states()
        seen = []
        for _ in range(3):
            moved = self._hunt(states, {"r2": 2})
            if not moved:
                break
            seen.append(moved["x"])
            states["thing"]["bodies"]["x"]["place"] = moved["x"]
        assert len(seen) == len(set(seen)), (
            "it went back into a room it had already put its head into")

    def test_the_search_is_bounded_and_it_gives_up(self):
        """A creature that searches for ever is a creature that never lets a
        story move on."""
        from world.charter_predation import CAST_BEATS

        states = self._states()
        states["thing"]["casting"] = {
            "x": {"beats": CAST_BEATS, "tried": []}}
        assert self._hunt(states, {"r2": 2}) == {}
        assert "x" not in states["thing"]["casting"], "it never gave up"

    def test_a_hearing_creature_does_not_cast(self):
        """The asymmetry is deliberate: a noise is over the moment it
        happens, so there is nothing to have lost. A nose is the sense that
        is slow to notice and hard to shake, and casting is why."""
        states = self._states(senses={"hearing": True, "range_rooms": 2})
        assert self._hunt(states, {"r2": 2}) == {}
        assert not states["thing"].get("casting")

    def test_one_shut_door_now_buys_distance_rather_than_safety(self):
        """s1.141 end to end, on the corridor it was measured on."""
        from world.spatial import advance_scents
        from world.charter_runtime import scent_for_creatures

        sc = self._corridor(shut_behind=3)
        for room in ("r0", "r1", "r2", "r3", "r4"):
            for _ in range(2):
                sc["scents"] = advance_scents(
                    sc, [{"room": room, "kind": "breath", "level": "faint"}])
        registry = {"items": {"thing": {"state": self._states()["thing"]}}}
        scent_for_creatures(registry, sc)
        state = registry["items"]["thing"]["state"]
        states = {"thing": state}
        from world.charter_predation import _pull

        moved = self._hunt(states, _pull(state))
        assert moved, "the shut door stopped it dead, as it used to"
