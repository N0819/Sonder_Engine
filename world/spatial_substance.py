# spatial_substance.py
"""Substances on and in bodies: placement, pooling, absorption, consumption,
transfer, and speech impediment."""

import hashlib

from world.spatial_contacts import (_part_identity, _same_region, contact_relation,
                              same_owned_region)
from world.spatial_identity import canonical_subject, same_subject


# Non-discrete matter which remains somewhere after a beat.  This is distinct
# from contact (a relation between bodies) and inventory (discrete objects): a
# liquid in a vessel, residue on a surface, gas in a chamber, powder in a wound
# or any fictional equivalent is matter located relative to a target.
_SUBSTANCE_PLACEMENTS = frozenset({"surface", "interior", "contained", "room"})


# Part kinds (per `_part_identity`) whose engagement mis-forms speech, split
# by HOW. Deliberately narrow: lips resting ON something (a hair-kiss residue,
# a shoulder) leave the mouth free to turn and speak -- measured live, lips on
# a scalp for six beats accompanied perfectly ordinary conversation that a
# broader rule would have wrongly flagged -- so on the speaker's own side only
# the TONGUE counts at surface relation: it is the articulator, and a tongue
# extended onto another body cannot also shape words. Direction decides the
# rest, as elsewhere: another body pressed against the speaker's mouth blocks
# it; a hand resting on the speaker's cheek does not.
_SPEECH_MOUTH_KINDS = frozenset({"mouth", "lip", "tongue"})
_SPEECH_CAVITY_INTERIORS = frozenset({"mouth", "throat"})

# How an impediment mis-forms the utterance. This is FORMATION, not
# transmission: the sound leaves the mouth already malformed and then travels
# normally, so it is identical for every listener and does not vary with
# distance or barriers -- which is exactly why it is not a hear_level. It sits
# beside `volume`, the other fact about how a sound was MADE.
ARTICULATION_STIFLED = "stifled"   # the mouth is filled, sealed, or covered
ARTICULATION_SLURRED = "slurred"   # the tongue is engaged on a surface


def speech_articulation_impediment(scene: dict, speaker: str) -> tuple:
    """(kind, reason) for how this speaker's mouth mis-forms speech now.

    Reads only the standing contact ledger. Kinds, by severity:

      - "stifled": something is INSIDE the speaker's mouth or throat; the
        speaker's own mouth-part is inside another body; or another body is
        pressed against the speaker's mouth from outside. Words can barely
        be shaped at all.
      - "slurred": the speaker's own TONGUE is engaged on another body's
        surface. Measured live (chat 69, turns 74-75): full clean sentences
        at `normal` volume while the beat's own ops re-asserted her tongue
        mid-lick -- you cannot articulate cleanly with your tongue on
        someone.

    Returns ("", "") when nothing impedes. The reason is a clause naming the
    impediment, for a notice; the KIND is what deterministic delivery keys
    on. The ledger can hold a stale contact, so callers that act on this
    (rather than merely reporting) should prefer the mildest true rendering.
    """
    name = str(speaker or "").strip()
    if not name:
        return "", ""
    slurred = None
    for contact in (scene or {}).get("contacts") or []:
        if not isinstance(contact, dict):
            continue
        actor = str(contact.get("actor") or "")
        target = str(contact.get("target") or "")
        speaker_is_actor = same_subject(scene, actor, name)
        speaker_is_target = same_subject(scene, target, name)
        if not speaker_is_actor and not speaker_is_target:
            continue
        relation = contact_relation(contact)
        actor_kind = _part_identity(contact.get("actor_part"))[0]
        target_kind = _part_identity(contact.get("target_part"))[0]
        interior = _part_identity(contact.get("target_interior"))[0]
        if speaker_is_target and relation == "interior" \
                and interior in _SPEECH_CAVITY_INTERIORS:
            return (ARTICULATION_STIFLED,
                    f"{actor}'s {contact.get('actor_part') or 'body'} is "
                    f"inside {name}'s {contact.get('target_interior')}")
        if speaker_is_actor and relation == "interior" \
                and actor_kind in _SPEECH_MOUTH_KINDS:
            return (ARTICULATION_STIFLED,
                    f"{name}'s {contact.get('actor_part')} is inside "
                    f"{target}'s "
                    f"{contact.get('target_interior') or 'body'}")
        if speaker_is_target and relation == "surface" \
                and target_kind in _SPEECH_MOUTH_KINDS \
                and actor_kind not in _SPEECH_MOUTH_KINDS:
            return (ARTICULATION_STIFLED,
                    f"{actor}'s {contact.get('actor_part') or 'body'} is "
                    f"pressed against {name}'s "
                    f"{contact.get('target_part')}")
        if slurred is None and speaker_is_actor and relation == "surface" \
                and actor_kind == "tongue":
            # Held rather than returned: a stifled impediment elsewhere in
            # the ledger outranks a slur, whatever the list order.
            slurred = (ARTICULATION_SLURRED,
                       f"{name}'s tongue is against {target}'s "
                       f"{contact.get('target_part') or 'body'}")
    return slurred or ("", "")


