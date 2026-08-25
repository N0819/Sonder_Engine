# spatial_substance.py
"""Substances on and in bodies: placement, pooling, absorption, consumption,
transfer, and speech impediment."""

import hashlib

from world.spatial_contacts import (
    _part_identity,
    _same_region,
    contact_id,
    contact_relation,
    same_owned_region,
)
from world.spatial_identity import canonical_subject, same_subject


# Non-discrete matter which remains somewhere after a beat.  This is distinct
# from contact (a relation between bodies) and inventory (discrete objects): a
# liquid in a vessel, residue on a surface, gas in a chamber, powder in a wound
# or any fictional equivalent is matter located relative to a target.
_SUBSTANCE_PLACEMENTS = frozenset({"surface", "interior", "contained", "room"})

# Magnitude is model-authored structure, never recovered from English prose.
# The free-text `amount` remains the fiction's wording; `amount_band` is only
# an optional comparison value for an explicitly declared transfer.
SUBSTANCE_AMOUNT_BANDS = ("trace", "small", "moderate", "large", "flooding")
SUBSTANCE_PORTIONS = ("trace", "some", "most", "all")


def substance_amount_band(value) -> str:
    raw = _substance_text(value, 32).casefold().replace("_", " ")
    aliases = {"light": "small", "copious": "large", "flood": "flooding"}
    raw = aliases.get(raw, raw)
    return raw if raw in SUBSTANCE_AMOUNT_BANDS else ""


def substance_portion(value) -> str:
    raw = _substance_text(value, 32).casefold()
    return raw if raw in SUBSTANCE_PORTIONS else ""


# A band names HOW MUCH, not a thing, so it cannot stand where a noun phrase
# does. Every phrase keeps "of" because mass-vs-count cannot be recovered from
# free text: "a small amount of fluids" is grammatical where "a little fluids"
# is not.
_AMOUNT_BAND_PHRASES = {
    "trace": "a trace of",
    "small": "a small amount of",
    "moderate": "a moderate amount of",
    "large": "a large amount of",
    "flooding": "a flood of",
}


