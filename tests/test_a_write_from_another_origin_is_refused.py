"""A page on another origin cannot drive a write as the host.

SameSite is per SITE (scheme and host), not per origin: `127.0.0.1:5173` and
`127.0.0.1:8008` are the same site, so the host's Strict cookie rides along
on a request a page on another port of the same host sends. A type-less
`Blob` body sends no Content-Type, so there is no preflight, and FastAPI parses
the body as JSON anyway -- a blind `POST /api/extensions/install` then
`.../enable` ran an extension's Python in the engine process (audit
2026-11-01, web_routes_extensions F1). `access_control` checked only the
cookie.

The rule: a write (`POST`/`PUT`/`PATCH`/`DELETE`) under `/api/` is refused
when the browser says it came from anywhere but this origin. `Sec-Fetch-Site`
is set by the browser and cannot be forged by a page; where it is absent (an
older browser), an `Origin` naming another host:port is refused. A caller
that sends neither -- curl, a script, the test client -- is not a browser
page and is unchanged. Reads are unchanged: without CORS headers a cross-
origin page cannot read the answer anyway.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def host(temp_db):
    from web import app as app_module
    from web import guest_access as guest

    guest._login_attempts.clear()
    guest.reset_host_account()
    guest.create_host_account("host", "pw12345")
    client = TestClient(app_module.app)  # no lifespan: no startup threads
    client.cookies.set("fe_host", guest.create_host_session())
    return client


def _delete_missing_turn(client, **headers):
    """A write that is harmless when it lands: the route answers 404."""
    return client.delete("/api/turns/999999", headers=headers)


@pytest.mark.parametrize("site", ["same-origin", "none"])
def test_a_write_from_this_origin_reaches_the_route(host, site):
    assert _delete_missing_turn(host, **{"Sec-Fetch-Site": site}).status_code == 404


@pytest.mark.parametrize("site", ["same-site", "cross-site"])
def test_a_write_from_another_origin_is_refused(host, site):
    r = _delete_missing_turn(host, **{"Sec-Fetch-Site": site})
    assert r.status_code == 403


def test_a_caller_that_says_nothing_is_not_a_browser_page(host):
    assert _delete_missing_turn(host).status_code == 404


def test_without_fetch_metadata_the_origin_must_be_this_one(host):
    assert _delete_missing_turn(host, Origin="http://testserver").status_code == 404
    assert _delete_missing_turn(host, Origin="http://testserver:5173").status_code == 403
    assert _delete_missing_turn(host, Origin="http://127.0.0.1:8008").status_code == 403
    assert _delete_missing_turn(host, Origin="null").status_code == 403


def test_a_browser_page_on_this_origin_is_never_refused_for_its_origin(host):
    """`Sec-Fetch-Site` decides when the browser sends it, whatever a proxy
    did to the Host header."""
    r = _delete_missing_turn(host, **{"Sec-Fetch-Site": "same-origin",
                                      "Origin": "https://published.example"})
    assert r.status_code == 404


def test_a_read_is_not_refused_for_its_site(host):
    r = host.get("/api/auth/status", headers={"Sec-Fetch-Site": "same-site"})
    assert r.status_code == 200


def test_the_public_and_guest_writes_are_held_to_the_same_rule(temp_db):
    """`/api/join` and `/api/auth/*` take no cookie, and the guest page posts
    from this origin with `fetch` -- no cross-origin form posts them."""
    from web import app as app_module
    from web import guest_access as guest

    guest._join_attempts.clear()
    client = TestClient(app_module.app)
    refused = client.post("/api/join", json={"code": "WRONGCODE"},
                          headers={"Sec-Fetch-Site": "cross-site"})
    assert refused.status_code == 403
    reached = client.post("/api/join", json={"code": "WRONGCODE"},
                          headers={"Sec-Fetch-Site": "same-origin"})
    assert reached.status_code == 400
    guest._join_attempts.clear()
