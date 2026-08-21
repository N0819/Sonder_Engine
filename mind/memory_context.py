"""The character memory payload.

Where retrieval, summaries and the active state become one context -- the
assembly seam, and the only place that decides what a mind is handed."""

from core.db import q
from llm.providers import embed_texts_meta
from llm.prompts import payload_legacy

from mind.memory_common import (
    SUMMARY_SCOPE_FIRSTHAND, _SUMMARY_SCOPES, summary_context_label,
)
from mind.memory_write import _clamp
from mind.memory_retrieval import (
    _RECALL_LIMIT, _SUMMARY_RECALL_LIMIT, provenance_context_label,
    recent_memory_buffer, search_memories,
)
from mind.memory_summaries import (
    backfill_missing_memory_event_keys, get_memory_summary,
    search_memory_summaries,
)

def _with_reading(mem, current_turn_idx=None):
    """Project one stored row as an explicitly PAST character memory.

    Present observations use ``current:<perceiver>:<n>`` ids. Memories cite
    their durable ``event_key`` and say ``remembered_past`` in the data itself,
    so a model does not have to infer temporal status from which parent list
    happened to contain the row. The numeric ``id`` stays host-only.

    The memory itself remains unchanged -- content, gist, provenance and
    salience all stay as recorded -- and a later re-reading travels beside it
    under its own key. A mind that was deceived holds both the experience and
    the correction.

    The key is phrased as the character's own voice, matching the
    `it_comes_back_to_me` / `i_suspect` precedent -- epistemic status carried
    by the key rather than by prose a model can drop.

    WHAT THIS DELIBERATELY DOES NOT PROJECT. Three fields were carried here for
    no reader on the deciding side, measured across the live banks:

      * ``key_phrases`` -- 12 short cues per row, 80% of them already verbatim
        in the gist/details beside them, and never once named in the 61 KB
        character prompt. Its consumers are ``memory_retrieval_fts`` and
        ``_retrieval_text`` -- retrieval machinery, not the mind deciding.
      * ``category`` -- one host-side reader (``promise_memories``' SQL), and
        across 900 corpus rows only four (category, epistemic_origin) pairs
        occur, so it restates a label the row already carries.
      * ``memory_form`` -- the constant ``"episode"`` on every row this
        function projects. Summaries set their own, so ABSENCE now means
        episode and the distinction survives.

    The columns stay written and stay indexed; only the projection narrows, so
    recall quality cannot move by construction. Together with the gist rule
    below this is 5.8 KB of a 26.8 KB delivered block (chat 72, 24 rows).
    """
    # Model projection only.  ``dict(mem)`` used to leak database ids,
    # access counters, archive state, embedding metadata and retrieval scores
    # into the character's mind.  Those are host diagnostics, not memories.
    out = {
        "memory_ref": str(mem.get("event_key") or ""),
        # RESTORED after measurement. Removing this per-row constant was the one
        # compaction that cost something: `appraisal.goal_impacts[].evidence` is
        # grounded namespace="present", so a memory_ref cited there is dropped as
        # ungrounded and the impact zeroed -- past evidence mis-laned as present,
        # 0 occurrences before and 2 after across three live turns, alongside the
        # same lane failure in tools/benchmark_memory_temporal.py's anomaly_now.
        # The label never varies, so it cannot ORDER anything (`when` does that);
        # what it does is mark the lane, per row, at the point of use. 0.9 KB of
        # a 26 KB block is a cheap price for a discrimination the engine cannot
        # re-impose downstream -- a dropped citation is evidence already lost.
        "temporal_status": "remembered_past",
        "epistemic_origin": provenance_context_label(mem.get("provenance")),
        "gist": mem.get("gist") or "",
        "details": mem.get("content") or "",
        "entities": list(mem.get("entities") or []),
        "location": mem.get("location") or "",
        "confidence": float(mem.get("confidence") or 0.0),
        "felt_importance": float(mem.get("importance") or
                                 mem.get("salience") or 0.0),
        "affect_before": {
            "label": mem.get("emotional_context") or "",
            "valence": float(mem.get("valence") or 0.0),
            "arousal": float(mem.get("arousal") or 0.0),
        },
        "affect_after_encoding": {
            "valence": float(mem.get("encoding_valence") or 0.0),
            "arousal": float(mem.get("encoding_arousal") or 0.0),
        },
    }
    if payload_legacy("fields"):
        out["memory_form"] = "episode"
        out["category"] = mem.get("category") or "episode"
        out["key_phrases"] = list(mem.get("key_phrases") or [])
    if not payload_legacy("gist"):
        # A gist that is a PREFIX of its own details is not a low-resolution
        # recall, it is the first sentence twice. Measured on chat 72's live
        # bank: 4% byte-identical, 77% a substring, median length ratio 0.52 --
        # so the consolidator does compress, and the rows where it did not are
        # the ones that carry nothing the details below do not already say.
        # Dropped only in that case; a genuinely condensed gist survives.
        gist = str(out.get("gist") or "").strip()
        details = str(out.get("details") or "").strip()
        if gist and details and gist.casefold() in details.casefold():
            out.pop("gist", None)
    out = {k: v for k, v in out.items()
           if v not in ("", [], {}) or k in {
               "memory_ref", "temporal_status", "memory_form",
               "epistemic_origin", "confidence", "felt_importance"}}
    ti = mem.get("turn_idx")
    if ti is None:
        out["when"] = "before this story's recorded turns"
    elif current_turn_idx is not None:
        age = max(1, int(current_turn_idx) - int(ti))
        out["when"] = "about 1 beat ago" if age == 1 else f"about {age} beats ago"
    dispute = mem.get("disputed")
    if not dispute:
        return out
    out["i_now_read_this_differently"] = dispute.get("reading") or ""
    if dispute.get("count", 0) > 1:
        out["times_i_have_reconsidered_it"] = int(dispute["count"])
    return out


