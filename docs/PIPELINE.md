# Turn Pipeline

This document describes the implemented orchestration in the `agents/` package, primarily `agents/runtime.py`. It is intentionally narrower than `Design.md`: it explains what executes, what each stage owns, and where results are stored.

## Runtime containers

A turn runs through a `PipelineContext` containing typed chat and turn records, active cast rows, player input, named step outputs, per-character results, reaction results, and warnings.

Every completed stage is also saved to:

- `steps`: one row per `(turn_id, key)` with order and stale state.
- `variants`: immutable JSON outputs for a step, with one active variant.

This dual representation allows live execution through `PipelineContext` and later inspection/reroll through stored variants.

## Opening turn (`turn.idx == 0`)

```text
mapping_stage
    ↓
director_establish
    ↓
perception_establish
    ↓
narrator
    ↓
commit
```

### `mapping_stage`

Routes attached lorebooks, retrieves relevant canon, and stages information needed to establish the scene.

### `director_establish`

Creates the initial objective scene and actor state. This is privileged objective setup, not player-facing prose.

Character and persona cards expose only their public `initial_outfit`
projection to establishment. A non-empty outfit is authoritative and is copied
into objective attire after model output; private history and psychology are
not added to this information path. Stable body appearance never supplies
clothing. `scene.seed_initial_attire` also seeds this state deterministically
when a scene first materializes or a participant first joins an existing scene,
but never replaces an existing `scene.attire` entry.

### `perception_establish`

Builds the player’s opening view from the established scene and spatial/perceptual constraints.
Attire/body detail reaches a model only through the observer-scoped
`scene.body_regions` projection. It previews commit's canonical attire change
on a copy, applies derived region visibility, and exposes only the outer surface
or legitimately bare body detail. For partial torso coverage, `chest` and
`midriff` are rendered separately; a description authored for one zone is never
used as fallback for the other, and the coarse whole-torso `beneath` string is
withheld while only one zone is exposed. Other bare regions remain independent:
for example, a bare `groin` sends its authored anatomy through the same
observer-safe projection even while a tank top still covers the chest.

The projection is an information boundary, not a guarantee that a generative
perception model will retain every allowed detail. After the model returns,
perception applies a deterministic body-detail fidelity floor: if the view
itself foregrounds an exposed surface (for example, a bare stomach or parted
legs), the corresponding authored detail is restored from that observer's
already-filtered `body_regions`. It never inventories unrelated anatomy, and a
covered zone cannot enter because it has no bare-surface detail in the
projection. This is semantic fidelity, not quotation fidelity: the model may
rephrase or integrate the description for natural flow, and the floor stays
silent when the resulting view retains concrete distinguishing traits. It acts
only when the view collapses them to a generic exposed body part. Positional
words such as `inner`, `outer`, and `thighs` do not count as distinguishing
traits merely because they also occur somewhere in an authored description.

### `narrator`

Renders the opening player-facing prose from the perception result.

### `commit`

Persists validated scene, entity, cast, lore, event, relationship, and memory changes through `commit_all`.

After the deterministic transit sweep, the `world_events` domain promotes only
scheduled rows mechanics actually fired into the objective, frame-scoped event
spine. The queue remains future state; the spine is happened state. Promotion
is stable/idempotent and shares the outer transaction, so a later domain failure
rolls both the fired status and its objective record back. Checkpoints restore
the table with the rest of the pre-turn world.

Off-screen life has two named commit domains after mapping and before memory.
`offscreen_plans` first accepts/cancels only Director encodings grounded in a
present character's declaration from this beat. `offscreen_epoch` then derives one
stable frame-scoped opportunity from the committed beat: opening, top-level
location change, crossed simulation-hour bucket, due mechanical event, or
crossed deadline of the active stage in a stored plan. A reactive stage may
fire only its already-adjudicated effect and performs no provider call. The
epoch domain is independent of mapping's no-work skip. Its
seeded draw and epoch/log writes remain inside the turn transaction. Only the
model-priced profile producer starts at the post-commit tail, carrying the base
turn, frame, and epoch id; landing refuses a world restored to another epoch.

