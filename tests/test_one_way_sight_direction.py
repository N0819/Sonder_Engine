"""A one-way window says which way it looks, in a field.

`one_way_window` was the ONLY barrier whose meaning depended on which side
declared it: sight passed in the direction the edge was written, and the blind
side was expected to say `wall`. Every other barrier is symmetric — a door is a
door from both ends — so writing adjacency from both rooms is the universal
habit, and it is correct for every value except this one. The habit silently
cancelled it: two "sight passes this way" declarations name no direction at all.

Live, chat 82 "Sarah Moon — Hinami attempt 2". The interview suite declared the
mirror from the annex AND from the cell. Both prompts had asked for `wall` on
the blind side. The model wrote the edge the way edges are written, and the
restrained subject watched her interviewer through a mirror her own room note
called opaque. A deterministic floor that depends on a model breaking a habit
every other barrier rewards is not a floor.

`sight_from` names the watching room on the edge, so the two declarations AGREE
instead of contradicting, and a scene is repaired by naming a room rather than
by deleting a declaration from the correct side.
"""

from __future__ import annotations

import json

import world.spatial as sp


def _suite(*, cell_edge=True, sight_from=None, cell_sight_from=None):
    def edge(to, sf):
        e = {"to": to, "barrier": "one_way_window"}
        if sf:
            e["sight_from"] = sf
        return e
    rooms = {"annex": {"adjacent": [edge("cell", sight_from)]},
             "cell": {"adjacent": [edge("annex", cell_sight_from)] if cell_edge
                      else [{"to": "annex", "barrier": "wall"}]}}
    return {"rooms": rooms}


def _levels(scene):
    return (sp.sight_level(sp.spatial_rel(scene, "annex", "cell")),
            sp.sight_level(sp.spatial_rel(scene, "cell", "annex")))


def test_both_sides_naming_the_watcher_is_one_fact_written_twice():
    """The shape a model actually writes, made correct."""
    scene = _suite(sight_from="annex", cell_sight_from="annex")

    assert sp.sight_direction(scene["rooms"], "annex", "cell") == "annex"
    assert _levels(scene) == ("full", "none")
    assert not sp.mutual_one_way_window(scene, "annex", "cell")
    assert sp.contradictory_sight_edges(scene) == []
    assert [r["room_id"] for r in sp.visible_adjacent_rooms(scene, "annex")] \
        == ["cell"]
    assert sp.visible_adjacent_rooms(scene, "cell") == []


def test_the_blind_side_alone_may_carry_the_field():
    """It is one fact about the doorway, so either side may state it."""
    scene = _suite(cell_sight_from="annex")
    assert sp.sight_direction(scene["rooms"], "annex", "cell") == "annex"
    assert _levels(scene) == ("full", "none")


def test_it_points_the_other_way_just_as_well():
    scene = _suite(sight_from="cell", cell_sight_from="cell")
    assert _levels(scene) == ("none", "full")


def test_the_old_one_sided_declaration_still_works():
    """No scene has this field yet; every one of them must keep working."""
    scene = _suite(cell_edge=False)
    assert sp.sight_direction(scene["rooms"], "annex", "cell") is None
    assert _levels(scene) == ("full", "none")


def test_both_sides_and_no_field_is_still_the_contradiction():
    """The live bug. Nothing names a direction, so nobody sees, and the
    engine says so rather than guessing."""
    scene = _suite()
    assert sp.sight_direction(scene["rooms"], "annex", "cell") is None
    assert _levels(scene) == ("none", "none")
    assert sp.mutual_one_way_window(scene, "annex", "cell")


def test_two_sides_naming_different_watchers_resolve_to_nothing():
    """The same contradiction in a new spelling. Picking one would be exactly
    the guess this field exists to remove."""
    scene = _suite(sight_from="annex", cell_sight_from="cell")
    assert sp.sight_direction(scene["rooms"], "annex", "cell") is None
    assert _levels(scene) == ("none", "none")


def test_a_room_that_is_not_on_the_edge_names_nobody():
    scene = _suite(sight_from="corridor", cell_sight_from="corridor")
    assert sp.sight_direction(scene["rooms"], "annex", "cell") is None


