# stimulation.py
"""What the WORLD says about physical stimulation of a body, for the drive.

`comfort.py` is this module's sibling and its opposite. Comfort is a resolved,
self-limiting pleasure LEVEL -- what a body is verifiably against -- and it is
forbidden from reaching `charge` at all, because integrating it would
manufacture saturated bodies out of sitting quietly. This module answers the
question comfort is not allowed to: how much of the sustained DRIVE the
physical facts of this beat can support.

THE PROBLEM IT EXISTS FOR. `resolve_hedonic` accumulates `charge` from
`somatic_impact.pleasure`, and the only gate on that number is that its `why`
is a non-empty string -- any sentence licenses any magnitude. Measured live
(chat 95, 2026-08-29): a character sat at `pleasure 1.0, charge 1.0,
saturated: true` with a `why` that was mostly social ("explicit verbal
approval layered on top of physical surrender") while the contact ledger held
four `settled` contacts -- a hand on a hip, weight pressing. At her observed
cadence the integral's equilibrium was 3.25 against a clamp of 1.0, so she was
not drifting up to the ceiling, she was welded to it by beat four and could
never come down.

THE RULE. Arousal from anything -- words, sight, anticipation, being held --
raises the drive, and none of it can saturate a body on its own. Each rung is
a CEILING on accumulation, and the last stretch to `_CHARGE_SATURATION` sits
above every rung a contact can reach: it is earned in beats of continued
active stimulation, never granted by a touch. Being touched and being
overwhelmed are different states and the ledger already distinguishes them.

WHAT IT READS, and nothing else: `scene.contacts` (parts, `relation`,
`motion`), `scene.attire` for whether a garment is between, and the body's own
authored responsive regions. No prose, and NO VOCABULARY -- there is no
manner word list here and there must never be one. `manner` and `detail` are
free text a model rewrites every beat, and this repo's oldest recurring defect
is a literal guard matching a string rather than the state it stands for. The
one intensity signal taken from words is the appraisal's own magnitude, which
`resolve_hedonic` applies as a RATE within a range this module already had to
grant -- so an over-eager 1.0 buys speed, never reach.

Responsive regions are AUTHORED, per body, on
`embodiment.interoception.responsive_regions`. A hardcoded anatomy list is
forbidden for the reason `spatial_contacts.canonical_region` gives for
refusing a body-part synonym table -- `tail_spade` is a nameable place on a
tail, not `tail` blurred -- and it would silently be wrong for every
non-human body the engine is built to carry. The engine's default when a card
says nothing is `groin` alone: `attire.REGIONS` already splits it from
`waist` as the private region, for unrelated reasons, so the distinction is
structural rather than a vocabulary this module invented.
"""

from __future__ import annotations

from story import attire as attire_model
from world.spatial import canonical_region, contacts_of, contact_endpoint_is_body

#: What the four rungs cap `charge` at. Above the top rung is
#: `psychology_runtime._CHARGE_SATURATION` (0.85), which no contact reaches:
#: the gap is what continued active stimulation climbs.
TIER_NONE = 1        # no contact with another body -- words, sight, anticipation
TIER_INDIRECT = 2    # contact, but through clothing or not on a responsive region
TIER_DIRECT = 3      # skin on a responsive region, settled
TIER_ACTIVE = 4      # skin on a responsive region, moving

#: The engine's answer when a card authored none. See the module docstring for
#: why this is one region and not a list of anatomy.
DEFAULT_RESPONSIVE_REGIONS = ("groin",)

#: An interior contact is a structural intensity floor rather than a word: the
#: contact record carries `relation` and has always distinguished the two.
_INTERIOR_FLOOR = 0.8

#: Simultaneous distinct responsive regions under active contact. Three points
#: is not one point, and it is a count rather than a judgment. The floor it
#: buys is capped so breadth cannot stand in for intensity by itself.
_BREADTH_FLOOR_PER_REGION = 0.25
_BREADTH_FLOOR_CAP = 0.75


def responsive_regions(interoception) -> tuple:
    """The regions this body answers to, from its own card.

    An entry may be an `attire.REGIONS` name, which the clothing ledger can
    report covered or bare, or a part in the story's own words ("clit",
    "spade", "gill") that only the contact ledger will ever name. Both are
    honoured: the region entries get the coverage test, and a free part
    counts as skin when the body is wearing nothing at all, which is the one
    case the wardrobe can answer without knowing where the part sits. The
    alternative -- folding a part onto a region -- is the body-part synonym
    table `spatial_contacts.canonical_region` refuses, for the reason it
    gives there.
    """
    raw = (interoception or {}).get("responsive_regions") \
        if isinstance(interoception, dict) else None
    if isinstance(raw, str):
        raw = [raw]
    out = []
    for item in (raw or []):
        name = str(item or "").strip().casefold()
        if name and name not in out:
            out.append(name)
    return tuple(out) if out else DEFAULT_RESPONSIVE_REGIONS


def _body_is_unclothed(scene, name) -> bool:
    """Does this body have no garment on it at all?

    The clothing question is only ever "is anything between", and for a body
    the story has undressed completely the answer is no, everywhere, without
    needing to know which region a part belongs to.
    """
    attire = scene.get("attire") if isinstance(scene, dict) else None
    entry = attire_model.entry_for(attire, name) if isinstance(attire, dict) else None
    if not isinstance(entry, dict):
        return True
    regions = attire_model.normalize_regions(entry)
    return not any((r or {}).get("garments") for r in regions.values())


