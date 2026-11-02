# Unbuilt work — Platform, persistence, and tooling

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-12"></a>

### 1.12 Watch items

Not defects yet. Each is a measured shape that will become one silently.

- **Arousal now has a ceiling where it had a floor.** Withdrawing the false
  satisfaction stand-down exposed the somatic lift underneath it. A body at
  saturated, unreleased appetite climbs to the arousal ceiling in about five
  beats and pins there until release. Probably right — the arc has a designed
  exit — but it is the same missing-equilibrium shape as the bug it replaced,
  pointing the other way. Watch whether a long unreleased stretch reads as
  sustained or as stuck.
- **`circling` fires on routine movement in familiar space.** Honest for a maze;
  likely wrong for a resident crossing their own home several times in a scene.
- **Nine payload markers is an attention budget.** `projects`, `en_route`,
  `adrift`, `ends_in`, `ground_fully_known`, `goal_reached`/`goal_held`,
  `fading`, `project_review`. Each is something a model must notice and act on,
  and attention is finite — at some point adding the tenth marker makes the
  ninth less likely to be read. Re-checked 2026-08-19: the LIST has not grown,
  but the markers have grown sub-keys (`closer_than_last_room` /
  `further_than_last_room` inside `en_route`, `beats_since_new_ground` beside
  `ground_fully_known`), so the budget is being spent without the count
  changing. Count what a model must READ, not what the payload is keyed by.
- **The place graph's distinct contribution is narrower than proposed.** With
  pruning gone, unpruned `known_exits` + `known_dead_ends` carry most of the
  routing information by themselves; the graph's remaining unique contributions
  are `disproven` retraction, walkedness surviving the recency window,
  reverse-declared `seen` edges, and bounded eviction. They are kept as
  graph-bounded *views* rather than a second authority, which is right while both
  exist — but two representations of one fact is the shape that produced
  `rekey_place_claims` and `reconcile_inference_confidence`. **If a third
  consumer appears, collapse them** — and one has arrived to be judged:
  `world/place_purpose.py` reads `state["place_graph"]` directly, for the
  `affords` ledger rather than for routing. **The condition has now FIRED and
  this is a decision that is due, not a watch item**: verified 2026-08-19, the
  graph has three module-level readers outside its own writer —
  `agents/character.py`, `world/place_purpose.py` and `persist/commit_memory.py`.
  Collapse them or state why three is the stable number.
