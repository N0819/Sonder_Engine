"""What is still open is one list, not two.

Review 2026-09-07 B32: the character memory payload answered "what is still
unsettled" twice. `unresolved_from_past` carried the union of the mind's live
`active_concerns` and its summary's `unresolved_threads`, deduped, capped and
stamped `temporal_status: remembered_past`; beside it a bare
`unresolved_threads` key repeated the summary field alone -- a different set of
items, under no temporal label. A third site, the retrieval aspect literally
labelled "what is still unsettled", read the summary field alone as well.

One question, one source: `unresolved_items` in `mind/memory_context.py`, read
by the payload and by the aspect -- and merged so that neither source's length
can delete the other.
"""

from __future__ import annotations

import time

import pytest

from mind import memory
from mind import memory_context


@pytest.fixture
def mind_with_threads(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Unsettled", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist) "
        "VALUES(?,?,?,'episodic','episode','witnessed',0.6,?,?)",
        (chat_id, char_id, 1, "The gate stood open.", "the open gate"))
    memory.save_memory_summary(
        chat_id, char_id, "I have been walking a long time.",
        start_turn_idx=0, end_turn_idx=4,
        key_phrases=["the gate"],
        unresolved_threads=["who left the gate open", "where the dog went"])
    return {"chat": chat_id, "char": char_id}


def _context(mind, **kw):
    return memory.build_character_memory_context(
        chat_id=mind["chat"], char_id=mind["char"], current_turn_idx=6,
        current_view="The gate is still open.",
        active_state={"mood": "wary", "goal": "reach the ford",
                      "active_concerns": ["the dog is still missing",
                                          "who left the gate open"]},
        **kw)


def test_payload_names_what_is_open_exactly_once(mind_with_threads):
    ctx = _context(mind_with_threads)
    assert "unresolved_threads" not in ctx, (
        "the summary's open threads reach the mind through "
        "`unresolved_from_past`; a second bare copy is the same fact under a "
        "second name, and without the remembered_past label")
    items = ctx["unresolved_from_past"]["items"]
    assert ctx["unresolved_from_past"]["temporal_status"] == "remembered_past"
    # The union, deduped: a live concern and a remembered thread that say the
    # same thing are one entry.
    assert items == ["the dog is still missing", "who left the gate open",
                     "where the dog went"]


def test_the_retrieval_aspect_asks_the_same_list(mind_with_threads,
                                                 monkeypatch):
    """`memory_context` binds `search_memories` at import, so the caller's own
    name is the only place the call can be observed."""
    seen = {}
    real = memory_context.search_memories

    def spy(*a, **kw):
        if kw.get("aspects") is not None:
            seen["aspects"] = list(kw["aspects"])
        return real(*a, **kw)

    monkeypatch.setattr(memory_context, "search_memories", spy)
    ctx = _context(mind_with_threads)
    unsettled = dict(seen["aspects"])["what is still unsettled"]
    assert unsettled == " ".join(ctx["unresolved_from_past"]["items"])
    assert "the dog is still missing" in unsettled


def test_a_long_concern_list_cannot_erase_the_remembered_threads(
        mind_with_threads):
    """Review 2026-09-07 B32: merging two sources into one capped list must not
    let one source's LENGTH silently delete the other.

    `active_concerns` is free model output -- `llm/schemas.py` declares it a
    `list[str]` bounded only by `FREE_STRING_LIST_LIMIT = 64`, it is replaced
    wholesale each beat from `persist/commit_memory.py`, and nothing prunes it.
    So a mind carrying six or more distinct concerns is a reachable regime, and
    under a concatenate-then-truncate merge it would have owned every slot and
    dropped the summary's dangling threads entirely -- the threads consolidation
    is told to preserve rather than resolve, and after B32 the payload has no
    other path for them.
    """
    ctx = memory.build_character_memory_context(
        chat_id=mind_with_threads["chat"], char_id=mind_with_threads["char"],
        current_turn_idx=6, current_view="The gate is still open.",
        active_state={"mood": "wary", "goal": "reach the ford",
                      "active_concerns": [
                          "the ford may be flooded",
                          "the dog is still missing",
                          "the lantern oil is low",
                          "someone followed me out of the village",
                          "my sister expects me by dark",
                          "the bridge toll went unpaid",
                          "the gate latch is broken"]})
    items = ctx["unresolved_from_past"]["items"]
    assert len(items) == 6
    remembered = ["who left the gate open", "where the dog went"]
    assert [item for item in items if item in remembered], (
        "six live concerns crowded every remembered thread out of the one list "
        "that carries them: " + repr(items))
    # And the live concerns are not themselves crowded out by the threads --
    # the merge is source-blind, not a reversed precedence.
    assert "the ford may be flooded" in items
