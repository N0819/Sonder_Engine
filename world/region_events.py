"""Region events: one change over a REGION of the map, at once or over time.

The owner's ask (plan § 5 Phase C): "big disaster events like large regions
of a story map being damaged at once or sequentially over time". One op
class with three parts, each closed onto the engine's own vocabulary:

* a FOOTPRINT -- rooms named by registry id, the rooms of named structures,
  and a graph radius from an epicentre over passable edges plus the plan's
  topology -- resolved to an ordered set of ``(room, hops)``;
* a PROFILE in time -- ``at_once`` (every room on one beat), a ``front``
  that advances one ring of hops per window at an authored rate, or a
  ``decay`` that revisits the whole footprint at falling intensity -- as a
  list of WAVES with a due story-second each;
* PER-ROOM EFFECTS, each landing through a seam that already exists: a
  hazard state on the room short of ruin, ruin itself (the room retired in
  the registry and kept as a ruin in the scene, never deleted), a shock to
  every upkeep served there (`charter_intervene`), harm to bodies standing
  there by the harm model (`charter_harm`), displacement of bodies whose
  berth is gone, artifacts left as evidence (`story/artifacts`), and news
  the Director renders where the player is (`story/authored_events`).

What this module never does: write a mind, move a major character, or tell
the player anything. A body in the footprint is hurt by the same function a
wolf hurts it with; an institution reads the shock the way it reads a bad
week; the player meets the event when the Director renders the beat the
news comes due in. The room authors the circumstance; the world answers.

The package clock is the fuse (`story/plot_packages.fire_due_clocks`): the
first wave lands when the clock fires and the rest ride the op's own record
until each is due. A rewind past the fire restores the frame's world row,
so the waves un-fire with the package and land again when due.
"""

from __future__ import annotations

import hashlib

#: Caps, every one the owner's to move. Rooms one event may cover.
REGION_FOOTPRINT_CAP = 64
#: Hops from an epicentre a radius may reach.
REGION_RADIUS_CAP = 6
#: Story hours a profile may spread over.
REGION_RAMP_HOURS_CAP = 24.0 * 30
#: A front's pace, in rings of hops per story hour.
REGION_FRONT_RATE_CAP = 8.0
REGION_FRONT_RATE_MIN = 0.05
#: Intensity at or above which a room is RUINED rather than damaged.
DESTROY_THRESHOLD = 0.8
#: The share of bodies standing in a room that harm may reach at full
#: intensity, and never more than this many bodies in one story hour.
HARM_FRACTION_MAX = 0.5
HARM_BODIES_PER_HOUR = 12
#: Artifacts one wave may leave.
ARTIFACTS_PER_WAVE = 2
#: A decay revisits at this share of the last wave's intensity, and stops
#: below the floor.
DECAY_FACTOR = 0.5
DECAY_FLOOR = 0.1
#: Waves one event may hold, whatever the profile asks.
WAVES_CAP = 48

MODES = ("at_once", "front", "decay")
HARM_OUTCOMES = ("hurt", "dead", "missing")


def _text(value, limit=200):
    return " ".join(str(value or "").split())[:limit]


def _number(value, default=0.0):
    from .charter_model import number
    return number(value, default)


