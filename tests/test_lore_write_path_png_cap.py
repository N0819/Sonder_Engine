"""extract_png_card must bound what it will decode.

Card imports are, by design, untrusted community files, and the zTXt inflate
inside `_png_text_chunks` is already bounded at 10MB for exactly that reason.
The base64 payload itself had no such bound: `base64.b64decode(raw)` ran on a
request-body string of any size, with no validation, before any structural
check. The cap here rejects on the LENGTH of the base64 text, before a single
byte is decoded, and validates the alphabet on the way through.

Deliberately NOT tightened: chunk CRCs. A bad chunk is silently skipped by
design today -- sloppy community exporters produce real cards with bad CRCs,
and rejecting those would trade a working import for a purity check.
"""

from __future__ import annotations

import base64
import json
import struct
import zlib

import pytest

from story import importers


def _png_with_chara(card):
    payload = base64.b64encode(
        json.dumps(card).encode("utf-8")).decode("ascii")
    data = b"chara\x00" + payload.encode("latin-1")
    chunk = struct.pack(">I", len(data)) + b"tEXt" + data
    chunk += struct.pack(">I", zlib.crc32(b"tEXt" + data))
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0)
    return importers._PNG_SIGNATURE + chunk + iend


class TestPngSizeCap:
    def test_an_oversized_payload_is_rejected_before_decode(self):
        raw = "A" * ((importers.MAX_CARD_PNG_BYTES * 4) // 3 + 100)
        with pytest.raises(ValueError, match="large"):
            importers.extract_png_card("data:image/png;base64," + raw)

    def test_invalid_base64_is_rejected(self):
        with pytest.raises(ValueError, match="Invalid PNG data"):
            importers.extract_png_card("data:image/png;base64,%%%%not-b64%%%%")

    def test_a_real_small_card_still_parses(self):
        png = _png_with_chara({"name": "Iseul", "description": "a courier"})
        b64 = base64.b64encode(png).decode("ascii")
        card = importers.extract_png_card("data:image/png;base64," + b64)
        assert card == {"name": "Iseul", "description": "a courier"}

    def test_wrapped_base64_from_a_sloppy_exporter_still_parses(self):
        """MIME-style 76-column wrapping is not malice; strip whitespace
        before validating the alphabet rather than rejecting it."""
        png = _png_with_chara({"name": "Iseul"})
        b64 = base64.b64encode(png).decode("ascii")
        wrapped = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
        card = importers.extract_png_card(wrapped)
        assert card == {"name": "Iseul"}
