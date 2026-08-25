"""A private helper between a decorator and its handler steals the route.

Python applies a decorator to the NEXT definition, whatever that is. A helper
inserted below `@app.post("/api/steps/{sid}/edit")` and above `step_edit` was
therefore registered as the endpoint, and `step_edit` became unreachable code
that nothing routed to and every test still imported happily.

What the host saw: every attempt to edit any pipeline step failed. The helper
takes `s`, which FastAPI reads as a required QUERY parameter, so each edit
returned 422 with a validation array -- and the frontend rendered that array
as "[object Object]", because `new Error(<array>)` stringifies that way. One
mis-wired route and one unrendered error shape, and between them the host got
an opaque refusal with no way to tell what was wrong.

Nothing here is about the perception step or any story: it is a route binding
and an error-message shape.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post("/api/auth/setup",
                          json={"username": "host", "password": "pw12345"})
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


@pytest.fixture
def step(temp_db, client):
    """One chat, one turn, one step with an active variant."""
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Editable", "", time.time()))
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "look around", time.time()))
    sid = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
        (tid, "perception_act", "Perception", 3))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) "
        "VALUES(?,?,?,1)", (sid, json.dumps({"views": {}}), time.time()))
    return {"chat_id": cid, "turn_id": tid, "step_id": sid}


class TestEveryStepRouteReachesItsOwnHandler:
    def test_the_edit_route_is_bound_to_step_edit(self):
        """The binding itself, stated where a reader can see it: a helper
        that drifts between decorator and handler silently takes the route."""
        bound = {r.path: r.endpoint.__name__
                 for r in app_module.app.routes
                 if "/api/steps/" in getattr(r, "path", "")}
        assert bound["/api/steps/{sid}/edit"] == "step_edit"
        assert bound["/api/steps/{sid}/activate"] == "step_activate"
        assert bound["/api/steps/{sid}/reroll"] == "step_reroll"

    def test_no_step_route_is_bound_to_a_private_helper(self):
        """The general rule rather than the one name that broke: a route
        handler is public API and a leading underscore says it is not."""
        for route in app_module.app.routes:
            name = getattr(getattr(route, "endpoint", None), "__name__", "")
            if "/api/steps/" in getattr(route, "path", ""):
                assert not name.startswith("_"), (route.path, name)


class TestEditingAStepWorks:
    def test_a_valid_edit_is_accepted(self, client, step):
        response = client.post(f"/api/steps/{step['step_id']}/edit",
                               json={"content": {"views": {"player": "hi"}}})
        assert response.status_code == 200, response.text
        assert "variant_id" in response.json()

    def test_the_edit_becomes_the_active_variant(self, temp_db, client, step):
        client.post(f"/api/steps/{step['step_id']}/edit",
                    json={"content": {"views": {"player": "hi"}}})
        from core.db import q

        rows = q("SELECT content, active FROM variants WHERE step_id=? "
                 "ORDER BY id", (step["step_id"],))
        assert [r["active"] for r in rows] == [0, 1]
        assert json.loads(rows[-1]["content"]) == {"views": {"player": "hi"}}

    def test_downstream_steps_are_marked_stale(self, temp_db, client, step):
        """The reason an edit is worth anything: what came after it is no
        longer derived from what is now there."""
        from core.db import q

        later = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
            (step["turn_id"], "narrator", "Narrator", 7))
        client.post(f"/api/steps/{step['step_id']}/edit",
                    json={"content": {"views": {}}})
        assert q("SELECT stale FROM steps WHERE id=?", (later,),
                 one=True)["stale"] == 1


class TestTheErrorTheHostActuallySaw:
    def test_a_validation_failure_is_a_structured_detail(self, client, step):
        """`detail` is an ARRAY of objects here, not a sentence -- which is
        what the frontend has to render rather than concatenate."""
        response = client.post(f"/api/steps/{step['step_id']}/edit",
                               content=b"not json",
                               headers={"Content-Type": "application/json"})
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)

    def test_the_frontend_renders_that_shape(self):
        """A guard on the JS, since no browser test runs in this tier: the
        helper must exist and must be what both error paths call."""
        source = open("static/js/utils.js", encoding="utf-8").read()
        assert "function errorDetailText(" in source
        # Both `api` and `streamPost` build a message from `detail`.
        assert source.count("errorDetailText(") >= 3
        assert "parsed.detail\n" not in source
