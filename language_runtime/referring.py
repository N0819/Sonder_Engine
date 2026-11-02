"""The grammar of a referring expression, read off the active pack's tables.

A stranger's label -- what a view, a memory and a page call a body the
observer does not recognise -- is a NOUN PHRASE WHOSE HEAD IS THE BODY:
"the woman with the scar through her eyebrow", "the man in the grey coat",
"the unfamiliar person". Never a bare modifier, an age, a number or a
sentence fragment. Measured 2026-10-20 (tavern probe, chat 1 turn 2): a
summary opening "Forty and weathered by years at sea before the harbour
claimed her" was cut to "the forty" in every view of the player who did not
know her, in the interaction loop ("the forty says: ...") and on the page
("At the corner table the forty shifts the tin candle dish"). The owner's
own cards carried the same class: "the lean", "the tall", "the sharp gaze",
"the weathered flight jacket over", "the tall full-figured who moves like".

The engine has no dictionary and wants none. What it owns is STRUCTURE and
the pack's own closed tables, and those are enough to know where a body
noun is and where there is none. (Two English facts still live in this file
rather than in the pack -- the coordinators `_COORDINATORS` and the plural
fold in `_numeric_piece` -- and a third spaced pack would inherit them;
dressing audit F21.)

* In a language with articles (``compositor.articles`` non-empty, English),
  a clause that OPENS with an article promises a noun. The noun phrase runs
  from the article to the first PHRASE BOUNDARY -- a preposition or
  possessive the pack lists in ``label_dangling``, a ``linking_participle``,
  a conjunction or relative from the ``_BREATH_CONJUNCTIONS`` table other
  than and/or, an and/or that opens a new noun phrase with an article, or a
  number -- and its HEAD is the last word before that boundary.
* A clause that opens with no article is a list of what the eye noticed,
  and a list names a body only three ways: it attaches a feature to a bare
  noun phrase with the pack's own feature connective (the words of its
  ``surface_with`` / ``surface_in`` templates: "Voluptuous succubus WITH
  lavender skin"); it opens on an age that modifies the phrase after it
  ("mid-thirties human male"); or one of its words is one of the pack's own
  generic label heads (``_GENERIC_LABEL_HEADS``: "Woman, forty, weathered").
  Otherwise its leading one-word parts are MODIFIERS of the body ("Tall,
  square-shouldered, ..."), which hang on the pack's generic noun, and the
  rest names nobody: "Forty and weathered by years at sea ...", "Weathered
  flight jacket over a patched pressure suit", "Sharp gaze, clean uniform."
* A NUMBER is never a head, and an age phrase is never one either. The
  engine recognises a number without a word list: digits, and the pack's
  own count, ordinal, numeral and cardinal words (``number_words``), whole
  or as the last piece of a hyphenated word ("mid-forties"); a compound
  that ends on a word is a noun or a modifier built on a number
  ("fifteen-year-old", "six-tailed"). An age coordinated with a word
  ("Forty and weathered") makes that word a modifier: coordination joins
  like with like, and an age said that way is said of the body.
* In a head-final language with no articles (Japanese), the head is the
  LAST word of its clause, and a clause ends on a noun when its last
  character is ideographic or katakana rather than kana inflection -- a
  script fact, not a vocabulary. The body is the last clause of the first
  sentence when the sentence ends on a noun, else the first clause that
  does; an age and its counter alone ("四十歳") are not a noun.

A feature -- the one thing a label may carry beside its noun, and what the
collision ladder widens through -- is a phrase the summary itself attaches
with a boundary word: "with a scar through her eyebrow", "in a grey coat",
"wearing a patched flight jacket". A bare comma part ("short black hair")
could be a feature or a modifier and the engine cannot tell, so it is not
taken; a part the summary attached with a connective is a feature by the
summary's own grammar.

Pure functions over pack data; no name handling here (that is
`agents.common`'s, which strips identity before it cuts).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache

from language_runtime import (compositor_value, current_language_id,
                              language_pack, linguistic, on_packs_reloaded,
                              split_sentences)


class _SentenceSplitter:
    """Where a description's sentences end: `language_runtime.split_sentences`
    under the name and the `split(text, maxsplit)` call this module's readers
    (and `agents.common_names._SENTENCE_END`) already make.

    It was `(?<=[a-z]{3}[.!?])\\s+|(?<=[。！？])`, which split after any
    abbreviation of four letters or more and never after a digit, an acronym
    or a non-ASCII letter -- measured (dressing audit F6, 2026-11-01): "A
    grizzled former Capt. of the harbour guard" was cut at the title, and "A
    stocky dwarf in his 300s. He wears chainmail." ran on into a ladder step
    reading "the stocky dwarf in his 300s. he wears chainmail"."""

    def split(self, text, maxsplit=0):
        return split_sentences(text, maxsplit)

    def __repr__(self):
        return "<referring.SENTENCE_END: language_runtime.split_sentences>"


SENTENCE_END = _SentenceSplitter()

#: A clause boundary inside a sentence: the comma, semicolon and colon of a
#: spaced script, their full-width forms, and a spaced dash.
CLAUSE_MARK = re.compile(r"[,;:、，；：]|\s+[—–]\s+|\s+--\s+")

#: Full-width and ASCII punctuation a stripped name leaves stranded at a
#: clause's edge.
_EDGE_PUNCT = " \t,;:.、。，；：—–-\"'「」()"

#: A word that is a number by itself: digits with their separators.
_DIGITS = re.compile(r"^[\d][\d.,:/-]*$")

#: The characters a head-final clause ends on when it ends on a NOUN:
#: CJK ideographs (both blocks the packs use) and katakana, with the long
#: vowel mark; a clause ending in hiragana ends on inflection -- a verb or
#: an adjective -- and names nothing.
_NOMINAL_END = re.compile(r"[㐀-䶿一-鿿゠-ヿㇰ-ㇿｦ-ﾟ]$")


def _fold(word):
    return re.sub(r"[^\w]", "", str(word or "")).casefold()


def _values(name, language_id):
    # No `except`: a missing key is `LanguagePackError`, the loud failure the
    # loader designed. Swallowed, a renamed `articles` key made `articles()`
    # empty and switched English labels to the head-final rule with no word
    # anywhere (dressing audit F13).
    value = compositor_value(name, language_id)
    # `compositor_value` hands back a read-only mapping proxy, not a dict.
    if isinstance(value, Mapping):
        return tuple(str(v) for v in value.values())
    return tuple(str(v) for v in (value or ()))


#: The two conjunctions that join LIKE with LIKE inside one noun phrase
#: ("tall and powerful", "red or black") rather than opening a new one.
_COORDINATORS = frozenset({"and", "or"})


@dataclass(frozen=True)
class _Tables:
    """Every pack table the grammar reads, for one language."""
    articles: frozenset
    number_words: frozenset
    phrase_openers: frozenset
    participles: frozenset
    conjunctions: frozenset
    generic_heads: frozenset
    feature_connectives: frozenset


def _compute_tables(language_id):
    articles = frozenset(a.casefold() for a in _values("articles", language_id))
    numbers = set()
    for name in ("count_names", "count_words", "ordinal_words",
                 "counter_numerals", "number_words"):
        numbers.update(v.casefold() for v in _values(name, language_id))
    participles = frozenset(
        w.casefold() for w in _values("linking_participles", language_id))
    dangling = {w.casefold() for w in _values("label_dangling", language_id)}
    connectives = set()
    templates = compositor_value("templates", language_id)
    for key in ("surface_with", "surface_in"):
        template = (str(templates.get(key) or "")
                    if isinstance(templates, Mapping) else "")
        for literal in re.split(r"\{[^}]*\}", template):
            for word in literal.split():
                connectives.add(word.casefold())
    return _Tables(
        articles=articles,
        # The pack's word for ONE may be its indefinite article
        # (``count_names`` "1": "a" -- "a figure"), and an article is never a
        # number: read as one, "a scar across one cheek" opened an age-led
        # phrase and the label read "the black-haired and slight a scar"
        # (2026-10-20).
        number_words=frozenset(numbers - articles),
        phrase_openers=frozenset((dangling - articles - _COORDINATORS)
                                 | participles),
        participles=participles,
        conjunctions=frozenset(str(w).casefold() for w in linguistic(
            "agents.common", "_BREATH_CONJUNCTIONS", language_id)),
        generic_heads=frozenset(str(w).casefold() for w in linguistic(
            "agents.common", "_GENERIC_LABEL_HEADS", language_id)),
        feature_connectives=frozenset(connectives),
    )


#: The tables per language, built once. They were rebuilt on EVERY call, and
#: `is_boundary` asks three of them per word: one label ladder cost 378
#: `compositor_value` calls and 7,120 casefolds, 6.29 ms (dressing audit E1,
#: 2026-11-01; 1.51 ms memoized, identical output). Dropped whenever the packs
#: reload (`on_packs_reloaded`), like `language_runtime._linguistic_cached`.
_tables = lru_cache(maxsize=16)(_compute_tables)
on_packs_reloaded(_tables.cache_clear)


def _active():
    """The active story language's tables -- the RESOLVED pack's, so "en-GB"
    and "en" share one entry."""
    return _tables(language_pack(current_language_id.get()).id)


def articles():
    """The pack's determiners, casefolded; empty for a language without."""
    return _active().articles


