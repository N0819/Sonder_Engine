"""Production seam for the pure institution/upkeep simulator.

The ``charter_*`` package deliberately owns no I/O.  This module owns the
small amount of I/O required to make it diegetic: frame-scoped state, one
out-of-band catch-up job per off-screen epoch, rollback/epoch guards, and
stable consequence rows on the existing scheduled-event rail.

Definitions remain explicit author input.  Merely enabling off-screen life
does not invent an institution; a stored registry with at least one item is
the opt-in.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import uuid

from core import jobs
from core.logging_utils import logger
from world.charter import (normalize_charter, run, trigger_view,
                          trigger_warnings)
from world.charter_news import WITNESSABLE
from world.mechanics import stable_event_key


CHARTERS_KEY = "charters"
REGISTRY_VERSION = 1
DEFAULT_WINDOW_HOURS = 4.0
#: How much simulated time one IN-PLAY catch-up may burn. A story returning to
#: a charter after a long absence advances it inside a turn's wall clock, so
#: this is a latency bound and stays where it was.
MAX_CATCHUP_HOURS = 720.0

#: How much history an author may ask a PRE-STORY run to live through. This
#: shared the number above until it was measured, and the sharing was silent
#: truncation: `min(MAX_CATCHUP_HOURS, horizon_hours)` handed a request for a
#: year back a month with no warning. The two are not the same question -- a
#: presim happens once, before anybody is waiting on a turn, and it costs
#: ~1.8 ms per simulated hour on a 40-body charter, so a full year is about
#: 16 seconds of arithmetic and 8 KB of familiarity. Two years is the ceiling
#: rather than the intent; the default horizon is unchanged.
MAX_PRESIM_HOURS = 17520.0

DEFAULT_PRESIM_TAIL_HOURS = 96.0

#: Below this horizon a presim stays in-process. Forking costs a pickled
#: registry item each way, which is worth paying for a month of simulated time
#: across several institutions and not worth it for an afternoon across two.
PARALLEL_PRESIM_HOURS = 168.0
GENERATION_LORE_LIMIT = 48
CAST_HISTORY_REQUEST_CAP = 16

#: Different institutions sharing one place exchange through a few actual
#: bodies, never by merging registers or broadcasting to both populations.
CROSS_CHARTER_GOSSIP_CAP = 8


def _window_hours(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = DEFAULT_WINDOW_HOURS
    return max(0.25, min(24.0, value))


#: The stores that belong to a PERSON rather than to an institution, each one
#: keyed directly by body. A charter used to hold these, which meant a person
#: was OWNED by the institution that employed them -- addressed as
#: ``(charter_key, body_key)`` and stored inside its blob. Two things follow
#: that are plainly wrong and the owner named both: a hermit the Director
#: invented needs an institution to exist in, and somebody moving town, joining
#: a crew or transferring ship has to be re-keyed across two blobs dragging
#: thirteen stores behind them. Holding posts in two institutions could not be
#: expressed at all.
#:
#: So a charter now EMPLOYS people it does not own. These live at registry
#: level keyed by body; the institution keeps `posts`, `upkeeps`, `watch`,
#: `roster`, `decisions`, `economy` and its own clock, plus `members` -- the
#: link. A hermit is a person with no membership. A transfer is a membership
#: change with identity, memory and relationships untouched.
#:
#: NOT in here, with reasons. `commitments` is keyed by promise id and names
#: two parties, so it is relational rather than person-scoped and moving it
#: means deciding which institution owns a cross-charter promise. `politics`
#: nests `regard` (pairwise, person) inside `blame`/`standing` (institution).
#: Both are registered at `docs/UNBUILT.md` §1.99d rather than half-moved.
PERSON_STORES = (
    "bodies", "minds", "needs", "feel", "experiences", "served_beside",
    "stood", "judgments", "ties", "marks", "habit_runs", "travelled",
    "heard_blame",
)


def person_id(charter_key, body_key):
    """The registry-wide address of one person.

    QUALIFIED, BECAUSE A BODY KEY IS NOT UNIQUE. Body keys are minted per
    institution -- two independently generated charters in the same story both
    produce `tech:0001`, and a flat person store keyed by body alone silently
    has the second overwrite the first. Measured the moment this was tried: a
    second generated location came back with every person store empty and its
    clock at zero, because both crews claimed the same keys.

    The institution is in the ADDRESS, not in the person. A transfer re-keys
    the address and moves the same objects, which is why what somebody
    remembers survives it.
    """
    return "%s/%s" % (str(charter_key), str(body_key))


def _body_of(pid):
    """The intra-charter body key inside a person id."""
    return str(pid).split("/", 1)[-1]


def _split_person_state(state, charter_key=""):
    """Take a whole charter state apart: (institution, {person_id: person})."""
    institution = {k: v for k, v in state.items() if k not in PERSON_STORES}
    bodies = state.get("bodies") or {}
    people = {}
    for key in bodies:
        person = {"bodies": copy.deepcopy(bodies[key])}
        for store in PERSON_STORES:
            if store == "bodies":
                continue
            held = state.get(store)
            if isinstance(held, dict) and key in held:
                person[store] = copy.deepcopy(held[key])
        people[person_id(charter_key, key)] = person
    return institution, people


def _join_person_state(institution, people, members):
    """Put one back together in the shape `charter_run.step` already takes.

    THE WHOLE POINT OF DOING IT THIS WAY. `step` and every function under it
    receive exactly what they received before -- dicts keyed by body -- so the
    two hundred reader sites across this package did not have to move. Only
    the OWNERSHIP moved, which is the thing that was wrong.
    """
    state = copy.deepcopy(institution)
    for store in PERSON_STORES:
        state[store] = {}
    for pid in members:
        person = people.get(str(pid))
        if not isinstance(person, dict):
            continue
        body_key = _body_of(pid)
        for store, held in person.items():
            if store in PERSON_STORES:
                state[store][body_key] = copy.deepcopy(held)
    return state


def _stored_shape(registry):
    """The on-disk registry: people once, institutions naming their members."""
    people = dict(registry.get("people") or {})
    items = {}
    for key, item in (registry.get("items") or {}).items():
        institution, held = _split_person_state(item.get("state") or {}, key)
        people.update(held)
        institution["members"] = sorted(held)
        items[str(key)] = dict(item, state=institution)
    return {"version": registry.get("version", REGISTRY_VERSION),
            "items": items, "people": people}


#: The charter a person belongs to when they belong to no institution.
#: Not a fake institution of one -- an institution of NONE: no posts, no
#: upkeeps, no watch bill, nothing to stand. It exists because a person still
#: has to be somewhere for the simulation to advance their needs, their
#: feeling and their acquaintance, and `charter_run.step` advances a charter's
#: MEMBERS. A hermit joins it and stands nothing; that is the whole of what
#: having no institution means here.
AMBIENT_CHARTER = "ambient"


def _ambient_body_key(name):
    """A stable key for a person the story named but no generator minted."""
    slug = re.sub(r"[^a-z0-9]+", "_",
                  " ".join(str(name or "").split()).casefold()).strip("_")
    digest = hashlib.sha256(str(name or "").encode("utf-8")).hexdigest()[:6]
    return "%s:%s" % (slug[:32] or "person", digest)


def ensure_ambient_bodies(cid, wanted, frame_id=None):
    """Give every named background person a body. Returns ``{name: ref}``.

    WHY THIS EXISTS. Measured across the corpus: 84 tracked background
    presences carried no charter body against 14 that did, so 86% of the
    people a story actually populates itself with reached none of the memory,
    familiarity, ties, marks or history-reading volition Charter was built to
    give them. They were a name in a dict, invented fresh each time, keyed by
    DISPLAY NAME -- which two people in one story may share.

    A presence minted here is an ordinary person from that moment: it
    accumulates a past, forms acquaintance, can be transferred to a real
    institution when the story gives it one, and promotes through the single
    path every other body promotes through. Nothing about it is a second tier.

    Bodies only, and no cognition is invented: a fresh person knows nobody and
    remembers nothing, which is true of somebody the story has only just
    introduced. What they come to know arrives through the same channels as
    everybody else's.
    """
    # The common turn mints nobody, so the alias lookup runs on the shared
    # cached registry; only the first actually-fresh name pays for a private
    # copy to mutate (`registry_for_update` -- the shared object is
    # read-only). Both shapes hold the same bodies, so a lookup answered by
    # the cache is answered identically by the private copy.
    registry = registry_for(cid, frame_id)
    known = {}
    for charter_key, item in (registry.get("items") or {}).items():
        for body_key, body in ((item.get("state") or {}).get("bodies")
                               or {}).items():
            for alias in (str(body.get("name") or ""), str(body_key)):
                if alias:
                    known.setdefault(alias.casefold(),
                                     {"charter": charter_key, "body": body_key})
    fresh = {}
    private = None
    for row in wanted or ():
        name = " ".join(str((row or {}).get("name") or "").split())
        if not name:
            continue
        hit = known.get(name.casefold())
        if hit:
            fresh[name] = dict(hit)
            continue
        if private is None:
            private = registry_for_update(cid, frame_id)
        body_key = _ambient_body_key(name)
        place = str((row or {}).get("place") or "")
        item = private.setdefault("items", {}).setdefault(
            AMBIENT_CHARTER, {"state": {
                "key": AMBIENT_CHARTER, "posts": {}, "upkeeps": {},
                "priority": [], "bodies": {}}})
        state = item.setdefault("state", {})
        state.setdefault("bodies", {})[body_key] = {
            "key": body_key, "name": name, "place": place,
            "berth": place, "competence": {}, "available": True,
        }
        known[name.casefold()] = {"charter": AMBIENT_CHARTER, "body": body_key}
        fresh[name] = {"charter": AMBIENT_CHARTER, "body": body_key}
    if fresh:
        # The pre-cache code saved whenever any wanted name RESOLVED, mint
        # or not, and that save re-applies the identity-reservation
        # subtraction; keep that exact write so nothing about the stored
        # blob's history changes shape.
        if private is None:
            private = registry_for_update(cid, frame_id)
        save_registry(cid, private, frame_id)
    return fresh


def transfer_person(registry, body_key, to_charter, *, place=None):
    """Move one person between institutions. Identity is not touched.

    THE OPERATION THE OLD SHAPE COULD NOT EXPRESS. A person used to live
    inside the blob of the institution that employed them, so joining a crew,
    moving town or transferring ship meant re-keying them across two blobs
    with thirteen stores behind them -- and anything that missed a store lost
    that part of the person silently. Here it is a membership change: what
    they remember, who they know, what they are owed and how they feel are the
    same objects before and after, because they were never the institution's.

    ``to_charter`` of None makes them a hermit: employed nowhere, still a
    person. Returns the registry.
    """
    body_key = str(body_key)
    items = registry.setdefault("items", {})
    person = None
    # Lift them out of wherever they are now.
    for from_key, item in items.items():
        state = item.get("state") or {}
        if body_key not in (state.get("bodies") or {}):
            continue
        _institution, held = _split_person_state(state, from_key)
        person = held.get(person_id(from_key, body_key))
        registry.setdefault("people", {}).pop(
            person_id(from_key, body_key), None)
        for store in PERSON_STORES:
            if isinstance(state.get(store), dict):
                state[store].pop(body_key, None)
        state["members"] = sorted(state.get("bodies") or {})
    if person is None:
        person = (registry.get("people") or {}).get(body_key)
    if person is None:
        raise ValueError(f"no such person: {body_key}")
    person = copy.deepcopy(person)
    if place is not None:
        person.setdefault("bodies", {})["place"] = str(place)
    if to_charter is None:
        # A hermit is addressed by body alone: no institution is in the name,
        # because none is in their life.
        registry.setdefault("people", {})[body_key] = person
        return registry
    registry.setdefault("people", {})[person_id(to_charter, body_key)] = person
    item = items.setdefault(str(to_charter), {"state": {}})
    state = item.setdefault("state", {})
    for store, held in person.items():
        if store in PERSON_STORES:
            state.setdefault(store, {})[body_key] = copy.deepcopy(held)
    state["members"] = sorted(state.get("bodies") or {})
    return registry


def charter_view(registry, charter_key):
    """One institution and the people it employs, ready to simulate."""
    item = (registry.get("items") or {}).get(str(charter_key)) or {}
    return _join_person_state(
        item.get("state") or {}, registry.get("people") or {},
        (item.get("state") or {}).get("members") or ())


def absorb_view(registry, charter_key, after):
    """Scatter a simulated window back: people to the registry, the rest here.

    A body the window MOVED to another institution is not lost -- the person
    keeps their whole self at registry level and only `members` changes.
    """
    item = (registry.setdefault("items", {}).setdefault(
        str(charter_key), {"state": {}}))
    institution, people = _split_person_state(after, charter_key)
    registry.setdefault("people", {}).update(people)
    institution["members"] = sorted(people)
    item["state"] = institution
    return registry


def normalize_registry(stored, reservation=None):
    """Normalize author definitions and runtime markers into one JSON shape.

    ``reservation`` is the story's registered identity forms, passed by every
    caller that has a story in reach (`save_registry`). Normalization is what
    mints a name for a body that arrived without one, so a registry saved by
    hand or by an older generation goes through the same refusal the
    generator does.
    """
    stored = stored if isinstance(stored, dict) else {}
    raw_items = stored.get("items")
    if not isinstance(raw_items, dict):
        # Authoring convenience: a bare ``{key: charter}`` map is accepted.
        raw_items = {
            key: value for key, value in stored.items()
            if key not in {"version", "recent_events"}
            and isinstance(value, dict)
        }
    items = {}
    # MIGRATION HAPPENS HERE, and only here. A registry saved before people
    # were hoisted holds them inside each item's state; one saved after holds
    # them at registry level with `members` naming who works where. Joining
    # first makes both shapes converge on the same whole state, so
    # `normalize_charter` still sees what it has always seen and the lift is
    # idempotent -- read an old blob, get a new one, read it again, get the
    # same one.
    incoming_people = stored.get("people")
    incoming_people = incoming_people if isinstance(incoming_people, dict) else {}
    employed = set()
    for key, raw in raw_items.items():
        raw = raw if isinstance(raw, dict) else {}
        state = raw.get("state") if isinstance(raw.get("state"), dict) else raw
        if incoming_people and not (state.get("bodies") or {}):
            state = _join_person_state(
                state, incoming_people, state.get("members") or ())
        state = normalize_charter(state, reservation)
        state["key"] = str(state.get("key") or key)
        last = raw.get("last_elapsed_seconds")
        try:
            last = None if last is None else max(0.0, float(last))
        except (TypeError, ValueError):
            last = None
        # WORKING SHAPE IS JOINED, STORED SHAPE IS SPLIT. Every reader in this
        # package -- and there are around two hundred -- takes a charter state
        # holding its own people, and rewriting them all to gather first would
        # be a large change for no behavioural gain. So the join is what a
        # caller gets and `save_registry` does the split, which makes the ITEM
        # authoritative within a session and `people` authoritative on disk.
        # The round trip is what carries identity, not the in-memory shape.
        # MEMBERS, NOT A MIRROR. Splitting every person out here to build a
        # `people` copy cost a deep copy of thirteen stores per body on EVERY
        # READ -- measured at 6.5s for a 307-body town, paid by each of the
        # half-dozen per-room readers a turn makes, which took a turn from
        # ~200s to never reaching its first model call. The joined item IS the
        # working shape and already holds these people; only `save_registry`
        # needs the split, and `_stored_shape` does it there.
        state["members"] = sorted(state.get("bodies") or {})
        employed.update(person_id(key, body) for body in state["members"])
        items[str(key)] = {
            "state": state,
            "window_hours": _window_hours(raw.get("window_hours")),
            "last_elapsed_seconds": last,
            "last_epoch_id": str(raw.get("last_epoch_id") or ""),
        }
    # Older development snapshots may contain ``recent_events``. Deliberately
    # discard it: incidents have one durable home, scheduled_events ->
    # world_events. The Charter registry stores current simulation state only.
    # Unemployed people survive normalization untouched -- nothing in `items`
    # refers to them, which is exactly what having no institution means, and
    # they are the only reason a read carries `people` at all.
    people = {str(key): person for key, person in incoming_people.items()
              if str(key) not in employed}
    return {"version": REGISTRY_VERSION, "items": items, "people": people}


# ---------------------------------------------------------------- job store

#: Stamped on every generation this process starts. A `running` job carrying a
#: DIFFERENT token was orphaned when that process died, which is an
#: interruption -- detected exactly, with no staleness timeout to tune. The
#: `lore_gen_jobs` pattern (`story/importers.py`), which exists for the same
#: reason: a multi-call generation can be lost to a dropped stream, an
#: exhausted retry budget, a closed tab or a restart, and before it there was
#: nothing to recover.
_GEN_OWNER = uuid.uuid4().hex

#: Chat-global world key. NOT a table, deliberately. A job is per-chat, and a
#: `world` row already rides `chat_archive.WORLD_TABLES`, the checkpoint
#: snapshot, branch cloning and story delete -- four of the eight items on
#: `docs/guides/DATABASE.md`'s schema-change checklist, for free and correctly.
#: `lore_gen_jobs` is a table because it is keyed per-LOREBOOK, which `world`
#: cannot express.
LIVED_LOCATION_JOB_KEY = "lived_location_job"

#: The stages, in order. `planned` is the boundary that matters: everything
#: before it is pure and replays for free, everything after it has written to
#: the world.
JOB_STAGES = ("planning", "planned", "planted", "presimmed", "done")

#: The stages a rerun cannot safely follow. By the time any of these is
#: recorded, rooms may already exist and the registry may already be saved --
#: and `_remap_generated_town` reads LIVE state, so a second run over the top
#: of an unfinished one plants a second town.
PAST_BOUNDARY_STAGES = frozenset({"planting", "planted", "presimmed"})


def _request_digest(cid, request, frame_id):
    """A stable fingerprint of what was asked for.

    A stored plan may only be reused for the SAME request. Sorting keys makes
    it independent of dict order, and the model output is excluded because it
    is what the digest identifies rather than part of the question.
    """
    payload = json.dumps(
        {"cid": int(cid), "frame": frame_id,
         "request": request if isinstance(request, dict) else {}},
        sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def lived_location_job(cid):
    """The stored job for this chat, or `None`.

    `interrupted` is DERIVED rather than stored: a `running` row whose owner
    is not this process can only be a crash or a restart, and deriving it
    means a job cannot be left claiming to be live by a process that is gone.
    """
    from core.db import wget

    stored = wget(int(cid), LIVED_LOCATION_JOB_KEY, None)
    if not isinstance(stored, dict) or not stored.get("job_id"):
        return None
    job = dict(stored)
    if job.get("status") == "running" and job.get("owner") != _GEN_OWNER:
        job["status"] = "interrupted"
        job["error"] = job.get("error") or (
            "Interrupted: the server stopped while this generation was "
            "running.")
    return job


def _save_job(cid, job):
    from core.db import wset

    job = dict(job)
    job["updated"] = job.get("updated") or 0.0
    wset(int(cid), LIVED_LOCATION_JOB_KEY, job)
    return job


def clear_lived_location_job(cid):
    """Forget the job. Called on success, and by an author abandoning one."""
    from core.db import wset

    wset(int(cid), LIVED_LOCATION_JOB_KEY, {})


#: Everything the pure prefix produces that anything after the boundary needs.
#: Stored whole, because a resume that restored only SOME of it would carry the
#: town from one run and the lore provenance from another.
_ARTIFACT_FIELDS = ("town", "required_rooms_added", "lore_manifest",
                    "source_book", "owning_book", "horizon", "wants_history")


def _resumable_plan(cid, digest):
    """The stored pure prefix this call may reuse instead of paying again.

    Only from a job for the SAME request that reached `planned` and no
    further. Past that the run has written to the world, and the caller
    refuses outright rather than resuming -- see `PAST_BOUNDARY_STAGES`.
    """
    job = lived_location_job(cid)
    if not job or job.get("digest") != digest:
        return None, job
    artifact = job.get("artifact")
    if job.get("stage") != "planned" or not isinstance(artifact, dict):
        return None, job
    if not isinstance(artifact.get("town"), dict):
        return None, job
    return copy.deepcopy(artifact), job


# ---- shared registry cache -------------------------------------------------
# One parsed+normalized registry per (chat, storage row), shared by every
# reader until a write lands. Motivating measurement (2026-08-28, generated
# market town, 307 bodies, chat 95): the stored blob is 41.4MB, one
# fetch+parse+normalize costs ~0.95s joined / ~2.3s split, and one live turn
# read it 21 times (registry_for x15, chatter_inputs x6) with zero
# intervening writes -- 22.2s of a 63.4s turn re-deriving one unchanged
# object. Copying instead of sharing does not work: copy.deepcopy of the
# normalized registry measured 2.5s, MORE than a fresh parse.
#
# THE RETURNED OBJECT IS SHARED AND READ-ONLY. A caller that intends to
# mutate uses `registry_for_update`, which pays the private parse the old
# `registry_for` always paid -- otherwise a mutation abandoned without
# `save_registry` (previously discarded with the private copy) would leak
# into every later reader's view. Validation is `core.db.world_read_token`:
# `wset` is the world-row write chokepoint and bumps the token; database
# swaps, checkpoint restores and raw world DELETEs bump the coarse epoch
# inside it. Two entries, not one, so a second chat polled mid-turn (the
# charters editor, a second story) cannot thrash the hot chat's entry.
_REGISTRY_CACHE = {}
_REGISTRY_CACHE_CAP = 2
_REGISTRY_CACHE_LOCK = threading.Lock()


def cached_registry(cid):
    """The AMBIENT frame's normalized registry: shared, read-only.

    Reads under whatever frame the pipeline has active, exactly as a bare
    `wget` does -- `chatter_inputs` needs that (a flashback's observer must
    hear the flashback's charters), while `registry_for` pins its frame
    around this. Mutating the result is a bug; see the cache comment.
    """
    from core.db import wget, world_read_token

    storage_key, token = world_read_token(cid, CHARTERS_KEY)
    cache_key = (int(cid), storage_key)
    with _REGISTRY_CACHE_LOCK:
        entry = _REGISTRY_CACHE.get(cache_key)
        if entry is not None and entry[0] == token:
            return entry[1]
    # Parse outside the lock: a second thread racing here recomputes the
    # same value, which costs seconds once and corrupts nothing. The token
    # was read BEFORE the fetch, so a write landing during the fetch leaves
    # this entry already-stale rather than wrongly-fresh.
    registry = normalize_registry(wget(cid, CHARTERS_KEY, {}) or {})
    with _REGISTRY_CACHE_LOCK:
        if cache_key not in _REGISTRY_CACHE \
                and len(_REGISTRY_CACHE) >= _REGISTRY_CACHE_CAP:
            _REGISTRY_CACHE.pop(next(iter(_REGISTRY_CACHE)))
        _REGISTRY_CACHE[cache_key] = (token, registry)
    return registry


def registry_for(cid, frame_id=None):
    """One frame's normalized registry: SHARED and READ-ONLY.

    Every reader this turn gets the same object (see the cache comment
    above). A caller that mutates what it got must use
    `registry_for_update` instead.
    """
    from core.db import active_frame_id

    token = active_frame_id.set(frame_id)
    try:
        return cached_registry(cid)
    finally:
        active_frame_id.reset(token)


def registry_for_update(cid, frame_id=None):
    """A PRIVATE normalized registry for a caller that will mutate it.

    The pre-cache `registry_for`, byte for byte: a fresh parse whose
    mutations stay invisible until `save_registry` lands them -- and are
    discarded with the object when the caller abandons them, which several
    writers (carrier ingest, caravan trade, public evidence) rely on.
    """
    from core.db import wget_for_frame
    return normalize_registry(
        wget_for_frame(cid, CHARTERS_KEY, frame_id, {}) or {})


def save_registry(cid, stored, frame_id=None):
    """Persist an explicitly authored registry in one temporal frame.

    The one write chokepoint for the registry, and therefore where the
    story's registered identity forms are subtracted from every charter's
    naming law before it lands. `story/naming.py` reads a stored Charter law
    as one of its lanes, so a law persisted holding a registered mind's
    address would keep offering it to readers that never saw this generation.
    """
    from core.db import wset_for_frame
    from story.naming import story_identity_reservation
    normalized = normalize_registry(
        stored, story_identity_reservation(cid, _stored_naming_laws(stored)))
    # THE SPLIT LANDS HERE, at the one write chokepoint. On disk a person is
    # stored once at registry level and an institution stores only who it
    # employs, so a body carries its identity, memory and relationships across
    # a transfer instead of being re-keyed with thirteen stores behind it.
    # Rebuilt from the ITEMS rather than from the incoming `people`, because
    # the joined item state is what the session has been mutating.
    stored_shape = _stored_shape(normalized)
    wset_for_frame(cid, CHARTERS_KEY, stored_shape, frame_id)
    # The caller gets the JOINED shape it handed in, not the stored one, so a
    # save round-trips against `registry_for` and no caller has to know which
    # side of the chokepoint it is on.
    return normalized


def _stored_naming_laws(stored):
    """Every naming law a registry-shaped blob carries, in either the
    normalized or the bare authoring shape. Read only for title vocabulary."""
    stored = stored if isinstance(stored, dict) else {}
    items = stored.get("items")
    if not isinstance(items, dict):
        items = {key: value for key, value in stored.items()
                 if key not in {"version", "recent_events"}
                 and isinstance(value, dict)}
    laws = []
    for raw in items.values():
        raw = raw if isinstance(raw, dict) else {}
        state = raw.get("state") if isinstance(raw.get("state"), dict) else raw
        if isinstance(state.get("naming"), dict):
            laws.append(state["naming"])
    return laws


def _prepare_cast_histories(cid, request, *, frame_id=None):
    """Resolve quick-start history routes and add only safe resident seeds.

    Browser keys never identify people here.  Every request is resolved back
    to an actual character attached to this story before any public slice is
    allowed into the location planner.
    """
    from core.db import q, wget_for_frame, wset_for_frame
    from story.character_schema import normalize_character_data
    from story.history_routing import (
        resolve_character_history_route, route_uses_charter)
    from story.journey_history import journey_event_count
    from world.charter_history import (
        featured_resident_private_habits, featured_resident_seed)

    raw = request.get("character_histories")
    if not isinstance(raw, list):
        return request, []
    # TWO SPELLINGS OF ONE ANSWER. `char_id` is this install's row id and is
    # the only key that existed; `resource_uid` is the identity that survives
    # an archive, which is what a caller provisioning a story HAS -- the local
    # ids are minted by the import that has not happened yet from its point of
    # view, and remapped again on every branch and clone. Both resolve through
    # the same `chat_chars` join below, so attachment to THIS story and the
    # per-story card override are enforced in one place for either spelling.
    requested = []
    seen_ids, seen_uids, uid_rows = set(), set(), []
    for value in raw:
        if not isinstance(value, dict):
            continue
        uid = str(value.get("resource_uid") or "").strip()
        if uid:
            if uid in seen_uids:
                continue
            seen_uids.add(uid)
            uid_rows.append((uid, value))
            continue
        try:
            char_id = int(value.get("char_id"))
        except (TypeError, ValueError):
            continue
        if char_id <= 0 or char_id in seen_ids:
            continue
        seen_ids.add(char_id)
        requested.append((char_id, value))
    if len(uid_rows) + len(requested) > CAST_HISTORY_REQUEST_CAP:
        # BEFORE THE SQL. The `char_id` spelling reaches the cap check below
        # with no query behind it; the uid spelling builds one placeholder per
        # entry, so an oversized request would have raised sqlite's "too many
        # SQL variables" -- a 500, not the documented refusal.
        raise ValueError(
            "a lived-location start can generate history for at most "
            f"{CAST_HISTORY_REQUEST_CAP} full characters at once; Charter "
            "residents themselves are not limited by this cognition budget")
    if uid_rows:
        marks = ",".join("?" for _ in uid_rows)
        resolved = {
            str(row["resource_uid"]): int(row["char_id"])
            for row in q(
                "SELECT cc.char_id, ch.resource_uid FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id "
                f"WHERE cc.chat_id=? AND ch.resource_uid IN ({marks})",
                (cid, *(uid for uid, _value in uid_rows)))
            if row["resource_uid"]
        }
        missing = [uid for uid, _value in uid_rows if uid not in resolved]
        if missing:
            # REFUSED, not skipped. An unresolvable `char_id` is dropped
            # silently below and always was -- a browser sending a stale id
            # is a UI bug the author cannot act on. A `resource_uid` is
            # supplied by a caller that believes it attached that character,
            # and silently generating a location without them is the failure
            # they most need told about.
            raise ValueError(
                "character_histories names %s no character in this story "
                "carries; attach the character before requesting its "
                "history" % ", ".join(repr(uid) for uid in sorted(missing)))
        for uid, value in uid_rows:
            char_id = resolved[uid]
            if char_id in seen_ids:
                continue
            seen_ids.add(char_id)
            requested.append((char_id, value))
    if len(requested) > CAST_HISTORY_REQUEST_CAP:
        raise ValueError(
            "a lived-location start can generate history for at most "
            f"{CAST_HISTORY_REQUEST_CAP} full characters at once; Charter "
            "residents themselves are not limited by this cognition budget")
    if not requested:
        clean = dict(request)
        clean.pop("character_histories", None)
        return clean, []

    placeholders = ",".join("?" for _ in requested)
    rows = q(
        "SELECT cc.char_id, COALESCE(NULLIF(cc.sheet,''), ch.sheet) sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        f"WHERE cc.chat_id=? AND cc.char_id IN ({placeholders})",
        (cid, *(char_id for char_id, _value in requested)))
    sheets = {
        int(row["char_id"]): normalize_character_data(
            json.loads(row["sheet"] or "{}"))
        for row in rows
    }
    chat = q("SELECT scenario FROM chats WHERE id=?", (cid,), one=True)
    opening = str(chat["scenario"] or "") if chat else ""
    clean = copy.deepcopy(request)
    clean.pop("character_histories", None)
    featured = [copy.deepcopy(row) for row in clean.get(
        "featured_residents", []) if isinstance(row, dict)]
    featured_ids = {str(row.get("seed_id") or "") for row in featured}
    # AND WHO THEY ARE, not only how the caller spelled the seed. Two seeds
    # naming the same person place two bodies: measured 2026-08-28, a caller
    # that passed its cast as `featured_residents` keyed `cast:<id>` while
    # also requesting `character_histories` for them got `cast:74` from itself
    # and `character:74` from this function, and the institution was generated
    # holding two captains both called Jean-Luc Picard, two Datas and two
    # Worfs. The seed_id guard below is right about its own question and blind
    # to this one.
    featured_by_name = {}
    for row in featured:
        folded = " ".join(str(row.get("name") or "").split()).casefold()
        if folded and folded not in featured_by_name:
            featured_by_name[folded] = str(row.get("seed_id") or "")
    private = copy.deepcopy(clean.get("featured_resident_private") or {})
    if not isinstance(private, dict):
        private = {}
    routes = wget_for_frame(
        cid, "character_history_routes", frame_id, {}) or {}
    prepared = []
    for char_id, value in requested:
        sheet = sheets.get(char_id)
        if not sheet:  # A character outside this story has no authority here.
            continue
        route = resolve_character_history_route(
            sheet, requested=value, opening=opening,
            location_brief=clean.get("brief") or "")
        route["guidance"] = str(value.get("brief") or "")[:2000]
        route["event_count"] = journey_event_count(value.get("events"))
        routes[str(char_id)] = copy.deepcopy(route)
        prepared.append({"char_id": char_id, "sheet": sheet, "route": route})
        if route_uses_charter(route):
            seed = featured_resident_seed(char_id, sheet)
            folded = " ".join(str(seed.get("name") or "").split()).casefold()
            seed_id = str(seed["seed_id"])
            if seed_id in featured_ids:
                pass
            elif folded and featured_by_name.get(folded):
                # The caller already supplied this person under a seed of its
                # own spelling. Dropping the second row is only half the fix:
                # everything downstream asks for this character's placement by
                # seed, so the surviving seed becomes this character's seed and
                # is carried on the route. Deleting the row without the remap
                # is what made the 2026-08-28 setup raise "did not place
                # featured character 74" -- one body, and nothing able to
                # find it.
                seed_id = featured_by_name[folded]
            else:
                featured.append(seed)
                featured_ids.add(seed_id)
                if folded:
                    featured_by_name[folded] = seed_id
            route["seed_id"] = seed_id
            routes[str(char_id)]["seed_id"] = seed_id
            private[seed_id] = {
                "habits": featured_resident_private_habits(sheet)}
    wset_for_frame(cid, "character_history_routes", routes, frame_id)
    if featured:
        clean["featured_residents"] = featured
    if private:
        clean["featured_resident_private"] = private
    return clean, prepared


def _complete_cast_histories(cid, request, prepared, generated, *,
                             frame_id=None):
    """Compile the selected topology and record the cognition handoff."""
    from core.db import q, wget_for_frame, wset_for_frame
    from story.character_schema import character_name
    from story.history_routing import route_uses_charter

    if not prepared or not isinstance(generated, dict) or not generated.get("ok"):
        return
    routes = wget_for_frame(
        cid, "character_history_routes", frame_id, {}) or {}
    bindings = generated.get("featured_residents") or {}
    opening_row = q(
        "SELECT scenario FROM chats WHERE id=?", (cid,), one=True)
    opening = str(opening_row["scenario"] or "") if opening_row else ""
    for item in prepared:
        char_id, sheet, route = (
            item["char_id"], item["sheet"], item["route"])
        if route_uses_charter(route):
            # `_prepare_cast_histories` may have folded this character onto a
            # seed the caller supplied for the same person, so ask the route
            # which seed was actually placed rather than assuming its own.
            binding = bindings.get(
                str(route.get("seed_id") or f"character:{char_id}"))
            if not binding:
                raise ValueError(
                    f"lived location did not place featured character {char_id}")
            from world.charter_history import integrate_featured_resident
            result = integrate_featured_resident(
                cid, char_id, binding, sheet, frame_id=frame_id,
                author_guidance=route.get("guidance") or "")
            routes[str(char_id)]["handoff"] = {
                "complete": True,
                "memory_count": len(result.get("memory_event_keys") or ()),
                "binding": copy.deepcopy(binding),
            }
            continue

        is_journey = (
            route.get("mode") in {"visitor", "generated_journey"}
            or (route.get("mode") == "auto"
                and route.get("opening_relationship") == "visiting"))
        if not is_journey:
            routes[str(char_id)]["handoff"] = {
                "complete": True, "memory_count": 0,
                "backend": "authored card" if route.get("backends") else "none",
            }
            continue
        from story.journey_history import compile_journey_history
        lore, _source = generation_lore(
            cid, request.get("lorebook_id"),
            query=f"{character_name(sheet)} journeys visits history")
        try:
            result = compile_journey_history(
                cid, char_id, sheet, route, lore=lore, opening=opening,
                arrival_brief=str(request.get("brief") or ""),
                frame_id=frame_id)
            routes[str(char_id)]["handoff"] = {
                "complete": True,
                "memory_count": len(result.get("memory_event_keys") or ()),
                "journey_events": len(result.get("events") or ()),
            }
        except Exception as exc:
            if route.get("mode") == "generated_journey":
                raise
            routes[str(char_id)]["handoff"] = {
                "complete": False,
                "safe_fallback": "authored card only",
                "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            }
    wset_for_frame(cid, "character_history_routes", routes, frame_id)


def registry_revision(registry):
    """Stable identity for the exact author/runtime state a job advanced."""
    encoded = json.dumps(normalize_registry(registry), sort_keys=True,
                         ensure_ascii=False, separators=(",", ":"))
    return stable_event_key("charter_registry", encoded)


def _presim_one(payload):
    """Advance one institution. MODULE LEVEL because it is sent to a process.

    A closure cannot be pickled, so writing this as a local function inside
    `presim_registry` makes the pool raise, the guard swallow it, and the work
    run sequentially while reporting success -- the parallelism would be a
    comment rather than a behaviour. Everything it needs travels in the
    payload for the same reason.
    """
    index, key, item_state, window_hours, coarse, tail, active, seed = payload
    state = copy.deepcopy(item_state)
    out = []
    if coarse:
        state["active_places"] = []
        state, events = run(
            state, coarse, window=max(8.0, window_hours),
            seed=seed + index * 100_000, simulate_bound=True)
        out.extend({"charter": key, **copy.deepcopy(event)}
                   for event in events)
    if tail:
        state["active_places"] = list(active)
        state, events = run(
            state, tail, window=min(4.0, window_hours),
            seed=seed + index * 100_000 + 50_000, simulate_bound=True)
        out.extend({"charter": key, **copy.deepcopy(event)}
                   for event in events)
    return state, out


def presim_registry(registry, *, horizon_hours=MAX_CATCHUP_HOURS,
                    active_tail_hours=DEFAULT_PRESIM_TAIL_HOURS,
                    tail_places=(), seed=0, scene=None):
    """Live a generated registry forward before the first story beat.

    ``scene`` is the room graph the prehistory is walked over -- the planted
    skeleton, in ordinary scene shape (`world/structure.skeleton_rooms`).
    Stamped on every institution that does not already carry one, so
    `charter_run.run` takes its scene branch: bodies route over
    `travel_rooms`, walks are recorded edge by edge, a shut door holds.
    Without it every one of the 720 hours was a teleport (Harrowmere,
    2026-09-02: `travelled` = 1 per body over a month), while the same
    registry's first in-play catch-up composed exactly this scene from the
    same skeleton -- so this is the missing argument, not a new model.

    The long body establishes durable service, acquaintance, politics and
    stock movement cheaply. The recent tail enables practices at authored
    places so Scene Life has fresh episodes to draw on. Returned events are
    objective history; no memories are fabricated from the history brief.

    BOUND BODIES ARE SIMULATED HERE, and only here. `charter_run.step` normally
    withholds cognition and motion from a body a registered character has taken
    over -- correct during play, and exactly backwards before the story opens,
    when no registered character exists yet and the featured cast's past is the
    thing this function is for. Left applied, it made the major characters the
    emptiest bodies in their own institution: 25 watches stood, no memory of
    any of them, nobody known.
    """
    registry = normalize_registry(copy.deepcopy(registry))
    if isinstance(scene, dict) and scene.get("rooms"):
        for item in registry["items"].values():
            if not (item.get("state") or {}).get("scene"):
                item["state"]["scene"] = copy.deepcopy(scene)
    horizon = max(0.0, min(MAX_PRESIM_HOURS, float(horizon_hours or 0.0)))
    tail = max(0.0, min(horizon, float(active_tail_hours or 0.0)))
    coarse = horizon - tail
    produced = []
    ordered = list(enumerate(sorted(registry["items"].items())))
    # ACROSS CHARTERS, IN PARALLEL. Each institution is a closed state advanced
    # from a seed derived from its own INDEX, so nothing crosses between them
    # here -- `cross_charter_gossip` is the barrier afterwards and is where
    # information is allowed to move. That makes this embarrassingly parallel
    # and, unusually, parallel WITHOUT losing replay: the seed comes from the
    # sorted position rather than from execution order, so results are
    # gathered back in that same order and a run is byte-identical whether it
    # ran on one core or eight.
    #
    # Measured on a generated market town, 7 charters and 300 bodies over
    # 2,160 simulated hours: 154.7s sequential, 30.9s per charter. The cost is
    # also SUPER-LINEAR in population -- 1.8 ms per simulated hour at 40
    # bodies against 71.6 at 300, so 7.5x the people cost 40x the time. This
    # divides the wall clock; it does not address that, and the profile that
    # would is `docs/UNBUILT.md` 1.99h.
    #
    # Fork cost is real (pickling a whole registry item both ways), so a lone
    # charter or a trivial horizon stays in-process where a pool would only
    # add latency.
    active = sorted({str(x) for x in tail_places if str(x)})
    payloads = [(index, key, item["state"], item["window_hours"],
                 coarse, tail, active, int(seed))
                for index, (key, item) in ordered]
    results = None
    if len(payloads) > 1 and (coarse + tail) >= PARALLEL_PRESIM_HOURS:
        try:
            from concurrent.futures import ProcessPoolExecutor
            import os as _os
            workers = min(len(payloads), max(1, (_os.cpu_count() or 2) - 1))
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_presim_one, payloads))
        except Exception:
            # A pool that cannot start is a latency problem, never a
            # correctness one: the same work runs here instead.
            results = None
    if results is None:
        results = [_presim_one(payload) for payload in payloads]

    for (index, (key, item)), (state, events) in zip(ordered, results):
        produced.extend(events)
        item["state"] = state
        item["last_elapsed_seconds"] = 0.0
        item["last_epoch_id"] = "presim"
    return normalize_registry(registry), produced


def generation_lore(cid, lorebook_id=None, entry_ids=None,
                    *, limit=GENERATION_LORE_LIMIT, query=""):
    """Bounded lore selected explicitly for one lived-location generation.

    The selected book and its descendants are the authoring scope.  This is
    intentionally narrower than ordinary retrieval, which may walk ancestors
    and reference links: choosing a city book must not quietly let an attached
    rules compendium or unrelated nation design the city instead.  A global
    library book is accepted for the create-story seam; story-local books must
    belong to this story.
    """
    from core.db import q
    from mind.memory import lorebook_descendants

    chat = q("SELECT id,lorebook_id FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise ValueError("story not found")
    source = lorebook_id if lorebook_id not in (None, "") \
        else chat["lorebook_id"]
    if source in (None, ""):
        return [], None
    try:
        source = int(source)
    except (TypeError, ValueError) as exc:
        raise ValueError("lorebook_id must be a number") from exc
    book = q("SELECT id,chat_id FROM lorebooks WHERE id=?", (source,), one=True)
    if not book:
        raise ValueError(f"lorebook {source} not found")
    if book["chat_id"] is not None and int(book["chat_id"]) != int(cid):
        raise ValueError("selected lorebook belongs to another story")
    scoped = lorebook_descendants(source)
    if book["chat_id"] is not None:
        scoped = [lid for lid in scoped if q(
            "SELECT 1 FROM lorebooks WHERE id=? AND chat_id=?",
            (lid, cid), one=True)]
    selected_entries = []
    for value in entry_ids or ():
        try:
            selected_entries.append(int(value))
        except (TypeError, ValueError):
            raise ValueError("lore_entry_ids must contain numbers")
    if not scoped:
        return [], source
    placeholders = ",".join("?" for _ in scoped)
    params = list(scoped)
    sql = (
        "SELECT le.id,le.title,le.content,lb.name book_name "
        "FROM lore_entries le JOIN lorebooks lb ON lb.id=le.lorebook_id "
        f"WHERE le.lorebook_id IN ({placeholders})")
    if selected_entries:
        entry_ph = ",".join("?" for _ in selected_entries)
        sql += f" AND le.id IN ({entry_ph})"
        params.extend(selected_entries)
    bounded = max(1, min(GENERATION_LORE_LIMIT, int(limit)))
    if selected_entries or not str(query or "").strip():
        sql += " ORDER BY le.lorebook_id,le.id LIMIT ?"
        params.append(bounded)
        rows = q(sql, tuple(params))
    else:
        # Generation is a retrieval problem, not an insertion-order problem.
        # The ordinary lore ranker already combines semantic and lexical
        # relevance across an arbitrarily large selected subtree. Reusing it
        # keeps a 2,000-entry library from making "the first 48 rows" author
        # the requested city merely because they were imported first.
        from mind.memory import search_lore
        hits = search_lore(scoped, str(query), k=bounded)
        ranked_ids = [int(hit["id"]) for hit in hits if hit.get("id")]
        # Setting-law entries are constraints rather than relevance hits.
        # Keep a small bounded prefix even when the requested location shares
        # none of their vocabulary; otherwise retrieval can faithfully find a
        # place while silently dropping the book's rules for depicting it.
        rule_rows = q(
            "SELECT id FROM lore_entries "
            f"WHERE lorebook_id IN ({placeholders}) AND ("
            "LOWER(COALESCE(category,'')) IN ('rule','rules') OR "
            "LOWER(LTRIM(COALESCE(content,''))) LIKE '<rules>%') "
            "ORDER BY lorebook_id,id LIMIT 4", tuple(scoped))
        ordered_ids = []
        for entry_id in [row["id"] for row in rule_rows] + ranked_ids:
            if entry_id not in ordered_ids:
                ordered_ids.append(entry_id)
        ordered_ids = ordered_ids[:bounded]
        if ordered_ids:
            ranked_ph = ",".join("?" for _ in ordered_ids)
            fetched = q(
                "SELECT le.id,le.title,le.content,lb.name book_name "
                "FROM lore_entries le JOIN lorebooks lb "
                "ON lb.id=le.lorebook_id "
                f"WHERE le.id IN ({ranked_ph})", tuple(ordered_ids))
            by_id = {row["id"]: row for row in fetched}
            rows = [by_id[entry_id] for entry_id in ordered_ids
                    if entry_id in by_id]
        else:
            sql += " ORDER BY le.lorebook_id,le.id LIMIT ?"
            params.append(bounded)
            rows = q(sql, tuple(params))
    if selected_entries and len(rows) != len(set(selected_entries)):
        raise ValueError("one or more lore entries are outside the selected book")
    return [{"id": row["id"], "book": row["book_name"],
             "title": row["title"], "content": row["content"]}
            for row in rows], source


def _generation_lore_query(request, brief):
    """The requested place and its author-required facets, as one query."""
    parts = [request.get("name"), brief, request.get("scale"),
             request.get("topology")]
    for room in request.get("required_rooms") or ():
        if isinstance(room, dict):
            parts.extend((room.get("name"), room.get("purpose")))
        elif isinstance(room, str):
            parts.append(room)
    return "\n".join(str(part).strip() for part in parts
                      if str(part or "").strip())


def _unique_generated_key(base, taken):
    base = str(base or "generated").strip() or "generated"
    if base not in taken:
        return base
    index = 2
    while f"{base}_{index}" in taken:
        index += 1
    return f"{base}_{index}"


def _remap_generated_town(cid, town, existing_registry):
    """Give an added location its own stable namespace when ids collide."""
    from core.db import q, wget_for_frame
    from world.spatial import normalize_room_id

    town = copy.deepcopy(town)
    stored_structures = wget_for_frame(cid, "structures", None, {}) or {}
    structure_items = stored_structures.get("items") \
        if isinstance(stored_structures.get("items"), dict) \
        else stored_structures
    taken_structures = {str(key) for key in (structure_items or {})}
    old_structure = str((town.get("structure") or {}).get("key") or "location")
    structure_key = _unique_generated_key(old_structure, taken_structures)
    existing_rooms = {str(row["room_uid"]) for row in q(
        "SELECT room_uid FROM room_registry WHERE chat_id=? ", (cid,))}
    generated_rooms = {str(uid) for uid in (town.get("rooms") or {})}
    needs_namespace = structure_key != old_structure \
        or bool(existing_rooms.intersection(generated_rooms))
    room_map = {uid: uid for uid in generated_rooms}
    if needs_namespace:
        taken = set(existing_rooms)
        room_map = {}
        for uid in sorted(generated_rooms):
            stem = normalize_room_id(f"{structure_key} {uid}") \
                or f"{structure_key}_{len(room_map) + 1}"
            mapped = _unique_generated_key(stem, taken)
            taken.add(mapped)
            room_map[uid] = mapped

    rooms = {}
    for old_uid, raw in (town.get("rooms") or {}).items():
        room = copy.deepcopy(raw)
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict):
                edge["to"] = room_map.get(str(edge.get("to")), edge.get("to"))
        rooms[room_map[str(old_uid)]] = room
    town["rooms"] = rooms
    town.setdefault("structure", {})["key"] = structure_key

    taken_charters = set((existing_registry.get("items") or {}).keys())
    charters = {}
    for old_key, raw in (town.get("charters") or {}).items():
        new_key = _unique_generated_key(old_key, taken_charters)
        taken_charters.add(new_key)
        state = copy.deepcopy(raw)
        state["key"] = new_key
        state["structure"] = structure_key
        for collection in ("upkeeps", "posts", "bodies"):
            for value in (state.get(collection) or {}).values():
                if not isinstance(value, dict):
                    continue
                for field in ("place", "berth"):
                    if value.get(field) is not None:
                        value[field] = room_map.get(
                            str(value[field]), value[field])
        for market in ((state.get("economy") or {}).get("markets") or {}).values():
            if isinstance(market, dict) and market.get("place") is not None:
                market["place"] = room_map.get(
                    str(market["place"]), market["place"])
        # A room id anywhere in a charter has to travel with the re-key, and a
        # list of them is as much a place reference as a `place` field is. Left
        # out, the commons would point at ids that no longer exist and the
        # circulation it was authored for would silently be gone again.
        if state.get("commons"):
            state["commons"] = [room_map.get(str(place), str(place))
                                for place in state["commons"]]
        for intervention in state.get("interventions") or ():
            if not isinstance(intervention, dict):
                continue
            if intervention.get("charter") == old_key:
                intervention["charter"] = new_key
            if intervention.get("place") is not None:
                intervention["place"] = room_map.get(
                    str(intervention["place"]), intervention["place"])
        charters[new_key] = normalize_charter(state)
    town["charters"] = charters
    town["structure"]["charters"] = list(charters)
    return town


def _lore_character_entries(cid):
    """The lore rows that may name a person, for the cast reader to judge."""
    try:
        from mind.memory import chat_lorebook_ids
        book_ids = list(chat_lorebook_ids(cid) or [])
    except Exception:
        return []
    if not book_ids:
        return []
    from core.db import q
    marks = ",".join("?" * len(book_ids))
    return [dict(row) for row in q(
        "SELECT id, title, content FROM lore_entries "
        "WHERE lorebook_id IN (%s) AND category=? ORDER BY id" % marks,
        (*book_ids, "character"))]


def generate_lived_location(cid, request, *, frame_id=None):
    """Generate and add one lore-grounded, presimulated Charter location.

    Existing locations and institutions are preserved.  Only the newly
    generated registry slice is lived through its prehistory, so adding a
    spaceport halfway through a story cannot age the town already in play by
    another month.
    """
    from core.db import q, wget_for_frame
    from world.charter_generate import (
        close_plan, ensure_required_rooms, narrate_actual_history,
        propose_history, propose_town)
    from world.structure import plant_structure, structure_warnings

    request = request if isinstance(request, dict) else {}
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise ValueError("story not found")
    digest = _request_digest(cid, request, frame_id)
    artifact, prior = _resumable_plan(cid, digest)
    if prior and prior.get("stage") in PAST_BOUNDARY_STAGES:
        # PAST THE BOUNDARY, whatever else is true of it. Rooms may already be
        # planted and the registry saved, and `_remap_generated_town` reads
        # LIVE state, so a second run over an unfinished one plants a second
        # town.
        #
        # ON STAGE ALONE, deliberately, and this is the correction that
        # matters. `status` only ever distinguishes a foreign OWNER, so a run
        # that died inside a live process still reads `running` and would have
        # sailed straight past a status test. Nor on the digest: a story with
        # half-planted rooms is in that state whatever is asked for next, and
        # the obvious thing an author does after a failure is retry with one
        # field changed.
        raise ValueError(
            "a previous generation of this story was interrupted after it had "
            "begun planting rooms (stage %r). Inspect the story's locations, "
            "then clear the job (DELETE /api/chats/<id>/charters/job) before "
            "generating again." % prior.get("stage"))
    if prior and prior.get("status") == "running" \
            and prior.get("owner") == _GEN_OWNER:
        # A LIVE ONE, in this process. `_require_frame_idle` cannot see this:
        # it reads the turn pipeline's `ABORTS`, which generation never
        # registers in, so a double-click or two hooks give two runs that
        # would both claim the single job slot -- and the loser's `planted`
        # marker would be erased by the winner's `planning`. A `running` job
        # this process owns can only be a live one, because every failure
        # path marks or clears it (`_fail_job`); one owned by a DEAD process
        # reads as `interrupted` instead and does not land here.
        raise ValueError(
            "a generation is already running for this story. Wait for it to "
            "finish, or clear it (DELETE /api/chats/<id>/charters/job).")
    _save_job(cid, {"version": 1, "job_id": uuid.uuid4().hex,
                    "owner": _GEN_OWNER, "status": "running",
                    "stage": "planning", "digest": digest,
                    "error": "", "resumed": bool(artifact)})
    try:
        return _generate_lived_location(
            cid, request, chat, frame_id, digest, artifact)
    except Exception as exc:
        _fail_job(cid, exc)
        raise


def _fail_job(cid, exc):
    """Record a failure so the next call can see it.

    BEFORE THE BOUNDARY there is nothing to recover and nothing was written,
    so the job is forgotten -- leaving a `running` claim owned by THIS process
    would not read as an interruption (the owner matches) and would look live
    forever. AFTER it, the record is the whole point: it is what refuses the
    next run, so it is kept and marked, never cleared.
    """
    job = lived_location_job(cid) or {}
    if job.get("stage") in PAST_BOUNDARY_STAGES:
        _save_job(cid, {**job, "status": "failed",
                        "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
        return
    clear_lived_location_job(cid)


def _plan_naming_laws(plan):
    """The naming laws a raw plan proposes, one per charter. Read only for
    their title vocabulary, so a registered name that carries a rank is still
    recognised as the person underneath it."""
    charters = (plan or {}).get("charters") if isinstance(plan, dict) else None
    return [raw.get("naming") for raw in (charters or ())
            if isinstance(raw, dict) and isinstance(raw.get("naming"), dict)]


def _plan_lived_location(cid, request, chat):
    """The pure prefix: two model calls, a deterministic closure, no writes.

    Returned whole as the artifact a resume restores. Everything downstream
    needs all seven fields, so restoring only some would carry the town from
    one run beside the lore provenance of another.
    """
    from core.db import q
    from world.charter_generate import (
        close_plan, ensure_required_rooms, propose_history, propose_town)

    lore = request.get("lore")
    source_book = request.get("lorebook_id")
    brief = str(request.get("brief") or chat["scenario"]
                or chat["name"] or "inhabited location")
    lore_query = _generation_lore_query(request, brief)
    if lore is None:
        lore, source_book = generation_lore(
            cid, source_book, request.get("lore_entry_ids"),
            query=lore_query)
    elif source_book not in (None, ""):
        # Explicit lore is allowed for tools, but a claimed provenance book
        # still has to exist in this authoring scope.
        _unused, source_book = generation_lore(cid, source_book, limit=1)
    # THE STORY'S OWN BOOK IS THE LAST FALLBACK, and without it the phonology
    # artifact is silently never written. A caller that supplies `lore` as
    # TEXT never reaches `generation_lore`, so `source_book` stays None, so
    # `_record_phonology` returns at its own front door -- and it is
    # deliberately never fatal, so nothing says so. Measured 2026-08-28: a
    # generation whose law carried a full set of fragments produced zero
    # phonology entries, and the one model judgement the lane exists to make
    # reviewable could only be read out of the raw stored law.
    owning_book = (request.get("owning_lorebook_id") or source_book
                   or chat["lorebook_id"])
    if request.get("owning_lorebook_id") not in (None, ""):
        try:
            owning_book = int(request["owning_lorebook_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("owning_lorebook_id must be a number") from exc
        owner = q("SELECT chat_id FROM lorebooks WHERE id=?",
                  (owning_book,), one=True)
        if not owner or int(owner["chat_id"] or -1) != int(cid):
            raise ValueError("owning lorebook must belong to this story")
    # The ceiling is the presim's; the DEFAULT is still a month. An author who
    # says nothing gets what they always got, and an author who asks for a year
    # gets a year instead of a silently truncated month.
    horizon = max(0.0, min(
        MAX_PRESIM_HOURS,
        float(request.get("horizon_hours", MAX_CATCHUP_HOURS))))
    # THE LORE'S OWN PEOPLE, handed over by a reader rather than a rule. An
    # individual the lore names is a person the world contains; if they are not
    # one of the story's registered minds they belong here, at a post, as an
    # ordinary promotable presence -- which is the other half of not letting
    # their name become pool material. See `charter_generate.lore_cast_residents`
    # for why a model does this reading and a parser cannot.
    requested_residents = list(request.get("featured_residents") or [])
    try:
        from story.naming import registered_identity_names
        from world.charter_generate import lore_cast_residents
        lore_people = lore_cast_residents(
            _lore_character_entries(cid), registered_identity_names(cid))
        taken = {str(row.get("seed_id")) for row in requested_residents
                 if isinstance(row, dict)}
        # By NAME as well as by seed. The reader is told who is registered and
        # excludes them, but a model asked to exclude somebody is not a
        # guarantee that it did -- and the cost of the miss is a second body
        # wearing a registered person's name.
        taken_names = {" ".join(str(row.get("name") or "").split()).casefold()
                       for row in requested_residents if isinstance(row, dict)}
        taken_names.discard("")
        for row in lore_people:
            folded = " ".join(str(row.get("name") or "").split()).casefold()
            if row["seed_id"] in taken or (folded and folded in taken_names):
                continue
            requested_residents.append(row)
            taken_names.add(folded)
    except Exception:
        pass
    population = request.get("population")
    if population not in (None, ""):
        try:
            population = max(1, int(population))
        except (TypeError, ValueError) as exc:
            raise ValueError("population must be a number") from exc
    else:
        population = None
    constraints = {
        key: copy.deepcopy(value)
        for key, value in (("scale", request.get("scale")),
                           ("topology", request.get("topology")),
                           ("required_rooms", request.get("required_rooms")),
                           ("featured_residents", requested_residents),
                           ("population", population))
        if value not in (None, "", [])}
    plan = (propose_town(lore, brief, constraints=constraints)
            if constraints else propose_town(lore, brief))
    history = {}
    wants_history = bool(request.get("generate_history", True)) and horizon > 0
    if wants_history:
        history = propose_history(plan, lore, horizon)
    # The cast is not a naming lane, it is the no-fly list. The planner was
    # handed the same lore the cast came from, so its pools arrive holding
    # the cast's own name elements unless something subtracts them.
    from story.naming import (
        authored_naming_profile, naming_law_exists, story_identity_reservation)
    authored = authored_naming_profile(cid)
    naming_law = authored if naming_law_exists(authored) else None
    laws = [naming_law] if naming_law else _plan_naming_laws(plan)
    town = close_plan(
        plan, history=history,
        featured_residents=requested_residents,
        reservation=story_identity_reservation(cid, laws),
        naming_law=naming_law, population=population)
    unnamed = [
        f"{charter_key}/{body_key}"
        for charter_key, state in town["charters"].items()
        for body_key, body in (state.get("bodies") or {}).items()
        if not str(body.get("name") or "").strip()
        or str(body.get("name") or "").strip() == str(body_key)
    ]
    if unnamed:
        raise ValueError(
            "generated lived location did not provide a usable naming law "
            "for every resident: " + ", ".join(unnamed[:8]))
    # Private character material crosses only after the public location plan
    # has closed and only onto the exact body selected by resident_seed_id.
    # It cannot shape rooms, posts, lore, or anybody else's state.
    private_by_seed = request.get("featured_resident_private") or {}
    if isinstance(private_by_seed, dict):
        for state in town["charters"].values():
            for body in state.get("bodies", {}).values():
                seed_id = str(body.get("resident_seed_id") or "")
                private = private_by_seed.get(seed_id)
                if isinstance(private, dict) and private.get("habits"):
                    body["private_habits"] = copy.deepcopy(private["habits"])
    lore_manifest = {
        "source_lorebook_id": source_book,
        "entry_ids": [entry.get("id") for entry in lore
                      if isinstance(entry, dict) and entry.get("id") is not None],
        "query": lore_query,
    }
    for state in town["charters"].values():
        state.setdefault("history", {}).setdefault(
            "architecture", {})["generation_lore"] = copy.deepcopy(
                lore_manifest)
    required_rooms_added = ensure_required_rooms(
        town, request.get("required_rooms"))
    requested_name = str(request.get("name") or "").strip()
    if requested_name:
        # Display spelling is author authority. The stable structure key stays
        # machine-normalized and collision-safe; names are allowed to retain
        # punctuation and case exactly as the author supplied them.
        town["name"] = requested_name
        town["structure"]["name"] = requested_name
    _record_phonology(owning_book, town)
    return {"town": town, "required_rooms_added": required_rooms_added,
            "lore_manifest": lore_manifest, "source_book": source_book,
            "owning_book": owning_book, "horizon": horizon,
            "wants_history": wants_history}


_PHONOLOGY_BUCKETS = (("given_parts", "given"), ("family_parts", "family"))


def _record_phonology(book_id, town):
    """Write a generated law's name FRAGMENTS back as a phonology entry.

    THE ARTIFACT THAT MAKES THE ONE MODEL JUDGEMENT REVIEWABLE. The planner
    decides, once, what the setting's names are built out of; from then on the
    mint is deterministic code reading a list an author can open and edit. The
    objection to model-made names is opacity at the SAMPLER, where nobody can
    audit a per-name decision -- it does not apply to a judgement made once,
    in the open, that a person can change.

    Fragments only, and that is the whole point: an entry in this category is
    a lane the mint reads (`story.naming.phonology_lanes`, ranked above the
    stored Charter law and below an author's explicit `naming_profile`), and
    it holds material rather than people. The pools the planner used to
    supply never reach a body, and neither do the fragments that turn out to
    be pieces of one (`charter_identity.refuse_harvested_material`, and the
    lane re-checks its own entries on every read because an entry can be
    edited by hand).

    Never fatal. A story whose lore write fails still generates; it simply has
    no authored phonology to read next time.
    """
    if not book_id:
        return
    try:
        from mind.memory import add_lore
    except Exception:
        return
    for key, state in (town.get("charters") or {}).items():
        law = (state or {}).get("naming") or {}
        lines = []
        for field, label in _PHONOLOGY_BUCKETS:
            group = law.get(field) or {}
            for bucket in ("starts", "middles", "ends"):
                values = [str(v).strip() for v in (group.get(bucket) or [])
                          if str(v).strip()]
                if values:
                    lines.append(f"{label}_{bucket}: " + ", ".join(values))
        if not lines:
            continue
        name = str(state.get("name") or key)
        try:
            add_lore(book_id, f"phonology, names, {key}",
                     "The fragments names here are built from. Edit freely: "
                     "the mint reads this list, and a fragment that is a "
                     "piece of somebody's name is dropped when it does."
                     "\n\n"
                     + "\n".join(lines),
                     category="phonology",
                     title=f"Naming fragments — {name}",
                     importance=0.4)
        except Exception:
            continue


def _generate_lived_location(cid, request, chat, frame_id, digest, artifact):
    """The body, with the job's lifecycle owned by the caller."""
    from core.db import q, wget_for_frame
    from world.charter_generate import narrate_actual_history
    from world.structure import plant_structure, structure_warnings

    was_resumed = artifact is not None

    request, cast_histories = _prepare_cast_histories(
        cid, request, frame_id=frame_id)
    if artifact is None:
        artifact = _plan_lived_location(cid, request, chat)
        # THE BOUNDARY. Everything above is pure -- two model calls and no
        # writes -- so it is exactly what is worth not paying for twice, and
        # exactly what is safe to replay. Everything below writes.
        _save_job(cid, {**(lived_location_job(cid) or {}),
                        "owner": _GEN_OWNER, "status": "running",
                        "stage": "planned",
                        "artifact": copy.deepcopy(artifact)})
    town = copy.deepcopy(artifact["town"])
    required_rooms_added = artifact["required_rooms_added"]
    lore_manifest = artifact["lore_manifest"]
    source_book = artifact["source_book"]
    owning_book = artifact["owning_book"]
    horizon = artifact["horizon"]
    wants_history = artifact["wants_history"]
    # BEFORE THE FIRST WRITE, not after it. A marker that claims a write which
    # did not happen costs one wasted regeneration; a marker that misses a
    # write which DID happen costs a second town on the same ground. Only one
    # of those is recoverable, so the marker leads.
    _save_job(cid, {**(lived_location_job(cid) or {}),
                    "owner": _GEN_OWNER, "stage": "planting",
                    "artifact": None})
    existing = registry_for_update(cid, frame_id)
    town = _remap_generated_town(cid, town, existing)
    structure, rooms = plant_structure(
        cid, town["structure"], town["rooms"],
        owning_book_id=owning_book)
    generated = normalize_registry({"items": {
        key: {"state": state,
              "window_hours": float(request.get("window_hours", 4.0))}
        for key, state in town["charters"].items()}})
    combined = copy.deepcopy(existing)
    combined["items"].update(copy.deepcopy(generated["items"]))
    combined = save_registry(cid, combined, frame_id)
    source_revision = registry_revision(combined)
    # Rooms are planted and the registry is saved.
    _save_job(cid, {**(lived_location_job(cid) or {}),
                    "owner": _GEN_OWNER, "stage": "planted"})
    tail_places = list(request.get("tail_places") or list(rooms)[:8])
    # Featured residents must receive recent-resolution life where they
    # actually work and live; otherwise the arbitrary first eight rooms can
    # leave the featured person with only an aggregate shift counter.
    for item in generated["items"].values():
        for body in item["state"].get("bodies", {}).values():
            if not body.get("resident_seed_id"):
                continue
            tail_places.extend((body.get("place"), body.get("berth")))
    tail_places = list(dict.fromkeys(str(place) for place in tail_places if place))
    presimmed, events = presim_registry(
        generated, horizon_hours=horizon,
        active_tail_hours=float(request.get(
            "active_tail_hours", min(DEFAULT_PRESIM_TAIL_HOURS, horizon))),
        tail_places=tail_places,
        seed=int(request.get("seed") or 0),
        scene=skeleton_scene(rooms))
    historian_error = ""
    if wants_history:
        try:
            actual = narrate_actual_history(town, presimmed, events)
            for key, item in presimmed["items"].items():
                local = dict(actual)
                local["residents"] = {
                    resident_id.split("/", 1)[1]: value
                    for resident_id, value in (actual.get("residents") or {}).items()
                    if resident_id.startswith(f"{key}/")}
                item["state"].setdefault("history", {})["actual"] = local
        except Exception as exc:  # history prose may fail; simulation stands
            historian_error = f"{type(exc).__name__}: {str(exc)[:240]}"
    landed_registry = copy.deepcopy(combined)
    landed_registry["items"].update(copy.deepcopy(presimmed["items"]))
    clock = wget_for_frame(
        cid, "simulation_clock", frame_id, {"elapsed_seconds": 0.0}) or {}
    latest = q("SELECT MAX(idx) idx FROM turns WHERE chat_id=?", (cid,), one=True)
    landed = land_presim(
        cid, frame_id, landed_registry, events,
        base_turn=int(latest["idx"] if latest and latest["idx"] is not None
                      else 0),
        expected_revision=source_revision,
        now_seconds=float(clock.get("elapsed_seconds") or 0.0))
    from world.charter_history import featured_resident_bindings
    resident_bindings = featured_resident_bindings(
        presimmed,
        [row.get("seed_id") for row in request.get("featured_residents") or ()
         if isinstance(row, dict)])
    result = {
        "ok": landed.get("reason") is None, "town": town["name"],
        "structure": structure, "rooms": len(rooms),
        "charters": list(presimmed["items"]), "presim": landed,
        "warnings": structure_warnings(structure, rooms)
        + list((town.get("closure") or {}).get("warnings") or ()),
        "closure": copy.deepcopy(town.get("closure") or {}),
        "historian_error": historian_error,
        "required_rooms_added": required_rooms_added,
        "source_lorebook_id": source_book,
        "source_lore_entry_ids": lore_manifest["entry_ids"],
        "featured_residents": resident_bindings,
    }
    _complete_cast_histories(
        cid, request, cast_histories, result, frame_id=frame_id)
    # Terminal. The job existed to make a LOST run recoverable, so a finished
    # one is not history worth keeping -- what happened is in the registry,
    # the rooms and the scheduled events, which is where a reader should look.
    clear_lived_location_job(cid)
    result["resumed_plan"] = bool(was_resumed)
    return result


def skeleton_scene(rooms):
    """The planted rooms in ordinary scene shape, from `plant_structure`'s
    own return -- the same shape `structure.skeleton_rooms` reads back from
    the registry, built without a database round trip."""
    return {"rooms": {
        str(uid): {
            "name": str(room.get("name") or uid),
            "adjacent": [dict(edge) for edge in room.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
            "planned": True,
            "purpose": str(room.get("purpose") or ""),
            "access": str(room.get("access") or ""),
        }
        for uid, room in (rooms or {}).items() if isinstance(room, dict)}}


def land_presim(cid, frame_id, registry, produced, *, base_turn=0,
                expected_revision=None, now_seconds=0.0):
    """Atomically land explicit presimulation with a revision race guard."""
    from core.db import qtx, transaction, wset_for_frame

    if expected_revision and registry_revision(registry_for(cid, frame_id)) \
            != expected_revision:
        return {"advanced": 0, "events": 0, "reason": "registry_changed"}
    rows = []
    horizon = max((float((item.get("state") or {}).get("clock_hours") or 0.0)
                   for item in (registry.get("items") or {}).values()),
                  default=0.0)
    for event in produced:
        charter_key = str(event.get("charter") or "charter")
        due_at = float(now_seconds) - max(
            0.0, horizon - float(event.get("at_hours") or 0.0)) * 3600.0
        rows.append(_scheduled_row(
            cid, frame_id, base_turn, "presim", charter_key, event, due_at))
    with transaction():
        if expected_revision and registry_revision(registry_for(cid, frame_id)) \
                != expected_revision:
            return {"advanced": 0, "events": 0,
                    "reason": "registry_changed"}
        wset_for_frame(cid, CHARTERS_KEY, normalize_registry(registry), frame_id)
        for row in rows:
            qtx(
                "INSERT OR IGNORE INTO scheduled_events"
                "(event_id,chat_id,due_at,kind,location_id,payload,seed,status) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (row["event_id"], row["chat_id"], row["due_at"], row["kind"],
                 row["location_id"], row["payload"], row["seed"], row["status"]),
            )
    return {"advanced": len(registry["items"]), "events": len(produced),
            "scheduled": len(rows)}


def registry_warnings(registry, scene=None, *, cid=None, frame_id=None):
    """Author-facing validation; warnings never silently rewrite a Charter."""
    registry = normalize_registry(registry)
    rooms = set((scene or {}).get("rooms") or {})
    warnings = []
    for key, item in registry["items"].items():
        state = item["state"]
        known_rooms = set(rooms)
        if cid is not None and state.get("structure"):
            try:
                from world.structure import skeleton_rooms
                known_rooms.update(skeleton_rooms(
                    cid, state["structure"], frame_id).get("rooms") or {})
            except Exception:
                pass
        from story.dialogue_colors import normalize_color
        from world.charter_identity import display_name
        if not state["upkeeps"]:
            warnings.append(f"{key}: no upkeeps; this institution has no goal")
        if not state["posts"]:
            warnings.append(f"{key}: no posts; no upkeep can be serviced")
        if not state["bodies"]:
            warnings.append(f"{key}: no bodies; every post will be unfilled")
        # A CONSEQUENCE RULE THAT DOES NOTHING FAILS SILENTLY, which is the
        # empty-psychology-field failure `CLAUDE.md` records: no error, no
        # warning at runtime, and a world that behaves wrongly fifty beats
        # later for a reason that looks like a model problem. Validation
        # belongs in the authoring surface on the day the field lands.
        for notice in trigger_warnings(state.get("triggers")):
            warnings.append(f"{key}: {notice}")
        roles = {}
        for post, assigned in (state.get("watch") or {}).items():
            roles.setdefault(str(assigned), []).append(str(post))
        display_groups = {}
        for body_key, body in state["bodies"].items():
            display = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            display_groups.setdefault(display.casefold(), []).append(body_key)
            raw_color = str(body.get("dialogue_color") or "").strip()
            if raw_color and not normalize_color(raw_color):
                warnings.append(
                    f"{key}: body {body_key!r} has unreadable dialogue_color "
                    f"{raw_color!r}; expected #rgb or #rrggbb")
        for display, bodies in sorted(display_groups.items()):
            if display and len(bodies) > 1:
                warnings.append(
                    f"{key}: display name {display!r} belongs to multiple "
                    f"bodies {bodies}; scene presence is withheld until "
                    "the author distinguishes them")
        served = {upkeep for post in state["posts"].values()
                  for upkeep in post.get("serves") or ()}
        for upkeep in sorted(set(state["upkeeps"]) - served):
            warnings.append(f"{key}: upkeep {upkeep!r} is served by no post")
        for post_key, post in state["posts"].items():
            for upkeep in post.get("serves") or ():
                if upkeep not in state["upkeeps"]:
                    warnings.append(
                        f"{key}: post {post_key!r} serves unknown upkeep "
                        f"{upkeep!r}")
            superior = str(post.get("reports_to") or "")
            if superior and superior not in state["posts"]:
                warnings.append(
                    f"{key}: post {post_key!r} reports to unknown post "
                    f"{superior!r}")
            if superior == post_key:
                warnings.append(
                    f"{key}: post {post_key!r} cannot report to itself")

        # THE SHAPE OF THE MEMBERSHIP, which nothing here used to read. Every
        # check below is about who the institution is MADE OF, and each one
        # was invisible on the day the charter was written.
        #
        # Measured, chat 95's generated `starfleet_crew`: 24 bodies across 7
        # posts, `home_post` non-empty for all 24, rank a strict function of
        # post (7 posts, 7 distinct (post, rank) pairs), the root post held by
        # three bodies, and 2 of the naming law's 6 rungs carried by nobody and
        # unreachable by construction. A brief that asked for a thousand people
        # on three shifts produced that, and every rendering layer downstream
        # was correct: the crowd composer tallied what the membership IS and
        # handed the Director and the narrator "a dozen or so captains and
        # commanders pulling transit watch" on all 16 turns.
        #
        # Warnings, never rewrites, and never refusals. An institution of
        # nothing but post-holders is legal -- a two-person workshop is one --
        # and co-equal roots are legitimate. What it may not do is arrive
        # unremarked.
        ranks_by_post = {}
        carried_ranks = set()
        unposted = 0
        for body in state["bodies"].values():
            rank = str(body.get("rank") or "")
            if rank:
                carried_ranks.add(rank)
            home = str(body.get("home_post") or "")
            if not home:
                unposted += 1
                continue
            ranks_by_post.setdefault(home, set()).add(rank)
        # AN INSTITUTION MODELLED ONLY AS ITS COMMAND POSTS HAS NO RANK-AND-
        # FILE, and a hierarchy with no base is not a hierarchy. Where the only
        # way to become a member is to be minted into a post, membership size
        # is bounded by post count times whatever rotation floor generation
        # applies, and every member is by construction whatever the top of the
        # ladder is. The tell needs no new field: nobody stands outside a post,
        # rank follows the post, and there are MORE BODIES THAN POSTS -- an org
        # chart replicated into a population rather than a population organised
        # by one. That last clause is what keeps a small institution, which is
        # legitimately all offices, out of it.
        if (state["posts"] and state["bodies"] and not unposted
                and len(state["bodies"]) > len(state["posts"])
                and carried_ranks
                and all(len(ranks) == 1 for ranks in ranks_by_post.values())):
            warnings.append(
                f"{key}: all {len(state['bodies'])} bodies hold one of its "
                f"{len(state['posts'])} posts and rank follows the post, so "
                "this institution is its own command tier and has no "
                "rank-and-file; describe members who hold no post")
        # A rung nobody stands on is a rung the institution does not have.
        # Two of chat 95's six were unreachable by construction.
        defined_ranks = ((state.get("naming") or {}).get("titles")
                         or {}).get("ranks")
        if isinstance(defined_ranks, dict):
            for rank in sorted(set(map(str, defined_ranks)) - carried_ranks):
                warnings.append(
                    f"{key}: rank {rank!r} is named by the naming law and "
                    "carried by no body")
        # A POST IS A DUTY, NOT A HEADCOUNT, and a coverage floor applied to a
        # post that cannot rotate is the same defect as two bodies sharing a
        # display name -- one word resolving to two minds (docs/UNBUILT.md
        # 1.84b). Readable from `reports_to` alone, and only where a chain was
        # actually authored: every post reporting to nothing means no hierarchy
        # was declared, not that every post is a top.
        superiors = {post_key: str(post.get("reports_to") or "")
                     for post_key, post in state["posts"].items()}
        roots = [post_key for post_key, superior in superiors.items()
                 if not superior]
        if len(roots) == 1 and any(
                superior in state["posts"] for superior in superiors.values()):
            held_by = sorted(
                body_key for body_key, body in state["bodies"].items()
                if str(body.get("home_post") or "") == roots[0])
            if len(held_by) > 1:
                warnings.append(
                    f"{key}: post {roots[0]!r} is the root of the chain of "
                    f"command and {len(held_by)} bodies hold it {held_by}; a "
                    "post nobody reports to is an address, and an address "
                    "resolving to more than one mind is the collision this "
                    "already refuses for display names")
        if known_rooms:
            places = {
                str(entry.get("place") or "")
                for entry in list(state["upkeeps"].values())
                + list(state["posts"].values())
                + list(state["bodies"].values())
                if str(entry.get("place") or "")
            }
            places.update(str(place) for place in state.get("commons") or ()
                          if str(place))
            for place in sorted(places - known_rooms):
                warnings.append(
                    f"{key}: place {place!r} is not a room in this frame")
        # AN INSTITUTION THAT ONLY WORKS WHERE IT GOES. `posts` and `upkeeps`
        # say where the work is; `commons` says where a body may go for its own
        # sake, and with none named the whole off-duty population can only be
        # routed to somebody's workplace. Measured on chat 98: 7 work places
        # against 45 rooms, and the author had to invent an upkeep nobody
        # serves to make one lounge reachable. Legal -- a two-room workshop
        # genuinely has no commons -- so this is a warning and not a refusal,
        # and it is here because an empty authored field otherwise fails in
        # exactly the silent way `CLAUDE.md` records for psychology.
        rate = state.get("errand_rate")
        if (state["bodies"] and not state.get("commons")
                and (rate is None or float(rate) > 0.0)
                and known_rooms - {
                    str(entry.get("place") or "")
                    for entry in list(state["upkeeps"].values())
                    + list(state["posts"].values())}):
            warnings.append(
                f"{key}: no commons; every room it does not work in is a room "
                "circulation can never send an off-duty body to. Name the "
                "places people go for their own sake")
    return warnings


def _event_subject(event):
    return str(event.get("upkeep") or event.get("post")
               or event.get("body") or event.get("actor")
               or event.get("by") or event.get("holder")
               or event.get("commitment_id") or event.get("order_id")
               or event.get("good") or "institution")


def _event_surface(event):
    subject = _event_subject(event)
    kind = str(event.get("kind") or "institution_event")
    # WHOM THE ACT WAS DIRECTED AT, where the event names one. What a
    # bystander in the room perceives is an act between two people, and a
    # surface that says only "somebody gave aid" throws away half of what was
    # standing in front of them. Nothing from the institution's blame register
    # may join it: this string is what `_scheduled_row` puts on the objective
    # carrier rail for registered characters.
    toward = str(event.get("subject") or "")
    phrases = {
        "upkeep_out_of_band": f"{subject} fell below its operating floor",
        "upkeep_restored": f"{subject} returned to its operating band",
        "body_unable": f"{subject} became unable to continue",
        "body_recovered": f"{subject} recovered enough to continue",
        "post_filled_again": f"{subject} was staffed again",
        "post_unfilled": f"{subject} could not be staffed",
        "post_believed_filled": f"{subject} was believed staffed but was not",
        "incident": str(event.get("surface") or
                        f"an incident changed {subject}"),
        "stock_low": f"{subject} ran low",
        "stock_empty": f"{subject} ran out",
        "stock_restored": f"{subject} was restocked",
        "stock_surplus": f"{subject} became abundant",
        "goods_exchanged": f"{subject} changed hands",
        "institution_order_issued": f"{subject} issued an order",
        "institution_order_executed": f"{subject} carried out an order",
        "institution_order_failed": f"an order concerning {subject} failed",
        "commitment_fulfilled": f"{subject} fulfilled an undertaking",
        "commitment_disputed": f"{subject} disputed an undertaking",
        "commitment_released": f"{subject} released an undertaking",
        "commitment_repudiated": f"{subject} repudiated an undertaking",
        "commitment_defaulted": f"{subject} defaulted on an undertaking",
        "commitment_transferred": f"{subject} transferred an undertaking",
        "report_confirmed": f"{subject} confirmed a report",
        "report_refuted": f"{subject} refuted a report",
        "aid_given": (f"{subject} gave aid to {toward}" if toward
                      else f"{subject} gave aid"),
        "harm_done": (f"{subject} caused harm to {toward}" if toward
                      else f"{subject} caused harm"),
        "accusation": (f"{subject} accused {toward}" if toward
                       else f"{subject} made an accusation"),
        "apology": (f"{subject} made peace with {toward}" if toward
                    else f"{subject} made peace"),
    }
    return phrases.get(kind, f"{subject} changed state")


def _event_frame(payload):
    """Which era a scheduled charter event belongs to, `None` for the present.

    `_scheduled_row` writes `frame_id` straight into the payload, so an older
    row written before that field existed reads as the present -- which is
    where those stories were.
    """
    value = (payload or {}).get("frame_id")
    if value in (None, "", 0):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _scheduled_row(cid, frame_id, base_turn, epoch_id, charter_key, event,
                   due_at):
    kind = str(event.get("kind") or "institution_event")
    subject = _event_subject(event)
    location = str(event.get("place") or "")
    event_id = stable_event_key(
        "charter", cid, frame_id, charter_key, kind, subject,
        event.get("at_hours"))
    public = _event_surface(event) if kind in WITNESSABLE else ""
    payload = {
        "frame_id": frame_id,
        "what": _event_surface(event),
        "where": location,
        "where_kind": "room",
        "witnessed": public,
        "origin": {"charter": charter_key, "epoch_id": epoch_id},
        "originator": "",
        "base_turn": int(base_turn),
        "disposition": "resolved_fact",
        "charter_event": copy.deepcopy(event),
    }
    return {
        "event_id": event_id, "chat_id": cid, "due_at": float(due_at),
        "kind": "consequence", "location_id": location,
        "payload": json.dumps(payload, ensure_ascii=False),
        "seed": f"charter:{charter_key}:{epoch_id}", "status": "pending",
    }


def advance_snapshot(registry, *, elapsed_seconds, epoch_id, base_turn,
                     cid, frame_id, scene=None, cancelled=None):
    """Advance a copied registry and compose stable scheduled-event rows."""
    registry = normalize_registry(copy.deepcopy(registry))
    rows, produced = [], []
    elapsed_seconds = max(0.0, float(elapsed_seconds or 0.0))
    advanced_any = False
    for index, (key, item) in enumerate(sorted(registry["items"].items())):
        if cancelled is not None and cancelled.is_set():
            break
        previous_elapsed = item.get("last_elapsed_seconds")
        if previous_elapsed is None:
            item["last_elapsed_seconds"] = elapsed_seconds
            item["last_epoch_id"] = str(epoch_id)
            continue
        delta_hours = max(0.0, (elapsed_seconds - previous_elapsed) / 3600.0)
        if delta_hours <= 0.0 or item.get("last_epoch_id") == str(epoch_id):
            continue
        advanced_hours = min(delta_hours, MAX_CATCHUP_HOURS)
        state = copy.deepcopy(item["state"])
        if isinstance(scene, dict) and scene.get("rooms"):
            # The live scene owns the room graph. Charter retains background
            # body positions but never carries a competing adjacency map.
            if state.get("structure"):
                from world.structure import composed_scene, skeleton_rooms
                state["scene"] = composed_scene(
                    skeleton_rooms(cid, state["structure"], frame_id), scene)
            else:
                state["scene"] = copy.deepcopy(scene)
            # Registered-character movement is authoritative.  A bound body
            # remains in Charter only as an institutional projection, and its
            # place follows the scene instead of being advanced here.
            #
            # THE ONE BRIDGE BETWEEN TWO NAMESPACES, and it used to sit in a
            # bare `except Exception: pass`. It is the only line anywhere
            # that asserts a charter `place` and a scene room id are the same
            # vocabulary; with bodies walking the room graph that assertion
            # is load-bearing, so a failure here is logged with its cause,
            # and a room the charter's own graph does not contain is said
            # out loud rather than written into `place` for the mover to
            # fail on silently next window. The catch-up still proceeds:
            # one body's stale place is not a reason to freeze the town.
            from world.spatial import room_of
            charter_rooms = set((state["scene"] or {}).get("rooms") or {})
            for body_key, binding in (state.get("bindings") or {}).items():
                try:
                    room = (room_of(scene, binding.get("name"))
                            or room_of(scene, binding.get("entity_id")))
                except Exception as exc:
                    logger.warning(
                        "charter %s: bound body %s could not be located in "
                        "the scene (%s: %s); its place is not advanced",
                        key, body_key, type(exc).__name__, exc)
                    continue
                if not room or body_key not in state["bodies"]:
                    continue
                if charter_rooms and str(room) not in charter_rooms:
                    logger.warning(
                        "charter %s: bound body %s stands in scene room %r, "
                        "which the charter's graph does not contain; its "
                        "place is left at %r",
                        key, body_key, str(room),
                        state["bodies"][body_key].get("place"))
                    continue
                state["bodies"][body_key]["place"] = str(room)
                # A registered character walks under its own movement, so
                # whatever route Charter had it on is over.
                state["bodies"][body_key].pop("walk", None)
        before_hours = float(state.get("clock_hours") or 0.0)
        state, events = run(
            state, hours=advanced_hours,
            window=item["window_hours"],
            seed=int(stable_event_key(epoch_id, key)[-8:], 16),
        )
        item["state"] = state
        advanced_any = True
        item["last_elapsed_seconds"] = (
            previous_elapsed + advanced_hours * 3600.0)
        item["last_epoch_id"] = str(epoch_id)
        start_elapsed = previous_elapsed
        for event in events:
            offset_hours = max(
                0.0, float(event.get("at_hours") or before_hours)
                - before_hours)
            due_at = min(elapsed_seconds,
                         start_elapsed + offset_hours * 3600.0)
            stamped = {"charter": key, **copy.deepcopy(event)}
            produced.append(stamped)
            rows.append(_scheduled_row(
                cid, frame_id, base_turn, epoch_id, key, event, due_at))
    if advanced_any:
        cross_charter_gossip(registry)
    return registry, rows, produced


def cross_charter_gossip(registry, cap=CROSS_CHARTER_GOSSIP_CAP):
    """Let co-present bodies from different Charters trade one claim each.

    A Charter is an ownership boundary, not a soundproof wall.  This function
    chooses at most one representative per institution per occupied place,
    pairs actual co-present bodies, and uses the same ``hear_claim`` uptake
    door as internal Charter conversation.  Registers, needs, politics and
    non-news beliefs never cross.  Repeated windows rotate the representative,
    so a market spreads a story over time instead of teaching every head at
    once.
    """
    from world.charter_identity import display_name
    from world.charter_mind import cap_minds, hear_claim
    from world.charter_news import known_news, news_keys_in
    from world.charter_talk import RETOLD_RETENTION

    normalized = normalize_registry(registry)
    # The caller owns the snapshot that will be landed. Keep the helper's
    # mutation explicit rather than returning a second registry beside a
    # count and inviting one caller to forget which copy is authoritative.
    registry.clear()
    registry.update(normalized)
    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = CROSS_CHARTER_GOSSIP_CAP
    by_place = {}
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        placed = {}
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}) \
                    or not body.get("available", True):
                continue
            place = str(body.get("place") or "")
            if place:
                placed.setdefault(place, []).append(body_key)
        for place, body_keys in placed.items():
            # Rotate on the institution's own clock. Sparse and deterministic:
            # a thousand people at one fair still create one mouth per Charter.
            turn = int(float(state.get("clock_hours") or 0.0))
            body_key = body_keys[turn % len(body_keys)]
            body = state["bodies"][body_key]
            by_place.setdefault(place, []).append({
                "charter": charter_key, "body": body_key,
                "name": display_name(
                    body, roles.get(body_key) or (), state.get("naming")),
            })

    told = 0
    for place in sorted(by_place):
        people = sorted(by_place[place], key=lambda row: (
            row["charter"], row["body"]))
        if len(people) < 2:
            continue
        pairs = []
        seen = set()
        for index, left in enumerate(people):
            right = people[(index + 1) % len(people)]
            if left["charter"] == right["charter"]:
                continue
            pair_key = tuple(sorted(((left["charter"], left["body"]),
                                     (right["charter"], right["body"]))))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            pairs.append((left, right))
        for left, right in pairs:
            for speaker, listener in ((left, right), (right, left)):
                if told >= cap:
                    break
                source = registry["items"][speaker["charter"]]["state"]
                target = registry["items"][listener["charter"]]["state"]
                for claim in known_news(
                        source.get("minds") or {}, speaker["body"]):
                    if hear_claim(
                            target.setdefault("minds", {}), listener["body"],
                            claim, RETOLD_RETENTION, 1.0,
                            heard_from=speaker["name"]):
                        target["minds"] = cap_minds(target["minds"])
                        target["news_keys"] = sorted(
                            news_keys_in(target["minds"]))
                        told += 1
                        break
            if told >= cap:
                break
        if told >= cap:
            break
    return told


