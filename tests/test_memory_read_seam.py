"""Every mind-facing read goes through one seam, and the seam holds.

Two filters decide what a character may legitimately retrieve, and both must
run before any ranking: the turn cutoff (a mind deciding turn N must never read
a memory of how turn N turned out -- audit F1) and frame visibility (another
era's memories are not this mind's to have yet).

They used to be written out again at every read path, and `docs/guides/MEMORY.md`
claimed that repetition was what stopped a new path forgetting them. That is
backwards -- repetition is exactly how a sixth path forgets, because nothing
makes it reproduce five filters it may not know exist. The rules now live in
`memory.visible_memory_rows` with every invariant-bearing argument REQUIRED, so
omitting one is a TypeError rather than a leak.

This file is the enforcement:

* the seam itself drops each class of row;
* every character-facing public API drops them too, adversarially, one class
  at a time;
* the seam cannot be called without stating each rule;
* the set of readers that deliberately cross character boundaries does not
  grow without someone deciding it should.
"""
from __future__ import annotations

import inspect
import re
import time

import pytest

import memory
from memory import (
    HOST_SCOPE_READERS,
    contrast_memory,
    list_memories,
    recent_memory_buffer,
    search_memories,
    visible_memory_rows,
)


def _chat(temp_db, name="T"):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      (name, "", time.time()))


def _char(temp_db, name):
    return temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, "{}", "{}", time.time()))


def _frame(temp_db, chat_id, ordinal, kind="temporal"):
    return temp_db.qi(
        "INSERT INTO frames(chat_id,kind,label,ordinal,created) "
        "VALUES(?,?,?,?,?)",
        (chat_id, kind, "f%s" % ordinal, ordinal, time.time()))


def _mem(temp_db, chat_id, char_id, content, *, turn_idx=1, frame_id=None,
         archived=0):
    return temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist,frame_id,archived) "
        "VALUES(?,?,?,'episodic','episode','witnessed',0.8,?,?,?,?)",
        (chat_id, char_id, turn_idx, content, content, frame_id, archived))


@pytest.fixture
def bank(temp_db):
    """One chat, two characters, and a memory of each excluded class."""
    chat_id = _chat(temp_db)
    mine = _char(temp_db, "Mara")
    theirs = _char(temp_db, "Bram")
    ids = {
        "past": _mem(temp_db, chat_id, mine, "the lantern guttered", turn_idx=3),
        "now": _mem(temp_db, chat_id, mine, "the lantern went out", turn_idx=9),
        "future": _mem(temp_db, chat_id, mine, "the lantern was relit", turn_idx=12),
        "foreign": _mem(temp_db, chat_id, theirs, "the lantern guttered", turn_idx=3),
        "unplaced": _mem(temp_db, chat_id, mine, "the lantern, once", turn_idx=None),
    }
    return {"chat": chat_id, "mine": mine, "theirs": theirs, "ids": ids}


# --- the seam itself -------------------------------------------------------

def test_the_seam_drops_the_turn_being_decided_and_everything_after(bank):
    got = {r["id"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=9,
        viewer_frame_id=None, include_archived=True)}
    assert bank["ids"]["past"] in got
    assert bank["ids"]["now"] not in got, "turn N itself must go -- strictly <"
    assert bank["ids"]["future"] not in got


def test_the_seam_keeps_memories_with_no_place_in_play_order(bank):
    """An imported or authored memory belongs to no turn, so it cannot be
    this turn's leaked outcome."""
    got = {r["id"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=1,
        viewer_frame_id=None, include_archived=True)}
    assert bank["ids"]["unplaced"] in got


def test_the_seam_never_returns_another_character(bank):
    got = {r["id"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=None,
        viewer_frame_id=None, include_archived=True)}
    assert bank["ids"]["foreign"] not in got
    assert all(r["char_id"] == bank["mine"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=None,
        viewer_frame_id=None, include_archived=True))


def test_the_seam_honours_the_archived_policy(temp_db, bank):
    hidden = _mem(temp_db, bank["chat"], bank["mine"], "long ago", turn_idx=1,
                  archived=1)
    kept = {r["id"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=None,
        viewer_frame_id=None, include_archived=True)}
    dropped = {r["id"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=None,
        viewer_frame_id=None, include_archived=False)}
    assert hidden in kept and hidden not in dropped


def test_the_seam_applies_frame_visibility(temp_db, bank):
    """A memory formed in a later era is not this mind's to have yet."""
    later = _frame(temp_db, bank["chat"], 5)
    ahead = _mem(temp_db, bank["chat"], bank["mine"], "much later",
                 turn_idx=2, frame_id=later)
    got = {r["id"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=None,
        viewer_frame_id=None, include_archived=True)}
    assert bank["ids"]["past"] in got
    assert ahead not in got


# --- the seam cannot be called without stating each rule -------------------

@pytest.mark.parametrize("omit", ["before_turn_idx", "viewer_frame_id",
                                  "include_archived"])
def test_every_invariant_argument_is_required(bank, omit):
    """The enforcement mechanism. A caller cannot omit one of these; it can
    only state it, including stating None. Forgetting is a TypeError."""
    kwargs = {"before_turn_idx": 5, "viewer_frame_id": None,
              "include_archived": True}
    kwargs.pop(omit)
    with pytest.raises(TypeError):
        visible_memory_rows(bank["chat"], bank["mine"], **kwargs)


