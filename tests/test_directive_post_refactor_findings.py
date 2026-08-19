"""Three findings from the Directive team's review of alpha 9.6.1.

Reviewed at `48920a7`, verified 2026-08-19. All three were confirmed against
source before being acted on; none needed refuting this time.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path, PureWindowsPath

import pytest

import extension_runtime
from extension_runtime import ExtensionError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check  # noqa: E402


# ------------------------------------------------------- the structural check

def test_the_install_root_owner_is_recognised_with_windows_separators():
    """`project_check.INSTALL_ROOT_OWNER` is written with a forward slash, like every
    constant in `project_check.py`. The comparison used `str(Path)`, which on
    Windows yields `core\\paths.py` -- so the one file PERMITTED to derive a
    filesystem root audited itself as a violation, and no maintainer on
    Windows could get a green structural check out of the tool that is
    supposed to be the local evidence gate.

    Asserted against `PureWindowsPath` so it fails on Linux too; a guard that
    can only be checked on the platform it is broken on is not a guard.
    """
    native = PureWindowsPath("core") / "paths.py"
    assert str(native) == "core\\paths.py", "fixture is not exercising Windows"
    assert str(native) != project_check.INSTALL_ROOT_OWNER
    assert native.as_posix() == project_check.INSTALL_ROOT_OWNER


def test_no_relative_path_is_derived_without_normalising_it():
    """The broken site was the ONLY one that used `str()`; eight others already
    used `.as_posix()`, which is exactly why it was invisible. Pinned as a
    property of the file so the next `rel = ...` cannot reintroduce it."""
    text = (ROOT / "tools" / "project_check.py").read_text(encoding="utf-8")
    assert "str(path.relative_to(ROOT))" not in text
    assert "rel = path.relative_to(ROOT)\n" not in text


# ------------------------------------------------- installer git diagnostics

class _Recorded(ExtensionError):
    pass


def test_a_git_failure_is_not_reported_as_an_oversized_extension(monkeypatch):
    """Git rejected a reviewer's checkout for dubious ownership.
    `_git_source_files` swallowed it, `_source_manifest` walked the directory
    as though it were a plain one -- `.git`, `node_modules` and every ignored
    artifact included -- and the installer reported "at least 4097 files, more
    than the 4096 an extension may install". The package git would ship was
    207 files and 8MB.

    The host was told to shrink an extension that was never too big, and never
    told the thing they could have fixed in one command.
    """
    def fake_git(*args):
        if "rev-parse" in args:
            raise _Recorded(
                "fatal: detected dubious ownership in repository at '/src'")
        raise AssertionError("ls-files must not run after rev-parse failed")

    monkeypatch.setattr(extension_runtime, "_git", fake_git)

    with pytest.raises(ExtensionError) as caught:
        extension_runtime._git_source_files(Path("/src"))
    assert "dubious ownership" in str(caught.value)


def test_ls_files_failing_after_rev_parse_said_yes_is_an_error(monkeypatch):
    """The repository is ESTABLISHED by then. A failure there cannot mean
    "not a work tree", so it can only be an inspection error -- returning None
    would claim the directory is something `rev-parse` just said it is not."""
    def fake_git(*args):
        if "rev-parse" in args:
            return "true\n"
        raise _Recorded("error: could not lock index")

    monkeypatch.setattr(extension_runtime, "_git", fake_git)

    with pytest.raises(ExtensionError) as caught:
        extension_runtime._git_source_files(Path("/src"))
    assert "could not lock index" in str(caught.value)


def test_a_plain_directory_still_falls_back(monkeypatch):
    """The fallback is not removed, only narrowed to the case it was written
    for: git saying, in its own words, that this is not a repository."""
    def fake_git(*args):
        raise _Recorded(
            "fatal: not a git repository (or any of the parent directories)")

    monkeypatch.setattr(extension_runtime, "_git", fake_git)

    assert extension_runtime._git_source_files(Path("/plain")) is None


def test_a_bare_repository_still_falls_back(monkeypatch):
    """`rev-parse` answering "false" is an ANSWER, not a failure."""
    monkeypatch.setattr(extension_runtime, "_git", lambda *a: "false\n")
    assert extension_runtime._git_source_files(Path("/bare")) is None


# --------------------------------------------------------- browser CI gating

def test_browser_provisioning_does_not_shell_out_to_apt():
    """`--with-deps` runs apt-get, and apt is the part that is not
    deterministic here: fifty minutes with no ceiling on 2026-08-19, then
    twelve minutes of Ubuntu font packages once a ceiling existed -- so the
    tagged release commit has passing Python jobs and no browser evidence.

    The libraries are on the runner image already, which the green runs either
    side of that failure prove. If an image ever drops one, Chromium fails to
    launch and names it, which is a better failure than a font download."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8")
    commands = [line.split("run:", 1)[1].strip()
                for line in workflow.splitlines() if "run:" in line]

    assert any("playwright install chromium" in c for c in commands)
    assert not [c for c in commands if "--with-deps" in c], (
        "apt is back in browser provisioning")
    assert "~/.cache/ms-playwright" in workflow, "browser payload is not cached"


# ------------------------------------ the host's own view routes select a frame

def test_the_http_view_routes_take_a_frame_parameter():
    """The extension API gained frame selection in 9.6 and these two routes did
    not, because the host UI had no consumer. That left one surface able to
    compose a frame-coherent read and its HTTP twin unable to -- an asymmetry
    between two doors onto one room, which is how an out-of-process caller
    straddles eras without being able to say so. The underlying functions
    already accepted `frame_id`; only the routes did not pass it.
    """
    from web import app as web_app

    for route in (web_app.story_view_get, web_app.player_view_get):
        assert "frame" in inspect.signature(route).parameters, route.__name__


def test_an_unasked_frame_is_omitted_rather_than_passed_as_none():
    """`story_view`'s default is a SENTINEL meaning "the latest committed turn
    across every frame". `None` is a different question -- it would be
    validated as a frame id -- so a route that always passed the parameter
    would turn "I did not ask" into "frame None"."""
    from web import story_view

    for fn in (story_view.story_view, story_view.player_view):
        default = inspect.signature(fn).parameters["frame_id"].default
        assert default is story_view._LATEST_FRAME
        assert default is not None
