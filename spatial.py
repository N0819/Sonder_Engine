# spatial.py
"""Spatial reasoning with entity-aware scene merging and containment validation."""

import copy
import hashlib
import re
from collections import defaultdict
from typing import Optional

from schemas import NON_ENTITY_FIELD_KEYS, is_derived_entity_name
from spatial_orientation import (
    _LEFT_SECTORS,
    _REL_SECTORS,
    _RIGHT_SECTORS,
    lateral_of,
    normalize_bearing,
    normalize_scene_bearings,
    normalize_vertical,
    opposite_bearing,
    opposite_vertical,
    relative_bearing,
    travel_bearing,
)


from spatial_identity import (
    _ci_get, _entity_named, _live_subject_spellings, _position_of,
    _SUBJECT_KEYED, canonical_subject, canonical_subject_map,
    is_derived_room_name, normalize_room_id, normalize_scene_subjects,
    room_of, same_subject,
)


from spatial_barriers import (
    _AMBIENT_BARRIERS, _barrier_against_its_own_name, _BARRIER_ALIASES,
    _BARRIER_CLOSED_FORM, _BARRIER_CLOSED_QUALIFIERS, _barrier_exact,
    _BARRIER_OPEN_FORM, _BARRIER_OPEN_QUALIFIERS, _BARRIER_SEAL_QUALIFIERS,
    _BARRIER_SEALED_FORM, _OPENING_WORDS, _PASSABLE_BARRIERS, _SCENT_BARRIERS,
    _SIGHT_BARRIERS, _VALID_BARRIERS, normalize_barrier,
    normalize_scene_barriers, unresolved_barrier_words,
)


from spatial_transit import (
    _closed_enclosure_barrier, _entity_exterior_room, _is_body_entity,
    _link_state, _open_enclosure_barrier, _TRANSIT_CLOSED_PHASES,
    _transit_state, ambient_scope, apply_transit_dock_edges,
    CONTAINER_ENCLOSURES, containment_chain, infer_body_enclosures,
)


from spatial_containment import (
    _body_interior_holder, _clean_containment, _hiding_holders,
    _innermost_hiding_holder, _MAX_CONTAINED, _MAX_SCALE, _MAX_SCALES,
    _MIN_SCALE, _NEVER_STATIONED_KINDS, _OPEN_CONTAINMENT_MODES,
    _SCALE_CONTACT_BREAK, _scale_phrase, _shares_enclosure, _SIZE_TIERS,
    carrier_chain, clamp_scale, container_of,
    containment_broken_by_scale_change, containment_conceals,
    containment_facts, containment_hides, CONTAINMENT_MODES, contents_of,
    derive_contained_positions, hiding_holders_of,
    normalize_scene_containment, normalize_scene_scales, scale_of,
    scale_ratio, size_facts, size_relation, size_tier,
    would_create_containment_cycle,
)


from spatial_contacts import (
    _CAVITY_GRIP_MANNERS, _clean_contact, _contact_key,
    _CONTACT_MOMENTARY_STALE_BEATS, _contact_motion_from_text,
    _contact_ops_are_evidence, _CONTACT_RESIDUE_VERB, _CONTACT_STALE_BEATS,
    _CONTACT_STATE_VERBS, _contact_text, _contained_inversion, _displaces,
    _ENCLOSING_PART_CAVITY, _ENVELOPMENT_MANNERS, _flip,
    _INTERIOR_MOVING_MANNERS, _is_anatomical_part, _LATERAL_QUALIFIERS,
    _MAX_CONTACT_DETAIL, _MAX_CONTACT_PART, _MAX_CONTACTS, _mirror_key,
    _MOMENTARY_SET, _NON_ANATOMICAL_PART_WORDS, _normalize_contact_motion,
    _normalize_contact_relation, _part_identity, _part_is_plural,
    _same_appendage, _same_region, _SENSATION_FORMS, _SINGULAR_S_PARTS,
    _STRICT_CAVITY_KINDS, apply_contact_ops, canonical_region,
    CONTACT_INTERIOR_MANNERS, contact_is_momentary, contact_manner_kind,
    CONTACT_MANNERS, CONTACT_MOMENTARY_MANNERS, contact_motion,
    CONTACT_MOVING_MANNERS, contact_relation, contacts_broken_by_scale_change,
    contacts_of, normalize_scene_contacts, owned_region, same_owned_region,
)


from spatial_contact_migration import (
    _CONTACT_KEY_MANNERS, _CONTACT_PROXIMITIES, _DIRECTION_AFTER_VERB,
    _drop_contradicted_state, _lift_valued_contact, _manner_from_fragment,
    _part_from_key, _PROTECTED_STATE_KEYS, _RELATIONAL_STATE_SUFFIXES,
    contacts_from_entity_state,
)


from spatial_substance import (
    _absorb_into_pool, _interior_destination_for_release, _record_region,
    _resolved_substance_add, _same_pool, _SPEECH_CAVITY_INTERIORS,
    _SPEECH_MOUTH_KINDS, _stock_consumed_by, _substance_id,
    _substance_placement, _SUBSTANCE_PLACEMENTS, _substance_target_exists,
    _substance_text, apply_substance_ops, ARTICULATION_SLURRED,
    ARTICULATION_STIFLED, resolve_substance_ops,
    speech_articulation_impediment, substance_event_clause, substances_for,
)


from spatial_geometry import (
    _anchor_dir, _anchor_for_entity, _BARRIER_ANCHOR_DESC, _clean_pose,
    _DOOR_ANCHOR_PREFIX, _occupancy, _POSE_FIELDS, _REAR_SECTORS,
    _relative_sector, _ROOM_SIZE_HINT_WORDS, _sector_label, _station,
    anchor_bearing_of, apply_pose_diff, crossing_of, derive_scene_stations,
    door_anchor_id, effective_anchors, effective_facing, effective_room_size,
    effective_station, egocentric_frame, entity_arc, entity_side,
    guessed_room_sizes, measured_proximity_rel, normalize_scene_poses,
    normalize_scene_stations, pose_facts, proximity_rel, room_layout,
    spatial_digest, THRESHOLD_CROSSING_BEATS,
)


from spatial_light import (
    _brighter, _LIGHT_ALIASES, _LIGHT_ORDER, _light_radius, _LIGHT_SIGHT,
    effective_light, light_at, light_blocks_sight, LIGHT_LEVELS,
    normalize_light, room_light, SIGHT_LEVELS, source_light,
)


from spatial_routing import (
    _CORRIDOR_NAMED, _CORRIDOR_VAGUENESS, _DISTANCE_ALIASES,
    _DISTANCE_UNIT_METERS, _is_carried_interior, _onward_exits, _reverse_dir,
    _ROOM_COST, CORRIDOR_SIGHT_LIMIT, corridor_sightlines, DISTANCE_TIERS,
    nearby_rooms, normalize_edge_distance, passable_neighbors, passable_path,
    passable_route_exists, passable_route_next_step, rooms_adjacent,
    spatial_rel, SPRINT_BUDGET, sprint_reach, visible_adjacent_rooms,
)


from spatial_senses import (
    _ACUITY_ABSENT, _ACUITY_MINUS_ONE, _ACUITY_PLUS_ONE, _ACUITY_PLUS_TWO,
    _clean_comms_channel, _comms_carrier_room, _comms_delivers,
    _comms_transmits, _COMPASS_WORDS, _edge_vertical,
    _material_shifted_barrier, _MATERIAL_SOUND_STEPS, _measured_intimacy,
    _opening_view_cap, _phrase_table, _RANGE_EXTENDED, _RANGE_REDUCED,
    _sector_phrases, _SECTOR_PHRASES, _SECTOR_STEPS, _sense_channel,
    _SENSE_CHANNEL_ALIASES, _SENSE_LADDERS, _sight_line, _SIGHT_ORDER,
    _sound_barrier_phrases, _SOUND_BARRIER_PHRASES, _SOUND_LADDER,
    _SOUND_WALK_BARRIERS, _weaker_sight, apply_comms_ops, can_perceive,
    can_perceive_onset, comms_between, comms_link, COMMS_MODES, comms_reach,
    crossing_visible_from, has_visual, hear_level, HEARING_LEVELS,
    is_alarming, normalize_scene_comms, scent_level, SCENT_LEVELS,
    sense_acuity_offset, sense_adjusted, sense_entry, sense_range_class,
    sight_level, sound_bearing, sound_path, sound_walk_level,
    spatial_rel_between, visual_level_between,
)


