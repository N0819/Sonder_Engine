# Validation play run: Cwm Du, Gallery Nine (2026-10-10)

The validation run the immersion round promised: a fresh story with everything
the two immersion waves built switched on, played beat by beat and read as
fiction before any diff. Scratch story 167 in the scratch play db (never the
owner's), served from the main checkout at c11f2a5e plus the three fixes the
run itself made.

## Setup

- **Story.** A slate-mining village in a Welsh valley at dusk. The player, Nell
  Hartley (persona 22), is a Crown mines inspector carrying a brass bull's-eye
  lantern and a flame safety lamp. The companion, Ffion Rees (character 84),
  is the banksman who let a shift go down knowing the timbering report was
  signed blind. Both cards were generated from briefs, never hand-built.
- **Writers' Room.** It was briefed with full authority and given the facts as
  world facts: the deputy Emrys Vaughan signed the report for a shift he did
  not work, and the far props were cut from green larch. It laid the valley as
  19 rooms and 3 charters in 18 calls and 385 s.
- **Settings, on the scratch db only.** `active_preset` Default (the owner had
  switched their own db off `tes` the same day); `prompt_cache_deny` `mypc`;
  `layout_solver_tier` on; `auto_promote` on with `promote_after_addressed` 2.
- **Routing.** Every model call went through OpenRouter (the NanoGPT
  subscription was expended): GLM 5.2 and 5.3, Gemini 3.8 Flash for the
  encoder, DeepSeek v4.1 Flash for the Room, Jev 1.13 for decisions.
- **Length.** 15 beats after the opening (turns 4616-4631), with two rerolls
  and one edited rerun. Stopped there because the open defects compound:
  names drift, the player strands, speech drops.

## Numbers

- Beat wall time: median 97 s, mean 109 s, range 72-169 s (18 runs, rerolls
  included). Brackwater's median, before the 2026-10-08 fixes, was 178 s.
- Opening 303 s (171 s before the turn was accepted); the launch itself 410 s.
- Spend $6.50 through OpenRouter, the launch and the Room's fills included.
- The tell scene floor (`jev.TELL_SCENE_FLOOR`) fired once in the run, and on a
  valid cue (turn 4628: "lips moving in a soundless rapid count as the
  overman's answer starts" -- the player heard that answer).

## What worked, read as fiction

- **The investigation's payoff landed.** The beam went on the far props and a
  hand went on the wood: "The wood was wrong under her hand. Sappy ... This prop
  had been cut green and stood wet in a wet heading, and the roof had found it
  out." The Room had built the green-larch consignment into the gallery.
- **The cage descent and the shaft read as places** (turn 4621), and so did
  the lamp-room book with its blank return columns (4619).
- **Minds handled being contradicted** (4628): Ffion turned on the overman
  with "is it five days old in your mouth?", and he held to his story.
- **Automatic promotion fired live.** The overman the player addressed on
  three beats became character 85. His drafted drive and taboo ("being caught
  in a lie or contradiction") fit what the story had shown of him.
- **The Room and the Dramaturge planned ahead.** They planted the deputies'
  cabin, scheduled Emrys Vaughan to arrive at the pit bottom (he did), and
  shaped the pressure ("the beat after should give it something physical to
  land on").

## Fixed during the run

- **c574c772: the inn opened onto sixteen places.** The opening's view listed
  sixteen openings from the inn: the chapel, the store, Plas Uchaf, eight
  terrace rows, and three galleries 400 ft down.
  - Cause 1: `merge_scene_with_diff` stood new rooms into its result as the
    diff's own records, so the orphan pass's repairs were written into the
    caller's diff.
  - Cause 2: the opening's placement floor previewed its diff on an empty
    scene, so every planned stub was an island tied to the first room listed.
  - Fix: the merge copies its diff, and the floor reads the scene the launch
    laid.
- **cc7fa91c: "the middle-aged square mr", "a handful of mrs and potmen".** A
  naming-profile post title ("Mr") was read as the noun. Now a title in the
  formal name's address slot is an address, never a noun. 13 of 638 play nouns
  change, all this story's; 0 of 146 in the owner's db.
- **08efc63b: one landlord, presented twice.** The landlord was shown as
  himself and still counted in his inn's crowd ("a handful of other
  landlords"). A body bound to a scene entity is no longer ground.

## Open findings, by class (turn ids are chat 167's)

1. **The player's declared speech and intent are not held.**
   - 4631: both quoted lines were dropped. The interpret coverage check listed
     them "uncovered", judged them "a paraphrase or a negative, most likely --
     not repaired", and Ffion answered the silence.
   - 4622: the player was moved with no walk declared.
   - 4628: the player's lines were retargeted to another person.
   - 4630: her line's target was written as the handle "character:84".
     FIXED in the fix wave: `normalize_causal_ledger` writes every identity
     handle as the name it stands for, and the one handle-only reader (which
     cast members a line addresses) reads names too.
   - 4617, 4627: the addressee was resolved to a different body than the one in
     view who had just spoken.

   Cause of 4617, 4627 and 4628 (fix-wave investigation): the player picks
   people out by what her view showed her, and the interpretation bound her
   words against the all-knowing world index, which said nothing of what
   she perceived or who had just spoken to her. The same class appeared at
   chat 165 turn 4582. FIXED (the owner's ruling, "give it her view, plus a
   re-ask"): the interpretation is handed `player_knows_as` and `last_lines`;
   one card clause in both packs says a person her input points at without
   naming them is the one her view showed her that way; and an account
   naming somebody no player perceived and no input named is asked again
   once, only where someone perceived is there to mean instead. Measured
   over the 105 stored play interpretations, it asks again on 4: three were
   these wrong bindings, and one named a man as scenery. Two repairs to the
   index went with it: a charter body the scene stands keeps its look and is
   listed once, and a thing placed under its own name is not a body.
2. **A conveyance worked by another does not carry those aboard** (4629). The
   shaft cage is no vessel. Both floors kept the player 400 ft down even after
   the encoder wrote the joint ascent:
   - "a walk is its owner's ... moved by another's declaration";
   - wave 1's D1 follow rule, "the place declared stands".

   The page took her up, and Ffion's whispered confession reached no view. It
   reproduced on reroll and was only cured by editing the input to declare
   the ride. Cause (fix-wave investigation): the decision model answered
   yes to "enter or leave a thing that has an inside" (0.94) and no to the
   things channel (0.23), and a part shipped only with its channel, so the
   encoder never saw that boarding is a walk into the thing's inside; every
   floor then rightly refused the ride written as the operator moving her.
   FIXED (the owner's ruling): a part that decides where a body is
   (`director_prose.BODY_PLACING_PARTS`: inside, transit, interior) brings
   its channel.
3. **World facts the Room holds do not reach the locals who would know them.**
   - 4619: Ffion named the dead wrongly, and one of them is a living banksman
     who later stood in the street.
   - 4620: "Mr Prothero signed it" against the Room's Emrys Vaughan.
   - 4626: she invented a deputy, "Tomos Rhiorig", and the Room then adopted
     him beside its own planned deputy.
   - Emrys Vaughan spoke on screen, yet his plan still reads unrendered, so the
     planned-person promotion bar can never count him.

   Cause (fix-wave investigation): every fact sat in a plan-tier store --
   package truths, plan roles, the place's history, the Room's own
   conversation -- that reached no mind. A truth's `known_by` was validated
   and never read; the launch could not file lore; and the deputy, placed by
   a crowd's dispersal under his name alone, had no record for the binder to
   bind, so a need was filed for him and the Room planned him again. FIXED
   (the owner's ruling, "truths reach the minds named"): every landed,
   unsuperseded truth reaches the minds its `known_by` names from the next
   turn, as something they already knew, over an older card
   (`plot_packages.truths_known_by`, `private_knowledge_for`); the Room's
   card names the three ways a fact is held (common lore, `known_by`,
   evidence), and the launch may `file_lore`; a planned body placed by name
   alone stands up as its plan's record
   (`director_floors._stand_up_plans_placed_by_name`), and no need is filed
   for a name the Room planned.
4. **The narrator originates or drops lines.**
   - 4617: it rendered a line nobody said.
   - 4618: a delivered background line never reached the page.
   - 4629: the first reroll's confession was placed after the ascent and given
     to the wind.
5. **An aim written as a phrase.**
   - 4623: `pointed_at: "Gallery Nine timbering"` resolves to nothing, so the
     beam through the brattice admitted nothing.
   - 4625: the phrase became a presence the background stage picked.
   - 4631: it became an unearned identity in a mind's view. The composer
     tripwire caught it.

   Cause (fix-wave investigation): the phrase was the Writers' Room's
   planned THING, and four readers took it for somebody. The interpret's
   identity index and the world index's figures listed it, so the beat aimed
   at it as a body. The encoder minted it at 4624 under the plan's exact name
   and look but no kind, so the binding floor searched the people and bound
   it to nothing. The presence harvest filed the placed kindless record a
   person, and the speech verdict read "no kind" as "person". The same
   harvest judged the beat's patch before the merged record, so the gate
   post lamp (a patch of name and state over `kind: lamp, portable`) was
   filed a presence at 4626. FIXED: a planned thing is listed to be
   rendered, never as an identity or a figure; a mint that names one and
   does not say it is somebody binds to it; the scene commit settles a bound
   thing's plan (before, only a person's render ever settled one); the
   harvest judges the merged record and files only somebody; and a record
   of no kind is undecided, voiced only by the Director's routing.
6. **An aborted beat** (4630). GLM 5.3 ran away ("Degenerate model output:
   repeating 26-character phrase"). That is classed a provider error, and D5's
   fresh attempt never follows one. FIXED in the fix wave: a runaway is kept
   apart from an outage, leaves no draft to repair and earns the one fresh
   ask, sent once (`llm_quality` `runaway`,
   `RetryConfig.degenerate_retries`); the transport logs every attempt it
   killed, and re-asks a runaway without a rate-limit backoff.
7. **Rendering.**
   - Hair without its noun: "slow landlord, with red". 69 of 228 hair entries
     are one word, and most phrases also lack the noun.
   - Adjective soup in full-sight labels, and a missing article.
   - A crowd pluralising a count of one.
   - Terrace siblings left as "Rhes Isaf 2" to "9": the grammar gave plain
     names, so there was no frame to deal from.
   - Card text verbatim on the page (4618, 4620).
   - Ffion's counting habit on 6 of 16 pages.
8. **Light and sound.**
   - 4623: "You are in a glare of light" 400 ft down, credited partly to "the
     open side, and the open doorway".
   - 4624: a voice in the same gallery reached the player as fragments.
9. **Speed.**
   - 4617: one narrator call took 72 s.
   - At launch, two DeepSeek JSON-mode answers were held 30 s each before JSON
     mode was dropped for the process (the turn-speed lane's owner question 4).

## Fix-wave replays (2026-10-10)

Each beat was replayed on its own copy of the scratch database, branched at
the beat before, with the recorded input submitted through the app as in
play (OpenRouter, the run's routing). 4629 used the ORIGINAL input,
reconstructed from that beat's first account and the run log, because the
stored one is the edit that declared the ride.

- **4620 (the truth beats the card): passed.** Ffion's mind was handed the
  Room's truth that the deputy, Emrys Vaughan, signed the report, beside her
  card's line saying Prothero did, and she answered "Emrys Vaughan's name is
  on it. The deputy." The original beat named Prothero.
- **4627 (her view binds her words): passed.** The account bound "the man on
  the rails ... you'll be the overman" to Gwenafryn Abogwyn, the man her view
  had shown as the overman; the original bound it to Prysenlas, who had walked
  in unseen. No re-ask was needed. His reply still reached her as fragments:
  the scene holds him at the pit bottom, a move no beat declared between 4626
  and 4627 (the investigation's separate finding, still open).
- **4629 (the ride): channel fixed, class still open.** Stepping into the cage
  brought its channels (`brought: contact_ops__interior, entities__inside`),
  and page and state now agree -- both women at the pit bottom as the cage
  starts to rise, the confession no longer lost to a contradiction. But the
  encoder wrote her boarding as a pose ("inside", relative to the landing)
  and minted the cage a vehicle in transit with no interior, so the arrival
  will not carry her. The open question is the owner's: a stronger encoder
  rule, or a floor that reads a body posed inside a vehicle as aboard it.
  The re-ask fired once here, on Emrys Vaughan named as scenery at the
  landing -- the measured scenery case, costing one account.
- **Found by the 4629 replay, fixed after it:** a planned body placed by name
  alone BEFORE the rule existed (Emrys, placed at 4628) was skipped by every
  floor -- the binder reads records, the lease counts a placed body as held,
  and the new floor read only the beat's own placements. The floor now reads
  the merged scene, so such a story heals on its next beat (checked on the
  replayed state: he stands up as his plan's record, nobody else does). And
  the needs drain, which retries open person-needs by enrolment, now CLOSES a
  need whose name a plan answers (`plan_answering`): retried, the stale need
  filed at 4618 would have enrolled the planned deputy as a second body
  wherever a seat was open.

The working log, with every turn's evidence, is the scratch `findings.md` that
the session's report points to.
