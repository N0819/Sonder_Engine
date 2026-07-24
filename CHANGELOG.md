# Changelog

## alpha3.2.3 — Provider rows are not dicts (hotfix)

**alpha3.2.2 is broken; use this instead.** Two helpers added in that release read
the provider record with `.get()`, but `provider()` returns a `sqlite3.Row`, which
supports subscripting and has no `.get()`. Every request to an OpenAI-compatible
provider -- which is every provider except a direct `kind="anthropic"` connection --
raised `AttributeError` inside request construction and surfaced as an opaque
`all providers failed` turn error. The default configuration hits this on the first
turn.

The dict-based tests all passed because they never used a real row. Provider fields
now go through one accessor that handles both `sqlite3.Row` (subscript, `IndexError`
on a missing key) and plain dicts, and the regression tests build a genuine
`sqlite3.Row` -- including a row missing a column, which must degrade rather than
raise.

Found by running the demo, not by the suite; the suite has been taught the case.

## alpha3.2.2 — Say who serves you, and what it costs

Provider-layer fixes from a user issue report, plus the deterministic half of the
pronoun-consistency work the alpha3.1 audit left open.

### Fixed
- **Unreachable output budgets locked callers out of models** (`providers.py`,
  `agents/director.py`, `agents/narration.py`). Four stages -- the three director stages and
  the narrator -- requested `max_tokens=200000`, a figure no model can produce but which
  providers still act on: a pay-per-use aggregator reserves credit against the requested
  maximum, and a model is rejected outright when input + max_tokens exceeds its context
  window. An unreachable ceiling therefore made models silently unusable and demanded a
  balance sized to an output that could never happen. Every request is now clamped in
  `providers.py` at both `chat_complete` entry points, so no single call site can
  reintroduce it, and a test walks the AST of every module to catch one that tries.
- **Claude reached through OpenRouter never cached** (`providers.py`). Prompt caching was
  implemented only on the `kind="anthropic"` branch. The caching is Anthropic's, not the
  aggregator's -- so Claude routed through OpenRouter took the OpenAI-compatible branch,
  sent a plain-string system message, set no cache breakpoint, and cached nothing. Since the
  per-role system prompt is the large byte-stable prefix repeated on every call for that
  role, this was the single largest cache win available and it was being missed entirely.
  Anthropic models on a cache-passthrough aggregator now get the cache-marked content-part
  form; every other provider keeps the plain string it expects.
- **Caching could not be verified** (`providers.py`, `logging_utils.py`). `_log_usage` read
  only the OpenAI-compatible dialect, so an Anthropic response's `cache_read_input_tokens` /
  `cache_creation_input_tokens` always reported zero -- making "caching is broken" and "we
  never looked" indistinguishable. Of the eight response paths (2 dialects x streaming/not x
  sync/async), only two logged anything; neither Anthropic path did. All eight now report,
  both dialects are read, and cache writes are logged separately from reads -- writes with no
  subsequent reads is the signature of a prefix that isn't stable across calls, which costs
  more than not caching at all.
