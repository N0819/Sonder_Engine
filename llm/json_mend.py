"""Mend a model's broken JSON by structural edits alone, before a model is asked.

Measured 2026-09-28 on the owner's capture: of the fifteen answers there that
failed to parse, today's parser already reads six (an answer restarted part
way, a stub around an empty object) and one more was bare prose, which the
ladder reads as its own case. Of the eight left, six are BRACKETS -- one
closer too many, two closers written in the wrong order, an inner container
never closed, the wrong kind of closer -- and two are a KEY'S QUOTES: one
unquoted, one whose closing quote went missing. The encoder's one failure in
470 calls was two closers in the wrong order, and the rebuild rung spent a
model round trip swapping two characters back.

WHAT A MEND MAY DO: insert, delete or swap a bracket or a comma, and add the
quotes a key is missing. It never changes the text inside a string or any
value, so it cannot change what the model said -- only how it was
punctuated. It never CLOSES an answer that stopped short: brackets left open
at the end are what a cut-off answer looks like, and closing one would pass
a truncated beat off as whole. That is the ladder's truncation re-ask.

A SLIP MADE BY HABIT IS MENDED EVERYWHERE IT RECURS: an establish answer
closed each of its eleven rooms' keyed maps with `]`, so once one edit clears
a fault, the same kind of edit may clear each later fault of that shape
(`MAX_REPEATS`). Candidates come fewest distinct edits first, each one a
parse the caller still validates against the step's schema -- a mend that
parses into the wrong shape is refused there and the next is tried.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Iterator

#: The most distinct edits one answer may take. Every measured failure
#: needed one kind; two covers an answer with two separate slips. Named per
#: the owner's ask-before-limiting rule, like the two below.
MAX_EDITS = 2
#: How many times one kind of edit may recur through an answer: a slip made
#: by habit (measured: eleven in one establish answer).
MAX_REPEATS = 64
#: The most candidate texts tried for one answer.
MAX_TRIES = 60
#: Longer answers are left to the model rungs: each try re-scans the text.
MAX_CHARS = 400_000

_CLOSER = {"{": "}", "[": "]"}
_OPENER = {"}": "{", "]": "["}
_BARE_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?=\s*:)")
#: A key whose closing quote went missing, with its scalar value swallowed
#: into the string: `"amount: 0.15,` up to the line break that ends it.
_KEY_LOST_QUOTE = re.compile(
    r'\s*([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*'
    r'(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null)\s*(,?)\s*$')


def _loads(text):
    """The object `text` holds, or None. `strict=False` lets a raw line break
    or tab stand inside a string, which is punctuation, not content."""
    try:
        value = json.loads(text, strict=False)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _error(text, strict):
    try:
        json.loads(text, strict=strict)
    except json.JSONDecodeError as exc:
        return exc.pos, exc.msg
    except (ValueError, RecursionError):
        return None
    return None


def _bracket_fault(text):
    """`(position, stack)` of the first closer that does not close the
    innermost open container, or None. `stack` is `[(opener, position)]`.
    A closer with nothing open is reported with an empty stack."""
    stack, in_string, escaped = [], False, False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append((ch, i))
        elif ch in "}]":
            if not stack or stack[-1][0] != _OPENER[ch]:
                return i, stack
            stack.pop()
    return None


def _next_significant(text, pos):
    j = pos
    while j < len(text) and text[j].isspace():
        j += 1
    return j


def _previous_significant(text, pos):
    j = pos - 1
    while j >= 0 and text[j].isspace():
        j -= 1
    return j


def _string_start(text, pos):
    """Where the string running at `pos` opened, or -1."""
    in_string, escaped, start = False, False, -1
    for i, ch in enumerate(text[:pos]):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string, start = True, i
    return start if in_string else -1


def _trailing_comma_at(text, pos):
    """Where the trailing comma at the decoder's fault `pos` stands, or None.

    READ OFF THE TEXT, NOT OFF THE MESSAGE. Python 3.11 and 3.12 report a
    trailing comma at the closer after it, as "Expecting property name" or
    "Expecting value"; 3.13 names it -- "Illegal trailing comma before end of
    object" -- at the comma itself. Keyed on the older wording, the mend
    mended nothing on the interpreter both launchers try first (CI on 3.13,
    2026-10-05)."""
    at = text[pos] if pos < len(text) else ""
    if at and at in "]}":
        comma = _previous_significant(text, pos)
        return comma if comma >= 0 and text[comma] == "," else None
    if at == ",":
        closer = _next_significant(text, pos + 1)
        return pos if closer < len(text) and text[closer] in "]}" else None
    return None


def _decoder_edits(text):
    """Edits at the point the decoder itself gave up: a key's quotes, a
    trailing comma, a comma missing between two elements. Each is
    `(text, what, kind)`."""
    out = []
    strict = _error(text, strict=True)
    if strict and (strict[1].startswith("Invalid control")
                   or strict[1].startswith("Unterminated string")):
        start = _string_start(text, strict[0] + 1)
        end = text.find("\n", start + 1) if start >= 0 else -1
        if start >= 0 and end > start:
            lost = _KEY_LOST_QUOTE.match(text[start + 1:end])
            if lost:
                key, value, comma = lost.groups()
                out.append((text[:start] + f'"{key}": {value}{comma}' + text[end:],
                            f"closed the quotes of the key {key}", "key-quote"))
    loose = _error(text, strict=False)
    if not loose:
        return out
    pos, msg = loose
    at = text[pos] if pos < len(text) else ""
    comma = _trailing_comma_at(text, pos)
    if comma is not None:
        out.append((text[:comma] + text[comma + 1:],
                    "dropped a trailing comma", "trailing-comma"))
    if msg.startswith("Expecting property name"):
        key = _BARE_KEY.match(text, pos)
        if key:
            out.append((text[:pos] + f'"{key.group(0)}"' + text[key.end():],
                        f"quoted the key {key.group(0)}", "bare-key"))
    elif msg.startswith("Expecting ',' delimiter") and at and at in '"{[':
        before = _previous_significant(text, pos)
        if before >= 0 and text[before] in '"}]el0123456789':
            out.append((text[:pos] + "," + text[pos:],
                        "added a missing comma", "missing-comma"))
    elif msg.startswith("Extra data"):
        # A closer that ended the whole answer early looks legal to a bracket
        # count; only the text after it says otherwise.
        early = _previous_significant(text, pos)
        if early >= 0 and text[early] in "}]":
            out.append((text[:early] + text[early + 1:],
                        "dropped a closer that ended the answer early", "early-close"))
    return out


def _bracket_edits(text):
    """Edits at the first closer that does not close what is open, as
    `(text, what, kind)`."""
    fault = _bracket_fault(text)
    if fault is None:
        return []
    pos, stack = fault
    closer = text[pos]
    if not stack:
        return [(text[:pos] + text[pos + 1:], "dropped a stray closer", "stray")]
    opener, open_at = stack[-1]
    want = _CLOSER[opener]
    out = []
    after = _next_significant(text, pos + 1)
    if after < len(text) and text[after] == want:
        out.append((text[:pos] + want + text[pos + 1:after] + closer + text[after + 1:],
                    "swapped two closers", "swap"))
    out.append((text[:pos] + text[pos + 1:], "dropped a stray closer", "stray"))
    out.append((text[:pos] + want + text[pos:], f"closed an unclosed {opener}",
                f"close-{opener}"))
    out.append((text[:pos] + want + text[pos + 1:], f"closed {opener} with {want}",
                f"closer-{opener}{want}"))
    out.append((text[:open_at] + _OPENER[closer] + text[open_at + 1:],
                f"opened with {_OPENER[closer]}", f"opener-{_OPENER[closer]}"))
    return out


def _edits(text):
    return _decoder_edits(text) + _bracket_edits(text)


def _repeated(text, kind):
    """`(object, whats)` when edits of `kind` applied at each later fault in
    turn make `text` parse, else None."""
    current, whats = text, []
    for _ in range(MAX_REPEATS):
        options = [edit for edit in _edits(current) if edit[2] == kind]
        if not options:
            return None
        current, what, _kind = options[0]
        whats.append(what)
        value = _loads(current)
        if value is not None:
            return value, whats
    return None


def _summary(whats):
    counts = Counter(whats)
    return [what if counts[what] == 1 else f"{what} (x{counts[what]})"
            for what in dict.fromkeys(whats)]


def mend_candidates(text) -> Iterator[tuple[dict, list[str]]]:
    """`(object, edits)` for each mend of `text` that parses, fewest distinct
    edits first. Nothing when `text` already parses, is too long, or only runs
    out of brackets at its end (a cut-off answer is not this function's to
    close)."""
    text = str(text or "")
    if not text.strip() or len(text) > MAX_CHARS:
        return
    try:
        json.loads(text)
        return
    except (ValueError, RecursionError):
        pass
    loose = _loads(text)
    if loose is not None:
        yield loose, ["let a raw line break or tab stand inside a string"]
        return
    seen, frontier, tries = {text}, [(text, [])], 0
    for _depth in range(MAX_EDITS):
        deeper = []
        for current, whats in frontier:
            for candidate, what, kind in _edits(current):
                if candidate in seen:
                    continue
                seen.add(candidate)
                tries += 1
                if tries > MAX_TRIES:
                    return
                value = _loads(candidate)
                if value is not None:
                    yield value, _summary(whats + [what])
                    continue
                again = _repeated(candidate, kind)
                if again is not None:
                    yield again[0], _summary(whats + [what] + again[1])
                    continue
                deeper.append((candidate, whats + [what]))
        frontier = deeper
