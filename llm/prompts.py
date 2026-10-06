"""Language-pack-backed system prompt assembly.

Only prompt selection, preset handling, and structural gating live here.
Authored human-language text belongs to ``language_packs/<id>``. Canonical
schema keys, enum values, payload paths, and step ids remain engine protocol.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping

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

#: `<channel>__<part>`: a part of a big channel's encoder chunk, shipped only
#: when the decision model says the beat needs it (`encoder_parts`).
ENCODER_PART_SEP = "__"

#: The prompt editor's ids for the encoder's card: `encoder.core`, one
#: `encoder.<channel>` per chunk and one `encoder.<channel>__<part>` per part.
#: PIECES, never the sheet: the sheet is assembled per beat from the channels
#: the decision model grants, so a preset of the assembly would replace every
#: beat's scoping with one fixed list -- the "one sheet, two spellings" defect
#: the causal hands' assembled sheets had in the editor.
ENCODER_PIECE_PREFIX = "encoder."

#: The Director's two stages, whose prose sheets the editor shows whole.
PROSE_DIRECTOR_STAGES = ("interpret", "resolve")


def _prompt_bodies(card):
    """Every prompt body one pack STORES under `prompts`. The turn Director's
    sheets live in their own families and are added for the editor by
    `_director_sheets`."""
    return {pid: str(text) for pid, text in card["prompts"].items()}


def encoder_pieces(card):
    """The encoder card's keys in the order its sheet is assembled: the core,
    then each channel in canonical owner order, each followed by its parts.
    A piece no order reaches comes last rather than going unpublished."""
    encoder = card["encoder"]
    keys = ["core"]
    for spec in card["specialists"].values():
        for channel in spec["order"]:
            if channel in encoder and channel not in keys:
                keys.append(channel)
                prefix = f"{channel}{ENCODER_PART_SEP}"
                keys.extend(part for part in encoder if part.startswith(prefix))
    keys.extend(key for key in encoder if key not in keys)
    return keys


def _director_sheets(card, language):
    """The turn Director's sheets as the prompt editor shows them (owner,
    2026-09-28: "prompt editor should show director and encoder").

    The two prose sheets whole, with the schema policy applied as every stored
    prompt's is, under the ids `prose_director_prompt` already reads a preset
    by. The encoder card piece by piece and BARE: a piece is spliced into the
    middle of an assembled sheet, and the policy belongs once, at its end."""
    out = {}
    for stage in PROSE_DIRECTOR_STAGES:
        pid = f"prose_director_{stage}"
        out[pid] = apply_prompt_policy(
            str(card["prose_contract"][f"director_{stage}"]), language, pid)
    encoder = card["encoder"]
    for key in encoder_pieces(card):
        out[ENCODER_PIECE_PREFIX + key] = str(encoder[key])
    return out


# Compatibility exports used by the prompt editor, project checks, benches,
# and tests. They are views of the English pack, not a second authored source.
DEFAULT_PROMPTS = {
    pid: apply_prompt_policy(text, "en", pid)
    for pid, text in _prompt_bodies(_ENGLISH).items()
}
DEFAULT_PROMPTS.update(_director_sheets(_ENGLISH, "en"))
# The one surviving eager English fragment, and it is read (story/importers.py).
# `extra_parts_note(language)` below is the localized accessor that should
# replace it: this constant resolves the ENGLISH card at import, so an import
# running under a Japanese story gets the English note.
EXTRA_PARTS_NOTE = str(_ENGLISH["extra_parts_note"])
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


def nsfw_overlay(pid, card):
    """The adult overlay this prompt id receives from one card, or ``""``.

    `nsfw_prompt_ids` is the whole roster. It was one of three answers to the
    same question (B11): the specialists consulted a per-hand
    `specialists.<name>.nsfw` flag, the prose author appended the overlay
    unconditionally, and `get_prompt_body` read the roster -- so a pack could
    grant `director_body` the overlay in one spelling and withhold it in the
    other, with nothing anywhere objecting. Every path that assembles a sheet
    asks here, by the prompt id the sheet is stored and edited under.
    """
    if not nsfw_enabled():
        return ""
    return str(card["nsfw_overlay"]) if pid in set(
        card["nsfw_prompt_ids"]) else ""


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
    card = _prompt_card(selected)
    out = {pid: apply_prompt_policy(text, selected, pid)
           for pid, text in _prompt_bodies(card).items()}
    out.update(_director_sheets(card, selected))
    return out


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


def prose_director_prompt(stage, language=None):
    """The prose-contract Director's sheet for `stage` (interpret|resolve).

    The sheet `agents/director_prose.py` runs at every stage after the
    opening -- the only Director contract since 2026-09-27: the Director
    writes the beat as an objective account and nothing else. It takes the
    adult overlay when the roster names it, as every other sheet does (owner,
    2026-09-28). The causal sheet carried none because it wrote no account;
    this one does, and the encoder can record only what the account says
    happened."""
    pid = f"prose_director_{stage}"
    card = _prompt_card(language)
    override = _preset_override(pid, language)
    sheet = override if override is not None else str(
        card["prose_contract"][f"director_{stage}"])
    return apply_prompt_policy(sheet + nsfw_overlay(pid, card),
                               _language(language), pid)


def encoder_parts(channel, language=None):
    """The part names of one channel's encoder chunk, in card order."""
    prefix = f"{channel}{ENCODER_PART_SEP}"
    return tuple(name for name in _prompt_card(language)["encoder"]
                 if name.startswith(prefix))


