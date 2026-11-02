"""The leaf every sibling stands on: language-pack lookup under the
'agents.common' key, coercion helpers, quote/typography folding and markup
stripping, the shared English third-person morphology helper, and the
append-once string utility.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import json
import re
from language_runtime import compositor_text, english_linguistic, linguistic

def _ling(name):
    return linguistic("agents.common", name)


def _text(key, **values):
    return compositor_text(key, **values)


def _dangling_speech(part, language_id=None):
    """The healer pattern for one wound, built from the ONE speech vocabulary.

    A dangling verb and a dangling colon are the same wound from the same cut,
    so what counts as speech is a single pack value (`_SPEECH_CUE`) and the two
    patterns are shapes around it. They were two independent literals before,
    and they drifted: `en`'s verb healer knew `call` and `shout` and its colon
    healer did not, and neither of `ja`'s carried a single Japanese verb while
    its `_SPEECH_CUE` carried eight. The SHAPE stays per-language because the
    wound is: English strands a verb before a comma, Japanese strands the
    quotative particle before a clause-final verb.
    """
    shape = linguistic("agents.common", "_DANGLING_SPEECH", language_id)[part]
    cue = str(linguistic("agents.common", "_SPEECH_CUE", language_id))
    return re.compile(str(shape["pattern"]).replace("{cue}", cue),
                      int(shape.get("flags") or 0))

# Read-only English compatibility views for diagnostics/tests that import the
# historical constants. Runtime guards resolve through the active pack and
# remain context local; these names are not consulted by a story pipeline.
_DANGLING_SPEECH_VERB_RE = _dangling_speech("verb", "en")
_SPEECH_CUE = english_linguistic("agents.common", "_SPEECH_CUE")

def _stem_token(tok):
    """Crude suffix stem for verb matching ('remembers' -> 'remember')."""
    for suf in ("ing", "es", "ed", "s"):
        if len(tok) > len(suf) + 2 and tok.endswith(suf):
            return tok[:-len(suf)]
    return tok


def _dict(value):
    return value if isinstance(value, dict) else {}

def _list(value):
    return value if isinstance(value, list) else []

def _dict_list(value):
    return [item for item in _list(value) if isinstance(item, dict)]

def _text_piece(value) -> str:
    """Normalize heterogeneous values for retrieval queries."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
        except (TypeError, ValueError):
            return ""
    return str(value).strip()

def _join_text(values) -> str:
    """Safely join retrieval-query components."""
    parts = [_text_piece(value) for value in values]
    return " ".join(part for part in parts if part)

def _append_once(view, text, marker=None):
    text = str(text or "").strip()
    if not text:
        return view
    view = str(view or "").strip()
    marker = str(marker or text).strip()
    if marker and marker.casefold() in view.casefold():
        return view
    return f"{view} {text}".strip()

# Typographic variants folded before quote comparison. A model renders the
# same line twice with different typography -- measured live: `"I‑I must
# of..."` with U+2011 hyphens and curly apostrophes, restored a second time
# with ASCII punctuation -- and a byte-wise dedupe called them two different
# lines, so one spoken line landed twice in one view.
_TYPOGRAPHY_FOLD = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...",
})


def _fold_typography(text):
    return str(text or "").translate(_TYPOGRAPHY_FOLD)


#: The closed set `schemas.canonicalize_prose_markup` may leave in prose. It
#: is stripped for COMPARISON only -- the tags stay in the stored string,
#: which is what the reader sees rendered.
_PROSE_MARKUP_RE = re.compile(
    r"</?(i|b|u|s|mark|sup|sub|code)>", re.I)


def strip_prose_markup(text):
    """Prose as the fidelity checks must read it: words, no marks.

    The narrator emits inline emphasis unprompted -- a consequence of the
    paragraph contract teaching it that this channel speaks HTML -- and a tag
    landing INSIDE a quoted line breaks every check that looks for that line
    by substring. `"I have <i>absolutely</i> got this,"` does not contain
    `I have absolutely got this,`, so a correctly rendered line reads as a
    DROPPED one, and the narrator is sent back to rewrite prose that was
    already right.
    """
    return _PROSE_MARKUP_RE.sub("", str(text or ""))


def _contains_quote(view, quote):
    body = _fold_typography(_quote_body(quote))
    normalized_view = re.sub(
        r"\s+", " ", _fold_typography(strip_prose_markup(view)).casefold())
    normalized_body = re.sub(r"\s+", " ", body.casefold()).rstrip(".,!?…;:")
    if not normalized_body:
        return False
    # A dialogue tag changes terminal punctuation mechanically: the logged
    # line ``Lie back.`` becomes ``"Lie back," she says``.  That is the same
    # delivered quote, and treating it as absent appends a duplicate exact-line
    # injection.  Internal punctuation remains significant; only the terminal
    # mark is ignored, with a word boundary so ``back`` cannot match
    # ``backwards``.
    return re.search(
        r"(?<!\w)%s(?=$|[^\w])" % re.escape(normalized_body),
        normalized_view,
    ) is not None


def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")


def _base_from_third_person_s(word):
    """Undo third-person-singular -s/-es/-ies on a regular present verb, or
    return None when the word is not one."""
    low = word.lower()
    if (low in _ling("_NON_VERB_S_WORDS") or len(low) <= 3 or not low.endswith("s")
            or low.endswith(("ss", "us", "is", "as", "'s", "’s"))):
        return None
    if low.endswith("ies") and len(low) > 4:      # carries -> carry
        return word[:-3] + "y"
    if low.endswith("es") and low[:-2].endswith(_ling("_ES_STEM_ENDINGS")):
        return word[:-2]                          # catches -> catch
    return word[:-1]                              # steps -> step
