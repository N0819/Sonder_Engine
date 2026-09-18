"""The Writers' Room designs the location, a piece at a time.

`docs/design/DESIGN_ROOM_PRELUDE.md` § 4. Until 2026-09-17 one inhabited
location -- its rooms, its institutions, their posts and upkeeps and
economies, a naming law and a look law -- was one `utility`-role call over a
2,800-word system prompt that asked for the whole object at once
(`charter_generate._PLAN_SYSTEM`, `propose_town`). Two things were wrong with
that, and the owner named both (2026-09-17): **this is the Writers' Room's
work**, and a single JSON blob is **wildly inefficient next to the Room's
multi-tool-call planning and execution**. It shows in the failures the
one-shot kept having -- a plan cut off inside a washroom with 99% of a
16,000-token budget spent on a reasoning trace, a model handed a lore dump it
could not ask questions about.

So the plan is now DRAFTED. The Room reads the lore with the tools it already
has, lays out the rooms, adds one institution per call, asks the engine to
check what it has so far, fixes what comes back, and submits. The product is
the same artifact `propose_town` returned, so everything downstream --
`close_plan`, `plant_structure`, the presimulation, the history -- is
untouched: what changed is who writes it and how many looks they get at it.

**The check is the real one.** `review_location` runs the same deterministic
closure the pipeline will run (`charter_generate.close_plan`) against what is
drafted, and hands back the errors. A draft that cannot close cannot be
submitted, so the Room finds out from the engine rather than from a launch
that failed twenty seconds later.

**The draft is per-story and short-lived.** It opens when a location pass
starts and is cleared when the pass ends, whatever the outcome; nothing reads
it afterwards, because the plan it produced has become the job's artifact.
"""

from __future__ import annotations

import copy

from core.db import wget, wset

#: The open draft: `{"open", "task", "plan", "submitted", "checked"}`.
#: Unframed -- a location is designed at launch, before there is a frame.
DRAFT_KEY = "location_draft"

#: How much of one drafted piece is kept. A room or a charter that arrives
#: larger than this is not a room or a charter; it is a model pasting the
#: whole plan into one argument, which is the shape this module exists to
#: stop.
PIECE_CHARS = 60_000

#: The ceiling on a drafted plan, whole. `close_plan` will walk all of it and
#: `plant_structure` will write it, so an unbounded draft is an unbounded
#: transaction.
PLAN_CHARS = 400_000

#: The key the prehistory rides back to the runtime on, inside the plan
#: object. `charter_runtime._ROOM_PREHISTORY_KEY` is the same string, and
#: `tests/test_room_prelude.py` holds the two together.
PREHISTORY_KEY = "prehistory"


#: WHAT THE LAST LOCATION PASS DID: `{calls, steps, seconds, stopped, rooms,
#: charters, error, at}`. Written whatever happened, and kept after the draft
#: is cleared -- a generation that failed leaves a story in the library with
#: a retry, and this is what its author needs in order to decide whether to
#: ask for less. The question a planner pass could not answer before was the
#: owner's own, on chat 131: "what is the writers room actually doing in
#: those calls, I have no idea."
PASS_KEY = "location_plan"

#: THE PLAN THE ROOM SUBMITTED, KEPT UNTIL IT IS PLANTED. A location design
#: is the most expensive thing a launch does -- 227 to 250 seconds and six to
#: nine model calls, measured on chats 149 and 150 -- and until 2026-09-17 a
#: failure at ANY later stage threw it away: the job's artifact is saved
#: after the whole pure prefix, so a raise between the design and that save
#: cost the design, and the retry paid for it again. Owner, chat 150: "you've
#: made it so i have to rerun every single step instead of recovering from
#: what the writers room sucesfully planned".
#:
#: Keyed by the REQUEST it answers, so a retry that changed what it asked for
#: gets a fresh design rather than the last one's. Cleared when the plan is
#: planted, because after that the registry is the fact and this is a stale
#: copy of it.
SUBMITTED_KEY = "location_submitted"


def record_pass(cid, **fields):
    import time

    row = {"at": time.time(), **fields}
    wset(int(cid), PASS_KEY, row)
    return row


def pass_record(cid):
    return wget(int(cid), PASS_KEY, {}) or {}


def draft(cid):
    row = wget(int(cid), DRAFT_KEY, {}) or {}
    return copy.deepcopy(row) if isinstance(row, dict) else {}


def save_draft(cid, row):
    wset(int(cid), DRAFT_KEY, row)
    return row


def open_draft(cid, task):
    """Start a design. `task` carries what the closure will need when the
    draft is checked -- the featured residents, the reservation, the naming
    law, the population -- so the check the Room runs is the check the
    pipeline runs."""
    return save_draft(cid, {"open": True, "task": copy.deepcopy(task or {}),
                            "plan": {"name": "", "structure": {}, "rooms": {},
                                     "charters": []},
                            "history": {},
                            "submitted": False, "checked": False})


def close_draft(cid):
    """The pass is over. Cleared whatever happened: the plan it produced is
    the job's artifact now, and a draft left open would be offered to the
    next pass as work in progress."""
    wset(int(cid), DRAFT_KEY, {})


