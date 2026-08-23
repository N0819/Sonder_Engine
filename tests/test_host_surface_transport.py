"""How the host surface reaches the browser: where files are read from, how
cookies are marked, and what the compressor tells caches.

Three findings that share a subject.

MASTER-013. `StaticFiles(directory="static")` runs at MODULE SCOPE and
`FileResponse("static/index.html")` at request scope, both relative to the
process's working directory. Five other modules already learned this on
2026-08-18 (see `tools/project_check.py`'s install-root check): a relative
path is a bet that the caller stood in the install root, and importing
`web.app` from anywhere else raised `RuntimeError: Directory 'static' does not
exist` before a single route could run.

MASTER-018. The host cookie sets `httponly` and `samesite` but never `secure`,
and the guest cookie was set inline in `app.py` with its own literal flags --
two writers, already drifted. `Secure` cannot be unconditional: the primary
workflow is plain http on loopback, where a Secure cookie is simply dropped.
So it is an explicit declaration by the host (`SONDER_PUBLIC=1`), never
sniffed from `X-Forwarded-Proto`, which the caller writes.

MASTER-019. The gzip middleware SKIPS adding `Vary: Accept-Encoding` when any
`Vary` already exists instead of merging into it -- a cache would then be free
to serve a compressed body to a client that cannot read one. Latent today
(nothing else emits `Vary`; there is deliberately no CORS middleware), which
makes it a trip-wire for the next middleware rather than a live hole.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import auth_routes
from web import guest_access as guest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(temp_db):
    guest._join_attempts.clear()
    guest._login_attempts.clear()
    with TestClient(app_module.app) as c:
        yield c
    guest._join_attempts.clear()
    guest._login_attempts.clear()


class TestStaticFilesAreFoundFromAnyworkingDirectory:
    def test_the_static_root_is_absolute_and_derived_from_the_install(self):
        assert app_module.STATIC_ROOT.is_absolute()
        assert app_module.STATIC_ROOT == ROOT / "static"

    def test_no_route_names_a_relative_static_path(self):
        source = (ROOT / "web/app.py").read_text(encoding="utf-8")
        assert 'directory="static"' not in source
        assert 'FileResponse("static/' not in source

    def test_importing_the_app_from_another_directory_works(self, tmp_path):
        # The defect in its own words: `import web.app` with a cwd that is not
        # the install root raised at import time, before any route existed.
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        env["ENGINE_DB"] = str(tmp_path / "scratch.db")
        result = subprocess.run(
            [sys.executable, "-c", "import web.app; print('imported')"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        assert "imported" in result.stdout

    def test_the_pages_are_served_from_the_install(self, client):
        for path in ("/", "/login", "/guest"):
            response = client.get(path)
            assert response.status_code == 200, path

    def test_the_spa_shell_revalidates_its_script_revision(self, client):
        guest.reset_host_account()
        setup = client.post(
            "/api/auth/setup",
            json={"username": "host", "password": "pw12345"},
        )
        assert setup.status_code == 200
        response = client.get("/")
        assert response.headers["cache-control"] == "no-store"
        assert "?release=alpha98-ui1" in response.text


class TestCookiesCarrySecureOnlyWhenTheHostSaysSo:
    def _account(self, client):
        guest.reset_host_account()
        response = client.post(
            "/api/auth/setup",
            json={"username": "host", "password": "pw12345"},
        )
        assert response.status_code == 200
        return response

    def test_loopback_by_default_means_no_secure_flag(self, client, monkeypatch):
        monkeypatch.delenv(auth_routes.PUBLIC_MODE_ENV, raising=False)
        header = self._account(client).headers["set-cookie"]
        assert "HttpOnly" in header
        assert "Secure" not in header

    def test_declaring_public_marks_the_host_cookie_secure(
        self, client, monkeypatch
    ):
        monkeypatch.setenv(auth_routes.PUBLIC_MODE_ENV, "1")
        header = self._account(client).headers["set-cookie"]
        assert "Secure" in header
        assert "HttpOnly" in header
        assert "SameSite=strict" in header.replace("samesite", "SameSite")

    def test_login_marks_it_too(self, client, monkeypatch):
        self._account(client)
        client.cookies.clear()
        monkeypatch.setenv(auth_routes.PUBLIC_MODE_ENV, "1")
        response = client.post(
            "/api/auth/login",
            json={"username": "host", "password": "pw12345"},
        )
        assert response.status_code == 200
        assert "Secure" in response.headers["set-cookie"]

    def test_the_guest_cookie_is_written_by_the_same_helper(self):
        # The two cookies had two writers and had already drifted -- one
        # gained a flag the other did not. There is one writer now, in the
        # module that owns cookie transport.
        source = (ROOT / "web/app.py").read_text(encoding="utf-8")
        assert "set_cookie(" not in source
        assert callable(auth_routes._set_guest_cookie)

    def test_the_guest_cookie_follows_the_declaration(self, monkeypatch):
        from fastapi.responses import JSONResponse

        monkeypatch.setenv(auth_routes.PUBLIC_MODE_ENV, "1")
        public = auth_routes._set_guest_cookie(JSONResponse({}), "tok")
        monkeypatch.delenv(auth_routes.PUBLIC_MODE_ENV)
        local = auth_routes._set_guest_cookie(JSONResponse({}), "tok")

        assert "Secure" in public.headers["set-cookie"]
        assert "Secure" not in local.headers["set-cookie"]
        # A guest link is followed from another site's page, so Lax stays.
        for response in (public, local):
            header = response.headers["set-cookie"].lower()
            assert "samesite=lax" in header
            assert "httponly" in header

    @pytest.mark.parametrize("value", ["1", "on", "true", "YES"])
    def test_the_declaration_reads_the_usual_truthy_words(
        self, monkeypatch, value
    ):
        monkeypatch.setenv(auth_routes.PUBLIC_MODE_ENV, value)
        assert auth_routes.public_mode() is True

    @pytest.mark.parametrize("value", ["", "0", "off", "no", "false"])
    def test_anything_else_is_the_local_default(self, monkeypatch, value):
        monkeypatch.setenv(auth_routes.PUBLIC_MODE_ENV, value)
        assert auth_routes.public_mode() is False


class TestVaryIsMergedNotSkipped:
    def _headers(self, existing):
        message = {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")] + existing,
        }
        started = app_module._SelectiveGZipResponder._gzip_start(message)
        return {
            key.decode().lower(): value.decode()
            for key, value in started["headers"]
        }

    def test_an_unvaried_response_gains_the_header(self):
        assert self._headers([])["vary"] == "Accept-Encoding"

    def test_an_existing_vary_is_extended(self):
        vary = self._headers([(b"vary", b"Origin")])["vary"]
        tokens = [token.strip() for token in vary.split(",")]
        assert "Origin" in tokens
        assert "Accept-Encoding" in tokens

    def test_a_vary_that_already_names_it_is_left_alone(self):
        vary = self._headers([(b"vary", b"Accept-Encoding, Origin")])["vary"]
        tokens = [token.strip() for token in vary.split(",")]
        assert tokens.count("Accept-Encoding") == 1

    def test_the_match_is_case_insensitive(self):
        vary = self._headers([(b"Vary", b"accept-encoding")])["vary"]
        assert vary.lower().count("accept-encoding") == 1

    def test_a_wildcard_vary_is_not_extended(self):
        # `Vary: *` already means "cache nothing by these rules"; appending to
        # it says less than it does.
        assert self._headers([(b"vary", b"*")])["vary"] == "*"
