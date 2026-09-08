"""Review 2026-09-07 C6/C17: the route scene is merged once per diff content
per turn, and a dry beat skips the per-room ground walk.
"""
import world.weather as weather
from agents.director import route_scene_for
from persist.commit import _advance_ground


def test_the_route_scene_is_shared_until_the_diff_changes():
    ctx = {}
    scene = {"rooms": {"a": {"adjacent": []}}, "positions": {}, "entities": {}}
    sd = {"positions": {"Aurel": "a"}}
    first = route_scene_for(ctx, scene, sd)
    assert route_scene_for(ctx, scene, sd) is first
    sd["positions"]["Aurel"] = "b"
    assert route_scene_for(ctx, scene, sd) is not first
    assert route_scene_for(None, scene, sd) is not None, "no context, no memo"


def test_a_dry_beat_with_nothing_on_the_floor_skips_the_walk(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no exposure walk on a dry beat")
    monkeypatch.setattr(weather, "room_exposure", boom)
    sc = {"rooms": {"a": {}, "b": {}}, "weather": {"precipitation": "none"},
          "ground": {}}
    _advance_ground(1, sc)
    assert "ground" not in sc


def test_two_scenes_do_not_evict_each_other():
    """One entry PER SCENE, because a resolve asks about two of them.

    `director_resolve` route-checks the beat's own scene and, in a charter
    story, the view that stands the town's unpromoted bodies at their cells
    (`common.charter_view_for_rooms`) -- a second, different object with the
    same diff. A single memo slot made each of those evict the other's merge
    every beat, so both re-merged; keyed by scene, both are answered once
    (review 2026-09-07 C6).
    """
    ctx = {}
    scene = {"rooms": {"a": {"adjacent": []}}, "positions": {}, "entities": {}}
    other = {"rooms": {"a": {"adjacent": []}},
             "positions": {"Townsperson": "a"}, "entities": {}}
    sd = {"positions": {"Aurel": "a"}}
    first = route_scene_for(ctx, scene, sd)
    second = route_scene_for(ctx, other, sd)
    assert second is not first
    assert route_scene_for(ctx, scene, sd) is first
    assert route_scene_for(ctx, other, sd) is second


def test_a_scene_moved_in_place_is_merged_again():
    """Identity is optimistic for a dict mutated IN PLACE: same object, same
    `id()`, different world. Positions are the part this engine has actually
    been measured moving that way inside one turn (review 2026-09-07 C9), and
    every route answer turns on them, so they are stamped beside identity."""
    ctx = {}
    scene = {"rooms": {"a": {"adjacent": []}, "b": {"adjacent": []}},
             "positions": {"Mora": "a"}, "entities": {}}
    sd = {"positions": {}}
    first = route_scene_for(ctx, scene, sd)
    assert route_scene_for(ctx, scene, sd) is first
    scene["positions"]["Mora"] = "b"
    again = route_scene_for(ctx, scene, sd)
    assert again is not first
    assert again["positions"]["Mora"] == "b"


def test_a_context_that_keeps_no_side_channels_still_answers():
    """The memo is an optimisation and never a precondition."""
    class NoSideChannels(dict):
        def __setitem__(self, key, value):
            raise TypeError("no side channels here")

    scene = {"rooms": {"a": {"adjacent": []}}, "positions": {}, "entities": {}}
    sd = {"positions": {"Aurel": "a"}}
    merged = route_scene_for(NoSideChannels(), scene, sd)
    assert merged["positions"]["Aurel"] == "a"


def test_no_ledger_and_no_op_means_no_merge_at_all(monkeypatch):
    """`_apply_following_movement` deep-copied the whole scene on every beat
    to discover that nobody was following anybody.

    `apply_following_ops` only ADDS on an op, so an empty ledger plus no ops
    is an empty ledger and the merge could not have said otherwise. Measured
    (review 2026-09-07 C6): 120 of the descent's 123 stored beats and 13 of
    13 of the charter town's carried neither, at 11.1 ms of merge each.
    """
    import agents.director_movement as movement

    def boom(*a, **k):
        raise AssertionError("merged a scene to read an empty follow ledger")

    monkeypatch.setattr(movement, "merge_scene_with_diff", boom)
    scene = {"rooms": {"a": {"adjacent": []}}, "positions": {"Mora": "a"},
             "entities": {}}
    assert movement._apply_following_movement(
        object(), scene, {"positions": {}}, {}, "Aurel") is False
    assert movement._apply_following_movement(
        object(), {**scene, "following": {}}, {"following_ops": []}, {},
        "Aurel") is False


def test_the_mint_floors_read_the_turns_merge():
    """`place_unplaced_mints` and `_unplaced_minted_entities` each built their
    own merge of the same scene and diff, twice per beat between them. Handed
    the turn they read its one merge, and the answer is the same one."""
    from agents.director import (_unplaced_minted_entities,
                                 place_unplaced_mints)

    def case():
        sc = {"rooms": {"kitchen": {"adjacent": []}}, "positions": {},
              "entities": {}}
        sd = {"entities": {"tap": {"name": "tap"}}, "positions": {}}
        return sc, sd

    sc, sd = case()
    assert _unplaced_minted_entities(sc, sd) == ["tap"]
    ctx = {}
    sc2, sd2 = case()
    assert _unplaced_minted_entities(sc2, sd2, ctx=ctx) == ["tap"]
    assert place_unplaced_mints(sc2, sd2, "kitchen", ctx=ctx) == ["tap"]
    # The placement mutated the diff, so the memo cannot answer the next
    # question from a merge that predates it.
    assert _unplaced_minted_entities(sc2, sd2, ctx=ctx) == []
    assert sd2["positions"] == {"tap": "kitchen"}
