"""Character decision agent."""

from __future__ import annotations

import json
import re
import time
from collections import deque

from mind import affect
from mind.affect import (CRISIS_STRAIN_MIN, INTENT_DORMANT_AFTER,
                    RUPTURE_FORCE_AFTER, ground_tells)
from core.db import q, wget
from language_runtime import compositor_text, linguistic
from story.character_schema import (
    cast_entity_id,
    character_name_from_text,
    character_abilities,
    character_embodiment_capabilities,
    character_extra_parts,
    character_curiosity,
    character_interoception,
    character_name,
    character_projects,
    character_psychology,
    character_standing_intentions,
    effective_drive,
    character_public_history,
    character_sampler,
    character_senses,
    character_temperature,
    character_tier,
    character_voice,
    senses_as_text,
)
from core.frames import is_recognized_in_frame
from world.gaps import interim_for
from mind.memory import (
    build_character_memory_context,
    contrast_memory,
    knowledge_for_character,
    payload_legacy,
    provenance_context_label,
    relationships_for_payload,
)
from llm.prompts import character_prompt, get_prompt
from story.scene import (
    NON_AWAKE_GATED,
    active_transformations,
    all_cast_name_to_id,
    awareness_of,
    dialogue_budget,
    get_scene,
    persona_of,
    transformed_sheet,
    private_knowledge_for,
    sheet_state,
)
from llm.schemas import validate_llm_output
from world.spatial import (contact_phrase, contacts_of, corridor_sightlines, room_of,
                     spatial_digest, speech_articulation_impediment,
                     sprint_reach, visible_adjacent_rooms)
from world.survival import vitals_of
from world.place_purpose import (affords_here, felt_needs, here_affords,
                           place_options)
from mind.psychology_runtime import cognitive_absorption
from mind.theory_of_mind import mind_models_for_payload, sheet_capacity

from .common import (
    _agent_json,
    _books,
    declared_goal,
    observer_label_fn,
    observer_name_scrub,
    scrub_names_deep,
    _char_known_tags,
    _dict,
    _list,
    _normalize_character_output,
    _word_shingles,
    assign_event_ids,
    attire_view,
    compact_attire,
    extra_parts_lines,
    cap_mind_model_updates,
    character_room,
    norm_sequence,
    player_speech_lines,
)

def _ling(name):
    return linguistic("agents.character", name)

def _merge_standing_intentions(authored, emergent):
    """Merge a character's authored standing intentions with the emergent ones
    formed at runtime. Authored intentions are always present (the character's
    defining goals), but an emergent intention whose text closely restates an
    authored one SUPERSEDES it -- the emergent copy carries live progress/status
    (including a `blocked`/nonviable state), so a goal the world has closed does
    not reappear as freshly-active. De-dup is by casefolded intent text."""
    emergent = [i for i in (emergent or []) if isinstance(i, dict)]
    seen = {str(i.get("intent") or "").strip().casefold() for i in emergent}
    kept_authored = [
        a for a in (authored or [])
        if isinstance(a, dict)
        and str(a.get("intent") or "").strip().casefold() not in seen
    ]
    return kept_authored + emergent


def _recent_self_lines(chat_id, char_name, current_turn_idx, n_turns=6, cap=6,
                       frame_id=None):
    """The character's own most-recent spoken lines, verbatim, oldest->newest,
    from the last few committed turns' director_resolve dialogue_log.

    Without this the character agent only ever sees the CURRENT beat plus its
    static sheet, so a character in a standing situation (an escort repeating
    'keep moving' at a checkpoint that will not clear) re-derives the same line
    turn after turn -- verbatim repetition reads as a broken machine. Feeding
    its own recent lines lets it notice the refrain and vary or escalate
    (through specificity/consequence, per the character prompt), never as an
    emotional-volume spike.

    The window is six beats because three was measurably too short: a live
    character reissued a line verbatim from four beats back, which the window
    could not show it, while the narrator's own repetition check (which reads
    four turns of prose) caught it downstream, where nothing can act on it --
    dialogue fidelity requires the narrator to render quotes exactly as
    declared."""
    if current_turn_idx is None:
        return []
    rows = q(
        "SELECT t.idx AS idx, v.content AS content FROM turns t "
        "JOIN steps s ON s.turn_id=t.id AND s.key='director_resolve' "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx < ? AND t.frame_id IS ? "
        "ORDER BY t.idx DESC LIMIT ?",
        (chat_id, current_turn_idx, frame_id, n_turns),
    )
    cf = str(char_name or "").casefold()
    lines = []
    for r in rows:
        try:
            dr = json.loads(r["content"])
        except (TypeError, ValueError):
            continue
        for d in (dr.get("dialogue_log") or []):
            if str(d.get("speaker") or "").casefold() == cf:
                quote = str(d.get("exact_quote") or "").strip()
                if quote:
                    lines.append({"turn": r["idx"], "said": quote})
    lines.sort(key=lambda x: x["turn"])
    return lines[-cap:]


def _recent_self_moves(chat_id, char_id, current_turn_idx, n_turns=12, cap=12,
                       frame_id=None):
    """Recent conversational jobs this character selected, oldest->newest.

    Lines answer *what words did I use?*  They do not answer *what was I
    trying to do by saying them?*  In live chat 38 the Doctor could see
    ``Saturn's rings or those dragons?`` in recent_self_lines and still chose
    "propose an entirely new destination to break repetition" -- substituting
    Calufrax while repeating the same post-shrine offer.  The selected
    response and enacted goal already record that semantic move.  Project a
    bounded ledger from immutable active variants instead of inventing another
    mutable state table, so rerolls and existing stories get it immediately.
    """
    if current_turn_idx is None:
        return []
    try:
        lower = max(0, int(current_turn_idx) - max(1, int(n_turns)))
    except (TypeError, ValueError):
        return []
    rows = q(
        "SELECT t.idx AS idx,s.key AS step_key,v.content AS content "
        "FROM turns t JOIN steps s ON s.turn_id=t.id "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx>=? AND t.idx<? AND t.frame_id IS ? "
        "AND (s.key='interaction_loop' OR s.key=?) "
        "ORDER BY t.idx,s.key",
        (chat_id, lower, current_turn_idx, frame_id, f"character:{char_id}"),
    )
    by_turn = {}
    for row in rows:
        try:
            content = json.loads(row["content"])
        except (TypeError, ValueError):
            continue
        if row["step_key"] == "interaction_loop":
            results = content.get("character_results") or {}
            result = results.get(str(char_id)) or results.get(char_id)
        else:
            result = content
        if not isinstance(result, dict):
            continue

        candidates = [
            item for item in (result.get("response_candidates") or [])
            if isinstance(item, dict) and item.get("selected")
        ]
        move = str((candidates[0].get("response") if candidates else "") or "").strip()
        # Derived, not read: the template stopped asking for active_state.goal
        # (commit overwrote it with the enacted want's text on 99.0% of
        # measured calls), so the ledger derives the same text from
        # wants[enacted].want -- and still reads the legacy field off variants
        # stored before the change.
        goal = declared_goal(result)
        said = _speech_texts(result)
        if not (move or goal or said):
            continue
        interaction = result.get("interaction") or {}
        # THE ASK IS ITS OWN JOB, recorded apart from what the beat was busy
        # doing. `move` holds the SELECTED RESPONSE, and a character who asks
        # something while cooking writes the cooking there -- so a repeated
        # question hides inside three different-sounding moves and neither
        # guard can see it.
        #
        # Live, chat 59 t152-t154. Tamamo asked the Doctor for his impression
        # of the hall on three consecutive beats -- "Tell us, Doctor. What does
        # it seem to you?", "What stands out most to you, Doctor?", "Doctor, a
        # traveler sees many halls. What does this one reveal to you?" -- after
        # Hinami had already asked it and he had already answered. Her ledger
        # held all of it. `_first_repeated_move` returned None, because the
        # moves it compared were "continue preparing the meal at the hearth"
        # and "lightly reassure Hinami and acknowledge the home compliment";
        # the exact-line guard found nothing, because the three are lexical
        # paraphrases sharing almost no wording.
        asked = [line[:200] for line in said if "?" in line]
        entry = {
            "turn": row["idx"],
            **({"move": move[:320]} if move else {}),
            **({"goal": goal[:240]} if goal else {}),
            **({"said": [line[:320] for line in said[-2:]]} if said else {}),
            **({"asked": asked[-2:]} if asked else {}),
            "expected_answer": bool(
                isinstance(interaction, dict)
                and interaction.get("expects_response")
            ),
        }
        # A loop result is the complete merged declaration and therefore wins
        # over a parallel character step if legacy data happens to hold both.
        if row["step_key"] == "interaction_loop" or row["idx"] not in by_turn:
            by_turn[row["idx"]] = entry
    return [by_turn[idx] for idx in sorted(by_turn)][-cap:]


# Repeated letters collapse so "Mmm" and "Mmmm" are one opener, which is
# exactly the kind of near-miss a model uses to feel like it varied.
_REFRAIN_RUN_RE = re.compile(r"(.)\1{2,}")
_REFRAIN_MIN_LINES = 3


def _self_line_tokens(line):
    return _ling("_REFRAIN_WORD_RE").findall(
        _REFRAIN_RUN_RE.sub(r"\1\1", str(line or "").lower()))


def _addressed_names_include(chat_id, addressed, folded_name):
    """Does this cast-id/name list from `flow.addressed_to` mean this body.

    The field holds ids on most beats and names on some; both forms are
    resolved here so a caller never has to know which it got.
    """
    if not addressed:
        return False
    if folded_name in addressed:
        return True
    for ref in addressed:
        if not str(ref).isdigit():
            continue
        row = q("SELECT COALESCE(cc.sheet, ch.sheet) AS sheet FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id "
                "WHERE cc.chat_id=? AND cc.char_id=?",
                (chat_id, int(ref)), one=True)
        if not row:
            continue
        try:
            if character_name_from_text(row["sheet"]).casefold() == folded_name:
                return True
        except Exception:
            continue
    return False


def _lines_delivered_to(char_id, rows):
    """Per turn, the prose THIS mind is recorded as having received.

    Three stores, all written by gates that already ran: the composed
    per-observer view (`perception_act` / `perception_outcome`, keyed by
    perceiver id, `None` when a mind was admitted nothing), and the
    micro-round's `delivered_views`, which `deterministic_micro_perception`
    fills through `_delivery_ok` per observer per element. Read together they
    are the engine's own answer to "what words reached this mind on this
    beat", and no other reader needs to re-derive it.
    """
    key = str(char_id)
    heard = {}
    for row in rows:
        if row["step_key"] == "director_interpret":
            continue
        try:
            content = json.loads(row["content"]) or {}
        except (TypeError, ValueError):
            continue
        parts = []
        view = (content.get("views") or {}).get(key)
        if isinstance(view, str):
            parts.append(view)
        for rnd in content.get("rounds") or []:
            if not isinstance(rnd, dict):
                continue
            delivered = (rnd.get("delivered_views") or {}).get(key)
            if isinstance(delivered, str):
                parts.append(delivered)
            elif isinstance(delivered, list):
                parts.extend(str(item) for item in delivered)
        if parts:
            heard.setdefault(int(row["idx"]), []).extend(parts)
    return {idx: "\n".join(parts) for idx, parts in heard.items()}


def _unanswered_question_note(chat_id, char_name, char_id, current_turn_idx,
                              frame_id, n_turns=3):
    """`{"awaiting_your_answer": {...}}` when somebody asked THIS character
    something, they received it, and they have not spoken since.

    The engine already knows this and told nobody. `interaction.expects_response`
    is declared on every character result and consumed in exactly one place --
    `_recent_self_moves`, as `expected_answer`, which tells a character *I*
    asked something. Nothing told a character that somebody asked *them*.

    Live, chat 38 t144-t147: the player stayed silent for four turns so the
    Doctor and Tamamo could talk. Tamamo asked him a direct question on three
    consecutive beats ("tell me yourself -- what purpose brings...", "describe
    its dimensional nature in your own terms", "Name one way its dimensions
    interface with established boundaries"). On the last two he said nothing
    at all, and his own reasoning is on the record: he KNEW about the question
    (it is in his `observations_used`, from memory) and selected "remain
    silent and observant to honor etiquette and give Tamamo room to respond",
    rejecting "offer one terse clarifying remark" at inhibition 0.4. Both
    characters were waiting for the other; Tamamo filled the gap with more
    questions and by turning back to the silent player.

    Nothing was wrong with either mind. What was missing was the fact that a
    question was outstanding and it was his. Presence is the signal, like
    `_player_silence_note` beside it -- the field is absent on any beat where
    nothing is owed.

    A DEBT IS MADE BY A LINE THAT REACHED THIS MIND, never by the asker's
    intent to address it. `expects_response` + `addresses` (and, for the
    player, `flow.addressed_to`) say who somebody MEANT to ask; they say
    nothing about whether it was heard, and this note read nothing else -- so
    a question put through a shut door arrived here verbatim, three turns
    deep, for a mind perception had correctly told nothing. Every candidate
    now has to appear in `_lines_delivered_to`, the record of what this mind
    was actually handed, which is also what picks WHICH line is owed: a
    concealed aside after an overt question is not this mind's line, and a
    line that arrived muffled arrived as a fragment rather than as words.
    """
    if current_turn_idx is None or not char_name or char_id is None:
        return {}
    try:
        lower = max(0, int(current_turn_idx) - max(1, int(n_turns)))
    except (TypeError, ValueError):
        return {}
    rows = q(
        "SELECT t.idx AS idx,s.key AS step_key,v.content AS content "
        "FROM turns t JOIN steps s ON s.turn_id=t.id "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx>=? AND t.idx<? AND t.frame_id IS ? "
        "AND s.key IN ('director_interpret','interaction_loop','reaction_loop',"
        "'perception_act','perception_outcome') "
        "ORDER BY t.idx, CASE s.key WHEN 'director_interpret' THEN 0 ELSE 1 END",
        (chat_id, lower, current_turn_idx, frame_id),
    )
    heard = _lines_delivered_to(char_id, rows)

    def _reached(text, idx):
        """Was this line among the words this mind was handed on that beat?
        Verbatim, because that is how a full-fidelity delivery renders a
        quote: a muffled fragment or a contentless trace does not contain the
        line, and a withheld one leaves no view at all."""
        line = str(text or "").strip()
        return bool(line) and line in (heard.get(int(idx)) or "")

    folded = str(char_name).casefold()
    asked = None
    for row in rows:
        try:
            content = json.loads(row["content"]) or {}
        except (TypeError, ValueError):
            continue
        # THE PLAYER ASKING COUNTS TOO, and it was the larger half: 809 beats
        # in the stored corpus carry player speech aimed at a named character,
        # 363 of them containing a question. Read from the Director's own
        # `flow.addressed_to`, which is where "who did the player mean" is
        # already decided, rather than re-deciding it here. The player has no
        # character result, so the loop below could never see them.
        #
        # Ordered before the loop steps of the same turn (see the CASE in the
        # query), because the player declares first and a character answering
        # in that same beat clears it.
        if row["step_key"] == "director_interpret":
            spoken = player_speech_lines(content)
            if not spoken:
                continue
            addressed = [str(a).casefold() for a in
                         ((content.get("flow") or {}).get("addressed_to_refs")
                          or (content.get("flow") or {}).get("addressed_to") or [])]
            # `addressed_to` is a cast-id list; resolve through the name the
            # caller already holds by asking the roster, not by matching ids.
            if not _addressed_names_include(chat_id, addressed, folded):
                continue
            # Per LINE, not per declaration: a declaration may carry a
            # concealed element beside an overt one, and the whole string is
            # what used to be copied. Only lines this mind received can be
            # owed by it.
            reached = [line for line in spoken if _reached(line, row["idx"])]
            # A statement aimed at somebody is not a debt. For the player the
            # question mark IS the available test -- there is no
            # `expects_response` on a player declaration, and inventing one
            # would mean guessing at intent the Director never recorded.
            reached = [line for line in reached if "?" in line]
            if not reached:
                continue
            asked = {"from": "the player", "asked": str(reached[-1])[:240],
                     "turns_ago": int(current_turn_idx) - int(row["idx"])}
            continue
        results = (content.get("character_results")
                   or content.get("reaction_results") or {})
        if not isinstance(results, dict):
            continue
        for result in results.values():
            if not isinstance(result, dict):
                continue
            speaker = str(result.get("name") or "").strip()
            said = [e.get("text") for e in (result.get("sequence") or [])
                    if isinstance(e, dict) and e.get("type") == "speech"
                    and e.get("text")]
            # THIS character speaking clears the debt, whatever they said. An
            # answer need not be responsive to count as having spoken; whether
            # it was a real answer is the asker's business, not a field's.
            if speaker.casefold() == folded:
                if said:
                    asked = None
                continue
            interaction = result.get("interaction")
            if not isinstance(interaction, dict):
                continue
            # `expects_response` + `addresses` is the engine's OWN answer to
            # "was this put to them". Deliberately not a question mark: the
            # asks in the live case were imperatives -- "describe its
            # dimensional nature in your own terms", "Name one way its
            # dimensions interface with established boundaries" -- and
            # punctuation would have missed every one of them.
            if not interaction.get("expects_response"):
                continue
            addresses = [str(a).casefold()
                         for a in (interaction.get("addresses") or [])]
            if folded not in addresses:
                continue
            # The LAST line this mind received from them, which is not
            # necessarily their last line: an overt question followed by a
            # concealed aside used to be reported as the aside, because the
            # element list was filtered on `type == "speech"` and nothing
            # else. Nothing received, nothing owed.
            reached = [line for line in said if _reached(line, row["idx"])]
            if not reached:
                continue
            asked = {"from": speaker, "asked": str(reached[-1])[:240],
                     "turns_ago": int(current_turn_idx) - int(row["idx"])}
    return {"awaiting_your_answer": asked} if asked else {}


def _player_quiet_beats(chat_id, current_turn_idx, frame_id, chat, cap=8):
    """How many consecutive beats up to and including this one the player has
    not spoken on. 1 means only this beat.

    Read from stored `director_interpret` rather than tracked in state: it is a
    pure function of what is already recorded, so it is correct on a rerun and
    on an imported archive without a migration.
    """
    if current_turn_idx is None:
        return 1
    try:
        lower = max(0, int(current_turn_idx) - cap)
    except (TypeError, ValueError):
        return 1
    rows = q(
        "SELECT t.idx AS idx,v.content AS content "
        "FROM turns t JOIN steps s ON s.turn_id=t.id AND s.key='director_interpret' "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx>=? AND t.idx<? AND t.frame_id IS ? "
        "ORDER BY t.idx DESC",
        (chat_id, lower, current_turn_idx, frame_id),
    )
    beats = 1
    for row in rows:
        try:
            spoke = str((json.loads(row["content"]) or {}).get("speech") or "").strip()
        except (TypeError, ValueError):
            break
        if spoke:
            break
        beats += 1
    return beats


