"""One reading of the world blob for both branch paths (review A17).

`turn_branch` remaps the LIVE `world` rows and `_remap_cp_blob` remaps the
checkpoint blob's copy of the same rows. The two had drifted on exactly one
case -- a world value that is a BARE string rather than JSON: the live side
put the branch's new id in it, the blob side left the SOURCE chat's id
alone. Since `restore_checkpoint` rewrites `world` wholesale from the blob,
the first reroll after a branch or an import undid the live remap.

Both now go through `_remap_world_values`, so the two answers cannot differ.
"""

from __future__ import annotations

import json

from web.app import _remap_cp_blob, _remap_world_values


def _remap():
    return {"entity_lamp": "newlamp", "entity_ghost": "newghost"}


def test_a_bare_string_world_value_is_remapped():
    world = {"focus_entity": "entity_lamp", "story_language": "en"}
    _remap_world_values(world, _remap())
    assert world["focus_entity"] == "newlamp"
    # A bare string that is not an id is left exactly as it was.
    assert world["story_language"] == "en"


def test_json_and_native_world_values_are_remapped():
    world = {
        "scene": json.dumps({"positions": {"entity_lamp": "hall"}}),
        "pending": [{"who": "entity_ghost"}],
    }
    _remap_world_values(world, _remap())
    assert json.loads(world["scene"])["positions"] == {"newlamp": "hall"}
    assert world["pending"] == [{"who": "newghost"}]


def test_checkpoint_blob_and_live_world_agree():
    """The defect itself: the same rows, remapped both ways, byte for byte."""
    rows = {
        "focus_entity": "entity_lamp",
        "scene": json.dumps({"positions": {"entity_ghost": "hall"}}),
        "notes": ["entity_lamp"],
        "story_language": "ja",
    }
    live = _remap_world_values(dict(rows), _remap())
    blob = _remap_cp_blob(
        {"world": dict(rows)}, turn_idmap={}, bookmap={}, fallback_canon=None,
        world_id_remap=_remap(), frame_idmap={},
    )["world"]
    assert blob == live
    assert live["focus_entity"] == "newlamp"


def test_no_remap_leaves_the_rows_untouched():
    rows = {"focus_entity": "entity_lamp"}
    assert _remap_world_values(dict(rows), {}) == rows
