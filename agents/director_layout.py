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
#: with it (`layout_bridge._grounds_of`). ON unless set to `0`/`off`/`false`/
#: `no` -- the owner's word the same day, having seen the comparison against
#: the layout lab's liked shrine (the lab's rule, that a layout change is
#: shown before it turns on): "I would like layout grounds on". The host's
#: setting, and the story's own key read first, as the tier's own switch is.
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
#: {signature, turn, failed?, failed_turn?, reasons?, moved?, unplaced?,
#: warnings?}}`. A reconstructible record: lost, a building is simply
#: attempted again.
LAYOUT_RUNS_KEY = "layout_tier_runs"
#: How many of an attempt's refusals and of its solve's warnings its run
#: record keeps -- the 12 the refusals were always cut to, now named and
#: applied to the warnings too. Diagnostic only: the log keeps every one.
LAYOUT_RUN_NOTES_MAX = 12
#: The two calls' step keys, by which the capture files them
#: (`persist/llm_capture.py`).
SORT_STEP = "director_rooms_layout_sort"
RELATE_STEP = "director_rooms_layout_relate"
BRIEF_STEP = "director_rooms_layout_brief"
#: The architect's first call, which chooses the lore the other three read
#: (`architect_lore`).
LORE_STEP = "director_rooms_layout_lore"


_ON = ("1", "on", "true", "yes")
_OFF = ("0", "off", "false", "no")


def layout_grounds_enabled(cid=None) -> bool:
    """Whether the tier lays out a building's grounds with it in chat `cid`:
    the story's own switch when it states one, else the host's -- ON unless
    one of them says off (`LAYOUT_GROUNDS_SETTING`)."""
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
        return True
    return str(raw or "").strip().casefold() not in _OFF


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


def _recording(cid, call, turn_idx=None):
    """`call`, with each of its provider calls recorded for chat `cid` under
    its own step key, and the turn the tier works for where a job names one
    (`llm_capture.recording_outside_a_step`).

    THE TIER'S CALLS ARE RECORDED (2026-10-11). It runs in the job that builds
    the rooms in view, where `core.jobs` clears the step's exchange sink, and
    at the launch, before any turn -- so no capture held one of its calls: the
    owner's database, capture on with full bodies, held ten step keys and
    none of them the tier's. A call a step is already recording is left to
    that step."""
    def recorded(step, system, payload):
        from persist.llm_capture import recording_outside_a_step
        with recording_outside_a_step(cid, step, turn_idx=turn_idx):
            return call(step, system, payload)
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


def _take_off_what_is_not_laid(whole, building, solved, expected):
    """A PLACE AN EARLIER SOLVE OF THE BUILDING LAID, LEFT OUT OF THIS ONE,
    COMES OFF THE PLAN in the same write -- dropped for failing, or with the
    whole ground where the house is laid alone. Left on its old site, the
    re-solve laid the rest of the ground, or the house itself, over it (two
    reviews of 2026-10-14). It goes back to what the Room planned: no site,
    the Room's own estimate of its size where the solve's record kept one
    (else none), and no doorway pin the solve gave it -- on its own edges or,
    where this solve writes the neighbour, on the neighbour's edge to it.
    Writes into `solved` and `expected` (`write_planned_layout`'s)."""
    held_specs = whole.get("ground_specs") or {}
    gone = {g["id"] for g in whole.get("grounds") or ()} - \
        {g["id"] for g in building.get("grounds") or ()}
    for pid in sorted(gone):
        held = held_specs.get(pid)
        if not isinstance(held, dict):
            continue
        record = held.get("layout") if isinstance(held.get("layout"), dict) else {}
        site = held.get("site")
        if not (record.get("grounds") and isinstance(site, dict)
                and site.get("plan") == building["plan"]):
            continue
        stated = record.get("stated") if isinstance(record.get("stated"), dict) else None
        unpin = {"cell": None, "offset": None}
        solved[pid] = {"geometry": {"site": None, "level": None, "parts": None,
                                    "extent": dict(stated) if stated else None},
                       "anchors": {},
                       "edges": {str(e["to"]): dict(unpin) for e in held.get("adjacent") or ()
                                 if isinstance(e, dict) and e.get("to")
                                 and (e.get("cell") is not None or e.get("offset") is not None)},
                       "layout": None}
        expected[pid] = held
        plans = {**(whole.get("specs") or {}), **held_specs}
        for uid, solve in solved.items():
            if uid == pid or solve.get("room") is not None or pid in (solve.get("edges") or {}):
                continue
            edge = next((e for e in (plans.get(uid) or {}).get("adjacent") or ()
                         if isinstance(e, dict) and str(e.get("to") or "") == pid), None)
            if edge and (edge.get("cell") is not None or edge.get("offset") is not None):
                solve.setdefault("edges", {})[pid] = dict(unpin)


