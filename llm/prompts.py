"""Language-pack-backed system prompt assembly.

Only prompt selection, preset handling, and structural gating live here.
Authored human-language text belongs to ``language_packs/<id>``. Canonical
schema keys, enum values, payload paths, and step ids remain engine protocol.
"""

from __future__ import annotations

import json
import os
import re

from core.db import get_setting
from language_runtime import (
    DEFAULT_LANGUAGE,
    LanguagePackError,
    apply_prompt_policy,
    current_language_id,
    language_pack,
    normalize_language_id,
    require_language_pack,
)


def _language(language=None):
    return current_language_id.get() if language is None else language


def _prompt_card(language=None):
    """Return the selected pack's complete prompt card."""
    return language_pack(_language(language)).card("system_prompts")


_ENGLISH = _prompt_card("en")


def _assembled_sheets(card):
    """The Director sheets that are BUILT, never stored.

    A specialist sheet is its core plus one chunk per channel scoping grants,
    and the prose author's is its own segment list. Storing a finished body
    for those ids alongside the parts is one sheet with two spellings, free
    to drift -- and it had: English `director_spatial` was 1,518 characters
    short of its own assembly (the entire `comms_ops` chunk) while the prompt
    editor showed it as the sheet, and a preset saved from that view replaces
    the assembled sheet for every beat afterwards. The parts are the source;
    this is the only place the whole is made.
    """
    sheets = {
        f"director_{name}": (
            str(spec["core"]) + "".join(
                str(spec["chunks"][channel]) for channel in spec["order"]))
        for name, spec in card["specialists"].items()
    }
    sheets["director_resolve_lean"] = "".join(
        str(text) for _name, text in card["prose_author_sheet"])
    return sheets


def _prompt_bodies(card):
    """Every prompt body one pack publishes: stored ones plus assembled ones."""
    bodies = {pid: str(text) for pid, text in card["prompts"].items()}
    bodies.update(_assembled_sheets(card))
    return bodies


#: Prompt ids whose body is assembled rather than authored as one block. A
#: pack that stores a body under one of these has re-created the duplication.
ASSEMBLED_SHEET_IDS = frozenset(_assembled_sheets(_ENGLISH))

# Compatibility exports used by the prompt editor, project checks, benches,
# and tests. They are views of the English pack, not a second authored source.
DEFAULT_PROMPTS = {
    pid: apply_prompt_policy(text, "en", pid)
    for pid, text in _prompt_bodies(_ENGLISH).items()
}
# The one surviving eager English fragment, and it is read (story/importers.py).
# `extra_parts_note(language)` below is the localized accessor that should
# replace it: this constant resolves the ENGLISH card at import, so an import
# running under a Japanese story gets the English note.
EXTRA_PARTS_NOTE = str(_ENGLISH["extra_parts_note"])
SPECIALIST_PROMPT_SPECS = {
    name: {
        "core": apply_prompt_policy(
            str(spec["core"]), "en", f"director_{name}"),
        "order": tuple(spec["order"]),
        "chunks": dict(spec["chunks"]),
        "nsfw": bool(spec.get("nsfw")),
    }
    for name, spec in _ENGLISH["specialists"].items()
}
SPECIALISTS_BY_NAME = {
    name: f"director_{name}" for name in SPECIALIST_PROMPT_SPECS
}
_ENGLISH_PROSE_AUTHOR_RAW = tuple(
    (name, text) for name, text in _ENGLISH["prose_author_sheet"]
)
_ENGLISH_POLICY = language_pack("en").prompt_suffix(
    "director_resolve_lean")
