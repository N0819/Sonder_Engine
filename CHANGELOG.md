# Changelog

## alpha1.4.1 — Chat import robustness

### Fixed
- **Story import no longer rejects enveloped archives.** `POST /api/chats/import`
  now tolerates a bare `{"data": {...}}` wrapper around the archive (as produced
  by the bundled `demo/` export and by the frontend re-wrapping the request
  body), instead of only unwrapping when a `schema: "fiction-engine.chat"` marker
  is present. Importing the demo story previously failed with "Chat archive has
  no chat object".

## alpha1.4 — Cross-LLM hardening, 4-agent audit & greeting-seeded openings

The theme of this release is **running well on small, cheap models**. A 30-turn
showcase run (`demo/`) driven on a lightweight model surfaced a class of
"plausible-but-off-shape output crashes the turn" bugs; a four-agent audit of the
whole codebase then turned up ~30 more. Everything below is fixed with regression
tests.

### Added
- **Greeting-seeded openings.** Import a SillyTavern card and jump straight in:
  - `first_mes` + `alternate_greetings` are captured as a swipeable greetings
    list; `{{char}}`/`{{user}}` macros are normalized at import.
  - A new ingest-time `greeting_interpret` stage parses the freeform greeting
    into establishment scaffolding — and, crucially, the character's **private
    knowledge**, which routes to character memory and is never shown to the player.
  - **Start story now** (`POST /api/characters/{cid}/start`): pick a persona and
    play. The hand-authored greeting is shown **verbatim** (deterministic
    persona substitution); the simulation is booted underneath it.
  - See `docs/GREETING_IMPORT_DESIGN.md`.
- **Rename stories** from the sidebar.
- **Portable story export.** `chat_export` now embeds a `resources` bundle
  (persona + character sheets) plus the multiplayer roster, per-player inputs,
  and lorebook links — so an exported story actually imports into a fresh install
  (it previously dropped characters and all memories cross-install).
- `demo/` — the "Meridian Station: The Vesper Audit" showcase story (annotated
  transcript, coverage matrix) and `demo/AUDIT_FINDINGS.md` (the consolidated
  4-agent bug audit).

### Fixed — information boundaries
- **Concealed speech no longer leaks through the interaction loop.** The
  micro-perception speech path delivered a concealed line to the very parties it
  was hidden from (and into their memories); it now respects `conceal_from`,
  mirroring the action path.
- **Background presences no longer receive the raw player declaration** or the
  full objective outcome — they get a perception-filtered beat with concealed
  content and private thoughts stripped.
- **Concealment survives normalization.** `norm_sequence` dropped a speech
  element's `visibility`/`conceal_from`; a hushed line co-declared with a
  concealed action now inherits that concealment (leak-safe backstop).
- **Spatial splits fail closed** — no accidental auto-merge granting light-years-
  apart parties permanent mutual memory visibility; undated parent memories no
  longer leak across an active split.

### Fixed — cross-LLM robustness (coerce, don't crash)
- Numeric bounds (relationship deltas, confidence, urgency, salience) **clamp**
  instead of hard-rejecting; `dialogue_log` alias keys / bare strings are coerced
  (were crashing or silently dropped); `mind_model_updates.alternatives`,
  `considered_responses`, and out-of-enum speech volumes coerce; `dice` and
  `other_players` shapes tolerated; non-numeric mood/temperature/stance in a
  character sheet no longer 500 the import or crash every subsequent turn.
- Prose-wrapped JSON is recovered instead of burning every repair attempt.

### Fixed — providers & reliability
- Transient network errors on the `requests` sync path
  (`ConnectionError`/`Timeout`/`ChunkedEncodingError`) are now **retried** (a
  mid-stream drop used to kill the whole turn); mid-stream SSE error events are
  surfaced instead of committing truncated output as success; configured
  **fallback models are used when the primary provider *errors*, not only on
  invalid JSON.

### Fixed — persistence, resume & reroll
- **Branch/import/checkpoint corruption:** checkpoint blobs kept the source
  chat's frame + persona ids, so a restore after branch/import could 500 forever
  or delete the branch's own frames — now remapped. Branch/import copy the
  normalized `world_*` tables (a branched chat no longer fires a false paradox);
  `refresh_checkpoint` no longer overwrites the pre-turn snapshot; restore deletes
  discarded-timeline lorebooks; entity turn-FKs are remapped.
