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
