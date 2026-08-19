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
import math
import secrets
import threading
import time

from core.db import q, qi, get_setting, set_setting, transaction

HOST_USERNAME_SETTING = "host_username"
HOST_PW_HASH_SETTING = "host_pw_hash"
HOST_PW_SALT_SETTING = "host_pw_salt"
HOST_SESSION_TTL = 60 * 60 * 24 * 30  # 30 days

# The work factor is DATA, not code. Storing a bare digest froze it: raising
# the number invalidated every existing password at once, because nothing at
# rest recorded which number had produced the stored bytes. So a stored
# password is a self-describing record --
# `pbkdf2_sha256$<iters>$<salt hex>$<digest hex>` -- and raising the constant
# below is now a one-line change that costs nobody their sign-in: the next
# successful login re-writes that host's record at the new factor.
#
# 600_000 is OWASP's current figure for PBKDF2-HMAC-SHA256. Measured on the
# development machine, 2026-08-19: 0.27s per verify against 0.09s at the old
# 200_000. That is invisible to a person signing in and it is the point of the
# parameter; it is visible in the test suite, which signs in some sixty times.
_PW_SCHEME = "pbkdf2_sha256"
_PBKDF2_ITERS = 600_000
# Bounds on what a stored record may ask for. The lower one refuses a record
# weakened by a hand-edited settings row; the upper one refuses one that would
# hang the process on every login attempt -- a settings file is not a trusted
# input just because it is local.
_PBKDF2_MIN_ITERS = 100_000
_PBKDF2_MAX_ITERS = 5_000_000
# What a bare-hex record (everything written before 2026-08-19) was made with.
_LEGACY_PBKDF2_ITERS = 200_000
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


def _pbkdf2(password: str, salt: str, iters: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iters
    ).hex()


def _hash_password(password: str, salt: str, iters: int | None = None) -> str:
    """Encode a password as a self-describing verifier record.

    The scheme and work factor travel WITH the digest, so a future change to
    either is readable by the code that has to verify against what is already
    stored. `salt` stays a separate argument (and a separate setting) because
    it is per-account material the caller generates, not a parameter.
    """
    iters = _PBKDF2_ITERS if iters is None else int(iters)
    return f"{_PW_SCHEME}${iters}${salt}${_pbkdf2(password, salt, iters)}"


def _parse_password_record(stored: str, legacy_salt: str) -> tuple | None:
    """`(iters, salt, digest)` for a stored verifier, or None if unusable.

    A record with no `$` is a bare digest from before the format existed:
    those were all made at 200_000 with the salt in its own setting, so they
    verify unchanged and are upgraded on the next successful login rather than
    being invalidated.
    """
    if not stored:
        return None
    if "$" not in stored:
        if not legacy_salt:
            return None
        try:
            bytes.fromhex(legacy_salt)
        except ValueError:
            return None
        return (_LEGACY_PBKDF2_ITERS, legacy_salt, stored)
    parts = stored.split("$")
    if len(parts) != 4:
        return None
    scheme, raw_iters, salt, digest = parts
    if scheme != _PW_SCHEME or not salt or not digest:
        return None
    try:
        iters = int(raw_iters)
        bytes.fromhex(salt)
    except ValueError:
        return None
    if not _PBKDF2_MIN_ITERS <= iters <= _PBKDF2_MAX_ITERS:
        return None
    return (iters, salt, digest)


def create_host_account(username: str, password: str) -> str | None:
    """One-time host account creation (the first-run setup page). Refuses
    to overwrite an existing account -- reset_host_account() is the only
    way to start over. Only a salted PBKDF2 hash of the password is
    stored, never the plaintext. Returns a fresh session token on
    success (so setup signs the browser in immediately), None on refusal.
    """
    username = username.strip()
    if not username or not password:
        return None
    salt = secrets.token_bytes(16).hex()
    # Account identity, verifier material, and the initial session are one
    # security boundary. A crash after writing only the username previously
    # made host_account_exists() true while leaving an account that could
    # never authenticate. BEGIN IMMEDIATE also closes the two-setup-request
    # race: the second request re-checks existence after the first commits.
    with transaction():
        if host_account_exists():
            return None
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
    if not stored_username or not stored_hash:
        return False
    record = _parse_password_record(stored_hash, stored_salt)
    if record is None:
        return False
    iters, salt, digest = record
    # compare_digest raises TypeError on a str containing non-ASCII code
    # points (it is ASCII-only for the str overload). A host who chose a
    # username with any non-ASCII character (accents, non-Latin scripts,
    # an emoji) would then 500 on every login attempt -- a permanently
    # broken, unrecoverable account. Compare the UTF-8 byte encodings
    # instead, which is well-defined for any string and equally
    # constant-time. stored_hash / _hash_password are hex ASCII, but encode
    # both sides uniformly for the same guarantee.
    username_ok = secrets.compare_digest(
        stored_username.encode("utf-8"), username.strip().encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        digest.encode("utf-8"),
        _pbkdf2(password, salt, iters).encode("utf-8"),
    )
    if username_ok and password_ok:
        # Only here: re-deriving a verifier needs the plaintext, and this is
        # the one moment the plaintext is both present and proven. A record
        # already at the current scheme and factor rewrites nothing.
        if iters != _PBKDF2_ITERS or "$" not in stored_hash:
            _rewrite_password_record(password)
    return username_ok and password_ok


