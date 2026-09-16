# Unbuilt work — Perception and presentation

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-18"></a>

### 1.18 The fallback is doing all the work

**Found 2026-08-01**, investigating whether embeddings could make the engine's
word tables "fire and catch" more often. Shelved deliberately after the
measurements pointed somewhere else. The attire half of this entry merged into
§2.14 on 2026-08-19; what is below is the EXPOSURE half, which is the one with
no owner.

**`weather.room_exposure` consults `_ENCLOSED_WORDS` only when `room.exposure`
is unset** — and `RoomDef.exposure` exists in the schema, the prompt says "give
every room an `exposure`", and it is set on **62 of 455 live rooms (13.6%,
re-measured read-only 2026-08-19; it was 8 of 289 when this was written)**. The
36-word list is deciding the other 393.

So the table is not the mechanism; it is the fallback that BECAME the mechanism
because the authoritative field is never populated. Worse, `room_exposure`
recomputes the guess from the room NAME on every read and never stores it, so a
wrong guess cannot be corrected by a host and changing the word list silently
rewrites the past.

**The proportionate fix, when it is wanted:** seed `exposure` once at commit
from the existing guess and STORE it, so downstream reads a stored fact that can
be edited; and emit a reconciliation signal when a room is created without one,
the same shape as `restraint_scan` and `unconsciousness_scan` already use. Then
the word list serves ~14% of rooms instead of 86% and its gaps stop mattering.

**Ask the same question of any other table first: is there an authoritative
field this is standing in for?** Where there is not (`_SPEECH_VERBS` parsing
model prose, `_BARRIER_ALIASES`), the table really is the mechanism and coverage
work is legitimate. The census that used to head this entry is stale and was
deleted: `world/spatial.py` is now a facade holding **0** constants.

**Rejected outright, measured with the real provider
(`perplexity/pplx-embed-v1-4b`, 2560d):** embeddings in any precision gate
("lifts her hand toward his face" vs "lowers her hand toward his face" cosine
**0.943**; "faint"/"faints" 0.784; "puts on"/"takes off" 0.612 — direction,
polarity and part of speech are invisible to cosine, and those are exactly what
`_inverted_motion_check` and `_UNCONSCIOUSNESS_CUE` turn on); embedding region
classification (nearest-exemplar 52% against the dumb `DEFAULT_REGION="torso"`
fallback at 72.5%); embedding identity matching for presences (an over-merge
welds two characters); `cheap_embed` for anything semantic (29.5%); and any
provider call inside the write lock (262 ms for one text against `core/db.py`'s
0.02 ms commit budget).

<a id="unbuilt-1-22"></a>

### 1.22 One window answers most beats, because every view describes the same person

**Found 2026-08-02**, measuring the window layer against chat 38's real
perception views rather than hand-written probes. **Re-tested and rejected
2026-08-02.** Against 27 historical beats, using the era most represented in
the raw semantic retriever's top 16 as the reference, the unchanged window
ranker reached 70.4% top-1 / 81.5% top-2 agreement. Stripping the appearance
tail reduced that to 63.0% / 77.8%; adding goal, mood and concern aspect RRF
reduced it further to 48.1% / 74.1%. Neither change shipped.

Asked a query that NAMES an era, the layer is accurate: "the replicator logs,
the miso soup and the mochi" returns windows (50,59) and (60,69) at 0.486/0.409;
"the Jefferies tube and the phase-doubled conduits" returns (90,99) and (80,89).
Raw recall agrees -- it returns turns 50-66 and 89-106 for the same two.

Asked a REAL view, it collapses. Across 30 of the Doctor's actual
`perception_act` views spanning turns 30-117, the origin window (0,9) wins **24
of 30 beats**, including deep inside the Deck-14 anomaly, and **7 of his 11
windows are never returned at all**.

The cause is that a real view is mostly a description of who is standing there,
and in a two-hander that never changes. His views nearly all describe Hinami,
and the window that describes her most is the one where they met. The layer is
ranking on the constant component of the beat instead of the variable one.

**What was tried and did not work.** Hubness correction -- subtract each
window's mean similarity across all views, so a window that matches everything
matches nothing. Measured against raw recall's era as reference, it made
targeting WORSE (median distance 12 turns vs 7; 4/30 exact-era hits vs 6/30).
Recorded because it is the obvious first idea.

**What did help, partially.** Every view carries a boilerplate tail -- `You see
A beautiful young woman appearing in her early twenties, with golden fox ears
and six golden tails.; wearing: modern casual attire.` -- identical on every
beat and ~24% of an average view's length. Stripping it FROM THE RETRIEVAL
QUERY ONLY (not from the view the character reads) drops the hub from 24/30 to
19/30 and lifts two starved windows from 1 pick to 4 each. Cheap and worth
doing, but it is not the whole cause.

**The initially proposed fix did not fit this layer.** Raw memories are short
enough for aspect fusion to help; chapter summaries are already compressed and
the added rank lists pulled them away from the era selected by raw recall.
Boilerplate stripping also removed useful identity/context signal along with
the constant tail. The remaining problem needs a different candidate and the
same historical replay before it lands.


---

<a id="unbuilt-1-24"></a>

### 1.24 What the enclosure investigation found and did not fix

