"""A newer memory that changes what an older one states brings itself back
beside it (`mind/memory_links.py`; the concept lab, 2026-09-30, §10-13).

Class-level throughout: a bare chat, a bare character, rows that state a
figure and later state another. The link is formed at commit by the decision
model's yes, stored on the NEWER row by `event_key`, and followed at recall
only through the firewall's own read.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from llm import decisions
from llm.providers import EmbeddingBatch
from story.character_schema import default_character_data
from tests.helpers import patch_provider_seam

DIM = 48


def _vector(text):
    """Words hashed into a fixed space: rows that share words lie close."""
    v = np.zeros(DIM, dtype=np.float32)
    for word in str(text or "").lower().split():
        v[sum(map(ord, word.strip(".,:;!?'\""))) % DIM] += 1.0
    norm = float(np.linalg.norm(v)) or 1.0
    return v / norm


@pytest.fixture
def embeddings(monkeypatch):
    def _embed(texts, **_kw):
        return EmbeddingBatch(vectors=[_vector(t) for t in texts],
                              model_key="test-words", dimensions=DIM)
    patch_provider_seam(monkeypatch, "embed_texts_meta", _embed)


@pytest.fixture
def jev(monkeypatch):
    """The decision model: yes where the OLDER quote holds `older_says` and
    the NEWER one `newer_says`; every question it was asked is kept."""
    asked = []
    rule = {"older_says": None, "newer_says": None, "raise": None}

    def _answer(state, questions):
        if rule["raise"]:
            raise rule["raise"]
        out = {}
        for key, q in questions.items():
            asked.append((state, key, q["instructions"]))
            older, _sep, newer = q["instructions"].partition("\n\n")
            yes = (rule["older_says"] is not None and rule["older_says"] in older
                   and rule["newer_says"] in newer)
            p = 0.9 if yes else 0.1
            out[key] = {"type": "choice", "choice": "yes" if yes else "no",
                        "probabilities": {"yes": p, "no": 1 - p}}
        return out

    monkeypatch.setattr(decisions, "OVERRIDE", _answer)
    return asked, rule


def _story(temp_db, name="A"):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    return chat_id, char_id


def _mint(chat_id, char_id, turn_idx, content, *, key=None, supersedes=None,
          category="episode", kind="episodic"):
    from mind.memory import add_memories_batch
    row = {"chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": turn_idx,
           "kind": kind, "category": category, "provenance": "witnessed",
           "salience": 0.6, "content": content,
           "event_key": key or f"event:{char_id}:{turn_idx}:{category}",
           "encoded_at_seconds": None if turn_idx is None else float(turn_idx) * 60.0}
    if supersedes is not None:
        row["supersedes"] = supersedes
    return add_memories_batch([row])[0]


def _batch(chat_id, char_id, turn_idx, content, **extra):
    from mind.memory import prepare_memories_batch
    return prepare_memories_batch([{
        "chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": turn_idx,
        "kind": "episodic", "category": "episode", "provenance": "witnessed",
        "salience": 0.6, "content": content,
        "event_key": f"event:{char_id}:{turn_idx}:episode", **extra}])


def _row(temp_db, mid):
    from mind.memory import _row_memory
    return _row_memory(temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True))


# ---- formation ----------------------------------------------------------------

def test_a_turn_memory_links_the_older_memory_it_changes(temp_db, embeddings, jev):
    from mind.memory import add_memories_batch, form_memory_links
    asked, rule = jev
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    _mint(chat_id, char_id, 4, "The innkeeper sang by the fire.")
    rule.update(older_says="twenty five crowns", newer_says="forty crowns")
    batch = _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now.")
    record = form_memory_links(chat_id, batch, turn_idx=7, names={char_id: "A"})
    assert record["linked"] == 1 and record["asked"] == 2
    assert {state for state, _k, _q in asked} == {"YOU ARE A."}
    mid = add_memories_batch(prepared_batch=batch)[0]
    assert _row(temp_db, mid)["supersedes"] == [f"event:{char_id}:3:episode"]


def test_only_this_minds_earlier_rows_are_ever_asked_about(temp_db, embeddings, jev):
    """The candidates are the firewall's own read at the beat committed:
    another mind's rows, this turn's own earlier minting (a re-commit) and a
    later turn's are never quoted."""
    from mind.memory import form_memory_links
    asked, _rule = jev
    chat_id, char_id = _story(temp_db)
    other = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("B", json.dumps(default_character_data("B")), "{}", time.time()))
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    _mint(chat_id, other, 3, "The ferry fare is thirty crowns, said the other.", key="event:other")
    _mint(chat_id, char_id, 7, "The ferry fare was minted before.", key="event:same-turn")
    _mint(chat_id, char_id, 9, "The ferry fare in the future.", key="event:later")
    form_memory_links(chat_id, _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now."),
                      turn_idx=7, names={char_id: "A"})
    quoted = " ".join(q for _s, _k, q in asked)
    assert "twenty five" in quoted
    for absent in ("thirty crowns", "minted before", "in the future"):
        assert absent not in quoted


