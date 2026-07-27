# Information-pipeline audit — consolidated findings

Five read-only auditors swept the pipeline. Severity: **leak** (a mind receives
what it did not earn) / **degradation** (a mind is denied what it did earn, or
is told something false about its own perception) / **corruption** (durable
state made wrong) / **latent** (mechanism real, crossing model-gated).
Confidence: CONFIRMED (traced end to end) / PLAUSIBLE.

All paths relative to the repo root.

---

## SEAM 1 — Perception view construction (`agents/perception.py`, `agents/common.py`)

Structural frame: all three passes make **one LLM call producing every
perceiver's view from one shared payload** (`perception.py:835`, `1132`,
`1766`). Anything in that payload is reachable by every view; the only
guarantees are the specific post-hoc scrubs.

### Payload contents

- **A1 — Concealed player speech rides `declared_act.sequence` verbatim.
  CONFIRMED leak (verified independently).** `perception.py:951-954` filters
  `if e.get("type") != "action" or e.get("visibility") != "concealed"` — for a
  speech element the first clause is already true, so it is kept. The comment
  directly above claims the withholding is complete; the other two copies
  (`overt_player_speech`, scalar `speech`) *are* closed. The act pass has no
  invented-dialogue scrub, so nothing catches it downstream. Untested.
- **A2 — `concealed_actions` metadata carries the secret's content, and in the
  outcome pass the RAW `attempt`.** Act: `perception.py:962-976`. Outcome:
  `perception.py:1511-1531, 1561-1563` use `a.get("attempt")` rather than
  `observable_action_text()`. The one class of act everything else strips
  intent from hands its intent-laden framing to the model precisely when
  concealed. CONFIRMED, latent.
- **A3 — Concealed dialogue is in the outcome payload verbatim**
  (`perception.py:1477-1506`), by documented design; only the LLM reasons about
  who a concealed line reaches. No structural counterpart to the
  `resolved_event` redaction. CONFIRMED, latent.
- **A4 — Identity/appearance stripping is all-or-nothing across the audience.**
  `perception.py:1071-1075` (name), `1094-1097` (appearance), outcome
  `1715-1727`. One knower or one seer in the reactor set keeps the canonical
  name / full appearance in the shared payload for every stranger and every
  hearing-only perceiver. There is no appearance scrub at all on the output
  side. CONFIRMED mechanism, model-gated crossing.
- **A5 — The act-pass identity scrub covers only the player.**
  `perception.py:1235-1245` passes the player as the sole unknown source, while
  the payload supplies every cast member's canonical name via `cast_pronouns`
  (`1123`) and `contacts`/`contained`/`scales` (`1109-1115`). Establish and
  outcome scrub against the full roster; the act pass does not. CONFIRMED gap.
- **A6 — Whole-scene relational state is serialized every pass**
  (`perception.py:810-820`, `1108-1115`, `1745-1752`). `contained` is the
  concealment ledger itself: a body hidden in a bag is named as hidden in that
  bag inside the payload that writes the views of the people it is hidden from.
  CONFIRMED, latent.
- **A7 — `_state_reaches_anyone` one-reaching-perceiver rule** (`common.py:400-406`)
  keeps act-naming entity `state` in the shared payload for the whole call.
  Pinned as intended by `tests/test_enclosed_act_leak.py:141`.
- **A8 — Disguise `concealed_truth` always in payload when a disguise is
  active** (`perception.py:625-644`); `_disguise_leak_check` (`647-671`) warns,
  never scrubs. CONFIRMED, latent.
- **A9 — Opening pass** ships raw player input as `player_seed`
  (`perception.py:789`) and the full rooms dict (`806`). Minor.

### Deterministic injections after the model returns

- **B1 — Containment gates sight and scent but not sound.** `hear_level`
  (`spatial.py:734-755`) returns `full` for `same_room` before consulting the
  `concealed` flag that `sight_level` (`456-457`) and `scent_level` (`170-171`)
  both honor. A verbatim quote from inside a sealed opaque container reaches
  everyone around it (`perception.py:1961-1963`, `1215-1221`). Pinned as
  deliberate by `tests/test_containment_concealment.py:128`. **Additionally, no
  perception call site passes `proximity`** (`perception.py:1216`, `:92`,
  `loops.py:92`), so the mutter/within-reach downgrade (`spatial.py:750-755`)
  never fires: a muttered aside is injected verbatim to an arbitrarily large
  room. CONFIRMED.
