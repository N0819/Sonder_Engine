import os
import pathlib
import stat
import sys

import pytest

from core import updates


class FakeGit:
    """Stand-in for :func:`updates._git` that records every invocation.

    Responses are keyed by the leading arguments of the command so a test
    only has to describe the calls it cares about.
    """

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        for prefix, value in self.responses.items():
            if args[: len(prefix)] == prefix:
                if isinstance(value, Exception):
                    raise value
                return value
        return ""

    def ran(self, command):
        return any(args and args[0] == command for args in self.calls)


def _check_harness(monkeypatch, responses):
    """Wire check_updates onto a FakeGit with the environment probes stubbed."""
    fake = FakeGit(responses)
    monkeypatch.setattr(updates, "_is_git_repo", lambda: True)
    monkeypatch.setattr(updates, "_current_branch", lambda: "main")
    monkeypatch.setattr(updates, "_short_status", lambda: "")
    monkeypatch.setattr(updates, "_upstream_ref", lambda branch: "origin/main")
    monkeypatch.setattr(updates, "_git", fake)
    return fake


def test_the_install_root_is_the_repository_not_the_package():
    """The one property every other test in this file monkeypatches away.

    Nine tests here patch `REPO_ROOT` or `_is_git_repo` outright, so when
    `updates.py` moved into `core/` and `REPO_ROOT` started naming
    `<repo>/core`, the whole suite stayed green while the feature was dead:
    `_is_git_repo()` compares the checkout's top level against this path, so
    it returned False for every real install and both routes answered "This
    install is not a git checkout".

    Asserted against the real module path, unpatched, because that is the
    thing that broke.
    """
    root = pathlib.Path(updates.REPO_ROOT)
    assert (root / "core" / "updates.py").is_file()
    assert (root / "Makefile").is_file()
    assert root.name != "core"


def test_git_repo_check_rejects_an_unrelated_parent_checkout(
    monkeypatch, tmp_path
):
    parent = tmp_path / "unrelated-checkout"
    install = parent / "copied-install"
    install.mkdir(parents=True)

    monkeypatch.setattr(updates, "REPO_ROOT", str(install))
    monkeypatch.setattr(
        updates, "_git", lambda *args, **kwargs: str(parent)
    )

    assert updates._is_git_repo() is False


def test_git_repo_check_accepts_the_install_as_checkout_root(
    monkeypatch, tmp_path
):
    install = tmp_path / "checkout"
    install.mkdir()

    monkeypatch.setattr(updates, "REPO_ROOT", str(install))
    monkeypatch.setattr(
        updates, "_git", lambda *args, **kwargs: str(install)
    )

    assert updates._is_git_repo() is True


def test_git_repo_check_handles_git_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise updates.GitError("not a checkout")

    monkeypatch.setattr(updates, "_git", fail)

    assert updates._is_git_repo() is False


def test_check_updates_returns_an_error_when_branch_lookup_fails(monkeypatch):
    monkeypatch.setattr(updates, "_is_git_repo", lambda: True)

    def fail():
        raise updates.GitError("HEAD is missing")

    monkeypatch.setattr(updates, "_current_branch", fail)

    assert updates.check_updates() == {
        "ok": False,
        "error": "HEAD is missing",
    }


def test_install_refuses_dirty_tree_before_contacting_remote(monkeypatch):
    monkeypatch.setattr(updates, "_is_git_repo", lambda: True)
    monkeypatch.setattr(updates, "_current_branch", lambda: "main")
    monkeypatch.setattr(updates, "_short_status", lambda: " M updates.py")

    def unexpected_remote_lookup(branch):
        raise AssertionError("dirty installs must not contact the remote")

    monkeypatch.setattr(updates, "_upstream_ref", unexpected_remote_lookup)

    result = updates.install_updates()

    assert result["ok"] is False
    assert "local changes" in result["error"]


def test_upstream_splits_on_the_remote_not_the_branch():
    # Branch names may contain slashes; remote names may not.
    assert updates._split_upstream("origin/main") == ("origin", "main")
    assert updates._split_upstream("origin/fix/pydantic-2-compat") == (
        "origin",
        "fix/pydantic-2-compat",
    )


