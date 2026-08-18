"""A position nothing can walk to is not a position.

`passable_neighbors` is the one graph everyone walks. Crowds move on it,
couriers move on it, and a follower is only carried along a route it proves.
The Director's own `state_diff.positions` was never held to it, so a body
could be written into a room it had no way of reaching and nothing objected.

Live, chat 80 turn 4. The player declared no movement -- `movement` null and
`positions` null on `director_interpret` -- and the spatial specialist wrote
`{"Hinami": "obs_room"}`. The interview cell's only edges are a `wall` (the
two-way mirror) and a `closed_door`, so `passable_route_exists` is False for
every room in the scene: she was moved through the mirror out of a sealed room
into the one the observers were watching her from. The prose author, in the
same step, had her correctly "in the interview cell" seen "through the two-way
mirror" with the psychologist's voice arriving "through the PA speaker".

The rule is about REACHABILITY and deliberately not about declarations. Being
dragged, carried or moved by a lift are legitimate undeclared moves; passing
through a wall is not legitimate however it was declared.
"""

from __future__ import annotations

from agents.director import _unreachable_position_writes as _refused

#: The live scene, reduced to what the rule reads.
BODIES = ["Hinami", "Sarah Moon", "A New Guard", "Traveller"]


def _refused_in(scene, positions, exempt=()):
    """The floor as `director_resolve` calls it: same scene before and after
    (no door opened this beat), every name in BODIES a body, nothing exempt."""
    return _refused(scene, scene, positions, BODIES, exempt=exempt)


SCENE = {
    "positions": {"Hinami": "interview_cell", "Sarah Moon": "obs_room"},
    "rooms": {
        "obs_room": {"name": "Observation Room", "adjacent": [
            {"to": "interview_cell", "barrier": "one_way_window"},
            {"to": "hallway", "barrier": "open_door"},
        ]},
        "interview_cell": {"name": "Interview Cell", "adjacent": [
            {"to": "obs_room", "barrier": "wall"},
            {"to": "holding_hallway", "barrier": "closed_door"},
        ]},
        "hallway": {"name": "Hallway", "adjacent": [
            {"to": "obs_room", "barrier": "open_door"},
        ]},
        "holding_hallway": {"name": "Holding Hallway", "adjacent": [
            {"to": "interview_cell", "barrier": "closed_door"},
            {"to": "hallway", "barrier": "open_door"},
        ]},
    },
}


class TestTheFloor:
    def test_the_live_teleport_is_refused(self):
        assert _refused_in(SCENE, {"Hinami": "obs_room"}) == [
            ("Hinami", "interview_cell", "obs_room")]

    def test_a_two_way_mirror_is_not_a_door(self):
        """The rooms are adjacent. Adjacency is not passability, and the whole
        bug is the two being confused."""
        assert SCENE["rooms"]["interview_cell"]["adjacent"][0]["to"] == "obs_room"
        assert _refused_in(SCENE, {"Hinami": "obs_room"})

    def test_an_ordinary_open_move_is_untouched(self):
        assert _refused_in(SCENE, {"Sarah Moon": "hallway"}) == []

    def test_a_multi_room_walk_over_open_edges_is_untouched(self):
        """`passable_route_exists`, not one-step adjacency: a body may cross
        several open rooms in a beat."""
        scene = {**SCENE, "positions": {**SCENE["positions"],
                                        "Sarah Moon": "hallway"}}

        assert _refused_in(scene, {"Sarah Moon": "obs_room"}) == []

    def test_a_body_that_did_not_move_is_not_a_move(self):
        assert _refused_in(SCENE, {"Sarah Moon": "obs_room"}) == []


class TestWhatItRefusesToJudge:
    """Refusing a write it cannot check would be inventing physics from a gap
    in the map, which is the opposite failure and a worse one."""

    def test_a_room_this_beat_is_minting_is_left_alone(self):
        assert _refused_in(SCENE, {"Hinami": "a_room_being_created"}) == []

    def test_a_body_not_in_the_scene_is_left_alone(self):
        """Somebody arriving has no origin to have walked from."""
        assert _refused_in(SCENE, {"A New Guard": "obs_room"}) == []

    def test_an_empty_or_absent_destination_is_left_alone(self):
        assert _refused_in(SCENE, {"Hinami": ""}) == []
        assert _refused_in(SCENE, {}) == []
        assert _refused_in(SCENE, None) == []

    def test_a_portal_needs_no_exemption(self):
        """`apply_transit_dock_edges` materialises an open `state.link` into a
        real adjacency edge, so the one graph already carries portals. A rule
        that special-cased them would be a second pathfinder."""
        scene = {
            "positions": {"Traveller": "vault"},
            "rooms": {
                "vault": {"adjacent": [{"to": "tower", "barrier": "open"}]},
                "tower": {"adjacent": [{"to": "vault", "barrier": "open"}]},
            },
        }

        assert _refused_in(scene, {"Traveller": "tower"}) == []


class TestWhatItMustNotOverride:
    """Both exemptions were taught by existing tests failing, and both are
    right. A floor that overrides the causality owner is worse than the write
    it was built to stop."""

    def test_a_declared_move_belongs_to_the_movement_backstop(self):
        """A closed door is CONTESTED, not impossible. Whether it was opened
        and crossed is the resolve's to decide, and the backstop above already
        rules on declared movement -- including honouring the resolve's own
        assertion. This floor must not re-answer that."""
        scene = {
            "positions": {"Hinami": "interview_cell"},
            "rooms": {
                "interview_cell": {"adjacent": [
                    {"to": "holding_hallway", "barrier": "closed_door"}]},
                "holding_hallway": {"adjacent": [
                    {"to": "interview_cell", "barrier": "closed_door"}]},
            },
        }
        move = {"Hinami": "holding_hallway"}

        assert _refused_in(scene, move) == [
            ("Hinami", "interview_cell", "holding_hallway")]
        assert _refused_in(scene, move, exempt={"hinami"}) == []

    def test_an_entity_is_not_a_body(self):
        """A vehicle does not reach a room by walking: it travels on
        `state.transit`, and its arrival is what CREATES the dock edge everyone
        else then uses. Route-checking one strips the move that opens the door
        -- which is exactly what it did to a lift arriving and its occupant
        stepping out in the same beat."""
        scene = {
            "positions": {"elevator": "shaft_top", "Hinami": "elevator_interior"},
            "rooms": {"shaft_top": {"adjacent": []},
                      "generator_room": {"adjacent": []},
                      "elevator_interior": {"adjacent": []}},
        }

        assert _refused(scene, scene, {"elevator": "generator_room"},
                        BODIES) == []


class TestTheWiring:
    def test_the_resolve_applies_it_to_the_merged_diff(self):
        """On the MERGED diff, so it holds whichever hand wrote the entry --
        the prose author, the spatial specialist, or a later seam."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)

        assert "_unreachable_position_writes(" in source
        assert "merge_scene_with_diff(sc, sd)" in source
        assert 'sd["positions"].pop(_body, None)' in source

    def test_it_runs_after_positions_are_canonicalized(self):
        """Before canonicalization a position may be keyed by uid rather than
        by the registered name, and `room_of` would not find the body -- the
        check would silently pass on exactly the entries it exists to read."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)
        canon = source.index("canonicalize_positions(sd[\"positions\"]")
        floor = source.index("_unreachable_position_writes(")

        assert floor > canon

    def test_the_refusal_is_reported_rather_than_silent(self):
        """A body that quietly stays put reads as the Director changing its
        mind. The warning names both rooms so the next reader can tell a
        sealed room from a bad write."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)

        assert "no passable route from" in source
