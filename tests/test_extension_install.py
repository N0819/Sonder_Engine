"""Installing, removing, and refusing a hostile bundle.

Phase 1 of the distribution plan: a host installs from a folder or a URL with
nothing reviewing what arrives. Consent for THAT is taken in the browser. What
this layer owes the host is narrower and testable: a malformed or hostile
ARCHIVE must not be able to damage the install before anyone gets to consent,
and an interrupted install must leave either the old extension or none.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

import extension_runtime as ext


DEMO = Path(__file__).resolve().parents[1] / "extensions" / "cohesion-demo"


@pytest.fixture
def root(tmp_path, monkeypatch, temp_db):
    monkeypatch.setenv(ext.ROOT_ENV, str(tmp_path))
    ext.reload()
    yield tmp_path
    ext.reload()


def test_installing_from_a_folder_lands_it_switched_off(root):
    """Nothing runs until the host enables it -- install is not consent."""
    row = ext.install_extension(str(DEMO))
    assert row["id"] == "cohesion-demo"
    assert row["enabled"] is False
    assert (root / "cohesion-demo" / "manifest.json").is_file()


def test_provenance_is_recorded_at_install(root):
    """Phase 2 tells a reviewed install from a sideloaded one by reading this,
    so it is written on day one rather than re-derived later."""
    row = ext.install_extension(str(DEMO))
    assert row["provenance"].startswith("local:")


def test_a_second_install_is_refused_rather_than_overwriting(root):
    ext.install_extension(str(DEMO))
    with pytest.raises(ext.ExtensionError, match="already installed"):
        ext.install_extension(str(DEMO))


def test_a_bundle_without_a_manifest_installs_nothing(root, tmp_path_factory):
    # Sourced from OUTSIDE the extensions root, or the source directory itself
    # would be what the assertion finds.
    empty = tmp_path_factory.mktemp("sources") / "notanextension"
    empty.mkdir()
    (empty / "readme.txt").write_text("hello", encoding="utf-8")
    with pytest.raises(ext.ExtensionError, match="manifest"):
        ext.install_extension(str(empty))
    assert not (root / "notanextension").exists(), "a failed install left debris"
    assert "notanextension" not in ext.installed_extensions()


def test_a_missing_source_is_refused(root):
    with pytest.raises(ext.ExtensionError):
        ext.install_extension(str(root / "does-not-exist"))
    with pytest.raises(ext.ExtensionError, match="nothing to install"):
        ext.install_extension("")


# --- the archive is the attack surface -------------------------------------

def _zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


@pytest.mark.parametrize("escaping", [
    "../escaped.txt",
    "../../escaped.txt",
    "nested/../../escaped.txt",
])
def test_zip_slip_is_refused(root, tmp_path, escaping):
    """An archive names its own paths. The extensions directory is writable by
    the engine -- that is what makes in-UI install possible -- so a member
    naming `../..` would otherwise be written wherever it liked."""
    bundle = _zip(tmp_path / "evil.zip", {escaping: "pwned"})
    with zipfile.ZipFile(bundle) as archive:
        with pytest.raises(ext.ExtensionError, match="escapes"):
            ext._safe_extract(archive, root / "probe")


def test_an_absolute_member_is_refused(root, tmp_path):
    bundle = _zip(tmp_path / "abs.zip", {"/etc/pwned": "x"})
    with zipfile.ZipFile(bundle) as archive:
        with pytest.raises(ext.ExtensionError, match="escapes"):
            ext._safe_extract(archive, root / "probe")


def test_a_symlink_member_is_refused(root, tmp_path):
    """A link is a path that resolves AFTER any check, so it is refused
    outright rather than validated."""
    bundle = tmp_path / "link.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.external_attr = (0xA1FF << 16)  # S_IFLNK | 0777
        archive.writestr(info, "/etc/passwd")
    with zipfile.ZipFile(bundle) as archive:
        with pytest.raises(ext.ExtensionError, match="symlink"):
            ext._safe_extract(archive, root / "probe")


def test_a_folder_install_is_audited_like_every_other_source(root, tmp_path):
    """"The rules that govern what may be installed should not depend on how
    it travelled" -- `_audit_tree`'s own words. A folder was bound by none of
    them, and `copytree(symlinks=False)` DEREFERENCES a link rather than
    refusing it, so a link in the source arrived as a copy of its target."""
    origin = tmp_path / "folder"
    origin.mkdir()
    (origin / "manifest.json").write_text(
        json.dumps({"id": "folder-ext", "version": "1.0.0", "ext_api": 1}),
        encoding="utf-8")
    try:
        (origin / "secrets").symlink_to("/etc/passwd")
    except (OSError, NotImplementedError):
        pytest.skip("this platform does not make symlinks")

    with pytest.raises(ext.ExtensionError, match="symlink"):
        ext.install_extension(str(origin))
    assert not (root / "folder-ext").exists()


def test_a_folder_install_obeys_the_size_ceiling(root, tmp_path, monkeypatch):
    origin = tmp_path / "folder"
    origin.mkdir()
    (origin / "manifest.json").write_text(
        json.dumps({"id": "folder-ext", "version": "1.0.0", "ext_api": 1}),
        encoding="utf-8")
    (origin / "blob.bin").write_text("x" * 200, encoding="utf-8")

    monkeypatch.setattr(ext, "MAX_EXTRACTED_BYTES", 10)
    with pytest.raises(ext.ExtensionError, match="larger than"):
        ext.install_extension(str(origin))
    assert not (root / "folder-ext").exists()


def test_an_ordinary_archive_still_extracts(root, tmp_path):
    bundle = _zip(tmp_path / "ok.zip", {"a.txt": "1", "sub/b.txt": "2"})
    destination = root / "probe"
    destination.mkdir()
    with zipfile.ZipFile(bundle) as archive:
        ext._safe_extract(archive, destination)
    assert (destination / "a.txt").read_text() == "1"
    assert (destination / "sub" / "b.txt").read_text() == "2"


# --- removal ----------------------------------------------------------------

def test_removing_takes_the_code(root):
    ext.install_extension(str(DEMO))
    assert ext.remove_extension("cohesion-demo")["removed"] is True
    assert not (root / "cohesion-demo").exists()
    assert "cohesion-demo" not in ext.installed_extensions()


def test_removing_leaves_what_the_extension_stored(root, temp_db):
    """Removal takes the code, not the history. A story played with an
    extension keeps its state, so reinstalling picks up where it left off and
    the story stays loadable meanwhile."""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES('t','',0)")
    temp_db.wset(chat_id, "ext:cohesion-demo", {"score": 61})
    ext.install_extension(str(DEMO))
    ext.remove_extension("cohesion-demo")
    assert temp_db.wget(chat_id, "ext:cohesion-demo") == {"score": 61}


def test_removing_something_absent_is_an_error_not_a_crash(root):
    with pytest.raises(ext.ExtensionError, match="not installed"):
        ext.remove_extension("never-existed")


@pytest.mark.parametrize("bad", ["../escape", "Has-Capitals", "", "a" * 80])
def test_an_invalid_id_is_refused_on_removal(root, bad):
    with pytest.raises(ext.ExtensionError, match="invalid extension id"):
        ext.remove_extension(bad)


class TestArchiveResourceCeilings:
    """Zip slip is about WHERE bytes land; these are about HOW MANY.

    `MAX_BUNDLE_BYTES` caps the download, which says nothing about what it
    expands to -- zip turns a few megabytes of zeroes into gigabytes, so a
    bundle that passes every path check could still fill the host's disk. The
    release note claimed a hostile archive "cannot damage the install"; that
    was true of the directory and not of the volume it sits on.
    """

    def _bomb(self, path, *, member_bytes, members=1):
        import zipfile

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("bomb/manifest.json", json.dumps({
                "id": "bomb", "version": "1.0.0", "ext_api": 1, "name": "Bomb",
                "capabilities": {},
            }))
            for index in range(members):
                archive.writestr(f"bomb/pad{index}.bin", b"\0" * member_bytes)
        return path

    def test_a_highly_compressible_archive_is_refused(self, tmp_path,
                                                      monkeypatch, temp_db):
        import zipfile

        monkeypatch.setenv(ext.ROOT_ENV, str(tmp_path / "extensions"))
        (tmp_path / "extensions").mkdir()
        ext.reload()
        monkeypatch.setattr(ext, "MAX_EXTRACTED_BYTES", 64 * 1024)

        bomb = self._bomb(tmp_path / "bomb.zip", member_bytes=1024 * 1024)
        # The whole point: it is tiny on the wire and huge on disk.
        assert bomb.stat().st_size < 16 * 1024

        with zipfile.ZipFile(bomb) as archive:
            with pytest.raises(ext.ExtensionError, match="expands to more than"):
                ext._safe_extract(archive, tmp_path / "staged")

    def test_a_flood_of_tiny_files_is_refused(self, tmp_path, monkeypatch,
                                              temp_db):
        """Bytes are not the only budget: empty files cost inodes and would
        pass a size ceiling untouched."""
        import zipfile

        monkeypatch.setattr(ext, "MAX_ARCHIVE_MEMBERS", 8)
        flood = self._bomb(tmp_path / "flood.zip", member_bytes=0, members=32)

        with zipfile.ZipFile(flood) as archive:
            with pytest.raises(ext.ExtensionError, match="more than the"):
                ext._safe_extract(archive, tmp_path / "staged")

    def test_an_honest_bundle_still_installs(self, tmp_path, monkeypatch,
                                             temp_db):
        """The ceilings must not be so tight that a real extension trips them."""
        import zipfile

        staged = tmp_path / "staged"
        ordinary = self._bomb(tmp_path / "ok.zip", member_bytes=2048)
        with zipfile.ZipFile(ordinary) as archive:
            ext._safe_extract(archive, staged)
        assert (staged / "bomb" / "manifest.json").is_file()
        assert (staged / "bomb" / "pad0.bin").stat().st_size == 2048

    def test_the_write_side_counter_is_belt_and_braces(self, tmp_path,
                                                       monkeypatch, temp_db):
        """Declared sizes are the archive's own claim about itself.

        CPython's `zipfile` happens to enforce `file_size` on read, so in
        practice a lie is caught before it costs anything -- try to fake one
        and you get `BadZipFile` instead. That is luck we do not own, so the
        bytes actually written are counted too, and this exercises that path
        through the same interface `_safe_extract` uses.
        """
        class _Member:
            def __init__(self, name, size):
                self.filename = name
                self.file_size = size
                self.external_attr = 0

            def is_dir(self):
                return False

        class _Archive:
            """Declares one byte per file and writes far more."""

            def __init__(self, root):
                self.root = root
                self.members = [_Member(f"pad{i}.bin", 1) for i in range(8)]

            def infolist(self):
                return self.members

            def extract(self, member, path):
                target = Path(path) / member.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"\0" * 4096)

        monkeypatch.setattr(ext, "MAX_EXTRACTED_BYTES", 8192)
        staged = tmp_path / "staged"
        with pytest.raises(ext.ExtensionError, match="expands to more than"):
            ext._safe_extract(_Archive(staged), staged)


class TestGitSources:
    """Installing from a repository, and finding out when it has moved.

    Exercised against a real local repository rather than a mocked subprocess:
    the interesting parts of this path are git's actual behaviour -- what
    `--branch` accepts, what `rev-parse` returns, what `ls-remote` prints for a
    tag versus a branch -- and a mock would assert my beliefs about git instead
    of git.
    """

    def _repo(self, tmp_path, ext_id="repo-ext", version="1.0.0"):
        import subprocess

        origin = tmp_path / "origin"
        (origin / ext_id).mkdir(parents=True)
        (origin / ext_id / "manifest.json").write_text(json.dumps({
            "id": ext_id, "version": version, "ext_api": 1, "name": "Repo Ext",
            "capabilities": {},
        }), encoding="utf-8")

        def git(*args):
            subprocess.run(("git",) + args, cwd=origin, check=True,
                           capture_output=True)

        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "T")
        git("add", "-A")
        git("commit", "-q", "-m", "one")
        return origin, git

    def _commit_more(self, origin, git, ext_id="repo-ext", version="1.1.0"):
        (origin / ext_id / "manifest.json").write_text(json.dumps({
            "id": ext_id, "version": version, "ext_api": 1, "name": "Repo Ext",
            "capabilities": {},
        }), encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "two")

    # -- what counts as a repository URL

    @pytest.mark.parametrize("source,kind", [
        ("https://github.com/owner/repo", "git"),
        ("https://github.com/owner/repo.git", "git"),
        ("https://gitlab.com/owner/repo", "git"),
        ("https://example.com/thing.git", "git"),
        ("git+https://example.com/thing", "git"),
        ("https://github.com/owner/repo#v2", "git"),
        ("https://example.com/bundle.zip", "zip"),
        ("https://example.com/download", "zip"),
        ("https://github.com/owner/repo/releases/x.zip", "zip"),
        ("/srv/extensions/mine", "local"),
        ("file:///srv/repos/mine", "git"),
        ("git+file:///srv/repos/mine", "git"),
    ])
    def test_a_source_is_classified_before_anything_is_fetched(self, source,
                                                               kind):
        assert ext._source_kind(source) == kind

    def test_an_ssh_remote_is_refused_with_the_reason(self):
        """It would not fail -- it would HANG. Without a key git blocks on a
        passphrase prompt that nobody is at the terminal to answer."""
        for source in ("ssh://git@github.com/o/r.git",
                       "git@github.com:o/r.git",
                       "git://example.com/r"):
            with pytest.raises(ext.ExtensionError, match="ssh|http"):
                ext._source_kind(source)

    def test_a_source_that_is_a_git_flag_is_refused(self):
        """`--upload-pack=...` is a command, not a URL."""
        with pytest.raises(ext.ExtensionError):
            ext._source_kind("--upload-pack=touch /tmp/pwned")

    # -- installing

    def test_a_repository_installs_and_records_where_it_came_from(
            self, tmp_path, monkeypatch, temp_db):
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, _git = self._repo(tmp_path)

        row = ext.install_extension(f"file://{origin}")

        assert row["id"] == "repo-ext"
        assert row["version"] == "1.0.0"
        assert row["updatable"] is True
        assert row["commit"]
        assert row["source_ref"] == "main"
        # The working tree, not the repository: an update re-clones, so there
        # is no git state on the host to drift or conflict.
        assert not (root / "repo-ext" / ".git").exists()

    def test_a_ref_may_be_named(self, tmp_path, monkeypatch, temp_db):
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, git = self._repo(tmp_path)
        git("tag", "v1")
        self._commit_more(origin, git)

        row = ext.install_extension(f"file://{origin}#v1")

        assert row["version"] == "1.0.0", "the tag, not the newer default branch"
        assert row["source_ref"] == "v1"

    # -- checking

    def test_a_check_finds_a_moved_remote(self, tmp_path, monkeypatch,
                                          temp_db):
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, git = self._repo(tmp_path)
        ext.install_extension(f"file://{origin}")

        before = ext.check_update("repo-ext")
        assert before["checkable"] is True
        assert before["update"] is False

        self._commit_more(origin, git)
        after = ext.check_update("repo-ext")
        assert after["update"] is True
        assert after["latest"] != after["current"]

    def test_a_source_with_no_upstream_is_uncheckable_not_up_to_date(
            self, tmp_path, monkeypatch, temp_db):
        """The distinction the whole report exists to make.

        Reporting a folder install as "up to date" is the same claim with the
        truth taken out -- nothing was asked, so nothing is known.
        """
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        plain = tmp_path / "plain-ext"
        plain.mkdir()
        (plain / "manifest.json").write_text(json.dumps({
            "id": "plain-ext", "version": "1.0.0", "ext_api": 1,
            "name": "Plain", "capabilities": {},
        }), encoding="utf-8")
        ext.install_extension(str(plain))

        report = ext.check_update("plain-ext")
        assert report["checkable"] is False
        assert report["update"] is False
        assert "zip" in report["reason"] or "folder" in report["reason"]

    def test_an_unreachable_remote_is_reported_not_raised(
            self, tmp_path, monkeypatch, temp_db):
        """A sweep runs for every installed extension, so one dead repository
        must not fail the check for the others."""
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, _git = self._repo(tmp_path)
        ext.install_extension(f"file://{origin}")
        shutil.rmtree(origin)

        report = ext.check_update("repo-ext")
        assert report["checkable"] is False
        assert report["update"] is False
        assert report["reason"]

        # And the sweep still returns a row for it.
        assert [row["id"] for row in ext.check_updates()] == ["repo-ext"]

    # -- updating

    def test_updating_takes_the_newer_commit(self, tmp_path, monkeypatch,
                                             temp_db):
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, git = self._repo(tmp_path)
        first = ext.install_extension(f"file://{origin}")
        self._commit_more(origin, git)

        row = ext.update_extension("repo-ext")

        assert row["updated"] is True
        assert row["version"] == "1.1.0"
        assert row["previous_version"] == "1.0.0"
        assert row["commit"] != first["commit"]

    def test_updating_an_unchanged_repository_does_nothing(
            self, tmp_path, monkeypatch, temp_db):
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, _git = self._repo(tmp_path)
        ext.install_extension(f"file://{origin}")

        row = ext.update_extension("repo-ext")
        assert row["updated"] is False

    def test_an_update_keeps_the_extension_enabled(self, tmp_path, monkeypatch,
                                                   temp_db):
        from core.db import set_setting

        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, git = self._repo(tmp_path)
        ext.install_extension(f"file://{origin}")
        set_setting(ext.ENABLED_SETTING, json.dumps(["repo-ext"]))
        ext.activate(refresh=True)
        self._commit_more(origin, git)

        ext.update_extension("repo-ext")

        assert ext.is_enabled("repo-ext") is True

    def test_an_update_that_would_not_load_leaves_the_old_one_standing(
            self, tmp_path, monkeypatch, temp_db):
        """Validation happens in staging, before the installed copy is touched.

        The version a host is running must never be destroyed by a broken
        upstream commit -- that turns someone else's bad push into an outage on
        a machine that did nothing.
        """
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, git = self._repo(tmp_path)
        ext.install_extension(f"file://{origin}")

        (origin / "repo-ext" / "manifest.json").write_text(
            "{ not json at all", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "broken")

        with pytest.raises(ext.ExtensionError):
            ext.update_extension("repo-ext")

        rows = {row["id"]: row for row in ext.listing()}
        assert rows["repo-ext"]["version"] == "1.0.0"
        assert rows["repo-ext"]["error"] is None

    def test_a_repository_that_renames_itself_is_refused(
            self, tmp_path, monkeypatch, temp_db):
        """An id change is a different extension, and updating into it would
        silently hand one extension's stored story state to another."""
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        origin, git = self._repo(tmp_path)
        ext.install_extension(f"file://{origin}")

        (origin / "repo-ext" / "manifest.json").write_text(json.dumps({
            "id": "renamed-ext", "version": "2.0.0", "ext_api": 1,
            "name": "Renamed", "capabilities": {},
        }), encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "renamed")

        with pytest.raises(ext.ExtensionError, match="install it separately"):
            ext.update_extension("repo-ext")

    def test_updating_something_with_no_upstream_is_refused(
            self, tmp_path, monkeypatch, temp_db):
        root = tmp_path / "extensions"
        root.mkdir()
        monkeypatch.setenv(ext.ROOT_ENV, str(root))
        ext.reload()
        plain = tmp_path / "plain-ext"
        plain.mkdir()
        (plain / "manifest.json").write_text(json.dumps({
            "id": "plain-ext", "version": "1.0.0", "ext_api": 1,
            "name": "Plain", "capabilities": {},
        }), encoding="utf-8")
        ext.install_extension(str(plain))

        with pytest.raises(ext.ExtensionError, match="nothing to update from"):
            ext.update_extension("plain-ext")

    # -- the ceilings apply to a clone too

    def test_a_clone_is_audited_like_an_archive(self, tmp_path, monkeypatch):
        """`_safe_extract` never sees a clone, and a repository can hold
        symlinks and gigabytes just as happily as a zip can."""
        tree = tmp_path / "tree"
        (tree / "sub").mkdir(parents=True)
        (tree / "sub" / "real.txt").write_text("x" * 100, encoding="utf-8")
        ext._audit_tree(tree)                       # fine as it stands

        monkeypatch.setattr(ext, "MAX_EXTRACTED_BYTES", 10)
        with pytest.raises(ext.ExtensionError, match="larger than"):
            ext._audit_tree(tree)

    def test_a_symlink_in_a_repository_is_refused(self, tmp_path):
        tree = tmp_path / "tree"
        tree.mkdir()
        (tree / "real.txt").write_text("ok", encoding="utf-8")
        try:
            (tree / "escape").symlink_to("/etc/passwd")
        except (OSError, NotImplementedError):
            pytest.skip("this platform does not make symlinks")
        with pytest.raises(ext.ExtensionError, match="symlink"):
            ext._audit_tree(tree)


