"""Planned location structure composed with the small live scene.

Planned rooms live in ``room_registry.payload`` and remain prose-free.  The
live scene receives only adjacent stubs; entering one lets the ordinary mapping
stage write description and contents without hauling a whole town through
every story prompt.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import threading

from world.charter_model import integer as _integer
from world.frontage import split_marks
from world.regions import normalize_region_id
from world.place_names import (SLOT, deal_place_name, is_pattern,
                               name_patterns, resident_name_words,
                               standing_fillers)
from world.spatial import (derived_room_name, normalize_bearing,
                           normalize_room_id, room_name_words,
                           room_words_answer)


STRUCTURES_KEY = "structures"
STRUCTURE_VERSION = 1


def normalize_structure(stored):
    stored = stored if isinstance(stored, dict) else {}
    grammar = []
    for raw in stored.get("grammar") or ():
        if not isinstance(raw, dict):
            continue
        grammar.append({
            "kind": str(raw.get("kind") or "place"),
            "names": [str(x) for x in raw.get("names") or () if str(x)],
            "purposes": [str(x) for x in raw.get("purposes") or () if str(x)],
        })
    return {
        "version": STRUCTURE_VERSION,
        "key": str(stored.get("key") or "structure"),
        "name": str(stored.get("name") or stored.get("key") or "Location"),
        "charters": sorted({str(x) for x in stored.get("charters") or ()
                            if str(x)}),
        "max_planned": max(1, min(
            1000, _integer(stored.get("max_planned"), 200))),
        "grammar": grammar,
        "revision": max(0, _integer(stored.get("revision"))),
    }


def normalize_structures(stored):
    stored = stored if isinstance(stored, dict) else {}
    items = stored.get("items") if isinstance(stored.get("items"), dict) \
        else stored
    return {"version": STRUCTURE_VERSION, "items": {
        str(key): normalize_structure(dict(value or {}, key=key))
        for key, value in items.items() if isinstance(value, dict)
        and key != "version"}}


#: The MEASURABLE half of a planned room, in the scene's own vocabulary.
#: `story.plot_packages._plan_geometry` normalizes and clamps these three
#: against the same closed sets a LIVED room is read through
#: (`spatial.normalize_extent` / `spatial.SHAPES` / `weather.EXPOSURES`), so
#: what the registry holds is already a scene value and is carried through as
#: is. Absent stays absent: a room that measured nothing must read exactly as
#: it did before a plan could measure anything, and a `None` written into the
#: field is not the same as no field.
#: What a planned room carries onto its live stub. `sound` is here rather
#: than in a table of its own because it travels the same way and for the
#: same reason: it is a property of the PLACE that the plan knows and the
#: scene does not, and a stub that arrives without it is a room the story
#: laid out and then silenced.
#: `site` (2026-10-08) is where a room stands on its building's plan and how
#: high its floor is (`world/site_plan`). No model writes it: `plan_rooms`
#: never reads one (`story.plot_packages._plan_geometry`), and the only
#: writer is the layout tier, which places a planned building by code
#: (`write_planned_layout`). Carried onto the stub so a sited room is
#: "described, never re-measured" from the beat it is first seen
#: (`spatial_merge`).
GEOMETRY_FIELDS = ("extent", "shape", "exposure", "sound",
                   "level", "over", "floor", "surface", "quiet", "site")

#: The fields of an anchor and of an edge that say WHERE it is, which a
#: solved plan lays onto the stub it already made (`apply_planned_layout`).
#: Positions only: what a thing is (`desc`) and what a doorway is (`barrier`)
#: stay whatever the stub holds -- save a record the plan wrote for SEVERAL
#: alike that a solve split into one anchor each, whose group words the stub
#: was minted with (`planned.layout.split`, `_lay_stub_on_its_plan`).
LAYOUT_ANCHOR_FIELDS = ("dir", "cell", "extent", "footprint", "height",
                        "opacity", "offset")
LAYOUT_EDGE_FIELDS = ("dir", "offset", "cell")
#: The plans the layout tier lays a building out on are named
#: `layout:<entrance room>` (`world.layout_bridge`). The name says which plan
#: a room stands on, never that a solve put it there: the engine's derivation
#: places every room it can beside one already on a plan ON THAT PLAN
#: (`site_plan.derive_site_plans` reuses it), so the street a laid-out
#: building opens onto, and a planned yard behind it, stand on a `layout:`
#: plan without any solve having placed them.
LAYOUT_PLAN_PREFIX = "layout:"
#: THE RECORD A SOLVE LEAVES ON THE STUB IT LAYS (`_lay_stub_on_its_plan`):
#: `{"plan": <the plan it was laid on>, "edges": [<each room the solve
#: placed this stub's doorway or stair to>]}`. Only that code writes it --
#: derivation places a room by its `site` alone, and a model cannot write a
#: key `RoomDef` does not declare -- so a stub carrying it stands where a solve
#: put it. The rule that takes a re-planned building's solve back off its
#: stubs reads this record and nothing else, and gives back only what it
#: lists (review of 2026-10-08, R2-1: keyed on the plan's name, the rule took
#: the site a planned yard was DERIVED onto beside a solved kitchen, an extent
#: a beat wrote and the yard's doorway offset off it, every commit).
LAID_OUT_KEY = "laid_out"

#: WHAT A PLAN SEEDS AND THE WORLD MAY CHANGE (2026-10-08). `far_look` --
#: how the place reads from far off (`world.landscape`) -- travels with the
#: plan the way `GEOMETRY_FIELDS` do: into the registry, onto the skeleton
#: and onto the stub, because a stub that arrived without it would read as
#: its ground alone ("open ground", "a building") to every far eye. It is
#: NOT held by the plan while the stub is prose-free, as a measurement is: a
#: beat that burns the place and a host who edits it both change how it
#: reads from afar, and the plan re-imposing its word every commit undid
#: both on exactly the places far looks are for (review 2026-10-08, F1).
#: The plan's word reaches the stub when the plan SAYS something new
#: (`_lay_planned_looks`).
PLAN_SEEDED_FIELDS = ("far_look",)

#: The scene's record of the far look each prose-free planned stub last took
#: from its plan: ``{room uid: look}``. Read and written by
#: `materialize_planned_fringe` alone, and absent from a scene whose plans
#: carry no far look. Frame-scoped because the scene is, so a look a beat
#: changes in one frame never reaches another frame's stub.
LAID_LOOKS_KEY = "far_looks_laid"


def planned_anchors(planned):
    """``{"anchors": {id: {...}}}`` for a planned room that names its
    fixtures, and ``{}`` for one that does not.

    A ROOM'S DESCRIPTION PROMISES THINGS; THIS IS WHERE IT KEEPS THEM. A
    room record carries an optional `anchors` map -- the named features a
    body can stand at, take cover behind, put something on or lay a hand
    against -- and it is what `spatial_contacts` resolves a contact target
    against, what a post's `anchor` names, and what `spatial_fov`,
    `comfort`, `place_purpose` and the light field all read. Until now the
    only anchors any story ever had were ones the Director authored
    mid-beat, because nothing asked a PLAN for them and this normalizer's
    allowlist dropped them if a plan sent them anyway.

    Measured (two_lives v7, 2026-09-19, turns 5/7/9): `mill_race` was
    planned as "The sluice channel and wet timber shroud housing the great
    undershot waterwheel" and planted as `{name, desc, adjacent, region}`.
    Emory Vane pressed a hand to the apron timber and reached for the wheel
    shroud, and the contact hand refused all of it -- "Targets 'shroud' and
    'apron timber' do not exist as established world keys or fixtures/
    anchors in the mill_race payload" -- correctly, because they did not.
    The room's furniture was stored twice, as English in `desc` and as
    structure nowhere, and a body could not touch the thing the room said
    it was made of.

    Same shape and same reason as `planned_geometry` beside it, which exists
    because this allowlist had already dropped the plan's MEASUREMENTS once
    (F47). An id whose value is not an object is dropped rather than
    guessed at: an anchor is a record, and a bare string is a description
    with nowhere to put it.
    """
    planned = planned if isinstance(planned, dict) else {}
    raw = planned.get("anchors")
    if not isinstance(raw, dict):
        return {}
    anchors = {}
    for aid, anchor in raw.items():
        key = str(aid or "").strip()
        if not key or not isinstance(anchor, dict):
            continue
        anchors[key] = copy.deepcopy(anchor)
    return {"anchors": anchors} if anchors else {}


def planned_geometry(planned):
    """The geometry a planned room carries, omitting what it does not. A
    `site` is read through `site_plan.normalize_site`, so one that is not a
    place on a plan is no site at all rather than a guess at one."""
    from world.site_plan import normalize_site

    planned = planned if isinstance(planned, dict) else {}
    out = {key: copy.deepcopy(planned[key]) for key in GEOMETRY_FIELDS
           if planned.get(key) and key != "site"}
    site = normalize_site(planned.get("site"))
    if site:
        out["site"] = site
    return out


def _placed_pin(anchor):
    """Whether an anchor carries a PLACER's pin: a `cell` with the whole
    rectangle beside it (`spatial_fov.anchor_extent`). Only code that placed
    a fixture writes `extent` on an anchor -- the layout tier, the layout
    converter -- so a `cell` alone (the World Browser's pin) is never read
    as one."""
    return isinstance(anchor, dict) and "cell" in anchor \
        and isinstance(anchor.get("extent"), dict)


def _plan_edges(spec):
    return {str(e.get("to")): e for e in (spec or {}).get("adjacent") or ()
            if isinstance(e, dict) and e.get("to")}


def apply_planned_layout(scene, specs, room_ids=None):
    """Lay each prose-free stub of a SOLVED plan on its plan, in place, and
    take the solve off a stub whose plan was re-planned since. Returns the
    room ids it touched.

    A plan is solved when it carries a `site` -- only the layout tier writes
    one -- so every plan the Room or the charter wrote is untouched, byte for
    byte. WHILE A ROOM IS THE PLAN'S PROSE-FREE STUB THE PLAN OWNS ITS
    MEASUREMENTS (the fringe's own rule, `materialize_planned_fringe`), and a
    solved plan's measurements are its rectangle, its storey, its site and
    where each of its fixtures and doorways stands. So the stub takes the
    plan's geometry (`planned_geometry`) and, on every anchor and doorway the
    plan places, the plan's position fields (`LAYOUT_ANCHOR_FIELDS`,
    `LAYOUT_EDGE_FIELDS`) -- the anchors the stub was minted with before the
    solve included, which is every fixture the Room named (chat 165's
    taproom planned `hearth`, `long_table`, `barrel_rack` and `stair_foot`,
    and its stub carried all four without a position). A fixture the solve
    left unpinned loses a placer's pin a stub held from an earlier solve
    (`_placed_pin`); a host's own `cell` is never read as one.

    A RE-PLAN DROPS THE SOLVE. `plant_structure` replaces a planned row
    whole, so a building the Room re-plans after it was laid out has rows
    with no `site` while its stubs still stand where the solve put them. A
    stub the solve laid says so (`LAID_OUT_KEY`, written here and nowhere
    else), and gives back what that record lists: its `site`, any rectangle
    or storey the plan no longer states, every placer's pin on its fixtures,
    and the `cell` and `offset` on each doorway and stair the solve placed --
    taking the new plan's measurements where it states them -- so no stub
    keeps a solve its plan no longer holds (review of 2026-10-08, F6: the
    stub kept its old site under the new 12 by 3 box). What the solve added
    that the new plan does not name stays an unpinned fixture of the stub.

    ONLY WHAT A SOLVE LAID IS TAKEN BACK. The engine's derivation places a
    planned neighbour beside a solved building on the building's own plan --
    the yard behind its kitchen, the street before its door -- and that site,
    with whatever a beat has measured on it since, is the neighbour's: it was
    never solved, so it carries no record and nothing here touches it
    (review of 2026-10-08, R2-1: read off the plan's name, the yard's derived
    site, a 3 by 3 a beat wrote and its doorway's offset came off every
    commit). A record left on a stub that no longer stands on the plan it
    names describes nothing, and is dropped.

    A room with a description is the story's and is never touched
    (`is_planned_stub`): it was laid on its plan before it was described,
    because every reader of a beat and the commit's own merge read the scene
    through `apply_solved_plans`.

    `specs` is `{uid: (name, planned)}` (`_planned_specs`); `room_ids`
    limits the pass to those rooms."""
    from world.site_plan import normalize_site
    rooms = (scene or {}).get("rooms") or {}
    touched = []
    for uid, (_name, spec) in (specs or {}).items():
        if room_ids is not None and uid not in room_ids:
            continue
        room = rooms.get(uid)
        if not isinstance(room, dict) or not isinstance(spec, dict):
            continue
        if str(room.get("desc") or room.get("description") or "").strip():
            continue
        if normalize_site(spec.get("site")):
            _lay_stub_on_its_plan(room, spec)
            touched.append(uid)
            continue
        if LAID_OUT_KEY not in room:
            continue
        record = room[LAID_OUT_KEY] if isinstance(room[LAID_OUT_KEY], dict) else {}
        site = normalize_site(room.get("site"))
        if site and site["plan"] == record.get("plan"):
            _take_the_solve_off(room, spec, record)
        else:
            room.pop(LAID_OUT_KEY, None)
        touched.append(uid)
    return touched


def _lay_stub_on_its_plan(room, spec):
    """One prose-free stub laid on its solved plan (`apply_planned_layout`),
    and the record of what the solve laid on it (`LAID_OUT_KEY`)."""
    room.update(planned_geometry(spec))
    held = room.get("anchors") if isinstance(room.get("anchors"), dict) else {}
    split = _split_records(spec)
    for aid, anchor in (planned_anchors(spec).get("anchors") or {}).items():
        live = held.get(aid)
        if not isinstance(live, dict):
            held[aid] = copy.deepcopy(anchor)
            continue
        if _placed_pin(live) and not _placed_pin(anchor):
            live.pop("cell", None)
            live.pop("extent", None)
        for key in LAYOUT_ANCHOR_FIELDS:
            if key in anchor:
                live[key] = copy.deepcopy(anchor[key])
        if aid in split and str(live.get("desc") or "") == split[aid] \
                and str(anchor.get("desc") or "").strip():
            # The plan's words for SEVERAL alike, which the solve split into
            # one record each: the stub was minted with the group's words
            # on the record that is now one of them, and takes that one's.
            live["desc"] = anchor["desc"]
    if held:
        room["anchors"] = held
    planned = _plan_edges(spec)
    placed = []
    for edge in room.get("adjacent") or ():
        if not isinstance(edge, dict):
            continue
        plan_edge = planned.get(str(edge.get("to") or ""))
        if not plan_edge:
            continue
        for key in LAYOUT_EDGE_FIELDS:
            if key in plan_edge:
                edge[key] = copy.deepcopy(plan_edge[key])
        if "offset" in plan_edge or "cell" in plan_edge:
            placed.append(str(edge["to"]))
    room[LAID_OUT_KEY] = {"plan": room["site"]["plan"], "edges": sorted(set(placed))}


def _split_records(spec):
    """`{anchor id: the plan's words for the group}` for every record of the
    plan a solve split into several alike (`planned.layout.split`,
    `layout_bridge.planned_layout`)."""
    record = spec.get("layout") if isinstance(spec.get("layout"), dict) else {}
    return {str(s.get("anchor")): str(s.get("desc") or "")
            for s in record.get("split") or () if isinstance(s, dict) and s.get("anchor")}


def _take_the_solve_off(room, spec, record):
    """One prose-free stub whose plan was re-planned after the layout tier
    laid it out, given back to the plan it now has (`apply_planned_layout`):
    what `record` (`LAID_OUT_KEY`) says the solve laid, and nothing else."""
    room.pop(LAID_OUT_KEY, None)
    room.pop("site", None)
    stated = planned_geometry(spec)
    for key in ("extent", "shape", "level"):
        if key in stated:
            room[key] = stated[key]
        else:
            room.pop(key, None)
    plan_anchors = planned_anchors(spec).get("anchors") or {}
    for aid, live in ((room.get("anchors") or {}) if isinstance(room.get("anchors"), dict)
                      else {}).items():
        if not _placed_pin(live):
            continue
        live.pop("cell", None)
        live.pop("extent", None)
        for key in LAYOUT_ANCHOR_FIELDS:
            if key in (plan_anchors.get(aid) or {}):
                live[key] = copy.deepcopy(plan_anchors[aid][key])
    placed = {str(to) for to in record.get("edges") or ()}
    planned = _plan_edges(spec)
    for edge in room.get("adjacent") or ():
        if not isinstance(edge, dict) or str(edge.get("to") or "") not in placed:
            continue
        edge.pop("cell", None)
        edge.pop("offset", None)
        plan_edge = planned.get(str(edge.get("to") or "")) or {}
        for key in LAYOUT_EDGE_FIELDS:
            if key in plan_edge:
                edge[key] = copy.deepcopy(plan_edge[key])


def apply_solved_plans(cid, scene):
    """Lay every prose-free stub in `scene` on its plan's solve, in place
    (`apply_planned_layout` over the whole registry); returns the room ids
    it touched. Inert -- nothing read beyond the registry's shared parse --
    for every story whose plans the layout tier never solved.

    THE SCENE A BEAT READS AND THE SCENE ITS COMMIT MERGES ONTO ARE THE
    PLAN'S. The tier writes the plan between commits, so the stored scene
    holds a stub the commit minted before the solve until the next commit's
    fringe pass lays it down -- and the job that solved the building designs
    its rooms on the solved geometry meanwhile. Read off the stored scene,
    the next beat installed that design onto the unsited stub and committed
    it off the plan, its fixtures unpinned, and the fringe never touched it
    again: half a building on a plan (review of 2026-10-08, F1). So
    `story.scene.get_scene` -- every reader of a beat, the install among
    them -- the commit's merge base (`compose_beat_scene`) and the design job
    (`director_rooms._predevelop_run`) all read the scene through this, the
    way the opening's readers and its merge both read the planted skeleton
    (`story.scene.seed_scene_from_plan`). No model writes a `site`, and
    nothing here makes one."""
    return apply_planned_layout(scene, _planned_specs(cid))


def write_planned_layout(cid, rooms, *, expected, job=None):
    """Write a solved building into the plan rows of its rooms, and say
    whether it was written. The layout tier's ONE write
    (`agents/director_layout.py`), and code's alone: no model reaches it.

    `rooms` is `{uid: {"geometry": {extent, shape, level, site}, "anchors":
    {anchor id: fields}, "edges": {neighbour uid: fields}, "layout": the
    solve's record}}` (`world.layout_bridge.planned_layout`). Each row's
    `planned` payload takes the geometry, each anchor's fields merged onto
    the plan's record of it (its `desc` kept), each edge's position fields
    onto the plan's edge to that neighbour, and the record under `layout`.

    ALL OR NOTHING, AND ONLY ONTO THE PLAN IT SOLVED. `expected` is each
    row's `planned` payload as the solve read it; a row the Room re-planned
    since, or retired, refuses the whole building, because half a building
    on a plan is a contradiction the next reader cannot see. Nothing is
    written once `job` is cancelled (`core.jobs.is_cancelled`, asked inside
    the transaction, as `director_rooms._file_prepared` does): a restore
    stops the job before it rolls the registry back.

    The plan tier writes the plan; the scene is the commit's
    (`materialize_planned_fringe` -> `apply_planned_layout`), so this is
    never a second scene writer."""
    from core import jobs
    from core.db import q, qi, transaction

    def canon(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)

    with transaction():
        if jobs.is_cancelled(job):
            return False
        current = {}
        for uid in rooms:
            row = q("SELECT payload FROM room_registry WHERE chat_id=? AND "
                    "room_uid=? AND retired_turn_id IS NULL", (cid, uid))
            if not row:
                return False
            payload = _payload(row[0])
            planned = payload.get("planned") if isinstance(payload, dict) else None
            if not isinstance(planned, dict) or canon(planned) != canon(
                    (expected or {}).get(uid)):
                return False
            current[uid] = payload
        for uid, solved in rooms.items():
            payload = current[uid]
            planned = payload["planned"]
            planned.update(copy.deepcopy(solved.get("geometry") or {}))
            anchors = planned.get("anchors") if isinstance(planned.get("anchors"), dict) else {}
            split = set(_split_records(solved))
            for aid, fields in (solved.get("anchors") or {}).items():
                record = dict(anchors.get(aid) or {}) if isinstance(anchors.get(aid), dict) else {}
                fields = copy.deepcopy(fields)
                if str(record.get("desc") or "").strip() and aid not in split:
                    # what a thing IS stays the plan's word for it; the solve
                    # says only where it stands -- except on a record the
                    # plan wrote for SEVERAL alike, now the first of them:
                    # the group's words go to the solve's record
                    # (`planned.layout.split`), and the copy takes its own
                    fields.pop("desc", None)
                record.update(fields)
                anchors[aid] = record
            if anchors:
                planned["anchors"] = anchors
            moves = solved.get("edges") or {}
            for edge in planned.get("adjacent") or ():
                if isinstance(edge, dict) and str(edge.get("to") or "") in moves:
                    edge.update(copy.deepcopy(moves[str(edge["to"])]))
            if solved.get("layout"):
                planned["layout"] = copy.deepcopy(solved["layout"])
            qi("UPDATE room_registry SET payload=? WHERE chat_id=? AND room_uid=? "
               "AND retired_turn_id IS NULL",
               (json.dumps(payload, ensure_ascii=False), cid, uid))
    return True


def planned_seed(planned):
    """What a planned room SEEDS onto its record (`PLAN_SEEDED_FIELDS`),
    omitting what it does not say -- a far look in the one spelling every
    writer and reader keeps (`landscape.normalize_far_look`), whoever
    planted it."""
    from world.landscape import normalize_far_look
    planned = planned if isinstance(planned, dict) else {}
    out = {}
    for key in PLAN_SEEDED_FIELDS:
        value = (normalize_far_look(planned.get(key)) if key == "far_look"
                 else copy.deepcopy(planned.get(key)))
        if value:
            out[key] = value
    return out


def _lay_planned_looks(scene, stubs, specs):
    """Lay each prose-free planned stub's far look as its plan last SAID it.

    `stubs` is the room ids of the prose-free planned stubs this pass keeps
    and `specs` {uid: (name, spec)}. The scene keeps what each stub last
    took (`LAID_LOOKS_KEY`), so the rule reads only the plan and that record:

    * the plan says what the stub last took: nothing to do, and whatever the
      stub reads now -- a beat's rewrite, a host's edit or clear -- stands;
    * the plan says something new (a re-plan, a claim on a frontier space):
      its word is laid;
    * the stub has taken nothing yet in this frame: the plan's word is laid
      only where the stub has no look, so a look the opening wrote onto it
      stands;
    * the plan says nothing: nothing is taken away, as no measurement is,
      and a plan that once spoke is remembered as having fallen silent, so
      its next word is new.

    The record holds only stubs that still are ones; it leaves a scene
    whose plans carry no far look exactly as it was."""
    rooms = scene.get("rooms") or {}
    laid = scene.get(LAID_LOOKS_KEY)
    laid = dict(laid) if isinstance(laid, dict) else {}
    kept = {}
    for uid in stubs:
        room = rooms.get(uid)
        if not isinstance(room, dict):
            continue
        said = str((specs.get(uid) or (None, {}))[1].get("far_look") or "")
        if uid in laid:
            if said and laid[uid] != said:
                room["far_look"] = said
        elif said and not room.get("far_look"):
            room["far_look"] = said
        if said or uid in laid:
            kept[uid] = said
    if kept:
        scene[LAID_LOOKS_KEY] = kept
    else:
        scene.pop(LAID_LOOKS_KEY, None)


def _payload(row):
    try:
        return json.loads(row["payload"] or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


# ---- one parse of the registry, shared by every planned_* reader ----------
# THE PLAN IS ONE OBJECT AND THE TURN READS IT ONCE. Every `planned_*`
# question below used to re-run its own
# `SELECT ... WHERE chat_id=? AND retired_turn_id IS NULL` and re-parse every
# row's payload JSON. Measured on chat 114's 51-room plan (review item C16,
# 2026-09-07, `tools/bench/room_registry_scan.py`): a normal turn asks 19
# times -- three Director payload builders, two movement readers, two room-
# slice readers, four region readers, the frontier reader and six commit
# domains -- for 22.3 ms of pure re-derivation with nothing changed in
# between.
#
# Thread-local, and one chat's snapshot at a time. Thread-local because the
# validity token is a property of THIS thread's connection (`db_read_token`),
# and the Director's specialists run in parallel: a shared entry would make
# five threads with five different `total_changes` counters thrash one slot.
# One chat because a turn reads one story; a reader for another chat replaces
# the entry rather than growing the cache, which costs that reader a parse and
# drops no data.
_REGISTRY_CACHE = threading.local()


def _read_registry_rows(cid):
    """Every live registry row for one chat, parsed. ``{uid: entry}``, in the
    order the table returns them -- the order every reader below used to see.

    Fields are carried as STORED, not coerced, because the readers disagree
    about what an absent one means: `skeleton_rooms` falls back to the uid for
    an empty name and `_planned_spellings` folds it to "" and drops it, so the
    entry keeps the raw string and each reader states its own default.
    """
    from core.db import q

    out = {}
    for row in q(
            "SELECT room_uid,owning_book_id,parent_entity,name,aliases,payload"
            " FROM room_registry WHERE chat_id=? AND retired_turn_id IS NULL",
            (cid,)):
        payload = _payload(row)
        planned = payload.get("planned") if isinstance(payload, dict) else None
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            aliases = []
        uid = str(row["room_uid"])
        out[uid] = {
            "room_uid": uid,
            "owning_book_id": row["owning_book_id"],
            "parent_entity": row["parent_entity"],
            "name": str(row["name"] or ""),
            "aliases": aliases,
            "payload": payload,
            "planned": planned if isinstance(planned, dict) else None,
        }
    return out


def registry_rows(cid):
    """Every live `room_registry` row for one chat, parsed once: SHARED and
    READ-ONLY.

    Every reader in this module gets the same entries until a write lands
    (`core.db.db_read_token` decides that, and over-invalidates rather than
    under-). MUTATING WHAT THIS RETURNS IS A BUG -- a spec's `adjacent` list
    handed out here is the same list the next reader sees, exactly as the
    charter registry's shared parse works (`charter_runtime.cached_registry`).
    A caller that intends to mutate uses `registry_rows_for_update`.
    """
    from core.db import db_read_token

    token = db_read_token()
    entry = getattr(_REGISTRY_CACHE, "entry", None)
    # The chat id is keyed as GIVEN, not coerced: the readers hand down
    # whatever `ctx.chat["id"]` held, and two spellings of one id costing a
    # re-parse is nothing beside a coercion that can raise where the old
    # query simply answered nothing.
    if entry is not None and entry[0] == cid and entry[1] == token:
        return entry[2]
    rows = _read_registry_rows(cid)
    _REGISTRY_CACHE.entry = (cid, token, rows)
    return rows


def registry_rows_for_update(cid):
    """The same rows, PRIVATE: a fresh parse for the one caller that mutates
    what it reads (`prepare_frontier_expansion` appends to a planned spec's
    `adjacent` and rewrites its `frontier`). Never cached, and never poisons
    the shared parse."""
    return _read_registry_rows(cid)


def retired_room_spellings(cid, *, folded=True):
    """Every spelling a RETIRED registry row still answers to, normalized
    (`folded=False`: as written, for a reader that compares a script
    `normalize_room_id` drops -- `world/place_names.spelling_key`).

    A RETIREMENT IS SPENT IDENTITY (review 2026-09-07, Section I residual on
    B8/A55). The registry is the authority for a room being over, and a ruin
    stays in the scene on purpose -- a ruin is still a place. But every
    `planned_*` reader filters `retired_turn_id IS NULL`, so the ruin is
    invisible to the frontier mint, which reserves only what it can see: an
    axis leaving a live room toward the dead one drew a stub under the ruin's
    own uid, and the upsert that wrote it carried `retired_turn_id=NULL`, so
    the building came back live as a nameless planned stub.

    Uids, names and aliases alike, folded with `normalize_room_id` because
    that is what `mint_frontier` checks its candidates against. Not cached:
    the one caller is the reader that already pays for its own parse.
    """
    from core.db import q

    out = set()
    for row in q(
            "SELECT room_uid,name,aliases FROM room_registry WHERE chat_id=? "
            "AND retired_turn_id IS NOT NULL", (cid,)):
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            aliases = []
        for spelling in (row["room_uid"], row["name"], *aliases):
            slug = normalize_room_id(str(spelling or "")) if folded \
                else " ".join(str(spelling or "").split())
            if slug:
                out.add(slug)
    return out


def skeleton_rooms(cid, structure_key, frame_id=None):
    """Read one planned skeleton in ordinary spatial scene shape."""
    rooms = {}
    for uid, entry in registry_rows(cid).items():
        planned = entry["planned"]
        if not isinstance(planned, dict) \
                or str(planned.get("structure") or "") != str(structure_key):
            continue
        rooms[uid] = {
            "name": str(entry["name"] or uid),
            "adjacent": [dict(edge) for edge in planned.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
            "planned": True,
            "purpose": str(planned.get("purpose") or ""),
            "access": str(planned.get("access") or ""),
            # A structure IS a region (world/regions.py): a planned room
            # enters the scene already knowing which part of the map it is.
            "region": normalize_region_id(structure_key),
            # And what the plan MEASURED, beside what the room is FOR.
            **planned_geometry(planned),
            # And how it reads from far off (`PLAN_SEEDED_FIELDS`).
            **planned_seed(planned),
            # And what it is MADE OF: the fixtures a body can reach.
            **planned_anchors(planned),
        }
    return {"rooms": rooms}


def crosses_an_interior(rooms, a, b):
    """Does the doorway between rooms `a` and `b` cross an entity's interior
    boundary -- one inside an entity (`parent_entity`), the other not, or in
    another one?

    THE PLAN NEVER SUPPLIES SUCH A DOORWAY. An interior's way out is where its
    entity stands, written every merge from its position and transit
    (`spatial_transit.apply_transit_dock_edges`); a planned edge across that
    boundary pins it to wherever the entity stood when the plan was drawn.
    Chat 160 turn 4541 (2026-10-01): the freight car docked four floors down,
    and three planned passes -- the fringe, the exit restore, the composed
    topology -- each put its door to the upper hallway back."""
    rooms = rooms or {}
    def parent(rid):
        room = rooms.get(str(rid or ""))
        return (room.get("parent_entity") or None) if isinstance(room, dict) else None
    return parent(a) != parent(b)


def composed_scene(skeleton, live_scene):
    """Merge planned travel topology under live authored room definitions."""
    live = copy.deepcopy(live_scene or {})
    planned_rooms = copy.deepcopy((skeleton or {}).get("rooms") or {})
    live_rooms = live.get("rooms") or {}
    merged = planned_rooms
    for uid, room in live_rooms.items():
        if not isinstance(room, dict):
            merged[str(uid)] = room
            continue
        base = dict(merged.get(str(uid)) or {})
        base.update(copy.deepcopy(room))
        # Live edges win per endpoint; planned edges retain destinations the
        # currently materialized scene has not had reason to spell yet.
        edges = {}
        for edge in (planned_rooms.get(str(uid)) or {}).get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("to") \
                    and not crosses_an_interior({**planned_rooms, **live_rooms}, uid, edge["to"]):
                edges[str(edge["to"])] = dict(edge)
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("to"):
                edges[str(edge["to"])] = dict(edge)
        if edges:
            base["adjacent"] = list(edges.values())
        merged[str(uid)] = base
    live["rooms"] = merged
    return live


def _axis_words(text):
    return set(re.findall(r"[^\W\d_]+", str(text or "").casefold()))


def _proper(name):
    """A room name is a proper noun. A grammar name or an axis label a
    planner wrote in lower case ("upland road") takes a capital at the front
    of each word; a name with a capital anywhere keeps its author's spelling
    ("Saint Orrin's Shrine", "McKay's Yard")."""
    text = " ".join(str(name or "").split())
    if not text or any(ch.isupper() for ch in text):
        return text
    return " ".join(part[:1].upper() + part[1:] for part in text.split(" "))


#: The widest a place's NAME runs before it stops being a name and starts
#: being a description of what is that way. Measured 2026-09-05 over every
#: frontier two live plans wrote: the nine phrases that minted junk rooms ran
#: 5 to 9 words ("the river flowing west upstream", "bare grassy slopes
#: falling away to the east and west"), and every label that named a place ran
#: 1 to 4 ("north", "far road", "west ridge path", "the fish wharves lane").
#: Four is where the two populations part.
FRONTIER_NAME_WORDS = 4


def frontier_refusal(axis, *, allow_bearing=False):
    """Why this frontier label cannot be minted as a room, or ``None``.

    A FRONTIER NAMES A PLACE. It is the answer to "what lies that way", and
    the way out is drawn to it by name -- so what cannot be a place's name
    cannot be minted as one, and is reported instead of becoming a room whose
    id is the sentence somebody wrote.

    Two things are not a name, and both were measured:

    * a bare BEARING (F3, chat 116): `frontier: ["west"]` minted a room called
      West. A direction is where the way out points, not what is at the end of
      it, and it belongs on `adjacent.bearing`.
    * a DESCRIPTION (F63 / PD4, the market and the road runs, six junk rooms
      of fifteen in one story): `frontier: ["the village street of Ambry
      beyond the gate"]` minted
      `the_village_street_of_ambry_beyond_the_gate` -- no extent, no light, no
      exposure, rendered to the player as "Through the open doorway is The
      Village Street Of Ambry Beyond The Gate", and reported by
      `inspect_contradictions.structure` as an edge to an unknown room ever
      after.

    The distinction is stated as the class rather than as a vocabulary of
    English: a name is short because it is a name (`FRONTIER_NAME_WORDS`), and
    a bearing is a closed set the engine owns.

    `allow_bearing` is for the MINT, and only there: the fringe has a grammar
    to draw on, so a bearing off a square becomes "North Lane" -- a real name
    for a real place -- and plans published before the authoring gate existed
    still carry bearings that mint correctly. A description has no such
    remedy: there is no name in it to draw.
    """
    from world.spatial import normalize_bearing

    text = " ".join(str(axis or "").split())
    if not text:
        return None
    word = text.casefold()
    if not allow_bearing and (normalize_bearing(word) or word in ("up", "down")):
        return ("frontier %r is a direction; a frontier names WHAT lies that "
                "way (a lane, a yard, the town beyond), and a direction "
                "belongs on adjacent.bearing" % text)
    if len(text.split()) > FRONTIER_NAME_WORDS:
        return ("frontier %r describes what lies that way instead of naming "
                "it; a frontier is the NAME the place is reached by, because "
                "the way out is drawn to it by that name -- say the name and "
                "put the description in the room's purpose" % text)
    return None


def mint_frontier(structure, from_uid, axis, seed, existing=(), *,
                  lanes=None, reservation=None, standing=(), residents=(),
                  spellings=()):
    """Deterministically turn one structure-side frontier label into a room.

    A FRONTIER STUB IS NAMED FOR THE DIRECTION IT LEAVES IN -- or, for a
    later stretch of one axis or a bare bearing whose kind the axis asked
    for, dealt a word in its rule's frame (below) -- never for a room the
    plan already has. The grammar's rule is chosen by its affinity with
    the axis (the words the axis shares with the rule's kind, names and
    purposes), so the "upland road" axis draws on the road rule and not the
    residential one; and a grammar name that is already a room -- the
    planner wrote its planned rooms into the grammar's name pool -- is
    RESERVED and never a stub's name. When every name in the rule is
    reserved, the axis label is the name: it is what the planner said leaves
    here. Measured on the Harrowmere replay (2026-09-03): the axis "upland
    road" off the gate minted "bridge road" (`bridge_road_2`, purpose
    "crossing") beside the real Bridge Road, and the Director, shown a stub
    called "bridge road" north of the gate, minted `upland_road` beside it;
    `slate_lane_2`, `market_square_2` and `_3` were the same class, and
    those were every duplicate room of the run. THAT CLASS IS CLOSED, in two
    halves: the naming half here (2026-09-03), and the half a name could
    never reach -- a later plan had no way to say "that space is mine", so
    it built a rival beside the stub whatever the stub was called. A plan
    now CLAIMS the space by identity (`claim_frontier_spaces`,
    `docs/design/DESIGN_FRONTIER_SPACES.md`, 2026-09-05).

    A STUB REMEMBERS WHAT IT STANDS FOR, which is what makes a later plan
    able to claim it instead of building a rival beside it: the spec keeps
    the axis it was minted from (`frontier_of`) and a `provisional` mark
    saying this room is a space held open, not a space spent.

    AND IT INHERITS THE AXIS IT WAS MINTED FROM, so the road runs on. A
    frontier is the answer to "what lies that way", and one ring out the
    answer is still the same road -- so the stub carries the axis onward and
    the world does not stop one ring past whatever a plan drew.  The onward
    axis is refused exactly where the plan-side gate refuses it (ONE RULE,
    ONE OWNER, `frontier_refusal`): a bearing is not the name of a place, so
    it cannot be the name of what lies beyond the place it named.

    A GRAMMAR NAME WITH A SLOT IS A FRAME, NOT A NAME. "the {name} Row" says
    how this story calls a row; handed out as written it named a stub "the
    {name} Sheds" (chat 165's grammar, the axis "the mainland": every one of
    its eight patterns opens on "the", so the article alone made each one
    eligible). A frame is never a stub's name as written, and a word every
    grammar name shares cannot say which name the axis asked for, so it
    makes none eligible: an axis that shares only an article with a
    grammar of literal names keeps its own label.

    A FRAME IS DEALT ONLY FOR A KIND THE AXIS ASKED FOR. Where the stub would
    otherwise be named by an ordinal (a later stretch of one axis) or by a
    bare bearing -- neither of which is a place's name -- the slot of its
    rule's frame is dealt a word from the story's own naming `lanes`
    (`world/place_names.py`, seeded by the structure and the stub's uid,
    refusing `reservation`'s people, the town's `residents`, the `standing`
    place words, and every spelling in `existing` and in `spellings`, the
    rooms' spellings as written), but only when the axis names that rule's
    kind -- a word of its `kind`, or one its frames do not all share -- more
    than any other rule's, and the rule was drawn alone. A rule drawn at
    random -- no affinity, or a tie broken by the seed -- is a kind nobody
    chose, and each stretch of one axis can draw a different one: that guess
    lives in `purpose`, which reaches the Director's brief and no mind, and
    putting it into the NAME every mind reads would assert it (review
    2026-10-08, M2: "the mainland" ran The Mainland -> "the Fennasted Way"
    -> "the Hollaholm Row"). So is a rule a purpose's prose drew: its
    articles and prepositions are words too, and "the far end of the walk"
    drew the row rule by them (N1). The ordinal stays there. An axis the
    planner named stays its name: it is the planner's word for what lies
    that way, and a dealt one would replace it.

    A DEALT NAME RENAMES THE ROOM, NEVER RE-KEYS IT. The uid stays the one
    minted above (`far_walk_2`), as a sibling the closure names keeps its
    own (`back_row_2`): the uid is the engine's key, the name the story's
    word, and a uid re-derived from a name in a script `normalize_room_id`
    does not fold was the empty id -- a kana name re-keyed a stub to the
    room uid '' (review 2026-10-08, H1).
    """
    structure = normalize_structure(structure)
    material = "|".join((structure["key"], str(from_uid), str(axis), str(seed)))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    axis_label = str(axis).replace("_", " ")
    grammar = structure["grammar"] or [{
        "kind": "place", "names": [axis_label], "purposes": [axis_label]}]
    words = _axis_words(axis_label)

    def pool_of(rule):
        pool = _axis_words(rule.get("kind"))
        for text in list(rule.get("names") or ()) + list(rule.get("purposes") or ()):
            pool |= _axis_words(str(text).replace(SLOT, " "))
        return pool

    pools = [pool_of(rule) for rule in grammar]
    # What every name says cannot tell one name from another, so it never
    # makes a name eligible. (A word every RULE's pool holds raises every
    # rule's affinity alike, which moves neither which rules tie at the top
    # nor how many, so it needs no rule of its own.)
    every_name = [_axis_words(str(n).replace(SLOT, " "))
                  for rule in grammar for n in rule.get("names") or ()]
    name_shared = set.intersection(*every_name) if len(every_name) > 1 else set()

    def affinity(index):
        return len(words & pools[index])

    best = max(affinity(i) for i in range(len(grammar)))
    rules = [rule for i, rule in enumerate(grammar) if affinity(i) == best] \
        if best else list(grammar)
    rule = rules[rng.randrange(len(rules))]
    # WHAT THE AXIS ASKED FOR IS READ OFF THE WORDS THAT NAME A KIND, never
    # off a purpose's prose. The draw above reads every word of a rule, and
    # a purpose is a sentence: its articles and prepositions are words like
    # any other, so "the far end of the walk" drew the row rule by "the",
    # "of" and "walk" (its purpose: "a row of stilt houses ... onto the
    # walk") and its second stretch was dealt "the Holawick Row" -- a kind
    # nobody chose, in the name every mind reads (review 2026-10-08, N1,
    # chat 165's own grammar). A rule's kind is named by its `kind` and by
    # the words its frames write around the slot, less the words EVERY one
    # of its frames writes: those are how the story frames a place of that
    # kind ("the {name} ..."), not which kind it is, and a rule with one
    # frame is named by its `kind` alone. The axis asked for a rule when it
    # shares more of those words with it than with any other rule, and its
    # frame is dealt only where the draw picked that same rule, alone: a tie
    # broken by the seed is a kind nobody chose (M2), and a draw the asking
    # words disagree with was decided by the prose. The draw itself does not
    # move, so `purpose` is what it was.
    asking = []
    for candidate in grammar:
        frames = [_axis_words(str(pattern).replace(SLOT, " "))
                  for pattern in name_patterns(candidate)]
        framed = set().union(*frames) - set.intersection(*frames) \
            if len(frames) > 1 else set()
        asking.append(len(words & (_axis_words(candidate.get("kind")) | framed)))
    top = max(asking)
    asked = (bool(best) and len(rules) == 1 and bool(top)
             and asking.count(top) == 1 and grammar[asking.index(top)] is rule)
    taken = {str(x) for x in existing}
    # A grammar name is the stub's only when the axis asked for it by a
    # word of its own -- "north" draws "North Lane"; "upland road" draws
    # "upland road" -- and never by the rule's kind word alone, or the "far
    # road" axis would draw the road rule's "upland road" and be one more
    # stub named for a place it is not. Otherwise the axis label is the
    # name, and the Director names the room properly when it furnishes it.
    kind_words = _axis_words(rule.get("kind"))
    names = [name for name in (rule["names"] or ())
             if not is_pattern(name)
             and normalize_room_id(name) not in taken
             and (_axis_words(name) & words) - kind_words - name_shared]
    purposes = rule["purposes"] or [rule["kind"]]
    name = _proper(names[rng.randrange(len(names))] if names else axis_label)
    base = normalize_room_id(name) or "planned_room"
    uid, suffix = base, 2
    while uid in taken:
        uid, suffix = f"{base}_{suffix}", suffix + 1
    if uid != base:
        # A second segment of the same axis is the same name with an
        # ordinal, so the Director never sees two rooms spelled alike.
        name = f"{name} {suffix - 1}"
    bare_bearing = not names and bool(
        normalize_bearing(axis_label.casefold())
        or axis_label.casefold() in ("up", "down"))
    patterns = name_patterns(rule)
    if (uid != base or bare_bearing) and asked and lanes and patterns:
        pattern = patterns[int(digest[16:32], 16) % len(patterns)]
        dealt = deal_place_name(
            pattern, scope=structure["key"], key=uid, lanes=lanes,
            reservation=reservation, residents=residents, standing=standing,
            taken=list(taken) + [str(x) for x in spellings or ()])
        if dealt:
            name = dealt
    # A PURPOSE THAT IS THE NAME SAYS NOTHING, AND READS AS AUTHORED. A
    # structure with no grammar falls back to a rule built out of the axis
    # label itself, so the purpose comes back as the room's own name: the
    # Room's `frontier: ["Lake Sarrat Dry Bed"]` minted a planned room whose
    # entire description was "Lake Sarrat Dry Bed" (PS8, solitude run,
    # 2026-09-05). An ABSENT purpose is honest -- the Director furnishes the
    # room on entry, and `is_planned_stub` already reads a stub with no prose
    # as a stub -- where a purpose equal to the name is a description nobody
    # wrote standing in the way of the one somebody would.
    purpose = str(purposes[rng.randrange(len(purposes))] or "")
    if normalize_room_id(purpose) in (normalize_room_id(name),
                                      normalize_room_id(axis_label)):
        purpose = ""
    return uid, {
        "name": name, "purpose": purpose,
        "structure": structure["key"], "access": "",
        # AN OPENING, NOT A DOOR. A frontier label answers "what lies that
        # way" and says nothing about what stands between, so minting
        # `open_door` invented a door -- outdoors, a door between a wharf
        # terrace and a dry lake bed (PS8). `open` asserts strictly less and
        # is passable, visible, audible and scent-carrying everywhere
        # `open_door` is; the Director may still declare a door when it
        # furnishes the room.
        "adjacent": [{"to": str(from_uid), "barrier": "open"}],
        "frontier": [] if frontier_refusal(axis) else [str(axis)],
        "provisional": True,
        "frontier_of": {"room": str(from_uid), "axis": str(axis)},
    }


def plant_structure(cid, structure, rooms, *, owning_book_id=None,
                    created_turn_id=None, claims=None):
    """Persist a prose-free planned skeleton and its structure grammar.

    `claims` is `claim_frontier_spaces`' second return value, and it is the
    only thing that may write a room's NAME to something other than the
    plan's own: a claimed room keeps the name a story has been using for it
    and accumulates the other spelling as an alias, so every reference
    already written still resolves (`_planned_spellings`). Absent, this
    writes exactly what it always wrote.
    """
    from core.db import q, qi, transaction, wget_for_frame, wset_for_frame

    structure = normalize_structure(structure)
    normalized = {}
    for uid, raw in (rooms or {}).items():
        if not isinstance(raw, dict):
            continue
        normalized[str(uid)] = {
            # A ROOM NOBODY NAMED WEARS THE PLACEHOLDER, never its id: the
            # Charter Planner landed "net_loft" and "the_stair" nameless
            # (scratch play 2026-09-14, chat 7) and the id became the name
            # the page showed. `derived_room_name` is the one spelling.
            "name": str(raw.get("name") or derived_room_name(uid)),
            "purpose": str(raw.get("purpose") or ""),
            "structure": structure["key"],
            "access": str(raw.get("access") or ""),
            "adjacent": [dict(edge) for edge in raw.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
            "frontier": [str(x) for x in raw.get("frontier") or () if str(x)],
            # What a claimed stub was minted for, carried through the claim:
            # the axis a room was minted from names the way ON, and
            # `prepare_frontier_expansion` reads it to tell a chain from a
            # reference. Absent on every room no frontier made.
            **({"frontier_of": dict(raw["frontier_of"])}
               if isinstance(raw.get("frontier_of"), dict) else {}),
            # A plan could say what a room is FOR and not how big it is: this
            # rebuild listed the prose fields and dropped the measurement, so
            # a stall range asked for "four paces wide and twenty long"
            # reached the registry sizeless and survived only as prose in
            # `purpose` (F47, measured 2026-09-05 in all five play runs).
            **planned_geometry(raw),
            # And how it reads from far off, which the plan seeds and the
            # world may change (`PLAN_SEEDED_FIELDS`).
            **planned_seed(raw),
            # And the FIXTURES it named, which is what a hand resolves a
            # contact target against (`planned_anchors`).
            **planned_anchors(raw),
            # And, for a room the closure invented, the room it was split
            # from (`world/frontage.py`): the plan is where provenance lives,
            # and the frontage reads it there by the room's own uid.
            **split_marks(raw),
        }
    if len(normalized) > structure["max_planned"]:
        raise ValueError("planned rooms exceed structure.max_planned")
    # AN EDGE IS ONE DOORWAY HOWEVER MANY SIDES DECLARE IT (the fringe's
    # own rule, `materialize_planned_fringe`), and the plan is where it is
    # settled. The Charter Planner declared the Stair's steps from the
    # Stair's side only (scratch play 2026-09-14, chat 7): the scene put the
    # creature one room below the player and no edge led back down to it,
    # so nothing it did could reach her, the aperture never held it, and
    # the Director minted a "cliff" for the steps she could see. A planned
    # room whose spec names a neighbour is that neighbour's neighbour too.
    for uid, spec in list(normalized.items()):
        for edge in spec.get("adjacent") or ():
            other = str(edge.get("to") or "")
            back = normalized.get(other)
            if back is None or other == uid:
                continue
            if any(str(e.get("to")) == uid for e in back.get("adjacent") or ()):
                continue
            reciprocal = {"to": uid, **{k: v for k, v in edge.items()
                                        if k in ("barrier", "distance") and v}}
            # The way back down a way up: a vertical edge reverses; a
            # bearing is the declaring side's and is not copied.
            vertical = str(edge.get("vertical") or "")
            if vertical in ("up", "down"):
                reciprocal["vertical"] = "down" if vertical == "up" else "up"
            back.setdefault("adjacent", []).append(reciprocal)
    # A PLAN DOES NOT RE-MINT A SPENT IDENTITY EITHER (review 2026-09-07,
    # Section I residual on B8/A55, rework). The registry's own rule is that a
    # projection revives a retired row only where the room's live existence
    # BEGINS this beat (`persist.commit_room_registry._prepare_room_registry`
    # carries that as `revive`); planting is not that -- a planned row is a
    # reservation of identity, not a room anybody is standing in. The mint was
    # shut by reserving every retired spelling (`prepare_frontier_expansion`),
    # and this is the same door: `story.plot_packages._apply_plan_rooms` calls
    # this mid-story, so a package planting a room whose uid folds onto a ruin
    # walked straight through the upserts below, which carried
    # `retired_turn_id=NULL`.
    #
    # Re-keyed rather than refused, because the alternatives are both silent:
    # leaving the revive off with the uid intact writes the plan's room into a
    # retired row, and every `planned_*` reader filters retired rows, so the
    # plan would lose a room and say nothing. A rebuilt chapel is a new room
    # beside the ruin of the old one, which is what the story means anyway.
    spent = retired_room_spellings(cid)
    renamed = {}
    if spent:
        live = set(registry_rows(cid))    # live rows only; retired are filtered
        taken = set(normalized) | live | spent
        # A uid a LIVE row already owns is never re-keyed: writing a live row
        # revives nothing, and re-keying it minted a second registry row for
        # one place while the live row's payload went stale -- a retired row
        # aliased "Ferry Crossing" re-keyed a replant of the live room
        # `ferry_crossing` to `ferry_crossing_2` (A55 rework, second skeptic).
        for uid in [u for u in normalized
                    if normalize_room_id(u) in spent and u not in live]:
            base, fresh, suffix = uid, uid, 2
            while fresh in taken or normalize_room_id(fresh) in spent:
                fresh, suffix = "%s_%d" % (base, suffix), suffix + 1
            taken.add(fresh)
            renamed[uid] = fresh
        for uid, fresh in renamed.items():
            normalized[fresh] = normalized.pop(uid)
        for spec in normalized.values():
            for edge in spec.get("adjacent") or ():
                if isinstance(edge, dict) and str(edge.get("to")) in renamed:
                    edge["to"] = renamed[str(edge["to"])]
            held = spec.get("frontier_of")
            if isinstance(held, dict) and str(held.get("room")) in renamed:
                held["room"] = renamed[str(held["room"])]
            # Every other field that names a room: the room a split room came
            # from, and the rooms a room lies `over` (a storey's footprint,
            # `spatial_levels`), which a closure plan now carries. Left on the
            # spent spelling, `over` named a ruin and the storey inference
            # dropped the pair as unknown (review 2026-10-08, L4).
            for mark, parent in split_marks(spec).items():
                if parent in renamed:
                    spec[mark] = renamed[parent]
            if isinstance(spec.get("over"), list):
                spec["over"] = [renamed.get(str(under), under)
                                for under in spec["over"]]
    claimed = (claims or {}).get("rows") or {}
    holders = (claims or {}).get("holders") or {}
    with transaction():
        for uid, planned in normalized.items():
            payload = json.dumps({"planned": planned}, ensure_ascii=False)
            row = claimed.get(uid)
            if row:
                # A CLAIM RENAMES IN PLACE. The uid never moves, so the name
                # and the alias list are the only columns that change, and
                # the old name goes into the aliases the same commit the new
                # one goes into the column.
                qi(
                    "INSERT INTO room_registry"
                    "(chat_id,room_uid,owning_book_id,parent_entity,name,"
                    "aliases,payload,created_turn_id,retired_turn_id) "
                    "VALUES(?,?,?,?,?,?,?,?,NULL) "
                    "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
                    "name=excluded.name,aliases=excluded.aliases,"
                    # No `retired_turn_id=NULL`: planting does not un-retire
                    # (see the reservation above). A claim targets a LIVE
                    # planned row, so this half never had a ruin to revive.
                    "payload=excluded.payload",
                    (cid, uid, owning_book_id, None, row["name"],
                     json.dumps(row.get("aliases") or [], ensure_ascii=False),
                     payload, created_turn_id),
                )
                continue
            qi(
                "INSERT INTO room_registry"
                "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,"
                "payload,created_turn_id,retired_turn_id) VALUES(?,?,?,?,?,?,?,?,NULL) "
                "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
                # Same rule, and the half a plot package reaches: the uid
                # here can no longer fold onto a retired spelling, and if a
                # caller hands one in by hand the retirement still stands.
                "name=excluded.name,payload=excluded.payload",
                (cid, uid, owning_book_id, None, planned["name"],
                 json.dumps([planned["name"], uid.replace("_", " ")]),
                 payload, created_turn_id),
            )
        # A claim on a space nothing has minted into yet spends the holder's
        # axis and records what now stands in it; only the holder's planned
        # payload moves, never its identity.
        for uid, spec in holders.items():
            row = q("SELECT payload FROM room_registry WHERE chat_id=? AND "
                    "room_uid=?", (cid, uid), one=True)
            if not row:
                continue
            payload = _payload(row)
            payload["planned"] = spec
            qi("UPDATE room_registry SET payload=? WHERE chat_id=? AND "
               "room_uid=?",
               (json.dumps(payload, ensure_ascii=False), cid, uid))
        stored = normalize_structures(
            wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})
        stored["items"][structure["key"]] = structure
        wset_for_frame(cid, STRUCTURES_KEY, stored, None)
    return structure, normalized


def materialize_planned_fringe(cid, scene):
    """Add planned neighbours of occupied rooms as small live-scene stubs."""
    scene = scene if isinstance(scene, dict) else {}
    rooms = scene.setdefault("rooms", {})
    occupied = {str(room) for room in (scene.get("positions") or {}).values()
                if str(room)}
    if not occupied:
        return scene, 0
    planned = _planned_specs(cid)
    added = 0
    targets = set()
    #: room uid -> the planned edges this pass offers it, applied below once
    #: every stub of the pass exists.
    supply = {}
    for uid in occupied:
        spec = (planned.get(uid) or (None, {}))[1]
        planned_edges = [dict(e) for e in spec.get("adjacent") or ()
                         if isinstance(e, dict) and e.get("to")]
        # A plan may attach to a room the scene ALREADY HOLDS from the
        # planned side only: the Room plans a lighthouse "adjacent: [{to:
        # beach}]" and the live beach, which is in no plan, carries no spec
        # naming the lighthouse back. Read from the occupied room alone, the
        # fringe never saw such a neighbour, so the player walked toward a
        # published plan and the Director minted a stub of its own beside
        # it and filed a need the plan already answered (chat 114 on a copy,
        # 2026-09-05, turns 4-6: `beach_far_end` minted, the planned
        # `lighthouse_keeper_room` never). An edge is one doorway however
        # many sides declare it, so a planned room whose spec names the
        # occupied room is that room's planned neighbour too, and the
        # occupied room receives the reciprocal exit it did not declare.
        for other_uid, (_name, other_spec) in planned.items():
            if other_uid == uid or other_uid in rooms:
                continue
            for e in other_spec.get("adjacent") or ():
                if isinstance(e, dict) and str(e.get("to") or "") == uid \
                        and not any(str(pe.get("to")) == other_uid
                                    for pe in planned_edges):
                    planned_edges.append({
                        "to": other_uid,
                        **{k: v for k, v in (("barrier", e.get("barrier")),)
                           if v}})
        targets.update(str(e.get("to")) for e in planned_edges)
        if uid in rooms and planned_edges:
            supply.setdefault(uid, []).extend(planned_edges)
    for uid in sorted(targets):
        if uid in rooms or uid not in planned:
            continue
        name, spec = planned[uid]
        rooms[uid] = {
            "name": name, "adjacent": [],
            "planned": True, "purpose": str(spec.get("purpose") or ""),
            # A stub is measured the beat it is minted, not once some hand
            # describes it: a planned room reaching the live scene by the
            # fringe is the same room `skeleton_rooms` lays out at the
            # opening, and a measurement the plan stated is not the
            # Director's to invent a second time.
            **planned_geometry(spec),
            **planned_seed(spec),
            **planned_anchors(spec),
        }
        if spec.get("structure"):
            rooms[uid]["region"] = normalize_region_id(spec["structure"])
        supply[uid] = [dict(e) for e in spec.get("adjacent") or ()
                       if isinstance(e, dict) and e.get("to")]
        added += 1
    # WHILE A ROOM IS STILL THE PLAN'S PROSE-FREE STUB, THE PLAN OWNS ITS
    # NAME, ITS PURPOSE AND ITS MEASUREMENTS. A claim renames the registry
    # row in place, and the live scene has to follow: `_prepare_room_registry`
    # projects the registry's name FROM the scene every commit, so a
    # registry-only rename of a stub the fringe has already materialized is
    # written back to its old name on the next beat and the claim silently
    # un-happens. Once the room carries prose it is its own
    # (`settle_developed_stubs` takes the seed off) and nothing here touches
    # it -- which is the same line the claim draws when it refuses to rename.
    stubs = []
    for uid, (name, spec) in planned.items():
        room = rooms.get(uid)
        if not isinstance(room, dict) or not room.get("planned"):
            continue
        if str(room.get("desc") or room.get("description") or "").strip():
            continue
        stubs.append(uid)
        room["name"] = name
        if str(spec.get("purpose") or ""):
            room["purpose"] = str(spec["purpose"])
        room.update(planned_geometry(spec))
        # A ROOM'S ANCHORS ARE ADDED TO, NOT REPLACED (`spatial_merge.
        # _merge_anchor_fields`, one layer out). A stub the plan furnished
        # may already have had a fixture written onto it by a beat, and
        # re-echoing the plan's map over the top would take that fixture
        # and every station hanging off it.
        for _aid, _anchor in planned_anchors(spec).get("anchors", {}).items():
            room.setdefault("anchors", {}).setdefault(_aid, _anchor)
    # ITS FAR LOOK IS THE PLAN'S ONLY WHEN THE PLAN SPEAKS: a beat that
    # burned the place, or a host who edited it, has the last word until the
    # plan says something new (`PLAN_SEEDED_FIELDS`).
    _lay_planned_looks(scene, stubs, planned)
    # THE SCENE ONLY EVER HOLDS AN EDGE INTO A ROOM THE SCENE HOLDS, and the
    # membership test runs after every stub of this pass exists, so two
    # planned rooms minted together keep the doorway between them.
    #
    # The plan keeps the rest. A fringe that materialises only the room next
    # to the occupied one hands the new stub the plan's whole adjacency,
    # including the way on to a room nobody has walked toward yet; the
    # dangling-exit guard then drops that edge and warns, in the same commit,
    # every beat, for ever ("scene: dropped exit(s) from `desert_road_east`
    # to undefined room(s) `milestone_shrine`", nine consecutive beats of one
    # caravanserai run, 2026-09-05). `protect_planned_edges` states the other
    # half of the same rule and puts the edge back the beat the target is
    # minted, so nothing is lost -- what stops is a warning about a room the
    # world does not have yet.
    for uid, edges_in in supply.items():
        room = rooms.get(uid)
        if not isinstance(room, dict):
            continue
        # The live definition owns prose/physics it declared; structure
        # supplies only exits that live mapping has not named.
        edges = {str(e.get("to")): dict(e)
                 for e in (room.get("adjacent") or ())
                 if isinstance(e, dict) and e.get("to")}
        for edge in edges_in:
            to = str(edge.get("to") or "")
            if to and to in rooms and not crosses_an_interior(rooms, uid, to):
                edges.setdefault(to, dict(edge))
        room["adjacent"] = list(edges.values())
    # A SOLVED PLAN REACHES THE STUB IT ALREADY MADE: the positions the
    # layout tier wrote onto anchors and doorways the stub was minted with
    # -- and a re-planned one takes its solve back off it
    # (`apply_planned_layout`). Only a plan carrying a `site`, or a stub
    # standing on the tier's plan, is read.
    apply_planned_layout(scene, planned)
    _settle_stub_barriers(rooms)
    # THE ROOMS THE CLOSURE INVENTED, GIVEN A PLACE ONCE THEIR STREET HAS A
    # WALL (`world/frontage.py`). A plan rarely says which wall a doorway is
    # on -- the location contract asks for none -- so the wall arrives with
    # whichever hand first declares one, usually the opening's establish, and
    # this is the first point after every merge where the scene holds it. It
    # writes doorway offsets only on rooms still the plan's prose-free stubs,
    # moves a split room only along the wall a hand chose for it and only to
    # where it then stands on no room on the plane, and a room it has placed
    # carries its offset and is left alone thereafter.
    from world.frontage import lay_frontages
    lay_frontages(scene, {uid: spec for uid, (_name, spec) in planned.items()})
    return scene, added


def _settle_stub_barriers(rooms):
    """A STUB'S DOORWAY IS THE PLAN'S GUESS UNTIL SOMEONE STANDS AT IT.

    An edge is one doorway however many sides declare it, and a barrier is a
    property of the doorway rather than of the side you stand on --
    `spatial_merge._mirror_symmetric_barriers` states that for a diff, which
    is where both sides are written by the same hand in the same breath. The
    plan-supply path above never met that rule: a stub takes its exits from
    the plan, where the barrier is whatever the Room wrote (or the schema's
    open way through) before anybody had been there, and it keeps that
    barrier for ever while the story goes on describing the same doorway
    from the room it can actually see.

    Every sense then reads whichever side it happens to stand on. Measured
    in the descent run (chat 117, turn 13): six of the seven doorways off
    one service spine disagreed with themselves, and the containment annex
    -- which the spine records behind a shut `closed_door` named "the
    containment door" -- heard through an `open_door`, because that is what
    its own side still said.

    The plan yields and the story stands: a stub's barrier is replaced by
    the one the room on the other side declares, and only ever by a barrier
    that room actually carries. A stub with prose is not a stub any more
    (`settle_developed_stubs` takes the flag off) and is not touched, and a
    declaration made from the stub's OWN side has already been mirrored onto
    the live room by the merge, so what is left here is exactly the
    plan-against-story disagreement."""
    for uid, room in (rooms or {}).items():
        if not isinstance(room, dict) or not room.get("planned"):
            continue
        for edge in room.get("adjacent") or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            other = rooms.get(str(edge["to"]))
            if not isinstance(other, dict):
                continue
            for back in other.get("adjacent") or ():
                if not isinstance(back, dict) \
                        or str(back.get("to") or "") != str(uid):
                    continue
                if "barrier" in back and back["barrier"] != edge.get("barrier"):
                    edge["barrier"] = back["barrier"]
                break


def _planned_specs(cid):
    """{room_uid: (name, planned spec)} for every live planned registry row.

    Off the shared parse (`registry_rows`), so the spec IS the one every
    other reader of this turn holds: read it, never mutate it.
    """
    return {uid: (str(entry["name"] or uid), entry["planned"])
            for uid, entry in registry_rows(cid).items()
            if entry["planned"] is not None}


def _planned_spellings(cid):
    """``{room_uid: {spelling, ...}}`` -- every spelling a live planned room
    answers to, folded by `normalize_room_id`: its id, its current name and
    every alias the registry keeps for it.

    THE ALIAS IS THE WHOLE POINT OF A RENAME. A room the plan renames keeps
    its uid and its old name as an alias (`claim_frontier_spaces`), and a
    lookup that reads only the `name` column stops answering to the old
    spelling the moment the new one lands -- so a Director still saying
    "Coastal Lane" mints `coastal_lane_2` beside the plan's room, which is
    exactly the duplicate class the claim exists to close (the second bridge
    road, Harrowmere 2026-09-03). `_registry_alias_index` and
    `subjects.resolve_subject` already read aliases; the plan's own tables
    did not.
    """
    out = {}
    for uid, entry in registry_rows(cid).items():
        if entry["planned"] is None:
            continue
        keys = {normalize_room_id(uid), normalize_room_id(entry["name"])}
        keys.update(normalize_room_id(str(a or ""))
                    for a in entry["aliases"] or ())
        keys.discard("")
        out[uid] = keys
    return out


def planned_room_spellings(cid):
    """{spelling: room_uid} for every live planned registry room, under its
    id, its name and every alias as `normalize_room_id` spells them. A
    spelling two plans share maps to ``""``: two rooms answer to it, so it
    names neither (the room rule `dedup_minted_rooms` applies to bodies
    too)."""
    out = {}
    for uid, keys in _planned_spellings(cid).items():
        for key in keys:
            out[key] = "" if key in out and out[key] != uid else uid
    return out


def is_planned_stub(scene, room_id, specs=None):
    """Is this live room still the plan's prose-free stub?

    A stub is a room the scene marks `planned` with no `desc`, or one the
    registry plans that the scene has not yet described. A room with a
    description has been developed, whatever flag it still carries.
    """
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        # Planned by the registry and not yet a scene row: a stub the
        # scene has not reached, which is exactly what a brief is for.
        return bool(specs and room_id in specs)
    if str(room.get("desc") or room.get("description") or "").strip():
        return False
    if room.get("planned"):
        return True
    return bool(specs and room_id in specs)


def rooms_to_develop(scene, focus_room, extra=()):
    """The rooms a Director beat is standing in or could be looking into:
    the focus room, any movement target, and every neighbour of the focus
    room joined by something other than a wall -- a closed door is a room
    the beat may open, and a room in view through an open one is a room
    the beat may describe. Deterministic; reads no prose."""
    from world.spatial import effective_adjacent, normalize_barrier

    rooms = (scene or {}).get("rooms") or {}
    out = []
    if focus_room and focus_room in rooms:
        out.append(str(focus_room))
    # A declared target is in reach whether or not the scene holds it yet:
    # a planned room the beat walks into is briefed before it is a scene
    # row (`planned_room_brief` keeps only what the plan knows).
    for rid in extra:
        if rid and str(rid) not in out:
            out.append(str(rid))
    if focus_room and focus_room in rooms:
        for edge in effective_adjacent(scene, focus_room):
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            if normalize_barrier(edge.get("barrier")) == "wall":
                continue
            to = str(edge["to"])
            if to in rooms and to not in out:
                out.append(to)
    return out


def rooms_in_view_or_ahead(scene, focus_room, *, next_leg=None, bound_for=None):
    """The rooms a body standing in `focus_room` can SEE INTO or is HEADING
    FOR, in the order it meets them: the focus room, the next leg of a walk
    under way, every room sight reaches through one of the focus room's
    doorways -- `visible_adjacent_rooms`, the same answer perception admits
    into a view, so an open doorway, a window or bars, and a one-way window
    only the way it looks -- and the walk's end. Only rooms the scene holds.
    Deterministic; reads no prose.

    NOT `rooms_to_develop`, which also takes every room behind a closed
    door: that set is the BRIEF a beat is handed, cheap author knowledge
    for a door the beat may open. This one is the set the world builds
    before anyone arrives (owner's ruling 2026-10-08: each planned room the
    player "can see into or is heading for"), and a room behind a shut door
    is neither until somebody opens it or sets off for it -- a beat that
    opens one still has its room designed in the beat, as before."""
    from world.spatial import visible_adjacent_rooms

    rooms = (scene or {}).get("rooms") or {}
    out = []

    def add(rid):
        rid = str(rid or "")
        if rid and rid in rooms and rid not in out:
            out.append(rid)

    if not focus_room or focus_room not in rooms:
        return out
    add(focus_room)
    add(next_leg)
    for seen in visible_adjacent_rooms(scene, focus_room) or ():
        if isinstance(seen, dict):
            add(seen.get("room_id"))
    add(bound_for)
    return out


def planned_room_brief(cid, scene, room_ids):
    """The Director's development brief for the planned stubs among
    `room_ids`: {room_id: {name, purpose, access, exits, structure}}.

    THE SEED, HANDED TO THE HAND THAT FURNISHES. The plan says what a room
    is FOR and what it joins; the Director says what is in it. Purpose and
    exits are given and protected (`protect_planned_edges`); contents are
    the Director's, and this brief is the one place the plan's purpose
    reaches a model during play. It is author knowledge: it goes to the
    Director stages and the spatial hand, never to a mind or the narrator,
    which learn the room by perceiving what the Director wrote.
    """
    from world.landscape import normalize_far_look
    specs = _planned_specs(cid)
    rooms = (scene or {}).get("rooms") or {}
    names = {rid: str((r or {}).get("name") or rid) for rid, r in rooms.items()}
    names.update({rid: name for rid, (name, _s) in specs.items()})
    structures = None
    out = {}
    for rid in room_ids or ():
        if not is_planned_stub(scene, rid, specs):
            continue
        room = rooms.get(rid) or {}
        name, spec = specs.get(rid, (names.get(rid, rid), {}))
        exits = {}
        for edge in list(spec.get("adjacent") or ()) + list(
                room.get("adjacent") or ()):
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            to = str(edge["to"])
            entry = exits.setdefault(to, {"to": to, "name": names.get(to, to)})
            for key in ("barrier", "dir", "name"):
                if edge.get(key) and key not in entry or key == "name" \
                        and edge.get(key):
                    entry[key if key != "name" else "way"] = edge[key]
        brief = {
            "name": name,
            "purpose": str(spec.get("purpose") or room.get("purpose") or ""),
            "access": str(spec.get("access") or room.get("access") or ""),
            "exits": list(exits.values()),
        }
        # HOW IT READS FROM FAR OFF, as far eyes have been seeing it: the
        # stub's own look first -- a beat that burned the place or a host
        # who edited it wrote there, and the far layer reads nothing else --
        # and the plan's only for a room the scene does not hold yet. The
        # room the hand furnishes is the one that look describes, and a desc
        # free to contradict it would be a second spelling of the place.
        far_look = normalize_far_look(room.get("far_look") if rid in rooms
                                      else spec.get("far_look"))
        if far_look:
            brief["far_look"] = far_look
        skey = str(spec.get("structure") or "")
        if skey:
            if structures is None:
                from core.db import wget_for_frame
                structures = normalize_structures(
                    wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})["items"]
            structure = structures.get(skey)
            if structure:
                brief["structure"] = {
                    "key": skey,
                    "grammar": structure.get("grammar") or [],
                }
            # The part of the map the room is in, by the structure that
            # planned it (world/regions.py) -- so the hand furnishing a stub
            # knows what the room is part of, and its neighbours it mints
            # inherit the same answer.
            brief["region"] = {
                "id": normalize_region_id(skey),
                "name": str((structure or {}).get("name") or skey),
            }
        out[rid] = brief
    return out


def planned_room_ids(cid):
    """Every live registry room that carries a plan -- the town's own
    topology, which a beat may furnish and may not delete."""
    return set(_planned_specs(cid))


def provisional_room_ids(cid):
    """Every live planned room that is a frontier space HELD OPEN: a stub
    `mint_frontier` made from an axis and marked `provisional`, standing in
    until a plan claims the space (`claim_frontier_spaces`, which rewrites
    the row without the mark). Its name came from the structure's grammar
    and its purpose is often empty; what the space IS is the Writers'
    Room's to say."""
    return {uid for uid, (_name, spec) in _planned_specs(cid).items()
            if spec.get("provisional")}


def planned_room_index(cid, scene=None):
    """`{room_uid: name}` for every live planned room the SCENE does not yet
    hold -- one line each, the whole plan, uncapped.

    THE BRIEF IS SCOPED; KNOWING THE PLACE EXISTS MUST NOT BE.
    `planned_room_brief` deliberately covers only the stubs a beat stands in
    or looks into, because a purpose, an access note and an exit list are
    expensive and a Director furnishing a room only needs the one it is
    entering. But a player names a place from anywhere -- across a town, from
    memory, from something a character said three beats ago -- and a Director
    that has never been shown the name cannot spell it. It invents one, and
    `classify_movement` cannot rescue an invention that shares no word with
    the plan's spelling.

    Measured (the Salt Terraces, 2026-09-05, PS5): the Writers' Room
    published "Town Habitations Shelf" (`town_shelf_lane`) and a roofless
    common hall; from three rooms away the interpret payload carried no
    `planned_rooms` key at all, the Director wrote
    `upper_terrace_settlement`, and the beat after minted
    `settlement_common_hall` beside the planned one. The town ended with two
    shelves of workers' houses, two common halls, and the one thing the Room
    had planted to be found unreachable in either.

    So the index is a NAME and nothing else, which is what a spelling costs:
    seven rooms was 591 bytes in that run, and the largest plan in the
    owner's database (chat 114, 49 rooms) is a few kilobytes. Uncapped, per
    the owner's standing ruling that a cap is named rather than buried --
    there is nothing here to cap.
    """
    rooms = (scene or {}).get("rooms") or {}
    return {rid: name for rid, (name, _spec) in _planned_specs(cid).items()
            if rid not in rooms}


def planned_topology(cid):
    """``{room_uid: [adjacent room uids]}`` for every live planned registry
    row -- the plan's edges by ID. `planned_context` renders the same edges
    by NAME for a reader; a walk over the graph wants the ids."""
    out = {}
    for rid, (_name, spec) in _planned_specs(cid).items():
        out[rid] = [str(edge.get("to")) for edge in spec.get("adjacent") or ()
                    if isinstance(edge, dict) and edge.get("to")]
    return out


def planned_rooms_named_in(cid, text):
    """The planned rooms whose uid or name spelling sits inside ``text``,
    folded the way `planned_context` folds a query -- the rooms a scenario
    names without ids. Sorted, for a stable payload."""
    folded = normalize_room_id(str(text or ""))
    if not folded:
        return []
    out = []
    for rid, keys in _planned_spellings(cid).items():
        if any(k == folded or k in folded for k in keys):
            out.append(str(rid))
    return sorted(out)


def protect_planned_edges(cid, scene):
    """Put back every planned exit a development dropped.

    A developed room may ADD exits; it may not lose one the plan gave it,
    because the plan is the town's topology and every other planned room
    counts on the way through. Restores the edge from the plan's own record
    (barrier, bearing, name) on the room that lost it. Returns
    [(room_id, to)] restored, for the caller's warning.
    """
    specs = _planned_specs(cid)
    rooms = (scene or {}).get("rooms") or {}
    restored = []
    for rid, (_name, spec) in specs.items():
        room = rooms.get(rid)
        if not isinstance(room, dict):
            continue
        present = {
            str(e.get("to")) for e in (room.get("adjacent") or [])
            if isinstance(e, dict) and e.get("to")}
        for other_id, other in rooms.items():
            if isinstance(other, dict):
                for e in other.get("adjacent") or []:
                    if isinstance(e, dict) and e.get("to") == rid:
                        present.add(str(other_id))
        for edge in spec.get("adjacent") or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            to = str(edge["to"])
            # Only into a room the SCENE holds. An edge to a planned room the
            # fringe has not minted yet is the plan's, not the scene's: put
            # back here, the dangling-exit guard drops it as undefined in the
            # same commit, and the pair fired four warnings a beat on chat
            # 114's terrace (lounge, dining, garden, 2026-09-04) while
            # changing nothing. The edge returns the beat the stub is minted.
            if to in present or to not in rooms:
                continue
            # AN INTERIOR'S WAY OUT IS WHERE ITS ENTITY STANDS, never the
            # plan's: `spatial_transit.apply_transit_dock_edges` rewrites
            # every edge across that boundary from the entity's position
            # and transit each merge. Chat 160 turn 4541 (2026-10-01): the
            # freight car's planned door to the upper hallway was restored
            # here after it docked four floors down, so stepping out of it
            # led back upstairs. Between two rooms of one interior, the plan
            # still holds.
            if crosses_an_interior(rooms, rid, to):
                continue
            room.setdefault("adjacent", []).append(dict(edge))
            restored.append((rid, to))
    return restored


def settle_developed_stubs(scene):
    """A planned stub that now carries a description is a room.

    Drops the `planned` flag and the plan's `purpose`/`access` seed from the
    live record: the registry keeps the plan, and the seed was author
    knowledge that has done its work. Returns the room ids settled.
    """
    settled = []
    for rid, room in ((scene or {}).get("rooms") or {}).items():
        if not isinstance(room, dict) or not room.get("planned"):
            continue
        if not str(room.get("desc") or room.get("description") or "").strip():
            continue
        room.pop("planned", None)
        room.pop("purpose", None)
        room.pop("access", None)
        settled.append(str(rid))
    return settled


def planned_context(cid, query):
    """Short structural context for mapping a specifically requested room."""
    folded = normalize_room_id(str(query or ""))
    if not folded:
        return None
    rows = []
    all_rows = registry_rows(cid)
    names = {uid: str(entry["name"] or uid)
             for uid, entry in all_rows.items()}
    # AND EVERY SPELLING THE ROOM ANSWERS TO, the old name a claim retired
    # included (`_planned_spellings`): a brief asked for under the name the
    # story has been using is the same room, not an unplanned destination.
    spellings = _planned_spellings(cid)
    for uid, entry in all_rows.items():
        spec = entry["planned"]
        if spec is None:
            continue
        name = names[uid]
        keys = set(spellings.get(uid) or ())
        keys.update({normalize_room_id(uid), normalize_room_id(name)})
        keys.discard("")
        exact = folded in keys
        if not exact and not any(key in folded for key in keys):
            # THE THIRD TIER IS THE NAME'S WORDS (`spatial.room_name_words`,
            # the same fold `scene_room_id` makes for a live room): a
            # destination written the way a person says it -- "Cope's
            # yard" for the plan's "Cope's Boatyard" -- has every word in
            # the room's name or the tail of one. Ranked below both tiers
            # above and unique or refused, like them.
            wanted = room_name_words(query)
            if not wanted or not any(
                    room_words_answer(wanted, room_name_words(form))
                    for form in (name, uid, *keys)):
                continue
            tier = 2
        else:
            tier = 0 if exact else 1
        rows.append({
            "_tier": tier,
            "room_uid": uid, "name": name,
            "purpose": str(spec.get("purpose") or ""),
            "structure": str(spec.get("structure") or ""),
            # The structure's key as a region id (world/regions.py): the
            # part of the map a reader files the room under.
            "region": normalize_region_id(spec.get("structure") or "") or None,
            "access": str(spec.get("access") or ""),
            "adjacent": [names.get(str(edge.get("to")), str(edge.get("to")))
                         for edge in spec.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
        })
    # AN EXACT MATCH IS NOT AMBIGUOUS, and the substring tier is what made it
    # look like one. The match above is deliberately loose -- the Director
    # writes a destination as a description ("Reeve's Hall interior and
    # occupants"), so a room answers when its spelling SITS INSIDE the query
    # -- but a room id also sits inside another room id. Measured on the live
    # chat 114 register: a room called `parking` is a substring of
    # `guest_parking_lot`, so both matched, `len(rows) != 1`, and the query
    # resolved to None; 30-odd rooms of that story's district answered nothing
    # at all, which is the brief the Director is handed walking into one.
    #
    # So the tiers are ranked rather than pooled. A query that names a room
    # exactly is answered by that room however many others it also brushes;
    # only when nothing matches exactly does the loose tier decide, and there
    # an ambiguity is still refused, because two descriptions matching one
    # query really is two candidates. Two EXACT hits stay refused too: one
    # room's uid equalling another's name is a genuine collision this cannot
    # break by guessing.
    for tier in (0, 1, 2):
        hits = [r for r in rows if r.get("_tier") == tier]
        if not hits:
            continue
        for row in rows:
            row.pop("_tier", None)
        return hits[0] if len(hits) == 1 else None
    return None


def _place_naming(cid, structure, by_uid, cache):
    """What `mint_frontier` deals a place name with: the story's own naming
    lanes, the identities they must not reproduce, the town's own residents,
    every spelling a room answers to as written, and the place words already
    standing in the grammar's frames -- or nothing at all for a grammar that
    opened no slot, or a story with no naming law, so neither pays a read.

    THE RESIDENTS ARE THE CHARTER REGISTRY'S PEOPLE, every institution's and
    the unemployed alike: the closure held a dealt word apart from them and
    the frontier was passed none, so chat 165's mainland minted "the
    Holensted Walk" with Tibidis Holensted asleep in the Back Row (review
    2026-10-08, M1). The SPELLINGS are as written, live rows and retired
    ones, because `existing` is folded by `normalize_room_id` and a name in
    a script it drops is not in it at all (H1). `cache["names"]` is the
    pass's own list: `prepare_frontier_expansion` adds each name it mints,
    so two stubs of one pass are held apart as well."""
    grammar = normalize_structure(structure)["grammar"]
    if not any(name_patterns(rule) for rule in grammar):
        return {}
    if "lanes" not in cache:
        from story.naming import story_identity_reservation, story_naming_lanes
        lanes, _source = story_naming_lanes(cid)
        cache["lanes"] = lanes
        cache["reservation"] = None
        cache["residents"] = []
        cache["names"] = []
        if lanes:
            from world.charter_runtime import registry_for
            cache["reservation"] = story_identity_reservation(cid, lanes)
            registry = registry_for(cid, None) or {}
            bodies = []
            for item in (registry.get("items") or {}).values():
                state = (item or {}).get("state") or {}
                bodies.extend((state.get("bodies") or {}).values())
            for person in (registry.get("people") or {}).values():
                if isinstance(person, dict):
                    bodies.append(person.get("bodies"))
            cache["residents"] = resident_name_words(bodies)
            names = cache["names"]
            for uid, entry in by_uid.items():
                names.extend([str(uid), str(entry["name"] or "")])
                names.extend(str(alias or "") for alias in entry["aliases"] or ())
            names.extend(retired_room_spellings(cid, folded=False))
    if not cache["lanes"]:
        return {}
    return {"lanes": cache["lanes"], "reservation": cache["reservation"],
            "residents": cache["residents"], "spellings": cache["names"],
            "standing": standing_fillers(grammar, cache["names"])}


def prepare_frontier_expansion(cid, scene):
    """Mint approached frontier nodes without writing during commit prepare.

    Returns ``(scene, mutations)``. The caller writes mutations inside the
    same transaction as the scene, so a frontier can never point at a room
    whose planned identity failed to land.
    """
    from core.db import wget_for_frame

    scene = scene if isinstance(scene, dict) else {}
    occupied = {str(room) for room in (scene.get("positions") or {}).values()
                if str(room)}
    if not occupied:
        return scene, []
    # THE ONE READER THAT MUTATES, so it pays for its own parse
    # (`registry_rows_for_update`): the `dict(spec)` below is shallow, and
    # `spec.setdefault("adjacent", []).append(...)` reaches straight through
    # it into the list the parse produced. Off the shared snapshot that edge
    # would land in every other reader's view of the plan for the rest of the
    # turn (C16, 2026-09-07).
    by_uid = registry_rows_for_update(cid)
    specs = {}
    counts = {}
    for uid, entry in by_uid.items():
        payload = entry["payload"]
        spec = entry["planned"]
        if isinstance(spec, dict):
            specs[uid] = (payload, dict(spec))
            skey = str(spec.get("structure") or "")
            counts[skey] = counts.get(skey, 0) + 1
    structures = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})["items"]
    mutations = []
    # A planned room reserves its uid, its name and every alias: a stub may
    # not be minted under any spelling the plan already answers to, and an
    # axis written in one of those spellings is an edge to that room.
    by_name = {}
    for row_uid, entry in by_uid.items():
        by_name.setdefault(row_uid, row_uid)
        by_name.setdefault(normalize_room_id(entry["name"]), row_uid)
        for alias in entry["aliases"] or ():
            by_name.setdefault(normalize_room_id(str(alias or "")), row_uid)
    by_name.pop("", None)
    # A RETIRED ROOM'S IDENTITY IS STILL SPENT. The parse above is live rows
    # only, so without this the reservation forgot every ruin and the mint
    # could name a stub after one -- and reviving it was one upsert away
    # (`retired_room_spellings`). Reserved, never resolved: a retired row is
    # not an edge target either, so an axis spelled like a ruin opens a new
    # space beside it instead of a door into closed history.
    existing = set(by_uid) | set(by_name) | retired_room_spellings(cid)
    rooms = scene.setdefault("rooms", {})
    naming_cache = {}
    for uid in sorted(occupied):
        if uid not in specs:
            continue
        payload, spec = specs[uid]
        structure_key = str(spec.get("structure") or "")
        structure = structures.get(structure_key) or {
            "key": structure_key, "max_planned": 200, "grammar": []}
        frontiers = [str(x) for x in spec.get("frontier") or () if str(x)]
        retained = []
        # What this expansion adds to the holder's plan, kept apart so the
        # write lays exactly this onto the row it finds inside the lock
        # (`apply_frontier_mutations`).
        added_edges = []
        standing_was = dict(spec.get("frontier_standing") or {}) \
            if isinstance(spec.get("frontier_standing"), dict) else {}
        # WHAT THE PLAN RESERVED AND WHAT NOW STANDS IN IT. An axis used to
        # be simply deleted the moment it minted, so nothing anywhere
        # recorded that a room was a placeholder and a later plan had no
        # slot to claim -- it built a rival beside it instead (the second
        # bridge road). ``{axis: room_uid}`` on the holder is that record.
        standing = dict(spec.get("frontier_standing") or {}) \
            if isinstance(spec.get("frontier_standing"), dict) else {}
        origin = spec.get("frontier_of")
        own_axis = str((origin or {}).get("axis") or "") \
            if isinstance(origin, dict) else ""
        for axis in frontiers:
            # WHAT CANNOT BE A PLACE'S NAME IS NOT MINTED AS ONE. A phrase
            # describing what lies that way is kept on the spec, where
            # `structure_warnings` reports it, instead of becoming a registry
            # room whose uid is the sentence (F63/PD4).
            if frontier_refusal(axis, allow_bearing=True):
                retained.append(axis)
                continue
            # An axis that names a room the plan already has is not a stub
            # to mint but an edge to draw: "the lane continues to Market
            # Square" reaches the square, never a second one.
            #
            # AN AXIS A ROOM WAS MINTED FROM NAMES THE WAY ON, NOT THE ROOM
            # IT MADE. A stub inherits its axis so the frontier keeps
            # moving; read as a reference, the inherited label would resolve
            # to the very room it named -- one ring out, the room BEFORE it
            # -- and the road would stop at its second segment with an edge
            # doubling back. A room's own origin axis is the one spelling
            # that cannot mean a room that already exists.
            target = None if axis == own_axis else by_name.get(
                normalize_room_id(str(axis).replace("_", " ")))
            if target and target != uid:
                edge = {"to": target, "barrier": "open_door", "axis": axis}
                spec.setdefault("adjacent", []).append(edge)
                added_edges.append(dict(edge))
                rooms.setdefault(uid, {"name": str(by_uid[uid]["name"] or uid),
                                       "adjacent": []})
                rooms[uid].setdefault("adjacent", []).append(dict(edge))
                if isinstance(rooms.get(target), dict):
                    rooms[target].setdefault("adjacent", []).append(
                        {"to": uid, "barrier": "open_door"})
                standing[axis] = target
                continue
            if counts.get(structure_key, 0) >= normalize_structure(
                    structure)["max_planned"]:
                retained.append(axis)
                continue
            new_uid, new_spec = mint_frontier(
                structure, uid, axis, f"{cid}:{structure_key}", existing,
                **_place_naming(cid, structure, by_uid, naming_cache))
            existing.add(new_uid)
            # A NAME DEALT THIS PASS IS A SPELLING THIS PASS HOLDS: the next
            # stub is minted beside it, never onto it.
            existing.add(normalize_room_id(new_spec["name"]) or new_uid)
            if "names" in naming_cache:
                naming_cache["names"].extend([new_uid, new_spec["name"]])
            standing[axis] = new_uid
            counts[structure_key] = counts.get(structure_key, 0) + 1
            edge = {"to": new_uid, "barrier": "open_door",
                    "axis": axis}
            spec.setdefault("adjacent", []).append(edge)
            added_edges.append(dict(edge))
            rooms.setdefault(uid, {"name": str(by_uid[uid]["name"] or uid),
                                   "adjacent": []})
            rooms[uid].setdefault("adjacent", []).append(dict(edge))
            rooms[new_uid] = {
                "name": new_spec["name"], "planned": True,
                "purpose": new_spec["purpose"],
                "adjacent": [dict(e) for e in new_spec["adjacent"]],
            }
            if structure_key:
                rooms[new_uid]["region"] = normalize_region_id(structure_key)
            new_payload = {"planned": new_spec}
            mutations.append({
                "room_uid": new_uid,
                "owning_book_id": by_uid[uid]["owning_book_id"],
                "parent_entity": by_uid[uid]["parent_entity"],
                "name": new_spec["name"],
                "aliases": [new_spec["name"], new_uid.replace("_", " ")],
                "payload": new_payload,
            })
        if frontiers:
            spec["frontier"] = retained
            if standing:
                spec["frontier_standing"] = standing
            payload = dict(payload, planned=spec)
            mutations.append({
                "room_uid": uid,
                "owning_book_id": by_uid[uid]["owning_book_id"],
                "parent_entity": by_uid[uid]["parent_entity"],
                "name": str(by_uid[uid]["name"] or uid),
                "aliases": by_uid[uid]["aliases"],
                "payload": payload,
                # WHAT THE EXPANSION OWNS of the holder's plan: the edges it
                # drew, the axes it spent and what now stands in them.
                # `apply_frontier_mutations` lays exactly this onto the row as
                # it stands inside the lock; the rest of the plan is written
                # out of band meanwhile (`write_planned_layout`).
                "expansion": {
                    "adjacent": added_edges,
                    "frontier_was": frontiers,
                    "frontier": retained,
                    "standing": {axis: room for axis, room in standing.items()
                                 if standing_was.get(axis) != room},
                },
            })
    return scene, mutations


