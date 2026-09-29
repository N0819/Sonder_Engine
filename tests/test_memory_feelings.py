"""A memory keeps what its moment made the character feel (`memories.feelings`).

The owner, 2026-09-29: a memory's mood "should be a stored value made at memory
formation not one derived every turn". The affect pass forms it
(`mind/affect_pass.py`), commit stamps it on the rows a beat mints
(`persist/commit_memory.py`), and a later one-time reading of a row -- one that
kept nothing, or whose meaning changed since -- is kept beside it
(`memory.record_memory_look`).

Pinned here: a minted row keeps its moment and reads it back; a later reading
is kept beside the moment and never over it, one per turn, a handful at most,
inside this mind's own bank; a corrupt record reads as nothing kept; the
record survives rollback, branching and export like `disputed` beside it; and
a bank carried into another story keeps what was felt but not its readings of
the old story's clocks.
"""

from __future__ import annotations

import json
import time

from mind import memory

MOMENT = {"moment": {"felt": {"dread": 0.6}, "strength": 0.7, "at": 12.5, "turn": 3, "key": "3:perceived"}}
LOOK = {"felt": {"grief": 0.5}, "strength": 0.5, "at": 20.0, "why": "reread"}


def _story(temp_db):
    now = time.time()
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Feelings", "", now))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)", ("Aldo", "{}", now))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,state) VALUES(?,?,?)", (cid, char_id, "{}"))
    frame_id = temp_db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) VALUES(?,?,?,?,?)",
                          (cid, "Present", 0, "present", now))
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                         (cid, 0, "wait", now, frame_id))
    memory.add_memories_batch([{
        "chat_id": cid, "char_id": char_id, "turn_id": turn_id, "turn_idx": 0, "kind": "episodic",
        "provenance": "witnessed", "salience": 0.6, "content": "The harbour bell rang twice at dusk.",
        "event_key": "t3:episode", "feelings": MOMENT}])
    return cid, char_id, turn_id


def _kept(temp_db, cid):
    row = temp_db.q("SELECT feelings FROM memories WHERE chat_id=? AND event_key=?", (cid, "t3:episode"), one=True)
    return json.loads(row["feelings"]) if row and row["feelings"] else None


def test_a_minted_row_keeps_its_moment_and_reads_it_back(temp_db):
    cid, _char_id, _turn_id = _story(temp_db)
    assert _kept(temp_db, cid) == MOMENT
    row = temp_db.q("SELECT * FROM memories WHERE chat_id=?", (cid,), one=True)
    assert memory._row_memory(row)["feelings"] == MOMENT


def test_a_later_reading_is_kept_beside_the_moment_never_over_it(temp_db):
    cid, char_id, _turn_id = _story(temp_db)
    for turn in (5, 5, 6, 7, 8, 9):
        memory.record_memory_look(cid, char_id, "t3:episode", {**LOOK, "turn": turn})
    kept = _kept(temp_db, cid)
    assert kept["moment"] == MOMENT["moment"]
    # one reading per turn (a re-committed beat keeps one), the latest last,
    # a handful at most
    assert [look["turn"] for look in kept["looks"]] == [6, 7, 8, 9]
    # addressed within this mind's own bank: another mind's rows are never reached
    assert memory.record_memory_look(cid, char_id + 1, "t3:episode", {**LOOK, "turn": 10}) == []
    assert memory.record_memory_look(cid, char_id, "", {**LOOK, "turn": 10}) == []


def test_a_corrupt_record_reads_as_nothing_kept():
    assert memory._feelings_of("{not json") is None
    assert memory._feelings_of(json.dumps(["a list"])) is None
    assert memory._feelings_of(json.dumps({"moment": "not a record"})) is None
    assert memory._feelings_of("") is None


def test_kept_feelings_survive_rollback_branch_and_export(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app

    cid, _char_id, turn_id = _story(temp_db)
    ensure_checkpoint(cid, 0)
    temp_db.qi("UPDATE memories SET feelings='' WHERE chat_id=?", (cid,))
    restore_checkpoint(cid, 0)
    assert _kept(temp_db, cid) == MOMENT, "rollback lost what the memory keeps"

    branch = app.turn_branch(turn_id)["id"]
    assert _kept(temp_db, branch) == MOMENT, "a branch lost what the memory keeps"

    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(branch)})
    imported_id = imported["id"] if isinstance(imported, dict) else imported
    assert _kept(temp_db, imported_id) == MOMENT, "export and import lost what the memory keeps"


def test_the_packet_hands_what_a_row_keeps_to_the_engine_never_to_the_mind(temp_db):
    """`build_character_memory_context` puts each delivered row's kept feeling
    and the turn it was last re-read on in the host-only registry, where the
    affect pass reads it (`affect_pass.memories_from`); nothing of it rides in
    the projection the character is handed."""
    from mind import affect_pass
    from mind.memory import build_character_memory_context

    cid, char_id, _turn_id = _story(temp_db)
    dispute = json.dumps({"turn_idx": 6, "reading": "It was never her.", "count": 1})
    temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,provenance,salience,content,gist,"
        "key_phrases,entities,location,emotional_context,valence,arousal,confidence,archived,event_key,"
        "embedding_model,disputed) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, char_id, 1, "episodic", "episode", "witnessed", 0.6, "She left the gate open.",
         "She left the gate open.", "[]", "[]", "", "", 0.0, 0.0, 1.0, 0, "t1:episode", "", dispute))
    payload = build_character_memory_context(cid, char_id, 9, "You are in a room.", {})
    registry = payload["_internal"]["feelings"]
    assert registry["t3:episode"] == {"record": MOMENT, "disputed_turn": None}
    assert registry["t1:episode"] == {"record": None, "disputed_turn": 6}
    projected = [row for lane in ("recalled_old_memories", "recent_memories") for row in payload.get(lane) or []]
    assert projected and not any("feelings" in row or "moment" in json.dumps(row) for row in projected)
    # and no affect numbers at all: the owner, 2026-09-29, "only the code
    # derived memory name should be exposed to the character"
    assert not any({"affect_before", "affect_after_encoding"} & set(row) for row in projected)
    assert not any(k in json.dumps(row) for row in projected for k in ("valence", "arousal"))
    read = {m["ref"]: m for m in affect_pass.memories_from(payload)}
    assert read["t3:episode"]["feelings"] == MOMENT and affect_pass.why_read(read["t3:episode"]) is None
    assert affect_pass.why_read(read["t1:episode"]) == "unfelt"


def test_a_bank_carried_into_another_story_keeps_the_feeling_not_the_clocks(temp_db):
    cid, char_id, _turn_id = _story(temp_db)
    memory.record_memory_look(cid, char_id, "t3:episode", {**LOOK, "turn": 5})
    bank = memory.dump_character_memories(cid, char_id)
    other = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Elsewhere", "", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,state) VALUES(?,?,?)", (other, char_id, "{}"))
    memory.import_character_memories(other, char_id, bank)
    row = temp_db.q("SELECT feelings FROM memories WHERE chat_id=?", (other,), one=True)
    kept = json.loads(row["feelings"])
    # what was felt travels; the old story's psych clock, turns and moment
    # key would be read against this story's as if they were its own
    assert kept["moment"] == {"felt": {"dread": 0.6}, "strength": 0.7}
    assert kept["looks"] == [{"felt": {"grief": 0.5}, "strength": 0.5, "why": "reread"}]
