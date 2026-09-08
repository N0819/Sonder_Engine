"""Temporal frames: a diegetic-time axis distinct from turns.idx (play
order). A frame is a contiguous run of turns declared to occur at one
in-fiction era -- a flash-forward, a visit to the past, an immortal
character's life read at a different point. NULL frame_id (on turns and
memories) always means "the present" -- the chat's original, implicit
era -- so an ordinary chat that never time-travels never touches this
feature at all.

This is deliberately the coarse, minimal slice: `ordinal` is a small
integer era marker (negative = past, positive = future, by convention
only), not a precise timestamp -- narrative time travel jumps between a
handful of eras, it doesn't get scrubbed continuously.

CONCURRENCY MODEL: frames support genuinely simultaneous play -- two
players can be eras apart, each independently advancing their own
frame's turns at once. The mutable per-era state (known/scene/
simulation_clock/relationships:*) is NOT swapped in and out of shared
rows; it lives natively at frame-scoped storage keys (see db.py's
active_frame_id contextvar and _scoped_world_key), set once per pipeline
run from the turn row's own frame_id -- never from ambient state, and
never inferred by director_interpret from prose; a frame is only ever
entered by an explicit turn-creation request naming it. The append-only
memories ledger is never duplicated or rewritten either -- it is
filtered by `is_memory_visible`, which is what makes this an epistemic
cursor rather than a branching-memory tree.

Character state/status (mood, stance, active/dormant) is also
frame-isolated, via the chat_char_frames overlay table: a per-frame
override row, falling back to the character's ordinary chat_chars row
in any frame that has never diverged from baseline. A character can
therefore genuinely be simultaneously alive in the past and dead in the
future. World entities, placements, conditions, scheduled events, and
lorebooks remain chat-global rather than frame-partitioned -- that
slicing is real follow-on work, not attempted here.

SPATIAL FRAMES (kind="spatial") are a different axis from the
past/future/other frames above: two parties simply far apart RIGHT NOW,
not visiting a different era. A spatial frame shares its parent's
`ordinal` (the same diegetic "now") but records `parent_frame_id` and
`split_turn_idx` (the global turns.idx play-order position at the
moment they parted). Because it shares the parent's ordinal, the
ordinary is_memory_visible ordinal rule would make parent and child
instantly, bidirectionally visible to each other -- exactly backwards
for an actual spatial separation. While `merged_turn_idx` is NULL, a
spatial frame and its parent (or another sibling split from the same
parent) are INCOMPARABLE instead: each side only sees the OTHER side's
memories formed at-or-before the split, never afterward. Once
`merged_turn_idx` is set (the parties reunited), the split is over and
the ordinary ordinal rule applies again -- since ordinals are now
equal, that means full, permanent, bidirectional visibility, matching a
real reunion where both sides eventually catch each other up. See
spatial_frames.py for the deterministic proximity-based split/merge
detector built on top of this; frames.py itself only defines the
visibility rule, never decides when to split or merge.
"""

from __future__ import annotations

import json
import time

from core.db import q, qi

PRESENT_ORDINAL = 0


def _present_frame():
    return {
        "id": None, "chat_id": None, "label": "Present", "ordinal": PRESENT_ORDINAL,
        "kind": "present", "travelers": [], "nonexistent_cast": [], "created": None,
        "parent_frame_id": None, "split_turn_idx": None, "merged_turn_idx": None,
    }


def _frame_from_row(row):
    return {
        "id": row["id"], "chat_id": row["chat_id"], "label": row["label"],
        "ordinal": row["ordinal"], "kind": row["kind"],
        "travelers": json.loads(row["travelers"]),
        "nonexistent_cast": json.loads(row["nonexistent_cast"]),
        "created": row["created"],
        "parent_frame_id": row["parent_frame_id"],
        "split_turn_idx": row["split_turn_idx"],
        "merged_turn_idx": row["merged_turn_idx"],
    }


def get_frame(frame_id):
    """Returns a plain dict, or None if frame_id doesn't exist. frame_id
    of None is a valid input -- it always resolves to the implicit
    present frame, never a lookup miss."""
    if frame_id is None:
        return _present_frame()
    row = q("SELECT * FROM frames WHERE id=?", (frame_id,), one=True)
    return _frame_from_row(row) if row else None


