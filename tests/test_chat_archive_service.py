"""The extracted archive service keeps legacy and HTTP compatibility."""

import pytest
from fastapi import HTTPException

import app
from chat_archive import ChatArchiveData, ChatArchiveService


def test_archive_routes_and_app_compatibility_aliases():
    routes = [
        route
        for route in app.app.routes
        if getattr(route, "path", None)
        in {"/api/chats/{cid}/export", "/api/chats/import"}
    ]

    assert [(route.path, route.methods) for route in routes] == [
        ("/api/chats/{cid}/export", {"GET"}),
        ("/api/chats/import", {"POST"}),
    ]
    assert [route.unique_id for route in routes] == [
        "chat_export_api_chats__cid__export_get",
        "chat_import_api_chats_import_post",
    ]
    assert isinstance(app._chat_archive_service, ChatArchiveService)
    assert app.chat_export == app._chat_archive_service.export_chat
    assert app.chat_import == app._chat_archive_service.import_chat


def test_archive_model_retains_extensions_and_normalizes_legacy_nulls():
    archive = ChatArchiveData(
        version="2",
        chat={"name": "Legacy"},
        frames=None,
        resources=None,
        future_extension={"kept": True},
    )

    assert archive.version == 2
    assert archive.frames == []
    assert archive.resources == {}
    assert archive.future_extension == {"kept": True}


def test_legacy_archive_with_null_collections_imports(temp_db):
    imported = app.chat_import(
        {
            "data": {
                "version": 1,
                "chat": {
                    "name": "Legacy",
                    "persona_id": None,
                    "scenario": "Old archive",
                },
                "frames": None,
                "turns": None,
                "world": None,
                "resources": None,
            }
        }
    )

    assert imported["name"] == "Legacy (import)"
    assert imported["scenario"] == "Old archive"


def test_invalid_data_member_keeps_original_400_contract():
    with pytest.raises(HTTPException) as exc:
        app.chat_import({"data": []})

    assert exc.value.status_code == 400
    assert exc.value.detail == "No chat data provided"


class TestTheGateIsNotStricterThanTheCodeBehindIt:
    """`import_chat` reads `data.get("resources") or {}` and
    `dict(data.get("world") or {})`, but the model refused `world: []`
    outright and rejected the whole archive with a 400. Pydantic 1 hid that
    by coercing an empty list to an empty mapping for free, so the
    intolerance only appeared on 2.x — the same hand-edited or third-party
    archive importing on one machine and not another."""

    @staticmethod
    def _validate(payload):
        from chat_archive import ChatArchiveData
        validate = getattr(ChatArchiveData, "model_validate", None)
        model = validate(payload) if validate else ChatArchiveData.parse_obj(payload)
        dump = getattr(model, "model_dump", None)
        return dump() if dump else model.dict()

    def test_an_empty_map_spelled_as_a_list(self):
        assert self._validate({"chat": {"id": 1}, "world": []})["world"] == {}

    def test_an_empty_map_spelled_as_a_string(self):
        assert self._validate({"chat": {"id": 1}, "resources": ""})["resources"] == {}

    def test_a_version_written_as_a_float(self):
        assert self._validate({"chat": {"id": 1}, "version": 1.5})["version"] == 1

    def test_legacy_nulls_still_become_empty_collections(self):
        data = self._validate({"chat": {"id": 1}, "frames": None, "world": None})
        assert data["frames"] == [] and data["world"] == {}

    def test_forward_compatible_keys_still_survive(self):
        assert self._validate({"chat": {"id": 1}, "kept": [1, 2]})["kept"] == [1, 2]

    def test_a_missing_chat_is_still_a_hard_failure(self):
        import pydantic, pytest
        with pytest.raises(pydantic.ValidationError):
            self._validate({"world": {}})