def _rewrite_password_record(password: str) -> None:
    """Re-salt and re-hash a verified password at the current work factor.

    Failure here is not a failed login: the caller has already proven the
    password, and an unwritten upgrade only means the record is upgraded on
    the next sign-in instead. Swallowing the error keeps a locked database or
    a read-only file from turning a correct password into a rejected one.
    """
    salt = secrets.token_bytes(16).hex()
    try:
        with transaction():
            set_setting(HOST_PW_SALT_SETTING, salt)
            set_setting(HOST_PW_HASH_SETTING, _hash_password(password, salt))
    except Exception:  # pragma: no cover - defensive, see docstring
        pass


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
    with transaction():
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
#
# Both ledgers below are plain module lists read and written from REQUEST
# threads. `/api/join` and `/api/auth/login` are both `def`, not `async def`,
# so FastAPI runs them in the anyio worker threadpool -- several at once, by
# construction. Without the guard the window was not a limit at all: every
# thread read `len(...) < MAX` before any of them appended, so the budget was
# spent as many times over as there were threads, and the prune loop could
# `pop(0)` an index another thread had just cleared. One global lock, held
# only across a list prune and an append, costs nothing measurable and makes
# check-and-consume a single decision.
#
# The limit stays GLOBAL rather than per-caller. This is a single-user
# application: there is exactly one account to guess at, so per-IP buckets
# would hand an attacker with a rotating source address an unbounded budget
# while giving the one legitimate host nothing.
_RATE_GUARD = threading.Lock()

_join_attempts: list[float] = []
_JOIN_WINDOW_SECONDS = 60
_JOIN_WINDOW_MAX = 10


def _prune(attempts: list[float], window: int, now: float) -> None:
    """Drop timestamps older than the window. Call with _RATE_GUARD held."""
    cutoff = now - window
    while attempts and attempts[0] < cutoff:
        attempts.pop(0)


def _join_rate_limited() -> bool:
    with _RATE_GUARD:
        now = time.time()
        _prune(_join_attempts, _JOIN_WINDOW_SECONDS, now)
        if len(_join_attempts) >= _JOIN_WINDOW_MAX:
            return True
        _join_attempts.append(now)
        return False


# /api/auth/login gets a limiter for the same reason as /api/join -- the
# attack is "try many passwords fast." Separate window so a burst of join
# attempts can't lock the host out (or vice versa). Unlike the join
# window, this one counts FAILURES only: the limiter used to consume a
# slot on every call, success included, so ten successful sign-ins in a
# minute -- or the 2026-08 incident, where a password manager's auto-
# submitted stale credentials burned all ten slots in seconds -- locked
# the legitimate host out of a single-user app. A successful login is
# proof the host is present, so it also clears the ledger; an attacker
# cannot reach that clear without already having the password.
_login_attempts: list[float] = []  # timestamps of FAILED attempts only
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_WINDOW_MAX = 10


def _login_retry_after_locked(now: float) -> int:
    """Seconds until the window has room again. Call with _RATE_GUARD held."""
    if len(_login_attempts) < _LOGIN_WINDOW_MAX:
        return 0
    oldest_counted = _login_attempts[-_LOGIN_WINDOW_MAX]
    remaining = oldest_counted + _LOGIN_WINDOW_SECONDS - now
    return max(1, math.ceil(remaining))


def login_retry_after() -> int:
    """Whole seconds until the next login attempt will be evaluated, or 0
    when not limited. Non-consuming: checking never spends budget, only
    claim_login_attempt() does. The number exists so the login page can
    show a real countdown instead of a static "wait a minute" -- during
    the incident there was no way to tell a stuck page from a waiting
    one.

    Non-consuming also makes this UNSAFE as the only gate: two threads that
    both read 0 both proceed. It is the cheap refusal that precedes the
    expensive verify; `claim_login_attempt` is the decision.
    """
    with _RATE_GUARD:
        now = time.time()
        _prune(_login_attempts, _LOGIN_WINDOW_SECONDS, now)
        return _login_retry_after_locked(now)