def repair_entity_positions(scene: dict) -> list:
    """A position naming an ENTITY rather than a room is a category error.

    `positions` maps a body to a ROOM. The Director periodically writes an
    entity id there instead -- "she is in Elyndra" is a true sentence and an
    invalid position -- and nothing rejected it, because every spatial query
    resolves an unknown room to the safe-closed default rather than raising.

    Measured live (chat 60): a body enclosed inside another sat at the literal
    string `"elyndra_succubus"` for the rest of the story, a room that does not
    exist. The relation to the body around her came back

        {"same_room": false, "barrier": "separated", "distance": "far"}

    -- the same answer the engine gave for a window across the room. Nothing
    was broken loudly. She was simply nowhere, and every channel read as
    distance, which is exactly what being nowhere looks like from inside a
    ranking function.

    The repair is the reading the Director meant: put the body in the entity's
    own room and record a station AT that entity, which is the engine's
    existing vocabulary for being at a thing rather than in it. Containment is
    NOT inferred here -- `derive_contained_positions` has already run and owns
    that case, and inventing an enclosure from a mistyped position would turn a
    typo into a firewall change. Returns what it repaired, for warnings.
    """
    positions = scene.get("positions")
    rooms = scene.get("rooms") or {}
    if not isinstance(positions, dict) or not isinstance(rooms, dict):
        return []
    repaired = []
    for name, where in list(positions.items()):
        key = str(where or "").strip()
        if not key or key in rooms or _ci_get(rooms, key) is not None:
            continue
        entity = _entity_named(scene, key)
        if not entity:
            continue
        room = _position_of(scene, key)
        if room is None or room == key:
            continue
        positions[name] = room
        stations = scene.setdefault("stations", {})
        if isinstance(stations, dict):
            slot = stations.get(name)
            if not isinstance(slot, dict):
                slot = {"at": None, "near": []}
                stations[name] = slot
            if not slot.get("at"):
                slot["at"] = key
        repaired.append((name, key, room))
    return repaired


def prune_bodiless_positions(scene: dict) -> list:
    """Drop `positions` entries belonging to a bodiless voice.

    A ship's computer, a station PA and a public-address system are not
    standing anywhere -- `scene.is_ubiquitous_entity` calls giving one a room
    a category error, and the Director prompt tells it to declare such a thing
    with NO position. It still happens: measured live, one was created with a
    room in the same breath as a description reading "a voice-activated system
    with no physical body", trailed the player for five beats, and was then
    stranded in the room it was last voiced in for eighty more.

    A stale entry like that is not inert. Every reader that asks where the
    speaker is gets an answer, and the answer is wrong -- the delivery rescue
    in perception is the one that matters, and it is now asked of the entity
    rather than of the position, but nothing was removing the record itself
    and there is no way for an author to. So merge hygiene removes it, the
    same way position changes prune an impossible contact.

    Returns the names dropped, for the caller to report; mutates in place.
    """
    positions = scene.get("positions")
    entities = scene.get("entities")
    if not isinstance(positions, dict) or not isinstance(entities, dict):
        return []
    try:  # lazy: scene.py imports THIS module, so the edge only goes one way
        from scene import ubiquitous_speaker_names
        bodiless = ubiquitous_speaker_names(scene)
    except Exception:
        return []
    if not bodiless:
        return []
    dropped = [key for key in list(positions)
               if str(key).strip().casefold() in bodiless]
    for key in dropped:
        positions.pop(key, None)
    return dropped


def contact_phrase(contact: dict, *, subject_first=True, you=None) -> str:
    """One STANDING contact as a plain clause -- state, never event.

    'Bramwell's hand grips Hinami's waist'. Every consumer of this phrase
    (narrator ground truth via `spatial_facts`, the perception scene payload)
    is asking what is true right now, so a manner naming an ACT renders as the
    touch that act left behind: a contact recorded `kiss` reads "X's lips is
    against Y's forehead", not "X's lips kiss Y's forehead". The act itself is
    delivered from the beat's declared sequence, which is the representation
    that carries WHEN it happened.

    Measured live, before this: a forehead kiss from four beats earlier was
    still rendered in the active present into a perceiver's view, and the
    character answered it as a live advance.

    `you` names the observer this phrase is FOR, when there is one. Their side
    renders in the second person ("your palm presses against her sternum"),
    because handing a perceiver a third-person clause about their own body --
    naming them canonically, in a view that must be written as "you" -- is the
    same objective-state-into-a-subjective-context pattern the engine forbids
    everywhere else, and it invites exactly the person drift it sounds like.
    """
    if not isinstance(contact, dict):
        return ""
    actor = str(contact.get("actor") or "").strip()
    target = str(contact.get("target") or "").strip()
    if not actor or not target:
        return ""
    manner = str(contact.get("manner") or "touch").strip() or "touch"
    actor_part = str(contact.get("actor_part") or "").strip()
    target_part = str(contact.get("target_part") or "").strip()
    target_interior = str(contact.get("target_interior") or "").strip()

    observer = str(you or "").strip().casefold()
    actor_is_you = bool(observer) and actor.casefold() == observer
    target_is_you = bool(observer) and target.casefold() == observer

    def _side(who, part, is_you):
        if is_you:
            return f"your {part}" if part else "you"
        return f"{who}'s {part}" if part else who

    left = _side(actor, actor_part, actor_is_you)
    right = _side(target, target_part, target_is_you)
    relation_kind = contact_relation(contact)
    motion_kind = contact_motion(contact)
    if relation_kind == "interior":
        # Interior topology says the ACTOR PART is within the TARGET. The
        # target_part is the precise endpoint/contact site, not necessarily the
        # structure doing the enclosing. Treating it as the container turned a
        # blade at a shoulder into "inside the shoulder" and a contact at a
        # terminal boundary into "inside the boundary".
        if target_interior:
            container = (f"your {target_interior}" if target_is_you else
                         f"{target}'s {target_interior}")
        else:
            container = "you" if target_is_you else target
        plural = _part_is_plural(actor_part) if actor_part else actor_is_you
        verb = ("move" if plural else "moves") if motion_kind == "moving" \
            else ("remain" if plural else "remains")
        phrase = f"{left} {verb} within {container}"
        if target_part:
            endpoint = f"your {target_part}" if target_is_you \
                else f"{target}'s {target_part}"
            phrase += f", maintaining contact at {endpoint}"
        detail = str(contact.get("detail") or "").strip()
        return f"{phrase}, {detail}" if detail else phrase
    if not subject_first:
        return f"{right} is under {left} ({manner})"
    # "You" always takes the plural verb form ("you are", "you hold"), and a
    # bare name the singular; with a part, the part decides.
    plural = _part_is_plural(actor_part) if actor_part else actor_is_you
    if manner in _MOMENTARY_SET:
        verb = _CONTACT_RESIDUE_VERB[plural]
    elif manner in _CONTACT_STATE_VERBS:
        verb = _CONTACT_STATE_VERBS[manner][plural]
    else:
        # Outside both vocabularies the fiction is on its own: inflect only
        # when the model has not already done it ("throttles" must not become
        # "throttleses"), and never for a plural subject.
        verb = manner if (plural or manner.endswith("s")) else f"{manner}s"
    detail = str(contact.get("detail") or "").strip()
    return f"{left} {verb} {right}, {detail}" if detail else f"{left} {verb} {right}"


