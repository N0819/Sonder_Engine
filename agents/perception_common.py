"""Leaf helpers every other sibling reads: the active pack's recognizer tables
and the one sentence splitter, the observer-identity test, the human-seat
test, the step's player-room stamp, and the per-observer composer ledger
(previous beat's seen/standing/described records, standing metadata, learned
labels).

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import json
import re
from language_runtime import english_linguistic, linguistic
from core.db import q
from world.spatial import same_subject
from . import composer


# Sensory-channel cues in priority order, matched as whole words against ONE
# atom rather than a whole view -- an unanchored substring scan over a page of
# prose relabels everything ("paint" matched "pain", one quoted line made a
# page of body sensation 'hearing"), and a single channel cannot describe a
# beat that arrives through several at once.
def _ling(name):
    """One deterministic recognition table from the ACTIVE story pack.

    These cue tables used to be English literals in this module, and
    `linguistics.json` had no `agents.perception` entry at all -- so every
    Japanese percept fell through to the `mixed` channel with flat salience,
    and `_SELF_DIRECTED` never fired, telling an observer that an event
    landing on their own body was somebody else's business.

    Read at use time, never at import: the story language is a contextvar and
    two languages can be running in the same process.
    """
    return linguistic("agents.perception", name)


# Sentence end, script-aware, and the module's ONLY definition -- a second,
# weaker binding of this name lived 1,250 lines below and silently won, so
# every reader got a splitter that treated neither `...` nor a trailing
# bracket as an ending while this comment described one that did.
#
# The ASCII branch needs trailing whitespace; the CJK branch must not,
# because Japanese writes no space after 。 -- so an English-only splitter
# returned the WHOLE Japanese event as one "sentence", and every guard that
# keeps a safe subset of sentences (the concealment redactor above all) had
# no subset to keep.
#
# The terminator class carries `…`, because an ellipsis is how prose ends a
# sentence and a beat written with one reached the redactor as a single
# unsplittable block that had to be thrown away whole to protect one clause.
#
# Closing quotes and brackets ride WITH the sentence they end -- '…to me!?"
# The voice is…' must keep its quote -- so they sit inside the LOOKBEHIND
# rather than inside the match, where the split would eat them. That was the
# deleted twin's one genuine advantage over this one, and the reason the
# repair is a union rather than a deletion. Python requires a lookbehind to
# be fixed-width, hence one alternative per closer count rather than a `*`.
_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?…])\s+"
    r"|(?<=[.!?…][\"'”’)\]])\s+"
    r"|(?<=[.!?…][\"'”’)\]][\"'”’)\]])\s+"
    r"|(?<=[。！？])[」』\"'”’)\]]*\s*")

# Does this sentence ASSERT SIGHT -- somebody looking at something, in the
# verbs a view actually uses for it. Read by `_strip_self_narration`'s floor,
# which refuses to leave a perceiver with no sight at all. In the ACTIVE PACK
# (`agents.perception._SIGHT_ASSERTION`), because the floor is worth exactly
# what the pattern recognises: written in English literals, a Japanese view
# asserting 見える scored as containing no sight at all, so the refusal could
# never fire and the whole third-person cut went through.
#
# Deliberately its own pattern rather than `_atom_channel`'s "sight" cues:
# those classify a whole ATOM for the observation projection, they lean on
# second-person phrasing ("you see") that is by definition absent from the
# third-person views this floor exists for, and widening them would move
# every consumer of that classification.
#
# The name survives as the ENGLISH COMPAT EXPORT, the same convention
# `composer.DIM_FIGURE` keeps: bound once at import from the English pack, read
# by tests and audits, and NEVER by the floor itself -- which reads the active
# pack at use time, because two languages can be running in one process.
_SIGHT_ASSERTION = english_linguistic(
    "agents.perception", "_SIGHT_ASSERTION")


def _cue_hits(cues, folded):
    return sum(1 for cue in cues if re.search(cue, folded))


def _atom_channel(folded):
    for channel, cues in _ling("_CHANNEL_CUES"):
        if _cue_hits(cues, folded):
            return channel
    return "mixed"


def _stage_player_room(out, ctx):
    """Stamp the room this perception stage resolved the player into onto the
    stage's own saved content.

    A SIDE CHANNEL THAT SURVIVES A RESUME (review 2026-09-07 A31).
    `ctx["_player_room"]` is written by `common.player_room_in` and read by
    the stages after it -- `director_resolve` reads it directly, because it is
    the stage that DECIDES the room and needs the one the beat arrived with.
    It was written by assignment and carried by nothing, so a resume from
    `director_resolve`, or a single-step reroll of it, ran with None there:
    `_fig_rooms` lost the player's own room and the two floors below it were
    handed nothing. The step content is the only thing a resume restores, so
    the room goes on the step content and `runtime._rehydrate_side_channels`
    puts it back.

    Not a second source of truth: `player_room_in` still answers the question
    live, scene first, and this is only the record of what it answered. Which
    is why every stage stamps its own -- the onset room and the outcome room
    are different facts about the same beat, and rehydration walks them in
    ord order exactly as the turn did.
    """
    if isinstance(out, dict):
        out["player_room"] = str(ctx.get("_player_room") or "")
    return out


def _composer_prev_ledger(ctx):
    """The per-observer composer ledger from the PREVIOUS turn's stored
    perception step -- what each observer's view already carried (standing
    dedupe keys) and which full appearance descriptions were already
    delivered (first-mention tracking). Same recovery pattern as
    `_previous_open_group_continuity`: read the stored step, never live
    state."""
    cache_key = "_composer_prev_ledger_cache"
    if cache_key in ctx:
        return ctx.get(cache_key) or {}
    ledger = {}
    if ctx.turn.idx > 0:
        previous = q(
            "SELECT id FROM turns WHERE chat_id=? AND idx=?",
            (ctx.chat.id, ctx.turn.idx - 1), one=True,
        )
        if previous:
            rows = q(
                "SELECT s.key, v.content FROM steps s JOIN variants v "
                "ON v.step_id=s.id AND v.active=1 "
                "WHERE s.turn_id=? AND s.key IN "
                "('perception_establish','perception_act','perception_outcome')",
                (previous["id"],),
            )
            by_key = {}
            for row in rows:
                try:
                    by_key[row["key"]] = json.loads(row["content"])
                except (TypeError, ValueError):
                    continue
            for key in ("perception_outcome", "perception_act",
                        "perception_establish"):
                candidate = (by_key.get(key) or {}).get("composer_ledger")
                if isinstance(candidate, dict):
                    ledger = candidate
                    break
    ctx[cache_key] = ledger
    return ledger


def _composer_prev_seen(ledger, pid):
    """Bodies the previous beat could see, or None when it left no record.

    None is not the empty set. Treating a missing key as "saw nobody" would
    make the first beat after any older ledger re-describe every body in
    the room at once, which is the flood this distinction exists to avoid.
    """
    entry = (ledger or {}).get(str(pid)) or {}
    seen = entry.get("seen")
    return set(seen) if isinstance(seen, list) else None


def _composer_prev_state(ledger, pid):
    entry = (ledger or {}).get(str(pid)) or {}
    return (frozenset(entry.get("standing") or []),
            frozenset(entry.get("described") or []))


def _is_player_view(pid):
    """Whether this observer is a HUMAN seat -- the player, or one of the
    extra players in a shared chat. One spelling, because the composer's
    player tier and the standing record it feeds (D7) must agree on who gets
    it: `_composer_outcome` had the expression inline and
    `_composer_establish` had no answer at all."""
    pid = str(pid or "")
    return pid == "player" or pid.startswith("extra:")


def _composer_prev_meta(ledger, pid):
    """This observer's standing METADATA from a stored ledger, or {} (D7)."""
    entry = (ledger or {}).get(str(pid)) or {}
    meta = entry.get("standing_meta")
    return meta if isinstance(meta, dict) else {}


