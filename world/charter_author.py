"""The author-switch: conduct written from outside, landing inside.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §12a. A background body
that walks on screen is not handed over to anything: its needs keep
draining, its feeling keeps resolving, its position keeps being its
position. What changes for a stretch is who WRITES ITS CONDUCT — and this
module is that switch, for the stretch between planning windows where a
scene actually happens.

Two directions, deliberately asymmetric, and the asymmetry is the firewall
shaping the API rather than a wart on it:

  * **A voiced BODY acts** (the scene manager writes a background NPC's
    line): the act resolves through ``charter_practice``'s own builders and
    effects — the identical path a utility-chosen act takes, with the
    identical licences. There is no parallel apply-function to drift from
    the chooser's, which is §12a's first requirement, and an act the state
    does not license is refused with a reason, never applied and never
    silently dropped.
  * **A FIGURE acts** (the player or a major character does something to a
    body): the figure has no mind here — its knowledge lives in the
    engine's own character machinery, and simulating its uptake would be a
    second copy of a mind that already exists. So a figure's acts touch
    only what a body could actually receive from them: a greeting opens the
    situation, a telling arrives through ``charter_mind.hear_claim`` — the
    ONE uptake door, same retention, same regard scaling, same
    stronger-holding-wins rule — an accusation lands in ``heard_blame``,
    a tending services a need. Nothing writes ``minds[figure]``, ever.

Situations open by circumstance here exactly as they do in
``opportunities``: an author bringing two people into speaking distance IS
the circumstance a greeting exists for, so a fresh encounter does not
require a planning window to have noticed the pair first. The situation
opened is the same situation, with the same key, that the window would have
opened — an authored meeting and a simulated one leave the same record.

Pure, like the rest of the package: takes a charter, returns a new charter
and a record. Commit is the reduction point that decides whether the record
becomes a ``world_events`` row; nothing here writes storage.
"""

from __future__ import annotations

import re

from .charter_commitment import (
    OPEN_STATES, answer_commitment, normalize_commitments, open_commitment)
from .charter_economy import normalize_economy, quote, trade
from .charter_figure import figure_claim
from .charter_mark import advance_marks
from .charter_mind import hear_claim
from .charter_model import normalize_charter
from .charter_politics import (NEUTRAL_REGARD, normalize_politics,
                               regard_map, regard_value)
from .charter_practice import (
    ASKED_RETENTION,
    REFUSED_ABSENT,
    REFUSED_NO_SITUATION,
    REFUSED_OUTSIDE_LICENCE,
    REFUSED_UNABLE,
    _by_body,
    _offer_for,
    landed_effect,
    _open,
    _state_of,
    _whereabouts,
    normalize_practices,
    offers,
)

#: Acts a figure can author toward a body. The body-actor set is whatever
#: `charter_practice._AFFORDANCES` offers — one vocabulary, read from the
#: same table the chooser reads.
#:
#: The second row is what a player actually does to a townsperson and what
#: the first row could not carry (Harrowmere playtest, 2026-09-02: seven
#: requests, two offers, a promise and a handed letter reached nobody as an
#: act). Each is stated as the class the ENGINE already has a ledger for --
#: an order and a favour and a bargain are commitments, a trade is the
#: economy, a gift is carriage -- so a body answers with the machinery it
#: has rather than with prose nothing checks.
FIGURE_ACTS = ("greet", "ask", "tell", "accuse", "tend",
               "order", "request", "bargain", "promise", "trade", "give")

#: What a body's answer to a figure's act is called, in the record and in
#: the commitment lifecycle behind it. Closed and engine-owned.
ANSWERS = ("obeyed", "refused", "granted", "declined", "accepted", "heard",
           "quoted", "taken")

#: A body's regard for the one ORDERING it, below which a standing order is
#: refused rather than obeyed. Regard is clamped to [REGARD_FLOOR 0.3,
#: REGARD_CEILING 1.6] with NEUTRAL_REGARD 1.0 the stranger's default, so a
#: superior a body merely dislikes is still obeyed; one it holds in
#: contempt is not. Named so it can be argued with.
ORDER_REFUSAL_REGARD = 0.6

