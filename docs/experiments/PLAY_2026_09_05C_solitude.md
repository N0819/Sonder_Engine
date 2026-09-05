# Play, 2026-09-05 (campaign 3): "The Salt Terraces" — one woman, no cast

Status: EVIDENCE. Twenty player turns plus an opening, Gemini 3.8 flash on
provider 3 for every role, on an export-built scratch database
(`export_bench.py prepare --chats 115`), worktree at `cf923464`. Stress axis:
**no other people at all.** No registered cast, no charter, no background
presence — strip out dialogue, reaction and relationship and what is left is
the engine's model of a WORLD, and its model of the one mind standing in it.

**Authored by hand: a persona sheet and a scenario in prose. Nothing else.**
Under the owner's correction of 2026-09-05 ("I think asking them to build
rooms is a flawed test design — we should have the engine build the rooms"),
no room, extent, shape, exposure, anchor, light source or sound source was
authored. `director_establish` built the road and the first terrace from the
scenario prose; the Writers' Room built everything below and above it at my
invitation, in four sessions; the Director minted the rest at the frontier as
I walked. The only hand-writing is four World Browser calls at turn 8, which
a host would actually have made and which are marked as interventions.

**Provider interruptions.** Between 12:45 and 13:10 the shared OpenRouter
account was exhausted and returned HTTP 402. It cost the tail of turn 9, the
narrator of turn 10, most of turn 11 and three Writers' Room attempts; all
were retried and completed. Harness noise, not filed as findings — except
PS16, which is about what the engine DID when a call failed. Turn 11's
timings are not comparable and are excluded from the averages. **The registry
was checked after every retry: no duplicate room, no stub minted twice, no
frontier expanded twice** (`room_registry` holds seven rows and every
`steps`/`variants` row is single-active; `perception_outcome` on turn 11 has
three variants, one active, which is the reroll behaviour and not a duplicate
world).

Cast: none. Persona: Mireille Adjani, 53, surveyor for the Reclamation
Office, sent alone to Ourmel — a salt town on the dry bed of Lake Sarrat,
abandoned in living memory — to write whether anything there is worth taking
back. `character_card_warnings`: empty.

## The turn table

| # | what she did | what the world did | findings |
|---|---|---|---|
| 0 | (opening) | Establish builds the haul road and a terrace below it, with steps down | PS1, PS7, PS15, PS18 |
| 1 | Writes the hour; tests the top step | Step holds; "someone's upper shaft against your right hand" | PS1, PS2 |
| 2 | Counts herself down the steps to the terrace | Arrives; her lamp, canteen and rule stay on the road | PS3 |
| 3 | Crosses to the cistern arch; shakes the lamp for oil | Arch leads nowhere; lamp is two rooms away and slosh is narrated | PS4, PS7 |
| 4 | Two hours pacing the middle tier | Room's planned tier materialises 24×16; view still says "dim" | PS10, PS17 |
| 5 | Into the vault; lights the lamp | Lamp teleports in; echo claim unadjudicated; "keeps its silence" | PS4, PS13 |
| 6 | Reads the vault wall for drawdown banding | **"No banding answers from the masonry."** | (works) |
| 7 | Down the revetment stair | The Room's wedged sluice gate and dropped tools are there | (works) |
| 8 | Reads the wedges; picks up the mallet | Mallet minted as a real entity; anchor desc still lists it | PS20 |
| — | *host: World Browser — kit moved, size word fixed, lamp out, cell pinned* | all four writes land and survive | — |
| 9 | Runs down the last flight, hands full, untested treads | Nothing. No dice, no contest, no scratch | PS12 |
| 10 | Works to midday; reaches for the canteen | Canteen is a room behind her; the narrator hands it to her | PS12 |
| 11 | Sets everything down and listens for a count of sixty | Provider outage: prose says she set it down, view says she holds it | PS16 |
| — | *Room: the town shelf, the stripped hall, the corbel* | published, and never seen again | PS5 |
| 12 | Climbs to "the shelf above, where the houses were" | Director mints a **second** shelf; the Room's is invisible | PS5 |
| 13 | Into the big roofless building | Director mints a **second** common hall | PS5, PS6 |
| 14 | Hunts the walls for the roof-frame's iron | **"No iron answers."** — in the wrong hall | PS5 |
| 15 | An afternoon writing; a memory; a decision | Four sentences about the temperature of a wall | PS14, PS15 |
| 16 | Down at dusk, thumb against a kerb for scale | Weather drifts to drizzle on a dry lake bed, silently | PS11 |
| 17 | Sits out the dark; lights the lamp | Night lands; narrator writes the drizzle this beat cancelled | PS10, PS11 |
| 18 | Back into the vault by lamplight alone | Light field correct; "the vault swallowed the sound without an echo" | PS13 |
| 19 | Writes and reads out the verdict | Graphite ridges on the back of the leaf | PS14, PS20 |
| 20 | Leaves the mallet; walks out under the stars | Four rooms in 240 seconds | (works) |

---

# Pass 1 — the critic

## What it got right that a cheaper system could not

The world was *built*, not described, and the difference is legible. From
eleven words of scenario prose the establish gave me a haul road topping out
on a bluff, a flight of salt-crusted stone steps going *down* — a vertical
edge, unprompted — a terrace of evaporation pans with a wound-shut sluice and
an arch into a cistern vault. It named none of that in my prose. By turn
eighteen Ourmel had ten rooms on five levels with the drops in the right
places, and I could draw it.

And the light does turn. This is the thing I most expected to fail and it did
not. She walked in at 06:10 and the composed view said "The light is dim." At
08:30 it said lit. At noon, lit. By 17:00 she was writing in yellow light and
by 23:00 every open room in the town computed `dark` and her lamp was the
only thing in the world — "The light from brass hand lamp falls on The
massive limestone revetment wall ... and thins to half-light at The low
cut-limestone arch". The engine tracked one anchor hour through five explicit
time skips and never lost it. In a story whose only antagonist is the
afternoon, that carried the whole thing.

The best single moment in twenty beats was earned by the machine and not by
me. I asked the Writers' Room to replace a cliché — it had put a punched lead
tally plate at the revetment stair, the ruin handing her its own explanatory
note — and it came back with a balk-oak sluice gate wedged mid-stroke on two
split-ash wedges, adze shavings sealed under a rind of halite, and an
iron-hooped mallet set down bare on a stair tread rather than packed in a
tool roll. Three beats later I walked her down that stair and **it was
there**, in the room the Room had named, phrased as the Room had phrased it,
and the Director minted the mallet as a real object when she picked it up.
She read it out loud: *"Nobody sets a mallet down on a stair at the end of a
season. You set it down like that when you are coming back to it after your
dinner."* That is co-authorship working, and no cheaper system does it.

The refusals were good too, twice. She scraped the cistern wall looking for
seasonal banding and got **"No banding answers from the masonry."** She went
along the hall wall looking for the iron the roof-frame must have been tied
to and got **"No iron answers. ... no sheared pintles, no leaded sockets, no
gouged pockets where an iron dog was driven home and levered out."** A world
that tells a specialist "not here" in her own vocabulary is a world with a
spine.

## Where it stopped being immersive, and on which sentence

**Turn 1, sentence six: "You feel someone's upper shaft against your right
hand: steady pressure, weight and shared warmth, continuous while the contact
holds."**

