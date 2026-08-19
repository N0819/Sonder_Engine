"""The four things a walk's view and a walk's advance have to agree about.

`_travel_in_flight_view` tells the Director what is under way and
`_travel_continues` advances it, and before DIRECTOR-D10 each carried its own
copy of the legacy-shape tolerance, the declared-mover exemption, the edge
lookup and the long-edge rule. Nothing compared the copies. These test the
shared helpers directly, so a change to one is a change to both by
construction.
"""

from agents.director_movement import (
    _declared_movers,
    _edge_to,
    _pending_legs,
    _still_crossing,
    _travel_in_flight_view,
)

ROOMS = {
    "yard": {"name": "Yard", "adjacent": [
        {"to": "road", "barrier": "open", "distance": "far"},
        {"to": "shed", "barrier": "open", "distance": "adjacent"}]},
    "road": {"name": "Road", "adjacent": [
        {"to": "town", "barrier": "open", "distance": "near"}]},
    "shed": {"name": "Shed", "adjacent": []},
    "town": {"name": "Town", "adjacent": []},
}


def test_the_scene_global_approach_shape_still_names_its_walker():
    """A save written before per-mover records keeps its one walker."""
    assert _pending_legs({"approach": {"who": "Mira", "to_room": "town"}}) == {
        "Mira": {"to_room": "town"}}


def test_a_scene_global_approach_with_no_walker_is_no_walk():
    assert _pending_legs({"approach": {"who": "", "to_room": "town"}}) == {}


def test_per_mover_records_pass_through_untouched():
    legs = {"Mira": {"to_room": "town", "edge_beats": 1}}
    assert _pending_legs({"approach": legs}) == legs


def test_no_approach_and_a_non_dict_approach_are_both_empty():
    assert _pending_legs({}) == {}
    assert _pending_legs({"approach": None}) == {}
    assert _pending_legs({"approach": ["Mira"]}) == {}


def test_the_player_declaring_their_own_move_is_named_by_the_player_name():
    """`self` and `player` are the two spellings the interpretation uses."""
    for who in ("self", "player"):
        assert _declared_movers(
            {"movement": {"mover": who, "to_room": "town"}}, "Mira") == {"Mira"}


def test_a_named_mover_is_exempted_under_their_own_name():
    assert _declared_movers(
        {"movement": {"mover": "Otto", "to_room": "town"}}, "Mira") == {"Otto"}


def test_a_movement_with_no_destination_exempts_nobody():
    assert _declared_movers({"movement": {"mover": "Otto"}}, "Mira") == set()
    assert _declared_movers({"movement": None}, "Mira") == set()
    assert _declared_movers({}, "Mira") == set()


def test_an_edge_is_found_by_its_destination_and_missing_edges_are_empty():
    assert _edge_to(ROOMS, "yard", "road")["distance"] == "far"
    assert _edge_to(ROOMS, "yard", "town") == {}
    assert _edge_to(ROOMS, "nowhere", "road") == {}


def test_a_short_edge_is_never_mid_crossing():
    assert _still_crossing("adjacent", 1) is False
    assert _still_crossing("near", 1) is False


def test_a_long_edge_holds_for_its_first_beat_and_releases_on_the_second():
    """`beats_spent` counts THIS beat, which is why both callers pass
    `edge_beats + 1` -- passing the stored count holds a walker a beat too
    long, on every long edge in the story."""
    assert _still_crossing("far", 1) is True
    assert _still_crossing("far", 2) is False
    assert _still_crossing("remote", 1) is True


def test_the_view_reports_a_long_edge_as_still_crossing_and_reaches_nowhere():
    scene = {"rooms": ROOMS, "positions": {"Mira": "yard"},
             "approach": {"Mira": {"to_room": "town"}}}
    (entry,) = _travel_in_flight_view(scene, {}, "Player")
    assert entry["distance"] == "far"
    assert entry["still_crossing"] is True
    assert entry["reaches_this_beat"] is None


def test_the_view_skips_a_mover_who_declared_their_own_walk_this_beat():
    scene = {"rooms": ROOMS, "positions": {"Mira": "yard"},
             "approach": {"Mira": {"to_room": "shed"}}}
    interp = {"movement": {"mover": "Mira", "to_room": "shed"}}
    assert _travel_in_flight_view(scene, interp, "Player") == []
