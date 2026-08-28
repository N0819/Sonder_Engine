"""Socially temporary facts about a body: what it is right now that it was not.

``docs/guides/RESEARCH.md`` §1.7.6 item 4. Comme il Faut keeps permanent
traits and TEMPORARY STATUS side by side, and this package had needs, felt
state, a service tally and nothing socially temporary at all — no newly
raised, no lately helped, no accused to your face, no in disgrace. Those are
what make a beat read as motivated rather than merely caused: a body acts
differently in the week after something happened to it, and the institution
spends it differently in the week after it was held responsible.

WHICH WORD MEANS WHAT, because this package already has three near neighbours
and a fourth spelling of the same idea is how it gets hurt:

  * ``politics.standing`` is PERMANENT rank — what a body is worth to the
    institution generally, and it never decays.
  * ``politics.blame`` is a MONOTONE counter — how many times a failure was
    attached to this body, ever. It is the institution's ledger and it does
    not forget.
  * ``charter_decide``'s per-order ``status`` is one ORDER's lifecycle, not a
    person's.
  * a **mark**, here, is a fact about a PERSON that expires. The counter says
    it happened; the mark says it happened RECENTLY, and only the mark
    reaches a decision.

TWO INVARIANTS THIS MODULE EXISTS TO HOLD.

  * **A mark store is bounded by bodies x MARKS and is pruned at expiry.**
    One row per (body, kind): a re-trigger overwrites ``since`` rather than
    appending, and ``advance_marks`` drops every row older than its kind's
    lifetime before it folds new ones in. So the store grows with the shape
    of the institution and never with time, which is the bound
    ``charter_run``'s docstring holds the event log to and which this package
    has now lost in three places by writing a row per window. A mark set and
    never touched again is gone within its lifetime whether or not anybody
    reads it.
  * **Body scope is an ALLOWLIST, and it is an allowlist because getting it
    wrong is a leak.** ``BODY_MARKS`` names the marks whose origin the marked
    body was PRESENT FOR — it was handed the duty, somebody tended it in the
    room, somebody said the accusation to its face. ``disgraced`` is the
    register's own mark: ``charter_politics.attribute_blame`` follows the
    watch the charter BELIEVED it had arranged, so a body can be disgraced
    for a post it was never at and there is no channel by which it would
    learn. It reaches the institution's planner and the author's diagnostic
    and nothing else. Listing what MAY cross rather than what may not is the
    same discipline ``charter_news.WITNESSABLE`` is held to, for the same
    reason: a new mark added tomorrow is register-scoped until somebody
    argues it into the list.

COST, AND THE READ IS THE HALF THAT MATTERED. ``advance_marks`` is one dict
pass over the bodies per window; measured on ``big_town(40)`` over a simulated
year (window 4.0, seed 3) with the WRITER swapped for a no-op and the arms
strictly interleaved in one process, 23.64/23.67 s live against 22.71/23.16 s
inert, against the 5 % gate this package uses.

That measurement left the expensive half live in both arms. ``held_marks`` is
read once per body per window by ``charter_run.step``'s reluctance loop, and
it used to answer by normalizing the WHOLE store and then indexing one key --
so the loop cost bodies x marked-bodies every window, which is the
quadratic-in-the-crowd class ``CO_PRESENCE_WIDTH`` exists to prevent, and it
was invisible at 40 bodies. Measured 2026-08-27 on ``big_ship(500)`` at 240 h,
strictly interleaved against a one-row lookup: 18.25/18.41 s against
15.71/15.63 s, +17 %. Fixed by ``_normalize_row``; the property is asserted as
a call count rather than a wall clock by
``test_reading_one_bodys_marks_does_not_walk_the_whole_store``, and
``tools/charter_audit_scale.py`` holds the run-level bound.

Imports nothing from the ``world`` package — it carries its own ``_number`` —
so ``charter_model`` may import ``normalize_marks`` at module scope the way it
already imports ``charter_figure.normalize_figures``.
"""

from __future__ import annotations

#: The four socially temporary facts, each with an origin that already exists
#: in `charter_run.step`. Ordered as the design ranks them; iteration order is
#: fixed so the fold below is deterministic.
MARKS = ("posted", "aided", "accused", "disgraced")

#: The marks a body may be told it holds — see the allowlist paragraph above.
#: `disgraced` is deliberately absent and its absence is the firewall.
BODY_MARKS = frozenset({"posted", "aided", "accused"})

#: The marks that name WHO. `by` is the person who acted on this body in front
#: of it, which is that body's own record of its own encounter, exactly as
#: `charter_promote.acquainted` treats its own co-presence count. `posted` has
#: no `by` (the institution is not a person here) and `disgraced` must not
#: have one — naming the blamer would hand the register's own reasoning to a
#: reader that already may not have the fact.
BY_MARKS = frozenset({"aided", "accused"})

