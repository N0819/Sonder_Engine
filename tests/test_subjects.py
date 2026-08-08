"""Subject identity reaches the kinds the scene fold cannot.

The scene fold (`spatial.canonical_subject_map`) is gated on scene liveness --
G3 -- and that gate is body-shaped: a faction, a crowd and a registry room own
no position, no scale, no attire, so they can never be live and the fold can
never reach them (docs/DESIGN_0c_subject_identity.md section 4, the
circularity). `subjects.resolve_subject` is the route-C answer: identity is
read from the durable ledger that already owns each kind, the scene fold is
left untouched, and where NO ledger owns a being nothing is minted -- the
measured 18 of 38 background presences that were never scene entities must
fail resolution with a reason, because giving them an id that exists in no
ledger is a second spelling beside the live name-keyed one, which is the
five-defect class this exists to end.
"""

from __future__ import annotations

import json
import time

import pytest

import subjects
from canon_provenance import validate_provisional


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _attach_character(db, chat_id, name, uid=None, aliases=None):
    sheet = {"identity": {"name": name, "aliases": aliases or []}}
    if uid:
        sheet["identity"]["uid"] = uid
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
        (name, json.dumps(sheet), time.time()),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
        (chat_id, char_id),
    )
    return char_id


def _add_book_with_entry(db, chat_id, title, category, keys="", aliases=None,
                         entry_uid=None):
    book_id = db.qi(
        "INSERT INTO lorebooks(name,chat_id) VALUES(?,?)",
        ("Canon", chat_id),
    )
    db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id) VALUES(?,?)",
        (chat_id, book_id),
    )
    entry_id = db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,category,title,"
        "aliases,entry_uid) VALUES(?,?,?,?,?,?,?)",
        (book_id, keys, "text", category, title,
         json.dumps(aliases or []), entry_uid),
    )
    return book_id, entry_id


def _register_room(db, chat_id, room_uid, name, aliases=None, retired_turn=None):
    db.qi(
        "INSERT INTO room_registry(chat_id,room_uid,name,aliases,"
        "retired_turn_id) VALUES(?,?,?,?,?)",
        (chat_id, room_uid, name, json.dumps(aliases or []), retired_turn),
    )


SCENE = {
    "rooms": {"great_hall": {"name": "The Great Hall", "adjacent": []}},
    "entities": {
        "market_throng_a1": {"name": "The Market Crowd", "kind": "crowd"},
        "guinan_x9": {"name": "Guinan", "kind": "person"},
    },
    "positions": {"Guinan": "great_hall"},
}


