# Sonder Engine — 4-agent bug audit (consolidated)

Four parallel audits (pipeline/info-boundaries · commit/persistence/restore ·
API/import-export/providers/spatial · schema/ToM/prompts/frontend). ~30 substantiated
findings; deduped and ranked below. **[verified]** = confirmed against code by hand;
**[×2]** = independently found by two agents; **[our-run]** = corroborated by the demo run.
Already-fixed items (the 3 JSON coercions, concealed-speech `norm_sequence`, `chat_export`
resources) are excluded.

## CRITICAL

1. **Checkpoint blob keeps SOURCE frame ids → branch/import restore corrupts or destroys frames.** `[verified] [×2]`
   `_remap_cp_blob` (app.py:509-604) remaps memories/world-keys/char_frames but never
   `blob["frames"]` or `blob["chat_personas"]`. After a branch or cross-install import,
   deleting/rerolling a turn → `_restore_frames` (checkpoints.py:205-242) either PK-collides
   → 500 forever, or (if source deleted) DELETEs the branch's own frames → silent cross-era
   collapse. `chat_personas` re-attach with foreign frame ids.
   *Fix:* remap `blob["frames"][].id/parent_frame_id` and `blob["chat_personas"][].frame_id`
   through `frame_idmap` (drop unmapped).

2. **Interaction-loop micro-perception delivers concealed NPC speech to conceal-from parties (and into their memories).** `[verified]`
   `deterministic_micro_perception` speech branch (loops.py:47-60) checks only `hear_level` —
   the action branch (loops.py:62) correctly skips `visibility=="concealed"`, the speech branch
   never does. A concealed line reaches every in-earshot observer → next character step → outcome
   view → durable "heard" memory. Same class as the fixed leak, via a parallel channel the
   concealment tests don't cover. (Same invariant: **background_react** feeds the bystander the
   raw player declaration + full objective outcome unfiltered — HIGH, see below.)
   *Fix:* in the speech branch, skip observers in `conceal_from` / skip concealed lines except to
   legitimate recipients, mirroring the action branch + `norm_sequence` backstop.

## HIGH

