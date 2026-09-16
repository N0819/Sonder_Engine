"""Pure adapters for the character agent's compact wire contract.

The character model makes one subjective decision.  It does not need to know
which persistence subsystem owns each consequence of that decision.  The wire
therefore keeps cognitive faculties as independently named lanes inside typed
``updates`` and groups physical consequences as typed ``effects``; this module
expands them into the long-lived :class:`llm.schemas.CharacterOutput` shape
used by the rest of the engine.

No world state is read here and no model is called.  Stored legacy answers can
still pass through unchanged.
"""

from __future__ import annotations

import re
from copy import deepcopy


_UPDATE_LANES = {
    "intention": ("intent_ops", "list"),
    "intent": ("intent_ops", "list"),
    "project": ("project_ops", "list"),
    "drive": ("drive_shift", "single"),
    "drive_shift": ("drive_shift", "single"),
    "belief": ("belief_updates", "list"),
    "association": ("association_updates", "list"),
    "mind_model": ("mind_model_updates", "list"),
    "relationship": ("relationship_updates", "list"),
    "remember": ("remember_lines", "list"),
    "remember_line": ("remember_lines", "list"),
    "memory_dispute": ("memory_disputes", "list"),
    "memory_effect": ("memory_effects", "list"),
}

_EFFECT_LANES = {
    "follow": ("follow_op", "single"),
    "contact": ("contact_ops", "list"),
    "contact_end": ("contact_ops", "list"),
    "material": ("material_effects", "list"),
}

_EVIDENCE_ID_LIST_KEYS = frozenset({"trigger_event_ids"})
_EVIDENCE_CONTAINER_KEYS = frozenset({
    "evidence", "present_evidence", "observations_used",
    "present_evidence_used", "memory_evidence_used",
})

_NAMED_UPDATE_LANES = {
    "intentions": "intent_ops",
    "projects": "project_ops",
    "beliefs": "belief_updates",
    "associations": "association_updates",
    "people": "mind_model_updates",
    "relationships": "relationship_updates",
}

# `updates` is the last and by far the largest object a character writes, and
# the contract's remaining top-level fields follow it. A writer that has not
# closed `updates` folds them inside. The lanes `updates` owns are a closed set
# the engine defines, so a top-level field found in there was misplaced and was
# never authored there -- measured on glm-5.2 beats 1199 and 1419, where a full
# `interaction` block (addresses, expects_response, yields_floor, urgency) and
# a `salience` of 0.85 arrived nested and were silently replaced by {} and the
# 0.5 default.
_TOP_LEVEL_AFTER_UPDATES = ("effects", "interaction", "salience")


def _recover_folded_top_level(raw, warnings):
    """Lift a top-level field the writer folded into ``updates``."""
    updates = raw.get("updates")
    if not isinstance(updates, dict):
        return raw
    folded = [
        key for key in _TOP_LEVEL_AFTER_UPDATES
        if key in updates
        and (key not in raw or raw[key] is None or raw[key] in ({}, []))
    ]
    if not folded:
        return raw
    raw = dict(raw)
    raw["updates"] = {
        key: value for key, value in updates.items() if key not in folded}
    for key in folded:
        raw[key] = updates[key]
        warnings.append(
            f"character kernel lifted {key} out of updates")
    return raw


_NAMED_MEMORY_LANES = {
    "keep": "remember_lines",
    "reinterpret": "memory_disputes",
    "effects": "memory_effects",
}


def is_character_kernel_output(raw):
    """Whether ``raw`` uses the compact contract rather than the archive one."""
    return isinstance(raw, dict) and (
        "state" in raw or "updates" in raw or "effects" in raw
    )


def compact_character_evidence(payload):
    """Replace long, call-local evidence identifiers with short handles.

    The prose and metadata beside each observation or memory stay untouched.
    The returned map is private host state and is used to restore canonical
    identifiers before the existing grounding and commit code sees the answer.
    Repeated delivery of one stored memory receives one repeated handle.
    """
    compacted = deepcopy(payload) if isinstance(payload, dict) else {}
    handle_to_id = {}
    id_to_handle = {}
    counts = {"o": 0, "m": 0, "s": 0}

    def handle(value, prefix):
        canonical = str(value or "").strip()
        if not canonical:
            return value
        lookup = (prefix, canonical)
        if lookup not in id_to_handle:
            counts[prefix] += 1
            short = f"{prefix}{counts[prefix]}"
            id_to_handle[lookup] = short
            handle_to_id[short] = canonical
        return id_to_handle[lookup]

    def visit(value):
        if isinstance(value, dict):
            for key, item in list(value.items()):
                # `line_ref` is a cue's pointer AT an observation
                # (`perception.impossible_knowledge`), so it takes the same
                # handle as the observation it names: one id, one handle,
                # whichever key carries it.
                if key in ("observation_id", "line_ref"):
                    value[key] = handle(item, "o")
                elif key == "memory_ref":
                    value[key] = handle(item, "m")
                elif key == "summary_id":
                    value[key] = handle(item, "s")
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(compacted)
    return compacted, handle_to_id