def _substance_text(value, limit=160):
    return " ".join(str(value or "").split())[:limit]


def _substance_placement(value):
    raw = _substance_text(value, 32).casefold().replace("_", " ")
    aliases = {
        "on": "surface", "coating": "surface", "coat": "surface",
        "inside": "interior", "internal": "interior", "within": "interior",
        "container": "contained", "in container": "contained",
        "environment": "room", "ambient": "room",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in _SUBSTANCE_PLACEMENTS else ""


def _interior_destination_for_release(scene, source, source_part):
    """Unique standing interior that encloses ``source_part``, or None.

    This is the content-agnostic causal hardening: a nozzle in a tank, needle
    in a vein, pipe in a chamber, fang in tissue, or any invented equivalent
    supplies the destination of matter released by that inserted part.  The
    code knows topology, never what the matter ought to be.
    """
    source_part = _substance_text(source_part, 120).casefold()
    if not source_part:
        return None
    matches = []
    for contact in (scene or {}).get("contacts") or []:
        if not isinstance(contact, dict) or contact_relation(contact) != "interior":
            continue
        if not same_subject(scene, contact.get("actor"), source):
            continue
        if _substance_text(contact.get("actor_part"), 120).casefold() != source_part:
            continue
        matches.append(contact)
    return matches[0] if len(matches) == 1 else None


def _substance_id(record):
    supplied = _substance_text(record.get("substance_id") or record.get("id"), 120)
    if supplied:
        return supplied
    identity = "\x1f".join(_substance_text(record.get(field), 160).casefold()
                            for field in (
                                "source", "source_part", "substance", "target",
                                "placement", "target_interior", "target_part"))
    return "substance:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def _substance_target_exists(scene, target):
    """Whether a material destination is a live room, body, or entity."""
    label = str(target or "").strip()
    if not label:
        return False
    folded = label.casefold()
    if any(str(room_id).strip().casefold() == folded
           for room_id in ((scene or {}).get("rooms") or {})):
        return True
    if any(same_subject(scene, key, label)
           for key in ((scene or {}).get("positions") or {})):
        return True
    for entity_id, entity in ((scene or {}).get("entities") or {}).items():
        if same_subject(scene, entity_id, label):
            return True
        if not isinstance(entity, dict):
            continue
        if same_subject(scene, entity.get("name"), label):
            return True
        if any(same_subject(scene, alias, label)
               for alias in (entity.get("aliases") or [])):
            return True
    return False


def _resolved_substance_add(scene, raw, report=None):
    if not isinstance(raw, dict):
        return None
    source = canonical_subject(scene, _substance_text(raw.get("source"), 120))
    source_part = _substance_text(raw.get("source_part"), 120)
    substance = _substance_text(raw.get("substance"), 160)
    target = canonical_subject(scene, _substance_text(raw.get("target"), 120))
    placement = _substance_placement(raw.get("placement"))
    target_interior = _substance_text(raw.get("target_interior"), 160)
    target_part = _substance_text(raw.get("target_part"), 120)
    if not source or not substance:
        if report:
            report("discarded substance add without both source and substance")
        return None

    interior = _interior_destination_for_release(scene, source, source_part)
    if interior is not None:
        derived_target = canonical_subject(
            scene, _substance_text(interior.get("target"), 120))
        derived_interior = _substance_text(
            interior.get("target_interior"), 160)
        derived_part = _substance_text(interior.get("target_part"), 120)
        if target and not same_subject(scene, target, derived_target):
            if report:
                report("discarded substance add whose target contradicted standing interior topology")
            return None
        if placement and placement != "interior":
            if report:
                report("discarded substance add whose placement contradicted standing interior topology")
            return None
        # Region slots compare through `_same_region`, not as raw text: this
        # check DISCARDS the whole op on disagreement, so a re-spelling of the
        # same cavity used to cost a release outright. Measured live (chat 69
        # ⎇49, turn 66) that is exactly what happened -- a deposit declared
        # into one cavity was thrown away against a differently worded
        # standing one, leaving only a warning behind.
        if target_interior and not _same_region(target_interior, derived_interior):
            if report:
                report("discarded substance add whose target_interior contradicted standing interior topology")
            return None
        if target_part and not _same_region(target_part, derived_part):
            if report:
                report("discarded substance add whose target_part contradicted standing interior topology")
            return None
        target = target or derived_target
        target_interior = target_interior or derived_interior
        target_part = target_part or derived_part
        placement = placement or "interior"

    if not placement:
        placement = "interior" if target_interior else "surface"
    if placement != "interior" and target_interior:
        # An enclosure named beside a non-interior placement is a cavity the
        # record has no room for, and every consumer reads `target_interior`
        # as a structure of the TARGET. Live (chat 69 ⎇49, turn 78): saliva
        # stored `target: Hinami, placement: surface, target_interior: mouth`
        # while Hinami was inside Elyra Voss -- the mouth was Elyra's, and the
        # recipient's own payload handed it back to her as hers. Drop the
        # slot rather than promoting the placement: the Director said the
        # matter landed on a SURFACE, and inferring an enclosure it did not
        # claim would invent topology from a stray field.
        if report:
            report(f"dropped enclosure {target_interior!r} from a "
                   f"{placement} deposit -- target_interior is a structure of "
                   "the target's own body and belongs only to an interior "
                   "placement")
        target_interior = ""
    if not target:
        if report:
            report("discarded substance add without a target or unique interior destination")
        return None
    if not _substance_target_exists(scene, target):
        if report:
            report("discarded substance add whose target is not present in the scene")
        return None
    if placement == "interior" and not target_interior:
        if report:
            report("discarded interior substance add without an enclosing target_interior")
        return None

    # NO derived ownership check here, and this is a measured refusal rather
    # than an omission. A slot's POSITION states whose body its region is, so
    # `{target: Hinami, target_part: glans}` is a perfectly well-formed owned
    # region -- `owned_region` makes it unambiguous but cannot make it TRUE.
    # Judging the truth of the claim needs evidence, and the only evidence
    # available without an anatomy model is what the other ledgers happen to
    # have asserted already.
    #
    # Replayed over every stored beat, that evidence answers 72 times in 2,066
    # part assertions and is right ONCE (turn 62's `glans` on Hinami). The
    # other 71 are ordinary anatomy whose first mention happened to be the
    # other body -- hand, waist, chest, mouth, hips, face, shoulder -- and
    # clearing those would destroy correct endpoints on 3.4% of every contact
    # this engine records.
    #
    # It is also self-poisoning, which is the part that settles it: the index
    # is built from the ledgers, so turn 62's bad `glans` became the scene's
    # belief, and by turn 64 the same check flagged a CORRECT record about the
    # body that actually has one. One wrong assertion inverts the check for
    # everything after it.
    #
    # Explicit ownership is the fix the shape of the data actually wants: the
    # Director naming whose region it is, in the record, rather than the
    # engine inferring it from history. That is a schema change and is not
    # taken here.

    record = {
        "source": source,
        "source_part": source_part,
        "substance": substance,
        "target": target,
        "placement": placement,
        "target_interior": target_interior,
        "target_part": target_part,
        "amount": _substance_text(raw.get("amount"), 80),
        "detail": _substance_text(raw.get("detail"), 240),
        # What this matter SMELLS of, deliberately beside `amount` and
        # `detail` rather than among the identity fields: matter deposited
        # somewhere is the commonest smell in play, and how much of it there
        # is and how it smells now are both facts a later release
        # re-describes. Hashing it into `_substance_id` would file drying
        # blood as a second puddle beside fresh.
        "scent": _substance_text(raw.get("scent"), 160),
    }
    # Adds derive identity from physical semantics. A model-supplied id could
    # otherwise overwrite an unrelated standing record; ids are selectors for
    # removal, not authority to choose an add's storage key.
    record["substance_id"] = _substance_id(record)
    return record


def resolve_substance_ops(scene: dict, ops, report=None) -> list[dict]:
    """Normalize substance operations against the PRE-BEAT contact topology.

    The returned add records are also the exact event deltas perception may
    deliver this beat.  Remove/clear operations remain selectors and never
    become sensory events themselves.
    """
    resolved = []
    for raw in (ops if isinstance(ops, list) else []):
        if not isinstance(raw, dict):
            continue
        op = _substance_text(raw.get("op") or "add", 32).casefold()
        if op in ("add", "release", "deposit"):
            record = _resolved_substance_add(scene, raw, report=report)
            if record is not None:
                resolved.append({"op": "add", **record})
            continue
        if op not in ("remove", "clear"):
            if report:
                report(f"discarded unknown substance op {op!r}")
            continue
        selector = {
            "op": op,
            "substance_id": _substance_text(
                raw.get("substance_id") or raw.get("id"), 120),
            "source": canonical_subject(
                scene, _substance_text(raw.get("source"), 120)),
            "substance": _substance_text(raw.get("substance"), 160),
            "target": canonical_subject(
                scene, _substance_text(raw.get("target"), 120)),
            "placement": _substance_placement(raw.get("placement")),
            "target_interior": _substance_text(raw.get("target_interior"), 160),
            "target_part": _substance_text(raw.get("target_part"), 120),
        }
        if not any(selector[field] for field in selector if field != "op"):
            if report:
                report("discarded unbounded substance removal")
            continue
        resolved.append(selector)
    return resolved


def _same_pool(scene, a, b) -> bool:
    """Are these two rows one pool of matter, rather than two deposits?

    The substance ledger's answer to the rule the contact ledger has had all
    along (`_displaces`): the same material, from the same source, on the same
    region of the same body is ONE pool that a later release re-describes --
    not a second puddle beside the first.

    Measured live (chat 69 ⎇49): three saliva rows on one region of one body
    across turns 74/78/80, held apart only by which part of the source
    delivered them, all three delivered to her every beat thereafter.

    Identity deliberately excludes `source_part` (saliva delivered by a tongue
    and then by a mouth is the same saliva), `amount` and `detail` (how much
    is there now, and what it is like now, are what a re-description UPDATES).
    It keeps `source`, because perception strips provenance per observer and
    two bodies' matter in one place is two facts about who was there.

    This subsumes the older blurred-twin fold and replaces it. That one caught
    the narrower measured case -- a Director narrating one release emits it
    twice in a beat, once as `add` carrying the endpoint part and once as
    `deposit` without it, and `_substance_id` hashes the part slots, so a
    single release stood in the saved scene as two verbatim-identical rows
    differing only in an empty `target_part`. Every such pair is also one
    pool, so keeping both predicates would leave two answers to one question,
    free to drift.

    A record inside an enclosure pools on the ENCLOSURE (see `_record_region`):
    matter at the inlet and matter at the outlet of one reservoir is one
    reservoir of matter. With no enclosure named, the part is the place.

    The place is asked as ONE qualified question (`same_owned_region`), not as
    a body compared here and a region compared there. The earlier version
    compared `target` as raw casefolded text, which is precisely the `==` that
    `same_subject` exists to replace -- a being carrying a display name and an
    entity id at once would have kept two pools on one region of one body.
    """
    for field in ("substance", "placement"):
        if _substance_text(a.get(field), 240).casefold() \
                != _substance_text(b.get(field), 240).casefold():
            return False
    if not same_subject(scene, a.get("source"), b.get("source")):
        return False
    left, right = _record_region(a), _record_region(b)
    if bool(left) != bool(right):
        return False
    if not left:
        return same_subject(scene, a.get("target"), b.get("target"))
    return same_owned_region(scene, a.get("target"), left,
                             b.get("target"), right)


def _record_region(record) -> str:
    """Where on its target a standing record sits: the enclosure, else the part."""
    return _substance_text(record.get("target_interior"), 160) \
        or _substance_text(record.get("target_part"), 120)


def _absorb_into_pool(standing: dict, arriving: dict) -> dict:
    """Fold a later release into the pool already standing there.

    The arriving row is the current account of that pool, so `amount`,
    `detail` and `scent` replace what was there -- a re-description says how
    much is there NOW, and what it smells of now. Silence is still silence:
    an op that says nothing about the smell does not blank the standing one.
    The part slots only ever gain precision: a release that named an
    endpoint fills a slot the earlier one left silent, and never blanks one.
    The standing record keeps its own `substance_id`, which is what makes a
    `{op:'remove', substance_id}` selector minted from an earlier payload
    still find the row.
    """
    for field in ("amount", "detail", "scent"):
        value = _substance_text(arriving.get(field), 240)
        if value:
            standing[field] = arriving.get(field, "")
    for field in ("source_part", "target_part", "target_interior"):
        if not _substance_text(standing.get(field), 160):
            standing[field] = arriving.get(field, "")
    return standing


def _stock_consumed_by(scene, record, current) -> list:
    """Standing record ids this add's SOURCE region gives up to it.

    Matter arriving somewhere never left where it came from, and the op
    vocabulary has no way to say so: `add` states a destination and nothing
    else, `remove` is a separate op the Director has to remember, and measured
    across the whole stored corpus it remembered 5 times against 38 deposits.
    So the departure is derived here instead, where both ends are already in
    hand -- the deterministic floor must not depend on a model cooperating.

    Two conditions, and both are structural:

    * the standing record sits at the SAME OWNED REGION this add names as its
      origin -- the body it names as `source`, at the place it names as
      `source_part`, asked as one qualified question through
      `same_owned_region`. Matter leaves the moving body's own region, never
      the same-named region on somebody else standing in the room;
    * that matter is FOREIGN to the body holding it -- its own `source` is
      somebody else. Matter a body produces at one of its own regions is a
      source, not a stock: a gland does not stop existing because some of what
      it made was moved, and the same rule would otherwise empty it.

    Substance NAMES are deliberately never compared. The Director renamed one
    material three times across turns 61/66/70 of the measured story ("fluid",
    "seed", "Elyra Voss seed"), so a name-matched rule would have fired on
    none of them.

    Known limit, and it is the honest one: this retires the whole standing
    record, because `amount` is free text and nothing can yet order "a small
    spill" against "the remainder". A partial transfer therefore clears its
    origin early. That is the recoverable direction of the two -- the Director
    can deposit again, whereas the failure this replaces stood for 19 turns
    and was still being delivered to the recipient after she had left the room.
    """
    source = _substance_text(record.get("source"), 120)
    source_part = _substance_text(record.get("source_part"), 120)
    if not source or not source_part:
        return []
    consumed = []
    for sid, standing in current.items():
        if sid == record.get("substance_id"):
            continue  # never let an add eat itself
        if same_subject(scene, standing.get("source"), standing.get("target")):
            continue  # the body's own product at its own region
        if same_owned_region(scene, standing.get("target"),
                             _record_region(standing), source, source_part):
            consumed.append(sid)
    return consumed


def apply_substance_ops(scene: dict, ops, report=None) -> dict:
    """Apply add/remove/clear operations to ``scene.substances``."""
    current = {}
    for raw_record in ((scene or {}).get("substances") or []):
        if not isinstance(raw_record, dict) or not raw_record.get("source") \
                or not raw_record.get("substance") or not raw_record.get("target"):
            continue
        record = dict(raw_record)
        # An enclosure stored beside a non-interior placement is somebody
        # else's cavity (see `_resolved_substance_add`). Shed it on read as
        # well as on write, or the stored rows never heal -- and while it
        # stands it also keeps the row out of its own pool, because
        # `_record_region` prefers the enclosure and would file one coating
        # under a cavity and its twin under the body it is actually on.
        if _substance_placement(record.get("placement")) != "interior" \
                and _substance_text(record.get("target_interior"), 160):
            record["target_interior"] = ""
        record["substance_id"] = _substance_id(record)
        pooled_id = next((sid for sid, standing in current.items()
                          if _same_pool(scene, standing, record)), None)
        if pooled_id is not None:
            # A scene saved before the fold below can already carry the stack;
            # pool it on read so the ledger heals on the next merge rather
            # than carrying every row forever. Rows arrive in the order they
            # were written, so the later one is the current account.
            _absorb_into_pool(current[pooled_id], record)
            continue
        current[record["substance_id"]] = record
    for raw in resolve_substance_ops(scene, ops, report=report):
        op = raw.get("op")
        if op == "add":
            record = {k: v for k, v in raw.items() if k != "op"}
            pooled_id = next(
                (sid for sid, standing in current.items()
                 if _same_pool(scene, standing, record)), None)
            # Conservation runs against the ledger as it stood BEFORE this add
            # lands, and BEFORE pooling, so a deposit can never consume itself
            # and a destination that already held some does not excuse the
            # origin. It runs per add rather than once per beat, so two
            # releases in one beat each empty their own origin.
            #
            # Found by replaying the live ledger: pooling used to return here
            # first, and the measured swallow deposited into a stomach that
            # already had a row -- so the mouth was never emptied at all.
            for sid in _stock_consumed_by(scene, record, current):
                if sid == pooled_id:
                    continue  # the destination is not its own origin
                if report:
                    gone = current[sid]
                    report(
                        f"{_substance_text(gone.get('substance'), 160)!r} left "
                        f"{_substance_text(gone.get('target'), 120)}'s "
                        f"{_record_region(gone)} -- "
                        f"{_substance_text(record.get('source'), 120)} moved "
                        f"matter out of that region this beat")
                current.pop(sid, None)
            if pooled_id is not None:
                # The standing record keeps its own id, so a removal by either
                # id's selector still finds one row rather than half of two.
                _absorb_into_pool(current[pooled_id], record)
                continue
            current[record["substance_id"]] = record
            continue

        def matches(record):
            sid = raw.get("substance_id")
            if sid and str(record.get("substance_id")) != sid:
                return False
            for field in ("source", "target"):
                if raw.get(field) and not same_subject(
                        scene, record.get(field), raw[field]):
                    return False
            for field in ("substance", "placement", "target_interior", "target_part"):
                if raw.get(field) and _substance_text(
                        record.get(field), 160).casefold() != raw[field].casefold():
                    return False
            return True

        current = {sid: record for sid, record in current.items()
                   if not matches(record)}
    scene["substances"] = list(current.values())
    return scene


def substances_for(scene: dict, name: str) -> list[dict]:
    """Every persistent substance record for which ``name`` is source/target."""
    return [record for record in ((scene or {}).get("substances") or [])
            if isinstance(record, dict)
            and (same_subject(scene, record.get("source"), name)
                 or same_subject(scene, record.get("target"), name))]


def substance_event_clause(event: dict, *, you: str, scene: dict) -> str:
    """First-person immediate percept for a newly added substance record.

    Cause-blind for the recipient: an internal target legitimately knows the
    material consequence reached them, not necessarily who caused it.  Hidden
    interior deposition never returns a bystander clause.
    """
    if not isinstance(event, dict) or str(event.get("op") or "add") != "add":
        return ""
    substance = _substance_text(event.get("substance"), 160)
    amount = _substance_text(event.get("amount"), 80)
    detail = _substance_text(event.get("detail"), 240)
    if not substance:
        return ""
    target_is_you = same_subject(scene, event.get("target"), you)
    source_is_you = same_subject(scene, event.get("source"), you)
    placement = _substance_placement(event.get("placement"))
    material = f"{amount} of {substance}" if amount else substance
    if target_is_you:
        if placement == "interior":
            interior = _substance_text(event.get("target_interior"), 160)
            clause = f"Your {interior or 'interior'} registers {material} being deposited within it"
        elif placement == "surface":
            part = _substance_text(event.get("target_part"), 120)
            clause = f"Your {part or 'surface'} registers {material} being deposited on it"
        else:
            clause = f"You register {material} entering what you contain"
    elif source_is_you:
        part = _substance_text(event.get("source_part"), 120)
        clause = f"You register releasing {material} from your {part or 'body'}"
    else:
        return ""
    if detail and (source_is_you or same_subject(
            scene, event.get("source"), event.get("target"))):
        clause += f", {detail}"
    return clause
