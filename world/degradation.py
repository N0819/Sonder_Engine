"""What a claim loses each time it is retold.

Approach C's floor says information "degrades by subtraction as it travels --
seeded, deterministic drops of specificity: a name becomes 'a stranger', a
count becomes 'several' -- never additive paraphrase, so distortion cannot
invent and therefore cannot contradict."

That last clause is the whole design and it is a CORRECTNESS argument rather
than a cost one. Additive distortion produces a DIFFERENT story, and a
different story reads as an engine error; subtractive distortion produces a
FAINTER story, and a fainter story reads as a rumor. The failure mode being
designed out is "how did he know that" -- and its quieter twin, "why does this
NPC believe something that never happened".

Two decisions carry the module:

**The degraded text is DERIVED, never stored.** A report keeps the original
witnessed surface and a hop count, and the vaguer wording is computed at the
moment it is read. Storing it would be a second source of truth that drifts,
and worse, re-degrading an already-degraded string compounds: "several" is
itself a word, and a function that ran over its own output twice would
eventually chew a claim into something nobody wrote. This is the
`wearing`/`state`/`regions` scar and the crowd-density scar arriving a third
time, so it is written the right way round from the start.

**The name goes last.** The order specificity is lost is a design choice with a
felt consequence: the point of a rumor is WHO, and the strongest single signal
approach C offers is that the player's own deeds precede them. Dropping the
name at the first hop would make every rumor useless one room from its source
-- "a stranger did something somewhere" -- and the mechanic would never land.
So the count goes first, the place second, and the name only when a claim has
travelled far enough that it barely says anything at all. At which point it
stops travelling: see `is_exhausted`.

PURE: strings in, strings out, no database, no model, no randomness. "Seeded"
in the design means reproducible, and the strongest form of reproducible is a
function of the claim and the hop count alone.
"""

from __future__ import annotations

import logging
import re

_log = logging.getLogger(__name__)

#: Specificity is lost in this order, one tier per hop. See the module note for
#: why the name outlives the count and the place.
TIER_COUNTS = 1
TIER_PLACES = 2
TIER_NAMES = 3

#: Past this, the claim has lost its count, its place and its name, and what is
#: left says almost nothing. A rumor that carries nothing should stop rather
#: than keep being repeated -- this is the deterministic answer to the "town of
#: criers" failure mode, where every NPC recites news forever.
EXHAUSTED_HOPS = TIER_NAMES + 1

#: THE WORDS ARE THE LANGUAGE'S. These three, `_ARTICLE` and `_COUNT` are
#: the ENGLISH defaults; a story pack states its own under
#: `linguistics["world.degradation"]` (`VAGUE_COUNT`, `VAGUE_PLACE`,
#: `VAGUE_PERSON`, `ARTICLE`, `COUNT`) and `_language` reads them there.
#: Measured (world_misc_causal F2, audit 2026-11-01): 「ミラ・ホルトが門の通路で
#: 衛兵を三人殺した」 came back word for word at hops 1, 2 and 3 -- `\b` never
#: falls between two characters of an unspaced script, so the caller's name
#: and place never matched, and neither 三 nor 三人 is an English count -- and
#: then `is_exhausted` stopped it: the rumour travelled exact until it died.
VAGUE_COUNT = "several"
VAGUE_PLACE = "some place"
VAGUE_PERSON = "a stranger"

#: An article in front of a redacted phrase is swallowed with it. "at the Gate
#: Passage" has to become "at some place" rather than "at the some place" --
#: the point of a rumor is that it sounds like someone talking, and a claim
#: that reads as broken grammar reads as an engine fault rather than as vague
#: hearsay, which is the exact confusion this module exists to prevent.
_ARTICLE = r"(?:\b(?:the|a|an)\s+)?"

#: Number words that mean MORE THAN ONE. `one` and `a` are deliberately absent:
#: "one man" is already about as vague as a count gets, and rewriting it to
#: "several man" would be additive -- it would claim more people than the
#: witnessed surface ever said, which is the one thing subtraction must never
#: do. NUMBERS, never idioms or vague quantities: "score", "couple", "few" and
#: "handful" were here, and "settled the score" became "settled the several",
#: "a couple of the guards saw a handful of riders" "a several of the guards
#: saw a several of riders" -- broken grammar, which the module note says
#: reads as an engine fault, for words that were never a count to lose
#: (world_misc_causal F3, audit 2026-11-01).
_PLURAL_NUMBER_WORDS = (
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "dozen",
)

#: A run of digits, or a hyphenated/spaced number phrase like "thirty-seven"
#: or "two hundred". Matched as a whole so "thirty-seven dockworkers" collapses
#: to one word rather than to "several-several". An indefinite article before
#: it goes with it ("a dozen guards" -> "several guards", never "a several
#: guards"), and a digit run that is half of a clock reading is a time, not a
#: count ("at 10:30" stayed "at several:several").
_COUNT = re.compile(
    r"(?:\b(?:a|an)\s+)?"
    r"(?:(?<![\d:])\b\d[\d,]*(?![\d:])|\b(?:%s)(?:[\s-]+(?:%s))*\b)"
    % ("|".join(_PLURAL_NUMBER_WORDS), "|".join(_PLURAL_NUMBER_WORDS)),
    re.IGNORECASE,
)

