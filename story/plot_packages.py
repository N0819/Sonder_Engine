"""Plot packages: the Writers' Room's durable contract with the simulation.

A PACKAGE is typed author state (docs/design/DESIGN_STORY_PLANNER_AND_
DRAMATURGE.md § 5): what the room has decided is true, what it wants in
question, the evidence it has placed, the pressures and clocks it has set,
and -- the part that reaches the world -- a list of typed OPERATIONS that
land through existing engine seams when the package is published. It rides
the frame-scoped `world` row under `PACKAGES_KEY`, so archive, checkpoint,
branch and frame split carry it without their own handling, and a restored
branch cannot inherit a package another era published.

Lifecycle: ``draft -> validating -> published -> active -> resolved ->
retired``, with ``retired`` reachable from any state. A draft is edited and
revisioned freely. Validation is deterministic code over the current world.
Preparation runs the LONG operations (location generation, presimulation)
BEFORE publish, each landing under its own seam's race guard. Publish is
then ONE short transaction over the remaining operations, guarded by the
package's pinned BASE (the turn and charter-registry revision it was
validated against): intervening history re-validates and re-pins (a
rebase) or refuses with the errors (a conflict). A published package is
visible to the pipeline from the turn AFTER the one it was published in,
never the current one, and turns ``active`` the first time a commit sees
it. Truths are immutable once published: a correction is a superseding
entry with the old one marked, never a silent rewrite.

THE AUTHOR-LAYER INVARIANT, AND WHERE IT IS ENFORCED. The room is an author
(v2 § 2.1): it may read objective truth, private charter minds and sealed
plot text freely, and NOTHING it writes reaches a fictional mind except
through a channel that mind has. The enforcement is `OPERATIONS`: a closed
table of operation kinds, each applied by one function over one existing
seam -- planned rooms through `structure.plant_structure`, plans through
`planned_entities.add_planned_entity`, artifacts through
`artifacts.new_artifact`, scheduled events through
`authored_events.mint_authored_events`, lore through
`canon_provenance.promote` and `add_lore`, planning needs through
`planning_needs.fill_planning_need`/`close_planning_need`, locations through
`charter_runtime.generate_lived_location`. There is no operation that
writes `chat_chars.state`, a memory row, a perception view, a relationship
or a character's knowledge, and an operation kind outside the table is
refused at DRAFT time, so a package cannot even carry one. What a package
places in the world -- a bill on a wall, a body in a post, a room behind a
door -- reaches a mind by being seen, heard, read or told, exactly as
anything else does (`tests/test_plot_packages.py::TestAuthorLayer`).

Sealed packages (v2 § 7) store their hidden text like any other; secrecy is
a PRESENTATION rule. `package_projection` is the spoiler-safe view -- what
is in motion, never what it is -- and is what the room panel shows for a
sealed package until the host reveals it.
"""

from __future__ import annotations

import copy
import hashlib
import re
import time

#: The world key. Frame-scoped (core/db.FRAME_SCOPED_WORLD_KEYS).
PACKAGES_KEY = "plot_packages"

STATUSES = ("draft", "validating", "published", "active", "resolved",
            "retired")
#: The states a package may be edited in.
EDITABLE = ("draft",)
#: The states in which the world holds what the package placed.
LANDED = ("published", "active", "resolved")

SPOILER_POLICIES = ("open", "sealed")

#: Caps. A package is read on every publish and its projection on every
#: panel refresh; each is a ceiling on one JSON blob in the world row.
#: Packages kept per frame that are not retired; past it `new_package`
#: refuses until one is resolved or retired.
PACKAGES_CAP = 32
#: Retired packages kept per frame; older ones are dropped oldest-first.
RETIRED_KEPT = 16
#: Operations one package may carry.
OPS_CAP = 64
#: Entries per list field (truths, questions, evidence, ...).
LIST_CAP = 48
#: Characters per prose field (premise, a truth's text, a question, ...).
TEXT_CHARS = 1200
#: Revisions remembered in `provenance.history`; older ones fall off.
HISTORY_CAP = 40
#: Rooms one `plan_rooms` operation may plant (the structure's own
#: `max_planned` still applies underneath).
PLAN_ROOMS_CAP = 200
#: Turns ahead a `schedule_event` may be due (the seam re-queues past it).
EVENT_DUE_CAP = 200
#: Story hours one `presimulate` may ask for at once.
PRESIM_HOURS_CAP = 24.0 * 30

#: Prose field names on a package, each a text capped at TEXT_CHARS.
_TEXT_FIELDS = ("title", "premise")
#: List fields and the id prefix each entry gets.
_LIST_FIELDS = {
    "truths": "truth", "questions": "question", "participants": "part",
    "evidence": "evidence", "pressures": "pressure", "clocks": "clock",
    "opportunities": "opportunity", "constraints": "constraint",
    "planner_requests": "request",
}
_ID_SAFE = re.compile(r"[^a-z0-9]+")


def _text(value, limit=TEXT_CHARS):
    return " ".join(str(value or "").split())[:limit]


def _slug(text):
    return _ID_SAFE.sub("_", _text(text, 60).casefold()).strip("_") or "package"


def package_uid(cid, title, created_at):
    material = "%s|%s|%s" % (cid, _text(title), created_at)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]
    return "plot:%s:%s" % (_slug(title), digest)


def _entry_id(prefix, package_uid_, text, index):
    material = "%s|%s|%s" % (package_uid_, _text(text), index)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:8]
    return "%s_%s" % (prefix, digest)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _normalize_entry(prefix, uid, entry, index):
    """One list entry: a dict with a stable id and a text, plus whatever
    typed fields the entry carries (evidence has origin/location/holders/
    bears_on/admission_path; a clock has due/story_hours; an opportunity has
    prerequisites). Free keys are kept, text-capped."""
    if isinstance(entry, str):
        entry = {"text": entry}
    entry = entry if isinstance(entry, dict) else {}
    out = {}
    for key, value in entry.items():
        key = str(key)
        if isinstance(value, (list, tuple)):
            out[key] = [_text(v, 200) for v in value if _text(v, 200)][:LIST_CAP]
        elif isinstance(value, dict):
            out[key] = {str(k): _text(v, 400) for k, v in value.items()}
        elif isinstance(value, bool) or value is None:
            out[key] = value
        elif isinstance(value, (int, float)):
            out[key] = value
        else:
            out[key] = _text(value)
    out["text"] = _text(entry.get("text"))
    out["id"] = str(entry.get("id") or "") or _entry_id(
        prefix, uid, out["text"], index)
    return out


