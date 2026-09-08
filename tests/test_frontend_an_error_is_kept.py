"""An error the reader is shown is kept: in the console, and on screen.

A toast is the only place most failures are ever stated. It said the right
thing and then went away: a greeting start that returned 404 (2026-09-08)
carried the real reason in its `detail`, the toast printed it, and four
seconds later the only thing left was an access-log line reading
"404 Not Found" -- which names a missing route, which it was not.

Two rules, both in `toast` itself rather than at the call sites, because what
they are about is a reader being shown something and not which surface raised
it:

  * every error and every warning is written to the console in the SAME
    words, so a message that scrolled away can still be read, copied and
    reported;
  * an error stays until it is dismissed. A confirmation may leave on its
    own; a failure the reader has to act on, quote or report may not.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static/js"
COMPONENTS = (JS / "components.js").read_text(encoding="utf-8")


def _toast_body() -> str:
    """The body of `function toast(...)`, to its closing brace."""
    start = COMPONENTS.index("function toast(")
    depth, i = 0, COMPONENTS.index("{", start)
    for j in range(i, len(COMPONENTS)):
        if COMPONENTS[j] == "{":
            depth += 1
        elif COMPONENTS[j] == "}":
            depth -= 1
            if depth == 0:
                return COMPONENTS[start:j + 1]
    raise AssertionError("toast() has no closing brace")


def test_an_error_toast_is_written_to_the_console():
    body = _toast_body()
    assert "console.error" in body, body[:400]
    assert "console.warn" in body, body[:400]


def test_the_console_gets_the_same_words_the_reader_got():
    """Not the exception object: the sentence that was shown. An `Error`
    logged raw prints its own class and stack and not the message the toast
    composed from a server `detail`."""
    body = _toast_body()
    for call in re.findall(r"console\.(?:error|warn)\(([^\n]*)\)", body):
        assert "message" in call, call


def test_an_error_stays_until_it_is_dismissed():
    """`timeout` defaults to null so the type can decide, and an error
    resolves to 0 -- which the caller below reads as "do not remove"."""
    body = _toast_body()
    assert re.search(r"function toast\([^)]*timeout\s*=\s*null", body), body[:200]
    assert re.search(r'timeout\s*=\s*type\s*===\s*"err"\s*\?\s*0\s*:', body), body[:600]
    assert "if (timeout)" in body, "a 0 timeout must not schedule a removal"


@pytest.mark.parametrize(
    "name", sorted(p.name for p in JS.glob("*.js")))
def test_no_error_toast_sets_its_own_expiry(name):
    """The rule is one rule. A call site naming its own seconds is the drift
    this test exists to stop -- five of them did, at 8000 and 9000ms, each
    an independent guess at how long a failure deserves. An explicit 0 is
    allowed: it says "stay", which is what the rule already gives."""
    source = (JS / name).read_text(encoding="utf-8")
    timed = re.findall(r'toast\([^;]*?"err"\s*,\s*(\d+)\s*\)', source)
    assert all(value == "0" for value in timed), (name, timed)
