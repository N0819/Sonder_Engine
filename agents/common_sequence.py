"""A declared beat as the engine holds it: player-speech provenance,
stage-direction excision, normalisation (norm_sequence), duplicate collapse,
speech fusion, event ids, narrated-speech repair and the player token.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import hashlib
import re
from llm.schemas import normalize_speech_volume, normalize_vocal_affect

from agents.common_base import _ling, _quote_body
from agents.common_names import _word_count
from agents.common_acts import (
    _COMMUNICATIVE_TYPES,
    _classify_action_commitment,
    _is_mental_action,
    _normalize_effect,
)


#: Characters of one speech line worth searching for provenance. A merged
#: player line is a sentence or three; past this it is not a speech line and
#: the coverage search is not owed to it.
_SPEECH_ANCHOR_MAX_CHARS = 4000


def _speech_anchor_atoms(value):
    """The comparable characters of a text: case, spacing, punctuation gone.

    The unit is the alphanumeric CHARACTER and not the word, because the
    engine runs stories in scripts that do not space their words -- a
    word-split provenance test answers nothing in Japanese. Both sides of
    every comparison are reduced the same way, so the reduction can only
    forgive punctuation the model re-styled, never invent a word.
    """
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _input_quoted_spans(raw_input):
    """The bodies of the input's quoted spans, in the order the player wrote
    them. The quote vocabulary is the language pack's, so a story written in
    corner brackets has spans too."""
    segments = _ling("_QUOTED_SPAN_RE").split(str(raw_input or ""))
    # split() alternates residue/span/residue...; odd indices are the spans.
    bodies = (_quote_body(s) for i, s in enumerate(segments) if i % 2 == 1)
    return [body for body in bodies if body.strip()]


def _covered_by_spans(atoms, spans):
    """Can this text be read off those spans, in order, in unbroken runs?

    Each span contributes at most one run and the spans are consumed in the
    order they were written, so a line that reorders the player's speech, that
    breaks a span to skip words inside it and rejoin later, or that carries one
    word from nowhere, is not covered.
    """
    if not atoms:
        return True
    if not spans or len(atoms) > _SPEECH_ANCHOR_MAX_CHARS:
        return False
    failed = set()

    def walk(pos, first):
        # Every step consumes a span, so recursion is bounded by the number of
        # spans rather than by the length of the line.
        if pos >= len(atoms):
            return True
        if (pos, first) in failed:
            return False
        for index in range(first, len(spans)):
            span = spans[index]
            start = span.find(atoms[pos])
            while start != -1:
                run = 0
                while (pos + run < len(atoms) and start + run < len(span)
                       and span[start + run] == atoms[pos + run]):
                    run += 1
                for take in range(run, 0, -1):
                    if walk(pos + take, index + 1):
                        return True
                start = span.find(atoms[pos], start + 1)
        failed.add((pos, first))
        return False

    return walk(0, 0)


def player_speech_anchored(line, raw_input):
    """Is every word of this player speech line the player's own?

    Provenance is COVERAGE, not containment. A player who writes several
    quoted spans separated by narration -- the ordinary way anyone writes a
    turn -- gets one merged `speech` element back from interpret, and that
    merge is a contiguous run of nothing. Measured (15-beat run, the beat whose
    question no character ever answered): the merged line read False against
    the raw input while every span of it read True, so the guard dropped the
    whole line and nulled the speech, and the player's question reached no
    mind. A neighbouring beat whose speech happened to be one unbroken quote
    survived and was answered; that was the entire difference.

    So a line is anchored when it is a contiguous run of the input (the old
    floor, kept whole) or when its characters can be read off the input's
    quoted spans in the order written. Narration BETWEEN the spans is not a
    span and does not anchor anything, and text the model invented matches
    nothing and is still refused.
    """
    atoms = _speech_anchor_atoms(line)
    if not atoms:
        return True
    flat_line = re.sub(r"\s+", " ", str(line or "")).strip().casefold()
    flat_source = re.sub(r"\s+", " ", str(raw_input or "")).strip().casefold()
    if flat_line and flat_line in flat_source:
        return True
    return _covered_by_spans(
        atoms,
        [_speech_anchor_atoms(body) for body in _input_quoted_spans(raw_input)])


def discard_unanchored_player_speech(out, raw_input):
    """Drop exact player lines whose words were not the player's own.

    A description such as ``I explain the warning signs`` does not authorize
    the interpreter to write a speech for the player. Downstream ownership
    checks trust the interpreter, so provenance has to be enforced here.
    `player_speech_anchored` is the test, and it is span-aware: merging the
    input's quoted spans into one line is legitimate authorship, inventing
    words is not.
    """
    if not isinstance(out, dict):
        return []

    dropped, kept = [], []
    for event in out.get("sequence") or []:
        if not isinstance(event, dict) or event.get("type") != "speech":
            kept.append(event)
            continue
        line = str(event.get("text") or "").strip()
        if line and not player_speech_anchored(line, raw_input):
            dropped.append(line)
            continue
        kept.append(event)
    out["sequence"] = kept

    flat = str(out.get("speech") or "").strip()
    if flat and not player_speech_anchored(flat, raw_input):
        if flat not in dropped:
            dropped.append(flat)
        out["speech"] = None
    surviving = [event.get("text") for event in kept
                 if isinstance(event, dict) and event.get("type") == "speech"
                 and event.get("text")]
    if surviving:
        out["speech"] = surviving[0]
    return dropped

# A stage direction written INSIDE a speech element: "*leans in* Sit down."
# Bounded and single-line on purpose: an unpaired asterisk in ordinary prose
# must not swallow the rest of the line looking for its partner.
_STAGE_DIRECTION_RE = re.compile(r"\*([^*\n]{1,400}?)\*")


def split_stage_directions(text):
    """Speech text -> (the words actually spoken, the conduct written into it).

    A character model trained on chat roleplay writes conduct inside the line
    it speaks -- "*leans in and sets a hand flat on her shoulder* You will want
    to sit down" -- instead of emitting the {type:'action'} element the
    sequence contract already provides beside it. Nothing forces this; one live
    beat declared a proper action element AND smuggled a second act into the
    speech in the same breath.

    The engine had no opinion about the contents of `text`, so everything in it
    was treated as SOUND. A body movement then went through the whole
    audibility apparatus -- distance, muffling, enclosure, deafness -- and a
    listener who could hear but not see was told about it in so many words:
    `You hear Reya say: "*leans in...*"`. That is a channel violation. Not a
    knowledge one -- the person being touched would feel it -- but the flow is
    wrong, and a wrong flow is an engine failure, never a model's, so the floor
    here is deterministic rather than a request in the prompt.

    Measured before the fix (chat 62, 12 turns): 52% of that chat's speech
    elements carried one, against 0.9% across the rest of the corpus. It grew
    turn over turn because the span was stored in the speaker's own episodic
    memory as words she SAID and read back to her on the next beat, and it was
    also the cause of a second symptom -- the Director, a different model,
    re-rendered the stage direction as prose, which no longer matched the
    declaration, so the verbatim-speech guard dropped the line as invented on
    7 of 12 turns against 7 of 1,715 turns corpus-wide.

    A ONE-WORD span is markdown emphasis, not a stage direction ("what does it
    *feel* like") -- the asterisks come off and the word stays spoken.

    `tone` was considered as the home for the vocal-manner spans (a laugh, a
    drop in register) and rejected. `_inject_dialogue` renders tone only when
    the listener can SEE the speaker, so an audible laugh parked there is lost
    in the dark -- exactly the same class of bug one layer down. Every span
    becomes conduct instead, and perception delivers it by whatever channel the
    act actually engages, which is perception's job and not this function's.
    """
    raw = str(text or "")
    if "*" not in raw:
        return raw, []
    spans = []

    def _take(match):
        body = " ".join(match.group(1).split())
        if not body:
            return ""
        if _word_count(body) == 1:
            # Emphasis on a single spoken word, counted in its own script
            # (`_word_count`: `.split()` made every Japanese span one word,
            # so no Japanese stage direction was ever cut -- agents_common
            # audit F4). It stays in the line.
            return body
        spans.append(body)
        return ""

    spoken = _STAGE_DIRECTION_RE.sub(_take, raw)
    # Collapse the whitespace and orphaned punctuation the excision leaves
    # behind, so "*leans in* You will..." does not become " You will...".
    spoken = re.sub(r"\s{2,}", " ", spoken).strip()
    # The full-width marks too: "*彼女の手を取って*、行こう。" left "、行こう。".
    spoken = re.sub(r"^[,;:.\-—\s、，。；：]+", "", spoken).strip()
    return spoken, spans


def _promoted_stage_action(span, speech_elem):
    """One excised stage direction, as the action element it should have been.

    It inherits the speech element's concealment: a stage direction inside a
    whispered aside was hidden by the words around it, and must not become
    overt conduct just because it moved onto its own channel. `observable` goes
    through the same mental-verb check `norm_sequence` applies to any other
    action, so "*thinks better of it*" resolves to an imperceptible beat rather
    than a visible one.
    """
    observable = "" if _is_mental_action("", span) else span
    return {
        "type": "action",
        "attempt": span,
        "observable": observable,
        "visibility": ("concealed"
                       if speech_elem.get("visibility") == "concealed"
                       else "overt"),
        "conceal_from": list(speech_elem.get("conceal_from") or []),
        "targets": [],
        "commitment": _classify_action_commitment(span),
        "verb": "",
        "stage": "immediate",
        "intended_effects": [],
        "asserted_effects": [],
        "_promoted": True,
    }


def collapse_duplicate_events(sequence, warn=None, asserted=None):
    """One declared act is one event.

    `speech`, `action` and `actions` are MIRRORS of `sequence`, not additional
    channels -- and `norm_sequence` treated them as additional, appending every
    entry of the scalar mirrors on top of a sequence that already held them.
    Measured on the real validated path:
    `{"sequence": [speech, "squirm", speech], "actions": [{"attempt": "squirm"}]}`
    came out as FOUR elements, and `assign_event_ids` labelled the one squirm
    `turn:1:player:1:action` AND `turn:1:player:3:action`. Nothing downstream
    collapsed them, so one declared act was adjudicated, perceived and narrated
    twice.

    IDENTITY IS THE DECLARATION, not the slot it arrived in: type, normalized
    content, targets, `stage` and `phase`. `stage`/`phase` are IN the key on
    purpose -- a declaration decomposed into approach-then-contact repeats its
    own text and is genuinely two events.

    The base tier is EXACT, and that is the whole safety argument. Dropping
    declared conduct is the failure this seam exists to prevent, so a
    restatement has to be a restatement: same words, same target, same phase.
    "grab the rifle" and "grab the rifle and rack it" overlap completely
    against the shorter and are two different declarations.

    `asserted` opens the narrower second tier for a REPAIR merge: elements at
    or after that index are additions, licensed only to cover a clause the
    coverage check found uncovered, and an addition that restates an already
    asserted action is by construction not that. Only there is content-word
    overlap used, on the same measure `_dedupe_promoted_actions` applies.

    A dropped element's dependents are rewritten onto its survivor, or
    `settle_sequence_dispositions` would block them as a missing prerequisite.
    """
    rows = [e for e in (sequence or []) if isinstance(e, dict)]
    if len(rows) < 2:
        return list(sequence or [])

    def _norm(text):
        return " ".join(str(text or "").casefold().split())

    def _content(element):
        kind = str(element.get("type") or "action")
        if kind == "speech":
            return _norm(element.get("text"))
        if kind == "communication":
            return _norm("%s %s" % (element.get("act") or "",
                                    element.get("content") or ""))
        if kind == "event":
            return _norm(element.get("description"))
        return _norm(element.get("observable") or element.get("attempt"))

    def _key(element):
        targets = sorted(str(t or "").strip().casefold()
                         for t in (element.get("targets") or []))
        return (str(element.get("type") or "action"), _content(element),
                tuple(targets), str(element.get("stage") or ""),
                str(element.get("phase") or ""),
                # Identical words at different causal moments are distinct
                # events: close, reopen, close must retain both closes.
                str(element.get("chrono_id") or ""))

    def _words(text):
        words = re.sub(r"[^\w\s]", " ", str(text or "")).lower().split()
        return {w for w in words if w not in _ling("_OVERLAP_STOPWORDS")}

    seen, kept, redirect = {}, [], {}
    for index, element in enumerate(rows):
        key = _key(element)
        survivor = seen.get(key)
        if survivor is None and asserted is not None and index >= asserted \
                and not element.get("chrono_id") \
                and str(element.get("type") or "action") == "action":
            mine = _words(element.get("observable") or element.get("attempt"))
            if len(mine) >= 3:
                for earlier in kept:
                    if str(earlier.get("type") or "action") != "action":
                        continue
                    theirs = _words(earlier.get("observable")
                                    or earlier.get("attempt"))
                    if len(theirs) >= 3 and (
                            len(mine & theirs) / min(len(mine), len(theirs))
                            >= 0.8):
                        survivor = earlier
                        break
        if survivor is None:
            seen[key] = element
            kept.append(element)
            continue
        for field in ("event_id", "phase_id"):
            dropped_id = str(element.get(field) or "")
            if dropped_id:
                redirect[dropped_id] = str(survivor.get(field) or "")
        if warn is not None:
            warn("dropped a restatement of an already declared act: %r"
                 % (_content(element)[:80],))
    if redirect:
        for element in kept:
            deps = element.get("depends_on")
            if isinstance(deps, list):
                element["depends_on"] = [
                    redirect.get(str(d), d) for d in deps
                    if redirect.get(str(d), d)]
    return kept


def _dedupe_promoted_actions(clean):
    """Drop a promoted action the character ALSO declared properly.

    The live failure mode narrated one act twice in a single paragraph: once
    through a real action element and once through the copy smuggled into the
    speech. The two spellings are almost never identical -- "sets a hand on her
    shoulder" against "sets a hand FLAT on her shoulder" -- so the comparison is
    content-word overlap rather than containment, measured against the SHORTER
    of the two so a long elaboration still matches the short declaration it
    elaborates.

    Deliberately not fuzzier than that. A false match silently drops conduct
    the character declared, which is the failure this whole path exists to
    prevent; a false miss only costs a duplicated beat the narrator can merge.
    """
    def _content(text):
        words = re.sub(r"[^\w\s]", " ", str(text or "")).lower().split()
        # Function words carry no evidence that two descriptions name the same act --
        # "on her" appears in every second stage direction -- so they are excluded
        # before the overlap in _dedupe_promoted_actions is measured.
        return {w for w in words if w not in _ling("_OVERLAP_STOPWORDS")}

    declared = [_content(e.get("observable") or e.get("attempt"))
                for e in clean
                if e.get("type") == "action" and not e.get("_promoted")]
    declared = [d for d in declared if len(d) >= 3]
    kept = []
    for e in clean:
        if e.get("type") == "action" and e.get("_promoted"):
            mine = _content(e.get("attempt"))
            if len(mine) >= 3 and any(
                    len(mine & d) / min(len(mine), len(d)) >= 0.8
                    for d in declared):
                continue
        kept.append(e)
    return kept


# Below this, a line has nothing to cut. "Wait." interrupted is still "Wait."
# -- truncating it produces "Wait.—", which reads as a typo, and fictionally
# there is no room to get inside a one-word line anyway.
_MIN_INTERRUPTIBLE_WORDS = 5


def cut_short_speech(text, ratio=0.6):
    """A spoken line as it lands when somebody cuts in, or None to leave it.

    Returning None rather than a shortened string is the important half: a
    short line, or one the speaker already trailed off, is delivered WHOLE and
    the interrupting beat simply follows it. Forcing a cut on everything is
    what makes an interruption mechanic read as a bug.

    Where the cut falls was chosen by reading the output rather than by
    picking a number. A flat halfway cut lands mid-phrase ("the shipment
    left—"); stopping at a breath point lands where a person actually gets cut
    off ("the shipment left on Tuesday—"). So: keep whole sentences, cut the
    final one near `ratio`, and slide that cut to the nearest comma or
    conjunction within a couple of words.

    The em dash replaces whatever punctuation it lands on, because "to do,—"
    and "hearth.—" are both wrong and the dash is doing that job now.
    """
    body = " ".join(str(text or "").split())
    if not body:
        return None
    # Already trailed off -- the writer has done this themselves.
    if body.endswith(("—", "–", "-", "...", "…")):
        return None
    if len(body.split()) < _MIN_INTERRUPTIBLE_WORDS:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", body)
    head, tail = sentences[:-1], sentences[-1]
    words = tail.split()
    if len(words) < 3 and head:
        kept = words
    else:
        target = max(1, int(len(words) * ratio))
        keep = target
        for index in range(max(1, target - 2), min(len(words), target + 3)):
            if words[index - 1].endswith(","):
                keep = index
                break
            # Words a sentence leans on rather than lands on. An interruption arrives where
            # the speaker drew breath, and the breath is taken just before one of these or
            # just after a comma -- not at an arbitrary word count.
            if words[index].lower().strip(",;:") in _ling("_BREATH_CONJUNCTIONS"):
                keep = index
                break
            if words[index - 1].lower().strip(",;:") in _ling("_BREATH_CONJUNCTIONS"):
                keep = max(1, index - 1)
                break
        kept = words[:keep]
    joined = " ".join(head + [" ".join(kept)]) if head else " ".join(kept)
    return re.sub(r"[.,;:!?\s—–-]+$", "", joined) + "—"


#: The fields that make a sequence element a WORK ITEM rather than a
#: description of one: which ledger family it lands in, how the Director wants
#: it settled, and which numbered things of the beat it concerns. Everything
#: else about a span is the engine's (`DESIGN_SPECIALIST_CONTRACT.md` 4a) --
#: the id is assigned, the order is the order it was written in.
#:
#: THIS LIST IS THE SINGLE POINT OF FAILURE for anything the Director writes
#: onto a sequence element. `norm_sequence` rebuilds each element from a fixed
#: set of keys, so a field added anywhere else and not added here is dropped
#: between the model and every reader, silently. That has now cost three
#: fields in one day: `category` and `note` (no work item reached any hand at
#: all), then `items`.
#: What survives normalization onto the built element, because `norm_sequence`
#: rebuilds every element from a fixed key set and anything not named here is
#: dropped on the floor.
#:
#: THE CAUSAL HALF WAS MISSING AND IT COST THE WHOLE INTERPRET FAN-OUT.
#: `item_id` is the join `compile_transforms` needs, and a transform arriving
#: without one is REJECTED ("missing item_id") -- so with the id stripped
#: here, every specialist transform at the interpret stage was discarded by
#: the engine that asked for it. Measured live 2026-09-12: the spatial hand
#: answered a beat and its answer was thrown away, and the objects hand ran on
#: a belt taken off and dropped, with no `object_name` to match and no id to
#: return under, leaving the belt in no ledger anywhere. Resolve was unharmed
#: because its sequence never passes through here.
#:
#: `categories` rides along beside the folded `category` because a span may
#: name two ledgers and only the list says so; keeping just the singular one
#: silently halves the multi-hand routing this contract is built on.
#:
#: `item_ids` and `item_names` are the lists the singular pair became
#: (the owner's contract, 2026-09-15). Measured before they were added
#: here, chat 12 turn 190: every interpret span reached the hands with the
#: lists gone, so the per-thing accounting saw one-thing rows everywhere
#: and a three-thing row's silence about two of them went unrecorded --
#: the exact failure the accounting was built to see.
SPAN_FIELDS = ("category", "categories", "note", "items",
               "chrono_id", "item_id", "item_ids", "item_names",
               "object_name", "act",
               "source_entity_id", "actor", "from_declaration", "movement",
               # A fact about how things stand, not conduct
               # (`UnifiedEvent.standing`): the interpret stage keeps its
               # writes and leaves the row out of the player's sequence.
               "standing")


def _restore_span_fields(source, clean, before):
    """Carry the span's own fields from a raw element onto the built one.

    Only the LAST element built from `source`, and only when the arm built
    anything. The speech arm emits promoted stage directions FIRST and the
    speech itself last, and a promoted direction is an act the Director never
    categorized -- inheriting the category would hand a hand a span that was
    never written.

    `category` is passed through unfolded, list or string alike: normalizing it
    is `director_evidence._span_items`' job and doing it in two places is how
    the two spellings drift.
    """
    if len(clean) <= before:
        return
    built = clean[-1]
    for field in SPAN_FIELDS:
        value = source.get(field)
        if value in (None, "", [], {}):
            continue
        built[field] = value


#: WHICH STEP OF A CHARACTER'S REPLY AN ELEMENT CAME FROM: `compile_bare`
#: marks each line and act with its index in the reply, so a tell the
#: read-back placed at one of them can be found again once the ids are
#: stamped (`character_bare.anchor_tells`, which takes the marks off). A
#: private mark, carried through normalization and read by nothing here.
STEP_MARK = "_step"


def _carry_step_mark(source, clean, before):
    """Every element built from `source` carries its step mark -- a stage
    direction promoted out of a line belongs to the step it was written in,
    which `_restore_span_fields` (the last element only) would not say."""
    if STEP_MARK not in source:
        return
    for built in clean[before:]:
        built[STEP_MARK] = source[STEP_MARK]


def _unnest_spoken(seq, warn=None):
    """`seq` with every speech element whose `text` holds elements rather than
    words flattened into the elements it holds.

    A LINE IS WORDS. The character agent (GLM 5.2, the owner's chat 137 idx
    46, 2026-09-23) wrote each of Mirelle's lines as an element nested inside
    its own field -- `{"type": "speech", "text": {"text": "There you are. ...",
    "tone": ..., "volume": "soft", ...}}` -- and `str()` of it went down the
    acoustic channel: fused with the next line into two Python reprs, it was
    what she said in the player's view, in her own memory of saying it, and
    on the page (`"{'text': ..."`). The keys are the engine's own schema, so
    the shape is structural: a `text` that is an element IS that element,
    its delivery filling only what the outer one left unsaid; a `text` that
    is a list is that many lines, in order. A nested element without `text`
    carries no words the engine can find, and is dropped and said."""
    flat, lifted, lost = [], 0, 0
    for element in seq:
        if not isinstance(element, dict):
            flat.append(element)
            continue
        words = element.get("text") or element.get("speech")
        kind = element.get("type") or ("speech" if words else "action")
        if kind != "speech" or not isinstance(words, (dict, list, tuple)):
            flat.append(element)
            continue
        parts = _spoken_parts(element, 0)
        lifted += 1
        lost += sum(1 for part in parts if not str(part.get("text") or "").strip())
        flat.extend(part for part in parts if str(part.get("text") or "").strip())
    if lifted and warn:
        warn(f"{lifted} spoken element(s) carried elements inside their own "
             "text; their words were lifted out"
             + (f", and {lost} nested element(s) with no words were dropped"
                if lost else ""))
    return flat


def _spoken_parts(element, depth):
    """The flat speech elements one speech element holds, in order."""
    words = element.get("text") or element.get("speech")
    if not isinstance(words, (dict, list, tuple)) or depth > 3:
        flat = {k: v for k, v in element.items() if k != "speech"}
        flat.update(type="speech", text=(
            "" if isinstance(words, (dict, list, tuple)) or words is None
            else str(words)))
        return [flat]
    outer = {k: v for k, v in element.items()
             if k not in ("text", "speech") and v not in (None, "", [], {})}
    parts = []
    for part in (words if isinstance(words, (list, tuple)) else [words]):
        if isinstance(part, dict):
            inner = {k: v for k, v in part.items() if k != "speech"}
            if not inner.get("text") and part.get("speech"):
                inner["text"] = part["speech"]
            parts.extend(_spoken_parts({**inner, **outer}, depth + 1))
        else:
            parts.append({**outer, "type": "speech",
                          "text": "" if part is None else str(part)})
    return parts


def norm_sequence(out, warn=None):
    seq = out.get("sequence")
    if not isinstance(seq, list) or not seq:
        seq = []
        if out.get("speech"):
            seq.append({
                "type": "speech",
                "text": out["speech"],
                "volume": normalize_speech_volume(
                    out.get("speech_volume")
                ),
            })
    acts = out.get("actions")
    if not isinstance(acts, list):
        acts = [out["action"]] if out.get("action") else []
    for a in acts:
        if isinstance(a, dict):
            seq.append({"type": "action", **a})
    seq = _unnest_spoken(seq, warn)
    clean = []
    for e in seq:
        if not isinstance(e, dict):
            continue
        # WHERE THE ELEMENT STOOD BEFORE THIS ARM RAN, so the span's own two
        # fields can be restored onto whatever the arm built from it. See
        # `_restore_span_fields`.
        _before = len(clean)
        t = e.get("type") or (
            "speech" if (e.get("text") or e.get("speech")) else "action"
        )
        if t == "speech":
            txt = e.get("text") or e.get("speech")
            if txt:
                # Conduct written into the spoken line comes out FIRST and
                # becomes its own action, placed immediately before the speech
                # it was buried in. See split_stage_directions: leaving it in
                # `text` routes a body movement down the acoustic channel.
                txt, _stage_spans = split_stage_directions(str(txt))
                for _span in _stage_spans:
                    clean.append(_promoted_stage_action(_span, e))
                    if warn:
                        warn("moved a stage direction out of spoken text into "
                             "its own action: '%s'" % _span[:80])
                        if not clean[-1]["observable"]:
                            warn("classified as interior, so no perceiver "
                                 "receives it: %r" % _span[:120])
            if txt:
                # Carry the speech element's OWN concealment through
                # normalization. Dropping it here (as we used to) meant a
                # line the director explicitly marked visibility:'concealed'
                # was re-emitted as overt, so perception_act's onset delivery
                # -- which reads visibility/conceal_from straight off these
                # normalized speech elements -- leaked the private words to
                # every in-range perceiver, including whoever it was
                # concealed from. See tests/test_speech_concealment.py.
                clean.append({
                    "type": "speech",
                    "text": str(txt),
                    "volume": normalize_speech_volume(e.get("volume")),
                    "tone": e.get("tone", ""),
                    # THE FEELING IN THE VOICE, typed (`schemas.VOCAL_AFFECTS`),
                    # or "". This arm rebuilds a spoken element from a fixed
                    # key list, and at interpret it runs AFTER the encoder's
                    # rows were projected (`director.director_interpret`), so a
                    # field missing here is dropped from the player's own
                    # line before the dialogue log is minted -- the way
                    # `intended_target` is, which survives only as
                    # `targets[0]`.
                    "vocal_affect": normalize_vocal_affect(e.get("vocal_affect")),
                    # Who this lands on top of, if the character declared it as
                    # cutting somebody off. Resolved deterministically in the
                    # interaction loop against who has actually spoken this
                    # beat -- a name here is a claim, not an outcome.
                    "interrupts": str(e.get("interrupts") or "").strip(),
                    "visibility": "concealed" if e.get("visibility") == "concealed" else "overt",
                    "conceal_from": e.get("conceal_from") or [],
                    "targets": e.get("targets") or [],
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                    # raw (pre-normalization) signals, consumed by the
                    # concealment backstop below and stripped before return.
                    "_raw_vis": e.get("visibility"),
                    "_raw_vol": e.get("volume"),
                })
        elif t in _COMMUNICATIVE_TYPES:
            content = e.get("content") or e.get("topic") or e.get("meaning")
            if content:
                targets = e.get("targets") or e.get("target") or []
                if not isinstance(targets, list):
                    targets = [targets]
                clean.append({
                    "type": "communication",
                    "act": str(e.get("act") or e.get("kind") or "say"),
                    "content": " ".join(str(content).split()),
                    "targets": targets,
                    "volume": normalize_speech_volume(e.get("volume")),
                    "tone": str(e.get("tone") or ""),
                    "visibility": ("concealed" if
                                   e.get("visibility") == "concealed"
                                   else "overt"),
                    "conceal_from": e.get("conceal_from") or [],
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                })
        elif t == "ponder":
            # Private cognitive action. It never enters the public sequence,
            # Director resolution, perception, or narration. Commit stores one
            # bounded query for the next character turn.
            query = " ".join(str(e.get("query") or "").split())[:240]
            why = " ".join(str(e.get("why") or "").split())[:240]
            if query and why:
                out["ponder"] = {
                    "type": "ponder", "query": query, "why": why}
            elif (query or why) and warn:
                # A ponder is by design not in the public sequence, so nothing
                # downstream can notice it went missing -- there is no view, no
                # percept and no prose it would have shown up in. Dropping half
                # of one silently is the same failure shape as blanking an act.
                warn("dropped a ponder missing its %s: %r"
                     % ("why" if query else "query", (query or why)[:80]))
        elif t in ("event", "environment", "environmental", "world"):
            # Actor-less environmental event ("the lights go out", "a
            # monster enters") declared by the player. These used to be
            # silently DROPPED here (only speech/action survived), so a
            # player world assertion never reached the resolve at all.
            # First-class representation, canonical type "event".
            description = (e.get("description") or e.get("text")
                           or e.get("attempt"))
            if description:
                raw_asserted = e.get("asserted_effects") or []
                asserted_effects = [
                    _normalize_effect(eff)
                    for eff in raw_asserted
                    if _normalize_effect(eff) is not None
                ]
                clean.append({
                    "type": "event",
                    "description": str(description),
                    "subject": str(e.get("subject") or ""),
                    "raw_text": e.get("raw_text") or "",
                    "visibility": "concealed"
                    if e.get("visibility") == "concealed" else "overt",
                    "conceal_from": e.get("conceal_from") or [],
                    "commitment": e.get("commitment") or "asserted",
                    "asserted_effects": asserted_effects,
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                    "requires_contacts": [dict(x) for x in
                                          e.get("requires_contacts") or []
                                          if isinstance(x, dict)],
                    "referents": [dict(x) for x in e.get("referents") or []
                                  if isinstance(x, dict)],
                })
        else:
            att = e.get("attempt")
            if att:
                tg = e.get("targets") or e.get("target") or []
                if not isinstance(tg, list):
                    tg = [tg]
                commitment = e.get("commitment")
                if commitment is None:
                    commitment = _classify_action_commitment(
                        e.get("raw_text") or att
                    )
                raw_intended = e.get("intended_effects") or []
                raw_asserted = e.get("asserted_effects") or []
                intended_effects = [
                    _normalize_effect(eff)
                    for eff in raw_intended
                    if _normalize_effect(eff) is not None
                ]
                asserted_effects = [
                    _normalize_effect(eff)
                    for eff in raw_asserted
                    if _normalize_effect(eff) is not None
                ]
                # The intent-free OUTWARD surface handed to other perceivers
                # (see observable_action_text). `attempt` is the actor's own
                # framing and routinely embeds purpose/magic-intent ("scratch
                # runes of slow and soften", "channel divine heritage") or
                # pure cognition ("remember the rune crafting") -- copying it
                # into an observer's view leaks meaning the perception filter
                # exists to strip. Prefer the director-authored `observable`;
                # default a mental act to "" (imperceptible -> skipped) and a
                # physical act with no authored surface to `attempt` (no
                # delivery regression for un-migrated / plain physical acts).
                observable = e.get("observable")
                if observable is None:
                    if _is_mental_action(e.get("verb"), att):
                        observable = ""
                        # SAY SO. Blanking is a decision that nobody will ever
                        # perceive this act -- it is skipped by every delivery
                        # site, so there is no view, no percept and no memory
                        # to notice it by, and the only trace left behind is an
                        # empty string in a stored variant.
                        if warn:
                            warn("classified as interior, so no perceiver "
                                 "receives it: %r" % att[:120])
                    else:
                        observable = att
                clean.append({
                    "type": "action",
                    "attempt": att,
                    "observable": str(observable),
                    # A blow, a hand over a mouth, a grab -- conduct cuts a line
                    # off exactly as a louder voice does.
                    "interrupts": str(e.get("interrupts") or "").strip(),
                    "visibility": e.get("visibility", "overt"),
                    "conceal_from": e.get("conceal_from") or [],
                    "targets": tg,
                    "commitment": commitment,
                    "verb": e.get("verb", ""),
                    "stage": e.get("stage", "immediate"),
                    # WHERE THE ACT LOOKS OR TURNS: carried through, so the
                    # commit can set the facing from it. The first live
                    # `look: around` was written by the model, kept by the
                    # ledger, and lost here (2026-09-15).
                    "look": str(e.get("look") or "").strip(),
                    # The bare card's act, written without a subject: carried
                    # so the mind's memory of it names its doer (2026-09-30;
                    # lost here, "I tried to picks up the card").
                    **({"subjectless": True} if e.get("subjectless") else {}),
                    "intended_effects": intended_effects,
                    "asserted_effects": asserted_effects,
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                    "requires_contacts": [dict(x) for x in
                                          e.get("requires_contacts") or []
                                          if isinstance(x, dict)],
                    "referents": [dict(x) for x in e.get("referents") or []
                                  if isinstance(x, dict)],
                })
        _restore_span_fields(e, clean, _before)
        _carry_step_mark(e, clean, _before)
    # A promoted stage direction the character also declared as a real action
    # is the same act twice, and the narrator rendered both.
    clean = _dedupe_promoted_actions(clean)
    clean = collapse_duplicate_events(clean, warn=warn)
    # Deterministic concealment backstop (leak-safe). A hushed or unmarked
    # line co-declared with a concealed action is almost always the private
    # communication itself; weak models routinely mark the ACTION concealed
    # (e.g. "open a private channel", "whisper an aside") but leave the SPEECH
    # overt, which would leak the words to everyone in range. So: for every
    # speech element that is not EXPLICITLY public, propagate the union of all
    # concealed actions' conceal_from onto it. "Explicitly public" = the model
    # set an explicit overt visibility, or an explicit loud/shout volume. We
    # never override a speech the model already marked concealed, and we
    # subtract the concealing actions' own targets so the intended addressee
    # is never made deaf. Over-concealment only costs marginal eavesdroppers
    # (the addressee still hears); a leak is irreversible.
    #
    # THAT LAST PARENTHESIS HOLDS ONLY ON THIS PATH, and the case it does not
    # cover was live for four stored beats. Here the addressee is recovered
    # from the concealing ACTION's `targets`, which is why over-concealing is
    # safe; but when the model writes the addressee into the SPEECH's own
    # explicit `conceal_from`, the skip on the next line preserves it verbatim
    # and nothing subtracts anything -- the addressee is made deaf by the
    # field that was supposed to protect them. It cannot be fixed here:
    # `targets` carries a NAME and `conceal_from` carries a cast ID, and this
    # function never sees `flow.addressed_to`, the one place both encodings of
    # the audience exist. `schemas._uncross_concealed_speech` does it there.
    concealed_from_union, conceal_targets = [], []
    for e in clean:
        if e["type"] in ("action", "communication") \
                and e.get("visibility") == "concealed":
            for cf in e.get("conceal_from") or []:
                if cf not in concealed_from_union:
                    concealed_from_union.append(cf)
            for tg in e.get("targets") or []:
                if tg not in conceal_targets:
                    conceal_targets.append(tg)
    propagate = [cf for cf in concealed_from_union if cf not in conceal_targets]
    if propagate:
        for e in clean:
            if e["type"] not in ("speech", "communication") \
                    or e.get("visibility") == "concealed":
                continue
            explicitly_public = (e.get("_raw_vis") == "overt") or (e.get("_raw_vol") in ("loud", "shout"))
            if explicitly_public:
                continue
            e["visibility"] = "concealed"
            e["conceal_from"] = list(propagate)
    for e in clean:
        e.pop("_raw_vis", None)
        e.pop("_raw_vol", None)
        e.pop("_promoted", None)

    out["sequence"] = clean
    return _sync_sequence_mirrors(out)

def player_communicated(interpreted):
    """True when the player's beat carried an utterance to somebody -- spoken
    or otherwise -- and False when it did not.

    ONE ANSWER TO "DID THE PLAYER SPEAK THIS BEAT" (review 2026-09-07 A44).
    The scalar `speech` mirror is derived from `type == "speech"` elements
    alone (`_sync_sequence_mirrors`), so every reader that asked it a
    yes/no question was answering a narrower one: a player who signed, wrote,
    gestured a meaning or spoke down a radio emits a `communication` element
    and no `speech`, and `character._player_silence_note` then told every
    mind in the room that they had stood there saying nothing -- while
    `_unanswered_question_note` and `narration._narrator_player_declared`,
    reading the same beat off the sequence, already counted it as speaking.
    Two readings of one fact, and the silence note was the wrong one.

    THREE READERS, ONE ANSWER. `_narrator_player_declared` kept a third
    reading until it too was routed here: its own walk said True on a speech
    element carrying no text and on a whitespace-only `speech` mirror, so a
    beat could reach the narrator marked as spoken while every mind in the
    room was told it was silent. It keeps its loop -- it is building the
    sequence the narrator renders, which is a different job -- and asks this
    for the yes/no.

    The class is the utterance, not the mouth: what makes this true is that
    the beat put something to somebody, whatever channel carried it. The
    scalar is the fallback and nothing more -- it answers for a stored beat
    from before the sequence existed, where it is the only record there is.
    """
    interpreted = interpreted if isinstance(interpreted, dict) else {}
    for event in interpreted.get("sequence") or []:
        if not isinstance(event, dict):
            continue
        if event.get("type") not in ("speech", "communication"):
            continue
        if str(event.get("text") or event.get("content") or "").strip():
            return True
    return bool(str(interpreted.get("speech") or "").strip())


def _sync_sequence_mirrors(out):
    """Recompute the legacy scalar mirrors (speech/speech_volume/action/
    actions) from out['sequence']. Factored out of norm_sequence so the
    interpret-reconciliation seam can re-sync after additively appending
    repaired elements WITHOUT re-running norm_sequence on the whole output
    (which would re-append out['actions'] and duplicate every action)."""
    clean = out.get("sequence") or []
    sp = [e for e in clean if e.get("type") == "speech"]
    ac = [e for e in clean if e.get("type") == "action"]
    out["speech"] = sp[0]["text"] if sp else None
    out["speech_volume"] = (
        sp[0]["volume"] if sp else out.get("speech_volume", "normal")
    )
    out["action"] = (
        {
            "attempt": ac[0]["attempt"],
            "visibility": ac[0]["visibility"],
            "conceal_from": ac[0]["conceal_from"],
            "targets": ac[0]["targets"],
            "commitment": ac[0].get("commitment", "contestable"),
        }
        if ac
        else None
    )
    out["actions"] = ac
    return out


#: What two spoken elements must agree on before they can be ONE delivery.
#: Every field here answers a question about DELIVERY -- who may hear it, how
#: loudly, at whom it is aimed, and which phase of a staged act it belongs to
#: -- so two elements that disagree on any of them are two deliveries however
#: adjacent they sit, and stay two. Tone is deliberately absent: a voice
#: shifts register inside one turn at talk, and a change of register is not a
#: change of delivery.
_DELIVERY_KEYS = ("volume", "visibility", "conceal_from", "targets",
                  "phase", "phase_id", "depends_on", "participants")


def _delivery_signature(element):
    return tuple(
        tuple(element.get(key) or ()) if key in (
            "conceal_from", "targets", "depends_on", "participants")
        else str(element.get(key) or "")
        for key in _DELIVERY_KEYS
    )


def fuse_speech_run(out, warn=None):
    """CONSECUTIVE LINES ONE MOUTH SPEAKS WITH NOTHING BETWEEN THEM ARE ONE
    UTTERANCE.

    The speech budget's own contract already says this. It defines a line as
    "one separate beat of talk, delivered between other conduct" and states
    outright that "multiple lines are not one speech split by punctuation:
    they are separate utterances". A run of `{type: "speech"}` elements with
    no conduct between them is exactly the thing that contract forbids -- one
    turn at talk, split at its full stops -- and nothing enforced it, so the
    engine carried the split all the way to the page.

    IT IS THE PAGE THAT PAYS. Each element becomes its own `dialogue_log`
    entry, its own `speech_percept`, its own "X says in a Y voice: ..."
    sentence in every view, and the narrator sets what the view hands it: N
    quoted lines from one mouth, back to back, with no narration or
    attribution between them. Measured over the 38 stored beats of chat 98:
    26 of the 51 rounds that spoke at all emitted two or three speech
    elements, and one beat (turn 29) put SIX quoted lines from one mouth on
    the page in two rounds of three. The same split also repeats the
    attribution, which is where "his voice was measured / formal, precise /
    formal, declarative" inside one beat comes from.

    So the engine states the rule deterministically instead of asking. This
    SUBTRACTS: it merges deliveries, invents no words, drops none, and can
    only ever reduce the number of separate lines attributed to a mouth. Two
    elements fuse only when they agree on every DELIVERY attribute
    (`_DELIVERY_KEYS`) and the later one claims no interruption -- a whisper
    inside a spoken turn, an aside concealed from one party, or a line that
    cuts into somebody is a genuinely separate delivery and keeps its
    boundary. The fused element keeps the first's tone when the run agrees on
    one and drops it when the run does not, because no single adverbial is
    true of a delivery that changed register.

    A run separated by ANY other element -- an action, a mental beat, a
    communication -- is untouched: conduct between two lines is precisely what
    makes them two beats of talk, and that is the shape the budget is asking
    for.
    """
    sequence = out.get("sequence")
    if not isinstance(sequence, list) or len(sequence) < 2:
        return out
    fused, joined = [], 0
    for element in sequence:
        last = fused[-1] if fused else None
        if (isinstance(element, dict)
                and element.get("type") == "speech"
                and isinstance(last, dict)
                and last.get("type") == "speech"
                and not str(element.get("interrupts") or "").strip()
                and _delivery_signature(last) == _delivery_signature(element)):
            head = str(last.get("text") or "").strip()
            tail = str(element.get("text") or "").strip()
            if tail:
                last["text"] = (head + " " + tail).strip() if head else tail
                if str(last.get("tone") or "") != str(element.get("tone") or ""):
                    last["tone"] = ""
                joined += 1
            continue
        fused.append(dict(element) if isinstance(element, dict) else element)
    if joined and warn:
        warn(f"fused {joined} spoken line{'s' if joined > 1 else ''} into the "
             "utterance before it -- separate lines are separate beats of "
             "talk, delivered between other conduct")
    out["sequence"] = fused
    return _sync_sequence_mirrors(out) if joined else out


def _next_event_index(earlier, prefix):
    """The first `<prefix>:<n>` number no element of `earlier` already holds."""
    head = f"{prefix}:"
    used = -1
    for element in earlier or ():
        if not isinstance(element, dict):
            continue
        event_id = str(element.get("event_id") or "")
        if not event_id.startswith(head):
            continue
        number = event_id[len(head):].split(":", 1)[0]
        if number.isdigit():
            used = max(used, int(number))
    return used + 1


def assign_event_ids(sequence, prefix, earlier=None):
    """Stamp each declared element `<prefix>:<n>:<type>`.

    ONE ID NAMES ONE DECLARATION IN THE BEAT. Every join downstream is keyed
    on it -- the resolve's citation (`from_declaration` through
    `director_evidence.declared_elements`, first id wins), perception's
    outcome stream (`seen_events`), the world ledger's order
    (`beat_ledger.beat_event_order`) -- so two elements under one id are one
    element to all of them. `earlier` is what the same mouth already declared
    under the same prefix this beat, and the numbering continues past it.

    A mouth declares more than once in a beat when the interaction loop gives
    it a second micro-round, and the prefix (turn, mouth) is the same both
    times. Numbered from 0 each round, the rounds collided: scratch story
    166, turn 4610, Abel Gale's round-0 and round-2 lines were all
    `turn:4610:character:83:{0,1,2}:speech`, the resolve bound round 2's
    lines to round 0's declarations, and his declared LOUD "Hester -- stay
    on the walk" ("louder, meant to carry down the stair") reached the log
    and the player's view as a mutter in round 0's tone.
    """
    start = _next_event_index(earlier, prefix)
    result = []
    for offset, raw in enumerate(sequence or []):
        event = dict(raw)
        event.setdefault(
            "event_id",
            f"{prefix}:{start + offset}:{event.get('type', 'event')}")
        result.append(event)
    return result

def _stable_event_key(*parts):
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"event:{digest}"

def _lore_fingerprint(entry):
    keys = re.sub(r"\s+", " ", str(entry.get("keys") or "").strip().casefold())
    content = re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold())
    digest = hashlib.sha256(f"{keys}\x1f{content}".encode("utf-8")).hexdigest()
    return f"content:{digest}"

# Narration ABOUT an utterance, as opposed to the utterance. A player writes
# their own beat in second person ("you gently take her by the wrist"), so a speech
# text carrying `you`/`your` outside its quotes is prose the interpreter lifted
# whole rather than the line the player spoke. Attribution verbs are kept
# deliberately narrow -- `say`/`said` and friends, never `tell`/`told` -- so an
# ordinary spoken line that happens to quote someone ('He told me "get out" and
# I left.') is not mistaken for narration and gutted.


def repair_narrated_speech(text):
    """Reduce a speech text that swallowed its own narration to the words said.

    Observed live: `director_interpret` returned the player's ENTIRE raw input
    as a single speech element, stage directions included --

        '"Wait" You say it flatly, without turning around. "I am not going."'

    -- and perception injected it faithfully as dialogue. Two failures follow
    at once: the narration is delivered as spoken words, and because the lifted
    prose is in second person, the "You" now points at the LISTENER, who is
    told they said it.

    Fires only when the text holds at least one quoted span AND the residue
    outside those spans reads as narration (>=2 words, carrying a second-person
    pronoun or a speech-attribution verb). A wholly unquoted line -- the normal
    shape -- is returned untouched, as is a line that is nothing but its quote.
    Returns the input unchanged when it declines to act, so callers may assign
    the result unconditionally.
    """
    raw = str(text or "")
    if not raw.strip():
        return text
    segments = _ling("_QUOTED_SPAN_RE").split(raw)
    # split() alternates residue/span/residue...; odd indices are the spans.
    spans = [s for i, s in enumerate(segments) if i % 2 == 1]
    if not spans:
        return text
    residue = " ".join(s for i, s in enumerate(segments) if i % 2 == 0)
    if len(residue.split()) < 2 or not _ling("_SPEECH_NARRATION_RE").search(residue):
        return text
    bodies = [b for b in (_quote_body(s) for s in spans) if b]
    if not bodies:
        return text
    spoken = ""
    for body in bodies:
        if spoken and spoken[-1] not in ".!?,;:-—":
            spoken += "."
        spoken = f"{spoken} {body}" if spoken else body
    return spoken


def repair_narrated_speech_elements(out):
    """Apply `repair_narrated_speech` to one interpret result in place.

    Covers both representations -- the `sequence` speech elements and the flat
    `speech` mirror -- because downstream stages read whichever is present.
    Returns the list of (before, after) pairs it changed, for warning.
    """
    changed = []
    if not isinstance(out, dict):
        return changed
    causal_speech = False
    for element in (out.get("sequence") or []):
        if not isinstance(element, dict) or element.get("type") != "speech":
            continue
        if element.get("chrono_id") and element.get("source_entity_id"):
            # A causal speech span already contains the spoken words alone.
            # Re-running the old narration heuristic can turn a recollection
            # and refusal (Yesterday you said 'Break the lock', but I won't)
            # into the opposite instruction by keeping only its inner quote.
            causal_speech = True
            continue
        before = element.get("text")
        after = repair_narrated_speech(before)
        if after != before:
            element["text"] = after
            changed.append((before, after))
    before = out.get("speech")
    if before and not causal_speech:
        after = repair_narrated_speech(before)
        if after != before:
            out["speech"] = after
            if not any(b == before for b, _ in changed):
                changed.append((before, after))
    return changed


def substitute_player_token(obj, player_name):
    """Every `{{PLAYER}}` in a stage's output is the persona.

    The token marks the player's slot in greetings and in the establish
    example, and the model copies it: an opening wrote `positions:
    {"{{PLAYER}}": ...}`, the commit tracked "{{PLAYER}}" as a background
    presence with an open person need, and three beats later the resolve
    was addressing lines to "{{PLAYER}}" while the persona sat unbound (the
    owner's chat 125, 2026-09-14). Keys and string values alike, whole-value
    equality (case-insensitive) or the token inside a longer string; the
    structure is returned rebuilt, never mutated.
    """
    from story.importers import PLAYER_TOKEN
    name = str(player_name or "").strip()
    if not name:
        return obj
    token_cf = PLAYER_TOKEN.casefold()

    def fix(value):
        if isinstance(value, dict):
            return {fix(k): fix(v) for k, v in value.items()}
        if isinstance(value, list):
            return [fix(v) for v in value]
        if isinstance(value, str):
            if value.strip().casefold() == token_cf:
                return name
            if token_cf in value.casefold():
                return re.sub(re.escape(PLAYER_TOKEN), name, value,
                              flags=re.IGNORECASE)
        return value
    return fix(obj)


def player_speech_lines(interp):
    lines = [e.get("text") for e in (interp.get("sequence") or [])
             if e.get("type") == "speech" and e.get("text")]
    if not lines and interp.get("speech"):
        lines = [interp["speech"]]
    return lines
