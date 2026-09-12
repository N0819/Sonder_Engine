"""Pure compilation of specialist transforms into one chronological diff.

The Director decides causality and routes spans. Specialists describe state
changes. This module is the boundary between those two model-authored layers
and the world: it accepts every valid transform, orders them by the engine's
chronology, and reduces them without making a narrative judgement.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from world.spatial import _merge_entity, _merge_room


# Ordered-operation ledgers preserve every entry. Object maps instead preserve
# every transform in ``history`` while exposing the latest compiled snapshot.
LIST_CHANNELS = frozenset({
    "cast_changes", "introductions", "world_facts", "public_evidence",
    "crowd_ops", "courier_ops", "telling_ops", "charter_ops",
    "ratified_claims", "contradicted_claims", "contact_ops",
    "contact_action_ops", "substance_ops", "remove_entities",
    "inventory_ops", "artifact_ops", "sensory_events", "remove_rooms",
    "remove_adjacent", "comms_ops", "following_ops", "claim_dispositions",
    "consequences",
})

LIST_MAP_CHANNELS = frozenset({"conditions", "overlays"})


def _merge_record(previous: Any, current: Any) -> Any:
    """Merge snapshots without interpreting their domain meaning.

    A later scalar or list is the current value. Nested objects retain fields
    the later transform did not mention and replace fields it did. The full
    before/after chain remains in the returned history, so no transform is
    discarded merely because a later one supersedes its current value.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return deepcopy(current)
    merged = deepcopy(previous)
    for key, value in current.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_record(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _merge_attire_record(previous: Any, current: Any) -> Any:
    """Reduce sequential wardrobe operations without losing their order.

    Most keyed channels are snapshots, where the later field is the current
    value. Attire also carries ``add``/``remove`` operations. Folding two of
    those by ordinary dict replacement would discard the first transform;
    merely concatenating both lists would make commit's fixed add-then-remove
    order reverse a later re-add. Keep the last operation per garment while
    preserving unrelated fields. Whole-wardrobe ``wearing``/``replace`` rows
    reset the preceding operation plan, as they do when applied sequentially.
    The uncollapsed transforms remain available in history.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return deepcopy(current)
    merged = deepcopy(previous)
    has_delta = bool(current.get("add") or current.get("remove"))
    has_wearing_snapshot = (
        current.get("wearing") is not None
        and not has_delta
        and not isinstance(current.get("replace"), list)
    )
    if has_wearing_snapshot:
        for key in ("add", "remove", "replace"):
            merged.pop(key, None)
    elif isinstance(current.get("replace"), list):
        for key in ("wearing", "add", "remove"):
            merged.pop(key, None)
    elif has_delta and merged.get("wearing") is not None \
            and not merged.get("add") and not merged.get("remove") \
            and not isinstance(merged.get("replace"), list):
        merged["replace"] = list(merged.pop("wearing") or [])

    operations = {
        "add": list(merged.get("add") or []),
        "remove": list(merged.get("remove") or []),
    }
    for action in ("add", "remove"):
        opposite = "remove" if action == "add" else "add"
        for garment in current.get(action) or []:
            operations[opposite] = [
                held for held in operations[opposite] if held != garment
            ]
            if garment not in operations[action]:
                operations[action].append(deepcopy(garment))

    for key, value in current.items():
        if key in ("add", "remove"):
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_record(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    for action, values in operations.items():
        if values or action in current or action in merged:
            merged[action] = values
    return merged


def _merge_channel(compiled: dict, channel: str, value: Any) -> None:
    if channel in LIST_CHANNELS:
        rows = value if isinstance(value, list) else []
        compiled.setdefault(channel, []).extend(deepcopy(rows))
        return

    if channel in LIST_MAP_CHANNELS:
        if not isinstance(value, dict):
            return
        target = compiled.setdefault(channel, {})
        for object_id, rows in value.items():
            if not isinstance(rows, list):
                continue
            target.setdefault(str(object_id), []).extend(deepcopy(rows))
        return

    if isinstance(value, dict):
        target = compiled.setdefault(channel, {})
        if not isinstance(target, dict):
            target = {}
            compiled[channel] = target
        for object_id, record in value.items():
            key = str(object_id)
            previous = target.get(key)
            if channel == "rooms" and isinstance(previous, dict) \
                    and isinstance(record, dict):
                target[key] = _merge_room(previous, record, key)
            elif channel == "entities" and isinstance(previous, dict) \
                    and isinstance(record, dict):
                target[key] = _merge_entity(key, previous, record)
            elif channel == "attire":
                target[key] = _merge_attire_record(previous, record)
            else:
                target[key] = _merge_record(previous, record)
        return

    # Scalar channels such as ``location`` replace their current value. The
    # uncollapsed causal history above still retains every earlier transform.
    compiled[channel] = deepcopy(value)


def _stamp_from_event(channel: str, value: Any, chrono_id: int) -> Any:
    """Attach chronology where a channel's own shape has room for it."""
    copied = deepcopy(value)
    if channel in LIST_CHANNELS and isinstance(copied, list):
        for row in copied:
            if isinstance(row, dict) and not row.get("from_event"):
                row["from_event"] = chrono_id
    elif channel in LIST_MAP_CHANNELS and isinstance(copied, dict):
        for rows in copied.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict) and not row.get("from_event"):
                    row["from_event"] = chrono_id
    elif isinstance(copied, dict):
        for row in copied.values():
            if isinstance(row, dict) and not row.get("from_event"):
                row["from_event"] = chrono_id
    return copied


