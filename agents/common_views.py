"""Deterministic sentences composed into a view: muffling, tone and dialogue
injection, self-reference forms and second-person rewriting, observable
predicates, the residue view, and the legacy injection/fallback family.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from story.character_schema import _UNSPACED_SCRIPT
from language_runtime import referring as _referring
from language_runtime import UNSPACED_SCRIPT, compositor_value, find_names
from world.spatial import has_visual

from agents.common_base import (
    _append_once,
    _base_from_third_person_s,
    _contains_quote,
    _ling,
    _quote_body,
    _text,
)
from agents.common_names import (
    _identity_token_set,
    _player_name_forms,
    _unknown_actor_label,
    name_occurrence_pattern,
)

# What survives muffling: stressed, longer words. Function words are the first
# thing lost, which is why an overheard fragment is a scatter of nouns and verbs
# rather than a summary.
_MUFFLE_KEEP_MIN = 4
_MUFFLE_MAX_WORDS = 3


#: Content-bearing runs in a script that does not space its words: kanji,
#: katakana, Hangul, and any Latin/digit run carried through code-switching.
#: Hiragana is deliberately absent -- it carries particles and inflection,
#: which is precisely the low-information half that drops out of a half-heard
#: line, and dropping it leaves chunks that are still verbatim substrings.
_UNSPACED_CONTENT_RUN = re.compile(
    r"[㐀-䶿一-鿿豈-﫿]+|[ァ-ヿ]+|[가-힯]+|[A-Za-z0-9]+")


def _muffle_tokens(body):
    """Verbatim chunks of a line, and the shortest one worth keeping.

    Returns `(tokens, keep_min)` because the threshold is a property of the
    script, not a constant: four characters is a short English word and a
    whole Japanese clause.

    `.split()` alone made this a no-op wherever words are not space-separated
    -- the entire utterance came back as one "word", sailed past the
    `_MUFFLE_MAX_WORDS` filter, and a character who should half-hear a
    whispered secret heard all of it. Every chunk here is still a verbatim
    substring, which `_scrub_invented_dialogue` depends on.
    """
    text = str(body or "")
    if _UNSPACED_SCRIPT.search(text):
        return _UNSPACED_CONTENT_RUN.findall(text), 1
    return ([w.strip(".,;:!?\"'“”‘’") for w in text.split()],
            _MUFFLE_KEEP_MIN)


def _muffle_middle(body, keep=3):
    """The middle few content chunks of a line, for the interaction loop.

    Shares `_muffle_tokens` with `_muffled_fragment` so there is ONE rule for
    what survives half-hearing. The loop used to slice `quote.split()`, which
    yields a single token in a language without spaces and therefore returned
    the whole utterance.

    And the pack's `muffle_join` for how the survivors are SET OUT, which was
    the other half of that same argument: a hardcoded ASCII space put 「小瓶
    捨」 in a story whose every other muffled line reads 「……小瓶……捨……」.
    A separator belongs to the language -- Japanese sets an ellipsis as the
    doubled leader with no spaces, and a half-width gap between two kanji runs
    reads as broken typesetting rather than as a gap in hearing. The template
    around this fragment supplies the leading and trailing ellipsis, so only
    the join is read here.
    """
    tokens, keep_min = _muffle_tokens(body)
    kept = [w for w in tokens if len(w) >= keep_min]
    if not kept:
        return _text("muffled_indistinct")
    start = max(0, len(kept) // 2)
    join = str(compositor_value("muffle_join"))
    return join.join(kept[start:start + keep])


def _muffled_fragment(body):
    """A partial transcript of what actually carried, not a description of it.

    This used to render "...something about <three middle words>...", which
    narrates the ACT of half-hearing instead of delivering the percept: the view
    said the perceiver heard something about a thing rather than letting them
    hear the pieces. It also read badly in prose and gave the narrator a stock
    phrase to echo.

    Each surviving word is emitted as its own ellipsis-separated chunk, and only
    ever verbatim -- `_scrub_invented_dialogue` validates a muffled line by
    checking every chunk against the lines actually spoken, so a chunk stitched
    across punctuation ("ledger, sink" -> "ledger sink") would fail that
    check and get the whole line dropped.
    """
    words, keep_min = _muffle_tokens(body)
    kept = [w for w in words if len(w) >= keep_min]
    if not kept:
        return _text("muffled_indistinct")
    if len(kept) > _MUFFLE_MAX_WORDS:
        # The longest carry best; original order is preserved so the fragment
        # still tracks the shape of the sentence.
        strongest = set(sorted(kept, key=len, reverse=True)[:_MUFFLE_MAX_WORDS])
        seen, kept2 = set(), []
        for w in kept:
            if w in strongest and w not in seen:
                seen.add(w)
                kept2.append(w)
        kept = kept2
    # The glyphs belong to the language: Japanese sets an ellipsis as the
    # doubled three-dot leader with no spaces (……棚……小瓶……), and ASCII dots
    # with half-width gaps read as broken typography inside Japanese prose.
    # The pack's own `muffled_indistinct` already used the right form, so the
    # same feature was being typeset two different ways.
    lead = str(compositor_value("muffle_ellipsis"))
    join = str(compositor_value("muffle_join"))
    return lead + join.join(kept) + lead


# `tone` is a free-text field and models fill it with two grammatically
# different things: an abstract NOUN ("warmth", "urgency", "a hint of
# steel") and an ADJECTIVE or adjective phrase ("bright", "quietly
# authoritative"). One slot was built for the first and fed both, so every
# adjectival tone rendered as "says with quietly authoritative in their
# voice" -- constant, reader-facing, and flagged in the corpus replay's
# prose sample as one of the two things a reader notices within minutes.
#
# The head word decides, and the DEFAULT IS ADJECTIVE: adjectives are what
# models emit most, and they are the half that was broken. A noun wrongly
# read as an adjective gives "in a warmth voice" -- bad, so the noun list
# below is explicit about the irregulars that no suffix catches, and the
# suffixes cover the productive endings that cannot be adjectives.


def _tone_clause(tone):
    """The dialogue tag's manner slot, agreeing with what kind of word the
    tone actually is. Returns "" or a leading-space clause."""
    tone = str(tone or "").strip().rstrip(".,;:")
    if not tone:
        return ""
    # An observable BEHAVIOUR, not a vocal quality: "with a smirk".
    articles = tuple(compositor_value("articles"))
    article_re = r"^(?:" + "|".join(map(re.escape, articles)) + r")\b"
    behavior_re = r"\b(?:" + "|".join(map(
        re.escape, compositor_value("tone_behavior_words"))) + r")\b"
    if re.search(behavior_re, tone, re.I):
        indefinite = compositor_value("indefinite_article")
        article = "" if re.match(article_re, tone, re.I) \
            else indefinite["other"] + " "
        return _text("tone_behavior", article=article, tone=tone)
    head = [w for w in re.split(r"[^\w]+", tone) if w]
    head = head[-1].casefold() if head else ""
    if head in _ling("_TONE_NOUNS") or head.endswith(_ling("_TONE_NOUN_SUFFIXES")):
        return _text("tone_noun", tone=tone)
    if re.match(article_re, tone, re.I):
        return _text("tone_article", tone=tone)
    indefinite = compositor_value("indefinite_article")
    article = (indefinite["vowel"] if tone[:1].casefold()
               in indefinite["vowels"] else indefinite["other"])
    return _text("tone_adjective", article=article, tone=tone)


def _inject_dialogue(view, display, quote, level, volume, can_see,
                    conducted=False, tone="", articulation=""):
    if level == "none":
        return view
    body = _quote_body(quote)
    if not body or _contains_quote(view, body):
        return view
    if level == "fragment":
        return _append_once(
            view, _text("muffled", fragment=_muffled_fragment(body)))
    if conducted:
        # Heard from inside the speaker: the mass around the listener is the
        # medium, so it arrives low and close rather than across a distance.
        return _append_once(
            view,
            _text("dialogue_conducted", label=display, body=body))
    # Two forms of the same verb, because the two frames below take different
    # ones. "You hear X" is a bare-infinitive construction -- "you hear her
    # SAY", never "you hear her says" -- and this wrote the inflected form into
    # both, so every view of a speaker the perceiver could not see carried
    # broken English: 226 occurrences across 71 turns of the live corpus, all
    # of them in exactly the situations this engine cares most about (a voice
    # through a door, in the dark, from inside an enclosure).
    verbs = compositor_value("dialogue_verbs")
    verb, bare = verbs.get(volume, verbs["default"])
    # Articulation is FORMATION, stamped at the source (see
    # _stamp_dialogue_articulation): the same malformed sound reaches every
    # listener, so it renders identically for all of them and rides the
    # dialogue tag rather than gating the level. The quote itself stays
    # verbatim -- the fidelity scrubs match on it, and dialogue fidelity
    # forbids rewriting words actually said.
    articulation_text = compositor_value("articulation")
    artic = articulation_text.get(articulation, articulation_text["default"])
    manner = _tone_clause(tone) if can_see else ""
    if can_see:
        add = _text("dialogue_visible", label=display, verb=verb,
                    manner=manner, articulation=artic, body=body)
    else:
        add = _text("dialogue_unseen", label=display, verb=bare,
                    articulation=artic, body=body)
    return _append_once(view, add)


def _content_tokens(text):
    """Distinctive (stopword-stripped, crudely stemmed) word tokens of a phrase
    -- the basis for 'has this beat already been narrated?' overlap."""
    toks = []
    for raw in re.split(r"[^\w]+", str(text or "").lower()):
        if not raw or raw in _ling("_OBSERVED_STOPWORDS"):
            continue
        for suf in ("ing", "ed", "es", "s"):
            if len(raw) > len(suf) + 2 and raw.endswith(suf):
                raw = raw[:-len(suf)]
                break
        toks.append(raw)
    return toks


def self_name_forms(primary_name, forms=None):
    """Every textual handle that means THIS perceiver, for _self_second_person.

    The scene keys alone are not enough: they carry the full display name and
    authored aliases, and prose does not. Measured live, a Director clause
    said "the base of Elyra's shaft" inside Elyra Voss's own view, and her
    forms -- 'Elyra Voss', 'elyra_voss_imp', 'Madame Elyra', ... -- matched
    none of it, so her own view named her in the third person on fifteen
    turns of one story. Prose reaches for the FIRST name of a multi-word
    name, so the word tokens of the primary name are forms too --
    `_player_name_forms` already draws exactly this conclusion for the
    player, which is why only the CHARACTERS' views carried the defect.

    Tokens come from the primary name only, never from aliases: an alias like
    'The Succu-Masseuse' would contribute 'The'. An ordinary-word token is
    safe to include because _self_second_person already matches those
    case-sensitively (_COMMON_WORD_NAMES).
    """
    out, seen = [], set()
    for form in [*(forms or []), *_player_name_forms(primary_name)]:
        text = str(form or "").strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
    return out


# Head nouns too generic to shorten a minted label onto. "the person"/"the
# figure" is not a shortening of one body's descriptor, it is the word every
# stranger label is built from, and rewriting it into "you" would claim any
# passing body as the perceiver.


def self_reference_forms(name, appearance=None, aliases=None, *,
                         labels=(), avoid=()):
    """The EPITHETS this engine mints for one body, as self-reference forms.

    `self_name_forms` above answers "what does prose call this mind by NAME".
    This answers the other half, and it exists because a name is not the only
    handle the engine itself puts into circulation: `_unknown_actor_label`
    mints a descriptor for every body an observer has not recognized, and
    every mind that receives that descriptor then writes it back out in its
    own declarations. The Director does it too.

    Measured live (three-model playthrough, 2026-08-12): the persona Corin
    reads "A young smith's apprentice with a borrowed sword", the composer
    minted "the young smith's apprentice" for every character in the square,
    and it came back through `director_resolve` ("Bryn turns toward the young
    smith's apprentice") and through the cast's own observable surfaces ("eyes
    settling on the sword at the apprentice's hip") into Corin's OWN view.
    The composer translates a canonical NAME into "you" for the body it
    belongs to; handed the epithet it minted, it had nothing to translate, so
    the player read about himself in the third person, described by a label
    that exists only because other people do not know who he is.

    The forms returned are deliberately narrow:

    - the exact minted label(s) -- the base `_unknown_actor_label` descriptor
      plus whatever `labels` the caller actually minted this beat (a widened
      or ordinal-distinguished variant), because those are the strings the
      engine put into circulation and nothing else is;
    - one SHORT definite form ("the apprentice") cut from a label's head
      noun, because prose shortens a long descriptor on second mention and
      that is exactly how the live case reached the player. Guarded three
      ways: the label must be long enough for the short form to be a genuine
      shortening, the head noun must not be generic
      (`_GENERIC_LABEL_HEADS`), and the head noun must not appear in any
      `avoid` label. THE HEAD IS THE NOUN THE LABEL IS BUILT ON, not its
      last word: a label carries a feature phrase after its noun ("the old
      woman with silver hair", "the unfamiliar person with a scar across
      one cheek"), and the last word of that phrase is a part or a thing,
      which claimed as self-reference would turn every "the hair" and "the
      cheek" in a view into "you" (found 2026-10-20, when feature-bearing
      labels became the rule rather than the exception).

    `avoid` is the set of labels this observer currently holds for OTHER
    bodies. Any form colliding with one of them is dropped outright: two
    strangers who look alike can share a descriptor, and rewriting a
    reference to one of them into "you" would tell the perceiver they did
    something somebody else did. Under-matching costs one clumsy sentence;
    over-matching invents an act.

    Indefinite variants ("a young smith's apprentice") are NOT returned. That
    phrasing is how prose introduces a body nobody has met, so matching it
    would reach for referents this cannot check.
    """
    avoid_labels = {str(a or "").strip().casefold()
                    for a in (avoid or []) if str(a or "").strip()}
    avoid_words = set()
    for label in avoid_labels:
        avoid_words.update(re.findall(r"[\w']+", label))
    minted = []
    for label in [_unknown_actor_label(name, appearance, aliases), *(labels or [])]:
        label = str(label or "").strip()
        if not label or label.casefold() in avoid_labels:
            continue
        if label.casefold() not in {m.casefold() for m in minted}:
            minted.append(label)
    out = list(minted)
    for label in minted:
        words = re.findall(r"[\w']+", label)
        if len(words) < 3:
            continue
        phrase = _referring.noun_phrase(words[1:]) or words[1:]
        head = phrase[-1].casefold()
        if head in _ling("_GENERIC_LABEL_HEADS") or head in avoid_words or len(head) < 3:
            continue
        short = f"the {phrase[-1]}"
        if short.casefold() in avoid_labels:
            continue
        if short.casefold() not in {m.casefold() for m in out}:
            out.append(short)
    return out


def _self_second_person(text, forms):
    """Rewrite a PERCEIVER's own name/alias forms inside engine-supplied prose
    into second person, before that prose is injected into their own view.

    Every perception view is written from its perceiver's own vantage ("You
    are in the lobby..."), but the deterministic action backstop appends an
    actor's `observable` surface verbatim -- and those surfaces are authored
    in third person by the acting agent, naming everyone else by name. So
    Dr. Moon's "steps briskly from the barricade toward Hinami" landed in
    HINAMI'S OWN view, producing the same beat twice in two different persons
    ("...beside your shoulder. Dr. Moon steps briskly ... toward Hinami...")
    and handing the narrator a player_view that names the player in the third
    person -- the exact thing its PERSON DISCIPLINE rule forbids.

    Scope is deliberately narrow and deterministic: only the perceiver's own
    explicit name/alias tokens are rewritten (possessive -> "your", every
    other form -> "you"), never pronouns. A third-person pronoun later in the
    same clause that referred to the perceiver ("...beside her shoulder") is
    left alone -- resolving that anaphora needs a referent the engine cannot
    determine when the actor shares the perceiver's pronouns, and a wrong
    guess would be worse than a mildly loose one. Quoted spans survive
    verbatim: a name spoken aloud is sensory signal, and dialogue fidelity
    forbids rewriting it.
    """
    text = str(text or "")
    if not text:
        return text
    patterns = []
    # A NAME WRITTEN IN AN UNSPACED SCRIPT is matched by its own boundary
    # (`find_names`): `name_occurrence_pattern` bounds a name with
    # `(?<!\w)`/`(?!\w)`, and a Japanese particle is a word character, so
    # ヒナミの / ヒナミは never matched and the perceiver read herself in the
    # third person inside her own view (agents_common audit F8). It becomes
    # the pack's own word for the perceiver (`self_label`: あなた), and the
    # particle stays, which is how Japanese writes the case.
    unspaced = sorted({str(f or "").strip() for f in (forms or [])
                       if str(f or "").strip()
                       and UNSPACED_SCRIPT.search(str(f))}, key=len, reverse=True)
    # WIDEST FORM FIRST. The forms of one body overlap by construction -- a
    # full name and the word tokens of it -- and applied in the order they
    # arrived, the short one fired inside the long one and the long one then
    # matched what was left: "toward Dov Aharon" became "toward you Aharon"
    # became "toward you you" (market run, 2026-09-05, F65), and the manor run
    # produced "turns away from you you" the same way. Sorted here rather than
    # at each caller, because every caller wants the same answer.
    for form in sorted({str(f or "").strip() for f in (forms or [])
                        if str(f or "").strip()}, key=len, reverse=True):
        if form in unspaced:
            continue
        # Ordinary-English single-token names ("Rose", "Hope") are matched
        # case-sensitively, exactly as the identity scrub does, so common
        # lowercase prose is never rewritten into second person.
        flags = 0 if form.casefold() in _ling("_COMMON_WORD_NAMES") else re.I
        patterns.append(name_occurrence_pattern(form, flags=flags))
    if not patterns and not unspaced:
        return text
    segments = _ling("_QUOTED_SPAN_RE").split(text)
    for i in range(0, len(segments), 2):  # even indices = unquoted prose
        before = segments[i]
        after = _self_unspaced_names(before, unspaced) if unspaced else before
        for pattern in patterns:
            after = pattern.sub(_self_pronoun_sub, after)
        # A name in SUBJECT position leaves the verb inflected for third
        # person singular ("Hinami is caught" -> "You is caught"), which
        # would reach the player as visibly broken prose. Only run the
        # repair on segments this pass actually rewrote.
        segments[i] = _fix_you_agreement(after) if after != before else before
    return "".join(segments)


def _fix_you_agreement(text):
    """Re-inflect the verb after a "you" that replaced a third-person subject.

    Handles the irregular copulas/auxiliaries by table and regular present-
    tense verbs by undoing the third-person-singular -s. "you is/was/has/does
    <x>" and "you <verb>s" are never grammatical English, so this is safe to
    run over prose that already contained a legitimate "you".
    """
    def _sub(m):
        you, gap, word = m.group(1), m.group(2), m.group(3)
        # Third-person-singular forms that must agree with an inserted "you".
        #
        # Words that can follow a subject, end in -s, and are NOT verbs -- the guard
        # on the regular-verb rule below, which otherwise strips a meaningful "s"
        # ("You always" -> "You alway"). Deliberately a closed list: a missed entry
        # costs one dropped letter, while dropping the rule entirely costs "You steps".
        #
        #
        # Stems that take -es rather than a bare -s ("catch/catches", "push/pushes",
        # "fix/fixes", "go/goes", "pass/passes"); everything else drops a single -s.
        # "ss" not "s": a stem ending in ONE s is rare ("bus"), while "loses",
        # "raises", "closes" are common and keep their stem-final e.
        fixed = _ling("_YOU_AGREEMENT").get(word.lower())
        if fixed is None:
            fixed = _base_from_third_person_s(word)
        if fixed is None:
            return m.group(0)
        if word[:1].isupper():
            fixed = fixed[:1].upper() + fixed[1:]
        return f"{you}{gap}{fixed}"

    return _ling("_YOU_VERB_RE").sub(_sub, str(text or ""))


#: An English possessive written straight after a name in an unspaced script
#: ("ヒナミ's hand" in an English story).
_TRAILING_POSSESSIVE = re.compile(r"['’]s(?![A-Za-z])")


def _self_unspaced_names(text, forms):
    """The perceiver's unspaced-script name forms in `text` rewritten to the
    pack's word for the perceiver (`compositor.self_label`), longest form
    first and never inside a longer name (`find_names`). An English
    possessive written after the name takes "your", as `_self_pronoun_sub`
    gives a Latin name."""
    hits = find_names(text, tuple(forms), flags=0)
    if not hits:
        return text
    self_word = str(compositor_value("self_label") or "")
    if not self_word:
        return text
    out, at = [], 0
    for start, end, _form in hits:
        out.append(text[at:start])
        possessive = _TRAILING_POSSESSIVE.match(text, end)
        word = "your" if possessive else self_word
        before = "".join(out).rstrip()
        if (not before or before[-1] in ".!?\n") and word[:1].islower():
            word = word.capitalize()
        out.append(word)
        at = possessive.end() if possessive else end
    out.append(text[at:])
    return "".join(out)


def _self_pronoun_sub(m):
    """Replacement callback for _self_second_person: possessive -> your,
    anything else -> you, capitalized when it opens a sentence."""
    word = "your" if m.group(1) else "you"
    before = m.string[:m.start()].rstrip()
    if not before or before[-1] in ".!?\n":
        word = word.capitalize()
    return word


def _observable_predicate(display, surface):
    """Compose one clean delivered sentence from an actor `display` label and an
    intent-free `observable` surface, without the double-subject run-ons the
    alpha3.1.2 full-sentence observable produced ('Dr. Moon Dr. Moon tilts...',
    'Dr. Moon The flashlight beam moves...'). Strip a leading occurrence of the
    actor's own name tokens (so an actor-led surface becomes a predicate); then
    if the surface still opens with its OWN capitalized subject (an independent
    clause like 'The flashlight beam moves...'), keep it verbatim as its own
    sentence -- prepending display would double the subject; otherwise it is a
    predicate and takes the display prefix."""
    surface = str(surface or "").strip()
    if not surface:
        return None
    # A SURFACE THAT ALREADY OPENS WITH THE LABEL IS A PREDICATE AFTER IT.
    # The identity scrub rewrites a name inside a surface to the observer's
    # label, so the surface arrives as "The constable's clerk of twenty-six
    # reaches out"; the token peel below misses a possessive, and the label
    # was prefixed again ("The constable's clerk of twenty-six constable's
    # clerk of twenty-six reaches out", Coldharbour Fair turn 4, 2026-09-15).
    _label = str(display or "").strip()
    if _label and surface.casefold().startswith(_label.casefold()):
        rest = surface[len(_label):].lstrip(" ,:;")
        if rest:
            surface = rest
    # The label's own article is not a name token: peeling it off "The
    # flashlight beam moves" for a label of "the gaunt man" doubled the
    # subject the docstring exists to prevent.
    disp_tokens = _identity_token_set(display) - set(compositor_value("articles"))
    words = surface.split()
    # Peel leading actor-name tokens / a leading pronoun off the surface.
    while words and (words[0].strip(".,;:'").casefold() in disp_tokens
                     or words[0].casefold()
                     in _ling("_LEADING_SUBJECT_PRONOUNS")):
        words = words[1:]
    stripped = " ".join(words).strip()
    if not stripped:
        return _text("observable_empty", label=display)
    first = stripped.split(maxsplit=1)[0]
    # Independent subject clause (starts with a capitalized non-actor word that
    # isn't a normal sentence-initial cap): render as its own sentence.
    #
    # A CAPITAL LETTER IS NOT A SUBJECT. A surface that opens with a verb in
    # the third-person-singular ("Wipes his hands on his apron...") is a
    # predicate whatever its case -- the background stage capitalises the
    # first word of an action as a matter of style -- and reading it as an
    # independent clause published it with no subject at all: the view read
    # "Wipes his hands..." and the narrator, handed a subjectless act beside
    # a stranger, supplied one from an earlier beat (Harrowmere replay
    # 2026-09-03 turn 24, the smith rendered as "the miller"). The same
    # verb test the episode renderer already applies to its first word.
    independent = (first[:1].isupper()
                   and first.casefold() not in disp_tokens
                   and _base_from_third_person_s(first) is None)
    if independent:
        return stripped if stripped.endswith((".", "!", "?")) else stripped + "."
    body = stripped[0].lower() + stripped[1:]
    # The template closes the sentence; a surface that arrived already
    # closed ("...eyes fixed on the light.") would close it twice.
    if body.endswith(".") and not body.endswith("..."):
        body = body[:-1].rstrip()
    return _text("observable", label=display, body=body)


def _action_already_rendered(view, display, surface):
    """True when the view already narrates this action (so the deterministic
    backstop should stay silent). Upgrades the old exact-substring test to
    content-token overlap, which catches the LLM's paraphrase of the same
    beat. Biases toward silence: since alpha3.1.2 duplication is the common,
    player-visible failure and a missed injection the rare one."""
    surf = set(_content_tokens(surface))
    if not surf:
        return False
    view_text = str(view or "")
    disp_tokens = _identity_token_set(display)
    for sent in re.split(r"(?<=[.!?])\s+", view_text):
        raw = set(re.split(r"[^\w]+", sent.lower()))
        stoks = set(_content_tokens(sent))
        overlap = surf & stoks
        if not overlap:
            continue
        if len(overlap) / len(surf) >= 0.6:
            return True
        if (disp_tokens & raw) and len(overlap) >= 2:
            return True
    # WHOLE-VIEW pass. The per-sentence loop above misses two common shapes:
    # the perception LLM spreads ONE beat over several sentences ("Dr. Moon is
    # right in front of you, having crossed quickly. Her arm is under yours,
    # bracing you against the wall."), and the sentence splitter itself breaks
    # on the abbreviation in a name like "Dr. Moon" -- which strands the actor
    # token in one fragment and the action tokens in the next, disarming the
    # disp_tokens rule exactly where it was needed. Live consequence (chat 27
    # turn 54): the beat was appended a SECOND time at the end of the view,
    # AFTER the dialogue, so the narrator rendered Dr. Moon crossing to brace
    # the player, then speaking, then crossing to brace them again.
    #
    # Requires the view to NAME this actor and to share strictly more
    # distinctive tokens than the per-sentence rule asks for: the whole view
    # is a far larger surface for coincidental matches than one sentence.
    raw_all = set(re.split(r"[^\w]+", view_text.lower()))
    whole_overlap = surf & set(_content_tokens(view_text))
    if (disp_tokens & raw_all) and len(whole_overlap) >= 3:
        return True
    return False


def _inject_action(view, display, attempt, can_see, event_id=None, delivered=None,
                   self_forms=None):
    """Append one actor's observable action to a perceiver's view.

    `self_forms` are the RECEIVING perceiver's own name/alias forms. They are
    rewritten to second person BEFORE the duplicate check, so the check scores
    the same person the LLM's own prose used ("...beside your shoulder") rather
    than the acting agent's third-person surface -- which is why the duplicate
    slipped through as well as the person mismatch. See _self_second_person.
    """
    if not attempt or not can_see:
        return view
    if delivered is not None and event_id:
        if event_id in delivered:
            return view
        delivered.add(event_id)
    if self_forms:
        attempt = _self_second_person(attempt, self_forms)
    if _action_already_rendered(view, display, attempt):
        return view
    sentence = _observable_predicate(display, attempt)
    if not sentence:
        return view
    return _append_once(view, sentence, marker=sentence)

# `appearance_of` builds a STRUCTURED summary for payload fields -- labelled
# segments joined by semicolons -- which is right for a field a model reads and
# wrong for prose. It was being pasted verbatim into perception views, so every
# view of every turn in a 47-turn chat read:
#
#     "You see A tall figure in a grey travelling coat, hood raised.;
#      clothing state: soaked through, ..."
#
# -- a capital mid-sentence, a full stop before a semicolon, and the field
# labels themselves narrated. Normalizing at the PASTE POINT rather than at the
# five construction sites keeps one mechanism and leaves the payload form,
# which is correct, alone.


def _appearance_as_prose(appearance):
    """A structured appearance summary rendered as something a view can hold."""
    text = str(appearance or "").strip()
    if not text:
        return ""
    for label, replacement in _ling("_APPEARANCE_LABELS"):
        text = text.replace(label, replacement)
    # The base appearance is authored as its own sentence; its terminal stop
    # and leading capital both fight the clause it is now part of.
    text = re.sub(r"\.\s*(?=,)", "", text)
    text = text.rstrip(" .")
    if text[:1].isupper() and re.match(r"^(a|an|the)\b", text, re.I):
        text = text[:1].lower() + text[1:]
    return re.sub(r"\s{2,}", " ", text).strip(" ,")


def _inject_visible_actor(
    view,
    *,
    display,
    appearance,
    relation,
):
    if not has_visual(relation):
        return view

    text = str(view or "").strip()

    for pattern in _ling("_VISUAL_CONTRADICTION_RES"):
        text = pattern.sub("", text)

    text = re.sub(r"\s{2,}", " ", text).strip()

    if appearance:
        prose = _appearance_as_prose(appearance)
        # The perception model may already have rendered the same visible
        # body in natural prose. Exact-marker dedupe cannot recognize a
        # paraphrase, which produced a second mechanical "You see ..." tail
        # on the live chat-38 view. Use the same conservative content-overlap
        # test as action injection before adding the deterministic floor.
        if prose and _action_already_rendered(text, display, prose):
            return text
        return _append_once(
            text,
            _text("appearance", description=prose),
            # Marker stays the RAW form: it is what a previous injection would
            # have left behind, and dedupe must catch those too.
            marker=prose or appearance,
        )

    return _append_once(
        text,
        _text("appearance", description=display),
        marker=display,
    )

def _normalise_views(raw_views, perceivers):
    if not isinstance(raw_views, dict):
        raw_views = {}
    # Casefolded map of the literal perceiver ids themselves ("player",
    # "extra:<id>", numeric ids) onto their canonical spelling -- a model
    # returning "Player" or "Extra:12" must fold onto the exact key every
    # consumer reads (views.get("player") etc.) instead of being dropped.
    id_by_fold = {str(p["id"]).casefold(): str(p["id"]) for p in perceivers}
    name_to_id = {}
    for p in perceivers:
        name_to_id[p["name"]] = str(p["id"])
        name_to_id[p["name"].lower()] = str(p["id"])
    clean = {}
    for k, v in raw_views.items():
        sk = str(k).strip()
        if sk.lower() == "player" and "player" not in id_by_fold:
            continue
        canonical_id = id_by_fold.get(sk.casefold())
        if canonical_id is not None:
            sk = canonical_id
        elif not sk.isdigit():
            sk = name_to_id.get(sk) or name_to_id.get(sk.lower()) or sk
        if isinstance(v, str):
            v = v.strip()
            if not v:
                v = None
        clean[sk] = v
    return clean

def _compose_residue_view(level, *, targeted=False, loud_event=False, pain=False,
                          woke="", episode=False):
    """The content-free perception RESIDUE for a non-awake mind (asleep /
    sedated / unconscious). An unconscious mind integrates no channel into
    scene, identity, or words -- so this NEVER carries speech content, a name, a
    visual scene, or a spatial fact. It delivers only interoception (pain, being
    moved) and the direction-less trace of the strongest stimuli (a loud event
    as a wordless intrusion). Deterministic and template-built: the perception
    LLM is never asked for a non-awake view (it would leak with the full payload
    in hand), so this IS the whole output. The fragments become, verbatim, that
    mind's fragmentary memory of the beat (commit mints episodic memory from the
    view), which is exactly the vague recovered impression waking should give.

    WOKEN (`woke`, DESIGN_SOUND_FIELD § 13): a sleeper a sound woke this beat
    is told THAT it did, and what kind of sound -- their own name, a shout,
    a voice, a noise (`spatial_listener.WAKING_SOUNDS`) -- and nothing else:
    no word of the line but the fact of the name, no speaker, no room. The
    rest of the beat happened while they slept; from the next beat they
    perceive as anyone awake does.

    `episode` asks for the memory's own words where the view's second person
    cannot be turned by the swap (`composer._first_person`): the pain is felt
    "in a body you can't quite feel", a subject inside a relative clause that
    no mark in the text names as the subject, so the pack carries its first
    person (`residue.pain_episode`). Every other fragment is turned by the
    swap, which reads the role each of them marks."""
    residue = compositor_value("residue")
    woke_text = (residue.get("woke") or {}).get(str(woke or ""))
    if woke_text:
        return woke_text
    lead = residue["lead"].get(level, residue["lead"]["default"])
    frag = []
    if pain:
        frag.append(residue["pain_episode" if episode else "pain"])
    if targeted:
        frag.append(residue["targeted"])
    if loud_event:
        frag.append(residue["loud_event"])
    if not frag:
        closing = residue["closing"].get(
            level, residue["closing"]["default"])
        return (lead + closing).strip()
    body = residue["separator"].join(frag[:2])
    body = body[0].upper() + body[1:]
    return _text("residue_content", lead=lead, body=body)


def _ensure_environment(view, perceiver, display, rel, vis, action_desc):
    if view:
        return view
    parts = [_text("room", room=perceiver.get("room_name"))]
    if perceiver.get("room_notes"):
        parts.append(perceiver["room_notes"])
    # `same_room` is true for a body sealed inside something standing in the
    # room -- a carried body's position derives to its carrier's. Announcing
    # it as "here with you" and pasting its observable is the same bypass the
    # injection sites had; `concealed` is absent (falsy) for every rel that
    # never went through containment, so open scenes are unchanged.
    if rel.get("same_room") and not rel.get("concealed"):
        parts.append(_text("environment_here", label=display))
        if action_desc:
            # action_desc is now an intent-free `observable` surface (predicate
            # or independent clause); compose it cleanly rather than gluing it
            # after "attempts to" (which double-verbs "attempts to tilts...").
            sentence = _observable_predicate(display, action_desc)
            if sentence:
                parts.append(sentence)
    elif vis:
        parts.append(_text("environment_nearby", label=display))
    return " ".join(parts)

def _fallback_perception_views(perceivers, dlog, resolved_event=None, known=None):
    views = {}
    for p in perceivers:
        pid = str(p["id"])
        p_room = p.get("room")
        parts = []
        rname = p.get("room_name")
        rnotes = p.get("room_notes")
        if rname and rname != "None":
            parts.append(_text("room", room=rname))
        if rnotes:
            parts.append(rnotes)
        for d in dlog:
            spk_room = d.get("speaker_room")
            if spk_room and p_room and spk_room == p_room:
                speaker = d.get("speaker", "?")
                # Same recognition gate as the main injection paths: a
                # speaker this perceiver has never been introduced to must
                # not be named by the no-LLM fallback either (the quote
                # itself is legitimately heard and stays verbatim).
                if known is not None and speaker != p.get("name") \
                        and speaker not in (known.get(p.get("name")) or []):
                    speaker = _unknown_actor_label(speaker)
                parts.append(_text(
                    "fallback_speech", label=speaker,
                    quote=d["exact_quote"]))
        views[pid] = " ".join(parts) if parts else None
    return views
