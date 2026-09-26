# Unbuilt work — Characters, memory, and psychology

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-5"></a>

### 1.5 A character cannot revise a bearing they learned wrong

`disproven` fires when a doorway fails to exist. Nothing fires when a doorway
exists but the character remembers the wrong HEADING for it. After a bearing
corruption was fixed in the world, one character kept oscillating in exactly
the pockets whose bearings had been wrong while he learned them.

**Narrowed 2026-08-19, and it is a smaller entry than it read.** The place
graph is not the store holding the stale heading: `_confirm` overwrites
`rec["bearing"]` on every re-standing (`persist/commit_place_graph.py`), so a
walked doorway self-corrects at the next visit. What has no retraction path is
the LEARNED ASSOCIATION — `mind/psychology_runtime.py` weakens a belief only
when something disputes it, and nothing ever disputes a heading. Fix it there
or nowhere.

Related, and wider: a character can revise a belief about the world and has
almost no mechanism for revising a belief about themselves. Project
displacement is the only one.

<a id="unbuilt-1-27"></a>

### 1.27 Residuals from the speech-channel investigation

Found in the same pass. The attire-blob accumulation is now fixed (`persist/commit.py`
rebuilds `state` from `attire.flat_state` unconditionally and keeps only notes
`attire.is_derived_state_note` says were authored; `tests/
test_attire_commit_stored_shape.py`). The rest are open.

- Two `remember_lines` were dropped whole across 12 turns because the character
  cited event ids that do not exist. The guard is right to drop an ungrounded
  citation; the cost is that the line the character chose to keep is discarded
  rather than salvaged with its citation stripped. Given Phase 4a measured
  these as the highest-yield rows in the bank (3.3x baseline retrieval), losing
  one to a malformed reference is expensive.

*(Two bullets left this entry on 2026-08-19: the `manner`/`contained` bullet was
verbatim §1.28's second, and the intent-stall bullet is built —
`mind/affect.py`'s `_INTENT_STALL_AFTER = 2` sets `status="dormant"` once a goal
sits barren at its ceiling.)*

<a id="unbuilt-1-29"></a>

### 1.29 Parallel reaction chains, and the isolated wave that is shelved for them

Written, tested, switched off 2026-08-04. `agents.loops._perceptually_isolated`
and `_isolated_wave` exist and are covered by
`tests/test_interaction_first_wave.py`; `parallel_isolated_reactors` is
`False` in `DEFAULT_INTERACTION_CONFIG`.

**The rule is right.** The beat now opens with ONE character so causality can
build (§ alpha 7.2), and the one honest exception is a reactor who could not
possibly perceive the opener -- separate room, no sight, nothing audible.
Sequencing those two claims an order no reader could detect, and running them
in one instant is what offscreen simulation needs.

**Why it is off.** Every reactor in a beat today is somebody the player can
hear, so the branch would never fire on a real story and its first live run
would be its first exercise. It is switched off until there is offscreen life
to run through it.

**The loose end whoever turns it on inherits.** Isolation is tested at `loud`,
not at `shout`. The engine's own model says a shout carries a FRAGMENT between
far separated rooms, so testing at `shout` makes nothing anywhere isolated and
the branch dead; testing at `loud` means a character who actually shouts can
reach somebody the wave already treated as unreachable. The honest fix is
re-running an isolated reactor when a shout was in fact declared, which needs
the declaration first and so needs the loop restructured.

**Where this is going.** `_isolated_wave` grows greedily and checks each
candidate against every member already in the wave, because two characters
together in a far room can hear each other and belong in sequence with one
another even though both are isolated from the opener. That is already the
shape of the real feature: the cast partitions into perceptual components, and
each component is its own **reaction chain** -- sequential within itself,
genuinely parallel with the others. The current code produces the partition's
first slice; the generalisation is to run every component as a chain rather
than only admitting the isolated ones to one opening wave.

**Interruption is solved, declaratively.** Landed 2026-08-04 -- `interrupts`
on a speech or action element, resolved against who actually spoke and who
could actually hear them, with `agents.common.cut_short_speech` breaking the
interrupted line at a breath point. See `CHANGELOG.md` and
`tests/test_interruption.py`. It needed no change to ordering, which was the
point: a character later in the chain has already heard the line they want to
cut off.

Still open there: the Director does not yet adjudicate an interrupted ACTION.
The element is marked `interrupted: true` and the Director resolves it like any
other attempt, so a reach that got grabbed and a reach that did not are handed
over identically -- the flag is written and nothing reads it. Giving it force
is a Director rule about which of two colliding attempts survives intact, and
it is the natural companion to `commitment: "contestable"`.

<a id="unbuilt-1-37"></a>

### 1.37 The aversive half of the stress model is live and unobserved

**Landed 2026-08-19.** `resolve_stress` weights `threat` at 0.55 and derived it
from `appraisal["goal_impacts"]`; `affect.appraise` returns the normalised list
under `"impacts"` and writes no key by that name, so the loop never ran and
threat was 0.0 on every beat of every story. Measured before: 33 characters
carried a resolved stress block, `overloaded` had fired ZERO times ever, and
strain never reached half its threshold. The channel is now an explicit
keyword-only argument (`goal_impacts=`), so the next omission is a TypeError
rather than a zero.

**It is a behavioural change and nobody has watched it yet.** Every character
in every story can now accumulate strain, and `overloaded` — strain-only, and
never once fired — can fire. The watched rows are `overloaded` and `load`: if
they now fire constantly the weights are wrong in the other direction, and the
0.55 was set against a term that was always zero, so it has never actually been
calibrated against anything. Re-measure after a run of real beats before
trusting the number.

<a id="unbuilt-1-41"></a>

### 1.41 Surface-affect habituation ships default-off; flipping it is a decision this entry exists to force

