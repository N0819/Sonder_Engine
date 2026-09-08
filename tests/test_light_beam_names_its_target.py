"""D5 (review 2026-09-07): the page says what the beam is ON.

A cone has changed the light field since 2026-09: `CONE_GAIN` concentrates
it, `cone_factor` masks off-axis, `_resolve_pointed_at` reads the aim. So
the engine has always known exactly where a lamp was pointed, and the view
named the LAMP and never its target. Measured, chat 117 beats 59-62: the
player held a hand lamp on a creature for five consecutive beats and no
sentence in any view said so.

Two halves, because the light field's vocabulary is anchors and a body is
not one:

* `light_shape` gains `aimed` -- the visible anchors a coned source in view
  is pointed at AND actually reaching, nearest the source first
  (`_aimed_at`, rule (f)). Rendered only where it names a set the grading
  did not already name by itself (`composer.aim_worth_naming`).
* `held_beam_falls_on` answers the same question about a BODY, and
  `presence_percepts` renders it on the presence sentence.

Both subtract: every anchor named is one `feature_visibility` already
admitted, every body named is one the presence gate already admitted, and
an unmeasured body claims nothing.
"""

from __future__ import annotations

from agents import composer
from agents.composer import aim_worth_naming, render_light_shape
from world.spatial import held_beam_falls_on, light_shape


ANCHORS = {
    "crate": {"desc": "a stack of crates", "cell": [3, 0], "height": "waist"},
    "bench": {"desc": "a work bench", "cell": [0, 3], "height": "waist"},
    "shelf": {"desc": "a steel shelf", "cell": [6, 3], "height": "waist"},
}


def hall(pointed, *, lamp="lit", bodies=None, held=True):
    """A seven-by-seven half-lit hall: the player at the south wall holding
    a coned lamp, three anchors round the walls, optional bodies on cells.
    Dim rather than dark on purpose -- the anchors have to be VISIBLE for
    the shape to grade them at all, and a beam is interesting exactly where
    there is other light for it to be picked out against."""
    room = {"name": "the Hall", "desc": "", "light": "dim",
            "exposure": "enclosed", "adjacent": [], "shape": "rectangle",
            "extent": {"w": 7, "d": 7}, "anchors": dict(ANCHORS)}
    entities = {"lamp": {"name": "the hand lamp", "light_source": lamp,
                         "light_shape": "cone", "portable": True,
                         "state": {"pointed_at": pointed}}}
    positions = {"P": "hall", "lamp": "hall"}
    stations = {"P": {"cell": [3, 6]}}
    for name, cell in (bodies or {}).items():
        positions[name] = "hall"
        stations[name] = {"cell": list(cell)}
    return {"rooms": {"hall": room}, "positions": positions,
            "entities": entities, "stations": stations,
            "orientation": {"P": {"facing": "n"}},
            "contained": {"lamp": {"in": "P"}} if held else {},
            "poses": {}, "attire": {}, "overlays": {}}


# ---------------------------------------------------------------------------
# The anchors the beam is on
# ---------------------------------------------------------------------------

def test_the_shape_names_what_the_beam_is_pointed_at():
    shape = light_shape(hall("crate"), "P")
    assert shape["aimed"] == ["a stack of crates"], shape
    assert "The beam is on a stack of crates." in render_light_shape(shape)


def test_swinging_the_beam_names_the_new_thing():
    for anchor, desc in (("crate", "a stack of crates"),
                         ("bench", "a work bench"),
                         ("shelf", "a steel shelf")):
        assert light_shape(hall(anchor), "P")["aimed"] == [desc], anchor


def test_an_all_round_source_is_pointed_at_nothing():
    """No axis, no beam: `light_shape` says nothing about aim, and the flat
    grading sentence stands exactly as it did."""
    scene = hall("crate")
    scene["entities"]["lamp"]["light_shape"] = "all_round"
    shape = light_shape(scene, "P")
    assert shape.get("aimed", []) == []  # no beam, no key (D5)
    assert "beam" not in render_light_shape(shape)


def test_the_aim_is_in_the_shape_signature():
    """Swinging the beam is NEWS. The signature is the environment percept's
    dedupe key, so an aim left out of it would leave the room `unchanged`
    and the new sentence suppressed as furniture."""
    one = composer._shape_signature(
        composer._clean_shape(light_shape(hall("crate"), "P"),
                              composer.LIGHT_SHAPE_LEVELS))
    two = composer._shape_signature(
        composer._clean_shape(light_shape(hall("bench"), "P"),
                              composer.LIGHT_SHAPE_LEVELS))
    assert one != two


