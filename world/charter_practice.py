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

VOLITION READS HISTORY, and only its own side of it. `_state_of` is the one
place that builds what an affordance may reason over, and until 2026-08-27 it
was `{bodies, figures, minds, needs, regard, blame, at}` -- so a body deciding
what to do could not see anything that had ever passed between it and the
person in front of it. Comme il Faut scores every exchange against the social
facts and that is the whole of its believability (McCoy et al., *Prom Week*,
FDG 2011; `docs/guides/RESEARCH.md` §1.7.6). `_between` is that scoring
surface here, and three invariants hold it:

  * **Every field is the DECIDING BODY'S OWN.** `experiences[actor]` is the
    actor's own diary, `served_beside[actor][other]` its own tally of its own
    co-presence, `judgments[actor][other]` its own stance, and a commitment
    is read only where the actor is a party to it. The other head's rows, the
    other head's stance and the other head's needs are never consulted --
    that is the 634-of-2,413 failure `_afford_ask` records, one tier out.
    Symmetric data is not shared data: `served_beside[a][b]` equals
    `served_beside[b][a]` because both are records of the same fact, held
    separately, and reading how an occasion LANDED on the other body is
    refused however symmetric the occasion was.
  * **Cost is constant in charter age.** Depth comes from the O(1)
    `served_beside` counter; the specific occasions come from ONE bounded
    `PAIR_TAIL` pass per holder per window, memoised in the throwaway state
    dict. A per-call scan of a body's whole life would be quadratic against
    an `EXPERIENCE_CAP` of 4,000.
  * **A body accuses from what IT perceived, never from the institution's
    books.** `grievance_against` is the only gate on `_afford_accuse` and on
    the `opportunities` quarrel opener, and no affordance reads
    `state["blame"]` any more. See `GRIEVANCE_KINDS` for why: the register
    read was dead code until `quarrel` got two live openers on 2026-08-27,
    and on that day it became the default path for who an ordinary body
    rounds on — with the utility sized on the counter's magnitude and handed
    to a scene-manager model through `charter_runtime.presence_view`.
  * **The memo assumes the four stores do not move under it.** True today:
    `enact` writes `minds`, `needs` and `regard` only, and `charter_run`
    writes experiences and tallies after `enact` returns. An affordance that
    minted an experience row inside its own effect would silently invalidate
    the cache, so it must not.

