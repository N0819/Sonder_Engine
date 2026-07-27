"""Typed HTTP boundary for host authentication.

Authentication state and token persistence belong to :mod:`guest_access`;
this module owns only request validation, response status, and cookie
transport. Keeping that boundary out of ``app.py`` makes the security
contract independently testable without coupling it to story orchestration.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import guest_access as guest


HOST_COOKIE = "fe_host"
GUEST_COOKIE = "fe_guest"
HOST_COOKIE_MAX_AGE = guest.HOST_SESSION_TTL
# Cap password length before PBKDF2 hashing to prevent CPU-exhaustion DoS.
# 1024 chars is generous for a passphrase while keeping hashing bounded.
MAX_PASSWORD_LENGTH = 1024
PUBLIC_API_PATHS = frozenset({
    "/api/join",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/logout",
})
GUEST_ALLOWED_API_PATHS = frozenset({
    "/api/guest/state",
    "/api/guest/input",
})


class AuthCredentials(BaseModel):
    """Wire contract shared by first-run setup and later sign-in."""

    username: str = ""
    password: str = ""


router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _set_host_cookie(response: JSONResponse, token: str) -> JSONResponse:
    response.set_cookie(
        HOST_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        max_age=HOST_COOKIE_MAX_AGE,
    )
    return response


@router.get("/status")
def auth_status(request: Request):
    return {
        "setup_required": not guest.host_account_exists(),
        "authenticated": guest.verify_host_session(
            request.cookies.get(HOST_COOKIE)
        ),
    }


@router.post("/setup")
def auth_setup(credentials: AuthCredentials):
    if guest.host_account_exists():
        return JSONResponse(
            {"detail": "Account already exists"},
            status_code=409,
        )
    if not credentials.username.strip():
        return JSONResponse(
            {"detail": "Username is required"},
            status_code=400,
        )
    if not credentials.password:
        return JSONResponse(
            {"detail": "Password is required"},
            status_code=400,
        )
    if len(credentials.password) > MAX_PASSWORD_LENGTH:
        return JSONResponse(
            {
                "detail": (
                    "Password must be at most "
                    f"{MAX_PASSWORD_LENGTH} characters"
                )
            },
            status_code=400,
        )
    token = guest.create_host_account(
        credentials.username,
        credentials.password,
    )
    if token is None:
        return JSONResponse(
            {"detail": "Account already exists"},
            status_code=409,
        )
    return _set_host_cookie(JSONResponse({"ok": True}), token)


@router.post("/login")
def auth_login(credentials: AuthCredentials):
    if guest.login_rate_limited():
        return JSONResponse(
            {"detail": "Too many attempts, wait a minute"},
            status_code=429,
        )
    if len(credentials.password) > MAX_PASSWORD_LENGTH:
        return JSONResponse(
            {
                "detail": (
                    "Password must be at most "
                    f"{MAX_PASSWORD_LENGTH} characters"
                )
            },
            status_code=400,
        )
    # Generic failure detail: don't reveal whether the username or the
    # password was the wrong half.
    if not guest.verify_host_login(
        credentials.username,
        credentials.password,
    ):
        return JSONResponse(
            {"detail": "Invalid username or password"},
            status_code=401,
        )
    token = guest.create_host_session()
    return _set_host_cookie(JSONResponse({"ok": True}), token)


@router.post("/logout")
def auth_logout(request: Request):
    guest.destroy_host_session(request.cookies.get(HOST_COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(HOST_COOKIE)
    return response
