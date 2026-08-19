"""Tests for provider model-list badging."""

from llm import providers
from llm.providers import list_models

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


def test_list_models_accepts_top_level_list_response(monkeypatch):
    _fake_get(monkeypatch, [
        {"id": "model-b"},
        {"id": "model-a"},
    ])

    out = list_models(_prov())

    assert [model["id"] for model in out] == ["model-a", "model-b"]


def test_list_models_tolerates_malformed_scalar_response(monkeypatch):
    _fake_get(monkeypatch, None)

    assert list_models(_prov()) == []


# ---- Image catalogue (scene backdrops) ----
# Shapes here are trimmed copies of a REAL nano-gpt /api/models/image response.

_IMAGE_PAYLOAD = {
    "models": {
        "image": {
            "flux-2-flash": {
                "name": "Flux 2 Flash", "provider": "other",
                "model": "flux-2-flash", "iconLabel": "text-to-image",
                "cost": {"1024x1024": 0.0075, "1536x1024": 0.011},
                "subscription": {"included": False},
                "resolutions": [{"value": "1024x1024", "comment": "Square"},
                                {"value": "1536x1024", "comment": "Landscape"}],
            },
            "fal-ai/bernini-r/edit-image": {
                "name": "Bernini R Edit Image", "iconLabel": "image-to-image",
                "cost": {"1024x1024": 0.03}, "subscription": {"included": False},
                "resolutions": [{"value": "1024x1024"}],
            },
            "some/both-model": {
                "name": "Both", "iconLabel": "both",
                "cost": {"auto": 0.04}, "subscription": {"included": True},
                "resolutions": [],
            },
        }
    },
    "meta": {"generatedAt": "2026-07-25T14:25:51.199Z"},
}


def _fake_get(monkeypatch, payload):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    import requests as requests_module
    monkeypatch.setattr(requests_module.Session, "get",
                        lambda self, *a, **k: FakeResponse())


def test_image_catalogue_is_unwrapped_two_levels(monkeypatch):
    """The catalogue is {"models": {"image": {...}}}. Stopping at "models" --
    which one level of unwrapping does -- yields a single row called "image",
    i.e. a picker that finds nothing you can search for."""
    from llm.providers import list_image_models
    _fake_get(monkeypatch, _IMAGE_PAYLOAD)
    out = {m["id"]: m for m in list_image_models(_prov())}
    assert "flux-2-flash" in out
    assert "image" not in out


def test_edit_only_models_are_not_offered(monkeypatch):
    """A backdrop is generated from text alone, so an image-to-image model can
    only fail at generation time. "both" stays."""
    from llm.providers import list_image_models
    _fake_get(monkeypatch, _IMAGE_PAYLOAD)
    ids = {m["id"] for m in list_image_models(_prov())}
    assert "fal-ai/bernini-r/edit-image" not in ids
    assert "some/both-model" in ids


def test_image_rows_carry_price_and_usable_sizes(monkeypatch):
    """Sizes are per-model and not always WxH, so the picker has to offer the
    model's own list rather than assume the engine default works."""
    from llm.providers import list_image_models
    _fake_get(monkeypatch, _IMAGE_PAYLOAD)
    out = {m["id"]: m for m in list_image_models(_prov())}
    assert out["flux-2-flash"]["sizes"] == ["1024x1024", "1536x1024"]
    assert out["flux-2-flash"]["badge"] == "from $0.0075"
    assert out["some/both-model"]["badge"] == "included in subscription"
    assert out["some/both-model"]["included"] is True


def test_image_catalogue_tolerates_a_flat_list(monkeypatch):
    """Nothing standardises this endpoint, so a plain list must still work."""
    from llm.providers import list_image_models
    _fake_get(monkeypatch, {"data": [{"id": "dall-e-3"}, "gpt-image-1"]})
    assert {m["id"] for m in list_image_models(_prov())} == {"dall-e-3", "gpt-image-1"}


