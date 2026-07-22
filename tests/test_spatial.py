"""Tests for pure spatial reasoning functions."""

import pytest
from spatial import (
    room_of,
    has_visual,
    spatial_rel,
    hear_level,
    can_perceive,
    visible_adjacent_rooms,
    merge_scene_with_diff,
    nearby_rooms,
    normalize_room_id,
)

def test_merge_dedupes_duplicate_adjacency_in_untouched_room():
    # Regression: a room the diff does NOT re-declare is carried through the
    # merge verbatim, so a duplicate same-target edge (a neighbor that is both
    # 'wall' and 'open_door' at once -- introduced once by rename remapping)
    # otherwise persists frozen forever, feeding perception incoherent spatial
    # cues. Every merge must now collapse it, keeping the last (open_door).
    scene = {
        "rooms": {
            "station": {"name": "Station", "adjacent": [
                {"to": "checkpoint", "barrier": "wall", "distance": "near"},
                {"to": "checkpoint", "barrier": "open_door", "distance": "near"},
            ]},
            "checkpoint": {"name": "Checkpoint", "adjacent": [
                {"to": "station", "barrier": "open_door", "distance": "near"},
            ]},
        },
        "entities": {}, "positions": {},
    }
    merged = merge_scene_with_diff(scene, {})  # empty diff -> station untouched
    edges = merged["rooms"]["station"]["adjacent"]
    assert len(edges) == 1
    assert edges[0]["to"] == "checkpoint"
    assert edges[0]["barrier"] == "open_door"  # last wins, matching _merge_room


def test_none_barrier_is_normalized_to_open():
    from spatial import spatial_rel, has_visual, hear_level

    scene = {
        "rooms": {
            "genkan": {
                "adjacent": [{
                    "to": "garden",
                    "barrier": "none",
                    "distance": "close",
                }],
            },
            "garden": {
                "adjacent": [],
            },
        },
    }

    relation = spatial_rel(
        scene,
        "genkan",
        "garden",
    )

    assert relation["barrier"] == "open"
    assert has_visual(relation) is True
    assert hear_level(relation, "normal") == "full"

def test_common_barrier_synonyms_resolve_correctly():
    # A live run generated "open_doorway" for a room a character had just
    # walked through -- an unambiguous synonym for an open passage, not an
    # exotic/ambiguous barrier. Because the alias table didn't recognize
    # it, it fell through to the same "fails closed" -> wall default meant
    # for genuinely unclear barriers (see test_unknown_barrier_fails_closed
    # below), which then made director_resolve's passable-route check
    # block the player from walking back through a door they had just
    # walked through moments earlier, while the narrator (unaware of the
    # mechanical cause) narrated an unrelated in-fiction reason. Movement
    # and perception must not silently break on ordinary word-choice
    # variation for well-understood barrier concepts.
    from spatial import normalize_barrier

    assert normalize_barrier("open_doorway") == "open"
    assert normalize_barrier("open counter") == "open"
    assert normalize_barrier("padlocked_door") == "closed_door"
    assert normalize_barrier("locked door") == "closed_door"
    # A barrier that is genuinely near-impassable should still land on
    # "wall", not be over-corrected into always-passable.
    assert normalize_barrier("sealed_door") == "wall"

def test_unknown_barrier_fails_closed():
    from spatial import spatial_rel, has_visual

    scene = {
        "rooms": {
            "a": {
                "adjacent": [{
                    "to": "b",
                    "barrier": "mysterious_force",
                }],
            },
            "b": {
                "adjacent": [],
            },
        },
    }

    relation = spatial_rel(scene, "a", "b")

    assert relation["barrier"] == "wall"
    assert has_visual(relation) is False

class TestRoomOf:
    def test_exact_match(self):
        scene = {"positions": {"Alice": "kitchen", "Bob": "garden"}}
        assert room_of(scene, "Alice") == "kitchen"

    def test_case_insensitive(self):
        scene = {"positions": {"Alice": "kitchen"}}
        assert room_of(scene, "alice") == "kitchen"
        assert room_of(scene, "ALICE") == "kitchen"

    def test_punctuation_insensitive(self):
        scene = {"positions": {"Alice O'Neil": "kitchen"}}
        assert room_of(scene, "Alice ONeil") == "kitchen"
        assert room_of(scene, "alice o neil") == "kitchen"

    def test_no_match(self):
        scene = {"positions": {"Alice": "kitchen"}}
        assert room_of(scene, "Charlie") is None

    def test_empty_scene(self):
        assert room_of({"positions": {}}, "Alice") is None

    def test_empty_name(self):
        assert room_of({"positions": {"Alice": "kitchen"}}, "") is None
        assert room_of({"positions": {"Alice": "kitchen"}}, None) is None