def test_without_a_decision_model_no_link_is_formed(temp_db, embeddings):
    from mind.memory import form_memory_links
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    batch = _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now.")
    record = form_memory_links(chat_id, batch, turn_idx=7, names={})
    assert record == {"unasked": "no decision model is configured"}
    assert not batch["prepared"][0].get("supersedes")


def test_a_refused_request_forms_no_link_and_fails_nothing(temp_db, embeddings, jev):
    from mind.memory import form_memory_links
    _asked, rule = jev
    rule["raise"] = decisions.DecisionError("jev 503")
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    batch = _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now.")
    record = form_memory_links(chat_id, batch, turn_idx=7, names={char_id: "A"})
    assert "jev 503" in record["failed"][str(char_id)]
    assert not batch["prepared"][0].get("supersedes")


def test_hashed_vectors_are_never_compared(temp_db, jev):
    """A beat whose embeddings fell back to the local hash has no meaning to
    rank by: it asks nothing rather than asking about the wrong rows."""
    from mind.memory import form_memory_links
    asked, _rule = jev
    chat_id, char_id = _story(temp_db)
    batch = _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now.")
    batch["embedded"].fallback = True
    assert form_memory_links(chat_id, batch, turn_idx=7, names={})["unasked"] == \
        "no comparable vectors"
    assert not asked


def test_the_commit_forms_the_link_on_the_row_it_mints(temp_db, embeddings, jev, monkeypatch):
    """End to end through the write path: two committed beats, the second
    stating a figure the first stated otherwise."""
    from persist import commit_memory_write
    from persist.commit import commit_memories
    from tests.test_memory_clock_stamp import _commit_context
    monkeypatch.setattr(commit_memory_write, "maybe_consolidate_character_memory",
                        lambda *a, **k: None)
    _asked, rule = jev
    chat_id, char_id = _story(temp_db)
    first = _commit_context(temp_db, chat_id, char_id, turn_idx=1, duration=30)
    first.perception_outcome = {"views": {str(char_id): "The ferry fare is twenty five crowns."}}
    commit_memories(first, nonce=0)
    rule.update(older_says="twenty five crowns", newer_says="forty crowns")
    second = _commit_context(temp_db, chat_id, char_id, turn_idx=2, duration=30)
    second.perception_outcome = {"views": {str(char_id): "The ferry fare is forty crowns now."}}
    result = commit_memories(second, nonce=0)
    older = temp_db.q("SELECT event_key FROM memories WHERE turn_idx=1 AND category='episode'",
                      one=True)["event_key"]
    newer = temp_db.q("SELECT supersedes FROM memories WHERE turn_idx=2 AND category='episode'",
                      one=True)["supersedes"]
    assert json.loads(newer) == [older]
    assert result["links"]["linked"] == 1


# ---- recall -------------------------------------------------------------------

def _recalled(temp_db, mid, score=0.8):
    return {**_row(temp_db, mid), "score": score}


