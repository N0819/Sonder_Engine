# Changelog

## Unreleased

### Added
- **A way through that is not a way to look through.** The barrier vocabulary
  could say "you can see it but you cannot reach it" — that is what `window`
  and `bars` are for — and had no way at all to say the reverse. Every passable
  barrier was also transparent: `open` and `open_door` were the only two ways
  to author a doorway a body could use, and both hand everyone on the far side
  a clear line of sight through it. A curtained doorway, a bead screen, a tent
  flap, a gasketed hatch — anything pushed through rather than swung open —
  had to be lied about as an open door, or degrade to `wall`, which nothing
  passes at all.

  That gap bit hardest on entity interiors, whose exterior doorway is *derived*
  rather than authored. An interior standing open always derived `open_door`,
  so **stepping inside an enclosure made a body more exposed than standing in
  the open** — the room outside got full sight of them the moment they went in.
  Perception was working correctly on top of a scene graph that said the wall
  was a window: it asked `has_visual`, got true, and pasted the occupant's
  appearance into every outside observer's view.

  `membrane` is the missing rung: passable, never see-through, sound muffled
  rather than stopped — a raised voice crosses it, an ordinary one arrives as a
  fragment. `enclosure` now describes what an interior lets through in *both*
  states rather than only when shut, and `membrane` is the one value whose open
  doorway is still opaque. A lid or a hatch is unchanged: standing open, it
  genuinely is see-through, so vehicles, cabins and chests derive exactly as
  before. Closing the sight channel closes the light channel with it — the
  spill rule that lifts a dark room to `dim` only reaches through a *sight*
  barrier, so an unlit interior behind a membrane stays dark instead of being
  lit by the room outside and putting its occupant back on view.

- **Crossing a threshold takes longer than a position field does.** A body's
  room is one value that changes between one beat and the next. Where the
  boundary is see-through that costs nothing — the room behind watches through
  the opening either way. Where it is opaque, the body *blinked out of the
  world*: the beat it stepped through, every observer behind it lost it
  completely, mid-step, with nothing narrated as having happened.

  A body that has just crossed an opaque boundary is now recorded as still
  crossing, and stays visible **as a shape** to the room it left for a beat or
  two before it is gone. Seen going in; not seen once in. It is a floor and
  never a bonus: it refuses to let someone vanish in the middle of a step, and
  hands out no detail the light did not already offer. The record is derived at
  commit from the same before/after positions orientation already reads,
  counts down while the body stays put, and is dropped the moment it moves
  again or leaves — so it can only ever describe the crossing itself.

- **Light — the other half of sight.** Sight was decided entirely by barriers:
  whether something stood between two rooms, and whether you could see through
  it. Whether there was any light to see *by* did not exist. A pitch-black
  cellar and a sunlit hall were identical to the engine, which for a system
  whose whole purpose is to stop a mind knowing what it did not perceive is the
  largest hole in that promise — darkness is the most ordinary perception gate
  there is.

  Every room now carries `light`: dark, dim, lit or bright. Absent means lit, so
  nothing changes for a scene that never mentions it. **In a dark room nobody
  sees anything** — not the room, not the person standing beside them — which
  is enforced at `has_visual`, the one place sight is decided, so it holds
  everywhere at once. Dim is shapes and movement without detail. Light spills:
  a dark room with an open way through to a lit one is dim rather than pitch
  black, worked out from the room's own light so only that has to be authored.

  **Carried light travels.** A torch, lantern, candle or screen is an entity
  with `light_source` set to what it emits, and it lights whatever room it is
  in — following its bearer for free, since a carried thing already has its
  holder's position derived onto it. Put it out (`state.lit` false) and the
  dark comes straight back, which is the whole tension of carrying one.

  **Light is graded, not binary.** `sight_level` mirrors `hear_level`'s shape —
  none / shapes / full. Dark is nothing at all; dim is movement, outline and
  bulk but not faces, not detail, not *who*; lit and bright are ordinary sight.
  So a character in dim light knows someone is there and must not recognize
  them by sight alone — identification comes from a voice, from already knowing
  them, from getting closer or bringing light.

  **And local, not room-wide.** A source declares `light_radius`: a pool
  (`spot` — a hand torch, a candle; the default for anything portable) or the
  whole space (`room` — a hearth, a ceiling lamp, a bonfire). A pool lights
  whoever holds it and whoever stands with them, and leaves everyone else in
  that room a shape in the dark who can see the light without being in it. A
  torch never silently illuminates the far corner.

  It reaches the backdrops too, painted as the player sees it: a cave crossed
  with a lit torch renders torchlit, and switching the light off returns it to
  the dark — which counts as a room change for the cache, or the dark cave
  would keep serving the lit picture. Intensity shapes the image rather than
  just its presence, so a candle gives a small pool falling off into deep
  shadow and a bonfire throws hard light across the space; a hand light in an
  otherwise dark room says so explicitly, or the model paints an evenly lit
  room with a torch standing in it.

- **Sound now depends on what the barrier is made of.** A paper shoji screen and
  an oak door are both `closed_door` — they stop a body and block sight
  identically — and are nothing alike to listen through. An optional `material`
  on an adjacency shifts how sound carries without touching sight or passage:
  paper, curtain and cloth pass a voice almost unhindered; wood is the default;
  metal, stone and glass take a grade away; soundproofing takes two.

- **Bodily condition, off by default.** Air, stamina, nourishment and injury per
  body, moved by how much simulation time a beat takes rather than by turns.
  Off means **absent** — no table, no ticking, nothing in any prompt — because a
  story that never asked for a hunger clock should not pay for one in state, in
  tokens, or in the Director's attention. A settings toggle turns it on, and a
  condition tracker appears in the Cast tab showing every tracked body.

  Air is the one with teeth, and it exists because of containers-as-places:
  sealing someone in was previously survivable indefinitely. Air depletes only
  for a body in a sealed enclosure, and fast — glass and bars included, since
  being seen through something is not breathing through it.

  The switch is **per story**, not per install, and lives in Genre & style with
  the other standing decisions about a story: one chat can be an ordeal and the
  next a conversation in a tavern. It survives rewinds and branches on the
  mechanism that already carries genre and NPC autonomy. The vitals themselves
  are diegetic and deliberately do not — rewind to before you were starving and
  you are not starving.

  The tracker is a corner panel rather than a buried tab: bottom-left, so it
  cannot collide with the activity panel that owns the bottom-right, and built
  from that panel's own rules so it reads as part of the frame. Player first,
  then every other tracked body — the Director tracks NPCs too, and a companion
  who is starving matters to you.

  The switch is **per story**, not per install, and lives in Genre & style
  where the other standing decisions about a story already are: one chat can be
  an ordeal and the next a conversation in a tavern. It rides through rewinds
  and branches on the same mechanism that already carries genre and NPC
  autonomy (`PRESERVED_SETTING_KEYS`), so rewinding to turn 12 cannot silently
  switch it off. The vitals themselves are diegetic and deliberately do *not*:
  they live in the scene blob and roll back with everything else, so rewinding
  to before you were starving means you are not starving.

  The tracker is a corner panel rather than a buried tab — bottom-left, so it
  can never collide with the activity panel that owns the bottom-right, and
  built from that panel's own rules so it reads as part of the frame. It lists
  the player first and every other tracked body after, because the Director
  tracks NPCs too: a companion who is starving matters to you.

- **Backdrop prompts say what the eye sees.** Image generators reject on
  keywords rather than on meaning, and a room description written for prose is
  full of them: "blood on the walls" is an ordinary thing for a room to have
  after a fight and an instant refusal from most generators, so a legitimate
  empty-room backdrop failed on a word. Charged vocabulary is now rewritten
  into what it actually looks like — dark red staining, dark wet residue, iron
  cuffs and chain, a heavy wooden frame — which paints the identical picture
  and is also better image prompting, since generators render colour, texture
  and form far more reliably than they render abstractions.

  Nouns that can only be a *person* are not patched but dropped with their
  whole sentence, exactly as a pronoun or a speech verb already was: a sentence
  about a body has no place in an empty-room prompt, and rewriting the word
  would have left "The has been removed" behind. Backdrops remain people-free
  by construction, so what is being described throughout is furniture, surfaces
  and light. The rewrite runs through `place_desc`, the single definition of
  what a place looks like, so the prompt and the cache key cannot drift.

- **Authoring edits stopped being discarded by rewinds.** A rewind rolls back
  the story; it was also rolling back two things the *author* had decided. The
  persona's private history — edited behind the lock in the Cast tab — reverted
  on any reroll, so editing your own secrets and then rerunning a turn silently
  threw the edit away. Declared fixed points went the same way: the paradox
  *policy* was preserved across a restore while the points themselves were not,
  so rewinding past the turn one was declared on quietly retracted it. Both now
  ride through on the same mechanism that already carries genre and NPC
  autonomy. The story state they shape — the paradoxes those points detect, and
  everything in the scene — still reverts, which is the entire purpose of a
  rewind.

### Fixed
- **Restraint was detected and never enforced.** A tripwire has scanned prose
  for someone being bound since the omission audit, and asks the Director to
  record a `restraint` condition. Nothing ever read it, so a character recorded
  as bound hand and foot could still walk across the room — the state was
  written, believed by nobody, enforced nowhere. A restraint in force now blocks
  that body from relocating itself, including one applied in the same beat.
  Being *carried* while bound is still allowed: that is the restrainer moving
  them, not them walking off.

- **A shout through prison bars was inaudible.** `window` and `bars` were added
  to the barrier vocabulary in 4.5 without cases in `hear_level`, so both fell
  through to silence. Bars now carry a voice as an open door does — the
  difference between a cage and a cell — and glass carries only a shout, as a
  fragment.

- **`enclosure` did not survive validation.** The field added in 4.5 was never
  declared on `SceneEntityDef`, and the schema round-trip drops anything a model
  does not declare — exactly the trap `RoomDef.zone` carries a comment about. A
  Director-authored glass case came back opaque. Found while adding `light`,
  which would have had the identical bug.

