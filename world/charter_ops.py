"""What an AUTHORED EVENT may say happened to an institution, and nothing else.

``docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md`` § 3a and
``docs/design/DESIGN_PLACE_HISTORY.md`` § 2. Charter is the physics of
off-screen life; the Planner is the hand that reaches into it. This module is
the write side of that instrument: a closed vocabulary of the facts an author
may MOVE, each routed through the function Charter already owns, each refused
deterministically with a named reason.

**AN AUTHORED EVENT IS AN INPUT TO THE SIMULATION, NOT A RIVAL OUTPUT.** The
Planner says the granary burned. Charter says who therefore has nothing to
tend, who notices, who is blamed and who never hears -- and it says it with
the same machinery it would have used had a wolf done it. So no operation
here names a reactor, and the fields below are the whole vocabulary: an event
that cannot be spelled in them is prose again, which is the defect this
module exists to stop (a concealment written as free text was no channel at
all; a barrier described in a sentence was not a barrier).

Two things follow, and both are tested:

  * **Nothing here writes a mind.** `charter_surgery.plant_claim` is the one
    surgery that touches a head and it is deliberately NOT in this set: what
    a person concludes from an event is theirs. A head learns of an authored
    event exactly as it learns of anything -- somebody saw it.
  * **The institution keeps its own beliefs.** A death removes a body and
    leaves the roster believing in them (`world/charter_roster.py`: a roster
    improves by OBSERVATION and decays otherwise). No operation corrects a
    roster by decree, and `charter_roster.observe` stays the only door.

Pure over a registry dict, exactly as `charter_surgery` is pure over one
charter's state. `charter_runtime.author_charter_ops` is the I/O seam that
loads, applies the whole event and saves it once; `story/plot_packages.py`'s
``charter_ops`` operation is what the Planner writes.
"""

from __future__ import annotations

from .charter_harm import CONDITIONS

#: THE CLOSED SET, and the fields each op takes beside ``charter``. A schema
#: the engine owns and can enumerate -- not a guess at how English will
#: phrase something -- so a field outside it is a refusal rather than a
#: silently ignored key.
CHARTER_OPS = {
    # An errand dispatched: a body walks there, one room at a time, and its
    # post calls it back after (`charter_move.continue_walks`).
    "errand": ("body", "to", "purpose"),
    # Somebody joins this institution. The person must already exist
    # somewhere in the world -- minting one is `plan_entity`'s act, under
    # the `create_people` grant.
    "arrive": ("body", "from_charter", "place"),
    # Somebody leaves it: for another institution, or for none at all --
    # a hermit, employed nowhere, still a person.
    "depart": ("body", "to_charter", "place"),
    # A body is dead, missing or hurt, through the harm model a wolf uses.
    "die": ("body", "condition", "cause"),
    # A post gets a holder; a post loses one.
    "fill_post": ("post", "body"),
    "vacate_post": ("post",),
    # A condition the institution owes drops. Its floor, its drift and what
    # depends on it are the institution's own; this moves the level.
    "upkeep_fails": ("upkeep", "to", "by", "surface"),
    # Lots leave a holder's books: a delivery that never came, a store
    # burned. A cut only ever subtracts.
    "supply_cut": ("holder", "good", "lots"),
}

#: Ops one authored event may carry. A LIMIT THE OWNER SHOULD KNOW ABOUT: an
#: event that moves more facts than this is more than one event, and saying
#: so is cheaper than a package that half-lands. They apply in order and the
#: whole event is refused if any one of them is.
CHARTER_OPS_CAP = 12

#: What a body may be moved to by `die`. `CONDITIONS` minus ``well``:
#: authoring a body back to health is recovery, which the institution owns
#: (`charter_harm.advance_harm`).
HARM_OUTCOMES = tuple(c for c in CONDITIONS if c != "well")

#: The most one `upkeep_fails` may move a level, and the most one
#: `supply_cut` may take off the books in lots. Both are ceilings on a
#: single authored event, not on what the simulation may do over time.
UPKEEP_DROP_CAP = 1.0
SUPPLY_CUT_CAP = 10_000.0


def _text(value, limit=240):
    return " ".join(str(value or "").split())[:limit]


def _charter_state(registry, key):
    item = ((registry or {}).get("items") or {}).get(str(key))
    if not isinstance(item, dict) or not isinstance(item.get("state"), dict):
        raise ValueError("no charter %r" % key)
    return item["state"]


def _employer_of(registry, body_key):
    """The charter key employing ``body_key``, or "" for a hermit."""
    for key, item in ((registry or {}).get("items") or {}).items():
        state = (item or {}).get("state") or {}
        if str(body_key) in (state.get("bodies") or {}):
            return str(key)
    return ""


def _number(value, what):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("%s is a number" % what)


