# spatial_contact_migration.py
"""Converting contact prose the Director wrote into entity `state` into real
contact records."""

import re

from language_runtime import fold_words
from story.character_schema import fold_identity_key
from world.spatial_contacts import (_MAX_CONTACT_DETAIL, _MAX_CONTACT_PART,
                              _clean_contact, _part_identity, _same_appendage,
                              apply_contact_ops, contacts_of)
from world.spatial_identity import _ci_get


# ---- migrating contact out of entity state --------------------------------
# Before contacts existed, the Director recorded contact inside an entity's own
# `state`: `target` + `proximity` in the documented shape, and in practice a
# drift of invented keys naming the other body -- `leaning_against: "tamamo"`,
# `tails_wrapped_around: "Tamamo"`, `squished_against: "tamamo_side"`. Those
# assertions are real physical facts written in the wrong place, where nothing
# prunes them when the two walk apart.
#
# They are converted to contacts and REMOVED from the state, so exactly one
# record of a contact exists. Conversion is deliberately conservative: only a
# key whose NAME carries a contact verb, whose VALUE names a co-located person,
# converts. Adjacency words ("beside", "alongside") are not contact and are left
# untouched -- inventing a hold is worse than missing one, because a contact
# becomes ground truth the narrator is told.
#
# The free-text `description` paragraph is NOT parsed. Regex over prose would
# manufacture body parts and holds that were never asserted; it stays as the
# descriptive text it is, and the Director is told to stop putting contact in it.

# Never touched: the engine reads these structurally (movement, portals,
# perception's own deterministic backstop).
_PROTECTED_STATE_KEYS = frozenset({
    "transit", "link", "phase", "hatch", "destination_room", "route_room",
    "eta_seconds", "posture", "activity", "held_items", "zone", "description",
    "proximity", "target", "targets", "kind", "name",
})

# key-name fragment -> manner. Ordered: the first match wins, so "wrapped"
# beats a bare "on".
_CONTACT_KEY_MANNERS = (
    ("coil", "coil"), ("curl", "coil"), ("wrap", "wrap"), ("entwin", "wrap"),
    ("caress", "caress"),
    ("straddl", "straddle"), ("astride", "straddle"), ("mount", "straddle"),
    ("pin", "pin"), ("carry", "carry"), ("carried", "carry"),
    ("support", "support"), ("kiss", "kiss"), ("bit", "bite"),
    ("grip", "grip"), ("grasp", "grip"), ("clutch", "grip"),
    ("clench", "grip"), ("hold", "hold"), ("held", "hold"),
    ("embrac", "hold"), ("hug", "hold"), ("cling", "hold"),
    ("squish", "press"), ("press", "press"), ("flush", "press"),
    ("lean", "lean"), ("rest", "rest"), ("touch", "touch"),
    ("contact", "touch"), ("against", "press"),
)
# `_on` WAS HERE, and it is a preposition, not a contact verb: the module's
# own rule converts "a key whose NAME carries a contact verb". Measured (audit
# world_spatial_structure_light F3, 2026-11-01): `eyes_on: Hinami` became
# Elyra's eyes TOUCHING Hinami and `focus_on` a touch with the part 'focus'.
# A key whose only contact word is "on" now stays the state it was written as
# -- the conservative direction this module states: inventing a hold is worse
# than missing one.

#: What may follow a contact verb's stem inside ONE word of a key or a value:
#: the English inflections of that verb ("pinned", "wrapping", "kisses",
#: "embraced"), a doubled final consonant before -ed/-ing included. A closed
#: grammatical class, not a vocabulary: it is what stops a stem matching
#: INSIDE another word -- "expression" was a press, "interest" a rest,
#: "threshold" a hold, "spine" a pin and "pink" a pin (F3).
_INFLECTIONS = ("", "e", "s", "es", "d", "ed", "ing")

#: The token that makes a key PASSIVE: `held_by: Hinami` says Hinami holds
#: the thing, and lifting it the way an active key lifts reversed the act --
#: "the lantern holds Hinami" (F3). Refused; the key stays.
_PASSIVE_MARK = "by"