def normalize_region_event(op):
    """The closed shape, refused rather than guessed. ``label`` says what
    kind of change it is in the author's words (a fire, a flood, a siege --
    illustrations, not a list to match); the profile and effects are the
    engine's numbers."""
    op = op if isinstance(op, dict) else {}
    label = _text(op.get("label") or op.get("kind"), 80)
    if not label:
        raise ValueError("region_event says what kind of change it is (label)")
    fp = op.get("footprint") if isinstance(op.get("footprint"), dict) else {}
    rooms = [_text(r, 120) for r in (fp.get("rooms") or ()) if _text(r, 120)]
    structures = [_text(s, 120) for s in (fp.get("structures") or ()) if _text(s, 120)]
    epicentre = _text(fp.get("epicentre"), 120)
    radius = int(_number(fp.get("radius_hops"), 0))
    if not rooms and not structures and not epicentre:
        raise ValueError("region_event's footprint names rooms, structures, or "
                         "an epicentre with a radius")
    if radius < 0 or radius > REGION_RADIUS_CAP:
        raise ValueError("region_event radius_hops is 0..%d" % REGION_RADIUS_CAP)
    if epicentre and radius == 0 and not rooms and not structures:
        radius = 1
    pr = op.get("profile") if isinstance(op.get("profile"), dict) else {}
    mode = _text(pr.get("mode"), 20) or "at_once"
    if mode not in MODES:
        raise ValueError("region_event profile mode is one of %s" % ", ".join(MODES))
    intensity = _number(pr.get("intensity"), 0.5)
    if intensity <= 0.0 or intensity > 1.0:
        raise ValueError("region_event intensity is 0 < intensity <= 1")
    ramp = _number(pr.get("ramp_hours"), 0.0)
    if ramp < 0.0 or ramp > REGION_RAMP_HOURS_CAP:
        raise ValueError("region_event ramp_hours is 0..%g" % REGION_RAMP_HOURS_CAP)
    rate = _number(pr.get("rate_rooms_per_hour"), 1.0)
    if mode == "front" and not (REGION_FRONT_RATE_MIN <= rate <= REGION_FRONT_RATE_CAP):
        raise ValueError("region_event front rate is %g..%g rings of hops per hour"
                         % (REGION_FRONT_RATE_MIN, REGION_FRONT_RATE_CAP))
    if mode == "decay" and ramp <= 0.0:
        raise ValueError("region_event decay needs ramp_hours > 0 to spread over")
    ef = op.get("effects") if isinstance(op.get("effects"), dict) else {}
    harm = ef.get("harm") if isinstance(ef.get("harm"), dict) else None
    if harm is not None:
        outcome = _text(harm.get("outcome"), 20) or "hurt"
        if outcome not in HARM_OUTCOMES:
            raise ValueError("region_event harm outcome is one of %s"
                             % ", ".join(HARM_OUTCOMES))
        fraction = _number(harm.get("fraction"), HARM_FRACTION_MAX)
        harm = {"outcome": outcome,
                "fraction": max(0.0, min(HARM_FRACTION_MAX, fraction))}
    destroy = ef.get("destroy")
    effects = {
        "damage": _text(ef.get("damage"), 60) or label,
        "destroy": bool(destroy) if destroy is not None
        else intensity >= DESTROY_THRESHOLD,
        "shock": max(0.0, min(1.0, _number(ef.get("shock"), intensity))),
        "harm": harm,
        "displace": bool(ef.get("displace", True)),
        "artifacts": [_text(a, 80) for a in (ef.get("artifacts") or ())
                      if _text(a, 80)][:ARTIFACTS_PER_WAVE * 4],
        "news": _text(ef.get("news"), 200),
    }
    return {
        "label": label,
        "footprint": {"rooms": rooms, "structures": structures,
                      "epicentre": epicentre, "radius_hops": radius},
        "profile": {"mode": mode, "intensity": intensity, "ramp_hours": ramp,
                    "rate_rooms_per_hour": rate},
        "effects": effects,
    }


def harms_a_body(event):
    """Whether the event can hurt anyone: harm named, or ruin (a ruined
    room's occupants are harmed by the ruin at the event's intensity)."""
    return bool(event["effects"].get("harm")) or bool(event["effects"].get("destroy"))


# ---------------------------------------------------------------------------
# Footprint
# ---------------------------------------------------------------------------

def _graph(cid, scene):
    from world.spatial import passable_neighbors
    from world.structure import planned_topology
    graph = {str(k): {str(v) for v in vs}
             for k, vs in passable_neighbors(scene).items()}
    for rid, others in planned_topology(cid).items():
        for other in others:
            graph.setdefault(rid, set()).add(other)
            graph.setdefault(other, set()).add(rid)
    return graph


def resolve_footprint(cid, scene, footprint, *, known=None):
    """``[(room_id, hops)]`` sorted by hops then id. ``known`` is the set of
    room ids the world holds (scene plus plan); a named room outside it is
    an error the caller reports. Containment rooms (the inside of a body,
    `parent_entity`) are never in a footprint: where the world puts a body
    is the Director's, and it is transient."""
    from world.structure import planned_room_ids
    rooms = (scene or {}).get("rooms") or {}
    contained = {str(r) for r, room in rooms.items()
                 if isinstance(room, dict) and room.get("parent_entity")}
    known = set(known if known is not None else rooms) | set(planned_room_ids(cid))
    hops = {}
    unknown = []
    for rid in footprint.get("rooms") or ():
        if rid in known:
            hops.setdefault(rid, 0)
        else:
            unknown.append(rid)
    if footprint.get("structures"):
        from world.structure import skeleton_rooms
        for key in footprint["structures"]:
            found = (skeleton_rooms(cid, key) or {}).get("rooms") or {}
            if not found:
                unknown.append("structure %s" % key)
            for rid in found:
                hops.setdefault(str(rid), 0)
    epi = footprint.get("epicentre")
    if epi:
        if epi not in known:
            unknown.append(epi)
        else:
            graph = _graph(cid, scene)
            seen, frontier = {epi: 0}, [epi]
            for hop in range(1, int(footprint.get("radius_hops") or 0) + 1):
                nxt = []
                for node in frontier:
                    for other in sorted(graph.get(node, ())):
                        if other not in seen:
                            seen[other] = hop
                            nxt.append(other)
                frontier = nxt
            for rid, hop in seen.items():
                hops[rid] = min(hops.get(rid, hop), hop)
    ordered = sorted(((r, h) for r, h in hops.items() if r not in contained),
                     key=lambda x: (x[1], x[0]))
    return ordered[:REGION_FOOTPRINT_CAP], unknown