def prose_contract_text(name, language=None):
    """One text of the prose contract's own family (`prose_contract.<name>`):
    a sheet, a section added to the encoder's, or a decision-model check."""
    return str(_prompt_card(language)["prose_contract"][name])


def affect_appraisal_text(name, language=None):
    """One question of the decision model's affect appraisal
    (`affect_appraisal.<name>`, see `mind/affect_appraisal.py`)."""
    return str(_prompt_card(language)["affect_appraisal"][name])


def affect_appraisal_options(option_set, language=None):
    """One of the appraisal's option sets, `{key: value}` in the card's
    order: the keys are protocol; a value is a label, or -- for the pole
    words of `dimensions` -- a `{low, high}` mapping of labels."""
    def plain(value):
        if isinstance(value, Mapping):
            return {str(k): plain(v) for k, v in value.items()}
        return str(value)
    return {str(k): plain(v) for k, v in
            _prompt_card(language)["affect_appraisal"]["options"][option_set].items()}


def character_jev_text(name, language=None):
    """One question the decision model asks around a bare character call
    (`character_jev.<name>`, see `mind/character_jev.py`)."""
    return str(_prompt_card(language)["character_jev"][name])


def character_jev_options(option_set, language=None):
    """One of those questions' option sets, `{key: label}` in the card's
    order: the keys are protocol, the labels are what the model reads."""
    return {str(k): str(v) for k, v in
            _prompt_card(language)["character_jev"]["options"][option_set].items()}


def character_tools_text(name, language=None):
    """One description of the lookups a character may make mid-thought
    (`character_tools.<name>`, `agents/character_tools.tool_specs`): the
    tools' names and parameters are protocol, what they say the pack's."""
    return str(_prompt_card(language)["character_tools"][name])


def character_bare_module(name, language=None):
    """One gated section of the bare character card (`character_bare.<name>`):
    shipped only when a detector says the moment calls for it."""
    return str(_prompt_card(language)["character_bare"][name])


def bare_character_prompt(language=None):
    """The bare character card, its identity line placed just before the
    output shape (`_relocate_character_identity`), so the card before it is
    the same for every mind and caches as a prefix."""
    return _relocate_character_identity(
        get_prompt("character_bare", language=language),
        anchors=('"want"', '"sequence"'))


#: The longest definition `encoder_definition` returns, cut back to a
#: sentence end.
ENCODER_DEFINITION_CHARS = 420


def encoder_definition(channel, language=None):
    """What a channel's record holds, in the encoder card's own words: the
    opening paragraph of its `encoder.<channel>` chunk, cut back to the last
    sentence end within `ENCODER_DEFINITION_CHARS`. It is the contract the
    encoder writes by, so a check asking whether a write is missing or wrong
    judges by the same rule -- not by the routing question, which is written
    to grant the tool generously ("a cry" as a signal, measured 2026-09-24)."""
    text = str((_prompt_card(language).get("encoder") or {}).get(channel) or "").strip()
    first = text.split("\n\n", 1)[0].strip()
    if len(first) <= ENCODER_DEFINITION_CHARS:
        return first
    head = first[:ENCODER_DEFINITION_CHARS]
    cut = max(head.rfind(". "), head.rfind("。"), head.rfind(".\n"))
    return head[:cut + 1] if cut > 0 else head