def is_open(cid):
    return bool(draft(cid).get("open"))


def _size(value):
    import json

    return len(json.dumps(value, ensure_ascii=False, default=str))


def _require_open(cid):
    row = draft(cid)
    if not row.get("open"):
        raise ValueError(
            "no location is being designed right now; these tools are for a "
            "location pass, which the engine opens when a story asks for a "
            "place with a life behind it")
    return row


def set_skeleton(cid, *, name=None, structure=None, rooms=None):
    """The location's name, its structure grammar, and rooms.

    Repeatable: rooms MERGE, so the map can be laid out over several calls
    and a room can be corrected by drafting it again under the same id. A
    name or a structure given again replaces the one before it."""
    row = _require_open(cid)
    plan = row["plan"]
    if name is not None:
        plan["name"] = str(name)[:200]
    if structure is not None:
        if not isinstance(structure, dict):
            raise ValueError("structure is an object: {key, max_planned, grammar}")
        if _size(structure) > PIECE_CHARS:
            raise ValueError("that structure is too large to be one structure")
        plan["structure"] = copy.deepcopy(structure)
    if rooms is not None:
        if not isinstance(rooms, dict):
            raise ValueError("rooms is an object keyed by room id")
        if _size(rooms) > PIECE_CHARS:
            raise ValueError("draft the rooms over several calls; that is more "
                             "than one call's worth of map")
        for room_id, room in rooms.items():
            if not isinstance(room, dict):
                raise ValueError("room %r is not an object" % room_id)
            plan["rooms"][str(room_id)] = copy.deepcopy(room)
    if _size(plan) > PLAN_CHARS:
        raise ValueError("this plan is larger than the engine will plant")
    row["checked"] = False
    save_draft(cid, row)
    return {"name": plan["name"], "rooms": sorted(plan["rooms"]),
            "charters": [c.get("key") for c in plan["charters"]],
            "structure": bool(plan["structure"])}


def set_charter(cid, charter):
    """One institution, whole. Drafting one whose `key` is already present
    replaces it, so a charter the check refused can be fixed by sending it
    again rather than by starting over."""
    row = _require_open(cid)
    if not isinstance(charter, dict):
        raise ValueError("a charter is an object")
    key = str(charter.get("key") or "").strip()
    if not key:
        raise ValueError("a charter carries a key: a stable machine id")
    if _size(charter) > PIECE_CHARS:
        raise ValueError("that charter is too large to be one institution")
    plan = row["plan"]
    kept = [c for c in plan["charters"] if str(c.get("key") or "") != key]
    kept.append(copy.deepcopy(charter))
    plan["charters"] = kept
    if _size(plan) > PLAN_CHARS:
        raise ValueError("this plan is larger than the engine will plant")
    row["checked"] = False
    save_draft(cid, row)
    return {"charters": [c.get("key") for c in plan["charters"]],
            "rooms": len(plan["rooms"])}


def drop_charter(cid, key):
    row = _require_open(cid)
    plan = row["plan"]
    before = len(plan["charters"])
    plan["charters"] = [c for c in plan["charters"]
                        if str(c.get("key") or "") != str(key)]
    row["checked"] = False
    save_draft(cid, row)
    return {"removed": before - len(plan["charters"]),
            "charters": [c.get("key") for c in plan["charters"]]}


def set_history(cid, *, eras=None, interventions=None):
    """The months behind the place, drafted by the same pass that drafted
    the place (`docs/design/DESIGN_ROOM_PRELUDE.md` § 4b).

    It used to be a second one-shot `utility` call
    (`charter_generate.propose_history`), and on chat 149 it is what
    actually failed a launch the Room had already designed correctly.
    Drafting it HERE also makes the review exact: `close_plan` takes the
    history, so a review that closed without one was answering a slightly
    different question from the launch."""
    row = _require_open(cid)
    history = row.get("history") or {}
    if eras is not None:
        if not isinstance(eras, list):
            raise ValueError("eras is a list of {name, summary}")
        history["eras"] = copy.deepcopy(eras)
    if interventions is not None:
        if not isinstance(interventions, list):
            raise ValueError("interventions is a list of operations")
        history["interventions"] = copy.deepcopy(interventions)
    if _size(history) > PIECE_CHARS:
        raise ValueError("that is more prehistory than the simulator will run")
    row["history"] = history
    row["checked"] = False
    save_draft(cid, row)
    return {"eras": len(history.get("eras") or []),
            "interventions": len(history.get("interventions") or [])}