def lay_out(building, call, language_id):
    """One building, solved: `(spec, layout, inventory, refusals)`. Raises
    when an answer cannot be read; refusals are the bridge's. The spec
    carries the brief the two calls followed (`brief`), for the record.

    THE GROUNDS NEVER COST THE HOUSE ITS LAYOUT. Where the ground laid round
    a building leaves every seed refused and only the ground is at fault
    (`layout_bridge.ground_breaches`), the places that failed on the seed
    failing fewest are taken out (`places_to_drop`; a seed refused for the
    house is never read for them) and the building is solved again with the
    rest (`without_places`, up to `GROUND_DROP_ROUNDS` times: the owner's
    ruling of 2026-10-13, drop only the failing places); failing that, or
    where the house itself is refused, it is solved as the tier laid it
    before the grounds (`without_grounds`). No further call either way, and
    the spec says why each place was left where the plan had it
    (`grounds_dropped`, and `places_dropped`, which names the places that
    went with them as well)."""
    from llm.prompts import layout_prompt
    from world import layout_bridge
    building = _briefed(building, call, language_id)
    sort_answer = call(SORT_STEP, layout_prompt("sort", language_id),
                       layout_bridge.sort_payload(building))
    inventory = layout_bridge.hold_inventory(building, sort_answer)
    # a room the first call says stands beyond the walls gets its own block
    # before the second call reads the building
    building = layout_bridge.stand_beyond(building, inventory)
    relate_answer = call(RELATE_STEP, layout_prompt("relate", language_id),
                         layout_bridge.relate_payload(building, inventory))
    spec = layout_bridge.spec_from_answers(building, inventory, copy.deepcopy(relate_answer))
    if building.get("brief"):
        spec["brief"] = building["brief"]
    attempts = []
    layout, refused = layout_bridge.solve_for(building, spec, attempts=attempts)
    first = (spec, layout, refused)
    whole, dropped, why = building, [], []
    for _round in range(layout_bridge.GROUND_DROP_ROUNDS):
        if not refused or not building.get("grounds"):
            break
        failing, words = layout_bridge.places_to_drop(building, spec, attempts)
        grounds = {g["id"] for g in building.get("grounds") or ()}
        if not failing or set(failing) >= grounds:
            break                   # the house is refused on every seed, or nothing would be left
        why += words
        building = layout_bridge.without_places(building, failing)
        # the places a place taken out leaves joined to nothing go too, and
        # are named with it
        dropped += sorted(grounds - {g["id"] for g in building.get("grounds") or ()})
        if not building.get("grounds"):
            break
        spec = layout_bridge.spec_from_answers(building, inventory, copy.deepcopy(relate_answer))
        if whole.get("brief"):
            spec["brief"] = whole["brief"]
        attempts = []
        layout, refused = layout_bridge.solve_for(building, spec, attempts=attempts)
    if not refused and dropped:
        spec["grounds_dropped"] = list(why[:12])
        spec["places_dropped"] = dropped
        return spec, layout, inventory, refused
    building, (spec, layout, refused) = whole, first
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


