"""Situations, and the actions a situation makes available.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md``. Modelled on Versu's social
practices (Evans & Short, *IEEE TCIAIG* 6(2), 2014), and adopted because the
prototype had the failure that architecture exists to prevent.

THE MEASUREMENT THAT SENT US LOOKING. A hundred beats of a two-town
simulation produced 103 interactions, and **every one of them fell in the
first nine beats**; 91 consecutive beats recorded nothing at all. The
population had met itself and had nothing further to do, because the only
thing that could happen between two bodies was passing a claim, and a claim
passes only when it arrives stronger than what the listener already holds.
After saturation nothing does. Personal decay eventually reopens the door --
at the measured rates, in about a hundred and sixty beats -- which is a world
that comes back to life roughly once a week and is not alive in between.

THE FIX, in Versu's terms: **affordances come from the situation, not from
the agent.** A practice is a recurring social situation; its job is to
describe the actions its participants may take. It never controls anybody --
it offers, and each body chooses on its own utility. Two properties make the
loop self-sustaining, and both are load-bearing here:

  * **Practices run concurrently and options are their UNION.** A body in a
    conversation, standing a post, and nursing a grievance has all three
    sets of affordances at once.
  * **Acting spawns practices.** Greeting somebody opens a conversation;
    somebody collapsing opens a tending; blame landing opens a quarrel. The
    system cannot run dry because doing a thing creates the next situation.

WHAT KEEPS IT GENRE-NEUTRAL. The practice KINDS here are as universal as the
concepts the engine already owns -- contact, evidence, authority. Meeting
somebody you have not met, attending somebody who has collapsed, falling out
with somebody who blamed you: none of those names a genre, and a lorebook
supplies what they are called and what is said. No noun in this module comes
from any fixture.

Pure and deterministic: no clock beyond what it is handed, no model, no
randomness beyond the caller's seed.
"""

from __future__ import annotations

import zlib

from .charter_mind import PERSONAL_FLOOR, hear, see
from .charter_talk import RETOLD_RETENTION, co_present

#: Practices one body may hold at once. Past this the oldest is dropped: a
#: body carrying twenty simultaneous situations is a bookkeeping artifact, not
#: a person, and unbounded practice sets are how this becomes quadratic.
PRACTICE_CAP = 4

#: A conversation with nothing left to say closes after this many hours of
#: producing no effect. Practices must be able to END or they accumulate,
#: and a stale practice offering affordances nobody takes is exactly the
#: "storage grows with time" failure in another costume.
IDLE_CLOSE_HOURS = 2.0

#: How much of a claim's strength an ASKED answer carries. Higher than an
#: unprompted telling: somebody who asked is listening.
ASKED_RETENTION = 0.75


def _roll(*parts):
    """Deterministic 0..1 from any key. crc32, never `hash()` -- Python salts
    string hashing per process, and a checkpoint restore is a different one."""
    return (zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))
            & 0xFFFF) / 65535.0


def normalize_practices(stored):
    out = {}
    for key, entry in (stored or {}).items():
        if isinstance(entry, dict) and entry.get("kind"):
            out[str(key)] = dict(entry)
    return out


def _open(kind, place, roles, at_hours, about=""):
    key = f"{kind}:{':'.join(sorted(roles.values()))}:{about}"
    return key, {
        "key": key, "kind": str(kind), "place": str(place),
        "roles": dict(roles), "about": str(about),
        "opened_at": float(at_hours), "last_effect_at": float(at_hours),
    }


# --------------------------------------------------------------- affordances
#
# Each returns (utility, effect) where effect(state) mutates and returns a
# short description, or None when the affordance is unavailable. Utility is
# a pure function of state the actor may legitimately read -- its own needs,
# its own claims, its own regard. Never another body's interior.

