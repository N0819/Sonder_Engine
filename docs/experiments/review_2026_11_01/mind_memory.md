# Audit — the memory subsystem (`mind/memory*.py`), 2026-11-01

Auditor: mind_memory. Working tree at `84f3de23` (branch `worktree-jev-character-tracking`), read-only.
Verification scripts (scratch databases only, never `engine.db`):
`<review scratch>/memaudit/verify1.py` … `verify5.py`, `deadscan.py`.
Live-corpus numbers come from `engine.db` opened `mode=ro`.

## Scope read

Read in full, every line:

- `mind/memory.py` 1-154 (facade)
- `mind/memory_common.py` 1-293
- `mind/memory_read.py` 1-471
- `mind/memory_write.py` 1-989
- `mind/memory_retrieval.py` 1-1248
- `mind/memory_context.py` 1-898
- `mind/memory_jev.py` 1-603
- `mind/memory_routes.py` 1-670
- `mind/memory_links.py` 1-289
- `mind/memory_time.py` 1-350
- `mind/memory_judge.py` 1-430
- `mind/memory_inference.py` 1-159
- `mind/memory_snapshot.py` 1-1005
- `mind/memory_vectors.py` 1-789
- `mind/memory_lore_entries.py` 1-867
- `mind/memory_relationships.py` 1-457
- `mind/memory_lorebooks.py` 1-583
- `mind/memory_summaries.py` 1-765
- `docs/design/SPLIT_MEMORY.md` (all), `docs/experiments/AUDIT_MEMORY.md` (all)

Read in part, to trace callers or check a claim (not audited as a whole):
`core/db.py` 420-432, 790-1050 (memories/FTS/summaries schema); `core/frames.py` 1-60, 164-280;
`llm/providers.py` 5306-5311, 5705-5849 (embedding fallback and coalescing);
`persist/commit_memory.py` 765-880, 2370-2392 (about tags, relationship ops); `persist/commit_memory_write.py` 285-385;
`persist/commit_common.py` 25-60; `persist/commit_mapping.py` 640-730; `persist/checkpoints.py` 1110-1128, 1720-1772;
`persist/chat_delete.py` 1-45; `agents/character.py` 1750-1840, 3830-3895, 3990-4045; `agents/common_cast.py` 129-160;
`agents/runtime.py` 1580-1645; `world/offscreen.py` 1640-1800, 2225-2265; `story/importers.py` 3040-3140;
`web/app.py` 180-250, 357-400, 3825-3848, 4170-4215, 4740-4790, 6630-6670; `static/js/chat.js` 3040-3160 (memory panel);
`language_runtime/__init__.py` 565-770; `tests/test_memory_read_seam.py` 1-110, 240-320;
`docs/guides/MEMORY.md` (grepped, ~25 claims read in place); `AGENTS.md` 993-1030, 538.
Other auditors' reports read for overlap: `persistence_paths_schema.md` (F4, F22, efficiency), `persist_background_memory.md` (E4),
`web_app.md` (E1, F15), `llm_providers_quality.md` (registered parse cut-off).

Focused test run (1 of the ~6 allowed): `tests/test_memory_read_seam.py` → 34 passed (but see F19: one of its guards is inert).

## Status of the recorded findings (AUDIT_MEMORY.md, SPLIT_MEMORY.md § Defects noticed)

| item | status now | evidence |
|---|---|---|
| SPLIT defect 1 / AUDIT 1.1 `_kw_scores` discards BM25 | **FIXED** | `memory_common.py:224-232` returns `-bm25/best`; also scoped to readable books (A59, `:218-222`) |
| SPLIT defect 2 / AUDIT 1.2 `search_lore` compares by width only | **FIXED**, residual | model key AND width (`memory_lore_entries.py:518-521`) with a NULL-stamp carve-out; live NULL-stamped lore rows 840 → 146. Residual: no crc32 refusal (F10) |
| 1.3 stopword-grade cue material | **FIXED** (mint + stock + scorer) | `_junk_cue` (`memory_write.py:84-107`), quote-initial rule (`:157-168`); exact list admits only ≥0.8 and caps at 60 (`memory_retrieval.py:698-700`). Live: 1 of 17,463 rows carries a junk key phrase, 0 a junk entity |
| 1.4 `record_dispute` stamps every gist hit | **STILL LIVE**, unregistered | `memory_read.py:334-342` unchanged; `MEMORY.md:1631-1634` still claims "accepted only when it resolves unambiguously". Legacy gist path only (the ref path is primary). It also reads rows with no frame/turn filter, so a gist can dispute another era's row |
| 1.5 `kind` vocabulary not enforced | **FIXED** | `memory_write.py:432-436`, `repair_memory_kinds`; live kinds = dialogue/episodic/inference/semantic only |
| 1.6a `_exact_cue_score` computed 3x | **FIXED** | `memory_retrieval.py:661-662` |
| 1.6b upsert UPDATE resets `archived=0` | **STILL LIVE, and wider** | see F7 — it also wipes importance, dispute, feelings, about, supersedes |
| 2.1 MEMORY.md §9 "not called at startup" | **STILL STALE** | `MEMORY.md:1305` vs `web/app.py:190-238` |
| 2.2 "access_count is bumped for everything returned" | **STILL STALE** | `MEMORY.md:67, 855-856`; the write is now `record_memory_access` from commit (A78) |
| 2.3 mood-congruence formula reads raw valence | **STILL STALE** | `MEMORY.md:773` vs `_congruence_valence` (`memory_retrieval.py:386-414`) |
| 2.4 "four stuck signals" | **STILL STALE** | `MEMORY.md:882`; `barren_goal` at `agents/character.py:1642` |
| 2.5 salience formula without length cap | **STILL STALE** | `MEMORY.md:118` |
| 2.6 `_is_empty_view` "two placeholders" | **STILL STALE** | `MEMORY.md:124-125` vs per-pack markers (`memory_summaries.py:359-394`) |
| 2.7 consolidation "in a thread pool" | **STILL STALE** | `MEMORY.md:243` |
| 2.9 archiving "salience < 0.72" | **STILL STALE** | `MEMORY.md:1011` vs `max(salience, effective_importance)` (`memory_summaries.py:725-726`) |
| 2.11 SPLIT note 1 wording | **FIXED** | SPLIT_MEMORY.md now carries the correction |
| 2.12 / 3.4 legacy salience-1.0 seeds, UNBUILT §1.16 | **RESOLVED** | 0 live rows at salience ≥0.99, turn ≤1; §1.16 gone from the registers |
| 3.3 "the player" residue | **STILL LIVE (data)** | 49 rows; a data repair the owner has not chosen |
| 4.3 abstention floor | built, then retired | `recall_confidence` is probe-only (UNBUILT_CHARACTERS §1.76); `memory_judge` replaced it |

