"""Regression tests for goal viability (P5).

Live bug (Elevator Adventure, turns 20-22): Dr. Moon kept serving intention i1
'reach the auxiliary shelter' even after she observed every corridor was
condemned and boarded (i1 now impossible). Nothing could mark an active goal
non-viable, so it steered her wants forever. Fix: a guarded `nonviable` intent
op sets a goal aside; engagement revives it.

Second live bug (The Doctor - Hinami, chat 38, turns 64-71): the Doctor asked
Hinami to describe the same "made from nothing" quality of a replicated object
for eight consecutive turns, reaching for a new metaphor each time (a book
missing its first chapter, a song without its opening bars, an echo with no
source) while asking for exactly the same thing. Intent i2 was stored `status:
active, progress: 1.0, last_progress_turn: 71` -- saturated since turn 69 and
still steering. Every beat emitted {op:'progress', id:'i2'}, which refreshed
last_progress_turn unconditionally, so _INTENT_DORMANT_AFTER could never fire:
the only guard against a goal steering forever was reset by the very act of
grinding it. Fix: progress that cannot move the value is barren -- it leaves
the clock alone and, after _INTENT_STALL_AFTER of them, the goal stops
steering. Closing a goal still requires evidence; only pursuit past the point
of yield is stopped.
"""

from __future__ import annotations

from affect import apply_intent_ops, steering_intent_ids


def _intents():
    return [{"id": "i1", "intent": "reach the auxiliary shelter", "status": "active",
             "formed_turn": 0, "last_progress_turn": 0, "progress": 0.3}]


def _always_ok(op):
    return True


