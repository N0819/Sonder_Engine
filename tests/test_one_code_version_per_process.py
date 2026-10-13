"""One server process runs one version of the engine (`core/code_version.py`).

Home 10 (chat 173, 2026-10-12): the play server held only part of its code in
memory -- 58 of 248 engine modules loaded from disk the first time a story
needed them -- so with the working tree changing under it, the new room
designer (`anchor_cells(..., raw=True)`) met the placement code loaded at
startup and every room design failed. The owner: "isn't the old code in
ram?". Now every engine module loads with the app, and the host is warned --
never refused -- when the disk no longer matches what the process holds.
"""
from __future__ import annotations

import ast
import asyncio
import os
import sys
import time

from core.paths import INSTALL_ROOT


def _roots_named_by_the_checks():
    tree = ast.parse(open(os.path.join(INSTALL_ROOT, "tools", "project_check.py"), encoding="utf-8").read())
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and getattr(node.targets[0], "id", "") in ("SUBSYSTEM_PACKAGES", "NON_PACKAGE_ENGINE_DIRS"):
            found[node.targets[0].id] = tuple(ast.literal_eval(node.value))
    return found["SUBSYSTEM_PACKAGES"] + found["NON_PACKAGE_ENGINE_DIRS"]


def test_every_engine_module_is_in_memory_once_the_app_is():
    import web.app  # noqa: F401
    missing = []
    for top in _roots_named_by_the_checks():
        base = os.path.join(INSTALL_ROOT, top)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d.isidentifier()
                           and os.path.isfile(os.path.join(dirpath, d, "__init__.py"))]
            for name in filenames:
                if not (name.endswith(".py") and name[:-3].isidentifier()):
                    continue
                parts = os.path.relpath(os.path.join(dirpath, name), INSTALL_ROOT)[:-3].split(os.sep)
                module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
                if module not in sys.modules:
                    missing.append(module)
    assert not missing, f"{len(missing)} engine modules would load from disk later: {missing[:8]}"


def test_the_engine_it_loads_is_the_engine_the_checks_check():
    from core import code_version
    assert code_version.ENGINE_ROOTS == _roots_named_by_the_checks()


def _fresh(tmp_path, monkeypatch):
    """A snapshot of two scratch files, the module's own state restored after."""
    from core import code_version
    monkeypatch.setattr(code_version, "_snapshot", {})
    monkeypatch.setattr(code_version, "_status", {"stale": False, "changed": [], "count": 0,
                                                  "started": code_version.STARTED, "files": 0})
    a, b = tmp_path / "a.py", tmp_path / "b.json"
    a.write_text("A = 1\n")
    b.write_text("{}\n")
    code_version.take_snapshot([str(a), str(b)])
    return code_version, a, b


def test_a_change_on_disk_is_named_and_a_touch_is_not(tmp_path, monkeypatch):
    cv, a, b = _fresh(tmp_path, monkeypatch)
    assert cv.check()["stale"] is False
    later = time.time() + 5
    os.utime(b, (later, later))                       # touched, same content
    a.write_text("A = 2\n")                           # changed
    now = cv.check()
    assert now["stale"] is True and now["count"] == 1
    assert now["changed"] == [os.path.relpath(str(a), INSTALL_ROOT)]
    a.write_text("A = 1\n")                           # the change undone
    assert cv.check()["stale"] is False


def test_a_file_that_cannot_be_read_counts_as_changed_and_nothing_raises(tmp_path, monkeypatch):
    cv, a, b = _fresh(tmp_path, monkeypatch)
    b.unlink()
    assert cv.check()["changed"] == [os.path.relpath(str(b), INSTALL_ROOT)]
    a.write_text("A = 3\n")

    def refuse(path):
        raise PermissionError(path)
    monkeypatch.setattr(cv, "_digest", refuse)
    now = cv.check()
    assert now["stale"] is True and now["count"] == 2

    def explode(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(cv.os, "stat", explode)
    broken = cv.check()                               # the last status, with why
    assert broken["error"] and broken["stale"] is True
    assert cv.stream_notice() is None or cv.stream_notice()["kind"] == "code_changed"


def test_a_module_that_cannot_load_is_reported_never_raised(tmp_path, monkeypatch):
    from core import code_version
    package = tmp_path / "pkg_codeversion_probe"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "fine.py").write_text("OK = True\n")
    (package / "broken.py").write_text("raise ImportError('a missing dependency')\n")
    (package / "notes").mkdir()                       # not a package: never walked
    (package / "notes" / "scratch.py").write_text("raise SystemExit('executed')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        failed = code_version.load_everything(str(tmp_path), ("pkg_codeversion_probe",))
        assert [f["module"] for f in failed] == ["pkg_codeversion_probe.broken"]
        assert "a missing dependency" in failed[0]["error"]
        assert "pkg_codeversion_probe.fine" in sys.modules
    finally:
        for name in [m for m in sys.modules if m.startswith("pkg_codeversion_probe")]:
            del sys.modules[name]
        code_version.load_everything()                # the real list back


def test_the_language_files_held_are_the_ones_the_loader_reads():
    from language_runtime import pack_source_files
    files = {os.path.relpath(str(p), INSTALL_ROOT) for p in pack_source_files()}
    for lang in ("en", "ja"):
        assert f"language_packs/{lang}/manifest.json" in files
        assert f"language_packs/{lang}/ui.json" in files
        assert any(f.startswith(f"language_packs/{lang}/cards/") and f.endswith(".txt") for f in files)
    assert not any("translation_" in f for f in files), "a tool's file is never held"


def _status(stale, count=0):
    return {"stale": stale, "changed": ["world/spatial_fov.py"][:count], "count": count,
            "started": 0.0, "files": 843}


def test_the_boot_and_a_turn_say_when_the_code_changed(monkeypatch):
    import web.app as app_module
    from core import code_version
    monkeypatch.setattr(code_version, "check", lambda: _status(False))
    assert app_module._bootstrap_code()["stale"] is False

    def body(response):
        async def read():
            return [chunk async for chunk in response.body_iterator]
        return "".join(asyncio.run(read()))

    quiet = body(app_module._stream(iter([{"type": "done"}])))
    assert quiet.splitlines()[0] == '{"type": "done"}', "nothing said while the code is current"

    monkeypatch.setattr(code_version, "check", lambda: _status(True, 1))
    assert app_module._bootstrap_code()["stale"] is True
    said = body(app_module._stream(iter([{"type": "done"}]))).splitlines()
    assert '"kind": "code_changed"' in said[0] and said[1] == '{"type": "done"}'

    # a check that raises costs the boot nothing
    def explode():
        raise RuntimeError("boom")
    monkeypatch.setattr(code_version, "check", explode)
    assert app_module._bootstrap_code()["stale"] is False
