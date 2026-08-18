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
import os
from pathlib import Path
import re
import threading
from types import MappingProxyType
from typing import Any, Mapping


DEFAULT_LANGUAGE = "en"
STORY_LANGUAGE_KEY = "story_language"
UI_LANGUAGE_SETTING = "ui_language"
PACK_SCHEMA_VERSION = 1

_PACK_ROOT = Path(os.environ.get(
    "SONDER_LANGUAGE_PACKS",
    Path(__file__).resolve().parent.parent / "language_packs",
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


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


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
    cards = {name: _read_json(directory / "cards" / f"{name}.json")
             for name in card_names}
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
        return dict(found)


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


def story_language(chat_id: int) -> str:
    from core.db import wget
    stored = wget(chat_id, STORY_LANGUAGE_KEY, DEFAULT_LANGUAGE)
    try:
        return require_language_pack(stored, capability="story").id
    except LanguagePackError:
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
    except LanguagePackError:
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
    # twice. English hides this (its `roles` map is empty, making the two
    # suffixes identical); Japanese has role suffixes and exposes it. Append
    # only the part that is not already there.
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
            # back to English; a bare ImportError sailed past it and killed
            # the turn before any stage ran, with a traceback that never
            # mentioned the language.
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


__all__ = [
    "DEFAULT_LANGUAGE", "STORY_LANGUAGE_KEY", "LanguagePack",
    "LanguagePackError", "apply_common_prompt_policy", "apply_prompt_policy",
    "compositor_text", "compositor_value", "prompt_policy_common",
    "current_language_id", "installed_language_packs",
    "language_scope", "output_token_scale", "story_language_scope",
    "english_linguistic", "linguistic", "language_pack",
    "normalize_language_id", "register_renderer",
    "renderer_for", "require_language_pack", "set_story_language",
    "set_ui_language", "story_language", "ui_language",
]
