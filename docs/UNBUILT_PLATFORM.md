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

- **PERSISTENCE-F17 — three world keys are not frame-scoped while seventeen
  siblings are.** `world_pressures` (`persist/commit_ledgers.py:150,227,299`),
  `background_claims` (`world/background_claims.py`, six sites) and
  `engine_notices` (re-verified 2026-08-19: `agents/director.py` reads it at two
  sites, and the WRITERS are `persist/commit_mechanics.py`,
  `persist/commit_destruction.py` and `persist/commit_scene_state.py` — the
  last was missing from this row)
  are plain `wget`/`wset`. So a pressure raised in one era, a claim ratified in
  one era and a notice raised in one era are all visible from every other era,
  and a rewind does not retract them. Adding a key to
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

- `agents/runtime.establishment_plan` is a fixed five-step list
  (`mapping_stage`, `director_establish`, `perception_establish`, `narrator`,
  `commit`) and never appends `narrator_extra`, which `build_plan` does append
  on every normal turn when the chat has extra players in this frame.
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
  module's shape, and world facts file through the fallback writer with no
  disposition at all. §3.5's P6 (the knowledge-tag door) is untouched.

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
new optional list op, like `obligations`; persist in `persist/commit.py` with dedup and a
cap, mirroring `commit_obligations`; inject the recent N into every co-present
character payload alongside `world_knowledge`, with a prompt rule: *settled
on-page facts may be disputed, never forgotten or contradicted.*

Note the `world_facts` path feeds neither lore nor character payloads since
2026-09-03: a Director world fact is a `setting_fact` planning need for the
Writers' Room (`persist/commit_mapping._setting_fact_needs`). This ledger
would still be separate.

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
- **An extension still cannot reach the Director's PROSE AUTHOR**, though the
  narrator seam is built. A registered specialist family writes its channel to
  the merged `state_diff` and nothing narrates it *from there*; closing it means
  a prose-chunk registry with
  `test_every_delegated_block_has_exactly_one_owner` extended across the
  boundary. Deliberately left — the narrator seam already delivers the
  reader-visible result without touching a one-owner invariant.
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
