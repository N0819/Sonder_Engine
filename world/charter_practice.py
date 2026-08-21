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

TWO AUTHORS, ONE VOCABULARY. Versu's own line about player choice -- "the
same architecture is used for player choice, except the Action Instances are
sent directly to the user-interface, rather than to the Decision Maker" --
is §12a's author-switch, and it is built here rather than beside here:
``offers`` enumerates the affordances a participant currently has (the
action instances, for a scene manager to hand to a model or a player), and
``enact``'s ``conduct`` parameter lets an author name the act a body takes
this beat. An authored act runs the IDENTICAL builder and effect a chosen
one would; the machinery underneath cannot tell which author moved the body,
and an authored act outside what the state licenses is refused with a
notice, never applied and never silently dropped.

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

from .charter_figure import figure_claim
from .charter_mind import PERSONAL_FLOOR, hear, see
from .charter_talk import RETOLD_RETENTION, co_present, tellable

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
# its own claims, its own regard. Never another head's interior.
#
# EVERY AFFORDANCE IS GATED BY CO-PRESENCE, at act time, not merely at the
# moment the situation opened. A practice outlives the room it opened in by
# up to `IDLE_CLOSE_HOURS`, and the first version of this module let its
# affordances keep firing across that gap: two bodies who had parted could go
# on trading claims for a window, and -- measured directly -- a body in one
# room GREETED a body in another and minted a full-strength first-hand
# sighting through the wall. The situation remembers the pair; the WORLD
# decides whether they are still within speaking distance.
#
# A target may be a body or a FIGURE (`charter_figure`): the player or a
# major character standing in the room. A figure has no mind here and no
# needs, so `tend` and the answer half of `ask` never fire toward one -- the
# ordinary gates do that work, not a special case.

def _whereabouts(key, state):
    """Where a participant currently stands, or '' for nowhere reachable."""
    body = state["bodies"].get(key)
    if body is not None:
        return str(body.get("place") or "")
    figure = (state.get("figures") or {}).get(key)
    if figure is not None:
        return str(figure.get("place") or "")
    return ""


def _within_speech(actor, other, state):
    place = _whereabouts(actor, state)
    return bool(place) and place == _whereabouts(other, state)


def _afford_greet(actor, other, practice, state):
    if (state["minds"].get(actor) or {}).get(other):
        return None
    if not _within_speech(actor, other, state):
        return None
    body = state["bodies"].get(other)
    figure = (state.get("figures") or {}).get(other)
    if body is None and figure is None:
        return None

    def effect():
        if body is not None:
            see(state["minds"], actor, body, state["at"])
        else:
            # A figure is seen at the resolution a coarse witness has:
            # presence and public surface, nothing interior.
            state["minds"].setdefault(actor, {})[other] = figure_claim(
                figure, state["at"])
        spawn = _open("converse", practice["place"],
                      {"a": actor, "b": other}, state["at"])
        state["spawned"].append(spawn)
        return f"{actor} greeted {other}"

    # Meeting somebody unknown outranks almost anything: it is the only
    # affordance that creates a relationship where there was none.
    return 0.9, effect


def _afford_ask(actor, other, practice, state):
    """Ask about something your own picture of has gone thin.

    THE AFFORDANCE THAT MAKES THE LOOP RENEWABLE, and the one the old gossip
    could not express. Telling fires only when the speaker's claim beats the
    listener's, so a saturated population goes silent. Asking fires on the
    ASKER'S OWN GAP, which decay reopens continuously -- so there is always
    something somebody wants to know, without anything new having happened.

    THE GAP IS THE ASKER'S OWN, and now actually is. The first version
    enumerated the subjects THE OTHER HEAD HELD and asked about the one the
    asker was thinnest on -- which guaranteed a useful answer by reading a
    mind: measured on the twin towns, 634 of 2,413 asks named a subject the
    asker did not hold at all, knowledge of which had reached it through no
    channel. The docstring said "the asker does not know what the other
    holds" while the utility function knew exactly that. The subject now
    comes from the asker's own thinning claims, and the ask may simply MISS
    -- the other holds nothing on it, nothing arrives, and the beat records
    nothing. A missed question is not an effect, and treating it as one was
    measured to matter: with misses keeping situations warm, every open
    conversation stayed open forever and the whole town acted every single
    beat, 0.9 acts per body per hour against the 0.147 the layer was
    tuned at. Conversations with nothing left in them must be able to END;
    renewal now comes from decay reopening gaps and circulation supplying
    strangers, not from dead questions. Toward a FIGURE the ask always
    lands as conduct, because its answer is authored, never simulated --
    asking the player something IS the act the player experiences.
    """
    if not _within_speech(actor, other, state):
        return None
    mine = state["minds"].get(actor) or {}
    gaps = [(float(c.get("strength") or 0.0), s)
            for s, c in mine.items() if s not in (actor, other)]
    if not gaps:
        return None
    weakest, subject = min(gaps)
    if weakest > 0.75:
        return None

    def effect():
        if other in (state.get("figures") or {}):
            return f"{actor} asked {other} about {subject}"
        if hear(state["minds"], actor, other, subject, ASKED_RETENTION,
                state["regard"].get((actor, other), 1.0)):
            return f"{actor} asked {other} about {subject}"
        return ""

    return 0.35 + (1.0 - weakest) * 0.3, effect


