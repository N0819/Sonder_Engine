"""Durable, locally recognised promises, bargains, debts and favours.

The records here establish that words were publicly undertaken and how later
events treated them.  They do *not* establish universal legal or moral
validity.  Each Charter keeps its own recognised projection and each record
names who inside that Charter has actually received evidence of it.

This is intentionally separate from ``pending_obligations`` (a two-beat prose
debt) and ``place_obligations`` (history owed to an unvisited location).
"""

from __future__ import annotations

import hashlib

from .charter_model import number as _number


COMMITMENT_CAP = 64
LIFECYCLE_CAP = 12
OPEN_STATES = frozenset({"proposed", "open", "accepted", "disputed"})
TERMINAL_STATES = frozenset({
    "fulfilled", "released", "repudiated", "defaulted", "transferred"})


def commitment_id(source_id, actor, target, terms):
    material = "|".join((str(source_id), str(actor), str(target), str(terms)))
    return "commitment:" + hashlib.sha256(
        material.encode("utf-8")).hexdigest()[:18]


def normalize_commitments(stored):
    out = {}
    for key, raw in (stored or {}).items():
        if not isinstance(raw, dict):
            continue
        lifecycle = []
        for event in raw.get("lifecycle") or ():
            if not isinstance(event, dict) or not event.get("kind"):
                continue
            lifecycle.append({
                "kind": str(event["kind"]),
                "at_hours": round(_number(event.get("at_hours")), 6),
                "evidence_id": str(event.get("evidence_id") or ""),
                "by": str(event.get("by") or ""),
                "to": str(event.get("to") or ""),
                "note": str(event.get("note") or "")[:240],
            })
        state = str(raw.get("state") or "proposed")
        if state not in OPEN_STATES | TERMINAL_STATES:
            state = "proposed"
        out[str(key)] = {
            "id": str(raw.get("id") or key),
            "kind": str(raw.get("kind") or "promise"),
            "promisor": str(raw.get("promisor") or ""),
            "beneficiary": str(raw.get("beneficiary") or ""),
            "terms": str(raw.get("terms") or "")[:320],
            "condition": str(raw.get("condition") or "")[:240],
            "state": state,
            "opened_at_hours": round(_number(raw.get("opened_at_hours")), 6),
            "source_id": str(raw.get("source_id") or ""),
            "recognized_by": sorted({str(x) for x in
                                     raw.get("recognized_by") or () if str(x)}),
            "lifecycle": lifecycle[-LIFECYCLE_CAP:],
        }
    ranked = sorted(out.items(), key=lambda pair: (
        pair[1]["state"] in TERMINAL_STATES,
        -pair[1]["opened_at_hours"], pair[0]))
    return dict(ranked[:COMMITMENT_CAP])


def _frame_terms(frame):
    return str(frame.get("content") or frame.get("about") or "").strip()


