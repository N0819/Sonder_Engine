"""Summary WINDOWS: a character's autobiography is a series, not a single row.

Until schema v23 `memory_summaries` was keyed `(chat_id, char_id, scope)`, so
every consolidation overwrote the one row that scope had. The consequence was
not storage — it was that the summary layer could not be SEARCHED, because
there was nothing to search between. Meanwhile every summary already carried a
maintained embedding: computed on write, re-embedded on a model change, carried
verbatim through every archive and checkpoint, and read by no retrieval path in
the engine.

v23 completes the key with `end_turn_idx`, so consolidation appends a window
and `search_memory_summaries` can rank the vectors that were already there.

What deliberately did NOT change is what a character receives.
`get_memory_summary` still returns one summary — now defined as the latest
window — because consolidation still folds the previous summary into the new
one. Wiring retrieved windows into the payload is a separate change with its
own evidence; making bounded windows the payload without it would silently cost
every character their early history.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

import memory
import providers
from character_schema import default_character_data


@pytest.fixture
def bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Windows", "", time.time()))
    ids = []
    for name in ("Mara", "Vesk"):
        ids.append(temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}", time.time(),
             "char_" + name.lower())))
    return {"chat": chat_id, "chars": ids}


def _window(bank, text, start, end, who=0, **kw):
    memory.save_memory_summary(bank["chat"], bank["chars"][who], text,
                               start_turn_idx=start, end_turn_idx=end, **kw)


# ---- storage ----

def test_two_windows_coexist_where_one_row_used_to_win(bank):
    _window(bank, "She crossed the bridge and met the ferryman.", 0, 10)
    _window(bank, "She reached the city and lost the letter.", 11, 20)
    from db import q
    rows = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=?",
             (bank["chat"], bank["chars"][0]))
    assert len(rows) == 2
    assert {r["end_turn_idx"] for r in rows} == {10, 20}


def test_rewriting_the_same_window_updates_in_place(bank):
    _window(bank, "First telling.", 0, 10)
    _window(bank, "Corrected telling.", 0, 10)
    from db import q
    rows = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=?",
             (bank["chat"], bank["chars"][0]))
    assert len(rows) == 1
    assert rows[0]["summary"] == "Corrected telling."


def test_the_current_summary_is_the_latest_window(bank):
    _window(bank, "She crossed the bridge.", 0, 10)
    _window(bank, "She reached the city.", 11, 20)
    cur = memory.get_memory_summary(bank["chat"], bank["chars"][0])
    assert cur["summary"] == "She reached the city."
    assert (cur["start_turn_idx"], cur["end_turn_idx"]) == (11, 20)


def test_windows_are_per_character(bank):
    _window(bank, "Mara's history.", 0, 10, who=0)
    _window(bank, "Vesk's history.", 0, 10, who=1)
    assert memory.get_memory_summary(
        bank["chat"], bank["chars"][0])["summary"] == "Mara's history."
    assert memory.get_memory_summary(
        bank["chat"], bank["chars"][1])["summary"] == "Vesk's history."


def test_scopes_remain_independent(bank):
    _window(bank, "What she lived.", 0, 10, scope="autobiographical")
    _window(bank, "What she was told.", 0, 10, scope="hearsay")
    assert memory.get_memory_summary(
        bank["chat"], bank["chars"][0],
        "hearsay")["summary"] == "What she was told."
    assert memory.get_memory_summary(
        bank["chat"], bank["chars"][0])["summary"] == "What she lived."


def test_an_empty_bank_still_answers(bank):
    cur = memory.get_memory_summary(bank["chat"], bank["chars"][0])
    assert cur["summary"] == ""
    assert cur["end_turn_idx"] == 0


# ---- retrieval, the thing the vectors were always for ----

def test_the_relevant_era_outranks_the_irrelevant_one(bank):
    _window(bank, "She crossed the bridge at dusk and paid the ferryman "
                  "in silver coins.", 0, 10)
    _window(bank, "She argued with the archivist about a missing ledger "
                  "in the record house.", 11, 20)
    _window(bank, "She slept badly and dreamed of nothing in particular.",
            21, 30)
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "the ferryman and his silver",
        exclude_latest=False)
    assert hits
    assert "ferryman" in hits[0]["summary"]
    assert hits[0]["score"] >= hits[-1]["score"]


def test_the_latest_window_is_excluded_by_default(bank):
    _window(bank, "The bridge and the ferryman.", 0, 10)
    _window(bank, "The city and the lost letter.", 11, 20)
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "the city and the letter")
    # The latest window is what get_memory_summary already returns; a caller
    # sending both must not send it twice.
    assert all(h["end_turn_idx"] != 20 for h in hits)


def test_a_window_that_closed_after_the_deciding_turn_is_withheld(bank):
    """The read seam's rule, applied one layer up: a mind deciding turn N may
    not read a summary of how turn N turned out."""
    _window(bank, "The bridge and the ferryman.", 0, 10)
    _window(bank, "The city and the lost letter.", 11, 20)
    _window(bank, "The fire that has not happened yet.", 21, 30)
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "fire", before_turn_idx=15,
        exclude_latest=False)
    assert all(h["end_turn_idx"] < 15 for h in hits)
    assert all("fire" not in h["summary"] for h in hits)


def test_another_characters_windows_are_never_returned(bank):
    _window(bank, "Mara paid the ferryman in silver.", 0, 10, who=0)
    _window(bank, "Vesk paid the ferryman in silver.", 0, 10, who=1)
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][1], "the ferryman and his silver",
        exclude_latest=False)
    assert len(hits) == 1
    assert hits[0]["summary"].startswith("Vesk")


def test_a_window_embedded_by_another_model_is_skipped_not_compared(bank):
    _window(bank, "The bridge and the ferryman.", 0, 10)
    _window(bank, "The city and the lost letter.", 11, 20)
    from db import qi
    qi("UPDATE memory_summaries SET embedding_model='ancient:model' "
       "WHERE end_turn_idx=10")
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "the ferryman", exclude_latest=False)
    # A cross-model cosine is noise wearing the shape of a score.
    assert all(h["end_turn_idx"] != 10 for h in hits)


def test_k_bounds_the_result(bank):
    for i in range(6):
        _window(bank, f"Era number {i} of her life.", i * 10, i * 10 + 9)
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "her life", k=2,
        exclude_latest=False)
    assert len(hits) == 2


def test_an_empty_window_is_not_a_candidate(bank):
    _window(bank, "", 0, 10)
    _window(bank, "The city and the lost letter.", 11, 20)
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "anything", exclude_latest=False)
    assert all(h["summary"].strip() for h in hits)


def test_searching_an_empty_bank_is_a_noop(bank):
    assert memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "anything") == []


# ---- the portability checklist ----

def test_every_window_survives_a_dump_restore_round_trip(bank):
    _window(bank, "The bridge and the ferryman.", 0, 10)
    _window(bank, "The city and the lost letter.", 11, 20)
    _window(bank, "What she was told in the tavern.", 0, 20, scope="hearsay")
    dumped = memory.dump_memory_summaries(bank["chat"])
    assert len(dumped) == 3

    memory.restore_memory_summaries(bank["chat"], dumped)
    again = memory.dump_memory_summaries(bank["chat"])
    assert len(again) == 3
    assert [(d["scope"], d["start_turn_idx"], d["end_turn_idx"], d["summary"])
            for d in again] == \
           [(d["scope"], d["start_turn_idx"], d["end_turn_idx"], d["summary"])
            for d in dumped]


def test_a_restore_reuses_the_stored_vector_rather_than_re_embedding(
        bank, monkeypatch):
    _window(bank, "The bridge and the ferryman.", 0, 10)
    _window(bank, "The city and the lost letter.", 11, 20)
    dumped = memory.dump_memory_summaries(bank["chat"])

    calls = []

    def _boom(texts, **kw):
        calls.append(texts)
        raise AssertionError("restore must not call the provider")

    monkeypatch.setattr(memory, "embed_texts_meta", _boom)
    memory.restore_memory_summaries(bank["chat"], dumped)
    assert calls == []
    assert len(memory.dump_memory_summaries(bank["chat"])) == 2


# ---- end to end: consolidation was already computing bounded windows ----

@pytest.fixture
def _stub_consolidator(monkeypatch):
    """One LLM call, stubbed. What is under test is the WINDOW BOUNDS the
    engine computes around it, not the model's prose."""
    state = {"n": 0}

    def fake(role, prompt, payload, **kw):
        state["n"] += 1
        return json.dumps({
            "summary": f"Era {state['n']} of her life.",
            "hearsay_summary": "", "surmise_summary": "",
            "key_phrases": [], "unresolved_threads": [], "stable_facts": [],
        })

    monkeypatch.setattr(memory, "chat_complete", fake)
    monkeypatch.setattr(memory, "embed_texts_meta", lambda texts, **k: type(
        "E", (), {"vectors": [providers.cheap_embed(t) for t in texts],
                  "model_key": "stub", "dimensions": 256})())