After the ordinary `memories` domain settles each acting character's prepared
state, `information_carriers` acquires public event surfaces for registered
characters physically at the event location and advances the bounded route on
reports whose holder moved. It must remain after `memories`: writing earlier
would let the precomputed state update erase the envelope. The report is stored
only in that holder's frame-specific character state and projected only into
their private character payload; co-location never copies it to another mind.

## Normal turn

The plan is built dynamically from `director_interpret.flow`.

```text
director_interpret
    ↓
mapping_stage OR mapping_quick
    ↓
perception_act
    ↓
[reaction_loop when contested physical reactions are required]
    ↓
[interaction_loop when reactors exist and autonomy > 0]
    OR
[parallel character:<id> steps when reactors exist, autonomy == 0,
 and the beat was NOT contested]
    ↓
director_resolve
    ↓
background_react
    ↓
perception_outcome
    ↓
narrator
    ↓
[narrator_extra when the chat has other human players]
    ↓
commit
```

Two conditions the diagram cannot show:

- **The reactor set is consciousness-gated first.** A reactor whose awareness is
  in `scene.NON_AWAKE_GATED` is dropped before any character step is planned, so
  a gated mind runs no step at all.
- **Contested beats plan no parallel character steps.** When a `reaction_loop`
  ran, it already collected each reactor's declaration; planning `character:<id>`
  steps as well would run those minds twice in one beat. `agents/runtime.py`
  records this as a deliberate fix, not an omission.

### `director_interpret`

Parses the player declaration into structured speech/action sequence, authority claims, likely reactors, mapping need, and resolution flags. It also determines the later plan shape.

This stage should preserve player wording and distinguish attempted actions from asserted facts.

**`flow.reactors` is load-bearing well beyond reaction eligibility, and that is
easy to miss.** It decides who gets a character step, and it is *also*
`perception_act`'s entire perceiver list — pass 1 iterates the cast and skips
anyone not in it, with no spatial or sensory reasoning of its own. So a present,
awake, watching character omitted here perceives the act never; their whole
account of the beat is `perception_outcome`, and they take no part in it.