def head_final():
    """True for a pack whose noun phrases carry the head LAST and promise it
    by no article (Japanese); False for an article language."""
    return not articles()


_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]")


def unspaced(text):
    """Is this text written in an unspaced script, whatever pack is active?
    A Japanese card in an English story is still read head-final: the words
    of an unspaced sentence cannot be counted, cut or capped."""
    letters = re.findall(r"[^\W\d_]", str(text or ""))
    if not letters:
        return False
    return len(_CJK.findall(str(text))) * 2 >= len(letters)


def number_words():
    """Every number word the pack owns: its counts, ordinals and numerals,
    and ``number_words`` -- the rest of the language's cardinals, a closed
    class the pack completes rather than a list that chases prose. Never the
    pack's article (see `_compute_tables`)."""
    return _active().number_words


def _numeric_piece(piece, words):
    p = piece.casefold()
    if not p:
        return False
    if _DIGITS.match(p) or re.match(r"^\d+s$", p):
        return True
    if p in words:
        return True
    # A number word pluralised is an age or a decade: "forties",
    # "twenties", "hundreds".
    if p.endswith("ies") and p[:-3] + "y" in words:
        return True
    return p.endswith("s") and p[:-1] in words


def is_number(word):
    """A numeral or a number word -- "forty", "40", "1.7", "thirty-two",
    "mid-forties", "40s" -- and so never a head noun: an age is a
    measurement of the body, not what the body is. A hyphenated word is a
    number when every piece is or when its LAST piece is (a decade:
    "mid-forties"); a compound that ends on a word has made a modifier or a
    noun of its number ("six-tailed", "one-eyed", "fifteen-year-old" --
    "the gangly fifteen-year-old with scorched cuffs" names a body, where
    "the forty" names nothing)."""
    bare = str(word or "").strip(_EDGE_PUNCT)
    if not bare:
        return False
    words = number_words()
    pieces = [piece for piece in re.split(r"[-\u2010\u2011/]", bare) if piece]
    if not pieces:
        return False
    numeric = [_numeric_piece(piece, words) for piece in pieces]
    return all(numeric) or numeric[-1]


