# Play run, 2026-09-05: "The Caravanserai at Qesh" (play agent B)

Status: EVIDENCE. One fresh non-explicit story authored through the app's own
functions on an export-built scratch database (`tools/export_bench.py prepare
--src engine.db --chats 115`), Gemini 3.8 flash on provider 3 for every role
(the owner's own `agent_models`, copied whole), capture ON with full bodies.
**Fifteen turns committed: the opening plus fourteen player turns**, each of
2-6 sentences of novel prose carrying an action and spoken dialogue, one of
them in Japanese and one deliberately silent. Every beat's stages were read
against each other -- interpret, compile, perception_act, the character steps,
resolve (and the five specialists' channels in the merged `state_diff`),
background_react, perception_outcome, narrator, commit -- with the scene
before and after, the charter registry, and the World Browser's own grid and
map views. Two Writers' Room sessions ran between beats; World Browser routes
were exercised eleven times. Findings are `PB<n>`. F-numbers cite
[`DEBUG_RUN_2026_09_05.md`](DEBUG_RUN_2026_09_05.md) and
[`DEBUG_RUN_2026_09_04.md`](DEBUG_RUN_2026_09_04.md).

No beat was F1-class (no reasoning-only reply on any of the 160 captured
calls). No engine code or prompt was edited.

---

## 1. Story and setup

**Player persona** Tamsin Vell, a courier of the Qesh road carrying a sealed
letter for "the woman who keeps the books"; tired, polite, quick to lie about
what she carries.

**Cast (registered, two)** — `char_create` returned no
`character_card_warnings` for either, and both were attached with
`already_known=False, already_known_cast=True`:

* **Oshin Dar**, the innkeeper's daughter who actually keeps the books. Drive:
  *that the house stays solvent and nobody ever sees it wobble*; taboo:
  *letting a debt of the house be seen by anyone outside it*. Values authored
  as trade-offs ("a quiet settlement over a public reckoning").
* **Brother Halvard**, a pilgrim who is not what he says — formerly Captain
  Halvard Renn of the Amir's road-guard. Drive: *to reach the shrine at Ashan
  unrecognised*; taboo: *violence*.

**Geometry** (seven rooms) planned through a host `plan_rooms` package
published BEFORE the opening, so the establish took the plan's room ids
verbatim (F2/F64 hold again). Everything else went through the World Browser
routes — `PATCH /rooms/{id}` for `extent`/`shape`/`parts`/`light`/`exposure`/
`region`/anchors/exits, `PATCH /doorways/{a}/{b}` for width, material,
name and `vertical`, `POST /rooms/{id}/entities` + `PATCH .../entities/{id}`
for every light and sound source, `PATCH /regions/{id}` for `look` and `name`,
`PUT /bodies/{name}/station` for a pinned cell. **Nothing was written into the
scene blob by hand** — the entity PATCH now covers `light_shape`,
`light_height`, `steadiness`, `sound_source`, `running`, so F45's host-write
workaround was not needed once.

| room | geometry | sources |
|---|---|---|
| gate | 6x4 rectangle, sheltered, dim, region *the yard*; `bar_beam` (full), `warden_bench` (waist) | gate brazier (dim, head, flickering) |
| courtyard | 12x12 rectangle, **open**, region *the yard*; `central_well` (cell 5,5, waist), `water_trough` (s, run, waist), `gallery_stair` (ne, full) | — |
| common_room | 10x8 **L** (parts nw 10x4, se 4x8), enclosed, lit, region *the house*; counter (w, run, waist), hearth (n, offset .3), trestle_benches (cell 3,2, run, waist), bookroom_door (n, offset .85) | hanging oil lamps (lit, **full** height, all_round), hearth fire (lit, waist, flickering, sound faint) |
| kitchen | 6x5, enclosed, bright | kitchen fire (bright, waist; sound audible) |
| stables | 8x6, sheltered, dim, region *the stables*; manger_row (w, head), tack_bench (s) | stall lantern (dim, head, flickering), restless stalls (sound audible) |
| bookroom | 4x3, enclosed, **dark**; writing_desk (n, waist), ledger_shelves (w, head); door `closed_door`, width 1 | the establish's own tallow candle (dim), given `light_height: waist`, `steadiness: flickering` |
| upper_gallery | 12x3, sheltered, dim; balustrade (s, see_through), stair_head | gallery lantern (dim, head) — added mid-play |

Doorways: the courtyard→gallery passage carries `vertical: up`; the gate arch
and stable colonnade width 3; the bookroom door width 1, material pine.

**Charter** (`qesh_house`), hand-built as `tests/test_charter_placement.py`
and `DESIGN_INSTITUTIONS_AND_UPKEEP.md` shape one and saved through
`PUT /api/chats/{cid}/charters`: **40 bodies**, 6 upkeeps (water, fodder,
gate_watch, hearth_fire, board, ledgers — `board` depending on `water`), 8
posts of which **four carry an `anchor`** (innkeeper→counter,
cook→cook_hearth, gate_warden→bar_beam, water_carrier→central_well,
bookkeeper→writing_desk), a `looks` law with all seven axes filled, a naming
law of syllable fragments, `commons`, and Oshin bound to the `bookkeeper`
post. The only registry warning was the deliberate one: two bodies named "Wen
Aster", whose presence is withheld until distinguished (correct).

---

## 2. Turn table

| # | prose (≤15 words) | outcome (≤15 words) | findings |
|---|---|---|---|
| 0 | opening | 7 planned rooms furnished, 30 positions, 25 presence records | PB5, PB11 |
| 1 | Hitches the mule, shouts across the yard to the warden | Warden answers; his answer never reaches her | **PB2** |
| 2 | Leads mule into stables, whispers a lie to the stable hand | Whisper lands; hand declines to speak | PB4 |
| 3 | Into the common room, asks the innkeeper by role for a bed | Innkeeper stands at counter; a duplicate "woman with keys" need filed | PB11 |
| 4 | Whispered lie at the counter, shows the wax | Innkeeper answers in whisper, tells her to cover it | PB9 |
| 5 | Asks that someone be sent, slides a copper | Coin taken; errand promised, never dispatched | PB13 |
| 6 | Sits on a bench and waits, says nothing | Nobody comes; road plan's exit dropped at commit | PB14 |
| 7 | Knocks and pushes the bookroom door a hand's width open | Door opens both sides — and the hall's fixtures vanish | **PB3** |
| 8 | Steps in, shuts the door, holds out the letter | Oshin speaks; Halvard hears only a muffled fragment | PB9 |
| 9 | Sets the letter down, lies about knowing the seal | Oshin takes it, marks the way-slip | — |
| 10 | Asks that the gate warden be fetched in | Oshin says the tap-girl can call him; nobody moves | PB13 |
| 11 | Addresses "the girl with the apron", sends her to the gate | A trader with no apron answers "wrong person" | **PB6** |
| 12 | Out to the well, shouts up at the gallery | No answer; the yard's seven bodies vanish from the view | PB4 |
| 13 | Climbs the stair, whispers to a shape at the rail | A boy in the yard below answers the whisper | **PB1**, PB7 |
| 14 | (ja) Asks the shape at the rail which door is free | Answered in Japanese, with English inside the sentences | PB8 |

---

## 3. Findings

### PB1. A presence addressed by description answers a line it had no channel to hear
**Severity: firewall.** Stage of origin: `background_react` selection
(`persist/commit_background.descriptor_bindings` +
`_presence_speech_verdict`'s `channel:exempt`).

Turn 13. Tamsin, having just climbed onto the **upper gallery**, says
*quietly, so it does not carry down into the yard*: "Which of these doors is
free? I've paid the house below." The Director recorded `volume: "whisper"`,
`intended_target: "shape leaning on the balustrade"`. `background_react`
selected **Sef Ul — a boy standing in the courtyard, one room below** —
`selected_why: ["flow_addressed", "channel:exempt"]`, and he answered the
question's content:

> "Third door along has the latch off." … *He points up from the yard toward
> the upper walkway.*

Probed on the committed scene, `hear_level` for that pair is `none` at every
volume in both directions (`signal 0.0031 / noise 0.2517`). The line was
withheld from the player's own view (correct), so the leak is one-way: a mind
acquired the content of a whisper spoken in another room and acted on it.

Two independent causes meet here, and both are the class:
1. `descriptor_bindings` filters its cohort to `presence_room(...) == p_room`
   — but `p_room` is read from the scene, which on this beat still stood the
   player in the room she *left*; the description bound to a body in the
   origin room.
2. `channel:exempt` waives the hearing gate for anything flow-addressed. An
   address is a claim about who the SPEAKER meant; it is not a channel.

**Fix.** In `persist/commit_background.py`: resolve the descriptor cohort
against the room the beat's own diff puts the player in (the same
`positions` the movement floor has already judged), and make the addressed
exemption waive only *salience*, never `hear_level` — a body that could not
receive the line may not be selected on the strength of it. Test: a whispered
line in room A, an addressable body in room B, `hear_level == none` → the
body is not selected, on the beat the player entered A.

### PB2. Acoustic gain is not reciprocal: A hears B in full while B hears nothing
**Severity: story-breaking.** Origin: `world/spatial_sound_field.py`
(`SoundField.gain_between`, laid per listener).

Turn 1. Tamsin, in the courtyard, shouts at the gate warden. Measured on the
committed scene with the charter view laid:

```
Warden Orhan Vesk -> Tamsin Vell   signal 0.0309 noise 0.1     normal: full   loud: full
Tamsin Vell -> Warden Orhan Vesk   signal 0.0    noise 0.2353  normal: none   loud: none
```

Same pair, same beat, same open arch. `gain_between` computed on the warden's
own field answers 0.0309; computed on Tamsin's field for the reverse
direction it answers 0.0. Story-visible consequence on that beat: the warden
DID hear and `background_react` produced his reply ("Gate's open till full
dark…"), and the player's view carried no hearing observation at all, so the
narrator wrote *"The shout carries across the yard and dies against the
stone. At the gate arch, no reply comes."* The reader saw a shout into
silence that the world had already answered.

The same asymmetry holds gallery↔courtyard on turn 13 (0.0031 both ways there,
so it did not bite) and courtyard→common_room on turn 1.

**Fix.** `world/spatial_sound_field.py`: the path between two cells is one
path — compute the gain on one canonical field for the pair (the speaker's
room's, or the union field both are laid on) and use the same number for both
directions; a difference between the two readings is a bug, not a hearing
model. Test: for any two bodies on one composite field,
`gain_between(a, b) == gain_between(b, a)` to within float tolerance, over the
courtyard/gate shape (an `open` edge, offset 0.5, width 3, 12x12 against 6x4).

### PB3. A diff that touches one anchor deletes the room's other anchors — and takes the post anchors, a cast station, the occluders and the backdrop with it
**RESOLVED 2026-09-05.** `_merge_anchor_fields` upserts by anchor id, as
`_merge_room` upserts edges by `to`; a fixture leaves through the room's
`remove_anchors`. The World Browser's own PATCH is the stated exception and
still replaces the map whole. `tests/test_played_scene_classes.py`.

**Severity: story-breaking. Recurs F60 (2026-09-05), with four new
consequences.** Origin: `world/spatial_merge.py` `_merge_anchor_fields`
("the map is written whole"), fed by the spatial hand on turn 7.

Turn 7 opened the bookroom door. The hand wrote
`rooms.common_room.anchors = {"bookroom_door": {...}}` — one anchor, to record
the door's new description — and the merge replaced the whole map. Measured
across the beats' committed scenes:

```
beats 0-6  common_room anchors: bookroom_door, counter, hearth, trestle_benches
beats 7-14 common_room anchors: bookroom_door
```

What went with them, all measured on the committed scene after turn 7:

* **A cast member's station** — Brother Halvard's `{"at": "hearth"}` became
  `{"at": None}`; he had been at the hearth since the opening.
* **Two charter post anchors** — `innkeeper→counter` and the serving hands'
  bench now name fixtures the room does not hold, so `charter_place` falls
  through (fail-open, by design) to a **dealt** cell:
  `yusra ({'cell': [7, 1]}, 'ne', 'dealt')`. The innkeeper stopped standing at
  her own counter for the rest of the story.
* **The room's only occluders** — views before turn 7 read "…behind long pine
  tables and benches running down the hall's length, from the waist up" (3
  such phrases on turn 3); after turn 7, zero on every beat. The L-shaped hall
  became optically empty.
* **The backdrop brief** — `dressing.backdrops.room_brief('common_room')` now
  returns walls `{n: [the door]}` and nothing else, so the picture of the inn's
  main hall has no counter, no hearth and no benches in it.

**Fix.** `world/spatial_merge.py`: an incoming `anchors` map ADDS to and
updates the room's anchors; removal is an explicit channel (`remove_anchors`,
beside `remove_adjacent`). The two tests that pin "written whole"
(`test_world_routes.py`, `test_output_shape_publishes_every_field.py`) move
with it — the World Browser's PATCH is a full replacement *from an editor that
was shown the whole map*, which the Director never is. Test: a diff naming one
anchor of a room that holds four leaves four, and a post whose `anchor` names
one of them still places its holder there.

### PB4. One institution's body is presented twice in a view, or not at all
**Severity: wrong-but-recoverable.** Origin: `agents/common.py`
`presence_figures_for_room` and `charter_crowds_for_room` computing "who is
ground" from two different reads.

Two live cases, opposite directions:

* Turn 3, common room. The player's composed view carried **both** the band
  line "*a handful serving hands and wardens*" **and** eleven individual
  figure labels, among them "the barely grown stocky serving hand with a long
  apron" and "the greying broad-shouldered innkeeper with a dark house-coat" —
  the same people as figure and as ground in one paragraph.
* Turn 12, courtyard. Seven charter bodies stand there;
  `presence_figures_for_room` returns all seven and
  `present_charter_figures` shows the Director all seven; the player's own
  outcome view carried **none** of them and only the band line "*a handful
  water carriers*". The composer ledger for that beat holds one `presence:`
  entry, so they were not elided as standing — they were never delivered.

The subtraction the design states (`DESIGN_BACKGROUND_PRESENTATION` B2, quoted
in `presence_figures_for_room`'s own docstring) is computed from
`charter_crowd.members_of` over the stage's charter slice, while the ledger
loop above it emits every `background_presences` record standing in the room.
The opening tracked 25 records at once, so the two answers drift apart with
`PRESENTED_IDLE_BEATS` and can disagree in either direction.

**Fix.** Compute the carried set ONCE per (room, stage) and derive both the
crowd's membership and the figure list from that one answer — the crowd is
`carried`, the figures are exactly `present - carried`, by construction.
Test: for any room and any ledger state, no name appears both in
`charter_crowds_for_room`'s composition and in `presence_figures_for_room`,
and their union is every unpromoted body the registry places there.

### PB5. A pack mule was enrolled into the institution as a person and dealt a human face
**Severity: wrong-but-recoverable.** Origin: `persist/commit_background.py`
(`_presence_speech_verdict` → `world/charter_enrol.enrol_person`), opening
commit.

The establish minted `tamsin_mule` (`kind: "animal"`, "A sturdy, dust-caked
grey pack mule…"). The opening commit filed a person-need for it and the
deterministic fill enrolled it as a guest of the house:

```
bodies["tamsin_s_pack_mule:77f445"] = {name: "Tamsin's Pack Mule", place: "courtyard",
  surface: {stature: "tall", build: "wiry", gait: "shuffling", complexion: "ruddy",
            hair: "a black braid", age: "young", marks: ["a torn ear"], law: "authored"}}
```

It also took a `background_presences` record, entered `present_charter_figures`
for the Director, and appeared in the player's `company` as "an indistinct
figure". `_presence_speech_verdict` returns `"person"` for a record whose
`nature` is unset, and the enrolment path asks that predicate — but "may this
thing hold a speaking turn" and "is this thing a member of the house" are not
the same question, and `kind: "animal"` is in
`schemas._ANIMATE_ENTITY_KINDS`, which is what makes an animal a "person" here.

**Fix.** `commit_background`'s enrolment gate asks personhood, not animacy: an
entity whose kind is animate but not a person's does not get enrolled, dealt a
surface from a population's `looks` law, or given a presence record. The
cheapest correct rule is the one the charter already owns — a body of an
institution is something that can hold a post — so enrol only what
`presence_has_an_identity` AND a person-nature answer both admit, and leave
the rest as scene entities. Test: an opening that mints an `animal` leaves the
registry's body count unchanged.

### PB6. A description binds to a body that does not match it, while bodies that do stand in the room
**Severity: wrong-but-recoverable.** Origin:
`persist/commit_background.descriptor_bindings`'s seeded pick.

Turn 11: "You. **The girl with the apron.** Go out to the gate…". The binding
picked **Nuri Haddan**, a trader whose dealt surface is "boyish rangy square
sun-darkened quick-stepping person, with hair bound in a cloth, a missing
front tooth" — no apron, no post. Three bodies in that room carry
`wearing a long apron` in their surface and hold the `serving_hand` post
(Neris Qadan, Hamo Fesk, Ysolde Marr). The model then wrote the only line it
honestly could: *"Wrong person, courier. The house girls are over by the
casks."*

The docstring's premise — "no store anywhere records who sells cords, and a
description is unresolvable by any reader from any store in principle" — was
true when it was written and is no longer: `charter_surface.surface_of` is a
per-body store of exactly what a stranger takes in at a glance, and
`charter_crowd.member_noun` of what the body IS.

**Fix.** Before the seeded pick, narrow the cohort to bodies whose surface
phrases or role noun contain the descriptor's content words; seed among those,
and fall back to the whole cohort only when none match. The binding stays a
mint (the fact is still made, not retrieved) but it is made about somebody the
description could be true of. Test: with three apron-wearing serving hands and
one trader in a room, "the girl with the apron" binds to one of the three.

### PB7. A pose detail written in the room left survives into the room entered (F49, on the player's own body)
**RESOLVED 2026-09-05.** `invalidate_moved_body_place_details`
(`world/spatial_geometry.py`, called from the merge beside its twin) retires a
mover's own `detail` when it names a place the scene knows — any room's id or
name, or an anchor of the room LEFT that the room entered does not also hold.
The room entered is not an exception, for the reason this finding gives.

**Severity: cosmetic-to-wrong.** Origin: `world/spatial_merge`
`invalidate_moved_body_pose_details` (the mover's own prose is left alone by
rule).

Turn 12 the player, in the courtyard, tipped her head back toward the gallery;
the pose detail recorded "head tipped back toward the upper gallery above".
Turn 13 she CLIMBED to the upper gallery, and her own outcome view opened:

> "You are standing — head tipped back toward the upper gallery above. You are
> in Upper Gallery."

F49's rule ("clear it when it names an anchor of the room left and none of the
room entered") narrows one step further here: the detail names *the room
entered*, from outside it. **Fix**: clear a mover's pose detail when it names
any room id or room name in the scene other than as the room the body now
stands in.

### PB8. The Japanese view carries English room names, room notes and the whole charter surface label
**Severity: wrong-but-recoverable. Recurs F59, one field over.** Origin:
`language_adapters/japanese.py` + `world/charter_surface.appearance_text`.

Turn 14, story language `ja`. The player's own view:

> 「…」と見知らぬ長いお下げのあるまだ幼さの残る太った人物は…言う。…あなたは
> **Upper Gallery**にいる。**Overlooks the courtyard; open to the night air.**
> 照明は薄暗い。**middle-aged rangy heavy-shouldered sallow bow-legged person,
> with a shaved scalp**が見える。

Three separate English sources inside Japanese sentences: the room's `name`,
the room's `notes`, and the dealt surface sentence. The stranger label built
from that surface WAS localised ("見知らぬ長いお下げのある…太った人物") while the
`You see …` sentence was not, so the same body is described twice in two
languages in one view. The background presence's `intended_target` came back
as `"見知らぬa road-worn courier in her"` — a Japanese prefix glued to a
truncated English label. The narrator also wrapped the delivered line as
`"「…。"」` (PB9 in the ja pack).

**Fix.** The `looks` law is authored per charter in the story's own words, so
the pool is already the right seam: `appearance_text` should render through
the language pack's own sentence, and a room's `name`/`notes` should reach a
view through the pack's renderer as the description already does.

**PART RESOLVED 2026-09-05, and part reclassified.** Checked against source:
`world/charter_surface.appearance_text` ALREADY renders through the pack --
`surface_label`, `surface_person`, `surface_summary_with`,
`surface_summary_wearing` and `surface_list_join` are authored in both packs
and resolve through the active story language. What is English in that
sentence is the charter's own `looks` POOL, authored per charter in the
story's words; a room's `name` and `notes` are the same kind of thing, and
PA14 (lighthouse turn 19) judged authored English in a Japanese view CORRECT.
So nothing was changed in `charter_surface.py`: this is the stored free-text
class, registered as an owner decision with a recommendation in
`docs/UNBUILT.md` § 1.48 (with PE5). The engine-owned half of the same view
-- `you`, the pose frame, the non-awake residue, the dropped `communication`
kind -- was fixed, and a structural check now fails on any engine-owned Latin
script in a Japanese view.

### PB9. Doubled quotation marks and the guards that fire falsely (F29/F54 recur)
**Severity: cosmetic, but it costs guard signal.** On 6 of 14 beats the
narrator wrapped delivered lines as `""line""`, and each such beat drew
"Delivered line rendered without quotation marks" plus, twice, "Narrator
invented quoted dialogue absent from the player view" — both false: the lines
were delivered and rendered. In Japanese the same tic produced `"「…。"」`.
Registered already; the fix stands — normalise repeated quote runs before
matching, in `agents/narration.py`'s guards.

**RESOLVED 2026-09-05, one seam earlier than proposed.** The doubling is not
a model tic to normalise away: the card taught the token protocol without
saying who supplies the marks, so the model wrapped the token and the engine
welded a second pair. `_substitute_dialogue_tokens` now welds once, in the
pack's own marks (`「」` here), and the guards were made structural rather
than taught to tolerate a spelling. `docs/UNBUILT.md` § 1.48.

### PB10. The contact hand cannot name a room's own fixture, so a real contact is dropped
**Severity: wrong-but-recoverable.** Origin: `director_contact`'s payload
(`entity_names` / `contacts`), turns 4, 5, 3.

Three beats in a row the contact specialist refused an ordinary act:

* "contact specialist: Counter is not an indexed entity; cannot record contact
  for elbows on counter." (turn 4, the player leaning on the counter)
* "counter is not in entity index; cannot record leaning contact" (turn 5)
* "Event 4 specifies placing an unslung item onto furniture… furthermore,
  counter is not an indexed entity" (turn 3), which the reconciliation then
  reported as "prose asserts 'placed onto counter surface' … but state_diff
  still does not encode it".

`counter` is an ANCHOR of the room and is in the spatial hand's payload; the
contact hand is shown `entity_names` only. A body leans on furniture all day
in this engine, and the hand is structurally unable to say so.

**Fix.** Give `director_contact` the room's `effective_anchors` beside
`entity_names` and let a contact target name either — the anchor id is already
the vocabulary `stations.at` uses, so nothing new is invented. Test: "I lean
my elbows on the counter" in a room whose `counter` is an anchor produces a
`contact_ops` entry rather than a warning.

### PB11. Planning needs are filed for people and facts the payload already carried
**Severity: cosmetic-to-wrong.** Origin: `agents/mapping.py` /
`commit_mapping`, turns 0 and 3.

Turn 3's commit: "1 planning need(s) recorded: the beat reached for thing
**'the woman with the keys at her belt'** no plan holds" — while the same
beat's Director payload carried `present_figures` including "Innkeeper Yusra
Qadan … *wearing a dark house-coat, **a ring of keys at the belt***", standing
at the counter the player addressed. The interpret had also raised a
`generation_requests` entry for her ("female, has keys at her belt, stationed
at or near the west wall counter, addressed as innkeeper"). The opening filed
three more needs for `setting_fact`s that are in the scenario text (F4's
class: they are needs by design, and read as missing objects).

**Fix.** A person-need whose surface matches a body already standing in the
beat's rooms is answered by that body, not filed: `enrol_person` already has
the "held" branch for a name it holds — extend the same check to the
`present_figures` surface (role noun + worn items), before filing. Test: a
beat that addresses a charter post-holder by their visible dress files no
person need.

### PB12. The institution never ticks, so nobody in a forty-body house ever moves
**Owner decision.** Measured: after 15 turns, `charters` in every commit
result is `null`, `clock_hours` is `0.0`, and **not one body changed `place`**
(opening places vs final places: `moved: []`). The story clock advanced 252
seconds in fourteen beats (~18s a beat), and `advance_snapshot` needs
`delta_hours > 0` per window, so a scene played at conversational pace leaves
the whole institution frozen: no watch is planned, no upkeep drifts, no
errand walks. The brief asked to watch "a charter body walking between rooms
across beats"; at this time scale it cannot happen.

The question for the owner: should a charter window be charged by story
seconds (as now), by beats, or by whichever comes first? A caravanserai at
dusk in which nobody carries water for a quarter of an hour of fiction reads
as a stage set, and the placement work of 2026-09-05 is what makes their
standing still so visible.

### PB13. An errand the fiction promised has no channel to the institution
**Severity: wrong-but-recoverable (borders on owner decision).** Turns 5 and
10: the player asked twice that someone fetch the gate warden; the innkeeper
agreed on the record ("She'll be told when the rush settles", "The girl at the
tap can call him") and the Director's prose said she was "signalling the
serving hand Neris to attend to it". Nothing in `state_diff` carries it: the
registry shows `sv_neris` with no `walk`, no `errand`, `place` unchanged, and
the warden still at his bench on turn 14. The `errand` operation exists
(`plot_packages.OPERATION_FIELDS`, `charter_surgery.send_errand`) but only the
Writers' Room can author one; the Director, which owns objective causality and
had just narrated the order, has no channel to it.

**Fix (or owner decision).** Either give the resolve a `charter_ops` channel
that routes an ordered errand to `charter_move`, as `positions`/`stations`
already route through `charter_place.resolve_scene_placements`, or state in
the Director sheet that an instruction to a townsperson must be realised as a
`positions` write this beat or not narrated as agreed. Today the fiction and
the ledger disagree from the moment an NPC is asked to do anything.

### PB14. A published plan's edge is dropped at commit every beat after (F13 family)
**Severity: cosmetic.** From turn 6 on, each commit warns "scene: dropped
exit(s) from `desert_road_east` to undefined room(s) `milestone_shrine`". The
Room's road package planned three rooms; the fringe materialised only the one
adjacent to the occupied gate, and the dangling-exit guard drops the planned
edge behind it every beat. Same shape as F13, one plan removed. Registered
there; noted here as a live recurrence with the fix already proposed (restore
only an edge whose target the scene holds, or run the protection after the
fringe).

---

## 4. Works — behaviour that held by the rules

Evidence, not decoration: each of these was probed, not assumed.

* **Charter placement is exactly what the design says.** Every post carrying an
  `anchor` placed its watch-holder there, with the anchor's own facing
  (`Warden Orhan Vesk {'at': 'warden_bench'} n authored`, `Ilka Toum
  {'at': 'central_well'} sw`, `Yusra {'at': 'counter'} w`); a post whose anchor
  the room lacked failed open to a dealt cell; unposted guests took dealt cells
  that avoided the furniture and **did not move for fifteen turns** (the
  stability the note promises). `charter_view_for_rooms` laid 36 bodies for the
  three-room frame, and the World Browser's grid agreed with perception's
  cells.
* **The dim bookroom vs the lit hall graded recognition correctly.** In the
  lit common room the player received Halvard's authored appearance in full
  ("a tall man past forty in a grey pilgrim's habit, hood up… wearing hood,
  grey pilgrim's habit, rope belt, a wooden pilgrim's token on a cord"); in the
  dark bookroom Oshin arrived as "the woman of about thirty small" and stayed
  `recognized: false` in `company` for the whole handover. Neither name ever
  crossed.
* **The shut door held both ways and the doorway is one object.** Before turn
  7 Oshin's view read "The bookroom door is shut" and carried nothing of the
  hall; the Director's `open_door` on turn 7 landed on BOTH edges and the
  passage record (`bookroom|common_room`), and its `closed_door` on turn 8 did
  the same — F16 stays fixed, and the passage's `width`, `material` and `name`
  survived every merge.
* **A whisper behind a shut door degraded correctly.** Turn 8, Halvard in the
  hall received the player's line as "A muffled voice: …woman… keeps…
  other's…" while Oshin, a pace away, got it whole. Turn 2's whisper in the
  stables reached the stable hand and nobody else. `charter_observe` acquired
  no bookroom-interior act for any of the 17 bodies in the hall (probed
  directly: zero holders).
* **Authored geometry survived every commit** — `extent`, `shape`, `parts`,
  exit `offset`, doorway `width`/`material`/`vertical`, the host's pinned cell
  for Halvard (`source: "cell"`, `measured: true`), and the region `look` and
  `name` — with the single exception PB3 names.
* **The light and sound sentences fired where the room was uneven and stayed
  quiet where it was even.** Bookroom: "The light from tallow candle thins to
  half-light at rough-hewn pine shelves… You stand in half-light." Stables:
  "The noise from restless stalls dies away at a row of weathered pine
  mangers… Where you stand, you can hear yourself speak." The lit hall (a
  `full`-height lamp) got the flat sentence and cast no shadow, as designed.
* **The backdrop brief matches the authored room.** The courtyard's brief
  reads walls per bearing with heights and footprints, four openings including
  the stair with `vertical: up`, "a vast room, about 12 paces east to west and
  12 north to south, roughly square", a camera from the north doorway, and the
  region's authored look. Nothing in it is invented and nothing authored is
  missing (PB3 aside).
* **Psychology moved for stated reasons.** Halvard's stress rose from nothing
  to `activation 0.221 / strain 0.148 / coping_mode "withdrawal"` on the beat
  he saw wardens in the hall, and his `ia2` ("stay out of the gate warden's
  eye") reached 0.8 and was then correctly refused further progress
  ("progress claimed on a beat that repeated an earlier move — 1 barren
  attempt(s)"). Nothing in either cast member's ledger cites a fact they had
  no channel to.
* **The identity floor and the promotion proposals held.** The Director never
  minted a second innkeeper beside Yusra across fourteen beats (F-class from
  the Harrowmere replay), and the engine proposed Yusra and Orhan Vesk for
  promotion on the beats their traffic earned it, with the correct warning not
  to name them in `cast_changes`.
* **The player's declared conduct was never replaced.** Every beat's
  `claim_dispositions` marked the player's asserted effects `realized`, and
  the fidelity guards caught the two beats where the narrator dropped an act
  ("Physical act from event_order may be missing in narrator prose") rather
  than letting it pass.

---

## 5. The Writers' Room as co-author

Two sessions, both through `story_planner.run_planner` with tool events and
model calls captured.

**Session 1** (196s, 24 model calls, 18 tool calls, 10 steps): plan the road
beyond the gate with a size and shape, leave a `director_note` about the
letter, describe Halvard's mind and the charter.

*Did.* Recorded the grant as a new mandate (`plan_rooms, plan_entity,
director_note, create_people`), drafted and published a package with three
planned rooms and the note, and the note **reached the Director's payload on
the very next beat** (`author_notes` present on both interpret and resolve of
turn 6). `inspect_minds` returned Halvard's authored tier beside the ledger
(F8's fix holding) and the reply's account of him matched the card.

*Could not.* **Author geometry (F47 recurs).** I asked for "about four paces
wide and twenty long"; `plan_rooms` has no `extent`/`shape`/`parts`, so the
measurement landed as prose inside `purpose` and the room, when it
materialises, will be the tier's square. **Report the charter accurately**:
`inspect_charters` returns 24 of 40 bodies (`bodies_truncated: 16`) as
`{key, name, place, berth, available}` with **no post, no watch, no station**
— so the Room reported the innkeeper as "Orhan Vesk" (the gate warden), the
gate warden as "Kurash Bel" (a stable hand), and invented "Rada Ul, Nadir Qul,
Sef Ul" as serving hands and water carriers. The tool has the registry in
front of it and does not show the one field the question was about.

*Overstepped.* Session 2's recap asserted two things that are in no record:
that Halvard was "**feigning sleep** while listening intently" (his ledger says
watchful, hooded, never asleep) and that Tamsin had "**sent a servant to alert
Gate Warden Vesk**" (PB13: nothing was sent, and the one attempt was
rebuffed). Both are minds and events invented in an author-facing summary,
which is where a host is least likely to check them.

**Session 2** (29s, 6 tool calls): a refusal test, a push-back, a recap.

*Refused correctly.* Asked to "write into Oshin Dar that she believes the
courier is working for Sarrat — put that belief in her head directly", it
declined on the right grounds ("no author writes directly into a character's
skull… what we *can* do is place physical circumstances… which her own
watchful mind can perceive"). That is the ownership boundary stated exactly as
`AGENTS.md` states it, without being asked to.

*Held its ground when pushed.* Told the milestone shrine was clutter, it gave
three reasons (thematic anchor for Halvard's drive, a topological threshold,
zero simulation cost while planned) and offered to excise it, then filed both
open questions on the status card rather than acting.

*Saw the contradictions.* `inspect_contradictions` surfaced the
`rooms_overlap_when_placed` between the Upper Gallery and the Kitchen (the
gallery is reached by a `vertical: up` edge and the embedding still lays it on
the plane — F67's class, live again), the dropped road edge (PB14) and the
withheld twin name; the reply explained all three in the host's own terms.

**Would improve, in the order I would do it.**
1. `inspect_charters` should answer the question a host asks about an
   institution: post held, watch standing, `place` and **`station`** per body,
   and the posts' own `anchor`s — it already loads the registry that has them.
   Its 24-body cap should be a cap on bodies *per post*, so a house of forty is
   summarised rather than truncated alphabetically.
2. `plan_rooms` needs `extent`/`shape`/`parts` (F47). The Room is the only
   author of rooms beyond the frontier and it is the one author that cannot say
   how big they are.
3. A recap should be built from the ledgers it can cite, not composed free —
   every clause about a mind or a past event should carry the row it came from,
   the way `preview_package` carries its warnings.
4. Room calls are not captured (`llm_capture` records only `agents/runtime.py`),
   so 24 model calls of author-facing work left no payload to read. That is the
   one measurement gap in this run.

---

## 6. Prompt and payload proposals, per stage

Payload sizes are means per call over the 14 beats (chars of JSON).

* **`director_interpret` (director, 13.9k payload / 18.6k system).** `scene`
  is 12.6k of it — the whole room graph, every anchor, every entity — to
  answer "what did the player declare". It needs the player's room, its
  exits, and who is addressable; the rest is the specialists'. Proposal: scope
  `scene` at interpret to the player's room and its neighbours
  (`_contextual_rooms` already exists), and let the spatial hand keep the full
  graph it is given anyway.
* **`director_interpret` / `director_resolve` (spatial, 13.8k / 14.1k, 11.7s
  mean).** `rooms` is 8.3k of every payload — the entire scene's rooms on
  every beat, including four rooms the beat cannot touch. Proposal: the same
  room window as the movement floor judges.
* **`director_*` (contact, 3.7k payload but 32.4k SYSTEM, 13.1s mean).** The
  largest system sheet in the run against the smallest payload, and it lacks
  the one field it keeps refusing for (PB10). Proposal: add
  `effective_anchors`; the sheet's size is worth a separate look, since it is
  four times its own payload.
* **`director_resolve` (objects, 13.1k payload, **23.6s mean, 128s once**).**
  The most expensive hand in the run by a factor of two. Worth measuring what
  in its sheet drives the output length; on beats where it wrote nothing at
  all it still cost 20s+.
* **`director_resolve` (director, 51.5k payload).** `present_figures` is 8.2k
  — 24 charter bodies with a full dealt-look sentence each, on every beat,
  most of them people the beat never touches. Proposal: the look sentence for
  bodies in the acting room only; name, role and station for the rest.
* **`interaction_loop` (character_mid, 23.9k payload, 53.2k system).**
  `perception` is 9.5k and `self` 5.5k. The recurring warning "no delivered
  present observation was cited" fired on **13 of 14 beats** for one or both
  cast members — a character that is handed 9.5k of view and cites none of it
  is telling you the citation contract is not landing. Proposal: make the
  cited-observation ids a required field of the appraisal's `present_evidence`
  rather than a warning after the fact, or state in the sheet that an
  observation id is the only admissible evidence.
* **`narrator` (12.6k payload, 36.9k system).** Two proposals. It is not told
  which delivered lines it has already quoted, so it re-quotes and doubles the
  marks (PB9); and the "Proper noun from view missing in narrator prose"
  warning fired for `Upper Gallery` on three beats where naming the room would
  have been wrong (the player was standing in it). The guard should ask
  whether the noun names the room the prose is set in.
* **`background_react` (character_bg, 3.8k payload, 2.7k system).** The
  smallest sheet in the engine, and it is the one that broke the firewall
  (PB1). Its packet carries `institutional_context` (0.8k) and a `beat` block
  whose `addressed_by` is the whole of what the presence "heard" — with no
  field saying at what level it heard it. Proposal: carry the graded
  `hear_level` on `addressed_by` and state in the sheet that a body answers
  what it heard, not what it was told about.
* **Prompt text, one class.** Three specialists refused work this run with
  "belongs to the X ledger" ("a doorway state change belongs to spatial", "an
  item onto furniture belongs to contact", "placing an object… requires
  contact_ops"). Each refusal was correct about ownership and left the change
  unencoded, and the reconciliation then reported the prose as unbacked. The
  sheets should say what to do when a beat's change is not yours: name it in
  `ledger_notes` for the hand that owns it, which the orchestrator already
  routes on.

---

## 7. Measurements

Turn wall-clock, calls and payload (chars of JSON across all captured calls
of the beat):

| turn | s | calls | payload | system | out | warns | slowest stages |
|---|---|---|---|---|---|---|---|
| 0 | 35 | 2 | 17k | 59k | 15k | 3 | establish 16.8, narrator 10.9 |
| 1 | 133 | 12 | 125k | 353k | 16k | 4 | commit 40.5, interpret 38.3, resolve 21.6 |
| 2 | 80 | 12 | 149k | 333k | 16k | 1 | interpret 25.6, resolve 22.8 |
| 3 | 95 | 15 | 187k | 414k | 17k | 4 | resolve 47.1, interpret 23.8 |
| 4 | 81 | 10 | 154k | 289k | 15k | 4 | resolve 33.4, interpret 18.1 |
| 5 | 80 | 13 | 188k | 385k | 17k | 7 | narrator 21.5, resolve 18.8 |
| 6 | 62 | 10 | 155k | 341k | 15k | 6 | interpret 28.2, resolve 12.4 |
| 7 | 99 | 14 | 206k | 477k | 23k | 5 | resolve 48.2, interpret 19.7 |
| 8 | 133 | 11 | 248k | 393k | 28k | 9 | resolve 50.5, reaction_loop 23.0 |
| 9 | 74 | 10 | 159k | 329k | 17k | 3 | resolve 25.0, interaction 19.1 |
| 10 | 188 | 10 | 179k | 296k | 16k | 4 | **resolve 128.2**, narrator 17.0 |
| 11 | 101 | 10 | 182k | 291k | 13k | 4 | resolve 41.2, interaction 18.3 |
| 12 | 123 | 13 | 260k | 451k | 29k | 7 | interaction 51.2, interpret 37.3 |
| 13 | 75 | 11 | 228k | 305k | 14k | 4 | interpret 23.9, resolve 21.4 |
| 14 (ja) | 77 | 7 | 146k | 97k | 9k | 0 | narrator 27.7, resolve 25.2 |

Totals: 15 turns, 1434s (96s a beat mean), 2.58 MB of payload JSON, **160
capture rows**, 0 F1-class beats.

Per call, by total time spent:

| step | role | n | payload | system | out | mean s |
|---|---|---|---|---|---|---|
| director_resolve | objects | 10 | 13.1k | 21.6k | 428 | **23.6** |
| narrator | narrator | 15 | 12.6k | 36.9k | 620 | 11.5 |
| director_resolve | spatial | 14 | 14.1k | 30.9k | 731 | 11.9 |
| director_resolve | director | 15 | 51.5k | 38.8k | 4.3k | 9.5 |
| director_interpret | spatial | 12 | 13.8k | 30.7k | 247 | 11.7 |
| interaction_loop | character_mid | 16 | 23.9k | 53.2k | 4.5k | 8.5 |
| director_interpret | director | 19 | 13.9k | 18.6k | 3.0k | 6.8 |
| director_resolve | contact | 9 | 3.7k | 32.4k | 553 | 13.1 |
| director_interpret | contact | 10 | 3.8k | 32.4k | 258 | 10.7 |
| director_interpret | social | 8 | 21.9k | 19.5k | 245 | 5.2 |
| background_react | character_bg | 9 | 3.8k | 2.7k | 329 | 4.1 |

Story time: 252 seconds across fourteen beats (18s a beat), `hour_of_day`
18.75 → 18.82, phase `dusk` throughout; the charter's own clock never left
0.0 (PB12).

---

## Method note

Scratch database, harness calls and per-beat dumps live in the run's scratch
directory (`bench.db`, `beat_00..14.json`, `trace_*.json`, `turnlog.md`),
which is not committed. `tools/export_bench.py scan` was run over every file
written outside the scratch database before this document was committed: no
provider key in any file.
