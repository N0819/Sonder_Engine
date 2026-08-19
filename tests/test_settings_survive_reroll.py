"""Reader settings are not turn-scoped facts and must survive a reroll.

Reported live: NPC autonomy, background life, prose pacing and the style
guide "reset every single time you branch or reroll a turn after setting
them".

Cause: they live in the chat-scoped `world` KV table, which is exactly what
checkpoints snapshot and what restore wipes and re-inserts. Turn a dial at
turn 60 and reroll turn 60 and the dial springs back -- the checkpoint
predates the change, so the change was never in it. A reroll is supposed to
re-run the beat, not undo your preferences; nothing in the fiction depends
on which pacing the reader likes.
"""

from __future__ import annotations

import json
import time

from persist.checkpoints import (PRESERVED_SETTING_KEYS, ensure_checkpoint,
                         restore_checkpoint, _preserved_settings)


def _chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))


def test_a_setting_changed_after_the_checkpoint_survives_reroll(temp_db):
    cid = _chat(temp_db)
    temp_db.wset(cid, "dialogue_config", {"autonomy": 50, "max_lines": 4})
    temp_db.wset(cid, "scene", {"rooms": {}, "positions": {}})
    ensure_checkpoint(cid, 1)

    # The reader turns the dials up AFTER that checkpoint was taken...
    temp_db.wset(cid, "dialogue_config", {"autonomy": 90, "max_lines": 8})
    temp_db.wset(cid, "background_config", {"scene_life": "full"})
    temp_db.wset(cid, "style_guide", {"genre": "horror"})
    # ...and something in the fiction also moved.
    temp_db.wset(cid, "scene", {"rooms": {"crypt": {}}, "positions": {}})

    restore_checkpoint(cid, 1)

    # Settings stand...
    assert temp_db.wget(cid, "dialogue_config", {})["autonomy"] == 90
    assert temp_db.wget(cid, "background_config", {})["scene_life"] == "full"
    assert temp_db.wget(cid, "style_guide", {})["genre"] == "horror"
    # ...while the fiction is rolled back, which is the point of a reroll.
    assert temp_db.wget(cid, "scene", {})["rooms"] == {}


def test_settings_absent_now_still_come_from_the_snapshot(temp_db):
    """A fresh chat (branch, import) has no live settings, so it must still
    inherit whatever the snapshot carries rather than end up with none."""
    cid = _chat(temp_db)
    temp_db.wset(cid, "dialogue_config", {"autonomy": 70})
    temp_db.wset(cid, "scene", {"rooms": {}})
    ensure_checkpoint(cid, 1)

    temp_db.qi("DELETE FROM world WHERE chat_id=? AND key='dialogue_config'",
               (cid,))
    assert _preserved_settings(cid) == {}

    restore_checkpoint(cid, 1)
    assert temp_db.wget(cid, "dialogue_config", {})["autonomy"] == 70


def test_an_unreadable_setting_says_so_before_the_rollback_takes_it(
    temp_db, caplog,
):
    """A setting that cannot be read is not a setting that is absent.

    An absent key is the branch/import case and correctly falls through to
    the snapshot. A key that EXISTS and will not parse is the one case where
    the restore does the exact thing this list was built to prevent: the
    checkpoint's older dial wins and the reader's own value is gone. Doing it
    quietly makes it indistinguishable from the dial never having been
    changed.
    """
    import logging

    cid = _chat(temp_db)
    temp_db.wset(cid, "scene", {"rooms": {}})
    temp_db.wset(cid, "style_guide", {"genre": "noir"})
    ensure_checkpoint(cid, 1)

    temp_db.qi("UPDATE world SET value=? WHERE chat_id=? AND key='style_guide'",
               ("{not json", cid))

    with caplog.at_level(logging.WARNING):
        assert _preserved_settings(cid) == {}
    assert any("style_guide" in record.getMessage()
               for record in caplog.records), caplog.text


def test_ordinary_world_state_is_still_rolled_back(temp_db):
    """The preserve list is deliberately narrow -- it must not turn into a
    general escape hatch that leaks turn state past a rollback."""
    cid = _chat(temp_db)
    temp_db.wset(cid, "scene", {"rooms": {}})
    temp_db.wset(cid, "pending", [])
    ensure_checkpoint(cid, 1)

    temp_db.wset(cid, "pending", [{"obligation": "answer the door"}])
    restore_checkpoint(cid, 1)

    assert temp_db.wget(cid, "pending", None) == []
    assert "pending" not in PRESERVED_SETTING_KEYS
