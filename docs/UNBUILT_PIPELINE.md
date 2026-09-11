# Unbuilt work — Pipeline and orchestration

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-1"></a>

### 1.1 The specialist contract: BUILT, with two parts still open

**BUILT 2026-09-10, and DELIVERING since later the same day**
(`DESIGN_SPECIALIST_CONTRACT.md` sections 4d and 4g). The Director emits one
list of categorized, numbered, annotated spans; the hands get their
scene-scoped ledgers and their work items and nothing of the beat; each record
names the chunk it resolves. A span may name SEVERAL ledger families and be
settled by several hands, each answering for its own part, and a hand is told
what the other owners of its span settle (`co_hands/<hand>.txt`, five shared
chunks per pack). `changes_asserted` is retired -- no sheet asks for it, and it
is still read so a stored variant from before the migration still reconciles.
TWO PARTS REMAIN OPEN, below.

**THIS ENTRY SAID "BUILT" WHILE NOT ONE WORK ITEM HAD EVER REACHED A HAND.**
The measurement behind it counted what the Director EMITTED -- "13 of 22 spans
carrying a category and a note" -- and nothing counted what a specialist
RECEIVED. Playing beats live found four defects in series, each hidden behind
the one in front: `norm_sequence` rebuilt every element from a key list that
never learned `category` or `note`, so the span channel died before the view
was built; the payload carried two different fields named `event_id`, so hands
cited the phase graph instead of the chronology; a citation the engine never
issued failed the whole call rather than the receipt; and the scope gates
overruled the Director on every beat, so a hand was handed a span and denied
the ledger to settle it in. Section 4g has each one, its live cost, and the
tests repinned for it. The lesson for this file: a stage's OUTPUT is not
evidence about its CONSUMER, and "built" needs a measurement taken at the far
end of the seam.

The measurements that motivated it, kept because they are what the design was
argued from: The owner's contract: a hand receives its scene-scoped slice
of world state, plus one or more dissected chunks of player/character input,
each carrying a chronological id and a natural-language note on how the
Director thinks it should resolve — and nothing else. It renders those through
its own output format, which is already built.

What happens instead, measured over 632 resolve-side specialist calls:

| the hand is sent | calls | size |
|---|---|---|
| `resolved_event` — the whole beat as prose, declared AUTHORITATIVE | 632/632 (100%) | 910 ch |
| `director_note` — what the Director asked of this hand | 311/632 (49%) | 147 ch |
| `changes_asserted` — the categorized events for this hand | 172/632 (27%) | 459 ch |

So 73% of specialist calls run on narrative alone, and the hands derive the
events themselves as a private step — which is what 90-97% of their output
tokens are spent on.

Five specific gaps, each with its measurement in the note: the dissection
(`sequence`) carries neither category nor id; categories and ids live on a
second, non-corresponding decomposition (`changes_asserted`, defined in its own
docstring as derived FROM the prose); the resolution intent exists only
per-HAND (`ledger_notes`) rather than per-event; and the chronological ids
never reach perception, where ordering is list position and `event_id` is used
only as a dedupe key.