def _afford_greet(actor, other, practice, state):
    if (state["minds"].get(actor) or {}).get(other):
        return None
    body = state["bodies"].get(other)
    if body is None:
        return None

    def effect():
        see(state["minds"], actor, body, state["at"])
        spawn = _open("converse", practice["place"],
                      {"a": actor, "b": other}, state["at"])
        state["spawned"].append(spawn)
        return f"{actor} greeted {other}"

    # Meeting somebody unknown outranks almost anything: it is the only
    # affordance that creates a relationship where there was none.
    return 0.9, effect


def _afford_ask(actor, other, practice, state):
    """Ask about somebody your picture of has gone thin.

    THE AFFORDANCE THAT MAKES THE LOOP RENEWABLE, and the one the old gossip
    could not express. Telling fires only when the speaker's claim beats the
    listener's, so a saturated population goes silent. Asking fires on the
    ASKER'S OWN GAP, which decay reopens continuously -- so there is always
    something somebody wants to know, without anything new having happened.

    Firewall-clean: the asker does not know what the other holds. It asks;
    what comes back is whatever the other actually has, or nothing.
    """
    mine = state["minds"].get(actor) or {}
    theirs = state["minds"].get(other) or {}
    gaps = [(float(mine.get(s, {}).get("strength", 0.0)), s)
            for s in theirs if s not in (actor, other)]
    if not gaps:
        return None
    weakest, subject = min(gaps)
    if weakest > 0.75:
        return None

    def effect():
        if hear(state["minds"], actor, other, subject, ASKED_RETENTION,
                state["regard"].get((actor, other), 1.0)):
            return f"{actor} asked {other} about {subject}"
        return ""

    return 0.35 + (1.0 - weakest) * 0.3, effect


def _afford_tell(actor, other, practice, state):
    mine = state["minds"].get(actor) or {}
    candidates = [(float(c.get("strength") or 0.0), s)
                  for s, c in mine.items() if s not in (actor, other)]
    if not candidates:
        return None
    strength, subject = max(candidates)
    if strength < PERSONAL_FLOOR:
        return None

    def effect():
        if hear(state["minds"], other, actor, subject, RETOLD_RETENTION,
                state["regard"].get((other, actor), 1.0)):
            return f"{actor} told {other} about {subject}"
        return ""

    return 0.25 + strength * 0.2, effect


def _afford_tend(actor, other, practice, state):
    """Attend somebody who has gone down. Services their worst need."""
    held = (state["needs"] or {}).get(other) or {}
    if not held:
        return None
    worst = min(held.values(), key=lambda n: float(n["level"]) -
                float(n["floor"]))
    gap = float(worst["floor"]) - float(worst["level"])
    if gap <= 0.0:
        return None

    def effect():
        worst["level"] = min(1.0, float(worst["level"]) + 0.05)
        see(state["minds"], actor, state["bodies"][other], state["at"])
        return f"{actor} tended {other} ({worst['key']})"

    # Somebody in front of you and under their floor outranks conversation.
    return 0.8 + min(0.2, gap), effect


def _afford_accuse(actor, other, practice, state):
    """Say aloud that you hold somebody responsible.

    Blame already exists as an institutional fact; until now it reached
    nobody. This is its channel: the accused LEARNS they are blamed, which is
    the gap Fable's report left open.
    """
    if int(state["blame"].get(other, 0)) <= 0:
        return None
    pair = (actor, other)
    if state["regard"].get(pair, 1.0) < 0.45:
        return None

    def effect():
        state["regard"][pair] = max(0.3, state["regard"].get(pair, 1.0) - 0.1)
        state["heard_blame"].setdefault(other, set()).add(actor)
        spawn = _open("quarrel", practice["place"],
                      {"a": actor, "b": other}, state["at"], about=other)
        state["spawned"].append(spawn)
        return f"{actor} accused {other}"

    return 0.55 + min(0.3, 0.1 * int(state["blame"].get(other, 0))), effect


