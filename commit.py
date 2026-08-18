"""Atomic world-state commit with mutation validation."""

import contextvars
import copy
import json, re, threading, time, weakref
from concurrent.futures import ThreadPoolExecutor
from db import q, qi, qtx, transaction, wget, wset, get_setting
from memory import (
    add_memories_batch, prepare_memories_batch, delete_turn_memories, search_lore, add_lore,
    record_dispute, raise_importance,
    update_lore, LORE_CATEGORIES, LOREBOOK_TYPES,
    chat_lorebook_ids, chat_lorebook_weights, lorebook_manifest, dump_chat_memories,
    ensure_chat_canon_book,
    add_lorebook_link, lorebook_descendants,
    restore_chat_memories, dump_lorebook, restore_lorebook,
    knowledge_for_character, get_relationships,
    save_relationships, update_relationships_from_inference,
    apply_relationship_updates, maybe_consolidate_character_memory,
    reconcile_inference_confidence, _is_empty_view,
)
from providers import embed_texts
from prompts import get_prompt
import affect
import psychology_runtime
from character_schema import (_UNSPACED_SCRIPT, character_name,
                              fold_identity_key,
                              character_name_from_text,
                              new_uid, character_psychology,
                              character_interoception,
                              character_initial_outfit,
                              character_initial_active_state, effective_drive,
                              character_standing_intentions,
                              character_projects,
                              normalize_character_data, persona_name,
                              character_appearance as _char_appearance)
from frames import is_recognized_in_frame
import attire as attire_model
from scene import (set_char_state, set_char_status, seed_initial_attire,
                   get_scene, SINGULAR_BODY_CONDITIONS,
)
from mechanics import mechanics_sweep, news_latency_seconds, stable_event_key
from weather import advance_weather, normalize_weather
from spatial import (merge_scene_with_diff, _merge_entity, room_of,
                     normalize_room_id, spatial_rel, hear_level,
                     normalize_barrier, normalize_bearing, opposite_bearing,
                     passable_path, rooms_adjacent, visible_adjacent_rooms,
                     guessed_room_sizes, _is_body_entity)
from theory_of_mind import (apply_mind_model_updates, rekey_place_claims,
                            select_active_hypotheses, sheet_capacity)
from survival import vitals_of
from comfort import comfort_level
from paradox import check_and_apply_paradox
from spatial_frames import detect_and_reconcile as detect_and_reconcile_spatial
from spatial_frames import (infer_companion_carry, infer_vehicle_zones,
                            infer_came_from, infer_focus, infer_facing,
                            infer_threshold_crossings)

# ---------------------------------------------------------------------------
# Split facade (see docs/experiments/AUDIT_COMMIT.md). commit.py's domain
# code lives in the commit_* modules imported below; every moved name --
# private names included -- is re-exported here so `from commit import X`,
# `commit.X` and `commit.__dict__[...]` keep working for every caller and
# test.
#
# The import block ABOVE is the pre-split block, kept byte-for-byte on
# purpose even though the split leaves many of its names unused in this
# file: `_is_empty_view` is a contract name reachable only through it,
# tests monkeypatch `commit.<imported-name>` (prepare_memories_batch,
# get_scene, persona_name, add_memories_batch,
# maybe_consolidate_character_memory, affect, ...), and callers import
# several of those names from `commit`. Pruning "unused" imports here is a
# forbidden cleanup -- it breaks that contract silently.
from commit_common import (_keys_str, _stable_event_key, _clamp,
    _normalize_character_output, _player_name_or_none, _monotonic_elapsed,
    _ADDRESS_ARTICLES, _form_in, _address_forms, _names_heard_in,
    _known_name_roster, _registered_name_roster, _resolve_roster_name,
    _GENERIC_ID_TOKENS, _canonical_token_key, _entity_alias_map,
    _canonical_anchor, _room_of, _normalized_fact)
from commit_place_graph import (VISITED_ROOMS_CAP, ROUTE_CREDIT_WINDOW,
    ROUTE_CREDIT_CAP, PLACE_GRAPH_NODE_CAP, update_place_graph,
    record_spatial_experience)
from commit_destruction import (_destruction_book, _chat_book_graph,
    _book_distances, _audience_book_id, _destruction_cascade,
    _prepare_destruction, _finalize_destruction_news, _apply_destruction)
from commit_room_registry import (_anchored_book_ids, _room_display_slug,
    _registry_alias_index, _apply_room_renames, dedup_minted_rooms,
    _prepare_room_registry, _apply_room_registry,
    sync_room_registry_with_scene, _refresh_relocated_location,
    prune_dangling_exits)
from commit_attire import (_NON_ATTIRE_TERMS, sanitize_attire_items,
    _heal_attire_identity_keys, _beat_voices, _NOTE_NAME_HEAD,
    _garment_named_in, interpret_attire_notes, _fold_duplicate_shed_garments,
    _fold_worn_garment_entities, _set_worn_garment_condition,
    _is_clothing_entity, _adopt_shed_record, _stamp_shed, _mint_shed_garments,
    apply_attire_diff)
from commit_entities import (_is_gated_awareness, _subjects_that_moved,
    _subjects_targeted_by_an_action, _supersede_disguises, _inherit_known_to,
    commit_world_entities)
from commit_ledgers import (OBLIGATION_OVERDUE_AGE, OBLIGATION_CAP,
    pending_obligation_view, _find_obligation, commit_obligations,
    WORLD_PRESSURE_STALL_AGE, WORLD_PRESSURE_CAP, world_pressure_view,
    _find_pressure, commit_world_pressure)
from commit_mapping import (normalize_offscreen_events,
    _apply_mapping_book_ops, prepare_mapping_commit, commit_mapping, _lore_for,
    _fact_is_covered, _generate_fallback_ops)
from commit_background import (BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
    BACKGROUND_PROMOTION_MENTION_THRESHOLD, promotion_thresholds,
    _BACKGROUND_NAME_TITLE_WORDS, _NAME_TITLE_PREFIXES, strip_name_titles,
    name_in_roster, _PRESENCE_ARTICLES, _presence_identity,
    _bodies_answering_to, _canonical_presence_name, _presence_scene_entity,
    _presence_speech_verdict, _merge_presence_record, _resolve_presence_name,
    _fold_duplicate_presences, _background_name_mentioned,
    _character_address_of, _valid_pending_reply, _background_fired_reactions,
    _INERT_ENTITY_KINDS, _is_inert_presence_candidate,
    prepare_background_claims, track_background_presences,
    BACKGROUND_RECENT_TAIL, _persist_blurbs, _append_manager_conduct,
    _background_fired_reactions_any, _flow_addressed_refs,
    _presence_in_addressed_refs, _at_post_within_earshot,
    pick_background_reactor, pick_background_reactors,
    promotable_background_presences, _refuse_name_collision,
    promote_background_character, AUTO_PROMOTE_DIALOGUE_THRESHOLD,
    _promote_after_addressed, _auto_promote_enabled,
    auto_promote_background_characters)
from commit_scene_state import (_anchor_current_room, sync_anchored_books,
    _guard_occupied_mover_removal, _advance_ground, prepare_scene_commit,
    commit_scene, _record_subject_last_seen)
from commit_mechanics import (commit_transit_sweep, commit_world_event_spine,
    commit_information_carriers, commit_cast_changes)
# ---- end split facade ----

_COMMIT_LOCKS = weakref.WeakValueDictionary()
_COMMIT_LOCKS_GUARD = threading.Lock()

def _commit_lock(turn_id):
    with _COMMIT_LOCKS_GUARD:
        return _COMMIT_LOCKS.setdefault(turn_id, threading.Lock())

# ---- Memory commit ----

# How many of a character's most recent physical tells (manifest cues) are
# kept on cstate as the anti-repetition ledger fed back into the character
# payload (see agents/character.py's TELL VARIETY block).
RECENT_TELLS_CAP = 6

def _durable_dialogue_category(text):
    """Category for a quote worth keeping verbatim, or None.

    Each marker must BEGIN at a word boundary. A marker is a spoken word, and
    a word does not start in the middle of another one: bare substring
    matching made "compromised" a promise, and the live corpus proves it --
    of its 5 promise-category rows, 3 were the word "compromised" (chat 6's
    "Section C and D compromised", twice, and chat 58's "TARGETING
    COMPROMISED") against 2 genuine promises. The boundary is only required
    at the start, so inflections still match ("I promised", "she promises");
    tools/remember_lines.py inlines this rule and
    tests/test_remember_lines_telemetry.py holds the two in sync."""
    lowered = (text or "").lower()
    def _spoken(marker):
        return re.search(r"\b" + re.escape(marker), lowered) is not None
    if any(_spoken(w) for w in ("promise", "i swear", "i vow", "you have my word",
                                "i'll return", "i will return")):
        return "promise"
    if any(_spoken(w) for w in ("my name is", "call me", "i confess", "the truth is",
                                "i killed", "i betrayed", "i love you", "i hate you",
                                "i'll kill", "i will kill")):
        return "dialogue"
    return None

def _cited_memory_ids(own_result):
    """Memory ids this mind used as EVIDENCE for a belief it formed this beat.

    Consequence, not popularity. Retrieval on its own never moves importance:
    a memory that gets recalled would then rank higher and get recalled more,
    which is a feedback loop wearing the word. Even citation is downstream of
    retrieval, so the loop is closed structurally instead of hoped away --
    `raise_importance` is called with `only_unrevised=True`, so a given memory
    can be lifted by citation exactly once, ever. The signal is "this turned
    out to be load-bearing at least once", which is boolean by nature.

    Bare `observations_used` deliberately does not count. Citing a memory while
    describing the beat is not the same as building a belief on it, and the
    weaker signal is the one that fires on almost every turn.

    Returns `event_key`s, because that is what a character actually cites. The
    first version of this required a numeric memory ROW id and was therefore
    dead on arrival -- across a 10-turn live run it matched nothing, while the
    handles the characters really wrote were `current`, `current:39:4`,
    `turn:2:character:39:0:action` and `event:<hash>`. The last of those IS the
    memory's `event_key` (`_stable_event_key`), and all five distinct ones
    emitted in that run resolved to a real row. The format was there the whole
    time; the reader was looking for one nothing produces.

    THE SAME MISTAKE, ONE LAYER UP. Having fixed the id format, this still read
    a single field, and measured over the beats that could have supplied any of
    them (`tools/fire_rates.py`):

        mind_model_updates evidence citing a stored memory     6 of 83
        belief_updates evidence citing a stored memory         1 of 83
        memory_effects, disposition `integrated`              74 of 83

    Importance has been revised on 9 of 6,460 memories, and that is why: the
    one signal being read is the rarest thing a character emits, while the
    field that says exactly what this function is looking for -- the character
    stating that a recalled memory changed their recognition, appraisal, choice
    or speech -- fires on 89% of eligible beats and was never consulted.

    `memory_effects` is a STRONGER consequence signal than citation, not a
    weaker one. Its prompt says in as many words: do not emit one merely
    because a row was present. `resisted` and `dismissed` do not count -- a
    memory the character pushed away did influence the beat, but recording that
    as "turned out to matter" would make importance a measure of salience-at-
    recall rather than of consequence. `only_unrevised=True` still holds the
    ceiling at one lift per memory for its whole life, so widening the inputs
    widens the population that can be lifted once, never the amount.

    `belief_updates` is included because the docstring's first line has always
    claimed it: a belief formed on a memory is the paradigm case. It contributes
    almost nothing at present, which is a fact about how models cite, not a
    reason to keep reading the wrong field.
    """
    if not isinstance(own_result, dict):
        return []
    out = set()
    for field in ("mind_model_updates", "belief_updates"):
        for update in own_result.get(field) or []:
            if not isinstance(update, dict):
                continue
            for ref in update.get("evidence") or []:
                if not isinstance(ref, dict):
                    continue
                raw = str(ref.get("event_id") or "").strip()
                # "current" and the turn:/character: handles name this beat or
                # an act within it, not a stored memory.
                if raw.startswith("event:"):
                    out.add(raw)
    for effect in own_result.get("memory_effects") or []:
        if not isinstance(effect, dict):
            continue
        if str(effect.get("disposition") or "").strip() != "integrated":
            continue
        raw = str(effect.get("memory_ref") or "").strip()
        if raw.startswith("event:"):
            out.add(raw)
    return sorted(out)