## Findings

### F1 — Summaries are not frame-scoped: a native in a past frame is handed the present era's autobiography
- **Severity:** LEAK. **Confidence:** CONFIRMED (reproduced).
- **Where:** `mind/memory_summaries.py:58-61` and `:101-108` (the two summary readers filter chat/char/scope and `end_turn_idx < before` only); `mind/memory_context.py:250-254` (`_origin_on_drift`), `:352-353`, `:400-401`, `:606-609`. `memory_summaries` has no `frame_id` column (`core/db.py:1012-1035`).
```python
row = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
        "AND scope=?" + cutoff_sql +
        " ORDER BY end_turn_idx DESC, id DESC LIMIT 1", tuple(args), one=True)
```
- **Scenario:** turns 1-5 played in the present; consolidation (present-only, `:754-756`) writes "I watched the city fall to the invaders and fled north" with an unresolved thread. The host opens a past frame (ordinal -1, "ten years earlier") and plays turn 10 there. `visible_memory_rows` correctly hides every present-era row from the native (`is_memory_visible`, ordinal 0 > -1), but `build_character_memory_context` still delivers `autobiographical_summary`, `unresolved_from_past.items`, `earlier_in_my_life`, `where_i_came_from` and the hearsay/surmise summaries — the younger self knows how the city fell. The `when` stamp degrades to "at a time you cannot place against now", which marks the leak rather than stopping it.
- **Verified:** `verify1.py` T1 — from the past frame: 0 visible raw rows, 0 recent, 0 recalled, `autobiographical_summary = 'I watched the city fall to the invaders and fled north.'`, `unresolved_from_past.items = ['whether my brother survived the fall']`. Not in any register.
- **Fix (class):** summaries are derived from frame-visible rows, so gate them by the same rule: stamp each window with the frame it was consolidated in (always the present today) and filter readers with `is_memory_visible(char_id, window_frame, viewer_frame, end_turn_idx)`, or have `build_character_memory_context` drop every summary lane when `viewer_frame` is not the present and the mind is not a traveller. **Test:** the T1 setup as a pytest — summary in the present, past frame active, assert every summary key is absent.

### F2 — The off-screen character agent reads its memories with raw SQL: no frame rule, no turn cutoff
- **Severity:** LEAK (frames chats). **Confidence:** CONFIRMED by reading (outside my file scope; question 1 of the brief).
- **Where:** `world/offscreen.py:1699-1704`, called from `:2254` with `frame_id=frame_id, turn_idx=turn_idx`, both ignored by the read.
```python
for r in q("SELECT content, turn_idx FROM memories "
           "WHERE chat_id=? AND char_id=? AND archived=0 "
           "ORDER BY turn_idx DESC LIMIT 12", (cid, char_id)) or []
```
- **Scenario:** a native played in a flash-forward (frame ordinal +1) at turns 50-60, back in the present at 61. An off-screen tick for that mind in the present takes its 12 newest rows by play order — the flash-forward's — into the `character_agent` call. That is the "how did he know that" failure `agent_context`'s own docstring names. The same function filters `mind_models` by frame (`:1733-1747`); only memories bypass it. Every other mind-facing memory read goes through `visible_memory_rows`.
- **Fix:** `visible_memory_rows(cid, char_id, before_turn_idx=turn_idx+1, viewer_frame_id=frame_id, include_archived=False)`, newest 12. **Test:** a flash-forward row plus a present row; assert `agent_context(..., frame_id=None)["memories"]` holds only the present one.

### F3 — Host memory edit and delete address a row by id, and every reroll re-mints the chat's ids
- **Severity:** CORRUPTION, and LEAK when the id now belongs to another mind. **Confidence:** PLAUSIBLE (traced; needs a memory panel loaded before a reroll).
- **Where:** `mind/memory_read.py:247-290` (`update_memory`: SELECT by `mid`, a provider round trip at `:274`, then `UPDATE … WHERE id=?`), `:468-470` (`delete_memory`); routes `web/app.py:6641-6665` pass only `mid`; the panel (`static/js/chat.js:3111, 3141, 3153`) sends the id it rendered.
- **Scenario:** the panel lists Mara's memories (ids 101-140). The host rerolls the turn: `apply_chat_memory_restore` deletes the chat's bank and re-inserts it in dump order (`memory_snapshot.py:491-505`, NULL turns last, then turn, then id). `memories.id` has no AUTOINCREMENT, so when the active story holds the table's highest ids (the usual case) the same ids are handed out again in an order that need not be the original one: NULL-turn rows move last, and rows written out of band land where their turn sorts. The persistence auditor's r7 repro shows the swap on the first restore. Otherwise the stale id names nothing and the edit 404s. The host then saves an edit to "id 117". `update_memory` rewrites row 117's kind, provenance, content, gist, cues and vectors with Mara's edited text, while that row's `char_id`, `event_key`, `turn_idx` and `frame_id` stay Bram's: Bram now remembers Mara's moment. A delete removes the wrong memory. Even without a stale panel, the edit's own embed window (`:274`) can straddle a restore. The repo states the rule this breaks (`memory_read.py:316-319`, `:402-404`: "never by row id -- checkpoint restore is delete-and-reinsert").
- **Fix:** address host edits by `(chat_id, char_id, event_key)` (every row has one after `backfill_missing_memory_event_keys`), or compare-and-set on the content the panel showed (`WHERE id=? AND content=?`), and 409 on a miss. **Test:** list memories, restore a checkpoint, PUT with a pre-restore id; assert 409 and no other row changed.