def observe_public_commitments(commitments, evidence_rows, recipients,
                               *, at_hours=0.0, targets=None):
    """Open/recognise commitments from grounded public speech.

    ``recipients`` maps source id to the body keys that actually heard it in
    full.  A source heard by nobody creates no locally recognised record.

    ``targets`` maps source id to the BODY KEY the utterance was aimed at,
    where the caller could resolve one. The Director writes ``target`` in
    whatever spelling the prose reached for -- an entity id, a role noun, a
    display name -- and a record keyed on that spelling names a party no
    Charter reader can find: `charter_practice._open_between` licenses a
    record to its parties BY KEY, so the promise a player made to "the
    clerk" was recognised by the clerk and owed to nobody. Resolved here,
    once, at the door every commitment enters by, so the act path
    (`charter_author`) and the evidence path mint the same id for the same
    undertaking and answer each other instead of duplicating.
    """
    out = normalize_commitments(commitments)
    opened = accepted = refused = changed = 0
    for evidence in evidence_rows or ():
        if not isinstance(evidence, dict) or evidence.get("kind") != "speech":
            continue
        source_id = str(evidence.get("source_id") or "")
        heard = sorted({str(x) for x in (recipients or {}).get(source_id, ())})
        if not heard:
            continue
        actor = str(evidence.get("actor") or "")
        target = str((targets or {}).get(source_id)
                     or evidence.get("target") or "")
        frames = [f for f in evidence.get("speech_acts") or ()
                  if isinstance(f, dict)]
        for frame in frames:
            kind = str(frame.get("kind") or "")
            terms = _frame_terms(frame)
            if kind in ("promise", "offer", "bargain") and terms:
                cid = commitment_id(source_id, actor, target, terms)
                if cid not in out:
                    state = "open" if kind == "promise" else "proposed"
                    out[cid] = {
                        "id": cid, "kind": kind, "promisor": actor,
                        "beneficiary": target, "terms": terms,
                        "condition": str(frame.get("condition") or "")[:240],
                        "state": state,
                        "opened_at_hours": round(float(at_hours), 6),
                        "source_id": source_id, "recognized_by": heard,
                        "lifecycle": [{
                            "kind": state, "at_hours": round(float(at_hours), 6),
                            "evidence_id": source_id, "by": actor,
                            "to": target, "note": terms[:240]}],
                    }
                    opened += 1
                else:
                    out[cid]["recognized_by"] = sorted(set(
                        out[cid]["recognized_by"]) | set(heard))
            elif kind in ("agreement", "refusal", "dispute", "release",
                          "repudiation", "transfer"):
                candidates = [record for record in out.values()
                              if record["state"] in OPEN_STATES
                              and actor in {record["promisor"],
                                            record["beneficiary"]}
                              and (not target or target in {
                                  record["promisor"], record["beneficiary"]})]
                candidates.sort(key=lambda r: (-r["opened_at_hours"], r["id"]))
                if not candidates:
                    continue
                record = candidates[0]
                state = {
                    "agreement": "accepted", "refusal": "repudiated",
                    "dispute": "disputed", "release": "released",
                    "repudiation": "repudiated", "transfer": "transferred",
                }[kind]
                # A proposal is the only thing agreement accepts. Other
                # lifecycle declarations can act on any open undertaking.
                if kind == "agreement" and record["state"] != "proposed":
                    continue
                record["state"] = state
                if kind == "transfer" and target:
                    record["promisor"] = target
                record["recognized_by"] = sorted(set(
                    record["recognized_by"]) | set(heard))
                record["lifecycle"].append({
                    "kind": record["state"],
                    "at_hours": round(float(at_hours), 6),
                    "evidence_id": source_id, "by": actor, "to": target,
                    "note": _frame_terms(frame)[:240]})
                accepted += kind == "agreement"
                refused += kind == "refusal"
                changed += kind not in ("agreement", "refusal")
    return normalize_commitments(out), {
        "opened": opened, "accepted": accepted, "refused": refused,
        "changed": changed}


_EVENT_TO_STATE = {
    "commitment_fulfilled": "fulfilled",
    "commitment_acknowledged": "fulfilled",
    "commitment_disputed": "disputed",
    "commitment_released": "released",
    "commitment_repudiated": "repudiated",
    "commitment_defaulted": "defaulted",
    "commitment_transferred": "transferred",
}


def advance_commitments(commitments, events):
    """Apply explicit lifecycle events; never infer fulfilment from prose."""
    out = normalize_commitments(commitments)
    changed = []
    for event in events or ():
        if not isinstance(event, dict):
            continue
        state = _EVENT_TO_STATE.get(str(event.get("kind") or ""))
        cid = str(event.get("commitment_id") or "")
        record = out.get(cid)
        if state is None or record is None:
            continue
        record["state"] = state
        if state == "transferred" and event.get("to"):
            record["promisor"] = str(event["to"])
        record["lifecycle"].append({
            "kind": state,
            "at_hours": round(float(event.get("at_hours") or 0.0), 6),
            "evidence_id": str(event.get("evidence_id") or ""),
            "by": str(event.get("by") or event.get("actor") or ""),
            "to": str(event.get("to") or ""),
            "note": str(event.get("note") or "")[:240],
        })
        changed.append(cid)
    return normalize_commitments(out), changed


