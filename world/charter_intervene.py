"""Author-tier physical interventions for Charter and presimulation.

The allowlist stops an authoring model from writing conclusions into minds,
relationships, politics, decisions, or commitments. It may alter material
circumstance; ordinary simulation must still turn that circumstance into
events, witnessing, reports, judgment and institutional response.

TWO FAMILIES OF OP. The three that shipped first (`drift_dial`,
`need_shock`, `upkeep_shock`) move a number the institution already keeps.
The ones added for creatures (``docs/design/DESIGN_CREATURES_AS_CHARTER.md``
§5) move a fact the institution already keeps, and are the same kind of
thing: `relocate` moves every berth, `creature_dial` turns an authored dial,
`watch_shock` and `watch_stand_down` raise and lower a temporary watch at a
place. Each is closed, normalized, and refused with a notice rather than
dropped. A `charter_trigger` rule may schedule any of them (`intervene`),
which is how "member killed -> move the lair" is one authored row.
"""

from __future__ import annotations

from .charter_model import number as _number, integer as _integer


INTERVENTION_OPS = frozenset({
    "drift_dial", "need_shock", "upkeep_shock",
    "relocate", "creature_dial", "watch_shock", "watch_stand_down",
})
INTERVENTION_CAP = 64

#: What a mobilisation reads as when the institution authored nothing
#: (`normalize_mobilisation`). Every one is a cap or a rate and every one is
#: an institution's own to set: a frontier town and a complacent one are the
#: same code with different numbers.
#:
#: `MOBILISATION_CREDENCE` is the strength a threat claim must hold in the
#: head of a body with standing over the watch before it calls the watch
#: out. Strength already carries regard and retelling
#: (`charter_mind.hear_claim`), so a stranger's word weighs less than a
#: known body's by construction.
MOBILISATION_CREDENCE = 0.6
#: How long a called watch stands before it lapses.
MOBILISATION_HOURS = 48.0
#: The fraction of the institution's available bodies a call may pull.
MOBILISATION_CREW_FRACTION = 0.25
#: And never more than this many, whatever the fraction says.
MOBILISATION_CREW_CAP = 12
#: The temporary upkeep a called watch serves. It starts EMPTY under a HIGH
#: floor so the planner fills its posts first (urgency is distance to floor
#: over drift), which is what pulls crew off their ordinary posts and makes
#: the ordinary upkeeps drift -- the cost the owner asked for by name.
MOBILISATION_UPKEEP_FLOOR = 0.9
MOBILISATION_UPKEEP_DRIFT = 0.05
MOBILISATION_UPKEEP_SERVICE = 0.5

#: The post `authority` word that lets an office call the watch out.
MOBILISE_AUTHORITY = "mobilise"

#: Claim kinds a body with standing reads as a threat to a place. The
#: engine's own harm vocabulary, nothing else.
THREAT_KINDS = frozenset({"harm_done", "stock_taken"})


def normalize_mobilisation(stored):
    """How this institution answers a threat. Absent fields read as the
    named defaults above."""
    stored = stored if isinstance(stored, dict) else {}
    from .charter_model import normalize_competence

    return {
        "credence": max(0.0, min(1.0, _number(
            stored.get("credence"), MOBILISATION_CREDENCE))),
        "duration_hours": max(1.0, _number(
            stored.get("duration_hours"), MOBILISATION_HOURS)),
        "crew_fraction": max(0.0, min(1.0, _number(
            stored.get("crew_fraction"), MOBILISATION_CREW_FRACTION))),
        "crew_cap": max(1, _integer(stored.get("crew_cap"),
                                    MOBILISATION_CREW_CAP)),
        "requires": normalize_competence(stored.get("requires")),
    }


def normalize_interventions(stored):
    rows = []
    for index, raw in enumerate(stored or ()):
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "")
        row = {
            "id": str(raw.get("id") or f"intervention:{index}"),
            "op": op,
            "at_hours": max(0.0, _number(raw.get("at_hours"))),
            "cause": str(raw.get("cause") or "")[:240],
        }
        for field in ("charter", "upkeep", "body", "need", "place", "surface",
                      "to", "field", "called_by", "evidence", "from_place"):
            if raw.get(field) is not None:
                row[field] = str(raw.get(field) or "")[:320]
        for field in ("delta", "drift_per_hour", "until_hours"):
            if raw.get(field) is not None:
                row[field] = _number(raw.get(field))
        if raw.get("crew") is not None:
            row["crew"] = max(0, _integer(raw.get("crew")))
        if isinstance(raw.get("requires"), dict):
            from .charter_model import normalize_competence
            row["requires"] = normalize_competence(raw.get("requires"))
        if op not in INTERVENTION_OPS:
            row["refused"] = "unknown intervention op"
        rows.append(row)
    rows.sort(key=lambda row: (row["at_hours"], row["id"]))
    return rows[:INTERVENTION_CAP]


