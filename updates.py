"""Self-update helper: check the GitHub origin for newer commits and
fast-forward the working tree onto them.

Kept deliberately small and side-effect-free at import time. All git work
happens through :func:`_git`, a thin subprocess wrapper scoped to the repo
root (the directory containing this file). The routes in ``app.py`` are
host-only by virtue of the global access-control middleware, so nothing
here re-checks auth.

The install path only ever fast-forwards (``git merge --ff-only``): it will
never create a merge commit, rewrite history, or discard local work. A dirty
working tree or a diverged branch makes install fail loudly with git's own
stderr rather than doing anything clever. The caller is expected to restart
the server process afterwards -- a running Python process does not pick up
updated source on disk on its own.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Hard ceiling so a hung network fetch can't wedge the request thread.
_FETCH_TIMEOUT = 60
_LOCAL_TIMEOUT = 15
_GITHUB_TIMEOUT = 12


class GitError(Exception):
    """A git invocation failed; ``message`` carries git's stderr."""


def _git(*args, timeout=_LOCAL_TIMEOUT):
    """Run a git command in the repo root. Returns stripped stdout.

    Raises :class:`GitError` on a non-zero exit (or if git is missing),
    with the command's stderr as the message so the UI can show it.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH.")
    except subprocess.TimeoutExpired:
        raise GitError(f"git {args[0]} timed out.")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise GitError(detail or f"git {args[0]} failed (exit {proc.returncode}).")
    return proc.stdout.strip()


def _is_git_repo():
    try:
        return _git("rev-parse", "--is-inside-work-tree") == "true"
    except GitError:
        return False


def _current_branch():
    # Empty (detached HEAD) -> "HEAD"; callers treat that as no tracking.
    return _git("rev-parse", "--abbrev-ref", "HEAD")


def _upstream_ref(branch):
    """Best-effort remote tracking ref for ``branch``.

    Prefers a configured upstream (``@{u}``); falls back to
    ``origin/<branch>`` and finally to whatever ``origin/HEAD`` points at,
    matching how this repo is normally cloned even when the local branch
    has no upstream set.
    """
    try:
        return _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    except GitError:
        pass
    for candidate in (f"origin/{branch}", "origin/HEAD"):
        try:
            _git("rev-parse", "--verify", "--quiet", candidate)
            if candidate == "origin/HEAD":
                # Resolve the symbolic ref to a concrete branch name.
                return _git("rev-parse", "--abbrev-ref", candidate)
            return candidate
        except GitError:
            continue
    raise GitError(
        "No remote tracking branch found. Is 'origin' configured?"
    )


def _short_status():
    """Working-tree cleanliness. Empty porcelain output == clean."""
    return _git("status", "--porcelain")


def _repo_slug():
    """``owner/repo`` for the origin remote, or None if it isn't GitHub.

    Handles both remote forms this repo is cloned with:
    ``https://github.com/owner/repo(.git)`` and
    ``git@github.com:owner/repo(.git)``.
    """
    try:
        url = _git("remote", "get-url", "origin")
    except GitError:
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/(.+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _incoming_tags(upstream):
    """Tag names reachable from ``upstream`` but not from current HEAD --
    i.e. the version tags this update would actually bring in. Empty when
    the incoming commits carry no release tag."""
    try:
        have = set(_git("tag", "--merged", "HEAD").split())
        coming = set(_git("tag", "--merged", upstream).split())
    except GitError:
        return set()
    return coming - have


def _github_releases(slug, wanted_tags):
    """Release notes from the GitHub API for the given tag names.

    Public-repo, unauthenticated read (subject to GitHub's ~60 req/hr/IP
    limit). Returns a list of ``{tag, name, body, url, published_at}`` in
    the API's newest-first order, or None on any failure so the caller can
    fall back to raw commit subjects. Never raises.
    """
    if not slug or not wanted_tags:
        return None
    req = urllib.request.Request(
        f"https://api.github.com/repos/{slug}/releases?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            # GitHub rejects API requests with no User-Agent.
            "User-Agent": "Sonder-Engine-Updater",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_GITHUB_TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    releases = []
    for r in data if isinstance(data, list) else []:
        tag = r.get("tag_name")
        if tag not in wanted_tags:
            continue
        releases.append({
            "tag": tag,
            "name": r.get("name") or tag,
            "body": (r.get("body") or "").strip(),
            "url": r.get("html_url") or "",
            "published_at": r.get("published_at") or "",
        })
    return releases


def check_updates():
    """Fetch origin and report how far behind the tracked branch is.

    Never mutates the working tree. Returns a dict the frontend renders
    directly; ``ok: False`` plus ``error`` signals an environment problem
    (not a git repo, no remote, offline) rather than raising.
    """
    if not _is_git_repo():
        return {"ok": False, "error": "This install is not a git checkout, so it can't self-update."}

    branch = _current_branch()
    if branch == "HEAD":
        return {"ok": False, "error": "Repository is in a detached-HEAD state; can't determine a branch to update."}

    try:
        upstream = _upstream_ref(branch)
        # Update remote-tracking refs and tags without touching the tree.
        _git("fetch", "--quiet", "--tags", "origin", timeout=_FETCH_TIMEOUT)
        local = _git("rev-parse", "--short", "HEAD")
        behind = int(_git("rev-list", "--count", f"HEAD..{upstream}"))
        ahead = int(_git("rev-list", "--count", f"{upstream}..HEAD"))
        commits = []
        incoming_tags = set()
        if behind:
            log = _git("log", "--pretty=format:%h\x1f%s", f"HEAD..{upstream}")
            for line in log.splitlines():
                h, _, subject = line.partition("\x1f")
                commits.append({"hash": h, "subject": subject})
            incoming_tags = _incoming_tags(upstream)
    except GitError as e:
        return {"ok": False, "error": str(e)}

    # Rich release notes for the incoming version tags, when any exist and
    # GitHub is reachable. None -> the frontend shows commit subjects instead.
    releases = _github_releases(_repo_slug(), incoming_tags) if incoming_tags else None

    return {
        "ok": True,
        "branch": branch,
        "upstream": upstream,
        "current": local,
        "behind": behind,
        "ahead": ahead,
        "up_to_date": behind == 0,
        "dirty": bool(_short_status()),
        "commits": commits,
        "releases": releases,
    }


def install_updates():
    """Fast-forward the working tree onto the tracked branch.

    Fetches again (so install is safe even if ``check_updates`` wasn't just
    run), then ``git merge --ff-only``. Refuses -- via git's own error --
    if the branch has diverged or local edits would be overwritten. On
    success the caller must restart the server for new code to take effect.
    """
    if not _is_git_repo():
        return {"ok": False, "error": "This install is not a git checkout, so it can't self-update."}

    branch = _current_branch()
    if branch == "HEAD":
        return {"ok": False, "error": "Repository is in a detached-HEAD state; can't update."}

    try:
        upstream = _upstream_ref(branch)
        _git("fetch", "--quiet", "origin", timeout=_FETCH_TIMEOUT)
        before = _git("rev-parse", "--short", "HEAD")
        behind = int(_git("rev-list", "--count", f"HEAD..{upstream}"))
        if behind == 0:
            return {"ok": True, "updated": False, "current": before,
                    "message": "Already up to date."}
        _git("merge", "--ff-only", upstream, timeout=_FETCH_TIMEOUT)
        after = _git("rev-parse", "--short", "HEAD")
    except GitError as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "updated": True,
        "previous": before,
        "current": after,
        "applied": behind,
        "message": f"Updated {before} → {after} ({behind} commit(s)). Restart the server to apply.",
    }