## alpha4.5 — Seen but not reached

### Added
- **Windows. They did not exist.** A barrier answered exactly one question —
  can a body pass — and every consumer reused that answer for sight as well.
  So there was no way to say *you can see it and cannot reach it*. Anything
  glassy had to degrade to `wall` (the normalizer's fallback for anything it
  does not recognize, so fully opaque) or be lied about as `open`. A cell with
  a barred door, an observation port, a shopfront, a porthole: none of them
  could be expressed, and this was an oversight for ordinary rooms long before
  it was one for containers.

  `window` and `bars` now exist, and the three questions a barrier answers are
  kept apart, because they genuinely differ:

  | | passage | sight | sound |
  |---|---|---|---|
  | `open`, `open_door` | yes | yes | yes |
  | `window` | no | **yes** | no |
  | `bars` | no | **yes** | **yes** |
  | `closed_door`, `wall` | no | no | no |

  Glass stops sound as well as bodies; a cage does not. Both are normalized
  from the vocabulary a model actually reaches for — glass, pane, porthole,
  viewport, one-way mirror; bars, cage, grate, grille, portcullis, lattice.

- **Containers are places, and see-through ones are seen through.** A container
  big enough to be inside is a room with `parent_entity`, which the engine has
  supported for vehicles all along — its own comment already named "a carried
  container" as a case. What was missing was what a *closed* one lets through.
  An entity now carries `enclosure`: `opaque` (the default and the old
  behaviour), `transparent`, or `barred`, and the derived doorway becomes a
  window or bars instead of a closed door.

  So a body sealed in a glass jar is visible to the room and can see out, and
  neither can reach the other — with no special case anywhere, because sight is
  decided in exactly one place (`has_visual`) and it now consults the sight set.
  A lid is also read from `state.hatch` directly, not only from a transit blob:
  a jar has a lid and no journey.

- **Nobody perceives the inside of what they are carrying.** An interior room
  attached to a carried or portable entity is no longer part of the surrounding
  room's view, so a character standing in a hall stops perpetually perceiving
  the inside of their own bag. Keyed on the carrier relation rather than on any
  notion of smallness: a ship's hold you are walking through stays ordinary
  scenery, because nobody is carrying the ship, and the same crate becomes
  invisible the moment someone picks it up.

  Looking in is an act with a result, not something a character simply always
  knew. The split that makes this coherent: you do not take in the inside of a
  carried thing as a *place*, but a body visible through its wall is still a
  body you can see — so the occupant of a carried glass jar is perceived, while
  the jar's interior is not scenery.

## alpha4.4.2 — Size, and being carried

### Added
- **Being carried: pockets, jars, shoulders, hands.** The sibling of the size
  change above, and the reason it had to exist. A body shrunk to a tenth and
  picked up is not merely *in contact with* the hand holding it — it has
  stopped being an independently positioned thing. Contact alone left the tiny
  person free to walk out of the room while sitting in someone's pocket,
  because nothing tied their position to their container's.

  `state_diff.containment` records it as `{subject: {in: holder, mode: ...}}`,
  released with a null value, and a contained body's position is then
  **derived** — transitively, so a person in a jar in a satchel goes where the
  satchel goes. Writing a position for a carried body does nothing; getting out
  is an explicit release, because "they climbed out and walked away" and "the
  Director forgot they were in a pocket" produce the identical diff and only
  one of them is meant. The Director is told plainly what a carried character
  cannot do: walk to the door, take something from a shelf, step between two
  people. What it can do is act on its container and whatever is within reach
  of it.

  Containment is released automatically when either body changes size — someone
  restored to full height is not still in a coat pocket — and, like the contact
  rule, that release runs *before* the beat's own declarations, so re-declaring
  the arrangement as the thing it now is keeps it. Cycles are refused, since a
  body inside itself makes position derivation unresolvable.

  Interior rooms remain the mechanism for large containers you stand *inside*
  (a ship, a building). This is the other direction: a container that carries
  you as cargo.

- **Shrinking and growing, and what stops being possible afterwards.** A body's
  size is now tracked as live physical state — `state_diff.scales` as
  `{name: factor}` relative to that body's own normal size, so 0.1 is a tenth
  as tall and 8 is eight times. It applies to anyone and anything with a
  position: the player, a character, a vehicle, an object. Absent means normal,
  so a scene that never mentions size behaves exactly as it did before.

  **A hold does not survive a size change.** This is the part the engine
  enforces rather than asks for. A contact is a fact about two bodies at the
  sizes they were: shrink the held person to a tenth and "his hand grips her
  wrist" is not a smaller version of itself — the wrist is no longer where the
  hand is. So every contact involving a resized body is cancelled outright
  rather than quietly rescaled, and whether anything equivalent is still
  possible is a question only the Director can answer. It is the same
  discipline movement already follows: a contact the physical situation no
  longer supports does not survive on inertia.

  Cancellation happens *before* the beat's own contact ops, so a Director that
  correctly re-establishes a hold as the thing it now is — a hand that held a
  wrist now closing around the whole body — keeps it. Holds it does not
  re-establish stay ended, which is right for every grip the new size has
  broken. A trivial change does not break anything; a growth spurt is not a
  reconfiguration.

  Everything else about feasibility is *reported*, not enforced, because the
  Director owns whether an act succeeds. It is now given the geometry to reason
  from — the ratio between two bodies, and whether one can reach the other's
  upper body, lift them, be lifted by them, or be held in a hand — so "too
  small to reach the latch" comes from a number rather than from vibes. The
  narrator is told the same, before the contacts it invalidates. The prompt
  spells out the consequences the model is expected to draw: an attempt the new
  size makes impossible fails on-page *for that reason*, an attempt it makes
  trivial simply succeeds, and the world is never silently rescaled to keep an
  act working.

  Size deliberately does **not** prune by position, unlike contact. A contact
  genuinely requires two bodies in one room; a size does not, so someone shrunk
  who steps offscreen for a scene is still shrunk when they return.

## alpha4.4.1 — One contact, one place