That is the survey staff. In the story where nobody is alive, the engine told
her twice on the first beat that she was in continuous warm contact with an
unidentified person, and it went on doing it for nineteen beats — her
notebook ("someone's cover"), her canteen ("someone's webbing strap"), her
lamp ("someone's wire bale"), and on turn 12 three of them in a row before
the room was even named:

> You feel someone against your arm ... You feel someone against your hand
> ... You feel someone's webbing strap against your fingers ... You are in
> Upper Terrace Settlement Shelf.

The premise of this story is that she is alone. The composed view broke it on
beat one and never stopped. It also leaked into the narrator, which wrote
"its shaft bearing into her palm with steady weight and familiar warmth" of a
stick — *shared warmth* is a phrase about two bodies, and a brass lamp does
not have any. (Root cause proved in Pass 3, PS1: it is not the model. Any
object the Director gives a POSTURE becomes a person to the identity floor,
and the establish gave her kit postures — `slung`, `hooked`, `pocketed`.)

Second break, turn 1: **"poised at the brow with one foot on the top step
down toward upper_terrace_rim"** — an engine room id, verbatim, on the page.

Third, and the one that cost the story its ending: **the Writers' Room and the
Director built two different towns and neither knew.** At turn 11 the Room
published a shelf of workers' dwellings above the middle tier and a stripped
common hall off it, with an eight-hundred-pound corbel hanging on petrified
hemp in the middle of the hall floor — the thing waiting to be found on the
beat I chose. On turn 12 I walked her up to "the shelf above where the houses
were" and the Director, which was not shown the plan, **minted a second
shelf**. On turn 13 she went into the big building and it **minted a second
hall**. She spent turns 13 and 14 in a roofless common hall that was not the
roofless common hall, looking for an iron ring that exists in the other one.
`inspect_contradictions` reported nothing about it. Ourmel now carries
`upper_terrace_settlement` and `town_shelf_lane` as two doors off the same
terrace to the same bench of houses, and `settlement_common_hall` and
`unroofed_common_hall` as two of the same building.

## Repetition: one paragraph, twenty-one times

Here is the opening clause of every narrator paragraph in the run:

| turn | ¶1 opens | ¶2 opens |
|---|---|---|
| 1 | The cut step takes her tread | **Nothing replies from the basin** |
| 2 | **The basin gives back no answer** | Her right hand holds the survey staff |
| 4 | The canvas coat pulls taut across her ribs | Against her left fingers, the stiff cover |
| 5 | **No answer comes back from the stone** | The brass hand lamp bears against her right hand |
| 6 | The damp skin drags rough over the cut face | **No banding answers from the masonry** |
| 8 | The ash handle carries the hard, oiled polish | Beside her hobnails, the chisel lies |
| 10 | The canvas strap yields beneath her fingers | A pace beyond her hobnails |
| 11 | The canteen's cap grates home | **No answer comes from the works** |
| 14 | **No iron answers** | Mireille stands upright against the wall |
| 15 | The broad cap of the wall yields up the day's stored heat | — |
| 17 | The wick takes the flame | The squared lip of the kerb bites hard |
| 18 | **No answer came from the masonry** | The wire bale bit hard into her fingers |
| 19 | The released wire bale settles | On her knee, the double rule scores deep |

Seven paragraphs open by telling me nothing answered. Fourteen open with a
surface pressing on her body: *yields* three times, *bites/bit* four times,
and the construction "X + verb + against her Y" in every single beat. There
is one sentence in this story and it is *a hard thing touches a woman*.

