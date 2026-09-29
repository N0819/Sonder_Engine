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


SELF_HOSTED = "http://127.0.0.1:8192/v1/systemone"


class _Answer:
    status_code = 200
    text = ""

    def json(self):
        return {"model": "Winnow-12B", "usage": {"input_tokens": 9},
                "answers": {"q": {"type": "noul", "noul": 0.9}}}


def _capture_posts(monkeypatch):
    import requests
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append({"url": url, "headers": dict(headers or {})})
        return _Answer()
    monkeypatch.setattr(requests, "post", post)
    return sent


def test_a_self_hosted_url_is_asked_with_no_key_at_all(temp_db, monkeypatch):
    """The owner's own Jev-compatible server (2026-09-28): it needs no key, and
    the OpenRouter row's key must not ride along to a host that is not
    OpenRouter just because no provider was chosen."""
    _provider_row(temp_db, key="openrouter-secret")
    temp_db.set_setting("jev_url", SELF_HOSTED)
    sent = _capture_posts(monkeypatch)
    assert decisions.configured() is True
    assert decisions.decide("state", {"q": {"type": "noul", "instructions": "?"}}) == {
        "q": {"type": "noul", "noul": 0.9}}
    assert sent[0]["url"] == SELF_HOSTED
    assert "Authorization" not in sent[0]["headers"]
    shown = decisions.setting()
    assert shown["url"] == SELF_HOSTED and shown["effective_provider"] is None


def test_a_chosen_provider_still_sends_its_own_key_to_the_url(temp_db, monkeypatch):
    chosen = _provider_row(temp_db, name="Hosted Jev", kind="generic", key="its-own")
    temp_db.set_setting("jev_provider", str(chosen))
    temp_db.set_setting("jev_url", SELF_HOSTED)
    sent = _capture_posts(monkeypatch)
    decisions.decide("state", {"q": {"type": "noul", "instructions": "?"}})
    assert sent[0]["headers"]["Authorization"] == "Bearer its-own"


def test_a_one_alternative_choice_is_answered_here_and_never_sent(temp_db, monkeypatch):
    """Winnow-12B refuses a choice with one alternative (400, "Questions
    require 2–64 alternatives") and the refusal sank a whole read-back; Jev
    1.13 answers it with certainty. Answered locally in Jev's own shape."""
    temp_db.set_setting("jev_url", SELF_HOSTED)
    sent = []
    import requests

    def post(url, headers=None, json=None, timeout=None):
        sent.append(json["questions"])
        return _Answer()
    monkeypatch.setattr(requests, "post", post)
    only = {"type": "choice", "instructions": "?", "criteria": {"situational": "none of them"}}
    got = decisions.decide("state", {"serves": only, "q": {"type": "noul", "instructions": "?"}})
    assert set(sent[0]) == {"q"}
    assert got["serves"] == {"type": "choice", "choice": "situational",
                             "probabilities": {"situational": 1.0}, "confidence": 1.0}
    assert got["q"]["noul"] == 0.9
    sent.clear()
    assert decisions.decide("state", {"serves": only})["serves"]["choice"] == "situational"
    assert sent == []


def test_without_a_url_a_keyless_provider_is_still_refused(temp_db, monkeypatch):
    chosen = _provider_row(temp_db, name="Local", kind="generic", key="")
    temp_db.set_setting("jev_provider", str(chosen))
    sent = _capture_posts(monkeypatch)
    assert decisions.configured() is False
    with pytest.raises(decisions.DecisionError):
        decisions.decide("state", {"q": {"type": "noul", "instructions": "?"}})
    assert sent == []


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