def _verb_form(token, fragment) -> bool:
    """Is this one word a form of the contact verb whose stem is `fragment`?"""
    if not token.startswith(fragment):
        return False
    tail = token[len(fragment):]
    if tail in _INFLECTIONS:
        return True
    # grip -> gripped, hug -> hugging, pin -> pinned
    return len(tail) >= 3 and tail[0] == fragment[-1] \
        and tail[1:] in ("ed", "ing")


def _key_manner(key):
    """`(manner, index of the verb word)` a state key's NAME asserts, or
    `(None, -1)`. Whole words of the key, in the table's order."""
    words = fold_words(key)
    for fragment, mapped in _CONTACT_KEY_MANNERS:
        for index, word in enumerate(words):
            if _verb_form(word, fragment):
                return mapped, index
    return None, -1

# `proximity` values that assert actual contact rather than mere nearness.
_CONTACT_PROXIMITIES = (
    "press", "contact", "touch", "flush", "against", "entwin", "on_top",
    "straddl", "atop",
)


def _manner_from_fragment(text):
    low = str(text or "").casefold()
    for fragment, manner in _CONTACT_KEY_MANNERS:
        if fragment in low:
            return manner
    return None


def _part_from_key(key, manner_fragment):
    """The body part a legacy key names, if any: `tails_wrapped_around` -> the
    part is 'tails'. Only the segment BEFORE the contact verb counts."""
    low = str(key or "").casefold()
    index = low.find(manner_fragment)
    if index <= 0:
        return ""
    return low[:index].strip("_ ").replace("_", " ").strip()


