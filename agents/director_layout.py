"""The layout tier: a planned building of several storeys is laid out by code
before any of its rooms is designed. ON unless the host or the story turns
it off (`LAYOUT_TIER_SETTING`, `LAYOUT_TIER_STORY_KEY`). The owner's ruling of
2026-10-10, after their shrine (chat 164) was built with no solve at all:
on by default once the bridge lays a real Room plan cleanly -- the shrine's
own plan, replicated, against the layout lab's. Judged not yet clean after
the bridge lane's seven rounds; then, the shrine's lore refined for
placement and the Room's sides weighed as wishes, two of three answer sets
laid it out room for room as the lab did, and the owner: "It's ok enough
now" (`docs/design/DESIGN_LAYOUT_TIER.md`).

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

import copy
import json
import time

#: The host's switch, in the settings table. ON unless set to
#: `0`/`off`/`false`/`no` -- the owner's ruling of 2026-10-10, "Bridge lane
#: now, then on", met that day on the shrine's refined lore ("It's ok enough
#: now"); the owner's comparison protocol for the layout lab applies to
#: every change of the solver (`tools/layout_lab/baselines`).
LAYOUT_TIER_SETTING = "layout_solver_tier"
#: The STORY's switch: a world key of the chat, read before the host's, so
#: the tier can be turned on for one story to compare it there and nowhere
#: else -- or off in one story while the host has it on. `on`/`off` (and the
#: words `layout_tier_enabled` reads for each); absent, the host's switch
#: decides. A dial the author set, so a reroll or a restore keeps it
#: (`persist.checkpoints.SETTING_PROVENANCE`). Review of 2026-10-08, F8: the
#: one global switch could not turn the tier on "for a story".
LAYOUT_TIER_STORY_KEY = "layout_solver_tier"
#: THE GROUNDS' SWITCH (2026-10-11, the owner: "Tier lays out the grounds"):
#: whether the tier lays out the outdoor places a planned building stands in
#: with it (`layout_bridge._grounds_of`). OFF until the owner has judged the
#: comparison against the layout lab's liked shrine -- the lab's rule, that
#: a layout change is shown before it turns on. The host's setting, and the
#: story's own key read first, as the tier's own switch is.
LAYOUT_GROUNDS_SETTING = "layout_grounds"
LAYOUT_GROUNDS_STORY_KEY = "layout_grounds"
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
BRIEF_STEP = "director_rooms_layout_brief"


_ON = ("1", "on", "true", "yes")
_OFF = ("0", "off", "false", "no")


def layout_grounds_enabled(cid=None) -> bool:
    """Whether the tier lays out a building's grounds with it in chat `cid`:
    the story's own switch when it states one, else the host's -- OFF unless
    one of them says on (`LAYOUT_GROUNDS_SETTING`)."""
    from core.db import get_setting, wget
    if cid is not None:
        try:
            story = str(wget(cid, LAYOUT_GROUNDS_STORY_KEY) or "").strip().casefold()
        except Exception:
            story = ""
        if story in _ON:
            return True
        if story in _OFF:
            return False
    try:
        raw = get_setting(LAYOUT_GROUNDS_SETTING)
    except Exception:
        return False
    return str(raw or "").strip().casefold() in _ON


def layout_tier_enabled(cid=None) -> bool:
    """Whether planned buildings are laid out by the solver in chat `cid`:
    the story's own switch when it states one (`LAYOUT_TIER_STORY_KEY`),
    else the host's (`LAYOUT_TIER_SETTING`) -- ON unless one of them says
    off."""
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
        return True
    return str(raw or "").strip().casefold() not in _OFF


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


def _recording(cid, call):
    """`call`, with each of its provider calls recorded for chat `cid`.

    THE TIER'S CALLS ARE RECORDED (2026-10-11). It runs in the job that builds
    the rooms in view, where `core.jobs` clears the step's exchange sink, and
    at the launch, before any turn -- so no capture held one of its calls: the
    owner's database, capture on with full bodies, held ten step keys and
    none of them the tier's. Each call is filed as the Room's are, under the
    turn in play or held until the story has one
    (`llm_capture.record_chat_exchange`), under its own step key. A call a
    step is already recording is left to that step."""
    def recorded(step, system, payload):
        from core.pipeline_context import current_exchange_sink
        if current_exchange_sink.get() is not None:
            return call(step, system, payload)

        def sink(entry):
            from persist.llm_capture import record_chat_exchange
            record_chat_exchange(cid, step_key=step, **{
                k: v for k, v in entry.items() if k != "step_key"})
        token = current_exchange_sink.set(sink)
        try:
            return call(step, system, payload)
        finally:
            current_exchange_sink.reset(token)
    return recorded


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
    when an answer cannot be read; refusals are the bridge's. The spec
    carries the brief the two calls followed (`brief`), for the record.

    THE GROUNDS NEVER COST THE HOUSE ITS LAYOUT. Where the ground laid round
    a building leaves every seed refused, the building is solved again from
    the same two answers as the tier laid it before the grounds
    (`layout_bridge.without_grounds`) -- no further call -- and the spec says
    why the ground was left where the plan had it (`grounds_dropped`)."""
    from llm.prompts import layout_prompt
    from world import layout_bridge
    building = _briefed(building, call, language_id)
    sort_answer = call(SORT_STEP, layout_prompt("sort", language_id),
                       layout_bridge.sort_payload(building))
    inventory = layout_bridge.hold_inventory(building, sort_answer)
    relate_answer = call(RELATE_STEP, layout_prompt("relate", language_id),
                         layout_bridge.relate_payload(building, inventory))
    spec = layout_bridge.spec_from_answers(building, inventory, copy.deepcopy(relate_answer))
    if building.get("brief"):
        spec["brief"] = building["brief"]
    layout, refused = layout_bridge.solve_for(building, spec)
    if refused and building.get("grounds"):
        house = layout_bridge.without_grounds(building)
        bare = layout_bridge.spec_from_answers(house, inventory, copy.deepcopy(relate_answer))
        bare_layout, bare_refused = layout_bridge.solve_for(house, bare)
        if not bare_refused:
            bare["grounds_dropped"] = list(refused[:12])
            if building.get("brief"):
                bare["brief"] = building["brief"]
            return bare, bare_layout, inventory, bare_refused
    return spec, layout, inventory, refused


