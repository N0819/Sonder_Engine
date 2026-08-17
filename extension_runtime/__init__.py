"""Installed extensions: discovery, activation, and the seams they hang on.

An extension is a directory under ``extensions/`` with a ``manifest.json``.  The
engine reads that manifest, decides what trust class the extension is in, and --
only if the host has enabled it -- imports its declared Python entry and calls
``register(api)`` once.  Everything after that happens through the facade in
``api.py``; this module owns discovery, the enable set, and the three total
dispatch helpers the core seams call.

Two failure modes are designed against explicitly, because both have already
happened in this repo:

* **One bad item must not kill the tree.**  ``language_runtime`` caches only the
  whole-tree success and raises on the first malformed pack
  (``language_runtime/__init__.py:263-268``), so a half-written directory took
  every language read down with it.  Discovery here is per-item: a malformed
  extension lands in ``load_errors()`` and its siblings load normally.
* **Nothing here may make ``import app`` fail.**  Discovery is lazy (a function
  with a cache, never module-import work), and every dispatch helper the core
  calls is total -- on any internal failure it logs and returns the safe value
  (plan unchanged, no-op) rather than raising into a turn.

Design intent, including why the plan-splice hook is the piece that had to
exist: ``docs/design/EXTENSIONS_DESIGN.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
from typing import Any, Callable

from .api import (
    CharacterAccess, CharacterHandle, CommitView, CommittedTurn, ExtState,
    ExtensionError, PSYCHOLOGY_STATE_KEYS, PayloadContext, Request,
    SonderExtensionAPI, StepView, enter_commit_scope, in_commit_scope,
    leave_commit_scope,
)

log = logging.getLogger("extension_runtime")

EXT_API_VERSION = 1
ENABLED_SETTING = "enabled_extensions"
ROOT_ENV = "SONDER_EXTENSIONS"
SAFE_MODE_ENV = "SONDER_EXTENSIONS_SAFE"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "extensions"

EXTENSION_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_VERSION = re.compile(r"^\d+(\.\d+)*$")
# Manifest keys the engine understands. Unknown ones are tolerated on purpose --
# a manifest written for a later ext_api must stay loadable, not become an error.
KNOWN_CAPABILITIES = (
    "stages", "chat_state", "char_state", "characters", "routing", "python",
    "ui", "system", "routes", "commit_domains",
)

_lock = threading.RLock()
_extensions: dict[str, "Extension"] | None = None
_errors: list[dict] = []
_registered: dict[str, "_Registration"] = {}
_apis: dict[str, SonderExtensionAPI] = {}
_activated_for: tuple | None = None
_observer_failures: dict[str, int] = {}


# ------------------------------------------------------------------ discovery


@dataclass(frozen=True)
class Extension:
    id: str
    name: str
    description: str
    version: str
    ext_api: int
    trust: str
    capabilities: dict
    provenance: Any
    path: Path

    @property
    def python_entry(self) -> str:
        return str(self.capabilities.get("python") or "").strip()

    @property
    def ui_entry(self) -> str:
        ui = self.capabilities.get("ui")
        if not isinstance(ui, dict):
            return ""
        return str(ui.get("js") or "").strip()

    @property
    def css_entry(self) -> str:
        ui = self.capabilities.get("ui")
        if not isinstance(ui, dict):
            return ""
        return str(ui.get("css") or "").strip()

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "ext_api": self.ext_api,
            "trust": self.trust,
            "capabilities": dict(self.capabilities),
            "provenance": self.provenance,
        }


def extension_root() -> Path:
    """Read the env override at CALL time, not import time.

    The language packs' root is frozen at import, which makes it untestable
    without reloading the module; this one follows the environment, so a test
    (or a host with a second extension directory) only has to set it.
    """
    return Path(os.environ.get(ROOT_ENV) or DEFAULT_ROOT)


def safe_mode() -> bool:
    """``SONDER_EXTENSIONS_SAFE=1`` -- boot with nothing enabled, no exceptions.

    The escape hatch for the case the whole trust model implies: an extension
    that breaks the app is otherwise fixable only by editing the database.
    """
    return str(os.environ.get(SAFE_MODE_ENV) or "").strip().lower() in (
        "1", "on", "true", "yes")


def _trust_class(manifest: dict, capabilities: dict, directory: Path) -> str:
    """code > prompt > data, by what the extension can actually do.

    Declared OR present: a ui.js sitting in the directory is code the moment the
    host enables the extension, whether or not the manifest admits to it.
    """
    ui = capabilities.get("ui") if isinstance(capabilities.get("ui"), dict) else {}
    if capabilities.get("python") or ui.get("js"):
        return "code"
    try:
        for child in directory.rglob("*"):
            if child.is_file() and child.suffix in (".py", ".js"):
                return "code"
    except OSError:
        pass
    stages = capabilities.get("stages")
    stage_prompts = isinstance(stages, list) and any(
        isinstance(stage, dict) and stage.get("prompt") for stage in stages)
    if manifest.get("prompts") or manifest.get("prompt_presets") or stage_prompts:
        return "prompt"
    return "data"


def _load_manifest(directory: Path) -> Extension:
    raw = (directory / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise ExtensionError("manifest.json must contain an object")

    ext_id = str(manifest.get("id") or "").strip()
    if not EXTENSION_ID.fullmatch(ext_id):
        raise ExtensionError(f"invalid extension id: {manifest.get('id')!r}")
    if ext_id != directory.name:
        raise ExtensionError(
            f"extension directory {directory.name!r} does not match id {ext_id!r}")

    version = str(manifest.get("version") or "").strip()
    if not _VERSION.fullmatch(version):
        raise ExtensionError(
            f"extension {ext_id!r} has an invalid version {manifest.get('version')!r}")

    if manifest.get("ext_api") != EXT_API_VERSION:
        raise ExtensionError(
            f"extension {ext_id!r} targets ext_api "
            f"{manifest.get('ext_api')!r}, not {EXT_API_VERSION}")

    capabilities = manifest.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        raise ExtensionError(f"extension {ext_id!r} capabilities must be an object")

    stages = capabilities.get("stages")
    if stages is not None and not isinstance(stages, list):
        raise ExtensionError(f"extension {ext_id!r} capabilities.stages must be a list")
    for stage in (stages or []):
        if not isinstance(stage, dict) or not str(stage.get("key") or "").strip():
            raise ExtensionError(
                f"extension {ext_id!r} declares a stage without a key")
        if not str(stage.get("anchor") or "").strip():
            raise ExtensionError(
                f"extension {ext_id!r} stage {stage.get('key')!r} declares no anchor")

    characters = capabilities.get("characters")
    if characters is not None and not isinstance(characters, list):
        raise ExtensionError(
            f"extension {ext_id!r} capabilities.characters must be a list")

    entry = str(capabilities.get("python") or "").strip()
    if entry and (Path(entry).is_absolute() or ".." in Path(entry).parts):
        raise ExtensionError(
            f"extension {ext_id!r} python entry must be inside its own directory")

    return Extension(
        id=ext_id,
        name=str(manifest.get("name") or ext_id),
        description=str(manifest.get("description") or ""),
        version=version,
        ext_api=EXT_API_VERSION,
        trust=_trust_class(manifest, capabilities, directory),
        capabilities=capabilities,
        provenance=manifest.get("provenance"),
        path=directory,
    )


def _scan() -> tuple[dict[str, Extension], list[dict]]:
    found: dict[str, Extension] = {}
    errors: list[dict] = []
    root = extension_root()
    try:
        children = sorted(child for child in root.iterdir() if child.is_dir())
    except OSError:
        return found, errors
    for directory in children:
        # `.staging-*` and friends: a half-written download in flight is not an
        # installed extension, and reporting it as a broken one is noise.
        if directory.name.startswith("."):
            continue
        if not (directory / "manifest.json").is_file():
            continue
        try:
            extension = _load_manifest(directory)
        except Exception as exc:
            errors.append({"dir": directory.name, "error": str(exc)})
            continue
        if extension.id in found:
            errors.append({"dir": directory.name,
                           "error": f"duplicate extension id {extension.id!r}"})
            continue
        found[extension.id] = extension
    return found, errors


def installed_extensions(*, refresh: bool = False) -> dict[str, Extension]:
    global _extensions, _errors
    with _lock:
        if _extensions is None or refresh:
            _extensions, _errors = _scan()
        return dict(_extensions)


def load_errors(*, refresh: bool = False) -> list[dict]:
    installed_extensions(refresh=refresh)
    with _lock:
        return [dict(item) for item in _errors]


def extension(ext_id: str) -> Extension | None:
    return installed_extensions().get(str(ext_id or ""))


# ------------------------------------------------------------------ enabling


def enabled_ids() -> list[str]:
    """The host's enabled set, filtered to what is actually installed."""
    if safe_mode():
        return []
    try:
        from db import get_setting
        raw = get_setting(ENABLED_SETTING)
    except Exception:
        return []
    try:
        stored = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(stored, list):
        return []
    installed = installed_extensions()
    return sorted({str(item) for item in stored if str(item) in installed})