def _marked_for_memory(own_result, qbody):
    """Did this character ask to keep this line (CharacterOutput.remember_lines)?

    Matched on the quote body, loosely in both directions: a model asked to
    echo a quote will trim or extend it by a word, and rejecting the mark over
    that would make the feature depend on transcription rather than intent.
    Loose matching is safe HERE and would not be elsewhere -- the caller has
    already proved this quote was said this beat and reached this observer, so
    the only thing being decided is whether a line the character definitely
    heard is also one they keep.
    """
    body = " ".join(str(qbody or "").split()).casefold()
    if not body or not isinstance(own_result, dict):
        return None
    for mark in own_result.get("remember_lines") or []:
        if not isinstance(mark, dict):
            continue
        want = " ".join(str(mark.get("quote") or "").split()).casefold()
        want = _quote_body(want)
        if not want:
            continue
        if want == body or want in body or body in want:
            return mark
    return None


def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")


def _is_player(speaker, chat):
    from agents import is_player_speaker
    return is_player_speaker(speaker, chat)

def _salience_of(text):
    s = 0.45 + min(len(text or ""), 400) / 1600.0
    for w in ("attack", "blood", "secret", "betray", "kiss", "dead",
              "weapon", "threat", "love", "steal", "scream", "knife",
              "confess", "liar", "promise"):
        if w in (text or "").lower():
            s += 0.08
    return round(min(s, 0.95), 3)


def _own_sequence_memory(seq):
    """Render a character's own conduct as grammatical, chronological first
    person: ``I said 'X.' Then I tried to Y.``

    This is the ONLY durable record of what a mind itself said and did. The
    witnessed episode cannot carry it: deterministic perception structurally
    excludes a mind's own speech and acts from its own view (`speaker == name`
    / `actor == name` skips in `agents/perception.py`, and
    `_strip_self_narration` above them), which is the firewall working, not a
    gap in it. So the wording here is decision-framed on purpose -- "I said",
    "I tried to" -- an attempt beside the perceived outcome, never a second
    resolved event competing with it. The old ``I chose to attempted '...'``
    construction is what actually replayed an act as though it were a second
    happening; preserve order, and never cut a gist midway through an act.
    """
    clauses = []
    for event in (seq or []):
        if not isinstance(event, dict):
            continue
        if event.get("type") == "speech" and str(event.get("text") or "").strip():
            spoken = str(event["text"]).strip()
            clauses.append(
                f"I said {spoken!r}" + ("" if spoken[-1] in ".!?" else "."))
        elif event.get("type") == "action" and str(event.get("attempt") or "").strip():
            clauses.append(f"I tried to {str(event['attempt']).strip().rstrip('.')}.")
    if not clauses:
        return "", ""
    content = " Then ".join(clauses)
    gist_parts = []
    for clause in clauses:
        candidate = " Then ".join(gist_parts + [clause])
        if len(candidate) > 240:
            break
        gist_parts.append(clause)
    gist = " Then ".join(gist_parts) if gist_parts else clauses[0][:239].rstrip() + "…"
    return content, gist