def _region_is_bare(scene, name, region):
    """Is this region of this body skin, rather than under a garment?

    Silence is treated as BARE only when the body has no attire entry at all
    -- a body the story never dressed. A dressed body with nothing recorded
    for the region reads as covered, because the failure direction that
    matters here is granting reach the fiction did not establish.
    """
    attire = scene.get("attire") if isinstance(scene, dict) else None
    entry = attire_model.entry_for(attire, name) if isinstance(attire, dict) else None
    if not isinstance(entry, dict):
        return True
    regions = attire_model.normalize_regions(entry)
    return not attire_model.region_is_covered(regions, region)


def stimulation_of(scene, name, interoception=None) -> dict:
    """This beat's physical facts about one body, for the drive ceiling.

    Returns ``{"tier", "active", "intensity_floor", "regions"}``. `tier` is
    one of the four rungs above; `active` says whether this beat counts toward
    the continuity ratio `resolve_hedonic` keeps; `intensity_floor` is what
    the structure vouches for regardless of what the appraisal claimed.

    Only contact where the body is the one RECEIVING is read. A hand of hers
    on somebody else's hip is stimulation of that body, not of hers -- the
    contact ledger stores one record for the pair, and reading it from both
    ends would let a character overwhelm herself by touching someone.
    """
    if not isinstance(scene, dict) or not str(name or "").strip():
        return {"tier": TIER_NONE, "active": False,
                "intensity_floor": 0.0, "regions": []}
    wanted = responsive_regions(interoception)
    folded = str(name).strip().casefold()
    nude = _body_is_unclothed(scene, name)

    tier = TIER_NONE
    floor = 0.0
    active_regions = []
    for contact in contacts_of(scene, name) or []:
        if not isinstance(contact, dict):
            continue
        # Which end of this record is the body in question, and therefore
        # which part is BEING touched.
        if str(contact.get("target") or "").strip().casefold() == folded:
            part, other = contact.get("target_part"), contact.get("actor")
        elif str(contact.get("actor") or "").strip().casefold() == folded:
            part, other = contact.get("actor_part"), contact.get("target")
        else:
            continue
        # A body, not a bench. Furniture is comfort's department, and comfort
        # is forbidden from reaching the drive at all.
        if not contact_endpoint_is_body(scene, other):
            continue
        tier = max(tier, TIER_INDIRECT)
        moving = str(contact.get("motion") or "").strip().casefold() == "moving"
        interior = str(contact.get("relation") or "").strip().casefold() == "interior"
        enclosing = str(contact.get("target_interior") or "") if interior else ""
        # INSIDE IS NOT THE SAME QUESTION AS SENSITIVE. `relation: interior`
        # says nothing is between two surfaces, which settles the CLOTHING
        # question and only that one. It does not say the site answers to
        # being touched, and reading it as though it did made every cavity
        # equivalent: a body swallowed into a stomach, a finger in a mouth and
        # a body taken into a vulva would all have saturated the same. The
        # ledger's own words for those three are "stomach", "mouth" and
        # "vagina" (chat 95 t45 carries the last two verbatim), and telling
        # them apart is exactly the body-part table this module and
        # `spatial_contacts.canonical_region` both refuse.
        #
        # So an interior contact skips the wardrobe and nothing else. WHICH
        # site answers is a fact about that body, and the body says: the
        # responsive set below, authored per character. For an interior
        # contact the enclosing passage is part of the answer, since that is
        # the surface doing the receiving.
        # THE HAND THAT NAMED THE PARTS SAYS WHETHER THEY ANSWER. `erogenous`
        # is the contact specialist's judgment about THIS body, made where the
        # anatomy is actually known, and it is what lets a stomach and a vulva
        # be told apart without a table of words. The card's authored set below
        # still counts, so an author who wants the answer fixed can fix it;
        # either saying yes is yes.
        declared = bool(contact.get("erogenous"))
        candidates = [canonical_region(part) or str(part or "").strip().casefold()]
        if interior and enclosing:
            candidates.append(canonical_region(enclosing)
                              or enclosing.strip().casefold())
        region = ""
        for candidate in candidates:
            if not candidate:
                continue
            region = candidate if candidate in wanted else next(
                (w for w in wanted if w and w in candidate), "")
            if region:
                break
        if not region and not declared:
            continue
        if not interior and not declared:
            if region in attire_model.REGIONS:
                # A body wearing nothing has nothing between, so the wardrobe
                # has nothing to contradict an empty one.
                if not nude and not _region_is_bare(scene, name, region):
                    continue
            elif not nude:
                # An authored part the clothing ledger cannot place: skin only
                # while the body is bare everywhere, since nothing can say
                # whether a garment covers a region it has no name for.
                continue
        tier = max(tier, TIER_ACTIVE if moving else TIER_DIRECT)
        if moving:
            region = region or canonical_region(part) or "site"
            if region not in active_regions:
                active_regions.append(region)
            if interior:
                floor = max(floor, _INTERIOR_FLOOR)
    if active_regions:
        floor = max(floor, min(_BREADTH_FLOOR_CAP,
                               _BREADTH_FLOOR_PER_REGION * len(active_regions)))
    return {
        "tier": tier,
        "active": tier >= TIER_ACTIVE,
        "intensity_floor": round(floor, 4),
        "regions": active_regions,
    }
