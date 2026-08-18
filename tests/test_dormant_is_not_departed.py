"""A character can be offscreen without ceasing to exist.

`chat_chars.status` was answering three questions with one word:

  (a) does this person exist in this chat's world?   -- the roster question
  (b) are they in the current scene?                  -- the perception question
  (c) should we spend a model call on them?           -- the animation question

`active_cast` answers (b) and (c) correctly, and `_known_name_roster` was
reading it as an answer to (a) as well. So a dormant character could be named
by nobody.

Measured live on chat 34: one turn emitted four `ok` introductions --
Hinami->Guinan, Hinami->The Doctor, Guinan->The Doctor, Guinan->Hinami -- and
the resulting `known` map held exactly one edge, `{"Hinami": ["The Doctor"]}`.
The only pair where BOTH names were active cast. Every entry naming dormant
Guinan vanished in both directions, silently.

The same roster drives the guard that stops a registered character being handed
to the background manager as furniture, so dormancy switched that off for
exactly the people most likely to be treated as furniture.
"""

from __future__ import annotations

import json
import time

from persist import commit
from story.character_schema import normalize_character_data
from story.scene import active_cast, extant_cast


def _chat(db, name="A story"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _character(db, chat_id, name, status="active"):
    sheet = normalize_character_data({"name": name})
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,?,?)", (chat_id, char_id, status, "{}"))
    return char_id


def test_a_dormant_character_is_still_someone_the_story_knows_about(temp_db):
    """THE DEFECT. Guinan walks out of the room and stops being nameable --
    not by the player, not by the Doctor, not by the introduction that says
    somebody just learned her name.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "The Doctor", "active")
    _character(temp_db, chat_id, "Guinan", "dormant")
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                          one=True))

    roster = commit._registered_name_roster(chat, active_cast(chat_id))

    assert "The Doctor" in roster
    assert "Guinan" in roster, "dormant read as gone"


def test_the_cast_that_costs_model_calls_is_not_widened(temp_db):
    """THE THING THAT MUST NOT CHANGE. `ctx.cast` drives `present_characters`
    into mapping and the director, and the per-character agent loop. Widen it
    and you pay for absent people and tell the director they are in the room.
    The roster widens; this does not.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "The Doctor", "active")
    _character(temp_db, chat_id, "Guinan", "dormant")

    assert [r["name"] for r in active_cast(chat_id)] == ["The Doctor"]
    assert {r["name"] for r in extant_cast(chat_id)} == {"The Doctor", "Guinan"}


def test_a_departed_character_leaves_the_roster(temp_db):
    """`departed` is the real answer to the existence question. Without it,
    dormancy has to mean both "offscreen" and "written out", which is the
    overloading this whole change exists to undo.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "The Doctor", "active")
    _character(temp_db, chat_id, "Someone Who Left", "departed")
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                          one=True))

    roster = commit._registered_name_roster(chat, active_cast(chat_id))

    assert "Someone Who Left" not in roster
    assert [r["name"] for r in extant_cast(chat_id)] == ["The Doctor"]


def test_existing_dormant_rows_are_read_as_extant(temp_db):
    """The migration question, decided in the safe direction. A `dormant` row
    predating this distinction is ambiguous between offscreen and written-out,
    and the column cannot say which. A departed character wrongly nameable is
    a continuity oddity; a present character wrongly unnameable is the defect
    above -- so ambiguity resolves to extant.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "Guinan", "dormant")

    assert [r["name"] for r in extant_cast(chat_id)] == ["Guinan"]


def test_a_caller_that_passes_a_narrower_cast_still_gets_the_full_roster(
        temp_db):
    """WIDENED AT THE FUNCTION, NOT AT EIGHT CALL SITES. A roster correct for
    name resolution and wrong for enumeration is exactly the shape that gets
    forgotten, so the floor must not depend on what the caller passed.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "The Doctor", "active")
    _character(temp_db, chat_id, "Guinan", "dormant")
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                          one=True))

    assert "Guinan" in commit._registered_name_roster(chat, [])


def test_the_roster_does_not_repeat_a_character_the_caller_also_passed(
        temp_db):
    """The caller's rows and the extant rows overlap by construction. A
    duplicated name would be harmless for `in` checks and wrong for anything
    that enumerates -- which is the surface this change has to be careful of.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "The Doctor", "active")
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                          one=True))

    roster = commit._registered_name_roster(chat, active_cast(chat_id))

    assert roster.count("The Doctor") == 1


def test_the_enumerated_roster_stays_narrow(temp_db):
    """THE ONE THAT MUST NOT WIDEN, and the reason this is two functions.

    `promote_background_character` iterates a roster straight into the `known`
    recognition map -- `for other in roster: known[other].append(her_name)` --
    and its own query is deliberately `status='active'`. Widening the function
    it calls would seed durable mutual recognition between a newly promoted
    character and every dormant one, and nothing downstream re-checks `known`.
    A prompt leak is embarrassing; a wrong write to the recognition ledger is
    permanent.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "The Doctor", "active")
    _character(temp_db, chat_id, "Guinan", "dormant")
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                          one=True))

    narrow = commit._known_name_roster(chat, active_cast(chat_id))

    assert "The Doctor" in narrow
    assert "Guinan" not in narrow, "the enumerated roster widened"


def test_promotion_does_not_seed_recognition_with_offscreen_people(temp_db):
    """The same guarantee, asserted through the caller rather than the helper,
    because that is where the damage would land.
    """
    chat_id = _chat(temp_db)
    _character(temp_db, chat_id, "The Doctor", "active")
    _character(temp_db, chat_id, "Guinan", "dormant")
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                          one=True))
    cast_rows = temp_db.q(
        "SELECT COALESCE(cc.sheet,ch.sheet) AS sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? AND cc.status='active'", (chat_id,))

    seeded = commit._known_name_roster(chat, cast_rows)

    assert "Guinan" not in seeded