This is not a taste failure, it is a payload failure, and Pass 2 shows it
exactly: the narrator's `sensory_channels` carries `hearing: {"status":
"live"}` **with no content on any beat of the run**, sight as a re-quoted
composed view, `interoception` as her pose — and three or four touch percepts
a beat. Touch is the only channel with anything in it, so touch is what gets
written. The engine's own repetition guard (`overused_phrases`) was
meanwhile forbidding her *"of the notebook"*, *"to the south"*, *"as she
works"* and *"in the grit"* — function-word trigrams — while seven identical
rhetorical moves went straight through, because they share no surface string.

Voice: there are no two characters to sound alike, so the question becomes
whether the narrator sounds like *her*, and it does not. It is a very good
materials writer and she is a woman with an argument. On turn 15 she said, to
her notebook, in the dark of a decision she had paid for once already:

> "Vaux-sur-Sel. Nineteen houses and one dog, and they still made me sign it
> 'no viable reclamation'. I signed it. I was right, and they never sent me
> anywhere warm again." ... "This one is not that. This one they left
> standing."

The narrator's whole answer was the temperature of a wall through her
trousers, straw in her lap, and paper against her thumb. On turn 19 she wrote
and read aloud the verdict the entire story exists to produce — *"The works
can be reclaimed the day the lake comes back and not one day before, and the
lake is not coming back. Recommend against. Signed, M. Adjani"* — and got
back the graphite ridges on the reverse of the leaf. Beautiful, and beside
the point. **After twenty-one turns the database holds zero memories for
her.** There is no character step for a player, no thought channel in any
payload, and no consolidation. A solo protagonist has, in this engine, no
interior at all: she is a very well-instrumented hand.

## Agency, and whether the world ever refused me

It refused me well twice (the banding, the iron) and mechanically the rest of
the time. What it never did was *cost* me anything. On turn 9 I ran her down
a twenty-pace revetment stair, at fifty-three, at speed, hands full of mallet
and lamp, explicitly not testing a tread — `dice: []`, `contested: false`, no
condition, no vitals, no bruise. At midday her canteen was two rooms and a
stair behind her and the narrator handed it to her anyway ("The canvas strap
yields beneath her fingers, the flask knocking against her hip bone"). She
sat out a night on a salt pan at `temperature: cold` and nothing marked her.
In twenty beats alone, nothing in this engine can hurt, tire, thirst, chill
or hinder a body. The only jeopardy available is the one I write, and if I
write it the engine narrates it and does not encode it.

## Surprise: one, and it was a bug

Across twenty beats exactly one thing happened I did not cause: on turn 16
the weather drifted to `precipitation: drizzle` on a dry lake bed at the end
of the dry season. No stage mentioned it. On turn 17 the Director cleared it
back to `clear/none` in the same beat that the narrator — composed before the
commit — wrote "a sparse drizzle drifts down through the stillness to speckle
the broad brim of her hat". Rain arrived invisibly, was narrated once, after
it had been cancelled. `background_react` fired 0 times in 21 turns, which is
correct with nobody there, and means there is no other source of event in an
empty world at all.

## Pacing

The median beat cost 61 s and returned two paragraphs. Turn 13 cost 113 s, of
which `director_contact` alone was 89 s, to record that a woman's hobnails
were on a floor. Turn 19 cost 114 s, 79 s of it contact, to record that she
sat down against a wall and wrote. The most expensive role in a story with
one person and nothing to touch but her own tools was the contact hand: **536
seconds of the run's ~1850 s of model time.**

## The Room's own verdict, which is the best criticism in this document

I asked it what was weakest about Ourmel and told it to be unkind:

> Ourmel does not feel like a ruined settlement; it feels like an outdoor
> architectural museum that closed for lunch twenty minutes ago. ... There is
> no domestic squalor, no broken pottery, no blowing chaff, no scrap metal
> torn loose by scavengers, no animal droppings, and no sign of what three
> hundred desperate people actually did when their drinking water went bad
> and their pay stopped.

It is right, and it is right about its own work. The engine and the Room both
default to the tidy, the dressed, the legible: cut stone, level courses, an
intact lintel. Nothing in twenty beats was *broken* in a way nobody intended.

---

# Pass 2 — the technical deep dive

193 `llm_capture` rows, 21 turns, one `trace_<turn>.json` per beat.

## Seconds and bytes per role per beat

`payload` below is `system + payload` characters as captured; seconds are
wall clock. Turn 11 is excluded (three specialists lost to HTTP 402).

| turn | beat s | calls | director | d_contact | d_spatial | d_objects | d_body | narrator |
|---|---|---|---|---|---|---|---|---|
| 0 | 15.0 | 2 | 9s/23kB | — | — | — | — | 5s/38kB |
| 1 | 96.2 | 11 | 11s/80kB | 55s/74kB | 15s/74kB | 39s/89kB | 22s/33kB | 9s/44kB |
| 2 | 98.0 | 9 | 13s/84kB | 20s/74kB | **73s/76kB** | 12s/57kB | — | 10s/44kB |
| 3 | 60.4 | 9 | 27s/88kB | 23s/75kB | 12s/78kB | 8s/58kB | — | 9s/46kB |
| 4 | 54.0 | 9 | 14s/88kB | 3s/36kB | 32s/79kB | 10s/58kB | 2s/34kB | 7s/47kB |
| 5 | 87.7 | 11 | 46s/150kB | 9s/73kB | 28s/81kB | 11s/58kB | — | 12s/48kB |
| 6 | 62.0 | 9 | 17s/94kB | 36s/74kB | 9s/82kB | — | 6s/33kB | 8s/50kB |
| 7 | 50.0 | 8 | 14s/91kB | 17s/76kB | 27s/84kB | — | 2s/35kB | 7s/50kB |
| 8 | 71.6 | 11 | 14s/91kB | 33s/74kB | 40s/86kB | 13s/62kB | 6s/67kB | 9s/52kB |
| 9 | (resumed) | 9 | 15s/93kB | 21s/75kB | 31s/86kB | 15s/62kB | — | 8s/54kB |
| 10 | (resumed) | 9 | 24s/101kB | 15s/76kB | 27s/87kB | — | 3s/34kB | 10s/54kB |
| 12 | 46.9 | 9 | 12s/66kB | 11s/37kB | 18s/91kB | 15s/64kB | 3s/34kB | 7s/58kB |
| 13 | 113.2 | 8 | 12s/93kB | **89s/78kB** | 16s/91kB | 2s/30kB | — | 7s/57kB |
| 14 | 57.6 | 10 | 20s/144kB | 26s/77kB | 11s/90kB | 15s/60kB | — | 10s/58kB |
| 15 | 82.2 | 12 | 40s/97kB | 33s/77kB | 20s/90kB | 11s/60kB | 14s/68kB | 6s/57kB |
| 16 | 65.1 | 12 | 24s/124kB | 26s/76kB | 15s/92kB | 10s/32kB | 16s/68kB | 10s/57kB |
| 17 | 42.6 | 10 | 19s/106kB | 13s/75kB | 7s/46kB | 9s/63kB | 2s/34kB | 9s/57kB |
| 18 | 40.6 | 9 | 14s/108kB | 11s/76kB | 18s/96kB | 3s/32kB | — | 7s/57kB |
| 19 | 113.7 | 11 | 14s/93kB | **79s/78kB** | 26s/143kB | 16s/63kB | 3s/36kB | 10s/60kB |
| 20 | 53.0 | 10 | 22s/106kB | 15s/78kB | 21s/96kB | 8s/32kB | 3s/36kB | 9s/58kB |

**Whole-run role totals (seconds of model time):** `director_contact` 536,
`director_spatial` 446, `director` (prose author, both stages) 408,
`director_objects` 197, `narrator` 178, `director_body` 85.

## `director` (the prose author) — 25 calls, 290 kB of payload

Sent: `scene` (5.7 kB mean, 120 kB total — the single largest key in the
run), `player_declaration` (4.9 kB), `director_recent_messages` (2.7 kB),
`player`, `author_notes`, `planned_rooms`, `sightlines`, `fiction_model`,
`simulation_clock`, `engine_notices` — and **thirty-one keys that were empty
on every call of the run**: `paradox`, `dialogue_mode`,
`standing_intentions`, `due_authored_events`, `present_characters`,
`active_awareness`, `active_restraints`, `active_conditions`,
`travel_in_flight`, `other_players_declarations`, `character_declarations`,
`character_contact_endings`, `character_material_effects`,
`character_abilities`, `dice_results_final`, `pending_obligations`,
`world_pressure`, `crowds`, `couriers`, `notices`, `carried_reports`,
`unratified_claims`, `background_presence_knowledge`, `interaction_rounds`,
`reaction_rounds`, `addressable_presences`, `world_books`, `pending`,
`other_players`, `variant_seed`, `player_seed`.

Bytes-wise that is 2 characters each and nothing. As *reading* it is a wall:
in a story with one body, every one of those thirty-one is structurally
impossible to fill, and the model is asked to consider each on every beat.
**Proposal:** omit a key that is empty AND whose emptiness is a property of
the scene rather than of the beat (no cast → no `character_*`, no
`interaction_rounds`, no `crowds`, no `couriers`, no `other_players`). Saving
is not bytes, it is the model's attention; the measured symptom is the
prose author repeatedly reaching into the touch channel because it is the
only populated one.

Where it misread: on turn 12 it was sent `existing_rooms` (the seven live
rooms) and **no `planned_rooms` at all**, and answered
`"Player movement targets new room 'upper_terrace_settlement' not in scene —
generate room description"`. The Room's `town_shelf_lane` had been published
twenty minutes earlier. `planned_rooms` is scoped to the planned neighbours
of the room the body currently stands in — turn 7 was sent
`["middle_terrace_pans"]` while four other rooms were published; turn 10 was
sent `["revetment_stair_chute"]`. **This one scope decision is the origin of
the run's worst story failure (PS5).**

## `director_contact` — 19 calls, 536 s, 647 kB of system prompt

Sent every call, regardless: `contacts`, `anchors`, `worn_garments` (349 B
mean, for a woman who changed clothes zero times), `entity_names`,
`substances`, `rooms`, `contained`, `declared_actions`, and — on 9 of 19 —
`player_declaration` at 2.1 kB. Empty on every call: `cast`,
`dice_results_final`, `scales`, `contact_actions`,
`character_contact_endings`, `character_material_effects`.

Its answers were mostly right and enormously expensive: turn 1, 42.3 s and
15,925 response tokens to record that a woman is holding a stick and a
notebook; turn 13, 89 s; turn 19, 79 s. **This is the biggest single waste in
the run.** In a scene whose bodies number one, every contact it can write is
self-to-object or self-to-fixture, and those are the two cases the spatial
and objects hands already know about. **Proposal:** gate the contact hand on
the beat's own shape — a beat with one body present and no `contact_ops` in
the interpret's own diff does not need a 34 kB system prompt and a 30-second
call. Estimated saving on this run: ~400 s of 1850 s, ~25 % of wall clock.

## `director_spatial` — 20 calls, 446 s, 177 kB of payload