def _story_lore(cid, frame_id=None):
    """Every entry of the chat's lorebooks as the story reads them
    (`chat_lorebook_ids`, the story's overlays merged by `lore_rows`), in the
    books' own order, each a plain dict; entries with no text left out."""
    from mind.memory import chat_lorebook_ids, lore_rows
    ids = chat_lorebook_ids(cid)
    if not ids:
        return []
    rows = (dict(row) for row in lore_rows(ids, chat_id=cid, frame_id=frame_id))
    return [row for row in rows if str(row.get("content") or "").strip()]


def _named_by_labels(rows, building):
    """`(own, named)`: the ids of the entries in `rows` whose authored labels
    -- keys, title, aliases and uid -- name the building itself (`own`), and
    of every entry whose labels name the building, one of its rooms or a
    place of the ground it stands in (`named`, which holds `own`), each in
    the books' order. Matched WHOLE, never by reading the entries' prose:
    a key that runs on past a room's name ("seal cavern divine side") names
    somewhere else, and a word the building's name merely contains
    ("shrine") names no building."""
    from language_runtime import compositor_value
    articles = {str(a).casefold() for a in compositor_value("articles") or ()}
    own_labels = {_label(building.get("structure"), articles),
                  _label(building.get("structure_name"), articles)}
    building_labels = set(own_labels)
    for uid in building.get("rooms") or ():
        building_labels.add(_label(uid, articles))
        building_labels.add(_label((building.get("names") or {}).get(uid), articles))
    # AND THE GROUND IT STANDS IN, which the tier lays out with it: the lore
    # of the garden, the path and what stands on them reached none of the
    # three calls, though they lay those places out too (2026-10-15)
    for place in building.get("grounds") or ():
        building_labels.add(_label(place.get("id"), articles))
        building_labels.add(_label(place.get("name"), articles))
    building_labels.discard("")
    own_labels.discard("")
    own, named = [], []
    for row in rows:
        labels = {_label(row.get("title"), articles), _label(row.get("entry_uid"), articles)}
        labels.update(_label(key, articles) for key in str(row.get("keys") or "").split(","))
        aliases = row.get("aliases")
        try:
            aliases = json.loads(aliases) if isinstance(aliases, str) else aliases
        except ValueError:
            aliases = []
        labels.update(_label(a, articles) for a in (aliases or ()) if a)
        labels.discard("")
        if labels & building_labels:
            named.append(row["id"])
            if labels & own_labels:
                own.append(row["id"])
    return own, named


def _described(rows, order):
    """The entries of `rows` with the ids in `order`, whole and in that
    order, up to `LAYOUT_DESCRIPTION_CHARS`: an entry that does not fit is
    passed over and a shorter one after it may still be read."""
    text_of = {row["id"]: str(row.get("content") or "").strip() for row in rows}
    out, total, seen = [], 0, set()
    for eid in order:
        text = text_of.get(eid)
        if not text or eid in seen or total + len(text) > LAYOUT_DESCRIPTION_CHARS:
            continue
        seen.add(eid)
        out.append(text)
        total += len(text) + 2
    return "\n\n".join(out)


def building_description(cid, building, frame_id=None):
    """WHAT THE STORY'S OWN LORE SAYS OF THIS BUILDING, by its labels alone:
    every entry whose authored labels name the building or one of its rooms
    by name or id (`_named_by_labels`), the entries naming the building
    itself first, then in the books' own order, whole, up to
    `LAYOUT_DESCRIPTION_CHARS`. "" when none. The floor of what the tier's
    calls read; the architect adds to it (`architect_lore`).

    The plan holds a room's one-line purpose; the lore holds what the room is
    -- its fixtures, its windows, what its floor is laid with -- and a solver
    sizes a room by what it holds. Without it the owner's shrine (chat 164)
    came back with every room a third of its planned size; the layout lab's
    liked shrine was laid out FROM such a description."""
    rows = _story_lore(cid, frame_id)
    own, named = _named_by_labels(rows, building)
    return _described(rows, own + named)


