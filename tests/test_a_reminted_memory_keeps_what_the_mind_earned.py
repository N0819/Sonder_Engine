"""Re-minting a memory's `event_key` restates the event; it never erases what
the mind has since made of it.

`event_key` is the idempotency key: a writer that mints the same key again
UPDATEs the row instead of inserting (`_upsert_memory`). Several writers mint
keys that are not scoped to one turn and run again for the same mind --
`acquaintance:`, `service:` and `accused:` (`world/charter_promote.py`), the
greeting seeds, journey and charter histories, background rows. The UPDATE arm
wrote every column from the new mint, and a fresh mint carries none of the
row's later history, so (review 2026-11-01, mind_memory F7, reproduced):
importance revised 0.76 -> None, a re-reading ("It was Oren in disguise.")
-> "", and the kept feelings and `supersedes` links -> "". That later history
is the mind's own -- what the memory turned out to matter for, how it reads it
now, what it felt on looking back -- and a restatement of the event is not a
reason to forget any of it.
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory

KEY = "acquaintance:mara:stranger"
TEXT = "A stranger in a grey coat watched the ferry."


@pytest.fixture
def mind(temp_db):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))
    mara = temp_db.qi("INSERT INTO characters(name,sheet,source,created) "
                      "VALUES(?,?,?,?)", ("Mara", "{}", "{}", time.time()))
    return {"chat": chat, "mara": mara}


def _mint(mind, text=TEXT, **extra):
    data = memory.prepare_memory(mind["chat"], mind["mara"], None, "episodic",
                                 "witnessed", 0.5, text, turn_idx=1,
                                 event_key=KEY, **extra)
    full, cue, embedded = memory._embed_memory(data)
    return memory._upsert_memory(data, full, cue, embedded)


def _row(temp_db, mid):
    return dict(temp_db.q("SELECT id, importance, disputed, feelings, supersedes, "
                          "content FROM memories WHERE id=?", (mid,), one=True))


def test_a_restatement_keeps_importance_rereading_feelings_and_links(temp_db, mind):
    mid = _mint(mind)
    memory.raise_importance(mind["chat"], mind["mara"], [mid])
    memory.record_dispute(mind["chat"], mind["mara"], "", "It was Oren in disguise.",
                          5, memory_ref=KEY)
    memory.record_memory_look(mind["chat"], mind["mara"], KEY,
                              {"turn": 6, "felt": "unease", "strength": 0.6})
    temp_db.qi("UPDATE memories SET supersedes=? WHERE id=?",
               (json.dumps(["ferry:first"]), mid))
    before = _row(temp_db, mid)
    assert before["importance"] and before["disputed"] and before["feelings"]

    again = _mint(mind, TEXT + " He did not board.")
    after = _row(temp_db, again)
    assert again == mid, "one key, one row"
    assert after["content"].endswith("He did not board."), "the restatement lands"
    assert after["importance"] == before["importance"]
    assert after["disputed"] == before["disputed"]
    assert after["feelings"] == before["feelings"]
    assert after["supersedes"] == before["supersedes"]


def test_what_a_restatement_does_state_is_written(temp_db, mind):
    """The new mint's own values win where it has them -- the writer is
    restating the memory, and what it says about it is current."""
    mid = _mint(mind)
    memory.raise_importance(mind["chat"], mind["mara"], [mid])
    _mint(mind, importance=0.95, about=["Oren"])
    row = dict(temp_db.q("SELECT importance, about FROM memories WHERE id=?",
                         (mid,), one=True))
    assert row["importance"] == pytest.approx(0.95)
    assert json.loads(row["about"]) == ["Oren"]