def claim_login_attempt() -> int:
    """Spend one slot of the window, or refuse. 0 means the caller may verify.

    Check and consume are ONE decision here, which is the whole point: the
    limiter used to check in one call and record in another, with a PBKDF2
    verify in between, so every request thread that arrived during that gap
    read a budget none of them had spent yet. Ten guesses per minute became
    ten per minute per thread the pool would give out.

    A refusal spends nothing, so a caller polling into a 429 never pushes its
    own unlock further away. A slot spent by an attempt that turns out to be
    CORRECT is refunded by record_login_success(), which is what keeps the
    window counting failures rather than sign-ins -- the 2026-08 lockout.
    """
    with _RATE_GUARD:
        now = time.time()
        _prune(_login_attempts, _LOGIN_WINDOW_SECONDS, now)
        retry_after = _login_retry_after_locked(now)
        if retry_after:
            return retry_after
        _login_attempts.append(now)
        return 0


def record_login_success() -> None:
    """Clear the failure ledger: the host has proven presence, so stale
    failures (their own typos, or a password manager's) stop counting
    against them -- including the slot this very attempt just claimed."""
    with _RATE_GUARD:
        _login_attempts.clear()


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
    token_hash = _hash(token)
    # Claim the grant ATOMICALLY. The SELECT above is only a fast pre-check;
    # it is NOT the guard. Two requests racing the same live code both pass
    # the SELECT (redeemed_at still NULL for both), and without an atomic
    # claim both would issue a distinct token off one single-use code. The
    # `redeemed_at IS NULL` predicate on the UPDATE is the real guard: SQLite
    # serializes the two UPDATEs, so exactly one writer sees redeemed_at still
    # NULL and wins; the loser's UPDATE matches zero rows and changes nothing.
    # (qi returns lastrowid, not the affected-row count, so we confirm the
    # win by reading back token_hash: after both UPDATEs settle the row holds
    # exactly one winner's hash -- if it is ours, we redeemed it; if not,
    # another request claimed this code first and we must reject.)
    qi(
        "UPDATE guest_grants SET redeemed_at=?, token_hash=?, token_expires=? "
        "WHERE id=? AND redeemed_at IS NULL",
        (now, token_hash, now + GUEST_TOKEN_TTL, grant["id"]),
    )
    claimed = q(
        "SELECT token_hash FROM guest_grants WHERE id=?",
        (grant["id"],),
        one=True,
    )
    if not claimed or claimed["token_hash"] != token_hash:
        return None  # lost the race -- another request already claimed this code
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
        "SELECT g.* FROM guest_grants g "
        "JOIN chat_personas cp "
        "ON cp.chat_id=g.chat_id AND cp.persona_id=g.persona_id "
        "WHERE g.token_hash=? AND g.revoked=0 AND cp.status='active'",
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


def revoke_persona_grants(chat_id: int, persona_id: int) -> None:
    """Invalidate every remote session for a persona removed from a chat.

    Callers normally use this in the same transaction that marks the
    chat_personas row dormant. verify_guest_token() independently checks the
    active attachment too, so stale or hand-edited database state still fails
    closed even if a future caller forgets this lifecycle hook.
    """
    qi(
        "UPDATE guest_grants SET revoked=1 "
        "WHERE chat_id=? AND persona_id=? AND revoked=0",
        (chat_id, persona_id),
    )


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


# How long a dead grant stays visible in the host's invite panel before the
# sweep takes it. Expiry is not the same question as usefulness: a code that
# lapsed twenty minutes ago is exactly what the host is looking at when they
# ask why their friend could not get in. A week is long enough for that
# conversation and short enough that the table cannot grow without bound.
GRANT_RETENTION = 60 * 60 * 24 * 7


def sweep_expired_access() -> int:
    """Delete access rows that can never authenticate again. Returns the count.

    Neither table had a reaper. `verify_host_session` filters on `expires > ?`
    and `verify_guest_token` on `token_expires`, so a dead row was never a
    security hole -- it was unbounded growth in a file the host backs up,
    checkpoints and copies, and a growing scan behind every request that
    checks a cookie.

    Called from startup, which is the right cadence for a single-worker
    local app: no timer to leak, no second process to coordinate with, and
    the table cannot grow faster than one host's sessions between restarts.
    """
    now = time.time()
    with transaction():
        dead_sessions = q(
            "SELECT COUNT(*) AS n FROM host_sessions WHERE expires < ?",
            (now,),
            one=True,
        )
        qi("DELETE FROM host_sessions WHERE expires < ?", (now,))
        # A grant dies by whichever clock it reached. An unredeemed grant has
        # no token_expires at all, so COALESCE lets the code's own expiry
        # stand in -- without it, `token_expires < ?` is NULL for exactly the
        # rows that were never used, which are the ones that pile up.
        cutoff = now - GRANT_RETENTION
        predicate = (
            "code_expires < ? AND COALESCE(token_expires, code_expires) < ?"
        )
        dead_grants = q(
            f"SELECT COUNT(*) AS n FROM guest_grants WHERE {predicate}",
            (cutoff, cutoff),
            one=True,
        )
        qi(
            f"DELETE FROM guest_grants WHERE {predicate}",
            (cutoff, cutoff),
        )
    return int(dead_sessions["n"] or 0) + int(dead_grants["n"] or 0)


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
