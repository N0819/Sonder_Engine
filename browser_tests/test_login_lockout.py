"""The 2026-08 lockout incident, browser half.

The host's password manager auto-resubmitted saved (stale) credentials on
the login page. Each synthetic submission was accepted as if a human had
acted, each burned one slot of the server's global 10-per-60s window, and
within seconds the host's own deliberate, CORRECT sign-in was refused --
with only a static "Too many attempts, wait a minute" on screen. A
private browser window "fixed" it precisely because it had no saved
credentials.

Three page defects converted non-deliberate event streams into unbounded
server attempts, and each is pinned here against a REAL server (the
limiter is server state, so route-mocking would prove nothing):

  (a) the keydown/click handlers accepted synthetic (isTrusted=false)
      events -- any auto-submitting extension could drive them;
  (b) a held Enter key auto-repeats ~30/s and each repeat fired a fresh
      request while the last was still in flight;
  (c) a lockout rendered as static text, indistinguishable from a stuck
      page -- the fix counts down on screen.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


ROOT = Path(__file__).resolve().parents[1]
USERNAME = "host"
PASSWORD = "right-horse-battery"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post_json(url: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.fixture
def auth_server(tmp_path):
    """The real app on a scratch database, one per test so each test owns
    the (process-global) limiter state, with a host account created."""
    port = _free_port()
    env = {**os.environ, "ENGINE_DB": str(tmp_path / "auth.db")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 30
        while True:
            try:
                with urllib.request.urlopen(f"{base}/api/auth/status"):
                    break
            except OSError:
                if proc.poll() is not None or time.time() > deadline:
                    raise RuntimeError("app server did not come up")
                time.sleep(0.2)
        status, _ = _post_json(
            f"{base}/api/auth/setup",
            {"username": USERNAME, "password": PASSWORD},
        )
        assert status == 200
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _count_login_requests(page: Page) -> list:
    hits: list = []
    page.on(
        "request",
        lambda r: hits.append(r.url)
        if r.url.endswith("/api/auth/login") else None,
    )
    return hits


def test_autofill_loop_cannot_spend_the_login_budget(
    page: Page, auth_server: str
) -> None:
    """The incident itself: 12 synthetic fill+Enter sequences (what an
    auto-submitting password manager dispatches; isTrusted=false) used to
    become 12 server attempts and a burned budget, so the human's correct
    sign-in got 429. Now zero synthetic events reach the server and the
    human signs straight in."""
    page.goto(f"{auth_server}/login")
    expect(page.locator("#login-form")).to_be_visible()
    hits = _count_login_requests(page)

    page.evaluate("""() => {
      const u = document.getElementById("login-username");
      const pw = document.getElementById("login-password");
      for (let i = 0; i < 12; i++) {
        u.value = "host";
        pw.value = "stale-saved-password";
        u.dispatchEvent(new Event("input", {bubbles: true}));
        pw.dispatchEvent(new Event("input", {bubbles: true}));
        pw.dispatchEvent(new KeyboardEvent("keydown",
            {key: "Enter", bubbles: true}));
      }
    }""")
    page.wait_for_timeout(800)
    assert len(hits) == 0, (
        f"{len(hits)} synthetic (non-human) events reached the server"
    )

    # The human act still works, first try, no lockout.
    page.fill("#login-username", USERNAME)
    page.fill("#login-password", PASSWORD)
    page.click("#login-btn")
    page.wait_for_url(f"{auth_server}/")


def test_held_enter_key_is_one_attempt(page: Page, auth_server: str) -> None:
    """A held Enter auto-repeats keydown ~30/s; every repeat used to fire
    its own request while the last was still in flight, so ONE slightly
    long keypress could spend most of the global budget. One hold must be
    one attempt."""
    page.goto(f"{auth_server}/login")
    expect(page.locator("#login-form")).to_be_visible()
    hits = _count_login_requests(page)

    page.fill("#login-username", USERNAME)
    page.fill("#login-password", "wrong-password")
    page.focus("#login-password")
    cdp = page.context.new_cdp_session(page)
    for i in range(8):
        cdp.send("Input.dispatchKeyEvent", {
            "type": "rawKeyDown", "key": "Enter", "code": "Enter",
            "windowsVirtualKeyCode": 13, "autoRepeat": i > 0,
        })
    cdp.send("Input.dispatchKeyEvent", {
        "type": "keyUp", "key": "Enter", "code": "Enter",
        "windowsVirtualKeyCode": 13,
    })
    page.wait_for_timeout(800)
    assert len(hits) == 1, (
        f"one held Enter became {len(hits)} server attempts"
    )


def test_lockout_shows_a_live_countdown(page: Page, auth_server: str) -> None:
    """During the incident the only message was the static "Too many
    attempts, wait a minute" -- no way to tell a waiting page from a stuck
    one, which is what turned a 60-second lockout into an hour. The 429
    must render as a countdown that visibly decreases, and the button must
    be held disabled while it runs."""
    for _ in range(10):
        status, _ = _post_json(
            f"{auth_server}/api/auth/login",
            {"username": USERNAME, "password": "wrong-password"},
        )
        assert status == 401
    status, body = _post_json(
        f"{auth_server}/api/auth/login",
        {"username": USERNAME, "password": PASSWORD},
    )
    assert status == 429 and "retry_after_seconds" in body

    page.goto(f"{auth_server}/login")
    expect(page.locator("#login-form")).to_be_visible()
    page.fill("#login-username", USERNAME)
    page.fill("#login-password", PASSWORD)
    page.click("#login-btn")

    err = page.locator("#login-err")
    expect(err).to_contain_text(re.compile(r"in \d+s"))
    expect(page.locator("#login-btn")).to_be_disabled()
    first = int(re.search(r"in (\d+)s", err.text_content()).group(1))
    page.wait_for_timeout(2200)
    second = int(re.search(r"in (\d+)s", err.text_content()).group(1))
    assert second < first, (
        f"countdown did not move: {first}s then {second}s"
    )