def _rewrite_evidence_container(item, rewrite_token, rewrite_scalar):
    """Rewrite every id inside an evidence container, whatever its shape.

    An evidence container names ids, and a writer spells them three ways: a
    bare id, a list of ids, or rows carrying ``event_id``. Only the row form
    was ever traversed, so the other two passed through untouched. Measured
    over 20 stored beats of the owner's stories replayed through glm-5.2: 88
    bare strings and 37 lists of strings against 4 row lists, leaving 152 of
    206 ids as call-local handles that name nothing outside the request that
    issued them. `schemas._evidence_slot` then files a bare `o7` as a real
    `event_id` and a joined `o5,o6,o7` -- commas fail its id pattern -- as
    prose `fact`, so both spellings become provenance that resolves to
    nothing. The old contract cited canonical ids directly and never met this.

    A row's own ``event_id`` takes the scalar rewrite: a structured row names
    one event, so it must not become a list.
    """
    if isinstance(item, str):
        return rewrite_token(item)
    if isinstance(item, list):
        out = []
        for entry in item:
            new = _rewrite_evidence_container(
                entry, rewrite_token, rewrite_scalar)
            if isinstance(entry, str) and isinstance(new, list):
                out.extend(new)
            else:
                out.append(new)
        return out
    if isinstance(item, dict):
        for key, sub in list(item.items()):
            if key == "event_id":
                item[key] = rewrite_scalar(sub)
            else:
                item[key] = _rewrite_evidence_container(
                    sub, rewrite_token, rewrite_scalar)
        return item
    return item


def expand_character_evidence(raw, handle_to_id):
    """Restore compact evidence handles in a model answer.

    Only evidence-bearing fields are rewritten.  An action's own ``event_id``
    is deliberately outside this traversal unless it sits in an evidence row;
    phase and sequence identifiers belong to a different namespace.
    """
    expanded = deepcopy(raw) if isinstance(raw, dict) else {}
    handles = dict(handle_to_id or {})

    def expand_scalar(value):
        return handles.get(str(value or "").strip(), value)

    def expand_token(value):
        """One citation, which may be the several a joined run names."""
        text = str(value or "").strip()
        if text in handles:
            return handles[text]
        parts = [part for part in re.split(r"[,;\s]+", text) if part]
        if len(parts) > 1 and all(part in handles for part in parts):
            return [handles[part] for part in parts]
        return value

    def visit(value, *, evidence_row=False):
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key in {"memory_ref", "summary_id"}:
                    value[key] = expand_scalar(item)
                elif key == "event_id" and evidence_row:
                    value[key] = expand_scalar(item)
                elif key in _EVIDENCE_ID_LIST_KEYS and isinstance(item, list):
                    value[key] = [expand_scalar(entry) for entry in item]
                elif key in _EVIDENCE_CONTAINER_KEYS:
                    value[key] = _rewrite_evidence_container(
                        item, expand_token, expand_scalar)
                else:
                    visit(item, evidence_row=evidence_row)
        elif isinstance(value, list):
            for item in value:
                visit(item, evidence_row=evidence_row)

    visit(expanded)
    return expanded


