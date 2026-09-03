# Turn Pipeline

This document describes the implemented orchestration in the `agents/` package, primarily `agents/runtime.py`. It is intentionally narrower than `Design.md`: it explains what executes, what each stage owns, and where results are stored.

## Runtime containers

A turn runs through a `PipelineContext` containing typed chat and turn records,
active cast rows, player input, the validated per-story language-pack id,
named step outputs, per-character results, reaction results, and warnings.
Protocol keys and enum values remain canonical across languages. The selected
pack governs prompt policy, deterministic human-language recognition, and the
compositor's Layer-B rendering; its Layer-A percept admission remains the same
language-neutral information boundary.

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

**No model runs in this stage.** Perception is deterministic end to end —
there is no `perception` role in `providers.ROLES`, no entry in
`prompts`/`schemas.SCHEMA_MAP`, and `agents/perception.py` imports no model
seam. The projection is therefore not "an information boundary a model may
still overrun": it is the whole of what the observer receives, composed from
typed percepts by `agents/composer.py` and realised by `render_view`, which
takes no scene and no database and so structurally cannot add a detail the
percepts did not carry.

The body-detail fidelity floor described here was a repair over MODEL PROSE —
it restored an authored detail when the returned view collapsed an exposed
surface to a generic body part. With the model gone the floor has nothing to
repair: the percept either admits the region's authored detail or it does not,
and there is no second, lossier account of it to compare against. Read the
`body_region_percepts` admission rules for what an observer gets, not this
paragraph.

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

Explicitly authored institutional Charters use that same post-commit epoch.
Charter advances material flows before social reporting, then lets reports
reach authorised officeholders, orders descend one staffed reporting edge,
and typed executors create real consequences. Public shortage/order events are
witnessed into individual minds; local judgments and commitment knowledge are
derived only from those held claims. Generation is an authoring path, not a
turn stage: `/charters/generate` closes one qualitative lore-grounded plan
under the closer's invariants (a requested `population`, one holder per head
post, a crew for every other, no berth over its ceiling), plants prose-free
planned rooms, runs coarse-plus-recent presim over that planted skeleton, and
optionally stores a historian summary whose turning points cite actual presim
event ids. The opening commit merges onto the seeded skeleton, so every
planned room and exit is in the committed scene from turn 0.
The same operation is available during ordinary story creation and greeting
quick-start; greeting launch lands it before establishment runs turn 0. During
play it reads the explicitly selected lorebook subtree, preserves existing
locations/Charters, namespaces room/structure/body collisions, and advances
only the newly added registry slice. It never rewrites the current live room.
`charter_runtime.schedule_charter_ticks` advances a copied registry in an
out-of-band deterministic job, then lands the whole frame-scoped state plus
stable `scheduled_events` rows atomically only if epoch, base turn, and the
source registry revision still stand. The guards run under the landing write
lock, so a concurrent turn, restore, or author edit cannot slip between check
and write. Those rows re-enter the ordinary mechanics → `world_events` → carrier
path on the next sweep. Charter owns each unpromoted body's sparse news claims;
`charter_runtime.carrier_entries` projects them onto the ordinary carrier
interface so witnessing, telling, couriers, caravans, notices and promotion use
one physical delivery rail rather than parallel ledgers.
Movement resolution additionally folds at most three current Charter facts into
the existing `destination_residue` aperture. A background presence receives
only the presence view for its own body. Unpromoted Charter bodies in the
player's ambient scope are derived into the background gate with durable
`{charter, body}` references; this does not create a second identity record
until ordinary presence tracking has conduct to retain.
Their personal names are materialized on the Charter body, while titles remain
bounded aliases. Player and character recognition learns those aliases only
when an exact delivered line names a co-located Charter body; lookup is indexed
once per beat, rather than scanning an institution for every spoken line.
Transcript color uses the permanent Charter/body seed before and after
promotion.