def contact_sensation(contact: dict, *, you: str, scene: dict = None,
                      label_for=None) -> str:
    """What one STANDING contact continuously delivers to ONE party's body.

    `label_for` is the identity floor (AGENTS.md: every payload that hands a
    mind prose somebody else wrote needs one): a callable mapping the OTHER
    party's canonical name to what THIS observer may call them. Without it,
    this clause named the other body canonically and the composer tripwire
    fired on every contact beat with an unrecognized partner (measured live,
    chat 70: `unearned identity ['Elyra Voss'] reached the composed view` —
    the scrub held the line; the floor belongs here at the source). Absent,
    the canonical name passes through unchanged, for callers rendering an
    omniscient or self-only view.

    `contact_phrase` renders a contact as an objective third-party fact -- who
    is touching whom, where. That is what a narrator needs and it is not what
    the touching party FEELS, so a perceiver in sustained contact received a
    diagram of the contact and no sensation from it.

    The gap this closes: the perception contract specified the tactile channel
    only as a SUBSTITUTE for sight -- every mandatory clause was conditioned on
    sight being absent (in the dark, behind a wall, sealed inside something).
    With both parties in a lit room and in continuous contact, the channel is
    wide open and nothing required a word of it, so under a token budget the
    view rendered what was seen and dropped what was felt. Measured across the
    corpus before this: 46.8% of all observations classified as `mixed`
    because no sensory cue matched them at all, and `interoception` accounted
    for 2.4%.

    A standing contact is neither an event nor inert state. It is a CONTINUOUS
    PERCEPT: true every beat and felt every beat, until it ends. This renders
    that percept, in the second person, from the named party's side, in plain
    physical terms -- pressure, movement, friction, warmth -- and says nothing
    about what the other body is doing internally, which no contact carries.

    Returns "" when the named party is not a party to the contact: a bystander
    watching two other people touch feels nothing, and this must never be the
    thing that tells them otherwise.
    """
    if not isinstance(contact, dict):
        return ""
    actor = str(contact.get("actor") or "").strip()
    target = str(contact.get("target") or "").strip()
    observer = str(you or "").strip()
    if not actor or not target or not observer:
        return ""
    # Through `same_subject`, never `==`: one being routinely carries a cast
    # display name and a scene entity id at once, and a contact recorded under
    # one spelling against a perceiver named by the other would silently match
    # nobody -- leaving the party to a contact feeling nothing from it.
    def _is_observer(name):
        if scene is not None:
            return same_subject(scene, name, observer)
        return str(name or "").strip().casefold() == observer.casefold()

    actor_is_observer = _is_observer(actor)
    if actor_is_observer:
        mine, theirs = contact.get("actor_part"), contact.get("target_part")
        other = target
    elif _is_observer(target):
        mine, theirs = contact.get("target_part"), contact.get("actor_part")
        other = actor
    else:
        return ""
    if callable(label_for):
        other = str(label_for(other) or other)

    # A slot holding an act, a sound or a state is a malformed record, not a
    # body. Say nothing rather than render a sensation nobody could have.
    if not (_is_anatomical_part(mine) and _is_anatomical_part(theirs)):
        return ""

    relation_kind = contact_relation(contact)
    motion_kind = contact_motion(contact)
    if relation_kind != "interior" and contact_is_momentary(contact):
        # A momentary manner names the ACT that made the touch, and the act's
        # own `motion` field says how the act moved -- a kiss is recorded
        # `moving`. The standing record outlives the act, so rendering that
        # stored motion delivered "movement and friction" for a kiss four
        # beats gone (measured: a head-kiss from turn 42 was still felt as a
        # live, moving kiss at turn 47, while its owner held a conversation).
        # What a momentary SURFACE contact continuously delivers is its
        # RESIDUE -- lips resting where the kiss landed -- exactly as
        # `contact_phrase` already renders it; the act itself reaches
        # perceivers through the beat's declared sequence, the representation
        # that carries WHEN. An INTERIOR contact is different: its enclosure
        # persists by definition, so `moving` there describes standing
        # kinematics (a blade working in a wound, a thrust not yet stilled),
        # not the echo of a finished act.
        motion_kind = "settled"
    if relation_kind == "interior":
        # `actor` is the party whose part goes in; the TARGET encloses it.
        # `target_part` names the endpoint/contact site. It does not mean that
        # endpoint is itself a cavity, so interior rendering must keep the
        # target entity and endpoint as two separate facts.
        side = "entering" if actor_is_observer else "enclosing"
        tail = "continuous while it stays there"
    else:
        side, tail = "either", "continuous while the contact holds"
    mine = str(mine or "").strip().replace("_", " ")
    theirs = str(theirs or "").strip().replace("_", " ")
    target_interior = str(
        contact.get("target_interior") or "").strip().replace("_", " ")
    if relation_kind == "interior":
        if motion_kind == "moving":
            quality = ("changing pressure, heat and friction along its length"
                       if side == "entering" else
                       "fullness, stretch, shifting pressure and movement")
        else:
            quality = ("pressure, heat and movement along its length"
                       if side == "entering" else
                       "pressure, fullness and movement")
        if side == "entering":
            site = f"your {mine}" if mine else "your body"
            plural = _part_is_plural(mine) if mine else False
            verb = "register" if plural else "registers"
            pronoun = "them" if plural else "it"
            enclosure = (f"{other}'s {target_interior}"
                         if target_interior else other)
            relation = f"{enclosure} enclosing {pronoun}"
            if theirs:
                relation += f", with contact at {other}'s {theirs}"
        else:
            site = "your body"
            source = f"{other}'s {theirs}" if theirs else other
            enclosure = f"your {target_interior}" if target_interior else "you"
            relation = f"{source} within {enclosure}"
            if mine:
                relation += f", with contact at your {mine}"
            verb = "registers"
        return f"{site} {verb} {relation}: {quality}, {tail}"

    sensation_kind = "moving" if motion_kind == "moving" else "settled"
    relation, quality = _SENSATION_FORMS[(sensation_kind, side)]
    site = f"your {mine}" if mine else "your body"
    source = f"{other}'s {theirs}" if theirs else other
    # Body parts are routinely plural, and the subject here is the PART, not
    # the person: "your legs registers" and "against it" for two legs are the
    # same agreement bug `contact_phrase` already carries `_part_is_plural`
    # for. The trailing pronoun refers back to the perceiver's own part.
    plural = _part_is_plural(mine) if mine else False
    verb = "register" if plural else "registers"
    relation = relation.replace(" it", " them") if plural else relation
    return f"{site} {verb} {source} {relation}: {quality}, {tail}"


