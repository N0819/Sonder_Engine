# spatial_contacts.py
"""The contact ledger: part/region identity, manner/relation/motion
classification, cleaning, and op application."""

import hashlib
import re

from world.spatial_containment import (_WHOLE_BODY_PARTS,
                                 containment_conceals, hiding_holders_of,
                                 scale_changed_names)
from world.spatial_identity import _ci_get, canonical_subject, same_subject


# ---------------------------------------------------------------------------
# BODY POSITION TRACKING -- who is in contact with whom, and where.
#
# Contact used to live as prose inside an entity's own `state`: a single
# whole-body `target`, a `proximity` word, and a `description` paragraph
# ("mouth on throat ..., hips ..., tail coiled around the leg"). Model-written
# and model-read, with nothing structural in between, which cost four things:
#
#   * it could not say WHERE -- one whole-body target, so a hand on a shoulder
#     and a grip on a wrist were the same fact, and a hold on two different
#     people at once was unsayable;
#   * it was stored per entity, so one contact became two records (one on each
#     body) free to drift apart, and each was overwritten wholesale each beat;
#   * nothing ever cleared it -- it persisted verbatim until the model happened
#     to rewrite the paragraph, so a grip survived the person walking away; and
#   * no reader could query it, so the narrator had only prose to re-read and
#     was free to contradict it.
#
# A contact is a RELATION, so it is stored once, at scene level, in the same
# grain as `stations` (the within-room sibling of `positions`): a plain list
# that deterministic hygiene prunes at every merge. Movement clearing contact
# falls out of that hygiene rather than needing the model to remember -- exactly
# how a room change already self-heals a stale station anchor.
_MAX_CONTACTS = 40
_MAX_CONTACT_PART = 48
# A qualifier, not a sentence. Long enough for "beneath her shift, feather
# light"; short enough that a model cannot narrate into the ledger.
_MAX_CONTACT_DETAIL = 80

# How many beats of contact talk a contact survives WITHOUT being re-asserted
# before it retires. See `_contact_ops_are_evidence` for what counts as such a
# beat; 2 means a contact survives one silent one and retires on the second.
_CONTACT_STALE_BEATS = 2

# Small controlled vocabulary. Unknown manners are kept (the fiction is wider
# than any list) but normalized to lowercase so equality holds.
#
# A contact is a STATE -- these bodies are touching, here. Every manner below
# can hold still and remain true a beat later.
CONTACT_MANNERS = (
    "touch", "hold", "grip", "press", "rest", "lean", "wrap", "coil",
    "straddle", "pin", "carry", "support",
)

# The other kind of word a Director reaches for: the ACT that produced the
# touch. `kiss`, `bite` and `strike` lived in the vocabulary above and were
# stored identically to `rest` -- so a kiss became a permanent fact about two
# bodies, re-read as present truth by every stage downstream, and narrated as
# happening now for as long as it survived. A kiss is a moment; a hand resting
# is a state, and the record had no way to say which it held.
#
# These are not rejected -- the Director means something real by them, and the
# residue (lips ARE at that forehead) is worth recording. They retire faster
# (`_CONTACT_MOMENTARY_STALE_BEATS`) and render as the residue rather than as
# the act, so a standing contact can never be mistaken for a fresh one. The act
# itself reaches perceivers through the beat's declared sequence, which is the
# representation that carries WHEN.
#
# The fluid verbs are here for the same reason kiss is: a spray or a gush is an
# EVENT, and the matter it moved persists in the substance ledger, not in the
# contact that delivered it. Measured live: a release recorded `spray` stood as
# a moving contact into the resting beat that followed and was still in the
# saved scene, so the later view reported it as still happening.
CONTACT_MOMENTARY_MANNERS = (
    "kiss", "bite", "strike", "pinch", "squeeze", "flick", "lick", "trail",
    "slap", "tap", "stroke", "brush", "nudge", "poke", "punch", "kick",
    "scratch", "swat", "shove", "rub", "caress", "graze", "nip", "suck",
    "nuzzle", "prod", "thrust", "jab", "smack", "tickle", "bump",
    "spray", "spraying", "spurt", "spurting", "squirt", "squirting",
    "gush", "gushing", "splash", "splashing", "drip", "dripping",
)
_MOMENTARY_SET = frozenset(CONTACT_MOMENTARY_MANNERS)

# How a standing contact READS, as (singular subject, plural subject). Durable
# manners keep their own verb (correctly inflected -- the old renderer emitted
# "press" and "kiss" bare to dodge "presss"); a momentary one renders as the
# touch it left behind. The pair is needed because the subject is usually a
# BODY PART, and body parts are routinely plural: "her fingers is against" is
# what a single form produces.
_CONTACT_STATE_VERBS = {
    "touch": ("is against", "are against"),
    "hold": ("holds", "hold"),
    "grip": ("grips", "grip"),
    "press": ("presses against", "press against"),
    "rest": ("rests against", "rest against"),
    "lean": ("leans against", "lean against"),
    "wrap": ("is wrapped around", "are wrapped around"),
    "coil": ("is coiled around", "are coiled around"),
    "straddle": ("straddles", "straddle"),
    "pin": ("pins", "pin"),
    "carry": ("carries", "carry"),
    "support": ("supports", "support"),
}
_CONTACT_RESIDUE_VERB = ("is against", "are against")

# Parts that end in `s` while naming one thing. Everything else ending in `s`
# is taken as plural, which is right far more often than not for anatomy.
# The intimate anatomy is here on live evidence, not completeness: a folded
# envelopment rendered "Elyra's glans move within", and the measured story's
# ledger names anatomical -s parts on most beats it names anything.
_SINGULAR_S_PARTS = frozenset({"abs", "iris", "solar plexus", "biceps",
                               "triceps", "forceps", "glans", "penis",
                               "anus", "clitoris", "uterus", "pelvis"})


def _part_is_plural(part: str) -> bool:
    part = str(part or "").strip().casefold()
    return bool(part) and part.endswith("s") and part not in _SINGULAR_S_PARTS


# Words that pick out WHICH of a paired part is meant. Everything else is a
# different KIND of part, on purpose: `tail_spade` is not `tail` blurred, it is
# a nameable place on it, and the fiction is allowed to touch one without the
# other.
_LATERAL_QUALIFIERS = frozenset({
    "left", "right", "other", "far", "near", "first", "second", "upper",
    "lower", "fore", "hind", "front", "back", "opposite", "free",
})