def commitment_view(commitments, holder, *, parties=(), cap=6):
    holder = str(holder)
    party_set = {str(p) for p in parties if str(p)}
    rows = []
    for record in normalize_commitments(commitments).values():
        if holder not in record["recognized_by"] \
                and holder not in {record["promisor"], record["beneficiary"]}:
            continue
        if party_set and not party_set.intersection({
                record["promisor"], record["beneficiary"]}):
            continue
        rows.append(dict(record))
    rows.sort(key=lambda r: (r["state"] in TERMINAL_STATES,
                             -r["opened_at_hours"], r["id"]))
    return rows[:max(0, int(cap))]


def open_commitment(commitments, *, source_id, kind, promisor, beneficiary,
                    terms, state="proposed", at_hours=0.0, recognized_by=(),
                    condition="", note=""):
    """Open one undertaking, or recognise it again if it already stands.

    Keyed by `commitment_id` on the same four facts the evidence path keys
    on, so an act that arrives through `charter_author` and the utterance
    that carried it make ONE record. Returns ``(commitments, id, opened)``;
    an existing record is widened by ``recognized_by`` and otherwise left
    as it was -- its state is its own history, not this call's to reset.
    """
    out = normalize_commitments(commitments)
    promisor, beneficiary = str(promisor or ""), str(beneficiary or "")
    terms = " ".join(str(terms or "").split())[:320]
    if not promisor or not beneficiary or promisor == beneficiary:
        return out, "", False
    cid = commitment_id(source_id, promisor, beneficiary, terms)
    heard = sorted({str(x) for x in recognized_by if str(x)})
    if cid in out:
        out[cid]["recognized_by"] = sorted(
            set(out[cid]["recognized_by"]) | set(heard))
        return normalize_commitments(out), cid, False
    state = str(state or "proposed")
    if state not in OPEN_STATES | TERMINAL_STATES:
        state = "proposed"
    out[cid] = {
        "id": cid, "kind": str(kind or "promise"), "promisor": promisor,
        "beneficiary": beneficiary, "terms": terms,
        "condition": str(condition or "")[:240], "state": state,
        "opened_at_hours": round(float(at_hours), 6),
        "source_id": str(source_id or ""), "recognized_by": heard,
        "lifecycle": [{
            "kind": state, "at_hours": round(float(at_hours), 6),
            "evidence_id": str(source_id or ""), "by": promisor,
            "to": beneficiary, "note": (note or terms)[:240]}],
    }
    return normalize_commitments(out), cid, True


def answer_commitment(commitments, cid, *, accepted, by, at_hours=0.0,
                      note="", evidence_id=""):
    """A party's answer to an undertaking still open: taken up or refused.

    The same two transitions `observe_public_commitments` applies for an
    ``agreement`` or ``refusal`` frame, exposed for a body whose answer is
    DECIDED rather than overheard -- `charter_author`'s order, request and
    bargain acts. Acceptance is only ever of a proposal; a refusal ends any
    open record. Returns ``(commitments, changed)``.
    """
    out = normalize_commitments(commitments)
    record = out.get(str(cid or ""))
    if record is None or record["state"] not in OPEN_STATES:
        return out, False
    if accepted and record["state"] != "proposed":
        return out, False
    record["state"] = "accepted" if accepted else "repudiated"
    record["lifecycle"].append({
        "kind": record["state"], "at_hours": round(float(at_hours), 6),
        "evidence_id": str(evidence_id or ""), "by": str(by or ""),
        "to": "", "note": str(note or "")[:240]})
    return normalize_commitments(out), True


__all__ = [
    "OPEN_STATES", "TERMINAL_STATES", "advance_commitments",
    "answer_commitment", "commitment_id", "commitment_view",
    "normalize_commitments", "observe_public_commitments", "open_commitment",
]
