"""What a window of institutional life feels like, per body, in the engine's
own affect model.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §4. The mood experiment
settled what this module must NOT be: a scalar built from pressure, blame and
regard correlates with ``pressure`` at r = 0.994 and is a duplicate signal
wearing a new name. So no affect arithmetic is invented here at all. Each
body's felt state is produced by calling ``mind/psychology_runtime`` —
``resolve_hedonic`` and ``resolve_stress``, the same deterministic functions
that own tone and stress for characters — with inputs the background tier
legitimately has. One affect model, two tiers, and a promoted body arrives at
the character tier already holding the interior its background life produced,
in the exact dict shapes the character pipeline persists.

WHAT MAY ENTER AN APPRAISAL, and it is the firewall doing the choosing:

  * **The body's own needs.** Interoception is always a channel to yourself:
    a need below its floor proposes pain, named for the need.
  * **Standing conditions at the body's place, THIS window's state.** A
    condition below its floor where the body stands is appraised every
    window it stands there — because a condition below its floor is not a
    static backdrop, it is actively degrading, and living beside it is a
    continuing threat rather than a remembered one. The first version read
    only the crossing EVENTS, and a month-long crisis produced one window of
    strain that had fully decayed by the time anyone could have been
    measured feeling it. Register facts — ``post_unfilled``,
    ``post_believed_filled`` — are excluded even at the body's own place,
    because they are entries in the institution's books, not states of a
    room, and a mind may not appraise a ledger it has never read.
  * **The body's own stake.** A failing condition served by the post this
    body stood weighs more than one it merely stands beside, and so does one
    that feeds a need of the body's own (``fed_by``) — the bakehouse going
    dark is worse when it is your bread. Neither is a second channel: the
    body is at that place, and the extra weight is what the failure MEANS to
    the one responsible for it, or fed by it.
  * **A peer going down in the same room** — the ``body_unable`` event,
    transient on purpose: a collapse is a shock in the window it happens,
    and a laid-up neighbour is thereafter a fact of life, not a fresh threat
    every four hours.
  * **A mark this body was PRESENT FOR** (``charter_mark.BODY_MARKS``): it
    was handed a duty, somebody tended it in the room, somebody said the
    accusation to its face. FRESH ONLY — the marks set or refreshed this
    window, never the ones it is still holding. A 168-hour mark appraised
    every window would rebuild exactly the standing-strain floor the comment
    in ``advance_feel`` records, which is the one measured way this module
    has been broken.

What deliberately does not enter: blame. The institution's blame ledger is a
register fact with no channel to the blamed — a body blamed for a post it was
never at does not feel the blame until somebody tells it. THE TELLING NOW
EXISTS: an accusation is co-present speech, ``charter_practice`` records the
accuser in ``heard_blame`` precisely because that is the channel, and the
``accused`` mark is that telling arriving here. The ledger itself still does
not, and neither does ``charter_mark``'s ``disgraced``, which is the same
register fact wearing a recency date — a body that was never told is a body
that feels nothing, and that gap is the design rather than a hole in it.

TIME, COARSE-GRAINED ON PURPOSE. The character tier's psych unit is one
minute (``elapsed_psych_units``); at that resolution every transient would
decay to nothing between four-hour planning windows and background bodies
could not carry feeling at all. This tier passes ONE UNIT PER HOUR instead: a
window is the background beat, so transient pain persists across a couple of
windows of deprivation, charge builds over half a day of it, and cumulative
load accrues across the two or three bad days an institutional crisis
actually takes. The state SHAPES are identical either way — a handoff at
promotion is a copy, and the character tier's own clock takes over from
there.

SPARSE, because storage grows with incident. A body with nothing proposed
and nothing residual has no entry: a quiet institution's ``feel`` dict is
empty, costs nothing to advance, and stores nothing across a checkpoint.
"""

from __future__ import annotations

from mind.psychology_runtime import resolve_hedonic, resolve_stress

