# A leaner Director: typed beat events, and the mechanical-burden audit

Branch goal (restated): perception becomes a pure function of spatial data with
zero LLM calls; the mapping stage and Director only ever CHANGE SPATIAL DATA,
never determine perspective. This note covers the last non-spatial channel the
Director owns — `resolved_event`, the one free-prose output that perception
currently performs per-perceiver text surgery on — and audits every other
Director output for mechanical burden that code could carry instead.

**Scope constraint from the owner, binding on everything below: the Director
keeps its LLM call, unconditionally.** Deciding what happens in the fiction is
a creative job and is not in question. The axis of this note is creative
authority (untouchable) versus mechanical/bookkeeping burden (fair game).
Nothing here proposes a deterministic Director.

Method: source read against this worktree (file:line cited throughout); corpus
claims measured read-only against `engine.db` — 2,296 turns, **2,232 active
`director_resolve` variants**, all parsed. Aggregates only; anything not
measured is flagged unverified.

---

## 1. Closing the prose hole

### 1.1 What `resolved_event` is today

`DirectorResolve.resolved_event` (`schemas.py:1907`) is the omniscient prose
account of the beat. Median 667 chars, mean 763, max 2,908; median 6 sentences
of which ~5 carry no quote (quotes are separately typed in `dialogue_log`).
Because it is omniscient free text, perception must do per-perceiver surgery
on it:

- `_redact_concealed_from_event` (`agents/perception.py:3116-3181`) strips
  sentences naming a concealed actor plus bare-pronoun continuations. Its own
  docstring names the failure it cannot close: *"a paraphrase that gives the
  concealed act a fresh explicit subject ('the vial disappears into a sleeve')
  names nobody"* — and names the structural answer: *"carry the actor's id on
  the event element and redact on identity, never on text"*
  (`agents/perception.py:3133-3140`, echoed by `docs/UNBUILT.md` §3.1 D1 and
  §4.2).
- `_surface_translate_event` (`agents/perception.py:3079-3103`) fails closed
  for touch-only perceivers: because free prose cannot be security-matched, the
  ENTIRE event is replaced by *"You register motion and pressure at the contact
  surface."* — every legitimate observable in the beat is destroyed to protect
  one channel.
- The per-perceiver copies are assembled at `agents/perception.py:3476-3520`
  and delivered per-observer at `:3597`; `_inverted_motion_check` (`:2186`)
  then police-checks the perception model's views against the prose because
  nothing structural ties the two.

