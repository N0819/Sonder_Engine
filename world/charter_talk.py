"""Gossip: how an institution's beliefs about its own people actually form.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §5. NOT A BOLT-ON. The
charter has never had ground truth about its crew — it reads a roster of
claims — and until now those claims were only refreshed by a body standing a
post. That makes an institution that knows nothing it did not personally
witness, which is not an institution, it is a supervisor with no colleagues.

Gossip is the missing channel, and it is the ordinary one: people who are in
the same place talk, and most of what a chief believes about a hand they have
never worked beside came from somebody else. So a claim now travels, and it
degrades on the way, which is what makes the roster interestingly wrong rather
than merely stale.

Three rules, all of them deliberate:

  * **Co-presence gates it.** Only bodies in the same place exchange anything.
    No timer grants knowledge and no charter-wide broadcast exists, which is
    the same shape ``story/carriers.py`` holds for reports.
  * **A telling is weaker than a seeing.** A claim arrives at a fraction of
    the teller's own confidence, so a fact three mouths from its source is
    already thin — and thin claims fall under ``TRUST_FLOOR`` and stop being
    staked on, which is exactly right.
  * **Regard scales belief.** Who you believe is a political fact, and it
    lives in ``charter_politics``. This module asks for a weight and does not
    care where it came from.
"""

from __future__ import annotations

from .charter_mind import hear, see
from .charter_roster import TRUST_FLOOR

#: What a claim retains when retold. A seeing is 1.0; hearing it once makes it
#: 0.6, twice 0.36, three times 0.216 — under the trust floor by the fourth
#: mouth. That decay IS the rumour horizon, and it is why an institution's
#: knowledge of itself is local without anything having to enforce locality.
RETOLD_RETENTION = 0.6

#: Partners any one body talks to in a window. Capped because the pairwise
#: work is the only part of this package that could go quadratic: a mess deck
#: holding two hundred people is 19,900 pairs, and none of the resulting talk
#: would be more informative than a handful of it. Talk of the Town amortised
#: the same problem rather than bounding it; bounding is cheaper and the loss
#: is unobservable.
PARTNERS_PER_WINDOW = 2


def _rotate(seq, by):
    if not seq:
        return seq
    by %= len(seq)
    return seq[by:] + seq[:by]


def co_present(bodies, speaking=False):
    """``{place: [body keys]}``, sorted.

    BEING SEEN AND BEING ABLE TO SERVE ARE DIFFERENT THINGS, and collapsing
    them cost the model its only route to disagreement. `available` means a
    body can stand a post; it does not mean the body has left the world. A
    hand laid up in a sickbay is still in the sickbay, and the people around
    them can see perfectly well that they are laid up.

    While absent bodies were filtered out of every room, nothing anywhere
    could learn that somebody had gone down: their claim was never refreshed,
    so every head went on holding the last accurate thing it knew and all
    those claims agreed. Measured — thirty hands taken out of a five-hundred
    crew, two simulated days later, contested bodies: zero. The institution
    had no channel by which bad news about a person could travel at all.

    ``speaking`` narrows to the bodies that can actually hold a conversation.
    """
    rooms = {}
    for key in sorted(bodies or {}):
        body = bodies[key]
        if speaking and not body.get("available"):
            continue
        place = str(body.get("place") or "")
        if place:
            rooms.setdefault(place, []).append(key)
    return rooms


def pair_up(bodies, seed=0):
    """Who talks to whom this window. Deterministic given ``(bodies, seed)``.

    Rotating the room's own membership by the seed rather than drawing pairs
    keeps this a pure function — the same seed rebuilds the same conversations
    on a replayed window, which is what checkpoint restore needs and what a
    random draw could not give.
    """
    pairs = []
    for place, present in sorted(co_present(bodies, speaking=True).items()):
        if len(present) < 2:
            continue
        partners = _rotate(present, int(seed) + 1)
        for index, speaker in enumerate(present):
            for offset in range(PARTNERS_PER_WINDOW):
                listener = partners[(index + offset) % len(partners)]
                if listener != speaker:
                    pairs.append((speaker, listener, place))
    return pairs