def normalize_package(entry):
    entry = entry if isinstance(entry, dict) else {}
    uid = str(entry.get("uid") or "")
    status = str(entry.get("status") or "draft")
    if status not in STATUSES:
        status = "draft"
    policy = str(entry.get("spoiler_policy") or "open")
    if policy not in SPOILER_POLICIES:
        policy = "open"
    authority = entry.get("authority") if isinstance(
        entry.get("authority"), dict) else {}
    scope = entry.get("scope") if isinstance(entry.get("scope"), dict) else {}
    base = entry.get("base") if isinstance(entry.get("base"), dict) else {}
    validation = entry.get("validation") if isinstance(
        entry.get("validation"), dict) else {}
    provenance = entry.get("provenance") if isinstance(
        entry.get("provenance"), dict) else {}
    history = [dict(h) for h in (provenance.get("history") or ())
               if isinstance(h, dict)][-HISTORY_CAP:]
    out = {
        "uid": uid,
        "title": _text(entry.get("title"), 200),
        "premise": _text(entry.get("premise")),
        "status": status,
        "revision": max(0, int(entry.get("revision") or 0)),
        "spoiler_policy": policy,
        "scope": {
            "locations": [_text(x, 120) for x in (scope.get("locations") or ())
                          if _text(x, 120)][:LIST_CAP],
            "earliest_time": scope.get("earliest_time"),
            "latest_time": scope.get("latest_time"),
        },
        "authority": {
            "mandate_uid": _text(authority.get("mandate_uid"), 120),
            "may_create_people": bool(authority.get("may_create_people", True)),
            "may_author_prehistory": bool(
                authority.get("may_author_prehistory", False)),
            "may_schedule_harm": bool(authority.get("may_schedule_harm", False)),
        },
        "base": {
            "turn_idx": base.get("turn_idx"),
            "registry_revision": _text(base.get("registry_revision"), 120),
            "pinned_at": float(base.get("pinned_at") or 0.0),
        },
        "operations": [],
        "validation": {
            "ok": bool(validation.get("ok", False)),
            "errors": [_text(e, 400) for e in (validation.get("errors") or ())][:LIST_CAP],
            "warnings": [_text(w, 400) for w in (validation.get("warnings") or ())][:LIST_CAP],
            "at_revision": validation.get("at_revision"),
        },
        "provenance": {
            "created_turn": provenance.get("created_turn"),
            "created_at": float(provenance.get("created_at") or 0.0),
            "created_by": _text(provenance.get("created_by"), 80) or "writers_room",
            "history": history,
        },
        "published_turn": entry.get("published_turn"),
        "activated_turn": entry.get("activated_turn"),
    }
    for field, prefix in _LIST_FIELDS.items():
        items = entry.get(field) or []
        items = items if isinstance(items, list) else []
        out[field] = [_normalize_entry(prefix, uid, item, i)
                      for i, item in enumerate(items[:LIST_CAP])]
    for i, op in enumerate((entry.get("operations") or [])[:OPS_CAP]):
        if isinstance(op, dict) and op.get("op") in OPERATIONS:
            clean = copy.deepcopy(op)
            clean["op"] = str(op["op"])
            out["operations"].append(clean)
    if isinstance(entry.get("resolution"), dict):
        out["resolution"] = dict(entry["resolution"])
    return out


def normalize_packages(stored):
    stored = stored if isinstance(stored, dict) else {}
    out = {}
    for uid, entry in stored.items():
        if not str(uid or "") or not isinstance(entry, dict):
            continue
        pkg = normalize_package(dict(entry, uid=str(uid)))
        out[pkg["uid"]] = pkg
    return out


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def packages(cid, frame_id=None):
    from core.db import wget_for_frame

    return normalize_packages(
        wget_for_frame(cid, PACKAGES_KEY, frame_id, {}) or {})


def save_packages(cid, stored, frame_id=None):
    from core.db import wset_for_frame

    clean = normalize_packages(stored)
    retired = sorted(
        (p for p in clean.values() if p["status"] == "retired"),
        key=lambda p: (p["provenance"].get("created_at") or 0.0, p["uid"]))
    for stale in retired[:max(0, len(retired) - RETIRED_KEPT)]:
        clean.pop(stale["uid"], None)
    wset_for_frame(cid, PACKAGES_KEY, clean, frame_id)
    return clean


def get_package(cid, uid, frame_id=None):
    return packages(cid, frame_id).get(str(uid))


def _require(cid, uid, frame_id=None):
    pkg = get_package(cid, uid, frame_id)
    if pkg is None:
        raise ValueError("no package %r" % uid)
    return pkg


def _latest_turn_idx(cid, frame_id=None):
    from core.db import q

    row = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,),
            one=True)
    return int(row["idx"]) if row and row["idx"] is not None else 0


def _registry_revision(cid, frame_id=None):
    try:
        from world.charter_runtime import registry_for, registry_revision
        return str(registry_revision(registry_for(cid, frame_id)))
    except Exception:
        return ""


def _note(pkg, action, note="", turn_idx=None):
    pkg["provenance"]["history"] = (pkg["provenance"].get("history") or [])[
        -(HISTORY_CAP - 1):] + [{
            "revision": pkg["revision"], "action": str(action),
            "note": _text(note, 400), "turn_idx": turn_idx,
            "at": time.time()}]


def _bump(pkg, action, note="", turn_idx=None):
    pkg["revision"] += 1
    pkg["validation"] = {"ok": False, "errors": [], "warnings": [],
                         "at_revision": None}
    _note(pkg, action, note, turn_idx)


def new_package(cid, *, title, premise="", spoiler_policy="open", scope=None,
                authority=None, frame_id=None, created_by="writers_room"):
    """Open a draft. Refuses past `PACKAGES_CAP` live packages."""
    stored = packages(cid, frame_id)
    live = [p for p in stored.values() if p["status"] != "retired"]
    if len(live) >= PACKAGES_CAP:
        raise ValueError(
            "the frame holds %d packages that are not retired (cap %d); "
            "resolve or retire one first" % (len(live), PACKAGES_CAP))
    title = _text(title, 200)
    if not title:
        raise ValueError("a package has a title")
    now = time.time()
    turn_idx = _latest_turn_idx(cid, frame_id)
    pkg = normalize_package({
        "uid": package_uid(cid, title, now), "title": title,
        "premise": premise, "spoiler_policy": spoiler_policy,
        "scope": scope or {}, "authority": authority or {},
        "status": "draft", "revision": 1,
        "base": {"turn_idx": turn_idx,
                 "registry_revision": _registry_revision(cid, frame_id),
                 "pinned_at": now},
        "provenance": {"created_turn": turn_idx, "created_at": now,
                       "created_by": created_by},
    })
    _note(pkg, "created", turn_idx=turn_idx)
    stored[pkg["uid"]] = pkg
    save_packages(cid, stored, frame_id)
    return pkg


def edit_package(cid, uid, fields, *, frame_id=None, reason=""):
    """Change prose or list fields on a draft (revision bumps). After
    publish only `truths` may change, and only by SUPERSEDING: the old entry
    stays with `superseded_by`, the new one carries `supersedes` and the
    reason -- a visible correction, never a silent mutation (v2 § 5.1).
    Anything else on a landed package is refused."""
    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    fields = dict(fields or {})
    unknown = [k for k in fields if k not in _TEXT_FIELDS
               and k not in _LIST_FIELDS
               and k not in ("spoiler_policy", "scope", "authority")]
    if unknown:
        raise ValueError("unknown package fields: %s" % ", ".join(sorted(unknown)))
    if pkg["status"] in LANDED:
        if set(fields) != {"truths"}:
            raise ValueError(
                "a %s package accepts only a superseding truth; retire it or "
                "open a new package for anything else" % pkg["status"])
        if not _text(reason):
            raise ValueError("superseding a published truth names its reason")
        replacements = fields["truths"] if isinstance(fields["truths"], list) \
            else [fields["truths"]]
        for raw in replacements:
            raw = raw if isinstance(raw, dict) else {"text": raw}
            old_id = str(raw.get("supersedes") or "")
            old = next((t for t in pkg["truths"] if t["id"] == old_id), None)
            if old is None:
                raise ValueError("a superseding truth names the truth id it "
                                 "supersedes")
            if old.get("superseded_by"):
                raise ValueError("truth %s is already superseded" % old_id)
            new = _normalize_entry("truth", pkg["uid"], dict(
                raw, id="", supersedes=old_id, reason=_text(reason, 400),
                revision=pkg["revision"] + 1), len(pkg["truths"]))
            old["superseded_by"] = new["id"]
            pkg["truths"].append(new)
        _bump(pkg, "truth_superseded", reason, _latest_turn_idx(cid, frame_id))
        pkg["validation"]["ok"] = True
        stored[pkg["uid"]] = pkg
        save_packages(cid, stored, frame_id)
        return pkg
    if pkg["status"] not in EDITABLE:
        raise ValueError("a %s package is not editable" % pkg["status"])
    merged = dict(pkg)
    merged.update(fields)
    fresh = normalize_package(merged)
    for key in ("operations", "base", "provenance", "validation", "status",
                "revision", "published_turn", "activated_turn"):
        fresh[key] = pkg[key]
    _bump(fresh, "edited", ", ".join(sorted(fields)),
          _latest_turn_idx(cid, frame_id))
    stored[fresh["uid"]] = fresh
    save_packages(cid, stored, frame_id)
    return fresh


