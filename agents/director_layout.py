"""The layout tier: a planned building of several storeys is laid out by code
before any of its rooms is designed. OFF unless the host or the story turns
it on (`LAYOUT_TIER_SETTING`, `LAYOUT_TIER_STORY_KEY`).

THE OWNER'S CHOICE (2026-10-08, survey rank 6, first slice): the layout lab's
solver as an out-of-band tier for planned buildings -- "a model decides what
and why, code decides where and how, and a model dresses it only when an
actor comes near". Two calls on the room designer's role say what each
planned room HOLDS (`prose_contract.layout_sort`) and how what it holds
RELATES (`prose_contract.layout_relate`); `world.layout_solver` places every
room, stair, doorway, window and fixture; `world.layout_bridge` holds the
answers to the plan and writes the solve as the plan's geometry
(`structure.write_planned_layout`). The rooms are then designed as every
planned room is (`director_rooms`), and a sited room is "described, never
re-measured" (`spatial_merge`).

WHERE IT RUNS, AND WHY THERE: inside the job that builds the rooms in view
or ahead of any actor (`director_rooms._predevelop_run`), before that job
designs anything. Of the three places the brief offered:
* the ROOMS-IN-VIEW JOB is the owner's heavy tier -- "save heavy plans for
  when the actors near them" -- already out of band, bounded per run, backed
  off on failure and stopped by a restore, on the same role the lab's two
  calls used, and the designer that dresses the building is the next thing
  that job does. A building nobody comes near costs nothing.
* the PLANTING SKETCH is ONE compact call by the owner's design; two more
  calls and an 11 s solve per building it plants would make it the heavy
  tier, for buildings most of which nobody visits (the hidden-draft
  predevelopment measured 19 of 25 designs never reaching a beat).
* a WRITERS' ROOM TOOL would put geometry inside the Planner's loop, whose
  waste the owner had just cut (77% of a fill's steps re-reading the world),
  and would run only where the Planner thought to call it.
What it gives up: a building far off is not laid out until an actor nears
it, so the height-aware far readers (`site_plan.plan_sight`, the landscape)
see it only then. Planting time is the place for that, if wanted.

NEVER A SECOND SCENE WRITER. The tier writes the PLAN (`room_registry`),
which only code reaches here. Every reader of the next beat reads the
scene through the plan (`structure.apply_solved_plans`, in `get_scene`), the
beat's commit merges onto it the same way (`compose_beat_scene`), and that
commit's fringe pass lays the plan onto the stubs it stores
(`materialize_planned_fringe` -> `apply_planned_layout`). The job's own copy
of the scene is laid on the plan the same way, so what it designs is what
the next beat holds, and a design filed for one of the building's rooms
before the solve is dropped (`director_rooms._predevelop_run`).

FAILS OPEN, ALWAYS: off, a building that is not one (`layout_bridge.
plan_buildings`), an answer that cannot be read, a solve the bridge refuses
(`layout_bridge.refusals`), a plan changed underneath, a cancelled job --
each leaves the plan as it was and the designer builds the rooms exactly as
it did before this existed. A failed attempt waits as a failed design does
(`director_rooms.predevelop_retry_beats`).
"""
from __future__ import annotations

import time

