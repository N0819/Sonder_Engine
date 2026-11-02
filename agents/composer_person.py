"""Grammatical person: an authored third-person line turned into the observer's
second person for the view and its own first person for memory and for its
own attempt.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from language_runtime import linguistic
from .common import (
    name_occurrence_pattern,
    _base_from_third_person_s,
    _fix_you_agreement,
)


#: Words that may follow an OBJECT pronoun and never a possessive one. A
#: possessive is followed by the thing possessed -- a noun, or an adjective
#: on its way to one -- so a preposition or a conjunction after "her" settles
#: that "her" is the object. This is a closed class the engine owns rather
#: than an attempt to anticipate English (CLAUDE.md's carve-out), and the
#: genuinely ambiguous members are left OUT on purpose: "her back", "her
#: past" and "her present" are possessives as readily as adverbs, so none of
#: those three is here.
_OBJECT_PRONOUN_FOLLOWERS = frozenset((
    "at", "to", "into", "onto", "in", "on", "out", "from", "by", "with",
    "without", "for", "toward", "towards", "through", "across", "over",
    "under", "against", "behind", "before", "after", "beside", "between",
    "among", "up", "down", "off", "away", "along", "upon", "within",
    "beneath", "below", "above", "inside", "outside",
    "and", "or", "but", "so", "then", "while", "as", "when", "if",
    "because", "though", "although", "until", "since",
))


def _reads_as_possessive(tail) -> bool:
    """Is the pronoun just matched a possessive, judged by what follows it?

    The two readings are spelled the same for a great many bodies -- `her` is
    both -- so the fallback asked only whether ANY word followed, and a
    prepositional phrase after an object pronoun is a word. Measured live
    (chat 99): a stored pose detail reading `holding her at the back of the
    mouth` reached its owner's own view as `holding your at the back of the
    mouth`, which is not English and which named the wrong body besides.

    A possessive is followed by what is possessed. A preposition or a
    conjunction is neither, so it settles the reading the other way.
    """
    match = re.match(r"\s+([A-Za-z][\w'\u2019-]*)", str(tail or ""))
    if not match:
        return False        # end of fragment, or punctuation: object
    return match.group(1).casefold() not in _OBJECT_PRONOUN_FOLLOWERS


def _pose_owner_second_person(text, pronouns, other_forms=(), *,
                              person="second"):
    """Rewrite pronouns whose referent is known from a pose's ownership.

    A pose is stored under the body it describes.  Its ``posture``,
    ``constraint`` and ``detail`` therefore have an explicit grammatical
    owner even when a model writes them as third-person fragments.  That is a
    materially narrower case than arbitrary prose anaphora: within each
    comma/semicolon-delimited fragment, the owner's declared pronouns refer
    to the owner until another body is explicitly named.  After that name we
    leave matching pronouns alone rather than guessing which body they mean.

    This is what turns ``settled on her heels ... Mara`` into ``settled on
    your heels ... Mara`` without turning the later ``steady her`` (after
    Mara has been named) into ``steady you``. Quoted spans are untouched.

    ``person="first"`` is the same rewrite into the owner's OWN first person,
    for the episode (`_said_as_mine`): the third person still says which role
    each pronoun had -- "she" the subject, "her" the object or the possessive
    -- and English's second person no longer does, so "as she turns her
    attention" is "as I turn my attention" here, where the swap of "as you
    turn your attention" could only guess (chat 152 turn 14 filed "as me
    turn my attention").
    """
    first = person == "first"
    text = str(text or "")
    if not text or not isinstance(pronouns, dict):
        return text
    subject = str(pronouns.get("subject") or "").strip()
    obj = str(pronouns.get("object") or "").strip()
    possessive = str(pronouns.get("possessive") or "").strip()
    if not any((subject, obj, possessive)):
        return text

    # A NAME'S OCCURRENCE INCLUDES THE TITLE THAT LEADS IT, here as well: the
    # cutoff marks where another body's name begins, and "Lord Edmund" begins
    # at "Lord". Cutting one word later left the title inside the span being
    # rewritten for somebody else.
    other_patterns = []
    for form in sorted({str(f or "").strip() for f in other_forms if str(f or "").strip()},
                       key=len, reverse=True):
        other_patterns.append(name_occurrence_pattern(form, flags=re.I))

    reflexives = {
        "she": "herself", "he": "himself", "they": "themselves",
        "it": "itself",
    }
    reflexive = reflexives.get(subject.casefold(), "")
    forms = sorted({f.casefold() for f in (subject, obj, possessive, reflexive)
                    if f}, key=len, reverse=True)
    if not forms:
        return text
    pronoun_re = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(f) for f in forms) + r")(?!\w)",
        re.I)

    def rewrite_fragment(fragment):
        cutoff = len(fragment)
        for pattern in other_patterns:
            match = pattern.search(fragment)
            if match:
                cutoff = min(cutoff, match.start())
        prefix, suffix = fragment[:cutoff], fragment[cutoff:]

        def replace(match):
            word = match.group(1)
            low = word.casefold()
            if reflexive and low == reflexive.casefold():
                replacement = "myself" if first else "yourself"
            elif ((low == possessive.casefold()
                   and low != obj.casefold()) or
                  (low == possessive.casefold() == obj.casefold()
                   and _reads_as_possessive(prefix[match.end():]))):
                replacement = "my" if first else "your"
            elif not first:
                replacement = "you"
            elif low == subject.casefold() and (
                    low != obj.casefold()
                    or _reads_as_subject(prefix[match.end():])):
                # The subject's own case -- or, for a pronoun spelled alike
                # in both ("it"), the verb that agrees with it.
                return "I"
            else:
                replacement = "me"
            return replacement.capitalize() if word[:1].isupper() else replacement

        rewritten = pronoun_re.sub(replace, prefix)
        return (_fix_i_agreement(rewritten) if first
                else _fix_you_agreement(rewritten)) + suffix

    quoted = linguistic("agents.common", "_QUOTED_SPAN_RE").split(text)
    for index in range(0, len(quoted), 2):
        pieces = re.split(r"([,;—])", quoted[index])
        for piece_index in range(0, len(pieces), 2):
            pieces[piece_index] = rewrite_fragment(pieces[piece_index])
        quoted[index] = "".join(pieces)
    return "".join(quoted)


def _action_target_second_person(text, target_forms, target_pronouns,
                                 other_forms=(), *, owner="your"):
    """Repair target-owned body pronouns after an explicit target name.

    `owner` is the word the owned body part takes: the observer's "your" in
    the view, its own "my" in the episode's first person (`act_percept`).

    Character observables are predicates whose omitted subject is the actor.
    When actor and target share pronouns, models commonly write a target once
    and then fall back to an ambiguous possessive: ``from Mara's back down
    between her thighs``.  Merely replacing the exact name produces ``your
    back ... her thighs`` and hands the action to the wrong body.

    This deliberately does *less* than general anaphora resolution.  It runs
    only when the event structurally targets this observer, only after an
    explicit form of that observer in the same sentence, and only when the
    matching possessive owns a body noun, optionally through a small
    language-pack list of anatomical modifiers. Subject pronouns, ``her
    own``, objects, quoted speech, arbitrary possessions, and everything
    after another explicitly named body are untouched.
    """
    text = str(text or "")
    if not text or not isinstance(target_pronouns, dict):
        return text
    possessive = str(target_pronouns.get("possessive") or "").strip()
    forms = sorted({str(form or "").strip() for form in target_forms or ()
                    if str(form or "").strip()}, key=len, reverse=True)
    if not possessive or not forms:
        return text

    # The explicit form of this observer that licenses the repair is a whole
    # NAME occurrence, title and article included -- "facing Lord Edmund
    # Harrowgate" names him once, at "Lord", not at "Edmund" with a stray
    # honorific in front (manor run 2026-09-05, PC8).
    target_re = name_occurrence_pattern(forms, flags=re.I)
    other_patterns = [
        name_occurrence_pattern(form, flags=re.I)
        for form in sorted({str(form or "").strip()
                            for form in other_forms or ()
                            if str(form or "").strip()}, key=len, reverse=True)
    ]
    body_nouns = sorted(linguistic(
        "agents.common", "_OWN_BODY_NOUNS"), key=len, reverse=True)
    modifiers = sorted(linguistic(
        "agents.common", "_BODY_OWNERSHIP_MODIFIERS"), key=len, reverse=True)
    modifier_part = ((r"(?:(?:" + "|".join(re.escape(word)
                                            for word in modifiers)
                      + r")\s+){0,2}") if modifiers else "")
    owned_body_re = re.compile(
        r"(?<!\w)" + re.escape(possessive)
        + r"(?=\s+(?!own\b)" + modifier_part + r"(?:"
        + "|".join(re.escape(noun) for noun in body_nouns)
        + r")\b)", re.I)

    quoted = linguistic("agents.common", "_QUOTED_SPAN_RE").split(text)
    for index in range(0, len(quoted), 2):
        sentences = re.split(r"([.!?]+\s*)", quoted[index])
        for sentence_index in range(0, len(sentences), 2):
            sentence = sentences[sentence_index]
            named = target_re.search(sentence)
            if not named:
                continue
            prefix, suffix = sentence[:named.end()], sentence[named.end():]
            cutoff = len(suffix)
            for pattern in other_patterns:
                match = pattern.search(suffix)
                if match:
                    cutoff = min(cutoff, match.start())
            owned, remainder = suffix[:cutoff], suffix[cutoff:]
            suffix = owned_body_re.sub(owner, owned) + remainder
            sentences[sentence_index] = prefix + suffix
        quoted[index] = "".join(sentences)
    return "".join(quoted)


# --------------------------------------------------------------------------
# The first person of an authored line, where the rewrite knows the role
# --------------------------------------------------------------------------

def _reads_as_subject(tail) -> bool:
    """Does the word after a name or pronoun agree with it as its SUBJECT?

    The same judgment `common._fix_you_agreement` acts on when it re-inflects
    the verb after a "you" that replaced a third-person subject: the next
    word is a third-person-singular form -- an auxiliary in the pack's
    agreement table, or a regular present verb's -s. A name followed by
    anything else (a noun phrase, a preposition, the end) is not the subject
    of that word."""
    match = re.match(r"\s+([A-Za-z][\w'’-]*)", str(tail or ""))
    if not match:
        return False
    word = match.group(1)
    return (word.casefold() in linguistic("agents.common", "_YOU_AGREEMENT")
            or _base_from_third_person_s(word) is not None)


def _fix_i_agreement(text):
    """Re-inflect the verb after an "I" that replaced a third-person subject
    -- the first-person twin of `common._fix_you_agreement`, and read from
    it rather than from a table of its own: the second person's form of the
    verb ("is" -> "are"), turned by the swap's own be row ("you are" -> "I
    am"). "I is", "I isn't" and "I turns" are never English, so this is as
    safe over prose that already held an "I" as its twin is."""
    def _sub(m):
        i, gap, word = m.group(1), m.group(2), m.group(3)
        second = linguistic(
            "agents.common", "_YOU_AGREEMENT").get(word.casefold())
        if second is None:
            base = _base_from_third_person_s(word)
            if base is None:
                return m.group(0)
            fixed = base
        else:
            turned = _first_person("you " + second)
            fixed = turned.split(" ", 1)[1] if " " in turned else second
        if word[:1].isupper():
            fixed = fixed[:1].upper() + fixed[1:]
        return f"{i}{gap}{fixed}"

    return re.sub(r"(?<![\w'’])(I)(\s+)([A-Za-z’']+)", _sub,
                  str(text or ""))


def _self_first_person(text, forms):
    """`common._self_second_person` into the perceiver's OWN first person,
    for the episode: a possessive name is "my", a name its next word agrees
    with as subject is "I" (the verb re-inflected for it), any other name is
    "me" -- the judgment the second-person rewrite makes when it re-inflects
    the verb after its "you", made here while the name still says which.

    Measured: "turns from the crag toward the tie-up where Pell stands" was
    rewritten "where you stand" for Pell and remembered "where me stand"
    (the lighthouse probe, 2026-10-20, chat 2 row 37)."""
    text = str(text or "")
    if not text:
        return text
    patterns = []
    for form in sorted({str(f or "").strip() for f in (forms or [])
                        if str(f or "").strip()}, key=len, reverse=True):
        flags = 0 if form.casefold() in linguistic(
            "agents.common", "_COMMON_WORD_NAMES") else re.I
        patterns.append(name_occurrence_pattern(form, flags=flags))
    if not patterns:
        return text

    def _sub(m):
        before = m.string[:m.start()].rstrip()
        opens = not before or before[-1] in ".!?\n"
        if m.group(1):
            return "My" if opens else "my"
        # A name between two verbs is the first one's object: English puts
        # the object straight after its verb. Without this, "hands Pell
        # letters" -- which the view's own agreement repair already reads as
        # "hands you letter" -- came back "hands I letter".
        prior = re.search(r"([A-Za-z][\w'’-]*)$", before)
        after_a_verb = bool(prior) and (
            prior.group(1).casefold() in linguistic(
                "agents.common", "_YOU_AGREEMENT")
            or _base_from_third_person_s(prior.group(1)) is not None)
        if not after_a_verb and _reads_as_subject(m.string[m.end():]):
            return "I"
        return "Me" if opens else "me"

    segments = linguistic("agents.common", "_QUOTED_SPAN_RE").split(text)
    for i in range(0, len(segments), 2):
        before = segments[i]
        after = before
        for pattern in patterns:
            after = pattern.sub(_sub, after)
        segments[i] = _fix_i_agreement(after) if after != before else before
    return "".join(segments)


#: One word of the person -- a pronoun of the first or the second person,
#: with its contracted auxiliary and the be form that agrees with it -- for
#: `_same_but_for_person`, which compares two renderings of one line with
#: the person taken out.
_PERSON_WORDS_RE = re.compile(
    r"(?<![\w'’])(?:I|me|my|mine|myself|you|your|yours|yourself)"
    r"(?:['’](?:m|re|ve|ll|d))?"
    r"(?:\s+(?:am|are|was|were)(?:n['’]t)?(?:\s+not)?)?"
    r"(?![\w'’])", re.I)


def _same_but_for_person(mine, view):
    """Do two renderings of one line say the same thing, the person aside?

    THE EPISODE NEVER OUTRUNS THE VIEW (rule 03 § 5.2): a first person
    carried beside a view's text is that text in another person or nothing.
    Quoted spans must match exactly; outside them every word of the person
    is set aside and the rest must match."""
    def _flat(text):
        segments = linguistic(
            "agents.common", "_QUOTED_SPAN_RE").split(str(text or ""))
        for i in range(0, len(segments), 2):
            segments[i] = _PERSON_WORDS_RE.sub("\x00", segments[i])
        return " ".join("".join(segments).split())
    return bool(str(mine or "").strip()) and _flat(mine) == _flat(view)


def _said_as_mine(data, field):
    """A percept's text `field` in the episode's first person.

    The rewrite that put the observer's own name or pronouns into the
    second person also wrote them into the first (`<field>_mine`), where the
    third person still said which role each had; that rendering is kept when
    it says what the view said, person aside, and the swap turns whatever
    the rewrite did not write. Otherwise the swap reads the view's text."""
    data = data or {}
    text = str(data.get(field) or "").strip()
    mine = str(data.get(field + "_mine") or "").strip()
    if mine and _same_but_for_person(mine, text):
        return _first_person(mine)
    return _first_person(text)


def _mine_if_it_matters(mine, view):
    """The first-person rendering worth carrying beside `view`: only one that
    passes `_same_but_for_person` and differs from what the swap would make
    of the view -- every other line is the swap's, and carries nothing."""
    mine, view = str(mine or "").strip(), str(view or "").strip()
    if not mine or mine == view or not _same_but_for_person(mine, view):
        return ""
    return mine if _first_person(mine) != _first_person(view) else ""


# --------------------------------------------------------------------------
# A mind's own act, in its own first person, as its attempt
# --------------------------------------------------------------------------

#: The third person's personal pronouns, one set to each subject -- the
#: closed paradigm, a schema rather than a guess at phrasing. `it` is not
#: here: in an act it is the thing handled ("tucks it"), and a doer who is
#: an "it" is not turned (`own_attempt`).
_THIRD_PERSON_SETS = (
    frozenset(("he", "him", "his", "himself")),
    frozenset(("she", "her", "hers", "herself")),
    frozenset(("they", "them", "their", "theirs", "themselves")),
)

#: Every personal pronoun that stands as a verb's object or as its object's
#: owner, in each person -- the same paradigm, read from the verb's side.
_OBJECT_PRONOUNS = frozenset((
    "me", "my", "myself", "you", "your", "yourself", "him", "his", "himself",
    "her", "hers", "herself", "it", "its", "itself", "us", "our", "ourselves",
    "them", "their", "themselves"))

#: The words that join one verb phrase of the doer's to the next where the
#: pack's coordinators (`referring.coordinator`: "and", "or") do not: the
#: sequencer and the contrasting conjunctions -- a closed grammatical class,
#: as the pronouns are. Every other breath word the pack holds
#: (`_BREATH_CONJUNCTIONS`) subordinates: it opens a clause of its own subject.
_SEQUENCERS = frozenset(("then", "but", "yet"))

_WORD_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def _opens_an_object(words, i, reach=3):
    """Is the word at `i` followed by an object -- a pronoun, a determiner, a
    number or a name -- straight away, or after the prepositions and
    particles the pack owns (`referring.phrase_openers`)? What only a verb or
    a preposition is followed by, never a noun ending a phrase."""
    from language_runtime import referring
    dets = set(referring.articles()) | {
        str(w).casefold()
        for w in linguistic("agents.common", "_DEFINITE_DETS")}
    openers = referring.phrase_openers()
    k = i + 1
    while k < len(words) and k <= i + reach:
        word = words[k]
        if not _WORD_TOKEN.fullmatch(word):
            return False
        low = word.casefold()
        if (low in _OBJECT_PRONOUNS or low in dets or referring.is_number(word)
                or (word[:1].isupper() and word[1:2].islower())):
            return True
        if low not in openers:
            return False
        k += 1
    return False


def _participle(word):
    """A word shaped like a participle -- the head of an absolute phrase
    ("hands clasped behind back", "eyes following the bow")."""
    low = str(word or "").casefold()
    return len(low) > 4 and low.endswith(("ing", "ed"))


def _pronoun_forms(pronouns):
    """Every form of one pronoun set, casefolded: the card's subject, object
    and possessive, and the paradigm's set its subject heads."""
    if not isinstance(pronouns, dict):
        return frozenset()
    forms = {str(pronouns.get(role) or "").strip().casefold()
             for role in ("subject", "object", "possessive")}
    forms.discard("")
    for paradigm in _THIRD_PERSON_SETS:
        if str(pronouns.get("subject") or "").strip().casefold() in paradigm:
            forms |= paradigm
    return frozenset(forms)


def _verbs_in_base(act):
    """A predicate written as a watcher sees it -- third person, its subject
    left out ("takes the letter and tucks it into the pocket") -- with every
    verb of its own doer's coordinated verb phrases in the base form ("take
    the letter and tuck it into the pocket"), or "" where that cannot be done
    exactly. ONE RULE for every frame that puts a predicate after its doer in
    the base form: the mind's own attempt ("I tried to ...", `own_attempt`)
    and the act it watched ("I saw Rhona Carrick ...", `_episode_sentence`).

    Read only from the closed classes the engine owns: the first word is the
    verb (a third-person form is turned to its base; a base form stays where
    its object follows it; a body noun or an auxiliary there is not turned);
    only the first sentence is the predicate's; a later third-person form
    opens a verb phrase of the same doer where a coordinator, a sequencer or
    a comma stands before it -- never inside a clause a subordinating or
    relative word, or a dash, opened for its own subject -- and is turned
    where its object follows it, or a coordinator stands before it with a
    word of its phrase after it or with the end of a verb phrase before the
    coordinator (the doer's own verb, an object pronoun, a particle: "held
    out and waits"); a body noun, a list of the body's parts, a plural ending
    a list and an absolute phrase's head are left as nouns, and anything
    uncertain is not turned at all. Quoted spans stay as said.
    """
    from language_runtime import referring
    act = str(act or "").strip().rstrip(".").strip()
    if not act or referring.unspaced(act):
        return ""
    breath = {str(w).casefold()
              for w in linguistic("agents.common", "_BREATH_CONJUNCTIONS")}
    body = {str(w).casefold()
            for w in linguistic("agents.common", "_OWN_BODY_NOUNS")}
    agreement = linguistic("agents.common", "_YOU_AGREEMENT")
    quoted = linguistic("agents.common", "_QUOTED_SPAN_RE")
    # ONLY THE FIRST SENTENCE IS THE ATTEMPT'S. "I tried to" governs the
    # sentence it opens; a later one stands as the act wrote it -- the owner's
    # bank, row 22342: "Lowers to one knee before the table. Takes Hinami's
    # nearest foot ... Lifts it slightly and presses", whose later sentences
    # open with their own verbs. Sentences by the engine's own splitter (a
    # title's period is not a full stop), over the text with its quotations
    # masked so a quoted full stop ends nothing.
    from .common import split_sentences
    masked = quoted.sub(lambda m: "x" * len(m.group(0)), act)
    parts = split_sentences(masked)
    cut = len(act)
    if len(parts) > 1 and parts[1]:
        cut = masked.find(parts[1], max(0, len(parts[0]) - 1))
        cut = len(act) if cut < 0 else cut
    act, rest = act[:cut], act[cut:]
    segments = quoted.split(act)
    if not segments[0].strip():
        return ""                       # opens with a quotation: no verb first
    # The words that end a verb phrase and never a noun phrase, before a
    # coordinator: a particle or a preposition the engine owns (a preposition
    # needs its object, so one standing before "and" is a particle) -- the
    # pack's phrase openers and the prepositions of `_OBJECT_PRONOUN_FOLLOWERS`,
    # less the subordinating words and the participles among them: a
    # participle ends a phrase inside a noun's as readily ("a man sitting and
    # others standing").
    particles = {
        w for w in set(referring.phrase_openers()) | _OBJECT_PRONOUN_FOLLOWERS
        if w not in breath and not _participle(w)}
    first, foreign, subordinate = True, False, False
    for s in range(0, len(segments), 2):
        tokens = re.split(r"(\s+|[,;—–])", segments[s])
        at = [k for k, t in enumerate(tokens) if t and not t.isspace()]
        words = [tokens[k] for k in at]
        verbs = set()                   # where the doer's own verbs stand
        for i, word in enumerate(words):
            if not _WORD_TOKEN.fullmatch(word):
                continue
            if first:
                first = False
                if word.casefold() in agreement:
                    return ""
                if word.casefold() in body and not _opens_an_object(
                        words, i, reach=1):
                    return ""           # a clause's subject: "hips lock forward"
                base = _base_from_third_person_s(word)
                if base is not None:
                    tokens[at[i]] = base
                elif not _opens_an_object(words, i):
                    return ""
                verbs.add(i)
                continue
            base = _base_from_third_person_s(word)
            low = word.casefold()
            prior = words[i - 1].casefold() if i else ""
            joins = referring.coordinator(low) or low in _SEQUENCERS
            if prior in (",", ";", "—", "–"):
                subordinate = False             # a clause stop ends one
            if prior in (";", "—", "–"):
                # A SPAN AFTER A DASH OR A SEMICOLON that opens with no verb of
                # the doer's is a clause of its own subject -- "intensify the
                # rhythm -- tongue presses deeper ..., then withdraws" (the
                # owner's bank, row 23519): "withdraws" is the tongue's.
                foreign = not ((base is not None and word[:1].islower())
                               or joins)
            if low in breath and not joins:
                # A SUBORDINATING OR RELATIVE WORD opens a clause of its own
                # subject that runs to the next stop: "as my own release breaks
                # and soaks through" (the owner's bank, row 28256), "before
                # things get warm" (row 25673), "all that lies between them" --
                # none of its verbs is the doer's.
                subordinate = True
                continue
            if base is None or not word[:1].islower() or subordinate:
                continue
            after_breath = referring.coordinator(prior) or prior in _SEQUENCERS
            after_stop = prior in (",", ";", "—", "–")
            if not (after_breath or after_stop):
                continue
            if low in agreement:
                return ""
            if low in body:
                # A BODY NOUN IS A VERB ONLY WITH ITS OBJECT STRAIGHT AFTER IT
                # ("eyes the door"): a phrase after it follows a noun as
                # readily -- "draw her torso and shoulders into the passage".
                nxt = words[i + 1].casefold() if i + 1 < len(words) else ""
                if _opens_an_object(words, i, reach=1):
                    tokens[at[i]] = base
                    verbs.add(i)
                elif nxt in referring.phrase_openers():
                    return ""
                continue                        # a noun: "hands and knees"
            if foreign:
                return ""                       # whose verb, nobody can say
            if (referring.coordinator(prior) and i >= 2
                    and words[i - 2].casefold() in body
                    and not _opens_an_object(words, i, reach=1)):
                # A LIST OF THE BODY'S PARTS: after "feet and", "calves
                # against the folds" is one more part (the owner's bank, row
                # 26690, filed "feet and calve").
                continue
            if _opens_an_object(words, i):
                tokens[at[i]] = base
                verbs.add(i)
            elif after_breath:
                # A verb by its place and form -- but after "and"/"or" only
                # with a word of its own phrase after it, or where what stands
                # before the coordinator ends a VERB phrase: a plural noun ends
                # its own coordination as readily ("brushing grit from coat
                # and trousers.", "gauges and keys,", the owner's bank rows
                # 27836 and 28637), where a verb before a stop is intransitive.
                # What stands before "and" settles it: the doer's own verb
                # ("pause and sighs."), an object pronoun ("turns to her and
                # waits"), or a particle ("keeps the letter held out and
                # waits.", the lighthouse probe, chat 2 row 40); a noun there
                # ("cheeks and ears", "corners and shadows") leaves it a noun.
                # After a sequencer ("then", "but") a noun phrase is not
                # coordinated, so the verb stands there whatever follows it.
                nxt = words[i + 1] if i + 1 < len(words) else ""
                left = words[i - 2] if i >= 2 else ""
                ends_a_verb = (i - 2 in verbs
                               or left.casefold() in _OBJECT_PRONOUNS
                               or left.casefold() in particles)
                if referring.coordinator(prior) and not ends_a_verb and (
                        not _WORD_TOKEN.fullmatch(nxt) or _participle(nxt)):
                    return ""
                tokens[at[i]] = base
                verbs.add(i)
            elif i + 1 < len(words) and _participle(words[i + 1]):
                continue                        # an absolute phrase's head
            else:
                return ""
        segments[s] = "".join(tokens)
    return "".join(segments) + rest


def own_attempt(act, *, self_forms=(), pronouns=None, pronouns_mine=False,
                keep_pronouns=False):
    """A mind's own act, written as a watcher sees it ("takes the letter and
    tucks it into his pocket"), as the predicate of its own attempt in its own
    first person ("take the letter and tuck it into my pocket") -- or "" where
    the turn cannot be made exactly, and the caller keeps the act as written.

    A MIND'S OWN ACT IS REMEMBERED IN ITS OWN FIRST PERSON, AS ITS ATTEMPT,
    WITH GRAMMAR THAT HOLDS. The memory files what the mind TRIED beside what
    it perceived come of it (`commit_memory._own_sequence_memory`); the bare
    contract's act written as a watcher sees it was filed with the doer's own
    name and as done -- "Pell Hardacre takes the sealed letter from Rhona
    Carrick's hand and tucks it into the inside pocket of the oilskin
    jacket." -- when the world had refused the take (the lighthouse probe,
    2026-10-20, chat 2 row 40), and two story days later his memory of the
    skip believed he had pocketed it.

    Turned exactly or not at all, and read only from the closed classes the
    engine owns: the act's first word is its verb (a third-person form is
    turned to its base; a base form stays where its object follows it); a
    later third-person form opens a verb phrase of the same doer where a
    coordinator, a sequencer or a comma stands before it -- never inside a
    clause a subordinating or relative word opened ("as my own release breaks
    and soaks through", "all that lies between them") -- and is turned
    where its object follows it, or where a coordinator stands before it and
    it is not a body noun ("hands and knees"; a body noun is a verb only with
    its object straight after it, "eyes the door"); after a comma it is left
    as the head of an absolute phrase where a participle follows it ("hands
    clasped behind back"), and anything else there is not turned at all; a
    span after a dash or a semicolon that opens with no verb of the doer's is
    a clause of its own subject ("-- tongue presses deeper, then withdraws"),
    and a verb phrase in it is not the doer's to turn. The
    doer's own pronouns turn with the doer, and only where nobody else
    present could be meant by them (`pronouns_mine`, the caller's reading of
    the scene): two women in one room, and "slides both hands from her inner
    thighs" is the other woman's. Where they cannot turn, the act is not
    turned -- unless `keep_pronouns`, for a line that already stood in the
    first person with them as written ("I tried to shift her posture"), which
    keeps them so and turns the rest. Quoted spans are what was said and stay.
    """
    text = _verbs_in_base(act)
    if not text:
        return ""
    # The doer's own pronouns, and nobody else's.
    def _seen(t):
        outside = " ".join(
            linguistic("agents.common", "_QUOTED_SPAN_RE").split(t)[0::2])
        return {w.casefold() for w in _WORD_TOKEN.findall(outside)}

    seen = _seen(text)
    own = _pronoun_forms(pronouns)
    unsure = (bool(seen & own) if own
              else any(seen & paradigm for paradigm in _THIRD_PERSON_SETS))
    if unsure and own and pronouns_mine and "they" not in own:
        turned = _pose_owner_second_person(text, pronouns, (), person="first")
        if not _seen(turned) & own:             # none left unturned ("hers")
            text, unsure = turned, False
    if unsure and not keep_pronouns:
        return ""                               # whose, nobody can say
    if self_forms:
        text = _self_first_person(text, self_forms)
    text = text.strip()
    head = text.split(" ", 1)[0]
    if not (head.isupper() and len(head) > 1):
        text = text[:1].lower() + text[1:]
    return text


def _second_to_first_rules():
    """The active pack's second->first person rewrites, compiled at use time.

    Bound from the English pack at import before, so the Japanese pack's
    あなた→私 rules were authored and dead: a first-person memory came out
    「あなたは立っている。」 sitting next to 「私は中庭にいた。」
    """
    from language_runtime import compositor_value
    return tuple((re.compile(pattern), replacement)
                 for pattern, replacement in compositor_value("second_to_first"))


def _first_person(text):
    """Second person -> first person, outside quoted spans (a quoted 'you'
    is what was said and stays verbatim).

    A MEMORY'S FIRST PERSON FOLLOWS THE WORDS' GRAMMATICAL ROLES. English
    spells the second person's subject and object alike, so the pack's rules
    (`second_to_first`) read the role from what the text itself marks, and
    from nothing else -- no list of verbs or prepositions: a "you" after the
    punctuation that opens a clause is its subject ("Through the walls, I can
    hear ..."), as are the contracted forms and the be row ("you're", "you
    aren't"); every other "you" is an object ("me") -- the first word of the
    text included, because the swap is applied to fragments as well as to
    sentences and a pose's referent alone ("you", the sentence's "astride
    you") is an object, while every rewrite capitalises the "You" that opens
    a sentence. The possessive, independent and reflexive forms keep their
    own. Measured: the rule that made every lowercase "you"
    "me" filed "Through the walls, me can hear the heavy rain, muffled." in
    the lighthouse probe's memories (2026-10-20, chat 2 rows 46 and 50);
    twelve rows across the three probe stories carried such a "me".

    What the text cannot mark -- a subject inside a relative or subordinate
    clause -- is given its first person where the role is known: an engine
    template's own episode wording (`render_distant_sound`, the residue's
    `pain_episode`), or the first person an authored line was rewritten into
    beside its second person (`_said_as_mine`). Japanese marks the role with
    a particle, so its rules map the pronoun alone."""
    segments = linguistic(
        "agents.common", "_QUOTED_SPAN_RE").split(str(text or ""))
    rules = _second_to_first_rules()
    for i in range(0, len(segments), 2):
        seg = segments[i]
        for pattern, replacement in rules:
            seg = pattern.sub(replacement, seg)
        segments[i] = seg
    return "".join(segments)