def draft_operation(cid, uid, op, *, frame_id=None):
    """Append one typed operation to a draft. Refused: an unknown kind
    (THE author-layer gate -- see the module docstring), a malformed one,
    or a draft already at `OPS_CAP`."""
    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    if pkg["status"] not in EDITABLE:
        raise ValueError("a %s package takes no new operations" % pkg["status"])
    op = dict(op or {})
    kind = str(op.get("op") or "")
    # `kind` is accepted as the kind key only when its value IS a kind, so a
    # plan_entity's own `kind` (person | thing | creature) is never read as
    # the operation's.
    if not kind and str(op.get("kind") or "") in OPERATIONS:
        kind = str(op.pop("kind"))
    if kind not in OPERATIONS:
        raise ValueError(
            "operation kind %r is not one the room may perform; an operation is "
            "an object whose `op` names its kind and whose other keys are that "
            "kind's fields; the kinds are %s"
            % (kind, ", ".join(sorted(OPERATIONS))))
    if len(pkg["operations"]) >= OPS_CAP:
        raise ValueError("a package carries at most %d operations" % OPS_CAP)
    shaped = OPERATIONS[kind]["shape"](op)
    shaped["op"] = kind
    shaped.pop("applied", None)
    shaped.pop("prepared", None)
    pkg["operations"].append(shaped)
    _bump(pkg, "operation_drafted", kind, _latest_turn_idx(cid, frame_id))
    stored[pkg["uid"]] = pkg
    save_packages(cid, stored, frame_id)
    return pkg


def remove_operation(cid, uid, index, *, frame_id=None):
    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    if pkg["status"] not in EDITABLE:
        raise ValueError("a %s package keeps its operations" % pkg["status"])
    try:
        removed = pkg["operations"].pop(int(index))
    except (IndexError, ValueError, TypeError):
        raise ValueError("no operation at index %r" % index)
    _bump(pkg, "operation_removed", removed.get("op"),
          _latest_turn_idx(cid, frame_id))
    stored[pkg["uid"]] = pkg
    save_packages(cid, stored, frame_id)
    return pkg


# ---------------------------------------------------------------------------
# Operations: shape, validate (dry run / preview), apply
# ---------------------------------------------------------------------------
#
# Each operation kind is three functions over ONE existing seam:
#   shape(op)                -> the stored form (raises ValueError)
#   preview(cid, frame_id, op, world) -> {"changes": [...], "errors": [...],
#                                          "warnings": [...]}
#   apply(cid, frame_id, op, turn_idx) -> the applied record
# `world` is the snapshot `_world_snapshot` takes once per validation so the
# validators agree with each other about what exists.

def _world_snapshot(cid, frame_id=None):
    from core.db import q
    from story.scene import get_scene
    from world.planned_entities import planned_entities
    from world.planning_needs import open_planning_needs
    from world.structure import planned_room_ids

    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    scene = get_scene(cid, chat) or {}
    rooms = scene.get("rooms") or {}
    specs = planned_room_ids(cid)
    names = set()
    for row in q("SELECT c.name FROM chat_chars cc JOIN characters c "
                 "ON c.id=cc.char_id WHERE cc.chat_id=?", (cid,)):
        if row["name"]:
            names.add(str(row["name"]).casefold())
    try:
        from world.charter_runtime import registry_for
        registry = registry_for(cid, frame_id)
        for item in (registry.get("items") or {}).values():
            for body in ((item.get("state") or {}).get("bodies") or {}).values():
                if body.get("name"):
                    names.add(str(body["name"]).casefold())
    except Exception:
        registry = {"items": {}}
    plans = planned_entities(cid, frame_id)
    for plan in plans.values():
        names.add(plan["name"].casefold())
        for alias in plan.get("aliases") or ():
            names.add(alias.casefold())
    return {
        "chat": dict(chat) if chat else {},
        "scene": scene,
        "rooms": {str(r) for r in rooms},
        "described_rooms": {
            str(r) for r, room in rooms.items() if isinstance(room, dict)
            and str(room.get("desc") or room.get("description") or "").strip()},
        "planned": set(specs),
        "reserved_names": names,
        "plans": plans,
        "needs": {n["uid"]: n for n in open_planning_needs(cid, frame_id)},
        "registry": registry,
    }


def _room_known(world, room):
    room = str(room or "")
    return room in world["rooms"] or room in world["planned"]


# -- plan_rooms ---------------------------------------------------------------

def _shape_plan_rooms(op):
    structure = op.get("structure") if isinstance(op.get("structure"), dict) else {}
    rooms = op.get("rooms") if isinstance(op.get("rooms"), dict) else {}
    if not structure.get("key"):
        raise ValueError("plan_rooms names its structure key")
    if not rooms:
        raise ValueError("plan_rooms plants at least one room")
    if len(rooms) > PLAN_ROOMS_CAP:
        raise ValueError("plan_rooms plants at most %d rooms" % PLAN_ROOMS_CAP)
    clean = {}
    for uid, raw in rooms.items():
        raw = raw if isinstance(raw, dict) else {}
        clean[str(uid)] = {
            "name": _text(raw.get("name"), 120) or str(uid),
            "purpose": _text(raw.get("purpose"), 400),
            "access": _text(raw.get("access"), 200),
            "adjacent": [dict(e) for e in raw.get("adjacent") or ()
                         if isinstance(e, dict) and e.get("to")],
            "frontier": [_text(x, 60) for x in raw.get("frontier") or ()
                         if _text(x, 60)],
        }
    return {"structure": dict(structure), "rooms": clean,
            "owning_book_id": op.get("owning_book_id")}


def _preview_plan_rooms(cid, frame_id, op, world):
    errors, warnings, changes = [], [], []
    rooms = op["rooms"]
    for uid, room in rooms.items():
        if uid in world["described_rooms"]:
            errors.append(
                "room %r is already described in the scene; a room the "
                "story has seen is a retcon, not a plan" % uid)
        for edge in room["adjacent"]:
            to = str(edge.get("to"))
            if to not in rooms and not _room_known(world, to):
                errors.append("room %r exits to %r, which exists nowhere"
                              % (uid, to))
    changes.append({"kind": "rooms_planted", "structure": op["structure"]["key"],
                    "rooms": sorted(rooms),
                    "already_planned": sorted(r for r in rooms
                                              if r in world["planned"])})
    return {"changes": changes, "errors": errors, "warnings": warnings}


def _apply_plan_rooms(cid, frame_id, op, turn_idx):
    from world.structure import plant_structure

    structure, planted = plant_structure(
        cid, op["structure"], op["rooms"],
        owning_book_id=op.get("owning_book_id"))
    return {"structure": structure["key"], "rooms": sorted(planted)}


