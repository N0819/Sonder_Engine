# character_schema.py
"""Versioned, context-agnostic character and persona schemas."""

from __future__ import annotations

import copy
import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field, validator

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

    @validator("traits", pre=True)
    def _traits(cls, value):
        if isinstance(value, (str, dict)):
            value = [value]
        return [
            {"name": item} if isinstance(item, str) else item
            for item in (value or [])
            if isinstance(item, (str, dict))
        ]

    @validator("values", pre=True)
    def _values(cls, value):
        if isinstance(value, (str, dict)):
            value = [value]
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


def _normalize_psychology(value: Any) -> dict:
    """Typed, tolerant normalization for the durable psychology contract.

    Imported cards and older native sheets remain accepted, but every live
    reader receives the v3 shape. Unknown extension keys survive because the
    profile models allow extras.
    """
    raw = value if isinstance(value, dict) else {}
    result = PsychologyProfile.parse_obj(raw).dict()

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
        BeliefProfile.parse_obj(
            {"belief": item} if isinstance(item, str) else item
        ).dict()
        for item in (self_model.get("beliefs") or [])
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
        CopingStrategyProfile.parse_obj(
            {"name": item, "response": item} if isinstance(item, str) else item
        ).dict()
        for item in (coping.get("strategies") or [])
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
    associations = learning.get("associations") or []
    learning["associations"] = [
        AssociationProfile.parse_obj(item).dict()
        for item in associations if isinstance(item, dict)
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
    if value is None:
        return []
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
    """Normalize authored starting clothes into the live attire shape."""
    if isinstance(value, dict):
        wearing = value.get("wearing")
        if wearing is None:
            wearing = value.get("items") or value.get("outfit")
        state = value.get("state")
    else:
        wearing, state = value, []
    return {
        "wearing": _outfit_items(wearing),
        "state": _outfit_items(state),
    }


def default_character_data(name: str = "Unnamed") -> dict:
    result = {
        "identity": {
            "uid": new_uid("char"),
            "name": name,
            "aliases": [],
            "pronouns": {"subject": "they", "object": "them", "possessive": "their"},
        },
        "initial_outfit": {"wearing": [], "state": []},
        "simulation": {"tier": "mid", "temperature": 0.8, "sampler": {},
                       "curiosity": 0.5},
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
        "initial_outfit": {"wearing": [], "state": []},
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
        },
        "embodiment": {
            "senses": _legacy_senses(value.get("senses")),
            "visible": {
                "summary": str(value.get("appearance") or "A person of unremarkable appearance."),
                "build": "", "face": "", "hair": "", "eyes": "",
                "distinctive_features": [],
            },
            "latent": copy.deepcopy(value.get("latent_capabilities") or []),
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
        },
        "competence": {"abilities": _legacy_abilities(value.get("abilities"))},
        "knowledge": {
            "public_history": str(value.get("public_history") or ""),
            "private_history": _legacy_private_history(value.get("private_history")),
        },
        "narration": {"voice_setting": str(value.get("voice_setting") or "")},
    }

# ---- Accessors ----

def character_name(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("identity", {}).get("name") or "Unnamed")

def character_tier(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("simulation", {}).get("tier", "mid"))

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
            "initial_outfit", {"wearing": [], "state": []})
    )

def character_senses(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_character_data(sheet).get("embodiment", {}).get("senses", []))

def character_interoception(sheet: dict) -> dict:
    return copy.deepcopy(
        normalize_character_data(sheet).get("embodiment", {}).get("interoception", {})
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
            "initial_outfit", {"wearing": [], "state": []})
    )

def persona_senses(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_persona_data(sheet).get("embodiment", {}).get("senses", []))

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