### F4 — `knowledge_for_character` hands every local-range lore entry to a mind with no room
- **Severity:** LEAK (narrow). **Confidence:** CONFIRMED (reproduced).
- **Where:** `mind/memory_lore_entries.py:850-859`.
```python
if range_type == "local":
    ...
    if char_room and char_room not in locations:
        continue
```
- **Scenario:** `char_room` is `None` whenever `character_room` cannot place the sheet (`agents/common_cast.py:129-153`), and `agents/background.py:1245` passes `room_id or None`. The guard is skipped and every local entry ("the cellar door sticks", tagged `common`, local to `cellar`) is delivered. The docstring's rule is "Local knowledge is knowledge you have because of where you ARE"; a mind that is nowhere qualifies for all of it. `tests/test_lore_knowledge_gate.py` covers `None` only for global entries.
- **Verified:** `verify1.py` T11 — room `None` → `['Cellar']`; room `hall` → `[]`.
- **Fix:** `if not char_room or char_room not in locations: continue`. **Test:** a local entry with places, `char_room=None`, assert `[]`.

### F5 — `update_lore` clears the gate fields whenever a caller omits them, and crashes on a list
- **Severity:** CORRUPTION (an entry silently becomes Director-only), CRASH. **Confidence:** CONFIRMED (reproduced).
- **Where:** `mind/memory_lore_entries.py:169-174`: `title`, `knowledge_tag`, `knowledge_range`, `knowledge_locations` are always SET, so `None` means "clear". `category`, `importance`, `aliases`, `scope`, `relations`, `circles`, `source_notes` are conditional, so `None` means "leave" (`:176-198`). `knowledge_locations` is bound raw, while `add_lore` serializes it (`:143`).
- **Scenario:** `persist/commit_mapping.py:705-712` (the live authoring-package path) passes `knowledge_tag=o.get("knowledge_tag")`. An update op that rewords content without restating the tag sets `knowledge_tag=NULL`, which `knowledge_for_character` reads as "reaches no mind" (`:826-831`). Every character that knew the fact loses it, and nothing warns. `story/importers.py:3110-3124` passes the plan's `knowledge_locations` list raw, and sqlite raises `ProgrammingError: Error binding parameter 7: type 'list' is not supported`.
- **Verified:** `verify2`/`verify1.py` T2 — after `update_lore(eid, keys, content)`: title, tag, range, locations all `None`. A list raised the `ProgrammingError` above.
- **Fix:** one convention: `None` = leave, an explicit sentinel = clear, and `_storage_json` on the two list fields as `set_lore_overlay` does (`:392-393`). **Test:** update with only keys/content, assert the tag survives; update with a list, assert stored JSON.

### F6 — A lorebook restore cannot roll back a compartment change
- **Severity:** CORRUPTION (rollback not faithful). **Confidence:** CONFIRMED (reproduced).
- **Where:** `mind/memory_snapshot.py:962-975` passes `circles=entry.get("circles")` to `update_lore`, whose `if circles is not None` (`memory_lore_entries.py:193-195`) treats the snapshot's NULL (inherit the book) as "leave unchanged".
- **Scenario:** at turn N an authoring package or a host edit gives an entry `circles=["order"]`. The host rerolls turn N. `_restore_books` → `restore_lorebook` restores everything except the compartment, so the fact stays secret (or stays public) in the timeline that never had the change.
- **Verified:** `verify1.py` T3 — circles `["order"]` before and after restoring the pre-edit dump.
- **Fix:** write circles verbatim on restore (the F5 sentinel, or a direct `UPDATE … SET circles=?`). **Test:** dump, change circles, restore, assert NULL.

### F7 — Re-minting an existing `event_key` wipes the mind's later history of that memory
- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (reproduced). AUDIT 1.6 recorded only `archived=0`.
- **Where:** `mind/memory_write.py:770-779`. The UPDATE arm writes `importance`, `disputed`, `feelings`, `about`, `supersedes` from the new `data`, and `prepare_memory` defaults them to `None`/`""` (`:478-499`), plus `archived=0`.
- **Scenario:** keys that are not turn-scoped are minted by `world/charter_promote.py:209-371` (`acquaintance:…`, `service:…`, `accused:…`), `story/greetings.py:338`, `story/journey_history.py:379-407`, `world/charter_history.py:795-842` and `persist/commit_background.py:5234`. When one of those writers runs again for the same mind, the row's revised importance, the mind's re-readings (the addendum history `record_dispute` exists to preserve), its kept feelings and its `supersedes` links reset to nothing. A minted-out turn is also un-archived.
- **Verified:** `verify4.py` — importance 0.76 → `None`; `disputed` `{"reading": "It was Oren in disguise.", …}` → `""`.
- **Fix:** on the UPDATE arm, keep the earned columns (`COALESCE(?, importance)`, keep `disputed`/`feelings` unless the caller supplies them; restore passes them explicitly, so it stays verbatim). **Test:** mint, `raise_importance`, `record_dispute`, re-mint the same key, assert both survive.