def spatial_facts(scene: dict, observer: str, source_names) -> list:
    """Deterministic, authoritative one-line spatial statements for a beat, from
    the observer's frame -- GROUND TRUTH a weak narrator must not contradict
    (it need NOT recite them; restraint still governs how much is said). Covers
    exit directions and co-located people (proximity tier, side, rear blind
    spot). Empty when nothing is derivable. This is scaffolding against weak
    models flipping 'behind' to 'ahead' or swapping who is where."""
    facts = []
    digest = spatial_digest(scene, observer)
    dir_word = {"behind": "behind you", "ahead": "ahead of you",
                "left": "to your left", "right": "to your right",
                "above": "above you", "below": "below you"}
    for bucket, word in dir_word.items():
        for ref in digest.get(bucket) or []:
            facts.append(f"{ref['room']} lies {word}.")
    tier_word = {"within_reach": "within arm's reach beside you",
                 "near": "a few steps away", "across": "across the room"}
    for name in source_names or []:
        if name == observer:
            continue
        tier = proximity_rel(scene, observer, name)
        if tier is None:
            continue
        clause = f"{name} is {tier_word.get(tier, 'nearby')}"
        if entity_arc(scene, observer, name) == "rear":
            clause += ", behind you and out of your sight (you hear, not see, them)"
        else:
            side = entity_side(scene, observer, name)
            if side:
                clause += f", on your {side}"
        facts.append(clause + ".")

    # Body position: contact is objective, and it is the fact a narrator most
    # easily contradicts -- describing hands that let go a beat ago, or a hold
    # that was never recorded.
    #
    # BOTH parties must be nameable to this observer, exactly like the
    # proximity clauses above, which only ever iterate source_names. These
    # lines carry canonical names, so a contact involving someone the observer
    # does not recognize would hand the narrator a name the observer has no way
    # to know -- the leak this engine exists to prevent. Being held by a
    # stranger therefore yields no line here rather than a named one; the
    # perception view still reports the hold in the observer's own terms.
    # Relative size, when anyone is off their baseline. This is the fact that
    # silently invalidates everything else -- reach, lifting, whether a hold is
    # even possible -- so it is stated before the contacts below it.
    # Light before anything else: it decides whether the rest of this list is
    # perceivable at all.
    here = effective_light(scene, room_of(scene, observer))
    if here == "dark":
        facts.append(
            "It is pitch dark here — you cannot see anything, including the "
            "people in this room with you.")
    elif here == "dim":
        facts.append("The light here is dim; shapes and movement, not detail.")
    elif here == "bright":
        facts.append("The light here is harsh and bright.")

    # Bodily condition, when the story tracks it at all. Lazy import: survival
    # reads spatial for sealed-enclosure detection, and this is the only edge
    # back the other way.
    if scene.get("vitals"):
        from survival import vitals_facts
        facts.extend(vitals_facts(scene, observer))

    facts.extend(size_facts(scene, observer, source_names))
    # Being carried is a harder constraint than any of the above: it decides
    # where you are at all, so the narrator is told before it describes anyone
    # walking anywhere.
    facts.extend(containment_facts(scene, observer, source_names))
    facts.extend(pose_facts(scene, observer, source_names))

    visible = {str(n) for n in (source_names or []) if n} | {observer}
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        actor = str(contact.get("actor") or "").strip()
        target = str(contact.get("target") or "").strip()
        if actor not in visible or target not in visible:
            continue
        phrase = contact_phrase(contact)
        if phrase:
            facts.append(phrase + ".")
    return facts


def _merge_room(existing: dict, incoming: dict, room_id=None) -> dict:
    """Merge an incoming room redeclaration into an already-known room.

    A director/mapping model redeclaring a room to add or change one
    adjacency edge has no reliable way to also echo back every other edge
    it didn't touch. Replacing the whole room (the old behavior) silently
    drops every edge the model didn't re-mention -- observed live when
    generating a west wing connection wiped out an existing corridor's
    links to the entrance hall and stairwell. Adjacency is merged by
    upserting on `to`: an incoming edge with the same target updates it
    (so barrier/distance changes still work), edges not mentioned survive.
    Explicit removal goes through `remove_adjacent`, not silence.
    """
    merged_room = dict(existing)

    for field in ("name", "desc", "notes", "parent_entity"):
        if not incoming.get(field):
            continue
        if field == "name" and existing.get("name") \
                and is_derived_room_name(room_id, incoming[field]):
            continue  # an id slug never overwrites a name someone authored
        merged_room[field] = incoming[field]

    existing_edges = {
        edge.get("to"): dict(edge)
        for edge in (existing.get("adjacent") or [])
        if isinstance(edge, dict) and edge.get("to")
    }

    # Edge FIELDS get the same silence-vs-erasure doctrine the edges
    # themselves already have. A model re-mentioning a doorway ("r0503
    # connects to r0603, open") has no reliable way to also echo back the
    # bearing it never thinks about, and wholesale replacement here was
    # erasing authored `dir`s every time -- measured live (maze arm): 18 of
    # 98 edge-sides stripped bare, including the shrine's ONLY approach,
    # after which every declared "run east" through them failed and
    # sprint_reach stopped offering the passage at all. An absent field is
    # silence; a value (barrier changes, a re-bearing) still lands.
    for edge in (incoming.get("adjacent") or []):
        if isinstance(edge, dict) and edge.get("to"):
            prior = existing_edges.get(edge["to"])
            if prior:
                spoken = {k: v for k, v in edge.items()
                          if v is not None and v != ""}
                existing_edges[edge["to"]] = {**prior, **spoken}
            else:
                existing_edges[edge["to"]] = dict(edge)

    merged_room["adjacent"] = list(existing_edges.values())

    for key, value in incoming.items():
        if key in ("name", "desc", "notes", "parent_entity", "adjacent"):
            continue
        # An empty container is indistinguishable from "the model did not
        # mention this", so it cannot be read as an erasure -- the doctrine
        # `_ENTITY_DEFAULT_FIELDS` already applies to entities, and the same
        # trap on rooms costs more: blanking `anchors` takes every station
        # hanging off them with it, silently, on any beat that re-echoes the
        # room. Emptying one goes through an explicit write, not a default.
        if key in _ROOM_SILENT_WHEN_EMPTY and not value:
            continue
        merged_room[key] = value

    return merged_room


# Room fields whose empty value means "unmentioned" rather than "cleared".
_ROOM_SILENT_WHEN_EMPTY = frozenset({"anchors", "size", "zone", "light",
                                     "exposure"})

# Every SceneEntityDef field whose schema default is indistinguishable from
# "the model did not mention this". A diff carrying one of these cannot be
# read as an erasure -- see _merge_entity.
_ENTITY_DEFAULT_FIELDS = {
    "kind": "object",
    "description": "",
    "aliases": [],
    "portable": False,
    "container": False,
    "interior_rooms": [],
    "ubiquitous": False,
    # Absent from this map, these two could only ever be set at CREATION: the
    # merge below copies listed fields and leaves everything else at whatever
    # the existing record held, so a Director declaring `enclosure` on an
    # entity it had already introduced was silently dropped every time. That
    # made both fields unfixable in flight -- an interior authored see-through
    # stayed see-through for the rest of the story, and a lamp that came back
    # without its emission could never get it back. None is the right default
    # here precisely because it is what "not declared" already looks like, so
    # silence still reads as silence.
    "enclosure": None,
    "light_source": None,
}


def _merge_entity(entity_id, existing: dict, incoming: dict) -> dict:
    """Merge an incoming entity redeclaration into an already-known entity.

    The exact sibling of _merge_room, and for the same reason: a Director
    updating one entity's pose has no way to echo back the description,
    aliases and interior rooms it did not touch. `entities.update(diff)`
    replaced the whole record instead -- and because validation fills every
    absent field with a schema default first, the replacement looked
    complete. Observed live (Elevator Adventure branch 41) on a pose-only
    diff: "Blue Police Box" (kind vehicle, container, interior_rooms
    ["tardis_interior_001"]) became "Tardis 001", kind object, no interior;
    the registered character "The Doctor" became an object named "The
    Doctor 10". Both then read back corrupted on every later turn.

    So a schema DEFAULT is treated as silence, never as an erasure, and a
    name the validator derived from the key cannot displace a real one.
    Deliberate changes still land: any non-default value wins, and
    genuinely clearing a field goes through remove_entities, not silence.
    """
    merged = dict(existing)

    incoming_name = str(incoming.get("name") or "").strip()
    existing_name = str(existing.get("name") or "").strip()
    if incoming_name and not (
        existing_name
        and is_derived_entity_name(entity_id, incoming_name,
                                   incoming.get("kind"))
    ):
        merged["name"] = incoming_name

    for field, default in _ENTITY_DEFAULT_FIELDS.items():
        if field not in incoming:
            continue
        value = incoming[field]
        if value == default and existing.get(field, default) != default:
            continue  # silence, not an erasure
        merged[field] = value

    # `state` is the live, per-beat half of an entity and is the field a
    # partial diff most often carries alone: merge key-wise so a pose
    # update keeps the transit//link state the same entity depends on.
    incoming_state = incoming.get("state")
    if isinstance(incoming_state, dict):
        state = dict(existing.get("state") or {})
        state.update(incoming_state)
        merged["state"] = state
    elif "state" in incoming:
        merged["state"] = incoming_state

    for key, value in incoming.items():
        if key == "name" or key == "state" or key in _ENTITY_DEFAULT_FIELDS:
            continue
        merged[key] = value

    return merged