#: Regard at or above which a FAVOUR or a BARGAIN is taken up. Neutral, so
#: an unpressed body grants a stranger's request and a body that thinks
#: less of you declines. The other two refusals are not regard at all: a
#: need under its floor, and an undertaking you already owe this body.
FAVOUR_REGARD_FLOOR = NEUTRAL_REGARD

#: Which of the Director's public speech-act kinds is which figure act.
#: The kinds are the Director's own closed vocabulary
#: (`agents.director._PUBLIC_SPEECH_ACTS`), so this is a map between two
#: schemas the engine owns, not a reading of prose. A kind absent here is
#: not an act toward the body -- a question is answered by the voice, a
#: greeting by the greeting affordance the evidence path already opens.
FIGURE_ACT_OF_SPEECH = {
    "command": "order",
    "request": "request",
    "offer": "bargain",
    "bargain": "bargain",
    "promise": "promise",
}


def _refusal(actor, act, other, reason):
    return {"actor": str(actor), "act": str(act), "other": str(other),
            "refused": reason}


def _pair_situations(actor, other, place, minds, needs, bodies, practices,
                     at_hours):
    """The situations this pair's circumstance licenses, opened if absent.

    The same kinds `opportunities` opens, for the one pair the author has
    brought together: a greeting between strangers, a conversation between
    acquaintances, a tending over somebody down. Deterministic keys, so an
    authored meeting and a window-opened one are the same situation.
    """
    opened = {}
    known = (minds.get(actor) or {}).get(other)
    kind = "converse" if known else "greeting"
    key, entry = _open(kind, place, {"a": actor, "b": other}, at_hours)
    if key not in practices:
        opened[key] = entry
    target = bodies.get(other)
    if target is not None and not target.get("available") \
            and (needs or {}).get(other):
        key, entry = _open("tending", place, {"a": actor, "b": other},
                           at_hours, about=other)
        if key not in practices:
            opened[key] = entry
    return opened


