# Audit: world/charter core (charter_runtime, charter, charter_model, charter_identity, charter_roster, charter_figure)

Auditor run 2026-11-01, tree at `84f3de23` (worktree-jev-character-tracking, clean). Read-only; one
pytest run (profiling), snippets on `.venv/bin/python` (pure functions, or `core.db.q`/`registry_for`
monkeypatched in-process), read-only `sqlite3 file:engine.db?mode=ro` measurements.

## Scope read

Read in full, line by line:
- `world/charter_runtime.py` 1-5866 (all 117 defs).
- `world/charter.py` 1-524, `world/charter_model.py` 1-971, `world/charter_identity.py` 1-1270,
  `world/charter_roster.py` 1-134, `world/charter_figure.py` 1-140.

Read in part, to trace callers/consumers (not audited as a whole):
- `core/db.py` 2309-2440 (conn/transaction/qi), 2993-3160 (wget/wset, read tokens, `_wset_encoded`).
- `core/jobs.py` 1-330 (submit, `_clear_turn_scoped_context`, `_run`).
- `persist/commit.py` 540-700, 820-880 (session scope, `schedule_charter_ticks` call site).
- `world/offscreen.py` 560-600, 1023-1140 (`_beat_context`, `advance_epoch`).
- `world/mechanics.py` 480-530, 699-830; `story/carriers.py` 131-300; `agents/character.py` 3456-3480, 4630-4645;
  `agents/background.py` 3095-3200; `world/charter_skip.py` 400-570; `world/charter_ops.py` 94-110, 255-300;
  `world/charter_surgery.py` 272-327; `world/charter_promote.py` 230-260, 381-460; `world/charter_social.py`
  430-460, 483-497; `world/charter_news.py` 40-80, 440-500; `world/charter_talk.py` 330-352;
  `world/charter_generate.py` 455-470, 630-660, 850-945; `world/structure.py` 1059-1086, 1362-1420;
  `agents/director_lots.py` 280-380; `story/plot_packages.py` 1710-1746, 4065-4150; `story/greetings.py`
  720-790, 995-1075; `persist/commit_background.py` 5050-5150; `web/app.py` 6140-6215;
  `tools/project_check.py` 2505-2620, 2708-2900; `world/charter_run.py` 150-192.
- Design/registers: AGENTS.md 30-250 and the charter routing rows; `docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`
  §7a (255-310); `docs/UNBUILT_LIVING_WORLD.md` 769-860, 1213-1340; `docs/UNBUILT_WORLD.md` 3537-3612.

Skimmed only (not audited): `docs/design/DESIGN_CHARTER_*.md`, `DESIGN_CREATURES_AS_CHARTER.md` (grep).

## Findings

### Answers to the assignment's six questions (pointers into the findings below)

1. **Cache coherence.** `_REGISTRY_CACHE` is keyed `(cid, storage_key)` (the frame/era-scoped world key from
   `world_read_token`), validated by `(world_epoch, per-row write gen)`; LRU of 2. Reads are coherent: the token
   is read before the fetch, `_wset_encoded` bumps after the write and re-bumps at the end of every outer
   transaction (`core/db.py:3121-3127`, `2387-2394`), DB swaps/restores/raw deletes bump the epoch. The cached
   object is never mutated by the in-scope readers I traced. `_IDENTITY_INDEX` is rebuilt lazily on the first
   `identity_index()` call against a NEW cached parse (object identity + token), pruned only on the next store;
   any non-cached registry (update copy, **commit-session copy**, job copy) gets a fresh uncached index on every
   call (E8). The real hazard is WRITES: `save_registry` outside a commit session is last-writer-wins with no
   token check, and background read-modify-write writers exist (F7). `land_snapshot`/`land_presim` are the only
   writers with optimistic concurrency (revision re-check inside the transaction). `_REGISTRY_SESSION` is a
   turn-scoped contextvar that `jobs._clear_turn_scoped_context` does not clear and `project_check`'s guard
   cannot see (it scans only `llm/providers.py`, `core/pipeline_context.py`); no job is submitted inside the
   session today (all `schedule_*` run after `persist/commit.py:556-695`), but extension commit domains run
   inside it (Structure notes).
2. **Onscreen minds and offscreen bodies.** Three leaks of the "name/fact with no channel" class: F1
   (`presence_view` gives one voice two bodies' private slices), F2 (charter event surfaces built from engine
   body keys become cast members' firsthand claims), F3 (promotion maps hearsay judgment subjects to display
   names). Director-only apertures (`charter_moves_since`, `residue_facts`, `charter_dwellings`,
   `figure_answers`) carry names/keys to the Director only, which is not a firewall breach.