def intervention_warnings(stored):
    return [
        f"{row['id']}: {row['refused']} ({row['op']!r})"
        for row in normalize_interventions(stored) if row.get("refused")
    ]


def watch_post_key(place, index):
    return "watch:%s:%d" % (str(place), int(index))


def watch_upkeep_key(place):
    return "guard:%s" % str(place)


def _apply_relocate(charter, row):
    """Every berth of the institution moves to ``to``: a named room, or the
    nearest room on the creature's own graph that is not the current lair
    (`charter_creature.creature_neighbors`). Bodies standing at the old
    lair are moved with it; a body elsewhere walks home to the new one on
    its own through `charter_move.homecomings`."""
    bodies = charter.get("bodies") or {}
    old = next((str(b.get("berth") or "") for b in bodies.values()
                if b.get("berth")), "")
    target = str(row.get("to") or "nearest")
    scene = charter.get("scene") or {}
    rooms = (scene.get("rooms") or {}) if isinstance(scene, dict) else {}
    if target == "nearest":
        if not old or not rooms:
            return None, "no lair or no graph to move it on"
        from .charter_creature import creature_neighbors
        neighbors = creature_neighbors(scene, charter.get("creature"))
        # Places this institution works at are not lairs.
        working = {str(p.get("place") or "")
                   for p in (charter.get("posts") or {}).values()}
        seen, frontier, found = {old}, [old], ""
        while frontier and not found:
            nxt = []
            for room in frontier:
                for other in sorted(neighbors.get(room, ())):
                    if other in seen:
                        continue
                    seen.add(other)
                    if other not in working and not (
                            rooms.get(other) or {}).get("parent_entity"):
                        found = other
                        break
                    nxt.append(other)
                if found:
                    break
            frontier = nxt
        target = found
    if not target or (rooms and target not in rooms):
        return None, "no room to move the lair to"
    for body in bodies.values():
        if str(body.get("berth") or "") == old or not body.get("berth"):
            body["berth"] = target
        if old and str(body.get("place") or "") == old:
            body["place"] = target
            body.pop("walk", None)
    return {"kind": "lair_moved", "at_hours": float(row["at_hours"]),
            "place": target, "from": old, "cause": row.get("cause", "")}, ""