#: The host's switch, in the settings table. OFF unless set to
#: `1`/`on`/`true`/`yes` -- the owner compares the tier's buildings with the
#: designer's before it publishes to any story (the brief of 2026-10-08), and
#: the owner's comparison protocol for the layout lab applies
#: (`tools/layout_lab/baselines`).
LAYOUT_TIER_SETTING = "layout_solver_tier"
#: The STORY's switch: a world key of the chat, read before the host's, so
#: the tier can be turned on for one story to compare it there and nowhere
#: else -- or off in one story while the host has it on. `on`/`off` (and the
#: words `layout_tier_enabled` reads for each); absent, the host's switch
#: decides. A dial the author set, so a reroll or a restore keeps it
#: (`persist.checkpoints.SETTING_PROVENANCE`). Review of 2026-10-08, F8: the
#: one global switch could not turn the tier on "for a story".
LAYOUT_TIER_STORY_KEY = "layout_solver_tier"
#: Buildings laid out per run of the rooms-in-view job, at most. Each is two
#: calls on the room role and about 11 s of solve (the owner's preferred
#: shrine: 11.1 s for eleven rooms on four storeys), and the run then designs
#: up to `director_rooms.PREDEVELOP_PER_TURN` rooms besides. One, because a
#: run is one commit's and the actors near two planned buildings at once
#: have the second laid out by the next commit's run; a building is laid out
#: once for its plan, so this bounds a burst, never the work. Named per
#: ask-before-limiting.
LAYOUT_TIER_PER_RUN = 1
#: The world key filing each building's last attempt: `{building key:
#: {signature, turn, failed?, failed_turn?, reasons?, moved?, unplaced?}}`.
#: A reconstructible record: lost, a building is simply attempted again.
LAYOUT_RUNS_KEY = "layout_tier_runs"
#: The two calls' step keys, by which the capture files them
#: (`persist/llm_capture.py`).
SORT_STEP = "director_rooms_layout_sort"
RELATE_STEP = "director_rooms_layout_relate"


_ON = ("1", "on", "true", "yes")
_OFF = ("0", "off", "false", "no")


def layout_tier_enabled(cid=None) -> bool:
    """Whether planned buildings are laid out by the solver in chat `cid`:
    the story's own switch when it states one (`LAYOUT_TIER_STORY_KEY`),
    else the host's (`LAYOUT_TIER_SETTING`) -- OFF unless one of them says
    on."""
    from core.db import get_setting, wget
    if cid is not None:
        try:
            story = str(wget(cid, LAYOUT_TIER_STORY_KEY) or "").strip().casefold()
        except Exception:
            story = ""
        if story in _ON:
            return True
        if story in _OFF:
            return False
    try:
        raw = get_setting(LAYOUT_TIER_SETTING)
    except Exception:
        return False
    return str(raw or "").strip().casefold() in _ON


def _plan_specs(cid):
    """`{uid: (name, planned)}` for every live planned room, off the shared
    parse of the registry (`structure.registry_rows`)."""
    from world.structure import registry_rows
    return {uid: (str(entry["name"] or uid), entry["planned"])
            for uid, entry in registry_rows(cid).items()
            if entry["planned"] is not None}


def _default_call(step, system, payload):
    from agents.common import _agent_json
    return _agent_json("director_rooms", step, system, payload,
                       temperature=None, max_tokens=None)


def _read_runs(cid):
    from core.db import wget
    stored = wget(cid, LAYOUT_RUNS_KEY) or {}
    return stored if isinstance(stored, dict) else {}


def _file_run(cid, job, key, entry):
    """File one building's attempt onto the record as it stands now, in one
    transaction, and nothing once the job is cancelled
    (`director_rooms._file_prepared` states the same discipline)."""
    from core import jobs
    from core.db import transaction, wget, wset
    with transaction():
        if jobs.is_cancelled(job):
            return False
        stored = wget(cid, LAYOUT_RUNS_KEY) or {}
        stored = dict(stored) if isinstance(stored, dict) else {}
        stored[key] = entry
        wset(cid, LAYOUT_RUNS_KEY, stored)
    return True


def _waiting(entry, signature, turn_idx):
    """Whether a building's last attempt on this same plan failed too
    recently to try again (`director_rooms.predevelop_retry_beats`)."""
    from agents.director_rooms import predevelop_retry_beats
    from core.jobs import story_rewound_past
    if not isinstance(entry, dict) or entry.get("signature") != signature:
        return False
    if not int(entry.get("failed") or 0):
        return False
    at = entry.get("failed_turn")
    if at is None or turn_idx is None or story_rewound_past(at, turn_idx):
        return False
    return int(turn_idx) - int(at) < predevelop_retry_beats(entry.get("failed"))