def test_remote_tip_ignores_refs_that_merely_share_a_prefix(monkeypatch):
    monkeypatch.setattr(
        updates,
        "_git",
        lambda *a, **k: (
            "1111111111111111111111111111111111111111\trefs/heads/main-old\n"
            "2222222222222222222222222222222222222222\trefs/heads/main\n"
        ),
    )

    assert updates._remote_tip("origin", "main") == "2" * 40


def test_remote_tip_is_none_when_the_branch_is_absent(monkeypatch):
    monkeypatch.setattr(updates, "_git", lambda *a, **k: "")

    assert updates._remote_tip("origin", "main") is None


def test_check_skips_the_fetch_when_the_remote_tip_is_already_local(monkeypatch):
    # The expensive, lock-taking path must not run just to answer
    # "is there anything new?" -- that fetch timing out is what wedged the
    # checkout the first time.
    tip = "b" * 40
    fake = _check_harness(monkeypatch, {
        ("ls-remote",): f"{tip}\trefs/heads/main",
        ("cat-file",): "",
        ("rev-parse", "--short", "HEAD"): "aaa1111",
        ("rev-list", "--count", f"HEAD..{tip}"): "2",
        ("rev-list", "--count", f"{tip}..HEAD"): "0",
        ("log",): "b1b1b1b\x1ffirst subject\nb2b2b2b\x1fsecond subject",
    })

    result = updates.check_updates()

    assert fake.ran("fetch") is False
    assert result["ok"] is True
    assert result["behind"] == 2
    assert result["up_to_date"] is False
    assert [c["subject"] for c in result["commits"]] == [
        "first subject",
        "second subject",
    ]


def test_check_fetches_when_the_remote_tip_is_unknown_locally(monkeypatch):
    tip = "c" * 40
    fake = _check_harness(monkeypatch, {
        ("ls-remote",): f"{tip}\trefs/heads/main",
        ("cat-file",): updates.GitError("no such object"),
        ("rev-parse", "--short", "HEAD"): "aaa1111",
        ("rev-list",): "0",
    })

    result = updates.check_updates()

    assert fake.ran("fetch") is True
    assert result["ok"] is True
    assert result["up_to_date"] is True


def test_check_falls_back_to_fetching_when_the_remote_has_no_such_branch(
    monkeypatch
):
    fake = _check_harness(monkeypatch, {
        ("ls-remote",): "",
        ("rev-parse", "--short", "HEAD"): "aaa1111",
        ("rev-list",): "0",
    })

    result = updates.check_updates()

    assert fake.ran("fetch") is True
    # With no remote tip to name, comparisons fall back to the tracking ref.
    assert any("origin/main" in a for args in fake.calls for a in args)
    assert result["ok"] is True


def test_lock_failures_explain_how_to_recover():
    message = updates._lock_hint(
        "error: cannot lock ref 'refs/remotes/origin/main': Unable to create "
        "'.git/refs/remotes/origin/main.lock': File exists."
    )

    assert "stale lock file" in message


def test_ordinary_failures_are_left_alone():
    assert updates._lock_hint("fatal: not a git repository") == (
        "fatal: not a git repository"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")
def test_timed_out_git_is_asked_to_clean_up_before_being_killed(
    monkeypatch, tmp_path
):
    """A timing-out fetch must get SIGTERM, not SIGKILL.

    Git deletes the ref locks it holds from its SIGTERM handler. A SIGKILL
    skips that, orphaning 'refs/remotes/origin/main.lock' and breaking every
    later fetch until a human removes it by hand.
    """
    marker = tmp_path / "cleaned-up"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake_git = bindir / "git"
    fake_git.write_text(
        # The sleep runs in the background so the shell can service the trap,
        # and is killed with it so no orphan holds the stdout pipe open.
        "#!/bin/sh\n"
        f"trap 'touch {marker}; kill $pid 2>/dev/null; exit 143' TERM\n"
        "sleep 30 & pid=$!\n"
        "wait $pid\n"
    )
    fake_git.chmod(fake_git.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("PATH", str(bindir), prepend=os.pathsep)
    monkeypatch.setattr(updates, "REPO_ROOT", str(tmp_path))

    with pytest.raises(updates.GitError) as excinfo:
        updates._git("fetch", timeout=1)

    assert "timed out" in str(excinfo.value)
    assert marker.exists(), "git was killed without a chance to drop its locks"