def land_snapshot(cid, frame_id, base_turn, epoch_id, registry, rows,
                  produced, *, expected_revision=None):
    """Atomically land state and consequences if the scheduling edge remains."""
    from core.db import (q, qtx, transaction, wget_for_frame,
                         wset_for_frame)

    with transaction():
        # All three checks run under the same write lock as landing. Reading
        # them before BEGIN leaves a gap where a turn commit, restore, or
        # author edit can invalidate the snapshot and then be overwritten.
        current_epoch = wget_for_frame(
            cid, "offscreen_epoch", frame_id, {}) or {}
        if str(current_epoch.get("epoch_id") or "") != str(epoch_id):
            logger.info("charter tick discarded: chat=%s epoch=%s changed",
                        cid, epoch_id)
            return {"advanced": 0, "events": 0,
                    "discarded": len(produced), "reason": "epoch_changed"}
        latest = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,),
                   one=True)
        current_turn = (latest["idx"] if latest
                        and latest["idx"] is not None else None)
        if jobs.story_rewound_past(base_turn, current_turn):
            logger.info("charter tick discarded: chat=%s base_turn=%s rewound",
                        cid, base_turn)
            return {"advanced": 0, "events": 0,
                    "discarded": len(produced), "reason": "rolled_back"}
        if expected_revision:
            current_registry = registry_for(cid, frame_id)
            if registry_revision(current_registry) != expected_revision:
                logger.info(
                    "charter tick discarded: chat=%s registry changed", cid)
                return {"advanced": 0, "events": 0,
                        "discarded": len(produced),
                        "reason": "registry_changed"}
        wset_for_frame(cid, CHARTERS_KEY, registry, frame_id)
        for row in rows:
            qtx(
                "INSERT OR IGNORE INTO scheduled_events"
                "(event_id,chat_id,due_at,kind,location_id,payload,seed,status) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (row["event_id"], row["chat_id"], row["due_at"], row["kind"],
                 row["location_id"], row["payload"], row["seed"],
                 row["status"]),
            )
    return {"advanced": len(registry["items"]), "events": len(produced),
            "scheduled": len(rows)}