def authored(charter, actor, act, other, claim=None, retention=None, *,
             terms="", source_id="", thing="", good="", quantity=1.0,
             direction="buy"):
    """One authored act, through the same machinery a chosen one uses.

    Returns ``(charter, record)`` — the record carries ``line`` when the act
    landed and ``refused`` with a reason when the state does not license it.
    A refused act changes nothing: the returned charter is the input,
    normalized, and a test pins that as byte-identical.

    ``claim`` is required only for a FIGURE telling a body something: the
    content of an authored telling comes from the author, and it arrives as
    a claim — provisional, decaying, refusable — through the same uptake
    door a body-to-body telling uses. ``retention`` defaults to
    ``ASKED_RETENTION``: a body in conversation with you is listening.

    The keyword arguments belong to the figure acts that carry content:
    ``terms`` and ``source_id`` to an order, request, bargain or promise
    (the undertaking's words and the utterance it rode in on, which
    together key the commitment record); ``good``, ``quantity`` and
    ``direction`` to a trade; ``thing`` to a gift. A body's answer lands in
    ``record["answer"]``, one of `ANSWERS`, with ``reason`` when it is a
    refusal.
    """
    charter = normalize_charter(charter)
    actor, act, other = str(actor), str(act or ""), str(other or "")
    at = float(charter["clock_hours"])

    bodies = charter["bodies"]
    figures = charter["figures"]
    minds = charter["minds"]
    needs = charter["needs"]
    politics = normalize_politics(charter.get("politics"))
    regard = dict(politics.get("regard") or {})
    blame = dict(politics.get("blame") or {})
    practices = normalize_practices(charter.get("practices"))
    heard_blame = {k: set(v) for k, v in
                   (charter.get("heard_blame") or {}).items()}
    # Snapshotted BEFORE `_figure_act`, which writes into `heard_blame`
    # directly rather than through `state`. The `accused` onset below is the
    # delta on the merged set for exactly that reason: a figure's accusation
    # and a body's arrive by two different doors and both are the same fact.
    heard_before = {k: set(v) for k, v in heard_blame.items()}

    state = _state_of(bodies, minds, needs, regard, blame, at,
                      figures=figures,
                      experiences=charter.get("experiences"),
                      served_beside=charter.get("served_beside"),
                      judgments=charter.get("judgments"),
                      commitments=charter.get("commitments"))

    # The ledgers the figure acts answer through. Read here, written back
    # below only when an act says it changed them, so the byte-identity a
    # refused act promises still holds.
    stores = {
        "commitments": normalize_commitments(charter.get("commitments")),
        "economy": normalize_economy(charter.get("economy")),
        "posts": charter.get("posts") or {},
        "watch": charter.get("watch") or {},
        "bindings": charter.get("bindings") or {},
    }

    if actor in bodies:
        record = _body_act(actor, act, other, bodies, state, practices,
                           minds, needs, at)
    elif actor in figures:
        record = _figure_act(actor, act, other, figures, bodies, state,
                             practices, minds, needs, heard_blame, at,
                             claim=claim, retention=retention, stores=stores,
                             terms=terms, source_id=source_id, thing=thing,
                             good=good, quantity=quantity,
                             direction=direction)
    else:
        record = _refusal(actor, act, other, REFUSED_ABSENT)

    if record.get("refused"):
        return charter, record
    for key in ("commitments", "economy"):
        if record.pop("_%s" % key, None) is not None:
            charter[key] = stores[key]

    for key, entry in state["spawned"]:
        practices.setdefault(key, entry)
    for key in state["closed"]:
        practices.pop(key, None)
    for subject, tellers in state["heard_blame"].items():
        heard_blame.setdefault(subject, set()).update(tellers)

    # THE SAME MARKS THE ENACT PATH MINTS (`RESEARCH.md` §1.7.6 item 4), from
    # the same two origins, because an authored act and a chosen one leave the
    # same record -- that is this module's whole contract. Without it the
    # accusation a FIGURE makes would set `heard_blame` and no mark, and the
    # next `step` would see no delta because the store had already absorbed
    # the telling: measured, a figure accusing a body is today the ONLY
    # reachable accusation outside a charter whose register already blames
    # somebody, so the author path is where most of them come from.
    #
    # `at` rather than `at + hours`: no time passes in an authored act, so the
    # onset hour is the clock the store will be pruned against next window.
    #
    # AND FILTERED BY `bindings`, exactly as `charter_run.step` filters its
    # four onset lists (`charter_run.py` §"AND FILTERED BY `external`") and as
    # `charter_runtime.bind_promoted_character` pops the store at binding: a
    # promoted body's interior has exactly one owner, and a Charter mark is a
    # scoring bias, which is cognition. Without this the author path was the
    # one writer of the store that did not check -- verified by execution on
    # the yard fixture: with `bindings = {"raul": ...}`,
    # `authored(charter, "ilse", "accuse", "raul")` returned
    # `marks = {"raul": {"accused": ...}}`, which then rode `normalize_charter`
    # (it filters to live `bodies`, not to unbound ones) onto
    # `charter_log.scene_ledger`'s presence slice, surviving the promotion
    # purge that had already run.
    # A gift is aid visibly given, the same mark a tending leaves: the class
    # is "somebody did something for this body in front of everyone", and
    # the engine's word for that was already `aided`.
    external = set((charter.get("bindings") or {}).keys())
    aided = [(other, actor)] if record.get("act") in ("tend", "give") \
        and other in bodies and other not in external else []
    accused = sorted(
        (subject, sorted(tellers - heard_before.get(subject, set()))[0])
        for subject, tellers in heard_blame.items()
        if tellers - heard_before.get(subject, set())
        and subject not in external)
    charter["marks"] = advance_marks(
        charter.get("marks"), at, aided=aided, accused=accused)[0]

    charter["practices"] = practices
    charter["minds"] = minds
    charter["needs"] = needs
    charter["heard_blame"] = {k: sorted(v) for k, v in heard_blame.items()}
    charter["politics"] = {"regard": regard,
                           "standing": dict(politics.get("standing") or {}),
                           "blame": blame}
    return charter, record


