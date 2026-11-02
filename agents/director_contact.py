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

from story.character_schema import (character_name, character_name_from_text,
                                    normalized_character_from_text)
from world.spatial import (
    _anchor_room_of,
    canonical_region,
    contact_id,
    contact_is_momentary,
    contact_motion,
    contacts_of,
    contact_relation,
    enclosure_joins_rooms,
    inside_as_holder,
    resolve_substance_ops,
    room_of,
    same_subject,
)

from .common import _check_player_contact_authority


def _drop_momentary_contact_adds(raw, report=None):
    """Keep event verbs out of end-of-beat contact topology.

    If contact remains after a strike, kiss, brush, or similar event, its
    standing relation must be described as a state such as rest, press, hold,
    or interior contact. Player-authored onset assertions use their separate
    authority path; this filters model-resolved operations only.
    """
    kept = []
    for item in (raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        op = str(item.get("op") or "add").strip().casefold()
        if op in ("add", "cross") and contact_is_momentary(item):
            if report:
                report("discarded momentary act from standing contact topology")
            continue
        kept.append(item)
    return kept

def _one_body(scene, a, b):
    """Do two spellings name the same body? Equal spellings always do; with a
    scene, so does any name the body answers to (`same_subject`). The merges
    below compared casefold strings while the validator above resolved
    bodies, so an alias-spelled op slipped past the floor that was written
    for it (review 2026-11-01, director floors F4)."""
    left = str(a or "").strip().casefold()
    right = str(b or "").strip().casefold()
    if left == right:
        return True
    return isinstance(scene, dict) and same_subject(scene, str(a or ""), str(b or ""))


def _canonical_scene_subject(sc, value):
    """The positioned scene spelling for one body/entity reference."""
    for subject in (sc.get("positions") or {}):
        if same_subject(sc, str(subject), str(value or "")):
            return str(subject)
    return str(value or "").strip()


def _validated_player_contact_assertions(
        sc, raw, player_name, report=None, *, allow_new_player_contacts=True):
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
        # A HAND ON AN INSIDE IS A HAND ON ITS HOLDER (`inside_as_holder`):
        # a target naming the room that is a body's inside is that body,
        # touched from within -- chat 137 idx 47, round 9, where all four of
        # a swallowed player's contacts named her holder's stomach room.
        holder, inside = inside_as_holder(sc, target)
        if holder:
            target = _canonical_scene_subject(sc, holder)
            if not str(item.get("target_interior") or "").strip():
                item = dict(item, target_interior=inside)
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
        actor_room = room_of(sc, actor)
        target_room = room_of(sc, target)
        # A ROOM'S OWN FIXTURE IS WHERE THE ROOM IS. `positions` places
        # bodies and the things the scene mints; a door, a counter, a rail is
        # an ANCHOR of its room with no position of its own, so a player's
        # hand on one failed this membership test and was dropped -- and the
        # contact came back only through the resolve manifest, a beat late,
        # or not at all. `spatial_contacts.normalize_scene_contacts` already
        # resolves an unplaced endpoint through the room that declares it as
        # an anchor (caravanserai turns 3-5); this is the same rule at the
        # player-authority site, which had kept the narrower test. Measured
        # on the descent copy (chat 117, beats 115 and 117): a palm on the
        # access door plate and a shoulder against its leaf, both discarded
        # here while both bodies stood STATIONED at that very anchor.
        if actor_room is None and target_room is not None:
            actor_room = _anchor_room_of(sc, actor, prefer=target_room)
        elif target_room is None and actor_room is not None:
            target_room = _anchor_room_of(sc, target, prefer=actor_room)
        # A BODY INSIDE ANOTHER IS AS CLOSE AS BODIES GET, though the inside
        # is a room of its own. `normalize_scene_contacts` keeps that pair
        # through `enclosure_joins_rooms`; this site kept the room-equality
        # test and threw it away at the source. Measured on the chat 137
        # replay (2026-09-23): every beat a swallowed player pressed her
        # hands to the walls of the throat she was in, the encoder wrote the
        # interior contact, and it was discarded here as "non-co-located" --
        # so the body she was inside never felt a thing, for seven beats.
        if actor_room is None or (
                actor_room != target_room
                and not enclosure_joins_rooms(sc, actor_room, target_room,
                                              actor, target)):
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
        if actor_is_player and standing is None and not allow_new_player_contacts:
            if report:
                report(
                    "discarded a new contact from a contestable action before "
                    "the other body had reacted")
            continue
        if standing is not None and not actor_is_player:
            actor_part = str(standing.get("actor_part") or actor_part).strip()
            # A first-person report may refine what an already-touching NPC
            # part feels like; omission may not move that part onto an
            # endpoint-free ghost relation.  Live combat ended the exact
            # forearm->shoulder frame but retained a second, coarser
            # forearm->"" contact minted here from the same onset.
            target_part = str(
                target_part or standing.get("target_part") or "").strip()
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


def _carries_player_authority(scene, assertion, player_name):
    """Does this interpret contact assertion hold its endpoint by the
    PLAYER'S authority -- her own body and her own acts, and nothing else?

    Her own act (she is the actor) always does. A contact some other body
    makes on hers does only where it says something the ledger did not: a
    first-person refinement of where it touches her (`cervix` where the
    ledger said `groin`), which is her sensation of her own body. One that
    says again what already stands -- the same two endpoints
    (`contact_id`), the same inside -- asserts nothing of hers, and the body
    that makes it keeps its own conduct. Measured on chat 178 t29-t35: the
    interpretation restated Mellisande's standing holds every beat, and the
    merge then held her lips at Hinami's throat, her hand at the waist and
    her fingertip at the groin against Mellisande's own moves
    ("preserved player-declared contact endpoint 'throat'...") -- three of
    the chat's six such blocks; the other three were Hinami's own acts and
    still hold. A contact between two bodies neither of which is hers is
    never hers to hold."""
    actor = assertion.get("actor")
    target = assertion.get("target")
    if same_subject(scene, actor, player_name):
        return True
    if not same_subject(scene, target, player_name):
        return False
    key = contact_id(assertion)
    inside = str(assertion.get("target_interior") or "").strip().casefold()
    for contact in (scene.get("contacts") or []):
        if isinstance(contact, dict) and key and contact_id(contact) == key \
                and str(contact.get("target_interior") or "").strip().casefold() \
                == inside:
            return False
    return True


def _player_contacts_held(ops, declared_actions, player_name, scene=None,
                          onset_scene=None, cast=()):
    """`(ops kept, warnings)`: the resolve's contact ops without those that
    give the PLAYER'S body an act on another body she did not declare.

    THE PLAYER IS THE ACTOR OR SHE IS NOT, and the op stores which
    (`common._check_player_contact_authority`, the reading, which names its
    own reasons -- reach rather than vocabulary, bodies rather than
    furniture). Chat 95 t40 put her tongue on a body her declared act never
    reached, and the reading only warned -- and under the prose contract it
    ran before the encoder's ops were folded, so it read an empty diff and
    warned of nothing at all. A flagged op is not committed: a body acting
    without its owner is not a soft property. A hold that already stands, in
    the stored scene or the onset the player's own declaration made
    (`onset_scene`), is the same contact said again and is never flagged --
    chat 177 t14's prose warning ("Player act not declared this beat") came
    with two such holds re-asserted, her seat on the chair and her hand on
    the plate, which change nothing and stay -- and nor is anything the world
    does TO her, which is not her act."""
    if not isinstance(ops, list) or not player_name:
        return ops, []
    standing = set()
    for source in (scene, onset_scene):
        for contact in ((source or {}).get("contacts") or []):
            if isinstance(contact, dict):
                standing.add(str(contact.get("contact_id") or ""))
                standing.add(contact_id(contact))
    standing.discard("")
    flagged = _check_player_contact_authority(
        ops, declared_actions, player_name, standing, cast)
    # HER BODY ANSWERING A TOUCH IS NOT HER REACHING FOR WHOEVER TOUCHES HER.
    # A part of another body that is on or in hers -- standing, at the onset,
    # or put there by this beat's own ops -- is something done TO her, and
    # her body closing on it is the world's to write, as a flinch is
    # (`prose_contract/director_resolve`: what bodies do involuntarily).
    # Measured on chat 155 t31, the only beat of 155 stored resolves the
    # reading flags at all: Mirelle's thumb inside her, and the encoder wrote
    # `Hinami.vaginal muscle -> Mirelle.left thumb` twice, as a clench and a
    # grip. Without this both are dropped; whether the player's reflexes are
    # the Director's to write at all is the owner's to rule.
    folded = str(player_name).strip().casefold()
    touching = set()
    for contact in [c for source in (scene, onset_scene)
                    for c in ((source or {}).get("contacts") or [])] + list(ops):
        if not isinstance(contact, dict) or str(
                contact.get("op") or "add").strip().casefold() not in ("add", "cross"):
            continue
        if str(contact.get("target") or "").strip().casefold() == folded:
            touching.add((str(contact.get("actor") or "").strip().casefold(),
                          canonical_region(contact.get("actor_part"))))
    flagged = [(index, warning) for index, warning in flagged
               if (str(ops[index].get("target") or "").strip().casefold(),
                   canonical_region(ops[index].get("target_part"))) not in touching]
    if not flagged:
        return ops, []
    drop = {index for index, _warning in flagged}
    return ([op for index, op in enumerate(ops) if index not in drop],
            [warning + " Not committed as the player's conduct."
             for _index, warning in flagged])


def _merge_player_contact_assertions(assertions, resolved_ops, report=None, *,
                                     scene=None, player_name=None):
    """Place onset truth before resolve ops without allowing silent coarsening.

    Resolve may end/move an asserted contact, but must say so with an explicit
    remove/clear first. A bare later add for the same acting part at a different
    endpoint is the common re-description drift (`cervix` -> `groin`), not an
    authored transition, and is dropped.

    ONLY WHAT THE PLAYER'S AUTHORITY COVERS IS HELD (`_carries_player_
    authority`), given the standing `scene` and the `player_name`: every
    assertion is still placed first, as the onset truth it is, but only her
    own acts and her own refinements of her own body hold an endpoint against
    the resolve. Without a scene every assertion holds, as it always did.
    """
    assertions = [dict(a) for a in (assertions or []) if isinstance(a, dict)]
    result = list(assertions)
    released = set()
    if isinstance(scene, dict) and player_name:
        unheld = {index for index, assertion in enumerate(assertions)
                  if not _carries_player_authority(scene, assertion, player_name)}
    else:
        unheld = set()

    def same_pair(left, right):
        return (_one_body(scene, left.get("actor"), right.get("actor"))
                and _one_body(scene, left.get("target"), right.get("target")))

    for raw in (resolved_ops if isinstance(resolved_ops, list) else []):
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "add").strip().casefold()
        if op in ("remove", "clear"):
            for index, assertion in enumerate(assertions):
                if op == "clear":
                    who = str(raw.get("actor") or "")
                    if not who.strip() or _one_body(scene, who, assertion.get("actor")) \
                            or _one_body(scene, who, assertion.get("target")):
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
            if index in released or index in unheld \
                    or not same_pair(assertion, raw):
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
            sheet = normalized_character_from_text(row["sheet"])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            continue
        # BOTH RESULT SETS, as `_character_material_effects` reads them: a
        # contested reactor's step is stored in `reaction_results` and the
        # reactor is then left out of the interaction loop, so its ending --
        # wrenching free of a grip -- was never read, and the Director's stale
        # re-add of the grip stood (review 2026-11-01, director floors F6).
        raws = []
        for results in (getattr(ctx, "reaction_results", None) or {},
                        getattr(ctx, "character_results", None) or {}):
            result = results.get(cid) or results.get(str(cid)) or {}
            if isinstance(result, dict):
                raws.extend(result.get("contact_ops") or [])
        cname = character_name(sheet)
        options = contacts_of(sc, cname)
        for raw in raws:
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


