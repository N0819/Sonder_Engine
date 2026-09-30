"""Who a memory had in it (`memories.about`), and the tag that turns on when a name is learned.

The owner, 2026-09-29: "I could probably solve the stranger description with a memory tagging
system, the tag could change to indicate the memory is about hinami when the character actually
learns there name, done in pure code" -- and "can a memory have multiple tags if it's about
multiple characters?". Measured first: in a 657-row bank, "where did I first meet Hinami?" never
reached the rows of the meeting, which call her "the young woman" and "the player".

Pinned here: a beat's memories are tagged with every body in the mind's room and a heard line's
speaker and addressee, never the mind itself, and never a body whose disguise keeps this mind
from recognising it (a glamour that leaves the face does not, a mask does, and a transformation
conceals nothing); a tag counts for a mind only once the name is in its `known` list -- before,
asking by the name reaches nothing, after, the rows that never say it come back, are graded as
the moments WITH that person they are and are handed over as `with_whom`; several tags resolve
each on its own; a beat's recall pick is told who was in each row but keeps no ABOUT lane; the
tags ride the checkpoint and the archive and are dropped from a bank carried into another story.

"With", never "about": the tag is who the moment had in it, and a grader told a row about the
TARDIS's landing was "about Hinami" graded its answer 0.05 where it had graded 0.72
(`memory_jev.memory_line`).
"""

from __future__ import annotations

import json
import time

from llm import decisions
from mind import memory
from persist.commit import _memory_about

ROOMS = {"positions": {"Mara": "hall", "Ilse": "hall", "Bram": "hall", "Otto": "cellar"}}


def test_a_beats_memory_has_in_it_everybody_in_the_room_but_the_mind():
    about = _memory_about(ROOMS, "Mara", "hall", {}, {}, {})
    assert about == ["Ilse", "Bram"]
    # a heard line's speaker and addressee, wherever they stood
    assert _memory_about(ROOMS, "Mara", "hall", {}, {}, {}, extra=("Otto", "Mara")) == ["Ilse", "Bram", "Otto"]


def test_a_disguise_that_hides_who_you_are_is_never_tagged_with_who_you_are():
    mask = {"ilse": {"subject": "Ilse", "conceals_identity": True, "known_to": ["Bram"]}}
    assert "Ilse" not in _memory_about(ROOMS, "Mara", "hall", {}, mask, {})
    # someone the disguise was shown to still knows her
    assert "Ilse" in _memory_about(ROOMS, "Bram", "hall", {}, mask, {})
    # a glamour over a feature leaves the face, and whoever it is
    glamour = {"ilse": {"subject": "Ilse", "conceals_identity": False, "known_to": ["Bram"]}}
    assert "Ilse" in _memory_about(ROOMS, "Mara", "hall", {}, glamour, {})
    # a transformed body conceals nothing
    assert "Ilse" in _memory_about(ROOMS, "Mara", "hall", {}, mask, {"ilse": {"subject": "Ilse"}})


# --- the tag and the name ----------------------------------------------------------

