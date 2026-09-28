"""The decision model is chosen on the models panel, beneath embeddings.

The owner, 2026-09-27: "add field to select decision models", "decision model
should be bellow embeding, should not have a reasoning or formating setting.
also don't know why embedding has a reasoning setting." The seam
(`llm/decisions.py`) always read `jev_provider` and `jev_model`, and nothing
in the app could set either. Neither it nor embeddings sends a reasoning
effort or a response format, so neither row offers one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llm import decisions

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_JS = (ROOT / "static" / "js" / "settings.js").read_text(encoding="utf-8")


def _provider_row(db, name="OpenRouter", kind="openrouter", key="k"):
    return db.qi("INSERT INTO providers(name,kind,base_url,api_key) VALUES(?,?,?,?)",
                  (name, kind, "https://openrouter.ai/api/v1", key))


def test_unchosen_it_shows_what_the_seam_will_use(temp_db):
    other = _provider_row(temp_db, name="Local", kind="generic")
    routed = _provider_row(temp_db)
    shown = decisions.setting()
    assert shown["provider"] is None and shown["model"] == ""
    assert shown["effective_provider"] == routed != other
    assert shown["default_model"] == decisions.DEFAULT_MODEL
    assert shown["configured"] is True


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient

    from web import app as app_module
    from web import guest_access as guest
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup", json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()


def test_the_panel_saves_it_and_the_seam_reads_it(client, temp_db):
    _provider_row(temp_db)
    chosen = _provider_row(temp_db, name="Other route")
    saved = client.put("/api/decision_model",
                       json={"provider": chosen, "model": "typesafe/jev-2"}).json()
    assert saved["decision_model"]["provider"] == chosen
    assert saved["decision_model"]["model"] == "typesafe/jev-2"
    assert decisions._provider()["id"] == chosen
    assert temp_db.get_setting("jev_model") == "typesafe/jev-2"
    assert client.get("/api/bootstrap").json()["decision_model"]["model"] == "typesafe/jev-2"


def test_clearing_it_returns_the_seam_to_its_defaults(client, temp_db):
    routed = _provider_row(temp_db)
    chosen = _provider_row(temp_db, name="Other route")
    client.put("/api/decision_model", json={"provider": chosen, "model": "m"})
    cleared = client.put("/api/decision_model", json={}).json()["decision_model"]
    assert cleared["provider"] is None and cleared["model"] == ""
    assert decisions._provider()["id"] == routed


def test_an_unknown_provider_is_refused(client):
    assert client.put("/api/decision_model",
                      json={"provider": 999, "model": "m"}).status_code == 404


def _function_body(source, opening):
    start = source.index(opening)
    depth, i = 0, source.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[start:i + 1]
        i += 1


def test_the_row_sits_beneath_embeddings_with_no_reasoning_or_format():
    # Embeddings sorts first, and the decision row is appended right after it.
    assert re.search(r"embeddings:\s*-2,\s*default:\s*-1", SETTINGS_JS)
    assert "if (isEmbeddings) b.append(decisionModelRow());" in SETTINGS_JS
    row = _function_body(SETTINGS_JS, "const decisionModelRow = () =>")
    assert "effort" not in row.casefold() and "format" not in row.casefold()
    assert "/api/decision_model" in SETTINGS_JS


def test_embeddings_offers_no_reasoning_or_format():
    """Its request carries the model and the text, nothing else
    (`providers._embed_request`)."""
    assert "if (!isEmbeddings) roleInputs[role].effort = effortSel;" in SETTINGS_JS
    assert "if (!isEmbeddings) roleInputs[role].format = formatSel;" in SETTINGS_JS
    assert "isEmbeddings ? null : effortSel" in SETTINGS_JS
    assert "isEmbeddings ? null : formatSel" in SETTINGS_JS


def test_the_encoder_row_says_not_to_use_a_reasoning_model():
    from llm.providers import ROLES
    assert "encoder" in ROLES and "director_specialist" not in ROLES
    assert 'role === "encoder"' in SETTINGS_JS
    assert SETTINGS_JS.count("Use a model that does not reason.") >= 2  # the row and the help


def test_the_untouched_row_pins_nothing():
    """Saved only when edited: an untouched row must not write today's default
    model id into the host's settings."""
    assert "if (decisionEdited && decisionCombo)" in SETTINGS_JS