def _dedupe_adjacent(edges):
    """Collapse adjacency edges that target the same room, keeping the LAST
    occurrence for each target (matching _merge_room's upsert-by-'to').

    _merge_room already dedupes, but ONLY for a room present in the incoming
    diff. A room the model doesn't re-declare this turn is carried through the
    merge verbatim, so a duplicate 'to' edge introduced once -- e.g. when
    rename-remapping rewrites two edges onto the same target -- otherwise
    persists frozen across every subsequent turn. That leaves a room
    simultaneously walled off from AND open-doored to the same neighbor
    (barrier 'wall' and 'open_door' at once), which makes perception's spatial
    cues incoherent. Deduping every room on every merge heals it. First-seen
    'to' order is preserved; malformed edges (no 'to') pass through untouched."""
    seen, order, extras = {}, [], []
    for edge in edges or []:
        if isinstance(edge, dict) and edge.get("to"):
            if edge["to"] not in seen:
                order.append(edge["to"])
            seen[edge["to"]] = edge  # last wins, matching _merge_room
        else:
            extras.append(edge)
    return [seen[t] for t in order] + extras


def _dedup_duplicate_position_keys(positions, entities, incoming_positions=None):
    """Collapse a position keyed under BOTH an entity's id and its display name
    to one key. Only a genuine duplicate is touched; a lone id-keyed position
    (an object with no name twin) is left alone. When both keys are present the
    FRESH write wins -- the one in this diff's incoming positions -- else the
    display-name key (the convention `room_of` and every character use).
    """
    if not isinstance(positions, dict) or not isinstance(entities, dict):
        return positions
    incoming = incoming_positions if isinstance(incoming_positions, dict) else {}
    for eid, ent in list(entities.items()):
        name = (ent.get("name") or "").strip() if isinstance(ent, dict) else ""
        if not name or name == eid:
            continue
        if eid in positions and name in positions:
            # Prefer whichever key this diff just wrote; default to the name.
            if eid in incoming and name not in incoming:
                positions[name] = positions.pop(eid)
            else:
                positions.pop(eid, None)
    return positions


# Durable structural facts about an entity, as opposed to `state`, which is a
# snapshot of right now. When two records for one entity are collapsed these
# survive from whichever record has them; `state` never merges (see below).
_ENTITY_STRUCTURAL_FIELDS = (
    "kind", "subtype", "name", "description", "aliases", "interior_rooms",
    "portable", "container", "ubiquitous", "parent_entity",
    # What the thing is made of and what it gives off are as durable as what
    # it is -- and were being lost whenever two records for one entity
    # collapsed, which is the other half of the same gap.
    "enclosure", "light_source",
)


def _dedup_duplicate_entity_keys(entities, incoming_entities=None):
    """Collapse an entity recorded under BOTH its id and its display name.

    The third instance of one bug. A character legitimately answers to several
    scene keys -- display name, identity.uid, aliases (see
    agents.common.character_scene_keys) -- and the Director keys with whichever
    it reaches for. `positions` survived that because readers try every key and
    duplicates collapse (_dedup_duplicate_position_keys); `attire` was healed
    after a character rendered as wearing nothing while her clothing state still
    described her coat (commit._heal_attire_identity_keys). `entities` had
    neither, and it is the record that says what each body is doing and what it
    is in contact with.

    Observed live: one character held two entity records -- `char_9f13c0a4...`
    frozen at the beat it was created, and `Bramwell` written every beat
    since. Both claimed to describe her, so "who is in contact with whom" had
    two contradictory answers at once, one of them arbitrarily old, and every
    reader that walks entities saw the same person twice.

    Unlike attire, `state` is NOT merged: a wardrobe accumulates, but contact
    and posture describe a single instant, so folding a stale snapshot into a
    fresh one is what manufactures the contradiction. The fresh record's state
    wins whole. Only the structural fields above are rescued from the loser, so
    collapsing can never drop a vehicle's interior_rooms or an entity's aliases.
    """
    if not isinstance(entities, dict):
        return entities
    incoming = incoming_entities if isinstance(incoming_entities, dict) else {}

    for eid, ent in list(entities.items()):
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip()
        if not name or name == eid or name not in entities:
            continue
        twin = entities.get(name)
        if not isinstance(twin, dict) or twin is ent:
            continue

        # The display name is the surviving KEY either way (the convention every
        # reader uses); which record's content survives depends on which one
        # this diff just wrote.
        if eid in incoming and name not in incoming:
            winner, loser = ent, twin
        else:
            winner, loser = twin, ent

        merged = dict(winner)
        for field in _ENTITY_STRUCTURAL_FIELDS:
            if field not in merged or merged.get(field) in (None, "", [], {}):
                if loser.get(field) not in (None, "", [], {}):
                    merged[field] = loser[field]
        merged["name"] = name

        entities[name] = merged
        entities.pop(eid, None)

    return entities


def _shield_standing_bearings(prior_rooms, incoming_rooms):
    """Refuse a ONE-SIDED re-bearing of a doorway both sides already agree on.

    A doorway whose two declared sides carry opposite-consistent bearings is
    a standing agreement -- usually authored world geometry. A model
    re-declaring one room routinely emits a wrong `dir` for an edge it is
    only mentioning in passing, and letting that single claim through
    destroys the agreement twice over: normalize_scene_bearings sees the
    contradiction and drops BOTH sides ("dropped rather than guessed"), and
    its reciprocal inference then faithfully rebuilds whatever wrong bearing
    gets asserted next. Measured live (maze arm): five doorway pairs carried
    internally-consistent bearings that were geometrically FALSE, and a
    runner was walked north on a declared "west" -- model noise laundered
    into scene truth by the engine's own repair machinery.

    So: an incoming `dir` that contradicts a standing opposite-consistent
    pair is stripped (the edge itself still merges -- barrier and distance
    changes land) unless the SAME diff re-declares the reciprocal side with
    the matching opposite. Changing settled geometry takes a two-sided
    declaration; a one-sided one falls back to the incumbent. Returns a
    sanitized copy; never mutates the caller's diff.
    """
    if not isinstance(incoming_rooms, dict) or not isinstance(
            prior_rooms, dict):
        return incoming_rooms

    def _edge_dir(rooms, room_id, to_id):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            return None
        for e in room.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == str(to_id):
                return normalize_bearing(e.get("dir"))
        return None

    out = {}
    for room_id, room in incoming_rooms.items():
        if not isinstance(room, dict) or not room.get("adjacent"):
            out[room_id] = room
            continue
        edges = []
        touched = False
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                edges.append(edge)
                continue
            new_dir = normalize_bearing(edge.get("dir"))
            to_id = edge["to"]
            if new_dir:
                fwd = _edge_dir(prior_rooms, room_id, to_id)
                back = _edge_dir(prior_rooms, to_id, room_id)
                standing = (fwd and back
                            and opposite_bearing(fwd) == back)
                if standing and new_dir != fwd:
                    recip = _edge_dir(incoming_rooms, to_id, room_id)
                    if recip != opposite_bearing(new_dir):
                        edge = {k: v for k, v in edge.items() if k != "dir"}
                        touched = True
            edges.append(edge)
        out[room_id] = {**room, "adjacent": edges} if touched else room
    return out