def test_recall_brings_the_newer_memory_in_beside_the_one_it_changes(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    old = _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    unrelated = _mint(chat_id, char_id, 4, "The innkeeper sang by the fire.")
    new = _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.",
                supersedes=[f"event:{char_id}:3:episode"])
    record = {}
    out = pull_successors(chat_id, char_id,
                          [_recalled(temp_db, old), _recalled(temp_db, unrelated, 0.5)],
                          current_turn_idx=10, record=record)
    assert [m["id"] for m in out] == [old, new, unrelated]
    assert out[1]["score"] > 0.8 and record == {"links_pulled": 1, "links_capped": 0}


def test_a_successor_the_mind_cannot_see_yet_is_never_pulled(temp_db, embeddings):
    """The deciding turn's own rows are not yet the mind's past: a link
    formed on turn 7 is not followed while turn 7 is being decided."""
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    old = _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.",
          supersedes=[f"event:{char_id}:3:episode"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, old)], current_turn_idx=7)
    assert [m["id"] for m in out] == [old]


def test_another_minds_link_is_never_followed(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    other = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("B", json.dumps(default_character_data("B")), "{}", time.time()))
    old = _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    _mint(chat_id, other, 7, "The ferry fare is forty crowns now.", key="event:b7",
          supersedes=[f"event:{char_id}:3:episode"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, old)], current_turn_idx=10)
    assert [m["id"] for m in out] == [old]


def test_a_chain_is_followed_to_its_newest_row(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    first = _mint(chat_id, char_id, 1, "The fare is ten crowns.")
    middle = _mint(chat_id, char_id, 4, "The fare is twenty crowns.",
                   supersedes=[f"event:{char_id}:1:episode"])
    last = _mint(chat_id, char_id, 8, "The fare is forty crowns.",
                 supersedes=[f"event:{char_id}:4:episode"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, first)], current_turn_idx=10)
    assert [m["id"] for m in out] == [first, middle, last]


def test_a_successor_already_delivered_is_not_brought_twice(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    old = _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    new = _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.",
                supersedes=[f"event:{char_id}:3:episode"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, old)], current_turn_idx=10,
                          delivered=[_row(temp_db, new)])
    assert [m["id"] for m in out] == [old]


def test_successors_past_the_cap_are_counted_not_dropped_unsaid(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    a = _mint(chat_id, char_id, 1, "The fare is ten crowns.")
    b = _mint(chat_id, char_id, 2, "The bridge is open.")
    _mint(chat_id, char_id, 5, "The fare is twenty crowns.", supersedes=[f"event:{char_id}:1:episode"])
    _mint(chat_id, char_id, 6, "The bridge is closed.", supersedes=[f"event:{char_id}:2:episode"])
    record = {}
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, a), _recalled(temp_db, b)],
                          current_turn_idx=10, record=record, cap=1)
    assert len(out) == 3 and record == {"links_pulled": 1, "links_capped": 1}


def test_nothing_a_model_reads_names_the_link(temp_db, embeddings):
    """A pulled row is projected exactly as an ordinary recalled row: no
    field, no label, no line the grader reads says it changed anything."""
    from mind.memory import MemoryClock, _with_reading, memory_line, pull_successors
    chat_id, char_id = _story(temp_db)
    old = _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    new = _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.",
                supersedes=[f"event:{char_id}:3:episode"])
    pulled = pull_successors(chat_id, char_id, [_recalled(temp_db, old)], current_turn_idx=10)[1]
    clock = MemoryClock(chat_id, char_id, 10, now_seconds=900.0, viewer_frame_id=None)
    ordinary = _recalled(temp_db, new)
    assert _with_reading(pulled, clock) == _with_reading(ordinary, clock)
    assert memory_line(pulled, 10) == memory_line(ordinary, 10)
    # Its own `memory_ref` is how a mind cites it; the row it changes is
    # named nowhere.
    linked_to = f"event:{char_id}:3:episode"
    for text in (json.dumps(_with_reading(pulled, clock)), memory_line(pulled, 10)):
        assert linked_to not in text and "supersed" not in text.lower()