def contacts_from_entity_state(scene: dict) -> dict:
    """Lift contact asserted inside entity `state` into scene.contacts.

    Converted keys are removed from the state, so one contact has exactly one
    record. Runs at merge, which also backfills a save written before contacts
    existed: the assertions become real contacts and then obey the same
    positional hygiene as everything else.
    """
    entities = scene.get("entities")
    if not isinstance(entities, dict):
        return scene
    positions = scene.get("positions") or {}
    if not positions:
        return scene

    # Who can be a contact partner: anyone (or anything) with a position,
    # matched loosely -- these values are model-written, so "tamamo" must find
    # "Tamamo". A value may also carry the part it touches: "tamamo_side" is
    # Tamamo's side, an observed shape. Returns (partner, target_part).
    normalized_positions = [
        (name, fold_identity_key(name))
        for name in positions
    ]

    def _resolve(value):
        text = fold_identity_key(value)
        if not text:
            return None, ""
        for name, slug in normalized_positions:
            if slug and slug == text:
                return name, ""
        # `<person><part>` -- longest name first so "tamamo" cannot win over a
        # longer name that also starts with it.
        for name, slug in sorted(normalized_positions,
                                 key=lambda item: -len(item[1])):
            if slug and text.startswith(slug) and len(text) > len(slug):
                remainder = " ".join(fold_words(value))
                # Drop the name's own words, keep what is left as the part.
                for word in fold_words(name):
                    if word:
                        remainder = remainder.replace(word, " ", 1)
                part = " ".join(remainder.split())[:_MAX_CONTACT_PART]
                if part.startswith("s "):     # "tamamo's side"
                    part = part[2:].strip()
                return name, part
        return None, ""

    derived = []
    for eid, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        state = entity.get("state")
        if not isinstance(state, dict) or not state:
            continue
        actor = str(entity.get("name") or eid).strip()
        if not actor or _ci_get(positions, actor) is None:
            continue

        # The documented old shape: one whole-body target plus a proximity
        # word. Only a proximity that means CONTACT converts -- "close_on_bed"
        # is nearness, and stations already model that.
        proximity = str(state.get("proximity") or "").casefold()
        target_name, target_part = _resolve(state.get("target"))
        if target_name and any(p in proximity for p in _CONTACT_PROXIMITIES):
            derived.append({
                "actor": actor, "actor_part": "", "target": target_name,
                "target_part": target_part,
                "manner": _manner_from_fragment(proximity) or "press",
            })
            # This legacy pair asserted one contact jointly. Once lifted, remove
            # both halves just as the invented-key path below removes its source:
            # leaving them behind would re-create a pruned/removed contact on a
            # later merge as soon as the two bodies shared a room again.
            state.pop("target", None)
            state.pop("proximity", None)

        # The invented keys: a contact verb in the NAME, a person in the VALUE.
        for key in list(state.keys()):
            if key in _PROTECTED_STATE_KEYS:
                continue
            value = state.get(key)
            if not isinstance(value, str):
                continue
            partner, partner_part = _resolve(value)
            if partner is None or partner == actor:
                continue
            words = fold_words(key)
            if _PASSIVE_MARK in words:
                continue  # `held_by`: the act runs the other way; not lifted
            manner, index = _key_manner(key)
            if manner is None:
                continue  # not a contact assertion: leave it exactly as it is
            record = {
                "actor": actor,
                "actor_part": " ".join(words[:index])[:_MAX_CONTACT_PART],
                "target": partner, "target_part": partner_part,
                "manner": manner,
            }
            # POPPED ONLY WHEN THE LEDGER WILL TAKE IT: a record
            # `apply_contact_ops` refuses (a part that is no part of a body)
            # used to cost the state key anyway, so the fact was simply lost.
            if _clean_contact(dict(record, op="add"), scene) is None:
                continue
            derived.append(record)
            state.pop(key, None)

        # Pattern B: the verb is in the VALUE, and the key names the part.
        # Every contact assertion in the measured story took this shape and
        # evaded both tests above --
        #   "hand_position": "beneath_Hinami's_shift_caressing_bare_side"
        #   "tail_spade":    "curled_around_Hinami's_ankle"
        #   "lips":          "trailing_kisses_along_Hinami's_jaw"
        # -- so all three stood unaged and unprunable, contradicting the real
        # ledger for the rest of the scene. The gate stays conservative in the
        # way that matters: still a named partner AND a contact verb, still no
        # parsing of the free-text `description` paragraph.
        for key, value in list(state.items()):
            if key in _PROTECTED_STATE_KEYS or not isinstance(value, str):
                continue
            lifted = _lift_valued_contact(actor, key, value, positions)
            if lifted is not None and _clean_contact(
                    dict(lifted, op="add"), scene) is not None:
                derived.append(lifted)
                state.pop(key, None)

    if derived:
        # Through the same door an op comes in by, so a lifted assertion obeys
        # the displacement rule too -- otherwise lifting a hold the ledger
        # already records under a different part noun would ADD the very
        # duplicate this whole change exists to stop. Ageing is suppressed:
        # this is a migration running at merge, not a beat of story.
        scene = apply_contact_ops(
            scene, [dict(record, op="add") for record in derived], _age=False)

    # Pattern C: a relational key naming NO partner, contradicted by a contact
    # that does. "lips_distance": "two_inches_of_visible_space" cannot lift --
    # there is nobody in it -- and it sat asserting a gap for four beats while
    # the ledger said the mouths were touching. When the aged, authoritative
    # record already speaks for that part, the unaged twin goes.
    _drop_contradicted_state(scene)
    return scene


# Key names that describe a part's relation to something else rather than the
# body's own doing. Only these are eligible to be dropped as a stale twin --
# "hand_position": "clenched_at_side" names no partner and describes only this
# body, so it survives unless a real contact speaks for that hand.
_RELATIONAL_STATE_SUFFIXES = ("_touch", "_contact", "_grip", "_hold",
                              "_distance", "_gap", "_position", "_placement")

# A contact verb in a VALUE means contact only if what follows is not a
# direction: "leaning_over_Hinami" is where she is, not what she is touching,
# and stations are what model that.
_DIRECTION_AFTER_VERB = ("over", "toward", "towards", "at", "into", "in",
                         "down", "up", "close", "closer", "forward", "near",
                         "beside", "alongside", "past", "away")


