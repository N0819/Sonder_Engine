"""Tests for provider model-list badging."""

from providers import list_models

def _prov(base_url="https://nano-gpt.com/api/v1", kind="nanogpt"):
    return {"base_url": base_url, "kind": kind, "api_key": "test-key"}

def test_list_models_respects_nested_subscription_included_flag(monkeypatch):
    # nanogpt reports subscription eligibility as a nested object, e.g.
    # {"included": false, "note": "Not included in subscription"}. A dict
    # is truthy in Python regardless of its "included" value, so a naive
    # `m.get("subscription")` check marks every model "included in
    # subscription" merely because the key exists -- including models
    # that actually 403 with model_not_included at request time.
    payload = {
        "data": [
            {
                "id": "included-model",
                "pricing": {"prompt": 0.4, "completion": 1.8},
                "subscription": {"included": True, "note": "Included in subscription"},
            },
            {
                "id": "excluded-model",
                "pricing": {"prompt": 0.4, "completion": 1.8},
                "subscription": {"included": False, "note": "Not included in subscription"},
            },
        ],
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    import requests as requests_module

    monkeypatch.setattr(
        requests_module.Session, "get", lambda self, *a, **k: FakeResponse()
    )

    out = {m["id"]: m for m in list_models(_prov())}

    assert out["included-model"]["included"] is True
    assert out["included-model"]["badge"] == "included in subscription"
    assert out["excluded-model"]["included"] is False
    assert out["excluded-model"]["badge"] == "pay-per-use"