Story-start prehistory may include full characters as featured residents.
Greeting launch supplies its one selected card; Story Quick Start exposes one
independent history route for every selected or newly generated cast member,
then resolves the browser's temporary keys to attached character ids before
calling the same `charter_runtime.generate_lived_location` operation. That
inclusion is never implied by generating a location. Before any history backend
runs, `story.history_routing` resolves a closed topology from the author choice,
card, opening and location brief. The runtime ignores any requested character
that is not actually attached to that story. Only fixed-place or bounded-moving
resident routes may send a full character through Charter;
travel/arrival evidence wins over apparent job competence, and uncertain auto
routes preserve authored history rather than inventing tenure.
Only their public history and ability name/scope rows corroborated by that
public history reach the location planner; ability limits, private history and
psychology do not enter Charter generation. Deterministic
closure places that stable seed exactly once and repairs a planner omission by
matching it to an existing lore-authored post. After presim, `charter_history`
builds a closed recent-life context from that body, its named coworkers and
reporting line, real work/home rooms, duties, held reports, commitments,
participant-owned experience and actual simulation anchors. One bounded
utility call authors 10–16 detailed personal episodes under an explicit
minor-prehistory licence. Each is validated against the closed people/place
ids and written as its own `turn_idx=NULL` memory row with a content-derived
identity, chronology, location, entities, affect and consequence. Every named
participant receives a compact reciprocal `shared_prestory` experience in
their own Charter history, so later promotion cannot erase that the meeting
happened. Fewer than
ten usable episodes abort launch; there is no sparse canonical fallback.
`bind_promoted_character` then retires the Charter mind before establishment
while preserving the institutional body. Aggregate watches produce a separate
human-readable career summary rather than an episodic memory. Recent presim
always includes the featured body's work and berth places. Generated lived
locations must materialize a stable personal name for every body; a missing
naming law fails generation instead of exposing a machine post id. Authored private
habits attach only after public location planning, run only while that body is
off duty, write only that body's bounded experience, and leave with the
temporary Charter cognition at handoff. Each selected cast member is routed
independently: one may be a local resident while another preserves an authored
traveler history, without sharing a universal location-shaped past.

An arriving traveler uses `story.journey_history`, never a location-shaped
Charter. Cited mode compiles only card/lore source ids into ordered world
visits; generated mode is a separate explicit author licence for the LLM to
invent a bounded journey ledger. Failure of cited compilation falls back to
the unchanged card and greeting; failure of an explicitly requested generated
journey aborts launch rather than silently charging for nothing.

After the ordinary `memories` domain settles each acting character's prepared
state, `information_carriers` acquires public event surfaces for physical
holders at the event location: registered characters, the player, unpromoted
Charter people, and standing crowds. It advances the bounded route on reports
whose full-character holder moved. It must remain after `memories`: writing
earlier would let the precomputed state update erase the envelope. A Charter
row is translated into that exact body's `minds` entry at persistence and is
projected back only from that body. Co-location never copies knowledge;
explicit speech, a staffed reporting line, a courier/caravan handoff, or
reading an artifact does.

`charter_observations` follows that domain. The resolve social specialist has
classified the beat's engine-authored player/major-character sources once;
deterministic grounding restores actor, target, exact quote/action surface,
volume and concealment from those sources and accepts semantic content only as
an exact span of the utterance. The commit domain then delivers each source to
each unpromoted Charter body through ordinary full-hearing/full-sight checks.
Only that body's sparse `minds` map receives the resulting news claim. A failed
or empty semantic classification keeps the factual source, while a retelling
drops the pristine quote and retains only coarse speech-act direction. Scene
Life reads the structured evidence through that body's capped `can_bring_up`;
no narrator prose, raw player input, objective state diff or other body's mind
enters this path. The domain unwraps the prepared-commit envelope to the scene
first (it passed the envelope itself until 2026-09-03, so no actor ever had a
room), lets every unbound body standing where a scene-owned figure stands see
it (`charter_runtime.sight_figures_in_scene`), keys the figure by its canonical
name with the witnesses' stranger label as the surface, and warns when the
scene places an actor nowhere.

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
- **An installed extension can add steps of its own.** `build_plan` returns
  `_extension_splices(plan, chat_id)` — the LAST thing it does, so an extension
  anchors against the plan the engine actually built this beat. Splices derive
  only from the enabled set and installed manifests, never from anything else
  about the turn, because resume and reroll recompute `build_plan` and must get
  the same list back. The hook is total: any failure leaves the plan exactly as
  the engine built it, so a broken extension cannot cost a turn. See
  [`EXTENSIONS.md`](EXTENSIONS.md) for `register_step` and the splice manifest.
  **`establishment_plan()` splices too**, and did not until recently: three of
  its five steps (`mapping_stage`, `narrator`, `commit`) also run on a normal
  turn, so an extension anchored `after:mapping_stage` or `before:narrator` was
  silently unplanned on turn zero — the step ran and the splice did not, which
  is the opposite of what the extension contract predicts.

A spliced step's key is `ext:<extension-id>:<step-name>`, and it is a plan step
like any other: one `steps`/`variants` row pair, one active variant, reroll,
rerun-from-stage and the pipeline drawer, with no schema entry required. That
namespace is why **a core step id is a published name** — extensions anchor on
them from outside the tree, so renaming one breaks every extension anchored on
it in a way nothing in this repository will catch.

### `director_interpret`

Parses the player declaration into structured speech/action sequence, authority claims, likely reactors, mapping need, and resolution flags. It also determines the later plan shape.

This stage should preserve player wording and distinguish attempted actions from asserted facts.