def schedule_charter_ticks(ctx, epoch=None):
    """Queue deterministic institution catch-up for one committed epoch."""
    from core.db import wget_for_frame
    from story.scene import dialogue_config, offscreen_life_allows

    epoch = epoch if isinstance(epoch, dict) else {}
    if not epoch.get("opportunity") or not epoch.get("epoch_id"):
        return None
    cfg = dialogue_config(ctx.chat.id) or {}
    if not offscreen_life_allows(cfg.get("offscreen_life"), "deterministic"):
        epoch["charter_skip"] = "ceiling"
        return None
    cid, frame_id, base_turn = ctx.chat.id, ctx.turn.frame_id, ctx.turn.idx
    registry = registry_for_update(cid, frame_id)
    if not registry["items"]:
        epoch["charter_skip"] = "no_charters"
        return None
    scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
    epoch_id = str(epoch["epoch_id"])
    elapsed = float(epoch.get("elapsed_seconds") or 0.0)
    source_revision = registry_revision(registry)

    def _produce(job):
        advanced, rows, produced = advance_snapshot(
            registry, elapsed_seconds=elapsed, epoch_id=epoch_id,
            base_turn=base_turn, cid=cid, frame_id=frame_id, scene=scene,
            cancelled=job.cancelled)
        if job.cancelled.is_set():
            return {"advanced": 0, "events": 0, "cancelled": True}
        return land_snapshot(cid, frame_id, base_turn, epoch_id, advanced,
                             rows, produced,
                             expected_revision=source_revision)

    job = jobs.submit(cid, f"charter:{epoch_id}", _produce,
                      base_turn=base_turn)
    epoch["charter_scheduled"] = True
    epoch["charters"] = len(registry["items"])
    return job


