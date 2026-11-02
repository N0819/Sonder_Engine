"""The Director/player authority checks on resolved prose and contacts, the
presence-knowledge channel floor, and the player-authority ladder applied to
claims.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from story.character_schema import (
    character_name,
    character_name_from_text,
    cue_boundary_pattern,
    name_boundary_pattern,
)
from story.scene import normalize_player_authority, PLAYER_AUTHORITY_GRANTS
from world.spatial import contact_id, hiding_holders_of, room_of

from agents.common_base import _dict_list, _ling, _quote_body
from agents.common_names import (
    _countable_word_units,
    _player_name_forms,
    _predicate_heads,
    _sentence_subjects,
    _strip_subject,
)
from agents.common_scrubs import _echo_fold


# How far past the name to look for the verb. Same window the player check
# uses, and for the same reason: the act must be what this body is DOING, not
# a word appearing anywhere in a long sentence.
_SPEECH_VERB_WINDOW = 3


def _check_character_speech_authority(resolved_event, silent_names,
                                      other_names=(), pronouns=None):
    """Speech a resolved_event gives a character who declared none this beat.

    The mirror of `_check_player_act_authority`, and the boundary it defends is
    the same one from the other side. Live, alpha 6.0.2: a character agent
    declared silence -- empty sequence, `stop_reason: "natural silence"`, no
    dialogue_log entry -- and the resolved_event said "<the character> adds a
    further comment" anyway. Perception rendered a speech event with no
    content; the narrator, having nothing to quote, dressed the absence as
    inaudibility. It read as a muffling bug and was a fabrication.

    A character owns their own speech exactly as the player owns theirs, and
    until now only the player had a guard. Nothing objected when the Director
    authored conduct for a mind that owns it.

    Scoped like its sibling, to the unambiguous case: the character was ASKED
    this beat and declared NO speech at all, so any utterance attributed to
    them is invented by construction. Sentence subject must be the name
    itself -- a pronoun subject could be anyone in the beat, and guessing
    would make this cry wolf on ordinary narration.

    `silent_names` is who declared nothing; a character who spoke is not
    checked, because separating an elaborated line from an added one needs
    more than a verb list.

    Subject resolution is pronoun-continuation-aware (`_sentence_subjects`)
    and the verb window is measured per conjunct (`_predicate_heads`). Both
    were added after chat 56 t1391, where the guard was armed and silent: the
    Director wrote the fabrication as "He takes a half-step closer, hands open
    at his sides, and speaks in a low, steady voice", which the original
    name-anchored, three-words-from-the-name check could not see at all.
    """
    warnings = []
    all_names = list(silent_names or []) + list(other_names or [])
    for sentence, subject in _sentence_subjects(resolved_event, all_names,
                                                pronouns=pronouns):
        if subject is None or subject not in (silent_names or []):
            continue
        # A quoted span is `_check_prose_quote_authority`'s business, not
        # this one: what this catches is the contentless attribution a quote
        # check cannot see -- "X adds a comment" quotes nothing, so nothing
        # downstream can tell it was invented.
        without_quotes = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
        tail = _strip_subject(without_quotes, subject)
        for head, _clause in _predicate_heads(tail, _SPEECH_VERB_WINDOW):
            if re.search(cue_boundary_pattern(_ling("_ATTRIBUTION_VERBS")), head, re.I):
                warnings.append(
                    "Speech attributed to a character who declared none "
                    f"(character-speech authority): {subject}: "
                    f"{sentence[:120]!r}"
                )
                break
    return warnings


def _check_character_act_authority(resolved_event, declared_actions, name,
                                   other_names=(), pronouns=None):
    """Physical acts a resolved_event gives a CHARACTER they did not declare.

    The third side of the same boundary `_check_player_act_authority` and
    `_check_character_speech_authority` defend, and the one nothing guarded:
    act authority was enforced for the player only, so a character could be
    handed conduct freely. Live, chat 56 t1391: the Doctor declared a scan
    "from several feet away", "while staying at distance", and the resolve had
    him take "a half-step closer". The narrator dropped it, so it was invisible
    in play -- and it still committed as his own episodic memory of what he did.

    Two scopes, because the two cases admit different certainty:

    * The character declared NO action at all. Silence about conduct is a
      declaration, so any act is invented by construction -- the full act-verb
      list applies, exactly as for the player.

    * The character declared actions, none of them locomotive. Elaborating a
      declared act is the Director's job and is NOT flagged; separating
      elaboration from addition in general needs more than a verb list, so
      this narrows to the one addition that is unambiguous and consequential:
      MOVEMENT. A character who declared no movement was not moved.
    """
    if not name:
        return []
    declared_text = " ".join(
        f"{a.get('attempt', '')} {a.get('observable', '')}"
        for a in (declared_actions or []) if isinstance(a, dict)
    )
    if declared_actions:
        # Already moving under their own declaration: the Director may render
        # that movement however it likes.
        # Verbs that change where a body IS or how far it is from someone else. The
        # Director may render a declared act richly; it may not relocate a character
        # who declared no movement, because distance is load-bearing -- it decides
        # what perception delivers, what contact is possible, and (chat 56 t1391) it
        # can directly reverse the intent the character declared, which was to scan
        # her "without crowding her".
        #
        # Movement is not always written as a locomotion VERB. The live case wrote it
        # as a verb plus a distance noun -- "takes a half-step closer" -- whose head
        # verb is "take", which is no more locomotive than taking a screwdriver. What
        # marks it as movement is the distance word, so read the clause for one.
        if re.search(cue_boundary_pattern(_ling("_LOCOMOTION_VERBS")), declared_text, re.I):
            return []
        verbs, kind, proximity = (
            _ling("_LOCOMOTION_VERBS"), "undeclared movement", True)
    else:
        # Verb STEMS a resolved_event uses when it gives someone an ACT, matched with
        # ordinary English inflection (-s/-es/-ed/-ing) so "straightens", "shifting"
        # and "reached" all count. Kept to unambiguous bodily/manipulative verbs: this
        # exists to catch the player being handed conduct they never declared, not to
        # police prose.
        verbs, kind, proximity = _ling("_PLAYER_ACT_VERBS"), "act not declared", False

    warnings = []
    all_names = [name] + [n for n in (other_names or []) if n != name]
    for sentence, subject in _sentence_subjects(resolved_event, all_names,
                                                pronouns=pronouns):
        if subject != name:
            continue
        without_quotes = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
        tail = _strip_subject(without_quotes, subject)
        for head, clause in _predicate_heads(tail, 3):
            if re.search(rf"\b(?:{verbs})\b", head, re.I) or (
                    proximity and _ling("_PROXIMITY_RE").search(clause)):
                warnings.append(
                    f"Character {kind} this beat (character-act authority): "
                    f"{name}: {sentence[:120]!r}"
                )
                break
    return warnings


# Below this, a quoted span is a label or a scare quote rather than an
# utterance -- a readout reading "STABLE", the word "safe".
_PROSE_QUOTE_MIN_WORDS = 3


def _check_prose_quote_authority(resolved_event, allowed_bodies):
    """Spoken lines in resolved_event PROSE that nobody declared.

    The dialogue_log backstop (director.py) drops a director-invented line for
    a registered character by comparing its `exact_quote` against that
    character's own declaration. It is a good guard and it was inert in chat 56
    t1391, because `dialogue_log` was EMPTY: the invented line existed only in
    the resolved_event prose. The speech check meanwhile strips quoted spans on
    the stated assumption that the dialogue path covers them. Each guard
    assumed the other held the ground, and a quote in prose with no log entry
    fell between them.

    This closes it from the other side, and needs no subject resolution to do
    it: a line nobody declared is invented no matter WHO the prose says said
    it. `allowed_bodies` is every quote body that was legitimately declared
    this beat -- by the player, by any character, or by an unsheeted background
    presence the Director is licensed to voice.
    """
    warnings = []
    seen = set()
    # Words only, for the same reason the player-echo strip needs it: the
    # Director RE-PUNCTUATES a line it is quoting, and an exact membership
    # test then reads its own faithful rendering as an invention.
    folded_allowed = [_echo_fold(a) for a in (allowed_bodies or ()) if _echo_fold(a)]
    # Quoted spans, in every style the resolve model actually produces. The single
    # -quote form must not mistake an apostrophe for a delimiter, so a quote may
    # only OPEN where no letter precedes it and CLOSE where no letter follows --
    # which leaves "You're" intact inside the span.
    for pattern in _ling("_PROSE_QUOTE_RES"):
        for span in pattern.findall(resolved_event or ""):
            body = _quote_body(span)
            if not body or body in seen:
                continue
            seen.add(body)
            # Counted in the span's own script (A2): `[A-Za-z']+` finds
            # nothing in Japanese prose, so every quoted line measured 0
            # words, fell under the minimum, and this authority floor --
            # the one that catches a line nobody declared -- was inert for
            # a whole story. Identical count for Latin input.
            if _countable_word_units(body) < _PROSE_QUOTE_MIN_WORDS:
                continue
            if body in allowed_bodies:
                continue
            # A quote NESTED inside a declared line is not a new utterance --
            # it is somebody quoting what was already said. The four patterns
            # above each sweep the whole prose independently, so a declared
            # line carrying inner quotes ('And I said "ask me again" -- not
            # "yes, absolutely, show you the stars."') yields the outer span
            # AND both inner ones, and only the outer could ever match.
            #
            # Measured across the live corpus: 14 flags, 13 of them cleared by
            # this test -- a 93% false-positive rate on a guard whose every
            # firing costs a full second Director call, the most expensive
            # correction this seam can order.
            #
            # ONE DIRECTION ONLY: the flagged span must sit INSIDE something
            # that was declared. The reverse -- a declared line sitting inside
            # the flagged span -- is prose that EXPANDED on what somebody said,
            # which is the invention this guard exists to catch, and allowing
            # it cleared the one genuine case in the corpus along with the
            # thirteen false ones.
            folded = _echo_fold(body)
            if folded and any(folded in a for a in folded_allowed):
                continue
            warnings.append(
                "Spoken line in resolved_event that nobody declared "
                f"(prose-quote authority): {body[:120]!r}"
            )
    return warnings


# WHAT THE DIRECTOR MAY STILL SPEAK FOR.
#
# Measured 2026-08-08 across the whole corpus: background lines authored in
# `director_resolve` run a MEDIAN OF 8 WORDS against the sheeted cast's 16, and
# 27% of them are four words or fewer against the cast's 13% -- "Dragon
# Kingdom...", "Kadomon.", "Sorry-sorry-". 2,042 of the 2,240 background lines
# in the corpus came from the Director; the stage built to voice extras
# produced 200, because `pick_background_reactors` is a BACKSTOP that stands
# down whenever the Director already spoke for someone.
#
# So the model adjudicating physics, dialogue order, state diffs and time in
# one pass was also writing every extra's dialogue, as filler, with no
# perception object for the speaker. That is one cause with two symptoms: the
# flatness above, and the Kadoman leak that `_check_presence_knowledge_channel`
# exists to catch.
#
# These kinds keep the Director's voice because a full character call would buy
# nothing: their speech is formulaic or barely linguistic -- a beast's snarl, a
# swarm, a drone's stock phrase. Anything PERSON-shaped is routed to the
# background stage, which gives it its own call, its own perception object and
# its own recognition of the room. The list is deliberately narrow: routing a
# borderline speaker costs one call and gets a better line, while keeping one
# costs the defect this whole change exists to remove.


def director_may_voice(speaker, scene, presence_rec=None):
    """Whether the Director may author this background speaker's dialogue.

    Kind is read from the scene entity, then from the presence record's own
    sketch. An UNKNOWN kind routes to the background stage -- the conservative
    direction, because the failure it avoids (a person voiced as filler) is the
    one that was actually measured, and the cost of being wrong is one model
    call rather than a flat line and a possible leak.
    """
    name = str(speaker or "").strip()
    if not name:
        return False
    ents = (scene or {}).get("entities") or {}
    ent = ents.get(name)
    if not isinstance(ent, dict):
        lowered = name.casefold()
        ent = next((v for k, v in ents.items()
                    if isinstance(v, dict)
                    and (str(k).casefold() == lowered
                         or str(v.get("name") or "").casefold() == lowered)), None)
    kind = str((ent or {}).get("kind") or "").strip().casefold()
    if not kind:
        kind = str(((presence_rec or {}).get("sketch") or {}).get("kind")
                   or "").strip().casefold()
    return kind in _ling("_DIRECTOR_VOICEABLE_KINDS")


def _check_presence_knowledge_channel(speaker, quote, sc, presence_rec,
                                      heard_text):
    """Scene-entity references in a Director-voiced presence line that the
    presence has no perceptual channel to.

    The Director is entitled to omniscience -- it owns objective causality --
    and the resolve prompt licenses it to voice unsheeted background
    presences. Nothing sat between those two facts: the voicing was authored
    from the omniscient working state with no perception object for the
    speaker. Chat 65 t2148 is the measured case -- Kadoman, a presence minted
    at turn 9 in eastern_market, referring to "the strange coins and notes"
    shown once at turn 4 in fountain_plaza and pocketed since.

    Deterministic floor, subtractive on purpose: it tests REFERENCES the
    engine can resolve (scene entities by name or alias), never meaning. A
    multi-word phrase matches bare; a single-word alias matches only under a
    definite/possessive determiner, because "the strange coins" claims
    acquaintance while "gold coins" is generic knowledge -- a presence must
    keep every true general thing it can say about its own world (the
    copper-and-silver rule), and a presence with no channel must be free to
    be ignorant in front of the player.

    The channel test is current-scene only (presences are stateless): an
    entity offers a channel when it is placed in the presence's own room and
    not shut inside anything (`hiding_holders_of`, both containment forms).
    An unplaced entity offers no provable channel -- in the measured corpus
    the unplaced entities are precisely the pocketed belongings, while room
    furniture lives in room `anchors`, which this never reads. ``heard_text``
    is what legitimately names things into the presence's beat: everything
    spoken aloud this beat by others, plus the presence's own record and
    characterization. Returns warning strings; empty means no leak.
    """
    q = " %s " % re.sub(r"\s+", " ", str(quote or "")).casefold()
    if not q.strip():
        return []
    entities = (sc or {}).get("entities") or {}
    positions = (sc or {}).get("positions") or {}
    speaker_cf = str(speaker or "").strip().casefold()
    heard_cf = str(heard_text or "").casefold()

    p_room = room_of(sc, speaker)
    if not p_room:
        by_name = {str((e or {}).get("name") or "").strip().casefold(): eid
                   for eid, e in entities.items() if isinstance(e, dict)}
        eid = by_name.get(speaker_cf)
        if eid:
            p_room = positions.get(eid) or room_of(sc, eid)
    if not p_room:
        p_room = ((presence_rec or {}).get("sketch") or {}).get("station_room")

    warnings = []
    for eid, edef in entities.items():
        if not isinstance(edef, dict):
            continue
        name = str(edef.get("name") or "").strip()
        name_cf = name.casefold()
        if name_cf and name_cf == speaker_cf:
            continue  # a presence may always speak of itself
        phrases = {p for p in
                   ({name} | {str(a).strip()
                              for a in (edef.get("aliases") or [])})
                   if p and len(p) >= 3}
        if not phrases:
            continue
        if any(p.casefold() in heard_cf for p in phrases):
            continue  # named aloud in the presence's beat, or its own record
        e_room = (positions.get(eid) or room_of(sc, eid)
                  or (room_of(sc, name) if name else None))
        concealed = bool(hiding_holders_of(sc, eid)) or (
            bool(name) and bool(hiding_holders_of(sc, name)))
        if p_room and e_room == p_room and not concealed:
            continue  # placed here, in the open: a channel exists
        hit = None
        for p in sorted(phrases, key=len, reverse=True):
            pcf = p.casefold()
            if len(p.split()) >= 2:
                if re.search(r"(?<!\w)%s(?!\w)" % re.escape(pcf), q):
                    hit = p
                    break
            elif re.search(
                    r"(?<!\w)(?:%s)\s+(?:[\w'-]+\s+){0,2}%s(?!\w)"
                    # Determiners that make a reference DEFINITE. "That explains the strange
                    # coins" refers to HER coins, a thing in the world; "local trade runs on
                    # copper and silver coins" is knowledge about coins in general. The definite
                    # article is what turns a generality into a claim of acquaintance, so it is
                    # what gates the single-word match below.
                    % ("|".join(_ling("_DEFINITE_DETS")), re.escape(pcf)), q):
                hit = p
                break
        if hit:
            where = "unplaced" if not e_room else e_room
            warnings.append(
                f"Background presence {speaker!r} references {hit!r} "
                f"({name or eid}: {where}"
                + (", concealed" if concealed else "")
                + f") with no perceptual channel from "
                + (repr(p_room) if p_room else "an unknown room")
                + " (presence-knowledge channel)."
            )
    return warnings


def _check_player_interiority_authority(resolved_event, player_name,
                                        declared_text="", other_names=()):
    """Interior states a resolved_event asserts about the PLAYER.

    The mirror of `_check_player_act_authority` for feeling rather than doing,
    and the same boundary. The Director owns objective causality; it does not
    own what is inside the protagonist. It may report every observable the
    body shows -- trembling, wide eyes, a shrill cry -- and must stop there,
    because naming the state behind them decides for the player what their
    character feels.

    Live, alpha 6.3, chat 52 turn 19: the player typed only "W-what did you do
    to me!?" and the resolve wrote "the shrill, PANICKED cry" and "she takes in
    the GENUINE TERROR in those wide eyes". Perception then copied both into
    another character's view, so an invented interior state became something a
    second mind had observed as fact.

    Exempt: anything the player themselves wrote. If they declared the fear,
    it is theirs to declare -- this catches what arrives from nowhere.
    `_INTERIOR_CERTAINTY` is flagged only ALONGSIDE an interior word, because
    "genuine" is unremarkable on its own and damning next to "terror".

    A sentence counts as being about the player when it NAMES them (they may be
    its object -- "she takes in the genuine terror in those wide eyes" is about
    the player from another body's side) or when subject tracking resolves it
    to them. The second was added after chat 56 ("Run!") t6: against a player
    who declared only "You imitate them slightly and shudder", the resolve
    wrote "She looks at him, still shaky, but the terror in her eyes has begun
    to recede" -- deciding the player's emotional arc for them. The name-only
    test could not see a pronoun subject, so nothing fired, and perception
    copied the sentence into the player's OWN view.
    """
    if not resolved_event or not player_name:
        return []
    declared = str(declared_text or "").casefold()
    all_names = [player_name] + [
        n for n in (other_names or []) if n and n != player_name]
    warnings = []
    for body, subject in _sentence_subjects(resolved_event, all_names):
        if not body:
            continue
        low = body.casefold()
        if subject != player_name and not _mentions_player(low, player_name):
            continue
        # Interior states a resolved_event may not assert about the PLAYER. Nouns and
        # adjectives that name what is INSIDE a mind, as against the surface a body
        # shows: "trembling", "wide eyes", "a shrill cry" are observable and always
        # allowed; "terror", "panic", "she realises" are not.
        #
        # Verbs that report a mind's own operation rather than its body's motion.
        #
        # Words that assert an interior state is TRUE, which no observer may know.
        #
        # Matched through `cue_boundary_pattern`, the boundary its neighbour
        # `_undeclared_world_object` already uses (A2): the vocabularies are
        # the pack's and a pack keeps its own language's words, but `\b` can
        # never fall around one written in an unspaced script -- so every
        # alternative a pack added here was unreachable and this floor found
        # nothing in such a story. The declaration side keeps its PREFIX
        # semantics (the player's "I have known this" exempts "knows"):
        # `\S*` carries the prefix through the trailing boundary, which for
        # English matches exactly what a bare `\b`-prefix search did.
        hits = [w for w in _ling("_INTERIOR_STATES")
                if re.search(cue_boundary_pattern(re.escape(w)), low)
                and not re.search(cue_boundary_pattern(re.escape(w)),
                                  declared)]
        hits += [v for v in _ling("_INTERIOR_VERBS")
                 if re.search(cue_boundary_pattern(
                     re.escape(v) + r"(?:s|es|d|ed|ing)?"), low)
                 and not re.search(cue_boundary_pattern(
                     re.escape(v) + r"\S*"), declared)]
        if not hits:
            continue
        certainty = [c for c in _ling("_INTERIOR_CERTAINTY")
                     if re.search(cue_boundary_pattern(re.escape(c)), low)]
        warnings.append(
            "Player interior state not declared this beat "
            "(player-interiority authority): "
            f"{sorted(set(hits))[:3]}"
            + (f" asserted as {certainty[0]!r}" if certainty else "")
            + f": {body[:120]!r}")
    return warnings


def _mentions_player(low_sentence, player_name):
    """Whether a sentence is ABOUT the player -- their name, or a possessive
    reaching for them. Pronouns are not guessed at: "her terror" in a
    two-woman scene could be either of them, and a guess here would flag
    ordinary NPC description.

    The name's own boundary, not `\\b` (review 2026-09-07 A2). This is the
    gate on the WHOLE player-interiority authority floor -- a sentence it
    cannot see as being about the player is one the floor never reads -- and
    `\\b` describes only scripts that space their words, so `ヒナミは` never
    matched `ヒナミ` and the floor was inert for an entire Japanese story.
    Identical for Latin names."""
    for form in _player_name_forms(player_name):
        if re.search(name_boundary_pattern(form.casefold()), low_sentence):
            return True
    return False


def _undeclared_world_object(clause, declared_low):
    """The world object a clause has the player take hold of, when the player's
    own declaration never mentions it. None when the clause touches only their
    own body, reaches for nothing, or names something they already declared."""
    # Verbs that put a body in contact with something outside itself.
    # Deliberately excludes verbs that read as manipulation but usually are not:
    # "catch" ("her hair catching the warm light"), "draw" ("draws a breath"),
    # "find" ("finds the words"). The list must earn its flags -- an act guard
    # that fires on scenery is one a maintainer learns to ignore.
    #
    # The player's own body is not a new object. An act on it re-describes what
    # they are doing with themselves, which is elaboration however it is worded --
    # "pushes herself upright" for a declared "slowly stands up".
    #
    # The DIRECT object a verb takes -- the noun it acts ON, with no preposition
    # in between. "grip the edge" is taking hold of the world; "pressed flat
    # AGAINST the cold metal" is a body bracing itself, and reading that as
    # seizing the metal is how a guard starts crying wolf on ordinary prose.
    # The captured group is the whole noun phrase after the article; the HEAD noun
    # is its last word, so "the warm light" reads as "light" rather than "warm".
    for match in re.finditer(cue_boundary_pattern(_ling("_MANIPULATION_VERBS")), clause, re.I):
        obj = _ling("_DIRECT_OBJECT_RE").match(clause[match.end():])
        if not obj:
            continue
        phrase = obj.group(1).split()
        noun = phrase[-1].casefold()
        # A phrase headed by the player's own body is elaboration whatever
        # sits in front of it: "the edge of the console" is the console.
        if noun in _ling("_OWN_BODY_NOUNS") or any(
                w.casefold() in _ling("_OWN_BODY_NOUNS") for w in phrase):
            continue
        if re.search(rf"\b{re.escape(noun)}", declared_low):
            continue
        return noun
    return None


def _claim_authority_kind(claim, player_name):
    """Which grant a claim needs. `None` for a claim no mode restricts.

    `subject_id` alone cannot answer this, and a played beat proved it twice in
    one story. `_extract_authority_claims` resolves an asserted effect to the
    DECLARING ACTOR when the action named no targets -- a deliberate fallback,
    so a player's own body acts (a wave, going rigid) stop tripping the resolve
    seam's 'no resolvable subject' note. But "named no target" is not the same
    fact as "was about my own body": it is equally what a world assertion the
    interpret stage typed as an action looks like.

    Live, the first hard-mode story ever played (2026-08-18, the empty house),
    both on turns where `targets` was empty and the fallback fired:

      * "Two guards come around the corner from the stair" became an ACTION
        rather than the `event` branch that exists for it, so the claim read
        subject_id="Wren", `actor_only` granted it as the player's own body,
        and two guards walked into the world unchallenged.
      * "I take the west door's handle and force the lock; the vault door
        swings open" minted the effect `west door opens, revealing a vault`
        with subject_id="Wren" -- a claim about a DOOR, filed under the
        player's body.

    Reading the prose instead does not save it: the first has no first person
    and the second has plenty, so any test on the wording grants exactly the
    wrong one. What separates them is not in the words at all -- it is that
    the subject was GUESSED. So an inferred subject is not evidence of a body,
    and a mode that exists to withhold authorship may not resolve the doubt in
    the author's favour. It falls to `own_effect`, which `explicit_outcomes`
    and `world_author` still grant; only `actor_only` tightens, which is the
    rung where tightening is the point.

    The cost is stated plainly: under `actor_only` a genuine "I raise my hand"
    is adjudicated rather than true in advance. The declaration still stands
    verbatim, is still resolved, still narrated -- and nothing in the scene
    opposes a raised hand, so it goes up. What it no longer does is bind the
    diff before the Director has read it.
    """
    if str(claim.get("scope") or "") != "effect":
        return None          # a contestable intent is already the Director's
    subject = str(claim.get("subject_id") or "").strip()
    player = str(player_name or "").strip()
    if (player and subject.casefold() == player.casefold()
            and not claim.get("subject_inferred")):
        return "own_body"
    if str(claim.get("claim_id") or "").endswith(":event"):
        return "world"
    return "own_effect"


def downgraded_sequence_indices(records):
    """Which sequence positions a set of authority downgrades came from.

    `apply_player_authority` computes this internally to move each element's
    commitment and then discards it; the caller needs the same answer to void
    the spans those elements became. Parsed HERE rather than at the call site
    because `claim:<index>:<...>` is this module's spelling -- the extractor
    writes it and the downgrade reads it -- and a second parse elsewhere is a
    second thing to keep in step with it.
    """
    indices = set()
    for record in records or []:
        parts = str((record or {}).get("claim_id") or "").split(":")
        if len(parts) >= 2 and parts[1].isdigit():
            indices.add(int(parts[1]))
    return indices


def apply_player_authority(out, mode, player_name=None):
    """Enforce a `PlayerAuthorityMode` on one interpreted beat, in place.

    The enum has existed since the vocabulary was written and was consumed
    nowhere; this is the consumer. It runs on the interpret output AFTER claim
    extraction, which is the only place both representations of the same
    declaration are on the table at once -- the sequence element the beat is
    resolved from, and the claim the resolve seam holds the diff to. Touching
    one and not the other is how a downgrade becomes invisible: the claim stops
    being non-rejectable while the element still says the effect already
    happened, and the Director reads the element.

    Two things move, and both must:

      * the CLAIM's scope, `effect` -> `intent`, which is what
        `_player_claim_findings` reads to decide a claim may not be rejected;
      * the sequence element's `commitment`, `asserted` -> `contestable`, which
        is what the reaction gate reads to decide whether the character this
        was done to gets to contest it physically. Hard mode without this is
        hard mode the cast cannot participate in.

    Nothing is deleted and nothing is rewritten. A downgraded declaration is
    still the player's words, still resolved, still narrated -- it is merely no
    longer true in advance. Returns the record of what moved, which the caller
    puts in front of the Director and on the step, so a refusal is answerable
    rather than silent.
    """
    # `normalize_player_authority` owns this vocabulary (story/scene.py): it is
    # what `player_authority` runs on the stored mode and on every history
    # entry, and it folds an unreadable value to the DEFAULT. A second copy
    # here -- a bare `str()` and a dict `.get` with the top rung as fallback --
    # answered `world_author` for any spelling the table did not hold
    # literally, so a story tightened to `actor_only` was handed the whole
    # ladder back by a capital letter.
    granted = PLAYER_AUTHORITY_GRANTS[normalize_player_authority(mode)]
    if not isinstance(out, dict):
        return []
    flow = out.get("flow")
    claims = _dict_list(flow.get("authority_claims")) if isinstance(
        flow, dict) else []
    records = []
    downgraded_elements = set()
    for claim in claims:
        kind = _claim_authority_kind(claim, player_name)
        if kind is None or kind in granted:
            continue
        claim["scope"] = "intent"
        records.append({
            "claim_id": claim.get("claim_id"),
            "kind": kind,
            "mode": mode,
            "predicate": str(claim.get("predicate") or ""),
            "source_text": str(claim.get("source_text") or ""),
        })
        # `claim:<index>:...` -- the sequence position the claim came from.
        parts = str(claim.get("claim_id") or "").split(":")
        if len(parts) >= 2 and parts[1].isdigit():
            downgraded_elements.add(int(parts[1]))
    for index, element in enumerate(_dict_list(out.get("sequence"))):
        if index not in downgraded_elements:
            continue
        if element.get("commitment") == "asserted":
            element["commitment"] = "contestable"
    return records


def _check_player_act_authority(resolved_event, declared_actions, player_name,
                                other_names=(), declared_text=""):
    """Physical acts a resolved_event gives the PLAYER that they did not declare
    (live: Elevator Adventure t63 -- the player said only "Let's get going?" and
    the Director had them take a bottle, drink from it and nod; t59 -- the player
    ASKED "I hope you don't mind if I lean on you" and the Director performed the
    leaning for them).

    Adding detail to a declared act is legitimate and is NOT flagged -- the
    Director is supposed to render an act richly. What this catches is an act
    appearing from nowhere, which then replays when the player declares it a
    beat later, so the same moment happens twice and the scene falls out of
    order.

    Two scopes, as for characters (`_check_character_act_authority`) -- but the
    second is drawn differently, because a character's latitude is not the
    player's. The Director may elaborate a character freely and is narrowed
    only on MOVEMENT; the player owns all of their conduct, so the question
    here is not "what kind of act" but "is this act the one they declared".

    * The player declared NO action this beat: any act is invented by
      construction, and the full verb list applies. Unchanged.

    * The player declared actions: rendering those richly is the Director's
      job and stays untouched however it is worded -- "pushes herself upright"
      elaborates a declared "slowly stands up" and shares not one word with it,
      so no vocabulary test can separate the two. What CAN be separated is
      WHAT the act touches. Elaboration re-describes the player's own body;
      fabrication reaches out and takes hold of the world. So this narrows to
      the one addition that is both unambiguous and consequential: the player
      given a grip on a world object their declaration never mentions.

      Live, chat 56 ("Run!") t10: the player typed `"Heh? What are we doing
      what's going on?" You look genuinely confused.` and the resolve wrote
      "her hands coming up to grip the edge of the console, fingers finding a
      lever as if to steady herself". Perception copied it into the player's
      OWN view as "I grip the console edge", the narrator rendered it as fact,
      and the player's very next input was "Which lever?!" -- the fabricated
      act replayed a beat later, which is the exact failure this guard was
      written to stop. The old blanket `if declared_actions: return []` let it
      through, and this player narrated a gesture on every single beat, so the
      guard was disarmed for the entire story.
    """
    if not player_name:
        return []
    declared_low = None
    if declared_actions:
        declared_low = " ".join(
            f"{a.get('attempt', '')} {a.get('observable', '')}"
            for a in declared_actions if isinstance(a, dict)
        ).casefold() + " " + str(declared_text or "").casefold()
    warnings = []
    all_names = [player_name] + [
        n for n in (other_names or []) if n and n != player_name]
    for sentence, subject in _sentence_subjects(resolved_event, all_names):
        if subject != player_name:
            continue
        # Speech attribution ("Hinami says, ...") is not a physical act; the
        # quote itself is guarded separately by the dialogue_log check and by
        # `_check_prose_quote_authority`.
        without_quotes = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
        tail = _strip_subject(without_quotes, subject)
        # Per conjunct, not three words from the subject: one subject governs
        # several verbs, and a window measured from the name sees only the
        # first (see `_predicate_heads`).
        for head, clause in _predicate_heads(tail, 3):
            if declared_low is None:
                if not re.search(cue_boundary_pattern(_ling("_PLAYER_ACT_VERBS")), head, re.I):
                    continue
                detail = ""
            else:
                noun = _undeclared_world_object(clause, declared_low)
                if not noun:
                    continue
                detail = f" (undeclared hold on {noun!r})"
            warnings.append(
                "Player act not declared this beat (player-act authority)"
                f"{detail}: {sentence[:120]!r}"
            )
            break
    return warnings


def _check_player_contact_authority(contact_ops, declared_actions, player_name,
                                    standing_ids=(), cast=()):
    """Contacts a resolve gives the PLAYER'S OWN BODY to perform.

    THE SECOND DOOR ON THE SAME RULE. `_check_player_act_authority` holds the
    boundary in `resolved_event`, and holds it well -- but prose is not the
    only channel that can say the player did something. `state_diff.contact_ops`
    stores an ACTOR, and an op naming the player there asserts that the player
    moved a part of their body, whatever the prose says.

    Measured live (chat 95 t40). The player wrote: `"H-how about the full
    thing..." You lie back on the bed. "W-would you like to sit on my face?"`
    -- one declared act, lying back, and an invitation phrased as a question.
    The prose was clean and the guard passed it (`player_act_warnings: null`),
    because the prose correctly has MIRELLE lower herself. The contact channel
    then wrote `Hinami.tongue -> Mirelle.vulva, press, moving`, and it
    committed. An invitation became the player performing, in the same beat.

    THE PLAYER IS THE ACTOR OR THEY ARE NOT, and the ledger already stores
    which. An op where the player is the TARGET is somebody else's conduct --
    a body pressing against theirs, or forcing its way in -- and the engine
    owns all of it; none of that is checked here. What the player does with
    their own tongue, and how their own mouth moves, is theirs.

    Elaboration stays legitimate, exactly as in the prose check, and the test
    is REACH rather than vocabulary: a declared act that reaches this body
    licenses the Director to render what that contact involves, however
    differently worded. Measured against the same run -- t23 declared "slide
    the shoulder straps of Mirelle's chemise" and got `hand -> upper arm`;
    t35 declared "clamp thighs around Mirelle's head" and got `vulva ->
    Mirelle`; t32 declared "run fingers through Mirelle's hair" with an EMPTY
    `targets` list. All three reach Mirelle and all three are correct. t40
    reaches the bed and nothing else.

    Reach is read from both places the pipeline records it, because neither
    is reliable alone: `targets` carries a display name in some beats and a
    cast id in others (t23: `['72']`), and is empty in beats whose attempt
    text names the body outright (t32).

    Returns ``[(index, warning)]`` so the caller can both report and, if a
    retry does not clear it, drop the op -- a body acting without its owner
    is not a soft property.
    """
    if not player_name or not isinstance(contact_ops, list):
        return []
    ids = {str(i) for i in (standing_ids or [])}
    reached, folded_player = set(), str(player_name).strip().casefold()
    by_id = {}
    for entry in (cast or []):
        if not isinstance(entry, dict):
            continue
        sheet = entry.get("sheet")
        name = (character_name_from_text(sheet) if isinstance(sheet, str)
                else character_name(sheet or {}))
        if entry.get("id") is not None and name:
            by_id[str(entry["id"])] = name.strip().casefold()
    for act in (declared_actions or []):
        if not isinstance(act, dict):
            continue
        for target in (act.get("targets") or []):
            token = str(target).strip()
            reached.add(by_id.get(token, token.casefold()))
        text = " ".join(str(act.get(k) or "") for k in
                        ("attempt", "observable", "verb")).casefold()
        for name in by_id.values():
            # ANY PART OF THE NAME REACHES THE BODY. Declarations use the
            # spelling a person would -- t32's "run fingers through Mirelle's
            # hair" names her as surely as the full "Mirelle Sulmirath" does,
            # and requiring the whole string read that beat as reaching nobody.
            if name and (name in text or any(
                    len(part) >= 4 and part in text for part in name.split())):
                reached.add(name)
    out = []
    for index, op in enumerate(contact_ops):
        if not isinstance(op, dict):
            continue
        if str(op.get("op") or "add").strip().casefold() not in ("add", "change"):
            continue
        if str(op.get("actor") or "").strip().casefold() != folded_player:
            continue
        target = str(op.get("target") or "").strip()
        if not target or target.casefold() == folded_player:
            continue
        # BODIES ONLY. This is the rule about one person's conduct on another,
        # and a bed is not a person: lying back on it, or a back arching
        # against it, is posture the world resolves. Restricting the check to
        # registered bodies is also what keeps it from firing on the furniture
        # every reclining beat carries (chat 95 t30, t40).
        if target.casefold() not in set(by_id.values()):
            continue
        if target.casefold() in reached:
            continue
        # A standing hold re-stated is not a new act; only a contact this beat
        # INVENTS is one. Matched by the contact's own endpoints as well as by
        # a stored id: an encoder's op carries no `contact_id`, so an id match
        # alone read every restated hold as invented.
        if str(op.get("contact_id") or "") in ids or contact_id(op) in ids:
            continue
        out.append((index, (
            "Player contact not declared this beat (player-act authority): "
            "%s's %s -> %s's %s. The player declared nothing reaching %s."
            % (player_name, op.get("actor_part") or "body", target,
               op.get("target_part") or "body", target))))
    return out