def apply_due(charter, through_hours):
    """Apply each due physical operation once and return emitted incidents."""
    pending, events, refused = [], [], []
    through = float(through_hours)
    for row in normalize_interventions(charter.get("interventions")):
        if row.get("refused"):
            refused.append(dict(row))
            continue
        if float(row["at_hours"]) > through:
            pending.append(row)
            continue
        op = row["op"]
        if op == "drift_dial":
            upkeep = (charter.get("upkeeps") or {}).get(row.get("upkeep"))
            if upkeep is None:
                refused.append(dict(row, refused="unknown upkeep"))
                continue
            # THE REVERT RESTORES WHAT THE DIAL FOUND, not zero. The first
            # version scheduled the end of a dial as `drift_per_hour: 0.0`,
            # so every dialled upkeep stopped drifting forever when the dial
            # ended -- "dormant for three days" would have been dormant for
            # good. A dial that is itself a revert carries the original.
            was = float(upkeep.get("drift_per_hour") or 0.0)
            upkeep["drift_per_hour"] = max(
                0.0, float(row.get("drift_per_hour") or 0.0))
            until = row.get("until_hours")
            if until is not None and float(until) > through:
                pending.append({
                    "id": row["id"] + ":revert", "op": "drift_dial",
                    "at_hours": float(until), "upkeep": row.get("upkeep", ""),
                    "drift_per_hour": was,
                    "cause": "end of " + str(row.get("cause") or "dial"),
                })
        elif op == "need_shock":
            body, need = row.get("body"), row.get("need")
            held = (charter.get("needs") or {}).get(body, {}).get(need)
            if held is None:
                refused.append(dict(row, refused="unknown body need"))
                continue
            held["level"] = max(0.0, min(
                1.0, float(held.get("level") or 0.0)
                + float(row.get("delta") or 0.0)))
        elif op == "upkeep_shock":
            upkeep_key = row.get("upkeep")
            upkeep = (charter.get("upkeeps") or {}).get(upkeep_key)
            if upkeep is None:
                refused.append(dict(row, refused="unknown upkeep"))
                continue
            upkeep["level"] = max(0.0, min(
                1.0, float(upkeep.get("level") or 0.0)
                + float(row.get("delta") or 0.0)))
            events.append({
                "kind": "incident", "at_hours": float(row["at_hours"]),
                "place": str(row.get("place") or upkeep.get("place") or ""),
                "upkeep": str(upkeep_key),
                "surface": str(row.get("surface") or
                               f"a disruption affected {upkeep_key}"),
                "cause": str(row.get("cause") or ""),
                "intervention_id": row["id"],
            })
        elif op == "relocate":
            event, why = _apply_relocate(charter, row)
            if event is None:
                refused.append(dict(row, refused=why))
                continue
            events.append(event)
        elif op == "creature_dial":
            creature = charter.get("creature")
            field = str(row.get("field") or "")
            if not isinstance(creature, dict) or field not in (
                    "boldness", "encounter_odds"):
                refused.append(dict(row, refused="no such creature dial"))
                continue
            creature[field] = max(0.0, min(
                1.0, float(creature.get(field) or 0.0)
                + float(row.get("delta") or 0.0)))
        elif op == "watch_shock":
            place = str(row.get("place") or "")
            crew = int(row.get("crew") or 0)
            standing = charter.setdefault("mobilisations", {})
            if not place or crew <= 0:
                refused.append(dict(row, refused="a watch needs a place and "
                                                 "a crew"))
                continue
            if place in standing:
                refused.append(dict(row, refused="the watch already stands "
                                                 "there"))
                continue
            from .charter_model import normalize_post, normalize_upkeep
            until = row.get("until_hours")
            until = float(until) if until is not None \
                else float(row["at_hours"]) + MOBILISATION_HOURS
            upkeep_key = watch_upkeep_key(place)
            charter.setdefault("upkeeps", {})[upkeep_key] = normalize_upkeep(
                upkeep_key, {
                    "place": place, "level": 0.0,
                    "floor": MOBILISATION_UPKEEP_FLOOR,
                    "drift_per_hour": MOBILISATION_UPKEEP_DRIFT,
                    "service_per_hour": MOBILISATION_UPKEEP_SERVICE,
                    "requires": row.get("requires") or {}})
            priority = [p for p in (charter.get("priority") or ())
                        if p != upkeep_key]
            charter["priority"] = [upkeep_key] + priority
            post_keys = []
            for index in range(crew):
                post_key = watch_post_key(place, index)
                charter.setdefault("posts", {})[post_key] = normalize_post(
                    post_key, {"place": place, "serves": [upkeep_key],
                               "requires": row.get("requires") or {},
                               "purpose": "the watch called out"})
                post_keys.append(post_key)
            standing[place] = {
                "since": float(row["at_hours"]), "until": until,
                "called_by": str(row.get("called_by") or ""),
                "posts": post_keys, "upkeep": upkeep_key,
                "harm_seen": False, "crew": crew,
                "evidence": str(row.get("evidence") or ""),
            }
            pending.append({
                "id": row["id"] + ":stand_down", "op": "watch_stand_down",
                "at_hours": until, "place": place,
                "cause": "end of " + str(row.get("cause") or "the watch"),
            })
            events.append({
                "kind": "mobilisation_called",
                "at_hours": float(row["at_hours"]),
                "place": str(row.get("from_place") or place),
                "about": str(row.get("called_by") or ""),
                "actor": str(row.get("called_by") or ""),
                "body": str(row.get("called_by") or ""),
                "subject": place, "crew": crew, "until_hours": until,
            })
        elif op == "watch_stand_down":
            place = str(row.get("place") or "")
            record = (charter.get("mobilisations") or {}).get(place)
            if not isinstance(record, dict):
                refused.append(dict(row, refused="no watch stands there"))
                continue
            for post_key in record.get("posts") or ():
                (charter.get("posts") or {}).pop(post_key, None)
                (charter.get("watch") or {}).pop(post_key, None)
            (charter.get("upkeeps") or {}).pop(record.get("upkeep"), None)
            charter["priority"] = [p for p in (charter.get("priority") or ())
                                   if p != record.get("upkeep")]
            charter["mobilisations"].pop(place, None)
            events.append({
                "kind": "mobilisation_lapsed",
                "at_hours": float(row["at_hours"]), "place": place,
                "about": str(record.get("called_by") or ""),
                "actor": str(record.get("called_by") or ""),
                "body": str(record.get("called_by") or ""),
                "subject": place,
                "false_alarm": not bool(record.get("harm_seen")),
            })
    charter["interventions"] = normalize_interventions(pending)
    charter["refused_interventions"] = refused[-24:]
    return charter, events


__all__ = [
    "INTERVENTION_OPS", "MOBILISATION_CREDENCE", "MOBILISATION_CREW_CAP",
    "MOBILISATION_CREW_FRACTION", "MOBILISATION_HOURS",
    "MOBILISATION_UPKEEP_DRIFT", "MOBILISATION_UPKEEP_FLOOR",
    "MOBILISATION_UPKEEP_SERVICE", "MOBILISE_AUTHORITY", "THREAT_KINDS",
    "apply_due", "intervention_warnings", "normalize_interventions",
    "normalize_mobilisation", "watch_post_key", "watch_upkeep_key",
]