def _part_identity(part: str) -> tuple:
    """A part as (kind, instance): 'left hand' -> ('hand', 'left').

    The ledger keyed a contact on the part's raw text, so 'hand' and 'hand'
    were the same limb and 'waist' and 'side' were two different places on a
    body that only has one of them. Both readings are wrong, and the fix is not
    a synonym table -- it is noticing that an UNQUALIFIED part noun is a
    definite description. When the fiction says "her hand" twice about the same
    two bodies it means the hand doing the thing now; when it means the other
    one it says so, or says both in the same breath.

    So the instance is only what the fiction actually distinguished. Plurals
    fold into the singular kind ('hands' is both of them, which supersedes
    either), and a sub-part keeps its own kind.
    """
    text = re.sub(r"[^a-z0-9]+", " ", str(part or "").casefold()).strip()
    if not text:
        return "", ""
    words = text.split()
    instance = []
    while len(words) > 1 and words[0] in _LATERAL_QUALIFIERS:
        instance.append(words.pop(0))
    kind = " ".join(words)
    if _part_is_plural(kind):
        kind = kind[:-1]
    return kind, " ".join(instance)


def _same_appendage(left: str, right: str) -> bool:
    """Do two part KINDS name the same limb, one of them more precisely?

    'tail' and 'tail spade' are one tail. Measured live: a hold recorded
    `tail_spade -> calf` was re-asserted the next beat as `tail -> ankle` --
    the same spade, moved, renamed -- and the ledger carried both, so the
    character was told two tails were on her.

    Structural, not a vocabulary: a refinement REPEATS the limb's own word
    ('tail spade', 'tail tip'). 'thumb' does not contain 'hand', so a thumb and
    a hand stay two facts, which is correct -- they can be in two places.
    """
    left, right = str(left or "").strip(), str(right or "").strip()
    if not left or not right:
        return False
    if left == right:
        return True
    short, long = sorted((left, right), key=len)
    return " " not in short and short in long.split()


def canonical_region(part) -> str:
    """One spelling for one place on a body, for COMPARISON only.

    Every region comparison in the substance ledger was raw casefolded text,
    so `Intake_Ports` and `intake port` were two places and a re-spelling
    minted a second row on a body that has one. This is the single fold point
    those comparisons now share: fold on the way in, in one place, rather than
    asking every reader to remember a normalizer.

    It returns a comparison TOKEN and is never written back over what the
    Director wrote. Two reasons, and both matter: the fiction's own wording is
    better prose than a canonical stand-in ("oral cavity" is not an
    improvement on itself), and `_substance_id` hashes the region slots, so
    rewriting the stored text would re-key standing records and break the
    `{op:'remove', substance_id}` selectors the Director holds from earlier
    payloads.

    Deliberately built out of `_part_identity` and `_same_appendage` alone --
    the structural rule, no vocabulary. A synonym table for body parts is
    forbidden here for a measured reason (see AGENTS.md): `tail_spade` is a
    nameable place on a tail rather than `tail` blurred, and a table that
    folded the one would fold the other. That leaves purely lexical pairs
    unfolded; see `_same_region`.
    """
    kind, instance = _part_identity(part)
    if not kind:
        return ""
    return f"{instance} {kind}".strip() if instance else kind


def _same_region(left, right) -> bool:
    """Do two region names name the same place on one body?

    Canonical equality, then the structural refinement rule -- a refinement
    repeats the region's own word ('holding reservoir' is that reservoir), so
    two places the fiction really distinguished stay two.

    What this deliberately does NOT catch is a purely lexical synonym pair
    with no shared word: measured live (chat 69 ⎇49, turns 61-62), one cavity
    written `mouth` and then `oral cavity` stands as two rows and still will.
    Folding that needs a vocabulary, and the vocabulary is the thing that
    cannot tell a synonym from a sub-part.
    """
    left_canon, right_canon = canonical_region(left), canonical_region(right)
    if not left_canon or not right_canon:
        return False
    if left_canon == right_canon:
        return True
    left_kind, left_instance = _part_identity(left)
    right_kind, right_instance = _part_identity(right)
    if left_instance != right_instance:
        return False
    return _same_appendage(left_kind, right_kind)


def owned_region(scene: dict, subject, part) -> tuple:
    """A place on a body, as the pair that actually identifies it.

    A region name is not an identity. `mouth` names no place in a scene:
    Hinami's mouth is a place, Elyra's mouth is a different one, and a ledger
    that stores the bare noun has thrown away the half of the fact that tells
    them apart. Measured live (chat 69 ⎇49, turns 78-80), that is exactly what
    happened -- one body's cavity was recorded, rendered and delivered as the
    other's, to both minds at once.

    So this is the unit the ledgers compare and index on: `(who, where)`, the
    subject folded through `canonical_subject` and the region through
    `canonical_region`. Empty when either half is missing, because half a
    region identity is not a weaker identity -- it is a different kind of
    claim, and treating it as a match is how the confusion got in.

    A comparison TOKEN, exactly as `canonical_region` is: nothing is written
    back over what the Director wrote, and no stored record is re-keyed.
    """
    who = canonical_subject(scene, str(subject or "").strip())
    where = canonical_region(part)
    if not who or not where:
        return ()
    return (who.casefold(), where)


def same_owned_region(scene: dict, subject_a, part_a,
                      subject_b, part_b) -> bool:
    """Same place on the same body?

    The question every "same region?" comparison should have been asking. It
    is deliberately two questions and not one token equality: identity of the
    BODY goes through `same_subject` (which knows a display name and an entity
    id are one being), and identity of the PLACE through `_same_region` (which
    knows a refinement repeats the region's own word). Collapsing them into a
    single string compare loses one rule or the other.
    """
    if not same_subject(scene, subject_a, subject_b):
        return False
    return _same_region(part_a, part_b)


def _displaces(standing: dict, incoming: dict) -> bool:
    """Does `incoming` say the SAME part moved, rather than a second one?

    True only when both name the same pair of bodies, the same part kind, the
    same instance, and a different spot. The instance rule is deliberately
    asymmetric: a bare noun never displaces a qualified limb and a qualified
    one never displaces a bare one. The moment the Director has bothered to
    distinguish her left hand from her right, both records are protected --
    losing a distinction the fiction drew is worse than carrying a stale hold
    the ageing clock will retire anyway.
    """
    if standing.get("actor", "").casefold() != incoming.get("actor", "").casefold():
        return False
    if standing.get("target", "").casefold() != incoming.get("target", "").casefold():
        return False
    was_kind, was_instance = _part_identity(standing.get("actor_part"))
    now_kind, now_instance = _part_identity(incoming.get("actor_part"))
    return bool(now_kind) and was_instance == now_instance \
        and _same_appendage(was_kind, now_kind)

