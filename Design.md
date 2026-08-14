# Sonder Engine — Design

## What this document is

The architectural record: what the engine is for, what is actually built, what
is partly built, what is not built, and what should be built next.

**The honesty rule.** The previous edition of this file grew past 1,500 lines
and drifted far enough from the code that `CLAUDE.md` had to warn readers to
verify it before trusting it — which made it a liability rather than a
reference. This edition was written by checking claims against source, and it
carries a conformance table precisely so drift becomes visible instead of
buried.

Every "Built" claim below was verified against code, not against another
document. Where verification was partial, it says so. When you change
behaviour, change the status row in the same commit; a row that is wrong is
worse than a row that is missing. The previous edition is in git history.

`AGENTS.md` is the operational guide (edit routing, invariants, workflow).
`docs/PIPELINE.md` is the stage-by-stage execution reference. `docs/DATABASE.md`
is the schema and change checklist. `docs/UNBUILT.md` is the single register of
everything not yet built. This file is the *why* and the status — do not
duplicate the other four here.

---

## Thesis

The engine produces long-form interactive fiction by **simulating people and a
world honestly, and letting story be the residue rather than the target**. No
agent is trying to be entertaining.

One layer computes what objectively happens. One computes what each mind could
register of it. One predicts what each person does given their psychology. One
renders the player's slice as prose. Secrets, betrayal, dramatic irony and false
belief are authored nowhere — they fall out of the simulation the moment the
bookkeeping is honest enough to make *absence of knowledge* computable.

The north star is **coherence without omniscience, not realism**. Realism is
expensive and often anti-dramatic. What the engine guarantees is narrower and
more valuable: a world that holds together *and* contains no mind that knows
more than it should. That second property is the soil dramatic irony grows in,
and it is the thing a single context window structurally cannot provide.

The player **is** the protagonist. No agent models the player's interior — the
player's own mind supplies it live, every turn. The engine exists to give that
mind a believable, causally honest, selectively ignorant world to act in, and to
hand the player the dials to shape it.

### Genre-agnostic substrate, world-specific law

The engine should be able to serve any genre without teaching its core that one
genre's interpretation is universal. Core state describes reusable facts:
identity, space, time, contact, motion, containment, visibility, perception,
knowledge, authority, conditions and causality. It should not hard-code what a
wound, spell, transformation, technology, supernatural weakness or social
custom means in every world.

Genre-specific mechanics belong in lorebooks when they are authored or already
canonical. When canon is silent, the Director infers the local rule from the
fiction model, established facts and immediate circumstances. The ordering is:
explicit canon first, established story facts second, Director inference last.
An inference may fill a gap but never silently override a lorebook rule. The
engine's job is to represent, validate, persist and deliver the resulting facts
without losing their causal or epistemic boundaries.

This is also the quality bar. Sonder Engine is not successful merely because it
can generate plausible prose in many genres; a raw LLM call already does that
with fewer seams and often smoother local writing. The orchestration must earn
its cost by producing demonstrably better long-form continuity, causality,
character agency, epistemic integrity, memory and world-specific coherence.
The target is eventually to handle any genre to a higher standard than an
unmediated model call, while being honest that every structured boundary can
lose nuance until it is made reliable.

That advantage is not wholly hypothetical. Long-term character memory has
already proved more durable than raw model context: it survives context-window
pressure, process restarts and story restoration as character-owned,
provenance-bearing evidence, then retrieves earlier experience into a bounded
current prompt. This proves durability, not perfection—selection, consolidation
and interpretation can still fail—but it is a concrete case where structure has
already delivered something an unmediated context cannot sustain.

### The two principles everything else serves

1. **Structure over instruction.** Anything you want guaranteed must be
   *impossible to violate*, not merely instructed against. A prompt cannot
   un-write its own context.
2. **Auditability.** Every numeric change should be event-linked, every
   scheduled effect seeded and logged, every resolution recorded. Silent drift
   is the failure mode being prevented at every layer.