def check(cid):
    """Run the closure the pipeline will run, and report what it said.

    THE CHECK IS THE REAL ONE, deliberately. A cheaper shape test written
    here would be a second opinion about what `close_plan` accepts, and the
    two would drift -- and the drift would show up as a launch that failed
    after the Room had been told its plan was good."""
    from world.charter_generate import close_plan

    row = _require_open(cid)
    plan = copy.deepcopy(row["plan"])
    task = row.get("task") or {}
    errors = []
    if not plan.get("name"):
        errors.append("the location has no name")
    if not plan.get("structure"):
        errors.append("no structure: the grammar the map is laid out under")
    if not plan.get("rooms"):
        errors.append("no rooms")
    if not plan.get("charters"):
        errors.append("no charters: nothing runs this place")
    if (row.get("task") or {}).get("wants_history") and not (
            (row.get("history") or {}).get("eras")
            or (row.get("history") or {}).get("interventions")):
        errors.append(
            "this launch asked for a place with months behind it and no "
            "prehistory is drafted: draft_history")
    town = None
    if not errors:
        try:
            town = close_plan(
                plan,
                # The history the Room drafted, not an empty one: the launch
                # closes with it, so a review that did not would be
                # answering a different question.
                history=row.get("history") or {},
                featured_residents=task.get("featured_residents") or [],
                reservation=_reservation(task, plan),
                naming_law=task.get("naming_law"),
                population=task.get("population"))
        except Exception as exc:
            errors.append("%s: %s" % (type(exc).__name__, str(exc)[:600]))
    unnamed = []
    if town is not None:
        unnamed = [
            "%s/%s" % (charter_key, body_key)
            for charter_key, state in (town.get("charters") or {}).items()
            for body_key, body in (state.get("bodies") or {}).items()
            if not str(body.get("name") or "").strip()
            or str(body.get("name") or "").strip() == str(body_key)]
        if unnamed:
            errors.append(
                "the naming law did not produce a usable name for every "
                "resident: " + ", ".join(unnamed[:8]))
    row["checked"] = not errors
    save_draft(cid, row)
    return {"ok": not errors, "errors": errors[:12],
            "rooms": len(plan.get("rooms") or {}),
            "charters": [c.get("key") for c in (plan.get("charters") or [])],
            "people": sum(len(state.get("bodies") or {})
                          for state in (town.get("charters") or {}).values())
            if town is not None else 0}


def _reservation(task, plan):
    """The story's registered identity forms, subtracted from whatever law
    this plan proposes.

    Derived from the DRAFT, by the same two lines `charter_runtime.
    _plan_lived_location` uses on the finished plan: without an authored law
    the reservation depends on the plan's own naming laws, so a value the
    caller computed before there was a plan would be a different reservation
    from the one the launch applies -- and a review that passed under it
    could still lose a resident's name when the launch ran."""
    from story.naming import story_identity_reservation
    from world.charter_runtime import _plan_naming_laws

    cid = task.get("chat_id")
    if cid is None:
        return None
    law = task.get("naming_law")
    laws = [law] if law else _plan_naming_laws(plan)
    try:
        return story_identity_reservation(int(cid), laws)
    except Exception:
        return None


def submit(cid):
    """Declare the plan finished. Refused unless the closure passed at the
    plan's CURRENT contents: every draft call clears `checked`, so a plan
    edited after its check has to be checked again."""
    row = _require_open(cid)
    if not row.get("checked"):
        result = check(cid)
        if not result["ok"]:
            raise ValueError(
                "this plan does not close yet: " + "; ".join(result["errors"][:4]))
        row = draft(cid)
    row["submitted"] = True
    save_draft(cid, row)
    return {"submitted": True,
            "rooms": len(row["plan"].get("rooms") or {}),
            "charters": [c.get("key") for c in (row["plan"].get("charters") or [])]}


def submitted_plan(cid):
    """The plan the Room submitted, or None. Shaped exactly as
    `charter_generate.propose_town` returns one, because it replaces it --
    plus the prehistory under `PREHISTORY_KEY` when one was drafted, which
    `charter_runtime._plan_lived_location` lifts off before anything reads
    the plan. One return value for two products the same pass wrote."""
    row = draft(cid)
    if not row.get("open") or not row.get("submitted"):
        return None
    plan = row.get("plan")
    if not isinstance(plan, dict):
        return None
    out = copy.deepcopy(plan)
    history = row.get("history") or {}
    if history.get("eras") or history.get("interventions"):
        out[PREHISTORY_KEY] = copy.deepcopy(history)
    return out


def keep_submitted(cid, digest, plan):
    """Hold the submitted plan against the request it answers, so that
    nothing after the design can cost the design."""
    import time

    wset(int(cid), SUBMITTED_KEY,
         {"digest": str(digest or ""), "plan": copy.deepcopy(plan),
          "at": time.time()})


def submitted_for(cid, digest):
    """The plan a previous pass submitted for this exact request, or None.

    The digest is what makes this a RESUME rather than a cache: an author
    who retries with a different brief is asking a different question and
    gets a fresh design."""
    row = wget(int(cid), SUBMITTED_KEY, {}) or {}
    if not isinstance(row, dict) or not isinstance(row.get("plan"), dict):
        return None
    if str(row.get("digest") or "") != str(digest or ""):
        return None
    return copy.deepcopy(row["plan"])


def forget_submitted(cid):
    """The plan is planted; the registry is the fact now, and this is a
    stale copy of it."""
    wset(int(cid), SUBMITTED_KEY, {})