def witnessed(bodies, seed=0):
    """``[(subject, watcher, place)]`` — who is in a position to see whom.

    Every body with a place can be SEEN, including one who cannot stand a
    post; only bodies who can serve do the watching. Bounded the same way
    conversation is, because a compartment holding two hundred people does
    not produce two hundred useful observations of each of them.
    """
    seen = []
    for place, present in sorted(co_present(bodies).items()):
        watchers = [k for k in present if bodies[k].get("available")]
        if not watchers:
            continue
        rotated = _rotate(watchers, int(seed) + 1)
        for index, subject in enumerate(present):
            for offset in range(PARTNERS_PER_WINDOW):
                watcher = rotated[(index + offset) % len(rotated)]
                if watcher != subject:
                    seen.append((subject, watcher, place))
    return seen


def converse(minds, bodies, seed=0, regard=None, at_hours=0.0):
    """One window of talk, per head. Returns ``(minds, told_count)``.

    Two things happen when two bodies share a room, and they are different
    kinds of knowing:

      * **They see each other.** First-hand, full strength, accurate. This is
        the only way an accurate claim enters a head.
      * **They talk about somebody else.** The speaker passes on its own
        strongest claim about a THIRD party, thinned by `RETOLD_RETENTION`
        and scaled by what the listener thinks of the speaker. That is the
        channel that lets a body know about people it has never met, and the
        channel by which the institution comes to believe things that are not
        so.

    A speaker offers the claim it holds most strongly, not a random one:
    people repeat what they are surest of, and it makes the pass deterministic
    without a draw.
    """
    minds = {k: dict(v) for k, v in (minds or {}).items()}
    regard = regard or {}
    told = 0

    # Seeing first, and over everybody present rather than everybody able:
    # this is the only channel by which the fact that a body has gone down
    # ever enters a head.
    for subject, watcher, _place in witnessed(bodies, seed=seed):
        body = (bodies or {}).get(subject)
        if body is not None:
            see(minds, watcher, body, at_hours)

    for speaker, listener, _place in pair_up(bodies, seed=seed):
        held = minds.get(speaker) or {}
        candidates = [subject for subject in held if subject != listener]
        if not candidates:
            continue
        subject = max(
            candidates,
            key=lambda s: (float(held[s].get("strength") or 0.0), s))
        weight = float(regard.get((listener, speaker), 1.0))
        if hear(minds, listener, speaker, subject, RETOLD_RETENTION, weight):
            told += 1

    return minds, told


def report_up(roster, minds, watch, bodies, standing=None, at_hours=0.0):
    """What the watch tells the institution. Returns a new roster.

    The bodies actually standing posts are the ones the charter hears from, so
    what they believe is what reaches the register — weighted by their
    standing, because an institution does not weigh every voice alike. This is
    where per-head belief becomes institutional belief, and where a confident
    wrong opinion held by a well-regarded body becomes the roster's problem.
    """
    roster = {k: dict(v) for k, v in (roster or {}).items()}
    standing = standing or {}

    for body_key in sorted(set((watch or {}).values())):
        body = (bodies or {}).get(body_key)
        if body is None or not body.get("available"):
            continue
        voice = 1.0 + max(0.0, float(standing.get(body_key, 0.0)) * 0.1)
        for subject, claim in (minds.get(body_key) or {}).items():
            arriving = min(1.0, float(claim.get("strength") or 0.0) * voice)
            if arriving < TRUST_FLOOR:
                continue
            current = roster.get(subject)
            if current is not None \
                    and float(current.get("strength") or 0.0) >= arriving:
                continue
            record = dict(claim)
            record["strength"] = arriving
            record["as_of_hours"] = float(at_hours)
            record["heard_from"] = body_key
            roster[subject] = record
    return roster