def _place_views(registry, place):
    """Build room views from one immutable registry snapshot."""
    from world.charter import scene_ledger

    place = str(place or "")
    ledgers = []
    for key, item in sorted(registry["items"].items()):
        state = item["state"]
        occupied_places = {
            str(entry.get("place") or "")
            for collection in (state["upkeeps"], state["posts"],
                               state["bodies"])
            for entry in collection.values()
        }
        if place not in occupied_places:
            continue
        ledgers.append({"charter": key,
                        **scene_ledger(state, place, events=())})
    return ledgers[:3]


def place_view(cid, place, frame_id=None):
    """Capped objective/presence aperture for one currently encountered room."""
    return _place_views(registry_for(cid, frame_id), place)


def residue_facts(cid, place, frame_id=None, cap=3):
    """Present-state Charter facts suitable for the existing residue aperture."""
    facts = []
    registry = registry_for(cid, frame_id)
    for ledger in _place_views(registry, place):
        key = ledger["charter"]
        for upkeep, state in (ledger.get("place_state") or {}).items():
            if state.get("failing"):
                facts.append(
                    f"{upkeep} is currently below its operating floor "
                    f"within {key}.")
        charter_state = registry["items"][key]["state"]
        unfilled = ((charter_state.get("reported") or {})
                    .get("post_unfilled") or {})
        for post in ledger.get("posts_here") or ():
            if post in unfilled:
                facts.append(
                    f"The {post} duty remains unfilled ({unfilled[post]}).")
        for name, presence in (ledger.get("presences") or {}).items():
            if not presence.get("able"):
                facts.append(f"{name} is here but unable to continue working.")
        if len(facts) >= max(0, int(cap)):
            break
    return facts[:max(0, int(cap))]