def _standing_meta(prev_meta, rendered, turn_idx, view):
    """{dedupe_key: {first_turn, last_rendered_turn, sentence}} for the
    standing facts THIS observer's view still carries (review D7).

    The ledger was a bare set of keys, which answers "have I been told this"
    and nothing else. A detail delivered once and then correctly suppressed
    by the player tier's delta is invisible from that set: the loaded object
    planted at beat 18 of the descent copy was still in the room 83 beats
    later, still filed under the same key, and had not reached a sentence
    since -- while the narrator's own window (`_PAST_NARRATION_TURNS`) reaches
    twelve turns back. Nothing anywhere held the two numbers that make that
    sayable.

    A KEY THAT SURVIVES IS AN UNCHANGED FACT. `composer.standing_key` hashes
    the subject and the CONTENT separately, so a pose that moved or an object
    that changed mints a different key and its old entry drops out here. The
    sentence carried forward is therefore still true of the thing it names --
    it is the observer's own last rendering of it, not a claim re-derived
    later.

    Entries exist only for keys that have actually reached a sentence: a key
    that never rendered (a voice key, a percept the tier dropped) has no
    delivered wording to refer back to. Keys absent from this beat's view are
    dropped, which is what bounds the record -- measured on the descent copy,
    5.3 standing keys per beat, never more than 11.

    THE DELIVERED VIEW IS THE AUTHORITY, not `rendered`. `rendered.spans`
    is the composition BEFORE `_composer_tripwires` runs, and this record
    outlives the beat: a sentence the identity tripwire rewrote, or one the
    self-narration strip dropped, would otherwise be filed here in its
    unrepaired wording and handed back to the narrator dozens of beats later
    -- the third-representation class `_repaired_observations` was written
    for, one field over. So a span files an entry only when its sentence
    survives VERBATIM in the view this observer was actually given; when it
    does not, the key simply keeps its older, already-delivered wording, or
    files nothing at all. A tripwire firing is an engine defect either way,
    and the contract is that when one fires nothing crosses.
    """
    try:
        now = int(turn_idx)
    except (TypeError, ValueError):
        return {}
    delivered = re.sub(r"\s+", " ", str(view or "")).strip()
    rendered_now = {}
    for percept, sentence in (getattr(rendered, "spans", None) or []):
        key = str(getattr(percept, "dedupe_key", "") or "")
        if not key or getattr(percept, "order_key", 0) is not None:
            continue
        flat = re.sub(r"\s+", " ", str(sentence or "")).strip()
        if flat and delivered and flat in delivered:
            rendered_now.setdefault(key, str(sentence))
    out = {}
    for key in sorted(getattr(rendered, "standing_keys", None) or ()):
        key = str(key)
        old = (prev_meta or {}).get(key)
        old = old if isinstance(old, dict) else {}
        sentence = rendered_now.get(key) or str(old.get("sentence") or "")
        if not sentence:
            continue
        try:
            first = int(old.get("first_turn"))
        except (TypeError, ValueError):
            first = now
        if key in rendered_now:
            last = now
        else:
            try:
                last = int(old.get("last_rendered_turn"))
            except (TypeError, ValueError):
                last = now
        out[key] = {"first_turn": min(first, now),
                    "last_rendered_turn": last,
                    "sentence": sentence}
    return out


