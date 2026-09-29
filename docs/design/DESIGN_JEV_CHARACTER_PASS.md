# Jev around the character call: the tracking pass and the memory packet

**Status: PARTLY BUILT, 2026-09-27, branch `worktree-jev-character-tracking`.**
The affect pass is wired (increment 1, "Wiring the affect pass" below); the
bare contract is built and, since 2026-09-27, the only character contract
("The bare contract" below), which carries increment 2 and everything the full
card's bookkeeping asked for -- the full card and its kernel compiler are
deleted; the
memory packet LANDED 2026-09-27 as `mind/memory_jev.py` -- the measured shape
at equal lane weights, without the moment tag (decided 2026-09-29 as the
beat's own feelings, stored on each memory and read by the affect pass --
"A memory keeps what its moment made the mind feel" below -- but no lane of
the net reads it yet) and at 24 rows (48 still the owner's, after the conduct replay);
`docs/guides/MEMORY.md` §5. The survey numbers come
from four read-only surveys of the code and of `engine.db`
(`llm_capture`/`llm_blobs`, `variants._engine_notes`) over the ten days to
2026-09-26, spot-checked by hand.

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

### Emotion and mood, as designed with the owner

The owner, 2026-09-26: "we might actually be able to remove mood handling
entirely from the prompt. And code can combine moods into moods that are
actually combos", "I still imagine jev needs event context to handle how
events might change mood", "if we ask these questions after jev has crafted
the memory packet ... can we factor memories into mood?", and "habituation
should also have a decay rate." Built and wired (`mind/affect_pass.py`,
"Wiring the affect pass" below); measured in the evidence doc from "Mood as a
Jev job" on.

**Three layers** -- temperament, mood, emotion -- the structure of ALMA
(Gebhard, "A Layered Model of Affect", 2005), built for virtual characters:

- **Emotion** is fast, about something, caused by an event. Jev names it
  and says how strongly it stirs; code carries it into the mood.
- **Mood** is slow and diffuse, a point in pleasure-arousal-dominance space
  that emotions push and that drifts home. Code owns it -- the measured
  shape: carrying the mood and moving it part way toward Jev's reading beat
  pure persistence on every axis.
- **Temperament** is home and how easily the character is moved: the card's
  `stress_profile` and traits. No new card field.

**Order within the before-call pass:**

1. The memory packet (net, then Jev).
2. Each of the beat's events put to Jev with the packet in its state: how
   strongly it stirs the character, and how it makes the character feel --
   one choice over OCC's event emotions (Ortony, Clore and Collins, 1988:
   joy and distress, hope and fear, a hope or a fear come true or not,
   pride, shame, disapproval, the fortunes of others, gratification and
   remorse) beside the forty standalone moods, or nothing much. Memory is the
   appraisal's context: a third lie is not a first.
