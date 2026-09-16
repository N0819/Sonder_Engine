# Causal prose stress audit — 2026-09-15

## Result

The six final fresh model captures preserve **89/89 expected event propositions
and 19/19 spoken lines**, producing **90 chronological event rows**. One
simultaneous checklist group becomes two rows. The private item registry stays
stable, and specialists receive no private item or chronology IDs.

**World execution is still incomplete.** The workshop log describes lid changes
and a set-down that the resulting world does not execute. The garment case
preserves its jacket identity and re-wear correctly, but leaves an intermediate
ownership gap and an incomplete final badge relationship. Door chronology,
braided transfers, attempted actions and the two-cup sequence pass their targeted
physical checks. Event coverage is therefore not an end-to-end success score.

[Structured evidence](data/causal_stress_2026_09_15.json) contains the prose,
predetermined checklists, grounded scenes, actual provider outputs, specialist
inputs, compiled programs, chronological worlds, observer views, warnings and
call metadata. [Readable event logs](CAUSAL_STRESS_2026_09_15_EVENTS.md) expose the
final sequences. The [baseline bundle](data/causal_stress_baseline_2026_09_15.json)
is historical evidence; its superseded failures are not the final findings.

## Method and limits

- Six newly authored scenes mix dialogue, pronouns, repeated transformations,
  similar objects, handovers, several categories in one span, temporary door
  states, unsuccessful attempts, negation and quoted recollection. Their finite
  checklists were written before testing. Static descriptions, denied actions,
  remembered commands and future train arrivals are not executed events.
- The harness runs real `director_interpret`, specialist fanout and
  `director_resolve` in isolated synthetic stories, then scene composition and
  deterministic onset/outcome perception. It does not generate autonomous
  character turns, narrate, or commit to production stories.
- The selected captures use OpenRouter `z-ai/glm-5.2`: **34 recorded provider
  calls**. The table counts those captures only, not every retry or earlier run
  in this investigation. Earlier NanoGPT stalls are availability observations,
  not semantic passes.
- An early fixture lacked empty attire rows used by this engine as evidence that
  otherwise unclothed actors are bodies. Every selected fresh capture uses the
  corrected fixture from the start. Fixture-only carrier failures are excluded.
- Coverage was checked against actual ledger spans, patches, intermediate worlds
  and observer views. Quotation glyphs and outer attribution punctuation may
  differ; spoken words and speakers must survive.
- All six selected captures were subsequently replayed with **zero provider
  calls** against the final code. Entity, position, station, pose, contact,
  containment, attire and substance state, plus the complete event log, matched
  their captures. This establishes stable execution of those replies, not their
  semantic correctness.
- The same six cases informed contract revisions. This is regression stress
  evidence, not an independent holdout success rate. A final prompt clarification
  of authority modes and raw-input handling, and restoration of missing spatial
  and social standing context, were checked locally after capture; they have
  not been remeasured with fresh model calls.

## Final selected captures

| Case | Propositions | Spoken lines | Log rows | Recorded calls | Elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `workshop_coreference` | 16/16 | 3/3 | 16 | 5 | 306.5 |
| `door_and_speech_timeline` | 13/13 | 4/4 | 13 | 4 | 50.2 |
| `garment_badge_and_water` | 17/17 | 3/3 | 17 | 9 | 449.0 |
| `two_object_braided_transfer` | 14/14 | 2/2 | 15 | 5 | 106.9 |
| `attempt_negation_and_embedded_quote` | 14/14 | 3/3 | 14 | 5 | 81.2 |
| `two_similar_cups_ambiguous_pronoun` | 15/15 | 4/4 | 15 | 6 | 60.6 |
| **Total** | **89/89** | **19/19** | **90** | **34** | |

These are six fresh captures selected after the relevant fixes, not a mixture
of fresh runs and replays. Long workshop/garment elapsed times include provider
latency and repair/forwarding; they are not deterministic engine execution time.

### Workshop: unresolved lid and release omissions

The log preserves all four open/close events, all transfers and all dialogue.
The Director routes the lid spans 2, 6, 13 and 15 to contact work. That hand says
`already_true` without requesting the object-state owner. No hatch changes are
written for those spans. An incidental `hatch: open` during needle extraction
at span 4 is the only hatch write: the tin is still closed at opening 2 and
never closes at 6 or 15. Its final state is incorrectly open.

