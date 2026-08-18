"""One vocabulary for `state_diff.cast_changes[].status`.

The field is a free string on an untyped entry, and until now the commit that
acts on it tested `stt in ("active", "dormant")` and dropped everything else
in silence -- while `schemas.py`'s own worked example writes `"departed"` and
the specialist's prompt named no vocabulary at all. A character who walked out
of the story stayed `active` in the roster, which means present in the scene,
addressable, and running a character step every beat.

It was invisible because departure still WORKS through the other readers of
`cast_changes`, which key on the entry existing rather than on what it says.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_cast_changes
from story.scene import cast_change_status


def _chat_with_cast(db, *names):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story", "", time.time()))
    for name in names:
        char = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, json.dumps({"identity": {"name": name}}), "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,?)",
              (cid, char, "active"))
    return cid


def _commit(db, cid, changes):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Story", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1, player_input="",
                      created=time.time(), frame_id=None),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": {"cast_changes": changes}}
    commit_cast_changes(ctx, nonce=0)
    return ctx


def _status(db, cid, name):
    return db.q("SELECT cc.status FROM chat_chars cc JOIN characters ch "
                "ON ch.id=cc.char_id WHERE cc.chat_id=? AND ch.name=?",
                (cid, name), one=True)["status"]


class TestTheVocabulary:
    def test_the_canonical_words_are_the_two_states_a_character_has(self):
        assert cast_change_status("active") == "active"
        assert cast_change_status("dormant") == "dormant"

    def test_a_natural_word_for_leaving_means_leaving(self):
        """The one the engine's own schema example writes."""
        for word in ("departed", "left", "gone", "away", "exited"):
            assert cast_change_status(word) == "dormant", word

    def test_a_natural_word_for_arriving_means_arriving(self):
        for word in ("arrived", "returned", "rejoined", "present"):
            assert cast_change_status(word) == "active", word

    def test_case_and_padding_do_not_decide_a_simulation(self):
        assert cast_change_status("  Departed ") == "dormant"

    def test_an_unrecognized_word_is_None_rather_than_a_guess(self):
        """Not a default, in either direction. The two answers put a mind in
        different simulations, and picking one silently is the defect."""
        for word in ("promoted", "", None, "asleep", 3):
            assert cast_change_status(word) is None, word


class TestTheCommit:
    def test_departed_sends_the_character_offscreen(self, temp_db):
        cid = _chat_with_cast(temp_db, "Merek")

        _commit(temp_db, cid, [{"who": "Merek", "status": "departed",
                                "reason": "rode for the garrison"}])

        assert _status(temp_db, cid, "Merek") == "dormant"

    def test_the_canonical_words_still_work(self, temp_db):
        cid = _chat_with_cast(temp_db, "Merek", "Sable")

        _commit(temp_db, cid, [{"who": "Merek", "status": "dormant"},
                               {"who": "Sable", "status": "active"}])

        assert _status(temp_db, cid, "Merek") == "dormant"
        assert _status(temp_db, cid, "Sable") == "active"

    def test_an_unrecognized_status_warns_instead_of_vanishing(self, temp_db):
        cid = _chat_with_cast(temp_db, "Merek")

        ctx = _commit(temp_db, cid, [{"who": "Merek", "status": "bewildered"}])

        assert _status(temp_db, cid, "Merek") == "active"
        assert any("bewildered" in w for w in ctx.warnings), ctx.warnings

    def test_a_name_that_is_not_in_the_cast_warns(self, temp_db):
        """Previously indistinguishable from an unknown status: both were the
        same silent `continue`."""
        cid = _chat_with_cast(temp_db, "Merek")

        ctx = _commit(temp_db, cid, [{"who": "Nobody", "status": "departed"}])

        assert any("Nobody" in w for w in ctx.warnings), ctx.warnings