from .charter_mark import BODY_MARKS
from .charter_needs import body_state
from .charter_temper import (
    interoception_of,
    stress_profile_of,
    temperament_of,
)

#: What standing beside a failing condition proposes, against your goals.
#: Negative and fairly certain — it is in front of you.
WITNESS_IMPACT = -0.5
WITNESS_CERTAINTY = 0.9

#: What the same failure proposes when the failed condition is one YOUR post
#: serves. The strongest thing the background tier can say about a body's
#: inner life: the thing you were responsible for went down while you stood
#: there.
OWN_CHARGE_IMPACT = -0.8
OWN_CHARGE_CERTAINTY = 0.95

#: A failing condition at your place that FEEDS one of your own needs.
#: Between witness and own charge: not your responsibility, but your bread.
OWN_STAKE_IMPACT = -0.7

#: A peer going under in the same room. Event-scoped: a shock in the window
#: it happens, a fact of life afterwards.
PEER_DOWN_IMPACT = -0.6

#: Somatic pleasure proposed by a condition coming back into band at the
#: body's place, and the larger figure when it was the body's own charge.
#: Relief is real and it is how ``pleasure_sensitivity`` gets a channel that
#: is not a bench.
RESTORED_PLEASURE = 0.3
OWN_RESTORED_PLEASURE = 0.5

#: What being told to your face that you are blamed proposes, against your
#: goals. Negative and nearly certain — the person saying it is standing in
#: front of you, which is the whole reason `accused` is a body mark and the
#: register's own `disgraced` is not. Sized between `WITNESS_IMPACT` and
#: `OWN_CHARGE_IMPACT`: worse than watching a condition fail beside you,
#: not as bad as the thing you were responsible for going down.
ACCUSED_IMPACT = -0.6
ACCUSED_CERTAINTY = 0.95

#: Somebody attended you where you stood. Above `RESTORED_PLEASURE`'s 0.3
#: because a person choosing to help you is more than a level coming back
#: into band, and below `OWN_RESTORED_PLEASURE` because it did not cost you
#: anything.
AIDED_PLEASURE = 0.4

#: The institution handed you a duty you had never stood. The smallest of the
#: three, and the only one that fires in a HEALTHY institution — which makes
#: it the one that could leave a quiet charter carrying feel entries where it
#: used to carry none. `_negligible` drains it: measured on `big_town(40)`
#: over a simulated year, `feel` ends empty and every body marked `posted`
#: had drained inside a handful of windows.
POSTED_PLEASURE = 0.2

#: How a need's gap below its floor scales into a pain proposal. Floors sit
#: around 0.1-0.3, so a freshly-crossed need proposes little and a body at
#: zero proposes close to the ceiling.
PAIN_PER_GAP = 3.0

#: Below this on every field, a feel entry is dropped rather than stored.
NEGLIGIBLE = 0.02

#: One psych unit per hour at this tier — see the module docstring.
UNITS_PER_HOUR = 1.0

#: How much faster a strained body spends rest, at full strain. The one road
#: back into the institution, and it runs through the EXISTING needs
#: machinery: strain disturbs rest, worn rest crosses its floor, and the
#: existing `body_unable` path takes the post away — no second stand-down
#: channel, no new event kind, no term on the planner's reluctance axis
#: (the mood lesson). Kept below `ON_WATCH_STRAIN`'s 2.5x so the work itself
#: remains the dominant cost of a watch.
STRAIN_REST_TOLL = 0.6

#: Event kinds a co-present body can perceive: things that HAPPEN in a room,
#: as opposed to entries in the institution's books. Adverse standing
#: conditions are read from STATE (`out_of_band` at the body's place), so
#: the only events feel consumes are the transient ones.
_PHYSICAL_RELIEF = ("upkeep_restored",)