# A momentary contact is over the moment the story moves on, so it retires on
# the very next beat that says anything about contact at all -- one evidence
# beat, against the two a standing hold gets.
_CONTACT_MOMENTARY_STALE_BEATS = 1


def contact_is_momentary(contact) -> bool:
    """True when this contact's manner names an ACT rather than a state.

    The head word decides when the whole phrase does not match, following the
    `contact_manner_kind` precedent: a live ledger held `dripping fluid`, which
    is the act `dripping` with its object narrated into the slot, and an exact
    match read it as a durable hold.
    """
    if not isinstance(contact, dict):
        return False
    word = str(contact.get("manner") or "").strip().casefold()
    if word in _MOMENTARY_SET:
        return True
    head = re.split(r"[^\w]+", word, maxsplit=1)[0]
    return head in _MOMENTARY_SET


def _contact_text(value, limit=_MAX_CONTACT_PART):
    return str(value or "").strip()[:limit]


def _contact_key(contact):
    """Identity of a contact for dedup/removal: who, by what, on whom, where.
    `manner` is deliberately excluded -- a grip that becomes a caress is the
    same contact changing, not a second one."""
    return (
        _contact_text(contact.get("actor")).casefold(),
        _contact_text(contact.get("actor_part")).casefold(),
        _contact_text(contact.get("target")).casefold(),
        _contact_text(contact.get("target_part")).casefold(),
    )


def _mirror_key(key):
    """The same contact stated from the other side: pair and parts swapped."""
    actor, actor_part, target, target_part = key
    return (target, target_part, actor, actor_part)


def contact_id(contact) -> str:
    """Stable opaque identity for one physical contact.

    Contact is symmetric for identity even though an interior contact keeps a
    meaningful stored direction. Sorting the two owned endpoints gives every
    observer and stage the same handle. If an endpoint changes, the handle
    changes too, so dependent effects end instead of migrating silently.
    """
    if not isinstance(contact, dict):
        return ""
    left = (
        _contact_text(contact.get("actor"), 120).casefold(),
        canonical_region(contact.get("actor_part")),
    )
    right = (
        _contact_text(contact.get("target"), 120).casefold(),
        canonical_region(contact.get("target_part")),
    )
    # Whole-body contact legitimately leaves one or both part slots blank;
    # the two owners are still enough to identify the one deduplicated row.
    if not left[0] or not right[0]:
        return ""
    identity = "\x1f".join(
        part for endpoint in sorted((left, right)) for part in endpoint)
    return "contact:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def _flip(contact):
    """The same contact read from the other body's side, for displacement.

    Contact is symmetric, but the ledger stores a direction, so a hold recorded
    'Hinami's hand -> Elyndra's waist' and later re-asserted from Elyndra's
    side has to be recognised as the same hand before it can be moved.
    """
    return {
        "actor": contact.get("target", ""), "actor_part": contact.get("target_part", ""),
        "target": contact.get("actor", ""), "target_part": contact.get("actor_part", ""),
    }


# Envelopment verbs: the ACTOR is the enclosing side, so the enclosed part
# lives on the OTHER body. The ledger's interior direction is fixed the other
# way round -- `actor_part` is the part that is inside; the target encloses it
# (see contact_sensation/contact_phrase) -- so a record written from the
# enclosing side must be FOLDED onto that direction at write time, in the one
# place every contact passes through, rather than asking each reader to guess
# which side encloses. Measured live: an interior contact stood for eight beats
# as `cavity -> part, relation surface` and both parties were told "against"
# about a body fully enclosed; the mirror spelling `mouth -> part, engulfing,
# surface` stood two beats more.
_ENVELOPMENT_MANNERS = frozenset({
    "engulf", "engulfs", "engulfed", "engulfing",
    "envelop", "envelops", "enveloped", "enveloping",
    "swallow", "swallows", "swallowed", "swallowing",
})

# The cavity an enclosing part implies, keyed by `_part_identity` kind. Used to
# fill `target_interior` after the fold; a part with no entry supplies its own
# name, which is right for invented anatomy ("within the sheath"). Only true
# cavities belong here: a tongue or a finger ENTERS things far more often than
# it encloses them, and listing one would flip records that were already
# stated from the entering side (a live ledger's `tongue -> outer labia,
# interior` is correctly directed as written).
_ENCLOSING_PART_CAVITY = {
    "mouth": "mouth", "lip": "mouth", "throat": "throat",
    "vagina": "vagina", "pussy": "vagina",
    # A cavity named by its WALL or its CANAL is the same cavity. `_part_identity`
    # keeps them distinct kinds -- "vaginal walls" identifies as "vaginal wall",
    # not "vagina" -- which is right for a ledger (two spellings are two rows)
    # and wrong here, where the only question is "does this part enclose?".
    # Measured live (chat 71): `Elyra "vaginal walls" -> Hinami, target_interior
    # "vaginal canal", interior, clench` stood unflipped, and Elyra was told in
    # her own perception view that her vaginal walls registered Hinami's vaginal
    # canal enclosing them. A vagina inside a vagina, delivered to the mind that
    # owns one of them. The truth was the reverse: Hinami's hand was inside her.
    "vaginal wall": "vagina", "vaginal canal": "vagina",
    "vaginal walls": "vagina", "vaginal passage": "vagina",
    "anal canal": "anus", "rectal wall": "rectum",
    "throat wall": "throat",
    "anus": "anus", "rectum": "rectum",
}

# The cavities that cannot GRIP another body's part without enclosing it. A
# mouth or lips press against skin all the time -- a kiss on a neck is a
# surface fact -- so they fold only on an envelopment manner or an explicit
# interior relation. The same live interior contact that stood as `engulf,
# surface` also stood a beat as `cavity -> part, clench, surface`: a grasping
# manner, an enclosing organ, and the wrong topology.
_STRICT_CAVITY_KINDS = frozenset({"vagina", "pussy", "anus", "rectum",
                                  "throat",
                                  # Same cavity, named by its wall or canal.
                                  "vaginal wall", "vaginal walls",
                                  "vaginal canal", "vaginal passage",
                                  "anal canal", "rectal wall", "throat wall"})
_CAVITY_GRIP_MANNERS = frozenset({
    "clench", "clenches", "clenched", "clenching",
    "clamp", "clamps", "clamped", "clamping",
    "squeeze", "squeezes", "squeezed", "squeezing",
    "grip", "grips", "gripped", "gripping",
    "milk", "milks", "milked", "milking",
})