def frontier_spaces(cid):
    """Every frontier space the plan is still holding OPEN, for a planner.

    A SPACE IS THE AXIS, THE ROOM IT HANGS OFF, AND WHAT STANDS THERE. Two
    states, and both are unfilled:

    * ``open`` -- the axis is on the holder's plan and nothing has minted
      from it, because nobody has stood in the holder room yet. An axis the
      mint refuses (`frontier_refusal`) is open too and says why.
    * ``provisional`` -- a stub stands in the space, named from the
      structure's grammar, standing in until a plan claims it.

    A space a real plan fills is not a space and is not listed. A planner
    that cannot see the slot plans BESIDE it, which is exactly what the
    Harrowmere corpus measured: the axis "upland road" minted a stub called
    "bridge road" beside the real Bridge Road and the Director, shown the
    stub, minted `upland_road` beside THAT. Those, with `slate_lane_2` and
    `market_square_2`/`_3`, were every duplicate room of the run.

    `claim_frontier_spaces` takes the ``room`` and ``axis`` of a row here.
    """
    specs = _planned_specs(cid)
    out = []
    for uid, (name, spec) in specs.items():
        skey = str(spec.get("structure") or "")
        for axis in spec.get("frontier") or ():
            axis = str(axis or "")
            if not axis:
                continue
            row = {"room": uid, "room_name": name, "structure": skey,
                   "axis": axis, "state": "open"}
            refusal = frontier_refusal(axis, allow_bearing=True)
            if refusal:
                row["unmintable"] = refusal
            out.append(row)
        standing = spec.get("frontier_standing")
        if not isinstance(standing, dict):
            continue
        for axis, target in standing.items():
            stub_name, stub_spec = specs.get(str(target), ("", {}))
            if not isinstance(stub_spec, dict) or not stub_spec.get("provisional"):
                continue
            out.append({"room": uid, "room_name": name, "structure": skey,
                        "axis": str(axis), "state": "provisional",
                        "stub": str(target), "stub_name": stub_name})
    return sorted(out, key=lambda row: (row["room"], row["axis"]))