- **B2 — The comm/shape floor delivers a line across any barrier on the
  strength of `intended_target`** (`perception.py:72-100`, applied `1961`), no
  comm device required. Concealed lines are excluded. Tested
  (`tests/test_comm_channel_hearing.py`); risk lives in director tagging.
- **B3 — The outcome action backstop ignores the rear-arc blind spot it
  advertises.** `behind_sources` is computed and shipped as advisory
  (`perception.py:1581`, `1628`) and enforced for tells in `_delivered_manifest`
  (`583-587`), but the deterministic action injection (`1964-1987`) gates only
  on `_in_plain_view`. A silent rear-arc act is appended to the view.
  CONFIRMED deterministic leak.
- **B4 — `_ensure_environment` announces presence and the action surface with
  no light or audibility check** (`common.py:2144-2166`). Containment handled,
  darkness not. CONFIRMED minor leak.
- **B5 — Micro-view append pastes `interaction_loop` deliveries AFTER every
  scrub** (`perception.py:2024-2035`), and `loops.py:69` builds its relation
  with bare `spatial_rel` — **no `containment_conceals` patch**. A contained
  actor reads `same_room`, `has_visual` passes (`loops.py:108`), and their
  overt micro-action renders to the whole room from inside a closed container.
  Being post-scrub, a third party's canonical name inside a micro-action
  surface also reaches an observer who does not recognize them. CONFIRMED leak.
- **B6/B7 — clean.** Fragment delivery (`common.py:1726-1733`) and residue
  views for non-awake minds (`common.py:2112-2141`) are sound and tested.

### What the scrubs actually remove

