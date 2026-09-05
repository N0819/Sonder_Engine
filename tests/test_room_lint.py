"""The layout lint (`world/spatial_lint.py`, behind `world/spatial.py`): every
check with a case that fires and a case that does not, the once-on-appearance
filter, and that no check reads prose.

Design: `docs/design/DESIGN_ROOM_FIDELITY.md` §3. Live cases: F3 (a compass
word minted a room; the embedding check is the geometry-side answer) and F27
(anchor ids read scene-wide; every check here is room-scoped).
"""

from __future__ import annotations

import inspect

from world.spatial import (
    LAYOUT_LINT_KINDS, layout_rooms, layout_warning, room_layout_lint,
)


def _scene(rooms):
    return {"rooms": rooms, "positions": {}, "entities": {}}


def _kinds(rows):
    return sorted(r["kind"] for r in rows)


# ---------------------------------------------------------------------------
# Bearings
# ---------------------------------------------------------------------------

def test_reciprocal_bearings_that_are_not_opposites_are_reported_once():
    sc = _scene({
        "a": {"name": "A", "adjacent": [{"to": "b", "barrier": "open_door",
                                         "dir": "n"}]},
        "b": {"name": "B", "adjacent": [{"to": "a", "barrier": "open_door",
                                         "dir": "e"}]},
    })
    rows = [r for r in room_layout_lint(sc)
            if r["kind"] == "reciprocal_bearing_disagrees"]
    assert len(rows) == 1
    assert rows[0]["rooms"] == ["a", "b"] and rows[0]["dirs"] == ["n", "e"]
    assert "not opposites" in layout_warning(rows[0])


def test_opposite_bearings_and_a_one_sided_bearing_are_fine():
    sc = _scene({
        "a": {"name": "A", "adjacent": [{"to": "b", "barrier": "open_door",
                                         "dir": "n"},
                                        {"to": "c", "barrier": "open_door",
                                         "dir": "e"}]},
        "b": {"name": "B", "adjacent": [{"to": "a", "barrier": "open_door",
                                         "dir": "s"}]},
        "c": {"name": "C", "adjacent": [{"to": "a", "barrier": "open_door"}]},
    })
    assert "reciprocal_bearing_disagrees" not in _kinds(room_layout_lint(sc))


# ---------------------------------------------------------------------------
# Walls and openings
# ---------------------------------------------------------------------------

def test_a_wall_whose_anchors_need_more_paces_than_it_has_is_overfull():
    sc = _scene({"r": {"name": "R", "extent": {"w": 2, "d": 6}, "anchors": {
        "a": {"desc": "a chest", "dir": "n"},
        "b": {"desc": "a crate", "dir": "n"},
        "c": {"desc": "a barrel", "dir": "n"},
    }}})
    (row,) = [r for r in room_layout_lint(sc) if r["kind"] == "wall_overfull"]
    assert row["wall"] == "n" and row["needs"] == 3 and row["holds"] == 2
    assert "cannot hold" in layout_warning(row)
    sc["rooms"]["r"]["anchors"].pop("c")
    assert "wall_overfull" not in _kinds(room_layout_lint(sc))


def test_two_doorways_placed_on_one_cell_overlap_and_two_walls_apart_do_not():
    """Two runs on one wall must share cells; a door per wall cannot."""
    sc = _scene({
        "r": {"name": "R", "size": "small",
              "anchors": {"door:a": {"desc": "an arch", "dir": "n",
                                     "footprint": "run"},
                          "door:b": {"desc": "a gate", "dir": "n",
                                     "footprint": "run"}},
              "adjacent": [{"to": "a", "barrier": "open", "dir": "n"},
                           {"to": "b", "barrier": "open", "dir": "n"}]},
        "a": {"name": "A"}, "b": {"name": "B"},
    })
    assert "openings_overlap" not in _kinds(room_layout_lint(sc)), \
        "authored door anchors are fixtures to this check, not openings"
    sc["rooms"]["r"].pop("anchors")
    sc["rooms"]["r"]["extent"] = {"w": 2, "d": 6}
    (row,) = [r for r in room_layout_lint(sc) if r["kind"] == "openings_overlap"]
    assert row["wall"] == "n" and sorted(row["openings"]) == ["door:a", "door:b"]
    assert "same cells" in layout_warning(row)
    sc["rooms"]["r"]["adjacent"][1]["dir"] = "s"
    assert "openings_overlap" not in _kinds(room_layout_lint(sc))


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