def _briefed(building, call, language_id):
    """THE ARCHITECT'S BRIEF: `building` carrying a short account of how it
    stands as a whole -- where each room lies, the wall each stair runs
    along, the room it rises from and the room it arrives in -- written by
    one call on the room role before the two that lay it out, and followed by
    both (`brief`). The owner's choice of 2026-10-10 ("the brief is a good
    idea too"): the layout lab's liked shrine was laid out from lore
    rewritten for placement, while most stories' lore says what a room holds
    and seldom where it stands; the shrine's own lore, unrefined, put its
    stairs mid-building and laid out messy, and a brief written this way
    stood on two of three answer sets where the plain lore stood on none
    (`docs/design/DESIGN_LAYOUT_TIER.md`). Fails open: no brief -- the call
    failed, or wrote nothing -- and the two calls read the lore alone."""
    from core.logging_utils import logger
    from llm.prompts import layout_prompt
    from world import layout_bridge
    try:
        answer = call(BRIEF_STEP, layout_prompt("brief", language_id),
                      layout_bridge.brief_payload(building))
    except Exception as exc:
        logger.info("layout tier: building=%s wrote no brief: %s", building.get("key"),
                    " ".join(str(exc).split())[:200])
        return building
    brief = str(answer.get("brief") or "").strip() if isinstance(answer, dict) else ""
    return dict(building, brief=brief) if brief else building