Exact quoted speech and described communicative meaning are different sequence
types. `speech` is licensed only by words the player actually supplied;
`communication` carries an authored act and proposition (ask, explain, warn,
report) without inventing a quotation. It follows the same hearing,
concealment, memory, public-evidence and Charter-carrier paths as speech, but a
partial hearing channel receives only that somebody spoke indistinctly.

An interruptible compound act is represented as phases rather than one prose
blob. `phase_id` identifies a phase, `depends_on` names the phases that must
have completed, and `participants` / `requires_contacts` state structural
prerequisites. `referents` binds exact occurrences of ambiguous pronouns to
canonical entities; every observer renderer substitutes only the label that
observer is entitled to use.

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

A `contestable` action's visible first phase is rendered under explicit attempt
modality. A model-authored predicate such as `creates space` is not itself
permission to tell a reactor that space was created before they react, nor to
tell the narrator it succeeded after resolution rejected that effect. The
complete observable remains available to resolution and is released only when
the action's dispositions make it true.

Only atomic/onset roots without dependencies enter this pass. Continuation and
completion phases are deferred until reactions have declared. The same rule
applies to `state_assertions`: `onset_state_assertions` is an engine-authored,
copy-only projection with changes sourced to deferred phases removed. The full
assertion remains available to resolve and commit, subject to the causal floor.

A direct contact the player declares as already present through their own
conduct or first-person body sense is structured by interpret as
`contact_assertions`. Pass 1 previews those assertions on a copy of the scene
before any reactor decides, so both participants receive the same relation from
their own bodily endpoint. The guard admits a new relation only when the player
is its actor; an NPC-to-player assertion must refine a matching contact that
already stands, preventing first-person wording from authoring a new NPC act.
Everything else the player's declaration ASSERTS as already true is carried
the same way and for the same reason, as `state_assertions`. **Interpret is
not a lesser authority than `director_resolve`; it is the same authority
scoped to the player's input**, so the field is a full `StateDiff` — the exact
structure resolve emits, every channel of it — applied through the same
`merge_scene_with_diff` commit uses, followed by `apply_attire_diff` in
commit's own order (attire has its own applier because the removal ladder's
clamp reads the beat's prose). Without this, a declaration reached the scene
only through resolve, which runs after every character has declared, so a
player who took their top off, knelt, or ducked into an alcove was perceived
in the previous outfit, the previous posture and a room without the alcove
for the whole beat in which they changed all three.

The player's ROOM is resolved from that previewed scene, not from the scene as
stored. It was read fourteen lines earlier, so a declared step into the next
room reached `sc` and never reached `p_room`, and every
`spatial_rel_between(..., target_room=p_room)` afterwards graded her from the
room she had left while the same scene placed her in the new one — one
observer's view carrying her presence in the room she had entered and her
lines as co-present in the room she had not. Presence and channel are two
readings of one world, so they read one scene. The cached `ctx["_player_room"]`
stands in only where the scene tracks no position at all, and the resolver
(which may cost a model call) is asked only when neither has an answer.

What bounds it is its SOURCE, not a channel list or a subject guard: interpret
reads the player's declaration and nothing else. An unfinished attempt, and
anything acting on another character, is kept out by being classified
`contestable` — which interpret already does, and which routes it to the
reaction phase — rather than by restricting which channels may be written.
`director_resolve` receives the same previewed world and may re-resolve any of
it; where it speaks about the same subject it wins, and silence does not
revoke the assertion. The assertion is merged into resolve's own `state_diff`,
so the beat persists exactly once through every guard commit already runs, and
commit remains the only writer. The information firewall is unaffected: a fact
in the scene is not a fact in a mind, and the composer still admits it to an
observer only if that observer can perceive it.

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

Each normalized contact also receives a stable opaque `contact_id` derived
symmetrically from its two owned endpoints. Ongoing tactile dynamics that
topology cannot express live in `scene.contact_actions`, attached to that id:
vibration, pressure pulses, steady pressure, suction, and analogous
genre-neutral effects. A same-beat new contact may be selected by its exact
four endpoints. Effects persist without reassertion, accept bounded
add/change/remove/clear operations, and are pruned when their parent contact
ends. Only a contact participant receives the deterministic, cause-blind touch
percept; arbitrary diagnostic detail never crosses the identity firewall.

A character can also end a contact without trusting the resolve model to infer
that state transition from prose. Its private payload lists every onset contact
involving its body under `self.standing_contacts` using opaque `contact:N`
handles. A completed, self-owned release or withdrawal returns exact
`contact_ops:[{op:"remove",contact_ref}]`; contested attempts return no op.
Resolve maps each ref back to the exact ledger direction and parts, projects
those removals before its own contact diff, and rejects a stale re-add of the
same contact. Other simultaneous contacts survive unless separately named.