def _player_silence_note(sc, chat, sh, spoke, quiet_beats=0):
    """`{"player_said_nothing": True}` when the player is here and did not speak.

    Absent otherwise -- when they spoke, and when they are not in the room,
    since a character elsewhere has no standing to know either way. Omitted
    rather than set False, so its presence IS the signal and a beat that says
    nothing about it reads as an ordinary one.

    `quiet_beats` is how many CONSECUTIVE beats they have now been silent for,
    because one is not the same event as four. A player who goes quiet mid-
    exchange is doing something, and the prompt rightly asks the character to
    read it. A player who has been quiet for four beats has stepped back to
    watch, and reading it afresh every beat is what produced "Hinami, you have
    gone quiet after such proud words" followed by "Hinami, your presence here
    is a quiet joy" -- attention pulled back to somebody who deliberately left
    the room to the others.
    """
    if spoke:
        return {}
    try:
        player = character_name(persona_of(chat))
    except Exception:
        return {}
    if not player:
        return {}
    positions = (sc or {}).get("positions") or {}
    here = positions.get(character_name(sh))
    if not here or positions.get(player) != here:
        return {}
    note = {"player_said_nothing": True, "player_name": player}
    if quiet_beats > 1:
        note["player_quiet_for_beats"] = quiet_beats
    return note


def _self_line_refrain(lines):
    """The SHAPE this character's recent lines keep reusing, or None.

    AVOID SELF-REPETITION in the character prompt targets repeated content,
    and explicitly exempts a consistent register -- rightly, since a character
    who says "pet" is being themselves. But that exemption is a hole a
    template walks straight through: measured live, one character opened nine
    consecutive lines the same way and closed six of eight the same way, with
    genuinely fresh content in between every time. Each line passed the
    content test; the effect on the page was a stuck record, and it got worse
    when the window widened, because more examples of a skeleton read as
    stronger evidence of the register the rule blesses.

    So the skeleton is computed here rather than left to the model to notice
    about itself: the first and last significant word of each line, reported
    when one recurs across at least `_REFRAIN_MIN_LINES` of them and at least
    half. Deterministic, and stated read-side -- it names the pattern and
    leaves what to do about it to the character.
    """
    tokenized = [t for t in (_self_line_tokens(x.get("said") if isinstance(x, dict)
                                               else x) for x in (lines or [])) if t]
    if len(tokenized) < _REFRAIN_MIN_LINES:
        return None
    total = len(tokenized)
    out = {}
    for slot, index in (("opening", 0), ("closing", -1)):
        counts = {}
        for t in tokenized:
            counts[t[index]] = counts.get(t[index], 0) + 1
        word, hits = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
        if hits >= _REFRAIN_MIN_LINES and hits * 2 >= total:
            out[slot] = {"word": word, "lines": hits, "of": total}
    return out or None


def _speech_texts(result):
    """This beat's declared spoken lines, from whichever shape carries them."""
    if not isinstance(result, dict):
        return []
    texts = [str(e.get("text") or "")
             for e in (result.get("sequence") or [])
             if isinstance(e, dict) and e.get("type") == "speech"]
    if not texts and result.get("speech"):
        texts = [str(result.get("speech"))]
    return [t for t in texts if t.strip()]


def _normalized_line(text):
    return " ".join(_ling("_REFRAIN_WORD_RE").findall(str(text or "").lower()))


# Spoken lines this short are interjections; see _first_verbatim_repeat.
_INTERJECTION_WORDS = 3


def _first_verbatim_repeat(new_texts, recent_texts):
    """A line this beat reissues from the character's own recent speech, or None.

    `recent_self_lines` and the AVOID SELF-REPETITION rule are advisory, and
    advice is not a guarantee: measured live, a character was handed its own
    previous line in that very field and emitted it back word for word on the
    next beat. The window worked; nothing checked the answer.

    Distinct from `_self_line_refrain`, which catches a reused sentence SHAPE
    carrying fresh content. This catches the plain case that one deliberately
    does not -- the same words again -- and the two miss each other's failure
    completely, so both are needed.

    Matches on normalized equality (punctuation and case are not variation) or
    on two shared six-word runs, the same threshold the narrator's own
    repetition check uses: two of those essentially cannot co-occur by accident
    in speech this short.
    """
    previous = [(t, _normalized_line(t), _word_shingles(t))
                for t in (recent_texts or []) if str(t or "").strip()]
    if not previous:
        return None
    for text in (new_texts or []):
        norm = _normalized_line(text)
        if not norm:
            continue
        # An INTERJECTION is not a reissued line. "Mm.", "Right.", "I see." --
        # 9.2% of the corpus's 14,365 spoken lines are three words or fewer,
        # and saying one of them twice in a story is how people talk, not the
        # failure this guard was built for (a character handed its own previous
        # line and emitting it back word for word). Without a floor, one
        # repeated monosyllable bought a full second character call: ~30k
        # tokens and 38-55s, measured. Its sibling `_first_repeated_move`
        # already declines to judge anything under five tokens; this is the
        # same floor, and the omission here was an asymmetry rather than a
        # decision. The shingle branch below is unaffected either way -- two
        # shared SIX-word runs cannot occur in a three-word line.
        if len(_self_line_tokens(text)) <= _INTERJECTION_WORDS:
            continue
        shingles = _word_shingles(text)
        for original, prev_norm, prev_shingles in previous:
            if norm and norm == prev_norm:
                return original
            if len(shingles & prev_shingles) >= 2:
                return original
    return None


def _selected_move_text(result):
    """The semantic response selected in one character result."""
    if not isinstance(result, dict):
        return ""
    for item in result.get("response_candidates") or []:
        if isinstance(item, dict) and item.get("selected"):
            text = str(item.get("response") or "").strip()
            if text:
                return text
    return ""


# Where a re-ask separates from a genuinely new question. Calibrated on the
# chat 59 t152-t154 case and its neighbours: the three paraphrases of "what do
# you make of this hall" score 0.600-0.667 against each other, while distinct
# questions from the same character in the same window score 0.200-0.400.
#
# Swept over the whole stored corpus: 594 beats where a character asked
# something, 47 flagged at this threshold (7.9%), and inspecting them by hand
# roughly half are genuine re-asks -- including the documented Saturn/dragons
# loop, which scores 1.00. The rest share a question SKELETON without sharing
# a subject ("Those shifting bands - what do they look like to you" against
# "What does it taste like?").
#
# Left at 0.5 rather than tightened, deliberately. This opens a bounded
# contextual review, it does not veto a line (AGENTS.md: "semantic similarity
# opens one contextual review; it is not proof of bad repetition"), so the
# cost of a false positive is one paragraph of prompt and the cost of a miss
# is the failure this exists for. Raising to 0.6 would halve the flags
# (83 -> 34 near-miss pairs) and still catch the live case -- but only just:
# it scores 0.600 exactly, so a slightly looser paraphrase would fall under.
# If the reviews start reading as churn, 0.6 is the next stop and the reason
# to move is measured, not guessed.
_REPEATED_ASK_THRESHOLD = 0.5



def _first_repeated_move(result, recent_moves, threshold=0.4):
    """A recent selected conversational move closely restated this beat.

    This deliberately compares deliberation summaries, not dialogue strings.
    ``claim_similarity`` is conservative and only triggers on substantial
    lexical overlap; the ledger in the prompt handles broader semantic
    continuity, while this is the deterministic floor for the measured case
    where the model itself wrote "new destination to break repetition".
    """
    current = _selected_move_text(result)
    if len(_self_line_tokens(current)) >= 5:
        for prior in reversed(recent_moves or []):
            if not isinstance(prior, dict):
                continue
            previous = str(prior.get("move") or "").strip()
            if len(_self_line_tokens(previous)) < 5:
                continue
            if affect.claim_similarity(current, previous) >= threshold:
                return {
                    "turn": prior.get("turn"),
                    "move": previous,
                    "current": current,
                }
    # ASKING THE SAME THING AGAIN IS A REPEATED MOVE, even when the beat around
    # it is different. Compared question-to-question rather than against
    # `move`, because the move records what the character was DOING and the
    # repetition lives in what they were asking (see `_recent_self_moves`).
    #
    # A lower threshold than the move comparison: two moves are prose
    # summaries with plenty of incidental shared vocabulary, while two
    # questions restating one request often share almost none -- "Tell us,
    # Doctor. What does it seem to you?" against "What stands out most to you,
    # Doctor?" -- so the same bar would never fire on the case this exists for.
    current_asks = [line for line in _speech_texts(result) if "?" in line]
    for ask in current_asks:
        if len(_self_line_tokens(ask)) < 4:
            continue
        for prior in reversed(recent_moves or []):
            if not isinstance(prior, dict):
                continue
            for earlier in (prior.get("asked") or []):
                if len(_self_line_tokens(earlier)) < 4:
                    continue
                if affect.claim_similarity(ask, earlier) >= _REPEATED_ASK_THRESHOLD:
                    return {
                        "turn": prior.get("turn"),
                        "move": f"asked the same thing: {earlier}",
                        "current": ask,
                    }
    return None


def _nonsteering_intention_refs(result, intentions, turn_idx):
    """Known but non-steering intention ids cited by this decision."""
    known = {
        str(item.get("id") or "")
        for item in intentions or [] if isinstance(item, dict) and item.get("id")
    }
    steering = affect.steering_intent_ids(intentions, turn_idx)
    spent = known - steering
    if not spent or not isinstance(result, dict):
        return []

    refs = []
    active = result.get("active_state") or {}
    if isinstance(active, dict):
        refs.extend(
            str(want.get("serves") or "").strip()
            for want in (active.get("wants") or []) if isinstance(want, dict)
        )
    for candidate in result.get("response_candidates") or []:
        if not isinstance(candidate, dict) or not candidate.get("selected"):
            continue
        refs.extend(str(value or "").strip()
                    for value in (candidate.get("serves") or []))

    normalized = set()
    for ref in refs:
        for prefix in ("intention:", "intent:"):
            if ref.casefold().startswith(prefix):
                ref = ref[len(prefix):].strip()
                break
        if ref in spent:
            normalized.add(ref)
    return sorted(normalized)


def _sanitize_nonsteering_intention_refs(result, invalid_refs):
    """Prevent a rejected spent aim from persisting as next beat's steering."""
    invalid = {str(value) for value in invalid_refs or []}
    if not invalid or not isinstance(result, dict):
        return result
    active = result.get("active_state") or {}
    bad_wants = []
    if isinstance(active, dict):
        for want in active.get("wants") or []:
            if not isinstance(want, dict):
                continue
            ref = str(want.get("serves") or "").strip()
            if ref in invalid or ref.removeprefix("intention:") in invalid:
                bad_wants.append(str(want.get("want") or ""))
                want["serves"] = "situational"
        goal = str(active.get("goal") or "")
        if bad_wants and any(
                affect.claim_similarity(goal, text) >= 0.4
                for text in bad_wants if text):
            active["goal"] = ""
    for candidate in result.get("response_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        candidate["serves"] = [
            value for value in (candidate.get("serves") or [])
            if str(value) not in invalid
            and str(value).removeprefix("intention:") not in invalid
        ]
    return result


# ---- Unbidden recall: one contrasting memory for a measurably stuck mind ----
#
# The three repetition mechanisms above (`recent_self_lines`, the refrain
# skeleton, the verbatim-repeat rewrite) all say "not that". This is the one
# mechanism that says "here is something else you own": when the SAME
# deterministic signals that measure stuck-ness fire, exactly one high-salience
# memory DISSIMILAR to the current beat is surfaced into the memory context,
# marked as arriving on its own (`it_comes_back_to_me`), substituting for one
# ordinary recall slot so the payload budget stays constant. What to do with
# it -- or whether to ignore it -- stays the character's, the recalled_places
# contract: the option must exist, the refusal may be theirs.

# Beats that must pass after an injection before another may fire.
_UNBIDDEN_COOLDOWN_BEATS = 5
# Above this absorption the mind has no room for reminiscence -- the same
# tier where _recall_cap grants place-recall zero slots. A long PLATEAU
# habituates absorption back under this bar (psychology_runtime), so the
# stuck-and-saturated case this exists for regains eligibility on its own.
_UNBIDDEN_ABSORPTION_CEILING = 0.85
# Bodily plateau length that reads as stuck (the measured live case: a
# sustained stimulus with zero new wants across this many beats).
_UNBIDDEN_PLATEAU_BEATS = 3