def prepare_memory_commit(ctx, *, scene=None):
    """Build and embed all per-character memory mutations without writes."""
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    # Build a fresh list -- never mutate res["dialogue_log"], since the
    # director_resolve step/variant was already persisted before
    # background_react ran (see agents/perception.py's merge comment). The
    # deterministic backstop line is merged only for rendering there; fold
    # it into the persisted event record here too, so hearers mint dialogue
    # memories of it and it reaches _promotion_evidence.
    dlog = list(res.get("dialogue_log") or [])
    for _r in _background_fired_reactions(ctx.get("background_react")):
        dlog.append({**_r["dialogue_log_entry"], "source": "background_react"})
    views = (
        (ctx.perception_outcome or {}).get("views")
        or (ctx.perception_establish or {}).get("views")
        or {}
    )
    # IR-minted episodes (deterministic composer, PERCEPTION_NO_LLM): when
    # perception composed the views, it also minted each character's episode
    # directly from the percept IR -- first person, event-bearing content
    # first, typed entities -- instead of the second-person view prose. A
    # composed "" is a NON-EVENT (all standing state, nothing changed) and
    # mints nothing; absent keys fall back to the view exactly as before.
    _composed_episodes = (ctx.perception_outcome or {}).get("episodes")
    if not isinstance(_composed_episodes, dict):
        _composed_episodes = None
    _composed_episode_meta = (
        (ctx.perception_outcome or {}).get("episode_meta") or {}
        if _composed_episodes is not None else {}
    )
    est = ctx.director_establish
    sc = scene if scene is not None else (wget(cid, "scene", {}) or {})
    pending_memories = []
    state_updates = []
    # Names learned by hearing them said, accumulated per hearer and applied
    # by commit_memories inside the transaction -- this function runs BEFORE
    # the write lock and must not write. See _names_heard_in.
    _name_roster = _known_name_roster(chat, ctx.cast)
    _names_learned = {}
    relationship_ops = []
    belief_reconciles = []
    memory_disputes = []
    importance_bumps = []
    _clock = wget(
        cid, "simulation_clock",
        {"elapsed_seconds": 0.0, "display": "now"},
    ) or {}
    _time_diff = ((res.get("state_diff") or {}).get("time")
                  if isinstance(res.get("state_diff"), dict) else None)
    if isinstance(_time_diff, dict):
        # The same monotonic read as the scene commit's, from the same
        # helper. This site read the raw `end_seconds` for two releases
        # after the clock itself was guarded, so a backwards beat stamped
        # affect decay, strain windows and belief provenance with a clock
        # the scene commit had just refused to store.
        _clock_seconds, _ = _monotonic_elapsed(_clock, _time_diff)
    else:
        _clock_seconds = float(_clock.get("elapsed_seconds") or 0.0)

    # Loop-invariant inputs to the place-claim rekey below, hoisted: the scene
    # rooms, the cast roster, and the persona do not change while this loop
    # runs, but they were being rebuilt (a full room walk plus a name
    # resolution per cast member) inside EVERY iteration that carried
    # mind_model_updates -- O(cast^2) name derivations on a full table.
    from scene import persona_of as _persona_of
    _rekey_place_names = [
        str((room or {}).get("name") or rid)
        for rid, room in (sc.get("rooms") or {}).items()
    ]
    _rekey_protected = [character_name_from_text(_r["sheet"])
                        for _r in ctx.cast]
    _rekey_protected.append(persona_name(_persona_of(chat)))

    for char_row in ctx.cast:
        ccid = char_row["id"]
        sh = json.loads(char_row["sheet"])
        st = json.loads(char_row["cstate"] or "{}")
        v = views.get(str(ccid))
        episode_content = ""
        _episode_entities = []
        _episode_gist = ""
        # Side records (durable quotes) are emitted after the coherent episode
        # row so storage order mirrors their role: event first, annotations
        # second.  They remain separately retrievable by provenance.
        side_memories = []
        cname = character_name(sh)
        char_room = _room_of(sc, cname)
        room_data = (sc.get("rooms") or {}).get(char_room, {})
        room_name = room_data.get("name") or char_room or ""
        # BOTH LOOPS, MERGED. The interaction loop merges its rounds into
        # `ctx.character_results`; the reaction loop writes to
        # `ctx.reaction_results` and nothing here ever read it, so everything
        # a REACTING mind worked out was dropped -- silently, because the
        # appliers below were handed empty lists and had nothing to warn
        # about.
        #
        # Measured across the 82 stored reaction beats in the corpus: every
        # single one carried interior content that never committed -- 159
        # mind_model_updates, 93 relationship_updates, 20 belief_updates, 18
        # remember_lines, 12 association_updates, and the only three project
        # adoptions the engine has ever produced (chats 70/71/72, one beat
        # across three branches: the Doctor committing to reach a shrine).
        # A reaction is the beat with the most immediate pressure on a
        # character, and they were forming theories about people and marking
        # things worth remembering into nothing.
        #
        # MERGED rather than chosen between, because a character can both
        # react and act in one beat, and the same union `_merge_character_
        # results` already performs across micro-rounds is the right one
        # here: accumulating lists combine, latest scalar state wins.
        from agents.common import _merge_character_results
        own_result = _merge_character_results(
            ctx.reaction_results.get(ccid),
            ctx.character_results.get(ccid)) or {}
        own_result = _normalize_character_output(own_result)
        # Place claims are re-keyed onto their place ONCE, up here, before
        # ANYTHING reads mind_model_updates. The inference memory minted for a
        # claim (below) and the hypothesis it is merged under (further down,
        # via apply_mind_model_updates) must share one subject key: minting
        # from the raw updates while merging the rekeyed ones stamped the
        # memory's entities[0] with a subject that never exists in
        # mind_models, so reconcile_inference_confidence could never find the
        # live hypothesis and demoted the row as abandoned from the start.
        _mm_updates = own_result.get("mind_model_updates") or []
        if _mm_updates:
            _mm_updates = rekey_place_claims(
                _mm_updates, _rekey_place_names, protected=_rekey_protected)
        active_state = own_result.get("active_state") or {}
        mood = str(active_state.get("mood") or "")
        # The character's blended surface affect this beat carries the numeric
        # valence/arousal that go with the `mood` label; without this the
        # emotional_context text was stored but valence/arousal stayed at their
        # 0.0 default on every memory (the memory editor showed them as always
        # zero). Mirror the label onto the numeric axes for this beat's memories.
        # THE MOOD THIS MEMORY WAS FORMED IN -- the character's RESOLVED affect,
        # not the self-report they opened the beat with.
        #
        # `resolve_affect` is what turns a model's proposed mood into the one
        # the character actually holds: decayed toward baseline, moved by this
        # beat's appraisal, and cross-checked against the label. It runs at the
        # psychology commit, ~500 lines below this one, so a memory minted here
        # can never see it -- it took the raw proposal instead.
        #
        # Measured across the same characters: the raw self-report averages
        # +0.773 with 0% negative, while their resolved affect averages +0.467
        # with 22% negative. The two disagree by +0.31, and only one of them is
        # a mood. Stored memories inherited the saturated one: newer stories
        # sat at a median valence of +0.85 with 4 negatives in 3,162 rows,
        # which is not an emotional axis, it is a constant -- and it silently
        # disables everything downstream that reads affect.
        #
        # The stored value is last beat's resolution, i.e. the mood the
        # character carried INTO this event. That is what encoding-time affect
        # should be: how you felt while it was happening, before the beat's own
        # appraisal moved you. The self-report is kept as the fallback for a
        # character with no resolved affect yet (their first beat).
        _surface = (((st.get("active_state") or {}).get("affect") or {})
                    .get("surface") or {})
        if not _surface:
            _surface = (active_state.get("affect") or {}).get("surface") or {}
        try:
            _mem_valence = float(_surface.get("valence") or 0.0)
            _mem_arousal = float(_surface.get("arousal") or 0.0)
        except (TypeError, ValueError):
            _mem_valence, _mem_arousal = 0.0, 0.0
        # Fallback for legacy/no-psychology turns: after equals before.  The
        # resolved appraisal below replaces these when it exists.
        _encoding_valence, _encoding_arousal = _mem_valence, _mem_arousal
        # --- Unbidden-recall ledger: the character stage proposed this beat's
        # probe on its step output (deterministic trigger state, and whether a
        # contrasting memory was surfaced); commit is the only writer of the
        # durable ledger, exactly like recent_tells. Placed BEFORE any st
        # mutation below so the previous beat's goal is still readable for
        # the same-beat "did it help" check. Nothing here ever mints a memory
        # row: a surfaced memory is context handed to the character, and only
        # what the character then DOES (speech, mind-model claims) is
        # canonical.
        _probe = own_result.get("unbidden_probe")
        if isinstance(_probe, dict):
            _led = dict(st.get("unbidden") or {})
            _probe_ref = str(_probe.get("memory_ref") or "")
            _effectful = any(
                isinstance(e, dict)
                and str(e.get("memory_ref") or "") == _probe_ref
                and str(e.get("disposition") or "").casefold()
                    not in {"", "dismissed", "ignored", "none"}
                and bool(str(e.get("changed") or "").strip())
                for e in (own_result.get("memory_effects") or []))
            _goal_before = str(((st.get("active_state") or {}).get("goal"))
                               or "")
            # The RAW emitted goal was read here to ask "did the goal move off
            # its snapshot" -- the third reader of that field the 2026-08-11
            # audit missed. The template no longer asks for it, so derive the
            # same text the psychology commit below will keep (the enacted
            # want's), with the legacy field as fallback; both sides of the
            # comparison (this and the `pending` snapshot) go through the one
            # derivation, so "moved" keeps meaning what it meant.
            from agents.common import declared_goal as _declared_goal
            _goal_now = _declared_goal(own_result)
            _pending = (_led.get("pending")
                        if isinstance(_led.get("pending"), dict) else None)
            if _pending is not None and turn.idx > int(_pending.get("turn")
                                                       or -1):
                # The beat AFTER an injection: it helped if the stuckness
                # cleared or the goal moved off its snapshot.
                _helped = (not _probe.get("stuck")
                           or _goal_now != str(_pending.get("goal") or ""))
                _outs = [o for o in (_led.get("outcomes") or [])
                         if isinstance(o, dict)]
                _outs = (_outs + [{"turn": turn.idx,
                                   "helped": bool(_helped)}])[-4:]
                _led["outcomes"] = _outs
                if (len(_outs) >= 2 and not _outs[-1]["helped"]
                        and not _outs[-2]["helped"]):
                    # Two consecutive injections that moved nothing: the
                    # character is stuck for a reason contrast cannot reach.
                    # Suppressed until the trigger is observed fully clear.
                    _led["suppressed"] = True
                _led.pop("pending", None)
            if not _probe.get("stuck"):
                _led["clear_seen"] = True
                _led["suppressed"] = False
            if _probe.get("fired") and _probe.get("memory_id") is not None:
                try:
                    _mid = int(_probe["memory_id"])
                except (TypeError, ValueError):
                    _mid = None
                if _mid is not None:
                    _led["last_turn"] = turn.idx
                    _led["last_trigger"] = str(_probe.get("trigger") or "")
                    _rids = [i for i in (_led.get("recent_ids") or [])
                             if isinstance(i, int) and i != _mid]
                    _led["recent_ids"] = (_rids + [_mid])[-8:]
                    _led["clear_seen"] = False
                    if _effectful or (_goal_now and _goal_now != _goal_before):
                        # Helped on the injection beat itself.
                        _led["outcomes"] = ([
                            o for o in (_led.get("outcomes") or [])
                            if isinstance(o, dict)]
                            + [{"turn": turn.idx, "helped": True}])[-4:]
                    else:
                        _led["pending"] = {
                            "turn": turn.idx, "goal": _goal_now,
                            **({"memory_ref": _probe_ref}
                               if _probe_ref else {})}
            _led["repeat_flag"] = bool(_probe.get("repeat_survived"))
            st["unbidden"] = _led
        if est and not v:
            room_label = char_room or "the scene"
            room_data2 = (sc.get("rooms") or {}).get(room_label, {})
            room_name2 = room_data2.get("name") or room_label
            room_desc = room_data2.get("desc") or room_data2.get("notes") or ""
            v = f"The scene opens. You are in {room_name2}." + (
                f" {room_desc}" if room_desc else ""
            )
        if v:
            # F2/P1: dialogue memory recognition gate. The speaker's
            # canonical name was stored regardless of whether the hearer
            # recognizes them, leaking identity into memory. Check the
            # hearer's known map -- if the speaker isn't recognized, store
            # an appearance-based label or "a voice" instead, and drop
            # intended_target (which also names the speaker).
            _known_map = wget(cid, "known", {}) or {}
            _hearer_known = set(_known_map.get(cname) or [])
            for d in dlog:
                spk = d.get("speaker", "")
                # The player used to be rewritten to the literal "the player"
                # here and then EXEMPTED from the recognition gate below, so a
                # character's own memory read `the player said "My Name is
                # Hinami." to Dr. Moon` -- the engine's out-of-fiction word for
                # the protagonist, inside a fictional mind, in the very memory
                # where they learned her name. 68 rows across the live corpus.
                # The player is a body in the room like any other: pass the
                # persona's real name in and let the gate decide, exactly as it
                # does for every character.
                _spk_is_player = _is_player(spk, chat)
                if _spk_is_player:
                    from scene import persona_of
                    spk = persona_name(persona_of(ctx.chat)) or spk
                if spk == cname:
                    continue
                # Recognition gate: the canonical name only if the hearer knows
                # the speaker. The label comes from _unknown_actor_label, the
                # same helper every perception path uses, rather than a second
                # hand-rolled copy of it -- the copy truncated at a fixed 60
                # characters and cut mid-word, and two implementations of the
                # identity floor drift apart exactly where it matters.
                if spk not in _hearer_known:
                    from agents.common import (
                        _unknown_actor_label, character_scene_keys)
                    if _spk_is_player:
                        from scene import persona_of
                        _spk_sheet = persona_of(ctx.chat)
                    else:
                        _spk_sheet = next(
                            (sheet for sheet in
                             (json.loads(_cr["sheet"]) for _cr in ctx.cast)
                             if character_name(sheet) == spk),
                            None)
                    spk_label = _unknown_actor_label(
                        spk,
                        _char_appearance(_spk_sheet) if _spk_sheet else None,
                        character_scene_keys(_spk_sheet)[1:] if _spk_sheet else None,
                    )
                    # This memory is HEARD. When there is no appearance to
                    # describe, _unknown_actor_label falls back to "the
                    # unfamiliar person" -- which claims the hearer saw a body.
                    # What they have is a voice.
                    if spk_label == "the unfamiliar person":
                        spk_label = "a voice"
                    tgt = None  # drop intended_target -- it names the speaker
                else:
                    spk_label = spk
                    tgt = d.get("intended_target")
                quote = d.get("exact_quote", "")
                qbody = _quote_body(quote)
                if qbody and (quote in v or qbody in v):
                    # This line reached THIS hearer's view -- the audibility
                    # question is already answered above, so a name inside it
                    # is a name they heard. See _names_heard_in.
                    for _learned in _names_heard_in(
                            qbody, cname, _name_roster, sc, char_room):
                        if _learned not in _hearer_known:
                            _hearer_known.add(_learned)
                            _names_learned.setdefault(cname, []).append(_learned)
                    category = _durable_dialogue_category(qbody)
                    memory_mark = _marked_for_memory(own_result, qbody)
                    # This mind asked to keep the line. The phrase list is a
                    # floor of what ANYONE would remember; what a particular
                    # character finds durable is a fact about that character,
                    # so their own declaration is allowed to add to it -- never
                    # to remove, since the floor exists for the model that
                    # declares nothing. Bounded by everything above: the quote
                    # must have been said this beat and must have reached THIS
                    # observer's view, so a mark can only preserve something
                    # already heard.
                    if not category and memory_mark:
                        category = "dialogue"
                    if category:
                        side_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                            "turn_idx": turn.idx, "kind": "dialogue", "category": category,
                            "provenance": "heard",
                            "salience": 0.9 if category == "promise" else 0.82,
                            "content": f"{spk_label} said {quote}" + (f" to {tgt}" if tgt else ""),
                            "gist": f"{spk_label}: {qbody}", "key_phrases": [qbody, spk_label],
                            "entities": [spk_label], "location": room_name,
                            "emotional_context": " — ".join(
                                p for p in (
                                    mood,
                                    ("kept because " + str(
                                        memory_mark.get("why") or "").strip())
                                    if memory_mark and str(
                                        memory_mark.get("why") or "").strip()
                                    else "",
                                ) if p),
                            "valence": _mem_valence, "arousal": _mem_arousal,
                            "event_key": _stable_event_key(
                                turn.id, ccid, "dialogue", d.get("speaker"),
                                qbody, d.get("intended_target"),
                            ),
                        })
            episode_content = v
            # IR-minted episode (see the top of this function): the composer
            # already rendered this mind's episode from the same gated,
            # fidelity-degraded percepts its view rendered -- never richer --
            # with typed entities instead of names scraped back out of prose
            # (memory.py's `_extract_entities` fallback).
            if _composed_episodes is not None and str(ccid) in _composed_episodes:
                episode_content = str(_composed_episodes.get(str(ccid)) or "")
                _meta = _composed_episode_meta.get(str(ccid)) or {}
                _episode_entities = [
                    str(e) for e in (_meta.get("entities") or [])
                    if str(e or "").strip()]
                _episode_gist = str(_meta.get("gist") or "").strip()
            # A view that says only "you are somewhere unspecified" is the
            # ABSENCE of an event, and an absence is not an episode. Minted
            # anyway, it becomes a retrievable memory carrying no information:
            # measured live, 356 rows across five stories -- 7.3% of the whole
            # bank, and a THIRD of one story's -- were the single sentence
            # "You are in an unspecified area.", all at salience 0.47, all
            # identical, all eligible to be handed to a character instead of
            # something that happened.
            #
            # It arises legitimately (an NPC off in unloaded space) and
            # illegitimately (`character_room`'s docstring calls the same
            # phrase "leaking a false empty view" from a position it could not
            # resolve). The cause does not change the remedy: either way there
            # is nothing to remember, so nothing is written. The turn still
            # happened and the turn index still records it. The composer
            # generalizes this floor upstream: a percept list that is all
            # unchanged standing state renders an EMPTY episode, so the
            # marker check below is the backstop, not the mechanism.
            if _is_empty_view(episode_content):
                episode_content = ""
        if episode_content:
            _episode_row = {
                "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                "turn_idx": turn.idx, "kind": "episodic", "category": "episode",
                "provenance": "witnessed", "salience": _salience_of(episode_content),
                "content": episode_content, "location": room_name,
                "emotional_context": mood,
                "valence": _mem_valence, "arousal": _mem_arousal,
                "event_key": _stable_event_key(turn.id, ccid, "episode"),
            }
            if _episode_entities:
                _episode_row["entities"] = _episode_entities
            if _episode_gist:
                _episode_row["gist"] = _episode_gist
            pending_memories.append(_episode_row)
        pending_memories.extend(side_memories)
        if own_result:
            # Ponder is a private, deliberate retrieval request for the NEXT
            # character turn. The character stage removed it from the public
            # sequence, so it never becomes a world action. Consume an older
            # pending query only when this mind actually produced a committed
            # result, then optionally stage one new bounded query.
            _pending_ponder = (st.get("memory_ponder")
                               if isinstance(st.get("memory_ponder"), dict)
                               else {})
            try:
                _ponder_due = int(_pending_ponder.get("set_turn")) < turn.idx
            except (TypeError, ValueError):
                _ponder_due = False
            if _ponder_due:
                st.pop("memory_ponder", None)
            _new_ponder = (own_result.get("ponder")
                           if isinstance(own_result.get("ponder"), dict)
                           else {})
            _ponder_query = " ".join(
                str(_new_ponder.get("query") or "").split())[:240]
            _ponder_why = " ".join(
                str(_new_ponder.get("why") or "").split())[:240]
            if _ponder_query and _ponder_why:
                st["memory_ponder"] = {
                    "query": _ponder_query,
                    "why": _ponder_why,
                    "set_turn": turn.idx,
                }
                # Telemetry only, never a gate: a useful answer is allowed to
                # raise a new deliberate question immediately.
                st["last_ponder_turn"] = turn.idx
            seq = own_result.get("sequence") or []
            own_salience = float(own_result.get("salience", 0.0))
            # The bound: everything a mind SAID is durable (conversation
            # continuity is what measurably dies without it), a silent act is
            # durable only when the mind's own appraisal reached 0.7 -- idle
            # motion below that keeps its 12-turn `_recent_self_moves` window
            # and the episode of its consequences, not a row per fidget. This
            # is at most one extra row per speaking/salient character per
            # beat, beside the episode row every character already gets.
            should_store_own_acts = bool(seq) and (
                own_salience >= 0.7
                or any(event.get("type") == "speech" for event in seq)
            )
            # ALWAYS beside the episode, never instead of it. d290ca4 gated
            # this on `not episode_content`, reasoning that the view was
            # "already the coherent, resolved first-person episode" -- true
            # under model-composed perception, which wrote "You say X" into a
            # mind's own view. One day later 3a82657 made every view
            # deterministic, and the composer structurally EXCLUDES a mind's
            # own conduct from its own view (that is the firewall, and it is
            # correct) -- so the branch went unreachable and every character
            # in every story stopped remembering anything they said or did.
            # Measured live: chat 67 (pre-regression) holds 20 self rows over
            # 51 turns; chats 69-80 hold 0 over 240 turns, and chat 80's Dr.
            # Moon restated the same three propositions on five consecutive
            # beats with no memory of a promise she made on turn 5. The
            # fragmentation d290ca4 was fixing was the old "I chose to
            # attempted '...'" wording replaying an act as a second event;
            # `_own_sequence_memory`'s decision framing is that fix, and it
            # stands whether or not a view exists.
            if should_store_own_acts:
                self_content, self_gist = _own_sequence_memory(seq)
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "episodic", "category": "self",
                    "provenance": "remembered", "salience": max(0.5, own_salience),
                    "content": self_content,
                    "gist": self_gist,
                    "location": room_name, "emotional_context": mood,
                    "valence": _mem_valence, "arousal": _mem_arousal,
                    "event_key": _stable_event_key(turn.id, ccid, "own_acts"),
                })
            # The REKEYED updates (see the top of this loop body), so the
            # memory row's subject matches the key the hypothesis will live
            # under in mind_models.
            for update in _mm_updates:
                confidence = _clamp(update.get("confidence", 0.5))
                evidence = "; ".join(
                    str(item.get("fact") or "").strip()
                    for item in update.get("evidence") or []
                    if isinstance(item, dict)
                    and str(item.get("fact") or "").strip()
                )
                about = str(update.get("about_entity") or "").strip()
                claim = str(update.get("claim") or "").strip().rstrip(".")
                prefix = "" if claim.casefold().startswith(
                    about.casefold() + " ") else (f"About {about}: " if about else "")
                inference_content = f"{prefix}{claim}."
                if evidence:
                    inference_content += f" Evidence: {evidence}"
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "inference", "category": "inference",
                    "provenance": "inferred", "salience": 0.45 + 0.3 * confidence,
                    "confidence": confidence,
                    "content": inference_content,
                    "gist": claim if len(claim) <= 240 else claim[:239].rsplit(" ", 1)[0] + "…",
                    "entities": [about] if about else [],
                    "location": room_name, "emotional_context": mood,
                    "event_key": _stable_event_key(
                        turn.id, ccid, "mind_model", update.get("about_entity"),
                        update.get("kind"), update.get("claim"),
                    ),
                })
            # --- Interior depth: deterministic floors over the model's proposed
            # active_state (goals + blended affect). All fields are optional;
            # absent ones degrade to the legacy {mood,goal}. affect.py is pure;
            # this is the single write point where the floors apply.
            if own_result.get("active_state") is not None:
                asv = own_result.get("active_state")
                if not isinstance(asv, dict):
                    asv = {"mood": str(asv), "goal": ""}
                prev_as = st.get("active_state") if isinstance(st.get("active_state"), dict) else {}
                interior = st.get("interior") if isinstance(st.get("interior"), dict) else {}
                intentions = interior.get("intentions") or []
                # How much this mind holds at once: the authored rung, narrowed
                # by one at the top of the absorption range. Read off the body
                # the character came INTO this beat with, because that is the
                # state they decided it in -- the settled figure below governs
                # the next beat, and using it here would apply a consequence of
                # the beat to the deliberation that produced it.
                _want_cap, _intent_cap = affect.capacity_caps(
                    character_psychology(sh).get("capacity"),
                    psychology_runtime.cognitive_absorption(
                        prev_as.get("hedonic"), prev_as.get("stress")))
                # Seed the character's AUTHORED standing intentions (from the
                # card's initial_state.goals) into the live list, so the model
                # can progress/close them via intent_ops and they persist and
                # evolve. Dedup by text against the CURRENT list (including any
                # already-abandoned/blocked copy), so a goal the character has
                # set aside never re-seeds. Mirrors the read-side merge in
                # agents/character._merge_standing_intentions.
                _seen_intent = {str(i.get("intent") or "").strip().casefold()
                                for i in intentions if isinstance(i, dict)}
                for _a in character_standing_intentions(sh):
                    if str(_a.get("intent") or "").strip().casefold() not in _seen_intent:
                        intentions = intentions + [_a]
                # PROJECTS (Tier 1.5): durable-but-not-eternal commitments,
                # capped at two -- see affect.apply_project_ops and
                # docs/design/DESIGN_LONG_TERM_GOALS.md. Authored ones seed from
                # the card exactly as standing intentions do, deduped
                # against live AND former so a project the character gave
                # up (with a stated reason) never silently re-seeds over
                # that decision. NOTE: _interior_out below is rebuilt from
                # scratch each beat, so both ledgers must be carried
                # through it explicitly or a beat would erase them.
                projects = [dict(p) for p in (interior.get("projects") or [])
                            if isinstance(p, dict)]
                former_projects = [
                    dict(p) for p in (interior.get("former_projects") or [])
                    if isinstance(p, dict)]
                # Deduped on ID as well as text. Text alone is not enough:
                # a project's wording can legitimately CHANGE after adoption
                # -- the maze harness appends the goal room's name the beat
                # the character first stands in it, which is the moment that
                # identifier becomes legitimately his -- and a text-keyed
                # check then stops recognising the authored source and seeds
                # a second copy of the same project. Measured live: `pa1`
                # held twice, one project occupying both slots, which defeats
                # the cap that is the entire point of the tier.
                _seen_proj = {
                    str(p.get("project") or "").strip().casefold()
                    for p in projects + former_projects}
                _seen_pids = {str(p.get("id") or "")
                              for p in projects + former_projects}
                for _p in character_projects(sh):
                    if len(projects) >= affect.PROJECT_CAP:
                        break
                    if str(_p.get("id") or "") in _seen_pids:
                        continue
                    if str(_p.get("project") or "").strip().casefold() \
                            not in _seen_proj:
                        # Seeding counts as service: the drift clock starts
                        # at the seeding beat, never at authored turn 0.
                        projects = projects + [
                            dict(_p, last_served_turn=turn.idx)]
                projects, former_projects, _pwarn = affect.apply_project_ops(
                    projects, former_projects,
                    own_result.get("project_ops") or [], turn.idx)
                for w in _pwarn:
                    ctx.add_warning(f"{cname}: project -- {w}")
                _project_ids = {str(p.get("id") or "") for p in projects}
                # Probationary vs established, as the character SAW them at
                # the start of this beat (pre-settlement, like valid_ids
                # for intentions): a probationary project weighs at
                # intention level until service establishes it.
                _probation_ids = {str(p.get("id") or "") for p in projects
                                  if p.get("probation")}
                _established_ids = _project_ids - _probation_ids
                drive = (character_psychology(sh) or {}).get("drive") or {}

                # this beat's evidence pool: resolved event + spoken lines, for
                # gating intention satisfy/abandon (light floor: cited + present).
                _ev_text = (res.get("resolved_event") or "") + " " + " ".join(
                    str(d.get("exact_quote") or "") for d in dlog)

                def _evidence_ok(op, _t=_ev_text):
                    ev = op.get("evidence") or []
                    if not ev:
                        return False
                    return any(str(e) and str(e) in _t for e in ev) or bool(op.get("why"))

                _before_status = {
                    str(i.get("id")): i.get("status")
                    for i in intentions if isinstance(i, dict)
                }
                intentions, _iwarn = affect.apply_intent_ops(
                    intentions, own_result.get("intent_ops") or [], turn.idx,
                    _evidence_ok, intent_cap=_intent_cap,
                    # Set by the character stage when this beat repeated an
                    # earlier move and the screen did not judge the repetition
                    # warranted -- i.e. the beat the engine already paid a full
                    # re-ask over. A `progress` claim on one of those does not
                    # advance the goal (affect._advance_intent).
                    barren_beat=bool(own_result.get("_barren_beat")))
                # OUTCOME FEEDBACK. Everything else in this engine revises a
                # belief by CONTRADICTION -- another claim -- never by whether
                # acting on it worked. So a character who concludes something,
                # acts, and is wrong sees that belief decay from disuse at
                # exactly the rate a correct one would, and a route that
                # demonstrably reached a goal accumulates no weight against the
                # novelty of one that has not been tried.
                #
                # An intention reaching `satisfied` is the one success signal
                # the engine can observe without trusting a bare self-report:
                # apply_intent_ops gates satisfy behind _evidence_ok, so it
                # needs on-screen cause. When one closes, the rooms walked
                # while pursuing it are credited -- their own route, no oracle
                # knowledge of whether it was the BEST way, only that it was a
                # way that worked.
                _satisfied = [
                    i for i in intentions
                    if isinstance(i, dict) and i.get("status") == "satisfied"
                    and _before_status.get(str(i.get("id"))) != "satisfied"
                ]
                if _satisfied:
                    _worked = st.get("routes_that_worked")
                    if not isinstance(_worked, dict):
                        _worked = {}
                    _since = max(
                        0, len(st.get("visited_rooms") or [])
                        - ROUTE_CREDIT_WINDOW)
                    for _r in set((st.get("visited_rooms") or [])[_since:]):
                        _worked[_r] = min(
                            ROUTE_CREDIT_CAP, int(_worked.get(_r, 0)) + 1)
                    st["routes_that_worked"] = _worked
                for w in _iwarn:
                    ctx.add_warning(f"{cname}: intention -- {w}")
                _steering = affect.steering_intent_ids(intentions, turn.idx)
                # A known id is not automatically a current purpose. Dormant,
                # blocked, satisfied and abandoned intentions remain in the
                # ledger for continuity, but cannot legitimize a fresh want by
                # appearing in `serves`. `_steering` deliberately includes an
                # intention closed THIS beat (last_progress_turn == turn.idx),
                # so a payoff is not demoted because of state the character
                # could not have seen when deciding. A goal already spent at
                # the START of the beat is absent and normalizes to situational.

                def _priority(serves, _ids=_steering, _intents=intentions,
                              _projs=projects, _pids=_established_ids,
                              _probs=_probation_ids):
                    # Models emit serves as "intention:<id-or-text>" or
                    # "project:<id-or-text>"; resolve to the bare id so a
                    # goal-serving impact scores at its tier's priority, not
                    # the situational default. An ESTABLISHED project weighs
                    # at DRIVE priority (1.0) -- the 1.0-vs-0.8 loss is the
                    # measured failure the project tier exists to close; a
                    # probationary one at intention priority (0.8) -- drive
                    # weight is earned by service, never by adoption.
                    serves = affect.normalize_serves(serves, _intents, _projs)
                    return affect.serves_priority(str(serves), _ids, _pids,
                                                  _probs)

                wants, enacted, suppressed = affect.normalize_wants(
                    asv.get("wants") or [], _steering | _project_ids,
                    want_cap=_want_cap)

                appraisal_input = dict(own_result.get("appraisal") or {})
                # Past experience may change familiarity, expectation and
                # perceived coping resources. It may also produce a mild body
                # echo or prime threat detection, but may not manufacture
                # current pain/pleasure, a present threat, or a goal event.
                # Apply every contribution only through the separately
                # grounded memory_modulation lane.
                _mod = appraisal_input.get("memory_modulation")
                _memory_echo = {}
                if isinstance(_mod, dict) and _mod.get("evidence"):
                    try:
                        _familiarity = max(
                            0.0, min(1.0, float(_mod.get("familiarity") or 0.0)))
                        _coping_effect = max(
                            -1.0, min(1.0, float(
                                _mod.get("coping_effect") or 0.0)))
                        _somatic_echo = max(
                            -1.0, min(1.0, float(
                                _mod.get("somatic_echo") or 0.0)))
                        _threat_bias = max(
                            0.0, min(1.0, float(
                                _mod.get("threat_bias") or 0.0)))
                    except (TypeError, ValueError):
                        (_familiarity, _coping_effect,
                         _somatic_echo, _threat_bias) = 0.0, 0.0, 0.0, 0.0
                    appraisal_input["novelty"] = max(
                        0.0, min(1.0,
                                 float(appraisal_input.get("novelty") or 0.0)
                                 * (1.0 - 0.35 * _familiarity)))
                    appraisal_input["coping_potential"] = max(
                        0.0, min(1.0,
                                 float(appraisal_input.get(
                                     "coping_potential") or 0.5)
                                 + 0.25 * _coping_effect))
                    # The model reports a normalized tendency; the engine
                    # decides how much reaches live state. One recalled beat
                    # can move either axis by at most 0.2, and the result stays
                    # explicitly labelled remembered_past.
                    _memory_echo = {
                        "somatic": round(0.2 * _somatic_echo, 4),
                        "threat_bias": round(0.2 * _threat_bias, 4),
                        "why": str(_mod.get("why") or "")[:240],
                        "source_refs": [
                            str(e.get("event_id") or "")
                            for e in (_mod.get("evidence") or [])
                            if isinstance(e, dict) and e.get("event_id")
                        ],
                        "temporal_source": "remembered_past",
                    }
                    appraisal_input["memory_echo"] = _memory_echo
                proposed_hedonic = (
                    asv.get("hedonic") if isinstance(asv.get("hedonic"), dict)
                    else {}
                )
                # The appetite this body carried INTO the beat, so appraisal can
                # tell a goal that completed from a drive that is being fed --
                # a confirmed win on an unreleased drive is not a reason to
                # stand down. Read before resolve_hedonic recomputes it, and
                # zeroed the moment the character declares the release, which
                # is the beat satisfaction becomes true.
                _prev_hedonic = (prev_as.get("hedonic")
                                 if isinstance(prev_as.get("hedonic"), dict)
                                 else {})
                _unresolved_drive = (
                    0.0 if bool(proposed_hedonic.get("released"))
                    else _prev_hedonic.get("charge") or 0.0
                )
                appraisal_out = affect.appraise(
                    appraisal_input.get("goal_impacts") or [], _priority,
                    dimensions=appraisal_input,
                    unresolved_drive=_unresolved_drive,
                )
                prev_affect = prev_as.get("affect") if isinstance(prev_as, dict) else None
                baseline = ((prev_affect or {}).get("baseline")
                            or character_initial_active_state(sh)["affect"]["baseline"])
                turns_since = max(1, turn.idx - int(prev_as.get("affect_turn") or (turn.idx - 1)))
                elapsed_units = psychology_runtime.elapsed_psych_units(
                    prev_as.get("affect_seconds"), _clock_seconds, turns_since)
                # Surface habituation (affect.py's _HABITUATION_* block):
                # default off, the shipped behaviour byte-for-byte. Switched
                # per install by the `affect_habituation` setting, read here
                # because affect.py deliberately imports no db. The release
                # flag is the character's own declared hedonic discharge --
                # the same one resolve_hedonic below receives -- which is
                # what lets a climax land uncompressed while the plateau
                # before it settles.
                _habituate = str(
                    get_setting("affect_habituation") or ""
                ).strip().casefold() in ("1", "on", "true")
                new_affect = affect.resolve_affect(
                    prev_affect, appraisal_out, baseline, elapsed_units,
                    proposed=asv.get("affect") or asv.get("mood"),
                    habituate=_habituate,
                    released=bool(proposed_hedonic.get("released")))
                _encoded_surface = new_affect.get("surface") or {}
                _encoding_valence = float(
                    _encoded_surface.get("valence") or 0.0)
                _encoding_arousal = float(
                    _encoded_surface.get("arousal") or 0.0)
                body_state = vitals_of(sc, cname)
                # World-side comfort, from the settled scene: what this body
                # is verifiably against (station/contact/posture, closed
                # vocabulary). Feeds the pleasure LEVEL floor only -- by
                # construction it never reaches the charge term, because a
                # warm bench is a resolved state, not an unresolved drive.
                _comfort, _comfort_src = comfort_level(sc, cname)
                new_hedonic = psychology_runtime.resolve_hedonic(
                    prev_as.get("hedonic"), appraisal_out,
                    character_interoception(sh), body_state, elapsed_units,
                    # Discharging an accumulated drive is the character's own
                    # event to have, so the declaration is theirs; how it built
                    # up in the first place stays the runtime's.
                    released=bool(proposed_hedonic.get("released")),
                    ambient_comfort=_comfort, comfort_source=_comfort_src,
                )
                proposed_stress = (
                    asv.get("stress") if isinstance(asv.get("stress"), dict) else {}
                )
                new_stress = psychology_runtime.resolve_stress(
                    prev_as.get("stress"), appraisal_out,
                    (character_psychology(sh) or {}).get("stress_profile") or {},
                    new_hedonic, elapsed_units,
                    proposed_mode=proposed_stress.get("coping_mode"),
                )

                # Leak tripwire: this character's OWN speech must not state a
                # suppressed want / the undercurrent / an unenacted intention.
                own_speech = [str(d.get("exact_quote") or "") for d in dlog
                              if d.get("speaker") == cname]
                for w in affect.leak_scan(own_speech, wants,
                                          new_affect.get("undercurrent"), intentions):
                    ctx.add_warning(f"{cname}: interior leak -- {w}")

                surface = new_affect.get("surface") or {}
                # The goal slot IS the enacted want's text -- measured on 401
                # recent-era calls: this branch took the want on 99.0% of
                # them, and the emitted goal string it used to fall back on
                # matched that want only 16.2% of the time, so the template
                # stopped asking for it. The fallback chain ends at the
                # PREVIOUS goal, never at empty: a beat with malformed wants
                # is the 1% case, and blanking the slot there silently killed
                # a standing aim -- goal routing, tenure and the unbidden
                # ledger all read this slot, and "" is a decision the
                # character never made. A legacy provider still emitting
                # asv.goal keeps its say first.
                enacted_goal = (wants[enacted]["want"]
                                if (wants and enacted is not None
                                    and 0 <= enacted < len(wants))
                                else asv.get("goal")
                                or prev_as.get("goal") or "")
                st["active_state"] = {
                    "mood": surface.get("label") or str(asv.get("mood") or ""),
                    "goal": str(enacted_goal or ""),
                    # canonical valence/arousal, projected to the flat legacy keys.
                    "valence": float(surface.get("valence") or 0.0),
                    "arousal": float(surface.get("arousal") or 0.0),
                    "affect": new_affect,
                    "wants": wants,
                    "enacted_want": enacted,
                    "suppressed_want": suppressed,
                    "affect_turn": turn.idx,
                    "affect_seconds": _clock_seconds,
                    "stress": new_stress,
                    "hedonic": new_hedonic,
                    # One-beat, source-labelled state. Deliberately separate
                    # from hedonic pain/pleasure and from current observations.
                    "memory_echo": _memory_echo,
                    "active_concerns": (
                        asv.get("active_concerns")
                        or prev_as.get("active_concerns")
                        or character_initial_active_state(sh).get("active_concerns")
                        or []
                    ),
                }
                # --- Project service ledger + boundary review (Tier 1.5).
                # A held project stopped failing by being outranked and
                # started failing by being FORGOTTEN (A15 run 5: pa1 held at
                # weight 1.0, twenty beats in, nothing emitted serving it).
                # Two deterministic facts close that gap: last_served_turn
                # per project (read back as `adrift` in the payload), and a
                # one-beat review flag when a boundary the engine can
                # actually see has passed. Facts only -- nothing here writes
                # a want or applies an op.
                from agents.common import character_room as _char_room_of
                _named_rooms = {}
                for _nrid, _nrec in (((st.get("place_graph") or {})
                                      .get("nodes")) or {}).items():
                    if isinstance(_nrec, dict):
                        _nname = str(_nrec.get("name") or "").strip()
                        if _nname:
                            _named_rooms.setdefault(_nname.casefold(),
                                                    str(_nrid))
                # Beat-goal slot currency: the slot is rewritten every
                # commit from the enacted want, but the CLAIM inside it is
                # whatever the model re-emits, and nothing above counts its
                # tenure or notices its named room has been reached. Stamp
                # both facts here (goal_since / goal_room /
                # goal_room_reached); agents/character reads them back as
                # `goal_held` / `goal_reached` and stops ROUTING on a spent
                # claim -- see affect.goal_slot_currency.
                st["active_state"].update(affect.goal_slot_currency(
                    prev_as, str(enacted_goal or ""), _named_rooms,
                    _char_room_of(sc, sh), turn.idx))
                for _p in projects:
                    # One-shot backfill for projects that predate the ledger
                    # (a live pa1 exists): grace from here, never instantly
                    # adrift on the deploy beat. NOT setdefault -- the live
                    # pa1 was measured carrying an explicit
                    # last_served_turn: null, which setdefault preserves,
                    # leaving the ledger dead and the drift marker silent
                    # forever.
                    try:
                        int(_p.get("last_served_turn"))
                    except (TypeError, ValueError):
                        _p["last_served_turn"] = turn.idx
                _impact_serves = [
                    affect.normalize_serves(
                        str((gi or {}).get("serves") or ""),
                        intentions, projects)
                    for gi in (appraisal_input.get("goal_impacts") or [])
                    if isinstance(gi, dict)]
                for _pid in affect.projects_served_this_beat(
                        projects, wants, str(enacted_goal or ""),
                        _impact_serves, _named_rooms):
                    for _p in projects:
                        if str(_p.get("id") or "") == _pid:
                            _p["last_served_turn"] = turn.idx
                            # Distinct serving beats, for establishment:
                            # probation is left by service, never survival.
                            _p["served_beats"] = 1 + int(
                                _p.get("served_beats") or 0)
                # Probation settles AFTER this beat's service counted:
                # runtime adoptions establish once lived into (drive weight
                # from the NEXT beat) or lapse quietly once unserved past
                # the fuse. Authored/harness projects carry no probation
                # flag and pass through untouched.
                projects, former_projects, _probw = affect.settle_probation(
                    projects, former_projects, turn.idx)
                for w in _probw:
                    ctx.add_warning(f"{cname}: project -- {w}")
                # Boundary detection runs BEFORE record_spatial_experience
                # (below, line ~4100), so st["visited_rooms"] still ends at
                # the previous position while sc already holds the new one
                # -- which is exactly the arrival comparison needed.
                _prev_room = next(
                    (str(r) for r in reversed(st.get("visited_rooms") or [])
                     if isinstance(r, str) and r), None)
                _scene_marker = (interior.get("scene_marker")
                                 if isinstance(interior.get("scene_marker"),
                                               dict) else None)
                _loc_now = str(sc.get("location") or "")
                _review_why = affect.project_boundary(
                    projects, intentions, _before_status,
                    _char_room_of(sc, sh), _prev_room, _scene_marker,
                    _loc_now, turn.frame_id, _named_rooms)
                # --- Drive rupture (Tier 1): a deterministic strain ledger and
                # two-key gate that can, rarely and earned, crack the core drive.
                def _serves_of(i):
                    return (str(wants[i].get("serves") or "")
                            if (isinstance(wants, list) and isinstance(i, int)
                                and 0 <= i < len(wants)) else "")
                strain = float(interior.get("drive_strain") or 0.0)
                strain_log = list(interior.get("strain_log") or [])
                _strain_turns = max(1, turn.idx - int(interior.get("strain_turn") or (turn.idx - 1)))
                _strain_elapsed = psychology_runtime.elapsed_psych_units(
                    interior.get("strain_seconds"), _clock_seconds, _strain_turns)
                strain, _slog = affect.update_drive_strain(
                    strain, strain_log, appraisal_out,
                    _serves_of(enacted), _serves_of(suppressed), _strain_elapsed)
                if _slog:
                    _slog["turn"] = turn.idx
                    strain_log = (strain_log + [_slog])[-12:]
                cur_drive = effective_drive(character_psychology(sh), interior)
                former = list(interior.get("former_drives") or [])
                last_shift = interior.get("last_shift_turn")
                override = interior.get("drive_override") if isinstance(interior.get("drive_override"), dict) else None
                rupture = interior.get("drive_rupture") if isinstance(interior.get("drive_rupture"), dict) else None
                window_open = bool(rupture and turn.idx <= int(rupture.get("window_expires") or -1))
                if not window_open:
                    _det = affect.detect_drive_rupture(strain, appraisal_out, turn.idx, last_shift)
                    if _det:
                        rupture = {"turn": turn.idx, "opened_turn": turn.idx,
                                   "why": _det.get("why"),
                                   "direction": _det.get("direction"), "window_expires": turn.idx + 3}
                        ctx.add_warning(f"{cname}: DRIVE RUPTURE window opened -- {_det.get('why')}")
                elif own_result.get("drive_shift"):
                    _norm, _kind, _vw = affect.validate_drive_shift(
                        own_result.get("drive_shift"), cur_drive, former, rupture)
                    for w in _vw:
                        ctx.add_warning(f"{cname}: drive_shift -- {w}")
                    if _norm and _kind == "break":
                        _rw = str(rupture.get("why") or "")
                        former = (former + [affect.former_drive_entry(cur_drive, turn.idx, _rw)])[-5:]
                        override = {**_norm, "since_turn": turn.idx, "by_event": _rw}
                        strain, last_shift, rupture = 0.0, turn.idx, None
                        ctx.add_warning(f"{cname}: DRIVE SHIFTED -> {_norm.get('essence')}")
                        pending_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id, "turn_idx": turn.idx,
                            "kind": "episode", "category": "self", "provenance": "remembered", "salience": 1.0,
                            "content": (f"Something in me broke when {_rw}. What I lived for -- "
                                        f"{cur_drive.get('essence')} -- no longer holds me. Now I live for: "
                                        f"{_norm.get('essence')}."),
                            "gist": f"drive shift -> {_norm.get('essence')}"[:240],
                            "entities": [cname], "location": room_name,
                            "emotional_context": surface.get("label") or "",
                            "event_key": _stable_event_key(turn.id, ccid, "drive_shift", cname,
                                                           _norm.get("essence"), ""),
                        })
                    elif _norm and _kind == "bend":
                        override = {**_norm, "since_turn": turn.idx, "by_event": str(rupture.get("why") or "")}
                        strain, last_shift, rupture = strain * 0.5, (turn.idx - 30), None
                if rupture and turn.idx > int(rupture.get("window_expires") or -1):
                    _opened_turn = int(rupture.get("opened_turn") or rupture.get("turn") or turn.idx)
                    _turns_open = turn.idx - _opened_turn
                    if strain >= affect.RUPTURE_STRAIN_MIN \
                            and _turns_open < affect.RUPTURE_MAX_OPEN:
                        # Strain still at rupture level and the hard cap not yet
                        # reached: the crisis is unresolved, so the window RE-OPENS
                        # (extends) instead of quietly closing -- denial is a phase,
                        # not an exit. (agents/character.py escalates the prompt to a
                        # FORCED resolution once the window has been open
                        # RUPTURE_FORCE_AFTER turns, so this extension is not the
                        # unpressured "you MAY" it used to be.)
                        rupture = {**rupture, "window_expires": turn.idx + 3}
                        ctx.add_warning(
                            f"{cname}: drive-rupture window extended -- "
                            f"strain {strain:.2f} still at rupture level")
                    else:
                        # Force-close: either strain finally decayed below the floor,
                        # OR the window has been open RUPTURE_MAX_OPEN turns with no
                        # shift. A model that will not shift within the forced window
                        # has, in effect, reaffirmed the drive under maximal pressure
                        # -- so resolve the crisis (pay strain down below the floor)
                        # rather than leaving the character in a permanent, never-
                        # resolving limbo (the 23-turn Vorne case).
                        if strain >= affect.RUPTURE_STRAIN_MIN:
                            strain = affect.RUPTURE_STRAIN_MIN * 0.75
                            ctx.add_warning(
                                f"{cname}: drive-rupture force-closed after "
                                f"{_turns_open} turns unresolved -- drive reaffirmed "
                                f"under pressure, strain paid down")
                        else:
                            strain = strain * 0.5   # weathered the crisis, no shift
                        rupture = None
                _interior_out = {
                    "intentions": intentions,
                    # Both project ledgers, every beat: this dict is rebuilt
                    # from scratch, and a key not carried here is a key
                    # silently erased.
                    "projects": projects,
                    "former_projects": former_projects,
                    # Where and in which frame this beat committed -- what
                    # project_boundary compares against next beat. Written
                    # unconditionally so a project adopted later still meets
                    # a fresh marker.
                    "scene_marker": {"location": _loc_now,
                                     "frame": str(turn.frame_id or "")},
                    "drive_strain": round(float(strain), 4),
                    "strain_log": strain_log,
                    "former_drives": former,
                    "last_shift_turn": last_shift,
                    "strain_turn": turn.idx,
                    "strain_seconds": _clock_seconds,
                    "beliefs": psychology_runtime.apply_belief_updates(
                        interior.get("beliefs"), character_psychology(sh),
                        own_result.get("belief_updates") or [], turn.idx,
                        _clock_seconds,
                    ),
                    "associations": psychology_runtime.apply_association_updates(
                        interior.get("associations"), character_psychology(sh),
                        own_result.get("association_updates") or [], turn.idx,
                        _clock_seconds,
                    ),
                }
                if rupture is not None:
                    _interior_out["drive_rupture"] = rupture
                if override is not None:
                    _interior_out["drive_override"] = override
                if _review_why:
                    # One-beat flag: _interior_out is rebuilt each commit,
                    # so this clears itself unless a new boundary fires.
                    _interior_out["project_review"] = {
                        "turn": turn.idx, "why": _review_why}
                st["interior"] = _interior_out
            # --- Recent-tell ledger: the last few physical cues this
            # character has shown, kept on cstate and fed back into the
            # next character payload (self.recent_tells) so the model
            # stops reaching for the same gesture every beat.
            _tells = [t for t in ((own_result.get("manifest") or {}).get("tells") or [])
                      if isinstance(t, dict)]
            _cues = [str(t.get("cue") or "").strip() for t in _tells]
            _cues = [c for c in _cues if c]
            if _cues:
                _prev_cues = [str(c) for c in (st.get("recent_tells") or [])
                              if str(c).strip()]
                st["recent_tells"] = (_prev_cues + _cues)[-RECENT_TELLS_CAP:]
            # --- Tell-ground ledger (F6): each shown cue with the private
            # ground it betrayed (`because`, grounded at the character stage
            # by affect.ground_tells), kept on cstate and fed back as
            # self.tell_grounds so a later beat can pay the tell off. Same
            # cap as the cue ledger; grounds never leave the character's own
            # private context.
            _grounds = [
                {"cue": str(t.get("cue") or "").strip(),
                 "because": str(t.get("because") or "").strip(),
                 "turn": turn.idx}
                for t in _tells
                if str(t.get("cue") or "").strip()
                and str(t.get("because") or "").strip()
            ]
            if _grounds:
                _prev_grounds = [
                    g for g in (st.get("tell_grounds") or [])
                    if isinstance(g, dict) and str(g.get("cue") or "").strip()
                ]
                st["tell_grounds"] = (_prev_grounds + _grounds)[-RECENT_TELLS_CAP:]
            stance = st.get("stance") or sh.get("stance") or {"axes": {}}
            for u in own_result.get("stance_updates") or []:
                ax = u.get("axis")
                if not ax:
                    continue
                try:
                    stance.setdefault("axes", {})
                    # P9: the schema clamps each DELTA, but the running total
                    # was unbounded -- a character nudged the same direction
                    # every beat walked past the [-1, 1] the axes are read as
                    # (character_schema seeds them from baseline_stances in
                    # that range), and every consumer downstream then compared
                    # against a scale the value had left. Clamped here because
                    # this is the only place the accumulation happens; a reroll
                    # re-applying a delta is P2's problem, not this one.
                    stance["axes"][ax] = round(
                        max(-1.0, min(1.0,
                            float(stance["axes"].get(ax, 0))
                            + float(u.get("delta", 0)))),
                        3,
                    )
                    stance.setdefault("log", []).append({
                        "turn": turn.idx, "axis": ax,
                        "delta": u.get("delta"), "trigger": u.get("trigger"),
                    })
                except Exception:
                    pass
            st["stance"] = stance
            # Rooms this body has actually walked through, the exits of rooms
            # stood in, visibly-closed chambers, and the durable place graph
            # -- everything a beat of standing somewhere earns, recorded in
            # one place (see record_spatial_experience). Their OWN traversal
            # history and sight, so it crosses no information boundary.
            # Lazy, like the other agents.common uses in this module: importing
            # it at module scope would close an import cycle.
            from agents.common import character_room as _character_room
            record_spatial_experience(
                st, sc, _character_room(sc, sh), turn.idx)
            # Place purpose, witnessed basis: their OWN vitals rising across
            # consecutive commits settled in this room (they ate here; they
            # rested here), or their body verifiably lying on a soft support
            # (comfort.rest_affording -- the seam comfort.py left for exactly
            # this writer). Runs after record_spatial_experience so the
            # standing room's node exists. Never the event row.
            import place_purpose
            place_purpose.witness_affords(st, sc, cname, turn.idx)
            # _mm_updates was rekeyed once at the top of this loop body (a
            # claim about a PLACE is re-keyed onto that place before it is
            # merged, because hypotheses group by (about_entity, kind) and
            # explain each other away within a group -- correct for a mind,
            # backwards for space; people stay protected). The SAME rekeyed
            # list minted this turn's inference memories above, so memory
            # subject and hypothesis key cannot drift apart.
            # Absorption is read off the state we just settled, so it reflects
            # the body at the END of the beat -- the state the character
            # actually comes out of it in, which is what governs what they can
            # still hold in mind going into the next one.
            _settled = st.get("active_state") or {}
            _absorption = psychology_runtime.cognitive_absorption(
                _settled.get("hedonic"), _settled.get("stress"))
            st = apply_mind_model_updates(
                st, _mm_updates, turn.idx, elapsed_seconds=_clock_seconds,
                absorption=_absorption,
            )
            # Place purpose, told basis: stated-fact place beliefs (already
            # re-keyed onto place names above) mirrored onto this character's
            # OWN place-graph nodes, and every existing told entry's sureness
            # re-asked from belief_credence -- the node entry is a read-model
            # of the belief, and a belief explained away must stop steering
            # (docs/design/DESIGN_PLACE_PURPOSE.md, mandatory drift rule). Runs
            # AFTER the merge so it reads reconciled beliefs, mirroring how
            # reconcile_inference_confidence treats memories.
            place_purpose.mirror_told_affords(st, turn.idx, _clock_seconds)
            # Re-selected on every beat this character acted in, not only when
            # `_mm_updates` is non-empty: capacity tracks the BODY, so someone
            # merely in more pain than last beat holds fewer open questions
            # even though they concluded nothing new.
            _sheet, _sheet_keys = select_active_hypotheses(
                st.get("mind_models") or {},
                st.get("active_hypothesis_keys"),
                sheet_capacity(_absorption),
                turn.idx,
                elapsed_seconds=_clock_seconds,
                absorption=_absorption,
            )
            st["active_hypotheses"] = _sheet
            st["active_hypothesis_keys"] = _sheet_keys
            if _mm_updates:
                # Only characters whose beliefs actually moved this turn are
                # reconciled: the reconcile scans that character's whole
                # inference bank, and a belief cannot be abandoned on a turn
                # nothing was claimed about it.
                belief_reconciles.append(
                    (cid, ccid, st, _clock_seconds))
            explicit_updates = own_result.get("relationship_updates") or []
            if explicit_updates:
                relationship_ops.append(("explicit", ccid, explicit_updates))
            elif own_result.get("inference_updates"):
                relationship_ops.append(
                    ("inference", ccid, own_result.get("inference_updates") or [])
                )
            # This mind re-read one of its own memories. Deferred to the write
            # phase with everything else: prepare_memory_commit is pure.
            for _d in own_result.get("memory_disputes") or []:
                if isinstance(_d, dict):
                    memory_disputes.append(
                        (cid, ccid, str(_d.get("gist") or ""),
                         str(_d.get("now_reads") or ""), turn.idx,
                         str(_d.get("memory_ref") or "")))
            # Consequence, not popularity: a memory the character cited as
            # EVIDENCE for a belief they formed this beat turned out to be
            # load-bearing. Retrieval alone never moves importance -- that
            # would make often-recalled memories more recallable, which is a
            # feedback loop wearing the word.
            _cited = _cited_memory_ids(own_result)
            if _cited:
                importance_bumps.append((ccid, _cited))
        # Every memory minted for this mind on this beat records both the
        # affect carried into the event (valence/arousal) and the resolved
        # affect after appraisal (encoding_*).  Assign here, after every
        # possible append including inference memories.
        for _memory in pending_memories:
            if _memory.get("char_id") == ccid:
                _memory["encoding_valence"] = _encoding_valence
                _memory["encoding_arousal"] = _encoding_arousal
        state_updates.append((cid, ccid, json.dumps(st)))

    event_content = json.dumps({
        "turn": turn.idx,
        "summary": res.get("summary") or "",
        "event": res.get("resolved_event") or "",
        "dialogue_log": dlog,
    })
    memory_batch = prepare_memories_batch(pending_memories)
    # A missing or failing embeddings provider silently downgrades every
    # vector to the local character-trigram hash, which then scores as a
    # fuzzy-lexical signal forever (an audit of a live corpus found 100% of
    # rows on the fallback with nothing anywhere saying so). The batch already
    # records the downgrade; surface it where every other turn anomaly goes.
    _embedded = memory_batch.get("embedded")
    if _embedded is not None and getattr(_embedded, "fallback", False):
        ctx.add_warning(
            "memory embeddings fell back to local hashing "
            f"({getattr(_embedded, 'error', '') or 'no embeddings provider'});"
            " semantic recall is degraded until an embeddings provider is "
            "configured")
    return {
        "memory_batch": memory_batch,
        "names_learned": _names_learned,
        "state_updates": state_updates,
        "relationship_ops": relationship_ops,
        "belief_reconciles": belief_reconciles,
        "memory_disputes": memory_disputes,
        "importance_bumps": importance_bumps,
        "event_content": event_content,
    }