def _afford_reconcile(actor, other, practice, state):
    pair = (actor, other)
    if state["regard"].get(pair, 1.0) >= 1.0:
        return None
    if state["at"] - float(practice["opened_at"]) < 12.0:
        return None

    def effect():
        state["regard"][pair] = min(1.0, state["regard"].get(pair, 1.0) + 0.08)
        state["closed"].append(practice["key"])
        return f"{actor} made peace with {other}"

    return 0.4, effect


_AFFORDANCES = {
    "greeting": (_afford_greet,),
    "converse": (_afford_ask, _afford_tell, _afford_greet),
    "tending": (_afford_tend, _afford_ask),
    "quarrel": (_afford_accuse, _afford_reconcile),
}


def opportunities(bodies, minds, needs, events, practices, at_hours, seed=0):
    """Practices the world has just made available. Returns new instances.

    Situations are OPENED BY CIRCUMSTANCE, not by anybody deciding to have
    one: two strangers in a room, somebody on the floor, a blame that has
    landed. That is what makes them a renewable source of things to do.
    """
    opened = {}
    rooms = co_present(bodies)
    for place, present in sorted(rooms.items()):
        able_here = [k for k in present if bodies[k].get("available")]
        for index, actor in enumerate(able_here):
            for other in able_here[index + 1:index + 3]:
                known = (minds.get(actor) or {}).get(other)
                kind = "converse" if known else "greeting"
                key, entry = _open(kind, place, {"a": actor, "b": other},
                                   at_hours)
                if key not in practices:
                    opened[key] = entry
        # Somebody under their floor, and anybody able standing over them.
        for subject in present:
            held = (needs or {}).get(subject) or {}
            if not held or bodies[subject].get("available"):
                continue
            for carer in able_here[:2]:
                key, entry = _open("tending", place, {"a": carer, "b": subject},
                                   at_hours, about=subject)
                if key not in practices:
                    opened[key] = entry
    return opened


def enact(bodies, minds, needs, practices, regard, blame, at_hours, seed=0):
    """One beat of everybody choosing. Returns ``(lines, spawned, closed)``.

    Each body's options are the UNION of the affordances of every practice it
    participates in; it takes the highest-utility one and no more, so a beat
    is one act per person. Ties break on a seeded crc32 of the pair, which
    keeps a replay identical without making the choice arbitrary.
    """
    state = {
        "bodies": bodies, "minds": minds, "needs": needs, "regard": regard,
        "blame": blame, "at": float(at_hours),
        "spawned": [], "closed": [], "heard_blame": {},
    }
    by_body = {}
    for practice in practices.values():
        for role, key in practice["roles"].items():
            by_body.setdefault(key, []).append((role, practice))

    lines = []
    for actor in sorted(by_body):
        body = bodies.get(actor)
        if body is None or not body.get("available"):
            continue
        best = None
        for role, practice in by_body[actor][:PRACTICE_CAP]:
            other = next((v for r, v in practice["roles"].items()
                          if r != role), None)
            if other is None or other == actor:
                continue
            for build in _AFFORDANCES.get(practice["kind"], ()):
                offer = build(actor, other, practice, state)
                if offer is None:
                    continue
                utility, effect = offer
                jitter = _roll(actor, other, practice["kind"], seed) * 0.02
                if best is None or utility + jitter > best[0]:
                    best = (utility + jitter, effect, practice)
        if best is None:
            continue
        line = best[1]()
        if line:
            lines.append(line)
            best[2]["last_effect_at"] = float(at_hours)

    return lines, state["spawned"], state["closed"], state["heard_blame"]


def close_stale(practices, at_hours):
    """Practices that have produced nothing for a while. Returns survivors.

    A situation nobody is acting in is over, whatever its participants
    believe. Without this the practice set only grows.
    """
    return {
        key: entry for key, entry in (practices or {}).items()
        if float(at_hours) - float(entry.get("last_effect_at") or 0.0)
        < IDLE_CLOSE_HOURS
    }
