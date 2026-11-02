"""The live extension set changes only between turns.

Audit 2026-11-01 (web_routes_extensions F12): a turn's plan is spliced once,
when it starts (`agents/runtime.py` `_extension_splices`), and the handler is
looked up when the step runs -- `compute_step` raises `unknown step <key>`
for a key with none. Disabling an extension deregistered its handlers at
once, and installing, updating or removing ANY extension called `reload()`,
which deregistered every one of them; a turn that reached an `ext:` stage in
that gap died with a RuntimeError, although the stage was `on_error="warn"`
("a flaky extension degrades to a visible note, it does not kill a beat").
None of the routes held an idle guard. The rule is the chat routes' own --
the run registry `agents.runtime.ABORTS` -- read for every chat at once,
because the extension set is the whole process's.
"""

from __future__ import annotations

import threading

import pytest

import extension_runtime

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _write_extension, ext_root,
)


@pytest.fixture
def staged(ext_root):
    _write_extension(ext_root, "staged", {
        "id": "staged", "version": "1.0.0", "ext_api": 1, "name": "Staged",
        "capabilities": {"python": "extension.py"},
    }, {"extension.py":
        "def register(api):\n"
        "    api.add_stage('pulse', anchor='after:director_resolve',\n"
        "                  handler=lambda view, api, nonce: {'pulse': 1})\n"})
    _enable("staged")
    return ext_root


@pytest.fixture
def a_turn_is_running():
    from agents import runtime

    key = (987654, None)
    runtime.ABORTS[key] = threading.Event()
    yield key
    runtime.ABORTS.pop(key, None)


def test_disabling_under_a_running_turn_is_refused_and_the_stage_still_runs(
        temp_db, staged, a_turn_is_running):
    from agents.runtime import compute_step

    with pytest.raises(extension_runtime.ExtensionBusy, match="turn is running"):
        extension_runtime.disable_extension("staged")

    assert extension_runtime.is_enabled("staged")
    assert compute_step("ext:staged:pulse", _StubCtx(), 0) == {"pulse": 1}


def test_every_change_to_the_live_set_is_refused_while_a_turn_runs(
        temp_db, staged, a_turn_is_running, tmp_path):
    other = tmp_path / "elsewhere" / "other-ext"
    other.mkdir(parents=True)
    (other / "manifest.json").write_text(
        '{"id": "other-ext", "version": "1", "ext_api": 1}', encoding="utf-8")

    for change in (lambda: extension_runtime.enable_extension("staged"),
                   lambda: extension_runtime.disable_extension("staged"),
                   lambda: extension_runtime.install_extension(str(other)),
                   lambda: extension_runtime.remove_extension("staged")):
        with pytest.raises(extension_runtime.ExtensionBusy):
            change()

    assert "other-ext" not in extension_runtime.installed_extensions(refresh=True)
    assert (staged / "staged").is_dir()
    assert [s["full_key"] for s in extension_runtime.registered_stages()] == [
        "ext:staged:pulse"]


def test_the_refusal_is_an_extension_error_naming_an_off_screen_beat(
        temp_db, staged):
    from agents import runtime

    event = threading.Event()
    event.offscreen_beat = True
    runtime.ABORTS[(987655, 3)] = event
    try:
        with pytest.raises(extension_runtime.ExtensionError,
                           match="off-screen beat"):
            extension_runtime.disable_extension("staged")
    finally:
        runtime.ABORTS.pop((987655, 3), None)


def test_with_no_turn_running_the_change_goes_through(temp_db, staged):
    extension_runtime.disable_extension("staged")

    assert not extension_runtime.is_enabled("staged")
    assert extension_runtime.registered_stages() == []
