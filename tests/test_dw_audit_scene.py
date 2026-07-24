"""Regression tests for two scene-truth findings from the Doctor Who paradox run.

DW-4: an auto-created entity ended up in `positions` under BOTH its id key and
its display-name key, co-present in two rooms. DW-1: after a relocation to a new
place, the top-level `scene.location` label stayed stale and leaked the departed
location's name into perception/narration.
"""

from __future__ import annotations

import commit
from spatial import merge_scene_with_diff, _dedup_duplicate_position_keys


# ---- DW-4: duplicate position keys ----

def test_id_and_name_position_keys_collapse_to_the_fresh_write():
    prev = {"entities": {"karen_marsh": {"name": "Karen Marsh"}},
            "positions": {"karen_marsh": "road", "Ellie Marsh": "road"}}
    diff = {"positions": {"Karen Marsh": "tardis", "Ellie Marsh": "tardis"}}
    merged = merge_scene_with_diff(prev, diff)
    assert "karen_marsh" not in merged["positions"]
    assert merged["positions"]["Karen Marsh"] == "tardis"  # fresh write wins


def test_a_lone_object_id_key_is_never_touched():
    """An object with only an id-keyed position (no name twin) must survive."""
    prev = {"entities": {"tardis": {"name": "TARDIS"}},
            "positions": {"tardis": "road", "Ellie Marsh": "road"}}
    merged = merge_scene_with_diff(prev, {"positions": {"Ellie Marsh": "hall"}})
    assert merged["positions"]["tardis"] == "road"


def test_dedup_prefers_name_key_when_neither_is_the_fresh_write():
    positions = {"karen_marsh": "road", "Karen Marsh": "tardis"}
    entities = {"karen_marsh": {"name": "Karen Marsh"}}
    _dedup_duplicate_position_keys(positions, entities, incoming_positions={})
    assert "karen_marsh" not in positions
    assert positions["Karen Marsh"] == "tardis"


def test_entity_without_a_name_is_ignored():
    positions = {"blob": "road"}
    entities = {"blob": {}}
    out = _dedup_duplicate_position_keys(positions, entities, {})
    assert out == {"blob": "road"}


# ---- DW-1: stale location label on relocation ----

def _ctx(monkeypatch, player="Ellie Marsh"):
    import scene
    monkeypatch.setattr(scene, "persona_of",
                        lambda c: {"identity": {"name": player}}, raising=False)
    monkeypatch.setattr(commit, "persona_name", lambda p: player)

    class _Ctx:
        chat = {"id": 1}
    return _Ctx()


def test_location_refreshes_on_move_to_a_new_room(monkeypatch):
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bute_street": {"name": "Bute Street"}},
            "location": "Alley off Bute Street, Cardiff"}
    sc = {"rooms": {"bute_street": {"name": "Bute Street"},
                    "Bethnal_Green_Road": {"name": "Bethnal Green Road"}},
          "positions": {"Ellie Marsh": "Bethnal_Green_Road"},
          "location": "Alley off Bute Street, Cardiff"}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "Bethnal Green Road"


def test_director_named_location_is_preferred(monkeypatch):
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bute_street": {"name": "Bute Street"}}, "location": "Cardiff"}
    sc = {"rooms": {"bute_street": {"name": "Bute Street"},
                    "bgr": {"name": "Bethnal Green Road"}},
          "positions": {"Ellie Marsh": "bgr"}, "location": "Cardiff"}
    commit._refresh_relocated_location(sc, prev, {"location": "East London, 2003"}, ctx)
    assert sc["location"] == "East London, 2003"


def test_same_place_move_leaves_the_label_untouched(monkeypatch):
    """Moving between rooms that already existed is not a relocation."""
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bar": {"name": "Bar"}, "kitchen": {"name": "Kitchen"}},
            "location": "The Old Anchor"}
    sc = {"rooms": {"bar": {"name": "Bar"}, "kitchen": {"name": "Kitchen"}},
          "positions": {"Ellie Marsh": "kitchen"}, "location": "The Old Anchor"}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "The Old Anchor"


def test_no_player_room_leaves_the_label_untouched(monkeypatch):
    ctx = _ctx(monkeypatch)
    sc = {"rooms": {}, "positions": {}, "location": "Somewhere"}
    commit._refresh_relocated_location(sc, {"rooms": {}}, {}, ctx)
    assert sc["location"] == "Somewhere"