def is_enabled(ext_id: str) -> bool:
    return str(ext_id or "") in enabled_ids()


def _write_enabled(ids) -> list[str]:
    from db import set_setting
    ordered = sorted({str(item) for item in ids})
    set_setting(ENABLED_SETTING, json.dumps(ordered))
    return ordered


def enable_extension(ext_id: str) -> dict:
    ext_id = str(ext_id or "")
    if ext_id not in installed_extensions():
        raise ExtensionError(f"no installed extension {ext_id!r}")
    _write_enabled(enabled_ids() + [ext_id])
    activate(refresh=True)
    with _lock:
        record = _registered.get(ext_id)
    return {"id": ext_id, "enabled": True,
            "error": record.error if record else None}


def disable_extension(ext_id: str) -> dict:
    ext_id = str(ext_id or "")
    _write_enabled([item for item in enabled_ids() if item != ext_id])
    activate(refresh=True)
    return {"id": ext_id, "enabled": False, "error": None}


# ------------------------------------------------------------------ activation


@dataclass
class _Registration:
    ext_id: str
    stages: list[dict] = field(default_factory=list)
    step_observers: list[tuple] = field(default_factory=list)
    commit_observers: list[Callable] = field(default_factory=list)
    commit_domains: list[dict] = field(default_factory=list)
    payload_hooks: list[Callable] = field(default_factory=list)
    routes: dict[str, dict] = field(default_factory=dict)
    specialists: list[str] = field(default_factory=list)
    error: str | None = None


def _record_stage(ext_id, key, full_key, *, anchor, label, handler) -> None:
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        from agents.runtime import register_step
        # `replace=True`: re-enabling an extension in a live process must not
        # collide with its own previous registration.
        register_step(full_key, handler, replace=True)
        record.stages = [stage for stage in record.stages
                         if stage["full_key"] != full_key]
        record.stages.append({"ext_id": ext_id, "key": key,
                              "full_key": full_key, "anchor": anchor,
                              "label": label})


