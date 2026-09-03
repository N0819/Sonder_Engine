"""Planned entities: the PLAN tier's ledger for people, things and
creatures, beside the planned rooms in `world/structure.py`.

THE DIVISION OF LABOUR (docs/design/DESIGN_WRITERS_ROOM_PLAN.md § 2): a plan
is what a thing is FOR and what is true of it before anyone sees it -- its
identity, role, past, ties, what it carries, where the world's clock has put
it. The Director RENDERS a plan when it comes into view: the high-fidelity
scene object of a planned body or thing, bounded by the plan and never a
second author of its identity. Charter SIMULATES what the plan put there.

Three functions, the same three the planned-room handoff needed
(`structure.planned_room_brief` / `settle_developed_stubs` /
`planned_room_ids`):

* a VIEW -- `plans_in_view` -- that puts the plans standing in the beat's
  rooms into the Director's payload, in the same row shape as
  `agents.common.present_charter_figures` (charter bodies ARE plans, and are
  the first plan source; this ledger holds the ones no charter simulates);
* a SETTLE -- `settle_rendered_plans` -- that writes the Director's render
  back onto the plan once, so the same thing looks the same next visit
  (`charter_surface.settle_render` is the body half of this);
* a RESERVATION -- `reserved_plans` -- so a Director mint naming a planned
  identity (name or alias) anywhere is a render of it, through the identity
  floor (`agents.director_floors._bind_minted_entities_to_present_figures`).

A Director mint with no plan behind it commits its SURFACE (what was seen:
appearance, position, what it did) and files a typed PLANNING NEED with
that surface attached -- the one ledger in `world/planning_needs.py`, shared
with the world-context compiler -- so the plan is authored behind what was
seen and never contradicts it (v2 § 7.4, the causal-exposure rule). This
ledger rides the `world` row under its own key, so archive, checkpoint,
branch and frame split carry it without their own handling.
"""
from __future__ import annotations

import hashlib
import re

from core.db import wget_for_frame, wset_for_frame

PLANNED_ENTITIES_KEY = "planned_entities"

#: What a plan may be for. A ROOM plan lives in the structure registry
#: (`world/structure.py`), not here, and a NEED of any kind lives in
#: `world/planning_needs.py`, because a need is filed before anything plans.
PLAN_KINDS = ("person", "thing", "creature")

#: The brief's prose fields are capped so a ledger read on every beat stays
#: a ledger.
PLAN_BRIEF_CHARS = 600
PLAN_ALIASES_CAP = 8
#: A plan's rendered surface, kept at the same ceiling as a need's.
SURFACE_CHARS = 600


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", _text(text, 200).casefold()).strip("_")


def plan_uid(kind, name):
    """A stable uid for an authored plan: kind, slug, and a digest of the
    name so two plans with one slug stay two plans."""
    digest = hashlib.sha256(
        ("%s|%s" % (kind, _text(name, 200))).encode("utf-8")).hexdigest()[:6]
    return "plan:%s:%s:%s" % (kind, _slug(name)[:32] or "entity", digest)


def body_plan_uid(charter_key, body_key):
    """The plan uid a charter body answers to: a body is a plan the charter
    simulates, and the Director's figures carry this so a render of a body
    and a render of an authored plan settle through one field."""
    return "charter:%s/%s" % (str(charter_key or ""), str(body_key or ""))


def normalize_plan(uid, entry):
    entry = entry if isinstance(entry, dict) else {}
    kind = str(entry.get("kind") or "person").strip().casefold()
    if kind not in PLAN_KINDS:
        kind = "person"
    brief = entry.get("brief") if isinstance(entry.get("brief"), dict) else {}
    aliases = []
    for alias in entry.get("aliases") or ():
        alias = _text(alias, 120)
        if alias and alias not in aliases:
            aliases.append(alias)
    out = {
        "uid": str(uid),
        "kind": kind,
        "name": _text(entry.get("name"), 120),
        "aliases": aliases[:PLAN_ALIASES_CAP],
        "role": _text(entry.get("role"), 120),
        "brief": {
            # What it is FOR.
            "purpose": _text(brief.get("purpose"), PLAN_BRIEF_CHARS),
            # What is true of it before anyone sees it.
            "truths": _text(brief.get("truths"), PLAN_BRIEF_CHARS),
            # Where the world's clock has put it: a room id.
            "where": _text(brief.get("where"), 120),
        },
        "source": _text(entry.get("source"), 40) or "authored",
        "filed_turn": entry.get("filed_turn"),
    }
    surface = entry.get("surface")
    if isinstance(surface, dict) and surface:
        out["surface"] = dict(surface)
    look = _text(entry.get("look"), SURFACE_CHARS)
    if look:
        out["look"] = look
    rendered = entry.get("rendered")
    if isinstance(rendered, dict) and str(rendered.get("render") or "").strip():
        out["rendered"] = {
            "entity_id": _text(rendered.get("entity_id"), 120),
            "turn": rendered.get("turn"),
            "render": _text(rendered.get("render"), SURFACE_CHARS),
        }
    return out


def normalize_plans(stored):
    stored = stored if isinstance(stored, dict) else {}
    return {str(uid): normalize_plan(uid, entry)
            for uid, entry in stored.items() if str(uid or "")}


def planned_entities(cid, frame_id=None):
    return normalize_plans(
        wget_for_frame(cid, PLANNED_ENTITIES_KEY, frame_id, {}) or {})


def save_planned_entities(cid, plans, frame_id=None):
    wset_for_frame(cid, PLANNED_ENTITIES_KEY, normalize_plans(plans), frame_id)