def unified_specialist_prompt(channels, language=None, parts=None, *,
                              extensions=()):
    """The prose contract's encoder sheet, from its own card.

    The core, then every granted channel's `encoder.<channel>` chunk in
    canonical hand order, each followed by whichever of its parts are in
    `parts` -- or by all of them when `parts` is None, which is what a
    caller with no decision to pass on gets (fail open: a longer sheet,
    never a missing rule). The card is written for ONE encoder that writes
    every channel itself: none of the several-hands vocabulary the causal
    specialists' chunks carry (rows, results, verdicts, routing work to
    another hand) reaches it, which is why it is a card of its own
    (owner, 2026-09-24: "specific prompts for this version of the director
    sound necessary? Otherwise we get a lot of weird confusing wording").
    The adult overlay is appended when any hand whose channel shipped would
    have received it on its own sheet.

    `extensions` are the granted channels of this story's extensions, as
    `(channel, instructions, list_shaped)` (`api.add_director_channel`):
    after the engine's chunks, under the card's own header
    (`prose_contract.encoder_extensions`), each channel's name and its
    extension's instructions verbatim. Their names are the grant: a channel
    in `channels` with no entry here reaches no sheet."""
    card = _prompt_card(language)
    encoder = card["encoder"]
    granted = set(channels or ())
    picked = None if parts is None else set(parts)

    def piece(key):
        # A host preset edits the card piece by piece (`encoder.<key>` in the
        # prompt editor); the assembly and its scoping stay the engine's.
        override = _preset_override(ENCODER_PIECE_PREFIX + key, language)
        return str(override if override is not None else encoder[key])

    sections = [piece("core")]
    hands = []
    for name, spec in card["specialists"].items():
        shipped = [channel for channel in spec["order"] if channel in granted]
        if shipped:
            hands.append(name)
        for channel in shipped:
            sections.append(piece(channel))
            prefix = f"{channel}{ENCODER_PART_SEP}"
            sections.extend(
                piece(part) for part in encoder
                if part.startswith(prefix) and (picked is None or part in picked))
    if extensions:
        block = [str(card["prose_contract"]["encoder_extensions"]).strip("\n")]
        for channel, instructions, list_shaped in extensions:
            head = f"`{channel}`" + (" `(list)`" if list_shaped else "")
            block.append(f"{head}\n{str(instructions).strip()}")
        sections.append("\n\n".join(block))
    sheet = "\n\n".join(section.strip("\n") for section in sections) + "\n"
    overlay = next((nsfw_overlay(f"director_{name}", card) for name in hands
                    if nsfw_overlay(f"director_{name}", card)), "")
    sheet += overlay
    return apply_prompt_policy(sheet, _language(language), "director_specialist")


#: The place-topology channels the prose contract's room author owns, in the
#: spatial hand's chunk order. Their chunks ship verbatim.
ROOM_AUTHOR_CHANNELS = ("rooms", "remove_rooms", "remove_adjacent")


def room_author_prompt(language=None):
    """The prose contract's parallel room author: its core plus the spatial
    hand's room-topology chunks, unmodified. Carries the adult overlay when
    the spatial hand's own sheet would."""
    card = _prompt_card(language)
    spec = card["specialists"]["spatial"]
    parts = [str(card["prose_contract"]["room_author"])]
    parts.extend(str(spec["chunks"][channel]) for channel in spec["order"]
                 if channel in ROOM_AUTHOR_CHANNELS)
    sheet = "\n\n".join(part.strip("\n") for part in parts) + "\n"
    sheet += nsfw_overlay("director_spatial", card)
    return apply_prompt_policy(sheet, _language(language), "director_rooms")


def room_reconcile_prompt(language=None):
    """The room author's short closing call: name its own features that the
    encoder also wrote as objects this beat."""
    return apply_prompt_policy(
        str(_prompt_card(language)["prose_contract"]["room_reconcile"]),
        _language(language), "director_rooms_reconcile")


def jev_channel_questions(channels, language=None):
    """`{channel: question text}` for the channels asked of the decision
    model -- an encoder part (`<channel>__<part>`) is asked by its own name.
    A channel with no authored question is simply not asked -- it cannot be
    selected, and the caller's fail-open covers it."""
    questions = _prompt_card(language).get("jev_questions") or {}
    return {channel: str(questions[channel])
            for channel in channels if channel in questions}