# ---------------------------------------------------------------------------
# Waves
# ---------------------------------------------------------------------------

def plan_waves(event, ordered, start_elapsed):
    """The event as waves: ``[{rooms, due_elapsed, intensity}]``.

    ``at_once``: one wave, due now. ``front``: one wave per ring of hops,
    the ring at ``h`` due ``h / rate`` hours after the start (the epicentre
    ring now). ``decay``: the whole footprint again at each step of the
    ramp, intensity falling by `DECAY_FACTOR` until `DECAY_FLOOR`.
    """
    mode = event["profile"]["mode"]
    intensity = float(event["profile"]["intensity"])
    start = float(start_elapsed or 0.0)
    rooms = [r for r, _h in ordered]
    if not rooms:
        return []
    if mode == "at_once":
        return [{"rooms": rooms, "due_elapsed": start, "intensity": intensity}]
    if mode == "front":
        rate = float(event["profile"]["rate_rooms_per_hour"])
        rings = {}
        for rid, hop in ordered:
            rings.setdefault(int(hop), []).append(rid)
        waves = []
        for hop in sorted(rings):
            waves.append({"rooms": rings[hop],
                          "due_elapsed": start + (hop / rate) * 3600.0,
                          "intensity": intensity})
        return waves[:WAVES_CAP]
    ramp = float(event["profile"]["ramp_hours"])
    waves, level, step = [], intensity, 0
    while level >= DECAY_FLOOR and len(waves) < WAVES_CAP:
        waves.append({"rooms": rooms,
                      "due_elapsed": start + step * (ramp * 3600.0) / max(
                          1, _decay_steps(intensity)),
                      "intensity": round(level, 4)})
        level *= DECAY_FACTOR
        step += 1
    return waves


def _decay_steps(intensity):
    steps, level = 0, float(intensity)
    while level >= DECAY_FLOOR and steps < WAVES_CAP:
        steps += 1
        level *= DECAY_FACTOR
    return max(1, steps - 1)


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------

def _draw(*parts):
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8"))
               .hexdigest()[:8], 16) / 0xFFFFFFFF