The saturation defect is measured and the fix is landed and validated
offline (`affect_habituation`, CHANGELOG Unreleased; replay evidence in
`tools/affect_replay.py` against chat 71's checkpoints), but the setting
defaults to the shipped behaviour, so **every live story still has the
defect until somebody flips it**: a surface at the ceiling stays there, and
a climax cannot out-score its own build-up. What the flip should wait for is
one live story played with it on and read for feel — the replay proves the
trajectory shape (plateau ~0.83, releases 0.92–0.94 on chat 71; sub-0.80
conduct moving a mean 0.012), but felt tone in prose is the thing no
counter measures. Two calibration facts for whoever tunes it next: the
compression must stay top-slice (a uniform gain strong enough to help chat
71 cost the warm long story chat 38 a story-wide ~0.1 valence shift —
medicine landing on health), and accumulation must read the STIMULUS (the
uncompressed target), not the body's own dampened surface, which stalls at
a feedback fixed point (measured: s froze at 0.40 exactly). Residuals
accepted knowingly: a spike that arrives mid-plateau on the same axis is
compressed like the plateau (only the hedonic release pierces — shock fires
chronically there and model novelty is noise); and a fast build that pins
within ~6 beats starts paying before its plateau formally begins. Both are
visible in the replay table; neither has a decidable discriminator in
stored data today.

Also recorded here from the same investigation, judged fine as they stand:
Elyra's climax minting no `awareness` condition while Hinami's did is the
Director describing two different bodies (one collapsed, one did not), and
the moment's structural carriage for Elyra exists regardless — her hedonic
charge hit 1.0, `released` fired, and the charge zeroed next beat, which is
the drive-feed loop working; a `drive_shift` there would have been WRONG
(a peak inside one's own drive confirms it — the hard drive lesson is about
strain never moving a drive, not success moving it).

<a id="unbuilt-1-56"></a>

### 1.56 The project tier's occasion now arrives, and is declined

v4 made the review beat reachable (`Design.md`'s project row has the diagnosis:
one condition written twice, so the only moment a first project could be
adopted was conditional on already having one). Re-measured read-only against
the live `engine.db` on 2026-08-18, **329 turns after that fix landed**:

| | |
|---|---|
| `chat_chars` rows | 100 |
| banks carrying `interior.projects` / `former_projects` at all | 32 |
| banks carrying a `project_review` | **6** |
| banks holding a project | **0** |
| banks holding a former project | **0** |

So the fix worked and the tier still has never been used. The failure has
MOVED, not closed: it was "the occasion cannot occur", and it is now "the
occasion occurs and the character does not take it". Those want different
evidence. The candidates, none of them measured yet:

- the adoption deliberation refuses everything — it is built to refuse a task
  wearing the word, and may be refusing legitimate candidates too;
- the review beat's payload reaches the model but loses to a drive-serving want
  in the same beat, which is the exact mechanism that made the shrine lose nine
  beats running at intention weight 0.8 against 1.0;
- `project_review` fires on beats where nothing is a plausible life's work.

Do not change a gate on this until one of the three is measured. The v4 lesson
is that the previous gate change was correct and did not produce an adoption,
and a second blind change would make the two indistinguishable.

**A long phase-chain arc, measured whole (2026-08-25).** The clearest single
case the corpus holds, filed here because it is evidence for the three
candidates above rather than a fourth defect. Chat 88, char 72, 67 turns: six
sequential dynamic intentions `i1`-`i6`, each one phase of a single continuing
engagement, every one of them carrying `serves_drive: ""`. `interior.projects`
and `former_projects` are `[]` for the entire arc, and the two authored
standing intentions sit at progress 0.0 throughout. Task closings — the beats
`project_boundary` opens its review on — occurred at turns 6, 19, 22, 33, 39
and 46, and produced no adoption. The engagement itself is a project wearing a
chain of intention clothes: durable but not eternal, able to name a place,
and repeatedly re-authored as a fresh completable goal because that is the only
tier the mind could reach for.

This is deliberately NOT coded around. `docs/design/DESIGN_LONG_TERM_GOALS.md`
and `CLAUDE.md` are explicit that projects form dynamically through
`project_ops` under the adoption deliberation and that seeding is not the
authoring surface, so the candidate fix is on the invitation/adoption surface —
why six successive task-closed reviews produced no adopt — not a seeding
change. The world-closed intention floor
(`affect.settle_intent_world_anchors`, landed 2026-08-25, `Design.md`'s
conformance row) closes the STUCK TAIL of such a chain — chat 88's `i6` was
`active` for thirteen turns after the world left the station it named — but it
does not create the tier that would have carried the arc, and a closed tail
just returns the mind to forming the seventh phase-shaped intention.

**Absorbs §1.23(d) and §7's "why 3 of 31" bullet (2026-08-19) — one zero written
three times.** Do not confuse the two denominators: `tools/fire_rates.py` reports
`has ever held a project 9.68% (3/31)` across characters with any project
history, while the table above counts LIVE banks and gets 0. Both say the tier
is essentially unentered; only the second is the recent engine. The measurement
that would separate the three candidates is filed at
[`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md) §1 —
it is the smallest number in the corpus with the largest documented effect
(`CLAUDE.md` records projects as what made NPCs pass the maze without altering
their drives), so measure it before enriching anything in the world layer.

<a id="unbuilt-1-76"></a>

### 1.76 `recall_confidence` measures distribution shape, and absence has the same shape as presence

Measured 2026-08-19 against LongMemEval (MIT), the first retrieval instrument
whose questions nobody on this project wrote
([`experiments/AUDIT_MEMORY.md`](experiments/AUDIT_MEMORY.md) asked for one;
`tools/longmemeval_to_bank.py` builds it). 10,960 rows in one bank, 470
positive probes and **30 negatives whose answers are absent by construction**
-- twice the hand-authored negative set that
[`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md) §5
could offer, and independent of this engine.

Two results, and the second one is the entry.

**The threshold does not survive scale.** Holding the query AND its target rows
fixed and growing only the distractor mass (so nothing about the question or
its answer changes):

| rows | hit rate | median lift | min lift on a hit | negative median |
|---|---|---|---|---|
| 500 | 100% | 3.708 | 3.098 | 2.654 |
| 1,000 | 100% | 4.702 | 3.852 | 3.379 |
| 2,500 | 100% | 5.769 | 4.597 | 4.389 |
| 5,000 | 100% | 6.204 | 4.943 | 5.127 |
| 10,960 | 100% | 7.086 | 5.526 | 5.934 |

The same question with the same answer scores nearly twice the lift purely
because the bank grew. `_RECALL_ABSTAIN_LIFT = 1.7` was calibrated where lifts
ran 1.724-2.3, on banks of at most 657 rows. At 500 rows on this corpus even
the NEGATIVES score 2.654. A z-score against the bank's own distribution is
scale-dependent by construction, so an absolute sigma threshold cannot hold
across bank sizes -- and a thousand-turn story is the case the signal was
built for.

**And recalibrating cannot fix it, because the negatives drift at the same
rate.** Positives climb 1.9x across the sweep, negatives 2.2x. The gap between
"the answer is in this bank" and "the answer does not exist anywhere" stays at
roughly ONE SIGMA at every scale and never widens. Over the full 500-probe run
the two populations overlap almost entirely: positives median 6.197 (min
3.555), negatives median 5.934 (min 4.249). True abstention on the shipped
threshold: **0 of 30**. False abstention: 0 of 399, which is only reassuring
until you notice nothing fires at all.

The reason is structural rather than numerical. A query whose answer is absent
still retrieves topically related rows and still produces a peaked distribution
relative to the bank mean. Presence and absence have the SAME SHAPE; only the
CONTENT of the top rows differs, and a statistic over scores cannot read
content. MEMORY_IMPROVEMENTS.md §5 reached the edge of this from the other
side -- "sharper teeth need row-level evidence... not a better threshold" -- and
this is the measurement that closes it.

**Its one production reader is gone, 2026-08-20.** It annotated the character
payload with `nothing_comes_back_clearly`; that call is removed, which also
removes a second full bank scan per character per beat. Nothing replaced it,
so **the engine currently has no abstention signal at all** -- a mind is never
told its own recall came back empty. That is a deliberate absence rather than
an oversight: the statistic fired 0 of 30 times, so removing it took away
nothing that ever happened.

The row-level replacement was attempted the same day and is unmeasured. A
reading pass over the top-k (`mind/memory_judge.review_recall`) answers the
question properly, but the arm that would price it -- 470 positives and 30
negatives -- was abandoned at 3 of 90 after two invalid runs and roughly two
minutes per call. **The number that matters is FALSE abstention**: a positive
probe the reviewer calls empty is a mind told it does not remember something
it does, which would be strictly worse than an inert statistic. Until that is
measured, do not wire it.

What survives: the signal fails open, and it has never falsely suppressed a
real recall in any measurement. So it is inert rather than harmful, and there
is no urgency to remove it. What it must not do is be trusted, cited as an
abstention mechanism, or extended to another lane. The honest replacements are
row-level (a cross-encoder or an entailment check over the top-k, which reads
what the rows SAY), and the honest interim is to stop calling this an
abstention floor.

Related: 2.16 records the floor as the surviving half of that entry and should
be read with this beside it; 2.20 notes the separate reason the signal cannot
fire early in a story (`_RECALL_CONFIDENCE_MIN_BANK = 40`, which the median
bank does not reach until turn 10).

<a id="unbuilt-1-85"></a>

### 1.85 A memory's age off a per-beat estimate, not a per-beat record

**Found:** 2026-08-26, landing `memories.encoded_at_seconds`.

Every memory now carries the simulation-clock reading it was written at, and
`mind/memory_time.py` names the interval off that reading alone -- so a single
delivered memory is exact and needs nothing here. A SUMMARY WINDOW is the gap:
it names a range of turn indices and carries no reading of its own, so the ends
have to be resolved to fiction time by some other route.

Today `window_clock_readings` resolves them by reading the stored stamps back
off the memories that window actually consolidated. Those are real recorded
values, not an estimate, and they are right whenever the window minted this
character anything at all. Two cases they cannot answer: a window whose rows
have since been archived away, and a window that minted this character nothing
(the character was gated out, or simply silent, for the whole stretch). Both
fall back to the qualitative phrase, which is honest and slightly poorer.

The same gap has a second face: the v34 migration backfills existing rows at
`turn_idx * world.mechanics.UNCLAIMED_BEAT_SECONDS`. That constant is the rate
the live clock already charges a beat that claimed no duration, so backfilled
rows come out consistent with new ones by construction rather than by an
invented number -- but a story whose beats mostly DID declare durations has a
bank dated by a flat 10s/beat that its own clock never followed.

**What closes both:** one row per committed turn holding the reading that turn
ended at -- a per-turn clock history, written where `persist/commit_scene_state`
already stores `simulation_clock`, rolled back with the turn like any other
committed row. `window_clock_readings` is the named seam: its BODY changes and
nothing downstream does, because every caller already takes
`(opened_at, closed_at)` or a qualitative refusal. The backfill becomes
re-derivable for any chat whose history survives.

Not urgent: the fallback is a phrase rather than a wrong number, which is the
posture this whole change insists on. Worth doing when something wants to date
a window whose memories are gone -- long-bank archival is the likely trigger.

<a id="unbuilt-1-99g"></a>

### 1.99g Memories the player owns, and the one thing that must be true first

OWNER'S DESIGN 2026-08-28, deliberately DEFERRED: memories recorded for the
player that the narrator may raise unprompted. Explicitly not to be built now.
The instruction that matters is the second half -- develop what IS built so
that adding this later is not a serious recode.

WHY IT IS NOT FREE TODAY. `personas` is `(id, name, sheet, source,
resource_uid)` and `memories` keys on `char_id`. A persona owns no memory bank
and nothing anywhere writes one, which is why 1.99f's companion could be given
sixteen events of shared road with nowhere to put the player's half.

THE ONE THING THAT DECIDES WHETHER IT IS A RECODE: identity. Everything built
around the player from here addresses them by the persona's `resource_uid` --
the id that already survives archive, branch and clone -- and never by display
name. Get that right and a player memory bank is a NEW WRITER against an
existing key: `memories` gains rows under an identity the ledgers already
carry, and the retrieval, summary and narrator paths work unchanged because
they were never told the identity was special. Get it wrong and adding it means
retrofitting identity through every relationship edge, every charter ref and
every presence record, which is the recode.

Concretely, the rules for anything landed before this exists:
  * a relationship edge naming the player stores the persona uid, and the
    display name only as a rendering;
  * a charter body standing in for the player carries the uid in its refs the
    way `featured_resident_bindings` already carries `entity_id`;
  * no code may branch on "the player has no memories" -- it may only find the
    bank ABSENT and skip, so the same path fills when the bank exists;
  * nothing may key player history on the persona's row `id`, which is local
    to an install and remapped on import.

WHAT THE DEFERRAL COSTS, stated so the decision stays honest: until it exists
the player's own recall is the transcript, and a character asking "do you
remember what you told me last winter" cannot be adjudicated by the engine --
only answered by the human. That is tolerable and may even be right; it is
recorded here so that if it stops being tolerable, the reason is visible.

<a id="unbuilt-1-107"></a>

### 1.107 `generalization_tags` promises a mechanism that does not exist

`AssociationProfile.generalization_tags` (`story/character_schema.py:225`) is
normalized, editable (`static/js/components.js:745`), archived with the sheet,
and serialised to the character as prose inside `learned_associations`. What it
is NOT is a generaliser: nothing deterministic reads it, and
`psychology_runtime.apply_association_updates` moves `appraisal_bias`,
`response_tendency` and `strength` and never touches this one. So a tag an
author writes is a note to the model, and a tag the runtime could have LEARNED
never appears.

Kept rather than deleted, and the measurement is the reason: read-only on the
live database 2026-08-18, **all 78 authored associations carry tags, and 87 of
the 152 in the interior ledgers do**. Deleting the field discards authored work
in three quarters of the places it exists. The choice — build the generaliser,
or withdraw the promise the field's NAME makes — is an owner's, and either way
`static/js/components.js` is the other half of whichever answer wins. Audit
MIND-F16.

## 2. Roadmap

<a id="unbuilt-2-2"></a>

### 2.2 Make stance auditable

**Closes debt #2.** Move relationships out of the `world` KV blob into a
`relationship_events` table: one row per delta, with target, axis, magnitude,
trigger event id and turn. Keep the current graph as a derived projection,
exactly as `world_entities` is derived from the scene. Then make
`trigger_event_ids` mandatory and tighten the clamp toward the specified ±0.05.

Today `apply_relationship_updates` accepts `trigger_event_ids` but treats them as
optional, with explicit handling for "a routine trigger-less delta"; there is no
change log, only the current value plus a `salient_event` string. There is no way
to answer "why does she distrust him?" from the record. The founding design
specifies ~0.05 per ordinary interaction; the schema clamps at ±0.2.

(Corrected 2026-08-19: this entry previously read "Verified absent: no
`relationship_events` table exists". It does — `core/db.py:663`, with a
writer, a reader, archive, checkpoint and branch-remap support, its own test
file, and **341 live rows**. A register that states the opposite of the
schema is worse than one that says nothing.)

<a id="unbuilt-2-3"></a>

### 2.3 Teach the heuristic import to read `description`

**Closes debt #3.** No LLM required: fall back to `description` for
`self_model.summary` and voice notes when `personality` is empty, and warn
specifically when a heuristic import lands below a populated-field threshold.

The heuristic path derives psychology from the card's `personality` field, so a
v2 card that puts everything in `description` — common — yields a sparse first
pass. The opt-in v3 gap-filler mitigates sparse old cards but does not remove the
value of a better deterministic first pass.
`character_card_warnings` now fires on all ten surfaces that hand back a card
(`8ddcc1e`), so a heuristic import that lands sparse is reported wherever it
was made; what is still missing is the populated-field THRESHOLD that would
make "sparse" a warning of its own.

<a id="unbuilt-2-16"></a>

### 2.16 A summary window should be an INDEX over raw memory, not more prose

**Raised 2026-08-02; verdict recorded 2026-08-19/20.** The strong form below
— route retrieval through the winning window — was MEASURED AND REFUSED:
window-first routing scored 6–7/12 against flat retrieval's 10/12 on the live
corpus ([`experiments/AUDIT_MEMORY.md`](experiments/AUDIT_MEMORY.md) §3.6),
the compounding P(right window) × P(right row) is real, and RAPTOR's and
MemTree's own ablations independently agree (audit §4.3). Do not rebuild it
without evidence that beats all three. What survives of this entry:

- **The "nothing convincing" floor this entry said did not exist now does** —
  `memory_retrieval.recall_confidence`, a per-query NQC/WIG-shape signal
  against the bank's own score distribution, calibrated at zero measured
  false abstention across both corpus states
  ([`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md)
  §5). It annotates the passive lane (`nothing_comes_back_clearly`); it is
  deliberately NOT extended to the ponder lane (measured: it would falsely
  abstain on a diffuse pattern-over-session query whose answer was
  delivered).
- **Still live, with the audit's evidence behind them**: windows entering the
  same RRF fusion as first-class candidates (audit §4.3 item 1), and the
  window's deterministic `start/end_turn_idx` as a temporal BOOST when the
  query carries a temporal cue (item 2) — the index shape this entry wanted,
  without the routing it feared.

The original argument, kept for the record:

Today the earlier windows travel *beside* raw recall: two paragraphs added to a
payload that separately ranks sixteen raw memories. That is the supplemental
form -- cheapest, and measurement says it is not redundant (14% mean overlap
with what raw recall already surfaced). It is not the strong form.

The strong form uses a window's **turn range** rather than its prose:

```
what does this beat remind me of
        -> rank the windows            (which stretch of my life)
        -> take that window's turns    (an index, not a payload)
        -> rank raw memories INSIDE it (the actual episodes)
```

The summary stops being autobiography dumped into context and becomes an index
over eras; the raw rows stay the episodic evidence. A character then recalls the
way recall works -- find the period, then the moments in it -- instead of one
flat similarity sweep over everything they have ever known.

**Correction, 2026-08-19: the turn range is not missing.**
`memory_summaries.start_turn_idx` and `end_turn_idx` exist in `core/db.py` and
have since the table shipped. What is missing is the RETRIEVAL SHAPE above and
the prompt contract below, not the column.

**What it needs first.** The turn-range semantics are *emergent, not
contractual*. `memory_consolidate` says "merge the new batch into an updated
summary"; nothing in it promises a window describes its own range. It happens to
(3-16% carried text, measured), because the same prompt also demands
low-salience detail be shed. An index built on that would rest on behaviour a
prompt edit could silently revoke. Either the prompt states it, or something
measures it and refuses to steer when it fails.

**And a fallback for when the index is empty**, which for 53 of 67 live banks it
is over their opening turns (§1.21). A progressive form answers both -- rank raw
memories normally, and only reach for a window when the first pass returns
nothing convincing -- and the "nothing convincing" signal that this paragraph
said did not exist is now `recall_confidence` (see the verdict block above).

<a id="unbuilt-2-17"></a>

### 2.17 Memory reliability after temporal separation

**Shelved 2026-08-02.** The benchmark that produced this list — the controlled
chat-38 embedding and character-question comparison, seven isolated questions
per arm — is measurement, and moved to
[`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md) on
2026-08-19 along with the integration-pass landing record. Its headline, kept
because every priority below is ranked against it: semantic answers passed
**7/7** against lexical-only **5/7**, relevant evidence reached the payload in
**5/5** historical cases against **2/5**, and relevant earlier windows **5/5 vs
0/5** — while raw-memory MRR was LOWER for semantic (0.207 vs 0.400), because
lexical put its two exact-word successes at rank 1 and missed the other three
entirely. Reliable retrieval is not yet reliable conduct, and that is what this
list is for.

**Remaining priority order:**

1. **Evaluate behaviour, not only answers.** Build a repeatable memory maze in
   which a character must recognise someone, honour a remembered promise,
   navigate from walked ground, reject a contradicted belief, and distinguish
   witnessed evidence from inference. Score the chosen acts. The existing
   benchmark proves reachability and temporal typing; it does not yet prove a
   memory changes conduct at the right moment.
2. **Separate recall confidence from claim credence completely.** The new
   `epistemic_origin` / `memory_form` names the axes and prevents provenance
   ambiguity, but a numeric recall-strength axis is still absent. A mind may confidently
   remember that it once inferred something while still assigning that
   inference low truth-confidence. Carry `memory_recall_confidence` beside
   `claim_credence`; never let retrieval itself promote the latter. Chat 38's
   kitsune probe exposed the ambiguity: the stored inference was 0.287 while
   the answer about having made that inference reported 0.75 confidence.
3. **Finish interior summary holes for legacy characters.** Chat 38's repaired
   live state has 41 windows and leading coverage is restored, but bounded
   absences remain between surviving windows (substantive coverage: Doctor
   419/452, Picard 8/17, Guinan 25/29). The current backfiller deliberately
   repairs only the destroyed leading era. An interior-hole repair needs the
   same inspect-on-copy discipline and checkpoint propagation.
4. **Log retrieval as an author-facing auditable event.** `memory_effects` now
   records model-declared influence and unbidden recall consumes it, but
   `access_count` still says only that a row was
   returned, but not the query, ranking reasons, score, whether it was cited,
   or whether it influenced conduct. A bounded `memory_retrieval_events`
   ledger should record those separately so false recall, unused payload and
   hub memories become measurable.
5. **Finish retrieval/rehearsal telemetry.** Merely being placed in context
   still does not strengthen a memory; `memory_evidence_used`,
   `memory_effects`, belief citation, and disputes now distinguish four later
   stages. Persist those distinctions in the proposed bounded ledger before
   adopting any accessibility/rehearsal policy.
6. **Retrieve counterevidence with uncertain beliefs.** When a low-confidence
   inference is decision-relevant, surface its strongest supporting and
   disputing rows together. This is the authoritative counterpart to
   non-authoritative contrast recall and prevents repeated one-sided retrieval
   from laundering a guess into certainty.
7. **Tune by query class, never with one global semantic weight.** Label real
   questions as exact quotation/name, place/navigation, thematic paraphrase,
   promise/obligation, or provenance. Tune and evaluate each separately. On
   chat 38 semantic retrieval greatly improved total relevance while the
   lexical fallback sometimes found the first exact hit sooner; both signals
   are useful in different proportions.
9. **Retry semantically unsupported present-evidence use before accepting conduct.** In
   one final semantic trial the Doctor correctly denied that the anomaly was
   active, but supported the denial only with the memory of closing it and did
   not cite the quiet present. The output guard now warns and never fabricates
   a citation. The stronger next step is one bounded retry when a present
   observation exists but `present_evidence_used` supplies none, then accept the
   omission with an audit warning if the retry does not improve it.
10. **Measure the clarified provenance contract.** `epistemic_origin` and
    `memory_form` now name how the claim was acquired versus what representation
    is being recalled. In one prior
    trial the Doctor correctly said Hinami told him her name, cited the exact
    witnessed line, then labeled the answer `remembered` rather than `heard`.
    The prose was right and the typed provenance was wrong because the field
    can be read as "how I know" or "what kind of memory this is." A future
    contract should name those two axes separately rather than prompt harder.

*(Item 8 — "audit summaries against their source rows" — was struck 2026-08-19:
per-clause `support` with `support_refs` + `epistemic_origin` is in `core/db.py`'s
`memory_summaries` and written by `mind/memory.py` at consolidation, derived
host-side so it costs no model call. Its convergence with §2.16 stands.)*

**Measured non-solutions — do not retry without new evidence:**

- Globally stripping appearance boilerplate from summary queries made
  historical-window targeting worse.
- Adding goal/mood/unresolved-thread aspects to summary-window ranking made it
  worse again; the raw-memory result does not transfer to summary prose.
- Always including the origin window spends attention every beat for something
  usually irrelevant. The landed drift-triggered origin rule is the bounded
  form.
- Replacing lexical ranking with embeddings alone throws away the fallback's
  exact-match strength. The measured answer is fusion, then query-class tuning.

The reusable instrument is `tools/benchmark_memory_temporal.py`; extend it
rather than creating another one-off question script. It is no longer married
to chat 38: `--cases-file` loads a case bank
(`tools/memory_probes/behavioral_chat63_char35.json` is the first), and the
retrieval-side probe harness is `tools/memory_probe_harness.py` with its
frozen sets under `tools/memory_probes/`
([`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md)).

---

<a id="unbuilt-2-19"></a>

### 2.19 Character: scope the sheet, do not split the judgement

**Raised 2026-08-12**, alongside §2.18. Recorded so a future session does not
reach for the decomposition first.

The character step is the pipeline's largest single cost (~38.8s median, ~56%
of the turn on a one-reactor beat) and its sheet is the second largest prompt
in the engine: **48 named rule blocks in ~15,100 tokens**. The obvious thought
is to do to it what §2.18 does to the Director. Two halves of that thought,
and they come apart.

**SCOPING GENERALISES. SPLITTING PROBABLY DOES NOT.**

Many of those 48 blocks are plainly conditional and have structural
preconditions that are checkable the same way a specialist's scope is:
`SOMEONE IS WAITING ON YOU` (is anyone actually waiting), `ON PROBATION` and
`GOAL EXHAUSTION` (is a goal actually in that state), `PAIN AND PLEASURE` and
`ATTENTION UNDER STRESS` (is there any), `AUTHORIAL OFFERS` (were any made),
`SPATIAL FRAME` (is there anywhere to go), `UNBIDDEN MEMORY`. Assembling the
sheet from the blocks that apply gets the token and reliability win with **one
call, one mind, one coherent decision** — nothing about the judgement changes.

Splitting the judgement is the part to resist. The Director emits 34 mostly
independent state channels, which is what makes ownership meaningful there.
A character emits a DECISION: speech, action, affect, wants and belief updates
are facets of one act of judgement, and coherence IS the deliverable rather
than a constraint on it. Splitting "what she says" from "what she does" from
"how she feels about it" produces incoherence, not modularity — the prose/diff
join problem again, and worse, because there is no representation to reconcile
against, only a mind that either held together or did not.

**THE FIREWALL OBJECTION IS VOID, and should not be revived.** An earlier
draft of this argued that character sub-agents would multiply the firewall
surface. They would not. The character agent enforces nothing: it receives a
view that perception and spatial already scrubbed, deterministically since
alpha 8.0. Slices of an already-scrubbed view contain nothing the whole view
did not, so no new boundary exists and there is no new place to leak. A leak
there would be perception's failure and would have reached the single
character call identically. The boundary is upstream and singular; do not
re-argue this.

**The genuinely open question is narrower:** *what in that call is not the
judgement?* Psychology persistence already is not — `mind/psychology_runtime.py`
does it deterministically from permitted inputs. If other pre- or post-work is
bundled into the same call, that is separable without touching the decision at
all, and is where any character-side decomposition should start.

<a id="unbuilt-2-20"></a>

### 2.20 Characters begin every story with no past they can recall

**HIGH PRIORITY.** Raised 2026-08-19; the full argument, with its measurements,
refusals and falsifier, is
[`design/DESIGN_PRESTORY_MEMORY.md`](design/DESIGN_PRESTORY_MEMORY.md). This
entry exists so the register names it; that note is the authority.

The measured shape: no memory row in the live corpus has a `turn_idx` below
zero, so the first thing that ever happened to any character is turn 0 of the
story they are in. Their semantic self is rich and their episodic self is
empty.

The diagnosis is not the obvious one. 56 of 58 cards carry
`knowledge.public_history` and it is delivered to the deciding mind every beat
(`agents/character.py`), so the past is not absent -- it is **unrecallable and
unforgettable at once**. It has no `when`, no epistemic origin, and no id
`_ground_observation_citations` will accept, so a mind may mention its history
but may never cite it as evidence for a belief, an appraisal or a dispute. It
never entered the retrieval layer.

The substrate is already half-built and already broken on four counts.
`turn_idx IS NULL` rows are admitted by the read seam and already described to
minds as "before this story's recorded turns" (`mind/memory_context.py`, with a
test pinning the string), and two live mint sites produce them. But the
old-memory temporal cue is gated on `ti is not None`, so the one query language
that names the pre-story past cannot reach the only rows that hold it; those
rows never consolidate; they never archive; and they count toward two floors
calibrated on lived banks.

Why "generate a backstory" is the wrong first move, in arithmetic rather than
taste: the median bank holds 11.5 rows at turn 3, the recent buffer excludes
turn-less rows, and `contrast_memory` scores by subtracting overlap -- which is
near zero for material from another decade, making authored rows
penalty-free by construction. Twenty seeded episodes would clear the contrast
gate at turn 0 and BE the character's entire recall for the opening beats. A
thick authored childhood does not read as depth; it reads as haunting.

Related and separately actionable: the import path already performs an
unlabelled `inherit` (its persona leak was closed 2026-09-04 by
`memory_snapshot`'s foreign-persona refusal), and the fact that
`recall_confidence` cannot fire below 40 rows -- which the median bank does not
reach until turn 10, precisely the window this entry is about.

Partial prototype answer (2026-08-21, `offscreen-charter-prototype` branch,
unwired): `world/charter_promote.remembered` converts a background body's
charter life into `prepare_memory`-vocabulary rows under one selection rule --
minted only from what changed a tracked ledger, the routine compressed to one
semantic row per post, the whole list capped and flat in quiet time (a
30-day famine month: 89 watches stood became 6 memories). It answers the
haunting warning above for the PROMOTION case only; characters authored with
a past, and the retrieval-layer plumbing this entry is really about, are
untouched. Its firewall tests (unheard blame does not cross, the register
does not cross) are the promotion-leak tests
`DESIGN_INSTITUTIONS_AND_UPKEEP.md` §12a called for.

**Several story-start slices have since landed (2026-08-22), and narrow rather
than close this entry.** `story.history_routing` now resolves conservative
automatic and author-locked routes before generation; only fixed or bounded-
moving residents enter Charter. Resident handoff now produces separate career
and recent-life summaries plus 10–16 ordered, identified personal episodes,
constrained to the pre-named roster, real rooms/duties, actual anchors, card
and author guidance. Each episode is an independent memory row; a sparse result
aborts instead of becoming canon. The planner still sees only public placement
material. `story.journey_history` is the
itinerary backend: cited mode compiles card/lore journeys and explicit
generated mode may invent a bounded event ledger. Greeting launch and the
multi-character Story Quick Start expose one route and optional past guidance
per selected character before turn zero; diagnostics show the resulting
handoff.

**The itinerary backend converged on the resident one (2026-08-26).** It had
been the resident path's poor sibling on four measured axes and is no longer:
the event count is the author's (`journey_event_count`, default 12 against the
resident target of 12, band 3–20) rather than a hardcoded 6/8; each event
carries the resident vocabulary's `tone`/`lesson`/`valence`/`arousal`/
`salience`, imported from `world.charter_history` rather than restated, so a
journey row reaches retrieval with the same things to rank on (measured before:
59 of 91 prestory memories at exactly salience 0.6); the ordinal welding
(`"<when>: Early in my travels, …"`) is gone, because when and place have their
own retrievable fields; the first-person requirement is enforced by the
pack-scoped `_FIRST_PERSON_RE` the narration-person machinery already reads,
as a grounding drop rather than a second instruction; and the lived-location
brief now reaches the generator as `arrival_brief`, so the last events may run
toward the place the story opens at. Arriving still is not residing: residence
remains a `story.history_routing` topology decision this generator never makes.

Still unbuilt on that axis: `importance` stays NULL on both paths by design
(NULL reads as the salience and only a consequence the engine can point at
revises it), so mint-time ranking is salience alone.

Still unbuilt: deeper resident eras beyond the recent-life window, direct
Scene Life use of the compact reciprocal episode records before a background
resident is promoted, and claim-level verification of authored/canon traveler
history.

Do **not** generalize that slice by making every selected character a Charter
resident. The full routing argument and authoring proposal now lives in
[`design/DESIGN_CHARACTER_HISTORY_ROUTING.md`](design/DESIGN_CHARACTER_HISTORY_ROUTING.md).
Charter is the right history backend when continuity is organized by a fixed
place or a moving institution (a garrison, court, prison, caravan or starship
crew). It is the wrong backend for an eccentric traveler whose past is a
sequence of journeys, or for a heavily authored/canonical figure whose history
is not engine authority to replace.

The remaining authoring design should complete three independent axes rather
than one genre-specific class enum:

1. **Continuity anchor:** fixed place / moving institution / itinerary /
   unanchored.
2. **Past authority:** simulated / authored lore / imported prior play /
   controlled mixture.
3. **Opening relationship:** resident / returning / visiting / just arrived.

Fixed or institution-anchored story-start simulation now routes through Charter.
The itinerary ledger is built for greeting launch and Story Quick Start but
still needs stronger
claim-level canon verification, obligation/carrier projection, explicit
arrival intersections, reuse outside story start, and measurement over an
adversarial corpus. Imported continuity's identity-safe repair has landed
(`mind/memory_snapshot.py` refuses an import naming a persona who is not this
story's player, and stamps `frame_id`). The hand-built-from-scratch path still needs cast selection before it
can offer per-character routes. A traveler must continue to arrive with
itinerary and authored continuity, never an inferred local career.

<a id="unbuilt-2-22"></a>

### 2.22 Exact-cue matching scans the whole bank, and an index is what it wants

Measured 2026-08-20, [`experiments/RETRIEVAL_COST.md`](experiments/RETRIEVAL_COST.md).
Roadmap rather than defect: the 4.9x constant-factor fix landed, and what is
left is an algorithm choice that only bites at a scale no live bank has reached
yet.

`_exact_cue_score` runs once per ROW per query. Profiled over 8 queries on a
10,960-row bank it was 79.9 of 89.9 seconds -- **89% of all retrieval time**,
against roughly 10% for the vector scan, which is the opposite of where this
project assumed the cost was. Guarding the word-boundary regex with a
substring test and caching compiled patterns took `search_memories` from
4,732 ms to 968 ms with an identical verdict set on all 470 LongMemEval
probes.

That is a constant factor. The complexity is unchanged: every row is still
visited to ask whether any of its cues appears in the query, and the answer is
no for almost all of them.

**The shape the problem actually has is an inverted index**, and this codebase
already runs one for the neighbouring ranking: `_lexical_memory_ranking` asks
SQLite FTS which rows match, rather than asking every row whether it matches.
An `cue -> row ids` index over `key_phrases`, `entities` and `location` would
make the exact ranking O(matching rows) instead of O(bank), and the matching
set is tiny by construction -- that is what makes the cue signal worth having.

Two things to settle before building it, neither hard, both easy to get wrong:

- **Substring semantics.** The phrase branch matches when a stored phrase is a
  substring of the QUERY (and, for short queries, the reverse). An FTS index is
  token-based, so it would need the cue tokenised and the substring rule
  re-derived from token adjacency, or the index used as a candidate filter with
  the exact rule re-run only on the candidates. The second is safer and still
  removes almost all the work.
- **Write cost.** The index has to be maintained on every mint and every cue
  repair. `repair_memory_cues` rewrites cues in bulk, so the rebuild path needs
  to be part of the design rather than an afterthought.

The vector scan is now the largest remaining term and is still a Python loop
over BLOB-decoded rows with no cache. Holding a bank's vectors as one
contiguous matrix is the standard fix, but after this change it is worth about
a tenth of what it looked worth before it -- which is the reason to measure
before optimising, recorded here because this entry got that backwards once
already.

<a id="unbuilt-2-23"></a>

### 2.23 Four of the seven memory kinds cannot be minted

Measured 2026-08-20 while chasing why preference recall is the worst class in
the LongMemEval benchmark (15/30 with real embeddings, 7/30 lexical --
[`experiments/CRC32_CONTROL.md`](experiments/CRC32_CONTROL.md)).

`MEMORY_KINDS` promises seven: `episodic`, `dialogue`, `inference`,
`semantic`, `relationship`, `promise`, `intention`. Every mint site in
`persist/commit_memory.py` hardcodes its kind -- `dialogue` at 580, `episodic`
at 637 and 715, `inference` at 743 -- so no model chooses one and no path
produces the other four. The live corpus agrees exactly: 5,353 `episodic`,
3,576 `inference`, 425 `dialogue`, 253 legacy `episode`, one stray `belief`,
and **zero `semantic`, `relationship` or `intention`**.

Kind barely reaches ranking today (only `inference` is read, for belief
weighting), so this is not a retrieval bug on its own. What it means is that a
stable fact about a person has nowhere to live.

**The retrieval consequence this entry first claimed is REFUTED, measured
2026-08-20.** The claim was that a preference stored as the EPISODE of the
moment it was mentioned drags that moment's location, turn and cast into its
retrieval document, and that a question about a preference has to compete with
all of it. Tested directly on the 15 missed preference probes by embedding the
stored document against the bare content:

    query vs stored DOCUMENT   median cosine 0.4047
    query vs CONTENT alone     median cosine 0.3994

Dropping every incidental makes it slightly WORSE, and content beats document
on 9 of 15 -- a coin flip. Metadata dilution is not the mechanism.

**What the measurement found instead** is that misses are simply far from
their answers in embedding space, and that this is not specific to
preferences:

    other HIT          median cos 0.5334
    preference HIT     median cos 0.4817
    preference MISS    median cos 0.3561
    other MISS         median cos 0.3311

Hits sit near 0.50 and misses near 0.33-0.36 regardless of class. That is the
question-versus-statement asymmetry -- "what do I like to do on weekends" and
"I took the coast path again on Saturday" occupy different regions -- and no
storage change closes it. Preferences are hardest because a preference is
stated once, casually, in language furthest from the category a question names.

So the SHAPE of this entry survives and its retrieval argument does not:
`semantic` is unreachable and stable facts have nowhere to live, which matters
for 2.20's authored past. It is not the reason preference recall is 15/30.

Related: 2.20 wants exactly this shape for a different reason -- an authored
past is mostly semantic rather than episodic, and the same missing tier is why
it has nowhere to go.

<a id="unbuilt-2-24"></a>

### 2.24 A superseded belief is read before its correction

Measured 2026-08-20 across three independently generated fiction worlds,
[`experiments/SYNTHETIC_BANK.md`](experiments/SYNTHETIC_BANK.md). Roadmap
rather than defect: retrieval is not failing, ordering is, and the engine
already contains the mechanism that would settle it.

A `superseded` fact plants a belief and, 60-400 beats later, the observation
that overturns it. The probe targets the correction and antitargets the belief:

| | |
|---|---|
| correction reaches the payload | 16/18 (89%) |
| correction OUTRANKS the stale belief | **8/18 (44%)** |
| median rank of the stale row | **2** |

So the mind is handed both versions and shown the outdated one first, more
often than not.

The mechanism is structural. The four fused rankings -- semantic 1.0,
cue-vector 1.15, keyword 1.1, exact 1.25 -- contain **no recency term**;
recency enters only when the QUERY carries a temporal cue
(`_temporal_mode`). A belief and its correction therefore compete on text
alone, and a question about a belief matches the STATEMENT of that belief more
closely than the later observation that overturns it. Nothing prefers the
newer row because nothing knows which is newer.

**Do not fix this with a recency tie-break.** That arm is already measured and
rejected: newest-first scored tuned 24->21 and held-out 10->13, "three probes
each way, a lottery, not a rule"
([`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md) §4).
A global recency preference trades one arbitrary ordering for another.

**CORRECTED 2026-08-20, and the correction inverts this entry.** The reading
above treats the ordering as the problem and assumes a mind needs help
NOTICING. Measured, it does not. `tools/benchmark_memory_rationality.py` hands
a character the belief and its refutation through the production payload and
asks the question; a judge that never sees the payload classifies the answer
against the plan's two facts. Across three independently generated worlds,
with the character prompt carrying NO instruction to look for conflicts:

| verdict | n=18 |
|---|---|
| named the contradiction | **15 (83%)** |
| stated the corrected fact silently | 2 (11%) |
| **took the superseded belief** | **0 (0%)** |
| neither | 1 (6%) |

Zero failures, despite the stale row being ranked HIGHER in the majority of
cases. The `when` stamp on each row is apparently enough. An arm run WITH a
clause inviting the character to name disagreements scored LOWER on conflict
(4/6 against 6/6), so the behaviour is not prompt-induced -- if anything the
invitation got in the way.

So the ordering defect above is real and cosmetic. What is expensive is not
that a mind reads the stale row first; it reads both, dates both, and resolves
them. Fixing the ranking would change a number and not a behaviour.

**What is actually missing is a channel, not a capability.** Characters are
articulating "I believed X, then I saw Y" in prose, in production, right now --
and it evaporates, because the only way into `disputed` is a structured
`memory_disputes` field the model has to volunteer separately from the prose
it already wrote. That is why the count is 1 in 9,608 while the behaviour runs
at 83%.

Two pieces, and the first is much cheaper than this entry originally implied:

- **Capture what is already said.** The field exists, the commit path handles
  it, the payload renders it as `i_now_read_this_differently`. The gap is
  asking for it in a form the engine can store, on a beat where the mind has
  just done it anyway.
- **Create the occasion.** Genuinely open. In this measurement a question was
  aimed squarely at the contradicted fact; real play does not do that, and a
  contradiction sitting unremarked among twenty other rows may never surface.
  This is where deterministic detection belongs -- two rows, one subject,
  separated in time, both in the payload -- and it stays an OCCASION rather
  than a conclusion, because nothing outside a mind may decide which of its
  memories is true.

**BUILT 2026-08-20, in two parts.** The measurement above located the gap
precisely, and it was not where this entry first put it.

*The grounding was the barrier.* A dispute's evidence was grounded in the
`present` namespace, so a re-reading citing the LATER MEMORY that overturned
the belief -- which is what characters actually cite, 15 times in 18 -- was
dropped as ungrounded before it ever reached storage. Both the code and the
prompt said "what this beat showed you", so this was a stated design rather
than an oversight; it is now widened to admit a memory this mind holds, and
refused only for the disputed memory itself. Firewall-safe on the invariant's
own terms: both rows are its own, legitimately acquired, and one re-reading
another is inference inside a single head. The decisive argument is that
`ponder` exists for exactly this -- a lane built for a mind to go looking
through its own memory, whose output the dispute rule was then refusing.

*And a dispute is now an addendum rather than an overwrite.* `record_dispute`
insists the event stays exactly as it was, but the READING did not get that
protection: a second re-reading replaced the first and only bumped a counter,
so the mechanism built to preserve a memory's history destroyed the history of
how it had been read. Every superseded reading is now kept with the evidence
that produced it, bounded at 8, with the latest still at the top level so no
existing reader moves.

*The rumination watch.* Widening the grounding lets a mind revise its past
from its own memories, round and round, with no new input. That is not
forbidden -- a mind is allowed to keep thinking -- but it can no longer happen
invisibly: `tests/test_dispute_addendum.py` pins that four re-readings citing
one source are distinguishable from three citing three, which a bare counter
could never separate.

**BUILT 2026-08-20, and the entry's own premise was refuted on the way.**

The reading above -- and every version of this entry before it -- says the
dispute lane is starved because nothing ASKS. The asking was built and
measured, and it makes minds dispute LESS.

On a neutral beat, with both rows already in the payload, a character asked
what is on its mind:

| | |
|---|---|
| no occasion offered | **16/16 (100%)** |
| handed the pair and the subject | **13/16 (81%)** |

That is the third measured instance of one shape in a single day. The conduct
table above records an arm run WITH a clause inviting the character to name
disagreements scoring 4/6 against an unled 6/6, and
[`experiments/SYNTHETIC_BANK.md`](experiments/SYNTHETIC_BANK.md) 6 records the
same. **Telling a mind to notice something makes it notice less**, reliably
enough now to plan around.

**What is actually missing is CO-PRESENCE, and the number is absolute:**

| | |
|---|---|
| unaimed beat, ordinary recall, no ponder | |
| both halves of a contradiction in the payload together | **0 / 18 (0%)** |

Never, not rarely. Every one of the sixteen successful disputes had both rows
present, and in every case the ponder lane is what put them there. Ponder
fires roughly 1 turn in 332; `record_dispute` fires 1 in 9,608. That ratio was
the finding, and it was sitting in this file the whole time.

So this entry's FIRST suggested direction was correct and the two that were
buildable were not: *"the ponder lane already does it accidentally... making
ponder more likely on a subject a character has beliefs about may be the whole
fix, and it needs no detector."*

**What shipped.** `schedule_memory_tension_pass` runs after commit, beside
consolidation, and reads what a mind just recorded against what it already
held. It stores the SUBJECT of anything that does not sit together; a later
beat runs that subject as a retrieval and hands over whatever returns
(`resurfaced_without_asking`). The mind receives ROWS. It is never told they
disagree -- which is both the measured-better behaviour and the only version
that respects this entry's own rule that nothing outside a mind may decide
which of its memories is true. Labelled `unbidden_subject` rather than
`query_i_chose_last_turn`, because this mind did not ask and saying it did
would be the engine speaking for a character (compare 1.11i).

Out of band for a measured reason: the reading pass costs **114s** against a
24-row payload and completed 20 of 36 calls in band. Its two failure modes
were budget rather than classification -- `RemoteDisconnected` was already
retryable and merely exhausted three attempts, and a reasoning model ate the
reply whole at 700 tokens and again at 6000.

**The reviewer discriminates better than any character model measured**, and it
is the same deepseek that scores worst as a character (n=18 scorable):

| | belief that turned out unfounded | the world simply changed |
|---|---|---|
| named the planted pair | **11/13 (85%)** | **1/5 (20%)** |

Zero tensions invented from nothing across 36 cases. The gap of +65 compares
with glm-5p2-fast +46, grok-4.3 +1, deepseek-v4-pro -20 as CHARACTERS on the
same axis. The framing does the work, not the weights.

**THE LANE IS CONFIRMED WORKING IN LIVE PLAY, 2026-09-04, and the rate item
this entry left open is answered.** Read off the author's corpus, split at the
build date:

| | memories | disputes | rate |
|---|---|---|---|
| before 2026-08-20 | 9,361 | 1 | 1 in 9,361 |
| after 2026-08-20 | 5,638 | 40 | **1 in 141** |

A 66x increase, and the "before" column reproduces this entry's own 1-in-9,608
independently. 41 rows across 25 chats; 3 have been re-read more than once, so
the addendum history is exercised too. One dispute was traced end to end
(chat 114 turn 8, the Doctor on Hinami): `disputed` written with the
re-reading, importance raised to 0.815, the superseded hypothesis gone from
`mind_models` and replaced by the corrected one at the top of 18, and recall
delivering the row with `i_now_read_this_differently`. Confidence landed at
0.3025, which is `_abandoned_confidence` exactly (mint 0.55 x 0.55) -- so the
belief was genuinely dropped rather than merely annotated.

**But the mechanism that fixed it is not the one this entry predicted, and
that part is still open.** The re-readings were sorted by what they cite:

| | |
|---|---|
| cited the present beat only | **39 / 41** |
| cited own memory (the 2026-08-20 grounding widening) | **1 / 41** |
| cited nothing | 1 / 41 |

And by how old the disputed row was: 34 of 41 were disputed within 2 beats of
being formed. Even the seven long-gap cases -- +11, +21, +43, +86 beats --
fire on `current:` events. So what produces a dispute in play is A PRESENT
PERCEPTION CONTRADICTING A HELD BELIEF, not two memory rows arriving together.
That is a statement about which occasions have ARRIVED, not about which
mechanism works: the first open item below is why the corpus cannot yet offer
the other one.

And the rate itself is right, not low. On the denominator that has
opportunities -- character results that could have carried one --
`memory_disputes` fires **1.81% (36/1987)**, against the `0 of 178` this entry
was written on. A mind that re-read its own memories often would be unstable
rather than perceptive; rare is the correct shape for this, and what matters
is that it is no longer zero.

- **The co-presence occasion has had almost no chances, and 1-in-41 is the
  wrong denominator for it.** `schedule_memory_tension_pass` and
  `resurfaced_without_asking` shipped, and the grounding was widened to admit
  "the later memory that overturned the belief" because characters cited one
  15 times in 18 on the synthetic bank -- where a belief was planted and its
  correction arrived **60 to 400 beats later**. The corpus does not reach
  that. Median story is **26 turns**; the longest ever played is 171; **none
  has reached 200**. Since the 2026-08-20 landing there are 1,539 turns across
  36 chats and the longest single horizon is 120. The upper half of the range
  this lane was designed for has never occurred once.

  So measuring it against all disputes is exactly the mistake `fire_rates.py`
  exists to prevent (`Design.md`, "Which mechanisms actually fire"): a
  mechanism with no opportunities reports `no chances`, never 0%. What the
  present-beat route being 39 of 41 shows is that the SHORT-horizon
  contradiction is common and the long-horizon one is not yet reachable --
  not that the built lane is mistuned. Nothing should be enriched or removed
  here until a story runs long enough to give it chances.

  Two things would settle it, and neither is code: a story past ~200 beats,
  and the same fire-rate read taken again afterwards.
- **A mind has no record of HAVING pondered.** `memory_ponder` is popped when
  consumed and no row is minted, so a character that has asked itself the same
  question five times cannot notice. Deliberately not built: a row per ponder
  is noise, and it changes what gets minted. It is the same shape as the
  rumination watch on disputes, which chose legibility over prohibition.

**The original reading, kept because it was the reasoning at the time:**

**The engine already has the right shape and never reaches it.**
`record_dispute` is wired end to end -- proposed in the character's output,
committed by `persist/commit_memory_write.py`, stored on the row, and rendered
to the mind as `i_now_read_this_differently` -- and it has fired **once in
9,608 live memories**. The gate is that `memory_disputes` is entirely
model-initiated: a character must spontaneously volunteer that it now reads a
memory differently, and nothing detects a contradiction or offers the
occasion. Compare `ponder`, also model-initiated, also rare (7 uses in 2,328
turns).

The shape of a fix, in the engine's own vocabulary: a mind handed two rows
about the same subject, separated in time, is being handed an occasion to
revise, and the payload can say so without deciding the answer. That is the
firewall-safe direction -- give the mind the material, never make it conclude
less. What must NOT be built is a deterministic contradiction detector that
decides which row is true; nothing outside a mind is entitled to that.

**Not established, and the honest caveat**: both rows usually reach the
payload, and each carries `when` ("about N beats ago"), so the character HAS
the material to prefer the newer one. Whether it does is a conduct question and
is unmeasured. Ordering matters because it decides what is read first, not
whether the answer is present. 18 probes is also a small set, reported with its
denominator.

<a id="unbuilt-2-25"></a>

### 2.25 Two retrieval ideas measured, one rejected, one parked

Measured 2026-08-20 against the 470-probe LongMemEval bank while looking for
what else would raise recall. Recorded so neither is retried without new
evidence.

**HyDE (embed a hypothetical answer, fuse it as an aspect) -- REJECTED.**
The motivation was sound and is worth keeping: misses sit at 0.33-0.36 cosine
from their answers while hits sit near 0.50 (2.23), which is the ordinary
question-versus-statement asymmetry, and writing what the remembered moment
would have SOUNDED like is the standard answer to it. Measured on 30 probes
that miss, it rescued 3 (10%). Measured on 40 that hit, it broke 1 (2%). Hits
outnumber misses six to one, so the extrapolated net is **+7 rescued against
-10 broken**. Measuring only the rescue rate would have made this look like a
win; the breakage arm is the whole finding.

**Query decomposition (split the question into clauses, fuse each as an
aspect) -- PARKED, not rejected.** Deterministic split on relational
connectives, clauses of three or more words, capped at three. Across all 470:
399 -> 402, **rescued 3, broken 0**. Strictly non-destructive on this
instrument and free at runtime, since aspects ride the same embedding call as
the query. Not shipped because +3 on one bank is inside the noise of a single
instrument and it has no conduct arm -- the same standard that let the
`_RECALL_LIMIT` change through. Cheap to revisit: `search_memories` already
accepts `aspects`, so this is a caller-side change with no plumbing.

## 6. Design-note residuals

<a id="unbuilt-6-6"></a>

### 6.6 Psychology as pressure — [`DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md)

(a) and (b) shipped; (e) declined by design. Open: (c) deterministic inclination
beside the raw sheet, and (d) a trait as a disposition rather than a switch —
both argued at length in that note under their own letters, including the
constraint that (c) must RELOCATE salience rather than add it. *(Restated here
until 2026-08-19.)*

<a id="unbuilt-6-7"></a>

### 6.7 Long-term goals — [`DESIGN_LONG_TERM_GOALS.md`](design/DESIGN_LONG_TERM_GOALS.md)

v1–v3 are built, including goal-slot currency. The three undecided questions —
whether a renewed intention should cost something, whether displacement should
feed the drive-strain ledger, and whether drive and project both weighing 1.0
needs revisiting — are that note's "Not yet decided" list. *(Restated here until
2026-08-19.)*

<a id="unbuilt-6-9"></a>

### 6.9 Character-agent output audit — [`../design_notes/09-character-agent-audit.md`](../design_notes/09-character-agent-audit.md)

Optimization audit (2026-08-11) of `character_step`'s output contract on the
owner's corpus snapshot, recent era n=404 calls. Verdict worth keeping: the
stage does NOT have `director_resolve`'s 84%-discard profile — ~85-90% of its
~1,974 output tokens/call is genuine product, and the psychology division of
labor (model authors appraisal, `psychology_runtime`/`affect` own persistence)
is already right. The note holds the measurements. The instrumentation, the
stress/hedonic template shrink, the goal-slot derivation and the observation
wrapper compaction landed 2026-08-11 (Design.md rows "The character contract
asks only for what commit reads" and "A second model call says it happened");
still open:

- **`considered_responses`** — schema-documented viewer-only scratch
  (`schemas.CharacterOutput`, beside `_coerce_considered_responses`, and still
  required by the prompt's own JSON shape), duplicates the consumed
  `response_candidates` in
  137/404 calls (re-measured 130/401). Engine-unread is NOT the bar: a
  freeform pre-list is plausibly chain-of-thought that seeds better
  candidates, so the gate is a cheap `contract_bench`-style A/B on stored
  payloads, not a grep. Drop it from the required JSON only if the A/B shows
  no candidate-quality cost. ~0.8s/call.
- **Read the second-call notes before designing a bounded-delta retry.**
  Every retry/repair rung now writes one `_engine_notes` line naming its
  path and duration. After a few sessions the deciding number is: fires of
  `"decision review retry"` per 100 character calls, times the mean duration
  those lines carry. Below ~5 fires/100 the full re-solve costs ~1-2s/turn
  amortized and is not worth a design that risks coherence between a
  regenerated sequence and a pinned appraisal; at ~15+/100 with ~30s
  durations it is the largest remaining lever in the stage.
- **NOT approved for cutting:** appraisal prose scratch
  (`goal_relevance`/`expectation`/`uncertainty`/`emotion`, ~130 tok/call) is
  engine-unread but sits upstream of numeric axes that are non-default in
  98-100% of emissions — a `contract_bench`-style A/B on stored payloads is
  the gate, not a grep.
- **Payload reordering for a longer cached prefix — gated on the affinity
  measurement.** The character payload opens with mostly-stable sheet-derived
  fields but places volatile `active_state` seventh, ahead of stable
  voice/senses/abilities/attire, so the cross-turn shared prefix breaks
  ~1-2k tokens in where it could run ~4-5k. Moving the volatile `self`
  fields after the stable block would lengthen the prefix implicit caching
  can reuse — but unlike the `user` routing hint this changes what the model
  reads in what order, which is a quality question needing its own argument.
  Do not build until the cache-affinity hint has run for a few sessions and
  `_log_usage`'s `cached_tokens` shows (a) hits landing at all, and (b) hits
  consistently stopping near the system-prompt boundary rather than deeper —
  only that pattern makes the reorder worth a quality A/B.

<a id="unbuilt-6-15"></a>

### 6.15 Jev around the character call — [`DESIGN_JEV_CHARACTER_PASS.md`](design/DESIGN_JEV_CHARACTER_PASS.md)

Proposal, 2026-09-26. Built but NOT WIRED: the affect pass --
`mind/affect_appraisal.py` (the Jev questions) and `mind/affect_mix.py` (OCC
emotions, the mood as fourteen spectrums and thirty-two standalone moods,
habituation, the layer beneath); nothing in the turn calls them. Open: wiring
them before and after the character call and retiring the prompt's affect
paragraphs; every knob and every `EMOTION_EFFECTS` value (the owner's);
Japanese situations for the battery, since the Japanese wordings are
untested translations; a concern gate that discriminates (Jev weighs every listed
concern about 0.7);
own acts' pride tilt; naming the combinations the coverage table lists; the
memory packet (a fitted weighted-RRF net of 100 over new lanes, then Jev) with
the moment tag written at commit -- which the memory-born moods wait on, since
today's packet stirs the scene's own moods; the fun sections; a ponder
answered by Jev over the whole bank; same-beat recall. The note's nine owner
decisions are the list. Measured in
[`JEV_MEMORY_PROBE_2026_09_26.md`](experiments/JEV_MEMORY_PROBE_2026_09_26.md);
instruments `tools/jev_*.py`.

<a id="unbuilt-6-16"></a>

### 6.16 Good memory — [`DESIGN_GOOD_MEMORY.md`](design/DESIGN_GOOD_MEMORY.md)

Proposal, 2026-09-26; nothing built. Twelve features borrowed from how people
remember, under the owner's goal of good memory rather than realistic
forgetting: sifting within the moment, larger packets organized by why each
row is there, activation from use, open intentions, unbidden cues, mood-aware
recall, surprise, self-defining memories, person dossiers, who else would
remember, consolidation that organizes, and the current state first (which is
§2.24). The note says where to start.
