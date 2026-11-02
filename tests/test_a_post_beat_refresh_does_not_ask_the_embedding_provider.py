"""The refresh after a beat does not ask the embedding provider anything.

`chat_get` checks whether the story's memory bank was embedded by another
model than the live one -- `embedding_bank_status`, which asks the provider
what the live model is with `embed_texts_meta(["status"], retry=None)`, the one
call that skips every cache ("it alone asks the wire every time"). Design.md
places that probe "while a host waits for a chat to open", but the page also
calls `chat_get` after every beat, with `?since_turn_id=` -- so every beat paid
a billed round trip, or waited out the connect failure while the endpoint was
down (audit 2026-11-01, web_app E1). The slice is the post-beat refresh: it
skips the probe, and the page offers the rebuild only on a whole read, which
is when it always meant to (`static/js/chat.js`: "opening a story is the
moment").
"""
from __future__ import annotations

import time


def test_a_since_read_skips_the_probe_and_a_whole_read_makes_it(temp_db, monkeypatch):
    from web import app

    asked = []

    def probe(chat_id=None, char_id=None):
        asked.append(chat_id)
        return {"memories": {"stranded": 0}, "memory_summaries": {"stranded": 0}}

    monkeypatch.setattr(app, "embedding_bank_status", probe)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Story", "", time.time()))
    tid = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                     (cid, 0, "", time.time()))

    sliced = app.chat_get(cid, since_turn_id=tid)
    assert asked == []
    assert sliced["embedding_bank"] is None and sliced["turns_since"] == tid

    app.chat_get(cid)
    assert asked == [cid]