class TestCharacters:
    """No second spelling: a cast member resolves to the id the engine has
    been minting into payloads all along, never to a fresh one."""

    def test_cast_resolves_to_the_authored_uid(self, temp_db):
        """`cast_scene_context` mints `identity.uid` as the entity id; a
        resolver deriving anything else would put two ids on one being."""
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid="elyndra_succubus")
        res = subjects.resolve_subject(cid, {}, "character", "Elyndra")
        assert res and res.subject.id == "elyndra_succubus"
        assert res.authority == "cast"

    def test_cast_without_a_uid_gets_the_stable_fallback_not_a_mint(self, temp_db):
        """Normalizing the sheet mints a FRESH char_<hex> per call -- an id
        that changes every time anything asks is a new spelling per ask. The
        fallback must be the stable `character:<char_id>` instead."""
        cid = _make_chat(temp_db)
        char_id = _attach_character(temp_db, cid, "Wren")
        first = subjects.resolve_subject(cid, {}, "character", "Wren")
        second = subjects.resolve_subject(cid, {}, "character", "Wren")
        assert first.subject.id == f"character:{char_id}"
        assert first.subject.id == second.subject.id

    def test_an_id_round_trips_through_resolution(self, temp_db):
        """A caller holding an id must be able to verify it through the same
        door a caller holding a name uses -- two doors would drift."""
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid="elyndra_succubus")
        res = subjects.resolve_subject(cid, {}, "character", "elyndra_succubus")
        assert res and res.subject.id == "elyndra_succubus"
        assert res.subject.display == "Elyndra"

    def test_a_non_cast_scene_entity_resolves_to_its_entity_id(self, temp_db):
        """The measured resolvable floor: 20 of 38 presences ARE scene
        entities, and those must resolve without a cast row."""
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, SCENE, "character", "Guinan")
        assert res and res.subject.id == "guinan_x9"
        assert res.authority == "scene_entity"

    def test_a_name_keyed_presence_resolves_to_nothing_with_the_reason(self, temp_db):
        """The other 18 of 38: a presence that was never an entity has no id
        in any ledger. Minting one here is the Guinan defect restated, so the
        answer is a refusal that says why -- silence is how add_lore ran
        without a model stamp for months."""
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {"Mot the Barber": {}})
        res = subjects.resolve_subject(cid, {}, "character", "Mot the Barber")
        assert not res
        assert "name-keyed" in res.reason

    def test_two_cast_rows_with_one_name_resolve_to_nothing(self, temp_db):
        """Two beings folded into one is strictly worse than two spellings of
        one -- the scene fold's G1 rule, held here too."""
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "A Dalek", uid="dalek_1")
        _attach_character(temp_db, cid, "A Dalek", uid="dalek_2")
        res = subjects.resolve_subject(cid, {}, "character", "A Dalek")
        assert not res and "2 cast rows" in res.reason

    def test_a_miss_never_returns_silence(self, temp_db):
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, {}, "character", "Nobody")
        assert not res and res.reason


class TestRooms:
    """The room ledger is a different namespace the fold never reached."""

    def test_a_scene_room_resolves_by_name_to_its_node_id(self, temp_db):
        """'The Great Hall' in prose and 'great_hall' in the graph are one
        room; the one row offscreen_log ever wrote ('a quiet office') is what
        happens when nothing owns that join."""
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, SCENE, "room", "The Great Hall")
        assert res and res.subject.id == "great_hall"

    def test_a_registry_room_resolves_when_the_scene_has_moved_on(self, temp_db):
        """`room_registry` is the sole cross-frame ledger of room identity;
        a room absent from the LIVE scene is still that room."""
        cid = _make_chat(temp_db)
        _register_room(temp_db, cid, "east_wing", "The East Wing",
                       aliases=["the burned wing"])
        res = subjects.resolve_subject(cid, {}, "room", "the burned wing")
        assert res and res.subject.id == "east_wing"
        assert res.authority == "room_registry"

    def test_a_retired_room_still_has_its_identity(self, temp_db):
        """Retire-not-delete exists so 'the ship that sank here' stays
        retrievable; a reference to a destroyed room must resolve to the
        ruin's own row, not to nothing."""
        cid = _make_chat(temp_db)
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (cid, 1, "x", time.time()))
        _register_room(temp_db, cid, "old_deck", "Deck 3", retired_turn=turn_id)
        res = subjects.resolve_subject(cid, {}, "room", "Deck 3")
        assert res and res.subject.id == "old_deck"
        assert res.authority == "room_registry_retired"

    def test_an_invented_room_resolves_to_nothing_with_a_reason(self, temp_db):
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, SCENE, "room", "a quiet office")
        assert not res and "quiet office" in res.reason


