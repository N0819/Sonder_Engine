"""Canaries for the repository-shape inventory and the guards built on it.

The class these pin is not a bug in any one file: it is a SECOND list. "Where
this project's Python lives" was written down four times -- `SUBSYSTEM_PACKAGES`
and `NON_PACKAGE_ENGINE_DIRS` in `tools/project_check.py`, a third ad-hoc list
inside `check_undefined_names` that re-appended three directories the first two
already covered, and the argument list of `make compile`. Three of the four
were updated when `extension_runtime/` appeared and one was not, so the entire
public extension API -- the thing an integrator's production code is told to
depend on -- was the least-checked source in the tree.

The same shape produced every other finding these tests cover: a supported
Python range written in four places and true in three, a launcher name written
in the docs and renamed in the tree, a stamp file that answered one of the
three questions the other launcher asks.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402


def _errors(check) -> list[str]:
    out: list[str] = []
    check(out)
    return out


# --- the inventory itself --------------------------------------------------

def test_every_directory_holding_our_python_is_in_the_inventory():
    """A new top-level directory of source must be added to ENGINE_SOURCE_ROOTS.

    The canary. `extensions/` is excluded because it holds INSTALLED
    third-party trees rather than this project's source, and the hidden and
    generated directories are excluded because they are not source at all.
    """
    ignored = pc._UNWALKED | {"extensions"}
    holds_python = {
        child.name for child in ROOT.iterdir()
        if child.is_dir() and child.name not in ignored
        and not child.name.startswith(".")
        and any(p for p in child.rglob("*.py")
                if "__pycache__" not in p.parts)
    }
    missing = holds_python - set(pc.ENGINE_SOURCE_ROOTS)
    assert not missing, (
        "these directories hold Python this project wrote and are in no "
        "structural check: %s. Add them to ENGINE_SOURCE_ROOTS."
        % ", ".join(sorted(missing)))


def test_the_inventory_names_only_directories_that_exist():
    for root in pc.ENGINE_SOURCE_ROOTS:
        assert (ROOT / root).is_dir(), (
            "ENGINE_SOURCE_ROOTS names %r, which is not a directory" % root)


def test_engine_paths_are_walked_recursively():
    """`glob` vs `rglob` currently costs nothing, which is why it was invisible.

    Measured 2026-08-19: no engine package has a subdirectory of `.py` files,
    so the one-level walk missed zero files -- and would have missed the whole
    of the first `core/sub/` anybody added. Asserted on a real nested file
    rather than on the call: `agents/` already has one.
    """
    walked = {p.relative_to(ROOT).as_posix() for p in pc.engine_python_paths()}
    nested = [p.relative_to(ROOT).as_posix()
              for root in pc.ENGINE_PACKAGE_ROOTS
              for p in (ROOT / root).rglob("*.py")
              if "__pycache__" not in p.parts and len(p.relative_to(ROOT).parts) > 2]
    for path in nested:
        assert path in walked, "%s is below a package and is walked by nothing" % path


def test_make_compile_reads_the_inventory_rather_than_repeating_it():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    compile_rule = text.split("\ncompile:", 1)[1].split("\n\n", 1)[0]
    assert "--source-roots" in compile_rule, (
        "make compile has gone back to a hand-written directory list; it must "
        "read ENGINE_SOURCE_ROOTS via `project_check.py --source-roots`")


def test_the_source_roots_flag_prints_the_inventory():
    out = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "project_check.py"),
         "--source-roots"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == list(pc.ENGINE_SOURCE_ROOTS)


# --- the guards built on it ------------------------------------------------

def test_the_supported_python_range_agrees_everywhere():
    """pyproject, both launchers and the CI matrix name one range.

    The matrix was `["3.11", "3.12"]` while `requires-python` allowed 3.13 and
    BOTH launchers try 3.13 first -- so the interpreter a fresh player is most
    likely to get was the one no gate had ever run.
    """
    assert _errors(pc.check_python_version_agreement) == []


def test_the_ci_matrix_covers_the_whole_declared_range():
    series = pc.declared_python_series()
    assert series, "pyproject.toml declares no readable requires-python bound"
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for version in series:
        assert '"%s"' % version in ci, (
            "Python %s is inside requires-python and absent from ci.yml"
            % version)


def test_no_runnable_file_names_one_machine():
    """Eleven demo sites hard-coded a path naming a project that was renamed."""
    assert _errors(pc.check_no_machine_paths_in_scripts) == []


def test_live_documentation_names_files_that_exist():
    assert _errors(pc.check_docs_name_real_paths) == []


def test_documented_imports_resolve():
    assert _errors(pc.check_docs_imports_resolve) == []


def test_turn_scoped_contextvars_are_cleared_or_declared_safe():
    assert _errors(pc.check_turn_scoped_contextvars_are_cleared) == []


def test_no_test_patches_a_facade_name_a_sibling_shadows():
    assert _errors(pc.check_facade_patch_targets) == []


def test_no_new_package_import_cycle():
    assert _errors(pc.check_package_edge_budget) == []


def test_the_package_cycle_baseline_is_current():
    """The baseline is generated; a hand-edited one records a belief."""
    import json
    stored = json.loads(pc.PACKAGE_EDGES.read_text(encoding="utf-8"))
    assert stored["cycles"] == pc.package_edge_report()["cycles"], (
        "tools/package_edges.json is stale; regenerate it with "
        "`python tools/project_check.py --write-package-edges`")


# --- the launchers ---------------------------------------------------------

LAUNCHERS = {"bat": ROOT / "Start_Sonder.bat", "sh": ROOT / "Start_Sonder.sh"}


@pytest.mark.parametrize("name", sorted(LAUNCHERS))
def test_both_launchers_ask_all_three_dependency_questions(name):
    """A stamp that only has to EXIST cannot notice a dependency change.

    The `.bat` gated its whole install on `if not exist "%STAMP%"`, so a
    Windows player who took an in-app update across a dependency change ran the
    new code against the old environment permanently: `core/updates.py` never
    touches the stamp and `install_updates()` only says "Restart the server".
    """
    text = LAUNCHERS[name].read_text(encoding="utf-8", errors="replace")
    assert "hashlib" in text, (
        "%s does not compute a dependency digest, so it cannot tell that "
        "requirements.txt or constraints.txt changed" % LAUNCHERS[name].name)
    assert "find_spec" in text, (
        "%s does not probe importability, so a stamp that outlived its "
        "environment is invisible to it" % LAUNCHERS[name].name)
    assert "sys.version_info" in text, (
        "%s does not check which Python built an existing .venv"
        % LAUNCHERS[name].name)


@pytest.mark.parametrize("name", sorted(LAUNCHERS))
def test_the_launcher_filenames_are_the_ones_the_docs_tell_you_to_type(name):
    """`Start Sonder.bat` -> `Start_Sonder.bat` left every doc behind."""
    launcher = LAUNCHERS[name]
    assert launcher.is_file()
    for doc in (ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / "AGENTS.md"):
        text = doc.read_text(encoding="utf-8")
        assert "Start Sonder." not in text, (
            "%s names the pre-rename launcher; the file is %s"
            % (doc.name, launcher.name))