Measured across the stored corpus before alpha 6.9, **435 of 551 beats (79%)
where two or more characters received an outcome view had at least one of those
witnesses missing from `reactors`** — usually just the ones the beat was not
addressed to. The prompt clause has been sharpened accordingly (reactors is
permission to respond, not a requirement, and explicitly not "who was
addressed"). The underlying conflation — one field answering both "who
perceived this" and "who may act on it" — is not fixed: `docs/UNBUILT.md`.

### `mapping_stage` versus `mapping_quick`

- `mapping_stage` performs fuller lore routing and candidate staging when the interpretation says new mapping is needed.
- `mapping_quick` combines fast retrieval with the last confirmed lore cache when existing context is sufficient.

Neither stage should directly decide what a character perceives. Full mapping may overlap with `perception_act` when it is only routing existing-world lore. When the turn enters or explicitly queries a new location, mapping runs first so the first perception pass can consume freshly staged room notes.

### `perception_act`

Produces observer-specific views of the action onset: speech delivery, visible movement, immediate sensory evidence, and deterministic spatial additions. This occurs before objective resolution so characters do not react using future knowledge.

A direct contact the player declares as already present through their own
conduct or first-person body sense is structured by interpret as
`contact_assertions`. Pass 1 previews those assertions on a copy of the scene
before any reactor decides, so both participants receive the same relation from
their own bodily endpoint. The guard admits a new relation only when the player
is its actor; an NPC-to-player assertion must refine a matching contact that
already stands, preventing first-person wording from authoring a new NPC act.
Contact points remain open anatomical strings and do not collapse onto attire's
visibility regions: `cervix` remains `cervix`, rather than becoming `groin`.
For interior topology, `target_interior` separately records the passage,
chamber, material, or other structure enclosing the acting part. `target_part`
is only the exact boundary or endpoint currently touched; an endpoint is never
assumed to be the container. Both are open, genre-agnostic strings inferred by
the model from established fiction.
The contact's geometry is likewise not folded into its prose verb:
`relation: surface|interior` records topology and `motion: settled|moving`
records kinematics. These axes are independent, so an interior contact may be
moving. Saves predating the fields derive both from `manner` and `detail`.
Resolve receives the previewed relation and commit receives it through
`contact_ops`; a later change must explicitly end it before moving the same part
to a different endpoint, so a coarse re-description cannot overwrite it. An
interior relation also requires an explicit end before the same endpoints can
become surface contact; changing `manner` alone cannot erase topology. An
explicit push past a standing endpoint instead uses `op: cross`, naming the
exact `crossed_target_part`, downstream `target_interior`, and optional new
`target_part`. The operation is rejected unless it matches exactly one standing
interior endpoint. The crossed boundary is transition evidence; only the
downstream interior and current endpoint persist as state.

A character can also end a contact without trusting the resolve model to infer
that state transition from prose. Its private payload lists every onset contact
involving its body under `self.standing_contacts` using opaque `contact:N`
handles. A completed, self-owned release or withdrawal returns exact
`contact_ops:[{op:"remove",contact_ref}]`; contested attempts return no op.
Resolve maps each ref back to the exact ledger direction and parts, projects
those removals before its own contact diff, and rejects a stale re-add of the
same contact. Other simultaneous contacts survive unless separately named.

Non-discrete matter uses a sibling relation rather than abusing contact or
inventory. `state_diff.substance_ops` records an established material's source,
destination, placement (`surface|interior|contained|room`), amount, and optional
interior/endpoint. If `source_part` is the actor part of exactly one standing
interior contact, resolve may omit the destination: merge derives the target and
enclosing structure from that onset topology before applying same-turn contact
removals. A contradictory explicit destination is refused. The resulting
`scene.substances` entry persists until a bounded remove/clear operation; code
tracks the material the fiction names but never infers one from an event label.

The model supplies ambient observer-specific sensory prose, but it does not own
the chronology of an already structured player declaration. Model-rendered
copies of declared speech/action are removed; ambient clauses sharing a
sentence with an action are retained; then authorized speech and visible action
are projected last in the Director sequence's exact order. Each element still
passes its own hearing/sight/concealment gate. Exact quote bodies and declared
tones survive, and observer-facing action uses only the intent-free
`observable` surface. Thus `speech -> turn -> speech` cannot become
`turn -> speech -> speech`, even when the perception model paraphrases it that
way. Delivery metacommentary (“the words reach you clearly”, “you hear both
lines in full”) is discarded because it describes the filter rather than the
fiction.

Interpret reconciliation counts `tone` and `observable` as declaration-bearing
channels. A gesture/delivery already represented there is not appended later
as a redundant repair action, which otherwise creates a second competing
chronology before perception begins.

It also emits structured observations for appraisal. These are reconstructed
from each final scrubbed prose view after output validation; model-authored
observation objects are discarded. They therefore carry the same information
budget as the view and cannot reintroduce raw event intent, private tell grounds,
unknown identities, or another body's internal state.

The projection decomposes a view into per-channel atoms (consecutive sentences
sharing a sensory channel, capped per view), and grades intensity, suddenness
and ambiguity by cue density rather than tripping them on a single hit. An
atom's own body state counts as directed at the perceiver. This metadata is
advisory context for the character's appraisal — no deterministic code consumes
the numbers — so its failure mode is a character told to doubt what it plainly
perceived, not a leak.

### `reaction_loop`

Used for contested, time-sensitive physical reactions. Reactions are declarations under limited information, not guaranteed outcomes.

### `interaction_loop`

Runs bounded observable conversational or physical micro-beats when autonomous interaction is enabled. Later participants can receive legitimate consequences of earlier visible or audible beats; they do not receive hidden agent state.

**What ends a beat.** `_requires_director_resolution` is the commonest early
exit and it ends the BEAT, not the round, so its bar is "nobody can sensibly
respond until the world says what happened" — `commitment: "contestable"`, a
concealed act, or a conflict/movement verb. Deliberately NOT "the act has a
target": in conversation every nod and glance is aimed at somebody, and gating
on targets meant 70% of all character actions ended the beat, making an
unprompted exchange between two characters impossible (`docs/UNBUILT.md`
§1.11f). With that narrowed, `max_micro_rounds` is what actually bounds an
exchange.

**The first wave is simultaneous.** Everyone in the initial reactor queue is
answering the same thing — the player's declaration, already fixed before this
stage runs — and none of them has seen any other reactor's response, because
none exists yet. So the first `initial_parallel_reactors` speakers declare
blind: micro-perception for the whole wave is delivered only once every member
has declared, and the loop's early exits are evaluated for the wave as a whole.
After the wave, one speaker at a time, unchanged — a character replying to
another character genuinely is responding to something they just heard, and
ordering is the whole content of that.

The person being ANSWERED is not in the wave. Its justification only holds
when the members are reacting to the same external thing; when one is answering
another, the asker is the addressee and steps out to the next round so they
hear the answer before speaking (`docs/UNBUILT.md` §1.11h).

Parallel in the FICTION, not in execution. The wave runs sequentially, because
`character_step` writes through `ctx`; what is guaranteed is that no member
sees another's output while deciding.

This exists because the early exits end the **beat**, not the round, and the
commonest of them fires on any declared act with a target — a hug returned, a
hand on a shoulder. With the addressed character queued first, that stranded
everyone else: 153 of 196 beats with two or more reactors left at least one
never called at all. A character who never ran has no appraisal, so no drive
strain from a beat aimed at them, and no memory of having chosen to stay quiet.
See `docs/UNBUILT.md` §1.11b.

### `character:<id>`

A single character decision using that character’s scrubbed view and structured
observations, memory context, private character data, relationships, learned
beliefs/associations, and its own interoception/body state. It appraises
goal impact, novelty, control, coping, norm/self compatibility, stress, and
current-event pain/pleasure, then proposes several response candidates before
declaring one behavior. Present and remembered evidence occupy separate
grounded lanes; a memory may produce a capped, labelled body/threat echo but
cannot become current somatic fact. An exceptional private
`{type: "ponder", query, why}` item is removed from the public declaration,
stored for that mind, and adds a labelled four-item deliberate-recall lane on
its next character turn without replacing normal recall. Pain and pleasure are
independent and do not require survival mode. Multiple independent character
steps may run in parallel.

Recent memory reaches this step in epistemically separate lanes. The
chronological `recent_episodes` stream contains first-hand experience only,
with at most one episode formed per beat; durable received lines travel in
`recent_received_information`, and fallible conclusions in
`recent_conclusions`. The latter two annotate a beat without becoming extra
events in the character's remembered chronology.

Dialogue continuity is tracked at two levels. `recent_self_lines` retains a
short verbatim window for exact reissues and repeated sentence shapes;
`recent_self_moves` projects one selected conversational job per turn from the
immutable prior character variants, so a chatty speaker cannot hide a repeated
offer or question behind four fresh lines or a substituted proper noun. The
ledger compares completed turns, not individual speech entries: emphasis,
lists, callbacks, and one continuous in-character rant remain legitimate. A
lexically similar move opens a contextual review rather than proving a defect;
the review may retain a continuation that the current beat invited, answered,
challenged, or materially advanced. Its target is an unmotivated reset that
reissues the old conversational job as though nobody heard it. Verbatim,
potential semantic-move, and spent-intention findings are combined into at most
one review call. Only an exact line that survives that review feeds the stuck
mind signal; a semantic move deliberately retained after review does not.

Intentions remain visible after they stop steering for autobiographical
continuity, but only
`steering_intention_ids` may authorize new wants or selected responses; commit
applies the same boundary when normalizing the settled active state.

The authored card is resolved per story: `chat_chars.sheet` wins when present,
otherwise the reusable library `characters.sheet` is used. This override never
replaces `chat_chars.state`; editing a card during an idle story changes future
character context without resetting earned mood, stress, beliefs, memories, or
relationships.

### `director_resolve`

Combines the player declaration, character declarations, reaction declarations, objective state, mechanics, and deterministic checks into one resolved event and state diff.

The Director owns objective causality but does not own character private psychology or narration.

Every persistent physical change asserted by the resolved event is repeated in
`changes_asserted` and checked against its own structured diff category before
commit. Contact entries carry the same actor, actor part, target, and target part
as their `contact_ops` relation. Matching only a participant is insufficient:
one hand-on-hip operation cannot prove a separately asserted interior contact
was encoded. Legacy endpoint-free contact manifests use an op-specific
part/manner match and fail toward one idempotent repair when underspecified.
The additive repair merge retains `contact_ops`; detection without that merge
would report the divergence while still committing the stale relation.
Substance entries likewise carry their material, target, placement, and
enclosing interior. Reconciliation treats a completed deposit/removal as its
own evidence category and retains `substance_ops` through additive repair.
Body arrangement is the third spatial grain: positions choose the room,
stations choose the anchor/nearness, and `poses` records posture, support,
relative arrangement, and physical constraint. A touched pose is a complete
snapshot rather than a partial merge, so obsolete `beneath`/`pinned` fields do
not survive a later rise. Pose changes have their own manifest/audit category.

### `background_react`

Unconditionally present in the plan but internally self-gating, with two paths chosen by the per-chat `background_config` (`scene.py`) key `scene_life`:

- **`off` (default) — one presence.** `commit.py`'s `pick_background_reactor` is a deterministic, LLM-free check that returns `None` for the large majority of turns (no salient, un-voiced named background presence this beat), in which case this stage costs nothing. Only when it picks a name does one small, stateless LLM call decide whether that person reacts and, if so, a single line and/or brief action for this beat only. `max_reactors` defaults to 1 and is raisable to 3, so "one presence" is the default rather than an invariant.
- **`ambient` / `full` — the scene manager.** One batched call voices every managed presence in the room at once (roster from `managed_presences`, capped by `max_managed`), partitioned by `spatial.ambient_scope` and filtered per presence by a `hear_level` audience map. The plan label changes to "Scene life · manager (ambient|full)" accordingly. Voicing is batched; **writing is not** — each attributed entry is routed to its own record at commit, which is what keeps one call from becoming one shared mind. Design and its still-unbuilt half: [`BACKGROUND_LIFE_DESIGN.md`](BACKGROUND_LIFE_DESIGN.md), [`UNBUILT.md`](UNBUILT.md) §6.1.

Neither path grants persistent memory, psychology, or mind-models — that is what character promotion is for. This is a deterministic backstop for the director_resolve prompt's own background-entity voicing license (see `prompts.py`), which live play showed goes unused often enough under sustained narrative pressure to need one, the same lesson already learned for spatial zone-tagging and speech concealment.

Its output is merged into `perception_outcome`'s dialogue processing rather than mutating `director_resolve`'s already-persisted step/variant, so a rerun/resume from this point onward stays consistent with what was actually rendered.

### `perception_outcome`

Filters the resolved event into separate observer experiences. This output feeds both player narration and character-specific memories.

Concealed actions are sentence-level redacted from the resolved event text
per-perceiver via `_redact_concealed_from_event` — sentences referencing a
concealed actor (identified by structured name, not prose matching) are
withheld; overt sentences survive. The unified delivery gate `_delivery_ok`
in `agents/common.py` consolidates containment, awareness, sight (including
rear-arc/`behind_sources`), and hearing (with proximity) checks for every
deterministic delivery site.

Observer scene projections include only visible bodies' pose snapshots plus the
observer's own. These are authoritative: visibility alone never licenses a
default standing or “before you” relation. Full authored appearance is scoped
to discovery or a structural visible change; familiar stable card description
is withheld while dynamic clothing and exposed body regions remain available.
This matters at the memory boundary because witnessed episodic memory is formed
from this output, not repaired after it.

### `narrator`

Renders the player-facing prose. Fidelity checks and player-echo stripping are applied before the output is saved.

### `narrator_extra`

Planned only when the chat has other human players: each needs its own perceiver
and its own render of what *they* saw. Registered like any other stage, and
together with `narrator` it forms the `_PRESENTATIONAL_TAIL` — rerolling either
re-runs the remaining tail rather than the whole turn.

It does **not** yet carry the primary narrator's consciousness gate or its full
fidelity payload ([`UNBUILT.md`](UNBUILT.md) §3.4, S3-A6).

### `commit`

`commit_all` first prepares the exact post-turn scene plus all lore and memory embeddings without holding SQLite's write lock. It then invokes every durable domain inside one outer transaction under a per-turn idempotency lock:

1. transit sweep — first, because it mutates the prepared scene (timed
   arrivals, engine notices) that the scene domain then persists
2. scene and simulation clock
3. world entities and conditions (a derived projection built from the same
   prepared post-dedup diff as the scene) — an entity state blob referencing a
   concealed actor raises a `"possible stale clause (S3-A8)"` warning and is
   still committed; an earlier skip-the-update fix was reverted as durable
   corruption, so this is a signal, not a guard
4. cast status/state
5. paradox checks
6. spatial-frame reconciliation
7. mapping/canon updates
8. character active psychology, beliefs/associations, memories, relationships,
   and event row — dialogue memories store appearance labels for unrecognized
   speakers (F2/P1); a character deciding turn N never retrieves memories from
   turn N or later, via the `current_turn_idx` hard cutoff in
   `search_memories` (F1); pending private ponder queries are consumed here and
   any newly chosen query is staged for that character's next turn
9. background-presence tracking — co-located character names pass through the
   presence's own recognition ledger (F3)
10. narration person
11. obligations
12. world pressure
13. authored events
14. pending-state clear

Domains 5 and 6 run deliberately after the scene/entity/cast writes so they
inspect this turn's projected world, while staying inside the same rollback
boundary.

A failure in any domain aborts immediately and rolls back all earlier writes from that turn. Two things run *after* the primary transaction, both because they may call an LLM and neither can corrupt a committed fact: character autobiographical consolidation (a reconstructible derived cache) and autonomous background-to-cast promotion (additive and forward-only — the new character becomes step-eligible next turn). A failure in either is a warning.

## Streaming

`agents.runtime._run_pipeline` executes stages and emits newline-delimited events through the FastAPI streaming layer.

- `step_start`: a stage began.
- `token`: provider token delta for the current step.
- provider generation events: retries or notices tied to the step key.
- `step`: completed structured result plus step/variant IDs.
- `done`: the planned pipeline fully materialized.
- `aborted`: cancellation was observed.

Consecutive `character:<id>` stages can run in parallel. Primary and extra-player narration may also overlap. Full mapping and action-onset perception overlap only when no newly staged location description is required; otherwise plan order is preserved.

All three pairings go through `_run_parallel_group`, which is also where
concurrency is made visible — twice, because it is asked twice. Each
`step_start` in a group carries `group` (the keys starting together) for the
live log; each saved step carries `_engine_notes.parallel_with` for the
persisted pipeline view, which reads the `steps` table long after the events
are gone and has nothing but `ord` to go on. Note how narrow the conditions
are: parallel `character:<id>` steps require `autonomy == 0` on an uncontested
beat, `narrator_extra` requires extra players, and the mapping overlap requires
`flow.needs_mapping` on a spatially familiar turn — so a typical story runs
strictly sequentially and correctly shows no groups at all.

`_engine_notes` is a reserved key on a step's saved content (`agents/storage.py`),
carrying what the deterministic layer did to that step's output: the warnings
raised while it ran, tagged by `pipeline_context.current_step_key`, and which
steps it ran beside. It is stripped by `active_content`, so a rerun rehydrating
a prior step into `ctx` never carries it into a prompt.

## Resume and rerun

`resume_key_for_turn` compares the expected plan with stored steps. The first missing, stale, or incorrectly activated step becomes the resume point.

When rerunning from a stage:

- Earlier active variants are loaded back into `PipelineContext`.
- Later dependent stages are recomputed.
- Each recomputation creates a new immutable variant and marks it active.
- `_assert_plan_materialized` verifies that every planned stage has a valid result before the turn is considered complete.

## Portable diagnostic traces

Completed stage outputs already live in immutable `steps` / `variants` rows.
`pipeline_trace.py` can export that record as a versioned, canonical JSON
artifact and replay the saved `step_start` / `step` / `done` event sequence
offline. Replay never imports the runtime dispatcher and never calls a model;
it reproduces persisted outputs, not the original computations.

The default export is deliberately hash-only. It includes structure, active
variant selection, stale state, variant counts, and SHA-256 integrity hashes,
but omits player input and stage payloads. A replayable export is an explicit
privacy decision because those payloads may contain story text, retrieved lore,
and private character reasoning:

```bash
# Lower-exposure structural diagnostic (not replayable)
python tools/pipeline_trace.py export 42 -o turn-42.trace.json

# Local replay artifact, including inactive reroll history
python tools/pipeline_trace.py export 42 --include-content --all-variants \
  -o turn-42.full.trace.json

python tools/pipeline_trace.py inspect turn-42.full.trace.json
python tools/pipeline_trace.py replay turn-42.full.trace.json
```

Exports do not mutate application rows and atomically replace their destination
file. Repeated exports of unchanged rows are byte-identical. The artifact
intentionally excludes provider keys, prompts, character sheets, the chat
scenario, and unrelated world rows. It is a bounded post-mortem tool: because
failed stages have no completed variant, it can replay everything persisted
before a failure but cannot reconstruct a provider exception or unsaved partial
model stream.

## Where to debug

| Symptom | Earliest likely stage |
|---|---|
| Player speech omitted or misattributed | `director_interpret`, then `perception_act` |
| NPC knows hidden lore | mapping-to-character context, `perception_act`, or `character_step` |
| NPC reacts to an outcome before it happens | `perception_act` / reaction planning |
| Action result is implausible | `director_resolve` or deterministic spatial/state support |
| Correct result is narrated incorrectly | `perception_outcome`, then `narrator` |
| Correct turn disappears after reload | `commit.py`, checkpoints, or database restore |
| Reroll leaves mixed old/new state | stale-step propagation, active variants, or resume logic |
| Character knows a concealed action from a prior turn | `recent_events_for_observer` in `scene.py` (Pattern 4), `_redact_concealed_from_event` in `agents/perception.py` |
| Character remembers something from a rerolled turn | `current_turn_idx` cutoff in `memory.py` `search_memories` (F1) |
| Character keeps recalling a belief they have since revised | `reconcile_inference_confidence` in `memory.py`, `belief_credence` in `theory_of_mind.py` |
| Character theorises lucidly about others while in agony or ecstasy | `cognitive_absorption` in `psychology_runtime.py`, `absorbed_cap`/`formation_floor`/`sheet_capacity` in `theory_of_mind.py` |
| Character treats its own guesses as established fact | `active_hypotheses` (`i_suspect` keys) in `agents/character.py`, ACTIVE HYPOTHESES block in `prompts.py` |
| Background dialogue names an unrecognized character | `_present_others` recognition gate in `agents/background.py` (F3) |
| Narrator reports a door state in an unseen room | `_visible_portal_states` visibility gating in `agents/narration.py` (S3-A5) |
