"""Rules that fire off a CHANGE, and the consequences they are allowed to have.

``docs/guides/RESEARCH.md`` §1.7.6 item 5, the last of the five taken from
Comme il Faut: *"Trigger Rules can be fired at any point and have cascading
effects in the Social State."* Charter had none. An act changed state and
nothing fired off the change, so the social layer only ever moved when the
planner or an author prodded it, and a consequence that ought to follow from
a thing having happened simply did not.

TWO INVARIANTS THIS MODULE EXISTS TO HOLD.

  * **The pass reads a CHANGE and never a state.** `fire_triggers` is handed
    a list of change rows and returns immediately when that list is empty, so
    a quiet window costs one falsy test. A pass that walked the charter
    looking for conditions to fire on would cost the institution's whole
    shape every window whether or not anything happened, which is the
    grows-with-time failure `charter_run`'s docstring forbids for events and
    which this layer would have re-introduced under a new name.
  * **A trigger fires on objective state and produces objective consequence.**
    An event that visibly happened between two people at a place, a situation
    between two co-present bodies, a mark on a body with a lifetime. WHO
    LEARNS of any of it is `charter_news.witness`'s separate question and is
    not asked here. That separation is the whole firewall: a rule that wants
    to move an opinion emits a witnessable event and the opinion forms next
    window from evidence a holder can cite, rather than a stance appearing in
    a head with nothing behind it.

WHAT THE PASS MAY READ, AND THE SIGNATURE IS THE ENFORCEMENT. `fire_triggers`
takes change rows and a body index (place and availability) and nothing else.
It is not handed ``minds``, ``judgments``, ``needs``, ``feel``,
``heard_blame``, ``roster`` or the charter, and this module imports none of
``charter_mind``, ``charter_social``, ``charter_feel``, ``charter_needs``,
``charter_talk`` or ``charter_observe``. Both facts are pinned by
`tests/test_charter_trigger.py`, because a firewall held by a signature is
checkable and one held by a docstring is not. The two sibling imports it does
have are both vocabularies rather than state: ``charter_practice._open``, so
an authored, a circumstantial and a triggered situation are the SAME record
and dedupe against each other, and ``charter_mark.MARKS``, so a rule cannot
coin a temporary fact with no lifetime.

A CHANGE ROW IS A CLOSED SHAPE (`CHANGE_FIELDS`) and a `where` clause may test
only `MATCHABLE`. That is deliberately narrower than "whatever the change
carries": an author who could match on a need level or a judgment axis would
have written a rule that reads a body's interior to decide what happens to
somebody else, which is exactly the leak this layer must not open. The closed
shape is also what makes the frame cheap to persist and restore.

`TRIGGER_EMITTABLE` IS A SECOND, TIGHTER ALLOWLIST THAN `charter_news`'s
`WITNESSABLE`, and the tightening is the point. `WITNESSABLE` also carries
kinds an author must not be able to forge -- `institution_order_executed`,
`report_confirmed`, `commitment_defaulted` -- and minting one from a rule
would put a false institutional fact into every head in the room at full
first-hand strength, with a stable news key two witnesses would agree on. So
the emittable set is only the kinds whose truth condition is exactly "this
visibly happened between these people at this place". Widening it is a
firewall change and should be treated as one.

ONE WINDOW OF LAG, AND IT IS NOT A BUG. A window deposits its changes and the
NEXT window fires on them, so a consequence lands 4-8 simulated hours after
its cause. It is the same lag `charter_run` already argues for judgments
("nobody revises their view of a person in the same instant they watch them
act"), and it is what keeps `step` a straight line: the pass's input is a
persisted, capped, restorable field rather than a growing pile of
mid-function locals. The pass runs BETWEEN `opportunities` and `enact` so a
situation it opens is actable in the window it opens -- see the placement
note there, which is a trap rather than a preference.

FOUR INDEPENDENT BOUNDS TERMINATE THE CASCADE, and they are here in one
function so a reader can check them without tracing the caller: a depth
carried on each change (`TRIGGER_DEPTH`), fire-once identity, a per-pair
refractory, and a per-window yield cap (`TRIGGER_YIELD_CAP`).

Pure and deterministic: no clock beyond what it is handed, no model, and
every draw is `hashlib` over the run's own seed the way `charter_run`'s
`ENCOUNTER_ODDS` draw is. `random` and process-salted `hash()` are both
unusable here because a checkpoint restore is a different process.
"""

from __future__ import annotations

import hashlib

from .charter_mark import BODY_MARKS, MARKS
from .charter_news import WITNESSABLE
from .charter_practice import _open


#: The three families a change may belong to, and the whole vocabulary of
#: `on`. `blame_landed` is the only SYNTHETIC one -- it is a delta on the
#: institution's blame counter rather than something the world emitted -- and
#: it exists because the counter moving is the most consequential state change
#: in this package that produced nothing at all.
CHANGE_FAMILIES = frozenset({"blame_landed", "event", "act"})

