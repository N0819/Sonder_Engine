"""The forgot-password hatch must announce itself on every startup it fires.

FICTION_ENGINE_RESET_HOST wipes the host account at startup, and an
environment variable cannot un-set itself: left in a launch script, it
re-wiped the account the operator had just re-created, on the very next
restart, with nothing in the startup output saying the hatch was still
armed. The lockout looked like an auth bug instead of a stale variable.
These tests pin that the wipe is loudly announced, names the variable to
unset, and says nothing when the hatch is not armed.
"""

from __future__ import annotations

import pytest

from web import app as app_module
from web import guest_access as guest


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("FICTION_ENGINE_RESET_HOST", raising=False)
    # This module tests startup messaging, not asynchronous memory-bank
    # reconciliation; lifespan coverage owns that worker separately.
    monkeypatch.setattr(app_module, "_reconcile_embedding_bank", lambda: None)
    return monkeypatch


def test_armed_hatch_wipes_and_announces_the_repeat(
    temp_db, clean_env, capsys
):
    guest.reset_host_account()
    assert guest.create_host_account("host", "pw12345")
    clean_env.setenv("FICTION_ENGINE_RESET_HOST", "1")

    app_module._startup_engine()

    assert not guest.host_account_exists()
    out = capsys.readouterr().out
    assert "FICTION_ENGINE_RESET_HOST is set" in out
    assert "wiped" in out
    # The half that was missing when this bit: the operator must be told
    # the wipe recurs until the variable is unset, or the account they are
    # about to re-create dies on the next restart.
    assert "EVERY restart" in out
    assert "unset FICTION_ENGINE_RESET_HOST" in out


def test_armed_hatch_with_no_account_still_announces(
    temp_db, clean_env, capsys
):
    guest.reset_host_account()
    clean_env.setenv("FICTION_ENGINE_RESET_HOST", "1")

    app_module._startup_engine()

    out = capsys.readouterr().out
    assert "FICTION_ENGINE_RESET_HOST is set" in out
    assert "unset FICTION_ENGINE_RESET_HOST" in out


def test_unarmed_startup_does_not_mention_a_wipe(temp_db, clean_env, capsys):
    guest.reset_host_account()
    assert guest.create_host_account("host", "pw12345")

    app_module._startup_engine()

    assert guest.host_account_exists()
    out = capsys.readouterr().out
    assert "is set" not in out
    assert "wiped" not in out
