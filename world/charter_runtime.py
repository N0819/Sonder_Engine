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
import json

from core import jobs
from core.logging_utils import logger
from world.charter import normalize_charter, run
from world.charter_news import WITNESSABLE
from world.mechanics import stable_event_key


CHARTERS_KEY = "charters"
REGISTRY_VERSION = 1
DEFAULT_WINDOW_HOURS = 4.0
MAX_CATCHUP_HOURS = 720.0

#: Different institutions sharing one place exchange through a few actual
#: bodies, never by merging registers or broadcasting to both populations.
CROSS_CHARTER_GOSSIP_CAP = 8


def _window_hours(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = DEFAULT_WINDOW_HOURS
    return max(0.25, min(24.0, value))


def normalize_registry(stored):
    """Normalize author definitions and runtime markers into one JSON shape."""
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
    for key, raw in raw_items.items():
        raw = raw if isinstance(raw, dict) else {}
        state = raw.get("state") if isinstance(raw.get("state"), dict) else raw
        state = normalize_charter(state)
        state["key"] = str(state.get("key") or key)
        last = raw.get("last_elapsed_seconds")
        try:
            last = None if last is None else max(0.0, float(last))
        except (TypeError, ValueError):
            last = None
        items[str(key)] = {
            "state": state,
            "window_hours": _window_hours(raw.get("window_hours")),
            "last_elapsed_seconds": last,
            "last_epoch_id": str(raw.get("last_epoch_id") or ""),
        }
    # Older development snapshots may contain ``recent_events``. Deliberately
    # discard it: incidents have one durable home, scheduled_events ->
    # world_events. The Charter registry stores current simulation state only.
    return {"version": REGISTRY_VERSION, "items": items}


def registry_for(cid, frame_id=None):
    from core.db import wget_for_frame
    return normalize_registry(
        wget_for_frame(cid, CHARTERS_KEY, frame_id, {}) or {})


def save_registry(cid, stored, frame_id=None):
    """Persist an explicitly authored registry in one temporal frame."""
    from core.db import wset_for_frame
    normalized = normalize_registry(stored)
    wset_for_frame(cid, CHARTERS_KEY, normalized, frame_id)
    return normalized


def registry_revision(registry):
    """Stable identity for the exact author/runtime state a job advanced."""
    encoded = json.dumps(normalize_registry(registry), sort_keys=True,
                         ensure_ascii=False, separators=(",", ":"))
    return stable_event_key("charter_registry", encoded)


def registry_warnings(registry, scene=None):
    """Author-facing validation; warnings never silently rewrite a Charter."""
    registry = normalize_registry(registry)
    rooms = set((scene or {}).get("rooms") or {})
    warnings = []
    for key, item in registry["items"].items():
        state = item["state"]
        from story.dialogue_colors import normalize_color
        from world.charter_identity import display_name
        if not state["upkeeps"]:
            warnings.append(f"{key}: no upkeeps; this institution has no goal")
        if not state["posts"]:
            warnings.append(f"{key}: no posts; no upkeep can be serviced")
        if not state["bodies"]:
            warnings.append(f"{key}: no bodies; every post will be unfilled")
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
        if rooms:
            places = {
                str(entry.get("place") or "")
                for entry in list(state["upkeeps"].values())
                + list(state["posts"].values())
                + list(state["bodies"].values())
                if str(entry.get("place") or "")
            }
            for place in sorted(places - rooms):
                warnings.append(
                    f"{key}: place {place!r} is not a room in this frame")
    return warnings


def _event_subject(event):
    return str(event.get("upkeep") or event.get("post")
               or event.get("body") or "institution")


def _event_surface(event):
    subject = _event_subject(event)
    kind = str(event.get("kind") or "institution_event")
    phrases = {
        "upkeep_out_of_band": f"{subject} fell below its operating floor",
        "upkeep_restored": f"{subject} returned to its operating band",
        "body_unable": f"{subject} became unable to continue",
        "body_recovered": f"{subject} recovered enough to continue",
        "post_filled_again": f"{subject} was staffed again",
        "post_unfilled": f"{subject} could not be staffed",
        "post_believed_filled": f"{subject} was believed staffed but was not",
    }
    return phrases.get(kind, f"{subject} changed state")


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
            state["scene"] = copy.deepcopy(scene)
            # Registered-character movement is authoritative.  A bound body
            # remains in Charter only as an institutional projection, and its
            # place follows the scene instead of being advanced here.
            try:
                from world.spatial import room_of
                for body_key, binding in (state.get("bindings") or {}).items():
                    room = (room_of(scene, binding.get("name"))
                            or room_of(scene, binding.get("entity_id")))
                    if room and body_key in state["bodies"]:
                        state["bodies"][body_key]["place"] = str(room)
            except Exception:
                pass
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
    registry = registry_for(cid, frame_id)
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
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}):
                continue
            place = str(body.get("place") or "")
            reports = []
            for claim in (state.get("minds") or {}).get(body_key, {}).values():
                row = report_from_claim(claim, current_location=place)
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
    registry = registry_for(cid, frame_id)
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
    for report in (carrier_state or {}).get("carried_reports") or ():
        claim = claim_from_report(report, at_hours)
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