def test_nonviable_blocks_goal_with_why():
    ops = [{"op": "nonviable", "id": "i1",
            "why": "every corridor off the lobby is condemned and boarded"}]
    out, warns = apply_intent_ops(_intents(), ops, turn_idx=21, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["status"] == "blocked"
    assert "condemned" in i1["blocked_why"]


def test_nonviable_rejected_without_evidence():
    ops = [{"op": "nonviable", "id": "i1", "why": ""}]
    # evidence_ok mirrors commit's: no evidence and no why -> reject
    out, warns = apply_intent_ops(_intents(), ops, turn_idx=21,
                                  evidence_ok=lambda op: bool(op.get("why")))
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["status"] == "active"  # not blocked
    assert any("nonviable rejected" in w for w in warns)


def test_progress_revives_blocked_goal():
    blocked = [{"id": "i1", "intent": "reach the shelter", "status": "blocked",
                "blocked_why": "corridors boarded", "formed_turn": 0,
                "last_progress_turn": 21, "progress": 0.3}]
    ops = [{"op": "progress", "id": "i1"}]
    out, _ = apply_intent_ops(blocked, ops, turn_idx=25, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["status"] == "active"
    assert "blocked_why" not in i1


def _spent():
    """The Doctor's i2 as stored at turn 69: saturated, still active."""
    return [{"id": "i2", "intent": "investigate what Hinami senses that the "
             "ship's systems cannot record", "status": "active",
             "formed_turn": 54, "last_progress_turn": 69, "progress": 1.0}]


def test_progress_at_the_ceiling_does_not_refresh_the_dormancy_clock():
    # The core of the bug: grinding a saturated goal used to look exactly like
    # advancing it, which reset the only timer that could ever retire it.
    out, warns = apply_intent_ops(_spent(), [{"op": "progress", "id": "i2"}],
                                  turn_idx=70, evidence_ok=_always_ok)
    i2 = next(i for i in out if i["id"] == "i2")
    assert i2["last_progress_turn"] == 69      # NOT 70
    assert i2["barren_attempts"] == 1
    assert i2["progress"] == 1.0
    assert any("nothing gained" in w for w in warns)


def test_repeated_barren_progress_stalls_the_goal():
    intents = _spent()
    for turn in (70, 71):
        intents, warns = apply_intent_ops(intents, [{"op": "progress", "id": "i2"}],
                                          turn_idx=turn, evidence_ok=_always_ok)
    i2 = next(i for i in intents if i["id"] == "i2")
    assert i2["status"] == "dormant"           # stops steering at turn 71
    assert i2["stalled_turn"] == 71
    assert i2["barren_attempts"] == 2
    assert any("stalled" in w for w in warns)


def test_a_stalled_goal_is_not_revived_by_more_of_the_same():
    stalled = [{"id": "i2", "intent": "x", "status": "dormant", "formed_turn": 54,
                "last_progress_turn": 69, "progress": 1.0, "barren_attempts": 2,
                "stalled_turn": 71}]
    out, _ = apply_intent_ops(stalled, [{"op": "progress", "id": "i2"}],
                              turn_idx=72, evidence_ok=_always_ok)
    i2 = next(i for i in out if i["id"] == "i2")
    assert i2["status"] == "dormant"           # another metaphor changes nothing
    assert i2["barren_attempts"] == 3


def test_rephrasing_a_spent_goal_does_not_revive_it():
    # `add` of near-duplicate text becomes progress on the match; that must not
    # be a way to launder a spent goal back into active.
    stalled = [{"id": "i2", "intent": "investigate what Hinami senses that the "
                "ship's systems cannot record", "status": "dormant",
                "formed_turn": 54, "last_progress_turn": 69, "progress": 1.0,
                "barren_attempts": 2}]
    ops = [{"op": "add", "intent": "investigate what Hinami senses that the "
            "ship's systems cannot record"}]
    out, _ = apply_intent_ops(stalled, ops, turn_idx=72, evidence_ok=_always_ok)
    assert len(out) == 1                       # merged, not a second goal
    assert out[0]["status"] == "dormant"


def test_genuine_progress_clears_the_barren_count_and_revives():
    part = [{"id": "i2", "intent": "x", "status": "dormant", "formed_turn": 54,
             "last_progress_turn": 69, "progress": 0.4, "barren_attempts": 1,
             "stalled_turn": 70}]
    out, _ = apply_intent_ops(part, [{"op": "progress", "id": "i2"}],
                              turn_idx=72, evidence_ok=_always_ok)
    i2 = next(i for i in out if i["id"] == "i2")
    assert i2["status"] == "active"
    assert round(i2["progress"], 6) == 0.6
    assert i2["last_progress_turn"] == 72
    assert "barren_attempts" not in i2
    assert "stalled_turn" not in i2


def test_a_goal_short_of_the_ceiling_still_progresses_normally():
    out, warns = apply_intent_ops(_intents(), [{"op": "progress", "id": "i1"}],
                                  turn_idx=21, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["progress"] == 0.5
    assert i1["last_progress_turn"] == 21
    assert not warns


def test_block_re_opens_room_and_resets_the_barren_count():
    # The world pushing back is engagement: it moves the goal down, so there is
    # somewhere to go again and the stall count starts over.
    spent = _spent()
    spent[0]["barren_attempts"] = 1
    out, _ = apply_intent_ops(spent, [{"op": "block", "id": "i2"}],
                              turn_idx=70, evidence_ok=_always_ok)
    i2 = next(i for i in out if i["id"] == "i2")
    assert i2["progress"] == 0.8
    assert i2["last_progress_turn"] == 70
    assert "barren_attempts" not in i2


def test_reviving_a_blocked_goal_clears_its_block_bookkeeping():
    blocked = [{"id": "i1", "intent": "reach the shelter", "status": "blocked",
                "blocked_why": "corridors boarded", "blocked_turn": 21,
                "formed_turn": 0, "last_progress_turn": 21, "progress": 0.3}]
    out, _ = apply_intent_ops(blocked, [{"op": "progress", "id": "i1"}],
                              turn_idx=25, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["status"] == "active"
    # blocked_turn used to outlive the block, leaving an active goal stamped
    # with the turn it was set aside on (live: the Doctor's i2 carried
    # blocked_turn 57 while active at turn 71).
    assert "blocked_turn" not in i1
    assert "blocked_why" not in i1


def test_a_set_aside_goal_stops_weighting_mood_at_goal_priority():
    # commit._priority scored every id in the intentions list at 0.8, so a goal
    # the world had closed kept moving affect as hard as a live one forever.
    aside = [
        {"id": "i1", "intent": "a", "status": "active", "last_progress_turn": 40},
        {"id": "i2", "intent": "b", "status": "blocked", "last_progress_turn": 21},
        {"id": "i3", "intent": "c", "status": "dormant", "last_progress_turn": 12},
        {"id": "i4", "intent": "d", "status": "abandoned", "last_progress_turn": 30},
        {"id": "i5", "intent": "e", "status": "satisfied", "last_progress_turn": 33},
    ]
    assert steering_intent_ids(aside, turn_idx=41) == {"i1"}


def test_the_beat_a_goal_closes_still_lands_at_full_weight():
    # Satisfying, abandoning or losing a goal is the beat it matters MOST --
    # all three stamp last_progress_turn, so the payoff is not muted at the
    # moment it arrives, only on every beat after.
    closing = [
        {"id": "i1", "intent": "a", "status": "satisfied", "last_progress_turn": 41},
        {"id": "i2", "intent": "b", "status": "abandoned", "last_progress_turn": 41},
        {"id": "i3", "intent": "c", "status": "blocked", "last_progress_turn": 41},
    ]
    assert steering_intent_ids(closing, turn_idx=41) == {"i1", "i2", "i3"}
    # ...and on the next beat all three have stopped steering.
    assert steering_intent_ids(closing, turn_idx=42) == set()


def test_a_stalled_goal_stops_weighting_mood_immediately():
    # The stall path deliberately does NOT stamp last_progress_turn: arriving
    # at "nothing gained, again" is not a dramatic beat and is not scored
    # like one.
    intents = _spent()
    for turn in (70, 71):
        intents, _ = apply_intent_ops(intents, [{"op": "progress", "id": "i2"}],
                                      turn_idx=turn, evidence_ok=_always_ok)
    assert steering_intent_ids(intents, turn_idx=71) == set()


def test_steering_ids_survive_junk_intentions():
    junk = [None, "nope", {}, {"id": "i1", "status": "active"},
            {"id": "i2", "status": "blocked", "last_progress_turn": "?"}]
    assert steering_intent_ids(junk, turn_idx=5) == {"i1"}


def test_blocked_goal_does_not_go_dormant_or_steer():
    blocked = [{"id": "i1", "intent": "x", "status": "blocked",
                "formed_turn": 0, "last_progress_turn": 0, "progress": 0.0}]
    out, _ = apply_intent_ops(blocked, [], turn_idx=100, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    # stays blocked (not active), so it no longer steers; the dormant sweep
    # only touches active goals
    assert i1["status"] == "blocked"
