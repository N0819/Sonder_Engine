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

### Emotion and mood, as designed with the owner

The owner, 2026-09-26: "we might actually be able to remove mood handling
entirely from the prompt. And code can combine moods into moods that are
actually combos", "I still imagine jev needs event context to handle how
events might change mood", "if we ask these questions after jev has crafted
the memory packet ... can we factor memories into mood?", and "habituation
should also have a decay rate." Measured so far: the evidence doc's "Mood as
a Jev job". Nothing below is built.

**Three layers** -- temperament, mood, emotion -- the structure of ALMA
(Gebhard, "A Layered Model of Affect", 2005), built for virtual characters:

- **Emotion** is fast, about something, caused by an event. Jev appraises;
  code names it.
- **Mood** is slow and diffuse, a point in pleasure-arousal-dominance space
  that emotions push and that drifts home. Code owns it -- the measured
  shape: carrying the mood and moving it part way toward Jev's reading beat
  pure persistence on every axis.
- **Temperament** is home and how easily the character is moved: the card's
  `stress_profile` and traits. No new card field.

**Order within the before-call pass:**

1. The memory packet (net, then Jev).
2. Each of the beat's events appraised with the packet in Jev's state --
   desirability, happened or might, confirmation of a hope or fear, who
   caused it, right or wrong by the character's standards, good or bad for
   someone they like or dislike, how much they can do about it (Lazarus;
   Scherer's component process model). Memory is the appraisal's context: a
   third lie is not a first.
3. Code turns appraisals into emotions by the OCC rules (Ortony, Clore and
   Collins, 1988), whose compounds are the combinations the owner describes --
   gratitude is admiration and joy, anger reproach and distress, remorse
   shame and distress -- each with its object ("angry at Hinami, who lied
   about the key before").
4. Memory-evoked feeling: for the packet's charged rows, does recalling this
   stir something now? The moment tag gives the direction; Jev whether it
   lands. Recalling a feeling brings part of it back (autobiographical
   recall is a standard mood induction), weaker than it was lived.
5. Code moves the mood: event emotions at full weight, memory-evoked ones at
   a fraction; decay toward temperament in psych units (story minutes where
   the clock runs, turns where it does not), the unit every affect decay
   already uses.

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
`mind/affect_appraisal.py` (the Jev questions); not wired into the pipeline.

- **The space.** A mood is a point `M` in forty-five coordinates: fourteen
  bipolar spectrums in [-1, 1] and thirty-one standalone moods in [0, 1] (the
  next section). It began as Mehrabian's three PAD axes; the owner widened
  it ("mood has way more dimensions than what you have mentioned", "spectrums
  of moods as coordinates as well as some moods that truly stand as their
  own", "cover all moods"). Temperament is a home point `H` in the same
  space; standalone moods' home is nothing.
- **Emotions.** Each emotion `e` has an intensity `i` in [0, 1] and a
  direction `v`: the coordinates it moves (`EMOTION_EFFECTS`) -- one row per
  OCC emotion, after ALMA's table (Gebhard, 2005), and one per standalone
  mood, itself in full and the spectrums it moves. An event yields both: the
  OCC emotions its appraisal gives, and each standalone mood it stirs (how
  strongly it stirs the character times that mood's share of "which of these
  does it stir most").
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
  memory related ... or their undercurrents at least"). A memory stirs the
  standalone moods named for it ("which of these does recalling it stir
  most"), the share none of them covers a plain pleasant or unpleasant
  feeling by its tone, all of it dulled by habituation. A concern stirs what
  the event rules give it, scaled by "how much is this weighing on you right
  now", and does not push the surface (`CONCERN_WEIGHT = 0`).
- **Names.** Mehrabian's eight octants (exuberant, relaxed, dependent,
  docile, hostile, disdainful, anxious, bored) for a compact label; the
  surface is the strongest feeling the present stirred, with its object; the
  undercurrent the strongest a memory or a concern stirred, when it reaches a
  floor -- else the strongest feeling of the other sign, or the mood when it
  disagrees with the surface.

Knobs, all the owner's, none tuned: reactivity, half-life, negativity weight,
negative decay factor, memory weight, concern weight, the undercurrent's
floor, and habituation's step, grace, ceiling and half-life. The card's
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

**Thirty-one standalone moods**, one graded question each: every category
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
  about wanting "to have" read every want as craving), curiosity (a want to
  know; engagement is attention, not wanting), anticipation (Plutchik's
  primary, eagerness for what is about to happen).
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
- **Not yet covered: greed** -- wanting to own or keep something. The
  battery's gold ring reads about zero on every coordinate that wants: it is
  neither an appetite nor envy. The owner's call whether it stands alone.

**Coverage.** How moods with no coordinate of their own sit in the system --
illustrations of the rule, not a list the engine matches against:

| mood | where it sits |
|---|---|
| content, serene | pleasant, calm, safe |
| excited | pleasant, energized, absorbed |
| anxious, worried | tense, threatened; hopeless when the worry is about what comes |
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
| suspicious | guarded, threatened |
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
| protective | tenderness, bold |
| predatory hunger | craving, bold, in command |
| aroused by being watched or shamed | sexual desire with embarrassment |

Code can name what the combinations make, as it names OCC's compounds (the
owner: "code can combine moods into moods that are actually combos"); none of
the rows above is built as a name yet. The blind rater in round three also
lists any mood a beat holds that no coordinate covers (the evidence doc).

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
  listed.
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