#: The closed shape of a change row. Nothing outside this may ride the frame,
#: which is what keeps the persisted field bounded and the firewall a
#: structural fact rather than a review item.
CHANGE_FIELDS = ("kind", "key", "at_hours", "place", "actor", "subject",
                 "about", "depth", "side")

#: What a `where` clause may test. Strictly narrower than `CHANGE_FIELDS`:
#: `kind` is already `on`, `key` is an identity rather than a property, and
#: `at_hours`/`depth` are the machinery's own bookkeeping. Matching a body
#: against a place, an actor, a subject or a named thing is the whole of what
#: an objective rule needs.
MATCHABLE = ("place", "actor", "subject", "about", "side")

#: Which SIDE of an event the institution's own body was on. Objective and
#: closed: ``dealt`` when the actor is one of ours, ``suffered`` when the
#: subject is, empty otherwise. It is what lets a creature's rule say "a
#: member of mine was killed" (`event:harm_done` where ``side`` is
#: ``suffered``) without naming a body, and it reads the body index alone.
SIDES = ("dealt", "suffered")

#: What a consequence may be. Three, and each one is objective: a situation, a
#: temporary fact about a body, a thing that visibly happened.
#:
#: There is no `set_judgment` and there never may be. A rule that wants to
#: move an opinion emits a witnessable event; `charter_news.witness` decides
#: who was present and `charter_social.update_judgments_from_minds` moves the
#: axes next window with a citable evidence id under its own idempotence
#: guard. Writing an axis here would produce a stance with no evidence to
#: cite, which is a leak wearing a convenience.
TRIGGER_OPS = frozenset({"open_practice", "set_mark", "emit",
                         "intervene", "settle_commitment"})

#: The two ops that move the INSTITUTION rather than a body: schedule a
#: physical intervention (`charter_intervene.INTERVENTION_OPS`, due at the
#: next window, applied where every other physical change is applied), or
#: settle an undertaking the institution holds (`charter_commitment`).
#: Fired by `fire_institution_rules`, a second pass under the same firewall
#: as `fire_triggers`, so the per-body pass keeps its signature and its
#: return shape. ``docs/design/DESIGN_CREATURES_AS_CHARTER.md`` §5.
INSTITUTION_OPS = frozenset({"intervene", "settle_commitment"})

#: The commitment states a rule may settle an open undertaking into.
SETTLE_STATES = frozenset({"fulfilled", "defaulted", "repudiated",
                           "released"})

#: The event kinds a rule may mint. See the allowlist paragraph in the module
#: docstring -- this is a subset of `charter_news.WITNESSABLE` and it is a
#: subset on purpose.
TRIGGER_EMITTABLE = frozenset({"aid_given", "harm_done"})

#: Who a consequence may be pointed at, named relative to the change. There is
#: deliberately no way to name a body literally: a rule that said "quarrel with
#: ramos" would be the instance-shaped rule this repo's CLAUDE.md forbids, and
#: it would be unportable between two stories that share nothing but the
#: engine.
#:
#: `nearby` is an available body standing where the change's own subject
#: stands, drawn from the run's seed. It is what lets a rule say "somebody
#: rounds on them" without the engine knowing who anybody is.
REFERENTS = frozenset({"actor", "subject", "nearby"})

#: How far a consequence may propagate from the change that caused it. A
#: change at or above this depth is skipped.
#:
#: MEASURED 2026-08-27 with one deliberately self-feeding authored rule
#: (`on: event:harm_done -> emit harm_done`, seeded by a single authored
#: `harm_done`) over 2,000 simulated hours of the SHIP fixture: at depth 1 the
#: rule produces 1 consequence, at 2 it produces 2, at 3 it produces 3, at 4 it
#: produces 4 -- exactly linear, because this bound is the ONLY thing stopping
#: it. The quiet control emits zero at every one of those settings, which is
#: what says the bound is doing the work rather than the fixture being dull.
#: 2 is taken because a consequence of a consequence is the shortest chain
#: that is recognisably a CASCADE, and every further link measured is the
#: second link repeated.
TRIGGER_DEPTH = 2

#: Rules an author may keep. A rulebase larger than this is the hand-authored
#: scale `docs/guides/RESEARCH.md` §1.7.6 explicitly REFUSES from Comme il
#: Faut ("over 5,000" social considerations): the scoring discipline is worth
#: taking and the authoring burden is not.
TRIGGER_CAP = 32

#: Consequences one rule may have per change. Three, so a rule reads as one
#: thing following from another rather than as a script.
TRIGGER_THEN_CAP = 3

