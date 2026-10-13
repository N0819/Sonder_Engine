"""One server process runs one version of the engine (2026-10-13).

A running server held only PART of its code in memory. After `import web.app`
190 of the 248 engine modules were loaded; the other 58 were imported the
first time a story needed them, from whatever was on disk at that moment. So a
server started before a change, and left running while the working tree
changed under it, ran a MIX of two versions. Home 10 (chat 173) met the new
room designer -- which asks `anchor_cells(..., raw=True)` -- against the
placement code loaded at startup, which had no `raw`, and every room design
of that story failed with a TypeError (docs/experiments/
OBSERVE_2026_10_13_home10.md, item 4). The owner: "isn't the old code in
ram?" -- this makes it so.

* `load_everything` imports every engine module when the app is imported, so
  nothing the process runs is read from disk later.
* `take_snapshot` records what the process holds -- the engine's Python, and
  the language packs it reads once and keeps (`language_runtime.
  pack_source_files`) -- by content; `check` says which of those files the
  disk no longer matches, so the host is WARNED that a restart would run
  different code. It never refuses anything (the owner, 2026-10-13: warn,
  never refuse).

NOTHING HERE RAISES: a module that fails to import is reported and the server
starts without it, as it would have done on first use; a file that cannot be
read during a check counts as changed, with its reason; an error in a check
returns the last good status with the error beside it. Every caller sits on a
path where an exception would cost a host their page or block a story's turns.
"""
from __future__ import annotations

import hashlib
import importlib
import os
import sys
import threading
import time

from core.paths import INSTALL_ROOT

#: The directories holding the engine's importable Python -- the eight
#: subsystem packages and the four loose directories, as
#: `tools/project_check.py` names them in ENGINE_PACKAGE_ROOTS (a test holds
#: the two equal, so a new package cannot be checked and not loaded).
ENGINE_ROOTS = ("core", "llm", "world", "mind", "story", "dressing", "persist",
                "web", "agents", "extension_runtime", "language_runtime",
                "language_adapters")

#: When this process began loading the engine.
STARTED = time.time()

_lock = threading.Lock()
_snapshot: dict = {}          # path -> (size, mtime_ns, digest)
_status: dict = {"stale": False, "changed": [], "count": 0, "started": STARTED,
                 "files": 0}
_failures: list = []


def engine_source_files(root: str = INSTALL_ROOT, roots=ENGINE_ROOTS) -> list:
    """Every engine module's file: `<identifier>.py` under each root, walking
    only directories that are packages (an identifier name and an
    `__init__.py`), so a data or scratch directory is never executed."""
    out = []
    for top in roots:
        base = os.path.join(root, top)
        if not os.path.isfile(os.path.join(base, "__init__.py")):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(
                d for d in dirnames
                if d.isidentifier() and os.path.isfile(os.path.join(dirpath, d, "__init__.py")))
            for name in sorted(filenames):
                if name.endswith(".py") and name[:-3].isidentifier():
                    out.append(os.path.join(dirpath, name))
    return out


def module_name(path: str, root: str = INSTALL_ROOT) -> str:
    """The dotted name `path` imports as from `root`."""
    parts = os.path.relpath(path, root)[:-3].split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def load_everything(root: str = INSTALL_ROOT, roots=ENGINE_ROOTS) -> list:
    """Import every engine module not yet imported. Returns the ones that
    failed, `[{module, error}]`, and never raises: a module that cannot be
    imported would have failed on its first use too, and the server must
    start either way."""
    failed = []
    for path in engine_source_files(root, roots):
        name = module_name(path, root)
        if name in sys.modules:
            continue
        try:
            importlib.import_module(name)
        except Exception as exc:          # reported, never raised
            failed.append({"module": name, "error": f"{type(exc).__name__}: {exc}"})
    with _lock:
        _failures[:] = failed
    return failed


def import_failures() -> list:
    """The modules `load_everything` could not import, as it reported them."""
    with _lock:
        return [dict(f) for f in _failures]


def _digest(path: str) -> str:
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def held_files(root: str = INSTALL_ROOT) -> list:
    """What this process holds and will not read again: the engine's Python,
    and the language packs' files as their loader reads them."""
    files = list(engine_source_files(root))
    try:
        from language_runtime import pack_source_files
        files += [str(p) for p in pack_source_files()]
    except Exception:
        pass                              # the packs are the loader's to report
    return sorted(set(files))


def take_snapshot(files=None) -> dict:
    """Record what the process holds, by content. Never raises."""
    try:
        files = held_files() if files is None else list(files)
        snap = {}
        for path in files:
            try:
                st = os.stat(path)
                snap[path] = (st.st_size, st.st_mtime_ns, _digest(path))
            except OSError:
                continue                  # a file that cannot be read is not held
        with _lock:
            _snapshot.clear()
            _snapshot.update(snap)
            _status.update({"stale": False, "changed": [], "count": 0,
                            "files": len(snap), "error": None})
        return status()
    except Exception as exc:
        with _lock:
            _status["error"] = f"{type(exc).__name__}: {exc}"
        return status()


def check() -> dict:
    """Which held files the disk no longer matches: `{stale, changed, count,
    started, files}`, `changed` the first twenty paths relative to the
    install. A file whose size and time moved but whose content did not is
    unchanged (a touch, or a change undone). Never raises: an unreadable or
    vanished file counts as changed, and an error keeps the last status."""
    try:
        with _lock:
            items = list(_snapshot.items())
        changed = []
        for path, (size, mtime_ns, digest) in items:
            try:
                st = os.stat(path)
                if (st.st_size, st.st_mtime_ns) == (size, mtime_ns):
                    continue
                if _digest(path) == digest:
                    with _lock:
                        _snapshot[path] = (st.st_size, st.st_mtime_ns, digest)
                    continue
            except OSError:
                pass                      # gone or unreadable: not what is held
            changed.append(os.path.relpath(path, INSTALL_ROOT))
        with _lock:
            _status.update({"stale": bool(changed), "changed": changed[:20],
                            "count": len(changed), "error": None})
        return status()
    except Exception as exc:
        with _lock:
            _status["error"] = f"{type(exc).__name__}: {exc}"
        return status()


def status() -> dict:
    """The last check's answer, as a copy."""
    with _lock:
        out = dict(_status)
        out["changed"] = list(_status.get("changed") or ())
        return out


def stream_notice():
    """The event a turn's stream opens with when the code changed under this
    server, else None. Never raises."""
    try:
        now = check()
        if not now.get("stale"):
            return None
        return {"type": "notice", "kind": "code_changed", "count": now["count"],
                "changed": now["changed"], "started": now["started"]}
    except Exception:
        return None
