# Jev around the character call: the tracking pass and the memory packet

**Status: PROPOSAL, 2026-09-26, branch `worktree-jev-character-tracking`.**
Nothing is built. Every number below comes from four read-only surveys of the
code and of `engine.db` (`llm_capture`/`llm_blobs`, `variants._engine_notes`)
over the ten days to 2026-09-26, spot-checked by hand.

## Why

The owner (2026-09-26): "I want to see how much of the character call we can
turn into jev calls that run before it, if we feed jev relevant psychological
details of the character it is acting as a part of I imagine we can make a lot
of tracking tasks something the character llm no longer has to keep track
of." And: "I think we can answer what kind of mood current events might put a
character into with jev's list answers and past moods", "I imagine we can use
it for book keeping as well", and a memory packet chosen by Jev from 100+
reciprocal-rank-fusion candidates, "we can even use autobiographical summaries
to get era relevancy."

It is the prose contract's argument one stage down
([`DESIGN_PROSE_CONTRACT.md`](DESIGN_PROSE_CONTRACT.md)): making a model track
everything costs it the ability to play author.

## What the character call spends today

- **Time.** `character_major` median about 26 s on GLM (p90 52 s), 24-30k input
  tokens, **0% cached**, about 4.5-5.3k output tokens of which about 60% is
  reasoning. Every beat made exactly one call per acting character, serially
  on the critical path; an interaction loop re-asks the same character up to
  six times a beat, and every round rewrites the whole tracking block while
  only the last round's appraisal and manifest survive.
- **Output.** The visible reply averages 7.9k chars. **About 81% is
  bookkeeping**: `state` 44% (appraisal 25%), `updates` 29%, `manifest` 8%.
  Conduct -- the `sequence` of speech and actions -- is 16%; the spoken words
  alone are 4.6%. Key names are 26% of the characters. Hand-checked on the
  five latest replies: bookkeeping 83-89%.
- **Reasoning.** About half of the trace plans the bookkeeping (field names
  appear in most traces: intentions/tells 77%, wants 72%, people 64%).
- **Instructions.** The card (`prompts/character.txt`, 23k chars) spends 43%
  on tracking paragraphs.
- **Unread.** `appraisal.goal_relevance / expectation / emotion /
  uncertainty`, `goal_impacts[].intentionality`, `yields_floor` have no reader;
  `present_evidence` is only grounded. `updates.projects` is written in 2 of
  161 replies, `updates.drive` in none.

## What Jev is

`llm/decisions.py`, TypeSafe's `typesafe/jev-1.13` on OpenRouter's
`/api/alpha/decisions`. One shared STATE per request, up to 64 independent
questions, each with its own instructions: `noul` (a probability), `choice`
(a key **and a distribution** over the options, which no caller reads today),
`score` (a position; never used or measured). 0.2-1.3 s a battery, about
$0.00002 for 38 questions, about 1,100 output tok/s.

What it has shown (Director use, `ENCODER_REPAIR_2026_09_24.md`,
`DESIGN_PROSE_CONTRACT.md`): reliable when the thing judged is QUOTED in the
question and the judgement is concrete (misplaced write 1.00 precision,
placement 0.99); weak on compound conditions and "is this already true?";
probabilities uncalibrated and rarely above 0.8, so thresholds are fragile
and orderings are not.

## The split

Three rules, then the fields.

1. **Jev judges, the character acts, code writes text.** A Jev answer is a
   choice or a grade; any `why` or evidence text a reader needs is written by
   code from the thing Jev cited.