def _body_act(actor, act, other, bodies, state, practices, minds, needs, at):
    body = bodies.get(actor)
    if not body.get("available"):
        return _refusal(actor, act, other, REFUSED_UNABLE)
    place = _whereabouts(actor, state)
    if place and place == _whereabouts(other, state):
        practices.update(_pair_situations(
            actor, other, place, minds, needs, bodies, practices, at))
    offer, practice, reason = _offer_for(
        actor, act, other, _by_body(practices).get(actor, ()), state)
    if offer is None:
        return _refusal(actor, act, other, reason)
    line, subject = landed_effect(offer[1]())
    if not line:
        # The builder licensed the act but the effect found nothing to do —
        # a telling the listener already held stronger. Still conduct; the
        # record says what was attempted rather than pretending silence.
        line = f"{actor} {act} {other}".strip()
    practice["last_effect_at"] = at
    record = {"actor": actor, "act": act, "other": other, "line": line}
    if subject:
        record["subject"] = subject
    return record


def _figure_act(actor, act, other, figures, bodies, state, practices, minds,
                needs, heard_blame, at, claim=None, retention=None, *,
                stores=None, terms="", source_id="", thing="", good="",
                quantity=1.0, direction="buy"):
    figure = figures[actor]
    target = bodies.get(other)
    if target is None:
        return _refusal(actor, act, other, REFUSED_ABSENT)
    if act not in FIGURE_ACTS:
        return _refusal(actor, act, other, REFUSED_NO_SITUATION)
    place = _whereabouts(actor, state)
    if not place or place != _whereabouts(other, state):
        return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)
    stores = stores or {}

    if act in ("order", "request", "bargain", "promise", "trade", "give"):
        # Every one of these is a turn toward the body, so the situation a
        # conversation needs is open and warm before the act itself lands,
        # exactly as `ask` keeps it. Opened here and left open on refusal:
        # a refused dealing is still an exchange that happened.
        key, entry = _open("converse", place, {"a": other, "b": actor}, at)
        practices.setdefault(key, entry)
        practices[key]["last_effect_at"] = at
        return _figure_dealing(
            actor, act, other, target, state, needs, at, stores,
            terms=terms, source_id=source_id, thing=thing, good=good,
            quantity=quantity, direction=direction)

    if act == "greet":
        # Being spoken to is being seen: the body's picture of the figure
        # refreshes, and the situation a conversation needs opens.
        minds.setdefault(other, {})[actor] = figure_claim(figure, at)
        key, entry = _open("converse", place, {"a": other, "b": actor}, at)
        practices.setdefault(key, entry)
        return {"actor": actor, "act": act, "other": other,
                "line": f"{actor} greeted {other}"}

    if act == "ask":
        # The question is the author's; the body's answer is its own
        # conduct, chosen or authored on the body's side. Asking only keeps
        # the situation warm.
        key, entry = _open("converse", place, {"a": other, "b": actor}, at)
        practices.setdefault(key, entry)
        practices[key]["last_effect_at"] = at
        return {"actor": actor, "act": act, "other": other,
                "line": f"{actor} asked {other}"}

    if act == "tell":
        if not isinstance(claim, dict) or not claim.get("body"):
            return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)
        keep = ASKED_RETENTION if retention is None else float(retention)
        taken = hear_claim(
            minds, other, claim, keep,
            regard_value(state["regard"], other, actor), heard_from=actor)
        subject = str(claim.get("body"))
        return {"actor": actor, "act": act, "other": other,
                "taken": bool(taken),
                "line": f"{actor} told {other} about {subject}"}

    if act == "accuse":
        heard_blame.setdefault(other, set()).add(actor)
        key, entry = _open("quarrel", place, {"a": other, "b": actor}, at,
                           about=other)
        practices.setdefault(key, entry)
        return {"actor": actor, "act": act, "other": other,
                "line": f"{actor} accused {other}"}

    # act == "tend"
    held = (needs or {}).get(other) or {}
    if not held:
        return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)
    worst = min(held.values(),
                key=lambda n: float(n["level"]) - float(n["floor"]))
    if float(worst["floor"]) - float(worst["level"]) <= 0.0:
        return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)
    worst["level"] = min(1.0, float(worst["level"]) + 0.05)
    return {"actor": actor, "act": act, "other": other,
            "line": f"{actor} tended {other} ({worst['key']})"}