#: Entries of the story's lore the architect is shown to choose from
#: (`architect_lore`). Past it, the entries the labels name and then the
#: lore search's best (`search_lore`, on the building's names and purposes)
#: fill the index. The owner's shrine lorebook is 13 entries; named per
#: ask-before-limiting.
LAYOUT_LORE_INDEX_MAX = 80
#: Characters of each entry the architect is shown in the index, from its
#: start: enough to say what the entry is about (the shrine's top-floor
#: entry says "The top floor is smaller due to the roofline" in its first
#: line). The entries it chooses are read whole.
LAYOUT_LORE_OPENING_CHARS = 600


def _lore_index(cid, building, rows, named, frame_id=None):
    """The entries the architect chooses from: all of `rows` up to
    `LAYOUT_LORE_INDEX_MAX`; past it, the entries the labels name and then
    the lore search's best for the building, in the books' order. A search
    that fails leaves the named entries and then the books' first."""
    if len(rows) <= LAYOUT_LORE_INDEX_MAX:
        return list(rows)
    from core.logging_utils import logger
    wanted = list(named)
    try:
        from mind.memory import chat_lorebook_ids, search_lore
        specs = building.get("specs") or {}
        words = [str(building.get("structure_name") or building.get("structure") or "")]
        for uid in building.get("rooms") or ():
            words.append(str((building.get("names") or {}).get(uid) or uid))
            words.append(str((specs.get(uid) or {}).get("purpose") or ""))
        words += [str(place.get("name") or place.get("id") or "")
                  for place in building.get("grounds") or ()]
        found = search_lore(chat_lorebook_ids(cid), " ".join(w for w in words if w),
                            k=LAYOUT_LORE_INDEX_MAX, chat_id=cid, frame_id=frame_id)
        wanted += [hit["id"] for hit in found]
    except Exception as exc:  # noqa: BLE001 -- the index is still offered
        logger.info("layout tier: chat=%s the lore search failed (%s); the index "
                    "holds the named entries and then the books' first", cid,
                    " ".join(str(exc).split())[:200])
        wanted += [row["id"] for row in rows]
    keep = []
    for eid in wanted:
        if eid not in keep:
            keep.append(eid)
        if len(keep) >= max(LAYOUT_LORE_INDEX_MAX, len(named)):
            break
    keep = set(keep)
    return [row for row in rows if row["id"] in keep]


def lore_payload(building, index):
    """What the architect chooses the lore from: the building as the sort
    reads it (rooms, storeys, purposes, joins, stairs and ground -- never a
    description or a brief), and each entry of `index` by its id, title, keys
    and opening."""
    from world import layout_bridge
    view = layout_bridge.sort_payload(dict(building, description=None, brief=None))
    entries = []
    for row in index:
        text = str(row.get("content") or "").strip()
        opening = text[:LAYOUT_LORE_OPENING_CHARS]
        entries.append({
            "id": row["id"],
            "title": str(row.get("title") or ""),
            "keys": [k.strip() for k in str(row.get("keys") or "").split(",") if k.strip()],
            "opening": opening + ("…" if len(text) > len(opening) else ""),
        })
    return {"building": view["building"], "entries": entries}


def _chosen(answer, offered):
    """The ids the architect chose, in its order, each once, kept only where
    the index offered it: an id may come back as a number or its digits."""
    raw = answer.get("entries") if isinstance(answer, dict) else None
    out = []
    for item in raw if isinstance(raw, list) else ():
        try:
            eid = int(str(item).strip())
        except ValueError:
            continue
        if eid in offered and eid not in out:
            out.append(eid)
    return out


