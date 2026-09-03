"""Bounded institutional agendas, decisions and physically delivered orders.

An institution never reads the objective event list here.  Agenda items are
made from news held by the body staffing an authorised post.  Policies choose
only from an authored closed action vocabulary; generated prose cannot mutate
the Charter.  Orders then move down staffed, co-present reporting lines.
"""

from __future__ import annotations

import hashlib

from .charter_model import integer as _integer, number as _number
from .charter_news import known_news


AGENDA_CAP = 12
ORDER_CAP = 24
ORDER_ACTIONS = frozenset({
    "investigate", "release_stock", "request_report", "reassign",
    "dispatch_caravan", "enforce_commitment", "hold",
})


def normalize_decisions(stored):
    stored = stored if isinstance(stored, dict) else {}
    policies = []
    for raw in stored.get("policies") or ():
        if not isinstance(raw, dict):
            continue
        action = str(raw.get("action") or "")
        if action not in ORDER_ACTIONS:
            continue
        policies.append({
            "when": str(raw.get("when") or ""), "action": action,
            "from_post": str(raw.get("from_post") or ""),
            "to_post": str(raw.get("to_post") or ""),
            "arguments": dict(raw.get("arguments") or {}),
            "priority": _integer(raw.get("priority")),
        })
    agenda = [dict(x) for x in stored.get("agenda") or ()
              if isinstance(x, dict) and x.get("evidence_id")][-AGENDA_CAP:]
    orders = []
    for raw in stored.get("orders") or ():
        if not isinstance(raw, dict) or raw.get("action") not in ORDER_ACTIONS:
            continue
        orders.append({
            "id": str(raw.get("id") or ""),
            "action": str(raw["action"]),
            "from_post": str(raw.get("from_post") or ""),
            "to_post": str(raw.get("to_post") or ""),
            "arguments": dict(raw.get("arguments") or {}),
            "evidence_id": str(raw.get("evidence_id") or ""),
            "issued_at_hours": round(_number(raw.get("issued_at_hours")), 6),
            "status": str(raw.get("status") or "issued"),
            "received_by": str(raw.get("received_by") or ""),
        })
    return {"policies": policies, "agenda": agenda,
            "orders": orders[-ORDER_CAP:]}


def _order_id(charter_key, post, evidence_id, action):
    material = "|".join((str(charter_key), str(post), str(evidence_id), action))
    return "order:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _leaders(watch, posts):
    reported_to = {str(p.get("reports_to") or "")
                   for p in (posts or {}).values() if p.get("reports_to")}
    explicit = {key for key, post in (posts or {}).items()
                if post.get("authority")}
    return sorted((explicit | reported_to) & set(watch or {}))


def advance_decisions(decisions, minds, watch, posts, bodies, *,
                      charter_key="charter", at_hours=0.0):
    """Turn authorised bodies' received news into policy-selected orders."""
    out = normalize_decisions(decisions)
    seen_agenda = {str(x.get("evidence_id")) for x in out["agenda"]}
    seen_orders = {str(x.get("id")) for x in out["orders"]}
    issued = []
    for post_key in _leaders(watch, posts):
        body_key = str((watch or {}).get(post_key) or "")
        body = (bodies or {}).get(body_key) or {}
        if not body_key or not body.get("available", True):
            continue
        claims = known_news(minds or {}, body_key)
        for claim in claims[:4]:
            evidence_id = str(claim.get("body") or "")
            event_kind = str(claim.get("event_kind") or "")
            if evidence_id not in seen_agenda:
                out["agenda"].append({
                    "evidence_id": evidence_id, "event_kind": event_kind,
                    "about": str(claim.get("about") or ""),
                    "held_by": body_key, "at_post": post_key,
                    "source": str(claim.get("heard_from") or ""),
                    "strength": round(float(claim.get("strength") or 0.0), 6),
                })
                seen_agenda.add(evidence_id)
            candidates = [p for p in out["policies"]
                          if p["when"] == event_kind
                          and (not p["from_post"] or p["from_post"] == post_key)]
            candidates.sort(key=lambda p: (-p["priority"], p["action"],
                                           p["to_post"]))
            if not candidates:
                continue
            policy = candidates[0]
            if policy["action"] not in set(
                    ((posts or {}).get(post_key) or {}).get("authority") or ()):
                continue
            oid = _order_id(charter_key, post_key, evidence_id,
                            policy["action"])
            if oid in seen_orders:
                continue
            order = {
                "id": oid, "action": policy["action"],
                "from_post": post_key, "to_post": policy["to_post"],
                "arguments": dict(policy["arguments"]),
                "evidence_id": evidence_id,
                "issued_at_hours": round(float(at_hours), 6),
                "status": "issued", "received_by": "",
            }
            out["orders"].append(order)
            issued.append(dict(order))
            seen_orders.add(oid)
    out["agenda"] = out["agenda"][-AGENDA_CAP:]
    out["orders"] = out["orders"][-ORDER_CAP:]
    return normalize_decisions(out), issued


