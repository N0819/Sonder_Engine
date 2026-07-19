# Fiction Engine Architecture Audit

**Date:** July 19, 2026  
**Scope:** Turn orchestration, epistemic boundaries, persistence, concurrency, memory, spatial state, canon authority, API startup, documentation, and tests.

## Executive assessment

The project is not merely a prompt wrapper. It is a real simulation-oriented fiction runtime with explicit information routing, durable private memory, objective resolution, variants, checkpoints, lore hierarchy, temporal frames, spatial delivery, and a meaningful test suite.

Its central thesis is sound:

> Long-form LLM fiction becomes more coherent when objective truth, perception, private cognition, memory, belief, and narration are separate systems with separate authority.

That thesis needed one important expansion:

> Epistemic separation is necessary, but it is not sufficient. Coherence also requires atomic state transitions, one declared authority for each fact, evidence-carrying belief updates, and deterministic rejection of authority laundering between agents.

The highest-impact integrity defect was that `commit_all` could persist half a turn. A later failure left earlier domains permanently real. That defect has been removed. The project now prepares slow provider work before the write lock and commits all primary turn effects inside one outer SQLite transaction.

## What the architecture gets right

### 1. Fictional minds do not receive a disguised omniscient prompt

Character agents are supplied with character-specific perception, memory, knowledge, relationships, private history, and fallible mind models. This is structurally stronger than placing all lore in one context and asking a model to pretend it does not know some of it.

### 2. Action onset and resolved outcome are different information events

`perception_act` lets characters react to what begins to happen. `director_resolve` determines what objectively succeeds. `perception_outcome` then distributes the result. This prevents the common roleplay error where an NPC reacts to the completed future outcome rather than the evidence available at reaction time.

### 3. Authority is mostly well partitioned

- The player owns declared speech, thought, and attempted action.
- The Director owns objective causality.
- Characters own their attempted behavior and private appraisal, not success.
- Perception owns signal delivery, not intent.
- Narration owns prose rendering, not world truth.
- Commit owns persistence.

This is the project’s strongest conceptual contribution.

### 4. Intermediate outputs are inspectable rather than ephemeral

Steps and immutable variants make rerolling, resume, stale propagation, manual inspection, and partial recomputation possible. This is essential for debugging a multi-agent fiction system because a bad final paragraph may originate several stages earlier.

### 5. The test suite protects real architectural seams

The suite includes concurrency, temporal-frame isolation, speech concealment, unknown identity, memory provenance, theory-of-mind revision, checkpoint behavior, world-entity chat scoping, spatial frames, strict output validation, and rerun behavior. This is far beyond typical experimental roleplay code.

## Improvements applied in this audit

### Atomic turn persistence

`commit_all` now performs three phases:

1. **Prepare:** project the post-turn scene, validate mapping, batch lore embeddings, build memories, and batch memory embeddings without holding SQLite’s write lock.
2. **Commit:** apply scene, entities, cast changes, paradox checks, spatial reconciliation, lore, memories, relationships, events, background presence state, and pending-state cleanup inside one outer transaction.
3. **Derive:** update autobiographical summaries afterward because they are reconstructible caches and may require an LLM call.

The first durable-domain failure aborts immediately. Nested transactions become savepoints, and the outer transaction rolls every earlier mutation back. A regression test deliberately writes state in the first domain, crashes the second domain, and verifies the first write does not exist afterward.

### Batched provider work outside the database lock

Memory documents and recall cues are normalized and embedded as one prepared batch. Mapping lore operations are also embedded in one batch. This reduces provider round trips and prevents network latency from holding `BEGIN IMMEDIATE`, improving both throughput and failure isolation.

### Pure scene projection

Scene merging now deep-copies the prior scene. Nested room, entity, overlay, and attire objects can no longer mutate the caller’s pre-turn state through shared references. This removes order-dependent comparisons and makes rollback preparation trustworthy.

### Mapping/perception scheduling correction

Fast cached mapping runs serially because parallelizing a near-instant operation only introduced a race seam. Full mapping may still overlap with action-onset perception when routing existing-world lore, preserving the major latency win. When a turn enters or explicitly queries a new location, mapping now runs first so the first perception pass receives freshly staged room notes.