#: Consequences the whole pass may produce in one window.
#:
#: MEASURED 2026-08-27 with the shipped defaults loaded, on three arms: a
#: simulated year of `big_town(40)` (2,190 windows, window 4.0, seed 3) fired
#: 0 consequences in total; a simulated month of `twin_towns(240)` driven into
#: famine (180 windows, window 4.0, seed 7) fired 3, maximum 2 in any one
#: window; a simulated quarter of `twin_towns(40)` in famine (547 windows)
#: fired 2, maximum 1. The 99th percentile is 0 on all three. So 8 never binds
#: in ordinary play and always binds on a rulebase that has gone wrong, which
#: is what a cap is for.
#:
#: IT IS ALSO THE ONLY THING HOLDING `_record_coarse_experiences`. That
#: function's `stood_through` loop writes one autobiographical row per (event
#: x body present), so every trigger-emitted event multiplies by the size of
#: the room. A runaway rulebase would blow `EXPERIENCE_CAP` (4,000) before it
#: blew the event log -- the quieter and worse of the two failures, and the
#: reason the cost test asserts experience-row growth and not only event
#: count.
TRIGGER_YIELD_CAP = 8

#: Refractory rows kept. Without a bound this is rules x ordered pairs, which
#: on `charter_worlds.big_town(1000)` is 32 x 10^6. With the expiry prune it is
#: bounded by `TRIGGER_YIELD_CAP` x windows-in-the-longest-refractory = 8 x 42
#: at a one-week refractory and a 4-hour window, so 336; 256 is that rounded
#: down to a number that binds only on a pathological rulebase.
TRIGGER_MEMORY_CAP = 256

#: Change rows one window may deposit for the next.
#:
#: A BUSY WINDOW LOSES ROWS, and that is the trade. Measured 2026-08-27 on a
#: famine week of `twin_towns(240)` (window 4.0, seed 7): the busiest window
#: produced 184 changes, mean 38.7, against 5.0 mean on `twin_towns(40)` over
#: a famine quarter. So on a large stressed institution a rule sees a
#: deterministic sample of the window rather than all of it -- the same trade
#: `EXPERIENCE_CAP` makes, and the reason the frame is capped at all is that
#: it is PERSISTED state and unbounded persisted state is how this package
#: gets hurt.
#:
#: THE CAP IS APPLIED ROUND-ROBIN ACROSS THE THREE FAMILIES rather than by
#: recency, and the measurement is the honest reason: it changed no outcome on
#: any arm measured (0 `blame_landed` rows would have been lost to a flat
#: most-recent cap on either famine fixture). It is here because the flat cap
#: SURVIVES ONLY BY AN ALPHABETICAL ACCIDENT -- all rows in a window share an
#: hour, so a recency sort degenerates to a sort by key, and `"act:" <
#: "blame_landed" < "event:"` is the only reason the one shipped default rule
#: is reachable on a window carrying 150 acts. Whether a rule ever gets a
#: chance must not depend on how its family name spells.
PENDING_CHANGE_CAP = 32

#: The rules that ship.
#:
#: ONE, and the count is the argument. Prose belongs to the model over cited
#: surfaces and the other four designs already gave every state change in this
#: package a direct producer in `charter_run` -- `aided` and `posted` and
#: `disgraced` are all minted where they happen, and a default trigger
#: re-minting one a window later would be a second writer of the same fact
#: that can only ever disagree with the first. What was left was a real dead
#: edge, and it is this one.
#:
#: `blame_opens_a_quarrel` closes it. `accuse` is offered only inside a
#: `quarrel`, and until 2026-08-27 `quarrel` opened only from `accuse`'s own
#: effect or from an author, so an accusation was unreachable in pure
#: simulation and every blame the institution attributed died in its register.
#: `charter_practice.opportunities` now opens it from the ledger ON SCREEN.
#: OFF screen it still does not: `quarrel` is not in `COARSE_PRACTICES` and
#: the offscreen branch passes no `blame`, and the measurement is design 4's
#: -- `twin_towns(240)` driven into famine for a simulated month recorded 48
#: bodies ever `posted`, 2 ever `disgraced`, and 0 ever `accused`. A blame that
#: lands where nobody is looking still lands on a person, and this is the
#: channel by which they find out.
#:
#: The refractory is a simulated week, matching `MARK_HOURS["accused"]`: the
#: recency window in which being rounded on is still a fact about you is the
#: right period for not being rounded on again over the same failure.
DEFAULT_TRIGGERS = (
    {
        "id": "blame_opens_a_quarrel",
        "on": "blame_landed",
        "refractory_hours": 168.0,
        "then": ({"op": "open_practice", "kind": "quarrel",
                  "a": "nearby", "b": "subject", "about": "subject"},),
    },
)


