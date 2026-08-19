"""Typed HTTP boundary for host authentication.

Authentication state and token persistence belong to :mod:`guest_access`;
this module owns only request validation, response status, and cookie
transport. Keeping that boundary out of ``app.py`` makes the security
contract independently testable without coupling it to story orchestration.
"""

from __future__ import annotations

import ipaddress
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from web import guest_access as guest


HOST_COOKIE = "fe_host"
GUEST_COOKIE = "fe_guest"
HOST_COOKIE_MAX_AGE = guest.HOST_SESSION_TTL
# How the host declares that this instance is published -- behind a tunnel,
# on a LAN, anywhere https is the transport. It is a DECLARATION, not a
# detection: `X-Forwarded-Proto` and friends are written by the caller, and a
# gate that reads them is a gate the caller controls. Auto-detecting would
# need a trusted-proxy list this application has no reason to own.
PUBLIC_MODE_ENV = "SONDER_PUBLIC"
_TRUTHY = ("1", "on", "true", "yes")
# Cap password length before PBKDF2 hashing to prevent CPU-exhaustion DoS.
# 1024 chars is generous for a passphrase while keeping hashing bounded.
MAX_PASSWORD_LENGTH = 1024
PUBLIC_API_PATHS = frozenset({
    "/api/join",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/ui",
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


def request_is_local(request: Request) -> bool:
    """True when the request's PEER is this machine.

    Read from the ASGI scope's `client` and nothing else. `Host`,
    `X-Forwarded-For` and `X-Forwarded-Proto` are written by the caller, so a
    gate that consults them is a gate the caller controls -- the same reason
    guest_access.py's docstring rejects header inspection as a classifier.

    A scope with no peer address, or one whose peer is not an IP address at
    all, is not a network caller: an ASGI server always reports an IP for a
    TCP peer, so the remaining cases are a unix-domain socket and an
    in-process transport. Neither can carry a stranger, and refusing them
    would only lock out callers that are already on the machine.
    """
    client = request.client
    if client is None or not client.host:
        return True
    try:
        return ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        return True


def public_mode() -> bool:
    """True when the host has declared this instance reachable over https.

    Read at call time rather than import time so a launcher, a test or a
    restart can change the answer without the module being reloaded.
    """
    return os.environ.get(PUBLIC_MODE_ENV, "").strip().lower() in _TRUTHY


def _set_host_cookie(response: JSONResponse, token: str) -> JSONResponse:
    response.set_cookie(
        HOST_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=public_mode(),
        max_age=HOST_COOKIE_MAX_AGE,
    )
    return response


def _set_guest_cookie(response: JSONResponse, token: str) -> JSONResponse:
    """The guest's half of the same transport decision.

    It lives here, next to the host cookie, because the two were written in
    two places with two literal flag lists and had already drifted apart --
    which is how a security property becomes a coincidence. `samesite` differs
    deliberately: a guest arrives by following a link from somewhere else, so
    Strict would drop the cookie on exactly the navigation that matters, while
    the host's session has no such arrival and keeps Strict.
    """
    response.set_cookie(
        GUEST_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=public_mode(),
        max_age=guest.GUEST_TOKEN_TTL,
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
def auth_setup(request: Request, credentials: AuthCredentials):
    if guest.host_account_exists():
        return JSONResponse(
            {"detail": "Account already exists"},
            status_code=409,
        )
    # An unclaimed instance has no cookie to check, which is why this path is
    # public -- so the peer address is the only evidence there is, and
    # claiming ownership of a machine is a thing you may only do FROM that
    # machine. Without this, the first client to reach a fresh install over
    # `--host 0.0.0.0` (the launcher's own usage example) owned every chat,
    # persona and lorebook in it, and could spend the host's stored provider
    # credentials. The sharper trigger is FICTION_ENGINE_RESET_HOST=1
    # re-opening setup on an instance that is already published.
    #
    # The refusal names no address: a caller learns that it may not do this,
    # not what would let it. It also does NOT consume the one-time claim --
    # a drive-by must not be able to deny the owner their own instance.
    if not request_is_local(request):
        return JSONResponse(
            {
                "detail": (
                    "First-run setup can only be completed from the "
                    "machine running Sonder."
                )
            },
            status_code=403,
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


def _rate_limited(retry_after: int) -> JSONResponse:
    return JSONResponse(
        {
            "detail": (
                "Too many failed sign-in attempts. Sign-in is paused "
                f"for {retry_after}s and then unlocks by itself."
            ),
            "retry_after_seconds": retry_after,
        },
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )


@router.post("/login")
def auth_login(credentials: AuthCredentials):
    # Refuse before the PBKDF2 verify (the CPU-bound step), and say for
    # how long: during the 2026-08 lockout incident the static "wait a
    # minute" gave no way to tell a stuck page from a waiting one. The
    # limiter counts failures only (see guest_access), so this branch is
    # only ever reached after ten wrong guesses inside a minute.
    #
    # This read is deliberately NON-consuming, and deliberately not the
    # decision either: it refuses cheaply, and the branches below it -- an
    # over-long password, an account that does not exist -- are not guesses
    # and must not spend the window. The slot is claimed atomically at the
    # one place a guess actually happens.
    retry_after = guest.login_retry_after()
    if retry_after:
        return _rate_limited(retry_after)
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
    # Naming this case leaks nothing: /api/auth/status already tells any
    # caller whether setup is required. Without the branch, a login racing
    # a host-account reset got the generic 401 -- a lie ("invalid
    # password") about a state ("there is no account") the client is
    # entitled to know, and it burned a limiter slot for a non-guess.
    if not guest.host_account_exists():
        return JSONResponse(
            {
                "detail": (
                    "No host account exists yet. Reload this page to "
                    "reach first-run setup."
                ),
                "setup_required": True,
            },
            status_code=409,
        )
    # Claim the slot BEFORE verifying, in one atomic check-and-consume. The
    # previous shape checked here and recorded after the verify, and a
    # threadpool's worth of concurrent requests all passed the check while the
    # first of them was still hashing. A correct password refunds the slot
    # below, so the window still counts failures rather than sign-ins.
    retry_after = guest.claim_login_attempt()
    if retry_after:
        return _rate_limited(retry_after)
    # Generic failure detail: don't reveal whether the username or the
    # password was the wrong half. This is deliberate and load-bearing --
    # verbosity elsewhere must never extend to splitting this message.
    if not guest.verify_host_login(
        credentials.username,
        credentials.password,
    ):
        return JSONResponse(
            {"detail": "Invalid username or password"},
            status_code=401,
        )
    guest.record_login_success()
    token = guest.create_host_session()
    return _set_host_cookie(JSONResponse({"ok": True}), token)


@router.post("/logout")
def auth_logout(request: Request):
    guest.destroy_host_session(request.cookies.get(HOST_COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(HOST_COOKIE)
    return response
