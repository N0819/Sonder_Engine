"""A word the engine cannot read must not become a wall.

`normalize_barrier` ended with `return "wall"` for anything unrecognized, and
`wall` is the most restrictive answer the vocabulary has: nothing passes it and
nothing sees through it. So every barrier word the alias table had not been
taught silently became a sealed surface, with no warning and no way downstream
to tell an authored wall from an unread one.

Measured over every `director_resolve`, `director_establish`, `mapping_stage`
and `mapping_quick` output in the live database: **250 of 1,716 barrier
declarations -- 14.6% -- were being turned into walls.** The words being lost
were the parts a building is made of. Every string in `SILENTLY_WALLED` below
is a verbatim value from that census, with the count it occurred at.

The live symptom, chat 63 turn 165: no passable route from
`shrine_interior_first_floor` to `shrine_interior_upstairs`, barrier=wall --
between a shrine's main hall and its own upstairs. `mapping_stage` authored
that edge as `open_shoji` on five consecutive rerolls and was overruled twice
over: once by this fallback, and once by the Director re-declaring the return
edge alone as `wall` (see `test_a_one_sided_seal_does_not_close_a_passage`).
"""

from __future__ import annotations

import pytest

from spatial import (_PASSABLE_BARRIERS, _shield_standing_passage,
                     normalize_barrier, unresolved_barrier_words)
from spatial_orientation import normalize_scene_bearings

# (raw value, live occurrences, what it must resolve to)
SILENTLY_WALLED = [
    ("shoji", 16, "closed_door"),
    ("open_archway", 14, "open"),
    ("pressure_door", 13, "closed_door"),
    ("jammed_door", 12, "closed_door"),
    ("hatch_open", 12, "open_door"),
    ("staircase", 8, "open"),
    ("open_shoji", 8, "open_door"),
    ("open window", 8, "window"),
    ("shoji door and stairs", 6, "open"),
    ("narrow wooden staircase", 6, "open"),
    ("double_doors", 6, "open_door"),
    ("shoji_screen", 4, "closed_door"),
    ("closed_shoji_door", 4, "closed_door"),
    ("genkan", 4, "open"),
    ("open_partition", 4, "open"),
    ("open_ramp", 4, "open"),
    ("stairs", 4, "open"),
    ("main door", 4, "open_door"),
    ("open_shoji_stair", 2, "open"),
    ("open_ground", 2, "open"),
    ("gap_in_barricade", 2, "open"),
]


@pytest.mark.parametrize("raw,count,expected", SILENTLY_WALLED)
def test_a_word_from_the_live_census_is_read(raw, count, expected):
    """Each of these was authored by a model and sealed by the engine."""
    assert normalize_barrier(raw) == expected, (
        "%r occurred %d times live and still does not resolve" % (raw, count))


def test_a_staircase_is_something_a_body_can_walk():
    """The whole point. No spelling of a stair was in the vocabulary, so every
    staircase in the database joined two floors with a wall.
    """
    for spelling in ("stairs", "stair", "staircase", "stairway", "stairwell",
                     "steps", "ladder", "narrow wooden staircase"):
        assert normalize_barrier(spelling) in _PASSABLE_BARRIERS, spelling


def test_a_seal_is_not_softened_into_a_door():
    """The fold must not run the other way. `sealed`, `warded` and `bolted`
    already meant `wall` in the alias table and a qualifier pass that promoted
    them back to an openable door would be worse than the bug it replaced.
    """
    assert normalize_barrier("sealed_blast_door") == "wall"
    assert normalize_barrier("warded_door") == "wall"
    assert normalize_barrier("bolted_hatch") == "wall"
    assert normalize_barrier("solid_wall") == "wall"


def test_the_understood_vocabulary_is_unchanged():
    """The fast path is still first and still exact: this pass must not move
    any value the engine already read correctly.
    """
    for value in ("open", "open_door", "closed_door", "window", "bars",
                  "membrane", "wall", "separated", "unknown"):
        assert normalize_barrier(value) == value
    assert normalize_barrier("shoji door") == "closed_door"
    assert normalize_barrier("none") == "open"
    assert normalize_barrier("") == "wall"
    assert normalize_barrier(None) == "wall"


def test_a_word_nothing_reads_is_reported_not_swallowed():
    """`wall` stays the last resort, because refusing to answer is not an
    option a scene graph has. What changes is that it is now sayable: an
    unreadable word is collected instead of quietly sealing a doorway.
    """
    seen = set()
    assert normalize_barrier("quantum_shimmerfield", unresolved=seen) == "wall"
    assert seen == {"quantum_shimmerfield"}

    rooms = {"hall": {"adjacent": [
        {"to": "upstairs", "barrier": "narrow wooden staircase"},
        {"to": "vault", "barrier": "psionic_baffle"},
    ]}}
    assert unresolved_barrier_words(rooms) == ["psionic_baffle"]


# --- the one-sided seal --------------------------------------------------

