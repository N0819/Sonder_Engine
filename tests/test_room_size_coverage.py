"""G6: a room nobody sized is a perception grade the engine picked itself.

`size` used to be prose flavour, and going unauthored cost nothing but flat
description. That stopped being true when the derivation layer landed:
`proximity_rel` reads size to decide whether two people are `across` a room
rather than `near` it, and S2a's placement-unknown fallback caps sight in a
large room at `shapes`. So an unauthored size now silently picks how far
apart two people are and how well they can see each other.

Measured on the 61 live scenes: 392 rooms, 217 authored. Of the 175 bare
ones the keyword hint rescues 24 and 151 fall to `medium`. Nothing anywhere
said so — which is the whole complaint. This warns, at the one seam that
knows the committed scene, and only where there is somebody to mis-grade.
"""

from __future__ import annotations

from spatial import guessed_room_sizes


def _scene(rooms, positions):
    return {"rooms": rooms, "positions": positions, "entities": {}}


def test_an_unsized_crowded_room_is_reported():
    rows = guessed_room_sizes(_scene(
        {"cell": {"name": "The Cell"}},
        {"a": "cell", "b": "cell"}))
    assert len(rows) == 1
    assert rows[0]["derived"] == "medium"
    assert rows[0]["by_keyword"] is False
    assert rows[0]["occupants"] == 2


def test_an_authored_size_is_never_reported():
    """Authored wins, and authoring is the fix — so it must silence this."""
    assert guessed_room_sizes(_scene(
        {"cell": {"name": "The Cell", "size": "small"}},
        {"a": "cell", "b": "cell"})) == []


def test_an_empty_room_has_no_proximity_to_get_wrong():
    """The warning exists to flag a mis-grade, and a room with nobody in it
    cannot produce one. Reporting all 175 bare rooms every beat would train
    the reader to skip the message."""
    assert guessed_room_sizes(_scene(
        {"cell": {"name": "The Cell"}}, {"a": "cell"})) == []


def test_a_keyword_guess_says_it_was_a_guess():
    """`large` from the word 'hall' and `medium` from nothing at all are
    different failures and read differently."""
    rows = guessed_room_sizes(_scene(
        {"h": {"name": "The Great Hall"}}, {"a": "h", "b": "h"}))
    assert rows[0]["derived"] == "large"
    assert rows[0]["by_keyword"] is True


def test_a_room_that_was_already_shared_is_not_reported_again():
    """A standing condition reported every beat is one the reader learns to
    skip — which is exactly the failure this warning exists to fix. The
    report fires on the beat the room CROSSES into being shared."""
    scene = _scene({"cell": {"name": "The Cell"}}, {"a": "cell", "b": "cell"})
    assert guessed_room_sizes(scene, prev_scene=scene) == []


def test_someone_walking_into_an_unsized_room_re_reports_it():
    before = _scene({"cell": {"name": "The Cell"}}, {"a": "cell"})
    after = _scene({"cell": {"name": "The Cell"}}, {"a": "cell", "b": "cell"})
    assert [r["room"] for r in guessed_room_sizes(after, before)] == ["cell"]


def test_a_freshly_minted_room_is_reported_even_if_it_starts_crowded():
    """Occupancy alone would call a brand-new room 'already shared'."""
    before = _scene({}, {})
    after = _scene({"cell": {"name": "The Cell"}}, {"a": "cell", "b": "cell"})
    assert [r["room"] for r in guessed_room_sizes(after, before)] == ["cell"]


def test_the_busiest_room_is_reported_first():
    rows = guessed_room_sizes(_scene(
        {"q": {"name": "Quiet"}, "b": {"name": "Busy"}},
        {"a": "q", "c": "q", "d": "b", "e": "b", "f": "b"}))
    assert [r["room"] for r in rows] == ["b", "q"]


def test_the_check_is_wired_into_prepare_scene_commit():
    """Pinned at the seam and not only on the helper. The repeated lesson in
    this repo is a test aimed at an extracted function rather than at the
    path it was extracted from (see test_mapping_quick_returns), so this
    asserts the call actually sits inside the scene-commit preparation —
    a helper nobody calls warns nobody."""
    import ast

    import commit

    tree = ast.parse(open(commit.__file__).read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef)
              and n.name == "prepare_scene_commit")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "guessed_room_sizes" in called