def architect_lore(cid, building, call, language_id, frame_id=None):
    """WHAT THE ARCHITECT READS: the story's lore of this building, chosen by
    the architect itself (`LORE_STEP`) from an index of the story's entries
    (`_lore_index`, `lore_payload`), over the entries the labels name
    (`building_description`), which it can add to and never take from. The
    entries naming the building itself come first, then every other entry
    the labels name, then the architect's own choices in its order, whole,
    up to `LAYOUT_DESCRIPTION_CHARS`. "" when the story has no lore.

    WHY THE ARCHITECT CHOOSES (chat 179, 2026-10-28). Which entries describe a
    building is a question about what the entries MEAN, and the labels only
    answer it where the lorebook's author and the plan happened to spell a
    room the same way. The owner's shrine lorebook holds seven entries about
    the house; its three calls read three. The top floor's entry is keyed
    "third floor, roost, tamamo quarters" and the plan named the room
    "Tamamo's Roost", so the roost was laid out with no window, its altar on
    the wrong wall and its nest in a corner; the overview that says the
    shrine faces south and has three floors is keyed "shrine of the golden
    fox", and the plan named the building "The House of the Shrine of the
    Golden Fox"; the cellar stair's entry is keyed "basement", a room of
    another structure. All seven come to 14,158 characters, inside the
    budget the three were read under.

    FAILS OPEN to the labels: the call raising, or choosing nothing the index
    offered, leaves what `building_description` reads."""
    from core.logging_utils import logger
    from llm.prompts import layout_prompt
    rows = _story_lore(cid, frame_id)
    if not rows:
        return ""
    own, named = _named_by_labels(rows, building)
    index = _lore_index(cid, building, rows, named, frame_id)
    chosen = []
    try:
        answer = call(LORE_STEP, layout_prompt("lore", language_id),
                      lore_payload(building, index))
        chosen = _chosen(answer, {row["id"] for row in index})
    except Exception as exc:  # noqa: BLE001 -- the labels' entries are still read
        logger.info("layout tier: chat=%s building=%s chose no lore: %s", cid,
                    building.get("key"), " ".join(str(exc).split())[:200])
    return _described(rows, own + named + chosen)


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
    call = _recording(cid, call or _default_call, turn_idx)
    try:
        specs = _plan_specs(cid)
        held_open = structure.provisional_room_ids(cid)
        wanted = set(room_ids)
        # ONLY THE BUILDINGS HOLDING A ROOM ASKED ABOUT ARE BUILT (`only`):
        # built whole and then filtered here, a street of expanded lots cost
        # 112 ms at 25 lots and 1,485 ms at 100 per rooms-in-view run (audit of
        # 2026-11-01, world_layout_bridge_structure E2). The grouping still
        # reads the whole plan, so a building is the same one either way.
        buildings = [b for b in layout_bridge.plan_buildings(
                         specs, scene, held_open=held_open,
                         grounds=layout_grounds_enabled(cid), only=wanted)
                     if b["refusal"] is None and wanted & set(b["rooms"])]
    except Exception as exc:
        logger.info("layout tier: chat=%s could not read the plan: %s", cid, str(exc)[:300])
        return scene, laid_out
    # THE SOLVES ASK THE JOB WHETHER IT WAS STOPPED (`layout_bridge.CANCELLED`):
    # the core counting its work and the lab's search between seeds raise
    # `ArrangeCancelled` when it says so. Nothing set it, so a rerolled job
    # kept solving to the core's budget and four lab seeds of pure-Python CPU
    # beside the beat that replaced it (audit of 2026-11-01, world_layout_core
    # E3). The job's alone, and off again when this run ends.
    stop_token = layout_bridge.CANCELLED.set(
        (lambda: jobs.is_cancelled(job)) if job is not None else None)
    try:
        return _lay_out_each(job, cid, scene, buildings, language_id, call,
                             turn_idx, laid_out)
    finally:
        layout_bridge.CANCELLED.reset(stop_token)


