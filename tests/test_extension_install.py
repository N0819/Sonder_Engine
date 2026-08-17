"""Installing, removing, and refusing a hostile bundle.

Phase 1 of the distribution plan: a host installs from a folder or a URL with
nothing reviewing what arrives. Consent for THAT is taken in the browser. What
this layer owes the host is narrower and testable: a malformed or hostile
ARCHIVE must not be able to damage the install before anyone gets to consent,
and an interrupted install must leave either the old extension or none.
"""

from __future__ import annotations

import json
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