**The Director is still asked to work out things code already knows.**
`flow.reactors` asks for "every awake character who could plausibly PERCEIVE
this beat" while perception is DETERMINISTIC and `agents/runtime.py` already
filters the answer through a presence gate -- the sheet's own text records the
model naming fewer reactors than witnesses on 79% of multi-witness beats, and
the gate's comment records six `character_major` calls at 13-22s each spent on
minds the scene placed nowhere. The paragraph is cut from 1,319 to 616 chars
(the pacing judgement is genuinely the model's); DERIVING the list is a
behaviour change to who speaks in every beat and wants its own measurement.
Same shape, unmeasured: MOVEMENT DIRECTION (996 chars, and
`world/spatial_orientation.py` owns bearing math), FOLLOWING STATE (863),
LOCATION & SYSTEM DETECTION (589). See `DESIGN_SPECIALIST_CONTRACT.md` 4f for
the table and the test each row has to pass.

**Room minting is the one exception, and the prose removal exposed it.** The
spatial hand authors a room's `desc`, name, anchors, `light` and `quiet` -- its
own sheet calls `desc` "the only durable record of how this place reads" -- and
`DESIGN_ROOM_FIDELITY.md` records it reading the Director's narration to do so
("the road run's spatial hand read the sentence and wrote `{w: 15, d: 20},
round` from it"). That input is gone as of the prose removal, correctly, and
nothing replaced it. The owner's proposal (2026-09-09) is a specialised
room-mint agent that spatial calls for a PLANNED room (Story Planner, not yet
fleshed out) or a NEW one (player declaration), taking the plan, purpose and
lore rather than a beat's narration. Not built: it is a new model role needing
its own scope, its own gate, and a measurement of current room fidelity first.
See `DESIGN_SPECIALIST_CONTRACT.md` section 6a.

**The migration order is decided (owner, 2026-09-09).** `sequence` becomes the
four-field chunk list (chunk / id / note / category) and `changes_asserted` is
deleted at the end; the endpoint-matching question is answered FIRST. It is
answered: the op carries the chunk id. `phase_sources` was the cheaper
candidate and failed on measurement -- emitted on 25% of productive calls, 68%
of `encoded` claims cited, and never once by `director_social` across 91 calls
(`tools/provenance_coverage.py`), because it is a second structure filled in
beside the work rather than a field inside it. See
`DESIGN_SPECIALIST_CONTRACT.md` sections 4a and 4b.

**THE BEAT IS NOW REASSEMBLED AND KEPT (2026-09-10).** The recompiler
(`DESIGN_SPECIALIST_CONTRACT.md` 4k) answers what happened, to whom and when
off four engine-issued identifiers, and `world/beat_ledger.py` (4m) makes the
beat's events WORLD STATE -- written at the composition rather than the commit,
expiring by beat number with nothing sweeping them, and read by perception for
the beat's chronology. Ingestion was widened to read a category in whatever
shape it arrived (4n), an unroutable span is now offered to every hand to
decline rather than reaching none (4o, on the owner's rule that "a ledger not
reaching a specialist is as good as that ledger not existing"), and a known
name is recovered from beside an unknown one (4p, `any` not `all` -- and a
stray separator no longer costs the name).

**A LONG BEAT COMPRESSES, AND THE OMISSION DETECTOR COULD NOT SEE IT.** Measured 2026-09-10 on paragraphs of
hand-counted acts, all confined to one room so movement's own backstops were
not in play:

| acts written | interpret elements | speech acts kept |
|---|---|---|
| 12 | 11 | n/a |
| 20 | 18 | 2 of 2 |
| 31 | **11** | **0 of 3** |

Twelve and twenty acts dissect near 1:1. Thirty-one collapse to eleven
compound elements -- one covers three acts, another four -- and all three
declared speech acts vanish from the typed sequence (`{'action': 11}`, where
the twenty-act beat gave `{'action': 16, 'communication': 2}`).
`_uncovered_declarations` reported ZERO uncovered for it, and the reason is
structural rather than a threshold: `_declaration_units` splits on sentence
boundaries and coordination, NOT on plain commas, so a comma-chained paragraph
is 2 units for 31 acts. The detector then asks whether each coarse unit's
significant tokens are present, and compression that KEEPS THE NOUNS while
dropping the acts passes it cleanly. Note the corpus is already deliberately
not `notes` -- coverage came from the sequence's own compressed `attempt`
strings.

**FIXED 2026-09-10, on the owner's choice of remedy, AND MEASURED BEFORE IT
SHIPPED.** `_CLAUSE_SPLIT_RE` now ends a declaration unit at a BARE COMMA. The
risk was the one the owner ruled on 2026-09-06 -- more units means more chances
to fire the bounded self-repair on an interpretation that was already complete,
the "guards that fire on valid output" class -- so it was measured across 171
stored interpret beats first:

| | before | after |
|---|---|---|
| declaration units | 261 | 311 (+19%) |
| uncovered reported | 0 | 4 |
| beats firing the repair | 0 | 2 (1.2%) |

**All four newly-reported units are real drops, not false positives**, checked
by reading each interpretation: the three speech acts of the 31-act beat, whose
sequence held none (`{'action': 11}`), and "tell her she can't hear me now" --
an input declaring two speech acts whose interpretation carried one, which is
the dramatically load-bearing line of the owner's own tardis example. 169 of
171 beats are untouched.

What this does NOT fix is the compression itself: a 31-act paragraph still
dissects to 11 compound elements, and the detector's answer to that is the
bounded self-repair, which is one model call and is capped at
`_RECONCILE_INTERPRET_MAX_UNITS` (4) units per beat -- deliberately, because
"a fully off-the-rails interpretation is better re-run than repaired unit by
unit". A beat losing more than four declarations is still losing them. Whether
the prompt should also be sharpened is the open half, and wants its own
measurement rather than being assumed from this one.

`_CLAUSE_SPLIT_RE` is per-pack, so this is an ENGLISH change; the Japanese
pattern already breaks on the Japanese comma only before a conjunction
(`、(?:そして|しかし|だが)`), which is the same gap one alphabet over, and is
covered by the standing deferral in s 1.0.

**THE RESIDUAL EDGE IN THE SPLIT RULE, named so it is not rediscovered as a
bug.** A sentence containing a bare routing word as its own delimited fragment
does split: "the belt comes off, body, and it lands" yields three parts, of
which `body` routes and two are reported as unknown names. The span reaches
the right hand and the cost is two junk entries in the unrouted report -- the
cheap direction to be wrong in, since the change is delivered. Prose in a
category field has never actually been observed: across the long-beat run's 54
categories, 49 plain strings, 5 lists, zero prose.

**AND ONE REPORTING GAP, deliberate.** `_unrouted_rulings` reads `ledger_notes`
keys and `spans`, so a change filed the older way -- as a `changes_asserted`
entry -- is DELIVERED to every hand but not reported. Delivery is the half the
owner's ruling is about, and the manifest is what spans replace when the
migration finishes.

**Open, and not to be papered over:** record-shaped channels (`poses`,
`overlays`, `conditions`, `attire`) are whole current-state records rather than
events, so there is often no chunk to attach an instruction to. `director_body`
owns four such channels and no others, which is why the manifest can never
dispatch it. That needs a second instruction shape before an event-only
pipeline is worth building.

<a id="unbuilt-1-1a"></a>

### 1.1a Conduct authority: what the guards still do not reach

**Found:** landing the character-authority guards (chat 56 t1391). The defect
they fix is closed; these are the edges they deliberately do not cover.

- **A player who declared an act is guarded only against taking hold of the
  WORLD.** `_check_player_act_authority`'s widened scope fires on a
  manipulation verb with a direct object that is neither the player's own body
  nor anything their declaration mentions. Gestures, expressions and undeclared
  movement are still unflagged on a beat where the player declared any action —
  the same "separating elaboration from addition needs more than a verb list"
  problem the character check punts on, narrowed here to the case that
  demonstrably replays into the next beat. `_MANIPULATION_STEMS` and
  `_OWN_BODY_NOUNS` are hand-built, tuned against one live chat and the
  existing suite, and their false-positive rate in live play is **unmeasured**.
  Blast radius is bounded the same way — one retry, kept only if it lowers the
  count — so a spurious flag costs a call and cannot corrupt the beat.

- **Perception has no player-ACTION scrub, and the SPEECH scrub this entry
  used to name is dead code.** Chat 56 t10's fabricated lever grip reached the
  player's view as "I grip the console edge" with nothing between the Director
  and the narrator, and the Director-side guard is still the only thing
  standing there. `common._scrub_undeclared_player_speech` has **no production
  caller** (verified 2026-08-19: `agents/perception.py` imports it and calls it
  nowhere; only tests and `tools/perception_quality.py` reach it), because
  perception stopped asking a model to write views —
  `tests/test_perception_has_no_model.py` pins that. So the second independent
  floor this bullet used to ask for cannot be built the way it described: a
  player-action check would sit where `_composer_tripwires` does, on the
  composed view, and it would be a defect DETECTOR rather than a scrubber —
  which is the right shape, since a fabricated act in a composed view is an
  engine defect and scrubbing it would hide the bug instead of the leak.

- **A character who declared a non-locomotive act is guarded only against
  MOVEMENT.** Handing something over, drawing a weapon, striking — additions
  that are not movement — are still unflagged for a character who declared
  any act at all. This is the same "separating elaboration from addition
  needs more than a verb list" problem the player check punted on, and it is
  punted on here for the same reason. Movement was carved out because
  distance decides what perception delivers and what contact is possible, so
  getting it wrong has consequences beyond the sentence.

- **`_check_prose_quote_authority` ignores quoted spans under three words.**
  A readout reading `"STABLE"` and the word `"safe"` in scare quotes are not
  utterances, and there is no way to tell them from a genuinely invented
  `"Run."` without reading the sentence around them. Short fabricated lines
  survive; the speech check catches them only if an attribution verb is
  present.

- **All of it is prose matching**, with everything §3.1 says about that.

<a id="unbuilt-1-7"></a>

### 1.7 JSON validation stalls cost beats

A model answering with a shape the schema does not admit costs the whole beat:
in a story it is a character who simply did nothing. Six-plus across one
experiment arm, then twice in eleven live turns on 2026-07-30.

**Every shape measured has been closed** — a `sequence` of bare sentences
(`_sequence_event_from_prose` reads such an entry as an ACTION unless the whole
string is a quotation, the safe reading rather than the likely one: typing
prose as speech would author an utterance AND transmit it to everyone in
earshot), the whole answer wrapped in one key of the model's own
(`_unwrap_envelope`), a staged lore `content` that was an object, and a
condition written as its own description. `_name_what_was_discarded` names what
was dropped for whatever still cannot be read, and the character step does have
a bounded schema-repair path (`agents/character.py` → `agents/common.py` →
`llm/llm_quality.complete_validated_json`).

**What remains open is the mixed sentence.** `Says, "Nobody leaves this room."`
keeps every word in its attempt text and is typed as an act, so a character in
the room may not receive it through the dialogue channel. Pinned as intended at
`tests/test_schema_leniency.py`. Deciding it needs the hearing path looked at,
not a better regex.

<a id="unbuilt-1-11"></a>

### 1.11 `ctx.warnings` reaches the pipeline drawer but not the story reader

**Landed, alpha 6.9**, except for an aggregate reader. Every warning is tagged
with the step that raised it (`pipeline_context.StepTaggedWarnings`, keyed off a
contextvar set in `compute_step`), persisted onto that step's saved content
under `_engine_notes`, and rendered above the step in the pipeline drawer
(`static/js/chat.js`). The tagging lives in the list rather than at the ~40 call
sites, so both spellings are caught including ones not written yet.

Why it was worth landing, on the record: perception dropped both sight sentences
out of a character's view of an embrace happening six feet in front of him (chat
38, turn idx 140), warned about it twice, and the warnings went nowhere. What
survived into his memory of that beat was a sound.

**Residual, and it is a roadmap wish rather than a defect:** there is no
aggregate view — no way to ask "which turns in this story had a view repaired",
which is the question that would have caught those six turns earlier. A warning
during a live run also still passes silently; only the persisted record shows
it.

<a id="unbuilt-1-11a"></a>

### 1.11a Pacing still decides who may ANSWER, and that half is unmeasured

**The perception half landed 2026-08-19.** `perception_act` builds a perceiver
for every cast body the scene places somewhere (`_present_cast_bodies`), not
only for `flow.reactors`. Being in the room is what decides whether you saw it.
Free: perception makes no model call, and `agents/loops.py` reads
`flow.reactors` for itself, so who speaks and what the beat costs are unchanged.
Measured before: a witness was missing from `reactors` in 757 of 975
multi-witness beats (77.6%), and 1,639 of 4,292 character-presences (38.2%) got
no act view at all.

**The complementary narrowing landed 2026-08-28.** The perception fix widened
perception to match presence and left the reactor list ungated, so the two
disagreed inside a single beat: a mind the scene places NOWHERE gets no view
and was still asked to declare conduct. Chat 95, turns 4/5/8/14 —
`flow.reactors` named two cast members `scene.positions` had no entry for at
any point, in beats whose own `perception_act.views` listed observers `['75']`
/ `['74','75']`; 6 `character_major` calls at 13-22s each, every one
deliberating from an empty perception base. All four readers of the list now
intersect it with `_present_cast_bodies` (moved to `agents/common.py` for the
purpose): `runtime.build_plan`, `loops._drop_absent` in both loops, and the
`character.character_step` choke point, which says so the way the awareness
gate beside it does. SOMEWHERE, not "the player's room" — a mind answering
over a comm channel from another room passes. Pinned by
`tests/test_reactors_are_narrowed_to_presence.py`. The drop is silent in
`build_plan` alone, because that planner also runs from `resume_key_for_turn`
under a web handler with no step to note against — so an autonomy-0,
uncontested beat, which plans per-character steps and enters no loop, drops
without a note.

What stays open is the half the Director legitimately owns. `flow.reactors` is
a pacing judgement — who speaks this beat — and its quality is still unmeasured:
nothing checks that the people it picks are the people a reader would expect to
answer, and the prompt sharpening in alpha 6.9 moved the perception number
without anyone establishing what the pacing number should be. A beat where the
addressed party is left out is now a pacing defect only, which is the right
shape for it, and it is the one worth measuring next.

Separately open: whether a cast member the scene places nowhere is a PACING
defect at all, or a COMMIT defect — the narrowing drops them from the beat;
having commit place every active cast member is the other half and is not in
this cluster.

<a id="unbuilt-1-13"></a>

### 1.13 `ActionStage` is classified and the resolve path never reads it

`schemas.ActionStage` (`immediate|preparation|approach|contact|sustained`) is
filled in by `director_interpret` on every action element and read, on the
resolve path, by **nothing**. Its only consumer anywhere is
`agents/common._requires_reaction_phase`. So the interpret has been correctly
classifying "this act has not landed yet" since the beginning, to no effect —
which is what let the blizzard beat resolve an approach as an arrival
(`Design.md`, "Approach is not arrival"; the fix routes around `stage` via
`MovementDecl.arrives` rather than through it).

Two things follow, neither done:

- **The other unlanded stages have no consequence either.** `preparation` means
  the act is setup, not the thing; the live corpus has 8 of them, 2 with an
  `inventory_ops` in the same beat. `initiation` appears 9 times and **is not a
  member of the enum at all** — the model invents it and it passes validation
  untouched, so any guard keying on the declared values silently misses those
  beats. Either the enum is enforced or it is not a closed set. Re-verified
  2026-07-31, now with the mechanism: a direct `ActionElement(stage=
  "initiation")` DOES raise, so the enum is real — but
  `validate_llm_output("director_interpret", …)` returns the element with
  `stage: "initiation"` intact and **no errors**. The closed set is enforced
  nowhere the pipeline actually passes through. Settle it at that seam.
- **`sustained` is the interesting one and the least safe to act on.** 250 live
  beats are staged sustained, 128 of which move somebody, 62 open a contact and
  53 mint a condition — and most of those are correct, because a sustained act
  is ONGOING rather than unfinished. Anything that treats sustained as
  "not landed" will be wrong most of the time. What is missing is the
  distinction between an act that continues and an act that has not yet
  completed, and the schema does not carry it.

<a id="unbuilt-1-32"></a>

### 1.32 A region assertion has an owner only by slot position

`spatial.owned_region` now makes a region UNAMBIGUOUS: `(who, where)`, so no
comparison can collapse one body's mouth into another's. It cannot make an
assertion TRUE. A slot's position is what names its owner, so a mis-slotted
`{target: Hinami, target_part: glans}` still yields a well-formed token.

A check derived from the scene's own history was built and measured against
every stored beat, each turn judged against its own pre-beat checkpoint:

    contacts     70 fires / 2,036 assertions
    substances    2 fires /    30 assertions
    true positives: 1

The false positives are ordinary anatomy — hand, waist, chest, mouth, lips —
whose first mention in a story happened to be the other body, and the rule
deadlocks: a common region asserted first on body A can never afterwards be
asserted on body B, because every attempt is cleared before it can become
evidence. It is also self-poisoning. Turn 62 of the reference story flags
`glans` on the wrong body (the true positive); turn 64 flags it on the RIGHT
body, because turn 62's own error had by then become the scene's belief. One
wrong assertion inverts the check for everything after — the exact failure
mode the investigation started from. Removed in `a851ea0`, numbers recorded in
place.

**Direction: the owner must be ASSERTED, not derived.** An owner qualifier on
the region slot, so the Director says whose mouth it is rather than the engine
inferring it. Schema plus prompt. This is what would actually close turn 62,
and it is the only route left that does not require an anatomy model.

<a id="unbuilt-1-33"></a>

### 1.33 An interpret that says nothing costs two model calls

Measured on a 51-beat authored playthrough: 42 of 50 final interprets carried
a degenerate sequence element — `attempt: "waits"`, `observable: "waits"`,
empty `verb`, no targets, no effects — for inputs as plain as *"I draw the
sword."* `interpret_repair` fired 25/50, reported `repaired=True` 25/25, and
left `unresolved` 25/25: its output was a byte-identical `waits` element,
because the repair sets `repaired` merely on the list being non-empty. The
deterministic re-check then still failed, which forced `mapping_stage` on all
25 (correlation exactly 1:1 with the clean turns running `mapping_quick`).

So half those turns paid two sequential model calls that produced nothing, and
— the part that is not about latency — **the player's declared act was dropped
from causality on those beats.**

Config-specific: across 1,886 interprets in the live corpus the repair fires
11.8% overall, 6.0% over the last 100 turns, and genuinely changes output
54–71% of the time. `"waits"` appears nowhere in engine source, so it is
model-emitted, plausibly `llm_quality`'s repair minimally satisfying the schema
after a primary call returned `{}`.

Two additive fixes, neither removing a stage: treat a sequence whose only
element has an empty `verb` and no targets or effects as a validation failure,
so the existing same-call repair fixes it before `_reconcile_interpretation`
runs; and make `recon["repaired"]` require the re-check to actually pass, so
the metric stops reporting 100% success on a 0% success rate.

<a id="unbuilt-1-49"></a>

### 1.49 Three things the prompt-card split made visible and did not change

The 2026-08-29 split moved every prompt leaf out of
`cards/system_prompts.json` into per-prompt `.txt` files
(`language_runtime/card_source.py`). Byte identity was the acceptance
criterion and it holds, so all three of these SHIPPED UNCHANGED. They were
invisible inside an escaped 414 KB JSON string and are obvious in a file, and
each is a judgement about prompt text rather than a refactor's business.

**The one glued join among 31 specialist joins.**
`specialists/body/chunks/conditions.txt` ends `"…and end what has ended."`
with no terminator of its own, and `vitals` follows it in `body`'s `order`.
A specialist sheet is `core + "".join(chunks in order)` with no separator, so
the shipped English sheet reads `…has ended.BODILY CONDITION (only when…` —
one sentence running into the next section header with no break at all. Every
other one of the 31 joins carries its own terminator. Whether the model reads
past it is unmeasured; the fix is one newline and a ledger line in
`tests/data/prompt_cards_presplit/EXPECTED_DIVERGENCE.json`.

**Two prose-author segments joined by a single trailing space.**
`prose_author_sheet/20_world_pressure.txt` ends `"…an unrelated invention. "`
and segment 21 begins `"WORLD PRESSURE — OPENING:"`, so the assembled sheet
runs them together on one line. Same shape as above, same one-character fix,
and now protected in the other direction: that space is load-bearing enough
that `.editorconfig` disables trailing-whitespace trimming for these files and
`test_assembled_card_matches_the_pre_split_reference` fails if it disappears.
(`prose_author_sheet/16.txt` is a single newline and nothing else — the same
class, but there the whitespace is doing the job correctly.)

**Nothing checks that a `character_block_keys` marker still prefixes a line of
the `character` body.** The 22 markers are matched with
`stripped.startswith(marker)` against lines of `prompts/character.txt`
(`llm/prompts.character_prompt`), and the match is what SUBTRACTS a block a
character has no business receiving. Editing a heading in the body — now an
easy, inviting edit, which is the point of the split — silently disarms its
subtraction: no error, no warning, no failing test, just a block that stops
being removed. The two files are deliberately kept in one place (the markers
stayed inline in the index) precisely because the coupling is silent, but
that is mitigation, not a check. A `project_check` rule asserting every marker
prefixes some line of the body is cheap and is not written.

<a id="unbuilt-1-59"></a>

### 1.59 A channel census over persisted `state_diff`s cannot see `phase_sources`

**Measured 2026-08-25**, deconstraint branch. A census of all 28 `state_diff`
channels over 2,723 resolved turns reported `phase_sources` as **never used,
not once** — and the census is structurally blind to it, not reporting a fact.
`agents/director.py:3903` pops the key IN PLACE out of `out["state_diff"]`
before the resolve step row is written, exactly as its docstring says
("consumed before persistence"), so **a persisted `state_diff` cannot carry
it**. Where it CAN be seen — `director_interpret.state_assertions` — it fires
23 times in the same corpus.

It is asked for unconditionally in `language_packs/en/prompt_policy.json` for
all six specialists and `director_resolve_lean`, and read by
`agents/common.py:485` `prune_blocked_phase_changes` at
`agents/director.py:780` and `:3903`. It is a live causal floor. Recorded here
because a later reader who repeats the census and trusts it will delete a
working one on "0 uses" evidence.

The same caution, weaker, covers `contradicted_claims` (asked for, 725 stored
diffs carry the key, 0 non-empty) and `ratified_claims` (1,876 present, 1
non-empty): both gate on `unratified_claims_present`, and
`agents/director_scopes.py`'s `_CHANNEL_GATES` granted that scope **0 times in
1,346 orchestrated Director stages**. They have not had a fair measurement yet;
§1.30 is the entry that owns them.

<a id="unbuilt-1-60"></a>

### 1.60 The interpret sheet and `agents/common.py` state opposite rules about concealed speech

**Found 2026-08-25**, deconstraint branch, in passing; NOT fixed here because
it is a concealment path and either direction is a firewall decision.

`prompts.director_interpret` says: *"Concealing the surrounding action
(stepping aside, opening a channel) does NOT by itself hide what is said — the
speech element itself needs its own visibility/conceal_from."*
`agents/common.py:2936-2955` does the opposite: it propagates a concealed
action's `conceal_from` onto every speech element not explicitly
`overt`/loud/shout, on the stated grounds that weak models mark the ACTION
concealed and leave the speech bare.

Both behaviours are defensible; they cannot both be the rule. A model told the
opposite of what the engine does will mis-set the field in whichever direction
it believes, and the prompt is what decides which. Settle it, then make the
loser follow the winner — do not leave the sheet arguing with the code.

<a id="unbuilt-1-69"></a>

### 1.69 Three other sentence splitters still have no abbreviations

**Landed on 2026-08-19 for the three splitters in `agents/`.**
`common.split_sentences` rejoins a fragment whose predecessor ends in a
`_SENTENCE_ABBREVIATIONS` token (language-pack data, because "a period may end
an abbreviation" is a fact about a writing system), and `_sentence_subjects`,
the perception redactor and the two narration fidelity checks all route through
it. `_subject_opener` gained the matching admission: a title standing
immediately before a name opens that name's sentence.

**Still splitting on a bare period, and there are THREE, not four** (title
corrected 2026-08-19; the body always said three): `common._VIEW_SENTENCE_SPLIT_RE`
(the view deduper — a different contract, its split keeps the separators
interleaved), `dressing/backdrops.py` and `tools/perception_retrieval.py`. **None
of them decides what a mind receives**, so none can produce the chat 82 failure;
they can only mis-count a sentence. Watch item, not a defect.

The token set is deliberately not every abbreviation — "etc." and "Ph.D."
genuinely end sentences, and rejoining there welds two real ones together. It
holds the class that essentially never ends a sentence and does routinely
precede a NAME, which is the shape that made the split damaging.

<a id="unbuilt-1-70"></a>

### 1.70 Narrator repetition: what the change-key fix reached, and what it did not

Landed 2026-08-28, from a 16-turn story (chat 95) whose every stage was read
against the others. Three reported symptoms — an ambient closer the prose kept
ending on, a re-declared smell, and two quotes welded into one span — were one
mechanism with three feeder sites, all upstream of the narrator: a percept the
engine calls `changed` becomes a numbered entry in `current_events`, and the
sheet defines that list as obligation ("every entry in it happened and must
reach the page"). The narrator writing a sentence about it is obedience.

**Fixed at the origin.** A standing percept's change key now hashes the STATE
it describes rather than the sentence composed from it
(`composer.room_content_percepts`, with the state published by
`common.crowds_for_room`), and no longer hashes a fact about the observer's
recognition of the owner (`composer.scent_percepts` drops `label`). Both bump
the key TAG, so a ledger written before the change reads as first sight rather
than as a claim that something moved. `observations_from_render` no longer
welds one mouth's consecutive lines into one numbered entry, and the atom cap
that now pays for that prices the pair it is about to weld — wallpaper, then
two silent events, then a silent event into a spoken one, then one mouth's two
deliveries, then the obligation boundary, then two mouths last.

**The middle of that order was wrong until 2026-08-29.** A same-mouth speech
weld was priced BELOW every other event pair, so the cap reached first for the
one shape the merge loop above deliberately refuses to mint. Measured, chat 98
turn 29: nine legitimate atoms against a cap of eight, the cap folded Picard's
first two lines into a single entry, and the page carried both quotes back to
back with no attribution or beat between them — the worst dialogue sample in
that run. Folding a SILENT atom into a spoken one cannot produce that shape,
because the entry still holds one quote; it costs the channel (the group
degrades to `mixed`) and the attribution, both of which the loop already
spends there.

**Still open: the cap itself.** `composer._MAX_OBSERVATION_ATOMS` is 8 and is
untouched — turn 29 delivered nine atoms a mind legitimately received, so SOME
boundary was going to be spent whatever the ordering, and the reorder only
chooses the cheapest one. Raising it trades narrator payload size against how
often any boundary is spent at all, which is the owner's call rather than the
workflow's.

**Not fixed: the `act_player` obligation marker asserts something false.**
`{n}. {actor} did this (NOT yet on the page — the player described attempting
it; you must render it happening)` is attached to an entry whose material is
verbatim one payload key away, in `current_narration`. The comment at
`narration.py:1141` records why the marker was added and is honest: it was
measured when the player's input was buried at the tail of `past_narration`,
and it took acts on the page from 5-in-12 to 7-of-9. `current_narration` has
since been split into its own key placed immediately before `current_events`,
so the two now say opposite things one line apart, and the model resolves the
contradiction by writing the beat again — chat 95 turn 8, three `onset`
surfaces, three paragraphs of replay with one of the player's own clauses
surviving verbatim. The fix is to state the entry as the ADJUDICATED OUTCOME
of what the player attempted (which is what earns it a number) instead of as a
claim about the page. It is not landed because the marker's power is a
MEASURED number and the only instrument that measures it is
`tools/narrator_package_bench.py`, which spends real model calls; and this
repo has been burned before by a marker that lost its force when reworded on
reasoning alone. Whoever runs the bench should move
`language_packs/en/cards/linguistics.json` `_EVENT_LINES.act_player` and the
three assertions in `tests/test_narrator_world_fidelity.py` (~1030, ~1106,
~1193) together, keeping the absence assertions at ~1237/1250.

**Three calls left to the owner.**
  * *Whether an ambient percept may enter the beat half at all.*
    `leads_the_beat` refusing `kind == "ambient"` outright is smaller and more
    certain than getting every state key right, and it would also cover
    couriers and notices, which publish no state to key on. It costs the
    ability to announce a crowd change as it happens.
  * *The derived crowd's composition is deliberately not in its state key.*
    `charter_crowd.composition_of` is a top-two-of-tally recomputed at every
    read over a membership that walks its errands, so it reorders without the
    crowd changing (chat 95: five spellings of one unchanged fact in sixteen
    turns; a sorted set of the nouns still flips four times). The band carries
    a real change instead. What this gives up: a crowd whose composition
    genuinely turns over while its band holds now re-renders only when
    something else about it moves.
  * *Whether `_overused_phrases` should read the PAYLOAD as well as recent
    prose.* Today it is computed from the narrator's own last four prose
    blocks, so an engine-supplied tic can be banned only after the narrator
    has written it twice, and the ban then argues against a payload that keeps
    re-supplying the material — measured: "held its pitch" was on the ban list
    at turns 7, 8 and 9 and the closer kept coming, and
    `already_established_phrases` fired on 1 of 19 narrator calls in the whole
    story. Pointing the ban list at engine-authored labels the narrator is
    REQUIRED to be able to use is the shape of guard this repo has measured
    failing, which is why it was not pursued.

<a id="unbuilt-1-73"></a>

### 1.73 The chronological-padding brake stops the inner loop only

Found 2026-08-20 by adversarial verification of the memory-probe harness.
`search_memories` pads its selection with chronological neighbours of the top
3 selected episodes, documented (MEMORY.md §5, and the in-code intent) as "up
to k+2 total" — but the `len(expanded) >= k + 2` brake sits inside the inner
neighbour-pair loop and never breaks the outer `selected[:3]` loop, so the
payload can reach k+6; k+4 was observed live on both measured banks. Present
since before the 2026-08 retrieval work (equal at the frozen-probe baseline),
and measured as deciding nothing: zero probe verdicts on any bank in any
state came via padding rows. Not fixed in the branch that found it because
shrinking payloads is a retrieval behaviour change that needs its own probe
run; the fix is moving the brake to the outer loop (or checking it before
each append) and re-measuring with `tools/memory_probe_harness.py`.

<a id="unbuilt-1-77a"></a>

### 1.77a Speaking turns and the page: what the utterance fix reached, and what it did not

Landed 2026-08-29 from the 40-turn bridge run (chat 98), every stage of the
cited turns read against the others.

**Fixed at the origin.** One mouth's consecutive spoken lines with no conduct
between them are now ONE utterance, fused deterministically in the character
stage (`common.fuse_speech_run`, called from `character.character_step` after
`norm_sequence` and before the event ids are stamped). The speech budget's own
contract already said this -- it defines a line as "one separate beat of talk,
delivered between other conduct" and states that "multiple lines are not one
speech split by punctuation" -- and nothing enforced it, so a three-element
round became three `dialogue_log` entries, three `speech_percept`s, three
"X says in a Y voice: ..." sentences in every view, and three quoted lines set
back to back on the page. Measured over the run's 85 stored rounds: 79 speech
elements become 51, 26 rounds fuse, and the speaker-beats carrying two or more
quoted lines halve (24 -> 12). Turn 29's worst case, six quoted lines from one
mouth in one beat, becomes two. The fuse SUBTRACTS -- no word is added or
dropped -- and it refuses to cross any delivery difference (volume,
visibility, conceal_from, targets, phase) or a line that claims an
interruption, so a whispered aside inside a spoken turn keeps its boundary.
A run that changed register loses its tone adverbial, because no single one is
true of it.

**Also fixed: a Python list repr in every character's composed view.**
`perception_outcome` handed `delivered_views[observer]` -- a LIST of rendered
lines -- to `composer.micro_round_percept`, which takes one line and calls
`str()` on it. Measured: 68 of the 142 stored character views in chat 98
carry a `['...']` span, on 24 of the 38 turns, and from there it reached the
observations projected off the view and the episode minted from it. The
composer's own dialogue tripwire caught four of them, said "engine defect,
view delivered as composed", and the view shipped anyway.
`composer.micro_round_percepts` now names the shape: a delivery is one line, a
round delivers several.

**Also fixed: the narrator was never told what the player was wearing.**
`attire_exposure_facts` was computed for the deterministic screen only, and
that screen asks one question -- is a COVERED region narrated bare. It has
nothing to say about a garment asserted onto a body whose ledger does not
carry it, which is the other half of the same disagreement (chat 98 t27, "her
uniform sleeve" against a ledger reading combadge + civilian clothing). The
narrator payload now carries `player_attire`, the ledger's own compact line
for the player's own body, and the sheet says the ledger owns it. This widens
nothing: a mind has a channel to its own clothing, which is the ground
`attire_exposure_facts` already stood on. Every other body's dress still
reaches the narrator only through the composed view, behind perception's gate.

**Not fixed, and it is an OWNER'S FORK: a second round restates instead of
advancing.** The register (`D-B`, reopened three times) hypothesised that the
mind was not being told what it had already said. It is: `_speak` writes the
accumulated `interaction_views[speaker_id]` before every call, and the
speaker's own conduct is appended to it in the same place as everyone else's.
CAUTION for the next reader -- the `self_view` key stored on a round record is
that round's OWN emission, captured after the call for `rehydrate_loop_views`
to replay; it is NOT the record handed to that round. Reading it as the input
makes the ledger look correct-and-ignored in a way that happens to be true for
a different reason.

What remains is a genuine restatement across an exchange boundary: chat 98
turn 29, Picard says "the sudden appearance after a clean survey eleven years
prior", Data answers, and Picard says "the sudden activation after a clean
survey eleven years prior". Both are separate rounds with another mouth
between them, so the fuse correctly leaves them two deliveries, and they are
paraphrases rather than repeats, so no literal guard reaches them. The
cross-turn case (t32 -> t33, verbatim identical) IS detected --
`repeat_correction` fired on t33 by name -- and the engine deliberately does
not re-ask, on the owner's stated rule and against measured evidence that the
retry only rephrases. So the remaining fork is the owner's:

  * *Drop the round.* The register's own hypothesis: a round is granted and
    the mind is asked what it says, never whether anything remains to be said.
    But the grant at t29 is CORRECT by every other measure -- Data answered
    the captain and expects a response -- so dropping it lands the answer in
    silence. Any rule that drops it has to be able to tell "nothing left to
    add" from "the exchange is still going", and nothing deterministic can.
  * *Ask the second round a different question.* Tell a mind that has already
    held the floor this beat that a further turn is for what the exchange has
    newly raised, and that saying nothing is a complete answer. That is a
    prompt change on a path where three separate negative constraints
    (`recent_self_lines`, the refrain skeleton, `repeat_correction`) have
    already been measured failing, for the reason `character.py` states at
    length: a negative constraint helps a mind that has another move and does
    nothing for one that does not.
  * *Accept it.* The trade-off the no-re-ask rule already accepts, one scope
    wider.

Not guessed at here, because the choice is between two of the owner's own
standing rulings.

**Also corrected, for the register rather than the code.** `D-C` ("the
narrator restates the player's own completed beat", turn 4) is not a narrator
defect. The turn-4 player view OPENS with "Jean-Luc Picard accepts padd from
you", because Picard's own round declared the act -- and he declared it
because the turn-3 transfer never committed (`D-A`). Director, perception and
narrator all carried it faithfully. Fixing it in the narrator would have
buried the commit defect.

<a id="unbuilt-1-82"></a>

### 1.82 Two narrator checks that fire and buy nothing

**Found:** the same day, adding them.

`_check_speech_marking` and `_check_attire_fidelity` score the page against
records the payload was already entitled to, and both ship as plain warnings
-- not in `_ENFORCEABLE_PREFIXES`, so neither buys a correction rewrite.

That is the right default and not the right resting place. Promotion is a
MEASUREMENT: 0fec229 measured the reuse check being fooled 4 of 5 times by the
attribution label, and demoted the ordering check on exactly that evidence.
Each enforceable firing costs a whole narrator call, so the question for both
is their false-positive rate over a live run, and nobody has counted yet.

<a id="unbuilt-1-101"></a>

### 1.101 A handover the scene has no record of is refused out loud, and still refused

**Found:** the Enterprise-D alpha-shift run (chat 98), turns 4 and 22.
**Half fixed 2026-08-29.** What landed: the possession claim a body's pose
prose was making no longer outlives the transfer, and the refusal is no longer
silent. What is still open is one decision the owner has not made.

The measured chain. The establishing beat minted no `entities` record for the
object the whole opening was about; its entire existence in the engine was one
line of pose prose, `poses["<a body>"]["detail"] = "holding <it> against
chest"`. Four beats later the Director resolved a complete, well-formed
transfer of it to another body. `derive_inventory_placements` placed nothing —
correctly; you cannot position a thing the scene does not know — and said
nothing, which was the defect. The pose detail was reconciled against no
possession record at all, so it stood: five beats after she let go, the
giver's own composed view still read "... — holding <it> against chest", in
the interoception channel and in every other observer's sight line, and the
narrator wrote it into the prose twice. Reading only the narrator misattributes
this; the narrator was being told.

Two of the three halves are closed:
  * `invalidate_transferred_pose_details` (`world/spatial_geometry.py`) retires
    a pose `detail`'s carriage clause when the transfer ledger says the thing
    left that body. The `detail` alone — posture, support and the relation
    fields are the body's own and no transfer touches them.
  * `derive_inventory_placements` now takes a `report` and writes a
    Director-facing sentence naming the thing it could not place, carried to
    the next beat through `engine_notices` the way `crossing_report` is.

**THE OPEN DECISION, and it is the owner's: should a transfer op MINT an entity
for an object the scene has not established?** The argument against is the one
this pass already makes everywhere else — it holds an id a model reached for
and nothing else, no name, no kind, no size, and a stub keyed on that token
would bind every later op to a record with nothing in it (a minted entity key
has already reached an `attire` remove as a garment handle once). The argument
for is the measurement: re-merging every stored (scene, diff) pair on disk —
2758 of them — a transfer names an object with no entity record on **26
beats**, across seven chats and seven different things. Every one of those
handovers is a possession fact the engine resolved and then did not write down
anywhere. The notice makes them audible and leaves the minting to a Director
that may or may not act on it; nothing yet measures whether it does.

Until that is settled, the giver has let go and nobody is recorded holding it.

**The other half of the class landed 2026-09-03: a handover to somebody the
scene has no record of.** Harrowmere t5 (the 2026-09-02 playtest): the thing
was known, the HOLDER was not -- `to_id: "reeve_halinham"` named a Charter body
with no entity and no position -- and `derive_inventory_placements` fell
through that case without even the notice above, so the letter the reeve took
in prose stayed on the player for thirty-five beats. The commit now passes the
bodies the town stands in the scene's rooms into the merge
(`charter_runtime.charter_carriers` -> `merge_scene_with_diff(carriers=)`);
the record lands marked `by: "charter"`, survives hygiene on that mark, and is
re-derived into the holder's current room every merge. An unresolvable
destination is now reported in the same voice as an unrecorded thing.

**The replay on merged main (2026-09-03) found the fact still stuck, through
two doors the op path did not cover.** The t5 handover reached the merge as a
CONTAINMENT record from the contact hand ("Reeve of Harrowmere Brgaron
Brfordwick takes hold of sealed letter"), not as an op; the reeve had no
entity, so `normalize_scene_containment` dropped the record as an unknown
holder and the letter lay loose in the hall for thirty-four beats. And the
player's worn satchel -- a garment in her wardrobe ledger and a container
entity in the scene, so the letter could sit in it -- had a position of its
own that nothing tied to her: it stayed at the hall from t3 to t26 while she
slept at the inn. Both closed at the merge: hygiene keeps a record naming a
holder the town stands, on the same `by: "charter"` mark
(`normalize_scene_containment(carriers=)`), and `derive_worn_containment`
ties a worn garment entity to its wearer every merge (`by: "attire"`,
retired when the garment leaves the wardrobe, yielding to any carriage a
hand declared). The objects chunk now says the carriage is the hand's to
write, including what a body arrives carrying. `tests/test_carried_follows_
wearer.py`.

Still open: the record follows the holder only into rooms the scene knows
(a body who walks off the map takes the thing off it, and it reappears where
the map resumes); a merge that does not pass `carriers` (`world/paradox.py`)
keeps the last room rather than following; a thing said to be INSIDE a worn
container at the opening ("the letter in my satchel") is tied to the
container only if a hand wrote the op or the record -- the wardrobe
derivation reaches the garment, not its contents; and `_MAX_CONTAINED` (40)
now counts derived garment records beside declared ones, which a story
minting many garments as entities could feel.

<a id="unbuilt-1-112"></a>

### 1.112 The process clamp reads a generic word in a clothing sentence

**Measured live 2026-08-29, chat 98 turns 40 and 41, twice in two turns.**

`attire._process_sentence` requires a sentence to be about clothing before it
reads process language as evidence about clothing — the fix for chat 70 t9,
where a sentence about hands clamped a removal. The other half is still open:
a sentence that IS about clothing and ALSO contains a generic process word
about something else.

    "...because alpha shift started in forty minutes she put the duty
     uniform back on"

`started` is `_PROCESS`; `uniform` is `_CLOTHING_CONTEXT`; the removal of the
civilian clothes was held at `loosened` on a beat that completed it. The
second case is the Director's own "She begins removing..." for a beat whose
narration takes four garments off, which held all four.

Failure direction is the safe one — a removal held one beat, restated the
next — so this is a pacing defect, not a state fork. The shape of a fix is the
same one `_CLOTHING_CONTEXT` already has: the process word and the clothing
word have to be about the same thing, which sentence-level co-occurrence does
not establish.

**Narrowed, not closed, 2026-08-29.** The clamp is now scoped to the GARMENTS
a process sentence names rather than to the body wearing them
(`attire.process_targets_by_garment`, `attire._attributed_scoped`), so the
second case above is smaller: "She begins removing her jacket" holds the
jacket and lets the other three land. What survives is the first case
verbatim — a sentence that names one garment and carries a process word about
something else still holds THAT garment — and the wholly unattributed shape,
"She begins removing her clothes", which names no garment and so still holds
everything the body has on. The fix's shape is unchanged: the process word and
the garment have to be about the same act, which co-occurrence in one sentence
does not establish.

<a id="unbuilt-1-119"></a>

### 1.119 The declared room word against the sources: two owner decisions the PA3 repair did not take

**Found 2026-09-05**, fixing PA3 (`docs/experiments/PLAY_2026_09_05_lighthouse.md`).
The declared word and the sources are two accounts of one fact, and the
repair let the sources correct the word in ONE case only: an `enclosed` room
that holds room-filling fixtures with every one of them switched off takes
the sources' answer (`spatial_light_field.ambient_floor_word`). Two questions
were deliberately left for the owner, because either answer changes every
story and the measured case does not decide them. The first was answered by
the F40 ruling the same day and is kept here for the reasoning; the second
is open.

* **Should a declared word ever outrank the sources OUTDOORS? ANSWERED
  2026-09-05** by the F40 ruling (`experiments/DEBUG_RUN_2026_09_05.md`),
  and the answer is: where there are no sources. A `sheltered` room whose
  declared word stands above what the sky gives it and which holds no light
  source of its own keeps its word, because the declaration is then the only
  thing that knows about the lamp nobody wrote as an entity; a `sheltered`
  room that HOLDS sources is decided by them, so the market hall with its
  braziers out is dark at midnight, exactly as this bullet's own test case
  asked; and an `open` room is untouched, because there is no roof to hide a
  source under. The two rules are now one rule read from both ends --
  `ambient_floor_word` lets dead fixtures darken an enclosed room's word,
  `room_light` lets a word stand where no fixture exists to speak.
* **Should the floor hold for `dim`? ANSWERED 2026-09-05 — no exemption**,
  and the answer to confirm is that `dim` is not special. Today it yields for
  any word above `dark`, so an enclosed room declared `dim` with its one dead
  sconce in it reads `dark`. The argument for exempting `dim` was that `dim`
  is the word an author reaches for when a room has SOME light from nowhere
  in particular -- a grate, a gap under a door, a window nobody minted -- and
  taking it to zero makes the room unnavigable for a reason the reader cannot
  see. That case is already answered one branch over and does not need an
  exemption to answer it: a room with NO fixture in it keeps its word
  entirely (`_room_fixtures` is empty, `ambient_floor_word` returns the
  declaration), which is exactly the "light from nowhere in particular" case
  and the whole of it. What is left for the exemption to cover is a room
  whose fixture was WRITTEN and is out — and there the sources are an
  account, the account that exists decides, and exempting `dim` would be the
  same lie the `bright` case was, one rung down. So the two rules stay one
  rule read from both ends, with no rung carved out of either.

  The pressure that produced this bullet has been relieved from the other
  end instead: `unsourced_light_rooms` now asks the Director for the source
  of EVERY room whose word nothing accounts for, indoors included (PQ1 / PR6
  / PX7, 2026-09-05), so the grate nobody minted is a thing the engine says
  out loud every beat until it exists, rather than a case the floor has to
  guess at.

F50 (`DEBUG_RUN_2026_09_05.md`) is the third of the family and is untouched:
a LIT source still cannot quantise below its room's declared floor, so a
single candle in a `dim` parlour lights all 32 cells to `dim` and its falloff
is invisible. All three want one answer.

<a id="unbuilt-1-122"></a>

### 1.122 What the 2026-09-05 presentation and plan fixes left open

**Five classes from the play runs landed 2026-09-05** and are pinned in
`tests/test_played_scene_classes.py`; each left a residual worth naming, and
one of them is a patch in a file this work did not own.

- **PB4 (`PLAY_2026_09_05_caravanserai.md`) — FIXED.** A body is presented
  once per view: `agents.common.charter_ground_for_room` asks
  `charter_crowd.members_of` once per (room, stage) and both readers cut from
  that one answer. **Open, and deliberate:** `CO_LOCATED_CAP` still drops a
  fourth co-located institution's crowd from a view while its members stay
  ground, so those bodies are presented nowhere in that view. The cap is a
  presentation BUDGET, not a subtraction, and the alternative (letting a
  capped-out institution's people fall through as individual figures) is what
  the figure loop's own docstring refuses. It has never fired live. The other
  known hole is `charter_runtime.background_presence_records`' ambiguity
  withholding: two bodies sharing a display name are in no view at all until
  the fiction distinguishes them, which is correct by design and reads as
  this class.
- **PE3 (`PLAY_2026_09_05_flat.md`) — FIXED for an ADDRESSED line.** A line
  aimed at somebody the scene stands in the beat's declared destination is
  graded there. **Open:** an UNADDRESSED line after a declared arrival is
  still graded from the room the beat found the speaker in. Closing it needs
  the declaration's own ORDER, and nothing carries it: `MovementDecl` has no
  index into `sequence`, and no structural test distinguishes the action
  element that IS the move from the ones around it. The patch is one field —
  `MovementDecl.after` (or an `event_id`) naming the sequence element the
  move belongs with, set by `director_interpret`, in `llm/schemas.py` and the
  interpret prompt — and one line in `perception._speech_room_for` reading
  it. Both are outside this work's files. Until then the conservative floor
  stands, because widening a channel is the direction a mistake here leaks in.
- **PD8 first half (`PLAY_2026_09_05_road.md`) — NOT BUILT, registered
  here.** `director_interpret` raised `generation_requests: [{kind: npc,
  subject: 'the shadow at the edge of the firelight', location_id:
  charcoal_camp_clearing}]` while `plan:person:hob_tarry` stood filed for
  that exact room and was in the same beat's `present_figures`; resolve
  encoded nothing, reconciliation warned the prose was unbacked, and commit
  filed a spurious `thing` need. **The patch, exactly:** in
  `language_packs/*/cards/system_prompts/prompts/director_interpret.txt`, one
  clause stating the class — *a figure the plan already holds for the room
  the beat reaches is the answer to the beat's own reach; a generation
  request is for what no plan holds* — beside the payload's existing
  `present_figures` block; and, if a deterministic floor is wanted,
  `agents/director.py` dropping a `generation_request` whose `location_id`
  names a room a filed `plan:person:*` need already answers. Both files are
  the Director agent's, not perception's.
- **PB14 (`PLAY_2026_09_05_caravanserai.md`) — FIXED.**
  `world.structure.materialize_planned_fringe` supplies a planned edge only
  into a room the scene holds, after every stub of the pass exists;
  `protect_planned_edges` already stated the same rule from the other side.
  Nothing open.
- **PA15 (`PLAY_2026_09_05_lighthouse.md`) — FIXED.**
  `perception._excerpt_in` gives every tripwire in the self-narration family
  40 characters of context on either side of the fragment it reports.
  Nothing open.

**And one deliberate loss, from PD8's second half.** A story with NO
institution at all no longer enrols a rendered person anywhere: the
`minted_households` branch of `world/charter_enrol.py` is gone, because
founding a town to hold one body made a townsman of a charcoal burner at a
woodland camp and then refused his own greeting as `outside_licence`. Such a
body keeps its surface, its presence record and its voice, and loses the
berth, the dealt seat and the simulated life a charter body has, until the
Writers' Room founds something for it to belong to. If that proves too
costly in play, the answer is a Room-facing prompt to found the institution,
not a branch that founds one silently.

<a id="unbuilt-1-126"></a>

### 1.126 Every cut a play run proposed, audited: not one field was dead

**Audited 2026-09-05**, at the owner's instruction after the campaign-3
reports: *"just because something didn't fire in their story doesn't mean it
has no purpose"* and *"I would run tests specifically around those functions
to confirm they are dead."* Four separate removals were proposed across the
reports. Every one was checked against readers, writers and a live test.
**None of them is dead, and nothing was removed.** The class, stated so the
next report inherits it: **a run measures its own story. An empty field is
evidence about the fiction that was played, never about the code.** A field
reads empty for three different reasons and only one of them is waste — the
story had nothing to put in it; the engine already retired the ask and fills
the field itself; or the branch guards a case this story did not reach.

- **The five `interaction_loop` citation keys** (`observations_used`,
  `present_evidence_used`, `memory_evidence_used`, `considered_responses`,
  `response_candidates`), reported empty in all 20 of a character's answers
  and proposed for deletion. All five are **already dropped from the wire
  schema for every caller** (`llm_quality._CHARACTER_RETIRED_WIRE_FIELDS`),
  so they cost no payload byte and the model is never invited to fill them:
  they read empty because the fix landed. Two of the evidence lanes are then
  WRITTEN BY THE ENGINE after grounding (`character.py`'s `ground_refs`), and
  `observations_used` is a compatibility projection over both that
  `persist/commit_memory.py` reads. A recorded story on disk
  (`demos/vale-model-played-14-story.json`) carries all three populated.
  Pinned by `test_the_retired_citation_lanes_are_absent_from_the_ask_not_dead`.
- **The two speech rescues** (§ 1.121), which I had myself recommended
  deleting. Both are live and both are load-bearing: the addressed rescue is
  what carries an ordinary named call through a wall
  (`hear_level` answers `none` for a normal voice through `wall`; the rescue
  makes it `full`), and the open-group floor is the only copy of a
  compatibility path for rerolled pre-repair checkpoints. Pinned by
  `test_the_addressed_rescue_is_live_and_says_so` and
  `test_the_open_group_continuity_floor_is_live_and_says_so`.
- **The body specialist's four "empty" channels**
  (`active_awareness`, `active_restraints`, `active_conditions`,
  `overlays`), proposed for conditional omission. `active_awareness` is the
  ONLY channel by which a sleeper is ever woken and `active_restraints` the
  only one by which a restraint ever ends -- the body chunk says so in both
  packs ("WAKING IS YOUR JOB, AND ONLY YOURS"), and a body whose condition is
  never re-emitted with `active:0` stays under forever. The conditional the
  report asked for **already exists** one level up:
  `director_scopes.py`'s `"conditions"` chunk is selected by
  `f["physical_beat"] or f["active_conditions"]`, so the sheet is not sent
  when there is nothing to end.
- **`world_knowledge` empty on all 20 character calls** — it is the lore
  paragraph (`character.py`), and that story had no lorebook entries.

**What remains open from § 1.121 is unchanged and is NOT a deletion:**
whether the addressed rescue's premise ("named across a barrier implies a
channel carrying it") should survive DISTANCE as well as a barrier -- three
rooms up a stone tower is not one closed door. That question was unanswerable
because nothing recorded which relation had decided; `speech_percept` now
carries the `note_step_decision` record `act_percept` has (level, how it was
reached, volume, barrier, tier), naming the comm channel, the addressed
rescue and the open-group floor separately. Decide it on the next run's
record, not on this one's absence.

<a id="unbuilt-1-133"></a>

### 1.133 A declaration of stillness is read as silence, and the walk carries on (PQ6)

**Open.** `agents/director_movement.py::_travel_continues` treats a beat with
no `movement` channel as SILENCE, and silence CONTINUES a standing approach.
That rule is right and was earned (chat 72: a beat spent grabbing someone by
the shoulders was read as abandoning a walk that was plainly still under
way). What it cannot see is the difference between a beat that says nothing
about movement and a beat that says the mover did not move.

Measured, run 2026-09-05C `quiet`
(`docs/experiments/PLAY_2026_09_05C_quiet.md` § PQ6). Turn 10 declared
`movement: {"to_room": "kitchen", "arrives": false}` and the resolve refused
it correctly: *"Halla Renn is heading there, not there. No position committed
this beat."* Turn 11's player prose read **"Halla did not move out of the
doorway"**, the interpret wrote `movement: null`, and
`director_resolve.state_diff.positions` put her in the kitchen. The narrator,
reading the new position, wrote *"Close on her left, Tobin moved"* and, one
paragraph later, *"the cold off the unlit hearth settled into her skirts"* --
the hearth being in the room she had just been moved out of. A body in two
places in three sentences, and the Director silently replacing the player's
declared conduct, which `AGENTS.md` names as its hard limit.

**The rule.** A stored approach is a standing INTENTION, and an intention the
player's next declaration contradicts is spent, not queued.

**Why it is still open.** The fix is not a prose match -- `_travel_continues`
rejects prose inference on purpose, and rightly. It needs the interpret to
distinguish "this beat declares stillness" from "this beat says nothing about
movement", and the resolve to hand that to the existing
`travel_interrupted` channel, which `_travel_continues` already honours. That
is `agents/director_movement.py` plus the interpret/resolve prompt cards; the
2026-09-05 fix wave assigned the finding to the composer lane, which owns
none of them.

<a id="unbuilt-1-135"></a>

### 1.135 The turn row, the narrator's contract and the guards (lane H, 2026-09-05)

Landed from the play campaign of 2026-09-05: **PX2** (`cast_pronouns` keyed by
what the player's view called each body, so a stranger has no name on the
page), **PQ10** (a beat that produced no step is not a turn -- the row and its
checkpoint go, and the story clock stays where it was), **PM19** (a
deterministic stage re-run on unchanged inputs reuses its active variant
instead of minting a byte-equivalent one), **PM8** (a quote's owner is the
subject of the sentence that introduces it, not the last name before it),
**PM4** (the player's declared conduct is scored against the page by its own
lexical footprint), **PM22** (a pronoun redirects a tracked subject only when
another body in scope answers to it), **PQ9** and the tense half of **PS20**
(the beat with nothing to detect from reads the author's stated intent; a
story whose author set no tense inherits the tense its own page is in), and the
deterministic half of **PX18** (one mark ends a line, at the weld the engine
itself makes).

**What is open, and whose it is.**

* **PX13, the composer half.** `state_diff.sensory_events` carries a `source`
  (`black_lacquer_cabinet`) and the composed view drops it, so the narrator
  placed a bolt-click at the locked door it had just written about and the
  next beat had to deny an arrival. The narrator card now says a percept the
  view delivers without a source has none and may not be given a home; the
  other half is `agents/composer.py` -- give the view the source when the
  observer can identify it (a hand on the lock certainly can). Until it does,
  a sound the observer COULD place still arrives placeless.
* **PX14, the guards that report a loss that landed.** Three warnings in one
  beat named things that had committed: two `attire: dropped an unsupported
  remove` for a mask that came off, and a `PLAYER AUTHORITY: declared ... was
  not captured` for an edge that committed as `barrier: open_door`. A fourth
  fired on a speech-attribution clause ("he said, at the same thread of a
  whisper") whose manner was already recorded in `declared_actions[0].volume`.
  The rule -- *say a thing was lost only after looking at whether it is
  there* -- belongs in `agents/director_floors.py` (the player-authority
  check) and `persist/commit_attire.py` (the removal report), neither of
  which is this lane's.
* **PM20, the call site.** `llm/llm_quality.json_failure_diagnosis` now
  answers which of the three JSON failures a parse error was, and
  `world/charter_generate.py::_json_call` still hand-writes a refusal that
  blames the token budget for a response that was the model's own reasoning.
  One expression: build the message from the diagnosis instead of the
  budget sentence.
* **PM24, an owner decision left as it stands.** The narrator moved a body
  through a door the ledger kept her behind; `_check_position_fidelity` fired
  and the prose shipped. The guard is right and the narrator card already
  says a character is exactly where `room` says. What is actually missing is
  upstream: a character declaration that reaches a doorway was resolved as no
  movement at all, so the ledger and the beat disagreed before the page was
  written. Fixing it at the narrator would be compensating downstream.
* **PX18, the rest of it.** Twenty-one guard firings, zero repairs. One
  repair now exists and it is deliberately the only one: the doubled
  terminal at the engine's own weld, which is typography and needs no
  opinion about the writing. The wrong-speaker attribution is a re-ask, the
  pronoun mismatch and the adverb tell are judgments about prose, and the
  standing rule for this stage -- detect and report, never rewrite -- was
  measured and should not be reversed piecemeal.
* **PX2's floor is `_speaker_display`, not `composer.observer_display_map`,
  and that is a choice with a residual.** `cast_pronouns` is now keyed by the
  same floor `co_present_positions` and `event_order` already use, which is
  the coherence PX2 asks for -- one answer to "what may this page call that
  body" across every body-keyed narrator field. The composer's map is
  STRICTLY finer: it gates a stranger's appearance descriptor on
  `visual_level_between`, so a body seen only as shapes is a bare figure
  rather than an epithet. Three narrator fields therefore still hand the
  model an appearance descriptor for a body the view rendered as a
  silhouette. It is a naming mismatch across the whole payload rather than
  anything `cast_pronouns` introduced, and closing it means giving
  `agents/narration.py` the scene and sight data on the establish path,
  where it currently has neither.

* **PM4's floor is a guess worth re-measuring.** The check declines unless a
  declared act adds at least `_PLAYER_ACT_MIN_DISTINCT_TOKENS` (two) words of
  its own beyond the view. Two was chosen because one shared word is a
  coincidence; nobody has replayed it against the stored corpus.

<a id="unbuilt-1-154"></a>

### 1.154 What the Director could not parse is filed as a thing to be built

When `director_interpret` cannot account for part of the player's
declaration, the leftover text is forwarded so nothing the player said is
silently dropped -- the warning says so: "declared 'X' was not captured by
director_interpret even after self-repair; forwarded verbatim to mapping as
a generation request". It arrives as a `thing` planning need whose SUBJECT
is that text.

**The residue of an unparsed sentence is not a noun.** It is whatever the
matcher could not account for, which is a different thing entirely from
something the player reached for. Every `generation_request` need chat 117
holds after 79 turns:

  | subject | words | is it a thing? |
  |---|---|---|
  | `tool belt` | 2 | yes |
  | `moving presence at edge of light` | 6 | no -- a description |
  | `there's floor to spare behind us` | 6 | no -- a clause of player prose |
  | `conduit runs somewhere` | 3 | no -- an inference |
  | `a bundle that thick needs a hole to leave through` | 10 | no -- an argument |

Four of five. They sit `open` against `PLANNING_NEEDS_CAP` (64), where the
oldest open need is closed as stale, so junk needs displace real ones at
four-fifths the rate they are filed; and a drain that answers them is being
asked to author a thing called "there's floor to spare behind us".

**THE ENGINE ALREADY DRAWS THIS DISTINCTION ONE NAMESPACE OVER.**
`structure.frontier_refusal` refuses to mint a room whose id would be the
sentence somebody wrote, and states the rule as a class rather than a
vocabulary: "a name is short because it is a name" (`FRONTIER_NAME_WORDS`
= 4, measured over every frontier two live plans wrote -- junk phrases ran
5 to 9 words, real names 1 to 4). On the table above that threshold is right
three times of four and never wrong: it keeps `tool belt`, refuses the
6/6/10-word clauses, and misses only `conduit runs somewhere`.

**NOT BUILT, AND THE REASON IS THE COUNT.** Five needs in one story is not a
population, and the identical-looking guard would have been WRONG on the
other reason code: `setting_fact` needs are sentences BY CONSTRUCTION -- a
fact is a sentence -- and all twelve in the corpus (chats 115/116/117, 8 to
21 words) are correct as filed. A word rule applied to `thing` needs at
large would refuse every one of them. So any refusal here must be scoped to
`generation_request` specifically, and that scoping is the part worth
getting a second opinion on before it ships.

**The better question, and the reason this is registered rather than
patched:** the forwarder exists so a player's declaration is never silently
dropped, which is the right guarantee. What is wrong is the CHANNEL it uses
to keep it -- filing unparsed prose as a request to build a noun. Keeping
the text as what it is (a declaration the interpreter could not place) costs
nothing and asks nobody to author a sentence.

**The clearest example arrived at turn 112**, and it settles what the word
count could not: the beat filed a `thing` need whose subject is

    "And while I run I let myself think about the thing I've been refusing
     to think about since the li[ft]"

alongside a perfectly good one in the same breath (`stairwell to Sub-Level
Three`). The junk subject is not a description of an object, a room, or
anything the world could hold -- it is INTERIOR MONOLOGUE, the player
narrating their own attention. No length rule distinguishes the two here;
what distinguishes them is that one names a thing and the other names a
thought, and the channel cannot tell because it was never asked to.

<a id="unbuilt-1-156"></a>

### 1.156 The player is never told what their own attempt DID

**The general case that s1.155 is one instance of, and the more serious of
the two.** A player declares an ATTEMPT. The engine decides the OUTCOME.
There is no channel that carries the outcome back to the player.

`agents/perception.py`, the act-percept loop:

    act = beat_event
    actor = act.get("actor")
    if _is_the_observer(sc, actor, name, cast_aliases.get(name)) \
            or actor in behind:
        order += 1
        continue

An act by the observer themselves is skipped before any percept is built.
The reason is obvious and half right -- you do not need to be told what you
did. It conflates WHAT YOU DID, which the player wrote, with WHAT CAME OF
IT, which only the engine knows.

**Three consecutive beats of chat 117, and the pattern is exact.**

| beat | the engine decided | did it reach the player? | why |
|---|---|---|---|
| 78 | the bracket tears free | **yes** | it changed a room anchor, so the env percept changed and was delivered as standing state |
| 80 | dice **success** margin 4, gap now "wide enough to pass a pair of human shoulders" | **no** | the outcome lived in an entity while the room reads from anchors; env key byte-identical, room suppressed as wallpaper (s1.155) |
| 84 | dice **failure** margin -6, "the rigid brackets refuse to yield... the opening still clear" | **no** | a pure event: it altered no standing state anybody perceives, so there was nothing for it to ride |

The player's view on turn 84 runs 1417 characters and is otherwise rich --
room, companion, contact, the way out -- and contains `bar` 0, `slip` 0,
`refuse` 0, `fail` 0, `brackets` 0. `_engine_notes.decisions` for that beat
lists `act_percept  Aurel Voss -> Sarah Moon  delivered` and nothing
addressed to Aurel.

**So an outcome reaches the player only by the accident of whether it
happened to change standing state they can perceive.** Turn 78 got through
because a fixture's description changed. Turn 84 did not, because "you tried
and it did not work" alters nothing describable.

**TURN 84 IS THE ONE THAT SHOWS WHY IT MATTERS.** The player levered a
conduit run across the hole to slow what was climbing after them. It FAILED,
and the failure was rolled, written and committed -- and he was not told. He
is lying on the plenum deck believing he may have covered the opening. The
opening is clear. The creature is one room below and moving. Every decision
he makes from here rests on a fact the engine determined and withheld.

The narrator cannot rescue this and should not: its own prompt says it has
"NO access to the objective event record, other minds, dice, or the
director", and it is given the player's DECLARATION but not the RESOLUTION.
On turn 84 it did the correct thing with what it had -- it declined to say
the attempt worked, and so said nothing about it at all.

**Shape of the answer.** The player needs a percept for the outcome of their
own declared attempt -- the one act-percept case `_is_the_observer` should
not skip. It is firewall-cheap in a way almost nothing else here is: a body
is entitled to the results of its own conduct, so the guard does not have to
decide what may cross, only that this one already has. What needs care is
the opposite of the usual worry -- not leaking more than the player should
have, but not RESTATING what they already wrote. The percept wants to carry
what the attempt DID and not what it WAS: the brackets held, the bar
slipped, the opening is still clear.

**AND THE FACT IS ALREADY THERE, ALREADY RENDERABLE.** Turn 85: the player
spent a whole beat asking the question the engine had answered the beat
before -- "did the conduit come down across it or not?" -- and the reply was
immediate and exact: "The clearance remained. The heavy conduit crossed
above the broken collar, but the sleeve gaped beneath it as an open throat
into the riser -- wide enough for a torso, completely unblocked."

An explicit look sets `full_render`, which re-renders the whole standing
state instead of suppressing what has not changed, and the truth arrives
without anything new being computed. So this is not a missing FACT and not a
missing renderer. It is a fact that is delivered only when the player thinks
to ask for it, on a beat they had to spend to ask -- with a deaf predator
climbing the shaft below and a barrier evaporating behind them, the cost of
that beat was the whole of what the beat was for.

**AND IT IS NOT ONLY ACTS. Turn 90: he left his companion behind and was
not told.** The player ran for the next doorway while Sarah was still
lowering herself through a ceiling sleeve two rooms back. The engine tracked
it exactly -- her view says "You are in Upper Service Core Plenum 14", his
position is Riser 15 -- and his prose says nothing about her not being
there. He is now separated from her by a drop, with the creature between
them, and nothing on the page says so.

`composer.crossing_percept` is documented as "a body entering or leaving THE
OBSERVER'S ROOM this beat". So the engine models someone walking out on you
and has no percept for you walking out on someone: the mover was the player,
and a mover's own movement is skipped for the mover by the same
`_is_the_observer` branch. Departure is built; it only fires for the one who
stayed.

This widens the entry from acts to conduct generally. What the player
declares is an intention to move; what the engine decides includes who ends
up where, and being alone is a consequence of one's own movement exactly as
a failed pry is a consequence of one's own attempt.

**ONE CHANNEL ALREADY DOES THIS CORRECTLY, which is the argument that the
fix is natural rather than novel.** Turn 101, the run's last beat: the player
made the same mistake as turn 90 -- walked on into the next riser while Sarah
stayed flat behind the jamb -- and this time he WAS told, immediately and
well:

    My hand reached into empty air. My fingers closed on nothing. She had
    not followed me onto the dark deck.

The difference is that he REACHED for her. Contact is delivered to the
player as interoception, so a contact that fails to land is an outcome of
his own conduct that reaches him by an existing channel. The act channel
skips him; the contact channel does not, and nobody had to invent anything
for it to read properly on the page.

**s1.155 folds into this** as the case where the outcome did alter standing
state and was lost on the way for a different reason. Fixing this one would
have covered turn 80 as well, from the other side.

<a id="unbuilt-1-159"></a>

### 1.159 One beat, read at every stage: what a stage-by-stage audit of turn 82 found and did not fix

The five prose fixes and two structural ones committed 2026-09-07 came out
of a critical read of chat 117 plus a full stage-by-stage audit of beat 82
(the player hauls himself through a ceiling sleeve into a plenum and reaches
down for his companion). The audit found more than was fixed. What follows
is the residue, with the evidence, so none of it has to be rediscovered.

**A. The act channel and the legs doctrine disagree between the two passes.**
`perception_act` graded both of the player's acts as `refused: observer
cannot see (sight gate)` for Sarah, who was standing in the room he climbed
OUT of -- the relation is built with `target_room=p_room`, the previewed
DESTINATION, so a body leaving through your ceiling is graded as if it were
already upstairs. `perception_outcome` then DELIVERED the same two acts to
her ("extend both hands down through the penetration sleeve"), and in the
same view told her "Through the ceiling conduit sleeve, only darkness", and
her episode ends "Aurel Voss left." while his arms are in her room. Two
passes, one act, two verdicts. The principled rule is that an act is
performed where the body WAS (the origin; `p_room_at_start` is already
captured before the preview), the crossing percepts carry the departure and
arrival, and presence is graded where the body IS -- but `_channel_to_every
_leg` states a competing doctrine ("an act that crosses rooms carries one
surface for the whole walk, so the surface is admitted only where the whole
walk was available"), under which pass 1 was right and pass 2 was the leak.
Not patched because which doctrine wins decides what a mind may know, and
that is not a decision to make at a gate without a replay against the beats
it changes.

**B. The lamp was released to nobody.** Resolve call 1 had the player take
the lamp from her hands; `_check_player_act_authority` rejected it ("an NPC
may offer, hold out, brace or wait -- the player accepts on their own turn")
although the player's declaration was "Lamp up to me first, then your
hands"; the retry kept her fidelity-locked line "Releasing my grip on the
lamp." and gave it to nobody. After commit and for the whole next beat:
`contained.emergency_utility_lamp = {in: "Sarah Moon", mode: "held"}`,
`positions` says riser 13, the contact ledger has no hand on it, and the
prose has it in the plenum. The agency guard and dialogue fidelity collided
and the world forked. The rule is right in general and wrong when the
player's own declaration already covers receiving; the retry also left no
warning on the step -- only `llm_capture.correction_notes` records that a
rewrite happened or what it removed.

**C. The tremor has no percept channel -- FIXED 2026-09-07** (a tick in the beat view now addresses the `sensory_events` owner; `director_scopes._ruling_for`, `director_fanout._resolve_beat_view`). `world_pressure.must_tick_this_beat`
forces the sector breach to "visibly act ON-PAGE" every third beat
(`beats_since_tick: 2`), and it does -- in `resolved_event`, in `overlays`
(five near-identical dust lines on one body by beat 106, evicting a distinct
knees-and-palms fact at `_MAX_OVERLAY_ENTRIES = 6`) and in the world-pressure
tick itself. Census of beats 60-115: a tremor in 18 resolved events, exactly
every third beat; **9 of the 18 never reached the player's view**, because
`sensory_events` belongs to the objects hand and the objects hand was not
dispatched. A pressure the floor forces onto the page has to arrive through
a channel a mind can perceive, or the floor is buying prose.

**D. A character's guess became committed geometry.** Beat 106: Sarah said
"Riser Nineteen on the flank is a blind compartment" about a PLANNED room
nobody had entered. The resolve spatial hand rewrote it -- `"Upper
Service-Core Pocket 19"`, `size: tiny`, a `blind_bulkhead` anchor -- and
re-hung riser 18's edge to it as `dir: "e"`, so the northward main run the
player was following lost its north exit from 18. The Director may author an
unplanned room; it authored this one from a mind's speculation and altered
the graph the player was standing in to match. (`known_dead_ends` writing
her belief from a one-edge stub is s1.156's neighbour and was fixed the same
day; this is the belief flowing the OTHER way, into the world.)

**E. Smaller, from the same beat.** The interpret body hand (119 bytes) and
contact hand (156 bytes) returned nothing; the resolve contact hand spent
5,564 output tokens re-encoding a removal already in
`character_contact_endings`; the interpret spatial hand spent 11,852 output
tokens (14.8 KB of reasoning) to emit 1.6 KB. The character model addressed
every action to `character:79`, an id that exists in no table, and it leaked
into memory 27815 ("I suspected this about character:79"). Twelve provider
calls, ~176k input tokens, for one beat.

## 2. Roadmap

<a id="unbuilt-2-18"></a>

### 2.18 The orchestrated Director: what is left after it landed

**LANDED 2026-08-14.** The fan-out is the only Director path: there is no
`DEFAULT_PROMPTS["director_resolve"]`, no `director_orchestration` setting,
and `director_fanout_mode` chooses concurrency rather than a different set of
hands. `Design.md`'s conformance row says Built, and it is right.

This entry used to be the whole proposal — the argument, the measurements,
the retracted framings and the build log — with its landing recorded in a
paragraph at the bottom. A reader triaging §2 read the shipped architecture
as an open experiment, and this register is supposed to WIN when the status
lists disagree. The argument and the numbers live in
[`design_notes/19-director-orchestration.md`](../design_notes/19-director-orchestration.md)
and in the alpha 9.2 changelog; what belongs here is only what is still
unbuilt:

- **The prose author's PAYLOAD is still the full monolithic one.** Its SHEET
  was carved (14 duty chunks, `_PROSE_DUTY_GATES`); the payload was not. The
  next real token win.
- **`director_interpret`'s own sheet is not chunked.** The delegated channels
  are suppressed at the source (`llm/prompts.interpret_delegation_note`, called from `agents/director.py`; the constant `INTERPRET_DELEGATION_NOTE` this entry used to name does not exist — corrected 2026-08-19), but the blocks
  teaching them still load on every call.
- **The specialist chunks have never been rewritten for leanness.** Permitted
  — they exist only on the orchestrated path, so there is no monolith to keep
  them compatible with.
- **The offscreen SIMULATOR** (out-of-band propose/ratify) remains
  owner-deferred. The `offscreen` specialist ships the ops surface only, and
  schedules nothing.
- **The dispatch rate under ruling-keyed dispatch is unmeasured.** Since
  2026-09-02 a hand runs only when the author's `ledger_notes` or
  `changes_asserted` reaches it. The 1.75-of-6 mean and the five-of-six
  physical beat were both measured under the gate-keyed dispatch; the
  9.10 arms found the author writing about a fifth of its channels with no
  ruling, and under the new rule that fifth is a hand not run rather than a
  hand run without a note -- the reconciliation seam's owner-routed repair
  is what catches it, at one serial call. Measure both before trusting the
  saving.
- **The replaced-channel warning rate has never been re-measured live.**
  Stored variants hold only the MERGED output, so the after-rate cannot be
  read from run 20's own beats.
- **Provider cache affinity is configuration, not code.** Run 20 diagnosed
  the 19% prefix-cache rate as provider replica routing rather than byte
  instability; honest ceiling ~57%, since the per-beat payload is inherently
  uncacheable. Recorded rather than chased.

## 3. Information-pipeline leaks still open

<a id="unbuilt-3-1"></a>

### 3.1 Prose matching as a boundary

Materially improved — `_surface_translate_event` now fails closed, speaker
attribution is structured, `_redact_concealed_from_event` is casefolded,
word-anchored and pronoun-continuation-aware — but **not eliminated**.

- **C1 — quoted spans are an identity smuggling channel**, and the whitelist
  that guards them is loose: `body == L or body in L or L in body`, so any
  short genuine line ("yes") whitelists every fabricated quote containing it.
  Quotes are exempt from the identity scrub by design. Both passes now run the
  check — `_scrub_invented_dialogue` inside `_composer_tripwires`, reached from
  `_composer_finish_observer`, so the act pass is no longer the blind one — but
  it is **warn-only** in both, which is the right call and worth stating as
  such: a composed view is realised from percepts, so dialogue in it that does
  not match the delivered-line ground truth is an ENGINE defect, and scrubbing
  it would hide the bug instead of the leak. The loose whitelist therefore
  costs a missed WARNING now rather than a missed scrub.
- **C2 / E2 — the identity floor is TOKEN-BASED, which is one finding and was
  written as two** *(merged 2026-08-19)*. Forms under three characters and
  single-token are never scrubbed, and `_unknown_actor_label` strips only name
  and alias tokens — so a short or common-word name escapes the floor at one
  end, and a unique identity-bearing EPITHET in the appearance survives into the
  label at the other. `_COMMON_WORD_NAMES` is a separate, exact-case mitigation,
  not a fix. Both are the same channel and want the same answer: identity
  carried structurally on the event rather than matched out of prose (§4.2).
- **D1 residual — a paraphrase with a fresh explicit subject still escapes**
  `_redact_concealed_from_event`. The function's own docstring names this
  residual and names the structural answer: carry identity on the event.

*(E1 was struck 2026-08-19: `knows_identity` is WRITE-ONLY — set at six sites in
`agents/perception.py` and read nowhere — so the inconsistency it named with the
title-tolerant `_recognizes` (`agents/common.py`) cannot be reached. See §1.45.)*

## 5. Deferred backlog

<a id="unbuilt-5-1"></a>

### 5.1 P2 — ambient repetition, deterministic

**Symptom.** "The bridge hums" recurs across a run. An AMBIENT RESTRAINT prompt
rule reduced but did not eliminate it — **reworded variants slip the exact-word-run
diff** in `_already_established_phrases`, which is still exact six-word shingles.

**Adjacent mechanism that is not this.** `_overused_phrases` (exact 3-gram
cross-block tic ban, wired into the narrator) now catches literal recurrence. It
does not catch the reworded variant, which is the whole point of this item.

**And a ceiling on any phrase-matching fix, measured 2026-08-28 (§1.70).** One
live instance of this symptom was not the narrator's invention at all: the
payload was handing it a false `changed` verdict on an unchanged crowd, and
`current_events` is obligation, so the ban list was arguing against material
the engine kept re-supplying — "held its pitch" was banned at turns 7, 8 and 9
and the closer arrived anyway. A ledger of ambient lemmas would have caught
the surface and left the cause. Fix the verdict first, and measure what is
left over before building the fuzzy matcher.

**Fix.** Extend recent-cue dedupe to ambient set-dressing: a small per-chat ledger
of recently-used ambient sensation lemmas (hum/thrum, klaxon, flicker,
door-open), fuzzy-matched by stem/lemma rather than exact word-run against the
draft; drop or warn on a re-mention not flagged as changed. Sits beside
`already_established_phrases` in `agents/narration.py` / `agents/common.py`.

**Test.** "The bridge hums." established in recent prose; a new draft "the ambient
hum of the bridge" is caught despite the reworded surface.

<a id="unbuilt-5-3"></a>

### 5.3 P5 — route player-authored NPC acts through the character reaction

**State.** Director-prompt rules (NPC acts belong to the NPC; being acted upon is
not passive) make the resolve *render* the reaction. It is not routed through the
actual `reaction_loop`, so the NPC gets no genuine agent-generated interiority or
choice for the beat.

**Root cause.** `_requires_reaction_phase` gates a reaction on
`commitment == "contestable"` — still literally `if event.get("commitment") !=
"contestable": return False`. A player physical act on an NPC is `asserted`
(player authority), so the NPC never enters the reaction loop. Separately, a
player-*authored* NPC volitional act executes as an objective event with no
character-agent call at all. Reactor derivation remains spatial-only.

**Fix.** (a) In `director_interpret`, when a player action targets a present,
volitional, sheeted character with a conflict verb, add that character to the
beat's reactors **even when the player's act is `asserted`** — the reaction is the
NPC's *response*, not a contest over whether the player's act succeeded. (b) When
the player declares a volitional act *by* an NPC, hand it to that NPC's character
agent to adopt (supplying interiority and voice) or refuse. Both touch the
delicate director/reaction seam — go test-first, small.

**Test.** A player "grab X" beat produces a reaction step for X; a player-authored
"X lunges" beat calls X's character agent.

## 6. Design-note residuals

<a id="unbuilt-6-3"></a>

### 6.3 Greeting-seeded openings — [`GREETING_IMPORT_DESIGN.md`](design/GREETING_IMPORT_DESIGN.md)

About 60% shipped in alpha 1.4, under a materially different architecture — the
narrator **does** run on turn 0 and its prose is overridden afterwards, rather
than the design's pre-baked variants plus resume. **The extraction's scope has
since outgrown this note**: what a greeting may put inside a MIND — beliefs,
stances, opening affect, for every person present rather than the card's owner
alone — moved to
[`DESIGN_GREETING_MINDS.md`](design/DESIGN_GREETING_MINDS.md) and is built
(extractor v2). Still unbuilt and still wanted:

- **Ingest-time extraction caching — the WRITE half only.** The read half
  landed with extractor v2: `story/greetings.py` stamps
  `extractor_version = EXTRACTOR_VERSION` where the extraction is MINTED
  (not where it is filed, so a copy made by an archive, an editor or a hand
  written card cannot claim a provenance it does not have), and
  `_usable_stored_extraction` replays a stored blob only if this extractor
  made it — unstamped means older than the stamp, and the stored blob is the
  one path into turn-0 seeding that never passes through today's schema.
  What is still missing is anything to replay: `story/importers.py` and the
  first-message fallback both write `"extraction": None`, so extraction runs
  lazily at launch and is discarded every time.
- **The `private_history` write.** Seeds route to character memory only.
  Idempotency itself is closed and by a better key than the design named: each
  seed carries `greeting_seed:<sha1(content)[:16]>` and the batch upserts on
  `(chat, character, event_key)`, so a retried or partially-failed launch
  updates one row rather than writing a second, and editing or reordering the
  greeting cannot orphan the old row the way a positional key would. It
  deliberately does not dedupe ACROSS launches — `start_story` creates a fresh
  chat each time, so a second launch is a different story entitled to its own
  copy.
- **`player_slot` and escalation.** `GreetingInterpret` has only a flat
  `player_room`; no `hard_attributes`, no `pronoun_tokens`, no conflict detection.
- **Turn-0 greeting swipe** (`greeting_swipe`, `refresh_checkpoint(cid, 0)`).
- **The verbatim-preservation invariant test.** The knowledge-boundary half of
  this pair now exists and is stronger than the design asked for —
  `tests/test_greeting_minds.py` pins the player-naming forced reveal in
  every mind, the identity floor on a stranger start, and the refusal of
  player affect/stances with the refusal made visible — but nothing asserts
  that imported greeting prose reaches the page byte-for-byte.