def normalize_feel(stored):
    """``{body: {"hedonic": {...}, "stress": {...}}}`` from any shape."""
    out = {}
    for key, entry in (stored or {}).items():
        if not isinstance(entry, dict):
            continue
        hedonic = entry.get("hedonic")
        stress = entry.get("stress")
        record = {}
        if isinstance(hedonic, dict):
            record["hedonic"] = dict(hedonic)
        if isinstance(stress, dict):
            record["stress"] = dict(stress)
        if record:
            out[str(key)] = record
    return out


def _served_by_body(watch, posts):
    """``{body: set(upkeep keys its post serves this window)}``."""
    out = {}
    for post_key, body_key in (watch or {}).items():
        post = (posts or {}).get(post_key)
        if post is None:
            continue
        out.setdefault(body_key, set()).update(post.get("serves") or ())
    return out


def appraise_window(body_key, place, upkeeps, events, held_needs=None,
                    own_upkeeps=None, marks=()):
    """One body's deterministic appraisal of one window.

    Returns ``(appraisal, goal_impacts)`` in the shapes
    ``resolve_hedonic``/``resolve_stress`` read. Everything in it arrived
    through a channel: the body's own needs, the state of the place the body
    actually stood, the transient events that happened there, and the marks
    it was itself present for.

    ``marks`` is the FRESH ``charter_mark`` kinds this body took THIS window,
    and it is keyword-defaulted so the facade export and
    ``tools/charter_audit_feel.py``'s direct calls keep working unchanged. A
    kind outside ``BODY_MARKS`` is ignored here rather than trusted from the
    caller: ``disgraced`` is a register fact with no channel to the blamed,
    and the scope split has to hold at the reader as well as the writer.
    """
    place = str(place or "")
    own_upkeeps = own_upkeeps or set()
    fed_by = {str(need.get("fed_by") or "")
              for need in (held_needs or {}).values()}
    fed_by.discard("")
    impacts = []

    if place:
        for key, upkeep in (upkeeps or {}).items():
            if str(upkeep.get("place") or "") != place:
                continue
            if float(upkeep.get("level", 1.0)) >= float(
                    upkeep.get("floor", 0.0)):
                continue
            if key in own_upkeeps:
                impacts.append({"impact": OWN_CHARGE_IMPACT,
                                "certainty": OWN_CHARGE_CERTAINTY})
            elif key in fed_by:
                impacts.append({"impact": OWN_STAKE_IMPACT,
                                "certainty": WITNESS_CERTAINTY})
            else:
                impacts.append({"impact": WITNESS_IMPACT,
                                "certainty": WITNESS_CERTAINTY})

    pleasure = 0.0
    pleasure_why = ""
    for event in events or ():
        if str(event.get("place") or "") != place or not place:
            continue
        kind = event.get("kind")
        if kind == "body_unable" and str(event.get("body")) != body_key:
            impacts.append({"impact": PEER_DOWN_IMPACT,
                            "certainty": WITNESS_CERTAINTY})
        elif kind in _PHYSICAL_RELIEF:
            mine = event.get("upkeep") in own_upkeeps
            gain = OWN_RESTORED_PLEASURE if mine else RESTORED_PLEASURE
            if gain > pleasure:
                pleasure = gain
                pleasure_why = "a failing condition held here came back " \
                    "into band" if mine else \
                    "a failing condition here came back into band"

    # WHAT HAPPENED TO THIS BODY, as opposed to around it. Competing on the
    # same `max` the relief branch uses, so `pain_why or pleasure_why` below
    # still lets a body under its floor be in pain rather than pleased.
    for kind in sorted(set(marks or ())):
        if kind not in BODY_MARKS:
            continue
        if kind == "accused":
            impacts.append({"impact": ACCUSED_IMPACT,
                            "certainty": ACCUSED_CERTAINTY})
        elif kind == "aided" and AIDED_PLEASURE > pleasure:
            pleasure = AIDED_PLEASURE
            pleasure_why = "somebody attended you here"
        elif kind == "posted" and POSTED_PLEASURE > pleasure:
            pleasure = POSTED_PLEASURE
            pleasure_why = "you were handed a duty you had not stood"

    pain = 0.0
    pain_why = ""
    for name, need in (held_needs or {}).items():
        gap = float(need.get("floor", 0.0)) - float(need.get("level", 1.0))
        if gap <= 0.0:
            continue
        proposed = min(1.0, gap * PAIN_PER_GAP)
        if proposed > pain:
            pain = proposed
            pain_why = f"{name} below its floor"

    why = pain_why or pleasure_why
    appraisal = {}
    if why and (pain > 0.0 or pleasure > 0.0):
        appraisal["somatic_impact"] = {
            "pain": round(pain, 4),
            "pleasure": round(pleasure, 4),
            "why": why,
        }
    return appraisal, impacts


