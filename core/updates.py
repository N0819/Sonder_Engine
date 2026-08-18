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

Two rules keep a slow network from damaging the checkout, learned from a
real failure where a release large enough to need a two-minute fetch left
the repo permanently unable to check for updates:

* Timing a fetch out must never SIGKILL it. Git removes the ``.lock`` files
  it holds when it receives SIGTERM, and cannot when it is killed outright;
  an orphaned ``refs/remotes/origin/main.lock`` breaks every later fetch
  until a human deletes it by hand. See :func:`_git`.
* A check should not fetch at all unless there is something new to fetch.
  :func:`_remote_tip` answers "is there anything new?" over the wire without
  writing to the object store or taking a single lock.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Hard ceiling so a hung network fetch can't wedge the request thread. This
# is generous because it is a backstop, not an expectation: a real release
# fetch on a slow link measured two minutes, and cutting one short is how the
# checkout got wedged in the first place. Checks reach it only when there are
# genuinely new objects to download -- see check_updates.
_FETCH_TIMEOUT = 300
_LOCAL_TIMEOUT = 15
# Read-only remote probe: one round trip, no transfer, so it can be strict.
_LS_REMOTE_TIMEOUT = 20
_GITHUB_TIMEOUT = 12
# Seconds given to a timed-out git to clean up its lock files before SIGKILL.
_TERM_GRACE = 5

_LOCK_HINT = (
    " A previous update check was interrupted and left a stale lock file "
    "behind. With no git command running, delete the '.lock' file named "
    "above and try again."
)


class GitError(Exception):
    """A git invocation failed; ``message`` carries git's stderr."""


def _lock_hint(message):
    """Append recovery guidance when git is complaining about a stale lock.

    Git's own wording ("Another git process seems to be running") sends the
    reader hunting for a process that exited long ago, so say what actually
    fixes it.
    """
    if "cannot lock ref" in message or "Unable to create" in message:
        return message.rstrip() + "\n" + _LOCK_HINT
    return message


