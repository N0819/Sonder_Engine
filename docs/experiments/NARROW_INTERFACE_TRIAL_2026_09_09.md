# Trial: reducing eight sheets to role + shape, and what refuted it

2026-09-09. Sixteen agents, no failures, 2.35M subagent tokens, 27 minutes.
Design under test: [`DESIGN_NARROW_MODEL_INTERFACE.md`](../design/DESIGN_NARROW_MODEL_INTERFACE.md).
Method: one reducer per sheet classifying every rule into the design's seven
buckets and drafting a replacement, then an INDEPENDENT skeptic per sheet
prompted to refute the deletions and default to refuted when uncertain.

Drafts are in `narrow_interface/*.draft.txt`. **None of them is shippable.**
That is the useful result: the direction survived and the execution did not, and
the distance between those two is now enumerated instead of guessed at.

## What the reduction found

| | chars | |
|---|---|---|
| eight sheets, as they ship | 224,993 | |
| the drafts | 47,764 | **-79%** |

Per-sheet cuts ran 60% (director_interpret) to 93% (the shared specialist core).
541 rules were classified:

| bucket | n | share |
|---|---|---|
| **category** -- a field or enum value wearing a paragraph | **204** | **38%** |
| engine_repairs | 133 | 25% |
| **irreducible** | **78** | **14%** |
| engine_drops | 57 | 11% |
| coordination -- exists only because there are five hands | 45 | 8% |
| needs_guard | 23 | 4% |
| decipherable | 1 | 0.2% |

**Two of those numbers correct this note's own author.**

`irreducible: 78`, not the four the design note claimed. That four came from
counting capitalised lead-ins in specialist chunks, which is a sampling frame,
not a floor. The real floor is an order of magnitude higher, and the design's
"role plus shape plus a handful of judgment fields" understates what a mind has
to be told.

`decipherable: 1`, against a design that expected `op`, `manner`, `relation` and
`motion` to fall out of the change sentence code already has. Across 541 rules,
one. The hypothesis that code can read the ledger's prose back into its
categories did not survive contact with the sheets -- which is consistent with
the 2026-08-29 record of guards that read free prose, and is an argument for the
grammar (design note section 5) rather than for cleverness.

## What refuted it

| verdict | sheets |
|---|---|
| unsafe | 6 |
| mixed | 2 |
| sound | 0 |

93 findings: **43 feature_loss, 27 silent_data_loss, 17 firewall**, 6 style.
And **39 bad guard claims** -- a reducer citing code as proof a rule was
unnecessary, where the code drops rather than repairs, or does not run on that
path at all. The design note named that as the one failure mode worse than not
reducing at all. It happened thirty-nine times across eight sheets, by agents
that had been given the rule in bold and told to read the code first.

The lesson is not that the agents were careless. It is that **"does this guard
repair or drop?" is not answerable by reading the guard.** Three of the misses
were reading the right function and the wrong branch:

- `agents/director.py:2846-2854` DISCARDS a channel outside the served scope
  (`dropped.append(channel); continue`). The reducer read the `outside` branch
  twenty lines below, which reports, and concluded the pair was fail-open.
- The `state_diff` unwrap at `llm/schemas.py:4583` is CONDITIONAL --
  `if ... not any(k in result for k in channels)`. A hand that puts one channel
  top-level and the rest inside the envelope gets no unwrap, and Pydantic's
  `extra='ignore'` then strips it silently. The repair covers all-or-nothing;
  the deleted sentence is what kept the mixed case rare.
- `_resolved_event_verdicts` (`director_fanout.py:761`) repairs nothing: its own
  docstring says an id outside `granted_ids` "is discarded". What repairs is
  another LLM call.

## Findings that outlive the experiment

These are properties of the engine as it ships, surfaced because someone
adversarial went looking for the floor under a prompt sentence and found none.
Each is worth its own look regardless of whether any sheet is ever reduced.

**1. A firewall property held by prompt text alone.** `_observable_predicate`
(`agents/common.py:7637`) peels leading tokens using `_identity_token_set(display)`
-- the OBSERVER's identity-gated label -- never the actor's canonical name.
Verified here by reading it: when a surface opens with the actor's real name and
the observer's gated label is an epithet, no token matches, `independent` is
True, and the sentence ships verbatim with the canonical name in it. The only
thing between that and a leak is the sheet's "do NOT start with the actor's
name" -- a model choosing to comply. `AGENTS.md` is explicit that a firewall
floor must not depend on that. This is a gap in the floor, not merely a reason
to keep the sentence.