def advance_feel(feel, bodies, needs, watch, posts, upkeeps, events, hours,
                 temper_of=temperament_of, *, fresh_marks=()):
    """One window of feeling, for every body with a reason to. Returns the
    new ``{body: {"hedonic", "stress"}}`` dict.

    ``temper_of`` is injectable so a measurement can run a flat-temperament
    arm against a varied one on otherwise identical windows; callers use the
    default.

    ``fresh_marks`` is ``charter_mark.advance_marks``' second return value —
    the ``(body, kind, by)`` rows set or refreshed THIS window. Not the
    store: a mark held for a week is a fact about the body, and appraising a
    standing fact every window is exactly what the comment below records
    costing 240 bodies a permanent strain floor. ``by`` is dropped here
    deliberately; who tended you does not change what being tended feels
    like, and not passing it is one less thing an appraisal can leak.
    """
    feel = normalize_feel(feel)
    hours = max(0.0, float(hours))
    units = hours * UNITS_PER_HOUR
    served = _served_by_body(watch, posts)

    # Who has anything to feel about. Everyone else is skipped entirely,
    # which is what keeps a quiet institution's feel dict empty and its
    # cost at nothing.
    marked = {}
    for row in fresh_marks or ():
        body_key, kind = str(row[0]), str(row[1])
        if kind in BODY_MARKS:
            marked.setdefault(body_key, set()).add(kind)
    stimulated = set(feel)
    failing_places = {str(u.get("place") or "")
                      for u in (upkeeps or {}).values()
                      if float(u.get("level", 1.0)) < float(
                          u.get("floor", 0.0))}
    event_places = {str(e.get("place") or "") for e in (events or ())
                    if e.get("kind") in _PHYSICAL_RELIEF
                    or e.get("kind") == "body_unable"}
    stirred = (failing_places | event_places) - {""}
    for key, body in (bodies or {}).items():
        if key in marked or str(body.get("place") or "") in stirred:
            stimulated.add(key)
        else:
            held = (needs or {}).get(key) or {}
            if any(float(n.get("floor", 0.0)) > float(n.get("level", 1.0))
                   for n in held.values()):
                stimulated.add(key)

    out = {}
    for key in sorted(stimulated):
        body = (bodies or {}).get(key)
        if body is None:
            continue
        held = (needs or {}).get(key) or {}
        appraisal, impacts = appraise_window(
            key, body.get("place"), upkeeps, events, held_needs=held,
            own_upkeeps=served.get(key), marks=marked.get(key, ()))
        if not impacts and not float(
                (appraisal.get("somatic_impact") or {}).get("pain") or 0.0):
            # A window with nothing wrong in it is APPRAISED AS SUCH.
            # `resolve_stress` defaults controllability and coping to 0.5 --
            # "unknown", correct for the character tier, where it is only
            # called on real beats. Called every window on residual state,
            # that unknown becomes a standing strain floor of reactivity x
            # 0.15 that never decays: measured, 240 bodies still carrying
            # strain 0.09 / load 0.16 after 480 QUIET hours, an anxiety
            # ledger for a famine long since over. The background tier
            # computed that nothing here is threatened; it says so.
            #
            # THE TEST IS "NOTHING ADVERSE", NOT "NOTHING AT ALL", and it was
            # the second until the `posted` mark arrived. A window whose only
            # content is GOOD -- a duty handed over, somebody tending you, a
            # condition back into band -- has an appraisal, so it used to
            # skip this branch and take the 0.5 unknown, and a body was
            # strained by being pleased. Measured on the one-body office
            # fixture: `posted` at hour 4 left the director carrying strain
            # 0.0952 at hour 48, spending rest 6% faster through
            # `STRAIN_REST_TOLL` and unavailable at the end of a run it used
            # to finish fit. The same was already true of the relief path and
            # nobody had a positive-only window to find it with.
            appraisal = dict(appraisal, controllability=1.0,
                             coping_potential=1.0)
        previous = feel.get(key) or {}
        temperament = temper_of(body)
        hedonic = resolve_hedonic(
            previous.get("hedonic"), appraisal,
            interoception_of(temperament), body_state(held),
            elapsed_units=units)
        stress = resolve_stress(
            previous.get("stress"), appraisal,
            stress_profile_of(temperament), hedonic,
            elapsed_units=units, goal_impacts=impacts)
        if _negligible(hedonic, stress):
            continue
        out[key] = {"hedonic": hedonic, "stress": stress}
    return out