PROSE_AUTHOR_SHEET = _ENGLISH_PROSE_AUTHOR_RAW + (
    ((None, "\n\n" + _ENGLISH_POLICY),) if _ENGLISH_POLICY else ()
)
PROSE_DUTY_CHUNKS = tuple(dict.fromkeys(
    name for name, _text in PROSE_AUTHOR_SHEET if name
))
CHARACTER_BLOCK_KEYS = tuple(
    (marker, tuple(paths))
    for marker, paths in _ENGLISH["character_block_keys"]
)
_PROSE_AUTHOR_OUTPUT_SHAPE = str(_ENGLISH["prose_author_output_shape"])


# A preset travels between installs as a self-describing document rather than
# a bare {pid: text} map, because the receiving engine has to know two things
# the map cannot say: that the file is a preset at all, and which language its
# sheets were authored in.
PRESET_FILE_KIND = "prompt_preset"
PRESET_FILE_VERSION = 1


def normalize_preset(value):
    """Read a stored preset in either the tagged or the pre-language shape.

    Presets predate story languages, so a stored value that is a bare
    ``{pid: text}`` map was authored against the English pack. Read it as
    English rather than discarding a host's saved work.
    """
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("prompts"), dict):
        raw_language, raw_prompts = value.get("language"), value["prompts"]
    else:
        raw_language, raw_prompts = DEFAULT_LANGUAGE, value
    try:
        language = normalize_language_id(raw_language)
    except LanguagePackError:
        # A forgiving read path: a preset whose pack was uninstalled, or whose
        # tag was hand-edited, must not break the prompt editor for everything
        # else. It simply stops matching any story until the tag is fixed.
        language = DEFAULT_LANGUAGE
    return {
        "language": language,
        "prompts": {str(pid): str(text)
                    for pid, text in raw_prompts.items()
                    if isinstance(pid, str) and isinstance(text, str)},
    }


def presets():
    """Every stored preset, normalized to the language-tagged shape."""
    stored = json.loads(get_setting("prompt_presets") or "{}")
    if not isinstance(stored, dict):
        return {}
    found = {}
    for name, value in stored.items():
        preset = normalize_preset(value)
        if preset is not None:
            found[str(name)] = preset
    return found


def active_preset():
    return get_setting("active_preset") or "Default"


def nsfw_enabled():
    return get_setting("nsfw_enabled") == "1"


#: The opening of a `{{fragment:<name>}}` reference. References are a PACK
#: authoring construct, resolved once at card load
#: (`language_runtime._resolve_prompt_fragments`); no resolver runs after
#: that, so any body still carrying the mark would reach a model verbatim.
FRAGMENT_REFERENCE_MARK = "{{fragment"


def unresolvable_fragment_references(prompts_map):
    """Prompt ids whose body carries a fragment reference nothing will resolve.

    Preset bodies are applied AFTER card load, so this is where a reference a
    host typed into the editor must be refused -- loudly, at save/import time,
    not as literal `{{fragment:...}}` text in a sheet every story reads.
    """
    return sorted(str(pid) for pid, text in prompts_map.items()
                  if isinstance(text, str) and FRAGMENT_REFERENCE_MARK in text)


def prompt_fragment(name, language=None):
    """Fetch a named authored fragment from one language pack."""
    card = _prompt_card(language)
    try:
        return str(card[name])
    except KeyError as exc:
        raise KeyError(f"language pack has no prompt fragment {name!r}") from exc


def extra_parts_note(language=None):
    return prompt_fragment("extra_parts_note", language)


def interpret_delegation_note(language=None):
    return prompt_fragment("interpret_delegation_note", language)


def _preset_override(pid, language=None):
    """A host preset's whole-sheet replacement for one prompt, or None.

    A preset overrides only the language it was authored in. A sheet is
    human-language text, so an English preset replacing a Japanese prompt does
    not merely change the instructions -- it changes which language the model
    is being addressed in, and drags that sheet's own schema policy along with
    it. Falling through to the pack is the mildest reading.
    """
    name = active_preset()
    if name == "Default":
        return None
    preset = presets().get(name)
    if preset is None:
        return None
    try:
        selected = normalize_language_id(_language(language))
    except LanguagePackError:
        return None
    if preset["language"] != selected:
        return None
    return preset["prompts"].get(pid) or None


