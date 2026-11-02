"""A rewind keeps the dials the host turned, `reaction_config` among them.

`checkpoints.SETTING_PROVENANCE` names the world keys that are a dial rather
than story state, and a restore carries those across. `reaction_config` --
the contested-reaction loop's switch and budgets (`story.scene.
reaction_config`) -- is written by no turn, only by the host, and was missing
from it, so every reroll put back the checkpoint's value and silently undid
the host's change (audit 2026-11-01, persistence F17; the same shape as the
registered `promotion_thresholds`).

The class: a `*_config` world key is a dial by the engine's own naming, so
every one the engine READS must be declared set by hand -- the guard below
fails for the next one added without it.
"""

from __future__ import annotations

import pathlib
import re
import time

from core.db import wget, wset
from persist.checkpoints import (SET_BY_HAND, SETTING_PROVENANCE,
                                 ensure_checkpoint, restore_checkpoint)

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = ("core", "llm", "world", "mind", "story", "dressing", "persist", "web",
          "agents", "extension_runtime")
_READ = re.compile(r"""wget(?:_for_frame)?\([^,()]+,\s*["']([a-z_]+_config)["']""")


def test_a_reroll_keeps_a_hand_set_reaction_config(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Dials", "", time.time()))
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
               (cid, 0, "begin", time.time()))
    wset(cid, "reaction_config", {"enabled": False})
    ensure_checkpoint(cid, 0)
    wset(cid, "reaction_config", {"enabled": True, "max_rounds": 2})

    restore_checkpoint(cid, 0)

    assert wget(cid, "reaction_config") == {"enabled": True, "max_rounds": 2}


def test_every_config_dial_the_engine_reads_is_declared_set_by_hand():
    read = set()
    for package in ENGINE:
        for path in (ROOT / package).rglob("*.py"):
            read.update(_READ.findall(path.read_text(encoding="utf-8")))
    assert read, "the scan found no config dial at all -- the pattern is stale"
    undeclared = sorted(k for k in read if SETTING_PROVENANCE.get(k) != SET_BY_HAND)
    assert undeclared == [], (
        f"{undeclared}: a dial a rewind would roll back. Declare it in "
        "persist/checkpoints.SETTING_PROVENANCE.")
