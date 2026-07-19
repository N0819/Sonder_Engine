# character_schema.py
"""Versioned, context-agnostic character and persona schemas."""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any

CHARACTER_SCHEMA = "fiction-engine.character"
CHARACTER_VERSION = 2
PERSONA_SCHEMA = "fiction-engine.persona"
PERSONA_VERSION = 2

def new_uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"

def default_character_data(name: str = "Unnamed") -> dict:
    return {
        "identity": {
            "uid": new_uid("char"),
            "name": name,
            "aliases": [],
            "pronouns": {"subject": "they", "object": "them", "possessive": "their"},
        },
        "simulation": {"tier": "mid", "temperature": 0.8, "sampler": {}},
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
        "psychology": {
            "traits": [],
            "values": [],
            "self_model": {
                "summary": "",
                "protected_beliefs": [],
                "pride_triggers": [],
                "shame_triggers": [],
            },
            "coping": {"under_stress": [], "default_conflict_style": ""},
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
        },
        "opening": {"first_message": ""},
    }

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
                    "valence": float(value.get("valence", 0.0)),
                    "arousal": float(value.get("arousal", 0.0))}
        return {"label": str(value.get("mood") or "neutral"),
                "valence": float(value.get("valence", 0.0)),
                "arousal": float(value.get("arousal", 0.0))}
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
        return [copy.deepcopy(item) for item in value if isinstance(item, dict)]
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
    summary = str(visible.get("summary", "")).strip()
    is_default = not summary or summary == "A person of unremarkable appearance."
    extra_visual = []
    for key in ("build", "face", "hair", "eyes", "complexion", "height",
                "weight", "clothing", "body_type", "ethnicity_descriptor"):
        val = embodiment.pop(key, None)
        if val:
            label = key.replace("_", " ").capitalize()
            extra_visual.append(f"{label}: {val}")
    features = embodiment.pop("distinct_features", None)
    if features and isinstance(features, list):
        extra_visual.append("Distinctive features: " + ", ".join(features))
    if is_default and extra_visual:
        visible["summary"] = ". ".join(extra_visual) + "."
    visible.setdefault("build", "")
    visible.setdefault("face", "")
    visible.setdefault("hair", "")
    visible.setdefault("eyes", "")
    visible.setdefault("distinctive_features", [])
    return target_dict

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
        name = (value.get("identity") or {}).get("name") or value.get("name") or "Unnamed"
        result = _deep_defaults(default_character_data(name), value)
        _coerce_latent(result)
        _coerce_appearance(result)
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
    return {
        "identity": {
            "uid": str(value.get("uid") or new_uid("char")),
            "name": name,
            "aliases": _list(value.get("aliases")),
            "pronouns": copy.deepcopy(value.get("pronouns") or {
                "subject": "they", "object": "them", "possessive": "their"}),
        },
        "simulation": {
            "tier": str(value.get("tier") or "mid"),
            "temperature": float(value.get("temperature", 0.8)),
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
        },
        "psychology": {
            "traits": _legacy_traits(core),
            "values": _legacy_values(core),
            "self_model": {
                "summary": str(core.get("self_image") or ""),
                "protected_beliefs": [],
                "pride_triggers": [],
                "shame_triggers": [],
            },
            "coping": {"under_stress": [], "default_conflict_style": ""},
        },
        "social": {
            "voice": _legacy_voice(value.get("voice")),
            "baseline_stances": {
                "unknown_person": {
                    "trust": float((stance.get("axes") or {}).get("trust_player", 0.0)),
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
        },
        "opening": {"first_message": str(value.get("first_message") or "")},
    }

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

def character_temperature(sheet: dict) -> float:
    return float(normalize_character_data(sheet).get("simulation", {}).get("temperature", 0.8))

def character_sampler(sheet: dict) -> dict:
    return copy.deepcopy(normalize_character_data(sheet).get("simulation", {}).get("sampler", {}))

def character_appearance(sheet: dict) -> str:
    return str(normalize_character_data(sheet).get("embodiment", {}).get("visible", {})
               .get("summary") or "A person of unremarkable appearance.")

def character_senses(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_character_data(sheet).get("embodiment", {}).get("senses", []))

def character_abilities(sheet: dict) -> list[dict]:
    return copy.deepcopy(normalize_character_data(sheet).get("competence", {}).get("abilities", []))

def character_voice(sheet: dict) -> dict:
    return copy.deepcopy(normalize_character_data(sheet).get("social", {}).get("voice", {}))

def character_psychology(sheet: dict) -> dict:
    return copy.deepcopy(normalize_character_data(sheet).get("psychology", {}))

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
    mood = state.get("mood") or {}
    goals = state.get("goals") or []
    return {
        "mood": mood.get("label") or "neutral",
        "valence": float(mood.get("valence", 0.0)),
        "arousal": float(mood.get("arousal", 0.0)),
        "goal": (str(goals[0].get("goal") or "")
                 if goals and isinstance(goals[0], dict) else ""),
        "active_concerns": state.get("active_concerns") or [],
    }

def character_initial_stance(sheet: dict) -> dict:
    social = normalize_character_data(sheet).get("social", {})
    if isinstance(social.get("legacy_stance"), dict):
        return copy.deepcopy(social["legacy_stance"])
    baseline = social.get("baseline_stances", {}).get("unknown_person", {})
    return {
        "axes": {
            "trust_player": float(baseline.get("trust", 0.0)),
            "warmth_player": float(baseline.get("warmth", 0.0)),
            "threat_sensitivity": float(baseline.get("threat_sensitivity", 0.0)),
        },
        "notes": "",
    }

def persona_name(sheet: dict) -> str:
    return str(normalize_persona_data(sheet).get("identity", {}).get("name") or "Player")

def persona_appearance(sheet: dict) -> str:
    return str(normalize_persona_data(sheet).get("embodiment", {}).get("visible", {})
               .get("summary") or "A person of unremarkable appearance.")

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