#: The most of the story's own lore about one building the tier's two calls
#: read (`building_description`), in characters, whole entries only. The
#: layout lab's liked shrine was laid out from 14k characters of description
#: (`tools/layout_lab/briefs`); the shrine's own entries in the owner's
#: lorebook that name it or its rooms come to about 10k. Named per
#: ask-before-limiting.
LAYOUT_DESCRIPTION_CHARS = 16000


def _label(text, articles):
    """A name as the lore's labels are compared: slugged
    (`spatial.normalize_room_id`), a leading article set aside -- the pack's
    own article list (`compositor.articles`), so "The Shrine of the Golden
    Fox" is the key "shrine of the golden fox" -- and nothing else changed."""
    from world.spatial import normalize_room_id
    slug = normalize_room_id(str(text or ""))
    head, _sep, rest = slug.partition("_")
    return rest if rest and head in articles else slug


def building_description(cid, building, frame_id=None):
    """WHAT THE STORY'S OWN LORE SAYS OF THIS BUILDING, for the tier's two
    calls: every entry of the chat's lorebooks (`chat_lorebook_ids`, the
    story's overlays merged by `lore_rows`) whose authored labels -- its
    keys, title, aliases and uid -- name the building or one of its rooms by
    name or id, the entries naming the building itself first, then in the
    books' own order, whole, up to `LAYOUT_DESCRIPTION_CHARS`. "" when none.

    The plan holds a room's one-line purpose; the lore holds what the room is
    -- its fixtures, its windows, what its floor is laid with -- and a solver
    sizes a room by what it holds. Without it the owner's shrine (chat 164)
    came back with every room a third of its planned size; the layout lab's
    liked shrine was laid out FROM such a description. Matched by the labels
    the lorebook's author wrote, WHOLE -- a key that runs on past a room's
    name ("seal cavern divine side") names somewhere else, and a word the
    building's name merely contains ("shrine") names no building -- never by
    reading the entries' prose. On the owner's lorebook this is exactly the
    seven entries the layout lab was laid out from, less the grounds."""
    from language_runtime import compositor_value
    from mind.memory import chat_lorebook_ids, lore_rows
    articles = {str(a).casefold() for a in compositor_value("articles") or ()}
    own = {_label(building.get("structure"), articles),
           _label(building.get("structure_name"), articles)}
    building_labels = set(own)
    for uid in building.get("rooms") or ():
        building_labels.add(_label(uid, articles))
        building_labels.add(_label((building.get("names") or {}).get(uid), articles))
    building_labels.discard("")
    own.discard("")
    ids = chat_lorebook_ids(cid)
    if not ids:
        return ""
    first, rest = [], []
    for row in lore_rows(ids, chat_id=cid, frame_id=frame_id):
        row = dict(row)
        labels = {_label(row.get("title"), articles), _label(row.get("entry_uid"), articles)}
        labels.update(_label(key, articles) for key in str(row.get("keys") or "").split(","))
        aliases = row.get("aliases")
        try:
            aliases = json.loads(aliases) if isinstance(aliases, str) else aliases
        except ValueError:
            aliases = []
        labels.update(_label(a, articles) for a in (aliases or ()) if a)
        labels.discard("")
        if not labels & building_labels:
            continue
        text = str(row.get("content") or "").strip()
        if not text:
            continue
        (first if labels & own else rest).append(text)
    out, total = [], 0
    for text in first + rest:
        if total + len(text) > LAYOUT_DESCRIPTION_CHARS:
            continue
        out.append(text)
        total += len(text) + 2
    return "\n\n".join(out)


