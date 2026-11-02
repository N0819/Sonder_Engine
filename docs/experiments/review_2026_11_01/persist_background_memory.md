# Audit — `persist/commit_background.py`, `persist/commit_memory.py`, `persist/commit_memory_write.py`, `persist/commit_skip.py`

Auditor scope as briefed, 2026-11-01, working tree at `84f3de23` (clean). Read-only.

## Scope read

Read in full, every line:
- `persist/commit_background.py` 1–5731
- `persist/commit_memory.py` 1–2532
- `persist/commit_memory_write.py` 1–434
- `persist/commit_skip.py` 1–126
- `docs/experiments/AUDIT_COMMIT.md` (the 2026-08 split audit)

Read in part, to trace callers/readers (NOT audited as such):
- `agents/background.py` 1004–1200 (stage orchestration, cap), 1474–1700 (`_chorus_for_overflow`, `_demanded_presences`), 3005–3270 (`_recent_words`, `_react_one` tail, `presence_hearing`)
- `agents/character.py` 3890–3915, 4360–4401, 4655–4700; `agents/character_bare.py` 250–280, 395–420; `mind/character_jev.py` (grep: 218, 844–866)
- `agents/director.py` 1150–1170, 4736–4800 (intended_target backfill)
- `persist/commit.py` 468–482, 555–680 (domain order), 760–870 (tail); `persist/commit_common.py` 72–125, 408–520, 570–590; `persist/commit_entities.py` 282–420; `persist/commit_scene_state.py` 2255–2330, 2974–2985
- `story/scene.py` 238–336, 2716–2748; `story/naming.py` (`story_identity_reservation`, `minted_presence_name`); `story/character_schema.py` 1813–1836, 1878–1890
- `world/charter_runtime.py` (`promotion_bundle`, `bind_promoted_character`); `world/spatial_senses.py` 1330–1360
- `mind/memory_inference.py` 90–165; `mind/theory_of_mind.py` 669–705; `mind/memory_write.py` 897–920; `mind/memory_summaries.py` 715–735; `mind/affect.py` 1319–1500
- `core/db.py` (`transaction`, `qi`, `wget`); `core/jobs.py` 91–131; `web/app.py` 4930–5010
- Skimmed only: `docs/design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md` (its claims are prompt-side; nothing checkable in these four files).

Tests: none run. The orchestrator's `.venv` full-suite baseline is green (`scratchpad/baseline.time`, exit 0), so every test named below passes today. Six pure-function snippets were run on `.venv/bin/python` (no DB writes); each is pasted with its finding.

## Findings

### F1 — LEAK: a waiting character is handed the owing figure's ledger NAME (and the figure's own private wording)

`persist/commit_background.py:1723-1730`
```python
    for record in (presences or {}).values():
        ...
        owed = owed_service(record, turn_idx, now_seconds)
        if not owed or owed["to_ref"].casefold() != want:
            continue
        owed["from"] = str(record.get("name") or "")
```
Delivered unscrubbed: `agents/character.py:4392-4401` puts the rows on `self.still_waiting_for` with no `observer_name_scrub`/`scrub_names_deep` pass (the same builder scrubs lore at 3902 and `while_you_were_offscreen` at 4665), and the bare contract prints it into the decision prompt at `mind/character_jev.py:865` — `f"{p.get('what')} ({p.get('from')})"`.

