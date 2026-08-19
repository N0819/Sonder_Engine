"""A vocabulary the engine owns must reach the browser from the engine.

Several controlled lists -- memory categories, memory provenance -- live in
Python, ride every `/api/bootstrap` response, and were then ignored by a
hardcoded second copy in `static/js/`. Both ends coerce silently: `mind/memory.py`
rewrites an unrecognised category or provenance to a default rather than
rejecting it. So a term added server-side is merely absent from the dropdown,
and one removed server-side is offered in the dropdown and quietly changed on
save. Drift here has no symptom at all, which is why it needs a test rather
than a convention.

The browser keeps a fallback for a tab whose cached JavaScript is running ahead
of its first bootstrap response. A fallback is allowed to exist; it is not
allowed to disagree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mind.memory import MEMORY_CATEGORIES, MEMORY_PROVENANCE

ROOT = Path(__file__).resolve().parents[1]
UTILS = (ROOT / "static/js/utils.js").read_text(encoding="utf-8")
CHAT = (ROOT / "static/js/chat.js").read_text(encoding="utf-8")


def _js_array(source: str, name: str) -> list[str]:
    match = re.search(r"^const %s = (\[[^\]]*\]);" % re.escape(name),
                      source, re.MULTILINE)
    assert match, f"{name} not found as a top-level array"
    return json.loads(match.group(1))


def test_the_browser_reads_the_shipped_memory_vocabularies():
    """The bootstrap already carries both lists; the dropdowns must use them."""
    assert "S.boot.memory_categories" in UTILS
    assert "S.boot.memory_provenance" in UTILS
    # And nothing may go back to reading a frozen copy directly.
    assert "MEM_CATS_FALLBACK" not in CHAT
    assert "MEM_PROV_FALLBACK" not in CHAT
    assert CHAT.count("memoryCategories()") == 3
    assert CHAT.count("memoryProvenance()") == 3


def test_the_browser_fallbacks_still_agree_with_the_engine():
    """A fallback that has drifted is worse than none: it renders a plausible
    dropdown out of terms the engine will overwrite without saying so."""
    assert _js_array(UTILS, "MEM_CATS_FALLBACK") == MEMORY_CATEGORIES
    assert _js_array(UTILS, "MEM_PROV_FALLBACK") == MEMORY_PROVENANCE