def _number(value, default=0.0):
    """A stored number, or the caller's default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _text(value, limit=120):
    return str(value or "")[:limit]


def _referent(value, default=""):
    name = str(value or "") or default
    return name if name in REFERENTS else ""


# ------------------------------------------------------------------- rules

def perceivable_change(on):
    """Could a body in the room have perceived the CAUSE of this change?

    THE `on` SIDE OF THE SAME ALLOWLIST `TRIGGER_EMITTABLE` IS THE `then` SIDE
    OF. Which kinds a rule may mint has been closed since this shipped; which
    changes it may mint them FROM was open, so the hole stayed reachable from
    the other end. Two rules were demonstrated on `.venv` 2026-08-27 and both
    normalized clean with no warning:

      * ``{"on": "blame_landed", "then": [{"op": "emit", "kind": "harm_done",
        ...}]}`` put a `harm_done` event into every head in the room at full
        first-hand strength off a move of the institution's private counter,
        and `charter_social.DEFAULT_SIGNALS` then moved trust/fear/suspicion
        in each of them, citing evidence no witness could have seen.
      * ``{"on": "event:post_unfilled", "then": [{"op": "set_mark", "mark":
        "accused", ...}]}`` left a body holding `accused` -- felt at
        `charter_feel`'s -0.6 and shown by `charter_mark.mark_view` -- with
        nothing said aloud, no accuser and `heard_blame` still empty.
        `post_unfilled` is the exact event `tests/test_charter_promote.py`
        calls "a conclusion in the institution's books that no one in a room
        could perceive."

    An act happens in front of whoever is standing there, so `act:` passes
    unconditionally. An event passes only where `charter_news.WITNESSABLE`
    says a body could have seen it -- the one authority for that question,
    read rather than copied, so a kind admitted there tomorrow is admitted
    here the same day. `blame_landed` is the register's own and never passes.

    `open_practice` is deliberately NOT held to this: opening a situation puts
    nothing in anybody's head, and every affordance inside one applies its own
    channel gate at act time (`charter_practice.grievance_against`).
    """
    family, _, kind = str(on or "").partition(":")
    if family == "act":
        return True
    return family == "event" and kind in WITNESSABLE


def _normalize_rule(index, raw):
    """One authored row, closed onto bounds. Refused rather than dropped.

    A refusal is a NOTICE and never a rewrite, the same contract
    `charter_intervene.normalize_interventions` holds: the row survives so
    `trigger_warnings` can render it and so an author can see what they
    wrote, and `fire_triggers` skips it entirely so it changes nothing.
    """
    row = {
        "id": _text(raw.get("id") or f"trigger:{index}"),
        "on": _text(raw.get("on")),
        "where": {},
        "odds": min(1.0, max(0.0, _number(raw.get("odds"), 1.0))),
        "refractory_hours": max(0.0, _number(raw.get("refractory_hours"))),
        "then": [],
    }
    refused = []
    if row["on"].split(":", 1)[0] not in CHANGE_FAMILIES:
        refused.append(f"unknown change kind {row['on']!r}")
    perceivable = perceivable_change(row["on"])
    for field, value in sorted((raw.get("where") or {}).items()):
        if str(field) in MATCHABLE:
            row["where"][str(field)] = _text(value)
        else:
            refused.append(f"a change carries no {str(field)!r} to match on")
    for op_raw in list(raw.get("then") or ())[:TRIGGER_THEN_CAP]:
        if not isinstance(op_raw, dict):
            continue
        op = str(op_raw.get("op") or "")
        if op not in TRIGGER_OPS:
            refused.append(f"unknown op {op!r}")
            continue
        if op == "open_practice":
            entry = {"op": op, "kind": _text(op_raw.get("kind"), 64),
                     "a": _referent(op_raw.get("a"), "nearby"),
                     "b": _referent(op_raw.get("b"), "subject"),
                     "about": _referent(op_raw.get("about"))}
            if not entry["kind"]:
                refused.append("open_practice names no practice kind")
                continue
            if not entry["a"] or not entry["b"]:
                refused.append(
                    f"open_practice wants two of {sorted(REFERENTS)}")
                continue
        elif op == "set_mark":
            mark = str(op_raw.get("mark") or "")
            if mark not in MARKS:
                refused.append(f"{mark!r} is not a mark with a lifetime")
                continue
            # `BODY_MARKS` is `charter_mark`'s allowlist of the marks whose
            # origin the marked body was PRESENT FOR, and a rule firing off a
            # change nobody perceived would mint one with no origin at all.
            # `disgraced` is unaffected: it is the register's own mark and is
            # register-scoped wherever it comes from.
            if mark in BODY_MARKS and not perceivable:
                refused.append(
                    f"{mark!r} is a mark its holder was present for, and "
                    f"{row['on']!r} is a change nobody in a room perceived")
                continue
            entry = {"op": op, "mark": mark,
                     "on": _referent(op_raw.get("on"), "subject"),
                     "by": _referent(op_raw.get("by"))}
            if not entry["on"]:
                refused.append(f"set_mark wants one of {sorted(REFERENTS)}")
                continue
        elif op == "intervene":
            from .charter_intervene import normalize_interventions
            raw_row = op_raw.get("intervention")
            if not isinstance(raw_row, dict):
                refused.append("intervene carries no intervention")
                continue
            rows = normalize_interventions([dict(raw_row, at_hours=0.0)])
            if not rows or rows[0].get("refused"):
                refused.append("intervene: %s" % (
                    rows[0]["refused"] if rows else "unreadable"))
                continue
            entry = {"op": op, "intervention": {
                k: v for k, v in rows[0].items()
                if k not in ("id", "at_hours")}}
            entry["intervention"]["delay_hours"] = max(
                0.0, _number(op_raw.get("delay_hours")))
        elif op == "settle_commitment":
            state = str(op_raw.get("state") or "")
            if state not in SETTLE_STATES:
                refused.append(
                    f"settle_commitment cannot settle into {state!r}")
                continue
            entry = {"op": op, "state": state,
                     "kind": _text(op_raw.get("kind"), 64)}
        else:
            kind = str(op_raw.get("kind") or "")
            if kind not in TRIGGER_EMITTABLE:
                refused.append(
                    f"a trigger may not emit {kind!r}; emittable is "
                    f"{sorted(TRIGGER_EMITTABLE)}")
                continue
            if not perceivable:
                refused.append(
                    f"a trigger may not emit from {row['on']!r}, which is a "
                    f"change nobody in a room perceived")
                continue
            entry = {"op": op, "kind": kind,
                     "actor": _referent(op_raw.get("actor"), "actor"),
                     "subject": _referent(op_raw.get("subject"), "subject")}
            if not entry["actor"]:
                refused.append(f"emit wants one of {sorted(REFERENTS)}")
                continue
        row["then"].append(entry)
    if refused:
        row["refused"] = "; ".join(refused)[:240]
    return row


def normalize_triggers(stored):
    """Authored rows merged over `DEFAULT_TRIGGERS`, BY ID.

    A row whose `then` is empty is KEPT rather than dropped: writing
    ``{"id": "blame_opens_a_quarrel", "on": "blame_landed", "then": []}`` is
    how an author switches a default off, exactly as `social_norms.signals`
    overrides `charter_social.DEFAULT_SIGNALS`. It also means a default rule
    is a compatibility surface and not a tweak -- changing one changes every
    saved charter's behaviour on its next load.
    """
    rows = {}
    for index, raw in enumerate(DEFAULT_TRIGGERS):
        row = _normalize_rule(index, raw)
        rows[row["id"]] = row
    for index, raw in enumerate(stored or ()):
        if not isinstance(raw, dict):
            continue
        row = _normalize_rule(index, raw)
        rows[row["id"]] = row
    return [rows[key] for key in sorted(rows)][:TRIGGER_CAP]


def trigger_warnings(stored):
    """Author-facing notices. Validation belongs in the authoring surface on
    the day the field lands, not afterwards -- a rule that silently does
    nothing is the empty-psychology-field failure `CLAUDE.md` records, which
    shows up fifty beats later looking like a model problem."""
    return [f"{row['id']}: {row['refused']}"
            for row in normalize_triggers(stored) if row.get("refused")]


# ----------------------------------------------------------------- changes

def change_key(kind, at_hours, place, actor, subject, about=""):
    """The stable identity of one change. Two windows cannot collide because
    the hour is in it, and a checkpoint restore reproduces it exactly because
    nothing in it is process-salted."""
    return "%s|%0.4f|%s|%s|%s|%s" % (
        kind, float(at_hours), place, actor, subject, about)


def _change(kind, at_hours, place, actor, subject, about="", depth=0,
            side=""):
    row = {
        "kind": str(kind), "at_hours": round(_number(at_hours), 6),
        "place": _text(place), "actor": _text(actor),
        "subject": _text(subject), "about": _text(about),
        "depth": max(0, int(depth)),
        "side": side if side in SIDES else "",
    }
    row["key"] = change_key(row["kind"], row["at_hours"], row["place"],
                            row["actor"], row["subject"], row["about"])
    return row


def _row_for_event(event, at_hours=0.0, depth=0, bodies=None):
    """One event as a change. `actor`/`body` are the same body on every event
    kind this package emits (`charter_run._social_events` writes all three of
    `about`, `actor` and `body`), and taking either means a rule matches the
    same way whichever writer minted the row. ``bodies`` decides `side`."""
    actor = str(event.get("actor") or event.get("body") or "")
    subject = str(event.get("subject") or "")
    side = ""
    if bodies:
        if actor and actor in bodies:
            side = "dealt"
        elif subject and subject in bodies:
            side = "suffered"
    return _change(
        "event:" + str(event.get("kind") or ""),
        event.get("at_hours", at_hours), event.get("place"), actor, subject,
        event.get("upkeep") or event.get("post") or event.get("good") or "",
        depth=depth, side=side)


def normalize_pending_changes(stored):
    """Any stored shape onto the closed one, capped."""
    rows = []
    for raw in (stored or ()):
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "")
        if kind.split(":", 1)[0] not in CHANGE_FAMILIES:
            continue
        rows.append(_change(kind, raw.get("at_hours"), raw.get("place"),
                            raw.get("actor"), raw.get("subject"),
                            raw.get("about"), raw.get("depth") or 0,
                            str(raw.get("side") or "")))
    return _cap_changes(rows)


def _cap_changes(rows):
    """`PENDING_CHANGE_CAP` rows, round-robin across the three families.

    See the constant. A flat recency cap starves `blame_landed` on exactly
    the busy windows it exists to fire on.
    """
    if len(rows) <= PENDING_CHANGE_CAP:
        return sorted(rows, key=lambda row: (row["at_hours"], row["key"]))
    families = {}
    for row in rows:
        families.setdefault(row["kind"].split(":", 1)[0], []).append(row)
    queues = [sorted(rows, key=lambda row: (-row["at_hours"], row["key"]))
              for _, rows in sorted(families.items())]
    kept, index = [], 0
    while len(kept) < PENDING_CHANGE_CAP and any(queues):
        queue = queues[index % len(queues)]
        if queue:
            kept.append(queue.pop(0))
        else:
            queues = [q for q in queues if q]
            continue
        index += 1
    return sorted(kept, key=lambda row: (row["at_hours"], row["key"]))


def changes_from(*, events=(), acts=(), blamed=(), bodies=None, at_hours=0.0,
                 depths=None):
    """This window's objective changes, for the next window to fire on.

    Three sources and nothing else: what the world emitted, what bodies did,
    and whose name the institution's blame counter moved against.
    ``depths`` carries the propagation depth of the events this pass itself
    minted, keyed by `change_key`, so a self-feeding rule terminates at
    `TRIGGER_DEPTH` instead of running until a cap catches it.
    """
    bodies = bodies or {}
    depths = depths or {}
    rows = []
    for event in events or ():
        if not isinstance(event, dict):
            continue
        row = _row_for_event(event, at_hours, bodies=bodies)
        row["depth"] = max(0, int(depths.get(row["key"], 0)))
        rows.append(row)
    for act in acts or ():
        actor = str(act.get("actor") or "")
        if not actor:
            continue
        # A BODY'S OWN CHOICE RE-ENTERS AT DEPTH ZERO, deliberately. Depth
        # measures how far a consequence has propagated from the world's own
        # change, and a person deciding to do something is a new cause rather
        # than a continuation of the old one. The path that can actually
        # self-feed is `emit`, which mints a change directly and carries its
        # depth; `open_practice` mints no change at all, so opening a
        # situation cannot cascade even in principle.
        rows.append(_change(
            "act:" + str(act.get("act") or ""), at_hours,
            (bodies.get(actor) or {}).get("place"), actor,
            act.get("other")))
    for body in blamed or ():
        body = str(body or "")
        if not body:
            continue
        rows.append(_change("blame_landed", at_hours,
                            (bodies.get(body) or {}).get("place"), "", body))
    return _cap_changes(rows)


def prune_trigger_last(stored, rules, at_hours):
    """Refractory rows still capable of suppressing anything.

    Pruned to the longest `refractory_hours` in the rule set rather than to
    each rule's own: a row is keyed by rule already, but reading the rules to
    prune per-rule would make the store's size depend on the order the two
    fields are normalized in, and the horizon bound is what the cap rests on.
    """
    horizon = max([0.0] + [row["refractory_hours"] for row in rules])
    at = _number(at_hours)
    kept = {}
    for key, when in (stored or {}).items():
        when = _number(when)
        if horizon and at - when >= horizon:
            continue
        kept[str(key)] = when
    if len(kept) <= TRIGGER_MEMORY_CAP:
        return kept
    newest = sorted(kept.items(), key=lambda item: (-item[1], item[0]))
    return dict(newest[:TRIGGER_MEMORY_CAP])


# -------------------------------------------------------------------- pass

def _draw(*parts):
    """0..1 from the run's own seed. `hashlib` over the seed exactly as
    `charter_run`'s `ENCOUNTER_ODDS` draw does -- `random` has no seed here
    and `hash()` is salted per process, and a checkpoint restore is a
    different process."""
    digest = hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / float(0xFFFFFFFF)


def fire_triggers(changes, bodies, at_hours, *, seed=0, rules=None,
                  last_fired=None):
    """Fire what the last window's changes license.

    Returns ``(events, opened, mark_onsets, last_fired, fired, depths)``:
    events to extend the window's list with, practices to merge into the
    practice set, ``{mark: [(body, by)]}`` for `charter_mark.advance_marks`,
    the refractory store carried forward, the ``rule|change`` ids that fired,
    and the propagation depth of each minted event for `changes_from`.

    THE PARAMETER LIST IS THE FIREWALL. Change rows and a body index; no
    minds, no judgments, no needs, no felt state, no blame register, no
    charter. A trigger decides from what objectively happened, and every
    question about who KNOWS it is asked somewhere else.
    """
    memory = dict(last_fired or {})
    changes = normalize_pending_changes(changes)
    if not changes:
        # The cheap path, and it is the ordinary one. A window in which
        # nothing crossed a floor, nobody acted and no blame landed deposits
        # an empty frame, so the next window's whole cost here is this test.
        return [], {}, {}, memory, [], {}
    rules = normalize_triggers(rules)
    by_kind = {}
    for rule in rules:
        if rule.get("refused") or not rule["then"]:
            continue
        by_kind.setdefault(rule["on"], []).append(rule)
    if not by_kind:
        return [], {}, {}, memory, [], {}

    bodies = bodies or {}
    at = _number(at_hours)
    events, opened, onsets, fired, depths = [], {}, {}, [], {}
    company = {}
    for key, body in sorted(bodies.items()):
        if body.get("available"):
            company.setdefault(str(body.get("place") or ""), []).append(key)

    def _place_of(key):
        return str((bodies.get(key) or {}).get("place") or "")

    def _resolve(referent, change, rule):
        if referent == "actor":
            return str(change["actor"])
        if referent == "subject":
            return str(change["subject"])
        if referent != "nearby":
            return ""
        anchor = change["subject"] or change["actor"]
        place = _place_of(anchor) or change["place"]
        here = [key for key in company.get(place, ()) if key != anchor]
        if not here:
            return ""
        # Seeded over the change's own identity, so a restored run picks the
        # same body and a busy window does not always pick the same one.
        return here[int(_draw(seed, rule["id"], change["key"], "nearby")
                        * len(here)) % len(here)]

    yielded = 0
    for change in changes:
        if yielded >= TRIGGER_YIELD_CAP:
            break
        if int(change["depth"]) >= TRIGGER_DEPTH:
            continue
        for rule in by_kind.get(change["kind"], ()):
            if yielded >= TRIGGER_YIELD_CAP:
                break
            if any(change.get(field) != value
                   for field, value in rule["where"].items()):
                continue
            # THE PAIR IS THE CHANGE'S OWN, not the consequence's. A rule that
            # rounded on the same body through a different bystander every
            # window would defeat its own refractory, which is the failure the
            # store exists to prevent.
            memory_key = "%s|%s|%s" % (rule["id"], change["actor"],
                                       change["subject"])
            since = memory.get(memory_key)
            if since is not None and rule["refractory_hours"] and \
                    at - _number(since) < rule["refractory_hours"]:
                continue
            if rule["odds"] < 1.0 and \
                    _draw(seed, at, rule["id"], change["key"]) >= rule["odds"]:
                continue
            produced = 0
            for op in rule["then"]:
                if yielded >= TRIGGER_YIELD_CAP:
                    break
                if op["op"] in INSTITUTION_OPS:
                    # `fire_institution_rules`' business, under its own
                    # refractory key; this pass neither fires nor counts it.
                    continue
                if op["op"] == "open_practice":
                    a = _resolve(op["a"], change, rule)
                    b = _resolve(op["b"], change, rule)
                    if not a or not b or a == b:
                        continue
                    place = _place_of(a)
                    # CO-PRESENCE AT OPENING TIME, the same gate every
                    # affordance applies at act time. A situation between two
                    # people in different rooms offers nothing to either of
                    # them and merely occupies a slot in `PRACTICE_CAP`.
                    if not place or place != _place_of(b):
                        continue
                    if not (bodies.get(a) or {}).get("available"):
                        continue
                    about = (_resolve(op["about"], change, rule)
                             if op["about"] else "")
                    # `_open` rather than a second key format, so an authored,
                    # a circumstantial and a triggered situation are the same
                    # record and dedupe against each other.
                    key, entry = _open(op["kind"], place, {"a": a, "b": b},
                                       at, about=about)
                    opened[key] = entry
                elif op["op"] == "set_mark":
                    body = _resolve(op["on"], change, rule)
                    if not body or body not in bodies:
                        continue
                    by = _resolve(op["by"], change, rule) if op["by"] else ""
                    onsets.setdefault(op["mark"], []).append((body, by))
                else:
                    actor = _resolve(op["actor"], change, rule)
                    if not actor or actor not in bodies:
                        continue
                    subject = (_resolve(op["subject"], change, rule)
                               if op["subject"] else "")
                    event = {
                        "kind": op["kind"], "at_hours": round(at, 6),
                        "place": _place_of(actor) or change["place"],
                        # `about`/`actor`/`body` all name the acting body, the
                        # shape `charter_run._social_events` already writes and
                        # `charter_social`'s signal reader already takes.
                        "about": actor, "actor": actor, "body": actor,
                        "subject": subject,
                        # Provenance for the author. A rule id names no person
                        # and no interior; `charter_news.news_claim` builds a
                        # fixed dict, so it reaches no mind.
                        "trigger": rule["id"],
                    }
                    events.append(event)
                    depths[_row_for_event(event, at)["key"]] = \
                        int(change["depth"]) + 1
                produced += 1
                yielded += 1
            if produced:
                memory[memory_key] = at
                fired.append("%s|%s" % (rule["id"], change["key"]))
    return events, opened, onsets, memory, fired, depths


def fire_institution_rules(changes, bodies, at_hours, *, seed=0, rules=None,
                           last_fired=None):
    """Fire what the last window's changes license the INSTITUTION to do.

    Returns ``(ops, last_fired, fired)``: resolved institution ops for
    `charter_run.step` to apply (an ``intervene`` row carries the
    intervention to schedule, a ``settle_commitment`` row the state and
    kind), the refractory store carried forward, and the ``rule|change``
    ids that fired. THE SAME PARAMETER LIST AS `fire_triggers`, and the
    same reason: change rows and a body index, nothing that is inside a
    head. Refractory rows are keyed apart (``inst|``) so a rule carrying
    both a body op and an institution op fires each on its own clock.
    """
    memory = dict(last_fired or {})
    changes = normalize_pending_changes(changes)
    if not changes:
        return [], memory, []
    rules = normalize_triggers(rules)
    by_kind = {}
    for rule in rules:
        if rule.get("refused"):
            continue
        if not any(op["op"] in INSTITUTION_OPS for op in rule["then"]):
            continue
        by_kind.setdefault(rule["on"], []).append(rule)
    if not by_kind:
        return [], memory, []
    at = _number(at_hours)
    ops, fired = [], []
    yielded = 0
    for change in changes:
        if yielded >= TRIGGER_YIELD_CAP:
            break
        if int(change["depth"]) >= TRIGGER_DEPTH:
            continue
        for rule in by_kind.get(change["kind"], ()):
            if yielded >= TRIGGER_YIELD_CAP:
                break
            if any(change.get(field) != value
                   for field, value in rule["where"].items()):
                continue
            memory_key = "inst|%s|%s|%s" % (rule["id"], change["actor"],
                                            change["subject"])
            since = memory.get(memory_key)
            if since is not None and rule["refractory_hours"] and \
                    at - _number(since) < rule["refractory_hours"]:
                continue
            if rule["odds"] < 1.0 and \
                    _draw(seed, at, rule["id"], change["key"], "inst") \
                    >= rule["odds"]:
                continue
            produced = 0
            for op in rule["then"]:
                if op["op"] not in INSTITUTION_OPS:
                    continue
                if op["op"] == "intervene":
                    row = dict(op["intervention"])
                    delay = float(row.pop("delay_hours", 0.0) or 0.0)
                    row["at_hours"] = round(at + delay, 6)
                    row["id"] = "trigger:%s:%0.4f" % (rule["id"], at)
                    row["cause"] = str(row.get("cause") or rule["id"])
                    ops.append({"op": "intervene", "intervention": row,
                                "rule": rule["id"], "change": change["key"]})
                else:
                    ops.append({"op": "settle_commitment",
                                "state": op["state"], "kind": op["kind"],
                                "rule": rule["id"], "change": change["key"]})
                produced += 1
                yielded += 1
            if produced:
                memory[memory_key] = at
                fired.append("%s|%s" % (rule["id"], change["key"]))
    return ops, memory, fired


def trigger_view(rules, pending_changes=None, last_fired=None):
    """Author-only: what is loaded, what it refused, and what is in flight.

    Nothing here reaches a mind. `pending_changes` is a count rather than the
    rows: the rows are objective and would be safe, but a diagnostic that
    grows with the window is how a payload becomes a transcript.
    """
    rows = normalize_triggers(rules)
    return {
        "rules": [{"id": row["id"], "on": row["on"],
                   "consequences": len(row["then"]),
                   **({"refused": row["refused"]} if row.get("refused")
                      else {})}
                  for row in rows],
        "pending_changes": len(normalize_pending_changes(pending_changes)),
        "refractory_rows": len(last_fired or {}),
    }


__all__ = [
    "CHANGE_FAMILIES", "CHANGE_FIELDS", "DEFAULT_TRIGGERS", "INSTITUTION_OPS",
    "MATCHABLE", "PENDING_CHANGE_CAP", "REFERENTS", "SETTLE_STATES", "SIDES",
    "TRIGGER_CAP", "TRIGGER_DEPTH", "TRIGGER_EMITTABLE", "TRIGGER_MEMORY_CAP",
    "TRIGGER_OPS", "TRIGGER_THEN_CAP", "TRIGGER_YIELD_CAP", "change_key",
    "changes_from", "fire_institution_rules", "fire_triggers",
    "normalize_pending_changes", "normalize_triggers", "perceivable_change",
    "prune_trigger_last", "trigger_view", "trigger_warnings",
]