def _contained_inversion(scene, actor, target) -> bool:
    """Does `target` sit INSIDE `actor`, making an interior contact backwards?

    The part vocabularies above decide direction from the part noun alone, and
    a tongue is deliberately absent from `_ENCLOSING_PART_CAVITY` because it
    enters things far more often than it encloses them. That carve-out is
    right and has no way to see the one fact that settles the case anyway:
    a body cannot enclose the body it is itself inside.

    Measured live (chat 69 ⎇49, turns 78-80): `contained` recorded Hinami at
    scale 0.1 inside Elyra Voss while the contact ledger carried `Elyra Voss's
    tongue -> Hinami/body, target_interior mouth`. Both minds were then told
    the mouth was Hinami's -- she was gagged by a cavity that was not hers,
    and Elyra was told her tongue was inside the body she was holding in her
    mouth. The scene knew better in a ledger nothing here was reading.

    Read through `hiding_holders_of`, never `scene['contained']`: containment
    has two forms and the parented-interior-room form is invisible to a direct
    read. Deliberately asymmetric -- the inverse arrangement (a holder
    reaching into what it contains) is physically ordinary and must survive.
    """
    if not isinstance(scene, dict):
        return False
    actor = str(actor or "").strip()
    target = str(target or "").strip()
    if not actor or not target or same_subject(scene, actor, target):
        return False
    return any(same_subject(scene, holder, actor)
               for holder in hiding_holders_of(scene, target))


def _clean_contact(raw, scene=None):
    """A contact record, or None if it names nobody on one side."""
    if not isinstance(raw, dict):
        return None
    actor = _contact_text(raw.get("actor"), 120)
    target = _contact_text(raw.get("target"), 120)
    if not actor or not target:
        return None
    if actor.casefold() == target.casefold():
        return None  # a body is always in contact with itself; not a fact
    if not (_is_anatomical_part(raw.get("actor_part"))
            and _is_anatomical_part(raw.get("target_part"))):
        # A part slot holding matter, a sound, or a state is wrong where it is
        # written, and every downstream floor was built to survive it rather
        # than stop it (see _NON_ANATOMICAL_PART_WORDS). Refuse it here, in
        # the one place every contact passes through: matter that moved
        # between bodies is a substance record, and a reaction is not a
        # contact. Measured live: `juices -> balls, coat` stood two beats as a
        # contact between a fluid and a body.
        return None
    manner = _contact_text(raw.get("manner")).casefold() or "touch"
    detail = re.sub(r"[_\s]+", " ",
                    _contact_text(raw.get("detail"), _MAX_CONTACT_DETAIL)).strip()
    relation = _normalize_contact_relation(raw.get("relation"))
    if not relation:
        relation = "interior" if contact_manner_kind(manner) == "interior" \
            else "surface"
    motion = _normalize_contact_motion(raw.get("motion"))
    if not motion:
        motion = _contact_motion_from_text(manner, detail)
    try:
        unasserted = max(0, int(raw.get("unasserted") or 0))
    except (TypeError, ValueError):
        unasserted = 0
    actor_part = _contact_text(raw.get("actor_part"))
    target_part = _contact_text(raw.get("target_part"))
    target_interior = _contact_text(raw.get("target_interior")) \
        if relation == "interior" else ""

    # The envelopment fold (see _ENVELOPMENT_MANNERS above). Two spellings
    # arrive from the enclosing side: an envelopment verb in `manner`, or
    # `relation: interior` with the enclosing organ in the ACTOR slot ("lips
    # seal glans, interior" -- which, read under the fixed direction, puts
    # lips inside a glans). Both fold to the enclosed part as actor_part.
    head = re.split(r"[^\w]+", manner, maxsplit=1)[0]
    actor_kind = _part_identity(actor_part)[0]
    enveloping = manner in _ENVELOPMENT_MANNERS or head in _ENVELOPMENT_MANNERS
    if not enveloping and relation == "interior":
        enveloping = (
            actor_kind in _ENCLOSING_PART_CAVITY
            and _part_identity(target_part)[0] not in _ENCLOSING_PART_CAVITY
            and bool(target_part))
    if not enveloping and actor_kind in _STRICT_CAVITY_KINDS:
        enveloping = (manner in _CAVITY_GRIP_MANNERS
                      or head in _CAVITY_GRIP_MANNERS)
    # Containment outranks every part vocabulary above, because it is a fact
    # the scene already holds rather than an inference from a noun. It also
    # folds when the enclosed side named no part: the direction is known wrong
    # whatever the slots say, and a bare name renders correctly ("Hinami
    # remains within Elyra Voss's mouth") where the inversion never could.
    contained_inversion = (relation == "interior"
                           and _contained_inversion(scene, actor, target))
    if contained_inversion:
        enveloping = True
    if enveloping and actor_part and (target_part or contained_inversion):
        actor, target = target, actor
        actor_part, target_part = target_part, actor_part
        relation = "interior"
        if not target_interior:
            target_interior = _ENCLOSING_PART_CAVITY.get(
                _part_identity(target_part)[0], target_part)
        if target_part.casefold() == target_interior.casefold():
            # The enclosing organ IS the enclosure; naming it again as the
            # contact endpoint renders "within the cavity, maintaining
            # contact at the cavity".
            target_part = ""

    cleaned = {
        "actor": actor,
        "actor_part": actor_part,
        "target": target,
        "target_part": target_part,
        # For interior topology, this is the passage/chamber/material that
        # currently encloses actor_part. `target_part` stays the exact boundary
        # or endpoint being touched. Keeping the two facts separate prevents a
        # terminal surface from being rendered as though it were a container.
        "target_interior": target_interior,
        "manner": manner,
        # Contact topology and kinematics are independent. A part can be
        # inside another body while either still or moving; `manner` cannot
        # carry both facts without losing one of them.
        "relation": relation,
        "motion": motion,
        # What the parts alone cannot say: pressure, temperature, over or under
        # clothing. Excluded from the identity key exactly as `manner` is -- a
        # grip that becomes feather-light is the same contact changing.
        #
        # This field exists because its absence was CAUSING the second defect.
        # With nowhere structured to put "beneath her shift" or "feather
        # light", the Director wrote them into the entity's own `state`, where
        # nothing ages them and nothing prunes them, and they stood
        # contradicting the ledger for the rest of the story.
        "detail": detail,
        # Beats of contact talk since this was last asserted. Absent on an
        # incoming op (an assertion is by definition fresh) and on a scene
        # saved before ageing existed, both of which read as 0.
        "unasserted": unasserted,
    }
    cleaned["contact_id"] = contact_id(cleaned)
    return cleaned