### F8 — Deleting a character leaves its rows in the FTS mirror: 1,419 orphans (7.5%) in the live index
- **Severity:** CORRUPTION (two representations disagree), PERF. **Confidence:** CONFIRMED (live count plus reproduction).
- **Where:** `web/app.py:3845-3848` (`char_del`) relies on the `memories.char_id … ON DELETE CASCADE`; `memory_retrieval_fts` is an FTS5 table with no trigger and no FK (`core/db.py:1001-1010`). `persist/chat_delete.py:36-38` cleans it for a chat; nothing cleans it for a character.
- **Live:** 18,882 FTS rows against 17,463 memories. All 1,419 orphans belong to characters that no longer exist, in chats that still do (chats 10, 12, 22, 38, 84, …). `verify4.py`: after `DELETE FROM characters`, memories 0, FTS 1.
- **Consequence:** every lexical MATCH and every §1.172 scan pays for the dead rows. If SQLite reuses the deleted character's id (max rowid + 1) for a new character attached to the same chat, the orphans match its `char_id` string and take lexical slots in `memory_net`/`search_memories`.
- **Fix:** `DELETE FROM memory_retrieval_fts WHERE char_id=?` beside the character delete (as `chat_delete` does for chats), or an `AFTER DELETE ON memories` trigger once §1.172's rowid keying lands, plus a one-shot sweep. **Test:** add a memory, delete the character, assert no FTS row.

### F9 — One `confidence` column, reconciled from each frame's own mind-models
- **Severity:** CORRUPTION (narrow: frames chats with beliefs). **Confidence:** PLAUSIBLE (traced).
- **Where:** `mind/memory_inference.py:122-158` selects every inference row of the mind (any frame) and rewrites `confidence` from the `state` it is handed. `persist/commit_memory_write.py:367-373` hands it the committing frame's state (state is frame-isolated via `chat_char_frames`).
- **Scenario:** a belief formed in the present is restated in a flash-forward, whose mind-models then decay it. That commit demotes the present-era row. Back in the present, recall ranks it on the flash-forward's credence until a present commit happens to reconcile again. The mechanism is symmetric: flash-forward inferences are "abandoned" by every present commit.
- **Fix:** reconcile only rows visible from the committing frame (`visible_memory_rows`), or keep confidence per frame. **Test:** two frames with diverging mind-models; assert a commit in one leaves the other frame's rows untouched.

### F10 — `search_lore` ranks on crc32 hash vectors, the signal the memory lanes refuse
- **Severity:** WRONG-SCENE (lore handed to the world compiler, Director and Room). **Confidence:** CONFIRMED (reproduced on no-provider; transient case traced).
- **Where:** `mind/memory_lore_entries.py:469-527`. Compatibility is `len(qv)==len(vec) and (stamp == _batch.model_key or stamp is None)`, and there is no `fallback` check. `search_memories` (`memory_retrieval.py:638`), `contrast_memory` (`:1127`), `recall_confidence` (`:1001`) and `memory_net` (`memory_jev.py:218`) all refuse a fallback batch (CRC32_CONTROL §8: ranking on the hash scored 289/470 against 338 with no vector at all).
- **Scenarios:** (a) every install with no embeddings provider: the batch is `cheap:crc32:256`, `fallback=True`, the rows carry the same stamp, so the 0.65 term is hash cosine (`verify4.py`). (b) With a provider, during a rate-limit window: lore written in that window is stamped `cheap:crc32:256` and queued for repair, the query falls back to the same stamp, those rows rank on hash noise at 0.65, and every real row scores 0.0. The outage that strands rows is the same outage that makes queries fall back, so the two co-occur. Each such call also logs "Re-embed to restore them" with no once-per-situation dedupe.
- **Fix:** mirror `search_memories`: `rank_by_vector = not _batch.fallback`, and keyword only otherwise. **Test:** a monkeypatched fallback batch plus a crc32-stamped row; assert it gains no vector term.

