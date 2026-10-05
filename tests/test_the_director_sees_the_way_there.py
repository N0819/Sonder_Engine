"""The Director routes a body by the world's ways, so it is shown them.

Live, Larch Hill turn 3 (chat 165, 2026-10-04): '"Show me the watch cabin,"
and I start up the steep stairs, all the way to the top.' The Director's
world index was the actors' sight aperture -- the store room, the kitchen,
the ground at the tower's foot -- its exits bare ids. The watch cabin and the
stair to it were two rooms off and nowhere in it, so a rerun sent the climb
out of the door to the short steps at the tower's foot, the only steps it
could see, and the page climbed stairs up the outside of a tower whose stair
runs inside. The decision model's "places already known" was the same slice,
so a room two rooms off read as a new place to build.
"""

from __future__ import annotations

import json

from agents.director import causal_room_names, causal_scene_room_ids, causal_world_index


def _lookout():
    def room(name, level, edges, **extra):
        return {"name": name, "level": level, "extent": {"w": 5, "d": 4},
                "adjacent": edges, **extra}
    return {
        "rooms": {
            "tower_foot": room("The Foot of the Lookout", 0, [
                {"to": "store_room", "barrier": "open_door", "dir": "n", "name": "the tower door"}],
                exposure="open", anchors={"tower_steps": {"desc": "short steps up to the door"}}),
            "store_room": room("The Store Room", 0, [
                {"to": "tower_foot", "barrier": "open_door", "dir": "s", "name": "the tower door"},
                {"to": "kitchen", "barrier": "open", "dir": "e", "name": "the inner way"}]),
            "kitchen": room("The Kitchen", 0, [
                {"to": "store_room", "barrier": "open", "dir": "w", "name": "the inner way"},
                {"to": "sleeping_room", "vertical": "up", "way": "stair", "barrier": "open",
                 "dir": "n", "name": "the steep stair"}]),
            "sleeping_room": room("The Sleeping Room", 1, [
                {"to": "kitchen", "vertical": "down", "way": "stair", "barrier": "open",
                 "dir": "s", "name": "the steep stair"},
                {"to": "watch_cabin", "vertical": "up", "way": "stair", "barrier": "open",
                 "dir": "n", "name": "the steep stair"}]),
            "watch_cabin": room("The Watch Cabin", 2, [
                {"to": "sleeping_room", "vertical": "down", "way": "stair", "barrier": "open",
                 "dir": "s", "name": "the steep stair"}]),
            "cart_bed": room("The Cart's Bed", 0, [], parent_entity="cart"),
        },
        "positions": {"Ren": "store_room", "Keeper": "watch_cabin", "cart": "tower_foot"},
        "entities": {"cart": {"name": "the hand cart", "kind": "vehicle"}},
    }


def _index():
    sc = _lookout()
    aperture = causal_scene_room_ids(sc, ["Ren"])
    assert {"sleeping_room", "watch_cabin"}.isdisjoint(aperture)   # two rooms off
    return causal_world_index(sc, here="store_room", room_ids=aperture,
                              include_entity_interiors=True)


def test_the_rest_of_the_map_is_shown_without_what_it_holds():
    far = _index()["elsewhere"]
    assert far["watch_cabin"]["name"] == "The Watch Cabin" and far["watch_cabin"]["level"] == 2
    assert far["sleeping_room"]["exits"] == ["kitchen", "watch_cabin"]
    for row in far.values():
        assert "holds" not in row and "features" not in row
    assert "Keeper" not in json.dumps(far)


def test_a_stair_is_shown_as_the_way_it_is_taken():
    index = _index()
    assert index["rooms"]["kitchen"]["ways"]["sleeping_room"] == {
        "way": "stair", "vertical": "up", "name": "the steep stair"}
    assert index["elsewhere"]["watch_cabin"]["ways"]["sleeping_room"]["vertical"] == "down"
    assert index["rooms"]["store_room"]["ways"]["tower_foot"] == {"name": "the tower door"}


def test_the_inside_of_a_thing_is_not_a_place_on_the_map():
    assert "cart_bed" not in _index()["elsewhere"]


def test_every_place_the_world_holds_is_already_known():
    from agents.director_prose import _jev_state
    names = causal_room_names(_index())
    assert names["watch_cabin"] == "The Watch Cabin"
    assert "The Watch Cabin" in _jev_state("They climb.", {"object_index": {"rooms": names}})


def test_an_unsliced_index_has_every_room_and_no_elsewhere():
    index = causal_world_index(_lookout())
    assert "elsewhere" not in index and "watch_cabin" in index["rooms"]


def test_both_director_cards_say_the_way_is_the_worlds():
    from llm.prompts import prose_contract_text
    for language in ("en", "ja"):
        for stage in ("interpret", "resolve"):
            text = prose_contract_text(f"director_{stage}", language)
            assert "elsewhere" in text and "ways" in text, (language, stage)
