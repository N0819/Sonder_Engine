"""The launchers must pick a SUPPORTED Python, not the newest one.

Reported from a Windows install: `Start_Sonder.bat` selected `py -3`, which
takes whatever is newest — there, Python 3.14.5. The pinned dependency set has
no `pydantic-core` wheel for it, so pip fell back to building from source, and
that source pins a PyO3 which refuses 3.14. The failure surfaced as a Rust
compiler error naming neither Python nor Sonder, three layers below anything
the reporter had chosen.

Both launchers had the same defect from opposite directions: the `.bat` asked
for "newest" and the `.sh` listed `python3.14` first. Neither is a typo — it is
the same wrong idea about what "a recent Python" means for a project with
pinned native dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BAT = ROOT / "Start_Sonder.bat"
SH = ROOT / "Start_Sonder.sh"

#: Kept here as well as in the launchers on purpose: a test that reads the
#: bound out of the file it is testing cannot notice the bound changing.
SUPPORTED = ("3.11", "3.12", "3.13")
UNSUPPORTED_NEWER = ("3.14", "3.15")


@pytest.mark.parametrize("launcher", [BAT, SH], ids=["bat", "sh"])
def test_the_launcher_exists_and_is_readable(launcher):
    assert launcher.is_file(), f"{launcher.name} is missing"


@pytest.mark.parametrize("launcher", [BAT, SH], ids=["bat", "sh"])
def test_no_launcher_asks_for_an_unsupported_python_by_name(launcher):
    """`python3.14` in the candidate list is the `.sh` form of the bug."""
    text = launcher.read_text(encoding="utf-8", errors="replace")
    code = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("#", "REM ", "rem "))
    )
    for version in UNSUPPORTED_NEWER:
        assert f"python{version}" not in code, (
            f"{launcher.name} names python{version} as a candidate")
        assert f"py -{version}" not in code, (
            f"{launcher.name} names py -{version} as a candidate")


def test_the_bat_does_not_take_whatever_is_newest():
    """`py -3` is the Windows form of the bug: it means 'newest installed'."""
    code = "\n".join(
        line for line in BAT.read_text(encoding="utf-8",
                                       errors="replace").splitlines()
        if not line.lstrip().lower().startswith("rem ")
    )
    assert not re.search(r"py\s+-3(?![.\d])", code), (
        "Start_Sonder.bat selects `py -3`, which takes the newest Python on "
        "the machine regardless of whether the pinned dependencies build on it")


@pytest.mark.parametrize("launcher", [BAT, SH], ids=["bat", "sh"])
def test_every_supported_version_is_offered(launcher):
    text = launcher.read_text(encoding="utf-8", errors="replace")
    for version in SUPPORTED:
        assert version in text, (
            f"{launcher.name} never offers Python {version}")


@pytest.mark.parametrize("launcher", [BAT, SH], ids=["bat", "sh"])
def test_the_ceiling_is_enforced_and_not_merely_preferred(launcher):
    """A bare `python3` may itself BE the unsupported one, so preferring the
    right names is not enough — the range has to be checked."""
    text = launcher.read_text(encoding="utf-8", errors="replace")
    assert "3, 13" in text or "(3,13)" in text or "3.13" in text
    assert "version_info" in text, (
        f"{launcher.name} never inspects an interpreter's actual version")


def test_the_sh_refuses_an_existing_venv_built_by_an_unsupported_python():
    """Fixing selection does not fix a box that already has a bad `.venv`:
    reusing it is the whole point of a second run."""
    text = SH.read_text(encoding="utf-8")
    assert "outside the supported range" in text
    # ...and it must never delete the user's environment to repair it.
    assert "mv " in text and 'rm -rf "${ROOT}/${VENV}"' not in text.replace(
        "        rm -rf \\\"${ROOT}/${VENV}\\\"", "")
