"""`make` runs the interpreter players run, and says when it cannot.

`make check` ran `python` -- on the owner's machine Pydantic 1, NumPy 1 and
pytest 9.1.1 with no xdist -- and `make run` served the engine through
`/usr/bin/uvicorn`, FastAPI 0.101 under the declared floor; `.venv`, which
both launchers build, carried the pinned stack (tooling_gate F1, 2026-11-01).
Each test here drives the real Makefile in a scratch directory against a
stand-in interpreter that records what it was asked, so nothing is compiled,
served or tested for real.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("make") is None,
                                reason="no make on this machine")

#: A stand-in interpreter: records its argv, then answers like Python would
#: for the few things the Makefile asks of it. `--source-roots` FAILS, which
#: is the failure `make compile` must not turn into success.
FAKE_PYTHON = """#!/bin/sh
printf '%s\\n' "$*" >> "{log}"
case "$*" in
  *--source-roots*) exit 1 ;;
  "-c import xdist") exit {xdist} ;;
  -c*) exit 1 ;;
esac
exit 0
"""


def _scratch(tmp_path, *, venv=True, xdist=0):
    shutil.copy(ROOT / "Makefile", tmp_path / "Makefile")
    log = tmp_path / "argv.log"
    log.write_text("", encoding="utf-8")
    python = tmp_path / "fakepython"
    if venv:
        python = tmp_path / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
    python.write_text(FAKE_PYTHON.format(log=log, xdist=xdist),
                      encoding="utf-8")
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    return python, log


def _make(tmp_path, *args, env=None):
    environ = {key: value for key, value in os.environ.items()
               if key not in ("PYTHON", "PYTEST", "MAKEFLAGS", "MFLAGS")}
    environ.update(env or {})
    return subprocess.run(["make", "--no-print-directory", *args],
                          cwd=tmp_path, env=environ, capture_output=True,
                          text=True, timeout=60)


def test_every_target_runs_the_venv_interpreter_when_there_is_one(tmp_path):
    _scratch(tmp_path)
    out = _make(tmp_path, "-n", "run", "serve", "structure", "map")
    assert out.returncode == 0, out.stderr
    commands = [line for line in out.stdout.splitlines() if line.strip()]
    assert all(line.startswith(".venv/bin/python ") for line in commands), (
        commands)
    assert sum("-m uvicorn web.app:app" in line for line in commands) == 2


def test_without_a_venv_it_falls_back_to_python(tmp_path):
    _scratch(tmp_path, venv=False)
    out = _make(tmp_path, "-n", "serve")
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("python -m uvicorn web.app:app"), out.stdout


def test_both_gates_state_their_stack_first(tmp_path):
    _scratch(tmp_path)
    for gate in ("check", "check-fast"):
        out = _make(tmp_path, "-n", gate)
        assert out.returncode == 0, out.stderr
        first = out.stdout.splitlines()[0]
        assert first == ".venv/bin/python tools/project_check.py --stack", (
            gate, first)


def test_check_skips_the_map_comparison_it_has_just_regenerated(tmp_path):
    _scratch(tmp_path)
    check = _make(tmp_path, "-n", "check").stdout
    fast = _make(tmp_path, "-n", "check-fast").stdout
    assert "tools/project_check.py --skip-generated-map" in check
    assert "--skip-generated-map" not in fast


def test_compile_fails_when_the_inventory_cannot_be_read(tmp_path):
    """`compileall` with no directory compiles `sys.path` and exits 0, so an
    inventory command that failed used to read as a green compile."""
    python, log = _scratch(tmp_path)
    out = _make(tmp_path, "compile", env={"PYTHON": str(python)})
    assert out.returncode != 0, out.stdout + out.stderr
    assert "compileall" not in log.read_text(encoding="utf-8")


def test_the_browser_suite_degrades_without_xdist(tmp_path):
    """`pyproject.toml`'s addopts carry `-n auto`; an environment without
    xdist used to fail on `unrecognized arguments: -n`."""
    python, log = _scratch(tmp_path, xdist=1)
    out = _make(tmp_path, "test-browser", env={"PYTHON": str(python)})
    assert out.returncode == 0, out.stdout + out.stderr
    ran = [line for line in log.read_text(encoding="utf-8").splitlines()
           if line.startswith("-m pytest")]
    assert ran and "browser_tests" in ran[-1]
    assert "-o addopts=" in ran[-1] and " -n " not in ran[-1] + " ", ran


def test_the_serial_addopts_are_pyprojects_less_parallelism():
    """`-o addopts=...` is a second spelling of pyproject's addopts; a flag
    added there and not here is dropped on every serial fallback."""
    with open(ROOT / "pyproject.toml", "rb") as handle:
        addopts = tomllib.load(handle)["tool"]["pytest"]["ini_options"][
            "addopts"]
    expected = addopts.replace("-n auto", "").split()
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    line = next(line for line in text.splitlines()
                if line.startswith("SERIAL_ADDOPTS"))
    assert line.split("=", 1)[1].split() == expected


def test_the_dev_extra_is_requirements_dev():
    """Two spellings of one dependency set: `pip install -e .[dev]` and then
    `pytest` failed on `-n` because the extra named pytest alone."""
    with open(ROOT / "pyproject.toml", "rb") as handle:
        extra = tomllib.load(handle)["project"]["optional-dependencies"]["dev"]
    lines = [line.split("#", 1)[0].strip() for line in
             (ROOT / "requirements-dev.txt").read_text(
                 encoding="utf-8").splitlines()]
    required = [line for line in lines if line and not line.startswith("-")]
    assert sorted(extra) == sorted(required)