def _record_step_observer(ext_id, pattern, fn) -> None:
    if not callable(fn):
        raise ExtensionError("on_step needs a callable")
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        record.step_observers.append((pattern, fn))


def _record_commit_observer(ext_id, fn) -> None:
    if not callable(fn):
        raise ExtensionError("on_turn_committed needs a callable")
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        record.commit_observers.append(fn)


def _record_commit_domain(ext_id, name, fn, on_error) -> None:
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        record.commit_domains = [item for item in record.commit_domains
                                 if item["name"] != name]
        record.commit_domains.append({"ext_id": ext_id, "name": name, "fn": fn,
                                      "on_error": on_error})


def _record_payload_hook(ext_id, fn) -> None:
    if not callable(fn):
        raise ExtensionError("on_character_payload needs a callable")
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        record.payload_hooks.append(fn)


def _record_specialist(ext_id, full_name) -> None:
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        if full_name not in record.specialists:
            record.specialists.append(full_name)


def _record_route(ext_id, path, fn, methods) -> None:
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        for method in methods:
            record.routes[f"{method} {path}"] = {"fn": fn, "path": path,
                                                 "method": method}


def _module_name(ext_id: str) -> str:
    """A name the LOADER constructs -- no manifest string reaches import.

    The manifest names a FILE, never a module path, and that file is resolved
    and containment-checked before anything is executed.  An extension can
    therefore never make the engine import something outside its own directory
    by writing a dotted string in JSON.
    """
    return "sonder_ext_" + re.sub(r"[^a-z0-9]+", "_", ext_id.lower())