### F11 — The embedding repair backs off after rounds that SUCCEED
- **Severity:** SILENT-NOOP (partial). **Confidence:** CONFIRMED (simulation).
- **Where:** `mind/memory_write.py:613-624`. Each round repairs at most 32 ids per table (`repair_pending_embeddings(batch=32)`), and `delay` doubles after every round, whatever the outcome.
- **Measured** (`verify3.py`, provider healthy, every round fixing its 32): a 200-row backlog takes 7 rounds and 1,350 s (22.5 min). A 500-row backlog (`queue_fallback_rows_for_repair`'s limit on chat open) uses all 12 rounds over 2,850 s and leaves 116 rows queued with no thread. Rows stay keyword-only throughout, and new memories minted meanwhile join the tail. If the pass raises (e.g. `database is locked`), the thread exits (`:618-620`) and nothing restarts it until another failure is noted or the chat is reopened.
- **Fix:** reset the delay (or loop at once) when a round fixed something; back off only on a fallback or empty round. **Test:** the `verify3.py` harness as a test; assert the delays after a productive round stay at `_REPAIR_DELAY`.

### F12 — `search_memories`' keyword list is not seam-filtered; the net's is
- **Severity:** WRONG-SCENE (ranking only; nothing outside the seam is delivered). **Confidence:** CONFIRMED (mechanism), impact PLAUSIBLE.
- **Where:** `mind/memory_retrieval.py:30-40` filters FTS by chat/char only (no frame, turn cutoff or archive filter). `:658` and `:705` feed those ids straight into RRF. `memory_jev.py:244-245` filters the same list with `if mid in memories` and widens the limit.
- **Scenario:** other-era rows (and archived rows when `include_archived=False`) take some of the 60 lexical slots, and in-scope rows get worse RRF ranks than their BM25 earns. `verify1.py` T6: 5 future-frame ids in a 6-id lexical list for a present-frame search. Production callers are the resurfaced lane, the tension pass and the author's search route.
- **Fix:** filter `lex_rank` to `memories` as `memory_net` does (one line).

### F13 — Three of the net's lanes break ties toward the oldest row
- **Severity:** WRONG-SCENE (bias). **Confidence:** CONFIRMED (mechanism), impact PLAUSIBLE.
- **Where:** `mind/memory_jev.py:276-279`: `valence_match` sorts `(gap, mid)` and `valence_contrast` sorts `(-gap, mid)`, so a tie block is ordered oldest first in BOTH lanes. `_ranked` (`:189-191`) does the same for the importance lane.
- **Scenario:** legacy banks with flat `encoding_valence` (chat 38, char 32: 99 of 111 rows at exactly 0). All 99 tie, and the oldest gets ~2/31 from the two valence lanes while the newest gets ~2/130, a two-lane "oldest first" ranking with no design behind it. Modern banks tie in blocks of ≤17, so the bias is small there.
- **Fix:** break contrast-lane ties by `-mid`, or give tied rows the mean rank.

### F14 — `retrieved_ids` omits the asked and resurfaced lanes, so the unbidden lane can return one of them
- **Severity:** WRONG-SCENE (minor). **Confidence:** CONFIRMED by reading.
- **Where:** `mind/memory_context.py:822-824` builds `retrieved_ids` from `recent`, `recalled` and `pondered` only. `agents/character.py:4024-4034` excludes exactly that set from `contrast_memory`.
- **Scenario:** a row delivered under `asked_recall` or `resurfaced_without_asking` can be re-delivered the same beat as an unbidden memory, labelled "came back on its own".
- **Fix:** include `asked_rows` and `resurfaced_rows` in `retrieved_ids`.

### F15 — Japanese: the keyword leg sees only extracted key phrases, dialogue rows never match, and the lore keyword term is always zero
- **Severity:** SILENT-NOOP (language pack). **Confidence:** CONFIRMED (reproduced).
- **Where:** `core/db.py:1001-1010` indexes `memory_retrieval_fts` with `unicode61`, which keeps an unspaced Japanese run as ONE token up to the next punctuation. `_memory_fts_query` (`memory_retrieval.py:21-28`) builds pack tokens (kanji or katakana runs). Lore uses `_fts_query` (`memory_common.py:182-184`), whose regex is `[A-Za-z0-9]{3,}`, over `lore_fts` (`core/db.py:423-425`, default tokenizer).
- **Measured:** `verify2.py`/`verify5.py`. An episode row is reachable only because its extracted key phrases are pack tokens joined by spaces (`["オレン 古","古 地図",…]`). The content and gist columns never match. A durable dialogue row, minted with `key_phrases=[whole quote, speaker]` (`persist/commit_memory.py:1259`), is unreachable: query `"灯台" OR "鍵"` returns `[]` while the English twin returns its row. Lore: `_kw_scores("lore_fts", "古い地図はどこ")` returns `{}`, so a Japanese story ranks lore on 0.65·cosine alone. Coverage is the top 12 extracted phrases per row against full text in English. The comment at `memory_write.py:24-28` records that the QUERY side was fixed for Japanese; the index side was not.
- **Fix (class):** index the pack's own segmentation, writing `" ".join(_WORD_RE.findall(text))` into the FTS columns (memories and lore), or use `tokenize='trigram'` for unspaced scripts; route `_fts_query` through the pack regex. **Test:** a Japanese dialogue row plus a query sharing one kanji word; assert a lexical hit.

### F16 — `without_names` is English-only: Japanese questions keep the name, or gain "them"
- **Severity:** SILENT-NOOP / WRONG-SCENE (language pack). **Confidence:** CONFIRMED (reproduced).
- **Where:** `mind/memory_jev.py:160-173` (`(?<!\w)…(?!\w)` boundaries; English "them"/"their"/`'s`), used by the about lane (`:299`) and `memory_routes._subject_lane` (`:338`). `named_in` beside it was fixed for unspaced scripts on 2026-10-06; this function was not.
- **Verified** (`verify2.py` T8): "オレンに初めて会ったのはいつ？" comes back unchanged, so the measured 48th → 15th gain does not apply. "初めて会ったのはオレン・ダスク" becomes "初めて会ったのはオレン・them". English: "When did I first meet them?" (correct).
- **Fix:** strip by the same in-place rule `_stands_in` uses for unspaced scripts, replacing with a pack pronoun (or simply deleting the name). **Test:** Japanese question plus known name, assert the name is absent.

### F17 — Every remembered row's "when" is an English phrase, whatever the story's language
- **Severity:** WRONG-SCENE (language pack). **Confidence:** CONFIRMED by reading.
- **Where:** `mind/memory_time.py:61, 66, 85, 131-182` ("just now", "about 3 minutes ago", "between about 4 and 9 minutes ago", "before this story's recorded turns", "at a time you cannot place against now"), stamped on every delivered row (`memory_context.py:122`, `agents/character.py:1695`) and on summary citations. The `in_time` mark on the same rows IS localised (`memory_routes.in_time_text` → `character_tools_text`). Not registered.
- **Fix:** move the ladder's phrases into the pack (units and templates), as `in_time_*` already are. **Test:** a Japanese clock stamp contains no ASCII letters.

### F18 — Promise cues are substring-matched: "disagreed" boosts every promise memory
- **Severity:** WRONG-SCENE (minor). **Confidence:** CONFIRMED (string test).
- **Where:** `mind/memory_retrieval.py:799-803`, `any(t in query_text.lower() for t in _ling("_PROMISE_QUERY_CUES"))` with en cues `promise, promised, swore, vow, agreed`. "agreed" matches inside "disagreed", "promise" inside "compromise", "vow" inside "vowel". Each hit adds +0.1 to every promise-category row and appends the reason without dedupe. This is the bare-substring class fixed once in `_durable_dialogue_category`.
- **Fix:** word-boundary match through the pack word regex (`_WORD_RE` tokens ∩ cues), hoisted out of the per-row loop.

### F19 — The cross-character reader guard has scanned nothing since the split
- **Severity:** DEAD (inert guard), STALE-DOC. **Confidence:** CONFIRMED.
- **Where:** `tests/test_memory_read_seam.py:270-306`. `_top_level_functions()` parses `inspect.getsource(memory)`, and `mind.memory` is a facade with ZERO function definitions, so `unlisted` is always `[]`. `docs/guides/MEMORY.md:614-615` still says "a test fails if an unlisted cross-character reader appears".
- **Verified:** AST of the facade has 0 defs. The same predicate run over the seventeen `mind/memory_*` modules flags `memory_snapshot.backfill_memory_vectors` and `_dump_vector_addresses`, both maintenance readers that need listing. It does not catch F1 or F2: the regex only knows `char_id=?`, not frame or turn scoping, and does not look outside `mind/`.
- **Fix:** iterate the modules the facade imports from (or `mind/memory_*.py`), assert the scanned set is non-empty, and list the two maintenance readers. Consider a second predicate for frame scoping on mind-facing reads.

### F20 — `memory_routes.routed_ponder` has no caller; `jev_ponder_packet` re-implements it inline
- **Severity:** DEAD. **Confidence:** CONFIRMED (repo-wide identifier scan: one occurrence, its definition; not exported by the facade).
- **Where:** `mind/memory_routes.py:650-670` versus `mind/memory_jev.py:515-568` (the same route → answer → record flow, with `route_soon` and the floors). Two copies of one flow, one of them never run.
- **Fix:** delete it, or make `jev_ponder_packet` call it.

### F21 — `update_relationships_from_inference` is reachable only from legacy output, and when it runs it reads "untrustworthy" as trust
- **Severity:** DEAD (in production), WRONG-SCENE when a legacy result is re-committed. **Confidence:** CONFIRMED.
- **Where:** `persist/commit_memory.py:2382-2385` calls it only for `inference_updates`, which no schema emits (`agents/common_beat.py:238-243`: "legacy inputs commit still reads"). In `mind/memory_relationships.py:217-224` the cues are substring-matched with "trusting" checked first. "She is untrustworthy and dangerous." hits `trustworthy` and gains +0.1·confidence trust; "He is not dangerous after all." reads wary.
- **Fix:** delete the legacy branch (and `_TRUST_INFERENCE_*`), or route legacy conclusions through `mind_model_updates` as `_normalize_character_output` already does.

### F22 — MEMORY.md still carries the audit's doc drift, plus new drift
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- Unapplied from AUDIT_MEMORY §2 (lines in `docs/guides/MEMORY.md`): `:243` thread pool, `:67` and `:855` access-count writer, `:773` congruence on raw valence, `:882` four signals, `:118` uncapped salience, `:124-125` two empty-view markers, `:1011` archiving on salience, `:1305` "not called at startup", `:1631-1634` dispute "unambiguously".
- New: `:858` heading `_RECALL_LIMIT = 16` (code 30, `memory_retrieval.py:330`); `:614-615` the HOST_SCOPE guard (F19). In code: `memory_retrieval.py:332` "the number above stops at 16"; `memory_inference.py:3-4` "the note … about the rebuild above" (no rebuild is above; the split plan said to keep the essay with the vector code); `web/app.py:4757` "Two COUNTs" (a provider probe, six COUNTs and four fallback scans); `AGENTS.md:995` "thirteen siblings" (the facade imports sixteen; `memory_jev`, `memory_links`, `memory_routes` are missing from the table at `:1006-1020`).

### F23 — A transient query fallback is reported as a stranded bank
- **Severity:** STALE-DOC (misleading diagnostics). **Confidence:** CONFIRMED by reading.
- **Where:** `memory_retrieval.py:642-655`. With a provider configured and the query batch fallen back, every row is "incompatible", and `_warn_stranded_embeddings` logs "N of N stored memories … were embedded by a different model than the live one (cheap:crc32:256) … Re-embed". The live model is fine, so the advice is a whole-bank rebuild for a 429. `search_lore`'s "Re-embed to restore them" (`memory_lore_entries.py:531-536`) fires per call.
- **Fix:** when `embedded.fallback`, say "the query embedding fell back" and do not count rows as stranded.

## Efficiency

**E1. The keyword lane scores the whole database's matches on every call. Hot: 1-4 calls per character per beat, plus the tension pass.** `_lexical_memory_ranking` (`memory_retrieval.py:35-37`) runs `MATCH` over all chats and filters `chat_id/char_id` after (both UNINDEXED). Measured read-only on `engine.db` (18,882 FTS rows): a typical view query matches **13,351 rows DB-wide (71%)** and the filtered call costs **53-57 ms warm, 102 ms cold**. Callers: the recall net, the ponder net, the asked net, the resurfaced search, the tension pass (`memory_net` asks with `limit=len(bank)`). The cost grows with every story in the database, the read-side twin of §1.172. **Gain:** ~50 ms → a few ms per call with a scope token column (`scope MATCH 'c64_35'` intersected by FTS) or a per-chat index. F8's orphans are 7.5% of the scanned set.

**E2. Sequential embedding round trips per character beat.** The main batch is one call (`memory_context.py:440-441`), but the ponder (`:546`), asked (`:577`), about-lane (`memory_jev.py:301`), routed subject lane (`memory_routes.py:338`, the SAME stripped string as the about lane when one person is asked about), resurfaced search (`:781`, no `embedded=`) and contrast (`memory_retrieval.py:1119`, no `embedded=` parameter) each issue their own request. That is up to 7 serial requests on a beat where every lane fires. The coalescer only merges concurrent callers (`llm/providers.py:5705-5726`). The ponder/asked/resurfaced texts are known before the main call. **Gain:** 3-5 fewer round trips on such beats, and fewer requests against the ~3-request bucket whose 429s are what strand rows on crc32.

**E3. Chat open scans every memory of the chat through its blob overflow pages.** `queue_fallback_rows_for_repair(cid)` plus `embedding_bank_status` on every `chat_get` (`web/app.py:4772-4784`). `embedding_model` sits after two ~10 KB blobs and no index covers it. Measured: **0.45 s cold, 15 ms warm** for a 1,000-row chat (EXPLAIN: `SEARCH memories USING INDEX idx_memories_event_key (chat_id=?)` then a row read). **Gain:** a partial index `ON memories(chat_id) WHERE embedding_model='cheap:crc32:256'` makes the repair adoption O(failed rows). (The probe's network round trip is web_app E1 / persistence P3.)

**E4. The same bank is parsed once per lane.** The bank memo caches raw rows (`memory_read.py:132-149`), but `_row_memory` (six `json.loads` per row: key_phrases, entities, disputed, feelings, about, supersedes) runs again in each of `memory_net` (recall net, ponder net, asked net), `search_memories` (resurfaced), `contrast_memory`, and `pull_successors` (`_supersedes_of` per row). That is ~24 parses per row per character beat on a pondering beat. **Gain:** memoise the parsed dicts in the same bank memo. Linear, cheap to fix.

**E5. Two rebuild threads can start at once.** `start_rebuild_if_needed` (`memory_vectors.py:748-787`) checks `running` and releases the lock. The new thread sets `running=True` only after its own provider probe (`:713-719`). A reroll inside the startup reconcile window starts a second rebuild over the same stale rows, doubling provider spend (same vectors, so no corruption). **Gain:** set `running` before starting the thread.

**E6. Belief reconciliation inside the commit's write lock** (persist_background_memory E4): `memory_inference.py:122-158`. The selected columns sit before the blobs, so the scan is cheap per row, and the UPDATEs are one statement per changed row. The other auditor's fix (compute in prepare) stands.

**E7. `resolve_lorebook_graph` is N+1** (`memory_lorebooks.py:235-310`): one `_owned` SELECT per visited book, child and link, per resolution. Several resolutions run per beat outside the ctx-cached `_books` (`persist/commit_mapping.py:270`, `persist/checkpoints.py:136`, `world/subjects.py:340`, `world/charter_runtime.py:1889`, `story/naming.py`). Small graphs today.

## Already registered / already found by another auditor

- **UNBUILT_PLATFORM §1.172**: `_replace_memory_fts`/`_delete_memory_fts` scan the whole FTS index (`memory_write.py:247-257`); restore pays two per row (`memory_snapshot.py:492-505`). Confirmed still live. E1 is its read-side twin and is NOT covered by it.
- **UNBUILT_PLATFORM §1.35**: `memories_fts` has no reader (`core/db.py:954-999`). Still true.
- **UNBUILT_PIPELINE §1.73**: the chronological-padding brake stops only the inner loop (`memory_retrieval.py:806-823`). Reproduced: k=2 → 5 rows, k=3 → 7 (`verify2.py` T4b). MEMORY.md:850's "k+2" is the doc half of that entry.
- **UNBUILT_CHARACTERS §1.76**: `recall_confidence` is inert. It is now probe-only (no production caller; `tools/memory_probe_harness.py`).
- **UNBUILT_CHARACTERS §1.85**: window clock readings come off the window's own rows (`memory_time.py:320-350`).
- **UNBUILT_PIPELINE §1.214** (via the llm auditor): `strict_json_parse` cut-off, reached from `memory_judge.py:136` and `memory_summaries.py:470`.
- **persistence_paths_schema F4** (not a register): `rebuild_embeddings` (`memory_vectors.py:262-279`) and the fallback repair (`memory_write.py:676-688`) UPDATE `WHERE id=?` after a slow embed while a restore re-mints ids. Addendum from this audit: the repair UPDATE is not compare-and-set even without a restore. It re-reads the stamp at SELECT time only (`:664-665`), so a host edit (`update_memory`) that re-embeds the row while the repair is inside its embed call is overwritten with vectors of the OLD content, stamped live, and nothing ever revisits it. Same fix: `AND embedding_model='cheap:crc32:256' AND content=?` in the UPDATE. F3 is this class on the host-edit side.
- **persistence F22 / P3 and web_app E1**: `embedding_bank_status` makes a provider round trip on every restore and chat open (`memory_vectors.py:64`).
- **persist_background_memory E4**: reconcile inside the write lock (E6 above).

## Structure notes

- **Monoliths in miniature:** `build_character_memory_context` (`memory_context.py:280-886`, ~600 lines; five lanes of recall interleaved with projection, citation and host bookkeeping); `search_memories` (`memory_retrieval.py:544-849`, ~300 lines, now used only by the resurfaced lane, the tension pass and the author's search route); `memory_routes.answer` (`:433-634`, ~200 lines with three closures); `rebuild_embeddings` (`memory_vectors.py:180-404`); `search_lore` (`memory_lore_entries.py:442-545`).
- **Natural seams:** (1) the recall lanes inside `build_character_memory_context` (recent, recall net, ponder, asked, resurfaced, summaries) each return rows + refs + access ids + record, so one builder per lane plus a thin assembler. (2) `memory_retrieval` holds three generations of retrieval: the legacy RRF `search_memories`, the probe-only `recall_confidence`, and `contrast_memory`. A `memory_contrast` module and a legacy module would leave retrieval primitives (`_rrf_add`, `_mmr_select`, `_exact_cue_score`, `_rank_normalized_importance`) as the shared leaf `memory_jev` already imports from. (3) Lore overlays (`memory_lore_entries.py:283-440`) are their own sub-domain. (4) `routed_ponder` versus `jev_ponder_packet`'s tail (F20).
- **Module-level mutable state and its writers:**
  - `memory_write._REPAIR_PENDING` (dict of sets; `note_failed_embedding_write`, `repair_pending_embeddings`, tests via the facade, which shares the object).
  - `memory_write._REPAIR_THREAD`, rebound with `global` in `_ensure_repair_thread`. The facade re-export `mind.memory._REPAIR_THREAD` is frozen at the import-time `None`, the brief's "global rebind of an imported name" shape. No reader today; a latent trap.
  - `memory_retrieval._STRANDED_REPORTED` (add in retrieval, `.clear()` from `memory_vectors:400`; shared object, as AGENTS.md says).
  - `memory_retrieval._BOUNDARY_RE_CACHE` (bounded 20,000, unlocked dict writes; GIL-safe).
  - `memory_vectors._REBUILD_STATE` / `_REBUILD_LOCK` (E5's check-then-act).
  - `memory_routes._POOL`, a lazily created `ThreadPoolExecutor` behind `global` with no lock: two concurrent first ponders build two pools, and neither is shut down.
- **Threads not joined at shutdown:** `_shutdown_engine` (`web/app.py:357-395`) joins the startup decider thread but not the `embedding-rebuild` thread it starts, nor `embedding-repair` (which sleeps 30-300 s and then queries whatever database `core.db` names, with ids queued against the old one: the same hazard the shutdown docstring measured for the reconciler), nor the `ponder-route` pool.
- **Tools drifting from production:** `tools/jev_packet_compare.py:126` still excludes the pre-2026-09-28 recent window (`turns=4, limit=12`) where production uses `RECENT_TURNS=8`, unlimited.
- **The essay "Why there is no vector index"** lives in `memory_inference.py:11-37`, against SPLIT_MEMORY's instruction to keep it with the vector code, and the module docstring's pointer to "the rebuild above" is false (F22).

## Docs checked

| claim | where | verdict |
|---|---|---|
| `visible_memory_rows` is the one seam a mind reads its memory through | `memory_read.py:1-5`, MEMORY.md §3 | **HOLDS for raw rows** inside `mind/` (every mind-facing row read traced: search/contrast/recent/net/successors/links/consolidation/backfill). **Does not hold** for the derived summary layer (F1) or `world/offscreen.agent_context` (F2) |
| "a test fails if an unlisted cross-character reader appears" | MEMORY.md:614-615 | **FALSE** since the split (F19) |
| Host-scope readers feed no mind | `memory_read.py:153-161` | **HOLDS**: `dramatic_irony_feed`/`promise_ledger` are called only from `web/app.py:4943, 4947` |
| `mind/memory.py` holds no domain code | CLAUDE.md, AGENTS.md:995-998 | **HOLDS** |
| "over thirteen `mind/memory_*` siblings" | AGENTS.md:995 | **STALE**: the facade imports sixteen; the table omits jev/links/routes |
| `memory_judge` deliberately not behind the facade | AGENTS.md:1000-1004 | **HOLDS** |
| `_STRANDED_REPORTED` is the one piece of shared mutable state | AGENTS.md (facade section) | **HOLDS** across modules; the `_REPAIR_THREAD` re-export is a frozen copy (structure note) |
| search_lore / knowledge_for_character / declared_circles read the library row with the story's overlay merged | AGENTS.md:538 | **HOLDS** (`lore_rows`); `agents/character.py:3884` calls `declared_circles` without `chat_id`, so a story-level circle on an overlay is missed in that warning |
| "every row of the last 8 turns (`RECENT_TURNS`)" | MEMORY.md:259 | **HOLDS** (`memory_context.py:277, 345-347`; `memory_retrieval.py:1228-1246`: turns N-8..N-1, prestory -1 excluded) |
| `NET_SIZE` 100, `_RECALL_LIMIT` 30, recalled then recent, perception last | MEMORY.md:684, owner's packet design | **HOLDS** in code (`memory_jev.py:59`, `memory_retrieval.py:330`, `memory_context.py:880-885`); MEMORY.md:858's heading still says 16 |
| consolidation refuses to run outside the present | MEMORY.md:988 | **HOLDS** (`memory_summaries.py:754-756`), but its readers do not apply the frame rule (F1) |
| `event_key`: "Re-minting the same key UPDATEs instead of inserting" | MEMORY.md §1 | **HOLDS**, understated (F7) |
| `_kw_scores` returns normalised BM25 and is scoped | `memory_common.py:186-215` | **HOLDS** |
| search_lore compatibility is "model key AND length, matching search_memories' rule" | `memory_lore_entries.py:498-511` | **PARTLY**: key and length match, but search_memories also refuses a fallback batch and search_lore does not (F10) |
| "Two COUNTs" on chat open | `web/app.py:4757` | **STALE** (F22) |
| AUDIT_MEMORY §2 drift items 2.1-2.9 | MEMORY.md | **STILL STALE** (table above, F22) |
| Design.md "Memory retrieval by meaning" row | Design.md:251 | dated 2026-08-01, so true as written; today's key is `generic:7:perplexity/pplx-embed-v1-4b` and recall is the jev net, not `search_memories` |
| RRF with ties | `memory_retrieval.py:429-433, 656-700`; `memory_jev.py:189-191, 314-318` | **HOLDS as documented**: each list gives tied ids distinct ranks. Semantic/cue ties go newest first (`sorted` on `(score, id)` reversed), exact ties oldest first (stable sort, a documented, measured choice at `:671-682`), net ties oldest first. The exception is F13 |
| importance rank-normalisation on one row / a flat bank | `memory_retrieval.py:520-529` | **HOLDS**: returns the raw `effective_importance` (same scale), never a fabricated spread |
| mood-congruence sign | `memory_retrieval.py:416-426, 755-763` | **HOLDS**: same sign raises, opposite lowers, valence 0 untouched; reads 0.75 encoded + 0.25 incoming |
| 8-turn window at turn 0, skips, prestory | `memory_retrieval.py:1228-1246` | **HOLDS**: turn 0 → empty; turns N-8..N-1; `limit=None` keeps a skip turn's rows whole; prestory (-1) never recent, still recallable |
| routed recall tie-breaking | `memory_routes.py:371-414` | **HOLDS**: `_first_sure` takes the first in walk order; `_surest` the earliest within `NEAR_TIE` and `TIE_REACH` |
| FTS query builders are injection-safe | `memory_common.py:182-184`, `memory_retrieval.py:21-28` | **HOLDS**: every token is double-quoted, an embedded `"` is doubled, lore tokens are alphanumeric, table names are internal constants |
| `_REPAIR_*` thread: bounded, idempotent, never takes a turn down | `memory_write.py:530-718` | **HOLDS** for bounds and safety; not for throughput (F11) or compare-and-set (F4 addendum above) |
