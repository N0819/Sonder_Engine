"""Rebuilding the windows the singleton destroyed.

Before schema v23 a scope held one summary row and each consolidation
overwrote it, so a long story ends holding a summary of its most recent ten
turns and nothing behind it. Live, chat 38 — 118 turns, the longest story in
the corpus — every one of its three characters has exactly one surviving
window, and 82-87% of their memories sit under no summary at all.

The raw memories were never deleted, so the eras are recoverable: consolidate
those turn ranges again. `backfill_memory_summary_windows` walks forward from a
character's first memory to the earliest surviving window in aligned steps,
chaining each result into the next as `previous_summary`, exactly as the
forward path would have at the time.

The invariant it rests on is the one `docs/UNBUILT.md` §1.21 flagged as worth
testing before anything wrote an old window: writing OLDER rows must not move
the consolidation cursor. `maybe_consolidate_character_memory` reads the
first-hand row's `end_turn_idx` as that cursor and `get_memory_summary` orders
by `end_turn_idx DESC`, so it holds — but it holds by construction elsewhere,
which is exactly the kind of thing that stops holding silently.
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory
from persist import checkpoints
from core.db import q, qi
from tests.helpers import patch_provider_seam


@pytest.fixture
def _consolidator(monkeypatch):
    """The consolidator is one LLM call; what is under test is the windowing
    around it, so it answers with the range it was handed."""
    seen = []

    def fake(role, prompt, payload, **kw):
        data = json.loads(payload)
        turns = [m["turn_idx"] for m in data["memories_chronological"]]
        seen.append({"turns": (min(turns), max(turns)),
                     "previous": data["previous_summary"]["summary"],
                     "n": len(turns)})
        return json.dumps({
            "summary": f"She lived through turns {min(turns)} to {max(turns)}.",
            "hearsay_summary": "", "surmise_summary": "",
            "key_phrases": [f"turns-{min(turns)}"],
            "unresolved_threads": [], "stable_facts": [],
        })

    patch_provider_seam(monkeypatch, "chat_complete", fake)
    return seen


@pytest.fixture
def story(temp_db):
    """A hundred-turn life whose only surviving summary covers turns 90-99 —
    the shape chat 38 is actually in."""
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Long", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    for t in range(0, 100):
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
            "provenance,salience,content,gist) "
            "VALUES(?,?,?,'episodic','episode','witnessed',0.6,?,?)",
            (chat_id, char_id, t, f"Something happened on turn {t}.",
             f"turn {t}"))
    memory.save_memory_summary(chat_id, char_id,
                               "She has been travelling a long time.",
                               start_turn_idx=90, end_turn_idx=99)
    return {"chat": chat_id, "char": char_id}


def _windows(story, scope=memory.SUMMARY_SCOPE_FIRSTHAND):
    return [(r["start_turn_idx"], r["end_turn_idx"]) for r in q(
        "SELECT start_turn_idx,end_turn_idx FROM memory_summaries WHERE "
        "chat_id=? AND char_id=? AND scope=? ORDER BY end_turn_idx",
        (story["chat"], story["char"], scope))]


# ---- what it rebuilds ----

def test_the_missing_eras_come_back(story, _consolidator):
    assert _windows(story) == [(90, 99)]
    out = memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert out["windows"] == 9
    assert _windows(story) == [(0, 9), (10, 19), (20, 29), (30, 39), (40, 49),
                               (50, 59), (60, 69), (70, 79), (80, 89), (90, 99)]


def test_the_windows_abut_the_survivor_rather_than_overlapping_it(story,
                                                                 _consolidator):
    """Counted BACKWARD from the surviving window's boundary. Aligning to turn
    0 instead would leave a ragged seam wherever the live cadence had drifted,
    and two windows both claiming the same turns."""
    qi("DELETE FROM memory_summaries WHERE chat_id=?", (story["chat"],))
    memory.save_memory_summary(story["chat"], story["char"], "Recently.",
                               start_turn_idx=93, end_turn_idx=99)
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    wins = _windows(story)
    assert (93, 99) in wins
    assert max(e for s, e in wins if e < 93) == 92
    # No turn is claimed by two windows.
    covered = [t for s, e in wins for t in range(s, e + 1)]
    assert len(covered) == len(set(covered))


def test_each_window_is_handed_the_one_before_it(story, _consolidator):
    """Chained exactly as the forward path chains, so a backfilled life reads
    as one continuous account rather than nine unrelated paragraphs."""
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert _consolidator[0]["previous"] == ""
    for earlier, later in zip(_consolidator, _consolidator[1:]):
        assert str(earlier["turns"][0]) in later["previous"]


def test_windows_are_written_oldest_first(story, _consolidator):
    turns = [c["turns"] for c in _consolidator] or None
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    turns = [c["turns"] for c in _consolidator]
    assert turns == sorted(turns)


# ---- what it must not disturb ----

def test_the_consolidation_cursor_does_not_move(story, _consolidator):
    """The invariant the whole operation rests on. Move this and the forward
    path either re-folds the same memories forever or skips a window, and
    neither raises — it shows up as a character who has forgotten a stretch of
    their own story, fifty beats later."""
    before = memory.get_memory_summary(story["chat"], story["char"])
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    after = memory.get_memory_summary(story["chat"], story["char"])
    assert after["end_turn_idx"] == before["end_turn_idx"] == 99
    assert after["summary"] == before["summary"]


def test_nothing_is_archived(story, _consolidator):
    """The forward path retires low-salience memories it has just folded in.
    Doing that here would archive hundreds of rows at once on the strength of
    a summary written long after the fact."""
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert q("SELECT COUNT(*) AS c FROM memories WHERE chat_id=? AND archived=1",
             (story["chat"],), one=True)["c"] == 0


def test_the_surviving_window_is_not_rewritten(story, _consolidator):
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert all(c["turns"][1] < 90 for c in _consolidator)


def test_running_it_twice_changes_nothing(story, _consolidator):
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    first = _windows(story)
    calls = len(_consolidator)
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    # Every window now exists, so the floor has moved to turn 0 and there is
    # nothing left below it. Idempotent by the floor, not by a guard.
    assert _windows(story) == first
    assert len(_consolidator) == calls


def test_backfilled_windows_can_be_carried_through_checkpoint_restore(
        story, _consolidator):
    checkpoints.ensure_checkpoint(story["chat"], 100)
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert checkpoints.propagate_memory_summaries_to_checkpoints(
        story["chat"], story["char"]) == 1
    qi("DELETE FROM memory_summaries WHERE chat_id=?", (story["chat"],))
    checkpoints.restore_checkpoint(story["chat"], 100)
    assert _windows(story) == [
        (0, 9), (10, 19), (20, 29), (30, 39), (40, 49),
        (50, 59), (60, 69), (70, 79), (80, 89), (90, 99)]


def test_summary_propagation_never_puts_future_windows_in_an_early_checkpoint(
        story, _consolidator):
    blob = checkpoints.snapshot_state(story["chat"])
    blob["memory_summaries"] = []
    qi("INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
       (story["chat"], 50, json.dumps(blob), time.time()))
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    checkpoints.propagate_memory_summaries_to_checkpoints(
        story["chat"], story["char"])
    row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=50",
            (story["chat"],), one=True)
    stored = json.loads(row["blob"])["memory_summaries"]
    assert stored
    assert all(int(s["end_turn_idx"]) < 50 for s in stored)


# ---- edges ----

def test_a_bank_with_no_summary_at_all_is_left_to_the_forward_path(temp_db,
                                                                  _consolidator):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Fresh", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Vesk", "{}", "{}", time.time()))
    temp_db.qi("INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
               "provenance,salience,content,gist) "
               "VALUES(?,?,3,'episodic','episode','witnessed',0.6,'x','x')",
               (chat_id, char_id))
    out = memory.backfill_memory_summary_windows(chat_id, char_id)
    assert out == {"windows": 0, "turns": None, "skipped": 0}
    assert _consolidator == []


def test_a_character_who_was_absent_for_a_stretch_gets_no_window_for_it(
        story, _consolidator):
    """An interior hole — the character is off-screen for thirty turns. There
    is nothing to summarise, and a window over it would be the consolidator
    inventing continuity out of an empty list."""
    q("DELETE FROM memories WHERE chat_id=? AND turn_idx>=30 AND turn_idx<60",
      (story["chat"],))
    out = memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert out["skipped"] == 3
    assert all(not (30 <= s < 60) for s, _e in _windows(story))


def test_the_walk_starts_at_the_first_memory_not_at_turn_zero(story,
                                                              _consolidator):
    """A character who joins the story late has no turns 0-39 to forget. The
    leading emptiness is not a gap to skip, it is simply before them."""
    q("DELETE FROM memories WHERE chat_id=? AND turn_idx<40", (story["chat"],))
    out = memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert out["skipped"] == 0
    assert out["turns"] == (40, 89)
    assert all(s >= 40 for s, _e in _windows(story) if _e < 90)


def test_an_unknown_character_is_an_error_not_a_silent_noop(story):
    with pytest.raises(ValueError):
        memory.backfill_memory_summary_windows(story["chat"], 9999)


def test_progress_is_reported_per_window(story, _consolidator):
    seen = []
    memory.backfill_memory_summary_windows(
        story["chat"], story["char"],
        on_window=lambda s, e, n: seen.append((s, e, n)))
    assert seen[0] == (0, 9, 10)
    assert len(seen) == 9


def test_the_window_size_is_configurable(story, _consolidator):
    memory.backfill_memory_summary_windows(story["chat"], story["char"],
                                           window=30)
    assert _windows(story) == [(0, 29), (30, 59), (60, 89), (90, 99)]


# ---- and the point of it: the payload can now reach them ----

def test_a_backfilled_era_reaches_the_character(story, _consolidator):
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    ctx = memory.build_character_memory_context(
        story["chat"], story["char"], current_turn_idx=100,
        current_view="She lived through turns 20 to 29.",
        active_state={"goal": "", "mood": ""})
    lived = " ".join(w["what_i_lived_through_then"]
                     for w in ctx["earlier_in_my_life"])
    assert "turns 20 to 29" in lived


# ---- a window of nothing is not a window ----

def test_a_window_of_pure_placeholder_is_not_summarised(story, _consolidator):
    """`commit.py` already refuses to MINT a memory from a view that says only
    "You are in an unspecified area" — an absence is not an episode. Banks
    written before that guard still carry them: 369 rows across the live
    corpus, and in the longest story 85 of one character's 101 memories.

    Consolidation had no such rule, so a backfill over those turns spends an
    LLM call to render an absence into prose and hands it to the character as
    a stretch of life they lived. Measured on chat 38: 13 of 27 backfilled
    windows summarised nothing but the placeholder."""
    q("UPDATE memories SET content='You are in an unspecified area.', "
      "gist='You are in an unspecified area.' WHERE chat_id=? AND turn_idx<40",
      (story["chat"],))
    out = memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert out["skipped"] == 4
    assert all(s >= 40 for s, _e in _windows(story) if _e < 90)
    assert all(c["turns"][0] >= 40 for c in _consolidator)


def test_placeholders_are_dropped_from_a_window_that_also_has_content(
        story, _consolidator):
    """Not all-or-nothing: a beat the character sat out does not belong in the
    account of a window they were otherwise present for."""
    q("UPDATE memories SET content='You are in an unspecified area.' "
      "WHERE chat_id=? AND turn_idx<10 AND turn_idx%2=0", (story["chat"],))
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    assert _consolidator[0]["n"] == 5


def test_the_forward_path_carries_the_account_forward_over_an_empty_window(
        story, _consolidator):
    """The forward path cannot simply skip: `maybe_consolidate` reads the
    first-hand row's `end_turn_idx` as its cursor, so a stalled cursor
    re-consolidates the same rows every ten turns forever. It advances the
    cursor with the PREVIOUS account intact — and asks no model, because there
    is nothing to ask about."""
    q("DELETE FROM memory_summaries WHERE chat_id=?", (story["chat"],))
    memory.save_memory_summary(story["chat"], story["char"],
                               "She crossed the mountains.",
                               start_turn_idx=0, end_turn_idx=49)
    q("UPDATE memories SET content='You are in an unspecified area.', "
      "gist='You are in an unspecified area.' WHERE chat_id=? AND turn_idx>=50",
      (story["chat"],))
    before = len(_consolidator)
    out = memory.consolidate_character_memory(story["chat"], story["char"],
                                              through_turn_idx=99)
    assert len(_consolidator) == before          # no LLM call
    assert out["end_turn_idx"] == 99             # cursor advanced
    assert out["summary"] == "She crossed the mountains."   # account intact


# ---- the host-facing seam ----

def test_coverage_reports_the_hole_the_button_offers_to_fill(story):
    cov = memory.memory_summary_coverage(story["chat"], story["char"])
    assert cov["total"] == 100
    assert cov["covered"] == 10          # only the surviving 90-99 window
    assert cov["uncovered"] == 90
    assert cov["first_turn"] == 0 and cov["floor"] == 90
    assert cov["missing_windows"] == 9


def test_coverage_reports_nothing_to_do_once_rebuilt(story, _consolidator):
    memory.backfill_memory_summary_windows(story["chat"], story["char"])
    cov = memory.memory_summary_coverage(story["chat"], story["char"])
    assert cov["missing_windows"] == 0
    assert cov["uncovered"] == 0


def test_coverage_does_not_count_placeholders_as_a_hole_to_fill(story):
    """A bank of empty views has nothing to summarise. Offering to rebuild it
    would spend a call per window rendering an absence into prose."""
    q("UPDATE memories SET content='You are in an unspecified area.', "
      "gist='You are in an unspecified area.' WHERE chat_id=? AND turn_idx<90",
      (story["chat"],))
    cov = memory.memory_summary_coverage(story["chat"], story["char"])
    assert cov["placeholders"] == 90
    assert cov["uncovered"] == 0
    assert cov["missing_windows"] == 0