def _negligible(hedonic, stress):
    return all(float(value) < NEGLIGIBLE for value in (
        hedonic.get("pain", 0.0), hedonic.get("pleasure", 0.0),
        hedonic.get("charge", 0.0), stress.get("activation", 0.0),
        stress.get("strain", 0.0), stress.get("load", 0.0)))


def strain_of(feel):
    """``{body: strain 0..1}`` for the bodies that carry any.

    The one felt quantity that acts on the world, and it acts through
    ``charter_needs.advance_needs``'s rest drift rather than through the
    planner — see ``STRAIN_REST_TOLL``.
    """
    out = {}
    for key, entry in (feel or {}).items():
        strain = float((entry.get("stress") or {}).get("strain") or 0.0)
        if strain > 0.0:
            out[key] = strain
    return out


def overloaded_bodies(feel):
    """Bodies whose stress model currently reports overload. Diagnostics."""
    return sorted(key for key, entry in (feel or {}).items()
                  if (entry.get("stress") or {}).get("overloaded"))


def felt_handoff(body_key, charter):
    """Everything the character tier needs to continue this interior.

    THE PROMOTION PAYLOAD, in the character pipeline's own vocabulary:
    ``hedonic``/``stress`` are ``psychology_runtime``'s persisted shapes,
    ``body_state`` is ``world/survival.py``'s vitals shape,
    ``interoception`` and ``stress_profile`` are the card fields under
    ``embodiment`` and ``psychology``. A copy, not a translation — there is
    nothing to keep in step because there is only one representation.

    ``stood`` is the service record: which posts this body actually stood
    and for how many windows. Not a project — adoption is a deliberation the
    model owns (`affect.apply_project_ops`) — but it is the EVIDENCE a
    promotion call needs to adopt one honestly: a body that stood the same
    post for a month has a life's shape worth deliberating about.
    """
    key = str(body_key)
    charter = charter if isinstance(charter, dict) else {}
    body = (charter.get("bodies") or {}).get(key) or {}
    entry = normalize_feel(charter.get("feel")).get(key) or {}
    temperament = temperament_of(dict(body, key=key))
    return {
        "body": key,
        "hedonic": dict(entry.get("hedonic") or {}),
        "stress": dict(entry.get("stress") or {}),
        "body_state": body_state((charter.get("needs") or {}).get(key) or {}),
        "interoception": interoception_of(temperament),
        "stress_profile": stress_profile_of(temperament),
        "stood": dict((charter.get("stood") or {}).get(key) or {}),
    }