def test_a_round_room_with_corner_parts_is_a_contradiction():
    sc = _scene({"r": {"name": "R", "extent": {"w": 6, "d": 6}, "shape": "round",
                       "parts": [{"w": 2, "d": 2, "at": "ne"}]}})
    (row,) = [r for r in room_layout_lint(sc) if r["kind"] == "corner_in_round_room"]
    assert row["corners"] == ["ne"] and "no corner" in layout_warning(row)
    sc["rooms"]["r"].pop("parts")
    assert "corner_in_round_room" not in _kinds(room_layout_lint(sc))


def test_an_l_whose_part_lies_within_the_other_is_a_rectangle():
    sc = _scene({"r": {"name": "R", "extent": {"w": 6, "d": 6}, "shape": "l",
                       "parts": [{"w": 6, "d": 6, "at": "nw"},
                                 {"w": 3, "d": 3, "at": "nw"}]}})
    (row,) = [r for r in room_layout_lint(sc) if r["kind"] == "l_part_redundant"]
    assert row["part"] == "nw" and row["within"] == "nw"
    assert "not an L" in layout_warning(row)
    sc["rooms"]["r"]["parts"] = [{"w": 6, "d": 2, "at": "nw"},
                                 {"w": 2, "d": 6, "at": "ne"}]
    assert "l_part_redundant" not in _kinds(room_layout_lint(sc))


def test_every_shape_the_engine_builds_is_one_floor_and_the_check_can_tell():
    """The shapes `room_grid` can build are connected by construction (one
    `l` part spans the width and one the depth), so the positive case is the
    helper's: a floor in two pieces is reported, one piece is not."""
    from world.spatial import _cells_connected
    assert _cells_connected({(0, 0), (1, 0), (1, 1)})
    assert not _cells_connected({(0, 0), (2, 0)})
    for room in ({"extent": {"w": 5, "d": 9}, "shape": "round"},
                 {"extent": {"w": 7, "d": 7}, "shape": "l",
                  "parts": [{"w": 7, "d": 2, "at": "sw"},
                            {"w": 2, "d": 7, "at": "ne"}]}):
        sc = _scene({"r": dict(room, name="R")})
        assert "shape_disconnected" not in _kinds(room_layout_lint(sc))
    assert "shape_disconnected" in LAYOUT_LINT_KINDS
    assert "one connected floor" in layout_warning(
        {"kind": "shape_disconnected", "room": "r", "shape": "l"})


# ---------------------------------------------------------------------------
# Size against extent
# ---------------------------------------------------------------------------

def test_a_size_word_the_extent_contradicts_is_reported():
    sc = _scene({"r": {"name": "R", "size": "vast", "extent": {"w": 3, "d": 3}}})
    (row,) = [r for r in room_layout_lint(sc)
              if r["kind"] == "size_disagrees_with_extent"]
    assert row["size"] == "vast" and row["measured"] == "tiny"
    assert "the extent decides" in layout_warning(row)
    sc["rooms"]["r"]["size"] = "small"
    sc["rooms"]["r"]["extent"] = {"w": 4, "d": 4}
    assert "size_disagrees_with_extent" not in _kinds(room_layout_lint(sc))


def test_an_extent_that_is_not_paces_is_reported_and_ignored():
    sc = _scene({"r": {"name": "R", "extent": "big"}})
    (row,) = [r for r in room_layout_lint(sc) if r["kind"] == "extent_unreadable"]
    assert row["extent"] == "big" and "was ignored" in layout_warning(row)
    sc["rooms"]["r"]["extent"] = {"w": 3, "d": 3}
    assert "extent_unreadable" not in _kinds(room_layout_lint(sc))
    sc["rooms"]["r"].pop("extent")
    assert "extent_unreadable" not in _kinds(room_layout_lint(sc))


# ---------------------------------------------------------------------------
# Embedding on a plane
# ---------------------------------------------------------------------------

def test_two_wide_rooms_both_north_of_one_room_land_on_each_other():
    """Two twenty-four-pace rooms cannot both stand north of a six-pace one:
    wherever their doorways fall, their cells meet. Placing by bearing the
    way the observer's field does names the pair."""
    sc = _scene({
        "a": {"name": "Hall", "size": "medium",
              "adjacent": [{"to": "b", "barrier": "open_door", "dir": "n"},
                           {"to": "c", "barrier": "closed_door", "dir": "n"}]},
        "b": {"name": "Gallery", "extent": {"w": 24, "d": 2}},
        "c": {"name": "Arcade", "extent": {"w": 24, "d": 2}},
    })
    layout = layout_rooms(sc, "a")
    assert layout["collisions"] == [("c", "b", "a")]
    assert set(layout["offsets"]) == {"a", "b"}
    (row,) = [r for r in room_layout_lint(sc)
              if r["kind"] == "rooms_overlap_when_placed"]
    assert row["rooms"] == ["c", "b"] and row["via"] == "a"
    assert row["names"] == ["Arcade", "Gallery"]
    assert "cannot be drawn on one plane" in layout_warning(row)