def _shield_standing_passage(prior_rooms, incoming_rooms, add_warning=None):
    """Refuse a ONE-SIDED sealing of a doorway that is standing open.

    The mirror of `_shield_standing_bearings`, and it exists because the same
    thing happened to `barrier` that had already happened to `dir`. Live, chat
    63 turn 165, across five consecutive rerolls: `mapping_stage` authored the
    stair between the shrine's two floors as `open_shoji` every single time,
    and `director_resolve` then re-declared the RETURN edge alone as `wall` --
    leaving one direction passable, the other sealed, and no route between a
    hall and its own upstairs.

    A barrier is a property of the doorway, not of the side you stand on. So a
    one-sided downgrade from passable to `wall` falls back to the incumbent
    unless the SAME diff seals the reciprocal side too. Sealing a passage takes
    a two-sided declaration; everything else about the edge still merges, and a
    room the diff opens UP is never blocked -- this only refuses the close.
    """
    if not isinstance(incoming_rooms, dict) or not isinstance(prior_rooms, dict):
        return incoming_rooms

    def _edge_barrier(rooms, room_id, to_id):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            return None
        for e in room.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == str(to_id):
                return normalize_barrier(e.get("barrier"))
        return None

    out = {}
    for room_id, room in incoming_rooms.items():
        if not isinstance(room, dict) or not room.get("adjacent"):
            out[room_id] = room
            continue
        edges = []
        touched = False
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                edges.append(edge)
                continue
            to_id = edge["to"]
            new_barrier = normalize_barrier(edge.get("barrier"))
            if new_barrier == "wall":
                fwd = _edge_barrier(prior_rooms, room_id, to_id)
                back = _edge_barrier(prior_rooms, to_id, room_id)
                standing = (fwd in _PASSABLE_BARRIERS
                            or back in _PASSABLE_BARRIERS)
                recip = _edge_barrier(incoming_rooms, to_id, room_id)
                if standing and recip != "wall":
                    edge = {k: v for k, v in edge.items() if k != "barrier"}
                    touched = True
                    if add_warning:
                        add_warning(
                            "kept the passage %s -> %s open: it was sealed "
                            "from one side only, and the other side still "
                            "reads %r" % (room_id, to_id,
                                          recip or fwd or back))
            edges.append(edge)
        out[room_id] = {**room, "adjacent": edges} if touched else room
    return out


def connect_orphan_new_rooms(scene: dict, prev_scene: dict) -> list:
    """A room created this turn must be reachable from somewhere.

    Adjacency resolves BOTH ways, so a room with an empty `adjacent` is fine as
    long as something points AT it -- which is why `alley_room` works while
    carrying no edges of its own. The failure is the stronger one: a room no
    edge reaches in EITHER direction. `spatial_rel` answers `separated`/`far`
    for every pair involving it, so it is an island, and the only thing its
    occupants can perceive is whatever happens to be standing in it with them.

    Live (chat 58): `northern_plaza` was minted with `adjacent: []` and nothing
    pointing at it. The player stepped out of the TARDIS into a described city
    plaza -- shuttered buildings, dripping awnings, an alley the Dalek was
    grinding out of -- and her view could only offer her the police box she had
    just left, because the dock edge was the single edge the map admitted.

    Applied ONLY to rooms that are new in this merge, and only at the moment
    they are created, because that is the one point where the engine still has
    the context to place them: where the bodies were standing immediately
    before. After the fact there is nothing left to infer from, which is why
    this cannot be a periodic repair pass.

    Interiors are skipped: a `parent_entity` room's doorway is DERIVED by
    `apply_transit_dock_edges` (which runs straight after this), and a sealed
    or in-transit hull is severed from the world on purpose.

    Mutates `scene` in place. Returns [(room_id, attached_to), ...].
    """
    rooms = scene.get("rooms")
    if not isinstance(rooms, dict) or len(rooms) < 2:
        return []
    known = set((prev_scene or {}).get("rooms") or {})
    fresh = [rid for rid in rooms if rid not in known]
    if not fresh:
        return []

    reached = set()
    for rid, room in rooms.items():
        for edge in (room.get("adjacent") or []):
            if isinstance(edge, dict) and edge.get("to"):
                reached.add(str(edge["to"]))
                reached.add(str(rid))

    # Where the bodies were standing BEFORE this turn's diff -- the scene's
    # centre of gravity, and the only honest guess available.
    counts = {}
    for room_id in ((prev_scene or {}).get("positions") or {}).values():
        if room_id and room_id in rooms:
            counts[room_id] = counts.get(room_id, 0) + 1
    attached = []
    for rid in fresh:
        room = rooms[rid]
        if not isinstance(room, dict) or room.get("parent_entity"):
            continue
        if rid in reached:
            continue
        anchor = max((r for r in counts if r != rid),
                     key=counts.get, default=None)
        if anchor is None:
            anchor = next((r for r in rooms if r != rid), None)
        if not anchor:
            continue
        room.setdefault("adjacent", []).append(
            {"to": anchor, "barrier": "open", "distance": "near"})
        reached.add(rid)
        reached.add(anchor)
        attached.append((rid, anchor))
    return attached


def _position_key(scene: dict, name) -> Optional[str]:
    """Canonical existing position key for an actor label, case-insensitive."""
    label = str(name or "").strip()
    if not label:
        return None
    positions = scene.get("positions") or {}
    if label in positions:
        return label
    folded = label.casefold()
    return next(
        (key for key in positions
         if str(key).strip().casefold() == folded),
        None,
    )


def apply_following_ops(scene: dict, operations) -> dict:
    """Apply voluntary durable follower -> target relations to ``scene``.

    Following records intention and ordinary travel affiliation; it never
    changes a position here. Movement follow-through is deliberately owned by
    the Director, where pace, barriers, and actor decisions are available.
    This function only maintains the durable ledger used equally by mid-turn
    perception merges, commit, checkpoints, branches, and rerolls.
    """
    following = scene.get("following")
    if not isinstance(following, dict):
        following = scene["following"] = {}

    for raw in operations or []:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "").strip().casefold()
        follower = _position_key(scene, raw.get("follower"))
        if follower is None:
            continue
        if op == "stop":
            for key in list(following):
                if str(key).strip().casefold() == follower.casefold():
                    following.pop(key, None)
            continue
        if op != "start":
            continue
        target = _position_key(scene, raw.get("target"))
        if target is None or target.casefold() == follower.casefold():
            continue

        # A follows B follows A is not travel; it is an ownerless cycle. Longer
        # cycles are rejected on the same terms. Case-tolerant because older
        # scenes can carry human-authored labels.
        cursor = target
        visited = {follower.casefold()}
        cyclic = False
        while cursor:
            folded = cursor.casefold()
            if folded in visited:
                cyclic = True
                break
            visited.add(folded)
            rec = next(
                (value for key, value in following.items()
                 if str(key).strip().casefold() == folded
                 and isinstance(value, dict)),
                None,
            )
            cursor = _position_key(scene, (rec or {}).get("target"))
        if cyclic:
            continue

        # Replace a case-variant/old target in place; one body follows at most
        # one target at a time.
        for key in list(following):
            if str(key).strip().casefold() == follower.casefold():
                following.pop(key, None)
        following[follower] = {
            "target": target,
            "since_turn": raw.get("turn"),
            "reason": str(raw.get("reason") or "").strip(),
        }

    # A departed/deleted actor cannot remain in the travel ledger. Separation
    # alone does NOT clear it: a follower left behind by a sprint may still be
    # trying to catch up and decides that on their next beat.
    positioned = {
        str(key).strip().casefold() for key in (scene.get("positions") or {})
    }
    for follower, rec in list(following.items()):
        target = str((rec or {}).get("target") or "").strip().casefold() \
            if isinstance(rec, dict) else ""
        if str(follower).strip().casefold() not in positioned \
                or target not in positioned:
            following.pop(follower, None)
    return scene