**2. `json_object` is measured WORSE than sending no flag.** On a prose-leading
prompt the repo's own measurement is narrator 0/5 valid under
`response_format=json_object` against 2/5 with nothing set
(`llm/providers.py:2176-2195`). Since `providers_no_json_schema` holds
`google/gemini-3.8-flash` -- what every specialist inherits -- the grammar rung
never fires and the fallback is the measured-worse one. This turns design note
section 5 into a precondition: **retest the stall before any sheet is
rewritten**, because a draft that opens in prose makes the current fallback
worse, and several of these drafts do.

**3. `tell_director` never reaches a specialist.** Three deletions rested on the
engine correcting the model in-band. It cannot: `engine_notices` is read into
exactly two payloads, `director.py:1037` and `:3762`, both Director stages.
`director_fanout.py:392-535` builds the specialist payload and its docstring
states an entitlement that excludes world machinery. Any reduction reasoning
"the engine will tell it" is wrong for five of the eight sheets.

**4. The player's awareness floor is beat-wide; the cast's is per-subject.**
`_awareness_support_in_beat` (`director_floors.py:167-176`) is "deliberately not
subject-attributed" -- any sleep cue anywhere in the beat licenses gating the
player's mind -- while `_unsupported_character_awareness` (`:225-256`) is
per-subject. The weaker floor is the one on the player.

**5. `_check_prose_quote_authority` records and ships.** `director.py:4030`
detects an unauthorised quote, `:4149` retries once, `:4165` keeps the retry only
if it lowers the count; otherwise the prose stands and the violation lives in
`out["player_act_warnings"]`.

**6. Destruction can roll back the whole turn, and the objects hand cannot
satisfy its own precondition.** `destruction.txt` requires occupants to be
repositioned via `positions` or recorded in `cast_changes`;
`DirectorObjectsSpecialist` (`llm/schemas.py:2620`) owns neither.
`persist/commit_destruction.py:26-27`: a stranded occupant anywhere in the
doomed set fails the whole domain, and a domain failure rolls the turn back. One
deleted sentence was the only text reconciling that order with the hand's
channel set.

## Word lists in live prompts

The reducers were asked to flag prose word lists per `CLAUDE.md`. They found
them in quantity, including several the doctrine names as the failure class --
`contact_ops`'s 19-verb `manner` list, its nine refused placement verbs,
`substance_ops`'s ten process nouns and six kinds of matter, `entities`'s five
door states and nine light-source illustrations, `director_interpret`'s
`arrives` example sentences and its following/addressee/mover lists. Two were
flagged as legitimate and recorded as such: the five-hand table and
`inventory_ops`'s carried-in-view modes are closed sets the engine owns.

Two live CODE word lists were reported rather than edited: `director.py:1484`
`movement_cues` (12 phrases) and the 16-entry `ATTEMPT_CUES` behind
`common.py:3287`, whose own docstring records the sheet and the table
disagreeing.

## Renames worth keeping

The constructive half. A sample the skeptics did not contest:

`amount_band` -> `how_much` (same values). `contact_action_ops.action` ->
`felt_as`, which retires a paragraph plus four examples because `felt_as` cannot
be filled with an event. `portion` -> `share_taken`, `source_substance_id` ->
`from_pool`. `reactors` -> `may_respond`, because "reactor" reads as "who must
react" and 79% of multi-witness beats listed only the addressee. `tom_triggers`
-> `rethinking_someone`. "channel" -> "ledger", which the core currently spends
a paragraph defining.

One proposed rename was refuted, and it is the instructive one:
`enclosure: 'membrane'` -> `'curtained'`. `CONTAINER_ENCLOSURES` is a
four-string literal (`world/spatial_transit.py:59`) and `_open_enclosure_barrier`
compares to `'membrane'` exactly, returning `open_door` for anything else. A
better name the engine does not own is not a rename; it is a silent behaviour
change. **The naming test needs a second clause: the engine must own the new
name everywhere it is compared.**

