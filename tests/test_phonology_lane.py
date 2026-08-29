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


def test_a_generated_law_writes_its_fragments_back_as_an_entry(temp_db):
    """The artifact that makes the one model judgement reviewable.

    The planner decides once what a setting's names are built from; from then
    on the mint is deterministic code reading a list an author can open and
    edit. Opacity at a SAMPLER is the objection to model-made names, and it
    does not apply to a judgement made once, in the open.
    """
    from world.charter_runtime import _record_phonology

    chat_id = db.qi("INSERT INTO chats(name,created) VALUES(?,?)",
                    ("story", time.time()))
    book = db.qi("INSERT INTO lorebooks(chat_id,name,summary) VALUES(?,?,?)",
                 (chat_id, "book", ""))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book, chat_id))

    _record_phonology(book, {"charters": {"works": {
        "name": "The Works",
        "naming": {"given_parts": {"starts": ["ka", "mi"], "middles": [],
                                   "ends": ["ren"]},
                   "family_parts": {"starts": ["bel"], "middles": [],
                                    "ends": ["mor"]}}}}})

    parts = phonology_parts(chat_id)
    assert parts["given_parts"]["starts"] == ["ka", "mi"]
    assert parts["given_parts"]["ends"] == ["ren"]
    assert parts["family_parts"]["starts"] == ["bel"]
    assert phonology_law_exists(chat_id)


def test_a_law_with_no_fragments_writes_nothing(temp_db):
    """A law carrying only pools has nothing a phonology entry could hold --
    and pools are exactly what must not be written back as material."""
    from world.charter_runtime import _record_phonology

    chat_id = db.qi("INSERT INTO chats(name,created) VALUES(?,?)",
                    ("story", time.time()))
    book = db.qi("INSERT INTO lorebooks(chat_id,name,summary) VALUES(?,?,?)",
                 (chat_id, "book", ""))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book, chat_id))

    _record_phonology(book, {"charters": {"works": {
        "naming": {"given": ["Jean-Luc"], "family": ["Picard"]}}}})

    assert phonology_entries(chat_id) == []


def test_lore_supplied_as_text_still_writes_the_entry_to_the_story_book(
        temp_db, monkeypatch):
    """The artifact is written even when the caller never names a lorebook.

    `owning_book` was `owning_lorebook_id or source_book`, and `source_book`
    is only set by `generation_lore` -- which a caller that passes `lore` as
    TEXT never reaches. So the whole lane went quiet for exactly the callers
    most likely to use it, and `_record_phonology` is deliberately never
    fatal, so nothing said so. Measured 2026-08-28: a generation whose law
    carried a full set of fragments produced zero phonology entries, and the
    one model judgement this lane exists to make reviewable could only be
    read out of the raw stored law.
    """
    from world import charter_generate, charter_runtime

    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("story", "", time.time()))
    book = db.qi("INSERT INTO lorebooks(chat_id,name,summary) VALUES(?,?,?)",
                 (chat_id, "book", ""))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book, chat_id))

    law = {"given_parts": {"starts": ["Ka", "Mi"], "middles": [],
                           "ends": ["ren"]},
           "family_parts": {"starts": ["Bel"], "middles": [], "ends": ["mor"]}}
    plan = {
        "name": "Waypoint",
        "structure": {"key": "waypoint", "max_planned": 8, "grammar": []},
        "rooms": {"hall": {"name": "Hall", "purpose": "work", "adjacent": []}},
        "charters": [{
            "key": "works", "naming": law, "priority": ["upkeep"],
            "upkeeps": {"upkeep": {
                "place": "hall", "floor": 0.25, "level": 1,
                "fails_untended": "a_week",
                "one_body_restores_in": "a_shift"}},
            "posts": {"warden": {"place": "hall", "serves": ["upkeep"],
                                 "requires": {"tending": 1}}},
            "populations": [{"post": "warden", "count": 4,
                             "competence": {"tending": 1}, "berth": "hall"}],
        }],
    }
    monkeypatch.setattr(charter_generate, "propose_town",
                        lambda lore, brief, constraints=None: plan)
    chat = db.q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)

    charter_runtime._plan_lived_location(
        chat_id,
        # `lore` as TEXT, and no lorebook named anywhere.
        {"lore": "a waypoint on a long road", "generate_history": False,
         "horizon_hours": 0.0},
        chat)

    entries = phonology_entries(chat_id)
    assert entries, "the fragments the mint was given were never written down"
    parts = phonology_parts(chat_id)
    assert parts["given_parts"]["starts"] == ["Ka", "Mi"]
    assert parts["family_parts"]["ends"] == ["mor"]