def _material_phrase(amount, substance) -> str:
    """Name a quantity of a substance in language rather than in register.

    `amount` is free text and the Director routinely writes the BAND
    VOCABULARY itself into it. A band is a magnitude, not a noun phrase, so
    the naive join put the engine's own register on the page: measured, the
    view read "Your palm registers moderate of oil being deposited on it".

    Any other wording is the fiction's own and passes through untouched --
    `substance_amount_band` matches the whole string only, so "a thin smear"
    is not a band.
    """
    amount = str(amount or "").strip()
    band = substance_amount_band(amount)
    if band:
        return f"{_AMOUNT_BAND_PHRASES[band]} {substance}"
    return f"{amount} of {substance}" if amount else str(substance)


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

    Reads standing topology plus an explicit material affordance. Quantity is
    not an articulation law: water, smoke, foam and magical silence can occupy
    the same named cavity with different consequences. A substance therefore
    affects speech only when the fiction records `speech_impediment`.

    Kinds, by severity:

      - "stifled": something is INSIDE the speaker's mouth or throat; the
        speaker's own mouth-part is inside another body; another body is
        pressed against the speaker's mouth from outside; the speaker's own
        mouth is explicitly sealed against another body's surface; or a
        standing substance explicitly carries that affordance.
      - "slurred": the speaker's own TONGUE is engaged on an external
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
        # A mouth merely touching a surface is not necessarily sealed. The
        # manner supplies that fact; otherwise a kiss on a cheek, drinking
        # from a cup, and invented anatomy all become the same obstruction.
        manner = str(contact.get("manner") or "").strip().casefold()
        if speaker_is_actor and relation == "surface" \
                and actor_kind == "mouth" \
                and manner in {"seal", "sealed", "cover", "covered"}:
            return (ARTICULATION_STIFLED,
                    f"{name}'s mouth is sealed against {target}'s "
                    f"{contact.get('target_part') or 'body'}")
        if slurred is None and speaker_is_actor and relation == "surface" \
                and actor_kind == "tongue":
            # Held rather than returned: a stifled impediment elsewhere in
            # the ledger outranks a slur, whatever the list order.
            slurred = (ARTICULATION_SLURRED,
                       f"{name}'s tongue is against {target}'s "
                       f"{contact.get('target_part') or 'body'}")
    # Material consequences are explicit and world-specific. The core locates
    # and enforces the affordance; it does not infer physiology from prose.
    for record in (scene or {}).get("substances") or []:
        if not isinstance(record, dict):
            continue
        if not same_subject(scene, record.get("target"), name):
            continue
        if _substance_placement(record.get("placement")) != "interior":
            continue
        interior = _part_identity(record.get("target_interior"))[0]
        if interior not in _SPEECH_CAVITY_INTERIORS:
            continue
        impediment = _substance_text(
            record.get("speech_impediment"), 32).casefold()
        if impediment not in {ARTICULATION_SLURRED, ARTICULATION_STIFLED}:
            continue
        substance = _substance_text(record.get("substance"), 160) or "matter"
        cavity = _substance_text(record.get("target_interior"), 160) \
            or interior
        return (impediment,
                f"{name}'s {cavity} holds "
                f"{_material_phrase(_substance_text(record.get('amount'), 80), substance)}")
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
        "amount_band": substance_amount_band(raw.get("amount_band")),
        "detail": _substance_text(raw.get("detail"), 240),
        # What this matter SMELLS of, deliberately beside `amount` and
        # `detail` rather than among the identity fields: matter deposited
        # somewhere is the commonest smell in play, and how much of it there
        # is and how it smells now are both facts a later release
        # re-describes. Hashing it into `_substance_id` would file drying
        # blood as a second puddle beside fresh.
        "scent": _substance_text(raw.get("scent"), 160),
        # World-specific affordance, never inferred from the material name or
        # amount. Empty means the material has no deterministic speech rule.
        "speech_impediment": (
            _substance_text(raw.get("speech_impediment"), 32).casefold()
            if _substance_text(raw.get("speech_impediment"), 32).casefold()
            in {ARTICULATION_SLURRED, ARTICULATION_STIFLED} else ""),
        # Transfer metadata is consumed by apply_substance_ops and is not part
        # of the destination pool's durable identity.
        "source_substance_id": _substance_text(
            raw.get("source_substance_id"), 120),
        "portion": substance_portion(raw.get("portion")),
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
    for field in ("amount", "amount_band", "detail", "scent",
                  "speech_impediment"):
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


def _apply_explicit_transfer(current, record, report=None) -> bool:
    """Apply one explicitly identified qualitative transfer.

    Returns True when the add named a source pool, including when that source
    could not be found. Free prose is never parsed into magnitude. Unknown
    bands preserve the source unless the fiction explicitly says `all`.
    """
    source_id = _substance_text(record.get("source_substance_id"), 120)
    if not source_id:
        return False
    source = current.get(source_id)
    if not isinstance(source, dict):
        if report:
            report(f"substance transfer source {source_id!r} was not present")
        return True
    portion = substance_portion(record.get("portion")) or "all"
    if portion == "all":
        current.pop(source_id, None)
        return True
    band = substance_amount_band(source.get("amount_band"))
    if not band:
        if report:
            report(
                f"preserved transfer source {source_id!r}: partial portion "
                "requires its explicit amount_band")
        return True
    index = SUBSTANCE_AMOUNT_BANDS.index(band)
    if portion == "most":
        source["amount_band"] = "trace"
    elif portion == "some" and index > 0:
        source["amount_band"] = SUBSTANCE_AMOUNT_BANDS[index - 1]
    # `trace` moves too little to lower a qualitative band.
    return True


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
            source_id = _substance_text(
                record.get("source_substance_id"), 120)
            # Moving a named portion back into its own already-pooled
            # destination changes no stock; it only re-describes that pool.
            explicit_transfer = bool(source_id and source_id == pooled_id)
            if not explicit_transfer:
                explicit_transfer = _apply_explicit_transfer(
                    current, record, report=report)
            if not explicit_transfer:
                # Backward-compatible all-or-nothing conservation for older
                # ops that identify an origin only by source/source_part. New
                # partial transfers name source_substance_id + portion.
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
            record.pop("source_substance_id", None)
            record.pop("portion", None)
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