Failure: Sal asks an innkeeper for ale; the figure knows her only as "the weathered woman" (`pending_act.to`). His record name is "Goodfolk Simota Barleymaner" — written by the Director or minted from the naming law by `_mint_missing_presence_names` (2065), i.e. possibly a name nobody in the fiction has ever said. Sal's perception renders him through the identity floor ("the stout innkeeper"); her very next payload names him. `what` is the figure's own typed `still_owes.what` (its model's private phrasing of the service), also delivered verbatim. The abandon path depends on the leak: `apply_abandoned_debts` (1802-1806) matches the character's `waiting_ops.from` against `record.name`, so it only works because the payload carried the real name.

Verified: writer → `agents/character.py` reader → `character_jev` renderer traced; `tests/test_a_promise_has_an_age.py:71-74` pins the leaked value (`rows[0]["from"] == "Goodfolk Simota Barleymaner"` for an asker the figure calls "the weathered woman"). **CONFIRMED.** Not in any UNBUILT register (grep `owed_to|still_waiting|pending_act`: none).

Fix: label `from` through the asker's own recognition (the `known` map `observer_name_scrub` uses; a label when unknown) and give each row a stable handle (figure uid + promise turn) that `waiting_ops` closes by, instead of by name. Test: an asker whose `known` lacks the figure gets `from` == the label, never the ledger name; an abandon op by handle clears the row.

### F2 — LEAK: a role-word `intended_target` is matched as a PRECISE address to every holder of the role — a whisper's words are quoted to bodies it was not breathed to

`persist/commit_background.py:1259-1268` (`_character_address_of`) and `:4055-4057` (`_presence_addressed_match`)
```python
        target = str(d.get("intended_target") or "").strip()
        # PRECISE match: `intended_target` is a structured field naming ONE
        # addressee, ...
        if not target or not _presence_addressed_match(presence_name, target):
            continue
...
    stripped = _normalized_descriptor(strip_name_titles(ref))
    return bool(stripped
                and re.search(rf"\b{re.escape(stripped)}\b", name_cf))
```
Snippet (run):
```
>>> _presence_addressed_match('Trader Bob', 'the trader')         -> True
>>> _character_address_of({'dialogue_log':[{'speaker':'Sal','intended_target':'the trader',...}]}, n, {'sal'})
Trader Bob True / Trader Ann True / Trader Tate True / Cook False
```
`_presence_in_addressed_refs`' own docstring (4060-4066) says partial containment is safe ONLY because `_flow_addressed_refs` canonicalised the ref through `descriptor_bindings` first; `intended_target` is never canonicalised before this matcher, and it does carry descriptions (`_player_intended_targets` docstring: resolve wrote `intended_target: "market trader"`, Harrowmere t2). The comment at 1260-1266 records that the fuzzy fallback here once turned one sleeve-grab into a 44-strong forced chorus (chat 95 t3043); the containment arm re-opens the same class for any ref that strips to a role word.

Consequences, traced:
- Gate (`pick_voice_demand` 4513 → 4571, 4585, 4646): each holder is `char_addr` → `exempt` from `address_reaches` and `addressed_precise` → `forced += 1` → every holder is voiced past `max_reactors` (the chorus collapse at `agents/background.py:1494-1508` fires only when they are one charter's crowd in one room).
- Commit (2879-2888): `_character_address_of(..., hears=ear)` grades the line with `hears(d, True)` — "the line is its own" — for EVERY holder. For an `ear`/`whisper` line `world/spatial_senses.py:1330-1350` grades it "to its addressee ... as a whisper is ... to anybody else ... nothing", so each holder within reach is graded FULL and stores `pending_reply.quote` = the breathed words, which `_react_one` hands it next beat as the address it owes. Each also accrues `addressed_turns` (the promotion counter).

**CONFIRMED** (snippet + trace). Not registered. Fix: refuse a ref whose stripped form is a word this story's tracked names share (`_shared_name_words` is already the title vocabulary), or route `intended_target` through `descriptor_bindings` exactly as flow refs are. Test: three "Trader *" presences + one whispered line with `intended_target: "the trader"` → at most one `pending_reply`, gate picks ≤ cap.

### F3 — LEAK + CORRUPTION: the charter overlay folds a different body into any tracked record of the same name; promotion then hands that record the other body's life

`persist/commit_background.py:976-988` (`with_charter_presences`)
```python
        if key is None:
            key, _rec, status = _presence_lookup(merged, name, scene)
            if status == "ambiguous":
                continue    # two tracked records answer; refuse to guess
        ...
        else:
            _merge_presence_record(merged[key], record)
```
No check that the hit record is bound to another body (`entity_id`) or carries another body's `charter_refs` — the rule `_resolve_or_mint_presence` keeps (770-779: "A name match already bound to a DIFFERENT body falls through to the mint: same name, two bodies, two records -- the point of the key").

Snippet (run; `background_presence_records` stubbed in-process):
```
ledger: "Mara" bound to entity m1 (hall);  charter derives a DIFFERENT "Mara" (millers/b17, mill)
records: 1
p_f09aa0e4013525ae m1 [{'charter': 'millers', 'body': 'b17'}] {'station_room': 'hall'}
```
The weld persists: `track_background_presences` overlays `names=candidates|selected` (2492-2495) and the record is in `_before`/`touched`, so `_earned` keeps it. `_merge_presence_record:644-649` also lets the charter record's `nature` overwrite. At promotion, `promotion_bundle(cid, name, record=...)` resolves by the record's `charter_refs` (world/charter_runtime.py `promotion_bundle`: `refs = record.charter_refs`) and hands the hall Mara b17's handoff — memories, relationships, inherited place graph, interoception, stress — and `promote_background_character:5188-5191` places her at the bundle's `place` (the mill), then `bind_promoted_character` binds b17 to her. The engine can produce the collision itself: `_mint_missing_presence_names` reserves only registered names (`story_identity_reservation` → `registered_identity_names`) while drawing from lanes that include the charters' (`_charter_naming_lanes`), so a minted presence name may equal a charter body's display name.

**CONFIRMED** (merge reproduced; promotion consequence by trace). Not registered (UNBUILT_IDENTITY §1.17 covers generic-name crowds, not this). Fix: accept a name hit in the overlay only when the hit has no conflicting `entity_id` and no other body's `charter_refs`; otherwise key a separate record on the deterministic charter seed. Test: the snippet's ledger → two records; promoting the hall Mara pulls no charter bundle.

### F4 — LEAK (narrow): a promise memory describes a speaker the hearer only HEARD by its full-sight appearance

`persist/commit_memory.py:1204-1206`, `:323-327`
```python
                spk_label = _hearer_label(
                    spk, chat, ctx.cast, _hearer_known,
                    describe=True, heard=True)
...
    label = _unknown_actor_label(
        raw,
        _char_appearance(sheet) if sheet else None,
        character_scene_keys(sheet)[1:] if sheet else None,
    )
```
`_unknown_actor_label(..., sight="full")` is the default and `_hearer_label` passes no sight; `heard=True` only changes the generic-fallback case. The only gate on the row is that the quote reached the hearer's view (1217) — a hearing test. Failure: an unrecognised cast member promises something through a shut door; the hearer's view says a voice spoke; the `category == "promise"` row (1252-1278) stores `content`/`gist`/`key_phrases`/`entities` as "I heard the tall silver-haired woman in a lab coat say ..." — appearance of a body never seen, recalled for the rest of the story. The same row's `about` IS sight-filtered (`_memory_about` → `sighted_level`, 803-804), so one row's two fields disagree. Scope: promise rows only (since 2026-09-30) and registered speakers only (a presence has no sheet → fallback → "a voice").

**CONFIRMED** by trace. Fix: pass the hearer's `sighted_level(sc, cname, spk, senses)` into `_hearer_label` → `_unknown_actor_label(sight=...)`, "a voice" when unseen. Test: closed-door promise from an unknown cast member → no appearance token in the row.

### F5 — CORRUPTION: `promote_background_character` is not atomic; a failure after the inserts leaves an attached character AND its presence record

Writes, each auto-committed because neither caller holds a transaction (`qi` outside `transaction()` commits per statement, `core/db.py:2414-2429`): INSERT `characters` 5015, INSERT `chat_chars` `status='active'` 5035, relationship graph 5061-5167, `scene` 5213/5216, `seed_mutual_recognition` 5224, `add_memories_batch` 5258 (an embeddings round-trip mid-sequence), `claim_greeting_mind` 5267, then
```python
        if not bound:
            raise RuntimeError("Charter promotion binding could not be saved")
```
(5279-5280) — and only after that the ledger cleanup 5282-5329. Callers: `web/app.py:4990-4993` (`with _era(...)`, no transaction) and `_land_drafted_promotion:5596-5605` in the commit tail (after `_commit_all_locked`'s transaction), which turns the raise into a warning.

Failure: a charter-backed promotion whose body is gone from the registry by binding time (`bind_promoted_character` returns False — the registry is rewritten out of band by the charter tick job) → the story keeps an active character with a position, recognition edges and seed memories, the presence record of the same name stays tracked, and the charter keeps simulating the now-unbound body (one person, two simulations). With auto-promote on, every later beat re-selects the still-`promotable` record, the job re-drafts it (two `utility` calls, ~27 s each per the C10 measurement), and the landing is refused by `_refuse_name_collision` because the half-made character holds the name — indefinitely (nothing records the failure).

**CONFIRMED** by trace. Not registered. Fix: split into a pure prepare (sheet, bundle, `prepare_memories_batch` embeddings) and ONE `with transaction():` for every write including the charter binding's `save_registry`. Test: monkeypatch `charter_runtime.bind_promoted_character` → False; assert no `characters`/`chat_chars` row and the presence record intact.

### F6 — CORRUPTION: the commit re-derives the beat's description binding AFTER the departure applier moved the bound body, and persists it on someone else

`persist/commit_background.py:2676-2687` (departures write the scene), `2693-2702` (handovers), then `2787` `_bindings = descriptor_bindings(ctx, res)`, which re-reads the scene (`3912-3915` `beat_scene(wget(cid, "scene"), ...)`) and rebuilds the cohort from it (`3998-4002` `presence_room(sc, name, rec) == p_room`).

Failure: "the man with the apron -- an ale, please." The gate's `descriptor_bindings` (pre-commit scene) binds the phrase to Tapster by seeded pick; Tapster is voiced and answers "Right away" with `goes_to: cellar`. At commit the departure applier moves him first; the re-derived cohort no longer holds him, so the seed picks Cook: 2795-2805 stores "the man with the apron" in Cook's `sketch.descriptors`, 2788 maps the address to Cook → Cook gains `addressed_turns` and (words reaching) a `pending_reply` for a question Tapster answered; next beat Cook is owed a reply and the phrase now retrieves Cook. Second vector: `offscreen_epoch` (commit.py, before `background_presences` at :650) can move charter bodies, changing the overlay `with_charter_presences(places=...)` (3931-3933) feeds into the cohort. The docstring's "Deterministic given the model's string" (3894-3896) holds only for one cohort; the gate and the commit compute it from different scenes.

**CONFIRMED** by trace (call order + re-read). Not registered. Fix: compute the bindings once at the gate and carry them on the `background_react` step output for the commit and the tail to read (also removes four recomputations, see E1); minimally, call `descriptor_bindings` before the appliers. Test: bind a description to A whose reaction carries `goes_to`; after `track_background_presences`, A carries the descriptor and B gains nothing.

### F7 — CORRUPTION: the commit's `addressed_turns` (the promotion counter) accrues on a loose word-match, with neither the gate's subject rule nor any channel test

`persist/commit_background.py:2820-2825` → 2926-2930
```python
        addressed = any(
            _presence_in_addressed_refs(n, addressed_refs)
            or _background_name_mentioned(n, player_input,
                                          shared=shared_words)
            for n in _presence_names(key, record)
        )
```
The gate drops a loose match when the words did not arrive (`address_reaches`, 4574-4584) and when the beat has a precise addressee ("A NAME IN A LINE AIMED AT SOMEONE ELSE IS A SUBJECT", 4697-4710). The writer applies neither. Failure: player to the clerk (flow-addressed): "Has Nookfeller been in today?" — Nookfeller, at the mill across town, gains `addressed_turns`. Two such beats and a Room-planned Nookfeller crosses `PLANNED_PROMOTION_ADDRESSED_THRESHOLD` (2): `_propose_promotions` tells the Director and the owner he was "turned to on 2 beats" (4803-4811), and `select_auto_promotion` counts the same list against `promote_after_addressed` (5441). The gate and the writer also use two different title vocabularies for the one beat: display names only at 4463-4465, display + `aka` at 2723-2725.

**CONFIRMED** by trace. `tests/test_who_you_talk_to.py:135-150` covers only the shared-word case. Fix: accrue from the gate's own verdict (carry `meta.why` on the step), or apply the subject rule and `address_reaches` here. Test: precise addressee A plus a loose mention of B in the same line → B gains no `addressed_turns`; B in another room never does.

### F8 — CORRUPTION: a body placed by `positions` alone is invisible to the crowd guard, folds into a same-named entity-bound record, and `presence_room` then reads the twin's room for the bound body

`persist/commit_background.py:288-292` (`_bodies_answering_to` counts `scene.entities` only), `:406-413` (`presence_room` tries `room_of(scene, name)` BEFORE the record's bound `entity_id`), `:3518-3521` (`apply_presence_departures` moves the name-keyed position first).

Snippet (run):
```
scene: entities {g2: Guard} at gate; positions {"g2": "gate", "Guard": "cellar"}
bodies answering 'guard' (crowd guard sees): 1
cellar body resolves to the gate guard's record: True records: 1
presence_room of that record: cellar
```
Failure: the positions harvest (2435-2463) tracks the cellar body as "Guard", `_resolve_or_mint_presence` hits the gate guard's record by exact name, and the merge writes `sketch.station_room = "cellar"` over the gate guard's (2575 `update`). Every reader that asks where the bound guard stands (gate channel tests, `_presence_ear`, `descriptor_bindings`' cohort, departures) answers the cellar. `_presence_scene_entity`'s docstring promises the bound id "outranks every string comparison"; `presence_room` does not honour it. Positions-only bodies are a documented class (chat 72's night clerk, 2366-2385).

**CONFIRMED** (snippet). UNBUILT_IDENTITY §1.17 registers the generic-crowd residual, not this. Fix: count bare-name `positions` keys that are not entity ids in `_bodies_answering_to`; in `presence_room`, prefer the bound entity's position when the record is bound. Test: the snippet's scene → two records; the gate guard's room stays "gate".

### F9 — CORRUPTION: salience cues match inside other words, pushing ordinary memories over the 0.72 archive bar

`persist/commit_memory.py:342-344`
```python
    for w in _ling("_SALIENCE_CUES"):
        if w in (text or "").lower():
            s += 0.08
```
The sibling `_durable_dialogue_category` (61-82) was fixed for exactly this ("bare substring matching made 'compromised' a promise") by anchoring the pack patterns with `\b`; the salience list is still bare substrings. Snippet (run):
```
54 chars, plain:                                                        0.484
"A familiar woman glanced at the compromised door ..." (liar, promise)  0.657
"He pulled on a glove at the deadline beside the secretary." (love, dead, secret)  0.726
```
`mind/memory_summaries.py:718-727` never archives a row with salience ≥ 0.72; a ≥ 320-character turn memory scores 0.65+ on length alone, so one spurious cue ("familiar", "compromise", "glove", "deadline", "secretary", "stealth") makes it permanently unarchivable. The episode row is the only caller (1376), i.e. every turn memory of every mind.

**CONFIRMED** (snippet). Not registered. The AUDIT_COMMIT finding (English-only lists) is fixed — the cues moved to the packs and `ja` is populated — this is a separate defect in the same list. Fix: write the `en` cues as `\b`-anchored patterns exactly as `_DURABLE_QUOTE_MARKERS` are, keep `ja` unanchored, and `re.search`. Test: "familiar"/"compromised" text scores the length-only floor.

### F10 — CORRUPTION: a promise's clock stamp re-applies the beat's span to a clock the scene domain already advanced

`persist/commit_background.py:1649-1653`
```python
        clock = wget(cid, "simulation_clock", ...) or {}
        diff = ((res or {}).get("state_diff") or {}).get("time")
        seconds, _ = _monotonic_elapsed(clock, diff, floor=True)
```
`track_background_presences` runs in the `background_presences` domain (persist/commit.py:650), after the `scene` domain (:572), whose `commit_scene` has already written this beat's clock (`commit_scene_state.py:2979-2980`). `prepare_memory_commit`, which the docstring claims to match, reads the clock pre-commit. Snippet (run):
```
clock the scene commit stores: 1600.0
what _owed_clock_seconds stamps (re-applied to the stored clock): 2200.0
silent beat: stored 1010.0 stamped 1020.0
```
So `owed_service.seconds = now - pa.seconds` reads 0 for a beat after the promise and is understated by one beat's span thereafter (an hour for an hour-long beat) — the one number `still_waiting_for` exists to carry.

**CONFIRMED** (snippet + domain order). Fix: stamp with the clock already stored (`wget(simulation_clock).elapsed_seconds` — it IS this beat's end), or pass the prepared clock. Test: a 600 s beat writes `pending_act.seconds` == the stored clock.

### F11 — CORRUPTION (two representations): a handed-over thing exists in `world.scene` and never in `world_entities`

`apply_presence_handovers` mints `scene.entities[key]` (`persist/commit_background.py:3434-3446`) and `track_background_presences` writes the scene (2697-2698). `commit_world_entities` (`persist/commit_entities.py:282+`) projects only `diff.entities` and has already run (`entities` domain, commit.py:585, before :650). The mug is in the blob and absent from the projection until some later diff happens to touch it; readers of the projection — `world/paradox.py:184-188` `_entity_exists` (fixed-point anchors), the checkpoint snapshot (`persist/checkpoints.py:228`) — disagree with the scene. Same shape for any future applier in this domain. **CONFIRMED** by trace. Not registered (UNBUILT_PIPELINE §1.101 is the unrecorded-object handover, not the projection). Fix: project the appliers' minted entities in this domain, or move both appliers ahead of the `entities` domain. Test: a handover → `world_entities` holds the minted key.

### F12 — WRONG-SCENE: in a non-present frame, a mind the skip brings back stays dormant

`persist/commit_skip.py:53-55, 83-87`
```python
    rows = q("SELECT ch.id, COALESCE(cc.sheet,ch.sheet) AS sheet, cc.status "
             "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
             "WHERE cc.chat_id=?", (chat_id,))
...
            if row is not None and str(row["status"] or "") != CAST_STATUS_PRESENT:
                set_char_status(chat_id, cid, CAST_STATUS_PRESENT, frame_id=frame_id)
```
`set_char_status(frame_id=F)` writes `chat_char_frames` (story/scene.py:296-310), but the decision reads the BASE `chat_chars.status`. In frame F a mind dormant in F (override row) but active in the base is never flipped back, though the far end put it in a room the world holds; the reverse case reports a false `back`. **CONFIRMED** by trace. Fix: read `COALESCE(ccf.status, cc.status)` joined on the frame, as `char_state` does (story/scene.py:328-335). Test: frame override dormant + base active + far-end room present → override becomes active.

### F13 — SILENT-NOOP: in the default `scene_life: off` path a promised act is never re-asked

`pick_voice_demand` (4313-4756) has no `pending_act` trigger — `owed` is `_valid_pending_reply` only (4517); `_valid_pending_act`'s only gate reader is the manager path, `agents/background.py:1614` (`owes_act`). The per-presence path DOES write the debt (`_react_one` returns `still_owes`, commit 2841-2867). So with the default setting the Aldermill tapster `_valid_pending_act`'s docstring (1822-1832) was written for still holds the mug unless re-addressed. Docs that say otherwise: Design.md:280 ("`still_owes` writes the figure's aged `pending_act` (re-asked until `hands_over` lands ...)"), DESIGN_CONVERSATION_THREADS.md:37-38, and `owed_service`'s "`lapsed` is the gate's own verdict" (1677-1679) — the default gate never consults it. **CONFIRMED** (grep: `pending_act`/`_valid_pending_act` absent from `pick_voice_demand`; no test pins a re-ask in either gate). Fix: add `owes_act` to `pick_voice_demand` with the same rank and channel rule `_demanded_presences` uses — better, one trigger evaluator both gates call (Structure notes). Test: a record with an unexpired `pending_act` and no other trigger is picked under `scene_life: off`.

### F14 — SILENT-NOOP: the memory-tension pass skips every beat that commits while a pass is in flight

`persist/commit_memory_write.py:233, 290-294, 307`: a constant job key, and `_produce` reads only `memories WHERE ... turn_idx=?` for its OWN scheduling turn. `core.jobs.submit` joins an in-flight job with the same key (core/jobs.py:114-123), so the next beat's tail schedules nothing and its rows are never reviewed. The pass costs ~114 s (its own docstring) against ~1-minute beats, so roughly every other beat goes unreviewed. The skip-memories job beside it fixed exactly this class with a per-turn key (166-170, 216); consolidation is immune because it re-reads a cursor. **CONFIRMED** by trace. UNBUILT_CHARACTERS's tension entry (around 1254) does not mention it. Fix: key per turn (`MEMORY_TENSION_JOB_KEY + turn_id`) or read every unreviewed turn since a stored cursor. Test: submit twice while the first is held → both turns reviewed.

### F15 — SILENT-NOOP (language pack): the presence name matchers use `\b`, so a Japanese name followed by a particle or honorific never matches

`persist/commit_background.py:1150, 1158-1160` (`_background_name_mentioned`), `1222-1223` (`_background_name_named_exactly`), `4053-4057` (`_presence_addressed_match`); `3795` `_word_stems` uses `[a-z0-9]+`. Snippet (run):
```
named_exactly JA: False   (_background_name_named_exactly('ハンナ', 'ハンナさん、エールを一杯'))
mentioned JA:     False   (_background_name_mentioned('ハンナ', 'ハンナは頷いた'))
named_exactly EN: True
```
`story/character_schema.py:1813-1836` `name_boundary_pattern` exists for exactly this ("`ヒナミに` never matched `ヒナミ` and every name-keyed guard silently stopped firing") and `commit_memory._intent_names_term` already uses it. In a Japanese story: the gate's `named_exactly`/`mentioned` triggers, the writer's `mention_turns` (and with them the mention promotion bar) and the player-precise reply debt never fire for the ordinary spelling; PB6's description narrowing (`_bodies_the_description_could_be_true_of`) never narrows. The English title/article tables (`_NAME_TITLE_PREFIXES`, `_PRESENCE_ARTICLES`, `_normalized_descriptor`) are harmless no-ops there (Japanese honorifics are suffixes). **CONFIRMED** (snippet). Not registered. Fix: build these regexes with `name_boundary_pattern`; tokenise `_word_stems` per script. Test: the three snippet calls with Japanese text → True.

### F16 — SILENT-NOOP: a charter figure's action-only first beat is discarded, promise and all

`persist/commit_background.py:3068-3082` keeps a charter-derived record only if it is in `_before`, `touched`, or has dialogue/addressed/mention turns or a `pending_reply`. `touched` comes from candidates, and the reaction harvest uses `_background_fired_reactions` (2471-2481), which admits only reactions WITH a `dialogue_log_entry` (1882-1887). So a charter body voiced for the first time (on `acting`/`arrived`/`owed`, not addressed) whose reaction is an act with `still_owes` gets its `pending_act` (2856-2870) and `recent` tail written onto the overlay record — and the record is then dropped. The promise never reaches `owed_to`. The comment (3064-3066) lists what earns a place and omits acting; the code follows the comment. **CONFIRMED** by trace (frequency PLAUSIBLE). Fix: count a fired reaction of any shape (`_background_fired_reactions_any`), `pending_act` and `engaged_turns` as participation. Test: overlay figure, action-only reaction with `still_owes` → the record and its `pending_act` persist.

### F17 — WRONG-SCENE: the gate grades a character's aimed line room-to-room while the debt writer uses the presence's own ear

`persist/commit_background.py:4513` `_character_address_of(dr_output, name, roster, sc, here)` — no `hears=` — against 2879-2881, which passes `hears=_presence_ear(...)`. The disagreement is measured in `_character_address_of`'s own docstring (1249-1252: the room read gives FULL to a bystander the ear grades "pieces" at 7.2 paces in a 68 dB din). The gate then exempts that pick from the channel test (4571) and forces it past the cap (4646), while the writer writes no reply debt — precisely the gate/writer disagreement 4602-4607 says the channel filter exists to remove. `agents/background.py:1605` (manager gate) has the same omission. AGENTS.md:435 states "One ear for every reader that asks whether the words arrived ... never its own hear_level call". **CONFIRMED** by trace. Fix: pass `presence_hearing(ctx, sc, name, here, dr_output)` in both gates (it is lazy, so free for untouched presences). Test: the docstring's din case → the gate does not pick on `character_address`.

### F18 — CORRUPTION: a presence record whose name now belongs to a registered character is never retired, keeps collecting that character's mentions, and is re-drafted every beat

The mention loop (2726-2736) has no roster check; no attach path prunes the ledger (grep `background_presences` in `web/app.py`/`story/`: readers only); `select_auto_promotion` (5432-5472) has no roster check either. A host who attaches a hand-made card for a figure the story tracked (or the half-promotion of F5) leaves a same-named record that accrues `mention_turns`/`last_turn` every beat the character is named, stays `promotable` in the presences panel, and — auto-promote on — is "active" every such beat, re-drafted out of band and refused by `_refuse_name_collision` at landing. **PLAUSIBLE** (traced; not reproduced). Fix: drop or freeze a record once `name_in_roster(record name, roster)`; skip roster names in the mention loop and in `select_auto_promotion`. Test: tracked "Mara" + attached card "Mara" → the record stops accruing and is not selected.

### F19 — WRONG-SCENE: `forced` is counted before same-name picks collapse, so two same-named addressees widen the slots for an unrequested extra voice

`persist/commit_background.py:4635-4646` counts every precise candidate; `4744-4752` then dedupes by display name, so `slots = max(forced, cap)` keeps a slot the duplicate no longer uses and fills it with the next candidate (e.g. an `acting`-only body) at cap 1. Uid keys make same-named records legitimate ("two people may share a name now"). **CONFIRMED** by trace. Fix: count distinct names. Test: two records named "Guard", both precisely addressed, plus one `acting` body, cap 1 → one pick.

### F20 — WRONG-SCENE (legacy scenes): the departure applier throws away a live walker's approach the scene commit carries over

`persist/commit_background.py:3542-3545`
```python
            approach = scene.get("approach")
            if not isinstance(approach, dict) or "who" in approach:
                approach = scene["approach"] = {}
```
`persist/commit_scene_state.py:2262-2269` and `2304-2308` migrate the legacy single-mover `{"who": ...}` shape by CARRYING the walker over ("rather than dropping the walker mid-stride"); this copy drops it when the scene commit did not touch `approach` that beat. Legacy-shaped scenes only. **CONFIRMED** by trace, low impact. Fix: reuse the scene commit's migration. Test: legacy approach + a presence departure → the walker's record survives.

### F21 — CORRUPTION (multiplayer): the name-collision floor ignores co-player personas

`persist/commit_background.py:4912-4922` checks the primary persona and `chat_chars` only; co-players live in `chat_personas` (`agents/runtime.py:113-123`). The tracker's roster includes extra players (2207) and the name mint reserves them (`reserved=roster`, 2936-2937), but promotion does not, so a presence tracked before a co-player named "Bo" joined can be promoted to a second "Bo" sharing that player's `positions` key — the cross-mind failure the docstring itself names. **PLAUSIBLE.** Fix: add active `chat_personas` names to `taken`. Test: co-player "Bo" + presence "Bo" → `ValueError`.

### F22 — CORRUPTION (partial, under a warning that says "not applied"): warn-only excepts inside `commit_memories`' transaction have no savepoint

`persist/commit_memory_write.py:352-357, 377-419` catch and warn around `apply_witnessed_signals`, `record_dispute`, `record_memory_look`, `raise_importance`, `record_memory_access`; each writes row by row with `qi`, which inside a transaction executes on the outer connection with no savepoint (core/db.py:2414-2420). A raise part-way commits the rows already written with the turn while the warning reports the step as not done. **PLAUSIBLE.** Fix: wrap each guarded call in a nested `with transaction():` (a savepoint). Test: a helper that writes one row then raises → that row is absent after commit.

### F23 — DEAD: the `stance_updates` block has no producer

`persist/commit_memory.py:2285-2312`. `stance_updates` is not a `CharacterOutput` field and no prompt asks for it (`agents/common.py:1279-1288`: "legacy inputs commit still reads"); only `tests/test_resume_correctness.py` builds one. The `stance.log` it appends is never capped and has no reader. **CONFIRMED** (grep). Fix: delete the loop (keep the one-line `st["stance"]` seed if anything reads it).

### F24 — DEAD in production: three test-only entry points, one with a trap default

No production caller (grep of call sites): `pick_background_reactor` (4135-4142), `auto_promote_background_characters` (5482-5497; 13 test calls exercise this blocking form while the live path is `schedule_auto_promotion`), and `_consolidate_committed_memories` (commit_memory_write.py:23-73), reachable only through `commit_memories(consolidate=True)` — the DEFAULT (311). A new production caller of `commit_memories` silently runs utility-role consolidation in band (29.5 s measured, PIPELINE.md:563). Divergence from the job twin: parallel pool sized to the cast vs sequential, no cancellation, warnings vs logs. **CONFIRMED.** Fix: default `consolidate=False`; move the test-only forms to a test helper.

### F25 — STALE-DOC: four top-level claims about background presences

- CLAUDE.md § Architecture: "a stateless reaction per beat — no persistent memory or psychology". The record keeps a 4-entry conversation tail fed back to the presence's own call as `recent_interaction` (`_append_manager_conduct` 3306-3340 → `agents/background._recent_words`), a frozen `blurb`, `pending_reply`/`pending_act`, thread `last` lines; a charter body keeps its charter minds.
- CLAUDE.md / Design.md:653: `max_reactors` "hard ceiling 3" / "hard-clamped to 3". The setting is clamped (`agents/background.py:1111-1112`); the number of voice calls is not — precise addressees widen it without bound (4744), collapsing to a chorus only for one charter's crowd in one room. AGENTS.md:435 says so correctly.
- AGENTS.md:435: "`pick_voice_demand` qualifies on exactly four demands — addressed, owed, acting, emerged"; the code also qualifies on `place_addressed` and `arrived` (4528-4544); `pick_background_reactors`' docstring (4151-4157) lists four too. Same row: "One ear for every reader" — false for both gates (F17).
- Design.md:280: re-ask of a promise — false in the default path (F13).

### F26 — STALE-DOC: code comments that describe what the code no longer does

- `persist/commit_background.py:2093` — "docs/UNBUILT.md 1.18 keeps the residuals": §1.18 is the weather-exposure fallback; the naming residuals are UNBUILT_IDENTITY §1.89 (and §1.17).
- `:4190-4192` `addressed_rooms` — "other than the one they stand in": the unaimed-line branch (4271-4299) adds the speaker's own room.
- `:1637-1645` `_owed_clock_seconds` — "the same monotonic read `commit_memory` stamps affect and strain with": it reads after the scene commit (F10).
- `:2093-2094`/`2072-2074` `_mint_missing_presence_names` and `:187-193` `_mint_presence_uid` — "a rolled-back commit replayed lands the same name": only for a seeded uid; a record minted without an entity/charter binding takes `uuid4` (796-797), so its replay gets a new uid and a new name.
- `:2893-2896` — `intended_target` "which no prompt instructs and which measured null on every one of 189 reads": `agents/director.py:4736-4800` now backfills it from the speech spans.
- `persist/commit_memory.py:2100-2101` — "record_spatial_experience (below, line ~4100)": it is at 2321.
- `docs/design/DESIGN_LONG_TERM_GOALS.md:12-13` status header — "Boundary review is prompt-normative in v1, not engine-gated": its own v2 bullet and the code (`affect.project_boundary`, commit_memory.py:2111-2114, 2238-2242) are engine-gated.

## Efficiency

Cheapest and largest first. "Per beat" means every committed turn; none of these was timed. The hotness comes from the call counts traced here.

- **E1. `descriptor_bindings` is computed four or five times a beat** (`pick_voice_demand` 4377 via `_flow_addressed_refs`; `agents/background.py:1589` on the manager path; `track_background_presences` 2787; `select_auto_promotion` 5425 in the tail). Each call re-reads `scene` and `background_presences`, re-runs `_fold_duplicate_presences`, re-derives the charter overlay over the player's room plus ambient scope (`background_presence_records`, the registry the 2026-08-28 note measured at 41 MB / ~1 s a parse for a 307-body town), re-reads `planned_entities` and rebuilds `scene_person_entities`. **Gain:** compute it once at the gate and carry it on the `background_react` step. That one change removes three or four of these derivations every beat and is also the fix for F6.
- **E2. The same two blobs are parsed again and again.** `scene` is read about 10 times a beat in these paths (three times inside `track_background_presences` alone: 2229, 2483, 2813) and `background_presences` about 8 times (gate, background stage, `descriptor_bindings` ×N, writer, `promotable_background_presences`, `select_auto_promotion`, `_land_drafted_promotion`). `wget` parses fresh every time (core/db.py `wget`). **Gain:** use the existing `world_read_token` cache, or pass the parsed blobs down the stage. This is linear in blob size, and the scene blob is the largest row a story has.
- **E3. `_fold_duplicate_presences` runs on every load.** It costs O(records × entities) (`_entity_key_for_name`/`_entity_uid_answering_to` scan every entity for each record, plus `_bodies_answering_to` for each identity group), and there are about 10 loads a beat (E1/E2). `presence_record_for` → `_presence_lookup` is O(records) and is called inside per-reaction loops. **Gain:** memoise the fold on (ledger token, scene token).
- **E4. Belief reconciliation scans the whole bank inside the write lock.** `commit_memories` → `reconcile_inference_confidence` (commit_memory_write.py:368-373; mind/memory_inference.py:121-158) runs for every mind whose beliefs moved that beat. It selects all of that mind's inference rows and similarity-matches each against its hypotheses, all under the global write lock, and the bank only grows. This is the class UNBUILT §1.172 registers (a per-write cost that grows with the story, paid inside the commit) in another place. **Gain:** compute the `(confidence, id)` updates in `prepare_memory_commit` (the settled `st` is already in hand, and the fresh rows are in `pending_memories`) and only issue the UPDATEs inside the transaction.
- **E5. Per-line × per-hearer sheet re-parsing in memory preparation.** `_hearer_label` (commit_memory.py:319-322) runs `json.loads` plus `character_name` (a full sheet normalisation, story/character_schema.py:1878-1879) over every cast row, for every dialogue line × every hearer that does not know the speaker. `_own_pronouns_in_scene` (427-432) does O(cast²) sheet parses. `known` is read 2+N times (885, 956, and 1176 once per character). **Gain:** build a name→sheet map once per prepare (or use `character_name_from_text`, which is lru-cached for exactly this), and read `known` once.
- **E6. A promotion that fails to land is re-drafted every beat** (F5/F18). Two `utility` calls, ~27 s each per the C10 measurement, go out each active beat with no failure memory. **Gain:** record the refusal on the record (or the job) and skip re-selection until the name or the binding changes.
- **E7. A role-word `intended_target` fans out into N forced voice calls** (F2). One line aimed at "the trader" in a market of N traders costs N `character_bg` calls past the cap.

## Already registered

- **UNBUILT_PLATFORM §1.172** ("Every memory write scans the whole retrieval index"). `commit_memories` pays it on every commit through `delete_turn_memories` and `add_memories_batch`. E4 is a second instance of the same class and is not registered.
- **UNBUILT_LIVING_WORLD §1.95.** Promotion seeds recognition "unconditionally and mutually across the whole active cast" (`promote_background_character` 5224 → `seed_mutual_recognition(recognition_roster(...))`). The register describes this as the call's stated answer. It does not discuss what that answer implies: the player learns a presence name that was never given (the identity floor conceals presence names), and every active cast member, including ones in other rooms or frames, learns it too. `seed_mutual_recognition`'s own docstring calls it "arguing from the fiction ... rather than from any rule".
- **UNBUILT_IDENTITY §1.17** covers the generic-name crowd residual ("with three Daleks ... the first one to speak collects everything"). F8 is a different hole, since positions-only bodies are not counted at all.
- **UNBUILT_WORLD §1.71**: `nature` is asked only under `scene_life: ambient|full`. This is the residual cited by `presence_has_an_identity` / `presence_is_enrollable`.
- **UNBUILT_IDENTITY §1.89** (the minted name serves only the unnamed): the naming residuals of `_mint_missing_presence_names`. The docstring cites §1.18 instead (F26).
- **The consolidation job's restore-mid-LLM-call window** is recorded per `schedule_memory_consolidation`'s docstring. Its frame pinning (136), language pinning (137), cooperative cancellation between members (141) and cursor-based dedupe all hold.
- **AUDIT_COMMIT.md findings in these modules, re-checked:**
  - `auto_dialogue` is enforced nowhere: **FIXED**. `select_auto_promotion` 5420/5457 enforces it for unplanned persons, and its docstring matches.
  - English salience/durable-quote word lists: **MOVED TO PACKS** (`ja` populated). The durable markers are anchored. The salience cues are still bare substrings, which is a new defect (F9).
  - The two title lists: **FIXED**. `tests/test_background_presence_tracking.py::TestTheTwoTitleListsAreNotOneList` holds them apart.
  - The `world_entities.retired_turn_id` filter: **FIXED** (commit_common.py:575-578 dropped it, with a test).

## Structure notes

**`track_background_presences` (2177-3107, 931 lines). Phases:**
- 2200-2217: setup (roster, accumulators)
- 2219-2263: id→name map; scene read #1 (`_scene_now`); ubiquitous voices
- 2265-2288: harvest A, the `dialogue_log` speakers (+ `engaged_speakers`)
- 2290-2364: harvest B, entity defs. Builds sketches (`role_hint`, `station_room`, `_charter_ref`, `_plan_ref`, `_desc`).
- 2366-2463: harvest C, positions-placed bodies (inert / somebody verdict index)
- 2465-2481: harvest D, the background stage's fired lines (`beat_reactions`)
- 2483-2495: load + fold the ledger (scene read #2), then the charter overlay
- 2496-2576: resolve or mint per candidate. Binds the entity, records dialogue/engaged turns, merges the sketch, attaches charter/plan refs.
- 2578-2639: settle renders onto charter bodies and authored plans
- 2641-2671: blurbs, the conduct tail, charter conduct
- 2673-2702: **scene writes after the scene domain** (departures, handovers; F6, F11)
- 2704-2717: claims record/settle
- 2719-2736: mention counting (no roster check: F18)
- 2738-2930: debts and addressing (`descriptor_bindings`, the `pending_act` / `pending_reply` writers, `addressed_turns`); scene read #3
- 2932-2937: name mint
- 2939-3053: planning need + enrolment
- 3055-3082: the earned filter (F16)
- 3083-3101: abandoned debts, promotion proposals, threads
- 3102-3107: write

Natural seams are harvest (pure; returns candidates, ids, sketches), resolve/attribute, appliers (scene-writing, which belong before the `entities` domain), debts/addressing, and planning/enrolment.

**`pick_voice_demand` (4313-4756) has a near-duplicate.** `agents/background._demanded_presences` (1548-1700) re-implements the same trigger set, and the two have already drifted. `owes_act` exists only there (F13), `arrived` only here, routed seeding only here, and neither passes the presence's ear (F17). This is the strongest seam in the file: one trigger evaluator that both gates call, with the cap and overflow policy left to each caller.

**`promote_background_character` (4929-5331, 403 lines)** runs in this order: resolve (4954-4985), sheet + charter handoff (4986-5013), rows (5015-5055), relationship graph ×2 near-duplicate blocks (5057-5167), scene position / vitals / attire (5169-5216), recognition (5218-5226), memories (5228-5258), greeting claim (5260-5267), charter binding (5269-5280), ledger cleanup (5282-5329). It should split into a pure prepare plus one transactional apply (F5).

**`prepare_memory_commit` (809-2532, 1,723 lines)** is the module's monolith; the per-character loop body alone is about 1,500 lines (959-2467):
- 874-911: name learning
- 1082-1160: the unbidden ledger
- 1169-1278: heard lines and the promise row
- 1279-1287: witnessed signals
- 1288-1392: the episode
- 1394-1414 and 1465-1537: own conduct (the alpha-9.5 fix, pinned by `tests/test_own_conduct_memory.py::test_a_speaker_remembers_having_spoken_even_with_a_view` and `tests/test_a_mind_remembers_what_it_did.py`)
- 1541-1571: inference memories
- 1572-2243: the interior-depth block, ~670 lines: capacity, intentions, projects, appraisal, affect/hedonic/stress, leak tripwire, `active_state`, notebook, project service/probation/boundary, drive strain/rupture
- 2244-2312: tells, carriage, the dead stance block
- 2313-2378: space, place purpose, mind models
- 2379-2422: relationship ops, disputes, importance, recall
- 2423-2467: memory affect stamping + `about`

Each region already reads like a function with `st`/`own_result`/`sc` in and deferred ops out.

**`commit_background.py` (1,476 → 5,731 lines since the split)** has seven separable areas:
1. presence identity: uid, lookup, fold, charter overlay, emergence/absorption (171-1083)
2. address/channel readers (1086-1626, 3556-4067)
3. promises/debts (1629-1849)
4. the tracker (2177-3107)
5. handovers/departures/threads (3109-3553)
6. the gate (4070-4756)
7. promotion (4758-5731)

**Module-level mutable state:** `_BACKGROUND_NAME_TITLE_WORDS` (93) is a mutable `set` with no writer (it could be a `frozenset`). There are no `global` rebinds in any of the four files.

**Other notes:**
- `commit_memory_write.py`'s `_consolidate_committed_memories` and the job twin are two copies of one loop (F24).
- `commit_skip.py` is small and coherent; the frame-status read is its one defect (F12).

## Docs checked

| Claim | Where | Holds? |
|---|---|---|
| `pick_background_reactors` returns `[]` for most turns; no model call when the gate says no | CLAUDE.md, PIPELINE.md:1112 | **Holds** for `scene_life: off` (`agents/background.py:1138-1141` returns with no call). Under ambient/full the manager runs by design. |
| `max_reactors` default 1, hard ceiling 3 | CLAUDE.md, Design.md:653 | **Partly.** The setting is clamped, but the call count is not (F25). AGENTS.md:435's "forced past the cap" is accurate. |
| A background presence is stateless, with no persistent memory | CLAUDE.md | **No** (F25: the `recent` tail, blurb, debts, threads) |
| `pick_voice_demand` qualifies on exactly four demands; one ear for every reader | AGENTS.md:435 | **No** (F25, F17) |
| A promise is re-asked until `hands_over` | Design.md:280, DESIGN_CONVERSATION_THREADS.md:37 | **No** in the default path (F13) |
| Slow memory preparation, embeddings included, before the write lock | CLAUDE.md | **Holds.** Embeddings are batched once a beat (2489) and links are pre-lock (2513). The belief reconcile is the exception (E4). |
| All primary turn mutations in one outer transaction across "twenty domains" | CLAUDE.md | **Holds.** The count is now 21 (`skip_lives` added; commit.py:561-671). |
| `commit_memories`: one transaction | AUDIT_COMMIT §2 | **Holds** (316-425), with the warn-only partial-write caveat (F22) |
| Consolidation out of band, frame + language pinned, cancellable | PIPELINE.md:563, docstring | **Holds** |
| `commit_skip_lives` runs after `scene`, before `entities` and `cast` | commit_skip.py docstring | **Holds** (commit.py:572/581/585/590) |
| Projects: drive weight 1.0 established / 0.8 probation; seeding deduped on text + id; one-beat `project_review`; persistence via `_interior_out` | DESIGN_LONG_TERM_GOALS.md "Decided in v1" | **Holds** (1614-1656, 1755-1768, 2096-2114, 2204-2243). The status header (lines 12-13) is stale (F26). |
| Own-conduct rows always minted beside the episode | AUDIT_COMMIT §2; the code comment | **Holds**, test-pinned |
| Empty-view floor: an "unspecified area" view mints no row | code comment 1303-1322 | **Holds** for both halves (1321, 1341) |
| `prepare_memory_commit` reads no other mind's state or raw Director event | brief question (4) | **Mostly holds.** See below. |

Details for the last row. Other cards are read for appearance (F4, the leak) and pronouns (engine-side grammar only). `resolved_event` is read only by `_evidence_ok` (1661-1668), which validates a cited string against omniscient prose rather than the mind's own view. That is lax, but nothing is delivered from it, so it is not a leak. Witnessed signals are gated by the mind's own view (`_witnessed_signals`).
