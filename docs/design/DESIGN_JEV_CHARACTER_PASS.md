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
| `active.affect` (surface, undercurrent) | One `choice` over the pack's 67-label `AFFECT_LEXICON`: which best names how the moment leaves you, given how you felt a moment ago. Surface = the top label; valence and arousal = the distribution's expectation over each label's signs; undercurrent = the strongest label of the other valence carrying real weight -- **a hypothesis to test**, not assumed. |
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
  ported, not merged.

## What it should save, and what it costs

Estimates to be measured, not results:
- The character call writes about 1.5k fewer visible tokens a beat plus the
  reasoning that plans them: plausibly 30-55% of its time.
- Jev adds about 0.4-1 s before the call (the mood/appraisal battery and the
  memory battery run concurrently) and nothing after it.
- A 26-30 row packet adds about 12-16 KB of uncached input over today's median
  of 4-8 rows.

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

## Found on the way

- `waiting_ops` is taught (STILL WAITING, `character.txt:41`) and read at commit
  (`persist/commit_background.py:1655`), but `agents/character_kernel.py`
  `_UPDATE_LANES` never compiles it: no character can give up on a promise.
- `docs/guides/MEMORY.md` §3 and §5 say k=16 and that recall bumps the access
  count on the spot; the code uses 24 and writes at commit.