#: What a substance op can name. `detail` is deliberately absent: it is
#: destination-side prose, not part of the record's address.
_SUBSTANCE_INDEX_FIELDS = (
    "substance", "source", "source_part", "target", "target_part",
    "target_interior", "placement", "amount", "amount_band", "scent",
)


def substance_ledger_index(scene: dict) -> list[dict]:
    """The standing substance ledger, each row carrying its own id.

    The ledger's OWNER -- the one hand entitled to `substance_ops` -- could
    not see it. Its prompt documents closing a record by `substance_id` and
    no id had ever been handed to it, so a drained or washed-away deposit
    could only be described around, never closed. This is the addressing
    surface for the ops that already exist; it adds no mechanism, per
    `docs/design/DESIGN_MATERIAL_MODEL.md` §1.

    Ids are recomputed the way `apply_substance_ops` stamps them, including
    the same shedding of an enclosure stored beside a non-interior
    placement, so a record saved before stamping is addressable too and the
    id quoted back always finds the row it named.
    """
    out = []
    for raw in ((scene or {}).get("substances") or []):
        if not isinstance(raw, dict) or not raw.get("source") \
                or not raw.get("substance") or not raw.get("target"):
            continue
        record = dict(raw)
        if _substance_placement(record.get("placement")) != "interior" \
                and _substance_text(record.get("target_interior"), 160):
            record["target_interior"] = ""
        row = {"substance_id": _substance_id(record)}
        for field in _SUBSTANCE_INDEX_FIELDS:
            value = _substance_text(record.get(field), 160)
            if value:
                row[field] = value
        out.append(row)
    return out


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
    material = _material_phrase(amount, substance)
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


# ---------------------------------------------------------------------------
# Contact effects: durable dynamics performed through a standing contact.
# The external channel remains `contact_action_ops`; internally every record
# is attached to a stable contact id and dies with that parent relation.
# ---------------------------------------------------------------------------

_MAX_CONTACT_ACTIONS = 80


def _contact_action_text(value, limit=160):
    return " ".join(str(value or "").replace("_", " ").split())[:limit]


def _contact_by_id(scene, value):
    needle = _contact_action_text(value, 80).casefold()
    if not needle:
        return None
    matches = [c for c in (scene or {}).get("contacts") or []
               if isinstance(c, dict)
               and contact_id(c).casefold() == needle]
    return matches[0] if len(matches) == 1 else None


def _selector_contact(scene, selector):
    if not isinstance(selector, dict):
        return None
    a = selector.get("actor")
    ap = selector.get("actor_part")
    t = selector.get("target")
    tp = selector.get("target_part")
    if not all(_contact_action_text(v) for v in (a, ap, t, tp)):
        return None

    def side_matches(contact, left, left_part, right, right_part):
        return (same_subject(scene, contact.get("actor"), left)
                and _same_region(contact.get("actor_part"), left_part)
                and same_subject(scene, contact.get("target"), right)
                and _same_region(contact.get("target_part"), right_part))

    matches = []
    for contact in (scene or {}).get("contacts") or []:
        if not isinstance(contact, dict):
            continue
        if side_matches(contact, a, ap, t, tp) or side_matches(
                contact, t, tp, a, ap):
            matches.append(contact)
    return matches[0] if len(matches) == 1 else None


def resolve_contact_action_ref(scene, value):
    """Resolve a durable contact id or an exact structured endpoint selector."""
    contact = _selector_contact(scene, value) if isinstance(value, dict) \
        else _contact_by_id(scene, value)
    return (contact_id(contact), contact) if contact is not None else ("", None)


def _contact_action_key(actor, contact_ref):
    """One participant drives ONE ongoing dynamic through one contact.

    The action TEXT is that dynamic's DESCRIPTION and is deliberately NOT
    part of its identity: a literal identity fails exactly when a model
    rewrites, and the corpus shows it did. Re-measured 2026-08-25 across
    every stored scene: 11 effect rows on 3 contacts, and each of the four
    multi-row groups is one dynamic reworded -- "steady peristaltic wave" /
    "slow steady peristaltic wave" / "steady pressure" whose rhythm restates
    the first (chat 88, contact:8a4058a942b38470dbb4). The composer renders
    one sentence per row, so an observer's four-sentence view carried three
    saying the same thing, and the narrator's own fidelity check flagged it
    reusing previous content on 5 of 15 turns. No corpus contact has ever
    carried two genuinely distinct effects by one participant; distinct
    part-pairs remain distinct contacts, and each participant keeps its own
    row, so re-describing is the only thing this collapses.
    """
    return (
        _contact_action_text(actor, 120).casefold(),
        _contact_action_text(contact_ref, 80).casefold(),
    )