3. **Branch/import never copy the normalized `world_*` tables → paradox false-fires + scene/table divergence.** `[×2]`
   `turn_branch`/`chat_import` copy frames/cast/turns/memories/lore/world-KV but not
   `world_entities/placements/conditions/scheduled_events/fiction_worlds/fiction_locations`
   (they're in the blob; `world_id_remap` already exists). A branched chat has empty world tables
   while `world.scene` + remapped `fixed_points` reference them → `_entity_exists`==False → a
   `required_exists` anchor fires a hazard paradox on the first commit. *Fix:* insert the six
   remapped `world_*` arrays inside the branch/import transaction; remap `fixed_points[].frame_id`.

4. **Sync retry classifier only knows `httpx`, but the pipeline runs on `requests` → transient network errors kill the turn.** `[verified] [our-run]`
   `_classify_error` (providers.py:377-386) → `requests.exceptions.ReadTimeout/ConnectionError/
   ChunkedEncodingError` become `retryable=False`. This is what killed our T29 (ChunkedEncoding)
   and T14 (RemoteDisconnected); only the harness resume saved them. *Fix:* classify the `requests`
   network exceptions as retryable.

5. **Configured fallback models are never used when the primary provider *errors* (only on invalid JSON).**
   `complete_validated_json` walks candidates only after *validation* failures; an `LLMError`
   (401/404/429-exhausted/500) from the initial `chat_complete` propagates out; an error mid-walk
   aborts remaining candidates. Async variant (which does iterate on errors) is dead code.
   *Fix:* catch `LLMError` (non-`Aborted`) around each candidate call and advance.

6. **Numeric bounds hard-reject instead of clamping (largest remaining coerce-vs-crash member).** `[verified-probe]`
   `RelationshipUpdate` deltas (±0.2), `MindHypothesis.confidence`, `urgency`, `salience`
   (schemas.py:724,734-736,743,762). A prompt-compliant "big betrayal" delta of 0.3 → strict fail →
   crash. `cap_mind_model_updates` already clamps but runs *after* strict validation. *Fix:* clamp
   in `preprocess_llm_output` for step `character`.

7. **`normalize_character_data`/accessors crash on non-numeric mood/temperature/stance.**
   `valence:null`, `temperature:"warm"`, `stance.trust:null` → TypeError/ValueError at import
   (500s the endpoint) or on `character_name()` **every subsequent turn** once the sheet is in the DB.
   *Fix:* tolerant `_float_or(value, default)` throughout character_schema.py.

8. **`refresh_checkpoint` replaces the PRE-turn checkpoint with POST-turn state.**
   Lorebook attach/detach after turn N re-snapshots the whole chat *post*-commit, so a later reroll/
   delete of turn N re-applies relationship deltas on top of the applied graph, keeps discarded
   `known`/lore/background bookkeeping, re-diffs the scene. `attach_lore` also skips `_require_chat_idle`.
   *Fix:* patch only the lorebook sections into the existing blob instead of full re-snapshot.

9. **Checkpoint restore never deletes lorebooks created after the snapshot → discarded-timeline lore contaminates canon.**
   `_restore_books` iterates only snapshot books; a turn that minted a child/vehicle book + entries,
   then gets rerolled, leaves the book + rolled-back entries alive; the rerun dedups to the stale book.
   `chats.lorebook_id` also not reset when the snapshot had no canon. *Fix:* delete chat-owned books
   absent from the snapshot; reset canon.

10. **`only_key` single-step reroll of a pre-commit stage runs against POST-commit state + this turn's committed memories.**
    Onset perception/character reroll sees the post-commit scene and `recent_memory_buffer` includes
    `turn_idx == current` → outcome knowledge bleeds into the onset declaration. *Fix:* restore the
    turn's checkpoint for any non-commit `only_key` after commit ran; exclude `turn_idx >= current`
    from `recent_memory_buffer`.

11. **`ctx.character_results` never rehydrated on resume → resumed turn silently drops character memories/mind-models/stances.**
    Loop results persist in step content but aren't copied back to `ctx.character_results`; commit/
    perception_outcome read it directly. Resume/reroll-commit → empty → no "I chose to…" memories, all
    `mind_model_updates`/`stance_updates` dropped, no warning. *Fix:* rebuild `ctx.character_results`
    from persisted `character_results`/`rounds` on hydration.

12. **`dialogue_log` alias keys crash director_resolve; plain-string lines silently deleted.** `[verified-probe]`
    `{"speaker","quote":...}` → `exact_quote: field required` → step fails; `["Barkeep: 'Aye.'"]` →
    preprocess drops it → validates with an EMPTY log → dialogue vanishes from narrator/memory. *Fix:*
    in the dialogue_log preprocess pass, alias-map `quote/text/line`→`exact_quote`, default speaker,
    coerce string lines.

13. **Export/import drops `chat_personas`, `turn_player_inputs`, `lorebook_links` (same shape as the resources bug).**
    Multiplayer roster + frame stations, pre-submitted co-player inputs, and the lore link graph are
    silently absent after import (`dump_lorebook_links` exists, imported, unused). *Fix:* export/import
    all three (frame_id remapped; extra-player personas in resources).

14. **`world_entities.created_turn_id/retired_turn_id` in blobs never remapped through the turn idmap.**
    `_remap_cp_blob` remaps strings only; import→restore INSERTs these ints → FK-fail aborts the whole
    restore (breaks recompute/delete), or silent cross-chat mis-attach in a branch. *Fix:* remap both
    columns through the turn idmap (null when unmapped).

## MEDIUM

15. Streaming parsers swallow mid-stream error events + treat premature close as success → truncated output committed as valid (providers.py:389-450).
16. `other_players.*.sequence` speech volumes never normalized → co-player line can go silently inaudible via `hear_level` (schemas.py:1091-1108); `other_players:null` hard-fails.
17. `FlowPlan.dice` requires actor/attempt/ability → one omitted key crashes all of director_interpret (advisory sub-field). *Fix:* default DiceSpec fields / drop incomplete.
18. `_asks_player` `?`-heuristic stops NPC↔NPC exchanges (a question to another NPC ends the loop as "awaiting player"); apply only when `addresses` is empty/player.
19. Second speaking round overwrites a character's first-round result → round-0 mind-model updates/actions lost at commit; merge per-character or iterate `rounds`.
20. `_strip_player_echo` runs *after* the fidelity check and can rewrite an NPC's verbatim quote → the ABSOLUTE violation the retry exists to prevent; skip quoted non-player spans, re-check post-strip.
21. `OUTPUT_EXAMPLES` missing `background_react`/incomplete `mapping_commit` → repair steered to `{}` → reaction/book_ops silently swallowed.
22. `snapshot_state` omits `anchor_entity_id` → vehicle-book anchoring lost on branch (book stops following the vehicle).
23. Provider/embedding calls can run inside `turn_branch`/`chat_import`'s outer write transaction (legacy blobs w/o vectors) → a hung provider stalls every write. Prepare embeddings before the transaction.
24. No `{{char}}/{{user}}` macro substitution at import → literal `{{user}}` renders to the player; heuristic import discards most card content; card-book `enabled:false` imported as active. (Ties into the greeting-import design.)
25. `turn_new` inserts the turn row before `_begin_pipeline_or_409` → a 409-losing request leaves a stepless orphan turn that then blocks the frame until manually resumed/deleted.
26. Spatial split fails open: zero-zone auto-merge (`detect_merge` when neither side is in a zoned room) grants permanent bidirectional memory visibility across light-years; NULL-`turn_idx` parent memories visible across an unmerged split.

## LOW

27. Frame ids validated for existence but not chat ownership (turn_new, chat_persona_station, fixed_points_create) → operate on another chat's frame.
28. Guest join-code redemption not atomically single-use (SELECT-then-UPDATE race → two tokens); `verify_host_login` 500s on non-ASCII username (`compare_digest` ASCII-only).
29. `interaction_loop` `delivered_views` appended to outcome views without dedup vs the dialogue_log injection → duplicated quotes in views + episode memories.
30. `_coerce_appearance` discards embodiment hair/clothing when a custom summary exists; `_normalize_latent` drops bare-string latents; ToM caps off-enum kinds inconsistently and keys mind-models by raw (case-sensitive) entity string.

---

### Cleared (checked, no finding)
Frontend rendering (all via `el()`/`textContent` — no XSS/collisions); `_commit_all_locked`
domain ordering + atomic outer transaction; `_stable_event_key`/`uq_memory_event` rerun idempotency;
`save_step` one-active-variant invariant; abort/contextvar/thread-local-DB correctness; ToM decay math;
paradox per-frame slots + tick ownership; candidate_offset walk; normalize round-trip idempotence.