def conjunctions():
    return _active().conjunctions


def phrase_openers():
    """The words that open a phrase attached to a noun: the pack's
    prepositions and possessives (``label_dangling`` less its articles and
    coordinators) and its linking participles."""
    return _active().phrase_openers


def feature_connectives():
    """The words the PACK attaches a feature to a label with -- read off
    its own `surface_with` / `surface_in` templates ("{label} with
    {feature}", "{label} in {worn}"), so a bare noun phrase that attaches a
    feature with one of them has declared where its noun ends."""
    return _active().feature_connectives


def coordinator(word):
    """Is ``word`` one of the two conjunctions that continue a phrase rather
    than open one ("and", "or")?"""
    return _fold(word) in _COORDINATORS


def _measure(word):
    """A number that MEASURES rather than modifies: a bare numeral or number
    word, or a compound of numbers ("1.7", "forty", "thirty-two"). An age
    said with a word in front ("mid-30s", "late-forties") is said as a
    modifier ("a tired, mid-30s woman") and continues the phrase."""
    bare = str(word or "").strip(_EDGE_PUNCT)
    pieces = [piece for piece in re.split(r"[-\u2010\u2011/]", bare) if piece]
    return bool(pieces) and is_number(word) and _numeric_piece(
        pieces[0], number_words())


def is_boundary(word, following=None):
    """Does ``word`` end the noun phrase before it? See the module doc."""
    w = _fold(word)
    if not w:
        return False
    if w in phrase_openers():
        return True
    if w in _COORDINATORS:
        return _fold(following) in articles() if following is not None else False
    if w in conjunctions():
        return True
    return _measure(word)


def content_words(text):
    """The whitespace tokens of ``text`` that are not articles."""
    arts = articles()
    return [w for w in str(text or "").split() if w.casefold() not in arts]


