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
import importlib.machinery
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
from typing import Any, Callable

from .api import (
    CharacterAccess, CharacterHandle, CommitView, CommittedTurn,
    DirectorBlock, DirectorContext, DocumentStore, ExtState,
    ExtensionError, NarrationBlock, NarrationContext,
    PSYCHOLOGY_STATE_KEYS, PayloadContext, Request,
    SonderExtensionAPI, StepView, document_path, enter_commit_scope,
    in_commit_scope, leave_commit_scope,
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
    #: Where an update would come from. Written at install for a git source and
    #: absent for every other, which is what makes "cannot be checked" an
    #: answer this module can give honestly rather than a guess it has to make.
    source_url: str = ""
    source_ref: str = ""
    commit: str = ""

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
    def module_entry(self) -> str:
        """An ES module entry, if this extension ships one.

        The alternative to `ui.js`, not a replacement for it: a classic entry
        is concatenated into one bundle and cannot contain `import`, which is
        fine for a panel and impossible for an extension built as a module
        graph. Declaring both is allowed and both are served -- a migration
        wants to move one file at a time.
        """
        ui = self.capabilities.get("ui")
        if not isinstance(ui, dict):
            return ""
        return str(ui.get("module") or "").strip()

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
            "source_url": self.source_url,
            "source_ref": self.source_ref,
            "commit": self.commit,
            "updatable": bool(self.source_url),
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
    if capabilities.get("python") or ui.get("js") or ui.get("module"):
        return "code"
    try:
        for child in directory.rglob("*"):
            if child.is_file() and child.suffix in (".py", ".js", ".mjs"):
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
    # Every failure out of this function is an ExtensionError, including a
    # manifest that is not JSON. Discovery catches everything anyway, but
    # install and update surface what this raises straight to the host, and
    # `JSONDecodeError: Expecting property name` is a stack trace's answer to
    # a question the host asked in English.
    try:
        raw = (directory / "manifest.json").read_text(encoding="utf-8")
    except OSError as exc:
        raise ExtensionError(f"manifest.json could not be read: {exc}") from exc
    try:
        manifest = json.loads(raw)
    except ValueError as exc:
        raise ExtensionError(f"manifest.json is not valid JSON: {exc}") from exc
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
        source_url=str(manifest.get("source_url") or ""),
        source_ref=str(manifest.get("source_ref") or ""),
        commit=str(manifest.get("commit") or ""),
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
        # A dotted directory is not an extension: hidden entries under this
        # root belong to the host or the filesystem, never to the scan.
        if directory.name.startswith("."):
            continue
        # THIS is what keeps an install in flight out of the scan, and it is
        # the reason a half-written download is never reported as a broken
        # extension. Staging happens in a `tempfile.TemporaryDirectory` under
        # this same root, which is named `tmpXXXXXXXX` and holds the bundle
        # one level DEEPER -- so it has no manifest of its own here. Nothing
        # in this tree has ever created a dot-prefixed staging directory; the
        # guard above has never fired for that reason.
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


def _stored_enabled_ids() -> list[str]:
    """The DURABLE enabled set, exactly as the host last chose it.

    Unfiltered on purpose. Safe mode and a broken manifest are reasons not to
    RUN an extension; neither is the host changing their mind about it, and a
    toggle that rewrote this from the filtered view would make them the same
    thing -- boot safe, disable the culprit, and the recovery workflow is what
    destroys every other extension's enablement.
    """
    try:
        from core.db import get_setting
        raw = get_setting(ENABLED_SETTING)
    except Exception:
        return []
    try:
        stored = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(stored, list):
        return []
    return sorted({str(item) for item in stored})


def enabled_ids() -> list[str]:
    """What may run right now: the stored set, filtered to what will load.

    A READ. Never the input to a write -- see `_stored_enabled_ids`.
    """
    if safe_mode():
        return []
    installed = installed_extensions()
    return [item for item in _stored_enabled_ids() if item in installed]


def is_enabled(ext_id: str) -> bool:
    return str(ext_id or "") in enabled_ids()


def _write_enabled(ids) -> list[str]:
    from core.db import set_setting
    ordered = sorted({str(item) for item in ids})
    set_setting(ENABLED_SETTING, json.dumps(ordered))
    return ordered


def enable_extension(ext_id: str) -> dict:
    ext_id = str(ext_id or "")
    if ext_id not in installed_extensions():
        raise ExtensionError(f"no installed extension {ext_id!r}")
    _write_enabled(_stored_enabled_ids() + [ext_id])
    activate(refresh=True)
    with _lock:
        record = _registered.get(ext_id)
    return {"id": ext_id, "enabled": True,
            "error": record.error if record else None}


def disable_extension(ext_id: str) -> dict:
    ext_id = str(ext_id or "")
    _write_enabled([item for item in _stored_enabled_ids()
                    if item != ext_id])
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
    narration_hooks: list[Callable] = field(default_factory=list)
    director_hooks: list[Callable] = field(default_factory=list)
    result_validators: list[dict] = field(default_factory=list)
    routes: dict[str, dict] = field(default_factory=dict)
    specialists: list[str] = field(default_factory=list)
    model_lanes: list[dict] = field(default_factory=list)
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


def _record_result_validator(ext_id, fn, on_error) -> None:
    if not callable(fn):
        raise ExtensionError("on_director_result needs a callable")
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        record.result_validators.append(
            {"fn": fn, "on_error": on_error,
             "name": getattr(fn, "__name__", "") or "validator"})


def _record_director_hook(ext_id, fn) -> None:
    if not callable(fn):
        raise ExtensionError("on_director_payload needs a callable")
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        record.director_hooks.append(fn)


def _record_narration_hook(ext_id, fn) -> None:
    if not callable(fn):
        raise ExtensionError("on_narration_payload needs a callable")
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        record.narration_hooks.append(fn)


def _record_specialist(ext_id, full_name) -> None:
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        if full_name not in record.specialists:
            record.specialists.append(full_name)


def _record_model_lane(ext_id, name, role, *, label, description) -> None:
    with _lock:
        record = _registered.setdefault(ext_id, _Registration(ext_id))
        # Replace, not append: re-enabling an extension in a live process
        # re-runs its register(), and the same lane declared twice is one
        # lane, not two settings rows.
        record.model_lanes = [lane for lane in record.model_lanes
                              if lane["name"] != name]
        record.model_lanes.append({"ext_id": ext_id, "name": name,
                                   "role": role, "label": label,
                                   "description": description})


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
    package = _module_name(ext.id)
    name = package + ".extension"
    # The extension's directory is registered as a PACKAGE before its entry is
    # executed, so an extension whose Python is more than one file can say
    # `from .campaign import package` and have it mean its own sibling.
    #
    # Found by writing one: `campaign-demo` is the first bundled extension to
    # split its Python, and `from campaign import ...` raised
    # ModuleNotFoundError -- the same shape as the ES-module blocker, which
    # nobody hit either until an extension was built as a module graph.
    #
    # A package rather than putting the directory on `sys.path`, and the
    # difference is the whole reason: a path entry makes every sibling
    # importable under its BARE name, so a file called `db.py` would shadow the
    # engine's `db` for whatever imported next, and two extensions each
    # shipping a `helper.py` would get whichever loaded first. Under a package
    # the names are `sonder_ext_<id>.helper`, which can collide with nothing.
    # Relative imports only, therefore -- the same rule the module UI half
    # already follows.
    if package not in sys.modules:
        container = importlib.util.module_from_spec(
            importlib.machinery.ModuleSpec(package, None, is_package=True))
        container.__path__ = [str(base)]
        sys.modules[package] = container
    spec = importlib.util.spec_from_file_location(name, target)
    if spec is None or spec.loader is None:
        sys.modules.pop(package, None)
        raise ExtensionError(f"extension {ext.id!r} entry could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        _drop_extension_modules(package)
        raise
    return module


def _drop_extension_modules(package: str) -> None:
    """Forget the extension's package and every submodule it imported.

    Submodules too, because a disable that left `sonder_ext_x.helper` behind
    would have the next enable execute a stale copy of a file the host may have
    replaced in between -- which is exactly what an update does.
    """
    for name in [n for n in sys.modules
                 if n == package or n.startswith(package + ".")]:
        sys.modules.pop(name, None)


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
        _drop_extension_modules(_module_name(ext_id))
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
            # Backstop only. `api.add_stage` refuses both of these at
            # registration now, with a reason the host can read
            # (`_UNSPLICEABLE_ANCHOR_PREFIXES`): `character:<id>` is the
            # runtime's reserved dynamic namespace, planned as a parallel
            # group that splicing would silently serialize, and
            # `ext:<id>:<key>` is another extension's stage, which this very
            # pass has not placed yet. A stage recorded before that check
            # existed still must not be planned somewhere arbitrary.
            if core.startswith(("character:", "ext:")):
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


def _live_ids() -> list[str]:
    """Extensions that actually REGISTERED, in id order.

    Not `sorted(_registered)`: a record whose `register(api)` raised is kept
    with an `.error` so the host can read the reason, and it is that keeping
    which made a broken extension look live to anything iterating the
    registry. Hook dispatch escapes by accident -- it iterates the record's
    own hook lists, which a failed record leaves empty -- but the two
    DECLARATIVE seams read stored per-story blocks that outlive the session
    the extension worked in, so they had nothing empty to iterate.
    """
    with _lock:
        return sorted(ext_id for ext_id, record in _registered.items()
                      if not record.error)


def _narration_blocks(chat_id) -> list:
    """Every enabled extension's standing block for this story, in id order.

    Read fresh each beat rather than cached: a block is installed by a host
    action outside the turn -- a panel's Save, a route call, a campaign
    starting -- so a cache would narrate the previous revision for the rest of
    the session, which is the failure mode this whole seam exists to prevent.
    """
    if chat_id is None:
        return []
    try:
        activate()
        ids = _live_ids()
    except Exception:
        log.exception("extension narration blocks could not be resolved")
        return []

    blocks = []
    for ext_id in ids:
        api = _apis.get(ext_id)
        if api is None:
            continue
        try:
            block = api.narration_context(chat_id).get()
        except Exception:
            log.exception("extension %s narration block failed to read", ext_id)
            continue
        text = str((block or {}).get("text") or "").strip()
        if text:
            blocks.append({"source": ext_id, "text": text,
                           "revision": int((block or {}).get("revision") or 0)})
    return blocks


def _director_blocks(chat_id, phase) -> list:
    """Every enabled extension's standing block for this story and phase.

    Read fresh each beat, for the reason `_narration_blocks` gives: a block is
    installed by a host action outside the turn, so a cache would run the whole
    session against the campaign rules of whenever it was first warmed.
    """
    if chat_id is None:
        return []
    try:
        activate()
        ids = _live_ids()
    except Exception:
        log.exception("extension director blocks could not be resolved")
        return []

    blocks = []
    for ext_id in ids:
        api = _apis.get(ext_id)
        if api is None:
            continue
        try:
            record = api.director_context(chat_id).get(phase)
        except Exception:
            log.exception("extension %s director block failed to read", ext_id)
            continue
        text = str((record or {}).get("text") or "").strip()
        if text:
            blocks.append({"source": ext_id, "text": text,
                           "revision": int((record or {}).get("revision") or 0)})
    return blocks


def validate_director_result(ctx, result):
    """Run every registered result validator over the settled Director result.

    Returns `(violations, fatal)`. `violations` are dicts carrying the
    extension id, the validator name, the code, the message and any evidence --
    ordered by extension id then registration order, so two extensions
    disagreeing about the same beat produce the same notes in the same order on
    every run, including a reroll.

    `fatal` is whether any violation came from a validator registered
    `on_error="fail"`. The caller decides what to do with that; this function
    never ends a beat, because "which failures cost a turn" is the pipeline's
    question and not this module's.

    A validator that RAISES is charged the same policy as one that refuses: a
    `warn` validator's exception becomes a turn warning and is otherwise
    ignored, and a `fail` validator's exception is a violation like any other.
    An extension whose rule cannot even be evaluated has not approved the beat.
    """
    violations, fatal = [], False
    try:
        activate()
        with _lock:
            registered = [
                (record.ext_id, dict(item))
                for record in _registered.values()
                for item in record.result_validators
            ]
    except Exception:
        log.exception("extension result validators could not be resolved")
        return [], False
    registered.sort(key=lambda row: row[0])

    for ext_id, item in registered:
        api = _apis.get(ext_id)
        if api is None:
            continue
        from .api import Correction, DirectorContext, DirectorResult

        # `fn(result, info)`, the same two-argument shape every other hook in
        # this module uses. No arity tolerance on purpose: guessing from a
        # TypeError would read one raised INSIDE a validator as a signature
        # mismatch and silently call it again with fewer arguments.
        try:
            outcome = item["fn"](DirectorResult(api, ctx, result),
                                 DirectorContext(api, ctx, phase="result"))
        except Exception as exc:
            outcome = _validator_failure(ctx, ext_id, item, exc)
            if outcome is None:
                continue

        for correction in (outcome if isinstance(outcome, (list, tuple))
                           else [outcome]):
            if not isinstance(correction, Correction):
                continue
            violations.append(correction.as_dict(ext_id, item["name"]))
            if item["on_error"] == "fail":
                fatal = True
    return violations, fatal


def _validator_failure(ctx, ext_id, item, exc):
    """What a raising validator produces, under its own declared policy."""
    from .api import Correction

    log.exception("extension result validator %s/%s failed",
                  ext_id, item["name"])
    _observer_failures[ext_id] = _observer_failures.get(ext_id, 0) + 1
    note = getattr(ctx, "add_warning", None)
    if callable(note):
        try:
            note(f"extension {ext_id}: result validator {item['name']!r} "
                 f"failed ({exc})")
        except Exception:
            pass
    if item["on_error"] != "fail":
        return None
    return Correction(
        "validator-error",
        f"{ext_id}'s campaign rule could not be evaluated: {exc}")


def dispatch_director_payload(ctx, payload, *, phase):
    """Let installed extensions colour what the DIRECTOR is about to be told.

    The same two seams in the same order as `dispatch_narration_payload`
    -- standing blocks into `payload["extension_context"]`, then
    `on_director_payload` hooks which may rewrite anything -- and the same
    total failure posture: any error leaves the payload exactly as the engine
    assembled it.

    Called ONCE per Director call, before the first attempt. The retries this
    stage owns (the world-pressure must-tick floor, the player-act authority
    correction, the Tier 2 omission repair) all rebuild from this payload, so
    a correction is answered against the same campaign context the answer it is
    correcting was given.

    What it does not touch is the deterministic floor underneath. A block or a
    hook can tell the Director anything; it cannot make the Director's output
    skip player-act authority, claim coverage, the movement backstop or the
    restraint floor, because those read the RESULT and run after this.
    """
    if not isinstance(payload, dict):
        return payload

    chat = getattr(ctx, "chat", None)
    chat_id = getattr(chat, "id", None)
    scope = f"director_{phase}"
    current = payload

    blocks = _director_blocks(chat_id, phase)
    if blocks:
        current = dict(current)
        current["extension_context"] = blocks
        for block in blocks:
            _note_narration_routing(ctx, block["source"], scope,
                                    ["extension_context"])

    try:
        with _lock:
            hooks = [(record.ext_id, fn) for record in _registered.values()
                     for fn in record.director_hooks]
        if not hooks:
            return current
    except Exception:
        log.exception("extension director hooks could not be resolved")
        return current

    for ext_id, fn in hooks:
        api = _apis.get(ext_id)
        if api is None:
            continue
        before = current
        # Fingerprint BEFORE the call, for the reason spelled out in
        # `dispatch_character_payload`.
        stamps = _payload_stamps(before)
        try:
            info = DirectorContext(api, ctx, phase=phase)
            result = fn(before, info)
        except Exception:
            log.exception("extension %s director payload hook failed", ext_id)
            continue
        if not isinstance(result, dict):
            continue
        after = _payload_stamps(result)
        changed = sorted({key for key in set(stamps) | set(after)
                          if stamps.get(key) != after.get(key)})
        if changed:
            _note_narration_routing(ctx, ext_id, scope, changed)
        current = result
    return current


def dispatch_narration_payload(ctx, payload, *, scope="narrator", player=""):
    """Let installed extensions colour what the narrator is about to be told.

    Two seams in one pass, in this order:

    1. Standing blocks (`api.narration_context`) are collected into
       `payload["extension_context"]`, a list of `{source, text, revision}`.
       Declarative, so the common case costs no extension code per beat.
    2. `on_narration_payload` hooks run, which may rewrite anything including
       the list just assembled.

    Attribution matches `dispatch_character_payload`: every top-level key an
    extension changed is recorded against its id on the context and rides the
    turn's commit results. Narration is the one place a routed fact reaches the
    PLAYER rather than a fictional mind, so being able to name its author in
    one read matters more here, not less.

    Total: any failure leaves the payload exactly as the engine assembled it.
    """
    if not isinstance(payload, dict):
        return payload

    chat = getattr(ctx, "chat", None)
    chat_id = getattr(chat, "id", None)
    current = payload

    blocks = _narration_blocks(chat_id)
    if blocks:
        current = dict(current)
        current["extension_context"] = blocks
        for block in blocks:
            _note_narration_routing(ctx, block["source"], scope,
                                    ["extension_context"])

    try:
        with _lock:
            hooks = [(record.ext_id, fn) for record in _registered.values()
                     for fn in record.narration_hooks]
        if not hooks:
            return current
    except Exception:
        log.exception("extension narration hooks could not be resolved")
        return current

    for ext_id, fn in hooks:
        api = _apis.get(ext_id)
        if api is None:
            continue
        before = current
        # Fingerprint BEFORE the call, for the reason spelled out in
        # `dispatch_character_payload`: a hook handed the real payload can
        # mutate both sides of a naive comparison at once and come back with an
        # empty diff, which is an unattributed edit to what the reader is told.
        stamps = _payload_stamps(before)
        try:
            info = NarrationContext(api, ctx, scope=scope, player=player)
            result = fn(before, info)
        except Exception:
            _observer_failures[ext_id] = _observer_failures.get(ext_id, 0) + 1
            log.exception("extension %s narration hook failed", ext_id)
            continue
        if result is None:
            result = before
        if not isinstance(result, dict):
            log.warning("extension %s narration hook returned %s; ignored",
                        ext_id, type(result).__name__)
            continue
        after = _payload_stamps(result)
        changed = sorted({key for key in set(stamps) | set(after)
                          if stamps.get(key) != after.get(key)})
        if changed:
            _note_narration_routing(ctx, ext_id, scope, changed)
        current = result
    return current


def _note_narration_routing(ctx, ext_id, scope, changed) -> None:
    """Record a narration edit beside the character-routing notes.

    Same list, same shape, `char_id: None` -- because the question a reader of
    the turn asks is "who touched what this beat", and splitting the answer
    across two places is how half of it stops being read.
    """
    log.info("extension %s rewrote %s payload keys: %s",
             ext_id, scope, ", ".join(changed))
    try:
        entries = ctx.get("_extension_routing")
        if not isinstance(entries, list):
            entries = []
        entries.append({"ext": ext_id, "char_id": None, "scope": str(scope),
                        "changed": list(changed)})
        ctx["_extension_routing"] = entries
    except Exception:
        log.exception("could not record extension narration routing note")


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
    from llm.providers import chat_complete

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


def registered_model_lanes() -> list[dict]:
    """Every enabled extension's declared model lanes, for the host's panel.

    This registry is the ONLY thing standing between a lane and the settings
    UI -- resolution never consults it. `providers.resolve_role_candidates`
    reads `agent_models` by role string, so a lane's calls resolve (and
    inherit `default` when its row is blank) whether or not the extension is
    still enabled; what a disabled extension loses is the settings row, which
    is exactly the phantom-role guarantee: `_deregister` pops the whole
    record, so a gone extension configures nothing and haunts nothing.
    """
    with _lock:
        return sorted(
            (dict(lane)
             for record in _registered.values()
             for lane in record.model_lanes),
            key=lambda row: (row["ext_id"], row["name"]))


def keep_orphan_lane_rows(stored: dict, incoming: dict) -> dict:
    """Carry a vanished extension's lane rows through a full-map settings save.

    The models panel PUTs the WHOLE role->config map, built from the rows it
    rendered -- which is how clearing a row works (omission means unset), and
    which would also silently delete the stored configuration of any lane
    whose extension is currently disabled or removed, because those rows are
    not rendered. That configuration is the HOST's work, not the extension's:
    removal takes the code, never the host's choices (the same rule that
    leaves `world["ext:<id>"]` alone on remove), so re-enabling must find the
    lane configured as it was left.

    The split is exact: an `ext:` key absent from the incoming map is dropped
    only when its lane is LIVE (the panel showed it, so omission was the host
    clearing it) and preserved otherwise. If the lane registry itself cannot
    be read, everything is preserved -- losing host configuration to a broken
    extension tree is strictly worse than keeping an orphan row nobody reads.
    """
    out = dict(incoming or {})
    try:
        activate()
        live = {lane["role"] for lane in registered_model_lanes()}
    except Exception:
        log.exception("could not read model lanes; keeping every ext: row")
        live = None
    for key, value in (stored or {}).items():
        key = str(key)
        if not key.startswith("ext:") or key in out:
            continue
        if live is None or key not in live:
            out[key] = value
    return out


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

    Enabled as well as installed, which is the same rule `extension_script`
    and `extension_styles` apply: switching an extension off has to reach
    everything it serves, or `/asset/extension.py` hands back the source of
    an extension the host believes is inert. Safe mode counts as off.
    """
    ext = installed_extensions().get(str(ext_id or ""))
    if ext is None:
        raise ExtensionError(f"no installed extension {ext_id!r}")
    if not is_enabled(ext.id):
        raise ExtensionError(f"extension {ext.id!r} is not enabled")
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


def _module_bootstrap(ext: "Extension") -> str:
    """A classic one-liner that dynamically imports an extension's ES module.

    Why a bootstrap rather than a `<script type="module">` served directly: the
    host has to be able to hand the module an ID-BOUND facade. The classic
    path attributes registrations with a `Sonder._begin(id)` / `_end()` pair
    around synchronous top-level code, and that trick does not survive a
    module -- imports resolve asynchronously and a `register` may `await`, so
    ambient owner state set before the await belongs to somebody else after it.
    A dynamic `import()` lets the host call `register(facade)` itself, which is
    both correct under concurrency and the same shape as the Python half's
    `register(api)`.

    Relative imports inside the module resolve against its own URL, which is
    why the entry is served from `/asset/` -- the whole extension tree is
    reachable there, already containment-checked by `asset_path`.
    """
    href = f"/api/extensions/{ext.id}/asset/{ext.module_entry}"
    return (f'window.Sonder && Sonder._loadModule('
            f'{json.dumps(ext.id)}, {json.dumps(href)});\n')


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
    if ext is None or not is_enabled(ext.id):
        return ""
    parts = []
    if ext.ui_entry:
        source = _read_asset(ext, ext.ui_entry)
        if source is not None:
            parts.append(_wrap_ui(ext, source))
    if ext.module_entry:
        parts.append(_module_bootstrap(ext))
    return "\n".join(parts)


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
        if ext.id not in enabled:
            continue
        if ext.ui_entry:
            source = _read_asset(ext, ext.ui_entry)
            if source is not None:
                parts.append(_wrap_ui(ext, source))
        # A module entry contributes a loader line, not its source: the module
        # is fetched by the browser from `/asset/` so its own imports resolve,
        # and inlining it here would put `import` in a classic script -- a
        # SyntaxError that takes down every extension after it in the bundle.
        if ext.module_entry:
            parts.append(_module_bootstrap(ext))
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
    "DirectorBlock", "DirectorContext", "DocumentStore",
    "EXT_API_VERSION", "ENABLED_SETTING", "ExtState", "Extension",
    "ExtensionError", "NarrationBlock", "NarrationContext",
    "PSYCHOLOGY_STATE_KEYS", "PayloadContext", "Request",
    "SonderExtensionAPI", "StepView", "activate", "apply_plan_splices",
    "asset_path", "check_update", "check_updates", "disable_extension",
    "disabled_reasons",
    "dispatch_character_payload", "dispatch_director_payload",
    "validate_director_result",
    "dispatch_narration_payload",
    "dispatch_route", "dispatch_turn_committed", "document_path",
    "enable_extension", "enabled_ids", "extension", "extension_root",
    "extension_script", "extension_styles", "in_commit_scope",
    "installed_extensions", "is_enabled", "keep_orphan_lane_rows", "listing",
    "load_errors",
    "notify_step_saved", "observer_failures", "registered_commit_domains",
    "registered_model_lanes",
    "registered_routes", "registered_specialists", "registered_stages",
    "reload", "routing_notes", "run_commit_domains", "run_specialist_call",
    "safe_mode", "ui_bundle", "ui_styles", "update_extension",
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


# ---------------------------------------------------------------- git sources
#
# "Compatible" is decided here and stated plainly rather than guessed at per
# call. Three rules, each with a reason:
#
# * **http(s) only.** `ssh://` and `git@host:path` need a key and, without one,
#   git BLOCKS on a passphrase prompt that nobody is there to answer -- an
#   install that hangs forever rather than failing. `git://` and `ext::` are
#   unauthenticated transports; the second can name a command to run.
# * **No submodules, ever.** A submodule is a second URL chosen by the repo
#   rather than by the host, and it can name any transport. Clone is explicitly
#   `--no-recurse-submodules`; a repo that needs them is not installable here.
# * **No argument injection.** A source beginning with `-` is a git FLAG, not a
#   URL, so it is refused before it can become one.

#: Hosts whose ordinary `https://host/owner/repo` form is a git remote even
#: with no `.git` suffix. Not an allowlist of who may be installed from -- any
#: https URL ending in `.git`, or prefixed `git+`, works too. This exists only
#: so pasting the URL out of a browser address bar does the obvious thing.
GIT_HOST_HINTS = ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org",
                  "git.sr.ht")

#: How long a clone or a remote query may take before it is abandoned.
GIT_TIMEOUT_SECONDS = 120


def _split_git_ref(source: str) -> tuple[str, str | None]:
    """`https://host/o/r#v2` -> (url, 'v2'). A ref may be a branch or a tag."""
    url, _, ref = source.partition("#")
    ref = ref.strip()
    return url.strip(), (ref or None)


#: Transports a repository may be cloned over. `file://` is here because it is
#: how a repository on this machine is named, and it grants nothing the plain
#: folder install does not already grant -- the host is choosing a local path
#: either way. What is NOT here is the point: `ssh://` and `git@host:path` need
#: a key and, lacking one, git blocks on a passphrase prompt inside a web
#: request; `git://` is unauthenticated; `ext::` can name a command to run.
GIT_SCHEMES = ("https://", "http://", "file://")
_REFUSED_SCHEMES = ("ssh://", "git://", "ext::", "gopher://")


def _source_kind(source: str) -> str:
    """``git`` | ``zip`` | ``local`` -- what this source actually is."""
    source = str(source or "").strip()
    if source.startswith("-"):
        raise ExtensionError(f"not a source: {source!r}")
    bare = source[len("git+"):] if source.startswith("git+") else source
    if bare.startswith(_REFUSED_SCHEMES):
        raise ExtensionError(
            "a repository must be reachable over http(s): an ssh remote needs "
            "a key, and git stops for a passphrase nobody is there to type")
    if source.startswith("git+") or bare.startswith("file://"):
        return "git"
    if not bare.startswith(("http://", "https://")):
        # `git@host:path` -- scp-style, which is ssh by another spelling.
        if re.match(r"^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:", source):
            raise ExtensionError(
                "a repository must be reachable over http(s): an ssh remote "
                "needs a key, and git stops for a passphrase nobody is there "
                "to type")
        return "local"
    url, _ref = _split_git_ref(source)
    if url.endswith(".zip"):
        return "zip"
    if url.endswith(".git"):
        return "git"
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    segments = [part for part in url.split("//", 1)[-1].split("/")[1:] if part]
    if host in GIT_HOST_HINTS and len(segments) == 2:
        return "git"
    return "zip"


def _git(*args, cwd=None, timeout=None) -> str:
    """Run one git command with the environment held still.

    `GIT_TERMINAL_PROMPT=0` is the load-bearing one: without it a private or
    mistyped repository makes git wait on a username prompt forever, inside a
    web request, with nobody at the terminal it is prompting.
    """
    import subprocess

    env = dict(os.environ)
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "",
        "SSH_ASKPASS": "",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GCM_INTERACTIVE": "never",
    })
    try:
        done = subprocess.run(
            ("git",) + tuple(args), cwd=str(cwd) if cwd else None, env=env,
            capture_output=True, text=True,
            timeout=GIT_TIMEOUT_SECONDS if timeout is None else timeout)
    except FileNotFoundError as exc:
        raise ExtensionError(
            "git is not installed, so a repository cannot be cloned") from exc
    except subprocess.TimeoutExpired as exc:
        spent = GIT_TIMEOUT_SECONDS if timeout is None else timeout
        raise ExtensionError(f"git gave up after {spent:g}s") from exc
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise ExtensionError(
            f"git failed: {detail[-1] if detail else done.returncode}")
    return done.stdout


def _git_clone(source: str, destination: Path) -> tuple[str, str, str]:
    """Clone into `destination`. Returns (url, ref, commit)."""
    url, ref = _split_git_ref(source)
    if url.startswith("git+"):
        url = url[len("git+"):]
    if not url.startswith(GIT_SCHEMES):
        raise ExtensionError(f"not a cloneable URL: {url!r}")
    args = ["clone", "--depth", "1", "--single-branch",
            "--no-recurse-submodules", "--quiet"]
    if ref:
        args += ["--branch", ref]
    # `--` so a URL can never be read as a flag, whatever it starts with.
    _git(*args, "--", url, str(destination))
    commit = _git("rev-parse", "HEAD", cwd=destination).strip()
    if not ref:
        ref = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=destination).strip()
    return url, ref, commit


def _git_remote_head(url: str, ref: str | None, *, timeout=None) -> str:
    """The commit a remote's branch or tag points at, without cloning it.

    One round trip and no download, which is what makes an update CHECK cheap
    enough to run for every installed extension at once.
    """
    out = _git("ls-remote", "--heads", "--tags", "--", url,
               *([ref] if ref else []), timeout=timeout)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            # An annotated tag resolves to `refs/tags/x^{}`; that dereferenced
            # line is the commit, so prefer it when both are present.
            if parts[1].endswith("^{}"):
                return parts[0]
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            return parts[0]
    raise ExtensionError(
        f"the remote has no {ref!r}" if ref else "the remote reported no refs")


def _audit_tree(root: Path) -> None:
    """Apply the archive ceilings to a directory that arrived some other way.

    A clone is not extracted, so `_safe_extract` never sees it -- and a git
    repository can hold symlinks and gigabytes just as happily as a zip can.
    The rules that govern what may be installed should not depend on how it
    travelled.
    """
    total = 0
    count = 0
    base = root.resolve()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ExtensionError(
                f"repository contains a symlink: {path.relative_to(root)}")
        if not path.is_file():
            continue
        count += 1
        if count > MAX_ARCHIVE_MEMBERS:
            raise ExtensionError(
                f"repository holds more than {MAX_ARCHIVE_MEMBERS} files")
        # Containment is re-checked on the resolved path even though nothing
        # here chose it: `rglob` follows nothing, but a future caller might.
        if base not in path.resolve().parents:
            raise ExtensionError(f"path escapes the extension directory: {path}")
        total += path.stat().st_size
        if total > MAX_EXTRACTED_BYTES:
            raise ExtensionError(
                f"repository is larger than "
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
    origin_url = origin_ref = commit = None
    kind = _source_kind(source)

    with tempfile.TemporaryDirectory(dir=root) as tmp:
        staged = Path(tmp) / "staged"
        if kind == "git":
            # Cloned into its own directory because `git clone` insists on an
            # empty target, then the working tree is taken and `.git` is left
            # behind: an update RE-CLONES rather than pulling, so there is no
            # repository state to drift, no local modification to conflict
            # with, and nothing of git's on the host's disk afterwards.
            checkout = Path(tmp) / "checkout"
            origin_url, origin_ref, commit = _git_clone(source, checkout)
            _audit_tree(checkout)
            shutil.copytree(checkout, staged, symlinks=False,
                            ignore=shutil.ignore_patterns(
                                ".git", "__pycache__", "*.pyc"))
        else:
            staged.mkdir()
        if kind == "zip":
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
        elif kind == "git":
            provenance = provenance or f"git:{origin_url}@{origin_ref}"
        else:
            origin = Path(source).expanduser()
            if not origin.is_dir():
                raise ExtensionError(f"not a directory: {source}")
            # Audited BEFORE the copy, and for the same reason the git branch
            # audits the checkout: `copytree(symlinks=False)` DEREFERENCES a
            # link rather than refusing it, so a link audited afterwards is
            # already a copy of whatever it pointed at. A folder is a source
            # like any other -- the rules must not depend on how it travelled.
            _audit_tree(origin)
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
        # What an update CHECK needs later, written now. Without the url and
        # ref there is nothing to ask, and without the commit there is nothing
        # to compare the answer against -- an extension installed before these
        # existed is simply reported as uncheckable rather than guessed at.
        if origin_url:
            manifest["source_url"] = origin_url
            manifest["source_ref"] = origin_ref
            manifest["commit"] = commit
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        os.replace(bundle, destination)

    reload()
    for row in listing():
        if row["id"] == candidate.id:
            return row
    raise ExtensionError(f"{candidate.id!r} did not load after install")


def check_update(extension_id: str, *, timeout=None) -> dict:
    """Is there a newer commit for one installed extension?

    Never raises. A network failure, a repository that has moved, a git that
    is not installed -- all of them are reported as `checkable: False` with the
    reason, because this runs for every installed extension at once and one
    unreachable remote must not fail the sweep for the others.

    Only git installs can be answered. A zip URL would have to be downloaded in
    full to be compared, and a local directory has no upstream at all; both are
    reported uncheckable rather than silently reported up to date, which is the
    same claim with the truth taken out.
    """
    ext = installed_extensions().get(str(extension_id or ""))
    if ext is None:
        return {"id": extension_id, "checkable": False, "update": False,
                "reason": "not installed"}
    row = {"id": ext.id, "name": ext.name, "version": ext.version,
           "current": ext.commit, "latest": "", "update": False,
           "checkable": bool(ext.source_url and ext.commit),
           "source_url": ext.source_url, "source_ref": ext.source_ref,
           "reason": ""}
    if not ext.source_url:
        row["reason"] = ("installed from a folder or a zip, so there is no "
                         "repository to ask")
        return row
    if not ext.commit:
        row["reason"] = "installed before update checking existed"
        return row
    try:
        row["latest"] = _git_remote_head(ext.source_url,
                                         ext.source_ref or None,
                                         timeout=timeout)
    except ExtensionError as exc:
        row["checkable"] = False
        row["reason"] = str(exc)
        return row
    except Exception as exc:                      # pragma: no cover - defensive
        row["checkable"] = False
        row["reason"] = f"{type(exc).__name__}: {exc}"
        return row
    row["update"] = row["latest"] != ext.commit
    return row


#: Wall-clock ceiling for one whole update sweep, in seconds.
#:
#: `check_update` is cheap in BANDWIDTH -- one `ls-remote` each, no download --
#: which is what makes checking everything at once reasonable, and says
#: nothing about latency, which is what actually bounds a request. Serially,
#: ten installed extensions against an unreachable network is ten times
#: `GIT_TIMEOUT_SECONDS`: a twenty-minute HTTP request holding a threadpool
#: worker for a question whose answer is "maybe later".
UPDATE_SWEEP_SECONDS = 60.0


def check_updates() -> list[dict]:
    """`check_update` for everything installed, in id order.

    Bounded by `UPDATE_SWEEP_SECONDS` overall: each remote gets what is left
    of the budget, and once it is spent the remaining extensions are reported
    UNCHECKABLE with the reason rather than skipped or reported up to date --
    "up to date" with the truth taken out is the one answer this must never
    give, which `check_update` already says about its own failures.
    """
    deadline = time.monotonic() + UPDATE_SWEEP_SECONDS
    rows = []
    for ext_id in sorted(installed_extensions()):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            ext = installed_extensions().get(ext_id)
            rows.append({
                "id": ext_id, "name": getattr(ext, "name", ext_id),
                "version": getattr(ext, "version", ""),
                "current": getattr(ext, "commit", ""), "latest": "",
                "update": False, "checkable": False,
                "source_url": getattr(ext, "source_url", ""),
                "source_ref": getattr(ext, "source_ref", ""),
                "reason": (f"the update check ran out of its "
                           f"{UPDATE_SWEEP_SECONDS:g}s budget before "
                           f"reaching this one"),
            })
            continue
        rows.append(check_update(ext_id, timeout=min(remaining,
                                                     GIT_TIMEOUT_SECONDS)))
    return rows


def update_extension(extension_id: str) -> dict:
    """Re-install one git-sourced extension at its ref's current commit.

    Re-clones rather than pulling. There is no `.git` in an installed
    extension, deliberately: a pull would mean carrying repository state that
    can drift, conflict with a host's local edit, or fail halfway and leave a
    working tree nobody chose. A fresh clone validated in staging and moved
    with `os.replace` is the same atomicity install already has, and the same
    failure mode -- the old version, or the new one, never a mixture.

    The enabled set and everything under `world["ext:<id>"]` survive: an update
    is the same extension, so a story played with it keeps going.
    """
    import shutil

    ext = installed_extensions().get(str(extension_id or ""))
    if ext is None:
        raise ExtensionError(f"{extension_id!r} is not installed")
    if not ext.source_url:
        raise ExtensionError(
            f"{ext.id!r} was not installed from a repository, so there is "
            "nothing to update from")

    was_enabled = is_enabled(ext.id)
    root = extension_root()
    source = ext.source_url + (f"#{ext.source_ref}" if ext.source_ref else "")

    with tempfile.TemporaryDirectory(dir=root) as tmp:
        checkout = Path(tmp) / "checkout"
        url, ref, commit = _git_clone(source, checkout)
        if commit == ext.commit:
            return {"id": ext.id, "updated": False, "commit": commit,
                    "reason": "already at the newest commit"}
        _audit_tree(checkout)
        work = Path(tmp) / "work"
        shutil.copytree(checkout, work, symlinks=False,
                        ignore=shutil.ignore_patterns(
                            ".git", "__pycache__", "*.pyc"))
        # The same one-level unwrap install does: a repository usually holds
        # the extension in a directory of its own rather than at its root.
        bundle = _staged_bundle_root(work)
        staged = Path(tmp) / ext.id
        if bundle != staged:
            os.replace(bundle, staged)
        # The id is read from the manifest FIRST, because `_load_manifest`
        # requires the directory name to match it and would otherwise report a
        # rename as a directory-name mismatch -- true, and not the reason.
        try:
            declared = json.loads(
                (staged / "manifest.json").read_text(encoding="utf-8"))
            claimed = str(declared.get("id") or "")
        except Exception:
            claimed = ext.id                  # let _load_manifest say why
        if claimed and claimed != ext.id:
            raise ExtensionError(
                f"the repository now declares id {claimed!r}, not "
                f"{ext.id!r}; install it separately rather than updating")
        # Validated BEFORE the installed copy is touched: an update that would
        # not load must leave the working one exactly where it is.
        candidate = _load_manifest(staged)
        manifest_path = staged / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({"provenance": f"git:{url}@{ref}", "source_url": url,
                         "source_ref": ref, "commit": commit})
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

        previous = Path(tmp) / f"{ext.id}.previous"
        os.replace(ext.path, previous)
        try:
            os.replace(staged, ext.path)
        except Exception:
            os.replace(previous, ext.path)        # put the old one back
            raise

    reload()
    if was_enabled:
        # `reload` cleared the live registrations; the enabled SET is durable,
        # so this only re-imports what the host had already switched on.
        try:
            activate(refresh=True)
        except Exception:
            log.exception("extension %s did not re-activate after update",
                          ext.id)
    for row in listing():
        if row["id"] == ext.id:
            row["updated"] = True
            row["previous_version"] = ext.version
            return row
    raise ExtensionError(f"{ext.id!r} did not load after the update")


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
