"""The charter's attempt: rank the posts, staff them, report what it could not.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §4. This module is the whole
thesis in one function -- **simulate the attempt, never the outcome.** Nothing
here decides whether the ship runs. It decides who the institution TRIED to put
where, and what it knew it was leaving uncovered.

The unfilled list is not an error path. It is the product. A charter that fills
every post produces a world that runs and a story that says nothing; the gap
between what the institution wants and the bodies it believes it has is the
entire dramatic yield, and it is a first-class return value for that reason.

Pure: no clock, no writes, no randomness beyond the caller's seed.
"""

from __future__ import annotations

import zlib

from .charter_drift import urgency
from .charter_model import priority_rank
from .charter_roster import assignable


def _post_urgency(post, charter, ranks, horizon_hours):
    """A post is as urgent as the most urgent thing it serves.

    A post serving nothing sorts last rather than being dropped: an authored
    post with no ``serves`` is far more likely to be an unfinished sheet than
    a deliberate sinecure, and staffing it harmlessly is a better failure than
    silently ignoring it.
    """
    best = None
    for key in post["serves"]:
        upkeep = charter["upkeeps"].get(key)
        if upkeep is None:
            continue
        score = urgency(upkeep, ranks.get(key, len(ranks)), horizon_hours)
        if best is None or score > best:
            best = score
    return best if best is not None else (-len(ranks) - 1, 0.0)


def criticality(charter, roster=None):
    """``{body: how many posts it is the ONLY assignable body for}``.

    THE DEFECT THIS EXISTS FOR, measured on the town fixture's first run: a
    fully staffed town starved its own shop on day two. The highest-priority
    post took the alphabetically-first capable body, which happened to be the
    only one holding the trade tag, and the counter then had nobody -- while
    three bodies whose only competence was general labour stood available.

    No institution does that. A chief does not put the only rated engineer on
    a job any hand could do. So candidates are ranked by what spending them
    COSTS ELSEWHERE: a body nobody else can replace at some other post is
    spent last, and the most replaceable body is spent first.
    """
    roster = charter["roster"] if roster is None else roster
    only = {}
    for post in charter["posts"].values():
        candidates = assignable(roster, post["requires"])
        if len(candidates) == 1:
            only[candidates[0]] = only.get(candidates[0], 0) + 1
    return only


def plan_watch(charter, horizon_hours=4.0, seed=0, reach=None,
               reluctance=None):
    """One planning window: ``{post_key: body_key}`` plus what went unfilled.

    A body holds at most one post per window. Where two posts want the same
    body the more urgent one takes it and the other is reported unfilled with
    ``contended`` -- which is the shape of every short-handed institution and
    the thing an author most wants to be able to read back.

    ``seed`` only breaks ties between equally-urgent posts, so a replay with
    the same seed produces the same watch and a different seed produces a
    different-but-legitimate one. Nothing here is otherwise random.
    """
    ranks = priority_rank(charter)
    posts = list(charter["posts"].values())
    posts.sort(
        key=lambda p: (_post_urgency(p, charter, ranks, horizon_hours),
                       # Stable, total, and seed-varied: the key is hashed
                       # with the seed rather than drawn, so the order is a
                       # pure function of (charter, seed) and replays exactly.
                       # crc32 rather than hash(): Python salts string hashes
                       # per PROCESS, and a checkpoint restore is a different
                       # process -- with hash() the tie-break order survived
                       # a same-process replay test and would not have
                       # survived the restart the test exists to stand for.
                       -(zlib.crc32(f"{p['key']}|{int(seed)}"
                                    .encode("utf-8")) & 0xFFFF)),
        reverse=True)

    scarce = criticality(charter)
    reluctance = reluctance or {}
    watch = {}
    unfilled = []
    taken = set()
    for post in posts:
        candidates = [b for b in assignable(charter["roster"], post["requires"])
                      if b not in taken]
        if reach is not None:
            # A body that cannot get to the post within the window is not a
            # candidate for it. Without this a five-hundred-hand ship rosters
            # by competence alone and produces a watch bill nobody could
            # physically stand.
            candidates = [b for b in candidates
                          if (b, post["place"]) in reach]
        # Spend the most replaceable body first, and the nearest of the
        # equally replaceable. `assignable` has already ordered by belief
        # strength; re-ordering by what a body is uniquely needed for
        # elsewhere takes precedence over that, because a confident belief
        # about the wrong person to spend is still the wrong person. Standing
        # rides on the same axis: a body the institution is reluctant to spend
        # is treated as scarcer than their competence alone implies.
        candidates.sort(key=lambda b: (
            scarce.get(b, 0) + float(reluctance.get(b, 0.0)),
            (reach or {}).get((b, post["place"]), 0),
            b))
        if not candidates:
            # Three distinct stories, and an author reading the log has to be
            # able to tell them apart: nobody can do this at all, somebody can
            # but is already standing a more urgent post, or somebody can and
            # is simply too far away to get there this window.
            any_capable = assignable(charter["roster"], post["requires"])
            if not any_capable:
                reason = "no_competence"
            elif reach is not None and not any(
                    (b, post["place"]) in reach for b in any_capable):
                reason = "out_of_reach"
            else:
                reason = "contended"
            unfilled.append({
                "post": post["key"],
                "place": post["place"],
                "serves": list(post["serves"]),
                "reason": reason,
            })
            continue
        watch[post["key"]] = candidates[0]
        taken.add(candidates[0])

    return {"watch": watch, "unfilled": unfilled}


def tended_upkeeps(charter, watch):
    """Which upkeeps actually get service under this watch.

    THE POINT AT WHICH BELIEF MEETS THE WORLD. The charter assigned from its
    roster; here the body's real ``available`` decides whether anybody is
    actually standing there. A post staffed with someone who is in fact absent
    tends nothing, and the charter does not find out until somebody looks.
    """
    served = set()
    for post_key, body_key in (watch or {}).items():
        body = charter["bodies"].get(body_key)
        if body is None or not body["available"]:
            continue
        post = charter["posts"].get(post_key)
        if post is None:
            continue
        for key in post["serves"]:
            if key in charter["upkeeps"]:
                served.add(key)
    return served