def default_prompts_for(language=None):
    """One language's editable prompt bodies, as the prompt editor shows them.

    ``DEFAULT_PROMPTS`` is this for English. The editor needs the same view of
    any story language, or a pack's sheets could never be edited or saved as a
    preset at all.
    """
    selected = _language(language)
    return {pid: apply_prompt_policy(text, selected, pid)
            for pid, text in _prompt_bodies(_prompt_card(selected)).items()}


def preset_export_document(name):
    """Return one stored preset as a portable, self-describing document."""
    preset = presets().get(str(name))
    if preset is None:
        raise KeyError(f"no prompt preset named {name!r}")
    return {
        "kind": PRESET_FILE_KIND,
        "version": PRESET_FILE_VERSION,
        "name": str(name),
        "language": preset["language"],
        # Bodies travel exactly as the host authored them, schema policy and
        # all. The language tag is what keeps an English sheet out of a
        # Japanese story, so the text itself needs no rewriting to be safe.
        "prompts": dict(preset["prompts"]),
    }


def preset_import_document(document, name=None):
    """Validate a portable preset document, returning ``(name, preset)``.

    Fails closed on every axis -- wrong kind, newer file version, uninstalled
    language, unknown prompt id. A preset that imports with half its sheets
    silently dropped is worse than one that refuses to import, because the
    dropped half reappears as a model behaving oddly many beats later.
    """
    if not isinstance(document, dict):
        raise ValueError("a preset file must contain an object")
    if str(document.get("kind") or "") != PRESET_FILE_KIND:
        raise ValueError("this file is not a prompt preset")
    try:
        version = int(document.get("version"))
    except (TypeError, ValueError):
        raise ValueError("preset file has no usable version") from None
    if version > PRESET_FILE_VERSION:
        raise ValueError(
            f"preset file version {version} is newer than this engine "
            f"understands ({PRESET_FILE_VERSION})")
    selected = str(
        name if name is not None else document.get("name") or "").strip()
    if not selected or selected == "Default":
        raise ValueError("a preset needs a name of its own")
    # require_ rather than the forgiving read: a tag that cannot be resolved
    # now would store a preset that silently matches no story ever.
    language = require_language_pack(
        document.get("language") or DEFAULT_LANGUAGE, capability="story").id
    raw = document.get("prompts")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("preset file carries no prompts")
    unknown = sorted(str(pid) for pid in raw if str(pid) not in DEFAULT_PROMPTS)
    if unknown:
        raise ValueError(
            "preset file names prompts this engine does not have: "
            + ", ".join(unknown[:8]))
    bad = sorted(str(pid) for pid, text in raw.items()
                 if not isinstance(text, str))
    if bad:
        raise ValueError(
            "preset bodies must be text: " + ", ".join(bad[:8]))
    unresolvable = unresolvable_fragment_references(raw)
    if unresolvable:
        raise ValueError(
            "preset bodies carry {{fragment:...}} references, which only a "
            "language pack's card can resolve; write the text itself in: "
            + ", ".join(unresolvable[:8]))
    return selected, {
        "language": language,
        "prompts": {str(pid): str(text) for pid, text in raw.items()},
    }


def unique_preset_name(name, existing):
    """Number an imported preset rather than overwrite a host's saved sheet."""
    if name not in existing:
        return name
    for suffix in range(2, 1000):
        candidate = f"{name} ({suffix})"
        if candidate not in existing:
            return candidate
    raise ValueError(f"too many presets already named {name!r}")