def test_build_context_delivers_the_successor_with_its_recalled_row(temp_db, embeddings):
    """Through the assembly: the net's order picks the older row alone (the
    preview path, no model call), and the newer row arrives beside it."""
    from mind.memory import build_character_memory_context
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns at the harbour gate.")
    for i in range(4, 8):
        _mint(chat_id, char_id, i, f"Rain on the roof, beat {i}, nothing else.")
    _mint(chat_id, char_id, 9, "Now the fare is forty.", supersedes=[f"event:{char_id}:3:episode"])
    ctx = build_character_memory_context(
        chat_id, char_id, 30, "The ferry fare at the harbour gate, twenty five crowns.",
        {"goal": "cross the river"}, recall_limit=1, recent_turns=1)
    recalled = [m["details"] if "details" in m else m.get("gist")
                for m in ctx["recalled_old_memories"]]
    assert any("twenty five" in str(r) for r in recalled)
    assert any("forty" in str(r) for r in recalled)
    assert ctx["_internal"]["picker"]["links_pulled"] == 1


# ---- round trips --------------------------------------------------------------

def test_the_link_rides_a_rollback_and_an_archive(temp_db, embeddings):
    """Keyed by `event_key`, the link needs no remapping: a checkpoint
    restore re-mints every row id and an archive import every chat id, and
    the newer row still names the older one."""
    from mind.memory import _supersedes_of
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    chat_id, char_id = _story(temp_db)
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
               (chat_id, 0, "", time.time()))
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.",
          supersedes=[f"event:{char_id}:3:episode"])

    def links(chat):
        return [_supersedes_of(r["supersedes"]) for r in temp_db.q(
            "SELECT supersedes FROM memories WHERE chat_id=? AND turn_idx=7", (chat,))]

    ensure_checkpoint(chat_id, 0)
    temp_db.qi("UPDATE memories SET supersedes='' WHERE chat_id=?", (chat_id,))
    restore_checkpoint(chat_id, 0)
    assert links(chat_id) == [[f"event:{char_id}:3:episode"]]
    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(chat_id)})
    new_chat = imported["id"] if isinstance(imported, dict) else imported
    assert links(new_chat) == [[f"event:{char_id}:3:episode"]]


def test_a_bank_imported_into_another_story_drops_its_links(temp_db, embeddings):
    """Import blanks every `event_key`, so a link would name nothing there."""
    from mind.memory import dump_character_memories, import_character_memories
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.",
          supersedes=[f"event:{char_id}:3:episode"])
    other_chat, other_char = _story(temp_db, name="A2")
    import_character_memories(other_chat, other_char, dump_character_memories(chat_id, char_id),
                              allow_foreign_personas=True)
    rows = temp_db.q("SELECT supersedes FROM memories WHERE chat_id=?", (other_chat,))
    assert rows and all(r["supersedes"] == "" for r in rows)


# ---- review round 5 (2026-10-05) ----------------------------------------------

def test_the_row_that_changed_a_memory_comes_though_it_was_changed_in_turn(temp_db, embeddings):
    """A link says a newer memory changes something the older one states,
    never WHICH thing: following the chain to its end handed a mind the fare
    from turn 3 and a walk to the inn from turn 8, and the turn-7 row that
    changed the fare by no lane at all."""
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    a = _mint(chat_id, char_id, 3, "At the dock the fare is twenty five crowns; Anna waits by the rope.")
    b = _mint(chat_id, char_id, 7, "The fare is forty crowns now; Anna waits by the rope.",
              supersedes=[f"event:{char_id}:3:episode"])
    c = _mint(chat_id, char_id, 8, "Anna left the dock and walked up to the inn.",
              supersedes=[f"event:{char_id}:7:episode"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, a)], current_turn_idx=20)
    assert [m["id"] for m in out] == [a, b, c]
    # ...and a chain whose end the payload already carries still brings the row
    # that changed this one.
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, a)], current_turn_idx=20,
                          delivered=[_row(temp_db, c)])
    assert [m["id"] for m in out] == [a, b]


