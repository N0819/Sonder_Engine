"""Installed language packs and per-story language selection.

The engine's stored protocol remains language-neutral: schema keys, enum
values, step ids and ledger vocabulary are never translated.  A language pack
owns only human-language recognition, rendering, prompts and UI copy around
those canonical values.

Packs are data by default.  A pack may name a trusted renderer adapter from
the in-process registry; merely placing Python in a pack directory never
executes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import contextlib
import contextvars
import importlib
import json
import logging
import os
from pathlib import Path

import re
import threading
import unicodedata
from types import MappingProxyType
from typing import Any, Mapping

from core.paths import INSTALL_ROOT
from language_runtime.card_source import (
    CardSourceError,
    card_parts_dir,
    expand_card_parts,
    read_card_source,
)


DEFAULT_LANGUAGE = "en"
STORY_LANGUAGE_KEY = "story_language"
UI_LANGUAGE_SETTING = "ui_language"
PACK_SCHEMA_VERSION = 1

# `INSTALL_ROOT` rather than this file's own location, for the reason
# `core/paths.py` exists: a module that answers "where am I installed" from
# `__file__` answers it wrongly the moment it moves, and takes the wrong
# answer with it silently.
_PACK_ROOT = Path(os.environ.get(
    "SONDER_LANGUAGE_PACKS",
    Path(INSTALL_ROOT) / "language_packs",
))
_LANGUAGE_ID = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
_CARD_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_ADAPTER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_DIRECTIONS = frozenset(("ltr", "rtl"))
_STORY_CARDS = frozenset((
    "authoring", "compositor", "linguistics", "system_prompts",
))
_STORY_COVERAGE = frozenset((
    "authoring", "compositor", "deterministic_linguistics",
    "system_prompts", "ui",
))
_lock = threading.RLock()
_packs: dict[str, "LanguagePack"] | None = None
_pack_failure: str | None = None
_renderers: dict[str, Any] = {}
_BUILTIN_ADAPTERS = {
    "japanese": "language_adapters.japanese",
}
current_language_id = contextvars.ContextVar(
    "current_language_id", default=DEFAULT_LANGUAGE)

# The engine's logger, by name: `core.logging_utils` reads a setting from the
# database at import, and this module is imported before one is configured.
_log = logging.getLogger("fiction_engine")

#: Caches built FROM pack data elsewhere (`referring`'s tables), dropped with
#: `_linguistic_cached` whenever the packs reload. See `on_packs_reloaded`.
_RELOAD_HOOKS: list = []


class LanguagePackError(ValueError):
    """An installed pack is malformed or cannot provide a requested role."""


def normalize_language_id(value: Any) -> str:
    """Return the canonical on-disk spelling of a BCP-47-like language id."""
    language_id = str(value or DEFAULT_LANGUAGE).strip().replace("_", "-").lower()
    if not _LANGUAGE_ID.fullmatch(language_id):
        raise LanguagePackError(f"invalid language id: {value!r}")
    return language_id


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LanguagePackError(f"missing language-pack file: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise LanguagePackError(f"cannot read language-pack file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LanguagePackError(f"language-pack file must contain an object: {path}")
    return value


def _read_card(directory: Path, name: str) -> dict:
    """Assemble one card from its index and, if it has them, its part files.

    A card is `cards/<name>.json` -- the structural index -- plus an optional
    sibling directory `cards/<name>/` of `.txt` part files, one per prose
    leaf, referenced from the index as `{"$text": "<relative path>"}`. The
    split exists because `system_prompts` is 414 KB (en) / 525 KB (ja) of
    62,000-character prompt strings with escaped newlines, which no human can
    edit without a surgical raw-text replace. It moves WHERE the text lives
    and nothing else; `language_runtime/card_source.py` states the format and
    `tests/test_prompt_card_split.py` holds the assembled values byte-
    identical to the pre-split reference.

    A card with no references and no parts directory passes straight through,
    so the three unsplit cards need no special case.

    If a part file is missing, empty, orphaned, misnamed or not LF UTF-8, this
    raises rather than returning a short prompt: the failure reaches
    `installed_language_packs()`, is negative-cached, and stops the server
    starting and the suite collecting. A truncated sheet that loads is a
    silent behaviour change read by every story in that language; a pack that
    refuses to load is a line in a log.
    """
    index = _read_json(directory / "cards" / f"{name}.json")
    try:
        return expand_card_parts(index, card_parts_dir(directory, name))
    except CardSourceError as exc:
        raise LanguagePackError(
            f"language-pack card {directory.name}/{name}: {exc}") from exc


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


#: The reference grammar: `{{fragment:<name>}}`, where <name> is a top-level
#: string key of the same system-prompt card.
_FRAGMENT_REF = re.compile(r"\{\{fragment:([a-z][a-z0-9_]*)\}\}")
#: Any spelling that merely OPENS a reference. The strict pattern above is
#: what resolves; this looser mark is what fails the load afterwards, so a
#: typo -- wrong case, missing colon -- cannot ship as literal prompt text.
_FRAGMENT_MARK = "{{fragment"


def _resolve_prompt_fragments(card: dict, language_id: str) -> dict:
    """Substitute every `{{fragment:<name>}}` reference in a prompt card.

    Authored fragments are embedded in many prompt bodies (eight fragments in
    twenty-nine places, measured 2026-11-01; `make structure` is the live
    count). As hand-maintained pastes they were free to drift, and in the
    Japanese pack every copy had: each was translated independently of its
    own fragment. A reference resolved here -- at card load, before anything
    downstream can read the card -- makes the copies the same bytes as the
    fragment by construction, and turns a fragment edit into one edit.

    Fails the pack load on an unknown name, a cycle, or a reference that
    does not parse, because a prompt shipped with `{{fragment:foo}}` in it
    is read by every story.
    """
    sources = {name: value for name, value in card.items()
               if isinstance(value, str)}
    resolved: dict[str, str] = {}
    resolving: list[str] = []

    def fragment(name: str, at: str) -> str:
        if name not in sources:
            raise LanguagePackError(
                f"language pack {language_id!r} references unknown prompt "
                f"fragment {name!r} at system_prompts.{at}")
        if name in resolving:
            raise LanguagePackError(
                f"language pack {language_id!r} has a fragment reference "
                f"cycle: {' -> '.join(resolving + [name])}")
        if name not in resolved:
            resolving.append(name)
            try:
                resolved[name] = substitute(sources[name], name)
            finally:
                resolving.pop()
        return resolved[name]

    def substitute(text: str, at: str) -> str:
        out = _FRAGMENT_REF.sub(lambda match: fragment(match.group(1), at),
                                text)
        if _FRAGMENT_MARK in out:
            raise LanguagePackError(
                f"language pack {language_id!r} has a malformed fragment "
                f"reference at system_prompts.{at}")
        return out

    def walk(value, path):
        if isinstance(value, dict):
            return {key: walk(child, f"{path}.{key}")
                    for key, child in value.items()}
        if isinstance(value, list):
            return [walk(child, f"{path}.{index}")
                    for index, child in enumerate(value)]
        if isinstance(value, str):
            return substitute(value, path)
        return value

    return {key: walk(child, key) for key, child in card.items()}


@dataclass(frozen=True)
class LanguagePack:
    id: str
    name: str
    native_name: str
    direction: str
    version: str
    translation_status: str
    fallback: str | None
    ui: bool
    story: bool
    adapter: str
    output_token_scale: float
    coverage: Any
    prompt_policy: Any
    ui_catalog: Any
    cards: Any

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "native_name": self.native_name,
            "direction": self.direction,
            "version": self.version,
            "translation_status": self.translation_status,
            "fallback": self.fallback,
            "ui": self.ui,
            "story": self.story,
            "adapter": self.adapter,
            "output_token_scale": self.output_token_scale,
            "coverage": dict(self.coverage),
        }

    def card(self, name: str) -> Any:
        try:
            return self.cards[name]
        except KeyError as exc:
            raise LanguagePackError(
                f"language pack {self.id!r} has no {name!r} card") from exc

    def prompt_suffix(self, role: str | None = None) -> str:
        common = str(self.prompt_policy.get("common") or "").strip()
        roles = self.prompt_policy.get("roles") or {}
        specific = str(roles.get(str(role or "")) or "").strip()
        return "\n\n".join(part for part in (common, specific) if part)


def _load_pack(directory: Path) -> LanguagePack:
    manifest = _read_json(directory / "manifest.json")
    language_id = normalize_language_id(manifest.get("id"))
    if directory.name.lower() != language_id:
        raise LanguagePackError(
            f"pack directory {directory.name!r} does not match id {language_id!r}")
    if manifest.get("schema_version") != PACK_SCHEMA_VERSION:
        raise LanguagePackError(
            f"language pack {language_id!r} uses unsupported schema version "
            f"{manifest.get('schema_version')!r}")
    direction = str(manifest.get("direction") or "ltr").lower()
    if direction not in _DIRECTIONS:
        raise LanguagePackError(
            f"language pack {language_id!r} has invalid direction {direction!r}")
    fallback = manifest.get("fallback")
    fallback = normalize_language_id(fallback) if fallback else None
    adapter = str(manifest.get("adapter") or "").strip()
    if not _ADAPTER_NAME.fullmatch(adapter):
        raise LanguagePackError(
            f"language pack {language_id!r} has invalid adapter {adapter!r}")
    # How much more OUTPUT budget this language needs for the same content.
    # Every max_tokens in the engine was measured against English, and
    # Japanese costs roughly twice as many tokens to say the same thing -- so
    # an English-tuned cap truncates it mid-JSON and the caller reports a
    # generation failure that looks like a model fault.
    try:
        output_token_scale = float(manifest.get("output_token_scale") or 1.0)
    except (TypeError, ValueError):
        raise LanguagePackError(
            f"language pack {language_id!r} has a non-numeric "
            f"output_token_scale") from None
    if not 1.0 <= output_token_scale <= 4.0:
        raise LanguagePackError(
            f"language pack {language_id!r} output_token_scale must be "
            f"between 1.0 and 4.0, not {output_token_scale}")

    card_names = manifest.get("cards") or []
    if not isinstance(card_names, list) or any(
            not isinstance(name, str) or not _CARD_NAME.fullmatch(name)
            for name in card_names):
        raise LanguagePackError(
            f"language pack {language_id!r} cards must be a list of names")
    if len(card_names) != len(set(card_names)):
        raise LanguagePackError(
            f"language pack {language_id!r} declares duplicate cards")
    story = bool(manifest.get("story"))
    coverage = manifest.get("coverage") or {}
    if not isinstance(coverage, dict):
        raise LanguagePackError(
            f"language pack {language_id!r} coverage must be an object")
    missing_coverage = (_STORY_COVERAGE.difference(
        key for key, enabled in coverage.items() if enabled) if story else set())
    if missing_coverage:
        raise LanguagePackError(
            f"story language pack {language_id!r} has incomplete coverage: "
            f"{', '.join(sorted(missing_coverage))}")
    if bool(manifest.get("ui")) and not coverage.get("ui"):
        raise LanguagePackError(
            f"UI language pack {language_id!r} does not declare UI coverage")
    missing_story_cards = _STORY_CARDS.difference(card_names) if story else set()
    if missing_story_cards:
        raise LanguagePackError(
            f"story language pack {language_id!r} is missing cards: "
            f"{', '.join(sorted(missing_story_cards))}")
    cards = {name: _read_card(directory, name) for name in card_names}
    if "system_prompts" in cards:
        cards["system_prompts"] = _resolve_prompt_fragments(
            cards["system_prompts"], language_id)
    prompt_policy = _read_json(directory / "prompt_policy.json")
    if not isinstance(prompt_policy.get("roles", {}), dict):
        raise LanguagePackError(
            f"language pack {language_id!r} prompt roles must be an object")
    if bool(manifest.get("story")) and not str(
            prompt_policy.get("common") or "").strip():
        raise LanguagePackError(
            f"story language pack {language_id!r} has no common schema policy")
    ui_catalog = _read_json(directory / "ui.json")

    authoring = cards.get("authoring", {})
    if story and any(not str(authoring.get(key) or "").strip() for key in (
            "create_character_brief", "create_persona_brief")):
        raise LanguagePackError(
            f"story language pack {language_id!r} has incomplete authoring defaults")
    prompt_card = cards.get("system_prompts", {})
    if story and (not isinstance(prompt_card.get("prompts"), dict)
                  or not prompt_card.get("prompts")):
        raise LanguagePackError(
            f"story language pack {language_id!r} has no system prompts")

    return LanguagePack(
        id=language_id,
        name=str(manifest.get("name") or language_id),
        native_name=str(manifest.get("native_name") or manifest.get("name")
                        or language_id),
        direction=direction,
        version=str(manifest.get("version") or "0"),
        translation_status=str(
            manifest.get("translation_status") or "unreviewed"),
        fallback=fallback,
        ui=bool(manifest.get("ui")),
        story=story,
        adapter=adapter,
        output_token_scale=output_token_scale,
        coverage=_freeze(coverage),
        prompt_policy=_freeze(prompt_policy),
        ui_catalog=_freeze(ui_catalog),
        cards=_freeze(cards),
    )


def pack_source_files() -> list[Path]:
    """Every file `installed_language_packs` reads to load the packs: each
    pack's manifest, its prompt policy and UI catalog, and each card the
    manifest names -- `cards/<name>.json` and its `cards/<name>/` parts. A
    file the loader never reads (a tool's translation report) is not one.
    For `core.code_version`, which warns when what a running server holds is
    no longer what is on disk. Never raises: a pack it cannot read lists what
    it found."""
    from language_runtime.card_source import PART_SUFFIX, card_parts_dir
    out: list[Path] = []
    try:
        directories = sorted(path for path in _PACK_ROOT.iterdir() if path.is_dir())
    except OSError:
        return out
    for directory in directories:
        manifest = directory / "manifest.json"
        if not manifest.is_file():
            continue
        out.append(manifest)
        for name in ("prompt_policy.json", "ui.json"):
            if (directory / name).is_file():
                out.append(directory / name)
        try:
            cards = json.loads(manifest.read_text(encoding="utf-8")).get("cards") or []
        except (OSError, ValueError, AttributeError):
            continue
        for card in cards:
            if not isinstance(card, str) or not _CARD_NAME.fullmatch(card):
                continue
            if (directory / "cards" / f"{card}.json").is_file():
                out.append(directory / "cards" / f"{card}.json")
            parts = card_parts_dir(directory, card)
            if parts.is_dir():
                out.extend(sorted(parts.rglob(f"*{PART_SUFFIX}")))
    return out


def installed_language_packs(*, refresh: bool = False) -> dict[str, LanguagePack]:
    global _packs, _pack_failure
    with _lock:
        if _packs is not None and not refresh:
            return dict(_packs)
        # Negative caching. Only the SUCCESS path was cached, so one malformed
        # pack directory -- a half-written translation drop, a truncated card
        # -- turned every language read into a full rescan of the tree. This
        # sits under get_prompt, compositor_value and every linguistic() miss,
        # i.e. thousands of calls per turn.
        if _pack_failure is not None and not refresh:
            raise LanguagePackError(_pack_failure)
        try:
            found = {}
            if _PACK_ROOT.is_dir():
                for directory in sorted(path for path in _PACK_ROOT.iterdir()
                                        if path.is_dir()):
                    pack = _load_pack(directory)
                    if pack.id in found:
                        raise LanguagePackError(f"duplicate language pack: {pack.id}")
                    found[pack.id] = pack
            if DEFAULT_LANGUAGE not in found:
                raise LanguagePackError("the built-in English language pack is missing")
            for pack in found.values():
                if pack.fallback and pack.fallback not in found:
                    raise LanguagePackError(
                        f"language pack {pack.id!r} has missing fallback {pack.fallback!r}")
            reference_prompts = set(
                found[DEFAULT_LANGUAGE].card("system_prompts")["prompts"])
            reference_card_keys = {
                card_name: _leaf_paths(found[DEFAULT_LANGUAGE].card(card_name))
                for card_name in _STORY_CARDS
            }
            for pack in found.values():
                if not pack.story:
                    continue
                supplied = set(pack.card("system_prompts")["prompts"])
                missing = reference_prompts.difference(supplied)
                if missing:
                    raise LanguagePackError(
                        f"story language pack {pack.id!r} is missing system prompts: "
                        f"{', '.join(sorted(missing))}")
                for card_name, reference_keys in reference_card_keys.items():
                    missing_keys = reference_keys.difference(
                        _leaf_paths(pack.card(card_name)))
                    if missing_keys:
                        sample = ", ".join(sorted(missing_keys)[:8])
                        raise LanguagePackError(
                            f"story language pack {pack.id!r} has incomplete "
                            f"{card_name} card: {sample}")
            reference_ui = set(found[DEFAULT_LANGUAGE].ui_catalog)
            for pack in found.values():
                if not pack.ui:
                    continue
                missing_ui = reference_ui.difference(pack.ui_catalog)
                if missing_ui:
                    raise LanguagePackError(
                        f"UI language pack {pack.id!r} is missing "
                        f"{len(missing_ui)} source messages")
        except LanguagePackError as exc:
            _pack_failure = str(exc)
            raise
        _packs = found
        _pack_failure = None
        _linguistic_cached.cache_clear()
        for hook in list(_RELOAD_HOOKS):
            hook()
        return dict(found)


def on_packs_reloaded(hook) -> None:
    """Run `hook()` every time the installed packs are (re)loaded.

    For a cache built FROM pack data in another module -- `referring`'s
    per-language tables -- which would otherwise outlive the packs it was
    read from, exactly as `_linguistic_cached` would without its
    `cache_clear` above."""
    if hook not in _RELOAD_HOOKS:
        _RELOAD_HOOKS.append(hook)


def _leaf_paths(value, prefix="") -> set[str]:
    """Return required object paths while treating typed card values as leaves."""
    if isinstance(value, Mapping) and "$type" not in value:
        paths = set()
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.update(_leaf_paths(child, child_prefix))
        return paths
    return {prefix}


def require_language_pack(language_id: Any, *, capability: str | None = None) -> LanguagePack:
    key = normalize_language_id(language_id)
    pack = installed_language_packs().get(key)
    if pack is None:
        raise LanguagePackError(f"language pack {key!r} is not installed")
    if capability in ("ui", "story") and not getattr(pack, capability):
        raise LanguagePackError(
            f"language pack {key!r} does not support {capability}")
    if capability == "story" and pack.adapter != "english":
        _load_builtin_adapter(pack.adapter)
    if (capability == "story" and pack.adapter != "english"
            and pack.adapter not in _renderers):
        raise LanguagePackError(
            f"language pack {key!r} requires unavailable deterministic "
            f"adapter {pack.adapter!r}")
    return pack


def pack_directory(language_id: Any = DEFAULT_LANGUAGE) -> Path:
    """The on-disk directory of one installed pack."""
    key = normalize_language_id(language_id)
    directory = _PACK_ROOT / key
    if not directory.is_dir():
        raise LanguagePackError(f"language pack {key!r} is not installed")
    return directory


def raw_card(language_id: Any = DEFAULT_LANGUAGE,
             card_name: str = "system_prompts") -> dict:
    """One pack's AUTHORED card: assembled from its parts, mutable, unresolved.

    The documented way for a tool or a test to reach what a human wrote.
    `LanguagePack.card(...)` is the wrong artifact for that: it is frozen, and
    its `{{fragment:...}}` references have already been substituted, so a
    single authored fragment appears in it as many times as it is referenced
    (up to seven, measured 2026-11-01). Anything auditing
    or grepping authored prompt text wants this; anything asking what a model
    will actually receive wants `card(...)`.
    """
    if not _CARD_NAME.fullmatch(str(card_name)):
        raise LanguagePackError(f"invalid card name: {card_name!r}")
    try:
        return read_card_source(pack_directory(language_id), str(card_name))
    except CardSourceError as exc:
        raise LanguagePackError(
            f"language-pack card {language_id}/{card_name}: {exc}") from exc


def language_pack(language_id: Any = DEFAULT_LANGUAGE) -> LanguagePack:
    """Resolve an installed pack, then its base language, then English.

    This forgiving read path keeps old/imported stories playable. Authoring
    endpoints use ``require_language_pack`` so a typo can never be persisted.
    """
    key = normalize_language_id(language_id)
    packs = installed_language_packs()
    if key in packs:
        return packs[key]
    base = key.split("-", 1)[0]
    return packs.get(base) or packs[DEFAULT_LANGUAGE]


#: (surface, stored language id) pairs whose English fallback has been
#: reported in this process. Once per language, not once per call: the story
#: reader runs on every turn.
_FALLBACK_REPORTED: set = set()


def _report_fallback(surface: str, stored: Any, exc: Exception) -> None:
    """Log, once per process per (surface, language), that a stored
    language could not be used and English stands in for it.

    The fallback itself is the owner's "warn, never refuse": a story whose
    pack or adapter cannot load still plays. It used to do so with no line at
    any log level (dressing audit F12, 2026-11-01): a Japanese story whose
    adapter failed to import ran every turn with English prompts, recognisers
    and renderer while its stored language still said `ja`."""
    key = (surface, str(stored))
    with _lock:
        if key in _FALLBACK_REPORTED:
            return
        _FALLBACK_REPORTED.add(key)
    _log.warning("%s language %r cannot be used (%s); it falls back to %r",
                 surface, str(stored), exc, DEFAULT_LANGUAGE)


def story_language(chat_id: int) -> str:
    from core.db import wget
    stored = wget(chat_id, STORY_LANGUAGE_KEY, DEFAULT_LANGUAGE)
    try:
        return require_language_pack(stored, capability="story").id
    except LanguagePackError as exc:
        _report_fallback("story", stored, exc)
        return DEFAULT_LANGUAGE


def set_story_language(chat_id: int, language_id: Any) -> str:
    from core.db import wset
    selected = require_language_pack(language_id, capability="story").id
    wset(chat_id, STORY_LANGUAGE_KEY, selected)
    return selected


def ui_language() -> str:
    from core.db import get_setting
    stored = get_setting(UI_LANGUAGE_SETTING) or DEFAULT_LANGUAGE
    try:
        return require_language_pack(stored, capability="ui").id
    except LanguagePackError as exc:
        _report_fallback("interface", stored, exc)
        return DEFAULT_LANGUAGE


def set_ui_language(language_id: Any) -> str:
    from core.db import set_setting
    selected = require_language_pack(language_id, capability="ui").id
    set_setting(UI_LANGUAGE_SETTING, selected)
    return selected


@contextlib.contextmanager
def language_scope(language_id: Any):
    """Run a block with `current_language_id` set, and always restore it.

    `run_pipeline` was the only place this was ever set, so every model call
    made OUTSIDE a turn -- greetings, memory consolidation, card and lorebook
    generation, appearance and psychology fills -- resolved to the English
    default. In a Japanese story that produced English prose, and worse, the
    provider boundary then appended the ENGLISH schema policy underneath the
    pack's Japanese one, telling the model both things at once.
    """
    token = current_language_id.set(normalize_language_id(language_id))
    try:
        yield
    finally:
        current_language_id.reset(token)


@contextlib.contextmanager
def story_language_scope(chat_id: Any):
    """`language_scope` for a chat, resolving its stored story language."""
    with language_scope(story_language(chat_id)):
        yield


def output_token_scale(language_id: Any = None) -> float:
    """The active pack's output-budget multiplier (1.0 for English)."""
    selected = current_language_id.get() if language_id is None else language_id
    try:
        return float(language_pack(selected).output_token_scale)
    except LanguagePackError:
        return 1.0


def apply_prompt_policy(text: str, language_id: Any = DEFAULT_LANGUAGE,
                        role: str | None = None) -> str:
    suffix = language_pack(language_id).prompt_suffix(role)
    base = str(text or "")
    # Prompt assembly has several compatibility views (the editable default
    # registry, scoped sheets, provider-level enforcement). Make the policy a
    # set-like contract: whichever boundary sees it first appends it, and
    # every later boundary proves it is already present rather than doubling
    # the instruction.
    if not suffix or base.rstrip().endswith(suffix):
        return base
    # The role suffix varies while `common` does not, so two calls with
    # different roles both fail the endswith test above and `common` lands
    # twice. Both packs carry role suffixes (English since 2026-08-24:
    # `interpret_repair` and `narrator`), so both expose it. Append only the
    # part that is not already there.
    common = str(prompt_policy_common(language_id) or "").strip()
    if common and common in base:
        role_only = suffix[len(common):].strip()
        if not role_only or role_only in base:
            return base
        return base + "\n\n" + role_only
    return base + "\n\n" + suffix


def prompt_policy_common(language_id: Any = DEFAULT_LANGUAGE) -> str:
    """The language/schema contract every prompt of this language carries."""
    return str(language_pack(language_id).prompt_policy.get("common") or "").strip()


def apply_common_prompt_policy(text: str, language_id: Any = None) -> str:
    """Ensure even ad-hoc/repair system prompts carry the schema contract."""
    selected = (current_language_id.get() if language_id is None
                else language_id)
    common = str(language_pack(selected).prompt_policy.get("common") or "").strip()
    base = str(text or "")
    if not common or common in base:
        return base
    return base + "\n\n" + common


def compositor_value(name: str, language_id: Any = None):
    """Return language-owned deterministic rendering data."""
    selected = current_language_id.get() if language_id is None else language_id
    try:
        return language_pack(selected).card("compositor")[name]
    except KeyError as exc:
        raise LanguagePackError(
            f"language pack {normalize_language_id(selected)!r} lacks "
            f"compositor value {name!r}") from exc


def compositor_text(key: str, language_id: Any = None, **values) -> str:
    """Format a reader-exposed deterministic template from the active pack."""
    templates = compositor_value("templates", language_id)
    try:
        template = templates[key]
    except KeyError as exc:
        raise LanguagePackError(
            f"language pack lacks compositor template {key!r}") from exc
    try:
        return str(template).format(**values)
    except (KeyError, IndexError, ValueError) as exc:
        # Distinct from the lookup failure above. Both used to raise "lacks
        # compositor template", so a template naming a field the caller does
        # not supply reported a missing template that was right there.
        raise LanguagePackError(
            f"compositor template {key!r} could not be filled: {exc}") from exc


def register_renderer(adapter: str, renderer: Any) -> None:
    """Register a trusted deterministic Layer-B renderer adapter."""
    name = str(adapter or "").strip()
    if not name or renderer is None:
        raise LanguagePackError("renderer adapter and implementation are required")
    missing = [method for method in ("render_view", "render_episode")
               if not callable(getattr(renderer, method, None))]
    if missing:
        raise LanguagePackError(
            f"renderer adapter {name!r} is missing: {', '.join(missing)}")
    with _lock:
        _renderers[name] = renderer


def _load_builtin_adapter(adapter: str) -> None:
    """Load only adapters explicitly trusted by the engine distribution."""
    if adapter in _renderers:
        return
    module_name = _BUILTIN_ADAPTERS.get(adapter)
    if module_name:
        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            # Reported as a pack failure, because that is what every caller
            # can handle. `story_language` catches LanguagePackError to fall
            # back to English, and logs that it did (`_report_fallback`); a
            # bare ImportError sailed past it and killed the turn before any
            # stage ran, with a traceback that never mentioned the language.
            raise LanguagePackError(
                f"deterministic adapter {adapter!r} could not be loaded: "
                f"{exc}") from exc


def renderer_for(language_id: Any = DEFAULT_LANGUAGE):
    pack = language_pack(language_id)
    # English remains the in-module reference renderer while it is extracted
    # card by card. Other adapters must register explicitly; no pack code is
    # imported or executed merely because it exists on disk.
    if pack.adapter == "english":
        return None
    _load_builtin_adapter(pack.adapter)
    renderer = _renderers.get(pack.adapter)
    if renderer is None:
        raise LanguagePackError(
            f"language pack {pack.id!r} requires unavailable adapter "
            f"{pack.adapter!r}")
    return renderer


def _decode_linguistic(value):
    if isinstance(value, Mapping):
        kind = value.get("$type")
        if kind == "regex":
            return re.compile(str(value["pattern"]), int(value.get("flags") or 0))
        if kind in ("tuple", "frozenset", "set"):
            items = tuple(_decode_linguistic(item) for item in value.get("items", ()))
            if kind == "frozenset":
                return frozenset(items)
            if kind == "set":
                return set(items)
            return items
        return {key: _decode_linguistic(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_decode_linguistic(item) for item in value)
    return value


@lru_cache(maxsize=1024)
def _linguistic_cached(language_id: str, module: str, name: str):
    # Under the same lock the pack map is rebuilt under. Without it a value
    # computed from the previous packs could land in the cache AFTER
    # installed_language_packs() cleared it, and stay there for the life of
    # the process.
    with _lock:
        pack = language_pack(language_id)
        card = pack.card("linguistics")
        try:
            return _decode_linguistic(card[module][name])
        except KeyError as exc:
            raise LanguagePackError(
                f"language pack {pack.id!r} lacks linguistic transform "
                f"{module}.{name}") from exc


def linguistic(module: str, name: str, language_id: Any = None):
    """Load one deterministic transform from the active story pack.

    This lookup deliberately happens at use time, not module import time.
    Pipelines for different languages can run concurrently, and every regex,
    cue table, agreement map, quote rule, and inflection rule must follow its
    own context-local story language without mutating process globals.
    """
    selected = current_language_id.get() if language_id is None else language_id
    return _linguistic_cached(normalize_language_id(selected), module, name)


def english_linguistic(module: str, name: str):
    """Compatibility helper for tests/tools that explicitly request English."""
    return linguistic(module, name, DEFAULT_LANGUAGE)


# ---- Scripts -------------------------------------------------------------------
#
# The helpers below are the engine's script-aware primitives: a comparison
# key, a tokenizer, a whole-name boundary and a sentence splitter, each
# decided by the SCRIPT a piece of text is written in rather than by the story
# language, because a Japanese story carries Latin names through imported cards
# and an English story carries Japanese ones. Use them instead of writing a
# `\b`, a `.split()`, a `[a-z0-9]` class or another sentence regex.

#: Letters that continue a word in a script that spaces its words: Latin (with
#: its supplements), Greek, Cyrillic, digits and the underscore. Deliberately
#: NOT `\w`, which also covers the scripts that do not space their words.
#: (`story.character_schema._SPACED_WORD_CHARS` is the same class.)
SPACED_WORD_CHARS = r"A-Za-z0-9_À-ɏḀ-ỿͰ-ϿЀ-ӿ"

#: The scripts written without spaces between words, one class each, as
#: regex character-class bodies. The iteration and closing marks 々〆〇 and the
#: small counters ヵヶ belong to the ideographs they sit among (佐々木, 霞ヶ関);
#: the middle dot ・ is punctuation, not katakana -- it is what JOINS two names.
HIRAGANA = "ぁ-ゟ"
KATAKANA = "ァ-ヴヷ-ヺー-ヿㇰ-ㇿｦ-ﾟ"
HAN = ("々-〇ヵヶ㐀-䶿一-鿿豈-﫿"
       "\U00020000-\U0003134f")
HANGUL = "ᄀ-ᇿ㄰-㆏가-힯"
THAI = "฀-๿"

_JAPANESE = HIRAGANA + KATAKANA + HAN
_SCRIPT_CLASSES = (
    ("hiragana", re.compile(f"[{HIRAGANA}]")),
    ("katakana", re.compile(f"[{KATAKANA}]")),
    ("han", re.compile(f"[{HAN}]")),
    ("hangul", re.compile(f"[{HANGUL}]")),
    ("thai", re.compile(f"[{THAI}]")),
)
#: Any character of an unspaced script.
UNSPACED_SCRIPT = re.compile(f"[{_JAPANESE}{HANGUL}{THAI}]")


def script_of(char: Any) -> str:
    """The unspaced script one character is written in -- "hiragana",
    "katakana", "han", "hangul" or "thai" -- or "" for anything else: a
    letter of a spaced script, a digit, punctuation, whitespace."""
    ch = str(char or "")[:1]
    if not ch:
        return ""
    for name, pattern in _SCRIPT_CLASSES:
        if pattern.match(ch):
            return name
    return ""


# ---- Comparison keys --------------------------------------------------------


def fold_text(text: Any) -> str:
    """NFKC, then casefold: the normalisation half of `fold_key`, with every
    character kept, for a caller that tokenizes the result itself. NFKC is
    what makes a full-width ＬＣＡＲＳ, a half-width ｶﾀｶﾅ and an ideographic
    space read as the same text as their ordinary forms."""
    return unicodedata.normalize("NFKC", str(text or "")).casefold()


def _key_char(ch: str) -> bool:
    # A letter, a digit or a combining mark, of any script. A mark is kept
    # because it is part of its letter: NFKC composes the Latin ones, but an
    # Indic vowel sign has no precomposed form and dropping it changes the
    # word.
    return unicodedata.category(ch)[0] in "LNM"


def fold_key(text: Any, sep: str = "") -> str:
    """A comparison key for a name, a place or any short label: NFKC,
    casefold, and everything that is not a letter, digit or mark of SOME
    script removed. "台所" -> "台所", "Café" -> "café", "Mirelle's Mouth" ->
    "mirellesmouth", "佐藤・ヒナミ" -> "佐藤ヒナミ".

    With `sep`, each run of removed characters becomes one separator and none
    stands at either end: `fold_key("Back Yard", "_") == "back_yard"`.

    THE CANONICAL REPLACEMENT for every `re.sub(r"[^a-z0-9]+", "_",
    text.casefold()).strip("_")`-style slug in the engine (world_spatial_
    structure_light F2 counted 67 such classes in 30 files). For ASCII input
    it is the SAME string -- `sep="_"` is that slug, `sep=" "` the
    space-joined form, `sep=""` the run-together key -- so an id already
    minted keeps matching its own spelling. For every other script it keeps
    the letters, which is the fix: the ASCII class folded `台所` to "" and
    so made every Japanese name equal to every other one. The case it ends,
    measured (persist_scene_entities F2): two kana owners shedding a jacket
    minted ONE floor object, keyed `jacket_`, stamped with the first owner.

    Two different names stay different. Two spellings of one name that
    differ only in case, width, punctuation or spacing fold together. Accents
    are letters and are kept ("café" is not "cafe"). An empty result means
    the text had no letter or digit at all -- an emoji, a run of punctuation
    -- and a caller keying a dict by this must still refuse "".
    """
    folded = fold_text(text)
    if not sep:
        return "".join(ch for ch in folded if _key_char(ch))
    out: list[str] = []
    gap = False
    for ch in folded:
        if _key_char(ch):
            if gap and out:
                out.append(sep)
            out.append(ch)
            gap = False
        else:
            gap = True
    return "".join(out)


def fold_words(text: Any) -> list[str]:
    """The folded words of `text`, in order: runs of letters, digits and
    marks, split at everything else AND where an unspaced script changes
    (kanji to kana, kana to Latin, a digit beside a kanji). For ASCII input
    it is exactly `re.findall(r"[a-z0-9]+", text.casefold())`, the token
    class it replaces; for an unspaced name it is the parts the name is
    written in -- `fold_words("佐藤ヒナミ") == ["佐藤", "ヒナミ"]` -- which a
    whitespace split never finds. Japanese prose comes back as script runs,
    hiragana runs (particles, inflection) included; a caller that wants
    content words drops the runs `script_of` calls hiragana."""
    words: list[str] = []
    run: list[str] = []
    run_script = None
    for ch in fold_text(text):
        if not _key_char(ch):
            if run:
                words.append("".join(run))
            run, run_script = [], None
            continue
        if unicodedata.category(ch)[0] == "M" and run:
            run.append(ch)          # a mark continues the letter it marks
            continue
        script = script_of(ch)
        if run and script != run_script:
            words.append("".join(run))
            run = []
        run.append(ch)
        run_script = script
    if run:
        words.append("".join(run))
    return words


# ---- Whole-name boundaries ----------------------------------------------------

#: What may directly FOLLOW a Japanese name in running text, where the name's
#: own edge is in the same script as the text after it: the particles that
#: attach to a noun, the copula, and the honorific and plural suffixes. A
#: closed grammatical class -- the engine owns it the way it owns its enum
#: tables -- and it lives here rather than in a pack because the boundary is a
#: fact of the NAME's script, not of the story's language: an English story
#: carries Japanese names too.
JA_NAME_FOLLOWERS = (
    "が", "を", "に", "へ", "と", "で", "の", "から", "より", "まで", "や",
    "は", "も", "こそ", "さえ", "しか", "だけ", "ばかり", "など", "なら",
    "ほど", "くらい", "ぐらい", "とか", "って", "か", "ね", "よ",
    "だ", "です", "じゃ",
    "さん", "さま", "様", "ちゃん", "くん", "君", "殿", "どの", "氏",
    "たち", "達", "ら", "等",
)
#: What may directly PRECEDE a hiragana-initial name: the particles that end
#: the phrase before it (「彼女はさくらを見た」).
JA_NAME_LEADERS = ("の", "は", "が", "を", "に", "へ", "と", "で", "も", "や",
                   "か", "から", "まで", "より")

_FOLLOWED = "(?=" + "|".join(
    sorted(set(JA_NAME_FOLLOWERS), key=len, reverse=True)) + ")"
# One lookbehind per particle: a lookbehind has to be one fixed width.
_LED = "|".join("(?<=%s)" % p for p in
                sorted(set(JA_NAME_LEADERS), key=len, reverse=True))


def _name_lead(char: str, single: bool) -> str:
    script = script_of(char)
    if script == "katakana":
        return f"(?<![{KATAKANA}])"
    if script == "hiragana":
        return f"(?:(?<![{HIRAGANA}])|{_LED})"
    if script == "han":
        # A kanji run holds several words -- a family name before a given
        # one (山田花子), a prefix before a name -- so a multi-character
        # kanji name's left edge stays open, as it always was. A ONE-kanji
        # term inside a run is nearly always another word (一角, 三角, 頭角
        # for 角), so its left edge is not.
        return f"(?<![{HAN}])" if single else ""
    if script in ("hangul", "thai"):
        return ""
    return f"(?<![{SPACED_WORD_CHARS}])"


def _name_tail(char: str, single: bool) -> str:
    script = script_of(char)
    if single and script in ("hiragana", "katakana", "han"):
        # One kana or kanji is a name only where a particle, the copula, an
        # honorific, punctuation, another script or the end follows it:
        # 「角が」 is the horn, 「角ばった顎」 an angular jaw.
        return f"(?:(?![{_JAPANESE}])|{_FOLLOWED})"
    if script == "katakana":
        return f"(?![{KATAKANA}])"
    if script == "hiragana":
        return f"(?:(?![{HIRAGANA}])|{_FOLLOWED})"
    if script in ("han", "hangul", "thai"):
        # Japanese compounds titles and suffixes onto a kanji name on the
        # right (田中部長, 佐藤隊長, 山田家), and the name is in every one of
        # them: an identity scrub that refused them would leak the name.
        # Hangul and Thai keep the open edge they had: Korean writes its
        # particles onto the noun and Thai runs its words together, and no
        # closed class here says where either ends.
        return ""
    return f"(?![{SPACED_WORD_CHARS}])"


@lru_cache(maxsize=2048)
def name_boundary_pattern(form: str) -> str:
    """Match `form` as a WHOLE name, in whatever script the name is written.

    A pattern string: compose it (`+ "(?:'s|’s)?"`, inside `(?-i:...)`, in a
    named group) and compile with your own flags, or use
    `name_boundary_regex`. Decided per EDGE of the name, by that edge's script,
    never by the story's language:

      * Latin, Greek, Cyrillic or a digit at the edge: no spaced-script letter
        or digit beside it -- `\\b` semantics that also see `彼はHinamiに`.
        Byte-identical to the rule this replaced.
      * katakana: no katakana beside it. 「ヒナミは」 and 「ヒナミ、」 match;
        「ヒナミコ」, 「アヒナミ」 and 「プレイヤー」 (for レイ) do not.
      * hiragana: no hiragana beside it, unless what is beside it is a
        particle (`JA_NAME_LEADERS` before, `JA_NAME_FOLLOWERS` after):
        「彼女はさくらを見た」 matches さくら; 「さくらんぼ」 does not.
      * kanji: a two-or-more-character kanji name keeps open edges, because
        Japanese compounds onto it on both sides and the name is in each
        compound (田中さん, 田中部長, 山田花子) -- an identity scrub that
        refused those would leak the name. A ONE-character kana or kanji name
        needs no kanji before it and, after it, a particle, the copula, an
        honorific, punctuation, another script or the end: 「額に二本の角が」
        matches 角, 「角ばった顎」 and 「部屋の一角に」 do not.
      * Hangul and Thai: open, as before (no closed class says where a word
        ends in either).

    Measured before this (dressing audit F7, 2026-11-01): an unspaced edge
    had NO assertion, so ヒナミ matched inside ヒナミコ and アヒナミ, レイ
    inside プレイヤー, and the disguise scrub of 角 rewrote 「角ばった顎」 as
    「ばった顎」 in every observer's view. An empty name never matches.
    """
    text = str(form or "")
    if not text:
        return r"(?!)"  # never matches, rather than matching everywhere
    single = len(text) == 1
    return (_name_lead(text[0], single) + re.escape(text)
            + _name_tail(text[-1], single))


@lru_cache(maxsize=2048)
def name_boundary_regex(form: str, flags: int = 0):
    """`name_boundary_pattern` compiled, and cached here rather than in
    `re`'s shared 512-entry cache, which forty call sites and every other
    dynamic pattern in a long story compete for (dressing audit E7)."""
    return re.compile(name_boundary_pattern(form), flags)


@lru_cache(maxsize=512)
def _longest_first(forms: tuple) -> tuple:
    return tuple(sorted({str(f) for f in forms if str(f or "")},
                        key=lambda f: (-len(f), f)))


@lru_cache(maxsize=512)
def _names_regex(forms: tuple, flags: int):
    return re.compile("|".join("(%s)" % name_boundary_pattern(form)
                               for form in forms), flags)


def find_names(text: Any, forms, flags: int = re.IGNORECASE) -> list:
    """Every whole-name occurrence of any of `forms` in `text`, as
    `[(start, end, form), ...]` in text order -- the SET matcher.

    At any position the LONGEST form wins, and no returned span lies inside
    another, so "Great Hall" is not also "Hall" and 「ヒナミコ」 is not also
    「ヒナミ」. That is the class fix for "does this text name this place /
    person" readers that test each form alone and let the shorter one win
    (mind_affect F6: five such readers disagreed; "Walk to the Great Hall"
    named the Hall). Each form is bounded by `name_boundary_pattern`; `flags`
    are the caller's (`0` for a case-sensitive proper-name match)."""
    body = str(text or "")
    if not body or not forms:
        return []
    unique = (_longest_first(forms) if isinstance(forms, tuple)
              else _longest_first(tuple(forms)))
    if not unique:
        return []
    return [(m.start(), m.end(), unique[m.lastindex - 1])
            for m in _names_regex(unique, flags).finditer(body)]


# ---- Sentences -----------------------------------------------------------------

#: What closes a quotation or a parenthesis after a sentence's stop and belongs
#: to that sentence: straight and curly quotes, guillemets, brackets, and the
#: corner brackets and full-width brackets Japanese closes with.
_ASCII_CLOSERS = "\"'”’»)]}"
_CJK_CLOSERS = "」』）】〕〉》〙〛"
_CLOSERS = "[" + re.escape(_ASCII_CLOSERS + _CJK_CLOSERS) + "]*"
#: A sentence stop: ASCII `.!?` (any run of them) with its closers, which
#: ends a sentence only before whitespace or the end -- `3.5`, `Dr.Moon` and
#: an unspaced `.` are not stops; or a full-width stop `。！？` (and the
#: half-width `｡`), which needs no whitespace after it, with its closers.
_SENTENCE_STOP = re.compile(
    r"(?P<ascii>[.!?]+)(?P<aclose>" + _CLOSERS + r")(?=\s|$)"
    r"|(?P<cjk>[。！？｡][。！？｡!?]*)"
    r"(?P<cclose>" + _CLOSERS + r")")
#: Opening quotes and brackets a token before an abbreviation's period may
#: carry: `("Dr.` is still the title "Dr".
_OPENERS = "\"'“‘«([{「『（【〔〈《"
#: The Japanese quotative particles: a quotation closed and carried on by one
#: of them is inside its sentence (「行こう。」と彼は言った。).
_QUOTATIVE = ("と", "って")
#: A sentence ending in an unspaced script's stop or closer, which the next
#: sentence follows with no space.
_UNSPACED_SENTENCE_END = re.compile(
    "[" + re.escape("。！？｡" + _CJK_CLOSERS) + "]$")


def _token_before(text: str, index: int) -> str:
    start = index
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    return text[start:index].lstrip(_OPENERS)


def _sentence_spans(text: str, language_id: Any = None) -> list:
    abbreviations = None
    spans: list = []
    start = 0
    for match in _SENTENCE_STOP.finditer(text):
        end = match.end()
        if match.group("ascii") is not None:
            if match.group("ascii") == ".":
                if abbreviations is None:
                    abbreviations = linguistic(
                        "agents.common", "_SENTENCE_ABBREVIATIONS", language_id)
                if _token_before(text, match.start()).casefold() in abbreviations:
                    continue        # "Dr. Moon", "Capt. of the guard"
            if match.group("aclose") and text[end:].lstrip()[:1].islower():
                continue            # '"Hi!" she said.' is one sentence
        elif match.group("cclose") and text[end:].lstrip().startswith(_QUOTATIVE):
            continue                # 「行こう。」と彼は言った。 is one sentence
        spans.append((start, end))
        start = end
    if start < len(text):
        spans.append((start, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def split_sentences(text: Any, maxsplit: int = 0, *,
                    language_id: Any = None) -> list:
    """The sentences of `text`, stripped, in order, none empty.

    ONE splitter for every script. A sentence ends at:

      * ASCII `.`, `!` or `?` (or a run of them) followed by whitespace or the
        end -- never at a `.` that ends one of the active pack's
        `_SENTENCE_ABBREVIATIONS` ("Dr. Moon", "Capt. of the harbour guard"),
        the token set `agents.common_names.split_sentences` already reads;
      * a full-width `。`, `！` or `？`, with or without whitespace after it.

    A closing quote or bracket after the stop stays with the sentence it
    closes (`She said "Go."`, 「こんにちは。」), except where the sentence
    plainly carries on past it: a lowercase word after a closed quote ('"Hi!"
    she said.') or a Japanese quotative particle after a closed corner bracket
    (「行こう。」と彼は言った。).

    It replaces `referring.SENTENCE_END`'s `(?<=[a-z]{3}[.!?])\\s+`, which cut
    a stranger's label at "Capt." and never at "300s.", "RAF." or "café."
    (dressing audit F6), and is what UNBUILT_PIPELINE 1.69's other splitters
    should read. `maxsplit` (as in `re.split`) keeps the remainder as written.
    `language_id` names the pack whose abbreviations apply; by default the
    active story language's.
    """
    body = str(text or "")
    spans = _sentence_spans(body, language_id)
    if maxsplit and maxsplit > 0 and len(spans) > maxsplit + 1:
        spans = spans[:maxsplit] + [(spans[maxsplit][0], spans[-1][1])]
    return [body[s:e].strip() for s, e in spans]


def join_sentences(sentences) -> str:
    """Rejoin sentences: a space after a sentence of a spaced script, none
    after one ending in an unspaced script's stop or closer (「。」 runs
    straight on). The inverse of `split_sentences` up to whitespace."""
    out = ""
    for sentence in sentences or ():
        piece = str(sentence or "").strip()
        if not piece:
            continue
        if out and not _UNSPACED_SENTENCE_END.search(out):
            out += " "
        out += piece
    return out


__all__ = [
    "DEFAULT_LANGUAGE", "STORY_LANGUAGE_KEY", "LanguagePack",
    "LanguagePackError", "apply_common_prompt_policy", "apply_prompt_policy",
    "compositor_text", "compositor_value", "prompt_policy_common",
    "current_language_id", "installed_language_packs", "on_packs_reloaded",
    "language_scope", "output_token_scale", "story_language_scope",
    "english_linguistic", "linguistic", "language_pack",
    "normalize_language_id", "register_renderer",
    "renderer_for", "require_language_pack", "set_story_language",
    "set_ui_language", "story_language", "ui_language",
    "pack_directory", "raw_card",
    # Script-aware primitives (see "Scripts" above).
    "SPACED_WORD_CHARS", "HIRAGANA", "KATAKANA", "HAN", "HANGUL", "THAI",
    "UNSPACED_SCRIPT", "JA_NAME_FOLLOWERS", "JA_NAME_LEADERS", "script_of",
    "fold_text", "fold_key", "fold_words", "name_boundary_pattern",
    "name_boundary_regex", "find_names", "split_sentences", "join_sentences",
]
