# Measurement play run: Saltmarsh Crossing (2026-10-11)

The fresh story recommended after the Cwm Du fix wave
(`PLAY_2026_10_10_cwm_du.md`), played to measure that wave live: how often the
interpretation's re-ask fires, whether locals use the Room's lore, and whether
truths reach the minds they name. Scratch story 170 in the scratch play db
(never the owner's), served from the main checkout at e06dfb88 plus the three
commits the run made. Every page was read as fiction before any record.

## Setup

- **Story.** A grain and fishing town on both banks of the tidal River Wenn,
  joined by a chain ferry. The player, Agnes Holloway (persona 23), is a
  marine-insurance loss assessor come to judge whether the grain barge Swallow,
  sunk at her moorings three nights before, was lost honestly. The companion,
  Bethan Marsh (character 86), works the ferry; her brother was the barge's mate
  and has not spoken since. Both cards were generated from briefs.
- **Writers' Room.** In the prelude it was given the town's common layer (the
  sinking, the drowned skipper, the harbour master, the owner) and one fact only
  Bethan holds: her brother told her the foreman loaded the barge forty tons
  over her marks on the owner's order. A lived location (the town brief) was
  built at begin, in 219 s.
- **Settings and routing** as Cwm Du's: the scratch db unchanged, every call
  through OpenRouter.
- **Length.** 15 player beats, turns 4633-4656. Bethan's own frame (frame 8)
  played its beats between them once the player left the ferry.

## Numbers

- Beat wall time: median 69 s, mean 92 s, range 32-363 s. The first beat
  carried the opening plan and turn 0 (a scenario chat runs both on the
  player's first line). Cwm Du's median was 97 s.
- Spend: $7.27 of OpenRouter credit from $88.79 to $81.52, which also covers
  the fix wave's last replays, the copy rerolls below and the opening A/B.

## The wave, measured live

- **Her view and the re-ask (O8).** The re-ask fired on 0 of 15
  interpretations. Bindings by description went right: "the red-faced man at
  the windlass" (beat 3) and "the old hand" (beat 4) bound to the ferry hands
  her view showed her.
- **Truths reach the minds named (O12).** The Bethan-only fact, once filed as a
  truth (by the Room, mid-story, on the player's second ask), reached her as
  "something you already knew, long before" from the next turn. The opening had
  not filed it at all; see `ebc72e7e` below.
- **Lore at launch (O12).** The opening filed the common layer as two `common`
  lore entries, and the locals used it unprompted: "Everyone knew Ned. Best
  skipper on this stretch." (beat 2); "Tom's not right. Hasn't said a word
  since they pulled him out." (beat 3); the harbour clerk knew Rudd and Venn
  (beats 6, 9).
- **A part that places a body brings its channel (O26).** It brought one on 6
  of 15 beats (`entities__inside`, `entities__transit`,
  `contact_ops__interior`).
- **A body inside a thing stands in it (e06dfb88).** Not exercised: the opening
  laid the chain ferry as a room of its own between the two slips, not as a
  thing with an interior.
- **A figure's departure is the resolve's (b02510d6).** The declared
  destination reached the resolve (`goes_to` appears 23 times across its
  records), and the office boy sent for the harbour master went by an errand.
- **A runaway is asked once more (O27).** It fired in Bethan's frame (turn
  4647), and the fresh ask degenerated exactly as the first had ("repeating
  37-character phrase"), so that frame's beat stopped after `perception_act`.
  Cwm Du's recurrence, again.

## Fixed during the run

- **441f0cd0: the page named two ferry hands nobody had named to her.** Beats 4
  and 5 said "Goddricey took up the mooring line" and "Cortonold Gorleridge
  stood where he had stood". The interpretation binds the player's words to
  the body she means, and three narrator fields carried its words as written:
  `player_declared`, her acts in `current_events` and `spatial_frame.turned`.
  `_ordered_beat_events` resolved referents through a map of the registered
  cast alone. Now one floor (`narration._page_identity_scrub`) calls every body
  in those fields what her view calls it. Re-run on copies with the model
  stubbed, both beats' payloads carry neither name.
- **c85c7a63: the player could not leave the harbour office.** Beats 12 and 13
  declared the walk to the Grain Office and committed nothing ("Walk stopped
  ... nothing walkable leads on", 0 paces) while the page walked her down the
  quay. The furnishing had laid the chair over the only doorway and the desk,
  chart table, tide slate and window seat round a three-cell pocket. Furniture
  is never a wall now (`spatial_walk._path_past_fixtures`). Re-run from the
  resolve on a copy, beat 13 ended her in the counting-room. Beat 14 then
  walked her there live.
- **ebc72e7e: the opening did not file what only Bethan knew.** It filed the
  common layer as lore and the held fact only in a `director_note`, which
  reaches no mind. One card clause beside `file_lore`. Measured on the opening
  plan alone, same scenario and prelude: with the clause 2 of 2 openings filed
  the truth; without it 1 of 3.

## Open findings, by class (turn ids are chat 170's)

1. **What a body reads does not reach it** (`docs/UNBUILT_PERCEPTION.md`
   §1.200). Four reads, none on the page: the tally in the harbour book (beats
   9, 10), the foreman's signature (beat 10), the loading slip (beat 15).
   - The resolve left the read unanswered 3 of 3 times (two beats and a copy
     reroll), under a Room note phrased as a prohibition ("Do not let a
     character arrive at it ..."). A resolve clause -- "What the story keeps
     from someone stays kept by what is there, which may be false or missing,
     never by leaving what was asked unanswered" -- answered on 1 of 2 copy
     rerolls. Not landed, because of the next two points.
   - Answered, the read still does not arrive. The encoder authored it under
     `entities__examined` on beat 8 ("barley, 120 qr. ... signed Gorerford")
     and on the reroll, but filed it on her own survey ledger, which stood on
     the far bank (finding 2).
   - On beat 15 it filed the slip's text on the slip itself ("220 qtrs barley,
     40 qtrs wheat ... Consignor: Venn"), and still nothing reached her. She
     held the slip only within the beat (two transfers), which is no standing
     contact, and the interpretation wrote no `look` for "reads it line by
     line". None of `_things_read_by`'s three admissions fired.
2. **A thing a body carries is left where it was minted**
   (`docs/UNBUILT_WORLD.md` §1.199). The opening minted her ledger, lantern,
   bag and letter as free-standing things at the south slip. Her card has her
   "with a ledger under one arm and a dark-lantern handle in the other".
   - Beat 8: a transfer of the letter "to desk" resolved to nothing and so
     wrote nothing. Its state says it lies on the desk; it is still across the
     river.
   - Beat 5: "takes up her canvas bag" was encoded as the bag's position.
   - Beat 12's explicit pickup ("tucks it under her arm and takes up her
     lantern") put both things in her hands, and they have followed her since.
3. **One id absorbs every ledger.** Her survey ledger was minted at the
   opening with the alias "ledger", a generic noun.
   - Beat 7 minted the harbour's lading book as `lading_ledger`, and it is no
     longer in the scene.
   - Beat 8's encoder filed that book's tally on `agnes_ledger`.
   - By the end of the run, `agnes_ledger`'s description is the Grain
     Office's "Outward Cargoes" ledger from beat 14.
   A kind's name as an alias binds every thing of that kind to one id; how
   `lading_ledger` left the scene is not traced.
4. **The foreman has four names.** The Room's truth says Harry Cole. The
   world produced "Gorerford" (beat 8's encoder, the tally's signature),
   "Gorenton" (a reroll) and "Jacob Ayscough" (the harbour clerk, beat 11). The
   Grain Office then held three clerks, none of them him. The Room had offered
   to plant Cole as a person, and the player did not ask. But nothing
   constrains a figure model's answer to "what's the foreman's name", so each
   model names its own. The opening note also kept Cole's name itself out of
   the town ("The overloading and Harry Cole are NOT filed"), though the
   secret was the order, not who the foreman is.
5. **A walk declared `arrives=false` commits nothing** (beat 12), PA12 in
   `docs/UNBUILT_PLANNING.md`, measured again. The body stays in the room it
   set off from.
6. **A conveyance laid as a room has no dock edges.** The ferry's edge to the
   north slip stayed `closed_door` after it docked (beat 4) and after she
   stepped off (beat 5). The hand at the north rail reached her "in fragments,
   flattened by distance and river air". `apply_transit_dock_edges` drives only
   a thing's interior.
7. **The resolve's own continuity.** Beat 9 put the clerk "within arm's reach,
   his weight braced against the chart table's edge" and in the same paragraph
   "turned stiffly in the chair"; the page repeated both.

Turn ids are chat 170's in the scratch play db; the drive's per-beat logs were
scratch and are not kept.
