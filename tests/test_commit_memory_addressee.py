"""A memory names a body only by the label its owner already holds for it.

**PX3** (the masque, 2026-09-05, firewall). Lisenne's turn-2 dialogue memory
read `I heard Verrin Sault say "You flatter the old man's sensibilities..." to
Ivo Sarn` (the quote here is a promise, which is the category the side-memory
path keeps). The SPEAKER label is recognition-aware -- three lines above, an
unrecognised speaker becomes an appearance label or "a voice" -- and the
addressee was `d["intended_target"]`, taken raw and appended as `f" to
{tgt}"`. Twelve rows across two minds carried the name that way, from turn 2
on, in a story whose whole subject is that neither of them ever learned it. A
view lasts a beat; a memory is cited for the rest of the story.
"""

from __future__ import annotations

import json
import time

from story.character_schema import default_character_data
from persist.commit import commit_memories
from core.pipeline_context import ChatData, PipelineContext, TurnData

_QUOTE = '"I promise the study will be opened before midnight."'


def _story(temp_db, *, known):
    """Three bodies in one room: a hearer, a speaker, an addressee."""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Masque", "", time.time()))
    ids = {}
    for name in ("Lisenne Corvay", "Verrin Sault", "Ivo Sarn"):
        sheet = default_character_data(name)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), "uid_" + name))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        ids[name] = char_id
    temp_db.wset(chat_id, "scene", {
        "rooms": {"gallery": {"name": "The Gallery"}},
        "positions": {name: "gallery" for name in ids},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", known)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 2, "", time.time()))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Masque", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=2, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx.director_resolve = {
        "summary": "A civility, aimed at one man.",
        "resolved_event": "Verrin speaks.",
        "dialogue_log": [{"speaker": "Verrin Sault", "exact_quote": _QUOTE,
                          "volume": "normal", "intended_target": "Ivo Sarn",
                          "tone": ""}],
    }
    ctx.perception_outcome = {"views": {
        str(cid): f"Someone says: {_QUOTE}" for cid in ids.values()}}
    return ctx, ids


def _dialogue_rows(temp_db, monkeypatch, ctx):
    captured = []

    def fake_add_memories_batch(memories=None, *, prepared_batch=None):
        batch = memories if memories is not None else prepared_batch["prepared"]
        captured.extend(batch)
        return list(range(1, len(batch) + 1))

    # commit_memories resolves both names in commit_memory_write's globals
    # since the split; patching the commit facade would be inert.
    from persist import commit_memory_write
    monkeypatch.setattr(commit_memory_write, "add_memories_batch",
                        fake_add_memories_batch)
    monkeypatch.setattr(commit_memory_write,
                        "maybe_consolidate_character_memory",
                        lambda *a, **k: None)
    commit_memories(ctx, nonce=0)
    return [m for m in captured if m["kind"] == "dialogue"]


def test_a_hearer_who_knows_neither_party_names_neither(temp_db, monkeypatch):
    """The live case: Lisenne knows neither the speaker nor the man he is
    speaking to, and her memory must carry no name at all."""
    ctx, ids = _story(temp_db, known={})
    rows = _dialogue_rows(temp_db, monkeypatch, ctx)

    mine = [r for r in rows if r["char_id"] == ids["Lisenne Corvay"]]
    assert mine
    for row in mine:
        assert "Verrin Sault" not in row["content"]
        assert "Ivo Sarn" not in row["content"]
        assert " to " not in row["content"]


def test_a_hearer_who_knows_the_addressee_may_name_them(temp_db, monkeypatch):
    """The complement: a name the hearer holds is a name the memory keeps.
    The firewall restricts the FLOW of knowledge, not knowledge itself."""
    ctx, ids = _story(temp_db, known={
        "Lisenne Corvay": ["Verrin Sault", "Ivo Sarn"]})
    rows = _dialogue_rows(temp_db, monkeypatch, ctx)

    mine = [r for r in rows if r["char_id"] == ids["Lisenne Corvay"]]
    assert mine
    assert any("to Ivo Sarn" in row["content"] for row in mine)


def test_a_line_aimed_at_the_hearer_is_addressed_to_them(
        temp_db, monkeypatch):
    """A mind has a word for itself and it is not its own name."""
    ctx, ids = _story(temp_db, known={})
    ctx.director_resolve["dialogue_log"][0]["intended_target"] = \
        "Lisenne Corvay"
    rows = _dialogue_rows(temp_db, monkeypatch, ctx)

    mine = [r for r in rows if r["char_id"] == ids["Lisenne Corvay"]]
    assert mine
    assert any(row["content"].endswith(" to me") for row in mine)
    assert not any("Lisenne Corvay" in row["content"] for row in mine)