def bind_current_evidence_to_memory(raw, memory_ref):
    """Re-key this beat's evidence onto the episode minted at commit.

    Current observation ids are only call-local.  Once a witnessed episode is
    created, durable state should cite that memory's stable key.  The character
    result kept on the turn is not mutated; callers pass their commit-local
    copy.  If no episode was minted, the current ids remain as honest transient
    provenance rather than pointing at a nonexistent row.
    """
    if not isinstance(raw, dict) or not str(memory_ref or "").strip():
        return raw
    stable = str(memory_ref).strip()

    def restable(value):
        return stable if str(value or "").startswith("current:") else value

    def visit(value, *, evidence_row=False):
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key == "event_id" and evidence_row \
                        and str(item or "").startswith("current:"):
                    value[key] = stable
                elif key in _EVIDENCE_ID_LIST_KEYS and isinstance(item, list):
                    value[key] = [
                        stable if str(entry or "").startswith("current:") else entry
                        for entry in item
                    ]
                elif key in _EVIDENCE_CONTAINER_KEYS:
                    value[key] = _rewrite_evidence_container(
                        item, restable, restable)
                else:
                    visit(item, evidence_row=evidence_row)
        elif isinstance(value, list):
            for item in value:
                visit(item, evidence_row=evidence_row)

    visit(raw)
    return raw


def _chosen_wants(active, warnings, decision=None):
    """Join local want ids onto the two legacy index slots.

    The first kernel put ``choice`` on each want.  That was small, but it did
    not require the model to state why one live pull beat another and its
    one-want example taught away ambivalence.  The current kernel names wants
    locally (w1, w2) and carries one decision hinge beside them. The indexes
    continue to serve existing readers; the short private reason travels in
    decision_continuity rather than being discarded at this join.
    """
    active = deepcopy(active) if isinstance(active, dict) else {}
    decision = decision if isinstance(decision, dict) else {}
    enacted_ref = str(decision.get("enact") or "").strip()
    suppressed_value = decision.get("suppress")
    suppressed_refs = {
        str(item or "").strip()
        for item in (suppressed_value if isinstance(suppressed_value, list)
                     else [suppressed_value])
        if str(item or "").strip()
    }
    wants = []
    enacted = []
    suppressed = []
    seen_ids = set()
    for index, want in enumerate(active.get("wants") or []):
        if not isinstance(want, dict):
            continue
        item = deepcopy(want)
        local_id = str(item.pop("id", "") or "").strip()
        if local_id:
            if local_id in seen_ids:
                warnings.append(
                    f"character kernel received duplicate want id {local_id!r}")
            seen_ids.add(local_id)
        choice = str(item.pop("choice", "") or "").strip().casefold()
        if local_id and local_id == enacted_ref:
            enacted.append(len(wants))
        elif choice in {"enact", "enacted", "choose", "chosen", "select"}:
            enacted.append(len(wants))
        if local_id and local_id in suppressed_refs:
            suppressed.append(len(wants))
        elif choice in {"suppress", "suppressed", "inhibit", "inhibited"}:
            suppressed.append(len(wants))
        elif choice not in {"", "hold", "held", "defer", "deferred"}:
            warnings.append(
                f"character kernel ignored unknown want choice {choice!r}")
        wants.append(item)
    active["wants"] = wants
    if "enacted_want" not in active and enacted:
        active["enacted_want"] = enacted[0]
    if "suppressed_want" not in active and suppressed:
        active["suppressed_want"] = suppressed[0]
    if len(enacted) > 1:
        warnings.append(
            "character kernel received several enacted wants; kept the first")
    if len(suppressed) > 1:
        warnings.append(
            "character kernel received several suppressed wants; kept the first")
    if enacted_ref and not enacted:
        warnings.append(
            f"character kernel decision enacted unknown want {enacted_ref!r}")
    unknown_suppressed = suppressed_refs - seen_ids
    for local_id in sorted(unknown_suppressed):
        warnings.append(
            f"character kernel decision suppressed unknown want {local_id!r}")
    return active


def _canonical_lane_item(lane, row):
    """Translate the compact spelling before the legacy schema sees it."""
    item = deepcopy(row)
    if lane == "belief_updates":
        if "operation" not in item and "op" in item:
            item["operation"] = item.pop("op")
        if "emotional_charge" not in item and "charge" in item:
            item["emotional_charge"] = item.pop("charge")
    elif lane == "association_updates":
        if "operation" not in item and "op" in item:
            item["operation"] = item.pop("op")
        operation = str(item.get("operation") or "").strip().casefold()
        if operation in {"strengthen", "strengthened"}:
            item["operation"] = "reinforce"
        elif operation in {"break", "broken", "extinguish", "weaken"}:
            item["operation"] = "extinguish"
    return item