def _beats_ago_span(current_turn_idx, start_turn_idx, end_turn_idx):
    """When an earlier window happened, in the character's own units.

    RELATIVE, never the absolute turn index, and that is a firewall rule rather
    than a style choice: `turn_idx` is GLOBAL play order shared by every frame,
    so an absolute number tells a character where a flash-forward or flashback
    sits in the story's construction -- something no mind in the fiction has any
    way to know. Every other dated thing in the payload says "about N beats ago"
    for the same reason (see `_unbidden_entry`).
    """
    if current_turn_idx is None:
        return ""
    oldest = int(current_turn_idx) - int(start_turn_idx or 0)
    newest = int(current_turn_idx) - int(end_turn_idx or 0)
    if newest <= 0:
        # Defensive only: every read seam must withhold a window that closed at
        # or after the deciding turn. Never relabel future knowledge "just now".
        return ""
    if oldest == newest:
        return f"about {oldest} beats ago"
    return f"between about {newest} and {oldest} beats ago"


def _summary_id(scope, end_turn_idx):
    """A citable, explicitly-past id for one delivered summary window."""
    return f"summary:{scope}:{int(end_turn_idx or 0)}"


def _origin_on_drift(chat_id, char_id, current_turn_idx, active_state, *,
                     earlier_ids=()):
    """Surface the character's ORIGIN summary window when a drift signal fires.

    An origin is not a similarity match: a character's foundational era is
    frequently dissimilar to whatever is happening now, which is exactly when
    it should still be present. Top-k similarity ranking drops it in the beats
    where it matters most (UNBUILT §1.21).

    Three drift signals, all already tracked in the active state:

    - **goal_held**: the same ungoverned goal for 12+ beats (the character is
      stuck in a rut, not pursuing something).
    - **project adrift**: a held project has gone 8+ beats without anything
      serving it (the character has lost the thread of what they set out to do).
    - **mood sign-flip**: the current mood's valence has flipped sign from the
      character's baseline (a despairing character who was once hopeful, or
      vice versa) -- the moment a person reaches for who they were before the
      current stretch swallowed them.

    When any signal fires, the earliest first-hand summary window is fetched
    and included under ``where_i_came_from``. It is NOT added to
    ``earlier_in_my_life`` because those are similarity-ranked; the origin is
    surfaced for a different reason and should not compete for a similarity
    slot. Absent (not empty) when no signal fires or when there is no origin
    window to reach.

    ``earlier_ids`` is the set of ``end_turn_idx`` values already in the
    ``earlier_in_my_life`` payload, so the origin is not sent twice when
    similarity ranking happened to reach it.
    """
    if not isinstance(active_state, dict):
        return {}
    drift = False
    # Signal 1: same goal held too long.
    if active_state.get("goal_held"):
        drift = True
    # Signal 2: a project has gone adrift.
    for p in (active_state.get("projects") or []):
        if isinstance(p, dict) and p.get("adrift"):
            drift = True
            break
    # Signal 3: mood sign-flip from baseline.
    mood = str(active_state.get("mood") or "").strip().casefold()
    if mood and not drift:
        # The baseline is "neutral" unless the character's stored affect
        # says otherwise. A sign-flip is when a clearly positive mood gives
        # way to a clearly negative one or vice versa, compared to what the
        # character's affect surface has been tracking. We use the mood label
        # vocabulary the engine already maintains.
        _negative = any(w in mood for w in (
            "afraid", "anxious", "angry", "ashamed", "despair", "disgust",
            "fear", "grief", "guilt", "horror", "rage", "sad", "shame",
            "terror", "worried", "dread", "misery", "anguish", "desolate",
        ))
        _positive = any(w in mood for w in (
            "calm", "content", "delighted", "ecstatic", "elated", "excited",
            "glad", "happy", "joy", "love", "peaceful", "pleased", "proud",
            "relieved", "satisfied", "serene", "triumphant", "warm",
        ))
        # Only a clear signal counts: a mood that is clearly one or the other,
        # and the character's active_state also carries valence from resolved
        # affect. We check the valence sign flip against the stored baseline.
        if _negative or _positive:
            surface = (active_state.get("affect") or {}).get("surface") or {}
            valence = float(surface.get("valence") or 0.0)
            baseline = (active_state.get("affect") or {}).get("baseline") or {}
            base_v = float(baseline.get("valence") or 0.0)
            # A sign flip: current and baseline are on opposite sides of zero,
            # and the current is not near zero (which is neutral, not a flip).
            if abs(valence) > 0.15 and (valence * base_v) < 0:
                drift = True
    if not drift:
        return {}
    # Fetch the earliest first-hand summary window.
    rows = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
             "AND scope=? AND end_turn_idx < ? "
             "ORDER BY end_turn_idx ASC, id ASC LIMIT 1",
             (chat_id, char_id, SUMMARY_SCOPE_FIRSTHAND,
              int(current_turn_idx)))
    if not rows:
        return {}
    r = rows[0]
    if not (r["summary"] or "").strip():
        return {}
    # Do not duplicate what earlier_in_my_life already carries.
    if (r["end_turn_idx"] or 0) in earlier_ids:
        return {}
    return {"where_i_came_from": {
        "what_i_lived_through_then": r["summary"] or "",
        "summary_id": _summary_id(r["scope"], r["end_turn_idx"]),
        "temporal_status": "remembered_past",
        "memory_form": "summary",
        "epistemic_origin": summary_context_label(r["scope"]),
        "when": _beats_ago_span(current_turn_idx, r["start_turn_idx"],
                                r["end_turn_idx"]),
    }}