### Narrator authority boundary

The Narrator had been explicitly instructed to coin proper nouns and hard facts, then report them through `new_specifics`; Mapping could validate those suggestions into canon. That created an authority-laundering path from rendering to objective truth.

The Narrator is now prohibited from coining hard world facts. `new_specifics` is an audit field for unsupported details accidentally introduced in prose. Commit excludes those flags from canon inputs and emits a warning. A dedicated test proves narrator-only specifics cannot create lore.

### Host credential semantics

Conflicting tests encoded two different contracts for the host secret. The implementation and tests now consistently enforce the safer contract: plaintext is returned only when a secret is minted or explicitly reset; only its hash persists.

### Lock lifetime and startup maintenance

Per-turn commit locks now use weak references so completed turn IDs do not accumulate permanently in process memory. FastAPI startup was moved from deprecated `on_event("startup")` handling to a lifespan context.

### Documentation alignment

The pipeline, database guide, editing guide, design document, and coding-agent notes now describe atomic commit behavior, mixed-scope concurrency, chat-scoped entity identity, and conditional mapping/perception overlap accurately.

## Gaps in the premise and the corrected model

### Gap 1: “No omniscient NPCs” is not a complete definition of coherence

An engine can perfectly restrict knowledge and still become incoherent if a turn partially commits, two state representations disagree, aliases fork one identity into several entities, or later stages canonize unsupported prose.

**Corrected premise:** coherence is the conjunction of epistemic integrity, causal integrity, identity integrity, temporal integrity, and transactional integrity.

### Gap 2: A model-filtered perception is not a security boundary by itself

Spatial helpers deterministically inject or suppress many speech/action signals, but the perception model can still add unsupported semantic conclusions: recognizing intent, identifying an unknown speaker, or describing an unseen causal source.

**Recommended direction:** represent important delivered evidence as structured signal records with stable IDs and channel metadata. Generate prose views from those signals, then validate that every named identity, quote, action, and causal assertion in the view is supported by at least one delivered signal or a legitimate memory/inference edge.

The ideal unit is not merely a string view. It is:

```text
objective event -> emitted signals -> delivered signals -> observer interpretation
```

Interpretation may be wrong, but it must be wrong from available evidence rather than imported truth.

### Gap 3: The project has overlapping physical authorities

Immediate state is split between the `world.scene` JSON document and normalized world/entity/location tables. Both are useful, but “durable” is not the same as “authoritative.” When they disagree, downstream code can select different realities.

**Recommended direction:** publish a field-level authority matrix. For example:

- normalized tables: identity, containment, durable entity existence, conditions, scheduled events;
- scene projection: current render-oriented room graph, transient overlays, attire presentation, cached adjacency;
- lore: descriptive and historical canon, never immediate placement;
- events: append-only causal ledger;
- checkpoints: recovery snapshots, never a live authority.

Eventually, generate the scene projection from normalized state plus presentation caches instead of maintaining two independently mutable world models.

### Gap 4: Belief confidence is weaker than evidence lineage

Mind models carry confidence and evidence text, but contradiction processing and source identity remain incomplete. Confidence values can blend smoothly while still being based on duplicated, circular, or mutually dependent evidence.

**Recommended direction:** make evidence references first-class rows or stable event/signal IDs. Track whether evidence was witnessed, reported, inferred, or copied from another belief. Belief revision can then discount circular reports and preserve explicit competing hypotheses.

### Gap 5: Canon validation needs provenance tiers

Mapping is privileged and can turn proposals into durable lore. Even with validation, not all inputs have equal authority. Player assertions, resolved objective events, imported canon, staged spatial necessities, character beliefs, and narrator wording should not enter the same “proposed fact” pool.

**Recommended direction:** assign every canon proposal a provenance and allowed disposition:

- `imported_canon`: update only through explicit edit/reinterpretation;
- `resolved_fact`: may create or update objective canon;
- `player_claim`: remains a claim unless Director Resolve accepts it;
- `spatial_generation`: may establish only the minimum required geometry/detail;
- `character_belief`: belongs in memory/mind models, never objective lore;
- `narrator_audit`: reject from canon;
- `inferred_mapping`: provisional until corroborated.

### Gap 6: Concurrent temporal frames share some supposedly objective domains

Frame-scoped world keys, memory visibility, and character overlays permit genuine concurrent play. Lorebooks, entities, placements, conditions, and scheduled events remain chat-global. Two frames may therefore prepare against different snapshots and merge into one shared domain later.

**Recommended direction:** decide domain by domain whether it is:

- frame-local;
- immutable across frames;
- append-only with temporal coordinates;
- shared but revision-checked;
- merged through an explicit paradox/reconciliation rule.

At minimum, prepared commits that touch shared canon should carry a base revision and reject or reprepare when the revision changed before commit.

### Gap 7: Narrative quality is orthogonal to simulation correctness

The architecture can produce a perfectly valid but dramatically inert sequence. Simulation determines what happened; it does not automatically determine scene purpose, tension shape, reveal timing, motif, or when a scene should end.

**Recommended direction:** add scene lifecycle and narrative-pressure state without giving it authority over facts. A scene manager may suggest pacing goals, unresolved dramatic questions, or compression, but must consume the simulation and never overwrite causality or character autonomy.

### Gap 8: Static pipelines spend cost uniformly where uncertainty is not uniform

The engine already self-gates background reactions and uses cached mapping, but most stage selection remains coarse. A quiet continuation and a multi-party spatially contested action do not need the same validation budget.

**Recommended direction:** use a deterministic risk score from action complexity, number of observers, spatial novelty, authority claims, contradiction count, and state-diff breadth. Use that score to select validation depth, model tier, repair count, and whether a sanity-check pass is worth its cost.

The sanity checker should validate invariants and deltas, not rewrite prose or decide story outcomes.

## Highest-priority remaining work

### Priority 0 — source-of-truth consolidation

Define an authority matrix for every durable field. Add assertions that prevent two systems from independently owning the same fact. Begin with positions, entity existence, room containment, time, and conditions.

### Priority 1 — evidence-carrying perception

Create stable signal/event IDs and require memory and belief evidence to reference them. Add adversarial tests where the perception model attempts to identify concealed actors, infer intent, or reconstruct muffled dialogue.

### Priority 2 — frame/global conflict control

Add revisions to shared canon/world domains and verify the revision used during preparation at commit time. Reprepare or surface a conflict rather than silently merging stale proposals.

### Priority 3 — migration and import hardening

Test every historical schema migration, archive round trip, nested lorebook branch, and malformed import. Apply configurable request-size and decompression limits before treating the service as safe beyond a trusted local environment.

### Priority 4 — test the expensive orchestration paths

The measured suite coverage is **77% overall**. Deterministic core modules are generally much stronger, but execution coverage remains weak in `agents/mapping.py` (11%), `agents/narration.py` (29%), provider paths (30%), importers (44%), and parts of the HTTP surface. These are precisely the areas where external model/provider behavior and malformed input create failures.

Use provider fakes and recorded structured payloads rather than live model calls. Prioritize behavior and invariants over line coverage alone.

## Suggested architectural target

A mature version of the engine should make this chain explicit:

```text
Player declarations
    -> interpreted claims and attempts
    -> objective candidate events
    -> emitted physical/informational signals
    -> observer-specific delivered signals
    -> observer interpretations and declarations
    -> objective resolution
    -> post-outcome signals
    -> memories and evidence-linked beliefs
    -> player-facing rendering
    -> atomic persistence and provenance-tagged canon
```

That architecture preserves the project’s original insight while closing the remaining loopholes: facts cannot leak merely because a model saw them, prose cannot become truth merely because it sounded good, and a failed subsystem cannot leave half a reality behind.

## Validation status

The release gate completed successfully:

```text
make check
- source compilation: passed
- generated code map: refreshed
- repository structure checks: passed
- complete test suite: 527 passed
- measured line coverage: 77% overall
```