def _compile_rows(rows, registry, compiled, warnings, group):
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            warnings.append(
                f"character kernel dropped non-object {group}.{index}")
            continue
        discriminator = "type" if row.get("type") else "kind"
        kind = str(row.get(discriminator) or "").strip().casefold()
        target = registry.get(kind)
        if target is None:
            warnings.append(
                f"character kernel dropped unknown {group} kind {kind!r}")
            continue
        lane, cardinality = target
        item = deepcopy(row)
        item.pop(discriminator, None)
        item = _canonical_lane_item(lane, item)
        if cardinality == "list":
            compiled.setdefault(lane, []).append(item)
        else:
            if compiled.get(lane) is not None:
                warnings.append(
                    f"character kernel received several {lane} rows; kept the last")
            compiled[lane] = item


def _compile_named_updates(updates, compiled, warnings):
    """Expand the typed, independently named cognitive apertures."""
    for source, lane in _NAMED_UPDATE_LANES.items():
        rows = updates.get(source) or []
        if not isinstance(rows, list):
            warnings.append(
                f"character kernel dropped non-array updates.{source}")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                warnings.append(
                    f"character kernel dropped non-object updates.{source}.{index}")
                continue
            compiled.setdefault(lane, []).append(
                _canonical_lane_item(lane, row))

    drive = updates.get("drive")
    if isinstance(drive, dict) and any(
            value not in (None, "", [], {}) for value in drive.values()):
        compiled["drive_shift"] = deepcopy(drive)

    memory = updates.get("memory")
    if memory is None:
        memory = {}
    if not isinstance(memory, dict):
        warnings.append("character kernel dropped non-object updates.memory")
        return
    for source, lane in _NAMED_MEMORY_LANES.items():
        rows = memory.get(source) or []
        if not isinstance(rows, list):
            warnings.append(
                f"character kernel dropped non-array updates.memory.{source}")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                warnings.append(
                    "character kernel dropped non-object "
                    f"updates.memory.{source}.{index}")
                continue
            compiled.setdefault(lane, []).append(deepcopy(row))


def decision_continuity(active, decision):
    """Resolve temporary want handles into a bounded private choice record."""
    active = active if isinstance(active, dict) else {}
    decision = decision if isinstance(decision, dict) else {}
    wants = active.get("wants") or []

    def selected(key):
        index = active.get(key)
        if type(index) is int and 0 <= index < len(wants):
            return str((wants[index] or {}).get("want") or "")
        return ""

    return {key: " ".join(str(value or "").split())[:240]
            for key, value in {
                "chosen": selected("enacted_want"),
                "suppressed": selected("suppressed_want"),
                "why": decision.get("hinge"),
                "uncertainty": decision.get("uncertainty"),
            }.items()}


def compile_character_kernel(raw):
    """Expand a compact character answer into ``CharacterOutput`` fields.

    Returns ``(compiled, warnings)``.  A legacy answer is copied byte-for-byte
    at the value level so old fixtures, provider fallbacks, and stored variants
    continue through the existing validation path.
    """
    if not isinstance(raw, dict):
        return {}, []
    if not is_character_kernel_output(raw):
        return deepcopy(raw), []

    warnings = []
    raw = _recover_folded_top_level(raw, warnings)
    state = raw.get("state") if isinstance(raw.get("state"), dict) else {}
    active = state.get("active", state.get("active_state", {}))
    compiled = {
        "appraisal": deepcopy(state.get("appraisal") or {}),
        "active_state": _chosen_wants(
            active, warnings, state.get("decision")),
        "sequence": deepcopy(raw.get("sequence") or []),
        "manifest": deepcopy(raw.get("manifest") or {}),
        "interaction": deepcopy(raw.get("interaction") or {}),
        "salience": raw.get("salience", 0.5),
    }
    affect = compiled["active_state"].get("affect") or {}
    surface = affect.get("surface") if isinstance(affect, dict) else None
    if not compiled["active_state"].get("mood") and isinstance(surface, dict):
        compiled["active_state"]["mood"] = str(surface.get("label") or "")
    if isinstance(state.get("decision"), dict):
        compiled["decision_continuity"] = decision_continuity(
            compiled["active_state"], state["decision"])
    updates = raw.get("updates")
    if isinstance(updates, dict):
        _compile_named_updates(updates, compiled, warnings)
    else:
        # Read compatibility for responses captured during the first compact
        # experiment. Runtime now advertises only the object form.
        _compile_rows(
            updates, _UPDATE_LANES, compiled, warnings, "updates")
    _compile_rows(
        raw.get("effects"), _EFFECT_LANES, compiled, warnings, "effects")
    return compiled, warnings
