"""Engine diagnostics are not world text.

When the engine synthesises a description of a place it does not have canon
for, it is worth recording WHY -- a retrieval came back with nothing and the
engine invented rather than waited. That is a fact about the engine. It is not
a fact about the place, and a mind standing in the room has no channel to it.

MEASURED, live, chat 95 beat 7. The composed view delivered to a character
agent opened:

    "You are in Harbour Office. generated because no candidate described this
     location."

The second sentence is the engine explaining its own bookkeeping, and the
character read it as a property of the room it was standing in. It reached the
view because the mapping prompt asked the model to "put your uncertainty in the
entry's own text", and a staged `layout` entry's text becomes the room's
description (`persist/commit_scene_state`) and the view's room notes
(`agents/common._room_notes_for_view`). One string served two audiences that
must never be the same audience.

DELETING THE SIGNAL WOULD BE THE WORSE FIX. A generated description that does
not say it was generated cannot be found, audited or corrected later, and the
whole point of the mapping rule is that a wrong guess should stay cheap. So the
two are SEPARATED rather than one of them dropped: `split_engine_provenance`
returns the place and the bookkeeping as two strings, the bookkeeping is filed
where this codebase already files provenance -- a lore row's `source_notes`,
the same column `world/background_claims.CANON_SOURCE_PREFIX` stamps -- and
only the place travels onward into prose.

PURE: strings in, strings out. No database, no model, no scene.

The patterns below are a deterministic FLOOR, not the fix. The fix is upstream:
the mapping prompt now asks for a structured `provenance` field and forbids the
sentence. A floor is kept anyway because a leak is an engine failure, never a
model's -- nothing here may depend on a model choosing to cooperate. Every
pattern is written in the engine's own vocabulary (retrieval, candidates,
canon, entries, placeholders) and names no story, no place and no character;
a sentence of fiction cannot match one without talking about the engine.
"""

from __future__ import annotations

import re

#: A sentence matches when it talks about how this text came to exist, rather
#: than about what it describes. Multi-word wherever a single word could
#: plausibly appear in fiction ("generated" alone is a hum from a turbine;
#: "generated because" is an engine explaining itself).
_PROVENANCE_PATTERNS = (
    r"\b(?:auto[-\s]?)?generated\s+(?:because|by\s+the\s+engine|"
    r"as\s+a\s+(?:placeholder|stub|fallback))",
    r"\bauto[-\s]?generated\b",
    r"\bautomatically\s+generated\b",
    r"\bengine[-\s]generated\b",
    r"\bno\s+candidates?\b",
    r"\bcanon\s+(?:is|was)\s+silent\b",
    r"\bplaceholder\b",
    r"\b(?:fallback|default|generated)\s+description\b",
    r"\bstub\s+(?:entry|room|description)\b",
    r"\bsynthesi[sz]ed\s+because\b",
    r"\bretrieval\s+(?:returned|failed|surfaced|found)\b",
    r"\bno\s+(?:lore|lorebook)\s+entry\b",
    r"\b(?:this|the)\s+(?:entry|description|record|text)\s+(?:was|is)\s+"
    r"(?:auto[-\s]?)?(?:generated|synthesi[sz]ed|invented|created|written)\b",
)

_PROVENANCE_RE = re.compile("|".join(_PROVENANCE_PATTERNS), re.IGNORECASE)

# A parenthetical is the other shape the same note arrives in -- "A narrow
# landing (generated because no candidate described this floor)" -- and it does
# not end a sentence, so the sentence splitter alone would keep it. Bounded and
# single-line: an unpaired bracket in ordinary prose must not swallow the rest.
_BRACKETED_RE = re.compile(r"[\(\[][^\)\]\n]{1,300}[\)\]]")

# Split AFTER terminal punctuation, keeping it, so the surviving prose reads
# exactly as it was written.
_SENTENCE_RE = re.compile(r"[^.!?\n]*(?:[.!?\n]+|$)")


def looks_like_engine_provenance(text):
    """True when this fragment is the engine describing its own bookkeeping."""
    return bool(_PROVENANCE_RE.search(str(text or "")))


def split_engine_provenance(text):
    """`text` -> (what describes the world, what describes the engine).

    Both halves are returned because both are wanted: the first is the only one
    that may reach a view, and the second is what an author or an audit needs in
    order to find a description the engine invented. Whitespace is normalised at
    the joins so removing a sentence from the middle does not leave a gap.
    """
    raw = str(text or "")
    if not raw.strip():
        return "", ""
    if not _PROVENANCE_RE.search(raw):
        return raw, ""

    provenance = []

    def _take_bracket(match):
        span = match.group(0)
        if _PROVENANCE_RE.search(span):
            provenance.append(span.strip("()[] \t"))
            return " "
        return span

    body = _BRACKETED_RE.sub(_take_bracket, raw)

    kept = []
    for match in _SENTENCE_RE.finditer(body):
        sentence = match.group(0)
        if not sentence.strip():
            continue
        if _PROVENANCE_RE.search(sentence):
            provenance.append(sentence.strip())
        else:
            kept.append(sentence.strip())

    prose = re.sub(r"\s+", " ", " ".join(kept)).strip()
    # A parenthetical taken out of the middle of a sentence leaves its own
    # space in front of the punctuation that followed it. Close it up, so what
    # a mind receives reads as the sentence the author would have written.
    prose = re.sub(r"\s+([.,;:!?])", r"\1", prose)
    note = re.sub(r"\s+", " ", " ".join(p for p in provenance if p)).strip()
    return prose, note


def strip_engine_provenance(text):
    """`text` with the engine's bookkeeping removed. The delivery floor."""
    return split_engine_provenance(text)[0]