`_normalise_views` (`common.py:2083-2110`) is key canonicalization only. Every
content guarantee lives in four scrubs: identity-outside-quotes, invented
dialogue (outcome only), undeclared player speech (player's outcome view only),
sentence dedupe.

- **C1 — Quoted spans are an identity smuggling channel.** Quotes are exempt
  from the identity scrub by design (`common.py:1329-1391`). The act pass has
  no invented-dialogue scrub at all. At outcome, quotes with no attribution cue
  are kept as environmental text (`common.py:2575-2576`), and the match
  `body == L or body in L or L in body` (`common.py:2483`) lets any short
  genuine line ("yes") whitelist every fabricated quote containing it.
- **C2 — Short/common-word names escape the identity floor**
  (`common.py:1373-1379`): forms under 3 chars are never scrubbed.
- **C3 — Stray view keys survive normalization**; a view keyed by a non-awake
  character's name is neither folded nor overwritten by the residue. PLAUSIBLE.
- **C4 — Confirmed protections:** structured observations re-projected from
  final scrubbed prose only; private thought never in any payload
  (`perception.py:1124-1127`); mental beats dropped (`common.py:135-149`).

### Structural redactions in `perception_outcome` — the stated defence, untested

- **D1 — `_redact_concealed_from_event` fails on pronouns, paraphrase and case.
  CONFIRMED (verified independently).** `perception.py:1355-1388`: a sentence is
  redacted only if it contains the actor's name as a **case-sensitive
  substring** AND shares a >4-char word with the attempt. "Mara turns to the
  shelf. She slips the vial into her sleeve." redacts sentence one and delivers
  sentence two. A paraphrasing director defeats the word test entirely.
  **Zero tests reference this helper.**
- **D2 — `_surface_translate_event` / `_touch_only_sources`
  (`perception.py:1309-1352`):** same name-only matching, so pronoun-subject
  sentences pass untranslated to a touch-only perceiver — the exact leak the
  function exists to prevent. The replacement sentence itself pastes the
  source's canonical name into the payload. `perception.py:1304` is a
  case-sensitive dict lookup after casefolded collection, silently disabling
  translation on a spelling mismatch. **Zero tests.**
- **D3 — Over-redaction for the legitimate audience** (`perception.py:1667-1673`):
  redaction excludes only the actor, so the intended co-audience loses the
  outcome and must rebuild it from `concealed_actions` — the degradation and the
  A2 intent leak are the same hole from both sides.

### Identity gating, minor

- **E1** — `knows_identity` uses strict membership (`perception.py:774`, `1045`,
  `1625`) while `_scrub_view_for` uses title-tolerant `_recognizes`
  (`common.py:1199-1225`). Inconsistent; over-anonymization.
- **E2** — `_unknown_actor_label` (`common.py:1238-1278`) strips only
  name/alias tokens; a unique identity-bearing epithet in the appearance
  survives into the label.
- **E3** — Outcome extra players get `knows_identity: True` hardcoded
  (`perception.py:1599`); advisory only.

### Coverage

**Completely untested:** D1, D2 (the stated defences for concealment and
touch-only perception), A1, A4, A5, B3, B5, B4.

**Ranked highest value:** A1, D1/D2, B5, A5, B3, A2.

---

## SEAM 2 — Character-step payload (`agents/character.py`, `agents/loops.py`, `theory_of_mind.py`)

The payload never contains the raw player input, the objective resolved event,
or any other character's sheet/state/wants/vitals/manifest. Other minds are
reachable only through the scrubbed view, the character's own mind models, and
the memory bank — so the findings concentrate on memory and the micro-loop,
the two paths that bypass the perception stage.

- **F1 — Rerolls feed the character its own committed memory of the CURRENT
  turn's outcome. CONFIRMED leak.** `recent_memory_buffer` excludes
  `turn_idx >= current` (`memory.py:1204-1212`), but `search_memories`
  (`memory.py:1089-1191`) has **no turn cutoff at all** — `current_turn_idx` is
  used only for recency scoring (`1125`). `build_character_memory_context`
  (`1272-1274`) subtracts only `recent_ids`, which contain no current-turn rows.
  On a reroll the just-committed outcome memory is the closest semantic match to
  the onset-view query, so the character re-decides the beat already knowing how
  it resolved. `tests/test_character_observes_the_present.py:37` asserts the
  invariant against an **empty** memory bank — vacuous for this path.
- **F2 — Dialogue memories store the canonical speaker and the director-private
  `intended_target`, with no recognition gate. CONFIRMED leak.**
  `commit.py:3233-3259`: admission is only "the quote appears in this
  character's scrubbed view"; the stored content uses the **objective**
  `d["speaker"]` and `d["intended_target"]`. Perception renders an unrecognized
  speaker as an appearance label or "a voice" while quoted speech survives
  verbatim — so the quote passes the gate and the name arrives anyway.
  Restricted to `_durable_dialogue_category` lines (`commit.py:3120-3129`),
  i.e. precisely the promises/confessions/threats.
  **Independently found by the persistence auditor as its finding 1.**
- **F3 — The deterministic micro-loop ignores containment concealment.
  CONFIRMED leak.** `deterministic_micro_perception` (`loops.py:40-122`) gates
  on bare `spatial_rel` + `hear_level`/`has_visual`; a contained body's position
  is derived from its carrier's, so it reads `same_room`/`open`. The `concealed`
  flag is set only at perception's own call sites. Both directions leak.
  (Same defect as SEAM 1's B5, reached from the other side.)
- **F4 — The micro-loop ignores sense profiles and graded sight. CONFIRMED.**
  `loops.py:92-119`: speech on `hear_level` alone — the observer's authored
  sense profile, which perception consults (`perception.py:526-562`), is never
  read; actions on boolean `has_visual`, so dim light ("shapes") still yields
  full observable text plus name attribution. `hear_level` called without
  `proximity`, so a same-room whisper always lands full.
- **F5 — `observable` falls back to the raw `attempt`.** `common.py:1066-1069`,
  `135-149`. Fires on weak-model omission; the surface then flows verbatim to
  other minds (`loops.py:115-117`). Pinned as intended by
  `tests/test_perception_intent_leak.py:106,115`.
- **F6 — `spatial_frame` hands over unvisited adjacent room names.** PLAUSIBLE.
  `spatial_digest` (`spatial.py:971-996`) renders every adjacency edge with its
  authored name, no visited/known gate. A cell's occupant learns what is behind
  the closed opaque door. Same digest goes to the narrator — cross-seam.
- **F7 — `known_pronouns` releases authored pronouns on the model's own
  unverified mind-model keys.** PLAUSIBLE. `character.py:114-146` keys off
  `relationships | mind_models`, both populated from model-authored
  `about_entity` strings that nothing validates against the `known` ledger; the
  frame filter applies only when `frame_id is not None`. Self-reinforcing with
  F2.
- **F8 — ToM confidence caps are honor-system on `kind`, evidence never
  verified.** Caps are enforced twice (`theory_of_mind.py:99-114`, `205-241`)
  but keyed to the model's self-declared `kind`; `MindHypothesis.evidence` is
  free text persisted verbatim as an `inferred` memory (`commit.py:3293-3316`).
  Degradation, not cross-mind leak.
- **F9 — `authorial_offers` is a sanctioned player→NPC knowledge injection.**
  By design (P3); the only payload field whose content is neither perceived,
  remembered, nor authored into the character.
- **F10 — minor/latent:** sleeping observers accumulate micro-views
  (`loops.py:322-328`, currently a dead end); `_next_speaker_candidates` orders
  by private urgency (control flow only); `search_memories_vec` has no
  frame/turn gating (zero non-test callers); `_recent_self_lines` misses
  alias-keyed dialogue rows.

**Verified clean:** retrieval query construction (own view + own goal/mood +
own threads, never the objective event); later speakers receive only observable
surfaces, never declaration fields; reactors declare blind to each other;
own-body isolation; mind-model persistence isolation; frame masks; parallel
character steps share no mutable payload state; the awareness choke point.

---

## SEAM 4 — Persistence and retrieval (`commit.py`, `memory.py`, mapping, checkpoints)

- **P1 — (= SEAM 2 F2) Dialogue memory stores the unrecognized speaker's true
  name and `intended_target`. CONFIRMED leak.** Indexed for retrieval under the
  true name (`memory.py:743-750`), so it is also a retrieval cue.
- **P2 — Checkpoint restore is defeated by a stale ctx cache on rerun.
  CONFIRMED corruption — the highest-impact finding in this seam.**
  `runtime.py:587-600` loads `cast_rows` and builds the `PipelineContext`
  **before** `restore_checkpoint` runs at `:645/:661/:697`. The restore rewrites
  `chat_chars.state`, but `ctx.cast[*]["cstate"]` still holds the discarded
  run's **post-turn** state. Consequences: `character.py:209` deliberates at
  onset with the discarded outcome's interior (exactly the leak the restore's
  own comment claims to prevent); `commit.py:3203` evolves from the discarded
  post-state and then overwrites the restored row. Downstream:
  stance double-applies (`commit.py:3599-3615`, and the accumulated axis is
  never clamped); hedonic `max(old*decay, proposed)` ratchets with
  `turns_since == 1`; `charge` re-accumulates; stress `strain` ratchets and
  `load` re-accrues; belief confidence re-blends 0.2 toward target; association
  strength re-adds; mind models re-reinforce; `drive_strain` re-pumps, so
  repeated rerolls can walk a character to the rupture threshold on one event.
  Unaffected: memories (delete + stable-key upsert), the events row,
  relationships (read via `wget` after restore). The scene analogue is pinned by
  `tests/test_resume_correctness.py:170`; the cstate side has no test.
- **P3 — `background_presences` is exempt from restore.** CONFIRMED corruption.
  `checkpoints.py:420-446` lists it among preserved reader dials, but it is
  diegetic bookkeeping written every commit. `_append_manager_conduct`
  (`commit.py:2059-2082`) has no per-turn dedup, so a discarded run's line stays
  in the 4-entry tail voiced back to the reactor; `_persist_blurbs` is
  write-once, so a discarded reroll's blurb anchors identity forever; a
  `pending_reply` debt survives into a timeline where the address never happened.
- **P4 — An auto-promoted character survives reroll hollow.** CONFIRMED.
  `restore_checkpoint` only UPDATEs `chat_chars` rows present in the snapshot
  (`checkpoints.py:499-505`) — never removes membership added since. Her seed
  memories, `known` and position roll back; she stays active cast with empty
  state and no recognition, and P3 means she can be neither re-tracked nor
  cleanly re-promoted.
- **P5 — Promotion memory seeds are minted from the objective event record and
  stored as `witnessed`.** CONFIRMED mechanism. `importers.py:740-773` uses the
  full `resolved_event` of every turn mentioning the name — including concealed
  acts, with no perception filter — and `commit.py:2318-2327` writes them
  `provenance: "witnessed"`. The autonomous promotion path has no reviewer.
- **P6 — The knowledge-tag door is the widest lore→mind channel.**
  `knowledge_for_character` (`memory.py:1946-1979`) delivers any
  `knowledge`-category entry with `range='global'` and a matching coarse tag to
  every tag-holder, with zero encounter tracking; category/tag/range are
  model-proposed at `mapping_commit` with only vocabulary validation
  (`commit.py:2736-2771`). One mis-filed secret is instantly in every
  character's `world_knowledge`.
- **P7 — `known` introductions are validated by model judgment over the
  objective log.** PLAUSIBLE. `commit.py:2799-2817` applies
  `validated_introductions` with only roster resolution and a frame gate; the
  mapping model judges from `beat_dialogue_log`/`beat_resolved_event` including
  concealed lines. Recognition never decays or retracts.
- **P8 — Consolidation flattens provenance.** CONFIRMED degradation.
  `heard`/`inferred`/`told` rows melt into one flat autobiographical string fed
  back wholesale each turn — the provenance distinction the engine's thesis
  rests on does not survive the summary layer.
- **P9 — Stance axes accumulate unclamped** at commit (`commit.py:3599-3615`);
  the clamp lives on the per-delta schema only.

**Verified clean:** the retrieval query; `world` KV scoping (`known`,
`relationships`, `shadow_profile`, lore caches — every reader scopes to the
perceiver); `tell_grounds` privacy end to end; the scene/world write path;
mapping's inability to see interiority; canon locking and its reroll safety;
stable event keys for idempotency.

---

## SEAM 3 — Director resolution output and the Narrator

### Consumer inventory (who reads what the Director emits)

- `resolved_event` → perception_outcome per-perceiver payload *after* redaction
  and touch translation (`perception.py:1648-1692`); Tier-0 scans
  (`director.py:1890-1951`); player-act-authority retry (`director.py:2488-2527`);
  mapping_commit `beat_resolved_event` (`commit.py:2640`). **Never** reaches the
  narrator — the narrator sees only `player_view`.
- `dialogue_log` → perception's `enriched_dlog` **including concealed entries**
  (`perception.py:1477-1505`); memory minting (`commit.py:3236-3260`);
  mapping_commit unredacted (`commit.py:2639`).
- `state_diff` → merged pre-commit for perception/narrator
  (`perception.py:1411-1433`); entity `state`/`description` blobs reach every
  perceiver via `_perceptible_entities` (`perception.py:1741`).
- `changes_asserted` → only the Tier-1 reconciliation check.
- `fact_adjudications` → only the warn-only `_audit_fact_adjudications`
  (`director.py:2139-2169`), and only claims whose id ends `:event`.
  **No commit consumer exists** — verdicts land only if the prose happens to
  carry them.
- `obligations`/`world_pressure` → commit-side views and ops; sound.

### Information

- **S3-A1 — (= SEAM 1 D1) `_redact_concealed_from_event` is name-anchored and
  defeats itself on pronouns and paraphrase.** Independently confirmed. This is
  the load-bearing structural guarantee for concealment and its failure is
  silent. No unit test targets it.
- **S3-A2 — Concealed actions declared in the REACTION loop are never collected
  for redaction. CONFIRMED.** `perception.py:1521-1531` builds the `concealed`
  list only from `ctx.character_results`; reaction output lives in
  `ctx.reaction_results` (`loops.py:521`) and only merges for the *interaction*
  loop (`loops.py:303`). A concealed reaction can be described in
  `resolved_event` with no perceiver's copy redacted for it — precisely on
  contested beats. No test.
- **S3-A3 — Full `dialogue_log` incl. concealed entries copied into the
  perception payload** (`perception.py:1498-1505`), a documented trade.
- **S3-A4 — `co_present_positions` is scoped by co-location only. CONFIRMED.**
  `narration.py:309-338`: no sight, light, awareness, or concealment gate. A
  character who entered the player's pitch-dark room appears with `moved: true`
  and their `prev_room` name; a character who **left** is included with the
  **destination room's display name** — a room the player may never have heard
  named. The prompt then invites rendering it (POSITION CONTINUITY), and the F2
  fidelity check *enforces* prose agreement with these facts.
- **S3-A5 — `portal_states` and `spatial_frame` name rooms the player has never
  perceived.** `narration.py:391-401` mints `"door to {to_name}"` for every
  adjacency; `spatial_digest` gives every bucket's adjacent room names including
  through `closed_door`. No light or knowledge gate. (= SEAM 2 F6, cross-seam.)
- **S3-A6 — `narrator_extra` lacks the consciousness gate and the fidelity
  facts. CONFIRMED, multiplayer.** `narration.py:685-703` includes
  `spatial_frame` unconditionally and sends no `player_awareness`, so the
  prompt's consciousness rule can never fire — the exact pattern the primary
  path's own comment forbids.
- **S3-A7 — The correction/retry loop is NOT an independent channel.** Every
  fact quoted in a correction note originates in the view or in payload fields
  the narrator already holds. But it *amplifies* A4/A5 by enforcing conformance.
- **S3-A8 — Nothing reconciles entity `state`/`description` blobs against the
  beat's own `resolved_event`. CONFIRMED — this is the stale-posture symptom.**
  Three parts: (1) the blobs are free text and the resolve payload hands the
  model the complete pre-beat `scene.entities` (`director.py:2337`), so stale
  clauses get copied forward wholesale; (2) `spatial._merge_entity`
  (`spatial.py:2512-2521`) merges key-wise, and `_PROTECTED_STATE_KEYS`
  (`spatial.py:1795-1799`) shields `posture`/`description` from normalization;
  (3) `_reconcile_resolution` (`director.py:1832-2099`) audits **omissions
  only** — there is no check that a state clause *contradicts* this beat's own
  prose. The stale clause then wins downstream, because deterministic layers
  prefer structured truth over prose. No test.
- **S3-A9 — Concealed dialogue is laundered into the lore path at commit**
  (`commit.py:2639-2640`). Retrieval is Director/mapping-privileged today, so no
  character receives it — a stored unredacted copy one consumer away. LOW.

### Attribution (remaining instances of the fixed bug class)

- **S3-B1 — Body-only `existing_bodies` lets one wrong-speaker transcription
  displace the true speaker permanently. CONFIRMED — highest severity in this
  seam.** `director.py:2789-2827`: the validation loop drops director-invented
  lines only for registered cast and the primary player, so a line attributed to
  any other name passes. `existing_bodies` is then keyed on the **quote body
  alone** (`:2797, :2804-2805`), and the deterministic re-append of declared
  lines is skipped whenever the body is present. So a resolve model that
  transcribes a character's whisper under `speaker: "the barkeep"` keeps the
  wrong entry, loses the concealment tag (restore is keyed `(speaker, body)`),
  and **suppresses the character's correct entry**. Downstream: views inject the
  wrong speaker, and memories mint it for every hearer (the view gate checks
  only that the quote reached the view, not who the view said spoke). The same
  key also silently suppresses two speakers legitimately saying the same words.
  Untested.
- **S3-B2 — Extra human players' speech has neither guard. CONFIRMED,
  multiplayer.** The `checked_dlog` loop validates cast and the primary player
  only (`_player_aliases` covers only the primary persona, `scene.py:693-700`).
  The Director can author words for a co-player, and an extra's dropped line
  vanishes silently — the append loops force-append only the primary's and
  cast's declarations.
- **S3-B3 — The player-name single-word fold can delete a name-sharing NPC's
  line.** PLAUSIBLE, low: usually self-healing for verbatim quotes; a *reworded*
  transcription under the shared word is dropped outright.
- **S3-B4 — Interpret-stage split across human players is model fiat, unchecked
  for extras.** `_reconcile_interpretation` coverage-checks only the primary
  `ctx.input`; an extra's declaration dropped from or swapped between entries is
  silent, and each entry then carries ABSOLUTE authority into resolve.
- **S3-B5 — Verified sound:** parallel character result names, loop-round
  display names, background speaker canonicalization, `_speaker_display`'s
  recognition gate, the NPC-line info barrier, `_observable_predicate`'s
  label handling, `canonicalize_positions`, movement-mover resolution.
  **Residual edge on the just-fixed bug:** a puppeted *physical-but-volitional*
  NPC act ("Dr. Moon steps back") is deliberately left in the player's sequence,
  where only the resolve prompt keeps the actor label from becoming the
  player's at perception time. Instruction-gated, not structural — the same
  shape as the fixed bug, one notch down in interiority.

---

## SEAM 5 — Non-obvious channels (background, multiplayer, coercion, diagnostics, restore)

### Background presence

- **X1 — Co-presence assumption delivers whole-scene dialogue to an unplaced
  presence. CONFIRMED leak.** `background.py:96-130`: the hear-level check runs
  only `if station_room and sc:`. A presence tracked from a `dialogue_log`
  speaker alone has no station room, so it receives every audible quote of the
  beat verbatim — and its reply becomes public canon. The scene-manager path
  fail-closes on the same uncertainty (`background.py:324-325`); this one does
  not.
- **X2 — "fragment" hearing delivers the verbatim quote. CONFIRMED.**
  `background.py:120-126` drops a line only when `hear_level == "none"`;
  `fragment` passes the whole `exact_quote`. `_character_address_of` requires
  `"full"` (`commit.py:1798`) — the two paths disagree.
- **X3 — `conceal_from` without `visibility:'concealed'` bypasses the player
  declaration filter.** `background.py:76-86` consults only `visibility`; every
  other guard in the file fail-closes on `conceal_from` independently precisely
  because models half-comply. Latent leak, no test.
- **X4 — `_present_others` bypasses recognition and disguise. CONFIRMED leak.**
  `background.py:644-662` returns the persona's true name plus every active cast
  name — no room, `known`-map, or disguise gate — and the minted line merges
  into the rendered dialogue_log.
- **X5 — Scene-manager `full` mode: per-presence non-hearing is an
  `audience[name]="none"` annotation on a shared context, not structure**
  (`background.py:331-362`). `ambient` correctly refuses divergence.
- **X6 — Sound:** merge discipline (background output merges at
  perception_outcome and into the events row, never mutating the persisted
  `director_resolve` variant).
- **X7 — Gate salience reads raw input** (`commit.py:2177, 2195`), so a
  concealed declaration naming a presence still raises its pick priority.

### Multiplayer

- **X8 — Guest scoping is sound and well tested** (deny-by-default middleware,
  two guest routes, persona-forced input, detach revokes in-transaction).
- **X9 — The host reads co-players' private thoughts.** `director.py:365-368`
  and `schemas.py:386-415`; full step content streams to the initiator (always
  the host) and is embedded in archives. Not a code bug — the host is the trust
  root — but an unstated product boundary.
- **X10 — In-fiction cross-player scoping is sound:** resolve receives
  co-player declarations without `private_thought`; `narrator_extra` gives each
  persona only its own entry; per-persona narration keys are independent.
- **X11 — Extra-player concealed SPEECH has only one defence.** Perception's
  concealment list gets extras' concealed actions but not their concealed
  speech, and the dialogue-fidelity floor whitelists all extras' speech
  including concealed (`perception.py:1852-1856`), so a leaked co-player
  whisper would not be scrubbed. PLAUSIBLE.
- **X12 — The onset pass is primary-player-only** (`perception.py:875-1010`), so
  the reaction-gate and `targets` guarantees never run for extras' sequences at
  onset. Degradation.

### Output coercion

- **X13 — Sound:** the observation pop; unknown-field smuggling is inert
  (extra-ignore everywhere except two self-scoped models); `commit_narration_person`
  re-validates deterministically because step content is hand-editable.
- **X14 — String-line dialogue reconstruction erases concealment. CONFIRMED
  mechanism.** `schemas.py:1701-1731`: a bare `"Speaker: quote"` line is rebuilt
  with no `visibility`, and every reader defaults to `"overt"`. The coercion
  that keeps a weak model's beat alive silently promotes a concealed line to
  public. `test_coerce_hardening.py` tests the coercion's success, not this.

### Diagnostics

- **X15 — `ctx.warnings` is write-only in production** (no non-test reader), so
  no warning text ever enters a model context — but a diagnosed violation
  vanishes unless a stage attaches it to its own step.
- **X16 — Pipeline traces are sound:** hash-only by default, content export is
  an explicit flag, replay never imports the runtime or calls a model.
- **X17 — Retry/repair correction notes carry no foreign privilege.** Verified
  across every loop.

### The events row — widest latent channel

- **X18 — The omniscient events record re-enters later model contexts
  unredacted.** `commit.py:3629-3634` persists `resolved_event` plus the **full
  dialogue_log including concealed entries**; `scene.py:625-654` replays it via
  `director_context` into the Director (entitled) **and into `mapping_stage`**
  (`mapping.py:64`). Laundering chain: concealed whisper → resolved_event →
  events row → next turn's mapping context → lore entry or `scene_patch` room
  note → `room_notes` served in every perceiver's payload
  (`perception.py:1574, 1595, 1620`). Two model hops, no deterministic guard on
  the middle one.
- **X19 — `_llm_resolve_player_room` receives the private thought**
  (`common.py:3285-3292`) for a call whose only output is a position key.

### Runtime

- **X20 — Sound overall.** Resume grants nothing a live run would not have had;
  the audit-#10 reroll restore is present and correct *for world state*; stale
  step refusal works. The only stages reading a sibling's raw output rather
  than a projection are `background_react` ← `director_resolve` (X1-X3) and
  mapping ← raw input/events (X18).
- **X21 — (= SEAM 3 A4) `co_present_positions` includes unobserved
  destinations.** Note: `tests/test_narrator_world_fidelity.py:287-312`
  **encodes the leaky behaviour** — it asserts the destination appears. Fixing
  this requires changing that test deliberately.

### Restore / branch / archive

- **X22 — (= SEAM 4 P3) `background_presences` survives rollback**
  (`checkpoints.py:437`, uncommented unlike every neighbour), so an erased
  timeline's spoken line is replayed into the rerun's payload and
  `pending_reply`/promotion counters accrue from turns that no longer happened.
- **X23 — Sound:** checkpoint restore scoping per character; branch copying is
  per-character-scoped.
- **X24 — Legacy-archive raw-id fallback can graft imported interior state onto
  an unrelated local character.** `chat_archive.py:618-661` resolves an archive
  integer against whatever local row holds that id, then attaches the archive's
  `chat_chars.state` to it. Memories are safe. Legacy path only.

---

## Cross-seam patterns (my synthesis, for the design pass)

Findings cluster into seven recurring shapes. Fixing the shape fixes many
findings at once; fixing findings one at a time will not converge.

1. **Prose text-matching used as a security boundary.** `_redact_concealed_from_event`
   (name substring), `_surface_translate_event`, `_touch_only_sources`, the
   identity scrub, `existing_bodies` (quote body), dialogue speaker matching,
   the invented-dialogue whitelist. Every one is defeated by ordinary English —
   pronouns, paraphrase, case, a short shared line. The structural answer is to
   carry **structured identity on the event** and match on that, never on prose.
   Covers D1, D2, S3-A1, S3-A2, S3-B1, C1, C2.
2. **One shared payload for all perceivers.** Each perception pass makes a
   single LLM call whose payload must contain the union of what every perceiver
   may see; per-perceiver scoping is instruction-only, and the "one reaching
   perceiver is enough" rule is the explicit form of it. Covers A4, A5, A6, A7,
   A8, A3, X5.
3. **Deterministic delivery paths bypass the gates the model path honours.**
   The micro-loop skips containment/senses/graded sight; the outcome backstop
   skips the rear arc; `_ensure_environment` skips darkness; the background
   channel skips recognition/disguise/station; fragment hearing delivers
   verbatim. There is no single "can this observer receive this content through
   this channel?" function that every delivery site must call. Covers B3, B4,
   B5, F3, F4, X1, X2, X4.
4. **The omniscient record persists unredacted and re-enters later contexts.**
   The events row, mapping's replay, promotion seeds, dialogue memories, the
   lore path. Covers X18, P5, P1/F2, S3-A9, P7.
5. **Restore is incomplete because callers cache what it rewrites.** `ctx.cast`
   is built before the restore; `background_presences` is exempted; a promoted
   character survives. Covers P2, P3, P4, X22.
6. **Free-text state blobs with no reconciliation against the beat's own
   resolution.** Entity `posture`/`description` merge key-wise and are shielded
   from normalization, and the reconcile seam audits omissions only. Covers A8
   (seam 3), and the stale-orgasm-clause symptom that started this.
7. **Model-declared metadata trusted as the gate.** ToM `kind` sets its own
   confidence cap; lore `category`/`tags`/`range` are model-proposed and open
   the widest lore→mind door; a coerced string dialogue line defaults to overt.
   Covers F8, P6, X14, X3.