def has_standing(charter, actor, other):
    """Whether a figure's office stands above the post a body holds.

    Read from the posts' authored ``reports_to`` chain and nothing else: a
    figure has standing over a body when the figure rides a body (a
    promoted character, via ``bindings``; or a member acting as a figure)
    whose post is somewhere up the line the body's post reports along. A
    self-report ("reeve reports to reeve") ends the chain rather than
    granting anyone standing. The player, unless they ride a body, has
    none -- which is the ordinary case, and why an order from a stranger
    is a request wearing a louder voice.
    """
    charter = charter if isinstance(charter, dict) else {}
    watch = charter.get("watch") or {}
    posts = charter.get("posts") or {}
    actor, other = str(actor or ""), str(other or "")
    actor_cf = actor.casefold()
    riding = {str(bk) for bk, binding in (charter.get("bindings") or {}).items()
              if str((binding or {}).get("name") or "").casefold() == actor_cf}
    if actor in (charter.get("bodies") or {}):
        riding.add(actor)
    held = {str(p) for p, who in watch.items() if str(who) in riding}
    if not held:
        return False
    for post, who in watch.items():
        if str(who) != other:
            continue
        seen = {str(post)}
        current = str((posts.get(str(post)) or {}).get("reports_to") or "")
        while current and current not in seen:
            if current in held:
                return True
            seen.add(current)
            current = str((posts.get(current) or {}).get("reports_to") or "")
    return False


def _owed_by(commitments, promisor, beneficiary):
    """Open undertakings `promisor` still owes `beneficiary`."""
    return [record for record in (commitments or {}).values()
            if str(record.get("state") or "") in OPEN_STATES
            and str(record.get("promisor") or "") == str(promisor)
            and str(record.get("beneficiary") or "") == str(beneficiary)]


def _disposed(state, needs, commitments, other, actor):
    """Whether a body takes up what a figure asks of it, and why not.

    Three refusals, each a fact the body may legitimately read of itself:
    a need under its floor (it is pressed), regard for the asker under
    `FAVOUR_REGARD_FLOOR` (it thinks less of them), or an undertaking the
    asker already owes it and has not made good (settle that first).
    Returns ``(willing, reason)``.
    """
    held = (needs or {}).get(other) or {}
    if any(float(n["level"]) < float(n["floor"]) for n in held.values()):
        return False, "pressed"
    if regard_value(state["regard"], other, actor) < FAVOUR_REGARD_FLOOR:
        return False, "regard"
    if _owed_by(commitments, actor, other):
        return False, "unsettled"
    return True, ""


def _answered(record, commitments, cid, answer, reason, line):
    record.update({"answer": answer, "commitment": cid,
                   "_commitments": True, "line": line})
    if reason:
        record["reason"] = reason
    return record


