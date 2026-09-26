# The mood battery

Constructed situations for testing the mood's coordinates
(`mind/affect_appraisal.py`, `mind/affect_mix.py`): does each question read
what it names, only that, and differently for different kinds of people? Run
by [`tools/jev_mood_battery.py`](../jev_mood_battery.py); results and what
they led to are in
[`docs/experiments/JEV_MEMORY_PROBE_2026_09_26.md`](../../docs/experiments/JEV_MEMORY_PROBE_2026_09_26.md).

The owner, 2026-09-26: "take inspiration from popular stories and real
psychological information as our test bed", and "how well does the mood
system align with particular types of people is good stress test data."

## `battery.json`

- **`situations`** -- each is one beat as the decision model reads it: `who`,
  optional `about` and `people`, what `happened` (an actor's line reads
  `Name: what they did`), what the character `remember`s. `expect` says what
  it should do: `high` or `low` for a standalone mood (low is for the moods
  it could be mistaken for), `+` or `-` for a spectrum's lean. Expect only
  what psychology would agree on; leave a mood out rather than guess.
  `inspired_by` names the paradigm or story beat, retold in new words.
- **`persons`** -- psychology profiles in the card's own fields (`drive`,
  `values` as trade-offs, `traits`, `self_model`), each grounded in a
  typology named in `inspired_by`; or a whole card, rendered as the decision
  model would read it -- `card_file` for a generated sheet kept in `cards/`,
  `card` for a character read by name from the open database (the owner's own
  cards stay there, never here).
- **`person_tests`** -- one situation lived by several persons, with the
  order psychology predicts: `tiers`, every person in an earlier tier reading
  higher than every person in a later one.

`python tools/jev_mood_battery.py check` validates the file and prints what
tests each coordinate.

## Refining a wording

Put candidates in a variants file -- `{"romance": ["romantic love or
infatuation", "..."]}`, a spectrum as `"low pole|high pole"` -- and run and
report with `--variants`. Only the new questions are asked (answers are
cached by question text), and the report prints each candidate beside the
pack's wording. The decision model grades an option by its words, so name
the class alone -- naming what a mood excludes pulls it toward that -- and
avoid words with a physical second sense.

## `acts.json`

The own-act half of the pass: does what a character just did make it feel
pride, shame or neither where people would? Acts of four `kind`s -- ordinary
acts that merely fit the character's values (pride should stay low),
praiseworthy acts that cost something (pride high), blameworthy acts (shame
high), and one act done by two kinds of people -- each with `who`, an
optional `person` from `battery.json`, the `context` it happened in and the
`act` in the pass's own words (`You said: "..."`, `You did: ...`). Run by
[`tools/jev_act_battery.py`](../jev_act_battery.py), which scores pride and
shame under the shipped rule and its alternatives, and any candidate pride
question passed as a JSON list with `--variants`. It is what eased the pride
tilt on 2026-09-26.

## `concerns.json`

The worry question: does a standing concern weigh on the character when the
moment brings it forward, and not when it does not? Each situation is one
beat (`who`, what `happened`) and the concerns the character carries into
it, one the event touches (`expect: high`) and background ones it leaves
alone (`low`); the quiet-evening situation touches none of them. Run by
[`tools/jev_concern_battery.py`](../jev_concern_battery.py), which scores the
pack's `concern_weight` question and any candidates (`--variants`, a JSON
list of question texts with `{concern}`) by what each reads high and low and
by the gap between the touched and the untouched. It is what replaced "How
much is this weighing on you right now?" -- which weighed every listed
concern about 0.75, since a concern is on the list because it weighs -- on
2026-09-26.

## Measured against readers, not constructed cases

Two instruments score the decision model against two blind raters (the
`utility` role routed to a different model family per database copy) on
captured beats of the four test stories, with the raters' agreement with
each other as the ceiling:

- [`tools/jev_mood_calibration.py`](../jev_mood_calibration.py) -- the mood
  coordinates, the pack's questions against candidate templates
  (`"_template"`), a which-mood-most question, and a per-mood linear
  calibration fitted on three stories and scored on the fourth. It chose
  the mood question's wording on 2026-09-26 and rejected the calibration.
- [`tools/jev_event_feelings.py`](../jev_event_feelings.py) -- the feeling
  each event (and each standing concern) is named, from OCC's event emotions
  and the standalone moods together: the engine's question against
  candidates, by exact name, by family of near-synonyms and by pleasant or
  unpleasant sign. It retired OCC's rules on 2026-09-26.

## `restraints.json`

What a character's held-back want costs it: each case is one beat -- who,
what happened, what the character did in the pass's own words, and the
want it held back -- with `expect` high where holding back costs (a nurse
kept from her own son's bedside by a stranger bleeding out, a humiliation
swallowed, a truth kept from a court) and low where it does not (a second
biscuit, a yawn, a retort one is glad not to have made). Run by
[`tools/jev_restraint_battery.py`](../jev_restraint_battery.py), which asks
each candidate question (`--variants`, a JSON list; `{act}` for any act,
`{want}` for the held-back want alone) of every act, so a report shows both
how a wording separates costly from cheap restraints and what it would read
of an ordinary act. It chose "How much do you mind not having done it?" on
2026-09-26, after "was there something else you wanted to do or say
instead?", asked of every act, made frustration what the story kept of 15
of 16 traced beats.