def _afford_tell(actor, other, practice, state):
    if not _within_speech(actor, other, state):
        return None
    mine = state["minds"].get(actor) or {}
    here = _whereabouts(actor, state)
    # What gets told is `charter_talk.tellable`'s decision — the
    # remarkable, then the absent, then the room — and the measurements
    # that forced that ordering live on it. One selection rule for both
    # tell channels, or they drift.
    visible = {s for s in mine if _whereabouts(s, state) == here}
    subject = tellable(mine, exclude=(actor, other), visible=visible)
    if subject is None:
        return None
    strength = float(mine[subject].get("strength") or 0.0)
    if strength < PERSONAL_FLOOR:
        return None

    def effect():
        if other in (state.get("figures") or {}):
            # The figure's uptake is not simulated -- its mind lives in the
            # engine, and what it makes of the telling is the scene's
            # business. The telling itself is conduct, and it is exactly
            # the act a player experiences from a background NPC.
            return f"{actor} told {other} about {subject}"
        if hear(state["minds"], other, actor, subject, RETOLD_RETENTION,
                state["regard"].get((other, actor), 1.0)):
            return f"{actor} told {other} about {subject}"
        return ""

    return 0.25 + strength * 0.2, effect


def _afford_tend(actor, other, practice, state):
    """Attend somebody who has gone down. Services their worst need."""
    if not _within_speech(actor, other, state):
        return None
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
    the gap Fable's report left open. A figure can only be accused if the
    institution's ledger blames it, and `attribute_blame` follows the watch a
    figure never stands -- the gate, not a special case, is what keeps
    accusation pointed at the rostered.
    """
    if not _within_speech(actor, other, state):
        return None
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
    if not _within_speech(actor, other, state):
        return None
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


#: Affordances by practice kind, each NAMED. The name is the shared
#: vocabulary of conduct §12a requires: the chooser picks one by utility,
#: and an author -- a scene manager voicing a body, a player being answered
#: -- names one from outside. Both land through the identical builder and
#: effect; there is no second apply-function to drift from this one.
_AFFORDANCES = {
    "greeting": (("greet", _afford_greet),),
    "converse": (("ask", _afford_ask), ("tell", _afford_tell),
                 ("greet", _afford_greet)),
    "tending": (("tend", _afford_tend), ("ask", _afford_ask)),
    "quarrel": (("accuse", _afford_accuse), ("reconcile", _afford_reconcile)),
}

#: Why an authored act was not applied. Refused WITH A NOTICE, never
#: silently -- the wardrobe lesson in another costume: an assertion outside
#: what the state licenses is dropped and says so, and the licence is the
#: affordance itself.
REFUSED_ABSENT = "absent"
REFUSED_UNABLE = "unable"
REFUSED_NO_SITUATION = "no_situation"
REFUSED_OUTSIDE_LICENCE = "outside_licence"


def _state_of(bodies, minds, needs, regard, blame, at_hours, figures=None):
    return {
        "bodies": bodies, "figures": figures or {}, "minds": minds,
        "needs": needs, "regard": regard, "blame": blame,
        "at": float(at_hours), "spawned": [], "closed": [], "heard_blame": {},
    }


def _by_body(practices):
    held = {}
    for practice in practices.values():
        for role, key in practice["roles"].items():
            held.setdefault(key, []).append((role, practice))
    return held


def _offer_for(actor, act, other, participations, state):
    """The named affordance, through the identical builder a chosen act uses.

    Returns ``(offer, practice, reason)`` -- ``offer`` is ``(utility,
    effect)`` when the act is licensed, else ``None`` with the reason an
    authored act gets refused for. The search order is the same order the
    chooser walks, so an authored act and a chosen act resolve identically
    when both name the same conduct.
    """
    act = str(act or "")
    other = str(other or "")
    matched = False
    for role, practice in list(participations)[:PRACTICE_CAP]:
        partner = next((v for r, v in practice["roles"].items()
                        if r != role), None)
        if partner != other:
            continue
        for name, build in _AFFORDANCES.get(practice["kind"], ()):
            if name != act:
                continue
            matched = True
            offer = build(actor, other, practice, state)
            if offer is not None:
                return offer, practice, None
    return None, None, (REFUSED_OUTSIDE_LICENCE if matched
                        else REFUSED_NO_SITUATION)


def opportunities(bodies, minds, needs, events, practices, at_hours, seed=0,
                  figures=None):
    """Practices the world has just made available. Returns new instances.

    Situations are OPENED BY CIRCUMSTANCE, not by anybody deciding to have
    one: two strangers in a room, somebody on the floor, a blame that has
    landed -- and now a FIGURE standing where bodies stand, because the
    player walking into the mill is exactly the circumstance a greeting
    exists for. Only bodies ever act; a figure's half of any situation is
    authored, which is the author-switch working rather than an exception
    to it.
    """
    opened = {}
    rooms = co_present(bodies)
    figures = figures or {}
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
        # A figure in the room: the two most able-to-hand bodies get the
        # situation. Not everybody -- forty people do not all greet the
        # traveller at once, and the cap is the same shape `tending` uses.
        for fig_key in sorted(figures):
            if str(figures[fig_key].get("place") or "") != place:
                continue
            for actor in able_here[:2]:
                known = (minds.get(actor) or {}).get(fig_key)
                kind = "converse" if known else "greeting"
                key, entry = _open(kind, place, {"a": actor, "b": fig_key},
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


def offers(bodies, minds, needs, practices, regard, blame, at_hours,
           figures=None, actor=None):
    """The action instances: every act each participant could take right now.

    ``{actor: [{act, other, practice, utility}, ...]}``, utility-sorted.
    This is the Versu seam verbatim -- the same affordance set the chooser
    in ``enact`` picks from, handed outward instead, for a scene manager to
    put in front of a model or a player. Reading it costs nothing and
    licenses nothing; conduct still lands only through ``enact``.
    """
    state = _state_of(bodies, minds, needs, regard, blame, at_hours,
                      figures=figures)
    held = _by_body(practices)
    out = {}
    for key in sorted(held) if actor is None else [str(actor)]:
        body = bodies.get(key)
        if body is None or not body.get("available"):
            continue
        rows = []
        for role, practice in held.get(key, [])[:PRACTICE_CAP]:
            other = next((v for r, v in practice["roles"].items()
                          if r != role), None)
            if other is None or other == key:
                continue
            for name, build in _AFFORDANCES.get(practice["kind"], ()):
                offer = build(key, other, practice, state)
                if offer is None:
                    continue
                rows.append({"act": name, "other": other,
                             "practice": practice["key"],
                             "utility": round(float(offer[0]), 4)})
        if rows:
            rows.sort(key=lambda r: (-r["utility"], r["act"], r["other"]))
            out[key] = rows
    return out


def enact(bodies, minds, needs, practices, regard, blame, at_hours, seed=0,
          figures=None, conduct=None):
    """One beat of everybody choosing -- or being written.

    Returns ``(acts, spawned, closed, heard_blame, refused)``. Each body's
    options are the UNION of the affordances of every practice it
    participates in; it takes the highest-utility one and no more, so a beat
    is one act per person. Ties break on a seeded crc32 of the pair, which
    keeps a replay identical without making the choice arbitrary.

    ``conduct`` is the author-switch: ``{actor: {"act": ..., "other": ...}}``
    names the act a body takes this beat instead of choosing one. The
    authored act resolves through the IDENTICAL builders and effects -- same
    licences, same spawns, same records -- so pinning a body to exactly what
    it would have chosen is bit-for-bit indistinguishable from not pinning
    it, which is the §12a property and is pinned by test. An authored act
    the state does not license lands in ``refused`` with a reason and the
    body does nothing this beat: dropped with a notice, never applied and
    never silent.

    Each act is a record ``{actor, act, other, line}`` rather than a bare
    line, so an author can replay conduct and a ledger can say who did what
    to whom without parsing prose.
    """
    state = _state_of(bodies, minds, needs, regard, blame, at_hours,
                      figures=figures)
    by_body = _by_body(practices)
    conduct = conduct or {}

    acts = []
    refused = []
    for actor in sorted(set(by_body) | set(conduct)):
        authored = conduct.get(actor)
        body = bodies.get(actor)
        if body is None:
            if authored is not None:
                refused.append({"actor": actor, **authored,
                                "reason": REFUSED_ABSENT})
            continue
        if not body.get("available"):
            if authored is not None:
                refused.append({"actor": actor, **authored,
                                "reason": REFUSED_UNABLE})
            continue

        if authored is not None:
            offer, practice, reason = _offer_for(
                actor, authored.get("act"), authored.get("other"),
                by_body.get(actor, ()), state)
            if offer is None:
                refused.append({"actor": actor, **authored, "reason": reason})
                continue
            chosen = (offer[0], str(authored.get("act")),
                      str(authored.get("other")), offer[1], practice)
        else:
            chosen = None
            for role, practice in by_body.get(actor, [])[:PRACTICE_CAP]:
                other = next((v for r, v in practice["roles"].items()
                              if r != role), None)
                if other is None or other == actor:
                    continue
                for name, build in _AFFORDANCES.get(practice["kind"], ()):
                    offer = build(actor, other, practice, state)
                    if offer is None:
                        continue
                    utility, effect = offer
                    jitter = _roll(actor, other, practice["kind"], seed) * 0.02
                    if chosen is None or utility + jitter > chosen[0]:
                        chosen = (utility + jitter, name, other, effect,
                                  practice)
            if chosen is None:
                continue

        line = chosen[3]()
        if line:
            acts.append({"actor": actor, "act": chosen[1],
                         "other": chosen[2], "line": line})
            chosen[4]["last_effect_at"] = float(at_hours)

    return acts, state["spawned"], state["closed"], state["heard_blame"], \
        refused


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
