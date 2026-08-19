# character_schema.py
"""Versioned, context-agnostic character and persona schemas."""

from __future__ import annotations

import copy
import functools
import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field, validator

from story import attire
from llm.schemas import coerce_to_declared

_PYDANTIC_V2 = hasattr(BaseModel, "model_validate")
if _PYDANTIC_V2:
    from pydantic import field_validator

CHARACTER_SCHEMA = "fiction-engine.character"
CHARACTER_VERSION = 4
PERSONA_SCHEMA = "fiction-engine.persona"
PERSONA_VERSION = 3


def _profile_str_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    return [str(item).strip() for item in value if str(item or "").strip()]


def _as_profile_list(value, key_slot=None, model=None, value_slot=""):
    """A list of profiles, whatever spelling arrived.

    One entry is accepted as itself. A MAP keyed by the profile's own name
    -- `{"freeze": {"trigger": "threat"}}` -- is expanded, with the key
    carried into `key_slot` when the entry left that slot empty, because the
    key IS the name there. Anything that is not a sequence at all -- a bare
    number, a flag -- is not a list of profiles and is dropped: iterating it
    raises `TypeError`, and the two majors disagree about what that becomes.
    Pydantic 1 rewrapped a validator's `TypeError` as a `ValidationError`;
    Pydantic 2 rewraps only `ValueError` and `AssertionError`, so the same
    sheet raises a bare `TypeError` straight past every caller that catches
    the latter.

    The map case is not new tolerance so much as recovered tolerance: the
    old code iterated a dict and got its KEYS, so `{"freeze": {...},
    "flee": {...}}` did produce two named strategies -- and threw away
    everything under them. It also iterated a bare STRING, so a single
    strategy spelled `"freeze"` became six strategies named `f`, `r`, `e`,
    `e`, `z`, `e`.

    A map to BARE NUMBERS -- `{"wary": 0.7}` -- is the same map written the
    shortest way, and it used to be the one spelling that lost the name:
    expansion required every value to be a dict, so this fell through to the
    single-profile branch and became one anonymous profile carrying `wary`
    as a stray key. The sheet then read as populated and named nobody, which
    is why it survived so long. The discriminator is whether the map's KEYS
    are the profile's own fields, taken from `model`, rather than whether its
    values happen to be scalars -- `{"name": "wary", "strength": 0.7}` is one
    trait, not two traits called `name` and `strength`. The number lands in
    `value_slot`, the profile's one magnitude.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        if value and _is_profile_map(value, model):
            expanded = []
            for key, item in value.items():
                if not isinstance(item, dict):
                    item = {value_slot: item} if value_slot else {}
                else:
                    item = dict(item)
                if key_slot and not item.get(key_slot):
                    item[key_slot] = key
                expanded.append(item)
            return expanded
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _is_profile_map(value, model=None):
    """True when this dict is keyed by profile NAMES rather than field names.

    Every value being a dict settles it on its own -- no profile has a field
    whose value is a profile. Otherwise the keys decide: a map that names
    none of the model's fields is not a profile written out, so its keys are
    names. Without a `model` only the all-dict case is recognised, which is
    exactly the behaviour that shipped.
    """
    if all(isinstance(item, dict) for item in value.values()):
        return True
    if model is None:
        return False
    from llm.schemas import _fields
    if set(value) & set(_fields(model) or ()):
        return False
    return all(isinstance(item, (int, float)) and not isinstance(item, bool)
               or isinstance(item, dict)
               for item in value.values())


def _profile_float(value, default=0.5, low=0.0, high=1.0):
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if result != result:
        result = default
    return max(low, min(high, result))


class _PsychologyModel(BaseModel):
    class Config:
        extra = "allow"

    # A number where prose was declared. `_normalize_psychology` validates
    # with no try/except and is reached from
    # `normalize_character_data`, so an authored `"expression": 3` -- which
    # Pydantic 1 quietly read as `"3"` -- is an uncaught ValidationError on
    # Pydantic 2, on the read path of every character accessor. The
    # coercion itself lives in `schemas.py`, which already owns both "what
    # did this field declare" and "what did v1 do with it".
    if _PYDANTIC_V2:
        @field_validator("*", mode="before")
        @classmethod
        def _coerce_number_into_prose(cls, value, info):
            return coerce_to_declared(cls, info.field_name, value)
    else:
        @validator("*", pre=True, allow_reuse=True)
        def _coerce_number_into_prose(cls, value, field):
            return coerce_to_declared(cls, field.name, value)


class TraitProfile(_PsychologyModel):
    name: str = ""
    strength: float = 0.5
    expression: str = ""
    activation_cues: list[str] = Field(default_factory=list)
    inhibited_by: list[str] = Field(default_factory=list)

    _strength = validator("strength", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_float(value)
    )
    _lists = validator("activation_cues", "inhibited_by", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_str_list(value)
    )


class ValueProfile(_PsychologyModel):
    name: str = ""
    priority: float = 0.5
    expression: str = ""
    conflicts_with: list[str] = Field(default_factory=list)

    _priority = validator("priority", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_float(value)
    )
    _conflicts = validator("conflicts_with", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_str_list(value)
    )


class BeliefProfile(_PsychologyModel):
    belief: str = ""
    confidence: float = 0.5
    protected: bool = False
    emotional_charge: float = 0.0
    source: str = ""

    _confidence = validator("confidence", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_float(value)
    )
    _charge = validator("emotional_charge", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_float(value, default=0.0, low=-1.0, high=1.0)
    )


class CopingStrategyProfile(_PsychologyModel):
    name: str = ""
    trigger: str = ""
    response: str = ""
    effectiveness: float = 0.5
    costs: str = ""

    _effectiveness = validator("effectiveness", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_float(value)
    )


class AssociationProfile(_PsychologyModel):
    cue: str = ""
    appraisal_bias: str = ""
    response_tendency: str = ""
    strength: float = 0.5
    generalization_tags: list[str] = Field(default_factory=list)

    _strength = validator("strength", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_float(value)
    )
    _tags = validator("generalization_tags", pre=True, allow_reuse=True)(
        lambda cls, value: _profile_str_list(value)
    )


class PsychologyProfile(_PsychologyModel):
    drive: dict = Field(default_factory=lambda: {
        "essence": "", "expression": "", "taboo": "",
    })
    traits: list[TraitProfile] = Field(default_factory=list)
    values: list[ValueProfile] = Field(default_factory=list)
    self_model: dict = Field(default_factory=lambda: {
        "summary": "", "protected_beliefs": [], "pride_triggers": [],
        "shame_triggers": [], "beliefs": [],
    })
    coping: dict = Field(default_factory=lambda: {
        "under_stress": [], "default_conflict_style": "", "strategies": [],
        "recovery_supports": [],
    })
    stress_profile: dict = Field(default_factory=lambda: {
        "baseline_reactivity": 0.5, "recovery_rate": 0.5,
        "overload_threshold": 0.8, "attentional_style": "",
        "somatic_signs": [],
    })
    learning: dict = Field(default_factory=lambda: {"associations": []})
    # How much this mind holds at once: one of affect.CAPACITY_LADDER. Scales
    # the want and intention caps, which were global constants identical for
    # every character and which measurably BIND -- 78% of live banks sit at the
    # want cap. Projects are deliberately NOT scaled by it (see PROJECT_CAP).
    # `ordinary` is exactly the pair that shipped, so an unset one behaves as
    # every existing story already does.
    # Stored EMPTY when unauthored, exactly as `drive.essence` is, rather than
    # backfilled to the default rung. Every reader resolves it through
    # `affect.normalize_capacity`, so behaviour is `ordinary` either way -- but
    # backfilling it here would make "the author chose the middle" and "nobody
    # ever saw this field" the same stored value, and
    # `character_card_warnings` would then never fire on any card,
    # which is the exact silent-failure shape this dial was written to avoid.
    capacity: str = ""

    @validator("capacity", pre=True)
    def _capacity(cls, value):
        from mind import affect
        key = str(value or "").strip().casefold()
        return key if key in affect.CAPACITY_LADDER else ""

    @validator("traits", pre=True)
    def _traits(cls, value):
        value = _as_profile_list(value, "name", TraitProfile, "strength")
        return [
            {"name": item} if isinstance(item, str) else item
            for item in (value or [])
            if isinstance(item, (str, dict))
        ]

    @validator("values", pre=True)
    def _values(cls, value):
        value = _as_profile_list(value, "name", ValueProfile, "priority")
        return [
            {"name": item} if isinstance(item, str) else item
            for item in (value or [])
            if isinstance(item, (str, dict))
        ]

    @validator(
        "drive", "self_model", "coping", "stress_profile", "learning", pre=True
    )
    def _mapping_fields(cls, value):
        return value if isinstance(value, dict) else {}


def _profile(model_cls, raw):
    """Validate and dump one profile, on whichever Pydantic is installed.

    `parse_obj`/`.dict()` still work on 2.x but are deprecated there and go
    away in 3.x, and the declared range (`pydantic>=1.10.13,<3`) is the only
    thing holding that off. One seam rather than six call sites.
    """
    validate = getattr(model_cls, "model_validate", None)
    model = validate(raw) if validate is not None else model_cls.parse_obj(raw)
    dump = getattr(model, "model_dump", None)
    return dump() if dump is not None else model.dict()


def _normalize_psychology(value: Any) -> dict:
    """Typed, tolerant normalization for the durable psychology contract.

    Imported cards and older native sheets remain accepted, but every live
    reader receives the v3 shape. Unknown extension keys survive because the
    profile models allow extras.
    """
    raw = value if isinstance(value, dict) else {}
    result = _profile(PsychologyProfile, raw)

    self_model = result.get("self_model")
    if not isinstance(self_model, dict):
        self_model = {}
    self_model = _deep_defaults({
        "summary": "", "protected_beliefs": [], "pride_triggers": [],
        "shame_triggers": [], "beliefs": [],
    }, self_model)
    self_model["protected_beliefs"] = _profile_str_list(
        self_model.get("protected_beliefs"))
    self_model["pride_triggers"] = _profile_str_list(
        self_model.get("pride_triggers"))
    self_model["shame_triggers"] = _profile_str_list(
        self_model.get("shame_triggers"))
    self_model["beliefs"] = [
        _profile(
            BeliefProfile,
            {"belief": item} if isinstance(item, str) else item,
        )
        for item in _as_profile_list(self_model.get("beliefs"), "belief",
                                     BeliefProfile, "confidence")
        if isinstance(item, (str, dict))
    ]
    result["self_model"] = self_model

    coping = result.get("coping")
    if not isinstance(coping, dict):
        coping = {}
    coping = _deep_defaults({
        "under_stress": [], "default_conflict_style": "",
        "strategies": [], "recovery_supports": [],
    }, coping)
    coping["under_stress"] = _profile_str_list(coping.get("under_stress"))
    coping["recovery_supports"] = _profile_str_list(
        coping.get("recovery_supports"))
    coping["strategies"] = [
        _profile(
            CopingStrategyProfile,
            {"name": item, "response": item} if isinstance(item, str) else item,
        )
        for item in _as_profile_list(coping.get("strategies"), "name",
                                     CopingStrategyProfile, "effectiveness")
        if isinstance(item, (str, dict))
    ]
    result["coping"] = coping

    stress = result.get("stress_profile")
    if not isinstance(stress, dict):
        stress = {}
    stress = _deep_defaults({
        "baseline_reactivity": 0.5, "recovery_rate": 0.5,
        "overload_threshold": 0.8, "attentional_style": "",
        "somatic_signs": [],
    }, stress)
    for key, default in (
        ("baseline_reactivity", 0.5),
        ("recovery_rate", 0.5),
        ("overload_threshold", 0.8),
    ):
        stress[key] = _profile_float(stress.get(key), default=default)
    stress["somatic_signs"] = _profile_str_list(stress.get("somatic_signs"))
    result["stress_profile"] = stress

    learning = result.get("learning")
    if not isinstance(learning, dict):
        learning = {}
    learning["associations"] = [
        _profile(AssociationProfile, item)
        for item in _as_profile_list(learning.get("associations"), "cue",
                                     AssociationProfile, "strength")
        if isinstance(item, dict)
    ]
    result["learning"] = learning
    return result

def new_uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _float_or(value: Any, default: float) -> float:
    """Tolerant float coercion. Imported cards and weak-model generator/promotion
    output routinely put non-numeric junk in numeric slots (`valence: null`,
    `temperature: "warm"`, `trust: "high"`). A bare float() there raises
    TypeError/ValueError, which 500s the import endpoint and then crashes
    character_name()/accessors on EVERY subsequent turn once the sheet is in the
    DB. Coerce instead of crashing on advisory numbers."""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return default if f != f else f  # NaN -> default


def _outfit_items(value: Any) -> list[str]:
    """Whatever a card says it is wearing, as a list of garment names, once
    each.

    THE ONE READER, and it has to accept every shape the field arrives in
    because there were two of these. `story/importers.py` had its own copy
    that unwrapped a wrapper dict and did not dedupe, and this one deduped
    and did not unwrap -- and both ran on the same import
    (`heuristic_character_sheet` builds the outfit with one,
    `normalize_character_data` re-reads it with the other), so which rule
    applied to a card was decided by which same-named helper ran last. Each
    failed at exactly what the other did: an outfit written
    `{"wearing": [...]}` -- what older cards, imports and the generators all
    produce -- came back here as ONE garment whose name is a Python dict.
    """
    if value is None:
        return []
    if isinstance(value, dict):
        value = value.get("wearing") or value.get("items") or []
    if isinstance(value, str):
        value = [part for part in re.split(r"[;\n]+", value) if part.strip()]
    elif not isinstance(value, (list, tuple, set)):
        value = [value]
    result = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_initial_outfit(value: Any) -> dict:
    """Normalize authored starting clothes into the live attire shape.

    `regions` is the authoring surface: which body part each garment occupies,
    and optionally what is underneath it.

    `wearing` is RETIRED as something an author fills in, and kept as an input
    format -- what every older card carries, what an import brings, and what
    the generators still emit. It is folded into `regions` on read, so a card
    written the old way migrates the first time anything looks at it, and the
    cue-table guess `attire.region_of` made lands in the region editor where an
    author can see it and move it. A guess nobody can find is worse than a
    guess in the wrong place.

    It is then written back as a DERIVED mirror, so the two can never disagree
    about the same body. `state` is retired outright: what has happened to a
    garment now belongs to the garment (`condition`), not to a free-text list
    beside the person. Existing values are preserved, never extended.
    """
    if isinstance(value, dict):
        wearing = value.get("wearing")
        if wearing is None:
            wearing = value.get("items") or value.get("outfit")
        state = value.get("state")
        regions = attire.normalize_regions({
            "regions": value.get("regions"),
            "wearing": _outfit_items(wearing),
        })
    else:
        wearing, state, regions = value, [], {}
    return {
        "wearing": attire.flat_wearing(regions) or _outfit_items(wearing),
        "state": _outfit_items(state),
        "regions": regions,
    }


# ---- Extra body parts (embodiment.extra_parts) ----
#
# Tails, wings, horns, extra arms: BODY, so they live on the card beside
# `visible`, never in the attire ledger (clothing) and never in the scene
# blob (a card edit must keep fixing the body it describes). The menus are
# closed and orthogonal; the part noun itself stays free because anatomy is
# open-ended and the noun doubles as the contact handle
# (spatial._part_identity already reads it structurally).
#
# `at` reuses attire.REGIONS -- the one region vocabulary clothing coverage,
# region_visibility and the editor already speak, which is what makes "does
# the skirt cover the tail's root" answerable without a second anatomy.
#
# `aspect` is which FACE of that region the part emerges from:
#   front     -- the ventral/leading face (in front)
#   back      -- the dorsal face (behind: tails, wings)
#   top       -- the upper surface (above: horns from the crown)
#   underside -- the lower surface (below)
#   left/right - one lateral side
#   sides     -- bilaterally, spread across both sides (extra arm pairs;
#                count is the total across both)
EXTRA_PART_ASPECTS = ("front", "back", "top", "underside", "left", "right",
                      "sides")
EXTRA_PART_COUNT_MAX = 12

# Where a part goes when the author did not say: an authoring default in the
# attire.region_of spirit (a guess visible in the editor, recoverable), NEVER
# an identity fold -- spatial.py's ban on body-part synonym tables is about
# comparing parts, and this table never compares anything.
_EXTRA_PART_PLACEMENTS = {
    "tail": ("waist", "back"),
    "wing": ("torso", "back"),
    "horn": ("head", "top"),
    "antler": ("head", "top"),
    "ear": ("head", "top"),
    "tentacle": ("torso", "back"),
    "arm": ("torso", "sides"),
    "eye": ("head", "front"),
    "halo": ("head", "top"),
}


def _extra_part_placement(kind: str) -> tuple[str, str]:
    word = str(kind or "").strip().casefold().split()[-1:] or [""]
    word = word[0]
    if word.endswith("s") and word[:-1] in _EXTRA_PART_PLACEMENTS:
        word = word[:-1]
    return _EXTRA_PART_PLACEMENTS.get(word, ("torso", "back"))


def _normalize_extra_parts(value: Any) -> list[dict]:
    """Authored extra body parts, menus enforced, junk tolerated.

    A bare string ("tail") is a part with everything else defaulted, matching
    how every sibling list field (senses, latent, traits) reads leniency. An
    entry with no kind is dropped -- there is nothing to attach. Menu values
    outside the closed vocabularies fall to the per-kind placement guess so
    the guess lands somewhere an author can see and move it.
    """
    if isinstance(value, dict):
        # {"tail": {...}} -- the keyed spelling a model plausibly writes.
        value = [dict(v, kind=k) if isinstance(v, dict) else k
                 for k, v in value.items()]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        if isinstance(item, str):
            item = {"kind": item}
        if not isinstance(item, dict):
            continue
        kind = " ".join(str(item.get("kind") or item.get("part")
                            or item.get("name") or "").split())
        if not kind:
            continue
        guess_at, guess_aspect = _extra_part_placement(kind)
        at = str(item.get("at") or item.get("region") or "").strip().casefold()
        if at not in attire.REGIONS:
            at = guess_at
        aspect = str(item.get("aspect") or item.get("orientation")
                     or "").strip().casefold()
        if aspect not in EXTRA_PART_ASPECTS:
            aspect = guess_aspect
        try:
            count = int(item.get("count", 1))
        except (TypeError, ValueError):
            count = 1
        count = max(1, min(EXTRA_PART_COUNT_MAX, count))
        through = item.get("through_clothing")
        out.append({
            "kind": kind,
            "count": count,
            "at": at,
            "aspect": aspect,
            # Default TRUE: the fiction's tail passes through the skirt, and
            # the wrong default silently deletes the swaying-tail detail
            # whenever the region is dressed.
            "through_clothing": True if through is None else bool(through),
            "description": " ".join(
                str(item.get("description") or "").split())[:400],
        })
    return out


def default_character_data(name: str = "Unnamed") -> dict:
    result = {
        "identity": {
            "uid": new_uid("char"),
            "name": name,
            "aliases": [],
            "pronouns": {"subject": "they", "object": "them", "possessive": "their"},
        },
        "initial_outfit": {"wearing": [], "state": [], "regions": {}},
        "simulation": {"tier": "mid", "temperature": 0.8, "sampler": {},
                       "curiosity": 0.5, "offscreen_agent": False},
        "embodiment": {
            "senses": [
                {"channel": "vision", "acuity": "ordinary", "range": "ordinary", "notes": ""},
                {"channel": "hearing", "acuity": "ordinary", "range": "ordinary", "notes": ""},
            ],
            "visible": {
                "summary": "A person of unremarkable appearance.",
                "build": "", "face": "", "hair": "", "eyes": "",
                "distinctive_features": [],
            },
            "latent": [],
            # Structured extra body parts -- see _normalize_extra_parts.
            "extra_parts": [],
            "interoception": {
                "acuity": 0.5,
                "pain_sensitivity": 0.5,
                "fatigue_sensitivity": 0.5,
                "pleasure_sensitivity": 0.5,
            },
        },
        "psychology": {
            "traits": [],
            "values": [],
            "self_model": {
                "summary": "",
                "protected_beliefs": [],
                "pride_triggers": [],
                "shame_triggers": [],
                "beliefs": [],
            },
            "coping": {
                "under_stress": [],
                "default_conflict_style": "",
                "strategies": [],
                "recovery_supports": [],
            },
            "stress_profile": {
                "baseline_reactivity": 0.5,
                "recovery_rate": 0.5,
                "overload_threshold": 0.8,
                "attentional_style": "",
                "somatic_signs": [],
            },
            "learning": {"associations": []},
            # Overarching core drive (Tier 1 of the goal hierarchy): identity-
            # level, rarely changes, and deliberately NOT part of the character
            # agent's output contract -- a model cannot flip-flop a field it
            # never emits. Read-only in the payload; backfilled on normalize for
            # older sheets via _deep_defaults.
            "drive": {"essence": "", "expression": "", "taboo": ""},
            # Attentional capacity (affect.CAPACITY_LADDER). Left EMPTY when
            # unauthored so an import warning can tell the difference; every
            # reader resolves it through affect.normalize_capacity, whose
            # default is the pair every existing story already ran on.
            "capacity": "",
        },
        "social": {
            "voice": {
                "register": "", "cadence": "", "verbosity": "natural",
                "markers": [], "notes": "",
            },
            "baseline_stances": {
                "unknown_person": {
                    "trust": 0.0, "warmth": 0.0, "threat_sensitivity": 0.0,
                },
            },
        },
        "competence": {"abilities": []},
        "knowledge": {
            "access_tags": ["common"],
            "excluded_titles": [],
            "public_history": "",
            "private_history": [],
        },
        "initial_state": {
            "mood": {"label": "neutral", "valence": 0.0, "arousal": 0.0},
            "goals": [],
            "active_concerns": [],
            "stress": {"activation": 0.0, "load": 0.0, "coping_mode": ""},
            "hedonic": {"pain": 0.0, "pleasure": 0.0, "source": ""},
        },
        "opening": {"first_message": ""},
    }
    return result

def default_character_document(name: str = "Unnamed") -> dict:
    return {
        "schema": CHARACTER_SCHEMA,
        "version": CHARACTER_VERSION,
        "data": default_character_data(name),
        "source": {"format": "native", "original": None},
    }

def default_persona_data(name: str = "Player") -> dict:
    return {
        "identity": {
            "uid": new_uid("persona"),
            "name": name,
            "aliases": [],
            "pronouns": {"subject": "they", "object": "them", "possessive": "their"},
        },
        "initial_outfit": {"wearing": [], "state": [], "regions": {}},
        "embodiment": {
            "senses": [
                {"channel": "vision", "acuity": "ordinary", "range": "ordinary", "notes": ""},
                {"channel": "hearing", "acuity": "ordinary", "range": "ordinary", "notes": ""},
            ],
            "visible": {
                "summary": "A person of unremarkable appearance.",
                "build": "", "face": "", "hair": "", "eyes": "",
                "distinctive_features": [],
            },
            "latent": [],
            "extra_parts": [],
        },
        "competence": {"abilities": []},
        "knowledge": {"public_history": "", "private_history": []},
        "narration": {"voice_setting": ""},
    }

def default_persona_document(name: str = "Player") -> dict:
    return {
        "schema": PERSONA_SCHEMA,
        "version": PERSONA_VERSION,
        "data": default_persona_data(name),
        "source": {"format": "native", "original": None},
    }

def _list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]

def _legacy_senses(value: Any) -> list[dict]:
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                result.append(copy.deepcopy(item))
            elif item:
                result.append({"channel": "other", "acuity": "ordinary",
                               "range": "ordinary", "notes": str(item)})
        return result
    text = str(value or "ordinary human senses")
    return [{"channel": "general", "acuity": "ordinary",
             "range": "ordinary", "notes": text}]

def _legacy_voice(value: Any) -> dict:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    return {"register": "", "cadence": "", "verbosity": "natural",
            "markers": [], "notes": str(value or "")}

def _legacy_mood(value: Any) -> dict:
    if isinstance(value, dict):
        if "label" in value:
            return {"label": str(value.get("label") or "neutral"),
                    "valence": _float_or(value.get("valence"), 0.0),
                    "arousal": _float_or(value.get("arousal"), 0.0)}
        return {"label": str(value.get("mood") or "neutral"),
                "valence": _float_or(value.get("valence"), 0.0),
                "arousal": _float_or(value.get("arousal"), 0.0)}
    return {"label": str(value or "neutral"), "valence": 0.0, "arousal": 0.0}

def _legacy_traits(core: Any) -> list[dict]:
    core = core if isinstance(core, dict) else {}
    result = []
    for item in _list(core.get("traits")):
        if isinstance(item, dict):
            result.append(copy.deepcopy(item))
        elif item:
            result.append({"name": str(item), "strength": 0.5, "expression": ""})
    return result

def _legacy_values(core: Any) -> list[dict]:
    core = core if isinstance(core, dict) else {}
    result = []
    for item in _list(core.get("values")):
        if isinstance(item, dict):
            result.append(copy.deepcopy(item))
        elif item:
            result.append({"name": str(item), "priority": 0.5})
    return result

def _legacy_abilities(value: Any) -> list[dict]:
    result = []
    for item in _list(value):
        if not isinstance(item, dict):
            if item:
                result.append({"name": str(item), "level": "competent",
                               "scope": "", "limits": "", "notes": ""})
            continue
        result.append({
            "name": str(item.get("name") or "unnamed ability"),
            "level": str(item.get("level") or "competent"),
            "scope": str(item.get("scope") or ""),
            "limits": str(item.get("limits") or ""),
            "notes": str(item.get("notes") or ""),
        })
    return result

def _legacy_private_history(value: Any) -> list[dict]:
    """Coerce private-history entries into the {content, about, known_by}
    shape the engine's information-boundary checks require (scene.py
    private_knowledge_for). Every other list-of-facts field on this schema
    (traits, values, abilities, senses) tolerates a bare-string legacy form;
    without this, a plain string entry is not a parse error, it is silently
    dropped by private_knowledge_for's `isinstance(e, dict)` check, so the
    character ends up with no private knowledge and nothing signals why.
    """
    result = []
    for item in _list(value):
        if isinstance(item, dict):
            if item.get("content"):
                result.append(copy.deepcopy(item))
            continue
        text = str(item or "").strip()
        if text:
            result.append({"content": text, "about": "", "known_by": []})
    return result

def _deep_defaults(defaults: Any, value: Any) -> Any:
    if not isinstance(defaults, dict):
        return copy.deepcopy(value)
    result = copy.deepcopy(defaults)
    if not isinstance(value, dict):
        return result
    for key, item in value.items():
        if key in result and isinstance(result[key], dict) and isinstance(item, dict):
            result[key] = _deep_defaults(result[key], item)
        else:
            result[key] = copy.deepcopy(item)
    return result

def _normalize_latent(value: Any) -> list[dict]:
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append(copy.deepcopy(item))
            elif item:
                # every sibling field (senses/traits/values/abilities) tolerates
                # bare strings; latent alone used to silently drop them.
                out.append({"capability": str(item), "visible_when": "", "limits": ""})
        return out
    if isinstance(value, dict):
        result = []
        for capability, details in value.items():
            if isinstance(details, str):
                result.append({"capability": str(capability), "visible_when": "", "limits": details})
            else:
                result.append({"capability": str(capability), "visible_when": "",
                                "limits": json.dumps(details, ensure_ascii=False)})
        return result
    return []

def _coerce_latent(target_dict: dict) -> dict:
    embodiment = target_dict.setdefault("embodiment", {})
    caps = embodiment.pop("latent_capabilities", None)
    if caps is None:
        caps = embodiment.pop("supernatural", None)
    if caps is None:
        caps = embodiment.pop("powers", None)
    latent = embodiment.get("latent")
    if caps is not None and not latent:
        embodiment["latent"] = _normalize_latent(caps)
    else:
        embodiment["latent"] = _normalize_latent(latent)
    return target_dict

def _coerce_appearance(target_dict: dict) -> dict:
    embodiment = target_dict.setdefault("embodiment", {})
    visible = embodiment.setdefault("visible", {})
    # Older/native-adjacent sheets commonly put clothes beside body fields.
    # Move them into authored starting attire before constructing appearance;
    # clothing is mutable story state, not anatomy.
    outfit_value = target_dict.get("initial_outfit")
    if not any(_normalize_initial_outfit(outfit_value).values()):
        outfit_value = None
    for key in ("outfit", "clothing", "attire"):
        top_level = target_dict.pop(key, None)
        nested = embodiment.pop(key, None)
        if outfit_value in (None, "", [], {}):
            outfit_value = (
                top_level
                if top_level not in (None, "", [], {})
                else nested
            )
    target_dict["initial_outfit"] = _normalize_initial_outfit(outfit_value)
    summary = str(visible.get("summary", "")).strip()
    is_default = not summary or summary == "A person of unremarkable appearance."
    extra_visual = []
    for key in ("build", "face", "hair", "eyes", "complexion", "height",
                "weight", "body_type", "ethnicity_descriptor"):
        val = embodiment.pop(key, None)
        if val:
            label = key.replace("_", " ").capitalize()
            extra_visual.append(f"{label}: {val}")
    features = embodiment.pop("distinct_features", None)
    if features and isinstance(features, list):
        extra_visual.append("Distinctive features: " + ", ".join(features))
    if extra_visual:
        # Fold popped embodiment details into the summary. Previously these were
        # only kept when the summary was default; a custom summary discarded
        # hair/body details permanently on every normalize (i.e. every import).
        if is_default:
            visible["summary"] = ". ".join(extra_visual) + "."
        else:
            visible["summary"] = summary.rstrip(". ") + ". " + ". ".join(extra_visual) + "."
    visible.setdefault("build", "")
    visible.setdefault("face", "")
    visible.setdefault("hair", "")
    visible.setdefault("eyes", "")
    visible.setdefault("distinctive_features", [])
    return target_dict

CHARACTER_SECTIONS = (
    "identity", "initial_outfit", "simulation", "embodiment", "psychology",
    "social", "competence", "knowledge", "initial_state", "opening",
)
_IDENTITY_FIELDS = ("uid", "name", "aliases", "pronouns")
# Values the schema skeleton carries when nobody filled the field in. An
# identity holding one of these is empty in every sense that matters, so a
# real value recovered from top level must win over it.
_IDENTITY_PLACEHOLDERS = {
    "name": "Unnamed",
    "aliases": [],
    "pronouns": {"subject": "they", "object": "them", "possessive": "their"},
}


def _content_weight(value) -> int:
    """How much actual content a subtree carries -- non-empty strings, non-zero
    numbers, populated lists. Used to tell the schema SKELETON a model emitted
    before it lost its place ({"abilities": []}) from the real section it
    emitted afterwards ({"abilities": [five of them]})."""
    if isinstance(value, dict):
        return sum(_content_weight(v) for v in value.values())
    if isinstance(value, list):
        return sum(_content_weight(v) for v in value)
    if isinstance(value, bool):
        return 0
    if isinstance(value, str):
        return 1 if value.strip() else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    return 0


def repair_character_shape(value: dict) -> dict:
    """Lift canonical sections that landed INSIDE another section, and fold a
    flat identity back into `identity`.

    An imported card is reinterpreted by a model, and a response missing one
    closing brace is repaired by importers._jparse into something that parses
    but nests the remaining sections under whichever one was left open.
    `_deep_defaults` then keeps those unknown keys verbatim and backfills the
    real slots with defaults -- so the sheet the engine reads is hollow while
    the content sits inert one level down. Nothing raised and nothing warned.

    Observed live on an imported character whose pronouns, aliases, voice,
    five abilities, whole history, three standing goals and first message
    were all parked under `psychology`, leaving her they/them, unskilled,
    goalless and silent. The content was never lost, only misplaced.

    Runs inside normalize_character_data, so it repairs on READ: existing
    damaged sheets heal without a migration.
    """
    if not isinstance(value, dict):
        return value
    value = dict(value)

    for host in CHARACTER_SECTIONS:
        section = value.get(host)
        if not isinstance(section, dict):
            continue
        misplaced = [k for k in CHARACTER_SECTIONS
                     if k != host and isinstance(section.get(k), dict)]
        if not misplaced:
            continue
        section = dict(section)
        for key in misplaced:
            lifted = section.pop(key)
            # Whichever copy actually carries content wins. The top-level one
            # is usually the skeleton the model emitted before it lost its
            # place, so "already present" is not the same as authoritative.
            if _content_weight(lifted) > _content_weight(value.get(key)):
                value[key] = lifted
        value[host] = section

    # A model that drops the `identity` wrapper puts name/pronouns/aliases/uid
    # at top level, where only `name` was ever rescued.
    identity = dict(value.get("identity") or {})
    recovered = False
    for field in _IDENTITY_FIELDS:
        if field not in value:
            continue
        current = identity.get(field)
        if not current or current == _IDENTITY_PLACEHOLDERS.get(field):
            if _content_weight(value[field]) >= _content_weight(current):
                identity[field] = value[field]
                recovered = True
    if recovered:
        value["identity"] = identity

    return value


def normalize_character_data(value: dict) -> dict:
    if not isinstance(value, dict):
        value = {}
    if value.get("schema") == CHARACTER_SCHEMA:
        value = value.get("data") or {}
    elif isinstance(value.get("sheet"), dict):
        value = value["sheet"]
    if any(key in value for key in (
        "identity", "simulation", "embodiment", "psychology",
        "social", "competence", "initial_state",
    )):
        # Only NATIVE sheets are repaired. A legacy sheet keeps `name` at top
        # level legitimately, and folding that into a synthesized `identity`
        # would make it look native to the branch test above and route it
        # away from the legacy conversion below.
        value = repair_character_shape(value)
        name = (value.get("identity") or {}).get("name") or value.get("name") or "Unnamed"
        result = _deep_defaults(default_character_data(name), value)
        _coerce_latent(result)
        _coerce_appearance(result)
        result["initial_outfit"] = _normalize_initial_outfit(
            result.get("initial_outfit"))
        result["psychology"] = _normalize_psychology(result.get("psychology"))
        interoception = result["embodiment"].get("interoception")
        if not isinstance(interoception, dict):
            interoception = {}
        interoception = _deep_defaults(
            default_character_data(name)["embodiment"]["interoception"],
            interoception,
        )
        for key in (
            "acuity", "pain_sensitivity", "fatigue_sensitivity",
            "pleasure_sensitivity",
        ):
            interoception[key] = _profile_float(interoception.get(key))
        result["embodiment"]["interoception"] = interoception
        result["embodiment"]["extra_parts"] = _normalize_extra_parts(
            result["embodiment"].get("extra_parts"))
        stress = result["initial_state"].get("stress")
        if not isinstance(stress, dict):
            stress = {}
        stress = _deep_defaults(
            {"activation": 0.0, "load": 0.0, "coping_mode": ""}, stress)
        stress["activation"] = _profile_float(stress.get("activation"), 0.0)
        stress["load"] = _profile_float(stress.get("load"), 0.0)
        result["initial_state"]["stress"] = stress
        hedonic = result["initial_state"].get("hedonic")
        if not isinstance(hedonic, dict):
            hedonic = {}
        hedonic = _deep_defaults(
            {"pain": 0.0, "pleasure": 0.0, "source": ""}, hedonic)
        hedonic["pain"] = _profile_float(hedonic.get("pain"), 0.0)
        hedonic["pleasure"] = _profile_float(hedonic.get("pleasure"), 0.0)
        result["initial_state"]["hedonic"] = hedonic
        result["knowledge"]["private_history"] = _legacy_private_history(
            result["knowledge"].get("private_history"))
        return result
    name = str(value.get("name") or "Unnamed")
    core = value.get("core") if isinstance(value.get("core"), dict) else {}
    active = value.get("active_state") if isinstance(value.get("active_state"), dict) else {}
    knowledge = value.get("knowledge") if isinstance(value.get("knowledge"), dict) else {}
    access_tags = []
    if knowledge.get("common", True):
        access_tags.append("common")
    if knowledge.get("scholarly", False):
        access_tags.append("scholarly")
    if knowledge.get("esoteric", False):
        access_tags.append("esoteric")
    stance = value.get("stance") if isinstance(value.get("stance"), dict) else {}
    result = {
        "identity": {
            "uid": str(value.get("uid") or new_uid("char")),
            "name": name,
            "aliases": _list(value.get("aliases")),
            "pronouns": copy.deepcopy(value.get("pronouns") or {
                "subject": "they", "object": "them", "possessive": "their"}),
        },
        "initial_outfit": _normalize_initial_outfit(
            value.get("initial_outfit")
            or value.get("outfit")
            or value.get("clothing")
            or value.get("attire")
        ),
        "simulation": {
            "tier": str(value.get("tier") or "mid"),
            "temperature": _float_or(value.get("temperature"), 0.8),
            "sampler": copy.deepcopy(value.get("sampler") or {}),
            "offscreen_agent": bool(value.get("offscreen_agent", False)),
        },
        "embodiment": {
            "senses": _legacy_senses(value.get("senses")),
            "visible": {
                "summary": str(value.get("appearance") or "A person of unremarkable appearance."),
                "build": "", "face": "", "hair": "", "eyes": "",
                "distinctive_features": [],
            },
            "latent": copy.deepcopy(value.get("latent_capabilities") or []),
            "extra_parts": _normalize_extra_parts(value.get("extra_parts")),
            "interoception": {
                "acuity": 0.5, "pain_sensitivity": 0.5,
                "fatigue_sensitivity": 0.5, "pleasure_sensitivity": 0.5,
            },
        },
        "psychology": {
            # Present but empty, matching default_character_data. Omitting the
            # slot entirely left legacy sheets with a psychology that had no
            # drive key at all -- effective_drive() tolerates it, but nothing
            # downstream could then fill one in.
            "drive": {"essence": "", "expression": "", "taboo": ""},
            "traits": _legacy_traits(core),
            "values": _legacy_values(core),
            "self_model": {
                "summary": str(core.get("self_image") or ""),
                "protected_beliefs": [],
                "pride_triggers": [],
                "shame_triggers": [],
                "beliefs": [],
            },
            "coping": {
                "under_stress": [], "default_conflict_style": "",
                "strategies": [], "recovery_supports": [],
            },
            "stress_profile": {
                "baseline_reactivity": 0.5, "recovery_rate": 0.5,
                "overload_threshold": 0.8, "attentional_style": "",
                "somatic_signs": [],
            },
            "learning": {"associations": []},
        },
        "social": {
            "voice": _legacy_voice(value.get("voice")),
            "baseline_stances": {
                "unknown_person": {
                    "trust": _float_or((stance.get("axes") or {}).get("trust_player"), 0.0),
                    "warmth": 0.0,
                    "threat_sensitivity": 0.0,
                },
            },
            "legacy_stance": copy.deepcopy(stance),
        },
        "competence": {"abilities": _legacy_abilities(value.get("abilities"))},
        "knowledge": {
            "access_tags": access_tags or ["common"],
            "excluded_titles": _list(knowledge.get("excluded_titles")),
            "public_history": str(value.get("public_history") or ""),
            "private_history": _legacy_private_history(value.get("private_history")),
        },
        "initial_state": {
            "mood": _legacy_mood(active.get("mood")),
            "goals": ([{"goal": str(active.get("goal")), "priority": 0.5}]
                      if active.get("goal") else []),
            "active_concerns": [],
            "stress": {"activation": 0.0, "load": 0.0, "coping_mode": ""},
            "hedonic": {"pain": 0.0, "pleasure": 0.0, "source": ""},
        },
        "opening": {"first_message": str(value.get("first_message") or "")},
    }
    result["psychology"] = _normalize_psychology(result["psychology"])
    return result

def normalize_persona_data(value: dict) -> dict:
    if not isinstance(value, dict):
        value = {}
    if value.get("schema") == PERSONA_SCHEMA:
        value = value.get("data") or {}
    elif isinstance(value.get("sheet"), dict):
        value = value["sheet"]
    if "identity" in value or "narration" in value:
        name = (value.get("identity") or {}).get("name") or value.get("name") or "Player"
        result = _deep_defaults(default_persona_data(name), value)
        _coerce_latent(result)
        _coerce_appearance(result)
        result["initial_outfit"] = _normalize_initial_outfit(
            result.get("initial_outfit"))
        result["embodiment"]["extra_parts"] = _normalize_extra_parts(
            result["embodiment"].get("extra_parts"))
        result["knowledge"]["private_history"] = _legacy_private_history(
            result["knowledge"].get("private_history"))
        return result
    return {
        "identity": {
            "uid": str(value.get("uid") or new_uid("persona")),
            "name": str(value.get("name") or "Player"),
            "aliases": _list(value.get("aliases")),
            "pronouns": copy.deepcopy(value.get("pronouns") or {
                "subject": "they", "object": "them", "possessive": "their"}),
        },
        "initial_outfit": _normalize_initial_outfit(
            value.get("initial_outfit")
            or value.get("outfit")
            or value.get("clothing")
            or value.get("attire")
        ),
        "embodiment": {
            "senses": _legacy_senses(value.get("senses")),
            "visible": {
                "summary": str(value.get("appearance") or "A person of unremarkable appearance."),
                "build": "", "face": "", "hair": "", "eyes": "",
                "distinctive_features": [],
            },
            "latent": copy.deepcopy(value.get("latent_capabilities") or []),
            "extra_parts": _normalize_extra_parts(value.get("extra_parts")),
        },
        "competence": {"abilities": _legacy_abilities(value.get("abilities"))},
        "knowledge": {
            "public_history": str(value.get("public_history") or ""),
            "private_history": _legacy_private_history(value.get("private_history")),
        },
        "narration": {"voice_setting": str(value.get("voice_setting") or "")},
    }

# ---- Name matching ----

#: Letters that can continue a word in a script that separates words with
#: spaces: Latin (with its supplements), Greek, Cyrillic, plus digits and the
#: underscore. Deliberately NOT `\w`, which also covers scripts that do not
#: space their words.
_SPACED_WORD_CHARS = (
    r"A-Za-z0-9_À-ɏḀ-ỿͰ-ϿЀ-ӿ")
#: Scripts written without spaces between words: kana, CJK ideographs and
#: their compatibility blocks, Hangul, Thai. A name in one of these is
#: followed directly by a particle or the next morpheme.
_UNSPACED_SCRIPT = re.compile(
    r"[぀-ヿ㐀-䶿一-鿿豈-﫿"
    r"가-힯฀-๿]")


@functools.lru_cache(maxsize=2048)
def name_boundary_pattern(form: str) -> str:
    """Match `form` as a whole name, in whatever script the name is written.

    `\\b` and `(?<!\\w)` assert a transition between word and non-word
    characters, which only describes scripts that put spaces between words.
    Japanese particles are word characters, so `ヒナミに` never matched `ヒナミ`
    and every name-keyed guard silently stopped firing -- identity scrubbing,
    concealment redaction and name fidelity alike, each failing OPEN with no
    warning because "no match" and "nothing to redact" are the same answer.

    The decision is per-NAME, not per-language: a Japanese story carries Latin
    names through code-switching and imported cards, and an English story
    carries Japanese ones. Each end of the form is judged by its own script.

    The boundary that IS applied excludes only spaced-script letters, so a
    Latin name still refuses to match inside `Hinamis` while matching in
    `彼はHinamiに`, where the neighbours are Japanese.
    """
    text = str(form or "")
    if not text:
        return r"(?!)"  # never matches, rather than matching everywhere
    lead = "" if _UNSPACED_SCRIPT.match(text[0]) else f"(?<![{_SPACED_WORD_CHARS}])"
    tail = "" if _UNSPACED_SCRIPT.match(text[-1]) else f"(?![{_SPACED_WORD_CHARS}])"
    return lead + re.escape(text) + tail


def name_boundary_regex(form: str, flags: int = 0):
    """`name_boundary_pattern` compiled; cached by the pattern cache."""
    return re.compile(name_boundary_pattern(form), flags)


def fold_identity_key(value: Any) -> str:
    """Casefold a name to a comparison key, keeping letters in every script.

    The old fold was `re.sub(r"[^a-z0-9]", "", name.lower())`, which deletes
    every non-ASCII character -- so every Japanese name folded to the EMPTY
    STRING and therefore compared equal to every other Japanese name. Where a
    caller guarded with `if norm:` that merely disabled the match; where it
    did not, distinct people were treated as one.

    Identical to the old behaviour for ASCII input.
    """
    return "".join(ch for ch in str(value or "").casefold().strip()
                   if ch.isalnum())


def cue_boundary_pattern(alternation: str) -> str:
    """Wrap a language pack's cue alternation in a script-safe boundary.

    The vocabulary moved into `linguistics.json` while the `\\b` around it
    stayed in Python, so every Japanese alternative a pack added was
    unreachable: `\\b(?:歩く|走る)\\b` cannot match, because CJK has no word
    boundary in the sense `\\b` means. Cue alternations are also MIXED -- a
    pack keeps the English alternatives for code-switching and quoted text --
    so the boundary has to admit both in one pattern.

    Excluding only spaced-script letters does that: `歩く` still matches
    after a particle, while `walk` still refuses to match inside `sidewalk`.
    """
    return (f"(?<![{_SPACED_WORD_CHARS}])(?:{alternation})"
            f"(?![{_SPACED_WORD_CHARS}])")


# ---- Accessors ----

def character_name(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("identity", {}).get("name") or "Unnamed")


@functools.lru_cache(maxsize=512)
def character_name_from_text(sheet_text: str | None) -> str:
    """`character_name` keyed on the raw stored sheet TEXT.

    The pipeline resolves names with `character_name(json.loads(row["sheet"]))`
    from ~20 call sites, several inside per-cast and per-observer loops -- and
    `character_name` runs the FULL sheet normalization (default-tree build,
    recursive merge, shape repair) just to read one string. The sheet text a
    row carries is byte-identical for the whole turn, so the derivation is a
    pure function of it and safe to memoize. An edited sheet is a different
    string and therefore a different cache entry; normalization stays the one
    authority on how a name is derived (no fast-path re-implementation to
    drift out of sync). Cached strings are immutable, so no copying is needed.
    """
    try:
        data = json.loads(sheet_text or "{}")
    except Exception:
        data = {}
    return character_name(data if isinstance(data, dict) else {})

def character_tier(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("simulation", {}).get("tier", "mid"))


def character_offscreen_agent(sheet: dict) -> bool:
    """Author-owned opt-in for the paid off-screen character ceiling."""
    return bool(normalize_character_data(sheet).get(
        "simulation", {}).get("offscreen_agent", False))


def cast_entity_id(sheet: dict, char_id) -> str:
    """The id-shaped spelling a cast member is ALREADY live under.

    `scene.cast_scene_context` has been minting exactly this expression into
    every mapping/director payload since scene entities existed, so it is the
    one id a cast member's scene entity is keyed by. Extracted so subject
    identity (`subjects.py`) resolves to the SAME string instead of deriving
    its own -- two derivations of one id is the two-spellings defect, one
    level up.

    Reads the RAW sheet on purpose, never `normalize_character_data`: for a
    sheet with no authored uid, normalization mints a FRESH `char_<hex>` per
    call, which would give one being a new name every time anything asked.
    The `character:<char_id>` fallback is stable because the row id is.
    """
    identity = (sheet or {}).get("identity") or {}
    return str(identity.get("uid") or f"character:{int(char_id)}")

def character_curiosity(sheet: dict) -> float:
    """How readily this character leaves something that works to look for
    something better. 0 = methodical, never abandons a proven way; 1 = restless,
    always drawn to what it has not tried.

    Observed live: a character that had learned a route perfectly then abandoned
    it on three consecutive attempts, exploring further each time. That was not
    malfunction -- exploring after mastery is reasonable -- but the balance was
    implicit, falling out of which affordances happened to exist rather than
    from anything an author chose. Willingness to leave a known-good route is a
    personality property and belongs on the card beside the rest of the
    psychology.
    """
    sim = normalize_character_data(sheet).get("simulation", {})
    return _profile_float(sim.get("curiosity"), 0.5)


def character_temperature(sheet: dict) -> float:
    return _float_or(normalize_character_data(sheet).get("simulation", {}).get("temperature"), 0.8)

def character_sampler(sheet: dict) -> dict:
    return copy.deepcopy(normalize_character_data(sheet).get("simulation", {}).get("sampler", {}))

def character_appearance(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("embodiment", {}).get("visible", {})
               .get("summary") or "A person of unremarkable appearance.")


def character_initial_outfit(sheet: dict) -> dict:
    return copy.deepcopy(
        normalize_character_data(sheet).get(
            "initial_outfit", {"wearing": [], "state": [], "regions": {}})
    )

def character_senses(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_character_data(sheet).get("embodiment", {}).get("senses", []))

def character_interoception(sheet: dict) -> dict:
    return copy.deepcopy(
        normalize_character_data(sheet).get("embodiment", {}).get("interoception", {})
    )


def character_embodiment_capabilities(sheet: dict) -> list[dict]:
    """Latent/conditional facts a character necessarily knows about itself.

    These are hidden from ordinary observers, not from the body that owns
    them.  Keeping the accessor separate from visible appearance prevents a
    private capability from leaking merely because another character can see
    its owner.
    """
    return copy.deepcopy(
        normalize_character_data(sheet).get("embodiment", {}).get("latent", [])
    )

def character_extra_parts(sheet: dict) -> list[dict]:
    """Authored structured extra body parts (tails, wings, horns...).

    Body configuration read live from the card, like senses -- a sheet edit
    fixes the body without a migration, and a sheet without any normalizes to
    [] so the whole feature stays inert by default.
    """
    return copy.deepcopy(
        normalize_character_data(sheet).get("embodiment", {}).get(
            "extra_parts", [])
    )


def character_abilities(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_character_data(sheet).get("competence", {}).get("abilities", []))

def character_voice(sheet: dict) -> dict:
    return copy.deepcopy(normalize_character_data(sheet).get("social", {}).get("voice", {}))

def character_psychology(sheet: dict) -> dict:
    return copy.deepcopy(normalize_character_data(sheet).get("psychology", {}))

def effective_drive(psychology: dict, interior: dict) -> dict:
    """The character's CURRENT core drive: a rupture-installed
    cstate.interior.drive_override when present, else the authored sheet drive
    (psychology.drive). The single read path so the payload and appraisal always
    see the live drive after a shift -- commit writes cstate, never the sheet."""
    override = interior.get("drive_override") if isinstance(interior, dict) else None
    if isinstance(override, dict) and str(override.get("essence") or "").strip():
        return {"essence": str(override.get("essence") or ""),
                "expression": str(override.get("expression") or ""),
                "taboo": str(override.get("taboo") or "")}
    drive = (psychology or {}).get("drive")
    return drive if isinstance(drive, dict) else {"essence": "", "expression": "", "taboo": ""}

def character_private_history(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_character_data(sheet).get("knowledge", {}).get("private_history", []))

def character_public_history(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("knowledge", {}).get("public_history", ""))

def character_opening_context(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("opening", {}).get("first_message", ""))

def character_knowledge_config(sheet: dict) -> dict:
    knowledge = normalize_character_data(sheet).get("knowledge", {})
    tags = set(knowledge.get("access_tags") or [])
    return {
        "common": "common" in tags,
        "scholarly": "scholarly" in tags,
        "esoteric": "esoteric" in tags,
        "excluded_titles": knowledge.get("excluded_titles") or [],
    }

def character_initial_active_state(sheet: dict) -> dict:
    state = normalize_character_data(sheet).get("initial_state", {})
    # _legacy_mood tolerates a bare-string mood ("wary") from an imported
    # card -- _deep_defaults keeps a non-dict leaf as-is, so a plain
    # `or {}` here crashed every turn that loaded such a character.
    mood = _legacy_mood(state.get("mood"))
    goals = state.get("goals") or []
    label = mood.get("label") or "neutral"
    v = _float_or(mood.get("valence"), 0.0)
    a = _float_or(mood.get("arousal"), 0.0)
    stress = state.get("stress") if isinstance(state.get("stress"), dict) else {}
    hedonic = state.get("hedonic") if isinstance(state.get("hedonic"), dict) else {}
    return {
        # Legacy flat projection -- kept so every existing reader (sheet_state,
        # memory recall query, commit's emotional_context) works unchanged.
        "mood": label,
        "valence": v,
        "arousal": a,
        "goal": (str(goals[0].get("goal") or "")
                 if goals and isinstance(goals[0], dict) else ""),
        "active_concerns": state.get("active_concerns") or [],
        "stress": {
            "activation": _profile_float(stress.get("activation"), 0.0),
            "strain": _profile_float(stress.get("strain"), 0.0),
            "load": _profile_float(stress.get("load"), 0.0),
            "coping_mode": str(stress.get("coping_mode") or ""),
        },
        "hedonic": {
            "pain": _profile_float(hedonic.get("pain"), 0.0),
            "pleasure": _profile_float(hedonic.get("pleasure"), 0.0),
            "source": str(hedonic.get("source") or ""),
            "charge": _profile_float(hedonic.get("charge"), 0.0),
            "saturated": bool(hedonic.get("saturated")),
        },
        # Interior-depth: blended affect (surface + optional undercurrent over a
        # resting baseline) and this-beat wants. undercurrent starts null (the
        # graceful-degradation state); the baseline is the return attractor.
        # Canonical valence/arousal keys (what the model emits; affect.py is
        # tolerant on input and emits these on output).
        "affect": {
            "surface": {"label": label, "valence": v, "arousal": a},
            "undercurrent": None,
            "baseline": {"valence": v, "arousal": a},
        },
        "wants": [],
        "enacted_want": None,
        "suppressed_want": None,
    }

def character_standing_intentions(sheet: dict) -> list[dict]:
    """Authored STANDING intentions -- the character's defining, durable goals,
    read from the card's initial_state.goals in the runtime-intention context
    shape. These are always present in the character's decision context so it
    pursues them proactively (a captain's 'hold command of the crisis'), which
    is what keeps an authored character from defaulting to purely reactive
    behavior. Distinct from EMERGENT intentions that form at runtime via
    intent_ops; ids are namespaced 'ia<n>' so they never collide with the
    emergent 'i<n>' space."""
    state = normalize_character_data(sheet).get("initial_state", {})
    goals = state.get("goals") or []
    out = []
    for i, g in enumerate(goals, 1):
        # A plain string is the obvious way to author a goal, normalization
        # preserves it, and this used to skip it -- so a card written that way
        # got NO standing intentions at all and behaved purely reactively, with
        # nothing anywhere saying why. Accept both shapes rather than leaving a
        # silent gap between what the card format takes and what this reads.
        if isinstance(g, str):
            g = {"goal": g}
        if not isinstance(g, dict):
            continue
        text = str(g.get("goal") or "").strip()
        if not text:
            continue
        out.append({
            "id": f"ia{i}", "intent": text, "status": "active",
            "progress": 0.0, "authored": True,
            "priority": _float_or(g.get("priority"), 0.5),
        })
    return out

def character_projects(sheet: dict) -> list[dict]:
    """Authored PROJECTS (Tier 1.5) -- durable-but-not-eternal commitments,
    read from the card's psychology.projects in the runtime shape. The tier
    between the drive (eternal, placeless) and intentions (completable,
    abandonable, swept when dormant): a project can name a room and survives
    barren stretches, single successes, and the death of the tactics that
    serve it. See docs/design/DESIGN_LONG_TERM_GOALS.md.

    At most two, because scarcity is what makes the tier mean anything --
    the runtime cap (affect.PROJECT_CAP) holds the same line. Ids are
    namespaced 'pa<n>' so they never collide with runtime-adopted 'p<n>'.
    Accepts plain strings as well as dicts, for the same reason
    character_standing_intentions does: a card written the obvious way must
    not silently get nothing.
    """
    psych = normalize_character_data(sheet).get("psychology", {})
    out = []
    for i, p in enumerate(psych.get("projects") or [], 1):
        if isinstance(p, str):
            p = {"project": p}
        if not isinstance(p, dict):
            continue
        text = str(p.get("project") or p.get("goal") or "").strip()
        if not text:
            continue
        about = str(p.get("about") or "").strip().casefold()
        out.append({
            "id": f"pa{i}", "project": text,
            "about": about if about in ("world", "self") else "",
            "satisfied_when": str(p.get("satisfied_when") or "").strip(),
            "authored": True, "adopted_turn": 0,
        })
        if len(out) >= 2:
            break
    return out


def character_initial_stance(sheet: dict) -> dict:
    social = normalize_character_data(sheet).get("social", {})
    if isinstance(social.get("legacy_stance"), dict):
        return copy.deepcopy(social["legacy_stance"])
    baseline = social.get("baseline_stances", {}).get("unknown_person", {})
    return {
        "axes": {
            "trust_player": _float_or(baseline.get("trust"), 0.0),
            "warmth_player": _float_or(baseline.get("warmth"), 0.0),
            "threat_sensitivity": _float_or(baseline.get("threat_sensitivity"), 0.0),
        },
        "notes": "",
    }

def persona_name(sheet: dict) -> str:
    return str(normalize_persona_data(sheet).get("identity", {}).get("name") or "Player")

def persona_appearance(sheet: dict) -> str:
    return str(normalize_persona_data(sheet).get("embodiment", {}).get("visible", {})
               .get("summary") or "A person of unremarkable appearance.")


def persona_initial_outfit(sheet: dict) -> dict:
    return copy.deepcopy(
        normalize_persona_data(sheet).get(
            "initial_outfit", {"wearing": [], "state": [], "regions": {}})
    )

def persona_senses(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_persona_data(sheet).get("embodiment", {}).get("senses", []))

def persona_extra_parts(sheet: dict) -> list[dict]:
    """The persona's authored extra body parts -- see character_extra_parts."""
    return copy.deepcopy(
        normalize_persona_data(sheet).get("embodiment", {}).get(
            "extra_parts", [])
    )

def persona_abilities(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_persona_data(sheet).get("competence", {}).get("abilities", []))

def persona_private_history(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_persona_data(sheet).get("knowledge", {}).get("private_history", []))

def persona_public_history(sheet: dict) -> str:
    return str(normalize_persona_data(sheet).get("knowledge", {}).get("public_history", ""))

def persona_voice_setting(sheet: dict) -> str:
    return str(normalize_persona_data(sheet).get("narration", {}).get("voice_setting", ""))

def senses_as_text(senses: Any) -> str:
    if isinstance(senses, str):
        return senses or "ordinary senses"
    if not isinstance(senses, list):
        return "ordinary senses"
    parts = []
    for sense in senses:
        if not isinstance(sense, dict):
            if sense:
                parts.append(str(sense))
            continue
        channel = str(sense.get("channel") or "other")
        acuity = str(sense.get("acuity") or "ordinary")
        range_value = str(sense.get("range") or "ordinary")
        notes = str(sense.get("notes") or "").strip()
        part = f"{acuity} {channel}, {range_value} range"
        if notes:
            part += f" ({notes})"
        parts.append(part)
    return "; ".join(parts) if parts else "ordinary senses"

def visible_appearance_payload(sheet: dict) -> dict:
    return copy.deepcopy(normalize_character_data(sheet).get("embodiment", {}).get("visible", {}))

def character_export_document(sheet: dict, source: dict | None = None) -> dict:
    return {
        "schema": CHARACTER_SCHEMA,
        "version": CHARACTER_VERSION,
        "data": normalize_character_data(sheet),
        "source": source or {"format": "native", "original": None},
    }

def persona_export_document(sheet: dict, source: dict | None = None) -> dict:
    return {
        "schema": PERSONA_SCHEMA,
        "version": PERSONA_VERSION,
        "data": normalize_persona_data(sheet),
        "source": source or {"format": "native", "original": None},
    }


def character_card_warnings(sheet):
    """What is missing from a character CARD that will make them read as
    passive, as a list of human-readable strings.

    A sheet, not an import: this ran on one of the nine surfaces that create
    or edit a card, and the blank-card route produces by construction the
    exact sheet the first three warnings exist to catch -- empty drive, no
    goals, unset capacity -- while saying nothing. Every card-producing
    surface should ask; nothing about the answer depends on where the sheet
    came from.

    psychology.drive is where every proactive want comes from (prompts.py's
    WANTS AND GOALS rule) and initial_state.goals are the durable objectives
    on top of it. A card that supplies neither imports cleanly and then only
    ever reacts -- which looks like a dull character rather than a missing
    field, so it has to be said out loud at import time. The heuristic
    (LLM-free) path cannot invent either one by construction.
    """
    warnings = []
    psychology = sheet.get("psychology") or {}
    drive = psychology.get("drive") or {}
    if not str(drive.get("essence") or "").strip():
        warnings.append(
            "No drive was authored for this character, so they will react "
            "rather than pursue anything. Add psychology.drive in the "
            "character editor, or re-import with AI reinterpretation."
        )
    if not (sheet.get("initial_state") or {}).get("goals"):
        warnings.append(
            "No standing goals were authored, so this character has nothing "
            "they are trying to achieve between beats."
        )
    # Not a defect -- the default is exactly the pair every story ran on before
    # this dial existed, so an unset one cannot misbehave. It is named because
    # nobody looks for a field they do not know is there, and a character who
    # should be single-minded or should juggle will otherwise be authored at
    # the middle rung forever by omission.
    if not str(psychology.get("capacity") or "").strip():
        warnings.append(
            "No attentional capacity was authored, so this character holds the "
            "ordinary three wants and four intentions. Set psychology.capacity "
            "(narrow / focused / ordinary / broad / wide) to make them "
            "single-minded or to let them keep more in the air at once."
        )
    if _prose_names_a_part(sheet) and not (
            (sheet.get("embodiment") or {}).get("extra_parts")):
        warnings.append(
            "This card describes a body part in prose that is not declared in "
            "embodiment.extra_parts, so the engine cannot see, cover or touch "
            "it — nobody in the story will ever notice it. Add it under Extra "
            "body parts in the character editor, or re-import with AI "
            "reinterpretation."
        )
    return warnings


# Nouns whose presence in a body DESCRIPTION means the body is not the human
# default. Deliberately a small, high-precision list rather than an anatomy:
# this only decides whether to say a sentence to the author, and a false
# positive costs a wrong warning on a card that mentions a horn of ale.
# `_EXTRA_PART_PLACEMENTS` in character_schema is the sibling table -- it is
# for placing a declared part, this is for noticing an undeclared one.
_PART_WORDS = (
    "tail", "tails", "wing", "wings", "horn", "horns", "antler", "antlers",
    "tentacle", "tentacles", "halo", "fox ears", "cat ears", "wolf ears",
    "animal ears", "extra arms", "second pair of arms",
)



def _prose_names_a_part(sheet):
    """Does this card's BODY prose describe a part the schema would want?

    Only the visible-body fields, never psychology or history: a character
    who "turned tail" or values "taking the bull by the horns" has no anatomy
    in either sentence, and a warning about one would teach an author to stop
    reading warnings.
    """
    visible = ((sheet.get("embodiment") or {}).get("visible") or {})
    text = " ".join(str(visible.get(field) or "") for field in
                    ("summary", "build", "face", "hair", "eyes")).casefold()
    text += " " + " ".join(str(item or "") for item
                           in (visible.get("distinctive_features") or [])).casefold()
    return any(re.search(r"\b%s\b" % re.escape(word), text)
               for word in _PART_WORDS)