def test_every_row_that_changed_it_comes_newest_first_then_the_newest_reached(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    a = _mint(chat_id, char_id, 3, "The bridge is open and the toll is two coins.")
    b = _mint(chat_id, char_id, 5, "The toll is three coins now.", supersedes=[f"event:{char_id}:3:episode"])
    c = _mint(chat_id, char_id, 6, "The bridge is closed for repairs.", supersedes=[f"event:{char_id}:3:episode"])
    d = _mint(chat_id, char_id, 9, "The toll is gone; the bridge is free.", supersedes=[f"event:{char_id}:5:episode"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, a)], current_turn_idx=20)
    assert [m["id"] for m in out] == [a, c, b, d]


def test_a_correction_outlasts_its_turnless_predecessor_in_the_unbidden_swap(temp_db, embeddings):
    """A turnless memory (a promotion seed, an imported or host-written row)
    sorts last in the payload, and the swap gave up the first of two tied
    rows -- the correction. A hair of score settles every tie the right way."""
    from agents.character import _attach_unbidden
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    old = _mint(chat_id, char_id, None, "The ferry fare is twenty five crowns.", key="promotion:1:1:0")
    _mint(chat_id, char_id, 9, "Now the fare is forty.", supersedes=["promotion:1:1:0"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, old, 0.5)], current_turn_idx=30)
    scores = {m["event_key"]: m["score"] for m in out}
    assert scores[f"event:{char_id}:9:episode"] > scores["promotion:1:1:0"]
    context = {"recalled_old_memories": [{"memory_ref": k} for k in
                                         (f"event:{char_id}:9:episode", "promotion:1:1:0")],
               "_internal": {"scores": scores}}
    _attach_unbidden(context, {"memory_ref": "unbidden"}, recall_limit=2)
    assert [m["memory_ref"] for m in context["recalled_old_memories"]] == [f"event:{char_id}:9:episode"]


@pytest.mark.parametrize("answer", ["yes", ["yes"], 0.9, {"probabilities": ["yes", 0.9]}])
def test_a_malformed_answer_is_a_no_and_never_fails_the_commit(temp_db, embeddings, monkeypatch, answer):
    from mind.memory import form_memory_links
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, qs: {k: answer for k in qs})
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    batch = _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now.")
    assert form_memory_links(chat_id, batch, turn_idx=7, names={})["linked"] == 0
    assert not batch["prepared"][0].get("supersedes")


def test_only_the_ten_most_alike_older_memories_are_asked_about(temp_db, embeddings, jev):
    from mind.memory import LINK_CANDIDATES, _cos, _vec, form_memory_links
    asked, _rule = jev
    chat_id, char_id = _story(temp_db)
    words = "ferry fare crowns dock rope harbour gate toll bridge river boat oar".split()
    for i in range(14):
        _mint(chat_id, char_id, i + 1, " ".join(words[: (i % 12) + 1]) + f" note{i}")
    # Its text leans one way and its gist and key phrases the other, so the
    # content vector and the cue vector rank the older rows differently: the
    # ranking must be the content's (the lab compared whole memories).
    batch = _batch(chat_id, char_id, 30, "ferry fare crowns dock rope harbour " * 4,
                   gist="toll bridge river boat oar", key_phrases=["toll bridge river boat oar"])
    form_memory_links(chat_id, batch, turn_idx=30, names={char_id: "A"})
    vec = batch["embedded"].vectors[0]
    rows = temp_db.q("SELECT content, embedding FROM memories WHERE char_id=? AND turn_idx<30", (char_id,))
    ranked = sorted(rows, key=lambda r: -_cos(vec, _vec(r["embedding"])))
    expected = {r["content"] for r in ranked[:LINK_CANDIDATES]}
    quoted = {r["content"] for r in rows if any(r["content"] in q for _s, _k, q in asked)}
    assert len(asked) == LINK_CANDIDATES and quoted == expected