- **Pronouns flipped mid-scene** (`agents/common.py`, `agents/character.py`,
  `agents/perception.py`, `prompts.py`). The alpha3.1 prompt rule reduced but did not
  enforce cast-pronoun consistency. A deterministic floor now flags a clause that opens with
  exactly one known cast name and then uses a pronoun from a different paradigm, and drives
  the narrator's existing correction-retry. Deliberately narrow -- a false positive costs a
  full rewrite -- so it stays silent on ambiguous referents, quoted dialogue, plural "they",
  and neopronoun sets. Character agents now receive the pronouns of people they already
  know (recognition-gated, so a stranger's are absent), and perception receives them for
  everyone except a character under an active disguise, whose canonical pronouns are part of
  the identity the disguise conceals.

### Added
- **Choose which upstream provider serves an OpenRouter model.** One OpenRouter model id is
  fronted by several upstreams (Anthropic direct, Amazon Bedrock, Azure, Google Vertex,
  third-party hosts) whose output quality *and* prompt-retention policy differ -- so this is
  a privacy control, not only a quality preference. API Connections gains allow-only and
  blacklist lists, "only providers that don't retain or train on prompts", "never fall back
  to another upstream" (pinning alone still silently reroutes when the upstream is busy),
  and a preference sort. Because the slugs are not guessable,
  `GET /api/openrouter/endpoints` lists the upstreams actually serving a given model with
  their retention policy shown, and the picker fills the lists from it.
- **Windows double-click launcher** (`Start Sonder.bat`) — creates a virtual environment and
  installs dependencies on first run, then just starts the server and opens a browser on
  later runs. Contributed by **DonBananas** (PR #5), along with README setup instructions.
- **A configurable response limit.** The output-token ceiling is now a setting
  (`PUT /api/max_output_tokens`, shown in API Connections) defaulting to **20000** --
  comfortably above the longest single output the engine produces, a narrator turn. Read per
  call, so a change applies on the next turn without a restart, and coerced into range
  rather than rejected: it gates every LLM call, so a bad value must degrade to a usable
  number instead of breaking generation.

### Notes
- On Claude Opus, three role prompts (`perception`, `director_interpret`, `character`) sit
  below Anthropic's 4096-token minimum cacheable prefix and will not cache however correct
  the breakpoint is. Sonnet-tier minimums are lower and unaffected. Consolidating those
  prompts is a prompt-architecture decision, not a code fix, and remains open.
- `demo/enterprise_d_v3 Alpha 3.2 Dev/` holds a salvaged partial of a destroyed v3 run; see
  its README.

## alpha3.2.1 — The hallucination hunt (coherence fixes from live play)

A run of the alpha3.2 features in **Elevator Adventure** (and its branches) surfaced a
cluster of coherence bugs, almost all the same shape: **prose asserts a state or a line the
structured layer never recorded, so a downstream stage re-hallucinates it.** Closed at the
earliest stage in each case, with deterministic floors where a prompt alone had proven
unreliable.

### Fixed
- **Branching orphaned character positions** (`app.py`). After branching a chat, Dr. Moon
  (and the player) resolved to no room — rendered as *"unspecified location"* on the next
  turn. Characters are projected into `world_entities` keyed by their name, and the branch
  ID-remap regenerated a fresh opaque uid for *every* entity id — including the character
  names — so the `scene.positions` key was rewritten off the character's stable identity.
  The remap now protects character / player-persona identities; object ids remap freely. The
  four already-corrupted branches were repaired in place.
- **Director invented player speech** (`agents/director.py`, `prompts.py`). A wordless cry
  *"AaUaa!"* became a fabricated player line in `dialogue_log`. The deterministic guard that
  already drops director-invented lines for cast now covers the **player**, and the
  "write a plausible line" license is scoped to exclude the player.
- **Cross-room object teleport** (`prompts.py`). Retrieving supplies the player placed in the
  lobby, the Director slid the objects into the actor's room (leaving their anchor behind) so
  she "reached across" to a desk in another room. New **OBJECT REACH & RETRIEVAL** rule: an
  actor must move to an object in another room and carry it back, not teleport it to
  themselves.
- **Perception invented player speech** (`agents/perception.py`, `agents/common.py`). Even
  with the director guard, the perception LLM fabricated a player line in views (echoing a
  past utterance, or laundering one from `resolved_event` prose). A **dialogue-fidelity
  floor** now runs on **every** perceiver view: any quote presented as speech whose body is
  not a line actually spoken this beat is dropped — while muffled/partial **fragments** of
  real lines and quoted **environmental text** (signage like *CONDEMNED*) are preserved. The
  upstream root is closed too: `resolved_event` prose is held to the same speech-authority
  rule as `dialogue_log`.
- **A spent effect kept coming back** (`prompts.py`). The protective runes died at turn 17,
  but the elevator room's `desc` was frozen mid-event (*"flicker weakly with dying
  blue-white light"*) and re-rendered every turn. New **ROOM DESCRIPTION FRESHNESS** rule:
  update a room's desc when a feature it names terminally changes. Stale descs repaired in
  the live chats.

Perception-layer design assist by the Fable model. +~25 regression tests; full suite 1122
passed.

## alpha3.2 — Minds that switch off, authors who direct, and characters who want things

A run of the **Elevator Adventure** and **Enterprise-D** demos exposed a cluster of
agency and information-barrier gaps. This release closes all of them: an unconscious mind
now perceives and acts like one, the player can author the world (and other minds) without
puppeting them, characters can set aside goals the world has closed, and — the root cause of
passive NPCs — every character can finally be given a **drive** and standing goals.

### Fixed — information barrier
- **The unconscious perceived everything** (`agents/perception.py`, `scene.py`, `agents/common.py`,
  `agents/runtime.py`, `agents/loops.py`, `agents/character.py`, `agents/narration.py`,
  `agents/director.py`, `prompts.py`). Found live: a knocked-out player received a full
  first-person *sighted* perception view every turn (she "saw" a lobby reveal while
  unconscious). Consciousness existed nowhere as state. Now a Director-authored `awareness`
  world-condition (level `unconscious|sedated|asleep|dazed`) — reusing the whole conditions
  machinery, so no schema/checkpoint work — gates the receiver: a non-awake mind is **excluded
  from the perception LLM call and every deterministic backstop** and gets only a content-free
  residue (which becomes its fragmentary memory of the beat); it is dropped from reactor
  planning and its character step no-ops. Born at `director_resolve` (prompt clause + a
  high-precision, grammatical-subject deterministic floor). Narrator renders an honest fade-out.
  Fail-open (absent condition ⇒ awake). *The floor was tightened post-release-candidate after a
  live false-positive that flagged a conscious first-aider standing over the fallen character.*
- **Observer views double-named and duplicated the actor** (`agents/common.py`, `agents/loops.py`,
  `prompts.py`). Since alpha3.1.2 the delivery used a full-sentence `observable` surface, so the
  backstop produced "Dr. Moon Dr. Moon tilts…" / "Dr. Moon The flashlight beam moves…". Fixed
  with a verb-first predicate contract + a deterministic composer, and content-token overlap
  replacing the exact-substring dedupe so the model's paraphrase of a beat is not re-injected.

### Fixed — authorship & agency
- **No authorial channel; the player puppeted NPCs** (`agents/director.py`, `agents/character.py`,
  `schemas.py`, `prompts.py`). When the player authored a character's interior ("Dr. Moon
  remembers she has her smartphone"), the Director enacted it as truth, pre-scripting her. A
  mental-verb beat whose grammatical subject is a sheeted cast member is now rerouted to an
  **offer** handed to that character's own agent (which decides in-character), and dropped from
  the resolved sequence. New action-element field `mode`.
- **Player-scheduled future events were silently dropped** (`authored_events.py`, `commit.py`,
  `agents/director.py`, `schemas.py`, `prompts.py`). "The elevator crashes next turn" vanished,
  forcing the player to re-narrate it. Now captured in `flow.scheduled_assertions`, stored in
  `scheduled_events` (kind `authored_event`), delivered when due with a resolve-now contract,
  and **re-queued rather than dropped** (bounded) via omission-detection if the resolution fails
  to enact them.

### Fixed — proactive characters (the passivity root cause)
- **`drive` and standing goals were authored nowhere** (`prompts.py`, `static/js/editors.js`,
  `character_schema.py`, `agents/character.py`, `commit.py`). Diagnosed from the Enterprise-D
  demo: NPC Captain Picard was passive because the decision procedure derives proactive wants
  from `drive` + standing intentions — but character **generation omitted `drive` entirely** and
  the **card editor had no drive section**, so every generated/edited character ran on an empty
  drive and no goals and could only react. Generation now emits `psychology.drive` (with guidance
  that a blank drive makes a character passive and that expression must drive *initiative*) and
  requires 1–3 standing goals; the editor gained a Drive section; and authored
  `initial_state.goals` now actually reach the agent as standing intentions (always in context,
  seeded into the live list at commit so they evolve via `intent_ops`).
- **Goals the world had closed steered forever** (`affect.py`, `prompts.py`). A character could
  observe its objective was now impossible (every corridor sealed) yet keep serving it. New
  guarded `nonviable` intent op sets a goal aside (engagement revives it); plus an
  *urgent-situational-fact* rule so the obvious high-salience action (a dying person in front of
  them) always appears in `considered_responses` — "the option must exist; the refusal may be in
  character."

Design by the Fable model; +50 regression tests across the areas above; full suite 1108 passed.

## alpha3.1.2 — Observers see the act, not the intent (perception stops leaking purpose)

Found in a live **Elevator Adventure** run: as Hinami carved protective runes beside
Dr. Moon, Dr. Moon's perception views were told the runes' *purpose* ("runes of slow
and soften"), Hinami's private nature ("divine heritage"), and even a purely mental
beat ("remember the rune crafting *her mother taught her*"). An observer should see
claws, frantic scratching, and a glow — never what the magic is *for*.

### Fixed
- **The deterministic perception backstops leaked action intent** (`agents/perception.py`,
  `agents/loops.py`, `agents/common.py`, `schemas.py`, `prompts.py`). The perception
  prompt was already correct (*"never add meaning, name intent"*) and the LLM obeyed it —
  its prose was clean. The leak was entirely in the deterministic delivery paths
  (`perception_act`, `perception_outcome`, and `loops.py` micro-perception), which pasted
  the director's raw `attempt` strings — the actor's own intent-laden framing — straight
  past the filter into every observer's view. The perception LLM was also *handed* the
  intent in its input (`intended_effects` plus the loaded `attempt`/`action_attempt`).
- **Every action element now carries an intent-free `observable` surface** — what a
  bystander literally sees/hears, no *why*. `norm_sequence` computes the contract
  centrally: a purely mental act (verb like `recall`/`decide`, or a mental leading verb
  when `verb` is unset) gets `observable ""` and is delivered to **no one**; a physical
  act uses the director/character-authored surface, falling back to `attempt` only for
  paths the field does not yet cover (so ordinary actions do not regress). All three
  delivery paths render `observable` via a single `observable_action_text` helper and
  skip mental beats; the perception LLM payload is projected through
  `_observer_facing_sequence`, which strips the `intended_effects`/`asserted_effects`
  ledger and drops mental beats — so the filter never even *receives* the intent (the
  pattern the engine forbids for character agents). Director and character prompts now
  author `observable`. +8 regression tests reproducing the Elevator turn.

## alpha3.1.1 — Memories carry their affect (valence/arousal no longer always zero)

### Fixed
- **Memory valence/arousal were never written** (`commit.py`). A character's memories
  stored the `emotional_context` *label* (from its mood) but left the numeric
  valence/arousal at their `0.0` schema default — so the memory editor's valence and
  arousal boxes always read zero. The commit path now propagates the character's blended
  **surface affect** (`active_state.affect.surface`) onto the dialogue, episodic, and
  own-action memories it forms each beat, so the numbers travel with the label they
  belong to. The read/write plumbing (list endpoint, editor, PUT) was already correct.
  Applies to memories formed from here on; existing memories have no stored affect to
  backfill. +2 regression tests.

## alpha3.1 — Resolve what you open: ruptures that land, narration that doesn't repeat itself

Driven by a fresh **40-turn Star Trek audit run** (`demo/enterprise_d_v2/`, graded
**C+** by the Fable critic, up from the prior D+). The prior run's two CRITICALs —
autonomous promotion and obligation discharge — were already fixed and confirmed
firing; this release closes the next tier, led by the central open flaw: the engine
could detect that a character *should* break and even stage the collapse, but could
not make the change actually happen.

### Fixed — interior
- **Drive rupture now has a floor** (`affect.py`, `commit.py`, `agents/character.py`)
  *(the headline)*. A rupture window used to re-extend indefinitely while the model
  quietly declined to shift — observed live as a **23-turn crisis limbo** (strain
  pinned near 1.0, the character neither transforming nor recovering). Two floors
  close it: after `RUPTURE_FORCE_AFTER` (3) turns the character prompt escalates from
  an optional "you MAY shift" to a **FORCED RESOLUTION** — passive calm is removed as
  an option, so the character must either shift *and enact it this beat* or visibly,
  costingly reaffirm the old drive; and after `RUPTURE_MAX_OPEN` (6) turns
  `commit.py` force-closes the window and pays strain below the floor, so a rupture
  the engine opened can no longer sit forever unresolved. New regression tests cover
  both floors.

### Fixed — narration
- **Player echo, done right** (`prompts.py`). The narrator no longer re-narrates the
  player's own declared action ("You <verb>…" openings) *and* no longer substitutes a
  vague placeholder for suppressed player speech ("I tell him what he needs to hear").
  It renders the weight and motion concretely, then moves to consequence — never the
  words, never a limp summary of the words.
- **Each line once** (`prompts.py`). The narrator renders each distinct declared line
  of dialogue exactly once; redundant view/interaction surfacing is not license to
  stutter a line back in a reworded attribution.

### Reduced (prompt-level; deterministic enforcement deferred)
These are probabilistic prompt rules that *reduce* a tic but do not yet eliminate it —
the 4-turn confirmation run still saw each slip occasionally. The absolute fix is a
deterministic correction-retry (mirroring the dialogue-fidelity floor), scheduled next.
- **Pronoun pin** (`agents/narration.py`, `prompts.py`). The narrator now receives
  `cast_pronouns` (each character's canonical subject/object/possessive) and is told to
  use them instead of guessing gender from a name. Cuts the flips; a mismatch-retry is
  still needed to make it absolute (confirmation still saw one "her" for a he/him
  character).
- **Ambient restraint** (`prompts.py`). A standing background sensation ("the bridge
  hums", flickering lights, a door left open) is told to be first-establishment-only
  unless it changes. Reduces the reworded-repeat tic the exact-word-run diff missed;
  not yet eliminated.

### Fixed — objective causality
- **Player-authored NPC acts belong to the NPC** (`prompts.py`). When the player
  narrates a volitional act *by* a sheeted character ("Vorne lunges for the console",
  "she sets the badge down"), the Director no longer executes it as a bare mechanical
  fact stripped of interiority — it attributes the act to the character (their motive,
  their voice) and, if it contradicts what they would choose, adjudicates it contested.
- **Being acted upon is not passive** (`prompts.py`). When the player physically acts
  ON a present, volitional character (grabs, restrains, wrenches something away), the
  resolved beat must render that character's immediate physical/emotional reaction —
  a struggle with only one side rendered is half a struggle.
- **Obligation timing** (`prompts.py`). The obligation ledger gains a narrow timing
  exception: a purely mechanical delivery (a requested report/padd) may wait one — and
  only one — beat when the current beat is an intimate/climactic close, so a delivery
  receipt doesn't walk into the middle of an emotional beat. Never applies to a demand,
  promise, or question.

### Known follow-ups (deferred to keep this release surgical)
Several audit findings need real work in the delicate director/perception/reaction
seams and are scheduled rather than rushed into a release: an `established_facts`
ledger for second-act continuity (W3), full deterministic routing of player-authored
NPC acts through the character agent's reaction (W2/W9), room-boundary scene-truth on
silent door/position drift (W10), the character-dialogue side of pronoun pinning (W6),
promotion-turn identity binding (W8), and the source-count-capped deterministic
dialogue dedupe (W4). The narrator pronoun pin and ambient restraint shipped
**partial** (prompt rules that reduce but don't eliminate the tic; deterministic
correction-retries pending). Resume-ready backlog with root causes and fix
approaches: `docs/AUDIT_FOLLOWUPS.md`; full evidence: `demo/enterprise_d_v2/findings.md`.

## alpha3.0.2 — Scrubber fixes: spoken names survive, no mangled stranger labels

Follow-on fixes to alpha3.0.1. Starting a story as strangers now actually runs
the perception identity scrubber on the player↔character views, which surfaced
two latent defects in that scrubber.

### Fixed
- **Spoken name scrubbed from dialogue** (`agents/common.py`): a name introduced
  aloud this beat (a self-introduction like `'I-I'm Hinami'`) was scrubbed out of
  what the hearer plainly heard, because the quoted-span guard only protected
  double quotes (`"…"`) while the perception model routinely renders speech in
  single quotes (`'…'`). Single-quoted dialogue is now protected too, in an
  apostrophe-aware way so contractions/possessives (`She's`, `Hinami's`) in plain
  narration are still anonymized for an observer who doesn't recognize the actor.
- **Mangled unknown-actor label** (`agents/common.py`): the 5-word cap on
  `_unknown_actor_label` could slice mid-phrase and leave a dangling article or
  preposition (`"the young woman five-foot-seven-inches with a"`), which read as
  broken prose when injected inline. The label now trims trailing function-words
  so it ends on a content word.

## alpha3.0.1 — Strangers stay strangers: opt-in name recognition at quick start

Fixes a name-identity leak where a character could begin a story already knowing
the player's name they had no in-fiction way to learn.

### Fixed
- **Quick-start name leak** (`greetings.py`, `app.py`): starting a story from a
  character's greeting ("⚡ Quick start with this greeting") unconditionally
  seeded *mutual* name-recognition between the character and the player. For a
  strangers-meeting greeting this handed the character the player's name at
  scene creation, so perception legitimately rendered it into the character's
  view and mind-model from turn 1. `start_story` now takes an `already_known`
  flag (default `True`, preserving companion-card behavior); when off, no
  recognition is pre-seeded and the character starts as a true stranger.

### Added
- **"Already knows me" toggle** (`static/js/editors.js`): the character-card
  quick-start modal now exposes a per-start checkbox (default on) to control
  whether the character begins knowing the player's name.
- **"Already knows you" per generated character** (`static/js/app.js`): the
  "New story" wizard's described-character briefs gained the same recognition
  checkbox that attached existing characters already had, so a freshly generated
  cast member can also start acquainted with the player.

## alpha3.0 — Interior depth: layered goals, blended mood, earned drive rupture

The headline of this release is **moment-to-moment character depth**. Character
agents no longer act from a single goal and a single mood — they carry a layered
interior that the information barrier keeps private, leaking only through
observable behavior.

### Added
- **Three-tier goal hierarchy** (`character_schema.py`, `affect.py`,
  `agents/character.py`): a stable **core drive** (essence / expression / taboo),
  **standing intentions** that persist across turns, and per-beat **wants** the
  character forms and drops in the moment. `effective_drive()` reads the live
  drive, honoring any active override.
- **Blended, appraisal-driven mood** (`affect.py`): moods are no longer a single
  label. An OCC-style appraisal reads the model's `goal_impacts`, and the engine
  deterministically computes affect on canonical `valence`/`arousal` axes —
  blending a **surface** reaction over a slower **undercurrent** above a
  character **baseline**, with decay between beats. The model proposes; the
  engine floors and reconciles, so even weaker models produce rich, stable
  affect.
- **Calibrated tells** (`agents/perception.py`, `agents/narration.py`,
  `prompts.py`): interior state surfaces as physical cues gated per perceiver — a
  tell only lands for observers who could actually read it — with a `_recent_tells`
  ledger and an anti-repetition scrub so the same tell doesn't fire every beat.
- **Earned drive rupture** (`affect.py`, `commit.py`, `agents/character.py`): a
  major personal event can shift a character's core drive, but only through a
  two-key lock — a sustained **strain primer** plus a high-impact **event
  score** — over a deliberate detect → open-window → proposable protocol.
  Ruptures leave **scars** (`former_drives`) and respect a cooldown. Drive
  overrides are written to character runtime state only, never silently onto the
  sheet.
- **Autonomous background-character promotion** (`commit.py`, `app.py`): a named
  background presence that keeps carrying scenes is promoted to a real character
  automatically (dialogue threshold), minting a sheet and memory seeds *after*
  the primary transaction so a promotion can never roll back an otherwise valid
  turn. The manual confirm-promotion path now shares one code path with the
  autonomous one; `GET/PUT /api/auto_promote` toggles the behavior.
- **Obligation ledger** (`commit.py`, `agents/director.py`, `prompts.py`): the
  Director tracks pending social/narrative obligations across turns and flags
  overdue ones, committed as a transaction domain that rolls back with the turn.
- **Player-asserted-fact adjudication** (`agents/director.py`, `prompts.py`,
  `schemas.py`): a first-class path (with a backstop audit) for the Director to
  accept, qualify, or reject facts the player asserts in narration.
- **`demo/enterprise_d/`**: a 30-turn Enterprise-D test flight (transcript,
  feature-coverage audit, harsh-critic narrative audit, and the W1–W12
  weakness/fix findings that drove much of this release).

### Fixed
- Interior state is written only to `cstate` at commit, never to the character
  sheet, preserving the objective-truth / private-state barrier.
- Orientation refreshes in `perception_outcome` so post-move facing/left-right
  stays consistent within a turn.
- Narrator prose gained a mind-reading scrub and narrative-integrity guards
  (action-first, person/pronoun discipline, no fabricated callbacks); duplicate
  view sentences are de-duped.
- Whole-project audit sweep of bugs and rough edges surfaced during the
  Enterprise flight.

New regression coverage: `tests/test_affect.py`, `test_director_obligations.py`,
`test_background_auto_promotion.py`, `test_rupture_window_and_tells.py`,
`test_view_dedupe.py`. `make check` green: **1053 tests passing.**

## alpha2.1 — Egocentric space: bearings, field of view, and on-the-fly rooms

Builds the second layer of the physical world: every mind now has an ORIENTATION.
Objective space stays allocentric (compass bearings, named anchors); each observer's
egocentric view — left/right, ahead/behind, who is in front vs. their blind spot — is
DERIVED per observer at read time, never stored, preserving the engine's
information-barrier: "left" is a fact about an observer, not the world. Delivered as
three phases plus on-the-fly generation, a narration-craft pass, and a code-review
sweep; validated live across two taverns on weak (deepseek-v4) models.

### Added
- **Compass bearings + facing → derived left/right (Phase 1).** Adjacency edges carry
  an optional allocentric `dir` (n/ne/e/…/nw); each character carries a `facing`
  derived deterministically at commit (`infer_facing`: you face the way you walked; a
  disorienting jump clears it; turning to address someone faces them). `egocentric_frame`
  classifies a room's exits into behind/ahead/left/right, with facing authoritative when
  known — so the frame stays coherent when a character turns in place. Reciprocity is
  reconciled at merge (A→B `n` ⟹ B→A `s`; a contradiction drops both, never guesses).
  The narrator direction license now permits left/right for the matching bucket
  (previously hard-forbidden).
- **Within-room position (Phase 2).** Rooms carry optional `anchors` {id:{desc,dir}};
  entities carry a `station` {at, near}. Proximity derives into within_reach / near /
  across, plus a co-located entity's left/right. A whisper (`mutter`) now only fully
  reaches someone within reach — a fragment to the merely-near, lost across a large
  room. Station hygiene auto-heals on a room move.
- **Per-observer field of view (Phase 3) — for characters and entities, not just the
  player.** A rear-arc blind spot within a room: a co-located person behind you by the
  way you face gives NO new visual detail (a silent approach is unseen) though sound
  still carries; turning to face them lifts it deterministically. A room-layout helper
  renders a full, convincing map on a deliberate "look around". Character agents receive
  their own egocentric frame.
- **On-the-fly spatially detailed rooms.** Entering unmapped space generates a room with
  anchors, `size`, and correctly-VERTICAL stair/ladder/hatch edges — for interiors (a
  letting room) and exteriors (a harbor street) alike.
- **Narration craft (env-gated, off by default).** Sensory directionality (sound is
  directional; smell is not — gradient/presence only); a restraint rule (positioning is
  seasoning, not a per-beat inventory) with a deliberate-survey exception; a prose-craft
  directive plus style exemplars; a deterministic spatial ground-truth scaffold and an
  AI-tell craft screen with a bounded self-rewrite. A live model sweep found the tuned
  prompt + exemplars — not a bigger model — is what yields good prose on one attempt.

### Fixed
- **Stale orientation on movement beats.** Orientation was computed only at commit (after
  the narrator), so perception and the narrator's spatial frame used the prior beat's
  heading on exactly the beats it mattered. `perception_outcome` now refreshes
  orientation on the merged scene and the narrator derives its frame from it.
- **Dropped map-detail.** Mapping reliably authored within-room anchors, but the commit
  path discarded them (only the Director's causal diff built the scene). Now folded in
  pre-merge, so anchors / size / edge-bearings survive normalization.
- **`_room_notes_from_lore` crashed** when a lore entry's `keys` was a list.
- Spatial-derivation hardenings from a code review: same-anchor pairs are no longer
  mislabeled a rear blind spot; pass-through no longer guesses "ahead" when a facing is
  known; case-tolerant orientation/station lookups; the craft screen ignores banned words
  inside quoted dialogue; plus several lower-severity guards.

## alpha2.0.1 — Background presence: track declared agents of any kind

### Fixed
- `track_background_presences` captured only entities whose `kind` was exactly
  `person` or `npc`, silently dropping every player-declared agent the model tagged
  otherwise — `actor` for "two security guards", plus monsters, creatures, robots,
  spirits, drones. Those were declared into the scene yet tracked by neither the cast
  nor the background-presence system: present but inert, with no path to a reaction or
  promotion. Tracking now uses a deny-list of clearly-inert kinds (`_INERT_ENTITY_KINDS`)
  and defaults to inclusion — ambiguous kinds like `machine` stay tracked so a sentient
  robot cannot fall through, while objects, fixtures, vehicles, and locations remain
  excluded. A rare mistracked object never reacts anyway: the `pick_background_reactor`
  gate still requires it to be addressed, owed a reply, or voiced.

## alpha2.0 — Movement & space: a tracked physical world

A major release that turns the physical world into a coherent, tracked simulation
in text. Movers (vehicles, elevators, ships) are first-class; the world can be
generated, moved, nested, and destroyed on the fly, yet stays internally consistent
across a hundred turns — and no mind learns of a change except by legitimate means.
Delivered as five reviewed phases plus fixes; schema v14 → v16. Validated live,
including a two-level nested-mover journey (a rover driven into a dropship that then
flies off, carrying its occupants at both levels).

### Added
- **Transit / moving rooms.** A container entity carries `state.transit` (docked,
  sealed, in transit, arriving; hatch open/closed/locked; destination, route, eta).
  Its interior-to-exterior doorway is DERIVED at commit from position + transit
  state — sealing severs it, arriving opens a new one onto the destination —
  retro-fixing the long-standing stale-vehicle-portal bug. Occupants travel with the
  mover; nesting composes (a mover inside a mover carries at every level). Timed
  journeys schedule an arrival completed by the mechanics sweep.
- **Reconciliation seams (capture, do not gate).** Two deterministic seams ensure
  what the model invents reaches structured state instead of evaporating: the
  resolve-side seam catches a persistent physical change the prose asserts but the
  diff omits (category-aware, alias-aware; repaired by the Director itself or
  warned), and the interpret-side seam catches a player-declared place/object/event
  the interpretation dropped — unblocking "I duck into the armory and grab a rifle."
- **Normalized `room_registry`** — the cross-frame ledger of room identity and
  retirement, a projection of every scene write; structural room dedup at creation
  (two structurally-identical ships no longer collide).
- **Mechanics sweep** — one deterministic, sim-clock-advanced pass at commit for
  timed arrivals, condition expiry, and mechanical follow-through (off-screen
  evolution without a wall-clock loop).
- **Destruction** — single- and multi-book destructive cascades over the lorebook
  tree, retire-not-delete (a ruined region stays retrievable), an occupant-stranding
  guard that rolls back rather than losing people, and knowledge propagation by
  distance: awareness of a catastrophe reaches distant characters only via
  latency-gated `news_arrival`, never by direct injection.
- **`movement.mover`** (self | vehicle) resolving driver conflation; a monitoring
  subtree-walk; perception ambient-scope by nesting depth (a sealed nested interior
  cannot perceive an ancestor location); `currently_within` links tracking live
  vehicle position without mutating canonical lorebook lineage.

### Fixed
- Passable-route backstop over-blocked legitimate multi-hop moves and same-beat
  vehicle deboards; now path-finds through open doorways and recomputes derived
  edges before the check.
- Same-install chat import aborted on a lorebook `resource_uid` collision (this also
  broke re-importing the bundled demo); imported books now mint a fresh uid on
  collision. The demo story imports cleanly again.
- The mapping agent's `remove_rooms` self-heal was advisory-only and dropped, leaving
  stray duplicate rooms; it now applies deterministically at commit (guarded).

### Changed
- **Physical-world authority is consolidated** (the two-representations debt is
  resolved): the frame-scoped scene blob is the single runtime source of truth for
  live state; `world_entities` is a derived projection; `world_placements`,
  `fiction_worlds`/`fiction_locations`, and `transit_edges` are decommissioned. The
  authority model is documented in `CLAUDE.md`, `AGENTS.md`, `docs/DATABASE.md`, and
  `Design.md`, and pinned by a characterization suite (byte-identical spatial-reader
  and checkpoint/restore behavior).

### Known limitations
- **Region-scale destruction is model-dependent.** The cascade machinery is correct
  and unit-tested, and a stronger prompt plus a high-precision deterministic tripwire
  raise the odds, but a weak model narrating a razing without emitting the structured
  declaration can still leave a region intact-but-burning. Reliable detection of
  freeform destruction prose needs a semantic audit pass (deferred, to avoid a
  false-positive keyword treadmill).

## alpha1.4.3 — Perception identity firewall

Perception is the stateless filter that decides what each observer legitimately
perceives — but its `knows_identity` gate was enforced only inside the
deterministic injection helpers, never against the perception model's own
free-text view prose. A model naming a stranger ("You see Hinami…") walked
straight past the gate, and the leaked name then fed the character agent
verbatim and could be minted into durable memory — collapsing the objective /
perception / memory layers the engine exists to keep apart. No prompt even
defined `knows_identity`, so this was not limited to weak models.

### Fixed
- **Deterministic identity floor on every view.** A new post-pass
  (`_scrub_unknown_identities`) runs last on every perceiver's view across all
  three perception stages (`perception_establish`, `perception_act`,
  `perception_outcome`): any source the observer does not recognize has its
  name/alias forms replaced with a momentary descriptor — **outside quoted
  spans only**, so a name introduced aloud this beat survives verbatim
  (recognition still flips only at commit). Word-boundary, case-aware and
  possessive-aware, with a common-word-name guard. Each scrub raises a pipeline
  warning instead of failing silently.
- **Three deterministic leak channels closed.** `_unknown_actor_label` and the
  pasted appearance summaries are now name-token-stripped (persona summaries
  routinely lead with the canonical name); `deterministic_micro_perception`
  (NPC↔NPC delivery) gained the recognition gate it never had; and the no-LLM
  `_fallback_perception_views` renderer now gates the speaker name too.
- **Input-side hygiene.** When no perceiver in an action-onset call recognizes
  the player, the perception model is handed a neutral descriptor instead of the
  canonical name — it cannot leak what it was never given.

### Added
- **IDENTITY GATE in the perception prompt.** The first explicit definition of
  `knows_identity`: when false, that entity's name must never appear in the
  perceiver's view except inside a verbatim quote they legitimately heard.
- Regression coverage (`tests/test_perception_identity_gate.py`, 9 assertions)
  on the stranger-meeting fixture, including the no-false-positive guarantee
  (a recognized observer's view passes through untouched) and the mid-beat
  introduction edge case.

### Known limitations
- The floor closes **name-class** leaks deterministically; semantic identity
  leaks (species/nature, occupation, relationship history, intent attribution,
  paraphrased identity) still rely on the perception prompt and are not yet
  deterministically enforced.

## alpha1.4.2 — Greeting swipe/quick-start & greeting-capture fix

The greeting-seeded openings shipped in alpha1.4 were captured in the data model
but never surfaced in the UI, and were silently dropped by one import path. This
release wires them up end to end.

### Fixed
- **Greetings are captured on every import path.** `first_mes` +
  `alternate_greetings` were only captured on the heuristic import path — the
  **AI-reinterpret** path returned a fresh sheet with no greetings, so any card
  imported with reinterpretation on lost its alternate greetings entirely. All
  paths now capture them (shared `importers._card_greetings`).
- **Editing a character no longer wipes its greetings.** The character editor
  rebuilt `opening` as just `{first_message}` on save, discarding the greetings
  list; it now round-trips them.

### Added
- **Greetings box on the character card.** Opening a saved character shows a
  greetings editor at the top: swipe between greetings, add, remove, and edit
  them inline (edits save with the character).
- **⚡ Quick start with a greeting.** Pick a persona (and optionally attach a
  lorebook) and launch a story seeded from the selected greeting — shown
  verbatim as the opening scene, with the character's private knowledge routed
  to memory. Backed by `POST /api/characters/{id}/start` (now takes an optional
  `lorebook_id`, attached before turn 0 so the opening can draw on that lore).
- **Recover greetings from the imported card.** `POST
  /api/characters/{id}/recover_greetings` (and a "⟲ Recover from card" button)
  backfill greetings from a character's stored source card, for imports made
  before capture existed or via the reinterpret path.

### Changed
- Import dialog now recommends **AI reinterpretation for everything except
  native sheets** — SillyTavern cards and World Info are built around free-text
  prose that doesn't map cleanly onto Sonder's structured character model.
  Greetings and any embedded lorebook are preserved verbatim either way.

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
