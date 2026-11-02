"""What a composed view may say and how it is finished: the self-narration
strip and its quote-safe wrapper, the identity scrubs over act surfaces,
authored prose and episodes, the composer tripwires and the disguise
tripwire, the per-observer finish (repaired observations, company record,
ledger entry), and the retired prose-surgery helpers kept for replay and
tests.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from story.character_schema import name_boundary_regex
from world.spatial import hiding_holders_of, same_subject
from . import composer
from .common import (
    _player_name_forms,
    _sentence_subjects,
    _scrub_unknown_identities,
    _mask_quoted_spans,
    _unmask_quoted_spans,
    _VIEW_MASK,
    _scrub_invented_dialogue,
    split_sentences,
)

from agents.perception_common import (
    _SENTENCE_SPLIT,
    _learned_labels,
    _ling,
    _prior_ledger_entry,
    _standing_meta,
)
from agents.perception_identity import _composer_unknown_sources

#: How much of the text on either side of an offending fragment a diagnostic
#: carries. A GUARD'S MESSAGE HAS TO LOCATE ITS CAUSE. The self-narration
#: tripwire fired on live data (lighthouse turn 9, 2026-09-05), repaired the
#: view correctly, and printed `'Marrick...'` -- a fragment the sentence
#: splitter had already cut down to nothing findable, in a view of a thousand
#: characters. A warning nobody can act on is worse than no warning: it costs
#: attention and hides the ones that can be acted on.
_EXCERPT_CONTEXT_CHARS = 40


def _excerpt_in(text, fragment, context=_EXCERPT_CONTEXT_CHARS, cap=200):
    """``fragment`` with enough of ``text`` around it to find the sentence.

    Falls back to the fragment alone when the text does not contain it --
    the repair may have rewritten what it reports, and a bounded excerpt is
    still better than nothing.
    """
    text, fragment = str(text or ""), str(fragment or "")
    if not fragment:
        return ""
    at = text.find(fragment)
    if at < 0:
        return fragment[:cap]
    start, end = max(0, at - context), min(len(text), at + len(fragment) + context)
    return "%s%s%s" % ("..." if start else "", text[start:end],
                       "..." if end < len(text) else "")


def _strip_self_narration(view, perceiver_name, other_names=(), refusals=None):
    """Drop sentences that narrate the PERCEIVER from outside their own view.

    A view is what one mind receives. It may say "you" and it may describe
    anyone else; what it must never do is stand outside the perceiver and
    report them as a third party -- least of all their own face, which they
    cannot see.

    Live, alpha 6.3: Elyndra's own view read "Elyndra's gaze stays fixed on
    the shifting lump, her teasing smile faltering as she watches the genuine
    terror in that tiny trembling form", in a view that elsewhere said "You
    see Hinami." Both halves are wrong from her side -- she is not watching
    her own smile falter, and she cannot know another mind's terror is
    genuine. Tracing it: `director_resolve` had written "Elyndra's teasing
    smile falters completely at the shrill, panicked cry", and perception
    COPIED the omniscient sentence into her view rather than rendering the
    beat from her frame. Per-observer calls did not prevent it; each observer
    got its own call and this one simply echoed its input.

    Dropping the sentence rather than rewriting it, and dropping only whole
    sentences whose SUBJECT is the perceiver: the rest of the view is
    untouched and still coherent, and no prose is invented to replace what
    goes.

    Subject resolution is pronoun-continuation-aware (`_sentence_subjects`),
    which is how the live case was found. Chat 56 ("Run!") t6, in the PLAYER's
    own view: "She feels her arms still wrapped tightly, her breathing slowing,
    the terror in her eyes beginning to recede." Third person, about the
    perceiver, in a view addressed to them -- the Director's omniscient
    sentence copied through whole, exactly the shape this guard exists to
    catch, and invisible to it because the subject was written as "She". An
    unanchored pronoun still binds to nobody rather than to a guess, so a view
    that never names the perceiver is left alone.

    Both floors below REFUSE to drop rather than dropping less, and a refusal
    is a view knowingly delivered with self-narration still in it. Pass a list
    as `refusals` to hear about it; the default of None keeps the two-tuple
    contract every existing caller and test relies on.
    """
    if not view or not perceiver_name:
        return view, []
    forms = _player_name_forms(perceiver_name)
    if not forms:
        return view, []
    names = [perceiver_name] + [
        n for n in (other_names or []) if n and n != perceiver_name]
    kept, dropped = [], []
    # A closing quote may sit between the terminal punctuation and the space
    # ('...to me!?" The voice is...'), and a naive lookbehind cannot split
    # there -- which silently made a whole passage one "sentence" and let this
    # guard pass everything.
    for stripped, subject in _sentence_subjects(
            str(view), names, split=_SENTENCE_SPLIT):
        if not stripped:
            continue
        if subject == perceiver_name:
            dropped.append(stripped)
        else:
            kept.append(stripped)
    if not dropped:
        return view, []
    # Never empty a view entirely: a perceiver who received something must be
    # told something. If every sentence named them, the view is beyond repair
    # by deletion and is left alone for the refusal to carry.
    if not kept:
        if refusals is not None:
            refusals.append(
                "every sentence named the perceiver, so the view is beyond "
                "repair by deletion and was delivered as written")
        return view, []
    # Never take a perceiver's eyes off the beat either. A view written wholly
    # from outside its own perceiver puts them in the subject slot of exactly
    # the sentences carrying what they SAW -- "The Doctor watches her run
    # across the gravel and throw her arms around the kitsune" -- so a
    # subject-anchored drop removes the framing error and the observation
    # together, and the sentences left standing are the ones about the weather.
    #
    # Live (chat 38, t140): the Doctor stood at the genkan, six feet from an
    # embrace the resolved event says he was watching with bright interest, in
    # a lit-enough room with `shapes` sight to both bodies. Perception wrote
    # his view in the third person, this guard dropped both sight sentences,
    # and his view, his structured observations and his committed memory of
    # that beat all came out sound-only -- a permanent hole in what that mind
    # knows, from a framing slip.
    #
    # The two failures are not equal. Over-denial is the worse one: silence
    # about something a mind plainly perceived is its own lie, and it is
    # invisible afterwards. Being told about yourself in the third person for
    # one beat is bounded and visible; losing what you saw is neither. So when
    # the drop would leave a view with no assertion of sight in it at all, the
    # view stands and the warning carries it.
    #
    # Narrow on purpose: it keys on the verbs a view actually uses to assert
    # sight, so it is a floor under this specific loss and NOT a general
    # promise that nothing informative is ever dropped (a view phrasing sight
    # as "visual sensors pick up" is still dropped whole -- see
    # test_a_body_named_with_an_article_is_caught_under_another_article).
    _sight = _ling("_SIGHT_ASSERTION")
    if (any(_sight.search(s) for s in dropped)
            and not any(_sight.search(s) for s in kept)):
        if refusals is not None:
            refusals.append(
                "dropping self-narration would have left this view with no "
                "sight in it at all, so it was delivered as written: "
                + "; ".join(_excerpt_in(view, s) for s in dropped))
        return view, []
    return " ".join(kept), dropped


# Vertical motion, and nothing else. A beat can legitimately open and close a
# door, or have one body approach while another retreats, so most antonym pairs
# generate false positives -- but a hand cannot rise and descend in the same
# instant, and that is the one that bit. Deliberately narrow: this is a
# tripwire, and a tripwire nobody trusts gets ignored.
# In the ACTIVE PACK (`agents.perception._RAISING` / `._LOWERING`): a tripwire
# written in one language is a tripwire that fires in one language, and the
# story it was measured on is not the only story.


def _inverted_motion_check(ctx, stage, views, resolved_event):
    """Flag a view that reverses a physical direction the Director resolved.

    Perception's structured observations are re-derived from the scrubbed prose
    view precisely so a second representation cannot widen the information
    budget -- but nothing checks the PROSE against the objective event it is
    supposed to be a view of. A model that rewrites the beat is invisible.

    Measured on chat 52's last beat. Elyndra declared "lowering her steadily
    toward exposed groin"; the Director resolved "begins to lower her hand
    steadily toward the parted robe and hiked skirt", with no form of "lift"
    anywhere in it; and the player's view arrived as "lifting you to eye
    level". The narrator, which renders the view and not the event, then had no
    lowering to describe -- so the beat the story had actually committed to
    never reached the page.

    A WARNING, never a scrubber, for the same reason `_disguise_leak_check` is:
    the fix belongs upstream in what perception is handed, and rewriting a view
    on a regex would be a worse authority than the model it is policing.
    """
    # CUT 2026-09-15. Measured on the scratch corpus: 5 fires in 167 turns,
    # every one read a false positive -- the check matched a raising word
    # and a lowering word anywhere in a whole view against a whole event
    # ("down through the hatch" flagged for a lantern "raised" in the same
    # paragraph). A regex over free prose fails in whichever direction its
    # missing word points; the owner's rule for a guard that fires on valid
    # output is to measure the rate and cut. Kept as a name so a stored
    # variant that names it still loads.
    return

def _disguise_leak_check(ctx, stage, views, perceivers, subject_name,
                         concealed_terms, known_to):
    """Deterministic fidelity tripwire (a WARNING, never a scrubber). Flags an
    UNAWARE perceiver whose view names one of the disguised subject's concealed
    features. Scoped to that subject's own terms, so unrelated lore (a
    'Nine-Tailed Fox' task-force name) is never touched. The real fix is
    upstream -- feeding the disguised appearance so correct text is generated
    -- this only catches a model that leaked anyway."""
    if not concealed_terms:
        return
    known = known_to or set()
    for p in perceivers:
        pid = str(p["id"])
        if pid.casefold() == "player":
            continue  # the player is the subject / always knows
        if str(p.get("name") or "").casefold() in known:
            continue
        v = str(views.get(pid) or "").lower()
        for t in concealed_terms:
            t = str(t).strip().lower()
            if t and re.search(rf"\b{re.escape(t)}\b", v):
                ctx.warnings.append(
                    f"{stage}: disguise leak -- '{t}' (a concealed feature of "
                    f"{subject_name}) surfaced in the view of {p.get('name')}")
                break

def _touch_only_sources(scene, perceiver_name, spatial_to_sources,
                        visual_channel_to_sources):
    """Return the set of source names who are touch-only for this perceiver.

    A source is touch-only when the perceiver cannot SEE it (no visual
    channel) but CAN feel it -- the two bodies are in physical contact
    (scene.contacts) or one is contained within the other (scene.contained).

    This is the structural basis for surface-translation: the resolved_event
    prose names the acts a touch-only source is performing, and the
    perception LLM -- able to feel the body but not see it -- resolves those
    acts through the touch channel, effectively learning what the hidden
    body is doing from the omniscient prose.  _surface_translate_event
    replaces those act-naming sentences with neutral surface-sensation
    descriptions so only motion/pressure reaches the perceiver.
    """
    if not scene or not perceiver_name:
        return set()
    p_cf = str(perceiver_name).casefold()
    # --- contact-based touch channel ---
    contacts = scene.get("contacts") or []
    contact_names = set()
    for c in contacts:
        if not isinstance(c, dict):
            continue
        actor = str(c.get("actor") or "").strip()
        target = str(c.get("target") or "").strip()
        if actor.casefold() == p_cf:
            contact_names.add(target)
        elif target.casefold() == p_cf:
            contact_names.add(actor)
    # --- containment-based touch channel ---
    # Read through spatial's resolver, not scene["contained"] alone: a scene
    # can also express one body inside another as a ROOM parented to that body,
    # and reading the ledger directly made that form deliver NO touch at all --
    # the body around them felt nothing, which is the wrong half of "concealed
    # but felt" to lose. hiding_holders_of understands both forms.
    # Every comparison here goes through `same_subject`, not casefold. The same
    # character routinely appears under two spellings at once -- a cast display
    # name and a scene entity id -- and the containment ledger names one while
    # the perceiver arrives as the other. Measured live: an enclosing character
    # was matched as "Elyndra" against a holder recorded as "elyndra_succubus",
    # so the occupant was not a touch candidate, `_surface_translate_event`
    # never fired, and the omniscient resolved_event -- naming the occupant's
    # interoceptive state in as many words -- went into the enclosing
    # character's payload intact. That is the own-body isolation rule breaking
    # on a string comparison: a mind may have its own body state and its own
    # scrubbed observations, never another mind's vitals.
    containment_names = set(hiding_holders_of(scene, perceiver_name))
    for other in (scene.get("positions") or {}):
        if same_subject(scene, str(other), perceiver_name):
            continue
        if any(same_subject(scene, holder, perceiver_name)
               for holder in hiding_holders_of(scene, other)):
            containment_names.add(str(other))
    contained = scene.get("contained") or {}
    if isinstance(contained, dict):
        for subject, record in contained.items():
            holder = str(
                record.get("in") if isinstance(record, dict) else record
                or ""
            ).strip()
            s_name = str(subject).strip()
            if holder and same_subject(scene, s_name, perceiver_name):
                containment_names.add(holder)
            elif s_name and same_subject(scene, holder, perceiver_name):
                containment_names.add(s_name)
    touch_candidates = {n for n in (contact_names | containment_names)
                        if n and not same_subject(scene, n, perceiver_name)}
    # A touch-only source: in spatial range, no visual channel, in physical
    # contact. The candidate may be spelled as an entity id while the source
    # tables are keyed by display name, so resolve rather than index -- the
    # returned name must be the SOURCE table's spelling, because that is what
    # every caller matches against.
    out = set()
    for name in touch_candidates:
        key = name if name in spatial_to_sources else next(
            (s for s in spatial_to_sources if same_subject(scene, s, name)),
            None)
        if key and not visual_channel_to_sources.get(key, False):
            out.add(key)
    return out


def _surface_translate_event(event_text, touch_only_sources):
    """Replace act-naming sentences for touch-only sources with surface-sensation prose.

    The resolved_event text is omniscient: it names what every actor is
    doing ("she curls her fingers around the knife at her belt").  A perceiver who can
    FEEL a source but not SEE it receives this text through the touch
    channel and the perception LLM translates the named act into felt
    sensation -- effectively learning the hidden body's exact actions from
    prose that was supposed to be filtered by channel.

    This function structurally withholds the act-naming language: sentences
    that describe actions BY a touch-only source are replaced with a neutral
    surface-sensation description that conveys only motion and pressure at
    the contact surface, never what the hidden body is doing or why.

    General by design -- works for any touch-only situation: a body held in
    a hand, sealed in a container, pressed against a wall, etc.
    """
    if not event_text or not touch_only_sources:
        return event_text

    # Free prose cannot be security-matched reliably: a later sentence may use
    # a pronoun or paraphrase the act. Fail closed for the whole omniscient
    # event and let the deterministic touch/contact facts supply the surface.
    return "You register motion and pressure at the contact surface."


# A sentence that opens with a bare pronoun continues the previous sentence's
# subject rather than naming one of its own.
_REDACTED_NOTICE = "[Some parts of the event are not perceptible to you.]"


def _redact_concealed_from_event(event_text, concealed_for_this_perceiver):
    """Strip sentences describing concealed actions out of the omniscient
    resolved_event before it reaches one perceiver's payload.

    This is a structural redaction rather than an instruction to the perception
    model, and it is the load-bearing guarantee for concealment -- so its
    limits matter more than its mechanism.

    A sentence goes if it names a concealed actor, OR if it continues a redacted
    sentence with a bare pronoun subject. The continuation rule is the whole
    point: the name-only test this replaced passed the audit's own worked
    example straight through -- "Mara turns to the shelf. She slips the vial
    into her sleeve." redacted sentence one and delivered sentence two, which
    is the sentence carrying the secret. A sentence that names a DIFFERENT
    actor ends the continuation, so an unrelated beat that merely follows a
    concealed one is not swallowed.

    What still escapes: a paraphrase that gives the concealed act a fresh
    explicit subject ("the vial disappears into a sleeve") names nobody and
    reads as a new subject, so nothing here catches it. Prose matching cannot
    close that -- the structural answer is to carry the actor's id on the event
    element and redact on identity, never on text (docs/UNBUILT.md §3.1, and
    §4.2 for the primitive). Until the Director emits that, this is a floor,
    not a proof, and the perception prompt's own instruction remains the second
    layer.

    Deliberately over-redacts in one direction: a concealed actor's OVERT acts
    in the same beat are stripped too, because "this sentence names Mara" does
    not say which of Mara's acts it describes. Losing an overt beat is a
    degradation; delivering a concealed one is a leak, and the two are not
    equally bad.
    """
    if not event_text or not concealed_for_this_perceiver:
        return event_text

    concealed_names = {
        str((entry or {}).get("actor") or "").strip().casefold()
        for entry in concealed_for_this_perceiver
        if str((entry or {}).get("actor") or "").strip()
    }
    if not concealed_names:
        return event_text

    sentences = [s.strip()
                 for s in split_sentences(event_text, _SENTENCE_SPLIT)
                 if s.strip()]
    if not sentences:
        # A single unpunctuated clause cannot be split, so there is no safe
        # subset to keep.
        return _REDACTED_NOTICE

    kept = []
    continuing = False
    for sentence in sentences:
        folded = sentence.casefold()
        # name_boundary_regex, not \b: Japanese particles are word characters,
        # so `\bミカ\b` never matched `ミカは棚に向かう` and the concealed
        # sentence was kept verbatim. This decides who may see an act, so it
        # has to hold in every script the story is written in.
        names_concealed = any(
            name_boundary_regex(name).search(folded)
            for name in concealed_names
        )
        if names_concealed:
            continuing = True
            continue
        if continuing and _ling("_PRONOUN_SUBJECT").match(sentence):
            continue
        continuing = False
        kept.append(sentence)

    return " ".join(kept) if kept else _REDACTED_NOTICE


# DERIVED from the one definition of the wire format, never re-spelled.
# `common._VIEW_MASK` is what `_mask_quoted_spans` actually emits; this
# module used to carry a second spelling of the same token, so changing the
# mask in common.py would have silently disarmed the refusal check below --
# the check that stops a self-narration cut from taking a reader's delivered
# line with it. It would not have raised, it would have stopped matching.
# `.split` rather than a regex over the format string, so a format that stops
# having exactly one `%d` fails here and loudly.
_MASK_PREFIX, _MASK_SUFFIX = _VIEW_MASK.split("%d")
_MASK_TOKEN = re.compile(
    re.escape(_MASK_PREFIX) + r"\d+" + re.escape(_MASK_SUFFIX))


def _strip_self_narration_quote_safe(view, perceiver_name, other_names=()):
    """`_strip_self_narration` with a floor under delivered speech.

    The stripper splits on sentence punctuation, and sentence punctuation
    occurs INSIDE quoted lines. On the model path that was tolerable: the
    text it repaired was model prose, and losing a sentence of it lost
    paraphrase. On the composer path the same pass ran over a view whose
    quotes are entitled delivered lines reproduced verbatim from
    `dialogue_log` -- so it cut them mid-sentence. Measured over the corpus
    replay: 167 of 382 fires dropped text containing a quote character, and
    at least 16 cascaded into the invented-dialogue guard, which then failed
    to match the mangled quote against ground truth and deleted the whole
    line. That is the composer's ONLY recall regression (33 player-view
    lines lost against the model's 6), and it was self-inflicted.

    So: a drop that would take a quote with it is refused outright. The
    refusal is returned rather than swallowed, because a view knowingly
    delivered with self-narration still in it is a thing the caller should
    say out loud -- the same contract `_strip_self_narration`'s own two
    floors already use.

    QUOTED SPANS ARE MASKED BEFORE THE SPLIT, the same way
    `_dedupe_view_sentences` does it and for the same reason its comment
    records: a per-fragment "does this contain a quote character" test is
    defeated by the splitter itself, because the fragment it hands you is
    already cut. Masked, a delivered line is one opaque token that no
    splitter can enter, so the stripper decides about whole sentences
    again. Then any sentence still carrying a token is refused outright:
    the mask proves a delivered line is in there, and no framing error is
    worth a reader's line.

    Not a quote CHARACTER class -- this is prose full of possessives, and
    "Reya's voice carries down the hall" is exactly the authored
    self-narration the gate exists to remove.

    Returns (text, dropped, refused), all unmasked.
    """
    masked, spans = _mask_quoted_spans(str(view or ""))
    own_refusals = []
    stripped, dropped_masked = _strip_self_narration(
        masked, perceiver_name, other_names, refusals=own_refusals)
    dropped = [_unmask_quoted_spans(s, spans) for s in dropped_masked]
    if any(_MASK_TOKEN.search(s) for s in dropped_masked):
        return view, [], dropped
    if own_refusals:
        # The stripper's OWN two floors (would empty the view / would take
        # all the sight with it) also decline to cut, and a view knowingly
        # delivered with self-narration in it is the same reportable thing
        # whichever floor stopped the cut. They were silent by default.
        return view, [], [_unmask_quoted_spans(r, spans)
                          for r in own_refusals]
    return _unmask_quoted_spans(stripped, spans), dropped, []


#: Where one authored predicate ends and the next begins, as TYPOGRAPHY
#: rather than vocabulary. This is deliberately not a list of conjunctions:
#: it is the punctuation an author already used to join predicates, and the
#: failure direction is the safe one -- a join point this misses leaves the
#: two predicates in ONE span, so a span that names an inadmissible body
#: takes more with it, never less. Nothing here decides meaning.
def _composer_scrub_surface(text, name, recognized, unknown_sources,
                            labels=None):
    """Input-side identity floor for an act's observable surface: a Director
    or character-authored surface can embed a canonical name ("steps toward
    Hinami") the receiving observer has not earned. Applied at ADMISSION so
    the percept never carries it; the output tripwire then has nothing to
    fire on."""
    if not text or not unknown_sources:
        return text
    scrubbed, _ = _scrub_unknown_identities(
        text, allowed_forms=[name, *recognized],
        unknown_sources=unknown_sources, labels=labels)
    return scrubbed


def _composer_authored_prose(ctx, stage, text, name, recognized,
                             unknown_sources, *, roster_names=()):
    """The admission gate for AUTHORED prose: room notes, appearance and
    overlay descriptions, ambient events.

    These three surfaces are the ones nobody wrote for a particular mind.
    An author writes a room note once and it is served to everyone standing
    in the room; an overlay describes a body to whoever can see it. So they
    arrive carrying two things a view must not: another person's canonical
    name, and the perceiver themself in the third person.

    Both are subtractions and both happen HERE, before the percept exists,
    for the same reason the act-surface scrub does: a fact that never
    entered the IR cannot be rendered, cannot be re-derived into a
    structured observation, and cannot be minted into a memory. Repairing
    the rendered view instead is what the corpus replay caught destroying
    entitled speech.

    Returns (text, notes) -- notes are things the caller should warn about,
    not failures. A gate that fires is doing its job; a gate that REFUSES
    (quoted self-narration it will not cut) is the one worth reading.
    """
    text = str(text or "").strip()
    if not text:
        return text, []
    notes = []
    if unknown_sources:
        text, leaked = _scrub_unknown_identities(
            text, allowed_forms=[name, *recognized],
            unknown_sources=unknown_sources)
        if leaked:
            notes.append(
                f"{stage}: authored prose named {leaked} to {name}, who has "
                "no channel to that identity; replaced with descriptors at "
                "admission")
    text, _dropped, refused = _strip_self_narration_quote_safe(
        text, name, list(roster_names))
    if refused:
        notes.append(
            f"{stage}: authored prose narrates {name} in the third person "
            "inside a quoted line, so it was admitted as written rather "
            f"than cut: {_excerpt_in(text, refused[0])!r}")
    return text, notes


def _composer_tripwires(ctx, stage, pid, name, view, known, roster,
                        spoken_lines=None, labels=None):
    """The retired scrub passes, kept armed as tripwires over composed views.

    Firing means a COMPOSER DEFECT -- Layer A admitted something it should
    not have -- and the warning says so.

    WHAT EACH ONE IS ALLOWED TO DO TO THE TEXT differs, and the difference
    was paid for. "Defense in depth costs nothing when the guards never
    fire" is what this function used to say, and the corpus replay measured
    what it actually cost: the guards fired 382 times, 167 of those drops
    took a quote character with them, and the composer lost 33 entitled
    player-view lines where the model path lost 6. The repair, not the
    composer, was the only recall regression in the build.

    So the three are graded by what a wrong repair destroys:

    * IDENTITY still repairs. `_scrub_unknown_identities` SUBSTITUTES a
      descriptor for a name, outside quoted spans only -- it cannot delete
      a sentence and cannot touch a delivered line. And what it prevents is
      a firewall breach, which must never ship on the strength of a warning
      nobody reads.
    * SELF-NARRATION repairs only where it can prove it is safe: a drop
      that would take a quote with it is refused and reported instead
      (`_strip_self_narration_quote_safe`). A sentence with no quote in it
      carries no delivered line, so cutting it costs framing and nothing
      else.
    * INVENTED DIALOGUE no longer repairs at all. It deletes whole lines --
      the most destructive act available here -- and on this path it has no
      legitimate work: every quote in a composed view was built from
      `dialogue_log` by `speech_percept`, so a fire is either the cascade
      above or a gap in the ground truth it checks against. Both are bugs
      in the engine, and neither is fixed by deleting the reader's line.
    """
    if not view:
        return view
    recognized, unknown = _composer_unknown_sources(name, known, roster)
    if unknown:
        # WITH THIS OBSERVER'S OWN LABELS: one label per (observer, body) per
        # beat. Without them a repaired name read "the unfamiliar person"
        # beside the descriptor the same view had used for the same body
        # (eight repairs on the playerless Aldermill run, round 5).
        view, leaked = _scrub_unknown_identities(
            view, allowed_forms=[name, *recognized], unknown_sources=unknown,
            labels=labels)
        if leaked:
            ctx.warnings.append(
                f"{stage}: COMPOSER TRIPWIRE -- unearned identity {leaked} "
                f"reached the composed view of {name}; Layer A admitted a "
                "fact with no channel (engine defect)")
    stripped, self_narrated, refused = _strip_self_narration_quote_safe(
        view, name, [s["name"] for s in roster])
    if self_narrated:
        # WITH THE TEXT AROUND IT (`_excerpt_in`): the fragment alone is
        # whatever the sentence splitter handed back, and on live data that
        # was four characters of a thousand-character view.
        ctx.warnings.append(
            f"{stage}: COMPOSER TRIPWIRE -- composed view of {name} narrated "
            "its own perceiver (engine defect): "
            f"{_excerpt_in(view, self_narrated[0])!r}")
        view = stripped
    if refused:
        ctx.warnings.append(
            f"{stage}: COMPOSER TRIPWIRE -- composed view of {name} narrates "
            "its own perceiver inside a delivered line; the line was kept "
            f"and the framing error stands (engine defect): "
            f"{_excerpt_in(view, refused[0])!r}")
    if spoken_lines is not None:
        _checked, invented = _scrub_invented_dialogue(
            view, spoken_lines, cast_names=[s["name"] for s in roster])
        if invented:
            ctx.warnings.append(
                f"{stage}: COMPOSER TRIPWIRE -- dialogue in composed view "
                f"'{pid}' does not match the delivered-line ground truth "
                f"(engine defect, view delivered as composed): {invented}")
    return view


def _authored_prose_gate(ctx, stage, name, known, identity_space):
    """One observer's admission gate over authored prose, as a callable.

    Built once per observer per stage and handed down, so the percept
    builders stay decision-free: they take text that is already safe for
    this mind rather than learning who this mind is."""
    recognized, unknown = _composer_unknown_sources(
        name, known, identity_space)
    roster_names = [s["name"] for s in identity_space]

    def gate(text):
        gated, notes = _composer_authored_prose(
            ctx, stage, text, name, recognized, unknown,
            roster_names=roster_names)
        for note in notes:
            ctx.warnings.append(note)
        return gated

    def names(text, labels=None):
        """The identity half alone, in this observer's own labels: for
        authored text about a body, which must keep the body's owner in
        the third person where the full gate would cut it (a pose)."""
        return _composer_scrub_surface(text, name, recognized, unknown,
                                       labels=labels)

    def written(text):
        """Text written on a thing, for this observer: a name in it of a
        body this observer does not know stays the name as written, quoted
        (`_scrub_unknown_identities`' ``as_written``), and is never turned
        into what this observer calls that body."""
        if not text or not unknown:
            return text
        out, _leaked = _scrub_unknown_identities(
            text, allowed_forms=[name, *recognized], unknown_sources=unknown,
            as_written=lambda form: composer._t("written_name", name=form))
        return out

    gate.names = names
    gate.written = written
    return gate


def _composer_company(others, display_map, percepts):
    """Which co-present bodies this observer's view was composed ABOUT, each
    under the label the observer earned -- the per-beat record the people
    projection (`story_view.player_view`'s `people`) reads back.

    Derived from the presence percepts themselves (their opaque `body` key)
    rather than by re-checking sight levels here, so this record structurally
    cannot admit a body the rendered view did not: both come from the same
    gated IR. `recognized` is `observer_display_map`'s own verdict -- a
    recognised body maps to its own name -- which is NOT the same question as
    "is the name in the identity ledger": a disguise that conceals identity
    makes a well-known name a stranger, and a reader that re-derived
    recognition from the ledger would undo the disguise.

    The canonical `name` rides this record because a step's content is
    engine-side, like the other viewers' views beside it; the projection is
    what withholds it from an unrecognising viewer.
    """
    admitted = {}
    for p in percepts:
        if p.kind == "presence" and p.data.get("body"):
            key = p.data.get("body")
            admitted[key] = admitted.get(key, False) or p.fidelity == "full"
    out = []
    for body in others or []:
        name = str(body.get("name") or "")
        if not name or composer.body_key(name) not in admitted:
            continue
        label = str(display_map.get(name) or "")
        if not label:
            continue
        # `full`: a presence line composed at FULL sight -- what a reader of
        # how a body LOOKS (its authored parts) may rely on; a figure in the
        # dim or a hand in the dark is in the record without it.
        out.append({"key": composer.body_key(name), "name": name,
                    "label": label, "recognized": label == name,
                    "full": bool(admitted[composer.body_key(name)])})
    return out


def _repaired_observations(observations, view, name, known, roster,
                           labels=None):
    """Carry the composed view's REPAIRS into the structured observations.

    `composer.observations_from_render` projects from `rendered`, the view
    BEFORE `_composer_tripwires` runs, so the invariant its docstring claims
    -- "the text is byte-for-byte part of the view" -- holds only while no
    tripwire fires. When one does, the two diverge and the observations keep
    exactly what the view had repaired.

    Survivable while the observations were a secondary representation; not
    survivable once `agents/narration.py` began building `current_events`
    from them, because a repaired leak then walks back to the one consumer
    whose output is the page. Measured over 104 turns in eight stories, 102
    agree byte for byte and both divergences are the same class: the observer
    named in the THIRD PERSON inside its own view ("Hinami and The Doctor
    have begun walking inland toward the ferry port"), which `Design.md`
    names as an invariant and the self-narration tripwire drops.

    The repaired VIEW is the authority, not a re-run of the repairs. Running
    them per observation cannot work: `_strip_self_narration_quote_safe`
    refuses to delete when EVERY sentence names the perceiver -- one
    observation is one sentence, so a self-narrating one is always the whole
    of its own input and the refusal fires every time.

    So identity is substituted first (it rewrites a name in place and never
    deletes), and what survives is what the repaired view still contains.
    Dropping on absence is safe precisely because of how the tripwire grades
    its repairs: the self-narration drop is quote-safe and REFUSES a deletion
    that would take a quote with it, so a sentence missing from the repaired
    view provably carried no delivered line, and nothing an enforceable
    dialogue check will demand can be lost here.

    Silent by design: the tripwire has already warned about the view, and
    this is one composer defect, not two.
    """
    if not observations:
        return []
    if not str(view or "").strip():
        return []
    recognized, unknown = _composer_unknown_sources(name, known, roster)
    haystack = re.sub(r"\s+", " ", str(view)).strip()
    out = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        observed = obs.get("observed") or {}
        text = str(observed.get("text") or "")
        if not text.strip():
            continue
        if unknown:
            text, _leaked = _scrub_unknown_identities(
                text, allowed_forms=[name, *recognized],
                unknown_sources=unknown, labels=labels)
        if re.sub(r"\s+", " ", text).strip() not in haystack:
            continue
        repaired = {**obs, "observed": {**observed, "text": text}}
        if unknown and repaired.get("actor"):
            repaired["actor"], _leaked = _scrub_unknown_identities(
                str(repaired["actor"]), allowed_forms=[name, *recognized],
                unknown_sources=unknown, labels=labels)
        out.append(repaired)
    return out


def _scrub_episode_identities(ctx, stage, name, content, gist, known, roster):
    """The identity floor over the EPISODE -- the first-person memory text
    minted from the same percepts as the view.

    `_composer_tripwires` runs `_scrub_unknown_identities` over the composed
    VIEW and stores the repaired text; the episode was rendered from the
    same IR and stored as rendered, so a stranger's name the view had
    repaired walked into the character's memory untouched. Measured
    2026-09-05 (chat 115 on a copy, turn 2): Sarah Moon's view read
    "standing facing the young woman" after the tripwire, and her episode
    read "standing facing Hinami" -- a name she had never been given,
    carried in by the body specialist's pose `detail`, now retrievable by
    every later beat as her own memory. A leak into memory is the worse
    one: a view lasts a beat, a memory is cited for the rest of the story.
    Same inputs, same repair, same warning shape; the substitution is the
    observer's own descriptor for that body, outside quoted spans only."""
    recognized, unknown = _composer_unknown_sources(name, known, roster)
    if not unknown:
        return content, gist
    allowed = [name, *recognized]
    content, leaked = _scrub_unknown_identities(
        content, allowed_forms=allowed, unknown_sources=unknown)
    gist, leaked_gist = _scrub_unknown_identities(
        gist, allowed_forms=allowed, unknown_sources=unknown)
    if leaked or leaked_gist:
        ctx.warnings.append(
            f"{stage}: COMPOSER TRIPWIRE -- unearned identity "
            f"{sorted(set(leaked) | set(leaked_gist))} reached the episode of "
            f"{name} and was repaired before it became memory (engine defect)")
    return content, gist


def _composer_finish_observer(ctx, stage, pid, name, rendered, known, roster,
                              clean_views, observations, ledger, *,
                              spoken_lines=None, seen=None, prev_meta=None,
                              track_standing_meta=False, labels=None, percepts=None):
    view = _composer_tripwires(
        ctx, stage, pid, name, rendered.text, known, roster,
        spoken_lines=spoken_lines, labels=labels)
    clean_views[pid] = view or None
    observations[pid] = _repaired_observations(
        composer.observations_from_render(pid, rendered), view,
        name, known, roster, labels=labels)
    ledger[pid] = {
        "standing": sorted(rendered.standing_keys),
        "described": sorted(rendered.described),
        # WHAT EACH STANDING KEY WAS FOR THIS OBSERVER THIS BEAT (B28).
        # Absent -- not empty -- wherever the composer computes no verdict
        # (character mode diffs against no ledger) and on a chat stored
        # before the field existed, so a reader that finds nothing treats
        # the fact as news rather than as settled. The narrator's sensory
        # manifest is that reader: it re-derives the same standing contacts
        # from the scene, and must not hand one this observer's own ledger
        # already carried to the page as though it had just happened.
        **({"verdicts": dict(rendered.verdicts)} if rendered.verdicts else {}),
        # WHO THIS OBSERVER COULD SEE. Absent (rather than empty) when the
        # stage did not compute it, and `_composer_prev_seen` keeps that
        # distinction: an empty list means "saw nobody", a missing key
        # means "unknown", and only the first can make the next beat a
        # re-encounter.
        **({"seen": sorted(seen)} if seen is not None else {}),
        # WHICH FORM each body was described in, carried forward
        # (`_learned_labels`; read by `present_label_fn`).
        "described_as": _learned_labels(_prior_ledger_entry(ctx, pid), percepts),
        # WHEN EACH STANDING FACT WAS FIRST AND LAST SAID TO THIS OBSERVER
        # (D7). Player tier only -- it is the only view that suppresses a
        # standing fact it has already delivered, so it is the only one where
        # "still true, not said for N beats" is a real state; and the narrator
        # is its only reader. Absent, never empty, wherever it was not
        # computed, so a chat stored before the field reads as no record.
        # Built against `view`, the REPAIRED text, for the same reason
        # `_repaired_observations` two lines up is: a record that outlives
        # the beat must not carry wording a tripwire took out of it.
        **({"standing_meta": _standing_meta(
            prev_meta, rendered,
            getattr(getattr(ctx, "turn", None), "idx", None), view)}
           if track_standing_meta else {}),
    }