def test_an_inference_or_another_models_memory_is_never_asked_about(temp_db, embeddings, jev, monkeypatch):
    """Only the kinds the lab compared (a turn's memory, a self record), and
    only rows whose vectors can be compared with this beat's."""
    from mind.memory import form_memory_links
    asked, _rule = jev
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns at the dock.")
    _mint(chat_id, char_id, 4, "I think the ferry fare is rising at the dock.",
          kind="inference", category="inference", key="event:inference")

    def _embedder(model_key):
        def _embed(texts, **_kw):
            return EmbeddingBatch(vectors=[_vector(t) for t in texts], model_key=model_key,
                                  dimensions=DIM)
        return _embed

    patch_provider_seam(monkeypatch, "embed_texts_meta", _embedder("other-model"))
    _mint(chat_id, char_id, 5, "The ferry fare at the dock is posted on a board.", key="event:other")
    patch_provider_seam(monkeypatch, "embed_texts_meta", _embedder("test-words"))
    form_memory_links(chat_id, _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now."),
                      turn_idx=7, names={char_id: "A"})
    quoted = " ".join(q for _s, _k, q in asked)
    assert "twenty five" in quoted
    assert "I think" not in quoted and "posted on a board" not in quoted


def test_a_successor_another_frame_holds_is_never_pulled(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    frame = temp_db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) VALUES(?,?,?,?,?)",
                       (chat_id, "F", 1, "other", time.time()))
    old = _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    from mind.memory import add_memories_batch
    add_memories_batch([{"chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": 7,
                         "kind": "episodic", "category": "episode", "provenance": "witnessed",
                         "salience": 0.6, "content": "The ferry fare is forty crowns now.",
                         "event_key": "event:elsewhere", "frame_id": frame,
                         "supersedes": [f"event:{char_id}:3:episode"]}])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, old)], current_turn_idx=10,
                          viewer_frame_id=None)
    assert [m["id"] for m in out] == [old]


def test_a_refused_request_is_a_turn_warning(temp_db, embeddings, jev, monkeypatch):
    from persist import commit_memory_write
    from persist.commit import commit_memories
    from tests.test_memory_clock_stamp import _commit_context
    monkeypatch.setattr(commit_memory_write, "maybe_consolidate_character_memory",
                        lambda *a, **k: None)
    _asked, rule = jev
    chat_id, char_id = _story(temp_db)
    first = _commit_context(temp_db, chat_id, char_id, turn_idx=1, duration=30)
    first.perception_outcome = {"views": {str(char_id): "The ferry fare is twenty five crowns."}}
    commit_memories(first, nonce=0)
    rule["raise"] = decisions.DecisionError("jev 503")
    second = _commit_context(temp_db, chat_id, char_id, turn_idx=2, duration=30)
    second.perception_outcome = {"views": {str(char_id): "The ferry fare is forty crowns now."}}
    commit_memories(second, nonce=0)
    assert any("memory links not formed" in w and "jev 503" in w for w in second.warnings)


def test_an_existing_key_written_again_keeps_its_links(temp_db, embeddings):
    """The upsert's UPDATE path writes the column like its INSERT."""
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.", key="event:k")
    _mint(chat_id, char_id, 7, "The ferry fare is forty crowns now.", key="event:k",
          supersedes=["event:older"])
    row = temp_db.q("SELECT supersedes FROM memories WHERE event_key='event:k'", one=True)
    assert json.loads(row["supersedes"]) == ["event:older"]


@pytest.mark.parametrize("p,links", [(0.5, 1), (0.49, 0)])
def test_the_link_floor_is_inclusive(temp_db, embeddings, monkeypatch, p, links):
    from mind.memory import form_memory_links
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, qs: {
        k: {"type": "choice", "probabilities": {"yes": p, "no": 1 - p}} for k in qs})
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 3, "The ferry fare is twenty five crowns.")
    batch = _batch(chat_id, char_id, 7, "The ferry fare is forty crowns now.")
    assert form_memory_links(chat_id, batch, turn_idx=7, names={})["linked"] == links


def test_a_successor_must_be_newer_than_the_memory_it_changes(temp_db, embeddings):
    from mind.memory import pull_successors
    chat_id, char_id = _story(temp_db)
    later = _mint(chat_id, char_id, 5, "The ferry fare is forty crowns now.")
    _mint(chat_id, char_id, 2, "The ferry fare is twenty five crowns.",
          supersedes=[f"event:{char_id}:5:episode"])
    out = pull_successors(chat_id, char_id, [_recalled(temp_db, later)], current_turn_idx=10)
    assert [m["id"] for m in out] == [later]