def _barren_intent(active_annotated, stored_state):
    """Is a live intention being pressed with nothing to show for it.

    Reads the same `barren_attempts` the character's own payload carries and
    the prompt already names ("an intention at progress 1.0, or carrying
    barren_attempts, is SPENT"). Deterministic, no model, and non-mutating:
    this only asks whether the mind is measurably stuck on a goal.
    """
    st = stored_state if isinstance(stored_state, dict) else {}
    interior = st.get("interior") if isinstance(st.get("interior"), dict) else {}
    for intent in interior.get("intentions") or []:
        if not isinstance(intent, dict) or intent.get("status") != "active":
            continue
        try:
            if int(intent.get("barren_attempts") or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _unbidden_trigger(stored_state, active_annotated, refrain, turn_idx,
                      absorption):
    """(stuck_reason or None, fire: bool) -- fully deterministic, no model.

    Edge-triggered with hysteresis: after an injection the trigger must have
    been observed CLEAR before it may fire again (`clear_seen`), on top of a
    flat cooldown -- a level-triggered version would re-fire every beat of a
    long stuck stretch and become wallpaper. Two consecutive injections that
    measurably helped nothing set `suppressed` (commit's ledger), because a
    character stuck for a reason contrast cannot reach -- usually the scene
    itself offering nothing -- should stop receiving reminiscence and let the
    real cause surface. Engine-crisis machinery outranks texture: an open
    drive-rupture window suppresses unconditionally, and an awareness-gated
    mind never reaches this code because it runs no character step at all.
    """
    st = stored_state if isinstance(stored_state, dict) else {}
    active = active_annotated if isinstance(active_annotated, dict) else {}
    ledger = st.get("unbidden") if isinstance(st.get("unbidden"), dict) else {}
    hedonic = active.get("hedonic") if isinstance(active.get("hedonic"), dict) else {}
    reason = None
    if refrain:
        reason = "refrain"
    elif ledger.get("repeat_flag"):
        reason = "verbatim_repeat"
    elif _barren_intent(active_annotated, st):
        # THE SIGNAL THAT ACTUALLY CAUGHT THE LIVE CASE. A goal carrying
        # `barren_attempts` was pressed on a beat that repeated an earlier
        # move and gained nothing (`affect._advance_intent`). The three
        # negative mechanisms all missed it: her lines were not verbatim
        # repeats, their shapes varied, and the goal was neither held nor at
        # its ceiling -- she was grinding UP the ramp, which nothing measured
        # until that floor existed. It belongs here rather than in another
        # "not that" rule, because a mind repeating itself for want of a
        # better move needs an alternative offered, not a further constraint.
        reason = "barren_goal"
    elif active.get("goal_held"):
        reason = "goal_held"
    else:
        try:
            if float(hedonic.get("sustained_beats") or 0.0) \
                    >= _UNBIDDEN_PLATEAU_BEATS:
                reason = "plateau"
        except (TypeError, ValueError):
            pass
    if not reason:
        return None, False
    if absorption >= _UNBIDDEN_ABSORPTION_CEILING:
        return reason, False
    interior = st.get("interior") if isinstance(st.get("interior"), dict) else {}
    rupture = interior.get("drive_rupture")
    if isinstance(rupture, dict):
        try:
            if int(turn_idx) <= int(rupture.get("window_expires") or -1):
                return reason, False
        except (TypeError, ValueError):
            pass
    if ledger.get("suppressed"):
        return reason, False
    last = ledger.get("last_turn")
    if isinstance(last, int):
        if turn_idx - last <= _UNBIDDEN_COOLDOWN_BEATS:
            return reason, False
        if not ledger.get("clear_seen"):
            return reason, False
    return reason, True


def _unbidden_entry(mem, turn_idx):
    """The payload shape: the KEY carries the epistemic status (the
    `i_suspect` precedent) -- this arrived on its own and answers no question
    the character asked. Gist only, provenance in the same three labels the
    summary scopes already teach, no id, no score, no instruction."""
    entry = {
        "it_comes_back_to_me": mem.get("gist") or "",
        "memory_ref": mem.get("event_key") or "",
        "temporal_status": "remembered_past",
        "memory_form": "unbidden_episode",
        "non_authoritative": True,
        "from": provenance_context_label(mem.get("provenance")),
    }
    ti = mem.get("turn_idx")
    if isinstance(ti, int) and isinstance(turn_idx, int) and turn_idx > ti:
        entry["when"] = f"about {turn_idx - ti} beats ago"
    if str(mem.get("location") or "").strip():
        entry["where"] = str(mem["location"]).strip()
    return entry


def _attach_unbidden(memory_context, entry, recall_limit=8):
    """Substitute, never add: the unbidden entry pays for itself out of the
    ordinary recall budget, so total recalled material per payload is
    constant. When recall came back under budget it simply takes the spare
    slot; when full, the lowest-ranked ordinary recall yields."""
    if not isinstance(memory_context, dict):
        return
    recalled = list(memory_context.get("recalled_old_memories") or [])
    if len(recalled) >= recall_limit:
        scores = ((memory_context.get("_internal") or {}).get("scores") or {})
        drop = min(recalled, key=lambda m: float(
            scores.get(str(m.get("memory_ref") or ""), 0.0)))
        recalled = [m for m in recalled if m is not drop]
        memory_context["recalled_old_memories"] = recalled
    memory_context["surfaces_unbidden"] = entry


def _ground_observation_citations(out, observations, memory_context,
                                  memory_internal=None):
    """Make present and remembered evidence mechanically distinguishable.

    The model is given two disjoint namespaces: current observations are
    ``current:<perceiver>:<n>`` and retrieved rows use their stable
    ``event_key`` (``event:<hash>``).
    Legacy outputs used bare numeric ids or labels such as
    ``recent_episode_4479``; those are normalized only when that exact memory
    was actually delivered. Invented/stale ids are dropped. A present citation
    the model supplied is moved first; one the model omitted is never invented
    by the guard, because audit metadata must describe the model's reasoning,
    not repair it after the fact.

    Returns warning strings for observability; it never changes conduct, only
    the evidence metadata attached to the decision.
    """
    if not isinstance(out, dict):
        return []
    current = {}
    for obs in observations or []:
        if not isinstance(obs, dict):
            continue
        oid = str(obs.get("observation_id") or "").strip()
        if not oid:
            continue
        observed = obs.get("observed") if isinstance(obs.get("observed"), dict) else {}
        current[oid] = str(observed.get("text") or "").strip()
    memories = {}
    row_ids = dict((memory_internal or {}).get("row_ids") or {})
    summaries = set()
    if isinstance(memory_context, dict):
        for field in ("recent_episodes", "recent_received_information",
                      "recent_conclusions", "recalled_old_memories"):
            for mem in memory_context.get(field) or []:
                if not isinstance(mem, dict):
                    continue
                ref = str(mem.get("memory_ref") or
                          mem.get("event_key") or "").strip()
                if not ref:
                    continue
                memories[ref] = str(
                    mem.get("gist") or mem.get("details") or "").strip()
                # Unit/legacy callers may still hand this guard an author
                # projection. Production model context contains no row id.
                if mem.get("id") is not None:
                    row_ids[str(mem["id"])] = ref
        deliberate = memory_context.get("deliberate_recall") or {}
        if isinstance(deliberate, dict):
            for mem in deliberate.get("additional_episodes") or []:
                if not isinstance(mem, dict):
                    continue
                ref = str(mem.get("memory_ref") or "").strip()
                if ref:
                    memories[ref] = str(
                        mem.get("gist") or mem.get("details") or "").strip()
        unbidden = memory_context.get("surfaces_unbidden") or {}
        if isinstance(unbidden, dict):
            ref = str(unbidden.get("memory_ref") or "").strip()
            if ref:
                memories[ref] = str(
                    unbidden.get("it_comes_back_to_me") or "").strip()
        for meta in (memory_context.get("summary_citations") or {}).values():
            if isinstance(meta, dict) and meta.get("summary_id"):
                summaries.add(str(meta["summary_id"]))
        for field in ("earlier_in_my_life",):
            for item in memory_context.get(field) or []:
                if isinstance(item, dict) and item.get("summary_id"):
                    summaries.add(str(item["summary_id"]))
        origin = memory_context.get("where_i_came_from") or {}
        if isinstance(origin, dict) and origin.get("summary_id"):
            summaries.add(str(origin["summary_id"]))

    warnings = []

    def ground_refs(refs, path, *, namespace="either",
                    allow_summaries=True):
        grounded = []
        for ref in refs or []:
            if not isinstance(ref, dict):
                continue
            item = dict(ref)
            eid = str(item.get("event_id") or "").strip()
            if eid == "current" and current and namespace != "past":
                item["event_id"] = next(iter(current))
                grounded.append(item)
                continue
            allowed = ((eid in current and namespace != "past") or
                       (eid in memories and namespace != "present") or
                       (eid in summaries and namespace != "present" and
                        allow_summaries))
            if allowed:
                grounded.append(item)
                continue
            mid = None
            if eid.startswith("memory:"):
                mid = eid.split(":", 1)[1]
            elif eid.isdigit():
                mid = eid
            else:
                match = re.fullmatch(
                    r"(?:recent_episode|memory|event)_(\d+)", eid)
                if match:
                    mid = match.group(1)
            if mid in row_ids and namespace != "present":
                item["event_id"] = row_ids[mid]
                grounded.append(item)
            else:
                warnings.append(
                    f"dropped ungrounded {path} citation {eid!r}")
        return grounded

    # New output has physically separate lanes.  Split legacy mixed output on
    # input so old providers remain usable without letting the two namespaces
    # collapse again downstream.
    legacy = ground_refs(out.get("observations_used") or [], "observation")
    present = ground_refs(out.get("present_evidence_used") or [],
                          "present_evidence", namespace="present")
    past = ground_refs(out.get("memory_evidence_used") or [],
                       "memory_evidence", namespace="past")
    for ref in legacy:
        eid = str(ref.get("event_id") or "")
        target = present if eid in current else past
        if ref not in target:
            target.append(ref)
    if current:
        if not present:
            warnings.append("no delivered present observation was cited")
    out["present_evidence_used"] = present
    out["memory_evidence_used"] = past
    # Compatibility projection for commit/archive readers written before the
    # split.  The model never needs to emit this field again.
    out["observations_used"] = present + past

    # These fields all use the same EvidenceRef contract. Ground them against
    # the same delivered registry so a belief cannot cite a stale or invented
    # memory merely because it lives below a different top-level key.
    for field in ("belief_updates", "association_updates",
                  "mind_model_updates"):
        kept = []
        for index, update in enumerate(out.get(field) or []):
            if isinstance(update, dict):
                # Derived summary prose can support an answer, but may not be
                # laundered into a durable belief as if it were a fresh source.
                update["evidence"] = ground_refs(
                    update.get("evidence") or [], f"{field}.{index}.evidence",
                    allow_summaries=False)
                if update["evidence"]:
                    kept.append(update)
                else:
                    warnings.append(
                        f"dropped unsupported {field}.{index}")
        out[field] = kept

    appraisal = out.get("appraisal")
    if isinstance(appraisal, dict):
        appraisal["present_evidence"] = ground_refs(
            appraisal.get("present_evidence") or [],
            "appraisal.present_evidence", namespace="present")
        modulation = appraisal.get("memory_modulation")
        if isinstance(modulation, dict):
            modulation["evidence"] = ground_refs(
                modulation.get("evidence") or [],
                "appraisal.memory_modulation.evidence", namespace="past")
            if not modulation["evidence"]:
                modulation.update({"familiarity": 0.0, "expectation": "",
                                   "anticipatory_emotion": "",
                                   "coping_effect": 0.0,
                                   "somatic_echo": 0.0,
                                   "threat_bias": 0.0,
                                   "why": ""})
        somatic = appraisal.get("somatic_impact")
        if isinstance(somatic, dict):
            somatic["evidence"] = ground_refs(
                somatic.get("evidence") or [],
                "appraisal.somatic_impact.evidence", namespace="present")
            if not somatic["evidence"] and (
                    float(somatic.get("pain") or 0.0) > 0.0 or
                    float(somatic.get("pleasure") or 0.0) > 0.0):
                somatic["pain"] = somatic["pleasure"] = 0.0
                warnings.append("zeroed unsupported somatic appraisal")
        for index, impact in enumerate(appraisal.get("goal_impacts") or []):
            if not isinstance(impact, dict):
                continue
            impact["evidence"] = ground_refs(
                impact.get("evidence") or [],
                f"appraisal.goal_impacts.{index}.evidence",
                namespace="present")
            if not impact["evidence"]:
                impact["impact"] = 0.0
                warnings.append(
                    f"zeroed unsupported appraisal.goal_impacts.{index}")

    kept_lines = []
    for index, mark in enumerate(out.get("remember_lines") or []):
        if not isinstance(mark, dict):
            continue
        mark["evidence"] = ground_refs(
            mark.get("evidence") or [],
            f"remember_lines.{index}.evidence", namespace="present")
        if not mark["evidence"]:
            quote = re.sub(r"\s+", " ", str(mark.get("quote") or "")) \
                .strip().strip('"\'“”‘’').casefold()
            observed_id = next((oid for oid, text in current.items()
                                if quote and quote in re.sub(
                                    r"\s+", " ", text).casefold()), None)
            if observed_id:
                mark["evidence"] = [{"event_id": observed_id,
                                     "fact": "heard this line now"}]
        if mark["evidence"]:
            kept_lines.append(mark)
        else:
            warnings.append(f"dropped unsupported remember_lines.{index}")
    out["remember_lines"] = kept_lines

    kept_disputes = []
    for index, dispute in enumerate(out.get("memory_disputes") or []):
        if not isinstance(dispute, dict):
            continue
        ref = str(dispute.get("memory_ref") or "").strip()
        if ref not in memories:
            needle = " ".join(str(dispute.get("gist") or "").split()).casefold()
            hits = [key for key, text in memories.items()
                    if needle and (needle == " ".join(text.split()).casefold()
                                   or needle in " ".join(text.split()).casefold())]
            ref = hits[0] if len(hits) == 1 else ""
        dispute["evidence"] = ground_refs(
            dispute.get("evidence") or [],
            f"memory_disputes.{index}.evidence", namespace="present")
        if ref and dispute["evidence"]:
            dispute["memory_ref"] = ref
            kept_disputes.append(dispute)
        else:
            warnings.append(f"dropped ungrounded memory_disputes.{index}")
    out["memory_disputes"] = kept_disputes

    kept_effects = []
    for index, effect in enumerate(out.get("memory_effects") or []):
        if not isinstance(effect, dict):
            continue
        ref = str(effect.get("memory_ref") or "").strip()
        if ref in memories:
            kept_effects.append(effect)
        else:
            warnings.append(f"dropped ungrounded memory_effects.{index}")
    out["memory_effects"] = kept_effects
    for index, update in enumerate(out.get("relationship_updates") or []):
        if not isinstance(update, dict):
            continue
        refs = [{"event_id": eid} for eid in
                (update.get("trigger_event_ids") or [])]
        update["trigger_event_ids"] = [
            ref["event_id"] for ref in ground_refs(
                refs, f"relationship_updates.{index}.trigger_event_ids",
                allow_summaries=False)]
        if not update["trigger_event_ids"] and any(
                abs(float(update.get(axis) or 0.0)) > 0.0
                for axis in ("trust_delta", "warmth_delta", "fear_delta")):
            update["trust_delta"] = update["warmth_delta"] = 0.0
            update["fear_delta"] = 0.0
            warnings.append(
                f"zeroed unsupported relationship_updates.{index}")
    return warnings


def _known_pronouns(cast, persona, recognized, exclude=None):
    """Canonical pronouns for the people this character ALREADY KNOWS, so a
    speaker refers to others correctly instead of guessing from a name (W6 --
    Crusher said "her discovery" about a he/him character).

    Info barrier: `recognized` is the character's own relationship/mind-model
    key set, which the caller has already frame-filtered by recognition. A
    stranger in the room is deliberately absent -- you don't know an
    unfamiliar person's pronouns, and handing them over would leak identity
    the character never legitimately acquired.
    """
    sheets = []
    for row in (cast or []):
        try:
            sheets.append((json.loads(row["sheet"]).get("identity") or {}))
        except Exception:
            continue
    if isinstance(persona, dict):
        sheets.append(persona.get("identity") or {})
    out = {}
    skip = {str(n or "").strip().casefold() for n in (exclude or [])}
    known = {str(n or "").strip().casefold() for n in (recognized or [])}
    for ident in sheets:
        name = str(ident.get("name") or "").strip()
        folded = name.casefold()
        if not name or folded in skip or folded not in known:
            continue
        pronouns = ident.get("pronouns") or {}
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if clean:
            out[name] = clean
    return out


# How far back "recently" reaches. Twelve beats is long enough to contain a
# couple of honest there-and-back trips through a hub, short enough that a
# genuine lock shows inside it.
LOOP_WINDOW = 12
# A pocket is measured as a RATIO, not a room count. A fixed count of four was
# tried first and immediately missed the real thing: a lock observed live
# widened from three rooms to five as he wandered a little further each cycle,
# and five rooms over twelve beats -- every room walked twice over -- is no
# less stuck than three. Half the window is the threshold because a character
# genuinely covering ground has a ratio near 1.0, so this cannot fire on
# exploration however fast it moves.
LOOP_DENSITY = 0.5


# The verdicts, most decisive first. A character was being handed eight
# separate facts per doorway and left to aggregate them into a decision --
# work the deterministic layer can already do, and do reliably. This is the
# same principle as re-deriving perception's structured observations from the
# scrubbed prose rather than trusting the model to have agreed with itself:
# where the engine knows the answer, it should say the answer.
#
# The raw markers stay underneath. This adds a reading, it does not replace
# the evidence, and a model that wants to disagree with the reading still has
# everything it needs to.
# Ordering only. `untried` leads and the discouraging verdicts trail, but
# `proven` deliberately sits just behind `untried` rather than ahead of it:
# choosing between a way that worked and a way not yet tried is what
# curiosity is FOR, and hard-coding it here would quietly settle a question
# the character is supposed to answer.
# `unentered` sits just behind `known`: a cul-de-sac you have never looked
# inside is worse than a route (it goes nowhere) and better than ground you
# have already covered (it might hold what you are looking for).
_APPEAL_ORDER = ("UNTRIED", "proven", "unentered", "known", "circling",
                 "spent", "no way through", "closed")
# The verdicts that argue AGAINST taking an exit. For these the supporting
# counters are redundant with the verdict itself and are dropped, so that a
# discouraged door never outweighs the encouraged one beside it.
# `unentered` is deliberately absent: its supporting markers are the only
# evidence the character has about a room they have never been in.
_DISCOURAGING = frozenset({"circling", "spent", "no way through", "closed"})


def _verdict(entry, frontier_hops=None):
    """One reading of an exit, added alongside its evidence.

    `frontier_hops` grades the `known` verdict: how many rooms down that way
    the nearest door seen-but-never-taken stands, measured over the
    character's OWN place graph. The open problem it answers was observed at
    the start of every repeat maze run: each neighbouring exit `known`, none
    untried, none proven -- the verdicts had nothing to say and the character
    thrashed (north, back, north, back). Local history cannot answer "which
    known exit leads TOWARD ground I have not explored"; the graph can, and
    where the engine knows the answer it should say the answer. Folded into
    the verdict STRING and the ordering only, never a key of its own: the
    salience inversion (the right door as the lightest entry) was fixed once
    and must not be re-created by decoration.
    """
    for key, label, because in _ling("_VERDICTS"):
        if not entry.get(key):
            continue
        # A cul-de-sac you have NEVER been inside is not a spent one. `closed`
        # is a fact about where a room LEADS; it says nothing about what is
        # in it, and it was masking `untried` entirely because it sits first
        # in the precedence.
        #
        # Measured in maze arm A11 run 3. The shrine -- the thing he is in
        # the maze to reach -- is a cul-de-sac. He walked sixteen optimal
        # moves to its doorway, SAW it ("a grey-slate room with a toppled
        # bench and a still water basin, which is a shrine"), read the
        # verdict "closed -- you can see from here it has no other way out",
        # concluded "it's a dead end, so that would be a waste of time", and
        # turned around. Chamber 0603 was never entered in any run of the
        # arm. Every arrival is a cul-de-sac: you go to the shrine, the
        # bedroom, the vault BECAUSE of what is in it, not to pass through.
        if key == "visibly_no_way_through" and entry.get("untried"):
            label = "unentered"
            because = ("it has no other way out, but you have never been "
                       "inside it -- what is IN a room is a different "
                       "question from what it leads to, and things worth "
                       "reaching are usually not thoroughfares")
        detail = because
        if label == "circling" and entry.get("entered_recently"):
            detail = (f"you have been in there {entry['entered_recently']} "
                      "times in your last dozen paces")
        # The distance rides ANY verdict that has one, not only `known`.
        # Restricting it to `known` suppressed it exactly where it mattered
        # most: measured in maze arm A11, a character stood with both exits
        # discouraging -- one `spent`, one `circling` -- while the `circling`
        # one led to the ONLY frontier left in the maze, nine rooms off. He
        # was told both were bad and given no way to tell them apart, so he
        # paced the pocket. The verdict describes his history; the distance
        # describes his prospects, and a room he has circled through can
        # still be the way out.
        if isinstance(frontier_hops, int) and frontier_hops >= 1:
            if frontier_hops == 1:
                detail += ("; the room through it still has a door you have "
                           "never taken")
            else:
                detail += ("; the nearest door you have never taken lies "
                           f"about {frontier_hops} rooms down that way")
        entry["verdict"] = f"{label} — {detail}"
        if label in _DISCOURAGING:
            # These numbers all say the same thing as the verdict, and
            # together they were three times the text of the untried door
            # beside them. The verdict carries the reading; the rest were
            # crowding out the answer. Applies to every discouraging verdict,
            # not only circling -- scoped to circling alone at first, which
            # left a `no way through` exit carrying eight keys against an
            # untried one carrying four, the same imbalance one label over.
            for redundant in ("times_entered", "turned_back_here",
                              "last_seen_beats_ago"):
                entry.pop(redundant, None)
        break
    return entry


def _appeal(entry):
    # Non-dict junk is passed through untouched elsewhere, so it must sort
    # too. It trails, and `sorted` being stable keeps whatever order it
    # arrived in.
    if not isinstance(entry, dict):
        return len(_APPEAL_ORDER)
    label = str(entry.get("verdict") or "").split(" — ")[0]
    try:
        return _APPEAL_ORDER.index(label)
    except ValueError:
        return len(_APPEAL_ORDER)


def _frontier_hops(first_step, here_rid, adj, walked, closed):
    """How many rooms down that way the nearest door seen-but-never-taken
    stands: BFS over the character's own knowledge (adjacency they recorded by
    standing in rooms, walkedness from their durable graph, chambers they saw
    were closed). Returns None when everything seen down that branch is spent,
    and 0 when the branch is live but unmeasurable (a room stood in whose
    exits were never recorded -- pre-graph saves).

    Replaces a boolean. The boolean answered "is there ANY route left untried
    that way" and went mute at the start of every repeat run, when every
    neighbouring exit was known and almost every branch still held frontier
    somewhere: all True is no answer. Distance is the discriminating fact a
    person who walked the ground actually has -- "the unexplored part is off
    that way, not far" -- and it crosses no boundary, being computed entirely
    from where they stood and what they saw from there.
    """
    if first_step not in walked:
        return 0
    if first_step not in adj:
        return 0
    seen = {here_rid, first_step}
    queue = deque([(first_step, 1)])
    while queue:
        cur, depth = queue.popleft()
        for nxt in adj.get(cur, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            if nxt not in walked:
                if nxt not in closed:
                    return depth      # a door seen and never taken
                continue
            queue.append((nxt, depth + 1))
    return None


def _intent_is_live(intent, now_turn):
    """Whether an active intention still speaks for what the character wants.

    `status == "active"` is not enough on its own. Intentions outlive their
    usefulness by design -- they are spent by the world rather than closed by
    a decision -- so a character carries rows that were true fifty beats ago
    and are merely not yet swept. That is harmless for motivation, where a
    dormant row simply loses, and harmful here, because naming a chamber is
    all it takes to redirect every routed move.

    Measured in A13 run 4: `i3`, "Explore connectivity from Chamber 0504 via
    western passage", sat active at progress 0.2 long after the exploration
    it described was over, while the character's own goal named the shrine.
    Stalled and blocked rows are excluded for the same reason -- an intention
    the world has already refused is the worst possible thing to steer by.
    """
    if intent.get("stalled_turn") or intent.get("blocked_turn"):
        return False
    if not isinstance(now_turn, int):
        return True
    try:
        last = int(intent.get("last_progress_turn"))
    except (TypeError, ValueError):
        return True
    return (now_turn - last) <= _INTENT_STALE_TURNS


# How many turns an intention may go without progress and still be trusted to
# name a destination. Deliberately generous: this gate exists to drop rows the
# character has plainly moved on from, not to second-guess a long patient aim.
_INTENT_STALE_TURNS = 40


def _destination_from_goals(stored_state, place_graph, here_rid=None,
                            now_turn=None):
    """The room this character's own goals NAME, resolved against his own map.

    Measured need (A12, run 4): a courier with a re-armed commission and a
    place graph holding a complete, optimal 28-room route to the shrine spent
    five beats standing still working out which way he already knew to go --
    r0003 entered three times, a northward step into a wall -- because every
    affordance answers "where have I not been" and none answers "how do I
    reach the room I already want". His own proven route read back to him as
    "spent Chamber 0003".

    The legitimacy gate is double: the destination must be named by HIS OWN
    authored text, and he must own a place-graph node for it. Sources are
    active_state.goal first, then active intentions by priority, then held
    projects (interior.projects) as the durable fallback --
    goal-first is not a stylistic choice: in the live failure no active
    intention named a chamber at all except a stale one at progress 1.0
    naming "Chamber 0401" (actively wrong), while his self-authored goal
    named "Chamber 0603" from the first pacing beat (right, and current).
    Resolution is exact node-NAME matching against his own nodes -- both
    vocabularies closed, so this is identifier recognition, not reading
    prose. Within a text the last-named room wins: "from the gate to the
    shrine" is going TO the shrine. Returns {"rid", "name"} or None, and
    None means silence -- no route is ever computed to a room he has not
    both wanted and walked.

    A goal whose claim commit has stamped SPENT (goal_room_reached: he has
    stood in the room it names since first stating it in these words) is
    not consulted at all -- it is not evidence of going anywhere, and
    routing on it was the measured 0206 oscillation tether. His intentions
    and projects speak instead.
    """
    nodes = (place_graph or {}).get("nodes")
    nodes = nodes if isinstance(nodes, dict) else {}
    named = {}
    for rid, rec in nodes.items():
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("name") or "").strip()
        if name:
            named.setdefault(name.casefold(), (str(rid), name))
    if not named:
        return None
    st = stored_state if isinstance(stored_state, dict) else {}
    texts = []
    _active = st.get("active_state") if isinstance(
        st.get("active_state"), dict) else {}
    goal = str(_active.get("goal") or "").strip()
    # A SPENT goal claim never routes. Commit stamps goal_room_reached the
    # beat his committed position becomes the room his own goal text names,
    # and carries it only while the words stand unchanged (see
    # affect.goal_slot_currency). Without this, a verbatim re-emitted goal
    # tethered him to the room it named: one step out of Chamber 0206 made
    # 0206 the destination again -- exits, en_route and run offers all
    # steering him BACK -- measured live as the oscillation ... 0306 0206
    # 0205 0206 0306 0206. Skipping falls through to his live intentions
    # and projects, exactly like the standing-in-it skip below; re-wording
    # the aim ("go back to Chamber 0206", said fresh) is a new claim and
    # routes again.
    try:
        _goal_spent = int(_active.get("goal_room_reached"))
    except (TypeError, ValueError):
        _goal_spent = None
    if goal and _goal_spent is None:
        texts.append(goal)
    intents = [i for i in ((st.get("interior") or {}).get("intentions") or [])
               if isinstance(i, dict) and i.get("status") == "active"
               and _intent_is_live(i, now_turn)]

    def _prio(intent):
        try:
            return -float(intent.get("priority") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    texts.extend(str(i.get("intent") or "") for i in sorted(intents, key=_prio))
    # PROJECTS last: the durable fallback. This is the measured hole the
    # project tier closes on the routing side -- when the beat goal names
    # nothing and every intention naming the aim has been satisfied once,
    # decayed dormant, or died with its tactic, a standing commitment that
    # names a room ("every run ends at the shrine in Chamber 0603") still
    # routes. Behind goal and intentions on purpose: a project is what he is
    # about, not necessarily where he is going THIS beat.
    texts.extend(
        str(p.get("project") or "")
        for p in ((st.get("interior") or {}).get("projects") or [])
        if isinstance(p, dict))
    for text in texts:
        folded = text.casefold()
        best = None
        for key, resolved in named.items():
            pos = folded.rfind(key)
            if pos >= 0 and (best is None or pos > best[0]):
                best = (pos, resolved)
        if best:
            rid, name = best[1]
            # A route to the room you are standing in is not information, and
            # claiming the slot with it silences the destination that would
            # have been. Characters phrase goals as the next step far more
            # often than as the aim -- "Run east to Chamber 0004 to progress
            # toward the shrine" names only the waypoint, because the shrine
            # is not a chamber NAME -- so the nearest text wins the match and
            # the real destination never gets looked for. Skipping to the
            # next text is what lets the standing intention be heard.
            if here_rid is not None and str(rid) == str(here_rid):
                continue
            return {"rid": rid, "name": name}
    return None


def _taken_adjacency(g_edges):
    """Doorways this character has actually TAKEN, as an undirected map.

    Stricter than plain adjacency on purpose: adjacency includes doors merely
    seen from rooms stood in, which is enough to know a frontier exists and
    not enough to promise a way through. A route offered toward a goal is a
    promise his feet made.

    Shared by the exit annotator and the run offers so the two cannot drift.
    A run judged against a different graph than the exits beside it would
    give the character two irreconcilable answers inside one payload.
    """
    taken, disproven = {}, []
    for a, side in (g_edges or {}).items():
        if not isinstance(side, dict):
            continue
        for b, rec in side.items():
            if not isinstance(rec, dict):
                continue
            if rec.get("disproven"):
                disproven.append((str(a), str(b)))
                continue
            if not rec.get("taken"):
                continue
            taken.setdefault(str(a), set()).add(str(b))
            taken.setdefault(str(b), set()).add(str(a))
    # A doorway disproven from either side is disproven, and the recording
    # is one-sided as often as not.
    for a, b in disproven:
        taken.get(a, set()).discard(b)
        taken.get(b, set()).discard(a)
    return taken


def _hops_to(rid, dest_rid, taken_adj):
    """Rooms from here to there over ground he has walked. 0 standing in it,
    None when no remembered route runs there at all.

    Same firewall as `_toward_hops`: his own graph, never the scene.
    """
    if rid == dest_rid:
        return 0
    seen = {rid}
    queue = deque([(rid, 0)])
    while queue:
        cur, depth = queue.popleft()
        for nxt in taken_adj.get(cur, ()):
            if nxt in seen:
                continue
            if nxt == dest_rid:
                return depth + 1
            seen.add(nxt)
            queue.append((nxt, depth + 1))
    return None


def _toward_hops(first_step, here_rid, taken_adj, dest_rid):
    """Rooms along this character's OWN walked ground from an exit to the
    destination his goals name: BFS over doorways he has actually taken
    (never merely seen -- a door seen from across a room is known to exist,
    not known to pass), minus the disproven. Returns the room count entering
    the destination, 1 when the exit IS it, None when no remembered route
    runs that way.

    Deliberately never reads the scene. If his map is wrong, the route is
    wrong in exactly the way his map is wrong -- a corridor bricked up since
    he walked it still routes, and he finds out with his feet. That is the
    property the maze-expansion arm measures, and consulting the true graph
    here would both leak unearned map and erase the measurement.
    """
    if first_step == dest_rid:
        return 1
    if first_step not in taken_adj:
        return None
    seen = {here_rid, first_step}
    queue = deque([(first_step, 1)])
    while queue:
        cur, depth = queue.popleft()
        for nxt in taken_adj.get(cur, ()):
            if nxt in seen:
                continue
            if nxt == dest_rid:
                return depth + 1
            seen.add(nxt)
            queue.append((nxt, depth + 1))
    return None


# An active intention idle for two-thirds of the dormancy fuse is surfaced
# as `fading` in the payload. Decay itself is right -- an aim yielding
# nothing for thirty turns should lose its grip -- but until now it was
# silent bookkeeping: the status flipped in commit and the character
# discovered, beats later, that they no longer wanted something. A courier
# walked sixteen optimal rooms to the shrine's threshold and turned away
# because the goal underneath had been spent by a sweep he was never party
# to (A11/A12). Surfacing the burning fuse lets the giving-up happen BY the
# character -- renew by acting, revise, or abandon with a stated reason --
# with the sweep remaining only as the backstop for an unanswered question.
_FADING_AFTER = (INTENT_DORMANT_AFTER * 2) // 3


def _annotate_fading(intentions, now_turn):
    """Mark each active intention that is near the dormancy sweep with how
    many beats it has yielded nothing. Read-side only, non-mutating: the stored
    rows and the sweep in affect.apply_intent_ops are untouched, so this adds
    a legible question, not a new lifecycle.

    `barren_attempts` needs no annotation of its own: it is a stored field, it
    rides in this dict whole, and the character prompt already names it ("an
    intention at progress 1.0, or carrying barren_attempts, is SPENT"). What
    was missing was never the WORD -- it was that `affect._advance_intent`
    only ever set it at the ceiling, so a goal grinding UP THE RAMP burned
    nothing and the character was never told. Live (chat 80, turns 1-3): three
    beats of the same three sentences, and an appraisal still reporting
    controllability 0.7, because nothing in the payload had ever said the
    approach was not working. A mind cannot revise a plan on evidence it was
    never given.
    """
    if not isinstance(now_turn, int):
        return intentions
    out = []
    for intent in intentions or []:
        if not isinstance(intent, dict):
            out.append(intent)
            continue
        intent = dict(intent)
        if intent.get("status") == "active":
            try:
                idle = now_turn - int(intent.get("last_progress_turn"))
            except (TypeError, ValueError):
                idle = None
            if idle is not None and idle >= _FADING_AFTER:
                intent["fading"] = idle
        out.append(intent)
    return out


# Beats a held project may go unserved before the payload says so. Above
# the fading threshold's granularity on purpose being a different clock:
# eight beats is long enough for a scene to legitimately demand other
# things (a project can REST), short enough to catch the measured mid-run
# drift (A15 run 5: visibly adrift by beat 10, twenty beats before anything
# could have said so). The marker only ever grows in wording, never in
# mechanism -- a project must not decay, and never-noticing is the failure
# mode this closes.
_ADRIFT_AFTER = 8


def _annotate_project_drift(projects, now_turn):
    """Mark each held project with how many beats since anything the
    character did served it -- commit's last_served_turn ledger read back.
    The gap between HOLDING a project and SERVING it was invisible: pa1 sat
    in the payload as a static string while the top want served the drive,
    and nothing anywhere marked the distance between the two. Read-side and
    non-mutating, exactly like _annotate_fading: a fact the character can
    notice, never a mechanism that acts. A project with no ledger entry yet
    (authored, pre-first-commit) is silent -- absent means cannot tell."""
    if not isinstance(now_turn, int):
        return projects
    out = []
    for p in projects or []:
        if not isinstance(p, dict):
            out.append(p)
            continue
        p = dict(p)
        try:
            idle = now_turn - int(p.get("last_served_turn"))
        except (TypeError, ValueError):
            idle = None
        if idle is not None and idle >= _ADRIFT_AFTER:
            p["adrift"] = idle
        out.append(p)
    return out


# Beats the goal slot may hold the SAME words, serving no intention or
# project, before the payload says so. Above the nine-beat journey scale on
# purpose: en_route deliberately made goals sticky, and a destination goal
# rightly holds its words for a whole walk -- which is why room-naming goals
# are governed by `goal_reached` instead and never by tenure. Twelve aligns
# with the adrift escalation ("past a dozen beats it is a choice you have
# not admitted"): a beat want held that long is doing a project's job with
# none of a project's governance -- no criterion, no cap, no probation.
_GOAL_HELD_AFTER = 12


def _annotate_goal_currency(active, now_turn, node_names=None,
                            governed_ids=()):
    """Read the goal slot's commit-side currency stamps back as facts.

    The measured failure (maze, turns 370-385): the goal slot behaved as an
    ungoverned project. "Compare chalk circle patterns across chambers"
    survived a run boundary and a process restart -- durable, steering,
    occupying the slot, with no satisfied_when, cap, displacement rule, or
    visibility. And "Run east to Chamber 0403 along the proved line" was
    still the stated goal EIGHT ROOMS past Chamber 0403 -- a claim the
    engine could see was spent, holding the slot because re-emission is
    free and stickiness serves whatever holds the slot.

    Two markers, read-side and non-mutating exactly like _annotate_fading
    and _annotate_project_drift -- facts the character can notice, never a
    mechanism that acts:

      * `goal_reached` {room, beats_ago} -- he has stood in the room this
        goal names since he first stated it in these words. As a movement
        claim it is spent, and routing already declines it; the marker is
        the character's half. A room-naming goal NOT yet reached carries
        nothing: the journey is underway and en_route owns it.
      * `goal_held` <beats> -- how long the slot has held these same words
        while the enacted want serves no live intention or project of his.
        A goal in explicit service of a governed tier is that tier's
        business (its fading / adrift clocks already burn); tenure marks
        only the free-floating claim quietly doing a project's job.

    Ordinary non-maze blast radius, stated loudly: a conversation goal
    names no room (no reached marker, routing untouched), is rewritten as
    wants shift (tenure never accumulates), or serves an intention (tenure
    suppressed). A character whose goals do none of those for twelve beats
    is holding an ungoverned commitment, and being told so is the point.
    """
    if not isinstance(active, dict) or not isinstance(now_turn, int):
        return active
    out = dict(active)
    try:
        reached = int(out.get("goal_room_reached"))
    except (TypeError, ValueError):
        reached = None
    room = str(out.get("goal_room") or "")
    if reached is not None and room:
        out["goal_reached"] = {
            "room": str((node_names or {}).get(room) or room),
            "beats_ago": max(0, now_turn - reached)}
        return out
    if room:
        return out
    if not str(out.get("goal") or "").strip():
        return out
    try:
        held = now_turn - int(out.get("goal_since"))
    except (TypeError, ValueError):
        return out
    if held < _GOAL_HELD_AFTER:
        return out
    wants = out.get("wants") if isinstance(out.get("wants"), list) else []
    enacted = out.get("enacted_want")
    serves = ""
    if isinstance(enacted, int) and 0 <= enacted < len(wants) \
            and isinstance(wants[enacted], dict):
        serves = str(wants[enacted].get("serves") or "")
    if serves and serves in {str(g) for g in governed_ids or ()}:
        return out
    out["goal_held"] = held
    return out


def _en_route(stored_state, here_rid, destination):
    """The journey he is already on, read back to him: the room his own
    goals name, how many rooms of his own walked ground remain to it, and
    whether the last room he stood in was nearer or farther than this one.

    Measured need (A14, post-completeness-fix): with routing, verdicts and
    run offers all naming his destination, a character 9 rooms from the
    chamber he had himself chosen closed to 7 and gave it all back -- trail
    9 9 7 8 9, four beats, net zero. The previous goal TEXT is already in
    the payload (self.active_state.goal), but a nine-room journey still
    needs the same intent to win the beat auction nine independent times,
    and incumbency carried no weight because it was nowhere stated as a
    STATUS: not how far in he was, not that the last beat closed distance.
    This states it. A fact, never a leash: continuation stays the model's
    decision, and the prompt frames leaving a journey as the deliberate
    act.

    Derived entirely at payload time: the destination is the one
    _destination_from_goals already resolved from his OWN previous goal and
    live intentions, and the distance runs over doorways his feet actually
    took (_hops_to on _taken_adjacency -- the same graph the exit verdicts
    and run offers are judged against, so the payload cannot argue with
    itself, and the same firewall: his map, never the scene). Nothing
    persists, so nothing needs cancel machinery -- every ending the journey
    can have is a change in the derivation itself next beat: arriving
    empties the destination, renaming the aim moves it, a disproven doorway
    breaks the remembered way into silence.

    Silence also under two rooms out: a neighbouring destination is already
    fully carried by its exit's "through here is X itself" verdict, and a
    character crossing a house to answer a door does not need a status line
    about the hallway.
    """
    if not (isinstance(destination, dict) and destination.get("rid")
            and here_rid):
        return None
    dest_rid = str(destination["rid"])
    here = str(here_rid)
    st = stored_state if isinstance(stored_state, dict) else {}
    graph = st.get("place_graph")
    graph = graph if isinstance(graph, dict) else {}
    taken = _taken_adjacency(graph.get("edges") or {})
    left = _hops_to(here, dest_rid, taken)
    if left is None or left < 2:
        return None
    out = {"to": str(destination.get("name") or dest_rid),
           "rooms_left": left}
    # The last DIFFERENT room stood in, off his own route window. By room
    # rather than by beat, because a run crosses several rooms in one beat
    # and dwelling crosses none; the SIGN is the fact that matters -- nine
    # rooms walked and given back is not nine rooms walked. Neither key
    # when the distance held or the window cannot say: absent means cannot
    # tell, never "no progress".
    prev = None
    for r in reversed(st.get("visited_rooms") or []):
        if isinstance(r, str) and r and r != here:
            prev = r
            break
    if prev:
        was = _hops_to(prev, dest_rid, taken)
        if was is not None:
            if left < was:
                out["closer_than_last_room"] = True
            elif left > was:
                out["further_than_last_room"] = True
    return out


def _annotate_known_exits(digest, scene, visited_rooms, known_exits=None,
                          here_rid=None, routes_that_worked=None,
                          known_dead_ends=None, place_graph=None,
                          destination=None):
    """Mark each exit with whether this character has been through it.

    `spatial_digest` renders an exit as {room, barrier} -- identical whether
    the character arrived through that doorway a beat ago or has never taken
    it. With nothing to separate them, preferring the unexplored exit is not a
    choice the payload makes available, and the result reads as backtracking.

    `visited_rooms` is the character's OWN route (commit records it from their
    committed position), so this adds no knowledge they did not earn by
    walking. `last_seen_beats_ago` is ordinal, not a turn count: how far back
    in their own route it was, which is the form a person actually has.

    `no_route_onward` marks an exit they entered and always had to reverse out
    of -- the thing `been_there` cannot say, and the thing that actually stops
    a repeated wrong turn. It is about DOORWAYS, not worth: somewhere they
    chose to linger is never marked, because that is a destination rather than
    a wrong turn.
    """
    if not isinstance(digest, dict):
        return digest
    rooms = (scene or {}).get("rooms") or {}
    name_to_id = {}
    for rid, room in rooms.items():
        display = str((room or {}).get("name") or rid)
        name_to_id.setdefault(display, rid)
    # What can be SEEN through each doorway right now, as against what has been
    # walked. A chamber with no other way out is visible as such from the
    # threshold; making a character enter it to find out is not caution, it is
    # a missing sense.
    seen_onward, seen_bearings = {}, {}
    if here_rid:
        try:
            from world.spatial import visible_adjacent_rooms
            for item in visible_adjacent_rooms(scene, here_rid) or []:
                if isinstance(item, dict) and "onward_exits" in item:
                    rid_seen = str(item.get("room_id"))
                    seen_onward[rid_seen] = item["onward_exits"]
                    # WHICH way on, not merely how many. The digest buckets
                    # exits egocentrically (ahead/behind/left), so a count
                    # sitting on the "behind" bucket carries no heading of its
                    # own and gets read as "on in the direction I was already
                    # facing" -- which is how a runner came to hunt a westward
                    # exit, four times, out of a chamber whose only other way
                    # out went north.
                    if item.get("onward_bearings"):
                        seen_bearings[rid_seen] = item["onward_bearings"]
        except Exception:
            seen_onward, seen_bearings = {}, {}
    worked = routes_that_worked if isinstance(routes_that_worked, dict) else {}
    route = [r for r in (visited_rooms or []) if isinstance(r, str)]
    counts = {}
    for rid in route:
        counts[rid] = counts.get(rid, 0) + 1
    # HOW RECENTLY, not merely how often. `times_entered` is a lifetime tally,
    # and a lifetime tally cannot tell "four times over eighty beats" from
    # "four times in the last twelve" -- which are the difference between a
    # thoroughfare and a loop you are stuck in.
    #
    # Observed live: on his second attempt at the same maze a character locked
    # into a period-four cycle, 0001 -> 0002 -> 0001 -> 0000, three times
    # exactly. He was not blind to the way out -- he GENERATED "south into
    # 0100" as a candidate, that being real new ground, and rejected it with
    # `norm_conflict: conflicts with association that east from blue-tile
    # reset leads toward 0507`. A route learned on the previous run was
    # outranking the evidence in front of him, and nothing in the payload said
    # that route had just failed three times running.
    #
    # This is the missing fact, and it is his own route, so it crosses no
    # boundary: a person who has walked the same three rooms four times in a
    # dozen paces knows it without being told.
    recent = route[-LOOP_WINDOW:]
    recent_counts = {}
    for rid in recent:
        recent_counts[rid] = recent_counts.get(rid, 0) + 1
    # A pocket is a handful of rooms that have absorbed a long stretch of the
    # route. Deliberately conservative: it needs a nearly-full window AND
    # genuinely few rooms, so that ordinary back-and-forth through a hub does
    # not read as being stuck.
    # BEATS SINCE NEW GROUND is the honest measure, and the density test above
    # is only a fast path for tight locks. Counting distinct rooms in a window
    # fails on the shape that matters most: an out-and-back along a corridor
    # fills the window with distinct rooms while making no progress at all.
    #
    # Observed live, twice, each time one level larger than the test written
    # for the last one. A fixed four-room threshold missed a lock that widened
    # to five. The ratio that replaced it went silent at a seven-room corridor
    # walked end to end -- 0001/0101/0201/0202/0203/0204/0104, ten beats, not
    # one room he had not already seen. The loop got worse and the warning
    # stopped. Room counts measure the wrong thing; what a lost person
    # actually notices is that nothing has been new for a while.
    since_new = 0
    seen_so_far = set()
    for i, rid in enumerate(route):
        if rid not in seen_so_far:
            seen_so_far.add(rid)
            since_new = 0
        else:
            since_new += 1
    circling = set()
    if since_new and (since_new >= LOOP_WINDOW or (
            len(recent) >= LOOP_WINDOW
            and len(set(recent)) <= LOOP_DENSITY * len(recent))):
        # `since_new` being zero means the last step found somewhere new --
        # the loop is already breaking, so this has nothing left to say.
        # Eleven of the last twelve beats can still be a tight cycle at that
        # moment, and the density test alone would go on calling it circling
        # while he was walking out of it. A signal that argues against the
        # move it wanted is worse than no signal.
        circling = set(recent)
    # Which rooms, in this character's OWN experience, they walked into and had
    # to walk straight back out of.
    #
    # `been_there` alone does not stop anyone re-entering a dead end -- and it
    # did not: observed live, a character was told been_there/times_entered=9
    # for a one-exit chamber and walked back into it six times, because knowing
    # you have been somewhere is not knowing it led nowhere. That is the
    # difference between visit history and route knowledge, and only the second
    # is any use for navigating.
    #
    # Derived purely from their own route: entered, and the next room was the
    # one they had just come from. No oracle knowledge of the maze -- this is
    # exactly what a person remembers about a wrong turn.
    returns, onward, dwelt = {}, {}, set()
    for i, rid in enumerate(route):
        if i + 1 < len(route) and route[i + 1] == rid:
            # Stayed put here for a beat. A place someone CHOSE to remain in
            # was a destination, not a wrong turn -- see below.
            dwelt.add(rid)
        if i == 0 or i + 1 >= len(route):
            continue
        if route[i + 1] == route[i - 1]:
            returns[rid] = returns.get(rid, 0) + 1
        elif route[i + 1] != rid:
            onward[rid] = onward.get(rid, 0) + 1

    # Exits seen from rooms actually stood in, recorded at commit. The FRONTIER
    # is a door seen but never walked through -- and it is the only thing that
    # separates "that way is exhausted" from "that way is where I came from".
    #
    # A first attempt used only walked adjacency, which collapses the whole
    # visited region into one blob: every exit came back "nothing new that way",
    # including the way out. A signal that fires on everything is worse than
    # none, because it argues against the correct move as loudly as the wrong
    # one.
    #
    # The single-room dead end is the easy case, caught by no_route_onward. What
    # actually traps is a dead-end CORRIDOR -- observed live, a character
    # bounced between two pass-through rooms for ten beats, since each was a
    # legitimate onward move and the exhausted thing was the whole branch.
    known_exits = {
        str(k): [str(x) for x in v]
        for k, v in (known_exits or {}).items() if isinstance(v, list)
    }
    # The character's own knowledge, three readings of it. Adjacency merges
    # the legacy known_exits ledger (directed, as recorded from rooms stood
    # in) with the durable place_graph's edges (undirected -- a doorway works
    # both ways -- minus the disproven, which present perception has shown
    # absent; a disproven edge also retracts any stale legacy copy).
    # Walkedness comes from the graph rather than the recency window, because
    # a room walked seventy beats ago has rolled off `visited_rooms` and was
    # reading as untried -- forgetting must never make stale ground look
    # promising.
    adj = {k: set(v) for k, v in known_exits.items()}
    graph = place_graph if isinstance(place_graph, dict) else {}
    g_nodes = graph.get("nodes")
    g_nodes = g_nodes if isinstance(g_nodes, dict) else {}
    g_edges = graph.get("edges")
    g_edges = g_edges if isinstance(g_edges, dict) else {}
    disproven = []
    for a, side in g_edges.items():
        if not isinstance(side, dict):
            continue
        for b, rec in side.items():
            if isinstance(rec, dict) and rec.get("disproven"):
                disproven.append((str(a), str(b)))
                continue
            adj.setdefault(str(a), set()).add(str(b))
            adj.setdefault(str(b), set()).add(str(a))
    for a, b in disproven:
        adj.get(a, set()).discard(b)
        adj.get(b, set()).discard(a)
    walked = set(route) | set(known_exits) | {
        str(r) for r, n in g_nodes.items()
        if isinstance(n, dict) and n.get("basis") == "walked"}
    # Doorways actually TAKEN, for routing toward a named destination.
    taken_adj = _taken_adjacency(g_edges)
    for a, b in disproven:
        taken_adj.get(a, set()).discard(b)
        taken_adj.get(b, set()).discard(a)
    dest_rid, dest_name = None, ""
    if isinstance(destination, dict) and destination.get("rid"):
        dest_rid = str(destination["rid"])
        dest_name = str(destination.get("name") or dest_rid)
        if dest_rid == str(here_rid or ""):
            # Standing in it. Nothing to route.
            dest_rid = None

    # Chambers he has SEEN into and found closed. An untrodden cul-de-sac is
    # a door not taken, but it is not a route, and counting it as frontier
    # kept a whole branch reading as live forever: observed live, a character
    # spent twenty-four beats in a six-room lobe whose only way out was back
    # the way he came, and it never registered as exhausted because one
    # visibly-closed chamber in it was still untrodden. He could see it was
    # closed from the doorway. That was simply never written down.
    dead_ends = {str(r) for r in (known_dead_ends or []) if r} | {
        str(r) for r, n in g_nodes.items()
        if isinstance(n, dict) and n.get("closed")}
    # THE GLOBAL FACT the per-branch markers cannot state: does ANY doorway
    # anywhere in his own map still lead to ground he has not walked?
    # `no_new_ground_that_way` is a comparative claim -- "this branch is
    # exhausted" is only information while some other branch is not -- and
    # when the whole map is walked it degrades into the same discouragement
    # on every exit, everywhere, forever. Measured live (Orrin, shrine-maze,
    # turn 228): 49 chambers all walked, a 0.95 belief in his own state that
    # "there is no unexplored ground left in this maze", and both exits of
    # his room reading "spent -- every door you have seen down that way is
    # one you have taken" with beats_since_new_ground at 26 and climbing.
    # Every direction read as failure, nothing said the map was COMPLETE, and
    # a mind in failure reaches for the thing that would fix it: his beliefs
    # from turns 215-219 invented "unexplored eastern corridor" out of a
    # sightline that "bends out of sight", and his goals chased it. The
    # payload made a finished maze illegible as anything but a maze where
    # every choice is wrong.
    frontier_anywhere = any(
        n not in walked and n not in dead_ends
        for side in adj.values() for n in side)
    # A door in THIS room he has never taken counts as frontier too: on a
    # first beat somewhere new the commit-recorded adjacency has not caught
    # up yet, and completeness must never be claimed across an untried door.
    untried_here = False
    for edges in digest.values():
        if not isinstance(edges, list):
            continue
        for e in edges:
            if not isinstance(e, dict):
                continue
            _rid = name_to_id.get(str(e.get("room") or ""))
            if not (_rid and (_rid in counts or _rid in walked)):
                untried_here = True
    # A POSITIVE claim, never an absence: it needs recorded adjacency to
    # stand on (a bare route window says nothing about doors), and one
    # untried door anywhere defeats it. Everything below that softens a
    # discouraging signal is gated on this, not on frontier_anywhere alone,
    # because "I cannot tell whether new ground exists" must never read as
    # "none exists".
    fully_known = bool(adj) and bool(walked) \
        and not frontier_anywhere and not untried_here
    out = {}
    all_marked = []
    for bucket, edges in digest.items():
        if not isinstance(edges, list):
            out[bucket] = edges
            continue
        marked = []
        for edge in edges:
            if not isinstance(edge, dict):
                marked.append((edge, None, None))
                continue
            rid = name_to_id.get(str(edge.get("room") or ""))
            entry = dict(edge)
            hops, toward = None, None
            if rid and here_rid and dest_rid:
                toward = _toward_hops(rid, str(here_rid), taken_adj, dest_rid)
            if rid in seen_onward:
                # Absent means "cannot tell from here" -- never "none".
                entry["onward_exits_visible"] = seen_onward[rid]
                if rid in seen_bearings:
                    entry["onward_bearings"] = seen_bearings[rid]
                if seen_onward[rid] == 0:
                    entry["visibly_no_way_through"] = True
            if rid and worked.get(rid):
                # The counterweight. Every other marker here says where they
                # have BEEN; this is the only one that says something WORKED,
                # and without it a proven route reads as merely old.
                entry["worked_before"] = worked[rid]
            if rid and (rid in counts or rid in walked):
                # Been-there is a LIFETIME fact read from the durable graph,
                # not the recency window: a room walked seventy beats ago has
                # rolled off `visited_rooms`, and reading it as `untried`
                # would send the character back over old ground as though it
                # were discovery. The window-scoped counters below are simply
                # absent for it -- absent means "cannot tell", never "none".
                entry["been_there"] = True
                if rid in counts:
                    entry["times_entered"] = counts[rid]
                if recent_counts.get(rid, 0) > 1:
                    # The one number that separates a thoroughfare from a
                    # loop. Only emitted above 1, because "you were there
                    # once recently" is just where you came from.
                    entry["entered_recently"] = recent_counts[rid]
                if rid in circling:
                    entry["circling_here"] = True
                if returns.get(rid):
                    # The FACT: they went in and came straight back out, N
                    # times. Always reported, because it is simply what
                    # happened.
                    entry["turned_back_here"] = returns[rid]
                    # The INFERENCE, named for what it actually is: no route
                    # ONWARD. Not "leads nowhere" -- a tavern is a room you
                    # enter and leave by the same door, and a marker calling it
                    # a dead end tells a character to avoid the place they were
                    # going. This says only that it is not a way THROUGH: a
                    # fact about doorways, saying nothing about whether it is
                    # worth being in.
                    #
                    # Held to two reversals with no onward move, and never
                    # applied to somewhere they chose to REMAIN: dwelling is
                    # what going somewhere on purpose looks like, as against
                    # passing through and finding a wall.
                    if (returns[rid] >= 2 and not onward.get(rid)
                            and rid not in dwelt):
                        entry["no_route_onward"] = True
                if here_rid:
                    hops = _frontier_hops(rid, here_rid, adj, walked,
                                          dead_ends)
                    # `spent` only while it discriminates: with no frontier
                    # left ANYWHERE the marker is true of every exit at once,
                    # which brands familiarity as failure -- for a maze
                    # finished, or simply for a character who lives here and
                    # has walked their whole home. The completeness fact
                    # rides `ground_fully_known` below instead.
                    if hops is None and not fully_known:
                        entry["no_new_ground_that_way"] = True
                for back, seen in enumerate(reversed(route), 1):
                    if seen == rid:
                        entry["last_seen_beats_ago"] = back
                        break
            else:
                entry["been_there"] = False
                # POSITIVELY marked, because the frontier was the one thing
                # here described only by an absence. Measured at the moment a
                # character failed to take it: the door he should have used
                # carried three keys and 64 characters, `been_there: false`
                # among them, while the door he kept taking instead carried
                # eight keys and 179. Every good thing about the right answer
                # was the lack of something, so it was the lightest item in
                # the payload -- and it was chosen against, nineteen beats
                # running. Salience follows weight, and ours pointed the
                # wrong way.
                entry["untried"] = True
            entry = _verdict(entry, frontier_hops=hops)
            # The destination reading rides the verdict STRING and the
            # ordering only, exactly as the frontier distance does -- a key
            # of its own would put weight back on the entries that should
            # carry the least, which is the failure _annotate_known_exits
            # exists to not repeat. The raw markers stay underneath as the
            # evidence a character needs to disagree with the reading.
            if toward is not None and isinstance(entry, dict) \
                    and entry.get("verdict"):
                if toward == 1:
                    entry["verdict"] += (
                        f"; through here is {dest_name} itself -- the room "
                        "your goal names")
                else:
                    entry["verdict"] += (
                        f"; your own remembered ground runs from here to "
                        f"{dest_name}, about {toward} rooms along this way")
            marked.append((entry, hops, toward))
        # Untried first, and among `known` exits the one with NEARER new
        # ground first. Position IS salience and it costs nothing; leaving
        # the order to however the digest happened to build it was spending
        # that for no reason. Stable within each group, so a bucket's own
        # ordering still shows through. The distance rides the sort key and
        # the verdict string only -- adding it as a per-exit key would put
        # weight back on the entries that should carry the least.
        def _rank(trio):
            entry, hops, toward = trio
            appeal = _appeal(entry)
            near_dest = 10 ** 6
            if isinstance(entry, dict) and isinstance(toward, int):
                # An exit on the remembered way to the room his goals name
                # must not be buried under its own discouragement:
                # spent/circling/closed all answer "anything NEW that way?",
                # which is not the question a named destination asks.
                # Measured in A12 run 4: every step of his optimal route
                # read `known`/`spent` BECAUSE he had walked it, which is
                # exactly why it was the route. Clamped to `known`, never
                # lifted above untried/proven -- goal against curiosity
                # stays the character's call, as the appeal order promises.
                appeal = min(appeal, _APPEAL_ORDER.index("known"))
                near_dest = toward
            near = 10 ** 6
            if isinstance(entry, dict) and isinstance(hops, int) \
                    and hops >= 1 \
                    and str(entry.get("verdict") or "").startswith("known"):
                near = hops
            return (appeal, near_dest, near)
        out[bucket] = sorted(marked, key=_rank)
        all_marked.extend(out[bucket])

    # THE ONLY WAY ON. When every doorway here argues against itself and
    # exactly one of them still leads to unexplored ground, say so outright.
    #
    # This is where the loop detector turned against the character. Measured
    # in A11: standing in a pocket, one exit `spent` and one `circling`, and
    # the `circling` one was the sole route to the only frontier left in the
    # maze. Both read as "do not go here", so he paced -- and every beat of
    # pacing made the circling verdict truer. A signal that fires because the
    # character is stuck, and then prevents them leaving, is worse than no
    # signal.
    #
    # Deterministic and narrow on purpose: it fires only when nothing
    # encouraging remains AND the choice is unambiguous. With two live
    # branches the character is choosing, not trapped, and choosing is theirs.
    live = [trio for trio in all_marked
            if isinstance(trio[1], int) and trio[1] >= 0]
    if live and len(live) == 1 and all(
            _appeal(e) >= _APPEAL_ORDER.index("circling")
            for e, _, _ in all_marked if isinstance(e, dict)):
        entry, hops, _toward = live[0]
        entry["only_way_onward"] = True
        entry["verdict"] = (
            str(entry.get("verdict") or "") +
            "; even so it is the ONLY way you know of that still leads to "
            "ground you have not walked -- going back through here is not "
            "circling, it is the way out")
    for bucket in list(out):
        if isinstance(out[bucket], list):
            out[bucket] = [trio[0] for trio in out[bucket]]
    # The completeness fact, stated once and positively. Every marker above
    # answers "where have I not been", and when the answer is NOWHERE the
    # absence of that statement was the bug: forty-nine local "nothing new
    # that way"s never sum, in a model's reading, to "there is nothing new
    # ANYWHERE" -- they sum to "I am in the wrong part of the maze". Only
    # claimed off his own recorded adjacency (`adj` non-empty), never off a
    # bare route window, and never across an untried door in this room.
    # Rooms seen-closed but never entered do NOT break completeness: they
    # carry `unentered` where they stand, and what is IN them is a different
    # question from where anything leads.
    if fully_known:
        out["ground_fully_known"] = True
    # Whole-route, not per-exit: how long since anywhere was new. The per-exit
    # markers say something about each doorway; this says something about the
    # walk. Only reported once it is worth noticing, since a couple of beats
    # retracing your steps is ordinary movement, not being lost -- and never
    # on a POSITIVELY complete map: there the counter can never reset again,
    # so it would brand every future beat as failure, including every step of
    # a proven route walked on purpose.
    if since_new >= LOOP_WINDOW // 2 and not fully_known:
        out["beats_since_new_ground"] = since_new
    return out


def _run_end_note(end_rid, nodes, closed_rids):
    """What the character already knows about the chamber a run finishes in.

    The exits digest carries a verdict for every doorway; the run offers
    carried nothing but a room NAME, so the same chamber could read as
    discouraging when walked to and as a bare destination when run to. The
    decision is made where the offer is, so what the character knows has to
    be stated there too.

    Split exactly as `_verdict` splits `closed` from `unentered`, and for the
    same measured reason: the shrine is a cul-de-sac. A run that finishes in
    a dead end the character has SEARCHED buys nothing, but a run finishing
    in one they have never been inside may be the whole point of the maze --
    A11 run 3 lost the shrine to precisely that conflation, the character
    reading "no other way out" off the thing he was sent to reach and
    turning around at its doorway. So `visits` decides the wording, and a
    never-entered cul-de-sac is never discouraged.

    Returns "" when there is nothing the character knows to say, which keeps
    the key absent from the offer rather than present and empty -- an
    encouraged run stays as short to read as it was before.
    """
    node = nodes.get(end_rid)
    node = node if isinstance(node, dict) else {}
    if not (node.get("closed") or end_rid in closed_rids):
        return ""
    if int(node.get("visits") or 0) > 0:
        return ("a dead end you have already been inside -- its only way out "
                "is the doorway you would go in by")
    return ("no other way out of it, but you have never been inside -- what "
            "is IN a room is a different question from what it leads to")


def sprint_offers(scene, room_id, stored_state, destination=None):
    """The RUNNING offers actually worth handing a deciding mind.

    Two gates on the raw `spatial.sprint_reach`, each preventing an observed
    failure:

    * Knowledge. Decision-bounded reach follows a corridor round its bends,
      and objectively that is the Director's resolve ceiling -- but handed
      raw to a character it would report the winding geometry of passages
      they have never walked, unearned map smuggled in as an affordance
      (the exact structured-representation leak the perception layer exists
      to prevent). The gate is the engine's own remembered-ground idiom
      (commit.record_spatial_experience): durable place-graph nodes plus the
      visited-rooms recency window. A body's offered reach GROWS as it
      learns the ground, which is also what is true of real runners.
    * Worth. A 1-room "run" is a step with a different verb, and listing it
      taught the model that runs are trivial: measured live (A11), 72 of 96
      passages offered exactly one room, and the character read offer after
      offer as "only 1 room, walking is fine" -- then never ran at all. An
      adjacent visible room needs no affordance entry to be sprinted into;
      only reach a walk cannot match is worth an entry.

    An omitted passage is still runnable -- open-endedly, "run until
    something stops me" -- and resolves against the Director's objective
    ceiling. The prompt says so.

    The offer names WHERE THE RUN ENDS, never the rooms along the way.
    Structural, not cosmetic: the first shape listed `path`, and the
    smallest-plausible directive did to it exactly what a minimizer does to
    a divisible quantity -- measured in A12, the character read a 3-room
    reach, reasoned "the smallest plausible next behavior might be just the
    first step", took the first room off the path list, and declared a
    1-room "run". Prompt text arguing that the whole reach is one behaviour
    was read and lost. So the offer no longer presents anything to split:
    `run_ends_at` names the terminal room, and declaring less than the
    reach now requires inventing an intermediate stop the offer never
    mentioned. Nothing epistemic is lost -- every room on a gated path was
    already the character's, by sight or by feet; the Director's objective
    reach keeps the full path for resolution and commit.
    """
    st = stored_state if isinstance(stored_state, dict) else {}
    graph = st.get("place_graph") or {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    nodes = nodes if isinstance(nodes, dict) else {}
    remembered = set(nodes) | {
        r for r in (st.get("visited_rooms") or []) if isinstance(r, str)}
    closed_rids = {r for r in (st.get("known_dead_ends") or [])
                   if isinstance(r, str)}
    rooms = (scene or {}).get("rooms") or {}
    # What the run does to the distance he still has to cover. Measured in
    # A13 run 4: the exits carried "your remembered ground runs from here to
    # Chamber 0603, about 26 rooms along this way" on the correct one-room
    # step, and the run offers carried nothing at all -- so the choice he
    # actually faced was a 1-room step that mentioned his destination against
    # a 3-room `full_reach` run that did not. For a character whose sheet
    # says running the proved line is the finish, that is not close. He took
    # the run; it ended four rooms further out. Every affordance was locally
    # correct and none of them talked to each other.
    dest_rid = dest_name = None
    here_hops = None
    taken_adj = {}
    if isinstance(destination, dict) and destination.get("rid"):
        dest_rid = str(destination["rid"])
        dest_name = str(destination.get("name") or dest_rid)
        taken_adj = _taken_adjacency(
            graph.get("edges") if isinstance(graph, dict) else {})
        here_hops = _hops_to(str(room_id), dest_rid, taken_adj)
    out = []
    for offer in sprint_reach(scene, room_id, known_rooms=remembered):
        if int(offer.get("rooms") or 0) < 2:
            continue
        end = str((offer.get("path") or [""])[-1])
        entry = {
            # Absent when the doorway carries no bearing -- the world gives
            # no compass there, and a null would read as one to fill in.
            # Such a run is declared by its `run_ends_at` name instead.
            **({"bearing": offer["bearing"]} if offer.get("bearing") else {}),
            "run_ends_at": str((rooms.get(end) or {}).get("name") or end),
            "rooms": offer.get("rooms"),
            "stops": offer.get("stops"),
        }
        notes = []
        note = _run_end_note(end, nodes, closed_rids)
        if note:
            notes.append(note)
        if here_hops is not None:
            end_hops = _hops_to(end, dest_rid, taken_adj)
            if end_hops is not None and end_hops != here_hops:
                gap = end_hops - here_hops
                notes.append(
                    f"it ends {gap} rooms further from {dest_name} than you "
                    f"stand now" if gap > 0 else
                    f"it ends {-gap} rooms closer to {dest_name}")
        if notes:
            entry["ends_in"] = "; ".join(notes)
        out.append(entry)
    return out


def _fold_claim(value):
    """One belief/association claim, folded for identity comparison."""
    return " ".join(str(value or "").split()).casefold()


def _prune_seeded_psychology(psych, interior):
    """Drop the card copies of beliefs/associations the interior already holds.

    Row by row, and only where the live ledger genuinely carries the same claim.
    Before the first commit the ledger is empty and the card is the only copy
    there is, so nothing is dropped then -- which is exactly the beat where a
    character with an authored self-model must still arrive holding it.
    """
    if payload_legacy("self") or not isinstance(interior, dict):
        return
    held_beliefs = {
        _fold_claim(row.get("belief")) for row in (interior.get("beliefs") or [])
        if isinstance(row, dict) and str(row.get("belief") or "").strip()}
    held_cues = {
        _fold_claim(row.get("cue")) for row in (interior.get("associations") or [])
        if isinstance(row, dict) and str(row.get("cue") or "").strip()}
    for section, key, held in (("self_model", "beliefs", held_beliefs),
                               ("learning", "associations", held_cues)):
        block = psych.get(section)
        if not isinstance(block, dict) or not held:
            continue
        field = "belief" if key == "beliefs" else "cue"
        kept = [row for row in (block.get(key) or [])
                if not (isinstance(row, dict)
                        and _fold_claim(row.get(field)) in held)]
        if kept:
            block[key] = kept
        else:
            block.pop(key, None)


def _extension_character_payload(ctx, cid, payload, sheet=None):
    """Hand the assembled payload to installed routing hooks, or leave it be.

    Lazy-imported and total, the same discipline as `runtime.py`'s two extension
    seams and for the same reason: this runs inside the turn's wall clock, so a
    broken extension must cost the beat nothing. With no hooks registered --
    the overwhelmingly common case -- this is one attribute lookup.
    """
    try:
        import extension_runtime

        names = ()
        if sheet is not None:
            name = character_name(sheet)
            names = (name,) if name else ()
        return extension_runtime.dispatch_character_payload(
            ctx, cid, payload, names)
    except Exception:
        return payload


def character_step(ctx, cid, nonce):
    chat = ctx.chat
    row = next((c for c in ctx.cast if c["id"] == cid), None)
    if row is None:
        # Cast member was dismissed between plan construction and execution;
        # skip this character step gracefully rather than crashing with
        # StopIteration.
        return None
    sh, active, stance = sheet_state(row)
    # The body as it IS, not as it was authored. Everything below reads the
    # card -- senses, abilities, embodiment capabilities, extra parts -- so a
    # transformation that stopped at the observer's view would leave this mind
    # certain it still had the shape it started with. See scene.transformed_sheet.
    sh = transformed_sheet(
        sh,
        active_transformations(chat["id"]).get(
            str(character_name(sh) or "").casefold()))
    sc = get_scene(chat["id"], chat)

    # Consciousness gate (choke point): an unconscious/asleep/sedated mind does
    # not deliberate or act. The planner and both loops already drop non-awake
    # reactors; this guard protects rerun/resume paths that hydrate a stale plan
    # and makes the invariant hold no matter who calls character_step. No LLM
    # call, no manifest (which perception would otherwise deliver as tells).
    if awareness_of(chat["id"], character_name(sh)) in NON_AWAKE_GATED:
        return {"sequence": [], "speech": None, "action": None, "actions": [],
                "manifest": {}, "mind_model_updates": [],
                "_awareness_gated": True}

    interaction_views = ctx.get("interaction_views", {}) or {}
    reaction_views = ctx.get("reaction_views", {}) or {}
    view = reaction_views.get(cid) or interaction_views.get(cid)
    if view is None:
        view = ((ctx.get("perception_act", {}).get("views") or {}).get(str(cid)))
    base_observations = (
        (ctx.get("perception_act", {}).get("observations") or {}).get(str(cid))
        or []
    )
    base_view = ((ctx.get("perception_act", {}).get("views") or {}).get(str(cid)))
    # Interaction/reaction micro-views are already filtered for this mind but
    # do not pass through the full perception stage. Never reuse stale base
    # metadata for a changed view; project only the permitted text itself.
    if view and view != base_view:
        from .composer import compact_observation
        observations = [compact_observation({
            # A character may receive several micro-views in one turn.  The
            # old constant id collapsed them into one apparent observation,
            # making later evidence impossible to audit against the round it
            # actually came from.
            "observation_id": f"current:{cid}:micro:{nonce}",
            "perceiver_id": str(cid),
            "source_atom_id": "current",
            "channel": "mixed",
            "fidelity": "rendered",
            "observed": {"text": str(view)},
            "intensity": 0.5,
            "suddenness": 0.1,
            "ambiguity": 0.3,
            "directed_at_self": False,
        })]
    else:
        observations = base_observations

    # Resolved before the memory context, not after: where the character is
    # standing is a retrieval cue, and the recall is built here.
    char_room = character_room(sc, sh)
    stored_state = json.loads(row["cstate"] or "{}")
    # How much of this mind its own body currently has. Own interoceptive state
    # only -- another character's pain is never an input to this character's
    # cognition (see AGENTS.md's own-body isolation rule). Resolved up here
    # because both the hypothesis sheet below and the unbidden-recall trigger
    # read it.
    absorption = cognitive_absorption(
        (active or {}).get("hedonic"), (active or {}).get("stress"))
    _interior = stored_state.get("interior") or {}
    # The same pair commit will enforce, from the same inputs, so the payload
    # never asks for more wants than the beat will keep.
    _capacity_band = affect.normalize_capacity(
        character_psychology(sh).get("capacity"))
    _want_cap, _intent_cap = affect.capacity_caps(_capacity_band, absorption)
    # The goal slot's currency, resolved once and reused: the trigger below
    # and the `_self` payload must judge the SAME annotated goal, or the
    # payload argues with itself. His own node names for display (the closed
    # vocabulary the stamp was resolved over -- never the scene's), and the
    # ids of his live intentions and projects, whose service suppresses the
    # tenure marker.
    _node_names = {
        str(rid): str((rec or {}).get("name") or rid)
        for rid, rec in (((stored_state.get("place_graph") or {})
                          .get("nodes")) or {}).items()
        if isinstance(rec, dict)}
    _governed_ids = (
        {str(p.get("id") or "") for p in (_interior.get("projects") or [])
         if isinstance(p, dict)}
        | {str(i.get("id") or "") for i in (_interior.get("intentions") or [])
           if isinstance(i, dict)}) - {""}
    _active_annotated = _annotate_goal_currency(
        active, ctx.turn.idx, _node_names, _governed_ids)
    # Memory's origin-on-drift rule needs the same deterministic annotations
    # the character payload reads. Legacy active_state rows do not store
    # `goal_held` or project `adrift` -- both are read-side facts derived from
    # the current turn and the existing project ledger -- so hand the memory
    # seam a contextual projection rather than inventing or persisting fields.
    _memory_active = dict(_active_annotated or {})
    _memory_active["projects"] = _annotate_project_drift(
        (_interior.get("projects") if isinstance(_interior, dict) else []) or [],
        ctx.turn.idx)
    _ponder_state = (stored_state.get("memory_ponder")
                     if isinstance(stored_state.get("memory_ponder"), dict)
                     else {})
    try:
        _ponder_ready = int(_ponder_state.get("set_turn")) < ctx.turn.idx
    except (TypeError, ValueError):
        _ponder_ready = False
    _ponder_query = (str(_ponder_state.get("query") or "")
                     if _ponder_ready else "")
    _self_lines = _recent_self_lines(
        chat.id, character_name(sh), ctx.turn.idx, frame_id=ctx.turn.frame_id)
    _self_moves = _recent_self_moves(
        chat.id, cid, ctx.turn.idx, frame_id=ctx.turn.frame_id)
    _refrain = _self_line_refrain(_self_lines)
    _decision_intentions = _annotate_fading(
        _merge_standing_intentions(
            character_standing_intentions(sh),
            _interior.get("intentions") or []),
        ctx.turn.idx,
    )
    _steering_intention_ids = sorted(
        affect.steering_intent_ids(_decision_intentions, ctx.turn.idx))
    _here_name = (sc.get("rooms") or {}).get(char_room, {}).get("name") \
        or char_room
    # Unbidden recall, decided BEFORE the memory context is built and entirely
    # deterministically: a measurably stuck mind gets one contrasting memory
    # of its own surfaced into that context (see _unbidden_trigger).
    # A dialogue micro-round is not a new beat: if an earlier round of this
    # SAME turn already fired (its result is merged latest-probe-wins), this
    # round must not fire a second intrusion -- the prior round's outcome is
    # carried forward onto this round's probe below instead.
    _prior_probe = ((getattr(ctx, "character_results", None) or {})
                    .get(cid) or {}).get("unbidden_probe")
    _prior_probe = _prior_probe if isinstance(_prior_probe, dict) else {}
    _unbidden_reason, _unbidden_fire = _unbidden_trigger(
        stored_state, _active_annotated, _refrain, ctx.turn.idx, absorption)
    if _prior_probe.get("fired"):
        _unbidden_fire = False
    memory_context = build_character_memory_context(
        chat_id=chat.id, char_id=cid,
        current_turn_idx=ctx.turn.idx,
        current_view=view or "",
        active_state=_memory_active,
        here=_here_name,
        # Rooms currently in sight are cues too. Recalling what happened where
        # you STAND tells you where you are; recalling it about a room you can
        # SEE tells you whether to go there -- which is the decision actually
        # being made.
        in_sight=[
            str(item.get("room_name") or item.get("room_id"))
            for item in (visible_adjacent_rooms(sc, char_room) or [])
            if isinstance(item, dict)
        ] if char_room else None,
        absorption=absorption,
        ponder_query=_ponder_query,
    )
    memory_internal = memory_context.get("_internal") or {}
    _unbidden_mem_id = None
    _unbidden_mem_ref = None
    if _unbidden_fire:
        # Everything already in mind is excluded -- the recent buffer, this
        # beat's ordinary recall, and the ledger of recently intruded rows
        # (a memory that returns every few beats is a haunting, which is an
        # authored effect, not a fallback behavior).
        _in_mind = set(memory_internal.get("retrieved_ids") or [])
        _in_mind |= {i for i in
                     ((stored_state.get("unbidden") or {}).get("recent_ids")
                      or [])}
        _contrast = contrast_memory(
            chat.id, cid,
            " ".join(p for p in (
                view or "", str((active or {}).get("goal") or ""),
                str((active or {}).get("mood") or "")) if p),
            ctx.turn.idx, here=_here_name,
            exclude_ids=[i for i in _in_mind if i is not None])
        if _contrast:
            _unbidden_mem_id = _contrast[0]["id"]
            _unbidden_mem_ref = _contrast[0].get("event_key") or ""
            _attach_unbidden(
                memory_context, _unbidden_entry(_contrast[0], ctx.turn.idx))
    known_tags, excl_titles = _char_known_tags(sh)
    knowledge = knowledge_for_character(_books(ctx), char_room, known_tags, excl_titles)
    # Lore is objective world record and its prose names people by name --
    # including entries the mapping stage writes DURING PLAY, from a beat the
    # reader was standing in. Which entries reach a mind is already gated by
    # knowledge_tag/range; who those entries are allowed to NAME was not, so a
    # character met one beat ago arrived pre-identified in a paragraph about
    # somewhere else entirely. Same identity floor as `ahead_entity` below and
    # as perception's own prose, from the same `known` map.
    _name_scrub = observer_name_scrub(chat, character_name(sh), ctx.cast)
    _gated_knowledge = scrub_names_deep(knowledge, _name_scrub)
    if _gated_knowledge != knowledge:
        ctx.add_warning(
            f"character {character_name(sh)}: scrubbed unearned identities out "
            "of world_knowledge lore text")
    knowledge = _gated_knowledge

    _interp = _dict(ctx.director_interpret)
    _flow = _dict(_interp.get("flow"))
    _tom = _list(_flow.get("tom_triggers"))

    relationships = relationships_for_payload(chat.id, cid)
    _sim_clock = wget(
        chat.id, "simulation_clock",
        {"elapsed_seconds": 0.0, "display": "now"},
    )
    mind_models = mind_models_for_payload(
        stored_state.get("mind_models") or {}, ctx.turn.idx,
        elapsed_seconds=(_sim_clock or {}).get("elapsed_seconds"),
    )
    # The stable sheet is SELECTED at commit (where the reconciled beliefs and
    # the settled end-of-beat body state both exist) and simply read here, so
    # what the character holds in mind this turn is what they came out of the
    # last beat holding.
    active_hypotheses = list(stored_state.get("active_hypotheses") or [])[
        :sheet_capacity(absorption)]
    frame_id = ctx.turn.frame_id
    if frame_id is not None:
        # A frame's own state-swap already starts blank the first time
        # it's visited, but nonexistent_cast is the deterministic
        # backstop regardless of how relationship/mind-model data got
        # there -- e.g. a character not yet born must never appear known
        # to a native here even if something upstream got it wrong.
        #
        # all_cast_name_to_id (NOT ctx.cast, which is active-only) --
        # a DORMANT cast member must be checked against nonexistent_cast
        # exactly like an active one. Building this from ctx.cast alone
        # made a dormant not-yet-existing character fall through to the
        # -1 fallback below, which reads as "recognized" (-1 is never in
        # a frame's nonexistent_cast list), silently defeating the mask
        # for exactly the case it exists to catch. A name that isn't ANY
        # cast member at all (a background presence, an unsheeted NPC)
        # correctly keeps that same -1/"recognized" fallback -- this
        # mask only ever applies to declared cast members.
        name_to_id = all_cast_name_to_id(chat.id)
        relationships = {
            name: rel for name, rel in relationships.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }
        mind_models = {
            name: mm for name, mm in mind_models.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }

    # _interior was resolved above, before the memory context, where the
    # unbidden-recall trigger also reads it.
    _psych = character_psychology(sh)
    # Tier-1: show the EFFECTIVE (possibly rupture-shifted) drive, read-only.
    _psych["drive"] = effective_drive(_psych, _interior)
    # The authored beliefs and associations are SEEDED into the interior ledger
    # at commit, so once that has happened the payload was carrying each of them
    # twice -- `psychology.self_model.beliefs` beside `learned_beliefs`, and
    # `psychology.learning.associations` beside `learned_associations`. Measured
    # on chat 72's live bank: 4/4 beliefs and 3/3 associations byte-identical
    # across the pair, 1.8 KB of a 22.7 KB self block.
    #
    # The interior copy is the one that stays, for three reasons: it is what the
    # prompt names (`self_model` and `learning` appear in it zero times), it is a
    # strict superset (it carries `authored: true`, so nothing about provenance
    # is lost), and it is the live one -- credence moves there, not on the card.
    # Dropped ROW BY ROW rather than wholesale, because before the first commit
    # the ledger is empty and the card is then the only copy there is.
    _prune_seeded_psychology(_psych, _interior)
    # A drive rupture is proposable ONLY inside its open window (see commit's
    # detect_drive_rupture) -- the base contract never documents drive_shift, so
    # the model cannot flip-flop it; it appears here only when the engine opened
    # the window this beat or in the two beats after.
    _rupture = _interior.get("drive_rupture")
    _window_open = bool(isinstance(_rupture, dict)
                        and ctx.turn.idx <= int(_rupture.get("window_expires") or -1))
    # How long the window has been open. Once it has stayed open
    # RUPTURE_FORCE_AFTER turns, the optional "you MAY shift" becomes a FORCED
    # resolution (below) -- the fix for a rupture that the engine keeps holding
    # open while the model quietly declines it every beat (the 23-turn limbo).
    _rupture_turns_open = (
        ctx.turn.idx - int(_rupture.get("opened_turn") or _rupture.get("turn") or ctx.turn.idx)
        if isinstance(_rupture, dict) else 0)
    _rupture_forced = _window_open and _rupture_turns_open >= RUPTURE_FORCE_AFTER
    # Crisis: strain at visible-breaking level. Even before any drive_shift,
    # the flag (plus the CRISIS prompt block below) forces the manifest/tells
    # to show the character cracking instead of playing untouched calm.
    try:
        _strain = float(_interior.get("drive_strain") or 0.0)
    except (TypeError, ValueError):
        _strain = 0.0
    _crisis = _strain >= CRISIS_STRAIN_MIN
    # Recent-tell ledger (written by commit): physical cues already shown,
    # fed back so the model does not reuse the same gesture every beat.
    _recent_tells = [str(t) for t in (stored_state.get("recent_tells") or [])
                     if str(t).strip()]
    # Tell-ground ledger (F6, written by commit): each recent cue with the
    # private ground it betrayed, fed back so a planted tell can be PAID OFF
    # in a later beat -- the ground surfacing in behavior or speech -- instead
    # of dangling forever as fake significance. Private context only; the
    # grounds never reach observers.
    _tell_grounds = [
        {"cue": str(g.get("cue") or ""), "because": str(g.get("because") or "")}
        for g in (stored_state.get("tell_grounds") or [])
        if isinstance(g, dict) and str(g.get("cue") or "").strip()
    ]
    # Resolved once and shared: the exits and the run offers must be judged
    # against the SAME destination, or the payload argues with itself.
    _goal_destination = _destination_from_goals(
        stored_state, stored_state.get("place_graph") or {},
        here_rid=char_room, now_turn=getattr(ctx, "turn_idx", None))
    # _node_names, _governed_ids, _self_lines and the annotated goal currency
    # were all resolved above, before the memory context -- the unbidden
    # trigger and this payload must judge the SAME annotated goal.
    _self = {
        "entity_id": f"character:{cid}",
        "name": character_name(sh),
        "public_history": character_public_history(sh),
        "psychology": _psych,
        "stance": stance,
        # How readily this mind leaves a known-good way for an untried one.
        # Explicit because the balance was previously implicit -- an artefact of
        # which navigational markers existed, not an authored trait.
        "curiosity": character_curiosity(sh),
        # The goal slot carries its currency: `goal_reached` when he has
        # stood in the room these words name since first saying them (the
        # claim is spent and no longer routes), `goal_held` when the same
        # room-less words have held the slot past the tenure threshold
        # while serving nothing governed. See _annotate_goal_currency.
        "active_state": _active_annotated,
        "voice": character_voice(sh),
        "senses": senses_as_text(character_senses(sh)),
        "sense_profile": character_senses(sh),
        "interoception": character_interoception(sh),
        "abilities": character_abilities(sh),
        # Hidden from observers does not mean hidden from the body itself.
        # This is the actor-side authority for conditional physiological,
        # mechanical, magical, or otherwise embodied material outputs.
        "embodiment_capabilities": character_embodiment_capabilities(sh),
        # Its own clothing, by region. A character knows what it is wearing
        # and what of itself is uncovered -- that is interoception, not
        # observation -- so this is the one place the region view is of the
        # reader's own body rather than someone else's.
        # Same compact line the Director gets. A body knows what it is
        # wearing, and knows it in the same terms the beat will be adjudicated
        # in -- two shapes for one fact is how `wearing` and `regions` drifted
        # apart in the first place.
        "attire": compact_attire(sc.get("attire", {}).get(character_name(sh))),
        # Its own authored extra body parts (tail, wings...). A mind knows its
        # own body whether or not anyone can see it -- same self-knowledge
        # floor as the interoception and attire lines beside this. Key absent
        # for the ordinary body, so defaults stay inert.
        **({"body_parts": extra_parts_lines(character_extra_parts(sh))}
           if character_extra_parts(sh) else {}),
        "recent_self_lines": _self_lines,
        # One row per turn rather than one row per utterance. This is the
        # semantic continuity ledger: a chatty speaker cannot push the last
        # conversational job out of view merely by saying four short lines.
        "recent_self_moves": _self_moves,
        # The SHAPE those lines keep reusing, computed rather than left to the
        # character to notice about itself -- see _self_line_refrain. Absent
        # when there is no template, so its presence is the whole signal.
        "recent_self_refrain": _refrain,
        # How much this mind holds at once (affect.CAPACITY_LADDER), as the
        # concrete numbers rather than the rung name. Told rather than enforced
        # silently: commit caps wants and intentions deterministically either
        # way, and a character asked for three wants whose third is then culled
        # has had a decision taken from it without being told the decision
        # existed. The narrowing under absorption is included, so a mind whose
        # body is screaming sees the smaller number and chooses within it.
        "attention": {
            "wants": _want_cap,
            "intentions": _intent_cap,
            "band": _capacity_band,
            "means": affect.CAPACITY_DESCRIPTIONS[_capacity_band],
        },
        # Tier-2 goal hierarchy: the character's AUTHORED standing intentions
        # (its defining goals, always present so it acts proactively) merged
        # with EMERGENT intentions formed at runtime via intent_ops. An emergent
        # intention that restates an authored one wins (it carries live
        # progress/status). Read-only context for deriving this beat's wants.
        "intentions": _decision_intentions,
        # Status is not merely descriptive. Only these ids may steer a newly
        # formed want/response; dormant, blocked, satisfied and abandoned rows
        # remain visible for continuity but are not current purposes.
        "steering_intention_ids": _steering_intention_ids,
        # PROJECTS (Tier 1.5): at most two standing commitments -- what this
        # character is ABOUT right now. The live ledger once commit has
        # seeded it; the authored card list only on beats before the first
        # commit, and never once any live or former project exists, so a
        # project given up with a stated reason does not read as held again.
        "projects": _annotate_project_drift(
            (_interior.get("projects")
             if (_interior.get("projects")
                 or _interior.get("former_projects"))
             else character_projects(sh)) or [],
            ctx.turn.idx),
        # What was given up or finished, with the stated reason --
        # continuity, like former_drives, not obligation.
        "former_projects": _interior.get("former_projects") or [],
        # Former drives (scars) give continuity to a character who has changed.
        "former_drives": _interior.get("former_drives") or [],
        "learned_beliefs": _interior.get("beliefs") or [],
        "learned_associations": _interior.get("associations") or [],
    }
    # Exact handles for contacts this body can deliberately end.  The prose
    # view already tells the character what they feel; these opaque refs make
    # a completed pull-away structurally expressible without asking the model
    # to recreate the ledger's part spelling.  Names in the description pass
    # through the same recognition gate as every other structured character
    # payload field.
    _contact_label = observer_label_fn(chat, character_name(sh), ctx.cast)
    _standing_contacts = []
    for _index, _contact in enumerate(contacts_of(sc, character_name(sh))):
        _visible_contact = dict(_contact)
        for _side in ("actor", "target"):
            _visible_contact[_side] = _contact_label(_contact.get(_side))
        _standing_contacts.append({
            "contact_ref": f"contact:{_index}",
            "description": contact_phrase(
                _visible_contact, you=_contact_label(character_name(sh))),
        })
    if _standing_contacts:
        _self["standing_contacts"] = _standing_contacts
    # Own-mouth self-knowledge, the sibling of body_state below: a person
    # KNOWS their tongue is on someone, and a mind that was never told wrote
    # clean full sentences mid-lick (measured live: "Every inch of you,
    # darling.", articulate, tongue extended -- the model composing her line
    # believed her mouth was free). The sensation clause in her view says the
    # contact exists; this states its consequence for speaking, so the mind
    # can CHOOSE -- lift, finish first, or speak anyway and mean the slur.
    # Phrased without the other party's name on purpose: it is a fact about
    # this body's own mouth, so it owes nothing to the recognition gate.
    _speech_kind, _ = speech_articulation_impediment(sc, character_name(sh))
    if _speech_kind == "slurred":
        _self["speaking_now"] = {
            "articulation": "slurred",
            "sense": ("Your tongue is engaged on another body; words spoken "
                      "through it will come out slurred until you lift it."),
        }
    elif _speech_kind == "stifled":
        _self["speaking_now"] = {
            "articulation": "stifled",
            "sense": ("Your mouth is filled, sealed, or covered by a "
                      "standing contact; barely a word can be shaped until "
                      "it ends."),
        }
    # Following is a voluntary, durable decision this mind owns. Surface its
    # own relation as self-knowledge even after a fast target has pulled ahead;
    # separation does not silently decide whether it keeps chasing or stops.
    _following = sc.get("following") or {}
    _my_follow = next(
        (record for follower, record in _following.items()
         if str(follower).strip().casefold()
         == character_name(sh).strip().casefold()
         and isinstance(record, dict)),
        None,
    )
    if _my_follow:
        _self["following"] = {
            "target": _my_follow.get("target"),
            "since_turn": _my_follow.get("since_turn"),
            "reason": _my_follow.get("reason") or "",
            "target_room": room_of(sc, _my_follow.get("target")),
            "same_room": (
                room_of(sc, _my_follow.get("target")) == char_room
                if char_room else False),
        }
    _body_state = vitals_of(sc, character_name(sh))
    if _body_state:
        # Own-body interoception only. Other characters' vitals never enter
        # this payload; their outward signs must cross perception normally.
        _self["body_state"] = _body_state
    # What the room they stand in visibly affords, computed once for the
    # perception block below.
    _here_affords_now = here_affords(sc, character_name(sh))
    if _window_open:
        _self["rupture"] = {"why": _rupture.get("why"), "direction": _rupture.get("direction"),
                            "forced": _rupture_forced}
    if _crisis:
        _self["crisis"] = True
    if _recent_tells:
        _self["recent_tells"] = _recent_tells
    if _tell_grounds:
        _self["tell_grounds"] = _tell_grounds
    # The journey already underway, as a stated status -- see _en_route.
    # Same destination the exit verdicts and run offers are judged against.
    _underway = _en_route(stored_state, char_room, _goal_destination)
    if _underway:
        _self["en_route"] = _underway
    # A boundary passed at last commit (arrival where a project points, a
    # task closing, the scene or frame changing -- affect.project_boundary).
    # Shown for the one beat after it fired: the moment to re-ask what each
    # held project means for what happens next. An invitation, never a
    # mechanism -- no op is ever applied by the engine.
    # Deliberately NOT gated on already holding one. Paired with the identical
    # guard that used to open affect.project_boundary, this made the tier
    # unreachable: the prompt names this beat as the occasion to emit
    # project_ops, and the occasion required the thing it would create. 0 of 14
    # live banks have ever held a project. For a character with none, this flag
    # is the invitation; for one with projects it is the review it always was.
    _preview = _interior.get("project_review")
    if isinstance(_preview, dict):
        try:
            _fresh = ctx.turn.idx <= int(_preview.get("turn")) + 1
        except (TypeError, ValueError):
            _fresh = False
        if _fresh:
            _self["project_review"] = {
                "why": str(_preview.get("why") or "")}
    # Place purpose, the recall half (docs/design/DESIGN_PLACE_PURPOSE.md): a felt
    # need remembers the option. Triggered only by this character's OWN felt
    # vitals at the pressing tier, drawn only from their OWN place-graph
    # ledger plus name-derived expectation, routed only over their own
    # walked doorways (the en_route firewall), capped at two entries and
    # narrowed further by absorption -- a body screaming for attention
    # leaves less room to remember where the good bread was. Suppressed
    # when the room they stand in already answers the need. The engine
    # guarantees the mind REMEMBERS THE OPTION; hunger becoming an
    # intention, and the intention movement, stays the character's --
    # the URGENT rule's shape: the option must exist, the refusal may be
    # theirs. Never a want, never an op.
    _recalled = []
    _needs = felt_needs(_body_state)
    if _needs and char_room:
        _pg = stored_state.get("place_graph") or {}
        _here_answers = affords_here(_pg, char_room)
        _recall_cap = 2 if absorption < 0.5 else (1 if absorption < 0.85
                                                  else 0)
        _walked = _taken_adjacency(_pg.get("edges") or {})
        for _need in _needs:
            if len(_recalled) >= _recall_cap or _need in _here_answers:
                continue
            for _opt in place_options(_pg, char_room, _need, _walked):
                if len(_recalled) >= _recall_cap:
                    break
                _place = {
                    "name": _opt["name"], "affords": _need,
                    "basis": _opt["basis"],
                    "as_you_remember_it": (
                        "the next room" if _opt["hops"] == 1
                        else f"about {_opt['hops']} rooms from here"),
                }
                if _opt.get("sureness") is not None:
                    _place["sureness"] = _opt["sureness"]
                if _opt.get("note"):
                    _place["note"] = _opt["note"]
                _recalled.append(_place)
    if _recalled and isinstance(memory_context, dict):
        memory_context["recalled_places"] = _recalled
    # Absolutely no host-only row ids/counters reach the model.
    memory_context.pop("_internal", None)
    # Did the player speak this beat. Read once: it gates the silence note
    # and the consecutive-quiet query behind it.
    _p_spoke = str((ctx.get("director_interpret") or {}).get("speech") or "").strip()

    payload = {
        "self": _self,
        "perception": {
            "view": view or compositor_text("narrator_nothing", ctx.language),
            "observations": observations,
            # What THIS room visibly affords -- "rest (the bed)" -- a
            # structured echo of what the view already shows, from anchors
            # and co-present unconcealed entities under full light. Never
            # memory, never the room's name: expecting food of a tavern is
            # the ledger's business (memory.recalled_places), not
            # perception's. Omitted when nothing in the closed vocabulary
            # is visibly here.
            **({"here_affords": _here_affords_now}
               if _here_affords_now else {}),
            # This character's OWN egocentric exits (ahead/behind/left/right of
            # the way THEY face) -- grounding for their movement/positioning
            # choices, not a script to narrate. Empty when they have no
            # established orientation.
            # `label_for` gates the one field in here that names a body
            # (`ahead_entity`) through this character's own recognition, the
            # same way perception gates the prose beside it. Without it the
            # orientation frame handed over an identity the view was
            # deliberately withholding.
            "spatial_frame": _annotate_known_exits(
                spatial_digest(sc, character_name(sh),
                               label_for=observer_label_fn(
                                   chat, character_name(sh), ctx.cast)), sc,
                stored_state.get("visited_rooms") or [],
                known_exits=stored_state.get("known_exits") or {},
                here_rid=char_room,
                routes_that_worked=stored_state.get("routes_that_worked") or {},
                known_dead_ends=stored_state.get("known_dead_ends") or [],
                place_graph=stored_state.get("place_graph") or {},
                # The room his own goal text names, if he owns a node for
                # it -- see _destination_from_goals for the double gate.
                destination=_goal_destination),
            # Where they are, named. The digest lists what leads OUT of a room
            # without ever naming the room itself, so a character had to
            # re-derive their own location from the view's prose every beat.
            "current_room": (sc.get("rooms") or {}).get(
                character_room(sc, sh), {}).get("name") or "",
            # Looking straight down each passage: whether it ends, opens out or
            # bends, and roughly how far off. Coarse on purpose -- "some way
            # north the passage comes to an end" is the percept, not a room
            # count -- and it stops at corners, so it is sight rather than a
            # map.
            "corridor_sight": corridor_sightlines(sc, char_room),
            # How far a RUN gets down each passage, and what stops it.
            # Knowledge-gated and pruned to the offers worth having -- see
            # sprint_offers. An offer, not an instruction: a body that can
            # run is not a body that must.
            # The destination rides here too, so a run that carries him AWAY
            # from where he is going says so. Without it the exits named his
            # goal and the runs did not, and the loudest option was the one
            # with the least context.
            "sprint_reach": sprint_offers(sc, char_room, stored_state,
                                          destination=_goal_destination),
        },
        "memory": memory_context,
        "relationships": relationships,
        "mind_models": mind_models,
        # The stable hypothesis sheet: the few open questions this mind is
        # actively holding, each keyed "i_suspect" so the field itself carries
        # the epistemic status. mind_models above is the full ledger; this is
        # what is actually in mind, and its size shrinks with absorption.
        "active_hypotheses": active_hypotheses,
        "known_pronouns": _known_pronouns(
            ctx.cast, persona_of(chat),
            set(relationships) | set(mind_models),
            exclude=[character_name(sh)]),
        "private_knowledge": private_knowledge_for(chat, character_name(sh), ctx.turn.frame_id),
        "world_knowledge": knowledge,
        "decision": {
            "deep_tom_requested": cid in _tom,
            "dialogue_mode": bool(_flow.get("dialogue_mode", False)),
            "speech_budget": dialogue_budget(chat, ctx.turn, cid, nonce),
            # Silence is a thing the player DID, and nothing was saying so.
            #
            # A beat where they act without speaking produced a payload with no
            # line from them in it -- indistinguishable, from inside, from a
            # beat whose line had simply not been mentioned. The nearest thing
            # to an unanswered remark was then whatever they last said, several
            # beats back, and characters answered that: measured in chat 57,
            # two consecutive action-only inputs ("You get behind him, tails
            # still bristled") whose perception view describes the movement in
            # full and never says whether she spoke.
            #
            # Present only when the player is in the room, because otherwise it
            # is not this character's business whether the player spoke -- and
            # `positions` is the objective scene, the same source `attire`
            # above reads.
            **_player_silence_note(
                sc, chat, sh, _p_spoke,
                quiet_beats=(0 if _p_spoke else _player_quiet_beats(
                    chat.id, ctx.turn.idx, ctx.turn.frame_id, chat))),
            # Somebody asked this character something and they have not spoken
            # since. The engine knew; nothing told them.
            **_unanswered_question_note(
                chat.id, character_name(sh), cid,
                ctx.turn.idx, ctx.turn.frame_id),
        },
        "simulation_clock": _sim_clock,
        "variant_seed": nonce,
    }

    # Approach C's physical carrier envelope. This is THIS character's own
    # witnessed public surface, stored in their frame-specific state; no other
    # character receives it. A listener can learn it only if the holder speaks
    # on-page and ordinary perception/memory carries that speech across.
    try:
        from story.carriers import reports_for_state
        _carried_reports = reports_for_state(stored_state)
    except Exception as exc:
        _carried_reports = []
        ctx.add_warning(
            f"character {character_name(sh)}: carried reports unavailable: {exc}")
    if _carried_reports:
        payload["carried_reports"] = _carried_reports

    # The lazy gap rung (proposal section 1.2 step 2, the reader): a
    # character acting again after an absence gets the deterministic record
    # of their own interval -- where they were last seen with the player,
    # where they stand now, any offscreen ticks about them -- so the interim
    # is theirs to speak from instead of a blank the model paints over.
    # `offscreen_log` was written for months and read by nothing; this is
    # the first reader. Strictly the character's OWN gap: handing a mind a
    # gap about somebody else would be a channel that bypasses perception.
    # `interim_for` asks for the free rung and returns None rather than a
    # payload-tax "nothing happened", so this line costs tokens only when
    # there is an interval worth having.
    _interim = interim_for(chat["id"], sc, "character",
                           cast_entity_id(sh, row["id"]), ctx.turn.idx,
                           frame_id=ctx.turn.frame_id)
    if _interim:
        # The gap is prose somebody else wrote -- offscreen ticks and the
        # mapping_commit model, both of which write canonical names -- so it
        # passes the same identity floor as `world_knowledge` above, from
        # the same `known` map: a character must not meet their own interval
        # pre-identified with names no channel ever gave them.
        _gated_interim = scrub_names_deep(_interim, _name_scrub)
        if _gated_interim != _interim:
            ctx.add_warning(
                f"character {character_name(sh)}: scrubbed unearned "
                "identities out of while_you_were_offscreen gap text")
        payload["while_you_were_offscreen"] = _gated_interim

    # Authorial offers (P3): propositions the PLAYER authored about THIS
    # character's interior/behavior, rerouted here instead of being enacted as
    # truth (see director._route_authorial_npc_beat). The character decides
    # in-character how (or whether) each lands -- its agency is preserved.
    _offers = [o.get("proposition") for o in
               ((ctx.get("director_interpret") or {}).get("authorial_offers") or [])
               if o.get("subject_id") == cid and o.get("proposition")]
    if _offers:
        payload["decision"]["authorial_offers"] = _offers

    role = {"bg": "character_bg", "mid": "character_mid",
            "major": "character_major"}.get(character_tier(sh), "character_mid")

    # The contract, minus the paragraphs whose subject this beat's payload does
    # not carry. Built from the finished payload on purpose: the gate must read
    # what the model will actually receive, not re-derive the conditions a
    # second time and drift from them.
    _cprompt = character_prompt(
        payload, language=ctx.language).replace("{name}", character_name(sh))
    if _carried_reports:
        _cprompt += (
            "\n\nCARRIED REPORTS: carried_reports contains what you know about "
            "events elsewhere, and each one records how you came by it. "
            "`provenance:'witnessed_surface'` is something you saw yourself and "
            "have carried from where you saw it. `provenance:'told'` is "
            "something SOMEONE SAID TO YOU — `told_by` names them, and "
            "`retellings` counts how many mouths it passed through before "
            "yours. A told claim is already vaguer than the truth and gets "
            "vaguer the further it has come: treat it as what a person told "
            "you rather than as what happened, and let how much you trust that "
            "person decide how far you act on it. Any of them may be stale. Do "
            "not sharpen, complete, or infer details beyond the stored claim — "
            "what is missing is missing from the story you were given, and "
            "filling it back in would be knowing something nobody told you. "
            "Nobody else knows one merely because you carry it; they learn only "
            "if you say it on-page."
        )
    if _window_open:
        # The base contract never documents drive_shift; the instruction to emit
        # one exists ONLY inside an engine-opened rupture window, so a drive can
        # never flip-flop turn to turn.
        _cprompt += (
            "\n\nDRIVE RUPTURE (window OPEN this beat): a shattering, drive-level "
            "event has cracked what you live for (see self.rupture.why). This event "
            "has ALREADY changed you -- the only question is how the change surfaces. "
            "Denial is a phase, not a stable end: even if you cling to the old drive, "
            "show the crack in your behavior NOW (a ritual performed wrong, a "
            "signature line that dies mid-sentence, a rule reached for and found "
            "hollow). And if your core is genuinely remade, emit drive_shift "
            "{essence, expression, taboo, because}: essence = the new deepest thing "
            "you live for, expression = how it shows, taboo = what you now cannot "
            "do; `because` must name the rupture event. WORKED EXAMPLE: a magistrate "
            "whose drive was 'the law is the only shelter' watches the court execute "
            "the clerk she vouched for. She emits drive_shift {\"essence\": "
            "\"protect the person in front of me, not the rule\", \"expression\": "
            "\"quietly bends procedure to shield people\", \"taboo\": \"never again "
            "hand someone over to process\", \"because\": \"the court executed the "
            "clerk I vouched for\"} -- and her sequence THIS beat already shows it: "
            "she pockets the arrest warrant instead of filing it. A shift is rare "
            "and irreversible -- do not shift for a survivable wound; but do not "
            "play untouched calm either. NEVER announce the change in dialogue; it "
            "shows only in what you do and come to want.")
        if _rupture_forced:
            _cprompt += (
                "\n\nRUPTURE -- FORCED RESOLUTION: this window has now stayed open "
                "several beats and you have kept deferring. Deferral is over. THIS "
                "beat you must LAND it, one way or the other, visibly on the page -- "
                "passive, untouched, wait-and-see calm is NOT an available option "
                "anymore; the strain has been on you far too long for that. Choose "
                "exactly one and enact it in your sequence this beat: (A) emit "
                "drive_shift {essence, expression, taboo, because} AND let your "
                "action/speech this beat already do the new thing -- not a promise "
                "to change, the change itself; or (B) if your core genuinely holds, "
                "stop merely enduring and REAFFIRM it in a concrete, costly act your "
                "pre-rupture self would recognize as doubling down -- a line said, a "
                "hand that acts, a refusal made real. Do not simply describe the "
                "strain again. Resolve it.")
    if _crisis:
        _cprompt += (
            "\n\nCRISIS (self.crisis -- your drive is under extreme strain): what "
            "you live for is under sustained assault and your composure is FAILING. "
            "Your manifest must show it: surface_demeanor cracks at the seams, and "
            "your tells escalate from subtle to VISIBLE (subtlety <= 0.4) -- a "
            "voice that breaks mid-sentence, a hand that will not stay still, a "
            "pause held one beat too long. You need not change what you live for, "
            "but you can no longer look untouched. Do NOT announce the strain in "
            "dialogue; it leaks through the body.")
    if _recent_tells:
        _cprompt += (
            "\n\nTELL VARIETY: self.recent_tells lists the physical cues you have "
            "already shown in recent beats. Do NOT reuse any of them -- or a "
            "near-identical variant -- as this beat's tell; find a DIFFERENT "
            "channel or gesture. A body under the same pressure finds new ways to "
            "betray it: vary the channel (face|eyes|voice|hands|posture|breath) "
            "and the cue itself.")
    if _tell_grounds:
        _cprompt += (
            "\n\nTELL PAYOFF: self.tell_grounds lists physical cues you have "
            "recently shown and, for each, the private ground it betrayed "
            "(`because`). These are debts the story has planted: when the scene "
            "gives a natural opening, let a ground SURFACE -- in what you do, "
            "choose, or say -- so an observant witness's banked suspicion can pay "
            "off. Never contradict a ground already shown, and never announce it "
            "as exposition; it emerges through behavior.")
    # The routing seam. LAST thing before the model sees the payload, so an
    # extension edits what is actually sent rather than something the engine
    # then rebuilds. Total: any failure leaves the payload exactly as assembled
    # here, and every top-level key a hook changes is attributed to it on the
    # context and echoed in the turn's commit results.
    payload = _extension_character_payload(ctx, cid, payload, sh)

    out = _agent_json(
        role,
        "character",
        _cprompt,
        payload,
        temperature=character_temperature(sh),
        sampler=character_sampler(sh) or None,
    )

    # Deterministic decision-continuity screen. Semantic similarity is a review
    # trigger, not proof of bad repetition -- an invited continuation,
    # deliberate emphasis and an in-character riff all look the same to it --
    # which is why what follows RECORDS rather than re-asks.
    _repeated = _first_verbatim_repeat(
        _speech_texts(out), [str(l.get("said") or "") for l in (_self_lines or [])])
    _repeated_move = _first_repeated_move(out, _self_moves)
    _spent_refs = _nonsteering_intention_refs(
        out, _decision_intentions, ctx.turn.idx)
    _corrections = {}
    if _repeated:
        _corrections["repeat_correction"] = {
            "you_already_said": _repeated,
            "instruction": (
                "Your draft reissued this line you have already spoken. "
                "Say something else, act instead, or stay silent."),
        }
    if _repeated_move:
        _corrections["move_correction"] = {
            "turn": _repeated_move.get("turn"),
            "you_already_did": _repeated_move.get("move"),
            "your_draft_does": _repeated_move.get("current"),
            "instruction": (
                "This is mechanically close to a recent conversational job. "
                "Re-read the current beat. If it invited, answered, challenged, "
                "or materially advanced that thread -- or deliberate repetition "
                "is itself meaningful in character -- keep it, acknowledge the "
                "continuity, and advance it. This includes one continuous excited "
                "riff or rant; do not flatten the character's voice. Otherwise it "
                "is an unmotivated reset: changing the example, destination, "
                "metaphor, or noun is not progress, so drop the move and answer "
                "what is new, act, or stay silent."),
        }
    if _spent_refs:
        _corrections["intention_correction"] = {
            "nonsteering_ids": _spent_refs,
            "steering_ids": _steering_intention_ids,
            "instruction": (
                "Your draft lets a dormant/spent intention steer the choice. "
                "Do not merely relabel that behavior as situational. Choose "
                "from a live intention, the drive, the present situation, or "
                "let the spent thread rest."),
        }
    # NO RE-ASK. Repetition is WEAK, not unusable, and a redo that fires on
    # anything short of broken output is a nuisance -- the owner's rule, and
    # the measurements agree with it. What the re-ask cost was a full second
    # character call on the character's own model: 36.3s, 58.0s, and 155.6s
    # measured live, the last of those on a beat whose corrected answer
    # restated the same three propositions in different words. It was kept
    # unchanged 48 times across stored variants. Paying a frontier model to
    # re-author a whole decision in order to be told the decision was fine is
    # the expensive way to ask a cheap question, and asking it cheaply
    # (a small screen that judged whether the beat had invited the
    # repetition) only made a wrong answer cheaper: its own tie-break was
    # "when you cannot tell, answer redo". It is gone with the re-ask it
    # existed to gate.
    #
    # THE DEEPER REASON IT COULD NOT WORK. This file already says it, one
    # screen up: `recent_self_lines`, the refrain skeleton and the verbatim
    # rewrite "all say NOT THAT". A negative constraint helps a mind that has
    # another move and does nothing for one that does not -- so the retry
    # rephrased, every time, because rephrasing was the only move left. Live
    # (chat 80): a psychologist delivered the same three propositions on five
    # consecutive beats, and each retry changed the wording and kept the
    # propositions.
    #
    # So the corrections stop buying a call and start doing what they always
    # should have: they are recorded, and they arm the one mechanism that says
    # HERE IS SOMETHING ELSE YOU OWN. `_unbidden_trigger` surfaces a
    # contrasting memory to a measurably stuck mind, and its signals now
    # include the two this beat can prove.
    _repeat_survived = bool(_repeated)
    # Still handed to the intent ledger, which is the one consumer that was
    # never about re-asking: a `progress` claim on a beat that repeated an
    # earlier move does not advance the goal (`affect._advance_intent`).
    _barren_beat = bool(_corrections) and "move_correction" in _corrections
    for _name, _correction in sorted(_corrections.items()):
        ctx.add_warning(
            f"character {character_name(sh)}: {_name} -- "
            f"{str(_correction.get('you_already_said') or _correction.get('you_already_did') or _correction.get('nonsteering_ids'))[:100]!r} "
            "(recorded; the beat stands)")

    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json -- a
    # mind_model_updates entry that fails CharacterOutput validation can
    # never reach the cap/commit path below.
    out, warnings = validate_llm_output("character", out)
    ctx.warnings.extend(warnings)

    out = _normalize_character_output(out)
    # Attached AFTER validation: the schema dump drops unknown keys, so setting
    # it on the draft above would have posted the flag into a dict that is
    # thrown away, and the ledger would have gone on trusting the self-report.
    if _barren_beat:
        out["_barren_beat"] = True
    for _warning in _ground_observation_citations(
            out, observations, memory_context, memory_internal):
        ctx.add_warning(f"character {character_name(sh)}: {_warning}")
    # F6: every manifest tell gets a stored ground (`because`) -- supplied by
    # the model or derived deterministically from the tell's own `betrays`
    # pointer -- so a planted anomaly always has a referent a later beat can
    # pay off. The ground stays private (perception delivers only the cue).
    if out.get("manifest"):
        out["manifest"], _tell_warnings = ground_tells(
            out.get("manifest"), out.get("active_state"))
        for _w in _tell_warnings:
            ctx.add_warning(f"character {character_name(sh)}: {_w}")
    out["mind_model_updates"] = cap_mind_model_updates(
        out.get("mind_model_updates") or [], absorption=absorption)
    norm_sequence(out, warn=lambda _w: ctx.add_warning(
        "character %s: %s" % (character_name(sh), _w)))
    out["sequence"] = assign_event_ids(
        out.get("sequence"), f"turn:{ctx.turn.id}:character:{cid}")
    out["name"] = character_name(sh)
    out["char_id"] = cid
    # Unbidden-recall telemetry, riding the step output the same way name/
    # char_id do: the stage proposes, commit persists (the cstate.unbidden
    # ledger). No durable write happens here -- the character stage stays
    # read-only, which search_memories' own mid-pipeline access_count update
    # regrettably does not, and this code must not copy that.
    # An earlier micro-round's injection and repeat-screen outcome are carried
    # forward, because _merge_character_results keeps the LATEST probe: the
    # last round's probe must therefore tell the whole beat's story.
    out["unbidden_probe"] = {
        "stuck": bool(_unbidden_reason),
        "trigger": _unbidden_reason or "",
        "fired": (_unbidden_mem_id is not None
                  or bool(_prior_probe.get("fired"))),
        "memory_id": (_unbidden_mem_id
                      if _unbidden_mem_id is not None
                      else _prior_probe.get("memory_id")),
        "memory_ref": (_unbidden_mem_ref
                        if _unbidden_mem_ref is not None
                        else _prior_probe.get("memory_ref")),
        "repeat_survived": (_repeat_survived
                            or bool(_prior_probe.get("repeat_survived"))),
    }
    return out
