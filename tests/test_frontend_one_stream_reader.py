"""One NDJSON reader for every stream this frontend consumes.

B25 (review 2026-09-07). `utils.js`'s `streamPost` reads the turn stream:
it redirects to /login on 401 (a host session expiring mid-stream is not an
error to toast, it is a signed-out tab), renders a structured `detail` through
`errorDetailText`, carries a partial line across chunk boundaries, flushes a
newline-less tail, and skips a frame it cannot parse instead of aborting the
answer.

`writers_room.js`'s `roomStream` re-implemented that loop and had none of the
first three: an expired session surfaced as a toast on a panel that looked
signed in, and a bare `JSON.parse` per line meant one malformed frame threw
out of the read loop and lost the rest of the reply. The two readers spoke the
same protocol and answered "what happens when the server says no" differently.

The rule is about the reader, not about the Writers' Room: a response body is
decoded in one place, and a caller that wants NDJSON asks for it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = sorted((ROOT / "static/js").glob("*.js"))
UTILS = (ROOT / "static/js/utils.js").read_text(encoding="utf-8")
ROOM = (ROOT / "static/js/writers_room.js").read_text(encoding="utf-8")


def test_only_one_file_reads_a_response_body():
    readers = [path.name for path in JS
               if "getReader(" in path.read_text(encoding="utf-8")]
    assert readers == ["utils.js"]


def test_the_room_streams_through_the_shared_reader():
    body = ROOM[ROOM.index("async function roomStream(text)"):]
    body = body[:body.index("function roomEvent")]

    assert "streamPost(" in body
    # The three the copy was missing, none of which belong to the room.
    assert "fetch(" not in body
    assert "JSON.parse" not in body
    assert "response.status" not in body


def test_the_shared_reader_still_carries_what_the_copy_lacked():
    """Pinned here rather than trusted, because the room now depends on it."""
    stream = UTILS[UTILS.index("async function streamPost"):]
    stream = stream[:stream.index("function downloadJSON")]

    assert re.search(r"status === 401", stream)
    assert 'window.location.href = "/login"' in stream
    assert "errorDetailText(" in stream
    # A frame that will not parse is skipped, not thrown out of the loop.
    assert stream.count("try { onEvt(JSON.parse(") == 2