def contacts_broken_by_scale_change(scene: dict, previous_scales) -> list:
    """Drop every contact involving a body that just changed size.

    A hold is a fact about two bodies at the sizes they were. Shrink the held
    person to a tenth and "his hand grips her wrist" is not a smaller version
    of itself -- the wrist is no longer where the hand is, and whether anything
    equivalent is still possible is a question only the Director can answer.
    So the engine cancels rather than rescales: the grip is released, and the
    Director re-establishes whatever the new geometry actually permits.

    This is the same discipline movement already follows -- a contact that the
    physical situation no longer supports does not survive on inertia -- and it
    is why a size change cannot leave a phantom grip behind.

    Returns the names whose contacts were cancelled, for the caller to report.
    """
    contacts = scene.get("contacts")
    if not isinstance(contacts, list) or not contacts:
        return []

    changed = scale_changed_names(previous_scales, scene.get("scales") or {})
    if not changed:
        return []

    kept = []
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        pair = {
            str(contact.get("actor") or "").strip().casefold(),
            str(contact.get("target") or "").strip().casefold(),
        }
        if pair & changed:
            continue
        kept.append(contact)

    scene["contacts"] = kept
    return sorted(changed)


def contacts_across_enclosure(scene: dict, report=None) -> list:
    """Retire a surface contact the scene's own enclosures deny.

    Sight has always answered this question -- `containment_conceals` says
    whether two bodies are on the same side of every closed thing -- and
    touch was never asked it. So an enclosure recorded in one ledger and a
    hold recorded in the other stood side by side, both delivered as live
    present sensation, with the hold's detail frozen at whatever beat last
    wrote it.

    THE ENCLOSURE IS ITSELF A CONTACT, which is why this cannot simply drop
    everything that crosses one. A WHOLE-BODY contact between a body and what
    encloses it IS that enclosure stated as touch -- the same whole-body/part
    distinction `derive_containment_from_contacts` turns on -- and it is the
    only channel an enclosed body has left, so it survives. So does any
    `interior` contact: interior is the relation an enclosure permits. What
    is denied is a named PART reaching the enclosed body's surface from
    outside the enclosure, the holder's own parts included -- a holder is not
    inside its own enclosure.

    Deliberately not conditional on the Director agreeing with itself: the
    measured beat both put a body inside another and re-asserted the surface
    holds that were true before it, and ageing cannot retire a row that was
    just asserted. Containment is the authoritative ledger (the ground
    `_contained_inversion` already defers on), so contact is the one that
    yields, and the report tells the Director what was read.

    Returns the dropped rows; appends one finished sentence per row to
    `report`, which is a list, as everything else here appends to it.
    """
    contacts = scene.get("contacts")
    if not isinstance(contacts, list) or not contacts:
        return []

    def _whole(part):
        folded = str(part or "").strip().casefold()
        return not folded or folded in _WHOLE_BODY_PARTS

    def _encloses(outer, inner):
        return any(same_subject(scene, holder, outer)
                   for holder in hiding_holders_of(scene, inner))

    kept, dropped = [], []
    for row in contacts:
        if not isinstance(row, dict):
            kept.append(row)
            continue
        actor, target = row.get("actor"), row.get("target")
        if str(row.get("relation") or "").strip().casefold() == "interior" \
                or not containment_conceals(scene, actor, target):
            kept.append(row)
            continue
        if _whole(row.get("actor_part")) and _whole(row.get("target_part")) \
                and (_encloses(actor, target) or _encloses(target, actor)):
            kept.append(row)
            continue
        dropped.append(row)
    if not dropped:
        return []
    scene["contacts"] = kept
    if report is not None:
        for row in dropped:
            report.append(
                f"contact {row.get('actor')} -> {row.get('target')} was "
                "dropped: an enclosure is between them, so a surface contact "
                "cannot stand. Reaching into an enclosure is relation "
                "'interior' with the cavity in target_interior.")
    return dropped


def normalize_scene_contacts(scene: dict) -> dict:
    """Contact hygiene, run at merge -- the sibling of normalize_scene_stations.

    Drops a contact naming someone with no position (they are not in the
    scene), and any contact between two people who are not in the SAME room:
    you cannot hold someone you are not standing next to. That single rule is
    what makes walking away clear contact deterministically, with no separate
    inferer and nothing for the Director to remember -- the stale record simply
    fails its membership test the moment a position changes.

    Deduped on (actor, actor_part, target, target_part) keeping the LAST
    occurrence, so re-asserting a contact updates its manner rather than
    stacking a second copy.

    A MIRROR -- the same pair with the parts swapped -- is one physical contact
    stated from the other side, and only one record survives it. Both bodies
    describing the same hold is precisely how the old per-entity shape produced
    two records that drifted, and legacy extraction can surface it too when
    each entity's state named the other.
    """
    contacts = scene.get("contacts")
    if not isinstance(contacts, list):
        if contacts is not None:
            scene["contacts"] = []
        return scene

    positions = scene.get("positions") or {}
    kept = {}
    for raw in contacts:
        contact = _clean_contact(raw, scene)
        if contact is None:
            continue
        actor_room = _ci_get(positions, contact["actor"])
        target_room = _ci_get(positions, contact["target"])
        if actor_room is None or target_room is None:
            continue
        if actor_room != target_room:
            continue
        key = _contact_key(contact)
        if _mirror_key(key) in kept:
            continue  # already recorded from the other side
        kept[key] = contact

    scene["contacts"] = list(kept.values())[-_MAX_CONTACTS:]
    return scene


def _contact_ops_are_evidence(ops) -> bool:
    """True when this beat's ops say anything usable about contact at all.

    The ageing rule below turns the Director's SILENCE about a contact into
    evidence that it ended, which is only sound on a beat where the Director
    spoke about contact and did not mention it. A beat with no ops (or only
    junk) is not evidence of anything: measured across a long live scene the
    Director routinely emits nothing for a beat, and ageing on those would
    retire the whole arrangement over a couple of quiet exchanges.
    """
    for raw in ops or []:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "add").strip().casefold()
        if op == "clear":
            return True
        if op == "remove":
            if (_contact_text(raw.get("actor"), 120)
                    and _contact_text(raw.get("target"), 120)):
                return True
            continue
        if _clean_contact(raw) is not None:
            return True
    return False