- **Reroll/resume:** a single-step reroll of a pre-commit stage no longer runs
  against post-commit state or the current turn's own memories; a resumed turn no
  longer silently drops character memories / mind-model / stance updates.

### Fixed — API & auth
- Guest join codes are atomically single-use; a non-ASCII host username no longer
  500s login; a 409'd turn no longer leaves an orphan row blocking the frame;
  frame ids are validated for chat ownership.

## alpha1.3 — Background NPCs & reliability audit

### Added
- **Background NPCs that feel like real people, cheaply.** Unregistered background
  presences now gain:
  - *Cheap individuation* — a `role_hint`/`station_room` sketch harvested
    deterministically from the Director's own entity description/position and
    replayed into the reaction payload (no persistent psychology).
  - *Continuity* — the deterministic backstop line is persisted into the
    committed event record and counted toward promotion, so a repeatedly-voiced
    presence stays consistent across turns instead of resetting to a stranger.
  - *Replies to registered characters* — a background NPC can answer a cast
    member's (or the player's) direct address, this beat if the gate is free
    else next turn via a bounded, expiring `pending_reply`. Concealed/unhearable
    lines never trigger it.
  - *Ensemble reactions* — `background_config.max_reactors` (default 1, hard cap
    3) lets several present bystanders react in a single beat.
  - *Location-implied establishment* — presences the Director places at scene
    open (idx 0) are now tracked with their sketch.
- **Director populates location-appropriate background people.** New
  BACKGROUND POPULATION guidance: a tavern implies a barkeep and patrons, a gate
  a guard, an empty moor no one — grounded, modest, no dialogue/backstory.
- `docs/RESEARCH.md` — sourced bibliography of the research the engine draws on.
- `.gitignore` (excludes `__pycache__`, all `*.db`/`*.sqlite*`, `.env`).

### Fixed — frontend
- **Message delete button did nothing.** `event.currentTarget` was read after an
  `await` (null by then), crashing before any request fired. Fixed here and in
  the identical latent pipeline **Resume** button.
- Silent action failures now surface: `buttonTask` toasts errors, a global
  `unhandledrejection` net catches un-caught `api()` rejections, and a failed
  `boot()` shows a message instead of a blank app.
- First-run "Use this model" can no longer brick; new-story **Cancel** no longer
  creates a nameless chat; **Send** restores typed input if the turn fails to
  start; memory "Back" no longer grows the modal stack; **Escape** no longer
  closes the modal beneath a confirm dialog; `modelCombobox` no longer leaks a
  document listener; the lore filter box no longer loses focus each keystroke.

### Fixed — web/API
- `turn_branch` is now fully transactional (a mid-branch failure no longer leaves
  a half-built chat); `turn_del` restores the checkpoint inside the delete
  transaction.
- `world_put` gained an idle guard, a 404, and a transaction (was destructively
  wiping world state mid-pipeline, non-atomically).
- Missing-row **404s instead of 500s** (`chat_edit`, `pipeline_get`,
  `put_provider`, `chat_add_char`); guest `idx` validation; a host hitting the
  guest endpoints now gets 403 instead of a 500; `chat_del`/`edit_input` gained
  idle guards; `mem_add`/`dlg_put`/`attach_lore` validate input.

### Fixed — pipeline
- Contested turn at autonomy=0 no longer double-runs reactors or drops their
  speech.
- uid/alias-tolerant room resolution in the director/character/interaction paths
  (was silently placing characters in "an unspecified area").
- Perception source ordering fixed for co-op players; `only_key`/`from_key`
  reroll paths gained stale/validity guards; the narrator's durable write is
  deferred to commit; perceiver view-keys are casefolded; extra-player planning
  is frame-aware.

### Fixed — persistence
- Checkpoint restore now snapshots/restores `frames` and `chat_personas`
  (rerolling a spatial split/merge no longer strands personas or leaks
  visibility).
- Embedding blobs are preserved verbatim across checkpoint and lorebook restore —
  restore no longer re-embeds the whole memory bank every reroll, and a provider
  hiccup can no longer silently downgrade vectors to crc32 (which had corrupted
  retrieval permanently).
- Checkpoint restore is atomic; memory consolidation no longer archives another
  era's un-summarized memories; the v14 migration is re-run-safe.

### Security
- PNG character-card import is bounded against decompression bombs.
- Provider retry backoff now honors cancellation instead of stalling.

### Internal
- ~49 new regression tests. `make check` green: **609 tests passing.**