def ingest_public_evidence(cid, evidence_rows, scene, *, turn_id,
                           frame_id=None):
    """Deliver one resolved beat to the Charter bodies that sensed it.

    One registry read and one conditional write regardless of population or
    witness count.  The expensive/semantic work was already shared at resolve;
    this side is deterministic perception plus sparse claim insertion.
    """
    from world.charter_observe import apply_public_evidence

    rows = [row for row in (evidence_rows or ()) if isinstance(row, dict)]
    if not rows:
        return {"sources": 0, "opportunities": 0, "acquired": 0}
    registry = registry_for(cid, frame_id)
    opportunities = acquired = 0
    for item in registry["items"].values():
        state, metrics = apply_public_evidence(
            item["state"], rows, scene or {}, turn_id)
        item["state"] = state
        opportunities += int(metrics.get("opportunities") or 0)
        acquired += int(metrics.get("acquired") or 0)
    if acquired:
        save_registry(cid, registry, frame_id)
    return {"sources": len(rows), "opportunities": opportunities,
            "acquired": acquired}


def presence_view(cid, place, name, frame_id=None, figures=None):
    """Only what one Charter body earned, never its institution's register."""
    out = []
    registry = registry_for(cid, frame_id)
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
        for figure in figures or ():
            figure = str(figure or "").strip()
            if figure and figure not in state["bodies"]:
                state.setdefault("figures", {})[figure] = {
                    "key": figure, "place": str(place or ""),
                    "surface": {"label": figure},
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
        out.append({
            "charter": charter_key,
            "body": body_key,
            "presence": copy.deepcopy(presence),
            # Exact typed options.  The model may echo one; prose can never
            # smuggle a Charter mutation through this seam.
            "action_instances": copy.deepcopy(
                (action_instances(state, actor=body_key).get(body_key) or [])[:6]),
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


def background_presence_records(cid, *, places=None, names=None,
                                frame_id=None):
    """Unpromoted Charter bodies as ordinary background-presence records.

    Records are derived apertures, not a second identity store.  Ambiguous
    display names are withheld until the fiction distinguishes them.
    """
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
            if body_key in (state.get("bindings") or {}):
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
    registry = registry_for(cid, frame_id)
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
            "surface": {"label": other},
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


def promotion_bundle(cid, name, *, record=None, frame_id=None):
    """The one Charter life this tracked presence can legitimately carry."""
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
    from world.charter_identity import identity_seed
    return {"charter": charter_key, "body": body_key,
            "place": str(body.get("place") or ""), "handoff": handoff,
            "dialogue_color": str(body.get("dialogue_color") or ""),
            "dialogue_color_seed": identity_seed(charter_key, body_key)}


def bind_promoted_character(cid, bundle, *, char_id, name, entity_id="",
                            promoted_turn=None, place="", frame_id=None):
    """Retire Charter cognition while retaining the institutional projection."""
    if not isinstance(bundle, dict):
        return False
    charter_key, body_key = bundle.get("charter"), bundle.get("body")
    registry = registry_for(cid, frame_id)
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
    for store in ("minds", "needs", "feel", "heard_blame"):
        (state.get(store) or {}).pop(body_key, None)
    state["practices"] = {
        key: practice for key, practice in (state.get("practices") or {}).items()
        if body_key not in set((practice.get("roles") or {}).values())
    }
    item["state"] = normalize_charter(state)
    save_registry(cid, registry, frame_id)
    return True
