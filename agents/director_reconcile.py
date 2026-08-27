"""Resolve-seam support that makes no model call.

Player-claim coverage findings, verdict settling and acquittal
(`_verify_already_true`, `_acquit_addressed_events`), repair routing by
channel owner (`_route_repair_omissions`), the deep-audit mode switch and
dialogue articulation stamping. The seam itself -- `_reconcile_resolution`
and its block comment, plus the model-calling `_deep_audit_omissions` and
`_specialist_repairs` -- stays in `agents/director.py`.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

import copy

from story import attire as attire_model
from core.db import get_setting
from world.spatial import (
    ARTICULATION_STIFLED,
    _clean_containment,
    apply_contact_ops,
    apply_substance_ops,
    clamp_scale,
    containment_hides,
    derive_containment_from_contacts,
    scale_of,
    size_relation,
    size_tier,
    speech_articulation_impediment,
)

from .common import _dict, _dict_list
from .director_evidence import (
    _claim_subject_in_world,
    _claim_subject_is_referrable,
    _make_subject_hit,
    _normalize_omission_category,
    _omission_subject_encoded,
    _subject_match_forms,
)
from .director_scopes import (
    SPECIALISTS,
    _CATEGORY_CHANNELS,
    _CHANNEL_SPECIALISTS,
)

def _deep_audit_mode():
    """The default-off standalone resolve_reconcile audit: 'off' (default),
    'always' (every physical beat -- the pre-manifest behavior, kept as a
    belt-and-suspenders option), or 'tripwire' (only when the silent-false-
    negative tripwire fires)."""
    value = str(get_setting("resolve_deep_audit") or "").strip().casefold()
    if value in ("1", "always", "on", "true"):
        return "always"
    if value == "tripwire":
        return "tripwire"
    return "off"

def _player_claim_findings(out, sd, interp, cast, sc, player_input=""):
    """Tier 0 player-authority coverage: every asserted scope='effect'
    authority claim with a resolvable subject must be encoded SOMEWHERE in
    the diff (shallow containment -- the claim's free-text predicate cannot
    be mapped to one category deterministically). Returns (omissions,
    notes, contract_warnings): null-subject claims become metadata notes
    only; an asserted claim the resolve marked rejected/failed is a player-
    authority contract violation surfaced as a deterministic warning."""
    omissions, notes, contract_warnings = [], [], []
    claims = _dict_list(_dict(interp.get("flow")).get("authority_claims"))
    if not claims:
        return omissions, notes, contract_warnings

    statuses = {}
    for d in _dict_list(out.get("claim_dispositions")) + \
            _dict_list(sd.get("claim_dispositions")):
        cid = str(d.get("claim_id") or "")
        if cid:
            statuses[cid] = str(d.get("status") or "").strip().casefold()

    for claim in claims:
        if str(claim.get("scope") or "") != "effect":
            continue  # contestable intents are the director's to resolve
        status = statuses.get(str(claim.get("claim_id") or ""), "")
        if status in ("rejected", "failed"):
            contract_warnings.append(
                "PLAYER AUTHORITY: asserted claim "
                f"{claim.get('claim_id')!r} ({claim.get('predicate')!r} on "
                f"{claim.get('subject_id')!r}) was marked {status!r} -- "
                "asserted effects occur as declared and may not be rejected."
            )
        subject = str(claim.get("subject_id") or "").strip()
        if not subject:
            notes.append({
                "claim_id": claim.get("claim_id"),
                "predicate": claim.get("predicate"),
                "note": "no resolvable subject; coverage not checkable",
            })
            continue
        forms = _subject_match_forms(subject, cast, sc)
        # A SUBJECT NOBODY CAN POINT AT is the null-subject case wearing a
        # word, and it has to degrade the same way -- because a player claim
        # is NON-REJECTABLE, so an unsatisfiable one warns every beat
        # forever and buys the full-core repair every beat forever.
        #
        # Live, chat 72 turn 45: the player added an aside addressed to the
        # ENGINE -- "(it is a hotel. even at late hour someone should be
        # staffing it, use logic and reasoning instead of assuming no one is
        # there)" -- and interpret minted two asserted completed effects on a
        # subject called `narrative_assertion`, split at a comma. Neither
        # could ever be encoded, so they bought the most expensive retry the
        # engine has and warned anyway; the repair answered 'already_encoded'
        # for both and non-rejectability correctly refused to hear it.
        #
        # Two channels qualify a subject and only failing BOTH disqualifies:
        #   * the WORLD knows it -- `_subject_match_forms` found cast keys or
        #     entity aliases beyond the bare string, or it names a room;
        #   * the PLAYER SAID IT -- the words are in their own input, which
        #     is what makes "I shatter the vault door" a real claim about a
        #     door no scene contains yet. Asserting a thing into existence is
        #     precisely what player authority is for.
        # Folded to words so punctuation and case cannot decide it.
        if not _claim_subject_is_referrable(subject, forms, sc, player_input):
            notes.append({
                "claim_id": claim.get("claim_id"),
                "predicate": claim.get("predicate"),
                "note": ("subject names nothing in the world and nothing the "
                         "player typed; coverage not checkable"),
            })
            continue
        if not _omission_subject_encoded(sd, subject, forms):
            omissions.append({
                "category": "other", "subject": subject,
                "change": (f"player-asserted completed effect "
                           f"{str(claim.get('predicate') or '')!r} on "
                           f"{subject}"),
                "evidence": str(claim.get("source_text") or ""),
                "source": "player_claim", "_forms": forms,
            })
    return omissions, notes, contract_warnings

def _public_omission(omission):
    return {k: v for k, v in omission.items() if not k.startswith("_")}


def _stamp_dialogue_articulation(sc, sd, dialogue_log):
    """Stamp each line with how it was FORMED; notice the impossible ones.

    Articulation is a property of the utterance at the moment it is produced
    -- the sibling of `volume`, which nobody considers a rewrite -- so it is
    stamped HERE, where the post-op ledger and the log meet, and rendered
    identically for every listener downstream. It is deliberately not a
    hearing level: a wall degrades sound in transit, differently per
    listener; an engaged tongue malforms the sound at the source, the same
    for everyone in the room, and a listener close by hears the slur BETTER,
    not less of it.

    The stamp is authoritative in both directions -- it sets and it CLEARS --
    so a model-invented value never survives and the field always reflects
    the ledger. The quotes themselves are never touched: `exact_quote` stays
    verbatim (the reconciliation contract), and the fidelity scrubs keep
    matching it.

    Notices go out only for the STIFLED kind at spoken volume: a full
    sentence with a filled mouth remains a fiction problem the Director
    should resolve (end the contact, or a word or two at 'mutter'), while a
    slurred line is now simply rendered as what it is. Checked against the
    POST-op ledger so a beat that ends the contact before the line is not
    scolded for it.
    """
    preview = dict(sc or {})
    preview["contacts"] = copy.deepcopy((sc or {}).get("contacts") or [])
    apply_contact_ops(preview, (sd or {}).get("contact_ops") or [])
    # The substance ledger needs the same treatment: a material affordance
    # established this beat is not in
    # `sc` yet, but it MUST be visible to the impediment check or the gate
    # silently clears as soon as the model names the matter aloud.  Mirror
    # contact_ops exactly so the stamp reads the post-op scene the same way
    # the merge will.
    preview["substances"] = copy.deepcopy((sc or {}).get("substances") or [])
    apply_substance_ops(preview, (sd or {}).get("substance_ops") or [])
    notices, noticed = [], set()
    impediments = {}
    for entry in dialogue_log or []:
        if not isinstance(entry, dict):
            continue
        speaker = str(entry.get("speaker") or "").strip()
        if not speaker:
            continue
        key = speaker.casefold()
        if key not in impediments:
            impediments[key] = speech_articulation_impediment(
                preview, speaker)
        kind, reason = impediments[key]
        entry["articulation"] = kind
        volume = str(entry.get("volume") or "normal").strip().casefold()
        if kind == ARTICULATION_STIFLED and key not in noticed \
                and volume in ("normal", "loud", "shout"):
            noticed.add(key)
            # The remedy is op-shaped: a contact that ends the block, or a
            # bounded substance op that ends or changes its explicit speech
            # affordance. The 'mutter' escape hatch is unchanged.
            notices.append(
                f"speech: {speaker} spoke at volume '{volume}' while "
                f"{reason}. Either end that contact in contact_ops, or update "
                "the blocking material state in substance_ops, before the "
                "line -- or keep the line to a word or two at volume "
                "'mutter' -- muffled against what blocks it.")
    return notices


def _scale_relation_conflicts(sc, sd):
    """Magnitudes that contradict the relations committed beside them.

    ONE DIFF, TWO HANDS: `scales` and `containment` are the contact
    specialist's channels, `poses`/`positions` the spatial one's, and no
    specialist ever sees the merged result -- so one beat can commit a body
    at a magnitude that its own enclosure relation rules out, and nothing
    objects. The orchestrator judges the MERGED diff, which is where this
    belongs.

    THE RULE, in the vocabulary the engine already has: an enclosure that
    HIDES a body (`containment_hides` -- the modes where the holder's own
    body or clothing closes around it, as against the five open carries)
    asserts that the holder can enclose it, and the engine's only
    enclosure-scale predicate is `size_relation`'s
    `other_fits_in_actors_hand`, whose boundary IS the `tiny` tier. A
    committed scale that denies it contradicts the relation committed in the
    same beat.

    DETECTION ONLY, and deliberately. It rewrites no number and drops no
    relation: the relation is corroborated by the prose channels and the
    number is not, so subtracting the relation would delete the witnesses to
    satisfy the suspect, and inventing a ratio that fits would be the engine
    fabricating objective state from a heuristic -- which it does nowhere
    else. `derive_containment_from_contacts` records the same lesson from
    the same measured beats (chat 86 t45-t50, `scales {"Hinami": 0.25}`
    beside prose calling her three inches, ~0.05): "a threshold read off a
    wrong number is a wrong answer with a confident shape". So the number
    stays the Director's to correct, with the contradiction named to it.

    Gated on the enclosed body carrying a NON-BASELINE scale, because this
    is a check on a COMMITTED MAGNITUDE: a scene where nobody's size is in
    play produces nothing, and an object held or pocketed at baseline --
    where a ratio between two different baselines means nothing -- never
    reaches the predicate. Gated again on this beat having written one half
    of the pair, so a contradiction the engine cannot fix warns while it is
    being made, not once per beat forever. Fail open: an exception anywhere
    returns no conflicts.
    """
    try:
        scales = dict((sc or {}).get("scales") or {})
        for name, raw in ((sd or {}).get("scales") or {}).items():
            label = str(name or "").strip()
            if label:
                # `clamp_scale(None)` is the merge's own "back to normal".
                scales[label] = clamp_scale(raw) or 1.0
        preview = {
            "scales": scales,
            "contained": dict((sc or {}).get("contained") or {}),
            "contacts": copy.deepcopy((sc or {}).get("contacts") or []),
        }
        incoming = (sd or {}).get("containment")
        if isinstance(incoming, dict):
            for subject, raw in incoming.items():
                label = str(subject or "").strip()
                if not label:
                    continue
                record = _clean_containment(raw, label) if raw else None
                if record is None:
                    for key in [k for k in preview["contained"]
                                if str(k).strip().casefold()
                                == label.casefold()]:
                        preview["contained"].pop(key, None)
                else:
                    preview["contained"][label] = record
        # The enclosure is as often expressed ONLY as an interior contact op
        # -- the merge derives the record from it, so the check has to read
        # the same derivation rather than a channel the beat left empty.
        apply_contact_ops(preview, (sd or {}).get("contact_ops") or [])
        touched = {str(k).strip().casefold() for k in
                   list((sd or {}).get("scales") or {})
                   + list((sd or {}).get("containment") or {})}
        for op in (sd or {}).get("contact_ops") or []:
            if isinstance(op, dict):
                touched |= {str(op.get("actor") or "").strip().casefold(),
                            str(op.get("target") or "").strip().casefold()}
        touched |= {str(n).strip().casefold()
                    for n in derive_containment_from_contacts(preview)}
        conflicts = []
        for subject, record in (preview.get("contained") or {}).items():
            if not isinstance(record, dict):
                continue
            holder = str(record.get("in") or "").strip()
            mode = str(record.get("mode") or "carried")
            if not holder or not containment_hides(mode):
                continue  # carried in the open says nothing about size
            if str(subject).strip().casefold() not in touched \
                    and holder.casefold() not in touched:
                continue  # this beat wrote neither half of the pair
            factor = scale_of(preview, subject)
            if factor == 1.0:
                continue  # no magnitude claimed, so none can conflict
            if size_relation(preview, holder, subject).get(
                    "other_fits_in_actors_hand"):
                continue
            conflicts.append(
                f"size: {subject} is committed as {mode!r} by {holder} -- an "
                "enclosure only a body small enough to be closed a hand "
                f"around can be inside -- while state_diff.scales puts "
                f"{subject} at {factor:g} of baseline, size tier "
                f"{size_tier(factor)!r}. The relation and the number cannot "
                "both be true, and the relation is the one the prose "
                "corroborates: if the size the prose gives is the real one, "
                "write THAT ratio into state_diff.scales.")
        return conflicts
    except Exception:
        return []


#: Verdicts that settle an event without a second call. `not_mine` is
#: deliberately absent: a specialist saying the change needs a channel it
#: was not granted is REPORTING A GAP, not closing one, and that gap is
#: exactly what the repair tier exists for.
_SETTLING_VERDICTS = frozenset({"encoded", "already_true"})


#: The verdict a repair returns for a player-asserted effect whose subject
#: is not a thing the world model can hold. Its own status rather than a
#: shade of `rejected`, because the two say different things: `rejected`
#: denies that the change happened, which the player authority contract
#: forbids for an asserted effect, while this accepts the effect and reports
#: that there is nothing structured to encode it AS.
_NO_REFERENT = "no_referent"


def _verify_no_referent(om, forms, sc):
    """Is `no_referent` an admissible answer for this player-claim omission?

    THE CLASS: player authority makes an asserted EFFECT true; it does not
    make that effect's grammatical subject an object. A column of numbers, a
    patch of light, a rhythm, a span of time -- each is the real subject of a
    real sentence, and none of them has a durable record, a position or a
    room. The repair sheet used to forbid the only correct answer for those
    ("never 'rejected'"), so the only permitted answer was to encode -- and
    encoding a subject with no structured home means MINTING IT AS A SCENE
    ENTITY. Measured over the audited 15-beat run: that is where the minted
    entities came from.

    Bounded exactly the way `_verify_already_true` is, and for the same
    reason -- a model verdict is evidence, never authority. Admissible only
    where the WORLD does not already know the subject. A subject that names a
    cast member, a scene entity or a room IS a thing, and the refusal is
    inadmissible there: the non-rejectability warning stands, unchanged.

    The referrability gate upstream lets a subject through on either of two
    channels, and only one of them is proof of thinghood: what the world
    holds a record for. The other -- the player typed the word -- is
    satisfied by every noun in a narrated sentence, so it qualifies a subject
    for COVERAGE CHECKING and settles nothing about what the subject is.
    That asymmetry is the whole of this function.
    """
    return not _claim_subject_in_world(om.get("subject"), forms, sc)


def _verify_already_true(om, sc):
    """Deterministic standing-state check behind an `already_true` verdict.

    Returns (ok, reason). ok=False means the acquittal is REFUSED: standing
    state provably cannot carry ANY definite fact about this subject in this
    category, so a specialist's "the change is already the standing state"
    is resting on a ledger that does not support definite claims -- the
    chat 70/71 corruption exactly (a garment marked `removed` while still
    resident in three regions), where a specialist reading the ledger could
    honestly answer `already_true` about a change standing state did NOT
    properly carry.

    WHAT THIS DELIBERATELY IS NOT: a proof that the change is already true.
    The manifest's structure carries no DIRECTION -- whether the change puts
    the garment on or takes it off, starts the contact or ends it, lives
    only in the `change` prose, and prose matching is the boundary this
    whole design exists to get away from (both end states are legitimate
    no-op targets, so an undirected presence check is vacuous). So this is
    a defect detector, scoped to what is deterministically decidable:

    - attire: a subject-hit garment resident in a wearer's regions with
      state 'removed' (removed means GONE -- `release_removed_garments` is
      the canonical repair), or wearing/regions membership drift for a hit
      garment when both representations are populated (`rederive_entry`'s
      fork case). An incoherent wardrobe supports no definite claim.
    - positions/stations: a subject-hit standing position whose value is
      not a room in the scene -- the category error every spatial query
      answers as `unknown`, which looks exactly like distance.
    - inventory: a subject-hit body tracked in `contained` while carrying
      its OWN positions entry that disagrees with its holder's -- a carried
      body's position is derived from its carrier's, so two answers is a
      corrupt ledger.
    - contacts, conditions: no refusal is decidable (a relation ledger
      cannot be incoherent about presence; either end state is a legitimate
      no-op) -- trusted, now deliberately rather than by omission.

    Anything this cannot decide returns ok=True and the acquittal proceeds
    exactly as before. Fail open: an exception anywhere reads as ok=True.
    """
    try:
        category = _normalize_omission_category(om.get("category"))
        hits = _make_subject_hit(om.get("subject"),
                                 list(om.get("_forms") or [])
                                 + [om.get("target")])

        if category == "attire":
            for wearer, entry in (sc.get("attire") or {}).items():
                if not isinstance(entry, dict):
                    continue
                wearer_hit = hits(wearer)
                wearing = [str(n) for n in (entry.get("wearing") or [])
                           if str(n or "").strip()]
                resident = []      # (name, state) seated in regions
                for region_entry in (entry.get("regions") or {}).values():
                    if not isinstance(region_entry, dict):
                        continue
                    for garment in region_entry.get("garments") or []:
                        if isinstance(garment, dict) \
                                and str(garment.get("name") or "").strip():
                            resident.append(
                                (str(garment.get("name")),
                                 str(garment.get("state") or "")))
                for name, state in resident:
                    if state.casefold() == "removed" \
                            and (wearer_hit or hits(name)):
                        return False, (
                            f"standing attire for {wearer!r} still seats "
                            f"{name!r} in regions marked 'removed' -- "
                            "removed means gone from the body "
                            "(attire.release_removed_garments is the "
                            "canonical repair)")
                if wearing and resident:
                    for name, state in resident:
                        if state.casefold() == "removed":
                            continue
                        if (wearer_hit or hits(name)) \
                                and attire_model.resolve_garment(
                                    name, wearing) is None:
                            return False, (
                                f"standing attire for {wearer!r} seats "
                                f"{name!r} in regions but not in wearing "
                                "-- the representations disagree")
                    region_names = [n for n, s in resident
                                    if s.casefold() != "removed"]
                    for name in wearing:
                        if (wearer_hit or hits(name)) \
                                and attire_model.resolve_garment(
                                    name, region_names) is None:
                            return False, (
                                f"standing attire for {wearer!r} lists "
                                f"{name!r} in wearing but seats it in no "
                                "region -- the representations disagree")
            return True, None

        if category in ("positions", "stations"):
            rooms = sc.get("rooms") or {}
            for key, value in (sc.get("positions") or {}).items():
                if hits(key) and str(value or "") \
                        and str(value) not in rooms:
                    return False, (
                        f"standing position for {key!r} is {value!r}, "
                        "which is not a room in the scene -- a category "
                        "error every spatial query answers as unknown")
            return True, None

        if category == "inventory":
            contained = sc.get("contained") or {}
            positions = sc.get("positions") or {}
            for key, record in contained.items():
                if not hits(key):
                    continue
                holder = record.get("in") if isinstance(record, dict) \
                    else record
                own = positions.get(key)
                holder_pos = positions.get(str(holder or ""))
                if own and holder_pos and str(own) != str(holder_pos):
                    return False, (
                        f"{key!r} is contained by {holder!r} yet carries "
                        f"its own position {own!r} against the holder's "
                        f"{holder_pos!r} -- a carried body's position is "
                        "derived from its carrier's")
            return True, None

        return True, None
    except Exception:
        return True, None


def _acquit_addressed_events(out, omissions, sc=None):
    """Split detected omissions into (owed a repair, acquitted, refused).

    An omission is acquitted when it carries an event_id that the specialist
    OWNING that event answered with a settling verdict this beat. Ownership
    is implicit and cannot be forged: an id only reaches the index through
    the specialist that was handed it, by the same category filter that
    built its payload, and only if that call actually ran.

    An `already_true` verdict is additionally checked against standing
    state (`_verify_already_true`): a ledger that provably cannot carry any
    definite fact about the subject earns no acquittal, and the refusal is
    returned as a named defect -- the omission stays owed, so the repair
    tier still sees the gap.

    Everything without an event_id -- signals, player claims, deep-audit
    findings, and every omission on the monolithic path, where no specialist
    ran and the index is empty -- falls through unchanged. That is what
    keeps the monolithic repair path byte-identical.
    """
    record = out.get("orchestration")
    index = (record or {}).get("events_addressed") or {}
    if not isinstance(index, dict) or not index:
        return omissions, [], []
    owed, acquitted, refused = [], [], []
    for om in omissions:
        entry = index.get(om.get("event_id")) or index.get(
            str(om.get("event_id")))
        status = (entry or {}).get("status")
        if entry and status in _SETTLING_VERDICTS:
            if status == "already_true":
                ok, reason = _verify_already_true(om, sc or {})
                if not ok:
                    refused.append({
                        "event_id": om.get("event_id"),
                        "category": om.get("category"),
                        "subject": om.get("subject"),
                        "owner": entry.get("owner"),
                        "reason": reason,
                    })
                    owed.append(om)
                    continue
            acquitted.append({
                "event_id": om.get("event_id"),
                "category": om.get("category"),
                "subject": om.get("subject"),
                "owner": entry.get("owner"),
                "status": status,
            })
        else:
            owed.append(om)
    return owed, acquitted, refused


#: Sentinel channel for a REROUTED omission: the hand that declined the
#: event named the owner but not which of its channels fits -- only the
#: owner knows that -- so it repairs with its full granted scope.
_REROUTE_FULL_SCOPE = "*"


def _route_repair_omissions(omissions, addressed=None):
    """Partition detected omissions by REPAIRER, for the orchestrated path.

    Returns (routed, core): `routed` maps specialist name -> [(channel,
    omission), ...] for every omission whose category names a delegated
    channel -- that channel's owner is who should be asked again, with its
    own 1-4k sheet, not the prose author with the full core. `core` keeps
    everything only a whole-diff authority can answer: player claims (their
    coverage check is whole-diff and they are non-rejectable), and
    categories no specialist owns (time, transit, 'other').
    """
    routed, core = {}, []
    index = addressed or {}
    for om in omissions:
        if om.get("source") == "player_claim":
            core.append(om)
            continue
        # A FORWARDING NOTE BEATS THE CATEGORY MAP. The hand that was given
        # this event declined it AND named the hand it belongs to, in a
        # structured field. Routing by category here would re-ask the hand
        # that just said no -- measured live, where contact and objects both
        # explained in prose that a posture change was not theirs while the
        # category kept sending it back. The address is a PROPOSAL, checked
        # against the roster before it is acted on: an unknown name, or a
        # hand that already had this event, falls back to the category.
        entry = index.get(om.get("event_id")) or index.get(
            str(om.get("event_id")))
        target = str((entry or {}).get("reroute_to") or "").strip()
        if (target in SPECIALISTS and target != (entry or {}).get("owner")
                and om.get("event_id")):
            routed.setdefault(target, []).append((_REROUTE_FULL_SCOPE, om))
            continue
        channel = _CATEGORY_CHANNELS.get(
            _normalize_omission_category(om.get("category")))
        owner = _CHANNEL_SPECIALISTS.get(channel) if channel else None
        if owner:
            routed.setdefault(owner, []).append((channel, om))
        else:
            core.append(om)
    return routed, core