def first_sentence(text):
    """The sentence a descriptor lives in. THE DESCRIPTOR IS IN THE FIRST
    SENTENCE: "A tall, thin, pale, nervous man. He wears wire glasses" ran
    on into "he wears wire" (review round 5, 2026-10-05). A fragment
    ("Tall.") keeps the run, and its further sentences are parts of their
    own (`read`)."""
    head = str(text or "").strip()
    if not head:
        return ""
    sentences = split_sentences(head, 1)
    first = sentences[0] if sentences else ""
    if head_final() or unspaced(head):
        # An unspaced script has no word count to judge a fragment by; its
        # first sentence is its first sentence.
        return first or head
    if first != head and len(content_words(first)) >= 2:
        return first
    return head


def clause_parts(sentence):
    """The clauses of one sentence, in order, edges cleaned, empties out."""
    parts = [p.strip(_EDGE_PUNCT) for p in CLAUSE_MARK.split(str(sentence or ""))]
    return [p for p in parts if p]


def opens_with_article(text):
    words = str(text or "").split()
    return bool(words) and words[0].casefold() in articles()


def noun_phrase(words):
    """The noun phrase at the start of ``words`` (article already off): every
    word up to the first boundary. Empty when the first word is one. A
    number OPENS a phrase as a modifier ("40 year old woman", "six foot
    man") and ENDS one as a measurement after it ("machine roughly 1.7
    meters tall")."""
    out = []
    for i, w in enumerate(words):
        following = words[i + 1] if i + 1 < len(words) else None
        if is_boundary(w, following) and not (i == 0 and is_number(w)):
            break
        out.append(w)
    return out


def head_of(words):
    """The head noun of the noun phrase opening ``words``, or "" when the
    phrase is empty or ends on a number."""
    phrase = noun_phrase(words)
    if not phrase:
        return ""
    head = phrase[-1]
    if is_number(head) or not re.search(r"[^\W\d_]", head):
        return ""
    return head


def nominal(clause):
    """Head-final: does this clause end on a noun (ideograph or katakana),
    and is it more than a number?"""
    text = str(clause or "").strip(_EDGE_PUNCT)
    if not text or not _NOMINAL_END.search(text):
        return False
    # A clause that is nothing but a number and its counter ("四十歳" less
    # its numerals) ends on an ideograph and still names nobody. Which
    # characters are numerals is the script's fact (`unicodedata.numeric`
    # knows 四 and 十 as it knows 4), so a Japanese card read in an English
    # story is judged the same way; the pack's number words cover the rest.
    stripped = text
    for numeral in sorted(number_words(), key=len, reverse=True):
        stripped = stripped.replace(numeral, "")
    stripped = "".join(ch for ch in stripped
                       if unicodedata.numeric(ch, None) is None
                       and not ch.isspace() and ch not in ".,")
    return len(stripped) > 1 or stripped == text


def head_final_clause(sentence):
    """Head-final: the clause that carries the body noun -- the last clause
    when the sentence ends on a noun, else the first clause that does; ""
    when none does."""
    parts = clause_parts(sentence)
    if not parts:
        return ""
    if nominal(parts[-1]):
        return parts[-1]
    for part in parts:
        if nominal(part):
            return part
    return ""


@dataclass
class Reading:
    """What the first sentence of an appearance summary says about the body
    it describes, before any name is stripped from it."""
    sentence: str = ""
    parts: list = field(default_factory=list)
    #: The clause the body is named in (a run of one-word parts joined to
    #: the part that carries the noun), article included.
    head_clause: str = ""
    #: Whether the head clause opened with an article -- a promise of a noun.
    promised: bool = False
    #: The head noun the clause promises, "" when it promises none or the
    #: promised head is a number.
    head: str = ""
    #: Unpromised only: the modifiers a bare list opens on -- its leading
    #: one-word parts and two-word coordinations ("Tall, square-shouldered,
    #: ..."; "long, black-slick and eel-jointed, ...") -- which hang on the
    #: generic noun, or a creature's own.
    modifiers: list = field(default_factory=list)
    #: The noun phrase itself: the words of the head clause up to the
    #: boundary after the head (modifiers included), article off.
    phrase: list = field(default_factory=list)
    #: The words of the head clause AFTER the noun phrase -- where the
    #: phrases the clause attaches to its noun are ("with six tails and
    #: amber eyes"). Empty when no head was found.
    tail: list = field(default_factory=list)
    #: The words a label is cut from, article off: the modifiers, the noun
    #: phrase and its tail. `phrase` is a prefix of it.
    words: list = field(default_factory=list)
    #: The parts of the first sentence after the head clause that the
    #: summary attached with an opener, a participle or a coordinator --
    #: feature phrases.
    attached: list = field(default_factory=list)