class TestTheUpdateSweepIsBounded:
    """A route's cost is latency, not bandwidth.

    `check_update` is one `ls-remote` each with no download, which is what
    makes checking everything at once cheap in BYTES. Serially, against an
    unreachable network, ten installed extensions is ten times the 120s git
    timeout -- a twenty-minute request holding a threadpool worker.
    """

    def _slow_extension(self, root, ext_id):
        directory = root / ext_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "manifest.json").write_text(json.dumps({
            "id": ext_id, "version": "1.0.0", "ext_api": 1,
            "source_url": "https://example.invalid/repo.git",
            "commit": "deadbeef",
        }), encoding="utf-8")

    def test_a_sweep_stops_at_its_budget_and_says_so(self, root, monkeypatch):
        for name in ("a-ext", "b-ext", "c-ext"):
            self._slow_extension(root, name)
        ext.reload()

        monkeypatch.setattr(ext, "UPDATE_SWEEP_SECONDS", 0.05)

        def slow_head(url, ref, *, timeout=None):
            import time as _time
            _time.sleep(0.06)
            return "deadbeef"

        monkeypatch.setattr(ext, "_git_remote_head", slow_head)
        rows = {row["id"]: row for row in ext.check_updates()}

        assert len(rows) == 3
        exhausted = [row for row in rows.values()
                     if "budget" in (row["reason"] or "")]
        assert exhausted, "the sweep ran every remote with no ceiling"
        # Never "up to date" with the truth taken out.
        assert all(row["update"] is False and row["checkable"] is False
                   for row in exhausted)

    def test_each_remote_gets_only_what_is_left_of_the_budget(
            self, root, monkeypatch):
        self._slow_extension(root, "a-ext")
        ext.reload()
        seen = {}

        def record(url, ref, *, timeout=None):
            seen["timeout"] = timeout
            return "deadbeef"

        monkeypatch.setattr(ext, "_git_remote_head", record)
        # `raising=False` so this test states the BEHAVIOUR rather than the
        # existence of a constant: without a sweep budget the call below still
        # runs, and the recorded timeout is None.
        monkeypatch.setattr(ext, "UPDATE_SWEEP_SECONDS", 3.0, raising=False)
        ext.check_updates()

        assert seen["timeout"] is not None, (
            "each remote must be given its share of the sweep's budget")
        assert seen["timeout"] <= 3.0