def _clean_contact_action(raw, scene=None):
    if not isinstance(raw, dict) or not isinstance(scene, dict):
        return None
    actor = canonical_subject(
        scene, _contact_action_text(raw.get("actor"), 120))
    action = _contact_action_text(raw.get("action"), 120)
    raw_ref = raw.get("contact_id") or raw.get("contact_ref")
    ref, contact = resolve_contact_action_ref(scene, raw_ref)
    if not actor or not action or not ref or contact is None:
        return None
    if not (same_subject(scene, actor, contact.get("actor"))
            or same_subject(scene, actor, contact.get("target"))):
        return None
    key = _contact_action_key(actor, ref)
    action_id = "contact-action:" + hashlib.sha256(
        "\x1f".join(key).encode("utf-8")).hexdigest()[:20]
    return {
        "action_id": action_id,
        "actor": actor,
        "contact_id": ref,
        "action": action,
        "intensity": _contact_action_text(raw.get("intensity"), 60),
        "rhythm": _contact_action_text(
            raw.get("rhythm") or raw.get("cadence"), 80),
        # Author diagnostics only. Deterministic perception does not deliver
        # arbitrary prose from this field across the identity firewall.
        "detail": _contact_action_text(raw.get("detail"), 200),
    }


def _live_contact_actions(scene):
    """Clean existing records, drop any whose parent contact has ended, and
    collapse a saved stack of rewordings to the one current account.

    Cleaning re-derives every row's id from (actor, contact), so a ledger
    saved while identity still hashed the action text arrives here as
    several rows under ONE id. The later row is the current description, and
    it takes the earlier row's position so the ledger's order survives the
    heal -- which is what lets the measured triples (chats 86, 87, 88) fix
    themselves on the next read, with no migration.
    """
    out, at = [], {}
    for raw in (scene or {}).get("contact_actions") or []:
        if not isinstance(raw, dict):
            continue
        # Saved rows already carry a durable id; feed it through the same
        # resolver so an orphan cannot survive a move, scale change, or release.
        candidate = {**raw, "contact_ref": raw.get("contact_id")}
        cleaned = _clean_contact_action(candidate, scene)
        if cleaned is None:
            continue
        seen = at.get(cleaned["action_id"])
        if seen is None:
            at[cleaned["action_id"]] = len(out)
            out.append(cleaned)
        else:
            out[seen] = cleaned
    return out[-_MAX_CONTACT_ACTIONS:]


def contact_actions_of(scene, name):
    """Standing contact effects performed by one body, oldest first."""
    return [dict(record) for record in _live_contact_actions(scene)
            if same_subject(scene, record.get("actor"), name)]


def contact_action_ledger_index(scene) -> list[dict]:
    """The standing effect ledger, each row carrying the id ops address.

    The sibling of `substance_ledger_index` and for the same reason: the one
    hand entitled to `contact_action_ops` was never shown the effects it had
    already declared, so `change` and `remove` -- both of which its prompt
    documents -- had nothing to name, and a reworded add was the only move
    available to it. `detail` is left out because it is author diagnostics,
    not part of what an op can address.
    """
    return [{
        "action_id": row.get("action_id"),
        "actor": row.get("actor"),
        "contact_id": row.get("contact_id"),
        "action": row.get("action"),
        **({"intensity": row["intensity"]} if row.get("intensity") else {}),
        **({"rhythm": row["rhythm"]} if row.get("rhythm") else {}),
    } for row in _live_contact_actions(scene)]


def actions_for_contact(scene, contact_ref):
    """All standing effects attached to one durable contact id."""
    ref, _ = resolve_contact_action_ref(scene, contact_ref)
    return [dict(record) for record in _live_contact_actions(scene)
            if ref and record.get("contact_id") == ref]