# -- plan_entity --------------------------------------------------------------

def _shape_plan_entity(op):
    if not _text(op.get("name"), 120):
        raise ValueError("plan_entity names the entity")
    brief = op.get("brief") if isinstance(op.get("brief"), dict) else {}
    return {
        "kind": _text(op.get("kind"), 20) or "person",
        "name": _text(op.get("name"), 120),
        "aliases": [_text(a, 120) for a in op.get("aliases") or () if _text(a, 120)],
        "role": _text(op.get("role"), 120),
        "brief": {"purpose": _text(brief.get("purpose"), 600),
                  "truths": _text(brief.get("truths"), 600),
                  "where": _text(brief.get("where"), 120)},
        "surface": dict(op["surface"]) if isinstance(op.get("surface"), dict) else {},
        "look": _text(op.get("look"), 600),
        "answers_need": _text(op.get("answers_need"), 60),
    }


def _preview_plan_entity(cid, frame_id, op, world):
    errors, warnings = [], []
    from world.planned_entities import PLAN_KINDS, plan_uid
    if op["kind"] not in PLAN_KINDS:
        errors.append("plan_entity kind %r is not one of %s"
                      % (op["kind"], ", ".join(PLAN_KINDS)))
    uid = plan_uid(op["kind"], op["name"])
    held = world["plans"].get(uid)
    for name in [op["name"]] + list(op["aliases"]):
        if name.casefold() in world["reserved_names"] and not held:
            errors.append(
                "%r is a reserved identity (a registered character, a charter "
                "body or another plan); a plan may not reuse it" % name)
    where = op["brief"]["where"]
    if where and not _room_known(world, where):
        errors.append("plan_entity places %r at %r, which exists nowhere"
                      % (op["name"], where))
    if op["answers_need"] and op["answers_need"] not in world["needs"]:
        errors.append("plan_entity answers need %r, which is not open"
                      % op["answers_need"])
    return {"changes": [{"kind": "plan_updated" if held else "plan_filed",
                         "uid": uid, "name": op["name"], "where": where}],
            "errors": errors, "warnings": warnings}


def _apply_plan_entity(cid, frame_id, op, turn_idx):
    from world.planned_entities import add_planned_entity
    from world.planning_needs import fill_planning_need

    plan = add_planned_entity(cid, {
        "kind": op["kind"], "name": op["name"], "aliases": op["aliases"],
        "role": op["role"], "brief": op["brief"], "surface": op["surface"],
        "look": op["look"], "source": "writers_room"},
        frame_id=frame_id, turn_idx=turn_idx)
    out = {"uid": plan["uid"]}
    if op["answers_need"]:
        fill_planning_need(cid, op["answers_need"],
                           {"ref": {"plan": plan["uid"]}, "how": "planned"},
                           frame_id=frame_id, turn_idx=turn_idx)
        out["answered_need"] = op["answers_need"]
    return out


# -- post_artifact ------------------------------------------------------------

def _shape_post_artifact(op):
    if not _text(op.get("room"), 120):
        raise ValueError("post_artifact names the room")
    if not _text(op.get("description"), 80):
        raise ValueError("post_artifact describes the artifact")
    return {"room": _text(op.get("room"), 120),
            "description": _text(op.get("description"), 80),
            "report": dict(op["report"]) if isinstance(op.get("report"), dict) else {},
            "text": _text(op.get("text"), 600)}


def _preview_post_artifact(cid, frame_id, op, world):
    from story.artifacts import MAX_ARTIFACTS, POSTED, standing_artifacts
    errors = []
    if not _room_known(world, op["room"]):
        errors.append("post_artifact places a bill in %r, which exists nowhere"
                      % op["room"])
    standing = [a for a in standing_artifacts(cid)
                if a.get("status") == POSTED]
    if len(standing) >= MAX_ARTIFACTS:
        errors.append("the story already holds %d posted artifacts (cap %d)"
                      % (len(standing), MAX_ARTIFACTS))
    return {"changes": [{"kind": "artifact_posted", "room": op["room"],
                         "description": op["description"]}],
            "errors": errors, "warnings": []}


def _apply_post_artifact(cid, frame_id, op, turn_idx):
    from core.db import wget_for_frame, wset_for_frame
    from story.artifacts import ARTIFACTS_WORLD_KEY, new_artifact

    artifact = new_artifact(cid, room=op["room"], turn=turn_idx,
                            description=op["description"], report=op["report"],
                            posted_by="")
    artifact["text"] = op["text"]
    artifact["authored"] = "writers_room"
    stored = wget_for_frame(cid, ARTIFACTS_WORLD_KEY, frame_id, []) or []
    stored = [a for a in stored if isinstance(a, dict)
              and a.get("uid") != artifact["uid"]] + [artifact]
    wset_for_frame(cid, ARTIFACTS_WORLD_KEY, stored, frame_id)
    return {"uid": artifact["uid"]}


# -- schedule_event -----------------------------------------------------------

def _shape_schedule_event(op):
    summary = _text(op.get("summary"), 400)
    if not summary:
        raise ValueError("schedule_event states what happens")
    try:
        due = int(op.get("due_in_turns") or 1)
    except (TypeError, ValueError):
        raise ValueError("schedule_event due_in_turns is a number of turns")
    if due < 1 or due > EVENT_DUE_CAP:
        raise ValueError("schedule_event is due 1..%d turns ahead" % EVENT_DUE_CAP)
    return {"summary": summary, "due_in_turns": due}


def _preview_schedule_event(cid, frame_id, op, world):
    return {"changes": [{"kind": "event_scheduled", "summary": op["summary"],
                         "due_in_turns": op["due_in_turns"]}],
            "errors": [], "warnings": []}


def _apply_schedule_event(cid, frame_id, op, turn_idx):
    from story.authored_events import mint_authored_events

    minted = mint_authored_events(
        cid, turn_idx, [{"summary": op["summary"],
                         "due_in_turns": op["due_in_turns"]}],
        source="writers_room")
    return {"minted": minted}


# -- file_lore ----------------------------------------------------------------

#: What the room's durable setting facts are filed as. The room is an
#: author supplying canon, which is what `imported_canon` names; the
#: adjudicator is the package, so a reader can trace the entry to it.
LORE_DISPOSITION = "imported_canon"


def _shape_file_lore(op):
    content = _text(op.get("content"), 4000)
    if not content:
        raise ValueError("file_lore carries the entry's content")
    subject = _text(op.get("subject_id"), 120)
    if not subject:
        raise ValueError("file_lore names its subject id (a room id, a plan uid, "
                         "a charter key, or an id-shaped slug for a setting fact)")
    from mind.memory import LORE_CATEGORIES
    category = _text(op.get("category"), 40) or "other"
    if category not in LORE_CATEGORIES:
        raise ValueError("file_lore category %r is not one of %s"
                         % (category, ", ".join(LORE_CATEGORIES)))
    return {
        "subject_id": subject,
        "subject_kind": _text(op.get("subject_kind"), 40) or "place",
        "keys": _text(op.get("keys"), 400),
        "title": _text(op.get("title"), 200),
        "content": content,
        "category": category,
        "knowledge_locations": [_text(x, 120) for x in op.get("knowledge_locations") or ()
                                if _text(x, 120)],
        "book_id": op.get("book_id"),
    }


