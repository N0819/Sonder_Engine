"""A summary window reaches a mind only where its era is visible.

Summaries are DERIVED from rows: `consolidate_character_memory` folds the rows
the present can see into a window, and `maybe_consolidate_character_memory`
refuses to run anywhere but the present. So every window is a present-era
fact, closing on its `end_turn_idx`, and the frame rule the raw rows obey
(`frames.is_memory_visible`) is the rule a window must obey too.

It did not (review 2026-11-01, mind_memory F1, reproduced): the readers
filtered chat, character, scope and turn only, so a native of a past frame
("ten years earlier") was handed the present era's autobiography -- "I watched
the city fall to the invaders and fled north" -- with its unresolved thread,
its earlier windows, its hearsay summary and its origin window, while every
raw row of that era was correctly hidden from it. The `when` stamp read "at a
time you cannot place against now", which marked the leak rather than
stopping it.
"""

from __future__ import annotations

import time

import pytest

from core.db import active_frame_id
from core.frames import create_frame
from mind import memory
from mind.memory import SUMMARY_SCOPE_FIRSTHAND, SUMMARY_SCOPE_HEARSAY

FALL = "I watched the city fall to the invaders and fled north."
THREAD = "whether my brother survived the fall"
ORIGIN = "I grew up above the harbour, mending nets with my father."
HEARD = "They say the invaders came over the mountain pass."


@pytest.fixture
def story(temp_db):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Fall", "", time.time()))
    mara = temp_db.qi("INSERT INTO characters(name,sheet,source,created) "
                      "VALUES(?,?,?,?)", ("Mara", "{}", "{}", time.time()))
    for t in range(1, 21):
        memory.add_memory(chat, mara, None, "episodic", "witnessed", 0.8,
                          f"Turn {t}: the city fell to the invaders and I ran.",
                          turn_idx=t, frame_id=None, event_key=f"fall:{t}")
    # Three present-era windows: an origin, a middle chapter, the latest.
    memory.save_memory_summary(chat, mara, ORIGIN, start_turn_idx=1, end_turn_idx=6)
    memory.save_memory_summary(chat, mara, "The harbour burned while I watched.",
                               start_turn_idx=7, end_turn_idx=12)
    memory.save_memory_summary(chat, mara, FALL, start_turn_idx=13, end_turn_idx=18,
                               unresolved_threads=[THREAD])
    memory.save_memory_summary(chat, mara, HEARD, scope=SUMMARY_SCOPE_HEARSAY,
                               start_turn_idx=13, end_turn_idx=18)
    return {"chat": chat, "mara": mara}


def _context(story, frame_id):
    token = active_frame_id.set(frame_id)
    try:
        # `goal_held` fires the origin-on-drift lane, so all five summary
        # lanes are asked for in one call.
        return memory.build_character_memory_context(
            story["chat"], story["mara"], 30, "A quiet morning in the market.",
            {"goal_held": True})
    finally:
        active_frame_id.reset(token)


def _summary_text(ctx):
    """Every summary a payload delivered, as one string."""
    parts = [ctx.get("autobiographical_summary") or ""]
    parts += [w.get("what_i_lived_through_then") or ""
              for w in ctx.get("earlier_in_my_life") or []]
    parts.append((ctx.get("where_i_came_from") or {}).get("what_i_lived_through_then") or "")
    parts += [str(v) for k, v in ctx.items()
              if k not in ("autobiographical_summary",) and isinstance(v, str)]
    parts += [str(i) for i in (ctx.get("unresolved_from_past") or {}).get("items") or []]
    return "\n".join(parts)


def test_a_native_of_a_past_frame_is_handed_no_present_era_summary(story):
    past = create_frame(story["chat"], label="ten years earlier", ordinal=-1, kind="past")
    ctx = _context(story, past)
    delivered = _summary_text(ctx)
    for text in (FALL, THREAD, ORIGIN, HEARD, "The harbour burned"):
        assert text not in delivered, f"{text!r} reached a mind ten years before it"
    assert not ctx.get("autobiographical_summary")
    assert not ctx.get("earlier_in_my_life")
    assert not ctx.get("where_i_came_from")
    assert not (ctx.get("summary_citations") or {})


def test_a_traveller_standing_in_the_past_keeps_their_own_life(story):
    """Continuity is the traveller's: they lived the present era, so its
    summary is theirs wherever they stand -- the raw-row rule, unchanged."""
    past = create_frame(story["chat"], label="ten years earlier", ordinal=-1,
                        kind="past", travelers=[story["mara"]])
    ctx = _context(story, past)
    assert ctx.get("autobiographical_summary") == FALL
    assert THREAD in (ctx.get("unresolved_from_past") or {}).get("items")


def test_the_present_and_a_later_era_still_read_the_present_summary(story):
    ctx = _context(story, None)
    assert ctx.get("autobiographical_summary") == FALL
    # The origin comes by one lane or the other: `where_i_came_from`, or
    # `earlier_in_my_life` when similarity already reached it.
    assert ORIGIN in _summary_text(ctx)
    assert HEARD in _summary_text(ctx)
    later = create_frame(story["chat"], label="a year on", ordinal=1, kind="future")
    ctx = _context(story, later)
    assert ctx.get("autobiographical_summary") == FALL


def test_an_unmerged_split_reads_only_the_windows_that_closed_before_it(story):
    """A spatial split sees its parent's history up to the split and nothing
    formed after -- a window closing after the split blends what this side
    has not lived, and cannot be un-blended."""
    split = create_frame(story["chat"], label="the far shore", ordinal=0, kind="spatial",
                         parent_frame_id=None, split_turn_idx=12)
    windows = memory.visible_summary_rows(
        story["chat"], story["mara"], SUMMARY_SCOPE_FIRSTHAND,
        before_turn_idx=30, viewer_frame_id=split)
    assert [w["end_turn_idx"] for w in windows] == [12, 6]