def normalize_charter_op(raw, *, default_charter=""):
    """One op, checked against `CHARTER_OPS`. Raises `ValueError` naming the
    reason: an unknown kind, a missing required field, or a field the kind
    does not take -- which is how a model's invented key is refused instead
    of dropped."""
    raw = raw if isinstance(raw, dict) else {}
    kind = _text(raw.get("op"), 60)
    if kind not in CHARTER_OPS:
        raise ValueError("no such charter op %r; the ops are %s"
                         % (kind, ", ".join(sorted(CHARTER_OPS))))
    allowed = set(CHARTER_OPS[kind]) | {"op", "charter"}
    unknown = sorted(str(k) for k in raw if str(k) not in allowed)
    if unknown:
        raise ValueError("%s does not take %s; its fields are %s"
                         % (kind, ", ".join(unknown),
                            ", ".join(CHARTER_OPS[kind])))
    out = {"op": kind,
           "charter": _text(raw.get("charter"), 120)
           or _text(default_charter, 120)}
    if not out["charter"]:
        raise ValueError("%s names the charter it moves" % kind)
    for field in CHARTER_OPS[kind]:
        value = raw.get(field)
        out[field] = value if isinstance(value, (int, float)) \
            and not isinstance(value, bool) else _text(value, 320)
    return _check(out)


def _check(op):
    """The per-kind requirements, each a refusal with its reason."""
    kind = op["op"]
    if kind in ("errand", "arrive", "depart", "die", "fill_post") \
            and not op.get("body"):
        raise ValueError("%s names the body" % kind)
    if kind == "errand" and not op.get("to"):
        raise ValueError("errand names where the body is sent")
    if kind == "die":
        condition = _text(op.get("condition"), 40).casefold() or "dead"
        if condition not in HARM_OUTCOMES:
            raise ValueError("die names one of %s, not %r"
                             % (", ".join(HARM_OUTCOMES), op.get("condition")))
        op["condition"] = condition
    if kind in ("fill_post", "vacate_post") and not op.get("post"):
        raise ValueError("%s names the post" % kind)
    if kind == "upkeep_fails":
        if not op.get("upkeep"):
            raise ValueError("upkeep_fails names the upkeep that drops")
        to, by = op.get("to"), op.get("by")
        if (to in ("", None)) == (by in ("", None)):
            raise ValueError("upkeep_fails says either `to` (the level it "
                             "falls to) or `by` (how far it falls), not both "
                             "and not neither")
        op["to"] = None if to in ("", None) else _number(to, "upkeep_fails to")
        op["by"] = None if by in ("", None) else _number(by, "upkeep_fails by")
        for field in ("to", "by"):
            if op[field] is not None \
                    and not 0.0 <= abs(op[field]) <= UPKEEP_DROP_CAP:
                raise ValueError("upkeep_fails %s is 0..%g"
                                 % (field, UPKEEP_DROP_CAP))
    if kind == "supply_cut":
        if not op.get("holder") or not op.get("good"):
            raise ValueError("supply_cut names the holder and the good")
        lots = _number(op.get("lots"), "supply_cut lots")
        if not 0.0 < lots <= SUPPLY_CUT_CAP:
            raise ValueError("supply_cut takes 0 < lots <= %g off the books"
                             % SUPPLY_CUT_CAP)
        op["lots"] = lots
    return op


# ---------------------------------------------------------------------------
# The ops, each through the function Charter already owns
# ---------------------------------------------------------------------------

def _surgery(registry, op, fields, *, by, turn_idx):
    from .charter_surgery import apply_surgery
    return apply_surgery(registry, {"op": op, **fields}, by=by,
                         turn_idx=turn_idx)


def _op_errand(registry, op, *, by, turn_idx, scene=None):
    return _surgery(registry, "send_errand", {
        "charter": op["charter"], "body": op["body"], "to": op["to"],
        "purpose": op.get("purpose") or "", "scene": scene},
        by=by, turn_idx=turn_idx)


def _op_die(registry, op, *, by, turn_idx, scene=None):
    return _surgery(registry, "harm_body", {
        "charter": op["charter"], "body": op["body"],
        "outcome": op["condition"], "cause": op.get("cause") or "", "by": by},
        by=by, turn_idx=turn_idx)


def _op_fill_post(registry, op, *, by, turn_idx, scene=None):
    return _surgery(registry, "assign_post", {
        "charter": op["charter"], "body": op["body"], "post": op["post"]},
        by=by, turn_idx=turn_idx)


def _op_vacate_post(registry, op, *, by, turn_idx, scene=None):
    return _surgery(registry, "vacate_post", {
        "charter": op["charter"], "post": op["post"]}, by=by, turn_idx=turn_idx)