class TestSpatialRel:
    def test_same_room(self):
        scene = {}
        rel = spatial_rel(scene, "kitchen", "kitchen")
        assert rel["same_room"] is True

    def test_adjacent_open(self):
        scene = {
            "rooms": {
                "kitchen": {
                    "adjacent": [
                        {"to": "garden", "barrier": "open", "distance": "near"}
                    ]
                }
            }
        }
        rel = spatial_rel(scene, "kitchen", "garden")
        assert rel["same_room"] is False
        assert rel["barrier"] == "open"
        assert rel["distance"] == "near"

    def test_adjacent_closed_door(self):
        scene = {
            "rooms": {
                "kitchen": {
                    "adjacent": [
                        {"to": "garden", "barrier": "closed_door"}
                    ]
                }
            }
        }
        rel = spatial_rel(scene, "kitchen", "garden")
        assert rel["barrier"] == "closed_door"

    def test_separated(self):
        scene = {"rooms": {}}
        rel = spatial_rel(scene, "kitchen", "garden")
        assert rel["same_room"] is False
        assert rel["barrier"] == "separated"
        assert rel["distance"] == "far"

    def test_fails_closed_no_room(self):
        scene = {}
        rel = spatial_rel(scene, None, "kitchen")
        assert rel["same_room"] is False
        assert rel["barrier"] == "unknown"
        assert rel["distance"] == "remote"

    def test_fails_closed_empty(self):
        scene = {}
        rel = spatial_rel(scene, "", "kitchen")
        assert rel["barrier"] == "unknown"

    def test_reverse_adjacency(self):
        scene = {
            "rooms": {
                "garden": {
                    "adjacent": [
                        {"to": "kitchen", "barrier": "wall"}
                    ]
                }
            }
        }
        rel = spatial_rel(scene, "kitchen", "garden")
        assert rel["barrier"] == "wall"

class TestHearLevel:
    def test_same_room_full(self):
        rel = {"same_room": True}
        for vol in ("whisper", "mutter", "normal", "loud", "shout"):
            assert hear_level(rel, vol) == "full"

    def test_open_door_normal(self):
        rel = {"same_room": False, "barrier": "open"}
        assert hear_level(rel, "normal") == "full"
        assert hear_level(rel, "loud") == "full"
        assert hear_level(rel, "shout") == "full"

    def test_open_door_whisper(self):
        rel = {"same_room": False, "barrier": "open"}
        assert hear_level(rel, "whisper") == "none"

    def test_open_door_mutter(self):
        rel = {"same_room": False, "barrier": "open"}
        assert hear_level(rel, "mutter") == "fragment"

    def test_closed_door_normal(self):
        rel = {"same_room": False, "barrier": "closed_door"}
        assert hear_level(rel, "normal") == "fragment"
        assert hear_level(rel, "loud") == "full"
        assert hear_level(rel, "shout") == "full"
        assert hear_level(rel, "whisper") == "none"
        assert hear_level(rel, "mutter") == "none"

    def test_wall(self):
        rel = {"same_room": False, "barrier": "wall"}
        assert hear_level(rel, "normal") == "none"
        assert hear_level(rel, "shout") == "fragment"
        assert hear_level(rel, "loud") == "none"

    def test_vouched(self):
        rel = {"same_room": False, "barrier": "unknown", "distance": "remote"}
        assert hear_level(rel, "loud", vouched=True) == "fragment"
        assert hear_level(rel, "shout", vouched=True) == "fragment"
        assert hear_level(rel, "normal", vouched=True) == "none"
        assert hear_level(rel, "mutter", vouched=True) == "none"
        assert hear_level(rel, "whisper", vouched=True) == "none"

    def test_remote_never_bypasses_physics(self):
        rel = {"same_room": False, "barrier": "unknown", "distance": "remote"}
        for volume in ("whisper", "mutter", "normal", "loud", "shout"):
            assert hear_level(rel, volume) == "none"

class TestHasVisual:
    def test_same_room(self):
        assert has_visual({"same_room": True}) is True

    def test_open(self):
        assert has_visual({"same_room": False, "barrier": "open"}) is True

    def test_open_door(self):
        assert has_visual({"same_room": False, "barrier": "open_door"}) is True

    def test_closed_door(self):
        assert has_visual({"same_room": False, "barrier": "closed_door"}) is False

    def test_wall(self):
        assert has_visual({"same_room": False, "barrier": "wall"}) is False

    def test_unknown(self):
        assert has_visual({"same_room": False, "barrier": "unknown"}) is False