[Structural debt](#structural-debt) is an honest account of where the engine
currently falls short of principle 1. It is the most useful section here.

### What the firewall is, and what it is not

**The firewall restricts the FLOW of knowledge, not knowledge itself.** A mind
may know anything it has a channel to. What it may not do is come into a fact
that reached it through no channel at all. Everything the engine does about
information is that single rule applied to a different pathway — sight, sound,
scent, touch, memory, frame, identity.

It is a GAP, not a rule imposed on top of one. Two people genuinely do not
share a head; the engine is not restraining a character, it is declining to
collapse a distance that already exists in the fiction. That is why nearly
every guard in the codebase SUBTRACTS — `_strip_unreachable_bodies` does not
forbid describing somebody, it declines to invent a channel; `visible_memory_rows`
does not withhold memories, there is no path from that mind to those rows.

Three things follow, and each has been got wrong at least once (see
`AGENTS.md` § Information boundaries for the operational form):

- **Inference is the product, not the risk.** A conclusion drawn from
  legitimately perceived material is exactly what this engine exists to
  produce. Never harden a guard by making minds conclude less.
- **A leak is an engine failure, never a model's.** The deterministic floor
  must not depend on a model cooperating, so no model behaviour excuses a
  crossing. A warning, by contrast, is the system working — nothing crossed.
- **Firewall integrity is an invariant, not a model-selection criterion.**

And the gap is kept because it is GENERATIVE, not because it is safe. Dramatic
irony, deception, misidentification, a mind acting confidently on a belief the
world has since contradicted — all of it requires the distance between minds to
be real. Collapse it and the result is not a freer story but one where nobody
can be surprised, deceived, or wrong.

### What it fixes

Three failures recur in single-model storytelling, and they are one bug: a
single context window where everything is epistemically flat, so the model
conditions on all of it, because that is the only thing a model can do.

- An NPC references a fact it was never told.
- An NPC treats the player's private thought as spoken dialogue.
- An NPC reacts to something that happened while it was not present.

None is a discipline failure a model can be instructed out of, because the
forbidden information is *in the context*. The fix is to never place the
forbidden thing in the slot: **each mind runs in its own context containing only
what it legitimately earned, and a filter decides what crosses.**

---

## Status at a glance

Conformance against the founding architecture, re-verified against source at
alpha 6.1.

| Founding commitment | Status | Evidence / gap |
|---|---|---|
| Firewall as plumbing — each mind gets only its perception object | **Built** | `agents/perception.py` composes per-observer views deterministically through `agents/composer.py` — percept builders decide admission on typed data (delivery gates, hear/sight/scent levels, containment, rear-arc, concealment, recognition labels), and `render_view`/`render_episode` realise them from percepts alone, taking no scene and no DB, so a rendering path structurally cannot ADD information. No model call is involved and there is no `perception` model role to configure. Characters receive their view, never the event stream; stored event rows are per-observer redacted via `recent_events_for_observer` when loaded into character context |
| Two perception passes per turn (onset, outcome) | **Built** | `perception_act` before resolution, `perception_outcome` after |
| Player-leads loop; characters declare blind to each other | **Built** | Plan built from `director_interpret.flow`; character steps run in parallel |
| Memory provenance | **Built, exceeds spec** | Six kinds (`witnessed/heard/told/read/inferred/remembered`) against the specified three, plus `turn_idx`, bound at commit |
| Action visibility posture | **Built** | `visibility` + `conceal_from` + `targets` on every declaration; targets the model leaves empty are bound deterministically, because the seams that ask "does this land on someone?" all read that field |
| A beat opens with one character, and causality builds | **Built** | The interaction loop used to open with a simultaneous wave of two, on the argument that everyone in the initial queue answers the same fixed thing and so could not have seen each other. That is right about a beat aimed at the ROOM and wrong about one aimed at a person, which is most of them: the others are bystanders to an exchange that has not finished, and deciding blind they answer a question that is already answered. Live, chat 59 t161 — the player asked the Doctor a direct question, he was correctly ranked first and answered, and Tamamo in the same blind instant said "Doctor?", prompting a man who had just spoken; the narrator's own fidelity check caught it as dialogue rendered out of order. The stranding the wave was introduced for is now fixed where it was caused (the beat-ending exit is gated on `commitment: "contestable"`), so `initial_parallel_reactors` defaults to 1 and survives as a knob. Order is the beat's own causality: spoken to, then acted upon, then merely present — speech outranking action because an action's `targets` is a looser field that the deterministic binder fills from whoever the act plausibly lands on, and a live beat had "sits back down at the table" targeting both people in the room. Inside the untargeted band it is standing want-urgency plus a seeded jitter (`_untargeted_order`), because cast-REGISTRATION order was deciding and that is not a fact about the fiction — the same character opened every untargeted beat for the life of a story. Seeded on turn AND nonce, so a rerun from a stage replays and a reroll may land differently, the rule the dice already follow. **Interruption is declarative, not scheduled** — a character later in the chain has already HEARD the line they want to cut off, which is how interruption works in life, so `interrupts:"<name>"` on a speech or action element says the beat landed DURING that line rather than after it. Resolved deterministically: the named party must have spoken this beat and the interrupter must have been able to hear them. `cut_short_speech` breaks the line at a breath point rather than a word count — whole sentences survive, the last breaks near 60%, and that cut slides to the nearest comma or conjunction, because a flat halfway cut lands mid-phrase. A line too short to get inside is left whole. An interrupted ACTION is marked and not rewritten, because what happens to a reach that got grabbed is causality and causality belongs to the Director — which does not yet read the flag; see `docs/UNBUILT.md` § 1.29. **And an early exit no longer strands the summoned cast**: both exits drain every initial reactor first, since being summoned to the beat is what earns a character their turn, not being flagged — the failure the wave existed to paper over came straight back when the wave did (chat 59 t161–t162, Tamamo never called, two beats running) |
| A name is learned by hearing it said | **Built** | `known` gates every identity the engine will let a mind use — perception scrubs an unearned name out of a view, memory stores "a voice" instead of a speaker, the narrator will not name a person to somebody who has not met them. It was written in exactly two places: `greetings.py` seeds the one greeting character against the player, and commit seeds everyone when a background presence is PROMOTED. A third path exists, `validated_introductions`, and needs the mapping model to declare an explicit introduction event. Nothing recorded a name learned in play, so a character attached the ordinary way never entered the map and nobody ever learned anybody by being told. **Measured: 19 of 42 played stories held fewer recognitions than a fully-acquainted cast**; chat 59 — 162 turns, two cast, a mother and her daughter — held ONE directed pair, so every beat scrubbed both names out of both views. The failure that surfaces is not a missing name but a wrong one: a view holding one surviving name and one anonymous body invites the model to join them, and the Doctor answered a question the player asked as though Tamamo had asked it. `commit._names_heard_in` learns a name when it is SPOKEN in a hearer's own delivered view AND the person it names is in the room with them — no model call, riding a channel the firewall already governs. Two refusals keep it from becoming a leak: a name for somebody absent or in another room teaches nothing (hearing about someone elsewhere teaches you a name, not a face, and would otherwise license recognising a stranger who walks in later), and your own name teaches you nothing. Accumulated in `prepare_memory_commit`, which runs before the write lock, and applied by `commit_memories` inside the transaction, merged rather than assigned so an explicit introduction earlier in the same turn is not overwritten |
| A standing contact is a continuous percept | **Built** | The engine had two categories for anything physical — `event` (rendered once, on the beat it happens) and `state` (mentioned, then inert) — and a contact between two bodies is neither. It is true every beat AND felt every beat, until the ledger drops it. The consequence of having no third category was that the perception contract specified the tactile channel only as a SUBSTITUTE for sight: every mandatory clause is conditioned on sight being absent (in the dark, behind a wall, sealed inside something), so two bodies in continuous contact in a lit room had a wide-open tactile channel and nothing requiring a word of it. A view written under a token budget renders what is seen and drops what is felt. Measured over 7,508 corpus observations before the fix: **46.8% classified as `mixed` because no sensory cue matched them at all**, `interoception` accounted for 2.4%, and in the story that surfaced it the ACTING view of a character in three standing contacts was a median 460 characters against 812 for the outcome view of the same character — she chose her conduct with no sensation from her own body and was told what she had felt after the choice was made. `spatial.contact_sensation` renders the percept from one party's side in plain physical terms (pressure, weight, movement, friction, warmth; fullness and stretch for an interior contact), asymmetric where the contact is — the enclosing party feels something within them, the entering party feels something closed around theirs, and rendering either side with the other's phrasing describes a body the perceiver does not have. `agents.perception._deliver_standing_sensations` is the deterministic floor: it appends what the model left out, adds only for a party to the contact (a bystander watching two other people touch feels nothing), and matches both parts in ONE sentence on word boundaries so it neither duplicates a paraphrase nor accepts a hip in one clause against a hand in another. The prompt carries the same mandate as the cheap half, stated as the one contact rule that does NOT depend on sight |
| A speech element carries words, and only words | **Built** | `text` is the utterance; conduct is an `{type:'action'}` element beside it, and the sequence is ordered so a character interleaves them freely. The engine had no opinion about the contents of `text`, so a model writing chat-roleplay stage directions into it (`"*leans in and sets a hand on her shoulder* Sit down"`) got the movement delivered as SOUND — lost entirely to a listener who could not hear, ground into word fragments by muffling, and narrated by ear to a listener who could hear but not see (`You hear Reya say: "*leans in…*"`). **A flow defect, not a knowledge one**: the person being touched would have felt it, and nobody learned anything they had no channel to — but the channel the information travelled was wrong, and a wrong channel is an engine failure, never a model's. `agents.common.split_stage_directions` excises the span inside `norm_sequence`, before anything downstream sees it, and re-files it as the action element it should have been: placed immediately before the line it was buried in, inheriting that line's concealment (a stage direction inside a whispered aside must not become overt conduct just because it moved channel), and routed through the same mental-verb check as any other action. A one-word span is markdown emphasis and stays spoken. `tone` was considered as the home for vocal manner and rejected — the delivery layer renders tone only when the listener can SEE the speaker, so an audible laugh parked there is lost in the dark, which is the same bug one layer down |
| Two-store protagonist, never merged | **Built** | `private_voice_setting` appears only in `agents/narration.py` — verified absent from character and perception stages. `shadow_profile` is separate world state |
| Seeded, logged, replayable dice | **Built** | `director_resolve` uses `random.Random("{chat}:{turn}:{nonce}:{actor}:{attempt}")` and records `seed/roll/modifier/dc/outcome/margin` |
| Deterministic scheduling | **Built** | `scheduled_events.seed` written as deterministic strings; `stable_event_key` gives rerun idempotency |
| Per-character temperature | **Built** | `character_temperature(sheet)` passed to the provider call in `agents/character.py` |
| Narrator exemplar pool, event-amnesiac | **Built** | `exemplars` setting read in `agents/narration.py`; narrator receives the player view, not the event stream |
| Tiered cognition | **Built** | Model roles (`default`/`director`/`narrator`/`utility`) plus per-character `simulation.tier` |
| Theory of mind, cached and event-triggered | **Built** | `theory_of_mind.py`; `tom_triggers` on the flow |
| Event-grounded live psychology | **Built** | v4 character schema plus `psychology_runtime.py`: stress split into aversive strain and non-distressing drive, mixed pain/pleasure outside survival with a slow-integrating unresolved `charge`, protected beliefs, learned cue associations, and simulation-time recovery. Ambient comfort from surfaces (`comfort.py` + `resolve_hedonic`'s `ambient_comfort` floor) is built: it raises the pleasure level only — never `charge` — habituates on a sustained source, and lets `tick_vitals` derive passive rest from lying on a soft support |
| Authored initial outfit with live story attire | **Built** | Character/persona `initial_outfit` is kept separate from stable body appearance and seeds `scene.attire` once; later clothing changes remain mutable story state |
| Clothing by body region | **Built** | `attire.py`: a garment covers one or more of head/torso/arms/hands/waist/**groin**/legs/feet, ordered outermost-first, so exposure is state rather than a sentence. `waist` and `groin` are separate because a sash covers the belt line and nothing else, while a dress covers both — conflated, a body in only an obi reports its groin covered, and a dress stopping at the waist reports it bare. `regions_covered` spans a garment across every region it covers (a kimono: torso/arms/waist/groin/legs), `_sync_spanning_garments` keeps those copies one garment so loosening a kimono at the torso does not leave its sleeves fastened, and `newly_removed` reports it once. A garment is worn OVER a region or merely AT it (`attaches`: a ribbon is in the hair, a necklace at the throat — present, visible, covering nothing, so a head wearing only a ribbon is bare and removing it uncovers nobody), and garments within a region are ordered outermost-first, so an under-layer keeps covering when the layer over it comes off and is reported as hidden while it does not. `name` is a short handle — the key the Director and `decisive_targets` match on — with `description` beside it; `split_garment_name` recovers the two from generators that write "Name — description" into one field, which used to truncate at the name limit mid-clause AND leave a hundred-word string as the matching key. The Director is given an explicit `exposed` list and told it is the whole truth about bare skin. Regions are the only authoring surface; `initial_outfit.wearing` is retired to an INPUT format (older cards, imports, generator output), migrated into regions by `character_schema._normalize_initial_outfit` on read and written back derived, so a cue-table guess lands in the region editor where an author can correct it and the two representations cannot disagree. `initial_outfit.state` is retired outright — see garment condition. `agents/common.attire_view` is the shared prompt projection, and `beneath` reaches no prompt unless the host sets `attire_beneath` — an uncovered region still reports itself uncovered |
| Garment condition, distinct from wear | **Built** | A garment carries `condition` (stained, torn, soaked) alongside `state` (how far off the body); a shirt can be soaked and fully worn. Set by the Director through `attire.<name>.conditions`, persists until something changes it, and travels with the garment when it comes off (`commit._mint_shed_garments`) so a stained shirt is a stained shirt on the floor. The resolve prompt states the asymmetry a blow creates: the garment's damage is permanent until mended, the body's is `vitals.injury`/a condition/an overlay, all of which heal, and neither may be written into stable appearance |
| Undressing as a sequence | **Built** | A garment with fastenings moves `worn → loosened → open → removed`, and the prompt teaches the staging — but the clamp is INVERTED (design note 17, second incident): a resolved `remove` LANDS by default, and `attire.advance` holds it one rung only when the beat's own prose shows the act still in progress (`attire._PROCESS`: inchoatives, conatives, explicit partiality — a smaller, closed set), because twice a wrong ledger's root cause was the completion vocabulary missing one more way English says a garment came off ("pulls the tank top off", then "shrugs the jacket off" on a live reroll). The Director owns objective causality; commit consistency-checks its resolution against the prose instead of re-deciding it, and an unrecognised phrasing now fails SAFE — a removal lands that the Director asserted anyway, instead of silently forking the ledger from the fiction. `process_targets`/`decisive_targets` share one attribution ladder (`_attributed_targets`: garment phrase, possessive-genitive owner, head noun, first person, sole name), so the actor is not mistaken for the target and one person's fumbling does not slow the room; decisive lifts even a same-beat process reading; intermediate jumps (`worn → open`) still clamp — staged states remain the contract. A held removal is reported to the Director (`tell_director`), never silent. Getting dressed is deliberately unrestricted. A garment that comes off is minted as a real portable object in the room (`commit._mint_shed_garments`) rather than ceasing to exist — unless it arrives on ANOTHER body the same beat, which is a handover rather than a drop: "she takes off her coat and drapes it over his shoulders" used to leave two coats, one on his shoulders and one at their feet. Keyed on arriving-this-beat rather than worn-by-anyone, so two guards in the same kind of cloak still get a real cloak on the floor when one takes his off |
| Displacement, the third clothing axis | **Built** | A still-worn garment that stops covering a place it normally covers — a jacket pushed off the shoulders, a skirt hiked to the waist, trousers around the ankles — is neither a ladder move (fully worn) nor a condition (undamaged), and it had no channel: the chat-70 incident held torso/arms/waist covered while the narration wrote the body out of the jacket, because the displacement lived in condition prose that coverage never reads. Now the existing `coverage`/`covered_zones` machinery generalized to region grain (`attire.zones_of`: an unzoned region is its own single zone, torso keeps chest/midriff), because the corpus showed models already reaching for exactly that shape — 4 region-grain coverage emissions silently dropped by the torso-only validator, 37% of stored condition notes carrying displacement language, one stating coverage outright in prose. Instant and reversible, no step rule: displacement is one gesture with no middle worth a beat and is cheap to undo, which is the ladder's asymmetry inverted — while removal from a fully-displaced garment is one rung, its middle already played. The removal/displacement boundary is guarded both ways: displacement anchors keep "off her shoulders" a shove, a coverage claim emptying a garment named by a removal-directed decisive phrase escalates to the removal it was (ambiguity keeps the recoverable reading) — and the removal ladder's clamp is inverted (see the undressing row: a resolved `remove` lands unless the prose is in progress, so no completion wordlist sits on the removal path). The floor detects and feeds back, never executes prose: held removals, rung words in conditions, and prose-only displacement all reach the Director via `tell_director`; an unreadable zone list keeps the garment covering (the mildest-reading rule). Hand edits are first-class — the region editor offers the coverage toggle for every covered region, `rederive_entry`/`dedupe_regions`/`_sync_spanning_garments` all carry the override idempotently. No schema change, no migration. `design_notes/17-garment-displacement.md`; residuals (left/right asymmetry, sheer transparency) in `docs/UNBUILT.md` |
| Extra body parts as structured data | **Built** | `embodiment.extra_parts` on character and persona cards: a part (tail, wings, horns) declared once with closed menus — attachment region from `attire.REGIONS`, aspect from `character_schema.EXTRA_PART_ASPECTS` (front/back/top/underside/left/right/sides), count, `through_clothing`, bounded description — instead of living only as prose in `visible.summary` (9 of 45 corpus character sheets carried one that way). Card-level and read live like senses, so persistence/archive/branch come free with the sheet and a cast without any is byte-identical to before. Perception delivers a part on the body-region rows through the same `region_visibility` verdicts clothing uses: vantage/containment/darkness hide everything, garment coverage at the attachment region hides only a part authored `through_clothing: false` (the default tail passes through the skirt), and a body always knows its own. Part nouns are free text and were already valid contact endpoints (`_part_identity`/`_same_appendage` are structural). Authored by every path that writes a card, not only by hand: one shared `prompts.EXTRA_PARTS_NOTE` is spliced into `generator_character`, `generator_persona`, `fill_appearance`, `promote_character` and both import-reinterpret prompts, each of which also carries `extra_parts` in its JSON template. Without it the field was writable only through the editor — a kitsune generated or imported from a card arrived with nine tails in prose and none the engine could see, cover or touch, which is `psychology.drive`'s failure mode exactly: a structured field that is empty reads as complete. `fill_appearance` keeps what comes back (the merge read `visible` and `initial_outfit` only, so a proposed part was discarded), treating an omitted list as silence rather than an amputation and an explicit `[]` as a clearance, and the editor sends the author's unsaved parts with the request so a fill run after typing "tail" does not propose a second one. `character_import_warnings` says so when body prose names a part the sheet does not declare, reading only the visible-body fields — a character who "never turns tail" has no anatomy in the sentence. `design_notes/11-extra-body-parts.md`; residuals in `docs/UNBUILT.md` §6.9 (Director-driven transformation, garments covering a part) |
| Generated body and clothing | **Built** | `importers.fill_appearance` + the `fill_appearance` prompt fill body and per-region outfit from the card, what the author has typed but not yet saved, and a brief; `beneath` is a separate opt-in and is stripped from the proposal when it was not asked for. Writes nothing — the editor reopens on an unsaved proposal, as `fill_character_psychology` does |
| Approach is not arrival | **Built** | `MovementDecl.arrives` — whether the declaration covers ARRIVING or only setting off — filled by `director_interpret` and honoured deterministically by `director_resolve` (`_guard_approach_is_not_arrival`, plus the backstop refusing to commit a non-arriving move). Live failure, "The Blizzard" turn 2: "You wander towards it" of a building seen through the snow became `to_room: distant_mountain_building`, the route check passed it (the rooms genuinely were adjacent and open), and the resolve wrote her through the door into the firelight — from `exposure: open` to `exposure: sheltered`, out of a blizzard, with nobody having said she was going in. A FIELD rather than a downstream test because the distinction is not recoverable downstream: measured across 1249 live turns, no text heuristic separates "I cross the command deck toward the med bay" (an asserted crossing) from "progresses across the clearing toward the building" — both say "toward", both are staged `approach`, both are `commitment: asserted`. Four heuristics were tried against the corpus and each blocked legitimate arrivals (3, 8 and 4 false positives). Defaults true, so no existing declaration changes meaning. Carried/contained bodies are exempt; a declared VEHICLE mover is guarded like any other, since a skiff told to head for a light is as much not-there-yet as the hand on its tiller. An approach in flight is recorded on the scene per mover (`scene.approach`), so the next declaration toward the same place ARRIVES — without that memory the feature strands anyone who keeps writing approach-flavoured text, and time spent approaching is time spent standing still (measured: six simulated hours of "trudging towards the mountain" left the walker in her starting clearing under level-12 snowdrifts). `ActionStage` — classified since the beginning, read by nothing — is `docs/UNBUILT.md` §1.13 |
| Place purpose (what a place is FOR) | **Built (v1)** | `place_purpose.py` per `docs/DESIGN_PLACE_PURPOSE.md`: live `perception.here_affords` echo; `affords` ledger on the character's own place-graph nodes — `witnessed` from own vitals/`comfort.rest_affording`, `told` mirrored from reconciled beliefs with `belief_credence`-refreshed sureness, `assumed` derived read-side from own node names (never stored); `memory.recalled_places` surfaces at most two walked-route options on a felt need. Witnessed drink/water/warmth, told-basis node minting, and negative entries deliberately not built |
| Durable place graph (a mind's own map of walked ground) | **Built** | `commit.update_place_graph` writes per-character nodes and edges onto `chat_chars.state` with `basis: walked\|seen`, `disproven` retraction both ways, and `PLACE_GRAPH_NODE_CAP` eviction; read back as navigational verdicts and `_frontier_hops` distance in `agents/character.py`. `basis: "told"` is an accepted value with no writer, deliberately |
| Long-term goals (the project tier) | **Built (v4)** | **v4 made it reachable.** Measured over the live corpus, **0 of 14 banks that carry the field have ever held a project or a former one** — not rarely adopted, never, in any story. One condition written twice: `affect.project_boundary` opened `if not projects: return None`, and the payload guarded `if isinstance(_preview, dict) and _self.get("projects")`. The prompt names the review beat as the occasion to emit `project_ops` — "That beat IS the review this tier owes you" — and both gates made the review beat require a project. The one moment a first project could be adopted was conditional on already having one. §2.1's rule from a new direction: there the payload made the asked-for thing harder to reach and the prompt lost; here it withholds the occasion entirely, and no prompt argues with a key that is never present. Arrival still needs a project to arrive at; a task closing and the scene or frame changing no longer do. v3: `affect.apply_project_ops` / `serves_priority` / `project_boundary` / `settle_probation`; persisted in `interior.projects` / `former_projects`. Caps at two, adoption requires a non-circular `satisfied_when`, probation weighs at intention level until served on ≥3 beats over ≥12 turns, drift surfaces as `adrift`. Per `docs/DESIGN_LONG_TERM_GOALS.md` |
| Memory retrieval by meaning | **Built** | An `embeddings` provider makes the two vector rankings of `search_memories` genuinely semantic, and one is configured: as of 2026-08-01 `embedding_model_key()` is `openrouter:3:perplexity/pplx-embed-v1-4b` at 2560 dimensions, with all 5,236 memory rows on it and none on the fallback — so the semantic half of retrieval is live rather than hypothetical. Without one the engine falls back to `providers.cheap_embed`, a signed character-n-gram hash (Weinberger et al. 2009) — measured against a real 441-memory story on vocabulary-disjoint paraphrase, that scores **0% recall at every k, median rank 228 of 441**, indistinguishable from random, while a real model reaches median 1–3. It is a strong LEXICAL retriever and a non-existent semantic one, which is why episodic recall worked and thematic recall never did. Deliberately no ANN index: `search_memories` applies a turn cutoff (its own comment calls it "the SOLE defence" against a mind retrieving how the turn it is deciding turned out) and frame visibility BEFORE ranking, and those are exactly the selective predicates an ANN index carries badly — the `sqlite-vec` declaration was deleted rather than wired. The exhaustive scan is also not the bottleneck: 16 ms at a real story's worst case, ~709 ms at ten thousand turns, against an LLM call in the same beat |
| Changing the embedding model is safe | **Built** | A vector is only comparable with one from the same model, so a row embedded by another scores 0.0 on both vector rankings forever. Nothing re-embedded and nothing said so, so configuring a provider silently split a bank into two eras. Now: `embedding_bank_status` counts the split, retrieval warns once per situation, `rebuild_embeddings` re-reads stranded rows resumably and refuses to write the fallback over real vectors, opening a story OFFERS the rebuild rather than performing it, a checkpoint restore hands the bank back to the reconciler (a reroll had been putting 637 of 642 rows back on the fallback), and `rebuild_checkpoint_embeddings` carries a completed rebuild through saved states by SUBSTITUTION rather than computation — 99,442 saved memories repaired across 1,040 checkpoints in 98 seconds and zero API calls, because a vector is a pure function of the memory and the same memory recurs unchanged across every checkpoint. Of the MEMORY, not of its `content`: that join keyed on `(char_id, content)` until alpha 6.6 while `_memory_document` also folds in turn, location, category, key_phrases, entities, gist, provenance and emotional_context — so two rows could agree on content, hold different vectors, and be handed each other's. It now keys on the whole document, and a summary on its whole `_summary_retrieval_text` rather than its `summary` field, which had the same collision |
| A row is not stranded by one bad second | **Built** | Everything above answers "the host changed models"; none of it answered "the provider blinked", which turned out to be the commoner way a bank splits. `embed_texts_meta` degrades to the crc32 hash on ANY error and the writers store that hash under its own honest stamp — correct for a query, permanent for a write, since nothing re-embeds until somebody accepts a paid rebuild. It had no retry (the machinery at `providers.RetryConfig` covered chat completions only), and no log, so the whole event was invisible: reported live 2026-08-11 as a story created from a greeting offering, on its first beat, to rebuild the memories it had just written, then stranding four more on turn 2 — while the very same eight documents embedded fine on demand a minute later. The embeddings POST now retries on the statuses a chat call retries and on the same dropped-connection exceptions, refuses to retry a 400 (a wrong model is an answer, not a hiccup, and retrying it would trebly slow every write for as long as the role is misconfigured), and says out loud which provider failed and why when it does fall back — rate-limited to once a minute per distinct error, so an outage reports itself without flooding. `embedding_bank_status` and the live-dimension probe opt OUT with `retry=None`: they run while a host waits for a chat to open, and a degraded provider is the thing they are asking about. Greeting seeds go through `add_memories_batch`, so six seeds are one round trip rather than six independent chances to be stranded on the busiest moment a story has. **And the engine paces itself against the ceiling it finds.** Measured the same day on the live OpenRouter/Perplexity route: a burst of 12 took 4 rate limits, and 8 SEQUENTIAL requests at ~2.5/s took 3 — so it is a request RATE, not a concurrency cap, the error is Perplexity's own `request_rate_limit_exceeded` relayed by OpenRouter rather than anything about the account, and this engine's ordinary fan-out reaches it (parallel character steps, one retrieval embedding each). `_embed_pace_wait`/`_penalize`/`_relax` start unpaced, learn an interval from the provider's own 429s, and decay it away once they stop — ADAPTIVE rather than configured, because the ceiling belongs to the model (a local embedder does tens per second and must not pay a number chosen for someone else's provider) and because a ceiling learned last week is not evidence about this week's. Slots are taken under the lock and slept outside it, so N concurrent callers get N spaced departures and then wait in parallel rather than serializing into each other. `RetryConfig.delay_for` gained EQUAL jitter — half fixed, half random — because a fan-out that all sleeps exactly 1s then exactly 2s retries as the same wave that was rate limited, and full jitter can draw a delay near zero, which against a rate ceiling is not a backoff at all. **And none of that is sufficient, so the engine finishes its own write.** A beat can still spend its whole retry budget inside one depleted window — live, chat 70 turn 6 lost all four memories with every guard above already running — so `note_failed_embedding_write`/`repair_pending_embeddings` re-embed the fallback-stamped rows BY ID about thirty seconds later, once the window has refilled. Deliberately not a rebuild, and the distinction carries the justification: walking the bank is a migration a host chooses and pays for, while re-doing a write the engine fumbled seconds ago is the engine finishing its job. It touches only rows whose own write fell back (never the historical corpus, never lore, never another chat), refuses to write the hash over the hash, skips rows another path already repaired, is bounded so an hour-long outage hands the problem back to the rebuild OFFER rather than accumulating, and is a no-op when the crc32 hash is itself the configured embedding — there the queue would mean re-hashing the same text on a timer forever. **The ceiling counts requests, not tokens, so concurrent calls are coalesced into one** (`_coalesced_embed`): callers arriving while a request is in flight queue behind it and the next request serves the whole group, identical texts embedded once. No artificial batching window — a timed wait-for-companions would tax every solo call to help the crowded ones, so instead the natural contention point IS the collection window, which means no-contention behaviour is unchanged and the busier the fan-out the better it batches. Licensed by measurement rather than by the API's promise: the same document embedded alone and inside a batch of three returned BITWISE identical vectors at both first and last position, so a text's vector does not depend on its companions. The engine already depended on that in one direction — writes batched, queries single — so recall would have been broken from the start if it were false. Vectors are routed back by position in both the success and fallback paths, so a caller structurally cannot receive another's vector; the bank probe opts out with `retry=None`, since a measurement taken while a chat is opening must not queue behind somebody else's turn |
| Relevance outranks recency | **Built** | RRF's magnitude is arbitrary (~0.02 at rank 1; only its order means anything) while the bonuses after it are hand-tuned on a 0..1 scale. Summed raw, the four relevance rankings reached 0.074 combined against a recency bonus of 0.12 alone — a recent, salient memory matching nothing outranked the best match on every relevance signal there is. Invisible until real embeddings made the signal real. `_RRF_SCALE` bridges the two scales; `_RECALL_LIMIT` rose 8→16 because every result set is padded with chronological neighbours and at 8 the padding was a third of what a character saw. Mood and goal now fuse as their own rank lists instead of being concatenated onto a query 20× their length |
| A character's history is searchable by era | **Built** | `memory_summaries` was keyed `(chat_id, char_id, scope)`, so a scope held one row and every consolidation overwrote it. The cost was not storage but that the summary layer could not be SEARCHED — there was nothing to search between — while every summary already carried a maintained `embedding`, computed on write, re-embedded on a model change, carried verbatim through every archive and checkpoint, and read by no retrieval path in the engine: 67 vectors on the live bank, maintained across years of turns and never once ranked. Schema v23 completes the key with `end_turn_idx`. Consolidation needed no change at all — it was already computing bounded windows (`min`/`max` turn_idx over that pass's memories, which are already the ones after the previous summary's `end_turn_idx`) and the constraint was throwing each one away on the next write. `search_memory_summaries` ranks them under the same scoping as `search_memories`: `char_id` is the bank, `before_turn_idx` is the same exclusive cutoff, a cross-model vector is skipped rather than compared. Migrated against a copy of the live bank: 67 rows in, 67 out, byte-identical |
| A character receives the era the beat is about | **Built** | The half the row above deliberately deferred, landed once the deferral's own premise was measured and found false. It said the latest window is CUMULATIVE — consolidation folds the previous summary forward, so bounded windows in the payload would cost a character their early history. The consolidator is indeed told to merge forward; it is told just as firmly to shed low-salience detail, and shedding wins. Across the six live window pairs, successive windows share **3–16% of their text** at cosine 0.57–0.88; the Doctor's second window recaps the first in one clause and is otherwise entirely about its own ten turns. So a "cumulative" summary is in practice the latest CHAPTER — which means the pre-v23 singleton was not holding a life and overwriting nothing, it was overwriting every chapter before the last, and **53 of the 67 live banks have no summary over their opening turns at all** and never will. Windows stopped the loss; this reads them. `build_character_memory_context` ranks the earlier windows against the beat's own query and sends the best two beside the current one as `earlier_in_my_life`, first-hand scope only (three provenances in one field is the collapse the separate scopes exist to prevent), chronological oldest-first (ranking chooses which, not what order a life is read in), each dated RELATIVELY — `turn_idx` is global play order shared by every frame, so an absolute index would tell a mind where a flash-forward sits in the story's construction. Same guarantees as raw recall: one character's bank, the same exclusive turn cutoff, a cross-model vector skipped. No minimum score, deliberately: every prose vector scores every window in a compressed 0.45–0.55 band, so an absolute floor would drop everything or nothing depending on the embedding model — but the ORDER inside that band is trustworthy, a memory formed inside a window ranking that window first 97% and 82% of the time across the two live windows. Costs no extra round trip (the query batch is embedded once and shared with `search_memories`) and duplicates little: across 48 probes on the live bank, a mean **14%** of the sixteen recalled raw memories fall inside the window's own turn span. `_origin_on_drift` now surfaces the earliest first-hand window separately as `where_i_came_from` when an existing drift signal fires (goal held, project adrift, or resolved mood crossing its baseline), without spending a similarity slot every beat |
| The eras a destroyed summary took with it can be rebuilt | **Built** | `backfill_memory_summary_windows` re-consolidates the turn ranges the pre-v23 singleton overwrote, walking forward from a character's first memory to the earliest surviving window in aligned steps and chaining each result into the next exactly as the forward path would have. It never archives (the forward path retires low-salience rows it has just folded in; doing that here would retire hundreds at once on the strength of a summary written long after the fact) and never moves the consolidation cursor — `get_memory_summary` orders by `end_turn_idx DESC`, so older rows leave the newest one holding it, which is load-bearing and tested. Run against the longest story (chat 38, 118 turns, three characters, 641 memories): **27 windows in 336s**, summary coverage 8–18% → **92–98%**. It also surfaced why consolidation needed a rule it did not have. `commit.py` already refuses to MINT a memory from a view that says only "You are in an unspecified area" — an absence is not an episode — but banks written before that guard still carry them (369 rows corpus-wide; 85 of one character's 101 in this story), and consolidation had no such rule, so **13 of the 27 backfilled windows spent an LLM call rendering an absence into prose** to hand a character as a stretch of life they lived. `_is_empty_view` moved to `memory.py` (commit imports it back) and both consolidation paths now drop placeholder rows; the forward path, which cannot simply skip because the cursor lives on that row, advances it carrying the previous account forward and asks no model at all |
| A memory carries the mood it was formed in | **Built** | `valence/arousal` record the resolved affect carried INTO the event rather than the model's saturated self-report (measured +0.773 mean, 0% negative, against resolved +0.467 and 22% negative). Schema v24 adds `encoding_valence/encoding_arousal` from the post-appraisal surface, so the record distinguishes how the event was encountered from how it left the mind. Both pairs survive checkpoint/archive/character-bank/editor round-trips; old rows remain neutral rather than receiving invented retrospective arcs |
| Nobody may author the player's interior state | **Built** | The Director owns objective causality and does not own what is inside the protagonist. Live: the player typed only "W-what did you do to me!?" and the resolve wrote "the shrill, PANICKED cry" and "she takes in the GENUINE TERROR in those wide eyes" — asserted as fact, with "genuine" claiming its truth — which perception then copied into a second mind's view. Guarded at both ends: `_check_player_interiority_authority` on `director_resolve` (exempting anything the player themselves wrote, folded into the existing one-retry loop), and `_check_player_interiority_prose` on the narrator in the second person it writes in, ENFORCED rather than warned because what the narrator writes is what the story said happened. Observable surface — trembling, wide eyes, a shrill cry — is always allowed; naming the state behind it is not. Both ends were then found blind to the same sentence written two ways. Live in "Run!" (chat 56, t6), against a player who declared only "You imitate them slightly and shudder": the resolve wrote "She looks at him, still shaky, but the terror in her eyes has begun to recede" — a pronoun subject the name-anchored test could not see, so nothing fired and perception copied it into the player's own view; the narrator then rendered it as "The terror that had been living wide-open in **your** eyes pulls back to something smaller", where "your" attaches to "eyes" and the verb is "pulls back", one word out of reach of every branch of `_YOU_INTERIOR`. The Director's side now resolves a pronoun subject through `_sentence_subjects`, and the narrator's regex reads a named state anywhere in a clause that also reaches for the player. Deciding the player's emotional *arc* — that the terror is receding — is the same violation as naming it |
| A character calls the player what they may legitimately call them | **Built** | Three possible handles, and the engine was using the two wrong ones. Live in "Run!" (chat 54), three of The Doctor's four turn-0 memories read "The Doctor knows **the player** was being chased by a Dalek", "intrigued by **the player's** appearance" — the engine's own out-of-fiction word for the protagonist, inside a fictional mind, at salience 1.0. `{{PLAYER}}` was in none of them: the model wrote the literal English words, so `sub()` — which replaces only the exact token — had nothing to replace. An earlier run of the same card had the opposite failure: the token WAS present, `sub()` resolved it to "Hinami", and the character began knowing a name the launch had explicitly said he did not (`already_known=False`). `greetings.player_handle_for` now answers the question once — recognised → the persona's name, not recognised → a DESCRIPTION from the same `_unknown_actor_label` every perception path uses, so the launch cannot drift from the identity floor — and `_substitute_player_slot` rewrites the token AND the bare words, anchored on a leading article so an in-fiction "a lute player" keeps their job. The same defect had a second source: `commit.py`'s dialogue-memory path rewrote the player to the literal `"the player"` and then EXEMPTED them from the recognition gate every other speaker passes, producing 68 rows across the live corpus including `the player said "My Name is Hinami." to Dr. Moon` — the memory in which the character learns her name, attributed to a word from outside the story. The player is now a body in the room like any other: the persona's real name goes in and the gate decides. `_unknown_actor_label` also stopped truncating mid-phrase on a linking participle ("the beautiful young woman appearing"), which matters once the description is the deliverable rather than a fallback |
| Nobody may author a character's conduct but that character | **Built** | The mirror of the row above, from the character's side: the Director resolves what a declared act ACHIEVES and does not decide that the character also did something else. Live in "Run!" (chat 56, t1391) The Doctor declared one act — scan "from several feet away", "while staying at distance", against a want to act "without crowding her" — and `speech: null`; the resolve had him take "a half-step closer" and say "You're alright, Hinami. Nothing broken…". `_check_character_speech_authority` was armed and blind to all of it: it read only sentences OPENING with the literal name (every fabricated sentence opened with "He") and measured its verb window three words from that name (the attribution verb sat twelve words out, in a compound predicate). The dialogue_log backstop that WOULD have dropped the line was inert because `dialogue_log` was empty — the line existed only in prose, and the speech check strips quoted spans on the assumption the dialogue path covers them. Each guard held ground the other had. Now: `_sentence_subjects` binds a pronoun subject to the most recent NAMED subject (a newer name takes it, an unanchored pronoun binds to nobody), `_predicate_heads` measures the verb window per conjunct, `_check_character_act_authority` guards acts — the full act-verb list for a character who declared none, narrowed to MOVEMENT for one who declared a non-locomotive act, because distance decides what perception delivers and what contact is possible — and `_check_prose_quote_authority` catches a spoken line in prose that no declaration supports, whoever the prose says said it. All fold into the existing one-retry loop, kept only if it reduces the total. The cost of missing it is not cosmetic: the narrator dropped both fabrications, so nothing was visible in play, and both still committed as the Doctor's own episodic memory of what he did |
| Nobody may author the player's conduct but the player | **Built** | The doing half of the row above. `_check_player_act_authority` on `director_resolve`, folded into the same one-retry loop. Two scopes, and the second was missing entirely: a player who declared NO action was protected, and `if declared_actions: return []` disarmed the guard for anyone who narrated so much as a gesture. Live in "Run!" (chat 56, t10) that player narrated one every single beat, so the guard was off for the whole story — they typed `"Heh? What are we doing what's going on?" You look genuinely confused.` and the resolve wrote "her hands coming up to grip the edge of the console, fingers finding a lever as if to steady herself", which perception copied into their OWN view as "I grip the console edge" and the narrator rendered as fact. Their very next input was "Which lever?!" — the fabricated act replayed a beat later, which is precisely the failure the guard exists to stop. Elaboration cannot be separated from addition by vocabulary, because "pushes herself upright" elaborates a declared "slowly stands up" and shares not one word with it; what CAN be separated is what the act TOUCHES. Elaboration re-describes the player's own body, fabrication reaches out and takes hold of the world, so the widened scope flags exactly one thing: a manipulation verb taking a DIRECT object that is neither the player's own body nor anything their declaration mentions. "Pressed flat against the cold metal" is a body bracing itself and is not a grip on the metal |
| A view never narrates its own perceiver | **Built** | `_strip_self_narration` drops sentences whose subject is the perceiver, in all three perception passes. Live: Elyndra's own view read "Elyndra's gaze stays fixed on the shifting lump, her teasing smile faltering" in a view that elsewhere said "You see Hinami". Perception had copied the Director's omniscient sentence rather than rendering the beat from her frame — per-observer calls do not prevent that, since each observer's call simply echoed its input. Whole sentences only, subject only, and never emptying a view entirely. Subject resolution was name-anchored on the stated ground that "a pronoun could be anyone in the beat" — true of a pronoun read in isolation, false of one read in sequence, and the reason chat 56 t6 walked through: the PLAYER's own view read "She feels her arms still wrapped tightly, her breathing slowing, the terror in her eyes beginning to recede", third person about its own perceiver, naming an interior state she never declared. Now shares `_sentence_subjects` with the Director-side guards, so a pronoun continuing a named subject is resolved; an unanchored one still binds to nobody. **The guard needed a floor and the prompt needed to agree with it**: a view written WHOLLY from outside its own perceiver puts them in the subject slot of exactly the sentences carrying what they saw, so dropping by subject removes the framing error and the observation together. Live (chat 38, t140) the Doctor stood at the genkan with `shapes` sight to both bodies, watching an embrace the resolved event says he was watching with bright interest, and his view, his structured observations and his committed memory of the beat all came out sound-only. The perception prompt carried no person discipline at all while this scrub enforced one — the Narrator has an explicit PERSON DISCIPLINE clause and perception had nothing — so it now requires each view to be written from inside its perceiver, and `_strip_self_narration` refuses a drop that would leave a view with no sight in it (`_SIGHT_ASSERTION`), reporting the refusal rather than performing it. Over-denial is the worse failure, on the same ground the row below states it: a framing slip is bounded and visible, and what a mind saw is not |
| A view describes only bodies the perceiver can reach | **Built** | The engine already knew: `visual_level_between` returns 'none' for the pair and `spatial_rel` calls the rooms `separated`, and nothing consumed either answer once the view was prose. Live (chat 58, t28) the player slammed the TARDIS doors and stood in the console room; the Dalek stood outside, two rooms off with no connecting edge, and her actions were still narrated into its view — and from there into its own next-turn context. `_strip_unreachable_bodies` runs in `_scrub_view_for` beside `_strip_self_narration`, dropping whole sentences whose subject is a body with NO sensory channel, warning per drop, never emptying a view. Deliberately the hard case only: a body the perceiver cannot see but can still hear through a shut door is left alone, because over-denial is the worse failure — silence about someone audibly present is its own lie — and sight-asserted-where-only-hearing-exists needs sense-cue analysis this guard does not attempt. The subject match itself was the other half: every subject-anchored guard read the bare registered name, so a body registered `A Dalek` and written `The Dalek's visual sensors` slipped past all of them, which is why that view narrated its own perceiver in the third person. `_subject_opener` tolerates a leading article — the three articles only, never a title, since a title is often the sole thing telling two bodies apart (§1.17's line). The scene DRIFT that put those bodies in the wrong rooms is not fixed: `docs/UNBUILT.md` §1.20 |
| A beat's transition is perceived, not just its result | **Built** | Perception ran against the OUTCOME scene alone, so any act that closed a channel erased the perception of itself. Live (chat 58, t27): the player ran through the TARDIS's open doors, the doors slammed, and the ship went `in_transit` — which correctly severs an interior's exterior edges — all in one beat, so by the time the Doctor's view was built the room she had run into was adjacent to nothing. His view records the doors closing on an empty doorway; he never saw her go in. Nothing in the transit model was wrong: a ship in flight IS cut off, and `in_transit` with no destination is a legitimate state (a destination need not be declared at departure, and the gap is room for later play). The defect was asking the perceptibility question only of the beat's last frame. `_source_channels` now takes `prev_sc` — the scene before this turn's diff — and a source counts as perceptible if it was reachable at EITHER end, marking the rel `was_reachable_at_beat_start` so a reader can tell a transition from a standing line of sight. It only ever UPGRADES: a body unreachable at both ends stays unreachable, so nothing closed for the whole beat is opened. Covers every act that shuts a channel it is seen through — a slammed door, a drawn curtain, stepping into a container, a vehicle pulling away |
| A delivered line reaches the mind that heard it, whole and in order | **Built** | `_dedupe_view_sentences` has always documented "sentences containing quoted dialogue are never dropped -- quotes must survive verbatim". The splitter defeated it: the check is per-SENTENCE, and a spoken line carrying its own terminal punctuation is cut into fragments -- only the two on the ends keep a quote mark, and every fragment between them is judged naked and dropped if it echoes anything earlier in the view. Live (chat 58, t30): the player answered a direct question with "Seven? I think? There might have been more... they began to spread out..." -- four terminators, four fragments. This runs LAST in `perception_act`, after the deterministic delivery, and ate the interior of the quotation; the Doctor then asked "How many? Where exactly?", the question that had just been answered. `_mask_quoted_spans` now replaces each quoted span with an opaque token carrying no whitespace and no terminal punctuation BEFORE splitting, so a quotation cannot be cut apart. A second ordering failure surfaced in chat 38 t125: interpret correctly held `awe line -> turn -> teasing line`, but perception rendered `turn -> untoned line -> tease`, softened the smirk, added delivery metacommentary, and duplicated the appearance tail. `_strip_onset_rendering` now keeps the model's ambient sensory prose while removing its copies of declared speech/action; `_inject_onset_sequence` then projects the structured declaration LAST, in exact order, through each element's own hearing/sight/concealment gate, with exact quote bodies, intent-free observable actions, and declared tones. `_inject_visible_actor` recognizes a natural appearance paraphrase before adding its deterministic floor. Upstream, `_interpret_coverage_corpus` includes `tone` and `observable`, so the already represented delivery no longer triggers a redundant repair action. Chronology is therefore plumbing rather than a prompt preference |
| A conversation remembers the job it already did without flattening character | **Built** | Exact-line history answered “did I reuse the words?” and missed “did I make the same offer again?” Live in chat 38, turns 126/127/136/137 repeatedly offered Saturn or dragons and handed the choice back; turn 138 substituted Calufrax while its own deliberation called that an “entirely new destination to break repetition.” `_recent_self_moves` now projects one selected response/goal per turn from immutable active variants across a twelve-turn window, so extra speech lines and fresh proper nouns cannot evict the conversational job. `_first_repeated_move` uses conservative lexical similarity only to open one bounded contextual review, combined with any exact-line or already-spent-intention finding. It is deliberately not a veto: the prompt says the ledger compares completed turns rather than examples within one response, explicitly preserving lists, emphasis, callbacks, invited continuations, and excited in-character riffs or rants. What it rejects is the unmotivated reset — making the same offer, question, or handoff as though the previous exchange never happened. A semantically similar move retained after contextual review is not marked as a stuck-mind signal. `steering_intention_ids` closes the adjacent cause: dormant, blocked, satisfied, and abandoned intentions remain visible as autobiography but cannot authorize a fresh want or response, and commit enforces the same boundary on settled state |
| A declared destination exists, and is reachable | **Built** | Going somewhere is the strongest possible assertion that a place is there -- stronger than naming it, which is why this is keyed on MOVEMENT rather than mention: a character can talk about a city all day without the engine minting it, but the moment a body walks toward one it has to be somewhere for them to arrive. `prepare_scene_commit` used to create the destination ONLY as a side effect of lore staging -- if that turn's mapping happened to stage a `layout` entry -- so a room existed or not depending on whether the lore layer had something to say, and a mover could be sent to a room that was never created. Live (chat 58, t25): movement targeted `alley_mouth`, an ANCHOR inside `street_outside` rather than a room, nothing staged layout lore for it, and nothing was made. The room is now always created, with staged layout lore supplying its description when there is any, AND with an adjacency edge back to where the mover came from -- a room with no edges reads `separated`/`far` from everywhere, which is how an interior falls out of the world. Falls back to the busiest room when the mover cannot be named, because an unreachable destination is worse than an imperfect edge |
| A room created this turn is reachable from somewhere | **Built** | Adjacency resolves BOTH ways, so an empty `adjacent` is fine as long as something points AT the room -- which is why `alley_room` worked carrying no edges of its own. The failure is the stronger one: a room no edge reaches in EITHER direction, for which `spatial_rel` answers `separated`/`far` on every pair, leaving its occupants able to perceive nothing but each other. Live (chat 58): `northern_plaza` was minted with `adjacent: []` and nothing pointing at it, so when the player stepped out of the TARDIS into a plaza whose own description carried shuttered buildings, dripping awnings and the alley a Dalek was grinding out of, her view could offer only the police box she had just left -- the derived dock edge was the single edge the map admitted. She looked around a city and was shown a doorway. `connect_orphan_new_rooms` runs in `merge_scene_with_diff` and attaches such a room to where the bodies stood immediately before the diff. Scoped to rooms NEW in this merge and applied as they are created, because that is the only moment the context to place them still exists -- an established map is never rewired, since the justification for a guess is by then long gone. Interiors are skipped: a `parent_entity` room's doorway is derived by `apply_transit_dock_edges`, and a sealed hull is severed on purpose |
| Dim light is a rendering fact up close | **Built** | `dim` used to make an ADMISSION decision — conceal every region of a body — for what is, at contact range, a RENDERING choice: `_LIGHT_SIGHT` maps `dim -> shapes` and `visual_level_between` applied the verdict flat, distance only ever weakening it, so two bodies in continuous contact in a dim room saw each other as silhouettes (chat 70: kneeling over a body, both hands on it, every region `vantage`-concealed while the surfaces were computed and discarded). The ladder of KIND, not degree (design note 18): dim + measured closeness → full admission with the light as Layer-B prose ("The light is dim." already rides the standing environment percept); dim at range → shapes, unchanged; dark → sight fails at every range, deliberately — touch has its own continuous channel and a carried source is `light_at`'s business. NOT solved with a richer authored vocabulary: 349 of 395 live rooms author no light and 40 write `dim` (the `DISTANCE_TIERS` lesson — data everyone writes and nothing can read, inverted), so the rungs come from light × proximity, both computed. The strengthening evidence is CLOSED and positive-only (`spatial._measured_intimacy`): a standing contact between the pair or station-measured `within_reach` — never `proximity_rel`'s "near", which is the documented no-station-data fallback and would un-dim every ordinary room; never cross-room; never dark. One seam: `visual_level_between` composes it, `region_visibility` stays attribution-only, and every admission consumer inherits. Same beat, same pass: the stranger label's cap-cut prepositional phrase is trimmed to its content head ("the towering hooded stranger with smooth" → "…stranger"), and `contact_sensation` gained the identity floor (`label_for`) — it named the OTHER party canonically, which is what the composer tripwire had been correctly scrubbing every contact beat; the tripwire stays as backstop |
| A mind is never told about itself in the third person, by name OR by the label strangers use for it | **Built** | `_self_second_person` had rewritten a perceiver's own NAME into "you" in their own view since alpha 6.3, and a name is not the only handle the engine puts into circulation: `_unknown_actor_label` mints an appearance descriptor for every body an observer has not recognised, and every mind that receives one writes it back out in its own declarations. Live (three-model playthrough, 2026-08-12): the persona read "A young smith's apprentice with a borrowed sword", the composer minted "the young smith's apprentice", `director_resolve` took it into the OBJECTIVE account ("Bryn turns toward the young smith's apprentice" — of the player, whose name the same paragraph had already used) and the cast shortened it in their surfaces, so the player's own view read "eyes settling on the sword at the apprentice's hip" and the narrator wrote him in the third person. `common.self_reference_forms` is the other half of `self_name_forms`: the exact minted label(s) plus ONE short definite form cut from the head noun, guarded by the labels this observer already uses for other bodies (`avoid`), a generic-head stoplist ("the person" is never a shortening — it is what every stranger label is built from) and no indefinite variant. Applied at the two places engine prose is HANDED to the mind it is about: `perception._composer_self_forms` feeding `composer.act_percept`'s admission-time rewrite, and `narration._ordered_beat_events`, because `event_order` is a second delivery of the same prose to the player. `director._report_observer_epithets` reports the objective-record use back through `tell_director` without rewriting the account; the `intended_target` half is an open admission question (`docs/UNBUILT.md` §1.38). Design note 20 |
| Two identical strangers are told apart in prose, not by an index | **Built** | `assign_stranger_labels` widens colliding labels from the bodies' own appearance summaries, and when the appearances genuinely cannot distinguish them it used to fall to `the person of unremarkable appearance (2)` — an ENGINE device in a layer whose whole contract is decision-free PROSE. Live, in the player's own view, three times in one sentence; one narrator model copied it onto the page verbatim and another paraphrased it away, and neither misbehaved. Now ordinal language (`_ordinal_label`): "the second person of unremarkable appearance". Chosen because an ordinal distinguishes by NOTHING the observer has not already got — they can see three bodies, and counting them adds no attribute, no history and no identity, so the firewall constraint is met by construction. Position and posture read better in one sentence and were rejected: they change within the beat (a referring expression must be stable while its referent moves) and they are separately admitted percepts. Words to twelfth, a numeral past that; the widening ladder is untouched and the ordinal stays the last resort. Design note 20 |
| The narrator is checked against the person it was asked for | **Built** | `_narration_person_counts` was called in exactly one place — on the PLAYER's raw input, to CHOOSE `narration_person` — and nothing read the prose that came back; `_check_player_person` catches the player being NAMED, not a draft written in the wrong person outright. `_check_narration_person_match` reuses the same detector on the output (reused, not re-implemented: it already strips quoted dialogue and folds unterminated quotes). Third-person evidence from the player's NAME only — every other body on the page is legitimately "he"/"she"/"they" — and the dominant person must lead the declared one by 2, the same hysteresis `_resolve_narration_person` uses. Measured before shipping over 2,303 stored drafts with the person replayed per turn: 12 warnings, 0.52%, all real. A WARNING and deliberately not enforceable (a rewrite is a whole narrator call, and person is a whole-draft property). It would NOT have caught the epithet row above — that phrase is neither a name nor a pronoun — and says so in its own docstring. Design note 20 |
| One being has one name (subject identity) | **Built** | A character can be registered cast AND present as a scene entity with its own id, with nothing joining the two records, so the Director writes whichever it reaches for and both are correct. Five separate defects in one investigation were the same consequence — some function compared `"Elyndra"` against `"elyndra_succubus"` with `==`, got False, and did nothing, silently, because every spatial query answers an unresolved subject with its safe-closed default and that is indistinguishable from distance. `same_subject` closed those five and is a FLOOR: it only helps where somebody remembered to route through it, and every new comparison site is a fresh chance to write `==` again. `spatial.normalize_scene_subjects` is the fix — run at merge, before anything resolves one ledger against another, it folds `positions`, `scales`, `attire`, `stations`, `contained` (keys and `in`), `contacts` (actor/target) and `following` onto one spelling per being, after which plain equality is correct because there is nothing left for it to be wrong about. **The scope was the hard part, and getting it wrong was worse than the defect**: the first version folded on identity alone and broke eleven tests, because `positions` legitimately keys objects, fixtures and unregistered presences by entity id and readers resolve them that way — carried lights, derived stations and destruction cascades all stranded. Two rules keep it narrow: fold only when the canonical name is ALREADY live as a subject spelling elsewhere in the scene (the defect is two records for one being, not "ids ought to be names"), and an id differing from its name only by case (`tardis` for `TARDIS`) is its own evidence and does not count. Ambiguity folds nothing — two entities named "A Dalek" are two Daleks, and merging them would be a worse error than either spelling |
| A body sealed inside another body is IN it, not far from it | **Built** | Investigated from a live story with one character fully enclosed in another. The measurement is the whole finding: the relation to the body around her came back `{"same_room": false, "barrier": "separated", "distance": "far"}` — byte-identical to the relation for a window across the room. The engine could not tell the mass she was inside from a draught outside, and every channel therefore read as distance. Four causes. (1) A `positions` value naming an ENTITY rather than a room was accepted silently, because every spatial query resolves an unknown room to its safe-closed default rather than raising, so she sat in a room that does not exist for the rest of the story; `repair_entity_positions` now places the body in that entity's room and records a station AT it, and never infers containment from a typo. (2) `derive_contained_positions` looked its carrier up by SPELLING, so a record naming the entity id found nothing in a map keyed by the display name and skipped, silently. (3) `_body_interior_holder` read only the interior-room form of enclosure while `_hiding_holders` read both, so an occupant got concealment and none of its compensations — conducted sound, flooding scent — and the one voice she was closest to in the world arrived through a wall. (4) `concealed` is symmetric and was standing in for two opposite situations. Now three directions: `inside_source` (perceiver within this source: scent full, voice conducted, sight none), `enclosed_from_source` (perceiver within something else: the room beyond is GONE, not faint), `source_enclosed` (source within something the perceiver is outside: muffled outward, which the barrier rules used to be trusted with and could not do once both sides derived into one room). A perceiver is never sealed from themselves; co-occupants of one enclosure perceive each other normally; and the whole thing is scoped to BODIES via `_is_body_entity`, because a crate is not a mass and opaque is still not soundproof |
| The enclosure directions fire on the paths that deliver | **Built** | The row above built the vocabulary; nothing in production spoke it. `spatial_rel_between` was the ONLY setter of `enclosed_from_source` and `source_enclosed` and had zero non-test callers — the purest form of AGENTS.md invariant 4, a guard that cannot fire — so a voice sealed inside a body reached the whole room at full clarity through both injection floors, an enclosed perceiver heard and smelled the room it was sealed away from, and the comments on `hear_level`'s enclosure branches cited measured live failures the branches could never again catch. It is now THE body-to-body relation builder (with `observer_room`/`target_room` overrides so callers keep their uid-tolerant room resolution): `_source_channels`, the onset perceiver build, the outcome dialogue fallback rel, the micro-loop, `_delivered_manifest` (a voice/breath tell no longer crosses a body seal that muffles the voice itself), and background hearing all route through it. Four masked siblings closed in the same pass, each the same anatomy — a graded fact computed in `spatial.py`, consumed as a coarser projection at the delivery site. The outcome dialogue floor gained the `proximity` the onset floor always passed, via `measured_proximity_rel`, which forwards a tier only when it is a MEASUREMENT — "near" is the fallback in the ~91% of rooms with no stations, and a default must not silence a conversation (the whisper lesson). Sight of an actor is graded by the light in the ACTOR's room: `spatial_rel` stamps the light of the room being looked at, and the onset build and micro-loop passed the arguments backwards, granting a full visual channel to an actor standing in darkness. `visible_adjacent_rooms` gates on `effective_light` — a pitch-dark neighbour's authored description is no longer delivered as literal sight, while spill keeps a lit doorway's cellar visible as dim. And `_audience_map` fails CLOSED on unresolvable geometry, as its sibling `_beat_for_presence` always did and as its own comment falsely claimed it already did. Every fix subtracts; the by-name comm rescue is the one narrowing worth naming — the shape floor no longer pierces an enclosure, because being named by a voice beyond the mass around you creates no channel through it (explicit `medium:'comm'` still does). `tests/test_masked_floor_leaks.py`: 17 assertions fail on the pre-fix tree, 8 over-subtraction guards pass on both |
| An actor sealed inside something is not shown themselves from outside | **Built** | `observable` is the intent-free surface of an act as seen FROM OUTSIDE, and the actor normally receives it in their own view — rewritten to second person by `_self_second_person` — because people can see themselves doing things. Sealed inside something that stops being true: the surface then describes the outside of the enclosure and there is no channel from inside to it. Live: the declared observable described cloth shifting and bulging around a small body, and the actor's own view came back naming the shape she made, in darkness, two clauses after her own narration said she could see nothing. `_self_cannot_see_own_surface` is keyed on being ENCLOSED and deliberately not on darkness or a failed sight check — proprioception is not sight, and suppressing an actor's own conduct every time the lights went out would be a worse error than the one this fixes. Every other perceiver's view is untouched: the surface is exactly what they can see, which is what it is for |
| The touch-only firewall does not fail on a spelling | **Built** | `_touch_only_sources` decides who a perceiver can feel but not see, and its answer is what triggers `_surface_translate_event` — which replaces the omniscient `resolved_event` WHOLESALE, because free prose cannot be security-matched. It compared names with casefolded equality, and one being routinely carries two names at once: a cast display name and a scene entity id. An enclosing character matched as `Elyndra` against a holder recorded as `elyndra_succubus` was not matched at all, so no translation fired and the unfiltered omniscient event — which names the occupant's own interoceptive state in as many words — went into her payload and out into her view. That is AGENTS.md's own-body isolation rule breaking on a string comparison, and it fails OPEN and silently. Every identity test in that function goes through `spatial.same_subject`. **The rule this generalises**: an engine in which one being can carry two names cannot use `==` to decide who anybody is — five separate defects in this investigation were that one comparison |
| An interior does not show you its own outside | **Built** | An entity's `description` is its EXTERIOR -- what a body in the room around it takes in. Handed to its own occupant it reads as a thing across the way. Live (chat 58, t38): the player stood in the TARDIS console room and her view read "...while a blue police box -- its paint darkened by rain -- settles with a heavy thud on the cobbles". The plaza beyond the open doors was correct; the police box was the one she was standing in, landing, seen from inside itself. The engine already knew the relationship -- `_body_interior_holder` resolves a room-parented interior and `spatial_rel_between` sets `inside_source` from it -- but that flag only ever conducted SOUND, and nothing withheld the exterior. `_perceptible_entities` now drops `description` for an entity whose interior the perceiver is standing in. Only the outward appearance goes: the entity itself stays, because presence is not the leak and the room's own `parent_entity` already says what you are inside |
| An act that happened reaches the page | **Built** | `event_order` is described to the narrator as "the engine's numbered record of what actually happened this beat", and for everyone except the player it was speech-only: `_ordered_beat_events` collected `type == "speech"` from every character's declared sequence and silently discarded `type == "action"`, so no physical event a character performed was ever listed. Live (chat 52, t26), across three rerolls: the Director resolved one character carrying another downward, perception delivered the direction correctly ("a steady pressure that pulls you downward"), and all three narrator drafts dropped it — the beat's only physical event reached the last stage as one clause buried mid-paragraph in the view, competing with the room's furniture, carrying `fidelity: "ambiguous"`, with nothing anywhere requiring it to survive. Two of the three also *halted* an ongoing motion the view said was continuing ("pauses mid-stroke" against "moving in a slow circle"). Acts now enter the record, gated on `visibility == "overt"` and the `_player_sees_character` test `co_present_positions` already uses, carrying only the Director-authored `observable` surface and never the private `attempt` with its intent and appraisal in it. Fails CLOSED with no scene or no player room. `_check_action_direction` backs it deterministically at two confidences: a REVERSED direction is enforceable, an absent one is a warning only, because correct prose can carry a descent with no directional verb in it |
| A background presence is somewhere | **Built** | `canonicalize_positions` folds a uid position key back onto the display name only for a REGISTERED cast character, and says so — "unregistered background presences are left untouched". Correct, since they are not cast; but nothing mapped the name back the other way, so a presence placed under its entity uid was unreachable by name from the moment it was placed. Every reader asking where a background speaker stood got None, and `spatial_rel(None, room)` answers "remote, no known spatial channel". Live (chat 58, t23): a machine in the player's own alley with its weapon trained on her chest sat in `positions` under `40af0ac4bf2644a1`; `cast_room` returned None, perception's hearing gate classified it as remote and dropped its line for every observer, and the view rendered it as "something" and "the source" rather than the thing she had just thrown a rock at. Corpus-wide, 47 of 78 background lines never reached a single view. `cast_room` now falls through to `entity_room_by_name`, matching `scene.entities` on name first and aliases second so a nickname cannot outrank a real name, and resolving an ambiguous name to NOBODY — two of the same machine in two rooms is precisely the case that must not be guessed, and a wrong room is worse than the None they all used to get. A background presence's ACT also reached no record: `_ordered_beat_events` read only `dialogue_log_entry` from a reaction, never its `action`, whose shape (one prose string, no `observable`/`visibility` pair) the character path cannot see. It is now collected under the same perceptibility gate. What the presence is CALLED is still wrong — see `docs/UNBUILT.md` §1.19 |
| The Director can see what the engine did | **Partial** | `scene.contacts` and `scene.stations` now reach the resolve payload — a stage asked to maintain a ledger it cannot see writes fresh every beat rather than re-asserting, which was the cause of the contact drift alpha 6.3 repaired downstream. `ctx.tell_director` carries the deterministic layer's READING of a beat's output onto the next beat's `engine_notices` (a re-described contact taken as the same limb moving; an attire note taken as dressing someone). Partial because coverage is thin: `_evidence_present` has not been audited category-by-category against what commit actually reads, and most silent discards still say nothing |
| Within-room position (stations) | **Built** | `scene.stations` {name:{at:anchor_id|null, near:[]}} against per-room `anchors`, deriving `proximity_rel` (within_reach/near/across), co-located left/right (`entity_side`), the rear-arc blind spot (`entity_arc`), whisper range, and surface comfort. Designed in Phase 2 and **inert in production until alpha 6.3**: `stations` was declared on neither `StateDiff` nor `ScenePatch`, so Pydantic's `extra="ignore"` deleted the field before `merge_scene_with_diff` — which has always merged it — could see one. Measured: 0 of 45 live scenes carried a station while 17 model outputs across the same database contained one the schema had thrown away, so every co-located pair read `near`, `entity_side`/`entity_arc` returned `None` universally, and a body lying on a bed drew no warmth from it. `RoomDef` declared neither `anchors` nor `size` either, so the Director could not author, update or preserve an anchor and the only anchors any story had arrived through the mapping stage's untyped patch dicts. Because models fill contact reliably and stations essentially never, `spatial.derive_scene_stations` seeds the ledger from the one they do maintain: a contact with an anchor-backed entity stations that body there, a body-to-body contact makes a mutual `near` link. Additive, idempotent, never argues with an explicit statement, and a derived station outlives the contact that produced it — you do not leave the bed by taking your hand off the quilt — while a room change still clears it. "On the bed" is a station AT it plus a contact WITH it plus that body's own `state.posture`; no fourth ledger |
| One limb, one place (contact identity) | **Built** | A contact is keyed on (actor, actor_part, target, target_part), all free text the Director writes fresh each beat — so a re-description read as a second limb. Measured over 17 live beats: `thumb→ear` became `thumb→ear_base`, `hand→waist` became `hand→side`, `tail_spade→calf` became `tail→ankle`, and the character was told as standing truth that one woman had two hands and two tails on her. Fixed by reading an unqualified part noun as a definite description: `spatial._part_identity` splits a part into (kind, instance), `_same_appendage` recognises a refinement that repeats the limb's own word (`tail spade` is that tail; `thumb` is not a `hand`), and a fresh spot for the same limb RETIRES the old one. Two carve-outs keep the range: anything asserted in the SAME beat stands (two hands are said in one breath), and a bare noun never displaces a qualified limb nor the reverse — once the fiction has distinguished her left hand from her right, losing the distinction is worse than carrying a hold ageing will retire anyway. Contacts gained a bounded `detail` ("beneath her shift", "feather-light"), which is what the parts alone could not say and therefore what the Director had been smuggling into entity `state` |
| Contact has exactly one record | **Built** | `contacts_from_entity_state` lifts contact out of an entity's own `state` and deletes it, so the ledger is the only account — but until alpha 6.3 it required the contact verb in the KEY NAME and the value to slugify to a bare person, and every contact assertion in the measured story evaded both (`hand_position: beneath_Hinami's_shift_caressing_bare_side`, `tail_spade: curled_around_Hinami's_ankle`, `lips: trailing_kisses_along_Hinami's_jaw`). Entity state neither ages nor prunes, so all of them stood contradicting the ledger for the rest of the scene — one mouth simultaneously two inches away, trailing kisses along a jaw, and kissing. Pattern B now lifts a verb found in the VALUE when the key names the part, with a direction guard so `leaning_over_X` stays the bearing it is and `gaze` is never touched; leftover words survive as `detail` rather than being deleted with the key. Lifted holds go through `apply_contact_ops`, so they obey displacement too. Pattern C drops a relational key (`lips_distance`) only where a standing contact already speaks for that part: the ledger ages and prunes, entity state does neither, so the ledger is the record — and a key nothing contradicts is left alone, because dropping it would be inventing an absence |
| A garment is one garment (attire identity) | **Built** | The wardrobe keyed garments on `name.casefold()` and the Director writes names fresh, so a redescription forked the garment: measured live, `"sheer obsidian silk robe"` against a registered `"sheer obsidian silk robe that parts with every movement"` left one body wearing two robes across four regions, one of them halfway off because the reconciliation was adding one back while removing the other. `attire.resolve_garment` resolves every incoming handle against what the body already wears in four narrowing tiers (exact, article-stripped, phrase containment, then head noun only when exactly one worn garment carries it — an ambiguous handle resolves to nothing rather than a coin flip, so a silk robe and a cotton robe stay two robes), and `dedupe_regions` heals an existing fork on READ, so the ~49 stored scenes repair lazily rather than through a migration that would rewrite stories mid-play. The fork's actual trigger was `app.attire_put`: the region editor stored the browser's body verbatim, so a hand rename left `wearing` naming the old spelling — it re-derives all three representations now. `flat_state` names a spanning garment once, as `flat_wearing` and `newly_removed` already did |
| An off-schema clothing change is read, not dropped | **Built** | `StateDiff.attire` had an untyped inner dict and `commit.py` reads exactly `wearing`/`add`/`remove`/`replace`/`state`/`conditions`; every other shape validated cleanly and then changed nothing. Two of the six attire diffs in the measured story were silent no-ops, one of them `{"shift": "linen shift, hem rucked up where Elyndra's hand slipped beneath"}` — which is why that story's narration described the hem of a shift and the waistband of a pair of shorts in one paragraph, the ledger still holding the travel clothes seeded off the card. A typed `AttireDiff` now canonicalizes through `attire.coerce_diff_shape` (also run at commit, because rerunning a stage replays diffs stored before it existed) and `commit.interpret_attire_notes` reads an unrecognised key three ways: a garment she wears → what just happened to it; the wardrobe as a whole → prose the body keeps, unless it says nothing changed; a garment the ledger has never heard of → she is wearing it now, with the one-rung rule and region tables applying as normal. `AttireState` also gained `regions`, undeclared until now — so the opening turn's authored garment descriptions and `beneath` text, the richest clothing detail any story gets, were stripped by the validation round-trip on every body in every story |
| Establishment states one moment, not a passage | **Partial** | An opening scenario usually narrates a SEQUENCE — a character-card greeting always does, since that is what a first message is — and the `director_establish` prompt was written end to end as if it described a standing situation. Nothing said which instant is t=0, so bodies froze at different ones. Live (chat 53, "Run!", five beats: cornered / rescued / hauled inside / lever thrown / turns to look): the player stood mid-motion at the doors from beat 2 while the character stood at the console with the lever already thrown from beat 4, and the creature the whole opening was about kept a present-tense "weapon charging with a rising whine" from beat 0 — a vortex away, in no room, its charge still rising. The prompt now names the last moment as the one being established and requires positions, stations, postures, activities, entity `state` and transit phase to agree with it; anything the passage finishes is past, recorded as consequence in `world_facts`, never as an in-progress posture. **Partial** because a prompt rule is unverifiable from source: the two structural halves below are the parts a test can hold |
| An agent the opening declares has a room | **Built** | `semantic_output_errors("director_establish")` checked exactly two things — rooms non-empty, positions non-empty — so an entity could carry a full description, a live `entity_states` entry and the scene's only open `world_pressure` thread while appearing in `positions` nowhere at all. That is not cosmetic: `agents/background.py` drops an unplaced presence by construction ("cannot prove co-presence, leave out"), so it can never be perceived and never acts, while the pressure ledger keeps demanding every later beat advance a threat with no location. `schemas._unplaced_establish_entities` now fails the step. Scoped by an ALLOW-list of animate kinds, deliberately the opposite shape to `commit._INERT_ENTITY_KINDS`, because a semantic error here aborts an opening after one repair and the fallbacks: measured across all 48 live scenes, 17 carry an unplaced non-portable entity and 53 exist in total — framed diplomas, a shoe rack, a captain's chair, a bell tower, ward doors, a day-room television — so a deny-list would have killed a third of openings to tidy furniture. The allow-list yields exactly one hit in that corpus, and one in 57 stored `director_establish` variants: the creature |
| An opening can express a hold | **Built** | `DirectorEstablish` had no way to say two bodies are touching, so a greeting whose entire event was a hand seizing a wrist and hauling a body through a door committed with `contacts: []` — the grab had never happened, and the body it moved had never been anywhere else. `contact_ops` is now declared on `DirectorEstablish` (undeclared is deleted by `extra="ignore"`, the failure that kept `stations` inert for 45 scenes) and routed by the establish tail into `state_diff.contact_ops`, so it reaches `spatial.apply_contact_ops` through the same merge every later beat uses — including `derive_scene_stations`, which reads fresh contact ops. Only holds still true at the chosen moment: a hand that grabbed and then let go is a `world_fact`, not a contact |
| Arriving inside something is not entering it | **Built** | `infer_threshold_crossings`' enclosure branch fires on `was_hidden != now_hidden`, and on the opening turn `prev_scene` is empty — so every body standing in any interior read as having just climbed into it. Live, that gave BOTH occupants of a vehicle a `{from: X, to: X}` crossing, including the one whose vehicle it was and who had not moved. Requiring a previous position fixes it for the same reason mid-story: a body that joins the cast already enclosed was not watched going in, because it was not there to be watched. Inert in effect — a crossing only ever *floors* sight — but it was the engine's sole trace of anyone entering anything, and it was fabricated |
| Multi-room movement (running) | **Built** | `spatial.sprint_reach` bounded by decision (one way onward), not sight; `spatial.passable_path` reconstructs the rooms crossed so a sprinted corridor is remembered; `agents/character.sprint_offers` truncates the *offer* to known ground. Per `docs/DESIGN_RUNNING.md` |
| Retrieval as perturbation (unbidden recall) | **Built** | `memory.contrast_memory` surfaces one high-salience *dissimilar* memory when deterministic stuck-ness signals fire; confidence-blind, edge-triggered, substitutes for one ordinary recall slot. Adapted from SIGMA SRIP-14 §XXII — see `docs/RESEARCH.md` §1.5. Dissimilarity was structural only (tokens, location, entities, turn distance) until alpha 6.3.1, correctly: on a crc32-embedded corpus cosine is a fuzzy-lexical signal and would only have restated the token penalty. Real vectors say what the token axis structurally cannot — that "the alley smelled of wet brick and chip fat" and "the backstreet stank of damp masonry and frying grease" are the SAME memory, not a perfect contrast — so a semantic term joins the structural one. Gated on 90% model coverage of the bank, and that gate is not optional: an incomparable row scores 0.0, which in ordinary recall is a silent omission but on an INVERTED axis reads as maximally contrasting, so unbidden recall would preferentially surface exactly the memories not yet rebuilt. A story mid-rebuild degrades to the old behaviour rather than to a wrong one |
| A summary keeps first-hand, hearsay and surmise apart (P8) | **Built** | Consolidation melted every provenance into ONE autobiographical string fed back wholesale each turn, so a belief the character *inferred* came back a few turns later indistinguishable from something they had *witnessed* — belief laundering into knowledge inside a single mind, the same layer collapse the engine polices between minds. `_PROVENANCE_SCOPE` routes the six provenance classes to three scopes (`witnessed`/`remembered` → autobiographical, `heard`/`told`/`read` → hearsay, `inferred` → surmise), each its own `memory_summaries` row, each reaching the character under its own label (`what_i_experienced` / `what_i_was_told` / `what_i_concluded`). Three rows rather than a provenance tag per sentence, because the summary is model-written prose and a tag inside prose is a convention the model can drop — a separate row cannot be. The first-hand row is written even for a window that produced nothing first-hand, because its `end_turn_idx` is the consolidation cursor; skipping it on a hearsay-only window re-consolidates the same memories forever |
| A character can distinguish remembered past from the present | **Built** | Present observations use `current:<perceiver>:<n>` (micro-rounds add a nonce); raw memories use `event:<hash>` and summaries `summary:<scope>:<end-turn>`. Current view/mood/goal no longer appear under `memory`. Model-visible rows are an allow-list with explicit `temporal_status`, `memory_form`, relative `when`, and `epistemic_origin`; database ids, access counters, archive/vector metadata and scores stay host-only. Output is physically split into `present_evidence_used` and `memory_evidence_used`; appraisal has separate present evidence and past `memory_modulation`. Grounding drops cross-lane/invented refs, forbids derived summaries from independently reinforcing durable state, and requires present support for nonzero somatic/goal/relationship changes. A recalled danger or pleasure can still create a realistic mild echo: grounded `somatic_echo` and `threat_bias` are capped to 0.2, persist for one beat as `active_state.memory_echo` with `temporal_source: remembered_past`, and cannot become current pain/pleasure, injury, goal impact, or proof of danger. Controlled chat-38 result after one deterministic phrase-scoring correction: semantic answered 7/7 vs lexical-only 5/7 with 100% grounded citations; semantic retrieval reached relevant evidence 5/5 vs 2/5 and earlier windows 5/5 vs 0/5. |
| A character can deliberately recall without making recall a default action | **Built** | An exceptional private `{type: "ponder", query, why}` sequence item is normalized out of the public action stream, so the Director, perception and narrator never treat thought as conduct. Commit stores one bounded query on that mind; its next character turn runs a four-item `deliberate_recall` lane on top of unchanged normal recall. Results carry `retrieval_origin: deliberate_ponder` (or both normal and deliberate origins when the same row was already reached), then the old query is consumed. A concrete reason is mandatory and ponder is absent from the default output shape. A result may raise a genuinely new query immediately; merely receiving results is explicitly not a reason to do so. |
| Psychology spends memory bandwidth honestly | **Built** | `cognitive_absorption` narrows deliberate recall from 12 recent / 16 old / 2 windows to 8/8/1 and then 4/4/0, preserving a small automatic-recognition lane rather than making pain or pleasure cause amnesia. Past can modulate familiarity and coping in bounded form, but cannot author present novelty, bodily sensation, or goal impact without current evidence. `remember_lines.why` survives minting; disputes address a stable delivered ref with present cause; `memory_effects` distinguishes retrieval from influence and feeds unbidden-recall outcome telemetry. All fields accumulate across dialogue micro-rounds. |
| The character contract asks only for what commit reads | **Built** | The 2026-08-11 output audit measured, on 401 recent-era stored calls, two dice-class transcriptions in the template and cut them. Ten stress/hedonic fields were requested where commit reads two — `hedonic.released` (the discharge declaration, rightly the character's own) and `stress.coping_mode` (a pass-through label) — and `psychology_runtime.resolve_stress`/`resolve_hedonic` recompute the rest from the appraisal plus prior state; the dicts were emitted on 71% of calls at a mean 78 tokens of which ~12 were signal. `active_state.goal` was overwritten with `wants[enacted].want` on 99.0% of calls and matched it only 16.2% of the time. The template now asks for `stress:{coping_mode}`, `hedonic:{released}` and no goal; `agents/common.declared_goal` is the single derivation every raw-variant reader goes through (the moves ledger, commit's unbidden "did the goal move" check), commit's malformed-wants fallback keeps the PREVIOUS goal rather than blanking a standing aim, and legacy emissions stay schema-valid and read identically. Proof standard: a legacy full-shape result and a slim one commit byte-identical character state (`tests/test_character_contract_slim.py`). The observation wrapper got the same treatment on the input side: six near-constant fields (intensity at its 0.35 base in 99% of 1,692 stored observations, suddenness/fidelity 99%, ambiguity 89%, `source_atom_id`/`perceiver_id` 100% redundant, ~356 wrapper tokens against ~188 of text) are omitted at their resting defaults (`composer.OBSERVATION_DEFAULTS`) — absent means the default, ids/text/channel never trimmed, non-default signal kept byte-for-byte. `considered_responses` is deliberately NOT cut: engine-unread but plausibly chain-of-thought; a `contract_bench`-style A/B is the gate (docs/UNBUILT.md §6.9) |
| A second model call says it happened | **Built** | The repair ladder (`llm_quality.complete_validated_json`: truncation re-ask, temperature-0 repair, per-candidate fallback) and the character stage's decision-review retry each re-issue a full provider call, and a retry that SUCCEEDED left no stored trace — so the invisible-second-call rate could only be bounded from its failures (14 "repetition retained" notes in 401 recent-era calls, a floor of ≥3.5%, true rate unknowable, with the live benchmark's 1.25–1.50 provider calls/turn against 1.01 stored results/turn leaving ~8–15s/turn unattributed). Every rung now writes one warning line — which path fired, and its duration — through `pipeline_context.current_warning_sink`, set by `agents.runtime.compute_step` beside `current_step_key` so a note raised deep inside `llm_quality` is attributed to the running step and rides the stored variant's `_engine_notes`; outside a pipeline step the sink is unset and noting is a no-op. The audit's order of operations stands: measure with this before designing any bounded-delta retry |
| Implicit prompt caching gets a replica to land on | **Built** | Explicit cache markers exist for Anthropic models only (`_anthropic_system`, `_openai_system_message`); everything else relies on provider-side implicit prefix caching — and Fireworks documents that theirs works **within one replica**, with serverless routing scattered unless the client hints placement via the standard OpenAI `user` field or an `x-session-affinity` header. Uncached, a character call re-prefills the ~15.5k-token role prompt plus ~8–11k of payload every time; cached input is discounted 50–90% (Fireworks' GLM-5.2 page: $0.14 vs $1.40/M) with TTFT reduction up to ~80%, so whether the hint lands is worth more than most output-side trims. `_apply_cache_affinity` adds `user: "sonder:<role>"` on both OpenAI-compatible body builders (sync and async; the SSE paths consume those bodies). **The value carries no content and no identity** — an engine role constant, never a chat, character, or input-derived string, because this field goes to a third party on every call. Role-only rather than chat+role, deliberately: the character prompt is name-substituted 32 chars in so cross-character sharing is nil either way, one replica caches many prefixes, a single-host engine's per-role traffic is far below one replica's capacity (measured 1.01–1.11 character calls/turn), and the retry paths inherit the same replica for free. Fail-closed opt-in via `cache_affinity_allow` (name or kind, the `prompt_cache_allow` idiom) — unset means every request is byte-identical to before — and the 400-retry strips the field rather than losing the turn to a host that rejects it. Measurable end-to-end without new code: both SSE paths request `stream_options.include_usage`, `_normalize_usage` reads `prompt_tokens_details.cached_tokens` (the Fireworks dialect) beside the Anthropic fields, and `_log_usage` logs `cached_tokens`/`cache_write_tokens` per call — writes with no subsequent reads is the signature of a prefix that is not stable. NanoGPT documents implicit caching for "OpenAI and Gemini model families plus many open-source provider/model routes" and explicit control for Claude only; whether GLM routes (TEE especially) cache is UNCONFIRMED — the hint costs nothing there and the usage log answers it empirically |
| Checkpoint / rollback | **Built** | `checkpoints.py`; branching depends on it. A checkpoint is a full PRE-turn snapshot, and it used to carry every memory's two float32 vectors inline -- so the same vector was re-stored on every turn for the life of the story. Measured on a live database: checkpoints were **94.5% of a 4.4 GB file**, `memories` was 98.9% of each checkpoint, and the vectors were 96.9% of that. One story held 40,224 memory copies across 118 checkpoints and **529 distinct by content** -- 76x duplication of 1.00 GB that needs 13 MB. Vectors now live once in `memory_vectors`, addressed by `memory.vector_address` — `v1:` plus a sha1 over the vector BYTES — and the checkpoint keeps a reference. It was briefly `sha1(char_id, content)`, on the reasoning that a vector is a pure function of the memory; it is, but not of its `content`, and the compaction verifier caught the collision in production (checkpoint 855 of chat 36 held "You are in Ten Forward." at turn 42 and again at turn 44, same character, two different payloads). Byte-addressing makes a collision impossible by construction rather than by assumption and still deduplicates 69x. Nothing is re-embedded: this changes where the bytes live, not what they are. Real conversion: **448.6 MB -> 44.0 MB (10x)**, 14,820 vector copies to 300 distinct, 0 unmatched. |
| Compaction cannot lose a memory | **Built** | Rewriting rollback history is the one maintenance job where a silent error is unrecoverable, so losslessness is enforced rather than intended. Work happens per STORY on an in-memory duplicate; every checkpoint is compacted into a candidate while the stored blob is untouched; each candidate is verified field-by-field against its original -- every top-level key, every memory entry, every scalar, and every vector reference **resolved back to the exact bytes it replaced** (`_verify_no_loss`), which is the question a restore will ask. Only if EVERY checkpoint in the story verifies are vectors and blobs written, in one transaction. Any failure names the story, discards its candidates, leaves its originals byte-identical and moves on -- proved with injected loss: `cannot compact 'Corrupt Story' -- entry 2 resolves to different vector bytes`, originals unchanged, and zero vectors written for it. The duplicate is held in memory rather than as a cloned chat: same guarantee, without copying a gigabyte, and with no half-written copy to clean up if the process dies. It also refuses to start when there is no legacy data -- a no-op run still walks every checkpoint and takes the write lock per story, and on this path the safest run is the one that does not happen. |
| Consolidation, salience-weighted hybrid retrieval | **Built** | `consolidate_character_memory`; keyword + embedding search in `memory.py` |
| Which mechanisms actually fire | **Built** | `tools/fire_rates.py` — per-mechanism fire rate over the corpus, `--last N` per chat, read-only. Its discipline is the DENOMINATOR: `memory_disputes` against every memory row reads 0 of 6,480 and means nothing, because the field did not exist for most of that corpus; against the beats that could have carried one it reads 0 of 181, beside a sibling introduced in the same commit, on the same 181 results, firing 78%. A mechanism with no opportunities reports `no chances`, never 0%. Four mechanisms in this engine were built, documented, tested and never ran once, and none looked dead from reading the code; three were found only because somebody went looking by hand. This is what makes that cheap. It found a fifth on its first run — see the project tier row |
| Salience discriminates the same amount in every bank | **Built** | `memory._rank_normalized_importance` rank-normalises `effective_importance` across the rows a search can see, inside their own p10-p90: ordering and influence budget both hold, only the gaps move. Measured first (`tools/salience_replay.py`, 270 real recalls, top-16 membership moved): term deleted **35.2%**, percentile-normalised to [0,1] **59.6%**, stretched 3× **47.0%**, respaced **15.2%**. So the term was never decoration, and both planned fixes for the measured compression (p10-p90 spread 0.27, 70% of rows in 0.6-0.8) moved retrieval MORE than deleting it — values in a 0.27-wide band mapped onto [0,1] gain ~3.7× the influence while reordering nothing, a weight change wearing the word normalisation. The defect actually fixed: discrimination depended on how the minting model happened to spread its numbers that day. Callers asking an absolute question (archiving, contrast) still read `effective_importance` |
| A memory that turned out to matter is found | **Built** | `commit._cited_memory_ids` reads mind-model evidence, belief evidence, and `memory_effects` with disposition `integrated`. It read only the first until 2026-08-03, which is why importance had been revised on 9 memories of 6,480: measured over the 83 results that could supply any candidate, mind-model evidence citing a stored memory fired 6, belief evidence 1, `memory_effects` **74**. The one field being read was the rarest thing a character emits. `resisted`/`dismissed` still do not count (pushed away is not turned out to matter) and `only_unrevised=True` still holds each row to one lift for its whole life, so this widens the population, never the amount |
| A mind can re-read what a memory meant | **Built, never occasioned** | The wire is proven end to end by `tests/test_dispute_reachability.py`, which builds the occasion the corpus never produced — a stranger remembered as kind, seen this beat picking a pocket — and walks a model-shaped dispute through schema coercion, grounding, the commit collector, `record_dispute` and the projection back to the mind, including its three refusals. So 0 of 181 is an absence of occasions: nobody in these stories has been deceived. The prompt was the other half — two prohibitions and one abstract permission, beside `memory_effects` at 89% which names four concrete occasions. CLAUDE.md records the same shape twice from the maze arms: bare prohibitions invert. It now names five |
| A summary clause says what stands behind it | **Built** | `memory_summaries.support` (schema v25), one entry per clause as `{claim, support_refs, epistemic_origin}`, derived host-side by content-word overlap against the window's own memories at consolidation — no model call, because an audit trail produced by the same kind of process it audits is not one. Scoped to the summary's own epistemic class so a first-hand clause cannot be supported by hearsay; `epistemic_origin` is left blank rather than defaulted when nothing supports it. Refs are `event_key`s, so rollback and branching need no remapping. An empty support set is the finding — the clause generalises, compresses, or was invented, and it is now countable. Summaries cannot reinforce durable belief, which contains most of the danger, but they move appraisal and speech and used to leave no trace when they did |
| What a character keeps, measured before it is limited | **Built** | `tools/remember_lines.py`, over 1,633 turns and 146 marks: **0 of the 125 that became rows** would have been caught by the fixed phrase list, and marked lines are retrieved later at **30.4%** against 9.3% for every non-dialogue row. No overlap with the list at all, 3.3× the baseline yield. A budget and a novelty gate were both considered and refused on those numbers. `why` is present on 146 of 146 marks and so predicts nothing — a constant is not a signal. The discriminator needs no schema change: the phrase list is a pure function of the quote, so a kept line it would have rejected is one only this character preserved |
| A traveller remembers where they have been | **Built** | `frames.is_memory_visible` honours the travellers list of the frame a memory was FORMED in as well as the one the character is standing in. It checked only the latter, and the present is the implicit frame — `frame_id is None`, no row, synthesised by `get_frame(None)` with an empty travellers list — so that clause could never fire in the present: a character who visited the year 5000 and walked home could not recall one moment of it. Everything while standing there, nothing once back where they live. Safe to widen because every caller arrives through `visible_memory_rows`, which has already filtered `char_id=?`; the only question this rule answers is whether a mind may reach its OWN experience. A native of the present is not a traveller of the future frame and still sees nothing. Five time-travel shapes covered in `tests/test_time_travel_memory.py` |
| How much a mind holds at once is authored | **Built** | `psychology.capacity` — `narrow / focused / ordinary / broad / wide` — scales the want and intention caps (1/2 to 5/6) and narrows one further at the top of the absorption range. Measured cause: the want cap binds **79.6%** of live banks at mean 2.65, so it was not a safety valve catching an outlier, it was the shape of every character's attention, authored once by whoever picked 3. Precedent is `theory_of_mind.sheet_capacity`. `ordinary` is exactly the pair that shipped and unset is stored as `""` rather than backfilled — backfilling made "the author chose the middle" and "nobody has seen this field" the same value and silently killed the import warning written to prevent that. The character is told its own ceiling (`self.attention`) rather than having wants culled without being told the decision existed. **Projects stay off the ladder**: `PROJECT_CAP` is a dramatic limit, and six slots would lose the displacement rule that makes one mean anything |
| Commit as sole persistence boundary | **Built** | `commit.py`; one outer transaction, any domain failure rolls the turn back |
| **Player action absolute** | **Built, then deliberately exceeded** | See [Player authority](#player-authority) — a considered product divergence, not drift |
| **Event-linked stance axes** | **Partial** | `trigger_event_ids` accepted but **optional**; relationships live in a `world` KV blob with no change log |
| **Canon lock** | **Partial** | `lore_entries.canon_locked` is settable via the API and chat-canon entries auto-lock after 20 turns; the specified repeated-reference lock rule is not implemented |
| **Scene-boundary coherence pass** | **Partial** | Validation and dedup exist throughout commit; the specified retcon protocol is not implemented as such |
| **Off-screen world ticks** | **Partial** | The low tier is built as specified. The `stochastic` rung is a real seeded draw against standing intentions (`offscreen.stochastic_ticks` — `random.Random(seed)`, no model call, same seed same ticks) taken on one frame-scoped `offscreen_epoch`. The `reactive` rung stores only grounded same-beat declarations and later fires only pre-adjudicated effects. Fired mechanics rows promote into checkpoint-safe `world_events`; physical C carriers expose public surfaces only to actual holders. The paid `character_agent` ceiling is built end to end: a card must explicitly opt in via `simulation.offscreen_agent`, `full_agent_candidates` selects a dormant mind only for its own active plan or carried evidence newer than its last paid tick (bounded by the actor cap, reading no player/omniscient content), and `offscreen.schedule_agent_ticks` runs one reduced turn per candidate out of band — the fail-closed `agent_context`, one character call, one Director adjudication whose consequence passes `mint_consequences` into `scheduled_events` under a stable id, and one atomic landing (own-trail movement, plan advance, log record, event-keyed autobiographical memory) guarded by epoch, base turn, and a per-subject `last_epoch_id` stamp so a reroll or restore replays rather than duplicates. Epoch, plans, carriers, and provisional logs all follow restore/frame boundaries, and fire-rate denominators are retained. Courier/letter carriers are built (`couriers.py`: engine-minted anonymous riders with positions on `passable_path` routes, clock-driven movement, a perception surface, and question/silence interception that actually stops delivery). Caravan and artifact carriers are built on the same physics (a `stops` list on `courier_ops` makes the body a caravan — it dwells at each stop on the clock and trades news both ways with the standing crowd, surfaces and notices; `artifacts.py` makes a claim physical — posted where the poster stands, acquired only by reading, stopped by tearing down, worded out of band by the rumor-ledger ceiling). Still open: re-contact settlement — `docs/UNBUILT.md` §2.8 and `docs/PROPOSAL_ARCHITECTURAL_COMPLETION.md` |
| **Player authority modes** | **Stub** | `PlayerAuthorityMode` enum exists in `schemas.py` and is **consumed nowhere** |
| **Predictive staging** | **Not built** | No pre-staging of lore or NPCs for likely-next locations |
| **Reactivation negotiation** | **Not built** | No gap-history / delta-summary proposal, refusal caps, or "stalemate eats canon" |
| **Session digest** | **Not built** | No end-of-session synthesis for resume |
| **Living world — the five state-producers** (`docs/DESIGN_LIVING_WORLD.md`) | **Floors of A–E built; C's and E's ceilings built; A/B/D ceilings open** | `living_world.py` carries the settings ladder for all five (declared/built split per the `OFFSCREEN_LIFE_BUILT` idiom; all default off, opt-in per chat via `/api/chats/{cid}/living_world`). A recomputes routine/entropy/occupancy at contact. B mints validated scheduled consequences and fires them deterministically. C's first physical carrier floor copies only a non-empty public `witnessed` surface to a registered character actually co-located with the fired event; the frame-specific envelope follows that holder's real movement and only their private agent receives it. Sharing a room does not grant it to another mind. D accumulates durable place obligations before arrival. E stores only same-beat, character-declared plans and deterministically fires their typed pre-adjudicated stages. C's courier/letter layer is built (`couriers.py` + `StateDiff.courier_ops`: dispatch from a holder's own hands, movement on the clock over the shared passable graph, interception and silencing that stop delivery); C is now complete through its ceiling: caravans ride the courier object with stops, dwelling and two-way news exchange; `artifacts.py` notices are posted from a holder's own hands, acquired by explicit reading (provenance `read`, a copy not a mouth), destructible so a torn-down bill informs nobody, and worded by one small out-of-band call that lands only while the bill still stands. The A/B/D model-assisted ceilings remain open; E's adaptive `character_agent` ceiling is built (`offscreen.schedule_agent_ticks`): one reduced Director-adjudicated turn per opted-in candidate, acting only on character-owned carrier evidence, landing atomically under epoch/base-turn/per-subject guards. The off-screen ladder is the single authority ceiling over all five; `effective_depth` clamps both axes at read time, and the settings UI renders the engine-owned truth |

---

## The engine as built

### The spine

Information flows one direction, enforced as plumbing rather than prompt:

```
        ┌──────────── player intent (up) ────────────┐
        │                                             ▼
PLAYER → PERCEPTION → CHARACTERS → DIRECTOR → PERCEPTION → NARRATION
(acts)   (filter the  (react,      (resolve   (filter the   & CHARACTERS
         player act)  blind to     to one     resolved      (render/remember)
                      each other)  state)     state)
```

**Eyes severed from hand.** Perception flows *down* to the player through the
narrator; intention flows *up* from the player to the director, never touching
the narrator. In a single model the narrator is both eyes and hand — it
describes the world *and* authors what you do — which is why such systems put
words in your mouth. Here the narrator is downstream of your eyes and has no
access to your hand. It can make you *feel* anything and *do* nothing. That
severance is what makes it safe to give the narrator a lush, interpretive voice:
flavour in the perception channel cannot leak into the action channel.

### Turn shape

Exact stage order lives in `docs/PIPELINE.md`. In brief:

**Opening turn** — `mapping_stage → director_establish → perception_establish →
narrator → commit`

**Normal turn** — `director_interpret → mapping_stage|mapping_quick →
perception_act → [reaction_loop] → [interaction_loop | parallel character:<id>]
→ director_resolve → background_react → perception_outcome → narrator → commit`

Every stage's output is stored as a `steps` row plus an immutable `variants`
row, with exactly one active variant. That dual representation is what makes
reroll, rerun-from-stage, manual editing and inspection possible — and it is why
the engine can be audited at all.

Auditable is not the same as legible, and the gap between them is measurable in
diagnosis time. A stored step is a JSON blob, and the two things hardest to see
in one are the two the engine does most: a perception stage emits one view per
mind keyed by cast id, where a view missing a whole sensory channel looks
exactly like a view that is merely shorter; and three of the plan's pairings run
concurrently, which `steps.ord` cannot express, so a simultaneous pair reads as
two sequential steps that happened to be quick. The pipeline drawer therefore
reads a per-perceiver step one mind at a time (named, with that mind's derived
observations beside its prose, raw JSON one click away), and every step carries
an `_engine_notes` record of what the deterministic layer repaired in it, which
steps it ran beside, and — `llm_calls` — every provider call the step paid for
({step_key, role, requested, served, in, out, cached, duration, kind}), so a
slow stage explains itself from the stored variant instead of from a stderr
line that died with the process.

### Ownership

Authority ends sharply. No agent overrules another in-domain.

| Agent | Owns | Must never |
|---|---|---|
| **Director** (`agents/director.py`) | Objective causality: interpreting the declaration, resolving outcomes, the seeded dice | Own character psychology or narration; silently replace the player's declared content |
| **Perception** (`agents/perception.py`) | What each observer legitimately receives. Stateless by requirement | Invent intent, add meaning, contradict the event stream, or leak hidden state. It may subtract and degrade, never add |
| **Character agents** (`agents/character.py`, `agents/loops.py`) | The subjective: what I would attempt, what these signals mean to me | Decide their own success — capability is objective and lives in the world record |
| **Background presence** (`agents/background.py`) | At most one named unregistered presence, one stateless reaction per beat | Hold memory or psychology — that requires promotion to a real character |
| **Narrator** (`agents/narration.py`) | Sentence-level craft, pacing, the player-facing slice | Originate player conduct or reveal unperceived facts |
| **Mapping** (`agents/mapping.py`) | Lore routing, retrieval, canon staging | Know character interiority |
| **`commit.py`** | The sole persistence boundary | Trust model output — it is provisional until deterministic code validates it |

**Perception is stateless by requirement, not thrift.** A perception layer with
memory is a *bug*: remembered context could let last turn's knowledge bleed into
this turn's seeing, the exact leak it exists to prevent. The cheapest agent is
cheap *because* it must be amnesiac.

**Character agents are predictors, not role-players.** Role-play optimises "be
interesting" and volunteers the secret because the reveal is juicy. Prediction
optimises "be accurate", which means it must be free to be *boring* — to let the
coward stay hidden and nothing happen. That freedom is what makes the eventual
drama earned. The cost is that a predictor treats every fact in its context as
true and load-bearing, so context hygiene is non-negotiable.

### Information model

The load-bearing primitive is **provenance**. Humans tag a fact at encoding with
how and when they learned it, and the tag rides along on every later retrieval,
so the access list maintains itself for free. Models flatten all of that the
moment it is in the window. Binding `witnessed/heard/told/read/inferred/
remembered + turn_idx` at commit hand-installs that faculty — so "told to me as
a secret" and "just true" become structurally different stored objects, and
belief revision becomes possible.

Memory layers, per character:

| Layer | Nature | Cadence |
|---|---|---|
| Stable core | Traits with activation/inhibition cues, values, self-image, protected beliefs, coping patterns | Rare, evidence-gated |
| Stance / relationships | Trust, warmth, fear per target | Event-triggered (see [Structural debt](#structural-debt)) |
| Active state | Mood, goals, affect, stress activation/strain/load, independent pain and pleasure, and the unresolved charge they accumulate | Every turn; relaxes using simulation time. Charge outlives the level that built it and discharges only on the character's own declared resolution |
| Learned associations | Cue, appraisal bias, response tendency, strength | Evidence-gated reinforcement/extinction |
| Episodic | Witnessed events, provenance + salience | On commit; consolidated over time |
| Summaries | Autobiographical synthesis | Post-commit; reconstructible |

`affect.py` implements surface/undercurrent/baseline with exponential decay
toward baseline. `psychology_runtime.py` applies the same explicit-time
principle to stress and hedonic carry-over while keeping pain and pleasure as
independent current-event signals: a comforting touch can hurt a bruise and
still feel welcome. Survival vitals can supply a pain floor but are not required.
Stance axes must not erode on a clock; the grudge does not fade unless something
fades it.

### Persistence and source of truth

When representations disagree, resolve deliberately rather than updating every
copy blindly:

1. SQLite rows and `world` keys — durable runtime state
2. Active step variants — the inspectable result of the current turn
3. `PipelineContext` — in-memory working state for one execution
4. Pydantic schemas (`schemas.py`) — accepted structured model output
5. Prompts — desired behaviour, never overriding deterministic validation

**Physical-world authority.** The frame-scoped `world.scene` blob is the sole
runtime authority for live rooms, positions and entity state. `room_registry` is
the sole cross-frame ledger of room identity and retirement. `world_entities` is
a derived projection of the scene commit. `world_placements` is decommissioned;
`fiction_worlds`, `fiction_locations`, and `transit_edges` are deprecated
import-compatibility tables.

**Commit is atomic.** Slow provider work (lore and memory embeddings) happens
*before* the write lock; then all primary turn mutations commit inside one outer
transaction under a per-turn idempotency lock. Any domain failure rolls the whole
turn back. Only autobiographical consolidation runs afterward, because it is a
reconstructible derived cache.

### Cost

Cost scales with **dramatic density, not story length**. Turn 2000 in a quiet
room with two people costs about what turn 2 in that room costs, because nothing
conditions on the 1998 turns between except memory stores that are *reduced and
retrieved against, not replayed*. The hot path is flat; only the backing stores
grow, and they grow cold.

Every agent runs on a reduction, never a log — and the reduction is both cheaper
*and* leak-proof, because the context an agent does not need and the context it
should not have are largely the same context. Statelessness is the default;
persistence is a privilege earned only by agents modelling a continuous self.

**The contract is reduced the same way the context is.** The character prompt
explains every key the payload *may* carry, while the payload carries most of
them rarely — so `prompts.character_prompt` subtracts the paragraphs whose whole
subject is a key this beat does not have, leaving a contract about the beat that
actually happened. Measured on live banks: 61.2 KB down to 52.9 KB and 50.5 KB,
13–17%. Three rules keep it from costing anything. It is gated on **the key
being in the payload**, never on a mechanism's fire rate — `PROJECTS`,
`WANTS AND GOALS` and `ASSOCIATIVE LEARNING` are the invitation that would
create the thing, and gating those would nail their rate at zero forever. It
reads **the finished payload**, not a second derivation of the same conditions,
so it cannot explain away a field the model is actually being handed. And it
fails **open**: an unmatched heading keeps its paragraph, so a preset that
rewrites one loses the saving and never the instruction. The gate table was
audited paragraph by paragraph rather than by heading, which is how three
paragraphs that carry rules beyond their own key — how to take a bearingless
doorway *at a walk*, why a walking stride is out of character for a body whose
drive is getting there, and what `active_state.goal` is at all — were found and
left ungated.

---

## Player authority

**This is the engine's largest deliberate divergence from the founding
architecture, and it should be understood as a product decision rather than
drift.**

The founding design gives the player authority over *attempts*: the action you
chose always occurs as chosen, but whether it succeeds belongs to the director,
and facts about the world belong to mapping. This engine went further. It
distinguishes:

- **Contestable declaration** — "I try to take the key", "I lunge toward Mara".
  The motion begins; reactions and circumstance may alter the result.
- **Asserted declaration** — "I take the key", "the door collapses", "three
  hours pass". The effect is treated as *true*, and the director determines its
  consequences rather than whether it happened.

Assertion authority extends to world facts and time, not just the protagonist's
body. `flow.authority_claims` and `flow.scheduled_assertions` carry these
through the pipeline, with narrow carve-outs the director still refuses — most
importantly, a player claim about **another character's interior** is rerouted
to that character as an authorial *offer* it may decline, rather than enacted as
truth. Character agency survives player assertion.

**Why this is defensible.** The founding document's own closing principle is
that the engine is *a world, not a warden* — it "has no opinion on how the user
plays, because having one would mean simulating the taste that is the user's
whole contribution", and explicitly: *"the user can shackle themselves whenever
a story wants it — chosen limits make better play than enforced ones."* An
engine that maximises authorial power by default and offers restriction as an
opt-in is a direct reading of that principle, not a departure from it.

**The cost, stated plainly.** Broad assertion authority weakens the thing the
architecture is otherwise built to guarantee. If the player can assert that the
door collapsed, the world's causal integrity is partly the player's
responsibility rather than the engine's. The firewall still holds — no character
learns anything illegitimately — but "coherence without omniscience" becomes
coherence the player can override.

### Hard mode (planned)

The intended resolution is the mode set already named in `schemas.py`:

| Mode | The player controls |
|---|---|
| `actor_only` | The protagonist's attempts, speech, and immediate bodily conduct. Assertions become *claims* the director adjudicates and may refuse |
| `explicit_outcomes` | The above, plus declared completed effects on the protagonist's own actions |
| `world_author` | The above, plus external events, entities, time, and world assertions (**today's behaviour**) |

`PlayerAuthorityMode` exists as an enum and is consumed nowhere; the vocabulary
is in place and the enforcement is not. Hard mode is `actor_only` with the
director free to say no.

Two design notes worth settling before building it:

1. **A refused assertion must not silently vanish.** The player wrote it for a
   reason. The honest behaviours are to translate it into an attempt ("you reach
   for the key") or to surface the refusal explicitly. Silently dropping player
   text is the one thing the engine's authority contract has never done, and
   hard mode must not become the exception.
2. **Mode is per-chat, not global.** A story is chosen at its start, and the
   dial belongs beside prose pacing and NPC autonomy. Changing it mid-story is
   legitimate but should be recorded, since it changes what earlier turns meant.

---

## Beyond the founding design

Subsystems the original architecture never imagined, now load-bearing:

- **Temporal frames and paradox** (`frames.py`, `paradox.py`,
  `spatial_frames.py`). Alternate eras, travellers, per-frame cast status, fixed
  points, paradox detection. Most `world` keys are frame-scoped; cross-frame
  contracts deliberately are not.
- **Spatial model** (`spatial.py`, `scene.py`). Rooms, adjacency with bearings,
  egocentric frames (ahead/behind/came_from), barriers, hearing and visibility
  gating, zones and carry inference. Multi-room movement (`sprint_reach`,
  `passable_path`) is bounded by decision rather than sight, and the rooms
  crossed are reconstructed deterministically so a sprinted corridor is
  remembered rather than left as a hole in the map.
- **A mind's own map** (`commit.update_place_graph`, `place_purpose.py`).
  Per-character nodes and edges earned by walking or seeing, with retraction,
  bounded eviction, frontier distance, and an `affords` ledger recording what a
  remembered place is *for*. Kept on `chat_chars.state`, so checkpoints,
  archives and branching carry it with no schema change.
- **Durable wanting** (`affect.py`). Drives, intentions, beat wants, and the
  project tier between them — capped at two, adopted only against a
  non-circular criterion, weighed at drive strength once established, and made
  legible when the mind drifts from one rather than decayed behind its back.
- **Deterministic mechanics sweep** (`mechanics.py`). Timed arrivals, expiry,
  dock edges, news latency — LLM-free, seeded, idempotent.
- **Weather** (`weather.py`). One sky per scene, with each room's share decided
  by its own `exposure` (open / sheltered / enclosed) and by how many muffling
  boundaries the room graph puts between it and open air. The Director sets it
  on a beat that changes it; between those it drifts on the simulation clock,
  seeded and idempotent, so a reroll cannot produce a different sky. Sight and
  sound are answered separately, because a cellar sees nothing of a downpour
  and hears it clearly — and walking into a cave takes the rain from present,
  to muffled, to faint, to gone. A scene acquires weather only when its fiction
  establishes one, so a starship never has any. A Director's declaration is
  read as a REPORT and written over the sky already blowing, never in place of
  it: the vocabulary is five short enums, a beat describing a storm reaches for
  the vivid word (`blizzard`, `gale-force`, `sub-zero`), and every default is
  the mildest reading of its field — so an exact-match lookup that answered
  each unread word with its default turned the worst weather in the vocabulary
  into a calm spring day and replaced the storm with it. `_SYNONYMS` reads the
  words models actually write, and a word it still cannot read keeps what the
  scene had rather than clearing it. (Live failure, "The Blizzard" turn 2: all
  five declared fields missed, the whiteout became fair/none/still/mild while
  the player stood in an open clearing, and five later beats inherited the
  calm.)
- **Weather rendering** (`static/js/weather-fx.js`). Rain and snow drawn over
  the story for rooms that can see the sky, with storm flashes and thunder
  arriving after them on a distance-shaped delay. A storm sky is not
  automatically an electrical one: `weather.has_lightning` and its mirror
  `weatherFxStormy` require precipitation that is not snow or sleet, so an
  ordinary blizzard neither flashes nor puts thunder into what a room hears.
  **Thundersnow** is the exception and is a property of the SKY rather than
  something derived from what falls — derived, every blizzard would flash;
  forbidden, none ever could. `advance_weather` rolls it seeded at
  `THUNDERSNOW_ODDS`, so a squall almost never flashes and a long blizzard
  probably will once, identically on every replay; a beat may also declare it.
  `normalize_weather` clears the flag anywhere it is meaningless, so lightning
  cannot outlive the snow that earned it. Drawn as three repeating tiles moved by the compositor. Snow
  additionally drifts: each layer carries a second, composed transform swaying
  it sideways on its own period (none of the three divide each other, so the
  depths never fall back into step) and leans a few degrees off the stack's
  angle via the independent `rotate` property — three layers on one identical
  vector read as wallpaper being pulled rather than as snow. Rain is exempt,
  and falls at roughly 1.7x its first-pass speed, because rain falls hard and
  straight. Marks per tile scale by tile AREA (equal counts at unequal sizes made the
  smallest layer three times the density of the largest) and snow gets its own
  larger, mutually non-multiple tile sizes: a rain streak blurs into its
  neighbours, while a snowflake is a distinct blob whose constellation the eye
  finds repeating. Skipped entirely under `prefers-reduced-motion`, and routed
  through the ambience mute.
- **Scene backdrops** (`backdrops.py`). Generated images of the room, built from
  a whitelisted spatial projection that structurally excludes occupants. Cached
  per room-plus-visible-state; a branch reads its ancestors' images in place.
  Reading one is free and immediate; commissioning one waits until the reader
  has settled on a turn — scrolling through a story passes rooms nobody stopped
  in, and neither the picture nor the sound is bought for those. All three
  presentation layers answer the same question — WHICH TURN IS BEING READ — from
  one scroll observer and one per-turn payload built from `scene_after_turn`, so
  scrolling back through a story is chronological: the picture, the sky and the
  sound are the ones that stood while that beat happened, not the ones the story
  has since arrived at. A turn with no picture or bed of its own holds the one
  already showing rather than blanking, but only while it belongs to the same
  ROOM — held across a doorway, the transcript and the screen disagree about
  where the story is.
- **Room ambience** (`ambience.py`). A looping sound bed for the player's room,
  from the same occupant-free discipline: the query is written from a
  whitelisted projection, so a soundscape cannot report a presence perception
  did not deliver. Cached per room-plus-AUDIBLE-state — deliberately a
  different set from the visual one, since light changes the picture and not
  the sound. Two sources (a local folder, or Freesound's CC-licensed APIv2,
  credited in the panel), a per-room host pin that overrides the automatic
  pick, and a reroll that remembers what it rejected. Up to three simultaneous
  layers (room tone / weather / one detail), each with its own level, its own
  reroll, its own credit and its own IDENTITY CHECK — a pin stores a sound's id
  rather than a preview URL that would expire, that id is resolved on
  Freesound's sound endpoint (its text search has no `id` field and answers
  `id:341802` with whatever scores as text — in practice one sound named
  `file_id.diz.mp3`, for every id alike, which made a pinned two-layer
  soundscape download one unrelated recording twice), and the preview URL,
  which carries its own sound id, is checked against the id the layer claims
  before anything is written to the cache — the weather layer carrying the attenuation its
  room's depth earned, so rain two rooms in is quiet over an undiminished room
  tone. That layer is the sky and only the sky: no thunder, since the engine
  draws the lightning and times the clap to it, and no wildlife, which belongs
  to the place, sits on its own level and goes on sounding after the rain
  stops. A host can stage that mix by ear and pin it to the room. The standard
  is a bed TRUE TO THE ROOM rather than a bed at any cost: candidates are
  ranked against the room's own description instead of the library's ordering,
  what the model names in `avoid` is struck out, and a place with no continuous
  sound of its own — a sealed vault, still air — can be judged silent, which is
  cached like any other answer and overruled by the reroll. The room's named
  FIXTURES are part of that description and rank ahead of its adjectives,
  because a hearth is a sound and "warm, modest, lit" is three things no
  microphone can hear. Freesound ANDs the words of a query, so a full room
  query almost always matches nothing and has to be broadened — and a rung that
  returns results is not a rung that ANSWERS: broadening is followed until a
  recording actually of this place comes back, and the ladder reaches past
  prefixes to single terms, since English puts modifiers in front of the head
  noun and a room's name in fiction is a proper noun no library has heard of.
  A winner matching neither the room nor what was searched for is refused
  outright rather than laid down as better than nothing. (Live failure, "The
  Blizzard": a warm hall with a lit hearth was searched for as "stone hearth
  fire crackle wooden room", every rung missed until the single word `stone`,
  and the hall was given a recording titled "ambience in a large cave" —
  scoring zero against the room, like every other candidate, and winning on a
  `loopable` tag.) Each bed loops by
  overlapping itself rather than restarting at the file boundary, where an MP3's
  padding leaves an audible hole. The cache key is deliberately coarse: it is a
  function of the TERMS a search would use, and a room whose state has moved but
  not audibly changed adopts the bed already on disk instead of resolving again.
- **Lorebook hierarchy** (`memory.py`, `agents/mapping.py`). Nested books,
  inheritance modes, scope by world and location, link graph, canon locking.
- **Multiplayer and guest access** (`guest_access.py`).
- **Obligation ledger, background claims, authored events** — bookkeeping that
  keeps promises and unregistered presences coherent.
- **Import pipeline** (`importers.py`, `character_schema.py`). External card
  formats, heuristic and AI-reinterpreted paths, damaged-sheet repair on read,
  and a non-destructive v3 psychology gap-filler for older cards.
- **Per-story character cards** (`chat_chars.sheet`, `scene.active_cast`).
  Authors can tune an attached character for one story without mutating the
  reusable library resource or resetting that story's earned interior state.
  Names/uids stay fixed because they are identity keys throughout scene,
  recognition, memory, and relationship records.
- **Portable chat archives** (`chat_archive.py`). Versioned, typed export/import
  with embedded resources, reference remapping, and atomic restoration.
- **Portable pipeline traces** (`pipeline_trace.py`). Hash-only diagnostics by
  default, with explicit content-bearing offline replay artifacts.
- **Host authentication routes** (`auth_routes.py`, `guest_access.py`). Typed
  request/cookie transport separated from credential/session persistence.
- **Appearance system** (`static/themes.css`). Browser-local themes, independent
  story-text sizing.
- **Provider layer** (`providers.py`, `prompt_cache.py`, `llm_quality.py`).

---

## Structural debt

The honest account. These are not open bugs; they are places where the engine is
weaker than its own stated principles.

### 1. The positive guarantee is weaker than the negative one

The firewall is excellent at *keeping the forbidden thing out*. It is much
weaker at *making the correct thing reachable and preferred*. Both are supposed
to follow from "structure over instruction"; only the first has really been
internalised.

Two production failures found in one session, both of this shape:

- **A model authored an engine primary key.** The AI import path accepted
  `identity.uid` from model output. `scene.py` falls back to that field for the
  *scene entity id*, so when the model returned the character's own name, every
  import of one card collided into a single scene entity — two characters
  sharing one position, one set of clothes, one owner of the memories. Fixed by
  minting the key in code, which is what structure required from the start.
- **A character could not cite the present.** `observations_used` *instructed*
  the character to cite evidence, in a payload where only memory rows carried
  ids and the current beat was an uncitable prose string. Result: 15 citations
  of a previous turn and zero of the current one across one 61-turn chat — a
  character reliably answering the previous line. The firewall worked perfectly;
  what failed was that the permitted information had no structural affordance
  while the stale information did.

The second fix has now landed: `perception.py` mints real observation ids
(`current:<perceiver>:<n>`), the prompt points at them, and `schemas.py`
normalizes legacy spellings back to the canonical sentinel. Retrieved rows use
their durable `event_key` and carry `temporal_status`, relative `when`, and
provenance. `_ground_observation_citations` then admits only ids actually
delivered to this mind across every evidence-bearing output field. A current
citation the model supplied is moved first; omission is warned, never repaired
by inventing audit evidence. The structural affordance exists, the prompt uses
it, and the output boundary can verify it.

**Rule to apply going forward:** whenever a prompt asks a model to prefer X over
Y, check whether the payload makes X *harder to reach* than Y. If it does, the
prompt will lose.

### 2. Stance changes are not auditable

The founding commitment is that every numeric change is event-linked with a
logged trigger. Reality: `apply_relationship_updates` accepts
`trigger_event_ids` but treats them as optional, with explicit handling for "a
routine trigger-less delta". Relationships live in the `world` KV blob, so there
is no change log — only the current value plus a `salient_event` string. There
is no way to answer "why does she distrust him?" from the record.

The founding design also specifies that a normal interaction moves an axis by no
more than ~0.05; the schema clamps at ±0.2.

### 3. Two import paths of very different quality

The heuristic (non-AI) import derives psychology from the card's `personality`
field. A v2 card that puts everything in `description` — common — can still
yield a sparse first pass. The character editor now exposes **Fill psychology
gaps**, which asks for a short account of formative pressures, triggers,
conflicts, coping, sensitivities, and recurring cues, then fills empty v3
psychology fields without replacing authored identity, appearance, goals, or
non-empty psychology. The initial heuristic path still needs better automatic
description fallback and sparse-import warning.

### 4. Documentation forcing functions are uneven

`docs/CODE_MAP.md` is well maintained because `make structure` fails on
staleness. No equivalent exists for hand-written docs, which is how the previous
edition of this file drifted. `docs/DATABASE.md` remains deliberately compact
for a schema with roughly 30 tables and a long migration chain, while
`AGENTS.md` routes every schema change through it.

---

## Roadmap

The roadmap now lives in [`docs/UNBUILT.md`](docs/UNBUILT.md), together with
every other list of unfinished work this repository was keeping separately —
known defects, deferred audit findings, and the residuals of each design note.
There is one register, and an entry is deleted from it in the commit that lands
it.

Items 1-3 of that register repay the structural debt above, in order:
a first-class event id for the present beat (debt #1), a `relationship_events`
table (debt #2), and a `description` fallback in the heuristic import (debt #3).

Ideas that are parked rather than scheduled — a conformance test for this
document, a leak-injection suite, salience-driven personal lore, per-character
retrieval depth, belief-revision salience, an epistemic minimap — are in that
file's final section.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| NPC says what it shouldn't | Forbidden fact in its context | Structural firewall: each mind gets only its perception object |
| NPC treats private thought as dialogue | Thought and speech entered the same window | Separate channels: speech → director event; thought → routed nowhere |
| NPC reacts to something it wasn't present for | Presence was a sentence, not a router rule | Perception routes the beat only to minds that were there |
| Narrator mentions what the player can't see | Narrator knows more than the player | Deny the narrator everything but the player's perception object |
| Character answers the *previous* line | Present beat unreachable; only the past was citable | Give the present a first-class id (`docs/UNBUILT.md` §2.1) |
| Cast feels lifeless, nobody acts | Variance too low | Raise per-character temperature |
| A character is spookily prescient | Context leak | Firewall plus strict character context hygiene |
| World heals — door un-breaks, trap vanishes | Off-screen state dropped | Commit-up plus standing intentions with triggers |
| Secret-in-a-crowd is common knowledge | Visibility posture missing | Overt/concealed plus target on every declaration |
| A character names an act it could only have *felt* | The closed channel cost modality but not resolution — the act's verb crossed into touch as a paraphrase | Sensation crosses, the act's name does not; acuity sharpens detail within its own modality and never buys knowledge of the cause |
| Betrayal reads as confusion | Flat beliefs, no provenance | Provenance tags; revision as high salience |
| Trust silently erodes | Clock-driven numeric drift | Stance axes event-linked; only mood decays |
| Two characters share one position and one set of clothes | A model authored an identity key | Mint engine keys in code; never read them from model output |
| The world cannot tell the player "no" | `world_author` authority by default | Hard mode (`docs/UNBUILT.md` §2.4) |

---

## Keeping this document honest

1. Change a status row in the same commit that changes the behaviour.
2. Prefer "Partial" with a precise gap over "Built" with a caveat buried in
   prose. The gap sentence is the useful part.
3. When something in `docs/UNBUILT.md` ships, add its row here and delete the
   entry there. Do not leave it in both.
4. If this file passes roughly 500 lines, something belongs in `AGENTS.md`,
   `docs/PIPELINE.md` or `docs/DATABASE.md` instead. Length is how the last
   edition died.

---

## In one breath

The player acts; perception filters the act so the present cast can react blind;
the director collapses the player's declaration and all reactions into one
resolved state, dice optional and seeded; perception filters that outcome per
mind; the narrator renders the player's slice — coloured by a voice-setting only
it can see — while each character commits a provenance-tagged, perception-
filtered memory of what it personally registered. The narrator renders
perception and never authors action, because intent runs straight to the
director and never through it. Every mind holds only what it earned.
Statelessness is the default; persistence is reserved for the agents being a
continuous self. No agent authors the story — it is the residue of honest minds
under honest causality. Omniscience exists nowhere inside the world, and only in
the player above it, who may hold as much or as little of it as they choose.
