"""Approaching is not arriving, and arriving is not entering.

Observed live, story "The Blizzard", turn 2. The player wrote:

    You wander towards it.

of a lit building seen through the snow the beat before. `director_interpret`
produced

    stage: "approach"
    asserted_effects: "progresses across the snowy clearing toward the bui..."
    intended_effects: "reach the mountain waystation"
    movement: {to_room: "distant_mountain_building",
               why: "heading towards the flickering light..."}

-- and `director_resolve` wrote

    "...she reaches the stone-and-wood building, opens the door, and steps
     into its lantern-lit interior where smoke rises from a hearth."

committing `positions: {"Hinami": "distant_mountain_building"}`. Three beats of
fiction in one, and the player declared only the first. It also took her from
`exposure: open` to `exposure: sheltered` -- out of a blizzard -- which nobody
asked for.

Note what was NOT wrong. The passable-route backstop ran and passed the move,
correctly: the rooms were adjacent and the edge was open. The interpret's
`to_room` was the right room. Every part worked except that "towards" was read
as a destination reached.

The distinction cannot be recovered downstream, which is why `arrives` is a
field on the declaration rather than a test applied later. Measured across the
whole live corpus (1249 turns), no text heuristic separates

    "I cross the command deck and head down the central corridor TOWARD the
     med bay"                                    -- an asserted crossing

from

    "PROGRESSES across the snowy clearing TOWARD the building"

Both say "toward", both are staged `approach`, both are `commitment: asserted`.
Four successive heuristics were tried and each blocked legitimate arrivals:
last-element stage (3 false positives), presence-vs-progress markers (8),
single-element beats (4). Only the stage that read the player's sentence can
tell, so that is where the answer is recorded.

`stage` is the cautionary tale one field over: an `ActionStage` enum present
since the beginning and read by NOTHING on the resolve path -- the interpret
has been classifying these correctly all along, to no effect.
"""

from __future__ import annotations

import types

from agents.director import _guard_approach_is_not_arrival


def _ctx():
    return types.SimpleNamespace(warnings=[])


def _scene(**extra):
    scene = {
        "rooms": {
            "snowy_clearing": {"name": "Snowy Clearing", "exposure": "open"},
            "distant_mountain_building": {"name": "Mountain Waystation",
                                          "exposure": "sheltered"},
        },
        "positions": {"Hinami": "snowy_clearing"},
    }
    scene.update(extra)
    return scene


def _heading(**extra):
    """The blizzard's own declaration: a destination, and not arriving at it."""
    mv = {"to_room": "distant_mountain_building",
          "why": "heading towards the flickering light of the mountain "
                 "waystation seen in the distance",
          "mover": "self", "arrives": False}
    mv.update(extra)
    return {"movement": mv}


# --- the guard ---------------------------------------------------------------

def test_wandering_towards_a_building_does_not_put_you_inside_it():
    """The live case, exactly."""
    ctx, scene = _ctx(), _scene()
    diff = {"positions": {"Hinami": "distant_mountain_building"}}
    _guard_approach_is_not_arrival(ctx, _heading(), diff, scene, "Hinami")
    assert diff["positions"] == {}
    assert "Approach is not arrival" in ctx.warnings[0]
    assert "arrives=false" in ctx.warnings[0]


def test_a_declaration_that_does_arrive_is_untouched():
    """The default, and the whole of the existing corpus: every movement that
    reached this field before it existed meant arrival."""
    ctx, scene = _ctx(), _scene()
    for mv in (_heading(arrives=True), {"movement": {"to_room": "x", "mover": "self"}}):
        diff = {"positions": {"Hinami": "distant_mountain_building"}}
        _guard_approach_is_not_arrival(ctx, mv, diff, scene, "Hinami")
        assert diff["positions"] == {"Hinami": "distant_mountain_building"}
    assert ctx.warnings == []


def test_no_declared_movement_is_not_this_guards_business():
    ctx, scene = _ctx(), _scene()
    diff = {"positions": {"Hinami": "distant_mountain_building"}}
    _guard_approach_is_not_arrival(ctx, {"movement": None}, diff, scene, "Hinami")
    assert diff["positions"] == {"Hinami": "distant_mountain_building"}
    assert ctx.warnings == []


def test_it_says_so_rather_than_failing_quietly():
    """A stripped position with no warning reads to a host as the model simply
    not having moved anyone, which is how this went unnoticed for a story."""
    ctx, scene = _ctx(), _scene()
    _guard_approach_is_not_arrival(
        ctx, _heading(), {"positions": {"Hinami": "distant_mountain_building"}},
        scene, "Hinami")
    assert len(ctx.warnings) == 1
    assert "not entering it" in ctx.warnings[0]


