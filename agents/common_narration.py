"""The narrator's own voice, measured: tics, rhythm, recycled shingles,
narration person/tense counts and the pronoun-fidelity check.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from language_runtime import UNSPACED_SCRIPT, script_of
from story.character_schema import _UNSPACED_SCRIPT, name_boundary_pattern

from agents.common_base import _ling
from agents.common_names import (
    _SENTENCE_SPLIT,
    _countable_word_units,
    _name_token_floor,
    _name_tokens,
    _pronoun_group,
    _pronoun_to_group,
    split_sentences,
)

#: Where one phrase stops and the next begins. A tic is something the
#: narrator SAYS; a run of words that crosses a stop, a comma or a dash is
#: two half-phrases welded at a boundary the prose put there on purpose.
#:
#: A TOKEN RULE, NOT A SPLIT RULE (A2). `[^A-Za-z']+` as a separator made
#: every character of an unspaced script a separator too, so a Japanese
#: sentence produced no words at all and the tic report was empty on every
#: beat of such a story. Matching the units instead reads a Latin run
#: exactly as the split did -- maximal runs of the same class -- and reads a
#: character of an unspaced script as its own unit, which is the same trade
#: `_countable_word_units` makes and for the same reason.
_PHRASE_TOKEN = re.compile(r"[A-Za-z']+|" + _UNSPACED_SCRIPT.pattern)
#: The punctuation a phrase cannot run across. Fullwidth marks belong here
#: for the same reason (A2): the class is "the prose put a stop here", and a
#: Japanese sentence marks its stops with 。、 rather than with . and , --
#: without them a whole paragraph was one segment, so every "run of words no
#: punctuation interrupts" crossed every clause boundary in it. No English
#: text carries these characters, so the Latin answer is unchanged.
_SEGMENT_BREAK = re.compile(r"[.!?;:,()—–\"“”\n。、；：！？（）「」『』]+")


def _phrase_segments(text):
    """`text` split into the runs of words no punctuation interrupts, each as
    a list of (original-case) words."""
    return [seg for seg in
            (_PHRASE_TOKEN.findall(part)
             for part in _SEGMENT_BREAK.split(str(text or "")))
            if seg]


def _named_tokens(blocks):
    """The lower-cased words these blocks capitalise where a sentence does not
    require it -- i.e. the people and places being NAMED.

    A NAME IS NOT A TIC. Measured, run 2026-09-05C `multitude` turn 3 (PM18):
    `overused_phrases: ["bench ilsabet roon", "corin ashe froze", "out on
    the"]`, handed to a narrator that had two `Proper noun from view missing
    in narrator prose` warnings in the same run -- one channel asking it to
    stop naming the people in the room while another counted the times it
    did. The rate worsens with cast size, because with six named bodies the
    frequent runs are increasingly name-adjacent.

    Decided from the prose itself rather than from a cast list, so it holds
    for a place, a ship or a title the caller never passes: a capital that a
    segment start does not explain is doing referring work.
    """
    named = set()
    for block in blocks:
        for segment in _phrase_segments(block):
            for word in segment[1:]:
                if word[:1].isupper() and word.lower() != "i":
                    named.add(word.lower())
    return named


def _join_units(units):
    """Units back into the phrase they were read from: a space between two
    words of a spaced script, none between two characters of an unspaced
    one. `" ".join` spelled a Japanese phrase one character at a time --
    the narrator was handed "っ て い る" to vary (agents_common audit F10).
    Identical to `" ".join` for Latin units."""
    out = ""
    for unit in units:
        if out and not (_UNSPACED_SCRIPT.match(out[-1:])
                        and _UNSPACED_SCRIPT.match(unit[:1])):
            out += " "
        out += unit
    return out


def _all_inflection(units):
    """Whether every unit is hiragana: particles and inflection, the
    caseless script's analogue of a function-word run. `_TIC_STOPWORDS` is
    the same English set in both packs, so it never excluded -ている."""
    return bool(units) and all(script_of(u[:1]) == "hiragana" for u in units)


def _phrase_unit_ngrams(text, n):
    """The lower-cased n-unit windows of `text`, as tuples of units, none of
    them spanning a punctuation boundary."""
    out = []
    for segment in _phrase_segments(text):
        words = [w.lower() for w in segment]
        out.extend(tuple(words[i:i + n]) for i in range(len(words) - n + 1))
    return out


def _phrase_ngrams(text, n):
    """Lower-cased n-word phrases of `text`, none of them spanning a
    punctuation boundary."""
    return [_join_units(units) for units in _phrase_unit_ngrams(text, n)]


# Content words whose repetition is a genuine tic; function-word runs ("in the
# middle of") are not. A phrase must carry at least one of these to be flagged.


def _overused_phrases(recent_prose, current_prose="", n=3, min_hits=2, cap=12,
                      forced=""):
    """The narrator's own recurring set-dressing tics (Fable A4): short phrases
    that recur across recent turns' prose -- "the clock ticks", "thumps her tail
    once", "the fire settles". Fed back to the narrator as a ban list so it
    varies them, and used by the repetition check below.

    A phrase counts once per prose block it appears in (so a within-block
    repeat isn't inflated), must contain a content word, and must recur in at
    least `min_hits` blocks including the current draft when supplied.

    THE SLOTS HOLD PHRASES, NOT SHINGLES. The window is fixed at `n` words,
    so the containment filter below could never fire -- no three-word phrase
    contains another -- and a single recurring sentence filled the list with
    its own overlapping thirds. Measured, run 2026-09-05C `quiet` turn 20
    (PQ8): seven of ten slots were overlapping trigrams of one phrase
    ("there was too", "was too little", "there was too little to make out"),
    which spends the ban list on one tic and hides every other. Overlapping
    hits inside one segment are therefore grown back into the whole phrase
    they came from before the list is filled.

    And a phrase that NAMES somebody is not a tic (`_named_tokens`, PM18).

    `forced` is THIS beat's composed view -- the sentences the engine writes
    and the narrator is required to render. A phrase the view itself contains
    is the engine's wording, not the narrator's tic, and banning it asks for
    a page that contradicts its own ground truth. Measured (quiet, PQ8): the
    repetition warning fired twice on a beat whose recurring phrase the
    composer had put in the view every time, and the prose published
    unchanged both times because there was nothing the narrator could
    legitimately do about it.
    """
    blocks = [p for p in list(recent_prose or []) + [current_prose] if p]
    if len(blocks) < min_hits:
        return []
    engine_said = set()
    for segment_text in ([forced] if isinstance(forced, str) else list(forced or ())):
        if str(segment_text or "").strip():
            engine_said |= set(_phrase_ngrams(str(segment_text), n))
    named = _named_tokens(blocks)
    counts = {}
    for block in blocks:
        for words in set(_phrase_unit_ngrams(block, n)):
            phrase = _join_units(words)
            if all(w in _ling("_TIC_STOPWORDS") for w in words):
                continue
            if _all_inflection(words):
                continue
            if any(w in named for w in words):
                continue
            if phrase in engine_said:
                continue
            counts[phrase] = counts.get(phrase, 0) + 1
    hits = {p for p, c in counts.items() if c >= min_hits}
    if not hits:
        return []
    # Grow each run of overlapping hits back into the phrase it is a window
    # onto. Done per segment, so a grown phrase is one the prose actually
    # contains and never a weld across a boundary.
    grown = set()
    for block in blocks:
        for segment in _phrase_segments(block):
            words = [w.lower() for w in segment]
            start = None
            for i in range(len(words) - n + 2):
                window = _join_units(words[i:i + n])
                if i <= len(words) - n and window in hits:
                    start = i if start is None else start
                    continue
                if start is not None:
                    grown.add(_join_units(words[start:i + n - 1]))
                    start = None
    # Prefer the longest/most-specific phrases; drop a phrase fully contained
    # in a longer flagged one so "clock ticks" and "the clock ticks" don't both
    # list.
    kept = []
    for phrase in sorted(grown, key=len, reverse=True):
        if not any(phrase in longer for longer in kept):
            kept.append(phrase)
    return kept[:cap]


#: A TRAILING PARTICIPIAL PHRASE, as shape rather than as vocabulary: a
#: comma, then a word carrying English's participial morphology, then the
#: rest of the sentence with no further clause boundary. It is the cadence
#: the ban lists were reaching for and kept missing -- review B29 measured
#: the tell migrating to words no list held ("steady" 48 times, "unyielding"
#: 11), because the tell was never in the words. Morphology is a fact about
#: the writing system; a list of participles is a promise that English can be
#: enumerated.
_TRAILING_PARTICIPIAL_RE = re.compile(
    r",\s+\w+(?:ing|ed)\b[^,;:]*[.!?\u2026]*[\"\'\u201d\u2019)\]]*\s*$")
#: Where a sentence opens on a quotation -- the attribution, if any, then
#: follows the line instead of announcing it.
_QUOTE_OPENS_RE = re.compile(r'^[\s\u2014\u2013-]*["\u201c]')
_ANY_QUOTE_RE = re.compile(r'["\u201c\u201d]')


def _closer_class(sentence):
    """Which SHAPE a sentence ends on -- dialogue, a trailing participial
    phrase, or a plain statement. Three classes, because they are the three
    ways a beat can be closed off and the engine can tell them apart from the
    punctuation and the morphology alone."""
    text = str(sentence or "").strip()
    if not text:
        return ""
    # Double quotes only: an apostrophe is not a closing quotation mark, and
    # a sentence ending on one is much the commoner case.
    if text.rstrip(".!?\u2026 ").endswith(('"', "\u201d")):
        return "dialogue"
    if _TRAILING_PARTICIPIAL_RE.search(text):
        return "participial"
    return "statement"


def _rhythm_report(recent_prose, current_prose=""):
    """The narrator's own recent CADENCE, measured (review D11, after B29).

    A ban list can only name the words somebody already noticed, and the tell
    is not in the words: when narrator.txt banned five adverbs and eight
    gestures, the same flat cadence came back in vocabulary no list held.
    What recurs is structural -- sentences of one length, a participial
    phrase hung off every second comma, every line of dialogue announced
    before it is spoken, four beats closing the same way -- and every one of
    those is countable without deciding that any particular word is bad.

    So this REPORTS, in the narrator's own payload, what its last few pages
    actually did. No threshold decides anything here and nothing is banned:
    the numbers are the evidence, and a writer who can see that all four of
    their last closers were participial does not need to be told which
    participles to avoid.

    `repeated_closer` is the one derived judgment, and it is unanimity rather
    than a cap: EVERY prose in the window closing on the same shape. That is
    the state `agents/narration.py` warns on.

    Empty (never a shell of zeroes) when there is nothing to measure -- an
    empty field is a key the model reads and discards, and one carrying
    `{"sentences": 0}` argues for a rule with no referent.
    """
    blocks = [str(p) for p in list(recent_prose or []) + [current_prose]
              if str(p or "").strip()]
    if not blocks:
        return {}
    lengths, trailing, quoted, quote_leads, closers = [], 0, 0, 0, []
    for block in blocks:
        sentences = [s.strip() for s in split_sentences(block, _SENTENCE_SPLIT)
                     if s and s.strip()]
        if not sentences:
            continue
        for sentence in sentences:
            # Counted in the sentence's own script (the A2 unit), so a
            # Japanese page reports a length rather than "one word".
            units = _countable_word_units(sentence)
            if not units:
                continue
            lengths.append(units)
            if _TRAILING_PARTICIPIAL_RE.search(sentence):
                trailing += 1
            if _ANY_QUOTE_RE.search(sentence):
                quoted += 1
                if _QUOTE_OPENS_RE.match(sentence):
                    quote_leads += 1
        closer = _closer_class(sentences[-1])
        if closer:
            closers.append(closer)
    if not lengths:
        return {}
    ordered = sorted(lengths)
    report = {
        "sentences": len(lengths),
        "words_per_sentence": {
            "shortest": ordered[0],
            "median": ordered[len(ordered) // 2],
            "longest": ordered[-1],
        },
        "trailing_participial_sentences": trailing,
        "quoted_sentences": quoted,
        # The attribution announced the line rather than following it.
        "attribution_before_the_quote": quoted - quote_leads,
        "closers": closers,
    }
    if len(closers) > 1 and len(set(closers)) == 1:
        report["repeated_closer"] = closers[0]
    return report


#: Words that carry no content in a recycling comparison: the attribution
#: formula the composer emits around every line, and the label-shaped words a
#: descriptor is built from. Stripped before shingling, because a shingle is
#: supposed to catch a RECYCLED BEAT and these catch the same person speaking
#: twice.
#:
#: Measured, Enterprise run turns 8-15: four of five "reuse" findings were the
#: attribution itself -- `spare upright man says in a`, `the spare upright man
#: speaks in`, `the tall turns back to the`, `he turns in the command chair`.
#: Only one was real prose recycling. An unrecognised body renders by its
#: appearance ("the spare upright man"), which is FOUR words of a six-word
#: window before any content reaches it, so two unrelated sentences about one
#: stranger collide on the label alone.
_SHINGLE_STOPWORDS = frozenset({
    "says", "said", "say", "speaks", "spoke", "asks", "asked", "replies",
    "replied", "adds", "added", "answers", "answered", "in", "a", "an",
    "the", "his", "her", "their", "its", "with", "voice", "tone", "and",
    "then", "to", "of", "at", "on", "he", "she", "they", "it",
})


def _word_shingles(text, n=6, *, labels=()):
    """Six-word runs of CONTENT, for the recycled-prose comparison.

    `labels` are the display names in play this beat -- an unrecognised body's
    descriptor is long and recurs in every sentence about them, so leaving it
    in makes the label the match rather than the prose. Stripping the
    attribution vocabulary alongside it leaves the shingle measuring what it
    was built to measure: whether the BEAT was rewritten from an earlier one.
    """
    lowered = str(text or "").lower()
    for label in sorted((str(x or "").lower() for x in labels or ()),
                        key=len, reverse=True):
        if len(label) > 2:
            lowered = lowered.replace(label, " ")
    # Units in the prose's own script (A2): `[a-z0-9']+` returns ONE token
    # for a whole Japanese clause, so a six-token shingle spanned six
    # clauses and the recycled-prose comparison never matched anything.
    # A character of an unspaced script is its own unit; Latin prose
    # tokenises exactly as before.
    words = [w for w in re.findall(r"[a-z0-9']+|" + _UNSPACED_SCRIPT.pattern,
                                   lowered)
             if w not in _SHINGLE_STOPWORDS]
    # Joined as written (`_join_units`): the same set either way, so every
    # comparison is unchanged, and a shingle handed to the narrator reads
    # "の外を見てい", never "の 外 を 見 て い" (agents_common audit F10).
    return {
        _join_units(words[i:i + n])
        for i in range(len(words) - n + 1)
    }

def _already_established_phrases(view, recent_prose, limit=12):
    """Deterministic overlap between THIS turn's raw view and the narrator's
    own recent prose.

    The narrator's job of "don't re-catalog what's unchanged" requires
    knowing what it already said, and having the model compare two blobs of
    prose itself is unreliable; this hands it a concrete, computed list.

    THIS DOCSTRING USED TO SAY the view re-describes the full room every
    turn because perception is "a stateless sensory filter with no memory of
    prior turns". That stopped being true when the composer began keeping a
    standing ledger: `render_view` suppresses standing state this observer
    was already given, so an ordinary beat's view has little left to overlap
    with. The claim survived in the narrator sheet as well, where it argued
    for a rule against a behaviour that no longer happens.

    What is actually true, measured over 2,294 stored beats in every chat on
    disk (2026-08-23): this returns something on 25.8% of them, and the rate
    is a property of the STORY rather than of the corpus -- 60% in chats 10
    and 12, 14-20% in the long-running ones. So the field is neither dead nor
    ordinary; it is emitted only when non-empty, and the sheet block it
    governs now says what an absent list means.
    """
    view_shingles = _word_shingles(str(view or ""))
    if not view_shingles:
        return []
    hits = set()
    for prev in recent_prose or []:
        hits |= (view_shingles & _word_shingles(prev))
    return sorted(hits)[:limit]

#: A doubled opening mark makes the paired pattern match an EMPTY span and
#: desynchronise every quote after it on the line -- observed live. Folded to
#: one mark before pairing rather than special-cased afterwards.
#: An opening mark with no partner, running to end of line. Applied only after
#: the paired passes, so it can only ever catch what is genuinely unclosed.
# Third-person player evidence comes almost entirely from the player's NAME
# used as a proper noun; pronouns are inherently ambiguous ("her"/"him"/
# "them" nearly always refer to OTHER people in the scene). We therefore
# count only subjective-form player pronouns and never object/possessive
# ones -- and even those only survive as a tiebreak once hysteresis in
# _resolve_narration_person guards against a lone token flipping the whole
# campaign's established person.

#: An HTML-style tag: `<i>`, `</i>`, `<em>` -- the italics the narrator is
#: allowed, and nothing a voice detector should read as a word.
_MARKUP_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9]*[^<>]*>")


def _narrative_outside_quotes(text):
    """`text` with quoted dialogue removed, in the ACTIVE story pack's quote
    marks. Everything a speaker says is somebody else's grammar: a "you" inside
    a spoken line addresses a character rather than the reader, and a spoken
    verb is in whatever tense that character is speaking in. Both of the
    whole-draft detectors below score the narrating voice only, so both start
    here.

    Whatever quote mark is left opened dialogue that never closed, so the rest
    of the line is dialogue too. Folded in here rather than guarded at the call
    sites, because a guard that must be remembered will be forgotten and this
    one was: the paired pattern needs a closing mark, so an unterminated quote
    let every "I" and "my" inside the speech vote on how the NARRATION should
    read. Rare and decisive -- 11 of 2163 live player turns change verdict, and
    one of them latched a whole story into first person.
    """
    # MARKUP IS NOT A WORD. The narrator may italicise ("<i>...Murrow...
    # tonight...</i>" for a line heard in pieces), and the tag name `i`
    # matched the first-person pronoun: a third-person page with no "I" in
    # it was reported as first person (scratch play 2026-09-14, chat 2 turn
    # 1: "2 first / 0 second / 0 third"). Tags are stripped before either
    # detector reads the voice.
    narrative = _MARKUP_TAG_RE.sub(" ", str(text or ""))
    narrative = _ling("_NARRATION_DOUBLED_QUOTE_RE").sub('"', narrative)
    narrative = _ling("_NARRATION_QUOTE_RE").sub(" ", narrative)
    narrative = _ling("_NARRATION_SQUOTE_RE").sub(" ", narrative)
    return _ling("_NARRATION_DANGLING_QUOTE_RE").sub(" ", narrative)


def _narration_person_counts(raw_input, player_name=None, player_pronouns=None):
    """Weighted first/second/third-person evidence from the player's own
    phrasing this turn, after stripping quoted dialogue (a "you" inside a
    spoken line addresses another character, not the player's narrating
    voice). Precision fixes over a naive word count:

    - Player-name parts are matched CASE-SENSITIVELY as proper nouns, so a
      character named "Will"/"Mark"/"Grace"/"Rose" no longer collects
      spurious third-person hits from the ordinary words "will"/"mark"/etc.
    - Only subjective-form player pronouns (he/she/they) are counted, and
      each distinct pronoun string is counted once -- so an object/possessive
      pronoun referring to someone else ("I gave her the key") and duplicate
      dict values (obj == poss == "her") no longer masquerade as the player
      being narrated in third person.
    """
    return _person_marker_counts(_narrative_outside_quotes(raw_input),
                                 player_name, player_pronouns)


def _person_marker_counts(narrative, player_name=None, player_pronouns=None):
    """`_narration_person_counts` over narrative that is ALREADY outside
    quoted dialogue -- one sentence of it, or all."""
    counts = {
        "first": len(_ling("_FIRST_PERSON_RE").findall(narrative)),
        "second": len(_ling("_SECOND_PERSON_RE").findall(narrative)),
        "third": 0,
    }
    for part in _name_tokens(player_name):
        # Case-sensitive, and only for parts written as a proper noun; a
        # lowercase name can't be told apart from the common word it collides
        # with, so we decline to guess and let the fallback hold.
        #
        # AN UNSPACED SCRIPT HAS NO CASE TO READ, and writes the same name in
        # fewer characters (A2): the Latin tokenizer found no parts at all in
        # a Japanese name, `\b` would not have matched beside a particle, and
        # three characters is a whole family name. So the token floor is
        # `_name_token_floor`'s, the boundary is `name_boundary_pattern`'s,
        # and the proper-noun test applies only where case exists. Latin
        # names count exactly as before.
        unspaced = bool(_UNSPACED_SCRIPT.match(part[:1]))
        if len(part) < _name_token_floor(part):
            continue
        if not unspaced and not part[:1].isupper():
            continue
        counts["third"] += len(
            re.findall(name_boundary_pattern(part), narrative))
    seen_pronouns = set()
    for pron in (player_pronouns or {}).values():
        pron = str(pron or "").strip().lower()
        if pron in _ling("_THIRD_SUBJECT_PRONOUNS") and pron not in seen_pronouns:
            seen_pronouns.add(pron)
            counts["third"] += len(re.findall(
                name_boundary_pattern(pron), narrative, re.IGNORECASE))
    return counts


def _check_pronoun_fidelity(prose, cast_pronouns):
    """Third-person pronoun flips the narrator prose commits against a cast
    member's canonical pronouns (W6).

    The PRONOUN CONSISTENCY prompt rule reduces but does not enforce this --
    a he/him character still picked up a "her" in live play. Deliberately
    narrow: a clause must OPEN with exactly one known cast name and then use a
    pronoun from a different paradigm, so the named subject is the only
    possible referent. Anything looser (a second name in the clause, a bare
    pronoun in a following sentence, an unnamed role noun) is left alone --
    a false positive costs a needless full narrator rewrite.
    """
    if not prose or not isinstance(cast_pronouns, dict):
        return []

    # name token -> (canonical name, group). Good prose drops to a surname or
    # first name alone after the first mention, so each word of a multi-word
    # name is a referent in its own right. A token two cast members share is
    # dropped: it no longer identifies one of them.
    token_owner = {}
    for name, pronouns in cast_pronouns.items():
        group = _pronoun_group(pronouns)
        canonical = str(name or "").strip()
        if not group or not canonical:
            continue
        for token in _name_tokens(canonical):
            if len(token) < _name_token_floor(token):
                continue
            # The capital is what separates a name part from an ordinary word
            # it sits beside -- in a script that HAS capitals. Demanding one of
            # a caseless script drops every token, which is how this guard came
            # to return [] for a Japanese cast before consulting a pronoun at
            # all. Same reasoning as `_player_name_forms`.
            if not _UNSPACED_SCRIPT.match(token[:1]) and not token[:1].isupper():
                continue
            # Names that are also ordinary capitalized English words. A cast member called
            # one of these can't be told apart from the common word, so we decline to score
            # their clauses rather than burn a rewrite on "Will you hand him the padd".
            if token.lower() in _ling("_AMBIGUOUS_NAME_WORDS"):
                continue
            # None marks a token already shared: it stays dropped for a third
            # holder and every one after (a family under one surname).
            if token not in token_owner:
                token_owner[token] = (canonical, group)
            elif token_owner[token] and token_owner[token][0] != canonical:
                token_owner[token] = None
    token_owner = {t: v for t, v in token_owner.items() if v}
    if not token_owner:
        return []

    # A pronoun inside quoted dialogue belongs to the speaker talking about
    # whoever they mean -- often someone the clause never names -- so it can't
    # be scored against the clause's named subject.
    scan = _ling("_NARRATION_QUOTE_RE").sub(" ", prose)

    warnings = []
    flagged = set()
    for sentence in split_sentences(scan, _SENTENCE_SPLIT):
        for clause in _ling("_CLAUSE_SPLIT").split(sentence):
            # MEASURED BEFORE ENFORCING, because this warning's prefix is in
            # `_ENFORCEABLE_PREFIXES` -- which since 2026-09-06 buys no rewrite
            # at all: narration blocks on being parseable JSON and on nothing
            # else, so a false positive costs a note on the step and the list
            # is a partition of the warnings, not a price (E12). Replayed over
            # every stored narrator variant in the live
            # database (2,350 with prose, 69,589 clauses): 0 clauses tokenise
            # differently. `_NAME_TOKEN_RE` opens with the same `[A-Za-z']+`,
            # so the English answer is unchanged by construction and the whole
            # of the new exposure is in scripts where this guard returns
            # nothing at all today.
            words = _name_tokens(clause)
            if len(words) < 2:
                continue
            present = {token_owner[w] for w in words if w in token_owner}
            if len(present) != 1:
                continue
            canonical, group = next(iter(present))
            # The name must OPEN the clause: only then is it unambiguously the
            # subject the following pronoun refers back to.
            head = next(i for i, w in enumerate(words) if w in token_owner)
            if head > 1:
                continue
            # A POSSESSIVE name is not the clause's SUBJECT, so a pronoun after
            # it does not refer back to that name. "Sarah Moon's orders reach
            # him" has `orders` as its subject and `him` as an object naming
            # somebody else -- live, chat 84 t13, where `him` was the guard
            # standing in the room and this fired an enforceable mismatch
            # against a doctor who was not its referent. The check cannot see
            # the guard at all: he is a background presence, not registered
            # cast, so `present` held exactly one name and the clause looked
            # unambiguous. Declining on the possessive costs a miss on
            # "Vorne's hand trembles as she reaches" and buys back every
            # clause of this shape, which is the trade this whole check is
            # written to make.
            if any(re.search(rf"(?<![\w']){re.escape(tok)}['\u2019]s(?![\w])",
                             clause)
                   for tok in _name_tokens(canonical)):
                continue
            for word in words[head + 1:]:
                other = _pronoun_to_group().get(word.lower())
                # A stray "they" is routinely a group ("Vorne watched them
                # scatter"), so only a GENDERED singular counts as a flip.
                if not other or other == group or other == "they":
                    continue
                key = (canonical, word.lower())
                if key in flagged:
                    break
                flagged.add(key)
                expected = "/".join(_ling("_PRONOUN_GROUPS")[group][:3])
                warnings.append(
                    f"Pronoun mismatch for '{canonical}' (canonical {expected}): "
                    f"prose renders '{word}'"
                )
                break
    return warnings


def _check_player_person(prose, player_name, narration_person, player_aliases=None):
    """Deterministic backstop for the narrator's PERSON DISCIPLINE rule.

    When narration_person is 'second' or 'first', the player character is
    'you'/'I' -- naming them is, in the prompt's own words, a hard error. The
    rule was prompt-only, so a player_view that named the player (see
    _self_second_person for how the engine itself used to do that) produced
    prose mixing persons for one character with nothing to catch it, and the
    competing PROPER NOUN FIDELITY instruction actively pushed the model to
    copy the name through.

    Name-based only, and outside quoted spans: a character ADDRESSING the
    player by name aloud is legitimate dialogue that must survive verbatim,
    and a third-person descriptor ('the traveller') cannot be distinguished
    from a reference to someone else without resolving it -- so this scores
    the one signal that is unambiguous.
    """
    person = str(narration_person or "").strip().lower()
    if person not in ("second", "first"):
        return []
    text = str(prose or "")
    if not text:
        return []
    segments = _ling("_QUOTED_SPAN_RE").split(text)
    hits = []
    for form in [player_name, *(player_aliases or [])]:
        form = str(form or "").strip()
        if not form:
            continue
        flags = 0 if form.casefold() in _ling("_COMMON_WORD_NAMES") else re.I
        # A form in an unspaced script by its own boundary: `(?!\w)` never
        # fell between a Japanese name and its particle, so a Japanese page
        # naming the player in the third person was never caught
        # (agents_common audit F14). A Latin form's pattern is unchanged.
        pattern = re.compile(
            name_boundary_pattern(form) if UNSPACED_SCRIPT.search(form)
            else r"(?<!\w)" + re.escape(form) + r"(?:['’]s)?(?!\w)", flags)
        for i in range(0, len(segments), 2):  # even indices = unquoted prose
            if pattern.search(segments[i]):
                hits.append(form)
                break
    if not hits:
        return []
    pronoun = "you/your" if person == "second" else "I/me/my"
    return [
        "Player named in third person: narration_person is "
        f"'{person}', so the player character is {pronoun} and must never be "
        f"named in the prose -- found {', '.join(sorted(set(hits)))} outside "
        "quoted dialogue. Rewrite those references in the correct person, "
        "keeping every quoted line verbatim."
    ]


#: How far the prose's dominant person must lead the person that was ASKED
#: for before the mismatch is reported. Same margin as
#: `_resolve_narration_person`'s hysteresis, for the same reason: one stray
#: token is not a voice change. Counted in SENTENCES on the page
#: (`_narration_person_sentences`).
_PERSON_DRIFT_MARGIN = 2


def _narration_person_sentences(prose, player_name=None):
    """Per person, how many SENTENCES of the narrating voice carry its
    evidence -- `_person_marker_counts` read one sentence at a time, outside
    quoted dialogue.

    A voice is a property of the page, and a page in the wrong person says so
    sentence after sentence; one clause can carry two tokens of it without
    the page being in that person at all. Counted in tokens, an impersonal
    "you" in a single simile crossed the margin: scratch story 166 turn 4611,
    a third-person page with "pushed out one at a time the way you'd shift
    cargo you weren't sure would hold" read "0 first / 2 second / 0 third"
    and was reported as second-person narration.

    Replayed over the 4,305 stored drafts of the Brackwater run's database
    (each read in its chat's person): tokens reported 20, sentences 16 and
    added none. Of the four no longer reported, two are impersonal-you
    similes on third-person pages (turns 125 and 4611) and two are pages
    that named the player once, by a two-word name, under first-person
    narration (163, 164) -- one mention the token count weighed twice, and a
    page `_check_player_person` reports by the name itself."""
    counts = {"first": 0, "second": 0, "third": 0}
    narrative = _narrative_outside_quotes(prose)
    for sentence in _SENTENCE_SPLIT.split(narrative):
        found = _person_marker_counts(sentence, player_name, None)
        for person, count in found.items():
            if count:
                counts[person] += 1
    return counts


def _check_narration_person_match(prose, narration_person, player_name=None):
    """Did the narrator actually WRITE in the person it was told to.

    `_narration_person_counts` was called in exactly one place -- on the
    PLAYER's raw input, to decide `narration_person`. The narrator was then
    told "PERSON DISCIPLINE: ONLY the player character is 'I'/'me'/'my'" and
    nothing read the prose that came back. This is that missing half: the same
    detector, run over the output, warning when the dominant person disagrees
    with the person that was asked for.

    Reusing the detector rather than writing a second one is the point -- it
    already strips quoted dialogue (a "you" inside a spoken line addresses a
    character, not the reader), and unterminated-quote folding is the part
    that is easy to get wrong.

    Two deliberate narrowings, because this scores prose full of OTHER people:

    - third-person evidence comes from the player's NAME only
      (`player_pronouns` is not passed). Every other body on the page is
      legitimately "he"/"she"/"they", and the player's own pronouns are
      routinely the same words; counting them would report every beat where
      the cast moved more than the player did.
    - the dominant person must lead the declared one by `_PERSON_DRIFT_MARGIN`
      SENTENCES, not tokens (`_narration_person_sentences`): an impersonal
      "you" in one simile is two tokens in one sentence.

    Measured over the stored corpus (2,303 narrator drafts, per-turn person
    replayed from each turn's own input): 12 warnings, 0.52%, and every one of
    them is a real disagreement -- prose reading "Your words land in the
    corridor's flat hum" for a turn whose person resolved to `first`. It is a
    WARNING, never enforceable: a rewrite costs a whole narrator call, and
    person is a whole-draft property that a correction note cannot patch
    locally.

    **What it cannot catch, stated plainly:** it would NOT have caught the
    Director's observer-relative epithet reaching the player ("the young
    smith's apprentice" for the player's own body). That phrase is neither a
    name nor a pronoun, so it is invisible to every person detector. This is a
    backstop for genuine model non-compliance, not a fix for bad input --
    that fix is the composer's identity floor (`self_reference_forms`).
    """
    person = str(narration_person or "").strip().lower()
    if person not in ("first", "second", "third"):
        return []
    text = str(prose or "")
    if not text.strip():
        return []
    counts = _narration_person_sentences(text, player_name)
    dominant = max(counts, key=counts.get)
    if dominant == person or counts[dominant] == 0:
        return []
    if counts[dominant] - counts.get(person, 0) < _PERSON_DRIFT_MARGIN:
        return []
    return [
        f"Narrator prose reads as {dominant} person but narration_person is "
        f"'{person}' ({counts['first']} first / {counts['second']} second / "
        f"{counts['third']} third-person sentences outside quoted dialogue)."
    ]


#: How much verb evidence a draft must carry before its tense is scored at
#: all, and how far the asked-for tense must trail before the draft is
#: reported. Person is scored on a flat lead of 2 because its markers are
#: pronouns -- near-unambiguous, and a handful per paragraph. Tense markers are
#: verbs, they are noisier one by one, and a page written in one tense
#: legitimately carries some of the other: a past-tense narrative states
#: standing truths in the present ("the corridor runs east"), and a
#: present-tense one reaches back to what already happened. So the bar is a
#: RATIO over a floor, not a flat lead.
#:
#: Both numbers were chosen by measurement, not taste, on the author's stored
#: corpus (2,803 active narrator drafts, read from a read-only copy 2026-08-26).
#: Against 60 of them hand-labelled from their own opening sentences (random
#: sample, seed 11; 3 past, 57 present), floor 4 / ratio 2.0 scores 57 and
#: gets 57 right, declining the other 3 -- raising the floor to 8 only
#: declines more. Over the whole corpus it decides 2,575 of 2,803 (91.9%), and
#: 40 of those (1.55%) disagree with their own chat's dominant tense, which is
#: the measured rate of real mid-story drift (2-4%) rather than a noise floor.
#: On the one story that narrates in the past throughout, it reads past on 41
#: of 41 drafts.
_TENSE_MIN_EVIDENCE = 4
_TENSE_DRIFT_RATIO = 2.0


def _narration_tense_counts(text):
    """Past/present verb evidence from the narrating voice, outside quoted
    dialogue.

    The markers live in the pack (`_PAST_TENSE_RE`/`_PRESENT_TENSE_RE`) and
    each has two arms, deliberately SYMMETRIC -- a marker set that is richer on
    one side does not detect tense, it detects that side.

    The first arm is a closed list of auxiliaries, copulas and high-frequency
    irregulars whose form alone fixes the tense. On its own it is far too thin
    for this prose: measured over the 2,803 stored narrator drafts, the median
    draft is 124 narrative words and yields about 3 such markers, and 90% of
    drafts carry fewer than 8. The second arm is the inflection, anchored to a
    subject so that morphology is not read out of thin air -- a pronoun or a
    short determiner phrase followed by an `-ed` (past) or `-s` (present) word.
    A BARE `-ed` scan was rejected: an English past participle is also an
    adjective ("the closed door", "his folded hands"), and counting those
    scores every present-tense page as past.

    The anchored arms are not clean either -- "the open double doors" reads as
    a determiner phrase plus an `-s` verb -- which is why the verdict is a
    ratio rather than a majority, and why this returns COUNTS and decides
    nothing.

    Quoted speech is stripped first (`_narrative_outside_quotes`). That is the
    load-bearing part rather than a refinement: dialogue is present tense in a
    past-tense narrative by ordinary convention -- chat 6 ran 41 of 41 stored
    drafts in first-person past with present-tense speech throughout -- so a
    detector that read the quotes would report every correct past-tense draft
    as drift.
    """
    narrative = _narrative_outside_quotes(text)
    return {
        "past": len(_ling("_PAST_TENSE_RE").findall(narrative)),
        "present": len(_ling("_PRESENT_TENSE_RE").findall(narrative)),
    }


def _check_narration_tense_match(prose, narration_tense):
    """Did the narrator actually WRITE in the tense it was told to.

    The same shape as `_check_narration_person_match` above, and the same
    verdict about what to do with the answer: it is a WARNING and it is
    deliberately NOT in `_ENFORCEABLE_PREFIXES`. That list bought a second
    narrator call when this was written; since 2026-09-06 it buys none (E12),
    so the two dispositions have converged and every reading of the prose is a
    note. The reason to keep this one out of the list stands either way: tense
    -- like person -- is a whole-draft property that a correction note cannot
    patch locally.

    It differs from the person check in what it may read. Person has a value on
    every turn because it is DETECTED; tense is AUTHORED, so `""` is the
    ordinary case and means the author expressed no opinion. Nothing is scored
    then: an unset story gets no payload field, no instruction and no warning,
    which is what makes this whole feature invisible to a story that did not
    ask for it.
    """
    # The vocabulary is `story.scene.NARRATION_TENSES`; it is spelled out here
    # rather than imported for the same reason the person check spells out its
    # three values -- this module is imported by every role module and owes
    # `story.scene` nothing. Anything else, including the empty string every
    # unset story sends, falls through to silence.
    tense = str(narration_tense or "").strip().lower()
    if tense not in ("present", "past"):
        return []
    text = str(prose or "")
    if not text.strip():
        return []
    counts = _narration_tense_counts(text)
    other = "present" if tense == "past" else "past"
    if counts["past"] + counts["present"] < _TENSE_MIN_EVIDENCE:
        return []
    if counts[other] < counts[tense] * _TENSE_DRIFT_RATIO:
        return []
    return [
        f"Narrator prose reads as {other} tense but narration_tense is "
        f"'{tense}' ({counts['past']} past / {counts['present']} present-tense "
        "verb markers outside quoted dialogue)."
    ]
