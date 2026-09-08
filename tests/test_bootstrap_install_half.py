"""`/api/bootstrap` sends the install half once per version, not per boot().

C22 (review 2026-09-07). `boot()` re-runs on every import, save, provider edit
and NSFW toggle -- 61 call sites across `static/js` -- and each run downloaded
the whole payload again. Measured on the owner's 307-body town database:
2,002,515 bytes per run, 767,608 of them (38.3%) the same bytes every time --
`default_prompts` (520 KB) and the UI catalog (256 KB).

The half is versioned by a DIGEST OF ITS OWN CONTENT, which is the only part
of this worth a test: a cache whose key is derived from the thing cached
cannot go stale, and a cache whose key is a rule someone maintains can. So
what is pinned here is the invalidation, from both sides -- the half's version
does not move when the host writes a story, and it does move the moment
anything in the half does.

The other thing pinned here is the ENCODING. The full path hand-serializes
where the `install_unchanged` path is still serialized by FastAPI, so one
route could answer in two encodings: a bare `json.dumps` escapes every
non-ASCII character, which cost +23,192 bytes on the English payload and
+49.6% on `language_packs/ja/ui.json` before it was caught.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest


@pytest.fixture
def host(temp_db):
    guest._join_attempts.clear()
    guest._login_attempts.clear()
    with TestClient(app_module.app) as client:
        guest.reset_host_account()
        assert client.post(
            "/api/auth/setup",
            json={"username": "host", "password": "pw12345"},
        ).status_code == 200
        yield client
    guest._join_attempts.clear()
    guest._login_attempts.clear()


def _full(client):
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    return response.json()


def test_the_named_half_is_actually_in_the_payload(temp_db):
    """A key renamed in the payload and not here would silently stop being
    cached, and nothing else would notice."""
    payload = app_module.bootstrap()
    missing = sorted(app_module._INSTALL_BLOCK_KEYS.difference(payload))
    assert missing == []


def test_a_caller_that_asks_for_nothing_gets_what_it_always_got(host, temp_db):
    """Every non-browser caller omits `known_install`, and must not notice."""
    payload = app_module.bootstrap()
    full = _full(host)
    assert full.pop("install_version")
    assert sorted(full.pop("install_keys")) == sorted(app_module._INSTALL_BLOCK_KEYS)
    assert full == payload


def test_a_known_version_omits_exactly_the_half_and_the_client_rebuilds_it(host):
    full = _full(host)
    version = full["install_version"]

    second = host.get("/api/bootstrap", params={"known_install": version}).json()
    assert second["install_unchanged"] is True
    assert second["install_version"] == version
    omitted = set(full) - set(second)
    assert omitted == set(app_module._INSTALL_BLOCK_KEYS)

    # What `boot()` does with it: merge the cached half back and the answer is
    # the one the full response carried, key for key.
    merged = dict(second)
    for key in full["install_keys"]:
        merged[key] = full[key]
    merged.pop("install_unchanged")
    merged["install_keys"] = full["install_keys"]
    assert json.dumps(merged, sort_keys=True) == json.dumps(full, sort_keys=True)


def test_a_stale_version_is_handed_the_whole_half_back(host):
    stale = host.get("/api/bootstrap",
                     params={"known_install": "0000000000000000"}).json()
    assert "install_unchanged" not in stale
    assert set(app_module._INSTALL_BLOCK_KEYS).issubset(stale)


def test_writing_a_story_does_not_move_the_half(host, temp_db):
    """The half is what the INSTALL ships. Saving a character is the commonest
    reason `boot()` re-runs, and it must not cost the catalog again."""
    before = _full(host)["install_version"]
    temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
               ("A Newcomer", json.dumps({"identity": {"name": "A Newcomer"}}),
                time.time()))
    after = _full(host)
    assert after["install_version"] == before
    assert any(row["name"] == "A Newcomer" for row in after["characters"])


def test_changing_the_half_moves_its_version(host, monkeypatch):
    """The other side of the same rule: nothing has to remember to bump a
    number, because the number is the content."""
    before = _full(host)
    edited = dict(before["default_prompts"])
    edited["narrator"] = edited.get("narrator", "") + "\nOne more line."
    monkeypatch.setitem(app_module.DEFAULT_PROMPTS, "narrator", edited["narrator"])

    after = _full(host)
    assert after["install_version"] != before["install_version"]
    # And a client holding the old version is sent the new half, not told it
    # is unchanged.
    fresh = host.get("/api/bootstrap",
                     params={"known_install": before["install_version"]}).json()
    assert "install_unchanged" not in fresh
    assert fresh["default_prompts"]["narrator"] == edited["narrator"]


def test_the_spliced_body_is_one_json_object():
    """The full response is two already-serialized halves spliced, so the half
    is serialized once (to be digested) rather than twice. The splice is the
    only hand-written JSON in the route."""
    merged = app_module._json_object_merge(b'{"a":1}', b'{"b":[2,3]}')
    assert json.loads(merged) == {"a": 1, "b": [2, 3]}
    assert json.loads(app_module._json_object_merge(b'{"a":1}', b"{}")) == {"a": 1}
    assert json.loads(app_module._json_object_merge(b"{}", b"{}")) == {}


def test_the_response_is_encoded_the_way_fastapi_encodes_everything_else(temp_db):
    """The full path hand-serializes; the `install_unchanged` path does not.
    A bare `json.dumps` there would escape every non-ASCII character, so one
    route would answer in two encodings and a Japanese install would pay
    +49.6% on its UI catalog. Pinned against starlette's own renderer."""
    from starlette.responses import JSONResponse

    payload = app_module.bootstrap()
    install_json, _version, rest = app_module._bootstrap_split(payload)
    body = app_module._json_object_merge(
        install_json, json.dumps(rest, **app_module._JSON_WIRE).encode("utf-8"))

    # The spliced order: the half's keys sorted, then everything else.
    whole = {key: payload[key] for key in sorted(payload)
             if key in app_module._INSTALL_BLOCK_KEYS}
    whole.update(rest)
    assert body == JSONResponse(whole).render(whole)

    # And the NaN half of the same parity: FastAPI refuses it rather than
    # emitting a bare `NaN` literal no JSON parser owes us.
    with pytest.raises(ValueError):
        json.dumps({"x": float("nan")}, **app_module._JSON_WIRE)
