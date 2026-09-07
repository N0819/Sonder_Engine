"""Review 2026-09-07 A10: a reunion carries the away party's ledgers home,
and a split partitions them by who stands where.
"""
from world.spatial_frames import _partition_scene, merge_frame_scenes


def test_the_away_partys_changes_survive_the_merge():
    parent = {"rooms": {"hall": {}, "yard": {}},
              "positions": {"A": "hall", "B": "yard"},
              "attire": {"A": {"wearing": ["coat"]}, "B": {"wearing": ["hat"]}},
              "scales": {"B": 1.0},
              "contacts": [{"actor": "A", "target": "B"}],
              "entities": {"lamp": {"name": "lamp"}}}
    child = {"rooms": {"yard": {}}, "positions": {"B": "yard", "stone": "yard"},
             "attire": {"B": {"wearing": []}}, "scales": {"B": 0.05},
             "contacts": [], "entities": {"stone": {"name": "stone"}}}
    merged = merge_frame_scenes(parent, child)
    assert merged["attire"] == {"A": {"wearing": ["coat"]}, "B": {"wearing": []}}
    assert merged["scales"] == {"B": 0.05}
    assert merged["contacts"] == [], "a contact naming the away body is the child's"
    assert set(merged["entities"]) == {"lamp", "stone"}


def test_a_split_partitions_the_subject_ledgers():
    scene = {"rooms": {"hall": {}, "yard": {}},
             "positions": {"A": "hall", "B": "yard"},
             "attire": {"A": {}, "B": {}},
             "contacts": [{"actor": "A", "target": "B"}, {"actor": "A", "target": "A"}]}
    away = _partition_scene(scene, {"B"}, {"yard"})
    assert set(away["attire"]) == {"B"}
    assert away["contacts"] == [{"actor": "A", "target": "B"}]
    stay = _partition_scene(scene, {"A"}, {"hall"})
    assert set(stay["attire"]) == {"A"} and len(stay["contacts"]) == 2
