# Unbuilt work — World, space, and physical state

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-2"></a>

### 1.2 Nothing validates the geometry of an asserted doorway

**Found:** live, alpha 6.0 session. **Do this before any multi-location story
with several characters.**

The scene merge accepts an adjacency a model asserts, with no check that the two
rooms *could* be adjacent. Measured: `r0204 <-> r0303` in the maze scene — a
diagonal in a grid maze, geometrically impossible by construction — sat in the
world model for hundreds of turns and was walked as a real doorway.

`spatial._shield_standing_bearings` protects the bearings of *existing* edges.
Nothing guards the creation of a *new* one.

Why it matters beyond mazes: a Director inventing a connection between two
locations is what happens in a village or a household when a model reaches for a
shortcut, and a fabricated doorway becomes part of every character's map and
every route computed over it. The maze has coordinates to check against; a
general scene may not, so the honest fix may be "require a stated basis for a
new edge" rather than a geometric test.

**Narrowed 2026-08-19.** Reciprocity landed: a NEW passable edge whose standing
reciprocal reads `wall` is refused unless the same diff re-declares that side
passable — the mirror of `_shield_standing_passage`'s two-sided-sealing rule,
scoped to `wall` only, since a standing `closed_door` is openable from either
side and `one_way_window` asymmetry is deliberate vocabulary.

A room-EXISTENCE check was landed and then removed, which is worth recording so
nobody reaches for it again: `tests/test_spatial.py` pins a live west-wing
mapping flow where a corridor's edge is minted BEFORE the room exists, and
`neighbor_map` tolerates dangling edges by design. An existence rule has to wait
for room-and-edge minting to become atomic.

What remains is this entry's own conclusion — a stated BASIS for a new
adjacency between known rooms (`authored|walked|opened|generated_map|asserted`),
with the orchestrator rather than the model stamping the trusted values. That is
a schema and prompt change across the mapping and spatial specialists.

**Narrowed again 2026-09-04, from the other end.** The layout lint
(`world/spatial_lint.room_layout_lint`, behind the `world/spatial.py` facade;
§ 2.37) reads a scene's bearings and extents AFTER the merge and reports where
they cannot all be true -- two sides of one doorway naming bearings that are
not opposites (`reciprocal_bearing_disagrees`), a set of bearings that cannot
be embedded on a plane (`rooms_overlap_when_placed`) -- once as a commit
warning and always in the Room's `inspect_contradictions["layout"]`. So an
impossible adjacency is now visible the beat it lands rather than when it is
walked. Rows, never fixes, and only over edges that carry a bearing (578 of
923 live exits carry none); nothing refuses the edge at the merge, and the
conclusion above -- a stated BASIS for a new adjacency -- is unchanged.

<a id="unbuilt-1-10"></a>

### 1.10 An entity's free-text `state` never ages, and a mind reads its own stale copy (S3-A8)

*(Absorbs §1.24's byte-identical bullet and the alpha 6.3 physical-ledger
residuals' ageing bullet, 2026-08-19.
It was one defect written three times in three sections, which is most of why
it read as three small things.)*

Nothing reconciles an entity's free-text `state` / `description` against the
beat's resolution, and nothing retires a key the beat did not touch. A body's
`posture` / `activity` / `held_items` blob is overwritten only when a model
happens to rewrite it; `"breath": "caught"` and
`"voice_quality": "held_breath_steadying"` persist verbatim until it does.
`contacts` was the worst case and was fixed at the source — this is the rest of
the same disease.

**It is a READ-BACK LOOP, which is what makes it the worst thing on this list.**
`agents/perception.py` composes `composer.body_state_percept(entity_state)`
(`posture`, `activity`, `held_items`, channel `interoception`, source "you"), so
a stale blob is not merely bad prose: it is what the mind believes about its own
body, and it feeds the next declaration and the memory of the beat. A mind that
lowered its wrench still reads *"raised to chest level, aimed forward into the
dark"* as what it is doing now.

**Measured 2026-08-19.** The engine's own detector fires on **62 of 306
instrumented commits (20.3%), 122 instances** — subjects overwhelmingly the cast
mirrored as scene entities (Hinami 44, Tamamo 32, The Doctor 25). Of 599
`world_entities` rows, 408 (68.1%) carry a non-empty `state` dict; walking every
checkpoint in `chat_id, turn_idx` order and hashing each entity's `state` gives
**2,074 unchanged runs across 425 (chat, entity) pairs — median 1 turn, p90 14,
max 138, and 172 pairs hold a run of ≥15 turns byte-identical.**

An earlier "skip the update" fix was **reverted** as durable corruption;
`persist/commit_entities.py` now warns `"possible stale clause (S3-A8)"` and
commits the blob anyway, pinned deliberately by
`tests/test_pipeline_audit_leak_gaps.py` as *a signal, not a fix*. **The
reverted fix is the record of what not to do.** What this wants is an
ageing/reconciliation rule for free-text state keys, not another guard. No
schema change. Root cause — free-text state blobs with omission-only
reconciliation and `_PROTECTED_STATE_KEYS` — untouched.

**Narrowed 2026-08-19.** `breath` and `voice_quality` — the two keys measured
persisting verbatim — now expire on every merge unless the incoming diff
re-asserts them, across all entities including ones the diff never mentions.

**Narrowed 2026-08-25, because that rule was defeated by the cheapest model
behaviour there is.** Expiry counted a re-emission as an assertion, so a
specialist echoing its whole state blob back verbatim kept every momentary key
alive forever. Measured on chat 88 turns 53-67: the hand owning `entities`
re-emitted the blob nearly every beat, and `throat_action` set at turn 56 was
still standing at turn 67 — thirteen beats after the act it named. Two rules
answer it, both in `world/spatial_merge.py`:

- **An echo is silence.** A byte-identical re-emission of a value that was
  ALREADY ASSERTED no longer counts as re-assertion; only a CHANGED value
  does. The cost is real and accepted: while a model keeps restating a
  momentary fact word for word, the key stays expired — it does not come back
  and then go again. For the momentary vocabulary, byte-identical across two
  beats is stale by construction, and a genuinely continuing dynamic has its
  own channel that persists through silence by contract
  (`contact_action_ops`). The `_merge_entity` "a schema default is silence"
  analogy is weaker than it reads — a default is UNCHOSEN and an echo was
  emitted — so the 13-beat measurement is what carries the rule, not the
  analogy.

  **ASSERTED, not STANDING — corrected 2026-08-25, before it shipped.** The
  first form of this rule compared the incoming value only against the value
  standing in the scene, and expiry deletes exactly that value: the next
  identical echo found nothing standing, re-established the key, and the echo
  after that expired it again. Measured on that form, one diff merged six
  times running gave `gaze: downcast` / gone / `downcast` / gone / `downcast`
  / gone — a momentary key blinking forever, on precisely the
  verbatim-re-emission input the rule exists for, and worse for every reader
  of the committed blob than the stale value it replaced. So a value
  suppressed as an echo is remembered under the scene's
  `expired_entity_state`, and every later echo of it is silence too. The
  memory lives only as long as the echo run: a beat that says nothing about
  the key releases it, so a genuine re-assertion after a silence is still an
  assertion, and suppression is never a standing ban on a word. A scene whose
  bodies are not mid-echo carries no such key at all.
- **The vocabulary is a stated class, not a list of names.** `state` is open
  free text, so an allowlist can only ever name the momentary keys some story
  already wrote. It is now the exact keys `breath`, `breathing`,
  `voice_quality`, `expression`, `gaze` plus the process-suffix families
  `_action`, `_motion`, `_sensation`. Re-measured over all 77 stored scene
  blobs on 2026-08-25: the predicate captures 31 of 1,270 stored
  key-occurrences under nine distinct names (27 of them newly reachable) and
  none of the other 370 distinct keys — every one of those a configuration
  (`power_state`, `lock_status`, `held_items`, `posture`).

Two residues stay open, deliberately. `_register` is NOT a process family: a
till or a ledger named `x_register` is a thing, not a reading, so that family
fails OPEN — as does any momentary key without a process-shaped name (a bare
participle, an anatomy noun, `taste_register` in the corpus). Failing open is
the correct direction, because a lingering momentary key is stale prose the
next beat overwrites while a configuration key wrongly called momentary
silently DELETES authored state. The general answer for the residue is a
declarative transience marker on the entity-state schema — the model saying
whether a key is momentary — which is a schema change with its own
silence-default question and is not taken here.

`activity`, the sharpest read-back key, deliberately does NOT expire yet:
`tests/test_body_position.py` pins it as load-bearing standing state, and a
first attempt at expiring it broke that test. Which of the two contracts wins is
a product decision and has to be made before the key moves. `posture` and
`held_items` stay durable by design — those are the S3-A8 reconciliation
problem, not an ageing one.

The reviewer's proposed `raise` on an undeclared key was declined: entity
`state` is deliberately open free text that models write into, and
`_ENTITY_DEFAULT_FIELDS` establishes the opposite doctrine — an unlisted key is
copied, silence is never an erasure.

<a id="unbuilt-1-20"></a>

### 1.20 A body's room changes with no warrant, and the scene never recovers

**Found 2026-08-02**, investigating chat 58 ("Run! ⎇10 ⎇20"), where the final
turn's perception made no narrative sense and `director_resolve` produced
incoherent output on strong models. Shelved deliberately: the guard is easy to
write and easy to write WRONG, and getting it wrong blocks legitimate movement
in every story.

Nothing validates that a position change was earned. `state_diff.positions` is
merged as written, so the Director can relocate a body on a beat where nothing
moved, and every later beat inherits it.

Measured, from each turn's own `state_diff`:

| turn | player input | positions written |
|---|---|---|
| t23–24 | throws a rock, ducks | everyone `alley_room` |
| **t25** | *"You pick up a rock again and chuck it… at the Dalek's eyestalk"* | **Doctor + Hinami → `street_outside`**, a room minted this turn |
| t26 | rolls behind a dumpster | Dalek → `street_outside` |
| t27 | dashes for the TARDIS | Hinami → `alley_room`; the other two stay |
| t28 | charges in, slams the doors | Hinami → `tardis_console_room` |

Nobody moved at t25. The map itself is fine — `tardis_console_room —(closed
door)— alley_room —(open)— street_outside` — and the TARDIS is in the alley.
The POSITIONS are wrong, and the whole fight is written as happening at the
TARDIS doors while two of its three participants stand a room away.

Everything downstream follows, and none of it is separately broken:

- `spatial_rel(tardis_console_room, street_outside)` is `separated`/`far`, so
  the Doctor's `normal`-volume lines reach Hinami only through
  `_dialogue_hear_level`'s by-name floor. That floor is NOT the bug: put the
  Doctor where the fiction puts him and `hear_level(closed_door, "normal")` is
  `fragment` — a muffled voice through slammed doors, exactly right.
- The Doctor declared *"steps between Hinami and the advancing Dalek"* and
  *"Hinami—behind me, now!"* for someone two rooms away behind a door she had
  just slammed. Correct conduct given his view; the view was wrong.
- `director_resolve` is then asked to resolve one continuous fight between
  three bodies the geometry says cannot see, hear or reach each other. There
  is no coherent resolution of that input. A stronger model returns more
  confident nonsense — which is what "failing even on strong models" looks
  like from the outside.

The scene also contradicts itself in prose by t28: `alley_room.desc` says "a
blue box appeared and vanished, leaving only empty air… The TARDIS is no
longer here" while `positions` still holds the TARDIS entity in `alley_room`,
and `tardis_console_room.desc` says the doors "stand sealed" while its own
`notes` say they "now stand open". And the Dalek's position key changed from
its entity uid (t23–24) to its name (t26 on), orphaning the entity record —
§1.17's fragmentation, in `positions` this time rather than
`background_presences`.

**The rule wants to be:** a body's room may only change with a warrant this
beat. **Why it is not written yet:** there are three warrants and only two are
legible. The player's `director_interpret.movement.to_room` is explicit, and a
character's declared locomotive action is inspectable — but Director-driven NPC
movement (someone walks in, someone flees) has no signal beyond the resolve's
own prose naming them moving, which is exactly the fuzzy test that would make
the guard either useless or a blocker on ordinary play. Prove that third
warrant before writing the guard; a check that silently pins NPCs in place is
worse than the drift it replaces.

Two consequences of the same investigation ARE fixed, because they hold on any
geometry: a body with no sensory channel is not described to a perceiver at all
(`visual_level_between` is consulted before any sentence exists, so the
composer mints no presence, pose or appearance percept for it — the guard moved
from the prose to the IR, and `_strip_unreachable_bodies` is gone with the rest
of the repair-over-prose layer), and `_subject_opener` (a leading article
belongs to the prose, not the name, so a body registered "A Dalek" is caught
when the prose writes "The Dalek's"). See `Design.md`.

**Absorbs §1.14 (2026-08-19)**, which said the same thing one body narrower —
`docs/archive/PROPOSAL_2026-08-06.md` already recorded them as one defect written
twice. §1.14's half: `director_resolve`'s passable-route backstop guards
`state_diff.positions` only when interpret DECLARED a movement, so a resolve
asserting a position on a beat with no declared movement reached commit with no
route, adjacency or authority check. Two-thirds of that headline is now paid by
`_unreachable_position_writes` (`agents/director_movement.py`, wired at
`agents/director.py`). What survives is the same unwritten rule as above, plus
the framing worth keeping: `movement` is the channel through which the player
says where they are going, and a stage that can relocate the player without it
is **authoring player conduct** — the boundary `_check_player_act_authority`
defends for speech and action, unguarded for position. The containment check in
`_guard_approach_is_not_arrival` is the start of the answer, not the whole of
it.

**Measured reach, 2026-08-19:** on turns played on or after 2026-08-01, a body's
room changed with no `movement.to_room` and no locomotion verb anywhere in the
declaration on **12.2%** of beats (91 of 745). That classifier deliberately
over-credits warrants — any locomotion word anywhere counts — so 91 is a FLOOR
and the true figure is higher by an unknown margin.

<a id="unbuilt-1-28"></a>

### 1.28 Residuals from the contact-sensation work

Landed 2026-08-04: `spatial.contact_sensation` and
`agents.perception._deliver_standing_sensations` (see `Design.md` § A standing
contact is a continuous percept, tests in
`tests/test_continuous_contact_sensation.py`). These are what the same
investigation found and did not close.

- **Partial interior contact still does not populate full containment.**
  Contact sensation no longer asks free-text `manner` to carry two axes:
  `relation: surface|interior` and `motion: settled|moving` now independently
  drive rendering, with backward-compatible derivation for old rows. That
  closes the perception ambiguity, but an interior contact still does not
  populate `contained`, so the §1.24 enclosure-direction work does not fire on
  it. Whether it should remains a design question: partial containment is not
  the same as being sealed inside something, and the two remain separate code
  paths describing overlapping physical situations.

  **The third path now exists and is routed** (2026-08-25). There were always
  three, not two: the ledger form (`contained`), the contact form
  (`relation: interior`), and the PLACE form -- a room whose `parent_entity`
  is the body around it. Nothing converted anything into the third, so an
  enclosure a beat declared stayed a one-line ledger entry and its occupant's
  position derived, every merge, to the holder's own room.
  `spatial.place_enclosed_bodies` closes that: a `mode: interior` record plus
  a holder that HAS interior rooms becomes a real position inside them, and
  contact hygiene admits an enclosure-joined pair so the touch channel across
  the boundary survives the move. A holder with no interior rooms is
  untouched. The migration was MEASURED rather than asserted: all 77 stored
  scenes were re-merged with an empty diff on the branch and on `main` and the
  results compared whole -- 76 byte-identical, and the one that differs is the
  story that already stands in this shape, where a surface contact between a
  body and the body it is inside now survives room hygiene instead of being
  severed. The follow-ons below are what that landing did not close.
- **A composed view carries a room's NAME and NOTES but never its `desc`.**
  `composer.environment_percept` takes `room_notes` and no description, so
  the authored sentence that says what a place looks like reaches the
  narrator (which reads the scene directly) and never a character agent.
  Mostly invisible while a view only ever described the room underfoot --
  the notes carry the orientation and the furniture layer carries the
  things. It became visible with the opening percept (2026-09-04): a glance
  through a doorway delivers the far room's name, notes, light and
  cone-capped furniture, and the one field that would carry "impossibly
  larger on the inside" is the one no view has. Whether `desc` should be
  delivered at all is a real question -- it is authored prose about a place,
  not a percept -- but it should be answered rather than left as an accident
  of which fields the percept happens to take.
- **A non-body inside a place-form interior is in no view.** `contents_of`
  answers the carry ledger for anything; `interior_occupants` answers the place
  form for BODIES only, because it feeds prose that says an occupant "goes
  where you go" and because `positions` keys objects and fixtures by entity id
  -- an engine handle, which is not a name anybody in the fiction has heard.
  So a lamp dropped inside a body-place is currently in nobody's account of
  anything: the holder cannot see into its own interior (the membrane is opaque
  in both directions, correctly) and is told nothing about what is in there
  that is not a body. The fix is a percept for the objects of an interior room,
  not a widening of this one function.
- **A story-written mint never gets the card's chain, and has to grow one.**
  `replace_engine_minted_interiors` swaps the engine's own one-room mint for
  an authored chain only where that room still carries EXACTLY the key set
  `_mint_minimal_interior` writes. Anything the story has since written on it
  -- a description, a crossing time, a declared `exposure` or `size`, a second
  room -- is lived topology the card does not get to overwrite, so the
  replacement skips and the story grows its chain station by station through
  `materialize_named_stations` or the spatial specialist's `rooms` channel.
  Measured live 2026-08-25 against a scratch copy of the author's corpus with
  the card filled: chat 90's stub is replaced and its occupant advances on the
  clock from the first silent beat; chat 91's carries `exposure: "enclosed"`
  and `size: "tight"` and is left standing, correctly and permanently. What is
  missing is an author-facing way to say "this stub was the engine's guess,
  take the card's chain instead" -- a per-holder re-derive, which is an
  authoring surface rather than a merge rule and must not be a looser trigger.
- **A persona cannot author an interior.** `stamp_authored_interiors` walks
  the CAST, and a player persona is not in it, so the field is deliberately
  absent from `default_persona_data`/`normalize_persona_data` and has no
  persona accessor -- a field with no reader is what `llm/schemas.py` deleted
  29 models over. `tests/test_card_interior_spec.py` pins the absence, so a
  reader cannot appear without the field appearing with it.
- **A non-body holder never gets an engine-minted interior.** Not a taxonomy
  preference: `sync_entity_interior_rooms` and `infer_body_enclosures` are
  both body-scoped, so a minted crate or lift-car interior is never indexed
  and never defaulted opaque, `apply_transit_dock_edges` derives an
  `open_door`, and an occupant `containment_hides` was concealing becomes one
  visible from the room outside -- information EXPANSION. Serving a container
  the same way needs the non-body enclosure default first, which is its own
  landing with the bullet above it.