def specialist_prompt(name, scope, language=None):
    """Assemble one scoped specialist sheet from the selected pack."""
    card = _prompt_card(language)
    spec = card["specialists"][name]
    pid = f"director_{name}"
    override = _preset_override(pid, language)
    if override is not None:
        sheet = override
    else:
        granted = set(scope or ())
        parts = [spec["core"]]
        parts.extend(spec["chunks"][channel]
                     for channel in spec["order"] if channel in granted)
        sheet = "".join(parts)
    if spec.get("nsfw") and nsfw_enabled():
        sheet += str(card["nsfw_overlay"])
    return apply_prompt_policy(sheet, _language(language), pid)


def _localized_prose_author_sheet(language=None):
    return tuple((name, text)
                 for name, text in _prompt_card(language)["prose_author_sheet"])


def prose_author_prompt(scope, language=None):
    """Assemble the scoped prose-author sheet from the selected pack."""
    override = _preset_override("director_resolve_lean", language)
    if override is not None:
        sheet = override
    else:
        localized = _localized_prose_author_sheet(language)
        duty_names = tuple(dict.fromkeys(
            name for name, _text in localized if name
        ))
        granted = set(duty_names if scope is None else scope)
        sheet = "".join(text for name, text in localized
                        if name is None or name in granted)
    if nsfw_enabled():
        sheet += str(_prompt_card(language)["nsfw_overlay"])
    return apply_prompt_policy(
        sheet, _language(language), "director_resolve_lean")


# Restore part of the pre-compaction character call for controlled A/B
# measurement. This is code/configuration, not human-language content.
_PAYLOAD_LEGACY_ARMS = frozenset(
    part for part in re.split(
        r"[,\s]+", str(os.environ.get("SONDER_PAYLOAD_LEGACY", "")).casefold())
    if part
)


def payload_legacy(part):
    return "all" in _PAYLOAD_LEGACY_ARMS or part in _PAYLOAD_LEGACY_ARMS


def _payload_has(payload, path):
    for sep in ("[].", "{}."):
        head, found, tail = path.partition(sep)
        if not found:
            continue
        node = _payload_node(payload, head)
        rows = ((node or {}).values() if sep == "{}." else [node or []])
        for row in rows:
            group = row if isinstance(row, list) else [row]
            if any(isinstance(item, dict) and tail in item
                   and _is_stamped(item[tail]) for item in group):
                return True
        return False
    return _is_stamped(_payload_node(payload, path))


def _is_stamped(value):
    return value is not None and value not in ("", [], {})


def _payload_node(payload, path):
    node = payload
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def character_prompt(payload, base=None, language=None):
    """Subtract inapplicable paragraphs from the localized character sheet."""
    text = get_prompt("character", language=language) if base is None else base
    if not isinstance(payload, dict) or payload_legacy("prompt"):
        return text
    block_keys = tuple(
        (marker, tuple(paths))
        for marker, paths in _prompt_card(language)["character_block_keys"]
    ) if base is None else CHARACTER_BLOCK_KEYS
    lines = text.split("\n")
    keep = []
    for line in lines:
        stripped = line.strip()
        entry = next((item for item in block_keys
                      if stripped.startswith(item[0])), None)
        if entry and not any(_payload_has(payload, key) for key in entry[1]):
            continue
        keep.append(line)
    if not keep:
        return text
    return re.sub(r"\n{3,}", "\n\n", "\n".join(keep))


def get_prompt_body(pid, language=None):
    """Return localized authored instructions before the universal policy."""
    override = _preset_override(pid, language)
    if override is not None:
        base = override
    else:
        prompts = _prompt_bodies(_prompt_card(language))
        try:
            base = prompts[pid]
        except KeyError as exc:
            raise KeyError(
                f"language pack {language!r} has no system prompt {pid!r}"
            ) from exc
    card = _prompt_card(language)
    if nsfw_enabled() and pid in set(card["nsfw_prompt_ids"]):
        base += str(card["nsfw_overlay"])
    return base


def get_prompt(pid, language=None):
    """Return one complete localized prompt with the schema contract applied."""
    return apply_prompt_policy(
        get_prompt_body(pid, language), _language(language), pid)