def _consolidate_committed_memories(ctx):
    """Update derived autobiographical summaries after the atomic commit.

    Summaries are reconstructible caches, not primary turn facts.  Keeping
    their LLM calls outside the transaction avoids deadlocks and ensures a
    consolidation failure can never roll back an otherwise valid turn.

    This is the DIRECT, blocking form -- commit_memories' standalone path
    and tests use it. The live turn pipeline no longer does: consolidation
    is a background summarisation job, and running it on the `utility` role
    inside the player's wait was measured at 29.5s of a 45.8s commit stage
    (chat 71 turn 10, the first beat to reach the consolidation cadence).
    `schedule_memory_consolidation` below is the out-of-band twin the commit
    tail actually calls.
    """
    cid = ctx.chat.id
    turn = ctx.turn
    notes = []

    def _consolidate_one(char_row):
        try:
            result = maybe_consolidate_character_memory(
                cid, char_row["id"], turn.idx, frame_id=turn.frame_id,
            )
            if result:
                return (
                    f"{character_name_from_text(char_row['sheet'])}: "
                    "autobiographical summary updated"
                )
        except Exception as exc:
            ctx.add_warning(
                f"Memory consolidation failed for character {char_row['id']}: {exc}"
            )
        return None

    if ctx.cast:
        # A bare pool worker starts from an EMPTY context, so the story
        # language was lost and `memory_consolidate` resolved to English --
        # writing English autobiography into a Japanese story's memory bank.
        # `agents/narration.py` and `agents/director.py` copy the context for
        # exactly this reason; this pool was missed.
        parent = contextvars.copy_context()

        def _consolidate_in_context(char_row):
            return parent.run(_consolidate_one, char_row)

        with ThreadPoolExecutor(max_workers=len(ctx.cast)) as pool:
            for note in pool.map(_consolidate_in_context, ctx.cast):
                if note:
                    notes.append(note)
    return notes