From the same live story as the enclosure fixes (`Design.md`, "A body sealed
inside another body"). These were observed in the same sweep, are real, and
were left alone deliberately — each needs a decision rather than a repair.

**Body scale is not a perception input.** `hear_level` takes a volume, a
barrier, a proximity and a vouched flag; it does not take a size. A body at
0.05 scale shouting and a body at 1.0 shouting are the same event to the
engine, and the same is true of what a tiny body can smell or be smelled at.
`scales` is already in the scene and already gates contacts and containment, so
the input exists; what does not exist is a defensible curve. Measure before
picking one.

**World pressure does not ask whether anyone can reach it.** Live, an
"Unlatched window" pressure kept demanding a tick — `must_tick_this_beat` —
while the only character who could have acted on it was sealed inside another
body and had no sensory channel to the room at all. A pressure nobody can
perceive or reach is not stalled, it is suspended, and forcing it to advance
puts a beat's weight on something the scene cannot honour. The reachability
test now exists (`enclosed_from_source`); nothing consumes it here yet.

**A derived observation carries one channel for a compound sentence.** The
re-derivation assigns a single `channel` per atom, so a sentence carrying both
a sound and a scent ("breath comes in short gasps, the air thick with...") is
filed under one of them and the other becomes unattributed. Minor, and the fix
is either sentence splitting before classification or a multi-channel atom;
both are more invasive than the defect.

*(Two bullets left this entry on 2026-08-19: "one being, two names" is landed
(`world/spatial_identity.normalize_scene_subjects`; `CHANGELOG.md`), and the
byte-identical-state bullet merged into §1.10, which is where the same finding
was already written twice more.)*

<a id="unbuilt-1-44"></a>

### 1.44 A concealed feature can leak through an attire description

**Found:** the same investigation, by reading a live wardrobe rather than by a
failure — it has not fired yet.

A garment's authored `description` is free prose and is delivered through
`observer_body_regions`, which gates by region visibility and knows nothing
about disguises. A live hair clip is described as *"pinned into her
copper-gold hair near the left fox ear"* while a `physical_disguise` on that
body lists `fox ears` in `concealed_terms`. The moment that region renders to
an unaware observer, the disguise is undone by an accessory.

`disguised_visible_appearance` scrubs the body summary and
`conceal_disguised_parts` drops authored parts; the attire ledger is the third
surface a body is described through and nothing scrubs it. The fix is the
existing rule applied to one more surface — a garment description reaching an
observer who is not in `known_to` should have concealed terms removed, and a
description that is *only* the concealed feature should fall back to the
garment name.

<a id="unbuilt-1-50"></a>

### 1.50 Residuals from the speaking-device repair (chat 80)


The repair that keyed one presence per body, gated background speech on
personhood, and stopped `state_diff` field names becoming entities left three
things deliberately unfixed:

- **`dialogue_turns` carries no provenance.** The ledger cannot say whether a
  dialogue turn was Director-authored (the fiction voicing this presence) or
  backstop-authored (this stage voicing itself into its own future
  qualification). So chat 80's merged Scranton Reality Anchors record keeps
  the two turns the backstop should never have authored, and a kind-undecided
  presence stays `promotable` on such history. The speech gate makes the
  history inert — an undecided presence needs `routed_to_background` or
  `flow.addressed_to` to speak, and auto-promotion additionally demands
  deliberate `addressed_turns` — but splitting provenance would also let
  ambient requalification (at-post, mentioned) return for an undecided
  presence whose history is genuinely the Director's, which the uniform rule
  currently denies (a "dalek war machine" standing silent until re-engaged).
- **Not every reader of `background_presences` folds.** The gate, the stage,
  the manager roster, the promotion list and commit read through
  `_fold_duplicate_presences`; the known-name rosters in `agents/director.py`
  and `agents/perception.py` and the subject index in `world/subjects.py` read raw
  and see a split ledger until the next commit heals it. They consume name
  lists, so the cost is a duplicate spelling for at most one beat.
- **`_STATE_DIFF_SIBLING_FIELDS` is still hand-maintained.**
  `schemas.NON_ENTITY_FIELD_KEYS` is computed from the models' own
  declarations, but the hoist's sibling list is not, so a new StateDiff
  channel is refused as an entity everywhere while its hoist-up repair needs
  the list edited by hand.

<a id="unbuilt-1-68"></a>

### 1.68 A barrier's appearance, and knowing how it works, are both in the room note

**Landed 2026-08-19:** a `one_way_window` declared from both sides is a
contradiction, so sight subtracts in both directions and the pair is reported
once per chat — to the developer as a warning and to the Director as an engine
notice naming the blind side it must declare. `sight_contradictions_told` makes
a scene that was ALREADY contradictory before the check existed get told once
rather than never.

The subtraction is a holding position with a known cost: the watching side
loses a view it should have had until somebody names the direction. It is
accepted because a gap plays wrong obviously and the notice says what to fix,
where the leak it replaces — chat 82's restrained subject watching her
interviewer through a mirror her own room note called opaque — is not noticed
until it has been true for fifty beats.

**Also landed 2026-08-20, the structured strand:** `spatial_digest` rendered
each adjacency edge identically to both rooms it joins, so the blind side was
handed the far room's name and the word `one_way_window` in the narrator's own
`spatial_frame` — the middle and bottom rows of the table below, arriving
through the payload rather than through a room note. Chat 78 t3: a restrained
player whose whole perception output was two PA lines was narrated a figure
"beyond the one-way window". The edge is now dropped from the digest on the
side it is a wall from; the watching side is unchanged.

**The open half is that one physical object is described in three registers and
the engine only has one place to put them.** Owner's statement of it, 2026-08-19:

> Sarah should know that the glass is one way... but not by looking at it, yes
> she can see through it on her side... but she only knows it's one way from
> prior info.

Three different questions, three different homes, and today all three live in
`rooms[x].notes`, which is authored once and served to everyone standing in the
room:

| question | where it belongs | today |
|---|---|---|
| who can see through it | the edge barrier, directional | the mutual declaration cancels it |
| what it LOOKS like from each side | edge-scoped prose, delivered per side | one note per room, so both sides get both |
| *knowing* it is one-way | the character's knowledge — a briefing, a memory | the note, so the subject is told too |

Chat 82 shows all three failing at once. The cell's note reads "The mirrored
side of the two-way glass offers no visibility to the annex" — a statement
about the FAR side's optics, handed to the woman restrained in the cell, who
has no channel to it. Standing beside a mirror is not a channel to how the
mirror works. Two sentences later the same view says she sees the annex and
everyone in it, because the geometry disagreed with the prose.

The fix is to move barrier prose onto the edge, where it can be rendered per
side, and to leave "it is one-way" out of the scene entirely — it is prior
knowledge, and the engine already has knowledge records. That is a schema
change (owner policy 4, §1.58) plus a migration for every scene whose barrier
prose currently sits in a room note, which is why only the deterministic half
landed. Until then a room note may still tell an occupant something the room
does not show, and no guard reads prose well enough to catch it.

<a id="unbuilt-1-80"></a>

### 1.80 Residuals from the change tier

Landed with `Design.md` § A view leads with what changed: a player view is now
partitioned into a beat half and a background half by
`composer.standing_verdicts`, reading each observer's own previous ledger.
Three things that work names for and does not close.

- **The content hash is LEXICAL, so a re-wording reads as a change.** A
  standing key's content half hashes the rendered fields, and a specialist
  that re-phrases a pose or a contact manner without moving anything mints a
  new hash. Measured on the replayed corpus (chats 86-92, 389 player views),
  the beat half carries 16.9% contact and 7.2% pose atoms per beat, and some
  unknown share of that is re-phrasing rather than movement. **The cost is
  bounded and is not an information leak**: every sentence still realises
  admitted percept data, so a false "changed" verdict buys a re-description
  the observer was already entitled to, never a fact they were not. Semantic,
  wording-invariant keys are the fix and they are a separate change with a
  separate argument — a pose is not obviously equal to a paraphrase of
  itself, and deciding it is has consequences for memory minting too.
- **The episode renderer keeps its own changed-list logic.**
  `_render_episode_english` still asks `dedupe_key not in prev_standing` plus
  `force`/`prev_described` directly rather than calling `standing_verdicts`.
  It is correct as it stands (the split key is still an exact match), but it
  is a second spelling of one rule, which is the shape this repo has watched
  drift before — the Japanese adapter's copy of the player delta rule had
  already drifted once when this work found it. Unifying it is a tidy-up, not
  a defect.
- **An adapter that implements `render_view` without calling
  `standing_verdicts` re-forks the rule.**
  `tests/test_japanese_renderer_parity.py` compares the two renderers'
  beat/background classification AND the order of their spans, so the shipped
  pack cannot drift silently; a THIRD pack could. The classification half of
  that comparison shipped a beat behind the ordering half: the first version
  of the ordering test rendered a beat containing exactly one member, which
  orders correctly whatever the rule says, and it passed while the Japanese
  adapter emitted the changed standing percepts before the events. The three
  private composer names the pack reached across for are now public
  (`leads_the_beat`, `as_beat`, `ACTIVE_STANDING_KINDS`) and the ordering
  itself is `composer.player_view_order`, which both renderers call, so the
  ORDER is no longer a thing a pack can hold an opinion about. What a pack
  still spells for itself is admission -- the appearance and standing-dedupe
  branches -- and that is the remaining fork. A malformed adapter still falls
  through to the English reference renderer, which carries the tier, so the
  failure mode is wording rather than information.
- **The delta can still starve a view without emptying it, and that half is
  the owner's call.** A view the delta empties completely is now re-asked for
  the background (`perception._composer_outcome`; `Design.md` § A view leads
  with what changed), because "nothing new" and "nothing reached this mind"
  are different states and `agents/narration.py` reads the second off a null
  view. A view the delta reduces to ONE sentence is untouched, and on chat 98
  that was the more common shape: turn 9's whole player view was "You are
  seated on the bar."; turn 10's "You are standing on the deck."; turn 38's
  "The lieutenant commander is close by. You see lieutenant commander." No
  room, no roster, no light — the narrator supplied all three from prose
  memory. **The question is whether PLACE and COMPANY are deltas at all.**
  They are continuously true, they are the frame every other sentence in a
  view is positioned inside, and `ACTIVE_STANDING_KINDS` already exempts
  sensations from suppression on exactly that argument ("an unchanged contact
  is still being felt now"). Against that: the tier's whole measured result
  was won by suppressing what the observer was already told, 772 of 2,645
  consecutive player-view pairs repeated a 60-character sentence verbatim
  before it, and a room's authored notes are long. A middle exists — restore
  the room's IDENTITY every beat and keep its notes and light on the delta —
  and it is a behaviour change to every story's prose, so it is named here
  rather than taken.
- **Two consecutive recovered views are byte-identical, by construction.**
  The recovery re-renders the same unchanged percepts, so a run of quiet
  beats hands the narrator the same paragraph each time. Measured live on
  chat 98 turns 39 and 40 (played on a copy, 2026-08-29): both views were
  the room, its notes, the roster and the pose, character for character, and
  both beats' prose still differed because `already_established_phrases`
  fills from the view against recent narration and is doing exactly the job
  it was built for. Recorded because the mechanism is not obvious from the
  code: the composer is not deduplicating across beats here, the narrator is.

One thing the replay surfaced that is NOT a residual, recorded so the next
reader does not re-open it: the stored corpus shows a structured overlay
reaching the page as a Python `repr` (`currently {'name': 'tail',
'description': '...'}`, chat 89, every beat). `story/scene.appearance_of`
already renders overlay dicts by description and has since before this work;
those rows are historical prose, not live behaviour. A stored view is a
record of what an older engine composed, and reading one as evidence about
the current one is the mistake this paragraph exists to stop.

<a id="unbuilt-1-93"></a>

### 1.93 A contact with an object is narrated as a contact with a person

The scene held one contact and it was CORRECT: `{actor: <player>, actor_part:
"hands", target: <a console entity>, target_part: "surface", manner: "pushing
sequence data", relation: "surface"}`. Hands on a console.

What reached the page, two beats running: "her palms rested against a surface
that pressed back — steady, warm with something other than her own heat" and
then "Her hands were against SOMEONE. Not the console, not the chair's arm — a
surface that gave back warmth and weight of its own." The second explicitly
rules out the console, which was the right answer.

The data is right and the rendering is wrong: a contact percept applies body
vocabulary — warmth, weight, pressing back — without asking whether the target
is a body. Precedent for the shape of the fix is
`spatial_transit._is_body_entity`, which refuses to read `kind` and derives
bodyness from attire/scales because the label could not be trusted.

Second half: a settled contact was re-narrated on every subsequent beat. A
standing contact should become background after the beat that made it.

<a id="unbuilt-1-109"></a>

### 1.109 A spoken line shorter than four characters is invisible, and takes the next one with it

**Found:** building the narrator placeholder protocol, 2026-08-24.

`_QUOTE_BODY_RE` matches an opening quote mark, then a run of at least
**four** non-quote characters, then a closing mark. That `{4,}` means a quoted
line of three characters or fewer -- `"No."`, `"Aye."`, `"Sir."` -- never
matches, so DIALOGUE FIDELITY does not check it and the narrator may drop it
freely.

**The second half is worse than the first.** The two quote marks the regex
skipped do not disappear; they pair with their neighbours. Given two short
lines in one view, the span BETWEEN them matches instead:

    'Picard says in a flat voice: "No." Riker says in a quiet voice: "No."'
    -> [' Riker says in a quiet voice: ']

So the check can be handed the composer's own attribution formula as though it
were a delivered line, and then complain that the narrator failed to reproduce
it. Every fidelity finding on a beat containing an odd number of sub-four
character quotes is therefore suspect.

`agents/common._dialogue_tokens` guards its own output with
`_reads_as_attribution`, because feeding that span to the narrator as a line to
PLACE would print `Riker says in a quiet voice:` inside quotation marks. The
underlying regex is untouched: raising `{4,}` to `{1,}` would admit stray
inch-marks and initials as dialogue, and the right fix is probably to match
quoted spans pairwise rather than by content length -- `static/js/chat.js`
already does exactly that (`quotedRegions`) for the speaker tinting, and its
comment explains why the region rather than the match is the unit.

<a id="unbuilt-1-116"></a>

### 1.116 The 2026-09-05 play runs: the perception-delivery classes

**Found** by five fresh scenarios played end to end on 2026-09-05 (the
lighthouse, `experiments/PLAY_2026_09_05_lighthouse.md`; the Ambry road,
`PLAY_2026_09_05_road.md`; the manor, `PLAY_2026_09_05_manor.md`; the flat,
`PLAY_2026_09_05_flat.md`), every stage of every beat read against the
others. Five of them are one family — what perception hands a mind, and what
that mind then remembers — and they are FIXED together, pinned in
`tests/test_played_scene_classes.py`:

- **PA1 (firewall)** — an act that crossed rooms was delivered whole to an
  observer who had a channel only to the room it began in, and became that
  mind's episodic memory (lighthouse turn 16, `memories` rows 69 and 77).
  FIXED: `director_movement.crossing_legs` walks the rooms a body was in;
  `perception._channel_to_every_leg` admits the beat's single surface only
  where the observer's channel stood in every one of them. One boundary is
  left exactly as it was.
- **PC1 + PE9 (firewall)** — sight is graded and the act channel was not:
  a `shapes`-only grade (a crossing record floors sight there for a beat)
  bought a readable description of conduct through a locked door (manor turns
  11-12), and `_in_plain_view`'s `same_room` short-circuit meant an occluder
  inside one room never subtracted at all (PE9). FIXED:
  `perception._sight_detail` passes the grade, and `composer.act_percept`
  spends it — `full` admits the surface, `shapes` a motion percept naming no
  object, `none` refuses.
- **PD3 (story-breaking, corrupts memory)** — a fragment from a speaker the
  observer could see and knew was delivered anonymously, the narrator
  invented a source for it, and the invention was filed as fact (road turn
  20). FIXED: `composer.speech_percept` marks a fragment `attributed` when
  the observer can see who spoke; both renderers keep the speaker.
- **PC2 (story-breaking)** — a line whose `conceal_from` named its own
  addressee reached nobody, the addressee included, and the player's declared
  speech was silently deleted (manor turn 17). FIXED:
  `director_floors.strip_addressee_concealment` strips every addressee the
  ELEMENT names, and a line concealed from every body in the scene is
  reported as a dropped declaration.
- **PC3 (story-breaking), half of it** — the act pass and the outcome pass
  graded one shout differently because the relations perception builds for a
  beat did not all carry the same sound field (manor turn 16, F61 with the
  roles reversed). FIXED here: every `spatial_rel_between` perception builds
  for a beat is given the beat's field. **STILL OPEN:** the field's own floor
  — a raised voice one passable edge away should not grade below `fragment`
  when the edge model says `full` — belongs in
  `world/spatial_sound_field.py` and is not built. Until it lands the two
  passes agree and both are the strict answer, so a shout across one open
  archway can still reach nobody.

**Still open from PA1's own report**, and deliberately: the per-leg action
ELEMENT. The Director cannot say which leg an act happened on, because
`ActionElement` has no room and `agents/common.norm_sequence` whitelists the
keys it carries, so a walk past one boundary delivers the crossing percepts
and not the act surface to the observers at either end. Restoring the prose
needs three edits nobody has made: `ActionElement.room` in `llm/schemas.py`,
that key carried through `norm_sequence`, and one clause in
`director_interpret` stating the class — a declaration that crosses rooms is
one action element per room, each describing only what happens there. The
deterministic floor above does not depend on any of them and must stay
whichever way that goes.

<a id="unbuilt-1-117"></a>

### 1.117 A sound that HAPPENS has no channel, and `running` is the only word for it

**Found 2026-09-05** by the lighthouse play run (PA2) and by the market turn 3
of `DEBUG_RUN_2026_09_05.md` section 2.36, which measured the complementary
half: a whistle blown on one beat reached nobody, because there is no
`sensory_events` channel after establish. Seen from the other side, the same
gap made a fog bell rung ONCE into a permanently running source, and nine
beats of one story were rewritten by a noise floor of 20.5 against a
whisper's 0.34.

**Narrowed 2026-09-05 to three lines of wiring**
(`docs/design/DESIGN_SOUND_DECIBELS.md` § 4, § 8). The channel is BUILT: the
shape (`spatial_sound_field.normalize_sensory_event`, a closed set of keys,
capped at `MAX_SENSORY_EVENTS` 8 a beat), the write
(`commit_scene_state._record_sensory_events`, which stores the beat's sounds
under the beat that made them and drops the record on any beat that makes
none), and the read (`beat_sensory_events`, which refuses any beat but its
own). The beat number IS the lifetime, so nothing decays and nothing expires
on a counter. The objects hand's card now points a one-off at that channel
rather than at `state.<x>_action`, and a sound loud enough to leave the room
travels the room graph to wherever it is still audible
(`spatial_sound_field.distant_sounds`).

**Closed 2026-09-05.** The three edits landed:
`StateDiff.sensory_events` (`llm/schemas.py`, so the channel survives the
validation round trip), `SPECIALISTS["objects"]["channels"]`
(`agents/director_scopes.py`, with the schema, category and ledger registries
that guard it, and a `sensory_events` chunk in both packs — the note said the
objects card already asked for it and it did not), and the delivery
(`agents/perception._composer_outcome` → `composer.distant_sound_percepts` /
`render_distant_sound`, pinned in `tests/test_distant_sound_delivery.py`).

The delivery reads the beat's own diff rather than `beat_sensory_events`,
which is where the note's § 8 was wrong about the code: the scene's record is
written by the commit, and the commit runs after the narrator — so the read
it specified would have answered `[]` on the beat that made the sound and
`[]` again next beat, when the beat number has moved. The stage normalises
with the commit's own `normalize_sensory_event`, so what a view delivers and
what the beat stores cannot disagree about which events were real.

**One residual, and it is the dispatch.** A hand runs when the Director's
ruling reaches it, and a one-beat signal is not a persistent change, so it
has no manifest category and reaches the objects hand only through a
`ledger_notes` line keyed `sensory_events`
(`tests/test_director_orchestration._UNREACHABLE_BY_DESIGN` records why).
On a beat whose only object-world event is a noise, nothing else dispatches
that hand — so whether the prose author reliably writes that note is
unmeasured, and is the next thing to watch.

`commit_scene_state._report_started_sources` continues to tell the Director
on the next beat about every `running` switch a beat threw.

<a id="unbuilt-1-118"></a>

### 1.118 Residuals from the addressed-hearing repair (PB1/PB6)

**Landed 2026-09-05** with the caravanserai firewall fix
(`docs/experiments/PLAY_2026_09_05_caravanserai.md` PB1/PB6): being addressed
changes whether a body is PICKED to answer, never whether it heard
(`persist/commit_background.address_reaches`), and a description is resolved
against the room the beat's diff puts the speaker in (`beat_scene`). Three
things were deliberately left.

* **`docs/design/DESIGN_BACKGROUND_PRESENTATION.md` §C3 still states the
  addressee guarantee unqualified** ("an addressee is never silently
  dropped"), and the code now qualifies it: an addressee who could not
  receive the line is not one this stage has anything to hand. The comment in
  `pick_voice_demand` carries the qualification; the design note does not.
  One sentence, in the note's own vocabulary, is what it owes. (Left because
  the note was outside the fix's edit scope, not because the change is
  uncertain.)

* **The background packet still says nothing about HOW WELL a body heard.**
  The play run's own proposal (§6): carry the graded `hear_level` on
  `addressed_by` and state in the `background_react` sheet that a body
  answers what it heard rather than what it was told about. Not needed for
  the firewall — the deterministic floor is the gate, and a leak must not
  depend on a model cooperating — but a presence handed a line it made out
  only in part has no way to say so, and currently either answers it whole or
  is not picked at all. The engine has the number; the packet drops it.

* **`agents/background._filtered_player_declaration` and
  `_beat_for_presence` grade a line without proximity**, while every cast
  path (`agents/loops.py`, `composer.line_hear_level`) passes it. So a
  background presence across a large room from a whispered line receives it
  in full where a registered mind would get a fragment. Not a cross-room
  leak — both read the same rooms — and not what PB1 was: the gate now
  refuses the pick in that case (`measured_proximity_rel`), so the content
  filter is not reached. It is an inconsistency between two readers of one
  question, which is the shape every other defect in this family had.

<a id="unbuilt-1-120"></a>

### 1.120 Outdoors, ordinary speech is `full` only inside about five paces — a constants decision

**TAKEN AND LANDED 2026-09-05.** The owner accepted the recommendation
below in full: `AMBIENT["open"]` 0.2 → 0.1 (27.0 → 30.0 dB, level with
`sheltered`) and `WEATHER_NOISE` light/moderate/heavy 0.3/0.6/1.0 →
0.1/0.25/0.5, and nothing else — `WIND_NOISE` deliberately unmoved, because
wind you have to raise your voice over is what wind is. Landed with the
test § 1.120 asked for (`tests/test_sound_field.py::
test_a_road_is_a_road_you_can_walk_and_talk_down`). Measured after, for a
normal voice, `full` radius in paces: fair 5.4 → **7.7**, light rain 3.3 →
**5.4**, moderate 2.5 → **4.0**, heavy 2.0 → **3.0**, heavy + gale 1.3 →
**1.7**. A road you can walk and talk down, and a downpour you have to raise
your voice in.

It interacts with the far field built the same day
(`DESIGN_SOUND_DECIBELS.md`) in one direction only, and less than expected:
the flood's TERMINATION is bounded by the quietest floor the model has,
which is `AMBIENT["enclosed"]` and did not move, so a `catastrophic` event
still reaches exactly 51 medium rooms of open doorways and no further. What
changed is what an OPEN room can hear of it — audible in 43 → **48** of
those rooms in fair weather, and 37 → **43** in light rain.

The rest of this entry is the measurement and the argument as they stood
before the decision, kept because the decision is only legible against them.

**Found 2026-09-05** (`docs/experiments/PLAY_2026_09_05_road.md` § PD2),
measured again here against the constants as they stand. NOT a bug: the
ambient floor is applied once, to the LISTENER's cell's room
(`SoundField.noise_at` reads `self.ambient[grid.inside[cell]]`), and the
weather term is a separate quantity from the exposure term
(`_ambient_floor` = `AMBIENT[exposure]` + `WEATHER_NOISE[intensity] * gain` +
`WIND_NOISE[wind]`, and `weather_for_room` returns `gain` 1.0 for an open
room, so nothing is counted twice). What is in question is the VALUES, and
they are the owner's.

Straight-line radii in cells at which each volume is still `full` / still
`fragment`, solving `P/(1+d²) >= max(SNR * noise, HEAR_FLOOR)` on the
constants as they stand (a real path costs 1.4 per diagonal, so these are
upper bounds):

| room | noise | whisper | normal | loud | shout |
|---|---|---|---|---|---|
| enclosed, still | 0.05 | 3.0 / 4.4 | 10.9 / 15.5 | 20.0 / 28.3 | 34.6 / 49.0 |
| sheltered, still | 0.10 | 2.0 / 3.4 | 7.7 / 12.2 | 14.1 / 22.3 | 24.5 / 38.7 |
| open, fair | 0.20 | 1.2 / 2.3 | 5.4 / 8.6 | 9.9 / 15.8 | 17.3 / 27.4 |
| open, light rain | 0.50 | — / 1.2 | 3.3 / 5.4 | 6.2 / 9.9 | 10.9 / 17.3 |
| open, moderate rain | 0.80 | — / 0.7 | 2.5 / 4.2 | 4.9 / 7.8 | 8.6 / 13.7 |
| open, heavy rain | 1.20 | — / 0.2 | 2.0 / 3.4 | 4.0 / 6.4 | 7.0 / 11.1 |
| open, heavy rain + gale | 2.20 | — / — | 1.3 / 2.4 | 2.8 / 4.7 | 5.1 / 8.2 |

The rule the constants should satisfy, stated by the run that found it: *two
people walking together on an open road converse in full; the road takes
their voices at the distance you would have to raise your voice in life.*
Fair weather outdoors already gives 5.4 paces, which is about right. It is
the WEATHER term that closes the road: light rain — the commonest weather
there is — more than doubles the noise floor of an open room and takes normal
speech to 3.3 paces, and a campfire beside them (an `audible` source at 12)
took the same pair to `none` at four.

**Recommendation, for the owner to take or refuse.** Move two constants and
no others, both in `world/spatial_sound_field.py`:

* `AMBIENT["open"]` 0.2 → 0.1 (equal to `sheltered`). Open air is not itself
  a noise; what is noisy outdoors is the weather, which is counted
  separately, and 0.2 is currently four times a quiet room for no source the
  world holds.
* `WEATHER_NOISE` light 0.3 → 0.1, moderate 0.6 → 0.25, heavy 1.0 → 0.5.
  Rain you can talk through until it is heavy.

That gives, for a normal voice: fair 7.7 paces full, light rain 5.4,
moderate 4.0, heavy 3.0, heavy + gale 1.7 — a road you can walk and talk
down, and a downpour you have to raise your voice in. The alternative considered and NOT
recommended is raising `SPEECH_POWER["normal"]`: it also stretches the indoor
radius, which is already 10.9 cells, and compresses the ladder against
`loud`. Test to land with whichever is chosen: an empty `open` room, fair
weather, two bodies four paces apart, normal volume ⇒ `full`.

<a id="unbuilt-1-121"></a>

### 1.121 The two rescues that promote an unheard line, and the record that would show them

**Found 2026-09-05** (`docs/experiments/PLAY_2026_09_05_lighthouse.md` § PA4),
half-addressed. The delivered clarity of a cross-room line is not
reproducible from the committed scene: a shout three rooms up a stone tower
was delivered verbatim on four separate beats, while every deterministic
reader replayed on the same scene answers `fragment` or `none`. The 2026-09-05
sound work removed one candidate cause (the pair's gain is now the same
number from either end, § PB2) and capped the answer by the listener's own
noise (§ PA5), so the live grade can no longer beat the room it is heard in.

What is left is in files that repair did not own: `composer.speech_percept`'s
`open_group_continuity` floor (`composer.py:2116`), which turns `none` into
`full` for any normal/loud/shout line, and `line_hear_level`'s addressed
rescue, whose premise — that a by-name exchange across a barrier implies a
device carrying it — is false in a stone tower. Both promote an unheard line
to a full verbatim quotation, which is a comm channel invented from a name.
**The record landed 2026-09-05.** `speech_percept` now carries the
`note_step_decision` record `act_percept` has -- level, how it was reached,
volume, barrier, tier -- naming the comm channel, the addressed rescue and
the open-group floor as three separate answers. **Neither rescue is dead and
neither was deleted** (§ 1.126 audits the proposal and the two tests that
prove them live). What is still open is only the addressed rescue's PREMISE:
whether being named across a barrier should survive distance as well, since
three rooms up a stone tower is not one closed door. Decide it on the next
run's record.

**The next run answered it, twice** (2026-09-05, campaign 3): masque § PX6, a
line from two closed doors and a room away delivered complete and attributed
in a view whose two unaddressed voices were correctly fragments; rush § PR5, a
verbatim shout from two rooms and two vertical hops below to a listener whose
card says hearing acuity "poor". The bound, and a second defect the same
reading exposed (the rescue outranks the senses gate), are written out as a
patch in § 1.129.

<a id="unbuilt-1-125"></a>

### 1.125 The decibel constants: a wall's loss, two new rungs, and three margins

**`WALL_LOSS_DB` RESOLVED 2026-09-05, and it was a UNIT rather than a
judgement.** The question was posed as 45 (the physical number) against 18
(the number that makes the note's own sentences true), and both readings
missed that the table is not denominated in real decibels at all. The
aperture losses are derived from `APERTURE_PASS`, calibrated against the near
field's own sentences; `SPEECH_POWER` was widened to give a voice "the ratio a
real voice has" in ORDER but not in span. Measured, and the two spans agree to
three decimals: whisper->shout is 20.8 dB here against 58 in the world, and
normal->shout 10.0 against 28 -- a compression of **0.358** either way. Every
aperture is already on that scale (window 10.0 against a real 28 scaled to
10.0, exactly; open_door 0.5 against 0.7; membrane 3.0 against 1.8;
closed_door 6.0 against 9.0). Only `wall` and `floor/ceiling` were raw.

So 45 and 50 were the same physical numbers as everything else, in the wrong
denomination, which is why they behaved like a bunker. They are now **16** and
**18** -- a real 45 dB wall and a real 50 dB floor, compressed. Measured
through medium rooms against the 27.0 dB floor: before, only `catastrophic`
crossed one wall and NOTHING crossed two; after, `thunderous` carries through
two walls and through a floor-and-wall, `catastrophic` through three,
`deafening` crosses one and dies at two, and a `loud` event still crosses
nothing. A shout still dies against a wall (60.8 - 16 - 21.6 = 23.2, under the
floor), which is the sentence the number had to keep.
`tests/test_sound_field.py::test_every_barrier_in_the_table_is_on_one_scale`
derives the compression rather than asserting it, so the next edit that
reaches for a physical number and forgets to scale it fails.

**STILL OPEN, and now the sharper question: `FAR_FIELD_ENTRY_DB` = 70.** It
sits above `deafening` (61.8) so that only `thunderous`, `catastrophic` and an
authored `db` flood the room graph -- which was exactly the ask ("incredibly
loud noises can travel very far"). With the wall fixed, a `deafening` source
WOULD now be heard through one wall (30.1 dB against the 27.0 floor) if it
were admitted, and a burning stairwell, a fire alarm and a running engine are
all `deafening` rather than `thunderous`. The tenement that measured this
(rush § PR6) wrote its fire as `loud`, which crosses nothing on any setting,
so the classification is half the question. Deriving the entry as
`SOUND_DB["deafening"]` rather than a literal 70 would also stop it drifting
from the rung it is defined against. Not taken: it widens the far field
beyond what was asked, and the walk cost is the owner's to spend.

**Answered by the ladder, 2026-09-14.** The emission rungs are real levels
now (§ 1.159): a standing `loud` source is 83 dB at its cell and
`deafening` 103, so both clear the unchanged entry of 70 and an engine or a
klaxon walks the room graph. The walk is one Dijkstra over a cached graph per
such source per beat, measured at nothing on a beat of conversation; the
owner is spending it by virtue of the numbers rather than by a decision here,
and can move `FAR_FIELD_ENTRY_DB` if that is wrong.



**Built 2026-09-05** (`docs/design/DESIGN_SOUND_DECIBELS.md`). The model is
denominated in decibels, a wall has a finite transmission loss, and a sound
over 70 dB floods the room graph until it is inaudible. The conversion was
exactly identity — 12,685 tests unchanged — so everything below is a NEW
number, and every one of them is the owner's.

**Taken as the note proposed, and pinned:** `WALL_LOSS_DB` 45,
`FLOOR_CEILING_LOSS_DB` 50, `FAR_FIELD_ENTRY_DB` 70, `SOUND_DB`
`thunderous` 85 / `catastrophic` 100. **New, not in the note, and named
here because every cap in this engine is named:** `DB_REF` 40 (the
reference; arbitrary, and it cancels out of every comparison but the
absolute floor and the far-field entry), `OVERWHELMING_MARGIN_DB` 20 (where
a distant sound stops being something you notice), `MAX_SENSORY_EVENTS` 8
(one-off sounds one beat may hold), `_DB_EPS` 1e-12 dB (arithmetic, not a
judgement: measured at seventy times the worst error a logarithm introduces
at an exact threshold).

`OVERWHELMING_MARGIN_DB` and the `DISTANT_LEVELS` words it grades reach a
READER as of 2026-09-05 — the delivery landed with § 1.117 — so the margin
is now something a play test can feel rather than a number in a table.

**The one decision this work could not take.** At 45 dB the wall does half
of what the note claims. Measured, medium rooms, enclosed, floor 27.0 dB:

| | one wall | two walls |
|---|---|---|
| shout (60.8 dB) | inaudible | inaudible |
| deafening (61.8) | inaudible | inaudible |
| thunderous (85) | 18.4 dB — inaudible | inaudible |
| catastrophic (100) | 33.4 dB — **heard** | inaudible |

"A shout is inaudible through it" holds. "A `catastrophic` event is a
fragment two rooms away" holds through doorways and NOT through walls: only
the top rung crosses a wall, and only one wall. The three numbers that
decide this are the wall's loss, the top rung, and the per-room spreading
term, and moving any of them moves the answer.

**Recommendation, for the owner to take or refuse.** Leave 45 dB and accept
that a wall is nearly absolute — it is the physical number for masonry, and
"one wall stops all but the loudest thing in the world" is a defensible
sentence about a building. If the note's sentence is the one that matters,
`WALL_LOSS_DB` 18 makes both halves true (a shout still dies at one wall; a
catastrophic event is a fragment at two) at the cost of a wall that a
`thunderous` sound also crosses. Do NOT reach for raising `catastrophic`
instead: it is already 38 dB over `deafening`, and stretching it further
compresses everything under it into one rung. **Test to land with whichever
is chosen**: two enclosed medium rooms joined by a `wall`, a `catastrophic`
event in one ⇒ heard in the other; a `shout` ⇒ not.

**And one measurement worth a play test before anything is moved:** a
`catastrophic` event crosses about 50 medium rooms of open doorways before
it terminates on audibility, and a `thunderous` one about 28. That is the
owner's sentence working — an incredibly loud noise travels very far — and
it is also the number most likely to feel wrong in a town.

<a id="unbuilt-1-128"></a>

### 1.128 What the light-and-sources repair left for other hands

**Filed 2026-09-05** alongside the PQ1 / PQ2 / PR6 / PR14 / PX7 / PM17
repair. Each of these is one edit in a file that lane's own work owns; none
of them is load-bearing for what landed.

* **`agents/perception.py::_sight_detail` — docstring only.** It says "every
  grader here already answers in three words -- `sight_level` and
  `visual_level_between` both return none/shapes/full". There are four now
  (`none | shapes | conduct | full`, `world/spatial_light._LIGHT_SIGHT`).
  The CODE is already right and is why PQ2's repair reaches the act channel
  at all: its last line is `return "shapes" if level == "shapes" else
  "full"`, so `conduct` delivers the observable surface, which is exactly
  "dim withholds detail, not conduct". Only the sentence is stale.
* **`agents/composer.py::pose_percepts` — a possible widening.** A body at
  `conduct` yields posture and nothing else, because the grade is not
  `full`. The subtraction is safe and may be right; the case for widening is
  that `support` ("sitting in the wing chair") is gross conduct rather than
  detail, and a dim room now grants the rest of a body's conduct. Not taken
  here, because it is the composer's judgement and under-granting is the
  safe direction.
* **PR14's other half — the standing substances and conditions.** The
  backdrop brief carries the room's light already (`room_projection` adds
  `light` and `light_sources`; the finding measured `room_brief` alone, one
  layer down). What it still does not carry is what is standing IN the room:
  a smoke plume, a `world_conditions` fire. That is the same class as lane
  D's finding that six `world_conditions` landed and nothing in perception
  or the composer reads them, and it should be fixed once, there.
* **The objects specialist's source clause (PR6, mid-play half).** The
  establish now states that a thing that gives light or keeps up a sound is
  an entity with `light_source` / `sound_source`, and the spatial hand's
  `rooms` chunk states that a room's light word never says what gives it.
  The hand that would mint a fire a BEAT introduces is `objects`, and
  `specialists/objects/chunks/entities.txt` says nothing about sources in
  either pack.

<a id="unbuilt-1-129"></a>

### 1.129 The perception-admission lane of the campaign-3 runs: what landed, and the seven answers that live in other files

**Worked 2026-09-05** over `PR1`, `PM5`, `PS13`, `PX5`, `PX6`, `PR5`, `PR8`.
Three landed. The other seven answers are written out here rather than
applied, because each belongs in a file this work did not own -- stated with
its live case and its exact condition, so the next hand applies it without
re-deriving the evidence.

**Landed.**

* **PX5 (firewall).** An actor's `observable` is free text describing the
  ACTOR, and the act channel admitted the whole string on the actor's
  channel alone -- so any OTHER body it named arrived as an unadmitted
  percept about that body. Live (masque t6): "looks leisurely over Ivo's
  uncovered face, then lifts his wine glass…" was delivered verbatim to a
  body two edges away and to a body whose own view in the same beat read
  "Through the glazed terrace door, only darkness". The identity scrub could
  not see it, because it asks whether an observer has earned a NAME and the
  leak was the STATE beside it. `perception._act_surface_admission` now cuts
  the span that names a body this observer's own eyes did not reach, on both
  delivery floors, and refuses the percept where no span survives. The rule:
  *what a body is seen doing is admissible; what it is seen doing it TO is
  admissible only where the target is.*
* **PR5, the half that was one line graded by two floors.** `perception_act`
  passed the RAW proximity tier into `speech_percept` while
  `perception_outcome` passed the measured one, against
  `line_hear_level`'s own stated contract -- and "near" is the fallback for
  the 93% of bodies with no station, so a quiet line was a fragment on the
  way in and whole on the way out.
* **PM5, isolated.** The branch the report could not find is
  `spatial.entity_arc` -- the within-room blind spot, consulted three times
  per observer and DROPPING each time. It follows FACING, which is why it did
  not follow station: the three factors who received nothing were turned
  north while the doors were south. Pinned in
  `tests/test_perception_act_reaches_the_room.py`.

**PX5's THIRD floor, in `agents/loops.py`.** The interaction micro-loop
delivers `observable_action_text(event)` straight into an observer's additions
(`deterministic_micro_perception`, the `type == "action"` branch) with no
third-body admission at all, so the same leak is live on the micro-round path
that the two perception passes are now closed on. It needs the same call. The
helper is `agents.perception._act_surface_admission` today and `loops.py`
importing `perception` would be a new role-module cross-import (already
discouraged, already real for `loops -> character`); moving it to
`agents/common.py` -- which both already import -- is the clean placement, and
it needs the observer's seen-set, which the micro-loop computes as
`_delivery_ok` per body rather than as a set.

**PM5's remaining half, in `agents/composer.py`.** `entity_arc` promises "no
new visual detail … though sound still carries" and neither half holds.
(a) `presence_percepts` (composer.py:1021) drops a rear-arc body outright, so
a woman who has stood in the room for eight beats is not in the room at all
for whoever happens to be turned away -- a body already present is not new
detail. (b) `act_percept` mints a HEARING percept for the rear arc
("something moved, and where") -- built 2026-09-05, and dead on the outcome
pass until 2026-09-07, where a pre-skip on `behind`/`can_see` ran before the
call; both passes now let the composer decide the arc. The run's most visible
nonsense -- the chair ordering doors unbolted that the player had just heaved
open in front of her -- was this half.

**PX6 / PR5's second half, in `composer.line_hear_level`.** Two independent
runs now answer § 1.121's open question the same way, and the record
`speech_percept` gained on 2026-09-05 is what makes it answerable. The
addressed rescue must be bounded by DISTANCE as well as by the barrier, and
must not outrank the senses gate:

1. *Distance.* The rescue's premise is that a by-name exchange across a
   barrier implies a device carrying it. One closed door is a barrier; two
   closed doors and a room is a ROUTE, and a route implies nothing. Gate the
   spoken-volume arm on the relation naming ONE DECLARED EDGE at
   conversational range -- `rel["barrier"]` neither `"separated"` (no edge
   between these rooms) nor `"unknown"` (no room known), and
   `rel["distance"]` not in `("far", "remote")`. The load-bearing case § 1.126
   pinned -- an ordinary named call through one closed door -- is adjacent,
   `closed_door`, `near`, and survives untouched. The explicit
   `medium == "comm"` arm is a real transmission and keeps crossing anything.
   Live: masque t16, a line from `music_room` through two closed doors and a
   room arrived complete and attributed while two unaddressed voices in the
   same view were correctly fragments; lighthouse § PA4, a shout three rooms
   up a stone tower, four beats running.
2. *Senses.* The rescue returns `"full"` AFTER `base = _sense_graded(…)` has
   run, so it is the one grade a card cannot dull. Live (rush): Mirela's card
   says hearing acuity "poor" (-1), and one view carried both "Vesna Kolar
   says something you cannot make out: …gospođa… carrying… nothing…" from a
   woman leaning into her good ear AND, on turn 12, a verbatim shout from two
   rooms and two vertical hops below. Grade the rescue's answer through
   `_sense_graded` like every other.

**PR5's third half, in `world.spatial_senses.sense_adjusted`.** There is no
rung above `full`, so a -1 offset makes `full`->`fragment` unconditional: a
dulled ear is total deafness for CONTENT at every volume and every distance,
and a speaker has no way to compensate. The design's own words are
"fragment->full is an ear pressed to the door". The rule: *a shift that would
silence content the channel is delivering at its own ceiling yields to a
measured intimacy or a raised voice* -- the exception `_measured_intimacy`
(spatial_senses.py:731) already makes for dim sight, applied to hearing.

**PR8, in `world.spatial_senses._opening_view_cap`.** A body stationed at a
hand-authored anchor that IS a doorway is invisible from the next room. The
function exempts only the implicit `door_anchor_id(other_room)` pseudo-anchor;
an establish-minted anchor `doorframe` ("The wooden frame of the front
entrance door", `dir: w`) on the same bearing as the edge lands 4 sectors from
`away` and caps to `none`. Live (rush t1-2): `body_visibility` answered
`{visible: True, basis: "line"}` and `visual_level_between` answered `"none"`
for the same pair in the same beat; the composed view named the frame the
woman was gripping and not the woman. F58 proposes the fix and this is the
argument for it: fold an anchor whose description names an exit onto that
exit's implicit door anchor. (The alternative that reads no prose -- letting
an anchor record which edge it sits on -- needs a field the scene does not
carry.)

**PR1, in `world.spatial.invalidate_moved_body_place_details`.** Reproduced:
a body whose pose `detail` names a place in the room it LEFT keeps that
detail through the merge, and the outcome pass delivers it to every other
observer -- so one perception pass composes a view saying the body is here and
a view saying it is still over there. The retirement exists and is correct;
its PLACE VOCABULARY is "every room id and name, plus the id/desc of every
anchor of the room left", and a world whose establish minted no anchors (PX7)
has an empty vocabulary, so nothing matches and nothing is retired. Live
(rush t19): both bodies moved to `roof_16` and the player's view read "Tomo
Lisak remains prone and motionless against the tar paper beside the hatch",
which the narrator sited across an eighteen-inch gap. The rule that needs no
vocabulary at all: *a mover's own pose detail is spent on a room change
unless this beat's own diff wrote it* -- which is the `stated` exemption the
function already has, with the phrase test dropped. It subtracts strictly
more than today and depends on nothing the establish may have failed to mint.

**PS13, in two places, neither of them perception.** A world with nobody in
it had a live and permanently empty hearing channel across twenty beats, and
a dressed-stone barrel vault returned no echo to a player-asserted acoustic
fact. The delivery is built and reached -- `_composer_standing_percepts`
calls `composer.soundscape_percept(sound_shape(...))` for every observer --
and it has nothing to say because nothing gives an empty room an acoustic
character: a room already carries `exposure`, `extent` and anchor `opacity`,
and a room-level acoustic property derived from them is the fix, in the sound
field. The other half is the Director's: turn 5 raised
`claim:4:event ('her own voice comes back at her off the ceiling')`, the
resolve returned no `fact_adjudications` verdict, and the narrator was then
free to write "No answer comes back from the stone" and, thirteen beats
later, "the barrel vault swallowed the sound without an echo". Adjudicating
the claim is the minimum; a dropped claim is a licence to assert its
opposite.

<a id="unbuilt-1-136"></a>

### 1.136 The rear arc promises sound and delivers silence — ANSWERED and BUILT 2026-09-05

**Isolated 2026-09-05** (multitude § PM5, lane B's trace). `spatial.entity_arc`
documents the blind spot as *"the observer gets NO NEW VISUAL detail from them
(a silent approach or gesture is unseen) though sound still carries"*, and
neither half of that holds:

* `composer.presence_percepts` drops a rear-arc body **outright**, so a body
  that has stood in the room for eight beats is not in the room at all -- not
  merely undetailed.
* `composer.act_percept` refuses on the arc with no substitute, and nothing
  carries the sound, because an act reaches an observer on the SIGHT channel
  alone.

Measured: five factors at one anchor; the three turned north got neither the
act nor the actor's presence and acted as if the beat had not happened, while
the two turned south got both.

**Why this is not fixed here.** The obvious repair -- admit a rear-arc body's
presence and withhold only detail -- is the same edit that would announce a
thing walking up behind you, and the blind spot is the machinery a horror
scene runs on. The Sarah Moon descent run
([[sarah-moon-descent-run]], creatures that are dangers rather than
interlocutors) will exercise exactly this, in both directions, within its
first twenty beats. So the fork is stated and left:

* **(a)** presence is not a visual detail -- a co-present body is in the room
  whichever way you are facing, and what the arc takes is their conduct and
  their appearance. Costs the silent approach unless something else conceals
  them; `concealed_from_observer` and `visual_level_between` are the channels
  that already exist for deliberate concealment, and the argument is that
  hiding should be a thing a body DOES rather than a consequence of where the
  observer's nose points.
* **(b)** the arc stands as it is, and the missing half is the SOUND the
  contract already promises: an act in the same room reaches a rear-arc
  observer on the hearing channel, ungraded by sight. This needs an act to be
  deliverable by hearing at all, which is § 1.117 from the other side and is
  a representation change rather than a gate change.

**The owner took (b), and sharpened it into three rules.** *"Receive only the
sounds someone behind you makes"*; *"it doesn't make sense to identify someone
purely by sound"*; and, on a voice specifically, *"Their voice? Yeah
absolutely if you already know them ... But maybe someone purposefully adjusts
their voice."*

**Built.** A rear-arc act is now a HEARING percept: that something moved, and
where, never who and never what they were doing -- the surface is dropped
whole and the label with it, because a footstep carries no identity.
`spatial.sound_bearing` supplies the observer's own egocentric sector where
the geometry supports one and nothing when it does not, and it is
firewall-clean by construction (its record names no room and no body).
`act_heard` / `act_heard_placed` in both packs.

And the voice half, which turned out to be a defect of its own:
`speech_percept` gated attribution on SIGHT, so a line from a body behind you
-- or across a dark room, or through a door -- arrived anonymous however well
you knew them. Recognition is the question, and `observer_display_map` already
answers it, returning a recognised body's own NAME and a stranger a
descriptor. It applies `disguise_breaks_recognition` on the way, so a disguise
that MEANS to conceal who somebody is takes their voice with it and one that
only hides features does not -- which is the owner's third sentence, already
built, reached by asking the existing question instead of a new one.

**(a) was NOT taken and the blind spot is untouched**: a body behind you is
still absent from presence, still gives no appearance and no conduct. The
descent run will exercise it.

**Residual, registered rather than invented: a VOICE-ONLY disguise.** Ordinary
appearance, deliberately altered voice, is a real thing a body does and the
engine has no field for it -- `conceals_identity` lives on the disguise, which
is about what is seen. A per-line or per-body voice-concealment flag is the
shape, and it wants authoring surfaces (card, Director channel, both packs)
rather than a guess.

**Also still owed: a genuinely SILENT act behind you.** What is delivered now
is "something moved", and a gesture makes no sound. The engine cannot tell a
footstep from a raised hand without reading the prose, which is the guard
class this repo has been burned by; the structural answer is whether the body
CHANGED PLACE this beat, which `act_percept` cannot see. Over-granting a sound
is the safe direction against three of five bodies missing the beat entirely,
and it is the direction taken.

<a id="unbuilt-1-140"></a>

### 1.140 A crowbar on steel does not carry eighteen paces down a dead corridor — BUILT 2026-09-06

**Measured 2026-09-06, descent turn 13, with the geometry finally right.**
Every gate in § 1.137 is fixed, the field spans the spine and the annex, all
three of the beat's sound events are placed, and the answer is still `none`.
The arithmetic, at the containment annex's cell, through the shut containment
door, 18 cells down the vaulted service spine:

  * the `loud` crack of a pry bar on a bulkhead seam: **24.9 dB**
  * the room's own ambient floor (`AMBIENT["enclosed"]` 0.05): **27.0 dB**
  * so **SNR -2.1 dB**, against the -0.97 dB a `fragment` asks for.

It misses by a decibel. Both other events (`audible`, 19.7 dB) miss by seven.

**Where the two decibels went.** `loud` is 40 power against an enclosed room's
0.05, which is 29 dB of headroom. Against that: `10*log10(1 + L^2)` over 18
cells is 25.1 dB, and a `closed_door` aperture is 6.0 dB. 31.1 against 29.

**Two things are worth the owner's eye, and they pull the same way.**

  * **THE AMBIENT OF A DEAD SUB-LEVEL IS NOT THE AMBIENT OF A QUIET ROOM.**
    One constant, `AMBIENT["enclosed"]`, answers for a furnished parlour, a
    working plant room and forty years of condemned concrete alike. The
    engine has the room's own words for this -- `exposure`, and the light
    field's precedent of a declared word standing where the model can see no
    source -- and does not use them. A silent room ought to be a place where
    a small sound carries; here it is the thing that swallows a large one.
  * **A CORRIDOR IS A DUCT AND THE MODEL SPREADS SOUND AS A SPHERE.**
    `10*log10(1 + L^2)` is free-field inverse square, which is right for a
    hall and wrong for a 6 by 24 vaulted spine -- sound down a long narrow
    enclosed room decays far slower, because the walls stop it going
    anywhere else. The engine already holds the shape that decides this
    (`extent`, `shape`, `exposure`), so this is a law it could pick per room
    rather than a constant it would have to guess. The story's own dialogue
    said it out loud, twice, in two different rerolls of this beat: "the
    vaulted concrete profile operates as an acoustic waveguide."

**THE OWNER RULED FOR BOTH, 2026-09-06. The duct half is BUILT; the ambient
half is not, and this is what happened to it.**

  * **BUILT: `is_duct` / `DUCT_ASPECT` 3.0 / `DUCT_STEP` 0.5.** A room three
    times longer than it is wide, and roofed, costs a sound half a pace per
    pace. Charged only on a step WITHIN a room -- a wall crossing is one step
    from either side and keeps its cost, which is what keeps a path the same
    length measured from either end. On the beat that asked for it, 18 paces
    of vaulted spine: 25.1 dB of spreading loss becomes 19.1, and the annex
    that heard nothing hears a `fragment`. It fires on **0 of the owner's 570
    live rooms** and 2 of the descent story's 10, because extents are new and
    mostly come from the Room's plans -- so it is right, it is cheap, and it
    is so far unproven anywhere but the story it was built for.
  * **BUILT 2026-09-06 as a DECLARED WORD, after the first attempt was
    WRONG.** The proxy tried first was "a room with no anchors" -- nothing in
    it to make a tone -- and it was shipped, measured, and backed out within
    the hour: **292 of the owner's 570 live rooms (51.2%) carry no anchors.**
    That is not a dead sub-level, it is half the world, and most of it is
    rooms nobody has got around to furnishing rather than rooms that are
    empty in the fiction. It also broke two tests that were right to break --
    a shut door stopped grading a line down at all, and the far field's
    `faint` rung vanished. (The same lesson as § 1.138, one level up: measure
    the proxy against the corpus before believing it names the class.) What
    shipped instead is below.

**What the ambient half needed was a word, and the light field already had
the shape of it.** `room_light` is a DECLARED property of a room; sound had
no equivalent, so one constant answered for a working plant room and forty
years of condemned concrete. `rooms[rid].quiet` -- hushed | dead,
`world.spatial.QUIET_SCALE`, x1/4 and x1/16, six decibels a rung -- is that
word: a `RoomDef` field, a clause in both packs, an entry in
`_ROOM_SILENT_WHEN_EMPTY`, and a scale on `_ambient_floor`.

**IT ONLY GOES DOWN, and the asymmetry is the design.** Loudness had two
channels already -- `sound_source` on an entity standing in the room, and
`rooms[rid].sound`, the standing noise a plan writes so an unfurnished room
can announce itself -- both of which TRAVEL and both of which already mask a
listener beside them, because `noise_at` counts every other source as noise.
A third word meaning "loud" would have restated a fact the scene already
holds and been free to disagree with it. Silence had no channel at all,
because an absence has no source to hang on, and that is exactly and only
what the word is for.

**Building it surfaced a second constant doing the first one's work.**
`HEAR_FLOOR` -- "a signal quieter than this is not heard however quiet the
room" -- was, by its own comment, "set with AMBIENT", and landed on 0.05,
which is `AMBIENT["enclosed"]` exactly. So in every ordinary indoor room the
absolute gate and the SNR gate sit within a decibel of each other and the
absolute one is higher, which is harmless while nothing can be quieter than
an ordinary room. `quiet` made something quieter, and the field would have
shipped INERT: a room could declare itself a tomb and hear precisely what a
furnished parlour hears, with no error anywhere. The floor is now taken
against the room's own noise (`min(HEAR_FLOOR, noise)`, in the linear grader,
the dB grader, the far-field word and the flood's cutoff, which is what keeps
the four agreeing) -- you cannot hear below the room you are standing in, and
the calibration was of an ORDINARY quiet room. A room that declares no quiet
has a floor at or above `HEAR_FLOOR` and takes `HEAR_FLOOR`, byte for byte as
before.

The measurement above is exact and reproducible on the descent copy at turn
13; with the duct rule in, the annex reads 28.4 dB against 27.0 and hears a
`fragment` where it heard nothing.

**What is NOT in question:** the geometry. Every room that should be on the
field is on it, the neighbour is placed, the aperture is charged, the three
events are sources, and the co-located ones no longer silence each other. The
model is now answering the question it was asked; this entry is about whether
the answer is right.

<a id="unbuilt-1-146"></a>

### 1.146 Two people three rooms apart cannot call to each other, and three models disagree about it — FIXED 2026-09-06

**Measured, chat 117 turns 47-49, and it read as a character flaw.** Aurel
told Sarah to follow him up; she did not, and went on not answering while he
walked two rooms ahead and then shouted her name. Her perception view over
three beats contains no trace of either line. She was not being stubborn: she
was never told. A companion who stops obeying is what an engine failure looks
like from the page.

**Three of the engine's own models answer the same question differently**,
for a `shout` from `upper_service_core_riser_10` to `_7`, three hops down a
straight run of open doorways, 26 paces:

  * `hear_level(rel, "shout")`, the relation reader: **fragment**
  * `sound_walk_level(...)`, the bounded walk: **none**
  * `room_sound_flood` + `distant_level_word`: **31.6 dB against a 27.0
    floor -> plain**

and the composer takes `hear_level`, which for the `loud` the Director
actually graded the line answers **none**. The flood says `loud` arrives at
26.8 dB, a `faint`. So the beat that reached the reader was the deafest of
four available answers.

**The cause is that two pre-decibel constructs survived the migration.**
`hear_level`'s `separated` arm is a WORD where the rest of the module now has
arithmetic, and `sound_walk_level` carries `max_hops: int = 2` with a
docstring that says why -- "so 'the castle hears every shout' stays impossible
by construction". The decibel model makes it impossible by CONSTRUCTION of a
different kind, and the flood's own docstring already says so: it terminates
on AUDIBILITY, "the physically meaningful bound and the one that makes the
reach of a sound a property of how loud it is rather than of a constant".

**The flood is not runaway, measured on synthetic chains of nine rooms**
(shout / loud, by first room that stops being audible):

  | edge | small | medium | large |
  |---|---|---|---|
  | open | 8 / 6 | 7 / 3 | 5 / 2 |
  | open_door | 7 / 4 | 5 / 3 | 3 / 2 |
  | closed_door | 2 / 1 | 1 / 1 | 1 / 0 |

One closed door ends a shout in two rooms. The castle does not hear it.

**THE OWNER RULED FOR DECIBELS, 2026-09-06: "decibel is probably the best
signal". FIXED, and the fix removes a model rather than adding one.**

**It does NOT go in `sound_walk_level`, which the composer never calls.** The
composer reads `hear_level` off a RELATION and deliberately never touches the
scene ("this module decides admission on typed data alone, and a rendering
path that could consult the world could add to it"). So the flood's answer is
stamped upstream, in `stamp_sound_relation`, and every reader below it --
masking, the `door_gain` ceiling, `_weaker_hearing` -- goes on working
unchanged.

`far_path_gain(scene, listener_room, source_room)` is the new reader. Three
properties make it drop in:

  * **Loss is independent of the source level** -- spreading and barriers are
    both subtractive in dB -- so ONE probe grades every volume and
    `hear_level` stays the only thing that knows what a shout is. The probe
    is a shout because the flood terminates on audibility: past where a shout
    dies, nothing anyone says is audible anyway.
  * **It only ever SUBTRACTS at the seam.** At one hop, where both readings
    exist, the composite field measured 0.0191 and the flood 0.0062: the
    flood charges whole room spans where the field walks cells, so the model
    taking over is the more conservative one.
  * **`0.0` is an answer** -- the rooms exist and no speech-scale sound gets
    between them -- and it is the sentence `door_gain` had no way to say.

**Scoped to NON-ADJACENT pairs.** Two rooms sharing an edge already have a
barrier to be graded by, tuned per barrier, and there is no distance to be
wrong about across one edge; a wall between neighbours is something the edge
rules say a deliberate thing about, and the flood would overrule it with a
coarser reading for no gain. `separated` -- one word for every distance
beyond the next room -- is the only case that changes.

**Two things it turned up, both worth the entry on their own.**

  * **A gain is a RATIO and must not go through `power_of_db`,** which
    carries `DB_REF = 40.0`. The two look interchangeable and differ by a
    factor of ten thousand. The first cut returned 6.2e-07 where the field
    read 0.0191 for the same pair -- a room that hears nothing, ever, and
    reports nothing -- and it was caught only by checking the one-hop answer
    against the composite field's own. `ratio_of_db` is now the declared
    other half of `db_ratio`.
  * **The vouched exemption held by ACCIDENT.** `_hear_level`'s field branch
    carried a comment saying "`vouched` is never reached with a field
    present ... two bodies on one placed field always have one", which was
    true only while a stamp meant one composite grid. Stamping any pair the
    room graph joins broke it, and a voice on a comm channel started being
    graded by the doorways between its two ends -- a deafening bell beside
    the listener silenced a radio. The guard is explicit now.

**WHAT IS NOT DONE, and it is where `max_hops` lives: THE HEARING-ACUITY
ENVELOPE.** `sense_range_class` grades a card's `range` as reduced | ordinary
| extended and the consumer widens `max_hops` for `extended` -- so sharp
hearing is currently spelled as EXTRA HOPS. Replacing hops with decibels
means acuity has to be spelled as a dB bonus instead, which is a design
decision about what a sense card means, not a defect. `sound_bearing`'s
non-adjacent arm is bound the same way (`sound_path(max_hops=2)`) and would
have to move with it, or a listener hears a shout from nowhere; the flood
already returns the `via` room that answers it.

**THE CAPS, NAMED, because they are exactly the kind the owner asks to see.**
Both survivors are still in the tree and both now answer for less than they
did: `sound_walk_level`'s `max_hops = 2` and its `fragment` ceiling beyond
the first hop still bound the ALARM SNAP (`spatial_frames.infer_focus`'s
`sound_walk_level` call), which is the one production caller and is about
where a body turns rather than what it hears. `FAR_FIELD_ENTRY_DB = 70` still
sits above every human voice (`SPEECH_DB["shout"]` is 60.8), so speech never
enters the far-field EVENT channel -- it now reaches a distant listener
through the relation instead, which is where speech belonged.

**One consequence to watch, stated rather than hedged:** a shout down a
straight run of open doorways now grades `full` at three rooms, where the old
model capped every distant raised voice at `fragment`. That is a real change
to what characters overhear. It applies to RAISED volumes only -- an ordinary
voice still does not cross a room -- and the arithmetic that permits it is
the same arithmetic that has a closed door end a shout in two rooms.

<a id="unbuilt-1-147"></a>

### 1.147 The cone hid the way on, because a guess was allowed to subtract — FIXED 2026-09-06

**The owner's read, 2026-09-06: "player perception culling might be too
aggressive". Measured, and it was — but not by being too narrow.**

Chat 117 turn 56. Aurel walks north up a 4x24 concrete corridor with a lamp.
The room holds five features and his view receives TWO:

  | feature | declared `dir` | placed cell | verdict |
  |---|---|---|---|
  | `concrete_deck` | n | (2, 0) | visible |
  | `cable_trays` | n | (1, 1) | visible |
  | `door:..._11` | **none** | (1, 16) | **culled, basis `cone`** |
  | `southern_threshold` | s | (2, 23) | culled, basis `cone` |
  | `door:..._9` | s | (1, 23) | culled, basis `cone` |

He stands at (2, 1) facing north. The two culled doorways with a declared
`s` are genuinely behind him and correctly hidden. The third is
**`..._11` -- the room he is walking toward** -- and it was placed fifteen
cells behind him.

**Why it was placed there.** Sight is denied derived bearings on purpose
(`derive=False`, so no view asserts a wall nobody declared, § 1.145's
boundary). That leaves an unbeared doorway's pseudo-anchor placed by the
hash that seeds any anchor along a wall -- fine as somewhere to lay a thing
out, worthless as evidence about where a body is looking. The cone was
reading it as evidence. `derived_edge_bearings` had the right answer the
whole time (`(_10, _11) -> n`) and sight is not allowed to ask for it.

**So the culling was not too aggressive; it was aggressive on INVENTED
GROUNDS.** That is the complement of CLAUDE.md's rule about the exposed
body -- "no guard was missing, a fact was" -- read from the other end: a
guard must not fire on a fact the engine made up. The subtraction was
right-shaped and its input was fiction.

**Fixed narrowly.** The cone may not hide a doorway whose bearing nobody
declared, on either side of the edge (`_unbeared_doorways`). The precedent
is in the same function: the light gate already carves doorways out, "a
DOORWAY, which is a gap in the wall rather than a thing in the room". Such
a row is NAMED and claims no `side`, no `sector` and no `peripheral`,
because "on your left" computed from a hash is exactly the false assertion
being avoided -- the same shape `_render_openings` already takes for the far
side of a threshold, where "the things are named and the distance is simply
not claimed".

**What it does NOT change:** a doorway anyone placed is ordinary geometry
and is hidden behind a body like anything else. Both declared doorways in
the beat above stay culled.

**Story consequence, which is how it was found at all:** the view had been
reporting the deck running on "into unbroken black" for several beats while
a door stood at the end of it, so the reader and the player were both being
told there was nothing ahead. See [[fiction-breaking-is-the-signal]]: the
prose was the only place this was visible.

<a id="unbuilt-1-149"></a>

### 1.149 A lamp cannot be aimed at the thing worth aiming it at

**Found by reading six beats as a READER, 2026-09-06, and that is the
whole of why it was found.** As an engineer it had already been checked:
`visual_level_between` answered `none`, which reads as "the beam moved off
it, correct behaviour, move on" -- and that is what was concluded, out
loud, twice. As a reader the question could not be waved away: the player
wrote *"I look at it properly for the first time -- the whole shape of the
thing, top to bottom, and whatever it has instead of a face"*, and the
prose described his own boot.

**FOUR FAULTS ON THE PAGE, ONE VALUE UNDERNEATH** (chat 117, turns 59-62):

    "pointed_at": "north along upper_service_core_riser_10"

The player held a light on a creature for three consecutive beats. The
creature stood at the SOUTH doorway. The beam went north.

  * The declared look was answered with nothing -- unlit, so no sight, so
    it never entered the player's company, so there was nothing to render.
  * It stood at the WRONG DOOR for four beats: the composer gave
    `side: None`, the narrator supplied "on my right", and then read its
    own guess back out of `past_narration` and repeated it until it was
    the story's settled account. Sarah squeezed past that doorway in turn
    61, within arm's reach of a predator, unremarked by anyone.
  * The beam was "locked unwavering on the corridor behind" in one beat
    and "locked straight forward" in the next, same target.
  * Nothing escalated, because an unseen monster cannot menace anybody.

**TWO OF THE THREE FIXES SHIPPED** (both packs, and both independent of
the third): the objects chunk had been telling the Director *"a carried
cone points where its holder faces"* -- so it never tried to aim one and
wrote a direction PHRASE, which resolves to nothing -- while
`light_sources` has always PREFERRED `pointed_at` over facing. The prompt
was contradicting the code. And the narrator's direction licence, which
forbade inventing a side for a ROOM, now forbids it for a BODY, with the
reason that makes it matter: an invented side does not stay in one
sentence.

**THE THIRD IS UNBUILT, and an inert fix for it was written and BACKED
OUT the same hour.** `_resolve_pointed_at` resolves a bearing, a scene
entity, or an anchor of the source's own room. A charter body is none of
those: it holds no `positions` row under its own name -- it is laid onto
the PERCEIVING stage's copy of the scene, and the light field runs on
another -- so `room_of` and `body_cell` both answer None and the aim falls
silently through to the holder's facing.

The attempt read the body's cell through `charter_place.charter_placements`,
which needs a chat id, which it took from `scene["_chat_id"]`. **No scene
carries that key.** It returned None on every real call and passed its own
test only because the test injected the id by hand -- the exact class this
register is full of, written by the person writing the register. What it
actually needs is a chat id plumbed into the light field, or the charter
bodies laid into the scene the field runs on, and neither is a five-minute
change.

**A NOTE ON THE EVIDENCE, because it nearly went in the commit message.**
The replayed turn 62 DID put the beam on the creature and describe it --
and not because of any of this. `pointed_at` was still the same
unresolvable phrase; what changed was that Aurel's facing became `e`, so
the cone followed his body onto the thing by luck. A beat that improves is
not a fix that worked.

<a id="unbuilt-1-151"></a>

### 1.151 Being TOLD does not ask for ears, and a closed intake leaves the old claims standing

Two residuals of the deafness gate (`charter_observe.body_receives_evidence`,
2026-09-06), both measured, neither built.

**THE ONLY UPTAKE DOOR DOES NOT ASK.** `charter_mind.hear_claim` says of
itself: "THE ONLY UPTAKE DOOR. `hear` routes through it for body-to-body
talk; an authored telling -- a voiced presence, the player, a major
character speaking to a background body -- lands through the same door with
the same rules." It is thinned by retention, scaled by regard, refused
below the floor -- and it never asks whether the listener can HEAR. So a
body authored deaf can be TOLD what someone said, by ordinary conversation
(`charter_talk.converse`) or across institutions
(`charter_runtime.cross_charter_gossip`), and the intake gate does not
cover it: that gate refuses direct observation, and this is hearsay.

Being told is speech. A body with no ears receives none of it.

**MEASURED BEFORE PROPOSING, and it is why this is registered rather than
fixed:** across the author's whole corpus there are **0 creature charters**
-- the descent story (chat 117) is the first to exercise the creature path
at all -- and **0 creatures with any body positioned to tell them
anything**. A creature charter here holds one body, so `converse` has
nobody to pair it with, and cross-charter gossip needs two institutions
standing in one room. The hole is structurally real and currently
unreachable, which is exactly the state that earns a line here instead of
code.

When it is built, the door is the place: one gate in `hear_claim` covers
every telling path by that function's own contract, and a second uptake
path with its own arithmetic "is how the two authors would drift apart".

**AND A CLOSED INTAKE DOES NOT CLEAN THE PAST.** The gate stops new speech
claims; the ones already written stay. Live, chat 117 after the fix, the
carbonic stalker's own mind holds:

  | kind | count |
  |---|---|
  | `figure` (sightings) | 2 |
  | `news/figure_action` (things it SAW) | 11 |
  | `news/figure_speech` | **15** |

The first two are legitimate -- it is deaf, not blind. The fifteen are
words it should never have had, and `presence_view` will go on offering
them under `can_bring_up` as things it might raise in conversation. A
read-side refusal would cover both this and the hearsay hole above, at the
cost of leaving wrong data in the ledger rather than removing it; a
migration would fix the data and not the doors. Whichever is chosen, the
existing rows are not fixed by the intake gate and should not be assumed
to be.

<a id="unbuilt-1-158"></a>

### 1.158 A sense can be masked by nothing, so the gas the plan was for was modelled as a noise

**s1.152's sibling, found at the other end of the same story.** That entry
says a creature can be stopped by the shape of an opening and by nothing
else. This one says its SENSES can be interfered with by nothing at all.

Chat 117 turns 96-100, the run's climax. Told by Sarah that the thing hunts
by chemoreception rather than hearing, the player -- a maintenance engineer
-- reasoned that a shelter of that era keeps charged CO2 flood systems in
every plant space, found a bottle bank, aligned the manifold selector down
the riser they had come from, paid the trip cable out to the threshold and
pulled it. The intent was exact: put a room full of the substance the
predator tracks BETWEEN it and them.

**The Director recorded it faithfully, in its own channel.**
`state_diff.entities.co2_suppression_bottle_bank`:

    "state": {"discharging": true, "venting": "down_riser_feed_line",
              "selector_alignment": "down_riser", "manual_release": "tripped",
              ...},
    "sound_source": "deafening"

**And `state_diff.substance_ops` was empty.** No CO2 was placed in any room.
`scent_at` for the two rooms afterwards returns `{'breath': 0.83}` and
`{'breath': 0.55}` -- their own trail, and nothing else. The gas does not
exist in the world; only a loud object does.

So a discharge staged specifically against a chemosensory hunter was modelled
as SOUND, for a creature whose card says `hearing: false`. The prose calls it
"a wall of pure pressure"; the simulation has a noisy cylinder.

**The engine owns every piece this needed.** `substance_ops` places a
substance in a room, `scent_at`/`scent_word`/`SCENT_STRENGTH` grade what is
smellable there, and `SCENT_PASS` already grades what a barrier does to a
smell crossing it. What is missing is the idea that a strong enough substance
DROWNS another rather than sitting beside it -- masking, as against presence.
Nothing anywhere reduces one scent because another is overwhelming.

**Why the story still worked, and why that is the wrong reason to leave it:**
the creature did lose them. Its `smelled` map went from `{riser_12: 1.0}` to
`{}` and it fell back to cast around riser_10 -- correct predator behaviour,
emerging from the model. But the cause was ordinary decay and distance after
five beats of deliberately slow, shallow-breathing movement, NOT the gas. Had
it still held the line, the discharge would have done nothing to it, and the
plan the whole last act was built on would have failed silently while reading
as a success.

**Where it belongs:** with the scent field, not the creature. A substance that
masks is a fact about the air in a room, and every hunter that reads that room
should be affected by it identically -- exactly as `SCENT_PASS` is a fact
about a barrier and not about who is sniffing at it.

<a id="unbuilt-1-159"></a>

### 1.159 The sound model is half real: the ladders are decibels and the losses are still compressed

**Built 2026-09-14** (`DESIGN_SOUND_DECIBELS.md` § 5c,
`DESIGN_SOUND_FIELD.md` § 6c, `tests/test_sound_calibration.py`): the
emission ladders are authored as real sound pressure levels at one pace
(`SPEECH_ONE_PACE_DB` mutter 38 | whisper 35 | normal 60 | loud 70 | shout
82; `SOUND_ONE_PACE_DB` faint 40 | audible 50 | loud 80 | deafening 100 |
thunderous 120 | catastrophic 140) and the fragment margin is a real
speech-reception number (`FRAGMENT_SNR` 1/16, -12 dB). The play scenes that
forced it -- a hearth fire masking a line spoken at the hearth, a launch
engine refusing a raised line one pace off -- now grade as a reader would.

**Moved later the same day (2026-09-14):** `APERTURE_PASS` is now derived
from real transmission losses (`APERTURE_DB`: open doorway 2, grille 2,
curtain 5, shut door 25, glass 28), `WALL_LOSS_DB` 45 and
`FLOOR_CEILING_LOSS_DB` 50 -- forced by
`tests/test_replay_defects_h.py`'s shut-door test failing the moment the
ladders went real. Measured after: a normal voice at a shut door is a
fragment beyond it and nothing at the far wall; one shut door passes a
shout, two end it; a normal voice down an open run is whole at two rooms,
pieces at three; no voice's level clears a masonry wall; the far-field
reach on a 300-room chain is 10 / 18 / 26 / 35 for loud / deafening /
thunderous / catastrophic. The two expected failures are ordinary tests now.

**Still on the compressed scale, and the remaining decision:** `AMBIENT`
27.0 / 30.0 / 30.0 (a furnished room is 35-40 dB(A), which is why a normal
voice is `full` across any room and a mutter carries three paces);
`WEATHER_NOISE` and `WIND_NOISE` (heavy rain 37, a gale 40, against real
55-70); and the impact ladder (`EVENT_POWER`), which now sits below the
emission ladder at `loud` and `deafening` -- nothing compares the two, so
no verdict turns on it. Each is one number with a known direction: rooms
mask more, weather masks at all, a whisper's reach shortens by a pace.

**A composer symptom the fragment exposed, not fixed:** a delivered fragment
that quotes the perceiver's own name ("...here's... Hinami... kitsune...")
trips the `COMPOSER TRIPWIRE -- composed view narrated its own perceiver`
warning, because the fragment renderer does not mark its pieces as quoted
speech the way a whole line is. Seen on chat 122's beach beat once the far
line became a fragment; a false alarm, and the warning is only a warning.

## 2. Roadmap

<a id="unbuilt-2-11"></a>

### 2.11 Weather rendering is rain, snow and lightning only

`static/js/weather-fx.js` draws falling precipitation and storm flashes for
rooms whose `weather_for_room(...)["weather_visible"]` is true, scaled by
`visible_reach`, and thunder follows each flash on a distance-shaped delay.
Not built:

- **the picture disagrees with the overlay under cover.** `weather_visible`
  was split from `sky_visible` so a porch draws the rain it is sheltering
  from, but `weather_words(..., "sight")` — which writes the backdrop image
  prompt — is still gated on `sky_visible` and `falls_on_you`. So a sheltered
  lane gets rain drawn over a picture generated as though it were dry. Fixing
  it means teaching the sight channel a third phrase ("rain beyond the
  eaves"), which moves `visual_signature` and re-generates every sheltered
  room's image — a cost worth choosing deliberately rather than in passing.

- **fog and wind have no visual.** Fog is the obvious next one and is a screen
  tint rather than falling weather, so it wants its own layer rather than a
  tile.
- **the fall is periodic.** Three tiled layers translating at different speeds
  is what a particle engine's randomness was traded for, and it is the reason
  the overlay costs almost nothing — but it is a loop, where particles never
  repeated. Watching one layer alone would show it; watching all three
  together, so far, does not.
- **snow does not settle** and rain does not streak a window. Both want a
  second, slower buffer that the current single-pass loop has no place for.

<a id="unbuilt-2-12"></a>

### 2.12 Ambience layering is capped at three, and has no sends

`dressing/ambience.py` mixes up to three simultaneous beds (`tone` / `weather` /
`extra`), each with its own gain, rerollable and pinnable per layer. What is
still absent:

- **no reverb or filtering.** A muffled room gets a different *recording*
  rather than the same one behind a low-pass, because the player is plain
  `<audio>` elements. Real filtering means an `AudioContext`, which needs its
  own unlock gesture — see the note in `ambience.js` on why Web Audio was not
  used for the crossfade either.
- **layers do not duck.** Nothing lowers the room tone when a louder element
  arrives; the gains are static per layer.
- **no per-layer loop offsets**, so two beds fetched at the same length can
  phase against each other audibly on long stays.
- **the loop overlap hides a seam, it cannot fix a clip.** `armSeamlessLoop`
  crossfades a bed into itself, which removes the hole at the file boundary but
  not a recording whose end does not belong beside its beginning — a passing
  car at 0:58 still arrives every 0:58. Freesound exposes no loopability
  descriptor (`ac_loop` is undefined on its search server), so `_LOOP_WORDS`
  guesses from tags; nothing measures the actual seam.

<a id="unbuilt-2-13"></a>

### 2.13 Matching a recording to a room is keyword overlap, not hearing

Freesound ANDs the terms of a query, so the seven- and eight-word acoustic
descriptions this module composes match *nothing at all*; `_query_ladder`
broadens until something comes back, and `_rank_candidates` then judges what
came back against the room's own words rather than the crowd's rating. That is
what a bath scene needs to stop being given falling roof tiles. What it still
cannot do:

- **it compares words, not sounds.** `fit` is set-overlap between a query and a
  recording's name and tags, with plurals folded and a penalty list of event
  words. A perfectly-tagged recording of the wrong place still scores; an
  untagged recording of exactly the right one scores nothing. Embeddings over
  the tag vocabulary would be the honest fix.
- **a room named in fiction has no acoustic vocabulary at all.** When the model
  writes proper nouns through into the query, the ladder strips them to
  something generic and the fallback to the room's own words hits the same
  wall — `Design.md`'s "describe the sound, never the fiction" rule is enforced
  only by the prompt.
- **`fit` is computed but never shown.** The picker lists candidates in ranked
  order without saying why, and a host who disagrees has no handle on it.

---

<a id="unbuilt-2-34"></a>

### 2.34 The light field — PROTOTYPE, what is left

Built 2026-09-04 on `writers-room` (not yet on `main`) from
[`design/DESIGN_LIGHT_FIELD.md`](design/DESIGN_LIGHT_FIELD.md) §§ 3-8 as
`world/spatial_light_field.py` (behind the `world/spatial.py` facade;
`tests/test_light_field.py`, 36 tests; measurements in the note's § 9).
Light is a scalar on the composite sight grid: per-source shadowcast from
the source's cell, blocked by occluders at or above the source's height
rank and by the wall line outside its doorway, inverse-square decay, a cone
with a linear penumbra, summed, bounced by the room's `exposure`, floored
by `room_light`, quantised LAST; `light_at` and `effective_light` (median
cell) read it where a room has a size tier or anchors and a body a cell
(the glare cap `sight_level` also read was removed 2026-09-16, owner
ruling: a light on a thing shows it; `DESIGN_LIGHT_FIELD.md` § 4b), and
answer exactly as before everywhere else
(pinned byte-for-byte on seven no-geometry scenes). `flickering` and
`failing` are a hash of (beat, source); the commit stamps `scene.beat_idx`,
records a failed source `state.lit: false` and files an `engine_notices`
line.

**The merge with the sound field (2026-09-04), recorded ONCE for both
fields** (the sound field's own residuals are § 2.36): ONE grid derivation
for every sense (`spatial_fov.room_field` under a placement predicate --
`light_passes`, `sound_passes`; the sound field's private `_acoustic_grid`,
which had drifted to squares, is gone; `tests/test_one_grid_two_senses.py`);
ONE steadiness vocabulary, hash and pair of rates (`STEADINESS`,
`FLICKER_RATE`, `FAIL_RATE`, defined in the light field and imported by the
sound field); ONE commit block switching a `failing` source off in every
sense it has (`state.lit`, `state.running`) and filing one notice per thing
(`persist/commit_scene_state._record_failed_sources`); the composer says
WHERE the light falls and WHERE the sound is (`light_shape` ->
`composer.render_light_shape`, `sound_shape` -> `composer.render_sound_shape`,
en and ja, under the owner's five rules; `tests/test_field_sentences.py`);
the ambient floor SPILLS through apertures (`FLOOR_SPILL` 0.25); a body with
no station reads the room's median; glare counted an all-round lantern
(the rule is gone since 2026-09-16); a listener whose station lands on an
occluder's cell hears. The corpus was
re-measured in the light note's § 9.6 and the sound note's § 9a. Left:

  * **Two of the owner's three open questions**: median or mean for a
    room's reading (§ 4b; median as built, and chat 115's dim corridor
    with one lit source reads dim, not lit); and the constants (§ 6). One
    already moved: LIT_T 2.0 -> 2.5, because 2.0 sat exactly on POWER[dim]
    and every dim room with a grid read lit. The § 9.3 table shows a `lit`
    source reaching one cell as lit and three as dim against the note's
    "about two ... about four"; LIT_T <= 1.2 or POWER[lit] >= 12 would
    meet the sentence. `FLOOR_SPILL` (0.25) is a fourth constant the owner
    may move; its table is beside it.
  * **The shape sentence replaces the flat one** when a room is uneven
    (§ 4b). The room's median word is then not said; the observer's own
    standing is. Whether the median should ALSO be said is a wording
    choice the owner has not seen on a live page.
  * **`light_radius` is superseded where geometry exists** (§ 3). Three
    assertions in `tests/test_light_and_survival.py` changed to say so; a
    `lit` fixture no longer fills a large hall and a `bright` one does.
  * **§ 9.5 live beats** were not played. Two beats with a held cone in a
    fresh non-explicit scenario, every stage read, is the next measurement
    under the standing grant -- and the first live reading of the shape
    sentence, which the corpus hands to one body in 104 scenes.
  * **Cost was not measured** at the geometry note's precision. The field
    is cached per (scene inputs, room) in a 64-entry memo keyed on a JSON
    dump of what it reads; the dump is taken on every reader call. The
    shape adds one `feature_visibility` and, per source, one `_visible_set`
    per observer per stage.
  * **The backdrop brief's `lighting` slot** (`dressing/backdrops.room_brief`,
    reserved for the light field's sentence) is still empty; `light_shape`
    is the input it was reserved for, and nothing hands it over yet.
  * **The Japanese adapter renders neither the furniture sentence nor the
    openings** (`language_adapters/japanese.py::_environment` reads
    `room_name`, `room_notes`, `light` and now `light_shape`; the pack's
    `features`, `feature_item`, `feature_glimpse` and `opening_*` templates
    are authored and never called). Found while wiring the shape sentence;
    the adapter's own docstring names this failure class. Not fixed here
    -- the tier and side phrases it needs are language data with their own
    reading rules -- and registered.

<a id="unbuilt-2-36"></a>

### 2.36 The sound field — PROTOTYPE, what is left

Designed and built 2026-09-04 on `writers-room` (not yet on `main`;
[`design/DESIGN_SOUND_FIELD.md`](design/DESIGN_SOUND_FIELD.md),
`world/spatial_sound_field.py`, `tests/test_sound_field.py`, 25 tests).
Loudness is a scalar on the sight grid, spread by shortest acoustic PATH,
attenuated per aperture by barrier and material, decayed by path length,
summed into a signal and a noise floor, and quantised LAST to `none |
fragment | full`; `spatial_rel_between` stamps `signal`/`noise` where the
listener's room carries geometry and `hear_level` reads them; entities carry
`sound_source`, `steadiness`, `state.running`; a failing source files an
engine notice; a scene without geometry composes byte-identically (pinned).
Measured: 2 of 589 live rooms carry geometry, 2 speaker-listener pairs on a
field, whisper and mutter the only words that moved. Merged with the light
field 2026-09-04; the shared record -- one grid, one steadiness, one
failed-source block, the two shape sentences, the occluder-cell listener --
is written once, in § 2.34. The sound side's own detail: the noise ladder
`quiet | din | drowned` (`NOISE_WORDS`) is derived from `FULL_SNR` /
`FRAGMENT_SNR` against a normal voice one pace off, never a fourth constant.
Left, each in the note's § 10 and each an owner decision: the constants
(§ 6a set them off the § 6 proposal, with the reason); whether a crowd's
`mood` should raise its level (built on its band, a closed set); which lines
of a beat are simultaneous (the reader grades one line at a time;
simultaneous masking exists only through the module API); whether a
fragment should thin with the ratio; **`sensory_events` on no schema after
establish** (§ 10.9 -- a crash two rooms away on a normal beat has no
channel to arrive by; a Director schema addition, and which hand owns a
one-beat sound is the owner's to say); **two gates** (§ 10.10 -- hearing
exists in the 2 rooms with an authored footprint/height/opacity, light in
the 321 with a size tier or anchors; whether hearing should take the wider
gate); and the live run, which needs a copy of the owner's database there
was no room for (the 2026-09-04 corpus pass streamed read-only instead, and
found no live room uneven for sound).

## 3. Information-pipeline leaks still open

<a id="unbuilt-3-2"></a>

### 3.2 Concealment gates not applied everywhere

- **X3 — `conceal_from` without `visibility: "concealed"` bypasses the
  background declaration filter**, which consults `visibility` only. Every other
  guard in `agents/background.py` fail-closes on `conceal_from` independently,
  precisely because models half-comply. *Latent, no test.*
- **X7 — half closed.** The player-input half is fixed: `pick_background_reactors`
  now qualifies a presence from `overt_declaration_text(ctx)` rather than
  `ctx.input`, with the reason at the call site (*"a whispered name used to
  qualify its own presence"*). What survives is the other reader in the same
  function — `resolved_event` is counted as a raw string with no concealment
  gate, so a concealed act the Director wrote into the beat's event text still
  raises a presence's pick priority (`persist/commit_background.py`).
- **X19 — `_llm_resolve_player_room` receives the private thought**, for a call
  whose only output is a position key.

*(Three bullets were struck 2026-08-19. **A8 residual** is deliberate, not open:
the channel is closed — `_p_disguise` is discarded at the `_composer_act` call —
and what remains is a tripwire whose own docstring says *"A WARNING, never a
scrubber."* **B4** (`_ensure_environment` does not check darkness) and **C3**
(stray view keys survive `_normalise_views`) both describe helpers with no
production caller; see §1.45's dead family.)*

<a id="unbuilt-3-3"></a>

### 3.3 Sense and awareness gaps

- **F4 residual — action delivery in the micro-loop is boolean visual rather
  than graded.** The sense-profile half landed: `agents/loops.py` reads
  `character_senses(observer_sheet)` and threads it into `_delivery_ok` and
  `sense_adjusted`. Speech is graded there; an action is still a yes/no gate
  followed by a whole sentence, so a half-seen act arrives entire or not at
  all, where a half-heard line arrives as a fragment.
- **Perception prose is not bound by the audibility layer.** Live data shows a
  view narrating "difficult to parse from this distance" while the deterministic
  layer had already ruled the speech fully audible. The deterministic layer is
  right; the prose should be CONSTRAINED by it rather than free to contradict
  it — same family as F4, and the same answer (the delivery verdict decides the
  sentence, not the other way round). *(Promoted out of §8 on 2026-08-19: it
  cites live data showing prose contradicting the deterministic verdict, which
  makes it a defect rather than an idea.)*
- **F6 / S3-A5 residual — `spatial.spatial_digest` still renders the authored
  room name behind every edge, including rooms never visited.** The perception
  payload was fixed (unseen edges keep their barrier, lose `to`/`to_name`);
  the digest that reaches the **narrator** was not, and the same digest is
  what every character navigates by (`agents/character.py`,
  `spatial_prose._annotate_known_exits`, which maps the rendered NAME back to
  a room id) — so matching perception's shape here is a change to that
  contract, not a one-line gate.
  **The directional half landed 2026-08-20**: an edge that is a wall only from
  THIS side is no longer rendered at all, so the blind side of a
  `one_way_window` stops naming the room behind it and the barrier keyword
  that says how it works (chat 78 t3 — see §1.68). Scoped to edges the
  observer-side resolution makes more restrictive than the record, because an
  adjacency declaring no barrier normalizes to `wall` for everyone and
  dropping those would take real exits out of every navigation payload.
- **F7 — `known_pronouns` releases pronouns on unverified mind-model keys.**
  `agents/character.py` keys off `set(relationships) | set(mind_models)`, which
  is the unvalidated set.

<a id="unbuilt-3-8"></a>

### 3.8 A structural risk, not a finding

`agents/perception.py` does **not** call `common._delivery_ok`; it uses
`hear_level` and `_in_plain_view` directly, while `agents/loops.py` routes
everything through `_delivery_ok`. Two families of delivery gate now exist and
can drift apart. Consolidating them is the cheap insurance.

## 4. Architecture gaps

<a id="unbuilt-4-2"></a>

### 4.2 Gap 4 residual / Priority 1 — evidence-carrying perception

**The headline item, now half of it.** Mind models carry confidence and
evidence, and confidence can still blend smoothly while resting on duplicated,
circular or mutually dependent evidence.

The reference half landed: `MindHypothesis.evidence` is
`list[EvidenceRef]` rather than free text, and `agents.character.ground_refs`
holds `mind_model_updates`, `belief_updates` and `association_updates` to ids
actually delivered to this mind — an update whose evidence does not resolve is
DROPPED, not warned about, and derived summary prose is refused
(`allow_summaries=False`) so a summary cannot launder itself into a durable
belief.

What is still missing is the DISCRIMINATOR. `EvidenceRef` carries `event_id`
and `fact` and nothing that says whether the evidence was witnessed, reported,
inferred, or copied from another belief — so two references can resolve
perfectly and still be the same claim arriving twice. Without that, revision
cannot discount a circular report or preserve competing hypotheses, and no
`signal_id` exists anywhere in the tree.

The same primitive is what §3.1 needs to stop matching on prose, and what
`current:<perceiver>:<n>` already mints for the present beat. **Two of this
file's largest items are one missing structure.** The adversarial-test half of
this priority has shipped.

## 6. Design-note residuals

<a id="unbuilt-6-12"></a>

### 6.12 Scent — [`DESIGN_SCENT.md`](design/DESIGN_SCENT.md)

v1 is built; the five things deliberately not built — decay, travel and drift,
multi-hop reach, an entity's smell never attributed, and whether a body receives
its OWN card scent — are all in that note (§5, §6, and §7's closing paragraph),
each with the argument for leaving it out. *(Restated here until 2026-08-19.)*