def lay_out(building, call, language_id):
    """One building, solved: `(spec, layout, inventory, refusals)`. Raises
    when an answer cannot be read; refusals are the bridge's."""
    from llm.prompts import layout_prompt
    from world import layout_bridge
    sort_answer = call(SORT_STEP, layout_prompt("sort", language_id),
                       layout_bridge.sort_payload(building))
    inventory = layout_bridge.hold_inventory(building, sort_answer)
    relate_answer = call(RELATE_STEP, layout_prompt("relate", language_id),
                         layout_bridge.relate_payload(building, inventory))
    spec = layout_bridge.spec_from_answers(building, inventory, relate_answer)
    layout = layout_bridge.solve_spec(spec)
    return spec, layout, inventory, layout_bridge.refusals(building, spec, layout)


def lay_out_buildings(job, cid, scene, room_ids, language_id, *, call=None):
    """Lay out the planned buildings that hold any of `room_ids` and are not
    laid out yet, at most `LAYOUT_TIER_PER_RUN`; return `(scene, laid_out)`:
    `scene` with the solved plans laid onto its stubs (in place), and the ids
    of every room of a building this call laid out. Off, it returns `scene`
    untouched having read nothing. Never raises: a failure is filed and
    logged, and the designer builds the rooms as it always has."""
    laid_out = set()
    if not room_ids or not layout_tier_enabled(cid):
        return scene, laid_out
    from core import jobs
    from core.logging_utils import logger
    from world import layout_bridge, structure

    turn_idx = getattr(job, "base_turn", None)
    call = call or _default_call
    try:
        specs = _plan_specs(cid)
        held_open = structure.provisional_room_ids(cid)
        wanted = set(room_ids)
        buildings = [b for b in layout_bridge.plan_buildings(specs, scene, held_open=held_open)
                     if b["refusal"] is None and wanted & set(b["rooms"])]
    except Exception as exc:
        logger.info("layout tier: chat=%s could not read the plan: %s", cid, str(exc)[:300])
        return scene, laid_out
    runs = _read_runs(cid)
    done = 0
    for building in buildings:
        if done >= LAYOUT_TIER_PER_RUN or jobs.is_cancelled(job):
            break
        key, signature = building["key"], building["signature"]
        if _waiting(runs.get(key), signature, turn_idx):
            continue
        done += 1
        started = time.time()
        try:
            spec, layout, inventory, refused = lay_out(building, call, language_id)
        except Exception as exc:
            refused = [f"an answer could not be laid out: {' '.join(str(exc).split())[:300]}"]
            spec = layout = inventory = None
        if refused:
            failed = int((runs.get(key) or {}).get("failed") or 0) + 1 \
                if (runs.get(key) or {}).get("signature") == signature else 1
            entry = {"signature": signature, "turn": turn_idx, "failed": failed,
                     "failed_turn": turn_idx, "reasons": refused[:12],
                     "seconds": round(time.time() - started, 2)}
            _file_run(cid, job, key, entry)
            runs[key] = entry
            logger.info("layout tier: chat=%s building=%s refused (%d in a row): %s",
                        cid, key, failed, "; ".join(refused[:6]))
            continue
        solved, report = layout_bridge.planned_layout(building, spec, layout, turn=turn_idx,
                                                      inventory=inventory)
        written = structure.write_planned_layout(
            cid, solved, expected=building["specs"], job=job)
        if not written:
            logger.info("layout tier: chat=%s building=%s not written: the plan "
                        "changed, or the job was stopped", cid, key)
            continue
        entry = {"signature": signature, "turn": turn_idx, "plan": building["plan"],
                 "moved": len(report["moved"]), "unplaced": len(report["unplaced"]),
                 "restored": len(report["restored"]), "marks": len(report["marks"]),
                 "seconds": round(time.time() - started, 2)}
        _file_run(cid, job, key, entry)
        runs[key] = entry
        logger.info("layout tier: chat=%s building=%s laid out on %s in %.1fs; "
                    "%d fixtures moved off their wall and %d unplaced, both left "
                    "to the designer; %d the plan listed restored, %d ways marked",
                    cid, key, building["plan"], entry["seconds"], entry["moved"],
                    entry["unplaced"], entry["restored"], entry["marks"])
        structure.apply_planned_layout(scene, _plan_specs(cid), set(building["rooms"]))
        laid_out.update(building["rooms"])
    return scene, laid_out