def test_nobody_else_is_touched():
    ctx, scene = _ctx(), _scene()
    diff = {"positions": {"Hinami": "distant_mountain_building",
                          "Corin": "distant_mountain_building"}}
    _guard_approach_is_not_arrival(ctx, _heading(), diff, scene, "Hinami")
    assert diff["positions"] == {"Corin": "distant_mountain_building"}


def test_a_vehicle_heading_somewhere_is_the_vehicles_business():
    """`mover` is an entity: the vessel is under way, and the body inside it
    has not walked anywhere. Not this guard's to refuse."""
    ctx, scene = _ctx(), _scene()
    diff = {"positions": {"Hinami": "distant_mountain_building"}}
    _guard_approach_is_not_arrival(
        ctx, _heading(mover="sledge_01"), diff, scene, "Hinami")
    assert diff["positions"] == {"Hinami": "distant_mountain_building"}


def test_a_move_that_goes_nowhere_is_left_alone():
    ctx, scene = _ctx(), _scene()
    diff = {"positions": {"Hinami": "snowy_clearing"}}
    _guard_approach_is_not_arrival(ctx, _heading(), diff, scene, "Hinami")
    assert diff["positions"] == {"Hinami": "snowy_clearing"}
    assert ctx.warnings == []


def test_being_carried_is_somebody_elses_doing():
    """Moving without walking -- carried, dragged, shut in a crate -- is the
    resolve's to assert. Refusing it here would pin a body in place while the
    thing holding it walks off."""
    ctx = _ctx()
    scene = _scene(contained={"Hinami": {"in": "sledge", "mode": "carried"}})
    diff = {"positions": {"Hinami": "distant_mountain_building"}}
    _guard_approach_is_not_arrival(ctx, _heading(), diff, scene, "Hinami")
    assert diff["positions"] == {"Hinami": "distant_mountain_building"}
    assert ctx.warnings == []


def test_a_diff_with_no_positions_is_not_an_error():
    ctx, scene = _ctx(), _scene()
    for diff in ({"positions": {}}, {}):
        _guard_approach_is_not_arrival(ctx, _heading(), diff, scene, "Hinami")
    assert ctx.warnings == []


# --- the contract ------------------------------------------------------------

def test_arrives_defaults_to_true():
    """Every declaration written before this field existed meant arrival, and
    a default of False would strand all of them."""
    from schemas import MovementDecl
    assert MovementDecl(to_room="bridge").arrives is True
    assert MovementDecl(to_room="bridge", arrives=False).arrives is False


def test_the_interpret_is_told_how_to_decide_it():
    """The deterministic half only works if the stage that reads the player's
    sentence fills the field in. Nothing downstream can recover it -- measured
    across 1249 live turns, no text test separates an asserted crossing from a
    declared approach."""
    from prompts import DEFAULT_PROMPTS

    prompt = DEFAULT_PROMPTS["director_interpret"]
    assert "arrives:true|false" in prompt
    assert "SAYS WHETHER THE DECLARATION REACHES" in prompt
    # Both sides of the line, by example.
    assert "I walk to the bridge" in prompt
    assert "I wander towards it" in prompt
    assert "Judge the player's SENTENCE" in prompt


# --- and the Director is told, not merely clamped -----------------------------

def test_the_prompt_states_the_rule_the_guard_enforces():
    """The clamp keeps the world right; the prompt is what stops the PROSE
    describing an interior nobody entered. Clamped state under narration that
    already walked her through the door is the worse failure of the two."""
    from prompts import DEFAULT_PROMPTS

    prompt = DEFAULT_PROMPTS["director_resolve_lean"]
    assert "APPROACHING IS NOT ARRIVING, AND ARRIVING IS NOT ENTERING" in prompt
    assert "`approach` has by definition not landed yet" in prompt
    assert "Crossing a threshold is its own act" in prompt