#: How long each mark stays true. Set from the held FRACTION each produces,
#: because the failure mode of a temporary trait is not that it decays too
#: fast, it is that most of the institution holds it at once and it stops
#: distinguishing anybody. Measured on `big_town(40)` over a simulated year
#: (window 4.0, seed 3) and on `twin_towns(240)` driven into famine for a
#: simulated month (window 4.0, seed 7):
MARK_HOURS = {
    # FIRST TIME AT A POST, not every window of standing it: the onset gate in
    # `charter_run` fires only where `stood[body][post]` was 0. Three days is
    # about how long a new duty is still new. Measured across 2,190 windows of
    # `big_town(40)`, healthy simulated year, window 4.0, seed 3: 13 of 40
    # bodies ever marked, 0.31% of (body, window) pairs holding it, and the
    # store EMPTY at the end of the year. The peak of 32.5% is the first
    # window of the institution's life, when the whole bill is handed out at
    # once and everybody genuinely is newly raised. On `twin_towns(240)`
    # driven into famine for a simulated month: 48 of 240 ever, 2.31% mean.
    "posted": 72.0,
    # SOMEBODY TENDED YOU. The favour that is still owed, and the shortest of
    # the four because being helped off the floor is the most local of them.
    # The busiest of the four and the one that had to be checked hardest
    # against "a mark most of the institution holds is not a mark": measured
    # on `big_town(40)` with needs seeded over a simulated year, 804
    # `aid_given` acts, 12.39% mean held and a peak of 6 of 40 -- six bodies
    # that keep going down, not a town of invalids.
    "aided": 48.0,
    # SOMEBODY SAID IT TO YOUR FACE. The longest of the three body marks: an
    # accusation heard is the one of these a person is still carrying a week
    # later, and `heard_blame` -- which is monotone and never forgets -- is
    # exactly the store this is the recency half of.
    "accused": 168.0,
    # THE INSTITUTION'S OWN. Two weeks, and longer than anything the body
    # feels, because a register outlasts a mood: the books hold a fresh
    # failure against you for a fortnight of rostering and then stop. The
    # counter in `politics.blame` still says it happened, forever.
    "disgraced": 336.0,
}

#: What a fresh disgrace adds to the planner's reluctance to spend a body.
#: THE AXIS `charter_politics.spend_reluctance` ALREADY OCCUPIES: a disgraced
#: body becomes EXPENSIVE, never unpostable, so a short-handed charter still
#: posts it. Sized against `STANDING_WEIGHT` (1.0 x standing, and authored
#: standings in this repo's fixtures sit at 0 to 2) and set by
#: `test_a_disgraced_body_is_spent_later_and_is_still_spent_when_it_must_be`.
#:
#: SET AGAINST `pressure`, because that is what it actually trades against.
#: The planner's first sort component is `criticality + standing + pressure +
#: disgrace`, so the size of this number is not "how much shame" -- it is the
#: exhaustion at which the institution stops preferring a clean hand. Measured
#: on a two-body works fixture, one rested body carrying a fresh disgrace
#: against one clean body worn down by degrees: at 0.3 the disgraced hand is
#: back on the bill once the clean one reaches need level 0.6; at 0.9 the
#: institution never reaches for it at all, working the clean hand down to 0.2
#: and the edge of collapse, which is an institution that would rather break
#: somebody than re-post the person it blamed last week. At 0.6 it spends the
#: disgraced hand rather than one more than about sixty per cent spent.
#:
#: AND BELOW 1.0 ON PURPOSE. `criticality` contributes whole numbers to the
#: same component, so anything at or above 1.0 would let a disgrace outweigh
#: being the last body qualified for some other post -- the exact failure
#: `criticality`'s docstring exists for, arriving by a new road.
DISGRACE_RELUCTANCE = 0.6


