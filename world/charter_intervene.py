"""Author-tier physical interventions for Charter and presimulation.

The allowlist stops an authoring model from writing conclusions into minds,
relationships, politics, decisions, or commitments. It may alter material
circumstance; ordinary simulation must still turn that circumstance into
events, witnessing, reports, judgment and institutional response.
"""

from __future__ import annotations

from .charter_model import number as _number


INTERVENTION_OPS = frozenset({"drift_dial", "need_shock", "upkeep_shock"})
INTERVENTION_CAP = 64


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
        for field in ("charter", "upkeep", "body", "need", "place", "surface"):
            if raw.get(field) is not None:
                row[field] = str(raw.get(field) or "")[:320]
        for field in ("delta", "drift_per_hour", "until_hours"):
            if raw.get(field) is not None:
                row[field] = _number(raw.get(field))
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
            upkeep["drift_per_hour"] = max(
                0.0, float(row.get("drift_per_hour") or 0.0))
            until = row.get("until_hours")
            if until is not None and float(until) > through:
                pending.append({
                    "id": row["id"] + ":revert", "op": "drift_dial",
                    "at_hours": float(until), "upkeep": row.get("upkeep", ""),
                    "drift_per_hour": 0.0,
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
    charter["interventions"] = normalize_interventions(pending)
    charter["refused_interventions"] = refused[-24:]
    return charter, events


__all__ = [
    "INTERVENTION_OPS", "apply_due", "intervention_warnings",
    "normalize_interventions",
]