def _git(*args, timeout=_LOCAL_TIMEOUT):
    """Run a git command in the repo root. Returns stripped stdout.

    Raises :class:`GitError` on a non-zero exit (or if git is missing),
    with the command's stderr as the message so the UI can show it.

    On timeout the child is asked to stop with SIGTERM and only killed if it
    ignores that. ``subprocess.run(timeout=...)`` sends SIGKILL instead, which
    is unsafe here: git deletes the ref and index ``.lock`` files it holds
    from its SIGTERM handler, and a SIGKILL leaves them on disk, where they
    block every subsequent fetch until someone removes them manually. (On
    Windows ``terminate`` cannot run that handler, so the guarantee is
    POSIX-only.)
    """
    try:
        proc = subprocess.Popen(
            ["git", *args],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH.")
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.communicate(timeout=_TERM_GRACE)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        raise GitError(f"git {args[0]} timed out after {timeout}s.")
    if proc.returncode != 0:
        detail = (err or out or "").strip()
        raise GitError(
            _lock_hint(detail)
            or f"git {args[0]} failed (exit {proc.returncode})."
        )
    return out.strip()


def _is_git_repo():
    """Return whether this install directory is itself a Git worktree root.

    ``git rev-parse --is-inside-work-tree`` is too permissive here: a copied
    install nested anywhere below an unrelated checkout would pass, and every
    later updater command would then operate on that parent repository.
    """
    try:
        top_level = _git("rev-parse", "--show-toplevel")
    except GitError:
        return False
    return os.path.normcase(os.path.realpath(top_level)) == os.path.normcase(
        os.path.realpath(REPO_ROOT)
    )


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


def _split_upstream(upstream):
    """``origin/main`` -> ``("origin", "main")``.

    Branch names may contain slashes (``origin/fix/pydantic-2-compat``); the
    remote name cannot, so only the first segment is the remote.
    """
    remote, _, name = upstream.partition("/")
    return remote, name


def _remote_tip(remote, branch):
    """The commit id ``refs/heads/<branch>`` points at on ``remote``.

    ``ls-remote`` is a single read-only round trip: it downloads no objects,
    writes nothing, and takes no locks, so it is safe to run on every check
    no matter how slow the link is. Returns None if the remote has no such
    branch, which sends the caller back to the fetch-and-compare path.
    """
    ref = f"refs/heads/{branch}"
    out = _git("ls-remote", remote, ref, timeout=_LS_REMOTE_TIMEOUT)
    for line in out.splitlines():
        oid, _, found = line.partition("\t")
        if found.strip() == ref:
            return oid.strip()
    return None


def _have_commit(oid):
    """Whether ``oid`` is already in the local object store.

    When it is, every count and log below can be computed offline and the
    fetch skipped entirely -- true both when there is no update and when a
    previous check already downloaded one.
    """
    try:
        _git("cat-file", "-e", f"{oid}^{{commit}}")
        return True
    except GitError:
        return False


def _sync_if_needed(remote, branch, upstream):
    """Resolve what to compare HEAD against, fetching only if we must.

    Returns the revision to use as the upstream tip: the remote's own commit
    id when ``ls-remote`` could name it, otherwise the remote-tracking ref.
    A fetch happens only when the remote tip is a commit this checkout has
    never seen.
    """
    tip = _remote_tip(remote, branch)
    if tip is None or not _have_commit(tip):
        _git("fetch", "--quiet", "--tags", remote, timeout=_FETCH_TIMEOUT)
    return tip or upstream


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

    try:
        branch = _current_branch()
        dirty = bool(_short_status())
    except GitError as e:
        return {"ok": False, "error": str(e)}
    if branch == "HEAD":
        return {"ok": False, "error": "Repository is in a detached-HEAD state; can't determine a branch to update."}

    try:
        upstream = _upstream_ref(branch)
        # Learn the remote tip, downloading objects only if it is new to us.
        # Neither path touches the working tree.
        target = _sync_if_needed(*_split_upstream(upstream), upstream)
        local = _git("rev-parse", "--short", "HEAD")
        behind = int(_git("rev-list", "--count", f"HEAD..{target}"))
        ahead = int(_git("rev-list", "--count", f"{target}..HEAD"))
        commits = []
        incoming_tags = set()
        if behind:
            log = _git("log", "--pretty=format:%h\x1f%s", f"HEAD..{target}")
            for line in log.splitlines():
                h, _, subject = line.partition("\x1f")
                commits.append({"hash": h, "subject": subject})
            incoming_tags = _incoming_tags(target)
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
        "dirty": dirty,
        "commits": commits,
        "releases": releases,
    }


def install_updates():
    """Fast-forward the working tree onto the tracked branch.

    Fetches again (so install is safe even if ``check_updates`` wasn't just
    run), then ``git merge --ff-only``. Refuses a dirty working tree or a
    diverged branch, even when Git could technically merge around unrelated
    local edits: an updater should never leave an install containing a mixture
    of two source versions. On success the caller must restart the server for
    new code to take effect.
    """
    if not _is_git_repo():
        return {"ok": False, "error": "This install is not a git checkout, so it can't self-update."}

    try:
        branch = _current_branch()
        dirty = bool(_short_status())
    except GitError as e:
        return {"ok": False, "error": str(e)}
    if branch == "HEAD":
        return {"ok": False, "error": "Repository is in a detached-HEAD state; can't update."}
    if dirty:
        return {
            "ok": False,
            "error": (
                "The working tree has local changes. Commit or stash them "
                "before installing updates."
            ),
        }

    try:
        upstream = _upstream_ref(branch)
        target = _sync_if_needed(*_split_upstream(upstream), upstream)
        before = _git("rev-parse", "--short", "HEAD")
        behind = int(_git("rev-list", "--count", f"HEAD..{target}"))
        if behind == 0:
            return {"ok": True, "updated": False, "current": before,
                    "message": "Already up to date."}
        _git("merge", "--ff-only", target, timeout=_FETCH_TIMEOUT)
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