A completed material output has the same actor-ownership guarantee. The
character sees its own conditional embodiment capabilities and can return an
additive `material_effects` record with the exit part, established material,
and known destination. The host canonicalizes `source` to that character and
accepts only add/release/deposit operations. Resolve receives the declaration
for prose and state projection; if it omits the op, code validates it through
the same topology and appends it. A hedonic `released` flag alone never creates
matter—the character must connect completion to an authored capability.

Non-discrete matter uses a sibling relation rather than abusing contact or
inventory. `state_diff.substance_ops` records an established material's source,
destination, placement (`surface|interior|contained|room`), amount, and optional
interior/endpoint. If `source_part` is the actor part of exactly one standing
interior contact, resolve may omit the destination: merge derives the target and
enclosing structure from that onset topology before applying same-turn contact
removals. A contradictory explicit destination is refused. The resulting
`scene.substances` entry persists until a bounded remove/clear operation; code
tracks the material the fiction names but never infers one from an event label.
`amount` remains fiction-authored wording. Optional `amount_band`
(`trace|small|moderate|large|flooding`) is the only comparable magnitude, and a
partial transfer names its exact `source_substance_id` plus a qualitative
`portion`. Silence and elapsed time never evaporate every genre's matter by
one universal law, and adding one substance never automatically displaces a
different one. Drying, mixing, absorption, decay, and wash-away require an
explicit operation or a world-specific mechanic. Speech impairment is likewise
an explicit material affordance, never inferred from amount prose.