def _episode(bank, turn_idx, content, who=0):
    memory.add_memory(bank["chat"], bank["chars"][who], None, "episodic",
                      "witnessed", 0.8, content, turn_idx=turn_idx,
                      gist=content)


def test_consolidation_accumulates_windows_instead_of_overwriting(
        bank, _stub_consolidator):
    """The bounds were never the problem. `consolidate_character_memory`
    already computed start/end from the memories of THAT pass only — it is the
    old UNIQUE(chat_id, char_id, scope) that threw the earlier window away on
    every write. Completing the key was the whole fix; consolidation itself is
    unchanged."""
    for i in range(1, 5):
        _episode(bank, i, f"She crossed the bridge, day {i}.")
    memory.consolidate_character_memory(bank["chat"], bank["chars"][0],
                                        through_turn_idx=4, archive_old=False)
    for i in range(5, 9):
        _episode(bank, i, f"She argued with the archivist, day {i}.")
    memory.consolidate_character_memory(bank["chat"], bank["chars"][0],
                                        through_turn_idx=8, archive_old=False)

    from db import q
    rows = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
             "AND scope='autobiographical' ORDER BY end_turn_idx",
             (bank["chat"], bank["chars"][0]))
    assert len(rows) == 2, "the second consolidation overwrote the first"
    assert (rows[0]["start_turn_idx"], rows[0]["end_turn_idx"]) == (1, 4)
    assert (rows[1]["start_turn_idx"], rows[1]["end_turn_idx"]) == (5, 8)
    # And the payload is unchanged: still exactly one summary, the newest.
    assert memory.get_memory_summary(
        bank["chat"], bank["chars"][0])["summary"] == "Era 2 of her life."
    # The earlier era is now reachable, which it never was before.
    hits = memory.search_memory_summaries(
        bank["chat"], bank["chars"][0], "Era 1 of her life.")
    assert [h["end_turn_idx"] for h in hits] == [4]