### Changed
- **Contact left in entity state is lifted out of it.** The prose shape that
  predates contact tracking — a whole-body `target` with a `proximity` word, and
  in practice a drift of invented keys naming the other body
  (`leaning_against: "tamamo"`, `tails_wrapped_around: "Tamamo"`,
  `squished_against: "tamamo_side"`) — is a real physical fact written in the
  wrong place, where nothing prunes it when the two walk apart. Those
  assertions are now converted to contacts and **removed** from the state, so
  one contact has exactly one record. That also backfills a save written before
  contacts existed: the assertions become real contacts and immediately obey the
  same positional hygiene as everything else, so a hold left over from an old
  beat ends the moment the two are no longer in the same room.

  Conversion is deliberately narrow, because inventing a hold is worse than
  missing one — a contact becomes ground truth the narrator is told. Only a key
  whose *name* carries a contact verb and whose *value* names a co-located
  person converts, and the shape often yields the anatomy for free
  (`tails_wrapped_around` → the tails, wrapping; `squished_against:
  "tamamo_side"` → against Tamamo's side). Adjacency words are not contact:
  `alongside` and `beside` are neither converted nor touched. Nearness is not
  contact either — `proximity: "close_on_bed"` stays proximity, which stations
  already model. Structurally load-bearing state (`transit`, `link`, `phase`,
  `hatch`, `posture`, `activity`, `held_items`) is never touched, and the
  free-text `description` paragraph is **not** parsed: regex over prose would
  manufacture body parts and holds nobody asserted.

  The Director is now also told plainly that contact belongs in `contact_ops`
  and nowhere else — state describes one body, contact is a relation between
  two, and a copy living on each body is how the two fall out of step.

- **One hold stated from both sides is one contact.** A contact and its mirror
  — the same pair with the parts swapped — are the same physical fact, so only
  one record survives, and re-asserting from the other side updates it rather
  than creating its twin. Each holding the other's wrist is still two contacts;
  that is two holds, not one stated twice.

- **`scene.contacts` always exists after a merge**, empty or not. A reader that
  has to ask whether contact tracking is "on" for a given scene is a reader that
  will eventually forget to.

## alpha4.4 — What is touching what

### Added
- **Body position tracking — who is in contact with whom, and where.** Physical
  contact used to live as prose inside an entity's own state: one whole-body
  `target`, a `proximity` word, and a free-text paragraph, written by the model
  and read back by the model with nothing structural in between. It cost four
  things at once.

  It could not say *where*. One whole-body target meant a hand on a shoulder and
  a grip on a wrist were the same fact, and holding two people at once was
  unsayable. It was stored per body, so a single contact became two records free
  to drift apart. Nothing ever cleared it — the paragraph persisted verbatim
  until the model happened to rewrite it, so a grip survived the person walking
  away, and a detail could migrate between beats with no transition and no
  record of either position. And nothing could query it, so the narrator had
  only prose to re-read and was free to contradict it.

  A contact is a relation, so it is now stored once, at scene level, in the
  grain `stations` already established: a list that deterministic hygiene prunes
  at every merge. The Director maintains it through `state_diff.contact_ops` —
  `add` with the parts involved (`hand` → `wrist`) and a manner, `remove` for a
  release, `clear` to let go of everything at once — and each contact carries
  both body parts, so one person can hold several things, in different ways, at
  the same time.

  The staleness is fixed structurally rather than by asking the model to
  remember: **a contact between two people who are no longer in the same room is
  dropped automatically.** Walking away ends a hold with no op required, the
  same way a room change already self-heals a stale station anchor. The
  Director never has to re-assert an unchanged contact, and cannot smuggle in a
  hold across two rooms, because hygiene runs after the ops either way.

  Contact is also now ground truth the narrator is told rather than left to
  infer — with both parties gated on being nameable to that observer, exactly
  like the existing proximity clauses, so a hold by someone unrecognized yields
  no named line rather than leaking a name the observer has no way to know.

  Useful well beyond the case that prompted it: a grapple, carrying someone,
  restraints, a hand on a shoulder held through a conversation, a grip on a
  rope. Existing scenes start empty and gain contacts as they are recorded.

## alpha4.3.3 — One body, one record

### Fixed
- **One body, one entity record.** A character could end up recorded twice in
  the scene at once — once under `identity.uid` and once under their display
  name — because the Director keys entities with whichever handle it reaches
  for, and nothing collapsed the two. Both records claimed to describe the same
  person, each carrying its own posture, proximity and contact, and the older
  one simply froze at the beat it was created while the other went on being
  rewritten. So "who is in contact with whom" had two contradictory answers
  simultaneously, one of them arbitrarily stale, and every reader that walks
  entities — perception, narration, the character agents — saw one person
  standing there twice.

  This is the third instance of one bug, and the first two are already fixed in
  the same way. `positions` survived it because readers try every key and
  duplicates collapse (`_dedup_duplicate_position_keys`); `attire` was healed
  after a character rendered as wearing nothing while her clothing state still
  described the coat she had on (`_heal_attire_identity_keys`). `entities` had
  neither guard, and it is the record that says what each body is doing.

  Duplicates now collapse at the scene merge, onto the display-name key every
  reader already uses. One deliberate difference from the attire heal: `state`
  is **not** merged field-by-field. A wardrobe accumulates, but posture and
  contact describe a single instant, so folding a stale snapshot into a fresh
  one is precisely what manufactures the contradiction — the record the beat
  just wrote wins whole. Only durable structural facts (kind, aliases, a
  vehicle's `interior_rooms`) are rescued from the discarded record, so
  collapsing can never orphan an interior. Existing saves heal on their next
  committed turn.

## alpha4.3.2 — Closing your eyes is not leaving the scene

### Fixed
- **Closing your eyes is not leaving the scene.** In a live chat the player
  wrote "You breath softly as you close your eyes wrapping your arms around
  her", curled against her mother in a nest, and the Director recorded an
  `awareness` condition on the **player** at level `asleep`, cause "settling
  into rest and protective affection after arrival". `asleep` is one of the
  gated levels, so the next beat would have opened her own view with "You are
  under, below waking." — no room, no sight, no speech, and no action — until
  the Director chose to end it. The player had asked for a cuddle.

  The prompt was the mechanism. Its AWARENESS rule listed "falls asleep" in the
  same breath as knocked out, sedated and drugged under, with an unconditional
  MUST and a warning that an omitted condition is a bug — pressure in one
  direction and no threshold in the other. Sleep now carries the same bar as a
  knockout, stated as what the level actually does: the mind is gone from the
  scene, so record it only once the character can no longer respond to what is
  said around them. Resting, lying down, closing the eyes, breathing slowly,
  leaning on someone, being drowsy or tired, or starting to drift are named as
  *not* non-awake states — a scene can be still, dark and half-dreaming with
  everyone in it fully awake.

  Underneath it, a deterministic floor, because this cost more than a lost beat:
  the engine already scans prose for a knockout the diff *forgot*, and it now
  also drops a gated level the diff imposed on the **player** with nothing in
  the beat to support it — no sleep or knockout language in their own input, in
  the resolved prose, or in anything spoken. The player alone is protected, for
  the asymmetry: a spurious non-awake NPC costs one beat of silence, while for
  the player it removes both their view of the story and their next move, which
  is the Director overriding declared player conduct in its strongest form.
  Waking (`active:0`) is never touched — dropping that would strand them under
  forever — and `dazed`, which does not gate, is left to the Director.

- **"Pass out" is now caught by the consciousness floor.** The cue pattern used
  `passes?\s+out`, which matches "passe" and "passes" but never bare "pass" —
  so second-person prose ("the blow makes you pass out") escaped the scan whose
  entire job is catching an unrecorded knockout. Same flaw in "black out" and
  "go limp". Found while adding the guard above, which had inherited it.

## alpha4.3.1 — Interrupted is not lost

### Added
- **A cast member can be moved to another room.** The Cast tab now shows which
  room each participant is standing in and lets you put them somewhere else,
  including inside a vehicle or building interior (labelled with what it is
  inside, so "Console Room" reads as "The TARDIS › Console Room") and including
  nowhere at all, which is offscreen. The player's own position is shown for
  orientation but not editable here: where the protagonist stands is the
  story's business, not an authoring dropdown's.

  It is an authoring edit and deliberately silent — like the world and attire
  editors, it changes state and narrates nothing. Adding or dismissing a
  character queues an arrival or departure beat for the narrator; a relocation
  queues nothing, so if the move should be seen, write it.

  Positions are only ever read from and written to the scene blob, which is the
  single runtime source of truth for who is standing where. Two things are
  therefore refused rather than trusted: a room id that is not in the scene
  (a position naming a room that does not exist puts someone nowhere that
  perception, adjacency, or the narrator can reason about), and any edit while
  a pipeline is running, which reads and rewrites positions throughout a turn.
  The write also lands on the spelling the scene already uses for that person
  rather than adding a second one — `spatial.room_of` matches names loosely, so
  two keys for one character would put them in two rooms at once for every
  reader that walks positions to find a room's occupants.

- **An interrupted lorebook-tree generation can be picked up where it
  stopped.** Generating a tree was one blocking request wrapped around one
  model call, and nothing was written down until the user applied the finished
  plan — so every way a long call can end badly ended the same way: with
  nothing. A dropped stream, a provider that ran out of retries, a closed tab,
  a refresh, a restarted server. Even *success* was fragile: the plan existed
  only in the HTTP response, so a tab closed one second early discarded work
  that had already been paid for in full.

  A run is now many recorded units instead of one unrecorded one. A cheap
  structure call settles the books, the links, and an outline of the entries;
  each following call writes one batch of those entries. Every completed unit
  is persisted to `lore_gen_jobs` the moment it lands, which is what gives
  recovery something to recover: resuming re-runs only the units that never
  finished, and the generator tab offers it on open — the plan lives in the
  job row, not in the browser.

  The distinction the recovery turns on is *why* a run stopped, because the two
  answers deserve opposite behaviour. Transport failure (a dropped connection,
  an exhausted retry budget, an abort) means the provider is unavailable right
  now, so the run stops immediately rather than marching the remaining batches
  into the same wall — every finished batch is kept and handed back as a
  reviewable partial plan. Unusable *output* from one batch is a content
  problem, not an outage: that batch alone is marked failed and the run carries
  on, so one bad response costs one batch instead of the other twelve. Either
  way a resume retries exactly the stubs that are not yet done.

  A run abandoned by a dead process is detected exactly, not by a timeout: each
  job carries the token of the process that started it, so a `running` row
  stamped by any other process is a crash by definition. Two consequences fall
  out of the same design. Splitting the call also gives each entry a real share
  of the output budget, which forty rich entries squeezed into a single
  8000-token response never had. And a run whose plan finished generating but
  whose response never reached the browser is now the cheapest recovery of all:
  the work is done, only the delivery was lost, and restoring it costs no model
  call at all.

  Nothing here writes lore. The plan is still provisional until it is applied,
  and applying it retires the run.
- **Lorebook generation can be given longer than 300 seconds.** The provider
  read timeout is sized for pipeline turns, which must not hang a player
  mid-scene — but a slow local model can still be producing a batch of entries
  when it expires, and cutting the connection there fails a response that was
  on its way. That failure is indistinguishable, from the outside, from the
  network dropping: it retries, exhausts its budget, and ends the run.

  The generator now has a **Model timeout (s)** field (30s–1h) that raises the
  read timeout for its own calls, leaving every other call in the engine on the
  default — nobody else pays for one long authoring pass. The value is stored
  with the request, so each later batch and each later resume inherits it, and
  a resume may raise it further than the attempt that ran out of it. Since a
  read timeout is itself one of the interruptions above, "generation timed out"
  and "resume with more time, keeping what already finished" are now the same
  gesture. Editing the field is what opts into overriding a recovered run's
  allowance; leaving it alone never quietly lowers one.

### Fixed
- **A story's lorebook tree shows the story's lorebooks.** Opening a book in a
  chat's workspace showed a fraction of that chat's tree, and for a chat whose
  canon book had no children it showed exactly one book — the one you clicked.
  The books were not missing; the browser was asking the wrong question.

  It built its tree from the chat payload's `lorebooks`, which is
  `chat_lorebook_ids()`: the *retrieval* graph, resolved outward from canon plus
  attachments through parents, children and links. That is the right question
  for "what lore may this chat draw on" and the wrong one for "what does this
  chat have," because a book that hangs off nothing is reachable from nothing.
  Every chat in the live database held such books — `TARDIS`, `Shelter
  Elevator`, `Japan`, two stray `Kansai Region`s — chat-owned, `parent_id`
  NULL, never attached, and so absent from the tree that was supposed to list
  them. The workspace now asks about ownership, via a new
  `GET /api/chats/{id}/lorebooks`, which cannot orphan anything; it also
  replaces a per-book request fan-out with one call.

  Retrieval scoping is deliberately untouched — making these books *visible*
  is a browser question, making them *readable* would put lore into play that
  was not in play before. So the tree says which is which: a book nothing
  reaches is badged **unreachable**, with the explanation that its entries can
  never reach the story and that dragging it onto a parent connects it. That
  state was previously not merely unshown but unsayable.

  The generator's apply path was one live source of these orphans: a planned
  book whose parent could not be resolved was written with no parent at all.
  `commit.py` already refuses to do that ("keeps the tree rooted under canon --
  never an unreachable orphan"); `apply_lorebook_plan` now follows the same
  rule, rooting under the book the plan was generated for, and an entry whose
  book reference does not resolve is filed there too rather than silently
  dropped. Existing orphans stay as they are — they are yours to place, and the
  tree can finally show you where they are.

- **An unstarted chat can be asked about its scene.** `scene.get_scene` read
  `(chat or {}).get("scenario")`, which raises `AttributeError` on a
  `sqlite3.Row` — and the app's scene-reading routes pass the row straight from
  `q()`. It only fired on the no-scene path, so asking a chat that had not
  opened yet about its attire returned a 500 rather than an empty scene. Found
  while adding relocation, which reads the scene the same way.

## alpha4.3 — A goal can be spent as well as impossible

### Fixed
- **A character stops asking the question that stopped paying.** In a live
  chat the Doctor asked Hinami to describe the same "made from nothing"
  quality of a replicated spanner for eleven consecutive turns, reaching for a
  new image each time — a book missing its first chapter, a song without its
  opening bars, an echo that never had a source — while asking for exactly the
  same thing. By turn 73 the narrator was describing the fault directly: "he
  keeps reaching for a layer you can't find, and every new metaphor he offers
  just makes the gap wider."

  The cause was a guard defeated by the behaviour it existed to catch. An
  intention that goes untouched for 30 turns fades to dormant so it cannot
  steer forever — but `{op:'progress'}` refreshed `last_progress_turn`
  unconditionally, including on a goal already at `progress: 1.0` where the
  value could not move. Grinding a goal every single beat therefore reset the
  only timer that could ever retire it, so the sweep could fire on a
  *forgotten* goal and never on a *stuck* one. The Doctor's `i2` sat at
  `status: active, progress: 1.0` from turn 68 onward, still steering, its
  clock refreshed by each fruitless attempt. The character agent was not
  confused about this — turn 71's own appraisal recorded that the reply
  "supplies no new modal detail despite the reframing", and then logged
  progress anyway.

  The asymmetry underneath it: `satisfy`, `abandon` and `nonviable` all
  require on-screen evidence, so a goal is never quietly *dropped* — while
  keeping one alive was entirely unguarded, so a goal was never *let go*.
  Progress that cannot move the value is now barren: it leaves the clock
  alone, never revives a set-aside goal, and after two in a row the goal stops
  steering and must be satisfied, abandoned, or replaced by one that asks
  something genuinely different. Rephrasing does not launder it back to active
  — an `add` that merges into a spent goal revives it only if it had somewhere
  left to go. Closing a goal still requires evidence; only pursuit past the
  point of yield is stopped. Replayed against the live chat, `i2` goes dormant
  at turn 70, three turns before the narrator started apologising for it.

  What made this read as *fixation* rather than as a broken record is that the
  anti-repetition machinery was working perfectly. `_recent_self_lines` feeds a
  character its own recent dialogue so it never repeats itself verbatim, and it
  didn't — it varied the wording every time. Wording variety over a stuck goal
  is what produces an escalating series of ever-more-elaborate metaphors, which
  is a worse symptom than plain repetition would have been. The character
  prompt now names that failure directly: a fresh image over the same request
  is a loop wearing a disguise.
- **A goal that stopped steering stops moving the mood too.** The same
  asymmetry had a second outlet. Appraisal weights each goal-impact by what it
  serves — 1.0 for the drive, 0.8 for an intention, 0.4 for anything
  situational — and the 0.8 was awarded to any id present in the character's
  intentions list, regardless of its status. So a goal the world had sealed
  off, a goal gone dormant, even one the character had explicitly abandoned,
  kept hitting affect exactly as hard as a live one for the rest of the story.
  `test_goal_viability` has asserted since it was written that a blocked goal
  "no longer steers"; through the prompt it mostly didn't, but the affect maths
  still paid it in full.

  Weight now goes to goals that are active — or that were touched **this**
  beat, whatever their new status. That second clause is the whole delicacy of
  it: satisfy, abandon and nonviable all stamp the turn they fire on, and the
  beat a goal is achieved, released, or destroyed is the beat it matters most.
  Muting the payoff at the exact moment it lands would have been a worse fault
  than the one being fixed. A stall is the deliberate exception — it does not
  stamp the clock, because arriving at "nothing gained, again" is not a
  dramatic beat and should not be scored like one.

  What did *not* change: which ids a want may name. Those are validated against
  the full list, because a beat's wants were formed against the intentions the
  character saw when the beat started — demoting one because its goal closed
  mid-beat would punish a mind for a state change it could not have seen, and
  demotion also culls all but the highest-urgency situational want, which is a
  side effect far out of proportion. Steering stops on the next beat, through
  the prompt, where the new status is visible.
- **A revived goal stops carrying the turn it was blocked on.** Progressing a
  blocked intention clears the block, but `blocked_turn` outlived it, so an
  active goal kept a stamp from a state it was no longer in (live: the Doctor's
  `i2` carried `blocked_turn: 57` while active at turn 71). Nothing read the
  field, so this was stale data rather than wrong behaviour — cleared with the
  rest of the block now.

## alpha4.2.2 — The whole tavern is a library

The tavern's Lore tab was the only place the theme committed to an idea: rows
became bound books on a shelf, and the lorebook editor became an open spread.
Everything around it stayed generic wood. That gap read as one tab's private
conceit rather than as what the interface is, so the idea now runs the length
of the theme — and the paper it is printed on stops being a lightbox.

### Improved
- **Stories, Characters and Personas are shelves too.** The three other sidebar
  tabs were planks while Lore was books. They now carry the same binding
  vocabulary the Lore shelf already had — raised spine bands, gilt tooling,
  fore-edge shading, the same five leathers on the same cycle — so switching
  tabs changes what is on the shelf rather than what furniture you are looking
  at. The selected row pulls proud of the stack the way an opened book does,
  and rename/export/delete become tooling on the spine instead of small planks
  nailed to it. No markup changed; the shelf board hangs off the last row
  rather than the container, because the container is also where the Lore tab
  renders a tree that already has a shelf of its own.
- **Every menu is a page.** The open-book treatment was scoped to the lorebook
  editor. It now binds to `#modalbox`, which is every dialog in the app —
  story setup, the character and persona editors, cast, world state, attire,
  dialogue, style, backdrops, appearance, API, prompts, memory — so the menu
  system is one book with no per-dialog rule anywhere. This is affordable
  because `styles.css` and `lorebooks.css` are almost entirely token-driven:
  rebinding tokens on the page re-tints inputs, buttons, cards, badges, chips
  and hovers at once, and rebinding the `--bg` ramp catches the second tier
  (inset code blocks, dropdown panels, toolbars) that reads `--bg` directly on
  the assumption that it is dark. The lorebook editor dropped the leather board
  it used to carry inside itself: the dialog is the binding now, and a second
  board put a wooden frame between the cover and the pages.
- **A dialog is bound in the cover of the book you opened it from.** Clicking a
  character, persona or lorebook binds its window in that row's leather;
  windows opened from the toolbar hash their title to a cover instead, so each
  is consistently its own volume rather than changing binding per opening. The
  choice is made in `components.js` because which list row you clicked is not
  something a stylesheet can see from `#modalbox`; it writes `data-cover`, and
  every other theme ignores it.

### Fixed
- **Paper stopped being the brightest thing on the screen.** The sheet was
  `#f2e6cb` down to `#e6d5b3` — the colour of new paper under a flash. Against
  a room this dark that reads as a lightbox rather than as something lying on
  the table, and a dialog opening at night put it straight into your eyes. It
  is old stock now, same hue at roughly half the luminance. The ink did not
  move, so contrast went **up**: ~6.5:1 for body text against the sheet, where
  the original cream was too light to have anywhere to go. A test asserts the
  luminance ceiling and the contrast floor, because "still looks like paper" is
  exactly the judgement that drifts back upward one tweak at a time.
- **LCARS: black ink on the filled blocks that were carrying dark-theme text.**
  Three surfaces in that theme are solid LCARS orange, and each drew text
  chosen for a near-black row. Badges took `--dim` grey (~1.9:1). A selected
  lore row — the entry you are working on, and so the hardest thing in the
  editor to read — drew its name in near-white and its subtitle in grey over
  the same orange. Every filled block takes black ink now, and the status
  badges recolour the block rather than the text, since their pastel greens and
  pinks were tuned to glow on near-black and do nothing on orange.
- **LCARS: the inspector tab strip is visible again.** The tabs across the
  cast, persona and lorebook windows are transparent buttons with a coloured
  underline — a dark-theme idiom that collided with the black ink every LCARS
  button carries, leaving black text on a transparent strip over a black panel.
  You could only find the tabs by hovering. They are pills now, in the same
  blue and orange the sidebar tabs already use.
- **A stray `*/` was eating a plank variant.** A comment in the tavern board
  section closed early and left two lines of prose at the top level, which CSS
  error recovery swallows by consuming up to and including the next rule — so
  the first of the seven per-row grain offsets never applied, and every seventh
  list row showed the same grain at the same offset as its neighbour.

## alpha4.2.1 — A mind can cite the present

### Fixed
- **A character answers the line just spoken to it, not the one before.** In a
  live 61-turn chat the Doctor kept replying a beat late: on the turn the
  player asked "Why are you looking at me like that, you brought me here?", his
  considered responses were about asking what she meant by "future is weird" —
  the previous turn's line — and the observation he cited resolved to a
  `memories` row stamped with the previous turn's index. The cause was
  structural rather than a stale read. `observations_used` asks the character
  to cite an `event_id`; the only ids in its payload belong to memory rows, and
  `recent_memory_buffer` deliberately excludes the current turn — a mind must
  not see how the turn it is deciding turned out. So the present beat arrived
  as an uncitable prose string while the past arrived with ids attached, and
  the model reached for what it could cite. Across that one chat: 15 citations
  of a previous turn, zero of the current one, ever, and the effect grew as
  memories accumulated. The present beat now carries a citable id of its own
  and the prompt says to lead with it, with the reason attached. The exclusion
  is unchanged — it was never the bug.

## alpha4.2 — Themes

Appearance becomes a real system rather than one hard-coded palette, and the
themes that existed as colour schemes become places: a tavern with a fire in
the corner, a console, quarried stone.

This release absorbs two versions that were never tagged. `alpha4.1.2` and
`alpha4.1.3` were an outside proposal (ChatGPT) for the appearance pass; the
interface fixes in them were worth having and are kept below, but most of the
theme work has been replaced rather than built on — the textures were present
in the file and invisible on screen, and two of the themes have been withdrawn
outright. Nothing shipped under those numbers, so their entries are folded in
here instead of standing as releases of their own.

Shipping alongside it: the findings from auditing a 93-turn live chat
("Elevator Adventure ⎇41"), where the player spent twenty consecutive turns
walking forward down a condemned passage and kept arriving somewhere they had
already been — in character: "Does this corridor go on forever?", "How long is
this hallway............".

### Fixed
- **A partial entity diff no longer erases the rest of the entity.**
  `merge_scene_with_diff` replaced `scene.entities` wholesale where rooms got
  `_merge_room`, and validation had already filled every absent field with a
  schema default — so a Director pose-only update looked like a complete
  record. A vehicle with an interior became a nameless object, and a
  registered character became "The Doctor 10", kind `object`, on the turn
  after it was committed correctly. Entities now merge field-aware: a schema
  default is silence, never an erasure, and a name the validator derived from
  the dict key cannot displace one someone authored. Deliberate changes still
  land; clearing goes through `remove_entities`, as before.
- **Walking forward no longer walks you backward.** The room graph is
  undirected, so "keep going" and "turn back" name the same two doorways, and
  `director_interpret` was never shown the mover's heading. It now gets
  `player.exits` (ahead / behind / came_from, derived from the same
  `egocentric_frame` perception already uses) plus a prompt rule to match.
  Tightening the deterministic backstop was tried and reverted: it validates
  reachability only, but requiring corroboration for a multi-room walk breaks
  the contract `test_director_movement_routes.py` pins, where a legitimate
  three-hop walk through open doorways must commit or the narrator describes
  arriving while the position never moves. Direction is enforced by giving the
  Director the heading, not by rejecting reachable destinations.
- **A room can no longer offer two different neighbours on one bearing.**
  Adjacency deduped by target but not by direction, so one room held `dir: "w"`
  to two rooms and "ahead" was ambiguous. Colliding bearings are dropped from
  both edges and their reciprocals, keeping the doorways — the same policy a
  contradicting reciprocal already had.
- **Perception no longer receives object lookup vocabulary.** Entity `aliases`
  and dict keys exist for `_name_to_entity_id` to match against; an observer
  has no way to acquire them. A character's own view named a thing "the
  TARDIS" — a word she had never heard — in the same sentence where the man
  himself was correctly anonymized as "the lean energetic man", because
  identity scrubbing covers cast and never covered objects. The perception
  payload now carries only what an observer could take in.
- **Attire is keyed one way per character.** A character answers to several
  scene keys (display name, `identity.uid`, aliases) and the Director used
  whichever it reached for; every reader looks under the display name alone.
  One character held her clothes under her uid and an empty `wearing` list
  under her name, rendering as dressed in nothing while her clothing state
  still read "lab coat ripped at the hem". Records now merge onto the display
  name — which heals existing saves — and incoming keys are canonicalized.
  Positions already had both halves of this fix; attire had neither.
- **A room id no longer overwrites the room's name.** The staged-lore
  materializers name a new room after its id as a placeholder, and re-ran for
  rooms that already existed — so an authored "Branching Junction" became
  "Site17 Deep Shelter Branching Junction" as the player-visible label. They
  now only materialize genuinely new rooms, and `_merge_room` refuses an id
  slug that would replace an authored name.
- **`scene.description` refreshes on relocation.** It was only ever written
  from `director_establish`, i.e. once on the opening turn, and still
  described the surface elevator bay 92 turns later. Nothing reads it back
  today, so this was latent — but it is the sibling of the DW-1 `location`
  fix and now shares its trigger.
- **Reader settings survive a reroll or a branch.** NPC autonomy, prose
  pacing, background life and the style guide live in the chat-scoped `world`
  table — which is exactly what checkpoints snapshot and what restore wipes
  and re-inserts. Turning a dial and rerolling that same turn sprang it back,
  because the checkpoint predated the change; branching took the settings as
  of the branch point for the same reason. They are not turn-scoped facts, so
  restore now carries the live values across and branching overlays the
  source's current ones. Only keys that already exist are preserved, so a
  fresh chat still inherits from the snapshot. The list is deliberately
  narrow: ordinary world state is still rolled back.
- **Imported characters get a drive.** `psychology.drive` is Tier-1 of the
  goal hierarchy — every proactive want derives from it, so a blank one makes
  a character purely reactive. The generator and promotion prompts were given
  the "REQUIRED and load-bearing" guidance; the import path keeps its own copy
  of the schema prompt and never was, so every imported character arrived
  passive. It now asks for a drive and standing goals, an import that still
  lacks them says so instead of failing quietly, and the reinterpret call
  sizes its token budget off the card's volume the way the lorebook path
  already did.
- **A truncated character import no longer hollows out the sheet.** A model
  response missing one closing brace is repaired by `_jparse` into an object
  that parses but nests every remaining section under whichever one was left
  open; `_deep_defaults` then keeps those as unknown keys and backfills the
  real slots with defaults. The result was a character whose pronouns,
  aliases, voice, five abilities, whole history, three standing goals and
  first message sat inert one level down while the engine read an empty
  sheet — silently. `normalize_character_data` now lifts misplaced sections
  back out, preferring whichever copy actually carries content, and folds a
  flat identity back into `identity`. It runs on read, so damaged sheets heal
  without a migration. Legacy sheets also normalize with a drive slot.

- **A long story or character name stays readable.** Rows ellipsized the title
  to protect a fixed action column, so the very thing you were choosing from
  was the part that got cut. The row wraps now: a long name takes the lines it
  needs and the whole Rename/Export/Delete group drops below it together,
  still right-aligned and in the same order. Short names keep the single-row
  layout — `flex-basis:auto` makes the drop conditional, since flexbox breaks
  lines on max-content width, so no JS width probe is involved.
- **The composer shares the story's column and its text size.** The transcript
  was capped at 720px while the composer ran the full window width, so what
  you typed and what you read were different widths stacked on each other; and
  the story-text-size control never reached the input, so you could be typing
  at 13px into a story rendered at 21px. The input now uses the prose face at
  `--prose-size` and sits in the same centred column as the turns. Prior
  player inputs in the transcript scale with it too — what the player wrote is
  fiction, and it was staying at 13px system-ui while the story around it grew.
  The input's growth ceiling is now a share of the window rather than a flat
  220px (barely four lines at the largest story size), and it is read from CSS
  rather than duplicated in JS. Send no longer stretches into a slab as the
  box grows.

- **The close button in an LCARS window is visible again.** LCARS has no ghost
  control — a block is filled or it is not there — and that collided with two
  rules that are each correct alone: `button.ghost` zeroes the background, and
  the theme sets black ink on every button. The result was a black glyph on a
  transparent black panel, legible only as the gap where something should be.
  Every dismiss control in a window is now a filled pill in the theme's own
  dismiss colour, with the black ink it already wanted.

- **An AI-reinterpreted import no longer lets the model name the character's
  key.** `identity.uid` is not decoration: `scene.py` falls back to it for the
  scene *entity id*, and character matching keys off it as one of a character's
  forms. The reinterpret path took whatever the model wrote there, and live
  models write the character's own name — GLM returns `"tamamo"` — so every
  import of the same card produced the same uid. Two characters, one scene
  entity: one position, one set of clothes, one owner of the memories, with
  nothing reporting a conflict. Sheets a model reconstructed now get a freshly
  minted uid, on both the character and persona paths. Re-importing this app's
  own export still round-trips its uid exactly, since that path never went
  through the model in the first place.

### Changed
- **The Scroll and Daylight themes were withdrawn**, along with the parchment
  texture. A regression test keeps them from returning by halves.
- **LCARS was rebuilt around the actual design language.** It had become a
  dark theme wearing an 18px/5px opposite-corner radius on every control,
  which reads as scattered diagonal lines rather than a console. It is now
  flat colour on true black — no gradients, no texture — with the canonical
  palette, black ink on every colour block, full-pill controls, an elbowed
  frame whose spine turns the corner under the header, colour-cycled control
  banks, and condensed wide-tracked uppercase type. The sidebar keeps a black
  gutter so its contents clear the spine rather than butting against it, and
  the tab strip stacks two-by-two — four condensed uppercase labels do not fit
  a quarter of a 286px sidebar, and clipping a navigation label to keep one
  row is the wrong trade.
- **Tavern and Stone actually look like their names now.** Both were dark
  neutrals with a tint, and both carried a texture that was present in the
  file and invisible on screen — a 512px tile under a 95–97% opaque wash. The
  washes come down to roughly half, the tiles tighten so the figure repeats
  often enough to read at sidebar width, and each gets a crisp CSS grain layer
  over the photo, since the source images are too soft to carry it alone.
  Tavern becomes a *lit interior*: surfaces well clear of black, a hearth glow
  falling across the room, brass fittings and worn-round corners. Stone
  becomes quarried granite: mid-tones raised to real grey, near-square cut
  corners, borders darkened into mortar joints, chiselled small-caps headings,
  and a single warm torch accent to make the grey read as cold.
- **Tavern is a room with a fire in it, not a brown interface.** Four things
  were wrong at once and each was hiding the next. The list rows were
  transparent over the sidebar's own wood, so a single grain ran unbroken
  through the whole list and slid *underneath* the rows as they scrolled —
  which reads as a hole in the panel rather than as an object sitting on it;
  rows and cards are now opaque boards with their own face, eased corners and
  a lit top edge, and each samples the plank, the grain and the splits at a
  different offset, so no two boards on screen are cut alike. The grain
  itself was one evenly spaced repeat — every line parallel, the same weight,
  the same distance apart, which is the one thing wood never is — and is now
  two passes on opposed bearings with irregular spacing, so lines converge and
  separate across the width, with knots on the panelling at intervals that
  share no factor with the plank tile. Splits run on three different bearings
  and enter from different edges; a single set of parallel verticals read as
  panel seams dividing a row rather than as damage in one board. And the light
  was an even wash across the top, which is a tint rather than a source: there
  is now one hearth high in the left corner, every surface graded by its own
  distance from it, and a slow irregular flicker on the part that moves — one
  compositor-friendly opacity on one fixed layer, frozen (not removed) under
  `prefers-reduced-motion`. The sidebar footer gives up its own surface: its
  separate graded background restarted the sidebar's falloff at the seam, so
  the light stepped down abruptly where the wall should have continued to the
  floor.
- **The Lore tab in Tavern is a bookshelf.** Every other tab lists things that
  live in the story; the Lore tab lists *books*, and the tree it already
  renders is the same shape as the furniture — a book with children is a book
  with a shelf under it. So the rows become bound spines: bound edge left,
  fore-edge right, raised cords under the leather, a tooled gilt rule top and
  bottom, and five muted leathers on a cycle so a shelf is not one colour
  repeated. Books touch rather than sitting in a list with gaps, the nesting
  rail becomes the shelf upright, and the open book is pulled proud of its
  neighbours and casts onto them. No new markup: `.lore-side-*` exists only in
  this tab, so nothing else picks up book styling.

- **The lorebook editor is an open book in Tavern.** The workspace is already
  three panels side by side, which is the shape of an open book with a margin
  column, so this restyles what is there rather than adding markup: the pages
  are inset into a leather board, meet at a gutter instead of floating apart,
  and each is shaded at its edges so it curves down into the fold. Headings are
  ruled small-caps rather than filled title bars, and the accent inside a page
  becomes rubric red — the colour a scribe reserved for headings — since
  candle-brass on cream is not a legible ink. What made this affordable is that
  `lorebooks.css` is almost entirely token-driven, so *rebinding* the tokens on
  the page re-tints its inputs, badges, rules and hovers in one place; only the
  values that file hardcodes for a dark panel had to be restated. Cards on a
  page needed clearing by hand, because the Tavern board rule sets
  `background-image` directly rather than through a token, and a wooden plank
  was sitting in the middle of the paper.

### Added
- **Browser-local themes** under the 🎨 Appearance control: Sonder, Tavern,
  LCARS, Stone, and Ink. The choice is restored before the stylesheet paints,
  so a saved light theme does not flash dark on startup, and it carries through
  the sign-in and guest pages. (Scroll and Daylight were proposed in the
  withdrawn pass and are not shipping — see the Changed section.)
- **Independent story-text sizing** (compact through extra large), which scales
  the fiction transcript without inflating every editor and toolbar control.
- **A branch reads the source story's scene backdrops instead of redrawing
  them.** Backdrops are cached per chat and keyed by a signature over the
  room and its visible state — and a branch inherits the entire scene graph,
  so its rooms hash identically. Only the storage directory differed, so
  every branch used to regenerate its whole inheritance one room at a time, at
  full price. A branch now records its ancestry and reads those files where
  they lie. Nothing is copied: a branch still costs no bytes, which is the
  point of branching, and a story branched a dozen times would otherwise hold
  a dozen copies of the same corridor. The ancestry is a plain id list rather
  than a `parent_chat_id` foreign key because deleting a chat removes its rows
  and leaves its pictures on disk — a cascade-nulled pointer would lose files
  that are still there. Reuse follows the lineage and nothing else: an
  unrelated story that hashes a room the same way still draws its own, and
  import deliberately drops the lineage, since a raw chat id names one
  directory in the database it was written in and someone else's in any other.

### Improved (kept from the withdrawn 4.1.2/4.1.3 pass)
- **Player input contrast is deliberately stronger across themes.** The
  composer and the textarea use separate surface tokens, per-theme borders,
  clearer placeholder text, and a visibly raised field, so the place you type
  reads as an active control rather than one more panel.
- **The header is structurally responsive.** The story title stays anchored
  while only the tool strip scrolls, instead of the whole header drifting
  offscreen. The technical-detail toggle becomes a proper icon control on
  phones, and story tools keep usable touch targets.
- **Composer and sidebar actions are easier to hit.** Send is visually primary,
  Stop is destructive, side-footer actions share the available width, and the
  composer no longer lets its textarea squeeze the action buttons.
- **Rows are keyboard-openable** and their icon buttons carry explicit
  accessible labels. (The fixed action column those rows introduced is gone —
  see the wrapping-row entry above, which replaced it.)
- **Texture assets** live under `static/assets/theme-textures/`, with the
  regression coverage that keeps themed surfaces and contrast tokens part of
  the UI contract instead of an incidental visual tweak. (The textures
  themselves were re-tuned here: at the original 95–97% opaque washes they were
  present in the file and invisible on screen.)

## alpha4.1.1 — Backdrops stop holding the door

Two follow-ups to alpha4.1, both rescued from a parallel implementation of the
same feature that was written in a session whose context was lost. That branch
is superseded and will not be merged, but it was ahead on these two points and
they are worth having.

### Fixed
- **Generating a backdrop no longer blocks a server worker.** `POST
  /api/turns/{id}/backdrop` used to run the image call inline: tens of seconds
  normally, up to the provider's three-minute ceiling, with a request held open
  the whole time for a picture nobody is waiting on — the prose is already on
  screen. It now queues the work and returns `pending` immediately; a worker
  thread generates, and the GET reports `ready` / `pending` / `error` for
  polling. Two callers wanting the same picture share one worker, and a failure
  is reported rather than swallowed — out-of-band work that fails silently
  leaves the reader in front of an image that never arrives and never explains
  itself. Asking again clears the error and retries, so topping up credit and
  pressing the button just works.
- **The `backdrop_prompt` agent actually runs.** `refine_prompt` called
  `get_prompt("backdrop_prompt")` for a prompt that was never defined, so the
  optional prompt-writing stage silently no-op'd on every call and every
  backdrop used the deterministic template. The prompt and its schema now
  exist. It remains optional and out of band, still falling back to the
  deterministic draft on any failure — and it inherits the same hard rules the
  feature is built on: no people, no text in frame, and nothing bright or
  high-contrast in the centre, because that is where the words go.

## alpha4.1 — The room you are standing in, as a picture

Scene backdrops become a feature of the app rather than something drivable only
from a Python shell: a generated image of the room the player is in, rendered
behind the transcript.

The rule that shapes it is the same information discipline as everything else
here. The prompt is built from a **whitelisted spatial projection** — room
name, description, light, exits, damage — and never from perception prose, so
occupants are absent by construction rather than filtered out afterwards. A
backdrop therefore depicts the room **empty, always**, which also makes
per-room caching correct: a place is not a different picture because someone
walked into it.

### Added
- **Backdrop API** (`app.py`). `GET /api/turns/{id}/backdrop` resolves the room
  and the cache signature and never generates — a read has to stay free, since
  the frontend asks for whichever beat the reader is looking at. `POST` on the
  same path generates; concurrent callers wanting one signature wait on a
  per-signature lock and take the cache hit rather than paying twice.
  `GET /api/chats/{id}/backdrop/{sig}.png` serves the bytes, content-addressed
  and immutable.

  All of it under `/api/`, so the existing access-control middleware makes it
  host-only for free. A `StaticFiles` mount would have put an enumerable dump
  of every room in every story *outside* that middleware entirely — the paths
  are predictable, and anything not under `/api/` is waved straight through.
- **The chat backdrop** (`static/js/backdrops.js`). Piggybacks on the
  scene-mood `IntersectionObserver` rather than adding a second one, so the
  picture follows whichever beat is on screen and scrolling back through the
  log walks back through its rooms. Two layers cross-fade, and the image is
  decoded before the fade starts so it is never a fade to a blank layer. The
  scrim over the picture is fixed; the panel behind the prose is derived from
  the image's own Rec. 709 luma in the band the text column occupies, so a
  bright render pays for its legibility locally instead of dimming everything.
- **Image-model settings** (⚙ API › Scene backdrops). Image generation is a
  different API surface from chat completion, so it gets its own setting rather
  than an `agent_models` role. Off by default — every new room costs a
  generation — but already-generated rooms still show with it off, because
  those are free.

### Fixed
- **Scene mood was restyling the application** (two distinct causes, both
  reported from live use). `body[data-mood]` swapped `--acc`/`--acc2`, so a
  keyword read of the prose repainted sidebar buttons, the tab underline, focus
  rings and the modal header. Removing that was not enough: the chrome panels
  were ~.9 alpha over a `backdrop-filter` blur and went on sampling the tint
  underneath them. Surfaces sitting directly over the page background are now
  opaque, and the tint moved off a full-viewport layer onto `#msgs` itself — so
  "mood colours the story area only" is structural rather than a rule someone
  has to remember.
- **Occupants reached the image prompt through `rooms[].desc`.** The whitelist
  assumed that field was architecture. Dry-running a live 44-turn chat says
  otherwise: mapping writes populations into it where prose would name a
  character — *"Crew members and civilians gather here during off-duty hours,
  conversations murmuring at various tables."* It is now people-stripped on the
  way out, and the cache key hashes the **stripped** text, so writing someone
  into or out of a description is not a new picture. The filter matches "crew
  members" and not "crew" deliberately: the same chat's corridor reads "doors
  lead to crew quarters" and its turbolift scrolls "crew registration data",
  and both are things to draw.
- **A generated image was thrown away instead of shown.** The paint was gated
  on a sequence number that every scroll tick bumps, and generation takes tens
  of seconds — so an image was requested, paid for, written to disk, and never
  displayed. It now gates on whether that *picture* is still wanted, which is
  the right identity anyway: consecutive turns in a room share a signature.
- **A painted image was still invisible.** The layer sat at `z-index:-2` as a
  sibling of `#app`, on the reasoning that a negative stack level paints above
  the page background and below the app. Devtools showed the background-image
  and the `.on` class with nothing on screen. Replaced with an ordinary layer
  at `z-index: 0` and `#app` lifted to `1` — no negative levels anywhere.
- **The nano-gpt image catalogue listed nothing searchable.** The response is
  nested two levels (`{"models": {"image": {…}}}`) and stopping one short
  yielded a single row literally named "image". Fixed; the 44 image-to-image
  models are also dropped, since a backdrop is generated from text alone and an
  edit model can only fail at generation time. Rows now carry a price and the
  model's own resolutions — sizes are per-model and not always `WxH`
  (`landscape_16_9`, and `1024*1024` with an asterisk), and offering none is
  how you save a model that then fails.

### Changed
- **Scene life is visible in the pipeline UI.** The stage is named after the
  path it will actually take — "Scene life · manager (ambient|full)" vs
  "Background · presence reaction" — and the sub-agents that run *inside* it
  (`blurb_mint`, `scene_life`, `backdrop_prompt`) are named too, so a stage
  that spends a whole extra call no longer looks stuck.

## alpha4.0.4 — A ship's computer is a voice, not a bystander

Findings from auditing a 39-turn live chat ("The Doctor — Hinami ⎇14 ⎇17 ⎇16 ⎇23").

**On cost, since that audit started as a billing question:** the engine is not
the cost source. 43 interaction-loop rounds across 38 turns (~1.1/turn),
`background_react` fired on 1 of 38, zero warnings, a 15.6KB scene with 8 rooms
and 9 entities. ~350 LLM calls for the whole chat. A provider reporting 23M
tokens for ~3 turns works out to ~850k per request — impossible for a single
inference, and consistent with upstream fan-out from a `multi-agent` model that
every role was pointed at via one `default` entry.

### Added
- **Bodiless voices** (`schemas.py`, `scene.py`, `commit.py`,
  `agents/perception.py`, `prompts.py`). A ship's computer, station AI or
  building PA is a voice with no body and no room. Live play had the Enterprise
  computer as `kind=agent` **positioned in `enterprise_ten_forward`**, so the
  engine believed the ship's AI existed in one room; walk to Deck 14 and it was
  not present. The alternative was not expressible either — `USS Enterprise D`
  carried `interior_rooms=[]` and every Enterprise room had
  `parent_entity=None`, so there was no containment to scope ubiquity against.

  Rather than build vessel-scoped presence, such an entity is exempt from
  position entirely: `SceneEntityDef.ubiquitous`, plus a narrow
  `UBIQUITOUS_KINDS` so a model that omits the flag but names the kind still
  gets it right. The Director voices them directly (new BODILESS VOICES clause),
  they are never tracked as background presences, and perception treats them as
  present everywhere.

  That last part was nearly a silent failure: `spatial_rel(None, room)` yields
  `barrier='unknown'`, so `hear_level` returns `none`. Without the exemption the
  Director could voice the ship's computer and **no perceiver would hear a
  word**. A test documents the trap directly.
- **Promotion thresholds are per-chat authorial config**
  (`scene.promotion_config`, world key `promotion_thresholds`): `dialogue`,
  `mention`, `auto_dialogue`, clamped 1–50, defaulting to the previous
  constants. How many lines a bystander must speak before the engine offers it a
  mind is pacing, not law.

### Fixed
- **Exits could point at rooms that do not exist**
  (`commit.prune_dangling_exits`). The merge dropped edges to rooms it had just
  *removed* but never checked that an edge's target existed at all, so a model
  naming a room it never defined committed a permanent broken exit — found live,
  a janitor closet with an exit to `enterprise_corridor` while only `_deck10`
  and `_deck14` existed. Not cosmetic: `spatial.py` treats `adjacent` as the
  authority on what leaves a room, so it was offered as a real exit and pathing
  counted an unreachable neighbour. Now dropped with a warning.
- **Opaque entity ids produced garbage display names** (`schemas.py`), a
  weakness in alpha4.0.2's own fix. That release derives a name from the entity
  key; live scenes key some entities as hex (`10ae6b6a11324780`), which would
  have become the player-visible name `10Ae6B6A11324780` *and* a lookup key.
  Opaque ids now derive nothing and fall back to the kind ("Vehicle", "Object")
  — still valid, so the turn survives, but honest.

### Not fixed (recorded, deliberately)
- Two one-way exits in that chat (`turbolift_car → corridor_deck10`,
  `tardis_console_room → janitor_closet`). Auto-adding reciprocals would invent
  world facts, and a one-way passage is legitimate fiction.
- Ship-AI *character cards* — an entity with real interiority scoped to a
  vessel — remain deferred. That needs vessels to actually claim their rooms.

## alpha4.0.3 — Prompt caching reaches the provider you actually use

### Fixed
- **A Claude model behind nanogpt never cached its system prompt**
  (`providers.py`). An Anthropic model reached through an OpenAI-compatible
  aggregator needs an explicit `cache_control` breakpoint — the caching is
  Anthropic's, not the aggregator's, so the plain-string system message every
  other provider takes produces no breakpoint at all. That marking was gated on
  a hardcoded `("openrouter",)` allowlist, so the same model through **nanogpt**
  — the provider this engine is configured with — reprocessed its entire system
  prompt on every single call, with no fix short of editing the file.

  nanogpt joins the built-in list, and the list is now extensible from settings:
  `prompt_cache_allow` opts a provider in by name or kind, `prompt_cache_deny`
  opts one back out and wins over both. `FICTION_ENGINE_PROMPT_CACHE=0` remains
  the all-providers kill switch.

  It stays an **allowlist** deliberately. Allow-by-default was tried and
  reverted: a provider that *rejects* an unrecognized `cache_control` key fails
  the turn, which is a worse outcome than simply not caching.

### Notes
- **Caching is not Anthropic-only.** Anthropic models are the only ones needing
  an explicit breakpoint; every other provider (GLM, GPT, DeepSeek …) does
  automatic prefix caching with no opt-in, and the engine already reads the
  result from `prompt_tokens_details.cached_tokens`. Live runs on
  nanogpt + `glm-latest` show it working — e.g. a perception call with 5,791
  system tokens served 3,423 from cache.
- **Only the barebones prompt is cached, never the turn's input.** Just the
  static per-role instruction from `get_prompt(role)` is ever marked; the
  per-turn payload goes as a plain string on both dialects. Marking volatile
  input would write a fresh cache entry every turn and never read one back.
  Now covered by tests so it cannot regress silently.

## alpha4.0.2 — An entity's key already names it

### Fixed
- **A turn could die because the Director omitted a field its own dict key
  carried** (`schemas.py`). Reported from live play with `glm-latest` as
  Director:

  ```
  Pipeline error: director_resolve failed JSON validation:
  state_diff.entities.sake_carafe.name: field required;
  state_diff.entities.computer.name: field required
  ```

  `entities` is `dict[str, SceneEntityDef]`, so the key *is* the identifier and
  a model reasonably declines to repeat it as `name`. `SceneEntityDef.name` was
  required, so the whole beat was rejected — losing the resolution, the
  dialogue, and every other entity in the diff over a redundant field.

  The name is now recovered in `preprocess_llm_output`, the same place the
  `dialogue_log` repair already turns a bare `"Speaker: quote"` string into a
  valid entry. This is not guesswork: the *same chat's* successful turns show
  the model performing exactly this transformation itself, so the derivation
  reproduces its own convention — `sake_carafe` → "Sake Carafe",
  `guinan_entity` → "Guinan", `turbolift_car_entity` → "Turbolift Car", with
  deliberate acronyms (`LCARS_panel` → "LCARS Panel") preserved rather than
  title-cased.

  An explicit `name` always wins; common aliases (`label`, `title`,
  `display_name`) are accepted the way `dialogue_log` accepts `quote`/`text`;
  and a blank name is replaced rather than kept, since an empty string
  satisfies `name: str` while leaving the entity invisible to every
  display-name reader (`commit.track_background_presences`,
  `agents/background._name_to_entity_id`).

  Applied to `director_resolve`, `resolve_repair`, `director_establish` (which
  carries entities at top level, not in a `state_diff`), and `mapping_stage`'s
  `scene_patch`. The last never failed validation — `ScenePatch.entities` is
  untyped — but a nameless entity still reaches the scene, where readers key
  display name to entity id, so it was silently unreachable rather than loudly
  broken.

  Pre-existing since the schema was introduced; not a regression from alpha4.0.

## alpha4.0.1 — The scene manager gets a switch

alpha4.0 shipped `background_config` with **no route and no UI**, so `scene_life`
was only reachable by writing world KV by hand — which is exactly how both demo
runs had to enable it. Nobody using the app could turn the feature on.

### Added
- **Background life controls in the Dialogue config modal** (`app.py`,
  `static/js/settings.js`, `tests/test_background_config_route.py`).
  `GET`/`PUT /api/chats/{cid}/background_config` exposing `scene_life`
  (off / ambient / full), `max_managed` and `max_reactors`.

  They sit beside **Dialogue config** rather than **Genre & style** because
  these are simulation dials — who gets to speak and act — the same family as
  the `allow_npc_to_npc_dialogue` toggle already there. The style guide keeps
  the other half of the feature: how invented extras *sound*, including the
  §3.8.1 canon licence that produced the correct TNG senior staff from station
  names alone. The panel says so, and points at Genre & style.

  The copy explains the levels in terms of what they cost rather than their
  internals: *ambient* is described as the manager only ever seeing what
  everyone present already heard, *full* as also seeing lines aimed at one
  person and relying on the model to honour who heard them. The known
  auto-promotion gap is called out in the panel itself rather than left in the
  changelog, since it bites whoever switches this on.

  Values are clamped server-side to the same hard caps the stage enforces
  (`max_managed` ≤ 8, `max_reactors` ≤ 3) so the UI cannot store a number
  `agents/background.py` will silently ignore, and an unrecognized level is a
  400 rather than a silent fallback.

Defaults are unchanged: an untouched chat still reads `scene_life: "off"`.

## alpha4.0 — The room is alive when you are not looking at it

Background extras were the one place the engine lost to plain single-context
LLM roleplay, and the cause was not an oversight: **the engine applied its
central information discipline to the tier with nothing to protect.** A
bystander with no sheet, no memory and no hidden state gains almost nothing
from per-presence isolation, while the isolation costs exactly what makes a
crowd feel inhabited — an ensemble improvised in one context.

This release adds an opt-in scene manager that recovers that, fenced inside a
partition that keeps the discipline where it pays. Everything here is **off by
default** (`background_config.scene_life`); with it unset, behaviour is
byte-for-byte what it was.

Design: [`docs/BACKGROUND_LIFE_DESIGN.md`](docs/BACKGROUND_LIFE_DESIGN.md).
Live evidence: `demo/tavern_scene_life/` and `demo/trek_bridge_scene_life/`.

### Added
- **The scene manager** (`agents/background.py`, `prompts.py`, `schemas.py`).
  One batched call voices a whole location's populace per beat instead of one
  LLM call per presence. It is selected by `scene_life`: `off` (default),
  `ambient`, or `full`.

  The cardinal rule is **voice batched, write unbatched**. This is not a claim
  that models cannot separate who-knows-what in one context — they can, and the
  payload asks them to, with per-presence `full`/`fragment`/`none` audience
  tags. It is about error economics: at any reliability *p*, a slip in *speech*
  decays (one odd line, gone next turn) while a slip written to *storage* is
  re-read every subsequent turn and preserved by every future compaction.
  Storage never sees a shared context window.

  Perception is two layers with distinct roles. **Admission control** is the
  guarantee: concealed lines, lines concealed from every managed presence, and
  (at `ambient`) any divergent event never enter the context at all, so no
  prompt discipline is protecting them. **Annotation** is fidelity, not safety.
  At `ambient` the manager's context holds only what every managed presence
  shares, making cross-contamination impossible rather than mitigated.

  Selection is by room, not salience. `managed_presences` hands over the
  populace of the player's ambient scope; the manager decides for itself who
  acts. Every condition in the old gate mirrored the player, which is what made
  extras feel reactive rather than alive.
- **Frozen personality blurbs** (`§3.8`). A `manner`/`trait`/`tell`/`look`
  sketch minted once per presence and never rewritten. Immutability is the
  feature: recognizability across turns is what a re-derived personality cannot
  give. Minting is batched — safely, and *because of* the rule above rather than
  as an exception to it: a blurb carries no perceptual content, so there is
  nothing to cross-contaminate. Blurbs are style-guide governed, which is where
  location theming is actually decided.
- **Claimed-not-established lore** (`background_claims.py`). Background
  presences invent small world facts through their people — roughly one proper
  noun per turn in live play. That is kept, because suppressing it costs most of
  the texture, and made safe by recording it as **hearsay the Director
  ratifies**: the same treatment the Player Authority Contract already gives a
  player's claim about another character. Neither owns objective causality.

  The failure being designed out is *"the engine forgot it said this."* With a
  claim recorded, all three outcomes are ordinary fiction: ratified (canon),
  contradicted (the speaker misremembered — and because the claimant is
  recorded, the world can show it), or expired (it was tavern talk).
  `claimant_credence` derives trust from the frozen blurb, so an unratified
  claim is safe to leave floating: the fiction has already signalled how much to
  believe a rambling old man.
- **A `place` block** in the background payload (`§3.7`): room name and
  description, location, nesting-aware ambient location, time, genre and style.
  Previously a presence's entire sense of place was a bare room id.

### Fixed
Six defects, all found by *running* the engine rather than by the suite.

- **A registered character could be handed to the stateless manager as
  furniture.** The Director writes "Captain Jean-Luc Picard"; the roster holds
  "Jean-Luc Picard". Exact-casefold comparison missed it, so a character with a
  sheet, memory and psychology was tracked as a background presence and offered
  to the manager on five consecutive turns. The model declined every time —
  precisely the "compliance holds until it doesn't" case this codebase keeps
  converting into a structural guarantee. New `commit.strip_name_titles` /
  `name_in_roster`, applied to tracking and selection.
- **Co-presence lookups missed nearly every presence.** Scene positions are
  keyed by opaque entity id (`barkeep`) while presences are tracked by display
  name (`The Barkeep`), so only one of five extras in a tavern ever qualified.
  `_presence_room` folds through the entity map, mirroring the fold
  `track_background_presences` already does in the other direction.
- **Concealed content could reach the manager through the Director's prose.**
  Admission control covered `dialogue_log` but not `resolved_event`, which is
  authored from the omniscient objective frame and can restate a whisper
  verbatim. The per-presence path had always redacted this;
  `_redacted_resolved_event` brings the manager path in line.
- **A bare rank was recorded as invented lore.** "...profiles, Captain." created
  a claim on `Captain`, which then auto-ratified because the word is everywhere.
  Fixed by `is_title_only`, with title-stripping so "Worf" resolves to the
  established "Lieutenant Worf".
- **Hyphenated names split** in the proper-noun scan ("Captain Jean" + "Luc
  Picard"), matching nothing.
- **Long refs were unmatchable ratification keys.** A presence self-declared a
  whole sentence; the Director visibly acted on it but the ref shared no string
  with the prose, so an adopted claim stayed hearsay and would have expired as
  never established. Refs are capped and the prompt asks for a short referring
  phrase.

### Known gaps
- Ambient conduct still accrues `dialogue_turns`, so auto-promotion should be
  disabled alongside `scene_life` until a separate counter lands
  (`AUTO_PROMOTE_DIALOGUE_THRESHOLD` is 3).
- A frozen `tell` can become a catchphrase — one presence performed hers on
  every turn she acted. The prompt fix (available colour, not a required beat)
  is specified in `§3.8` but not yet applied.
- Ratification is one-sided: a claim the Director *rejects* is indistinguishable
  from one it ignored. An explicit `contradicted_claims` would let a later beat
  show a presence was wrong.
- The manager does not exclude presences the Director already voiced this beat.
  It behaved correctly across both live runs, but nothing enforces it.

## alpha3.3 — Nobody speaks for the player, and nobody skips the person the scene is about

Two authority failures and one authoring feature. Both failures were found by
*running* the engine rather than by the suite, and both had the same shape: a
stage quietly doing something on someone else's behalf.

### Fixed
- **The Director invented player actions** (`agents/director.py`,
  `agents/common.py`, `prompts.py`). Reported from live play as "perception is
  inventing player actions and also out of ordering events". Perception was
  innocent -- it rendered faithfully what it was handed. `resolved_event` was
  giving the player conduct they never declared: on a speech-only beat
  ("Well... I love the confidence at least. Let's get going?") it had them take
  a water bottle, drink from it and nod; when they merely ASKED "I hope you
  don't mind if I lean on you", it performed the leaning for them.

  The reported out-of-order symptom was the same bug's shadow, not a second
  defect: the engine enacts the act, the player then declares that same act a
  beat later, so the moment happens twice and the scene doubles back.

  The line drawn is **elaboration vs invention**. Rendering a DECLARED act with
  as much physical detail as the prose wants is the Director's job and is never
  touched; only an act arriving from nowhere is. A new prompt rule (PLAYER ACT
  AUTHORITY -- ELABORATE, NEVER INVENT) names the trap directly: **a request is
  not an act.** An NPC may offer, hold out, brace or wait; the player accepts on
  their own turn. Enforcement is a bounded correction retry on `director_resolve`,
  kept only if it reduces the violation count, with anything surviving attached
  to the step as `player_act_warnings` so it stays visible.

  This is the action-side counterpart to the alpha3.2.1 player-SPEECH guard,
  which covered the player's words but left their conduct open.
- **A beat could end with the character it was about never simulated**
  (`agents/loops.py`, `prompts.py`). Found by the v3 demo run. The Director
  flagged Dr. Vorne in `flow.tom_triggers`, Picard's own line handed him the
  floor ("Doctor, I would hear your answer as well"), and the interaction loop
  then ended the beat after a single call with 5 of 6 permitted calls unused.
  Vorne's agent never ran, and the narrator rendered "He does not speak" as a
  characterful refusal no agent had chosen.

  The cost compounds: appraisal -- and therefore the `goal_impacts` drive strain
  accrues from -- exists only for characters that actually ran. Skipping the
  focus character on precisely the beats aimed at his drive pinned his strain at
  0.0 and made a rupture unreachable however correct the accrual arithmetic was.
  This sits ABOVE the v2 audit's W1: alpha3.2 fixed the maths, this supplies the
  input it was waiting on. Both of the loop's early exits now give a flagged
  focus character one call before the beat ends.
- **The player's own name in the player's own view** (`agents/perception.py`,
  `agents/common.py`, `agents/narration.py`). Perception's "last overt action"
  backstop appended the acting agent's `observable` surface verbatim to every
  perceiver's view, and those surfaces are authored in third person naming
  everyone else -- so the player's name landed in their own view at zero
  temperature and the narrator copied it through. Two floors: the receiving
  perceiver's own name is rewritten to second person before injection, and prose
  naming the player while `narration_person` is second/first raises an
  enforceable narrator warning. Both stay quiet on quoted dialogue and on
  third-person narration, where naming the player is correct.

### Added
- **Genre and standing generation instructions** (`scene.py`, `prompts.py`, UI).
  A per-chat style guide -- genre, tone, director notes, mapping notes, and
  things to avoid -- so rooms minted mid-play match the world's theme instead of
  drifting to a generic register. Reachable from a new **Genre & style** toolbar
  panel.

  **Self-determination stays the default and first-class:** an unset guide, or an
  explicit "self-determine" genre, carries no genre at all, leaving the payload
  identical to before this existed. The engine already infers a register from
  scenario and lore, and an author who hasn't decided shouldn't be made to
  invent one. The parts compose -- leave the genre to the engine while still
  pinning "every room has exactly one working light".

  Scope is generative stages only: `director_establish`, `director_resolve` and
  mapping receive it. `director_interpret` does not -- it reads what the PLAYER
  declared, and a house style there would colour how their own words are read.
  Character agents and perception are excluded on the principle that keeps them
  separate elsewhere: a character's manner comes from their authored voice, and
  one house style in every head would make every mind sound like the narrator.

### Notes
- Both prompt-level rules state the same hard limit: a style guide is a STYLE,
  not a fact source. It never overrides canon, an established room, a player
  declaration, or plausibility, and is never quoted back into output.
- On Claude Opus, three role prompts still sit below Anthropic's 4096-token
  minimum cacheable prefix and will not cache however correct the breakpoint is
  (carried over from alpha3.2.2). Sonnet-tier minimums are lower and unaffected.

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
