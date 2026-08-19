"""The deterministic prose-vs-diff floors of the Director's resolve seam.

Restraint and duress detection, consciousness onset in both directions
(a knockout the diff forgot; a mind the diff took away on nothing), the
waking exits, and the destruction tripwire. Detection substrate and seam
orchestration live elsewhere; the seam's block comment survives in
`agents/director.py` above `_reconcile_resolution`.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

import re

from story.character_schema import name_boundary_pattern
from story.scene import (
    NON_AWAKE_GATED,
    awareness_cond_level,
    awareness_conditions,
    awareness_kind_level,
    awareness_of,
)
from world.spatial import room_of

from .director_lingua import _ling

# Keep the keyword list small and specific so it does not fire on ordinary
# descriptive prose. This is a legacy high-precision detector for one known
# failure (a character held at gunpoint narrated but never written to
# state_diff.conditions); the general omission audit above it is what covers
# the open-ended class.

def _untracked_restraint_subjects(resolved_event, dialogue_log, conditions,
                                  tracked_names):
    """Named, tracked characters whose mention co-occurs with a restraint/
    duress keyword in resolved_event or a dialogue_log exact_quote, but who
    have no matching state_diff.conditions entry (matched by subject_id,
    casefolded). Sorted for deterministic output."""
    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict):
            quote = entry.get("exact_quote")
            if quote:
                text_units.append(str(quote))

    tracked_condition_subjects = set()
    for cond_value in (conditions or {}).values():
        cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
        for c in cond_list:
            if isinstance(c, dict):
                tracked_condition_subjects.add(
                    str(c.get("subject_id") or "").casefold())

    flagged_names = set()
    for text in text_units:
        lower = text.casefold()
        if not any(keyword in lower for keyword in _ling("_RESTRAINT_KEYWORDS")):
            continue
        for name in tracked_names:
            if name and name.casefold() in lower:
                flagged_names.add(name)

    return [name for name in sorted(flagged_names)
            if name.casefold() not in tracked_condition_subjects]

# Consciousness floor (awareness Phase 1). Observed live: an elevator crash
# resolved with the prose narrating the player "unconscious" and "knocked out"
# while state_diff.conditions was null -- so no `awareness` condition was born
# and perception kept handing the unconscious mind a full sighted view for
# turns. High-precision loss-of-consciousness cues, keyed on tracked names, and
# -- unlike the destruction tripwire -- this DOES feed the Tier-2 self-repair:
# an awareness condition is reversible and non-cascading, so a false positive
# costs one degraded beat while a miss is a multi-turn perception-barrier
# breach. HIGH-PRECISION via grammatical-subject attribution (like the
# destruction tripwire): a cue is pinned to the single nearest tracked name in
# the same clause, so a bystander merely co-mentioned with the fallen one ("Dr.
# Moon kneels beside the unconscious anomaly") is never flagged. It is the
# deterministic floor UNDER the broad semantic omission auditor, never the
# mechanism.
# "faint" is a verb and an adjective, and the adjective is far commoner in
# prose. Bare `faints?` matched "a FAINT pulse of rose-gold motes" and, with a
# name five tokens away, told the Director that Elyndra had lost consciousness
# mid-scene -- measured on chat 52's last beat, where she was doing nothing of
# the kind. This scan is the deterministic floor UNDER the semantic auditor, so
# a false positive costs far more than a miss: it instructs the Director to
# knock a character out, and the auditor above it still catches a real faint.
#
# The inflections are unambiguous, and the bare form is admitted only where a
# modal or infinitive marker makes it a verb ("might faint", "about to faint").
# Titles whose trailing period is not a sentence break (so "Dr. Moon" is one
# clause, and "unconscious ... Dr. Moon" across a real "anomaly." break stays
# two clauses).
_MAX_UNCONSCIOUSNESS_GAP = 5  # word tokens between a cue and its subject name


def _sentence_break_positions(low):
    """Offsets in casefolded `low` that terminate a sentence -- a '.', '!',
    '?' or newline -- excluding an abbreviation period (one preceded by a
    short title word in _TITLE_ABBREV). Used as clause barriers so a cue and
    a name on opposite sides of a real break are never paired."""
    breaks = []
    for m in re.finditer(r"[.!?]|\n", low):
        if low[m.start()] == ".":
            wm = re.search(r"([a-z]+)$", low[:m.start()])
            if wm and wm.group(1) in _ling("_TITLE_ABBREV"):
                continue
        breaks.append(m.start())
    return breaks


# The other direction of the consciousness floor above. That one catches a
# knockout the diff FORGOT; this catches a mind the diff took away on nothing.
# Observed live (chat 40 'Hmmm', turn 8): the player wrote "You breath softly as
# you close your eyes wrapping your arms around her", resting against another
# character, and the Director recorded awareness level 'asleep' on the PLAYER
# with cause "settling into rest and protective affection after arrival". Since
# 'asleep' is in NON_AWAKE_GATED the player's own next view became "You are
# under, below waking." -- the scene taken away from them for closing their eyes
# in a cuddle, and only endable by the Director choosing to end it.
#
# The asymmetry that justifies a floor here: for an NPC a spurious non-awake
# level costs one beat of silence, but for the PLAYER it removes both their view
# of the story and their next move, which is the Director overriding declared
# player conduct (AGENTS.md's information/agency boundary) in its strongest
# form. So the player alone is protected, and only against a level that GATES
# ('dazed' is untouched -- present but degraded). Support is read generously and
# from anywhere in the beat, because a false drop must be rarer than the false
# imposition it prevents.


def _awareness_support_in_beat(player_input, resolved_event, dialogue_log):
    """Did anything in this beat actually put the player under?

    Deliberately not subject-attributed, unlike the omission scan: this decides
    whether to KEEP the Director's judgement, so it errs toward keeping. Any
    sleep/knockout language anywhere in the player's own declaration or in the
    beat's prose is enough. What it excludes is the case that went wrong -- a
    beat where nobody said anything about going under at all.
    """
    texts = [str(player_input or ""), str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            texts.append(str(entry["exact_quote"]))

    return any(_ling("_SLEEP_CUE").search(text.casefold()) for text in texts if text)


def _unsupported_player_awareness(conditions, player_name, player_input,
                                  resolved_event, dialogue_log):
    """Condition keys that gate the PLAYER's mind on no stated basis.

    Returns [(key, level)] for awareness conditions that are ACTIVE, name the
    player as subject, sit at a gated level, and have nothing in the beat
    supporting them. An ending condition (active:0) is never touched -- that is
    the player WAKING, which must always be allowed through.
    """
    if not player_name:
        return []
    if _awareness_support_in_beat(player_input, resolved_event, dialogue_log):
        return []

    target = re.sub(r"[^a-z0-9]", "", str(player_name).casefold())
    if not target:
        return []

    unsupported = []
    for key, cond_value in (conditions or {}).items():
        cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
        for cond in cond_list:
            if not isinstance(cond, dict):
                continue
            level = awareness_cond_level(cond)
            if level is None:
                continue
            try:
                if not int(cond.get("active", 1)):
                    continue  # waking -- always allowed
            except (TypeError, ValueError):
                pass
            subject = re.sub(
                r"[^a-z0-9]", "",
                str(cond.get("subject_id") or "").casefold(),
            )
            if subject != target:
                continue
            if level in NON_AWAKE_GATED:
                unsupported.append((key, level))
                break

    return unsupported


# ---------------------------------------------------------------------------
# WAKING (awareness Phase 1, exit side).
#
# The two floors above police the ONSET of a non-awake state -- one catches a
# knockout the diff forgot, the other catches a mind the diff took away on
# nothing. Neither of them can end one, and until this block nothing else could
# either except the Director choosing to.
#
# Measured against the author's live corpus (engine.db, 1483 director
# resolve/establish variants across 44 chats): 24 `awareness` conditions were
# ever emitted and NOT ONE of them carried `active: 0`. The Director has never
# once ended an awareness condition in real play. The four that ever stopped
# gating stopped because they were born with `expires_at_seconds` and
# mechanics.py's clock expiry closed them; every condition without that field is
# still active, up to 75 turns after it was created. The reported incident is
# the whole class: chat 40 'Hmmm', turn 9 the player declared going to sleep
# (legitimate onset), turn 10 declared "You eventually wake when morning comes",
# turn 11 "You open your eyes and look around" -- and both resolves returned
# state_diff.conditions == {}. Turn 10's own `changes_asserted` said
# "conditions / Hinami / transitions from asleep to awake"; the Tier-1 manifest
# check caught the omission and the Tier-2 self-repair answered
# `already_encoded`, pointing at entities.hinami.state.posture =
# "awake_stirring_in_nest" -- a field nothing reads for awareness. The repair's
# word was taken and the condition stayed on.
#
# Two reasons, and both are fixed here:
#   1. The resolve payload never told the Director that anyone was under, or
#      under which condition_id. It cannot re-emit an id it was never given,
#      and after a context window it cannot remember one either. `_awareness_view`
#      puts the live rows in the payload.
#   2. Nothing deterministic enforced the exit. `_awareness_exits` is that
#      floor, and it covers only the cases where waking is not a judgement call.
#
# Whose call waking is: the WORLD's, never the sleeping mind's. A gated
# character runs no character step at all (agents/character.py's consciousness
# gate), which is correct -- a mind that is out does not deliberate -- but it
# also means an NPC generates no pressure to be woken, so a stuck sleeper reads
# as a quiet one. Every rule below is therefore driven by something outside the
# sleeper: their own player's declaration, another body's hands, or the clock.
_NATURAL_SLEEP_SECONDS = 8 * 3600  # ordinary sleep, on the simulation clock

# A deliberate act of rousing, aimed at a named sleeper. Deliberately narrower
# than "anything loud": attribution is by nearest name in the same clause (the
# `_untracked_unconsciousness_subjects` idiom), which cannot tell "shouts at the
# sleeper" from "shouts across the room the sleeper is in", so shouting/calling
# out is left to the Director rather than made deterministic. Hands on a body,
# or the word "wake" aimed at it, is unambiguous.
# What a PLAYER can say that means "leave me under". `_SLEEP_CUE` plus the
# stayings it does not cover. Kept separate from `_SLEEP_CUE` on purpose:
# that one decides whether to KEEP an onset and errs toward keeping, so
# widening it would make prose more likely to put the player under -- the
# direction the original bug came from.


def _clause_attributed_subjects(text_units, cue_re, subject_names,
                                prefer_object=False):
    """Names from `subject_names` that `cue_re` fires on in the same clause.

    The high-precision attribution `_untracked_unconsciousness_subjects` uses,
    lifted so the rouse scan reads the same way: a cue is pinned to the nearest
    candidate name in the same sentence within `_MAX_UNCONSCIOUSNESS_GAP` word
    tokens, so a bystander merely co-mentioned is never picked up.

    `prefer_object` flips which side of the cue wins, and the two scans need
    opposite answers. An unconsciousness cue is INTRANSITIVE -- "Hinami passes
    out" -- so its subject precedes it. A rouse cue is TRANSITIVE -- "Kaede
    shakes Tamamo awake" -- so the body being woken FOLLOWS it, and the nearest
    name is the waker. With the flag set, a name after the cue wins whenever
    the clause has one, and the preceding name is used only as a fallback ("she
    is shaken awake")."""
    name_res = [(name, re.compile(r"\b" + re.escape(name.casefold()) + r"(?:'s)?\b"))
                for name in subject_names if name]
    if not name_res:
        return set()
    flagged = set()
    for text in text_units:
        low = str(text or "").casefold()
        if not low:
            continue
        name_hits = [(m.start(), m.end(), name)
                     for name, rx in name_res for m in rx.finditer(low)]
        if not name_hits:
            continue
        breaks = _sentence_break_positions(low)
        for cm in cue_re.finditer(low):
            cs, ce = cm.start(), cm.end()
            best = None  # (side_rank, word_gap, name)
            for ns, ne, name in name_hits:
                if ne <= cs:            # name before the cue
                    lo, hi, side = ne, cs, 1 if prefer_object else 0
                elif ns >= ce:          # name after the cue
                    lo, hi, side = ce, ns, 0
                else:                   # overlaps the cue span; skip
                    continue
                if any(lo <= p < hi for p in breaks):
                    continue            # a sentence break separates them
                gap = len(re.findall(r"\w+", low[lo:hi]))
                if gap > _MAX_UNCONSCIOUSNESS_GAP:
                    continue
                if best is None or (side, gap) < best[:2]:
                    best = (side, gap, name)
            if best is not None:
                flagged.add(best[2])
    return flagged


def _declared_act_texts(interp, char_actions):
    """Every declared act in this beat, as text: the player's sequence and each
    character's actions. A rouse is an INTENTION by an agent, so the
    declarations are the primary evidence -- the resolved prose is scanned too,
    but a Director that narrated the shake without encoding it still counts."""
    texts = []
    for event in ((interp or {}).get("sequence") or []):
        if not isinstance(event, dict):
            continue
        texts.append(str(event.get("attempt") or ""))
        texts.append(str(event.get("observable") or ""))
    for _who, acts in (char_actions or {}).items():
        for act in (acts if isinstance(acts, list) else [acts]):
            if isinstance(act, dict):
                texts.append(str(act.get("attempt") or ""))
                texts.append(str(act.get("observable") or ""))
    return [t for t in texts if t]


def _rouse_attempts(interp, char_actions, resolved_event, gated_names):
    """Gated subjects somebody deliberately tried to wake this beat."""
    if not gated_names:
        return set()
    units = _declared_act_texts(interp, char_actions) + [str(resolved_event or "")]
    return _clause_attributed_subjects(units, _ling("_ROUSE_CUE"), gated_names,
                                       prefer_object=True)


def _sleep_elapsed(record, clock, diff_time):
    """Simulation seconds this condition has been in force at the END of this
    beat, or None when the clock cannot say. `started_at_seconds` is
    model-authored, so a negative or absurd span is treated as unknown."""
    end = None
    if isinstance(diff_time, dict):
        for key in ("end_seconds", "start_seconds"):
            try:
                if diff_time.get(key) is not None:
                    end = float(diff_time[key])
                    break
            except (TypeError, ValueError):
                end = None
        if end is not None and diff_time.get("end_seconds") is None:
            try:
                end += float(diff_time.get("duration_seconds") or 0.0)
            except (TypeError, ValueError):
                pass
    if end is None:
        try:
            end = float((clock or {}).get("elapsed_seconds") or 0.0)
        except (TypeError, ValueError):
            return None
    try:
        started = float(record.get("started_at_seconds") or 0.0)
    except (TypeError, ValueError):
        return None
    elapsed = end - started
    return elapsed if elapsed >= 0 else None


def _awareness_view(chat_id, clock, interp, char_actions, sd_time=None):
    """The `active_awareness` block the resolve payload carries.

    The Director has never once ended an awareness condition, and the first
    reason is that it was never shown one. Each entry names the condition_id it
    must re-emit with active:0, what put the subject under, whether someone is
    trying to wake them THIS beat, and whether the clock says an ordinary sleep
    is over."""
    records = awareness_conditions(chat_id)
    if not records:
        return []
    gated = [r for r in records if r["level"] in NON_AWAKE_GATED]
    roused = _rouse_attempts(interp, char_actions, "",
                             [r["subject"] for r in gated])
    view = []
    for record in records:
        elapsed = _sleep_elapsed(record, clock, sd_time)
        view.append({
            "condition_id": record["condition_id"],
            "subject": record["subject"],
            "level": record["level"],
            "cause": record["cause"],
            "rousable_by": record["rousable_by"],
            "gates_this_mind": record["level"] in NON_AWAKE_GATED,
            "under_for_seconds": None if elapsed is None else round(elapsed),
            "natural_wake_due": bool(
                record["level"] == "asleep" and elapsed is not None
                and elapsed >= _NATURAL_SLEEP_SECONDS),
            "someone_is_trying_to_wake_them": record["subject"] in roused,
        })
    return view


def _already_ended(cond_value):
    """Did the diff itself close this condition? Any entry with a falsy
    `active` counts; a re-assertion (active truthy, or absent, which defaults
    to active) does not."""
    for cond in (cond_value if isinstance(cond_value, list) else [cond_value]):
        if not isinstance(cond, dict):
            continue
        try:
            if not int(cond.get("active", 1)):
                return True
        except (TypeError, ValueError):
            continue
    return False


def _ending_condition(record, reason, kind="awareness"):
    """The same condition, closed. Built from the stored payload so nothing
    authored on it is lost, and keyed by the SAME condition_id -- commit
    UPDATEs on that id, and a fresh one would open a second row."""
    ended = dict(record.get("payload") or {})
    ended["condition_id"] = record["condition_id"]
    ended["subject_id"] = record["subject"]
    # The payload's own kind survives (post-vocabulary, a live row may spell
    # its family member differently); the fallback names the canonical kind
    # of the floor that ends it.
    ended["kind"] = str(ended.get("kind") or "").strip() or kind
    ended["active"] = 0
    ended["ended_reason"] = reason
    return ended


def _awareness_exits(chat_id, conditions, player_name, player_input,
                     interp, char_actions, resolved_event, clock, sd_time):
    """Awareness conditions the world has ENDED this beat, whatever the diff says.

    Returns (endings, warnings): endings is {condition_id: [ending_condition]}
    to merge into state_diff.conditions, warnings is prose for ctx.

    Three rules, each driven from outside the sleeping mind, and each covering
    only the part of waking that is not a judgement call:

    1. THE PLAYER DECLARED SOMETHING. Any non-empty player declaration that is
       not itself a request to stay under ends EVERY gated awareness condition
       on the player, at any level. This is the strong rule and it is meant to
       be: the player owns the declaration of their character's conduct
       (AGENTS.md, authority boundaries), the onset floor already refuses to put
       them under without their own input or unmistakable beat prose, and the
       Director keeps every other lever -- it may narrate the attempt failing,
       or impose the condition again with a fresh cause. Being wrong in this
       direction costs one beat the Director can re-narrate. Being wrong in the
       other direction is a chat that cannot be played, which is what the corpus
       actually contains.
    2. SOMEBODY TRIED TO WAKE THEM. A deliberate rouse aimed at a subject who
       is `asleep` ends it -- shaking a shoulder is the world at its least
       ambiguous, and it is the commonest beat in fiction. It does NOT end
       `sedated` or `unconscious`: those bodies do not sit up because they were
       shaken, and the refusal is a fact the Director should narrate, so it
       becomes a warning rather than an ending.
    3. THE NIGHT ENDED. A subject who has been `asleep` for a full ordinary
       sleep on the simulation clock wakes. Only `asleep`: a sedative wearing
       off is dosage, and unconsciousness resolving is medicine -- both belong
       to the Director, which the payload now equips to decide.
    """
    endings, warnings = {}, []
    if not conditions:
        return endings, warnings

    target = re.sub(r"[^a-z0-9]", "", str(player_name or "").casefold())
    gated = [r for r in conditions if r["level"] in NON_AWAKE_GATED]
    if not gated:
        return endings, warnings

    # 1. the player's own declaration
    declared = str(player_input or "").strip()
    player_acts = bool(declared) and not _ling("_STAY_UNDER_CUE").search(declared.casefold())
    if target and player_acts:
        for record in gated:
            subject = re.sub(r"[^a-z0-9]", "", record["subject"].casefold())
            if subject != target:
                continue
            endings[record["condition_id"]] = [
                _ending_condition(record, "player declared conduct while gated")]
            warnings.append(
                f"Ended awareness '{record['level']}' on the player "
                f"({player_name}): they declared conduct this beat, and a "
                "player's declaration of their own character cannot be "
                "overruled by a gate they are given no way to leave. Narrate "
                "the waking, or re-impose the condition with a stated cause. "
                "To stay under deliberately, the player's own input says so "
                "(\"you stay under\", \"you sleep on\", \"you dream of ...\").")

    # 2. somebody deliberately rousing them
    roused = _rouse_attempts(interp, char_actions, resolved_event,
                             [r["subject"] for r in gated])
    for record in gated:
        if record["subject"] not in roused:
            continue
        if record["condition_id"] in endings:
            continue
        if record["level"] == "asleep":
            endings[record["condition_id"]] = [
                _ending_condition(record, "roused by another character")]
            warnings.append(
                f"Ended awareness 'asleep' on {record['subject']}: someone "
                "deliberately woke them this beat and the diff did not record "
                "it. A rouse aimed at a sleeper works.")
        else:
            warnings.append(
                f"A rouse was aimed at {record['subject']}, who is "
                f"'{record['level']}' -- not sleeping. They do not wake from "
                "being shaken, and the resolved_event should say so as a fact "
                "rather than leave the attempt unanswered.")

    # 3. the clock
    for record in gated:
        if record["condition_id"] in endings or record["level"] != "asleep":
            continue
        elapsed = _sleep_elapsed(record, clock, sd_time)
        if elapsed is None or elapsed < _NATURAL_SLEEP_SECONDS:
            continue
        endings[record["condition_id"]] = [
            _ending_condition(record, "a full night's sleep elapsed")]
        warnings.append(
            f"Ended awareness 'asleep' on {record['subject']}: "
            f"{round(elapsed / 3600.0, 1)}h of simulation time have passed "
            "since they went under, which is a full sleep. Nothing else in the "
            "engine wakes a sleeper, so an unended sleep is permanent.")

    return endings, warnings


# ---------------------------------------------------------------------------
# RESTRAINT as a relation. `story/scene.py` reads each record's rung and
# holder; whether a record actually STOPS a body needs the scene, so it is
# decided here. A standing record (`bound`/`encased`, or `pinned` by a mass)
# holds with nobody attending it. A hold (`held`, or `pinned` by a body) is a
# live relation: it is in force only while the named holder is co-present and
# conscious, and a record that names no holder the scene can vouch for is a
# description handed to the Director, never a floor -- measured live, the
# holderless "held" rows are embraces whose own descriptions say "not a
# binding restraint" (chats 50/51) and a body gripping a console lever
# (chats 57/58), not captives.


def _restraint_holder_in(record, candidate_names):
    """The tracked body the record's holder field names, or None.

    Live rows name the holder inside a phrase as often as bare --
    `restrained_by: "Dr. Moon's hand"`, `enveloped_by: "Elyndra's
    entrance"` -- so a candidate name found anywhere in the field, on its
    own word boundaries, counts."""
    by = str(record.get("by") or "").strip().casefold()
    if not by:
        return None
    for name in candidate_names:
        label = str(name or "").strip()
        if not label:
            continue
        if label.casefold() == by or re.search(
                name_boundary_pattern(label.casefold()), by):
            return label
    return None


def _restraint_holder_pool(sc, extra_names=()):
    """Everything a holder field could legitimately name: tracked minds,
    every body with a position, and every scene entity by name or id --
    because a vine, a mechanism or a crowd-mass can hold a body exactly as a
    person can."""
    pool = [str(n) for n in (extra_names or ()) if n]
    pool += [str(k) for k in ((sc or {}).get("positions") or {})]
    for eid, ent in ((sc or {}).get("entities") or {}).items():
        name = str((ent or {}).get("name") or "").strip()
        if name:
            pool.append(name)
        pool.append(str(eid))
    return pool


def _hold_is_live(record, sc, amap, candidate_names):
    """Is a non-standing record's grip still physically in force?

    True: the holder is resolvable and nothing disproves the grip.
    False: positively broken -- the holder is in another room or below
    waking. A grip is a live relation between two bodies; it does not
    persist from another room or from unconsciousness.
    None: no holder the scene can vouch for. Unknown positions keep the
    hold (absence of data is not evidence of departure); an unresolvable
    holder never establishes one.
    """
    holder = _restraint_holder_in(record, candidate_names)
    if holder is None:
        return None
    if awareness_of(amap or {}, holder) in NON_AWAKE_GATED:
        return False
    subject_room = room_of(sc, record.get("subject"))
    holder_room = room_of(sc, holder)
    if subject_room and holder_room and subject_room != holder_room:
        return False
    return True


def _restraint_blocked_moves(sd, sc, records, amap, candidate_names):
    """[(who, record)] for each self-relocation this diff writes that a
    restraint actually stops. Judged per record, because restraints are
    additive: a body is as restrained as the strongest thing on it, and six
    live rows on one body (chat 80) must not be masked by the vaguest.

    Being CARRIED somewhere while restrained is legitimate -- that is the
    restrainer moving them, not them walking off -- and a position write
    that changes nothing (or first places the body) is no move at all.
    """
    out = []
    positions = sd.get("positions") if isinstance(sd, dict) else None
    if not records or not isinstance(positions, dict):
        return out
    prior = (sc.get("positions") or {})
    by_subject = {}
    for record in records:
        by_subject.setdefault(record["subject"].casefold(), []).append(record)
    for who in list(positions):
        subject_records = by_subject.get(str(who).casefold())
        if not subject_records:
            continue
        was = prior.get(who)
        if was is None or positions[who] == was:
            continue
        if (sc.get("contained") or {}).get(who):
            continue
        for record in subject_records:
            if record.get("standing") or _hold_is_live(
                    record, sc, amap, candidate_names):
                out.append((who, record))
                break
    return out


# ---------------------------------------------------------------------------
# RELEASE (the exit side of restraint).
#
# The same trap the WAKING block above records for awareness, one section up:
# a gate that can be entered and not left is worse than no gate. Measured
# against the author's live corpus before this landed, the Director had never
# once ended ANY condition by re-emitting it with active:0 (0 of 1483
# resolves), and the restraint rows bear it out: 24 active, zero ever ended,
# the oldest standing for a whole story. The same two causes, the same two
# repairs: the resolve payload never showed the Director a restraint or its
# condition_id (`_restraint_view` now does), and nothing deterministic
# enforced the exits that are not judgement calls (`_restraint_exits`).
#
# What is deterministic here is narrower than waking, because restraints do
# not end by themselves on a clock: a rope stays tied all night. The floor
# ends only (1) a hold whose holder is POSITIVELY gone -- physics, not
# adjudication -- and (2) a release the Director's own resolved prose already
# asserts. Escape ATTEMPTS -- struggling, working at the knots -- are
# contests, and contests are the Director's.


def _release_attempts(resolved_event, restrained_names):
    """Restrained subjects whose release the resolved prose asserts.

    Reads ONLY resolved_event -- the Director's own adjudicated account --
    never declared acts (an attempt is not a completion) and never dialogue
    quotes ("I'll untie you" is a plan spoken by someone still holding the
    rope). Cues are completed-release verbs; attribution is the same
    clause-pinned idiom as the rouse scan, object-side first, because a
    release is transitive ("Sarah uncuffs Hinami")."""
    if not restrained_names:
        return set()
    return _clause_attributed_subjects(
        [str(resolved_event or "")], _ling("_RELEASE_CUE"), restrained_names,
        prefer_object=True)


def _restraint_view(records, sc, amap, clock, sd_time, candidate_names):
    """The `active_restraints` block the resolve payload carries.

    The Director has never once ended a restraint condition, and the first
    reason is that it was never shown one. Each entry names the condition_id
    it must re-emit with active:0, who or what holds the subject, whether
    that hold is still physically live, and how long the body has been
    restrained on the simulation clock."""
    view = []
    for record in records or []:
        elapsed = _sleep_elapsed(record, clock, sd_time)
        hold = (None if record.get("standing")
                else _hold_is_live(record, sc, amap, candidate_names))
        view.append({
            "condition_id": record["condition_id"],
            "subject": record["subject"],
            "level": record["level"],
            "by": record["by"],
            "means": record["means"],
            "escapable_by": record["escapable_by"],
            "holds_unattended": bool(record.get("standing")),
            # None: this hold names no holder the scene can vouch for, so
            # it blocks nothing and only the Director can settle it.
            "holder_still_holding": hold,
            "restrained_for_seconds": (None if elapsed is None
                                       else round(elapsed)),
            "blocks_self_relocation": bool(record.get("standing") or hold),
        })
    return view


def _restraint_exits(records, resolved_event, sc, amap, candidate_names):
    """Restraint conditions the world has ENDED this beat, whatever the diff says.

    Returns (endings, warnings) exactly as `_awareness_exits` does: endings
    is {condition_id: [ending_condition]} to merge into
    state_diff.conditions, warnings is prose for ctx.

    Two rules, each covering only the part of release that is not a
    judgement call:

    1. A HOLD NEEDS A HOLDER. A hold (`held`, or `pinned` by a body) whose
       named holder is positively elsewhere or below waking has physically
       ended -- a grip is a live relation, and nobody goes on gripping from
       another room or from unconsciousness. Standing restraints are
       untouched: a knot stays tied when the tier walks away. So is a hold
       whose holder the scene cannot vouch for -- ending what cannot be
       verified is adjudication, and the view already tells the Director the
       record vouches for nobody.

    2. A RELEASE THE PROSE ASSERTS. A completed-release cue pinned to a
       restrained subject in resolved_event ends every record on them: the
       Director adjudicated the release when it wrote the sentence, and the
       floor only encodes what the prose already asserts. A partial release
       (one cuff of two) is the Director's to re-impose, which the warning
       says.
    """
    endings, warnings = {}, []
    if not records:
        return endings, warnings

    # 1. holds whose holder is positively gone
    for record in records:
        if record.get("standing"):
            continue
        if _hold_is_live(record, sc, amap, candidate_names) is False:
            endings[record["condition_id"]] = [
                _ending_condition(record, "the holder is no longer holding "
                                  "them", kind="restraint")]
            warnings.append(
                f"Ended restraint '{record['level']}' on {record['subject']}"
                + (f" (by {record['by']})" if record["by"] else "")
                + ": the holder is in another room or below waking, and a "
                "grip cannot outlive its holder's presence. Narrate the "
                "release if it has not been, or re-impose the hold with the "
                "holder actually there.")

    # 2. releases the resolved prose asserts
    released = _release_attempts(
        resolved_event, [r["subject"] for r in records])
    for record in records:
        if record["subject"] not in released:
            continue
        if record["condition_id"] in endings:
            continue
        endings[record["condition_id"]] = [
            _ending_condition(record, "a release narrated this beat",
                              kind="restraint")]
        warnings.append(
            f"Ended restraint '{record['level']}' on {record['subject']}: "
            "the resolved prose asserts their release and the diff did not "
            "record it. If anything still holds them -- a second binding, "
            "one cuff of two -- re-impose it as its own condition.")

    return endings, warnings


def _untracked_unconsciousness_subjects(resolved_event, dialogue_log, conditions,
                                        tracked_names):
    """Named, tracked characters narrated as losing consciousness with no
    matching `awareness` condition in the diff. Each cue is attributed to a
    SINGLE subject -- the nearest tracked name in the same sentence within
    _MAX_UNCONSCIOUSNESS_GAP words -- so a bystander merely co-mentioned with
    the fallen one is never flagged. Presence check is specific to
    kind:'awareness'; an unrelated wound/restraint condition on the same
    subject must not suppress the awareness flag."""
    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            text_units.append(str(entry["exact_quote"]))

    aware_subjects = set()
    for cond_value in (conditions or {}).values():
        for c in (cond_value if isinstance(cond_value, list) else [cond_value]):
            if (isinstance(c, dict)
                    and awareness_kind_level(c.get("kind")) is not None):
                aware_subjects.add(str(c.get("subject_id") or "").casefold())

    flagged = _clause_attributed_subjects(
        text_units, _ling("_UNCONSCIOUSNESS_CUE"), tracked_names)
    return [n for n in sorted(flagged) if n.casefold() not in aware_subjects]

# Destruction tripwire (movement/space Phase 3b follow-up). Observed live:
# the resolved_event narrated a whole-town firestorm consuming a named
# region ward by ward, yet state_diff.destruction was null and remove_rooms
# empty -- so the Phase-3b cascade (which only realizes a DECLARED
# destruction) never fired and the town stayed objectively intact against
# the prose. Same design constraints as the restraint scan: deterministic,
# HIGH-PRECISION, and WARN-ONLY -- this engine never fabricates objective
# state from a heuristic, and a wrongly-invented razing (books retired,
# rooms gone, news minted) would be far worse than a stale-missing one, so
# this detector deliberately does NOT feed the Tier-2 self-repair path.
#
# Precision guard: a bare keyword scan ("the fire spread") or even
# sentence-level co-occurrence ("the letter was destroyed in the hall"
# flagging the hall) false-fires on ordinary flavor. Matching is keyed on
# ACTUAL known place names (scene rooms, the scene location, interior-
# bearing entities, live lorebook names) in destruction-shaped grammatical
# positions only:
#   subject-first:  "<name> ... was razed / burned down / in ruins"
#   verb-object:    "razed/consumed/destroyed (the) <name>"
#   of-phrase:      "ruins/ashes/nothing left of <name>"

def _destruction_name_pattern(name_cf):
    """One compiled pattern per known place name covering the three
    destruction-shaped positions above. Bounded word-gaps, not free
    sentence co-occurrence.

    The name boundary is script-aware and the gaps allow an unspaced run:
    `\\b` never fires against a Japanese particle, and `\\s+` between a cue and
    a name assumes words are spaced, so all three positions were dead in
    Japanese. The English genitive and determiners stay OPTIONAL rather than
    being removed -- a Japanese story still carries them through
    code-switching and imported names.
    """
    name = name_boundary_pattern(name_cf)
    gap = r"[,\s]*"
    return re.compile(
        rf"{name}(?:'s)?{gap}(?:\S+\s+){{0,4}}?{_ling("_DESTRUCTION_TERMINAL_CUES")}"
        rf"|{_ling("_DESTRUCTION_VERB_OBJECT")}{gap}"
        rf"(?:the\s+|all\s+of\s+|the\s+whole\s+|the\s+entire\s+|most\s+of\s+)?"
        rf"{name}"
        rf"|{_ling("_DESTRUCTION_OF_PHRASE")}{gap}(?:the\s+)?{name}"
    )

def _narrated_destruction_subjects(resolved_event, dialogue_log, sd, sc,
                                   extra_names=()):
    """Named, KNOWN places (scene rooms, the scene location, interior-
    bearing entities, plus extra_names -- live lorebook names) that the
    prose asserts destroyed while the diff encodes neither
    state_diff.destruction nor a remove_rooms/remove_entities entry
    covering them. Sorted labels for deterministic output.

    Any declared destruction this beat suppresses the whole scan: scoping
    what the cascade covers is commit's job, not a text heuristic's.
    """
    destruction = sd.get("destruction")
    if isinstance(destruction, dict) and destruction.get("target_id"):
        return []

    candidates = {}

    def _add(label, room_ids=(), entity_ids=()):
        label = str(label or "").strip()
        if len(label) < 3:
            return
        key = label.casefold()
        cand = candidates.setdefault(key, {
            "label": label, "room_ids": set(), "entity_ids": set(),
            "pattern": _destruction_name_pattern(key),
        })
        # Prefer a display-cased label (room "name") over a lowercased
        # id-derived one for the same key -- it names the warning.
        if cand["label"].islower() and not label.islower():
            cand["label"] = label
        cand["room_ids"].update(room_ids)
        cand["entity_ids"].update(entity_ids)

    for rid, room in (sc.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        _add(str(rid).replace("_", " "), room_ids={str(rid)})
        _add(room.get("name"), room_ids={str(rid)})
    location = str(sc.get("location") or "").strip()
    if location:
        _add(location)
        _add(re.split(r"[,—]", location)[0])
    for eid, ent in (sc.get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        kind = str(ent.get("kind") or "").casefold()
        if not (ent.get("interior_rooms")
                or kind in ("vehicle", "building", "structure")):
            continue
        _add(ent.get("name"), entity_ids={str(eid)})
        _add(str(eid).replace("_", " "), entity_ids={str(eid)})
        for alias in (ent.get("aliases") or []):
            _add(alias, entity_ids={str(eid)})
    for name in extra_names:
        _add(name)

    removed_rooms = {str(r) for r in (sd.get("remove_rooms") or [])}
    removed_entities = {str(e).casefold()
                        for e in (sd.get("remove_entities") or [])}

    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            text_units.append(str(entry["exact_quote"]))

    flagged = {}
    for text in text_units:
        lower = text.casefold()
        for key, cand in candidates.items():
            if key in flagged:
                continue
            if not cand["pattern"].search(lower):
                continue
            if cand["room_ids"] & removed_rooms:
                continue
            if {e.casefold() for e in cand["entity_ids"]} & removed_entities:
                continue
            flagged[key] = cand["label"]
    return [flagged[key] for key in sorted(flagged)]

def _scan_for_untracked_restraint(resolved_event, dialogue_log, conditions,
                                   tracked_names):
    """Return warning strings for the subjects _untracked_restraint_subjects
    flags. Kept as a stable, directly-testable entry point; director_resolve
    now routes these through the reconciliation seam (which may repair the
    diff first) and emits this exact text only for what remains unencoded.
    """
    return [
        f"Possible untracked physical restraint/duress detected for "
        f"{name!r} (restraint/duress keyword found alongside their "
        "name in resolved_event or dialogue) but no matching "
        "state_diff.conditions entry was recorded this beat."
        for name in _untracked_restraint_subjects(
            resolved_event, dialogue_log, conditions, tracked_names)
    ]