At set-down 10, contact ends Sera's grip and spatial places the tin at the stool,
but neither requests the missing inventory operation. The tin remains held by
Sera despite its stool station. Needle extraction, set-down, pickup and stowing
in the pouch execute, the extended palm has a pose, and final contacts are
empty. The earlier persistent-grip defect is absent; the surviving failures
are raw model omissions and incorrect local completion claims. The complete log
alone would conceal them.

### Door: chronology reaches perception

The door opens at 1, closes at 3, opens at 7 and closes at 11. Mara moves
through office → archive → office → corridor → office and sits at 12. Oren
hears the first open-route line and the corridor line, but not the archive
sentence or the final closed-door whisper. The seated pose is present. A spoken
request does not fetch the ledger, and static lamp/ledger state remains intact.
An initially mis-sized spatial result was repaired; no failed specialist remains
in the selected result.

### Garment: one identity, improved transfers, two remaining gaps

Exactly one original `jacket` exists at every span. The jacket transfers to Rin,
is released onto the rail, is picked up again at 12, returns to Nia, and becomes
worn at 14. Re-wear ends Nia's free-object grip. Badge pickup at 15 is now an
actual held/gripped state, and earlier handovers no longer lose their new holder
through a competing containment clear.

Two incomplete relationships remain:

- Removing the jacket at 4 creates a Nia–jacket grip but leaves no held
  containment. The completion diagnostic explicitly reports that the requested
  inventory owner did not settle this span.
- Clipping the badge at 16 returns a transfer to `jacket` with relation
  `mounted`, sets its attachment description and adds a badge-clip/jacket-chest
  contact. Final containment contains only the jacket worn by Nia; it does not
  contain a badge-to-jacket relationship. The badge's old tray station remains.
  The action is represented, but its persistent placement is incomplete. A
  separate zero-call diagnostic copied this final scene, added an adjacent
  corridor and applied only a typed room move for Nia. Nia and her worn jacket
  moved; the badge stayed in the bay at the tray and its clip contact vanished.
  This confirms the missing attachment binding for this captured state. The
  extra move is outside the scored prose and changes none of the event totals.
  Its [before/after evidence](data/causal_stress_garment_followup_2026_09_15.json)
  is preserved separately.

The water operation is a valid source-linked partial transfer, with
`source_substance_id` and `portion: trace`. An unknown source amount remains
unknown. A locally wet cuff does not by itself invalidate the jacket's earlier
whole-garment condition text.

### Braided transfer: all object transitions execute

The bundle moves Asha → Bram → fountain → Asha → bench. The case moves
Asha → table → Asha → Bram → fountain; it opens and closes around the key's
extraction. The key moves from the case to Asha's hand and into her worn pouch.
Every required set-down releases its holder, every temporary grip ends, and
final contacts are empty. The bundle, case and key remain distinct. One
simultaneous checklist proposition is represented by two chronological rows.

### Attempt and embedded quote: failure stays failure

The key has a typed key-to-keyhole relationship during insertion and the failed
turn; withdrawal removes it before set-down ends the hand grip. The mug is
picked up, carried into the pantry and released on its shelf. Leah returns and
sits; Pavel's raised hands are represented. The door remains locked and intact,
and the red book stays in the cellar. No denied kick, successful unlock,
remembered imperative or book retrieval is invented. The enclosing spoken
recollection survives with its embedded quote intact.

Some earlier station metadata remains during the key insertion. The required
contact topology exists; this capture does not prove a general spatial
consistency guarantee for every retained hint.

### Similar cups: distinct objects and actual releases

The ambiguous pronoun explicitly resolves to the striped cup, an allowed
interpretation in the checklist. Only that cup moves. Both cups retain separate
identities through every pickup and set-down; the dotted pickup at 13 is an
actual held/gripped state before release at 14. Final containment and contacts
are empty, with striped cup at counter and dotted cup at sill. Their final
support poses agree with those placements.

All four lines retain their speakers. Social explicitly declines to convert
“No train until noon” into an objective world fact: the speech proves what was
said, not that the timetable assertion is true. This refusal is an appropriate
diagnostic, not an omitted physical event.

## Repairs established in the worktree

1. **Private identity and actual world binding.** Validate positive item IDs,
   parallel list widths, duplicate IDs within a row and stable scene-wide
   ID-to-label mappings. Distinct objects may share a readable name. Specialists
   receive public names and scoped world matches; positional result correlation
   restores private handles without exposing them to the model.
