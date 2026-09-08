"""A room nobody has named is shown by its placeholder, never by its id.

The engine already had the placeholder -- the id spelled out, recognised by
`is_derived_room_name` so an authored name can displace it -- but five sites
each spelled it for themselves and the six places perception falls back from
a missing name applied none, handing the view the raw id. Measured on the
descent copy (chat 117 beat 118): the spatial hand minted
`sub_level_three_utility_core` with `name: ""`, the player's view read
"You are in sub_level_three_utility_core.", and the narrator had to write
around it. One producer now, a floor at merge for a room minted nameless,
and a reader-side floor for a blank already stored.
"""

from __future__ import annotations

from world.spatial import (
    derived_room_name, is_derived_room_name, merge_scene_with_diff,
    room_display_name,
)


def test_the_placeholder_is_what_the_predicate_recognises():
    assert derived_room_name("sub_level_three_utility_core") \
        == "Sub Level Three Utility Core"
    assert is_derived_room_name("sub_level_three_utility_core",
                                derived_room_name("sub_level_three_utility_core"))
    assert derived_room_name("") == ""


def test_the_reader_floor_prefers_an_authored_name_and_never_shows_an_id():
    assert room_display_name({"name": "The Landing"}, "landing_3") == "The Landing"
    assert room_display_name({"name": ""}, "landing_3") == "Landing 3"
    assert room_display_name(None, "landing_3") == "Landing 3"
    assert room_display_name(None, None) == ""


def _scene():
    return {"rooms": {"landing": {"name": "Sub-Level Three Landing",
                                  "desc": "", "adjacent": []}},
            "positions": {"Aurel": "landing"}, "entities": {}}


def test_a_room_minted_nameless_takes_its_placeholder_at_merge():
    diff = {"rooms": {"utility_core": {
        "name": "", "desc": "", "adjacent": [
            {"to": "landing", "barrier": "open", "distance": "near"}]}},
        "positions": {"Aurel": "utility_core"}}
    merged = merge_scene_with_diff(_scene(), diff)
    assert merged["rooms"]["utility_core"]["name"] == "Utility Core"
    assert merged["rooms"]["landing"]["name"] == "Sub-Level Three Landing"


def test_an_authored_name_still_displaces_the_placeholder_later():
    first = merge_scene_with_diff(
        _scene(), {"rooms": {"utility_core": {"name": "", "adjacent": []}}})
    second = merge_scene_with_diff(
        first, {"rooms": {"utility_core": {"name": "The Utility Core",
                                            "adjacent": []}}})
    assert second["rooms"]["utility_core"]["name"] == "The Utility Core"
    third = merge_scene_with_diff(
        second, {"rooms": {"utility_core": {"name": "Utility Core",
                                             "adjacent": []}}})
    assert third["rooms"]["utility_core"]["name"] == "The Utility Core", \
        "an id slug never overwrites a name someone authored"


def test_an_existing_stored_blank_is_left_to_the_reader_floor():
    sc = _scene()
    sc["rooms"]["landing"]["name"] = ""
    merged = merge_scene_with_diff(sc, {"rooms": {"landing": {"adjacent": []}}})
    assert merged["rooms"]["landing"]["name"] == ""
    assert room_display_name(merged["rooms"]["landing"], "landing") == "Landing"