3. **advance_snapshot caps/determinism/budget.** Caps, all named (owner's to rule): `MAX_CATCHUP_HOURS` 720,
   `MAX_PRESIM_HOURS` 17520, `DEFAULT_PRESIM_TAIL_HOURS` 96, `PARALLEL_PRESIM_HOURS` 168,
   `CHARTER_BUDGET_SECONDS` {beat 10, time_skip 60, presim None}, `_window_hours` clamp [0.25, 24],
   presim coarse window `max(8.0, w)` / tail `min(4.0, w)` (inline, 1353/1360/1384/1392),
   `CROSS_CHARTER_GOSSIP_CAP` 8, `CAST_HISTORY_REQUEST_CAP` 16, `GENERATION_LORE_LIMIT` 48 (+ inline `LIMIT 4`
   rule rows, 1582), `_REGISTRY_CACHE_CAP` 2, `SALVAGED_PLANS_KEPT` 1, inline `[:8]` default tail places (2421),
   `[:24]` naming register (2134), `[:3]` place ledgers (3838), `cap=8` moves lines and `[-200:]` act keys
   (3846/3940), `cap=3` residue facts, `LIMIT 500` diagnostics events (4015), `[:6]` action instances (5167),
   `[:2]` presence bodies (5198, see F1), presim workers `cpu_count-1`; in charter_model `EXPERIENCE_CAP` 4000,
   habits 4, cadence [4, 720], `carried_events[-64:]`, `heard[-32:]`, `refused_interventions[-24:]`; in
   charter_identity `NAME_RUN_FLOOR`/`NAME_PREFIX_FLOOR` 4, `NAME_ELEMENT_FLOOR` 2, `NAME_SIMILARITY_FLOOR`
   0.88, allocator `attempts=max(32, 2N)`, `lane_attempts<=64`, enumerable space 1024; charter_roster
   `TRUST_FLOOR` 0.2, `DECAY_PER_HOUR` 0.004, `ARCHIVE_FLOOR` 0.05.
   Budget: in the solitary path a stopped `run` lands the partial state and `last_elapsed_seconds` from the
   clock actually reached; untouched charters keep theirs; the shortfall is CARRIED (verified 3221-3282). The
   720 h cap also carries (it is not a truncation, despite the comment at 103-105 saying "720 simulated hours
   is what the design says is worth catching up on"). The creature (`together`) path takes no deadline
   (documented, §7a) and ignores the time-skip grid and seed (F10). Determinism: seeds are keyed by charter
   (`stable_event_key(beat_id, key)`, `skip_seed`), presim seeds by sorted index, parallel presim
   byte-identical; it breaks only where the wall-clock budget binds (documented) and in F10.
   **Hours per beat as it stands:** `delta = (story elapsed at beat end - last_elapsed_seconds)/3600`, story
   elapsed from `offscreen.advance_epoch` (`beat_elapsed_seconds = _as_seconds(clock)`, cumulative). Correct.
   Measured on engine.db (read-only): chat 175 story 440 s over 14 beats, every charter at
   `clock_hours` 720.12 and `last_elapsed_seconds` 440.0 -- the town tracks the story clock exactly; the rate
   (~31-39 s of story per beat on chats 150-175) is the story clock's, not this module's. The one place the
   mapping breaks is F4.
4. **Story clock vs wall clock.** No mixing found: wall clock is used only as the advance deadline
   (`time.monotonic`) and the salvage timestamp. The charter-hours <-> story-seconds pairing (`clock_anchor`,
   `anchor_charter_day`) is broken by F4 (mid-story landing at 0.0).
5. **Deferred imports.** None of the 133 hides a package cycle that `tools/package_edges.json` lacks:
   charter_runtime's cross-package edges are `world->core` (eager+deferred), `world->mind` and `world->story`
   (deferred here, but both already eager elsewhere in `world`). The baseline computes cycles on EAGER edges
   only: measured, eager SCC = {agents, persist, story, world}; eager+deferred SCC = 11 packages (agents, core,
   dressing, extension_runtime, language_runtime, llm, mind, persist, story, web, world). No `world/` module imports
   charter_runtime at module level, so the ~70 intra-`world` deferrals are not cycle breakers (Structure notes).
6. **Slow tests.** Profiled the same workload in-process (twin_towns(40), window 4): see E1/E2. The year test is
   superlinear because `_remember_experience` copies and re-sorts each body's whole experience list on every
   insert and `normalize_charter` copies every experience row at the head of every `step`; per-240 h chunk cost
   rose 1.46 -> 1.93 -> 2.50 -> 2.98 s as mean experiences/body rose 72 -> 133 -> 192 -> 253.

---

### F1 — `presence_view` hands ONE background voice the private slices of every same-named body in the room
- Severity: **LEAK**. Confidence: **CONFIRMED** (reproduced).
- Where: `world/charter_runtime.py:5066` `for charter_key, body_key in _body_refs(registry, name=name):` ...
  `5198 return out[:2]`; consumer `agents/background.py:3134-3155` puts every returned entry into the voice
  payload (`shown_context`).
- `_body_refs(..., name=)` matches by body key, stored name or display name across ALL charters; `presence_view`
  ignores the presence record's exact `charter_refs` (which `apply_presence_conduct:5729` and
  `promotion_bundle:5789` both pass, and both REFUSE when `len(matches) != 1`).
- Scenario (reproduced): charters `inn` and `mill` each hold a body named "Ada Fenn", both standing in `square`.
  `presence_view(1, "square", "Ada Fenn")` returned `[('inn','tapster:0001'), ('mill','miller:0001')]`, and the
  one voice received both `can_bring_up` lists: "INN-ADA'S PRIVATE: the reeve skimmed the granary" and
  "MILL-ADA'S PRIVATE: I set the kiln fire myself". Two people sharing a head -- exactly what the firewall
  forbids. Cross-charter display-name collisions are not prevented (the allocator's `used` set is per charter;
  `registry_warnings` checks collisions per charter only), and a persisted presence record outlives the beat
  in which its name was unique (`background_presence_records` withholds ambiguity only at record creation).
- Verified: snippet with `cr.registry_for` patched to a normalized two-charter registry (output above); traced
  `agents/background.py:3134-3155`.
- Fix: pass the presence record's `charter_refs` into `presence_view` and resolve with `refs=`; return `[]`
  when the match is not exactly one, the rule the two other `_body_refs` callers already keep. Test: two
  charters, same display name, same room -> `presence_view` returns at most the ref'd body (or nothing).

### F2 — Charter event surfaces built from engine body KEYS become a cast member's firsthand claim
- Severity: **LEAK** where a body key is a name (authored registries; the repo's own fixtures key bodies
  "ilse", "raul"), **WRONG-SCENE** otherwise (generated keys are `{post}:{NNNN}`). Confidence: **CONFIRMED**
  (traced end to end; surface text pinned by `tests/test_charter_ordinary_evidence.py:287`
  `_event_surface(event) == "ilse gave aid to raul"`).
- Where: `world/charter_runtime.py:2838-2896` (`_event_subject`/`_event_surface` read `upkeep|post|body|actor`
  keys and `subject`), `2939-2945` (`public = _event_surface(event) if kind in WITNESSABLE`; payload `what`,
  `witnessed`). Consumer: `story/carriers.py:229,263-287` stores `"claim": witnessed` verbatim on any cast
  member (and the player persona) standing in the room; `agents/character.py:4636-4643` hands it to the mind;
  `tellers_as_known` (3456-3480) relabels only `told_by`, never the claim text.
- Scenario: a charter `harm_done` (`body: "warden:0001"`, `subject: "cook:0003"`) fires in the chapel; a cast
  member who walks in later acquires the claim "warden:0001 caused harm to cook:0003". With an authored
  registry keyed by name, the cast member learns "ilse" and "raul" without any channel. The same class was
  fixed for charter-held news in `carrier_entries` (4121-4136, "never by key ... a registered character told
  one would have kept the key as what it heard") but not on the scheduled-row rail.
- Fix: carry the parties structurally on the payload (charter, body keys) and render the claim per observer at
  acquisition (known name via the `known` ledger, else the stranger label/appearance), as `tellers_as_known`
  does for tellers. Test: a charter `aid_given` between two unmet bodies lands in a room; a cast member
  acquires it; assert the claim contains neither key nor name.

### F3 — Promotion names people the promoted body only ever heard ABOUT
- Severity: **LEAK**. Confidence: **PLAUSIBLE** (traced, not executed).
- Where: `world/charter_runtime.py:5799-5807` `social_names = dict(identity_index(registry).display(charter_key).deal_all())`
  ("the whole town's address book"); consumer `persist/commit_background.py:5066-5072`
  `target = str(social_names.get(subject) or subject)` writes a relationship edge under that DISPLAY NAME for
  every `social_judgments` subject; `charter_promote.promotion_handoff:398` takes judgments about ANY body.
- Scenario: H hears from Z (`charter_talk`, hearsay weight) that X accused somebody; `update_judgments_from_minds`
  forms H->X; X is not in `_members_known_to(H)` (H holds no claim keyed by X). The charter's own voice for H
  calls X "a house hand" (`_member_namer`), but after promotion H's relationship graph holds X's full name and
  the character payload names X. Same for a judgment that outlived a decayed/capped sighting claim.
- Fix: map a judgment subject to its name only when the subject is in `_members_known_to(state, body_key)`
  (the rule `acquainted` already uses); otherwise the post words. Test: promote a body with a hearsay-only
  judgment; assert the graph target is not the subject's display name.

### F4 — A location added mid-story lands its prehistory at story second 0, so its first beat re-lives the whole story and fires the history as pending events
- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (reproduced).
- Where: `world/charter_runtime.py:1501` `item["last_elapsed_seconds"] = 0.0` (presim_registry);
  `2466-2471` `land_presim(..., now_seconds=story elapsed)` uses `now_seconds` only for history `due_at`;
  `3226-3233` the next `advance_snapshot` computes `delta = elapsed - 0.0`. `clock_anchor` 4205-4217 claims
  "`last_elapsed_seconds` is stamped 0.0 when presim lands ... so the two always describe the same instant"
  -- true only for a turn-0 generation.
- Reproduced (small_town and twin_towns(40), `_story_day` stubbed): presim 48 h, landed with
  `last_elapsed=0.0`; the story had run 50 h; ONE 60-second beat then advanced the new town **+50.02 h**, and
  the twin_towns run produced a `pending` scheduled row dated before the beat began (it fires at the next
  sweep as if happening now -- the defect `land_presim`'s "HISTORY, NOT DUE" comment fixed for turn 0).
  `generate_lived_location` is the production op for Dialogue Config and the lorebook workspace on a running
  story (AGENTS.md; its own docstring: "adding a spaceport halfway through a story").
- Also: `land_presim:2566` takes `horizon = max(clock_hours)` over the WHOLE landed registry (existing charters
  included), so when an existing charter is further along, every new history row's `due_at` is backdated by
  the difference (only `charter_diagnostics` reads history rows; low).
- Fix: stamp `last_elapsed_seconds = now_seconds` (and `last_epoch_id`) when landing; compute each history
  row's `due_at` from its own charter's end clock. Test: generate on a story at elapsed E>0; first beat
  advances by the beat's own seconds; no pending row has `due_at < E`.

### F5 — `transfer_person` addresses a person by a bare body key that the module itself says is not unique
- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (reproduced).
- Where: `world/charter_runtime.py:272-283` lifts from EVERY item whose `bodies` holds `body_key` (keeping the
  last), `285` reads a hermit by bare key, `294` stores a hermit at bare key, and never pops that hermit entry
  on re-employment (296). Production callers: `world/charter_ops._transfer` (`arrive`/`depart` ops,
  258-287, `_employer_of` returns the first match). `person_id` docstring 162-167: "two independently
  generated charters in the same story both produce `tech:0001`" (generated keys are `{post}:{NNNN}`,
  `charter_generate.py:649`).
- Reproduced: inn `cook:0001`=Ada and tavern `cook:0001`=Bel; `transfer_person(reg, "cook:0001", "market")` ->
  inn [], tavern [], market {cook:0001: Bel}, people {market/cook:0001: Bel}: **Ada erased**, the wrong
  person moved. Hermit round trip: depart -> `people` {cook:0001}; arrive -> {cook:0001, market/cook:0001};
  stored and renormalized -> the hermit copy survives beside the employed one (one person stored twice).
- Fix: take `(charter_key, body_key)` (a person id) and pop the hermit entry when re-employing; refuse an
  ambiguous bare key in `charter_ops`. Test: the two cases above.

### F6 — A charter key containing "/" rewrites every body key on the first save/read round trip
- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (reproduced).
- Where: `person_id` 173 `"%s/%s" % (charter_key, body_key)`, `_body_of` 178 `split("/", 1)[-1]`;
  `normalize_registry:361-363` rejoins stored people through `_body_of`. Charter keys are not sanitized:
  `charter_generate._key` (459-461) only strips, `_remap_generated_town:1847` keeps the model's key, the
  charters editor saves any key. Same assumption at `charter_generate.py:1696` and `_generate_lived_location:2455`.
- Reproduced: item `"north/south ferry"` with body `cook:0001` -> `_stored_shape` -> json -> `normalize_registry`
  -> bodies `['south ferry/cook:0001']`. Watch, bindings, minds and judgments keyed by the old key no longer
  match (watch is filtered to bodies at `charter_model.py:619-623`).
- Fix: escape or forbid the separator in charter keys at `normalize_registry` (slug it) or split on the LAST
  "/" with body keys guaranteed slash-free. Test: round-trip a registry whose charter key contains "/".

### F7 — `save_registry` outside a commit is last-writer-wins; background read-modify-write writers can revert a landed advance or a commit's charter writes
- Severity: **CORRUPTION**. Confidence: **PLAUSIBLE** (race; window traced, not reproduced).
- Where: `world/charter_runtime.py:810-823` (`registry_for_update`: unlocked read), `964-996` (`save_registry`:
  no token/revision check). Unguarded RMW callers: `agents/director_lots.deal_berths:306-331`, called from
  `expand_lot:372` in the lot-expansion job with no `transaction()`; `world/region_events.apply_wave:321-388`
  when reached from `story/plot_packages.fire_due_clocks` -> `advance_region_waves:3158` (called at
  `persist/commit.py:815`, after the commit transaction, with no `transaction()`); `web/app.py:6142` (editor
  posts a whole registry). Guarded: `publish_package` (inside `transaction()`, 4122), the commit session
  (parsed inside the commit transaction), `land_snapshot`/`land_presim` (revision re-check under the lock).
- Scenario: `deal_berths` parses the registry; the charter tick job's `land_snapshot` lands (hours of town,
  `last_elapsed_seconds`, scheduled rows); `deal_berths` saves its stale copy -> the advance is reverted while
  its scheduled_events rows stay; the next advance re-lives the span on a different seed and mints a second,
  different set of rows for the same story time. Same with a turn commit's flushed placements/evidence/carrier
  claims landing inside the window. Window = parse+normalize+write (~0.1 s at 0.9 MB, seconds at the 41 MB
  measured registry).
- Fix: give `save_registry` an `expected_token` (the `world_read_token` captured by `registry_for_update`) checked
  under the write lock, or make out-of-commit writers run their RMW inside `transaction()`. Test: interleave a
  `land_snapshot` between `registry_for_update` and `save_registry`; assert refusal.

### F8 — A salvaged plan plants the new story's rooms under the DISCARDED story's canon book
- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (traced).
- Where: `_PER_CHAT_REQUEST_KEYS = ("owning_lorebook_id",)` (562) excludes the per-chat book from the
  fingerprint by design; but the artifact stores the resolved `owning_book` (2062-2081, 2273-2276) and
  `_generate_lived_location:2361,2399-2401` plants with `owning_book_id=artifact["owning_book"]`, never the
  current request's. `story/greetings.py:1029` sets a NEW `owning_lorebook_id` per chat;
  `tests/test_a_failed_start_keeps_what_it_paid_for.py:166-175` adopts 101's plan for a request saying 102.
- Effect: `room_registry.owning_book_id` (dedup scope `commit_room_registry._registry_alias_index`, destruction
  cascade `commit_destruction:150-165`, archive `bookmap.get` -> NULL at `chat_archive.py:1123`) points at a book
  of another chat; deleting the failed-setup chat SET-NULLs them (`core/db.py:1254`); the phonology entries
  (`_record_phonology`) were written into the old chat's book too.
- Fix: on adoption recompute `owning_book` (and the phonology write) from the current request/chat. Test:
  extend the salvage end-to-end test to assert planted rows carry the second chat's book.

### F9 — A transfer silently drops the person's `walked` routes
- Severity: **CORRUPTION** (low). Confidence: **CONFIRMED** (reproduced).
- Where: `PERSON_STORES` (152-156) omits `walked`, a per-body store (`charter_model.py:941-948`, "the one record
  a promotion can hand over as EARNED routes"); the exclusion list in the comment names only `commitments`
  and `politics` (registered §1.99d), not `walked`.
- Reproduced: `walked {ada: {kitchen: {yard: 7}}}` at inn; transfer to market; after normalize: market
  `walked {}`, inn `walked {}` (stood carried, walked lost).
- Fix: add `walked` to `PERSON_STORES` (or note why not). Test: transfer keeps `walked`.

### F10 — A time skip in a registry holding a creature is stepped on equal windows and the epoch seed (and with predation), not on the grid the cast lived
- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** (traced).
- Where: `advance_snapshot:3248-3251` (`if together: prepared[key] = ...; continue`) runs BEFORE the
  `context == "time_skip"` branch (3252-3263); the together path (3294-3308) uses `min(window_hours)` and
  `stable_event_key(epoch_id, k)` seeds. The cast's skip (`world/charter_skip._TownRun`, 406-426, 495-560)
  steps every charter separately with `step` on `skip_windows` and `skip_seed`, no `run_registry`.
- Effect: AGENTS.md's property ("the town the story stores [is] the town every asked mind lived in") fails for
  any creature story: residents the cast saw at window edges are elsewhere in the stored town, and a kill the
  stored town contains is in no cast memory. Same failure, any registry, for skips longer than
  `MAX_CATCHUP_HOURS` (720 h): the remainder is advanced on later ordinary beats (equal windows, epoch seed).
- Fix: either run the skip grid/seed through `run_registry`, or have `live_in_charter` run the same predation
  rounds; for >720 h, carry the skip context with the shortfall. Test: creature registry + time_skip context ->
  window edges equal `skip_windows`.

### F11 — A new location's generic rooms merge into ANY unlanded planned room of the same name, in another building
- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** (reproduced).
- Where: `_merge_generated_rooms_by_name` (1632-1702), used at `_remap_generated_town:1776`; the SQL takes every
  unlanded, unretired `room_registry` row of the chat with no structure/building scope; merged rooms are dropped
  (1807-1808) and every `place`/`berth` re-keyed to the planned room (1852-1859).
- Reproduced (`core.db.q` patched): planned unlanded `manor_kitchen` "Kitchen"; generated inn rooms ->
  `{'lamb_flag_kitchen': 'manor_kitchen', 'lamb_flag_hall': 'manor_great_hall', ...}`: the inn's cook now works
  in the manor's kitchen. Also language-dependent: tokens are `[^a-z0-9]+` plus an English stop list
  `{"the","a","an","of","and","s"}`, so a Japanese name only ever merges on the exact folded form
  ("境内 神社の" vs "神社の境内" not merged while the English equivalent is) -- a recogniser that works only for
  English.
- Related, narrower case registered: UNBUILT_WORLD §2.44 ("A dealt sibling name can coincide with an unlanded
  planned room's name elsewhere ..."). Generic planner-written names (Kitchen, Cellar, Yard) are the common case
  and are not registered.
- Fix: scope the merge to the generated town's own structure/lot (or to rooms the request names); compare
  normalized forms with a script-neutral normalizer. Test: planned unlanded "Kitchen" in structure A + new town
  with "Kitchen" -> no merge.

### F12 — `heard_from` holds a body key on one path and a display name on three; report checks and judgments key by it
- Severity: **WRONG-SCENE** (stances on a phantom subject; trust weighting ignored). Confidence: **CONFIRMED**
  (traced, not executed).
- Writers: `charter_mind.hear:97` `heard_from=speaker` (body key, ordinary talk); `charter_talk.py:348`
  `heard_from=source_name or subordinate` (display name, formal reports); `charter_runtime.cross_charter_gossip:3632`
  `heard_from=speaker["name"]` (display); `deliver_errands:3053` `copy_["heard_from"] = walker display name`.
- Readers expecting a body key: `charter_social.py:441-445` `regard_value(regard, holder, source)` (display name
  -> neutral regard); `charter_news.check_reports:451-484` mints `check:{subject}:{teller}` with
  `about/actor = teller` -> `update_judgments_from_minds` forms `judgments[holder]["<display name>"]`, a
  subject that is neither a body nor a figure, so `judgment_view(subjects=bodies+figures)` (promotion) and
  ties never see it; `charter_promote.py:249` renders "heard from hostler:0003 that ..." for the key form.
- Fix: one vocabulary (the teller's body key, or a qualified person id across charters) at every writer;
  render names only at the voice. Test: a formally reported claim later refuted produces a stance keyed by the
  subordinate's body key.

### F13 — `charter_moves_since` snapshots places by DISPLAY NAME, not identity
- Severity: **WRONG-SCENE** (low). Confidence: **PLAUSIBLE**.
- Where: `charter_runtime.py:3889-3897` `places[shown] = place` / `prev_places.get(shown)`; persisted by
  `persist/commit_mapping`.
- Two bodies sharing a display name collapse into one entry (phantom "came into X from Y" lines); a display
  change (home post changes at succession, `title_for` uses the post title) makes the body vanish from the
  comparison for a beat. AGENTS.md: "The Charter/body dict key is permanent identity".
- Fix: key the snapshot by `charter/body`; keep the shown name only in the line. Test: two same-named bodies,
  one moves -> exactly one line.

### F14 — A body named by its own key counts as named forever; a law that cannot mint, or arrives later, names nobody, and nothing warns
- Severity: **SILENT-NOOP**. Confidence: **CONFIRMED** (reproduced).
- Where: `charter_identity.materialize_body_names:1097-1107` (no candidate -> `name = body_key`);
  `generated_name_parts:341-342` returns "" without a GIVEN source even when the format is `{family}`
  (`_stored_name_components:386-389` explicitly supports family-alone laws); `charter_model.normalize_body:243`
  `"name": str(entry.get("name") or key)`. The generator treats a key-name as unnamed
  (`_plan_lived_location:2231-2241`); the allocator treats it as named -- two notions of "named".
- Reproduced: no law -> names `cook:0001`, `cook:0002`; law added later -> unchanged; family-only law
  (`{"family": [...], "name_format": "{family}"}`) -> `cook:0001`; `registry_warnings` says nothing about names.
- Fix: treat `name == key` as unnamed in the allocator (or warn), and mint family-alone names when the format
  addresses by family alone (or warn that the law cannot mint). Test: the three cases above.

### F15 — Selecting more than 48 lore entries is refused as "outside the selected book"
- Severity: **SILENT-NOOP** (a false refusal; the author is told the wrong cause). Confidence: **CONFIRMED** (read).
- Where: `generation_lore:1555-1563` adds `LIMIT bounded` (≤ `GENERATION_LORE_LIMIT` 48) to the
  selected-entries query; `1602-1603` raises "one or more lore entries are outside the selected book" when
  `len(rows) != len(set(selected_entries))`. Reachable from `POST /api/chats/{cid}/charters/generate` with
  `lore_entry_ids` (web/app.py:6160-6175, body passed through).
- Fix: check membership without the LIMIT (or say "at most 48"). Test: 49 valid ids -> no false refusal.

### F16 — "The pure prefix ... no writes" is false; three writes precede the boundary
- Severity: **STALE-DOC** (with a residue consequence). Confidence: **CONFIRMED**.
- Where: `_plan_lived_location:2024` docstring; `_generate_lived_location:2350-2352` "Everything above is pure
  -- two model calls and no writes"; `_fail_job:1994-1996` "BEFORE THE BOUNDARY ... nothing was written".
  Writes before `planned`: `_prepare_cast_histories:1235` (`character_history_routes`),
  `ensure_chat_canon_book` (2072, mints a book), `_record_phonology:2272/2324` (`add_lore`). A retry with a
  changed request re-plans and files a second phonology entry per charter (titled with the PRE-remap key),
  which `story.naming.phonology_lanes` reads as a lane.
- Fix: correct the comments; move the phonology/route writes after the boundary or make them idempotent.

### F17 — The cost claims the caps were ruled on are stale by ~5x, and one points at a register section that does not exist
- Severity: **STALE-DOC**. Confidence: **CONFIRMED** (measured).
- `MAX_PRESIM_HOURS` comment 49-52: "~1.8 ms per simulated hour on a 40-body charter, so a full year is about 16
  seconds". Measured twin_towns(40), window 4: 240 h chunks 1.46/1.93/2.50/2.98 s = 6.1-12.4 ms/h and rising;
  the suite's year test (window 8) is 95.7 s. `tests/test_charter_ordinary_evidence.py:445-447` says the year
  "costs 17 seconds"; the quarter now costs 27 s.
- `charter_model.py:495-504`: "a row is ~324 bytes ... At this cap [4000] a body holding a full life costs well
  under a megabyte": 4000 x 324 B = 1.30 MB.
- `presim_registry:1466` "the profile that would is `docs/UNBUILT.md` 1.99h" -- no §1.99h exists (1.99-1.99f).
- Fix: re-measure and restate; point at a real section. The owner's caps (720 h, 17520 h, 10 s) were argued
  from these numbers.

### F18 — Smaller stale claims
- Severity: **STALE-DOC**. Confidence: **CONFIRMED**.
- `world/charter.py:18-19` "forty-one `charter_*` siblings": there are 42 (29 re-exported is right).
- `JOB_STAGES` (470) lists `presimmed`, `done` (never written) and omits `planting` (written at 2369);
  `PAST_BOUNDARY_STAGES` (476) carries the unwritten `presimmed`.
- `_split_person_state` docstring 184-186 names `absorb_view` as a live caller (it has none, F19).
- `_presim_together:1377-1379` "a charter that never meets a creature replays as it did alone" -- only when
  every charter's `window_hours` is equal (together uses `min(windows)` for all).
- `presim_registry:1452-1455` "`cross_charter_gossip` is the barrier afterwards" -- it never runs after a presim
  (only per in-play advance, 3335-3336), so a month of prehistory exchanges nothing between institutions.
- `CHARTER_BUDGET_SECONDS` comment 103-105 reads as a truncation at 720 h; the remainder is carried.

### F19 — Dead code
- Severity: **DEAD**. Confidence: **CONFIRMED** (whole-repo grep incl. tests/tools/extensions).
- `charter_view` / `absorb_view` (306-326): no caller anywhere (`tools/bubble_town_drive.py` defines its own
  `charter_view`). Latent bug if revived: `members` means body keys in the working shape (385) and person ids
  in the stored shape (248), so `charter_view(normalized, "inn")["bodies"]` is `{}` (reproduced).
- `charter_figure.known_figures`, `figure_spread`, `stale_figure_claims`: tests only.
- `JOB_STAGES`: no reader. Lived-location job `updated` (518) is always 0.0 and exposed by
  `GET /charters/job` (no frontend reader).

## Efficiency

E1. **`_remember_experience` copies and re-sorts the whole list on every insert** (`world/charter_run.py:157-188`;
out of this file set, but it is the answer to question 6). Hot: every social act/witnessed happening, every
window, presim and in-play. Evidence: 720 h profile, 8,507 inserts -> 840,579 sort-key calls (avg list ~99);
chunk cost grows with experiences (1.46 -> 2.98 s per 240 h as mean rows/body 72 -> 253). Fix: append when
`at_hours` >= last (the common case), else `bisect.insort`; slice only on overflow. Expected: removes the
superlinear term (the year test is the symptom: 95.7 s vs the 17 s recorded in §1.99).

E2. **`normalize_charter` at the head of every `step` re-copies every experience row and re-materializes names**
(`charter_model.py:849-853`, `charter_run.py:466`; `charter_identity._stored_name_components:369`
re-normalizes the naming profile per body). Profile: 181 calls 1.99 s of 11.1 s (18%), of which
`materialize_body_names` 0.54 s, `_stored_name_components` 7,240 calls 0.42 s; grows with E1's lists. Fix:
skip re-normalization of state `step` produced itself, pass the normalized profile down. Cheap, ~15-20% of
every presim/advance.

E3. **One advance normalizes the full registry ~7 times and hashes it twice, once under the global write lock**:
`_produce` (`registry_for_update` parse, `registry_revision` 3775), `advance_snapshot` (`copy.deepcopy` + normalize
3196 on a copy the caller already owns), `cross_charter_gossip` (3567), `land_snapshot` (`registry_for` +
`registry_revision` 3678-3679 inside `transaction()`), `_write_registry` (normalize + reservation). Measured on
chat 175 (0.9 MB): normalize 42 ms, revision 52 ms, deepcopy 34 ms -> ~230 ms/advance of overhead; the 41 MB
registry the comments measured scales this to seconds, the land part while holding `_write_lock` (blocking turn
commits). Fix: carry the `world_read_token` from the read and compare it under the lock instead of re-hashing;
drop the redundant deepcopy.

E4. **Every advance stores a full deep copy of the live scene in EVERY charter** (`advance_snapshot:3236-3239` ->
`charter_scene` -> `structure.composed_scene` deep-copies the whole scene; `normalize_charter:651` persists it).
Measured (engine.db read-only, chat 175): each of 3 charters carries `attire`, `positions`, `entities`,
`contacts`, `poses`, `sensory_events`... -- 0.16 MB of a 0.90 MB registry; rooms-only would save ~84 KB/9% there,
more with more charters/bigger scenes. Re-parsed/deep-copied/dumped by every registry operation, checkpoint and
archive. Also a second representation (stale cast positions read by `charter_predation._scene_figures_at` between
refreshes). Fix: persist `{"rooms": ...}` only (it is recomposed every advance).

E5. **`land_snapshot` rewrites the registry when nothing advanced** (rerun/reroll of the same beat, zero delta):
`_produce` always lands (3801); the write bumps the token and every reader re-parses next turn. Fix: skip landing
when `not advanced_any and not rows` (baseline-only changes aside).

E6. `charter_practice.enact -> _afford_ask -> _between -> _pair_rows/_counterpart` is the largest single cost of
`step` (3.50 s / 11.1 s; 604,228 `_counterpart` calls) -- out of scope; noted for whoever owns charter_practice.

E7. `hearing_for_creatures` recomputes `room_sound_flood(scene, source, level)` per (creature place, event)
(3413-3433) though it depends only on the event; cache per event. Per beat, creature stories only.

E8. Inside a commit session `identity_index(session copy)` is never cached (929-961): every
`carrier_entries`/`background_presence_records` call in the commit rebuilds the display/alias maps (30 ms per
`carrier_entries` on chat 114 per the code's own measurement). Fix: memo per session entry.

E9. `generation_lore:1538-1540` one `SELECT` per descendant book (once per generation; minor).

## Already registered

- `_scheduled_row` INSERT OR IGNORE on `(kind, subject, at_hours)` collides two acts by one actor in one window --
  `docs/UNBUILT_LIVING_WORLD.md` §1.98 (bullet "`news_key` stamps the hour ... The same exposure sits at
  `charter_runtime._scheduled_row`").
- Dealt sibling names merged into an unlanded planned room -- `docs/UNBUILT_WORLD.md` §2.44 (F11 is the broader,
  unregistered class).
- `commitments`/`politics.regard` not moved by a transfer; the person/institution split itself --
  `docs/UNBUILT_LIVING_WORLD.md` §1.99d (F9's `walked` is not in it).
- The 2x charter scale regression on `big_ship(500)` -- `docs/UNBUILT_LIVING_WORLD.md` §1.99c (E1/E2 are a
  separate, superlinear cause).
- Creature path bounded by the wall-clock budget at entry only -- documented in
  `docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md` §7a (not a register; contradicts the owner's 10 s cap for
  creature stories -- an owner decision).

## Structure notes

- **Natural seams in `charter_runtime.py`** (5,866 lines): (a) storage -- person split/join, `normalize_registry`,
  cache, session, identity index, save/write (1-1040); (b) lived-location generation -- job store, salvage, cast
  histories, presim, generation lore, remap/merge, plan/generate, phonology, `land_presim` (448-2600, ~2,100
  lines, its own module); (c) author surfaces -- `registry_warnings`, `charter_diagnostics`; (d) the beat advance
  -- event surfaces/rows, catch-up order, errands, `sync_minds_to_scene`, `advance_snapshot`, creature senses,
  gossip, `land_snapshot`, `schedule_charter_ticks` (2838-3817); (e) play-time apertures -- place views, moves,
  residue, carriers, figures, `presence_view`, voiced presence, background records, dwellings, speakers,
  conduct (3820-5750); (f) promotion (5751-5866).
- **Monoliths in miniature:** `_plan_lived_location` 254, `registry_warnings` 233, `_prepare_cast_histories` 199,
  `advance_snapshot` 166 (two copy-pasted event-stamping loops, 3284-3293 and 3324-3334), `presence_view` 163,
  `_generate_lived_location` 163.
- **Near-duplicates:** `_presim_one`/`_presim_together` (differ in predation and window choice);
  `land_presim`/`land_snapshot` (revision check + `_write_registry` + the same INSERT OR IGNORE);
  `_merge_generated_rooms_by_name`/`_merge_town_rooms_by_name` (different name normalizers for the same
  question); `_stored_naming_laws`/`_plan_naming_laws`.
- **Stored twice:** live scene per charter (E4); `members` in two vocabularies (F19); `heard_from` in two
  vocabularies (F12); hermit + employed copies (F5); derived `fed_by` written into the same field an author
  writes (`_derive_sustenance_feeds:405-445`), so a derived hand becomes indistinguishable from an authored one
  once saved.
- **Module-level mutable state and writers:** `_REGISTRY_CACHE` (only `cached_registry`, under
  `_REGISTRY_CACHE_LOCK`; one test patches it); `_IDENTITY_INDEX` (only `identity_index`, under the lock; its
  `_DealtMap` values MUTATE ON READ via `__missing__` and are shared across threads -- safe for subscript readers,
  a Python-level iteration concurrent with a first read of a new key would raise; no such iterator found);
  `_REGISTRY_SESSION` (contextvar; `registry_session`, `_session_entry`, `save_registry`; turn-scoped but outside
  the two modules `project_check.check_turn_scoped_contextvars_are_cleared` scans -- extension commit domains run
  inside it, so an extension that submits a job would hand the job the commit's session dict);
  `CHARTER_BUDGET_SECONDS` (a mutable dict, read per schedule); `_GEN_OWNER` (per-process constant -- with
  several worker processes a live run in another worker reads "interrupted").
- **Deferred imports (Q5):** 133; ~45 are `from core.db import ...` (no cycle; plausibly for monkeypatching),
  ~70 are `world.*` siblings (no world module imports charter_runtime eagerly, so these are not cycle breakers),
  `story.*`/`mind.memory` (package edges already eager elsewhere), stdlib (`json as _json`, `re as _re` at
  1637/1639 duplicate module-level imports). Package-level: deferred edges hide a near-total SCC (11 packages)
  that `tools/package_edges.json` cannot represent because it computes cycles on eager edges only.
- `presim_registry` forks a `ProcessPoolExecutor` with the default start method (`fork`, Python 3.12.3) from a
  multi-threaded server (request handler `POST /charters/generate`, quick-start jobs). Children touch no lock I
  could find (charter/spatial modules hold none; logging re-inits at fork), so the deadlock risk is low but real
  in principle; an explicit `mp_context=get_context("forkserver")` removes it.
- Robustness: `normalize_upkeep:125-127` uses bare `float()` (a model string like "0.02/h" raises in every
  registry read path; `inf` is accepted and serializes as non-JSON `Infinity`) while `number()` exists for this.

## Docs checked

- AGENTS.md "THE CHARTER ADVANCES EVERY BEAT, by that beat's own elapsed time" -- **holds** (computation traced;
  engine.db chats 150-175 track the story clock exactly).
- AGENTS.md idempotence by `beat_id` (reroll/rerun cannot advance twice) -- **holds** (`last_epoch_id` skip 3232;
  `land_snapshot` beat check 3662-3667).
- AGENTS.md / §7a "`CHARTER_BUDGET_SECONDS` caps WALL CLOCK (beat 10.0s -- the owner's cap ...)" -- **holds for
  the solitary path; not for creature registries** (documented in §7a only).
- AGENTS.md / §7a "When a budget binds ... each records the clock it actually reached, and the rest catch up next
  beat" -- **holds** (3221-3282).
- AGENTS.md "the town's own advance of a `time_skip` beat steps the same windows with the same seed ... the town the
  story stores [is] the town every asked mind lived in" -- **fails** with a creature, and beyond 720 h (F10).
- AGENTS.md "`generate_lived_location` ... presimulates only the new registry slice" -- **holds for the presim; the
  first in-play beat then re-lives the story's elapsed time** (F4).
- AGENTS.md "The Charter/body dict key is permanent identity" -- **fails** on a "/" in a charter key (F6) and for
  bare-key transfers (F5).
- AGENTS.md "A generated personal name is materialized once; profile edits affect only unnamed future bodies" --
  **holds**, with F14's key-name caveat.
- AGENTS.md "a resident reaches a mind's record under the name THAT mind's known ledger gives it ... never under a
  name it has not met" -- **fails** on the scheduled-row rail (F2) and plausibly at promotion (F3).
- AGENTS.md "Author diagnostics never enter any cognition payload" -- **holds** (`charter_diagnostics` has one
  caller, the author route).
- `world/charter.py` "This facade remains model-free and performs no I/O" -- **holds**; "forty-one siblings" --
  **stale** (42).
- `_wset_encoded`/`transaction` read-token claims (core/db) -- **hold** (re-bump at transaction exit).
- `cached_registry` "a write landing during the fetch leaves this entry already-stale rather than wrongly-fresh"
  -- **holds**.
- `clock_anchor` "the two always describe the same instant" -- **fails** for mid-story landings (F4).
- `_plan_lived_location` "no writes" / `_fail_job` "nothing was written" -- **fail** (F16).
- `MAX_PRESIM_HOURS` cost claim, `EXPERIENCE_CAP` cost claim, "UNBUILT.md 1.99h" -- **stale/dangling** (F17).
- `registry_warnings` "scene presence is withheld until the author distinguishes them" -- **holds for
  `background_presence_records`, not for `presence_view`** (F1).