def test_image_models_url_climbs_out_of_the_v1_base():
    """Generation is under /v1; the catalogue is a sibling of it."""
    from llm.providers import image_models_url
    assert (image_models_url("https://nano-gpt.com/api/v1")
            == "https://nano-gpt.com/api/models/image")
    assert (image_models_url("https://nano-gpt.com/api/v1/")
            == "https://nano-gpt.com/api/models/image")


class TestASettingThatCannotReachTheProvider:
    """The native Anthropic branch builds its body and RETURNS before
    `_apply_reasoning_effort` and `_apply_json_mode` run, so both are
    OpenAI-path only. Neither is a small setting -- reasoning effort is a
    first-class per-role control in the settings panel, and the JSON grammar
    is worth a measured narrator 2/5 -> 5/5 valid and character 53.4s/2029
    tokens -> 15.3s/587 -- and configured against a native Anthropic
    connection they change nothing, silently. The host reads the panel, sees
    the value they set, and attributes the difference to the model.

    Sending them is a request-shape decision the owner has not taken.
    Announcing that a set dial is inert is not.
    """

    def _anthropic(self, monkeypatch):
        providers._UNSENT_ON_ANTHROPIC.clear()
        prov = {"kind": "anthropic", "base_url": "https://example.invalid",
                "api_key": "k", "name": "claude-direct"}
        monkeypatch.setattr(
            providers, "resolve_role", lambda role: (prov, "some-model", {}))
        monkeypatch.setattr(
            providers, "_merge_samplers",
            lambda cfg, sampler, temperature: (0.5, {}))
        monkeypatch.setattr(providers, "_anthropic_system",
                            lambda system, prov: system)

        class _Response:
            status_code = 200

            @staticmethod
            def json():
                return {"content": [{"text": "{}"}], "usage": {}}

        class _Session:
            def post(self, *a, **k):
                return _Response()

        monkeypatch.setattr(providers, "_session", lambda: _Session())
        return prov

    def test_a_configured_effort_that_cannot_be_sent_is_reported(
            self, monkeypatch, caplog):
        import logging

        self._anthropic(monkeypatch)
        monkeypatch.setattr(providers, "reasoning_effort_for",
                            lambda role: "high")
        with caplog.at_level(logging.WARNING, logger="fiction_engine"):
            providers._chat_complete_once(
                "narrator", "sys", "user", temperature=0.5, json_mode=True,
                max_tokens=100, sampler=None)
        said = [r.getMessage() for r in caplog.records
                if "native Anthropic" in r.getMessage()]
        assert said, [r.getMessage() for r in caplog.records]
        assert "reasoning effort" in said[0]

    def test_a_grammar_that_cannot_be_sent_is_reported_once(
            self, monkeypatch, caplog):
        import logging

        self._anthropic(monkeypatch)
        monkeypatch.setattr(providers, "reasoning_effort_for", lambda role: "")
        with caplog.at_level(logging.WARNING, logger="fiction_engine"):
            for _ in range(3):
                providers._chat_complete_once(
                    "narrator", "sys", "user", temperature=0.5,
                    json_mode=True, max_tokens=100, sampler=None,
                    json_schema={"type": "object"})
        said = [r.getMessage() for r in caplog.records
                if "native Anthropic" in r.getMessage()]
        assert len(said) == 1, said
        assert "JSON grammar" in said[0]

    def test_nothing_is_said_when_nothing_was_configured(
            self, monkeypatch, caplog):
        import logging

        self._anthropic(monkeypatch)
        monkeypatch.setattr(providers, "reasoning_effort_for", lambda role: "")
        with caplog.at_level(logging.WARNING, logger="fiction_engine"):
            providers._chat_complete_once(
                "narrator", "sys", "user", temperature=0.5, json_mode=True,
                max_tokens=100, sampler=None)
        assert not [r for r in caplog.records
                    if "native Anthropic" in r.getMessage()]