def _op_upkeep_fails(registry, op, *, by, turn_idx, scene=None):
    """The level moves through the institution's own intervention window
    (`charter_intervene`'s ``upkeep_shock``), which is what emits the
    incident the place witnesses. Refused HERE when the upkeep does not
    exist, because the window's own refusal is a silent row in
    ``refused_interventions`` and an authored event that lands nowhere is
    the defect being closed."""
    state = _charter_state(registry, op["charter"])
    upkeep = (state.get("upkeeps") or {}).get(str(op["upkeep"]))
    if upkeep is None:
        raise ValueError(
            "charter %r owes no upkeep %r; its upkeeps are %s"
            % (op["charter"], op["upkeep"],
               ", ".join(sorted(state.get("upkeeps") or {})) or "none"))
    if op.get("to") is not None:
        delta = float(op["to"]) - float(upkeep.get("level") or 0.0)
    else:
        delta = -abs(float(op["by"]))
    intervention = {"op": "upkeep_shock", "upkeep": str(op["upkeep"]),
                    "delta": delta, "place": str(upkeep.get("place") or "")}
    if op.get("surface"):
        intervention["surface"] = op["surface"]
    return _surgery(registry, "charter_shock", {
        "charter": op["charter"], "intervention": intervention},
        by=by, turn_idx=turn_idx)


def _op_supply_cut(registry, op, *, by, turn_idx, scene=None):
    return _surgery(registry, "adjust_stock", {
        "charter": op["charter"], "holder": op["holder"], "good": op["good"],
        "delta": -abs(float(op["lots"]))}, by=by, turn_idx=turn_idx)


def _transfer(registry, op, *, to_charter, by, turn_idx):
    """`charter_runtime.transfer_person` is the one expression of joining,
    leaving and the hermit employed nowhere. Imported at call time: this
    module is pure and `charter_runtime` is the I/O seam above it."""
    from .charter_runtime import transfer_person
    from .charter_surgery import record_authored
    body = str(op["body"])
    was = _employer_of(registry, body)
    if to_charter is not None:
        # An institution the registry does not hold is a refusal, not a new
        # institution: `transfer_person` would mint the item, and a town
        # founded by a typo is worse than a refused event.
        _charter_state(registry, to_charter)
        if was == str(to_charter):
            raise ValueError("charter %r already employs %r"
                             % (to_charter, body))
    elif not was:
        raise ValueError("%r is employed nowhere already" % body)
    if not was and body not in (registry.get("people") or {}):
        raise ValueError("no such person: %s; a person the world does not "
                         "hold is planned first, never arrived" % body)
    place = op.get("place") or None
    transfer_person(registry, body, to_charter, place=place)
    detail = {"body": body, "from": was or "nowhere",
              "to": str(to_charter) if to_charter is not None else "nowhere"}
    for key in {was, str(to_charter) if to_charter is not None else ""}:
        if key and key in ((registry.get("items") or {})):
            record_authored(_charter_state(registry, key), op["op"], by,
                            turn_idx, detail)
    return dict(detail, place=str(place or ""))


def _op_arrive(registry, op, *, by, turn_idx, scene=None):
    return _transfer(registry, op, to_charter=op["charter"], by=by,
                     turn_idx=turn_idx)


def _op_depart(registry, op, *, by, turn_idx, scene=None):
    to = _text(op.get("to_charter"), 120)
    if _employer_of(registry, str(op["body"])) != str(op["charter"]):
        raise ValueError("charter %r does not employ %r"
                         % (op["charter"], op["body"]))
    return _transfer(registry, op, to_charter=to or None, by=by,
                     turn_idx=turn_idx)


_HANDLERS = {
    "errand": _op_errand, "arrive": _op_arrive, "depart": _op_depart,
    "die": _op_die, "fill_post": _op_fill_post, "vacate_post": _op_vacate_post,
    "upkeep_fails": _op_upkeep_fails, "supply_cut": _op_supply_cut,
}


def apply_charter_ops(registry, ops, *, by="writers_room", turn_idx=None,
                      scene=None):
    """Apply one authored EVENT -- an ordered list of ops -- to a registry in
    place, and return one result row per op.

    ALL OR NOTHING at the caller's level: the first refusal raises
    `ValueError` naming the op's index, its kind and the reason, and the
    caller (`charter_runtime.author_charter_ops`) never saves. Apply to a
    deep copy to dry-run one, which is what the package preview does.
    """
    ops = list(ops or ())
    if not ops:
        raise ValueError("a charter event carries at least one op")
    if len(ops) > CHARTER_OPS_CAP:
        raise ValueError("an authored event carries at most %d ops; this one "
                         "carries %d" % (CHARTER_OPS_CAP, len(ops)))
    out = []
    for index, raw in enumerate(ops):
        op = raw if isinstance(raw, dict) and raw.get("op") in CHARTER_OPS \
            else normalize_charter_op(raw)
        try:
            result = _HANDLERS[op["op"]](registry, op, by=by,
                                         turn_idx=turn_idx, scene=scene)
        except ValueError as exc:
            raise ValueError("op %d (%s): %s" % (index, op["op"], exc))
        out.append({"index": index, "op": op["op"], "charter": op["charter"],
                    "result": result})
    return out


__all__ = ["CHARTER_OPS", "CHARTER_OPS_CAP", "HARM_OUTCOMES",
           "SUPPLY_CUT_CAP", "UPKEEP_DROP_CAP", "apply_charter_ops",
           "normalize_charter_op"]