`rooms` is 3.8 kB mean and 76 kB total: the whole live room map, every call,
at interpret AND at resolve. `poses` 875 B. `movers` and `movement` empty on
10 of 20. It also re-echoed rooms it had no business restating —
`upper_terrace_rim` came back on turn 2 as `{"name": "", "desc": "",
"adjacent": [], "anchors": {...}}`; the merge protected the room, correctly,
but the hand is spending output on a whole-record re-emission when it wanted
to add one anchor. Its `size`/`extent` disagreement fired the layout lint
twice.

**Proposal:** send the spatial hand the room the body is in, its neighbours
and the destination — not the map. The map is what `compile_world_context`
is for, and the hand's own output shows it does not read past the current
room.

## `director_objects` — 15 calls, 197 s

`entities` at 2.3 kB mean is the whole entity ledger. Its clearest misread:
turn 1, she took her notebook out of her own coat, and it wrote
`{"op": "transfer", "object_id": "field_notebook", "from_id": "Mireille
Adjani", "to_id": "Mireille Adjani", "relation": "held"}` — a transfer from a
body to itself. There is no vocabulary for *pocket → hand*, so it used the
channel it had. On turn 5 it re-emitted `brass_hand_lamp` with `kind`
flipped item→object, `portable` true→false, the aliases and scent dropped —
the merge yielded and warned, which is the system working, but the hand is
being invited to restate a whole record in order to change one flag.

## `director_body` — 7 calls, 85 s, 5 of them returning an empty diff

Sent `worn_garments` and `attire` on every call in a story with one costume
change (a hat off and on). Returned 119 bytes — the empty answer — on five of
seven. **Proposal:** the body hand has nothing to do on a beat with no
attire, pose-detail or pain change; the 22.5 s it cost on turn 1 bought
nothing.

## `narrator` — 11 calls, 178 s, 122 kB payload

`past_narration` is 5.0 kB mean and rising (55 kB across the run) — the
largest narrator key by a factor of three. `sensory_channels` (1.5 kB)
carried `hearing: {"status": "live"}` **with no `this_beat` content on any
beat of the run**, sight as a verbatim re-quote of the composed view, and
interoception as the pose sentence. `overused_phrases` (129 B) is a list of
function-word n-grams: `["of the notebook", "the stiff cover", "stiff cover
of", "cover of the"]`, `["south west the", "the south west", "as she works",
"to the south", "basin to the"]`. It forbids the narrator ordinary
prepositional strings and cannot see that seven paragraphs opened by saying
nothing answered.

**Proposals, in order of value:** (1) `overused_phrases` should carry the
opening MOVE of recent paragraphs, not their trigrams — the observable class
is a rhetorical repeat, and the current list actively degrades the prose by
banning connectives. (2) A `hearing` channel that is `live` and always empty
should either carry the world's own ambient sound (wind over the pans, her
own footfall, the acoustics of an enclosed stone room) or say `silent`, so
the narrator is not told a channel is open and handed nothing through it.
(3) `past_narration` at 5 kB and growing is where the beat's cost goes as the
story lengthens; it wants a budget.

## Payload shapes that are wrong in kind

* **A planned THING is delivered to the Director under `present_figures`** —
  the key named for people. On turn 8 the payload's `present_figures` was the
  Room's wedged sluice gate and dropped mallet.
* **Inside it, `truths` is a Python repr of a list inside a JSON string**:
  `"truths": "['The heavy oak shutter is wedged ...', \"Pale, curled adze
  shavings ...\"]"`. The model receives Python quoting as content. That is a
  `str()` where a JSON array was meant.

---

# Pass 3 — the bugs

Severity: firewall / story-breaking / wrong-but-recoverable / cosmetic.

### PS1. An object the Director gave a POSTURE is a person to the identity floor, so the composed view manufactures people in an empty world
* **Stage of origin:** `agents/perception.py` `_sensation_label` →
  `agents/composer.py::_names_a_body`; the input is `director_establish`'s
  `state_diff.poses`.
* **Live case:** turn 1, `perception_outcome` for the player: *"You feel
  someone's cover against your left hand: steady pressure, weight and shared
  warmth"* (the field notebook) and *"You feel someone's upper shaft against
  your right hand"* (the survey staff). Recurred on 14 of 20 beats; turn 12
  opened with three consecutive "You feel someone..." lines.
* **Root cause, proved on the committed scene:**
  `composer._names_a_body(scene, "survey_staff", [])` → `True`;
  `_pose_referent(...)` → `"someone"`. `_names_a_body` treats any subject
  with an entry in `scene.poses` as a body. The establish wrote
  `poses: {survey_staff: {posture: "upright"}, canteen: {posture: "slung"},
  brass_hand_lamp: {posture: "hooked"}, folding_rule: {posture: "pocketed"},
  field_notebook: {posture: "pocketed"}}`. The `mallet`, which never received
  a pose, renders correctly as *"the iron-hooped mallet's polished handle"* —
  the control case is inside the same view.
* **Severity:** story-breaking (and firewall-adjacent: it mints an
  unidentified PERSON into the player's view where the scene holds none).
* **Recurs:** the class of F43 / chat 84 / chat 98 t22 — `_pose_referent` was
  built to fix exactly this and the fix does not reach here, because the test
  it applies (`_names_a_body`) reads a ledger that objects are legitimately
  in.
* **Fix:** ask `spatial_contacts.contact_thing_label` FIRST at
  `_pose_referent` step 3, exactly as `contact_sensation`'s own docstring
  says a caller holding an identity floor must — verified live, it returns
  `"brass hand lamp"`, `"survey staff"`, `"field notebook"` for all three.
  Where it answers, the answer is affirmative evidence of a thing and
  outranks the person-shaped default. State the rule as: *a pose is not
  evidence of a body; a body is what the scene's own entity ledger declines
  to call a thing.* **Test:** a scene with one body and a positioned entity
  carrying a `poses` entry; assert the contact percept names the entity and
  never "someone".
* Second half, same finding: the sensation template says **"shared warmth"**
  of a stick, a wall and a mallet. Warmth is shared between two bodies; a
  thing has temperature. The clause wants a thing-form.

### PS2. An engine room id reaches the player's page inside a pose detail
* **Origin:** `director_resolve.state_diff.poses` (body specialist) free text;
  `agents/composer.py` prints `detail` verbatim.
* **Live case:** turn 1, composed view: *"poised at the brow with one foot on
  the top step down toward upper_terrace_rim, survey staff planted in a
  rut."*
* **Severity:** wrong-but-recoverable (cosmetic in effect, but it shows the
  reader engine plumbing — the thing `_pose_referent` step 5 already refuses
  for referents).
* **Fix:** the same id-shaped-token refusal `_pose_referent` applies to
  referents should run over pose `detail` before it is composed: a token that
  matches a room uid or an entity id and is not a name is replaced by the
  record's display name or dropped. **Test:** a pose detail naming a room uid
  composes with the room's name or without the clause.

### PS3. A posture word that MEANS carried is not a carriage record, so a body walks away from its own kit — and the prose keeps using it
* **Origin:** `director_establish.state_diff.poses` writes `slung`, `hooked`,
  `pocketed` for her equipment; nothing derives containment from them, and
  `director_resolve.state_diff.positions` moves only the objects a hand
  happened to think about.
* **Live case:** turn 2, she walks down five steps carrying everything; the
  committed positions are `{Mireille: upper_terrace_rim, field_notebook:
  upper_terrace_rim, survey_staff: upper_terrace_rim, brass_hand_lamp:
  haul_road_head, canteen: haul_road_head, folding_rule: haul_road_head}`.
  By turn 10 her possessions were spread over three rooms while the narrator
  used all of them. Converged only at turn 12, when the objects hand finally
  wrote `transfer ... relation: carried` for three of them; the folding rule
  is still on the revetment stair at the end of the story.
* **Severity:** story-breaking.
* **Recurs:** F46 (a carried light recorded by position), widened from lights
  to every possession.
* **Fix:** `persist/commit_scene_state` (or the merge) should derive
  containment from an establish-time posture that states carriage, the way
  `derive_worn_containment` derives it from the wardrobe ledger — the rule in
  engine vocabulary: *a thing whose posture says a body is bearing it is
  contained by that body, and a contained thing goes where its holder goes.*
  **Test:** an establish that gives a portable entity a bearing posture, then
  a move; assert the entity's position follows the body.

### PS4. The player-authority floor un-rejects an act the world had grounds to refuse, and then encodes nothing
* **Origin:** `director_resolve` claim adjudication + the asserted-effect
  floor.
* **Live case:** turn 3. She unhooks the lamp from her belt and shakes it;
  the lamp is in `haul_road_head` and she is in `upper_terrace_rim`. Warning:
  *"PLAYER AUTHORITY: asserted claim 'claim:4:effect:0' ('brass_hand_lamp
  held in hand beside ear' on None) was marked 'rejected' — asserted effects
  occur as declared and may not be rejected."* The state_diff then encodes
  nothing, and the narrator writes *"The reservoir answers with a heavy,
  thick slosh against the brass—plenty of fuel left in the belly of it."*
  On turn 5 the same lamp simply teleported two rooms and a stair into the
  cistern (`positions.brass_hand_lamp: sunken_cistern_vault`) with no leg,
  no carriage record and no warning.
* **Severity:** story-breaking. The floor is right — a player's declared act
  occurs — but "occurs" and "occurs with nothing changed in the world" are
  different, and the second is what shipped.
* **Fix:** where an asserted effect is un-rejected, the same seam that
  reports the rejection should tell the Director what the world needed in
  order for it to be true (*the lamp is not with her; if the act stands, it
  came with her*), through `ctx.tell_director` — the mechanism F40's fix
  already uses for unsourced light. **Test:** an asserted effect naming an
  object in another room produces either an encoded relocation or a
  told-to-Director notice; never silence.

### PS5. A published plan is visible to the Director only from the room it is attached to, so a player who names a planned place from anywhere else gets a duplicate — and the Room's planted event becomes unreachable
* **Origin:** the `planned_rooms` payload key's scope (`agents/director.py` /
  `agents/mapping.py`).