def _figure_dealing(actor, act, other, target, state, needs, at, stores, *,
                    terms="", source_id="", thing="", good="", quantity=1.0,
                    direction="buy"):
    """The six acts that answer through a ledger rather than a mind."""
    commitments = stores.get("commitments") or {}
    terms = " ".join(str(terms or "").split())
    record = {"actor": actor, "act": act, "other": other}
    if terms:
        record["terms"] = terms[:320]

    if act == "order":
        standing = has_standing(
            {"watch": stores.get("watch"), "posts": stores.get("posts"),
             "bindings": stores.get("bindings"), "bodies": state["bodies"]},
            actor, other)
        if not standing:
            # Nobody to obey: the words are a request, and are answered as
            # one. The record says what was attempted.
            record["as"] = "request"
            act = "request"
        else:
            if not target.get("available"):
                willing, reason = False, "unable"
            elif regard_value(state["regard"], other, actor) \
                    < ORDER_REFUSAL_REGARD:
                willing, reason = False, "regard"
            else:
                willing, reason = True, ""
            commitments, cid, _ = open_commitment(
                commitments, source_id=source_id, kind="order",
                promisor=other, beneficiary=actor, terms=terms or "an order",
                state="proposed", at_hours=at, recognized_by=[other])
            commitments, _ = answer_commitment(
                commitments, cid, accepted=willing, by=other, at_hours=at,
                note=reason or "obeyed", evidence_id=source_id)
            stores["commitments"] = commitments
            return _answered(
                record, commitments, cid, "obeyed" if willing else "refused",
                reason, "%s ordered %s; %s" % (
                    actor, other, "obeyed" if willing else "refused"))

    if act == "request":
        willing, reason = _disposed(state, needs, commitments, other, actor)
        commitments, cid, _ = open_commitment(
            commitments, source_id=source_id, kind="favour",
            promisor=other, beneficiary=actor, terms=terms or "a favour",
            state="proposed", at_hours=at, recognized_by=[other])
        commitments, _ = answer_commitment(
            commitments, cid, accepted=willing, by=other, at_hours=at,
            note=reason or "granted", evidence_id=source_id)
        stores["commitments"] = commitments
        return _answered(
            record, commitments, cid, "granted" if willing else "declined",
            reason, "%s asked %s for %s; %s" % (
                actor, other, terms or "a favour",
                "granted" if willing else "declined"))

    if act == "bargain":
        willing, reason = _disposed(state, needs, commitments, other, actor)
        commitments, cid, _ = open_commitment(
            commitments, source_id=source_id, kind="bargain",
            promisor=actor, beneficiary=other, terms=terms or "a bargain",
            state="proposed", at_hours=at, recognized_by=[other])
        commitments, _ = answer_commitment(
            commitments, cid, accepted=willing, by=other, at_hours=at,
            note=reason or "accepted", evidence_id=source_id)
        stores["commitments"] = commitments
        return _answered(
            record, commitments, cid, "accepted" if willing else "declined",
            reason, "%s offered %s %s; %s" % (
                actor, other, terms or "a bargain",
                "accepted" if willing else "declined"))

    if act == "promise":
        # The figure's own undertaking. Nothing for the body to decide; it
        # heard, and the record is open against the promisor from here on.
        commitments, cid, _ = open_commitment(
            commitments, source_id=source_id, kind="promise",
            promisor=actor, beneficiary=other, terms=terms or "a promise",
            state="open", at_hours=at, recognized_by=[other])
        stores["commitments"] = commitments
        return _answered(
            record, commitments, cid, "heard", "",
            "%s promised %s %s" % (actor, other, terms or "something"))

    if act == "trade":
        economy = stores.get("economy") or normalize_economy(None)
        place = _whereabouts(other, state)
        markets = [(k, m) for k, m in sorted(economy["markets"].items())
                   if str(m.get("place") or "") == place]
        if not markets:
            return dict(_refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE),
                        reason="no_market")
        good = str(good or "")
        # The market this body deals at: the one whose holder is a post it
        # stands or its own key, else the first at the place.
        held_posts = {str(p) for p, who in (stores.get("watch") or {}).items()
                      if str(who) == other}
        markets.sort(key=lambda km: (
            0 if km[1].get("holder") in held_posts | {other} else 1, km[0]))
        market_key, market = markets[0]
        # Regard is a discount, in the economy's own knob: `quote` clamps
        # the relationship adjustment to its [0.65, 1.5] multiplier itself.
        priced = quote(economy, market_key, good, quantity=quantity,
                       relationship_adjustment=(
                           NEUTRAL_REGARD
                           - regard_value(state["regard"], other, actor)))
        if priced is None:
            return dict(_refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE),
                        reason="no_such_good", market=market_key)
        holder = str(market.get("holder") or market_key)
        seller, buyer = (holder, actor) if direction != "sell" \
            else (actor, holder)
        economy, event, moved = trade(
            economy, seller=seller, buyer=buyer, good=good,
            quantity=quantity, at_hours=at, place=place, price=priced,
            reason="sale")
        record.update({"answer": "quoted", "market": market_key,
                       "quote": priced, "moved": moved,
                       "line": "%s traded with %s for %s at %s %s" % (
                           actor, other, good, priced["total_value"],
                           priced["currency"])})
        if event is not None:
            record["deal"] = event
            record["_economy"] = True
            stores["economy"] = economy
        else:
            record["reason"] = "no_stock" if direction != "sell" \
                else "nothing_to_sell"
        return record

    # act == "give"
    thing = " ".join(str(thing or "").split())
    if not thing:
        return dict(_refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE),
                    reason="nothing_given")
    record.update({"answer": "taken", "thing": thing[:120],
                   "line": "%s gave %s %s" % (actor, other, thing[:120])})
    return record


def _label_tokens(text):
    return set(re.findall(r"[a-z0-9]+", str(text or "").casefold()))