2. **Jev files; the character decides.** Anything that is a decision the
   character makes -- adopting a project (it has an adoption deliberation),
   abandoning an intention (the owner's rule: it needs a stated reason), giving
   up on a promise -- stays with the character. Jev may notice; it does not
   decide.
3. **The firewall holds by construction.** Jev's state is built only from the
   character's own gated payload -- its sheet, its memories, its perception of
   this beat -- never from the scene or the Director's account, and **one
   request per character**: every question in a request reads the whole state,
   so two minds in one request would share a context.

Jev's distributions are used for grades and orderings, never as gates.

### Before the call: how this beat lands on you

One Jev request per character, state = psychology (drive, values, self-model,
stress profile), last beat's mood, steering intentions and projects with ids,
the beat's observations with ids, and the delivered memories with refs.

| Replaces | Question |
|---|---|
| `active.affect` (surface, undercurrent) | **Measured 2026-09-26** (the evidence doc, "Mood as a Jev job"): not one choice over the lexicon but sixteen graded questions -- Plutchik's eight primaries plus desire, five spectrums (pleasure, arousal, dominance, playful/serious, open/guarded), and two for the quieter layer beneath. Several moods come out at once; code names the blend from Plutchik's dyads. Code carries the mood from beat to beat and moves it part of the way toward Jev's reading (the card's `stress_profile` sets how far), which beat pure persistence on every axis measured. Needs the moods the character came in with in Jev's state; intimate moods need explicit words. |
| appraisal's six axes | An ordinal `choice` each (five grades), read as the expected grade; `score` measured alongside. |
| `goal_impacts[]` | Per live aim: impact grade (hinders strongly ... helps strongly, "does not bear on it"), agency (self/other/world/none), evidence (one of the beat's observation ids, or none). |
| `somatic_impact` | Pain and pleasure grades plus an evidence choice. |
| `memory_modulation` | Which delivered memory the moment echoes (or none), plus four grades. |

The character call then receives these as a given block ("how this lands on
you") and stops writing them; the card loses the matching paragraphs.

### After the call: filing what was done

Off the critical path: it needs the character's conduct, and its results are
read only at commit, so it runs beside `director_resolve`.

| Replaces | Question |
|---|---|
| `updates.intentions` on existing ids (136 of 149 measured ops) | Per steering intention: none / progress / block / satisfy / nonviable, plus evidence. `add` and `abandon` stay with the character. |
| `updates.beliefs` reinforce/weaken (75 of 83 ops) | Per held belief the beat touched: reinforce / weaken / neither. Revisions and new beliefs stay. |
| `updates.associations` (65 of 65 ops were reinforce) | Per held cue present: reinforced or not. |
| `updates.relationships` | Per known person present: five grades plus a trigger. |
| `updates.memory.keep` | A `noul` per line heard this beat. |

Stays in the character call: `sequence`, `effects`, `interaction`, `wants` +
`decision`, `surface_demeanor` and the tell cues, new `people` claims,
intention `add`/`abandon`, projects, drive shifts, belief revisions,
reinterpretations, `ponder`.

### The card as Jev's question bank

The owner, 2026-09-26: "now look at the character prompt and theorize what we
can reduce to jev questions (Fed with psychology fields from the character
card) Before and after the character call."

Most of a generated card's `psychology` is authored cue-to-response data, and
today the character model reads all of it on every call to find what applies.
"Is this present in what you perceive?", with the card's own words quoted, is
the concrete judgement Jev is reliable at. One atomic question per card item;
code composes the answers -- a trait is engaged when one of its cues is
present and none of its inhibitors is, never asked as one compound question,
which is where Jev is weak.

| Card field | Asked before the call | Becomes | After the call |
|---|---|---|---|
| `traits[].activation_cues`, `inhibited_by` | per cue and inhibitor: present? | the traits engaged, each with the cue that engaged it | -- |
| `values[]`, `conflicts_with` | per value: at stake? per pair: set against each other? | values at stake; the tension between two | -- |
| `self_model.pride_triggers`, `shame_triggers` | per trigger: touched? | pride or shame pressure, feeding the affect choice | -- |
| `self_model.protected_beliefs`, `beliefs` | per belief: challenged? | a threat to who they are | reinforce / weaken (the row above) |
| `coping.strategies[].trigger` | one choice: which strategy the moment calls up, or none | `stress.coping_mode`, written by the model today | -- |
| `coping.recovery_supports` | per support: present? | recovery this beat, applied by code | -- |
| `stress_profile` numbers | one grade: how much the moment strains you | code applies `baseline_reactivity`, `overload_threshold` and `recovery_rate` to it; `recovery_rate` also carries mood from beat to beat | -- |
| `stress_profile.somatic_signs`, `coping.under_stress` | one choice: which authored sign shows, or none | a tell the character may use | -- |
| `learning.associations[].cue` | per cue: present? | the associations that fire, with their `appraisal_bias` | reinforced when fired (the row above) |
| `drive` | a grade: does the moment touch the essence? a `noul`: does anything tempt toward the taboo? | drive pressure; a taboo alarm | a `noul`: did the conduct cross the taboo? It flags a rupture occasion; the drive shift stays the character's |

The Doctor's card (chat 63): 24 activation cues, 12 inhibitors, 5 values and
7 conflict pairs, 8 pride and shame triggers, 5 protected beliefs, 3
strategies, 4 supports, 4 associations -- about 75 questions from the card,
about 110 with the rows of the section above: two requests, well under a
second, about $0.001 per character per beat. 33 of the 67 cards in the
database carry these lists; a card without them gets fewer questions, and no
new field is asked of an author.

Code writes the answers as one block, "what presses on you", in the prompt's
own terms ("Drives and traits are pressure, not premises"): the traits
engaged and their cues, the values at stake, pride or shame touched, the
coping pull, the associations that fire, drive and taboo pressure -- then how
the beat lands, surface and undercurrent.

After the call, beyond the section above:

| Replaces | Question |
|---|---|
| `updates.memory.effects` | Per delivered memory the conduct could have drawn on: did it shape what you did -- integrated, resisted, dismissed, or no? |
| `updates.people` on readings already held | Per held reading of someone present: did what they did support it, undercut it, or neither? New readings stay. |
| `active_concerns` | Per held concern: is it settled now? New concerns stay. |
| `hedonic.released` | Did the enacted sequence complete a release? |
| `contact` removal | Per standing contact: does the sequence separate its endpoints? |
| `salience` | How much will this beat stay with you? |

### The prompt, paragraph by paragraph

`character.txt` is 68 paragraphs, 22,840 characters. With the rows above
moved out:

- **Removed** (9 paragraphs, 2,518 characters): pain and pleasure, the
  sustained drive's release, active hypotheses, sensation and thought, what
  you keep, memory effects, associative learning, relationships, ending
  contact.
- **Cut to what stays with the character** (12 paragraphs, 6,717 -> about
  3,490): current feelings becomes the explanation of the given block;
  intention continuity keeps `add` and `abandon`; current evidence keeps its
  rule without the `goal_impacts` schema; belief learning keeps `revise`;
  theory of mind keeps new readings; unbidden memory, persist the reasoning,
  attention under stress, earlier this beat, deliberation, the `updates`
  paragraph and the JSON shape shrink with them.
- **Untouched** (47 paragraphs): conduct -- sequences, speech budget, mouth,
  field of view, interrupting, ponder, following, material, effects --
  reading perception, the spatial frame and running, voice, self-repetition,
  the waiting, project and fading decisions, and the memory-is-past rules.

The instructions shrink by about a quarter, to roughly 17,500 characters with
the new block's explanation. The larger saving is output: appraisal (25% of
today's reply) goes whole, `updates` (29%) keeps only its rare rows,
`state.active` keeps `wants` -- about 40% of today's reply remains, before the
reasoning that planned the rest. The call is decode-bound, so that is the
time; and the interaction loop, which rewrites the whole tracking block every
round, stops rewriting it.

What pushes back:

- **Owner decision 3, and an audit.** The 2026-08-11 output audit
  ([`UNBUILT_CHARACTERS.md`](../UNBUILT_CHARACTERS.md) §6.9) called "the
  psychology division of labor (model authors appraisal, `psychology_runtime`/
  `affect` own persistence) ... already right". It weighed the model against
  code; a judge that is not the actor is a third option it did not have.
  Appraisal theory sides with the proposal -- a feeling arrives from appraisal
  before anyone chooses it, and agency is in what the character does with it
  -- but it is a behaviour change to every character, so it waits for step 1
  of the measurement below: Jev against the character's own answers on
  captured payloads.
- **The interaction loop.** Re-run the before-call questions per round only
  for what reached the character since the last round; the after-call pass
  runs once per beat.
- **The firewall.** Every question reads only the character's own perception,
  memories and card, one request per character (rule 3).

### The memory packet

- **Candidates.** The fused (RRF) score already ranks the whole bank; take the
  top 150 (or the whole bank -- recent characters hold 99-181 rows) BEFORE the
  diversity pass. Widening the lanes does nothing: each is capped at 60.
- **Jev.** One `noul` per candidate: does this memory bear on what you face
  right now, with the memory's own text quoted in the question and the
  character's perception, mood and concerns in the state. Three shards, about
  a second, concurrently with the pre-pass.
- **Era, as a soft signal.** A few `noul`s over the character's summary
  windows (does this chapter of your life bear on now?) add a boost to
  memories inside the windows that do. Not routing: ranking windows first and
  searching inside the winner scored 6-7/12 against 10/12 for flat retrieval
  (`AUDIT_MEMORY.md` §3.2), and most characters hold 0-1 windows today, so
  this matters more as stories grow.
- **Packing.** Code orders by Jev's probability (fused score breaks ties), keeps
  the existing diversity pass and chronological neighbours, and stops at
  26-30 -- inside the band the docs measured: recall climbs to k=48, conduct
  peaked at k=24 (`RETRIEVAL_COST.md` §6).
- **The judge that failed.** An in-turn LLM judge of recalled rows was moved
  out of the turn for measuring 114 s per 24 rows, 16 of 36 calls never
  returning (`mind/memory_judge.py`). Jev is what makes judging in the turn
  affordable.
- **A fix it needs.** Batteries over 64 questions shard into threads that do
  not inherit the call-ledger context, so their usage is never recorded; the
  fix exists on `codex/jev-encoder-contract` (`copy_context`) and would be
  ported, not merged. (Confirmed 2026-09-26: a sink set around a 970-question
  pass recorded 0 of its 18 requests.)

### The packet, as measured (2026-09-26)

Evidence: [`JEV_MEMORY_PROBE_2026_09_26.md`](../experiments/JEV_MEMORY_PROBE_2026_09_26.md),
22 beats of one character on banks of 308-649, and 71 questions. It replaces
the first three bullets above.

- **The net is a fitted weighted RRF, not the fused score.** Today's fused
  ranking keeps 55% of Jev's topical top 30 inside 100 and 53% of a
  five-channel packet. Weighted RRF over the generators plus four new lanes --
  `primed` (last beat's packet), `primed_nb` (rows nearest it), `recency`,
  `here` -- keeps 81% and, with the tag below, 79% of the packet (90% at
  200). Today's fused ranking earned weight 0 in every fit.
- **Tag each memory's moment once, at commit.** Mood-contrast picks were
  invisible to every lane (15%): Jev reads them from what the moment
  contained, while the stored affect is the character's own feeling at
  encoding. One Jev choice per new row -- how did this moment feel -- makes
  mood contrast 85% reachable alone, and the fun channels with it. It is a new
  stored field, so it takes the schema checklist (`DATABASE.md`).
- **No Jev feedback round.** Grading the first 30-60 and refilling around the
  best added nothing over `primed_nb`.
- **"Everything Jev would pick" is defined at 100, and reached at about 300.**
  A reworded Jev keeps only 70-87% of its own top 30 but all of it inside its
  top 100; holding every pick of one wording needs a median of 272-344 rows.
- **A ponder reads the whole bank.** Retrieval hands a ponder about one of its
  five best answers at k=8 and two at k=24; the best fitted pool of 50 holds
  60%. A ponder fires about one beat in 332, and 650 rows cost $0.005, so the
  judge reads everything and picks the five.
- **The fun sections** (the owner's "ironic to bring up", "good teasing
  material"): `callback` and the tact channel `sore` pick the right rows and
  are reachable; `irony` is mixed and unreachable by any lane (22%); `tease`
  is flat and needs a question about what was said or done.

## What it should save, and what it costs

Estimates to be measured, not results:
- The character call writes about 1.5k fewer visible tokens a beat plus the
  reasoning that plans them: plausibly 30-55% of its time.
- Jev adds about 0.4-1 s before the call (the mood/appraisal battery and the
  memory battery run concurrently) and nothing after it.
- A 26-30 row packet adds about 12-16 KB of uncached input over today's median
  of 4-8 rows.

Measured 2026-09-26 (Jev's own `usage.cost`): **about $8 per million
questions** once each carries a quoted memory -- 200 input and 58 output
tokens a question, not the $0.00002 per 38 of a Director battery above. Per
character per beat: a net of 100 on 5 channels $0.004, on 9 channels $0.007;
the whole bank of 650 on 5 channels $0.026, about a character call's worth.

## How it will be measured

On a copy of the database in this worktree, from captured calls: `llm_capture`
stores every character call's full request, so the same inputs can be replayed.

1. **Jev against the character's own answers**, same payloads: mood top-3
   agreement and valence/arousal correlation, goal-impact sign agreement,
   evidence agreement, intention-op agreement.
2. **The slim call**: output tokens and seconds against the original, and the
   conduct read side by side -- the page is the test.
3. **The packet**: old against new on the same beats, read by the owner on a
   sample and by a second model on all of them.

Character calls are the expensive part: credit is checked first, on the
owner's replay route.

## Owner decisions

1. **Absorption.** Under pain, pleasure or stress the packet is cut to 4 or 8
   rows today (59% of captured calls). Does a Jev packet override that, or does
   absorption scale it?
2. **The drive in goal impacts.** No measured impact has ever served the drive
   (0 of 227). Asking Jev about it would start feeding drive strain -- a
   behaviour change.
3. **Mood as a given.** The character is told how the beat lands instead of
   deciding it.
4. **Order.** Proposed: the memory packet first, then the pre-pass, then the
   post-pass.
5. **The moment tag.** A new stored field on every memory, written by Jev at
   commit (one question a row), with backfill for existing banks.
6. **Which fun sections ship.** `callback` and `sore` are ready; `irony` and
   `tease` are not. A section title is an affordance -- "good teasing material"
   invites teasing -- so each would be capped at two or three rows and judged
   for this character.
7. **The weights.** Fitted to one story's character; a second story's label
   set comes before any of them becomes a constant.
8. **Packet size.** Graded blind, a 48-row Jev packet holds fewer irrelevant
   rows (3.6) than today's 24-row one (5.6) and about 4x the relevant ones;
   the k=24 ceiling was traced to exactly those irrelevant rows. A conduct
   replay on captured character calls (RRF@24, Jev@24, Jev@48, Jev@48 with a
   slimmed prompt), judged blind and read by the owner, decides it; it spends
   character calls on the owner's route.
9. **Same-beat recall.** The owner, 2026-09-26: the goal is GOOD memory, not
   realistic forgetting, and "people can sift through memory really rapidly
   if they need to" -- a ponder cannot, being answered a beat later. Jev
   reads a 650-row bank in about half a second, so a recall a character asks
   for mid-call could be answered before it finishes; the engine has no
   model tool-calling loop today, so it is new plumbing in the character
   call, and gisting the packet's periphery is rejected in its favour.

## Found on the way

- `waiting_ops` is taught (STILL WAITING, `character.txt:41`) and read at commit
  (`persist/commit_background.py:1655`), but `agents/character_kernel.py`
  `_UPDATE_LANES` never compiles it: no character can give up on a promise.
- `docs/guides/MEMORY.md` §3 and §5 say k=16 and that recall bumps the access
  count on the spot; the code uses 24 and writes at commit.
- Memory `entities` hold the label a row was perceived under ("the beautiful
  young woman", "the player") beside the name ("Hinami"), so no entity lane
  can gather one person's rows; and witnessed scene rows carry none.