def test_no_invariant_argument_has_a_default():
    sig = inspect.signature(visible_memory_rows)
    for name in ("before_turn_idx", "viewer_frame_id", "include_archived"):
        assert sig.parameters[name].default is inspect.Parameter.empty, name


def test_narrowing_arguments_cannot_readmit_an_excluded_row(bank):
    """`since_turn_idx` only ever narrows. Reaching back past the cutoff with
    it must not pull the future forward."""
    got = {r["id"] for r in visible_memory_rows(
        bank["chat"], bank["mine"], before_turn_idx=9, viewer_frame_id=None,
        include_archived=True, since_turn_idx=0)}
    assert bank["ids"]["future"] not in got
    assert bank["ids"]["now"] not in got


# --- every character-facing API, adversarially -----------------------------

def _character_facing(bank):
    """(label, callable) for each public read that feeds a mind."""
    chat, mine = bank["chat"], bank["mine"]
    return [
        ("search_memories", lambda: search_memories(
            chat, mine, "lantern", k=20, current_turn_idx=9,
            viewer_frame_id=None)),
        ("recent_memory_buffer", lambda: recent_memory_buffer(
            chat, mine, 9, turns=20, limit=50, viewer_frame_id=None)),
        ("list_memories", lambda: list_memories(
            chat, mine, include_archived=True, viewer_frame_id=None)),
    ]


@pytest.mark.parametrize("label", ["search_memories", "recent_memory_buffer",
                                   "list_memories"])
def test_no_character_facing_read_returns_another_character(bank, label):
    call = dict(_character_facing(bank))[label]
    assert all(m["char_id"] == bank["mine"] for m in call())


@pytest.mark.parametrize("label", ["search_memories", "recent_memory_buffer"])
def test_no_mind_facing_read_returns_the_turn_being_decided(bank, label):
    """list_memories is excluded on purpose: it is the host's panel, where
    nobody is deciding a beat and there is no future to withhold."""
    call = dict(_character_facing(bank))[label]
    got = {m["id"] for m in call()}
    assert bank["ids"]["now"] not in got
    assert bank["ids"]["future"] not in got


@pytest.mark.parametrize("label", ["search_memories", "recent_memory_buffer",
                                   "list_memories"])
def test_no_character_facing_read_returns_an_invisible_frame(temp_db, bank, label):
    later = _frame(temp_db, bank["chat"], 5)
    ahead = _mem(temp_db, bank["chat"], bank["mine"], "much later",
                 turn_idx=2, frame_id=later)
    call = dict(_character_facing(bank))[label]
    assert ahead not in {m["id"] for m in call()}


def test_contrast_memory_holds_the_same_three_rules(temp_db, bank):
    """Its own bank floor means it needs a real corpus before it returns
    anything, so it is exercised separately rather than in the sweep."""
    later = _frame(temp_db, bank["chat"], 5)
    ahead, foreign, future = [], [], []
    for i in range(memory._CONTRAST_MIN_BANK + 5):
        _mem(temp_db, bank["chat"], bank["mine"],
             "a quiet hour in the archive number %d" % i, turn_idx=i % 8)
        foreign.append(_mem(temp_db, bank["chat"], bank["theirs"],
                            "another mind's hour %d" % i, turn_idx=i % 8))
        ahead.append(_mem(temp_db, bank["chat"], bank["mine"],
                          "an era away %d" % i, turn_idx=1, frame_id=later))
        future.append(_mem(temp_db, bank["chat"], bank["mine"],
                           "not yet %d" % i, turn_idx=40 + i))
    got = {m["id"] for m in contrast_memory(
        bank["chat"], bank["mine"], "the lantern went out", 9, k=12,
        viewer_frame_id=None)}
    assert got, "expected contrast_memory to return something to test"
    assert not got & set(foreign)
    assert not got & set(ahead)
    assert not got & set(future)


# --- the host-scope exception stays an exception ---------------------------

def test_no_unlisted_cross_character_reader(temp_db):
    """Cross-character reads answer a question ABOUT the cast, never one a
    character asks itself, so they must never feed a mind's context. This
    fails when a new one appears without being named, which is the moment to
    decide whether it is really host-facing."""
    src = inspect.getsource(memory)
    offenders = []
    for match in re.finditer(r"\ndef (\w+)\(", src):
        name = match.group(1)
        body = src[match.end():]
        nxt = re.search(r"\ndef \w+\(", body)
        body = body[:nxt.start()] if nxt else body
        if "FROM memories" not in body:
            continue
        if "char_id=?" in body or "char_id = ?" in body:
            continue
        if "m.char_id" in body or "WHERE id=?" in body:
            pass
        offenders.append(name)
    unlisted = [
        n for n in offenders
        if n not in HOST_SCOPE_READERS
        # Maintenance and round-trip paths are chat- or row-scoped by
        # definition: dumps, deletes, the embedding rebuilds. They never
        # reach a character's context.
        and not n.startswith(("dump_", "restore_", "prepare_", "apply_",
                              "rebuild_", "delete_", "import_", "_"))
        and n not in ("update_memory", "reconcile_inference_confidence",
                      "embedding_bank_status")
    ]
    assert not unlisted, (
        "new cross-character memory reader(s) %s -- add to "
        "memory.HOST_SCOPE_READERS if genuinely host-facing, or scope to "
        "char_id via visible_memory_rows" % unlisted)


def test_the_listed_host_readers_still_exist():
    for name in HOST_SCOPE_READERS:
        assert callable(getattr(memory, name)), name