def test_a_one_sided_seal_does_not_close_a_passage():
    """THE REPRODUCTION. `mapping_stage` authored the stair as `open_shoji`;
    `director_resolve` re-declared the RETURN edge alone as `wall`. One
    direction passable, the other sealed, no route between a hall and its own
    upstairs -- five consecutive rerolls, live.
    """
    prior = {
        "shrine_interior_first_floor": {"adjacent": [
            {"to": "shrine_interior_upstairs", "barrier": "open_shoji"}]},
        "shrine_interior_upstairs": {"adjacent": [
            {"to": "shrine_interior_first_floor", "barrier": "open_shoji"}]},
    }
    incoming = {
        "shrine_interior_upstairs": {"adjacent": [
            {"to": "shrine_interior_first_floor", "barrier": "wall"}]},
    }
    warnings = []
    out = _shield_standing_passage(prior, incoming, warnings.append)
    edge = out["shrine_interior_upstairs"]["adjacent"][0]
    assert "barrier" not in edge, "the one-sided seal closed the stair"
    assert warnings and "one side only" in warnings[0]


def test_sealing_both_sides_in_one_diff_still_seals():
    """Refusing every seal would be the same defect pointing the other way. A
    two-sided declaration is a decision about the doorway, and it lands.
    """
    prior = {
        "hall": {"adjacent": [{"to": "vault", "barrier": "open_door"}]},
        "vault": {"adjacent": [{"to": "hall", "barrier": "open_door"}]},
    }
    incoming = {
        "hall": {"adjacent": [{"to": "vault", "barrier": "wall"}]},
        "vault": {"adjacent": [{"to": "hall", "barrier": "wall"}]},
    }
    out = _shield_standing_passage(prior, incoming)
    assert out["hall"]["adjacent"][0]["barrier"] == "wall"
    assert out["vault"]["adjacent"][0]["barrier"] == "wall"


def test_a_wall_where_nothing_stood_open_is_left_alone():
    """The shield reads the incumbent. A brand-new edge declared as a wall is
    an authored wall and has nothing to fall back to.
    """
    incoming = {"hall": {"adjacent": [{"to": "cellar", "barrier": "wall"}]}}
    out = _shield_standing_passage({}, incoming)
    assert out["hall"]["adjacent"][0]["barrier"] == "wall"


# --- vertical reciprocity ------------------------------------------------

def test_the_two_ends_of_a_staircase_are_opposite():
    """A stair's two ends are not the same direction. Live, both ends of one
    staircase read `up`, so from the upstairs room the hall it came from was
    also above -- and the same hall has a SECOND stair going down to a
    basement, which with both edges reading `up` there is nothing left to tell
    apart.
    """
    scene = {"rooms": {
        "hall": {"adjacent": [{"to": "upstairs", "vertical": "up"},
                              {"to": "basement", "vertical": "down"}]},
        "upstairs": {"adjacent": [{"to": "hall"}]},
        "basement": {"adjacent": [{"to": "hall"}]},
    }}
    normalize_scene_bearings(scene)
    assert scene["rooms"]["upstairs"]["adjacent"][0]["vertical"] == "down"
    assert scene["rooms"]["basement"]["adjacent"][0]["vertical"] == "up"


def test_two_flights_from_one_room_stay_distinguishable():
    """The reason this matters for the shrine: the main hall has two sets of
    stairs, one up to the second-floor hallway and one down to the basement.
    """
    scene = {"rooms": {
        "hall": {"adjacent": [{"to": "second_floor_hallway", "vertical": "up"},
                              {"to": "basement", "vertical": "down"}]},
        "second_floor_hallway": {"adjacent": [{"to": "hall", "vertical": "up"}]},
        "basement": {"adjacent": [{"to": "hall", "vertical": "down"}]},
    }}
    normalize_scene_bearings(scene)
    # Both reciprocals contradicted their forward edge, so both are dropped
    # rather than guessed -- the doorway survives, the claim does not.
    assert "vertical" not in scene["rooms"]["hall"]["adjacent"][0]
    assert "vertical" not in scene["rooms"]["second_floor_hallway"]["adjacent"][0]


def test_an_unreadable_vertical_is_dropped_then_inferred_from_the_other_end():
    """Same posture as `dir`, in both halves. `sideways` is not a level, so it
    is removed rather than coerced -- and the edge is then left with one side
    declared, which is exactly the case reciprocity is for. `upstairs` folds to
    `up`, and the hall gets `down` from it.
    """
    scene = {"rooms": {
        "hall": {"adjacent": [{"to": "loft", "vertical": "sideways"}]},
        "loft": {"adjacent": [{"to": "hall", "vertical": "upstairs"}]},
    }}
    normalize_scene_bearings(scene)
    assert scene["rooms"]["loft"]["adjacent"][0]["vertical"] == "up"
    assert scene["rooms"]["hall"]["adjacent"][0]["vertical"] == "down"


def test_a_level_nothing_reads_on_both_ends_is_dropped_entirely():
    """With no readable claim at either end there is nothing to infer from,
    and the edge carries no level rather than a guessed one.
    """
    scene = {"rooms": {
        "hall": {"adjacent": [{"to": "loft", "vertical": "sideways"}]},
        "loft": {"adjacent": [{"to": "hall", "vertical": "askew"}]},
    }}
    normalize_scene_bearings(scene)
    assert "vertical" not in scene["rooms"]["hall"]["adjacent"][0]
    assert "vertical" not in scene["rooms"]["loft"]["adjacent"][0]
