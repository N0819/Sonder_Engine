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

### `narrator`

Renders the opening player-facing prose from the perception result.

### `commit`

Persists validated scene, entity, cast, lore, event, relationship, and memory changes through `commit_all`.

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
[parallel character:<id> steps when reactors exist and autonomy == 0]
    ↓
director_resolve
    ↓
background_react
    ↓
perception_outcome
    ↓
narrator
    ↓
commit
```

### `director_interpret`

Parses the player declaration into structured speech/action sequence, authority claims, likely reactors, mapping need, and resolution flags. It also determines the later plan shape.

This stage should preserve player wording and distinguish attempted actions from asserted facts.

### `mapping_stage` versus `mapping_quick`

- `mapping_stage` performs fuller lore routing and candidate staging when the interpretation says new mapping is needed.
- `mapping_quick` combines fast retrieval with the last confirmed lore cache when existing context is sufficient.

Neither stage should directly decide what a character perceives. Full mapping may overlap with `perception_act` when it is only routing existing-world lore. When the turn enters or explicitly queries a new location, mapping runs first so the first perception pass can consume freshly staged room notes.

### `perception_act`

Produces observer-specific views of the action onset: speech delivery, visible movement, immediate sensory evidence, and deterministic spatial additions. This occurs before objective resolution so characters do not react using future knowledge.

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

### `character:<id>`

A single character decision using that character’s scrubbed view and structured
observations, memory context, private character data, relationships, learned
beliefs/associations, and its own interoception/body state. It appraises
goal impact, novelty, control, coping, norm/self compatibility, stress, and
current-event pain/pleasure, then proposes several response candidates before
declaring one behavior. Pain and pleasure are independent and do not require
survival mode. Multiple independent character steps may run in parallel.

The authored card is resolved per story: `chat_chars.sheet` wins when present,
otherwise the reusable library `characters.sheet` is used. This override never
replaces `chat_chars.state`; editing a card during an idle story changes future
character context without resetting earned mood, stress, beliefs, memories, or
relationships.

### `director_resolve`

Combines the player declaration, character declarations, reaction declarations, objective state, mechanics, and deterministic checks into one resolved event and state diff.

The Director owns objective causality but does not own character private psychology or narration.

### `background_react`

Unconditionally present in the plan but internally self-gating: `commit.py`'s `pick_background_reactor` is a deterministic, LLM-free check that returns `None` for the large majority of turns (no salient, un-voiced named background presence this beat), in which case this stage costs nothing. Only when it picks a name does one small, stateless LLM call decide whether that person reacts and, if so, a single line and/or brief action for this beat only — no persistent memory, psychology, or mind-models (that is what character promotion is for). This is a deterministic backstop for the director_resolve prompt's own background-entity voicing license (see `prompts.py`), which live play showed goes unused often enough under sustained narrative pressure to need one, the same lesson already learned for spatial zone-tagging and speech concealment.

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

### `narrator`

Renders the player-facing prose. Fidelity checks and player-echo stripping are applied before the output is saved.

### `commit`

`commit_all` first prepares the exact post-turn scene plus all lore and memory embeddings without holding SQLite's write lock. It then invokes every durable domain inside one outer transaction under a per-turn idempotency lock:

1. scene and simulation clock
2. world entities and conditions (a derived projection built from the same prepared post-dedup diff as the scene) — entity state blobs referencing concealed actors are skipped (S3-A8)
3. cast status/state
4. paradox checks
5. spatial-frame reconciliation
6. mapping/canon updates
7. character active psychology, beliefs/associations, memories, relationships,
   and event row — dialogue memories store appearance labels for unrecognized
   speakers (F2/P1); a character deciding turn N never retrieves memories from
   turn N or later, via the `current_turn_idx` hard cutoff in
   `search_memories` (F1)
8. background-presence tracking — co-located character names pass through the
   the presence's own recognition ledger (F3)
9. pending-state clear

A failure in any domain aborts immediately and rolls back all earlier writes from that turn. Character autobiographical consolidation runs after the primary transaction because it is a reconstructible derived cache and may require an LLM call; consolidation failure produces a warning without corrupting committed facts.

## Streaming

`agents.runtime._run_pipeline` executes stages and emits newline-delimited events through the FastAPI streaming layer.

- `step_start`: a stage began.
- `token`: provider token delta for the current step.
- provider generation events: retries or notices tied to the step key.
- `step`: completed structured result plus step/variant IDs.
- `done`: the planned pipeline fully materialized.
- `aborted`: cancellation was observed.

Consecutive `character:<id>` stages can run in parallel. Primary and extra-player narration may also overlap. Full mapping and action-onset perception overlap only when no newly staged location description is required; otherwise plan order is preserved.

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