def _target_book(cid, world, op):
    from mind.memory import chat_lorebook_ids
    attached = set(chat_lorebook_ids(cid))
    canon = world["chat"].get("lorebook_id")
    if canon:
        attached.add(int(canon))
    if op.get("book_id") is not None:
        try:
            book = int(op["book_id"])
        except (TypeError, ValueError):
            return None, attached
        return (book if book in attached else None), attached
    return (int(canon) if canon else None), attached


def _preview_file_lore(cid, frame_id, op, world):
    from mind.canon_provenance import promote
    errors, warnings = [], []
    book, attached = _target_book(cid, world, op)
    if book is None:
        errors.append("file_lore has no book: the chat has no canon lorebook "
                      "and the named book is not attached")
    record = {"disposition": "provisional",
              "subject": {"kind": op["subject_kind"], "id": op["subject_id"]},
              "base_turn": 0, "basis": "model"}
    try:
        promote(record, LORE_DISPOSITION, adjudicator="writers_room")
    except ValueError as exc:
        errors.append("file_lore: %s" % exc)
    return {"changes": [{"kind": "lore_filed", "book_id": book,
                         "title": op["title"] or op["keys"],
                         "category": op["category"]}],
            "errors": errors, "warnings": warnings}


def _apply_file_lore(cid, frame_id, op, turn_idx, package_uid_=""):
    from mind.canon_provenance import promote
    from mind.memory import add_lore

    world = {"chat": _chat_row(cid)}
    book, _attached = _target_book(cid, world, op)
    record = promote({
        "disposition": "provisional",
        "subject": {"kind": op["subject_kind"], "id": op["subject_id"]},
        "base_turn": int(turn_idx), "basis": "model",
    }, LORE_DISPOSITION, adjudicator="writers_room:%s" % package_uid_)
    provenance = "%s by %s (subject %s)" % (
        record["disposition"], record["adjudicator"], op["subject_id"])
    entry_id = add_lore(
        book, op["keys"] or op["title"], op["content"], turn_added=turn_idx,
        category=op["category"], title=op["title"] or None,
        knowledge_locations=op["knowledge_locations"] or None,
        source_notes=provenance)
    return {"entry_id": entry_id, "book_id": book}


def _chat_row(cid):
    from core.db import q
    row = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    return dict(row) if row else {}


# -- answer_need / close_need -------------------------------------------------

def _shape_answer_need(op):
    uid = _text(op.get("need_uid"), 60)
    if not uid:
        raise ValueError("answer_need names the need uid")
    fill = op.get("fill") if isinstance(op.get("fill"), dict) else {}
    if not fill:
        raise ValueError("answer_need says what fills the need")
    return {"need_uid": uid, "fill": dict(fill)}


def _preview_answer_need(cid, frame_id, op, world):
    errors = []
    if op["need_uid"] not in world["needs"]:
        errors.append("need %r is not open" % op["need_uid"])
    return {"changes": [{"kind": "need_filled", "need_uid": op["need_uid"]}],
            "errors": errors, "warnings": []}


def _apply_answer_need(cid, frame_id, op, turn_idx):
    from world.planning_needs import fill_planning_need
    record = fill_planning_need(cid, op["need_uid"], op["fill"],
                                frame_id=frame_id, turn_idx=turn_idx)
    return {"need_uid": op["need_uid"], "filled": record is not None}


def _shape_close_need(op):
    uid = _text(op.get("need_uid"), 60)
    reason = _text(op.get("reason"), 200)
    if not uid or not reason:
        raise ValueError("close_need names the need uid and the reason")
    return {"need_uid": uid, "reason": reason}


def _preview_close_need(cid, frame_id, op, world):
    errors = []
    if op["need_uid"] not in world["needs"]:
        errors.append("need %r is not open" % op["need_uid"])
    return {"changes": [{"kind": "need_closed", "need_uid": op["need_uid"]}],
            "errors": errors, "warnings": []}


def _apply_close_need(cid, frame_id, op, turn_idx):
    from world.planning_needs import close_planning_need
    record = close_planning_need(cid, op["need_uid"], op["reason"],
                                 frame_id=frame_id)
    return {"need_uid": op["need_uid"], "closed": record is not None}


# -- request_location (LONG: a model call; runs in prepare) -------------------

def _shape_request_location(op):
    request = op.get("request") if isinstance(op.get("request"), dict) else {}
    if not _text(request.get("name") or request.get("brief"), 200):
        raise ValueError("request_location carries a generation request with "
                         "a name or a brief")
    return {"request": copy.deepcopy(request)}


def _preview_request_location(cid, frame_id, op, world):
    from world.charter_runtime import lived_location_job
    errors, warnings = [], []
    job = lived_location_job(cid)
    if job and job.get("status") == "running":
        errors.append("a lived-location generation is already running")
    if op.get("prepared"):
        warnings.append("request_location already prepared: %s"
                        % _text(op["prepared"].get("summary"), 200))
    return {"changes": [{"kind": "location_generated",
                         "name": _text(op["request"].get("name"), 200),
                         "prepared": bool(op.get("prepared"))}],
            "errors": errors, "warnings": warnings}


def _prepare_request_location(cid, frame_id, op):
    from world.charter_runtime import generate_lived_location
    result = generate_lived_location(cid, op["request"], frame_id=frame_id)
    result = result if isinstance(result, dict) else {}
    town = result.get("town") if isinstance(result.get("town"), dict) else {}
    rooms = town.get("rooms") if isinstance(town.get("rooms"), dict) else {}
    return {"summary": _text(town.get("name") or op["request"].get("name")
                             or "generated", 400),
            "rooms": sorted(str(r) for r in rooms)[:LIST_CAP],
            "charters": sorted(str(c) for c in (town.get("charters") or {}))[:LIST_CAP]
            if isinstance(town.get("charters"), dict) else [],
            "at": time.time()}


# -- presimulate (LONG: deterministic but seconds; runs in prepare) ----------

def _shape_presimulate(op):
    try:
        hours = float(op.get("hours") or 0.0)
    except (TypeError, ValueError):
        raise ValueError("presimulate hours is a number")
    if hours <= 0 or hours > PRESIM_HOURS_CAP:
        raise ValueError("presimulate lives the town forward 0 < hours <= %g"
                         % PRESIM_HOURS_CAP)
    return {"hours": hours,
            "charters": [_text(c, 80) for c in op.get("charters") or () if _text(c, 80)]}


def _preview_presimulate(cid, frame_id, op, world):
    errors = []
    items = (world["registry"].get("items") or {})
    if not items:
        errors.append("presimulate: the story has no charter registry")
    for key in op["charters"]:
        if key not in items:
            errors.append("presimulate names charter %r, which does not exist" % key)
    return {"changes": [{"kind": "presimulated", "hours": op["hours"],
                         "charters": op["charters"] or sorted(items)}],
            "errors": errors, "warnings": []}


def _prepare_presimulate(cid, frame_id, op):
    from world.charter_runtime import (land_presim, presim_registry,
                                       registry_for, registry_revision)
    registry = registry_for(cid, frame_id)
    expected = registry_revision(registry)
    advanced, produced = presim_registry(
        registry, horizon_hours=op["hours"], active_tail_hours=0.0,
        tail_places=(), seed=int(hashlib.sha256(
            ("%s|%s" % (cid, op["hours"])).encode("utf-8")).hexdigest()[:8], 16))
    land_presim(cid, frame_id, advanced, produced,
                base_turn=_latest_turn_idx(cid, frame_id),
                expected_revision=expected)
    return {"summary": "lived %g hours forward" % op["hours"],
            "events": len(produced) if isinstance(produced, (list, tuple)) else 0,
            "at": time.time()}