class TestAnApproachThatCanComplete:
    """Found by driving the harness rather than by reading code: `arrives`
    without a memory strands anyone who keeps writing approach-flavoured text.
    The engine answers "you get closer" for as long as they keep asking, and
    time spent approaching is time spent standing still -- six simulated hours
    of "trudging towards the mountain" left the walker in the clearing she
    started in, under the level-12 snowdrifts the weather had piled on a body
    that never moved.

    One beat closes the distance; the next one arrives.
    """

    def _interp(self, to_room="waystation", mover="self"):
        return {"movement": {"to_room": to_room, "mover": mover,
                             "why": "wandering towards the light",
                             "arrives": False}}

    def test_the_first_beat_does_not_arrive(self):
        ctx, scene = _ctx(), _scene()
        diff = {"positions": {"Hinami": "waystation"}}
        _guard_approach_is_not_arrival(ctx, self._interp(), diff, scene, "Hinami")
        assert diff["positions"] == {}

    def test_the_second_beat_toward_the_same_place_does(self):
        ctx = _ctx()
        scene = _scene(approach={"Hinami": {"to_room": "waystation", "turn": 2}})
        diff = {"positions": {"Hinami": "waystation"}}
        _guard_approach_is_not_arrival(ctx, self._interp(), diff, scene, "Hinami")
        assert diff["positions"] == {"Hinami": "waystation"}
        assert "Approach completed" in ctx.warnings[0]

    def test_a_different_destination_starts_over(self):
        """Changing your mind mid-walk is not progress toward the new place."""
        ctx = _ctx()
        scene = _scene(approach={"Hinami": {"to_room": "elsewhere", "turn": 2}})
        diff = {"positions": {"Hinami": "waystation"}}
        _guard_approach_is_not_arrival(ctx, self._interp(), diff, scene, "Hinami")
        assert diff["positions"] == {}

    def test_somebody_elses_approach_is_not_yours(self):
        ctx = _ctx()
        scene = _scene(approach={"Corin": {"to_room": "waystation", "turn": 2}})
        diff = {"positions": {"Hinami": "waystation"}}
        _guard_approach_is_not_arrival(ctx, self._interp(), diff, scene, "Hinami")
        assert diff["positions"] == {}


class TestAVesselIsAlsoNotThereYet:
    """Found by driving the harness: the guard covered the player's own body
    and nothing else, so "I steer us towards the lighthouse" -- mover: the
    skiff, arrives: false -- put the boat on the rock. A vessel told to head
    for the light is as much not-there-yet as the hand on its tiller."""

    def test_a_vehicle_heading_somewhere_does_not_arrive_either(self):
        ctx = _ctx()
        scene = _scene(positions={"Hinami": "skiff_deck", "skiff": "open_water"})
        diff = {"positions": {"skiff": "lighthouse_rock"}}
        interp = {"movement": {"to_room": "lighthouse_rock", "mover": "skiff",
                               "why": "steering toward the light",
                               "arrives": False}}
        _guard_approach_is_not_arrival(ctx, interp, diff, scene, "Hinami")
        assert diff["positions"] == {}
        assert "skiff" in ctx.warnings[0]

    def test_and_its_second_beat_arrives_like_anyone_elses(self):
        ctx = _ctx()
        scene = _scene(positions={"skiff": "open_water"},
                       approach={"skiff": {"to_room": "lighthouse_rock",
                                           "turn": 4}})
        diff = {"positions": {"skiff": "lighthouse_rock"}}
        interp = {"movement": {"to_room": "lighthouse_rock", "mover": "skiff",
                               "arrives": False}}
        _guard_approach_is_not_arrival(ctx, interp, diff, scene, "Hinami")
        assert diff["positions"] == {"skiff": "lighthouse_rock"}


    def test_two_walkers_do_not_overwrite_each_other(self):
        """Multiplayer is supported. One record for the whole scene meant Ana
        never arrived at the tower because Bo was heading for the gate."""
        ctx = _ctx()
        scene = _scene(approach={"Ana": {"to_room": "tower", "turn": 1},
                                 "Bo": {"to_room": "gate", "turn": 2}})
        diff = {"positions": {"Ana": "tower"}}
        interp = {"movement": {"to_room": "tower", "mover": "self",
                               "arrives": False}}
        _guard_approach_is_not_arrival(ctx, interp, diff, scene, "Ana")
        assert diff["positions"] == {"Ana": "tower"}
        assert "Approach completed" in ctx.warnings[0]

    def test_a_save_written_before_the_per_mover_shape_still_arrives(self):
        """The scene-global record this replaced is still read, so nobody is
        dropped mid-stride by the upgrade."""
        ctx = _ctx()
        scene = _scene(approach={"who": "Hinami", "to_room": "waystation",
                                 "turn": 2})
        diff = {"positions": {"Hinami": "waystation"}}
        interp = {"movement": {"to_room": "waystation", "mover": "self",
                               "arrives": False}}
        _guard_approach_is_not_arrival(ctx, interp, diff, scene, "Hinami")
        assert diff["positions"] == {"Hinami": "waystation"}