def charter_diagnostics(cid, frame_id=None, *, charter_key="", body_key=""):
    """Author-only explanation surface; no result is delivered to a mind."""
    from core.db import q, wget_for_frame
    from world.charter_log import life_of, summarize

    registry = registry_for(cid, frame_id)
    events = []
    for row in q(
            "SELECT payload FROM scheduled_events WHERE chat_id=? "
            "AND seed LIKE 'charter:%' ORDER BY due_at DESC LIMIT 500", (cid,)):
        try:
            payload = json.loads(row["payload"] or "{}")
            # ONE ERA'S DIAGNOSTICS. `registry_for` above is frame-scoped and
            # this listing was not, so a story with frames explained its
            # present with events another era minted. `scheduled_events` has
            # no frame column -- the scoping rides in the payload, written by
            # `_scheduled_row` -- so the filter belongs here rather than in
            # the SQL. `None` is the present era on both sides.
            if _event_frame(payload) != (frame_id if frame_id else None):
                continue
            event = payload.get("charter_event")
            if isinstance(event, dict):
                event = {"charter": str(
                    (payload.get("origin") or {}).get("charter") or ""),
                    **event}
        except (TypeError, ValueError, json.JSONDecodeError):
            event = None
        if isinstance(event, dict):
            events.append(event)
    resident_histories = wget_for_frame(
        cid, "charter_resident_histories", frame_id, {}) or {}
    items = {}
    for key, item in sorted(registry["items"].items()):
        if charter_key and key != str(charter_key):
            continue
        state = item["state"]
        local_events = [e for e in events
                        if not e.get("charter") or e.get("charter") == key]
        entry = {
            "summary": summarize(state, local_events),
            "warnings": registry_warnings(
                {"items": {key: item}}, scene=state.get("scene"),
                cid=cid, frame_id=frame_id),
            "judgment_holders": len(state.get("judgments") or {}),
            "commitments": list((state.get("commitments") or {}).values()),
            "economy": copy.deepcopy(state.get("economy") or {}),
            "decisions": copy.deepcopy(state.get("decisions") or {}),
            "history": copy.deepcopy(state.get("history") or {}),
            "refused_interventions": copy.deepcopy(
                state.get("refused_interventions") or []),
            # WHAT THE CONSEQUENCE LAYER IS CARRYING. `statuses` needs at
            # least one honest reader on the day it lands; `triggers` needs
            # one for the same reason, and this is it. Author-only: rule ids
            # and counts, never the change rows themselves, because a
            # diagnostic that grows with the window is how a payload becomes
            # a transcript.
            "triggers": trigger_view(
                state.get("triggers"), state.get("pending_changes"),
                state.get("trigger_last")),
            "featured_resident_histories": {
                char_id: copy.deepcopy(history)
                for char_id, history in resident_histories.items()
                if isinstance(history, dict)
                and str((history.get("binding") or {}).get("charter") or "")
                == key
                and (not body_key or str(
                    (history.get("binding") or {}).get("body") or "")
                    == str(body_key))
            },
        }
        if body_key:
            entry["life"] = life_of(body_key, state, local_events)
            entry["believes"] = copy.deepcopy(
                (state.get("minds") or {}).get(str(body_key)) or {})
            entry["believed_by"] = {
                holder: copy.deepcopy(claims[str(body_key)])
                for holder, claims in (state.get("minds") or {}).items()
                if str(body_key) in claims}
            entry["judgments_by"] = copy.deepcopy(
                (state.get("judgments") or {}).get(str(body_key)) or {})
            entry["judgments_about"] = {
                holder: copy.deepcopy(subjects[str(body_key)])
                for holder, subjects in (state.get("judgments") or {}).items()
                if str(body_key) in subjects}
        items[key] = entry
    return {"items": items, "event_count": len(events)}