def jev_question(key, language=None, **fields):
    """One decision-model question that is not a channel's -- `walk_stopped`
    -- with each `{field}` filled from `fields`. "" when the pack has none,
    so the caller asks nothing rather than a question with holes in it."""
    text = str((_prompt_card(language).get("jev_questions") or {}).get(key) or "").strip()
    for key, value in fields.items():
        text = text.replace("{%s}" % key, str(value))
    return text


# Restore part of the pre-compaction character call for controlled A/B
# measurement. This is code/configuration, not human-language content.
_PAYLOAD_LEGACY_ARMS = frozenset(
    part for part in re.split(
        r"[,\s]+", str(os.environ.get("SONDER_PAYLOAD_LEGACY", "")).casefold())
    if part
)


def payload_legacy(part):
    return "all" in _PAYLOAD_LEGACY_ARMS or part in _PAYLOAD_LEGACY_ARMS


def _relocate_character_identity(text, anchors=('"state"', '"sequence"')):
    """Move the name-bearing line behind the stable character contract.

    The authored sentence is preserved byte-for-byte.  Only its position
    changes: a character name 32 characters into a 62 KB system message made
    the reusable prefix unique per character.  Put it immediately before the
    output contract so the schema-shaped final instruction remains final.
    This works for every language pack without adding an English replacement
    sentence to translated text.
    """
    lines = text.split("\n")
    try:
        identity_index = next(
            index for index, line in enumerate(lines) if "{name}" in line)
    except StopIteration:
        return text
    identity = lines.pop(identity_index)
    # Protocol keys stay English in every translated pack.  Detect the output
    # contract by its shape rather than by an authored-language heading.
    # Anchored on two keys in the compact contract.  This stays language-free:
    # protocol keys remain English in every translated pack.
    output_index = next(
        (index for index, line in enumerate(lines)
         if all(anchor in line for anchor in anchors)),
        len(lines),
    )
    lines.insert(output_index, identity)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")


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
    return base + nsfw_overlay(pid, _prompt_card(language))


#: A section of the narrator's sheet that teaches ONE optional payload
#: field opens with a marker line naming the field(s) and closes with
#: `[[core]]`; text under no marker is the core every beat reads. The
#: markers are the sheet's own and never reach a model.
_SECTION_MARK = re.compile(r"^\[\[(?:when:\s*([A-Za-z0-9_,\s]+)|core)\]\]\s*$",
                           re.MULTILINE)


def narrator_sections(body):
    """``[(fields, text), ...]`` -- the sheet cut at its markers. ``fields``
    is the frozenset of payload keys a section teaches, empty for the core.
    A sheet with no markers is one core section, which is what the
    Japanese pack is until it adopts them."""
    out, fields, start = [], frozenset(), 0
    for match in _SECTION_MARK.finditer(str(body or "")):
        text = body[start:match.start()]
        if text:
            out.append((fields, text))
        named = match.group(1)
        fields = frozenset(f.strip() for f in named.split(",") if f.strip()) \
            if named else frozenset()
        start = match.end()
    tail = body[start:]
    if tail:
        out.append((fields, tail))
    return out


def narrator_prompt(present, language=None):
    """The narrator's sheet for ONE beat: its core plus every section whose
    payload field this beat carries. THE SAME MINIATURISATION THE HANDS
    GOT: a specialist loads its core and one chunk per granted channel; the
    narrator loaded 42 KB every beat, eleven sections of which describe a
    field the payload carries only sometimes (portal states, attire, the
    spatial frame, beat time, sensory channels, exemplars, correction notes,
    dialogue placeholders...). ``present`` is the set of keys in the call
    payload. A preset's replacement sheet is cut by the same markers, and a
    sheet with none is sent whole."""
    body = get_prompt_body("narrator", language)
    present = {str(k) for k in (present or ())}
    kept = [text for fields, text in narrator_sections(body)
            if not fields or fields & present]
    return apply_prompt_policy("".join(kept), _language(language), "narrator")


def get_prompt(pid, language=None):
    """Return one complete localized prompt with the schema contract applied."""
    return apply_prompt_policy(
        get_prompt_body(pid, language), _language(language), pid)
