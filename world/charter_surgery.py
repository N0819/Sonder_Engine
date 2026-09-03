"""Author surgery on a charter: the Writers' Room's nudge toolkit.

v2 § 9.1 names "explicit author surgery" as the one way an author changes
carried charter state, and the plan (§ 5 Phase C, "the Planner's
intervention toolkit") says what a nudge IS: a pressure the body's own state
answers -- never a puppet string. So every operation here moves a FACT the
institution already keeps (where a body stands, which post it holds, what
stock a holder has, which rules are armed, what a head has been TOLD) and
none writes a conclusion into a head. A planted claim lands through
`charter_mind.hear_claim`, the only uptake door, from a named teller, with
the claim marked ``provenance: "authored"`` -- so the body believes what it
was told exactly as it would believe a rumour, can be wrong about it, and an
audit can see it was the room talking. A shock lands as an intervention row
the institution's own window applies (`charter_intervene.apply_due`).

Every surgery is RECORDED on the institution under ``authored`` (who, when,
what), because the point of an author layer is that its hand is visible to
the author's tools and to nobody in the fiction.

Pure over a registry dict; `charter_runtime.author_surgery` is the seam that
loads, applies and saves (the facade a caller imports). Refuses with
`ValueError` rather than guessing: a body that is dead, a post that does not
exist, a good the institution never stocked.
"""

from __future__ import annotations

import hashlib

#: The closed set. Each is a mandate capability in `story/mandates.py`.
SURGERY_OPS = ("move_body", "assign_post", "plant_claim", "adjust_stock",
               "arm_trigger", "charter_shock")

#: Records kept per institution; oldest fall off.
AUTHORED_CAP = 64
#: A planted claim's strength ceiling, and what it reads as when unsaid --
#: a rumour, not an eyewitness account (`charter_news.WITNESS_STRENGTH` is
#: 1.0; a teller the body regards fully still lands below that).
PLANT_STRENGTH_DEFAULT = 0.6
PLANT_STRENGTH_CAP = 0.9
#: Stock one surgery may move, in lots.
STOCK_DELTA_CAP = 10_000.0


def _text(value, limit=240):
    return " ".join(str(value or "").split())[:limit]


def _charter(registry, key):
    item = (registry.get("items") or {}).get(str(key))
    if not isinstance(item, dict) or not isinstance(item.get("state"), dict):
        raise ValueError("no charter %r" % key)
    return item["state"]


def _body(charter, body_key):
    from .charter_harm import is_gone
    if not str(body_key or ""):
        raise ValueError("charter %r: the surgery names the body" % charter.get("key"))
    body = (charter.get("bodies") or {}).get(str(body_key))
    if body is None:
        raise ValueError("charter %r holds no body %r"
                         % (charter.get("key"), body_key))
    if is_gone(body) or body.get("departed"):
        raise ValueError("body %r is %s; the room does not move the dead or "
                         "the departed"
                         % (body_key, body.get("condition") if is_gone(body)
                            else "departed"))
    return body


def _record(charter, op, by, turn_idx, detail):
    rows = [dict(r) for r in (charter.get("authored") or ()) if isinstance(r, dict)]
    rows.append({"op": str(op), "by": _text(by, 120), "turn_idx": turn_idx,
                 "at_hours": float(charter.get("clock_hours") or 0.0),
                 "detail": {str(k): _text(v, 200) for k, v in detail.items()}})
    charter["authored"] = rows[-AUTHORED_CAP:]


def normalize_authored(stored):
    out = []
    for raw in (stored or ()) if isinstance(stored, (list, tuple)) else ():
        if not isinstance(raw, dict) or not raw.get("op"):
            continue
        detail = raw.get("detail") if isinstance(raw.get("detail"), dict) else {}
        out.append({"op": str(raw["op"]), "by": _text(raw.get("by"), 120),
                    "turn_idx": raw.get("turn_idx"),
                    "at_hours": float(raw.get("at_hours") or 0.0),
                    "detail": {str(k): _text(v, 200) for k, v in detail.items()}})
    return out[-AUTHORED_CAP:]


# ---------------------------------------------------------------------------
# The operations
# ---------------------------------------------------------------------------

def move_body(charter, *, body="", room="", berth=False):
    """Stand a body in a room now. With ``berth``, it also lives there.
    Drops a walk in progress: the author put them here, they did not
    arrive. The caller says whether the room exists; this only knows the
    institution."""
    room = _text(room, 120)
    if not room:
        raise ValueError("move_body names the room")
    held = _body(charter, body)
    was = str(held.get("place") or "")
    held["place"] = room
    if berth:
        held["berth"] = room
    held.pop("walk", None)
    return {"body": str(body), "from": was, "to": room, "berth": bool(berth)}


