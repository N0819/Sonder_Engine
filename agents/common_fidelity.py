"""The narrator page against its records: event order, quote attribution,
action attribution, position/portal/attire fidelity, speech marking,
dialogue tokens and _check_narrator_fidelity.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from story.character_schema import (
    _UNSPACED_SCRIPT,
    cue_boundary_pattern,
    name_boundary_pattern,
)
from language_runtime import UNSPACED_SCRIPT, compositor_value
from language_runtime import referring as _referring

from agents.common_base import (
    _contains_quote,
    _fold_typography,
    _ling,
    _quote_body,
    strip_prose_markup,
)
from agents.common_names import (
    _SENTENCE_SPLIT,
    _display_floor,
    _name_token_floor,
    _name_tokens,
    _pronoun_group,
    _pronoun_to_group,
    _unspaced_name_parts,
    split_sentences,
)
from agents.common_narration import (
    _check_narration_person_match,
    _check_narration_tense_match,
    _check_player_person,
    _check_pronoun_fidelity,
    _word_shingles,
)


def _flexible_quote_re(body, flags=re.I):
    """Regex matching a quote body verbatim but whitespace-flexible (the
    narrator may re-wrap lines) and terminal-punctuation-tolerant (English
    convention turns a line's final period into a comma before a trailing
    attribution: '"...," she says')."""
    body = re.sub(r"\s+", " ", str(body or "").strip())
    body = body.rstrip(".,!?…;: ")
    if not body:
        return None
    return re.compile(
        r"(?<!\w)" + r"\s+".join(re.escape(w) for w in body.split(" "))
        + r"(?!\w)", flags)


def _check_action_attribution(prose, observations, player_forms=(),
                              present_labels=()):
    """F7: an ACT the record gives to one body, rendered as another's.

    Measured (scratch play 2026-09-14): chat 9 turn 14 gave Reen's letting
    go of the bell rope to Edith ("Edith let the hemp drop"), and chat 7
    turn 1 gave the captain's line to a footman. Perception's own record
    names the actor of every act it delivered (`observations[*].actor`, the
    label this mind may call them by), so the page can be read against it:
    the sentence that renders an act is the one sharing the most of its
    content words, and the body that sentence puts first is who the page
    says did it.

    Deterministic and conservative, reported and never edited: an act is
    scored only where a sentence shares at least two content words of five
    letters or more with it, the actor's own words excluded, and only where
    that sentence's first-named body is a DIFFERENT present body. A sentence
    naming nobody, or naming the actor first, is not a finding.
    """
    if not prose or not observations:
        return []
    text = strip_prose_markup(str(prose))
    text = _ling("_QUOTED_SPAN_RE").sub(" ", text)
    sentences = [x.strip() for x in _SENTENCE_SPLIT.split(text) if x.strip()]
    if not sentences:
        return []

    def _words(value):
        return {w for w in re.findall(r"[a-z]{5,}", str(value or "").casefold())}

    forms = {}
    for label in present_labels or ():
        label = str(label or "").strip()
        if label:
            forms[label] = [label] + [w for w in label.split() if len(w) > 2]
    you = [str(f) for f in (player_forms or ()) if str(f or "").strip()]

    def _first_body(sentence):
        low = sentence.casefold()
        best, at = None, None
        for who, spellings in list(forms.items()) + ([("__player__", you)] if you else []):
            for form in spellings:
                m = re.search(r"(?<!\w)%s(?!\w)" % re.escape(form.casefold()), low)
                if m and (at is None or m.start() < at):
                    best, at = who, m.start()
        return best

    warnings = []
    for obs in observations:
        if not isinstance(obs, dict) or obs.get("kind") not in ("act", "action"):
            continue
        actor = str(obs.get("actor") or "").strip()
        if not actor or actor not in forms:
            continue
        act = str((obs.get("observed") or {}).get("text") or "")
        want = _words(act) - _words(actor)
        if len(want) < 2:
            continue
        scored = sorted(((len(want & _words(sent)), i) for i, sent in enumerate(sentences)),
                        reverse=True)
        overlap, index = scored[0]
        if overlap < 2:
            continue
        first = _first_body(sentences[index])
        if first is None or first == actor:
            continue
        who = "the player" if first == "__player__" else first
        warnings.append(
            f"Action attributed to {who} where perception's record has "
            f"{actor} doing it (\"{act[:60]}\"): \"{sentences[index][:80]}\"")
    return warnings


def quoted_lines(text):
    """`[(start, body)]` for every quoted span of `text` that counts as a
    LINE (`_QUOTE_BODY_RE`), with every quoted span PAIRED FIRST.

    `_QUOTE_BODY_RE` carries the pack's floor for a line inside its own
    pattern (four characters in English, two in Japanese), so a shorter line
    never matched -- and the two marks it skipped did not disappear, they
    paired with their neighbours, so every span after a short line was the
    narration BETWEEN two lines (`docs/UNBUILT_PERCEPTION.md` 1.109).
    Measured, scratch story 166 turn 4614: Abel's "No." opened the view, so
    the narrator was handed no `dialogue_lines` at all (every span it was
    offered was an attribution, and `_reads_as_attribution` dropped each),
    and the fidelity check reported his four real lines missing and four
    stretches of narration as invented dialogue -- seven warnings, none true.

    So every span is paired by its marks (`_VIEW_QUOTE_BODY_RE`, any
    length) and the floor is asked of each paired span afterwards: a short
    line is still not scored, and no longer takes the next one with it."""
    scored = _ling("_QUOTE_BODY_RE")
    out = []
    for span in _ling("_VIEW_QUOTE_BODY_RE").finditer(str(text or "")):
        line = scored.fullmatch(span.group(0))
        if line is None:
            continue
        out.append((span.start(),
                    next((g for g in line.groups() if g is not None), "")))
    return out


def _check_event_order(prose, event_order):
    """F1 (A1 ordering half): a quoted line must not render before the event
    it answers. event_order is the pipeline's own numbered causal record of
    this beat (player declaration first, then reaction/interaction rounds in
    call order, then parallel character declarations, then background
    reactions -- see agents/narration.py's _ordered_beat_events).

    Deterministic and conservative: only events whose quote appears VERBATIM
    in the prose are scored (DIALOGUE FIDELITY guarantees NPC lines do; the
    player's own echo-stripped lines simply won't match and are skipped), and
    only a strict position inversion between two located quotes fires."""
    if not prose or not event_order:
        return []
    quote_spans = []
    for at, body in quoted_lines(strip_prose_markup(prose)):
        span = re.sub(r"\s+", " ", body.strip())
        if span:
            quote_spans.append((at, span))

    located = []
    for ev in event_order:
        if not isinstance(ev, dict) or ev.get("kind") != "speech":
            continue
        body = re.sub(
            r"\s+", " ", _quote_body(str(ev.get("quote") or "")).strip())
        normalized = _fold_typography(body).casefold().rstrip(".,!?…;:")
        if len(normalized) < 3:
            continue
        # Locate a line only as a whole quoted span or a sentence-bounded line
        # region inside one. A plain substring search reads the player's short
        # ``More?`` as present inside an NPC's later ``More of that.``, then
        # reports the perfectly ordered answer as an inversion and spends
        # narrator rewrites trying to fix it. `_spoken_line_regions` retains
        # legitimate same-mouth multi-line spans without reviving that prefix
        # collision.
        at = None
        for start, span in quote_spans:
            if (_fold_typography(span).casefold().rstrip(".,!?…;:")
                    == normalized):
                at = start
                break
            regions = _spoken_line_regions(body, span)
            if regions:
                at = start + regions[0][0]
                break
        if at is not None:
            located.append((at, ev))
    warnings = []
    for (pos_a, ev_a), (pos_b, ev_b) in zip(located, located[1:]):
        if pos_b < pos_a:
            warnings.append(
                "Dialogue rendered out of order: "
                f"{ev_b.get('actor')}'s line "
                f"\"{_quote_body(ev_b.get('quote'))[:60]}\" appears in the "
                "prose BEFORE the earlier event it follows/answers "
                f"({ev_a.get('actor')}: "
                f"\"{_quote_body(ev_a.get('quote'))[:60]}\"). Render events "
                "in event_order's numbered order."
            )
    return warnings


def _check_action_direction(prose, event_order):
    """CUT 2026-09-15: returns nothing, and is kept only because
    `_check_narrator_fidelity` and a pinned test still name it.

    It compared the direction an act in `event_order` named (lowering,
    raising) with the direction words in the narrator's prose, and reported
    REVERSED and MISSING findings. Measured before it was cut: 19 stored
    REVERSED findings over the corpus and every one false (it bound no
    subject, read no negation and allowed no sequence -- "fox ears fold
    downward" against "a tail lifts"), then 4 fires in 167 scratch turns,
    the ones read all false ("You descend the ladder" against prose that
    took the rungs "down through the hatch" and raised a lantern). The rule
    lives on in `perception._inverted_motion_check`.

    Its pack keys, `agents.common._NARR_LOWERING` / `_NARR_RAISING`, are now
    read by no engine module (agents_common audit F19, 2026-11-01).
    """
    return []


def _actor_reference_patterns(display):
    """Compiled patterns that count as a prose reference to one actor.

    A canonical proper name yields one case-sensitive pattern per usable name
    token (surname or first name alone is a normal reference). A descriptor
    label ('the unfamiliar woman', 'a woman in a gray uniform') yields one
    case-insensitive pattern for its content phrase minus the article."""
    display = str(display or "").strip()
    if not display:
        return []
    head = display.split()[0]
    # The pack's own article list -- the same one the compositor uses when it
    # BUILDS a descriptor label. A language with no articles supplies an empty
    # list and the leading-article branch simply never fires.
    articles = [str(a).lower() for a in (compositor_value("articles") or [])]
    article_re = ("^(?:%s)\\s+" % "|".join(re.escape(a) for a in articles)
                  if articles else None)
    proper = display[:1].isupper() or bool(_UNSPACED_SCRIPT.match(display[:1]))
    if head.lower() in articles or not proper:
        phrase = display
        if article_re:
            phrase = re.sub(article_re, "", phrase, flags=re.I)
        phrase = phrase.strip()
        if len(phrase) < _display_floor(phrase):
            return []
        return [re.compile(cue_boundary_pattern(
            r"\s+".join(re.escape(w) for w in phrase.split())), re.I)]
    pats = []
    for tok in _name_tokens(display):
        if len(tok) < _name_token_floor(tok):
            continue
        if not _UNSPACED_SCRIPT.match(tok[:1]) and not tok[:1].isupper():
            continue
        if tok.lower() in _ling("_AMBIGUOUS_NAME_WORDS"):
            continue
        pats.append(re.compile(cue_boundary_pattern(
            re.escape(tok) + r"(?:['’]s)?")))
    return pats


#: At or above this many characters a line is taken at FACE VALUE inside a
#: quoted span -- long enough that finding it there is not coincidence. This
#: used to be the only test, which silently exempted every line below it.
_MERGE_FACE_VALUE_CHARS = 15


def _spoken_line_regions(spoken, span):
    """Where this whole spoken line sits inside this one quoted span.

    A long line is matched plainly. A SHORT one is matched only where it
    stands as its own sentence -- bounded at the front by the span's start or
    a sentence ending, and closed by its own terminal punctuation or the end
    of the span.

    The length floor was there for a real reason: a short body can sit inside
    a longer one by coincidence, and this warning's prefix is enforceable, so
    a false positive cost a rewrite when this was written and costs a false
    record on the step now (E12; nothing rewrites since 2026-09-06). But a
    floor alone exempted exactly the lines
    that get absorbed -- short replies. Live, chat 84 turn 13: Sarah Moon's
    two lines and a guard's "Yes ma'am." (ten characters) were welded into a
    single quoted span, the guard never entered the comparison at all, and
    the span scored as one speaker with no warning raised.
    """
    if not spoken:
        return []
    if len(spoken) >= _MERGE_FACE_VALUE_CHARS:
        at = span.find(spoken)
        return [(at, at + len(spoken))] if at >= 0 else []
    ends = _ling("_SENTENCE_END_CHARS")
    out = []
    for match in re.finditer(re.escape(spoken), span):
        before = span[:match.start()].rstrip()
        if before and before[-1] not in ends:
            continue
        if spoken[-1] in ends or not span[match.end():].strip():
            out.append((match.start(), match.end()))
    return out


def _merged_span_actors(span, speech_events):
    """Which speakers' lines are actually inside this one quoted span.

    REGIONS, not membership, because one line can be a PREFIX or a tail of
    another speaker's longer line and the sentence-boundary test alone cannot
    tell that from absorption: Tamamo's "Go on." sits, correctly punctuated
    and correctly bounded, at the front of the Doctor's "Go on. I will wait
    here by the gate." Prose carrying only the Doctor's line is not a merge,
    and calling it one files a false finding against a correct page (it cost a
    rewrite until 2026-09-06, E12).

    So a claim whose text is entirely accounted for by a LONGER line from a
    different speaker is coincidence and drops out. What survives is a line
    occupying text no longer line explains -- which is what absorption is.
    """
    placed = []
    for actor, spoken in speech_events:
        for start, end in _spoken_line_regions(spoken, span):
            placed.append((start, end, actor, len(spoken)))
    actors = set()
    for start, end, actor, length in placed:
        if any(other_actor != actor and other_len > length
               and other_start <= start and end <= other_end
               for other_start, other_end, other_actor, other_len in placed):
            continue
        actors.add(actor)
    return actors


def _introducing_subject(lead, pat_map):
    """`(position, actor)` for the body that is the SUBJECT of `lead`, the
    sentence that introduces a quote, or None when no named body is.

    THE SUBJECT IS NAMED WHERE THE SENTENCE OPENS -- after nothing but the
    pack's own article ("The unfamiliar woman pulls her hands back"). A body
    named anywhere further in is an object or a modifier, and so is the
    possessor of a thing; a sentence whose subject is a description, a
    pronoun, a possessed thing or nothing at all says nothing this scan can
    check, and the check declines rather than promote the first other name
    it meets. It took the first body named ANYWHERE, skipping possessives,
    and every one of its three firings in the Brackwater run (scratch story
    166, 2026-10-07) was that promotion:

      turn 4607  "A man Tamsin didn't know leaned against the nearest
                 mooring post." -- Tamsin, inside the relative clause
      turn 4609  "Hester's voice came from behind, flat and low, pitched to
                 carry through the open door without following Tamsin
                 across the threshold." -- Tamsin, after a possessive
                 subject that names the speaker
      turn 4610  "Not to Tamsin." -- a verbless fragment whose subject is
                 the sentence before it

    Replayed over the 54 firings stored in that run's database, the old scan
    reproduces 45 and this one none: 38 are one story's pronoun subjects
    across its branches ("Her gaze returns to the Doctor."), the rest a
    vocative inside the speaker's own line, a "you" subject, and the three
    above. A body that opens the sentence by name and did not speak the line
    is still reported.
    """
    refs = sorted((mm.start(), mm.end(), actor)
                  for actor, pats in pat_map.items() for p in pats
                  for mm in p.finditer(lead))
    if not refs:
        return None
    start, end, actor = refs[0]
    opening = " ".join(re.findall(r"\w+", lead[:start])).casefold()
    if opening and opening not in {
            str(a).casefold() for a in (compositor_value("articles") or ())}:
        return None
    if lead[start:end].endswith(("'s", "’s")):
        return None
    return start, actor


def _check_quote_attribution(prose, event_order, actor_pronouns=None):
    """F4: a quoted line's nearest preceding actor reference must resolve to
    its actual speaker (prose convention assigns an unattributed quote to the
    nearest prior actor -- Enterprise t4 rendered Vorne's line right after
    'The unfamiliar woman pulls her hands back...', silently reassigning a
    tracked mind's speech to an anonymous body).

    Conservative by design -- it only fires when it POSITIVELY finds a
    different speaker's reference closer than the true speaker's:
    - a trailing attribution naming the true speaker clears the quote;
    - no locatable actor reference at all -> no call;
    - an intervening third-person pronoun whose gender differs from the
      nearest candidate's declared pronouns -> ambiguous, no call."""
    events = [ev for ev in (event_order or [])
              if isinstance(ev, dict) and ev.get("kind") == "speech"
              and ev.get("quote") and ev.get("actor")]
    if not prose or not events:
        return []
    # Reference patterns per distinct actor; a pattern text shared by two
    # actors identifies neither and is dropped.
    actors = list(dict.fromkeys(str(ev["actor"]) for ev in events))
    raw = {a: _actor_reference_patterns(a) for a in actors}
    owner = {}
    for a, pats in raw.items():
        for p in pats:
            owner.setdefault(p.pattern, set()).add(a)
    pat_map = {
        a: [p for p in pats if len(owner.get(p.pattern, ())) == 1]
        for a, pats in raw.items()
    }

    def _group_of(actor):
        return _pronoun_group((actor_pronouns or {}).get(actor))

    warnings = []
    flagged = set()
    for ev in events:
        expected = str(ev["actor"])
        body = _quote_body(str(ev.get("quote") or ""))
        if len(body) < 4 or body in flagged:
            continue
        qpat = _flexible_quote_re(body)
        m = qpat.search(prose) if qpat else None
        if not m:
            continue
        start, end = m.span()
        # Trailing attribution: same sentence right after the quote.
        tail = prose[end:end + 120]
        stop = re.search(r"[.!?\n]", tail)
        tail_seg = tail[:stop.end()] if stop else tail
        if any(p.search(tail_seg) for p in pat_map.get(expected, [])):
            continue
        # Leading scan: nearest actor reference between the previous quote
        # (or paragraph start) and this quote. The current quote's own
        # OPENING delimiter sits just before `start` and must not truncate
        # the context it opens.
        prefix = prose[:start].rstrip()
        while prefix and prefix[-1] in _ling("_QUOTE_CHARS"):
            prefix = prefix[:-1]
        cut = max(prefix.rfind("\n"),
                  max((prefix.rfind(qc) for qc in _ling("_QUOTE_CHARS")),
                      default=-1))
        prefix = prefix[cut + 1:]
        # THE OWNER OF A QUOTE IS THE SUBJECT OF THE SENTENCE THAT INTRODUCES
        # IT, NOT THE LAST NAME BEFORE IT.
        #
        # This scan used to take the reference NEAREST the quote, anywhere in
        # the run-up. In a room with one other body that is the subject; in a
        # room with five it is whoever the subject was looking at, holding
        # something of, or inclining toward -- which is what people do in a
        # crowd. Measured (multitude, 2026-09-05, PM8): 15 fires in 20 beats,
        # 0 true, every one the same shape. "Devereux Hallam kept his gloved
        # hands resting open upon the oak and inclined his head deferentially
        # toward Maren Vaunt." + Hallam's line was reported as Vaunt's,
        # because Vaunt is the object of `toward` and stands last. It fires
        # MORE the more names a sentence carries, so the guard got worse
        # exactly where dialogue is hardest to attribute.
        #
        # So: the introducing sentence is the last one before the quote, and
        # its subject is the body named where it OPENS (`_introducing_subject`)
        # -- English puts the subject before its verb, and every oblique
        # position (the object of a preposition, the possessor of a thing)
        # comes after it.
        # The last NON-EMPTY piece: the prefix ends where the quote's opening
        # mark was stripped off, so the splitter's final piece is the empty
        # tail after that sentence's full stop.
        _pieces = [s for s in split_sentences(prefix, _SENTENCE_SPLIT)
                   if s.strip()]
        lead = _pieces[-1] if _pieces else prefix
        best = _introducing_subject(lead, pat_map)  # (pos, actor)
        if best is None or best[1] == expected:
            continue
        # A gendered pronoun AFTER the subject that does not match that
        # subject's own declared pronouns re-points the reader elsewhere
        # ("Vorne nods, and she says...") -- ambiguous, decline to call.
        between = lead[best[0]:]
        cand_group = _group_of(best[1])
        ambiguous = False
        # The groups the ACTIVE pack declares, not three English words: the
        # Japanese pack adds 彼/彼女/彼ら groups and this scan could not see
        # any of them, so the ambiguity brake never engaged for a Japanese
        # story -- the same defect `_pronoun_to_group` was written to fix.
        groups = _pronoun_to_group()
        # EVERY FORM, not just the three subject pronouns. Iterating
        # `_PRONOUN_GROUPS` yields its KEYS -- he/she/they -- so an OBJECT or
        # POSSESSIVE pronoun ("him", "her", "them", "his") could never engage
        # this brake, and a sentence ending "...before Sarah Moon's orders
        # reach him." read to the check as containing no pronoun at all.
        # `_pronoun_to_group` already maps every form to its group; the brake
        # simply was not asking it. Live, chat 84 t13: the brake was the thing
        # that should have declined, and instead the guard's "Yes ma'am." was
        # reported as the doctor's -- an ENFORCEABLE finding, so a wrong call
        # here spends a whole extra narrator call.
        forms = sorted(_pronoun_to_group(), key=len, reverse=True)
        subject_re = re.compile(cue_boundary_pattern(
            "|".join(re.escape(w) for w in forms)), re.I)
        for pm in subject_re.finditer(between):
            pg = groups.get(pm.group(0).lower())
            if cand_group and pg and pg != cand_group:
                ambiguous = True
                break
        if ambiguous:
            continue
        flagged.add(body)
        warnings.append(
            f"Quote attributed to wrong speaker: \"{body[:60]}\" is spoken "
            f"by {expected}, but the nearest preceding actor reference in "
            f"the prose is {best[1]} and no attribution names {expected}. "
            "Make the true speaker the quote's clear owner."
        )
    return warnings


# Perception/gesture verbs that make a following room mention a LOOK, not a
# placement ("glances at the corridor"); they must not trip the position check.


def _check_position_fidelity(prose, position_facts, room_names):
    """F2: a character narrated at a room that differs from their committed
    position, with no movement event this beat, is a continuity break (DW t6:
    the Doctor mid-road; t7 renders him back in the TARDIS doorway).

    position_facts: [{name, room_id, moved}] -- display name, the room the
    scene commits them to THIS beat, and whether this beat's diff moved them.
    room_names: {room_id: display_name} for the rooms in play.

    Narrow: only a placement preposition (in/inside/within/into/at/back in)
    directly ahead of another room's display name, in a sentence whose nearest
    preceding actor reference is the unmoved character, fires."""
    if not prose or not position_facts:
        return []
    usable_rooms = {}
    for rid, rname in (room_names or {}).items():
        rname = str(rname or "").strip()
        if (len(rname) < _display_floor(rname)
                or rname.lower() in _ling("_GENERIC_ROOM_WORDS")):
            continue
        usable_rooms[rid] = rname
    warnings = []
    for fact in position_facts:
        if not isinstance(fact, dict) or fact.get("moved"):
            continue
        name = str(fact.get("name") or "").strip()
        own_room = fact.get("room_id")
        pats = _actor_reference_patterns(name)
        if not name or not own_room or not pats:
            continue
        own_name = str(usable_rooms.get(own_room) or "").lower()
        for sentence in split_sentences(prose, _SENTENCE_SPLIT):
            # Quoted speech is a speaker's claim, not narration.
            scan = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
            best = max((mm.start() for p in pats for mm in p.finditer(scan)),
                       default=-1)
            if best < 0:
                continue
            for rid, rname in usable_rooms.items():
                if rid == own_room:
                    continue
                low = rname.lower()
                # A room whose name contains (or is contained by) the
                # character's own room's name cannot be told apart reliably.
                if own_name and (low in own_name or own_name in low):
                    continue
                # A language marks place with an adposition, and which SIDE of
                # the room name it sits on is the language's business, not this
                # guard's -- Japanese postposes it. The pack holds the whole
                # phrase with a {room} slot for that reason.
                shape = _ling("_PLACEMENT_PHRASE")
                place = re.compile(
                    str(shape["pattern"]).replace("{room}", re.escape(rname)),
                    int(shape.get("flags") or 0))
                pm = place.search(scan, best)
                if not pm:
                    continue
                if _ling("_LOOK_VERB_RE").search(scan[:pm.start()]):
                    continue
                warnings.append(
                    f"Character placed in wrong room: '{name}' is narrated "
                    f"in '{rname}' but this beat's committed position is "
                    f"'{usable_rooms.get(own_room, own_room)}' and no "
                    "movement occurred for them this beat. Keep them where "
                    "the scene puts them."
                )
                break
            else:
                continue
            break
    return warnings


def _check_portal_fidelity(prose, portal_states):
    """F3: named portal state in prose must match the committed scene (DW t9
    shuts the double doors; t12 renders 'through the open doors' with no
    open event). portal_states: {display_name: 'open'|'shut'} for portals the
    player can currently see (built in agents/narration.py)."""
    if not prose or not portal_states:
        return []
    scan = _ling("_NARRATION_QUOTE_RE").sub(" ", prose)
    warnings = []
    for name, state in portal_states.items():
        name = str(name or "").strip()
        state = str(state or "").strip().lower()
        if len(name) < _display_floor(name) or state not in ("open", "shut"):
            continue
        shape = _ling("_PORTAL_STATE")
        wrong = shape["shut"] if state == "open" else shape["open"]
        name_pat = str(shape["join"]).join(
            re.escape(w) for w in name.split()) or re.escape(name)

        def _asserted(form):
            return re.search(
                str(shape[form]).replace("{state}", wrong)
                                .replace("{name}", name_pat), scan, re.I)

        asserted = (
            # "the open doors" / "still-sealed hatch"
            _asserted("modifier")
            # "the doors ... stand open" (same clause)
            or _asserted("predicate")
        )
        if asserted:
            opposite = "shut" if state == "open" else "open"
            warnings.append(
                f"Portal state contradicts the scene: '{name}' is committed "
                f"{state} this beat, but the prose renders it {opposite}. "
                "Match the committed portal state exactly."
            )
    return warnings


# The player's own interiority, in the second person the narrator writes in.
# "you feel", "your terror", "terror grips you" -- the same boundary
# `_check_player_interiority_authority` defends on the Director's side, at the
# last stage before the reader.


# `_check_player_interiority_prose` LIVED HERE, and it is gone rather than
# demoted. It matched `_YOU_INTERIOR` -- a named-emotion list plus a verb
# list ("you feel", "you know", "you realise") -- against narrator prose in
# the second person, and it was ENFORCEABLE, so every firing bought a whole
# extra narrator call.
#
# It could not tell the two meanings of its own trigger apart. Second-person
# narration says "you feel" about SENSATION constantly, and that is the
# narrator doing its job: measured over 2,389 stored drafts it flagged 73
# (3.1%), and the sample reads "'you feel' in 'laps against your
# shoulders'" -- water against a body, an observable the view delivered.
# The view-exemption did not save it, because the phrase it looked up was
# the bare trigger rather than the clause.
#
# It is the guard class this repo already has a name for: a literal matcher
# whose failure rate rises with how well the model writes. The rule it was
# defending is real and stays in the narrator sheet, and the DIRECTOR-side
# `_check_player_interiority_authority` is untouched -- that one matches a
# named subject in an omniscient sentence, which is a different and
# answerable question.


def _dialogue_tokens(view, p_lines):
    """The delivered lines, numbered, for the narrator to place not retype.

    THE MODEL CANNOT PARAPHRASE A LINE IT NEVER TYPES. That is the whole
    mechanism, and it is the move this codebase already made once: perception
    stopped repairing model prose when the composer began writing percepts,
    because chronology became a field rather than a pass. Dialogue fidelity is
    the same shape -- a property of the assembly, not a behaviour to request.

    Measured (`docs/experiments/NARRATOR_DIALOGUE_PLACEHOLDERS_2026-08-24.md`)
    on the beat that prompted it: 75% of delivered lines survived under the
    shipped prompt, 100% under this. The prompt was not the variable --
    DIALOGUE FIDELITY is already "ABSOLUTE", already says "NEVER SUMMARISE A
    SPOKEN LINE", and had already failed three times on that beat with the
    dropped lines named in correction notes.

    The player's own lines are excluded, because the current_narration framing (the player's own line is already on the page, 2026-09-14; the named PLAYER ECHO RULE is gone) requires
    their ABSENCE -- handing them back as tokens to place would push the model
    to violate one rule to satisfy the other.
    """
    excluded = {
        re.sub(r"\s+", " ", _quote_body(q).casefold()).rstrip(".,!?…;:")
        for q in (p_lines or []) if _quote_body(q)
    }
    lines, seen = [], set()
    for _at, body in quoted_lines(view):
        quote = re.sub(r"\s+", " ", body.strip())
        key = quote.casefold().rstrip(".,!?…;:")
        if not quote or key in excluded or key in seen:
            continue
        if _reads_as_attribution(quote):
            # NOT A LINE, AND WORSE THAN USELESS AS ONE. A span is paired by
            # its marks now (`quoted_lines`), so a short line ("No.") no
            # longer leaves its marks to pair across the ATTRIBUTION between
            # two lines -- the shape this guard was written for. It stays
            # for any mark still unpaired (a stray one inside a delivered
            # line pairs across its neighbour the same way): handed to the
            # narrator as a line to place, an attribution would put "Riker
            # says in a quiet voice:" on the page inside quotation marks.
            continue
        seen.add(key)
        lines.append(quote)
    return lines


#: The composer's own attribution formula. A span carrying one is the text
#: BETWEEN two quoted lines, never a line.
_ATTRIBUTION_TELLS = (" says in a ", " says in an ", " says under ",
                      " speaks in a ", " asks in a ", " replies in a ",
                      " says:", " speaks:", " asks:")


def _reads_as_attribution(text):
    lowered = " %s " % str(text or "").casefold()
    return any(tell in lowered for tell in _ATTRIBUTION_TELLS)



def _check_speech_marking(prose, view_quotes, excluded_bodies=()):
    """A delivered line that reached the page unquoted was re-costumed.

    DIALOGUE FIDELITY asks only whether the WORDS survived: `_contains_quote`
    strips markup for comparison (deliberately -- a tag inside a quote must
    not read as a dropped line) and then substring-searches, so an emphasised
    span with no quote marks passes it. Measured: view `Mara says in a quiet
    voice: "We should not be here."` with prose `She looks away. <i>We should
    not be here.</i>` raised no warning at all. A delivered line is SPEECH,
    and the page marks speech with quotation marks; the same words outside
    every quoted region are a different speech act, which is why the reader's
    own contract reserves emphasis for a thought the prose is voicing rather
    than quoting.

    Regions rather than a quote regex, the way the frontend and the schema
    both do it: `_QUOTE_BODY_RE` needs four characters between the marks, so
    a short line is invisible to it and the marks it skips then pair with
    their neighbours.

    The player's own lines are excluded: the current_narration framing (the player's own line is already on the page, 2026-09-14; the named PLAYER ECHO RULE is gone) requires their
    ABSENCE, so their marking is a different rule's business.
    """
    scan = re.sub(r"\s+", " ",
                  _fold_typography(strip_prose_markup(str(prose or ""))))
    regions = [m.span() for m in _ling("_NARRATION_QUOTE_RE").finditer(scan)]
    folded = scan.casefold()
    warnings = []
    for quote in view_quotes or ():
        body = re.sub(r"\s+", " ",
                      _fold_typography(quote)).casefold().rstrip(".,!?…;:")
        if not body or body in (excluded_bodies or ()):
            continue
        placed, marked, at = False, False, folded.find(body)
        while at >= 0:
            placed = True
            end = at + len(body)
            if any(s <= at and end <= e for s, e in regions):
                marked = True
                break
            at = folded.find(body, at + 1)
        if placed and not marked:
            warnings.append(
                "Delivered line rendered without quotation marks: "
                f"\"{quote[:80]}\"")
    return warnings


def _check_attire_fidelity(prose, attire_facts):
    """A region the ledger still COVERS may not be narrated bare.

    The same shape as `_check_portal_fidelity`: a committed two-valued state
    and a prose assertion of its opposite. `attire_facts` is [{refs,
    covered}], built in agents/narration.py behind the same perception gate
    `_position_delta_payload` uses, so an unperceived body can never raise a
    warning about prose that rightly omits it.

    Three narrowings, each subtracting: quoted speech is scrubbed first (a
    speaker's CLAIM about a body is not narration); a partially exposed
    region never reaches `covered`; and the exposure word must be bound to
    the region noun by an ownership token of that body, so scenery is never a
    body.
    """
    if not prose or not attire_facts:
        return []
    shape = _ling("_EXPOSURE_STATE")
    scan = _ling("_NARRATION_QUOTE_RE").sub(" ", str(prose))
    # An idiom that names a REGION by accident -- being unarmed, not being
    # undressed. Masked at equal length so nothing shifts under a later match.
    scan = re.sub(str(shape["idiom"]), lambda m: " " * len(m.group(0)),
                  scan, flags=re.I)
    warnings = []
    for fact in attire_facts:
        refs = [re.escape(str(r)) for r in (fact.get("refs") or ()) if str(r)]
        if not refs:
            continue
        for region in (fact.get("covered") or ()):
            region = str(region or "").strip()
            if not region:
                continue
            pattern = (str(shape["assertion"])
                       .replace("{owner}", "|".join(refs))
                       .replace("{state}", str(shape["state"]))
                       .replace("{region}", re.escape(region)))
            if re.search(pattern, scan, re.I):
                warnings.append(
                    "Narrated exposure contradicts the attire ledger: the "
                    f"{region} is narrated bare while this beat's ledger "
                    "still has it covered. Describe it as the ledger has it.")
                break
    return warnings


def _whole_on_the_page(form):
    """A form as a whole word of the page: no word character on either side
    for a form in a spaced script, exactly as this module always bounded one,
    and the form's own script boundary (`name_boundary_pattern`) for a form
    holding an unspaced script, whose particle is a word character."""
    text = str(form or "")
    if UNSPACED_SCRIPT.search(text):
        return name_boundary_pattern(text)
    return rf"(?<!\w){re.escape(text)}(?!\w)"


def _check_narrator_fidelity(out, view, recent_prose=None, exclude_quotes=None,
                             cast_pronouns=None, player_name=None,
                             narration_person=None, player_aliases=None,
                             event_order=None, position_facts=None,
                             room_names=None, portal_states=None,
                             attire_facts=None, narration_tense=None,
                             observations=None, player_forms=None,
                             present_labels=None):
    warnings = []
    view_text = str(view or "")
    prose = out.get("prose") or ""
    # THE MULTI-WORD ARM IS GONE (2026-09-06, the owner's ruling: a check
    # that fires on otherwise valid output has to die, and the fix belongs
    # in the payload and the prompt rather than in a reading of the page).
    #
    # It asked `[A-Z][a-z]+( [A-Z][a-z]+)+` of the view and then required the
    # prose to say whatever came back -- GUESSING AT WHAT A NAME IS FROM
    # CAPITAL LETTERS, which is this repo's oldest recurring defect and the
    # one thing CLAUDE.md's no-word-lists rule is about. Measured over the
    # owner's 3,770 stored beats carrying both a view and prose: it fires on
    # 1,577 of them, 41.8%, 2,141 times over 138 distinct phrases. What it
    # actually caught, by volume: ROOM NAMES the narrator was never obliged
    # to utter -- `Private Session Room` 595, `Reception Room` 465, `Ten
    # Forward` 108, `Observation Room`, `Interview Cell`, `Western Array
    # Chamber` -- and phrases that are not names at all: `Mmmm It`, `So Uhm`,
    # `Doctor Doctor`, `East Asian`, `Long Odds`. Two beats in five carried a
    # warning about prose that was fine, which is how a warning channel stops
    # being read.
    #
    # The arm below survives because it is built the other way round: it asks
    # the CAST ROSTER who the people are -- a closed set the engine owns --
    # and carries a measured tolerance for the pronoun prose ordinarily uses
    # after a first mention (29 false positives down to 3, over the same
    # corpus). A name comes from the roster, never from a capital letter.

    # A NAME IS WHOEVER THE ROSTER SAYS IS HERE, of one word or several.
    #
    # Two questions, both of which the deleted regex was guessing at. WHAT IS
    # A NAME: the roster is already in this payload, so the answer comes from
    # the cast rather than from capitalisation -- which is also what keeps a
    # room, a rank and a stray capitalised phrase out of it. WHAT COUNTS AS
    # PRESENT: prose names a person once and then refers to them by pronoun,
    # or by one part of their name, and neither is a dropped body. Measured
    # over 2,277 stored beats carrying both a view and prose: without the
    # pronoun tolerance this fires on 29 of 217 view-named single-token cast
    # members and 26 of those are pronoun prose; with it, 3.
    #
    # The single-token restriction went with the regex it was paired with:
    # it existed because the multi-word case was the regex's, and a
    # multi-word cast name is now nobody's unless it is this arm's. Each
    # part of a name counts as the name, which is the surname tolerance the
    # old arm had and the reason "Voss" answers for "Elyra Voss".
    #
    # AN ARTICLE IS NOT A PART OF THE NAME IT LEADS (agents_common audit
    # F15): "The" was a part of "The Doctor", matched case-insensitively, so
    # any page containing the word *the* had "mentioned" him. And every form
    # is bounded by its own script (`_whole_on_the_page`): `(?<!\w)…(?!\w)`
    # never matched a Japanese name with its particle on, so in Japanese the
    # name was never in the view and this arm never ran (F14). A name written
    # without spaces answers by its script runs as a spaced one by its words.
    articles = _referring.articles()
    for name, pronouns in (cast_pronouns or {}).items():
        text = str(name or "").strip()
        if not text or text == player_name:
            continue
        if not re.search(_whole_on_the_page(text), view_text):
            continue
        parts = [w for w in text.split()
                 if len(w) >= 3 and w.casefold() not in articles] \
            + _unspaced_name_parts(text)
        parts = parts or [text]
        if any(re.search(_whole_on_the_page(w), prose, re.I) for w in parts):
            continue
        forms = [str(pronouns.get(k) or "").strip().lower()
                 for k in ("subject", "object", "possessive")
                 ] if isinstance(pronouns, dict) else []
        if any(form and re.search(_whole_on_the_page(form), prose.lower())
               for form in forms):
            continue
        warnings.append(
            f"Proper noun from view missing in narrator prose: '{text}'")

    # past_narration is supplied to the narrator as the story's own text --
    # voice, rhythm and established detail -- but nothing stops the model
    # from reusing its content instead -- especially when the current view covers similar ground
    # (same room, same people) to a recent turn. Two or more shared
    # six-word runs between this turn's prose and a recent turn's prose
    # essentially can't happen by coincidence; it means this turn's beats
    # were recycled rather than drawn from the current view.
    # STRIP THE SPEAKERS FIRST. The labels in play come from the view, which
    # is where the composer wrote them -- a recognised name is short and
    # harmless, an unrecognised body's descriptor is long ("the spare upright
    # man") and recurs in every sentence about them, so two unrelated
    # sentences about one stranger overlap on the label rather than on any
    # recycled content. See `_word_shingles`.
    speaker_labels = set(re.findall(
        r"(?:^|[.!?]\s+)([A-Za-z][^.!?\n]{0,40}?)\s+(?:says|asks|replies|"
        r"speaks|adds|answers)\b", view_text))
    speaker_labels |= {str(x) for x in (player_aliases or ())}
    if player_name:
        speaker_labels.add(str(player_name))
    current_shingles = _word_shingles(prose, labels=speaker_labels)
    if current_shingles:
        for prev_prose in (recent_prose or []):
            overlap = current_shingles & _word_shingles(
                prev_prose, labels=speaker_labels)
            if len(overlap) >= 2:
                sample = next(iter(overlap))
                warnings.append(
                    "Narrator prose appears to reuse a previous turn's "
                    "content instead of describing this turn's view "
                    f"(shared phrase: '{sample}...')."
                )
                break

    # Any quoted line in the view is dialogue that reached the player at
    # full or fragment clarity (muffled hits render as unquoted "...something
    # about X..." text and are exempt). DIALOGUE FIDELITY requires every such
    # line to survive verbatim -- if the narrator drops, truncates, or
    # paraphrases a quote, the exact substring will no longer be found.
    # EXCEPT the player's own declared lines: the current_narration framing (the player's own line is already on the page, 2026-09-14; the named PLAYER ECHO RULE is gone) requires those
    # to be *excluded*, the exact opposite requirement, so they must never be
    # scored against this check -- otherwise the two rules contradict each
    # other and the retry loop would be pushing the model to violate one to
    # satisfy the other.
    excluded_bodies = {
        re.sub(r"\s+", " ", _quote_body(q).casefold()).rstrip(".,!?…;:")
        for q in (exclude_quotes or []) if _quote_body(q)
    }
    normalized_prose = re.sub(r"\s+", " ", prose.casefold())
    view_quotes = []
    for _at, body in quoted_lines(view_text):
        quote = re.sub(r"\s+", " ", body.strip())
        if not quote:
            continue
        view_quotes.append(quote)
        if quote.casefold().rstrip(".,!?…;:") in excluded_bodies:
            continue
        if not _contains_quote(normalized_prose, quote):
            warnings.append(
                f"Dialogue from view missing or altered in narrator prose: \"{quote[:80]}\""
            )

    # The inverse of dialogue preservation is equally absolute: a quoted line
    # the player-facing view never delivered has no authorised speaker. The
    # old check proved only that required quotes survived, so a draft could
    # keep every real line and add one more from the narrator. This happened
    # when a reaction-loop act vanished from perception and the narrator
    # guessed both the missing motion and a fresh NPC line.
    # AN ELLIPSIS IS ONE MARK HOWEVER IT IS TYPED. The view writes a heard
    # fragment "...there... pawing..." and the narrator sets it
    # "…there… pawing…"; compared byte for byte, a line the view
    # delivered read as invented (scratch play 2026-09-14, chat 2 turn 6).
    # Both sides fold to the three-dot spelling before the comparison.
    def _fold_marks(text):
        return re.sub(r"\s+", " ", str(text).replace("\u2026", "...")).casefold()

    allowed_quotes = {
        _fold_marks(quote).rstrip(".,!?;:")
        for quote in view_quotes
    }
    # INVENTED MEANS THE VIEW NEVER DELIVERED IT, NOT THAT THE VIEW DID NOT
    # QUOTE IT. The set above holds only spans the view itself put inside
    # quote marks, and the view marks a full line that way and a HALF-HEARD
    # one not at all: a muffled percept renders as `A muffled voice:
    # ...deafen... glass... midnight...`, and a narrator that correctly puts
    # that fragment in the reader's ear as a quote was told it had invented
    # dialogue (PA10, lighthouse turn 12 -- and the warning is enforceable,
    # so the false positive bought a rewrite). The same holds for any other
    # words the view delivers unquoted and prose rightly quotes. So the
    # comparison is against WHAT THE VIEW DELIVERED: a span whose words are
    # in the view verbatim came from the view, however the view marked them.
    delivered = _fold_marks(view_text)
    # AND THE PLAYER'S OWN LINE HAS A SPEAKER. The view does not carry it --
    # it is on the page already -- so a narrator that quotes it back was told
    # it had invented dialogue ("Ahh... This is really tight.", the owner's
    # chat 137 idx 46, round 9; "Wahh! What's happening?", chat 153 idx 23,
    # round 4). The same exemption the missing-line check above makes.
    player_lines = {_fold_marks(body).rstrip(".,!?;:") for body in excluded_bodies}
    for _at, body in quoted_lines(prose):
        quote = re.sub(r"\s+", " ", body.strip())
        normalized = _fold_marks(quote).rstrip(".,!?;:")
        if (normalized and normalized not in allowed_quotes
                and normalized not in player_lines
                and normalized not in delivered):
            warnings.append(
                "Narrator invented quoted dialogue absent from the player "
                f"view: \"{quote[:80]}\""
            )

    # ONE PAIR OF QUOTES, ONE MOUTH.
    #
    # The check above asks whether each line SURVIVED. It cannot ask whether
    # the line ended up in the right person's mouth, and both questions have
    # the same answer when two speakers' lines are welded into a single
    # quoted span: every body is present verbatim, so dialogue fidelity
    # passes while the reader is told the wrong character said half of it.
    #
    # Live (chat 38, t140): Tamamo's "Be at ease, both of you." and the
    # Doctor's "Tamamo. A pleasure." rendered as the single span
    # "Be at ease, both of you. Tamamo. A pleasure.", closed by "The Doctor's
    # voice carries clean across the clearing". The view had them correctly
    # separated, one attributed clause each. Also chat 38 t39, where the whole
    # of Guinan's line was absorbed into the Doctor's.
    #
    # `event_order` is the right source rather than the raw dialogue log: it
    # is already gated to lines that reached the player's view, so a line the
    # player never heard cannot raise a warning about prose that rightly
    # omits it. Bodies under 15 characters are ignored -- a short line can sit
    # inside a longer one by coincidence, and being wrong here costs a
    # rewrite.
    speech_events = []
    for event in (event_order or []):
        if not isinstance(event, dict) or event.get("kind") != "speech":
            continue
        # The player's OWN line is not this check's business. The echo rule
        # requires it to be ABSENT, so its presence is a different failure
        # with a different fix, and scoring it here would buy a rewrite for
        # the wrong reason. It has to be skipped explicitly rather than by
        # accident: it carried no `quote` at all until the narrator-package
        # work restored one.
        if event.get("declared"):
            continue
        actor = str(event.get("actor") or "").strip()
        spoken = re.sub(r"\s+", " ", _quote_body(event.get("quote"))).casefold()
        if actor and spoken:
            speech_events.append((actor, spoken))
    for _at, body in quoted_lines(prose):
        span = re.sub(r"\s+", " ", body).casefold()
        actors = _merged_span_actors(span, speech_events)
        if len(actors) >= 2:
            warnings.append(
                "Merged dialogue from different speakers in one quoted span "
                f"({', '.join(sorted(actors))}): \"{body[:80]}\""
            )

    warnings.extend(_check_pronoun_fidelity(prose, cast_pronouns))
    warnings.extend(_check_player_person(
        prose, player_name, narration_person, player_aliases))
    warnings.extend(_check_narration_person_match(
        prose, narration_person, player_name))
    # `narration_tense` is None on every story that has not set one, and the
    # check returns [] for it -- so this line adds nothing to the warning
    # stream of the 81 stories that predate the dial.
    warnings.extend(_check_narration_tense_match(prose, narration_tense))

    # F1-F4 world/ordering fidelity (all deterministic; each has its own
    # prefix in `agents/narration._ENFORCEABLE_PREFIXES`, which named the
    # findings that bought one correction rewrite until the correction pass
    # was removed 2026-09-06 -- a violation is now recorded on the step and
    # the page stands, E12).
    warnings.extend(_check_event_order(prose, event_order))
    warnings.extend(_check_quote_attribution(
        prose, event_order, actor_pronouns=cast_pronouns))
    warnings.extend(_check_position_fidelity(
        prose, position_facts, room_names))
    warnings.extend(_check_portal_fidelity(prose, portal_states))
    warnings.extend(_check_action_direction(prose, event_order))
    warnings.extend(_check_action_attribution(
        prose, observations, player_forms=player_forms,
        present_labels=present_labels))

    # F5-F6: the page against the two records it was written from. Neither is
    # in `_ENFORCEABLE_PREFIXES`, which no longer decides anything the reader
    # sees (E12): every finding here is a measurement, and none is an edit.
    warnings.extend(_check_speech_marking(prose, view_quotes, excluded_bodies))
    warnings.extend(_check_attire_fidelity(prose, attire_facts))

    return warnings