Every one of these is text surgery standing in for a missing field. The repo
has already diagnosed this three separate times (perception docstring,
UNBUILT §3.1, UNBUILT §4.2: "Three of this file's largest items are one
missing structure").

### 1.2 The vocabulary the engine already has

Character-declared acts are already typed and already consumed with zero LLM:

- `ActionElement` (`schemas.py:839-869`): `event_id`, `actor_id`, `attempt`
  (private intent), **`observable`** (intent-free outward surface; `""` = no
  outward manifestation at all), `visibility`, `conceal_from`, `targets`,
  `stage`, `commitment`.
- `SpeechElement` (`schemas.py:871-881`): `text`, `volume`, `tone`,
  `visibility`, `conceal_from`.
- `DialogueLogEntry` (`schemas.py:1554-1575`): the resolve-side spoken record,
  already deterministically re-stamped from the original declarations
  (`agents/director.py:4868-4957`) so the model cannot mis-tag concealment or
  volume.
- `deterministic_micro_perception` (`agents/loops.py:45-140`) proves the
  consumption pattern: per observer, per event — recognition gate (`known`),
  concealment absolute-exclusion, `_delivery_ok` (containment + awareness +
  sight incl. rear-arc + hearing with proximity, `agents/common.py`), graded
  degradation (`hear_level` full vs. muffled fragment), `observable` surface
  only, mental beats skipped. No model, no text matching, no leak surface.

The design question is therefore not "invent a typed event system" but "let
the Director speak the vocabulary the engine already consumes."

### 1.3 Proposed replacement: `beat_events`

`DirectorResolve` gains `beat_events: list[BeatEvent]`, the typed account of
the resolution, replacing `resolved_event` as the input to perception. One
element = one subject = one sentence-grain observable. Vocabulary:

| type | fields (beyond shared) | replaces in today's prose |
|---|---|---|
| `speech` | as `DialogueLogEntry` (or a ref into `dialogue_log` by index — do not state lines twice) | quoted lines restated in prose |
| `action` | as `ActionElement`: `actor`, `observable`, `visibility`, `conceal_from` | declared acts elaborated in prose |
| `outcome` | `of_event_id` (the declared act's `ActionElement.event_id`), `actor`, `result: succeeds/partial/fails/interrupted`, `observable`, `state_ref?` | "the dial turns; a chime answers" — the resolution of an attempt |
| `display` | `actor`, `observable`, `channel: visual/audible` | involuntary expressive surface of a body being acted on — "her ears flatten", "a visible tremor runs through her" (the BEING ACTED UPON IS NOT PASSIVE rule, `prompts.py:2069-2074`) |
| `world` | `subject` (entity id or `""` ambient), `room`, `observable`, `channels: [visual/audible/olfactory/tactile]`, `volume?`, `state_ref?` | environment acting: the rotor slows, the smell of solvent, the door hisses shut |

Shared fields on every element: `actor/subject` (identity — the whole point),
`room` (where it is perceivable from), `visibility`, `conceal_from`,
`in_response_to?` (event_id — see residue §1.4), `state_ref?` (see §1.5).

Corpus grounding for the shapes: five randomly sampled beats (turns 216, 332,
667, 1413, 1708) decompose completely into these five types; the non-quote
prose is per-subject expressive/environmental surface plus act elaboration in
every sample. Median burden: ~5 non-quote sentences/beat become ~5 typed
elements (p90: 11).

Perception then assembles each observer's view **deterministically**, exactly
as `deterministic_micro_perception` already does for character declarations:

- Concealment = identity check on `actor` + `conceal_from`, never sentence
  regex. The paraphrase leak class (§3.1 D1) dies structurally.
- Touch-only sources = per-EVENT exclusion (drop that source's `action`/
  `display`/`outcome` events unless channel tactile; deterministic contact
  facts supply the felt surface). The fail-closed nuke of the whole beat
  (`_surface_translate_event`) becomes a per-event filter — strictly more
  content delivered, strictly no more leaked.
- `X7` (`docs/UNBUILT.md:2678`: background-pick salience reads raw
  `resolved_event` with no concealment gate) is fixed for free — the mention
  scan becomes an event-subject scan that respects `conceal_from`.
- `_inverted_motion_check` becomes unnecessary: there is no second prose
  account for a view model to invert, because there is no view model.

The opening turn needs the same treatment: `director_establish` aliases
`scene_description` into `resolved_event` (`agents/director.py:696`), so
establish either emits `beat_events` too or an adapter types the establishing
description as `world` events (it is all environment by construction).

### 1.4 What CANNOT be expressed this way — the residue

This is the crux of the branch, stated honestly:

1. **The observable strings are still prose.** The typed layer does not remove
   prose; it *attributes and scopes* it — one subject, one channel-set, one
   room per fragment. Anything that genuinely needs a wider grain than that is
   residue. Concretely:
2. **Cross-event composition** — causality, pacing, simultaneity: "*a soft
   chime answers* from somewhere beneath the panels" (answers = caused by the
   dial-turn), "*Without looking away from his work* he speaks" (two acts
   welded into one moment). `in_response_to` and list order carry the causal
   skeleton; the weld itself — the sentence rhythm that makes two events one
   moment — cannot cross the event boundary. **This is acceptable residue
   because composition is the Narrator's job**, and the narrator already works
   from the player's gated view + `event_order`, not from `resolved_event`
   (`agents/narration.py:635-747`; it consumes resolved prose nowhere — the
   `:390` reference is a comment). The cost is real but lands in the right
   place: the narrator recomposes from a flatter account.
3. **Genuinely joint multi-subject moments** — a struggle where one sentence's
   information belongs to two bodies at different visibility levels. A
   one-subject grain rule forces a split, and a split account of an entangled
   grapple is flatter than the sentence was. A `participants: []` extension is
   decidable (deliver iff a channel to ANY participant; identity-scrub the
   unearned names) but re-creates sub-sentence surgery. Recommendation: keep
   the one-subject rule, accept the flatness, let the narrator re-entangle.
4. **Beat-level register/tone** — "his voice warm and steady over the hum" is
   expressible (`tone` on speech), but the mood of a whole beat is not an
   event. Residue; belongs to the narrator's style channel anyway
   (`style_guide`).
5. **The omniscient audit record.** Today `resolved_event` is also the
   objective archive (events row, promotion mining, salience scans). A typed
   account serves every one of those consumers *better* (see §2) — but a
   human reading the events table loses the readable paragraph unless one is
   retained. §3.5 keeps it, as a private field.

Nothing in the sampled corpus falls outside 1–5. The residue is composition
and register — narration concerns — not information. That is the strongest
available evidence that the branch thesis holds: the Director's information
content IS expressible as typed events over spatial data.

### 1.5 Reconciliation becomes a hard correctness requirement — and cheaper

Today's machinery exists because prose asserts what the diff does not encode:
`AssertedChange` manifest (`schemas.py:1883-1904`), `ReconcileOmission` /
`ResolveReconcileOutput` / `ResolveRepairOutput` (`schemas.py:1941-1963`),
the seam `_reconcile_resolution` (`agents/director.py:3309-3630`).

Measured, corpus-wide: **28.8% of beats (643/2,232) had at least one detected
omission; 1,046 omissions total; the model's own manifest was the top detector
(681, i.e. 17.2% of its 3,953 manifest entries had no diff evidence); 382
beats still carried 571 unresolved entries after the one-shot self-repair.**
Prose-vs-diff drift is not an edge case; it is a sixth of everything the
Director asserts as a persistent change.

Under `beat_events` the reconciliation question inverts:

- It **cannot become unnecessary**, because the drift risk merely moves:
  events can assert what the diff does not encode exactly as prose did. It
  becomes a **hard correctness requirement** — under this branch the events
  are what every mind perceives and the diff is what the world becomes, both
  model-authored, and a gap between them is now a gap between what everyone
  SAW and what IS. Today the narrator papers over that gap; a zero-LLM
  perception cannot.
- But the CHECK becomes structural and mostly free. `state_ref` on
  `outcome`/`world` events carries exactly the `AssertedChange` fields
  (category/subject/change + the contact/substance endpoint fields), so **the
  manifest folds into the event list and the beat is stated twice
  (events + diff), not three times (prose + manifest + diff)**. The existing
  deterministic verifier (`_manifest_items` → `_evidence_present`,
  `agents/director.py:3126, 2927`) runs unchanged over `state_ref`s. The
  detection LLM (`resolve_reconcile`, deep-audit mode) loses its remaining
  reason to exist — measured `audited: 0/2,232`, it never ran in production
  anyway. The one-shot `resolve_repair` call survives as the repair arm for
  detected gaps, unchanged.
- What is genuinely lost: the scans that read prose for UNMANIFESTED changes —
  restraint (41 detections), unconsciousness (18), destruction tripwire —
  today catch the model failing to manifest at all. Their event-world
  equivalent is weaker (an event whose `observable` implies persistence but
  carries no `state_ref` is not machine-detectable from the string). Those 59
  detections across 2,232 beats are the honest price; the keyword scans can
  keep running over the concatenated `observable` strings at reduced fidelity.

---

## 2. Consumer blast radius of `resolved_event`

Everything that reads it, and what each needs under `beat_events`. (Tests and
`tools/` drivers omitted; they follow their subjects.)

| # | Consumer | What it does with the prose | Under typed events |
|---|---|---|---|
| 1 | `agents/perception.py:3476-3520,3562,3597` (payload + per-perceiver redaction), `:3079` (surface translate), `:2186` (inverted-motion), `:3690` (quote-fidelity note) | the whole §1.1 surgery stack | **deleted** — replaced by deterministic per-observer event assembly |
| 2 | `agents/background.py:123` (`_beat_for_presence`), `:508,:713` (`_redacted_resolved_event`, manager path), `:864` | per-presence earshot slice with quote-body scrubbing | same deterministic assembly, presence as observer; both scrub functions deleted |
| 3 | `agents/narration.py` | none directly (comment `:390` only; narrator renders the player VIEW + `event_order`) | unchanged; benefits from a structured player slice |
| 4 | `commit.py:1487` (undressing pace evidence), `:1768` (`interpret_attire_notes` prose hint) | keyword scan | scan the concatenated `observable`s; same fidelity |
| 5 | `commit.py:2824` (entity copy-forward salience, S3-A8) | "does the beat prose name this entity" | event `subject` check — strictly more reliable |
| 6 | `commit.py:3421-3570` (`pick_background_reactor` salience + name mention), `:3730,:3965` (presence mention tracking) | name-mention regex over omniscient prose (X7: no concealment gate) | event-subject check, concealment-gated for free |
| 7 | `commit.py:3548,:3721` (`prepare_canon`/`settle_claims` — claim adoption inferred from objective prose) | token overlap between claim and prose | overlap against event observables/subjects; note this lane has produced 0 ratifications in production (`ratified_claims` non-empty in 1/2,232 beats) |
| 8 | `commit.py:4500,:4512` (`mapping_commit` LLM payload: `resolved_summary`, `beat_resolved_event`) | context for lore validation | feed events (or the retained private prose — §3.5); LLM consumer, either works |
| 9 | `commit.py:5714` (intention satisfy/abandon evidence pool: cited evidence must appear in beat text) | substring match | `EvidenceRef` already has an `event_id` slot (`schemas.py:1988-1998`); typed events finally give it real ids to cite — upgrade, not breakage |
| 10 | `commit.py:6312` (events row `"event"` field — the omniscient archive) | durable objective record | store `beat_events` JSON; keep the private prose alongside for the author (§3.5) |
| 11 | `commit.py:6503` (`resolve_authored_events` — did the beat enact a scheduled assertion) | text scan | scan observables; same fidelity |
| 12 | `importers.py:784` (promotion evidence pack; also `docs/UNBUILT.md:261`) | full prose of every mentioning turn | events filtered to that presence's OWN subject/earshot — fixes the documented defect where the pack is "the whole beat, not just this person's part" (`importers.py:825-830`) |
| 13 | `agents/director.py` internal: fallback synthesis `:4702-4717`, authority checks `:4325-4502`, awareness/restraint/destruction scans `:1479-2199`, reconciliation `:3309` | regex over own prose | authority checks become field checks on events (actor ≠ declarer = violation) — the five regex detectors and their retry loop shrink to structural validation; scans per §1.5 |
| 14 | `director_establish` alias `agents/director.py:696` | opening turn's `resolved_event` | establish emits typed `world` events or an adapter does |
| 15 | UI: `static/js/chat.js:954,1107` (step inspector renders `resolved_event` specially) | display | render `beat_events`; small JS change |
| 16 | `pipeline_trace.py`, `chat_archive.py` | opaque step content | no schema knowledge; replay of OLD traces still carries prose — the perception stage must keep a legacy path or traces predating the change replay against the adapter |
| 17 | Prompts referencing `resolved_event` by name across stages (`prompts.py:586,753,809` perception; `:2009-2916` resolve itself; `:3697` promote_character) | instruction text | rewritten with their stages |

Blast radius verdict: two consumers are the surgery this branch exists to
delete (#1, #2); one is untouched (#3); seven are text-matching that becomes
*more* reliable structured (#5, #6, #7, #9, #11, #12, #13); three are storage/
display (#10, #15, #16); two are LLM payloads that accept either form (#8);
one needs an adapter (#14). **No consumer needs prose regenerated from events
at pipeline time.** The narrator remains the sole prose-producer for the
player, which is where the architecture always said prose belonged.

---

## 3. The leaner Director

### 3.1 Corpus field census (2,232 active resolves)

Top-level: `resolved_event` 100%, `summary` 100%, `state_diff` 100%,
`dialogue_log` 97.1%, `dialogue_order` 96.5%, `fiction_frame` 88.0%,
`reconciliation` 84.5% (engine-attached), `changes_asserted` 65.7%,
`fact_adjudications` 28.2%, `claim_dispositions` 18.9%, `world_pressure`
11.5%, `obligations` 9.5%, `dice` 2.2%.

`state_diff` (25 fields): `time` 99.2%, `entities` 57.0%, `positions` 49.1%,
`claim_dispositions` 39.0%, `contact_ops` 21.2%, `rooms` 20.8%, `conditions`
16.8%, `stations` 16.4%, `attire` 11.6%, `inventory_ops` 8.1%, `world_facts`
5.6%, `introductions` 3.9%, `poses` 2.2%, `containment` 1.9%, `scales` 1.7%,
`remove_adjacent` 1.5%, `substance_ops` 1.3%, `remove_rooms` 0.8%,
`cast_changes` 0.5%, `remove_entities` 0.4%, `overlays` 0.3%, `weather` 0.1%,
`vitals` 0.1%, `following_ops` 0.1% (legacy rows — now engine-projected),
`ratified_claims` 0.04%, `contradicted_claims` 0%, `consequences` /
`offscreen_plan_ops` / `crowd_ops` / `telling_ops` / `courier_ops` /
`artifact_ops` / `destruction` ~0% (features newer than most of the corpus —
population is not evidence against them).

### 3.2 Removable from the MODEL's burden (ranked, with what-is-lost)

1. **`dice` in the output contract** (`prompts.py:2972`). The engine rolls
   deterministically BEFORE the call (`agents/director.py:3859-3871`), hands
   the model `dice_results_final`, then **overwrites the model's field
   entirely** (`out["dice"] = dice`, `:4540`). The model is asked to transcribe
   a value the engine discards. Remove from the contract; keep the schema field
   as engine-stamped (the `routed_to_background` precedent,
   `schemas.py:1931-1937`). Lost: nothing, by construction.

2. **`fiction_frame` in the resolve output** (`schemas.py:1915`,
   `prompts.py:2972`). Grep-verified: no code anywhere reads
   `director_resolve.fiction_frame` — the payload passes interpret's
   `flow.fiction_frame` IN (`agents/director.py:4128`) and the model's echo
   goes nowhere. It was 88% populated: the single largest fully-dead token
   spend in the contract. Remove from contract and prompt's FICTION FRAME
   output requirement (`prompts.py:2130` keeps the *reasoning* instruction;
   only the echo goes). Lost: nothing. (Interpret-side `FlowPlan.fiction_frame`
   is consumed and stays.)

3. **`dialogue_order`** (`schemas.py:1909`). Sole consumer is a perception
   payload hint (`agents/perception.py:3563`). Measured: 92.6% of the time it
   equals the speaker sequence already implicit in `dialogue_log` (72.3%
   per-line order, +20.3% first-appearance order); the residue is repeats/
   noise, and director.py already has to police it for phantom speakers
   (`:4837-4866` — a whole guard for a derivable list). Project it from
   `dialogue_log` order in code; delete the field, the prompt line, and the
   guard. Lost: the 7.4% of orderings that differ, none of which any consumer
   distinguishes. Under `beat_events`, ordering is the event list itself and
   even the projection disappears.

4. **`claim_dispositions`, stated twice.** The model emits it top-level
   (18.9%) AND inside `state_diff` (39.0%); the sole consumer reads both and
   unions them (`agents/director.py:3167-3168`). One location suffices —
   keep the `state_diff` one (it survives `_PROSE_KEYS`-style pruning already,
   `schemas.py:2968`), drop the top-level from schema and contract. Further:
   the deterministic evidence check (`_omission_subject_encoded`) is already
   the authority on whether a claim landed; the disposition's only decisive
   use is the explicit `rejected`/`deferred` override. A leaner contract asks
   for dispositions ONLY for claims not realized — absence = realized,
   verified against the diff as today. Lost: an explicit "realized" the engine
   can already prove.

5. **Explicit `world_pressure` `hold` ops.** Commit already treats silence as
   an implicit hold WITH a warning (`schemas.py:1920-1926`), so the 66
   explicit holds (of 371 total ops) bought nothing the default didn't.
   Contract change: emit `tick`/`open`/`resolve` only; a deliberate hold is
   the absence of a tick, exactly as commit already reads it. Keep the
   `must_tick_this_beat` enforcement retry (`agents/director.py:4252-4318`)
   untouched — that is the part that works. Lost: the distinction between
   "chose to hold" and "forgot", which today is already only a warning; if
   that distinction matters, keep `hold` as optional rather than required
   per-pressure bookkeeping.

6. **`changes_asserted` — folds into `beat_events`** (conditional on Half One
   landing). Today it is the model stating the beat a THIRD time
   (prose account, manifest, diff), 3,953 entries across the corpus, existing
   only because prose is unmatchable (`schemas.py:1883-1887`). As `state_ref`
   on `outcome`/`world` events it is the SAME statement made once, in place,
   and the deterministic verifier keeps running. Do not remove it before
   `beat_events` lands: it is the single highest-yield omission detector
   (681 of 1,046 detections). Lost after fold: nothing — the check's inputs
   move, the check stays.

7. **The declared mover's `positions` entry.** For a declared player/vehicle
   movement the engine is already the authority: the passable-route backstop
   writes, strips, or refuses the position regardless of what the model
   asserted (`agents/director.py:4586-4686`), `_guard_approach_is_not_arrival`
   gets the last word (`:5037`), and following is projected (`:4526`). The
   model's restatement matters only for `contested` (closed-door) beats where
   its diff assertion is the tiebreak (`:4641-4651`). Prompt simplification:
   "do not emit `positions` for the declared movement — the engine commits it;
   emit positions only for movement YOU originate (NPCs, forced moves) or to
   assert a contested crossing." Lost: nothing deterministic; slight prompt
   complexity trade.

8. **`summary`.** Three cheap consumers (`commit.py:4482,4500,6311`), 40
   words, with a truncation fallback already in place. Keep — it is genuine
   compression work a truncation does badly, and it costs ~50 tokens. Listed
   only for completeness: this is the kind of field NOT worth removing.

Not removable, examined and rejected: `state_diff.time` (99.2% populated but
duration is a judgment — a beat is five seconds or an hour and only the thing
that read the fiction knows); obligation `open`/`discharge`/`refuse`
(recognizing that a promise was made is reading the fiction — creative);
`fact_adjudications` (the 890/10/0 confirmed/contested/false skew says the
VERDICT is nearly constant, but the `landing` — on-page corroboration — is
creative work; candidate for a default-confirmed contract where only
contested/false need stating, worth a later look); everything in §3.3.

### 3.3 Load-bearing, and why

- **The `state_diff` physical vocabulary** (positions-for-NPCs, rooms,
  entities, conditions, contact/substance/inventory ops, attire, containment,
  scales, stations, poses, weather, destruction): this IS the job — objective
  causality rendered as world change. Every op family already has a
  deterministic commit validator (`crowds.apply_ops`, `carriers.
  apply_tellings`, `couriers.run_couriers`, `artifacts.run_artifacts`,
  `living_world.mint_consequences`, `offscreen.apply_plan_ops`,
  `spatial.apply_contact_ops`…) — the model proposes, code disposes, which is
  the correct division and already built.
- **`dialogue_log`**: the typed spoken record; the engine already restamps
  its delivery metadata deterministically (`agents/director.py:4868-4957`)
  and enforces every speech-authority boundary against it. Under
  `beat_events` it can become the `speech` events themselves (one statement,
  not two), but the content is irreplaceable.
- **`obligations` open/discharge/refuse; `world_pressure` tick/resolve
  content; `consequences`; `offscreen_plan_ops`; ratification** — each is the
  Director noticing or deciding something in the fiction. The LEDGERS are all
  engine-owned already (`commit_obligations` `commit.py:4770`,
  `commit_world_pressure` `:4891`, aging and must-flags computed in the views
  `:4727,:4847`); the ops are the minimal creative payload.

### 3.4 The pattern, named

Everything healthy in this stage already follows one rule: **the model
authors content; code owns every rule, ledger, and echo.** Dice, obligation
aging, pressure must-ticks, awareness exits, restraint blocking, movement
backstops, articulation stamping, dialogue re-attribution, following,
background routing — all engine-side today. Items 1-5 in §3.2 are the five
places the contract still asks the model to hand-maintain what code owns:
a transcription (dice), an echo (fiction_frame), a projection
(dialogue_order), a double entry (claim_dispositions), and a default
(world_pressure hold). They are individually small; jointly they are the
difference between a contract that reads as "say what happened, encode what
changed" and one that reads as bookkeeping with a story attached. The output
contract paragraph (`prompts.py:2930-2976`) currently enumerates ~45 shapes.

### 3.5 The chain-of-thought question — position

**The tension, stated plainly first:** writing a paragraph is cheap for a
model; filling a structured event vocabulary correctly, exhaustively, every
turn, is not. `beat_events` is a REAL new burden on the resolve call — the
evidence that structured contracts degrade under narrative pressure is this
repo's own (`zone` tagging, dialogue-log volume mis-transcription
`agents/director.py:4868-4879`, `stations` emitted by 0 of 45 scenes while
undeclared, 17.2% of the model's own manifest entries unencoded). Anyone
claiming the Director will fill five typed events per beat with clean
subjects, channels and state_refs at the same reliability it writes a
paragraph is claiming something this codebase has repeatedly measured to be
false. The mitigations are that the vocabulary is one the model already
speaks (it is the character-sequence schema it reads every turn, and 97% of
beats already produce a correct typed `dialogue_log`), that the grain is
sentence-sized, and that every field has a deterministic backstop
(delivery gates fail closed: a mistyped channel under-delivers, it does not
leak). But the honest expectation is a reliability dip at introduction and a
permanent tax of roughly the JSON overhead on ~5 fragments/beat.

**Position: keep the prose — demoted to a private reasoning field that
NOTHING downstream consumes.** Concretely: rename `resolved_event` to
`account` (or keep the name, change the contract wording), ordered FIRST in
the output contract so the model still narrates the beat to itself before
typing it; excluded from every payload (perception, background,
mapping_commit gets events instead), excluded from the events row's consumed
fields (stored for the author's benefit only, like `reasoning` on the
variants row, `db.py` variants schema); consumed by zero code paths. The
branch's goal holds fully — perception never sees it — while the model keeps
the substrate it demonstrably reasons in.

Why this is the honest trade rather than hedging:

- The entire reconciliation stack is testimony that the prose is where the
  model's actual beat lives: the manifest is defined AGAINST the prose
  ("changes your resolved_event asserts", `prompts.py:2098`), and the repair
  seam treats prose as "the account being reconciled against, not the thing
  under repair" (`agents/director.py:3314-3316`). Structure is currently
  downstream of prose in this model's cognition; deleting the prose field
  gambles the `state_diff` quality of every beat on that ordering being an
  artifact. 28.8% omission-with-prose is the baseline; without the anchor it
  has no measured floor. (Unverified: no A/B exists. `tools/contract_bench.py`
  + stored payloads can produce one — run resolve on ~50 stored payloads with
  and without the prose field and compare manifest-omission and
  diff-completeness rates. Do this before deciding to ever drop the field.)
- The cost of keeping it is ~150 tokens/beat of output (median 667 chars) and
  zero firewall cost, since consumption is what leaks, not existence. The
  cost of wrongly deleting it is degraded objective state on every beat.
- Token arithmetic for the whole change (estimates, unverified): today's
  output = prose (~150 tok) + manifest (~65% beats) + diff. Proposed = private
  prose (~150) + events (~5 fragments ≈ 180-250 with JSON overhead) − manifest
  (folded) − dice/fiction_frame/dialogue_order echoes (~40-80). Net: roughly
  +100-150 output tokens/beat, bought back partially in reliability: the five
  prose-regex authority checks (`:4330-4502`) become field comparisons
  (actor ≠ declarer), their double-call retry loop fires on structure instead
  of regex confidence, and the per-perceiver LLM view calls disappear
  entirely with the branch. (The retry fire-rate is not recoverable from
  stored variants — `player_act_warnings` records only violations that
  SURVIVE retry: 0/2,232. Flagged unverified.)

---

## 4. What is lost, consolidated

| Change | Loss | Why acceptable |
|---|---|---|
| `beat_events` replaces prose as perception input | inter-event composition/pacing; entangled multi-subject sentences flattened; introduction-period reliability dip on a new structured contract | composition is narration's job and narrator never consumed the prose; deterministic gates fail closed (mistype ⇒ under-deliver, never leak); prose kept as private CoT preserves diff quality |
| prose demoted to private field | prose-keyword scans (restraint 41, unconsciousness 18, destruction 0 detections/corpus) lose their richest text | scans run over concatenated observables at reduced fidelity; 59 detections/2,232 beats is the measured exposure |
| drop `dice` from contract | nothing (engine overwrites it today) | — |
| drop resolve `fiction_frame` | nothing (no consumer) | — |
| derive `dialogue_order` | 7.4% divergent orderings | no consumer distinguishes them; guard code deleted |
| single-location, exception-only `claim_dispositions` | explicit "realized" statements | engine already proves realization from diff evidence |
| optional `world_pressure` hold | explicit hold vs. forgot distinction | already warning-only; keep `hold` accepted-but-not-required |
| fold `changes_asserted` into `state_ref` | nothing once events land; DO NOT remove before | detector inputs move, check unchanged |

## 5. Sequencing

1. Contract-only trims first, each independently testable, no architecture
   risk: dice (§3.2.1), fiction_frame (§3.2.2), dialogue_order (§3.2.3),
   claim_dispositions dedup (§3.2.4), world_pressure hold (§3.2.5). Schema
   fields stay (LenientModel tolerance + saved-variant compat); prompts and
   projections change.
2. `BeatEvent` schema + Director emits `beat_events` ALONGSIDE
   `resolved_event`, consumed by nothing — measure fill quality against the
   prose on live beats (the `stations` lesson: declare every field on the
   Pydantic model or the round-trip deletes it, `schemas.py:1770-1780`).
3. Cut perception over: deterministic assembly from `beat_events`;
   `_redact_concealed_from_event` / `_surface_translate_event` retired;
   legacy path retained for pre-change traces/reruns.
4. Migrate the §2 text-matching consumers to event subjects (X7 fix rides
   this).
5. Fold `changes_asserted` into `state_ref`; run the §3.5 A/B before any
   decision about the private prose field's long-term fate.

Each step lands with its regression tests per the safe-change workflow
(`AGENTS.md` §Safe change workflow); step 3 is the one requiring the
adversarial perception suite in full.