def _merge_character_contact_endings(endings, resolved_ops, report=None, *,
                                     scene=None):
    """Project completed endings and reject a stale same-contact re-add.

    ``contact_ops`` describes the state at the end of the character's own
    declaration.  If that declaration explicitly ended contact:N, a Director
    echoing the onset contact is stale, not a later transition.  A genuinely
    resumed contact should remain standing in the character declaration and
    therefore must not emit the removal ref.
    """
    endings = [dict(op) for op in (endings or []) if isinstance(op, dict)]

    def part(op, field):
        return str(op.get(field) or "").strip().casefold()

    def ended(raw):
        # Either direction is the same physical relation; each body by every
        # name it answers to (`_one_body`), the parts as written -- a re-add
        # under her full name re-added a contact she had ended (review
        # 2026-11-01, director floors F4).
        for end in endings:
            for actor, actor_part, target, target_part in (
                    ("actor", "actor_part", "target", "target_part"),
                    ("target", "target_part", "actor", "actor_part")):
                if (_one_body(scene, raw.get("actor"), end.get(actor))
                        and part(raw, "actor_part") == part(end, actor_part)
                        and _one_body(scene, raw.get("target"), end.get(target))
                        and part(raw, "target_part") == part(end, target_part)):
                    return True
        return False

    result = list(endings)
    for raw in (resolved_ops if isinstance(resolved_ops, list) else []):
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "add").strip().casefold()
        if op in ("add", "cross") and ended(raw):
            if report:
                report("discarded Director re-add of character-ended contact")
            continue
        if raw not in result:
            result.append(raw)
    return result