MEMORY_CONSOLIDATION_JOB_KEY = "memory_consolidation"


def schedule_memory_consolidation(ctx):
    """Queue this turn's autobiographical consolidation out of band.

    Returns the Job, or None when there is no cast or one is already in
    flight for this chat. Called from the commit tail AFTER the turn's
    facts are durable, on the same terms as the offscreen ticks beside it:
    a summary is a reconstructible cache derived from committed rows, so
    nothing about correctness changes -- only who waits for it. Measured
    cost of waiting: the first consolidation of a live chat took 29.5s
    (27.4s of it one `utility`-role LLM call) inside the commit stage's
    wall clock.

    The job snapshots the scalars it needs (ids, names, turn, frame) so it
    never touches ctx after the turn returns. Sequential per character with
    a cancellation check between -- abandonable at every unit boundary --
    and a failure for one character is logged and skipped, never raised:
    background work cannot break a turn, and the cadence check re-offers
    the window on a later beat. Deduped on the chat by jobs.submit: a
    consolidation still running when the next beat commits simply keeps
    running, and that beat schedules nothing (maybe_consolidate re-reads
    the cursor, so nothing is lost -- only deferred). Checkpoint restore
    cancels the in-flight job cooperatively (see checkpoints.py) so a
    rolled-back turn does not land a summary computed from rows that no
    longer exist; the residual window -- a restore arriving mid-LLM-call --
    is recorded in docs/UNBUILT.md.
    """
    import jobs

    cid = ctx.chat.id
    turn_idx = ctx.turn.idx
    frame_id = ctx.turn.frame_id
    members = [
        {"id": row["id"],
         "name": character_name_from_text(row["sheet"])}
        for row in (ctx.cast or [])
    ]
    if not members:
        return None

    def _produce(job):
        # Fresh thread, fresh contextvars: pin the scheduling turn's frame
        # for every frame-scoped read/write below (the offscreen tick
        # producers set the precedent, and the reason -- a nested frame's
        # consolidation landing in the present frame -- is the same).
        from db import active_frame_id
        from logging_utils import logger
        token = active_frame_id.set(frame_id)
        try:
            notes = []
            for member in members:
                if job.cancelled.is_set():
                    break
                try:
                    result = maybe_consolidate_character_memory(
                        cid, member["id"], turn_idx, frame_id=frame_id,
                    )
                    if result:
                        notes.append(f"{member['name']}: autobiographical "
                                     "summary updated")
                except Exception as exc:
                    # Silence toward the turn, a trace toward the operator:
                    # the cadence re-offers this window next beat.
                    logger.info(
                        "memory consolidation failed out of band: chat=%s "
                        "char=%s error=%s", cid, member["id"],
                        str(exc)[:300])
            return notes
        finally:
            active_frame_id.reset(token)

    return jobs.submit(cid, MEMORY_CONSOLIDATION_JOB_KEY, _produce,
                       base_turn=turn_idx)