def good_named(economy, place, *texts):
    """The one good sold at ``place`` that the texts name, or ''.

    A closed set the ENGINE owns: goods are author vocabulary the economy
    enumerates, so matching a request against them is a lookup in a table,
    not a reading of how English phrases a purchase. Every token of a
    good's key or label must appear in the text; two goods matching is no
    good named.
    """
    economy = normalize_economy(economy)
    holders = {str(m.get("holder") or k)
               for k, m in economy["markets"].items()
               if str(m.get("place") or "") == str(place or "")}
    if not holders:
        return ""
    sold = set()
    for holder in holders:
        sold |= set(economy["stocks"].get(holder) or {})
        sold |= set(economy["targets"].get(holder) or {})
    words = set()
    for text in texts:
        words |= _label_tokens(text)
    if not words:
        return ""
    found = set()
    for key in sorted(sold):
        spec = economy["goods"].get(key) or {}
        for form in (key, spec.get("label")):
            tokens = _label_tokens(form)
            if tokens and tokens <= words:
                found.add(key)
                break
    return next(iter(found)) if len(found) == 1 else ""


def acts_in_evidence(evidence_rows, inventory_ops, figures):
    """The figure acts one resolved beat carries, before any body is named.

    Speech rows yield the act `FIGURE_ACT_OF_SPEECH` maps their kind to,
    with the frame's own words as terms; a transfer op whose giver is a
    figure and whose destination is somebody yields a gift. Rows are
    ``{actor, act, target, terms, source_id, thing}`` with ``target`` still
    the Director's spelling -- resolving it to a body is the runtime's
    job, because only the registry can say who is standing where.
    ``figures`` is the beat's authored minds by name (player and cast);
    an actor outside it is not a figure and yields nothing.
    """
    figure_cf = {str(f or "").strip().casefold() for f in (figures or ())
                 if str(f or "").strip()}
    rows = []
    for evidence in evidence_rows or ():
        if not isinstance(evidence, dict):
            continue
        if evidence.get("kind") not in ("speech", "communication"):
            continue
        actor = str(evidence.get("actor") or "").strip()
        target = str(evidence.get("target") or "").strip()
        if not actor or not target or actor.casefold() not in figure_cf:
            continue
        source_id = str(evidence.get("source_id") or "")
        for frame in evidence.get("speech_acts") or ():
            if not isinstance(frame, dict):
                continue
            act = FIGURE_ACT_OF_SPEECH.get(
                str(frame.get("kind") or "").strip().casefold())
            if not act:
                continue
            terms = " ".join(str(frame.get("content")
                                 or frame.get("about") or "").split())
            rows.append({"actor": actor, "act": act, "target": target,
                         "terms": terms, "source_id": source_id,
                         "about": " ".join(
                             str(frame.get("about") or "").split()),
                         "thing": ""})
    for op in inventory_ops or ():
        if not isinstance(op, dict):
            continue
        giver = str(op.get("from_id") or "").strip()
        taker = str(op.get("to_id") or "").strip()
        thing = str(op.get("object_id") or "").strip()
        if not giver or not taker or not thing:
            continue
        if giver.casefold() not in figure_cf:
            continue
        rows.append({"actor": giver, "act": "give", "target": taker,
                     "terms": "", "source_id": "", "about": "",
                     "thing": " ".join(thing.split("_"))})
    return rows


def action_instances(charter, actor=None):
    """The affordances currently open to one presence, or to all of them.

    A convenience over ``charter_practice.offers`` that reads the charter's
    own stores, for a scene manager deciding what a voiced body could
    plausibly do next. Reading it licenses nothing.
    """
    charter = normalize_charter(charter)
    politics = normalize_politics(charter.get("politics"))
    # The same four history stores the chooser reads, and passed for the same
    # reason: `charter_runtime` puts these utility numbers in front of a
    # scene-manager model (`agents/background.py`), and numbers computed
    # without history beside a chooser that decides with it would be a seam
    # lying about what the body wants.
    return offers(
        charter["bodies"], charter["minds"], charter["needs"],
        normalize_practices(charter.get("practices")),
        regard_map(politics), dict(politics.get("blame") or {}),
        float(charter["clock_hours"]), figures=charter["figures"],
        actor=actor, experiences=charter.get("experiences"),
        served_beside=charter.get("served_beside"),
        judgments=charter.get("judgments"),
        commitments=charter.get("commitments"))