def _registry_aliases(cid):
    """``{room_uid: [alias, ...]}`` as the registry stores them."""
    return {uid: [str(a) for a in entry["aliases"] or () if str(a)]
            for uid, entry in registry_rows(cid).items()}


def claim_frontier_spaces(cid, rooms, *, scene=None):
    """Rekey planned rooms that CLAIM a frontier space onto the room already
    holding it.

    THE RULE: a minted stub is the space the plan reserved, standing in
    until a plan claims it; claiming renames the room and never mints a
    second one.

    A plan says which space it fills BY IDENTITY -- ``claims: {room, axis}``
    on a planned room, the holder's uid and the axis, both ids
    `frontier_spaces` already hands the planner. Never a name and never a
    resemblance between two nouns: a guard reading free prose fails in
    whichever direction its missing word points, and this one would decide
    whether two places are one place.

    Returns ``(rooms, plan, errors)``:

    * `rooms` -- the map rekeyed onto the claimed uids, every
      ``adjacent.to`` inside the same operation remapped with it, so THE
      ROOM'S UID NEVER CHANGES: edges, the registry projection, anything
      standing in it and every reference already written stay intact. The
      stub's own edges survive a claim that does not name them, the same
      rule `protect_planned_edges` keeps for a developed room.
    * `plan` -- ``{"rows", "holders", "claims"}`` for `plant_structure` to
      write and for a preview to report.
    * `errors` -- one per refusal, naming the holder and what fills the
      space. First claim wins; a second is refused, because a place cannot
      be two things. `plan["refused"]` names the rooms those refusals came
      from: a claim that cannot be honoured must not fall back to planting
      the room ANYWAY, because a room planted beside the space it meant to
      fill is the whole defect.

    A ROOM SOMEBODY HAS BEEN IN KEEPS ITS NAME. A name is what the player
    knows the place by, and renaming it is a lie about their own memory --
    so a claim on such a room takes the purpose, the geometry and the onward
    axes and LEAVES the name, and says which it did. What "has been in"
    means is the record the engine can answer honestly rather than the one
    that would be nicest to have: the room CARRIES PROSE (the live `desc`,
    or `planned.resolved`, which `_prepare_room_registry` maintains from it
    every commit) or a body stands in it NOW. This engine keeps no durable
    "was ever occupied" mark to ask, and prose is the closest honest
    proxy -- a stub is furnished the beat a beat reaches it, and a memory
    is only ever written under the name of a room its owner was standing
    in, so the rooms whose names memory retrieval depends on
    (`memory_retrieval`, which matches `memories.location` by NAME) are
    exactly the rooms this refuses to rename.
    """
    from core.db import wget

    # LIVE ROWS ONLY, ON PURPOSE (review 2026-09-07, Section I residual on
    # B8/A55, rework). Both tables below come from `registry_rows`, which
    # filters `retired_turn_id IS NULL`, and a claim resolves a HOLDER and an
    # AXIS: a retired room holds no frontier and is nobody's neighbour, so a
    # ruin must not be claimable -- claiming it would rename a spent identity
    # into a live plan, which is the revive this residual closed one door
    # further on. The other half, a plan whose own uid folds onto a ruin's
    # spelling, is not a claim at all and is settled where the write happens:
    # `plant_structure` reserves every retired spelling before it upserts.
    specs = _planned_specs(cid)
    aliases_by_uid = _registry_aliases(cid)
    if scene is None:
        scene = wget(cid, "scene", {}) or {}
    scene = scene if isinstance(scene, dict) else {}
    live = scene.get("rooms") or {}
    occupied = {str(r) for r in (scene.get("positions") or {}).values()
                if str(r)}
    rooms = {str(k): dict(v) for k, v in (rooms or {}).items()
             if isinstance(v, dict)}
    errors, records, rows, work = [], [], {}, {}
    rename, filled, refused = {}, set(), []

    def _live_prose(uid):
        room = live.get(uid)
        if not isinstance(room, dict):
            return False
        return bool(str(room.get("desc") or room.get("description")
                        or "").strip())

    for key in sorted(rooms):
        raw = rooms[key].pop("claims", None)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            errors.append("room %r claims a frontier space that is not a "
                          "{room, axis}" % key)
            refused.append(key)
            continue
        holder = str(raw.get("room") or "")
        axis = str(raw.get("axis") or "")
        if not holder or not axis:
            errors.append("room %r claims a frontier space without naming "
                          "both the room it hangs off and the axis it fills"
                          % key)
            refused.append(key)
            continue
        if holder not in specs:
            errors.append("room %r claims the space %r off %r, which holds no "
                          "plan; a frontier space hangs off a planned room"
                          % (key, axis, holder))
            refused.append(key)
            continue
        hspec = work.get(holder) or specs[holder][1]
        standing = hspec.get("frontier_standing")
        standing = dict(standing) if isinstance(standing, dict) else {}
        open_axes = [str(a) for a in hspec.get("frontier") or () if str(a)]
        if (holder, axis) in filled:
            errors.append("room %r claims the space %r off %r, which an "
                          "earlier room of this plan already fills; a place "
                          "cannot be two things" % (key, axis, holder))
            refused.append(key)
            continue
        if axis in standing:
            target = str(standing[axis])
            stub_name, stub_spec = specs.get(target, ("", None))
            if not isinstance(stub_spec, dict):
                errors.append("room %r claims the space %r off %r, whose room "
                              "%r the plan no longer holds"
                              % (key, axis, holder, target))
                refused.append(key)
                continue
            if not stub_spec.get("provisional"):
                errors.append("room %r claims the space %r off %r, which %r "
                              "already fills; a place cannot be two things"
                              % (key, axis, holder, target))
                refused.append(key)
                continue
            if target in rooms and target != key:
                errors.append("room %r claims the space %r off %r, whose room "
                              "%r this same plan also plants"
                              % (key, axis, holder, target))
                refused.append(key)
                continue
            filled.add((holder, axis))
            rename[key] = target
            was = str(stub_name or target)
            wants = str(rooms[key].get("name") or key)
            visited = target in occupied or bool(stub_spec.get("resolved")) \
                or _live_prose(target)
            keep = bool(visited and was and wants != was)
            # The stub's ways out survive a claim that does not name them.
            edges = {str(e.get("to")): dict(e)
                     for e in stub_spec.get("adjacent") or ()
                     if isinstance(e, dict) and e.get("to")}
            for edge in rooms[key].get("adjacent") or ():
                if isinstance(edge, dict) and edge.get("to"):
                    edges[str(edge["to"])] = dict(edge)
            rooms[key]["adjacent"] = list(edges.values())
            if isinstance(stub_spec.get("frontier_of"), dict):
                rooms[key]["frontier_of"] = dict(stub_spec["frontier_of"])
            rows[target] = {
                "name": was if keep else wants,
                "aliases": list(dict.fromkeys(
                    [*aliases_by_uid.get(target, ()), was, wants,
                     target.replace("_", " ")])),
            }
            records.append({
                "room": target, "holder": holder, "axis": axis,
                "stub": target, "was": was, "name": was if keep else wants,
                "renamed": bool(not keep and wants != was),
                "kept_name": keep, "visited": bool(visited)})
            continue
        if axis in open_axes:
            # NOTHING STANDS THERE YET, and the plan's own room fills the
            # space directly: no stub, no rename, and the axis is spent the
            # way a mint spends it.
            filled.add((holder, axis))
            wspec = work.setdefault(holder, copy.deepcopy(specs[holder][1]))
            wspec["frontier"] = [str(a) for a in wspec.get("frontier") or ()
                                 if str(a) and str(a) != axis]
            wstanding = wspec.get("frontier_standing")
            wstanding = dict(wstanding) if isinstance(wstanding, dict) else {}
            wstanding[axis] = key
            wspec["frontier_standing"] = wstanding
            hedges = {str(e.get("to")): dict(e)
                      for e in wspec.get("adjacent") or ()
                      if isinstance(e, dict) and e.get("to")}
            hedges.setdefault(key, {"to": key, "barrier": "open_door",
                                    "axis": axis})
            wspec["adjacent"] = list(hedges.values())
            redges = {str(e.get("to")): dict(e)
                      for e in rooms[key].get("adjacent") or ()
                      if isinstance(e, dict) and e.get("to")}
            redges.setdefault(holder, {"to": holder, "barrier": "open_door"})
            rooms[key]["adjacent"] = list(redges.values())
            records.append({
                "room": key, "holder": holder, "axis": axis, "stub": "",
                "was": "", "name": str(rooms[key].get("name") or key),
                "renamed": False, "kept_name": False, "visited": False})
            continue
        held = sorted(set(open_axes) | set(standing))
        errors.append("room %r claims the space %r off %r, which holds no "
                      "such frontier; %r holds %s"
                      % (key, axis, holder, holder,
                         ", ".join(repr(a) for a in held) or "no frontier"))
        refused.append(key)

    for old, new in rename.items():
        rooms[new] = rooms.pop(old)
    if rename:
        for room in rooms.values():
            for edge in room.get("adjacent") or ():
                if isinstance(edge, dict) and str(edge.get("to")) in rename:
                    edge["to"] = rename[str(edge["to"])]
    return (rooms,
            {"rows": rows, "holders": work, "claims": records,
             "refused": refused},
            errors)


