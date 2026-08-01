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

### The two principles everything else serves

1. **Structure over instruction.** Anything you want guaranteed must be
   *impossible to violate*, not merely instructed against. A prompt cannot
   un-write its own context.
2. **Auditability.** Every numeric change should be event-linked, every
   scheduled effect seeded and logged, every resolution recorded. Silent drift
   is the failure mode being prevented at every layer.

[Structural debt](#structural-debt) is an honest account of where the engine
currently falls short of principle 1. It is the most useful section here.

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
| Firewall as plumbing — each mind gets only its perception object | **Built** | `agents/perception.py` emits per-observer views via `_per_observer_model_views` (one LLM call per perceiver); characters receive their view, never the event stream; stored event rows are per-observer redacted via `recent_events_for_observer` when loaded into character context |
| Two perception passes per turn (onset, outcome) | **Built** | `perception_act` before resolution, `perception_outcome` after |
| Player-leads loop; characters declare blind to each other | **Built** | Plan built from `director_interpret.flow`; character steps run in parallel |
| Memory provenance | **Built, exceeds spec** | Six kinds (`witnessed/heard/told/read/inferred/remembered`) against the specified three, plus `turn_idx`, bound at commit |
| Action visibility posture | **Built** | `visibility` + `conceal_from` + `targets` on every declaration; targets the model leaves empty are bound deterministically, because the seams that ask "does this land on someone?" all read that field |
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
| Undressing as a sequence | **Built** | A garment moves `worn → loosened → open → removed` one rung per beat (`attire.advance`), lifted by a decisive act from ANY voice in the beat — player input, a character's declaration, or the resolved prose. `attire.decisive_targets` attributes it PER BODY (garment first, then first person in the player's own words, then a sole name), so the actor is not mistaken for the target and one person hurrying does not undress the room. Getting dressed is deliberately unrestricted. `commit.py` clamps the Director's whole-garment proposals through `apply_flat_change`, and `director_resolve`'s prompt states the rule so the events match the step actually reached. A garment that comes off is minted as a real portable object in the room (`commit._mint_shed_garments`) rather than ceasing to exist — unless it arrives on ANOTHER body the same beat, which is a handover rather than a drop: "she takes off her coat and drapes it over his shoulders" used to leave two coats, one on his shoulders and one at their feet. Keyed on arriving-this-beat rather than worn-by-anyone, so two guards in the same kind of cloak still get a real cloak on the floor when one takes his off |
| Generated body and clothing | **Built** | `importers.fill_appearance` + the `fill_appearance` prompt fill body and per-region outfit from the card, what the author has typed but not yet saved, and a brief; `beneath` is a separate opt-in and is stripped from the proposal when it was not asked for. Writes nothing — the editor reopens on an unsaved proposal, as `fill_character_psychology` does |
| Approach is not arrival | **Built** | `MovementDecl.arrives` — whether the declaration covers ARRIVING or only setting off — filled by `director_interpret` and honoured deterministically by `director_resolve` (`_guard_approach_is_not_arrival`, plus the backstop refusing to commit a non-arriving move). Live failure, "The Blizzard" turn 2: "You wander towards it" of a building seen through the snow became `to_room: distant_mountain_building`, the route check passed it (the rooms genuinely were adjacent and open), and the resolve wrote her through the door into the firelight — from `exposure: open` to `exposure: sheltered`, out of a blizzard, with nobody having said she was going in. A FIELD rather than a downstream test because the distinction is not recoverable downstream: measured across 1249 live turns, no text heuristic separates "I cross the command deck toward the med bay" (an asserted crossing) from "progresses across the clearing toward the building" — both say "toward", both are staged `approach`, both are `commitment: asserted`. Four heuristics were tried against the corpus and each blocked legitimate arrivals (3, 8 and 4 false positives). Defaults true, so no existing declaration changes meaning. Carried/contained bodies are exempt; a declared VEHICLE mover is guarded like any other, since a skiff told to head for a light is as much not-there-yet as the hand on its tiller. An approach in flight is recorded on the scene per mover (`scene.approach`), so the next declaration toward the same place ARRIVES — without that memory the feature strands anyone who keeps writing approach-flavoured text, and time spent approaching is time spent standing still (measured: six simulated hours of "trudging towards the mountain" left the walker in her starting clearing under level-12 snowdrifts). `ActionStage` — classified since the beginning, read by nothing — is `docs/UNBUILT.md` §1.13 |
| Place purpose (what a place is FOR) | **Built (v1)** | `place_purpose.py` per `docs/DESIGN_PLACE_PURPOSE.md`: live `perception.here_affords` echo; `affords` ledger on the character's own place-graph nodes — `witnessed` from own vitals/`comfort.rest_affording`, `told` mirrored from reconciled beliefs with `belief_credence`-refreshed sureness, `assumed` derived read-side from own node names (never stored); `memory.recalled_places` surfaces at most two walked-route options on a felt need. Witnessed drink/water/warmth, told-basis node minting, and negative entries deliberately not built |
| Durable place graph (a mind's own map of walked ground) | **Built** | `commit.update_place_graph` writes per-character nodes and edges onto `chat_chars.state` with `basis: walked\|seen`, `disproven` retraction both ways, and `PLACE_GRAPH_NODE_CAP` eviction; read back as navigational verdicts and `_frontier_hops` distance in `agents/character.py`. `basis: "told"` is an accepted value with no writer, deliberately |
| Long-term goals (the project tier) | **Built (v3)** | `affect.apply_project_ops` / `serves_priority` / `project_boundary` / `settle_probation`; persisted in `interior.projects` / `former_projects`. Caps at two, adoption requires a non-circular `satisfied_when`, probation weighs at intention level until served on ≥3 beats over ≥12 turns, drift surfaces as `adrift`. Per `docs/DESIGN_LONG_TERM_GOALS.md` |
| Memory retrieval by meaning | **Built** | An `embeddings` provider makes the two vector rankings of `search_memories` genuinely semantic. Without one the engine falls back to `providers.cheap_embed`, a signed character-n-gram hash (Weinberger et al. 2009) — measured against a real 441-memory story on vocabulary-disjoint paraphrase, that scores **0% recall at every k, median rank 228 of 441**, indistinguishable from random, while a real model reaches median 1–3. It is a strong LEXICAL retriever and a non-existent semantic one, which is why episodic recall worked and thematic recall never did. Deliberately no ANN index: `search_memories` applies a turn cutoff (its own comment calls it "the SOLE defence" against a mind retrieving how the turn it is deciding turned out) and frame visibility BEFORE ranking, and those are exactly the selective predicates an ANN index carries badly — the `sqlite-vec` declaration was deleted rather than wired. The exhaustive scan is also not the bottleneck: 16 ms at a real story's worst case, ~709 ms at ten thousand turns, against an LLM call in the same beat |
| Changing the embedding model is safe | **Built** | A vector is only comparable with one from the same model, so a row embedded by another scores 0.0 on both vector rankings forever. Nothing re-embedded and nothing said so, so configuring a provider silently split a bank into two eras. Now: `embedding_bank_status` counts the split, retrieval warns once per situation, `rebuild_embeddings` re-reads stranded rows resumably and refuses to write the fallback over real vectors, opening a story OFFERS the rebuild rather than performing it, a checkpoint restore hands the bank back to the reconciler (a reroll had been putting 637 of 642 rows back on the fallback), and `rebuild_checkpoint_embeddings` carries a completed rebuild through saved states by SUBSTITUTION rather than computation — 99,442 saved memories repaired across 1,040 checkpoints in 98 seconds and zero API calls, because a vector is a pure function of the memory and the same memory recurs unchanged across every checkpoint. Of the MEMORY, not of its `content`: that join keyed on `(char_id, content)` until alpha 6.6 while `_memory_document` also folds in turn, location, category, key_phrases, entities, gist, provenance and emotional_context — so two rows could agree on content, hold different vectors, and be handed each other's. It now keys on the whole document, and a summary on its whole `_summary_retrieval_text` rather than its `summary` field, which had the same collision |
| Relevance outranks recency | **Built** | RRF's magnitude is arbitrary (~0.02 at rank 1; only its order means anything) while the bonuses after it are hand-tuned on a 0..1 scale. Summed raw, the four relevance rankings reached 0.074 combined against a recency bonus of 0.12 alone — a recent, salient memory matching nothing outranked the best match on every relevance signal there is. Invisible until real embeddings made the signal real. `_RRF_SCALE` bridges the two scales; `_RECALL_LIMIT` rose 8→16 because every result set is padded with chronological neighbours and at 8 the padding was a third of what a character saw. Mood and goal now fuse as their own rank lists instead of being concatenated onto a query 20× their length |
| A memory carries the mood it was formed in | **Built** | `affect.resolve_affect` decays mood toward baseline, applies appraisal, and cross-checks the label — and runs ~500 lines below the memory mint, so memories took the model's raw self-report instead. Measured across the same characters: self-report +0.773 mean with **0% negative**; resolved affect +0.467 with **22% negative**. Newer stories inherited the saturated one (median valence +0.85, four negatives in 3,162 rows), which is a constant rather than an axis and silently disabled everything downstream that reads affect. Memories now take the stored resolved affect — last beat's resolution, i.e. the mood carried INTO the event, which is what encoding-time affect should be |
| Nobody may author the player's interior state | **Built** | The Director owns objective causality and does not own what is inside the protagonist. Live: the player typed only "W-what did you do to me!?" and the resolve wrote "the shrill, PANICKED cry" and "she takes in the GENUINE TERROR in those wide eyes" — asserted as fact, with "genuine" claiming its truth — which perception then copied into a second mind's view. Guarded at both ends: `_check_player_interiority_authority` on `director_resolve` (exempting anything the player themselves wrote, folded into the existing one-retry loop), and `_check_player_interiority_prose` on the narrator in the second person it writes in, ENFORCED rather than warned because what the narrator writes is what the story said happened. Observable surface — trembling, wide eyes, a shrill cry — is always allowed; naming the state behind it is not. Both ends were then found blind to the same sentence written two ways. Live in "Run!" (chat 56, t6), against a player who declared only "You imitate them slightly and shudder": the resolve wrote "She looks at him, still shaky, but the terror in her eyes has begun to recede" — a pronoun subject the name-anchored test could not see, so nothing fired and perception copied it into the player's own view; the narrator then rendered it as "The terror that had been living wide-open in **your** eyes pulls back to something smaller", where "your" attaches to "eyes" and the verb is "pulls back", one word out of reach of every branch of `_YOU_INTERIOR`. The Director's side now resolves a pronoun subject through `_sentence_subjects`, and the narrator's regex reads a named state anywhere in a clause that also reaches for the player. Deciding the player's emotional *arc* — that the terror is receding — is the same violation as naming it |
| A character calls the player what they may legitimately call them | **Built** | Three possible handles, and the engine was using the two wrong ones. Live in "Run!" (chat 54), three of The Doctor's four turn-0 memories read "The Doctor knows **the player** was being chased by a Dalek", "intrigued by **the player's** appearance" — the engine's own out-of-fiction word for the protagonist, inside a fictional mind, at salience 1.0. `{{PLAYER}}` was in none of them: the model wrote the literal English words, so `sub()` — which replaces only the exact token — had nothing to replace. An earlier run of the same card had the opposite failure: the token WAS present, `sub()` resolved it to "Hinami", and the character began knowing a name the launch had explicitly said he did not (`already_known=False`). `greetings.player_handle_for` now answers the question once — recognised → the persona's name, not recognised → a DESCRIPTION from the same `_unknown_actor_label` every perception path uses, so the launch cannot drift from the identity floor — and `_substitute_player_slot` rewrites the token AND the bare words, anchored on a leading article so an in-fiction "a lute player" keeps their job. The same defect had a second source: `commit.py`'s dialogue-memory path rewrote the player to the literal `"the player"` and then EXEMPTED them from the recognition gate every other speaker passes, producing 68 rows across the live corpus including `the player said "My Name is Hinami." to Dr. Moon` — the memory in which the character learns her name, attributed to a word from outside the story. The player is now a body in the room like any other: the persona's real name goes in and the gate decides. `_unknown_actor_label` also stopped truncating mid-phrase on a linking participle ("the beautiful young woman appearing"), which matters once the description is the deliverable rather than a fallback |
| Nobody may author a character's conduct but that character | **Built** | The mirror of the row above, from the character's side: the Director resolves what a declared act ACHIEVES and does not decide that the character also did something else. Live in "Run!" (chat 56, t1391) The Doctor declared one act — scan "from several feet away", "while staying at distance", against a want to act "without crowding her" — and `speech: null`; the resolve had him take "a half-step closer" and say "You're alright, Hinami. Nothing broken…". `_check_character_speech_authority` was armed and blind to all of it: it read only sentences OPENING with the literal name (every fabricated sentence opened with "He") and measured its verb window three words from that name (the attribution verb sat twelve words out, in a compound predicate). The dialogue_log backstop that WOULD have dropped the line was inert because `dialogue_log` was empty — the line existed only in prose, and the speech check strips quoted spans on the assumption the dialogue path covers them. Each guard held ground the other had. Now: `_sentence_subjects` binds a pronoun subject to the most recent NAMED subject (a newer name takes it, an unanchored pronoun binds to nobody), `_predicate_heads` measures the verb window per conjunct, `_check_character_act_authority` guards acts — the full act-verb list for a character who declared none, narrowed to MOVEMENT for one who declared a non-locomotive act, because distance decides what perception delivers and what contact is possible — and `_check_prose_quote_authority` catches a spoken line in prose that no declaration supports, whoever the prose says said it. All fold into the existing one-retry loop, kept only if it reduces the total. The cost of missing it is not cosmetic: the narrator dropped both fabrications, so nothing was visible in play, and both still committed as the Doctor's own episodic memory of what he did |
| Nobody may author the player's conduct but the player | **Built** | The doing half of the row above. `_check_player_act_authority` on `director_resolve`, folded into the same one-retry loop. Two scopes, and the second was missing entirely: a player who declared NO action was protected, and `if declared_actions: return []` disarmed the guard for anyone who narrated so much as a gesture. Live in "Run!" (chat 56, t10) that player narrated one every single beat, so the guard was off for the whole story — they typed `"Heh? What are we doing what's going on?" You look genuinely confused.` and the resolve wrote "her hands coming up to grip the edge of the console, fingers finding a lever as if to steady herself", which perception copied into their OWN view as "I grip the console edge" and the narrator rendered as fact. Their very next input was "Which lever?!" — the fabricated act replayed a beat later, which is precisely the failure the guard exists to stop. Elaboration cannot be separated from addition by vocabulary, because "pushes herself upright" elaborates a declared "slowly stands up" and shares not one word with it; what CAN be separated is what the act TOUCHES. Elaboration re-describes the player's own body, fabrication reaches out and takes hold of the world, so the widened scope flags exactly one thing: a manipulation verb taking a DIRECT object that is neither the player's own body nor anything their declaration mentions. "Pressed flat against the cold metal" is a body bracing itself and is not a grip on the metal |
| A view never narrates its own perceiver | **Built** | `_strip_self_narration` drops sentences whose subject is the perceiver, in all three perception passes. Live: Elyndra's own view read "Elyndra's gaze stays fixed on the shifting lump, her teasing smile faltering" in a view that elsewhere said "You see Hinami". Perception had copied the Director's omniscient sentence rather than rendering the beat from her frame — per-observer calls do not prevent that, since each observer's call simply echoed its input. Whole sentences only, subject only, and never emptying a view entirely. Subject resolution was name-anchored on the stated ground that "a pronoun could be anyone in the beat" — true of a pronoun read in isolation, false of one read in sequence, and the reason chat 56 t6 walked through: the PLAYER's own view read "She feels her arms still wrapped tightly, her breathing slowing, the terror in her eyes beginning to recede", third person about its own perceiver, naming an interior state she never declared. Now shares `_sentence_subjects` with the Director-side guards, so a pronoun continuing a named subject is resolved; an unanchored one still binds to nobody |
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
| Checkpoint / rollback | **Built** | `checkpoints.py`; branching depends on it. A checkpoint is a full PRE-turn snapshot, and it used to carry every memory's two float32 vectors inline -- so the same vector was re-stored on every turn for the life of the story. Measured on a live database: checkpoints were **94.5% of a 4.4 GB file**, `memories` was 98.9% of each checkpoint, and the vectors were 96.9% of that. One story held 40,224 memory copies across 118 checkpoints and **529 distinct by content** -- 76x duplication of 1.00 GB that needs 13 MB. Vectors now live once in `memory_vectors`, addressed by `memory.vector_address` — `v1:` plus a sha1 over the vector BYTES — and the checkpoint keeps a reference. It was briefly `sha1(char_id, content)`, on the reasoning that a vector is a pure function of the memory; it is, but not of its `content`, and the compaction verifier caught the collision in production (checkpoint 855 of chat 36 held "You are in Ten Forward." at turn 42 and again at turn 44, same character, two different payloads). Byte-addressing makes a collision impossible by construction rather than by assumption and still deduplicates 69x. Nothing is re-embedded: this changes where the bytes live, not what they are. Real conversion: **448.6 MB -> 44.0 MB (10x)**, 14,820 vector copies to 300 distinct, 0 unmatched. |
| Compaction cannot lose a memory | **Built** | Rewriting rollback history is the one maintenance job where a silent error is unrecoverable, so losslessness is enforced rather than intended. Work happens per STORY on an in-memory duplicate; every checkpoint is compacted into a candidate while the stored blob is untouched; each candidate is verified field-by-field against its original -- every top-level key, every memory entry, every scalar, and every vector reference **resolved back to the exact bytes it replaced** (`_verify_no_loss`), which is the question a restore will ask. Only if EVERY checkpoint in the story verifies are vectors and blobs written, in one transaction. Any failure names the story, discards its candidates, leaves its originals byte-identical and moves on -- proved with injected loss: `cannot compact 'Corrupt Story' -- entry 2 resolves to different vector bytes`, originals unchanged, and zero vectors written for it. The duplicate is held in memory rather than as a cloned chat: same guarantee, without copying a gigabyte, and with no half-written copy to clean up if the process dies. It also refuses to start when there is no legacy data -- a no-op run still walks every checkpoint and takes the write lock per story, and on this path the safest run is the one that does not happen. |
| Consolidation, salience-weighted hybrid retrieval | **Built** | `consolidate_character_memory`; keyword + embedding search in `memory.py` |
| Commit as sole persistence boundary | **Built** | `commit.py`; one outer transaction, any domain failure rolls the turn back |
| **Player action absolute** | **Built, then deliberately exceeded** | See [Player authority](#player-authority) — a considered product divergence, not drift |
| **Event-linked stance axes** | **Partial** | `trigger_event_ids` accepted but **optional**; relationships live in a `world` KV blob with no change log |
| **Canon lock** | **Partial** | `lore_entries.canon_locked` is settable via the API and chat-canon entries auto-lock after 20 turns; the specified repeated-reference lock rule is not implemented |
| **Scene-boundary coherence pass** | **Partial** | Validation and dedup exist throughout commit; the specified retcon protocol is not implemented as such |
| **Off-screen world ticks** | **Partial** | Deterministic scheduling and an `offscreen_log` exist; the world advancing meaningfully during absence is narrower than specified |
| **Player authority modes** | **Stub** | `PlayerAuthorityMode` enum exists in `schemas.py` and is **consumed nowhere** |
| **Predictive staging** | **Not built** | No pre-staging of lore or NPCs for likely-next locations |
| **Reactivation negotiation** | **Not built** | No gap-history / delta-summary proposal, refusal caps, or "stalemate eats canon" |
| **Session digest** | **Not built** | No end-of-session synthesis for resume |

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

The second fix is itself half-instruction (a prompt rule plus a sentinel id),
which by this document's own standard is the losing move. **The structural fix
is for the current beat to carry a real, first-class event id at declaration
time, like every other observation.** Until then this is debt, not a fix.

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
