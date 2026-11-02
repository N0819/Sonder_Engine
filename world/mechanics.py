"""Deterministic mechanics sweep (movement/space Phase 2, item 3).

One ordered orchestration of every deterministic mechanical follow-through
that used to be scattered across commit_transit_sweep's inline body and
prepare_scene_commit's tail:

    (a) fire due scheduled_events for THIS frame (transit_arrival moves
        the entity and docks it; news_arrival stages latency-gated
        awareness -- see the news note below);
    (b) time every journey toward a destination: a written eta, else the
        engine's price of the way (`spatial.journey_seconds`) -- something
        under way arrives when its way is done;
    (c1) fire due world_conditions ticks -- a condition that declares a
        cadence ACTS while it lasts (see the pass (c1) block below), and
        (c2) expire due world_conditions;
    (d) recompute derived dock edges (when an arrival fired);
    (e) vehicle-zone inference.

`mechanics_sweep` is pure with respect to the DATABASE: it never writes --
every durable effect is returned as an event_op for the commit domain
(commit.commit_transit_sweep) to apply inside the turn's transaction. It
mutates only the passed-in scene dict, exactly as the pieces it gathers
always did. Pass implementations shared with other consumers stay where
those consumers need them (apply_transit_dock_edges in spatial.py, because
merge_scene_with_diff must derive the same doorways for perception's
mid-turn merges; infer_vehicle_zones in spatial_frames.py, whose tests
exercise it directly) -- this module owns
the ordering and the sweep contract, not duplicate copies.

Behavior preservation notes (the refactor this module came from is
contractually behavior-identical -- tests/test_mechanics_sweep.py pins it):
- pass (e) ALSO runs during scene preparation (prepare_scene_commit), so
  memory preparation -- which reads the prepared scene before the write
  transaction opens -- sees vehicle zones as the commit will. Both passes
  are idempotent, so the sweep's (e) run is a
  no-op unless pass (a) moved a vehicle this very sweep -- the one case
  the old arrangement structurally missed.
- pass (d) runs only when an arrival fired, mirroring the old sweep: on a
  no-fire turn the dock edges were already derived by
  merge_scene_with_diff during preparation.

News arrivals (item 4): a `news_arrival` event is minted by the
destruction commit path (one per audience scope, due_at = the minting
frame's clock + declared latency, deterministic stable id). Firing one
stages an engine notice carrying told/heard provenance for the next
director turn to acknowledge -- destruction is objective the moment it
commits; AWARENESS of it propagates only through this latency gate and
then through the ordinary director/perception filters, never by code
injecting knowledge directly into minds. Since Phase 3b, a news entry
that declares no latency gets one DERIVED from the audience's hop
distance to the destroyed root in the lorebook containment/presence
graph (news_latency_seconds below): near regions hear sooner, distant
ones later, and an audience matching no book waits a flat day.

Reproducibility contract (unchanged from the pieces this gathers): due
times compare against the SIM clock only (never wall-clock), events are
frame-gated via the frame_id in their payload, event ids are stable hashes
of (kind, chat, frame, subject, turn), and checkpoint restore snapshots
scheduled_events/world_conditions whole -- so a rerolled turn reproduces
the exact pending/fired state.
"""

from __future__ import annotations

import hashlib
import json
import math

from core import jobs
from world.spatial import (apply_transit_dock_edges, journey_pace,
                           journey_seconds, room_of_record, scene_names_body,
                           scene_room_id, stand_in_no_room, vessel_speed)
from world.spatial_frames import infer_vehicle_zones


def stable_event_key(*parts):
    """Deterministic id for events/memories: same inputs, same id, so a
    rerun cannot double-schedule or double-store."""
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"event:{digest}"


# ---- The state_diff.time vocabulary, and its ONE reader ----
#
# `state_diff.time` is declared `Optional[dict]` (llm/schemas.py), so every
# key a model can spell validates and nothing downstream is obliged to look
# at any of them. That is the right declaration -- a typed submodel with
# extra="forbid" would THROW AWAY declared fiction time, which is the defect
# itself wearing a validator -- but it means the shape has to be owned
# somewhere, by one reader, or each caller invents its own subset.
#
# Three callers had invented three: the scene commit knew `end_seconds`
# alone, the sleep floor knew end/start/duration in that order, and the
# vitals tick knew `duration_seconds` alone. So a beat could end a sleep and
# not move the clock, or move the clock and not age a body.
#
# The spellings below are the ones the ENGINE ITSELF TEACHES, which is why
# tolerating them is not leniency. The resolve payload prints the clock to
# the model every beat as `simulation_clock: {elapsed_seconds, display,
# time_scale}` (agents/director_fanout.py), so a model that answers in the
# key it was just shown is echoing us. Measured over the live corpus
# 2026-08-25 (2,450 stored time diffs; these totals grow with play, the
# five-row set below does not): `display` 38x, `elapsed_seconds` 22x,
# `time_scale` 10x. Of the 22 `elapsed_seconds` diffs, 17 sit beside a full
# canonical shape with the value always inside [start_seconds, end_seconds]
# -- an absolute POSITION, not a duration, which is what fixes its reading
# -- and 5 carry no other numeric key at all and were dropped whole: chat 74
# turns 55 and 60, chat 88 turns 61, 64 and 66. In chat 88 turns 61 and 64
# claimed 1107 and 1266 against a clock standing at 1106.0, and turn 66
# claimed 7200 against 1136.0; not one of the three moved the clock or
# warned, and the only advance in that stretch came from turn 65's
# canonically spelled diff.
#
# The house pattern for a natural synonym is weather's `_SYNONYMS`:
# normalize what the fiction plainly meant, and report only what cannot be
# read at all. The prompts keep teaching ONE canonical spelling -- the
# tolerance lives here, not in the prompt, because a prompt naming two
# spellings encourages the second.

# Keys that ASSERT A TIME. A diff carrying one of these and getting no
# advance out of the reader has been refused, and a refusal is reportable.
TIME_CLAIM_KEYS = frozenset({
    "start_seconds",      # where the beat began on the story clock
    "duration_seconds",   # how long the beat took
    "end_seconds",        # where the beat ended: the canonical position
    "elapsed_seconds",    # the same position under the clock's own name
})

# Keys this vocabulary KNOWS but does not act on: the beat's own labelling
# of its time, plus the clock's metadata echoed back. Their presence is
# never a claim, so a diff carrying only these asserts no time and gets no
# warning (5 corpus rows carry `display` alone).
#
# THE PASSAGE PHRASE IS A RECORD, NOT A CHANNEL. `display_advance`/`display`
# reach no live reader anywhere in the engine: they used to be written onto
# `scene.time` and `simulation_clock.display`, which is how a per-beat phrase
# came to overwrite -- and, spelled empty, ERASE -- the standing time of day
# those two fields were documented to carry. That write is gone (see
# `normalize_time_of_day`), and the phrase survives only as the beat's own
# words on its persisted resolve variant. They stay in this set because a key
# the vocabulary does not KNOW is reported as an unreadable claim, and a beat
# labelling its own passage has made no claim to refuse.
TIME_METADATA_KEYS = frozenset({
    "mode",               # 'action' | 'time_skip'
    "explicit",           # did the player ask for the skip
    "display_advance",    # the beat's own phrase for its passage; recorded
    "display",            # the same phrase under the clock's own name
    "time_scale",         # the clock's own scale, echoed back
    # A LATER PART OF THE DAY a beat passes over to ("that evening", "by
    # morning"): written by the encoder's `time` tool, and SOLVED into
    # `duration_seconds` where the story clock is at hand
    # (`director_prose.solve_skip`), so what reaches this reader is a span.
    # Recorded, never acted on here: this reader holds no time of day, and
    # one that cannot be solved is reported where the solve was tried.
    "until_phase",
    # A COUNT OF THE STORY'S DAYS a beat passes over ("two days later", "a
    # week on"), alone or with the part of the day it lands in
    # ("two days later ... all morning"): written by the same tool and
    # solved the same way, into `duration_seconds`
    # (`director_prose.solve_skip`, `day_cycle.seconds_until(days=)`).
    # Recorded, never acted on here.
    "days",
    # The stretch the beat PASSED OVER, apart from its steps -- written
    # beside the total it is part of (`beat_time_block`), so a reader of the
    # stored diff can tell a skipped evening from a long scene. Recorded,
    # never acted on: `duration_seconds` carries it.
    "skipped_seconds",
})

# Everything the vocabulary contains. A key outside it has no meaning to any
# reader in the engine; `tools/project_check.check_time_channel_vocabulary`
# holds the prompts and the shipped output examples to exactly this set.
TIME_DIFF_KEYS = TIME_CLAIM_KEYS | TIME_METADATA_KEYS