def merge_scene_with_diff(
    scene: dict,
    diff: dict | None,
    *,
    contact_report=None,
    substance_report=None,
) -> dict:
    diff = diff or {}
    # A scene is a nested mutable structure.  A shallow copy allowed
    # downstream normalization and deterministic backstops (zone stamping,
    # adjacency edits, overlays, attire) to mutate the caller's supposedly
    # pre-diff scene through shared child dictionaries/lists.  That made
    # before/after comparisons order-dependent and could contaminate rollback
    # preparation.  Scene merges are correctness boundaries, so pay the small
    # cost of a real copy here.
    merged = copy.deepcopy(scene)

    merged["rooms"] = dict(merged.get("rooms") or {})
    merged["entities"] = dict(merged.get("entities") or {})
    merged["positions"] = dict(merged.get("positions") or {})

    _prior_rooms = (merged["rooms"]
                    if isinstance(merged.get("rooms"), dict) else {})
    incoming_rooms = _shield_standing_bearings(
        _prior_rooms, diff.get("rooms") or {})
    incoming_rooms = _shield_standing_passage(
        _prior_rooms, incoming_rooms)
    incoming_entities = diff.get("entities") or {}
    incoming_positions = diff.get("positions") or {}
    incoming_stations = diff.get("stations") or {}
    incoming_poses = diff.get("poses") or {}

    if isinstance(incoming_rooms, dict):
        for room_id, incoming_room in incoming_rooms.items():
            if not isinstance(incoming_room, dict):
                continue
            existing_room = merged["rooms"].get(room_id)
            merged["rooms"][room_id] = (
                _merge_room(existing_room, incoming_room, room_id)
                if isinstance(existing_room, dict)
                else incoming_room
            )

    if isinstance(incoming_entities, dict):
        for entity_id, incoming_entity in incoming_entities.items():
            existing_entity = merged["entities"].get(entity_id)
            merged["entities"][entity_id] = (
                _merge_entity(entity_id, existing_entity, incoming_entity)
                if isinstance(existing_entity, dict)
                and isinstance(incoming_entity, dict)
                else incoming_entity
            )

    # An entity keyed by its id in one beat and by its display name in the next
    # leaves TWO records for one body -- each with its own posture and contact,
    # one of them frozen at whatever beat it was last written. Collapse before
    # anything reads them (positions dedup below reads entities, and every
    # perception/narration reader walks this dict).
    _dedup_duplicate_entity_keys(merged["entities"], incoming_entities)

    # A FIELD NAME can never key an entity. A sibling field written one
    # nesting level too deep (or its validation debris) arrives in the
    # entities map keyed `remove_entities`, `notes`, ... -- chat 80's scene
    # carried six such "entities", each a verbatim copy of the Interview
    # Chair. The hoist in schemas.preprocess_llm_output now stops new ones at
    # validation; this floor refuses whatever still arrives AND heals a scene
    # already carrying them, since the merged blob is what commits -- the
    # same heal-on-load shape commit._fold_duplicate_presences uses, so a
    # live story needs no migration.
    for _bad in [k for k in merged["entities"] if k in NON_ENTITY_FIELD_KEYS]:
        merged["entities"].pop(_bad, None)

    if isinstance(incoming_positions, dict):
        merged["positions"].update(incoming_positions)
    # The same refusal for the position ledger: a field name is not a body,
    # so it cannot stand in a room. After the update so an incoming key is
    # refused too, before the dedup below reads the ledger.
    for _bad in [k for k in merged["positions"] if k in NON_ENTITY_FIELD_KEYS]:
        merged["positions"].pop(_bad, None)
    # DW-4: an entity can end up in `positions` under BOTH its id key and its
    # display-name key -- e.g. an auto-created backstory person seeded with an
    # id-keyed position (`karen_marsh`) while director_resolve moves it by name
    # (`Karen Marsh`). The blind update() above then leaves BOTH, so the entity
    # is co-present in two rooms and perception's co-present set is corrupted.
    # Collapse only a genuine id+name DUPLICATE -- a lone id-keyed object
    # position (tardis, a dropped item) has no name-key twin and is untouched.
    _dedup_duplicate_position_keys(
        merged["positions"], merged["entities"], incoming_positions)

    # Stations (within-room position) are a sibling of positions, merged per
    # entity so a diff touching only `at` keeps the entity's `near` list, and
    # vice versa. Hygiene (phantom-anchor blanking, non-colocated pruning,
    # symmetrization) runs below via normalize_scene_stations.
    if isinstance(incoming_stations, dict) and incoming_stations:
        merged["stations"] = dict(merged.get("stations") or {})
        for name, st in incoming_stations.items():
            if isinstance(st, dict):
                cur = dict(merged["stations"].get(name) or {})
                cur.update(st)
                merged["stations"][name] = cur
    apply_pose_diff(merged, incoming_poses)

    for removal in diff.get("remove_adjacent") or []:
        if not isinstance(removal, dict):
            continue
        room = merged["rooms"].get(removal.get("room"))
        target = removal.get("to")
        if not isinstance(room, dict) or not target:
            continue
        room["adjacent"] = [
            edge for edge in (room.get("adjacent") or [])
            if not (isinstance(edge, dict) and edge.get("to") == target)
        ]

    for entity_id in diff.get("remove_entities") or []:
        entity = merged["entities"].pop(entity_id, None)

        if not entity:
            continue

        names = {
            entity_id,
            str(entity.get("name") or ""),
            *(entity.get("aliases") or []),
        }

        for name in names:
            if name:
                merged["positions"].pop(name, None)
        folded_names = {str(name).strip().casefold() for name in names if name}
        merged["poses"] = {
            name: pose for name, pose in (merged.get("poses") or {}).items()
            if str(name).strip().casefold() not in folded_names
        }
        for pose in (merged.get("poses") or {}).values():
            if isinstance(pose, dict) and str(
                    pose.get("relative_to") or "").strip().casefold() in folded_names:
                pose["relative_to"] = ""
                pose["relation"] = ""
                pose["constraint"] = ""
        merged["substances"] = [
            record for record in (merged.get("substances") or [])
            if not isinstance(record, dict)
            or str(record.get("target") or "").strip().casefold()
            not in folded_names
        ]

    occupied_rooms = set(merged["positions"].values())

    for room_id in diff.get("remove_rooms") or []:
        if room_id in occupied_rooms:
            continue
        merged["rooms"].pop(room_id, None)
        merged["substances"] = [
            record for record in (merged.get("substances") or [])
            if not isinstance(record, dict)
            or str(record.get("target") or "") != str(room_id)
        ]

    # A body's interior is opaque whether or not anyone declared it so. Runs
    # BEFORE the dock-edge rewrite, which reads `enclosure` to pick the
    # doorway's barrier.
    infer_body_enclosures(merged)

    # Derived dock/portal edges are a function of the merged scene, not an
    # authored fact -- recompute them here so every consumer of a merge
    # (commit preparation, perception's mid-turn merges) sees the same
    # correct doorways. Runs before barrier normalization, which then
    # canonicalizes whatever the rewrite emitted.
    # A room minted this turn that no edge reaches is an island: every pair
    # involving it answers `separated`/`far`, so its occupants can perceive
    # nothing but each other. Runs BEFORE the dock rewrite, which owns
    # interiors and is left to derive those on its own.
    connect_orphan_new_rooms(merged, scene)

    apply_transit_dock_edges(merged)

    # Collapse duplicate same-target adjacency edges across EVERY room, not
    # just the ones re-declared this turn -- otherwise a duplicate frozen into
    # an untouched room (a neighbor that is both walled and open-doored) leaks
    # incoherent spatial cues into perception forever. See _dedupe_adjacent.
    for room in merged["rooms"].values():
        if isinstance(room, dict) and room.get("adjacent"):
            room["adjacent"] = _dedupe_adjacent(room["adjacent"])

    normalize_scene_barriers(merged)
    # Optional compass bearings on edges: canonicalize each `dir` and reconcile
    # reciprocals so either room can derive a consistent left/right. Runs after
    # dedupe (so only surviving edges are reconciled) and barrier normalization.
    normalize_scene_bearings(merged)
    # Station hygiene moved to the end of the merge, beside contact hygiene:
    # it has to run after `derive_contained_positions`, or a carried body keeps
    # the anchor it was standing at while its carrier walks off with it.
    # Body position tracking: apply this beat's contact ops, then prune every
    # contact that positions no longer permit. Runs LAST, after positions are
    # final, which is what makes walking away end a hold with nothing for the
    # Director to remember.
    # Lift any contact the Director wrote into an entity's own state (the shape
    # that predates contacts, and the one a model still reaches for) before the
    # ops, so both paths land in one place and one truth survives.
    contacts_from_entity_state(merged)
    # The key always exists after a merge, empty or not: a reader that has to
    # ask whether contact tracking is "on" for this scene is a reader that will
    # eventually forget to.
    merged.setdefault("contacts", [])

    # Scale FIRST, and the contacts it invalidates with it -- before this
    # beat's contact ops, not after. A size change cancels the holds that were
    # standing when it happened; the Director is then expected to re-establish
    # whatever the new geometry allows IN THE SAME BEAT, and those ops must
    # survive. Cancelling after them would wipe exactly the correct behaviour.
    incoming_scales = diff.get("scales")
    previous_scales = dict(merged.get("scales") or {})
    if isinstance(incoming_scales, dict) and incoming_scales:
        scales = dict(previous_scales)
        for name, raw in incoming_scales.items():
            label = str(name or "").strip()
            if not label:
                continue
            factor = clamp_scale(raw)
            # An explicit 1.0 (or an unusable value) means "back to normal";
            # normalize_scene_scales drops it, which is the same thing.
            scales[label] = factor if factor is not None else 1.0
        merged["scales"] = scales
    merged.setdefault("scales", {})
    normalize_scene_scales(merged)
    # The return value is for callers/tests; nothing is stashed in the scene,
    # which is saved verbatim and must not accumulate scratch keys.
    contacts_broken_by_scale_change(merged, previous_scales)

    # Containment. Declared as {subject: {"in": holder, "mode": ...}}, with a
    # null/empty value releasing -- the same shape positions uses, because a
    # body is in exactly one container at a time.
    merged.setdefault("contained", {})
    # A size change releases containment for the same reason it breaks a hold:
    # someone restored to full height is not still in the coat pocket. Runs
    # BEFORE this beat's own containment declarations, so a Director that
    # re-declares the arrangement as the thing it now is keeps it -- the same
    # ordering the contact cancellation needs, and for the same reason.
    containment_broken_by_scale_change(merged, previous_scales)
    incoming_contained = diff.get("containment")
    if isinstance(incoming_contained, dict):
        for subject, raw in incoming_contained.items():
            label = str(subject or "").strip()
            if not label:
                continue
            record = _clean_containment(raw, label) if raw else None
            if record is None:
                # Released: out of the pocket, off the shoulder, out of the jar.
                for key in [k for k in merged["contained"]
                            if str(k).strip().casefold() == label.casefold()]:
                    merged["contained"].pop(key, None)
            else:
                merged["contained"][label] = record
    # One spelling per being, BEFORE anything resolves a subject against
    # another ledger. A containment record naming an entity id and a positions
    # map keyed by the display name are the same fact written twice, and every
    # lookup between them fails silently until they agree.
    normalize_scene_subjects(merged)
    normalize_scene_containment(merged)
    # Derived LAST among position writes: whatever else this beat did to
    # positions, a carried body ends up where its carrier is.
    derive_contained_positions(merged)
    # ...and a position that names an ENTITY rather than a room is repaired
    # after that, so a real containment record always wins over the guess.
    repair_entity_positions(merged)
    # A bodiless voice is not standing anywhere; a position on one is a
    # category error that no author can currently delete by hand.
    prune_bodiless_positions(merged)

    # Durable travel affiliation. This changes only the relation ledger;
    # position follow-through already ran at Director resolution so perception
    # and commit merge the exact same destinations.
    apply_following_ops(merged, diff.get("following_ops"))

    # Non-discrete matter is located while onset contact still stands.  That
    # ordering is causal: a release can occur through an interior relation and
    # the bodies can withdraw later in the same beat.  Deriving after contact
    # removals would erase the route that established the destination.
    apply_substance_ops(merged, diff.get("substance_ops"),
                        report=substance_report)

    apply_contact_ops(merged, diff.get("contact_ops"),
                      report=contact_report)
    normalize_scene_contacts(merged)

    # Within-room position, last of all. Contact is settled by now, and contact
    # is what the derivation reads: a hand on the quilt is a body at the bed.
    # Then the same hygiene as before -- prune a stale anchor (which auto-heals
    # a room move), drop non-co-located `near` links, symmetrize what survives.
    derive_scene_stations(merged, diff.get("stations"), diff.get("contact_ops"))
    merged.setdefault("stations", {})
    normalize_scene_stations(merged)
    normalize_scene_poses(merged)

    # Channels, after rooms have settled: a channel names rooms, so it can only
    # be pruned once this beat's room retirements are known.
    apply_comms_ops(merged, diff.get("comms_ops"))
    normalize_scene_comms(merged)

    # Bodily condition, last: air depends on whether the doorway ended the beat
    # sealed, which the dock-edge rewrite above has only just settled. Entirely
    # skipped unless something has written a vitals table -- absence is the
    # off switch, so a story without survival tracking never touches this.
    incoming_vitals = diff.get("vitals")
    if incoming_vitals or merged.get("vitals"):
        from survival import apply_vitals_diff, tick_vitals
        apply_vitals_diff(merged, incoming_vitals)
        elapsed = 0
        time_block = diff.get("time")
        if isinstance(time_block, dict):
            elapsed = time_block.get("duration_seconds") or 0
        tick_vitals(
            merged, elapsed,
            asleep=[n for n, r in (merged.get("contained") or {}).items()
                    if isinstance(r, dict) and r.get("mode") == "asleep"],
        )
    return merged


def validate_operations(scene: dict, operations: list) -> list:
    """Validate world mutation operations before atomic commit."""
    known_ids = set((scene.get("entities") or {}).keys())
    known_ids.update((scene.get("rooms") or {}).keys())
    created_ids = set()
    errors = []

    for operation in operations:
        op = operation.get("op")
        if op == "create_entity":
            entity = operation.get("entity") or {}
            entity_id = str(entity.get("entity_id") or "")
            if not entity_id:
                errors.append("Created entity has no entity_id")
            elif entity_id in known_ids or entity_id in created_ids:
                errors.append(f"Duplicate entity ID: {entity_id}")
            else:
                created_ids.add(entity_id)
        elif op == "move_entity":
            entity_id = operation.get("entity_id")
            destination_id = operation.get("destination_id")
            if entity_id not in known_ids | created_ids:
                errors.append(f"Unknown moved entity: {entity_id}")
            if destination_id not in known_ids | created_ids:
                errors.append(f"Unknown movement destination: {destination_id}")
            if entity_id == destination_id:
                errors.append("An entity cannot contain itself")
    return errors
