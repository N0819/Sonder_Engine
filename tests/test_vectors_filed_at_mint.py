"""Review 2026-09-07 C2/A17: a memory's vector is filed in the store when the
memory is written, so the per-turn checkpoint inserts nothing; and the
checkpoint remap rescopes the two frame ids the generic remaps never touched.
"""
import json
import time

import mind.memory_snapshot as snapshot
from mind.memory import add_memory, dump_chat_memories, vector_address


def test_a_minted_memory_is_in_the_vector_store_and_the_dump_writes_nothing(
        temp_db, monkeypatch):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Vec", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Sarah", json.dumps({"identity": {"name": "Sarah"}}), "{}", time.time(), "c1"))
    add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
               "The lift doors would not close.", turn_idx=1)
    row = temp_db.q("SELECT embedding, cue_embedding FROM memories WHERE chat_id=?",
                    (chat_id,), one=True)
    vkey = vector_address(row["embedding"], row["cue_embedding"])
    assert temp_db.q("SELECT 1 FROM memory_vectors WHERE vkey=?", (vkey,), one=True)

    def refuse(*a, **k):
        raise AssertionError("the checkpoint dump must not write the store")
    monkeypatch.setattr(snapshot, "put_memory_vector", refuse)
    rows = dump_chat_memories(chat_id, inline_vectors=False)
    assert len(rows) == 1


def test_the_checkpoint_remap_rescopes_fixed_points_and_scheduled_events():
    from web.app import _remap_cp_blob
    blob = {"world": {"fixed_points": [{"id": "fp", "frame_id": 5}]},
            "scheduled_events": [{"payload": json.dumps({"frame_id": 5, "k": 1})}]}
    out = _remap_cp_blob(blob, {}, {}, None, world_id_remap={}, frame_idmap={5: 9})
    assert out["world"]["fixed_points"][0]["frame_id"] == 9
    assert json.loads(out["scheduled_events"][0]["payload"])["frame_id"] == 9