def commit_memories(ctx, nonce, *, prepared=None, consolidate=True):
    prepared = prepared or prepare_memory_commit(ctx)
    turn = ctx.turn
    cid = ctx.chat.id

    with transaction():
        # A name heard this beat, of somebody standing in the room. Applied
        # here rather than in prepare, which runs outside the write lock;
        # merged rather than assigned, because `validated_introductions` may
        # have written the same map earlier in this turn and an explicit
        # introduction must not be lost to an overwrite.
        _learned = prepared.get("names_learned") or {}
        if _learned:
            _known = wget(cid, "known", {}) or {}
            for _hearer, _names in _learned.items():
                _known.setdefault(_hearer, [])
                for _name in _names:
                    if _name not in _known[_hearer]:
                        _known[_hearer].append(_name)
            wset(cid, "known", _known)
        delete_turn_memories(turn.id)
        memory_ids = add_memories_batch(
            prepared_batch=prepared["memory_batch"],
        )
        for kind, char_id, updates in prepared["relationship_ops"]:
            if kind == "explicit":
                # The frame goes with it: a branch that never had the argument
                # must not inherit the reason it happened.
                apply_relationship_updates(cid, char_id, turn.idx, updates,
                                           frame_id=ctx.turn.frame_id)
            else:
                update_relationships_from_inference(
                    cid, char_id, turn.idx, updates,
                )
        for chat_id, char_id, state_json in prepared["state_updates"]:
            set_char_state(
                chat_id, char_id, state_json, frame_id=turn.frame_id,
            )
        # After the batch insert AND after the state write, so this turn's own
        # freshly-minted inference rows are re-weighted by the same reconciled
        # mind_models everything else now reads -- a claim minted at the
        # model's declared confidence and then blended/suppressed by
        # apply_mind_model_updates would otherwise sit in the bank at the
        # pre-blend number forever.
        for chat_id, char_id, char_state, clock_seconds in prepared.get(
                "belief_reconciles") or []:
            reconcile_inference_confidence(
                chat_id, char_id, char_state, turn.idx,
                elapsed_seconds=clock_seconds,
            )
        # A mind re-reading one of its own memories. Scoped to that character's
        # own rows inside record_dispute, so this can never reach across the
        # firewall however the model phrased the gist.
        for chat_id, char_id, _gist, _reading, _tidx, _ref in prepared.get(
                "memory_disputes") or []:
            try:
                record_dispute(chat_id, char_id, _gist, _reading, _tidx,
                               memory_ref=_ref)
            except Exception as exc:
                ctx.add_warning(f"memory dispute not recorded: {exc}")
        # Memories that turned out to be load-bearing for a belief. Once each,
        # ever (`only_unrevised`), which is what keeps this a consequence
        # rather than a popularity loop -- see _cited_memory_ids.
        for char_id, ids in prepared.get("importance_bumps") or []:
            try:
                raise_importance(cid, char_id, event_keys=ids,
                                 only_unrevised=True)
            except Exception as exc:
                ctx.add_warning(f"memory importance not updated: {exc}")
        qi(
            """INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)
            ON CONFLICT(chat_id,turn_id) WHERE turn_id IS NOT NULL
            DO UPDATE SET content=excluded.content""",
            (cid, turn.id, prepared["event_content"]),
        )

    committed = [f"memory:{mid}" for mid in memory_ids]
    if consolidate:
        committed.extend(_consolidate_committed_memories(ctx))
    return {"committed": committed}

