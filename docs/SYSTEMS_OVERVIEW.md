# Sonder Engine — Systems Overview & Diagram Prompts

A plain-language tour of every major system in the engine: what it does, which
files own it, and how it connects to the rest. Each section that benefits from a
picture includes a **ready-to-paste ChatGPT prompt** for a diagram.

> This is the friendly orientation doc. For exact execution order see
> [`PIPELINE.md`](PIPELINE.md); for the module/table/route index see
> [`CODE_MAP.md`](CODE_MAP.md); for schema and write helpers see
> [`DATABASE.md`](DATABASE.md); for philosophy and roadmap see [`Design.md`](../Design.md);
> for the current fix backlog see [`AUDIT_FOLLOWUPS.md`](AUDIT_FOLLOWUPS.md).

### How to use the diagram prompts

Each fenced **DIAGRAM PROMPT** below is written for ChatGPT. Two ways to use it:

- **For crisp, legible flowcharts / graphs / ER diagrams** — paste the prompt and add:
  *"Render this as a Mermaid diagram and show the code."* Text stays sharp and you can
  tweak it. (Mermaid also renders directly in GitHub and in this repo's tooling.)
- **For a conceptual "hero" illustration** — paste the prompt and add:
  *"Generate an image of this."* Good for slides; raster text may blur, so keep labels short.

---

## 1. What the engine is (in one breath)

A local, multi-agent interactive-fiction engine whose defining rule is an
**information barrier**: it produces coherent fiction *without* letting any
fictional mind use knowledge it did not legitimately perceive, learn, remember, or
infer. Six things that most engines collapse into one blob are kept as distinct
layers: **objective truth → perception → memory → inference → belief → narration.**
Every agent sees only its layer.

```
DIAGRAM PROMPT — "The six information layers" (concept diagram)
Create a horizontal layered diagram titled "Sonder Engine — Information Barrier".
Six stacked panels, left to right, each feeding the next through a narrowing funnel:
1) OBJECTIVE TRUTH (what actually happened — owned by the Director)
2) PERCEPTION (what a given observer could sense — a stateless filter)
3) MEMORY (what that observer retained from its own perceptions)
4) INFERENCE (what it concluded, with confidence)
5) BELIEF (its possibly-wrong model of the world and other minds)
6) NARRATION (only the player's slice, rendered as prose)
Between each panel draw a filter/funnel labeled with what gets removed
("hidden state", "unperceived facts", "other minds", "unearned identity").
Caption: "No mind receives a layer to its left." Clean, modern, muted palette.
```

---

## 2. The cast of agents (who is allowed to know what)

The engine is a pipeline of specialized agents with strict ownership boundaries.
Role modules live in `agents/` and may import `agents/common.py` but never each
other; only `agents/runtime.py` knows every stage.

| Agent | File | Owns | Must NOT |
|---|---|---|---|
| **Director** | `agents/director.py` | Objective causality: interprets input, resolves outcomes, owns the world diff, dice, obligation ledger, player-fact adjudication | Character psychology; narration; silently rewriting the player's declared words |
| **Perception** | `agents/perception.py` | A stateless filter deciding what each observer legitimately receives this beat | Invent intent; leak hidden state or unearned identity |
| **Character** | `agents/character.py`, `agents/loops.py` | A private mind's declared behavior from its own perception/memory/relationships/interior | Decide its own success; see other minds or objective truth |
| **Background** | `agents/background.py` | At most one stateless, one-beat line for a named unregistered presence | Persist memory or psychology (that needs promotion) |
| **Narrator** | `agents/narration.py` | Rendering the player-facing slice as prose | Originate player conduct; reveal unperceived facts |
| **Mapping** | `agents/mapping.py` | Routing lore, staging canon, growing the world tree | Decide what a character perceives |
| **Commit** | `commit.py` | The **sole** persistence boundary — validates provisional output and writes it | (everything else is provisional until it runs) |
| **Runtime** | `agents/runtime.py` | Building the per-turn plan, dispatch, streaming, cancel, resume, reroll | — |

```
DIAGRAM PROMPT — "Agent authority map" (graph)
Create a node-graph titled "Sonder Engine — Agents & Boundaries".
Center node: RUNTIME (orchestrator). Around it, agent nodes: Director, Mapping,
Perception, Character (x multiple), Background, Narrator, Commit.
Color the nodes by trust tier: Director = "objective truth" (red), Perception =
"filter" (amber), Character/Background = "private mind, partial info" (blue),
Narrator = "player-facing only" (green), Commit = "persistence gate" (grey).
Draw arrows for data flow: Runtime dispatches each agent in turn order; Perception
feeds Character and Narrator; Character feeds Director-Resolve; everything funnels
into Commit. Add a dashed boundary line labeled "information barrier" separating
the red Director from the blue Character nodes, annotated "characters never receive
objective truth directly." Legend included.
```

---

## 3. The turn lifecycle

Every turn runs through a `PipelineContext` (`pipeline_context.py`) executed by
`agents/runtime.py`. Each stage's output is saved as a `steps` row + one active
`variants` row — which is what makes reroll, rerun-from-stage, and manual editing
possible.

**Opening turn** (`turn.idx == 0`): establish the world, then render it.
**Normal turn**: the plan is built dynamically from `director_interpret.flow`.

```
DIAGRAM PROMPT — "Normal turn pipeline" (flowchart)
Create a top-to-bottom flowchart titled "Sonder Engine — Normal Turn".
Sequence of boxes with arrows:
1) director_interpret  (parse player input -> speech/action sequence, authority
   claims, likely reactors, mapping need, resolution flags)
2) decision diamond: "new location / lore needed?" -> YES: mapping_stage (full lore
   routing) ; NO: mapping_quick (cached recall)
3) perception_act  (observer views of the action ONSET, before outcome)
4) decision diamond: "contested physical reaction?" -> YES branch to reaction_loop
   (blind simultaneous reactions)
5) decision diamond: "reactors exist?" -> if autonomy>0: interaction_loop
   (sequential, later speakers hear earlier ones) ; if autonomy==0: parallel
   character:<id> steps (blind, independent)
6) director_resolve  (combine all declarations -> one resolved event + state diff;
   obligation ledger; player-fact adjudication)
7) background_react  (deterministically gated; usually a no-op)
8) perception_outcome (observer views of the RESULT)
9) narrator  (player-facing prose)
10) commit  (validate + persist everything atomically)
Put a side note on perception_act: "runs BEFORE resolution so characters can't
react with future knowledge." Use a clean vertical flowchart style, rounded boxes,
diamonds for decisions.
```

```
DIAGRAM PROMPT — "Opening turn pipeline" (flowchart)
Create a short top-to-bottom flowchart titled "Sonder Engine — Opening Turn (idx 0)":
mapping_stage -> director_establish (privileged objective scene + actor state) ->
perception_establish (player's opening view) -> narrator (opening prose) -> commit.
Annotate director_establish: "objective setup, not player-facing." Simple, 5 boxes.
```

**Stage owners in brief** (full detail in `PIPELINE.md`):
- `director_interpret` — parse the declaration; preserve wording; separate *attempts* from *asserted facts*; decide the plan shape.
- `mapping_stage` / `mapping_quick` — full lore routing vs. fast cached recall.
- `perception_act` — action-onset views (delivery, visible movement, sensory evidence, deterministic spatial facts).
- `reaction_loop` — contested, time-sensitive physical reactions: blind, simultaneous declarations.
- `interaction_loop` / `character:<id>` — conversational/physical micro-beats; sequential (hear each other) or parallel (blind).
- `director_resolve` — one resolved event + state diff; owns dice, obligation ledger, fact adjudication.
- `background_react` — self-gating one-beat backstop for an unregistered presence.
- `perception_outcome` — outcome views on the merged post-resolution scene.
- `narrator` — the only stage that writes prose to the player.
- `commit` — the atomic persistence boundary.

---

## 4. Orchestration & persistence spine

| System | File | What it does |
|---|---|---|
| **Runtime** | `agents/runtime.py` | Builds the plan from `director_interpret.flow`; dispatches stages; streams; cancels; **resume** (recompute from a stage), **reroll** (new variant of one step), **rerun-from-stage** |
| **Pipeline context** | `pipeline_context.py` | The typed mutable object carried through a turn (chat/turn rows, cast, input, per-stage outputs, per-character results, warnings) |
| **Step storage** | `agents/storage.py` | `steps` (one per `(turn_id, key)`) + `variants` (immutable JSON outputs, one `active`) |
| **Commit** | `commit.py` | The single persistence gate. Slow prep (lore/memory embeddings) happens *before* the write lock; then all primary mutations commit inside one outer transaction. Any domain failure rolls the whole turn back; only reconstructible summary consolidation runs afterward |
| **Database** | `db.py` | SQLite schema, migrations (recreate-copy-swap), connection pool, transaction helpers (`q`/`qi`/`qtx`/`transaction`), and the world key/value store (`wget`/`wset`) |
| **Checkpoints** | `checkpoints.py` | Whole-chat snapshots per turn + restore orchestration |

**The invariant:** *a turn either commits all primary persistent effects, or none.*

```
DIAGRAM PROMPT — "Steps, variants & reroll" (diagram)
Create a diagram titled "How reroll / rerun works".
Show a horizontal chain of pipeline STEPS (director_interpret -> perception_act ->
character -> director_resolve -> narrator -> commit). Under each STEP box, stack 1-3
VARIANT cards (immutable JSON outputs); highlight ONE per step as the "active"
variant (glowing border). Illustrate three operations with colored arrows:
(a) REROLL = generate a new variant for a single step and make it active;
(b) RERUN-FROM-STAGE = mark this step and all downstream steps stale, recompute;
(c) EDIT = hand-author a new active variant.
Caption: "Because every stage's output is a stored, immutable variant with one active
pick, the whole turn is inspectable, editable, and reproducible." Clean, card-based.
```

```
DIAGRAM PROMPT — "Atomic commit" (flowchart)
Create a flowchart titled "commit_all — atomic turn persistence".
Phase 1 (BEFORE write lock): "prepare" — scene projection, mapping validation, lore
embeddings, character-memory embeddings (may call a provider). Then a lock icon.
Phase 2 (UNDER one outer transaction): write scene, world_entities, room_registry,
cast, lore, relationships, events, memories, obligations. Show a red "first failure
-> ROLL BACK ENTIRE TURN" path branching off. Phase 3 (AFTER commit, outside txn):
"autobiographical summary consolidation (reconstructible; failure is a warning only)."
Annotate the transaction box: "a turn commits all primary effects or none."
```

---

## 5. The character mind (interior depth)

This is the engine's signature system: a character acts from a layered interior
that the information barrier keeps private, leaking only through observable behavior.

| System | File | What it does |
|---|---|---|
| **Character agent** | `agents/character.py` | Builds a private payload (identity, psychology, filtered perception, memory, relationships, mind-models, interior) and returns declared behavior |
| **Affect** | `affect.py` | The engine-side math: three-tier goals, blended mood, drive-strain accrual, and the drive-rupture machinery |
| **Theory of mind** | `theory_of_mind.py` | Per-character models of *other* minds, with confidence caps and fallible belief |
| **Memory** | `memory.py` | Per-character episodic/semantic/inference memory, retrieval, consolidation, and relationships |
| **Schema** | `character_schema.py` | Versioned character/persona sheets, normalization, accessors |

**The layers:**
- **Three-tier goals** — a stable **core drive** (essence / expression / taboo), persistent **standing intentions**, and per-beat **wants** (with an enacted/suppressed distinction).
- **Blended mood** — an OCC-style appraisal reads the model's `goal_impacts`; the engine deterministically computes affect on canonical valence/arousal axes: a **surface** reaction over a slower **undercurrent** above a character **baseline**, decaying between beats. *The model proposes; the engine floors and reconciles.*
- **Calibrated tells** — interior state surfaces only as physical cues, gated per perceiver, with an anti-repetition ledger.
- **Earned drive rupture (with a floor)** — sustained strain + a high-impact event opens a rupture window; after a few turns the character prompt escalates to a **forced resolution**, and after a hard cap the window **force-closes** — so a rupture the engine opens can't sit in permanent limbo. A completed shift leaves a **scar** (`former_drives`).

```
DIAGRAM PROMPT — "Drive-rupture state machine" (state diagram)
Create a state-machine diagram titled "Drive Rupture Lifecycle".
States and transitions:
- STABLE --(sustained strain primer + high-impact event)--> RUPTURE WINDOW OPEN
- RUPTURE WINDOW OPEN --(a few turns pass, strain stays high)--> FORCED RESOLUTION
- FORCED RESOLUTION --(character emits drive_shift)--> DRIVE SHIFTED (leaves a "scar"
  in former_drives; strain resets) --> STABLE (new drive)
- FORCED RESOLUTION --(character reaffirms old drive)--> STABLE (strain paid down)
- RUPTURE WINDOW OPEN --(hard cap turns reached, still no shift)--> FORCE-CLOSE
  (strain paid below floor) --> STABLE
Annotate: "the window can re-extend while strain stays high, but the two floors
(force-resolution, force-close) guarantee it can never sit open forever." Add a small
gauge showing 'drive_strain 0..1' with markers at RUPTURE_STRAIN_MIN and CRISIS_STRAIN_MIN.
```

```
DIAGRAM PROMPT — "Blended affect" (layered graph)
Create a layered line-graph titled "Blended Mood over a scene".
X axis = turns. Three stacked bands: BASELINE (flat, the character's temperament),
UNDERCURRENT (slow-moving, e.g. rising dread), SURFACE (fast, spiky per-beat reaction).
Show the rendered "mood" as the blend of all three. Mark one beat where surface spikes
(a shock) while undercurrent keeps climbing. Caption: "The model proposes goal-impacts;
the engine computes valence/arousal deterministically and decays them between beats."
```

---

## 6. Memory & lore

`memory.py` is a large module covering both a character's autobiographical memory
**and** the shared lorebook graph (they share the vector-search machinery).

- **Per-character memory** — `memories` rows: episodic / semantic / dialogue / inference, each with `provenance` (witnessed / heard / told / inferred / read), `salience`, `emotional_context` + numeric `valence`/`arousal`, entities, location, and a vector embedding. Retrieval blends recency + salience + semantic cue match; **consolidation** rolls episodes into `memory_summaries`.
- **The lore graph** — `lorebooks` form a tree (`parent_id`, links), holding `lore_entries` with keys, knowledge tags, and embeddings. Mapping routes and retrieves from it.

```
DIAGRAM PROMPT — "A memory's life" (flowchart)
Create a flowchart titled "Life of a Memory".
1) A character PERCEIVES an event (filtered view). 2) At COMMIT, the engine mints a
memory row: content + gist + provenance (witnessed/heard/told/inferred/read) +
salience + emotional valence/arousal + entities + a vector embedding. 3) Later turns
RETRIEVE it by blending recency + salience + semantic cue-match to the current beat.
4) CONSOLIDATION periodically rolls recent episodes into an autobiographical summary
(memory_summaries), preserving unresolved threads. Side note: "a character's memory is
derived ONLY from that character's own view — never from objective truth or another
mind." Clean vertical flowchart.
```

```
DIAGRAM PROMPT — "Lorebook tree" (tree/graph)
Create a tree diagram titled "Lore Graph".
Root: a WORLD lorebook. Children: LOCATION books and ENTITY books, nested. Show
typed LINKS between books (e.g. "part_of", "rules", "see_also") with the
follow-for-retrieval flag. Each book holds LORE ENTRIES (cards) with keys +
knowledge tags (common / scholarly / esoteric). Annotate: "retired-not-deleted — a
destroyed region is retired with the turn that ended it, so its history stays
retrievable." Clean nested tree with a few cross-links.
```

---

## 7. World, space & time

| System | File | What it does |
|---|---|---|
| **Scene** | `scene.py` + the frame-scoped `world.scene` JSON blob | The single runtime source of truth for live rooms, positions, and entity state |
| **Spatial** | `spatial.py` | Room adjacency, visual access, hearing attenuation (open / open-door / closed-door / wall / separated / unknown), fail-closed on unknowns |
| **Egocentric space** | `spatial_frames.py` | Per-character orientation: bearings, facing, derived left/right, came-from, field of view |
| **Mechanics** | `mechanics.py` | The commit-time deterministic sweep: due scheduled events fire, timed transit completes, conditions expire |
| **Registry / entities** | `room_registry`, `world_entities` tables | Cross-frame room identity ledger; derived projection of the committed scene diff |
| **Temporal frames** | `frames.py` | Parallel timelines/eras of one chat; each frame holds its own live world |
| **Paradox** | `paradox.py` | Fixed-point and hazard handling for time-travel/concurrent play |

**Physical-truth authority** (important invariant): the frame-scoped `world.scene`
blob is authoritative for live state; `room_registry` is the single cross-frame room
ledger; `world_entities` is a *derived projection*; `world_placements` /
`fiction_*` / `transit_edges` are decommissioned import-compat tables. Every scene
writer must keep the registry projection in sync.

```
DIAGRAM PROMPT — "Perception firewall by space" (sequence-ish diagram)
Create a diagram titled "Who hears the shout?".
A floor plan of 4 rooms: A (speaker), B (open doorway to A), C (closed door to A),
D (across a wall from A). A character in each. From room A draw sound propagation:
-> B: "full speech (line of sight + sound)"; -> C: "muffled fragment (no sight)";
-> D: "at most a dull thud"; a far room: "nothing". Overlay each listener's resulting
PERCEPTION VIEW as a speech bubble showing exactly what they got. Caption: "Perception
is a deterministic filter; unknown spatial relationships fail closed (no access)."
```

```
DIAGRAM PROMPT — "Temporal frames & paradox" (branching timeline)
Create a branching-timeline diagram titled "Frames".
A main timeline of turns. At one turn it SPLITS into a second frame (an era / a
time-travel branch) that carries its OWN live world (a place destroyed in the present
still exists in the past-era frame). Show frames later MERGING. Mark a "paradox check"
node where a change would contradict an established fixed point, resolved as
fixed-point or flagged as a hazard. Annotate: "the scene blob is frame-scoped; room
identity and lore are cross-frame ledgers."
```

---

## 8. Providers, contracts & IO

| System | File | What it does |
|---|---|---|
| **Providers** | `providers.py` | Model selection per role (`agent_models` setting), retries, streaming, cancellation, embeddings; OpenRouter / Anthropic / OpenAI-compatible backends; Anthropic prompt caching |
| **Output contracts** | `schemas.py` | Pydantic contracts + semantic validation for every agent payload |
| **JSON hygiene** | `llm_quality.py` | Strict JSON parsing, schema validation, model-assisted repair |
| **Prompts** | `prompts.py` | The default system prompts for every agent + preset access |
| **Import / generate** | `importers.py`, `greetings.py` | Native + AI-assisted character/persona/lorebook import (incl. SillyTavern v2/v3 cards); "start story from a greeting" |
| **API + UI** | `app.py`, `static/js/*` | FastAPI app (resource CRUD, import/export, turn control, SSE streaming) + a browser-globals frontend |
| **Access control** | `guest_access.py` | Host login sessions, single-use join codes, scoped guest tokens, deny-by-default |
| **Self-update** | `updates.py` | Fast-forward-only self-update from the GitHub origin |

```
DIAGRAM PROMPT — "Model routing" (graph)
Create a diagram titled "Per-role model routing".
Left: pipeline roles (director, perception, character_major/mid/bg, narrator, mapping,
utility, embeddings). Middle: the agent_models config (role -> {provider, model,
fallbacks}). Right: providers (OpenRouter / Anthropic / OpenAI-compatible), each with
base_url + key. Draw arrows from each role through its config to a provider/model, with
one role showing a fallback chain. Caption: "every role can run a different model tier;
missing config fails loudly." Include prompt-caching as a badge on the provider box.
```

---

## 9. The data model

The relational core is small; most rich state lives in JSON (the `world` key/value
store, character `sheet`, scene blob, and `variants` content).

**Backbone:** `chats` → `turns` → `steps` → `variants`. **Cast:** `characters` +
`chat_chars` (+ `chat_char_frames` per era). **Memory:** `memories` +
`memory_summaries`. **World:** `world` (KV), `world_entities`, `room_registry`,
`world_conditions`, `scheduled_events`, `world_events`. **Lore:** `lorebooks` +
`lore_entries` + `lorebook_links` + `chat_lorebooks`. **Time:** `frames`.
**Recovery:** `checkpoints`.

```
DIAGRAM PROMPT — "Core schema" (entity-relationship diagram)
Create an ER diagram titled "Sonder Engine — Core Tables".
Entities and key relationships (crow's-foot):
- chats 1--* turns 1--* steps 1--* variants   (a turn's stage outputs; one active variant)
- chats *--* characters via chat_chars (status, per-chat state JSON)
- chats 1--* memories *--1 characters ; chats 1--* memory_summaries
- chats 1--* frames (parallel timelines) ; turns *--1 frames
- chats 1--* world (key/value store; holds the live scene blob)
- chats 1--* world_entities / world_conditions / scheduled_events / world_events
- chats 1--* room_registry (cross-frame room identity)
- lorebooks 1--* lore_entries ; lorebooks *--* lorebooks via lorebook_links ;
  chats *--* lorebooks via chat_lorebooks
- chats 1--* checkpoints (per-turn whole-chat snapshot)
- chats *--1 personas
Group the tables into clusters labeled: "Turn spine", "Cast", "Memory", "World state",
"Lore", "Time", "Recovery". Note next to world_entities: "derived projection of the
committed scene diff — the scene blob is authoritative." Clean, grouped, legible.
```

---

## 10. Cross-cutting principles (the "why")

- **Epistemic least privilege** — an agent gets the *minimum* context for its job. The Narrator never sees other minds; a Character never sees objective truth.
- **Capture, don't gate** — the interpret stage *captures* everything the player declared (including world assertions); validation happens later at commit, not by refusing input up front.
- **Persistence is earned** — model output is provisional until `commit.py` validates and writes it; a background presence has no memory until *promotion* earns it one.
- **Structure over instruction** — behavior is shaped by structured payloads and deterministic floors, not by hoping a prompt is obeyed. (The drive-rupture floor and affect reconciliation are examples: *the model proposes; the engine enforces.*)
- **Auditability & recoverability** — every stage is a stored variant; every turn is a checkpoint; a destroyed region is retired, not deleted.

```
DIAGRAM PROMPT — "The engine's thesis" (single hero diagram)
Create one elegant conceptual illustration titled "Sonder".
A crowd of silhouetted figures; a spotlight falls on one, and inside that figure show
a small private world — its own memories, beliefs (some wrong), wants, and a heart
under strain — none of it visible to the figures around it. Thin barrier lines
separate each figure's inner world from the others'. Caption: "Every mind knows only
what it earned. The engine's whole job is to keep it that way." Painterly, warm,
restrained palette. (Sonder = the realization that every passerby has an inner life
as vivid as your own.)
```

---

## Where to go next

- **Change something?** Start with [`AGENTS.md`](../AGENTS.md) (edit-routing table + invariants).
- **Exact flow?** [`PIPELINE.md`](PIPELINE.md).
- **Add a table/field?** [`DATABASE.md`](DATABASE.md) (schema-change checklist).
- **Add a pipeline stage?** [`../agents/README.md`](../agents/README.md).
- **What's still rough?** [`AUDIT_FOLLOWUPS.md`](AUDIT_FOLLOWUPS.md) and Design.md's "Known weaknesses".
</content>