def carrier_entries(cid, frame_id=None):
    """Unpromoted Charter people shaped for ``story.carriers``.

    This is a projection, never a second knowledge store. Carrier modules may
    enumerate and copy these rows exactly as they do for full characters;
    ``save_carrier_state`` translates only newly acquired rows back into the
    owning body's sparse Charter mind.
    """
    from world.charter_identity import display_name, identity_aliases
    from world.charter_news import report_from_claim

    registry = registry_for(cid, frame_id)
    out = []
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        anchor = clock_anchor(item)
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}):
                continue
            place = str(body.get("place") or "")
            reports = []
            for claim in (state.get("minds") or {}).get(body_key, {}).values():
                row = report_from_claim(claim, current_location=place,
                                        anchor=anchor)
                if row is not None:
                    reports.append(row)
            aliases = identity_aliases(
                body, roles.get(body_key) or (), state.get("naming"))
            shown = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            out.append({
                "row": None,
                "charter": True,
                "charter_ref": {"charter": charter_key, "body": body_key},
                "name": shown,
                "uid": body_key,
                "aliases": list(dict.fromkeys(
                    [str(body.get("name") or ""), body_key, *aliases])),
                "room": place,
                "state": {"carried_reports": reports},
            })
    return out


def save_carrier_state(cid, entry, carrier_state, frame_id=None):
    """Land rows newly earned through the shared physical carrier rail."""
    ref = (entry or {}).get("charter_ref") or {}
    charter_key = str(ref.get("charter") or "")
    body_key = str(ref.get("body") or "")
    if not charter_key or not body_key:
        return False
    registry = registry_for_update(cid, frame_id)
    item = registry["items"].get(charter_key)
    if item is None or body_key not in item["state"]["bodies"] \
            or body_key in (item["state"].get("bindings") or {}):
        return False
    from world.charter_mind import cap_minds
    from world.charter_news import FIRSTHAND_PROVENANCE, claim_from_report

    state = item["state"]
    held = state.setdefault("minds", {}).setdefault(body_key, {})
    changed = False
    at_hours = float(state.get("clock_hours") or 0.0)
    anchor = clock_anchor(item)
    for report in (carrier_state or {}).get("carried_reports") or ():
        claim = claim_from_report(report, at_hours, anchor=anchor)
        if claim is None:
            continue
        current = held.get(claim["body"])
        if current is not None:
            current_firsthand = str(
                current.get("provenance") or "") in FIRSTHAND_PROVENANCE
            arriving_firsthand = str(
                claim.get("provenance") or "") in FIRSTHAND_PROVENANCE
            if current_firsthand or not arriving_firsthand \
                    and float(current.get("strength") or 0.0) >= float(
                        claim.get("strength") or 0.0):
                continue
        held[claim["body"]] = claim
        changed = True
    if not changed:
        return False
    state["minds"] = cap_minds(state.get("minds") or {})
    state["news_keys"] = sorted({
        subject for claims in state["minds"].values()
        for subject, claim in claims.items() if claim.get("kind") == "news"
    })
    item["state"] = state
    save_registry(cid, registry, frame_id)
    return True


