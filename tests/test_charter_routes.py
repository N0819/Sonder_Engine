"""The structured Charter authoring surface is reachable and era-scoped."""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from web import app as app_module


@pytest.fixture
def chat_id(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Charter routes", "", time.time()),
    )
    temp_db.wset(cid, "scene", {
        "rooms": {"engine_room": {"name": "Engine Room", "adjacent": []}},
        "positions": {}, "entities": {}, "attire": {}, "overlays": {},
    })
    return cid


def test_round_trip_normalizes_and_reports_authoring_warnings(
        temp_db, chat_id):
    body = app_module.charters_put(chat_id, {
        "ship": {
            "key": "ship",
            "upkeeps": {"air": {"place": "engine_room"}},
            "posts": {},
            "bodies": {},
        },
    })

    assert set(body["charters"]["items"]) == {"ship"}
    assert any("no posts" in warning for warning in body["warnings"])
    assert any("served by no post" in warning for warning in body["warnings"])
    assert app_module.charters_get(chat_id)["charters"] == body["charters"]

    routes = {(route.path, method)
              for route in app_module.app.routes
              for method in (getattr(route, "methods", None) or ())}
    assert ("/api/chats/{cid}/charters", "GET") in routes
    assert ("/api/chats/{cid}/charters", "PUT") in routes


def test_missing_chat_is_not_created_by_the_authoring_route(temp_db):
    with pytest.raises(HTTPException) as get_error:
        app_module.charters_get(999999)
    with pytest.raises(HTTPException) as put_error:
        app_module.charters_put(999999, {})
    assert get_error.value.status_code == 404
    assert put_error.value.status_code == 404
