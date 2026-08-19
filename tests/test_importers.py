"""Tests for native character and persona imports."""

import base64
import json
import struct
import zlib

import pytest

from story.character_schema import (
    CHARACTER_SCHEMA,
    PERSONA_SCHEMA,
    default_character_data,
    default_persona_data,
)


def _png_chunk(ctype, data):
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", 0)


def _fake_png(chunks):
    body = b"\x89PNG\r\n\x1a\n"
    for ctype, data in chunks:
        body += _png_chunk(ctype, data)
    body += _png_chunk(b"IEND", b"")
    return body

def test_native_character_imports_without_ai(temp_db, monkeypatch):
    from story import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "AI must not be called for native imports"
        )

    monkeypatch.setattr(
        importers,
        "chat_complete",
        fail_if_called,
    )

    sheet = default_character_data("Test Character")
    sheet["psychology"]["traits"] = [{
        "name": "patient",
        "strength": 0.7,
        "expression": "waits before responding",
    }]

    payload = {
        "schema": CHARACTER_SCHEMA,
        "version": 2,
        "data": sheet,
        "source": {
            "format": "native",
            "original": None,
        },
    }

    character_id, imported = importers.import_character(
        payload,
        reinterpret=False,
    )

    assert character_id
    assert imported["identity"]["name"] == "Test Character"
    assert imported["psychology"]["traits"][0]["name"] == "patient"

    row = temp_db.q(
        "SELECT name,sheet FROM characters WHERE id=?",
        (character_id,),
        one=True,
    )

    assert row["name"] == "Test Character"

def test_native_persona_imports_without_ai(temp_db, monkeypatch):
    from story import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "AI must not be called for native imports"
        )

    monkeypatch.setattr(
        importers,
        "chat_complete",
        fail_if_called,
    )

    sheet = default_persona_data("Test Player")
    payload = {
        "schema": PERSONA_SCHEMA,
        "version": 2,
        "data": sheet,
        "source": {
            "format": "native",
            "original": None,
        },
    }

    persona_id, imported = importers.import_persona(
        payload,
        reinterpret=False,
    )

    assert persona_id
    assert imported["identity"]["name"] == "Test Player"

    row = temp_db.q(
        "SELECT name,sheet FROM personas WHERE id=?",
        (persona_id,),
        one=True,
    )

    assert row["name"] == "Test Player"


def test_native_character_import_ignores_reinterpret_flag(temp_db, monkeypatch):
    # The UI's "AI reinterpretation" checkbox now defaults to checked (it's
    # the only practical way to handle the long tail of foreign card
    # formats), but a payload already in this project's native schema must
    # still round-trip exactly and deterministically -- reimporting your
    # own export should never depend on remembering to untick a checkbox.
    from story import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "AI must not be called for a native payload even with "
            "reinterpret=True"
        )

    monkeypatch.setattr(importers, "chat_complete", fail_if_called)

    sheet = default_character_data("Test Character")
    payload = {"schema": CHARACTER_SCHEMA, "version": 2, "data": sheet}

    character_id, imported = importers.import_character(
        payload, reinterpret=True,
    )

    assert character_id
    assert imported["identity"]["name"] == "Test Character"


def test_native_persona_import_ignores_reinterpret_flag(temp_db, monkeypatch):
    from story import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "AI must not be called for a native payload even with "
            "reinterpret=True"
        )

    monkeypatch.setattr(importers, "chat_complete", fail_if_called)

    sheet = default_persona_data("Test Player")
    payload = {"schema": PERSONA_SCHEMA, "version": 2, "data": sheet}

    persona_id, imported = importers.import_persona(
        payload, reinterpret=True,
    )

    assert persona_id
    assert imported["identity"]["name"] == "Test Player"


def test_native_lorebook_export_round_trips_without_ai_or_reguessing(
    temp_db, monkeypatch,
):
    from story import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "AI must not be called for a native lorebook export even "
            "with reinterpret=True"
        )

    monkeypatch.setattr(importers, "chat_complete", fail_if_called)

    exported = {
        "name": "Original Book",
        "book_type": "location",
        "summary": "A place.",
        "resource_uid": "book_abc123",
        "entries": [
            {
                "entry_uid": "entry_abc123",
                "keys": "castle, keep",
                "content": "A stone castle on the hill.",
                "category": "location",
                "locked": 1,
                "title": "The Castle",
                "knowledge_tag": "common",
                "knowledge_range": None,
                "knowledge_locations": [],
                "importance": 0.8,
                "aliases": ["the keep"],
                "scope": {},
                "relations": {},
                "source_notes": "hand-written",
            },
        ],
    }

    lb_id, count = importers.import_lorebook(exported, reinterpret=True)

    assert count == 1
    row = temp_db.q(
        "SELECT * FROM lore_entries WHERE lorebook_id=?", (lb_id,), one=True,
    )
    assert row["keys"] == "castle, keep"
    assert row["content"] == "A stone castle on the hill."
    # category/title/importance came straight from the export, not from
    # guess_category() re-deriving them from scratch.
    assert row["category"] == "location"
    assert row["title"] == "The Castle"
    assert row["canon_locked"] == 1
    assert row["importance"] == 0.8
    # entry_uid is uniquely indexed -- reusing the exported one verbatim
    # would collide on a second import of the same book, so a fresh one
    # must have been minted instead.
    assert row["entry_uid"] != "entry_abc123"

    book_row = temp_db.q(
        "SELECT * FROM lorebooks WHERE id=?", (lb_id,), one=True,
    )
    assert book_row["book_type"] == "location"