def test_the_field_survives_a_room_redeclaration():
    """A model re-mentioning the doorway has no reliable way to echo back a
    field it never thinks about, and wholesale replacement would strip it --
    the same silence-vs-erasure doctrine `dir` earned the hard way."""
    scene = _suite(sight_from="annex", cell_sight_from="annex")
    merged = sp.merge_scene_with_diff(scene, {"rooms": {
        "annex": {"adjacent": [{"to": "cell", "barrier": "one_way_window"}]}}})

    assert sp.sight_direction(merged["rooms"], "annex", "cell") == "annex"
    assert _levels(merged) == ("full", "none")


def test_the_prompts_ask_for_the_field_in_both_packs():
    """The engine cannot infer a direction, so the prompt has to request it --
    in every language, or the pack that does not ask gets the live bug."""
    import json

    for lang in ("en", "ja"):
        prompts = json.load(open(
            "language_packs/%s/cards/system_prompts.json" % lang))["prompts"]
        for key in ("director_establish", "resolve_repair"):
            assert "sight_from" in str(prompts[key]), (lang, key)


# ---------------------------------------------------------- from the greeting


def test_the_greeting_stamps_the_direction_while_it_is_knowable():
    """A one-sided declaration already says which way it looks — but in a form
    the next beat can destroy without touching it. Promoted to the field at
    the merge, on the beat it is still unambiguous."""
    born = sp.merge_scene_with_diff({}, {"rooms": {
        "annex": {"name": "Annex",
                  "adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
        "cell": {"name": "Cell", "adjacent": []}}})

    assert sp.sight_direction(born["rooms"], "annex", "cell") == "annex"
    assert _levels(born) == ("full", "none")


def test_the_stamped_mirror_survives_the_habit_that_killed_it():
    """Chat 82's exact sequence. The scene is born with the mirror declared
    once, and a later beat writes the far side too — which is how adjacency is
    normally written, and correct for every other barrier. Before the stamp
    that cancelled the mirror; now the redeclaration agrees with it."""
    born = sp.merge_scene_with_diff({}, {"rooms": {
        "annex": {"adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
        "cell": {"adjacent": []}}})
    later = sp.merge_scene_with_diff(born, {"rooms": {
        "cell": {"adjacent": [{"to": "annex", "barrier": "one_way_window"}]}}})

    assert sp.sight_direction(later["rooms"], "annex", "cell") == "annex"
    assert _levels(later) == ("full", "none")
    assert not sp.mutual_one_way_window(later, "annex", "cell")


def test_an_ambiguous_pair_is_never_stamped():
    """Nothing in a bare two-sided pair names a direction, and inventing one is
    the guess the field exists to remove. It stays a contradiction, and stays
    reported."""
    scene = sp.merge_scene_with_diff({}, {"rooms": {
        "annex": {"adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
        "cell": {"adjacent": [{"to": "annex", "barrier": "one_way_window"}]}}})

    assert sp.stamp_sight_direction(scene) == []
    assert sp.sight_direction(scene["rooms"], "annex", "cell") is None
    assert sp.mutual_one_way_window(scene, "annex", "cell")


def test_an_authored_direction_is_never_overwritten():
    scene = {"rooms": {
        "annex": {"adjacent": [{"to": "cell", "barrier": "one_way_window",
                                "sight_from": "cell"}]},
        "cell": {"adjacent": []}}}

    assert sp.stamp_sight_direction(scene) == []
    assert sp.sight_direction(scene["rooms"], "annex", "cell") == "cell"


def test_stamping_is_idempotent():
    scene = {"rooms": {
        "annex": {"adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
        "cell": {"adjacent": []}}}

    assert sp.stamp_sight_direction(scene) == [("annex", "cell", "annex")]
    assert sp.stamp_sight_direction(scene) == []


def test_it_touches_no_other_barrier():
    scene = {"rooms": {
        "hall": {"adjacent": [{"to": "yard", "barrier": "open_door"},
                              {"to": "cell", "barrier": "wall"}]},
        "yard": {"adjacent": []}, "cell": {"adjacent": []}}}
    before = json.dumps(scene, sort_keys=True)

    assert sp.stamp_sight_direction(scene) == []
    assert json.dumps(scene, sort_keys=True) == before