def add_planned_entity(cid, entry, frame_id=None, turn_idx=None):
    """File one authored plan; returns the stored plan. A plan already held
    under the same kind and name is UPDATED in place rather than doubled,
    which is the reservation working on the ledger itself."""
    entry = dict(entry or {})
    if turn_idx is not None and entry.get("filed_turn") is None:
        entry["filed_turn"] = int(turn_idx)
    uid = str(entry.get("uid") or plan_uid(entry.get("kind") or "person",
                                          entry.get("name")))
    plans = planned_entities(cid, frame_id)
    plan = normalize_plan(uid, entry)
    if uid in plans and plans[uid].get("rendered") and not plan.get("rendered"):
        plan["rendered"] = plans[uid]["rendered"]
    plans[uid] = plan
    save_planned_entities(cid, plans, frame_id)
    return plan


def plan_figure(plan):
    """One plan in the row shape `agents.common.present_charter_figures`
    returns, so the Director's payload and the identity floor read authored
    plans and charter bodies as one list. ``charter``/``body`` are empty
    (nobody simulates an authored plan until it is enrolled); ``plan``
    carries the uid the render settles through."""
    brief = plan.get("brief") or {}
    look = str(plan.get("look") or "")
    if not look and isinstance(plan.get("surface"), dict):
        try:
            from world.charter_surface import appearance_text
            look = appearance_text(plan["surface"])
        except Exception:
            look = ""
    row = {
        "name": str(plan.get("name") or ""),
        "room": str(brief.get("where") or ""),
        "role": str(plan.get("role") or ""),
        "posts": [],
        "charter": "",
        "body": "",
        "plan": str(plan.get("uid") or ""),
        "kind": str(plan.get("kind") or "person"),
        "aliases": list(plan.get("aliases") or ()),
    }
    if look:
        row["look"] = look
    purpose = str(brief.get("purpose") or "")
    truths = str(brief.get("truths") or "")
    if purpose or truths:
        row["brief"] = {k: v for k, v in (("purpose", purpose),
                                          ("truths", truths)) if v}
    return row


def plans_in_view(cid, rooms, frame_id=None):
    """The authored plans standing in `rooms` that no render has settled
    yet, as figure rows -- the VIEW half of the handoff. Empty for a story
    that authored none, so an ordinary payload is unchanged."""
    wanted = {str(r) for r in (rooms or ()) if str(r or "")}
    if not wanted:
        return []
    out = []
    for _uid, plan in sorted(planned_entities(cid, frame_id).items()):
        if plan.get("rendered"):
            continue
        if str((plan.get("brief") or {}).get("where") or "") not in wanted:
            continue
        if not plan.get("name"):
            continue
        out.append(plan_figure(plan))
    return out


def reserved_plans(cid, frame_id=None, exclude_rooms=()):
    """Every unrendered authored plan, wherever it stands, as a figure row
    flagged ``reserved`` -- the RESERVATION half: a mint naming one of these
    by name or alias is a render of it whatever room the mint stands in.
    A plan already listed for the beat's rooms is left to `plans_in_view`."""
    skip = {str(r) for r in (exclude_rooms or ()) if str(r or "")}
    out = []
    for _uid, plan in sorted(planned_entities(cid, frame_id).items()):
        if plan.get("rendered") or not plan.get("name"):
            continue
        if str((plan.get("brief") or {}).get("where") or "") in skip:
            continue
        row = plan_figure(plan)
        row["reserved"] = True
        out.append(row)
    return out


def settle_rendered_plans(cid, renders, frame_id=None):
    """The Director's render of an authored plan the floor bound, settled
    onto the plan ONCE. ``renders`` is ``[{plan, entity_id, render, turn}]``;
    returns one record per entry with ``settled`` or ``refused``. A plan
    already rendered keeps its render and is reported as neither; a render
    contradicting a dealt axis of the plan's surface is refused, by the same
    rule a body's is (`charter_surface.settle_render`: a second value of a
    closed axis is a second body)."""
    rows = [r for r in (renders or ()) if isinstance(r, dict)
            and str(r.get("plan") or "").startswith("plan:")
            and str(r.get("render") or "").strip()]
    if not rows:
        return []
    plans = planned_entities(cid, frame_id)
    out, changed = [], False
    for row in rows:
        plan = plans.get(str(row["plan"]))
        if plan is None:
            continue
        record = {"plan": str(row["plan"])}
        if plan.get("rendered"):
            continue
        render = _text(row.get("render"), SURFACE_CHARS)
        surface = plan.get("surface")
        if isinstance(surface, dict) and surface:
            refused = _contradicted_axis(surface, render)
            if refused:
                record["refused"] = refused
                out.append(record)
                continue
            surface = dict(surface)
            surface["rendered"] = render
            plan["surface"] = surface
        plan["rendered"] = {"entity_id": _text(row.get("entity_id"), 120),
                            "turn": row.get("turn"), "render": render}
        record["settled"] = render
        out.append(record)
        changed = True
    if changed:
        save_planned_entities(cid, plans, frame_id)
    return out


def _contradicted_axis(surface, render):
    """The first dealt axis whose pool holds another value the render names
    -- the body rule (`charter_surface.settle_render`) applied to a plan's
    surface against the engine's default pools, since an authored plan has
    no population law of its own."""
    try:
        from world.charter_surface import AXES, _phrase_in, default_looks
    except Exception:
        return ""
    looks = default_looks()
    for axis in AXES:
        dealt = str(surface.get(axis) or "")
        if not dealt:
            continue
        for value in looks.get(axis) or ():
            if value == dealt or not value:
                continue
            if _phrase_in(value, render) and not _phrase_in(dealt, value):
                return axis
    return ""
