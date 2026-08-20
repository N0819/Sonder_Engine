"""A memory carried in from another story may not name that story's player.

`import_character_memories` is the additive path behind
`POST /api/chats/{cid}/characters/{ch}/memories/import`, and it copied
`content` straight through. Every other cross-story read scrubs the previous
player's handle; this one did not, so importing a bank moved one player's
persona name into another player's story as a fact a mind can recall.

That is the plain shape of a firewall breach and not a subtle one: the
receiving mind has no channel to that person. They were never perceived here,
never spoken of here, never inferred from anything here. The name simply
appears in a memory.

REFUSED rather than scrubbed, deliberately. Rewriting the prose would be
authoring -- deciding what a character remembers -- and an import is a HOST
action: one deliberate act, fully retryable, where a loud failure costs a retry
and a silent one costs the invariant the engine exists to keep. The override is
there because two stories legitimately sharing a player is a real case.

Two smaller faults in the same function, fixed with it: `archived` rode the
export and was never read back, so retired memories came back alive; and
`frame_id` fell through to the ambient contextvar rather than being stated.
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory


def _persona(db, name):
    return db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (name, json.dumps({"identity": {"name": name}}), "{}"))


def _chat_with_player(db, chat_name, persona_id):
    return db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        (chat_name, "", time.time(), persona_id))


@pytest.fixture
def _two_stories(temp_db):
    """Two stories with different players, and one character in the second."""
    theirs = _persona(temp_db, "Dana Osei")
    mine = _persona(temp_db, "Sarah Chen")
    _chat_with_player(temp_db, "their story", theirs)
    target = _chat_with_player(temp_db, "my story", mine)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    return target, char_id


class TestAForeignPlayerIsRefused:
    def test_a_memory_naming_another_storys_player_is_refused(
            self, _two_stories, temp_db):
        target, char_id = _two_stories
        with pytest.raises(ValueError, match="Dana Osei"):
            memory.import_character_memories(target, char_id, [
                {"content": "Dana Osei asked me to keep the ledger quiet."}])
        assert not temp_db.q(
            "SELECT 1 FROM memories WHERE chat_id=?", (target,)), \
            "a refused import must leave nothing behind"

    def test_the_error_says_what_it_found(self, _two_stories):
        target, char_id = _two_stories
        with pytest.raises(ValueError) as excinfo:
            memory.import_character_memories(target, char_id, [
                {"content": "Dana Osei asked me to keep the ledger quiet."}])
        message = str(excinfo.value)
        assert "no channel" in message, "say WHY, not just no"
        assert "allow_foreign_personas" in message, "say how to proceed"

    def test_this_storys_own_player_is_not_foreign(self, _two_stories):
        """The receiving story's own player is someone this mind may
        legitimately remember."""
        target, char_id = _two_stories
        assert memory.import_character_memories(target, char_id, [
            {"content": "Sarah Chen left the lantern burning on the sill."}]) == 1

    def test_a_name_inside_a_longer_word_does_not_trip_it(self, _two_stories):
        """Word boundaries, for the same reason the cue matcher uses them: a
        refusal that fires on a substring would block ordinary prose."""
        target, char_id = _two_stories
        assert memory.import_character_memories(target, char_id, [
            {"content": "The danish on the counter had gone stale."}]) == 1

    def test_a_host_who_means_it_may_override(self, _two_stories):
        """Two stories can legitimately share a player. The escape hatch is
        explicit and named, so it appears in the caller rather than being a
        default nobody notices."""
        target, char_id = _two_stories
        assert memory.import_character_memories(
            target, char_id,
            [{"content": "Dana Osei asked me to keep the ledger quiet."}],
            allow_foreign_personas=True) == 1


class TestTheOtherTwoFaults:
    def test_an_archived_memory_does_not_come_back_alive(self, _two_stories,
                                                         temp_db):
        """`archived` rides the export. Dropping it on the way in resurrects
        rows the source story had already retired."""
        target, char_id = _two_stories
        memory.import_character_memories(target, char_id, [
            {"content": "The gate stood open all night.", "archived": True},
            {"content": "She crossed the yard at dawn.", "archived": False},
        ])
        rows = temp_db.q(
            "SELECT content, archived FROM memories WHERE chat_id=? ORDER BY id",
            (target,))
        by_archived = {r["content"].split()[1]: r["archived"] for r in rows}
        assert by_archived["gate"] == 1, "a retired memory must stay retired"
        assert by_archived["crossed"] == 0, "a live one must stay live"

    def test_frame_id_is_stated_rather_than_inherited(self, _two_stories,
                                                      temp_db):
        """It fell through to the ambient contextvar, which in a worker thread
        reads the thread default rather than the frame being imported into --
        the same class as the B5 thread-pool defect."""
        from core.db import active_frame_id

        target, char_id = _two_stories
        token = active_frame_id.set(4242)
        try:
            memory.import_character_memories(target, char_id, [
                {"content": "The bell rang twice before anyone moved."}])
        finally:
            active_frame_id.reset(token)
        rows = temp_db.q("SELECT frame_id FROM memories WHERE chat_id=?", (target,))
        assert rows and all(r["frame_id"] is None for r in rows), \
            "an import must not inherit whatever frame happened to be ambient"