def test_extract_png_card_reads_v2_chara_text_chunk():
    from story import importers

    card = {
        "name": "Ada",
        "description": "A test character.",
        "personality": "curious",
        "first_mes": "Hello.",
    }
    card_b64 = base64.b64encode(json.dumps(card).encode("utf-8")).decode("ascii")
    png_bytes = _fake_png([
        (b"tEXt", b"chara\x00" + card_b64.encode("ascii")),
    ])
    png_b64 = base64.b64encode(png_bytes).decode("ascii")

    assert importers.extract_png_card(png_b64) == card


def test_extract_png_card_prefers_ccv3_ztxt_over_legacy_chara():
    from story import importers

    v3_card = {"spec": "chara_card_v3", "data": {"name": "Ada V3"}}
    v3_b64 = base64.b64encode(json.dumps(v3_card).encode("utf-8")).decode("ascii")
    ccv3_data = b"ccv3\x00\x00" + zlib.compress(v3_b64.encode("ascii"))

    v2_card = {"name": "Ada V2 legacy"}
    v2_b64 = base64.b64encode(json.dumps(v2_card).encode("utf-8")).decode("ascii")
    chara_data = b"chara\x00" + v2_b64.encode("ascii")

    png_bytes = _fake_png([(b"zTXt", ccv3_data), (b"tEXt", chara_data)])
    png_b64 = base64.b64encode(png_bytes).decode("ascii")

    assert importers.extract_png_card(png_b64) == v3_card


def test_extract_png_card_strips_data_url_prefix():
    from story import importers

    card = {"name": "Ada"}
    card_b64 = base64.b64encode(json.dumps(card).encode("utf-8")).decode("ascii")
    png_bytes = _fake_png([(b"tEXt", b"chara\x00" + card_b64.encode("ascii"))])
    png_b64 = base64.b64encode(png_bytes).decode("ascii")

    assert importers.extract_png_card("data:image/png;base64," + png_b64) == card


def test_extract_png_card_returns_none_without_card_chunk():
    from story import importers

    png_bytes = _fake_png([(b"tEXt", b"Comment\x00just a normal picture")])
    png_b64 = base64.b64encode(png_bytes).decode("ascii")

    assert importers.extract_png_card(png_b64) is None


def test_resolve_import_card_raises_clear_error_for_cardless_png():
    from story import importers

    png_bytes = _fake_png([])
    png_b64 = base64.b64encode(png_bytes).decode("ascii")

    with pytest.raises(ValueError):
        importers.resolve_import_card({"png_base64": png_b64})


def test_resolve_import_card_passes_through_plain_dict():
    from story import importers

    card = {"name": "Ada"}
    assert importers.resolve_import_card(card) == card


def test_png_character_card_imports_end_to_end(temp_db, monkeypatch):
    from story import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError("AI must not be called for a native-shaped PNG card")

    monkeypatch.setattr(importers, "chat_complete", fail_if_called)

    sheet = default_character_data("PNG Character")
    payload = {
        "schema": CHARACTER_SCHEMA,
        "version": 2,
        "data": sheet,
    }
    payload_b64 = base64.b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    png_bytes = _fake_png([(b"tEXt", b"chara\x00" + payload_b64.encode("ascii"))])
    png_b64 = base64.b64encode(png_bytes).decode("ascii")

    card = importers.resolve_import_card({"png_base64": png_b64})
    character_id, imported = importers.import_character(card, reinterpret=False)

    assert character_id
    assert imported["identity"]["name"] == "PNG Character"

# --- the book type a guessed category maps to -------------------------------
#
# `guess_book_type` mapped six categories to book types. Two of them,
# `character` and `knowledge`, are categories `guess_category` cannot return
# -- they belong to `memory.LORE_CATEGORIES`, the vocabulary an entry's own
# `category` field uses, not to the six-way guess feeding this map. And two
# categories it DOES return, `myth` and `other`, were absent, so a book of
# legends and a book of nothing recognisable both fell through to "general".
#
# The map's domain is now exactly the guess's range, with a test binding
# them: a reader adding a branch to one has no signal that the other is the
# thing that must change.

class TestBookTypeFollowsTheGuessedCategory:
    def test_the_map_answers_for_every_category_the_guess_can_return(self):
        from story.importers import GUESSABLE_CATEGORIES, _BOOK_TYPE_BY_CATEGORY
        assert set(_BOOK_TYPE_BY_CATEGORY) == set(GUESSABLE_CATEGORIES)

    def test_the_guess_never_returns_a_category_outside_its_range(self):
        from story.importers import GUESSABLE_CATEGORIES, guess_category
        for keys, content in [
            ("Great Hall", "A stair leads to the basement."),
            ("Aether", "The spell works by drawing on the ley lines."),
            ("The Drowned God", "Folklore holds that the goddess sleeps."),
            ("Siege of Anvil", "The battle happened in the third year."),
            ("Kestrel", "A fishing village on the island."),
            ("", ""),
            ("Aunt Marla", "She keeps bees."),
        ]:
            assert guess_category(keys, content) in GUESSABLE_CATEGORIES

    def test_a_book_of_legends_is_world_lore(self):
        from story.importers import guess_book_type
        entries = [("The Drowned God", "Folklore holds that the goddess sleeps.", 0),
                   ("The Long Night", "A prophecy the villagers still believe.", 0)]
        assert guess_book_type(entries) == "world"

    def test_a_book_of_nothing_recognisable_stays_general(self):
        from story.importers import guess_book_type
        entries = [("Aunt Marla", "She keeps bees.", 0),
                   ("Tuesday", "It rained.", 0)]
        assert guess_book_type(entries) == "general"

    def test_every_book_type_it_can_produce_is_a_real_one(self):
        from mind.memory import LOREBOOK_TYPES
        from story.importers import _BOOK_TYPE_BY_CATEGORY
        assert set(_BOOK_TYPE_BY_CATEGORY.values()) <= set(LOREBOOK_TYPES)