def apply_frontier_mutations(cid, turn_id, mutations):
    """Write prepared frontier rows; call only inside the scene transaction.

    A MINT DOES NOT UN-RETIRE (review 2026-09-07, Section I residual on
    B8/A55). This upsert used to set `retired_turn_id=NULL` on conflict, so
    the two rows it writes -- the new stub and the holder whose spent axis it
    is recording -- could each revive a retirement the registry is the
    authority for. `prepare_frontier_expansion` now reserves every retired
    spelling so the stub cannot land on one; leaving the revive in place
    would keep a second way to the same defect, and the holder is a live room
    whose row was never retired anyway.

    THE HOLDER'S PLAN AS IT STANDS NOW, NOT AS IT WAS READ. The expansion is
    prepared before the lock and the plan is written out of band meanwhile:
    the layout tier lays a building onto its rows between any two commits.
    Writing back the holder's whole payload as prepared took a solved hall's
    site off it while its kitchen and loft kept theirs, and the building was
    refused for good (review of 2026-10-08, R2-4; the registry projection's
    own case was F5). So a holder's row is re-read here and only what the
    expansion owns is laid onto it (`_expanded`); a stub this expansion
    minted, which no row held when it was prepared, is written whole.
    """
    from core.db import q, qtx

    for row in mutations or ():
        payload = row.get("payload") or {}
        if isinstance(row.get("expansion"), dict):
            current = q("SELECT payload FROM room_registry WHERE chat_id=? AND "
                        "room_uid=?", (cid, row["room_uid"]), one=True)
            stored = _payload(current) if current is not None else None
            if isinstance(stored, dict) and isinstance(stored.get("planned"), dict):
                payload = _expanded(stored, row["expansion"])
        qtx(
            "INSERT INTO room_registry"
            "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,payload,"
            "created_turn_id,retired_turn_id) VALUES(?,?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
            "owning_book_id=excluded.owning_book_id,"
            "parent_entity=excluded.parent_entity,name=excluded.name,"
            "aliases=excluded.aliases,payload=excluded.payload",
            (cid, row["room_uid"], row.get("owning_book_id"),
             row.get("parent_entity"), row["name"],
             json.dumps(row.get("aliases") or []),
             json.dumps(payload, ensure_ascii=False), turn_id),
        )


