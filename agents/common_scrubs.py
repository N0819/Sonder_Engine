"""Prose repair passes: the repeated-quote cap, dangling-speech healing, the
player-echo strip, the invented-dialogue scrub and within-view sentence
dedupe.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re

from language_runtime import UNSPACED_SCRIPT

from agents.common_base import _dangling_speech, _ling, _quote_body
from agents.common_names import _countable_word_units


def _cap_repeated_quotes(prose, view, exclude_bodies=()):
    """Cap each spoken line's occurrences in the prose at how many times it
    actually appears in the authoritative source (the view). (Fable A1 / backlog
    P3.) `_dedupe_view_sentences` deliberately exempts quotes so an intentional
    repeat survives, which let a line the narrator both SUMMARIZED and quoted
    verbatim render twice (impostor t9: the last-stand speech; t5: Lady Thorne's
    kitchen-door line, verbatim, twice). A quote appearing more often than the
    source authorized is an artifact; drop the surplus occurrences, keep the
    first. The player's own lines are handled by the echo strip and excluded.
    """
    if not prose:
        return prose
    excluded = {re.sub(r"\s+", " ", str(b).casefold()) for b in (exclude_bodies or [])}
    quote_re = _ling("_QUOTE_SPAN_RE")
    source_text = re.sub(r"\s+", " ", str(view or "").casefold())
    # Source count per body: how many times the view presents that exact line.
    source_counts = {}
    for m in quote_re.finditer(str(view or "")):
        body = re.sub(r"\s+", " ", m.group(2).strip().casefold())
        if body:
            source_counts[body] = source_counts.get(body, 0) + 1

    seen = {}
    out_parts = []
    last = 0
    for m in quote_re.finditer(prose):
        body = re.sub(r"\s+", " ", m.group(2).strip().casefold())
        if not body or body in excluded:
            continue
        cap = source_counts.get(body, 1)
        seen[body] = seen.get(body, 0) + 1
        if seen[body] > cap:
            # Surplus occurrence: excise this quoted span (keep the text
            # around it; the dangling-verb heal below tidies "he says ,").
            out_parts.append(prose[last:m.start()])
            last = m.end()
    if not out_parts:
        return prose
    out_parts.append(prose[last:])
    result = "".join(out_parts)
    result = _dangling_speech("verb").sub(_heal_dangling_verb, result)
    result = _dangling_speech("colon").sub(_heal_dangling_colon, result)
    result = _collapse_empty_quote_debris(result)
    return re.sub(r"\s{2,}", " ", result).strip()

# A speech verb left dangling by the echo strip ("you say.", "I ask,") is healed
# to "<verb> it." The lookahead is SENTENCE-end only ([.!?] or end of string):
# a verb followed by a comma that CONTINUES the sentence ("he says, quiet and
# gentle, 'Ellie'") is a normal attribution around a quote that survived, not a
# dangling verb -- healing it produced "he says it., quiet and gentle," in live
# NPC dialogue whenever the same beat also stripped a player echo (v4).


# ONE vocabulary, shared with the colon healer below -- by construction, not by
# discipline. Two independent literals drifted twice: the colon healer knew
# `add`, `speak`, `voice`, `continue` and `offer` and the verb healer did not,
# so a quote stripped after "as you add," left the fragment "You let the wry
# amusement show as you add," standing on the page with nothing after it (live,
# chat 72); and later the verb healer alone gained `call` and `shout`. Both now
# read `_SPEECH_CUE` through `_dangling_speech` (defined at the top of this
# file), so a pack states what counts as speech ONCE and neither healer can
# hold a vocabulary the other does not.


def _heal_dangling_verb(match):
    """Give a stranded speech verb its object back, in the shape it landed in.

    `it` is deliberately vague: the line itself is what the player already
    knows and what this function exists to keep off the page, so the
    replacement must refer to the utterance without reproducing it.
    """
    heal = _ling("_DANGLING_SPEECH")
    verb = match.group(1)
    if match.group("cont"):
        # A capital straight after the comma means the cut left two sentences
        # welded by it ("I say,  He tells Karen the truth"), so close the
        # first rather than running them together with an object between.
        rest = match.string[match.end():].lstrip()
        if rest[:1].isupper():
            return heal["heal_stop"].format(verb=verb)
        # attribution mid-sentence: keep going
        return heal["heal_cont"].format(verb=verb)
    if match.group("end"):
        # consume the punctuation the wound left; never double it
        return heal["heal_end"].format(verb=verb, end=match.group("end"))
    return heal["heal_stop"].format(verb=verb)   # end of paragraph or prose


# `, ,` and `,,` left where a quote sat between an attribution and its
# continuation. The empty-quote collapser handles the quote marks; nothing
# handled the punctuation on either side of them.
_DOUBLED_COMMA_RE = re.compile(r",(?:[^\S\n]*,)+")

# A quote can also be introduced by an attributive CLAUSE ending in a colon
# ("...and when I speak again it's quieter, almost gentle:"). Stripping the
# player's echoed quote leaves the colon dangling against the next sentence
# (live: v3 t7 "...almost gentle: Vorne swallows once..."). Drop the orphaned
# lead-in back to the preceding clause/sentence boundary -- but only a clause
# that actually carries a speech cue, so a legitimate non-speech colon (a
# list, a ratio, a time) is never eaten. The colon match also consumes an
# orphaned period the strip may have left ("gentle: .").
# The lead-in TEXT is kept -- only the dangling colon (and any orphaned period
# the strip left) is converted to a full stop, so nothing legitimate can be
# eaten. Requiring a speech cue in the same clause keeps this off a real
# non-speech colon (a list, a ratio, a time). `[^.!?:]*` cannot cross a
# sentence boundary, so the cue and the colon are always in one clause.


def _heal_dangling_colon(m):
    return _ling("_DANGLING_SPEECH")["heal_colon"].format(lead=m.group(1))

def _protected_view_quotes(view, player_lines=None):
    """Quoted spans in a perceiver's view that belong to a NON-player speaker
    -- the exact lines DIALOGUE FIDELITY requires the narrator to keep
    verbatim. Excludes the player's own declared lines (those are the ones
    the echo strip is meant to remove). Fed to _strip_player_echo so it never
    corrupts a legitimately-quoted NPC line while stripping a player echo."""
    excluded = {
        re.sub(r"\s+", " ", _quote_body(line).casefold())
        for line in (player_lines or [])
        if _quote_body(line)
    }
    quotes = []
    for match in _ling("_VIEW_QUOTE_BODY_RE").finditer(str(view or "")):
        body = _quote_body(match.group(1))
        if not body:
            continue
        if re.sub(r"\s+", " ", body.casefold()) in excluded:
            continue
        quotes.append(body)
    return quotes

# Punctuation and case are not variation. `_strip_player_echo` matched the
# player's declared line as a literal substring, and a narrator that lightly
# TIDIES what the player typed defeats that completely: declared
# `Anyways your plan doctor?` was rendered `"Anyways, your plan, Doctor?"` --
# two inserted commas and a capitalised Doctor -- and sailed through the guard
# into the page as an unattributed quote (chat 72, turn 35). Correcting the
# player's grammar is the one thing a narrator reliably does, so the guard's
# failure rate was proportional to how well the narrator wrote.
_ECHO_FOLD_RE = re.compile(r"[^\w\s]+")


def _length_in_units(text):
    """How long a span is, in the unit its script is measured in: words by
    whitespace in a spaced script -- exactly the `.split()` count these
    floors always took -- and, for text holding an unspaced script, the A2
    unit (`_countable_word_units`, one per character), which every other
    "long enough to be an utterance" floor in these files already uses.
    `.split()` measured any Japanese line as ONE word, so both floors read
    every Japanese span as too short to act on (agents_common audit F14)."""
    body = str(text or "")
    if UNSPACED_SCRIPT.search(body):
        return _countable_word_units(body)
    return len(body.split())


def _echo_fold(text):
    """One spoken line, folded so only its WORDS remain."""
    return " ".join(_ECHO_FOLD_RE.sub(" ", str(text or "")).casefold().split())


# Below this, a folded match is not evidence of an echo -- "no", "wait", "why"
# recur in anyone's mouth, and the literal pass above already handles a short
# line that arrived unedited.
_ECHO_FOLD_MIN_WORDS = 3


def _strip_player_echo(prose, lines, protect_quotes=None):
    if not prose:
        return prose
    # DIALOGUE FIDELITY vs PLAYER ECHO: the echo strip removes the player's
    # OWN declared lines from prose, but it must never reach inside a span the
    # narrator legitimately quoted from a NON-player speaker (an NPC line the
    # fidelity check just required verbatim). When a player line coincides
    # with, or is a substring of, an NPC's quoted line, blind stripping would
    # corrupt that protected quote. Mask the NPC-attributed quoted spans out
    # of reach for the duration of the strip, then restore them intact.
    masks = []
    for quote in (protect_quotes or []):
        body = _quote_body(quote)
        if not body:
            continue
        forms = [o + body + c for o, c in _ling("_QUOTE_PAIRS")]
        if len(body) >= 8:
            forms.append(body)
        for form in forms:
            start = 0
            while True:
                pos = prose.find(form, start)
                if pos == -1:
                    break
                token = "\x00%d\x00" % len(masks)
                masks.append((token, form))
                prose = prose[:pos] + token + prose[pos + len(form):]
                start = pos + len(token)
    for speech in (lines or []):
        body = (speech or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")
        if not body:
            continue
        # Quoted forms are delimited by quote marks, so stripping them is
        # safe at any length. The bare (unquoted) form is only stripped for
        # longer lines, since a short bare substring (e.g. "no") risks
        # corrupting unrelated words ("know", "not"). Without this split,
        # short player lines (e.g. "Stop!", "Wait!") were never stripped at
        # all and echoed verbatim in narrator prose.
        quoted_forms = tuple(o + body + c for o, c in _ling("_QUOTE_PAIRS"))
        matched = any(q in prose for q in quoted_forms)
        if len(body) >= 8 and body in prose:
            matched = True
        if not matched:
            # The narrator tidied it. Fall back to a WORDS-ONLY comparison
            # against each quoted span still in reach -- NPC quotes were
            # masked out above, so anything left is fair game -- and drop the
            # span whose words are the player's, whatever punctuation and
            # capitalisation the narrator gave them.
            folded = _echo_fold(body)
            if _length_in_units(folded) < _ECHO_FOLD_MIN_WORDS:
                continue
            hit = next((m for m in _ling("_QUOTE_SPAN_RE").finditer(prose)
                        if _echo_fold(m.group(2)) == folded), None)
            if hit is None:
                continue
            prose = prose[:hit.start()] + prose[hit.end():]
            prose = _dangling_speech("verb").sub(
                _heal_dangling_verb, prose)
            prose = _dangling_speech("colon").sub(_heal_dangling_colon, prose)
            continue
        for quoted in quoted_forms:
            prose = prose.replace(quoted, "")
        if len(body) >= 8:
            prose = prose.replace(body, "")
        # Stripping the quote can leave a dangling speech verb ("you say,",
        # "I ask,", "Alex says.") with nothing after it -- the subject varies
        # with narration_person (first/second/third), so match on the verb
        # rather than assuming "you".
        prose = _dangling_speech("verb").sub(_heal_dangling_verb, prose)
        prose = _dangling_speech("colon").sub(_heal_dangling_colon, prose)
    for token, form in masks:
        prose = prose.replace(token, form)
    prose = _collapse_empty_quote_debris(prose)
    # HORIZONTAL WHITESPACE ONLY. This was `\s{2,}` -> " ", which cleans the
    # double space a removed quote leaves behind and ALSO ate every paragraph
    # break in the story, because `\s` is newlines too.
    #
    # That is the whole reason narrator prose was arriving unbroken. Three
    # contracts were built and measured against a model that was often doing
    # its part -- the blank-line instruction's 1% and the marker contract's
    # live `paragraph_count` of 3, 4, 8, 10 both passed through here and came
    # out flat. The engine was deleting the breaks after the model wrote them.
    prose = re.sub(r"[^\S\n]{2,}", " ", prose)      # the spacing debris
    prose = re.sub(r"[^\S\n]*\n[^\S\n]*", "\n", prose)  # tidy around breaks
    prose = re.sub(r"\n{3,}", "\n\n", prose)        # never a blank run
    # A quote removed from between an attribution and its continuation leaves
    # the punctuation from BOTH sides ("You ask,, quietly"). The empty-quote
    # collapser above takes the marks; this takes the commas they sat between.
    prose = _DOUBLED_COMMA_RE.sub(",", prose)
    prose = re.sub(r"[^\S\n]+([,.!?])", r"\1", prose)   # " ," -> ","
    # A paragraph that BEGAN with the player's quote now begins with the
    # attribution that followed it, in lower case ("you ask it, your voice
    # clear..."). Nothing else in this function can see that a sentence lost
    # its head. Restoring the capital is safe here because narrator prose is
    # ordinary English paragraphs -- and it is the last visible trace of the
    # cut, so leaving it is leaving the seam on the page.
    prose = prose.strip()
    prose = re.sub(r"(\A|\n)([^\S\n]*)([a-z])",
                   lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
                   prose)
    return prose


# An empty quote pair -- '' "" “” -- left where a stripped player line used to
# sit (Fable review, DW t12: "I can't hold her eyes. ''"). Collapse the orphan
# and heal the punctuation/space it leaves. Only a genuinely EMPTY pair is
# touched, so real quoted dialogue is never harmed.
#
# EMPTY MEANS ZERO CHARACTERS BETWEEN THE MARKS. `_EMPTY_QUOTE_RE` also carried
# `"\s*"` and `'\s*'`, which read any two quote marks separated only by
# whitespace as an empty pair -- and `\s` is a newline, so the alternative
# spanned a paragraph break. One speaker's close-quote and the next speaker's
# open-quote are exactly that shape once `narration._substitute_dialogue_tokens`
# has wrapped each delivered line in its own quotes, and `_strip_player_echo`
# above calls this unconditionally, so no player line and no strip were needed
# to trigger it: the two marks went, and two speakers were welded into a single
# quoted string attributed to one voice while the reply was narrated again as if
# unspoken (15-beat trace, model output `{{L2}}</p><p>{{L3}}` correct, the
# dialogue_log record correct, only the rendered page wrong).
#
# Nothing in the engine can leave a whitespace-separated pair for this to
# collapse. Both removal paths in `_strip_player_echo` -- the literal
# `_QUOTE_PAIRS` form and the `_QUOTE_SPAN_RE` span -- delete the whole
# delimited span INCLUDING its marks, and so does `_cap_repeated_quotes`. A
# pair with anything at all between the marks is dialogue, not debris.


def _collapse_empty_quote_debris(prose):
    if not prose:
        return prose
    out = _ling("_EMPTY_QUOTE_RE").sub(" ", prose)
    # A lead-in left dangling against the removed quote ("She said, .", "then, .")
    out = re.sub(r"[,:]\s*\.", ".", out)
    out = re.sub(r"\s+([.,!?;])", r"\1", out)
    return out

_YOU_RE = re.compile(r"\byou\b|\byour\b", re.I)


def _scrub_invented_dialogue(view, spoken_bodies, *, cast_names=(), mode="all"):
    """DIALOGUE-FIDELITY FLOOR at the perception layer: drop any quoted line
    of a perceiver view that is presented as SPEECH but whose body is not in
    the set of lines actually spoken this beat (declared player/character
    speech + dialogue_log). The perception LLM sometimes invents a fresh
    utterance -- often a memory/backstory callback rendered as if freshly
    spoken (live t42: a fabricated player line about "trapped under the
    rubble" injected into Dr. Moon's view) -- which then propagates into
    other minds' character context and durable memory. No stage may author
    words a speaker did not say.

    Kept untouched:
    - any quote whose body matches a spoken line GENEROUSLY (case/whitespace
      normalized; substring either direction, so a distant perceiver's
      legitimate muffled FRAGMENT of a real line survives; an ellipsis-split
      quote survives when every fragment is verbatim from one spoken line);
    - environmental quoted text (mode="all"): signage, labels, screens --
      recognized by the ABSENCE of a speech-attribution cue around the quote
      ("reads"/"is painted" are not speech verbs);
    - quotes with no player attribution (mode="player": only a quote whose
      nearest speaker cue is 'you'/'your' is in scope -- the original
      player-view-only scrub semantics).

    Removal is clause surgery: the quote plus its immediate attribution
    clause (before it, and after it for a trailing '"...," she says.'),
    never the surrounding prose. Returns (scrubbed_view, dropped)."""
    if not view:
        return view, []
    legit = []
    for b in spoken_bodies:
        nb = re.sub(r"\s+", " ", (_quote_body(b) or "")).casefold().strip()
        if nb:
            legit.append(nb)

    def _matches_spoken(raw_body):
        body = re.sub(r"\s+", " ", (_quote_body(raw_body) or "")).casefold().strip()
        if not body or not re.search(r"\w", body):
            return True  # empty / pure punctuation: nothing was authored
        if any(body == L or body in L or L in body for L in legit):
            return True
        core = body.strip(" .…—–-")
        if core and any(core in L for L in legit):
            return True
        # Muffled/partial rendering: an ellipsis-chunked quote is legitimate
        # when EVERY chunk is a verbatim piece of some actually-spoken line.
        chunks = []
        for c in re.split(r"\.{2,}|…", body):
            c = c.strip(" ,;:—–-.!?")
            for prefix in _ling("_PARTIAL_QUOTE_PREFIXES"):
                if c.startswith(prefix):
                    c = c[len(prefix):]
                    break
            if len(c) >= 3:
                chunks.append(c)
        return bool(chunks) and all(any(c in L for L in legit) for c in chunks)

    name_re = re.compile(
        "|".join(r"\b" + re.escape(str(n).lower()) + r"\b" for n in cast_names if n),
        re.I) if cast_names else None

    # Quoted spans (a body may itself contain '...'/'!' -- so we cannot split
    # into sentences first; we work over the whole view). Clause boundaries are
    # sentence terminators OUTSIDE any quote, plus the END of each quoted span
    # (a new clause almost always begins after a quoted line).
    quote_spans = [(m.start(), m.end(), m.group(1))
                   for m in _ling("_VIEW_QUOTE_BODY_RE").finditer(view)]
    boundaries = {0}
    inside = False
    # Read once, not once per character of the view (agents_common audit,
    # Efficiency 2: ~3 ms per 3,000-character view, per observer, per pass).
    quote_chars = _ling("_QUOTE_CHARS")
    for i, ch in enumerate(view):
        if ch in quote_chars:
            inside = not inside
        elif ch in ".!?…" and not inside:
            boundaries.add(i + 1)
    for _s, qe, _b in quote_spans:
        boundaries.add(qe)
    boundaries = sorted(boundaries)
    quote_starts = [qs for qs, _qe, _b in quote_spans]

    def _clause_start(pos):
        b = 0
        for bp in boundaries:
            if bp <= pos:
                b = bp
            else:
                break
        while b < len(view) and view[b] in " \n\t":
            b += 1
        return b

    def _tail_stop(pos):
        # The attribution tail of a quote runs to the next sentence boundary,
        # but never INTO a following quote -- a legit quote after 'she says,
        # and X replies,' must survive the surgery.
        stop = len(view)
        for bp in boundaries:
            if bp > pos:
                stop = bp
                break
        for q2 in quote_starts:
            if pos < q2 < stop:
                stop = q2
                break
        return stop

    removals, dropped = [], []
    for qs, qe, raw_body in quote_spans:
        if _matches_spoken(raw_body):
            continue
        if mode == "player":
            # Original player-view semantics: only a quote whose NEAREST
            # speaker cue before it is the player ('you'/'your', closer than
            # any NPC pronoun/cast name) is in scope.
            prefix = view[:qs]
            you = max((mm.start() for mm in _YOU_RE.finditer(prefix)), default=-1)
            npc = max((mm.start() for mm in _ling("_NPC_PRONOUN_RE").finditer(prefix)), default=-1)
            if name_re:
                npc = max([npc] + [mm.start() for mm in name_re.finditer(prefix)])
            if you < 0 or you <= npc:
                continue
            start, end = _clause_start(qs), qe
        else:
            cstart = _clause_start(qs)
            # Attribution cue for the dialogue-fidelity floor: a speech verb, or a bare
            # voice noun ("A muffled voice: ..."). Deliberately excludes reading verbs
            # (reads, is written/painted/carved, displays) so quoted ENVIRONMENTAL text --
            # signage, labels, screens -- is never mistaken for dialogue.
            pre_attr = bool(_ling("_DIALOGUE_CUE_RE").search(view[cstart:qs]))
            tstop = _tail_stop(qe)
            tail = view[qe:tstop]
            tail_lead = tail.lstrip()
            # A trailing attribution ('"...," she says.') continues the same
            # sentence, so it starts lowercase or with a dash -- an uppercase
            # tail is a NEW sentence and out of scope.
            tail_attr = bool(tail_lead) and (
                tail_lead[0].islower() or tail_lead[0] in ",—–-") \
                and bool(_ling("_DIALOGUE_CUE_RE").search(tail))
            if not pre_attr and not tail_attr:
                continue  # no speech attribution: environmental text (signage)
            start = cstart if pre_attr else qs
            end = tstop if tail_attr else qe
        while end < len(view) and view[end] in " \n\t":
            end += 1
        removals.append((start, end))
        dropped.append(view[start:qe].strip())

    if not removals:
        return view, []
    out = view
    for start, end in sorted(removals, reverse=True):
        out = out[:start] + out[end:]
    return re.sub(r"\s{2,}", " ", out).strip(), dropped


def _scrub_undeclared_player_speech(view, declared_bodies, protected_bodies=(),
                                    cast_names=()):
    """PLAYER-SPEECH AUTHORITY at the perception layer: drop any sentence of the
    PLAYER's own view that quotes a player-attributed line the player did NOT
    declare this beat (live: the turn-39 fragment "The same..." resurfaced as
    "Same... the one who... did this... before." in a later turn's view).
    Thin wrapper over _scrub_invented_dialogue's player mode; NPC lines the
    player legitimately heard ride in as protected_bodies. Returns
    (scrubbed_view, dropped_sentences)."""
    return _scrub_invented_dialogue(
        view, list(declared_bodies) + list(protected_bodies),
        cast_names=cast_names, mode="player")


# Within-view dedupe (W12): the same sentence rendered twice in ONE turn's
# view/prose ("Picard turns his head slightly toward Troi" appearing twice in
# a single beat). Splitting is a plain sentence-boundary regex; a quote whose
# body contains sentence punctuation mis-splits into fragments, but every such
# fragment carries a quote character and is therefore exempt from dropping
# (below), so mis-splits can only UNDER-dedupe, never eat real content.
# One capture group, so a split alternates [sentence, separator, ...]. The
# second alternative is the full-width stop, after which Japanese writes no
# space: without it a Japanese view was one sentence and nothing in it was
# ever a repeat (agents_common audit F14). No English text carries 。！？.
_VIEW_SENTENCE_SPLIT_RE = re.compile(r"((?<=[.!?…])\s+|(?<=[。！？])\s*)")
_VIEW_DEDUPE_MIN_WORDS = 5

_VIEW_MASK = "\x00Q%d\x00"


def _mask_quoted_spans(text):
    """Replace each quoted span with a single opaque token.

    The token carries no whitespace and no terminal punctuation, so a sentence
    splitter cannot cut a quotation into pieces -- which is the whole point.
    Returns (masked_text, spans) for `_unmask_quoted_spans`.
    """
    spans = []

    def _swap(match):
        spans.append(match.group(0))
        return _VIEW_MASK % (len(spans) - 1)

    return _ling("_VIEW_QUOTED_SPAN_RE").sub(_swap, text), spans


def _unmask_quoted_spans(text, spans):
    for i, span in enumerate(spans):
        text = text.replace(_VIEW_MASK % i, span)
    return text


def _dedupe_view_sentences(text):
    """Drop a sentence that repeats an EARLIER sentence of the same text
    verbatim (case/whitespace/terminal-punctuation-insensitive), keeping the
    first occurrence. Deterministic and deliberately conservative:

    - sentences containing quoted dialogue are never dropped -- quotes must
      survive verbatim (dialogue fidelity), and a character repeating a line
      on purpose is legitimate;
    - short sentences (< 5 words) are never dropped -- intentional beats
      ("No. No.") and terse stage directions must survive;
    - only exact normalized repeats go; paraphrase is out of scope.

    QUOTED SPANS ARE MASKED BEFORE SPLITTING, because that first rule was
    defeated by the splitter for years. The check is per-SENTENCE ("does this
    fragment contain a quote character"), and a spoken line containing its own
    terminal punctuation is cut into several fragments -- only the two on the
    ends keep a quote mark, and every fragment between them is judged naked and
    dropped if it echoes anything earlier in the view.

    Live (chat 58, t30). The player answered a direct question with "Seven? I
    think? There might have been more... they began to spread out..." -- four
    terminators, so four fragments. This runs LAST in `perception_act`, after
    the deterministic delivery, and ate the interior of the quotation:

        Hinami says: "Seven? I think? There might have been more... they began
                      to spread out..."
        ->  Hinami says: "Seven? I think? they began to spread out..."

    The character then answered as though the line had never been said, asking
    the question that had just been answered. Perception_act is the view a
    character DECIDES from, so unlike a narrator-side drop this is invisible in
    play -- it surfaces only as a non-sequitur that reads like a model failure.

    Returns the text unchanged (same object) when nothing repeats.
    """
    text = str(text or "")
    if not text.strip():
        return text
    masked, spans = _mask_quoted_spans(text)
    pieces = _VIEW_SENTENCE_SPLIT_RE.split(masked)
    seen = set()
    kept = []
    dropped = False
    # pieces alternates [sentence, separator, sentence, separator, ...];
    # each sentence is kept/dropped together with ITS OWN trailing
    # separator, so removing a duplicate leaves the surrounding
    # whitespace/paragraph structure intact.
    for i in range(0, len(pieces), 2):
        sent = pieces[i]
        sep = pieces[i + 1] if i + 1 < len(pieces) else ""
        key = re.sub(r"\s+", " ", sent).strip().strip(".!?…").casefold()
        droppable = (
            _length_in_units(key) >= _VIEW_DEDUPE_MIN_WORDS
            # A masked span means this sentence carries a quotation. The raw
            # check stays alongside it for an UNTERMINATED quote, which the
            # span regex cannot match and which must still be protected.
            and "\x00" not in sent
            # Double-quote characters only: curly/straight single quotes double as
            # apostrophes in ordinary prose and cannot mark dialogue reliably. The
            # pack names them, because which glyphs open a spoken line is the one
            # thing about dialogue that every language answers differently.
            and not any(qc in sent for qc in _ling("_QUOTE_CHARS"))
        )
        if droppable:
            if key in seen:
                dropped = True
                continue
            seen.add(key)
        kept.append(sent)
        kept.append(sep)
    if not dropped:
        return text
    return _unmask_quoted_spans("".join(kept).rstrip(), spans)