* **Live case:** turn 11, the Room published `town_shelf_lane` ("Town
  Habitations Shelf", extent 8×24, off `middle_terrace_pans`) and
  `unroofed_common_hall` with `plan:thing:abandoned_salvage_derrick_and_su`
  in it. Turn 12, from `shoreline_wharf_pans`, the interpret payload carried
  `existing_rooms: [...seven live rooms...]` and **no `planned_rooms` key at
  all**; the answer was *"Player movement targets new room
  'upper_terrace_settlement' not in scene — generate room description"*. Turn
  13 minted `settlement_common_hall`. Measured scope on other beats: turn 7
  (standing in `upper_terrace_rim`) was sent `planned_rooms:
  ["middle_terrace_pans"]` while four rooms were published; turn 10 was sent
  `["revetment_stair_chute"]`.
* **Severity:** story-breaking. This is the run's worst failure: the town has
  two shelves of workers' houses and two common halls, and the one thing the
  Room planted to be found — an 800-lb corbel hanging on petrified hemp — was
  never findable.
* **Recurs:** F42's family, from the other end. F42 fixed "a planned room
  that names an OCCUPIED room"; this is "a planned room the mover names from
  three rooms away."
* **Fix:** `planned_rooms` should carry every unretired planned room the
  chat holds — the registry is small (seven rows here) and the payload cost is
  591 B mean today. Failing that, the interpret's own
  `Player movement targets new room '<id>' not in scene` branch must consult
  the registry by NAME before minting: the rule in engine vocabulary is *a
  place the story has already planned is not a new place.* **Test:** publish
  a plan naming a room two hops from the body, declare a walk to it by
  description, assert no new room uid is minted.

### PS6. Two rooms that are the same place are not a contradiction, and the one overlap the lint does see is reported twice
* **Origin:** `world/spatial_lint.py` / `story.room_tools.inspect_contradictions`.
* **Live case:** with `upper_terrace_settlement` and `town_shelf_lane` both
  adjacent to `middle_terrace_pans` and both described as the bench of
  workers' dwellings above it, and `settlement_common_hall` /
  `unroofed_common_hall` both the roofless hall, `inspect_contradictions`
  returned `{"registry": [], "structure": [], "dangling": [], "layout": []}`
  on turns 11–16. At turn 18 it reported one row and reported it twice:
  `rooms_overlap_when_placed [upper_terrace_settlement, upper_terrace_rim]
  via middle_terrace_pans` and the same pair reversed.
* **Severity:** wrong-but-recoverable (it is the tool a co-author would use
  to catch PS5, and it does not).
* **Fix:** two: (a) dedupe `rooms_overlap_when_placed` on the unordered pair;
  (b) a new lint kind — a live room and a planned room reachable from the
  same room whose names or purposes describe one place. **Test:** publish a
  plan, mint a duplicate live room off the same neighbour, assert
  `inspect_contradictions` names both.

### PS7. An anchor whose description names a passage is not a passage
* **Origin:** `director_establish.state_diff.rooms.<id>.anchors`.
* **Live case:** turn 0, `upper_terrace_rim.anchors.cistern_arch = {"desc":
  "The deep, unglazed archway leading into the lower cistern vaults.", "dir":
  "ne"}` — and the room has no edge to any cistern. Turn 3 she walked to it,
  stood in it, and there was nothing through it; the vault she eventually
  entered hangs off the terrace BELOW. The interpret raised
  `needs_mapping: true, mapping_request: "Map the interior of the cistern
  vault accessible through upper_terrace_rim's cistern_arch"` and nothing
  answered it.
* **Severity:** story-breaking (the world offers a door that is not a door,
  and the request to make it one is dropped).
* **Recurs:** F58's class from the other side (a hand-written anchor whose
  desc names an exit).
* **Fix:** owner decision, stated as a class — either the establish's anchor
  prompt says *an anchor is a place in this room, never a way out of it; a
  way out is an `adjacent` entry*, or the merge folds an anchor whose desc
  names a passage onto the exit it names, as F58 proposed. **Test:** an
  establish writing an anchor described as leading somewhere either produces
  an edge or a warning.

### PS8. A frontier label becomes a planned room whose whole description is the label, behind a door onto open ground
* **Origin:** the frontier mint (`world/structure.py`) + the spatial hand.
* **Live case:** the Room's `shoreline_wharf_pans` carried `frontier: ["Lake
  Sarrat Dry Bed"]` (4 words, inside `FRONTIER_NAME_WORDS`). It minted
  `lake_sarrat_dry_bed` with `{"planned": true, "purpose": "Lake Sarrat Dry
  Bed", "adjacent": [{"to": "shoreline_wharf_pans", "barrier": "open_door"}]}`
  — a place whose entire description is its own name. When the Director later
  described it properly it also kept `barrier: "open_door"`: **a door between
  a wharf terrace and an open dry lake bed**, and `size: "vast"` with no
  extent (the extent normalizer caps at 24 paces, so a dry lake cannot be
  drawn).
