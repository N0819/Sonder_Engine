"""Host/guest access control for the "invite a friend" remote-join feature.

Security model: by default (no tunnel, no invite ever created) the app
behaves exactly as it always has -- no auth, single trusted local user.
The moment a request needs to be told apart from a forged one (a guest
joining over a public tunnel, or any request hitting /api/* once host
auth has been bootstrapped), classification is deny-by-default:

  - The host signs in with a username + password (created once on a
    first-run setup page), receiving a 30-day session token held in a
    long-lived, HttpOnly, SameSite=Strict cookie. SameSite=Strict means
    a forged cross-site request (a malicious page's blind POST to
    127.0.0.1) never carries this cookie, which is what actually stops
    that attack -- not the absence of some header, which is
    spoofable/fragile and was explicitly rejected as a classifier (see
    project discussion).
  - A guest redeems a single-use, 30-minute, rate-limited join code for a
    persona-scoped, HttpOnly, SameSite=Lax session token with a hard
    24-hour expiry regardless of revocation.
  - The host password is stored only as a salted PBKDF2 hash, and every
    issued session token/join code only as a SHA-256 hash, never
    plaintext -- a local SQLite file can be read by anything else with
    filesystem access on the host machine.
"""

from __future__ import annotations

import hashlib
import secrets
import time

from db import q, qi, get_setting, set_setting

HOST_USERNAME_SETTING = "host_username"
HOST_PW_HASH_SETTING = "host_pw_hash"
HOST_PW_SALT_SETTING = "host_pw_salt"
HOST_SESSION_TTL = 60 * 60 * 24 * 30  # 30 days
_PBKDF2_ITERS = 200_000
GUEST_TOKEN_TTL = 60 * 60 * 24  # 24h hard backstop, independent of revoke
JOIN_CODE_TTL = 60 * 30  # 30 minutes
# No 0/1/O/I/L: avoids characters a guest could misread when copying a
# code by hand. 8 chars over this 32-symbol alphabet is 40 bits of
# entropy -- combined with the 30-minute expiry, single-use consumption,
# and the rate limit below, brute-forcing a live code is infeasible.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def host_account_exists() -> bool:
    return bool(get_setting(HOST_USERNAME_SETTING))


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERS
    ).hex()


def create_host_account(username: str, password: str) -> str | None:
    """One-time host account creation (the first-run setup page). Refuses
    to overwrite an existing account -- reset_host_account() is the only
    way to start over. Only a salted PBKDF2 hash of the password is
    stored, never the plaintext. Returns a fresh session token on
    success (so setup signs the browser in immediately), None on refusal.
    """
    if host_account_exists():
        return None
    username = username.strip()
    if not username or not password:
        return None
    salt = secrets.token_bytes(16).hex()
    set_setting(HOST_USERNAME_SETTING, username)
    set_setting(HOST_PW_SALT_SETTING, salt)
    set_setting(HOST_PW_HASH_SETTING, _hash_password(password, salt))
    return create_host_session()


def verify_host_login(username: str, password: str) -> bool:
    """Check a username+password pair against the stored account.
    compare_digest on both fields keeps the comparison constant-time-ish
    so a response-timing probe can't confirm the username separately
    from the password."""
    stored_username = get_setting(HOST_USERNAME_SETTING)
    stored_salt = get_setting(HOST_PW_SALT_SETTING)
    stored_hash = get_setting(HOST_PW_HASH_SETTING)
    if not stored_username or not stored_salt or not stored_hash:
        return False
    username_ok = secrets.compare_digest(stored_username, username.strip())
    password_ok = secrets.compare_digest(
        stored_hash, _hash_password(password, stored_salt)
    )
    return username_ok and password_ok


def create_host_session() -> str:
    """Mint a 30-day session token, storing only its SHA-256 hash."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    qi(
        "INSERT INTO host_sessions(token_hash,created,expires) VALUES(?,?,?)",
        (_hash(token), now, now + HOST_SESSION_TTL),
    )
    return token


def verify_host_session(token: str | None) -> bool:
    if not token:
        return False
    row = q(
        "SELECT id FROM host_sessions WHERE token_hash=? AND expires > ?",
        (_hash(token), time.time()),
        one=True,
    )
    return bool(row)


def destroy_host_session(token: str | None) -> None:
    if token:
        qi("DELETE FROM host_sessions WHERE token_hash=?", (_hash(token),))


def reset_host_account() -> None:
    """Wipe the host account and every session -- the escape hatch for a
    lost password (FICTION_ENGINE_RESET_HOST=1 at startup). The next
    visit to /login sees the first-run setup page again."""
    set_setting(HOST_USERNAME_SETTING, "")
    set_setting(HOST_PW_HASH_SETTING, "")
    set_setting(HOST_PW_SALT_SETTING, "")
    qi("DELETE FROM host_sessions")


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


# /api/auth/login gets the same treatment as /api/join and for the same
# reason -- the attack is "try many passwords fast." Separate window so a
# burst of join attempts can't lock the host out (or vice versa).
_login_attempts: list[float] = []
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_WINDOW_MAX = 10


def login_rate_limited() -> bool:
    now = time.time()
    while _login_attempts and _login_attempts[0] < now - _LOGIN_WINDOW_SECONDS:
        _login_attempts.pop(0)
    if len(_login_attempts) >= _LOGIN_WINDOW_MAX:
        return True
    _login_attempts.append(now)
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