def assign_post(charter, *, body="", post=""):
    """Give a body a post: the watch bill names them for it, and it becomes
    their home post. Another holder of that post is stood off it (not
    dismissed: the planner re-posts them next window)."""
    post = _text(post, 120)
    posts = charter.get("posts") or {}
    if post not in posts:
        raise ValueError("charter %r has no post %r" % (charter.get("key"), post))
    held = _body(charter, body)
    watch = dict(charter.get("watch") or {})
    displaced = [p for p, who in watch.items() if str(who) == str(body)]
    for p in displaced:
        watch.pop(p, None)
    previous = watch.get(post)
    watch[post] = str(body)
    charter["watch"] = watch
    held["home_post"] = post
    held["available"] = True
    held["stood_down"] = False
    return {"body": str(body), "post": post, "displaced": previous,
            "left": displaced}


def _claim_key(text):
    return "authored:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def plant_claim(charter, *, body="", text="", told_by="", about="", place="",
                strength=None):
    """A head HEARS something, from a named teller. The claim rides the one
    uptake door, so retention and regard thin it and a stronger holding is
    not overwritten; it is marked authored so an audit can tell the room's
    voice from a witness's. Returns whether the head took it."""
    from .charter_mind import hear_claim
    text = _text(text, 320)
    told_by = _text(told_by, 120)
    if not text:
        raise ValueError("plant_claim says what the body is told")
    if not told_by:
        raise ValueError("plant_claim names who told them: a claim with no "
                         "teller is a thought put in a head")
    held = _body(charter, body)
    try:
        strength = float(PLANT_STRENGTH_DEFAULT if strength is None else strength)
    except (TypeError, ValueError):
        raise ValueError("plant_claim strength is a number")
    strength = max(0.0, min(PLANT_STRENGTH_CAP, strength))
    at = float(charter.get("clock_hours") or 0.0)
    claim = {
        "kind": "news", "body": _claim_key(text), "event_kind": "report",
        "about": _text(about, 320) or text, "claim_text": text,
        "place": _text(place, 120) or str(held.get("place") or ""),
        "happened_at": at, "strength": strength, "as_of_hours": at,
        "heard_from": told_by, "provenance": "authored", "retellings": 0,
    }
    minds = charter.setdefault("minds", {})
    taken = hear_claim(minds, str(body), claim, retention=1.0, regard=1.0,
                       heard_from=told_by)
    return {"body": str(body), "claim": claim["body"], "taken": bool(taken),
            "told_by": told_by}


def adjust_stock(charter, *, holder="", good="", delta=None):
    """Lots appear on or leave a holder's books by the author's hand: a
    delivery that came, a store that spoiled. The good must be one the
    institution's economy knows; the level is clamped at zero."""
    from .charter_economy import normalize_economy
    economy = normalize_economy(charter.get("economy"))
    holder, good = _text(holder, 120), _text(good, 120)
    if good not in economy["goods"]:
        raise ValueError("charter %r stocks no good %r; its goods are %s"
                         % (charter.get("key"), good,
                            ", ".join(sorted(economy["goods"])) or "none"))
    if not holder:
        raise ValueError("adjust_stock names the holder")
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        raise ValueError("adjust_stock delta is a number of lots")
    if abs(delta) > STOCK_DELTA_CAP:
        raise ValueError("adjust_stock moves at most %g lots" % STOCK_DELTA_CAP)
    stocks = economy.setdefault("stocks", {})
    was = float((stocks.get(holder) or {}).get(good, 0.0))
    now = max(0.0, round(was + delta, 6))
    stocks.setdefault(holder, {})[good] = now
    charter["economy"] = normalize_economy(economy)
    return {"holder": holder, "good": good, "from": was, "to": now}


def arm_trigger(charter, *, rule=None):
    """Arm an authored consequence rule on the institution
    (`charter_trigger`): when such a change is perceived, then this. The
    rule is normalized by the trigger module's own validator and refused
    on its terms."""
    from .charter_trigger import normalize_triggers
    if not isinstance(rule, dict) or not rule.get("on"):
        raise ValueError("arm_trigger carries a rule with an `on` change")
    existing = [r for r in (charter.get("triggers") or ()) if isinstance(r, dict)]
    rows = normalize_triggers(existing + [dict(rule)])
    rid = str(rule.get("id") or "")
    armed = next((r for r in rows if rid and r["id"] == rid), None) or rows[-1]
    if armed.get("refused"):
        raise ValueError("arm_trigger: %s" % armed["refused"])
    charter["triggers"] = rows
    return {"rule": armed["id"], "on": armed["on"]}


def charter_shock(charter, *, intervention=None):
    """Schedule one physical intervention on the institution's own list
    (`charter_intervene.INTERVENTION_OPS`), due now: a need or upkeep
    shock, a drift dial, a relocation, a watch called out. The window
    applies it and the institution answers it with its own machinery."""
    from .charter_intervene import normalize_interventions
    if not isinstance(intervention, dict) or not intervention.get("op"):
        raise ValueError("charter_shock carries an intervention with an `op`")
    row = dict(intervention)
    row.setdefault("at_hours", float(charter.get("clock_hours") or 0.0))
    row.setdefault("cause", "the room")
    rows = normalize_interventions([row])
    if not rows or rows[0].get("refused"):
        raise ValueError("charter_shock: %s"
                         % (rows[0]["refused"] if rows else "unreadable"))
    existing = list(charter.get("interventions") or ())
    rows[0]["id"] = str(intervention.get("id") or
                        "authored:%s:%d" % (rows[0]["op"], len(existing)))
    charter["interventions"] = normalize_interventions(existing + rows)
    return {"intervention": rows[0]["id"], "op": rows[0]["op"]}