**There is no perception model here either.** Each declared element becomes its
own percept through its own hearing/sight/concealment gate (`speech_percept`,
`act_percept`, `crossing_percept`), carrying the exact quote body, the
intent-free `observable` surface and the declared tone; `Percept.order_key`
holds the Director sequence's declared order, so chronology is a FIELD rather
than a repair pass. `speech -> turn -> speech` cannot become
`turn -> speech -> speech` because nothing between the declaration and the
rendered view is free to rewrite it, and delivery metacommentary ("the words
reach you clearly") cannot be produced because no stage writes prose about the
filter. The strip-and-reinject machinery that enforced this over model prose
(`_strip_onset_rendering`, `_inject_onset_sequence`, `_inject_visible_actor`,
`_inject_action`) is dead code kept pending removal — `docs/UNBUILT.md` §1.45.

Interpret reconciliation counts `tone` and `observable` as declaration-bearing
channels. A gesture/delivery already represented there is not appended later
as a redundant repair action, which otherwise creates a second competing
chronology before perception begins.

It also emits structured observations for appraisal. These are re-derived from
each final rendered view (`composer.observations_from_render`), never assembled
alongside it, so the second representation cannot widen the first's information
budget: it cannot reintroduce raw event intent, private tell grounds, unknown
identities, or another body's internal state.

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
unprompted exchange between two characters impossible. With that narrowed, `max_micro_rounds` is what actually bounds an
exchange.

**The first wave is one speaker, by default.** `initial_parallel_reactors`
defaults to **1** (`story/scene.py`'s `DEFAULT_INTERACTION_CONFIG`), so the
beat opens with a single character and causality builds from there — a
character replying to another character genuinely is responding to something
they just heard, and ordering is the whole content of that. `Design.md`'s
conformance row is the authority on why: a blind wave is right about a beat
aimed at the ROOM and wrong about one aimed at a person, and the stranding the
wave was introduced to fix is now fixed where it was caused (the beat-ending
exit is gated on `commitment: "contestable"`).

Raising the knob restores exactly the old behaviour, and it is the behaviour
described here: the first `initial_parallel_reactors` speakers declare blind —
micro-perception for the whole wave is delivered only once every member has
declared, and the loop's early exits are evaluated for the wave as a whole.

The person being ANSWERED is not in the wave. Its justification only holds
when the members are reacting to the same external thing; when one is answering
another, the asker is the addressee and steps out to the next round so they
hear the answer before speaking.

Parallel in the FICTION, not in execution. The wave runs sequentially, because
`character_step` writes through `ctx`; what is guaranteed is that no member
sees another's output while deciding.

This exists because the early exits end the **beat**, not the round, and the
commonest of them fires on any declared act with a target — a hug returned, a
hand on a shoulder. With the addressed character queued first, that stranded
everyone else: 153 of 196 beats with two or more reactors left at least one
never called at all. A character who never ran has no appraisal, so no drive
strain from a beat aimed at them, and no memory of having chosen to stay quiet.

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

The decision contract is large, but latency work must not narrow the mind it
describes. The provider receives a constraint-equivalent JSON Schema with
annotation-only metadata removed; local validation still uses the complete
Pydantic model. The name-bearing identity line is placed immediately before
the output shape so the long authored contract before it is a reusable cache
prefix. Immutable per-turn reads (scene, transformations, simulation clock,
all-cast name map and unanswered-question history) are reused through
`ctx._extra.character_turn_snapshot`. Memory-context construction runs under a
parent-copied context while the main thread assembles independent lore,
relationship and frame projections, and is joined before anything
memory-dependent is built.

`considered_responses` and the compatibility fields `observations_used`,
`speech`, `action` and `actions` remain in the production wire contract. Their
removal is an experiment only (`wire_variant="compact"`), measured by
`tools/character_wire_ab.py` across cognition, agency, knowledge-firewall and
synthetic social-memory situations; an absent downstream reader is not
evidence that deliberation scratch does no cognitive work.

`self.embodiment_capabilities` contains conditional facts hidden from ordinary
observers but necessarily known by their owner. When a chosen completed process
has an established non-discrete output, `material_effects` carries that
actor-owned physical consequence beside the public sequence instead of leaving
it trapped in private appraisal/hedonic state.

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
lexically similar move is a review TRIGGER, not proof of a defect — an invited
continuation, deliberate emphasis and an in-character riff all look the same to
it — and since `e629d60` the review costs nothing, because there is no longer a
review call to pay for. The verbatim, semantic-move and spent-intention
findings are RECORDED on the step as `repeat_correction` / `move_correction` /
`intention_correction`, each raised as a warning, and the beat stands. The
second character call they used to buy (and the `move_repeat_screen` that
gated it) is gone: repetition is weak output, not broken output, and a negative
constraint gives a mind that has run out of moves nothing but a rephrasing.
Two consumers read the records — `affect._advance_intent`, where a `progress`
claim on a repeated move does not advance the goal, and `_unbidden_trigger`,
whose `barren_goal` reason offers the mind a contrasting memory instead of a
further prohibition.

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

After the model adjudicates contested outcomes, the engine settles every player
sequence phase against the onset scene. A dependency that did not complete, a
missing participant, or a required contact that was not standing makes the
phase `blocked`; otherwise it is `executed`, `attempted`, or `realized`.
These engine-authored `sequence_dispositions` govern perception and event-order
admission. Specialists associate each phased change with its source event in
`state_diff.phase_sources`, keyed by channel path or list index. The causal
floor drops changes belonging to blocked phases and consumes the sidecar before
persistence; it never tries to infer a prose-to-state correspondence.

The resulting chronology is structural: root/onset player events, character
reactions and interaction, then surviving player continuation/completion
events. Ending contact also invalidates a standing pose only when its support,
constraint, relation, or detail was contact-bound; non-contact spatial facts
remain standing.

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
Completed `character_material_effects` are separately source-locked and
topology-validated after resolve, so Director omission cannot erase an output
the acting body itself declared.
Body arrangement is the third spatial grain: positions choose the room,
stations choose the anchor/nearness, and `poses` records posture, support,
relative arrangement, and physical constraint. A touched pose is a complete
snapshot rather than a partial merge, so obsolete `beneath`/`pinned` fields do
not survive a later rise. Pose changes have their own manifest/audit category.

A station is decoration on the position ledger, never a mover. `stations.at`
names an anchor and the anchor belongs to a room, so resolving it as room
membership let a threshold anchor — the back office's name for the door
through to the lobby — read as being inside the back office, and the
near-group repair then carried everyone standing near that body in with them.
Where nobody is travelling, that repair may only settle which of the rooms
the group ALREADY occupies wins, the player's above all; where the player IS
travelling the anchor is the party's destination and still names it.

A declared walk CONTINUES. A beat that says nothing about movement no longer
abandons the journey: `_travel_continues` advances the mover one edge along
the passable route (two beats for a `far`/`remote` edge), writing the leg
into `state_diff.positions` BEFORE every movement backstop so restraint, the
passable-route check and approach semantics all judge it exactly as they
judge a declared move. The leg is computed before the resolve is called and
handed to the prose author as `travel_in_flight`, so the scenery changes on
the page rather than behind it. An INTERRUPTION is what must be established,
not continuation: the Director asserts it in `travel_interrupted`, under a
deterministic floor (no passable route, carried, already arrived) it cannot
argue with. `out['travel']` records what happened and `persist/commit.py` retires or
keeps each standing `scene.approach` record from it, so the ledger and the
committed position are written from one answer.

Both Director stages stay ONE step each and fan out inside themselves
(design note 19). This is the only Director path; there is no monolithic
sheet and no setting that returns one. A deterministic dispatch keyed on the stage author's own ruling — a
`ledger_notes` line naming the hand or one of its channels, or a
`changes_asserted` entry in one of its categories — decides which hands run,
and the scene-state gates compute each addressed hand's channel SCOPE
(dispatch is `bool(scope)`; a hand the ruling never reached has an empty one,
and at interpret only the notes address, since that view carries no
manifest), the stage model runs with a lean instruction sheet (same role, step key, schema, and
payload), and each dispatched specialist — `body`, `social`, `contact`,
`objects`, `spatial`, `offscreen`, with sheets assembled per beat from its
granted channels' chunks (`prompts.specialist_prompt`) — reads the finished
beat and owns its channels. The specialist calls never stream (structured
output only; results merge in canonical order, never completion order; a
failed call costs exactly its own channels; Aborted propagates). They run in
PARALLEL by default — they hold disjoint channels of the same finished beat
and have nothing to say to each other, so the beat costs its slowest hand
rather than their sum. `director_fanout_mode: sequential` runs them one at a
time for a provider that will not take concurrent requests; it is not a
fallback to the removed monolith, since the same hands run with the same
scopes and assemble in the same order, and a beat still dispatches only
the hands the ruling addressed, each a 1-4k sheet against the single sheet's
~21k. The SAME specialist definitions serve both stages: resolve's
instances read the resolved prose and own `state_diff` channels;
interpret's read the player's structured declaration (never the raw input)
and own the same channels of `state_assertions` (contact under
`contact_assertions`), merged BEFORE the deterministic validators. Assembly
is ownership per granted channel; every deterministic seam above — the
movement backstop above all — judges the merged result. Scope gates fail
open per channel, a single backstop reports any channel that ships content
outside every served scope through `tell_director`, a note keyed by a name
no hand answers to is reported as unrouted rather than guessed at, and the
dispatch/scope record (per hand: `addressed_by`, `gated`, `scope`; granted
vs served vs produced overall) persists on the step under `orchestration`.

### `background_react`

Unconditionally present in the plan but internally self-gating, with two paths chosen by the per-chat `background_config` (`story/scene.py`) key `scene_life`. Three rules apply to both paths since 2026-09-02 (the identity family, `AGENTS.md` § Background presence reactions): a debt does not cross a doorway (`demand_reaches(..., aimed=)` — an owed reply, aimed by nobody now, needs the presence and an authored mind in one room; the player's words naming the person, or the body's own act, ride the hearing channel as before), a name in a line aimed at someone else is a subject and is not voiced once the beat has a precise addressee, and a line aimed at one person is answered by one person (`_one_answer_per_line` demotes a second answer to a background claim). The stage is also non-fatal: a provider failure inside a voice call is a warning and silence (`_voice_call`), never an aborted turn — the beat was resolved before this stage ran, and only a causal stage may abort. The Director's own `intended_target` on the player's lines is the third source of the address channel, after the flow refs and the structured fallback, so "market trader" binds to a present body when interpret marked no address. The stage's upstream half lives in `director_resolve`: `present_figures` shows the prose author and the `objects` hand the charter bodies standing in the beat's rooms with their posts, and `_bind_minted_entities_to_present_figures` rebinds a minted person a listed body already is.

- **`off` (default) — one presence.** `persist/commit_background.py`'s `pick_background_reactors` is a deterministic, LLM-free check that returns `[]` for the large majority of turns (no salient, un-voiced named background presence this beat), in which case this stage costs nothing. It is the function `agents/background.py` actually calls, with `cap=background_config.max_reactors`; `pick_background_reactor` (singular) is only a convenience wrapper that takes the top pick. Both are re-exported from `persist/commit.py`, which is why older notes name that module. Only when it picks a name does one small, stateless LLM call decide whether that person reacts and, if so, a single line and/or brief action for this beat only. `max_reactors` defaults to 1 and is capped at 3, so "one presence" is the default rather than an invariant.
- **`ambient` / `full` — the scene manager.** One batched call voices every managed presence in the room at once (roster from `managed_presences`, capped by `max_managed`), partitioned by `spatial.ambient_scope` and filtered per presence by a `hear_level` audience map. The plan label changes to "Scene life · manager (ambient|full)" accordingly. Voicing is batched; **writing is not** — each attributed entry is routed to its own record at commit, which is what keeps one call from becoming one shared mind. Design and its still-unbuilt half: [`BACKGROUND_LIFE_DESIGN.md`](../design/BACKGROUND_LIFE_DESIGN.md), [`UNBUILT.md`](../UNBUILT.md) §6.1.

Charter-linked presences are orchestrated by this same stage but excluded from
the shared manager payload: their own condition, temperament, relationships and
news are divergent private context. Each receives an isolated presence call.
The call also receives that presence's last three verified addressed/reply
fragments, allowing a powerful scene-life model to continue the local exchange
without receiving an unbounded history or another body's private context.
Its packet includes capped exact `action_instances`; an optional
`charter_act:{act,other}` echo lands only when it exactly matches that
engine-authored allowlist and `charter_author.authored` still licenses it.
Prose is never parsed into state. Off-screen departure needs no handoff because
the call only authored conduct against the live Charter body. Promotion is the
only ownership transfer and makes the registered character the exclusive owner
of cognition and motion.

Neither path grants a stateless presence its own persistent memory, psychology,
or mind-models. A Charter presence is the explicit exception in source, not in
ownership: the packet is a read aperture over state Charter already owns.
Promotion transfers that state to a real character.

Its output is merged into `perception_outcome`'s dialogue processing rather than mutating `director_resolve`'s already-persisted step/variant, so a rerun/resume from this point onward stays consistent with what was actually rendered.

### `perception_outcome`

Filters the resolved event into separate observer experiences. This output feeds both player narration and character-specific memories.

Concealed actions are sentence-level redacted per-perceiver by
`_redact_concealed_from_event` — sentences referencing a concealed actor
(identified by structured name, not prose matching) are withheld; overt
sentences survive. **The function lives in `agents/perception.py` and this
stage does not call it.** Its only production caller is `story/scene.py`'s
`recent_events_for_observer`, which redacts STORED event rows as they are
loaded into a character's context on a later turn — so the boundary it holds
is the historical one (Pattern 4 in the debugging map), not this turn's
outcome view. This turn's concealment is decided by the composer, per percept,
before any prose exists.

`agents/common._delivery_ok` consolidates containment, awareness, sight
(including rear-arc/`behind_sources`), and hearing (with proximity). It is
called from `agents/loops.py`'s two micro-round deliveries and nowhere else;
perception and the composer re-derive the same four questions from the same
primitives. Two families of gate, and the risk that they drift is registered
in [`UNBUILT.md`](../UNBUILT.md) §3.8.

Observer scene projections include only visible bodies' pose snapshots plus the
observer's own. These are authoritative: visibility alone never licenses a
default standing or “before you” relation. A body without a snapshot appears in
`pose_unknown`. Pose snapshots are owner-keyed, so their owner-bound posture,
constraint and detail fragments are normalized into that owner's own view
before becoming percepts; exact self names in any body's pose become
second-person references. An explicit third-party name stops pronoun rewriting
within its local fragment, avoiding anaphora guesses. Episodic rendering then
converts those same admitted references to first person. In player-facing
views, full authored appearance is scoped to
discovery, re-encounter, explicit examination or a structural visible change;
an attire change renders as its delta rather than reissuing the wardrobe. NPC
views do **not** share that presentation compression: every character call
receives complete visible body/attire strings for every other person. Only the
NPC observer's own body/attire string is omitted from perception, because its
updated card state and `self.attire` already supply that same fact in the call.
An authored beneath-surface becomes eligible when its region is first
uncovered. That eligibility is durable across unrelated later wardrobe changes;
ordinary coverage still hides the surface. Bare-surface phrases are state and
must never be stored as garments.
Active sensations are never presentation-compressed in either view: sustained
touch, pressure, motion, temperature and contact actions remain current bodily
input on every beat they remain true. Their stable keys still prevent duplicate
percepts and an unchanged sensation alone still does not mint an episodic
memory.
This matters at the memory boundary because witnessed episodic memory is formed
from this output, not repaired after it.

Character declarations are merged from both behavior stores before source and
action projection: ordinary interaction results and contested-beat reaction
results. Dialogue already used both; the physical act beside a reactor's line
must use the same merged declaration or the narrator receives a disembodied
voice and is forced to guess the missing motion. Every distinct overt action
in that merged sequence is projected as its own event. An actor-keyed
"last action" summary is not equivalent: it turns a multi-motion response into
a terminal pose and silently removes conduct that the Director already
resolved. Speech and action are rebound into one stream from the original
declaration sequence; `dialogue_log` proves which exact lines landed, but its
row order is not allowed to regroup the beat. When an action structurally
targets the observer, a possessive body reference following that observer's
explicit name remains attached to the observer during second-person rendering
(`Alice's back ... her hands` becomes `your back ... your hands`), without
rewriting an actor's explicit `her own` body. A bounded language-pack list of
anatomical modifiers covers `her injured lower back`; naming another body ends
that local rewrite rather than handing the new person's pronouns to the first
target.

### `narrator`

Renders the player-facing prose. Fidelity checks and player-echo stripping are
applied before the output is saved. Dialogue fidelity is bidirectional: every
quote delivered in the player view must survive verbatim, and every quote in
the narrator draft must already exist in that view. An extra invented line is
an enforceable correction, even when all required lines also survived.
Standing sensations remain available as bodily evidence, but the composer's
plain "X registers Y" wording is a sensor ledger rather than story voice. If a
draft copies that construction in any ordinary inflection (`registers`,
`registered`, `registering`), or copies the `steady pressure / shared warmth`
list around it, the bounded craft screen asks for one direct, integrated
rendering instead; unchanged sensation may also remain implicit. Dialogue
chronology is scored by complete quoted spans: an echo-stripped short player
line cannot be mistaken for the prefix of a longer NPC line.

### `narrator_extra`

Planned only when the chat has other human players *stationed in this frame*
(`_chat_has_extra_players`; a co-player in a different frame is not in this
scene), and only on a normal turn — `establishment_plan()` is a fixed five-step
list, so turn 0 never carries one however many players are attached. Each extra
player needs its own perceiver and its own render of what *they* saw.
Registered like any other stage, and together with `narrator` it forms the
`_PRESENTATIONAL_TAIL` — rerolling either re-runs the remaining tail rather
than the whole turn.

It does **not** yet carry the primary narrator's consciousness gate or its full
fidelity payload ([`UNBUILT.md`](../UNBUILT.md) §3.4, S3-A6).

### `commit`

`commit_all` first prepares the exact post-turn scene plus all lore and memory embeddings without holding SQLite's write lock. It then invokes every durable domain inside one outer transaction under a per-turn idempotency lock:

1. transit sweep — first, because it mutates the prepared scene (timed
   arrivals, engine notices) that the scene domain then persists
2. scene and simulation clock — the clock's `elapsed_seconds` is charged
   by `beat_end_elapsed`, and `_advance_day_cycle` then derives the hour
   of the day and the phase from it (`world/day_cycle.py`): `scene.
   day_phase` and `simulation_clock.{anchor_hour, day_length_hours,
   hour_of_day, phase}` are written here, `scene.time_of_day` moves to
   the phase's name once the clock has left the phase the Director's
   last label named, and a declared label the clock is not in re-anchors
   it with a warning. A story whose opening named no readable time has no
   anchor and none of this runs
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

A failure in any domain aborts immediately and rolls back all earlier writes from that turn. Two things run *after* the primary transaction, both because they may call an LLM and neither can corrupt a committed fact: character autobiographical consolidation (a reconstructible derived cache) and autonomous background-to-cast promotion (additive and forward-only — the new character becomes step-eligible next turn). A failure in either is a warning. Consolidation is additionally OUT OF BAND (`commit.schedule_memory_consolidation` → `core/jobs.py`, beside the offscreen ticks): measured live, the first consolidation of a chat spent 29.5s of a 45.8s commit stage on one `utility`-role LLM call inside the player's wait. The job is deduped per chat, abandonable between characters, silent-per-character on failure, and cooperatively cancelled by `restore_checkpoint` so a rolled-back turn does not land a summary computed from rows that no longer exist.

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
- `_assert_plan_materialized` checks two things, and only two: that every
  planned key is present in `ctx`, and that its step has **exactly one** active
  variant. It does not inspect the content, so "a valid result" overstates it —
  a stage that returned a structurally poor dict passes.
- **A single-step reroll skips that check entirely.** The `only_key` branch of
  `_run_pipeline` runs the one step and yields `done` without calling
  `_assert_plan_materialized`; the invariant is asserted on the two whole-plan
  paths (establishment and normal) only.

## Portable diagnostic traces

Completed stage outputs already live in immutable `steps` / `variants` rows.
`persist/pipeline_trace.py` can export that record as a versioned, canonical JSON
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
| Correct turn disappears after reload | `persist/commit.py`, checkpoints, or database restore |
| Reroll leaves mixed old/new state | stale-step propagation, active variants, or resume logic |
| Character knows a concealed action from a prior turn | `recent_events_for_observer` in `story/scene.py` (Pattern 4), which is the one production caller of `_redact_concealed_from_event` in `agents/perception.py` |
| Character remembers something from a rerolled turn | `current_turn_idx` cutoff in `mind/memory.py` `search_memories` (F1) |
| Character keeps recalling a belief they have since revised | `reconcile_inference_confidence` in `mind/memory.py`, `belief_credence` in `mind/theory_of_mind.py` |
| Character theorises lucidly about others while in agony or ecstasy | `cognitive_absorption` in `mind/psychology_runtime.py`, `absorbed_cap`/`formation_floor`/`sheet_capacity` in `mind/theory_of_mind.py` |
| Character treats its own guesses as established fact | `active_hypotheses` (`i_suspect` keys) in `agents/character.py`, ACTIVE HYPOTHESES block in `llm/prompts.py` |
| Background dialogue names an unrecognized character | `_present_others` recognition gate in `agents/background.py` (F3) |
| Narrator reports a door state in an unseen room | `_visible_portal_states` visibility gating in `agents/narration.py` (S3-A5) |