def frame_index(chat_id):
    """Every frame of one chat in ONE select, keyed by frame_id.

    For a reader that wants the whole set anyway. The implicit present is in
    it under `None`, so a caller never has to special-case it.
    """
    index = {None: _present_frame()}
    for row in q("SELECT * FROM frames WHERE chat_id=?", (int(chat_id),)):
        index[row["id"]] = _frame_from_row(row)
    return index


def frame_lookup(frame_id, index):
    """One frame, remembered in `index` so a repeated id costs one SELECT.

    The lookup a per-ROW visibility check needs. `is_memory_visible` asks for
    a frame two to six times for every memory it judges, and a mind's recall
    judges its whole bank on every read -- so a framed chat paid hundreds of
    single-row SELECTs to answer a question about a handful of declared eras
    (review 2026-09-07, C15). One query per distinct era, not per row.

    `index` is any dict the caller owns and drops; `{}` is the ordinary
    starting point, and it stays EMPTY until something is actually asked for.
    That is what keeps the common case free: an unframed chat compares None
    against None, never reaches a lookup, and so still issues no query at all
    -- rather than paying for an index of a table it has no rows in.

    `index is None` means "no memo": the plain per-call SELECT. An id the
    index does not hold is not an error either way -- it is fetched once and
    remembered -- so a row pointing at another chat's frame, or at one
    deleted underneath the read, answers exactly as it did before.
    """
    if index is None:
        return get_frame(frame_id)
    if frame_id not in index:
        index[frame_id] = get_frame(frame_id)
    return index[frame_id]


def list_frames(chat_id):
    """Present first, then every declared frame ordered by ordinal."""
    index = frame_index(chat_id)
    present = index.pop(None)
    # Stable sort over the scan's own (rowid) order, which is what
    # `ORDER BY ordinal` gave ties before this read one row at a time.
    return [present] + sorted(index.values(), key=lambda f: f["ordinal"])


def create_frame(chat_id, *, label, ordinal, kind="other", travelers=None, nonexistent_cast=None,
                 parent_frame_id=None, split_turn_idx=None):
    if kind not in ("past", "future", "other", "spatial"):
        raise ValueError(
            "kind must be 'past', 'future', 'other', or 'spatial' -- "
            "'present' is reserved for the implicit frame_id=None era"
        )
    if kind == "spatial" and split_turn_idx is None:
        raise ValueError("a spatial frame requires split_turn_idx (the play-order position of the split)")
    return qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,travelers,nonexistent_cast,created,"
        "parent_frame_id,split_turn_idx) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            chat_id, str(label), int(ordinal), kind,
            json.dumps([int(c) for c in (travelers or [])]),
            json.dumps([int(c) for c in (nonexistent_cast or [])]),
            time.time(), parent_frame_id, split_turn_idx,
        ),
    )


def frame_ordinal(frame_id, index=None):
    if frame_id is None:
        return PRESENT_ORDINAL
    frame = frame_lookup(frame_id, index)
    return frame["ordinal"] if frame else PRESENT_ORDINAL