def _import_entry(ext: Extension):
    base = ext.path.resolve()
    target = (base / ext.python_entry).resolve()
    if base != target and base not in target.parents:
        raise ExtensionError(
            f"extension {ext.id!r} python entry escapes its own directory")
    if not target.is_file():
        raise ExtensionError(
            f"extension {ext.id!r} python entry {ext.python_entry!r} is missing")
    name = _module_name(ext.id)
    spec = importlib.util.spec_from_file_location(name, target)
    if spec is None or spec.loader is None:
        raise ExtensionError(f"extension {ext.id!r} entry could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _deregister(ext_id: str, *, error: str | None = None) -> None:
    record = _registered.get(ext_id)
    if record is None:
        if error:
            _registered[ext_id] = _Registration(ext_id, error=error)
        return
    try:
        from agents.runtime import STEP_HANDLERS
        for stage in record.stages:
            STEP_HANDLERS.pop(stage["full_key"], None)
    except Exception:
        log.exception("could not unregister steps for extension %s", ext_id)
    if record.specialists:
        # Director specialists live in that module's own registries, so
        # disabling has to reach in and take them back out -- otherwise a
        # disabled extension keeps being dispatched every beat.
        try:
            from agents.director import unregister_specialists
            unregister_specialists(ext_id)
        except Exception:
            log.exception(
                "could not unregister specialists for extension %s", ext_id)
    if error is None:
        _registered.pop(ext_id, None)
        sys.modules.pop(_module_name(ext_id), None)
    else:
        _registered[ext_id] = _Registration(ext_id, error=error)


def _activate_one(ext_id: str) -> None:
    ext = installed_extensions().get(ext_id)
    if ext is None:
        _registered[ext_id] = _Registration(ext_id, error="not installed")
        return
    _registered[ext_id] = _Registration(ext_id)
    api = _apis.get(ext_id)
    if api is None or api.data_path != ext.path:
        api = SonderExtensionAPI(ext_id, ext.path)
        _apis[ext_id] = api
    if not ext.python_entry:
        return
    try:
        module = _import_entry(ext)
        register = getattr(module, "register", None)
        if not callable(register):
            raise ExtensionError(
                f"extension {ext_id!r} entry defines no register(api)")
        register(api)
    except Exception as exc:
        # Isolated exactly like discovery: this extension is disabled with a
        # reason the host can read, and every sibling stays live.
        log.exception("extension %s failed to register", ext_id)
        _deregister(ext_id, error=str(exc))


def activate(*, refresh: bool = False) -> None:
    """Bring live registrations in line with the enabled set.

    Called by every seam, so an extension enabled before this process started
    loads on first use rather than needing a boot hook.
    """
    global _activated_for
    with _lock:
        wanted = tuple(enabled_ids())
        if _activated_for == wanted and not refresh:
            return
        for ext_id in list(_registered):
            if ext_id not in wanted:
                _deregister(ext_id)
        for ext_id in wanted:
            if ext_id in _registered:
                continue
            _activate_one(ext_id)
        _activated_for = wanted


def reload() -> None:
    """Forget everything. The next read rescans; nothing is scanned here.

    Deliberately lazy rather than eager: this is called from a host route and
    from tests that have just changed the tree, and an eager rescan would cache
    the state of the directory at the moment of the call rather than at the
    moment of the next read.
    """
    global _activated_for, _extensions
    with _lock:
        for ext_id in list(_registered):
            _deregister(ext_id)
        _registered.clear()
        _activated_for = None
        _extensions = None
        _errors.clear()
        _observer_failures.clear()


def disabled_reasons() -> dict[str, str]:
    with _lock:
        return {ext_id: record.error for ext_id, record in _registered.items()
                if record.error}


def registered_stages() -> list[dict]:
    with _lock:
        stages: list[dict] = []
        for record in _registered.values():
            stages.extend(dict(stage) for stage in record.stages)
    stages.sort(key=lambda stage: (stage["ext_id"], stage["key"]))
    return stages


def listing() -> list[dict]:
    """Everything the host UI needs about installed extensions."""
    try:
        activate()
    except Exception:
        log.exception("extension activation failed while listing")
    enabled = set(enabled_ids())
    reasons = disabled_reasons()
    out = []
    for ext in sorted(installed_extensions().values(), key=lambda e: e.id):
        row = ext.public()
        row["enabled"] = ext.id in enabled
        row["error"] = reasons.get(ext.id)
        out.append(row)
    return out


# ------------------------------------------------------------------ seams


def apply_plan_splices(plan, chat_id=None):
    """Place every enabled extension's registered stage into a turn's plan.

    This is the half `register_step` deliberately punted on, and the only reason
    a third party had to edit `agents/runtime.py` at all.  Two properties are
    load-bearing:

    * **Pure function of durable settings + manifests.**  `resume_key_for_turn`
      and every `from_key` path rebuild this plan from stored step content, so a
      splice that varied with anything else would break resume.
    * **Silent when it cannot apply.**  An unknown anchor, or an anchor naming a
      core step this particular turn does not run, means the extension stage is
      simply not planned this turn -- not an error, and not a stage bolted onto
      a different position, which would make the plan differ between the run and
      the recompute.
    """
    try:
        activate()
        stages = registered_stages()
        if not stages:
            return plan
        before: dict[str, list] = {}
        after: dict[str, list] = {}
        for stage in stages:
            mode, _, core = str(stage["anchor"]).partition(":")
            core = core.strip()
            if mode not in ("after", "before") or not core:
                continue
            # `character:<id>` is the runtime's reserved dynamic namespace and
            # is planned as a parallel group; splicing into the middle of one
            # would silently serialize it.
            if core.startswith("character:") or core.startswith("ext:"):
                continue
            (after if mode == "after" else before).setdefault(core, []).append(
                (stage["full_key"], stage["label"]))
        if not before and not after:
            return plan
        out = []
        seen = set()
        for key, label in plan:
            if key in seen:
                out.append((key, label))
                continue
            seen.add(key)
            out.extend(before.get(key, ()))
            out.append((key, label))
            out.extend(after.get(key, ()))
        return out
    except Exception:
        log.exception("extension plan splices failed; plan left unchanged")
        return plan


def notify_step_saved(ctx, key, content) -> None:
    """Tell `on_step` observers a step's content just became durable.

    Read-only by construction: the observer gets the saved key and content,
    never the context, so it cannot feed one stage's output into another's
    payload.  Every callback is individually contained -- a broken observer is
    a counted, logged failure, never a failed turn.
    """
    try:
        activate()
        with _lock:
            observers = [(record.ext_id, pattern, fn)
                         for record in _registered.values()
                         for pattern, fn in record.step_observers]
        if not observers:
            return
        step_key = str(key or "")
        for ext_id, pattern, fn in observers:
            try:
                if not fnmatch.fnmatchcase(step_key, str(pattern)):
                    continue
                fn(step_key, content)
            except Exception:
                _observer_failures[ext_id] = _observer_failures.get(ext_id, 0) + 1
                log.exception("extension %s on_step observer failed on %s",
                              ext_id, step_key)
    except Exception:
        log.exception("extension step notification failed")


def dispatch_turn_committed(ctx) -> dict:
    """Run every `on_turn_committed` hook after the turn's facts are durable.

    The one write-enabled seam: the commit scope is entered around each hook so
    `ExtState.set()` works here and nowhere else.  Returns a small report the
    commit result carries, so a silently-failing extension is visible in the
    same place every other out-of-band failure is.
    """
    report = {"ran": [], "errors": {}}
    try:
        activate()
        with _lock:
            hooks = [(record.ext_id, fn) for record in _registered.values()
                     for fn in record.commit_observers]
        if not hooks:
            return report
        for ext_id, fn in hooks:
            api = _apis.get(ext_id)
            if api is None:
                continue
            token = enter_commit_scope()
            try:
                fn(CommittedTurn(api, ctx))
                report["ran"].append(ext_id)
            except Exception as exc:
                _observer_failures[ext_id] = _observer_failures.get(ext_id, 0) + 1
                log.exception("extension %s on_turn_committed hook failed", ext_id)
                report["errors"][ext_id] = str(exc)
            finally:
                leave_commit_scope(token)
    except Exception as exc:
        log.exception("extension commit dispatch failed")
        report["errors"]["_dispatch"] = str(exc)
    return report


def run_commit_domains(ctx, results) -> None:
    """Run every registered commit domain INSIDE the turn's transaction.

    Called from `commit.py`'s `_commit_all_locked`, which is why this one is
    NOT total in the way the other seams are: a domain registered with
    `on_error="fail"` is asking for its failure to roll the turn back, and
    swallowing that here would make the option a lie. Everything else --
    activation, lookup, a domain that only warns -- still cannot cost a turn.
    """
    try:
        activate()
        with _lock:
            domains = [dict(item) for record in _registered.values()
                       for item in record.commit_domains]
    except Exception:
        log.exception("extension commit domains could not be resolved")
        return
    domains.sort(key=lambda item: (item["ext_id"], item["name"]))
    for domain in domains:
        api = _apis.get(domain["ext_id"])
        if api is None:
            continue
        name = f"ext:{domain['ext_id']}:{domain['name']}"
        try:
            results[name] = domain["fn"](CommitView(api, ctx))
        except Exception as exc:
            log.exception("extension commit domain %s failed", name)
            _observer_failures[domain["ext_id"]] = _observer_failures.get(
                domain["ext_id"], 0) + 1
            if domain["on_error"] == "fail":
                raise
            note = getattr(ctx, "add_warning", None)
            if callable(note):
                try:
                    note(f"commit domain {name} failed (turn kept): {exc}")
                except Exception:
                    pass
            results[name] = {"error": str(exc)}


def dispatch_character_payload(ctx, char_id, payload, names=()):
    """Let routing hooks rewrite one character's payload, with attribution.

    The powerful seam, and the one the responsibility doctrine is about: a hook
    may add, remove or rewrite anything here. What is guaranteed is not
    restraint but LEGIBILITY -- every top-level key a hook changes is recorded
    against its extension id on the context, so a mind that knows what it
    should not names its author in one read rather than looking like an engine
    defect.

    Total: any failure leaves the payload exactly as the engine assembled it.
    """
    if not isinstance(payload, dict):
        return payload
    try:
        activate()
        with _lock:
            hooks = [(record.ext_id, fn) for record in _registered.values()
                     for fn in record.payload_hooks]
        if not hooks:
            return payload
    except Exception:
        log.exception("extension payload hooks could not be resolved")
        return payload

    current = payload
    for ext_id, fn in hooks:
        api = _apis.get(ext_id)
        if api is None:
            continue
        before = current
        # Fingerprint BEFORE the call. Comparing the returned object against
        # the passed one is the obvious implementation and it does not work:
        # a hook is handed the real payload, so the ordinary
        #
        #     def hook(payload, info):
        #         payload["forbidden_fact"] = "..."
        #         return payload
        #
        # mutates both sides of the comparison at once and the diff comes back
        # EMPTY -- an extension altering what a mind knows with no attribution
        # record, which is precisely the guarantee this seam exists to make.
        # Returning `None` (leave it alone) after mutating in place is the same
        # hole by a shorter route.
        stamps = _payload_stamps(before)
        try:
            info = PayloadContext(api, ctx, char_id, names)
            result = fn(before, info)
        except Exception:
            _observer_failures[ext_id] = _observer_failures.get(ext_id, 0) + 1
            log.exception("extension %s payload hook failed", ext_id)
            continue
        if result is None:
            result = before
        if not isinstance(result, dict):
            log.warning("extension %s payload hook returned %s; ignored",
                        ext_id, type(result).__name__)
            continue
        after = _payload_stamps(result)
        changed = sorted({key for key in set(stamps) | set(after)
                          if stamps.get(key) != after.get(key)})
        if changed:
            _note_routing(ctx, ext_id, char_id, changed)
        current = result
    return current


def _payload_stamps(payload) -> dict:
    """A comparable snapshot of each top-level value, taken by VALUE.

    Serialised rather than shallow-copied because a shallow copy still shares
    the nested objects: `payload["perception"]["view"] = ...` would leave the
    copy and the original identical and slip past the audit. Cost is one dump
    of the payload per registered hook, on a turn that is about to spend
    seconds in a model call -- and zero on the overwhelmingly common turn where
    no hook is registered at all, because this is never reached.

    Top-level keys are the resolution the record is kept at: the question is
    WHO touched this mind, not which leaf moved.
    """
    stamps = {}
    for key, value in payload.items():
        try:
            stamps[key] = json.dumps(value, sort_keys=True, default=str,
                                     ensure_ascii=False)
        except Exception:
            # An unserialisable value is still comparable by its repr, and a
            # value that cannot even be repr'd must read as CHANGED rather
            # than as untouched -- silence here is the failure mode.
            try:
                stamps[key] = repr(value)
            except Exception:
                stamps[key] = object()
    return stamps


def _note_routing(ctx, ext_id, char_id, changed) -> None:
    """Record a routing edit where the turn's own diagnostics already live."""
    log.info("extension %s rewrote character %s payload keys: %s",
             ext_id, char_id, ", ".join(changed))
    try:
        entries = ctx.get("_extension_routing")
        if not isinstance(entries, list):
            entries = []
        entries.append({"ext": ext_id, "char_id": int(char_id),
                        "changed": list(changed)})
        ctx["_extension_routing"] = entries
    except Exception:
        log.exception("could not record extension routing note")


def routing_notes(ctx) -> list:
    try:
        entries = ctx.get("_extension_routing")
    except Exception:
        return []
    return [dict(item) for item in entries] if isinstance(entries, list) else []


def dispatch_route(ext_id: str, method: str, path: str, query=None, body=None):
    """Serve one call to an extension's own route. Raises for the host to map."""
    activate()
    ext_id = str(ext_id or "")
    if not is_enabled(ext_id):
        raise ExtensionError(f"extension {ext_id!r} is not enabled")
    path = "/" + str(path or "").strip().strip("/")
    with _lock:
        record = _registered.get(ext_id)
        entry = record.routes.get(f"{str(method).upper()} {path}") if record else None
    if entry is None:
        raise ExtensionError(
            f"extension {ext_id!r} serves no {str(method).upper()} {path}")
    api = _apis.get(ext_id)
    if api is None:
        raise ExtensionError(f"extension {ext_id!r} is not active")
    return entry["fn"](Request(method, path, query, body))


def registered_routes() -> list[dict]:
    with _lock:
        return sorted(
            ({"ext_id": record.ext_id, "method": entry["method"],
              "path": entry["path"]}
             for record in _registered.values()
             for entry in record.routes.values()),
            key=lambda row: (row["ext_id"], row["path"], row["method"]))


def run_specialist_call(spec, scope, payload):
    """The model call an extension-owned Director specialist runs as.

    Lives HERE rather than in `agents/director.py` because of what it does:
    it parses permissively, and `test_stage_modules_stay_on_strict_path`
    forbids that in a stage module. The rule is right and worth keeping exactly
    as strict as it is -- a Director stage's own output reaches `commit.py`, so
    it must go through `schemas.validate_llm_output_strict` or a malformed
    answer commits as junk. An extension specialist's output does not: its
    channels are namespaced `ext:<id>:<channel>` and no commit domain reads
    one, so nothing it writes can commit by itself. An extension also owns the
    shape of its own channels, which `SCHEMA_MAP` cannot know. Same split, and
    same reason, as `api.llm_json`.
    """
    from agents.common import jparse
    from providers import chat_complete

    sheet = (
        f"{spec['prompt']}\n\n"
        "Answer with a JSON object. Emit ONLY these keys, and only where this "
        "beat gives them content:\n"
        + "\n".join(f"- {channel}" for channel in scope)
    )
    return jparse(chat_complete(
        spec["role"], sheet,
        json.dumps(payload, ensure_ascii=False, default=str),
        temperature=0.2, max_tokens=8000))


def registered_specialists() -> list[dict]:
    with _lock:
        return sorted(
            ({"ext_id": record.ext_id, "name": name}
             for record in _registered.values()
             for name in record.specialists),
            key=lambda row: (row["ext_id"], row["name"]))


def registered_commit_domains() -> list[dict]:
    with _lock:
        return sorted(
            ({"ext_id": item["ext_id"], "name": item["name"],
              "on_error": item["on_error"]}
             for record in _registered.values()
             for item in record.commit_domains),
            key=lambda row: (row["ext_id"], row["name"]))


def observer_failures() -> dict[str, int]:
    with _lock:
        return dict(_observer_failures)


# ------------------------------------------------------------------ assets


def asset_path(ext_id: str, relative: str) -> Path:
    """Resolve one file inside an extension's directory, or refuse.

    Containment is checked on the RESOLVED path, so a symlink pointing out of
    the tree is refused the same way `../` is.
    """
    ext = installed_extensions().get(str(ext_id or ""))
    if ext is None:
        raise ExtensionError(f"no installed extension {ext_id!r}")
    candidate = Path(str(relative or ""))
    if not str(relative or "").strip() or candidate.is_absolute():
        raise ExtensionError("asset path must be relative")
    if any(part in ("..", "") for part in candidate.parts):
        raise ExtensionError("asset path may not traverse directories")
    base = ext.path.resolve()
    target = (base / candidate).resolve()
    if base not in target.parents:
        raise ExtensionError("asset path escapes the extension directory")
    if not target.is_file():
        raise ExtensionError(f"extension {ext.id!r} has no asset {relative!r}")
    return target


def _wrap_ui(ext: "Extension", source: str) -> str:
    """Attribute an extension's script to it, and give it its own scope.

    The begin/end pair is what lets the front end attribute every registration
    to an extension without the extension cooperating (and without it being
    able to claim another's name by doing so).

    The function scope around it is not decoration. Concatenation puts every
    extension's top level in ONE script: two extensions declaring `const EXT`
    is a SyntaxError that kills the whole bundle, and re-injecting a script on
    re-enable would redeclare against itself. Both disappear inside a scope.
    An extension that wants a global must say so -- `window.foo = ...`.
    """
    return (
        f'(function () {{\n'
        f'window.Sonder && Sonder._begin("{ext.id}");\n'
        f'try {{\n'
        f'{source}\n'
        f'}} catch (error) {{\n'
        f'  console.error({{ extension: "{ext.id}", error: error }});\n'
        f'  window.Sonder && Sonder._fault("{ext.id}", error);\n'
        f'}} finally {{\n'
        f'  window.Sonder && Sonder._end();\n'
        f'}}\n'
        f'}})();\n'
        f'//# sourceURL=/api/extensions/{ext.id}/asset/{ext.ui_entry}\n'
    )


def _read_asset(ext: "Extension", relative: str) -> str | None:
    try:
        return asset_path(ext.id, relative).read_text(encoding="utf-8")
    except Exception:
        log.exception("extension %s asset %s could not be read",
                      ext.id, relative)
        return None


def extension_script(ext_id: str) -> str:
    """One enabled extension's wrapped UI script, or an empty string.

    Exists so the browser can load a single extension AFTER page load, which is
    what makes enable/disable hot rather than reload-only.
    """
    if safe_mode():
        return ""
    ext = installed_extensions().get(str(ext_id or ""))
    if ext is None or not ext.ui_entry or not is_enabled(ext.id):
        return ""
    source = _read_asset(ext, ext.ui_entry)
    return "" if source is None else _wrap_ui(ext, source)


def extension_styles(ext_id: str) -> str:
    """One enabled extension's stylesheet, or an empty string."""
    if safe_mode():
        return ""
    ext = installed_extensions().get(str(ext_id or ""))
    if ext is None or not ext.css_entry or not is_enabled(ext.id):
        return ""
    source = _read_asset(ext, ext.css_entry)
    return "" if source is None else source


def ui_bundle() -> str:
    """Every enabled extension's UI script, concatenated in id order.

    Served from `/api/` rather than `/static/` on purpose: `access_control`
    only guards `/api/*`, so extension code stays session-gated and never
    reaches the guest page, which loads its own shell entirely.
    """
    if safe_mode():
        return ""
    parts = []
    enabled = set(enabled_ids())
    for ext in sorted(installed_extensions().values(), key=lambda e: e.id):
        if ext.id not in enabled or not ext.ui_entry:
            continue
        source = _read_asset(ext, ext.ui_entry)
        if source is None:
            continue
        parts.append(_wrap_ui(ext, source))
    return "\n".join(parts)


def ui_styles() -> str:
    """Every enabled extension's stylesheet, concatenated in id order.

    A separate document rather than a `<style>` written by the bundle, so a
    theme lands before first paint instead of flashing the host's colours
    first. Each block is fenced by a comment naming its owner, which is how the
    host removes one again on disable.
    """
    if safe_mode():
        return ""
    parts = []
    enabled = set(enabled_ids())
    for ext in sorted(installed_extensions().values(), key=lambda e: e.id):
        if ext.id not in enabled or not ext.css_entry:
            continue
        source = _read_asset(ext, ext.css_entry)
        if source is None:
            continue
        parts.append(f"/* extension: {ext.id} */\n{source}")
    return "\n\n".join(parts)


__all__ = [
    "CharacterAccess", "CharacterHandle", "CommitView", "CommittedTurn",
    "EXT_API_VERSION", "ENABLED_SETTING", "ExtState", "Extension",
    "ExtensionError", "PSYCHOLOGY_STATE_KEYS", "PayloadContext", "Request",
    "SonderExtensionAPI", "StepView", "activate", "apply_plan_splices",
    "asset_path", "disable_extension", "disabled_reasons",
    "dispatch_character_payload", "dispatch_route", "dispatch_turn_committed",
    "enable_extension", "enabled_ids", "extension", "extension_root",
    "extension_script", "extension_styles", "in_commit_scope",
    "installed_extensions", "is_enabled", "listing", "load_errors",
    "notify_step_saved", "observer_failures", "registered_commit_domains",
    "registered_routes", "registered_specialists", "registered_stages",
    "reload", "routing_notes", "run_commit_domains", "run_specialist_call",
    "safe_mode", "ui_bundle", "ui_styles",
]


# ---------------------------------------------------------------------------
# Install and removal
#
# Phase 1 of the distribution plan: a host installs from a local directory or
# a URL, with nothing reviewing what arrives. Phase 2 adds a registry of
# reviewed extensions, and every field it needs (stable id, version, an
# integrity hash, a provenance record) is written HERE so that phase is an
# addition rather than a migration of everything already installed.
#
# The honesty about that is in the consent dialog, not in a restriction: an
# extension runs in this process with the engine's own access. What this code
# owes the host is that a BROKEN or HOSTILE archive cannot damage the install
# before they ever get to consent -- so the checks below are about the archive,
# not about the code's intentions.
# ---------------------------------------------------------------------------

#: A downloaded bundle is held in memory before it is written, so it is capped.
#: Generous for a real extension (the reference one is a few KB) and far below
#: anything that could exhaust a host running this on their own machine.
MAX_BUNDLE_BYTES = 32 * 1024 * 1024
#: What the bundle may become once unpacked. The download cap above bounds the
#: COMPRESSED bytes and says nothing about the expanded ones: zip is happy to
#: turn a few megabytes of zeroes into several gigabytes, so a bundle that
#: passes every path check can still fill the host's disk. Generous for a real
#: extension -- the reference one is a few KB -- and far below anything that
#: matters on a machine someone plays on.
MAX_EXTRACTED_BYTES = 256 * 1024 * 1024
#: And a count, because a million empty files costs inodes rather than bytes
#: and would slip under the ceiling above entirely.
MAX_ARCHIVE_MEMBERS = 4096


def _safe_extract(archive, destination: Path) -> None:
    """Extract a zip, refusing any member that would escape `destination` --
    or that would cost more than an extension has any business costing.

    ZIP SLIP: an archive may name `../../etc/thing` or an absolute path, and a
    naive extractall writes it wherever the name says. The engine's directory
    is user-writable by design here -- that is what makes in-UI install
    possible -- so this is the one place a downloaded file chooses a path.
    Symlinks are refused for the same reason: a link is a path that resolves
    later, after any check.

    ZIP BOMB: every check is made against the DECLARED sizes in the central
    directory before a single byte is written, and the write is then verified
    against them. Checking the declaration alone would trust the archive about
    its own size, which is the same mistake as trusting it about its own paths.
    """
    root = destination.resolve()
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ExtensionError(
            f"archive holds {len(members)} files, more than the "
            f"{MAX_ARCHIVE_MEMBERS} an extension may install")
    declared = 0
    for member in members:
        name = member.filename
        if name.startswith("/") or ".." in Path(name).parts:
            raise ExtensionError(f"archive escapes its directory: {name!r}")
        # 0xA000 is S_IFLNK in the high bits of a zip's external attributes.
        if (member.external_attr >> 16) & 0xF000 == 0xA000:
            raise ExtensionError(f"archive contains a symlink: {name!r}")
        target = (root / name).resolve()
        if target != root and root not in target.parents:
            raise ExtensionError(f"archive escapes its directory: {name!r}")
        declared += int(member.file_size or 0)
        if declared > MAX_EXTRACTED_BYTES:
            raise ExtensionError(
                f"archive expands to more than "
                f"{MAX_EXTRACTED_BYTES // (1024 * 1024)}MB")

    # Member by member, counting what actually lands. CPython's `zipfile`
    # happens to enforce `file_size` on read, so a lie in the central directory
    # is caught before it costs anything -- but that is luck this code does not
    # own, and `extractall` would believe the declaration it was just handed.
    written = 0
    for member in members:
        archive.extract(member, root)
        if member.is_dir():
            continue
        try:
            written += (root / member.filename).stat().st_size
        except OSError:
            continue
        if written > MAX_EXTRACTED_BYTES:
            raise ExtensionError(
                f"archive expands to more than "
                f"{MAX_EXTRACTED_BYTES // (1024 * 1024)}MB")


def _staged_bundle_root(staged: Path) -> Path:
    """The directory holding `manifest.json`, unwrapping one nesting level.

    An archive made with `zip -r ext.zip my-extension/` unpacks to a single
    directory rather than to the manifest, and that is what people produce, so
    accept it rather than making them repack.
    """
    if (staged / "manifest.json").is_file():
        return staged
    entries = [p for p in staged.iterdir() if not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir() \
            and (entries[0] / "manifest.json").is_file():
        return entries[0]
    raise ExtensionError("no manifest.json in the bundle")


def install_extension(source: str, *, provenance: str | None = None) -> dict:
    """Install from a local directory or an http(s) URL. Returns the listing row.

    Staged, validated, then moved into place with `os.replace`, so an install
    interrupted at any point leaves either the old extension or none -- never a
    half-written directory that then fails to load forever. (Learned from a
    non-atomic checkpoint write in the translation tool, which corrupted itself
    on interrupt and could only be recovered by discarding paid work.)
    """
    import hashlib
    import shutil
    import tempfile
    import zipfile

    source = str(source or "").strip()
    if not source:
        raise ExtensionError("nothing to install")
    root = extension_root()
    root.mkdir(parents=True, exist_ok=True)
    digest = None

    with tempfile.TemporaryDirectory(dir=root) as tmp:
        staged = Path(tmp) / "staged"
        staged.mkdir()
        if source.startswith(("http://", "https://")):
            import requests

            response = requests.get(source, timeout=60, stream=True)
            response.raise_for_status()
            blob = b""
            for chunk in response.iter_content(64 * 1024):
                blob += chunk
                if len(blob) > MAX_BUNDLE_BYTES:
                    raise ExtensionError(
                        f"bundle is larger than {MAX_BUNDLE_BYTES // (1024*1024)}MB")
            digest = hashlib.sha256(blob).hexdigest()
            import io

            try:
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    _safe_extract(archive, staged)
            except zipfile.BadZipFile as exc:
                raise ExtensionError(f"not a zip archive: {exc}") from exc
            provenance = provenance or f"url:{source}"
        else:
            origin = Path(source).expanduser()
            if not origin.is_dir():
                raise ExtensionError(f"not a directory: {source}")
            shutil.copytree(origin, staged, dirs_exist_ok=True,
                            symlinks=False, ignore=shutil.ignore_patterns(
                                "__pycache__", "*.pyc", ".git"))
            provenance = provenance or f"local:{origin.name}"

        bundle = _staged_bundle_root(staged)
        # `_load_manifest` requires the DIRECTORY NAME to equal the declared
        # id, so the bundle is renamed to its own id before validation --
        # inside the staging area, where a bad name costs nothing.
        declared = json.loads(
            (bundle / "manifest.json").read_text(encoding="utf-8"))
        claimed = str(declared.get("id") or "")
        if not EXTENSION_ID.fullmatch(claimed):
            raise ExtensionError(f"invalid extension id: {claimed!r}")
        if bundle.name != claimed:
            renamed = bundle.parent / claimed
            if renamed.exists():
                shutil.rmtree(renamed)
            os.replace(bundle, renamed)
            bundle = renamed
        # Validate BEFORE anything is moved into place: a bundle that cannot
        # produce a manifest never becomes an installed directory.
        candidate = _load_manifest(bundle)
        destination = root / candidate.id
        if destination.exists():
            raise ExtensionError(
                f"{candidate.id!r} is already installed — remove it first")
        # Record where it came from, so phase 2 can tell a reviewed install
        # from a sideloaded one without re-deriving it.
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["provenance"] = provenance
        if digest:
            manifest["sha256"] = digest
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        os.replace(bundle, destination)

    reload()
    for row in listing():
        if row["id"] == candidate.id:
            return row
    raise ExtensionError(f"{candidate.id!r} did not load after install")


def remove_extension(extension_id: str) -> dict:
    """Delete an installed extension. Its stored per-story state is LEFT.

    Removal takes the code, not the history: a story played with an extension
    keeps whatever that extension wrote under `world["ext:<id>"]`, so
    reinstalling picks the story back up rather than starting it over, and a
    story remains loadable in the meantime. Orphaned state is small, inert, and
    the alternative -- deleting it -- silently destroys play the host may not
    have meant to discard.
    """
    import shutil

    extension_id = str(extension_id or "")
    if not EXTENSION_ID.fullmatch(extension_id):
        raise ExtensionError(f"invalid extension id: {extension_id!r}")
    directory = extension_root() / extension_id
    if not directory.is_dir():
        raise ExtensionError(f"{extension_id!r} is not installed")
    try:
        disable_extension(extension_id)
    except Exception:
        pass  # removing it is the point; a failed disable must not block that
    shutil.rmtree(directory)
    reload()
    return {"id": extension_id, "removed": True}