class TestNearbyRooms:
    # A linear chain a-b-c-d-e, each room only declaring the edge to its
    # forward neighbor (b doesn't declare a reverse edge back to a, etc.)
    # -- mirroring how a model often only states one direction.
    _CHAIN_SCENE = {
        "rooms": {
            "a": {"adjacent": [{"to": "b"}]},
            "b": {"adjacent": [{"to": "c"}]},
            "c": {"adjacent": [{"to": "d"}]},
            "d": {"adjacent": [{"to": "e"}]},
            "e": {"adjacent": []},
        },
    }

    def test_one_hop_includes_center_and_immediate_neighbors(self):
        result = nearby_rooms(self._CHAIN_SCENE, {"c"}, hops=1)
        assert set(result.keys()) == {"b", "c", "d"}

    def test_two_hops_extends_reach(self):
        result = nearby_rooms(self._CHAIN_SCENE, {"c"}, hops=2)
        assert set(result.keys()) == {"a", "b", "c", "d", "e"}

    def test_zero_hops_returns_only_centers(self):
        result = nearby_rooms(self._CHAIN_SCENE, {"c"}, hops=0)
        assert set(result.keys()) == {"c"}

    def test_adjacency_is_treated_as_undirected(self):
        # "a" only has a forward edge to "b"; a center at "b" must still
        # reach "a" even though "b" declares no edge back to "a".
        result = nearby_rooms(self._CHAIN_SCENE, {"b"}, hops=1)
        assert "a" in result

    def test_multiple_centers_union_their_neighborhoods(self):
        result = nearby_rooms(self._CHAIN_SCENE, {"a", "e"}, hops=1)
        assert set(result.keys()) == {"a", "b", "d", "e"}

    def test_disconnected_room_is_excluded(self):
        scene = {
            "rooms": {
                "a": {"adjacent": [{"to": "b"}]},
                "b": {"adjacent": []},
                "far_away_room": {"adjacent": []},
            },
        }
        result = nearby_rooms(scene, {"a"}, hops=5)
        assert "far_away_room" not in result

    def test_unknown_center_is_ignored_without_error(self):
        result = nearby_rooms(self._CHAIN_SCENE, {"nonexistent"}, hops=1)
        assert result == {}

class TestVisibleAdjacentRooms:
    def test_forward_adjacency(self):
        scene = {
            "rooms": {
                "kitchen": {
                    "adjacent": [
                        {"to": "garden", "barrier": "open"}
                    ]
                },
                "garden": {
                    "name": "Garden",
                    "notes": "A lush garden with roses.",
                },
            }
        }
        visible = visible_adjacent_rooms(scene, "kitchen")
        assert len(visible) == 1
        assert visible[0]["room_id"] == "garden"
        assert visible[0]["room_name"] == "Garden"
        assert "roses" in visible[0]["description"]

    def test_reverse_adjacency(self):
        scene = {
            "rooms": {
                "garden": {
                    "adjacent": [
                        {"to": "kitchen", "barrier": "open_door"}
                    ]
                },
                "kitchen": {
                    "name": "Kitchen",
                    "notes": "A small kitchen.",
                },
            }
        }
        visible = visible_adjacent_rooms(scene, "kitchen")
        assert len(visible) == 1
        assert visible[0]["room_id"] == "garden"

    def test_closed_door_not_visible(self):
        scene = {
            "rooms": {
                "kitchen": {
                    "adjacent": [
                        {"to": "garden", "barrier": "closed_door"}
                    ]
                },
                "garden": {"notes": "A garden."},
            }
        }
        visible = visible_adjacent_rooms(scene, "kitchen")
        assert len(visible) == 0

    def test_wall_not_visible(self):
        scene = {
            "rooms": {
                "kitchen": {
                    "adjacent": [{"to": "garden", "barrier": "wall"}]
                },
                "garden": {"notes": "A garden."},
            }
        }
        visible = visible_adjacent_rooms(scene, "kitchen")
        assert len(visible) == 0

    def test_no_adjacent_rooms(self):
        scene = {"rooms": {"kitchen": {"adjacent": []}}}
        assert visible_adjacent_rooms(scene, "kitchen") == []

    def test_empty_room_id(self):
        assert visible_adjacent_rooms({}, "") == []
        assert visible_adjacent_rooms({}, None) == []

    def test_merge_extra_rooms(self):
        scene = {"rooms": {"kitchen": {"adjacent": []}}}
        extra = {
            "garden": {
                "name": "Garden",
                "notes": "Newly created garden.",
                "adjacent": [{"to": "kitchen", "barrier": "open"}],
            }
        }
        visible = visible_adjacent_rooms(scene, "kitchen", extra_rooms=extra)
        assert len(visible) == 1
        assert visible[0]["room_id"] == "garden"