#: THE CLOSED TABLE. Every way a package can touch the world, each over one
#: existing seam. A kind absent here is refused at draft time.
OPERATIONS = {
    "plan_rooms": {"shape": _shape_plan_rooms, "preview": _preview_plan_rooms,
                   "apply": _apply_plan_rooms, "long": False,
                   "seam": "world.structure.plant_structure"},
    "plan_entity": {"shape": _shape_plan_entity, "preview": _preview_plan_entity,
                    "apply": _apply_plan_entity, "long": False,
                    "seam": "world.planned_entities.add_planned_entity"},
    "post_artifact": {"shape": _shape_post_artifact,
                      "preview": _preview_post_artifact,
                      "apply": _apply_post_artifact, "long": False,
                      "seam": "story.artifacts.new_artifact"},
    "schedule_event": {"shape": _shape_schedule_event,
                       "preview": _preview_schedule_event,
                       "apply": _apply_schedule_event, "long": False,
                       "seam": "story.authored_events.mint_authored_events"},
    "file_lore": {"shape": _shape_file_lore, "preview": _preview_file_lore,
                  "apply": _apply_file_lore, "long": False,
                  "seam": "mind.canon_provenance.promote + add_lore"},
    "answer_need": {"shape": _shape_answer_need, "preview": _preview_answer_need,
                    "apply": _apply_answer_need, "long": False,
                    "seam": "world.planning_needs.fill_planning_need"},
    "close_need": {"shape": _shape_close_need, "preview": _preview_close_need,
                   "apply": _apply_close_need, "long": False,
                   "seam": "world.planning_needs.close_planning_need"},
    "request_location": {"shape": _shape_request_location,
                         "preview": _preview_request_location,
                         "prepare": _prepare_request_location, "long": True,
                         "seam": "world.charter_runtime.generate_lived_location"},
    "presimulate": {"shape": _shape_presimulate, "preview": _preview_presimulate,
                    "prepare": _prepare_presimulate, "long": True,
                    "seam": "world.charter_runtime.presim_registry + land_presim"},
}


#: THE FIELDS OF EACH KIND, as the model is told them (the draft_operation
#: tool description renders this table). A closed set the engine owns: the
#: shape functions above are the authority and this table restates them, so
#: a model drafts against a schema instead of guessing field names. Measured
#: live (chat 111, 2026-09-03): four drafts in a row were refused because the
#: model spelled the kind `kind` and the fields as it imagined them, and the
#: refusal named neither.
OPERATION_FIELDS = {
    "plan_rooms": {
        "structure": "{key, name} -- the structure the rooms belong to",
        "rooms": "{<room_id>: {name, purpose, access, adjacent: [{to: <room_id>, barrier?, bearing?}], frontier: [<direction>]}}",
        "owning_book_id?": "lorebook id"},
    "plan_entity": {
        "name": "the entity's name", "kind": "person | thing | creature",
        "role?": "what they are for, in a word or two", "aliases?": "[names]",
        "brief": "{purpose, truths, where: <room_id>}",
        "look?": "how they read at a glance", "answers_need?": "a planning-need uid"},
    "post_artifact": {"room": "<room_id>", "description": "what the bill is, briefly",
                      "text?": "what it says", "report?": "{...}"},
    "schedule_event": {"summary": "what happens", "due_in_turns": "1..EVENT_DUE_CAP"},
    "file_lore": {"subject_id": "a room id, a plan uid, a charter key, or an id-shaped slug",
                  "content": "the entry", "subject_kind?": "place | person | thing | setting",
                  "category?": "a lore category", "title?": "", "keys?": "comma-separated",
                  "knowledge_locations?": "[room ids]", "book_id?": "lorebook id"},
    "answer_need": {"need_uid": "an open need", "fill": "{...what fills it}"},
    "close_need": {"need_uid": "an open need", "reason": "why it closes unanswered"},
    "request_location": {"request": "{name | brief, ...as the Charter Planner returned it}"},
    "presimulate": {"hours": "0 < hours <= PRESIM_HOURS_CAP", "charters?": "[charter keys]"},
}


def operation_shape_text():
    """One line per kind for a tool description: `op` names the kind, the
    other keys are its fields (`?` marks an optional one)."""
    lines = []
    for kind, fields in OPERATION_FIELDS.items():
        lines.append("%s: %s" % (kind, ", ".join(
            "%s=%s" % (k, v) if v else k for k, v in fields.items())))
    return "; ".join(lines)


#: Who authored a package decides whether it needs a grant. A package the
#: HOST drafted by hand (`created_by` = "writers_room", the default) is the
#: host's own world and needs none; a package an AGENT drafted publishes only
#: under standing mandates that cover it (`story/mandates.py`). The Planner
#: passes its name through `room_tools.run_tool(actor=)`.
AGENT_AUTHORS = ("story_planner",)

#: The capability each authority flag asks for, in the mandate vocabulary.
AUTHORITY_CAPABILITY = {
    "may_create_people": "create_people",
    "may_author_prehistory": "author_prehistory",
    "may_schedule_harm": "schedule_harm",
}


def package_requirements(pkg):
    """The capabilities a package needs a grant for: one per operation kind
    it carries; `create_people` when an operation makes a person (a person
    plan, a location request); `author_prehistory` when one presimulates;
    `schedule_harm` when the package claims that authority; `surprise` when
    it is sealed. A flag a package merely carries by default is not an act
    and asks for nothing. The vocabulary is `mandates.MANDATE_CAPABILITIES`."""
    needed = []
    ops = list(pkg.get("operations") or ())
    for op in ops:
        if op["op"] not in needed:
            needed.append(op["op"])
    if any(op["op"] == "request_location"
           or (op["op"] == "plan_entity" and op.get("kind") == "person")
           for op in ops):
        needed.append(AUTHORITY_CAPABILITY["may_create_people"])
    if any(op["op"] == "presimulate" for op in ops):
        needed.append(AUTHORITY_CAPABILITY["may_author_prehistory"])
    if (pkg.get("authority") or {}).get("may_schedule_harm"):
        needed.append(AUTHORITY_CAPABILITY["may_schedule_harm"])
    if pkg.get("spoiler_policy") == "sealed":
        needed.append("surprise")
    return needed


def authority_errors(cid, frame_id, pkg):
    """Why the standing mandates refuse this package, as error strings; empty
    when the package is the host's own or the grants cover it. The named
    `authority.mandate_uid`, when set, must itself be active."""
    if str((pkg.get("provenance") or {}).get("created_by") or "") not in AGENT_AUTHORS:
        return []
    from story.mandates import active_mandates, citation, coverage
    errors = []
    named = str((pkg.get("authority") or {}).get("mandate_uid") or "")
    if named:
        active = {m["uid"] for m in active_mandates(cid, frame_id)}
        if named not in active:
            errors.append("the package cites mandate %s, which is not active (%s)"
                          % (named, citation(cid, frame_id, [named]) or "unknown"))
    cov = coverage(cid, frame_id, package_requirements(pkg))
    if not cov["ok"]:
        errors.append(
            "no standing mandate permits %s; the room does not do this unasked "
            "-- ask the player for the grant%s"
            % (", ".join(cov["missing"]),
               (" (standing: %s)" % citation(cid, frame_id, cov["cited"]))
               if cov["cited"] else ""))
    return errors


# ---------------------------------------------------------------------------
# Package-level validation
# ---------------------------------------------------------------------------

