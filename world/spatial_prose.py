# spatial_prose.py
"""Reader-facing contact phrase renderers and the aggregate spatial_facts bundle."""

import re

from world.spatial_containment import containment_facts, size_facts
from world.spatial_contacts import (
    _CONTACT_RESIDUE_VERB,
    _CONTACT_STATE_VERBS,
    _MOMENTARY_SET,
    _SENSATION_FORMS,
    _endpoint_is_worn_clothing,
    _is_anatomical_part,
    _part_is_clothing,
    _part_is_plural,
    contact_is_momentary,
    contact_motion,
    contact_relation,
)
from world.spatial_geometry import (entity_arc, entity_side, pose_facts,
                              proximity_rel, spatial_digest)
from world.spatial_identity import room_of, same_subject
from world.spatial_light import effective_light


def _interior_label(raw, owner) -> str:
    """An enclosing passage, ready to sit inside somebody's possessive.

    `target_interior` is whatever the fiction called the place, and a Director
    that has minted a room for it writes the ROOM'S NAME -- which carries the
    owner. Wrapping the standard possessive around that says it twice.

    Measured live (chat 97 t58): `target_interior: "Mirelle's Mouth"` rendered
    as "your Mirelle's Mouth" in her own view and "Mirelle Sulmirath's
    Mirelle's Mouth" in his. Structural, not a word list: strip a leading
    possessive that names the owner, by any part of their name, and lower the
    remainder so it reads as the body part it is rather than as a room title.
    """
    label = str(raw or "").strip().replace("_", " ")
    if not label:
        return ""
    tokens = [t for t in re.split(r"\s+", str(owner or "").strip()) if t]
    # The whole name first, then any single part of it: a Director writes
    # "Mirelle Sulmirath's Esophagus" as readily as "Mirelle's Mouth".
    candidates = ([" ".join(tokens)] if len(tokens) > 1 else []) + sorted(
        tokens, key=len, reverse=True)
    for token in candidates:
        for suffix in ("'s", "\u2019s"):
            prefix = token + suffix
            if label.casefold().startswith(prefix.casefold()):
                label = label[len(prefix):].strip()
                break
    # A room title reads as a place; the same words in lower case read as the
    # part of a body they name, which is what a possessive needs.
    return label.lower() if label.istitle() else label


def contact_phrase(contact: dict, *, you=None) -> str:
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

    Clause ORDER is not a caller's choice. A `subject_first=False` option
    existed and nothing ever passed it; what it rendered -- "{right} is under
    {left} ({manner})" -- put the recorded manner back into the clause as a
    bare parenthetical, which is the act-as-standing-state reading the whole
    function exists to prevent, and skipped the residue verbs and the interior
    topology besides. A target-first rendering, if one is ever wanted, is a
    second pass over the same three vocabularies, not a flag.

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
        me, other = actor, target
    elif _is_observer(target):
        mine, theirs = contact.get("target_part"), contact.get("actor_part")
        me, other = target, actor
    else:
        return ""

    # CLOTHING IS NOT A SURFACE THAT TOUCHES AND NOT A PLACE ON A BODY.
    # `_clean_contact` refuses such a record at write time; this is the render
    # floor for records written before that refusal existed, and it sits
    # beside the malformed-part floor below for the same reason.
    #
    # It matters most HERE, of every renderer, because of what comes next:
    # `label_for` is an identity floor built for a PERSON, so a party it
    # cannot place becomes "someone". Handed a garment, it minted a body.
    # Measured live, chat 98 turn 22 -- a record whose target was a worn
    # garment and whose actor_part named another one composed straight into
    # the player's view as "Your uniform registers someone against it: steady
    # pressure, weight and shared warmth, continuous while the contact holds."
    # The narrator invented nothing; it was handed a person.
    if scene is not None and (_endpoint_is_worn_clothing(scene, other)
                              or _part_is_clothing(scene, me, mine)
                              or _part_is_clothing(scene, other, theirs)):
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
    raw_interior = contact.get("target_interior")
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
            yours = f"your {mine}" if mine else "you"
            # The passage belongs to the OTHER body here -- the observer is
            # the one inside it.
            target_interior = _interior_label(raw_interior, other)
            enclosure = (f"{other}'s {target_interior}"
                         if target_interior else other)
            relation = f"{enclosure} enclosing {yours}"
            if theirs:
                relation += f", with contact at {other}'s {theirs}"
        else:
            source = f"{other}'s {theirs}" if theirs else other
            # ...and to the OBSERVER here, who is the one enclosing.
            target_interior = _interior_label(raw_interior, you)
            enclosure = f"your {target_interior}" if target_interior else "you"
            relation = f"{source} within {enclosure}"
            if mine:
                relation += f", with contact at your {mine}"
        return f"You feel {relation}: {quality}, {tail}"

    sensation_kind = "moving" if motion_kind == "moving" else "settled"
    relation, quality = _SENSATION_FORMS[(sensation_kind, side)]
    source = f"{other}'s {theirs}" if theirs else other
    # THE PART GOES WHERE IT IS FELT, not in front of a verb. The old shape
    # put the body part in the subject slot -- "your legs registers ... against
    # it" -- which needed a plural agreement fix and a pronoun pointing back at
    # a noun three words earlier, and still read as instrumentation. Naming the
    # part inside the relation drops both problems: no agreement to get wrong,
    # and nothing for the pronoun to lose track of.
    relation = relation.replace(" it", f" your {mine}" if mine else " you")
    return f"You feel {source} {relation}: {quality}, {tail}"


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

    # Light, which qualifies every VISUAL fact after it -- it decides whether
    # detail is perceivable at all. Not "before anything else": the exit
    # directions and proximity clauses above are already in the list, and they
    # are placement rather than sight, so they stand in the dark.
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
        from world.survival import vitals_facts
        facts.extend(vitals_facts(scene, observer))

    # Relative size, when anyone is off their baseline. The fact that silently
    # invalidates the ones after it -- reach, lifting, whether a hold is even
    # possible -- so it is stated before the contacts at the end.
    facts.extend(size_facts(scene, observer, source_names))
    # Being carried is a harder constraint than any of the above: it decides
    # where you are at all, so the narrator is told before it describes anyone
    # walking anywhere.
    facts.extend(containment_facts(scene, observer, source_names))
    facts.extend(pose_facts(scene, observer, source_names))

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
