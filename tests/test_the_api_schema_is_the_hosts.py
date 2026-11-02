"""FastAPI's own schema and docs pages are the host's, behind the host cookie.

`FastAPI()` registers `/openapi.json`, `/docs`, `/docs/oauth2-redirect` and
`/redoc` by default, and `access_control` gated `/api/*` only -- so any peer
that could reach the port read the full inventory of 214 routes and their
parameters with no cookie at all (audit 2026-11-01, web_app F16). The startup
banner warns about LAN binds and tunnels; those are exactly the peers.

Auth is a path rule, so the second test is the guard on the rule itself: a
route registered outside `/api/` is public unless it is named here.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

DOCS = ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")

#: Served to anyone, deliberately: the shell, the two standalone pages, and
#: the static bundle they load. Every other route lives under /api/ or is
#: one of FastAPI's pages above.
PUBLIC_PAGES = frozenset({"/", "/login", "/guest", "/static"})


@pytest.mark.parametrize("path", DOCS)
def test_no_cookie_reads_no_schema(temp_db, path):
    from web import app as app_module

    assert TestClient(app_module.app).get(path).status_code == 401


def test_the_host_still_reads_it(temp_db):
    from web import app as app_module
    from web import guest_access as guest

    guest.reset_host_account()
    guest.create_host_account("host", "pw12345")
    client = TestClient(app_module.app)
    client.cookies.set("fe_host", guest.create_host_session())
    r = client.get("/openapi.json")
    assert r.status_code == 200 and "/api/chats" in r.json()["paths"]
    assert client.get("/docs").status_code == 200


def test_every_route_outside_api_is_named_public_or_host_only():
    from web import app as app_module

    outside = {getattr(route, "path", "") for route in app_module.app.routes} - {""}
    outside = {path for path in outside if not path.startswith("/api/")}
    assert outside <= PUBLIC_PAGES | set(DOCS), sorted(outside - PUBLIC_PAGES - set(DOCS))
