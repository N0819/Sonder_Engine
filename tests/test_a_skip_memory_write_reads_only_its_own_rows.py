"""A skip-memory write reads back only the rows it wrote.

`skip_memories.write_rows` writes one mind's memories of a skip inside ONE
transaction -- the write lock the next beat's commit waits on -- and, when a
later checkpoint exists, carries them forward. To pick out those rows it
dumped the WHOLE chat's memory bank, every character's, once per mind, and
kept the at most eight it had just written (review 2026-11-01,
mind_affect_psychology E2): O(bank) work under the lock, multiplied by the
cast, in the window the module itself expects the next beat to start in.
"""

from __future__ import annotations

import time

from mind import memory, skip_memories


def test_the_carry_dumps_the_written_rows_alone(temp_db, monkeypatch):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))
    ilse = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                      ("Ilse", "{}", "{}", time.time()))
    oren = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                      ("Oren", "{}", "{}", time.time()))
    turn = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                      (chat, 4, "", time.time()))
    for t in range(1, 30):
        memory.add_memory(chat, oren, None, "episodic", "witnessed", 0.5,
                          f"Oren mended a net on day {t}.", turn_idx=t, event_key=f"net:{t}")
    # The next beat has begun: a later checkpoint exists, so the carry runs.
    temp_db.qi("INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
               (chat, 5, "{}", time.time()))
    monkeypatch.setattr(skip_memories, "still_committed", lambda *a: True)
    asked, carried = {}, {}
    real_dump = skip_memories.dump_chat_memories

    def dump(chat_id, **kw):
        asked.update(kw)
        return real_dump(chat_id, **kw)

    def carry(chat_id, turn_idx, mine, entries):
        carried["entries"] = entries
    monkeypatch.setattr(skip_memories, "dump_chat_memories", dump)
    monkeypatch.setattr("persist.checkpoints.carry_memories_forward", carry)

    rows = [{"chat_id": chat, "char_id": ilse, "turn_id": turn, "kind": "episodic",
             "provenance": "witnessed", "salience": 0.6, "turn_idx": 4,
             "content": f"Across the skip I walked the shore, stretch {n}.",
             "event_key": f"{skip_memories.SKIP_ORIGIN_PREFIX}{turn}:{n}"} for n in range(2)]
    written = skip_memories.write_rows(chat, ilse, {"id": turn, "idx": 4}, 1, rows)
    assert written == 2
    assert sorted(asked.get("ids") or []) == sorted(
        r["id"] for r in temp_db.q("SELECT id FROM memories WHERE char_id=?", (ilse,))), \
        "the dump asks for the written rows, not the bank"
    assert [e["content"] for e in carried["entries"]] == [r["content"] for r in rows]
