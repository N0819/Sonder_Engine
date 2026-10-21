"""A place no walk from here reaches is a locale of its own, and nothing
invents a doorway onto it.

The control story (2026-10-20, chat 1 idx 3): Pell promised to post a
letter "in Harrow Street, by the post office on the quay", and the room
designer was asked to build the street. Its first step said exactly the
right thing -- "a disconnected locale (the mainland, nine kilometres east
across the water), so it gets its own zone ... No doorway to the rock" --
and its `draft_room` call left the `zone` field out. The plan the engine
drew back already showed a doorway to `tower_foot` it had not drawn: the
merge heals a fresh room no edge reaches by opening it onto the room the
bodies stood in (`spatial_merge.connect_orphan_new_rooms`), and all three
bodies stood at the tower's foot. The check then said so ("Left joined to
nothing, the engine opens it onto the room the bodies stood in"), and the
designer joined the street to the tower's foot as a `far` way "without
pretending it is beside the tower" -- which every reader then treated as a
doorway next door (`tests/test_a_way_that_covers_ground.py`).

Two halves, one class. The engine's: a room whose `zone` says no walk
reaches it is not an island to heal onto another locale -- the designer's
own check already accepts such a place with no doorway
(`director_rooms._no_way_in`), and the merge undid that answer. The
model's, which is a sentence: a way of any distance is a walk, so a place
no walk reaches joins none of the rooms here and carries its `zone`.
"""

from __future__ import annotations

import pytest

from llm.prompts import room_author_prompt
from world.spatial import merge_scene_with_diff, spatial_rel

ROCK = {
    "rooms": {
        "landing": {"name": "The Landing", "exposure": "open",
                    "adjacent": [{"to": "tower_foot", "barrier": "open"}]},
        "tower_foot": {"name": "The Tower Foot", "exposure": "enclosed",
                       "adjacent": [{"to": "landing", "barrier": "open"}]},
    },
    "positions": {"Rhona Carrick": "tower_foot", "Elias Thorne": "tower_foot",
                  "Pell Hardacre": "tower_foot"},
    "entities": {},
}

STREET = {"name": "Harrow Street", "exposure": "open", "size": "medium",
          "adjacent": []}


def _edges_between(scene, a, b):
    return [e for x, y in ((a, b), (b, a))
            for e in (scene["rooms"][x].get("adjacent") or [])
            if isinstance(e, dict) and e.get("to") == y]


def test_a_zoned_place_is_not_opened_onto_the_rock():
    """The street as the designer meant it -- its own zone, no doorway --
    merges as it was drawn: no way between it and the tower's foot, where
    the healer opened one before. An unzoned island is still healed, which
    is the floor chat 58's plaza needed; and a zoned island beside a room of
    its own zone is healed onto that room as any island is."""
    meant = merge_scene_with_diff(ROCK, {"rooms": {
        "harrow_street": dict(STREET, zone="mainland")}})
    assert _edges_between(meant, "harrow_street", "tower_foot") == []
    assert meant["rooms"]["harrow_street"].get("adjacent") == []
    rel = spatial_rel(meant, "tower_foot", "harrow_street")
    assert rel["barrier"] != "open", "no air was invented between them"

    unzoned = merge_scene_with_diff(ROCK, {"rooms": {"harrow_street": dict(STREET)}})
    assert [e["to"] for e in unzoned["rooms"]["harrow_street"]["adjacent"]] == ["tower_foot"]

    quay = {"rooms": {"quay": {"name": "The Quay", "zone": "mainland",
                               "exposure": "open", "adjacent": []}},
            "positions": {"Pell Hardacre": "quay"}, "entities": {}}
    built = merge_scene_with_diff(quay, {"rooms": {
        "harrow_street": dict(STREET, zone="mainland")}})
    assert [e["to"] for e in built["rooms"]["harrow_street"]["adjacent"]] == ["quay"]


@pytest.mark.parametrize("language, clause", [
    ("en", "Every way you draw is a walk, however far it runs: a place no walk "
           "from these rooms could reach joins none of them, and its record "
           "carries a `zone` naming the locale it lies in."),
    ("ja", "あなたが描く道は、どれほど遠くまで続いても、どれも歩いて通る道です。"
           "ここの room から歩いては着けない場所は、そのどれにもつながらず、"
           "その記録には、それがある場所を名指す `zone` を書きます。"),
])
def test_the_room_designer_is_told_a_far_way_is_a_walk(language, clause):
    """The designer's sheet states the class it misread: a `far` way is a
    walk however far, so a place no walk reaches carries its `zone` and joins
    none of the rooms around it. Both packs, word for word."""
    assert clause in room_author_prompt(language)