- **The locomotion verb list is unproven in live play.** It was tuned against
  one live `resolved_event` and the existing suite, and it includes posture
  verbs that double as ordinary elaboration — "leans in", "settles". A character
  who declared a non-locomotive act and is then written as leaning toward
  someone fires a correction retry. That is the intended reading (leaning in IS
  a distance change, and distance is the character's to declare), but it is a
  judgement call made on one example and the false-positive rate is
  **unmeasured**. Blast radius is bounded — one retry, kept only if it lowers
  the violation count, so a spurious flag costs a call and cannot corrupt the
  beat. If it proves noisy the fix is to drop the posture verbs, not to widen
  the window. *(Moved from §1.1a, 2026-08-19.)*

*(Two further bullets — observation-text duplication and the gist ladder — were
recorded negative results with retry protocols rather than watch items, and
moved to [`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md)
§5 on 2026-08-19. Neither may be retried without the protocol stated there.)*

<a id="unbuilt-1-35"></a>

### 1.35 `memories_fts` is dead, and has been for some time

9,545 rows in the live database and **zero readers anywhere in the repo** —
`grep memories_fts` outside the schema, trigger and migration statements
returns nothing. `memory_retrieval_fts`, at 10,696 rows, is the one retrieval
actually uses.

Its triggers lived in a MIGRATION while `init()` skips every migration for a
fresh database, so any Sonder database created since that change had the table,
no triggers and nothing in it.

**That half is fixed, and it was never the dangerous half.** The same drift hit
`lore_fts`, which is NOT dead — it supplies the 0.35 keyword term of
`search_lore` — so every install created in that window ranked lore on the
vector term alone, scoring 0.0 for every entry, silently. All six triggers now
live in `SCHEMA` as `CREATE TRIGGER IF NOT EXISTS`, v30->v31 rebuilds both
indexes (required for correctness, not backfill: live triggers over a desynced
external-content index corrupt it on the next UPDATE), and
`TestFreshEqualsMigrated` now holds fresh and migrated `sqlite_master` equal so
the class cannot recur.

What remains here is only the removal of the dead table itself.

Found while extracting the memory model into Nullo Engine, which dropped it on
this measurement rather than porting it. Removal here needs a migration and
should confirm the rowcount is not load-bearing for anything outside the repo
first.

<a id="unbuilt-1-40"></a>

### 1.40 A restore racing a mid-flight consolidation call

All that remains of the 216-second turn investigation (chat 71 turn 10). The
diagnosis, the three per-stage findings, what landed against them, and the
correction to the "empty specialists" misreading are in
[`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md) §3 —
they are method and measurement, not a defect.

**The one open defect.** The cancel in `restore_checkpoint` is COOPERATIVE
(between characters), so a restore arriving while one character's consolidation
LLM call is in flight can still land a summary computed from pre-restore rows,
and the cursor on that summary row then skips the window. Seconds-wide, needs a
reroll to coincide with the ~10-turn consolidation cadence, and the summary
layer is reconstructible (`backfill_memory_summary_windows` can rebuild) — but
it is a window the old synchronous design did not have, opened by moving
consolidation out of band (`schedule_memory_consolidation` → `core/jobs.py`).
Recorded rather than closed.

**Also unclosed, and it is now a lookup rather than an inference:** `narrator`
at 29.5s was attributed to the bounded rewrite ladder from code structure alone.
The per-call ledger (`_engine_notes.llm_calls`) stamps every narrator call on
the stored variant, so the next slow narrator beat answers this directly —
including whether the orchestrated path makes a rewrite MORE likely.

<a id="unbuilt-1-45"></a>

### 1.45 A dead helper family with passing tests and no production caller

**Reduced 2026-08-18.** The original entry named seven; the composer repair
closed four of them (`perception._inject_onset_sequence`,
`_inject_onset_speech`, `_strip_onset_rendering`, `_self_cannot_see_own_surface`
are gone, and `tests/test_self_surface_when_enclosed.py`'s two
`inspect.getsource` assertions on statement order inside the first went with
them in `6d843e2`). **Widened 2026-08-19: it is a FAMILY of seven, not three.** Re-verified by
grepping every non-test module — each of these has no production caller, only
the `agents/__init__.py` facade re-export and tests:

| Symbol | Where |
|---|---|
| `common._inject_visible_actor` | `agents/common.py` |
| `common._inject_action` | `agents/common.py` |
| `common._normalise_views` | `agents/common.py` |
| `common._ensure_environment` | `agents/common.py` |
| `common._fallback_perception_views` | `agents/common.py` |
| `common._perceptible_entities` | `agents/common.py` |
| `perception._deliver_foreground_body_details` | `agents/perception.py` |
| `common._action_already_rendered` | `agents/common_views.py` (added 2026-11-01, `agents_common` docs check: reachable only through `_inject_visible_actor` / `_inject_action`) |

**Five more production-dead names that tests or a tool still call** (added
2026-11-01 from `agents_common` F21; review lane L16 left them because
deleting any changes a test or tool): `common._stable_event_key` (tests),
`_scrub_undeclared_player_speech` (`tools/perception_quality.py` by
`getattr`, and tests), `common_names._SENTENCE_END` (one test), and
`_DANGLING_SPEECH_VERB_RE` / `_SPEECH_CUE` (test-only English views, loaded
at import). Two more are dead outright and await a deletion request the
review logged: `common_rooms._ambient_blocked_slugs` and
`_keys_reference_blocked` (`agents_common` F18), and the
`_check_action_direction` stub (F19). On the composer side,
`composer.micro_round_percept` / `micro_round_percepts` (now in
`agents/composer_things.py`) have no production caller and three test files
that call them (`agents_composer` F11; review lane L17 left them so the
deletion and its pins land in one commit).

So each has passing tests and no effect, which is the worst combination
available: it reads as a live floor. Six test files pin them —
`test_perception_appearance.py`, `test_perception_identity_gate.py`,
`test_enclosed_act_leak.py`, `test_player_person_discipline.py`,
`test_observable_injection.py`, `test_scene_identity_hygiene.py`.

**Three other register entries were describing behaviour inside this family and
were struck on the same reading**: §3.2 C3 (`_normalise_views` writes through an
unmatched view key) and §3.2 B4 (`_ensure_environment` does not check darkness)
are both dead paths, not live gates. `knows_identity` is the same shape one
layer over — set at six sites in `agents/perception.py` and READ NOWHERE — which
is what made §3.1 E1 unreachable.

`_inject_dialogue` and `_compose_residue_view` are the two siblings that ARE
live, both through `agents/composer.py` (and `_compose_residue_view` also
through `language_adapters/japanese.py`).

Every one of them was a repair over MODEL PROSE, and perception no longer
produces any: chronology is `Percept.order_key`, concealment is a per-percept
gate, and a rendered view is realised from percepts alone. So this is not an
oversight per symbol, it is one retirement that took its own callers with it
and left the helpers standing.

`_deliver_foreground_body_details`' two jobs appear to be superseded by the
composer IR rather than missing. The appearance half is done by
`composer.appearance_percept` → `"You see {desc}."`, which carries the same
`_appearance_as_prose` output including the `wearing:` clause. The
contradiction-stripping half looks for phrases ("no clear figure visible",
"cannot see them") that do not occur: **0 of 5,499 stored views across the
corpus contain any of them**, because the model-authored perception path that
produced them is gone.

So the likely correct change is deletion — of the whole family and of the tests
that keep it looking alive, in one commit. It is filed rather than done because it is a
judgement about design intent — whether these were meant to be deterministic
floors that were never wired — and because `agents/__init__.py` is a
compatibility facade that replay may depend on.

Corrected while finding it: an earlier note in this session's handoff claimed
the attire string never reaches perception at all. It does. It is emitted on
FIRST MENTION and again when a structural change re-earns it (`force=True` on
`appearance_percept`, gated by the render ledger), which is why sampling a run
of turns with neither shows nothing. Measured live, chat 76 turn 60, in a
player observation: `"...wearing charcoal pinstripe suit, light blue dress
shirt, ..."`. Not a defect — the suppression of per-beat repetition is the
design.

<a id="unbuilt-1-57"></a>

### 1.57 Two per-item tags in `OFFSCREEN_WORLD_COMPLETION.md` overstate what is built

`docs/design/OFFSCREEN_WORLD_COMPLETION.md` is a design note and its per-item
tags are one of the four rival status surfaces `docs/README.md` names. Checked
against source 2026-08-18; recorded here because `UNBUILT.md` is the register
and the note is argument.

- **§2 "Build crowds and persistent fixtures — BUILT (2026-08-10)"** claimed
  all five ordered steps were in the tree, and two were not. Step 1 ("a
  stationary crowd blob visible to ordinary perception") landed 2026-08-18:
  `composer.room_content_percepts` mints the crowd, the courier and the posted
  notice as `ambient` percepts from the per-observer dicts perception had been
  computing and dropping. Step 2 ("persistent location fixtures": barkeeps,
  vendors, guards, attendants, regulars belonging to a LOCATION and
  re-meetable) still has no implementation anywhere; background presences are
  scene-scoped and are a different thing. Steps 3–5 (density as terrain,
  movement/splitting, one-way emergence) are real: `world/crowds.py`'s
  `density`/`terrain`/`drift`, `advance_crowds`/`split_band`, and `emerge`.
  **So the item is still not BUILT, for one step instead of two.**
- **§5's "`offscreen_log` has exactly one reader, `gaps.interim_for`"** is
  wrong: there are three read sites — `world/gaps.py:268` (the consumer),
  `world/offscreen.py:464` (`append_offscreen_log`'s own read-modify-write) and
  `world/spatial_frames.py:906`/`1053` (frame fork and merge copying the key).
  The claim it supports — that no diagnostic surface exists to spoiler-gate —
  survives, since only one of the three is a reader in the sense meant. The
  sentence is what is wrong, not the conclusion.

<a id="unbuilt-1-58"></a>

### 1.58 Schema-touching work deferred by owner policy 4

The 2026-08-18 repair wave authorised **exactly one** schema migration
(`persona_carrier_state`, landed as SCHEMA_VERSION 30 — the player's carrier
envelope was the one carrier home outside `FRAME_SCOPED_WORLD_KEYS`, so what
the player witnessed in one era survived a rewind or a branch). Every other
schema-touching finding was deferred here rather than half-done, on the
principle that a migration deserves its own pass, its own testing and its own
release. This entry is that paperwork. Each row below is CONFIRMED against
source; none is speculative.

The checklist every one of them owes is `docs/guides/DATABASE.md` §
"Schema-change checklist" — eight steps, and the ones that actually bite here
are 4 (export/import payloads), 5 (checkpoint snapshot AND restore) and 6
(branch/clone id remapping in `web/app.py`). A frame-scoping change owes one
more that the checklist does not name, because it is specific to this engine:
**a bare `wget` redirects on the AMBIENT frame and is the caller's era only by
accident**, so every read site has to be re-examined for whether it wants
`wget_for_frame` with an explicit frame, not merely left alone.

- **PERSISTENCE-F17 — two world keys are not frame-scoped while their
  siblings are.** `world_pressures` (`persist/commit_ledgers.py`) and
  `background_claims` (`world/background_claims.py`, six sites) are plain
  `wget`/`wset`. So a pressure raised in one era and a claim ratified in one
  era are visible from every other era, and a rewind does not retract them.
  (This row named a third, `engine_notices`; `core.db.FRAME_SCOPED_WORLD_KEYS`
  has scoped it since the playerless Aldermill run of 2026-09-23 -- corrected
  2026-11-01 from the `persist_scene_entities` docs check.) Adding a key to
  `FRAME_SCOPED_WORLD_KEYS` is not itself a migration — the scoping is a key
  rewrite at the storage layer — but the EXISTING rows keep the unscoped key
  and would go silent on the next read, so the data migration (re-key each row
  to the era that wrote it, or to the ambient frame) is the work.
- **RUNTIME-11 — `world_conditions` has no `frame_id`.** Same shape, different
  storage: this is a real column on a real table (`core/db.py:716`), and
  `story/scene.awareness_conditions` queries `WHERE chat_id=? AND
  kind='awareness' AND active=1` with no era filter at all. A character
  knocked unconscious in one era is unconscious in every era of that chat.
  `world_events` already carries `frame_id` as an explicit FK, so the shape to
  copy exists; the migration is the column, the backfill, and the
  `world_conditions` readers.
- **PERSISTENCE-F15's gate half.** The writers half is not deferred and landed;
  moving `_backfill_resource_uids` behind the version gate bumps
  `SCHEMA_VERSION`, so it waits for the same pass.
- **PERSISTENCE-F5's drop half.** The three deprecated macro-geography tables
  (`fiction_worlds`, `fiction_locations`, `transit_edges`). The doc correction
  landed; dropping them is a schema change. `transit_edges` is the cheap one —
  nothing snapshots, exports or restores it, so there is nothing to migrate.
- **RUNTIME-6's stored-data purge.** The write-side fix landed — the
  `candidates` payload is no longer persisted with each step. The
  already-written payloads remain: measured read-only on the owner's install
  2026-08-18, **590 variant rows carrying 7.16 MB of `candidates`**. A purge is
  an UPDATE over live stories' saved steps, which is why it is here and not in
  a tidy-up commit. That number GREW between the audit (4.9 MB) and this
  measurement, which is the argument for doing it rather than against: the
  write side is fixed, so the cost is now fixed too and will not grow again.
- **The four dead settings keys** — §1.51b, kept there because the diagnosis is
  there. Listed again here because the repair is the same kind of thing: a
  migration that deletes rows from live stories at next launch.

<a id="unbuilt-1-61"></a>

### 1.61 Half the prompt ids are outside the prompt/schema drift check

`tools/project_check.py`'s `check_prompt_schema_ops` exists because the same
defect landed three times in two days — a prompt asking for an `_ops` field the
stage's model does not have, so Pydantic drops every op silently (`project_ops`
cost an entire tier of psychology: "has ever held a project: 0 of 14 banks").
It iterates `schemas.SCHEMA_MAP` plus `PROMPT_MODEL_ALIASES`.

Measured 2026-08-18: **21 of 41 prompt ids are inside the check and 20 are
outside it**, and they are outside STRUCTURALLY rather than by oversight —
there is no Pydantic model to check them against, because their outputs are
consumed as raw dicts. The twenty: `ambience_prompt`, `artifact_wording`,
`fill_appearance`, `fill_character_psychology`, `generator_character`,
`generator_greeting`, `generator_lorebook`, `generator_lorebook_entries`,
`generator_persona`, `import_character_reinterpret`,
`import_persona_reinterpret`, `lore_reinterpret`, `memory_consolidate`,
`offscreen_agent_adjudicate`, `offscreen_agent_attempt`, `offscreen_profile`,
`patch_json_field`, `position_resolver`, `promote_character`, `repair_json`.
(The three `offscreen_*` ids were deleted on 2026-11-01 with the paid
off-screen tiers that fetched them, so seventeen of these remain.)

The generator group is the sharp one: `book_ops`, `link_ops` and `entry_ops`
are asked for by name in those prompts and opened as raw dicts on the other
side, which is exactly the `entry_ops`/`entries` defect the check was built
for, sitting where the check cannot see it. **Blocked on an owner decision** —
"how should the generator prompts be typed" is an API-shape question about
`llm/schemas.py`, not a checker change, and typing them is what makes the
checker cover them for free. Audit TOOLS-S3.

<a id="unbuilt-1-62"></a>

### 1.62 An extra player has no opening turn

Two halves of one repair, in two files, both confirmed 2026-08-18:

- `agents/runtime.establishment_plan` is a five-step list
  (`compile_world_context` -- spelled `mapping_stage` here until the
  2026-11-01 docs check -- `director_establish`, `perception_establish`,
  `narrator`, `commit`), widened only by extension splices, and never appends
  `narrator_extra`, which `build_plan` does append on every normal turn when
  the chat has extra players in this frame.
- `agents/perception.perception_establish` builds perceivers for `"player"` and
  for each cast member, and no `extra:<pid>` perceiver at all — `perception_act`
  and `perception_outcome` both do (`agents/perception.py:2051`).

So a co-player attached before the story opens receives no view of the opening
scene and no render of it; the first thing they see is turn 1. Nothing warns —
the plan is simply shorter. `agents/narration.py:1119` already reads
`establish_views.get(f"extra:{pid_key}")` before falling back to the outcome
views, so the narrator half is waiting for a key nothing writes, which is why
this reads as built until you go looking for the producer. Audit RUNTIME-4.

<a id="unbuilt-1-88"></a>

### 1.88 A restored checkpoint is as old as the beat it snapshot

A checkpoint restore deletes every world row and writes the snapshot back
verbatim, so a blob taken before the `scene.time` / `scene.time_of_day` split
comes back in the pre-split shape: 2,731 of 2,810 stored blobs carry
`scene.time` and none carries `time_of_day`. Within the session, a restore
therefore reproduces the empty-clock symptom the split exists to remove. The
next `db.init()` repairs it, so this is a within-session defect rather than a
durable one.

**A recovery call on the restore path was built and then REVERTED**, and the
reason is worth keeping. Restoring a pre-split blob and converting it makes the
restore a MUTATION, and `test_rerun_of_the_same_turn_produces_an_identical_world`
is the invariant that forbids it: reroll restores the pre-turn checkpoint and
re-runs the beat, and the two worlds must come out byte-identical. A conversion
that fires on the first restore and not the second breaks that. Narrowing the
call to rows that actually carry the old shape (`only_pre_split`, which is why
that parameter exists on `recover_scene_time_of_day`) fixed a second, different
regression — a restore of one era stamping an empty key onto another era's
scene row, caught by
`test_restoring_mid_a_framed_turn_does_not_clobber_the_present` — but does not
fix this one, because the pre-split shape is exactly what the conversion acts on.

So the fix is not a call on the restore path. Either the snapshot is upgraded
when it is WRITTEN rather than when it is read, or the readers tolerate a
pre-split scene for the life of a session. Reroll identity is not negotiable
against a cosmetic within-session gap.

<a id="unbuilt-1-94"></a>

### 1.94 A time block that disagrees with itself is not detected

The anchor rule (1.84a, closed) decides what to do with a block anchored away
from the engine clock: only its span crosses. It says nothing about a block that
is incoherent WITH ITSELF.

    read_time_diff(100.0, {"start_seconds": 100, "duration_seconds": 0,
                           "end_seconds": 9999})  ->  9999.0

That block is anchored correctly — its `start_seconds` matches where the clock
stands — so its absolutes are trusted verbatim, exactly as the rule intends. But
it claims a beat that began at 100, took zero seconds, and ended at 9999. Those
three cannot all be true, and nothing notices: no warning, no `displaced` slot,
no refusal.

The three fields are over-determined by one: `start + duration` should equal
`end`. When they disagree, one of the three is wrong and the reader currently
picks by precedence rather than by noticing the contradiction.

Found by a confirmation test whose own fixture was wrong — it asserted that
`duration_seconds: 0` beside an absolute should mean no time passed, which is
not what the documented guarantee says. The guarantee is that a beat keeps the
authority to say no time passed BY SAYING IT, and `{duration_seconds: 0}` alone
does exactly that. Registered rather than fixed because the resolution is a
judgment about which of three contradictory fields to believe, and that is the
same class of choice as 1.84a — not a patch.

<a id="unbuilt-1-160"></a>

### 1.160 A phantom character id, one past the real one, is written into memory

Chat 117 carries `character:79` in **153 step variants and 111 memory rows**,
from turn 2 onward. There is no character 79 and no persona 79: the chat's
one attached character is 78 (Sarah Moon) and the player is persona 20 (Aurel
Voss). Every id present is 78 or 20; **79 is 78 + 1 and belongs to nobody.**

It is not cosmetic. It is the KEY the beat routes conduct and cognition
through. The interaction/reaction loops address every one of Sarah's actions
`targets: ["character:79"]`, and her theory-of-mind about the player is
stored under it: memory row, verbatim -- *"I suspected this about
character:79: Pragmatic, steady under emergency conditions... I based that on:
Correctly deduce[d]..."*. So Sarah's model of Aurel is filed against an id
that resolves to no body; anything that later reads her belief about the
player by his real handle finds nothing, and anything that reads 79 finds a
person the world does not contain.

**Scope: this one chat.** `character:79` appears in no other chat in the
corpus, which points at something particular to how this story numbered its
bodies -- a persona-plus-attached-character chat where the count-derived id
(one past the last real character) was minted as a target and then never
reconciled to either the persona or the character. The off-by-one is stable
(always 79, never 77 or 80), so it is a single derivation, not noise.

**Not traced to source here** -- it needs its own pass through how a beat
assigns `character:<id>` to the player and how `targets` are validated (they
are not: an id in no table reached `interaction_loop`, `reaction_loop`,
`director_resolve` and the memory writer unchallenged). Registered now
because it is a data-integrity leak into durable memory, measurable and
bounded, and because the fix wants the id space audited rather than the
symptom patched: the player is a persona, not a character, and giving them a
`character:<n>` handle at all is where to start.

<a id="unbuilt-1-161"></a>

### 1.161 The 2026-09-07 review: what landed and what is still open

**Found:** 2026-09-07, by a 57-agent read-only review of every package, both
language packs and the docs, each finding re-read by an independent skeptic.
The full synthesis is `docs/experiments/REVIEW_2026-09-07.md` (319 findings,
Sections A-F). Its fifteen-item build order landed the same day: the shared
JSON-mode recovery ladder and typed stream failures (`llm/providers.py`);
single-step reroll hydrating only the steps before the rerolled one; one label
per (observer, body) on the outcome pass, the authored-prose gate writing
`detail`, the rear arc live on both passes; interpret-side hands shown the
ruling that dispatched them, the note-key resolver (`note_key_targets`,
`RETIRED_HANDS`), phase provenance by stage; the schema-derived repair merge
and diff normaliser, no manifest clamp, room-bound mint binding, the previewed
scene on the repair pass; one identity floor across the debt note, the
micro-round, background presences and both narrators; script-aware boundaries
at the firewall sites with the disguise guard's vocabulary in the packs
(`story.scene`); the spatial truth pack (forward first hop, two-ended
severance, one-way window heard, corridor lamps at the room's centre, sized
sprints, an interior record as a mass); `medium` on the dialogue schema, the
near field's events, `far_path_gain` None for unjoined rooms; the five charter
fixes and `needs_template`; one registry per commit (`registry_session`);
vectors filed at mint (schema v37) and the checkpoint remap's two frame
rescopes, branch membership from the snapshot; the Room reading the frame it
means and the editors writing the entries they name; the frame merge carrying
the away party's ledgers; and the wall-clock pack.

**Still open, by section of the synthesis** (each is stated there with file,
line, evidence and the class rule):

* Section A high items not in the build order: A16 (Room lines clipped on
  restore -- LANDED with item 13), A18/A19 (LANDED), A22 (LANDED), A25 (LANDED
  as `needs_template`), A26/B1 the outcome-pass scene mirror vs commit's
  composition (`compose_beat_scene`, deferred: it moves five structure passes
  into a stage that runs before resolve and needs the perception_outcome <->
  commit contract restated first).
* Section A medium: A29-A34, A36-A38, A41, A43-A44, A49-A89 except those the
  build order named. The largest reader-visible ones: A36 `source_manifest`
  computed and read by nobody (D1 is its delivery), A37 a standing disguise
  re-earning the full description every beat, A55 ruin undone by the registry
  projection, A56 `positions` read as a body roster, A57 vitals keyed by
  spelling, A82 declared `consequences` dropped by an off-by-default gate,
  A83 (LANDED with item 15), A87 sight hard-wired to light, A88 weather as a
  closed Earth vocabulary, A89 an outfit region outside `REGIONS` dropped.
* Section B: every two-representations item except B3, B16, B26 (landed).
* Section C: C2 (LANDED), C3/C4 (LANDED), C5 (LANDED), C6 (partly: the route
  memo), C11 the scene-blob memo on the PipelineContext (deferred: most
  `get_scene` callers mutate in place, so it needs the read/for-update split
  and a measurement first), C7-C10, C12-C22.
* Section D, the improvements from other arts: none built. D1 (tells reach
  the page) is next once the outcome pass is clean; D2 (a voice established
  once), D3, D6, D7, D9, D12 are composer/narrator-payload work; D13-D16 are
  the Dramaturge's; D17-D22 the charter's and psychology's; D8 is a design
  ruling for the owner.
* Section E, the stale-docs table: the counts, the retired hand and the
  statements the build order made true or false were corrected in the same
  commit; the rest of the table stands as the list to work through.

<a id="unbuilt-1-171"></a>

### 1.171 A failed model attempt leaves no trace in the ledger or the log

`chat_complete` retries a failed attempt (`llm/providers.py:3355`), but only
the attempt that succeeds reaches `record_llm_call` (the step's
`_engine_notes.llm_calls`) and the `llm_call` log line; a failure emits a UI
`generation_reset` notice and is otherwise unrecorded, reason included. Only
`llm_capture.duration` times the whole call. On 24 reruns of real character
steps on 2026-09-28, the two disagreed on 10: 388 s of 827 s of character-call
time (47%) went to attempts no ledger recorded
([`MEMORY_WINDOW_REPLAY_2026_09_28.md`](experiments/MEMORY_WINDOW_REPLAY_2026_09_28.md) § 5).
The two calls that exhausted every attempt died on the degenerate-repetition
guard, the likeliest cause of the rest. Anyone timing turns from the ledger or
the log reads the successful attempt alone. Wanted: a ledger entry per failed
attempt, with its duration and error class.

<a id="unbuilt-1-172"></a>

### 1.172 Every memory write scans the whole retrieval index

`mind/memory_write._replace_memory_fts` and `_delete_memory_fts` find a
memory's row in `memory_retrieval_fts` with `WHERE memory_id=?`, and
`memory_id` is an UNINDEXED FTS5 column, so every lookup is a full scan of the
index across every chat (`SCAN memory_retrieval_fts VIRTUAL TABLE INDEX 0`).
Measured 2026-09-28 on a copy of `engine.db`: 40.3 ms per lookup at 25,384
rows, against 0.021 ms by rowid. Each new memory at commit pays one scan; a
checkpoint restore (every reroll and every rerun from a stage) pays two per row
of the chat's bank inside `apply_chat_memory_restore`: 23 s for a 292-row bank,
timed, and by extrapolation about 80 s for chat 64's 1,009. It grows with the
whole database, not the chat
([`MEMORY_WINDOW_REPLAY_2026_09_28.md`](experiments/MEMORY_WINDOW_REPLAY_2026_09_28.md) § 5).

The fix is to key each FTS row by rowid = memory id and delete by rowid, which
needs the existing index rebuilt: migration work, so it waits for §1.58's
policy.

<a id="unbuilt-1-186"></a>

### 1.186 The format ladder after a hold, and service tiers (2026-10-08)

- **The flag's drop does not survive a restart.** A grammar suspension
  persists for 24 h (`providers_schema_suspended`), but `_NO_JSON_OBJECT` is
  process-local. After a restart inside the window, a suspended pair is sent
  `json_object` again and pays two holds (2 x 30 s) before the flag is
  dropped.
- **A formatless rung that is itself silent restarts from the grammar.**
  After a hold, the ladder retries without a format. When that rung also
  goes silent it is re-raised, and the outer retry rebuilds the original
  format. On OpenRouter glm-5.3 (Brackwater beats 27-29), 3 of 4 formatless
  rungs went silent too, so those silences were the route's; the format-
  bearing retries answered 2 of 3 times. Continuing down the ladder instead
  was proposed and not built: stage two strips the reasoning controls and
  samplers, which is a different request, not a remedy for a slow upstream.
- **Service tiers have no models-panel column** (raw `service_tier` setting
  only). A flex capacity error takes the ordinary retry ladder, never a
  standard-tier retry of the same call. Flex latency on a full-size encoder
  call is unmeasured.

<a id="unbuilt-1-197"></a>

### 1.197 An active prompt preset masks every later change to the card it replaces (2026-10-09)

The owner's play on chats 160-166 ran with `active_preset` = `tes`, a preset whose one entry replaces `character_bare` whole: the card as it stood on 2026-09-27 (5dd8b65a) with "You know nothing else: what never reached you stays unknown," taken out. `llm/prompts.py` `_preset_override` hands that text to every bare character call, so no change to the pack's bare card after 2026-09-27 reached that play -- the context and kept-thinking sentences (2026-10-05, 2026-10-06), the tells cadence and the observable floor (2026-10-08), the project wording and a sign without its reading (2026-10-09), and the sign alone (2026-10-10). Measured on the stored captures: all 102 `character_major` calls on chats 160, 161, 163, 165 and 166 (2026-10-02 to 2026-10-07) carried the preset's text, the one on chat 159 (2026-09-30) the pack's; the Brackwater run's prose findings and the 2026-10-08 tells A/B were taken against the preset. **Switched off by the owner on 2026-10-10:** the owner's database runs `active_preset` = `Default`, with `tes` kept among its stored presets. A copy taken before then still runs `tes` -- the scratch play database copied on 2026-10-07 does -- so a validation run on such a copy sets `active_preset` to `Default` first, or it measures the 2026-09-27 card. Nothing in the engine says whether an override is stale: it keeps no record of the pack text a preset was written against, so neither the prompt editor nor a log can tell a kept override from a stale one.

- **Owner decision, still open:** `tes` took "You know nothing else: what never reached you stays unknown," out of the bare card -- whether the pack card should lose it too.
- **What would make it visible (not built):** keep, beside each prompt a preset replaces, the pack text (or its hash) it was saved against, and flag the override in the prompt editor, and once per process in the log, when the pack text has changed since.

<a id="unbuilt-1-212"></a>

### 1.212 One code version per process -- built 2026-10-13, residuals open

Design.md: "One server process runs one version of the engine". What it does
not reach:

- **A spawned worker imports from disk.** The charter's pre-simulation pool
  (`world/charter_runtime.py`, `ProcessPoolExecutor`) forks on Linux, where
  the children share the parent's modules; on Windows and macOS it spawns,
  and each child imports the engine from disk -- the version the parent holds
  only if the tree has not changed since start.
- **A file added after start is not noticed.** The fingerprint compares the
  files the process held when it started; a new module or a new card part
  appearing later is not a change until it is read, which today means a
  restart.
- **Extensions are out of scope**: they keep their own reload path.


<a id="unbuilt-1-264"></a>

### 1.264 A database older than v7 cannot be opened (2026-11-01 review)

`persistence_paths_schema` F18, confirmed on a scratch database stamped 6
(`OperationalError: no such column: resource_uid`). `core/db.py`'s docstring
promises any older version opens, but `init()` runs `executescript(SCHEMA)`
before the migration chain, and SCHEMA creates indexes on columns that
v2, v4, v7 and v8 add (`uq_characters_resource_uid`,
`idx_memories_chronology`, `idx_lorebooks_parent`, ...). SCHEMA's own
comment explains the hazard for `idx_lorebooks_anchor` alone, which alone
moved to `LATE_SCHEMA`; and `tests/test_schema_integrity_fresh_vs_migrated.py`
builds the CURRENT schema and stamps 1, so it cannot see it. No such
database is known to exist (the owner's is v45). Skipped by review lane L3:
**the owner's decision** is which versions the engine promises to open --
move every migration-dependent index to `LATE_SCHEMA`, or refuse below a
named oldest version with a named error.

<a id="unbuilt-1-265"></a>

### 1.265 Captured text a prune orphans waits for the next story deletion (2026-11-01 review)

`persistence_paths_schema` F15. Capture retention never ran -- `prune` and
`vacuum_blobs` had no callers. Review lane L3 wired both:
`llm_capture.record_exchange` prunes a chat to `RETAIN_TURNS` (200) on a
turn's first captured call (capture is off by default), and
`chat_delete.delete_chat_data` runs `vacuum_blobs()` after its transaction
(`tests/test_a_capture_is_kept_to_its_window_and_dies_with_its_story.py`).
What it left: blobs orphaned by a PRUNE, not a deletion, stay in
`llm_blobs` until some story is deleted, and `vacuum_blobs` reads every
capture row, so it is O(capture store) wherever it runs. **The owner's
choice:** a vacuum per turn (a new cost and rate), a vacuum on some other
cadence, or deletion-only as now.

<a id="unbuilt-1-266"></a>

### 1.266 A book a turn minted after a checkpoint is carried into it by a later refresh (2026-11-01 review)

The residual of `persistence_paths_schema` F6. Every checkpoint refresh now
carries the host's book-set change and keeps the beat's own entries as
taken (`checkpoints._carry_the_book_set`,
`tests/test_a_book_refresh_carries_the_hosts_change_not_the_beats.py`). But a
chat-owned book MINTED by a turn after the checkpoint -- a location or
vehicle book, a canon book minted on its first write -- reads "added since"
and is carried into the checkpoint by any later refresh. `lorebooks` has no
`created_turn_id`, so a host's fork (origin set) and a turn's mint (origin
NULL) can be told apart, but a host's `POST /api/lorebooks` book (origin
NULL) cannot. **Needs a provenance field or the owner's ruling**, and it is
the same question as §1.267.

<a id="unbuilt-1-267"></a>

### 1.267 Which lorebook edits a reroll carries is decided route by route (2026-11-01 review)

`web_app` F10, confirmed by trace. `web.app._refresh_rewindable_checkpoints`
exists because "retrieval is snapshotted with the turn, so the checkpoint
has to move with the books or a rewind restores the old reach", and it is
called from attach, enable, detach, bind and unbind (since 2026-11-01 also
from an unbind written as `{"lorebook_id": null}`, `web_app` F9). The
routes that change the reach of the story's own books in other ways never
refresh it: `lorebook_link_create` / `_update` / `_delete` (where
`follow_for_retrieval` and `weight` are reach) and `lorebook_move` /
`lorebook_reorder` (where parent and inheritance are). The restore puts
parents, links and entries back, so a host who links two of the story's
books and rerolls loses the link -- the exact symptom the attach refresh was
written for -- while the reroll confirm (`static/js/chat.js`) tells the host
"lorebook edits" are reverted, untrue for attachments. **The owner's
ruling**, stated once: which lorebook edits are configuration (carried
across a rewind) and which are story facts (reverted).

<a id="unbuilt-1-268"></a>

### 1.268 Stopping the server waits for every turn in flight (2026-11-01 review)

`web_app` F18. `web.app._shutdown_engine`'s docstring said "Daemon threads
mean nothing HANGS", but `_drain_on_own_thread` starts its thread without
`daemon=`, daemon status is inherited, and AnyIO's worker thread is not a
daemon; the shutdown neither aborts nor tracks these threads. So Ctrl-C, or
a `make run` reload, waits out every in-flight turn -- minutes -- after the
lifespan has "finished". **The owner's call:** abort with a bounded join,
or wait for the commit; the docstring then says which.

<a id="unbuilt-1-269"></a>

### 1.269 A guest's input has no size or rate bound (2026-11-01 review)

`web_routes_extensions` F21, confirmed by reading. `web.app.guest_input`
takes any length, at any rate, for any `idx >= 0`; `_submit_player_input`
upserts per (chat, idx, persona); `guest_state` reads all of the guest's
rows on every poll; and the next served declaration rides the Director's
and narrator's payloads -- so a guest script posting multi-megabyte lines
for idx 0..N grows `turn_player_inputs` without bound and spends the host's
provider budget, from the less-trusted actor this module exists for.
Skipped by review lanes L2 and L1 alike: **the owner's numbers** -- a byte
cap and a rate (the join limiter's pattern is there to reuse), and whether
`idx` is limited to the guest frame's next-beat window.

<a id="unbuilt-1-270"></a>

### 1.270 Only first-run setup checks the Host a request was sent to (2026-11-01 review)

`web_routes_extensions` F2. During the unclaimed first-run window -- a fresh
install, or every restart under `FICTION_ENGINE_RESET_HOST=1` --
`request_is_local` reads only the TCP peer, so a DNS-rebinding page in the
host's own browser counted as local, could claim setup and got a
same-origin `fe_host` cookie. Review lane L1 fixed it narrowly:
`POST /api/auth/setup` from an IP peer is refused unless the Host is an IP
literal, `localhost` / `*.localhost`, or a name in `SONDER_SETUP_HOSTS`
(`web.app.SETUP_HOSTS_ENV`, empty by default;
`tests/test_first_run_setup_answers_only_its_own_address.py`). It assessed
and did not make the allowlist for every `/api/*` that review lane L2 called
better: it would lock a tunnel or LAN name out of an instance already
claimed unless the operator declares it, and after setup a rebinding page
holds no cookie and no password. **The owner's decision:** the narrow rule,
or the whole-API allowlist and the declaring it demands of a host on a
tunnel or a LAN name.

<a id="unbuilt-1-271"></a>

### 1.271 A branch holds the write lock while it re-dumps every older checkpoint (2026-11-01 review)

`persistence_paths_schema` P4 (with P3). `web.app.turn_branch` holds the
global write lock while it parses, remaps and re-dumps every checkpoint.
Review lane L3 cut the remap itself (one 4.0 MB checkpoint with 2k entities
and a 3k-body charter: 1.003 s -> 0.002 s, by no longer remapping
chat-partitioned ids), which leaves about 0.44 s a checkpoint inside the
lock for `json.loads` + `json.dumps` (a 41 MB charter row scales about ten
times). Two changes were written out and not made: copy steps, variants
and events with `INSERT ... SELECT` instead of pulling every variant
through Python; and move the older checkpoints' parse/remap/dump out of the
lock by splitting the transaction -- commit the branch with its
branch-point checkpoint, then insert each older one in its own short
transaction. **The owner's call is the split:** it trades "a failed branch
leaves nothing visible" for the older checkpoints only -- a branch missing
them is playable, just not rewindable past its start.

<a id="unbuilt-1-272"></a>

### 1.272 A grammar verdict is per model, and its stall count never decays (2026-11-01 review)

The two skipped parts of `llm_providers_quality` F8. Review lane L13 made a
json_schema rejection heal across restarts: the stored verdict is a
timestamp, a lapsed one is pruned, and a grammar-bearing answer removes it
(`tests/test_a_grammar_rejection_heals_across_restarts.py`; in the process
that saw the 400 it stays permanent). Left for the owner: (a) the verdict is
keyed on the MODEL, so one step's oversized grammar costs every role on
that model -- keying it on the schema too changes what the verdict is about;
(b) `providers._SCHEMA_STALLS` never decays or resets on success, so a model
that stalls one call in three is suspended in time; changing that changes
the measured "two stalls" threshold's meaning. (The owner's memory note
"the grammar blacklist never heals" is now stale for 400s as well as
stalls.)

<a id="unbuilt-1-273"></a>

### 1.273 The call ledger's `in` means two things by dialect (2026-11-01 review)

`llm_providers_quality` F14. Review lane L13 put reasoning tokens on the
ledger (`providers._log_usage` writes `reasoning` when the provider reports
it, and leaves it absent when it does not -- unmeasured is not zero;
`tests/test_the_ledger_says_how_much_was_thinking.py`). It implemented and
reverted the other half: normalising `in` to the inclusive total for
Anthropic and the CLI (`input_tokens` plus the two cache fields; the
Responses dialect's `input_tokens` is already inclusive) changes five pinned
assertions in three test files (`test_usage_telemetry.py`,
`test_llm_call_ledger.py`, `test_claude_cli_provider.py`) and what the
stderr metric means. **The owner's decision:** one meaning for `in` -- a
six-line change in `providers._normalize_usage` plus those five pins -- or
two, documented.

<a id="unbuilt-1-274"></a>

### 1.274 Two schema enums are second spellings, and six models are validated by tests alone (2026-11-01 review)

`tooling_gate` F5. The schema reachability test was satisfied by a class
name in a comment; review lane L14 rewrote it to read reachability off code,
which found seven classes beyond the audit's three that only text reached.
Review lane L13 deleted the two nothing read (`Engagement`, `BookOp`). The
rest are kept by name, each with the test that needs it
(`tests/test_schemas.py`'s `kept`): `PlayerAuthorityMode`, a second
spelling of `story.scene.PLAYER_AUTHORITY_MODES` that only a test holds
equal; `BehaviorController`, whose first spelling (`OFFSCREEN_LIFE_LADDER`)
and the test that held the two equal were deleted with the off-screen ladder
on 2026-11-01, so it is held by nothing and goes with the next edit to
`llm/schemas.py`; and `ActionElement` (with its field types `ActionCommitment` and
`IntendedEffect`), `LoreOp`, `DestructionEffect` and `Observation` -- shapes
the engine never validates, since every `sequence` is `list[dict]`.
**The owner's question:** one spelling per vocabulary (delete the enums and
rewrite their two tests against the `story.scene` tuples), and for the
fixture models, engine validation or deletion -- deleting a kept name means
deleting the model.

<a id="unbuilt-1-275"></a>

### 1.275 An extension's character-hook attribution is lost on a rerun (2026-11-01 review)

`tooling_gate` F3. The side-channel check read only `agents/` and `story/`;
review lane L14 widened it to every engine package, which found
`extension_runtime`'s `_extension_routing` (and the commit's own
`_engine_notices_rewritten`). `_extension_routing` is now declared in
`runtime.SIDE_CHANNELS` honestly: diagnostic, and NOT rebuilt -- a resume or
rerun that does not re-run the character stage commits without that
stage's notes of which extension rewrote what a mind or the narrator was
handed. **The owner's call:** rehydrate it from the persisted character
variants on resume, or accept that a rerun from the narrator or the commit
loses the attribution.

<a id="unbuilt-1-277"></a>

### 1.277 CI proves the direct pins, not the stack players run (2026-11-01 review)

`tooling_gate` F17 (plausible; no defect measured). `constraints.txt` pins
the twelve direct packages and transitive dependencies float: CI resolves
fresh on every push, while a player's `.venv` is reinstalled only when the
digest of `requirements.txt` plus `constraints.txt` changes. On the audit's
day CI and the owner's `.venv` differed on anyio, websockets, uvloop,
watchfiles, urllib3, httptools, idna and click; only the direct pins
agreed. "CI is the authority" holds for the direct layer only, and no
Windows or macOS leg runs although a `.bat` launcher ships. Review lane L14
added `make stack`, which reports how the running interpreter differs from
the pins. **The owner's call:** a full lock file used by both the launchers
and CI (for example a `pip freeze` from the CI job), and whether to add the
other platforms.

<a id="unbuilt-1-278"></a>

### 1.278 `tools/package_edges.json` is generated and read by nothing (2026-11-01 review)

`tooling_gate` F12. The edges table was stale (58 rows against 72; 59
differing) and the walker missed an import under an `if` inside a function;
review lane L14 fixed the walker and regenerated the table
(`--write-package-edges`), and the cycle baseline (`[agents, persist, story,
world]`) is unchanged and checked. But nothing reads the edges, so they will
go stale again. **The owner's call (the audit proposed, did not choose):**
store the cycles only, or ratchet the eager edges inside the cycle.

<a id="unbuilt-1-279"></a>

### 1.279 The caps the 2026-11-01 fix lanes named, kept at today's values for the owner to set

Every cap, bound and rate the review's lanes touched is named in code and
kept at the value it had (or, where it is new, at one chosen to cut nothing
measured), per the standing rule to name a cap rather than bury it. Each
number is the owner's:

- `director.ENGINE_NOTICES_SHOWN` = 8 (new): how many of the commit's
  notices reach the next beat's author and encoder; the rest are counted.
- `director_fanout.PUBLIC_SOURCES_SHOWN` = 20 and
  `director.PUBLIC_EVIDENCE_KEPT` = 12: bare slices before, now named and
  said when they cut. 12 < 20, so 12 is the cut that bites; whether the
  overflow falls back rather than drops is part of the call.
- `charter_intervene.INTERVENTION_CAP` = 64 (a scheduled end is now never
  evicted for room); `charter_trigger.TRIGGER_CAP` = 32 and
  `TRIGGER_THEN_CAP` = 3 (a cut is now reported, and the shipped default
  rule is never the one evicted).
- `lots.LOT_STOREYS_MAX` = 4 now also bounds the architect's answer for a
  lot the plan gave no storeys, and a lot with no `cellar` refuses a level
  -1 room (`DESIGN_BUILDING_LOTS.md` "Defaults").
- A structure's `max_planned` (200): one meaning now (a lot's interior is
  not frontier), the number unchanged.
- `director_layout.LAYOUT_RUN_NOTES_MAX` = 12: the 12 a refusal was always
  cut to, now named and shared with the solve's warnings.
- `web.world_routes.LINT_MEMO_SIZE` = 16 and
  `director_repair.ATTRIBUTION_MEMO_SIZE` = 64: cache bounds, not behaviour.
- `character_jev.MAX_AIMS` = 5: the aims a read-back offers, now filled
  around every held project rather than cut by position.
- `ambience.QUERY_TERMS` = 9: the search's term cut, now applied before
  its own "ambience" anchor.
- `research_providers.FETCH_REDIRECTS_MAX` = 5 (new; requests' default was
  30) and `providers.HTTP_POOL_MAXSIZE` = 32 (new; requests' default was 10
  per session).
- `plot_packages.PUBLISH_ATTEMPTS` = 3 (new): publish refuses after three
  races with a story that kept moving.
- `RUN_FOLLOW_POLL_MS` = 2000 doubling to `RUN_FOLLOW_POLL_MAX_MS` = 30000
  (`static/js/chat.js`), and `GUEST_POLL_MAX_MS` = 60000
  (`static/guest.html`): the re-attach and guest back-off polls.
- `character._MEMORY_CONTEXT_POOL` (4 workers) against
  `skip_stage.SKIP_ASK_WORKERS` (8): minds five to eight of a skip queue for
  an embedding round trip; raise the pool to 8 (or `max(4,
  SKIP_ASK_WORKERS)`), or keep 4 to bound concurrent embedding calls.
- `affect._FORMER_PROJECTS_CAP` = 6: how many unauthored project endings
  the former ledger keeps (every authored ending is now kept regardless).
- Two caps found unnamed and not yet named (`agents_director_prose_movement_rooms`
  F13 and F17): `director_rooms.inspect_rooms` takes the first six ids
  silently, and `director_prose.bind_new_places` stops at 250 rooms.
- One engine table widened, flagged: overcoat, raincoat, trenchcoat,
  greatcoat, topcoat and petticoat joined `attire._REGION_CUES` /
  `_SPANNING_CUES` (closed compounds that fell to the torso). And one left as
  it was, flagged: whether belted gear ("a sword at her hip") is worn is
  `attire._NON_ATTIRE_TERMS`' question.

The numbers the review left as their own entries are there with their
evidence: `IDLE_CLOSE_HOURS` (UNBUILT_LIVING_WORLD §1.253),
`NAME_RUN_FLOOR` / `NAME_PREFIX_FLOOR` (UNBUILT_IDENTITY §1.244), a
courier's wait (UNBUILT_LIVING_WORLD §1.258), a region hazard's linger
(UNBUILT_PLANNING §1.260), and a guest's input bounds (§1.269 here).

## 2. Roadmap

<a id="unbuilt-2-5"></a>

### 2.5 Complete automatic canon lock

Age-based locking is built (`persist/commit.py` locks chat-canon entries older than 20
turns; locked entries reject in-place mapping updates). Add the remaining
specified rule so facts **referenced multiple times** lock before the age
threshold. Verified absent: no reference counter on `lore_entries`.

Cheap, and it is what stops long-run lore drift.

<a id="unbuilt-2-10"></a>

### 2.10 Session digest

A short end-of-session synthesis that re-anchors on resume. Small, and it
directly addresses the "coming back after a week" experience.

<a id="unbuilt-2-41"></a>

### 2.41 A decision model of Sonder's own

The owner, 2026-10-06: "The best option would probably be to finetune a small
decision model maybe 4 or 9b parameters specifically for sonder. but for now
using jev is fine." Every decision-model call goes to OpenRouter today, so its
credit bounds how much can be measured, and Jev's own run-to-run noise (a
spread of 0.02-0.05 at the median for one memory, up to 0.32) flips near
ties.

Built: the training data (`docs/guides/DECISION_TRAINING_DATA.md`) -- capture
of every answered request while `decision_capture` is on, and
`tools/decision_data/build.py`, which turns captures into one example a
(state, question) with Jev's averaged answer and, where a source checked it,
the right one. Not built: the model, a serving path for it beside `jev_url`
(the seam already takes any Jev-compatible URL), and gold beyond the router
and the moment checks -- most of what the engine asks (the ponder's grades,
appraisal, the Director's channel questions) has only Jev's answer to learn
from, so a model trained today learns to be Jev there.

## 3. Information-pipeline leaks still open

<a id="unbuilt-3-4"></a>

### 3.4 Multiplayer

All multiplayer-only — but **not** unreached, which is how this preamble used to
read: 135 `narrator_extra` steps across 3 chats (measured 2026-08-19).

- **S3-A6 — `narrator_extra` lacks the consciousness gate and fidelity facts.**
  It ships `spatial_frame` unconditionally and its payload has no
  `player_awareness` key, unlike the primary narrator path.
- **S3-B2 — extra players' speech has neither speaker guard.** `_player_aliases`
  covers the primary persona only.
- **S3-B4 — the interpret-stage split is unchecked for extras.**
  `_reconcile_interpretation` coverage-checks only the primary input.
- **X12 — the onset pass is primary-player-only**, so the reaction-gate and
  `targets` guarantees never run for extras' sequences at onset. *Degradation.*

*(X11 was struck 2026-08-19: it could not be verified against source, and
`perception_act` handles no extras at all — which changes the shape of the claim
rather than confirming it. If it is real it is a face of X12; re-raise it there
with evidence. X9 — the host reads co-players' private thoughts — is not a code
bug but a product boundary, and moved to `AGENTS.md` § Information boundaries
with the other deliberate keeps.)*

<a id="unbuilt-3-5"></a>

### 3.5 Persistence

- **P6 — the knowledge-tag door is the widest lore-to-mind channel.**
  `knowledge_for_character` delivers any `knowledge`-category entry with
  `range='global'` and a matching coarse tag to every tag-holder, with zero
  encounter tracking; category, tag and range are model-proposed at
  `mapping_commit` with only vocabulary validation. **One mis-filed secret is
  instantly in every character's `world_knowledge`.**
- **P7 — CLOSED 2026-09-04.** Introductions are the Director's typed
  `{who, learns}` rows; no model judges them any more (the `mapping_commit`
  model is retired). The application gate is what remains, and it is the
  same one the verdicts had — roster resolution, then a positive presence test on BOTH parties
  (an introduction between two people who were both absent used to pass once
  the roster admitted offscreen characters, trading a missed edge for an
  invented one, which is worse because a wrong edge is indistinguishable from a
  right one afterwards), then a same-room test wherever the engine can place
  both bodies, then `is_recognized_in_frame`. The roster it resolves against is
  now the same one the hearing channel uses, Charter bodies included
  (`commit_common.charter_recognition_projection`), and it reads address forms
  rather than substrings — measured on chat 98, that gate had been dropping 9
  of the 11 `ok` introductions the model authored across forty turns, including
  every one that named a Charter body. What is untouched is the judgement
  itself and the fact that **recognition never decays or retracts**: there is
  no path that un-learns a face. *Plausible.*
- **X24 — the legacy-archive raw-id fallback grafts interior state.**
  `persist/chat_archive.py` resolves an archive integer against whatever local row holds
  that id, then attaches the archive's `chat_chars.state` to it. Memories are
  safe. Legacy path only.
- **P5 / P8** are defects, filed at §1.8 and §1.9.

<a id="unbuilt-3-7"></a>

### 3.7 Test gaps

`tests/test_pipeline_audit_leak_gaps.py` covers D1, D2, B3, B5, X14, F1, F2/P1,
S3-A4, S3-A5, S3-A8, X18 and X4. **A1 still has no dedicated test**, and it is a
confirmed leak class. B4 was listed beside it until 2026-08-19 and is struck: it
names `_ensure_environment`, which has no production caller (§1.45's dead
family), so a test there would pin a dead path.

## 4. Architecture gaps

<a id="unbuilt-4-3"></a>

### 4.3 Gap 5 — canon validation needs provenance tiers

Mapping is privileged and can turn proposals into durable lore. Player
assertions, resolved objective events, imported canon, staged spatial
necessities, character beliefs and narrator wording should not enter the same
"proposed fact" pool. §3.5's P6 and P7 are this gap seen from the other side.

**The tier itself has landed.** `mind/canon_provenance.py` carries the seven
dispositions verbatim — `imported_canon`, `resolved_fact`, `player_claim`,
`spatial_generation`, `character_belief`, `narrator_audit`, `inferred_mapping`
— under `PROVISIONAL`, with `outranks` claiming only that provisional sits
below all seven and deliberately declining to rank them against each other,
because nothing has measured that and inventing an order would be a decision
taken by accident. Wired into `world/gaps.py`, `world/offscreen.py`, `world/subjects.py` and
`world/living_world.py`; `tests/test_canon_provenance.py`.

Two things remain, and they are the ones with teeth:

- **Promotion is implemented and the mapping path is routed through it**
  (2026-09-04). `canon_provenance.promote` validates a provisional record and
  returns it under an adjudicated disposition with its adjudicator named,
  writing nothing; `persist/commit_mapping.room_filings` is the first real
  producer -- every room the Director's committed diff described is promoted
  to `spatial_generation` on the ruling stage's authority before it is filed.
  What remains of this gap: background claims still take their own path
  (`settle_claims` → `write_canon`, keyed by content hash) rather than this
  module's shape. (World facts, which filed through a fallback writer with
  no disposition at all, are retired: as filings 2026-09-03, as a channel
  2026-09-26.) §3.5's P6 (the knowledge-tag door) is untouched.

<a id="unbuilt-4-4"></a>

### 4.4 Gap 6 / Priority 2 — frame/global conflict control

Frame-scoped world keys, memory visibility and character overlays permit genuine
concurrent play. Lorebooks, entities, placements, conditions and scheduled events
remain chat-global, so two frames may prepare against different snapshots and
merge into one shared domain later.

**Recommended direction:** decide domain by domain whether it is frame-local,
immutable across frames, append-only with temporal coordinates, shared but
revision-checked, or merged through an explicit paradox rule. **At minimum,
prepared commits touching shared canon should carry a base revision and reject or
reprepare when the revision changed before commit.**

Verified absent: no revision concept in `core/db.py`, `persist/commit.py` or `core/frames.py`.

<a id="unbuilt-4-5"></a>

### 4.5 Gap 8 — uniform cost against non-uniform uncertainty

The engine self-gates background reactions and caches mapping, but stage
selection is otherwise coarse. A quiet continuation and a multi-party spatially
contested action do not need the same validation budget.

**Recommended direction:** a deterministic risk score from action complexity,
observer count, spatial novelty, authority claims, contradiction count and
state-diff breadth — used to select validation depth, model tier, repair count,
and whether a sanity pass is worth its cost. Any such checker validates
invariants and deltas; it never rewrites prose or decides story outcomes.

Verified absent.

<a id="unbuilt-4-6"></a>

### 4.6 Priority 3 residual — request-size limits

Decompression-bomb limits are in `story/importers.py`. There is no upload or
content-length guard in `web/app.py`. Needed before the service is treated as safe
beyond a trusted local environment.

---

## 5. Deferred backlog

<a id="unbuilt-5-2"></a>

### 5.2 P4 — `established_facts` continuity ledger

**Symptom.** Second-act amnesia: a character contradicts a fact the whole room
established — one character said "I can't translate it" nine turns after the log
was translated in front of them; another's relief flipped to fear across adjacent
turns.

**Fix.** A world-KV `established_facts` ledger. Emit from `director_resolve` as a
new optional list op, like `world_pressure`; persist in `persist/commit.py` with dedup and a
cap, mirroring `commit_world_pressure` (this named the obligations ledger until that
was deleted, 2026-11-01); inject the recent N into every co-present
character payload alongside `world_knowledge`, with a prompt rule: *settled
on-page facts may be disputed, never forgotten or contradicted.*

Note there is no `world_facts` path to build on: it fed neither lore nor
character payloads after 2026-09-03 and was retired on 2026-09-26 (the owner:
rooms, bodies and things carry what is, and the Writers' Room keeps the facts
not yet in play). This ledger would be new.

**Test.** Establish a fact at turn N; assert it appears in a later turn's
character payload and that the prompt carries the no-contradict rule.

Verified absent: zero occurrences of `established_facts` in source.

## 6. Design-note residuals

<a id="unbuilt-6-2"></a>

### 6.2 Extensions — [`EXTENSIONS_DESIGN.md`](design/EXTENSIONS_DESIGN.md)

**What shipped across five batches (9.0–9.6) is not listed here** — it was a
changelog inside a register. Disposition: `Design.md`'s **Third-party
extensions** row; developer surface:
[`docs/guides/EXTENSIONS.md`](guides/EXTENSIONS.md). Two things a reader of this
entry needs and would not find there: the Tier 0–3 ladder (story packs as rung
1) was **abandoned**, not deferred — design note §2 says why, so it is not debt
— and every refusal from the Directive review's hardening list carries its
argument in
[`DESIGN_FRAME_COHERENT_READS.md`](design/DESIGN_FRAME_COHERENT_READS.md)'s
"Refused" section. *(Collapsed 2026-08-19.)*

Still missing:

- **A model lane cannot be declared without Python.** `api.add_model_lane` is
  built, but declaring one happens in `register(api)`, so a data-only extension
  cannot have one — the smaller half of declarative advisor stages below. Nor
  can a lane ship a SUGGESTED model: a manifest choosing a model is an install
  choosing spend.
- **No BINARY/blob storage.** `api.documents` stores JSON only and refuses
  above 128 KiB, because a story document is a `world` row that rides every
  checkpoint. A large asset — image pack, audio, a multi-megabyte export — has
  no home surviving an extension update (`data_path` is replaced by re-clone).
  Deliberately left: the right shape (content-addressed like `memory_vectors`,
  or plain files outside story history) depends on whether the asset needs to
  ride checkpoints at all.
- **Declarative advisor stages** — a stage as data (role, prompt, input-scope
  whitelist, anchor) for authors who write no code. Genuinely useful; no longer a
  prerequisite for anything.
- **Pre/post hooks on `compute_step`**, and the two routing hooks that were
  designed alongside `on_character_payload` but not built: `on_admission` and
  `on_view`, which would let an extension alter what perception ADMITS rather
  than only what the assembled payload carries.
- **An extension still cannot add to the Director's sheet or the encoder's
  card**, though the narrator seam is built and `api.director_context` puts a
  standing block in front of the Director. Registering a specialist family of
  one's own was removed with the fan-out on 2026-09-27; an extension records
  its judgement of a beat from its own commit domain or stage, and the narrator
  seam delivers the reader-visible result. Closing the rest would mean a chunk
  registry for the encoder's card -- deliberately left.
- **`tools/project_check.py --extension <path>`** — the author-facing
  self-check. The checks exist and the AUDIT half has a Python entry point
  (`extension_runtime.audit_extension_source`); the lints have no way in from
  outside.
- **Phase 2: the reviewed registry.** Every field it needs (id, version,
  `sha256`, `provenance`, and now `source_url`/`source_ref`/`commit`) is
  already written at install time, so this is an addition rather than a
  migration.
- **A zip or folder install cannot be checked for updates.** Only a repository
  source has something to ask; an `ETag`/`Last-Modified` probe is cheap and not
  universally honoured, so it was left out rather than shipped as a check that
  is right most of the time. Reported as `checkable: false` with the reason.
- **Update checks are manual.** There is no periodic sweep and no notification
  badge; the host presses a button. A background check is a network call per
  installed extension on a schedule nobody asked for, and wants a rate limit
  and a stored last-checked time before it is worth having.
- **Scoped clients**, which is what would make third-party frontends real for
  non-host players: scoped stream and chat reads, `client`-scope tokens. A
  firewall decision, and it deserves its own design note before code.
- **Documents are not frame-scoped.** `api.state` has a per-era counterpart
  (`api.frame_state` → `extf:<id>`) and `api.documents` does not: a document
  row is `ext:<id>:doc:<path>`, which is chat-global like the namespace it sits
  in. A campaign holding per-era documents would need an `extf:` document
  store, and nothing has wanted one yet.
- **`extension_runtime/` is outside the UI catalog's reach.**
  `tools/extract_ui_catalog.py` scans root `*.py` and `agents/*.py`, so the
  dozen-odd registration errors surfacing in the Extensions menu are never
  harvested and never translated — while the four living in `agents/director.py`
  are, which would make one list four-sixteenths Japanese. Fix: add the package
  to the scanner and translate the set.
- **`Sonder._unload` cannot undo side effects**, only registrations and the two
  injected elements. A monkeypatched global, a timer or a `document`-level
  listener survives a disable. Inherent to the no-sandbox posture; stated in the
  guide so an author can compensate.
- **Two "absent means absent" edges in `player_view["people"]`.** A fact can
  only carry `authored_public` provenance today — nothing mines memories to
  affirm a `what_i_was_told` role, so experience-sourced facts stay absent
  rather than deduced — and a ledger name that resolves to no cast member or
  persona is omitted, because an unregistered presence has no stable id until
  promotion makes one.
- **The archive does not DECLARE its extension schema.** Export/import
  round-trips `ext:<id>`/`extf:<id>` state, char state and documents without a
  version or an enumeration, so an importer cannot tell a complete carriage from
  a partial one. Raised by the Directive hardening list; left until a second
  home exists, because a version number with one member is one nobody reads.
- **No read-snapshot token.** The same review asks for a read transaction so a
  DTO combining several domains cannot straddle a concurrent write. Not built,
  and deliberately not folded into the frame-coherence work, because it is a
  different axis: `at_frame` chooses an ERA, a snapshot would fix a MOMENT.
  `tests/test_extensions.py::test_no_capability_is_declared_for_work_that_is_not_built`
  names it as today's example of a capability that must not be declared.
- ~~The host's own `story_view`/`player_view` HTTP routes take no `frame`
  parameter.~~ **Built 2026-08-19.** Both routes take `frame`, omitted rather
  than defaulted when the caller does not ask — the underlying default is a
  sentinel meaning "the latest committed turn across every frame", and `None`
  is a different question that would be validated as a frame id. The entry
  said to wait for a consumer; the reason to build it anyway is that an
  asymmetry between two doors onto one room is its own defect: one surface
  could compose a frame-coherent read and its HTTP twin could not say which
  era it wanted.