def read(summary):
    """Read the first sentence of ``summary`` for its body noun and its
    attached features. Spaced scripts only; see `head_final_clause` for the
    other kind. Where the first sentence is a fragment and the run goes on
    (`first_sentence`), each further sentence is a part of its own."""
    sentence = first_sentence(summary)
    parts = _join_promised_nouns([part for piece in split_sentences(sentence)
                                  for part in clause_parts(piece)])
    reading = Reading(sentence=sentence, parts=parts)
    if not parts:
        return reading
    promised = opens_with_article(parts[0])
    reading.promised = promised
    taken = 1
    if promised:
        # THE HEAD CLAUSE IS THE DESCRIPTOR: the clauses after it are detail
        # a label has no room for, and running them together made "the
        # county surveyor of thirty small" (Hollin Mill, 2026-09-15). BUT A
        # COMMA BETWEEN ADJECTIVES IS NOT A CLAUSE BREAK: "a short,
        # thick-forearmed man" cut at its comma read "the short" in every
        # view and memory of him for eight beats (playerless Aldermill
        # round 9, 2026-09-23), and "A tall, slim, youthful-looking man"
        # stopped at two words read "the tall slim" (Kirinoura, scratch
        # chat 167, 2026-10-05). A clause that promises a noun runs on
        # through its one-word parts to the part that carries more than
        # one content word, which is where the noun is.
        while taken < len(parts) and len(content_words(parts[taken - 1])) < 2:
            taken += 1
        words = " ".join(parts[:taken]).split()[1:]
        reading.phrase = noun_phrase(words)
        reading.head = head_of(words)
        # A promised phrase whose head is an AGE ("A forty-year-old in a
        # grey coat") names no noun, but it is still the body's phrase, so
        # what it attaches is the body's: the label is the generic person
        # carrying it.
        aged = bool(reading.phrase) and is_number(reading.phrase[-1])
        reading.tail = (words[len(reading.phrase):]
                        if reading.head or aged else [])
        reading.words = words
    else:
        # A BARE LIST OPENS ON ITS MODIFIERS: each leading part that is one
        # word, or two words on a coordinator, describes the body; an age
        # alone ("Thirty, lean, ...") is passed over, and an age coordinated
        # with a word gives the word ("Forty and weathered by years at sea"
        # -> "weathered"). The first part of any other shape -- a noun
        # phrase ("short black hair"), prose -- ends the run: run on, a bare
        # list took a feature for its noun, "the tall square-shouldered
        # short black hair" (review, 2026-10-05).
        taken = 0
        heads = generic_heads()
        while taken < len(parts):
            words = parts[taken].split()
            if len(words) == 1 and _fold(words[0]) in heads:
                # A word the pack itself heads labels with IS the noun.
                reading.head = words[0]
                reading.phrase = reading.modifiers + words
                reading.words = list(reading.phrase)
                taken += 1
                break
            modifiers, continues = _list_modifiers(parts[taken])
            reading.modifiers.extend(modifiers)
            if not continues:
                taken += bool(modifiers)
                break
            taken += 1
        if not reading.head and taken < len(parts):
            _bare_noun_phrase(reading, parts[taken].split())
            if reading.head:
                taken += 1
        taken = max(taken, 1)
        if not reading.words:
            reading.words = " ".join(parts[:taken]).split()
    reading.head_clause = " ".join(parts[:taken])
    for part in parts[taken:]:
        words = part.split()
        if words and attaches(words[0]):
            reading.attached.append(part)
    return reading


