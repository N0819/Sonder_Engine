"""Engine receipts for typed effects, evaluated at their chronological span.

This module never reads event prose. A model's completion label is a proposal;
the requested patch, the executed world, and explicit assignment decide what
can actually be certified. Unsupported commit domains remain pending.
"""
from copy import deepcopy

from world.causal_verification import TRANSIENT_EVENT


# These commit-side records describe knowledge, recognition, evidence, or
# obligations. Their pending persistence does not undo an observed gesture.
# Physical channels, unknown channels, and mixed scene/commit domains are not
# exempt merely because a particular specialist owns them.
DEFERRED_NONPHYSICAL_CHANNELS = frozenset({
    "world_facts", "public_evidence", "introductions", "ratified_claims",
    "contradicted_claims", "claim_dispositions", "obligations", "telling_ops",
})


def execution_receipt(before, after, step):
    """Verify a span's original requests after all complementary hands apply."""
    from world.causal_verification import verify_patch

    effects = []
    transforms = step.get("transforms")
    if transforms is None:
        # An archive's transient gesture can legitimately have no persistent
        # effect. Missing assigned work is represented by requirements below.
        patch = step.get("patch") or {}
        if step.get("stage") == "engine":
            # Schema defaults in the engine's trailing projection are silence,
            # unlike an empty model answer assigned to a concrete item.
            patch = {key: value for key, value in patch.items()
                     if value not in (None, "", [], {})
                     and key not in {"speech", "movement_refused"}}
        transforms = [{"patch": patch}] if patch else []
    for transform_index, transform in enumerate(transforms):
        verified = verify_patch(
            before, after, transform.get("patch") or {},
            item_id=transform.get("item_id"),
            chrono_id=step.get("chrono_id"),
            specialist=str(transform.get("specialist") or ""),
            verification_context=step.get("patch") or {})
        effects.extend(dict(effect, transform_index=transform_index) for effect in verified)
    for requirement in step.get("requirements") or []:
        own = [effect for effect in effects
               if effect.get("specialist") == requirement.get("specialist")
               and (effect.get("transform_index") in requirement["transform_indices"]
                    if "transform_indices" in requirement else
                    requirement.get("item_id") is None
                    or effect.get("item_id") == requirement["item_id"])]
        channels = set(requirement.get("channels") or [])
        present = {effect.get("channel") for effect in own}
        missing = channels - present
        if requirement.get("status") == "not_applicable":
            continue
        if own and not missing and requirement.get("status") != "unresolved":
            continue
        effects.append({
            "chrono_id": step.get("chrono_id"),
            "item_id": requirement.get("item_id"),
            "item": requirement.get("item", ""),
            "specialist": requirement.get("specialist", ""),
            "channel": ",".join(sorted(missing)),
            "status": "unresolved", "code": "missing_effect",
            "reason": requirement.get("reason") or
                      "assigned work has no typed desired effect",
        })
    unresolved = [effect for effect in effects
                  if effect.get("status") == "unresolved"]
    # No verifier is a limitation, never a successful no-op or a failed act.
    pending = [effect for effect in unresolved
               if effect.get("code") in {"unsupported_channel", "pending_commit_domain",
                                         TRANSIENT_EVENT}]
    status = ("unresolved" if len(unresolved) > len(pending) else
              "pending" if pending else
              "applied" if any(e.get("status") == "applied" for e in effects) else
              "unchanged" if effects else "recorded")
    # WHAT MAKES AN ACT UNACCOMPLISHED IS THE WORLD REFUSING IT, NEVER THE
    # LEDGER BEING THIN. `action_status` answers one question -- may this
    # act render as something that happened -- and a `missing_effect` is
    # not an answer to it. That code means an assigned hand wrote no typed
    # effect, which is a fact about the ledger; a `verify_patch` failure
    # means a patch WAS requested and the world does not show it, which is
    # the Doctor stepping onto a platform that is not there
    # (`tests/test_causal_completion_perception.py`). Only the second is
    # evidence the act did not happen, and only it should un-see one.
    #
    # EXPRESSION IS AN ACTION AND RENDERS NO MATTER HOW TEMPORARY (owner
    # ruling, 2026-09-16). A blush, a flinch, a glance, a wince leave
    # nothing durable by construction, so a hand asked to record one
    # correctly writes nothing -- and the engine was reading that silence
    # as proof the act never occurred. Measured on chat 135 turn 1: the
    # player looked at Mirelle, flushed and stiffened her tails, the body
    # hand said in so many words "the row's observable action carries
    # them", and every one of those facts was then dropped from Mirelle's
    # view, which received the two spoken lines and nothing else.
    #
    # `status` is untouched, so the gap stays in the audit ledger exactly
    # as it was -- the test's own title, "failed requested effects remain
    # auditable without becoming observed successes", is what this keeps.
    action_unresolved = [effect for effect in unresolved
                         if not (effect.get("code") in ("missing_effect", TRANSIENT_EVENT)
                                 or (effect.get("code") == "unsupported_channel"
                                     and effect.get("channel") in DEFERRED_NONPHYSICAL_CHANNELS)
                                 or (effect.get("code") == "pending_commit_domain"
                                     and effect.get("scope") == "commit"))]
    action_status = ("unresolved" if action_unresolved else
                     "applied" if any(e.get("status") == "applied" for e in effects) else
                     "unchanged" if any(e.get("status") == "unchanged" for e in effects) else
                     "recorded")
    return {"status": status, "action_status": action_status, "effects": effects}


def annotate_event_execution(events, worlds):
    """Keep every event and attach the outcome of its engine-owned span."""
    indexed = {(str(world.get("stage")), str(world.get("chrono_id"))):
               (world.get("completion") or {}).get("status")
               for world in worlds or []}
    out = deepcopy(events or [])
    for event in out:
        span = event.get("causal_span")
        if isinstance(span, (list, tuple)) and len(span) == 2:
            status = indexed.get(tuple(map(str, span)))
            if status:
                event["execution"] = status
    return out


def event_execution_statuses(worlds, events, *, action=False):
    """Join receipt status to percept inputs through engine identity only."""
    spans, aliases = {}, {}
    for world in worlds or []:
        completion = world.get("completion") or {}
        status = completion.get("action_status", completion.get("status")) if action else completion.get("status")
        if status:
            spans[(str(world.get("stage")), str(world.get("chrono_id")))] = status
            for alias in world.get("events") or []:
                if not str(alias).endswith(":raw"):
                    aliases.setdefault(str(alias), status)
    found = {}
    for index, entry in enumerate(events):
        source = entry.get("event") or {}
        span = entry.get("causal_span") or source.get("_causal_span")
        if isinstance(span, (tuple, list)) and tuple(map(str, span)) in spans:
            found[index] = spans[tuple(map(str, span))]
            continue
        for alias in (entry.get("declared"), source.get("event_id")):
            if str(alias or "") in aliases:
                found[index] = aliases[str(alias)]
                break
    return found