def is_memory_visible(char_id, memory_frame_id, viewer_frame_id, memory_turn_idx=None,
                      index=None):
    """A memory formed in memory_frame_id is visible to char_id currently
    being portrayed in viewer_frame_id iff it's diegetically at-or-before
    the viewer's frame, OR char_id is a registered traveler of EITHER frame
    -- travelers keep full continuity of their OWN memory ledger regardless
    of which era they're standing in, and of which era they formed it in;
    natives get the ordinal cutoff.

    Spatial frames are checked FIRST and can short-circuit the ordinal
    rule entirely -- see frames.py's module docstring for why the
    ordinal rule alone is wrong for them (same ordinal as parent means
    it would otherwise make the two sides instantly, bidirectionally
    visible, the opposite of an actual spatial separation). Both checks
    below only apply while the relevant spatial frame is unmerged; once
    merged_turn_idx is set the ordinary ordinal rule resumes and (since
    ordinals are equal) grants full bidirectional visibility, matching
    a genuine reunion.

    `index` is an optional lookup memo (`frame_lookup`) -- an empty dict a
    caller shares across a whole bank's worth of rows, so a repeated era costs
    one SELECT rather than one per memory. Every lookup below goes through it
    when it is given and falls back to a per-call SELECT when it is not, so
    the answer never depends on whether a caller supplied one.
    """
    if memory_frame_id != viewer_frame_id:
        viewer_frame = frame_lookup(viewer_frame_id, index)
        if (viewer_frame and viewer_frame.get("kind") == "spatial"
                and viewer_frame.get("merged_turn_idx") is None
                and memory_frame_id == viewer_frame.get("parent_frame_id")):
            # Looking from inside an unmerged spatial split back at the
            # parent it split FROM -- only the shared history up to the
            # split is visible; the parent's post-split memories are the
            # other side's business, not yet this side's.
            #
            # Fail CLOSED on a missing turn_idx. A parent-side memory formed
            # without a turn_id (e.g. one added outside the numbered-turn
            # pipeline) has NULL turn_idx; treating that as pre-split
            # (returning True) leaked the parent's post-split memories across
            # an active, unmerged split -- exactly the incomparability this
            # rule exists to enforce. With no positive proof the memory
            # predates the split, it is not this side's to see.
            if memory_turn_idx is None:
                return False
            return memory_turn_idx <= (viewer_frame.get("split_turn_idx") or 0)

        memory_frame = frame_lookup(memory_frame_id, index)
        if (memory_frame and memory_frame.get("kind") == "spatial"
                and memory_frame.get("merged_turn_idx") is None):
            # The memory itself was formed inside an unmerged spatial
            # split that ISN'T the viewer's own current frame (covers
            # both "viewer is the parent" and "viewer is a DIFFERENT
            # sibling split from the same parent") -- invisible to a
            # native, unless char_id genuinely traveled there.
            if int(char_id) in (memory_frame.get("travelers") or []):
                return True
            return False

    if frame_ordinal(memory_frame_id, index) <= frame_ordinal(viewer_frame_id, index):
        return True
    # A later era than the one they are standing in. Two ways that is still
    # their own memory to reach, and BOTH are needed:
    #
    #   * they are a registered traveller of the frame they are standing in --
    #     a time traveller in Edo still remembers their own later life;
    #   * they are a registered traveller of the frame the memory was FORMED
    #     in -- they were there, so they remember it, wherever they are now.
    #
    # The second used to be missing, and its absence was invisible because the
    # first LOOKS like it covers the case. It does not: the present is the
    # implicit frame, `frame_id is None`, with no row of its own, and
    # `get_frame(None)` synthesises it with an empty travellers list. So the
    # first clause can never fire in the present, and a character who visited
    # the year 5000 and walked home could not recall one moment of it --
    # everything while standing there, nothing once back where they live.
    #
    # Widening this is safe for a reason worth stating: every caller arrives
    # through `visible_memory_rows`, which has already filtered `char_id=?`.
    # The only question this function ever answers is whether a mind may reach
    # its OWN experience, and "registered as having travelled there" is not a
    # widening of anybody's information -- it is what having been there means.
    # A native of the present is not a traveller of the future frame and still
    # sees nothing, which is the firewall the whole feature exists for.
    viewer_frame = frame_lookup(viewer_frame_id, index)
    if viewer_frame and int(char_id) in (viewer_frame.get("travelers") or []):
        return True
    memory_frame = frame_lookup(memory_frame_id, index)
    return bool(memory_frame
                and int(char_id) in (memory_frame.get("travelers") or []))


def is_recognized_in_frame(char_id, frame_id):
    """False if char_id is declared not-yet-existing (to natives) in this
    frame, independent of world.known's accumulated play-order truth.
    This gates RECOGNITION only -- a masked character can still be
    perceived and interacted with as a stranger, just not known-as-
    themselves (e.g. a daughter visiting a mother who hasn't had her
    yet: present, perceivable, not recognized)."""
    frame = get_frame(frame_id)
    if not frame:
        return True
    return int(char_id) not in (frame.get("nonexistent_cast") or [])
