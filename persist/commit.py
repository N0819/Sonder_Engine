"""Atomic world-state commit with mutation validation."""

import contextvars
import copy
import json, re, threading, time, weakref
from concurrent.futures import ThreadPoolExecutor
from core.db import q, qi, qtx, transaction, wget, wset, get_setting
from mind.memory import (
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
from llm.providers import embed_texts
from llm.prompts import get_prompt
from mind import affect
from mind import psychology_runtime
from story.character_schema import (_UNSPACED_SCRIPT, character_name,
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
from core.frames import is_recognized_in_frame
from story import attire as attire_model
from story.scene import (set_char_state, set_char_status, seed_initial_attire,
                   get_scene, SINGULAR_BODY_CONDITIONS,
)
from world.mechanics import mechanics_sweep, news_latency_seconds, stable_event_key
from world.weather import advance_weather, normalize_weather
from world.spatial import (merge_scene_with_diff, _merge_entity, room_of,
                     normalize_room_id, spatial_rel, hear_level,
                     normalize_barrier, normalize_bearing, opposite_bearing,
                     passable_path, rooms_adjacent, visible_adjacent_rooms,
                     guessed_room_sizes, _is_body_entity)
from mind.theory_of_mind import (apply_mind_model_updates, rekey_place_claims,
                            select_active_hypotheses, sheet_capacity)
from world.survival import vitals_of
from world.comfort import comfort_level
from world.paradox import check_and_apply_paradox
from world.spatial_frames import detect_and_reconcile as detect_and_reconcile_spatial
from world.spatial_frames import (infer_companion_carry, infer_vehicle_zones,
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
#
# SEVEN of them are dead in BOTH directions and were dead before the split
# (COMMIT-2, re-verified): `dump_chat_memories`, `restore_chat_memories`,
# `dump_lorebook`, `restore_lorebook`, `knowledge_for_character`,
# `get_relationships` and `save_relationships` are used nowhere in this file
# and imported from `commit` by nothing in the tree. They are named here so
# a reader stops hunting for the use -- not so they can be quietly pruned:
# this block is published surface while extensions port against `ext_api: 1`,
# and removing a re-export is an API change that belongs to one deliberate
# decision covering every facade in the tree, not to a tidy-up.
from persist.commit_common import (_keys_str, _stable_event_key, _clamp,
    _normalize_character_output, _player_name_or_none, _monotonic_elapsed,
    _ADDRESS_ARTICLES, _form_in, _address_forms, _names_heard_in,
    _known_name_roster, _registered_name_roster, _resolve_roster_name,
    _GENERIC_ID_TOKENS, _canonical_token_key, _entity_alias_map,
    _canonical_anchor, _room_of, _normalized_fact)
from persist.commit_place_graph import (VISITED_ROOMS_CAP, ROUTE_CREDIT_WINDOW,
    ROUTE_CREDIT_CAP, PLACE_GRAPH_NODE_CAP, update_place_graph,
    record_spatial_experience)
from persist.commit_destruction import (_destruction_book, _chat_book_graph,
    _book_distances, _audience_book_id, _destruction_cascade,
    _prepare_destruction, _finalize_destruction_news, _apply_destruction)
from persist.commit_room_registry import (_anchored_book_ids, _room_display_slug,
    _registry_alias_index, _apply_room_renames, dedup_minted_rooms,
    _prepare_room_registry, _apply_room_registry,
    sync_room_registry_with_scene, _refresh_relocated_location,
    prune_dangling_exits)
from persist.commit_attire import (_NON_ATTIRE_TERMS, sanitize_attire_items,
    _heal_attire_identity_keys, _beat_voices, _NOTE_NAME_HEAD,
    _garment_named_in, interpret_attire_notes, _fold_duplicate_shed_garments,
    _fold_worn_garment_entities, _set_worn_garment_condition,
    _is_clothing_entity, _adopt_shed_record, _stamp_shed, _mint_shed_garments,
    _record_describes_garment, _shed_record_candidates,
    apply_attire_diff)
from persist.commit_entities import (_is_gated_awareness, _subjects_that_moved,
    _subjects_targeted_by_an_action, _supersede_disguises, _inherit_known_to,
    commit_world_entities)
from persist.commit_ledgers import (OBLIGATION_OVERDUE_AGE, OBLIGATION_CAP,
    pending_obligation_view, _find_obligation, commit_obligations,
    WORLD_PRESSURE_STALL_AGE, WORLD_PRESSURE_CAP, world_pressure_view,
    _find_pressure, commit_world_pressure)
from persist.commit_mapping import (normalize_offscreen_events,
    _apply_mapping_book_ops, prepare_mapping_commit, commit_mapping, _lore_for,
    _fact_is_covered, _generate_fallback_ops)
from persist.commit_background import (BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
    BACKGROUND_PROMOTION_MENTION_THRESHOLD, promotion_thresholds,
    _BACKGROUND_NAME_TITLE_WORDS, _NAME_TITLE_PREFIXES, strip_name_titles,
    name_in_roster, _PRESENCE_ARTICLES, _presence_identity,
    _bodies_answering_to, _canonical_presence_name, _presence_scene_entity,
    _presence_speech_verdict, presence_has_an_identity,
    presence_personhood, presence_room,
    _merge_presence_record,
    _resolve_presence_name,
    _fold_duplicate_presences, with_charter_presences,
    overt_declaration, overt_declaration_text,
    _background_name_mentioned,
    _character_address_of, _valid_pending_reply, _background_fired_reactions,
    _INERT_ENTITY_KINDS, _is_inert_presence_candidate,
    prepare_background_claims, commit_charter_observations,
    track_background_presences,
    BACKGROUND_RECENT_TAIL, _persist_blurbs, _append_manager_conduct,
    _background_fired_reactions_any, _flow_addressed_refs,
    _presence_in_addressed_refs, _at_post_within_earshot,
    pick_background_reactor, pick_background_reactors,
    promotable_background_presences, _refuse_name_collision,
    promote_background_character, AUTO_PROMOTE_DIALOGUE_THRESHOLD,
    _promote_after_addressed, _auto_promote_enabled,
    auto_promote_background_characters)
from persist.commit_scene_state import (_anchor_current_room, sync_anchored_books,
    _guard_occupied_mover_removal, _advance_ground, prepare_scene_commit,
    commit_scene, _record_subject_last_seen, _dedupe_overlay_entries,
    _merge_overlays, _overlay_handles)
from persist.commit_mechanics import (commit_transit_sweep, commit_world_event_spine,
    commit_information_carriers, commit_cast_changes)
from persist.commit_memory import (RECENT_TELLS_CAP, _durable_dialogue_category,
    _cited_memory_ids, _marked_for_memory, _quote_body, _is_player,
    _salience_of, _own_sequence_memory, _inference_memory_text,
    _intent_names_term, _interior_relations_of,
    prepare_memory_commit)
from persist.commit_memory_write import (_consolidate_committed_memories,
    MEMORY_CONSOLIDATION_JOB_KEY, schedule_memory_consolidation,
    MEMORY_TENSION_JOB_KEY, schedule_memory_tension_pass,
    commit_memories)
# ---- end split facade ----

_COMMIT_LOCKS = weakref.WeakValueDictionary()
_COMMIT_LOCKS_GUARD = threading.Lock()

def _commit_lock(turn_id):
    with _COMMIT_LOCKS_GUARD:
        return _COMMIT_LOCKS.setdefault(turn_id, threading.Lock())

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
    from story.authored_events import mint_authored_events, resolve_authored_events
    cid = ctx.chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    # The MERGED committed diff -- `director_fanout` writes the merged
    # specialist output back to `state_diff` -- so the referent check reads
    # what the beat actually retired. Establish has none; `or {}` covers it.
    fired, requeued, dropped = resolve_authored_events(
        cid, ctx.turn.idx, str(res.get("resolved_event") or ""),
        state_diff=(res.get("state_diff") or {}))
    if requeued:
        ctx.add_warning(
            f"{requeued} authored future-event(s) not enacted this beat; "
            "re-queued to next turn rather than dropped")
    if dropped:
        ctx.add_warning(
            f"{dropped} authored future-event(s) can no longer be enacted "
            "(this beat retired what they name, or they went unresolved past "
            "the re-queue limit) and were marked stale")
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
    from world.offscreen import advance_epoch

    return advance_epoch(ctx, prepared_scene, transit_result)


def commit_offscreen_plans(ctx, prepared_scene):
    """Apply Director-adjudicated, character-grounded reactive plan ops."""
    from world.offscreen import apply_plan_ops

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
    from world import crowds as crowds_model
    from world.spatial import passable_neighbors

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
            # The same post-resolution scene and the same physical delivery
            # rules, but a different source: player/major-character conduct
            # licensed by exact dialogue/declarations rather than a fired
            # world-event surface.  It lands after ordinary carrier updates so
            # neither writer can be overwritten by the other's registry copy.
            _commit_domain(
                ctx, results, "charter_observations",
                lambda: commit_charter_observations(ctx, prepared["scene"]),
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

    # And the contradiction pass, on the same terms and for the same reason:
    # measured at 114s against a 24-row payload, which is not a cost a player
    # may be asked to pay for an annotation that is not a turn fact. UNBUILT
    # 2.24. A scheduling failure is a warning like its neighbour's -- the next
    # beat that mints anything asks again, so nothing here is lost, only
    # deferred.
    try:
        job = schedule_memory_tension_pass(ctx)
        results["memory_tension"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"memory tension scheduling failed: {exc}")
        results["memory_tension"] = {"error": str(exc)}

    # Autonomous background->cast promotion likewise runs after the primary
    # transaction: it mints a sheet with an LLM call and is additive and
    # forward-only (the new character becomes step-eligible next turn), so a
    # failure is a warning, never a turn rollback.
    try:
        results["promotions"] = auto_promote_background_characters(ctx)
    except Exception as exc:
        ctx.add_warning(f"auto-promotion failed: {exc}")
        results["promotions"] = {"promoted": [], "error": str(exc)}

    # Deterministic institution/upkeep catch-up rides the same committed
    # epoch as the character ticks. It is explicit-opt-in (a stored Charter
    # definition), model-free, frame-scoped, and lands incidents onto the
    # existing scheduled-event rail rather than inventing a delivery path.
    try:
        from world import charter_runtime as _charter_runtime

        job = _charter_runtime.schedule_charter_ticks(
            ctx, results.get("offscreen_epoch") or {})
        results["charters"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"charter scheduling failed: {exc}")
        results["charters"] = {"error": str(exc)}

    # Out-of-band offscreen ticks start HERE, after the turn's facts are
    # durable, and run in parallel with whatever the player does next. A
    # turn starting never cancels one: cancelling on turn-start would make
    # the world's progress depend on player idleness, which inverts the
    # feature (amendments section 4). Arrival is safe because every tick
    # write is provisional (section 5). Failure is a warning, never a
    # rollback -- and never silence.
    try:
        from world import offscreen as _offscreen

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
        from world import offscreen as _offscreen

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
        from story import artifacts as _artifacts

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

    # No "errors" key. It was hardcoded `[]` here, written by no domain and
    # read by nothing, and it could not have been anything else: a domain that
    # fails RAISES, and the outer transaction rolls the whole turn back rather
    # than returning a partial commit with a list of complaints. Publishing a
    # channel that cannot carry anything invites a caller to check it instead
    # of catching.
    return {
        "summary": (
            f"Committed turn {ctx.turn.idx}: "
            f"{len(results.get('memories', {}).get('committed', []))} "
            "memory writes"
        ),
        "results": results,
    }
