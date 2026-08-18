"""Contact and material-effect validation and merging for the Director.

Player-asserted contact ops are VALIDATED at interpret and MERGED at
resolve; character-declared contact endings and actor-owned material
effects follow the same validate/merge pairing. The merge exists to honour
what the validation admitted, which is why the pairs live together.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

import copy
import json
import re

from character_schema import character_name, character_name_from_text
from spatial import (
    contact_motion,
    contacts_of,
    contact_relation,
    resolve_substance_ops,
    room_of,
    same_subject,
)

def _canonical_scene_subject(sc, value):
    """The positioned scene spelling for one body/entity reference."""
    for subject in (sc.get("positions") or {}):
        if same_subject(sc, str(subject), str(value or "")):
            return str(subject)
    return str(value or "").strip()


def _validated_player_contact_assertions(sc, raw, player_name, report=None):
    """Guard pass-1 contact assertions at the player-authority boundary.

    A player may establish contact through their OWN completed conduct. When
    the other body is the actor, the assertion may only refine a contact that
    already stands between the same bodies through the same acting part; that
    lets first-person body sense sharpen a coarse ``part -> region`` contact
    into the exact ``part -> interior`` one it already stands in
    without turning "I feel her strike me" into authority over an NPC attack.
    """
    out = []
    for item in (raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        actor = _canonical_scene_subject(sc, item.get("actor"))
        target = _canonical_scene_subject(sc, item.get("target"))
        actor_part = str(item.get("actor_part") or "").strip()
        target_part = str(item.get("target_part") or "").strip()
        requested_op = str(item.get("op") or "add").strip().casefold()
        requested_op = requested_op if requested_op in ("add", "cross") else "add"
        crossed_target_part = str(
            item.get("crossed_target_part") or "").strip()
        if not actor or not target or same_subject(sc, actor, target):
            continue
        actor_is_player = same_subject(sc, actor, player_name)
        target_is_player = same_subject(sc, target, player_name)
        if not (actor_is_player or target_is_player):
            if report:
                report("discarded a contact assertion that did not involve the player")
            continue
        if room_of(sc, actor) != room_of(sc, target) or room_of(sc, actor) is None:
            if report:
                report("discarded a contact assertion between non-co-located bodies")
            continue

        standing = None
        pair_contacts = []
        for contact in (sc.get("contacts") or []):
            if not isinstance(contact, dict):
                continue
            if not (same_subject(sc, contact.get("actor"), actor)
                    and same_subject(sc, contact.get("target"), target)):
                continue
            pair_contacts.append(contact)
            if (str(contact.get("actor_part") or "").strip().casefold()
                    == actor_part.casefold()):
                standing = contact
                break

        # A player may name the touching sub-part ("fingertip") while the
        # ledger names its owning part ("hand"). When exactly one standing relation
        # between the pair has the same physical manner kind, it is unambiguous;
        # bind back to the ledger's canonical part instead of minting a second
        # anatomical object beside it.
        if standing is None and not actor_is_player:
            same_kind = [
                contact for contact in pair_contacts
                if contact_relation(contact) == contact_relation(item)
            ]
            if len(same_kind) == 1:
                standing = same_kind[0]

        # Another participant's part may only be reported as already touching
        # the player when that relation already stands. The player can refine
        # their own endpoint from direct sensation; they cannot mint an NPC act.
        if not actor_is_player and standing is None:
            if report:
                report("discarded a new NPC-authored contact assertion")
            continue
        if standing is not None and not actor_is_player:
            actor_part = str(standing.get("actor_part") or actor_part).strip()
        manner = str(item.get("manner") or (
            standing or {}).get("manner") or "touch").strip()
        detail = str(item.get("detail") or "").strip()
        target_interior = str(item.get("target_interior") or (
            standing or {}).get("target_interior") or "").strip()
        semantics = {
            "manner": manner,
            "detail": detail,
            "relation": item.get("relation"),
            "motion": item.get("motion"),
        }
        relation = contact_relation(semantics)
        # A first-person refinement of an already-interior relation must not
        # flatten it merely because the interpret model chose `press`.
        if standing is not None and contact_relation(standing) == "interior" \
                and relation != "interior":
            relation = "interior"
        if requested_op == "cross":
            if (standing is None or contact_relation(standing) != "interior"
                    or not crossed_target_part or not target_interior
                    or crossed_target_part.casefold() != str(
                        standing.get("target_part") or "").strip().casefold()):
                if report:
                    report(
                        "discarded a contact crossing that did not match the "
                        "standing interior endpoint and downstream interior")
                continue
            relation = "interior"
        assertion = {
            "op": requested_op, "actor": actor, "actor_part": actor_part,
            "target": target, "target_part": target_part,
            "manner": manner or "touch",
            "relation": relation,
            "motion": contact_motion(semantics),
        }
        if target_interior:
            assertion["target_interior"] = target_interior
        if requested_op == "cross":
            assertion["crossed_target_part"] = crossed_target_part
            assertion["motion"] = "moving"
        if detail:
            assertion["detail"] = detail
        if assertion not in out:
            out.append(assertion)
    return out


def _merge_player_contact_assertions(assertions, resolved_ops, report=None):
    """Place onset truth before resolve ops without allowing silent coarsening.

    Resolve may end/move an asserted contact, but must say so with an explicit
    remove/clear first. A bare later add for the same acting part at a different
    endpoint is the common re-description drift (`cervix` -> `groin`), not an
    authored transition, and is dropped.
    """
    assertions = [dict(a) for a in (assertions or []) if isinstance(a, dict)]
    result = list(assertions)
    released = set()

    def same_pair(left, right):
        return (str(left.get("actor") or "").casefold()
                == str(right.get("actor") or "").casefold()
                and str(left.get("target") or "").casefold()
                == str(right.get("target") or "").casefold())

    for raw in (resolved_ops if isinstance(resolved_ops, list) else []):
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "add").strip().casefold()
        if op in ("remove", "clear"):
            for index, assertion in enumerate(assertions):
                if op == "clear":
                    who = str(raw.get("actor") or "").casefold()
                    if not who or who in (str(assertion.get("actor") or "").casefold(),
                                          str(assertion.get("target") or "").casefold()):
                        released.add(index)
                elif same_pair(assertion, raw):
                    ap = str(raw.get("actor_part") or "").casefold()
                    tp = str(raw.get("target_part") or "").casefold()
                    if (not ap or ap == str(assertion.get("actor_part") or "").casefold()) \
                            and (not tp or tp == str(assertion.get("target_part") or "").casefold()):
                        released.add(index)
            if raw not in result:
                result.append(raw)
            continue

        if op == "cross":
            crossed = str(raw.get("crossed_target_part") or "").casefold()
            duplicate = False
            for index, assertion in enumerate(assertions):
                if not same_pair(assertion, raw):
                    continue
                if (str(assertion.get("actor_part") or "").casefold()
                        != str(raw.get("actor_part") or "").casefold()):
                    continue
                assertion_op = str(
                    assertion.get("op") or "add").strip().casefold()
                if assertion_op == "cross" and crossed == str(
                        assertion.get("crossed_target_part") or "").casefold():
                    # Commit already begins with the player's crossing. A
                    # second rendering of that same transition cannot start
                    # from the now-crossed boundary, so keep the authoritative
                    # assertion and discard the duplicate.
                    duplicate = True
                    break
                if crossed == str(assertion.get("target_part") or "").casefold():
                    # Crossing is the explicit transition that authorizes an
                    # endpoint change; it is not re-description drift.
                    released.add(index)
            if duplicate:
                continue

        blocked = False
        for index, assertion in enumerate(assertions):
            if index in released or not same_pair(assertion, raw):
                continue
            if (str(assertion.get("actor_part") or "").casefold()
                    != str(raw.get("actor_part") or "").casefold()):
                continue
            if (str(assertion.get("target_part") or "").casefold()
                    != str(raw.get("target_part") or "").casefold()):
                blocked = True
                if report:
                    report(
                        "preserved player-declared contact endpoint "
                        f"{assertion.get('target_part')!r}; resolve attempted to "
                        f"coarsen it to {raw.get('target_part')!r} without ending "
                        "the standing relation")
                break
        if not blocked and raw not in result:
            result.append(raw)
    return result


def _validated_character_contact_endings(ctx, sc, report=None):
    """Resolve character-owned contact refs against the onset ledger.

    A character may end only an exact contact that involved their own body and
    was supplied to their decision payload as ``contact:N``.  Returning the
    ledger's original direction and parts is intentional: removals therefore
    cannot widen from "this kiss" to "everything between these people".
    """
    out = []
    for row in ctx.cast:
        try:
            cid = int(row["id"])
            sheet = json.loads(row["sheet"])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            continue
        result = (ctx.character_results.get(cid)
                  or ctx.character_results.get(str(cid)) or {})
        if not isinstance(result, dict):
            continue
        cname = character_name(sheet)
        options = contacts_of(sc, cname)
        for raw in (result.get("contact_ops") or []):
            if not isinstance(raw, dict) or str(
                    raw.get("op") or "").strip().casefold() != "remove":
                if report:
                    report(f"{cname}: discarded non-removal character contact op")
                continue
            match = re.fullmatch(r"contact:(\d+)", str(
                raw.get("contact_ref") or "").strip().casefold())
            if not match:
                if report:
                    report(f"{cname}: discarded unknown character contact ref")
                continue
            index = int(match.group(1))
            if index >= len(options):
                if report:
                    report(f"{cname}: discarded stale character contact ref")
                continue
            contact = options[index]
            ending = {
                "op": "remove",
                "actor": contact.get("actor"),
                "actor_part": contact.get("actor_part") or "",
                "target": contact.get("target"),
                "target_part": contact.get("target_part") or "",
                "source": "character_declaration",
                "declared_by": cname,
            }
            if ending not in out:
                out.append(ending)
    return out


_ACTOR_MATERIAL_FIELDS = (
    "source_part", "substance", "target", "placement", "target_interior",
    "target_part", "amount", "detail",
)


def _character_material_effects(ctx, report=None):
    """Completed actor-owned material outputs from character decisions.

    A character may declare only matter leaving its own body/device.  The
    model supplies the fiction-specific material; code supplies the canonical
    source identity and refuses removal/clear operations.  Reaction and later
    interaction results are both included and exact duplicates collapse.
    """
    names = {}
    for row in ctx.cast:
        try:
            names[int(row["id"])] = character_name_from_text(row["sheet"])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            continue
    effects = []
    for results in (ctx.reaction_results or {}, ctx.character_results or {}):
        for raw_id, result in results.items():
            try:
                cid = int(raw_id)
            except (TypeError, ValueError):
                continue
            actor = names.get(cid)
            if not actor or not isinstance(result, dict):
                continue
            for raw in (result.get("material_effects") or []):
                if not isinstance(raw, dict):
                    continue
                op = str(raw.get("op") or "release").strip().casefold()
                if op not in ("add", "release", "deposit"):
                    if report:
                        report(f"{actor}: discarded non-additive material effect")
                    continue
                source_part = str(raw.get("source_part") or "").strip()
                substance = str(raw.get("substance") or "").strip()
                if not source_part or not substance:
                    if report:
                        report(f"{actor}: discarded material effect without source_part/substance")
                    continue
                effect = {"op": op, "source": actor}
                for field in _ACTOR_MATERIAL_FIELDS:
                    value = raw.get(field)
                    if value not in (None, "", [], {}):
                        effect[field] = (str(value).strip()
                                         if not isinstance(value, (dict, list))
                                         else copy.deepcopy(value))
                effect["source_part"] = source_part
                effect["substance"] = substance
                if str(effect.get("target") or "").casefold() in ("self", "you"):
                    effect["target"] = actor
                if effect not in effects:
                    effects.append(effect)
    return effects


def _merge_character_material_effects(scene, resolved_ops, actor_effects,
                                      report=None):
    """Make valid actor-owned outputs survive Director omission.

    The existing substance resolver remains the topology authority.  A richer
    Director op wins only when it resolves to the same source/material and
    destination; otherwise the independently valid actor declaration is kept.
    """
    merged = [copy.deepcopy(op) for op in (resolved_ops or [])
              if isinstance(op, dict)]

    def event_key(event):
        return tuple(str(event.get(field) or "").strip().casefold() for field in (
            "source", "source_part", "substance", "target", "placement",
            "target_interior", "target_part",
        ))

    existing_keys = set()
    for op in merged:
        for event in resolve_substance_ops(scene, [op]):
            existing_keys.add(event_key(event))
    for effect in (actor_effects or []):
        warnings = []
        events = resolve_substance_ops(scene, [effect], report=warnings.append)
        if not events:
            if report:
                report((warnings[0] if warnings else
                        "discarded unresolved character material effect"))
            continue
        keys = {event_key(event) for event in events}
        if keys <= existing_keys:
            continue
        merged.append(copy.deepcopy(effect))
        existing_keys.update(keys)
    return merged


def _merge_character_contact_endings(endings, resolved_ops, report=None):
    """Project completed endings and reject a stale same-contact re-add.

    ``contact_ops`` describes the state at the end of the character's own
    declaration.  If that declaration explicitly ended contact:N, a Director
    echoing the onset contact is stale, not a later transition.  A genuinely
    resumed contact should remain standing in the character declaration and
    therefore must not emit the removal ref.
    """
    endings = [dict(op) for op in (endings or []) if isinstance(op, dict)]

    def key(op):
        return tuple(str(op.get(field) or "").strip().casefold()
                     for field in ("actor", "actor_part", "target", "target_part"))

    ended = set()
    for ending in endings:
        actor, actor_part, target, target_part = key(ending)
        ended.add((actor, actor_part, target, target_part))
        ended.add((target, target_part, actor, actor_part))
    result = list(endings)
    for raw in (resolved_ops if isinstance(resolved_ops, list) else []):
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "add").strip().casefold()
        if op in ("add", "cross") and key(raw) in ended:
            if report:
                report("discarded Director re-add of character-ended contact")
            continue
        if raw not in result:
            result.append(raw)
    return result
