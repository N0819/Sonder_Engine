"""A lore edit changes the fields it states, and nothing else.

`update_lore` had two conventions in one signature (review 2026-11-01,
mind_memory F5 and F6, both reproduced):

* `title`, `knowledge_tag`, `knowledge_range` and `knowledge_locations` were
  always written, so a caller that left them out CLEARED them. A tag cleared
  is an entry that reaches no mind (`knowledge_for_character` reads an untagged
  entry as Director-only): every character who knew the fact lost it, silently,
  when an authoring op reworded its content.
* `knowledge_locations` was bound raw, so the list shape a plan carries raised
  `ProgrammingError: Error binding parameter 7: type 'list' is not supported`.
* `circles` was written only when not None, so NULL -- "inherit the book" --
  could never be written back, and a lorebook restore could not roll a
  compartment change back: the fact stayed secret (or public) in a timeline
  that never had the change.

One convention now: a field the caller does not pass is left alone; a field it
passes is written, and for the nullable gate fields an explicit None is a real
value (no title, Director-only, global, no places, inherit the book).
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory


@pytest.fixture
def book(temp_db):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))
    return temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type,summary) "
                      "VALUES(?,?,?,?)", ("B", chat, "general", ""))


def _row(temp_db, eid):
    return dict(temp_db.q("SELECT title, knowledge_tag, knowledge_range, "
                          "knowledge_locations, circles, content FROM lore_entries "
                          "WHERE id=?", (eid,), one=True))


def test_a_rewording_keeps_every_gate_field(temp_db, book):
    eid = memory.add_lore(book, "gate", "The gate is iron.", knowledge_tag="common",
                          title="Gate", knowledge_range="local",
                          knowledge_locations=["yard"], circles=["watch"])
    memory.update_lore(eid, "gate", "The gate is iron and old.")
    row = _row(temp_db, eid)
    assert row["content"] == "The gate is iron and old."
    assert row["title"] == "Gate"
    assert row["knowledge_tag"] == "common", "an untagged entry reaches no mind"
    assert row["knowledge_range"] == "local"
    assert json.loads(row["knowledge_locations"]) == ["yard"]
    assert json.loads(row["circles"]) == ["watch"]
    assert [k["title"] for k in memory.knowledge_for_character(
        [book], "yard", {"common"}, [], circles=["watch"])] == ["Gate"]


def test_a_list_of_places_is_stored_as_json(temp_db, book):
    eid = memory.add_lore(book, "gate", "The gate is iron.", knowledge_tag="common")
    memory.update_lore(eid, "gate", "The gate is iron.", knowledge_range="local",
                       knowledge_locations=["yard", "gatehouse"])
    assert json.loads(_row(temp_db, eid)["knowledge_locations"]) == ["yard", "gatehouse"]


def test_a_stated_none_still_clears_a_gate_field(temp_db, book):
    """The host's editor sends `knowledge_tag: null` to take an entry out of
    every mind's reach; that must keep working."""
    eid = memory.add_lore(book, "gate", "The gate is iron.", knowledge_tag="common",
                          title="Gate")
    memory.update_lore(eid, "gate", "The gate is iron.", knowledge_tag=None)
    row = _row(temp_db, eid)
    assert row["knowledge_tag"] is None and row["title"] == "Gate"


def test_a_restore_rolls_a_compartment_change_back(temp_db, book):
    eid = memory.add_lore(book, "seal", "The seal is kept by the order.",
                          knowledge_tag="common", title="Seal")
    snapshot = memory.dump_lorebook(book)
    memory.update_lore(eid, "seal", "The seal is kept by the order.", circles=["order"])
    assert json.loads(_row(temp_db, eid)["circles"]) == ["order"]
    memory.restore_lorebook(book, snapshot)
    assert _row(temp_db, eid)["circles"] is None, "NULL inherits the book, as before the edit"


def test_a_restore_puts_every_gate_field_back_verbatim(temp_db, book):
    eid = memory.add_lore(book, "seal", "The seal is kept.", knowledge_tag="common",
                          title="Seal", knowledge_range="local",
                          knowledge_locations=["vault"], circles=[])
    snapshot = memory.dump_lorebook(book)
    memory.update_lore(eid, "seal", "The seal is lost.", knowledge_tag="esoteric",
                       title="Lost seal", knowledge_range="global",
                       knowledge_locations=None, circles=["order"])
    memory.restore_lorebook(book, snapshot)
    row = _row(temp_db, eid)
    assert (row["title"], row["knowledge_tag"], row["knowledge_range"]) == \
        ("Seal", "common", "local")
    assert json.loads(row["knowledge_locations"]) == ["vault"]
    assert json.loads(row["circles"]) == [], "an explicit [] (public) survives too"
    assert row["content"] == "The seal is kept."
