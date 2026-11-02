"""Code the host has not consented to never runs: an update brings an enabled
extension back DISABLED, and an install never inherits a standing enablement.

Audit 2026-11-01 (frontend_lorebooks_editors F2, SECURITY, CONFIRMED by
tracing): the host consents to an extension at Enable -- the dialog that
discloses its capability list (`static/js/settings.js`: "Disclosure that
arrives after consent is not disclosure"). Update re-cloned the remote and,
because the extension was enabled, `activate()`d the NEW version's
`register(api)` inside the engine process with one click and no dialog: v2's
new capabilities, or simply its new code, ran on v1's consent. The rule
stated once: new code runs only after the Enable that discloses it.
"""

from __future__ import annotations

import json
import subprocess
import threading

import pytest

import extension_runtime as ext


ENTRY = ("def register(api):\n"
         "    api.add_stage('pulse', anchor='after:director_resolve',\n"
         "                  handler=lambda view, api, nonce: {'pulse': 1})\n")


def _repo(tmp_path, version="1.0.0", capabilities=None):
    origin = tmp_path / "origin"
    (origin / "repo-ext").mkdir(parents=True)

    def write(version, capabilities):
        (origin / "repo-ext" / "manifest.json").write_text(json.dumps({
            "id": "repo-ext", "version": version, "ext_api": 1,
            "name": "Repo Ext",
            "capabilities": {"python": "extension.py", **(capabilities or {})},
        }), encoding="utf-8")
        (origin / "repo-ext" / "extension.py").write_text(ENTRY, encoding="utf-8")

    def git(*args):
        subprocess.run(("git",) + args, cwd=origin, check=True,
                       capture_output=True)

    write(version, capabilities)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    git("add", "-A")
    git("commit", "-q", "-m", "one")

    def commit(version, capabilities=None):
        write(version, capabilities)
        git("add", "-A")
        git("commit", "-q", "-m", version)

    return origin, commit


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / "extensions"
    root.mkdir()
    monkeypatch.setenv(ext.ROOT_ENV, str(root))
    monkeypatch.delenv(ext.SAFE_MODE_ENV, raising=False)
    ext.reload()
    yield root
    ext.reload()


def _enable(ext_id):
    ext.enable_extension(ext_id)
    assert ext.is_enabled(ext_id)


def test_an_update_of_an_enabled_extension_leaves_it_disabled(
        temp_db, tmp_path, root):
    origin, commit = _repo(tmp_path)
    ext.install_extension(f"file://{origin}")
    _enable("repo-ext")
    commit("1.1.0", {"chat_state": True})

    row = ext.update_extension("repo-ext")

    assert row["updated"] is True and row["version"] == "1.1.0"
    assert row["enabled"] is False
    assert row["disabled_for_consent"] is True
    assert ext.is_enabled("repo-ext") is False
    # Not a stage of the new code is live until the host enables it again.
    assert ext.registered_stages() == []
    _enable("repo-ext")
    assert [s["full_key"] for s in ext.registered_stages()] == [
        "ext:repo-ext:pulse"]


def test_an_update_of_a_disabled_extension_says_nothing_was_withdrawn(
        temp_db, tmp_path, root):
    origin, commit = _repo(tmp_path)
    ext.install_extension(f"file://{origin}")
    commit("1.1.0")

    row = ext.update_extension("repo-ext")

    assert row["updated"] is True
    assert row["disabled_for_consent"] is False
    assert ext.is_enabled("repo-ext") is False


def test_an_install_never_inherits_a_standing_enablement(
        temp_db, tmp_path, root):
    from core.db import set_setting

    origin, _commit = _repo(tmp_path)
    # An id left in the enabled set -- a directory deleted by hand, a
    # restored settings row -- is not consent to whatever arrives under it.
    set_setting(ext.ENABLED_SETTING, json.dumps(["repo-ext"]))

    row = ext.install_extension(f"file://{origin}")

    assert row["enabled"] is False
    assert ext.is_enabled("repo-ext") is False
    assert ext.registered_stages() == []


def test_an_update_is_refused_while_a_turn_runs(temp_db, tmp_path, root):
    from agents import runtime

    origin, commit = _repo(tmp_path)
    ext.install_extension(f"file://{origin}")
    commit("1.1.0")
    runtime.ABORTS[(987656, None)] = threading.Event()
    try:
        with pytest.raises(ext.ExtensionBusy):
            ext.update_extension("repo-ext")
    finally:
        runtime.ABORTS.pop((987656, None), None)

    assert ext.installed_extensions(refresh=True)["repo-ext"].version == "1.0.0"