class TestMergeSceneWithDiff:
    def test_merge_rooms(self):
        scene = {"rooms": {"kitchen": {"name": "Kitchen"}}}
        diff = {"rooms": {"garden": {"name": "Garden"}}}
        merged = merge_scene_with_diff(scene, diff)
        assert "kitchen" in merged["rooms"]
        assert "garden" in merged["rooms"]

    def test_merge_positions(self):
        scene = {"positions": {"Alice": "kitchen"}}
        diff = {"positions": {"Bob": "garden"}}
        merged = merge_scene_with_diff(scene, diff)
        assert merged["positions"]["Alice"] == "kitchen"
        assert merged["positions"]["Bob"] == "garden"

    def test_no_diff(self):
        scene = {
            "rooms": {"kitchen": {}},
            "positions": {"Alice": "kitchen"},
        }
        merged = merge_scene_with_diff(scene, None)
        assert scene["rooms"] == {"kitchen": {}}
        assert merged["rooms"] == {"kitchen": {"adjacent": []}}
        assert merged["rooms"]["kitchen"] is not scene["rooms"]["kitchen"]
        assert merged["positions"] == scene["positions"]

    def test_redeclaring_a_room_preserves_untouched_edges(self):
        # Reproduces a live bug: generating a new west-wing connection off
        # an existing corridor, the director redeclared "main_corridor"
        # with only the new edge, wiping out its existing edges to the
        # entrance hall and a stairwell (dict.update replaces the whole
        # room object per key, not a deep merge). A room redeclaration
        # must only be allowed to ADD/UPDATE edges the model actually
        # mentions; edges it stays silent about must survive.
        scene = {
            "rooms": {
                "main_corridor": {
                    "name": "Main Corridor",
                    "adjacent": [
                        {"to": "entrance_hall", "barrier": "closed_door", "distance": "close"},
                        {"to": "basement_stairwell", "barrier": "closed_door", "distance": "far"},
                    ],
                },
            },
        }
        diff = {
            "rooms": {
                "main_corridor": {
                    "name": "Main Corridor",
                    "adjacent": [
                        {"to": "west_wing_entry", "barrier": "closed_door", "distance": "close"},
                    ],
                },
            },
        }

        merged = merge_scene_with_diff(scene, diff)
        targets = {e["to"] for e in merged["rooms"]["main_corridor"]["adjacent"]}

        assert targets == {"entrance_hall", "basement_stairwell", "west_wing_entry"}

    def test_redeclaring_a_room_can_update_an_existing_edge(self):
        scene = {
            "rooms": {
                "hall": {"adjacent": [{"to": "study", "barrier": "closed_door", "distance": "near"}]},
            },
        }
        diff = {
            "rooms": {
                "hall": {"adjacent": [{"to": "study", "barrier": "open", "distance": "near"}]},
            },
        }

        merged = merge_scene_with_diff(scene, diff)
        edges = merged["rooms"]["hall"]["adjacent"]

        assert len(edges) == 1
        assert edges[0]["barrier"] == "open"

    def test_new_room_is_unaffected_by_merge_logic(self):
        scene = {"rooms": {}}
        diff = {"rooms": {"garden": {"name": "Garden", "adjacent": []}}}

        merged = merge_scene_with_diff(scene, diff)

        assert merged["rooms"]["garden"] == {"name": "Garden", "adjacent": []}

    def test_remove_adjacent_explicitly_severs_an_edge(self):
        scene = {
            "rooms": {
                "hall": {
                    "adjacent": [
                        {"to": "study", "barrier": "closed_door", "distance": "near"},
                        {"to": "kitchen", "barrier": "open", "distance": "near"},
                    ],
                },
            },
        }
        diff = {"remove_adjacent": [{"room": "hall", "to": "study"}]}

        merged = merge_scene_with_diff(scene, diff)
        targets = {e["to"] for e in merged["rooms"]["hall"]["adjacent"]}

        assert targets == {"kitchen"}

class TestNormalizeRoomId:
    def test_basic(self):
        assert normalize_room_id("The Grand Hall") == "the_grand_hall"

    def test_punctuation(self):
        assert normalize_room_id("St. Mary's Church") == "st_mary_s_church"

    def test_extra_spaces(self):
        assert normalize_room_id("  Multiple   Spaces  ") == "multiple_spaces"

    def test_empty(self):
        assert normalize_room_id("") == ""
        assert normalize_room_id(None) == ""

    def test_numbers(self):
        assert normalize_room_id("Room 101") == "room_101"