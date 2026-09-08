"""The host edits the private history the era's mind actually reads (A80).

`private_knowledge_for` takes `COALESCE(chat_char_frames.state,
chat_chars.state)`, and every committed turn in a frame creates that override
row. The authoring surfaces read and wrote the base row alone, so in any story
with an era the host edited a channel nobody would ever be told.

Two rules now hold, and they are different because the two surfaces are:
the private-history dialog is a per-ERA runtime edit and takes `frame_id`;
the story CARD is per-story, so its sync reaches the base row and every era
that has one -- the host is editing the person, not one of their eras.
"""

import json
import time

import pytest

from web import app
from story.scene import char_state, private_knowledge_for, set_char_state


def _chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("A story", "", time.time()))


def _character(temp_db, name="Alice"):
    return temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps({"identity": {"name": name}}), "{}", time.time()))


def _attach(temp_db, chat_id, char_id, state=None, sheet=None):
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
        "VALUES(?,?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(state or {}),
         json.dumps(sheet) if sheet is not None else None))


def _entry(text):
    return [{"about": "Alice", "content": text, "known_by": ["alice"]}]


class TestCharState:
    """The read half of `set_char_state`, and the one both surfaces use."""

    def test_a_frame_with_no_override_falls_back_to_the_base_row(self, temp_db):
        chat_id = _chat(temp_db)
        alice = _character(temp_db)
        _attach(temp_db, chat_id, alice, {"mood": "calm"})
        future = app.frames_create(
            chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        assert char_state(chat_id, alice, future["id"]) == {"mood": "calm"}

    def test_a_frame_with_an_override_reads_it(self, temp_db):
        chat_id = _chat(temp_db)
        alice = _character(temp_db)
        _attach(temp_db, chat_id, alice, {"mood": "calm"})
        future = app.frames_create(
            chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        set_char_state(chat_id, alice, json.dumps({"mood": "terrified"}),
                       frame_id=future["id"])
        assert char_state(chat_id, alice, future["id"]) == {"mood": "terrified"}
        assert char_state(chat_id, alice) == {"mood": "calm"}

    def test_an_unattached_character_is_none(self, temp_db):
        chat_id = _chat(temp_db)
        assert char_state(chat_id, 999999) is None


class TestTheDialogEditsTheEra:

    def _story_with_an_era(self, temp_db):
        chat_id = _chat(temp_db)
        alice = _character(temp_db)
        _attach(temp_db, chat_id, alice, {"private_history": _entry("I feel fine.")})
        future = app.frames_create(
            chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        # What a committed turn in that frame leaves behind.
        set_char_state(chat_id, alice, json.dumps(
            {"private_history": _entry("I survived the paradox.")}),
            frame_id=future["id"])
        return chat_id, alice, future["id"]

    def test_the_read_shows_the_era_not_the_base_row(self, temp_db):
        chat_id, alice, era = self._story_with_an_era(temp_db)
        assert app.ph_get(chat_id, alice)["entries"][0]["content"] \
            == "I feel fine."
        assert app.ph_get(chat_id, alice, frame_id=era)["entries"][0]["content"] \
            == "I survived the paradox."

    def test_the_write_lands_where_the_mind_reads(self, temp_db):
        chat_id, alice, era = self._story_with_an_era(temp_db)
        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?",
                              (chat_id,), one=True))
        app.ph_put(chat_id, alice, {"entries": _entry("I was warned.")},
                   frame_id=era)

        assert private_knowledge_for(chat, "Alice", frame_id=era)[0]["content"] \
            == "I was warned."
        # And the present is untouched: an era is not the story.
        assert private_knowledge_for(chat, "Alice")[0]["content"] \
            == "I feel fine."

    def test_a_frame_from_another_chat_is_refused(self, temp_db):
        chat_id, alice, _era = self._story_with_an_era(temp_db)
        other = _chat(temp_db)
        stranger = app.frames_create(
            other, {"label": "Elsewhere", "ordinal": 3, "kind": "future"})
        with pytest.raises(Exception):
            app.ph_get(chat_id, alice, frame_id=stranger["id"])


class TestTheCardReachesEveryEra:

    def test_a_card_edit_is_read_by_an_era_that_has_its_own_row(self, temp_db):
        chat_id = _chat(temp_db)
        alice = _character(temp_db)
        card = {"identity": {"name": "Alice"},
                "knowledge": {"private_history": _entry("I feel fine.")}}
        _attach(temp_db, chat_id, alice,
                {"private_history": _entry("I feel fine.")}, sheet=card)
        future = app.frames_create(
            chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        set_char_state(chat_id, alice, json.dumps(
            {"private_history": _entry("I survived the paradox.")}),
            frame_id=future["id"])

        edited = dict(card)
        edited["knowledge"] = {"private_history": _entry("I was warned.")}
        app.chat_char_card_put(chat_id, alice, {"sheet": edited})

        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?",
                              (chat_id,), one=True))
        for frame_id in (None, future["id"]):
            assert (private_knowledge_for(chat, "Alice",
                                          frame_id=frame_id)[0]["content"]
                    == "I was warned."), frame_id

    def test_it_leaves_every_other_live_field_of_the_era_alone(self, temp_db):
        chat_id = _chat(temp_db)
        alice = _character(temp_db)
        card = {"identity": {"name": "Alice"},
                "knowledge": {"private_history": _entry("I feel fine.")}}
        _attach(temp_db, chat_id, alice, {"mood": "calm"}, sheet=card)
        future = app.frames_create(
            chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        set_char_state(chat_id, alice, json.dumps({"mood": "terrified"}),
                       frame_id=future["id"])

        app.chat_char_card_put(chat_id, alice, {"sheet": card})

        assert char_state(chat_id, alice, future["id"])["mood"] == "terrified"
        assert char_state(chat_id, alice)["mood"] == "calm"