def apply_contact_ops(scene: dict, ops, *, _age=True, report=None) -> dict:
    """Apply state_diff.contact_ops to scene.contacts.

    add     -- upsert by (actor, actor_part, target, target_part). `relation`
               is surface|interior and `motion` is settled|moving; old ops
               derive both from manner/detail.
    cross   -- advance an established interior contact past its exact current
               `crossed_target_part`, recording the downstream
               `target_interior` and optional new `target_part`. The crossed
               boundary is transition evidence, not standing state.
    remove  -- drop matching contacts; parts omitted means "any contact
               between these two", so ending a hold does not require the
               Director to recall exactly which parts it recorded
    clear   -- with `actor`, every contact that person is part of (on either
               side); bare, the whole list

    Hygiene still runs afterwards, so an op naming someone in another room
    cannot smuggle in an impossible contact.

    AGEING. Position pruning (`normalize_scene_contacts`) ends a hold when
    someone walks away, and was the only retirement path there was -- so in a
    scene where nobody changes room, contact was append-only. Measured live:
    147 adds against 3 removes across one story, ending with fifteen
    simultaneous holds including one body's mouth recorded in five places, and
    single touches from four beats earlier still asserted as current. A
    perception stage reading the scene as present truth then narrates a
    long-finished act as though it were happening now, and a character
    answering that is behaving correctly on corrupted input.

    The signal needed to fix it was already in the Director's behaviour: it
    re-asserts a hold that is still true and simply stops mentioning one that
    ended. Nothing read it. So on every beat that says anything about contact
    (`_contact_ops_are_evidence`), each standing contact ages one beat, and one
    that goes `_CONTACT_STALE_BEATS` such beats without re-assertion retires.
    An `add` -- from either side, mirror included -- resets the count.

    This does NOT cap how many contacts may stand at once; simultaneity is the
    point of the ledger. It removes the ones that are no longer true.
    """
    if not isinstance(ops, list) or not ops:
        return scene

    contacts = scene.get("contacts")
    if not isinstance(contacts, list):
        contacts = []
    current = {_contact_key(c): c for c in
               (_clean_contact(r, scene) for r in contacts) if c is not None}
    # Keys this beat has already spoken for. A displacement may never eat one
    # of them: the Director naming two spots in one breath means two spots.
    asserted = set()
    # (old, new) pairs, so a caller can report what it read a re-description
    # AS -- a rename collapsed in silence teaches the model nothing.
    displaced = []

    # Age BEFORE applying, so this beat's own assertions land fresh on top and
    # a re-asserted hold never ages at all.
    # A cross depends on the contact it advances. Keep the pre-age snapshot so
    # the transition itself can refresh a contact that would otherwise retire
    # on this evidence beat.
    before_age = dict(current)
    if _age and _contact_ops_are_evidence(ops):
        aged = {}
        for key, contact in current.items():
            stale = int(contact.get("unasserted") or 0) + 1
            # An act is over as soon as the story moves on; a hold persists
            # until the Director stops naming it.
            limit = (_CONTACT_MOMENTARY_STALE_BEATS
                     if contact_is_momentary(contact) else _CONTACT_STALE_BEATS)
            if stale >= limit:
                continue  # unmentioned too long: it is over
            aged[key] = {**contact, "unasserted": stale}
        current = aged
    cross_sources = {
        key: contact for key, contact in before_age.items() if key not in current
    }

    for raw in ops:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "add").strip().casefold()

        if op == "clear":
            who = _contact_text(raw.get("actor"), 120).casefold()
            if not who:
                current = {}
                cross_sources = {}
                continue
            current = {
                key: c for key, c in current.items()
                if who not in (c["actor"].casefold(), c["target"].casefold())
            }
            cross_sources = {
                key: c for key, c in cross_sources.items()
                if who not in (c["actor"].casefold(), c["target"].casefold())
            }
            continue

        if op == "remove":
            actor = _contact_text(raw.get("actor"), 120).casefold()
            target = _contact_text(raw.get("target"), 120).casefold()
            actor_part = _contact_text(raw.get("actor_part")).casefold()
            target_part = _contact_text(raw.get("target_part")).casefold()
            if not actor or not target:
                continue
            def _survives_removal(c):
                pair = {c["actor"].casefold(), c["target"].casefold()}
                # Contact is physically symmetric, so a removal naming the two
                # in either order ends it.
                if pair != {actor, target}:
                    return True
                if actor_part and c["actor_part"].casefold() != actor_part:
                    return True
                if target_part and c["target_part"].casefold() != target_part:
                    return True
                return False

            current = {key: c for key, c in current.items()
                       if _survives_removal(c)}
            cross_sources = {key: c for key, c in cross_sources.items()
                             if _survives_removal(c)}
            continue

        if op == "cross":
            actor = _contact_text(raw.get("actor"), 120).casefold()
            target = _contact_text(raw.get("target"), 120).casefold()
            actor_part = _contact_text(raw.get("actor_part")).casefold()
            crossed = _contact_text(raw.get("crossed_target_part")).casefold()
            downstream = _contact_text(raw.get("target_interior"))
            candidates = []
            available = {**cross_sources, **current}
            for old_key, standing in available.items():
                if standing.get("relation") != "interior":
                    continue
                if standing.get("actor", "").casefold() != actor \
                        or standing.get("target", "").casefold() != target:
                    continue
                if actor_part and standing.get("actor_part", "").casefold() \
                        != actor_part:
                    continue
                if standing.get("target_part", "").casefold() != crossed:
                    continue
                candidates.append((old_key, standing))
            if not actor or not target or not crossed or not downstream \
                    or len(candidates) != 1:
                if report is not None:
                    report.append(
                        "ignored contact crossing: it must match exactly one "
                        "standing interior endpoint and name the downstream "
                        "target_interior")
                continue
            old_key, standing = candidates[0]
            advanced = {
                **standing,
                **raw,
                "op": "add",
                "actor": standing["actor"],
                "actor_part": standing["actor_part"],
                "target": standing["target"],
                "target_interior": downstream,
                # Omitting the new endpoint means no downstream point is
                # currently touched; never carry the crossed boundary forward.
                "target_part": _contact_text(raw.get("target_part")),
                "relation": "interior",
                "motion": "moving",
                "unasserted": 0,
            }
            contact = _clean_contact(advanced, scene)
            if contact is None:
                continue
            current.pop(old_key, None)
            cross_sources.pop(old_key, None)
            # Continue through ordinary add/upsert logic with the validated
            # downstream standing contact. `crossed_target_part` is omitted by
            # _clean_contact and therefore never becomes persistent state.
            raw = advanced
            op = "add"
        else:
            contact = _clean_contact(raw, scene)
            raw_actor = _contact_text(raw.get("actor"), 120)
            if contact is None and report is not None and raw_actor \
                    and _contact_text(raw.get("target"), 120):
                bad = [str(raw.get(slot)) for slot in
                       ("actor_part", "target_part")
                       if not _is_anatomical_part(raw.get(slot))]
                if bad:
                    # The refusal itself is silent (see _clean_contact); a
                    # rename collapsed in silence teaches the model nothing,
                    # and neither does a dropped op.
                    report.append(
                        "contact: dropped " + ", ".join(repr(b) for b in bad)
                        + " -- not a body part. Matter that moved between "
                        "bodies is a substance_ops record; a sound or a "
                        "reaction is not a contact.")
            elif contact is not None and report is not None and raw_actor \
                    and contact["actor"].casefold() != raw_actor.casefold():
                # The envelopment fold (see _clean_contact) reversed this
                # record onto the enclosed side. Say so, in the same voice as
                # the displacement notices, so the Director learns the
                # direction rather than re-asserting the folded spelling
                # every beat.
                #
                # Ask containment the same question `_clean_contact` asked,
                # rather than having it hand back a marker: a private field on
                # the record would ride into the stored scene, and the two
                # folds need different explanations. Only the containment one
                # can name a reason the Director can check against a ledger it
                # already has, so it does not borrow the envelopment wording.
                raw_target = _contact_text(raw.get("target"), 120)
                if _contained_inversion(scene, raw_actor, raw_target):
                    report.append(
                        f"contact: read {raw_actor}'s "
                        f"{_contact_text(raw.get('actor_part')) or 'body'} "
                        f"inside {raw_target} as {contact['actor']} inside "
                        f"{contact['target']}'s "
                        f"{contact['target_interior'] or 'body'} -- "
                        f"{contact['target']} encloses {contact['actor']}, so "
                        f"{raw_target} cannot be the enclosure here. End the "
                        "containment first if that is what changed.")
                else:
                    report.append(
                        f"contact: read {raw_actor}'s "
                        f"{_contact_text(raw.get('actor_part')) or 'body'} "
                        f"enveloping {contact['actor']}'s "
                        f"{contact['actor_part'] or 'body'} as "
                        f"{contact['actor']}'s {contact['actor_part'] or 'body'} "
                        f"inside {contact['target']}'s "
                        f"{contact['target_interior'] or 'body'} -- the actor of "
                        "an interior contact is the enclosed side.")

        if contact is not None:
            key = _contact_key(contact)
            mirror = _mirror_key(key)
            existing_key = key if key in current else (
                mirror if mirror in current else None)
            existing = current.get(existing_key) if existing_key else None
            # Interior topology cannot disappear through a bare re-description
            # of the same endpoints. A real withdrawal must remove the
            # interior relation before adding whatever surface contact remains.
            if existing and existing.get("relation") == "interior" \
                    and contact.get("relation") != "interior":
                contact["relation"] = "interior"
                if report is not None:
                    report.append(
                        f"preserved interior contact for {contact['actor']}'s "
                        f"{contact['actor_part']} and {contact['target']}'s "
                        f"{contact['target_part']}; end it explicitly before "
                        "changing it to surface contact")
            if existing and contact.get("relation") == "interior" \
                    and not contact.get("target_interior"):
                # An omitted enclosure is silence, not evidence that a durable
                # interior ceased to exist. This also lets old saves acquire
                # the field without losing it on the next concise reassertion.
                contact["target_interior"] = existing.get(
                    "target_interior", "")
            # A part that was somewhere else has MOVED, not multiplied. The
            # Director re-describes a standing hold rather than repeating it --
            # measured live, `thumb->ear` became `thumb->ear_base` and
            # `hand->waist` became `hand->side`, and the ledger read each
            # rename as a second limb until the staleness clock caught up. So
            # a fresh spot for the same part retires the old one.
            #
            # Not anything asserted THIS beat, though: two spots stated in one
            # breath are two spots, and the simultaneity they express is the
            # whole point of a ledger rather than a single "posture" field.
            for standing in [k for k in current if k not in asserted]:
                if _displaces(current[standing], contact) \
                        or _displaces(_flip(current[standing]), contact):
                    moved = current.pop(standing, None)
                    if moved is not None:
                        displaced.append((moved, contact))
            # Re-asserting from the other side updates the contact already on
            # record rather than creating its twin.
            if mirror in current and key not in current:
                if contact.get("relation") == "interior" \
                        and current[mirror].get("relation") != "interior":
                    # Interior direction has meaning: the actor's part is the
                    # enclosed one. A surface hold re-asserted as interior
                    # from the other side must adopt the interior record's
                    # OWN direction -- grafting `interior` onto the reversed
                    # pair puts the enclosing organ inside the part it
                    # encloses (measured: `cavity -> part, surface` updated
                    # in place by `part -> cavity, interior` would have read
                    # as the cavity moving within the part).
                    current.pop(mirror, None)
                    current[key] = contact
                    asserted.add(key)
                    continue
                # Re-assertion from the other side is still re-assertion: the
                # manner updates AND the staleness clock resets.
                current[mirror] = {**current[mirror],
                                   "manner": contact["manner"],
                                   "relation": contact["relation"],
                                   "motion": contact["motion"],
                                   # Interior direction has meaning. A mirror
                                   # reassertion may update motion/manner, but
                                   # its target-side enclosure is not the
                                   # stored relation's target-side enclosure.
                                   "target_interior": current[mirror].get(
                                       "target_interior", ""),
                                   "detail": contact["detail"] or current[mirror].get("detail", ""),
                                   "unasserted": 0}
                asserted.add(mirror)
            else:
                current[key] = contact
                asserted.add(key)

    scene["contacts"] = list(current.values())[-_MAX_CONTACTS:]
    # Out of band, never onto the scene: the saved document carries world
    # state and nothing else, and a `_`-prefixed scratch key is exactly what
    # `test_nothing_is_stashed_in_the_saved_scene` exists to refuse.
    if report is not None:
        report.extend(
            (f"{a['actor']}'s {a['actor_part']} on {a['target']}'s "
             f"{a['target_part']}",
             f"{b['actor']}'s {b['actor_part']} on {b['target']}'s "
             f"{b['target_part']}")
            for a, b in displaced)
    return scene