Pure and deterministic: no clock beyond what it is handed, no model, no
randomness beyond the caller's seed.
"""

from __future__ import annotations

import zlib

from .charter_commitment import OPEN_STATES
from .charter_figure import figure_claim
from .charter_mind import PERSONAL_FLOOR, hear, see
from .charter_politics import regard_key, regard_value
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

#: How far the pair's shared history may move any single utility.
#:
#: Bounded against the two numbers already in the module. It is 7.5x the
#: seeded tie-break jitter (`_roll(...) * 0.02` in `enact`), so a body with a
#: reason decides by the reason rather than by a coin flip -- which is the
#: whole point of the change. And it is BELOW the smallest dynamic range any
#: affordance already computes from present state (`tell` and `tend` both
#: swing 0.2; `ask` and `accuse` swing 0.3), so what is happening now still
#: outranks what happened before. One constant caps every history term
#: together, which is this repo's answer to the problem CiF solved with five
#: thousand hand-authored considerations: no single factor dominates a
#: decision.
HISTORY_WEIGHT = 0.15

#: How many of a holder's most recent experience rows the pair digest reads.
#:
#: The bound is what makes cost constant in charter age rather than merely
#: small. Measured 2026-08-27 on `tests/charter_worlds.big_ship(crew=40)`
#: over a simulated year: rows per body came out 11 at the quietest, 195 at
#: the busiest, median 30. So 256 is a year and a third of the busiest body
#: in the fixture and is essentially never reached, which is what a bound
#: should be -- `EXPERIENCE_CAP` is 4,000 and a body that lived to it would
#: otherwise be scanned in full, four practices deep, every window.
PAIR_TAIL = 256

#: Windows-plus-occasions with one person at which familiarity reads 1.0.
#:
#: Measured 2026-08-27 over a simulated year: the nonzero `served_beside`
#: distribution has median 272 on `big_ship(crew=40)` and median 219 on the
#: healthy six-body `SHIP` harness (`tests/test_charter_run.py`'s `KEPT`
#: needs, everybody in `galley`, `active_places = []`). 250 sits between the
#: two, so on either fixture about half the pairs who have stood a year
#: together read above 0.5 -- a year of somebody being the person you were
#: beside, not the ceiling of what a friendship can be.
FAMILIAR_SATURATION = 250.0

#: The judgment axes that say whether a body is easy to be near, signed so
#: they sum toward liking. `charter_social.JUDGMENT_AXES`'s fifth, `respect`,
#: is deliberately absent: it is orthogonal to fondness -- a body can respect
#: one it fears and hold none for one it is fond of -- and folding it in here
#: would make competence read as warmth.
AFFECT_AXES = (("trust", 1.0), ("warmth", 1.0),
               ("fear", -1.0), ("suspicion", -1.0))

#: Which field of a claim names the party it holds ANSWERABLE, per kind.
#:
#: THE ACCUSER'S CHANNEL, and it exists because there was none. `_afford_accuse`
#: decided entirely from `state["blame"][other]` -- the institution's private
#: register -- with no test that the actor had heard of the failure at all,
#: and sized its utility on the counter's magnitude, so a body's conduct (and
#: the utility number `charter_runtime.presence_view` hands a scene-manager
#: model) was produced by a fact that had reached it through no channel. That
#: read was DEAD CODE until 2026-08-27 -- `quarrel` had no opener but
#: `_afford_accuse`'s own effect, measured at zero `accuse` acts on screen and
#: off, in health and in famine -- and the same day's work gave it two live
#: openers. A leak nobody could reach is a residual; a leak on the default
#: path is a defect.
#:
#: Keyed by kind because WHICH field names the answerable party is a property
#: of the kind and not of any story: on `harm_done` and the commitment
#: failures the claim's `actor` did the thing, and on an `accusation` the
#: actor is the person SPEAKING and the answerable party is who they spoke
#: about. Every one of these is the actor's own claim in its own head,
#: firsthand or heard; hearsay counts, because inference is the product.
GRIEVANCE_KINDS = {
    "harm_done": "actor",
    "accusation": "toward",
    "report_refuted": "actor",
    "commitment_defaulted": "actor",
    "commitment_repudiated": "actor",
    "commitment_disputed": "actor",
    "institution_order_failed": "actor",
}

#: Claims that name a PLACE as having failed rather than a person.
#:
#: The seed, and without it the vocabulary above has no producer: the only
#: event a stressed institution actually emits is `upkeep_out_of_band`
#: (measured on a famine quarter of `twin_towns(40)`, on screen: 4
#: `upkeep_out_of_band` and nothing else that names anybody). What a body
#: standing in a failed place holds is its own claim that THIS PLACE has
#: failed, and the answerable party it can round on is whoever is standing in
#: it with them -- which is the shape of an ordinary accusation and is not the
#: register's answer. Where the two differ, the institution blaming a body
#: that was nowhere near (`charter_politics.attribute_blame`'s own docstring)
#: is now VISIBLE as the divergence it always was, rather than being laundered
#: into the accuser's mouth.
PLACE_FAILURE_KINDS = frozenset({"upkeep_out_of_band", "stock_empty"})


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


def _counterpart(row, holder):
    """Which party of an experience row is the OTHER one, per row kind.

    A row naming nobody -- a post stood, a private habit, a happening lived
    through -- is not about anybody and returns "", which is most of a quiet
    body's diary and the reason the pass is cheap even before `PAIR_TAIL`
    bites.
    """
    kind = str(row.get("kind") or "")
    if kind == "social":
        # Written to both participants with a `role` saying which end the
        # holder was (`charter_run._record_social_experiences`), so the
        # counterpart is the field the holder is NOT.
        if str(row.get("role") or "") == "actor":
            return str(row.get("other") or "")
        actor = str(row.get("actor") or "")
        return actor if actor != holder else str(row.get("other") or "")
    if kind in ("acquaintance", "encounter"):
        return str(row.get("other") or "")
    if kind == "shared_prestory":
        return str(row.get("with") or "")
    return ""


def _pair_rows(state, holder):
    """One bounded pass over a holder's own diary, keyed by counterpart.

    Memoised in the throwaway `state` dict, so four practices deep and six
    affordances wide a holder's rows are visited ONCE per window rather than
    once per offer. The tail bound is what makes this constant in charter
    age: `EXPERIENCE_CAP` is 4,000 and `PAIR_TAIL` is 256, so a body that has
    lived a long time costs exactly what a body that has lived a short one
    does. Same shape as `charter_news.decay_news`'s `keys` index.
    """
    held = state["pairs"].get(holder)
    if held is not None:
        return held
    held = {}
    rows = (state["experiences"].get(holder) or ())
    for row in rows[-PAIR_TAIL:]:
        if not isinstance(row, dict):
            continue
        other = _counterpart(row, holder)
        if not other or other == holder:
            continue
        acc = held.get(other)
        if acc is None:
            acc = held[other] = [0, 0.0, 0, 0.0]
        # occasions, valence sum, valence count, last hour.
        acc[0] += 1
        if "valence" in row:
            acc[1] += float(row.get("valence") or 0.0)
            acc[2] += 1
        at = float(row.get("at_hours") or 0.0)
        if at > acc[3]:
            acc[3] = at
    state["pairs"][holder] = held
    return held


def _clamp_unit(value):
    return max(-1.0, min(1.0, float(value)))


def _between(state, actor, other):
    """What has passed between these two, as the ACTOR holds it.

    ``{familiar, affect, debt, owed}`` -- the surface every affordance
    weights on and the only one they may. Each field is read out of the
    deciding body's own side of a store; the other body's rows, stance and
    needs are never touched. See the module docstring for why symmetry does
    not make the other side readable.
    """
    beside = float(((state["served_beside"].get(actor) or {})
                    .get(other) or 0))
    acc = _pair_rows(state, actor).get(other) or (0, 0.0, 0, 0.0)

    # ONE UNIT, DELIBERATELY. A window stood beside somebody and a specific
    # occasion with them are both "time with this person" at the resolution
    # this layer works at, and keeping them apart would need a second
    # constant nobody can set from evidence. The tally carries the volume
    # (it is what a quiet institution deposits) and the rows carry the
    # occasions (they are what a busy one does); a pair has whichever of the
    # two its life actually produced.
    familiar = min(1.0, (beside + acc[0]) / FAMILIAR_SATURATION)

    # HOW THEY SIT WITH ME, from the two records of that the actor holds:
    # the affect stamped on its own rows by `charter_feel` at the time, and
    # its own five-axis stance. Both are already normalised readings, so
    # they are summed and clamped rather than mixed at some authored ratio
    # -- either alone can carry the axis, and where both exist they agree or
    # they cancel.
    #
    # MEASURED THIN TODAY, and this is the honest reading of it:
    # `charter_run._record_social_experiences` stamps no valence, and
    # judgments measured EMPTY across a simulated year of `big_ship(crew=40)`
    # and across four charters of a real story (RESEARCH.md §1.7.6). So the
    # axis is fed by `encounter`/`acquaintance` rows only until design 2 --
    # ordinary evidence, not only failure -- lands. Do not compensate by
    # raising `HISTORY_WEIGHT`; that would make the constant mean something
    # different once the evidence arrives.
    affect = acc[1] / acc[2] if acc[2] else 0.0
    stance = (state["judgments"].get(actor) or {}).get(other)
    if stance:
        affect += sum(sign * float(stance.get(axis) or 0.0)
                      for axis, sign in AFFECT_AXES) / len(AFFECT_AXES)

    # An unsettled matter between the two of them, in the actor's own
    # direction. `debt` is what the actor owes; `owed` is anything open
    # either way, because being at odds with somebody you have business with
    # is its own reason to stop being at odds.
    open_between = (state["between"].get(actor) or {}).get(other) or (0, 0)
    return {"familiar": familiar, "affect": _clamp_unit(affect),
            "debt": float(open_between[0]), "owed": float(open_between[1])}


def _grievances(state, holder):
    """One pass over a holder's OWN claims, indexed by who they implicate.

    ``{"named": {body: count}, "places": {place: count}}``. Memoised in the
    throwaway `state` dict for the same reason `_pair_rows` is: a head is
    visited once per window rather than once per offer, four practices deep.

    THE HOLDER'S OWN, END TO END. `minds[holder]` is what this head was told
    or saw; no other head's claims, no register, no event log. A claim that
    has faded below `charter_mind.PERSONAL_FLOOR` is already gone from the
    store (`charter_news.decay_news` deletes rather than floors), so a
    grievance lapses on its own -- which is the difference between this and
    `politics.blame`, a MONOTONE counter that would still be a reason to round
    on somebody a decade later.
    """
    held = state["grievances"].get(holder)
    if held is not None:
        return held
    held = {"named": {}, "places": {}}
    for claim in (state["minds"].get(holder) or {}).values():
        if not isinstance(claim, dict) or claim.get("kind") != "news":
            continue
        kind = str(claim.get("event_kind") or "")
        field = GRIEVANCE_KINDS.get(kind)
        if field:
            named = str(claim.get(field) or "")
            if named and named != holder:
                held["named"][named] = held["named"].get(named, 0) + 1
        elif kind in PLACE_FAILURE_KINDS:
            place = str(claim.get("place") or "")
            if place:
                held["places"][place] = held["places"].get(place, 0) + 1
    state["grievances"][holder] = held
    return held


def grievance_against(state, actor, other):
    """How many of the ACTOR'S OWN claims give it a reason to round on
    ``other``, here. Zero means it has no channel and may not accuse.

    Two shapes, both the actor's: a claim that names ``other`` as the party at
    fault, and a claim that this place has failed while ``other`` stands in it
    with them. Co-presence is the whole of the second test, exactly as it is
    for `charter_news.witness` -- a body elsewhere saw nothing and is owed
    nothing.
    """
    index = _grievances(state, actor)
    count = int(index["named"].get(other, 0))
    place = _whereabouts(actor, state)
    if place and place == _whereabouts(other, state):
        count += int(index["places"].get(place, 0))
    return count


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
    #
    # A RE-MEETING IS NOT A MEETING. This affordance opens whenever the
    # actor's claim on the other is gone, and `charter_mind.decay_minds`
    # takes claims away while `experiences` keeps rows forever -- so the
    # second time two people are strangers, the actor still has its own
    # record of the first time. Only affect moves the number: warmth makes
    # somebody easier to walk back up to, and a body with genuinely no
    # history reads exactly 0.9, which is the old constant untouched.
    return 0.9 + HISTORY_WEIGHT * _between(state, actor, other)["affect"], \
        effect


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
                regard_value(state["regard"], actor, other)):
            return f"{actor} asked {other} about {subject}"
        return ""

    # WHO YOU ASK, not what you ask about: the subject is already the
    # asker's own thinnest claim and the gap sets most of the number. History
    # decides between two people who could both answer -- you take a question
    # to somebody you have a life with, and slightly more readily to somebody
    # you like. Only the POSITIVE half of affect counts: disliking somebody
    # is a reason to ask them less, not a reason to be less curious, and
    # regard already applies that penalty at uptake inside `hear` (the
    # `regard_value` argument in the effect below). Counting it twice would
    # make dislike weigh on both the wanting and the getting.
    pair = _between(state, actor, other)
    return 0.35 + (1.0 - weakest) * 0.3 + HISTORY_WEIGHT * (
        0.6 * pair["familiar"] + 0.4 * max(0.0, pair["affect"])), effect


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
                regard_value(state["regard"], other, actor)):
            return f"{actor} told {other} about {subject}"
        return ""

    # Telling is the affordance that saturates, so what history adds here is
    # only WHO you would rather tell. Familiarity alone: you carry a thing to
    # the person you have a life with. Affect is deliberately absent -- a
    # grievance is at least as tellable to somebody you dislike as to
    # somebody you like, and the uptake half already weighs the listener's
    # regard inside `hear`.
    return 0.25 + strength * 0.2 + HISTORY_WEIGHT * 0.5 * _between(
        state, actor, other)["familiar"], effect


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
    #
    # ADDITIVE ONLY, AND NOT FAMILIARITY. A body does not walk past somebody
    # on the floor because it dislikes them, so nothing here may subtract and
    # affect is not read at all: who you help is not a popularity question.
    # What history contributes is the one thing that genuinely changes the
    # answer -- an open commitment the actor itself undertook toward this
    # person. A debt is a reason to be the one who steps forward.
    return 0.8 + min(0.2, gap) + HISTORY_WEIGHT * 0.5 * _between(
        state, actor, other)["debt"], effect


def _afford_accuse(actor, other, practice, state):
    """Say aloud that you hold somebody responsible.

    THE ACCUSER DECIDES FROM ITS OWN HEAD. Until 2026-08-27 this gated on
    `state["blame"][other]` and sized its utility on that counter, so who an
    ordinary body rounded on -- and how hard -- was produced by the
    institution's PRIVATE register, a fact that reached the accuser through no
    channel and that `charter_news.WITNESSABLE`'s own allowlist comment names
    as the leak class ("`post_unfilled` is a conclusion the institution
    reached in its own books, and a body in the room has no way to perceive
    it"). See `GRIEVANCE_KINDS`: the gate is now the actor's own claims, and
    the register is not read here at all.

    The accused still LEARNS they are blamed -- that was the gap Fable's
    report left open, and `heard_blame` still closes it. What changed is that
    the accusation now follows somebody's perception rather than the books, so
    the institution blaming a body that was nowhere near the place shows up as
    a divergence between who is disgraced and who gets rounded on instead of
    being laundered into an accuser's mouth.
    """
    if not _within_speech(actor, other, state):
        return None
    # POINTED AT THE ROSTERED, which the register gate used to do as a side
    # effect (a figure is never in `politics.blame`) and which now has to be
    # said. A figure has no `heard_blame` entry, no mark and no place in
    # `normalize_marks`' body filter, so an accusation aimed at one is a
    # half-written record; the author switch is where a body rounds on the
    # player. Subtraction, and it keeps the old scope exactly.
    if other not in state["bodies"]:
        return None
    grievance = grievance_against(state, actor, other)
    if grievance <= 0:
        return None
    pair = regard_key(actor, other)
    if regard_value(state["regard"], actor, other) < 0.45:
        return None

    def effect():
        state["regard"][pair] = max(
            0.3, regard_value(state["regard"], actor, other) - 0.1)
        state["heard_blame"].setdefault(other, set()).add(actor)
        spawn = _open("quarrel", practice["place"],
                      {"a": actor, "b": other}, state["at"], about=other)
        state["spawned"].append(spawn)
        return f"{actor} accused {other}"

    # SUBTRACTION ONLY, which is Prom Week's Simon: he refuses to carry
    # Cassandra's gossip about Naomi because the friendship outweighs the
    # influence, and the refusal is legible precisely because it names a
    # specific remembered thing. A life with somebody is a reason to hold
    # your tongue about them; it is never a reason to accuse somebody else
    # harder, so this term cannot raise the number. Affect gates it: the
    # reluctance comes from a life you VALUE -- two hundred windows beside
    # somebody you have come to dislike buys them nothing.
    #
    # NAMED APART FROM `pair`, and this is not style. `pair` is the regard key
    # the closure above writes through, and `effect` resolves it at CALL time
    # from this scope -- so rebinding it to the digest made every accusation
    # raise `TypeError: unhashable type: 'dict'`. Nothing caught it because
    # `quarrel` had no opener until the same day: the affordance was dead code
    # from the moment the history term was added to it.
    history = _between(state, actor, other)
    # SIZED ON THE ACTOR'S OWN COUNT, not the register's. The swing is the
    # same 0.3 it was, so nothing about the affordance's rank against `ask`
    # or `tend` moved; what moved is that the number now says "how much I
    # have against you" rather than "how many times the books have blamed
    # you", which was a monotone read of a counter this body cannot see.
    return 0.55 + min(0.3, 0.1 * grievance) \
        - HISTORY_WEIGHT * history["familiar"] \
        * max(0.0, history["affect"]), effect


def _afford_reconcile(actor, other, practice, state):
    if not _within_speech(actor, other, state):
        return None
    pair = regard_key(actor, other)
    if regard_value(state["regard"], actor, other) >= 1.0:
        return None
    if state["at"] - float(practice["opened_at"]) < 12.0:
        return None

    def effect():
        state["regard"][pair] = min(
            1.0, regard_value(state["regard"], actor, other) + 0.08)
        state["closed"].append(practice["key"])
        return f"{actor} made peace with {other}"

    # The flat 0.4 said a quarrel with a stranger and a quarrel with the hand
    # you have stood four hundred watches beside are worth ending equally,
    # which is the exact claim this design exists to stop making. Two reasons
    # to make peace, both the actor's own: a life together, and an unsettled
    # matter between you that being at odds is in the way of.
    # Named apart from the regard key `pair` for the reason `_afford_accuse`
    # states above: the closure resolves that name when the act lands.
    history = _between(state, actor, other)
    return 0.4 + HISTORY_WEIGHT * (
        0.7 * history["familiar"] + 0.3 * history["owed"]), effect


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


def _state_of(bodies, minds, needs, regard, blame, at_hours, figures=None,
              *, experiences=None, served_beside=None, judgments=None,
              commitments=None):
    """Everything an affordance may reason over, built in ONE place.

    The four history stores are keyword-only with `None` defaults so every
    existing caller and every existing test keeps working unchanged, and so
    that a caller which forgets them gets the old behaviour rather than a
    wrong answer. Nothing here is persisted: the dict is created per call,
    mutated by effects, and dropped.

    `blame` IS CARRIED AND NO AFFORDANCE READS IT, as of 2026-08-27. It is the
    institution's private register -- the leak class
    `charter_news.WITNESSABLE`'s allowlist comment names -- and the one
    affordance that read it (`_afford_accuse`) now decides from the actor's own
    claims instead. It stays in the signature because it is positional in
    `offers`/`enact` and dropping it would move every call site; it stays in
    the dict so this note has somewhere to live. Reading it again from an
    affordance is a firewall decision and needs its own argument.
    """
    return {
        "bodies": bodies, "figures": figures or {}, "minds": minds,
        "needs": needs, "regard": regard, "blame": blame,
        "at": float(at_hours), "spawned": [], "closed": [], "heard_blame": {},
        "experiences": experiences or {}, "judgments": judgments or {},
        "served_beside": served_beside or {},
        "between": _open_between(commitments), "pairs": {},
        "grievances": {},
    }


def _open_between(commitments):
    """Open commitments, indexed by a reader LICENSED for them.

    ``{reader: {counterparty: (owes_them, they_owe_me)}}``. Eager rather than
    lazy because `COMMITMENT_CAP` is 64 and the whole index costs less than
    one lazy miss would.

    THE GATE IS THE LINE, and it is enforced here so no affordance can go
    round it: `charter_commitment`'s own docstring says each record "names who
    inside that Charter has actually received evidence of it". A record is
    read only by a party to it or by somebody in `recognized_by` -- and only
    the two PARTIES get a pair entry out of it, because knowing that two other
    people have business is not having business with either of them. Parties
    are licensed by identity, so the `recognized_by` half currently admits
    nobody new; it is written out because the condition is the rule, and a
    later record kind that names a pair the reader merely heard about must
    not slip in behind it.
    """
    index = {}
    for record in (commitments or {}).values():
        if not isinstance(record, dict):
            continue
        if str(record.get("state") or "") not in OPEN_STATES:
            continue
        promisor = str(record.get("promisor") or "")
        beneficiary = str(record.get("beneficiary") or "")
        if not promisor or not beneficiary or promisor == beneficiary:
            continue
        licensed = {promisor, beneficiary} | {
            str(x) for x in record.get("recognized_by") or ()}
        for reader, counterparty, owes in ((promisor, beneficiary, True),
                                           (beneficiary, promisor, False)):
            if reader not in licensed:
                continue
            held = index.setdefault(reader, {})
            debt, owed = held.get(counterparty, (0, 0))
            held[counterparty] = (1 if owes else debt, 1)
    return index


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


#: The situations worth opening where nobody is watching. A quiet institution
#: is not an absence of story -- "all systems nominal" is a REPORT, and the
#: story was never in the systems. But `converse` is the kind that saturates:
#: every acquainted pair in a room, every window, forever, which is what took
#: a simulated month from 3.6s to 32.7s and got beat-scale social detail
#: switched off offscreen wholesale. These two do not saturate. `tending`
#: opens only when somebody is actually under their floor, which is rare and
#: consequential; `greeting` opens only between people who do not yet know
#: each other, which is bounded by the pairs an institution contains. So the
#: resolution dial is per-KIND as well as per-place: offscreen you do not get
#: gossip, and you do get the handful of things that change who people are to
#: one another.
#:
#: NOW EVERY KIND, owner's call 2026-08-27. The exclusion of `converse` rested
#: on a 9x figure (a simulated month, 3.6s to 32.7s) that does NOT reproduce on
#: this code: measured today on twin_towns(40) offscreen for a simulated month,
#: greeting+tending is 0.67s and every kind is 1.29s -- 1.9x, and it triples
#: the autobiographical rows deposited, 1,276 to 3,932. Saturation was the
#: other half of the argument and `_afford_ask` already answered it: asking
#: fires on the ASKER'S OWN gap, which decay reopens continuously, so the loop
#: no longer goes silent once a population has met itself. None means no
#: restriction; the constant survives as the seam a future throttle would use.
COARSE_PRACTICES = None


def opportunities(bodies, minds, needs, events, practices, at_hours, seed=0,
                  figures=None, kinds=None, *, blame=None):
    """Practices the world has just made available. Returns new instances.

    Situations are OPENED BY CIRCUMSTANCE, not by anybody deciding to have
    one: two strangers in a room, somebody on the floor, a blame that has
    landed -- and now a FIGURE standing where bodies stand, because the
    player walking into the mill is exactly the circumstance a greeting
    exists for. Only bodies ever act; a figure's half of any situation is
    authored, which is the author-switch working rather than an exception
    to it.

    ``kinds`` restricts which of them may open. None is every kind, which is
    what a scene gets; `COARSE_PRACTICES` is what the rest of the world gets.

    ``blame`` is the institution's own ledger, keyword-only and defaulting to
    none so every existing caller keeps its behaviour. It opens `quarrel` and
    nothing else, and only between a pair where the ACTOR holds its own reason
    (`grievance_against`); what any body then SAYS about it still goes through
    `_afford_accuse`'s own gates.
    """
    opened = {}
    allowed = None if kinds is None else frozenset(str(k) for k in kinds)

    def _permits(kind):
        return allowed is None or kind in allowed

    rooms = co_present(bodies)
    figures = figures or {}
    # Built lazily and ONCE for the whole call, so the grievance index over a
    # head is walked once per window rather than once per room -- the same
    # memo `_pair_rows` carries and for the same reason. `needs`/`regard`/
    # `blame` are deliberately empty: `grievance_against` reads `minds` and
    # `bodies` and nothing else, and handing it stores it does not use is how
    # a reader later assumes it does.
    reasons = {"state": None}

    def _has_reason(actor, subject):
        if reasons["state"] is None:
            reasons["state"] = _state_of(bodies, minds, {}, {}, {}, at_hours,
                                         figures=figures)
        return grievance_against(reasons["state"], actor, subject) > 0

    for place, present in sorted(rooms.items()):
        able_here = [k for k in present if bodies[k].get("available")]
        for index, actor in enumerate(able_here):
            for other in able_here[index + 1:index + 3]:
                known = (minds.get(actor) or {}).get(other)
                kind = "converse" if known else "greeting"
                if not _permits(kind):
                    continue
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
                if not _permits(kind):
                    continue
                key, entry = _open(kind, place, {"a": actor, "b": fig_key},
                                   at_hours)
                if key not in practices:
                    opened[key] = entry
        # Somebody under their floor, and anybody able standing over them.
        for subject in present:
            held = (needs or {}).get(subject) or {}
            if not held or bodies[subject].get("available"):
                continue
            if not _permits("tending"):
                continue
            for carer in able_here[:2]:
                key, entry = _open("tending", place, {"a": carer, "b": subject},
                                   at_hours, about=subject)
                if key not in practices:
                    opened[key] = entry
        # A BLAME THAT HAS LANDED -- the third circumstance this function's own
        # docstring has always claimed to open, and the one it never did.
        # `quarrel` had exactly ONE opener in the package: `_afford_accuse`,
        # which is an affordance OF quarrel. So no state the simulation can
        # reach ever produced a quarrel, `accuse` and `reconcile` were
        # unreachable, and `charter_social.DEFAULT_SIGNALS`' `accusation` and
        # `apology` weights sat beside `aid_given`'s in the same
        # three-quarters-of-a-feature state. Measured: zero `accuse` acts in a
        # simulated quarter of `twin_towns(40)` on screen and off, in health
        # and in famine, against 10 `post_unfilled` events that had already
        # attributed blame to somebody.
        #
        # Opening it is not accusing: `_afford_accuse` still requires speech
        # range, its own grievance and regard at or above 0.45, and each
        # accusation costs 0.1 of that regard, so a pair is self-limiting at
        # roughly two. Capped at the two most able bodies to hand, the same
        # bound `tending` uses, because forty people do not all round on the
        # same person at once and pairing a room is quadratic.
        #
        # AND THE ACTOR MUST HOLD ITS OWN REASON. The register says which of
        # its own situations the institution has cause to open; it may not
        # pair two people who have none. Without this test a quarrel opened
        # off the books alone, and a quarrel is not inert: it occupies one of
        # four `PRACTICE_CAP` slots, and `_afford_reconcile` would offer
        # "made peace with" inside a quarrel that had never been had -- which
        # is conduct caused by a fact neither body could perceive.
        if blame and _permits("quarrel"):
            for subject in sorted(present):
                if int((blame or {}).get(subject, 0) or 0) <= 0:
                    continue
                for actor in able_here[:2]:
                    if actor == subject:
                        continue
                    if not _has_reason(actor, subject):
                        continue
                    key, entry = _open("quarrel", place,
                                       {"a": actor, "b": subject},
                                       at_hours, about=subject)
                    if key not in practices:
                        opened[key] = entry
    return opened


def offers(bodies, minds, needs, practices, regard, blame, at_hours,
           figures=None, actor=None, *, experiences=None, served_beside=None,
           judgments=None, commitments=None):
    """The action instances: every act each participant could take right now.

    ``{actor: [{act, other, practice, utility}, ...]}``, utility-sorted.
    This is the Versu seam verbatim -- the same affordance set the chooser
    in ``enact`` picks from, handed outward instead, for a scene manager to
    put in front of a model or a player. Reading it costs nothing and
    licenses nothing; conduct still lands only through ``enact``.

    The four history stores are keyword-only and MUST be passed the same way
    ``enact`` is passed them. This seam and the chooser have to score
    identically -- an author handed numbers computed without history while
    the engine chooses with it is a seam that lies about what the body wants.
    """
    state = _state_of(bodies, minds, needs, regard, blame, at_hours,
                      figures=figures, experiences=experiences,
                      served_beside=served_beside, judgments=judgments,
                      commitments=commitments)
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
          figures=None, conduct=None, *, experiences=None, served_beside=None,
          judgments=None, commitments=None):
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

    The four history stores are the pair's shared record, read only from the
    deciding body's own side (see the module docstring). They are read and
    never written: everything this function mutates is `minds`, `needs`,
    `regard` and the practice set, which is what lets the digest be memoised
    for the life of the call.
    """
    state = _state_of(bodies, minds, needs, regard, blame, at_hours,
                      figures=figures, experiences=experiences,
                      served_beside=served_beside, judgments=judgments,
                      commitments=commitments)
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