def _lay_out_each(job, cid, scene, buildings, language_id, call, turn_idx,
                  laid_out):
    """`lay_out_buildings`' walk over the buildings it may lay out this run,
    under the job's stop (`layout_bridge.CANCELLED`)."""
    from core import jobs
    from core.logging_utils import logger
    from world import layout_bridge, structure
    from world.layout_arrange import ArrangeCancelled

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
            described = architect_lore(cid, building, call, language_id)
        except Exception:
            described = ""
        if described:
            building = dict(building, description=described)
        try:
            spec, layout, inventory, refused = lay_out(building, call, language_id)
        except ArrangeCancelled as exc:
            # A STOPPED JOB IS NO FAILURE: nothing filed, nothing waits on a
            # retry, and no further building is begun this run.
            logger.info("layout tier: chat=%s building=%s not laid out: %s",
                        cid, key, " ".join(str(exc).split())[:200])
            break
        except Exception as exc:
            refused = [f"an answer could not be laid out: {' '.join(str(exc).split())[:300]}"]
            spec = layout = inventory = None
        # WHAT THE SOLVE SAID, ON THE RECORD: why a building was laid by the
        # lab's search instead of the arrangement core, or why the core gave
        # up first (`layout_bridge._fell_back`). It reached the log and no
        # run record, so a fallback was silent wherever the log is not read
        # (audit of 2026-11-01, world_layout_core F1).
        said = [str(w) for w in (getattr(layout, "warnings", None) or ())]
        if refused:
            failed = int((runs.get(key) or {}).get("failed") or 0) + 1 \
                if (runs.get(key) or {}).get("signature") == signature else 1
            entry = {"signature": signature, "turn": turn_idx, "failed": failed,
                     "failed_turn": turn_idx,
                     "reasons": refused[:LAYOUT_RUN_NOTES_MAX],
                     "seconds": round(time.time() - started, 2)}
            if said:
                entry["warnings"] = said[:LAYOUT_RUN_NOTES_MAX]
            if (spec or {}).get("brief"):
                entry["brief"] = spec["brief"]
            _file_run(cid, job, key, entry)
            runs[key] = entry
            logger.info("layout tier: chat=%s building=%s refused (%d in a row): %s",
                        cid, key, failed, "; ".join(refused[:6]))
            continue
        whole = building
        if spec.get("places_dropped"):
            # only the places that failed: the rest of the ground is written
            building = layout_bridge.without_places(building, spec["places_dropped"])
            logger.warning("layout tier: chat=%s building=%s laid out without %s: %s",
                           cid, key, ", ".join(spec["places_dropped"]),
                           "; ".join(spec["grounds_dropped"][:6]))
        elif spec.get("grounds_dropped"):
            building = layout_bridge.without_grounds(building)
            logger.info("layout tier: chat=%s building=%s laid out without its grounds: %s",
                        cid, key, "; ".join(spec["grounds_dropped"][:6]))
        solved, report = layout_bridge.planned_layout(building, spec, layout, turn=turn_idx,
                                                      inventory=inventory)
        expected = {**building["specs"], **(building.get("ground_specs") or {})}
        _take_off_what_is_not_laid(whole, building, solved, expected)
        written = structure.write_planned_layout(cid, solved, expected=expected, job=job)
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
        if spec.get("places_dropped"):
            entry["places_dropped"] = list(spec["places_dropped"])
        if spec.get("brief"):
            entry["brief"] = spec["brief"]
        said = [str(w) for w in (report.get("warnings") or said)]
        if said:
            entry["warnings"] = said[:LAYOUT_RUN_NOTES_MAX]
        _file_run(cid, job, key, entry)
        runs[key] = entry
        logger.info("layout tier: chat=%s building=%s laid out on %s in %.1fs; "
                    "%d fixtures moved off their wall and pinned where the solver "
                    "stood them, %d unplaced and left to the designer; %d the plan "
                    "listed restored, %d ways marked",
                    cid, key, building["plan"], entry["seconds"], entry["moved"],
                    entry["unplaced"], entry["restored"], entry["marks"])
        # the building's rooms and the ground the solve laid round it
        rooms_laid = set(building["rooms"]) | set(solved)
        structure.apply_planned_layout(scene, _plan_specs(cid), rooms_laid)
        laid_out.update(rooms_laid)
    return scene, laid_out