def apply_contact_action_ops(scene, ops, report=None) -> dict:
    """Apply bounded effect ops, then enforce parent-contact ownership.

    Effects persist until explicitly removed or until their contact ends.
    Model silence never changes physical state.
    """
    scene = scene if isinstance(scene, dict) else {}
    rows = _live_contact_actions(scene)

    def rebuild_index():
        return {row.get("action_id"): i for i, row in enumerate(rows)
                if isinstance(row, dict) and row.get("action_id")}

    index = rebuild_index()
    for raw in (ops if isinstance(ops, list) else []):
        if not isinstance(raw, dict):
            continue
        op = _contact_action_text(raw.get("op"), 32).casefold()
        if op in {"add", "change"}:
            action_id = _contact_action_text(raw.get("action_id"), 80)
            at = index.get(action_id) if action_id else None
            candidate = raw
            if op == "change" and at is not None:
                # A stable action_id is enough to address a change; omitted
                # identity fields inherit from the standing record rather
                # than making the model repeat an opaque contact id.
                candidate = {**rows[at], **raw}
                candidate["contact_ref"] = (
                    raw.get("contact_ref") or raw.get("contact_id")
                    or rows[at].get("contact_id"))
            cleaned = _clean_contact_action(candidate, scene)
            if cleaned is None:
                if report:
                    report("discarded contact action without a live contact, "
                           "participant actor, and noun-like action")
                continue
            if at is None:
                at = index.get(cleaned["action_id"])
            if at is None:
                rows.append(cleaned)
            else:
                rows[at] = cleaned
            index = rebuild_index()
            continue

        action_id = _contact_action_text(raw.get("action_id"), 80)
        actor = canonical_subject(
            scene, _contact_action_text(raw.get("actor"), 120))
        action = _contact_action_text(raw.get("action"), 120).casefold()
        raw_ref = raw.get("contact_id") or raw.get("contact_ref")
        ref, _ = resolve_contact_action_ref(scene, raw_ref)
        if op not in {"remove", "clear"}:
            continue
        if raw_ref and not ref:
            if report:
                report("discarded contact-action removal with an unknown "
                       "contact reference")
            continue
        if not any((action_id, actor, ref)):
            if report:
                report("discarded unbounded contact-action removal")
            continue
        kept = []
        for row in rows:
            matches = True
            if action_id and row.get("action_id") != action_id:
                matches = False
            if actor and not same_subject(scene, row.get("actor"), actor):
                matches = False
            if ref and row.get("contact_id") != ref:
                matches = False
            if op == "remove" and action \
                    and row.get("action", "").casefold() != action:
                matches = False
            if not matches:
                kept.append(row)
        rows = kept
        index = rebuild_index()

    scene["contact_actions"] = _live_contact_actions(
        {**scene, "contact_actions": rows})[-_MAX_CONTACT_ACTIONS:]
    return scene


def contact_actions_for_observer(scene, observer):
    """Effects on contacts the observer is physically party to.

    Returns cleaned records only. The parent contact is deliberately not
    exposed to the renderer; ordinary contact perception already carries its
    endpoint-specific sensation and identity-safe partner label.
    """
    out = []
    for record in _live_contact_actions(scene):
        contact = _contact_by_id(scene, record.get("contact_id"))
        if contact is None:
            continue
        if (same_subject(scene, contact.get("actor"), observer)
                or same_subject(scene, contact.get("target"), observer)):
            out.append(dict(record))
    return out


def contact_action_clause(record, *, observer, scene=None, label_for=None):
    """Observer-safe tactile clause for one standing contact effect.

    `action` is required to be a noun-like physical effect ("vibration",
    "pressure pulses", "suction"), allowing fixed grammar in every genre.
    The recipient does not need a canonical name for the other party; the
    ordinary contact sensation already carries the recognition-safe identity.
    """
    if not isinstance(record, dict):
        return ""
    action = _contact_action_text(record.get("action"))
    if not action:
        return ""
    intensity = _contact_action_text(record.get("intensity"))
    rhythm = _contact_action_text(record.get("rhythm"))
    effect = " ".join(part for part in (intensity, action) if part)
    if rhythm:
        effect += f", {rhythm}"
    actor_is_observer = same_subject(
        scene or {}, record.get("actor"), observer)
    return (f"You sustain {effect} through the contact" if actor_is_observer
            else f"You feel {effect} through the contact")
