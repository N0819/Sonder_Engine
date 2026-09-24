"""A contract nobody can switch to is a contract nobody can play.

The prose contract (docs/design/DESIGN_PROSE_CONTRACT.md) was selected by the
setting `director_contract` alone, with no control anywhere in the app -- the
owner, 2026-09-24: "I want to test the new contract in engine but there seems
no way to use it". Settings now carries a select; these pin that it writes
the key the engine reads, and shows the state the engine is in.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException


def test_the_route_writes_what_the_engine_reads(temp_db):
    from agents import director_prose
    from web import app as app_module

    assert director_prose.enabled() is False                      # the default
    assert app_module.set_director_contract({"contract": "prose"}) == {
        "contract": "prose"}
    assert director_prose.enabled() is True
    assert app_module.set_director_contract({"contract": "causal"}) == {
        "contract": "causal"}
    assert director_prose.enabled() is False


def test_boot_reports_it_so_the_select_shows_its_state(temp_db):
    from web import app as app_module

    assert app_module.bootstrap()["director_contract"] == "causal"
    app_module.set_director_contract({"contract": "prose"})
    assert app_module.bootstrap()["director_contract"] == "prose"


def test_an_unknown_contract_is_refused_and_changes_nothing(temp_db):
    from agents import director_prose
    from web import app as app_module

    app_module.set_director_contract({"contract": "prose"})
    with pytest.raises(HTTPException) as caught:
        app_module.set_director_contract({"contract": "monolith"})
    assert caught.value.status_code == 400
    assert director_prose.enabled() is True


def test_the_settings_page_offers_it():
    source = Path("static/js/settings.js").read_text(encoding="utf-8")
    assert '"/api/director_contract"' in source
    assert "S.boot.director_contract" in source