* **Severity:** wrong-but-recoverable.
* **Recurs:** F63/F3's family (narrowed, not closed — the refusal is now by
  word count and a 4-word place-name still mints a labelled stub).
* **Fix:** a planned room minted from a frontier label should carry no
  `purpose` at all rather than an echo of its name (an absent purpose is
  honest; a purpose equal to the name reads as authored), and a frontier edge
  should default to the barrier of the edge it came from — `open`, not
  `open_door`, which is what a label with no barrier information means
  outdoors. **Test:** mint from a frontier; assert `purpose != name` and the
  barrier is not a door.

### PS9. The composed view splices sentence-shaped anchor descriptions into a list and drops the pack's articles
* **Origin:** `agents/composer.py` feature and light sentences; the anchor
  `desc` written by the Director is a capitalised full sentence.
* **Live case:** turn 4 — *"You can see Salt-rimed limestone kerbstones
  dividing the rectangular crystallisation pans. within arm's reach, The open
  stone lip of the middle shelf ... across the room, and The cut-limestone
  steps leading up to the upper terrace. across the room. There is cistern
  intake passage. There is revetment stair and sluice."* Turn 5 — *"The light
  from brass hand lamp and the opening thins to half-light at The low
  cut-limestone arch ... and The massive limestone revetment wall at the far
  northeast end of the dry basin.."* (two full stops). Turn 20 — *"There is
  broad salt-crusted stone steps."*
* **Severity:** cosmetic per sentence; in this story it is the whole reader
  experience, because with nobody to talk to the composed view IS the page.
* **Recurs:** F52's last line ("from hand torch" — the `light_origin` items
  are entity names without the pack's article), unfixed and now visible in
  three sentence families.
* **Fix:** two halves. (a) The passage and light sentences take the pack's
  article the way `_pose_referent` does. (b) State in the establish and
  spatial prompts that an anchor `desc` is a NOUN PHRASE naming a thing in
  the room, not a sentence about it — and have the composer trim a trailing
  full stop and lowercase a leading article before splicing. **Test:** a room
  whose anchors carry sentence-shaped descs composes a grammatical feature
  list.

### PS10. The outcome view and the narrator are composed before the commit, so a beat that changes the hour, the light or the weather reports the previous one
* **Origin:** stage order — `perception_outcome` and `narrator` run before
  `commit`, which is where `commit_scene_state` derives `day_phase` from the
  clock.