def contacts_of(scene: dict, name: str) -> list:
    """Every contact `name` is part of, on either side.

    The reader that did not exist before: "what is touching Hinami" was only
    answerable by re-reading a prose paragraph and hoping.
    """
    target = str(name or "").strip().casefold()
    if not target:
        return []
    out = []
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        if target in (str(contact.get("actor") or "").strip().casefold(),
                      str(contact.get("target") or "").strip().casefold()):
            out.append(contact)
    return out


# A contact whose manner places one part WITHIN another rather than against its
# surface. The distinction is not decorative: an interior contact is felt by the
# enclosing party as internal state, which is the interoceptive channel, while a
# surface contact arrives at the skin, which is touch. Reading the second as the
# first hands a perceiver a body sense they do not have; reading the first as
# the second loses the only channel that carries it.
CONTACT_INTERIOR_MANNERS = frozenset({
    "penetrate", "penetrating", "penetrated", "inside", "within", "insert",
    "inserted", "inserting", "impale", "impaled", "sheathe", "sheathed",
    "lodge", "lodged", "embed", "embedded", "buried", "burrow", "burrowed",
    "pierce", "pierced", "piercing", "enter", "entered", "entering",
})

# A contact whose manner carries MOTION across the contact surface. A moving
# contact delivers friction and changing pressure; a settled one delivers steady
# pressure and shared warmth. Both are continuous, and neither is an event.
CONTACT_MOVING_MANNERS = frozenset({
    "rub", "rubbing", "stroke", "stroking", "swirl", "swirling", "circle",
    "circling", "grind", "grinding", "slide", "sliding", "thrust", "thrusting",
    "trace", "tracing", "drag", "dragging", "work", "working", "roll",
    "rolling", "pump", "pumping", "caress", "caressing", "brush", "brushing",
    "graze", "grazing", "knead", "kneading", "ghost", "ghosting",
    "digging", "scratch", "scratching", "tickle", "flick",
    "withdraw", "withdrawing", "withdrawn", "rock", "rocking",
})