def deliver_orders(decisions, watch, posts, bodies):
    """Move issued orders down one staffed, co-present reporting edge."""
    out = normalize_decisions(decisions)
    delivered = []
    for order in out["orders"]:
        if order["status"] != "issued":
            continue
        source = str((watch or {}).get(order["from_post"]) or "")
        target_post = order["to_post"]
        target = str((watch or {}).get(target_post) or "")
        if not source or not target or source == target:
            continue
        sb, tb = (bodies or {}).get(source) or {}, (bodies or {}).get(target) or {}
        if not sb.get("available", True) or not tb.get("available", True):
            continue
        if not sb.get("place") or str(sb.get("place")) != str(tb.get("place")):
            continue
        # The recipient's post must report, directly or through an authored
        # chain step, to the issuer.  One call delivers one edge only.
        if str(((posts or {}).get(target_post) or {}).get("reports_to") or "") \
                != order["from_post"]:
            continue
        order["status"] = "received"
        order["received_by"] = target
        delivered.append(order["id"])
    return normalize_decisions(out), delivered


def execute_orders(decisions, economy, *, at_hours=0.0, posts=None):
    """Execute received typed orders once; return state, economy and events.

    Most orders create a public institutional act for later systems to react
    to.  ``release_stock`` additionally transfers real abstract inventory.
    A model can never place an arbitrary mutation in ``arguments`` because
    the action vocabulary above is closed and each executor reads its own
    allowlisted fields.
    """
    from .charter_economy import normalize_economy, trade

    out = normalize_decisions(decisions)
    economy = normalize_economy(economy)
    events = []
    for order in out["orders"]:
        if order["status"] != "received":
            continue
        args = order.get("arguments") or {}
        place = str(((posts or {}).get(order["to_post"]) or {}).get("place")
                    or args.get("place") or "")
        if order["action"] == "release_stock":
            economy, trade_event, moved = trade(
                economy, seller=str(args.get("from_holder") or ""),
                buyer=str(args.get("to_holder") or ""),
                good=str(args.get("good") or ""),
                quantity=_number(args.get("quantity")),
                at_hours=at_hours, place=place,
                reason=f"order:{order['id']}")
            if trade_event is None:
                order["status"] = "failed"
                events.append({
                    "kind": "institution_order_failed",
                    "at_hours": round(float(at_hours), 6), "place": place,
                    "order_id": order["id"], "action": order["action"],
                    "reason": "no transferable stock"})
                continue
            events.append(trade_event)
            args = dict(args, quantity=moved)
        order["status"] = "executed"
        events.append({
            "kind": "institution_order_executed",
            "at_hours": round(float(at_hours), 6), "place": place,
            "order_id": order["id"], "action": order["action"],
            "by": order.get("received_by") or "",
            "arguments": args,
        })
    return normalize_decisions(out), economy, events


def mobilisation_calls(charter, minds, watch, posts, bodies, *, at_hours=0.0):
    """The watch called out, from what a body with standing over it holds.

    THE ONLY INPUT IS THE CALLER'S OWN HEAD. An office whose post carries
    `charter_intervene.MOBILISE_AUTHORITY` reads its own claims
    (`known_news`), and a claim of a `THREAT_KINDS` kind that names a place
    and holds at or above the institution's authored credence
    (`normalize_mobilisation`) is a call. Strength already carries regard
    for the teller and the retelling count (`charter_mind.hear_claim`), so
    who said it and how many mouths it crossed are in the number before it
    is compared. A stranger's warning is a weaker call than a neighbour's;
    a lie that clears the bar is a mobilisation the liar will be blamed
    for when it lapses with nothing seen (`charter_run.step`).

    Returns ``[intervention rows]`` for the caller to schedule -- one
    `watch_shock` per place, due at the next window, so the call is applied
    where every other physical change is applied and reported as an event
    from there. A place already under a called watch is not called again.
    """
    from .charter_intervene import (MOBILISE_AUTHORITY, THREAT_KINDS,
                                    normalize_mobilisation)

    config = normalize_mobilisation((charter or {}).get("mobilisation"))
    standing = (charter or {}).get("mobilisations") or {}
    able = sum(1 for body in (bodies or {}).values()
               if body.get("available", True))
    crew = min(int(config["crew_cap"]),
               max(1, int(round(config["crew_fraction"] * able))))
    calls, called = [], set(standing)
    for post_key, post in sorted((posts or {}).items()):
        if MOBILISE_AUTHORITY not in set(post.get("authority") or ()):
            continue
        body_key = str((watch or {}).get(post_key) or "")
        body = (bodies or {}).get(body_key) or {}
        if not body_key or not body.get("available", True):
            continue
        for claim in known_news(minds or {}, body_key):
            if str(claim.get("event_kind") or "") not in THREAT_KINDS:
                continue
            place = str(claim.get("place") or "")
            if not place or place in called:
                continue
            if float(claim.get("strength") or 0.0) < config["credence"]:
                continue
            called.add(place)
            calls.append({
                "op": "watch_shock", "at_hours": round(float(at_hours), 6),
                "place": place,
                "until_hours": round(float(at_hours)
                                     + config["duration_hours"], 6),
                "crew": crew, "requires": dict(config["requires"]),
                "called_by": body_key, "from_place": str(post.get("place")
                                                         or ""),
                "evidence": str(claim.get("body") or ""),
                "cause": "a threat reported at %s" % place,
            })
    return calls


def decision_view(decisions, *, post="", body="", cap=6):
    out = normalize_decisions(decisions)
    orders = [o for o in out["orders"] if (
        not post or post in {o["from_post"], o["to_post"]}) and (
        not body or body == o["received_by"])]
    return {"agenda": list(out["agenda"][-max(0, int(cap)):]),
            "orders": orders[-max(0, int(cap)):]}


__all__ = [
    "ORDER_ACTIONS", "advance_decisions", "decision_view", "deliver_orders",
    "execute_orders", "mobilisation_calls", "normalize_decisions",
]
