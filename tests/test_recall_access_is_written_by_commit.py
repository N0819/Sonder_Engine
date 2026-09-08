"""The stage proposes what came back; the commit records it.

Review 2026-09-07 finding A78. `access_count`/`last_accessed` answer one
question -- did this memory ever come BACK to the character -- and
`tools/remember_lines.py` and `tools/salience_replay.py` read them as their
entire answer. The character stage's own recall bumped them mid-pipeline,
from a stage that is otherwise read-only: a reroll of one character step, a
resume, a replay each moved the number, so the counter partly measured how
often the engine had been asked to recompute a beat rather than how often a
mind reached for a memory.

The stage now proposes the row ids on its step output
(`recalled_memory_ids`, the same shape `unbidden_probe` already had) and
`commit_memory`/`commit_memories` makes the one write for the variant that
stands. A repeated id is still a second reach: two micro-rounds, or the
ponder lane over the ordinary one, moved the counter twice while
`search_memories` made the write itself, and `record_memory_access` peels
that multiplicity off rather than collapsing it.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

from mind.memory import record_memory_access, search_memories
import mind.memory_context as memory_context
from agents.common import (_MERGE_APPEND_FIELDS, _MERGE_NON_SCHEMA_KEYS,
                           _merge_character_results)


def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))


def _char(temp_db, name):
    return temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, "{}", "{}", time.time()))


def _mem(temp_db, chat_id, char_id, content, *, turn_idx=1):
    return temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist) "
        "VALUES(?,?,?,'episodic','episode','witnessed',0.8,?,?)",
        (chat_id, char_id, turn_idx, content, content))


@pytest.fixture
def bank(temp_db):
    chat_id = _chat(temp_db)
    mine = _char(temp_db, "Mara")
    return {"chat": chat_id, "mine": mine,
            "a": _mem(temp_db, chat_id, mine, "the lantern guttered"),
            "b": _mem(temp_db, chat_id, mine, "the lantern was relit")}


def _counts(temp_db, chat_id):
    return {r["id"]: (r["access_count"], r["last_accessed_turn"])
            for r in temp_db.q(
                "SELECT id, access_count, last_accessed_turn FROM memories "
                "WHERE chat_id=?", (chat_id,))}


class TestTheWrite:
    def test_a_row_reached_once_is_counted_once(self, bank, temp_db):
        record_memory_access([bank["a"]], current_turn_idx=7)

        assert _counts(temp_db, bank["chat"])[bank["a"]] == (1, 7)
        assert _counts(temp_db, bank["chat"])[bank["b"]] == (0, None)

    def test_a_row_reached_twice_in_one_beat_is_counted_twice(self, bank,
                                                              temp_db):
        """Two lanes returning the same row moved the counter twice when
        `search_memories` made the write; routing it through one call must
        not quietly redefine the number."""
        record_memory_access([bank["a"], bank["b"], bank["a"]],
                             current_turn_idx=7)

        counts = _counts(temp_db, bank["chat"])
        assert counts[bank["a"]] == (2, 7)
        assert counts[bank["b"]] == (1, 7)

    def test_no_turn_leaves_the_turn_column_alone(self, bank, temp_db):
        """NULL means "reached, but not during play at a known turn" -- a
        preview endpoint or a tool. A guessed turn would be worse."""
        record_memory_access([bank["a"]])

        assert _counts(temp_db, bank["chat"])[bank["a"]] == (1, None)

    def test_nothing_reached_writes_nothing(self, bank, temp_db):
        before = _counts(temp_db, bank["chat"])

        assert record_memory_access([]) == 0
        assert record_memory_access([None, None]) == 0
        assert _counts(temp_db, bank["chat"]) == before


class TestTheReadOnlyStage:
    def test_the_character_payload_asks_for_no_write(self):
        """The defect, pinned at its own site: every retrieval lane in the
        character memory context asks for no durable write. Read off the
        calls rather than the text, so a comment saying so cannot pass for
        the thing itself."""
        # The sibling by `__file__`, which is what the facade rule permits a
        # test to name: this parses its source, it does not call through it.
        module = ast.parse(
            Path(memory_context.__file__).read_text(encoding="utf-8"))
        builder = next(
            node for node in ast.walk(module)
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_character_memory_context")
        lanes = [node for node in ast.walk(builder)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "search_memories"]

        assert len(lanes) == 3, "a retrieval lane was added or removed"
        for call in lanes:
            asked = {kw.arg: kw.value for kw in call.keywords}
            assert isinstance(asked.get("record_access"), ast.Constant)
            assert asked["record_access"].value is False

    def test_a_plain_search_still_records_nothing(self, bank, temp_db):
        before = _counts(temp_db, bank["chat"])
        assert search_memories(bank["chat"], bank["mine"], "lantern", k=4,
                               current_turn_idx=9, viewer_frame_id=None)
        assert _counts(temp_db, bank["chat"]) == before


class TestTheProposal:
    def test_the_ids_ride_the_step_output_and_accumulate_across_rounds(self):
        """`_merge_character_results` starts from the later round alone, so
        an unclassified key is dropped without a warning. This one appends,
        because a row reached in both rounds came back in both."""
        assert "recalled_memory_ids" in _MERGE_APPEND_FIELDS
        assert "recalled_memory_ids" in _MERGE_NON_SCHEMA_KEYS

        merged = _merge_character_results(
            {"recalled_memory_ids": [11, 12]},
            {"recalled_memory_ids": [12, 13]})

        assert merged["recalled_memory_ids"] == [11, 12, 12, 13]

    def test_a_round_that_recalled_nothing_does_not_erase_the_earlier_one(self):
        merged = _merge_character_results({"recalled_memory_ids": [11]}, {})

        assert merged["recalled_memory_ids"] == [11]


class TestTheCommit:
    """End to end: the ids a character step proposed reach the counter, and
    they reach it from the commit rather than from the stage."""

    def _ctx(self, temp_db, bank, proposed):
        from core.pipeline_context import ChatData, PipelineContext, TurnData

        cid = bank["chat"]
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (cid, bank["mine"], "active", "{}"))
        temp_db.wset(cid, "scene", {
            "rooms": {"kitchen": {"name": "Kitchen"}},
            "positions": {"Mara": "kitchen"},
            "entities": {}, "attire": {}, "overlays": {}})
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (cid, 4, "", time.time()))
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (cid,))
        ctx = PipelineContext(
            chat=ChatData(id=cid, name="T", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=cid, idx=4, player_input="",
                          created=time.time()),
            cast=cast, input="")
        ctx.director_resolve = {"summary": "", "resolved_event": "",
                                "dialogue_log": []}
        ctx.perception_outcome = {"views": {str(bank["mine"]): ""}}
        ctx.character_results = {
            bank["mine"]: {"sequence": [], "recalled_memory_ids": proposed}}
        return ctx

    def test_the_commit_records_what_the_stage_proposed(self, bank, temp_db,
                                                        monkeypatch):
        from persist import commit_memory_write
        from persist.commit import commit_memories

        monkeypatch.setattr(commit_memory_write,
                            "maybe_consolidate_character_memory",
                            lambda *a, **k: None)
        ctx = self._ctx(temp_db, bank, [bank["a"], bank["a"], bank["b"]])

        commit_memories(ctx, nonce=0)

        counts = _counts(temp_db, bank["chat"])
        assert counts[bank["a"]] == (2, 4)
        assert counts[bank["b"]] == (1, 4)

    def test_a_beat_whose_minds_recalled_nothing_writes_nothing(
            self, bank, temp_db, monkeypatch):
        from persist import commit_memory_write
        from persist.commit import commit_memories

        monkeypatch.setattr(commit_memory_write,
                            "maybe_consolidate_character_memory",
                            lambda *a, **k: None)
        before = _counts(temp_db, bank["chat"])

        commit_memories(self._ctx(temp_db, bank, []), nonce=0)

        assert _counts(temp_db, bank["chat"]) == before