_INTERIOR_MOVING_MANNERS = frozenset({
    "penetrate", "penetrating", "inserting", "insertion", "impale",
    "sheathe", "sheathing", "embed", "embedding", "burrow", "burrowing",
    "pierce", "piercing", "enter", "entering",
})


def _normalize_contact_relation(value) -> str:
    word = str(value or "").strip().casefold()
    return word if word in ("surface", "interior") else ""


def _normalize_contact_motion(value) -> str:
    word = str(value or "").strip().casefold()
    return word if word in ("settled", "moving") else ""


def _contact_motion_from_text(manner, detail="") -> str:
    """Backward-compatible kinematics for contacts saved before `motion`."""
    words = set(re.findall(
        r"[a-z]+", f"{str(manner or '').casefold()} {str(detail or '').casefold()}"))
    if words & (CONTACT_MOVING_MANNERS | _INTERIOR_MOVING_MANNERS):
        return "moving"
    return "settled"

# (relation phrase, qualities) per legacy manner kind. An interior contact is NOT symmetric:
# the enclosing party feels something within them, the entering party feels
# something closed around them, and rendering either side with the other's
# phrasing describes a body the perceiver does not have.
# Words that name an act, a sound, or a state rather than a piece of anatomy.
# The Director periodically fills a contact's part slots with one -- a live
# ledger holds `actor_part: "physical reaction"` against `target_part:
# "laughter"` -- and a renderer that trusts the slot produces "your physical
# reaction registers her laughter against it", which is not a sensation and not
# a sentence anybody should read.
#
# `_clean_contact` now refuses a non-part at write time, which is the fix the
# paragraph above asked for; this remains the render floor for records written
# before that refusal existed. The substance words are in the same list for
# the same reason: matter is not a place on a body, and a fluid recorded as a
# contact's part (`juices -> balls, coat`, live for two beats) belongs in the
# substance ledger, which is built to carry exactly that.
_NON_ANATOMICAL_PART_WORDS = frozenset({
    "reaction", "reactions", "response", "responses", "behaviour", "behavior",
    "laughter", "laugh", "moan", "moans", "cry", "cries", "sound", "sounds",
    "noise", "expression", "expressions", "demeanor", "demeanour", "presence",
    "aura", "energy", "emotion", "emotions", "feeling", "feelings", "mood",
    "attention", "gaze", "stare", "glance", "state", "status", "posture",
    "pleasure", "arousal", "climax", "orgasm", "movement", "motion", "action",
    "act", "acts", "self", "body language", "attitude", "intent", "intention",
    "juice", "juices", "fluid", "fluids", "cum", "semen", "seed", "ejaculate",
    "saliva", "sweat", "slick", "wetness", "precum", "pre-cum", "milk",
    "blood",
})


def _is_anatomical_part(part) -> bool:
    """Could this string name a place ON a body?

    Permissive by design -- anatomy is open-ended and every story invents some
    -- so this rejects only what is affirmatively NOT a part.
    """
    words = str(part or "").replace("_", " ").strip().casefold()
    if not words:
        return True  # No part named is a whole-body contact, which is valid.
    if words in _NON_ANATOMICAL_PART_WORDS:
        return False
    return not any(w in _NON_ANATOMICAL_PART_WORDS for w in words.split())


_SENSATION_FORMS = {
    ("moving", "either"): ("against it",
                           "shifting pressure, movement and friction"),
    ("settled", "either"): ("against it",
                            "steady pressure, weight and shared warmth"),
}


def contact_manner_kind(manner) -> str:
    """`interior`, `moving`, or `settled` for one contact manner.

    Falls through to `settled` on an unknown manner, which is the conservative
    reading: an unrecognised word describes a contact that is simply THERE, and
    claiming motion or interiority the record does not state would be inventing
    physical fact rather than reporting it.
    """
    word = str(manner or "").strip().casefold()
    if not word:
        return "settled"
    head = re.split(r"[^\w]+", word, maxsplit=1)[0]
    for candidate in (word, head):
        if candidate in CONTACT_INTERIOR_MANNERS:
            return "interior"
        if candidate in CONTACT_MOVING_MANNERS:
            return "moving"
    return "settled"


def contact_relation(contact) -> str:
    """Surface or interior topology, with legacy `manner` fallback."""
    if not isinstance(contact, dict):
        contact = {"manner": contact}
    explicit = _normalize_contact_relation(contact.get("relation"))
    if explicit:
        return explicit
    return "interior" if contact_manner_kind(contact.get("manner")) == "interior" \
        else "surface"


def contact_motion(contact) -> str:
    """Settled or moving kinematics, independent of contact topology."""
    if not isinstance(contact, dict):
        contact = {"manner": contact}
    explicit = _normalize_contact_motion(contact.get("motion"))
    if explicit:
        return explicit
    return _contact_motion_from_text(
        contact.get("manner"), contact.get("detail"))