2. **Chronological execution and perception.** Compose complementary transforms
   for a span, execute ordered spans through domain appliers, preserve repeated
   acts and quotes, and retain before/after worlds. Asserted onset events enter
   the final log without being executed again during resolve. Event delivery
   uses the relevant chronological world and actual speaker.
3. **Usable outputs and local completion.** Require current wire envelopes,
   preserve the scoped sheet during repair and report malformed/dropped work.
   `encoded`/`already_true` settle only a hand's own part. `required_channels`
   can request complementary owners independently of that status; per-row
   `assigned_hands` is distinct from batch-wide `co_hands`.
4. **Chronological completion requests.** Forwarded work receives its requested
   channels and prior public work. Inserting earlier work reevaluates the
   receiving hand's later chronological suffix, replacing stale answers: a new
   earlier set-down can invalidate a later `already_true` pickup. Known hand
   names supplied as referrals remain compatible; unknown names are reported.
5. **Typed ownership and garment identity.** Inventory transfers into portable
   containers establish containment. Stations do not imply release or grip
   endings. Ordinary positioned objects are not offered as bodies. Exact,
   uniquely owned garment matches reuse the original entity through removal and
   re-wear; ambiguous identical garments are not silently merged.
6. **Authority of speech.** A spoken assertion is not automatically a persistent
   world fact, and an unsupported fact has no invented alternative owner.
7. **Standing context follows its owner.** Spatial receives current following,
   location, weather and time labels. Social receives pending obligations and
   public social standing at resolve. These fields had been built for the
   retired author payload but did not all reach the current specialists.

These repairs improve the mechanism and expose unfinished work. They do not
prove that a model will always assign every needed owner or reject its own
incorrect `already_true` claim, as the workshop capture demonstrates.

## Additional migration gap: obligation writes

The current causal wire contract cannot open, discharge or refuse legacy
`pending_obligations`. Its commit function still reads top-level
`director_resolve.obligations`, but neither the minimal Director output nor any
specialist channel can write that field. Restoring the social hand's standing
context does not restore this lifecycle. A complete migration needs explicit
ownership and handling of asserted onset versus later resolve events; it must
not turn an overdue flag into an invented discharge. This remains unresolved
and is outside the six physical-scene scores above.

## Automated validation

The original baseline comparison established **53 existing failing tests**.
An earlier full run recorded **15,190 passed, 78 failed and 3 skipped**. Of its
25 additional failures, 24 passed on isolated rerun; the remaining obsolete
prompt-literal assertion was corrected and passed in a focused 90-test run.
That explains the stale count without making the earlier full run green.

The latest full run recorded **15,235 passed, 76 failed and 3 skipped** in
634.04 seconds. Of those 76 failures, 53 match the original baseline. All **23
additional failures passed on isolated rerun** after generated catalog/Japanese
entry updates and stale identity, speech and world-fact assertions were
corrected. **`make structure` passed.** There is still no clean full-suite
result; isolated follow-up success is reported separately.

The final focused contract run passed **225 tests**, covering completion
requests, patch validation, speech facts, span order, schemas and prompt cards.
After restoring spatial standing context, **305 tests passed** across its
payload regressions, completion contract and orchestration. The room and
parallel-speech failures were checked against current causal inputs before
their obsolete payload-key assertions were updated; both behaviors remain
covered. These focused sets overlap and are not additive.
The final combined run after both context fixes passed **327 tests** across
16 relevant files. All six model captures were replayed again after those fixes
with identical checked world fields and event logs, and zero provider calls.

Validation logs: `/tmp/sonder-causal-full-final.log`,
`/tmp/sonder-causal-rerun-final.log`, `/tmp/sonder-causal-full-stable.log` and
`/tmp/sonder-causal-stable-rerun.log` and
`/tmp/sonder-causal-final-focused.log`. Final replay roots are
`/tmp/sonder-causal-final-replay-v3-core`, `-braid`, `-attempt` and `-door`.
The separate garment movement diagnostic is
`/tmp/sonder-causal-garment-followup-probe.json`.

## Conclusion

The recompiler now retains the full audited event sequence, stable object
correlation and chronological evidence for perception. Four scenes satisfy
their targeted world checks; two still expose missing or inconsistent physical
relationships. The next reliability work must measure those relationships and
completion claims directly. Complete event prose is necessary evidence, but it
cannot substitute for the transforms that make those events true in the world.