def _package_checks(pkg, world):
    """The checks that are about the package rather than an operation:
    evidence that is evidence (v2 § 5.3), clocks with a due, participants
    that resolve, sealed policy with an envelope, authority honoured."""
    errors, warnings = [], []
    if not pkg["operations"]:
        # A package with nothing in it validates clean and publishes nothing;
        # a model that read `ok: true` as "prepared" told the player so
        # (chat 111, 2026-09-03). Said here, where the verdict is built.
        warnings.append("the package carries no operations; publishing it "
                        "changes nothing")
    for ev in pkg["evidence"]:
        missing = [f for f in ("origin", "location", "bears_on", "admission_path")
                   if not ev.get(f)]
        if missing:
            errors.append("evidence %s lacks %s; a clue without an origin, a "
                          "place, a truth it bears on and a way to be found "
                          "is a label, not evidence" % (ev["id"], ", ".join(missing)))
        else:
            bears = ev["bears_on"] if isinstance(ev["bears_on"], list) else [ev["bears_on"]]
            truth_ids = {t["id"] for t in pkg["truths"]}
            for tid in bears:
                if tid not in truth_ids:
                    errors.append("evidence %s bears on %r, which is no truth "
                                  "of this package" % (ev["id"], tid))
    truths_with_evidence = set()
    for ev in pkg["evidence"]:
        bears = ev.get("bears_on") or []
        for tid in (bears if isinstance(bears, list) else [bears]):
            truths_with_evidence.add(tid)
    for truth in pkg["truths"]:
        if truth.get("superseded_by"):
            continue
        paths = sum(1 for ev in pkg["evidence"]
                    if truth["id"] in (ev.get("bears_on") or []))
        if pkg["spoiler_policy"] == "sealed" and paths < 2:
            warnings.append("truth %s has %d evidence path(s); a sealed truth "
                            "with one path is unknowable if that path is lost"
                            % (truth["id"], paths))
    for clock in pkg["clocks"]:
        if clock.get("due_story_hours") is None and clock.get("due_turns") is None:
            errors.append("clock %s has no due (due_story_hours or due_turns)"
                          % clock["id"])
    for part in pkg["participants"]:
        name = _text(part.get("name") or part.get("text"), 120)
        if name and name.casefold() not in world["reserved_names"]:
            planned = any(op["op"] == "plan_entity" and op["name"].casefold()
                          == name.casefold() for op in pkg["operations"])
            if not planned:
                warnings.append("participant %r is nobody the world holds and "
                                "no operation plans them" % name)
    if pkg["spoiler_policy"] == "sealed" and not pkg["constraints"]:
        warnings.append("a sealed package states its envelope as constraints "
                        "(forbidden content, protected characters, permitted "
                        "harm) so the host can approve what they cannot read")
    if not pkg["authority"]["may_create_people"]:
        for op in pkg["operations"]:
            if op["op"] == "plan_entity" and op["kind"] == "person" \
                    or op["op"] == "request_location":
                errors.append("the package's authority does not permit creating "
                              "people, and %s does" % op["op"])
    if not pkg["authority"]["may_author_prehistory"]:
        for op in pkg["operations"]:
            if op["op"] == "presimulate":
                errors.append("the package's authority does not permit authoring "
                              "prehistory, and presimulate does")
    return errors, warnings


def preview_package(cid, uid, *, frame_id=None):
    """The cross-system diff of a draft: what each operation would change,
    with the errors that would refuse it. Pure read."""
    pkg = _require(cid, uid, frame_id)
    world = _world_snapshot(cid, frame_id)
    changes, errors, warnings = [], [], []
    for i, op in enumerate(pkg["operations"]):
        result = OPERATIONS[op["op"]]["preview"](cid, frame_id, op, world)
        # Operations see what EARLIER operations in the package establish:
        # a plan placed in a room the package plants is placed somewhere.
        if op["op"] == "plan_rooms" and not result["errors"]:
            world["planned"].update(op["rooms"])
        for change in result["changes"]:
            changes.append({"index": i, "op": op["op"], **change})
        errors.extend("op %d (%s): %s" % (i, op["op"], e) for e in result["errors"])
        warnings.extend("op %d (%s): %s" % (i, op["op"], w) for w in result["warnings"])
    p_errors, p_warnings = _package_checks(pkg, world)
    p_errors += authority_errors(cid, frame_id, pkg)
    return {"uid": pkg["uid"], "revision": pkg["revision"],
            "changes": changes, "errors": errors + p_errors,
            "warnings": warnings + p_warnings,
            "long_operations": [i for i, op in enumerate(pkg["operations"])
                                if OPERATIONS[op["op"]]["long"]
                                and not op.get("prepared")]}


def validate_package(cid, uid, *, frame_id=None):
    """Run the preview and record the verdict on the package at its current
    revision. Status passes through `validating` and returns to `draft`."""
    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    if pkg["status"] not in EDITABLE:
        raise ValueError("a %s package is not validated again" % pkg["status"])
    pkg["status"] = "validating"
    save_packages(cid, stored, frame_id)
    try:
        result = preview_package(cid, uid, frame_id=frame_id)
    finally:
        stored = packages(cid, frame_id)
        pkg = stored[str(uid)]
        pkg["status"] = "draft"
        save_packages(cid, stored, frame_id)
    pkg["validation"] = {"ok": not result["errors"], "errors": result["errors"],
                         "warnings": result["warnings"],
                         "at_revision": pkg["revision"]}
    _note(pkg, "validated", "ok" if not result["errors"]
          else "%d error(s)" % len(result["errors"]))
    stored[pkg["uid"]] = pkg
    save_packages(cid, stored, frame_id)
    return pkg["validation"]


def prepare_package(cid, uid, *, frame_id=None):
    """Run the LONG operations (a model call, a presimulation) before
    publish, each landing under its own seam's guard. Each prepared
    operation records what it produced; publish then refuses nothing on
    their account. A validated draft only."""
    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    if pkg["status"] not in EDITABLE:
        raise ValueError("a %s package is not prepared" % pkg["status"])
    if not pkg["validation"]["ok"] or pkg["validation"]["at_revision"] != pkg["revision"]:
        raise ValueError("validate the package at its current revision first")
    prepared = []
    for i, op in enumerate(pkg["operations"]):
        spec = OPERATIONS[op["op"]]
        if not spec["long"] or op.get("prepared"):
            continue
        op["prepared"] = spec["prepare"](cid, frame_id, op)
        prepared.append(i)
        # Persist after EACH long operation: a crash between two leaves
        # the first recorded as done, so a retry does not run it twice.
        stored[pkg["uid"]] = pkg
        save_packages(cid, stored, frame_id)
    _note(pkg, "prepared", "%d operation(s)" % len(prepared))
    # The world moved under the long operations by design (rooms planted, a
    # registry saved); re-pin so publish does not read its own preparation
    # as a conflict.
    pkg["base"] = {"turn_idx": _latest_turn_idx(cid, frame_id),
                   "registry_revision": _registry_revision(cid, frame_id),
                   "pinned_at": time.time()}
    stored[pkg["uid"]] = pkg
    save_packages(cid, stored, frame_id)
    return {"prepared": prepared}