# ---- Narration-person commit ----

_NARRATION_PERSONS = ("first", "second", "third")

def commit_narration_person(ctx, nonce):
    """Apply the narration-person detections the narrator stages recorded on
    their returned step content (`narration_person_writes`) but deliberately
    did not persist themselves -- commit.py is the sole persistence boundary,
    and the narrator previously did a durable wset mid-pipeline, before the
    turn was validated/committed (so an aborted or rolled-back turn had
    already flipped the campaign's narration voice). Deterministically
    validated: only `narration_person*` keys with a known person value are
    written, since step content is inspectable and manually editable.
    """
    cid = ctx.chat.id
    applied = 0
    sources = []
    if isinstance(ctx.narrator, dict):
        sources.append(ctx.narrator)
    extra = ctx.get("narrator_extra") or {}
    if isinstance(extra, dict):
        sources.extend(v for v in extra.values() if isinstance(v, dict))
    with transaction():
        for out in sources:
            writes = out.get("narration_person_writes")
            if not isinstance(writes, dict):
                continue
            for key, value in writes.items():
                if (isinstance(key, str) and key.startswith("narration_person")
                        and value in _NARRATION_PERSONS):
                    wset(cid, key, value)
                    applied += 1
    return {"applied": applied}

# ---- Top-level atomic commit ----

def commit_authored_events(ctx, nonce):
    """P4: resolve this beat's DUE authored (player-scheduled) future events
    against the resolved prose (fire / bounded re-queue / stale), then mint any
    NEW ones the Director captured this turn from a future-tense player
    assertion (flow.scheduled_assertions). Runs inside the turn transaction so a
    rollback un-does both -- a rerun re-mints with stable ids (no double
    schedule) and re-resolves idempotently."""
    from authored_events import mint_authored_events, resolve_authored_events
    cid = ctx.chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    fired, requeued, dropped = resolve_authored_events(
        cid, ctx.turn.idx, str(res.get("resolved_event") or ""))
    if requeued:
        ctx.add_warning(
            f"{requeued} authored future-event(s) not enacted this beat; "
            "re-queued to next turn rather than dropped")
    if dropped:
        ctx.add_warning(
            f"{dropped} authored future-event(s) went unresolved past the "
            "re-queue limit and were marked stale")
    interp = ctx.director_interpret or {}
    minted = mint_authored_events(
        cid, ctx.turn.idx, (interp.get("flow") or {}).get("scheduled_assertions"))
    return {"fired": fired, "requeued": requeued, "dropped": dropped,
            "minted": minted}


def commit_offscreen_epoch(ctx, prepared_scene, transit_result):
    """Advance the shared off-screen epoch inside the turn transaction.

    Kept as a named commit domain instead of an inline import so the generated
    code map, failure warning, and pipeline trace all expose this persistence
    boundary. The implementation is pure/deterministic plus world-KV writes;
    model-priced work remains at the post-commit tail.
    """
    from offscreen import advance_epoch

    return advance_epoch(ctx, prepared_scene, transit_result)


def commit_offscreen_plans(ctx, prepared_scene):
    """Apply Director-adjudicated, character-grounded reactive plan ops."""
    from offscreen import apply_plan_ops

    clock = (prepared_scene.get("clock")
             or wget(ctx.chat.id, "simulation_clock", {}) or {})
    return apply_plan_ops(ctx, prepared_scene.get("scene") or {}, clock)


