"""A rewind past a promotion takes the library row with the cast link.

Measured in the owner's database: chat 58 promoted "A Dalek" at 20:44 and
again at 21:07 the same evening (characters 48 and 49, both
`{"format": "promoted", "chat_id": 58}`). Row 48 is attached to nothing and
remembers nothing; row 49 carries the story. Between them the run was
rewound: the restore's cast sweep removed 48's `chat_chars` link, the
presence ledger came back from the checkpoint, and the next beat minted the
same person a second time -- `_refuse_name_collision` reads attached cast
only, so an orphaned mint is invisible to it. The library tab then lists two
Daleks, one of them in no story at all.

The rule: a row this chat minted, that no chat links and no memory names,
is the discarded run's own artefact and leaves with it. A mint another chat
holds (a branch), or one a host has attached by hand elsewhere, survives.
"""
import time

from persist.checkpoints import ensure_checkpoint, restore_checkpoint
from persist.commit import promote_background_character


def _chat(db, name="Enterprise-D"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "The bridge.", time.time()))


def _library(db):
    return sorted(r["id"] for r in db.q("SELECT id FROM characters"))


def test_rewinding_past_a_promotion_removes_its_library_row(temp_db):
    cid = _chat(temp_db)
    ensure_checkpoint(cid, 1)
    before = _library(temp_db)

    char_id = promote_background_character(
        cid, "A Dalek", sheet={"identity": {"name": "A Dalek"}}, memory_seeds=[])
    assert char_id in _library(temp_db)

    restore_checkpoint(cid, 1)

    assert _library(temp_db) == before
    assert temp_db.q("SELECT 1 FROM chat_chars WHERE char_id=?",
                     (char_id,), one=True) is None


def test_a_second_promotion_after_a_rewind_does_not_double_the_library(temp_db):
    cid = _chat(temp_db)
    ensure_checkpoint(cid, 1)
    promote_background_character(
        cid, "A Dalek", sheet={"identity": {"name": "A Dalek"}}, memory_seeds=[])
    restore_checkpoint(cid, 1)
    promote_background_character(
        cid, "A Dalek", sheet={"identity": {"name": "A Dalek"}}, memory_seeds=[])

    rows = temp_db.q("SELECT id FROM characters WHERE name='A Dalek'")
    assert len(rows) == 1


def test_a_mint_another_chat_holds_survives_the_rewind(temp_db):
    cid = _chat(temp_db)
    other = _chat(temp_db, "a branch")
    ensure_checkpoint(cid, 1)
    char_id = promote_background_character(
        cid, "A Dalek", sheet={"identity": {"name": "A Dalek"}}, memory_seeds=[])
    # A branch links the same library row (web.app.turn_branch copies the
    # cast link, never the character).
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
               (other, char_id))

    restore_checkpoint(cid, 1)

    assert temp_db.q("SELECT 1 FROM characters WHERE id=?",
                     (char_id,), one=True) is not None
    assert temp_db.q("SELECT 1 FROM chat_chars WHERE chat_id=? AND char_id=?",
                     (cid, char_id), one=True) is None


def test_a_row_this_chat_did_not_mint_is_never_touched(temp_db):
    cid = _chat(temp_db)
    ensure_checkpoint(cid, 1)
    # Attached by hand after the checkpoint: the link rolls back, the
    # library row is the host's and stays.
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Guinan", '{"identity": {"name": "Guinan"}}', '{"format": "native"}',
         time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
               (cid, char_id))

    restore_checkpoint(cid, 1)

    assert temp_db.q("SELECT 1 FROM characters WHERE id=?",
                     (char_id,), one=True) is not None