def _story(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("About", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                         ("Mara", "{}", "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    rows = [
        ("A woman in a grey coat caught my sleeve at the ferry and asked the way to the lighthouse.", ["Ilse"]),
        ("The woman in the grey coat and a tall man argued about the tide tables.", ["Ilse", "Bram"]),
        ("Rain all afternoon; I mended the nets alone.", []),
    ]
    for i, (text, about) in enumerate(rows):
        memory.add_memories_batch([{"chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": i,
                                    "kind": "episodic", "provenance": "witnessed", "salience": 0.6,
                                    "content": text, "event_key": f"t{i}", "about": about}])
    return chat_id, char_id


def _context(chat_id, char_id, **kw):
    return memory.build_character_memory_context(chat_id, char_id, 9, "the harbour at dusk", {}, **kw)


def _rows(ctx):
    return {m["memory_ref"]: m for lane in ("recalled_old_memories", "recent_memories")
            for m in ctx.get(lane) or []}


def test_a_tag_is_nothing_to_a_mind_that_does_not_know_the_name(temp_db):
    chat_id, char_id = _story(temp_db)
    ctx = _context(chat_id, char_id)
    assert not any("with_whom" in row for row in _rows(ctx).values())
    assert "Ilse" not in json.dumps({k: v for k, v in ctx.items() if k != "_internal"})


def test_learning_the_name_turns_the_tag_on(temp_db):
    chat_id, char_id = _story(temp_db)
    temp_db.wset(chat_id, "known", {"Mara": ["Ilse"]})
    rows = _rows(_context(chat_id, char_id))
    assert rows["t0"]["with_whom"] == ["Ilse"]
    # several tags resolve each on its own: Bram's name is still unknown
    assert rows["t1"]["with_whom"] == ["Ilse"]
    assert "with_whom" not in rows["t2"]
    # and the tag is never handed over itself
    assert not any("about" in row for row in rows.values())


def test_a_ponder_by_the_name_reaches_the_rows_that_never_say_it(temp_db, monkeypatch):
    chat_id, char_id = _story(temp_db)
    asked = []

    def grade(state, questions):
        asked.append(questions)
        # the decision model, as a test: a row it is told was with Ilse answers
        return {k: {"type": "choice", "probabilities": ({"strong": 1.0} if "; with Ilse)" in q["instructions"]
                                                        else {"none": 1.0})}
                for k, q in questions.items()}

    monkeypatch.setattr(decisions, "OVERRIDE", grade)
    person = {"name": "Mara", "drive": "", "values": []}
    before = _context(chat_id, char_id, person=person, ponder_query="What do I know about Ilse?")
    assert before["deliberate_recall"]["result_refs"] == []
    temp_db.wset(chat_id, "known", {"Mara": ["Ilse"]})
    after = _context(chat_id, char_id, person=person, ponder_query="What do I know about Ilse?")
    assert set(after["deliberate_recall"]["result_refs"]) == {"t0", "t1"}
    ponder = [q for q in asked if any(k.startswith("memory_ponder__") for k in q)][-1]
    assert sum("; with Ilse)" in q["instructions"] for q in ponder.values()) == 2
    assert not any("about Ilse" in q["instructions"] for q in ponder.values())
    # the ponder reached them by the ABOUT lane; the beat's own pick has none
    internal = after["_internal"]
    assert "about" in internal["ponder"]["lanes"] and "about" not in internal["picker"]["lanes"]


def test_the_beats_own_pick_is_told_who_was_there_but_keeps_no_about_lane(temp_db, monkeypatch):
    chat_id, char_id = _story(temp_db)
    temp_db.wset(chat_id, "known", {"Mara": ["Ilse"]})
    asked = []

    def grade(state, questions):
        asked.append(questions)
        return {k: {"type": "choice", "probabilities": {"weak": 1.0}} for k in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", grade)
    # the view names Ilse, as a view names everybody present; beat 20 leaves every row to recall
    ctx = memory.build_character_memory_context(chat_id, char_id, 20, "Ilse waits by the harbour at dusk.", {},
                                                person={"name": "Mara", "drive": "", "values": []})
    assert "about" not in ctx["_internal"]["picker"]["lanes"]
    lines = [q["instructions"] for batch in asked for q in batch.values()]
    assert any("; with Ilse)" in line for line in lines)


def test_the_tags_ride_rollback_and_archive_and_stay_behind_in_another_story(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app

    chat_id, char_id = _story(temp_db)
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)", (chat_id, 0, "", time.time()))

    def tags(chat):
        return {r["event_key"]: memory._about_of(r["about"]) for r in temp_db.q(
            "SELECT event_key, about FROM memories WHERE chat_id=?", (chat,))}

    ensure_checkpoint(chat_id, 0)
    temp_db.qi("UPDATE memories SET about='' WHERE chat_id=?", (chat_id,))
    restore_checkpoint(chat_id, 0)
    assert tags(chat_id)["t1"] == ["Ilse", "Bram"]
    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(chat_id)})
    assert tags(imported["id"] if isinstance(imported, dict) else imported)["t1"] == ["Ilse", "Bram"]
    other = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Elsewhere", "", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)", (other, char_id, "active", "{}"))
    memory.import_character_memories(other, char_id, memory.dump_character_memories(chat_id, char_id))
    assert all(not memory._about_of(r["about"]) for r in temp_db.q("SELECT about FROM memories WHERE chat_id=?", (other,)))
