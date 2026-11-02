"""Changing the extension set while a beat runs answers 409, the conflict it is.

`extension_runtime` refuses enable, disable, install, update and remove with
`ExtensionBusy` while any run slot is held, because a turn is planned with
the extensions live when it began and a stage that vanishes under it killed
it ("unknown step ext:...", web_routes_extensions F12, L2's fix). The routes
answered that refusal as whatever their generic `ExtensionError` handler
said -- 404 for enable and remove, 400 for install and update -- and
`extension_disable` had no handler at all, so its refusal was a 500. 409 is
the answer every chat route gives a host who edits under a running turn.
"""
from __future__ import annotations

import threading

import pytest
from fastapi import HTTPException


@pytest.fixture
def held_slot():
    from agents.runtime import ABORTS
    key = (987654, None)
    ABORTS[key] = threading.Event()
    try:
        yield
    finally:
        ABORTS.pop(key, None)


def test_a_disable_under_a_running_beat_is_a_conflict(temp_db, held_slot):
    from web import app
    with pytest.raises(HTTPException) as refused:
        app.extension_disable("demo-ext")
    assert refused.value.status_code == 409


def test_an_install_under_a_running_beat_is_a_conflict(temp_db, held_slot):
    from web import app
    with pytest.raises(HTTPException) as refused:
        app.extension_install({"source": "https://example.invalid/never-fetched.git"})
    assert refused.value.status_code == 409


@pytest.mark.parametrize("route, runtime_name, args", [
    ("extension_enable", "enable_extension", ("demo-ext",)),
    ("extension_update", "update_extension", ("demo-ext",)),
    ("extension_remove", "remove_extension", ("demo-ext",)),
])
def test_every_change_answers_the_refusal_as_a_conflict(monkeypatch, route, runtime_name, args):
    import extension_runtime
    from web import app

    def busy(*_a, **_k):
        raise extension_runtime.ExtensionBusy("A turn is running.")

    monkeypatch.setattr(extension_runtime, runtime_name, busy)
    with pytest.raises(HTTPException) as refused:
        getattr(app, route)(*args)
    assert refused.value.status_code == 409
    assert "A turn is running." in refused.value.detail


@pytest.mark.parametrize("route, runtime_name, status", [
    ("extension_enable", "enable_extension", 404),
    ("extension_update", "update_extension", 400),
    ("extension_remove", "remove_extension", 404),
])
def test_any_other_refusal_keeps_its_status(monkeypatch, route, runtime_name, status):
    import extension_runtime
    from web import app

    def refuse(*_a, **_k):
        raise extension_runtime.ExtensionError("'demo-ext' is not installed")

    monkeypatch.setattr(extension_runtime, runtime_name, refuse)
    with pytest.raises(HTTPException) as refused:
        getattr(app, route)("demo-ext")
    assert refused.value.status_code == status