def commit_crowds(ctx, prepared_scene):
    """Apply Director crowd ops, then move every crowd that has somewhere to be.

    Deliberately NOT gated behind a living-world setting. A crowd is on-screen
    atmosphere in the room the player is standing in, not off-screen
    simulation, and it only ever exists because the Director declared it this
    beat -- the off switch is a model that writes no ops. Gating it would make
    the feature invisible in most chats, which is the failure mode this
    project keeps rediscovering: a mechanism assumed live that has never run.

    Two steps in one domain because they must not be separable, and the ORDER
    is the whole mechanic: last beat's flow is spent FIRST, then this beat's
    declaration is applied.

    The other order is the obvious one and it is dead. Applying ops and then
    advancing spends a heading inside the commit that declared it, so the crowd
    arrives before anyone sees it leave -- and `crowds_for_room` therefore
    reports `drift: None` on every turn that will ever be perceived. The whole
    terrain layer is unreachable: the Director is told to resolve a press it
    can never be shown. Caught by `tools/crowd_drive.py` on its first run, and
    it is the same shape as every other zero this project has dug up -- a
    mechanism that reads correct at every line and cannot fire.

    So a heading lives for exactly one beat of perception. The Director
    declares that the market is flowing toward the gate; the player's next
    breath is spent inside a crowd that is going somewhere, with a drift offer
    the Director can honour; and the beat after that, it has gone. `move` stays
    available for a relocation declared outright.
    """
    import crowds as crowds_model
    from spatial import passable_neighbors

    cid = ctx.chat.id
    scene = prepared_scene.get("scene") or {}
    resolved = ctx.director_resolve or ctx.director_establish or {}
    # Establish authors the opening scene and has no `state_diff`, so its
    # crowd ops sit at the top level. Reading only one of the two shapes made
    # an opening beat unable to put anybody in the square.
    raw_ops = ((resolved.get("state_diff") or {}).get("crowd_ops")
               or resolved.get("crowd_ops") or [])
    if not isinstance(raw_ops, list):
        raw_ops = []
    ops = [op.dict() if hasattr(op, "dict") else op for op in raw_ops]

    # The two facts emergence is adjudicated against, both deterministic. Who
    # the story already knows -- a crowd produces strangers, never cast -- and
    # who has spoken this beat, because a line attributed to someone is the
    # durable record that makes their emergence one-way.
    roster = _registered_name_roster(ctx.chat, ctx.cast)
    spoken = {str(line.get("speaker") or "")
              for line in (resolved.get("dialogue_log") or [])
              if isinstance(line, dict)}

    before = wget(cid, crowds_model.CROWDS_WORLD_KEY, []) or []
    rooms = list((scene.get("rooms") or {}).keys())
    turn = int(getattr(ctx.turn, "id", 0) or 0)

    # Counted before `advance_crowds`, which spends every heading it honours
    # and leaves nothing to count afterwards. This is the denominator for "a
    # crowd moved on the graph": a crowd standing still with nowhere to be was
    # never a chance to move, and measuring moves against every standing crowd
    # made a working mechanism read as stuck -- 0/78 over a fifty-one beat
    # story in which no heading was ever declared. Measuring against every row
    # in the table rather than against the opportunities a mechanism had is
    # the exact mistake that has cost this project the most.
    headed = sum(1 for crowd in before
                 if isinstance(crowd, dict) and crowd.get("heading")
                 and str(crowd.get("heading")) != str(crowd.get("room_uid")))

    standing, moves = crowds_model.advance_crowds(
        before, passable_neighbors(scene))
    standing, rejected = crowds_model.apply_ops(
        standing, ops, chat_id=cid, turn=turn, known_rooms=rooms,
        roster=roster, spoken=spoken)

    for reason in rejected:
        ctx.add_warning("crowd op rejected: %s" % reason)
    if standing != before:
        wset(cid, crowds_model.CROWDS_WORLD_KEY, standing)
    return {"offered": len(ops), "standing": len(standing),
            "headed": headed,
            "moved": len(moves), "rejected": len(rejected)}


def commit_all(ctx, nonce):
    """Commit one turn exactly once and atomically.

    Expensive or failure-prone preparation (LLM validation and embeddings)
    happens before SQLite's write transaction.  Every durable mutation then
    runs under one outer transaction; a failure in any domain rolls back all
    earlier domains from the same turn.
    """
    lock = _commit_lock(ctx.turn.id)
    with lock:
        return _commit_all_locked(ctx, nonce)


def _prepare_turn_commit(ctx):
    """Prepare slow commit inputs without holding SQLite's write lock."""
    try:
        scene = prepare_scene_commit(ctx)
        mapping = prepare_mapping_commit(ctx)
        memories = prepare_memory_commit(ctx, scene=scene["scene"])
        claims = prepare_background_claims(ctx)
        return {"scene": scene, "mapping": mapping, "memories": memories,
                "claims": claims}
    except Exception as exc:
        ctx.add_warning(f"commit preparation failed: {exc}")
        raise RuntimeError(f"Commit preparation failed: {exc}") from exc


def _commit_domain(ctx, results, name, operation):
    """Run one durable domain and preserve its name on rollback errors."""
    try:
        results[name] = operation()
    except Exception as exc:
        ctx.add_warning(f"commit_{name} failed; turn rolled back: {exc}")
        raise RuntimeError(f"{name}: {exc}") from exc


def _commit_all_locked(ctx, nonce):
    import extension_runtime as _extensions_module

    prepared = _prepare_turn_commit(ctx)
    results = {}

    try:
        with transaction():
            # Transit sweep first: it mutates the prepared scene (timed
            # arrivals, engine notices) that the scene domain then persists.
            _commit_domain(
                ctx, results, "transit",
                lambda: commit_transit_sweep(
                    ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "world_events",
                lambda: commit_world_event_spine(
                    ctx, results.get("transit") or {}),
            )
            _commit_domain(
                ctx, results, "scene",
                lambda: commit_scene(ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "entities",
                lambda: commit_world_entities(
                    ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "cast",
                lambda: commit_cast_changes(ctx, nonce),
            )
            # These checks intentionally run after scene/entity/cast writes so
            # they inspect this turn's projected world, while still remaining
            # inside the same rollback boundary.
            _commit_domain(
                ctx, results, "paradox",
                lambda: check_and_apply_paradox(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "spatial",
                lambda: detect_and_reconcile_spatial(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "mapping",
                lambda: commit_mapping(ctx, nonce, prepared=prepared["mapping"]),
            )
            _commit_domain(
                ctx, results, "offscreen_plans",
                lambda: commit_offscreen_plans(ctx, prepared["scene"]),
            )
            # After the scene domain, because a crowd op naming a room the
            # same beat created must find that room in the projected world
            # rather than the one the turn started in.
            _commit_domain(
                ctx, results, "crowds",
                lambda: commit_crowds(ctx, prepared["scene"]),
            )
            # A first-class frame-scoped epoch, after mapping so a freshly
            # validated standing intention can participate, but independent of
            # mapping's skip path. `director_establish` is an opening-stage
            # result, not a scene-boundary event; leaving ticks in
            # commit_mapping made the documented mechanism fire once per chat.
            _commit_domain(
                ctx, results, "offscreen_epoch",
                lambda: commit_offscreen_epoch(
                    ctx, prepared["scene"], results.get("transit") or {}),
            )
            _commit_domain(
                ctx, results, "memories",
                lambda: commit_memories(
                    ctx, nonce, prepared=prepared["memories"], consolidate=False,
                ),
            )
            _commit_domain(
                ctx, results, "information_carriers",
                lambda: commit_information_carriers(
                    ctx, prepared["scene"], results.get("world_events") or {}),
            )
            _commit_domain(
                ctx, results, "background_presences",
                lambda: track_background_presences(
                    ctx, nonce, prepared=prepared["claims"]),
            )
            _commit_domain(
                ctx, results, "narration_person",
                lambda: commit_narration_person(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "obligations",
                lambda: commit_obligations(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "world_pressure",
                lambda: commit_world_pressure(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "authored_events",
                lambda: commit_authored_events(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "pending",
                lambda: wset(ctx.chat.id, "pending", []),
            )
            # Extension commit domains run LAST inside the transaction, after
            # every engine domain has landed: an extension computing from the
            # turn's own durable writes must be able to read them. Their
            # failures are contained by the registration's own `on_error` --
            # "warn" (the default) keeps the promise that a broken extension
            # never costs a turn, "fail" is an extension saying its state being
            # wrong is worse than the beat being lost.
            _extensions_module.run_commit_domains(ctx, results)
    except Exception as exc:
        raise RuntimeError(
            f"Commit failed and was rolled back: {exc}"
        ) from exc

    # Autobiographical summaries are derived, reconstructible caches and may
    # invoke an LLM. They therefore run OUT OF BAND, beside the offscreen
    # ticks below: measured live (chat 71 turn 10), the first consolidation
    # was 29.5s of a 45.8s commit stage -- a background summarisation job on
    # the `utility` role, inside the player's wait. A failure is a warning,
    # never a rollback, and never silence.
    try:
        job = schedule_memory_consolidation(ctx)
        results["memory_consolidation"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"memory consolidation scheduling failed: {exc}")
        results["memory_consolidation"] = {"error": str(exc)}

    # Autonomous background->cast promotion likewise runs after the primary
    # transaction: it mints a sheet with an LLM call and is additive and
    # forward-only (the new character becomes step-eligible next turn), so a
    # failure is a warning, never a turn rollback.
    try:
        results["promotions"] = auto_promote_background_characters(ctx)
    except Exception as exc:
        ctx.add_warning(f"auto-promotion failed: {exc}")
        results["promotions"] = {"promoted": [], "error": str(exc)}

    # Out-of-band offscreen ticks start HERE, after the turn's facts are
    # durable, and run in parallel with whatever the player does next. A
    # turn starting never cancels one: cancelling on turn-start would make
    # the world's progress depend on player idleness, which inverts the
    # feature (amendments section 4). Arrival is safe because every tick
    # write is provisional (section 5). Failure is a warning, never a
    # rollback -- and never silence.
    try:
        import offscreen as _offscreen

        job = _offscreen.schedule_profile_ticks(
            ctx, results.get("offscreen_epoch") or {})
        results["offscreen_ticks"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"offscreen tick scheduling failed: {exc}")
        results["offscreen_ticks"] = {"error": str(exc)}

    # The paid `character_agent` rung rides the same epoch, on the same
    # terms: out of band, epoch/base-turn-guarded at landing, never
    # cancelled by a turn starting, and a failure is a warning.
    try:
        import offscreen as _offscreen

        job = _offscreen.schedule_agent_ticks(
            ctx, results.get("offscreen_epoch") or {})
        results["offscreen_agent"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"offscreen agent scheduling failed: {exc}")
        results["offscreen_agent"] = {"error": str(exc)}

    # The rumor ledger's ceiling: authored wording for freshly posted
    # notices, on the same terms as every other out-of-band spend -- after
    # the turn's facts are durable, gated on the ceiling setting, and landed
    # only if the bill still stands when the job returns. The floor never
    # waits on this and never needs it.
    try:
        import artifacts as _artifacts

        job = _artifacts.schedule_artifact_wording(ctx)
        results["artifact_wording"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"artifact wording scheduling failed: {exc}")
        results["artifact_wording"] = {"error": str(exc)}

    # Installed extensions observe the turn HERE, on the same terms as every
    # other hook in this tail: after the turn's facts are durable, so an
    # extension's own write can never be the thing left standing when a domain
    # failure rolls the turn back. It is also the only place an extension may
    # write per-turn state at all (extension_runtime/api.py's commit scope).
    # A failure is a warning, never a rollback -- and never silence.
    try:
        import extension_runtime as _extensions

        results["extensions"] = _extensions.dispatch_turn_committed(ctx)
        # Attribution for the routing seam. An extension that rewrote what a
        # mind was given names itself HERE, on the durable turn, so a character
        # who knows something they should not is one read from their author
        # rather than looking like an engine defect.
        _routing = _extensions.routing_notes(ctx)
        if _routing:
            results["extensions"]["routing"] = _routing
    except Exception as exc:
        ctx.add_warning(f"extension turn hooks failed: {exc}")
        results["extensions"] = {"error": str(exc)}

    # Approach A's floor is computed on the Director payload path, which no
    # commit domain ever sees -- so without this echo the one mechanism whose
    # whole failure history is "nobody could tell it never fired" would stay
    # unmeasurable by tools/fire_rates.py forever. Present only on beats
    # whose resolve stage actually ran with a declared movement (a rerun
    # replayed from storage carries no stash), so absence reads as
    # `no chances`, never as 0%.
    _residue_report = ctx.get("_destination_residue_report")
    if isinstance(_residue_report, dict):
        results["routine_residue"] = dict(_residue_report)

    return {
        "summary": (
            f"Committed turn {ctx.turn.idx}: "
            f"{len(results.get('memories', {}).get('committed', []))} "
            "memory writes"
        ),
        "errors": [],
        "results": results,
    }