#: (language, name) pairs already reported missing from a pack, so the log
#: says it once per process rather than once per rumour.
_REPORTED: set = set()


def _language(name):
    """One of the five language-owned values: the active story pack's
    (`linguistics["world.degradation"][name]`), else the English default
    above. A non-English story whose pack does not carry it is told once in
    the log: its rumours still lose their name, place and count, in English
    words, until the pack says them in its own."""
    from language_runtime import (DEFAULT_LANGUAGE, LanguagePackError,
                                  current_language_id, linguistic)
    try:
        return linguistic("world.degradation", name)
    except LanguagePackError:
        language = current_language_id.get()
        if language != DEFAULT_LANGUAGE and (language, name) not in _REPORTED:
            _REPORTED.add((language, name))
            _log.warning("language pack %r carries no linguistics "
                         "world.degradation.%s; rumours degrade with the "
                         "English default", language, name)
    return {"COUNT": _COUNT, "ARTICLE": _ARTICLE, "VAGUE_COUNT": VAGUE_COUNT,
            "VAGUE_PLACE": VAGUE_PLACE, "VAGUE_PERSON": VAGUE_PERSON}[name]


def _collapse(text):
    return " ".join(str(text or "").split())


def _replace_phrases(text, phrases, replacement, article=_ARTICLE):
    """Swap each known phrase for one vaguer word, longest first.

    Longest-first matters: replacing "Gate" before "Gate Passage" would leave
    "somewhere Passage" behind, which is neither the original claim nor a
    vaguer one -- it is a sentence nobody wrote, and inventing wording is the
    exact thing this module exists to make impossible.

    A phrase is matched as a WHOLE name in whatever script it is written
    (`language_runtime.name_boundary_pattern`): `\b` never falls between two
    characters of an unspaced script, so a Japanese name or place was never
    matched at all (world_misc_causal F2).
    """
    from language_runtime import name_boundary_pattern
    out = text
    for phrase in sorted({_collapse(p) for p in phrases if _collapse(p)},
                         key=len, reverse=True):
        out = re.sub(str(article or "") + name_boundary_pattern(phrase),
                     lambda _m: replacement, out, flags=re.IGNORECASE)
    return _collapse(out)


def degrade(claim, hops, *, names=(), places=()):
    """The claim as it sounds after `hops` retellings.

    A pure function of the ORIGINAL claim and the hop count, so calling it
    again with a larger count is always equivalent to having called it once --
    there is no accumulated state to drift and no way to compound.

    `names` and `places` are supplied by the caller rather than guessed. The
    engine knows its own cast and rooms; a general-purpose name detector would
    have to invent a judgement about which words are people, and a wrong guess
    here silently rewrites a claim into something false. Nothing is redacted
    that the caller did not name.
    """
    text = _collapse(claim)
    if not text:
        return ""
    try:
        hops = max(0, int(hops))
    except (TypeError, ValueError):
        hops = 0
    article = _language("ARTICLE")
    article = getattr(article, "pattern", article)   # a pack may compile it
    if hops >= TIER_COUNTS:
        vague = _language("VAGUE_COUNT")
        count = _language("COUNT")
        if isinstance(count, str):                    # ...or write it plain
            count = re.compile(count, re.IGNORECASE)
        text = _collapse(count.sub(lambda _m: vague, text))
    if hops >= TIER_PLACES:
        text = _replace_phrases(text, places, _language("VAGUE_PLACE"), article)
    if hops >= TIER_NAMES:
        text = _replace_phrases(text, names, _language("VAGUE_PERSON"), article)
    return text


def is_exhausted(hops):
    """True when a claim has nothing specific left to lose.

    An exhausted rumor should not be passed on again. It is not that the words
    become nonsense -- they stay grammatical -- it is that they have stopped
    being about anything, and a world where such a claim keeps circulating is
    the town of criers.
    """
    try:
        return int(hops) >= EXHAUSTED_HOPS
    except (TypeError, ValueError):
        return False


def lost_at(hops):
    """What a listener could tell you was missing, for diagnostics and tests.

    Deliberately not shown to any model. A mind that knew WHICH details had
    been filed off would know more than a mind that had merely heard a vague
    story, and that is knowledge nobody delivered to them.
    """
    try:
        hops = max(0, int(hops))
    except (TypeError, ValueError):
        hops = 0
    lost = []
    if hops >= TIER_COUNTS:
        lost.append("count")
    if hops >= TIER_PLACES:
        lost.append("place")
    if hops >= TIER_NAMES:
        lost.append("name")
    return lost