def send_errand(charter, *, body="", to="", purpose="", scene=None):
    """Send a body somewhere on foot: a walk record toward ``to`` that the
    institution's own movement phase spends (`charter_move.continue_walks`),
    so the body is seen on the way and arrives when the rooms are walked,
    and its post calls it back the window after. With no scene graph the
    walk is one step. Refuses an unreachable target."""
    from .charter_space import walk_route
    to = _text(to, 120)
    if not to:
        raise ValueError("errand names where the body is sent")
    held = _body(charter, body)
    origin = str(held.get("place") or "")
    if scene:
        route = walk_route(scene, origin, to)
        if route is None:
            raise ValueError("no route from %r to %r for body %r"
                             % (origin, to, body))
    else:
        route = [origin, to] if origin != to else [origin]
    if len(route) > 1:
        held["walk"] = {"target": to, "route": route, "leg": 0,
                        "credit": 0.0, "held": False}
    held["errand"] = {"to": to, "purpose": _text(purpose, 200)}
    return {"body": str(body), "from": origin, "to": to, "rooms": len(route) - 1}


def harm_body(charter, *, body="", outcome="hurt", cause="", by=""):
    """A body is harmed by the author's hand, through the harm model
    (`charter_harm.apply_harm`): the same function a wolf hurts it with,
    so the institution grieves, re-elects and mobilises exactly as it
    would. Gated by the `schedule_harm` capability at the package."""
    from .charter_harm import apply_harm, normalize_condition
    outcome = normalize_condition(outcome)
    if outcome == "well":
        raise ValueError("harm_body outcome is hurt, dead or missing")
    _body(charter, body)
    charter, events = apply_harm(
        charter, str(body), by=_text(by, 120) or "the room",
        at_hours=float(charter.get("clock_hours") or 0.0), outcome=outcome,
        cause=_text(cause, 120), copy_state=False)
    carried = list(charter.get("carried_events") or ())
    carried.extend(events)
    charter["carried_events"] = carried
    return {"body": str(body), "outcome": outcome, "events": len(events)}


def open_summons(charter, *, post="", target="", place="", terms="", source_id=""):
    """An institution calls somebody to a place: a commitment opened toward
    the target from the post's holder (`charter_commitment.open_commitment`),
    so answering it or ignoring it has a ledger. The target is a NAME the
    world holds; the room never writes the target's mind, only the
    institution's expectation of them."""
    post = _text(post, 120)
    target = _text(target, 120)
    if post not in (charter.get("posts") or {}):
        raise ValueError("charter %r has no post %r" % (charter.get("key"), post))
    if not target:
        raise ValueError("summons names whom it calls")
    from .charter_commitment import open_commitment
    holder = str((charter.get("watch") or {}).get(post) or post)
    at = float(charter.get("clock_hours") or 0.0)
    where = _text(place, 120) or str(((charter.get("posts") or {}).get(post) or {})
                                     .get("place") or "")
    commitments, cid, opened = open_commitment(
        charter.get("commitments"), source_id=_text(source_id, 120) or "authored",
        kind="summons", promisor=holder, beneficiary=target,
        terms=_text(terms, 320) or "come to %s" % where, state="proposed",
        at_hours=at, condition="", note="summoned to %s" % where)
    charter["commitments"] = commitments
    return {"commitment": cid, "opened": bool(opened), "by": holder,
            "post": post, "target": target, "place": where}


_HANDLERS = {
    "move_body": move_body, "assign_post": assign_post,
    "plant_claim": plant_claim, "adjust_stock": adjust_stock,
    "arm_trigger": arm_trigger, "charter_shock": charter_shock,
    "send_errand": send_errand, "harm_body": harm_body,
    "open_summons": open_summons,
}


def apply_surgery(registry, op, *, by="writers_room", turn_idx=None):
    """Apply one surgery to a registry in place and record it. ``op`` is
    ``{op, charter, ...fields}``. Returns the operation's result."""
    kind = str((op or {}).get("op") or "")
    if kind not in _HANDLERS:
        raise ValueError("no such surgery %r; the surgeries are %s"
                         % (kind, ", ".join(SURGERY_OPS)))
    charter = _charter(registry, (op or {}).get("charter"))
    fields = {k: v for k, v in op.items() if k not in ("op", "charter")}
    try:
        result = _HANDLERS[kind](charter, **fields)
    except TypeError as exc:
        # A field the surgery does not take is a refusal, not a crash.
        raise ValueError("%s: %s" % (kind, str(exc).split("got an unexpected keyword argument")[-1].strip() or exc))
    _record(charter, kind, by, turn_idx, {
        k: v for k, v in fields.items() if not isinstance(v, (dict, list))})
    return result
