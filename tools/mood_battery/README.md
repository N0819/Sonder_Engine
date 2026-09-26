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
  typology named in `inspired_by`.
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
