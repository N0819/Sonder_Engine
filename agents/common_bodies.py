"""What one observer can perceive of a body: attire views and exposure facts,
extra parts, per-region visibility, enclosure/containment spelling, the
perceptible-entity projection, and the micro-round delivery gate.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from story import attire as attire_model
from story.character_schema import (
    _extra_part_placement,
    character_extra_parts,
    character_name,
    normalized_character_of_row,
    persona_extra_parts,
    persona_name,
)
from core.db import get_setting
from story.scene import NON_AWAKE_GATED
from world.spatial import (
    _body_interior_holder,
    containment_conceals,
    detail_resolves_between,
    entity_arc,
    hear_level,
    hiding_holders_of,
    same_subject,
    sense_adjusted,
    sight_verdict,
    visual_level_between,
)

from agents.common_base import _ling

# Entity fields that exist so CODE can resolve a reference, not because an
# observer could perceive them. See _perceptible_entities.
_ENTITY_LOOKUP_ONLY_FIELDS = ("aliases",)


def _beneath_visible():
    """Whether what is under someone's clothing is spelled out at all.

    Off unless the host turns it on. What a card authors per region as
    `beneath` is explicit body description, and a default that starts
    narrating it the first time a coat comes off is not a default anyone
    chose. With this off the region still reports itself as bare -- the
    exposure is objective and the story needs it -- and the body's own
    appearance is what fills the rest, which is where it lived before regions
    existed.

    ONE ANSWER PER COMPOSED VIEW, NOT ONE PER BODY. This is a host setting --
    a SELECT on `settings` -- and it cannot differ between two bodies or two
    observers in the same view, so every function below that walks bodies
    resolves it once and passes it down (`beneath=`). Measured for review
    2026-09-07 C20: a scene of twelve bodies composed for six observers asked
    the database 84 times for the one answer.
    """
    return str(get_setting("attire_beneath") or "").strip().casefold() in (
        "1", "on", "true", "yes")


def attire_view(entry, body="", beneath=None):
    """One body's clothing as a stage should see it.

    The flat `wearing`/`state` pair stays, because that is the shape the
    Director writes back in `attire:{name:{add,remove,...}}`. Alongside it goes
    one line per region, which is the only representation that can say a robe
    is open rather than merely present -- and the only one that can say a
    region is bare while the body is still dressed.

    ``beneath`` is the host's `attire_beneath` answer when a caller walking
    several bodies already resolved it; None asks for it here (see
    `_beneath_visible`).
    """
    if not isinstance(entry, dict):
        return {}
    # Through `rederive_entry`, not straight off the stored dict. `wearing` and
    # `state` used to be passed through verbatim while only `regions` was
    # normalised, so this view could -- and did -- hand a character a coherent
    # region breakdown next to a flat list contradicting it. Live in chat 52:
    # the regions were clean and `wearing` still read
    # `[... 'corset', 'worn', 'skirt']`, with a phantom garment named after a
    # state, because every repair to the ledger's normalisation was bypassed
    # for exactly the two fields anyone reads first.
    #
    # A read path, so this presents the three representations agreeing without
    # writing anything back; commit still owns the stored shape.
    coherent = attire_model.rederive_entry(entry)
    regions = coherent.get("regions") or {}
    lines = attire_model.describe(
        regions,
        beneath_visible=_beneath_visible() if beneath is None else beneath,
        body=body)
    exposed = attire_model.exposed_regions(regions)
    partial = attire_model.partially_exposed_regions(regions)
    return {
        "wearing": coherent.get("wearing") or [],
        "state": coherent.get("state") or [],
        **({"regions": lines} if lines else {}),
        # Stated rather than left to be worked out from the lines above. What
        # a body shows is exactly this list -- a garment that is loosened or
        # hanging open is still ON, and a region nobody has mentioned is
        # unmodelled rather than bare, so neither appears here.
        **({"exposed": exposed} if exposed else {}),
        **({"partially_exposed": partial} if partial else {}),
    }


def attire_exposure_facts(sc, bodies):
    """Which regions the ledger still has COVERED, per body, for the screen.

    `bodies` is [(ledger_key, [ownership token, ...])] and the CALLER decides
    who is in it -- this function has no perception opinion, the same division
    `_position_delta_payload` keeps for rooms.

    A partially exposed region is left OUT: a garment worn open still counts
    as concealing, so prose calling that region bare is defensible and
    warning about it would spend a rewrite on a true sentence.
    """
    out, ledger = [], (sc or {}).get("attire") or {}
    for key, refs in bodies or ():
        # `entry_for`, not a bare `.get`: the caller passes whatever spelling
        # it holds, and a miss here means no covered region is reported --
        # the screen then stops objecting to a covered region narrated bare
        # (review 2026-09-07 B5).
        entry = attire_model.entry_for(ledger, key)
        refs = [str(r).strip() for r in (refs or ()) if str(r).strip()]
        if not entry or not refs:
            continue
        regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
        partial = set(attire_model.partially_exposed_regions(regions))
        covered = [r for r in attire_model.covered_regions(regions)
                   if r not in partial]
        if covered:
            out.append({"refs": refs, "covered": covered})
    return out


def exposure_owner_refs(narration_person, display, pronouns=None):
    """Every word in prose that would OWN this body's regions.

    The possessive that means "the player" is decided by narration person,
    not by the persona's pronouns, which is why the person table is language
    data beside the exposure vocabulary rather than a constant here.
    """
    shape = _ling("_EXPOSURE_STATE")
    refs = list((shape.get("person_possessive") or {}).get(
        str(narration_person or "").strip().lower()) or ())
    display = str(display or "").strip()
    if display:
        refs.append(display + "'s")
    poss = str((pronouns or {}).get("possessive") or "").strip()
    if poss:
        refs.append(poss)
    return refs


def scene_attire_view(sc):
    """`attire_view` across every body in the scene."""
    beneath = _beneath_visible()
    return {
        name: attire_view(entry, beneath=beneath)
        for name, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
    }


# How much of a garment's appearance rides in a payload. The Director is the
# only path by which what a thing looks like reaches prose, so it gets enough
# to describe with; a character looking at their own clothes gets the same,
# because a body knows what it is wearing.
ATTIRE_LOOK_CHARS = 60


def compact_attire(entry, look=ATTIRE_LOOK_CHARS, beneath=None):
    """One body's clothing as a single line -- see `attire.compact_line`.

    Replaces the multi-field `attire_view` in PAYLOADS only. Measured on chat
    67: the view sent to the Director was 3,789 chars, this is 1,314 -- 65%,
    ~618 tokens off every resolve call. `attire_view` itself stays as it is for
    panels and anything that wants the structured shape.

    Rederived rather than read raw, for the reason `attire_view` gives: the
    stored `wearing`/`state` pair and `regions` could disagree, and this must
    render the reconciled truth. It is also what migrates a LEGACY body -- a
    story whose attire predates regions entirely -- into regions on read, so
    an old chat needs no backfill to be rendered by this.

    ``beneath`` as in `attire_view`: the host answer, resolved once by a
    caller walking bodies.
    """
    if not isinstance(entry, dict):
        return ""
    regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
    return attire_model.compact_line(
        regions,
        beneath_visible=_beneath_visible() if beneath is None else beneath,
        look=look)


def scene_compact_attire(sc, look=ATTIRE_LOOK_CHARS):
    """`compact_attire` across every body in the scene."""
    beneath = _beneath_visible()
    return {
        name: compact_attire(entry, look=look, beneath=beneath)
        for name, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
    }


def extra_part_phrase(part):
    """One authored extra body part as a deterministic phrase.

    `tail — emerges from the back of the waist; passes through clothing;
    long and russet-furred`. Same input, same string, every beat: the parts
    are card configuration, so a body whose anatomy did not change renders
    byte-identically and a provider's prefix cache can absorb it.
    """
    part = part if isinstance(part, dict) else {}
    kind = " ".join(str(part.get("kind") or "").split())
    if not kind:
        return ""
    try:
        count = max(1, int(part.get("count", 1)))
    except (TypeError, ValueError):
        count = 1
    at = str(part.get("at") or "torso")
    aspect = str(part.get("aspect") or "back")
    if aspect == "sides":
        where = f"across both sides of the {at}"
    elif aspect in ("left", "right"):
        where = f"from the {aspect} side of the {at}"
    else:
        where = f"from the {aspect} of the {at}"
    head = kind if count == 1 else f"{kind} x{count}"
    bits = [f"emerges {where}" if count == 1 else f"emerge {where}"]
    if part.get("through_clothing", True):
        bits.append("passes through clothing worn there"
                    if count == 1 else "pass through clothing worn there")
    else:
        bits.append("worn beneath clothing there")
    description = " ".join(str(part.get("description") or "").split())
    if description:
        bits.append(description)
    return f"{head} — {'; '.join(bits)}"


def extra_parts_lines(parts):
    """Every declared part as its phrase; [] stays [] so defaults stay inert."""
    out = []
    for part in (parts or []):
        text = extra_part_phrase(part)
        if text:
            out.append(text)
    return out


def scene_extra_parts(cast, persona=None, player_name=None):
    """{display name: authored extra parts} for every body that has any.

    Read live from the cards (the acuity/lexicon pattern): no scene state, no
    per-beat maintenance, and a sheet edit fixes the body it describes. Only
    bodies with a non-empty declaration appear, so a cast with none produces
    {} and every payload key hanging off this stays absent.
    """
    out = {}
    for row in (cast or []):
        # The card only -- this reader never wanted the stored state -- and
        # memoised on its text, so the two reads below share one
        # normalization (C14). AN INTENDED WIDENING: `sheet_state` raised
        # `KeyError` on a row carrying a `sheet` but no `cstate`, and this
        # reads the parts off it instead. Both cast queries select `cstate`,
        # so no production row is in that shape; a row that has a card has
        # extra parts whether or not it has state.
        sh = normalized_character_of_row(row)
        if sh is None:
            continue
        parts = character_extra_parts(sh)
        if parts:
            out[character_name(sh)] = parts
    if persona is not None:
        parts = persona_extra_parts(persona)
        if parts:
            name = str(player_name or persona.get("name")
                       or persona_name(persona))
            out[name] = parts
    return out


def region_visibility(sc, observer, body, entry=None):
    """Which of one body's regions THIS observer can see, and what conceals
    the rest -- concealment, applied to bodies instead of acts.

    Returns every region in `attire.REGIONS`, in anatomical order, in the
    vocabulary concealed action already uses:

        {"torso": {"visibility": "concealed", "by": {"garments": ["kimono"]}},
         "hands": {"visibility": "overt"},
         ...}

    `by` is a one-key dict naming the KIND of concealer alongside the
    concealers themselves, and the kinds are exactly the three the engine can
    already answer for:

      - `garments` -- what `attire.concealing_garments` says still covers the
        region. A garment that only attaches never appears here: a hair clip
        is present without covering.
      - `containment` -- the body is shut inside something the observer is
        outside (or the observer is shut inside something themselves), read
        through `hiding_holders_of`/`containment_conceals` so the parented
        interior-room form conceals exactly as the `contained` ledger form
        does.
      - `vantage` -- the observer's own position is what fails: the body is in
        their rear arc (`entity_arc`, the `behind_sources` rule -- no NEW
        visual detail from a blind spot), or `visual_level_between` answers
        `none` for darkness or barriers, or `shapes` for a body still going
        through one (distance takes nothing one doorway away). At `shapes` a
        silhouette shows presence and outline, not what is worn or bare, so
        every region is concealed -- the same reading `_co_present_company`
        gives an unrecognised figure.

    DERIVED, NEVER STORED. `wearing`/`state`/`regions` are already three
    representations of one wardrobe and they drifted until `rederive_entry`
    existed; a stored per-region `visible` flag would be a fourth with the
    same failure mode and no new information. This is a pure read: the
    coverage half comes from the reconciled regions (which also migrates a
    legacy flat-list body on read), the observer half from the scene, and
    nothing is written anywhere.

    Per-observer on purpose -- the point of the transfer from `conceal_from`.
    Two observers of one body get different answers when one stands behind it,
    or outside the wardrobe it is hiding in. A body is never concealed from
    itself by containment or vantage (`same_subject`, not `==` -- a being
    routinely carries a display name and an entity id at once): a perceiver is
    never sealed from themselves and is never in their own blind spot. Their
    own garments still conceal their regions, because covered is covered.

    Safe-closed: an observer the scene cannot place sees nothing, which is the
    same answer every other spatial query gives for `unknown`.
    """
    sc = sc if isinstance(sc, dict) else {}
    if entry is None:
        # The ledger's own reader owns the key tolerance -- this was one of
        # four open-coded copies of it (review 2026-09-07 B5). Read back
        # through the key so a present-but-empty entry stays distinct from
        # an absent one, which is the distinction this `is None` turns on.
        ledger = sc.get("attire") or {}
        key = attire_model.key_for(ledger, body)
        entry = ledger.get(key) if key is not None else None
    regions = {}
    if isinstance(entry, dict):
        regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
    cover = attire_model.concealing_garments(regions)

    body_level = None
    if not same_subject(sc, observer, body):
        level = visual_level_between(sc, observer, body)
        if level != "full":
            # Attribution only: whether sight fails is spatial's composed
            # answer (light, barriers, containment, crossing grace), never
            # re-derived here where a second copy of that policy would drift.
            if containment_conceals(sc, observer, body):
                holders = (hiding_holders_of(sc, body)
                           or hiding_holders_of(sc, observer))
                body_level = {"containment":
                              [str(holders[0])] if holders else []}
            else:
                # Stated as "is there a visual channel at all" rather than
                # by naming one rung, so the sight ladder can grow without
                # this attribution silently inverting: when `_LIGHT_SIGHT`
                # gained `conduct` (PQ2, 2026-09-05) a body plainly seen
                # moving in a dim room would otherwise have been reported
                # "out of sight". Anything short of full hides the regions;
                # only `none` hides the body.
                body_level = {"vantage": ["out of sight" if level == "none"
                                          else "seen only in silhouette"]}
        elif entity_arc(sc, observer, body) == "rear":
            body_level = {"vantage": ["behind the observer"]}

    out = {}
    for region in attire_model.REGIONS:
        if body_level is not None:
            out[region] = {"visibility": "concealed", "by": dict(body_level)}
        elif region in cover:
            out[region] = {"visibility": "concealed",
                           "by": {"garments": list(cover[region])}}
        else:
            out[region] = {"visibility": "overt"}
    return out


def observer_body_regions(sc, observer, body_labels=None, extra_parts=None):
    """Observer-safe attire/body surfaces for a perception payload.

    ``body_labels`` maps canonical scene subjects to labels already safe for
    this observer (``you``, a recognized name, or an appearance-derived
    descriptor).  Canonical keys are never emitted.  Vantage/containment
    concealment removes a region entirely; garment concealment exposes only
    the garment surface, while an overt region may expose its authored
    ``beneath`` description when the host enabled that feature and a garment
    has actually been removed there.

    A SCALE GAP costs texture, never acquaintance: a body far off this
    observer's own scale keeps every region it would otherwise deliver, and
    each arrives without its authored detail (``detail_resolves_between``).

    ``extra_parts`` maps canonical subjects to their authored structured
    body parts (character_schema.character_extra_parts). A visible part rides
    the body's row as ``parts``, gated by the SAME region_visibility verdicts
    the surfaces use: a body-level concealment (vantage, containment,
    darkness) hides every part; garment concealment at the attachment region
    hides only a part authored as worn beneath the clothing, because the
    default part -- a tail through a skirt -- emerges through what covers its
    root. A body is never concealed from itself: the self row keeps all its
    own parts, tucked ones annotated, matching the self-knowledge floor.
    """
    sc = sc if isinstance(sc, dict) else {}
    labels = dict(body_labels or {str(observer): "you"})
    ledger = sc.get("attire") or {}
    parts_map = extra_parts if isinstance(extra_parts, dict) else {}
    # One host answer for the whole delivery, not one per body (C20).
    beneath = _beneath_visible()
    results = []
    for body, label in labels.items():
        folded = str(body or "").strip().casefold()
        # Key tolerance through the ledger's own reader (review 2026-09-07
        # B5); read back through the key so an authored-but-empty entry is
        # still an entry, as the `not isinstance(...)` below reads it.
        key = attire_model.key_for(ledger, body)
        entry = ledger.get(key) if key is not None else None
        parts = parts_map.get(body)
        if parts is None:
            # One being, one name: the map is keyed by display name and the
            # caller may hold another casing of it.
            parts = next((value for key, value in parts_map.items()
                          if str(key).strip().casefold() == folded), None)
        parts = [p for p in (parts or [])
                 if isinstance(p, dict) and p.get("kind")]
        if not isinstance(entry, dict) and not parts:
            continue
        coherent = (attire_model.rederive_entry(entry) or {}
                    if isinstance(entry, dict) else {})
        regions = coherent.get("regions") or {}
        surfaces = attire_model.perceptible_region_surfaces(
            regions, beneath_visible=beneath)
        visibility = region_visibility(
            sc, observer, body, entry=coherent if coherent else None)
        # The scale gap is a fact about the PAIR, not about a shoulder, so it
        # is asked once per body rather than once per region.
        resolves = detail_resolves_between(sc, observer, body)
        delivered = {}
        for region in attire_model.REGIONS:
            surface = surfaces.get(region)
            if not surface:
                continue
            verdict = visibility.get(region) or {}
            cause = verdict.get("by") or {}
            if verdict.get("visibility") == "concealed" \
                    and "garments" not in cause:
                continue
            # ACUITY IS PROPORTIONALITY. A region on a body far off this
            # observer's own scale delivers its form and not its texture --
            # the same subtraction dim light already makes, on the axis the
            # `scales` ledger measures. Measured: an observer received
            # "Barely visible copper-gold hair on her shins" and card tan-line
            # detail verbatim across a 4x gap, because nothing between the
            # ledger and the composed view ever read the ledger. It SUBTRACTS
            # only: the region still arrives, still says covered-or-bare,
            # still names the garment. `same_subject` is deliberately not
            # consulted -- a body's ratio to itself is 1.0, so the self row is
            # never coarsened by construction.
            delivered[region] = (
                surface if resolves
                else attire_model.coarsen_region_surface(surface))
        shown_parts = []
        shown_data = []
        self_view = same_subject(sc, observer, body)
        for part in parts:
            # A REGION THIS MAP KNOWS, or nothing is shown.
            #
            # `region_visibility` is keyed by attire.REGIONS. A part authored
            # on a CARD is coerced to those keys (character_schema's
            # `_extra_part_placement`), but a part minted by a
            # `physical_transformation` is model free text and nothing
            # normalised it -- so `at` arrived as "top of the head" and "back
            # of the waist". `.get()` missed, the empty verdict read as NOT
            # concealed, and the guard failed OPEN.
            #
            # Live, chat 76 turn 71: every one of the eight regions correctly
            # returned concealed/vantage "out of sight", and The Doctor still
            # received "Two fox ears emerge from ... Hinami's top of the head"
            # as a SIGHT percept through a closed bathroom door -- into his
            # view, his observations, and his character step's appraisal.
            #
            # Resolve through the same fallback the card path uses, then treat
            # an unresolvable placement as concealed. A guard on the firewall
            # must fail CLOSED: an unknown region is not evidence of exposure,
            # and a missing key must never read as permission.
            at = str(part.get("at") or "").strip().casefold()
            if at not in attire_model.REGIONS:
                at = _extra_part_placement(str(part.get("kind") or ""))[0]
            verdict = visibility.get(at)
            if verdict is None:
                continue
            cause = verdict.get("by") or {}
            concealed = verdict.get("visibility") == "concealed"
            if concealed and "garments" not in cause and not self_view:
                continue   # whole body unseen: vantage/containment/darkness
            tucked = (concealed and "garments" in cause
                      and not part.get("through_clothing", True))
            if tucked and not self_view:
                continue   # worn beneath the clothing that covers its root
            text = extra_part_phrase(part)
            if not text:
                continue
            if tucked:
                text += " [currently beneath clothing]"
            shown_parts.append(text)
            # The phrase is shaped for a payload a model would rewrite. The
            # composer renders straight to the reader, so it needs the parts
            # themselves -- same gating decision, carried structured. Kept
            # beside `parts` rather than replacing it: the phrase is what
            # the Director payloads and this module's own tests consume.
            shown_data.append({**part, "tucked": tucked})
        if delivered or shown_parts:
            row = {"body": str(label or "someone"), "regions": delivered}
            if shown_parts:
                row["parts"] = shown_parts
                row["part_data"] = shown_data
            results.append(row)
    return results


def _subject_spellings(sc, subject):
    """Every handle this scene keys one being by: the string as given, plus
    the entity id and the display name of the record it names.

    A being routinely carries the pair at once -- entity `tardis_001`, display
    name "Blue Police Box" -- and each of its ledgers is keyed by whichever
    handle its writer had. Aliases are deliberately NOT spellings here: they
    are lookup vocabulary, several beings may claim one, and this list decides
    a firewall answer.
    """
    text = str(subject or "").strip()
    if not text:
        return []
    forms = [text]
    seen = {text.casefold()}
    for eid, ent in ((sc or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        labels = (eid, ent.get("name"), *(ent.get("aliases") or []))
        if not any(str(label or "").strip().casefold() == text.casefold()
                   for label in labels):
            continue
        for handle in (eid, ent.get("name")):
            form = str(handle or "").strip()
            if form and form.casefold() not in seen:
                seen.add(form.casefold())
                forms.append(form)
        break
    return forms


def _enclosure_of(sc, subject):
    """The nearest enclosure around this being, under any name it is keyed by.

    The first spelling the scene knows an enclosure for wins. A spelling the
    scene does not key answers "nothing around it" -- which is the ignorant
    answer, indistinguishable from a body standing in the open -- and the
    informed answer must outrank it.
    """
    for form in _subject_spellings(sc, subject):
        holders = hiding_holders_of(sc, form)
        if holders:
            return str(holders[0]).strip()
    return ""


def _enclosure_conceals(sc, observer, target):
    """`spatial.containment_conceals`, asked under every live spelling.

    Sight and sound need both parties on the same side of every closed thing,
    which `containment_conceals` decides by comparing their nearest
    enclosures -- resolving each from the ONE string it was handed. One being
    routinely answers to two (a cast display name and a scene entity id), each
    ledger is keyed by whichever its writer had, and
    `spatial_identity.canonical_subject_map` deliberately declines to fold a
    lone entity-id key, so the pair stays live on purpose. Handed the spelling
    a scene does not key, the primitive reports a being with nothing shut
    around it, and every caller reads that as "in the open".

    So both parties are resolved across their spellings first, and the two
    enclosures are compared through `same_subject`, because the holder carries
    the pair too. Nothing is concealed from itself under either of its names.
    """
    if same_subject(sc, observer, target):
        return False
    around_observer = _enclosure_of(sc, observer)
    around_target = _enclosure_of(sc, target)
    if around_observer == around_target:
        return False
    return not same_subject(sc, around_observer, around_target)


def _perceptible_entities(sc, perceiver_names=None):
    """The entities dict to serialize into a PERCEPTION payload.

    Perception is handed the objective entity table so it can describe what
    is present -- but an entity carries two kinds of string. Its `name` and
    `description` are what an observer standing there could actually take
    in. Its `aliases` and its dict KEY are lookup handles, written for
    commit.track_background_presences and background._name_to_entity_id to
    match against, and an observer has no way to acquire that vocabulary.

    Handing both to the model let the vocabulary leak. Observed live
    (Elevator Adventure branch 41, turn 91): entity `tardis_001`, display
    name "Blue Police Box", aliases ["tardis", "box", "police box"]. Dr.
    Moon's own view came back "The TARDIS looms behind her, still wheezing
    as its temporal engines wind down" -- a word she has never heard, in
    the same sentence where the man himself was correctly anonymized as
    "the lean energetic man" (identities are scrubbed by
    _scrub_unknown_identities; object vocabulary was not).

    So the lookup handles do not go in: entities are keyed by display name
    where that is unambiguous, and aliases are dropped. A character who
    legitimately knows what the thing is knows it from their own sheet and
    memory -- which is where that knowledge belongs.

    `state` is the SECOND thing this table carries that an observer may have
    no channel to. The Director writes it as objective fact, in act-naming
    language -- `state.posture` and `state.proximity` spell out what a body
    is doing and where it is doing it. Observed live: a body shut inside a
    container had its every act written out in `state` while no perceiver in
    the call had any sight of it at all. That is the same shape as the alias
    leak above -- objective state handed over with an implicit instruction
    not to use it -- and the same argument applies: when NOBODY in this call
    can perceive the entity, none of them has a legitimate use for what it is
    doing, so it does not go in.

    `perceiver_names` is who the payload is being built for. Concealment is
    decided by containment only: an entity in the open is unaffected, so this
    is inert for the ordinary scene and bites exactly on the enclosed case
    that motivated it. The entity still appears -- only `state` is withheld --
    because presence may reach the perceiver through contact or sound even
    when nothing else does. Omitted (the default) keeps the whole table, which
    is right for callers that have no perceiver set to gate against.

    Concealment goes through `_enclosure_conceals`, which asks both parties
    under every spelling they are keyed by: the record's `name` and its dict
    key are routinely two live handles for one being, and a gate that resolves
    only one of them failed OPEN here for an id-keyed enclosed entity (its
    act-naming `state` shipped to every perceiver) and CLOSED for an id-keyed
    co-occupant (denied what the body beside it was doing).
    """
    entities = (sc or {}).get("entities") or {}
    if not isinstance(entities, dict):
        return entities

    names = [str(n).strip() for n in (perceiver_names or []) if str(n or "").strip()]
    _inhabited_by_a_perceiver = {
        holder for holder in (_body_interior_holder(sc, n) for n in names)
        if holder
    }

    def _state_reaches_anyone(*ent_spellings):
        spellings = [s for s in (str(f or "").strip() for f in ent_spellings)
                     if s]
        if not names or not spellings:
            return True
        return any(
            all(not _enclosure_conceals(sc, observer, form)
                for form in spellings)
            for observer in names
        )

    by_name = {}
    for eid, ent in entities.items():
        if isinstance(ent, dict):
            name = str(ent.get("name") or "").strip()
            if name:
                by_name.setdefault(name.casefold(), []).append(eid)

    projected = {}
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            projected[eid] = ent
            continue
        name = str(ent.get("name") or "").strip()
        # Keep the id when the name is missing or shared, so two entities
        # never collapse into one payload entry.
        key = name if name and len(by_name.get(name.casefold(), ())) == 1 \
            else eid
        drop = set(_ENTITY_LOOKUP_ONLY_FIELDS)
        if not _state_reaches_anyone(name, eid):
            drop.add("state")
        if eid in _inhabited_by_a_perceiver:
            # YOU CANNOT SEE THE OUTSIDE OF WHAT YOU ARE STANDING INSIDE.
            # `description` is an entity's EXTERIOR -- what a body in the room
            # around it takes in. Handed to its own occupant it reads as a
            # thing across the way. Live (chat 58, t38): the player stood in
            # the TARDIS console room and her view had "a blue police box --
            # its paint darkened by rain -- settles with a heavy thud on the
            # cobbles", which is the box she was standing in, landing, seen
            # from inside itself.
            #
            # The entity itself STAYS -- the room's own `parent_entity`
            # already tells the reader what they are inside, and presence is
            # not the leak. Only the outward appearance goes. (`state` is
            # separately withheld here by the containment gate above, which
            # predates this and is not changed by it.)
            drop.add("description")
        projected[key] = {k: v for k, v in ent.items() if k not in drop}
    return projected

def _delivery_ok(relation, scene, observer_name, source_name, channel,
                 volume="normal", proximity=None, behind_sources=None,
                 awareness=None, senses=None, level_db=None, addressed=None):
    """Can this observer receive this source through this channel?

    Cross-seam pattern 3: the deterministic delivery paths each grew their own
    partial gate, so every one of them skipped a rule the perception model path
    honours -- the micro-loop skipped containment and graded sight, the outcome
    action backstop skipped the rear arc, the background channel skipped
    station.

    THIS GATE IS NOT UNIVERSAL, and this docstring used to say it was ("the one
    predicate all of them call, so a rule added here reaches every
    deterministic delivery site at once"). Measured for review finding B35
    (2026-09-07): its only production callers are the two micro-round
    deliveries in `agents/loops.py`. `agents/perception.py`,
    `agents/composer.py` and `agents/background.py` answer the same questions
    from the same primitives without routing through here (`hear_level`,
    `_in_plain_view`/`_sight_detail`, `containment_conceals`,
    `sense_adjusted`), so a rule added HERE reaches the micro-round path and
    nothing else -- add it to that family in the same commit, or it holds on
    one of the two delivery paths only. Two families exist and can drift apart:
    that is the structural risk registered as `docs/UNBUILT.md` 3.8, which is
    the entry to close, and AGENTS.md's delivery-gate row says the same.
    `tests/test_delivery_gate_not_universal.py` measures the caller set rather
    than trusting this paragraph.

    `relation` is the caller's own `spatial_rel` result (built from ROOM ids,
    which only the caller can resolve uid/alias-tolerantly). Everything else is
    derived here:

    - **awareness** -- a non-awake mind receives nothing.
    - **containment** -- a sealed enclosure blocks sight AND sound, in both
      directions (`containment_conceals` is symmetric).
    - **hearing** -- `hear_level` including the `proximity` downgrade, so a
      muttered aside does not carry to an arbitrarily large room. A pitched
      line passes the `level_db` its addressee's cell solved, as the
      composer's hearing does (`hear_level(..., level_db=...)`). A line
      breathed into an ear reaches only its addressee: `addressed` says
      this observer is that body, and its default delivers it to nobody
      (`spatial_senses.EAR_VOLUME`).
    - **sight/action** -- `has_visual` plus the rear-arc blind spot. An action
      is visible or it is nothing.
    - **senses** (optional) -- the observer's card senses (G4). When passed,
      the channel grade is shifted by `spatial.sense_adjusted`; None or an
      ordinary card is byte-identical to before. NOTE for callers: with an
      extraordinary-hearing card this can answer True at hearing level
      `trace`, which is DETECTION ONLY -- re-grade with sense_adjusted before
      rendering, and never deliver words or identity on a trace.
    """
    if awareness is not None and awareness in NON_AWAKE_GATED:
        return False
    # `same_subject`, not `==`, for `region_visibility`'s reason 1,800 lines
    # above: a being routinely carries a display name and an entity id at
    # once, and a bare comparison between the two answers "these are two
    # people". Here that denies a mind its OWN percept rather than handing it
    # somebody else's -- and the case where it matters most is a body sealed
    # inside something, which is concealed from every subject in the scene,
    # itself included, once the self-exemption has failed to recognise it.
    if same_subject(scene, observer_name, source_name):
        return True
    # `_enclosure_conceals`, not the bare primitive, for the same reason the
    # line above is not `==`: containment is resolved from the strings this
    # caller happened to use, and a body keyed by entity id read as a body
    # standing in the open -- so a sealed body was delivered, on every
    # channel, to everyone around whatever held it.
    if _enclosure_conceals(scene, observer_name, source_name):
        return False

    if channel == "hearing":
        # `addressed`: whether the line was spoken TO this observer -- in a
        # din a bystander beyond conversational reach catches a far table's
        # talk in pieces (`hear_level`); None, unknown, caps nothing.
        level = hear_level(relation, volume, proximity=proximity,
                           level_db=level_db, addressed=addressed)
        if senses is not None:
            level = sense_adjusted(level, "hearing", senses)
        return level != "none"

    if behind_sources and source_name in behind_sources:
        return False
    if entity_arc(scene, observer_name, source_name) == "rear":
        return False
    # `sight_verdict` is the grade the LIGHT allowed plus what the place did
    # to it (A87), in one derivation: passing both is what lets an authored
    # sight that does not need light answer here -- the dark lifts for that
    # perceiver, while a wall and a shut container do exactly what they do
    # to an eye. For an ordinary card this reads the same as
    # `sight_level(relation)` always did.
    level, block = sight_verdict(relation)
    level = sense_adjusted(level, "sight", senses, blocked_by=block)
    return level != "none"