def test_a_beamless_shape_hashes_to_exactly_what_it_hashed_before():
    """NO UPGRADE BEAT. `_shape_signature` is the dedupe key of both the
    environment percept and the soundscape percept, so an `aimed=` segment
    emitted unconditionally would rewrite the stored standing key of every
    room description and every din in every live chat and re-announce them
    all as news on the first beat after this landed. Measured on the sound
    shape below: `din=a generator|from=a generator|self=din` before, and
    `din=a generator|from=a generator|aimed=|self=din` with the segment
    unconditional. The segment is APPENDED and only where there is a beam.
    """
    din = {"groups": [{"level": "din", "items": ["a generator"]}],
           "sources": ["a generator"], "openings": [], "self": "din"}
    assert composer._shape_signature(
        composer._clean_shape(din, composer.SOUND_SHAPE_LEVELS)) == (
            "din=a generator|from=a generator|self=din")

    # An all-round lamp: a light shape that can never carry an aim either.
    flat_scene = hall("crate")
    flat_scene["entities"]["lamp"]["light_shape"] = "all_round"
    flat = composer._clean_shape(light_shape(flat_scene, "P"),
                                 composer.LIGHT_SHAPE_LEVELS)
    assert "aimed" not in composer._shape_signature(flat)


def test_the_aim_is_silent_when_it_singles_nothing_out():
    """`aim_worth_naming`, both ways it can add nothing: a beam whose
    anchors are exactly the brightest group repeats the sentence before it,
    and a beam over everything in view has partitioned nothing."""
    brightest_only = {"groups": [{"level": "lit", "items": ["a crate"]},
                                 {"level": "dim", "items": ["a bench"]}],
                      "sources": [], "openings": [], "self": None,
                      "aimed": ["a crate"]}
    assert aim_worth_naming(brightest_only) == []

    everything = {"groups": [{"level": "dim", "items": ["a crate", "a bench"]}],
                  "sources": [], "openings": [], "self": None,
                  "aimed": ["a crate", "a bench"]}
    assert aim_worth_naming(everything) == []

    partitions = {"groups": [{"level": "dim",
                              "items": ["a crate", "a bench", "a shelf"]}],
                  "sources": [], "openings": [], "self": None,
                  "aimed": ["a bench"]}
    assert aim_worth_naming(partitions) == ["a bench"]


# ---------------------------------------------------------------------------
# The body the beam is on -- the measured case
# ---------------------------------------------------------------------------

def test_a_body_in_the_players_own_beam_is_said_so():
    scene = hall("Q", bodies={"Q": (3, 3)})
    assert held_beam_falls_on(scene, "P", "Q") is True
    percept = composer.presence_percepts(
        scene, "P", [{"name": "Q"}], {"Q": "Quill"})[0]
    assert percept.data.get("in_beam") is True
    sentence = composer._render_presence_group([(percept, False, False)])[0][1]
    assert "where your beam falls" in sentence, sentence


def test_a_body_out_of_the_cone_is_not_claimed():
    scene = hall("crate", bodies={"R": (0, 5)})
    assert held_beam_falls_on(scene, "P", "R") is False
    percept = composer.presence_percepts(
        scene, "P", [{"name": "R"}], {"R": "Rook"})
    assert not percept or "in_beam" not in percept[0].data


def test_only_a_beam_the_observer_holds_counts():
    """A lamp standing on the floor lights the same body the same way; the
    aim is a fact about where the OBSERVER is pointing, and there is no
    pointing when nobody is holding it."""
    scene = hall("Q", bodies={"Q": (3, 3)}, held=False)
    assert held_beam_falls_on(scene, "P", "Q") is False


def test_an_unmeasured_body_claims_nothing():
    scene = hall("Q", bodies={"Q": (3, 3)})
    scene["stations"].pop("Q")
    assert held_beam_falls_on(scene, "P", "Q") is False


def test_the_beam_rides_the_dedupe_key_but_costs_nobody_else_a_redescription():
    """Swinging a beam onto a body is a CHANGE for this observer, so the
    presence key moves. Appended rather than placed, so a body nobody is
    pointing a lamp at hashes to what it always hashed to -- no live chat
    spends an upgrade beat re-announcing everyone standing in it."""
    lit = composer.presence_percepts(
        hall("Q", bodies={"Q": (3, 3)}), "P", [{"name": "Q"}], {"Q": "Quill"})[0]
    away = composer.presence_percepts(
        hall("bench", bodies={"Q": (6, 1)}), "P",
        [{"name": "Q"}], {"Q": "Quill"})
    assert lit.data.get("in_beam") is True
    if away:                       # only if the body is visible at all
        assert away[0].dedupe_key != lit.dedupe_key
    # A scene with no light geometry has no beam and no extra key part.
    flat = {"rooms": {"hall": {"name": "the Hall", "desc": "", "light": "lit",
                               "exposure": "enclosed", "adjacent": []}},
            "positions": {"P": "hall", "Q": "hall"}, "entities": {},
            "stations": {}, "orientation": {}, "contained": {},
            "poses": {}, "attire": {}, "overlays": {}}
    plain = composer.presence_percepts(
        flat, "P", [{"name": "Q"}], {"Q": "Quill"})[0]
    assert "in_beam" not in plain.data
    assert plain.dedupe_key == composer.standing_key(
        "presence", (composer.body_key("Q"),),
        (plain.data["tier"], plain.data["arc"], plain.data["sight"], ""))
