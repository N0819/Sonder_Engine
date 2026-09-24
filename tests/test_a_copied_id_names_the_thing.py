"""An entity the encoder writes under an id it copied wrong is still the
thing it meant.

The owner's chat 154 turn 4398 resolve call, re-sent 2026-09-24 (GLM 5.2,
reasoning off): all six transits the encoder wrote for the TARDIS across
twelve samples were keyed with a slip -- `75bd6ac12fa14a5d`, `...14a7d` --
for `75bd6ac12fa14e7d`. The merge files such a write as a new, nameless
entity, so the ship stays on the beach while a phantom flies. The
transform's `item` is the encoder's own name for the thing, and it vouches
for the key; nothing it cannot vouch for is moved onto a thing.
"""

from __future__ import annotations

from agents import director_prose
from world.spatial import merge_scene_with_diff

TARDIS = "75bd6ac12fa14e7d"
CONSOLE = "91f236af51424e31"


def _scene():
    return {
        "rooms": {"moonlit_beach": {"name": "Moonlit Beach", "adjacent": []}},
        "entities": {
            TARDIS: {"name": "The TARDIS", "kind": "object", "aliases": ["the ship"]},
            CONSOLE: {"name": "central console", "kind": "fixture"},
            "The Doctor": {"name": "The Doctor", "kind": "person"},
        },
        "positions": {TARDIS: "moonlit_beach"},
    }


def _written(item, key, record):
    return {"event": "The TARDIS commits.",
            "transforms": [{"item": item, "patch": {"entities": {key: record}}}]}


def _keys(events):
    return [key for event in events for transform in event["transforms"]
            for key in transform["patch"]["entities"]]


TRANSIT = {"state": {"transit": {"phase": "in_transit", "hatch": "closed"}}}


def test_a_slipped_copy_of_an_id_is_the_thing_its_item_names():
    warned = []
    events = [_written("The TARDIS", "75bd6ac12fa14a5d", TRANSIT),
              _written("the ship", "75bd6ac12fa14a7d", TRANSIT),   # an alias
              _written("The TARDIS", "the_tardis", TRANSIT)]       # a name as key
    out = director_prose.entity_keys_name_held_things(events, _scene(), warn=warned.append)
    assert _keys(out) == [TARDIS, TARDIS, TARDIS]
    assert len(warned) == 3 and all("read as" in w for w in warned)
    merged = merge_scene_with_diff(_scene(), out[0]["transforms"][0]["patch"])
    assert merged["entities"][TARDIS]["state"]["transit"]["phase"] == "in_transit"
    assert "75bd6ac12fa14a5d" not in merged["entities"]


def test_what_the_item_cannot_vouch_for_is_left_as_written():
    warned = []
    events = [
        # the item names a different thing: never moved onto The Doctor
        _written("The Doctor", "91f236af51424a31", {"state": {"lit": True}}),
        # too many slips to be a copy of the console's id
        _written("central console", "91f236af5142ffff", {"state": {"lit": True}}),
        # an item naming nothing held
        _written("the doors", "75bd6ac12fa14a5d", TRANSIT),
    ]
    out = director_prose.entity_keys_name_held_things(events, _scene(), warn=warned.append)
    assert _keys(out) == ["91f236af51424a31", "91f236af5142ffff", "75bd6ac12fa14a5d"]
    assert len(warned) == 1 and "filed as written" in warned[0]


def test_a_new_thing_and_its_later_writes_are_never_rekeyed():
    minted = {"name": "the TARDIS key", "kind": "object"}
    events = [_written("The TARDIS", "75bd6ac12fa14a5d", minted),     # a mint
              _written("The TARDIS", "75bd6ac12fa14a5d", TRANSIT),    # its own key now
              _written("The TARDIS", TARDIS, TRANSIT)]                # held
    out = director_prose.entity_keys_name_held_things(events, _scene())
    assert _keys(out) == ["75bd6ac12fa14a5d", "75bd6ac12fa14a5d", TARDIS]
    assert out == events


def test_a_slip_and_the_right_id_in_one_patch_merge():
    events = [{"event": "e", "transforms": [{"item": "The TARDIS", "patch": {"entities": {
        TARDIS: {"state": {"running": True}},
        "75bd6ac12fa14a5d": {"state": {"transit": {"phase": "in_transit"}}}}}}]}]
    out = director_prose.entity_keys_name_held_things(events, _scene())
    assert out[0]["transforms"][0]["patch"]["entities"] == {
        TARDIS: {"state": {"running": True, "transit": {"phase": "in_transit"}}}}