def _bare_noun_phrase(reading, words):
    """The ways a part of a bare list names its noun (module doc): a feature
    attached with the pack's own connective after a run of plain words, an
    age opening the phrase it modifies, or a phrase ending on one of the
    pack's own generic label heads ("Tall woman, forty"). A part that opens
    with an article inside a bare list ("Forty. A weathered woman.") is
    held to the first and the last of those, never to its open noun phrase,
    which in a later sentence runs on into the verb ("A thin white scar
    cuts clean through ..." names nobody). Sets ``head``, ``phrase``,
    ``tail`` and ``words`` on ``reading`` when one holds."""
    articled = bool(words) and words[0].casefold() in articles()
    if articled:
        words = words[1:]

    def _take(phrase, tail):
        reading.phrase = reading.modifiers + phrase
        reading.tail = list(tail)
        reading.words = reading.phrase + reading.tail

    connectives = feature_connectives()
    at = next((i for i, w in enumerate(words) if _fold(w) in connectives), -1)
    if at > 0 and not any(is_number(w) for w in words[:at]) and not any(
            is_boundary(w, words[i + 1]) for i, w in enumerate(words[:at])):
        head = head_of(words[:at])
        if head:
            reading.head = head
            _take(words[:at], words[at:])
            return
    if (not articled and len(words) >= 2 and is_number(words[0])
            and not is_boundary(words[1], words[2] if len(words) > 2 else None)
            and not coordinator(words[1])):
        phrase = noun_phrase(words)
        head = head_of(words)
        if head and len(phrase) >= 2:
            reading.head = head
            _take(phrase, words[len(phrase):])
            return
    phrase = noun_phrase(words)
    if phrase and _fold(phrase[-1]) in generic_heads():
        reading.head = phrase[-1]
        _take(phrase, words[len(phrase):])


def _join_promised_nouns(parts):
    """A part that ends one word after an article inside it has not reached
    the noun that article promised -- "...man with an intense, restless
    presence", "...man with a round, jutting belly" -- so the comma was one
    between adjectives, and the next part carries the noun. Joined. The
    article that OPENS a part is the clause's own promise and is left to
    the run-on rule, else "A tall, slim, ..." would close on "slim"."""
    arts = articles()
    out = list(parts)
    i = 0
    while i + 1 < len(out):
        words = out[i].split()
        following = out[i + 1].split()
        if (len(words) >= 3 and words[-2].casefold() in arts
                and following and not is_boundary(following[0])
                and following[0].casefold() not in arts):
            out[i] = out[i] + " " + out[i + 1]
            del out[i + 1]
            continue
        i += 1
    return out


def _list_modifiers(part):
    """``(modifiers, continues)`` for one part of a bare list: the words it
    gives the body as modifiers, and whether the list may run on past it.
    One word is a modifier; an age alone gives nothing and the list runs
    on; ``<a> <and|or> <b>`` gives both words, or the one that is not an
    age, and the list runs on only if that was the whole part."""
    words = str(part or "").split()
    if not words:
        return [], True
    if all(is_number(w) for w in words):
        return [], True
    if len(words) == 1:
        word = words[0]
        return ([word] if re.search(r"[^\W\d_]", word) else []), True
    phrase = noun_phrase(words)
    if len(phrase) == 3 and coordinator(phrase[1]) and not any(
            is_boundary(w) and not is_number(w) for w in (phrase[0], phrase[2])):
        sides = [w for w in (phrase[0], phrase[2]) if not is_number(w)]
        modifiers = phrase if len(sides) == 2 else sides
        return list(modifiers), len(phrase) == len(words)
    return [], False


def generic_heads():
    """The words the pack heads its own generic labels with
    (``_GENERIC_LABEL_HEADS``) -- the person nouns the engine owns."""
    return _active().generic_heads


def attaches(word):
    """Does a part opening on ``word`` attach to the noun before it as a
    feature -- an opener ("with", "in", "her"), a linking participle
    ("wearing") or a coordinator ("and")? A relative or conjunction ("who",
    "that", "when") opens a clause about conduct, which is not a feature."""
    return _fold(word) in phrase_openers() or coordinator(word)


def splits_tail(word):
    """Does ``word`` begin a NEW phrase inside the tail that follows a noun?
    A coordinator, a relative or conjunction, or a linking participle; a
    preposition inside a phrase ("in a coat sewn FROM repaired coats")
    continues it."""
    w = _fold(word)
    if not w:
        return False
    if w in _COORDINATORS or w in conjunctions():
        return True
    return w in _active().participles


def cuts_phrase(word):
    """Does ``word`` end the label's own phrase: a linking participle
    introducing a phrase the cap would halve, or a relative or conjunction
    opening a clause? Coordinators continue ("with silver hair and sharp
    eyes")."""
    w = _fold(word)
    if not w or w in _COORDINATORS:
        return False
    return w in conjunctions() or w in _active().participles


def names_a_body(summary):
    """Does this appearance summary name what the body IS, by the rule
    above? The card warning's question, asked of the raw summary."""
    text = str(summary or "").strip()
    if not text:
        return False
    if head_final() or unspaced(text):
        return bool(head_final_clause(first_sentence(text)))
    return bool(read(text).head)