def lay_out_opening_ground(cid, frame_id=None, *, call=None):
    """THE BUILDING THE OPENING STANDS IN IS LAID OUT BEFORE ANY OF IT IS
    DESCRIBED. Returns the ids of the rooms laid out; never raises.

    The tier's own run is the rooms-in-view job, after a beat -- and a story
    that OPENS inside a planned building never got one there: the opening
    had described the room the player woke in by then, and a room the story
    has seen is never re-measured (`layout_bridge.plan_buildings` refuses the
    building). The owner's shrine, chat 164 (2026-10-10), was built with no
    solve at all for exactly that, with Hinami waking on its second floor.
    So the opening plan (`story_planner.run_opening_plan`), once the Room has
    placed the opening's bodies, lays out the buildings their rooms belong
    to -- the tier's planting-time option, taken for the one building the
    first beat is sure to stand in -- and turn 0 describes rooms that
    already stand on their solve (`structure.apply_solved_plans`)."""
    from core.logging_utils import logger
    try:
        from core.db import wget_for_frame
        from language_runtime import story_language
        from story.opening_plan import opening_placements
        rooms = sorted({str(spot.get("room"))
                        for spot in (opening_placements(cid, frame_id) or {}).values()
                        if isinstance(spot, dict) and spot.get("room")})
        if not rooms:
            return set()
        scene = wget_for_frame(cid, "scene", frame_id) or {}
        _scene, laid = lay_out_buildings(None, cid, scene, rooms,
                                         story_language(cid), call=call)
        return set(laid)
    except Exception as exc:
        logger.info("layout tier: chat=%s could not lay out the opening's "
                    "ground: %s", cid, str(exc)[:300])
        return set()


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
    call = _recording(cid, call or _default_call)
    try:
        specs = _plan_specs(cid)
        held_open = structure.provisional_room_ids(cid)
        wanted = set(room_ids)
        buildings = [b for b in layout_bridge.plan_buildings(
                         specs, scene, held_open=held_open,
                         grounds=layout_grounds_enabled(cid))
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
            described = building_description(cid, building)
        except Exception:
            described = ""
        if described:
            building = dict(building, description=described)
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
            if (spec or {}).get("brief"):
                entry["brief"] = spec["brief"]
            _file_run(cid, job, key, entry)
            runs[key] = entry
            logger.info("layout tier: chat=%s building=%s refused (%d in a row): %s",
                        cid, key, failed, "; ".join(refused[:6]))
            continue
        if spec.get("grounds_dropped"):
            building = layout_bridge.without_grounds(building)
            logger.info("layout tier: chat=%s building=%s laid out without its grounds: %s",
                        cid, key, "; ".join(spec["grounds_dropped"][:6]))
        solved, report = layout_bridge.planned_layout(building, spec, layout, turn=turn_idx,
                                                      inventory=inventory)
        written = structure.write_planned_layout(
            cid, solved, expected={**building["specs"], **(building.get("ground_specs") or {})},
            job=job)
        if not written:
            logger.info("layout tier: chat=%s building=%s not written: the plan "
                        "changed, or the job was stopped", cid, key)
            continue
        entry = {"signature": signature, "turn": turn_idx, "plan": building["plan"],
                 "moved": len(report["moved"]), "unplaced": len(report["unplaced"]),
                 "restored": len(report["restored"]), "marks": len(report["marks"]),
                 "seconds": round(time.time() - started, 2)}
        if "grounds" in report:
            entry["grounds"] = len(report["grounds"])
            entry["grounds_unplaced"] = list(report["grounds_unplaced"])
        if spec.get("grounds_dropped"):
            entry["grounds_dropped"] = list(spec["grounds_dropped"])
        if spec.get("brief"):
            entry["brief"] = spec["brief"]
        _file_run(cid, job, key, entry)
        runs[key] = entry
        logger.info("layout tier: chat=%s building=%s laid out on %s in %.1fs; "
                    "%d fixtures moved off their wall and %d unplaced, both left "
                    "to the designer; %d the plan listed restored, %d ways marked",
                    cid, key, building["plan"], entry["seconds"], entry["moved"],
                    entry["unplaced"], entry["restored"], entry["marks"])
        # the building's rooms and the ground the solve laid round it
        rooms_laid = set(building["rooms"]) | set(solved)
        structure.apply_planned_layout(scene, _plan_specs(cid), rooms_laid)
        laid_out.update(rooms_laid)
    return scene, laid_out