def _lift_valued_contact(actor, key, value, positions):
    """A contact asserted as `<part key>: "<verb> ... <person> ... <part>"`.

    Returns a contact record, or None when this is not one. The leftover words
    become `detail`, which is the point: "beneath her shift", "feather light"
    is authored physical detail, and deleting the state key without keeping it
    would trade a stale fact for a lost one.
    """
    text = str(value or "")
    words = fold_words(text)
    partner = None
    for name in positions:
        slug = fold_identity_key(name)
        if slug and slug in [w for w in words if w]:
            partner = str(name)
            break
    if partner is None or partner.strip().casefold() == str(actor).strip().casefold():
        return None

    manner = index = None
    for fragment, mapped in _CONTACT_KEY_MANNERS:
        for position, word in enumerate(words):
            # A form of the verb, never a word that merely starts with its
            # stem ("pink" is not "pin", F3).
            if _verb_form(word, fragment):
                nxt = words[position + 1] if position + 1 < len(words) else ""
                if nxt in _DIRECTION_AFTER_VERB:
                    continue      # a bearing, not a hold
                if nxt == _PASSIVE_MARK:
                    continue      # "pinned_by_Hinami": the act runs the other way
                manner, index = mapped, position
                break
        if manner:
            break
    if manner is None:
        return None

    # The part this key names, minus the relational suffix that made it a key.
    part = str(key).casefold()
    for suffix in _RELATIONAL_STATE_SUFFIXES:
        if part.endswith(suffix):
            part = part[:-len(suffix)]
            break
    part = " ".join(fold_words(part))

    # What is left after the verb, the partner's own name and the joining
    # words: the far part if it reads like one, everything else as detail.
    drop = set(fold_words(partner)) | {"s", ""} \
        | set(_DIRECTION_AFTER_VERB) | {"the", "a", "an", "her", "his", "their",
                                        "its", "on", "along", "against", "and",
                                        "around", "of", "to", "with"}
    tail = [w for w in words[index + 1:] if w and w not in drop]
    target_part = tail[-1] if tail else ""
    detail = " ".join([w for w in words[:index] if w and w not in drop]
                      + tail[:-1])
    return {
        "actor": str(actor), "actor_part": part[:_MAX_CONTACT_PART],
        "target": partner, "target_part": target_part[:_MAX_CONTACT_PART],
        "manner": manner, "detail": detail[:_MAX_CONTACT_DETAIL],
    }


def _drop_contradicted_state(scene):
    """Retire a relational state key the contact ledger already speaks for.

    The ledger ages and prunes; entity state does neither. So where both
    describe the same part of the same body, the ledger is the record and the
    state copy is its unaged twin -- and an unaged twin is exactly how a beat
    that ended four beats ago goes on being narrated as present.

    Only relational keys, and only where a standing contact names that part.
    A key nothing speaks for is left alone: dropping a fact nobody contradicts
    would be inventing an absence.
    """
    entities = scene.get("entities")
    if not isinstance(entities, dict):
        return scene
    for eid, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        state = entity.get("state")
        if not isinstance(state, dict) or not state:
            continue
        actor = str(entity.get("name") or eid).strip()
        held = [_part_identity(c.get("actor_part"))[0]
                for c in contacts_of(scene, actor)
                if str(c.get("actor") or "").strip().casefold() == actor.casefold()]
        if not held:
            continue
        for key in list(state.keys()):
            if key in _PROTECTED_STATE_KEYS or not isinstance(state.get(key), str):
                continue
            low = str(key).casefold()
            suffix = next((s for s in _RELATIONAL_STATE_SUFFIXES
                           if low.endswith(s)), None)
            if not suffix:
                continue
            kind, _ = _part_identity(low[:-len(suffix)])
            if kind and any(_same_appendage(kind, k) for k in held):
                state.pop(key, None)
    return scene
