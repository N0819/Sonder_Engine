"""How the engine reads and writes names in any script: name tokens and
recognition, sentence splitting, subject and pronoun tracking, and the
stranger-label grammar a non-recognising observer uses.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from functools import lru_cache
import re
from story.character_schema import _UNSPACED_SCRIPT, name_boundary_pattern
from language_runtime import referring as _referring
from language_runtime import (
    UNSPACED_SCRIPT,
    compositor_text,
    compositor_value,
    fold_words,
    linguistic,
    script_of,
)

from agents.common_base import _ling, _text

#: The word-runs of a NAME, in whatever script it is written. `[A-Za-z']+`
#: describes the Latin script rather than a name, and returns nothing at all
#: for the rest -- so every rule built on tokens (recognition variants,
#: standalone forms) simply stopped having anything to work with.
#:
#: A run in a script that does not space its words is one token; the joiners
#: those scripts put BETWEEN the parts of a name -- the katakana middle dot
#: and double hyphen -- are deliberately outside the classes, so 佐藤・ヒナミ
#: splits where a reader would split it. Latin runs are matched exactly as
#: before, hyphen and all, so no existing name tokenises differently.
_NAME_TOKEN_RE = re.compile(
    r"[A-Za-z']+"
    r"|[ぁ-ゖ]+|[ァ-ヺ]+|[㐀-䶿一-鿿豈-﫿]+|[가-힯]+|[฀-๿]+")

#: A short Latin token cannot be told from an ordinary word; a short token in
#: a script that does not space its words is a perfectly ordinary name --
#: 佐藤 is two characters and is a family name. The same distinction
#: `_scrub_unknown_identities` draws, for the same reason.
_NAME_TOKEN_MIN = 3
_UNSPACED_NAME_TOKEN_MIN = 2


def _name_tokens(text):
    """The word-runs of a name, in whatever script it is written."""
    return _NAME_TOKEN_RE.findall(str(text or ""))


def _countable_word_units(text):
    """How much CONTENT a span holds, counted in whatever script wrote it.

    A word count is a length measure, and `[A-Za-z']+` measures zero in a
    script that neither spaces its words nor writes them in Latin -- so
    every "is this long enough to be an utterance rather than a label" test
    built on one answered 0 and fell to whichever side 0 points at. Review
    2026-09-07 A2: `_check_prose_quote_authority`'s minimum is the measured
    case, where 0 < 3 skipped every quoted line in a Japanese story and the
    prose-quote authority floor never fired at all.

    A spaced run counts as one unit; an unspaced run counts once per
    character, which is the trade `_muffle_tokens` and `_display_floor`
    already make -- the same amount of language is written in fewer
    characters, so the character is the comparable unit. Identical to the
    old count for Latin input.
    """
    units = 0
    for run in _name_tokens(text):
        units += len(run) if _UNSPACED_SCRIPT.match(run[:1]) else 1
    return units


def _word_count(text):
    """How many WORDS `text` holds, counted in its own script.

    Text with no letter of an unspaced script: by whitespace, `.split()`,
    exactly the count every caller made before. Text holding one: by its
    CONTENT runs -- `fold_words`' script runs less the hiragana ones, which
    are particles and inflection, the use `fold_words`' own docstring names
    -- so 本当 and 本当に are one word as "really" is, 奇妙な硬貨 is two as
    "strange coins" is, and 身を乗り出して彼女の肩に手を置く is seven. A run
    of hiragana alone is one word.

    `.split()` made every Japanese span ONE word, so every "is this a phrase
    or a word" rule fell to whichever side one points at (agents_common audit
    F3, F4: no Japanese stage direction was ever cut, and no unspaced alias
    was ever a phrase). Not `_countable_word_units`, which counts a
    CHARACTER as a unit -- right for "is this long enough to be an
    utterance", wrong for "is this one word": it makes 本当 two.
    """
    body = str(text or "")
    if not UNSPACED_SCRIPT.search(body):
        return len(body.split())
    content = [run for run in fold_words(body)
               if script_of(run[:1]) != "hiragana"]
    return max(1, len(content))


def _name_token_floor(token):
    """The shortest this token could be and still identify somebody."""
    return (_UNSPACED_NAME_TOKEN_MIN if _UNSPACED_SCRIPT.match(token[:1])
            else _NAME_TOKEN_MIN)


def _display_floor(name, spaced=4):
    """The shortest a DISPLAY name can be and still be worth matching in prose.

    Four characters is a floor drawn for a spaced script, where a name that
    short is usually a common word too. An unspaced script writes the same
    amount of name in two or three characters -- 鉄の扉 is a full portal name
    at three -- so applying the spaced floor to it skips the guard outright,
    silently, on every portal and every room in the story.
    """
    return (_UNSPACED_NAME_TOKEN_MIN if _UNSPACED_SCRIPT.match(str(name)[:1])
            else spaced)


def _name_parts(name):
    """The parts of a name that identify its body on their own: its script
    runs (`_name_tokens` -- 佐藤 | ヒナミ for 佐藤ヒナミ and 佐藤・ヒナミ alike,
    "Hinami" | "Sato" for "Hinami Sato"), each at least as long as its script
    needs to tell a name from a word (`_name_token_floor`). [] for a name of
    one run: the name itself is its only spelling.

    A NAME'S PARTS WERE FOUND BY WHITESPACE, so a name written without
    spaces had none, and the two places that decide what a stranger may read
    -- the label (`_summary_label`) and the last-pass scrub
    (`_scrub_unknown_identities`) -- let the bare given name through
    (agents_common audit F1/F2, 2026-11-01: "見知らぬヒナミは狐耳の背の高い
    女性", and ヒナミが手を振る。 delivered with no leak reported).
    Callers drop what their own rules exempt (titles, a role worn in the
    name)."""
    tokens = _name_tokens(name)
    if len(tokens) < 2:
        return []
    out = []
    for tok in tokens:
        if len(tok) >= _name_token_floor(tok) and tok not in out:
            out.append(tok)
    return out


def _unspaced_name_parts(name):
    """`_name_parts` for a name written with NO space and in a script that
    does not space its words (佐藤ヒナミ, 佐藤・ヒナミ); [] otherwise. A
    spaced name's parts are its caller's own split, and a Latin name with no
    space ("Jean-Luc") is one word."""
    text = str(name or "").strip()
    if not text or len(text.split()) > 1 or not _UNSPACED_SCRIPT.search(text):
        return []
    return _name_parts(text)


def _significant_name_tokens(name):
    """Lower-cased identifying tokens of a name -- titles, ranks and single
    initials removed. 'Commander Riker' -> {'riker'}."""
    out = set()
    for tok in _name_tokens(name):
        low = tok.strip(".'").casefold()
        if not low or len(low) < _name_token_floor(low):
            continue
        # Rank/title/honorific tokens dropped before comparing names, plus single-letter
        # middle initials. So "Commander Riker" and "Cmdr. Riker" reduce to {riker}.
        if low in _ling("_NAME_TITLE_TOKENS"):
            continue
        out.add(low)
    return out


def _recognizes(name, recognized):
    """Whether an observer who recognizes the `recognized` name forms also
    recognizes `name`, allowing a rank/title VARIANT of a known person
    (P7 / v3 V3: a background presence voiced as 'Commander Riker' was
    anonymized to 'the unfamiliar person' though the observer knew 'William T.
    Riker').

    Deliberately tight to protect the information barrier: a variant is
    recognized ONLY if every one of its significant tokens is contained in a
    single known name. That admits 'Commander Riker' against 'William T. Riker'
    but still anonymizes 'Commander Sato' (no shared token) AND 'Thomas Riker'
    (shares a surname but 'Thomas' is not known) -- a same-surname stranger
    stays a stranger.

    Lives here (not in agents/perception.py) so the narrator payload builders
    resolve speaker displays with the SAME recognition rule perception used to
    build the view -- role modules never import each other."""
    if name in recognized:
        return True
    tokens = _significant_name_tokens(name)
    if not tokens:
        return False
    for known_name in recognized:
        known_tokens = _significant_name_tokens(known_name)
        if known_tokens and tokens <= known_tokens:
            return True
    return False


def _identity_token_set(actor_name, aliases=None):
    """Casefolded word tokens of an actor's name and aliases -- the tokens
    that must never surface to an observer who does not recognize them."""
    tokens = set()
    for form in [actor_name] + list(aliases or []):
        for tok in re.split(r"[^\w]+", str(form or "")):
            if tok:
                tokens.add(tok.casefold())
    return tokens


#: Characters a generated label may never carry. A label is SPLICED INTO
#: PROSE that later passes parse structurally, and the identity scrub
#: (`_scrub_unknown_identities`) decides what it may rewrite by splitting on
#: `_QUOTED_SPAN_RE` and treating even segments as outside-quotes. So one
#: quote character inside a label does not merely look wrong -- it shifts
#: every span boundary after it and INVERTS the guard.
#:
#: Measured live, chat 82 t1: an appearance summary reading `Young
#: Korean-American woman, 5'7", with a lithe...` produced the label `the young
#: korean-american woman 5'7"`. Spliced into the speaker attribution, its
#: stray `"` made the attribution parse as quoted (protected) and the
#: character's actual spoken line parse as unquoted (scrubbed) -- so the
#: engine rewrote a name INSIDE delivered dialogue, which is the one thing
#: this whole area is built not to do. A speaker saying their own name is an
#: introduction, and an introduction is the channel by which a name is
#: legitimately learned; editing it does not close a leak, it destroys the
#: channel. The rendered quote broke too, and the fidelity tripwire fired on
#: the damage rather than the cause.
#: Double quotes only. A single quote BETWEEN word characters is a possessive
#: or a contraction -- "the young smith's apprentice" -- and cannot open a
#: span either, because `_QUOTED_SPAN_RE`'s single-quote alternative refuses an
#: opener preceded by a word character. Stripping those too turned every
#: possessive label into "the young smith s apprentice".
_LABEL_STRUCTURAL_CHARS = "\"\u201c\u201d"

#: A single quote that is NOT holding a word together, which is the only kind
#: that can act as a delimiter downstream.
_LABEL_LOOSE_QUOTE_RE = re.compile(r"(?<![^\W_])['\u2018\u2019]|['\u2018\u2019](?![^\W_])")


def _label_safe(text):
    """A label with the prose STRUCTURE stripped out of it -- see
    `_LABEL_STRUCTURAL_CHARS`. Whitespace is re-collapsed because removing a
    character can leave a double space where a word used to be."""
    cleaned = "".join(
        " " if ch in _LABEL_STRUCTURAL_CHARS else ch for ch in str(text or ""))
    cleaned = _LABEL_LOOSE_QUOTE_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


#: Where a description's first sentence ends -- `referring.SENTENCE_END`,
#: kept under its old name for the readers that import it from here.
_SENTENCE_END = _referring.SENTENCE_END


def _unknown_actor_label(actor_name, appearance_text=None, aliases=None, *,
                         role="", surface=None, sight="full", head_noun=None):
    # Every unrecognized actor used to render as the exact same generic
    # "the unfamiliar person" -- two strangers in one scene (or the same
    # stranger across a perceiver's dialogue and action lines) were
    # indistinguishable in both prose and any memory recorded from it.
    # Derive a short, stable descriptor from the actor's own appearance
    # summary instead. This is deliberately a short label for repeat/
    # inline reference, not a substitute for the full appearance
    # description a caller surfaces separately on first mention.
    #
    # The label is what a NON-recognizing observer refers to the actor by,
    # and appearance summaries routinely LEAD with the canonical name
    # ("Hinami, a fox-eared young woman..."), so the actor's own name/alias
    # tokens are dropped before the descriptor is built -- otherwise the
    # label itself was a deterministic identity leak walking straight past
    # the knows_identity gate it exists to serve.
    #
    # A ROLE WORN IN THE NAME IS NOT IDENTITY. A body's institution supplies
    # a public noun for what it is -- a rank, a duty, a trade -- and a minted
    # display name routinely carries it in front of the personal name
    # ("<rank> <given> <family>"). Set membership then treats that noun as an
    # identity token and subtracts it from the body's own appearance summary,
    # which for such a body IS the noun: everything is stripped, nothing
    # survives, and a person standing in a lit room reaches the view as the
    # generic fallback. Measured live, chat 98 turns 13-21: five crew, each
    # rendered "the unfamiliar person" while the crowd they had been
    # subtracted from called them ensigns aloud. The exemption is of the
    # role's own tokens and nothing else, so a summary that is the body's
    # PERSONAL name still strips to the fallback -- and it discloses nothing,
    # because the same noun is what `charter_crowd` already renders to any
    # observer for the band these bodies are members of. Nothing about "an
    # ensign" narrows down which ensign.
    #
    # A STRUCTURED SURFACE OUTRANKS A SUMMARY (`world.charter_surface`). A
    # charter body's look is dealt per axis from its population's law, so
    # the descriptor is composed from the tier the observer's ``sight``
    # admits -- a silhouette's stature, build and worn outline short of
    # full light, the face tier at full -- and from the surface ALONE: no
    # name token is in it to strip, and the post's name never enters it
    # (the role shows only through what is worn and marked). Measured,
    # Harrowmere replay 2026-09-03: a hundred townspeople with no
    # appearance text, every unrecognised one the fallback below.
    if surface:
        from world.charter_surface import surface_label
        described = surface_label(surface, sight, noun=role)
        if described:
            return _text("unknown_actor", description=described)
    if appearance_text:
        label, _wider = _label_and_ladder(
            actor_name, appearance_text, aliases, role=role,
            head_noun=head_noun)
        if label:
            return label
    if head_noun:
        return _text("unknown_actor", description=str(head_noun).strip())
    return _text("unknown_actor_fallback")


#: The word cap on a stranger's label: the modifiers and head of a noun
#: phrase, with the phrase the summary attached to it where that fits. Five
#: since the label was first cut; the cut now keeps the HEAD under the cap,
#: so a long run of adjectives yields its earliest words and never its noun.
LABEL_WORDS = 5

#: The word cap on one FEATURE phrase appended to a label, articles
#: counted ("with a thin white scar through the left eyebrow" is nine), cut
#: back to a whole phrase when the cap lands inside one. Twice the label's
#: own cap because a feature is appended only to tell two strangers apart,
#: and a feature cut short told nobody anything ("the striking succubus with
#: an athletic", the owner's cards measured 2026-10-20).
LABEL_FEATURE_WORDS = 10


def _fold_word(word):
    return re.sub(r"[^\w]", "", str(word or "")).casefold()


def _describe(words):
    """The description a label template takes: lowercased, prose structure
    out, no terminal stop."""
    return _label_safe(
        " ".join(words).rstrip(".;:").lower()).rstrip(".;:").strip()


def _cap_phrase(words, cap, *, keep=None, ends_at_cut=False):
    """Cut a phrase to ``cap`` words so that it ends on a whole phrase, and
    -- with ``keep`` -- so that its head noun is still in it.

    The rules are the ones the label has carried since 2026-08, in the
    order they run:

    * A LINKING PARTICIPLE introduces a phrase the cap would cut part-way:
      summaries overwhelmingly read "<body> appearing in her early twenties"
      or "<body> wearing a patched flight jacket", which cap to "...woman
      appearing" and "...smuggler wearing a patched". Cut AT the participle,
      before the cap, so the kept words are the head of the description.
      Only verbs that introduce a following phrase are listed; a bare -ing
      rule would eat real nouns ("the figure in mourning").
    * A CAP-CUT PHRASE ENDS ON A WHOLE PHRASE. The evidence is the first
      word the cap DROPPED: a conjunction there means the kept phrase had
      finished ("old woman with silver hair" | "and sharp eyes"); anything
      else means the phrase runs on into the cut ("young woman with golden
      fox" | "ears"), so cut back to the word that opened it. The trailing
      function-word trim and this cut-back must CONVERGE, because each
      exposes a new tail for the other: "a lean courier in a rain-darkened
      canvas coat" capped to "lean courier in a rain-darkened", lost "a
      rain-darkened" to the cut-back and stood as "the lean courier IN" in
      every view of that story (A/B run, 2026-08-19).
    * ...and it ends on a WORD: a bare measurement ("5 7") distinguishes
      nobody and reads as debris.
    * THE HEAD SURVIVES THE CAP. When the trims leave the phrase without
      ``keep`` -- "An extraordinarily tall and powerfully built armoured
      knight" capped and cut back to "extraordinarily tall" -- the earliest
      modifiers yield instead: the cap's worth of words ending on the head,
      with any function word they open on dropped. A rule the comma series
      already had ("A tall, thin, pale, nervous young clerk" -> "the thin
      pale nervous young clerk", review round 4, 2026-10-05), now the
      phrase's whatever its shape.
    """
    words = list(words)
    # A RELATIVE CUTS AS A PARTICIPLE DOES: "A tall, spare man who has the
    # look of a sailor" capped to "the tall spare man who has" (the
    # 2026-09-26 stories, every view of Aurel Holt). What follows "who",
    # "that" or "which" is a clause about conduct, not the body's noun
    # phrase, and no cap inside it ends on anything whole. ``ends_at_cut``
    # says the caller already cut the run there.
    for i, w in enumerate(words):
        if i and _referring.cuts_phrase(w):
            words = words[:i]
            ends_at_cut = True
            break
    whole = list(words)
    overflow = words[cap] if len(words) > cap else ""
    truncated = len(words) > cap
    words = words[:cap]
    dangling = frozenset(str(w).casefold() for w in compositor_value("label_dangling"))
    if truncated and _fold_word(overflow) not in _ling("_BREATH_CONJUNCTIONS"):
        ends_at_cut = True
        # ONE CUT, TO THE OPENER OF THE PHRASE THE CAP LANDED INSIDE -- the
        # last word of the kept run that opens a phrase (`phrase_openers`:
        # a preposition, a possessive, a participle; never an article,
        # which sits inside a phrase). The walk used to stop at the last
        # FUNCTION word and run again until nothing moved, which with every
        # preposition in the table cut "woman across the room in | a" down
        # to "woman" (2026-10-20); before the table was complete it left
        # "the woman across".
        openers = _referring.phrase_openers()
        at = max((i for i, w in enumerate(words)
                  if i and _referring.is_boundary(
                      w, words[i + 1] if i + 1 < len(words) else overflow)
                  # A number is a measurement inside its phrase ("in her
                  # late thirties"), and a possessive after a preposition
                  # ("in HER late thirties") is inside the phrase that
                  # preposition opened: neither opens one.
                  and not _referring.is_number(w)
                  and _fold_word(words[i - 1]) not in openers),
                 default=-1)
        if at > 0:
            words = words[:at]
            # The run now ends where a phrase opener followed it, which is
            # where the phrase before it was whole.
            ends_at_cut = False
    arts = _referring.articles()
    while True:
        before = len(words)
        while words and words[-1].lower() in dangling:
            words = words[:-1]
            # The run now ends BEFORE a function word, which opens a phrase:
            # what it keeps is whole ("with a habit | of standing").
            ends_at_cut = False
        # AN ARTICLE PROMISES A NOUN. A run that ends AT a cut one word
        # after an article has lost that noun to the cut ("with an
        # athletic | yet curvaceous build", "in a long | grey coat"); an
        # article followed by a function word has lost it to the identity
        # strip ("with the of beauty", an alias holding the word). Either
        # way the words from the article on come off and the trim runs
        # again. A run that ends before a phrase opener is whole ("at the
        # belly | from ale"), article or no article.
        hole = next((i for i in range(1, len(words))
                     if words[i].lower() in arts
                     and ((ends_at_cut and i == len(words) - 2)
                          or (i + 1 < len(words)
                              and words[i + 1].lower() in dangling))), -1)
        if hole > 0:
            words = words[:hole]
        if len(words) == before:
            break
    while words and not re.search(r"[^\W\d_]", words[-1]):
        words = words[:-1]
    if keep and not any(_fold_word(w) == _fold_word(keep) for w in words):
        at = max((i for i, w in enumerate(whole)
                  if _fold_word(w) == _fold_word(keep)), default=-1)
        # ...unless a coordinator lies between the cut and the head: "A
        # young woman built lean AND weathered by cold water" read its
        # head as "weathered", and the floor would have dropped "young" to
        # keep it (the 2026-09-26 stories). The floor fires only where the
        # head is a plain continuation of the kept run.
        between = whole[len(words):at] if at >= 0 else []
        if any(_referring.coordinator(w) for w in between):
            at = -1
        if at >= 0:
            tail = whole[max(0, at + 1 - cap):at + 1]
            conjunctions = _ling("_BREATH_CONJUNCTIONS")
            while tail and (tail[0].lower() in dangling
                            or _fold_word(tail[0]) in conjunctions):
                tail = tail[1:]
            if tail:
                words = tail
    return words


def _summary_label(actor_name, appearance_text, aliases=None, *, role="",
                   head_noun=None):
    """``(label, features, named)`` for a stranger described by an
    appearance summary: the label every observer who does not recognise the
    body starts from, the ordered feature phrases
    `composer.assign_stranger_labels` widens it through when two strangers
    share it (`stranger_label_ladder`), and whether the label carries a
    noun of the summary's own (``named``) or is the pack's generic person.
    ``("", [], False)`` for an empty summary.

    A STRANGER'S LABEL IS A NOUN PHRASE WHOSE HEAD IS THE BODY
    (`language_runtime.referring`, which states the grammar). The first
    sentence is read for the clause that names the body: a clause opening
    with an article promises a noun, and the noun is the last word of the
    phrase before its first boundary. Where that noun is a word, the label
    is the phrase cut to `LABEL_WORDS` with the head kept under the cap.
    Where the clause promises no noun -- it opens on a list of what the eye
    noticed, "Forty and weathered by years at sea ..." -- the summary names
    no body, and the label is the pack's generic person carrying the first
    feature the summary attached: "the unfamiliar person with a scar
    through her eyebrow". The cut used to take the first five words and
    trim back to a content word, and the content word it stopped on was
    "forty" (tavern probe, chat 1 turn 2, 2026-10-20): every view of the
    player who did not know her, the interaction loop ("the forty says:")
    and the page ("the forty shifts the tin candle dish") called her that.
    The owner's own cards carried the class -- "the lean", "the tall", "the
    sharp gaze", "the weathered flight jacket over", "the tall full-figured
    who moves like" -- and the collision ladder, which cut the same flat
    word list wider, was worse ("the tall and predatory-graceful at top
    human").

    THE NAME COMES OFF BEFORE THE CUT. Summaries routinely lead with the
    canonical name ("Hinami, a fox-eared young woman ..."), and a label
    carrying it was an identity leak walking straight past the recognition
    gate it serves. Every name and alias form is stripped boundary-aware
    first (an unspaced script has no token to filter), then the tokens,
    then the words that HOLD a name -- a possessive ("Sarah's"), a piece of
    a compound ("Sulmirath-house", "half-Sulmirath") written as a name --
    except the sentence-case capital that opens a description with no
    article before it ("Black-haired" for Mira Black; review rounds 3-4,
    2026-10-05). A personal-name token only, of two letters or more: an
    alias's words took "nine-tailed" from Tamamo-no-Mae, the "T" of William
    T. Riker took "T-shirt", and "Gray" took "gray-eyed". An article inside
    an alias ("the navigator") is the language's, not the name's.

    A NOUN THE STRIP TOOK IS STILL A NOUN. When the promised head is itself
    an alias the card wears -- "A lean tinker ..." on a card aliased "the
    tinker" -- the modifiers that survive close on the generic noun, "the
    lean person": an observer who may not say the alias can still see a
    person. The owner's Cass Mott read "the lean" in every view.

    A ROLE WORN IN THE NAME IS NOT IDENTITY: `role`'s own tokens are exempt
    from the strip (chat 98 turns 13-21: five crew rendered "the unfamiliar
    person" because their rank stood in their display names, while the
    crowd they had been subtracted from called them ensigns aloud).

    IN A HEAD-FINAL PACK (no articles) the body noun ENDS its clause, so
    the label is the first sentence's noun-final clause; a sentence that
    ends on inflection names nothing and takes the generic noun. Until
    2026-10-20 the Japanese path cut nothing at all: the label was the
    entire summary, every sentence of it, with its 。 on.
    """
    from language_runtime import referring

    text = str(appearance_text or "").strip()
    if not text:
        return "", [], False
    articles = referring.articles()
    # A FUNCTION WORD IN A NAME IS THE LANGUAGE'S, NOT THE NAME'S: an alias
    # "Succubus of Endless Craving" or "the navigator" must not take every
    # "of" and "the" out of the body's own description (the owner's
    # Vaelith read "with kind beauty" for "with the kind of beauty").
    function_words = articles | {
        str(w).casefold() for w in compositor_value("label_dangling")}
    name_tokens = _identity_token_set(actor_name, aliases) - function_words
    if role:
        name_tokens -= _identity_token_set(role)
    forms = [f for f in [actor_name, *(aliases or [])]
             if str(f or "").strip()
             and _identity_token_set(str(f)) - articles
             and not (role and _identity_token_set(str(f))
                      <= _identity_token_set(role))]
    noun = " ".join(str(head_noun or "").split())
    generic = str(compositor_value("surface_person"))

    def _close(description, close):
        if description and close and close.casefold() not in description.casefold().split():
            return compositor_text("surface_label", adjectives=description,
                                   noun=close).strip()
        return description

    if referring.head_final() or referring.unspaced(text):
        # THE NAME'S PARTS COME OFF TOO, as the token strip below takes them
        # in an article language: an unspaced card named 佐藤ヒナミ whose
        # summary leads with ヒナミ minted "見知らぬヒナミは..." for every
        # observer who had not met her (agents_common audit F1). A title, a
        # generic head, a function word or the role worn in the name is the
        # language's word, not the body's spelling -- the exemptions
        # `_scrub_unknown_identities` keeps for the same parts.
        exempt = (function_words | set(_ling("_NAME_TITLE_TOKENS"))
                  | set(_ling("_GENERIC_LABEL_HEADS")))
        if role:
            exempt |= _identity_token_set(role) | {
                tok.casefold() for tok in _name_tokens(role)}
        parts = [tok for tok in _name_parts(actor_name)
                 if tok.casefold() not in exempt]
        sentence = _strip_identity_tokens(referring.first_sentence(text),
                                          forms + parts)
        clause = referring.head_final_clause(sentence)
        description = _label_safe(clause).strip(" ,.;:、。")
        description = _close(description, noun)
        if description:
            return _text("unknown_actor", description=description), [], True
        if noun:
            return _text("unknown_actor", description=noun), [], True
        return _text("unknown_actor_fallback"), [], False

    # READ THE RAW TEXT FOR THE HEAD, THE STRIPPED TEXT FOR THE REST: the
    # boundary strip takes a name-led summary's name off so the article it
    # hid can promise its noun ("Hinami, a fox-eared young woman"), and the
    # same strip takes a NOUN that happens to be the body's name or alias
    # ("a masked guard" on a card named Guard) -- the raw reading is what
    # says a noun stood there.
    raw_head = referring.read(text).head
    reading = referring.read(_strip_identity_tokens(text, forms))
    if not reading.parts:
        return "", [], False
    raw_words = list(reading.words)
    head = reading.head
    # A PUBLIC NOUN THE ENGINE OWNS IS A HEAD WITHOUT AN ARTICLE: the
    # body's `role` (the crowd's own noun for what it is -- "ensign",
    # "chief engineer") and a creature's authored noun. A bare description
    # that ENDS on one names the body by it: five crew whose appearance
    # was their rank alone (chat 98) read "the ensign", never "the
    # unfamiliar person" and never "the ensign person".
    if not head and not reading.promised and raw_words:
        public = _identity_token_set(role) | ({noun.casefold()} if noun else set())
        if _fold_word(raw_words[-1]) in public:
            head = raw_head = raw_words[-1]
            reading.phrase = list(raw_words)
            reading.tail = []
    personal = {t for t in _identity_token_set(actor_name) if len(t) >= 2}
    if role:
        personal -= _identity_token_set(role)

    def _holds_the_name(i, w):
        pieces = [piece for piece in re.split(r"[^\w]+", w) if piece]
        named = [k for k, piece in enumerate(pieces)
                 if piece[:1].isupper() and piece.casefold() in personal]
        if not named:
            return False
        # A possessive is the name wherever it stands ("Sarah's"). So is
        # any piece of a compound -- "half-Sulmirath" -- except the first
        # piece of the word that OPENS a description with no article,
        # whose capital is sentence case.
        if len(pieces) == 2 and pieces[1].casefold() == "s" and "-" not in w:
            return True
        if i == 0 and not reading.promised:
            return any(k > 0 for k in named)
        return True

    def _strip(words):
        out = [w for i, w in enumerate(words)
               if _fold_word(w) not in name_tokens and not _holds_the_name(i, w)]
        while out and out[0].casefold() in articles:
            out = out[1:]
        return out

    words = _strip(raw_words)
    phrase = list(reading.phrase)
    lost = raw_head and not any(_fold_word(w) == _fold_word(raw_head) for w in words)
    kept_head = bool(head) and not lost and any(
        _fold_word(w) == _fold_word(head) for w in words)
    features = _label_features(reading, _strip)

    if head and kept_head:
        description = _close(_describe(_cap_phrase(words, LABEL_WORDS, keep=head)), noun)
        if description:
            return _text("unknown_actor", description=description), features, True
    if lost:
        modifiers = [w for w in _strip(phrase) if _fold_word(w) != _fold_word(raw_head)]
        description = _describe(_cap_phrase(modifiers, LABEL_WORDS - 1))
        if description:
            description = _close(description, noun or generic)
            return _text("unknown_actor", description=description), features, True
    if reading.modifiers:
        description = _describe(_cap_phrase(_strip(reading.modifiers), LABEL_WORDS - 1))
        if description:
            description = _close(description, noun or generic)
            return _text("unknown_actor", description=description), features, True
    # NO NOUN PROMISED, OR A NUMBER WHERE ONE WAS: the body is the pack's
    # generic person, told apart by what the summary attached to it
    # (`_label_and_ladder` puts the first feature on the label itself).
    label = (_text("unknown_actor", description=noun) if noun
             else _text("unknown_actor_fallback"))
    return label, features, bool(noun)


def _label_and_ladder(actor_name, appearance_text, aliases=None, *, role="",
                      head_noun=None):
    """``(label, wider)``: the label a stranger starts from and the labels it
    widens into. A label that is the pack's generic person carries the
    first feature the summary attached ("the unfamiliar person with a scar
    through her eyebrow"), because the generic noun alone tells two
    strangers apart no better than nothing; a label with a noun of its own
    keeps the features for the collision ladder."""
    label, features, named = _summary_label(
        actor_name, appearance_text, aliases, role=role, head_noun=head_noun)
    if not label:
        return "", []
    wider = _widen(label, features)
    if not named and wider:
        return wider[0], wider[1:]
    return label, wider


def _label_features(reading, strip):
    """The feature phrases of a summary's first sentence, in the order a
    label widens through them: the phrases its head clause attaches after
    the noun ("with six tails", "and amber eyes"), then the later clauses
    the sentence attached with a boundary word (", with a slightly
    dishevelled uniform"). Each is cut to `LABEL_FEATURE_WORDS` on a whole
    phrase; one that comes to its opener alone is nothing."""
    from language_runtime import referring

    # Only a clause that named its noun has a tail: a list or prose with no
    # noun attaches its later words to nothing of the body's ("the
    # unfamiliar person by years at sea", first draft of this rule).
    tail = list(reading.tail)
    phrases, current = [], []
    for w in tail:
        if current and referring.splits_tail(w):
            phrases.append(current)
            current = []
        current.append(w)
    if current:
        phrases.append(current)
    # A phrase that does not ATTACH -- one opening on a relative or a
    # number -- is a clause about conduct or a measurement, not a feature,
    # and everything after it in the tail is inside that clause ("who reads
    # as older than thirty-six in poor light" is not "as older than...").
    kept = []
    for i, words in enumerate(phrases):
        if not words or not referring.attaches(words[0]):
            break
        # A phrase the tail split ended at a conjunction ("with an athletic
        # | yet curvaceous build") ends at a cut, which `_cap_phrase` must
        # know to apply its article rule.
        following = phrases[i + 1] if i + 1 < len(phrases) else None
        kept.append((words, bool(following) and referring.cuts_phrase(following[0])))
    kept.extend((part.split(), False) for part in reading.attached
                if part.split() and referring.attaches(part.split()[0]))
    out = []
    for words, ends_at_cut in kept:
        # AN ARTICLE THAT FOLLOWS NO OPENER OPENS A CLAUSE: "in the way
        # dock work makes A man big" is a sentence wearing a preposition,
        # and no cut of it is a feature.
        if _clause_like(words):
            continue
        # A FEATURE THE IDENTITY STRIP TOOK A WORD FROM IS NOT SAYABLE: an
        # alias "The Hollow Smile" takes "smile" out of "with a deceptively
        # soft smile" and leaves a phrase ending on an adjective.
        stripped = strip(words)
        if len(stripped) != len(words):
            continue
        cut = _cap_phrase(stripped, LABEL_FEATURE_WORDS, ends_at_cut=ends_at_cut)
        if len(cut) < 2:
            continue
        text = _describe(cut)
        if text and text not in out:
            out.append(text)
    return out


def _clause_like(words):
    arts = _referring.articles()
    openers = _referring.phrase_openers()
    for i, w in enumerate(words):
        if i and w.casefold() in arts:
            before = _fold_word(words[i - 1])
            if before not in openers and not _referring.coordinator(before) \
                    and before not in arts:
                return True
    return False


def _append_feature(label, feature):
    return f"{label} {feature}".strip()


def _widen(base, features):
    """The labels ``base`` widens into, one feature at a time. A feature
    that only continues a phrase ("and amber eyes") is skipped where no
    phrase precedes it; what the label already ends with is not said
    twice ("the woman across the room" + "across the room in a grey
    coat")."""
    wider, label = [], base
    attached = any(_referring.is_boundary(w) for w in base.split()[1:])
    for feature in features:
        first = feature.split()[0] if feature.split() else ""
        if _referring.coordinator(first) and not attached:
            continue
        have, add = label.casefold().split(), feature.split()
        overlap = max((n for n in range(min(len(have), len(add)), 0, -1)
                       if have[-n:] == [w.casefold() for w in add[:n]]),
                      default=0)
        rest = " ".join(add[overlap:])
        if not rest or rest.casefold() in label.casefold():
            continue
        label = _append_feature(label, rest)
        attached = True
        wider.append(label)
    return wider


def stranger_label_ladder(actor_name, appearance_text, aliases=None, *,
                          role="", head_noun=None):
    """``(base, wider)``: a stranger's label and the labels it widens into,
    one attached feature at a time, when another stranger shares it. The
    composer walks `wider` on collision and falls to the ordinal
    distinguisher when it is spent. A feature that only continues a phrase
    ("and amber eyes") is skipped where no phrase precedes it."""
    base, wider = _label_and_ladder(actor_name, appearance_text, aliases,
                                    role=role, head_noun=head_noun)
    if not base:
        return _unknown_actor_label(actor_name, None, aliases, role=role,
                                    head_noun=head_noun), []
    return base, wider

def _strip_identity_tokens(text, forms):
    """Remove an actor's name/alias forms from engine-supplied prose (an
    appearance summary, an overlay) before it is surfaced to an observer
    who does not recognize that actor. appearance_of()/persona summaries
    routinely lead with the canonical name, so pasting them verbatim into
    a stranger's view via _inject_visible_actor leaked identity entirely
    deterministically, independent of anything the model wrote."""
    out = str(text or "")
    for form in forms or []:
        form = str(form or "").strip()
        if not form:
            continue
        # Per-edge boundaries (`name_boundary_pattern`), not `(?<!\w)`: an
        # unspaced-script name never had a non-word neighbour to match at.
        # What a name carries away with it is the pack's to say: English an
        # attached possessive, Japanese the case particle that would
        # otherwise stand stranded where the name was.
        out = re.sub(
            name_boundary_pattern(form)
            + str(linguistic("agents.common", "_NAME_TAIL_PATTERN")),
            "", out, flags=re.I,
        )
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,;.!?])", r"\1", out)
    out = re.sub(r"([,;])(\s*[,;])+", r"\1", out)
    # A hyphen the removed name was bound to ("Alice-grey" -> "-grey") is
    # debris of the same kind as the doubled comma above.
    out = re.sub(r"(?<![\w])[-\u2010\u2011](?=\w)", "", out)
    return out.strip().lstrip(",;: ").strip()


# Leading words that are not the name itself. Splitting a name on whitespace
# and taking token 0 matched "The" for a player called "The Stranger", which
# then matched almost every sentence in the beat.


def _player_name_forms(player_name):
    """Sentence-opening forms that identify the player: the full name, plus any
    single word of it substantial enough to stand alone."""
    name = str(player_name or "").strip()
    if not name:
        return []
    forms = [name]
    for clean in _name_tokens(name):
        # The capital is what separates a name part from an ordinary word it
        # sits beside -- in a script that HAS capitals. A caseless script
        # offers no such signal, and demanding one there is how a Japanese
        # player name contributed no standalone form at all; the leader list
        # and the length floor carry it instead.
        if len(clean) < _name_token_floor(clean):
            continue
        if not clean[:1].islower() \
                and clean.casefold() not in _ling("_NAME_LEADERS"):
            forms.append(clean)
    # Longest first so "The Stranger" is preferred over "Stranger".
    return sorted(set(forms), key=len, reverse=True)


#: Bounded, because this is the file's one piece of mutable module state and it
#: is keyed by NAME FORM (and the active pack's title alternation, which the
#: pattern embeds) -- so it grows with every cast of every chat the process has
#: served, and nothing ever cleared it. An LRU is the right shape: the working
#: set is one scene's cast, and a form that falls out is recompiled in
#: microseconds.
_SUBJECT_OPENER_CACHE = 512


def _name_title_alternation():
    """The regex alternation of every title that may LEAD a name.

    A closed table the engine owns (`_NAME_LEADERS` narrowed to
    `_NAME_TITLE_TOKENS`, which `_identity_token_set` already strips when it
    compares two names), so the two questions built on it stay one answer:
    where a name's occurrence BEGINS (`name_occurrence_pattern`) and whether a
    sentence OPENS with one (`_subject_opener`). Articles are excluded here --
    each caller has its own rule about those.

    Longest first, so "cmdr." wins over "cmdr" at the same position.
    """
    titles = sorted((t for t in _ling("_NAME_LEADERS")
                     if t.strip(".").casefold() in _ling("_NAME_TITLE_TOKENS")
                     and t.strip(".").casefold() not in ("a", "an", "the")),
                    key=len, reverse=True)
    return "|".join(re.escape(t) for t in titles)


def name_occurrence_pattern(form, *, flags=0, possessive=True):
    """One WHOLE occurrence of a body's name, the title and article that lead
    it included, with an optional possessive `'s`. `form` is one name or an
    iterable of the forms of one body, which are alternated widest-first.

    A TITLE WITH A NAME IN IT IS ONE NAME, NOT A TITLE BESIDE A PRONOUN. Every
    rewrite that puts a perceiver into second person was replacing the name
    fragment it happened to know and leaving whatever stood in front of it, so
    the manor run of 2026-09-05 (PC8) composed "facing Lord you", "before Lord
    you" and -- once the episode renderer had taken the second person into
    first -- "toward Mrs. I". Twice the composer's own tripwire fired on it and
    reported an engine defect, which it was.

    The article comes in for the same reason and from the same live case: a
    body registered as "A Dalek" is written "The Dalek" the moment it stops
    being new (chat 58), and "The Dalek's visual sensors" rewritten on the
    bare name is "The your visual sensors".

    `flags` is the caller's case rule for the NAME (the identity scrub matches
    an ordinary-English name case-sensitively); the lead is always caseless,
    because a title carries no identity and "Dr." and "dr." are one word.
    """
    lead = _name_title_alternation()
    prefix = r"(?<!\w)(?:(?:[Tt]he|[Aa]n?)\s+)?"
    if lead:
        prefix += rf"(?:(?i:{lead})\s+)?"
    tail = r"(['’]s)?(?!\w)" if possessive else r"(?!\w)"
    names = [str(form)] if isinstance(form, str) else [
        str(f or "").strip() for f in form if str(f or "").strip()]
    body = "|".join(re.escape(name) for name in
                    sorted(set(names), key=len, reverse=True))
    return re.compile(prefix + "(?:" + body + ")" + tail, flags)


def _subject_opener(form):
    """Does a sentence OPEN with this name, as subject or possessive?

    Tolerates a LEADING ARTICLE, because the article belongs to the prose and
    not to the name. A body registered as "A Dalek" is written "The Dalek" the
    moment it stops being new, and the article is the only difference -- the
    same trap `docs/UNBUILT.md` §1.17 documents for presence identity. Without
    this every subject-anchored guard silently missed such a body: live
    (chat 58, t28) the Dalek's own view read "The Dalek's visual sensors pick
    up...", "The Dalek hears...", "The Dalek's own base grinds forward" --
    third person about its own perceiver, straight past `_strip_self_narration`,
    whose forms were "A Dalek" and "Dalek" and neither of which opens that
    sentence.

    Articles, and a TITLE STANDING IMMEDIATELY BEFORE THE NAME. The two are
    not the same admission and the line between them is where §1.17 draws it:
    a title used INSTEAD of a name is frequently the only thing telling two
    bodies apart ("the guard" is not "the captain"), and that is still
    refused -- `_NAME_LEADERS` cannot open a sentence on its own here. A title
    used BEFORE a name adds nothing to identify and cannot confuse anybody,
    because the name still has to match right behind it.

    Found by the abbreviation repair (`split_sentences`). Before it, "Dr.
    Watson watches the door" reached this function already broken in half, so
    the second piece opened with the bare name and the guard fired by
    accident -- leaving a dangling "Dr." where the cut had been. Repairing the
    split correctly would otherwise have handed the sentence back whole and
    lost the catch, turning one visible defect into a silent one.

    The name itself keeps its case sensitivity: a capitalised form matches
    case-sensitively as before, so an ordinary noun that happens to spell a
    name does not bind.
    """
    # `name_boundary_pattern`, not a trailing `\b`: `\b` asserts a
    # transition between word and non-word characters, which describes
    # scripts that space their words and nothing else. A Japanese particle
    # is a word character, so 「ヒナミは」 never matched `ヒナミ\b` -- and
    # this is the primitive every subject-anchored guard in the file is
    # built on, so all of them, player-act authority included, resolved
    # NOBODY as the subject of any sentence in such a story. The boundary
    # the pattern does apply still refuses a Latin name inside a longer
    # word ("Hinamis"), and the leading article stays this function's own
    # rule.
    # Inline-insensitive: the name itself keeps this function's case rule, and
    # a title never carries identity, so "Dr." and "dr." are the same word.
    #
    # KEYED ON THE TITLES IT COMPILES, never on the form alone: the pattern
    # embeds the ACTIVE pack's title alternation, and a cache keyed by the
    # form handed whichever language compiled it first to every later story
    # in the process (agents_common audit F9, 2026-11-01) -- the server runs
    # stories in both packs at once.
    return _compiled_subject_opener(form, _name_title_alternation())


@lru_cache(maxsize=_SUBJECT_OPENER_CACHE)
def _compiled_subject_opener(form, lead):
    return re.compile(
        rf"^(?:(?i:{lead})\s+)?(?:[Tt]he\s+|[Aa]n?\s+)?"
        rf"{name_boundary_pattern(form)}(?:['’]s)?",
        re.I if form[:1].islower() else 0)


def _ends_with_abbreviation(piece, abbreviations):
    """Does this fragment end in an abbreviation's full stop rather than a
    sentence's? The last whitespace-delimited token, minus any closing
    punctuation around it, stripped of its trailing period."""
    token = str(piece or "").strip().split()[-1:] or [""]
    word = token[0].strip("\"'“”‘’()[]")
    if not word.endswith("."):
        return False
    return word[:-1].casefold() in abbreviations


#: A sentence stop of a script that does not space its words.
_UNSPACED_STOP = re.compile("[。！？｡]")


def split_sentences(text, split=None):
    """Sentences, with an abbreviation's period not mistaken for a full stop.

    Every splitter in this tree breaks on `.` followed by whitespace, and a
    title is a period followed by whitespace. So "occupied by Dr. Sarah Moon."
    is TWO sentences: one ending "...by Dr.", and a fragment that is nothing
    but a name.

    That is not cosmetic where a sentence is the unit a guard decides about.
    `_strip_self_narration` drops whole sentences whose subject is the
    perceiver, and the fragment IS the perceiver -- so it was dropped and the
    honorific left dangling. Live, chat 82: Sarah Moon's own view of her own
    room read "The observation chair is occupied by Dr." The identical note
    written without the title is untouched, because then her name sits inside
    a real sentence and no whole sentence is only her.

    The token set is language pack data (`_SENTENCE_ABBREVIATIONS`), because
    "a period may end an abbreviation" is a fact about a WRITING SYSTEM, not
    about a story -- Japanese ends its sentences with `。` and has nothing here
    to protect.

    Deliberately NOT every abbreviation: "etc." and "Ph.D." genuinely end
    sentences, and rejoining there would weld two real ones together. What is
    in the set is the class that essentially never ends a sentence -- titles
    and name particles, which are also the class that appears immediately
    before a NAME, which is what makes the split damaging in the first place.
    """
    # A TEXT THAT ENDS ITS SENTENCES IN AN UNSPACED SCRIPT IS SPLIT BY
    # `language_runtime.split_sentences`, the one script-aware splitter: this
    # module's own pattern ate the closing 」 after 。 and cut a quotation
    # carried on by its quotative particle (「行こう。」と彼は言った。) in two.
    # Only there, because only there is it the same answer for English: on
    # the owner's English prose (2,682 narrator/perception texts, 2026-11-01)
    # the two splitters disagreed on 850, every one a closing quote before
    # the next sentence ('…it." Mellisande holds…'), which this splitter has
    # always kept together and its callers' guards were measured against.
    # A caller's own `split` is still that caller's (UNBUILT_PIPELINE 1.69 is
    # the class: several splitters, one now script-aware).
    if (split is None or split is _SENTENCE_SPLIT) \
            and _UNSPACED_STOP.search(str(text or "")):
        return _split_sentences_by_script(str(text or ""))
    pattern = split if split is not None else _SENTENCE_SPLIT
    abbreviations = _ling("_SENTENCE_ABBREVIATIONS")
    out = []
    for piece in pattern.split(str(text or "")):
        if piece is None:
            continue
        if out and out[-1].strip() and _ends_with_abbreviation(
                out[-1], abbreviations):
            out[-1] = f"{out[-1].rstrip()} {piece.lstrip()}"
        else:
            out.append(piece)
    return out


def _split_sentences_by_script(text):
    from language_runtime import split_sentences as _by_script
    return _by_script(text)


def _sentence_subjects(prose, names, split=None, pronouns=None):
    """Each sentence of `prose` paired with the name that is plainly its subject.

    The version this replaced refused to resolve pronouns at all, on the
    ground that "She lifts it" could be anyone in the beat. That is true of
    a pronoun read in ISOLATION and false of one read in sequence: prose
    establishes a subject by name and then continues it, which is why the
    live miss (chat 56 t1391) slipped through -- the Director named the Doctor
    once, then wrote four more sentences about him as "he", and a check that
    only reads sentence-opening names saw only the one legitimate sentence.

    So: track the most recently NAMED subject and let a pronoun-subject
    sentence continue it. A new named subject takes over, which is what keeps
    this honest -- "The Doctor draws it. Hinami flinches. She says nothing."
    binds the pronoun to Hinami, not to the Doctor. Where no name has been
    established yet, the pronoun binds to nobody rather than to a guess.

    Yields (sentence, subject_name_or_None) in order.

    A PRONOUN REDIRECTS ONLY WHEN THERE IS SOMEBODY FOR IT TO REDIRECT TO.
    `pronouns` is `{name: {subject, object, possessive}}`, the roster's own
    declared paradigms -- a closed set the engine owns. When a sentence opens
    with a pronoun of a different group from the tracked subject's AND some
    other body in scope answers to that group, the continuation is wrong:
    measured (multitude, 2026-09-05, PM22) "She turns the key twice with a
    harsh screech of tumblers..." was continued onto Tobin Slake, who is
    he/him and was across the room with his palms on a door, while the body
    the sentence is about was standing in the same roster. The sentence binds
    to that other body when exactly one answers, and to nobody when several
    do -- a guard that declines is quiet, and a guard that guesses among
    equals is the thing being fixed.

    IT IS NOT A GENDER CHECK ON THE PROSE. A disagreement with NO other
    candidate is a sheet out of step with the page -- a default paradigm
    nobody edited, a body written as "he" against a card that never said so
    -- and the continuation stands, because there is no other reading. That
    is the whole difference between narrowing this tracker and switching it
    off for every cast carrying an unedited card. Omitting `pronouns` keeps
    the older, paradigm-blind continuation, so a caller with no roster is
    unchanged.

    `split` overrides the sentence splitter for callers that need a different
    one -- perception's tolerates a closing quote between the terminal
    punctuation and the space, and losing that would silently make a whole
    passage one "sentence" again.
    """
    current = None
    # The default is this module's splitter: on text without an unspaced
    # script's stop its pattern IS the `(?<=[.!?])\s+` this used, so English
    # splits exactly as it did; on text with one it is the script-aware
    # splitter. The ASCII-only default made a Japanese paragraph ONE sentence
    # whose subject was its first name, and the four authority checks read
    # nothing past it (agents_common audit F14, the class's root).
    pieces = split_sentences(prose or "", split)
    groups = {name: _pronoun_group(p) for name, p in (pronouns or {}).items()}
    for sentence in pieces:
        stripped = sentence.strip()
        if not stripped:
            continue
        matched = None
        for cand in (names or []):
            for form in _player_name_forms(cand):
                if _subject_opener(form).match(stripped):
                    matched = cand
                    break
            if matched:
                break
        if matched:
            current = matched
            yield stripped, matched
        else:
            opener = _ling("_SUBJECT_PRONOUN_RE").match(stripped)
            if not opener:
                yield stripped, None
                continue
            # The opener may carry a leading adverbial ("With a turn of her
            # shoulder, she ..."), so the pronoun is its LAST word, not the
            # whole match.
            words = re.findall(r"[^\W\d_]+", opener.group(0), re.UNICODE)
            said = _pronoun_to_group().get(words[-1].lower()) if words else None
            held = groups.get(current)
            if said and held and said != held:
                answers = [n for n in (names or [])
                           if n != current and groups.get(n) == said]
                if answers:
                    current = answers[0] if len(answers) == 1 else None
            yield stripped, current


# A conjunct that introduces its OWN subject is not the tracked body's doing.


def _predicate_heads(tail, window):
    """The head words of each conjunct of a predicate.

    One subject governs several verbs -- "takes a half-step closer, hands open
    at his sides, and speaks in a low, steady voice" is one body doing two
    things -- so a window measured from the NAME sees only the first verb and
    the second escapes. That is exactly how the live case slipped past: the
    attribution verb sat twelve words past the subject, and the window is
    three. Measuring the window from each conjunct instead keeps the check on
    what this body is DOING (rather than any word anywhere in a long sentence)
    while letting it reach the later verbs of a compound predicate.

    Conjuncts that introduce their own subject are dropped: in "The Doctor
    lowers the device, and she says nothing" the saying is hers.

    Returns (head, clause) pairs -- the head for verb matching, the whole
    clause for tests that read wider than the verb (see `_PROXIMITY_RE`).
    """
    heads = []
    # 、 is the clause mark of the unspaced scripts: absent from English text,
    # so the English split is unchanged.
    for part in re.split(r",|、|\band\b|\bthen\b|;", tail or "", flags=re.I):
        part = part.strip()
        if not part or _ling("_NEW_SUBJECT_RE").match(part):
            continue
        # The window is counted in the clause's own script (A2), the same
        # unit `_countable_word_units` measures: `[A-Za-z']+` found no head
        # at all in an unspaced clause, so every conjunct's head was the
        # empty string.
        #
        # AN UNSPACED CLAUSE IS READ AS WRITTEN, FROM ITS END. Joining its
        # script runs with spaces made 話す the head "話 す", which no verb
        # alternation can match, and a window counted from the subject cut
        # before the verb, because the scripts the engine reads without
        # spaces (Japanese) put the predicate LAST -- the A2 skeptic's
        # measured deferral ("the window unit needs thought"). So the window
        # is the clause's last `window` runs, as the text writes them:
        # 「静かに話す」 -> "かに話す". A spaced clause is unchanged: its first
        # `window` tokens, joined by single spaces.
        if UNSPACED_SCRIPT.search(part):
            runs = list(_NAME_TOKEN_RE.finditer(part))
            if not runs:
                continue
            kept = runs[-window:] if window > 0 else []
            head = part[kept[0].start():kept[-1].end()] if kept else ""
            heads.append((head, part))
            continue
        heads.append((" ".join(_name_tokens(part)[:window]), part))
    return heads


def _strip_subject(sentence, name):
    """A sentence's predicate: everything past its subject, whether that
    subject was written as the name or as a pronoun continuing it.

    The name's own boundary at both ends (A2): the trailing `\\b` described
    only spaced scripts, so a sentence opening with a name written in an
    unspaced one yielded no predicate at all -- '' -- and every verb check
    reading this had nothing to read. The possessive is a second form rather
    than an optional suffix so the boundary still falls after it. Identical
    for Latin names."""
    for form in _player_name_forms(name):
        match = (re.match(name_boundary_pattern(form + "'s"), sentence)
                 or re.match(name_boundary_pattern(form), sentence))
        if match:
            return sentence[match.end():]
    match = _ling("_SUBJECT_PRONOUN_RE").match(sentence)
    return sentence[match.end():] if match else ""

# Third-person paradigms screened by _check_pronoun_fidelity. Only these three
# closed sets are checked: a character whose declared pronouns fall outside the
# table (neopronouns, mixed sets like she/them) is skipped entirely rather than
# guessed at -- the check exists to catch UNAMBIGUOUS flips, so anything it
# can't be certain about is not its business.
def _pronoun_to_group():
    """Pronoun -> group, for the ACTIVE story pack.

    Built at MODULE level before, which evaluated `_ling` once at import with
    the contextvar still at its "en" default. The Japanese pack deliberately
    adds 彼/彼女/彼ら groups and every one of them was dead, so the pronoun
    fidelity check silently returned nothing for a Japanese story. This is the
    exact hazard `linguistic()`'s own docstring warns about: the lookup has to
    happen at use time, because two languages can run in one process.
    """
    return {w: g for g, ws in _ling("_PRONOUN_GROUPS").items() for w in ws}

# Splits a sentence into clauses. A pronoun is only scored against a name in
# the SAME clause, which is what keeps "Vorne glanced at the ensign; her hands
# shook" (referent is the ensign, not Vorne) out of the check.
#
# The CJK branch takes no trailing whitespace, because Japanese writes none
# after 。 -- an ASCII-only splitter returned the whole passage as one clause,
# so every pronoun scored against every name in it.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])[」』\"\'”’)\]]*\s*")

def _pronoun_group(pronouns):
    """The closed paradigm a declared pronoun set belongs to, or None when the
    declared forms are absent, unknown, or disagree with each other."""
    if not isinstance(pronouns, dict):
        return None
    groups = set()
    for key in ("subject", "object", "possessive"):
        word = str(pronouns.get(key) or "").strip().lower()
        if not word:
            continue
        group = _pronoun_to_group().get(word)
        if group is None:
            return None
        groups.add(group)
    return groups.pop() if len(groups) == 1 else None