def _expanded(stored, expansion):
    """A holder's stored registry payload with what its frontier expansion
    owns laid onto it (`apply_frontier_mutations`): the edges it drew
    appended, the axes it spent gone from the frontier, and what now stands
    in each added to `frontier_standing`. On a row nobody wrote since it was
    prepared this is exactly the payload the expansion prepared."""
    payload = dict(stored)
    planned = dict(payload["planned"])
    planned["adjacent"] = list(planned.get("adjacent") or []) + [
        dict(edge) for edge in expansion.get("adjacent") or ()]
    was = [str(x) for x in expansion.get("frontier_was") or ()]
    kept = [str(x) for x in expansion.get("frontier") or ()]
    now = [str(x) for x in planned.get("frontier") or () if str(x)]
    if now == was:
        planned["frontier"] = kept
    else:
        spent = set(was) - set(kept)
        planned["frontier"] = [x for x in now if x not in spent]
    standing = dict(planned.get("frontier_standing") or {}) \
        if isinstance(planned.get("frontier_standing"), dict) else {}
    standing.update(expansion.get("standing") or {})
    if standing:
        planned["frontier_standing"] = standing
    payload["planned"] = planned
    return payload


def structure_warnings(structure, rooms, known=()):
    """What is wrong with this planned skeleton, in author-facing words.

    `known` is every room that exists OUTSIDE the plan -- in practice the live
    scene's ids. A PLAN MAY NAME A ROOM THAT ALREADY EXISTS: what this warning
    is for is a plan that names a room nothing can be, and a live room is the
    least unknown thing in the scene. It joins the plan too, so a skeleton
    hanging off an existing room is connected rather than "disconnected".

    Measured 2026-09-05 (PE8, Flat 4B): the Writers' Room planned
    `stairwell_fourth_to_third` and `flat_4a_hallway`, each declaring
    `adjacent: [{to: landing}]`; both landed, the landing carried both
    reciprocals, the plan WORKED -- and `inspect_contradictions.structure`
    reported three contradictions for it, so the tool that exists to show the
    Room its errors showed it errors it had not made.
    """
    structure = normalize_structure(structure)
    rooms = rooms if isinstance(rooms, dict) else {}
    known = {str(x) for x in known or ()} - set(rooms)
    warnings = []
    if not rooms:
        return [f"{structure['key']}: structure has no planned rooms"]
    for uid, room in rooms.items():
        if str(room.get("desc") or room.get("description") or "").strip():
            warnings.append(f"{uid}: planned room contains prose")
        destinations = [str(e.get("to")) for e in room.get("adjacent") or ()
                        if isinstance(e, dict) and e.get("to")]
        for target in destinations:
            if target not in rooms and target not in known:
                warnings.append(f"{uid}: planned edge targets unknown room {target}")
        if set(destinations) & set(str(x) for x in room.get("frontier") or ()):
            warnings.append(f"{uid}: frontier label collides with a real edge")
        for axis in room.get("frontier") or ():
            refusal = frontier_refusal(axis, allow_bearing=True)
            if refusal:
                warnings.append(f"{uid}: {refusal}")
    # Undirected reach is sufficient for author diagnostics; runtime pathing
    # will still enforce each authored barrier direction.
    # A live room the plan hangs off is a NODE of the graph, not a hole in
    # it: two planned rooms that both open onto the landing are joined
    # through it.
    nodes = set(rooms) | known
    start, seen = next(iter(rooms)), set()
    stack = [start]
    reverse = {}
    for uid, room in rooms.items():
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict) and str(edge.get("to")) in nodes:
                reverse.setdefault(str(edge["to"]), set()).add(str(uid))
    while stack:
        uid = stack.pop()
        if uid in seen:
            continue
        seen.add(uid)
        room = rooms.get(uid) or {}
        stack.extend(str(e.get("to")) for e in room.get("adjacent") or ()
                     if isinstance(e, dict) and str(e.get("to")) in nodes)
        stack.extend(reverse.get(uid, ()))
    if len(seen & set(rooms)) != len(rooms):
        warnings.append(f"{structure['key']}: planned skeleton is disconnected")
    return warnings


__all__ = [
    "FRONTIER_NAME_WORDS", "GEOMETRY_FIELDS", "LAID_LOOKS_KEY",
    "LAYOUT_ANCHOR_FIELDS", "LAYOUT_EDGE_FIELDS", "LAYOUT_PLAN_PREFIX",
    "PLAN_SEEDED_FIELDS", "STRUCTURES_KEY", "apply_planned_layout",
    "apply_solved_plans", "planned_anchors", "planned_seed",
    "write_planned_layout",
    "apply_frontier_mutations", "claim_frontier_spaces",
    "composed_scene", "frontier_refusal", "frontier_spaces",
    "planned_geometry",
    "materialize_planned_fringe", "prepare_frontier_expansion",
    "mint_frontier", "normalize_structure", "normalize_structures",
    "planned_context",
    "registry_rows", "registry_rows_for_update", "retired_room_spellings",
    "plant_structure", "skeleton_rooms", "structure_warnings",
]
