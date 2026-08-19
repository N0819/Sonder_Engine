"""Belief confidence at mint, at abandonment, and reconciled between.

Also the note on why there is no vector index -- it is about the rebuild above,
not about the confidences below it."""

from core.db import q, qi
from mind.theory_of_mind import belief_credence

from mind.memory_write import _json_list

# ---- Why there is no vector index ----
#
# There was a `sqlite-vec` ANN index here (`init_vec_index`,
# `search_memories_vec`). It never ran -- no caller, and the extension was
# never loaded -- and it was deleted rather than wired, because wiring it
# would have been a REGRESSION.
#
# `search_memories` filters its rows before ranking: the F1 turn cutoff (a
# mind deciding turn N must never retrieve how turn N turned out, live on
# every reroll) and frame visibility. The ANN query filtered on chat_id and
# char_id only, and those predicates are exactly the kind an ANN index cannot
# carry cheaply -- so a vec-first branch would have handed a character the
# committed outcome of its own undecided beat.
#
# And the scan it would have optimised does not need optimising. Memories
# accrue at ~3.5 rows per turn per character; measured with `_cos` verbatim,
# the full scan costs 16ms at a real story's worst case (442 rows), 126ms at
# ~1,000 turns, 709ms at ~10,000 -- beside an LLM call measured in seconds.
# Two cheap optimisations sit in front of an index anyway if it ever mattered:
# `_cos` recomputes both norms although every stored vector is already
# normalised (~4x), and the loop could be one matmul (~20x). See
# docs/UNBUILT.md §1.4.


# How far an inference the character no longer holds is pushed down, and the
# floor it stops at. Not zero: a belief that was explained away is still a
# belief they once had, and "I was sure of this and I was wrong" is a thing a
# character should be able to recall. It just must not outrank what replaced it.
#
# The demotion is a ONE-SHOT re-anchoring to a fraction of the confidence the
# character declared at mint time -- never a compounding per-turn decay on the
# current value. The predicate "no surviving hypothesis expresses it" is met by
# per-entity pruning and half-life expiry as well as by genuine explaining-away,
# and mind_models is a small working set while the memory bank is an archive:
# under the compounding rule, 76-80% of a long chat's entire inference bank
# reached the floor within 7-18 played turns of the rule landing (measured
# 2026-07-29 across the live corpus), at which point the belief-weighted
# ranking term removed inferences from recall almost completely (0-1 of top-8
# vs 13-15 at mint confidence in replayed late-turn retrievals). A belief that
# merely aged out of the working set was never concluded WRONG, and must not
# rank as though it was.
_ABANDONED_BELIEF_DECAY = 0.55
_ABANDONED_BELIEF_FLOOR = 0.08


def _mint_confidence_of(salience):
    """The confidence an inference row was minted with, recovered from its
    salience. commit.py mints inference memories with
    salience = 0.45 + 0.3 * confidence, and reconciliation deliberately never
    touches salience (it records how much the inference mattered when formed),
    so the mint-time confidence stays reconstructible without a second column.
    Rows whose salience was authored/imported outside that rule get a
    conservative low anchor rather than a crash."""
    try:
        return max(0.0, min(1.0, (float(salience) - 0.45) / 0.3))
    except (TypeError, ValueError):
        return 0.5


def _abandoned_confidence(salience):
    """The resting confidence for an inference no live hypothesis carries.

    A pure function of the row's (untouched) salience, which is what makes
    reconciliation idempotent: reconciling the same abandoned row on every
    subsequent turn lands on the same number instead of compounding it into
    unretrievability -- and a corpus previously crushed by the compounding
    rule self-heals to this value on its next reconcile pass, no migration.
    Clamped to never exceed the mint confidence, so a belief the character
    barely credited when they formed it is not lifted to the floor."""
    mint = _mint_confidence_of(salience)
    return min(mint, max(_ABANDONED_BELIEF_FLOOR,
                         mint * _ABANDONED_BELIEF_DECAY))


def reconcile_inference_confidence(chat_id, char_id, state, turn_idx,
                                   elapsed_seconds=None):
    """Re-weight this character's inference memories to what they believe NOW.

    An inference memory is minted with the confidence the character declared
    the moment they formed it, and nothing ever revisited it. Meanwhile their
    mind_models kept moving -- theory_of_mind.apply_mind_model_updates blends a
    restated belief upward, partially explains away the competitor it displaces,
    decays the unreinforced, and prunes what falls through the floor. So a
    character could hold one belief and preferentially RECALL the one they had
    already abandoned, because recall ranked on a number frozen at mint time.

    This projects the reconciled credence back onto the memories that expressed
    it: a claim still carried by a live hypothesis takes that hypothesis's
    decay-adjusted confidence; a claim no hypothesis carries any more is pushed
    toward _ABANDONED_BELIEF_FLOOR.

    Information-firewall note, because this is the part that matters: the only
    inputs are this character's OWN memory rows and their OWN mind_models, both
    already built from what they legitimately perceived. Nothing here consults
    the objective record, another mind's state, or whether the belief was
    actually TRUE -- a character revises because of what they later perceived,
    never because they were graded against reality. Reconciling against truth
    would collapse the belief layer into the truth layer, which is the one
    distinction this engine exists to keep.

    `salience` is deliberately untouched: it records how much the inference
    mattered when it was formed (and drives consolidation/archiving), which is
    a different question from how much the character credits it now.

    Returns the number of rows whose confidence changed.
    """
    rows = q(
        "SELECT id, entities, gist, salience, confidence FROM memories "
        "WHERE chat_id=? AND char_id=? AND kind='inference'",
        (chat_id, char_id),
    )
    if not rows:
        return 0

    updates = []
    for row in rows:
        subjects = _json_list(row["entities"])
        subject = str(subjects[0]).strip() if subjects else ""
        claim = str(row["gist"] or "").strip()
        if not subject or not claim:
            continue
        credence = belief_credence(
            state, subject, claim, turn_idx, elapsed_seconds)
        abandoned = _abandoned_confidence(row["salience"])
        if credence is None:
            # No live hypothesis carries this claim. That is NOT proof the
            # character concluded they were wrong -- mind_models prunes on
            # capacity and half-life as well as on displacement -- so the row
            # rests at a fixed fraction of its mint confidence (idempotent;
            # see _abandoned_confidence) rather than compounding downward on
            # every reconciled turn.
            revised = abandoned
        else:
            # A claim STILL STORED must never rank below one that was pruned:
            # half-life decay on a surviving hypothesis measures staleness,
            # not disbelief, so the live credence is floored at the abandoned
            # resting place. Held >= abandoned, always.
            revised = max(credence, abandoned)
        if abs(revised - float(row["confidence"] or 0.0)) > 1e-6:
            updates.append((round(revised, 4), row["id"]))

    for confidence, mid in updates:
        qi("UPDATE memories SET confidence=? WHERE id=?", (confidence, mid))
    return len(updates)