def _finite(value):
    """`float(value)`, refused unless the number is FINITE.

    NaN and the infinities parse -- `float("NaN")`, `float("Infinity")`, a
    JSON `NaN` -- and measure nothing. Read as a claim, one moved the story
    clock to NaN, where every `due_at > elapsed` is False: every pending
    consequence, news arrival and transit arrival fired on the next sweep, and
    the clock stayed NaN for good (`nan + d`); an infinite duration aged a
    body by forever (world_offscreen_time F14, audit 2026-11-01). Raises
    ValueError, so each reader's own `except (TypeError, ValueError)` treats
    it exactly as it treats a word: a claim this vocabulary cannot act on.
    `beat_time_from_spans` already dropped a non-finite span; this is the
    same rule for the block readers that must agree with it.
    """
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("not a finite number of seconds: %r" % (value,))
    return number


def clock_elapsed(clock):
    """Where the STORED simulation clock stands, from its own dict.

    The other half of the same ownership: `read_time_diff` knows the shape a
    beat's claim arrives in, and this knows the shape the clock is kept in,
    so neither the scene commit nor the memory commit has to spell
    `float((clock or {}).get("elapsed_seconds", 0.0) or 0.0)` for itself and
    drift. Missing, absent or unparseable reads 0.0 -- the story has not
    started. (`agents.director_floors._sleep_elapsed` deliberately does NOT
    use this: it returns None for an unreadable clock, because "the clock
    cannot say how long you have been under" is a different answer from
    "you have been under since zero".)
    """
    try:
        return float((clock or {}).get("elapsed_seconds", 0.0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def read_time_diff(prev_elapsed, time_diff):
    """What a `state_diff.time` block says about the story clock.

    THE ENGINE OWNS THE CLOCK'S POSITION; A BEAT CONTRIBUTES A SPAN. Nothing
    a model emits measures where the story clock stands -- the payload
    PRINTS the clock to it, but a model is free to run its arithmetic from
    another zero entirely (a time of day, the story's first line, nothing),
    and an absolute produced there is a guess wearing the authority of a
    measurement. Measured live, chat 95 second pass beat 2: a conversation
    declared `{start_seconds: 20520, duration_seconds: 45, end_seconds:
    20565}` against a clock standing at 20.0; the forward absolute won under
    the old contract and four people talking moved the story clock five and
    a half hours, while the 45-second duration -- the one correct number in
    the block -- was discarded.

    So an absolute is read only IN THE FRAME THE BLOCK ITSELF DECLARES.
    `start_seconds` is the block's own anchor: where the model says this
    beat began. A beat begins where the clock stands -- that is a
    definition, not an assumption -- so a block whose anchor IS the clock
    (or that declares none) has its claimed end adopted verbatim, which is
    every canonical corpus row behaving exactly as it always did. A block
    anchored ANYWHERE ELSE is internally coherent and externally
    meaningless: the only part of it the fiction actually asserted is the
    SPAN, so the clock advances from where the ENGINE stood, by the declared
    duration (or by end-minus-start when no duration parses), and the caller
    is told.

    Returns ``(elapsed_seconds, displaced, refused)``:

    * ``elapsed_seconds`` -- where the clock stands at the END of this beat.
    * ``displaced`` -- None, or ``(claimed, was)`` when the beat asserted a
      position the engine did not adopt. Two ways that happens, one rule
      under both: a position EARLIER than the clock (TIME DOES NOT RUN
      BACKWARDS -- a model emitting `start_seconds: 0` every beat, an easy
      and entirely natural reading of a field named "start", would
      otherwise reset the world to the length of its own beat, over and
      over), and a position anchored AWAY from the clock (the bridge beat
      above). Both advance by the span the fiction asserted instead.
    * ``refused`` -- sorted keys that made a time claim this reader could
      NOT act on, and empty whenever it did act. It is empty for a diff
      that asserts no time at all (`{"display": "later"}` says nothing about
      the clock and is not a refusal), and it is empty when a position
      parsed and merely happened to equal the clock. What it names is the
      real class: `{"start_seconds": 1200}` with no end and no duration,
      `{"end_seconds": "soon"}`, `{"seconds": 300}` -- a beat that meant to
      move time and got silence. Keyed on whether the reader ACTED, not on
      whether the number changed, because those differ in both directions.

    A position may arrive under either name the engine uses for it, and the
    canonical `end_seconds` outranks the synonym when both are present (17
    corpus rows carry both; the synonym is the mid-beat position there). A
    diff carrying ONLY a duration is an advance from where the clock stood,
    not silence -- it asserted a span, and a span is a claim. A time skip is
    a duration too -- `duration_seconds: 28800` for a night's sleep lands
    whole from any frame, because a span survives the translation that a
    position does not.
    """
    try:
        was = float(prev_elapsed or 0.0)
    except (TypeError, ValueError):
        was = 0.0
    td = time_diff if isinstance(time_diff, dict) else {}

    duration = 0.0
    duration_claimed = False
    if "duration_seconds" in td:
        try:
            duration = max(0.0, _finite(td.get("duration_seconds") or 0.0))
            duration_claimed = True
        except (TypeError, ValueError):
            duration = 0.0

    claim = None
    for key in ("end_seconds", "elapsed_seconds"):
        if td.get(key) is None:
            continue
        try:
            claim = _finite(td[key])
            break
        except (TypeError, ValueError):
            claim = None

    acted = claim is not None or duration_claimed
    refused = [] if acted else sorted(
        k for k in td if k in TIME_CLAIM_KEYS or k not in TIME_DIFF_KEYS)

    if claim is None:
        return (was + duration if duration_claimed else was), None, refused

    anchor = None
    if td.get("start_seconds") is not None:
        try:
            anchor = _finite(td["start_seconds"])
        except (TypeError, ValueError):
            anchor = None

    if anchor is not None and anchor != was:
        # The block's absolutes live in a frame of its own declaring. The
        # span survives the translation onto the engine clock; the position
        # does not. Duration first, on the same ground as the backwards
        # branch below and `time_diff_duration`'s precedence: it is the
        # beat's direct statement of its own length, and end-minus-start is
        # the model's arithmetic about it. (Chat 95 second pass beat 2:
        # anchor 20520 against a clock at 20.0 -- the model was working in
        # a time of day the engine never held.)
        span = duration if duration_claimed else max(0.0, claim - anchor)
        return was + span, (claim, was), refused
    if claim < was:
        return was + duration, (claim, was), refused
    return claim, None, refused


# What a resolved beat that asserts NO time still costs the story clock.
#
# A BEAT HAPPENED. The world is not entitled to stand still because the block
# that was meant to say how long it took arrived empty: a clock that stops
# whenever a model forgets a field is a clock the whole engine's windowing
# reads through -- condition ticks, scheduled events, weather drift, the
# off-screen epoch, affect decay, strain and belief provenance all compare
# against it, and every one of them went quiet together.
#
# Measured read-only against the author's corpus 2026-08-25 at 49ea899: of
# 2,614 active non-stale `director_resolve` outputs, 130 (5.0%) assert no time
# this reader can act on, and 109 of the 130 sit in six chats of one story line
# (88:24, 89:24, 90:20, 86:15, 87:15, 85:11). Chat 89 turns 58-62 are five of
# them consecutively: the clock stood at 1098.0 for nine turns while its own
# Director wrote notes about a transit in progress.
#
# TEN SECONDS is the p25 of the 2,479 beats that DO declare a positive
# duration (p10 5.0, p25 10.0, median 25.0, p75 30.0, p90 45.0, mean 42.1).
# The quartile rather than the median, on `time_diff_duration`'s own stated
# doctrine one screen below: "Under-ageing a body is recoverable; ageing it by
# the whole elapsed history of the story is not." A floor is a guess about a
# beat that told us nothing, so it takes the cautious end of the distribution
# it is guessing from.
UNCLAIMED_BEAT_SECONDS = 10.0


def beat_time_from_spans(spans):
    """The beat's own span, summed from what the prose author priced each
    causal step at. A `state_diff.time` block, or None when no row named one.

    THE SUM IS CODE'S BECAUSE THE PARTS ARE THE AUTHOR'S. `state_diff.time`
    was the spatial specialist's channel, and a specialist is handed
    `_specialist_span_slice` -- the rows selected for it, not the beat. Its
    sheet asked it for the whole ("a beat that holds several things in
    sequence spans all of them: the time is the sum of its parts") while the
    fan-out handed it some of the parts, so it was being asked for a total it
    could not see the terms of. It answered by declining, which is the right
    answer to that question and left every beat on
    `UNCLAIMED_BEAT_SECONDS`: measured 2026-09-20, the channel was in the
    hand's scope on 38 of 60 playerless beats and 50 of 118 live beats since
    2026-09-15 and carried a claim on 0 of either, and across 3,000 resolve
    variants the author routed the `time` category 0 times, so the hand was
    never given a time work item in the first place.

    The prose author is the one agent that sees the beat whole -- it cuts the
    spans -- so it prices each span it cut, and the beat's total is
    arithmetic. A row that names no number contributes nothing rather than a
    guess, on `time_diff_duration`'s doctrine one screen below: under-ageing
    a body is recoverable, over-ageing it is not. A beat where NO row named
    one returns None and is charged the floor exactly as before.

    Negative and unreadable spans are dropped, not clamped to the beat: a
    number this reader cannot act on is silence, the same answer
    `time_diff_claims` gives for one.
    """
    total = 0.0
    priced = False
    for span in spans or ():
        if not isinstance(span, dict) or "seconds" not in span:
            continue
        value = span.get("seconds")
        if value is None or isinstance(value, bool):
            continue
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        if seconds != seconds or seconds in (float("inf"), float("-inf")) \
                or seconds < 0:
            continue
        total += seconds
        priced = True
    if not priced:
        return None
    # DURATION ALONE, deliberately. A span survives a translation a position
    # does not (`read_time_diff`), the engine owns where the clock stands,
    # and this reader holds no clock. `mode` stays unwritten: the narrator
    # reads it to tell a span it should summarise from a scene it should
    # play (agents/narration.py), and separating those by a cutoff on this
    # number would be a threshold nobody chose.
    return {"duration_seconds": total}


#: The keys that PLACE a beat on the story clock, as opposed to measuring a
#: stretch of it. A block carrying one is the retired contract's whole-beat
#: reading (`read_time_diff` reads it as it always has); a block carrying
#: none is a span.
POSITION_KEYS = ("start_seconds", "end_seconds", "elapsed_seconds")


def _positioned(block):
    return isinstance(block, dict) and any(
        block.get(key) is not None for key in POSITION_KEYS)


def skip_seconds(block):
    """The stretch a `time` block PASSES OVER, in story seconds: the
    `duration_seconds` it states or was solved to
    (`director_prose.solve_skip`). 0.0 for no block, a block that places the
    beat on the clock instead, and anything unreadable -- a stretch this
    reader cannot measure is never guessed at."""
    if not isinstance(block, dict) or _positioned(block):
        return 0.0
    try:
        value = float(block.get("duration_seconds") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return value if 0.0 < value < float("inf") else 0.0


def skip_days(block):
    """`(present, count)` for a `time` block's `days`: whether it carries a
    count of the story's days, and that count as a whole number -- None for
    a count that is not one (a fraction, a word, a negative), which states
    nothing this reader can solve. A null `days` is no count at all."""
    if not isinstance(block, dict) or block.get("days") is None:
        return False, None
    raw = block.get("days")
    if isinstance(raw, bool):
        return True, None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return True, None
    if not (0.0 <= value < float("inf")) or value != int(value):
        return True, None
    return True, int(value)


def _states_a_length(block):
    """Did the block STATE a length -- the encoder's readable
    `duration_seconds`, not one the engine solved from a part of the day or
    a count of days? A stated zero is a claim (no time passed), which a
    solved zero is not: "that evening" said in the evening is the engine's
    arithmetic arriving at now. A length that is not a number states
    nothing."""
    if (not isinstance(block, dict) or "duration_seconds" not in block
            or str(block.get("until_phase") or "").strip()
            or skip_days(block)[0] or _positioned(block)):
        return False
    try:
        value = float(block.get("duration_seconds"))
    except (TypeError, ValueError):
        return False
    return 0.0 <= value < float("inf")


def beat_time_block(steps, onset=None, resolve=None):
    """`state_diff.time` for a resolved beat: the stretches its accounts
    PASSED OVER, then its steps. None when the beat says nothing about time,
    which `beat_end_elapsed` charges the floor for.

    TWO HALVES, AND NO SUM OF ONE CAN CARRY THE OTHER. `steps` is
    `beat_time_from_spans`' answer: how long the beat's own events took, each
    priced by the agent that cut it. What it cannot hold is time the account
    passes over BETWEEN them -- "that evening", "hours later" -- which is in
    no step, so the encoder writes it as the `time` channel (`encoder.time`)
    at whichever stage the account passes over it: `onset` is the
    interpret stage's (the players' input passed the time; the ladder has
    already ruled on it, `agents.common.refuse_ungranted_time_skip`) and
    `resolve` the resolve's (the world's account did). Measured, the probe
    story (2026-10-20, chat 1 turn 5): "That evening, with the lamp lit ..."
    against a clock at 15:50 summed to 44 seconds of steps, and the owner's
    chats 101, 102, 112 and 113 at idx 70 ("a few hours later") moved the
    clock on 0 of 4.

    THE SAME STRETCH TOLD TWICE COUNTS ONCE. The resolve is handed the
    input's account as `already_happened`, and a part of the day it names
    again was solved from where the input's stretch landed, so it arrives
    as 0 by construction. A LENGTH it restates equal to the one the input
    stated is that stretch again, and counts once; a different length is a
    different stretch, and both happened.

    A block carrying a POSITION is the retired contract's whole-beat reading
    and is kept as written; the steps are added only where it made no claim
    `read_time_diff` can act on, exactly as before.
    """
    if _positioned(resolve):
        if steps and not time_diff_claims(resolve):
            return dict(resolve, **steps)
        return resolve
    onset_s = skip_seconds(onset)
    resolve_s = skip_seconds(resolve)
    if (onset_s and resolve_s == onset_s
            and _states_a_length(onset) and _states_a_length(resolve)):
        resolve_s = 0.0
    skipped = onset_s + resolve_s
    block = {key: value for key, value in (resolve or {}).items()
             if key not in ("duration_seconds", "skipped_seconds")} \
        if isinstance(resolve, dict) else {}
    # Where the input's stretch landed is ONE record -- a count of days and
    # the part of the day it landed in -- so it is taken whole or not at
    # all: a resolve's own part of the day beside the input's days would
    # read as a landing nobody wrote.
    if isinstance(onset, dict) and "until_phase" not in block \
            and "days" not in block:
        for key in ("until_phase", "days"):
            if onset.get(key) not in (None, ""):
                block[key] = onset[key]
    for key in ("display_advance", "display"):
        if key not in block and isinstance(onset, dict) and onset.get(key):
            block[key] = onset[key]
    stepped = (steps or {}).get("duration_seconds") \
        if isinstance(steps, dict) else None
    if skipped > 0 or stepped is not None \
            or _states_a_length(onset) or _states_a_length(resolve):
        block["duration_seconds"] = skipped + float(stepped or 0.0)
        if skipped > 0:
            block["skipped_seconds"] = skipped
            block["mode"] = "time_skip"
    return block or None


def time_diff_claims(time_diff) -> bool:
    """Did this time block make a claim `read_time_diff` could ACT on?

    Exactly that reader's own `acted` test, extracted so the two can never
    drift: a parseable `duration_seconds`, or a parseable position under
    either name the engine uses for one. Everything else -- an absent block,
    `{}`, `{"display": "later"}`, `{"start_seconds": 1200}` alone,
    `{"end_seconds": "soon"}` -- claims nothing this engine can move a clock
    with, and is what `beat_end_elapsed` charges the floor for.

    Silence and a REFUSED claim are deliberately the same answer here. They
    differ in whether anyone should be warned, which is the caller's business
    and which `read_time_diff.refused` already answers; they do not differ in
    what the world did, which is pass.
    """
    td = time_diff if isinstance(time_diff, dict) else {}
    if "duration_seconds" in td:
        try:
            _finite(td.get("duration_seconds") or 0.0)
            return True
        except (TypeError, ValueError):
            pass
    for key in ("end_seconds", "elapsed_seconds"):
        if td.get(key) is None:
            continue
        try:
            _finite(td[key])
            return True
        except (TypeError, ValueError):
            continue
    return False


def beat_end_elapsed(prev_elapsed, time_diff, *, floor=False):
    """Where the clock stands at the END of a beat. THE ONE PLACE THIS IS
    COMPUTED.

    Returns ``(elapsed, displaced, refused, floored)`` -- `read_time_diff`'s
    three answers plus whether this beat was charged
    `UNCLAIMED_BEAT_SECONDS` for saying nothing.

    ONE HELPER, AND THE REASON IS A CLASS THAT HAS ALREADY BITTEN TWICE.
    Three separate readers decide what the beat's end clock is for something
    STORED -- the scene commit writes `simulation_clock`, the memory commit
    stamps affect decay, strain windows and belief provenance, and the
    perception mirror merges the scene the narrator composes. When they read
    the diff themselves they disagreed: first about a beat that ran backwards
    (`persist/commit_memory` carries that regression's own comment), and then
    about a beat that claimed a position under a key one of them did not
    know. A caller that computes its own end clock re-opens exactly that
    class. Do not.

    `floor` is the caller saying THIS BEAT HAPPENED -- a resolved turn, not an
    establish. Assertion is the off switch: any claim `time_diff_claims`
    can read, including `duration_seconds: 0` and a re-asserted current
    position, turns the floor off completely, so a beat keeps the authority to
    say no time passed by SAYING it. Only silence and an unreadable claim are
    charged, and an unreadable claim is charged AND still reported: a refusal
    that also froze the world was the double defect.
    """
    elapsed, displaced, refused = read_time_diff(prev_elapsed, time_diff)
    if floor and not time_diff_claims(time_diff):
        return elapsed + UNCLAIMED_BEAT_SECONDS, displaced, refused, True
    return elapsed, displaced, refused, False


def normalize_time_of_day(value):
    """The scene's standing TIME-OF-DAY label, or "" when the value is not one.

    THE SPLIT THIS ENFORCES. `scene.time` used to hold two incompatible kinds
    of statement: a standing world property ("dusk", "Late autumn afternoon")
    written once by `director_establish`, and a per-beat PASSAGE PHRASE
    ("moments later") written by every resolved beat. They are not the same
    kind of sentence -- one says where the world stands, the other says how
    far this beat moved -- and every reader in the tree wanted the first while
    the writer that won on almost every beat produced the second. Measured
    2026-08-25 across the author's 81-chat corpus: 63 of 80 openings named a
    readable time of day and only 6 live scenes still held one, so 57 stories
    lost theirs to the passage phrase. `scene.time_of_day` is the standing
    property; the passage phrase has no scene field at all (it survives as the
    beat's own record on the persisted resolve variant).

    A LABEL, NOT A CLOCK. Any written form is legitimate -- "dusk", "0830",
    "Stardate 46357.4, 14:32 hours" -- because a time of day is fiction the
    story wrote, and `dressing.backdrops.time_bucket` is the one place that
    has to categorise it. What this refuses is a value that is not written
    language at all: one live chat holds the bare boolean `False` here, and a
    non-string reaching an image prompt or a mind's payload is nonsense no
    reader downstream can detect.
    """
    if isinstance(value, str):
        return value.strip()
    return ""


def time_diff_duration(time_diff):
    """How long a beat took, in story seconds, from the diff ALONE.

    `duration_seconds` when it parses, else the span between a parseable
    start and end. An absolute-only diff reads 0 here on purpose: this seam
    (the vitals tick inside `merge_scene_with_diff`) is handed no previous
    clock to subtract from, so the honest answer to "how long was this
    beat" is "this block does not say". Under-ageing a body is recoverable;
    ageing it by the whole elapsed history of the story is not. Registered
    as a residual in docs/UNBUILT.md 1.83.
    """
    td = time_diff if isinstance(time_diff, dict) else {}
    if "duration_seconds" in td:
        try:
            return max(0.0, _finite(td.get("duration_seconds") or 0.0))
        except (TypeError, ValueError):
            pass
    try:
        return max(0.0, _finite(td["end_seconds"]) - _finite(td["start_seconds"]))
    except (KeyError, TypeError, ValueError):
        return 0.0


# News latency by distance (movement/space Phase 3b): when a destruction
# declaration names a news audience WITHOUT an explicit latency_seconds,
# the minting path (commit._prepare_destruction) derives one from the
# audience's hop distance to the destroyed root in the lorebook
# containment/presence graph (parent_id + currently_within edges,
# undirected BFS). One hop = one hour of story time; an audience that
# matches no book, or is unreachable from the root, waits a flat day. A
# declared latency always wins -- the Director owns the causal narrative;
# this is only the deterministic default that makes near regions hear
# sooner and distant ones later.
NEWS_HOP_LATENCY_SECONDS = 3600.0
NEWS_UNREACHABLE_LATENCY_SECONDS = 86400.0


def news_latency_seconds(distance_hops):
    """Deterministic derived news latency: graph hops * one hour; None
    (no matching book / unreachable) -> one day."""
    if distance_hops is None:
        return NEWS_UNREACHABLE_LATENCY_SECONDS
    try:
        hops = max(0.0, float(distance_hops))
    except (TypeError, ValueError):
        return NEWS_UNREACHABLE_LATENCY_SECONDS
    return hops * NEWS_HOP_LATENCY_SECONDS


def _payload_of(row):
    """A row's payload as a dict. Already-parsed payloads pass through, so a
    caller that hands rows straight out of SQL and one that builds them in
    memory reach the same code -- the sweep owns the shape either way."""
    raw = row.get("payload")
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


#: A town event's room no frame's people attend (`_fire_due_events`).
_UNCLAIMED = object()


def _is_town_event(row):
    """A charter's own event (`charter_runtime._scheduled_row`): the town's,
    stamped with its era, not with the frame whose commit ticked it."""
    return str((row or {}).get("seed") or "").startswith("charter:")


def _era_stamp(payload):
    """The era a town event is stamped with; None for the present."""
    value = (payload or {}).get("frame_id")
    if value in (None, "", 0):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _fire_due_events(scene, elapsed, frame_id, pending, *, turn_idx=None,
                     player_room=None, town=None, presence_rooms=()):
    """Pass (a). Returns (event_ops, notices, counts, pending_arrivals):
    the last is `{entity id: row}` for this frame's transit arrivals not yet
    due, which pass (b) reads to time each journey once.

    ``town`` is how a TOWN event is placed when the era has more than one
    frame running (`commit_mechanics.town_for_sweep`): `frames`, every frame
    of the era; `claims`, {room: frame} for the rooms some frame's people
    attend; `root`, the era's own frame. A town event fires in the frame whose
    people are standing where it happens, on that frame's clock; nobody
    there, it is recorded in the era root by whichever frame reaches its time
    first, and the people of the town who stood there carry it. Without
    ``town`` every row keeps the rule below -- this frame's rows only.
    ``presence_rooms`` are the rooms this frame's own people stand in when
    it has no player: a town event landing there is a walk-in too.

    pending rows arrive in due_at order (the caller's query) and each is
    frame-gated by the frame_id in its payload: scheduled_events has no
    frame column while simulation clocks are frame-scoped, so an event
    minted in one frame must never fire against another frame's clock.

    ``consequence`` rows (living_world.mint_consequences) fire the same
    deterministic way and their firing is LAYER-1 FACT — it happened
    whether or not anyone was there. The notice is the only knowledge
    surface, and it is emitted ONLY when the player is standing at the
    fuse's location as it lands (walking in on it); everywhere else the
    fired row waits to be read at contact (residue, gap skeleton). That
    presence gate is the §0.2 firewall: an event elsewhere is never told,
    only encountered. No setting gates the notice: the
    `scheduled_consequence` depth that once did was retired on 2026-09-20
    (see `mechanics_sweep`), and every declared fuse is minted and fires on
    its clock whatever any setting says (A82).
    """
    event_ops = []
    notices = []
    fired = news_fired = consequences_fired = 0
    pending_arrivals = {}
    entities = scene.get("entities") or {}
    positions = scene.setdefault("positions", {})

    for row in pending:
        payload = _payload_of(row)
        if row.get("kind") == "consequence":
            where = str(payload.get("where") or "")
            record_in = frame_id
            if town is not None and _is_town_event(row):
                if (_era_stamp(payload) not in town["frames"]
                        or row["due_at"] > elapsed):
                    continue
                claimant = town["claims"].get(where, _UNCLAIMED)
                if claimant is _UNCLAIMED:
                    record_in = town["root"]
                elif claimant != frame_id:
                    # Another frame's people are standing there: it lands in
                    # front of them, on their clock, in their commit.
                    continue
            elif payload.get("frame_id") != frame_id or row["due_at"] > elapsed:
                continue
            if jobs.story_rewound_past(payload.get("base_turn"), turn_idx):
                # The base-revision check at fire time: a fuse minted from a
                # turn the story no longer contains describes a future whose
                # cause un-happened. Cancelled loudly, never fired — the
                # base-turn discipline every out-of-band landing keeps
                # (`jobs.story_rewound_past`), applied to the delay line.
                event_ops.append(("status", row["event_id"], "cancelled"))
                continue
            event_ops.append(("status", row["event_id"], "fired"))
            if record_in != frame_id:
                event_ops.append(("record_in", row["event_id"], record_in))
            consequences_fired += 1
            walked_in = bool(player_room) and where == str(player_room)
            if not walked_in and record_in == frame_id:
                walked_in = where in set(presence_rooms or ())
            if walked_in:
                notices.append(
                    "Falling due here, now: "
                    f"{payload.get('what') or 'a scheduled consequence'} "
                    "(stage it as present state resolving in front of the "
                    "party)."
                )
            continue
        if row.get("kind") == "news_arrival":
            if payload.get("frame_id") != frame_id or row["due_at"] > elapsed:
                continue
            event_ops.append(("status", row["event_id"], "fired"))
            news_fired += 1
            audience = str(payload.get("audience") or "nearby observers")
            summary = str(payload.get("summary") or "word of a distant event")
            notices.append(
                f"News reaches {audience} (told/heard, not witnessed): "
                f"{summary}"
            )
            continue

        # transit_arrival
        eid = str(payload.get("entity_id") or "")
        if payload.get("frame_id") != frame_id:
            continue
        if row["due_at"] > elapsed:
            pending_arrivals[eid] = row
            continue
        ent = entities.get(eid)
        state = ent.get("state") if isinstance(ent, dict) else None
        transit = state.get("transit") if isinstance(state, dict) else None
        if not isinstance(transit, dict) \
                or str(transit.get("phase") or "").casefold() == "docked":
            # Entity gone, or the director already docked it by hand --
            # the event is moot, not fireable.
            event_ops.append(("status", row["event_id"], "cancelled"))
            continue
        bound_now = str(transit.get("destination_room") or "").strip()
        destination = str(payload.get("destination_room") or bound_now or "")
        # A JOURNEY THAT NAMES ANOTHER END IS NOT THIS ARRIVAL'S (2026-10-21).
        # The payload's end stands over a transit that names none -- a later
        # write that leaves the destination out is silence about it (review
        # B1) -- but a transit that names a different place has turned for
        # it: this arrival is moot, and pass (b) times the journey it is on.
        # Before every journey had an arrival, a turned vessel docked at the
        # end it had given up.
        if bound_now and destination and not _same_place(scene, bound_now, destination):
            event_ops.append(("status", row["event_id"], "cancelled"))
            continue
        label = (ent.get("name") if isinstance(ent, dict) else "") or eid
        held = scene_room_id(scene, destination) if destination else ""
        if destination and not held:
            # NOTHING ARRIVES NOWHERE, AND NOTHING WAITS FOREVER (2026-10-21).
            # Its way is done and its end is a place the world does not hold:
            # it comes in AT that place, off the map -- docked, in no room,
            # its `destination_room` naming where it is -- and stands there the
            # beat the place is a room (`spatial_transit.settle_departures`'
            # docked rule); until then its doorway opens onto nothing
            # (`apply_transit_dock_edges`, pass (d)), and the bodies in its
            # rooms are with it. Code never builds the place: the compiler
            # asks the Room for it (`mapping._transit_destination_needs`).
            # This replaced writing the name into `positions`, which stood the
            # vessel in a room that does not exist.
            stand_in_no_room(scene, eid, ent)
            transit["phase"] = "docked"
            transit["destination_room"] = destination
            for key in ("eta_seconds", "route_room", "departed_from"):
                transit.pop(key, None)
            event_ops.append(("status", row["event_id"], "fired"))
            fired += 1
            notices.append(
                f"{label} has come to the end of its way, at {destination}: "
                "a place the world does not hold yet. It is docked there, off "
                "the map, with whoever is in its rooms, and stands there the "
                "beat the place is built.")
            continue
        if destination:
            positions[eid] = held
        transit["phase"] = "docked"
        transit.pop("eta_seconds", None)
        transit.pop("destination_room", None)
        # Docked, the journey is over (`spatial_transit.settle_departures`).
        transit.pop("departed_from", None)
        event_ops.append(("status", row["event_id"], "fired"))
        fired += 1
        notices.append(
            f"{label} has arrived at "
            f"{held or 'its destination'} and is docked there."
        )

    return event_ops, notices, \
        {"fired": fired, "news_fired": news_fired,
         "consequences_fired": consequences_fired}, \
        pending_arrivals


def _same_place(scene, a, b) -> bool:
    """Two spellings of one destination: equal folded, or the same room the
    scene holds (`spatial.scene_room_id`)."""
    a, b = str(a or "").strip(), str(b or "").strip()
    if not a or not b:
        return False
    if a.casefold() == b.casefold():
        return True
    held = scene_room_id(scene, a)
    return bool(held) and held == scene_room_id(scene, b)


#: The payload key an arrival timed by the ENGINE'S price of the way carries
#: (the seconds priced), beside the three every arrival carries. Its absence
#: is a time somebody wrote, which a later write never moves; its presence is
#: an estimate, which the first time anybody writes replaces
#: (`_schedule_new_arrivals`).
PRICED_ARRIVAL_KEY = "priced_seconds"

#: ...and the pace that price was made at, in paces (metres) a second
#: (`spatial.journey_pace`: the vessel's own speed, else the charter's walk).
#: A row priced before a vessel could carry a speed has none, and was priced
#: at the walk (`_priced_pace`). It is what re-times a journey under way when
#: the story changes how fast the vessel goes (`_schedule_new_arrivals`).
PRICED_SPEED_KEY = "priced_speed"

#: Decimal places (of a metre a second) at which the pace an arrival was
#: priced at and the speed the vessel now makes are compared; the payload
#: keeps the pace whole, so the re-timed remainder is exact. Not a tolerance
#: anyone tunes: a speed restated in the same words reads back as the same
#: number, and one restated in another unit (seven knots as 12.96 km/h)
#: differs only past these places, where it is the same speed.
PRICED_SPEED_DIGITS = 4


def _priced_pace(booked):
    """The pace an arrival the engine priced was priced at: its
    `PRICED_SPEED_KEY`, else the charter's walk, the only pace there was
    before a vessel could carry its own (2026-10-21)."""
    try:
        pace = float(booked.get(PRICED_SPEED_KEY))
    except (TypeError, ValueError):
        pace = 0.0
    if pace > 0:
        return pace
    from world.charter_move import WALK_PACES_PER_SECOND
    return float(WALK_PACES_PER_SECOND)


def _written_eta(transit):
    """The positive `eta_seconds` a transit carries, else None. A positive
    number is a time somebody wrote; nothing, zero, a negative or a word is
    no time written -- the rule pass (b) always had, which scheduled on a
    parseable positive eta and nothing else. No stored journey with a
    destination carries a zero (the owner's database, the probe and the
    2026-09-26 stories)."""
    try:
        eta = float(transit.get("eta_seconds"))
    except (TypeError, ValueError):
        return None
    return eta if eta > 0 else None


def _schedule_new_arrivals(scene, elapsed, frame_id, pending_arrivals,
                           chat_id, turn_id, turn_idx):
    """Pass (b): every journey toward a destination is timed, once, with a
    deterministic arrival event (stable id, so a rerun cannot
    double-schedule).

    SOMETHING UNDER WAY TOWARD A DESTINATION ARRIVES WHEN ITS WAY IS DONE,
    whether or not anyone wrote down a time (2026-10-21). This pass used to
    schedule on a written `eta_seconds` and nothing else, and the transit
    card names that field without ever asking for it: since the prose encoder
    (2026-09-27) not one stored journey with a destination carried one, so
    none of them could arrive. The control story (chat 2, idx 4-9): the Mary
    Ann sat in the channel 77.7 story hours, bound for a mainland the world
    measured at thirteen kilometres.

    * A POSITIVE `eta_seconds` IS A TIME SOMEBODY WROTE, and it stands: due
      that many seconds from this sweep's clock, as it always was.
    * WITHOUT ONE, THE ENGINE PRICES THE WAY (`spatial.journey_seconds`: the
      world's own edges from the space it moves through to where it is bound,
      at the vessel's own speed where the story wrote one, else the charter's
      walking pace -- `spatial.journey_pace`) for a journey under way --
      `in_transit` or `arriving`; a vehicle `sealed` and not yet away has not
      begun one -- and the payload carries the price and the pace it was made
      at (`PRICED_ARRIVAL_KEY`, `PRICED_SPEED_KEY`). A vessel already
      standing where it is bound is not timed again: its way is done.
    * ONE ARRIVAL PER JOURNEY. A pending arrival for the same end stands --
      a time restated each beat never slips -- unless it was the engine's
      price and a time has since been written, which replaces it once. A
      pending arrival for an end the journey no longer names is cancelled
      and the journey it is on is timed (`_fire_due_events` cancels one that
      comes due so, too).
    * A SPEED THE STORY CHANGES RE-TIMES THE JOURNEY UNDER WAY, as a turn
      does: the engine's price, booked at one pace, is cancelled when the
      vessel's record writes another, and what is left of the way -- the
      seconds still to run at the old pace -- is booked again at the new one.
      The owner's ruling (2026-10-21) gives each vessel the speed its story
      gives it, so an engine that fails mid-crossing, written as the slower
      speed it now makes, must slow the crossing it is on. A record that
      stops saying a speed is silence, not a return to a walk, and a time
      somebody wrote is never moved by a speed.

    ``pending_arrivals`` is `_fire_due_events`' `{entity id: row}`; a plain
    collection of ids is read as rows unknown, which are left standing."""
    event_ops = []
    scheduled = 0
    entities = scene.get("entities") or {}
    pending = pending_arrivals if isinstance(pending_arrivals, dict) else {
        str(eid): None for eid in (pending_arrivals or ())}

    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        state = ent.get("state")
        transit = state.get("transit") if isinstance(state, dict) else None
        if not isinstance(transit, dict):
            continue
        phase = str(transit.get("phase") or "").strip().casefold()
        if phase == "docked":
            continue
        destination = str(transit.get("destination_room") or "").strip()
        if not destination:
            continue
        written = _written_eta(transit)
        speed = vessel_speed(ent)
        rest_of_the_way = None
        if str(eid) in pending:
            row = pending[str(eid)]
            if row is None:
                continue
            booked = _payload_of(row)
            same_end = _same_place(scene, booked.get("destination_room"), destination)
            priced_row = PRICED_ARRIVAL_KEY in booked
            if same_end:
                if written is not None and priced_row:
                    pass        # a time written after the price replaces it once
                elif written is None and priced_row and speed is not None \
                        and round(speed, PRICED_SPEED_DIGITS) \
                        != round(_priced_pace(booked), PRICED_SPEED_DIGITS):
                    # What is left of the way, at the pace it was priced at,
                    # covered at the speed the vessel now makes.
                    left = max(0.0, float(row["due_at"]) - float(elapsed))
                    rest_of_the_way = left * _priced_pace(booked) / speed
                else:
                    continue
            event_ops.append(("status", row["event_id"], "cancelled"))
        priced = None
        if written is not None:
            eta = written
        elif rest_of_the_way is not None:
            eta = priced = rest_of_the_way
        else:
            # Under way toward a place, or nothing to price (`journey_seconds`).
            eta = journey_seconds(scene, eid, ent)
            if not eta:
                continue        # nothing to price, or already where it is bound
            priced = eta
        payload = {"entity_id": eid, "destination_room": destination,
                   "frame_id": frame_id}
        if priced is not None:
            payload[PRICED_ARRIVAL_KEY] = round(float(priced), 1)
            payload[PRICED_SPEED_KEY] = journey_pace(ent)
        event_id = stable_event_key(
            "transit_arrival", chat_id, frame_id, eid, turn_id)
        event_ops.append(("schedule", {
            "event_id": event_id,
            "chat_id": chat_id,
            "due_at": elapsed + eta,
            "kind": "transit_arrival",
            # Where the mover IS, by identity (review 2026-09-07, B18):
            # `positions.get(eid)` filed the arrival event at no location
            # whenever the row was keyed by the vehicle's display name.
            "location_id": room_of_record(scene, eid, ent),
            "payload": json.dumps(payload, ensure_ascii=False),
            "seed": f"transit:{chat_id}:{turn_idx}",
            "status": "pending",
        }))
        scheduled += 1

    return event_ops, scheduled


# ---- Conditions that ACT while they last (pass (c1)) ----
#
# `world_conditions` shipped with a `next_tick` column and an
# `idx_world_conditions_due` index over it, and nothing ever wrote either.
# Measured read-only on the author's engine.db 2026-08-25: 444 rows across
# 50 chats, `next_tick` NULL in all 444, while 131 ACTIVE rows carried an
# authored `tick_interval_seconds` (0, 5, 10, 15, 20, 30, 45, 60, 300) that
# no reader in the engine consumed. The body specialist's own sheet asks for
# the field; llm/schemas.py stated the open question in its own comment --
# build the due-tick sweep, or drop the field, the column and the index.
# This pass is the build, and it runs BEFORE expiry so a condition's last
# due tick lands before the clock closes it.
#
# WHAT A TICK MAY DO IS DELIBERATELY SMALL, because the engine must not learn
# what any particular condition MEANS -- 106 distinct `kind` strings are
# active in the corpus, so `kind` is open vocabulary and a per-kind effects
# table would be an instance fix wearing a general syntax. A tick may move a
# survival vital the scene ALREADY tracks, and it may re-announce one clause
# as an engine notice. Everything else a condition does stays the Director's.
#
# Cadence is owned by THIS pass, never by the writer: a row is scheduled from
# the clock the sweep first sees it on. Every existing row meets this
# uninitialized, and an initialization that also fired would charge each of
# them for the whole of the story that happened before the sweep existed.

#: Most fires one row may take in one beat. Not a rate limit on fiction --
#: a rate limit on arithmetic, for a five-second cadence meeting a time skip.
_TICK_FIRE_CAP = 500
#: Most one tick may move one vital. A model authoring `-1.0` against a
#: five-second cadence would empty a body inside one beat; the CADENCE is how
#: a condition gets to be lethal, not the size of a single step.
_TICK_VITAL_STEP_CAP = 0.25
#: Most tick notices one sweep may stage. The sibling of
#: `director_floors._CONDITIONS_VIEW_CAP` (40) and set lower on purpose: the
#: view is a ledger the Director reads to ACT on, and these are the world
#: saying the same sentence again. One corpus chat carries 24 active rows
#: (engine.db 2026-08-25), so an uncapped sweep can spend a beat's whole
#: notice budget on ongoing processes and crowd out what just happened.
_TICK_NOTICE_CAP = 8


def _condition_field(payload, key):
    """A condition field, spelled at the payload root or inside `state`.

    Both spellings are live across the table (`story.scene._condition_state`
    tolerates the same pair), so a reader that knows only one of them is a
    reader that silently ignores half the rows.

    A root spelling present but NULL is silence, not an answer: a model that
    emits the whole field list with the ones it has nothing to say about left
    null would otherwise mask the value it did fill in under `state`. Latent
    today (0 of 444 corpus rows are in that shape, measured 2026-08-25), and
    the docstring above is the reason to close it anyway -- the failure it
    describes is exactly a reader ignoring the half of the row that speaks.
    """
    value = payload.get(key)
    if value is not None:
        return value
    state = payload.get("state")
    if isinstance(state, dict) and state.get(key) is not None:
        return state.get(key)
    return value


def _tick_interval(payload):
    """The declared cadence in simulation seconds, or None when there is not
    one. Zero is NOT "tick constantly" -- 48 of the 131 interval-bearing
    corpus rows spell `0`, the commonest authored value, and a field filled
    in with nothing is not a cadence (it is also a divisor of zero)."""
    try:
        interval = float(_condition_field(payload, "tick_interval_seconds"))
    except (TypeError, ValueError):
        return None
    if interval <= 0 or interval != interval or interval in (
            float("inf"), float("-inf")):
        return None
    return interval


def _tick_spec(payload):
    """What one tick of this condition DOES: (vitals_deltas, percept).

    `vitals` is restricted to the four keys `world.survival.VITALS` defines
    and each per-tick step is clamped -- the guard SUBTRACTS, so a vital the
    ledger does not track is dropped rather than invented. `percept` is one
    short clause the world keeps saying while the process runs.
    """
    from world.survival import VITALS

    block = _condition_field(payload, "tick")
    if not isinstance(block, dict):
        return {}, ""
    deltas = {}
    raw = block.get("vitals")
    for vital, value in (raw.items() if isinstance(raw, dict) else ()):
        name = str(vital or "").strip().casefold()
        if name not in VITALS:
            continue
        try:
            delta = float(value)
        except (TypeError, ValueError):
            continue
        if delta != delta or delta in (float("inf"), float("-inf")):
            continue
        deltas[name] = max(-_TICK_VITAL_STEP_CAP,
                           min(delta, _TICK_VITAL_STEP_CAP))
    return deltas, str(block.get("percept") or "").strip()


def _room_occupants(scene, room_id):
    """Every BODY standing in `room_id`, in the scene's own order.

    Read off `positions`, which is the one map that answers "where is this"
    -- not `rooms[...]` membership, which no scene keeps.

    AND `positions` IS NOT A BODY ROSTER (review 2026-09-07 A56). Everything
    with a where is in it: docked vehicles, the zones
    `spatial_frames.infer_vehicle_zones` derives, and every fixture, tool and
    piece of debris the Director has placed. Measured on chat 117's live
    scene (bench copy, 2026-09-08, `tools/bench/body_predicate_on_positions`):
    22 position keys and 2 bodies. A condition standing over every room of
    that scene reached 22 subjects and now reaches 3 -- it was taking the air
    of a pry bar, a klaxon speaker, two doors and a wrecked trolley, and
    warning every beat that no body of those names was in the vitals ledger.
    `spatial.scene_names_body` is the one predicate that
    answers this, shared with the contact identity floor, the comfort
    derivation and the creature's prey table rather than re-typed here; its
    last tier deliberately keeps a subject the scene records nothing about
    but where it stands, so a person nobody has dressed yet is never dropped
    from a fire in silence.
    """
    positions = (scene or {}).get("positions")
    if not isinstance(positions, dict):
        return []
    target = str(room_id or "").strip()
    return [str(name) for name, where in positions.items()
            if str(where or "").strip() == target and str(name or "").strip()
            and scene_names_body(scene, name)]


def condition_subject_room(scene, subject):
    """`subject` as a ROOM of this scene, or "" when it names no room.

    A room is matched by its id and by its display name, because
    `world_conditions.subject_id` is free model text and the body specialist
    writes whichever of the two the payload it was shown put in front of it.
    """
    rooms = (scene or {}).get("rooms")
    if not isinstance(rooms, dict):
        return ""
    raw = str(subject or "").strip()
    if not raw:
        return ""
    if raw in rooms:
        return raw
    folded = raw.casefold()
    for rid, room in rooms.items():
        if str(rid).strip().casefold() == folded:
            return str(rid)
        if isinstance(room, dict) and str(
                room.get("name") or "").strip().casefold() == folded:
            return str(rid)
    return ""


def _tick_subjects(scene, cond):
    """Whose bodies one ticking condition acts on.

    A STANDING CONDITION OF A PLACE IS A FACT ABOUT STANDING IN IT. This is
    still the SINGLE place a ticking condition's subject is resolved to
    bodies, and it now answers the case the docstring here reserved: when the
    subject names a room of this scene, the condition acts on whoever is in
    that room, and on nobody when the room is empty. Everything else -- the
    firing, the batching, the clamps, the op family -- is unchanged.

    Measured, chat "rush" 2026-09-05 (PR4): `second_landing_fire` (severity
    0.9) and `third_landing_fire` ("critical") stood for six beats while two
    bodies climbed through them, and a condition whose subject is a landing
    reached nobody, because the only subject this function knew was a person.
    """
    subject = str(cond.get("subject_id") or "").strip()
    if not subject:
        return []
    room_id = condition_subject_room(scene, subject)
    if room_id:
        return _room_occupants(scene, room_id)
    return [subject]


def inert_condition_ids(conditions):
    """Active conditions that SPELL a cadence and fill it with a non-cadence.

    A row whose `tick_interval_seconds` is absent is a condition that never
    claimed to act; a row that spells the field and puts `0` (or a negative,
    or something unreadable) in it is a writer who meant "this goes on" and
    said nothing the sweep can fire on. That second kind is silently inert,
    and silence is this table's whole failure history -- 48 of the 131
    interval-bearing corpus rows spell `0` (engine.db 2026-08-25), and all six
    conditions of the burning tenement did (chat "rush" 2026-09-05, PR4b),
    which is why a building on fire acted on nobody for twenty beats.

    Returns condition ids, sorted, for the commit domain to report. Pure: it
    reads rows and decides nothing.
    """
    out = []
    for cond in conditions or []:
        if not condition_cadence_is_inert(_payload_of(cond)):
            continue
        cid = str(cond.get("condition_id") or "").strip()
        if cid and cid not in out:
            out.append(cid)
    return sorted(out)


def condition_cadence_is_inert(payload):
    """Does this payload SPELL a cadence that the sweep can never fire on?

    The predicate behind `inert_condition_ids`, public because the answer is
    needed in two places and a second derivation of it drifted. The Director's
    `active_conditions` view (`agents/director_floors._conditions_view`) read
    the same field through a plain float cast, which answers `0.0` where
    `_tick_interval` answers None -- so the ledger showed the Director a
    cadence the engine had already refused, and the row that "declares a tick
    cadence" was reported inert at commit while reading as live in the payload
    that was supposed to let the Director repair it.

    Absent is not inert: a row that never claimed a cadence is a condition
    that never claimed to act.
    """
    if _condition_field(payload, "tick_interval_seconds") is None:
        return False
    return _tick_interval(payload) is None


def _tick_conditions(scene, conditions, elapsed):
    """Pass (c1). Returns (event_ops, notices).

    One op shape: ("tick_condition", condition_id, new_next_tick), applied by
    the commit domain as the `next_tick` column write the table was built for.
    """
    from world.survival import _stored_vitals, vitals_entry_key

    event_ops, notices, unnamed, air_taken = [], [], [], []
    for cond in conditions or []:
        payload = _payload_of(cond)
        interval = _tick_interval(payload)
        if interval is None:
            continue
        cid = cond.get("condition_id")
        raw_next = cond.get("next_tick")
        if raw_next is None:
            event_ops.append(("tick_condition", cid, elapsed + interval))
            continue
        try:
            t = float(raw_next)
        except (TypeError, ValueError):
            event_ops.append(("tick_condition", cid, elapsed + interval))
            continue
        expires = _condition_expires_at(cond)

        fires = 0
        while t <= elapsed and fires < _TICK_FIRE_CAP:
            if expires is not None and t >= expires:
                break
            fires += 1
            t += interval
        if not fires:
            continue
        if fires >= _TICK_FIRE_CAP and t <= elapsed:
            # THE CAP CATCHES UP; IT DOES NOT LAG. The story clock is free to
            # jump hours in one beat (`read_time_diff`, alpha 9.8.2), so
            # carrying the capped cadence forward as next_tick + fires*
            # interval would leave the row permanently behind the clock and
            # re-hit the cap on every beat for the rest of the story.
            t = elapsed + interval
        event_ops.append(("tick_condition", cid, t))

        deltas, percept = _tick_spec(payload)
        table = scene.get("vitals") if isinstance(scene, dict) else None
        moved, missing = [], []
        subjects = _tick_subjects(scene, cond)
        if deltas.get("air", 0.0) < 0:
            # WHOSE AIR THE WORLD IS TAKING, written down where the next
            # beat's `tick_vitals` can read it (world/survival.AIR_DENIED_KEY).
            # Recorded from the CONDITION acting, not from the ledger moving,
            # so a story that has not enabled survival still records the fact
            # and one that enables it mid-fire is right from the next beat.
            for subject in subjects:
                if subject not in air_taken:
                    air_taken.append(subject)
        for subject in subjects:
            if not deltas:
                break
            if not isinstance(table, dict) or not table:
                # ABSENCE IS THE OFF SWITCH (world/survival.py: "nothing
                # creates the table but an explicit write"). A tick may MOVE
                # a vital; it may never CREATE the ledger. 131 active corpus
                # rows carry intervals, so a seeding tick would have started
                # a hunger clock in every story that never enabled survival.
                # Dropped in silence: the setting being off is not a failure.
                break
            # One body is one row, and `world.survival.vitals_entry_key` is
            # the single answer to which row that is (review 2026-09-07, B4).
            key = vitals_entry_key(table, subject)
            if key is None:
                # The ledger EXISTS and this subject is not in it -- a real
                # miss worth saying, not a setting. Condition subjects are
                # free model text and some rows carry scene uids
                # (docs/UNBUILT.md 1.65). A mechanism that silently never
                # fires is this table's whole failure history.
                missing.append(subject)
                continue
            record = table[key]
            current = _stored_vitals(record)
            for vital, delta in deltas.items():
                before = current.get(vital, 0.0)
                after = max(0.0, min(before + delta * fires, 1.0))
                record[vital] = after
                if after != before:
                    moved.append(f"{subject} {vital} {after - before:+.2f}")

        label = str(cond.get("subject_id") or cond.get("kind") or "").strip()
        parts = [p for p in (percept, ", ".join(moved)) if p]
        if parts:
            # ONE notice per condition per sweep however many times it fired:
            # a clause repeated four times is the same fact four times.
            notices.append(
                f"Ongoing ({label}, {fires}x): " + "; ".join(parts))
        for subject in missing:
            if subject not in unnamed:
                unnamed.append(subject)

    if len(notices) > _TICK_NOTICE_CAP:
        # Truncated, and SAID. A silently dropped notice is a process the
        # world stopped mentioning while it kept running.
        dropped = len(notices) - _TICK_NOTICE_CAP
        notices = notices[:_TICK_NOTICE_CAP]
        notices.append(
            f"Ongoing: {dropped} further standing condition"
            f"{'s are' if dropped != 1 else ' is'} also acting this beat, "
            "not listed here.")
    if unnamed:
        # ONE line per sweep, not one per row. This notice restages every
        # beat until the Director re-emits with a subject the ledger names,
        # so N rows naming the same absent body is that body's name repeated
        # N times every beat for the rest of the story.
        notices.append(
            "Ongoing: standing conditions declare vitals changes for "
            + ", ".join(unnamed)
            + ", and no body of that name is in this scene's vitals ledger "
            "-- name the subject as the scene names them, or the change goes "
            "nowhere.")

    if isinstance(scene, dict):
        from world.survival import set_air_denied
        # REPLACES every beat, like `engine_notices`: a body that walked out
        # of the smoke this beat is not in this list, and recovers normally.
        set_air_denied(scene, air_taken)

    return event_ops, notices


#: How many bodies one unanswered-hazard warning names before it counts the
#: rest. A crowd in a burning building is the case this exists for, and a
#: warning that lists twenty names is a warning nobody reads.
HAZARD_REPORT_CAP = 6

#: The state_diff channels that constitute the world having ACTED on a body:
#: a roll, a standing condition, a vital, a consequence. Named here because
#: this is the whole vocabulary the engine has for "something happened to
#: this body", and a floor that checked fewer of them would report a beat
#: that did answer. `_answered_bodies` READS these -- it spelled the same
#: four out for itself while this constant sat unread (E30, 2026-09-07),
#: which is the two-representations-free-to-disagree failure this repo keeps
#: finding, and a channel added to one copy would have reached neither floor.
#: The first member is the whole-beat channel: it names no subject and
#: answers for everybody at once, so it is read apart from the rest.
_HAZARD_WHOLE_BEAT_CHANNEL = "dice"
_HAZARD_ANSWER_CHANNELS = (_HAZARD_WHOLE_BEAT_CHANNEL, "conditions", "vitals",
                           "consequences")


def _condition_states_harm(cond):
    """Does this row say, in a field the engine owns, that it is dangerous?

    `kind` is open vocabulary -- 106 distinct strings across the corpus -- so
    nothing here reads it, and a room condition is not a hazard just for
    existing (a room can stand under a festival as easily as under a fire).
    Two fields answer without a word list: a declared `severity`, which is
    the row's own statement of how bad it is, and a `tick` that TAKES a
    vital. All six conditions of the burning tenement carried the first
    (`second_landing_fire` 0.9, `third_landing_fire` "critical") and none
    carried the second, which is why severity has to count.
    """
    payload = _payload_of(cond)
    if str(_condition_field(payload, "severity") or "").strip():
        return True
    deltas, _percept = _tick_spec(payload)
    return any(value < 0 for value in deltas.values())


def _hazard_rooms(scene, conditions):
    """Room ids this world states are dangerous to stand in, by cause.

    ONE SOURCE: an active `world_conditions` row whose subject resolves to a
    room of this scene. It used to read a second one -- a `hazard` block on
    the scene's room dict -- and a question with two stores is a question
    with two answers (review 2026-09-07 B8); `world.region_events.apply_wave`
    now states its hazard in the table every other standing condition of a
    place is already in. Nothing here reads a description, a name or a
    severity word.
    """
    out = {}
    for cond in conditions or []:
        rid = condition_subject_room(scene, cond.get("subject_id"))
        if not rid or not _condition_states_harm(cond):
            continue
        out.setdefault(rid, []).append(
            str(cond.get("kind") or cond.get("condition_id") or "condition"))
    return out


def _answered_bodies(state_diff):
    """Casefolded names of bodies this beat's diff recorded an outcome for.

    A `dice` list with any entry in it answers for EVERYBODY: a beat that
    rolled has contested something, and this floor is about beats that never
    reached for the dice at all. The channels are `_HAZARD_ANSWER_CHANNELS`,
    read and not re-typed.
    """
    diff = state_diff if isinstance(state_diff, dict) else {}
    if diff.get(_HAZARD_WHOLE_BEAT_CHANNEL):
        return None                     # None means "the whole beat answered"
    named = set()
    for key in _HAZARD_ANSWER_CHANNELS:
        if key == _HAZARD_WHOLE_BEAT_CHANNEL:
            continue
        value = diff.get(key)
        if isinstance(value, dict):
            for subject, entry in value.items():
                named.add(str(subject).strip().casefold())
                rows = entry if isinstance(entry, list) else [entry]
                for row in rows:
                    if isinstance(row, dict):
                        named.add(str(row.get("subject_id") or "")
                                  .strip().casefold())
        elif isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    named.add(str(row.get("subject_id")
                                  or row.get("subject")
                                  or row.get("who") or "").strip().casefold())
    named.discard("")
    return named


def unanswered_hazard_subjects(scene, conditions, bodies, state_diff):
    """Bodies standing in a stated hazard on a beat that recorded no outcome.

    THE WORLD IS A PARTY TO A CONTEST. `resolution_flags.contested` keys off
    REACTORS, so a story with nobody else in it has no contest, no `dice`, and
    a resolve that writes no `conditions`, `vitals` or `consequences` -- across
    21 turns of chat "solitude" 2026-09-05 (PS12) those three channels were
    empty 21 times out of 21, including a deliberate fast descent of a
    twenty-pace salt-glazed stair with both hands full. The complement of that
    finding is chat "rush" (PR4): six fire conditions stood over two bodies for
    six beats and not one of them was ever answered either, and there a second
    party was present. The common rule is not about who else is in the room.

    Returns the names, in scene order, of bodies the scene puts inside a
    hazardous place (`_hazard_rooms`) on a beat whose diff answered for
    nobody. Pure and total; the caller decides what to say about it. It
    self-silences the moment the mechanism works -- a condition that ticks a
    vital IS an answer.
    """
    if not isinstance(scene, dict):
        return []
    hazards = _hazard_rooms(scene, conditions)
    if not hazards:
        return []
    answered = _answered_bodies(state_diff)
    if answered is None:
        return []
    positions = scene.get("positions")
    if not isinstance(positions, dict):
        return []
    out = []
    for name, where in positions.items():
        label = str(name or "").strip()
        if not label or str(where or "").strip() not in hazards:
            continue
        # `positions` is not a body roster (A56): a boat docked at a flooded
        # quay is in it, and the warning is about who the world was not
        # answered FOR. The predicate is `spatial.scene_names_body`, not the
        # caller's cast list -- the player is a body and is not cast, and the
        # one production caller passes no roster at all.
        if not scene_names_body(scene, label):
            continue
        if bodies is not None and label.casefold() not in {
                str(b).strip().casefold() for b in bodies}:
            continue
        if label.casefold() in answered:
            continue
        out.append(label)
    return out


def _condition_expires_at(cond):
    """A `world_conditions` row's end on the story clock, or None for a row
    whose end this sweep cannot read -- absent, a word, empty, not finite.

    ONE READER FOR BOTH PASSES. The tick pass (c1) guarded this column and
    the expiry pass (c2) did not: SQLite's REAL affinity keeps a value that
    is not a number as TEXT, the sweep is the FIRST domain inside the commit
    transaction, so a single row written `""` or `"dawn"` raised in (c2),
    rolled that beat back, and every beat after it, until a hand edited the
    row (world_offscreen_time F2, audit 2026-11-01; 0 of 538 live rows today).
    An unreadable end is no end: the row stays until something that can be
    read ends it, exactly as (c1) already treated it. Coercing the value at
    the WRITE is the storage side's (`persist/commit_entities`).
    """
    raw = (cond or {}).get("expires_at") if isinstance(cond, dict) else None
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return _finite(raw)
    except (TypeError, ValueError):
        return None


def _expire_conditions(conditions, elapsed):
    """Pass (c2): active conditions whose expires_at has passed on this
    frame's clock. world_conditions is chat-scoped (no frame column); the
    committing frame's clock is used, matching how started_at is written."""
    event_ops = []
    for cond in conditions or []:
        expires = _condition_expires_at(cond)
        if expires is not None and expires <= elapsed:
            event_ops.append(("expire_condition", cond["condition_id"]))
    return event_ops


def mechanics_sweep(scene, clock, frame_id, pending, *,
                    conditions=(), prev_scene=None, chat_id=None,
                    turn_id=None, turn_idx=None, player_room=None, town=None,
                    presence_rooms=()):
    """Run the ordered passes (a)-(e).

    Returns (scene, event_ops, notices, counts).

    scene is mutated in place and also returned; event_ops is the list of
    durable operations for the caller to apply inside its transaction:
        ("status", event_id, new_status)   -- scheduled_events row update
        ("record_in", event_id, frame_id)  -- a fired town event belongs to
                                              another frame's record
                                              (`_fire_due_events`' `town`)
        ("schedule", row_dict)             -- scheduled_events upsert
        ("expire_condition", condition_id) -- world_conditions deactivate
        ("tick_condition", condition_id, next_tick) -- world_conditions
                                              cadence advance (pass (c1))
    notices is the engine_notices list for this beat (overwritten every
    sweep, so notices self-expire after one beat).

    counts is what pass (a) fired, by kind: `fired` (transit arrivals),
    `news_fired`, `consequences_fired`. Returned rather than kept private
    because the commit domain reports these numbers, and a caller that has to
    rebuild them from `event_ops` is writing a second implementation of a
    count this function already has -- which is what it did until WORLD-F3.
    `scheduled`, `expired` and `ticked` are NOT here: those are counts of ops
    the caller applies, and belong to whoever applies them.
    """
    elapsed = float((clock or {}).get("elapsed_seconds") or 0.0)

    # (a) fire due events for this frame. A fuse FIRES whatever the story's
    # settings say -- it is adjudicated causality, and truth accumulates
    # (A82) -- and its landing is put in front of whoever walks in on it.
    # ALWAYS SURFACED since 2026-09-20: the `scheduled_consequence` switch
    # this once read was described in the settings panel as a GENERATION
    # policy -- "what happens, not who gets to know it" -- while what it
    # actually gated was whether the player was told. The event fired either
    # way, so the switch could only ever hide a fact the world had already
    # committed. The ladder is retired; the telling is not a setting, and the
    # parameter that carried it is gone with it (review 2026-11-01,
    # world_offscreen_time F13: it was passed `True` by its one caller).
    event_ops, notices, counts, pending_arrivals = _fire_due_events(
        scene, elapsed, frame_id, pending or [],
        turn_idx=turn_idx, player_room=player_room,
        town=town, presence_rooms=presence_rooms)

    # (b) schedule new arrivals.
    schedule_ops, scheduled = _schedule_new_arrivals(
        scene, elapsed, frame_id, pending_arrivals,
        chat_id, turn_id, turn_idx)
    event_ops.extend(schedule_ops)

    # (c1) conditions that act while they last, then (c2) condition expiry.
    # Ticks FIRST so a row's last due tick lands before the clock closes it.
    tick_ops, tick_notices = _tick_conditions(scene, conditions, elapsed)
    event_ops.extend(tick_ops)
    notices.extend(tick_notices)
    event_ops.extend(_expire_conditions(conditions, elapsed))

    # (d) dock-edge recompute: an arrival changed the inputs the dock-edge
    # rewrite derives doorways from; recompute before the scene persists.
    if counts["fired"]:
        apply_transit_dock_edges(scene)

    # (e) vehicle-zone inference (idempotent; also applied at preparation
    # time -- see the module docstring). There is no companion carry: a mind
    # goes only where its own declaration takes it (`commit_scene_state`
    # says what the carry did and why it went).
    if prev_scene is not None and chat_id is not None:
        infer_vehicle_zones(chat_id, frame_id, prev_scene, scene)

    return scene, event_ops, notices, counts
