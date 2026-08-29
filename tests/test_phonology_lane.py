"""The mint's only legitimate source: fragments, never people.

Everything else in `story/naming.py` subtracts -- it harvests whatever a law
carries and removes the names it recognises. That is a backstop and it is
provably insufficient: measured 2026-08-28 on a generated Star Trek
institution, two of the four surnames still reachable after every subtraction
(`Soong`, `Pulaski`) appear in no lore entry anywhere. The planner supplied
them from its own knowledge of the setting, and no reservation can reach a
name the story never wrote down.

A `phonology` entry holds the material a name is built FROM and names nobody,
so a pool drawn from one cannot issue a person's name however well the model
knows the setting.
"""
from __future__ import annotations

import time

from core import db
from mind.memory import add_lore
from story.naming import (phonology_entries, phonology_law_exists,
                          phonology_parts)


def _chat_with(temp_db, category, content, title="Naming"):
    chat_id = db.qi("INSERT INTO chats(name,created) VALUES(?,?)",
                    ("story", time.time()))
    book = db.qi("INSERT INTO lorebooks(chat_id,name,summary) VALUES(?,?,?)",
                 (chat_id, "book", ""))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book, chat_id))
    add_lore(book, "naming", content, category=category, title=title)
    return chat_id


FRAGMENTS = """given_starts: ka, mi, tor
given_ends: ren, is
family_starts: bel, wyn
family_ends: mor, ath
"""


def test_fragments_become_name_material(temp_db):
    chat_id = _chat_with(temp_db, "phonology", FRAGMENTS)
    parts = phonology_parts(chat_id)

    assert parts["given_parts"]["starts"] == ["ka", "mi", "tor"]
    assert parts["given_parts"]["ends"] == ["ren", "is"]
    assert parts["family_parts"]["starts"] == ["bel", "wyn"]
    assert parts["family_parts"]["ends"] == ["mor", "ath"]
    assert phonology_law_exists(chat_id)


def test_a_character_entry_is_not_name_material(temp_db):
    """The partition, stated as a test. An entry naming a person is invisible
    to this lane no matter what it contains -- which is the whole point, and
    the reason a filter was the wrong mechanism."""
    chat_id = _chat_with(temp_db, "character",
                         "given_starts: Jean-Luc\nfamily_starts: Picard",
                         title="Jean-Luc Picard")

    assert phonology_entries(chat_id) == []
    assert not phonology_law_exists(chat_id)
    parts = phonology_parts(chat_id)
    assert parts["family_parts"]["starts"] == []


def test_a_story_that_authored_nothing_contributes_nothing(temp_db):
    chat_id = _chat_with(temp_db, "phonology", "prose about how names sound")

    assert not phonology_law_exists(chat_id)


def test_fields_it_does_not_understand_are_ignored_rather_than_guessed(temp_db):
    """An entry written for some other purpose contributes nothing, rather
    than having its lines read as fragments because they had a colon in."""
    chat_id = _chat_with(temp_db, "phonology",
                         "tone: harsh\nnote: avoid sibilants\n"
                         "given_starts: va")
    parts = phonology_parts(chat_id)

    assert parts["given_parts"]["starts"] == ["va"]
    assert parts["family_parts"]["starts"] == []