def build_character_memory_context(chat_id, char_id, current_turn_idx, current_view, active_state, *,
                                   recent_turns=4, recall_limit=_RECALL_LIMIT, here=None,
                                   in_sight=None, absorption=0.0,
                                   ponder_query="", ponder_why="",
                                   resurfaced_subject=""):
    active_state = active_state or {}
    # Legacy banks predate event_key. Repair only the active mind's missing
    # handles before any row is projected, so every delivered citation is
    # stable across checkpoint restore and portable archive import.
    backfill_missing_memory_event_keys(chat_id, char_id)
    # Sensory absorption narrows deliberative recall while preserving a small
    # automatic-recognition lane.  A body monopolising attention should reduce
    # how many old chapters can be worked through, not erase a salient face,
    # warning, or promise already associated with the present cue.
    absorption = _clamp(absorption)
    if absorption >= 0.7:
        recent_limit, recall_limit, summary_limit = 4, min(recall_limit, 4), 0
    elif absorption >= 0.35:
        recent_limit, recall_limit, summary_limit = 8, min(recall_limit, 8), 1
    else:
        recent_limit, summary_limit = 12, _SUMMARY_RECALL_LIMIT
    recent = recent_memory_buffer(
        chat_id, char_id, current_turn_idx, turns=recent_turns,
        limit=recent_limit)
    recent_ids = {m["id"] for m in recent}
    summary = get_memory_summary(
        chat_id, char_id, before_turn_idx=current_turn_idx)
    # P8: the other two epistemic classes travel as their own labelled fields
    # rather than being melted into the first-hand paragraph. A character must
    # be able to tell what they saw from what they were told from what they
    # worked out -- collapsing them is the same layer-collapse the engine
    # polices between minds, happening inside one.
    provenance_summaries = {}
    summary_citations = {}
    for scope, _field, label in _SUMMARY_SCOPES:
        if scope == SUMMARY_SCOPE_FIRSTHAND:
            continue
        scoped_summary = get_memory_summary(
            chat_id, char_id, scope, before_turn_idx=current_turn_idx)
        text = str(scoped_summary.get("summary") or "").strip()
        if text:
            provenance_summaries[label] = text
            summary_citations[label] = {
                "summary_id": _summary_id(
                    scope, scoped_summary.get("end_turn_idx")),
                "temporal_status": "remembered_past",
                "when": _beats_ago_span(
                    current_turn_idx, scoped_summary.get("start_turn_idx"),
                    scoped_summary.get("end_turn_idx")),
                "epistemic_origin": label,
                "memory_form": "summary",
            }
    # The beat is the query; what the character BRINGS to it travels beside it
    # as aspects, each with its own ranking. Concatenated, they did nothing:
    # the view runs a median ~1,015 characters and a mood fragment 10-60, so
    # the combined vector sat at cosine 0.994 to the view alone and the mood
    # reached recall only through stray shared n-grams. See search_memories.
    query_text = str(current_view or "").strip()
    aspects = [
        ("what you are trying to do", str(active_state.get("goal") or "")),
        ("how you are feeling", str(active_state.get("mood") or "")),
        ("what is still unsettled",
         " ".join(summary.get("unresolved_threads") or [])),
    ]
    if not query_text:
        # No perception this beat (a character gated out of the scene): fall
        # back to the aspects as the query rather than retrieving on "".
        query_text = " ".join(t for _l, t in aspects if t)
    # current_turn_idx is required here (recent_memory_buffer arithmetic above
    # would already fail on None), so search_memories' F1 turn cutoff always
    # fires on this path -- the character context can never see turn N's own
    # committed memories while deciding turn N, reroll or not.
    # One embedding for everything ranked from this beat. search_memories has
    # always batched the query with its aspects; the summary windows rank
    # against the same query vector, so sharing the batch is what keeps the
    # window layer free rather than a second round trip per character per beat.
    _aspects = [(str(lbl), str(txt).strip()) for lbl, txt in aspects
                if str(txt or "").strip()]
    embedded = embed_texts_meta([query_text or "memory"]
                                + [txt for _lbl, txt in _aspects])
    recalled = search_memories(chat_id, char_id, query_text, k=recall_limit,
                               include_archived=True, current_turn_idx=current_turn_idx,
                               chronological=True, here=here, in_sight=in_sight,
                               aspects=aspects, embedded=embedded,
                               record_access=True)
    # NO ABSTENTION SIGNAL IS COMPUTED HERE ANY MORE, and the reason is worth
    # the paragraph because the thing that was here looked like it worked.
    #
    # `recall_confidence` is an NQC/WIG-shape z-score against the bank's own
    # score distribution, and it annotated this payload with
    # `nothing_comes_back_clearly`. Measured against 470 positive and 30
    # negative LongMemEval probes -- negatives whose answers are absent by
    # construction -- it fires 0 of 30 times, and recalibrating cannot fix it:
    # positives climb 1.9x across a bank-size sweep while negatives climb
    # 2.2x, so the gap holds at about one sigma at every scale and never
    # widens. A query whose answer is absent still retrieves topically related
    # rows and still produces a peaked distribution: presence and absence have
    # the SAME SHAPE, and a statistic over scores cannot read content
    # (UNBUILT 1.76).
    #
    # The replacement reads the rows, and lives in `agents/character.py`
    # (`_attach_recall_review`) rather than here -- it costs a model call, and
    # the other caller of this function is an author-facing preview route that
    # must not pay for one. The function survives for the probe harness, which
    # is the only reader entitled to a number it must not trust. Removing the
    # call also removes a second full bank scan per character per beat, which
    # is most of what the review costs back.
    recalled = [m for m in recalled if m["id"] not in recent_ids]
    if len(recalled) > recall_limit:
        recalled = sorted(
            sorted(recalled, key=lambda m: float(m.get("score") or 0.0),
                   reverse=True)[:recall_limit],
            key=lambda m: (m.get("turn_idx") is None,
                           m.get("turn_idx") if m.get("turn_idx") is not None
                           else 10**12, m.get("id") or 0))
    # A character may deliberately set ONE query on the previous character
    # turn. This is an additive, explicitly-labelled retrieval lane: normal
    # cue/mood/goal recall above remains untouched. It costs an embedding call
    # only when a ponder is actually pending, which should be exceptional.
    ponder_query = " ".join(str(ponder_query or "").split())[:240]
    ponder_why = " ".join(str(ponder_why or "").split())[:240]
    pondered = []
    if ponder_query:
        # The SAME budget passive recall just used, which is `recall_limit`
        # after absorption has narrowed it -- not a fixed 4.
        #
        # A fixed 4 meant a deliberate act of remembering was always served as
        # though the mind were maximally absorbed, which is the one state it
        # is not in: absorption narrows passive recall precisely because
        # attention is elsewhere, and a ponder is attention deliberately
        # placed. Scaling with absorption keeps that meaning in both
        # directions -- an absorbed mind's ponder is still small.
        #
        # Measured on 470 independent questions (LongMemEval, ranks from the
        # k=16 payload): k=4 answers 287, k=16 answers 396. The cap was
        # costing 28% of answerable questions, and the loss falls hardest on
        # exactly the classes a ponder tends to be -- preferences 47% of
        # answerable, multi-session 34%, temporal 32% -- while questions whose
        # evidence sits in a single row barely notice it. The curve has no
        # knee at 4; it is simply the bottom of it.
        #
        # The payload argument the old comment made is real and does not bite
        # here: measured on the live corpus, a ponder fires on roughly 1 turn
        # in 332, so this spends about a thousand extra tokens on 0.3% of
        # beats, on the lane where a character has decided it needs to
        # remember something.
        ponder_k = max(4, int(recall_limit))
        pondered = search_memories(
            chat_id, char_id, ponder_query, k=ponder_k, include_archived=True,
            current_turn_idx=current_turn_idx, chronological=True,
            here=here, in_sight=in_sight, record_access=True)
        # Chronological-neighbour expansion may return k+2; trim to the budget.
        if len(pondered) > ponder_k:
            pondered = sorted(
                sorted(pondered, key=lambda m: float(m.get("score") or 0.0),
                       reverse=True)[:ponder_k],
                key=lambda m: (m.get("turn_idx") is None,
                               m.get("turn_idx")
                               if m.get("turn_idx") is not None else 10**12,
                               m.get("id") or 0))
    # The layer between the summary and the raw rows: which EARLIER stretch of
    # this life the present beat is about.
    #
    # `summary` above is only the latest window, and a window is in practice
    # about its own turns -- the consolidator is told to merge the previous
    # summary in, but it is told just as firmly to shed low-salience detail, and
    # shedding wins. Measured across the six live window pairs, successive
    # windows share 3-16% of their text and sit at cosine 0.57-0.88; the
    # Doctor's second window recaps the first in a single clause and is
    # otherwise entirely about its own ten turns.
    #
    # So the singleton design was not holding a life story, it was holding the
    # most recent chapter of one, and overwriting the rest. 53 of the 67 live
    # banks have no summary at all over their opening turns. Windows stopped the
    # loss; this is what reads what they kept.
    #
    # First-hand scope only. Hearsay and surmise have windows too, and folding
    # them in here would put three provenances in one field -- the same collapse
    # `provenance_summaries` exists to prevent.
    earlier = (search_memory_summaries(
        chat_id, char_id, query_text, k=summary_limit,
        scope=SUMMARY_SCOPE_FIRSTHAND, before_turn_idx=current_turn_idx,
        exclude_latest=True, embedded=embedded) if summary_limit else [])
    # Chronological, oldest first: these are stretches of a life, and rank order
    # would present it out of sequence. Ranking has already done its work by
    # choosing WHICH ones. Absent rather than empty when there are none, like
    # the provenance summaries below -- an empty key still spends attention.
    earlier_payload = {"earlier_in_my_life": [
        {"what_i_lived_through_then": w.get("summary") or "",
         "summary_id": _summary_id(
             w.get("scope") or SUMMARY_SCOPE_FIRSTHAND,
             w.get("end_turn_idx")),
         "temporal_status": "remembered_past",
         "memory_form": "summary",
         "epistemic_origin": summary_context_label(
             w.get("scope") or SUMMARY_SCOPE_FIRSTHAND),
         "when": _beats_ago_span(current_turn_idx, w.get("start_turn_idx"),
                                 w.get("end_turn_idx"))}
        for w in sorted(earlier, key=lambda w: (w.get("end_turn_idx") or 0))
    ]} if earlier else {}
    # Origin-era retrieval on drift (UNBUILT §1.21).
    #
    # A character's foundational era is frequently DISSIMILAR to whatever is
    # happening now, which is exactly when it should still be present -- a
    # character who has lost the thread of why they set out needs to remember
    # the beginning, and similarity-based top-k drops it in the beats where it
    # matters most. An origin is not a similarity match.
    #
    # Rather than always including the origin (which costs a slot every beat
    # for something usually irrelevant) or waiting for an absolute floor the
    # compressed cosine band cannot provide, surface the origin window when a
    # drift signal fires: the same goal held for 12+ beats, a project gone
    # adrift for 8+ beats, or a mood sign-flip from the character's baseline.
    # These are exactly the moments a person reaches for who they were before
    # the current stretch swallowed them.
    origin_payload = _origin_on_drift(
        chat_id, char_id, current_turn_idx, active_state,
        earlier_ids={w.get("end_turn_idx") for w in earlier})
    if str(summary.get("summary") or "").strip():
        summary_citations["autobiographical_summary"] = {
            "summary_id": _summary_id(
                SUMMARY_SCOPE_FIRSTHAND, summary.get("end_turn_idx")),
            "temporal_status": "remembered_past",
            "when": _beats_ago_span(
                current_turn_idx, summary.get("start_turn_idx"),
                summary.get("end_turn_idx")),
            "epistemic_origin": summary_context_label(
                SUMMARY_SCOPE_FIRSTHAND),
            "memory_form": "summary",
        }
    row_ids = {
        str(m.get("id")): str(m.get("event_key") or "")
        for m in (*recent, *recalled, *pondered)
        if m.get("id") is not None and str(m.get("event_key") or "")
    }
    normal_refs = {str(m.get("event_key") or "")
                   for m in (*recent, *recalled)}
    ponder_refs = [str(m.get("event_key") or "") for m in pondered
                   if str(m.get("event_key") or "")]
    recent_projected = [_with_reading(m, current_turn_idx) for m in recent]
    # A recent-life stream must be one chronological row per experienced beat,
    # not a turn-sized blob of episode + durable quote + self duplicate +
    # conclusion.  Keep the epistemic side records available, but in their own
    # lanes so neither chronology nor provenance has to be reconstructed by the
    # character model.
    recent_experienced = [
        m for m in recent_projected
        if m.get("epistemic_origin") == "what_i_experienced"]
    recent_received = [
        m for m in recent_projected
        if m.get("epistemic_origin") == "what_i_was_told"]
    recent_conclusions = [
        m for m in recent_projected
        if m.get("epistemic_origin") == "what_i_concluded"]
    recalled_projected = [
        _with_reading(m, current_turn_idx) for m in recalled]
    for item in (*recent_projected, *recalled_projected):
        if str(item.get("memory_ref") or "") in ponder_refs:
            item["retrieval_origin"] = [
                "normal_recall", "deliberate_ponder"]
            # The reason travels WITH the label, on these rows only.
            #
            # `deliberate_ponder` says "you went looking for this", and these
            # are the ponder results that came back through ordinary recall
            # too -- so they sit in `recalled_old_memories`, structurally
            # apart from the `deliberate_recall` lane where the reason is
            # stated once. Without this a mind reads a row stamped "you
            # deliberately went looking" with the motive an indirection away
            # through `result_refs`, which is the same complaint the
            # `memory_ref` per-row constant was RESTORED to answer: the label
            # marks the lane at the point of use, and a discrimination the
            # engine cannot re-impose downstream is worth its bytes.
            #
            # Only here. Rows inside the lane already have the reason at their
            # head, and repeating it there would be paying for it twice.
            if ponder_why:
                item["why_i_went_looking"] = ponder_why
    ponder_additional = []
    for mem in pondered:
        ref = str(mem.get("event_key") or "")
        if ref in normal_refs:
            continue
        item = _with_reading(mem, current_turn_idx)
        item["retrieval_origin"] = ["deliberate_ponder"]
        ponder_additional.append(item)
    ponder_payload = ({"deliberate_recall": {
        "query_i_chose_last_turn": ponder_query,
        # Absent rather than empty when a legacy state blob has no reason
        # stored, like every other optional key here.
        **({"why_i_chose_it": ponder_why} if ponder_why else {}),
        "temporal_status": "remembered_past",
        "retrieval_origin": "deliberate_ponder",
        "result_refs": ponder_refs,
        "additional_episodes": ponder_additional,
        # Results do not force another query, but a genuinely new uncertainty
        # may be pondered immediately; optionality lives in the explicit act.
        "may_set_another_ponder_this_turn": True,
    }} if ponder_query else {})

    # A subject that came back on its own.
    #
    # Seeded by the out-of-band pass that reads what this mind just recorded
    # against what it already held (`schedule_memory_tension_pass`). That pass
    # finds contradictions; this lane deliberately does NOT say so. It runs
    # the subject as a query and hands over whatever returns, because the
    # measurement is unambiguous about which of those two things works: told
    # that two memories disagree, minds disputed 13/16; handed the rows with
    # nothing said, 16/16. And on an unaimed beat ordinary recall delivers
    # both halves 0 times in 18, so the retrieval is the entire mechanism.
    #
    # Labelled as unbidden rather than chosen, on the same grounds the engine
    # refuses to speak for a silent player: this mind did not ask for it, and
    # `query_i_chose_last_turn` would be the engine telling a character it
    # decided something it did not.
    resurfaced_subject = " ".join(str(resurfaced_subject or "").split())[:240]
    resurfaced_payload = {}
    if resurfaced_subject:
        already = normal_refs | set(ponder_refs)
        back = [m for m in search_memories(
            chat_id, char_id, resurfaced_subject, k=max(4, int(recall_limit)),
            include_archived=True, current_turn_idx=current_turn_idx,
            chronological=True, here=here, in_sight=in_sight,
            record_access=True)
            if str(m.get("event_key") or "") not in already]
        if back:
            resurfaced_payload = {"resurfaced_without_asking": {
                "subject": resurfaced_subject,
                "temporal_status": "remembered_past",
                "retrieval_origin": "unbidden_subject",
                "episodes": [_with_reading(m, current_turn_idx)
                             for m in back[:max(4, int(recall_limit))]],
            }}
    score_rows = {}
    for mem in (*recalled, *pondered):
        ref = str(mem.get("event_key") or "")
        if ref:
            score_rows[ref] = max(
                score_rows.get(ref, float("-inf")),
                float(mem.get("score") or 0.0))
    return {
        # Host-only registry. character.py removes it before serialization.
        "_internal": {
            "row_ids": row_ids,
            "retrieved_ids": [
                m.get("id") for m in (*recent, *recalled, *pondered)
                              if m.get("id") is not None],
            "scores": score_rows,
        },
        "unresolved_from_past": {
            "temporal_status": "remembered_past",
            "items": list(dict.fromkeys([
                *[str(item) for item in (active_state.get("active_concerns") or [])
                  if str(item).strip()],
                *[str(item) for item in (summary.get("unresolved_threads") or [])
                  if str(item).strip()],
            ]))[:6],
        },
        "recent_episodes": recent_experienced,
        **({"recent_received_information": recent_received}
           if recent_received else {}),
        **({"recent_conclusions": recent_conclusions}
           if recent_conclusions else {}),
        "recalled_old_memories": recalled_projected,
        # First-hand only. What reached this character through someone else's
        # account, and what they worked out for themselves, are carried
        # separately below and must not be folded in here.
        "autobiographical_summary": summary.get("summary") or "",
        "summary_key_phrases": summary.get("key_phrases") or [],
        "unresolved_threads": summary.get("unresolved_threads") or [],
        **({"summary_citations": summary_citations}
           if summary_citations else {}),
        **earlier_payload,
        **origin_payload,
        **ponder_payload,
        **resurfaced_payload,
        **provenance_summaries,
    }

# Views that record no perceptible event. Matched on the engine's OWN
# placeholders rather than on prose: `agents/perception.py` writes "an
# unspecified area" when it cannot name a room, and `agents/character.py`
# falls back to "You register nothing new this beat." Both mean the same
# thing -- this mind perceived nothing this beat -- and neither is an episode.
#
# Lives here rather than in `commit.py` (which owns the write-side rule and
# imports it back) because consolidation needs the same answer. Banks written
# before the write-side guard still carry these rows -- 369 across the live
# corpus -- and a consolidator handed ten of them summarises an absence into
# prose, which is then handed to a character as something they lived through.