def apply_wave(cid, frame_id, event, wave, *, turn_idx, turn_id, elapsed,
               by="writers_room"):
    """Land one wave through the seams. Returns what happened, per effect.
    Everything here is a fact about the world; nothing is a line to a mind."""
    from core.db import qi, wget, wget_for_frame, wset, wset_for_frame
    label = event["label"]
    effects = event["effects"]
    intensity = float(wave.get("intensity") or event["profile"]["intensity"])
    rooms = [str(r) for r in wave.get("rooms") or ()]
    destroy = bool(effects.get("destroy")) and intensity >= DESTROY_THRESHOLD
    report = {"rooms": rooms, "intensity": intensity, "damaged": [],
              "ruined": [], "shocked": [], "harmed": [], "displaced": [],
              "artifacts": [], "news": 0}

    # 1. The rooms: a hazard state short of ruin, or ruin kept as a ruin.
    scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
    live = scene.get("rooms") or {}
    for rid in rooms:
        room = live.get(rid)
        if not isinstance(room, dict):
            continue
        state = "ruined" if destroy else effects["damage"]
        room["hazard"] = {"state": state, "cause": label,
                          "intensity": round(intensity, 3),
                          "since_elapsed": float(elapsed or 0.0), "by": by}
        if destroy:
            room["ruined"] = True
            report["ruined"].append(rid)
        else:
            report["damaged"].append(rid)
    if report["damaged"] or report["ruined"]:
        wset_for_frame(cid, "scene", scene, frame_id)
    if destroy and turn_id is not None:
        for rid in report["ruined"]:
            qi("UPDATE room_registry SET retired_turn_id=? WHERE chat_id=? "
               "AND room_uid=? AND retired_turn_id IS NULL", (turn_id, cid, rid))

    # 2. The institutions: shocks, harm, displacement.
    try:
        from world.charter_runtime import registry_for_update, save_registry
        registry = registry_for_update(cid, frame_id)
    except Exception:
        registry = None
    if registry and (registry.get("items") or {}):
        from world.charter_harm import apply_harm, is_gone
        from world.charter_intervene import normalize_interventions
        wave_rooms = set(rooms)
        ruined = set(report["ruined"])
        harmed_total = 0
        for key in sorted(registry["items"]):
            charter = registry["items"][key]["state"]
            at = float(charter.get("clock_hours") or 0.0)
            # Shock every upkeep served in the footprint.
            if effects["shock"] > 0.0:
                rows = list(charter.get("interventions") or ())
                for ukey, upkeep in sorted((charter.get("upkeeps") or {}).items()):
                    if str(upkeep.get("place") or "") not in wave_rooms:
                        continue
                    rows.append({
                        "id": "region:%s:%s:%d" % (_slug(label), ukey, int(turn_idx or 0)),
                        "op": "upkeep_shock", "at_hours": at, "upkeep": ukey,
                        "delta": -round(effects["shock"] * intensity, 4),
                        "place": str(upkeep.get("place") or ""),
                        "surface": label, "cause": "region event: " + label})
                    report["shocked"].append("%s/%s" % (key, ukey))
                charter["interventions"] = normalize_interventions(rows)
            # Harm bodies standing in the footprint, by the harm model.
            harm = effects.get("harm")
            if harm or destroy:
                outcome = (harm or {}).get("outcome") or ("dead" if destroy else "hurt")
                fraction = float((harm or {}).get("fraction", HARM_FRACTION_MAX))
                if destroy and not harm:
                    fraction = HARM_FRACTION_MAX
                present = sorted(
                    b for b, body in (charter.get("bodies") or {}).items()
                    if str(body.get("place") or "") in wave_rooms
                    and not is_gone(body) and not body.get("departed"))
                quota = int(round(len(present) * fraction * intensity))
                carried = list(charter.get("carried_events") or ())
                for victim in present:
                    if quota <= 0 or harmed_total >= HARM_BODIES_PER_HOUR:
                        break
                    if _draw(cid, label, key, victim, turn_idx) > fraction * intensity:
                        continue
                    charter, events = apply_harm(
                        charter, victim, by="region:" + _slug(label), at_hours=at,
                        outcome=outcome, cause=label, copy_state=False)
                    carried.extend(events)
                    report["harmed"].append("%s/%s:%s" % (key, victim, outcome))
                    quota -= 1
                    harmed_total += 1
                charter["carried_events"] = carried
            # Displace bodies whose berth is a ruin.
            if effects.get("displace") and ruined:
                standing = sorted({str(p.get("place") or "")
                                   for p in (charter.get("posts") or {}).values()
                                   if str(p.get("place") or "") not in ruined}
                                  | {str(c) for c in (charter.get("commons") or ())
                                     if str(c) not in ruined})
                for bkey, body in sorted((charter.get("bodies") or {}).items()):
                    if str(body.get("berth") or "") in ruined and not is_gone(body):
                        body["berth"] = standing[0] if standing else ""
                        if str(body.get("place") or "") in ruined:
                            body["place"] = body["berth"]
                        report["displaced"].append("%s/%s" % (key, bkey))
            registry["items"][key]["state"] = charter
        save_registry(cid, registry, frame_id)

    # 3. Evidence left, and news the Director renders where the player is.
    if effects.get("artifacts") and rooms:
        from story.artifacts import ARTIFACTS_WORLD_KEY, MAX_ARTIFACTS, POSTED, new_artifact
        stored = wget_for_frame(cid, ARTIFACTS_WORLD_KEY, frame_id, []) or []
        posted = sum(1 for a in stored if isinstance(a, dict) and a.get("status") == POSTED)
        for i, description in enumerate(effects["artifacts"][:ARTIFACTS_PER_WAVE]):
            if posted >= MAX_ARTIFACTS:
                break
            artifact = new_artifact(cid, room=rooms[i % len(rooms)],
                                    turn=int(turn_idx or 0),
                                    description=description, report={}, posted_by="")
            artifact["authored"] = by
            stored = [a for a in stored if isinstance(a, dict)
                      and a.get("uid") != artifact["uid"]] + [artifact]
            posted += 1
            report["artifacts"].append(artifact["uid"])
        wset_for_frame(cid, ARTIFACTS_WORLD_KEY, stored, frame_id)
    summary = effects.get("news") or "%s reaches %s" % (
        label, ", ".join(_room_name(live, r) for r in rooms[:4]))
    from story.authored_events import mint_authored_events
    report["news"] = mint_authored_events(
        cid, int(turn_idx or 0), [{"summary": summary, "due_in_turns": 1}],
        source=by)
    notices = wget(cid, "engine_notices", []) or []
    notices.append("%s: %d room(s) damaged, %d ruined, %d body(ies) harmed."
                   % (label, len(report["damaged"]), len(report["ruined"]),
                      len(report["harmed"])))
    wset(cid, "engine_notices", notices)
    return report


def _room_name(rooms, rid):
    room = rooms.get(rid) if isinstance(rooms, dict) else None
    return str((room or {}).get("name") or rid) if isinstance(room, dict) else str(rid)


def _slug(text):
    import re
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").casefold()).strip("_")[:40]