def _number(value, default=0.0):
    """A stored number, or the caller's default. Local on purpose — this
    module imports nothing from the package (see the docstring)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_marks(stored, bodies=None):
    """``{body: {kind: {"since": float, "by": str?}}}`` from any shape.

    ``bodies`` filters to the live roster exactly as `experiences` and
    `habit_runs` are filtered, so a body that leaves the charter cannot leave
    a mark behind. An unknown kind is dropped rather than carried: the
    vocabulary is `MARK_HOURS`, and a row whose kind has no lifetime could
    never expire.
    """
    out = {}
    for key, held in (stored or {}).items():
        key = str(key)
        if bodies is not None and key not in bodies:
            continue
        rows = _normalize_row(held)
        if rows:
            out[key] = rows
    return out


def _normalize_row(held):
    """One body's rows, normalized. The unit `normalize_marks` is built from.

    Split out because `held_marks` wants exactly this and used to get it by
    normalizing the WHOLE store and then indexing one key -- so the planner's
    per-body reluctance read in `charter_run.step` cost bodies x marked-bodies
    every window, which is the quadratic-in-the-crowd class `CO_PRESENCE_WIDTH`
    exists to prevent. Measured 2026-08-27, strictly interleaved in one
    process against a one-row lookup: `big_ship(500)` at 240 h 18.25/18.41 s
    against 15.71/15.63 s (+17%), `big_town(1000)` at 240 h +7.7% with only
    20-110 mark holders, and the loop alone microbenched at 1.358 s per window
    with 1,000 bodies marked. Against a 5% gate.
    """
    if not isinstance(held, dict):
        return {}
    rows = {}
    for kind, entry in held.items():
        kind = str(kind)
        if kind not in MARK_HOURS or not isinstance(entry, dict):
            continue
        row = {"since": _number(entry.get("since"), 0.0)}
        by = str(entry.get("by") or "")
        if by and kind in BY_MARKS:
            row["by"] = by
        rows[kind] = row
    return rows


def _onset(item):
    """``(body, by)`` from either a bare body key or a ``(body, by)`` pair."""
    if isinstance(item, (tuple, list)):
        if not item:
            return "", ""
        return str(item[0] or ""), str(item[1] or "") if len(item) > 1 else ""
    return str(item or ""), ""


def advance_marks(marks, at_hours, *, posted=(), aided=(), accused=(),
                  disgraced=()):
    """Prune what has lapsed, fold in what happened. ``(marks, fresh)``.

    PRUNE FIRST, THEN FOLD, so a mark re-triggered in the same window it would
    have expired stays held rather than blinking off and on. ``fresh`` is the
    ``(body, kind, by)`` rows set or refreshed by THIS call, sorted — it is
    what a live reader appraises, and the only thing `charter_feel` may see.
    Deliberately not the whole store: appraising a standing 168-hour mark
    every window is the failure the comment at `charter_feel.advance_feel`
    records, where a residual appraisal left 240 bodies carrying strain 0.09
    after 480 quiet hours.

    Onsets are sorted here rather than trusted from the caller. `heard_blame`
    is a dict of SETS and `politics.blame` a dict, so an unsorted onset list
    would let two accusers in one window race for the same row and a
    checkpoint restore would land a different past — the byte-identical
    replay `tests/test_charter_run.py` TestReplay pins.
    """
    at = _number(at_hours, 0.0)
    out = {}
    for body, held in normalize_marks(marks).items():
        kept = {kind: dict(entry) for kind, entry in held.items()
                if at - _number(entry.get("since")) < MARK_HOURS[kind]}
        if kept:
            out[body] = kept

    # Keyed by (body, kind) rather than appended, which is the one-row-per-pair
    # bound doing its work: two people tending the same body in one window
    # leave one mark, not two, and `fresh` says exactly what the store says.
    minted = {}
    for kind, onsets in (("posted", posted), ("aided", aided),
                         ("accused", accused), ("disgraced", disgraced)):
        for body, by in sorted(_onset(item) for item in (onsets or ())):
            if not body:
                continue
            row = {"since": at}
            if by and kind in BY_MARKS:
                row["by"] = by
            out.setdefault(body, {})[kind] = row
            minted[(body, kind)] = row.get("by", "")
    fresh = sorted((body, kind, by) for (body, kind), by in minted.items())
    return out, fresh


def held_marks(marks, body, at_hours=None):
    """``{kind: entry}`` this body currently holds.

    ``at_hours`` filters lapsed rows for a reader that is not the writer. The
    store `advance_marks` returns is already pruned as of the window it ran
    in, so a same-window reader may omit it; a surface read at an arbitrary
    later hour must not.
    """
    # INDEX FIRST, NORMALIZE ONE ROW. See `_normalize_row`: this is read once
    # per body per window by the planner, so normalizing the whole store here
    # made the reluctance loop quadratic in the crowd.
    held = _normalize_row((marks or {}).get(str(body)))
    if at_hours is None:
        return held
    at = _number(at_hours, 0.0)
    return {kind: entry for kind, entry in held.items()
            if at - _number(entry.get("since")) < MARK_HOURS[kind]}


def mark_view(marks, body, at_hours):
    """This body's own marks, as rows something could say out loud.

    ``[{"mark", "by"?, "hours_ago"}]``, BODY SCOPE ONLY. The filter is by
    membership in `BODY_MARKS` rather than by a caller remembering to drop
    `disgraced`, which is what makes the register mark unreachable from this
    surface by construction instead of by discipline.
    """
    at = _number(at_hours, 0.0)
    out = []
    for kind, entry in sorted(held_marks(marks, body, at).items()):
        if kind not in BODY_MARKS:
            continue
        row = {"mark": kind,
               "hours_ago": round(at - _number(entry.get("since")), 1)}
        if entry.get("by"):
            row["by"] = entry["by"]
        out.append(row)
    return out