def compile_transforms(
        transforms: Iterable[dict], *, allowed_channels: Iterable[str],
        ledger_items: Iterable[dict] | None = None,
        allowed_item_ids: Iterable[int] | None = None,
        allowed_chrono_ids: Iterable[int] | None = None,
        specialist: str = "") -> tuple[dict, list[dict], list[dict]]:
    """Compile all valid transforms and return ``(diff, history, rejected)``.

    A current transform cites only the Director's small numeric ``item_id``;
    chronology is recovered from the original ledger rather than trusted to a
    second model. Ordering is then ``chrono_id`` followed by response order.
    Legacy ``chrono_id``/``object_id`` transforms remain readable when no
    ledger index is supplied.
    """
    channels = {str(channel) for channel in allowed_channels}
    ledger_index = {}
    for row in ledger_items or []:
        if not isinstance(row, dict):
            continue
        try:
            item_id = int(row.get("item_id") or 0)
            chrono_id = int(row.get("chrono_id") or row.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        if item_id > 0 and chrono_id > 0:
            ledger_index[item_id] = {
                "chrono_id": chrono_id,
                "object_name": str(row.get("object_name") or "").strip(),
            }
    item_ids = None if allowed_item_ids is None else {
        int(value) for value in allowed_item_ids
    }
    if item_ids is None and ledger_index:
        item_ids = set(ledger_index)
    chrono_ids = None if allowed_chrono_ids is None else {
        int(value) for value in allowed_chrono_ids
    }
    accepted = []
    rejected = []
    for response_order, raw in enumerate(transforms or []):
        if not isinstance(raw, dict):
            rejected.append({"reason": "transform is not an object",
                             "value": raw})
            continue
        try:
            item_id = int(raw.get("item_id") or 0)
        except (TypeError, ValueError):
            item_id = 0
        legacy_object_id = str(raw.get("object_id") or "").strip()
        meta = ledger_index.get(item_id) if item_id > 0 else None
        try:
            chrono_id = int((meta or {}).get("chrono_id")
                            or raw.get("chrono_id") or 0)
        except (TypeError, ValueError):
            chrono_id = 0
        object_name = str((meta or {}).get("object_name") or "").strip()
        patch = raw.get("patch")
        if item_ids is not None and item_id not in item_ids:
            rejected.append({"reason": "item_id was not granted",
                             "item_id": item_id})
            continue
        if chrono_id <= 0:
            rejected.append({"reason": "item has no valid chronology",
                             "item_id": item_id, "value": raw})
            continue
        if chrono_ids is not None and chrono_id not in chrono_ids:
            rejected.append({"reason": "chrono_id was not granted",
                             "chrono_id": chrono_id, "item_id": item_id})
            continue
        if not item_id and not legacy_object_id:
            rejected.append({"reason": "missing item_id",
                             "chrono_id": chrono_id})
            continue
        if not isinstance(patch, dict) or not patch:
            rejected.append({"reason": "empty patch", "chrono_id": chrono_id,
                             "item_id": item_id})
            continue
        owned = {key: value for key, value in patch.items() if key in channels}
        foreign = sorted(set(patch) - channels)
        if foreign:
            rejected.append({"reason": "unowned channels",
                             "chrono_id": chrono_id, "item_id": item_id,
                             "channels": foreign})
        if not owned:
            continue
        accepted.append((chrono_id, response_order, item_id, object_name,
                         legacy_object_id, owned))

    compiled: dict[str, Any] = {}
    history: list[dict] = []
    last_touch: dict[tuple[str, str], tuple[int, int]] = {}
    for (chrono_id, response_order, item_id, object_name, legacy_object_id,
         patch) in sorted(
            accepted, key=lambda row: (row[0], row[1])):
        channels_written = []
        supersedes = []
        history_patch = {}
        for channel, value in patch.items():
            stamped = _stamp_from_event(channel, value, chrono_id)
            history_patch[channel] = deepcopy(stamped)
            # Dict channel keys are the engine-compatible identities selected
            # by the specialist. They, not free-text object_name, define
            # same-object conflicts. Ordered operation channels append and
            # therefore have no replacement conflict to report.
            targets = list(value) if isinstance(value, dict) else []
            for target in targets:
                previous = last_touch.get((channel, str(target)))
                if previous is not None:
                    supersedes.append({
                        "channel": channel,
                        "object": str(target),
                        "prior_chrono_id": previous[0],
                        "prior_item_id": previous[1],
                    })
            _merge_channel(compiled, channel, stamped)
            if isinstance(value, dict):
                sources = compiled.setdefault("phase_sources", {})
                for key in value:
                    sources[f"{channel}.{key}"] = str(chrono_id)
            for target in targets:
                last_touch[(channel, str(target))] = (chrono_id, item_id)
            channels_written.append(channel)
        history.append({
            "chrono_id": chrono_id,
            "item_id": item_id,
            **({"object_name": object_name} if object_name else {}),
            **({"object_id": legacy_object_id}
               if legacy_object_id and not item_id else {}),
            "specialist": str(specialist or ""),
            "response_order": response_order,
            "channels": channels_written,
            "patch": history_patch,
            **({"supersedes": supersedes} if supersedes else {}),
        })
    return compiled, history, rejected