3. Code turns the answer into emotions -- each feeling by its share times
   how strongly the event stirs -- each about its event ("disapproval
   (Hinami: says she took the key)").

   Until 2026-09-26 step 2 was nine appraisal questions (desirability,
   happened or might, confirmation of a hope or fear, who caused it, right or
   wrong by the character's standards, good or bad for someone liked or
   disliked, how much the character can do -- Lazarus; Scherer's component
   process model) and step 3 OCC's rules over them, compounds included.
   Against two blind readers the rules named an event's feeling at chance,
   and the direct question named it nearly as well as the readers named it
   for each other (the evidence doc, "Round seven"); the rules are retired.
4. Memory-evoked feeling: a recalled memory brings back what its moment made
   the character feel, kept with it when it formed and faded by its age --
   slowly, never to nothing (recalling a feeling brings part of it back:
   autobiographical recall is a standard mood induction). Built that way
   2026-09-29 ("A memory keeps what its moment made the mind feel", below);
   until then each recalled row was asked three questions on every beat it
   came back.
5. Code moves the mood: event emotions at full weight, memory-evoked ones at
   a fraction; decay toward temperament in psych units (story minutes where
   the clock runs, turns where it does not), the unit every affect decay
   already uses. The fraction is built as the owner stated it on 2026-09-28
   ("memory should have a subtler mood affect. unless it is a particularly
   intense memory"; its "intensity still shouldn't exceed presen moment but
   it should definetly be noticeable"), once a beat carried the recent turns
   and 30 recalled memories -- about 69 against at most 8 events
   (`mind/affect_mix.py`): a memory's pull on the mood is `MEMORY_WEIGHT` x
   its strength cubed (`MEMORY_MOOD_CURVE`: 0.5 keeps 12% of its pull, 0.9
   keeps 73%), how strongly it is FELT and named left as it was; all the
   memories together pull at most as hard as the present moment
   (`MEMORY_OVER_PRESENT`), whose say is never less than one intense
   memory's (`QUIET_PRESENT`), and what the present's own feelings leave of
   that say holds the mood where it stands -- so a quiet beat is coloured by
   what is remembered, at most halfway toward it.

The character receives one block -- emotions with their objects, the mood,
the undercurrent -- and stops writing affect; the prompt's feelings, pain and
pleasure, and hedonic paragraphs go.

**Loop guards.** Mood chooses which memories surface (`mood_match`), and
memories move the mood (Bower's associative network, 1981): unchecked, that
is rumination. So memory's push per beat is capped relative to the events',
the split between `mood_match` and `mood_contrast` rows follows temperament
(a steady character repairs, a vulnerable one spirals), and a memory's pull
habituates:

**Habituation, with decay** -- the owner's model: "a character recalls a
pleasant memory and gets a mood boost from it for a few turns of recalling
before habituation reduces that effect. but that same memory if evoked
some... number of turns later can once again deliver that pleasantness."
Habituation's defining properties agree -- a response that wanes with
repetition and recovers spontaneously when the stimulus is withheld
(Thompson and Spencer, 1966; Rankin et al., 2009). Per memory:

- each time a memory lands, its habituation rises by a step;
- below a grace level it costs nothing: the first few recalls deliver the
  memory's full feeling -- the shape of the surface habituation's protected
  range, where only elevation above a floor is paid for;
- above the grace level, the evoked push shrinks toward a ceiling of
  reduction;
- while the memory is not evoked, its habituation decays on a half-life in
  psych units, back to nothing -- after enough turns away, the same memory
  delivers its full feeling again;
- new information about the memory -- a reinterpretation, or a new event of
  the same kind -- resets it at once.

Psychology also describes a slower habituation that builds across repeated
series and outlasts a rest; the owner's model recovers fully, so it is not
part of this design.

### The mood math

The owner: "We can also probably do math with moods, the cumulative effects
of events and memories average into an overall mood with multiple
dimensions." Built in `mind/affect_mix.py` (pure code) and
`mind/affect_appraisal.py` (the Jev questions); run around each character
call by `mind/affect_pass.py`.

- **The space.** A mood is a point `M` in forty-six coordinates: fourteen
  bipolar spectrums in [-1, 1] and forty standalone moods in [0, 1] (the
  next section). It began as Mehrabian's three PAD axes; the owner widened
  it ("mood has way more dimensions than what you have mentioned", "spectrums
  of moods as coordinates as well as some moods that truly stand as their
  own", "cover all moods"). Temperament is a home point `H` in the same
  space; standalone moods' home is nothing.
- **Emotions.** Each emotion `e` has an intensity `i` in [0, 1] and a
  direction `v`: the coordinates it moves (`EMOTION_EFFECTS`) -- one row per
  OCC emotion, after ALMA's table (Gebhard, 2005), and one per standalone
  mood, itself in full and the spectrums it moves. An event yields the
  feelings named for it, an OCC emotion or a standalone mood alike: how
  strongly it stirs the character times each feeling's share of "how does
  this make you feel".
- **Decay.** Between beats `M` returns toward `H` by `0.5^(dt / half_life)`
  per axis, `dt` in psych units; pleasure below home decays more slowly
  (bad is stronger than good -- Baumeister et al., 2001).
- **The centre.** This beat's emotions average into
  `C = sum(w v) / sum(w)`, weighted `w = i x negativity (when v's pleasure is
  below zero) x memory weight (when the emotion was evoked by a memory, already
  scaled by that memory's habituation)`.
- **The push.** `S = 1 - prod(1 - i)`: several emotions push harder than one,
  never past 1. `M <- M + reactivity x S x (C - M)`: the mood moves toward
  the centre by a share -- the shape measured to beat persistence.
- **The layer beneath.** The present -- a perceived event, the character's
  own act -- is the surface; the past and the unsettled -- a recalled memory,
  a standing concern -- are beneath (the owner: some moods "may be purely
  memory related ... or their undercurrents at least"). A memory brings back
  the feelings its moment stirred, kept when it formed, faded by its age
  toward a floor and dulled by habituation; one that keeps nothing -- minted
  before memories kept their feeling -- or that the mind re-read since is
  read once instead: the standalone moods named for it ("which of these
  does recalling it stir most"), the share none of them covers a plain
  pleasant or unpleasant feeling by its tone, and that reading is kept. A concern is named
  like an event, scaled by "in this moment, how much does this crowd out
  everything else?", and does not push the surface (`CONCERN_WEIGHT = 0`).
- **Names.** Mehrabian's eight octants (exuberant, relaxed, dependent,
  docile, hostile, disdainful, anxious, bored) for a compact label; the
  surface is the strongest feeling the present stirred, with its object; the
  undercurrent the strongest a memory or a concern stirred, when it reaches a
  floor -- else the strongest feeling of the other sign, or the mood when it
  disagrees with the surface.

Knobs, all the owner's, none tuned: reactivity, half-life, negativity weight,
negative decay factor, memory weight, concern weight, the undercurrent's
floor, habituation's step, grace, ceiling and half-life, and a kept memory
feeling's fade half-life and floor. The card's
`stress_profile` can set reactivity and half-life per character once the
defaults are chosen. Every value in `EMOTION_EFFECTS` is the owner's too.

### The coordinate system

The owner: "We are trying to cover all moods and make a coordinate system out
of them", "some moods are really just spectrums some aren't, so there is some
simplification but simplification is not the goal." The rule used here: a
mood is a **point in spectrum space** when two people in it would agree on
every spectrum and differ on nothing else; it is **standalone** when some
mood at the same point is a different mood -- numbness and calm share a
point, guilt and embarrassment do, jealousy and envy do -- or when it has an
object the spectrums cannot carry (romance is toward someone). The keys are
the pack's (`affect_appraisal.options`); the words below are its English.

**Fourteen spectrums**, one five-step question each:

| key | low -- high | why its own axis |
|---|---|---|
| pleasure | unpleasant -- pleasant | valence, in every inventory |
| energy | drained -- energized | energetic arousal (UWIST, Matthews 1990) |
| tension | calm -- tense | tense arousal, apart from energy (UWIST) |
| control | powerless -- in command | PAD's dominance; Fontaine's potency |
| clarity | bewildered -- clear-headed | confusion is its own POMS factor |
| connection | alone -- connected | felt belonging |
| openness | guarded -- open | self-disclosure and trust |
| playfulness | serious -- playful | play as a state (the round-one probe needed it) |
| hope | hopeless -- hopeful | the future's valence, apart from the present's |
| self_regard | ashamed -- proud | the self's valence; shame lives here |
| safety | threatened -- safe | fear's axis, apart from displeasure |
| engagement | bored -- absorbed | interest and entrancement against boredom |
| boldness | timid -- bold | approach against avoidance: anger approaches and fear withdraws at the same displeasure (Carver and Harmon-Jones, 2009) |
| sociability | wanting to be alone -- wanting company | loneliness is the gap between wanted and felt connection (Perlman and Peplau, 1981), so wanting company is apart from feeling connected |

**Forty standalone moods**, one graded question each: every category
Cowen and Keltner (2017) found self-report keeps distinct that no spectrum
already holds, then what their list lacks.

Each mood's wording is the pack's, and several were chosen by measurement --
a one-question probe on captured beats, then the mood battery's constructed
situations (the evidence doc, rounds three and four and "The mood
battery"). Words in an option pull toward what they name, so a wording
states its class alone.

- **Wanting** -- romance ("romantic love, or being drawn to someone
  romantically"), sexual desire ("sexual desire or sexual arousal": intimate
  moods need explicit words), craving (the owner, "there is non romantic and
  sexual desire to consider": "hunger or thirst for something to consume" --
  an appetite on its own axis, beside sexual desire or without it; wordings
  about wanting "to have" read every want as craving), greed ("a hunger for
  wealth and things": wanting to own, which is neither an appetite nor envy
  -- the battery found no coordinate held it, and the owner made it one;
  "wanting to own or keep something for yourself" read a starving man's bread
  as greed), curiosity (a want to know; engagement is attention, not
  wanting), anticipation (Plutchik's primary, eagerness for what is about to
  happen).
- **Appreciation** -- awe ("awe before something vast": "awe or wonder" read
  any beauty), admiration, aesthetic appreciation, amusement, being moved
  ("moved by someone's goodness": kama muta, Fiske, Seibt and Schubert,
  2017). All sit near one pleasant, absorbed point.
- **Toward someone** -- tenderness, compassion (feeling for someone's pain and
  wanting to ease it), gratitude; anger, contempt ("scorn for someone you
  consider worthless"), disgust -- the hostility triad, one unpleasant point
  split by what was violated (Rozin et al., 1999); jealousy ("fear of losing
  someone you love to a rival": English says "jealous" of what another has)
  apart from envy (wanting what someone has: Parrott and Smith, 1993).
- **The self** -- guilt (about an act) and embarrassment (about being seen);
  shame is the self_regard spectrum (Tangney and Dearing, 2002).
- **Others** -- horror ("horror at something unnatural or monstrous": a bare
  "horror" read anything awful), sadness (loss, apart from fear and anger at
  the same displeasure), surprise (Fontaine's novelty, as a transient),
  resolve, numbness (emotional numbing, which no point near neutral can tell
  from calm).
- **Whose object is the past** -- nostalgia, grief ("bereavement, grieving
  someone who has died": "grief for something lost" read every loss), regret,
  longing, homesickness, and being troubled by a memory from one's own past
  that keeps coming back. Recall stirs them; they are what sits beneath.

**Coverage.** How moods with no coordinate of their own sit in the system --
illustrations of the rule, not a list the engine matches against:

| mood | where it sits |
|---|---|
| content | contentment -- its own coordinate since 2026-09-26; serene: pleasant, calm, safe |
| excited | pleasant, energized, absorbed |
| anxious, worried | tense, threatened; dread when the worry is about what comes (its own coordinate since 2026-09-26) |
| afraid | threatened, tense, timid |
| panicked | tense, threatened, bewildered, powerless |
| overwhelmed | tense, powerless, bewildered |
| restless | energized, bored, tense |
| exhausted | drained |
| confident | in command, proud, bold |
| insecure | ashamed, threatened |
| shy | timid, guarded, with embarrassment |
| lonely | alone and wanting company, often with longing |
| withdrawn | wanting to be alone, guarded |
| suspicious | suspicion -- its own coordinate since 2026-09-26: guarded and threatened said too little about someone's intentions |
| vulnerable | open, threatened |
| despairing | hopeless, unpleasant, drained |
| apathetic | bored, drained, with numbness |
| dominant | in command, bold; submissive or docile: pleasant, powerless, calm (Mehrabian's docile octant) |
| defiant | bold, in command, with anger |
| bittersweet | nostalgia with sadness |
| wistful | nostalgia with longing |
| schadenfreude | amusement with contempt (OCC's gloating) |
| smug | proud, with contempt and amusement |
| humiliated | ashamed, powerless, with embarrassment |
| betrayed | anger with sadness, alone |
| heartbroken | sadness with romance, alone (the battery reads both high when a ring is returned) |
| infatuated, obsessed | romance, absorbed |
| possessive | jealousy, in command |
| protective | protectiveness -- its own coordinate since 2026-09-26, out of tenderness |
| predatory hunger | craving, bold, in command |
| aroused by being watched or shamed | sexual desire with embarrassment |

Code can name what the combinations make, as OCC's rules named their
compounds until 2026-09-26 (the owner: "code can combine moods into moods
that are actually combos"); none of
the rows above is built as a name yet. The blind rater in round three also
lists any mood a beat holds that no coordinate covers (the evidence doc).

**What the rater kept naming, and what became a coordinate** (2026-09-26, the
owner: "add the missing moods ... and explore what other moods we may be
missing"). Across 272 rated beats -- the Doctor and Mirelle chats, rounds five
and six, and the four test stories -- the rater named 151 distinct uncovered
moods, 287 times. Grouped by what they mean: protectiveness about 29, pride
in one's craft about 40 (mostly one character), savoring and satiety about 20,
wariness and suspicion about 19, dread about 16, urgency about 14, vigilance
about 8, triumph and vindication 6. Ten candidates went through the mood
battery with situations and person types built for them; eight became
coordinates (protectiveness, dread, suspicion, urgency, mastery, triumph,
relief, contentment) and two did not: **vigilance** fired unasked in 45 of 152
situations -- a soldier's letter, a ball, gold by a fire -- because watching
closely reads as attending to anything gripping, and its sense is tense,
threatened and absorbed, its "protective vigilance" protectiveness;
**savoring** fired in any pleasant scene (36) and leaked into hunger, where
pleasure, contentment and appreciation of beauty already stand. Tenderness
lost "or protectiveness" from its wording, which had pulled it into a guard
kicking a prisoner (0.81, now 0.45). Explored and left to what already covers
them: reassurance (compassion, protectiveness), weariness (drained), cornered
(powerless, threatened), rivalry (envy, triumph), and from the taxonomies
boredom (bored), loneliness (alone), shame (ashamed), hatred (anger with
contempt), schadenfreude (gloating) -- none of which the rater named.

**Measured 2026-09-26** (the evidence doc, "The affect pass, built and run"
and rounds two to four):

- **Read the mood directly; let the math attribute and carry it.** Against a
  blind rater, Jev's direct reading of the coordinates leads -- mean r 0.64
  over round two's twenty, 0.50 over the 36 of 45 that varied in round four
  -- where the mood derived from the beat's emotions reaches 0.27-0.30 and the
  direct reading settled with inertia 0.36-0.52. The math is what says what a
  feeling is about and carries the mood between readings; the reading is what
  says where it is.
- **Desire in three works where it varies**: sexual desire r 0.90, craving
  0.88 once worded as an appetite (a one-question probe chose the words).
  Romance is unmeasured -- neither story is a romance (the owner) -- and its
  wording was chosen on constructed contrasts. Nine more moods did not vary
  in the two stories (contempt, disgust, jealousy, envy, sadness, numbness,
  grief, regret, homesickness) -- unmeasured, not absent.
- **Jev is read by its words**: a word in an option pulls toward what it
  names, even when it names what the option excludes, and a word with a
  physical second sense reads physically in an explicit story. State each
  mood's class alone, and probe a wording before adopting it -- the mood
  battery is the probe (`tools/jev_mood_battery.py`): nine wordings chosen
  there took its situations from 93% to 97% of expectations met.
- **The mood reads the person, not only the event.** Given one situation and
  thirteen person types written in the card's fields, Jev orders 80 of 82
  predicted pairs as psychology does -- envy for the achiever and the
  narcissist over the secure, compassion and guilt for the caregiver over the
  psychopath, awe for the explorer over the depressed. So the card's
  psychology is what Jev needs in its state for the mood to be the
  character's own.
- **The memories today's recall delivers stir the scene's own moods** --
  sexual desire, curiosity, tenderness -- and almost never the past-directed
  ones; which moods are memory's own waits on a packet that holds some past.
  Today's packet also repeats: habituation at the placeholder knobs dulls
  about half of all recalls.
- **Concerns are the layer beneath, and not yet gated.** Appraising what is
  still unsettled for the character (rumination) names the undercurrent its
  report carries on 32 of 32 beats where events alone named 11 -- but moving
  the surface mood with them costs its tracking at every weight tried, so a
  concern names the undercurrent and does not push the surface
  (`CONCERN_WEIGHT = 0`). "How much is this weighing on you right now" does
  not discriminate: Jev answers about 0.7 for every concern the character
  listed. Since round seven the question is "In this moment, how much does
  this crowd out everything else?": 15 of 21 expectations on the concern
  battery against 9, and still present on a quiet evening.
- **The pass after the turn** (the owner: "a pass after the character turn
  finishes to see how their actions speech and thoughts affect their mood")
  runs beside `director_resolve`, off the critical path, and carries its push
  into the next beat. With the event questions it helps a little and reads
  the character's own acts with a self-serving tilt, so it gets its own
  questions: did this go against something you value (dissonance -- Festinger);
  did you hold back something you wanted (restraint's cost); did saying it
  ease the feeling or feed it (affect labelling -- Lieberman et al., 2007 --
  against venting -- Bushman, 2002).
- **Memories as context** wait for the Jev packet: the packet recall delivers
  today is about a quarter relevant, and its effect was mixed.

This dulls a memory's FEELING, never its availability: the row stays in
recall in full (the owner's goal is good memory, not forgetting). The surface
habituation already in `mind/affect.py` recovers on its own half-life
(`_HABITUATION_RECOVERY_HALF_LIFE`, 2.5 psych units) and ships off
([`UNBUILT_CHARACTERS.md`](../UNBUILT_CHARACTERS.md) §1.41).

Every step, half-life, cap and ceiling above is the owner's to set; none is
chosen here.

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

## Wiring the affect pass

The owner, 2026-09-26: "remove all mood related machinery from the character
prompt. and just have it fed to the character in it's packet. And have it
update the moods again post character actions." Mapped before any edit: the
prompt carries eleven affect clauses; the reply's `affect`, `stress`,
`hedonic` and full `appraisal` are required fields; commit folds the reply's
affect into stored state through `affect.resolve_affect(..., proposed=...)`,
and memory rows, mood-congruent recall, tells, absorption and stress read
that state.

**Increment 1 -- feelings. Built 2026-09-26** (`mind/affect_pass.py`, wired
in `agents/character.py`; `tests/test_affect_pass.py`,
`tests/test_character_continuity.py`; the full suite, 16,488, green on the
shipped stack).

- **Leaves the prompt:** CURRENT FEELINGS as an instruction to propose
  feelings, the `affect` object in the required shape, and the feelings in
  EARLIER THIS BEAT. CURRENT FEELINGS becomes the explanation of the given
  block; `active_concerns` stays with the character.
- **Before each character call:** the carried mood (`active_state.mood_coords`,
  persisted) decays over the psych units since it was last touched; Jev
  appraises what this character legitimately holds -- its own card, this
  call's perception, its recalled memories, its concerns, its people -- one
  request per character; `affect_mix` turns that into emotions, mixes them into
  the mood and settles it toward Jev's direct reading; the packet gains
  `self.feelings`: the surface feeling with its object, the undercurrent, and
  the mood in words.
- **After the call:** Jev appraises the character's own speech, actions and
  held-back want; pride, shame, frustration and easing or stoking move the
  mood.
- **Into commit through the existing seam:** the engine writes the given
  affect into the result's `active_state.affect` -- the field the model used
  to fill -- so `resolve_affect`, tells, the round merge and memory context
  read the same field, now from the engine; `mood_coords` and per-memory
  habituation ride in the state JSON, so checkpoints and archives carry them.
- **Fails open:** when Jev cannot be asked, the carried mood decays and the
  turn goes on.

What increment 1 leaves, found while documenting it:

- **Two records of one mood.** The pass keeps `mood_coords`; memory rows,
  tells and mood-congruent recall read `affect.surface`, which
  `resolve_affect` still blends from the decayed prior toward the pass's
  point, nudged by the model's own `appraisal` dV/dA. The next call's
  feelings read the first, the memory written this beat the second, and
  they can disagree. Writing the pass's point through (or deriving one
  from the other) changes every new memory row's valence -- the owner's call.
- **The undercurrent synthesis is retired in effect.** The pass always
  writes the undercurrent key, so `resolve_affect`'s contradiction synthesis
  never fires on a given affect; the layer beneath is memory and concern.
- **Latency, measured in play:** two Jev requests a character call, the
  first on the critical path before the model call, each 0.2-0.3 s on the
  test stories against 7-82 s character calls; each lands in the step's
  call records as `role: jev`.
- **A memory with no stable key never habituates** -- named by its place in
  the packet, it has nothing to habituate by (134 of 17,065 rows in the
  owner's database).

Read live on the four test stories (2026-09-26, 11 turns on the new engine), the
given feelings turned into conduct without being reported -- a traitor handed
"a fear come true" and guilt beneath went into duty ("Pulse steady,
Anselm?"); a teacher handed tenderness toward the boy said "That was my
choice, Kit. Not yours to carry." Each Jev request took 0.2-0.3 s against
7-82 s character calls. Fixed the same day:

- **A mind's own earlier lines were felt twice.** A later round of a beat
  hands a mind its own conduct back (`loops.self_micro_view`); the pass read
  it again as a perceived event, and a magistrate's second round was given
  "gratification (You said: ...)" as how he felt now. `events_from` skips it.
- **Blame toward nobody named landed on "someone".** A concern has no actor,
  and "anger (someone)" was the layer beneath the same magistrate's mood;
  such a feeling is now about the thing -- the concern's own text.

**The own-act pride tilt, eased the same day** (the owner: "adjust the pride
tilt a bit"). "Did doing this honor something you value?" is true of almost
any line a principled character speaks, and pride took either that or a lift
in self-regard, so after the post-call pass the stored surface read "pride
(You said: ...)" for a teacher telling a boy to answer the magistrate. OCC's
pride is approval of a praiseworthy act, and a praiseworthy act is the one
that also leaves a mind thinking better of itself: pride now needs both
(`emotions_from_act`). Measured on an act battery built for it
(`tools/jev_act_battery.py`, 19 acts): ordinary acts from pride 0.66 to
0.17, praiseworthy ones 0.86 to 0.72, blameworthy ones unchanged at 0.00;
expectations met 28 of 33 to 31 of 33, with no new question asked. A direct
"Is this something you are proud of having done?" met 32 of 33 but left
ordinary acts at 0.26 and costs a question in both languages.

**Several feelings at once, the same day** (the owner: "allow characters to
feel multiple moods if we aren't already"). The mood was always many
coordinates and the packet named four of them, but `now` and `beneath` each
held one feeling, so a mind lost the second one pulling the other way.
`now` now lists the present's feelings strongest first -- up to
`NOW_FEELINGS` (3), each at least `NOW_SHARE` (half) of the strongest, one
per kind -- and `beneath` up to `BENEATH_FEELINGS` (2); the prompt says they
may pull against each other. The stored `affect` keeps one surface and one
undercurrent, which memory rows and tells read.

**Feelings named, not derived -- and better questions, the same day** (the
owner: "We may need some better questions too potentially, anyways fine tune
and experiment"). Scored against two blind readers on the four stories'
beats (the evidence doc, "Round seven"):

- **Each event's feeling is named by the question "How does this make you
  feel?"** over OCC's event emotions and the standalone moods together, times
  "How strongly does this stir you?" (`affect_appraisal.EVENT_QUESTIONS`).
  OCC's rules named it at chance -- 17% and 22% of a reader's feeling family
  where the readers share 44% -- because the change questions ask whether a
  fear grew more likely and the rules named it a fear come true; named
  directly, 37% and 43%. A beat's `now` list overlaps each reader's own
  strongest three 55% and 65% by family, where the readers overlap 58%. A
  concern is named the same way, times its weight. An event costs two
  questions where it cost nine plus one per person.
- **The mood's questions ask whether a mood is one of the main things felt**
  ("Right now, is this one of the main things you feel? How strongly:
  {mood}?"): 4.7 moods read clearly per beat, between GLM's 4.8 and
  Gemini's 3.9, where the old wording read 5.6; against each reader alone
  the reading reaches r 0.64 and 0.59, the readers 0.66 with each other.
- **The worry question asks what a concern crowds out** ("In this moment,
  how much does this crowd out everything else?"): the concern battery's
  expectations met 15 of 21 where the old question met 9, and a worry still
  weighs on a quiet evening, which the best discriminator ("does what just
  happened bring this forward?", 20 of 21) would not allow.

**Frustration is the restraint's, once -- the same day.** Traced end to end
(the owner: "probe what jev answers with vs input and how the character
behaves as a result and ask if it makes sense";
`docs/experiments/AFFECT_TRACE_2026_09_26.md`), Jev read the moment apt and
conduct followed, but 15 of 16 characters' stored feeling after the call
was frustration: "was there something else you wanted to do or say
instead?" was asked of every act, and the held-back want listed beside them
made each say yes -- the pride tilt, moved to the next own-act feeling. The
owner: "Likely needs some question refinement." The held-back want alone is
now asked "How much do you mind not having done it?"
(`affect_appraisal.HELD_QUESTION`): 14 of 16 on a restraint battery,
costly restraints 0.89 against cheap ones 0.25, where the old question met
10. On the traced beats frustration is stored on 10 of 16 -- the restraint
each was about.

**The moment against the act, and the self-conscious feelings apart -- the
owner's rulings, the same day.** Two things remained, and the owner took
the recommendation on both ("Go ahead. also add embarrasment and related
fields"):

- **Like for like.** A moment's feelings split one stir among names by
  share, an act's feeling is whole, so the largest single feeling was an
  act's by construction. An act's feeling now becomes the stored one only
  where it outweighs everything the moment's strongest item stirred
  (`affect_mix.surface_and_undercurrent`); the `now` list and the mood's
  push are unchanged.
- **Shame, guilt, embarrassment and falling short, apart.** Shame is an act
  going against what the character believes is right -- the values
  question reworded from "something you value or believe", which read a
  violinist's stumble on stage 0.77, to right and wrong, which reads social
  mishaps 0.28 and wrongs 0.93. Guilt needs that AND the act having hurt or
  wronged someone, as pride needs both halves (a psychopath's kicked cup
  hurt someone, and is not his guilt). Embarrassment is others having seen
  the character make a fool of itself. Falling short of oneself is what an
  act below what the character expects of itself leaves once shame and
  embarrassment have named what was wrong or seen -- the fumble alone. On
  the act battery (32 acts: ordinary, praiseworthy, blameworthy, social
  mishaps, acts that hurt someone, fumbles with nobody watching) the
  shipped rules meet pride 18 of 20, shame 22 of 24, guilt 28 of 29,
  embarrassment 27 of 30 and falling short 12 of 14. Humiliation was not
  added as a mood: the coverage table has it as ashamed, powerless and
  embarrassed, and no rater named it uncovered.

The 16 traced beats, their after-call pass asked again with all of it,
store suspicion on 4, protectiveness on 3, dread, guilt, grief and
frustration on 2 each and a fear come true on 1: Wren keeps guilt at "Go
on, then", the captain dread at the letter; frustration stays where a
restraint outweighed a quiet moment (the captain walking out, unable to
learn what the medic understood, 0.94).

Still open: a memory-sourced feeling's object is its opening text, which for
a remembered scene is scene description ("resolve (You are in the
harbourmaster's shed...)"); marking it as remembered wants a pack phrase in
both languages.

**The moment is what stirred most as a whole -- the same day, late.** A
story played with characters written to show their feelings
(`docs/experiments/FEELINGS_EXPRESSIVE_CARDS_2026_09_26.md`; they did, as
plainly as their cards say, a reserved one did not, and how strong a feeling
they displayed rose with how strongly it was felt) found the like-for-like
rule taking "the moment's strongest item" as the item holding the largest
single feeling. A mixed event splits its stir among names, so the moments
that stir several things at once lost to a small gesture with one
concentrated feeling: a grandson's announcement that he is emigrating stirred
his grandmother 0.99 across dread, sadness, longing and distress, his
straightening in his chair 0.62 as dread, and she was handed and stored
dread about the chair. The strongest item is now the one that stirred most
as a whole, the surface its strongest feeling, and an act weighed against
that item's whole stir -- what the ruling's words said. Replayed over the 29
traced calls, the block names the most stirring event first on 27 of 27
(15 before) and the stored feeling is about a held-back want on 6 of 29
(8 before); the `now` list still adds what else pulls at once by single
feeling, one per kind.

**A memory keeps what its moment made the mind feel -- 2026-09-29.** The
owner: "i'm thinking of memory mood completely wrong, it should be a stored
value made at memory formation not one derived every turn"; "instead of
computing the mood each memory invokes, we use the moods of the beat based
on character perception and the pass based on how their actions make them
feel and store those. the decay should be slowish and it should never go to
zero", "because humans can reminisce a memory years ago with fondness".

What it replaced: every memory the payload carried -- the 30 recalled and
the recent turns, about 69 in the owner's chats -- was asked three questions
on every beat it came back (how strongly recalling it stirs you now, pleasant
or not, which of forty moods), from a one-line summary of it. On the two
played beats in the self-hosted decision model's request log (the r2 run of
2026-09-28) they were 162 of s27 beat 89's 218 before-call questions (54
memories) and 48 of s113 beat 104's 118; replayed on the tuned Winnow-12B the
pass took 75.6 s and 27.2 s of decision-model time with them and 10.5 s and
13.6 s without -- each quotes a whole memory over a long state, the costliest
question the pass asked. On the synthetic decision test set built the same
day they were also its least reliable, matching their labels 50-54% of the
time against 73% overall.

Built (`mind/affect_pass.py`, `mind/affect_mix.py`; the `memories.feelings`
column, schema v42):

- **Formed from the beat.** The before-call pass's event feelings -- what
  perception stirred -- and the after-call pass's act feelings -- what the
  mind's own acts made it feel -- by name, with the moment's strength: the
  item that stirred most as a whole. A row of what the mind perceived (the
  episode, a line heard, a conclusion drawn) keeps the first, the row of its
  own acts the second (`FACETS`). The layer beneath -- what a recalled
  memory or a concern stirred -- is kept by neither: stored into every new
  memory, a recalled feeling would copy itself forward without end. The
  rounds of one beat are one moment.
- **Brought back, fading slowly, never to nothing.** A recalled memory's
  kept feelings fade by its age on the mind's psych clock: a floor
  (`MEMORY_FADE_FLOOR`, 0.3) is never lost and the rest halves every
  `MEMORY_FADE_HALF_LIFE` (a week of story time; a unit a turn where no clock
  runs) -- 0.93 after a day, 0.65 after a week, 0.35 after a month, the floor
  after a year. Habituation dulls it as before, and its pull on the mood is
  curved by the faded strength (`MEMORY_MOOD_CURVE`), so an old memory is
  still felt, faintly, and barely moves the mood unless it was intense. Rows
  of one moment recalled together bring its feeling back once.
- **Read once, then kept.** A row that keeps nothing -- minted before v42, or
  on a beat no pass reached (the opening, a mind not called) -- and one the
  mind re-read (`disputed`) since what it keeps was found are asked the old
  three questions once; the answer is kept beside the moment, never over it
  (`record_memory_look`), and brought back at once it is exactly what asking
  gave (`tests/test_affect_mix.py`). An existing bank thins its questions out
  row by row as it is recalled.
- **The numbers are the code's; the mind gets a name.** The owner: "We should
  keep the spectrum values so we can do math with them but only the code
  derived memory name should be exposed to the character." A kept feeling
  carries its place in the mood's coordinates (`coords`: each spectrum and
  standalone mood its feelings move, how far and which way -- where
  `targets` would push the mood) beside the named feelings and strength. A
  delivered memory row no longer carries the mood it was formed in as
  numbers (`affect_before`: a label, valence and arousal; `affect_after_encoding`);
  it carries one word, `how_it_feels` -- its strongest kept feeling in the
  pack's words, named by the affect pass after it runs, so a row read afresh
  that call is named by that reading (`affect_pass.name_memories`). The
  columns stay written for the engine's recall lanes.
- **Carried like `disputed`.** Checkpoints, branches and archives carry the
  column verbatim; a bank imported into another story keeps what was felt
  but not its readings of the old story's clocks, and such a feeling reads
  as long ago (`tests/test_memory_feelings.py`).

Still open:

- **The beat's outcome.** A beat's episode row is the mind's view of the
  OUTCOME -- what the others did in parallel and what came of it
  (`perception_outcome`) -- and no pass appraises it: the before-call pass
  sees only what reached the mind before it acted, and the next beat hands
  the outcome back as memory, never as events. The per-beat memory questions
  used to carry its feeling into the next beat, weakly; the kept feeling is
  the lead-up's, so what the others did in response moves no mood. Options:
  appraise the outcome as events (at the next call, or in a pass after
  `perception_outcome`) and complete the episode's kept feeling with it --
  minding the interaction loop's rounds, which already appraise some of the
  same conduct -- or read the newest episode once at its first recall. The
  owner's call.
- **Nostalgia.** The three questions were where the moods whose object is the
  past came from -- nostalgia, grief, regret, longing. A kept feeling is what
  the moment felt like, so those now come only from a row being read (never
  kept, or re-read) or from a moment that itself stirred them. And the owner:
  "even negative memories in the moment can become nostalgic" -- so nostalgia
  cannot be a rule on a kept feeling's sign. Proposed: a one-time looking back
  when a memory first returns after it has aged past a stage (a day, a week, a
  month, a year of story time), asked with what the moment felt like, the
  answer kept as a reading. The owner's call.
- **The net's lanes.** `mind/memory_jev.py`'s feeling lanes still read
  `encoding_valence`, the whole mood at encoding; the kept feeling is the
  lane the research wanted.
- **Fading affect bias.** Unpleasant memories fade faster than pleasant ones
  (Walker, Skowronski and Thompson, 2003); the fade is symmetric, as the
  owner set the mood's negativity knobs neutral.
- **A clock that barely moves.** A played scene's clock tops out around three
  minutes (`mind/memory_time.py`), so within a scene nothing fades; a memory
  ages with story time -- a skip, a night -- not with the turn count.

**Increment 2 -- asked of the owner first:** the appraisal object
(`goal_impacts`, `somatic_impact`, `memory_modulation`), stress `coping_mode`
and `hedonic.released` feed stress, drive strain and pain and pleasure; each
needs a Jev question before its clause can leave the prompt.

## The bare contract

**Status: BUILT, 2026-09-27, and the only character contract since that day**
(`agents/character_bare.py`, `mind/character_jev.py`,
`tests/test_character_bare.py`): the owner committed the branch to decision
models, and the full card, its kernel compiler, its prompt paragraphs and the
`character_contract` setting were deleted so two contracts do not linger. What
is still open is UNBUILT §6.17.

The owner, 2026-09-26, in order: "Observe what other fields from the
character prompt can be handled by jev, one of my thoughts is memory
citation can be handled by jev the llm need only output a why"; "I thought I
told you to remove emotion completely from the llm and just handle before
and after with jev. The LLM just getting told it's mood at the start of it's
turn"; "The goal is to remove as much as possible and move it to jev so the
character is more focused on being a character"; "Can we also include the
models reasoning block in the jev post run?"; "the models still output some
whys, but jev can still likely find which memory that why and
action/thought/speech refrenced"; "I truly want an as bare bones character
prompt as possible. That still basically does the same thing thanks to
jev... except the character is now mostly reasoning about being the
character it's been given"; "Mind modeling and cross turn [note] taking so
the character knows roughly what it's been doing across turn and changes
what it thinks of other people are probably needed in some capacity still
insdie the turn. The good news is we can now gate parts of the prompts, Jev
can detect a disput and insert the disput payload deterministically".

### What was measured first

Three read-only surveys (2026-09-26, the code and 187 captured
`character_major` replies from 2026-09-13 to 2026-09-26 -- 2 distinct
characters across 14 branched chats, so indicative, not a population):

- **Where the reply goes.** Appraisal 25.3% of the visible reply, the
  update lanes 28.4% (readings of people 9.1%, intentions 5.6%), the rest of
  `state` 18.7% (wants 4.9%, decision 3.8%), sequence 16.0%, manifest 8.9%,
  citations inside all of it 7.4%.
- **Citations are gates, not data.** All 3,794 cited handles were rows the
  call delivered. What a citation does is mostly decide whether a value
  survives: no present row cited zeroes pain and pleasure, a goal impact,
  and trust/warmth/fear; no row drops a belief, an association or a reading.
  A few ids are read: a belief, reading or memory effect citing a memory
  raises its importance once; `reinterpret` picks the disputed row;
  `effects` feeds the unbidden-recall ledger; an intention's transition
  keeps its evidence for display.
- **No reader at all:** appraisal `goal_relevance / expectation / emotion /
  uncertainty`, `goal_impacts[].intentionality`,
  `memory_modulation.expectation / anticipatory_emotion`,
  `memory.effects[].use`, `people[].alternatives`, `interaction.yields_floor`,
  and `waiting_ops`, which is not in the kernel schema and never compiled --
  no character could give up on a promise. Read back only by the same model
  next beat: the decision's hinge and uncertainty, the coping mode, the
  memory echo's why, a belief's emotional charge, association texts, a
  tell's reason.
- **Reached only through the Director:** where a character looks, the room
  it walks to and its pace -- the Director reads the act's text and decides
  them. So the bare reply types none of them.
- **Repairs:** 9 of 186 first attempts failed, none on a citation -- belief
  target rules (since non-fatal), malformed JSON, a missing field.
- **Reasoning:** 143 of 187 calls returned a trace (the Claude route none),
  1.7x the reply's length; under 6% of it concerns citations.

### The card and the reply

The card is seven paragraphs (3.6k characters in English with the universal
language contract, against the full card's 22.8k of instructions): who you
are, what you have (`self`, `self.feelings` given and never reported,
`perception`, `memory` all past), where your turn ends, how you act, what
moves you, the notebook (below), and the reply:

```json
{"want":"","held_back":"","hinge":"","unsure":"",
 "sequence":[{"say":"","to":"","how":"","why":""},{"do":"","why":""},{"ponder":"","why":""}],
 "demeanor":"","tells":[],"changes":[],"note":"",
 "notebook":[{"id":"","about":"","note":"","sure":"","until":"","strike":""}]}
```

`do` is what the character tries, in a few plain words: only what a
stranger watching could see or hear its body do, only up to where the world
must answer whether it works, written without a subject (the renderer names
the actor for each observer); what it means, notices, remembers or intends
goes in `why`. Each step's `why` comes LAST: put first, it swallowed the
turn on 7 of 20 replayed beats.
What the character makes of people and things goes in its `notebook`
(below), `changes` is what changed in it, `note` a line to itself about what
it is in the middle of -- kept as `my_notes`, the last `NOTES_KEPT` (5), and
shown next beat beside the last decision. The payload gives the mood once,
as `self.feelings`: the coordinates, labels and ledgers behind it
(`MOOD_INTERNALS`, 1.3k-2.7k characters a beat on ten captured payloads)
leave `self.active_state`.

**Gated sections** ship only when the payload carries what they explain,
each a short paragraph: `dispute` (the decision model, before the call: does
what just happened change what a recalled memory meant? a yes-share of
`DISPUTE_FLOOR` (0.7; no replayed share reached 0.8, and at 0.5 the section
shipped on 13 of 20 beats) adds the memory to `memory.may_mean_otherwise`),
`drive_rupture` and its forced form, `project_review` (a project finishes or
is set aside by a strike in the notebook, with the reason),
`still_waiting`, `impossible_knowledge`, `carried_reports` (code) -- and,
restored 2026-09-27 from what the full card said on every beat and the bare
card had dropped, `their_silence` (`decision.they_said_nothing`),
`answer_owed` (`decision.awaiting_your_answer`), `offers`
(`decision.comes_to_you`), `speech_budget` (`decision.speech_budget` --
present every beat, as the full card's clause was), `crisis`
(`self.crisis`), `tell_variety` (`self.recent_tells`) and `tell_payoff`
(`self.tell_grounds`), 129-243 characters each in English -- and
`repetition`, the full card's self-repetition clause, shipped only when the
engine's own detector finds a shape the recent lines keep reusing
(`self.recent_self_refrain`), and `ways_on`, the full card's
spatial-frame, places and en-route clauses as one class, shipped with the
spatial frame: what the frame is, that a missing key means it cannot be
told from here, to name the place a walk is for rather than its first
step (the Director writes the walk from the act's words and carries it
across beats), and that a journey under way can be kept, stopped or left.

### What the decision model reads back

One request after the call (sharded at 64 questions, concurrently), one
state per mind: its card psychology, what it is after and believes, who is
here, what reached it, what it remembers, what it did with its whys, and its
reasoning trace when the provider returned one (`REASONING_CHARS`, 6000).
Every option is a row this mind was given or an item it holds, and "none" is
always one -- so a citation cannot be invented, and "none" drops a lane
exactly where commit would have dropped the model's.

| The full card asked the model for | Now |
|---|---|
| volume, `conceal_from`, visibility | `line_volume`; `line_kept_from` per person here -- never the addressee |
| `interaction.addresses`, `expects_response`, interrupts | `line_to`, `line_expects`, `line_interrupts` |
| `observable` (and "an inner act has none") | `act_seen`: an act no one could see or hear is imperceptible; otherwise observers get the parts of the act someone watching could tell -- THE OBSERVABLE FLOOR (2026-09-27): `do` split at its punctuation (`act_parts`), `act_part_seen` asked of each part, the Director given the whole attempt, and unread, only the first part. A motive written into `do` reached observers before it (probe: 8 of 8 inner parts caught, 19 of 23 visible kept); one with no punctuation around it still rides with its act |
| `targets`, follow, ending a contact | `act_target`, `follow`, `contact_end` per standing contact |
| an act's `look` (a body faced, or `around` for a sweep) and `interrupts` | `act_look` over the people here, all around, or no one -- asked alone too, since a sweep is how a mind takes in an empty room; `act_interrupts` over those who spoke, asked as what stops someone finishing, with a plain "No one." (an interruption truncates the other's line; that wording wrongly flagged 6 of 27 replayed acts where "cut off what someone is saying" flagged 11, both catching 4 of 4 made-up interruptions; walking away while someone talks is still read as one). Restored 2026-09-27 |
| wants' `serves` and `urgency`; enact/suppress ids | `want_serves`, `want_urgency`; the want is enacted, `held_back` suppressed |
| tells' `channel`, `subtlety`; "at most two"; "no subtler than 0.4 in a crisis" | `tell_channel`, `tell_subtlety`; `MAX_TELLS` (2) and, under `self.crisis`, the 0.4 ceiling in code |
| readings of people (`about_entity`, `kind`, `confidence`, evidence) | the character's notebook entries (below); `note_kind`, `note_about`, `based_now` / `based_memory` |
| beliefs: acquire, reinforce, weaken, revise with exact held text | a `changes` line sorted by `change_kind`; a line aimed at a held belief (`belief_target`) revises it in the mind's own words when it rests on something given and the pair check (`belief_replaces`, asked back after the read-back: is this that belief changed, or a different thought?) says it IS that belief -- the notebook's rule, since 2026-09-27; until then the decision model had to call the belief overturned as well, and without the pair check round eleven rewrote convictions with unrelated lines ("He can save more by staying numb than by feeling" became "Luca left the room and I let him go without a word"); a different thought is a belief of its own and overwrites nothing; per held belief the reply left alone, `belief_touched` asked against the moment alone (bore out, doubt, overturned: reinforce, weaken, weaken at the full step) |
| memory re-reading (`memory_ref`, evidence not the disputed row) | `which_memory` + evidence from anything else |
| intentions add/abandon (the character's) and progress/block/satisfy/nonviable | add and give-up are `changes` lines; `aim_moved` per steering aim |
| associations (reinforce, `extinguish`), relationships (+-0.05, +-0.2 on a real break) | `cue_present` and `cue_held` against the moment: a cue that came and whose reading proved true reinforces, proved untrue breaks the association (extinction), neither moves nothing -- every appearance used to reinforce, so a learned fear could only grow; five `rel_axis` steps x `REL_STEP` (0.05), x `REL_BREAK_STEP` (0.2) when `rel_break` -- the card's rule, now code |
| concerns, lines kept, memory effects, salience | new worries are `changes` lines or notebook entries, each kept once (`notebook.concern_id`) and held whole (`notebook.concern_text`); `concern_settled`, `keep_line`, `memory_shaped`, `salience` |
| giving up a promise (`waiting_ops`, dead in the kernel) | a `changes` line and `which_promise` |
| the appraisal: six axes, pain and pleasure with a named cause, goal impacts, the memory echo | `novelty`, `control`, `coping`, `norm`, `self_fit`, `pleasant`; `pain` / `body_pleasure` per event (the event is the cause); `impact`, `impact_certain`, `impact_agency` per live aim, the drive included; `echo` and its three grades, and `echo_body` for the signed `somatic_echo` (a tightening or a warmth; written as 0.0 on every bare beat until 2026-09-27). The full card never explained the field and its model wrote small positive strengths (0.01-0.4) on 129 of the 135 echoes in the four stories' captures, 0 on the rest, whatever the memory; `echo_body` came out unpleasant on 24 of round nine's 25 echoes in two grim stories (-0.16 to -0.93) and about nothing on the other -- unmeasured beyond that |
| `stress.coping_mode`, `hedonic.released` | `coping_mode` over the card's strategies; `released`, asked only above `RELEASE_ASK_FLOOR` (0.3) of charge |

**One behaviour change to watch:** the drive is now one of the aims every
impact is asked about. In the measured replies no impact ever served the
drive (0 of 227, owner decision 2 above), so drive strain -- and the
rupture window it opens -- had effectively never run.

**No second call.** When the reply cannot be read back
(`READ_BACK_ATTEMPTS`, 2), the beat the character wrote stands on code alone
and says so: a line goes to whoever its `to` names among the people here (a
set the engine owns, matched whole-word) at `pitched` volume -- loud enough
for them and no louder -- acts stay visible, and only what the character
wrote for itself is kept (its running note, and its notebook: new entries as
reminders, its own strikes and rewrites, and the nudges the note check made
before the call), as the mood already fails open. A first draft re-asked the
full card instead;
`test_no_quality_redo` held the line (one model call a beat), and a fallback
to the call being replaced is what the owner ruled out for the Room.
Speaking in a room is a channel, and voices lean toward carrying.

**Not carried, by measurement:** material effects (the substance ledger's
`release/deposit/add` from a character's own body). The Director's hands
own substances; the character's lane was a backstop for the Director
omitting one, and in the owner's database the Director's own resolve named
the same body for 61 of the 62 emissions full-card characters declared. Adopting a project is carried by the notebook
(below): an entry with `until` that the decision model reads as something
the character means to see through. One that adoption would refuse --
circular, or both slots held (`affect.adoption_refusal`, the one reader
adoption itself uses) -- is kept as an intention with what would finish it
in its words; a commitment refused a slot was simply lost in the round-8
chains.

### The notebook

**Status: BUILT behind the same setting, 2026-09-27** (`mind/notebook.py`,
`tests/test_notebook.py`; the routing in `agents/character_bare.py`).

The owner, 2026-09-27, in order: "A hypothesis is basicaly a note that can
be updated or refuted an important piece of a characters mind model of other
characters"; "hypothesis should be about anything in general I suppose but
also about characters"; "I needs stable core where a characters keeps track
of what it thinks about things and other people and how it thinks they
think"; "there should be a general note taking system for things the llm
wishes to keep track of"; "There should also be an active concerns section
that has a method of resolution. Well I suppose that is projects under a
different name"; "Lets not focus on minimal prompting, what do you think is
best but not extremely large?"; and on the context: "making sure the llm
still has acces to what it needs without letting it baloon".

**What it holds.** One view, `self.notebook`, in four sections, over stores
the engine already had or now has -- one store per kind of thing, no copies:

- `on_your_mind` -- the concerns (`active_state.active_concerns`, still the
  engine's plain strings). A worry the character raises carries what would
  settle it in its own words ("whether Kit hangs (settled when: Wat
  speaks)"), and the decision model's per-beat check (`concern_settled`)
  reads the criterion with it.
- `what_you_are_about` -- the projects (`affect.apply_project_ops`): an entry
  the character means to see through, with `until` naming its end outside
  the doing, is adopted -- two at most, on trial until lived into. One with
  no end to name is a task, and becomes an intention. A project closes only
  when the character strikes it (finished, or given up, with the reason).
- `people_and_things` -- what the mind thinks of people, of places and
  things, and what it thinks they think: the mind-model core
  (`theory_of_mind`), with three kinds for things (`THING_KINDS`: what it
  is, what happened, what will happen) beside the person kinds. Each note
  has a stable id (`note_id`); the character adds, changes (`revise`: new
  words, the same note) and strikes by it, and the decision model, asked of
  each note about a subject in play whether this beat bore it out, cast
  doubt on it or told against it, NUDGES its confidence -- never strikes
  it. A mind may hold to what the evidence is against; only it lets go.
  That check is asked before the call, in its own request, against the
  moment alone (`moment_text`: who is here and what just reached the mind,
  never its notebook, memories or aims). Asked after the call, 27 of the 29
  nudges in the round-8 chains were "bore it out" -- a man sitting down bore
  out an accusation, a mutter too faint to make out bore out who brought the
  news. Moved before the call against the whole state it was still 21 of 21
  in round nine: the question is about what just happened, and the decision
  model read the notebook's own copy of the note, and the memories that
  first supported it, as confirmation. On 56 hand-labelled checks (one
  labeller), beats that told the mind nothing new were called "bore it out"
  28 times of 34 against the whole state and 9 of 34 against the moment
  (agreement 24 and 40 of 56, real confirmations caught 16 and 14 of 16);
  the wording was not the cause (two rewordings scored 33 and 30). A note
  the reply changes or strikes itself is not nudged.
- `to_keep` -- reminders (`state["notebook"]`, `apply_notebook_ops`): facts
  and things to remember, kept until struck.

**The reply** gains one field and loses one: `notebook` (entries with `id`,
`about`, `note`, `sure`, `until`, `strike`) replaces `people`, whose lines
are still read as new notes. A new entry's kind and, when it names no one,
its subject are the decision model's; its sureness is the character's own
(`SURE_CONFIDENCE`), capped by its kind. A note about someone or something
rests on something this mind was given, as every reading does; one that
names no subject or rests on nothing is not lost -- it is kept as a
reminder in its own words.

**Context.** The store keeps everything -- notes fade by their kind and are
pruned below a floor, reminders are kept up to `REMINDERS_KEPT` (100) -- and
the view is bounded and chosen for the moment: every note about who and
what is in play first (the people perceived, the room, anyone or anything
named in what reached the mind, in its latest running note or in the recall
it asked for), then the strongest and most recently touched, at most
`PER_SUBJECT_SHOWN` (3) about any one subject and `NOTES_SHOWN` (16) in all,
narrowing to `NOTES_SHOWN_ABSORBED` (6) as the body takes the mind. A
reminder untouched for `REMINDER_STALE_TURNS` (40) leaves the view unless it
is in play. What is not shown is one `ponder` away. The view replaces four
renderings of the same stores in the payload (`mind_models`,
`active_hypotheses`, `self.projects`, the concerns), so the payload shrank:
82.3k to 79.6k characters on a replayed beat with six concerns and six
notes. The decision model's per-beat check runs only on shown notes about
subjects in play, which keeps it bounded -- and keeps a note from being
borne out by a beat about someone else, the way held beliefs, asked every
beat, came to be touched three times as often as the full card touched them.

**The knobs** (`mind/notebook.py`, the owner's): the view's sizes above,
`CONCERNS_SHOWN` (6), `REMINDERS_SHOWN` (6), `RECENT_TURNS` (3),
`SURE_CONFIDENCE` (certain 0.9, likely 0.65, guess 0.4), `NUDGE_TOWARD`
(bore out 0.85, doubted 0.3, told against 0.1, each moved by the kind's
plasticity), and the kinds for things' ceilings, plasticity and half-lives
(`theory_of_mind`: what it is 0.8 / 0.4 / 400, what happened 0.7 / 0.35 /
400, what will happen 0.6 / 0.5 / 45).

**Found building it:** the bare path kept only the first four concerns
(`MAX_CONCERNS`) and wrote back only those, so a mind with seven lost three
on every bare beat. Every concern is now kept; the six shown are checked.

**Measured** (`docs/experiments/BARE_CARD_REPLAY_2026_09_27.md`, round
seven, 20 beats): 10 held notes revised by id, 8 new (6 of the 7 about
people what someone thinks), 8 nudged, 4 reminders kept, concerns reworded
to carry what settles them; no note struck and no project taken up. The
kind question's first wording read the character's own plans as someone's
goals (4 of 9 on a probe); naming ANOTHER person for the person kinds and
saying what separates a worry, a commitment and a note to keep scored 11
of 13. Concerns are capped (`CONCERN_CHARS` 240, `UNTIL_CHARS` 120) after
the characters wrote paragraphs into them.

**Carried across a character's own captures** (round eight, the `--chain`
replay, 2026-09-27: each beat's compiled output applied the way commit
applies it, so the notebook is the character's own from beat to beat):
Margit (16 of 18 beats read back) wrote 20 new notes, revised 21 by id and
had 21 nudged; Anselm (16 beats) wrote 6, revised 6, changed a reminder 12
times and had 8 nudged. What it showed, and what changed for it: notes
drifted into a log of what happened (the card now says a note is one line of
what the character thinks, memory keeps what happened -- round nine still
wrote logs, so this is not settled); 27 of the 29 nudges confirmed (the
check now reads the moment alone, above); one concern appeared twice, cut at
two lengths -- the view derived a concern's id from its whole words while
the read-back held it cut at 300 characters, so a longer concern could never
be struck or rewritten by its id and each rewrite added a copy
(`notebook.concern_text` is now the one reader of a concern's words); a
commitment adoption refused as circular was lost (kept as an intention
now). Conduct cost nothing measurable against the same beats without the
notebook.

### How it was measured

`docs/experiments/BARE_CARD_REPLAY_2026_09_27.md`: 20 captured beats of the
four test stories (`betrayal`, `homecoming`, `lie`, `rival`), replayed on
GLM 5.2 thinking over the owner's NanoGPT subscription, one request at a
time, with `tools/character_bare_replay.py`. Six rounds:

- **Against the full card** (round one): as much conduct -- 1.2 lines and
  1.5 acts a beat against 1.65 and 1.8, the same words spoken -- read as well
  or better side by side, at a median 19.8 s against 88.6 s and 1,171 output
  tokens against 6,616. The decision model's two passes: 0.4 s each.
- **The booking** (rounds one and two): asked of each memory in turn, the
  read-back filed 165 memory effects where the full card wrote 11; one
  choice a beat brought it to 20. Intentions 57 to 22-30 (full card 15),
  beliefs 41 to 34-37 (full card 12, still open).
- **Where the why goes** (rounds three and four): first, it swallowed 7 of
  20 turns; last, none.
- **Time is a distribution on this route**: round four's exact condition
  ran at a median 84 s on ten beats, and 17 s when run again.
- **The layout** (rounds five and six): the owner's order -- the sheet, what
  the character holds, the moment with its feelings -- beat today's layout
  under two pairs of blind judges; putting the card last as well ran past
  the turn and wrote inner states into acts twice as often, while keeping
  it as the system message kept the fewest faults of the three.

Found on the way and fixed: a feeling named twice in the feelings block
(5d967d68), decision shards missing from the call ledger (c38ec2f6). Found
and registered: what `do` says is what observers get (UNBUILT §6.17).

## Owner decisions

1. **Absorption.** Under pain, pleasure or stress the packet is cut to 4 or 8
   rows today (59% of captured calls). Does a Jev packet override that, or does
   absorption scale it?
2. **The drive in goal impacts.** No measured impact has ever served the drive
   (0 of 227). Asking Jev about it would start feeding drive strain -- a
   behaviour change.
3. **Mood as a given.** The character is told how the beat lands instead of
   deciding it. **Decided 2026-09-26** (the owner: "we should remove all mood
   related machinery from the character prompt. and just have it fed to the
   character in it's packet. And have it update the moods again post character
   actions"); built in increments, below ("Wiring the affect pass").
4. **Order.** Proposed: the memory packet first, then the pre-pass, then the
   post-pass.
5. **The moment tag.** A new stored field on every memory, written by Jev at
   commit (one question a row), with backfill for existing banks.
   **Decided 2026-09-29, and not as proposed** (the owner: "instead of
   computing the mood each memory invokes, we use the moods of the beat
   based on character perception and the pass based on how their actions
   make them feel and store those"): the field is written from the affect
   pass's own answers, so no question is added at commit, and an existing
   bank is read one row at a time, the first time each is recalled, instead
   of backfilled ("A memory keeps what its moment made the mind feel").
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

- `waiting_ops` was taught (STILL WAITING, the full card's `character.txt:41`)
  and read at commit (`persist/commit_background.py:1655`), but the full card's
  kernel compiler never compiled it: no character could give up on a promise.
  The bare contract's `stop_waiting` change files it; the kernel is deleted.
- `docs/guides/MEMORY.md` §3 and §5 say k=16 and that recall bumps the access
  count on the spot; the code uses 24 and writes at commit.
- Memory `entities` hold the label a row was perceived under ("the beautiful
  young woman", "the player") beside the name ("Hinami"), so no entity lane
  can gather one person's rows; and witnessed scene rows carry none.