def publish_package(cid, uid, *, expected_revision=None, frame_id=None):
    """Land the package: ONE short transaction over the short operations.

    Refused: an unvalidated draft, a revision other than the caller
    expected, an unprepared long operation, or a CONFLICT -- history has
    moved since the base was pinned AND re-validation against the moved
    world fails. History that moved without breaking anything is a REBASE:
    the base is re-pinned and noted, and the publish proceeds. Visibility
    is next-turn by construction: `published_turn` is the latest turn row,
    and `visible_packages` serves the package only to turns after it.
    """
    from core.db import transaction

    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    if pkg["status"] not in EDITABLE:
        raise ValueError("a %s package is not published again" % pkg["status"])
    if expected_revision is not None and int(expected_revision) != pkg["revision"]:
        raise ValueError("the package is at revision %d, not %s"
                         % (pkg["revision"], expected_revision))
    if not pkg["validation"]["ok"] or pkg["validation"]["at_revision"] != pkg["revision"]:
        raise ValueError("validate the package at its current revision first")
    unprepared = [i for i, op in enumerate(pkg["operations"])
                  if OPERATIONS[op["op"]]["long"] and not op.get("prepared")]
    if unprepared:
        raise ValueError("operations %s are long and unprepared; prepare the "
                         "package first" % unprepared)
    # The grant is checked AGAIN here, not only at validation: a mandate
    # revoked between the two prevents the write (v2 § 14.1), and a queued
    # fill job publishes through this same seam.
    refused = authority_errors(cid, frame_id, pkg)
    if refused:
        raise ValueError("; ".join(refused))
    turn_idx = _latest_turn_idx(cid, frame_id)
    revision_now = _registry_revision(cid, frame_id)
    moved = (pkg["base"].get("turn_idx") != turn_idx
             or (pkg["base"].get("registry_revision") or "") != revision_now)
    if moved:
        result = preview_package(cid, uid, frame_id=frame_id)
        if result["errors"]:
            pkg["validation"] = {"ok": False, "errors": result["errors"],
                                 "warnings": result["warnings"],
                                 "at_revision": pkg["revision"]}
            _note(pkg, "conflict", "history moved: turn %s -> %s"
                  % (pkg["base"].get("turn_idx"), turn_idx), turn_idx)
            stored[pkg["uid"]] = pkg
            save_packages(cid, stored, frame_id)
            raise ValueError("conflict: history moved under the package and it "
                             "no longer validates: " + "; ".join(result["errors"][:4]))
        _note(pkg, "rebased", "history moved: turn %s -> %s"
              % (pkg["base"].get("turn_idx"), turn_idx), turn_idx)
        pkg["base"] = {"turn_idx": turn_idx, "registry_revision": revision_now,
                       "pinned_at": time.time()}
    applied = []
    with transaction():
        for i, op in enumerate(pkg["operations"]):
            spec = OPERATIONS[op["op"]]
            if spec["long"]:
                applied.append({"index": i, "op": op["op"],
                                "result": op.get("prepared")})
                continue
            if op["op"] == "file_lore":
                result = spec["apply"](cid, frame_id, op, turn_idx, pkg["uid"])
            else:
                result = spec["apply"](cid, frame_id, op, turn_idx)
            op["applied"] = result
            applied.append({"index": i, "op": op["op"], "result": result})
        pkg["status"] = "published"
        pkg["published_turn"] = turn_idx
        _note(pkg, "published", "%d operation(s)" % len(applied), turn_idx)
        stored[pkg["uid"]] = pkg
        save_packages(cid, stored, frame_id)
    return {"uid": pkg["uid"], "revision": pkg["revision"],
            "published_turn": turn_idx, "visible_from_turn": turn_idx + 1,
            "applied": applied}


def visible_packages(cid, turn_idx, *, frame_id=None):
    """The landed packages a turn may see: published before it, never in
    it. What the pipeline (and later the Planner's frontier) reads."""
    return [p for p in packages(cid, frame_id).values()
            if p["status"] in ("published", "active")
            and p.get("published_turn") is not None
            and int(p["published_turn"]) < int(turn_idx)]


def activate_due_packages(cid, turn_idx, *, frame_id=None):
    """`published -> active` for every package a turn has now seen.
    Idempotent bookkeeping, called from the commit's out-of-band tail.
    Returns the uids activated."""
    stored = packages(cid, frame_id)
    activated = []
    for pkg in stored.values():
        if pkg["status"] == "published" and pkg.get("published_turn") is not None \
                and int(pkg["published_turn"]) < int(turn_idx):
            pkg["status"] = "active"
            pkg["activated_turn"] = int(turn_idx)
            _note(pkg, "activated", turn_idx=turn_idx)
            activated.append(pkg["uid"])
    if activated:
        save_packages(cid, stored, frame_id)
    return activated


def resolve_package(cid, uid, *, note="", frame_id=None):
    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    if pkg["status"] not in ("published", "active"):
        raise ValueError("a %s package is not resolved" % pkg["status"])
    turn_idx = _latest_turn_idx(cid, frame_id)
    pkg["status"] = "resolved"
    pkg["resolution"] = {"note": _text(note, 400), "turn_idx": turn_idx}
    _note(pkg, "resolved", note, turn_idx)
    save_packages(cid, stored, frame_id)
    return pkg


def retire_package(cid, uid, *, note="", frame_id=None):
    """Retire from any state. What a landed package placed in the world
    STAYS: retiring is the room closing its file, not the world forgetting
    a room it planted."""
    stored = packages(cid, frame_id)
    pkg = stored.get(str(uid))
    if pkg is None:
        raise ValueError("no package %r" % uid)
    if pkg["status"] == "retired":
        return pkg
    turn_idx = _latest_turn_idx(cid, frame_id)
    pkg["status"] = "retired"
    _note(pkg, "retired", note, turn_idx)
    save_packages(cid, stored, frame_id)
    return stored.get(pkg["uid"], pkg)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def package_projection(pkg):
    """The spoiler-safe view: what is in motion, never what it is. Counts,
    status, revision, validation verdicts without their text, clock labels
    and dues, the operation kinds. Shown for a sealed package until the
    host reveals it; an open package shows the whole record instead."""
    return {
        "uid": pkg["uid"], "title": pkg["title"], "status": pkg["status"],
        "revision": pkg["revision"], "spoiler_policy": pkg["spoiler_policy"],
        "published_turn": pkg.get("published_turn"),
        "counts": {field: len(pkg[field]) for field in _LIST_FIELDS},
        "operations": [op["op"] for op in pkg["operations"]],
        "clocks": [{"id": c["id"], "label": _text(c.get("label"), 80),
                    "due_story_hours": c.get("due_story_hours"),
                    "due_turns": c.get("due_turns")} for c in pkg["clocks"]],
        "validation": {"ok": pkg["validation"]["ok"],
                       "errors": len(pkg["validation"]["errors"]),
                       "warnings": len(pkg["validation"]["warnings"]),
                       "at_revision": pkg["validation"]["at_revision"]},
        "history": [{"revision": h.get("revision"), "action": h.get("action"),
                     "turn_idx": h.get("turn_idx")}
                    for h in pkg["provenance"].get("history") or ()][-12:],
        "sealed": pkg["spoiler_policy"] == "sealed",
    }


def package_view(cid, uid, *, reveal=False, frame_id=None):
    """What a reader may see: the record for an open package or a revealed
    sealed one; the projection otherwise."""
    pkg = _require(cid, uid, frame_id)
    if pkg["spoiler_policy"] == "sealed" and not reveal:
        return package_projection(pkg)
    return copy.deepcopy(pkg)


def list_packages(cid, *, status=None, frame_id=None):
    out = []
    for pkg in sorted(packages(cid, frame_id).values(),
                      key=lambda p: (p["provenance"].get("created_at") or 0.0)):
        if status and pkg["status"] != status:
            continue
        out.append(package_projection(pkg))
    return out