* **Live cases, three:** turn 4 skipped 2h20m from dawn to 08:30 and the view
  said *"The light is dim."* (dawn's value); post-commit the same room
  computed `lit`. Turn 17 skipped to full night and the composed view carried
  **no light sentence at all** while she lit a lamp in what post-commit was a
  `dark` room. Turn 17's narrator wrote *"a sparse drizzle drifts down ... to
  speckle the broad brim of her hat"* while that beat's own diff wrote
  `weather: {sky: clear, precipitation: none}`.
* **Severity:** wrong-but-recoverable, three times.
* **Recurs:** the placement half of F68 ("an approach completed at commit
  leaves the outcome view in the room left behind") — same class, different
  ledger.
* **Fix:** derive the beat's day phase, sky and room light from the diff's
  own `time`/`weather` before composing the outcome view, rather than after.
  The rule: *a view describes the world the beat leaves, not the one it
  found.* **Test:** a beat with an explicit time skip across a phase
  boundary; assert the outcome view's light sentence matches the committed
  phase.

### PS11. A weather drift introduced precipitation nothing asked for and no stage reported it
* **Origin:** the clock-driven weather drift (`drift_step` 11 at turn 16).
* **Live case:** turn 16 committed `{"sky": "fair", "precipitation":
  "drizzle", "intensity": "light"}` on a dry lake bed at the end of the dry
  season. No stage mentioned rain; the narrator of that beat wrote a dry
  dusk. The Director cleared it on turn 17.
* **Severity:** wrong-but-recoverable.
* **Recurs:** PD7's family (the clock's cumulative elapsed drives a weather
  re-roll), whose "overwrites the Director's declared sky" half was fixed;
  the "drifts into precipitation the setting excludes, silently" half is
  live.
* **Fix:** a drift that changes `precipitation` should be told to the
  Director as a notice on the beat it happens, so the beat can narrate it or
  contradict it. **Test:** force a drift step that adds precipitation; assert
  the Director payload carries it.

### PS12. Nothing can hurt, tire, thirst or chill a lone body
* **Origin:** none — the absence is the finding. `agents/director.py`'s
  `resolution_flags.contested` keys off REACTORS; with no reactor there is no
  contest, no `dice`, and the resolve writes no `conditions`, `vitals` or
  `consequences`.
* **Live cases:** turn 9, a deliberate fast descent of a twenty-pace
  salt-glazed revetment stair, hands full, at fifty-three, untested treads —
  `dice: []`, `contested: false`, zero conditions. Turn 10, midday, her
  canteen two rooms behind her — the narrator handed it to her. Turn 17, a
  night outdoors at `temperature: cold` — nothing. Across 21 turns:
  `conditions` 0, `vitals` 0, `consequences` 0.
* **Severity:** story-breaking for solitary fiction. A world with no other
  people has only the world for an antagonist, and this engine's world cannot
  act on a body.
* **Fix:** owner decision, and I would ask it as a question rather than
  propose a mechanism: *should a declared act against a stated physical
  hazard be contestable with no second party?* The engine already has the
  vocabulary — `dice`, `conditions`, `vitals`, `hedonic` — and only the
  trigger is missing.

### PS13. The hearing channel is live and empty for a world with nobody in it
* **Origin:** `agents/perception.py` / the sound field; there is no ambient
  sound percept for an unoccupied room.
* **Live case:** the narrator's `sensory_channels.hearing` was
  `{"status": "live"}` with no `this_beat` on **every captured beat**. The
  only hearing percept in twenty turns was turn 16's *"faint crunching of
  salt crust underfoot"* — her own footfall. Compounding it: on turn 5 she
  spoke inside a dry stone barrel vault and the interpret raised
  `claim:4:event ('her own voice comes back at her off the ceiling')`; the
  resolve returned no `fact_adjudications` verdict (warned as *"Unadjudicated
  player-asserted fact"*) and the narrator wrote **"No answer comes back from
  the stone. The Deep Cistern Vault keeps its silence"**. On turn 18 it
  doubled down: *"the barrel vault swallowed the sound without an echo"*.
  A dressed-stone barrel vault over dry flags is the most reverberant room a
  person can stand in.
* **Severity:** story-breaking for this genre; wrong-but-recoverable in
  general. Under the owner's rule it is a bug even though the engine followed
  its own rules: the rule is *hearing carries speech and events*, it produced
  a silent world and a vault with no echo, and it should say instead that an
  enclosed hard-surfaced room returns what is made in it.
* **Fix:** the room already carries `exposure`, `extent` and anchor
  `opacity`; a room-level acoustic property derived from them would let the
  view say what the place does to a sound without a word list. Minimum fix:
  adjudicate the fact claim rather than dropping it, so the narrator is not
  free to assert the opposite. **Test:** a player-asserted acoustic fact in an
  enclosed room receives a verdict.

### PS14. The player has no mind: zero memories, no thought channel, and interiority is answered with the temperature of a wall
* **Origin:** structural. There is no `character:<id>` step for a player, no
  `mind/psychology_runtime` pass over the persona, and no memory write.
* **Live case:** `SELECT count(*) FROM memories WHERE chat_id=?` → **0**
  after 21 turns. Turn 15, she speaks a memory that carries the story's whole
  moral weight (*"Nineteen houses and one dog, and they still made me sign it
  'no viable reclamation'. I signed it. I was right"*) and a decision (*"This
  one is not that"*); the narrator's answer is four sentences about stored
  heat in limestone, straw, and paper against a thumb. Turn 19, she writes and
  reads aloud the verdict the whole story exists to reach; the answer is the
  graphite ridges on the back of the leaf.
* **Severity:** story-breaking for a solo story, and the largest gap the run
  found.
* **Fix:** owner decision. The narrower, cheap half is a narrator payload
  key for what the player just *concluded or recalled* — the interpret
  already classifies it as an `authority_claim` with scope `effect` and
  subject `Mireille Adjani` — so the narrator is at least told that this beat
  contained a judgement. The larger half (does a persona accumulate memory
  and psychology like a character) is a design question, not a patch.

### PS15. A shed garment is minted as a room-level entity with a machine id, and the wardrobe loses it
* **Origin:** `persist/commit_attire.py`'s attire→entity projection.
* **Live cases:** turn 0, `tinted_glass_goggles_pushed_up_on_the_hat_brim_
  mireille_adjani` appears in `positions` with `state: {"clothing": true,
  "worn_by": "Mireille Adjani", "shed": true}` — goggles she is wearing,
  shed onto the road, on the opening beat, by nobody; they are gone from
  `attire.wearing` for the rest of the story. Turn 15, she takes her hat off
  and `a_wide_straw_hat_mireille_adjani` is minted the same way; when she
  puts it back on the wardrobe records it as `"wide straw hat"` — the article
  lost in the round trip.
* **Severity:** wrong-but-recoverable.
* **Fix:** a garment that is worn and never removed by any op must not be
  projected as shed; and a garment re-equipped from its projection should be
  restored under the string the wardrobe held, not the entity's name. **Test:**
  an opening attire list with a garment whose `covers` is empty; assert it
  stays in `wearing` and mints no positioned entity.

### PS16. When a specialist call fails, the prose author's assertions stand and nothing is encoded — and the same beat's view contradicts its own narrator
* **Origin:** the orchestration fail-open (`agents/director_fanout.py`).
* **Live case:** turn 11 (during the provider outage). Warnings:
  *"contact, spatial specialist call(s) failed, so their granted scope went
  unserved and the stage model's own content stands there (fail-open, working
  as designed)"*, then six reconciliation warnings — *"prose asserts 'resting
  on flagstones at wharf_slip' (subject 'mallet') but state_diff still does
  not encode it after self-repair"*, the same for the lamp and the notebook,
  the same for the canteen being carried. The narrator wrote *"On the
  flagstones, the ash mallet, the brass lantern, and the notebook settle into
  the grit, their release leaving her bare hands light and free."* The
  outcome view composed for the same beat read *"You feel the iron-hooped
  mallet's polished handle ... against your hands ... You feel someone's wire
  bale against your fingers."* She put everything down and was still holding
  it.
* **Severity:** story-breaking. The trigger was harness noise; the behaviour
  is the engine's. The fail-open is documented and it is what produced a beat
  that does not make sense.
* **Fix:** where a specialist's scope went unserved AND reconciliation says
  the prose asserts a change in that scope, the beat should not compose a
  view that asserts the old state — either the assertion is dropped from the
  prose or the view is suppressed for those percepts. The rule: *a beat may
  fail to encode a change; it may not narrate the change and then perceive
  its absence.* **Test:** stub a specialist to raise; assert the outcome view
  and the narrator do not contradict each other on the unserved channel.

### PS17. Two layout lints disagree about whether an extent decides a room's size, and one fires on a room that has one
* **Origin:** `world/spatial_lint.py` / `persist/commit_scene_state.py`.
* **Live cases:** turn 4 — *"Room 'middle_terrace_pans' is written size
  'large' and extent 24x16 paces, which is 'vast' floor; **the extent
  decides**, and the size word should agree with it."* Turn 5 — *"Room 'Deep
  Cistern Vault' **holds 3 and has no authored size**; perception is grading
  it 'vast' by default. Author scene_patch.rooms.sunken_cistern_vault.size to
  set it."* — and the vault carries `extent: {w: 10, d: 14}`.
* **Severity:** cosmetic, but it is engine advice that contradicts itself in
  consecutive beats and would send a host the wrong way.
* **Fix:** the "no authored size" notice should not fire for a room that
  carries an extent. **Test:** a room with an extent and no size word draws
  no default-size warning.

### PS18. `world_facts` written by the establish are committed nowhere and re-filed as unmet planning needs
* **Origin:** `director_establish.state_diff.world_facts` → commit.
* **Live case:** turn 0 wrote three world facts ("Lake Sarrat dried up a
  generation ago...", etc.). `wget(cid, "world_facts")` is **null** at the end
  of the run, and the commit warned *"3 planning need(s) recorded: the beat
  reached for setting fact '...'"* — the needs are still `status: "open"`
  twenty turns later, one of them naming the player herself.
* **Severity:** wrong-but-recoverable.
* **Recurs:** F4 and PB11 — planning needs filed for facts the payload
  already carried. Here the mechanism is sharper: the fact the Director
  *wrote this beat* becomes a need because nothing stored it.
* **Fix:** commit the establish's `world_facts` before the planning-need pass
  reads them; a fact the same diff supplies is not a need. **Test:** an
  establish writing `world_facts` produces no `setting_fact` needs for those
  strings.

### PS19. The Room reports measurements the engine silently clamped
* **Origin:** `world/spatial_geometry.normalize_extent`
  (`EXTENT_MAX_PACES = 24`) with no report to the author.
* **Live case:** the Room's reply told me *"Rectangular, 28 paces wide by 16
  paces deep"* and *"Composite shape, 32 paces wide by 18 paces deep"*; the
  registry rows hold `{"w": 24, "d": 16}` and `{"w": 24, "d": 18}`. Two
  differently-sized terraces became the same width. Nothing said so.
* **Severity:** cosmetic mechanically, corrosive to co-authorship: I am
  reading a collaborator's prose against rows it does not match.
* **Fix:** `normalize_extent` returning a clamped value should be reportable,
  and `plan_rooms`' result should carry the stored extent so the Room states
  what it wrote. **Test:** draft a plan with an over-cap extent; assert the
  tool result names the clamp.

### PS20. Small, real, and each one costs a sentence
* **`text` empty, `prose` full.** The narrator step blob carries
  `{"prose": "...", "text": ""}`; a reader keying on `text` gets nothing (my
  own reader did, on turn 9). Cosmetic; a footgun in four tools.
* **"You stand in the light."** — composed on turn 19 while her pose is
  `seated`. The light sentence has a hard-coded posture verb.
* **Narrator tense.** Present tense for seventeen beats, then past from turn
  18 ("No answer came... swallowed... She stood"), then present again at 19.
* **`inspect_plans` shows planned THINGS and not planned ROOMS** — it
  returned `{"plans": []}` immediately after four rooms were published, which
  reads as "nothing is planned" to a co-author. Naming, not behaviour.
* **`director_objects` has no vocabulary for pocket→hand**, so it wrote
  `{"op": "transfer", "from_id": "Mireille Adjani", "to_id": "Mireille
  Adjani"}` — a transfer from a body to itself (turn 1).
* **A `substance` add was discarded at commit** ("target is not present in
  the scene", turn 6) with no indication of which target.

---

# 4. Works — what behaved by the rules

* **The day cycle.** One anchor hour (06:10) survived five explicit time
  skips across 23 story hours; `day_phase` moved dawn → morning → midday →
  afternoon → night, and `spatial_light.room_light` moved every open room
  dim → lit → dark with it. This is the load-bearing system of the story and
  it did not slip once.
* **The light field with a carried source.** Turn 18, full night, enclosed
  vault, one lamp: *"Through the opening, only darkness. The light from brass
  hand lamp thins to half-light at [the intake arch] and [the revetment
  wall]."* Turn 19, seated: *"The light from brass hand lamp falls on [the
  revetment wall] and thins to half-light at [the intake arch]. You stand in
  the light."* Correct falloff, correct naming, correct darkness through the
  opening.
* **The plan reached the world where it was attached.** Every planned room
  adjacent to the room she stood in materialised with the Room's extent,
  shape, exposure and reciprocal vertical edge —
  `middle_terrace_pans` (24×16, rectangle, `up` to the terrace),
  `sunken_cistern_vault` (10×14, enclosed), `revetment_stair_chute` (6×20),
  `shoreline_wharf_pans` (24×18, composite). F42 and F47 both hold.
* **The Room's planted thing arrived verbatim** in the room the Room named,
  three beats after it was written, and became a real entity when she picked
  it up (`generation_requests` → `mallet`).
* **Player-state protection.** Four `"resolve restated X for Y; the assertion
  yields"` warnings across the run, each one catching a specialist re-emitting
  an existing record with blanked fields or a flipped `portable`. The merge
  kept the true record every time.
* **The movement backstop and the vertical edges.** Ten rooms on five levels;
  every `vertical: up`/`down` edge round-tripped, and `spatial_frame` fed the
  narrator correct `above`/`below`/`ahead` on every beat.
* **F63/F3 held for junk labels**; the one 4-word frontier that got through
  is PS8, which is about what the mint DOES, not about the refusal.
* **The retry did not build the world twice.** After three interrupted beats
  and three interrupted Room calls, `room_registry` holds seven rows with no
  duplicate uid, every turn has exactly eight steps, and only
  `perception_outcome` on turn 11 carries extra variants (three, one active).

---

# 5. The Writers' Room as co-author

Four sessions: a plan of the terraces below (145 s), the history and its
evidence (109 s), a push-back (137 s), and the town shelf plus two hard
questions (434 s, 19 model calls, 45 tool calls, after three attempts lost to
the provider).

**What it did, and did well.** It is a genuine collaborator with taste. Given
five constraints — cut limestone and salt, exactly one roofed thing and that
one dark at noon, a cistern where water would actually have been put, a stair
or a drop between tiers, nobody in them — it held all five and produced four
connected rooms with extents, shapes, exposures and correct vertical edges.
Given four pieces of physical evidence she had actually stood on, it produced
a two-stage failure of the water with a reading for each piece
(*"The hinge pintles were prised cleanly from the stone jambs ... This proves
an organized, deliberate evacuation"*), and marked its two invented claims
`proposal: true` with no citation while citing the room rows for the four
claims that were restatements. That citation surface is exactly right.

**It takes criticism and gets better.** I told it a punched lead tally plate
was the ruin handing her its own explanatory note. It removed it and replaced
it with a wedged gate, wedges driven from below, adze shavings under halite,
and tools set down bare on a tread — and explained why each is where it is,
ending *"There is no script or punched tally: Mireille has to read the iron
hoop on the mallet, the fresh curl of timber preserved under salt, and the
driven wedges to deduce that this town did not wind down through months of
slackening indifference, but broke off mid-stroke."* That is better than what
I asked for.

**It refuses honestly.** Asked whether it could make a planned room dark, it
said:

> I cannot mechanically make a room dark. The room schema provides only
> `exposure` (open, sheltered, enclosed), shape, dimensions, and adjacent
> barriers; it holds no lighting state, illumination tier, or ambient shadow
> flag. ... there is no dial or switch on a planned room that enforces pitch
> darkness at the engine level.

That is accurate — `plot_packages._plan_geometry` gave `plan_rooms` extent,
shape and parts (F47) and no `light` — and it offered the `director_note`
workaround while saying it is not the same thing. It also reported honestly
that `file_lore` failed *"because no canon lorebook is currently attached to
the story workspace"* and routed to a plot package instead.

**What it could not do.**
1. **Author darkness.** The one room it designed as the story's dark
   interior is `dim` at noon and `dim` at midnight. `plan_rooms` needs a
   light word, or `exposure: enclosed` with no source needs to mean dark.
2. **File lore in a fresh chat.** Its `file_lore` capability is dead by
   default because a new story has no canon lorebook. Its own honest report
   of this is the only reason I know.
3. **Reach the Director.** This is the big one and it is not the Room's
   fault: it published a shelf and a hall and the Director never saw them
   (PS5). Its *prose* did reach the Director — the minted duplicate hall was
   described as *"open to the sky where its timbers were systematically
   unpinned and hauled away"*, which is the Room's own salvage explanation —
   so lore crosses the seam and geometry does not.

**Where I would improve it.**
* **45 tool calls for two rooms and one thing.** `inspect_rooms` 7 times,
  `read_package` 9, `search_lore` 3, `scan_lore` 2, `inspect_structures` 3,
  `inspect_contradictions` 2 — mostly re-reading rows it had already read in
  the same session. A session cache would cut its wall clock in half.
* **Its reply prose does not carry its own proposal marks.** The structured
  `claims` field correctly separates cited fact from `proposal: true`
  invention; the reply I read presents both in the same confident register.
  A co-author should see which sentences are new fiction.
* **It reports numbers it did not store** (PS19).
* **A later package can contradict an earlier one and nothing notices.** The
  history said the town made an *"organized, deliberate evacuation"* that
  salvaged its valuable ironwork; four minutes later the sluice package said
  the crew *"broke off mid-stroke"* and left an iron-strapped mallet and a
  chisel on a stair. Both are good; nobody reconciled them, and
  `inspect_contradictions` has no notion of a semantic contradiction between
  published packages.

**Where it overstepped: nowhere.** It authored no mind (there was none to
author), never replaced my declared conduct, invented no world fact outside a
package, and put no person in a room after I asked it not to. When I asked it
for something it could not do it said so instead of faking it.

---

# 6. What I would change first

1. **Ask `contact_thing_label` before the person-shaped default in
   `composer._pose_referent`** (PS1). One call, already written, already
   correct on the live data, and it stops the engine telling a woman alone in
   a dead town that she is holding hands with somebody, three times a beat,
   for the length of a story.
2. **Send the Director every unretired planned room, not the ones next door**
   (PS5). Seven rows, 591 bytes, and it is the difference between the
   Writers' Room being a co-author and being a parallel universe. Everything
   the Room built above the middle tier was unreachable because of one scope.
3. **Give the narrator something in the hearing channel and something in the
   thought channel** (PS13, PS14). Every beat of this story was written out of
   the touch percepts because touch was the only channel with content — seven
   paragraphs opening "nothing answered" and fourteen opening with a surface
   pressing on her body is not a model failing at prose, it is a model writing
   the only payload it was given.