- **An exterior conduit declares a crossing time nothing can direct.** A room
  may now carry `transit_seconds`, and `world.spatial_containment` carries an
  occupant onward on the simulation clock -- but only inside a
  `parent_entity` enclosure, because "onward" is derived as "strictly farther
  from the way in" and the way in is `_interior_entry_room`'s `dock_exit`
  marker, which only an enclosure has. A river reach, a conveyor hall or a
  sloped chute between two ordinary rooms therefore has no derivable
  direction. The field is READ and REFUSED there with a named notice through
  `crossing_report` ("this place declares a crossing time and the engine
  cannot derive which way is onward outside an enclosure"), never a guessed
  move -- so the declaration is not silently ignored, and what is missing is
  said out loud. THE MISSING FACT IS A DIRECTION SOURCE for rooms with no
  dock marker: a per-edge `downstream` flag, or a room-level flow direction.
  Pinned by `tests/test_room_transit_clock.py`.
- **Every stored card's interior is still empty until somebody runs the
  fill.** The reader now exists on BOTH card surfaces --
  `POST /api/characters/{cid}/fill_interior` for the reusable card and
  `POST /api/chats/{cid}/characters/{ch}/fill_interior` for the per-story one
  -- and reads a card's own prose ONCE, at authoring time, proposing the
  structured chain with its magnitudes; there is still deliberately no
  runtime prose-duration parser, because one is shaped by the phrasings one
  story happens to use. What remains is that running it is an authoring act,
  and it has to be run on the card THIS STORY READS: `scene.active_cast`
  resolves `chat_chars.sheet` over `characters.sheet`, and measured read-only
  2026-08-25, 13 of 116 `chat_chars` rows carry a per-story sheet, so a story
  that has its own card is filled from the story-card editor (Cast -> ✏️
  card) and a story that does not is filled from the reusable one. 0 of the
  79 stored sheets (61 characters, 18 personas) carry a non-empty
  `embodiment.interior`, so every live story is byte-identical to before this
  landing until its author opens the card the story reads, presses the
  button, reviews the stations and saves.
- **A region the ledger names that an authored chain omits is dropped rather
  than placed.** `materialize_named_stations` gate 5: where the holder's
  inside is a card-declared chain and the occupant stands mid-way along it, a
  standing contact naming a region no station matches mints nothing, and
  `_restation_interior_contact` re-derives the ledger's region from the room
  the occupant is actually in. It is a SUBTRACTION and the alternative was
  measured worse -- on a scratch corpus copy with the card filled, the graft
  chained the omitted region DEEPER than the entry station and walked the
  occupant outward into it, where she held for fourteen beats -- but the
  region the beat named is still a fact the engine now discards. THE MISSING
  FACT IS WHERE IN THE CHAIN IT BELONGS: the card states an order and the
  ledger states a name, and nothing relates them. The author's own fix today
  is to add the station to the card, which is why this is a residual rather
  than a defect; a real one needs a way to say "between these two".
- **Two read-only Director views lag the floored clock.** A resolved beat
  that asserts no readable time is now charged `UNCLAIMED_BEAT_SECONDS`, and
  three readers of the beat's end clock apply it through
  `world.mechanics.beat_end_elapsed` -- the scene commit, the memory commit
  and the perception mirror, which are the three that decide what is STORED.
  `agents.director_floors._sleep_elapsed` and `_conditions_view` are the
  fourth reader and are NOT floored: they take `sd_time=None` on pre-resolve
  calls, so a blanket floor would be wrong there. BOUNDED: they lag by at
  most `UNCLAIMED_BEAT_SECONDS` per silent beat, and the only decision they
  gate is `_NATURAL_SLEEP_SECONDS = 28800`, which a ten-second lag cannot
  flip. Closing it needs those views given a resolved-beat flag.
- **A room cannot carry a hazard.** A place-form interior is exactly where "a
  place that acts on the bodies in it over time" becomes expressible -- and
  there is no room field for it, no sweep that ticks one, and no capability
  that suppresses one. Declaring `RoomDef.hazard` ahead of a reader would be a
  field nothing reads, which `llm/schemas.py` deleted 29 models over; the seam
  is registered here instead, to land with its consumer.
- **A body that regrows inside a place-form interior is not auto-released.**
  `containment_broken_by_scale_change` reads the `contained` ledger only, and
  the handoff empties it. A scale change that makes the enclosure absurd
  therefore releases nothing, and the Director/movement backstop is the only
  thing that governs the exit. The scale rule and the place form need to meet.
- **The occupied-body-is-a-place clause is English-only.** `language_packs/en`
  carries it in the spatial specialist's `rooms` chunk; the `ja` pack keeps
  the old text, so a Japanese story's specialist is not told it owns this.
  The card-side `interior_note` fragment is NOT in this class and cannot be:
  the pack loader checks every story pack's `system_prompts` card against
  English key by key, so an EN-only fragment fails the `ja` pack's load
  outright -- measured 2026-08-25. Both packs carry it, and the Japanese copy
  is a model draft like the rest of that pack.
- **Observation metadata is computed and consumed by nothing.** `intensity`,
  `suddenness`, `ambiguity` and `directed_at_self` are re-derived from the
  scrubbed view for every atom, cost tokens on every character payload, and
  have no reader in code — `intensity` does not appear anywhere in the
  character prompt either. They are also nearly constant: `intensity` is 0.35
  on **96.7%** of 7,508 observations, and only 18 distinct
  (intensity, suddenness, ambiguity) tuples exist corpus-wide, because the cue
  lists behind them are an adventure vocabulary (explosions, gunshots, alarms,
  agony). Either give them a consumer or stop computing them; a field that
  tells a character every percept is equally important is worse than no field.
- **`directed_at_self` mislabels the intransitive own-body case.** Of 590
  observations opening on the perceiver's own body, **64.7%** carry
  `directed_at_self: false`, because `_SELF_DIRECTED` recognises only
  agent-first constructions ("grips your", "against you") and "Your body keeps
  spasming" matches none of them. Fixed for the deterministic sensation clause
  only, keyed on its verb rather than on a bare leading `your` — "your
  companion steps back" is not about the perceiver, and a broad rule would
  claim it is. Inert until the field above has a consumer.
- **The atom budget collapses channels.** `_observation_spans` merges
  smallest-first to fit `_MAX_OBSERVATION_ATOMS = 8`, and merging two spans of
  different channels marks the result `mixed`. That accounts for 16.6% of
  `mixed` observations — secondary to the 83.4% that matched no cue at all, but
  it means a beat arriving through MORE senses loses more channel information
  than a simple one.
- **A hover is not a contact, and there is nowhere else for it.** A measured
  "two inches of visible space" between two mouths is real fiction with real
  tension, and `contacts` can only say touching or nothing. It lives in entity
  `state`, where nothing ages it (§1.10): `_drop_contradicted_state` retires
  such a key only where a standing contact already speaks for that part, so a
  genuine hover with no contact survives unaged. A near-contact tier — or a
  `manner` that means "not quite" — would cover it. *(Moved from the alpha 6.3
  physical-ledger residuals, 2026-08-19.)*
- **A contact ledger whose only clock ticks on beats that MENTION contact
  cannot retire what the story stopped mentioning.** Ageing lives inside
  `spatial.apply_contact_ops` behind two gates: `_contact_ops_are_evidence`,
  and the early `if not isinstance(ops, list) or not ops: return scene` above
  it. Measured, chat 95 turns 10-15 (all 30 `director_contact` calls of the
  story read): every one of those beats emitted `contact_ops: []`, so
  `unasserted` never left 0 and one record stood six consecutive beats,
  delivered to the narrator each time as a live touch percept. The asymmetry
  is the tell — in replay, three beats in which two OTHER bodies touch retire
  the record and twenty beats of its own participants' silence do not: a
  contact is retired by strangers and never by its participants. Neither
  participant can end one by their own conduct, either. A character MAY emit
  `contact_ops:[{op:'remove',...}]` and is never obliged to (Picard was handed
  `contact:0` on five consecutive beats and never used it), and the player has
  no path at all — `director_contact._validated_player_contact_assertions`
  coerces every player op to add/cross, so a declared step ends a contact only
  by leaving the room. The fix is to move the clock to the per-beat call site
  (`world/spatial_merge.py` already calls `apply_contact_ops` on every merge),
  and it cannot land on a guess: `_CONTACT_STALE_BEATS = 2` was measured
  against evidence beats, which are rare, and against real beats it is almost
  certainly too short. That number, and whether a participant's own declared
  movement should retire that pair's whole-body contacts, are owner decisions
  and are why this is still here. The OTHER half of the same record is fixed
  (2026-08-28): a placement verb between two bodies is refused at the ledger
  floor (`CONTACT_PLACEMENT_MANNERS`), which cleared that record and the class
  it came from — but a genuine hold nobody mentions again still stands
  forever. That refusal was then defeated by a synonym (chat 98 turn 27: two
  adds differing only in `manner`, 'stand' refused and 'settle' kept), which
  is closed separately — within one beat, ops sharing a `_contact_key` are
  one claim, and a refusal on any wording of it refuses the claim.
- **A touched thing the scene never established is felt as "something", not
  named.** The contact channel's identity floor now has three tiers -- the
  observer's display map, the scene's own entity record for a thing, then a
  floor that says "someone" only where the scene will vouch for a BODY and
  "something" where it will not (2026-08-29, closing the half of D-L that was
  a person invented out of an object). The middle tier is the one that names
  a thing, and it needs an entity record. Measured across chat 98: five of
  the six object contacts in the run -- a bar, a table twice, a glass, a padd
  -- had no entity record at all, because nothing mints one for an object the
  Director merely names in an op (the same gap the transfer defect sits in:
  `derive_inventory_placements` places nothing for an object the scene does
  not know, and the possession fact dies with the placement). Those five never
  reached a view either: with no entity there is no position, and contact
  hygiene prunes a contact whose two parties are not in one room -- so a
  second defect was hiding the first, which is exactly why the floor may not
  depend on it. Where an object IS established the player is now told a thing
  rather than a person; where it is not, they are told a thing and not WHICH
  thing. Whether an op naming an unknown object should mint an entity for it
  is the owner's call, and it is the same question in both channels.
- **`something's surface` is honest and reads badly.** The clause builder
  composes the other party's label and their part as a possessive, which is
  right for a body ("Data's shoulder") and stilted for the generic thing-word
  the floor above falls back to. Dropping the possessive would need the
  renderer to know its label came from the floor rather than from a name, and
  `label_for` is deliberately opaque to it.
- **An orphaned relational value is dropped rather than folded.** When
  `thumb_touch: "feather_light_at_ear_base"` is retired by a standing thumb
  contact, its qualifier is discarded instead of merged into that contact's
  `detail`. Folding it was rejected for now: matching the right contact by part
  name is the same guesswork the whole change exists to remove, and a wrong
  `detail` is a sentence the narrator will repeat. *(Moved from the alpha 6.3
  physical-ledger residuals, 2026-08-19.)*

*(Bullet 1 — "`contacts` accepts a part slot that does not name a body" — was
struck 2026-08-19: `world/spatial_contacts.py` now refuses a non-anatomical
actor_part or target_part at the commit seam, in the one place every contact
passes through.)*

<a id="unbuilt-1-46"></a>

### 1.46 A transformation's parts are repaired on read, never at the source

`scene.normalize_transformed_parts` coerces a `physical_transformation`'s
`parts` onto `attire.REGIONS` and `EXTRA_PART_ASPECTS` and salvages the
off-menu text into `description`, on the `rederive_entry` precedent — so
stored conditions heal lazily and the malformed phrase ("emerge from the
fluffy, pointed, golden of the top of the head") stopped reaching anyone.

**The body specialist still writes the free text.** Its contract was not
changed, so every new transformation mints the same shape and is repaired
downstream on every read. `character_schema._normalize_extra_parts` shows what
the closed menus look like at the authoring surface; the specialist prompt
should say the same thing, and then the read-path repair becomes a floor
rather than a working part.

<a id="unbuilt-1-65"></a>

### 1.65 A condition subject written as a scene uid names nobody

Found while landing restraint and awareness exits
([`DESIGN_RESTRAINT_AND_AWARENESS_EXITS.md`](design/DESIGN_RESTRAINT_AND_AWARENESS_EXITS.md)
§ Residuals). `world_conditions` rows in chats 24 and 25 carry a **subject
written as a scene-entity uid**, which matches no perceiver's display name —
so those rows are inert under any selector, including the widened ones, and
the gate they describe has never fired for the body they describe.

This is not created by the kind widening and is not fixed by widening
further: chat 26 holds a canonically-spelled `awareness` row with the same
uid-subject shape and is equally inert. The two faults look alike from the
symptom (a condition that does nothing) and are unrelated at the cause — one
was a vocabulary the reader did not recognise, this one is an IDENTITY the
reader cannot resolve.

The fix is identity folding — `same_subject` / `normalize_scene_subjects`
territory — applied to condition subjects, so a uid and the display name it
belongs to are one subject. It is its own change with its own tests because
folding `world_conditions` subjects touches the commit path, the restore
path, and branch/clone ID remapping, which is the checklist in
[`guides/DATABASE.md`](guides/DATABASE.md) rather than a predicate edit.

Three smaller residuals from the same note, deliberately not landed with it:

- **One metaphorical `_RELEASE_CUE` false positive** ("breaks free of her
  paralysing fear") and its mirror class (a possessive object like "pulls
  Hinami's file free", unreachable today only because the apostrophe breaks
  the cue's lookahead chain). Both need noun semantics a regex does not
  have; the cost is a warned, recoverable ending, and prose saying a
  physically-restrained body "breaks free" is nearly always literal.
- **Restraint synonym and holder-field tables are English** — the same
  standing gap `_RESTRAINT_SYNONYMS` had before that work. Owner decision 2
  (route recognizers through the packs) covers the class.
- **`consciousness` rows stay unread forever** by design: the word does not
  say which way the body is crossing. If a model starts writing them at
  volume the fix is the prompt, not the predicate.

<a id="unbuilt-1-66"></a>

### 1.66 The story column's floor overrides the room it reserved

`syncVitalsGutter` (`static/js/settings.js`) computes `--story-width` as
`clamp(STORY_MIN_WIDTH, shellWidth - 2*reserve, STORY_MAX_WIDTH)`, where
`reserve` is the widest float that has to sit beside the column. The
reservation is correct and the clamp silently defeats it: when
`shellWidth - 2*reserve < STORY_MIN_WIDTH` the column is pushed back up to 720
and the float it was making room for lands ON it.

Found by the browser suite 2026-08-19, the first run after the CI job stopped
being skipped: at a 1400px window the reservation asked for a 650px column, the
floor forced 720, and the ambience controls sat **27px inside the input box** —
over the right-hand end of the field being typed into.

**The instance is fixed and the class is not.** The container queries that shed
the slider and then stop floating are now derived from the cluster's measured
widths (`static/styles.css`, `@container composer`). The same hole is open on
the LEFT: `VITALS_MIN_GUTTER + 12` is 198, so a shell narrower than
`720 + 396 = 1116` with the tracker visible reserves room the clamp then
refuses to give, **and nothing reports it**.

Two shapes of real fix, neither taken: let the column go below
`STORY_MIN_WIDTH` when a float genuinely needs the room (readability loses to
not-overlapping), or make the floats' own container queries the single
mechanism and drop the JS reservation (one mechanism instead of two that can
disagree). The second is closer to how the ambience cluster already behaves.
Whichever wins, `browser_tests/test_ui_smoke.py` holds the invariant and should
gain a tracker-side case.

<a id="unbuilt-1-71"></a>

### 1.71 `nature` is the designed answer and it is almost never asked

`BlurbMintEntry.nature` (`llm/schemas.py`, `PRESENCE_NATURES = person | thing |
voice`) exists precisely so the engine stops deriving animacy from a noun the
model chose in passing. Its own docstring calls that "an enumeration
treadmill": `_INERT_ENTITY_KINDS` reached 50 entries and
`_ANIMATE_ENTITY_KINDS` 35, "and a kind string still cannot separate a
suppression device from a dalek war machine."

**It is only answered on the `scene_life` path.** `background._mint_blurbs`
runs over MANAGED presences, which exist under `scene_life: ambient|full`; at
the default level no presence is ever asked what it is. Measured over the live
corpus: **not one tracked presence carries a `nature`**, so every consumer
falls through to the graded guesses, and 16 of them land in `undecided` — 14
machines and 2 Daleks, exactly the pair the docstring says a noun cannot
separate.

Two gates now read that verdict, and they read it with opposite conservatism
because they ask different questions — may this thing act (silence is cheap)
versus is this name protected (a wrongly-protected name renders a machine as
"the unfamiliar person" in the room's own description). The identity floor
settles `undecided` on CONDUCT, which separates the live corpus perfectly and
is honest about what it cannot see: a genuine person who has never spoken and
whose kind is neither animate nor inert.

The fix is to ask the question. Either widen the blurb pass to every newly
tracked presence — it is one batched call per room, and the answer is frozen
once — or ask the Director for it at entity creation, which is a schema change
(owner policy 4, §1.58). Until then the answer is inferred, and the inference
is documented rather than reliable.

<a id="unbuilt-1-72"></a>

### 1.72 `placement` and `add[].covers` are documented, passed, and inert

Found wiring §2.14's guessed-span report (2026-08-19). Both prompts tell the
Director where to say a garment is worn when the name does not imply it —
`add:[{name:'linen shirt',covers:['legs','groin']}]` and
`placement:{'<garment>':['<region>',...]}`, with the reasoning spelled out
("underwear on the head, a belt across the chest, a shirt worn as trousers…
the variations have no end and no word list reaches them"). Neither works
through the commit path.

`story.attire.apply_flat_change` honours `placement` perfectly — called
directly with `({}, ["nagajuban"], placement={"nagajuban": [...]})` it returns
`torso, legs, groin`, each garment stamped `placed: True`. `commit_attire`
passes the same argument at the same call (`persist/commit_attire.py:845`,
`placement=d.get("placement")`), and the stored result is **torso alone**.

The cause is ORDER, not plumbing. The `add` loop puts the garment into
`cur["wearing"]` first; `_before = attire_model.normalize_regions(cur)` then
DERIVES its span from the cue tables before `placement` is ever consulted; and
`apply_flat_change` finds the garment already placed and leaves it where the
tables put it. The authored answer arrives after the guess has been made and
loses to it.

No test covers the surface end to end — searching `tests/` for `placement`
finds only `displacement`, an unrelated feature whose name contains it, which
is how a documented authoring channel stayed inert without a single red run.

Not fixed here because the fix is a reorder inside a function with a long
measured history (the decisive-removal rule, the steal guard, the shed-object
minting and the region derivation all read `_before`), and it wants its own
pass with the ordering stated as an invariant: an AUTHORED span is not a guess
to be improved, so it must be applied before anything derives one. Until then,
`guessed_spans` reports these garments — which is the right report, since
nothing did in fact know where they go.

<a id="unbuilt-1-78"></a>

### 1.78 One authored body field reaches no reader

**Found:** the same beat, asking why the same engine renders one body richly
and another thinly.

`character_appearance` (`story/character_schema.py:1447`) and
`persona_appearance` (`:1690`) return `embodiment.visible.summary` and nothing
else. `visible.build`, `visible.face`, `visible.hair`, `visible.eyes` and
`visible.distinctive_features` are offered in the card editor, normalized,
persisted, archived — and read, outside `character_schema` itself, by exactly
one thing: `_prose_names_a_part`, a card-warning heuristic. No view, no
narrator, no memory ever receives them.

So how a body renders is decided by which field its author happened to fill.
Measured on one pair: Mirelle's summary is a full paragraph and she arrives
with skin, hair, eyes, horns, tail and wings; Hinami's summary is "A young
woman appearing in golden fox ears and six golden tails." and her equally
detailed `build`/`face`/`hair`/`eyes` reach nobody.

`_coerce_appearance` (`:963`) already folds these fields into the summary —
but only from `embodiment.<key>`, where an older sheet MISPLACED them. A card
that puts them in the correct place, `embodiment.visible.<key>`, is the one
that loses them. Either compose them the way the misplaced ones are composed,
or stop offering fields the engine does not read.

**Four of the five landed.** `build`, `face`, `hair` and `eyes` are delivered.
`_coerce_appearance` projects the located three into
`embodiment.visible.regions.head.visible_zones` on every normalize — no new
authoring surface, no re-authoring, and one correct answer per field — and
`attire.uncovered_zone_text` gates them on the mirror of the `beneath` rule:
delivered until something covers the region, delivered again when it comes off
or is pushed aside. `build` is not located, so nothing worn can cover it and it
rides beside the summary. Delivery is on the description path only
(`perception._body_descriptions`), behind the sight and arc gates that were
already there, and the stranger LABEL still comes from the summary alone so an
observer holding a silhouette gains nothing. See `Design.md`.

**`distinctive_features` remains.** It is offered in the editor, kept through
every normalize, carried in archives, and read by exactly one thing —
`_prose_names_a_part`, a card-warning heuristic. It is also the natural source
for the stranger descriptor that `observer_display_map` currently cuts from
`visible.summary`, so the field literally named "what distinguishes this
person" is not used to distinguish them. `character_card_warnings` says so, on
every card-producing surface.

<a id="unbuilt-1-79"></a>

### 1.79 Four readers spell the same tolerant ledger lookup

`story.attire.entry_for` is the shared casefold-tolerant lookup of a body's
attire entry, added because `scene.visible_body_text` did a bare `.get(name)`
and a case-variant identity key therefore found no garment for a dressed body
— a gate that failed OPEN, delivering the face a covering conceals. Three
inline copies of the same fallback remain in `agents/common.py` (around the
`observer_body_regions`, region-coverage and per-body ledger reads). They are
correct today and independently maintained, which is the same second-copy risk
`_co_present_company` was just collapsed to remove. Adopting `entry_for` at all
three is pure subtraction and wants no design decision.

The key is unreliable in the first place because
`persist.commit_attire._heal_attire_identity_keys` heals on the WRITE path and
nothing heals on the read path. Healing on read, or canonicalising the key at
one boundary, would retire all four call sites rather than unify them.

<a id="unbuilt-1-81"></a>

### 1.81 A part-qualified pose support is invisible to the pose sweeper

**Found:** closing the chat-87 view-register class, 2026-08-25.

`_pose_referent` now resolves `<owner>.<part>` through its owner, and
`normalize_scene_subjects` folds the owner half so one field holds one
spelling. `normalize_scene_poses` was not touched: it still checks a support
against `positions` and the room's `anchors` **by whole string**, so
`Kestrel.hand` matches neither and the sweeper never clears it. The pose keeps
naming a body after that body has left the room.

Adjacent and real, and deliberately left out of the render fix: it changes
what gets CLEARED rather than what gets rendered, and it belongs with the
contact-bound pose invalidation rather than with the referent resolver.

<a id="unbuilt-1-83"></a>

### 1.83 A beat that names only where the clock ENDS ages no body at all

**Found:** 2026-08-25, closing the `state_diff.time` vocabulary.

The vitals tick inside `world.spatial_merge.merge_scene_with_diff` asks
`world.mechanics.time_diff_duration` how long the beat took, and that helper
is handed the time block ALONE — no previous clock. So it can answer from
`duration_seconds`, or from the span between a parseable `start_seconds` and
`end_seconds`, and from an absolute-only diff it answers 0.0. Hunger, thirst,
fatigue and every other vitals channel therefore do not move across a beat
that says only "the clock now reads N", which is precisely the shape the
clock reader was just taught to accept (5 such diffs in the live corpus: chat
74 turns 55 and 60, chat 88 turns 61, 64 and 66).

The 0.0 is deliberate and is the safe half of the trade, which is why this is
a residual and not a defect to fix in place: under-ageing a body is
recoverable, and ageing it by the story's whole elapsed history — which is
what subtracting nothing from an absolute position would do — is not. The
argument is written at `time_diff_duration` itself; this entry exists because
a docstring is only found by someone already reading that function.

The repair is a seam widening, not a guard: `merge_scene_with_diff` has no
previous-clock parameter, and the callers that would have to supply one
include perception's mid-turn merges, where the "previous" clock is a
different question. Do it with the seam, not around it.

**The seam now exists, and this entry is still open.** `merge_scene_with_diff`
gained a keyword-only `clock_seconds` when a passage learned to carry its
occupants on the clock (`world.spatial_containment.advance_room_transits`),
and both stored-side callers pass the same end-of-beat value through
`world.mechanics.beat_end_elapsed`. The vitals tick was deliberately NOT
rewired onto it: this entry is about which QUANTITY ages a body, and moving
it from `time_diff_duration` to a clock delta is a change to how every
survival channel advances, which wants its own measurement rather than a
free ride. Note also that a beat charged `UNCLAIMED_BEAT_SECONDS` shares
this entry's shape exactly -- the clock moves and the bodies do not -- so
the floor makes the class visible on 130 more corpus beats without widening
it.

<a id="unbuilt-1-84"></a>

### 1.84 A condition with no declared end and no owning floor still stands forever

**Found:** 2026-08-25, landing the due-tick sweep. Half of that landing; this
is the half that was deliberately NOT shipped.

A condition now has three ways to be seen and two ways to end. It can end on
the clock (`expires_at`, `world.mechanics._expire_conditions`) or by an act
(the Director re-emitting the same `condition_id` with `active: 0`, which
`_conditions_view` finally equips it to do by showing every live row's id).
What it still has is no way to end when the fiction simply moved on and
nobody said so. Measured read-only on the author's `engine.db` 2026-08-25:
444 `world_conditions` rows across 50 chats, 363 active, and **360 of those
active rows carry no `expires_at` at all** — spread over 106 distinct free-
text `kind` strings, so no per-kind duration table could hold the class.

The mechanism designed for it was an idle-review backstop in the same sweep:
a row that declares no clock end and whose family owns no deterministic exit
(`story.scene.condition_exit_owner` returns None) closes with a stated reason
after long idleness. It was deferred because BOTH of its arms were measured
to close zero of the 360 rows they were built for:

* the **simulation-clock arm** needed 24 story hours (86,400s). No chat in
  the corpus has ever reached it: the maximum `simulation_clock.elapsed_
  seconds` over 74 chats is 29,145 (chat 40) and the median is 372.5. The
  threshold is 209x the p90 of the 76 authored condition durations (414s),
  and unreachable in every story that exists.
* the **turn arm** needed `last_asserted_turn_idx`, which this landing began
  stamping at the write — so it exists only on rows written after it, and
  not one of the 360 legacy rows has it.

A simulation-second twin of that stamp (`last_asserted_at_seconds`) shipped
with the landing and was removed in the repair pass the same day: nothing read
it, `_conditions_view` already reports `age_seconds` off `started_at`, and the
arm that would have wanted it is the clock arm this entry says should probably
be dropped. A field nothing reads is worse than no field, and that rule does
not stop applying to the fields this landing added. If the clock arm is ever
argued for rather than assumed, the stamp is two lines in
`persist/commit_entities.commit_world_entities` and belongs in the commit that
argues it.

Shipping it would have been a mechanism whose measured effect is zero while
its register entry claimed the rows "drain organically", which is the exact
failure mode this table already has too much of. The two things it needs are
both small and both real work: (1) an initialization op in the sweep that
stamps `last_asserted_turn_idx` on un-stamped rows the first time it sees
them (the `next_tick` initialization is the shape to copy), and (2) a
turn-count threshold argued from something — `mind/affect.py`'s
`_INTENT_DORMANT_AFTER` of 30 turns is a borrowed constant, not a measured
one. The clock arm should probably be dropped rather than lowered: story
clocks in this corpus do not move far enough to carry a rule.

The cost asymmetry that justifies building it at all is the awareness floor's
own, generalized: closing a condition wrongly costs one beat the Director can
re-narrate, and never closing one is the 360-row ledger.

**And the ledger is now charged per beat.** `active_conditions` reaches the
Director in `director_interpret`, in `director_resolve` and inside the body
specialist's payload, so a live row is spelled three times a beat (four for a
gated awareness row, which `active_awareness` also carries). The view is
capped at 40 rows and one corpus chat carries 24 active at once, so the worst
case is real and recurring rather than theoretical. Two separate reductions
are available and neither is free: closing the un-owned rows (this entry) so
the ledger is short, or composing the Director's condition blocks once per
beat instead of once per stage. The first is the one with the design argument
behind it; the second is a payload-assembly change and should not be made
before somebody measures what the three copies actually cost.

<a id="unbuilt-1-84a"></a>

### 1.84a A condition's start is still a model-declared clock position

The question this entry used to hold is DECIDED AND BUILT: the engine owns
the clock's position, and a beat contributes a span. `read_time_diff` now
reads every absolute in the frame the block itself declares -- its
`start_seconds` is the block's own anchor. Anchored where the clock stands,
or declaring no anchor, the claimed end is adopted verbatim (every canonical
corpus row, byte-identical to before, and the bare-absolute chat 88 rows
with them); anchored anywhere else, only the SPAN crosses -- the declared
duration, else end-minus-start -- from where the ENGINE stood, and the
commit warns ("anchored away from the engine clock"). The measured beat
(chat 95 second pass, beat 2: start 20520 / duration 45 / end 20565 against
a clock at 20.0) now advances the clock 45 seconds, not five and a half
hours. A skip still lands whole from any frame, because a skip is a
duration and a span survives the translation a position does not. Sleep
still measures: `_sleep_elapsed` subtracts a stored `started_at_seconds`
from a beat end that is now always engine-framed, and the three tests that
pinned the old contract were rewritten to worlds whose clock and triple
agree (`test_time_channel.py`, `test_awareness_waking.py`,
`test_time_of_day.py` -- each says so at the site).

What remains is the OTHER operand of the sleep subtraction, and it is the
same ownership question one table over. A condition row's
`started_at_seconds` is model-authored at creation (`llm/schemas.py`
defaults it to 0.0; `persist/commit_entities` stores it verbatim), so the
anchor a sleep is measured FROM is still a model-declared clock position: a
model that leaves the default reads as "asleep since the story began", and
one that stamps a foreign frame reads negative and falls to
`_sleep_elapsed`'s unknown-guard -- honest, and one rung poorer than a
number. Under the decided ownership the engine knows when a row began (the
beat its INSERT committed, whose end clock the scene commit computes two
domains earlier), so the close is the condition commit stamping that
reading when the payload's own anchor is absent or not credible. Two
things make it not a two-line change: 0.0 is also a legitimate reading at
a story's opening, and a Director recording a condition RETROACTIVELY
("asleep since dusk") is asserting a past start the stamp must not
overwrite -- which is the reconciliation problem again, one field over.
Sibling of 1.84's `last_asserted_at_seconds` note: the stamp itself is two
lines in `persist/commit_entities`, and it belongs in the commit that
argues the credibility test.

<a id="unbuilt-1-100"></a>

### 1.100 A card can author one garment twice, and the ledger cannot tell

**Found 2026-08-29 while fixing the attire write gate (chat 98).** The gate's
paraphrase defect is fixed; this is what was underneath it and is not.

Every one of that run's four cards carries the same outfit written twice, in
two spellings. Measured in the persona sheet and in the committed ledger:

    "standard Starfleet duty uniform (teal science division shoulders)"
    "Starfleet uniform jumpsuit, sciences blue shoulders"
    "combadge"  /  "commbadge"
    "Klingon baldric"  /  "Klingon warrior's baldric"

The mechanism is the card's two representations. `character_schema.
_normalize_initial_outfit` hands `normalize_regions` an authored `regions`
block AND the flat `wearing` list beside it; the fold is deliberately additive
("an author who wrote regions is not overruled by the flat list their card
also carries") and dedupes with `resolve_garment`, which correctly refuses to
call those two strings one garment. So both land, and the body wears one coat
twice for the life of the story.

What it costs, all downstream and all measured in that run: the duplicate
destroys the uniqueness the licence's per-garment tier needs, so the one word
the beat used named neither garment (that half is fixed); a `remove` of one
spelling leaves the other on; and the shed-object mint runs twice for one
garment, which is how an entity id reached a `remove` as a garment handle.

**Not fixed, because every available fix is a guess.** The two strings share
"Starfleet" and "shoulders" and nothing else; their `covers` sets differ; one
attaches and one does not. No determinate reading of the ledger's own
vocabulary says they are one garment, and a fuzzy same-garment matcher would
be exactly the instance-shaped rule this repo forbids. The two candidates,
both needing the owner:

  * **Regions win.** When a card carries an authored `regions` block, treat
    the flat `wearing` list as already represented rather than folding it in.
    Determinate, and it fixes all four cards at once — but it silently drops a
    garment an author put only in the flat list, and the fold's comment says
    that additive direction was chosen on purpose.
  * **Tell the author.** The merge is the only place the two lists still exist
    separately, so a warning has to be raised there and carried out to
    `character_card_warnings` — which today reads a card the merge has already
    flattened. Costs nothing behaviourally and closes nothing on its own.

<a id="unbuilt-1-110"></a>

### 1.110 An opening may leave the whole cast nowhere, and nothing objects

`director_establish` writes `positions`. On one generation of a five-character
scenario it wrote ONE body — the player — and left every attached,
`status='active'` cast member with no position, no pose and no station.

WHAT THAT COSTS, measured end to end. `agents/common.character_room()` returns
None for a body with no position; `agents/perception.py` builds `sources` only
from cast that have a room, so `perception_act` committed
`{"views": {}, "observations": {}}` with an all-empty `composer_ledger`. The
character payload then carried `perception.current_room: ""`,
`view: "Nothing in particular reaches you this beat."`, `observations: []`,
`spatial_frame: {}`. An officer asked a direct question by name answered
nothing, and his three considered responses were "remain at station",
"initiate standard security sweep", "stand ready for any orders" — exactly what
a mind with an empty beat produces. The Director was correct throughout
(`flow.addressed_to` resolved, every speech span preserved) and the interaction
loop called him first. Every stage behaved correctly on data that was already
wrong before turn 1 ran.

IT IS A SAMPLING FAILURE WITH NO FLOOR UNDER IT. Same scenario, same prompt,
four runs: three placed all six bodies, one placed one. Nothing objected,
because the only opening-stage placement checks —
`llm/schemas.py:5222 _unplaced_establish_entities` and
`agents/director_floors.py:1287 _unplaced_minted_entities` — iterate
`state_diff.entities`, things the Director MINTED. **Registered cast are not
entities**, so no floor covers them, no warning fires, and no test asserts that
an attached active character receives a room from the opening.

The fix is a floor, not a prompt: an attached, active, non-dormant cast member
that the opening left unplaced is a defect the engine can see for itself.

<a id="unbuilt-1-113"></a>

### 1.113 A short whole garment name cannot license its own wardrobe

**Found 2026-08-29** while fixing the licence gate's compound-name blindness
(chat 92 t17). `attire.garments_named_in` floors every suffix window at two
words or eight characters, so a fragment of a name cannot license a change to
the whole garment. The floor applies at `i == 0` too, where the window is not
a fragment — it is the name. A ledger garment called `t-shirt` (one word,
seven characters) never clears it, and tier (c)'s word-set rescue cannot see
`tshirt` in prose either, so that garment can be named by no beat at all and
every change to it is refused.

Not fixed with the compound-name pass because the two guards are separate and
only one was measured: the floor's cost is a garment whose whole name is short
AND spelled differently in prose, which no live chat has yet produced. The
shape of a fix is to exempt the whole-name window from the floor — a name is
never a fragment of itself — and then to decide whether tier (c)'s uniqueness
test is enough protection for a three-letter name like `tie`, which is what
the floor is currently standing in for.

<a id="unbuilt-1-114"></a>

### 1.114 The ledger can say what a garment replaced; nothing says it yet

**Found by playing 2026-09-05** (flat run PE4, turn 11): out of the shower,
the body specialist wrote `attire: {"Noor Haddad": {"add": ["big blue bath
towel"], "remove": []}}` and the committed ledger read `scrubs top, lanyard,
jumper, towel, scrubs trousers, socks` — a woman who had just showered, in a
towel over a jumper over scrubs. No warning fired at any stage.

**The ledger half landed in the same commit** (`story/attire.py`:
`displaced_by`, `_place_held`, `apply_flat_change(displaces=...)`;
`tests/test_attire_region_displacement.py`). A garment put on in another's
place turns it out, and the displaced garment reaches `removed` like any other
departure, so `newly_removed` reports it and it becomes a thing in the room
rather than disappearing from the ledger. Layering stays the default: the
ledger cannot tell a coat over a jumper from a towel instead of one, so it
honours a declared replacement and never infers one.

Two halves are outstanding, and neither is the ledger's to build:

- **The body hand's attire clause** (`llm/prompts.py`, the body specialist's
  attire block, plus `language_packs/*/cards/system_prompts/`). State the
  class, not the case: *a garment put on in place of what was worn names what
  came off in `remove`; adding alone means adding a layer over what is
  there.* This is the whole fix for the live beat — the engine has always
  handled a `remove` correctly — and it is one sentence read by every story.
  Watch the next few beats for what it licenses (a hand that now removes too
  eagerly is the failure to look for).
- **The commit seam** (`persist/commit_attire.py`, `apply_attire_diff`), which
  builds `wanted` as previous + `add` − `remove` and calls
  `attire.apply_flat_change`. To let a replacement be stated rather than
  inferred it would pass `displaces=` for the garments the beat says arrived
  in another's stead. That needs a channel to carry the statement: either the
  body specialist's attire diff gains an optional
  `in_place_of: {garment: [garment, ...]}` (`llm/schemas.py`, and
  `attire.coerce_diff_shape`'s `_DIFF_KNOWN_KEYS` already reserves the shape
  of such a key), or — cheaper and probably enough — the clause above lands
  and nothing else is built. **Do the clause first and measure.** A
  deterministic trigger here would have to guess which of the two a beat
  meant, which is exactly the guess the ledger refuses to make.

A third option was considered and rejected: warning whenever an `add` lands
on an already-covered region. It fires on every legitimate layer — a coat, an
apron, a robe over nightwear — which is PE20's disease one module over.

<a id="unbuilt-1-127"></a>

### 1.127 A place the plan already holds, named from anywhere (PS5, BUILT 2026-09-05)

**Found and fixed 2026-09-05** (`docs/experiments/PLAY_2026_09_05C_solitude.md`
§ PS5), the run's worst failure. `planned_rooms` carries the plan's
development brief and is scoped by REACH -- the room a body stands in, the
one it is moving into, the non-wall neighbours -- which is right for a brief
and wrong for a spelling. A player names a place from anywhere, and a
Director never shown the name invents one; `classify_movement` consults the
whole plan, but it cannot match an invention that shares no word with the
plan's spelling.

Measured: the Writers' Room published "Town Habitations Shelf"
(`town_shelf_lane`) and `unroofed_common_hall` with a planted derrick in it.
Turn 12, from three rooms away, the interpret payload carried
`existing_rooms` and **no `planned_rooms` key at all**; the Director wrote
`upper_terrace_settlement`, and turn 13 minted `settlement_common_hall`. The
town ended with two shelves of workers' houses and two common halls, and the
one thing the Room had planted to be found was unreachable in either. Turn 7
was sent one planned room while four were published; turn 10 was sent one.

**Built:** `world.structure.planned_room_index(cid, scene)` -- `{room_uid:
name}` for every live planned room the scene does not yet hold -- reaches the
interpret and resolve payloads as `planned_elsewhere`, beside the scoped
brief and never replacing it. A name is what a spelling costs: seven rooms
was 591 bytes in that run, and the largest plan in the owner's database (chat
114, 49 rooms) is a few kilobytes. **Uncapped**, per the standing ruling that
a cap is named rather than buried -- there is nothing here worth capping. The
interpret prompt states the rule in both packs: *a place the story has
already planned is not a new place*; only a destination no scene room and no
indexed room answers is a new room.

**Residual.** A player may still name a planned place in words that match
neither its id nor its name -- "the settlement" for "Town Habitations Shelf".
The index gives the Director the material to make that judgement and does not
make it; whether a fuzzy match belongs in `planned_context` is a separate
question, and the deterministic matcher is deliberately exact
(§ *An exact match is not ambiguous*).

<a id="unbuilt-1-130"></a>

### 1.130 Harm, conditions and the body: what the 2026-09-05 fixes left open

Campaign 3 lane D (PR3, PR4, PS12, PQ21, PM9). Built the same day, in
`world/survival.py`, `world/mechanics.py`, `persist/commit_mechanics.py`,
`mind/psychology_runtime.py`, `mind/affect.py` and
`agents/director_floors.py`: air no longer recovers while the world is taking
it or in the same merge that declared it lost (`AIR_DENIED_KEY`); a standing
condition whose subject is a ROOM acts on the bodies in that room; a
condition that spells a cadence and fills it with nothing is reported at
commit; a body standing in a stated hazard on a beat that rolled nothing is
reported; an authored `initial_state.stress.activation` reaches the first
beat; a drive's strain is not paid down by the clock; and the restraint scan
pins its cue to one clause instead of indicting the room. What remains:

**A room condition still reaches no VIEW.** PR4's half (a): *a standing
condition of a place is a fact about standing in it.* Nothing in
`agents/perception.py` or `agents/composer.py` reads `world_conditions` --
grep returns the Director's `active_conditions` payload key and nothing else
-- so turns 8–13 of the burning tenement put Mirela on a landing that was on
fire and her view said *"steady pressure, weight and shared warmth"*. The
condition now ACTS on her body; it still does not reach her senses.
`world.mechanics._hazard_rooms(scene, conditions)` is the reader that answers
"which rooms does the engine state are dangerous", and a percept path would
compose from it the way a substance does.

**`resolution_flags.contested` still keys off REACTORS.** PS12's owner
question was answered YES -- a declared act against a stated physical hazard
is contestable with no second party, because a contest needs an opposing
FORCE, not an opposing person -- and the deterministic floor
(`world.mechanics.unanswered_hazard_subjects`, warned from
`persist/commit_mechanics.commit_transit_sweep`) reports the beats that went
unanswered. It reports; it does not roll. The trigger itself belongs in
`agents/director.py::_reconcile_resolution`, where `contested` is computed,
and in one clause on the `body` specialist's sheet in both packs.

**A mind-model claim can still form with no cited evidence.**
`mind/psychology_runtime.apply_belief_updates` refuses an update carrying no
`evidence` and stores `last_evidence` on what it keeps;
`mind/theory_of_mind.apply_mind_model_updates` requires only a non-empty
`claim` and records no provenance at all. That asymmetry is the most likely
mechanism behind PQ21's one unattachable belief (*"Halla will let others
circle the house unless she is stopped"*, 0.6, in a run whose every other
belief traced to a beat). Not fixed on a single observation, and per the
standing rule a missing field is not a dead one: the repair is ADDITIVE
(store the cited evidence on the hypothesis so a reader can attach it),
never a refusal that would silently drop theory of mind wholesale.

**`_RESTRAINT_KEYWORDS` is still a word list read against free prose.** The
attribution is fixed; the vocabulary is not, and `pinned` is an ordinary
transitive verb of ordinary objects. The reduction the finding asks for is to
state the class the engine owns -- a restraint is a `conditions` entry or a
contact with a restraining relation -- and the audit that has to precede it
is that the scan's own regression file pins a case where the only evidence is
a line of dialogue (`"Reya is my hostage now."`), so the dialogue path is
earned and cannot be dropped.

**`elapsed_psych_units` returns one number in two units.** One unit per TURN
in a story with no simulation clock, one per MINUTE in one with a clock, and
three consumers (`resolve_stress`'s two half-lives, `resolve_hedonic`,
`update_drive_strain`) read it as if it were one. `_STRAIN_DECAY_FLOOR_PER_BEAT`
bounds the damage where it was measured; the clean fix is for the caller
(`persist/commit_memory.py`) to say which unit it is passing.

<a id="unbuilt-1-131"></a>

### 1.131 Geometry after the 2026-09-05 campaign: what the vertical repair left open

**Fixed 2026-09-05** in `world/spatial_orientation.py`,
`world/spatial_senses.py`, `world/spatial_fov.py`, `world/spatial_lint.py`,
`world/spatial_geometry.py`, `agents/director_movement.py`,
`agents/director_fanout.py` and `story/plot_packages.py`; regressions in
`tests/test_spatial_campaign3.py`. A VERTICAL WAY OUT IS NOT ON A WALL, so
it no longer collides for one (PM1), gets no doorway view-cone (PM2), and is
not laid out on the floor below it by the sight field or the layout lint
(F67, which PM1's repair would otherwise have made live). A fixture with
`footprint: run` no longer puts two bodies at its two ends within arm's reach
(PM3). An extent is an authored size, so the unauthored-size row no longer
fires against the lint that says the extent decides (PS17). `extent_clamp`
reports a measurement `EXTENT_MAX_PACES` moved (PS19). The contact hand is
scoped to the rooms the beat can leave a body in, not the one it started in
(PM15). A declared walk is attributed to the LEAST OBSTRUCTED route rather
than the shortest (PX11). A planned edge may carry `distance` (PR13).

**Residuals, each an owner decision or another lane's file.**

* **PS7 — an anchor whose description names a passage is not a passage.**
  `upper_terrace_rim.anchors.cistern_arch` read "the deep, unglazed archway
  leading into the lower cistern vaults" in a room with no edge to any
  cistern; the player walked into it and there was nothing through it. The
  merge cannot fold it onto the exit it names without READING the anchor's
  prose to decide whether it names one, which is the free-prose guard
  `CLAUDE.md` refuses and F58 was already refused on. The fix is one clause
  in `language_packs/{en,ja}/cards/system_prompts/prompts/director_establish.txt`
  and the spatial specialist's `chunks/rooms.txt`: *an anchor is a place in
  this room, never a way out of it; a way out is an `adjacent` entry.* The
  second half — the interpret raised `needs_mapping` with
  `mapping_request: "Map the interior of the cistern vault accessible through
  upper_terrace_rim's cistern_arch"` and nothing answered it — is real and
  not addressed: `agents/mapping.py` files a planning need for an unplanned
  DESTINATION and an unmatched LOCATION QUERY and for nothing else, and
  `needs_mapping` alone is set from a word-cue list on ordinary declarations,
  so filing on it would flood. A need reason for a mapping request the beat
  raised and no other need covers wants `world/planning_needs.py` and
  `agents/mapping.py` together.
* **PM3's other half — nothing authors a `run`.** The floor is built and
  answers correctly; no establish or specialist prompt tells a hand that a
  fixture with length carries `footprint: run`, and the spatial chunk that
  documents `footprint` describes it only in terms of sight
  (`specialists/spatial/chunks/rooms.txt`). Until that clause lands, the
  measurement in the live case — a fourteen-pace table — still has nowhere
  to live.
* **PR11's other half — a character's crossing is not a declared walk.**
  `_travel_continues` advances a walk the PLAYER declared, a leg a beat,
  through the `approach` record `persist/commit_scene_state.py` writes from
  `interp.movement`. A character has no such record: their movement is a
  position the spatial hand writes or does not, so a body narrated climbing
  for six beats simply never arrives (rush turns 7-13, four
  "progress held at 0.0" warnings and no position change). Opening a travel
  leg for a character is Director/character-side work, not geometry.
* **PR13's other half — the engine has no difficulty axis.** `distance` says
  a crossing takes more than one beat; nothing says it is HARD. The Room's
  own note ("an 18-inch void with a four-foot drop … impossible for an
  eighty-year-old woman without two hands bracing") has no field. Whether a
  way through should carry a cost the movement backstop can refuse against a
  body's state is an owner decision, and inventing one would touch the edge
  schema, the backstop, the World Browser and both packs.
* **PS19's other half — the tool must state what it stored.** `extent_clamp`
  exists; `story/room_tools.py`'s `plan_rooms` result still reports the
  extent the Room asked for rather than the one the registry holds.
  The preview's own clamp warning (`plot_packages._preview_plan_rooms`)
  never fired from a drafted package until 2026-10-08: it read the STORED
  op, whose extent was already clamped, and compared the clamp with itself.
  The shaped op now keeps what was written (`extent_said`), as it keeps a
  cut far look's length (`far_look_cut_from`).

<a id="unbuilt-1-132"></a>

### 1.132 What the possession and wardrobe fixes of 2026-09-05 left open

Landed the same day (PS3, PS15, PS18, PX3, PX10, PX25, PR9, PM16 of the
campaign-3 play runs): containment is now derived from every affirmative
ledger that says a body is bearing a thing (`commit_scene_state.
derive_borne_containment`); a transfer whose source is neither holding the
object nor standing in its room is refused (`_refuse_unheld_transfers`); a
mint the same diff moves between itself and its match is no longer folded
into it; a wardrobe's opening statement takes nothing off; a garment put back
on consumes the object it became; the sanitiser refuses a thing for what it
IS rather than for a word inside its name; the beat's `world_facts` were
recorded in a chat-scoped ledger (retired with the channel, 2026-09-26); and a
dialogue memory names the addressee only by a label its owner holds. Two
residues (two more closed when the channel was retired):

1. **A posture that MEANS carried, with no bearer named.** PS3's own live case
   is not reached. The establish wrote `poses: {canteen: {posture: "slung"},
   brass_hand_lamp: {posture: "hooked"}, folding_rule: {posture:
   "pocketed"}}` -- a posture and nothing else: no `support`, no `held_items`,
   no contact whose manner the ledger records as bearing. The derivation is
   affirmative by construction, so it says nothing about those three, and the
   rule that would reach them needs the ONE thing the engine already owns and
   does not export: `spatial_fov._POSTURE_TOKENS`, "the one place the engine
   already reads a posture token", which enumerates the ways a body holds
   ITSELF up. The rule in its complement form -- *a thing whose posture is not
   one of the ways a thing stands on its own, in a room with exactly one body,
   is borne by that body* -- needs a predicate over that table exported
   through the `world/spatial.py` facade (`posture_class` cannot serve: it
   answers "standing" for `upright` and for an unknown word alike). Until
   then the Director must name the bearer, and no prompt says so.
2. **PM23's refusal-without-routing.** Nine `Resolve reconciliation` warnings
   in one run, five in turn 20 alone, for a document three people signed in
   the prose and nobody signed in the state. Both specialists refused with a
   correct destination ("unindexed held item belongs to objects", "target
   wharf_slip is not an indexed entity") and no route to it. That channel is
   the Director orchestrator's, not persistence's, and none of it is built.

<a id="unbuilt-1-138"></a>

### 1.138 An anchor with no bearing is placed in the middle of the room

**Found 2026-09-06 while widening § 1.137's gate.** `spatial_fov._place_anchors`
places an anchor against the wall its `dir` names. An anchor with NO `dir`
falls to the last branch and takes a seeded INTERIOR cell instead --
`1 + seed % (w - 2)` by `1 + (seed // 7) % (d - 2)` -- so it is spread, but
spread through the middle of the floor rather than around the walls.

Two consequences, and the second is the one that matters. Furniture is mostly
against a wall -- a rail, a stair, a hearth, a counter -- so an interior cell
is the wrong prior for the thing being placed. And two anchors drawn from the
interior are closer to each other on average than two on opposite walls, which
is what makes the sound path shorter.

**CORRECTED 2026-09-06:** an earlier draft of this entry said undirected
anchors land "near the room's centre" and are "stacked". They are not; they
are seeded across the interior. The measured cells for four undirected anchors
in one `large` room were (1,4), (1,1), (4,4) and (3,1). The effect is real and
the mechanism is separation, not collision.

Measured, two bodies at `rail` and `stair` in one `large` room:

  * anchors with `dir` n and s: path signal **0.0332**
  * the same anchors with no `dir`: **0.0796**, 2.4x stronger

`measured_proximity_rel` answers `across` either way, so the ANCHOR model
knows they are apart and the GRID does not. With the near field off this
never showed, because the grid was not consulted; turning it on makes a
whisper carry across a large room between two people the anchor model calls
`across`, which
`test_a_whisper_the_sound_model_calls_inaudible_gets_no_reply` catches
exactly.

**MEASURED, and it is small.** Across the owner's 854 live anchors in 282
rooms: **823 (96.4%) already carry a `dir`**, none is pinned to a cell, and
**31 (3.6%) have no bearing**. So the defect reaches one anchor in twenty-eight,
and the fixture that caught it -- two anchors, both undirected -- is an
unrepresentative shape a test author wrote, not what the world looks like.

**The rule, stated as a class:** a thing with no stated bearing is against a
WALL, like most things in a room; which wall is seeded, from the same
`_seed(room_id, aid)` the interior placement already uses, so it stays
deterministic and stable across reads. Implemented by seeding a bearing and
falling through to the existing wall path, so there is one placement model
rather than two.

**Order, as it actually went (superseded 2026-09-06).** This entry asked for
this first and § 1.137 second, on the reasoning that widening the sound gate
would ship the whisper regression in the case the estimate is worst at.
§ 1.137 landed first anyway, and the regression did not appear: the whisper
fixture the argument rests on carries two undirected anchors, which is 3.6% of
anchors twice over and not what a room looks like. The fixture was given
bearings (96.4% of live anchors have one) and the suite stayed green. So this
is still worth doing and is no longer blocking anything.

<a id="unbuilt-1-143"></a>

### 1.143 A door exists twice and only one of them decides passage

**Found and fixed 2026-09-06, descent turn 20.** The player pried a bulkhead
open a hand's width, knelt, and put a lamp through the gap. Perception showed
him unbroken steel, and the narrator wrote it beautifully -- "nothing showed
in the beam" -- with his companion standing on the other side of it.

The beat encoded the opening perfectly, in the wrong place. The objects hand
wrote `entities.plant_room_bulkhead_door.state = {closed: false, ajar: true,
gap: "hand's width", dogged: false}`; `rooms.sub5a_plant_room.adjacent` came
back EMPTY, so the edge still read `closed_door`. Sight, sound, scent and
passage all read the EDGE, and the edge had not moved.

**Both representations reached the page.** `narration._visible_portal_states`
builds its answer from door-like ENTITIES and from edge barriers, so the
narrator was handed "open" and "shut" about one door in the same payload.

**Fixed at the cause, in the objects card, both packs.** The entities chunk
already carried the shape of this rule -- "WHERE A THING IS IS NEVER ONE OF
THOSE KEYS ... a state word saying a thing is hidden is read by NOTHING" --
and it now extends to ways: a door between two rooms is an edge, its barrier
is what decides passage, and an entity for the same door is scenery that may
say what it is made of and not whether it is open. A lid, a drawer, a
cupboard, a case -- anything with no room on the other side -- stays the
entity's, which is the line that keeps the rule from eating the useful case.

**And at the symptom, in the payload.** The first cut dropped every entity
door-claim where the room had a door edge, and a test caught it: there are
TWO branches and only one of them is a guess. An entity carrying a portal
`link` NAMES the two rooms it joins, so it IS that doorway and keeps
speaking; the other branch infers a door from a word in the entity's name
(`door|gate|hatch|portal|shutter`) and that guess now yields to the edge. A
cupboard door has no door edge to contradict and keeps its own state.

The third word-list guess this day to turn out to be the defective half of a
pair, and the first where the bound alternative was already sitting beside
it.

**THE NEXT BEAT WAS THE EVIDENCE, and the whole chain worked.** Descent turn
21: the player hauled the bulkhead fully open, the objects hand DECLINED it
and named the right owner -- "Event 2: opening a door between rooms is an
edge barrier change belonging to spatial, not entity state" -- the engine
rerouted `objects -> spatial`, and spatial wrote
`rooms.sub5a_service_spine.adjacent[].barrier = open_door`. Both sides read
`open_door`, and sight between the two bodies went from `none` to `full`.
The clause removed the wrong destination and the reroute found the right
one.

**And the leftover warning was a real defect, not noise.** The beat still
reported the change unencoded. `director_evidence._omission_subject_encoded`
walks every diff channel for the subject, and for `rooms` it reads room ids
and a room's `name`. A DOORWAY's identity in that channel is an ANCHOR KEY
-- `effective_anchors` mints `door:<to>` for every edge, and an authored
doorway is keyed by its own id -- so the door sat in the diff under
`anchors.plant_room_bulkhead_door` and the check could not see it. Its own
docstring had named the failure in advance: "a channel this does not walk is
a channel in which a CORRECT encoding reads as an omission, and the answer
here is what decides whether the Director is asked to repair a beat that was
already right." It now walks anchor keys and their descriptions, and stays a
containment check -- a subject the diff never mentions is still an omission.

<a id="unbuilt-1-144"></a>

### 1.144 A voice turned a body away from what its hands were on — FIXED 2026-09-06

**Measured, chat 117 turn 45, and the symptom was two subsystems away from
the cause.** Aurel stood at a fire door with a lit cone lamp aimed through
the gap; the composer answered "Through the opening, only darkness" and the
narrator wrote it; the room beyond was four paces of concrete deck.

Everything the engine needed was stored and correct. `stations.at =
fire_egress_door`, `poses.relative_to = fire_egress_door` ("an eye pressed to
the narrow seam"), a `contacts` row for his right hand on its handle, and the
door's anchor bearing `n` in the room he stood in. He ended the beat facing
`s`.

**The cause: he said one sentence to Sarah, one room below.** `infer_focus`
ranks addressing above everything but a disorienting jump, and addressing
someone in ANOTHER room resolves to an EDGE focus -- which `infer_facing`
reads as the whole body's heading. So a word over the shoulder spun him 180
degrees, and the lamp's cone, which takes its axis from the holder's facing,
turned to point at the wall behind him. Sight, the lamp's cone and every
left/right in the prose are downstream of the same value.

**Fixed by a precedence change, not new machinery** (`address_focus` in
`world/spatial_frames.py`): a cross-room address yields to a pose this beat
declared against a fixture of the speaker's own room. CO-LOCATED addressing
keeps its rank -- looking at the person you are talking to is right, and is
what mutual focus is for -- and a body with no fixture claiming it still
turns toward the doorway it speaks through, which is what stops the fix from
quietly ending conversation-across-a-threshold for every story. A voice turns
a head, not a body braced against something.

**Worth the owner's eye: ATTENTION and FACING are one field.** `focus` is
what a mind is attending; `facing` is where a body is pointed; the engine
derives the second from the first and they are not the same fact. This fix
picks the one case where the disagreement was measured and loud. The general
form -- a body's heading following what it is DOING while its attention goes
where it likes -- is a bigger change and is not made.

<a id="unbuilt-1-145"></a>

### 1.145 Sixty-two percent of bodies have never faced a direction

**Noticed as a frontier-stub cosmetic, measured, and it is neither.** The
service-core chain mints edges like `{"to": "..._11", "barrier": "open_door",
"axis": "Upper service-core riser"}` -- an axis label and no `dir`. That
looked like a stub property furnishing would fix. It is not: measured
read-only against the author's `engine.db` on 2026-09-06, across 103 scenes,
570 rooms and 756 edges --

  * **465 edges (61.5%) carry no `dir`.**
  * **426 of them (56.3% of ALL edges) are on a FURNISHED room** -- a room
    with a description, written by a hand that stood in it.
  * **211 of 559 bodies (37.7%) carry a facing. The other 62.3% have none.**
  * **In 48 scenes of 103, not one body in the story has ever faced a
    direction.**
  * Anchors are FINE by comparison: 31 of 844 (3.7%) lack a `dir`, which is
    § 1.138's figure unchanged. The gap is entirely in EDGES.

**What it costs.** `infer_facing`'s moved branch is `travel_bearing(old_room,
new_room)`, and where the edge carries no bearing it returns None -- "we will
not guess a heading", which is the right refusal. So a body that walks
through an undirected doorway arrives with no heading and keeps none until
something turns it, and everything egocentric is downstream: left and right
vanish from the prose, `egocentric_frame` cannot say what is ahead, a cone
lamp has no axis to point (§ 1.144 is this same value read one layer down),
and a sound that grades audible cannot be placed at a doorway. In half the
author's stories that is the permanent state.

**Why it happens: `dir` is taught as OPTIONAL.** The rooms chunk's shape line
publishes `adjacent:[{to,barrier,distance,vertical?,dir?,...}]` and nothing
said what omitting it costs, so it is omitted. Addressed 2026-09-06 with a
clause in both packs naming the class -- `dir` is the only thing the engine
has to derive left and right from, an edge without one leaves a body with no
heading at all, and the engine will not guess because a guessed heading is a
body told it walked north when nobody said so.

**A clause is not a fix until the next few beats prove it** (CLAUDE.md), and
this one changes what a model writes rather than what the engine does, so the
figures above are the thing to re-measure.

**NOT DONE, and it is the owner's call because someone drew the line
deliberately:** `spatial_orientation.derived_edge_bearings` already invents a
bearing for exactly these edges -- every doorway both sides left silent -- so
the sense composites have somewhere to lay a neighbour out. Its docstring
scopes itself out of this on purpose: "It decides which wall a doorway is in,
and nothing else -- not that a room lies north in the world, **not what a
body would learn by walking it.**" Feeding it to `travel_bearing` would give
62% of bodies a heading tomorrow, and would also have the engine tell a body
it walked north on the strength of a hash. The boundary is real; moving it is
a decision, not a repair.

<a id="unbuilt-1-148"></a>

### 1.148 The median room has nowhere to stand

**Measured while answering the owner's "player perception culling might be
too aggressive", 2026-09-06. Culling is not the constraint. The FIRST
version of this entry got the consequence wrong and the owner caught it;
the correction is the useful part and is kept below.**

Across the author's `engine.db`, 760 bodies and 2909 feature rows:

  * **11.7% of feature rows are culled.** 340 by the cone, ONE by light.
    The observer receives 88.3% of what the room holds.
  * § 1.147's fix, correct and found in play, moved **2 rows of 2909**.

And the rooms, across 570 of them:

  * **292 (51.2%) carry NO anchors at all. The median room has zero.**
  * Mean 1.5; p90 is 5; max 10.
  * **Anchor count does not scale with room size.** `small` averages 2.7,
    `large` 2.5, `medium` 2.9. A 4x24-pace corridor and a wardrobe get the
    same budget. 243 rooms are `unsized` and average 0.0.

**WHAT IT DOES NOT COST: THE PROSE.** This entry first claimed the narrator
fills the gap by inventing fixtures, citing chat 117 turn 55 -- "rough
courses of cinder block, expansion seams, and the black iron brackets
anchoring conduit overhead". Checked against the room record, that is
wrong. `cable_trays` IS an anchor of that room ("Overhead cable trays
suspended beneath the concrete ceiling"), so the brackets are that anchor
rendered finely, which is the narrator's rule 3 working exactly as written.
The cinder block and masonry are the room's FABRIC, which no room should
mint and no anchor should be spent on. The absent signage was what the
player's own turn asked him to look for. Nothing was invented.

**The narrator's licence is correct and load-bearing, and the near-miss is
worth recording: a clause forbidding it to "add a noun" was drafted and not
shipped.** It would have suppressed the texture, sensation and
gesture-flesh that are the narrator's actual job -- the layer rooms do not
mint and should not. The owner's framing of the tension is the right one:
the narrator is an INVENTIVE role that may not make OBJECTS, which is a
genuinely awkward seat. The line that resolves it is not invent-versus-not
but WHAT SURVIVES THE PARAGRAPH: it may say what a thing is LIKE, and not
what a room HAS. Texture expires and costs nothing; an object either
persists, and the world model contradicts it, or vanishes, and the reader
was told something untrue.

**WHAT IT ACTUALLY COSTS: EVERYONE IS NOWHERE IN PARTICULAR.** An anchor is
what a body STANDS AT, and the engine spends them on:

  * **10.4% of bodies (81 of 780) stand at a real anchor of their room.**
  * **15.0% of multi-occupant rooms (23 of 153) have two anchored bodies**
    -- the condition `proximity_rel` needs before it can say whether two
    people are near each other or across the room from each other.

So `near`/`across` is unanswerable for the overwhelming majority of pairs,
a gesture has nothing to be made against, a contact has nothing to be
anchored to, and the sight model's `line` basis -- which needs a measured
station -- almost never runs. These are the same numbers CLAUDE.md already
quotes as the blocker on tightening the whisper rule ("`across` needs both
bodies anchored, and measured over the live corpus only 6.7% of bodies
carry an anchored station"). It is one shortfall, and it is a SIMULATION
poverty that the narrator's compensation keeps invisible: the page reads
full either way, which is exactly why it went unmeasured.

**Addressed 2026-09-06** with a clause in both packs: anchors are places a
body can BE, scale them to the place, and what is not a PLACE -- a smell, a
draught, a quality of light, the room's own silence -- is the room's own
(`desc`, `light`, `quiet`) rather than an anchor nobody can stand at.

**THE CLAUSE WAS WRONG ONCE ON THE WAY, and the owner caught that too.** It
first told the spatial hand that texture was not its job and was supplied
downstream. That would have caused drift, for a mechanism worth writing
down: the narrator's own sensory memory is `past_narration`, capped at
`_PAST_NARRATION_TURNS = 12`, while a `desc` never expires. A place
revisited after that window is rendered from its descs and nothing else, so
a thin desc is exactly how the same room comes back a different room. The
durable sensory record IS the spatial hand's, and the ephemeral rendering
is the narrator's; telling the owner of the durable layer to stop writing
it would have left the consistent layer empty and the inconsistent one
carrying everything. The clause now says the opposite: write the texture
into the descs, because that is the part that lasts.

**PROPOSED, NOT BUILT: an engine notice, on the `unsourced_light_rooms`
pattern.** The clause fires when a room is WRITTEN; the shortfall shows up
when a room is USED, and a room minted small and then occupied for fifteen
beats is never revisited. The channel already exists and is the only one
the ownership boundary allows: a deterministic read of COMMITTED state at
merge, composed into `engine_notices`, reaching the Director next beat --
no prose anywhere in it, and the narrator never in the loop. Candidate
trigger measured before proposing, which is the discipline the 2026-08-30
triggers died for want of: *furnished, large-or-at-least-60-paces-squared,
fewer than 3 anchors* fires on **31 of 238 occupied rooms (13.0%)** and 89
of 544 furnished rooms (16.4%). Frequent enough to matter, rare enough not
to be wallpaper, and arithmetic over the room record rather than a guard
reading prose.

<a id="unbuilt-1-153"></a>

### 1.153 The corridor grows as fast as the player walks it, so a search can recede forever

**Found by playing, not by reading**, chat 117 turns 75-77. Under a stated
ten-minute in-fiction deadline (the solvent barrier evaporating behind them)
the player declared a specific search three beats running -- "a ladder, a
stair, a shaft with rungs, a hatch in the ceiling, anything vertical" -- and
each beat the world answered by extending north and promising it further on.
The last answer was Sarah's: "a junction box or vertical access rung set
should appear within twenty meters."

**Nothing here is misbehaving.** The rooms are honestly furnished --
`_13` arrived with four anchors and a real description, so this is NOT
s1.148's underfurnished frontier. Each room genuinely has no way up, and
saying so is the correct answer. The Director is not stalling; it is
answering truthfully about a place that keeps being extended underneath it.

**THE MECHANISM.** `structure.prepare_frontier_expansion` mints "approached
frontier nodes" -- so stepping into the last room of the chain mints the
next one, and the stub inherits the axis it was minted from precisely so
"the frontier keeps moving" (its own comment). Walking the corridor is what
creates more corridor. Measured live at turn 77: `_14` existed, blank, before
anyone had seen it.

**THE CAP IS REAL AND IS NOT A NARRATIVE BOUND.** `max_planned` stops the
chain; for this story it is **200**, and the structure held **23** planned
rooms. So the goal can recede another 177 times. That number is defensible
for exploration and useless as a limit on a chase -- the bound exists in the
wrong currency. It is measured here rather than changed because lowering it
would cost every exploring story something real, and because a cap is the
owner's to set.

**WHAT IS ACTUALLY MISSING** is not a smaller number. It is that nothing
connects a DECLARED SEARCH under narrative pressure to whether the world is
allowed to defer again. A search that can always be answered with "further
on" is a search with no failure state, and a deadline the fiction has
already announced is exactly the pressure that should force the world to
commit: the rungs are in this room, or this axis does not have them and the
player has spent the time finding that out. Both are answers. "Twenty meters
further" is the one shape that costs the player their clock and tells them
nothing.

This is the same question the owner raised about giving the story planner
authority to act between turns -- a receding goal under a countdown is
precisely what a planner tier would close, and it cannot be closed by any
single stage: `director_resolve` answers honestly about the room it was
given, and the room it was given was minted a beat earlier by deterministic
code that has never heard of the deadline.

**AND THE SHAPE OF THE ANSWER MAY BE SMALL, measured at turns 106-109 of the
same story.** The corridor stopped growing the moment a CHARACTER asserted
where it ends. Asked the right question -- where does a technician go, not
where does a cable go -- the companion answered from her own expertise that
a personnel companionway sits "at the terminal bulkhead where the riser
intersects the primary circulation vestibule... it is at the northern end of
this run", and the next beat produced `upper_service_core_riser_20`, named
Terminus Twenty, with a rated fire door closing the line. Three beats
earlier the identical search had receded twice.

So the frontier is not committed to growing; it grows when nothing in the
beat says where the ground stops. A terminus asserted by any mind with
standing to assert it -- a character's expertise, a planner's intent -- may
be all that is needed, which is a far cheaper fix than a cap and does not
cost an exploring story anything.

<a id="unbuilt-1-155"></a>

### 1.155 A fixture is two records with two owners and no link, so the player was not told what his own hands had just done

**The clearest instance yet of the question this engine keeps rewarding: is
this fact stored twice?** Chat 117 turn 80, traced end to end.

The player levered the spalled concrete around a ceiling conduit sleeve to
find out whether the gap would take shoulders. The Director answered him,
completely and correctly:

* dice: roll 16 against DC 12, **success**, margin 4
* `resolved_event`: "broad enough now to pass a pair of human shoulders"
* `state_diff.entities.conduit_ceiling_penetration.state`:
  `clearance: "shoulder_width"`, `bypass_accessible: true`, `gap: "widened"`

**And the beat on the page never says whether it worked.** The prose renders
him sizing the gap against Sarah's shoulders and stops.

**THE SAME FIXTURE IS TWO RECORDS.** Room `_13` holds an ANCHOR
`ceiling_sleeve` (the `spatial` hand's, `state_diff.rooms`) and the scene
holds an ENTITY `conduit_ceiling_penetration` (the `objects` hand's,
`state_diff.entities`). After the beat:

  | record | owner | says |
  |---|---|---|
  | entity `conduit_ceiling_penetration` | `objects` | "spalled concrete lip pried away to leave an opening **wide enough to pass a pair of human shoulders**" |
  | anchor `ceiling_sleeve` | `spatial` | "expansion bolts sheared away to leave **an accessible gap** carrying a steady updraft" |

The objects hand recorded the outcome. The spatial hand left its anchor in
the turn-79 wording. Neither is wrong within its own channel, and each hand
did its own job.

**AND PERCEPTION RENDERS THE ROOM FROM THE ANCHORS.** So the chain runs:

1. `environment_percept`'s dedupe key mixes a `feature_sig` built from each
   feature row's `desc` -- and those rows are the anchors. Stale anchor,
   unchanged signature.
2. Measured, the player's env key across three beats:
   t78 `env:699c3aa40d:dc9baf35f6`, t79 `...:dc346aab50`,
   t80 `...:dc346aab50` -- **byte-identical to the beat before**.
3. `standing_verdicts` therefore answers `unchanged`.
4. `_render_view_english`, for the player tier without an explicit look
   (`delta = player and not full_render`), drops an unchanged standing
   percept outright: `elif (delta and p.dedupe_key in prev_standing and
   p.kind not in ACTIVE_STANDING_KINDS): continue`. The whole room goes,
   features included.
5. The player's view collapses from **2928 characters on t79 to 758 on
   t80**, losing the room line, his own pose, and every mention of the
   sleeve (`penetration` 0, `gap` 0, `shoulder` 0; the single "sleeve" hit
   is inside Sarah's quoted dialogue).
6. The narrator is told in its own prompt that it has "NO access to the
   objective event record, other minds, dice, or the director". It rendered
   what reached it and correctly refused to invent a result.

**NOBODY MISBEHAVED.** Every stage is individually right, which is why this
is worth a register entry rather than a patch to whichever one looks
guilty. Step 4 is a good rule -- not repeating wallpaper is most of what
makes the player view readable. Step 6 is the firewall doing its job. The
defect lives in the JOIN that does not exist.

**THERE IS NO ANCHOR-TO-ENTITY LINK ANYWHERE.** `anchor_entity_id` in
`commit_mapping`/`commit_room_registry` binds a LOREBOOK to an entity and is
a different thing. Nothing relates the anchor `ceiling_sleeve` to the entity
`conduit_ceiling_penetration`, and their ids do not even resemble each
other, so no reconciliation is currently possible -- not by the orchestrator
on the merged diff, where every other cross-channel judgment already lives.

**Three candidate answers, and choosing between them is the owner's:**

* **One record.** A fixture that is a place a body can stand AND a thing the
  fiction acts on stops being two rows. Correct, and the largest change.
* **A link, then a floor.** Give an anchor an optional entity id and let the
  orchestrator reconcile the pair on the merged diff -- the seam where the
  architecture already says cross-channel judgments belong. Needs the hands
  to state the link when they mint, which is a prompt change on both.
* **Widen what "the room changed" means.** Fold the co-located entities'
  state into `feature_sig`, so an entity the beat changed makes the room
  read as changed even while the anchor prose is stale. Cheapest, and it
  only fixes the SUPPRESSION -- the player would then be shown the room in
  its stale words, which is better than silence and still not the truth.

**Why this matters beyond one beat:** the failure is specifically invisible.
It costs the player the result of their OWN action, on exactly the beats
where they did something that worked, and it leaves no warning anywhere --
the run was clean, two warnings, neither about this.

<a id="unbuilt-1-157"></a>

### 1.157 A room in a chat with no lorebook is never registered, and the escape route died of it

`persist/commit_room_registry.py`, building the upserts:

    book_id = anchor_books.get(owner) if owner else default_book
    if not book_id:
        continue

**A room whose owner resolves to no book is dropped, silently.** No row, no
warning, no note. And the module's own header says the registry "is a
deterministic projection of every scene write".

**THE SCHEMA DISAGREES WITH THE CODE, in writing:**

    owning_book_id INTEGER REFERENCES lorebooks(id) ON DELETE SET NULL

The column is NULLABLE, and `ON DELETE SET NULL` means a bookless row is not
an error state the table is protecting itself from -- it is a state the table
is designed to arrive at whenever a book is deleted. The commit path refuses
to write the row the schema was built to hold.

**MEASURED (engine.db, read-only, 2026-09-06).** Splitting the corpus so the
legacy population does not flatter or inflate the live one:

  | | chats |
  |---|---|
  | registry holds NOTHING (predates it) | 35 |
  | fully in sync | 58 |
  | **partially in sync -- the live bug** | **11** |

In those 11, **14 of 43 rooms** have no registry row, and the signature is
uniform: every one is an interior or a vehicle car --
`lilaeve_vagina_interior`, `mirelle_sulmirath_interior`, `vaginal_canal`,
`Mirelle Sulmirath_throat`, `room_site17_elevator`, `room_elevator_interior`,
`shelter_elevator_car`. Those are exactly the rooms carrying
`parent_entity`, whose owner has no anchored book. Separately, **12 of 106
chats hold no lorebook at all**, and in those every Director-minted room
fails to register for the second half of the same condition (`default_book`
resolves to nothing).

**AND IT COST THIS STORY ITS WAY OUT.** Chat 117 has no lorebooks. Its 23
registered rooms are all ones the STRUCTURE path wrote directly --
`prepare_frontier_expansion`'s mutations carry an `owning_book_id` copied
from the origin's registry row, so the riser chain registered itself. The
four the Director minted through `state_diff.rooms` did not:
`corridor_sublevel`, `lift_interior`, `upper_service_core_plenum_13`,
`upper_service_core_plenum_14`.

`prepare_frontier_expansion` READS `room_registry`. So `plenum_13`, being
absent from it, can never expand a frontier -- the plenum chase cannot grow
the way the riser chase did (s1.153). Turn 86, live:

    Blocked movement: no passable route from 'upper_service_core_plenum_13'
    to 'upper_service_core_plenum_14' (barrier=separated); position unchanged.

`plenum_14` holds an edge back to `plenum_13`; `plenum_13` holds no edge
onward. A one-way passage, and the crawl the player is making along it is
prose over a position that does not move.

**THE FIX IS NOT TWO LINES, and that is why this is registered rather than
patched mid-run.** Registering under a NULL book is right, but the dedup
index beside it reads

    WHERE chat_id=? AND owning_book_id=? AND retired_turn_id IS NULL

and `= NULL` matches nothing in SQL, so bookless rows would register and
then silently stop deduping against each other -- trading a missing row for
a duplicate one, in the table whose entire job is identity. Any fix has to
carry `IS NULL` through every owning_book_id comparison. The registry owns
identity, dedup and retirement, and `docs/guides/DATABASE.md` has a
checklist for exactly this kind of change.

At minimum the skip should not be silent: it is the one branch here that
discards a write and says nothing.

<a id="unbuilt-1-162"></a>
### 1.162 The doorway cone reads no cell, so a body a pace from the door is graded by the room's size

`world/spatial_senses._opening_view_cap` grades what a body in the next room
shows through an opening: in the cone (the strip from the doorway through the
centre to the far wall) it is `full`, beside the doorframe it is `none`, and
with "placement unknown" it falls back on the room's size, which for a
`large` room is `conduct` (it was `shapes` until 2026-10-05; see below). The
bearing test reads `_anchor_dir(at)` and nothing else, so a body stationed by
`cell` and no anchor is "placement unknown" even though the grid knows
exactly where it stands.

Measured on the owner's chat 126, turn 9 (2026-09-16): Hinami stood at cell
(6,1) of the reception parlor, one pace from the north wall the door is in,
and her step into the treatment room -- graded from its origin room, which is
the right rule (PA1) -- reached Mirelle through the open door as "Hinami
moves, too little of it to make out". The parlor is authored `size: small`
and measured `extent: 8x10`, and the extent wins (`size_from_extent`), so the
fallback was the large-room one. Across the checkpoints of chats 100-126 the
same fallback capped a cell-placed body 20 times (chats 122, 123, 126).

**Why this is filed and not fixed.** Reading the cell is one line -- bearing
from the room's centre to the cell, then the same one-sector test -- but on
this very beat it would have graded Hinami `none`: at (6,1) she was two paces
to the side of the door and one pace back, which is exactly the "beside the
doorframe" case the cone is built to refuse. The spatial hand had placed her
there as `near` Mirelle, who stood AT the door anchor; the fiction had her
leaning past Mirelle's shoulder to look through it. So the honest fix has two
parts, and the second needs a measurement: read the cell, and let a body
`near` one that stands at the door share the door (or let the hand write the
door's own cell, which its stations chunk already asks for). Until both land,
a cell-placed body in a large room is graded by the size fallback.

**The fallback is `conduct` -- what they do, not their face (owner,
2026-10-05).** Measured that day across every distinct scene in the owner's
checkpoints (3,473 scenes, 133 chats): 1,296 next-room body pairs had sight
admitted by the edge, 766 graded `shapes`, and 659 of those were this
fallback on one side or both (344 both sides, 164 the target's, 151 the
observer's own doorframe), with 748 of the 751 targets carrying no station
at all -- "placement unknown" was the ordinary case, not the hedge. The act
channel gave each one's act as motion, so in 26 chats a body standing in a
lit room through an open door "moves, too little of it to make out". The
fallback was written to withhold a FACE before the ladder had a rung for
exactly that, and the owner took that option ("go ahead"): after the change
the same 1,296 pairs grade 530 `full`, 674 `conduct` (the act delivered, the
face withheld -- a stranger is still a figure, never a descriptor) and 92
`shapes`. A dulled eye now sees those bodies' doing as motion where it saw
nothing (`tests/test_view_cone.py`).

**The 92 left were an authored far edge, and the cap is gone (owner,
2026-10-05).** A `far` or `remote` edge capped sight across it at `shapes`
(`far` is 20-75 m by `normalize_edge_distance`), written with the same intent
("a figure across a courtyard is `shapes`, not a readable face") and the same
effect: a wave thirty metres off across a far edge was "moves, too little of
it to make out", one doorway away. Asked whether it too should become
"what they do, not their face", the owner: "Maybe that bit is just an
overzealous feature overall." It was removed, and with it `FACE_READ_M` (a
line up a storey through a window capped at `shapes` past 25 m, "an engine
number"). The same 1,296 pairs now grade 622 `full`, 674 `conduct`, 0
`shapes`; the shape left one doorway away is a body still going through a
shut door, and the interaction micro-round gives its act as motion again,
as the composed view does (it was handing the whole act through a locked
door -- the Long Gallery leak, PC1).

<a id="unbuilt-1-168"></a>

### 1.168 A crossing written at the resolve was refused at every shut door — FIXED 2026-09-26, residuals open

Under the prose contract every position the encoder writes is the prose's
own statement of a crossing, so `_unreachable_position_writes` judges it as
the declared mover's is -- a shut door on the way contested and asserted, a
wall refused (`director_prose.declared_moves`, 6bcb76a9, for the owner's
chat 126 idx 9). At the resolve that never happened: `director_resolve` read
the stage's record off the context after `director_prose.attach_record` had
moved it into `out["orchestration"]["prose_contract"]` and cleared it, so
only the interpret's crossings counted as declared and every crossing the
resolve wrote through a shut door was popped with "Unreachable position:
nothing declared a move for ...". Found in the 2026-09-26 morning story
(`docs/experiments/FEELINGS_EXPRESSIVE_CARDS_2026_09_26.md`): a grandmother
"crosses the dining room, opens the kitchen door, and goes through" on two
beats, the encoder wrote her into the kitchen both times, the scene kept her
in the dining room, and her lines to the boy in the kitchen -- "Tomaso. You
saw my Marco." -- never reached him, the page reading "No one answers." The
record is now read from the stage's orchestration; replayed on the story's
own checkpoints and records, both refusals become crossings, and
`tests/test_prose_contract.py` holds it behaviourally (the old wiring test
only read the source).

Residuals, from the same trace, not built:

- **The refusal reaches no Director.** The floor warns (`ctx.add_warning`)
  and tells nobody (`ctx.tell_director`), so the next beat's author writes
  the same crossing and is refused the same way; it repeated here.
- **A refused crossing leaves its placement behind.** The floor writes no
  `movement_refused` and does not strip the station and pose the hand wrote
  for the destination (`_strip_unreached_placement`), so a body kept in the
  dining room carried a kitchen-side pose.
- **Declared keys are folded raw.** `declared_moves` casefolds the encoder's
  own key; the floor folds the canonicalized `positions` key, so an encoder
  key such as `character:<id>` would miss the declaration.
- **The player's own reach into the next room moves nobody.** In the same
  story the interpret recorded `movement: null` for "Tomaso leans into the
  dining room doorway" (resolved as a pose against the door, the door left
  shut) and for "Tomaso sets the small paper parcel on the table in front of
  Rosa" -- a table in the room he was not in. An act whose object stands in
  another room implies the walk to it; nothing reads it so, and the answers
  from that room were lost to him ("No one answers.").
- **The door the prose opened stays shut.** The resolve's own event said she
  "opens the kitchen door, and goes through"; the encoder wrote the crossing
  and no open edge, though its card asks for one when the prose opens a door
  (`encoder/core.txt`), and nothing checks the two against each other -- so
  the crossing now lands and the door behind her still reads shut to
  everyone left in the dining room.

<a id="unbuilt-1-169"></a>

### 1.169 A player one open stair away is neither seen nor seen to leave — a lead, unclassified

Found 2026-09-27 by the blind judges of the bare-card replay
(`docs/experiments/BARE_CARD_REPLAY_2026_09_27.md`), on the `rival` test
story, turn idx 16 (a copy of the story's database; the story itself lives
in the job's scratch directory). Before the beat (checkpoint 15) the player,
Tomas Rell, stood on the `stage` and Isolde in the `orchestra_pit`, the pit
steps between them `open` (a stair, vertical up). After it (checkpoint 16)
the player was in the `rehearsal_room`, behind the closed door off the
stage. The player's input that beat was empty; `director_interpret` (474
characters) names no one and `director_resolve` never names the rehearsal
room. Isolde's perception carried two standing rows and no trace of him --
neither standing above her nor leaving -- and every reply to it spoke to
him from memory: the story's own full card, and three layouts of the bare
card. Unclassified: which stage moved him, and whether a silent body across
an open vertical connection should be perceived (§1.131's vertical
residuals; the geometry note's "no elevation ... a pit ... not modelled").
Read every stage of that turn before forming a view.

<a id="unbuilt-1-193"></a>

### 1.193 A declared follow carries the player — BUILT 2026-10-09, residuals open

The owner's ruling D1 (`Design.md`, "A player's declared follow carries her"):
`director_interpret.follow_op` is restored from her own span, a walk she
declares with the one she follows waits on theirs and reaches the resolve's
author as her input, a place she declares wins over the follow, and a follow
goes only where its follower last saw the one it follows or heard a sound
they made. What it leaves, measured on the Brackwater run (scratch story
166, `docs/experiments/PLAY_2026_10_07_brackwater.md`) and over the play
db's 19 stored player follows -- two wait (166 turn 4607, 160 turn 4552),
fifteen are a follow with no walk of hers, and two follow someone in another
room:

- **A follow begun across rooms still walks at the onset.**
  `director_movement.follow_walk_waits` acts only where the two began in one
  room. Turn 4598 -- the player in the chapel, the pilot rejoined from her
  bubble on the low walk, "follows her back over the bridge and down to the
  landing stage" -- still walks the player at the onset, so the pilot's
  whisper "as they pass the counting-house junction" (F88's first case) was
  graded with the player already aboard. The two walks would need one clock
  to meet on.
- **An act of hers after the walk keeps the walk at the onset.** "I follow
  her to the door and knock": a step of her own after the walk that does
  anything but walk happened where the walk ended, so the walk is hers at
  the onset, where the cast perceives it, and the words on the way are
  graded from the door. No stored follow has one.
- **An act of hers along the way is done where she stood.** Where the
  resolve's encoder writes no step of hers, she rides only the steps that
  move the one she follows after her last act of her own
  (`follow_through_the_steps`), so an act left behind -- a latch lifted at
  the gate before she goes up after them -- is done at the gate. An act done
  along the way with them -- a hand on the rail of the stair they climb
  together, which turn 4607's stored resolve sourced to her -- is then done
  where she started as well: telling the two apart needs the act's place,
  which a ledger row does not carry. No stored beat reaches the carry: on
  every one where the player followed a body beside her that changed room
  in a step (18 in the play db, 14 in the owner's), a step also wrote her
  room.
- **What a follower heard is graded, not recorded.** A follow toward someone
  in another room goes where she last saw them or heard a sound they made
  (`_perceived_room`): their own lines at their own volume, their footfalls,
  a noise the diff sources to their body, graded as the outcome grades them
  but without a live channel or the addressed rescue, neither of which
  places a body. The beat before is read from its committed resolve, and
  only a sound made where both still stand (`_FOLLOW_HEARD_BEATS_BACK`, one
  beat). A sound a thing made in their hands (a knock sourced to the door),
  a line from two beats back, and where she saw them go are not read, so a
  follow begun after they left her sight and hearing moves nobody unless her
  declaration names the way, and says so ("nothing perceived to follow").
- **Lost in the dark.** Beside the one followed, a mind that neither saw
  them when the beat began nor heard them go stays where it is. A walker's
  footfalls are graded where its walk ends, through a room's sound field
  only, so in rooms with no sound geometry, and in a large dark room, a body that walks off in the dark is not heard going. A follow reads the follower's own senses: a blind mind sees nothing, a deaf one hears nothing. On every stored beat where the one followed left a
  mind's side (31 in the play db, 26 in the owner's), the follower saw them
  when the beat began.
- **A character following the player still arrives at the end of the
  beat.** The relation carry lands a character's position on the engine's
  closing step or its own last write; moving it into the player's onset
  steps would put the character's own resolve acts, made where it stood, at
  the destination.
- **Other human players** get `follow_op`, but neither the wait nor the
  chronology carry, which read the primary player's follow only.
- **A follow toward someone who then stays put** leaves her own walk
  standing and the follow with it: she goes on alone after their answer
  (160 turn 4552), and the floor, which needs a place the one followed
  reached, does not end it.
- **Where the resolve's encoder writes her walk, it times it.** Handed the
  waiting walk as her input, the encoder may write her steps itself, and
  then they stand as written rather than riding the steps of the one she
  follows; on the turn 4607 replay it interleaved the two walks a step
  apart, and then parted them at the stair onto two landings for one door.
- **The decision model's follow question** (`jev_questions/following_ops.txt`)
  says to answer no where bodies "move together without one following the
  other"; whether that loses a walk "a step behind" someone is unmeasured
  (turn 4607's was kept). The encoder's part now says the same, so the two
  agree.

<a id="unbuilt-1-194"></a>

### 1.194 A vessel moving within one room stays in it — BUILT 2026-10-09, residuals open

The owner's ruling D2 as worded (`Design.md`, "A vessel moving within one
room stays in it"; `spatial_transit.settle_departures`). What it leaves:

- **A departure that names no space now stands where it set off.** Eighteen
  stored TARDIS writes, the same in both databases (chats 30, 56-59, 63, 64,
  153, 154 and 157), now stand under way where they set off, behind a shut door, and a later untimed `docked` lands them there -- the stored next beat does, chat 157 turn 4481, which re-docks the TARDIS on the beach it left, its `departed_from` spent; among them chat
  157 turn 4480, written before the transit card asked a departure to name
  its space. The card is the guard; the one stored dematerialisation written
  after it (chat 159) named `new:the time vortex`.
- **A journey bound elsewhere through the room it left is in no room.** Turn
  4605: the Grebe, lying in the down-channel, set off back for the stage
  naming the channel as its route -- the room it set off from. Bound
  elsewhere, it is leaving, and the 2026-09-25 rule drops that route, so the
  boat is in no room, its deck's doorway severed, until it docks at the
  stage two beats later. It is the one stored write of this shape in either
  database.
- **A departure named only in a movement row.** Chat 154 turn 4398's
  interpret wrote the ship's movement to `new:in the time vortex` and a
  transit with no route. No transit reads a movement row, and a row cannot
  say whether the place it names is the space crossed or the place bound
  for -- read as the route, a car heading for a town the world holds would
  be stood in the town -- so the ship stands on the beach for that step; its
  resolve named the vortex as the route a moment later.
- **A mooring written as state, not transit.** In round 1's replay of turn
  4607 the encoder wrote the pilot making the Grebe fast as `state.moored:
  true` and no `transit`, so the boat stayed `in_transit`, bound for the
  stage, with its line on the stage cleat -- and, bound elsewhere, in no
  room, not docked. A later write brings it in; nothing reads `moored`.
- **`sealed` with no route severs the doorway** (F37 in
  `UNBUILT_PLANNING.md`); a sealed carrier whose route the world holds keeps
  a shut door onto it. The opening card's `transit_note` fragment still says
  a route is set "only if occupants could perceive or exit into it".
- **The hatch is not carried** through a later write that omits it, as the
  route and `departed_from` are, so such a write reads as shut while under
  way (`_under_way_barrier`).
- **The light (the owner's D3, wave 2).** At turn 4601 the Grebe now stands in
  the channel with its deck open onto it, and the coat a boat's length off
  still reads `none`: the channel is `dark` and the lantern lights the deck.
  Lit `dim`, the same scene grades the coat at `conduct`.

## 2. Roadmap

<a id="unbuilt-2-6"></a>

### 2.6 Scene-boundary coherence pass

Established-earlier wins unless the later fact is load-bearing for an active
thread, in which case the older is retconned *with a logged entry*. The logging
is the point: a silent retcon is the failure mode. Verified absent.

<a id="unbuilt-2-14"></a>

### 2.14 Clothing regions: the guess is reported, the authored answer is inert

**The report landed 2026-08-19.** `attire.guessed_spans` had no production
caller — its own docstring described the hand-off in the present tense while
the loop stayed open. It now runs at the attire commit seam and tells the
Director, which is the only stage with the fiction in front of it and can
answer with `coverage`. Told rather than repaired, because the cue tables are
the thing that does not know, so a second deterministic guess would be the same
guess. Measured while it was open: 110 of 560 live worn garment records carry a
span the tables guessed, twenty of them a nagajuban sitting on the torso alone,
so those bodies report legs and groin bare while wearing a full-length
under-kimono.

The open half moved to **§1.72**: the authoring surface the Director is being
pointed at does not work. `placement` and `add[].covers` are documented in both
prompts, passed correctly at the call site, and lost to an ordering bug before
they are applied. Until that lands, the report asks for something the engine
cannot yet accept — which is worth knowing when reading the warnings.

<a id="unbuilt-2-15"></a>

### 2.15 Movement is an arrival, never a crossing

**Raised 2026-08-02**, after "step outside" landed correctly and still read
wrong. A turn that moved a body rendered the destination and nothing else, so a
plaza crossing or an elevator ride read as a cut.

**Two-thirds landed 2026-08-14, verified 2026-08-19.** A journey is now a
standing thing: a declared walk survives a beat that says nothing about it and
advances one edge per beat (`director_movement._travel_continues`,
`scene.approach`), a long edge takes two (`_LONG_EDGE_DISTANCES`), and the leg
is computed BEFORE the prose is written and handed to the author as
`travel_in_flight`, so the scenery changes on the page in the same breath as
everything else. That decided need (1) against the Narrator — the ENGINE owns
the crossing and the Director may only stop it (`travel_interrupted`) — and need
(3) is met by the `adjacent`/`near`/`far`/`remote` tier the edges already carry,
so a doorway step is unaffected.

**Need (2) is open, and it was always the hard one: what a body PERCEIVES
mid-crossing.** The honest answer is "both rooms, briefly" — the same union
`_source_channels` computes across a beat, and possibly the same mechanism.
Today a mid-walk body is simply IN the room the leg put it in, so a corridor
crossed over two beats is perceived as two rooms in sequence rather than as a
passage between them. Truthful, and thin, which is what this entry was raised
about.

**Related, from the alpha 6.3 physical-ledger work (its residual list was
dissolved 2026-08-19 and deleted 2026-09-04):** nothing derives a station from within-room movement INTENT ("she
crosses to the hearth"), because there is no within-room approach concept for it
to read — room-level `scene.approach` is the only staged-movement memory there
is.

<a id="unbuilt-2-27"></a>

### 2.27 Room geometry and occlusion — PROTOTYPE, on `main`

Built 2026-09-02 in an isolated worktree and on `main` since 2026-09-03
(`world/spatial_fov.py`, `tests/test_room_geometry.py`; the planned-room
handoff beside it, `tests/test_planned_room_handoff.py`):
[`design/DESIGN_ROOM_GEOMETRY.md`](design/DESIGN_ROOM_GEOMETRY.md).
`world/spatial_fov.py` derives a per-room grid from the size tier, places
anchors from their bearing with a seed keyed on (room, anchor), derives body
cells from stations (with a new `cover` field for the far side of a fixture),
and casts sight by recursive shadowcasting with eye height from posture. The
verdict is folded into `visual_level_between`, so a body behind the counter
is refused to every sight consumer at once; the composer renders what
survives as a person would say it; the Director reads `payload.sightlines`.
Subtracts only on evidence it has, and a room without geometry composes
byte-identically (pinned). Measured first: the cone bites on ~27% of live
bodies and body occlusion on ~11%, so the residual is the INPUT — whether
the Director writes stations, and `cover` at all, once the two clauses ask.

Extended on `writers-room` 2026-09-04 and not yet on `main`: extents and
shapes (§ 2.37), the light and sound fields on the same grid (§ 2.34,
§ 2.36), and `offset` along a wall for an anchor or a doorway (the map
editor, § 2.26).

What is still open, from the note's own §10: no elevation (a balcony, a pit
and a stairwell are not modelled); seeded placement can disagree with
specific prose and nothing surfaces it -- narrowed by `offset`, which lets a
HOST put an anchor where the prose put it, while nothing reads the prose;
`cover` on an interior anchor is relative to the room's centre; two doorways
on one wall both cast only where extents let both neighbours fit, and the
lint reports the pair that does not; the features sentence is a per-room
opt-in that changes a room's whole view once one anchor is annotated; the
archive round-trip of the new fields is asserted, not measured. Per-cell
light left this list on 2026-09-04: it is the light field (§ 2.34).

The same commit carries the planned-room handoff (note §8): the plan's seed
reaches `director_establish`/`director_resolve` and the spatial hand as
`payload.planned_rooms` when a body enters a planned stub or has one
adjacent through a non-wall barrier; planned exits are protected at commit;
a described stub settles. Residual: the count of stubs developed per trigger
in a played story is unmeasured -- the 2026-09-04 debug runs played the
handoff (`experiments/DEBUG_RUN_2026_09_04.md` F2: a plan published before
the first beat reached the opening; F13: the planned-exit churn, fixed) and
counted nothing. The mapping stage's own `planned_context` path went with the mapping
model (2026-09-04): the world-context compiler reads the plan for a named
room and raises a planning need for an unplanned one, so there is one seed
per room again.

<a id="unbuilt-2-28"></a>

### 2.28 The day cycle's residuals

Landed 2026-09-03 (`world/day_cycle.py`, `Design.md` "The day moves with the
clock"). What it deliberately does not do:

- **The derived label is a phase word, never a clock reading.** A story that
  opened at "08:42" reads "midday" three hours later, not "11:42". The hour
  is on the clock record (`simulation_clock.hour_of_day`) for the Director,
  and a fiction that measures time in minutes can keep declaring readings --
  each one re-anchors exactly. Rendering the derived hour in the opening's
  own style (24h, 12h, stardate) would need a format the engine does not
  have, and a minute-precise label asserts a precision most fictions do not.
- **`sheltered` is treated as daylight.** A porch, an overhang, a covered
  market get the sun's light one step down only under fog or cloud, not for
  the roof. `room_exposure`'s keyword fallback reads an unrecognised room as
  `enclosed`, so a room the reader cannot place keeps its declared light --
  the failure direction is "a square that should have gone dark stayed lit",
  never the reverse.
- **Evening is dark.** 19:30-22:00 on a 24-hour day reads `dark` outdoors,
  which is right for a town with no street lamps and wrong for a summer
  latitude; seasons and latitude are not modelled, and a lamp is an entity
  with `light_source`, which is the intended way to light a square at night.
- **Charter posts do not know about night.** A post is a continuous watch
  and stays manned around the clock; only the OFF-duty half of the town
  responds (no errands while resting, commons only in the social phases).
  A day/night shift concept on posts, and sleep as a need the resting phases
  restore, are the two obvious next steps and neither was asked for.
- **Presim gets a day only when generated inside a story that has one.** The
  anchor comes from the story clock at generation; a charter generated before
  the opening turn is anchored on the greeting-seeded display label if it
  reads, else runs its prehistory unanchored as before.
- **The label-to-phase table is a word table** (`day_cycle._PHASE_WORDS`),
  the same kind `dressing.backdrops._TIME_BUCKETS` already was, and subject
  to the same rule: it is what the cycle can READ, and a label outside it is
  left standing rather than misread. Expect it to be widened; a widening
  changes which stories get a cycle, never what the cycle does.
- **A skip lands at the START of the phase it names** (2026-09-03, replay
  N13), never inside it: "by dusk" is 18:00 whatever the duration said, and
  "late in the afternoon" is the afternoon's first minute. The phrase is
  read by the same word table, so a phrase it cannot read changes nothing.
  The light duty loads on a `sustained` interpret element under an anchored
  day; an instantaneous beat that crosses a phase boundary by its floor
  charge alone still relies on the backstop's manifest half.

<a id="unbuilt-2-37"></a>

### 2.37 Room fidelity — what the 2026-09-04 prototype left

Built 2026-09-04 on `writers-room`, not yet on `main`:
[`design/DESIGN_ROOM_FIDELITY.md`](design/DESIGN_ROOM_FIDELITY.md).
A room may declare `extent` and `shape`; the layout lint reports where a
scene's geometry cannot all be true; the backdrop brief draws the picture
from the same record the composer and the geometry read. Measured on a copy
of the owner's database: 0 of 589 rooms carry an extent; the lint finds 9
rows in 4 of 104 scenes; the pre-change and built geometry agree on every
room and body. The passage record (note §5) and `composite` (note §2) landed
2026-09-05 with the map editor's completion (note §11): `scene.passages`,
edges carrying `passage: id`, the five readers resolving through it, the
merge's `sync_scene_passages`, the doorways routes; `tests/test_passages.py`,
`tests/test_composite_rooms.py`. Left open, each an owner decision or a build:

- **A passage's `state` has no reader.** The record carries it so F22's
  "latched" against `open_door` (§ 2.35) has a home on ONE object rather
  than as prose against an edge; nothing consults it yet, and what a latch
  does to `edge_passable` is a decision -- a barrier word (`closed_door`) or
  a state on an open one -- before it is a build. The Director still writes
  barriers on edges (the schema has no passage channel); the sync reads
  which edge changed. A frame split that keeps one room of a pair leaves a
  passage naming a room the frame lacks; the hygiene drops it and the
  surviving edge reads per edge again -- the fail-open, not a merge of the
  two frames' records.
- **A Room tool that writes a region's `look`.** `regions.set_region_look`
  is the seam; since later on 2026-09-04 the World Browser's room card calls
  it through `PATCH /api/chats/{cid}/regions/{region_id}` (`web/world_routes.py`),
  so a HOST sets a look by hand. Nothing in the Room does: the registry's
  only writer at commit still enters names. A `describe_region` tool (look,
  and the `brief` the regions note left for the same reason) is one tool,
  one mandate kind, and a card clause.
- **The Director has to write extents.** 0 of 589 rooms carry one. The
  clause asks for one where proportion matters; whether the hand supplies
  it, and whether `size_disagrees_with_extent` then fires often enough to
  want a repair rather than a report, is a play-test question.
- **A rim is not a curve.** A round room's doorway is a gap in an
  axis-aligned wall line between the two boxes; the arc itself is a
  staircase of cells. Right for sight through the door, coarse at the arc.
- **The lint's embedding check reads only beared edges.** 578 of 923 exits
  carry no bearing and cannot be placed; a contradiction through one of
  them is not seen. The same 578 are the ceiling on what any room geometry
  can draw, cast through or picture.
- **The viewer camera multiplies pictures** (up to nine parts by eight
  facings per room) and is behind `backdrop_continuity` for that reason;
  whether the edit-from-anchor path keeps the room the same room under a
  turned camera is unmeasured, because no image call was made here.
- **Every existing backdrop is redrawn once** (299 images across 74 chat
  directories on the owner's install): the brief is keyed, as the module's
  own rule requires, and every room with an exit or an anchor hashes anew.
  A one-time cost, named rather than hidden; there is no migration that
  could map an old key to a new one without lying about what the old picture
  shows.
- **`size` from area loses one distinction** (a 2x18 gallery and a 6x6 room
  are both `medium` floor). The proportion sentence carries it to the
  picture; the proximity ladder does not. If `near`/`across` should read the
  long side for a corridor, that is a `proximity_rel` change, not a size one.

<a id="unbuilt-2-38"></a>

### 2.38 The room designer's shortcuts: what they leave (2026-09-27)

Built on `worktree-jev-character-tracking`
([`DESIGN_PROSE_CONTRACT.md`](design/DESIGN_PROSE_CONTRACT.md) § The room
designer; measured in
[`ROOM_DESIGNER_SPEED_2026_09_27.md`](experiments/ROOM_DESIGNER_SPEED_2026_09_27.md)):
the standing rooms and the doorways that fit arrive before the first step,
the check runs itself, the extent sets the size word, a doorway can be
dropped from the draft, and Jev says when a design is finished. Left:

- **Jev's stop reads only the rooms the designer OWES.** A designer that
  chose to build a further place in the same beat -- an inside, a second
  room the prose opened -- is stopped as soon as the owed ones pass. Not
  seen in the measured runs; watch for a beat whose prose builds two places
  and reserves one.
- **`doorways_that_fit` is one doorway at a time.** A place joined to two
  rooms must fit both at once, which only the check says; the second run on
  the yard spent five steps on exactly that before `drop` and the re-fit
  existed. A pair search is not built (looked at again 2026-10-08, the
  procedural-generation round: the one-doorway search is now cheap enough --
  2.6 ms a screened wall, 48 ms a confirming merge on a 33-room town --
  and whether a blind pair search over fixed trial shapes would close two
  doorways at once is untested). What it needs: lay both rooms out by the
  check's own walks (`layout_index`), find walls of the two that face each
  other across a gap a place could fill, derive the place's extent and both
  doorways' offsets from that gap, and confirm the pair with one real merge
  and the whole check -- a constructive solve, about 150 lines and its
  tests, and a case of its own when the two rooms lie in different walks.
  A place with two doorways is no leaf, so `leaf_rows` cannot judge it.
- **What the packer and the doorway rules of 2026-10-08 leave**
  (`world/spatial_pack.py`, `director_rooms._pack`/`_place_doorways`/
  `_doorways_that_fit`; `docs/design/DESIGN_PROSE_CONTRACT.md` § Where
  along the wall):
  - A wall's own surface filed as a fixture is the designer's content error,
    and code cannot tell it from a floor-to-ceiling fixture without reading
    its desc. The elevator shaft's first drafts (chat 160 turns 2 and 5):
    where two full-height runs share a wall, the packer reports instead of
    packing; where the heights do not collide (turn 2), the draft is now
    clean with the shaft's lower walls still filed as an anchor. A card
    clause naming the class is the owner's call.
  - A full-height fixture and a waist-height one may share a cell: the
    check, and so the packer, count one height at a time.
  - A fixture laid end to end with others drafted beside it may stand at
    one end of its wall; what a fixture is for relative to a doorway (a
    doorstep at a door) is the prose's, and `offset` is the designer's lever.
  - A level doorway written from both rooms whose far-side bearing would lay
    one room onto another stays as the merge leaves it, bearingless: the
    Gale house's door in chat 166 turn 22 -- the landing is up a stair but
    written on the walk's storey, and the check lays every storey on one
    plane. A storey-aware layout (the procedural-generation survey's item 6)
    is what clears it. By turn 26 the world holds that door, with no
    bearing, and code gives no doorway the world holds a wall: written `s`
    from both rooms again, it stays as the merge leaves it. The narrower
    rule -- a held doorway with no bearing derived like a new one -- is
    built behind `director_rooms.DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY`,
    off, for the owner; on, it changes none of the 33 recorded final
    drafts: turn 26's door is tried and taken back, as turn 22's is.
  - A level doorway whose two drafted copies are not opposites and that
    code leaves as written -- a far copy whose place along its wall the
    designer wrote, a doorway the world holds, a derivation taken back --
    is merged with no wall, as before the round, and the check does not
    say so. A sentence naming it would hold the Gale house's design unclean
    at every check while the lint lays every storey on one plane.
  - A doorway onto a room the check's walk could not place, or a new place
    whose id sorts before its part of the world, starts a walk of its own
    that re-lays that part in another order, and a standing collision comes
    back reversed or via another room: a row about two rooms the draft does
    not hold, which the designer cannot clear. The search no longer offers
    such a wall, but a designer who writes one meets the row, and so does
    the commit's once-told warning, since both compare rows by key. In the
    recorded runs of 2026-10-08, 1 of 33 final drafts held a row about two
    rooms its draft did not contain (chat 165 turn 1). Comparing a
    collision by the two rooms it names clears it, and is built behind
    `spatial_lint.LAYOUT_COLLISIONS_COMPARED_BY_PAIR`, off, for the owner.
    Measured: it clears that final draft and the 6 of 150 recorded designer
    checks that held such a row, leaves clean finals at 32 of 33 and clean
    first drafts at 24 of 31, and over the 4,108 beats stored in the play
    database's checkpoints it stops the commit's once-told warning
    reporting 3 of its 12 new collisions (chat 27 turn 84, two rows; chat
    165 turn 2, the chandlery and the boat shed). A walk laid in another
    order can also move a standing collision onto another pair, which the
    pair does not catch.
  - Such a place is also the doorway search's slow case on a large town:
    every wall the walks cannot judge goes to the whole check (every room of
    chat 166's 33-room town a host, no deadline: 24-25 s for an id sorting
    first, 8 s for one sorting last); inside the search's 1.5 s, the rooms
    left are named (`not_tried`).
  - On a host standing on a site plan, a wall the walks refuse is put to a
    merge and the whole check before it is refused, since the merge may
    stand the place on that plan. Of the seven recorded in-beat searches
    only chat 160's turn 2 has such a host (one of five), and its searches
    take 0.37 s against 0.32 s; a town whose every host stands on a plan
    pays a merge for every wall the walks refuse.
  - The install (`install_prepared_rooms`) runs neither the packer nor the
    doorway rules: a design the world has moved under since the job made it
    fails the install's check and stays a seed.
  - `lane` is read by the engine and offered by no card.
  - Fixtures other writers mint at the merge (the encoder, the Writers'
    Room) are not packed; extending the packer to them waits until this
    one is measured live.
- **The layout lint does not lay out a neighbour behind a solid wall**, so
  a room placed on that side overlaps it unseen. The offered doorways never
  use a wall with any neighbour on it; the check itself still cannot see
  the overlap. The fix is the lint's (lay a `wall` edge's room out for the
  collision test and for nothing else), and it would add rows to standing
  scenes, so it wants a measurement first.
- **One false hold remains**: `room_done_missing` reads 0.50-0.54 on the
  finished osteria (one step), and 0.52 on the Gale house landing in the
  2026-10-08 live replay of chat 166 turn 22, which held a design the check
  had passed. Its bar is the owner's to move.
- **The rooms chunk still tells the designer to furnish planned rooms "in
  view".** Written for the spatial hand ("the first time a body enters it or
  has it in view"), it ships verbatim in the designer's sheet, while the
  designer owes only the planned rooms the beat ENTERS (Jev's `enter__`
  questions). One run on the lighthouse rail developed seven unentered stubs
  and redrafted the designed harbour wall whole -- 81.7 s for its first
  step, then the wall, unclean. Stubs are no longer drawn in `surroundings`,
  which removes the loudest invitation; the chunk's clause is the owner's to
  narrow for the designer (rooms in view of any actor are now built between
  turns and stand when the beat opens -- `install_prepared_rooms`, on by
  default since the owner's 2026-10-08 rulings -- so the in-beat designer
  meets a stub in view only in these cases: its design is not made yet, it
  came back unclean, it was refused with its one continuation spent, it was
  made for another frame's brief of the same room, or the stub is a frontier
  space held open for the Writers' Room).
- **A room built between turns never gets the stop.** With no prose there is
  nothing to read the room against, so a design between turns ends on the
  model's own submit or at the 8-step cap. It is now put into the world, not
  just seeded. The plan's purpose could be that text (`room_done_missing`
  over the brief): of three Gale house designs replayed on 2026-10-08, one
  dropped the purpose's "a man's boots drying beside it". The step cap is
  the in-beat one; out of band it could be the owner's to raise. One of
  three Gale house runs ended at it with a chair and the bed on one cell.
- **The route is the owner's.** On the owner's NanoGPT `z-ai/glm-5.2:thinking`
  at `medium`, one loop took 162-174 s and met the 150 s wall; every
  measurement here is plain `z-ai/glm-5.2` with `reasoning_effort` `off`.
- ~~**A prepared design's effect on a room is unmeasured.**~~ **MEASURED
  2026-10-08** (replay of chat 166 turns 3, 9 and 26 on a db copy, 52
  room-author calls, about $0.22).
  - Built in, the bell loft, the low walk and (two of three runs) the Gale
    house stood when the beat opened, and the in-beat designer was not
    started for them.
  - A built room is what its plan says, not what a beat's prose later adds.
    The run's in-beat low walk carried the guide rope and the second bridge
    the Director's prose had put there; the built one has the tide stain,
    the Gale doorstep and the joins, and the encoder may only turn a built
    room's doorways.
  - The reach of the cast and of bubble travellers (the owner's same-day
    choice) is not replayed live; it is tested with fake designers only.
- **The prepared cache rolls back with a reroll.** `PREPARED_KEY` is a world
  row, so a checkpoint restore returns it to the checkpoint's copy and drops
  the designs and brief fingerprints made after it. A reroll therefore
  builds in from the checkpoint's copy, and a design filed after the beat's
  checkpoint is made again (spend only; the room is never built twice). A
  failed design's back-off (`failed`, `failed_turn`) and a refusal's filing
  (`refused_turn`) live in the same row. So a reroll takes them back with
  the beat, and its commit tries the room again at once (spend only;
  `test_a_design_run_that_fails_is_filed_and_waits_before_it_is_tried_again`).
  A run still designing when its beat is rerolled is stopped and writes
  nothing (`core.jobs.cancel_from`). The call it was inside is paid for and
  thrown away, and the rerolled commit's run designs that room again.
- **The card asks the room author to redraft a standing room's physical
  change, and the engine discards it.** `room_author.txt` (en and ja) says
  to redraft only what the prose physically does to a standing room, while
  `director_prose.keep_new_places` keeps only a standing room's doorways to
  places built that beat, and warns. Narrowing the clause or keeping the
  change is the owner's call. Today only the encoder's doorway edits write a
  standing room's physical change.
- ~~**A whole record can outrun an inspect result.**~~ **FIXED 2026-10-08**:
  `inspect_rooms` is fitted room by room (`director_rooms._fit_inspection`,
  `ROOM_INSPECT_CHARS` = 16,000): whole records in the order asked while
  they fit, the first always (its drawing dropped before its record is
  cut), the rest named under `not_shown` to ask for again. A raw
  6,000-character prefix had cut chat 166's low walk (11.5k) mid-record.
- **A design seeds only the brief it was made from** (2026-10-08): the
  prepared cache keeps a design while its room is a stub and its brief
  unchanged, near or far, and `prepared_rooms` handed the beat's own
  briefs refuses a design made from an older one.
- **A design overrides the plan's measured geometry.** The bell loft's and
  the Gale house's plans say `exposure: enclosed`. Both built designs (and
  the run's in-beat bell loft) wrote `sheltered`, which puts the sky into
  their light (`room_light`). `planned_geometry` carries the plan's fields
  onto the stub, and nothing keeps them through a design. The same class
  exists in-beat.
- **A plan's own fixtures stay beside the design's.** The bell loft's stub
  carries the plan's `bell_wheel` and `bell_louvre`. The built design added
  `bell_beam`, with the bell on an eyebolt, and did not mention them, and
  the merge keeps all five: the spatial merge keeps a fixture until
  `remove_anchors` takes it (`world/spatial_merge.py`,
  `_merge_anchor_fields`). The card tells the designer everything in a
  planned room is its own; the run's in-beat designer wrote `remove_anchors`
  for both instead.
- **A frontier space held open is left for the Writers' Room.** This is the
  main session's ruling on the review of the landing (2026-10-08), under the
  owner's ruling 1 that the Room plants ahead. `rooms_to_build` drops every
  stub `structure.provisional_room_ids` names, for every actor, so the job
  never designs it and the install never builds it. Built from the name the
  grammar gave it (chat 166's `the_open_water`, purpose empty), the space
  was spent before the Room could claim it: a claim keeps the name of a room
  with prose, and its purpose and geometry reach the registry and never the
  room. What is left: a held-open space in view stays a name through its
  opening ("Through the opening is The Open Water.") until a plan claims it
  or a beat enters it. Nothing asks the Room to claim a held-open space in
  view sooner than its fill comes round.
- **Two designs each clean alone can contradict each other.** In the turn-3
  replay, the open water's continued design and the built low walk took the
  same cells of the landing stage's east wall. The install builds the first
  one the players meet. The next commit's job runs the same test
  (`_install_test`), merges what stands into the scene it designs on, and
  takes the other up again there, once (`PREDEVELOP_CONTINUATIONS`). Refused
  again after that, it is filed not clean and waits as a seed for the beat
  that enters its room, and no beat's install re-checks it, even if the
  world later makes room for it. Not replayed live.
- **A failed design is retried for as long as its room is in reach.** A
  design that raises waits 2 beats, doubling to 16
  (`PREDEVELOP_RETRY_BEATS`, `PREDEVELOP_RETRY_BEATS_CAP`, the Writers'
  Room's own fill back-off). So a room that can never be designed costs one
  designer run in sixteen beats for as long as it stays in an actor's view.
  Whether failures should stop after some count is the owner's call.
- **A run that raises outside a design is not backed off.** A design that
  raises is filed and waits, but the rest of a run is outside that guard:
  the actors, the plan's briefs, the install's own test, the cache writes
  and the card loads. A raise there files nothing. The job is recorded
  failed (`core.jobs.history`), and the next commit runs it again, so a
  raise that repeats repeats at every commit. It makes no model call (the
  designer is the only one, and it is inside the guard). An ask made while
  it ran still gets its run (`core.jobs._run`, the third review of the
  landing). Whether to file it with the design back-off is the owner's call.
  Not seen live.
- **One design a room, across frames.** The cache keeps one design per room
  id, and every frame's run prunes it; a design is kept while any live frame
  holds its room as the stub it was made for. Where two live frames hold the
  same stub under different briefs (a door one frame opened, a neighbour one
  frame named), the design made for one frame's brief is that frame's to
  build. The other frame's run neither takes it up nor designs over it, and
  its beat that enters the room designs it in the beat. Not seen live: a
  bubble exists while its travellers are out of the player's range, so one
  stub in reach of two frames is rare. Keying the cache by room and brief
  would build both.
- **A follow-up run is stamped with the turn that asked.** A commit landing
  while a run designs asks for one more run under its own turn
  (`core.jobs.submit_latest`). A restore can discard that commit while the
  run, which read an earlier beat, goes on. The ask then stays in place: the
  next run reads the restored world and files under the discarded turn
  number, so a failure's back-off filed there can end a beat or so early
  (spend only).
- **`PREDEVELOP_PER_TURN` (4, per run of one frame's job),
  `PREDEVELOP_CONTINUATIONS` (1) and the retry back-off (2 doubling to 16)
  are the owner's to set.**
  - 4 is the most stubs in the player's reach on any of the run's 30 beats
    (the low walk at turns 4-5). With every actor's reach a busy frame can
    owe more; the players' rooms go first and the rest wait for the next
    run.
  - The bound is per frame so that a bubble traveller's rooms never wait
    behind the player's view (`OFFSCREEN_BEATS_ARE_UNCAPPED`).
  - 1 continuation is one more designer run per brief at most.
  - The back-off is the Writers' Room's own (`FILL_RETRY_BEATS`,
    `FILL_RETRY_BEATS_CAP`).

<a id="unbuilt-2-39"></a>

### 2.39 The site plan: sight with height, drops, flight, terrain

Step 1 landed 2026-10-03 ([`design/DESIGN_SITE_PLAN.md`](design/DESIGN_SITE_PLAN.md)):
a room may stand on a plan at a position and a floor height, the structure map
draws it there, and a layout lab result converts into engine rooms. What it
leaves, in the order the owner agreed:

* **Sight with height (step 2) landed 2026-10-04** for a body a storey
  away through a window. Still flat: an anchor in the garden (a tree, a
  wall) does not stand in that line, sound and hearing across storeys read
  the edge's barrier only, and two plans never see each other.
* **Drops as facts (step 3) landed 2026-10-04.** Still open: a drop is
  only known between rooms of one plan; a body that falls off a ledge
  inside one room has nowhere to fall to; the movement floor still refuses
  a body through a window nobody opened, which is the right floor and means
  "she climbed out of the window" needs the window opened in the same beat.
* **Flight landed 2026-10-04** (`stations[body].altitude_m`). Still open:
  a flier walks the doorway graph like anyone -- over a garden wall into the
  next lane is no route; nothing renders "hovering" unless the pose says so;
  hearing ignores altitude; a body coming down from height is never reported
  as a fall, because landing and falling look alike to code.
* **Vistas landed 2026-10-04** (`world/vistas.py`). Still open: the room
  designer cannot mint one mid-scene, the narrator's sensory manifest does
  not list them (it gets them through the view), and the visibility table is
  the engine's, not the owner's, until the owner rules on it.
* **Ground is flat**: no slope, no cliff, no bank between two cells.
* **A plan is derived in play since 2026-10-04, room by room since
  2026-10-09** (`site_plan.derive_site_plans`, every merge;
  [`design/DESIGN_SITE_PLAN.md`](design/DESIGN_SITE_PLAN.md), "A plan
  derived room by room"): a group of rooms spanning two storeys or more is
  laid out by its doorways and stacked by its stairs, a room that cannot
  stand is left off and named (`site_plan_unplaced`), an open side slides
  along its wall, a plan is written only where the rooms it lays out span
  two storeys, and a derived site is recomputed every merge from where its
  rooms stood: a room keeps its ground against a room that comes onto it
  while its doorway keeps it there, a room whose place a beat moved is read
  again as one reading lays it, a room is reached through an edge either
  room declares, what no chain of doorways reaches is laid where it stood,
  and a join stands whole or each plan keeps its own. So a beat may
  re-measure its room, a room added later never takes the ground of one still standing where it stood (an open side nobody stands in slides along its wall for a room with one place; one somebody stands in never does), and a town whose joining walk is lost keeps
  both halves. Measured on the play database: 54 rooms sited after one merge
  before, 163 after; played forward through the stored checkpoints, as
  commits store sites, 173 (laying whatever stood first, as the round before
  did, 158: chat 165 held 7 of 30 rooms, chat 27 3 of 13). Still open:
  - **One-storey groups get no plan.** On one, the landscape would hide far
    places behind their buildings and measure them by the plan; off one it
    walks the graph. Measured: 156 groups of 659 rooms, 87 of which would
    hold a plan of 227 rooms between them (most of them two rooms), 7 rooms
    refused; and three groups of two storeys whose other storey the plan
    refuses or cannot reach lay out on one (chats 40, 160 and 161, 8 rooms),
    so they hold none either. A change to far sight in every one-storey
    world: the owner's call. (A group of one storey that stood on a plan of
    two -- the half of a town cut off when its lane was lost -- keeps where
    it stood.)
  - **A room whose doorways carry no bearing stands on no plan** -- a plan
    never guesses a wall (chat 166: 10 of 34 rooms, the closure's pile
    houses among them; the beach of chats 150-159 places one room of each
    group of 21 to 23).
  - **An unmeasured stub street too short for the stubs the plan hangs on
    it** is measured longer only for the rooms the closure split
    (`frontage.FRONTAGE_MEASURES_STREETS`): chat 165's opening town keeps 10
    of its 30 rooms refused off its plan, the Back Row's four siblings among
    them, and the stubs on its designed main walk. A doorway at its seeded
    place is never slid by the plan (only an open side is), so two guessed
    squares on one wall stay refused until somebody measures them.
  - **The layout is greedy.** Of two rooms that cannot both stand, the first
    the frontier lays keeps its place -- a room still standing where it
    stood, then the measured before the guessed, a building before open
    ground -- which on a loose rectangle of open ground can be the wrong one
    (chat 166's reed flats yield to the Blackreed channel, its drying racks
    to the chandlery and the walks).
  - **Only a stack slides along an open side**, and only for a room with one
    place: an open side carrying rooms laid from it by doorways holds where
    it is, and so does the room a plan is grown from. Carrying the rooms
    laid from it too, played forward, stood two more of chat 166's rooms in
    each frame (19 where 17 stand), and slid chat 165's whole town three to
    six paces at five of its six checkpoints (60 room moves where a stack
    alone makes 5).
  - **A room a beat moves onto another storey, where its column on that
    storey is taken, leaves the plan named by no row**: no doorway was tried
    for it. The room it would land on, which the beat did not move, keeps
    its site. Chained through chat 160's stored checkpoints, its crash site,
    put on the elevator shaft's storey where the shaft stands, is the case
    (and chat 161's); the level doorway joining two storeys that put it
    there is named by no check either.
  - **A plan played forward can hold what one reading would not**: chats 160
    and 161 keep five rooms each on two storeys that one reading of their
    last scene lays out on one.
  - **The raw scene editor writes what the host typed** (`world_put`): a
    derived site in it is read into the plan at the next merge, where the
    World Browser's field edits are read at once (`_write_scene`).
  - **A stair between two rooms of one storey places nothing**, so a landing
    written on its walk's storey (chat 166's Gale house landing) stands off
    the plan; a stair still lands over where it left, whatever the plan.
  - **A town with two solved buildings** is laid on the plan holding more of
    their rooms, and the other building stands on its own (§2.43).
  - **The far layer's eye in a closed room on a plan** stands at the room's
    cell nearest the place it looks at, not at the opening it looks out
    through, and its own walls are no obstacle: from deep in chat 165's
    taproom the landing stage is said hidden by the houses behind the
    taproom's south wall (`landscape._eye_on_plan`, the far layer's own
    lane). Replayed on every perception step of chats 165 and 166, 14 of 119
    far views change once the plans stand, each by a building in the line.
  A planned building can also be laid out onto a plan by code before anyone
  has described it (§2.43, off by default).
* **A window between storeys is an anchor, not an edge**: an edge is one per
  pair of rooms, and the ground-floor door already holds it.

<a id="unbuilt-2-40"></a>
### 2.40 A level of detail for distant landscapes -- BUILT 2026-10-05, what is left

The ask: "for distant objects we might need something like the text
equivalent of an LOD" (2026-10-04); after a build that graded detail by
metres inside ordinary range was reverted (594e4f67), "all I wanted it for
was distant landscapes. like 5 or so rooms of distance or more", and "go
ahead" to: places, not people; far starts past the next room, detail by
measured distance where the world measures it, else two to four rooms off
the place and what is big on it and five or more its outline; a far place
named only once the mind knows it. Built as `world/landscape.py` (Design.md,
"A far place is seen as landscape"), from a survey of five readers and a
critic and a panel of three designs and three judges. Left:

- **People at that range**, by the plan. Showing them would need rulings on
  causality bubbles (a major character more than one hop off lives in her own
  frame and is absent from the player's), the beat aperture (`rooms_in_view`
  is "sight plus earshot", owner 2026-09-23 -- far sight inside it puts far
  townsfolk on screen and model-voiced), the `seen` ledger (which licenses
  attire deltas and prunes appearance) and hailing what is seen.
- ~~**A look AT a far place** is not an event yet~~ -- BUILT 2026-10-07
  (`landscape.looked_far`, Design.md "A look aimed far off is answered, never
  with a placeholder"): one matcher beside `vistas.looked_vistas`, answered
  as an event with the place's line or what stands in the way.
- **What the far layer cannot read**: planned registry rooms outside the
  scene (chat 114's 31-room district), frontier stubs, another locale (chat
  10's colony seen from orbit), and an event happening far off -- an event
  carries targets and no place (`UnifiedEvent`), so a Director event is
  delivered where it is targeted, at full detail.
- **The world rarely says where its far rooms are.** Ground is DECLARED
  exposure only (the keyword fallback `weather.room_exposure` uses for
  weather, light and sound misreads indoor rooms as open air and is never an
  outlook); 8.7% of the owner's rooms declare it, and 36% of live edges carry
  a compass, so 4 of 283 placed bodies in the owner's current scenes get a far
  line. From 2026-10-05 the planner is asked to declare exposure on every
  room and a compass and a measured distance on the ways that cover ground,
  and a plan keeps both (Design.md, "A plan keeps where a place is and how
  far"); older worlds stay as they are, and whether a model writes them is
  for the next live run to show. **The next live run showed** (Kirinoura,
  scratch chat 167, 2026-10-05, a fresh planner-built hill village): exposure
  declared on all seven rooms, a compass on every way, and no measured
  distance on any -- the planner set the rooms on a site plan instead
  (`site.x/y/elev_m` and extents), which measures them as well. The plan was
  rough: the stair's footprint ran over the square and the lane, and the
  hill fell 6 m from the shrine to the river. The far scenery it wanted
  seen (the river, the fields across it, the hills) it made vistas.
- ~~**A far place nobody has been to reads as its ground and nothing else.**~~
  BUILT 2026-10-08 on the owner's choice of the option this entry held
  (Design.md, "A far place reads by how it looks from a distance"): the
  planner writes `far_look` -- how an outdoor place, a building's outside or
  a region reads from far off -- and the far layer says it in place of the
  ground word, never the name of another place or of a region the mind has
  not learned. What is left:
  * **What is left of looks on places that already stand** (Design.md, "A
    place that already stands takes a far look": the Room's `set_far_looks`,
    the fill's bounded pass, a drafted town's room shape and the room
    author's card, 2026-10-09):
    - **Most of a story's places are in no far view at all**, and no look
      can reach them: the far layer reads declared exposure only, and on the
      owner's db 582 of 809 rooms outside bodies (72%), across 135 scene
      rows, declare none (2026-10-09, read by `landscape.declared_ground`;
      chat 165, a second Brackwater, 25 of 30). Declaring exposure on a
      place that already stands would change its weather, light and sound
      too (the keyword fallback stops reading it), and is the owner's call;
      nothing writes it today but a plan, the sketch for what it plants, a
      beat and the host.
    - **A look written at publish can be lost to a beat's commit** that
      prepared its scene before the publish landed, as `set_vistas`' can: a
      described room's comes back as wanted and the next pass offers it
      again; a stub's is laid again from its plan.
    - **A host's edit or clear is recorded from 2026-10-09 only**: one made
      in the World Browser before then, on a room no plan laid a look on,
      reads as never made, and the next pass may write one there. The raw
      world editor (`world_put`) marks nothing.
    - **The live pass wrote no region's look**: offered chat 166's one part
      of the map beside seven places, it wrote the seven and not the region.
      A place with no look of its own then reads by its ground at the
      outline until a pass gives it one.
    - **A sketch that hands its question on files nothing, its looks
      included**: re-run on chat 166, the answer gave the seven places it
      was offered their looks and asked for the full planner over a person
      it could not place, so none of them landed. The full loop's task names
      the same places, so they are written there, at the loop's cost.
    - **A pass waits while planting has spent the hour's fills**: a pass
      that only gave looks is not counted against planting's hour
      (`FILLS_PER_STORY_HOUR`) in either tier, but no fill is queued at all
      once planting has spent it, so in a story whose clock moves slowly the
      looks wait with the planting.
    - **The opening writes no look for the places it describes**
      (`director_establish`); the next pass offers them, a beat or more
      after the story opens.
    - **A side of a building whose look would be read from another side in
      place of a look already written there is never offered**
      (`landscape._look_lands_clear`): the far layer reads a mass's first
      look in order from the front a walk reaches, so that side reads as "a
      building" until a host writes it. The Room's own look counts: where a
      pass gave one street door of a two-level building its look and not
      the terrace side, and the stair up to the terrace room comes before
      that door in another street door's reading order, the terrace side
      waits for good. None stands in the stored corpora (2026-10-09: the
      check withholds none of the 35, 19 and 16 fronts that reach it in the
      play, live and owner's dbs). The operation itself checks the room it
      writes, never the rest of its building, so the Planner's own
      `set_far_looks` is not held to this.
    - **A side that reads the look made for another side waits a pass**: a
      pass that gave one side of a building its look and not the other --
      the cap cut the farther front, or the answer left it out -- leaves the
      other side reading the first side's look, a one-storey side's word
      said of a two-storey mass, until a later pass gives it its own
      (`landscape._made_for_another_side`). The full loop is told such sides
      are among the places it is handed, never which, and its room slices
      show no look, so it writes one without the other side's in view; the
      sketch is shown it (`another_sides_look`).
    - **One mass can carry two of the Room's looks**: a second door of a
      mass whose own view reaches the other side's room before the first
      door's is offered at a later pass, so one mass can carry two of the
      Room's looks, and the sketch is shown the other side's look rather
      than the first door's, so the two may differ in wording (review B2,
      2026-10-09). A look made for another side is not one the check
      protects: a door that reads it is offered its own (B1).
    - **An annex the closure mints for a drafted building carries no look**
      until a pass offers it or a beat describes it: unlike a split
      dwelling's sibling, it is not the same kind of room as its parent.
    - **Unmeasured live**: the room author's look on a place nobody planned,
      a drafted town's looks, the sketch's looks in Japanese and a side of a
      building shown another side's look (no stored scene holds one) -- no
      model call was spent on any of them.
  * **A flood or a fire that is not a destruction does not rewrite a look by
    itself.** The encoder may (`RoomDef.far_look`, one clause in its `rooms`
    part, en and ja) when a beat shows the place changed for good, and the
    commit keeps its word on a stub the plan seeded (`_lay_planned_looks`)
    -- not yet seen in a live run; a `region_event`'s `damage` writes a hazard
    row and leaves the look as it was. Destruction removes the room, look and
    all.
  * **The floor reads whole names, and in a script without capitals one
    name passes it unmarked.** A look carrying the name of a room the mind
    does not know, as the room is called, or of a region, is not said; a
    room's own name in its own look, written as a word, is the word for what
    the place is and is said there (`landscape.SIGHT_NAMES`, "own"). In a
    script with case the look's own capitals mark a proper name; in one
    without, nothing does, so a place's own coined name the plan writes into
    its own look against the card is said to every eye in that look --
    measured, 1 of 16 leaking looks, a Japanese inn's own name, which "own"
    keeps out of every other look ("every" also said it in a neighbour's: 2
    of 16 together). Under "own", a look naming another place by the word for
    what that place is reads by its ground: measured on Kirinoura with its
    rooms named in Japanese, 1 of 7 (a hall "above the stone stair"), where a
    floor reading every name as a name refused 6 of the 7. Left to the card
    besides: a name held nowhere in the world, and a family name inside a
    possessive with no person the world holds behind it. A one-character name
    that its own place's look does not use still matches inside a longer word
    in a script without spaces (川 inside 小川), as the people floor chooses.
  * **A part of the map's name is said to nobody.** No engine channel carries
    a region's name to a mind, so a look carrying one is withheld from every
    mind and its place reads by its ground -- save inside a place's own name
    in its own look, which the own-name pass above says where nothing marks
    it as a name (a harbour named for its town, written in a script with no
    capitals). A structure's region carries the structure's own name, so a
    re-plan that renames it renames the region, and only a host's rename
    stands over it. Letting a mind that knows a place of the region be told
    it is the owner's switch
    (`landscape.REGION_NAMES_TO_LOCALS`, off). A region named by a common word
    withholds every look that uses the word: of the 39 region and structure
    names in the two scratch dbs, one, chat 94's structure "apartment".
  * **A row of buildings that each read differently is each described.**
    Buildings that share a look are said once with their count, and a run of
    ground folds as it always did, so no mind is told about fewer places (414
    on chat 166, as before). Trading places for detail -- each distinct look
    its own row, which told minds about 347 -- is the owner's switch
    (`landscape.LOOKS_SPLIT_RUNS`, off), and saying only the nearest looks of
    a row, the rest as if they had no look, is the owner's number
    (`landscape.DESCRIBED_BUILDINGS_PER_ROW`, none). Replayed, a line averages
    259.2 characters against 126.2 (longest 473); with the cap at 2 it would
    average 252.8 (longest 447), at 1 239.8 (longest 395), the same 414 places
    told.
  * **The planner sees which places lack one only in the frontier it is
    shown** (`looks_wanted`, the nearest few, and only under the grant
    that lets it write one); its room slices still show a stub's purpose
    and exits, never its geometry or its look.
- **Off a site plan a height is inferred from the graph** -- and since
  2026-10-07 what stands between is tested there too (Design.md "What stands
  between hides what is behind it, by height"): the ground of every open
  place the way crosses, and the buildings in the angle of a corner it turns,
  placed by the edge's compass. What is left: a building with no compass on
  its edge stands nowhere and hides nothing; distances off a plan are
  estimates (`NOMINAL_SPAN_M` a room); the corner rule reads one turn at a
  time, never a winding street as a whole. On a plan, open ground now hides
  what is lower behind it; terrain between two cells is still flat (§2.39).
- **A far place nobody has been to is still described by its ground alone**
  where no look is declared ("a building", "open ground") -- the owner's
  2026-10-07 ruling on placeholders ("nothing can be made out and similar
  place holders are quite frustrating") reaches it, and the far look above
  retires it place by place as plans carry one.
- **Messy data, as found**: chat 114's TARDIS console room declares itself
  `sheltered` with no `parent_entity`, so the layer -- reading declared data
  -- has it look out over the beach to the terrace.
- **The numbers**, named to the owner: two to four rooms the place and what
  is big on it, five or more the outline (the owner's); a measured path under
  250 m mid and over it outline; the walk stops at 12 rooms; at most 4 lines a
  view, 3 places a line (the nearest two and the farthest), 2 big things a
  place, 32 places graded a walk; an eye 1 m over a roof sees past the
  building; over 7.5 m is "tall" (engine estimates). Cost: 0.09 ms a call on
  the owner's scenes; about 9 ms a body on a 625-field open plain inside a
  read pass; on a site plan about 17 ms a body on a 24-room plan of
  two-storey halls (every line to a far place is sampled four times a pace
  over the plan's slabs), against 2 ms off it -- the one cost left to cut.

<a id="unbuilt-2-44"></a>

### 2.44 The rooms the closure invents: frontages and names -- BUILT 2026-10-08, what is left

[`design/DESIGN_CHARTER_PLACES.md`](design/DESIGN_CHARTER_PLACES.md). Built:
split siblings and annexes marked, measured and laid along their street once
a hand gives it a wall, a place taken only where the room then lands on no
room on the plane; a street nobody measured lengthened to hold them and a
split dwelling's siblings named in its frame, both on the owner's ruling of
2026-10-08; names dealt into the grammar's `{name}` frames for a kind the
axis names; the closure keeping a drafted room's measurements; every split
said in the Room's review. What it leaves:

* **One call is the owner's, built OFF: whether the plan specification tells
  the Room what a frame is** (`charter_generate.PLAN_EXPLAINS_FRAMES`).
  Rooms write frames unprompted -- chat 165's grammar is eight of them -- and
  the engine fills them either way; the sentence changes only what the Room
  is told, and may lead it to write more frames in every story.
* **A street the Room measured is never lengthened at run time**, because
  the fringe re-applies the plan's measurement to a stub every beat;
  lengthening one would be a registry write, and is not built. Chat 165's
  cross walk is unmeasured, so it is measured to 30 paces and holds all four
  of the Back Row's siblings (8 sibling rows -> 0, derive 33 -> 18 pairs).
* **A sibling whose doorway onto its street has no wall yet is not counted
  when the street is measured**: only a room standing on the wall is, so a
  hand that walls the parent and not its copies leaves the copies waiting
  for walls of their own.
* **A developed street keeps its doors where its author put them**, so a
  sibling on it moves only by its own door: chat 165's main row's one sibling
  stays stacked on the main row, on the main walk.
* **What does not fit at run time is said only by the layout lint's own
  rows** (`rooms_overlap_when_placed`), whose sentence blames a bearing;
  `lay_frontages`' report -- placed, far side, measured, unplaced, paces
  short, put back, the streets a sibling could front -- reaches no reader in
  play. The closure's split warning reaches the host's launch warnings and
  the Room's review.
* **What cannot be placed is tried again every commit.** Nothing is pinned
  unless it stands clear, so a sibling with no clear run costs a pass each
  beat -- on chat 165's 30 rooms about 40 ms while all five of its siblings
  wait, and about 15 ms once its cross walk holds four of them and only the
  main row's sibling waits; about 50 ms on chat 164's -- and reads no plane while no run along its wall is free; one whose free runs all land on a room reads it once or twice every commit (14 of 375 fuzzed configurations over the stored scenes, up to about 0.25 s a commit on chat 166). A measurement the
  plane refuses is tried again every commit too, two reads of the plane
  (about 30 ms each on chat 165).
* **Rectangles only**: a round or composite street or room is left to
  whoever drew it.
* **Towns planted before 2026-10-08 carry no marks**, so their siblings are
  never laid; the measurements reconstructed the marks from the closure's
  `<berth>_<n>` minting, for measurement only.
* **The establish's own stacked rooms are not touched**: chat 165's three
  rooms on the cross walk's six-pace east wall, three on the main walk's, and
  the rest of its 18 remaining clash pairs; chat 166's five are the Room's and
  the Director's. Several doorways on one wall laid by width rather than by
  even fractions is the room-designer doorway work, not the closure's.
* **What names a kind is read off words a space separates**, so an axis in
  a script that does not space its words rarely names one. The draw that
  picks a stretch's rule still reads every word of a rule, a purpose's
  included, so a purpose that mentions another kind ties the draw and the
  stretch keeps its ordinal: chat 165's row and shed purposes say "the
  walk", so "far walk" names the walk rule and is drawn to a three-way tie.
  Preferring the rule whose kind the axis names would name more stretches,
  and would change which rule a tied axis draws in every story: not built.
  A word only some of one rule's frames write -- an article one frame opens
  on and another does not -- and a word of a kind written with an article or
  a conjunction in it (chat 115's "containment_and_intake_annex") still name
  that kind; no stored grammar with a frame has either.
* **A frontier axis with no affinity to any rule still borrows a random
  rule's purpose** (author knowledge, never a name). The kind it asserts was
  never chosen; an absent purpose would be honest.
* **A frame whose fixed words the room fold keeps** ("{name} Nagaya") folds
  every name it makes in another script to those words alone, so it names at
  most one room and the rest keep their ordinals.
* **An annex is never named**: no rule is its kind. Chat 164's 29 annex
  ordinals stand until its plan berths the walk's people elsewhere.
* **A dealt sibling name can coincide with an unlanded planned room's name
  elsewhere in the story** and be merged into it by
  `_merge_generated_rooms_by_name`; the closure sees only its own plan.
  Unmeasured; a dealt word is seeded and rarely collides.
* **The person mint does not use `NAME_SIMILARITY_FLOOR`**
  (`UNBUILT_IDENTITY.md` §1.90a).


<a id="unbuilt-2-43"></a>
### 2.43 Buildings from relations: the layout solver as a tier of the plan -- first slice BUILT 2026-10-08, what is left

The owner's choice of 2026-10-08, the fourth procedural-generation item
([`design/DESIGN_LAYOUT_TIER.md`](design/DESIGN_LAYOUT_TIER.md); Design.md, "A
planned building is laid out from relations before its rooms are designed").
Built: the solver never chooses an L stair; a pinned fixture keeps its whole
rectangle; a plan carries `site`; the tier itself, off by default
(`layout_solver_tier`, for one story or for every story), inside the job
that builds the rooms in view or ahead of any actor; every reader of a beat
and its commit read the scene through a solved plan; the commit's writes to a
planned row prepared before the lock lay only their own fields onto it; a
re-plan takes back only what a solve laid; a comparison page for the owner.
Left, each with what it needs:

- **The owner's comparison before any story.** The tier stays off until the
  owner has compared its buildings with the designer's. The lab inn's liked
  first floor stood on an L stair the fallback chose and now re-solves with
  U stairs (15 room rectangles move): keep it, or put the L back into the
  fallback -- the owner's call.
- **An L asked for by name.** The lab's answers may still name an L and get
  one; the tier never offers it to the model. Whether an answer may ask for
  an L at all is the owner's, and either answer is a solver change: a round
  of its own under the one-change-a-round rule.
- **An incremental mode.** A building is laid out whole, and only while every
  room of it is a stub nobody has described: one described room keeps the
  whole building out. Needs the solver to hold standing rooms fixed and lay
  out the rest around them.
- **A stated proportion refuses the building.** A plan that states a long
  room -- twelve paces by three -- is refused, because the solver aims each
  room at its floor area and near square. Needs the solver to take a stated
  proportion as a constraint: a solver change, for its own round.
- **One building to a plan, so one to a street.** A building is laid out on a
  plan of its own (`layout:<entrance room>`), only while none of its stubs
  stands on a plan and no other room stands on that one. The engine's
  derivation (`site_plan.derive_site_plans`) places what it can beside a
  laid-out building on its plan -- the street it opens onto, a planned yard
  behind it, the ground floor of the next planned building along the street
  -- so that next building is left to the designer (tried: two planned
  buildings on one street, the second refused, "stands on a plan already",
  the commit after the first one's upper storey was minted). Since
  2026-10-09 a derived site keeps a building out only where it lies in
  another building's solve: a building whose own solve a re-plan took back
  is laid out again, its ground re-derived from the rooms -- and one the
  answers cannot solve (a stated proportion, above) costs the tier's two
  calls each time its wait runs out (2 beats, then 4, 8 and every 16 while
  it keeps failing on the same plan), where the stale ground refused it
  before any call. Where two are laid out before the engine places their
  ground, the group is laid on the plan holding more of their rooms, and
  the other building stands on its own plan, apart from the street it
  opens onto.
  Needs a solve laid onto the plan its ground already stands on, moved to
  where its doorway meets that ground, and then the town-fabric tier (survey
  rank 7): streets, plots and footprints on one plan.
- **Zones, stair halls, stores and grounds are not carried.** An anchor is the
  engine's only floor place, so a zone holding cushions would read to the
  designer's check as fixtures on one cell. The solver's stair hall is not a
  room of the plan, so a stair is the plan's vertical edge pinned where each
  room meets it, the hall's cells belong to no room, and an enclosed stair's
  walls and door are not kept. Needs a floor-area record the check reads as
  floor, and a ruling on whether a stairwell is a room.
- **A moved fixture goes back to the model unpinned, not as a question.** It
  is written on the wall the model named and laid along it, and the
  designer's check shows what it crowds (live: the taproom's hearth laid
  along its asked wall shares a cell with the pinned bar; the commit's
  layout lint has no row for it); nothing asks the model to choose between
  moving, shrinking and dropping it. Needs a designer step that reads the
  solve's record (`planned.layout.moved`).
- **A fixture the plan lists, given a new id, is two.** An answer that leaves
  a listed fixture out has it kept as the plan holds it, unpinned; an answer
  that gives it a new id as well leaves the plan's and the new one, because
  code cannot tell a renamed thing from a second thing without reading the
  model's words. The record lists every restored fixture
  (`planned.layout.restored`), and the sort card asks for the plan's ids.
- **The solver's stair-shape rule reads one planned room per storey as a
  tower** and turns the stair in a spiral when no answer names a shape (the
  first live run on scratch chat 165's inn; the second named it straight).
  A plan is coarser than the lab's descriptions. Needs the rule to count
  what a storey holds rather than its rooms -- a solver change, a round of
  its own -- or the relate card to ask for the shape -- a card change. The
  owner's call.
- **Nothing holds a sited room's pinned fixtures but the designer's own
  reading.** `spatial_merge` keeps a sited room's box, shape and storey, and a
  designer may still re-pin a fixture by writing its `cell`, or give a pinned
  one another wall's `dir`. Needs a rule in the room author's card or a merge
  that keeps a solved pin.
- **A room's `windows` bearings (vistas) are not carried** by planned
  geometry; its window anchors are. Needs `windows` in `GEOMETRY_FIELDS`, once
  the vista reader is checked against a solved building.
- **A re-planned building is not laid out again where its ground stands.** Its
  stubs give back what the solve laid on them -- their own record says what
  (`laid_out`) -- but the street it opened onto stands where the old solve's
  coordinates put it, so the building is left to the designer and the
  engine's derivation places its stubs beside that street. A fixture the old
  solve added that the new plan does not name stays on the stub, unpinned.
  Needs a solve laid onto a standing plan (above), and a record of what a
  solve added.
- **A design made before the solve is dropped only by the run that solves.**
  A design's fingerprint reads names, purposes and exits, never a site, so
  the run that lays a building out drops every design filed for its rooms;
  the in-beat designer never runs the tier, and a beat entering an unsolved
  building designs it as today.
- **The far layer meets a building only once an actor nears it.** Laid out in
  the rooms-in-view job, a building nobody approaches has no site, so the
  height-aware far readers (`site_plan.plan_sight`, the landscape) see it
  only then. Planting time is where to move it, if that matters more than the
  calls: a new trigger site, and two calls and a solve for every building
  planted.
- **Measured on the play database only.** Counting a pinned anchor as the
  cells of its wall it stands on left `wall_overfull` at 8 rows before and 8
  after over the play database's 139 scene rows (133 chats; 10 pinned
  anchors there); the owner's own database, where the map editor pinned
  anchors, was not measured: `room_layout_lint` over each chat's `scene`,
  with and without the change.
- **The sort card's newest clauses and the Japanese cards have not been run
  live.** The sort card names every thing for what it is, never whose, and
  asks an entry for several alike to name one of them; no model was asked
  since, so whether answers follow is unmeasured (replayed, the second live
  run's answer named its three box beds in the plural, and each bed carries
  that name). The Japanese cards pass protocol parity and have never run.
- **OR-Tools and Codex's plan lab** stay unread beyond the survey and unmerged
  (the owner's hands-off ruling); the solver stays pure Python.

## 4. Architecture gaps

<a id="unbuilt-4-7"></a>

### 4.7 Does the engine grow a material model at all?

Moved to [`DESIGN_MATERIAL_MODEL.md`](design/DESIGN_MATERIAL_MODEL.md) on
2026-08-19. Displacement with no magnitude to order it (was §4.7) and two
spellings of one region on one body (was §4.8) are one undecided question about
MATTER, not two defects; the note holds both and the argument for keeping them
together.

**Addendum 2026-08-25 — the question was asked again and answered NO
MECHANISM.** A ledger-accumulation pass over four scene ledgers reached the
substance ledger and deliberately built nothing: no expiry timer, no cap, no
displacement, no region fold. The note's standing reasons hold (the amount
vocabulary is not a magnitude; conservation already means matter on a moved
body moves with it; the fold point exists but the ruling is world law the
engine refuses to hard-code), and `AGENTS.md` forbids the universal timer
outright.

What WAS built is addressability, because the measured cause of remove-op
disuse turned out not to be prompt wording: the specialist that owns
`substance_ops` had never been shown the standing records or their
`substance_id`s, so the removal its own sheet documents could not be written
at all. Its payload now carries both of its ledgers with their ids
(`world.spatial.substance_ledger_index` / `contact_action_ledger_index`), which
is what makes the note's prompt-efficacy hypothesis testable for the first
time.

Survey 2026-08-25, for whoever reopens this: 5 of 77 stored scene blobs carry
substance records at all, holding 10, 9, 9, 9 and 3 rows — and four of the
five are branches of one story. There is no runaway. Re-measure the 38-adds /
5-removes ratio on stories played AFTER the ids started arriving before
treating a missing mechanism as the explanation.

## 5. Deferred backlog

<a id="unbuilt-5-4"></a>

### 5.4 P6 — room-boundary scene-truth

**Symptom.** A door closed at turn 31 silently reopened at 32; by 33, characters
in the adjacent room were speaking *into* the closed room and one was effectively
inside it. An information-integrity failure in an engine whose premise is the
information barrier.

**Root cause.** Not the perception *rules* — they gate same-room, closed-door and
wall correctly. It is scene *state*: door state and positions drift, so perception
is fed a wrong co-present set.

**Adjacent coverage that is not this.** Portal state is now first-class in the
scene blob, `apply_transit_dock_edges` recomputes edges from hatch/transit phase
with authored-barrier preservation, and the narrator receives `portal_states`
plus a fidelity check. That is narrator-render fidelity, not the scene-state drift
and co-present-set construction this item specifies.

**Fix.** Build the perceiver's co-present set strictly from `world.scene` room
membership plus open-door adjacency; ensure a door's closed state persists across
turns unless an action changes it; ensure a character led into a room has their
position updated. Add a hard invariant check in the commit path.

**Test.** Close a door at turn N; at N+1 assert it is still closed and that a
character in the adjacent room is not in the occupant's co-present set.

## 6. Design-note residuals

<a id="unbuilt-6-4"></a>

### 6.4 Place purpose — [`DESIGN_PLACE_PURPOSE.md`](design/DESIGN_PLACE_PURPOSE.md)

v1 is built. What was deliberately not built, each with its stated reason, is
that note's own "Not built, plainly" line plus the deferred own-memory-row
heuristic (signal 2). *(Restated here until 2026-08-19.)*

<a id="unbuilt-6-5"></a>

### 6.5 Place graph

The walkable-edge defect is §1.6; the redundancy watch is §1.12.

- **`basis: "told"` has no PLACE-GRAPH writer**, deliberately. Moved to
  [`DESIGN_PLACE_PURPOSE.md`](design/DESIGN_PLACE_PURPOSE.md) on 2026-08-19 —
  testimony can say what a place you already know is FOR; it cannot mint the
  place, and a future testimony writer needs a structured claim field, not a
  parser over prose.
- **Do not remove the three-valued frontier semantics.** `_frontier_hops` returns
  `None` (spent), `0` (live but unmeasurable), or `N`. The middle value exists for
  saves written before the graph — a walked room with no recorded exits can
  honestly be called neither spent nor near. It is not defensive padding; removing
  it would make old saves read as exhausted.
- **Live sight correctly outranks the remembered gradient.** Recorded because it
  looked like a gap and was not: `visibly_no_way_through` pre-empts the distance
  verdict via the existing `_VERDICTS` precedence, which is the right order.

<a id="unbuilt-6-10"></a>

### 6.10 Extra body parts — [`../design_notes/11-extra-body-parts.md`](../design_notes/11-extra-body-parts.md)

The card field, the `region_visibility`-gated delivery, the Director payloads
and the editor menus are built; what was deliberately not built is that note's
"Residuals" list. *(Restated here until 2026-08-19.)*

<a id="unbuilt-6-11"></a>

### 6.11 Garment displacement — [`../design_notes/17-garment-displacement.md`](../design_notes/17-garment-displacement.md)

Region-grain displacement is built; what is left open — left/right asymmetry,
transparency, and retro-repair of stale displacement prose — is that note's
"Left open" list, with each item's argument above it. *(Restated here until
2026-08-19.)*

<a id="unbuilt-6-13"></a>

### 6.13 Paradox consequences — [`DESIGN_PARADOX_CONSEQUENCES.md`](design/DESIGN_PARADOX_CONSEQUENCES.md)

All three decisions in that note are built; its three deliberately-open edges (a
warden outliving the wound it guards, cross-frame scenes, a toll with no restore
path) live in the note's §5, not here. None is urgent for the reason the note
records: no live story has ever opened a paradox. *(Restated here until
2026-08-19.)*

<a id="unbuilt-6-14"></a>

### 6.14 Close-contact causality — [`CLOSE_CONTACT_SCENARIO_AUDIT_2026-08-23.md`](experiments/CLOSE_CONTACT_SCENARIO_AUDIT_2026-08-23.md)

Alpha 9.8.1 landed the phase/dependency floor, typed communicative acts, typed
referents, contact actions and substance conservation this audit asked for.
Three residuals survive it, all genre-neutral and all stated in the audit's
own words:

- **A typed observation/result ledger.** A test whose finding gates a later
  action still has no record with an id, observer, subject, method, bounded
  finding, time and provenance for a conditional phase to reference. Branch
  truth is therefore read out of prose, which is the audit's weakest measured
  judgment (the surgical arm can still proceed after a finding falsifies an
  explicit "only if"). The same ledger serves a surgeon checking numbness, a
  mechanic testing pressure, a dancer checking balance, a hacker validating
  access, and a fighter checking whether a grip took.
- **Deterministic contact-bound pose invalidation is only partial.**
  Support/pin/grapple facts are dropped when their contact ends; a stale
  *detail* fragment (`underhook`) can still survive one evidence beat while a
  replacement (`overhook`) is established, so contact refinement remains less
  exact than the prose that produced it.
- **Durable procedure results and device state.** A splint, dressing,
  anesthetic, finding or aftercare plan is still reduced to a generic
  condition or to prose, so a material procedure leaves no typed thing a
  later beat can check.

Also open from the same run: direct-object and instrument pronouns
(`kisses her`, `takes Alice's hand with her left hand`) are solved by the
compatibility anaphora repair rather than by typed referents, which exist but
are not yet emitted on every action surface.

<a id="unbuilt-1-166"></a>

### 1.166 `state_diff.time.mode` has two readers and no writer

**Found:** 2026-09-20, moving the beat's span from the spatial hand to the
prose author's rows.

`time` left the spatial specialist's grant because a hand is handed
`_specialist_span_slice` -- the rows selected for it, never the beat -- so the
sum its chunk asked for ("the time is the sum of its parts") was over terms it
could not see. The beat's span is now `world.mechanics.beat_time_from_spans`
over each ledger row's own `seconds`, which is arithmetic and needs no model.

`mode` is not arithmetic. It says whether the beat is a SPAN TO SUMMARISE or a
SCENE TO PLAY, and two readers want it: `agents/narration.py` passes it to the
narrator as `beat_time.mode` (D9, review 2026-09-07 -- four consecutive beats
of one bare corridor were written at full scene length because the page had no
idea how long the beat it was writing covered), and
`world.charter_runtime.CHARTER_BUDGET_SECONDS` keys the off-screen wall-clock
budget on it (`beat` 10.0s, `time_skip` 60.0s).

It has never had a writer on the causal contract: measured across 3,000 stored
`director_resolve` variants, 0 carry a `time` block written by a current hand
at all, so both readers have been reading an absent field for as long as the
fan-out has existed. Nothing REGRESSED here -- the engine now supplies the
duration those readers wanted beside it, which is strictly more than they had.

**Not closed, because the obvious closure is a threshold nobody chose.** The
engine could call a beat a skip past some number of seconds, and that number
would be a cutoff invented to satisfy a field rather than a fact anyone
measured. The author knows the answer -- it wrote the prose and cut the spans
-- so the repair is one more thing asked of the row, not a rule in code. That
is an owner's call on the author's contract, and the sheet is under a stated
size bound (`tests/test_causal_director.py`), so it is an argument to have and
not a line to slip in.

Until then: the narrator receives `duration_seconds` without `mode`, and a
genuine time skip is budgeted as a beat (10.0s) rather than as a skip (60.0s)
-- which is what happens today, so the effect is a bound that has never been
lifted rather than one that was lowered.