def clock_anchor(item):
    """The pair `charter_news.charter_hours_of` converts with: this
    charter's hour clock and the simulation second it was last advanced to.
    `last_elapsed_seconds` is stamped 0.0 when presim lands and moved by
    `advance_snapshot`, so the two always describe the same instant. None
    for a charter never landed, and the converters pass numbers through."""
    item = item if isinstance(item, dict) else {}
    elapsed = item.get("last_elapsed_seconds")
    state = item.get("state") or {}
    if elapsed is None or state.get("clock_hours") is None:
        return None
    return {"clock_hours": float(state.get("clock_hours") or 0.0),
            "elapsed_seconds": float(elapsed or 0.0)}


def sight_figures_in_scene(cid, figures, *, frame_id=None):
    """Every unbound Charter body standing where a figure stands sees it.

    THE CO-PRESENCE CHANNEL, live. `charter_figure.sight_figures` is the
    rule -- presence is the whole test -- and it ran only inside offscreen
    windows over `state.figures`, which nothing in live play ever filled:
    measured on the Harrowmere playtest, `figures` was `{}` in all eight
    charters after forty turns, so a body the player stood in front of for
    a whole conversation held no claim about them unless the player also
    spoke or acted (`ingest_public_evidence`) or the body greeted them
    (`apply_presence_conduct`). Walking into a room is the channel a
    stranger is noticed by; this is that channel.

    ``figures`` is ``[{"key", "place", "label"}]``: the engine's canonical
    name, the room, and what a stranger sees. The claim is keyed by the
    name -- one subject per person, however they are dressed -- and its
    surface carries the label; `presence_view` renders the key back to
    each observer's own label, so the name reaches a voice only where
    recognition earned it.

    One cached read decides whether anything would change; the private
    parse and the save are paid only when a body gains or refreshes a
    claim (the same gate `ingest_public_evidence` keeps).
    """
    from world.charter_figure import sight_figures
    from world.charter_mind import cap_minds

    wanted = {}
    for figure in figures or ():
        if not isinstance(figure, dict):
            continue
        key = str(figure.get("key") or "").strip()
        place = str(figure.get("place") or "").strip()
        if not key or not place:
            continue
        wanted[key] = {"key": key, "place": place,
                       "surface": {"label": str(figure.get("label") or key)}}
    if not wanted:
        return {"figures": 0, "sighted": 0}

    def _unbound(state):
        bindings = state.get("bindings") or {}
        return {k: b for k, b in (state.get("bodies") or {}).items()
                if k not in bindings and k not in wanted}

    def _would_change(state):
        minds = state.get("minds") or {}
        for fig_key, figure in wanted.items():
            for body_key, body in _unbound(state).items():
                if str(body.get("place") or "") != figure["place"]:
                    continue
                current = (minds.get(body_key) or {}).get(fig_key)
                if current is None or current.get("heard_from") is not None \
                        or float(current.get("strength") or 0.0) < 1.0 \
                        or str(current.get("place") or "") != figure["place"]:
                    return True
        return False

    if not any(_would_change(item["state"])
               for item in registry_for(cid, frame_id)["items"].values()):
        return {"figures": len(wanted), "sighted": 0}
    registry = registry_for_update(cid, frame_id)
    sighted = 0
    for item in registry["items"].values():
        state = item["state"]
        if not _would_change(state):
            continue
        before = {h: set(c) for h, c in (state.get("minds") or {}).items()}
        minds = sight_figures(
            state.setdefault("minds", {}), _unbound(state), wanted,
            float(state.get("clock_hours") or 0.0))
        state["minds"] = cap_minds(minds)
        for holder, claims in state["minds"].items():
            sighted += len(set(claims) & set(wanted)
                           - before.get(holder, set()))
        item["state"] = state
    save_registry(cid, registry, frame_id)
    return {"figures": len(wanted), "sighted": sighted}


def load_caravan_freight(cid, request, origin, *, frame_id=None):
    """Take requested lots from a real market holder into a caravan.

    The Director may ask for freight but cannot mint it. ``from_holder`` must
    own stock at a market in the origin room; the actual loaded amount is
    bounded by that stock. One registry read/write for the whole request.
    """
    request = request if isinstance(request, dict) else {}
    wanted = request.get("stock") if isinstance(request.get("stock"), dict) \
        else {}
    source = str(request.get("from_holder") or "")
    if not source or not wanted:
        return {"stock": {}, "wants": dict(request.get("wants") or {}),
                "from_holder": source}, []
    from world.charter_economy import normalize_economy, trade

    registry = registry_for_update(cid, frame_id)
    def amount(value):
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    loaded, events = {}, []
    changed = False
    for item in registry["items"].values():
        state = item["state"]
        economy = normalize_economy(state.get("economy"))
        if not any(m["holder"] == source and m["place"] == str(origin)
                   for m in economy["markets"].values()):
            continue
        wagon = "__loading_caravan__"
        for good, quantity in wanted.items():
            economy, event, moved = trade(
                economy, seller=source, buyer=wagon, good=str(good),
                quantity=amount(quantity),
                at_hours=float(state.get("clock_hours") or 0.0),
                place=str(origin), reason="caravan_loading")
            if moved:
                loaded[str(good)] = loaded.get(str(good), 0.0) + moved
                events.append(event)
                changed = True
        economy["stocks"].pop(wagon, None)
        state["economy"] = economy
        item["state"] = state
        if loaded:
            break
    if changed:
        save_registry(cid, registry, frame_id)
    return {"stock": loaded,
            "wants": {str(k): amount(v) for k, v in
                      (request.get("wants") or {}).items()
                      if amount(v) > 0.0},
            "from_holder": source}, events


def exchange_caravan_freight(cid, freight, room, *, frame_id=None):
    """Exchange one wagon with authored markets at its physical stop."""
    from world.charter_economy import caravan_exchange

    registry = registry_for_update(cid, frame_id)
    changed = False
    events = []
    carried = copy.deepcopy(freight) if isinstance(freight, dict) else {}
    for item in registry["items"].values():
        state = item["state"]
        economy, carried_after, traded = caravan_exchange(
            state.get("economy"), carried, str(room),
            at_hours=float(state.get("clock_hours") or 0.0))
        if traded:
            from world.charter_news import news_keys_in, witness
            state["minds"], _witnessed = witness(
                state.get("minds") or {}, state.get("bodies") or {}, traded,
                float(state.get("clock_hours") or 0.0))
            state["news_keys"] = sorted(news_keys_in(state["minds"]))
            state["economy"] = economy
            item["state"] = state
            carried = carried_after
            events.extend(traded)
            changed = True
    if changed:
        save_registry(cid, registry, frame_id)
    return carried, events


def ingest_public_evidence(cid, evidence_rows, scene, *, turn_id,
                           frame_id=None, labels=None):
    """Deliver one resolved beat to the Charter bodies that sensed it.

    One registry read and one conditional write regardless of population or
    witness count.  The expensive/semantic work was already shared at resolve;
    this side is deterministic perception plus sparse claim insertion.

    ``labels`` (canonical actor name -> what a stranger sees) decides how a
    landed claim reads; ``unplaced`` in the result names actors the scene
    could not place, which is the one way this seam yields zero for
    everybody at once and used to do so silently.
    """
    from world.charter_observe import (apply_public_evidence,
                                       plan_public_evidence)

    rows = [row for row in (evidence_rows or ()) if isinstance(row, dict)]
    if not rows:
        return {"sources": 0, "opportunities": 0, "acquired": 0}
    # Appraise on the SHARED cached registry first: most beats reach no
    # Charter mind, and this runs inside the locked commit every turn a
    # beat resolved. Before the split, the no-acquisition case still paid
    # the private 41.4MB parse `registry_for_update` exists for (measured
    # 2026-08-28, chat 95, 307 bodies: ~1.1s of the commit stretch spent
    # parsing, then nothing saved). The appraisal only GATES -- when
    # something lands, the write below is computed entirely from the
    # private parse, so a wrong gate can cost a skipped save or a spare
    # parse, never a wrong stored byte.
    opportunities = acquired = 0
    unplaced = []
    for item in registry_for(cid, frame_id)["items"].values():
        plan = plan_public_evidence(item["state"], rows, scene or {}, turn_id,
                                    labels=labels)
        opportunities += int(plan["opportunities"])
        acquired += int(plan["acquired"])
        for actor in plan.get("unplaced") or ():
            if actor not in unplaced:
                unplaced.append(actor)
    if not acquired:
        return {"sources": len(rows), "opportunities": opportunities,
                "acquired": acquired, "unplaced": unplaced}
    registry = registry_for_update(cid, frame_id)
    opportunities = acquired = 0
    for item in registry["items"].values():
        state, metrics = apply_public_evidence(
            item["state"], rows, scene or {}, turn_id, labels=labels)
        item["state"] = state
        opportunities += int(metrics.get("opportunities") or 0)
        acquired += int(metrics.get("acquired") or 0)
    if acquired:
        save_registry(cid, registry, frame_id)
    return {"sources": len(rows), "opportunities": opportunities,
            "acquired": acquired, "unplaced": unplaced}


def _figure_labels(figures):
    """``{canonical key: label}`` from the figures a caller hands over.

    A bare string is a figure whose key and label coincide (a role, a
    description); a dict carries ``key`` -- the engine's canonical name,
    which the mind keys its claims by -- and ``label``, how THIS observer
    renders it (the name where recognition earned it, the stranger label
    otherwise). Keeping the two apart is what lets a body that met "the
    slight woman" this morning recognise her this afternoon under a new
    coat, and lets the name stay out of a payload where nobody said it.
    """
    out = {}
    for figure in figures or ():
        if isinstance(figure, dict):
            key = str(figure.get("key") or "").strip()
            label = str(figure.get("label") or key).strip()
        else:
            key = label = str(figure or "").strip()
        if key:
            out[key] = label or key
    return out


