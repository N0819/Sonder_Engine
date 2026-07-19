"""Host/guest access control for the "invite a friend" remote-join feature.

Security model: by default (no tunnel, no invite ever created) the app
behaves exactly as it always has -- no auth, single trusted local user.
The moment a request needs to be told apart from a forged one (a guest
joining over a public tunnel, or any request hitting /api/* once host
auth has been bootstrapped), classification is deny-by-default:

  - The host authenticates once via a secret bootstrapped through a URL
    parameter (printed to the server's own console output -- never sent
    over any network response), then holds a long-lived, HttpOnly,
    SameSite=Strict cookie. SameSite=Strict means a forged cross-site
    request (a malicious page's blind POST to 127.0.0.1) never carries
    this cookie, which is what actually stops that attack -- not the
    absence of some header, which is spoofable/fragile and was explicitly
    rejected as a classifier (see project discussion).
  - A guest redeems a single-use, 30-minute, rate-limited join code for a
    persona-scoped, HttpOnly, SameSite=Lax session token with a hard
    24-hour expiry regardless of revocation.
  - Both the host secret and every issued code/token are stored and
    compared only as SHA-256 hashes, never plaintext -- a local SQLite
    file can be read by anything else with filesystem access on the host
    machine.
"""

from __future__ import annotations

import hashlib
import secrets
import time

from db import q, qi, get_setting, set_setting

HOST_SECRET_SETTING = "host_secret"  # legacy plaintext slot; migrated to hash on startup
HOST_SECRET_HASH_SETTING = "host_secret_hash"
GUEST_TOKEN_TTL = 60 * 60 * 24  # 24h hard backstop, independent of revoke
JOIN_CODE_TTL = 60 * 30  # 30 minutes
# No 0/1/O/I/L: avoids characters a guest could misread when copying a
# code by hand. 8 chars over this 32-symbol alphabet is 40 bits of
# entropy -- combined with the 30-minute expiry, single-use consumption,
# and the rate limit below, brute-forcing a live code is infeasible.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_host_secret() -> str | None:
    """Ensure a host secret exists, returning its PLAINTEXT only when THIS
    call mints a fresh one. The plaintext is never persisted (only its
    SHA-256 hash is), so it can be shown exactly once -- printed to the
    server's own console. Returns None when a secret was already configured
    on a prior run: there is nothing to display because the plaintext is
    unrecoverable by design (a stolen engine.db must not yield a working
    host credential). A legacy plaintext secret from before hashing-at-rest
    is upgraded in place -- hashed, plaintext cleared -- and since the host
    cookie carries that same plaintext, verify_host_secret keeps accepting
    it, so no already-authorized host is logged out by the upgrade.
    """
    if get_setting(HOST_SECRET_HASH_SETTING):
        return None
    legacy = get_setting(HOST_SECRET_SETTING)
    if legacy:
        set_setting(HOST_SECRET_HASH_SETTING, _hash(legacy))
        set_setting(HOST_SECRET_SETTING, "")
        return None
    return _mint_host_secret()


def reset_host_secret() -> str:
    """Mint a fresh host secret, invalidating any prior one (and the host
    cookie derived from it). Returns the new plaintext to display once.
    The escape hatch for a host who cleared cookies or lost the one-time
    link -- there is no other way back in, since nothing stores plaintext.
    """
    return _mint_host_secret()


def _mint_host_secret() -> str:
    secret = secrets.token_urlsafe(32)
    set_setting(HOST_SECRET_HASH_SETTING, _hash(secret))
    set_setting(HOST_SECRET_SETTING, "")
    return secret


def verify_host_secret(candidate: str | None) -> bool:
    stored = get_setting(HOST_SECRET_HASH_SETTING)
    if not stored or not candidate:
        return False
    return secrets.compare_digest(stored, _hash(candidate))


def generate_join_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def create_guest_invite(chat_id: int, persona_id: int) -> dict:
    code = generate_join_code()
    now = time.time()
    grant_id = qi(
        "INSERT INTO guest_grants(chat_id,persona_id,code_hash,code_expires,created) "
        "VALUES(?,?,?,?,?)",
        (chat_id, persona_id, _hash(code), now + JOIN_CODE_TTL, now),
    )
    return {"grant_id": grant_id, "code": code, "expires": now + JOIN_CODE_TTL}


# /api/join needs its own throttle independent of any single code's
# lifecycle -- the attack is "try many codes fast," not "try one code
# many times" (a code is already single-use). A simple in-process sliding
# window is enough for a local single-user app; no external infra.
_join_attempts: list[float] = []
_JOIN_WINDOW_SECONDS = 60
_JOIN_WINDOW_MAX = 10


def _join_rate_limited() -> bool:
    now = time.time()
    while _join_attempts and _join_attempts[0] < now - _JOIN_WINDOW_SECONDS:
        _join_attempts.pop(0)
    if len(_join_attempts) >= _JOIN_WINDOW_MAX:
        return True
    _join_attempts.append(now)
    return False


def redeem_code(code: str) -> dict | None:
    """Exchange a join code for a session token. Returns None on any
    failure (unknown code, expired, revoked, already redeemed, or rate
    limited) without distinguishing which, so the response doesn't leak
    which codes exist or why one didn't work."""
    if _join_rate_limited() or not code:
        return None

    now = time.time()
    grant = q(
        "SELECT * FROM guest_grants WHERE code_hash=? AND revoked=0 "
        "AND redeemed_at IS NULL",
        (_hash(code),),
        one=True,
    )
    if not grant or grant["code_expires"] < now:
        return None

    token = secrets.token_urlsafe(32)
    qi(
        "UPDATE guest_grants SET redeemed_at=?, token_hash=?, token_expires=? "
        "WHERE id=?",
        (now, _hash(token), now + GUEST_TOKEN_TTL, grant["id"]),
    )
    return {
        "token": token,
        "chat_id": grant["chat_id"],
        "persona_id": grant["persona_id"],
    }


def verify_guest_token(token: str | None) -> dict | None:
    if not token:
        return None
    now = time.time()
    grant = q(
        "SELECT * FROM guest_grants WHERE token_hash=? AND revoked=0",
        (_hash(token),),
        one=True,
    )
    if not grant or not grant["token_expires"] or grant["token_expires"] < now:
        return None
    return {
        "grant_id": grant["id"],
        "chat_id": grant["chat_id"],
        "persona_id": grant["persona_id"],
    }


def revoke_grant(chat_id: int, grant_id: int) -> bool:
    row = q(
        "SELECT id FROM guest_grants WHERE id=? AND chat_id=?",
        (grant_id, chat_id),
        one=True,
    )
    if not row:
        return False
    qi("UPDATE guest_grants SET revoked=1 WHERE id=?", (grant_id,))
    return True


def list_grants(chat_id: int) -> list[dict]:
    rows = q(
        "SELECT g.*, p.name AS persona_name FROM guest_grants g "
        "JOIN personas p ON p.id=g.persona_id "
        "WHERE g.chat_id=? ORDER BY g.created DESC",
        (chat_id,),
    )
    now = time.time()
    out = []
    for r in rows:
        d = dict(r)
        d.pop("code_hash", None)
        d.pop("token_hash", None)
        if d["revoked"]:
            status = "revoked"
        elif d["redeemed_at"] and d["token_expires"] and d["token_expires"] > now:
            status = "active"
        elif d["redeemed_at"]:
            status = "expired"
        elif d["code_expires"] < now:
            status = "code_expired"
        else:
            status = "pending"
        d["status"] = status
        out.append(d)
    return out
