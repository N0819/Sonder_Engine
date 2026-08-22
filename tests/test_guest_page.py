from pathlib import Path


GUEST_HTML = (
    Path(__file__).resolve().parents[1] / "static" / "guest.html"
).read_text(encoding="utf-8")


def test_guest_page_restores_an_existing_cookie_session():
    assert "async function resumeGuestSession()" in GUEST_HTML
    resume = GUEST_HTML[GUEST_HTML.index("async function resumeGuestSession()"):]
    resume = resume[:resume.index("\n}")]

    assert 'api("GET", "/api/guest/state")' in resume
    assert "showPlayState(state)" in resume
    assert "startPolling()" in resume
    assert "resumeGuestSession();" in GUEST_HTML


def test_guest_polling_serializes_state_requests():
    assert "if (refreshInFlight) return refreshInFlight;" in GUEST_HTML
    assert "setInterval(refresh" not in GUEST_HTML
    assert "pollHandle = setTimeout(pollOnce, 10000);" in GUEST_HTML


def test_guest_join_uses_the_authoritative_state_response():
    join = GUEST_HTML[GUEST_HTML.index("async function doJoin()"):]
    join = join[:join.index("\n}")]

    assert 'api("POST", "/api/join", { code })' in join
    assert 'api("GET", "/api/guest/state")' in join
    assert "showPlayState(state)" in join


def test_guest_failures_are_inline_and_recoverable():
    assert "alert(" not in GUEST_HTML
    assert 'id="send-status"' in GUEST_HTML
    assert 'id="connection-status"' in GUEST_HTML
    assert 'id="connection-retry"' in GUEST_HTML
    assert "inputEl.value = \"\";" in GUEST_HTML
    assert "sendStatus.textContent = e.message;" in GUEST_HTML