def test_rooms_on_opposite_walls_embed_and_a_bearingless_edge_is_not_placed():
    sc = _scene({
        "a": {"name": "A", "size": "medium",
              "adjacent": [{"to": "b", "barrier": "open_door", "dir": "n"},
                           {"to": "c", "barrier": "open_door", "dir": "s"},
                           {"to": "d", "barrier": "open_door"},
                           {"to": "e", "barrier": "wall", "dir": "e"}]},
        "b": {"name": "B", "extent": {"w": 24, "d": 2}},
        "c": {"name": "C", "extent": {"w": 24, "d": 2}},
        "d": {"name": "D", "extent": {"w": 24, "d": 24}},
        "e": {"name": "E", "extent": {"w": 24, "d": 24}},
    })
    layout = layout_rooms(sc, "a")
    assert layout["collisions"] == []
    assert set(layout["offsets"]) == {"a", "b", "c"}
    assert "rooms_overlap_when_placed" not in _kinds(room_layout_lint(sc))


def test_the_layout_is_deterministic_and_reaches_a_second_hop():
    sc = _scene({
        "a": {"name": "A", "size": "small",
              "adjacent": [{"to": "b", "barrier": "open_door", "dir": "e"}]},
        "b": {"name": "B", "size": "small",
              "adjacent": [{"to": "c", "barrier": "open_door", "dir": "e"}]},
        "c": {"name": "C", "size": "small"},
    })
    first = layout_rooms(sc, "a")
    assert set(first["offsets"]) == {"a", "b", "c"}
    assert first["offsets"]["b"][0] > 0 and first["offsets"]["c"][0] > \
        first["offsets"]["b"][0]
    assert layout_rooms(sc, "a") == first


# ---------------------------------------------------------------------------
# Once on appearance, and the rules of the module
# ---------------------------------------------------------------------------

def test_with_a_previous_scene_only_new_rows_are_reported():
    before = _scene({
        "a": {"name": "A", "adjacent": [{"to": "b", "barrier": "open_door",
                                         "dir": "n"}]},
        "b": {"name": "B", "adjacent": [{"to": "a", "barrier": "open_door",
                                         "dir": "e"}]},
    })
    assert _kinds(room_layout_lint(before)) == ["reciprocal_bearing_disagrees"]
    assert room_layout_lint(before, before) == []
    after = {"rooms": {**before["rooms"],
                       "c": {"name": "C", "size": "vast",
                             "extent": {"w": 2, "d": 2}}}}
    assert _kinds(room_layout_lint(after, before)) == [
        "size_disagrees_with_extent"]


def test_every_kind_has_a_sentence_and_an_empty_scene_has_no_rows():
    assert room_layout_lint({}) == [] and room_layout_lint(None) == []
    assert room_layout_lint({"rooms": {"r": "not a room"}}) == []
    for kind in LAYOUT_LINT_KINDS:
        assert isinstance(layout_warning({"kind": kind, "room": "r",
                                          "names": ["A", "B"], "dirs": ["n", "e"],
                                          "rooms": ["a", "b"], "via": "c",
                                          "wall": "n", "openings": ["x", "y"],
                                          "needs": 3, "holds": 2,
                                          "corners": ["ne"], "part": "nw",
                                          "within": "ne", "shape": "l",
                                          "size": "vast", "measured": "tiny",
                                          "extent": {"w": 2, "d": 2}}), str)
    assert layout_warning({"kind": "something_else"}).startswith("layout:")


def test_the_lint_reads_no_prose():
    """CLAUDE.md forbids a guard that reads free text. The module never
    touches `desc`, `notes` or a `name` as a value -- `name` appears only
    as the label a row carries for its reader."""
    from pathlib import Path
    from world import spatial_lint
    source = Path(spatial_lint.__file__).read_text(encoding="utf-8")
    for field in ('get("desc")', 'get("notes")', "['desc']", "['notes']"):
        assert field not in source


def test_the_commit_and_the_room_both_surface_the_rows():
    """Wiring: the commit reports appearance under its own told-flag, the
    Room's `inspect_contradictions` reports the standing state under
    `layout`."""
    from persist import commit_scene_state
    from story import room_tools
    commit_src = inspect.getsource(commit_scene_state)
    assert "room_layout_lint(sc, prev_scene if _layout_told else None)" in commit_src
    assert '"layout_lint_told"' in commit_src
    tool_src = inspect.getsource(room_tools._t_inspect_contradictions)
    assert 'out["layout"] = room_layout_lint(scene)' in tool_src
