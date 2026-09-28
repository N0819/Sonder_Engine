"""Evidence identifiers around the character call: pure adapters.

The payload a character reads carries evidence rows -- observations, recalled
memories, summaries -- under long, call-local identifiers. The model needs the
rows and their provenance, not database- or observer-sized ids, so
`compact_character_evidence` swaps them for short handles before the call.
After commit mints this beat's witnessed episode, `bind_current_evidence_to_memory`
re-keys this beat's `current:` evidence onto that episode's stable key.

What remains of `agents/character_kernel.py` (the full card's compiler, removed
2026-09-27 with the full card: the bare contract is the only one, and its
reply cites nothing -- the decision model maps its lines to the rows).

No world state is read here and no model is called.
"""

from __future__ import annotations

from copy import deepcopy

_EVIDENCE_ID_LIST_KEYS = frozenset({"trigger_event_ids"})
_EVIDENCE_CONTAINER_KEYS = frozenset({
    "evidence", "present_evidence", "observations_used",
    "present_evidence_used", "memory_evidence_used",
})


def compact_character_evidence(payload):
    """Replace long, call-local evidence identifiers with short handles.

    The prose and metadata beside each observation or memory stay untouched.
    The returned map is private host state. Repeated delivery of one stored
    memory receives one repeated handle.
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
    was ever traversed, so the other two passed through untouched -- measured
    over 20 stored beats, 88 bare strings and 37 lists against 4 row lists.

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