def _relabel(value, mapping):
    """Replace every string equal to a figure key -- as a dict key or a
    value -- with that observer's label, recursively. The presence slice is
    copied into a voiced payload, so a canonical name surviving anywhere in
    it (an acquaintance key, a judgment subject, a commitment party) is a
    name reaching a mind nothing told it to."""
    if not mapping:
        return value
    if isinstance(value, dict):
        return {mapping.get(k, k) if isinstance(k, str) else k:
                _relabel(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_relabel(v, mapping) for v in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def presence_view(cid, place, name, frame_id=None, figures=None):
    """Only what one Charter body earned, never its institution's register.

    ``figures`` are the scene-owned people standing here, as ``{key,
    label}`` (or a bare string where the two coincide); see
    `_figure_labels`. Everything returned is rendered in this observer's
    labels, and each affordance row aimed at a figure carries the canonical
    ``key`` beside its rendered ``other`` so the echo can be resolved
    without guessing.
    """
    out = []
    registry = registry_for(cid, frame_id)
    labels = _figure_labels(figures)
    for charter_key, body_key in _body_refs(registry, name=name):
        item = registry["items"][charter_key]
        state = copy.deepcopy(item["state"])
        body = state["bodies"].get(body_key) or {}
        if str(body.get("place") or "") != str(place or ""):
            continue
        # Scene-owned people are figures here: visible subjects with no mind
        # for Charter to read or simulate.  They exist only in this aperture;
        # a landed act may leave a claim about the encounter, but no copied
        # character mind survives the call.
        for figure, label in labels.items():
            if figure not in state["bodies"]:
                state.setdefault("figures", {})[figure] = {
                    "key": figure, "place": str(place or ""),
                    "surface": {"label": label},
                }
        from world.charter import (action_instances, opportunities,
                                   scene_ledger)
        focused = {body_key: body}
        opened = opportunities(
            focused, state.get("minds") or {}, state.get("needs") or {},
            events=(), practices=state.get("practices") or {},
            at_hours=float(state.get("clock_hours") or 0.0),
            figures={key: value for key, value in state["figures"].items()
                     if str(value.get("place") or "") == str(place or "")})
        state.setdefault("practices", {}).update(opened)
        presence = (scene_ledger(state, place, events=())
                    .get("presences", {}).get(body_key))
        if presence is None:
            continue
        # Exact typed options.  The model may echo one; prose can never
        # smuggle a Charter mutation through this seam. A row aimed at a
        # figure keeps the canonical key beside the rendered `other`.
        rows = []
        for row in (action_instances(state, actor=body_key)
                    .get(body_key) or [])[:6]:
            row = copy.deepcopy(row)
            other = str(row.get("other") or "")
            if other in labels:
                row["key"] = other
                row["other"] = labels[other]
                # The practice id embeds its parties' keys.
                if isinstance(row.get("practice"), str):
                    row["practice"] = row["practice"].replace(
                        other, labels[other])
            rows.append(row)
        out.append({
            "charter": charter_key,
            "body": body_key,
            "presence": _relabel(copy.deepcopy(presence), labels),
            "action_instances": rows,
        })
    return out[:2]


def _body_refs(registry, *, name=None, refs=None, include_bound=False):
    """Resolve an external presence to Charter body ids, without guessing."""
    wanted = str(name or "").strip().casefold()
    exact = set()
    for ref in refs or ():
        if isinstance(ref, dict) and ref.get("charter") and ref.get("body"):
            exact.add((str(ref["charter"]), str(ref["body"])))
    found = []
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        from world.charter_identity import display_name
        roles = {}
        for post, assigned in (state.get("watch") or {}).items():
            roles.setdefault(str(assigned), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}) and not include_bound:
                continue
            if exact:
                matches = (charter_key, body_key) in exact
            else:
                matches = bool(wanted) and wanted in {
                    str(body_key).casefold(),
                    str(body.get("name") or "").strip().casefold(),
                    display_name(body, roles.get(body_key) or (),
                                 state.get("naming")).casefold(),
                }
            if matches:
                found.append((charter_key, body_key))
    return found


def charter_place_ids(cid, frame_id=None) -> set:
    """Every place id the charter registry knows, for THIS frame.

    Exists so a caller can tell "no bodies here" from "no body could ever be
    here". `background_presence_records` filters by place and returns the same
    empty result either way, and the difference is the whole of a defect
    measured on chat 84: the scene's rooms and the registry's places shared no
    id, so 37 bodies were unreachable for fourteen turns and the subsystem
    read as unexercised.

    Read-only, and tolerant of a malformed registry: this is used by a
    diagnostic and must never be the reason a beat fails.
    """
    out = set()
    try:
        registry = registry_for(cid, frame_id)
    except Exception:
        return out
    for item in (registry.get("items") or {}).values():
        state = (item or {}).get("state") or {}
        for place in (state.get("active_places") or ()):
            if str(place or "").strip():
                out.add(str(place))
        for body in (state.get("bodies") or {}).values():
            if isinstance(body, dict):
                for field in ("place", "berth"):
                    value = str(body.get(field) or "").strip()
                    if value:
                        out.add(value)
    return out


def background_presence_records(cid, *, places=None, names=None,
                                frame_id=None):
    """Unpromoted Charter bodies as ordinary background-presence records.

    Records are derived apertures, not a second identity store.  Ambiguous
    display names are withheld until the fiction distinguishes them.
    """
    from world.charter_model import body_of_an_authored_mind
    registry = registry_for(cid, frame_id)
    place_set = {str(p) for p in (places or ()) if str(p or "")}
    name_set = {str(n).strip().casefold() for n in (names or ())
                if str(n or "").strip()}
    candidates = []
    counts = {}
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        from world.charter_identity import display_name
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            # An authored person is not an anonymous extra. Bound OR RESERVED
            # -- chat 95 was generated through `generate_lived_location(
            # featured_residents=...)`, which returns bindings for the caller
            # to apply, so `bindings` was empty and four registered cast
            # members' own bodies were derived here as background people.
            if body_of_an_authored_mind(state, body_key, body):
                continue
            display = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            place = str(body.get("place") or "")
            if place_set and place not in place_set:
                continue
            if name_set and display.casefold() not in name_set \
                    and body_key.casefold() not in name_set:
                continue
            counts[display.casefold()] = counts.get(display.casefold(), 0) + 1
            candidates.append((charter_key, body_key, display, place,
                               roles.get(body_key) or []))
    out = {}
    for charter_key, body_key, display, place, roles in candidates:
        if counts.get(display.casefold(), 0) != 1:
            continue
        role = (", ".join(roles) if roles else f"member of {charter_key}")
        out[display] = {
            "dialogue_turns": [], "mention_turns": [],
            "addressed_turns": [], "nature": "person",
            "charter_refs": [{"charter": charter_key, "body": body_key}],
            "sketch": {"role_hint": role, "station_room": place},
        }
    return out


def bodies_acting_toward_authored(cid, authored, frame_id=None):
    """Display names of unbound charter bodies whose last landed window held
    an act aimed at an authored mind's aperture.

    The Part C "acting" trigger's substrate half (DESIGN_BACKGROUND_
    PRESENTATION §C1.3): an act's ``other`` is a body key or a figure key,
    and it points at an authored mind exactly when it is a BOUND body (the
    body a registered character rides) or a scene figure whose key is an
    authored name (`presence_view` injects figures under exactly those
    keys, so a landed act toward one is recorded under it). "Last beat" is
    the last landed window, the same one-window lag every reader of
    ``window_acts`` already tolerates (§0's staleness note).

    Ambiguous display names are withheld, the same refusal as
    `background_presence_records`: a trigger that cannot say WHICH body it
    means must not voice either.
    """
    registry = registry_for(cid, frame_id)
    authored_cf = {str(a or "").strip().casefold() for a in (authored or ())
                   if str(a or "").strip()}
    acting = []
    counts = {}
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        bindings = set(state.get("bindings") or {})
        figure_keys = {str(k) for k in (state.get("figures") or {})
                       if str(k).casefold() in authored_cf}
        wanted = bindings | figure_keys
        actors = {str((row or {}).get("actor") or "")
                  for row in (state.get("window_acts") or [])
                  if str((row or {}).get("other") or "") in wanted}
        from world.charter_identity import display_name
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            display = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            counts[display.casefold()] = counts.get(display.casefold(), 0) + 1
            if body_key in actors and body_key not in bindings:
                acting.append(display)
    return {d for d in acting if counts.get(d.casefold(), 0) == 1}


def charter_entanglement_of(cid, refs, present, frame_id=None,
                            registry=None):
    """The B3 entanglement digest for one presented body: summed over its
    charter refs, against the authored minds present.

    Part C's overflow tie-break (§C3): among candidates whose triggers tie,
    the one with a tie, a debt or a grievance toward whoever is standing
    there speaks first -- the same score, from the same reader
    (`charter_practice.entanglement`), that picks who steps out of a derived
    crowd, so the two "who has a reason" questions cannot drift apart. A
    record with no charter refs scores 0.0 and falls through to the stable
    tie-break.
    """
    held = [r for r in (refs or ()) if isinstance(r, dict)]
    if not held:
        return 0.0
    from world.charter import entanglement

    if registry is None:
        registry = registry_for(cid, frame_id)
    total = 0.0
    for ref in held:
        item = (registry.get("items") or {}).get(
            str(ref.get("charter") or ""))
        if not item:
            continue
        total += entanglement(
            item["state"], str(ref.get("body") or ""), present)
    return total


def charter_emergence_pick(cid, charter_key, place, *, who="", present=(),
                           frame_id=None, turn_idx=None):
    """Who steps out of the derived charter crowd, as ``(display, reason)``.

    DESIGN_BACKGROUND_PRESENTATION §B3. The op may name somebody -- a display
    name or body key, resolved without guessing -- or name nobody and let the
    engine pick: candidates are ranked by `charter_practice.entanglement`
    with whoever is present, so the person who steps out of the crowd is the
    one with a reason to. Ties break on the body key, so a replay picks the
    same person.

    Candidates come through `background_presence_records`, which is the
    subtraction that matters: bound bodies are excluded there (a cast member
    coming out of the extras is a canon write nobody authored -- naming one
    in ``who`` therefore resolves to nobody and is refused), an ambiguous
    display name is withheld until the fiction distinguishes them, and a
    body already carrying a live presence record is not IN the crowd and is
    excluded here. Failing to pick returns a reason, never a guess.
    """
    from core.db import wget

    registry = registry_for(cid, frame_id)
    charter_key = str(charter_key or "")
    if charter_key not in (registry.get("items") or {}):
        return "", "no charter %r holds anyone here" % charter_key
    records = background_presence_records(
        cid, places={str(place or "")}, frame_id=frame_id)
    presented = set()
    for rec in (wget(cid, "background_presences", {}) or {}).values():
        if not isinstance(rec, dict):
            continue
        # A record past `PRESENTED_IDLE_BEATS` no longer presents its body
        # (§C3): the body is back in the crowd and may step out of it again
        # -- into the SAME record, because `with_charter_presences` resolves
        # by charter ref, so nothing is duplicated by the round trip.
        from world.charter_crowd import presented as _still_presented
        if turn_idx is not None and not _still_presented(rec, turn_idx):
            continue
        for ref in rec.get("charter_refs") or ():
            if isinstance(ref, dict) \
                    and str(ref.get("charter") or "") == charter_key:
                presented.add(str(ref.get("body") or ""))
    candidates = {}
    for display, rec in records.items():
        for ref in rec.get("charter_refs") or ():
            if str(ref.get("charter") or "") != charter_key:
                continue
            body_key = str(ref.get("body") or "")
            if body_key and body_key not in presented:
                candidates[body_key] = display
    if not candidates:
        return "", ("nobody in the %s crowd at %r can step out; whoever is "
                    "there is bound, already met, or not yet tellable apart"
                    % (charter_key, str(place or "")))
    wanted = " ".join(str(who or "").split()).casefold()
    if wanted:
        for body_key, display in sorted(candidates.items()):
            if wanted in {body_key.casefold(), display.casefold()}:
                return display, ""
        return "", ("%r names nobody in that crowd; leave who empty and the "
                    "engine picks" % str(who))
    from world.charter import entanglement

    state = registry["items"][charter_key]["state"]
    ranked = sorted(
        candidates,
        key=lambda key: (-entanglement(state, key, present), key))
    return candidates[ranked[0]], ""


def charter_speaker_records(cid, frame_id=None, *, include_bound=False):
    """All stable Charter speaker identities for render-time colour lookup.

    This is deliberately a flat O(bodies) projection.  It performs no model
    calls and stores no duplicate palette.  A thousand bodies are cheap; the
    transcript still colours only exact quotes that were actually spoken.
    """
    from world.charter_identity import (
        display_name, identity_aliases, identity_seed)

    registry = registry_for(cid, frame_id)
    out = []
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        roles = {}
        for post, assigned in (state.get("watch") or {}).items():
            roles.setdefault(str(assigned), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}) and not include_bound:
                continue
            name = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            if not name:
                continue
            out.append({
                "name": name,
                "aliases": identity_aliases(
                    body, roles.get(body_key) or (), state.get("naming")),
                "charter": charter_key,
                "body": body_key,
                "seed": identity_seed(charter_key, body_key),
                "color": str(body.get("dialogue_color") or ""),
                "place": str(body.get("place") or ""),
            })
    return out


def apply_presence_conduct(cid, name, conduct, *, record=None, frame_id=None,
                           allowed=None, place=""):
    """Land one exact background-authored Charter act, or refuse it."""
    conduct = conduct if isinstance(conduct, dict) else {}
    act, other = str(conduct.get("act") or ""), str(conduct.get("other") or "")
    if not act or not other:
        return None
    permitted = {(str(row.get("act") or ""), str(row.get("other") or ""))
                 for row in (allowed or ()) if isinstance(row, dict)}
    if (act, other) not in permitted:
        return {"actor": str(name), "act": act, "other": other,
                "refused": "not_offered_to_scene_life"}
    # The model echoed the rendered label; the offer row that licensed it
    # carries the canonical key (`presence_view`), which is what the mind
    # keys the encounter by. Without this the greet path minted a second
    # subject under the label beside the one sighting and evidence keep.
    shown = other
    other = next((str(row.get("key")) for row in (allowed or ())
                  if isinstance(row, dict) and row.get("key")
                  and (str(row.get("act") or ""),
                       str(row.get("other") or "")) == (act, shown)),
                 other)
    registry = registry_for_update(cid, frame_id)
    refs = (record or {}).get("charter_refs") or ()
    matches = _body_refs(registry, name=name, refs=refs)
    if len(matches) != 1:
        return {"actor": str(name), "act": act, "other": other,
                "refused": "ambiguous_charter_identity"}
    charter_key, body_key = matches[0]
    from world.charter import authored
    original = registry["items"][charter_key]["state"]
    state = copy.deepcopy(original)
    temporary_figure = other not in state["bodies"]
    if temporary_figure:
        state.setdefault("figures", {})[other] = {
            "key": other, "place": str(place or ""),
            "surface": {"label": shown},
        }
    state, result = authored(state, body_key, act, other)
    if temporary_figure:
        state.setdefault("figures", {}).pop(other, None)
    registry["items"][charter_key]["state"] = state
    save_registry(cid, registry, frame_id)
    return {"charter": charter_key, "body": body_key, **result}


def _charter_events(cid, charter_key, frame_id=None):
    """Fired objective Charter events only; never a private runtime cache."""
    from core.db import q
    if frame_id is None:
        rows = q("SELECT payload FROM world_events WHERE chat_id=? "
                 "AND frame_id IS NULL ORDER BY occurred_at", (cid,))
    else:
        rows = q("SELECT payload FROM world_events WHERE chat_id=? "
                 "AND frame_id=? ORDER BY occurred_at", (cid, frame_id))
    out = []
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        origin = payload.get("origin") or {}
        event = payload.get("charter_event")
        if str(origin.get("charter") or "") == str(charter_key) \
                and isinstance(event, dict):
            out.append(event)
    return out


def promotion_bundle(cid, name, *, record=None, frame_id=None,
                     promoted_turn=None):
    """The one Charter life this tracked presence can legitimately carry.

    ``promoted_turn`` stamps the inherited place graph: every node the town
    hands over is "last seen" at the turn the character was minted, which is
    what `commit_place_graph`'s eviction order needs to forget the streets
    never walked before the ones that were.
    """
    registry = registry_for(cid, frame_id)
    refs = (record or {}).get("charter_refs") or ()
    matches = _body_refs(registry, name=name, refs=refs)
    if len(matches) != 1:
        return None
    charter_key, body_key = matches[0]
    from world.charter import promotion_handoff
    handoff = promotion_handoff(
        body_key, registry["items"][charter_key]["state"],
        events=_charter_events(cid, charter_key, frame_id))
    body = registry["items"][charter_key]["state"]["bodies"][body_key]
    state = registry["items"][charter_key]["state"]
    from world.charter_identity import display_name
    roles = {}
    for post, assigned in (state.get("watch") or {}).items():
        roles.setdefault(str(assigned), []).append(str(post))
    social_names = {
        key: display_name(value, roles.get(key) or (), state.get("naming"))
        for key, value in state["bodies"].items()}
    for key, figure in (state.get("figures") or {}).items():
        surface = figure.get("surface") or {}
        social_names[key] = str(surface.get("name") or surface.get("label")
                                or key)
    from world.charter_identity import identity_seed
    from world.charter_promote import inherited_place_graph
    return {"charter": charter_key, "body": body_key,
            "place": str(body.get("place") or ""), "handoff": handoff,
            # The town's public graph plus the routes this body walked, in
            # `chat_chars.state.place_graph`'s own shape. Empty when the
            # institution has no scene: there is no graph to inherit, and
            # the promoted mind learns its map by walking as any other does.
            "place_graph": inherited_place_graph(
                state, body_key, turn_idx=promoted_turn),
            "social_names": social_names,
            "dialogue_color": str(body.get("dialogue_color") or ""),
            "dialogue_color_seed": identity_seed(charter_key, body_key)}


def bind_promoted_character(cid, bundle, *, char_id, name, entity_id="",
                            promoted_turn=None, place="", frame_id=None):
    """Retire Charter cognition while retaining the institutional projection."""
    if not isinstance(bundle, dict):
        return False
    charter_key, body_key = bundle.get("charter"), bundle.get("body")
    registry = registry_for_update(cid, frame_id)
    item = registry["items"].get(str(charter_key))
    if item is None or str(body_key) not in item["state"]["bodies"]:
        return False
    state = item["state"]
    body_key = str(body_key)
    state.setdefault("bindings", {})[body_key] = {
        "char_id": int(char_id), "entity_id": str(entity_id or ""),
        "name": str(name), "promoted_turn": promoted_turn,
    }
    state["bodies"][body_key]["name"] = str(name)
    if place:
        state["bodies"][body_key]["place"] = str(place)
    # `marks` is here for the same reason the other four are: a Charter-window
    # scoring bias is cognition, and cognition belongs to the registered
    # character from this point. It is deliberately NOT in
    # `charter_promote.promotion_handoff` either -- the character tier has no
    # reader for a temporary institutional status, and a field nothing reads is
    # the dead weight this design exists to avoid.
    for store in ("minds", "needs", "feel", "heard_blame", "marks"):
        (state.get(store) or {}).pop(body_key, None)
    for store in ("experiences", "habit_runs"):
        (state.get(store) or {}).pop(body_key, None)
    state["bodies"][body_key].pop("private_habits", None)
    (state.get("judgments") or {}).pop(body_key, None)
    # A tie is cognition, so the promoted body's own ties retire with the rest
    # of its head. Ties OTHERS hold ABOUT it stay, exactly as their judgments
    # and their claims about it stay one and three lines up: the institution
    # keeps its view of a person who has become a character, and that person's
    # relationships are the character tier's from here.
    (state.get("ties") or {}).pop(body_key, None)
    state["practices"] = {
        key: practice for key, practice in (state.get("practices") or {}).items()
        if body_key not in set((practice.get("roles") or {}).values())
    }
    item["state"] = normalize_charter(state)
    save_registry(cid, registry, frame_id)
    return True