def _is_the_observer(sc, candidate, observer, observer_aliases=()):
    """Is `candidate` another spelling of the observer's own name.

    AGENTS.md: one being, one name -- and a being routinely carries several
    at once. `character_scene_keys` names the cast half and says why readers
    must try all of them: "the director sometimes keys by identity.uid (or an
    alias)". `same_subject` covers the scene half, an entity id and its
    aliases. A bare `==` between two of those spellings is False, and this
    module already learned that lesson five times.

    Asked in the direction that matters: everything in a view is suppressed
    for the one person it is about, so a miss here does not leak -- it hands
    an observer their own line and their own act as somebody else's.
    """
    if same_subject(sc, candidate, observer):
        return True
    cand = str(candidate or "").strip().casefold()
    if not cand:
        return False
    return any(str(alias or "").strip().casefold() == cand
               for alias in observer_aliases or ())


def described_by(ctx, observer_key):
    """`(described, described_as)` for one observer: the bodies this
    observer's view has ever described in full, as the composer's body keys
    -- the per-observer first-mention ledger (`RenderedView.described`,
    carried forward beat to beat and never pruned) -- or None when no ledger
    is on record; and the label each was LEARNED under (`described_as`, the
    form the view gave at the last full sighting), {} on a ledger written
    before that field existed."""
    entry = (ctx.get("_composer_turn_ledger") or {}).get(str(observer_key))
    if not isinstance(entry, dict):
        entry = (_composer_prev_ledger(ctx) or {}).get(str(observer_key))
    if not isinstance(entry, dict):
        return None, {}
    described = entry.get("described")
    learned = entry.get("described_as")
    return ({str(k) for k in described} if isinstance(described, list) else None,
            {str(k): str(v) for k, v in learned.items()} if isinstance(learned, dict) else {})


def _prior_ledger_entry(ctx, pid):
    """The ledger entry this observer carried into this stage -- an earlier
    stage of this turn's, else the previous turn's -- or {} where the
    context keeps neither (a bare test context, an author preview)."""
    getter = getattr(ctx, "get", None)
    if callable(getter):
        entry = (getter("_composer_turn_ledger") or {}).get(str(pid))
        if isinstance(entry, dict):
            return entry
    try:
        entry = (_composer_prev_ledger(ctx) or {}).get(str(pid))
    except (AttributeError, TypeError):
        return {}
    return entry if isinstance(entry, dict) else {}


def _learned_labels(ledger_entry, percepts):
    """`described_as` carried forward with this beat's: for every stranger
    a presence line of this view showed at FULL sight, the label it was
    shown under. What the dark later calls a body seen once is THIS, not its
    present form: a disguise donned since was never seen, and one dropped
    since leaves the disguise the only form this observer knows.

    Only what the view composed (review rounds 2-3, 2026-10-05): learning
    from the whole display map learned a body standing behind the observer,
    whom the view never showed, and a later silhouette overwrote a face."""
    learned = dict((ledger_entry or {}).get("described_as") or {})
    generic = {composer._unfamiliar_person(), composer._dim_figure()}
    for p in percepts or ():
        if getattr(p, "kind", None) != "presence" or getattr(p, "fidelity", None) != "full":
            continue
        data = p.data or {}
        shown = str(p.source_label or "")
        if data.get("known") or not data.get("body") or not shown or shown in generic:
            continue
        learned[str(data["body"])] = shown
    return learned