## Should JSON go entirely? Measured, and the answer splits

Asked during the trial: drop schemas and JSON requests, use a simpler output
format. Two measurements over the same 2,004 captured responses settle it, and
they point opposite ways.

**JSON is not failing.** The syntax tax is 0.6%.

| | n | |
|---|---|---|
| parses clean, no fence, no trim | 1,991 | **99.4%** |
| needed a ``` fence stripped | 13 | 0.6% |
| needed trimming to outer braces | 0 | 0% |
| **unparseable** | **0** | **0%** |

Per role, the worst is `director_spatial` at 1.7% fenced. `director`,
`director_objects`, `narrator`, `character_major` and `story_planner` are 100%
clean. No repair-stage call appears anywhere in the capture corpus.

So the argument that JSON fails all-or-nothing and a line format degrades
gracefully is true in principle and describes a failure this engine does not
have. Dropping the format would solve nothing measured here -- and it would make
the problem it IS having worse: nine invented field names observed live are
detectable precisely because a key can be compared to a schema. In a positional
line format an invented field is a value in slot three, and nothing can tell it
from a correct one. **The invented keys are a grammar problem, not a format
problem, and the two fixes point in opposite directions.**

The 0/5-against-2/5 measurement that motivated the question is about the FLAG,
not the format: `response_format=json_object` on a prose-leading prompt. The fix
for a bad flag is to stop sending the bad flag.

**But the scaffolding cost is real, and lands somewhere unexpected.** Counting
structural punctuation plus key names against value bytes:

| role | scaffolding | per call |
|---|---|---|
| `director_objects` | 83.4% | ~38 tok |
| `director_social` | 63.2% | ~68 tok |
| `director_contact` | 62.4% | ~85 tok |
| `director_spatial` | 60.0% | ~62 tok |
| `director_body` | 57.9% | ~36 tok |
| **`director` (prose author)** | 45.2% | **~399 tok** |
| **`character_major`** | 28.9% | **~701 tok** |
| `narrator` | 4.5% | ~13 tok |

Overall, 37.9% of emitted JSON bytes are punctuation and key names.

The percentages invert the absolute numbers, and the absolute numbers are what
cost time. The specialists have the worst RATIOS and the smallest bills -- 36-85
tokens on calls that are prefill-bound anyway, so a lighter format saves them
nothing. `character_major` has the best ratio and the biggest bill: **~701
tokens of scaffolding per call**, on the one stage that is decode-bound. At its
measured rate (2,520 tokens in ~37.7s) that is roughly **ten seconds a call, or
about 11% of a 91-second turn, spent emitting braces and key names.** The prose
author is another ~400 tokens on a call that runs alone in serial.

`director_objects` at 83.4% deserves its own line: the hand whose calls are 87%
empty spends nearly all of its output naming channels in order to say they are
empty. That is not a format problem either -- it is the dispatch finding in the
design note's section 3c, wearing a different costume.

**So: keep JSON, fix the grammar, and look for the output win on the two
decode-bound stages** -- where the lever is emitting fewer keys (drop empty
channels, shorten names) rather than changing format. A lighter format is worth
revisiting only for those two, only after the grammar question is settled, and
only positionally-closed if at all.

## Where this leaves the design

Confirmed: 38% of rules are categories wearing paragraphs, 79% of the text goes,
and the coordination bucket disappears rather than shrinking.

Not confirmed: that the residue is small. 78 irreducible rules and 57
engine_drops is a far larger floor than the design's four boundaries implied, and
39 bad guard claims say the bucket a rule belongs in cannot be settled by reading
one function.

Order of work, revised by this trial:

1. **Retest the `json_schema` stall.** Now a precondition, not a preference: the
   current fallback is measured worse than nothing on prose-leading sheets.
2. **Fix the floors this trial found**, especially finding 1. They are defects
   today, independent of any reduction.
3. **Land design note section 3c** -- route on categories, delete `ledger_notes`.
   It is the one change whose evidence is a correctness argument (82%
   self-disagreement) and whose deletions are coordination, the bucket no
   skeptic defended.
4. **Only then reduce a sheet**, one at a time, with the guard for every deleted
   rule written and tested BEFORE the sentence goes -- not cited after.