class TestLoreOwnedKinds:
    """A faction has neither an entity id nor a cast row; its lore entry is
    the only durable record of it anywhere, so that is its identity."""

    def test_a_faction_resolves_to_its_lore_entry_uid(self, temp_db):
        cid = _make_chat(temp_db)
        _add_book_with_entry(
            temp_db, cid, "The Obsidian Order", "faction",
            keys="obsidian order, the order", entry_uid="entry_ab12")
        res = subjects.resolve_subject(cid, {}, "faction", "The Obsidian Order")
        assert res and res.subject.id == "entry_ab12"
        assert res.authority == "lore_entry"

    def test_a_faction_with_no_lore_entry_is_owned_by_no_ledger(self, temp_db):
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, {}, "faction", "The Unwritten Guild")
        assert not res and "no ledger" in res.reason

    def test_an_ungenerated_place_is_keyed_on_its_lore_entry(self, temp_db):
        """Amendment 8: a lorebook place mapping has never generated has no
        room_uid, so `room` cannot spell it -- `place` on the entry_uid can,
        and the accumulated obligations need that key to hang off."""
        cid = _make_chat(temp_db)
        _add_book_with_entry(
            temp_db, cid, "The Sunken Library", "location",
            entry_uid="entry_cd34")
        res = subjects.resolve_subject(cid, {}, "place", "The Sunken Library")
        assert res and res.subject.kind == "place"
        assert res.subject.id == "entry_cd34"

    def test_a_generated_place_resolves_as_the_room_not_the_entry(self, temp_db):
        """The seam that keeps room-and-place from being the two-spellings
        defect one level up: once the room exists, `place` must yield to it,
        or one location is addressable under two ids at once."""
        cid = _make_chat(temp_db)
        _add_book_with_entry(
            temp_db, cid, "The Sunken Library", "location",
            entry_uid="entry_cd34")
        _register_room(temp_db, cid, "sunken_library", "The Sunken Library")
        res = subjects.resolve_subject(cid, {}, "place", "The Sunken Library")
        assert res and res.subject.kind == "room"
        assert res.subject.id == "sunken_library"

    def test_an_entry_without_a_uid_is_refused_not_papered_over(self, temp_db):
        """The numeric lore id does not survive export/import remapping; an
        id that changes on import is not an identity, so a NULL entry_uid is
        a stated refusal rather than a silent fallback."""
        cid = _make_chat(temp_db)
        _add_book_with_entry(
            temp_db, cid, "The Grey Court", "faction", entry_uid=None)
        res = subjects.resolve_subject(cid, {}, "faction", "The Grey Court")
        assert not res and "entry_uid" in res.reason


class TestCrowds:
    def test_a_crowd_that_is_a_scene_entity_uses_that_id(self, temp_db):
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, SCENE, "crowd", "The Market Crowd")
        assert res and res.subject.id == "market_throng_a1"

    def test_a_crowd_owned_by_no_ledger_resolves_to_nothing(self, temp_db):
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, {}, "crowd", "the garrison watch")
        assert not res and res.reason


class TestTheOpenVocabulary:
    def test_an_unknown_kind_does_not_raise(self, temp_db):
        """Closing the vocabulary now IS the migration (canon_provenance's
        rule). A new subject kind must be spellable without an edit here."""
        cid = _make_chat(temp_db)
        res = subjects.resolve_subject(cid, SCENE, "vessel", "The Market Crowd")
        assert res and res.subject.kind == "vessel"
        res = subjects.resolve_subject(cid, {}, "vessel", "The Argo")
        assert not res and "no identity authority" in res.reason


class TestTheRecordShape:
    def test_a_resolved_subject_survives_the_provenance_validator(self, temp_db):
        """0a refuses a subject whose id is its display name; the resolver
        must produce subjects 0a accepts, or the two modules disagree about
        what an identity is."""
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid="elyndra_succubus")
        res = subjects.resolve_subject(cid, {}, "character", "Elyndra")
        record = {
            "disposition": "provisional",
            "subject": res.subject.as_dict(),
            "base_turn": 3,
            "basis": "deterministic",
        }
        assert validate_provisional(record).ok

    def test_a_display_equal_to_the_id_is_dropped_not_stored(self, temp_db):
        """0a's validator refuses id == display; a resolver that stores the
        equality would make every such subject unstorable downstream."""
        cid = _make_chat(temp_db)
        sc = {"entities": {"tardis": {"name": "TARDIS"}}, "rooms": {}}
        res = subjects.resolve_subject(cid, sc, "crowd", "TARDIS")
        assert res and res.subject.display is None
