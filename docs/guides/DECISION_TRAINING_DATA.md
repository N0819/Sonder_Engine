# Decision-model training data

For the day the engine gets a decision model of its own. The owner,
2026-10-06: "The best option would probably be to finetune a small decision
model maybe 4 or 9b parameters specifically for sonder. but for now using jev
is fine." Then: "I suppose we might as well build a training data file for
the day we decide to do a fine tune." This is that file: where it comes from,
what one example holds, and what in it can be trusted.

## What a decision model learns

`llm/decisions.decide(state, questions)` asks typed questions of one state
and every question is answered on its own -- one answer never informs another
(`llm/decisions.py`). So the unit of training is one **(state, question)**
pair and its answer, and a model of Sonder's own has to do exactly what the
engine asks of Jev today: read a state, read one question with its named
options, and give a distribution over those options (a `choice`), a
probability (a `noul`) or a position (a `score`).

## Two kinds of answer

- **Teacher** -- what the decision model the engine runs today answered, in
  Jev's own answer shape. Every question the engine asks of the same state is
  averaged over the times it was asked, with the count (`teacher.n`); Jev
  repeats agree to about ±0.03, so a count above one is a calmer target than
  any single answer. Teacher answers are only as right as Jev: they teach a
  model to be Jev, mistakes included.
- **Gold** -- the option that is right, known without any model. Few, and the
  only evidence that a model is *better* than Jev rather than like it.

## Where examples come from

| Source | Answer | Content | Where |
|---|---|---|---|
| Play, while capture is on | teacher | the install's own stories | `training/decisions/<database>/<day>.jsonl` beside the database |
| The router's labelled questions | gold | synthetic | `tools/chrono_bench/router_tuning.json` (train), `router_heldout.json` (eval), built by the builder |
| The concept lab's people present | gold | synthetic | `tools/concept_lab/bank_large.json`, built by the builder |
| Saltmere bench runs (`tools/chrono_bench/run.py`) | teacher, gold on moment checks | synthetic | captured beside the bench's scratch database |
| The committed seed | both | synthetic | `tools/decision_data/seed_examples.jsonl`, read by every build |
| The judges' rulings | corrections to gold | -- | `tools/decision_data/rulings.json`, applied by every build |

**What a build holds today** (2026-10-06, no play captured yet): 1,667 gold
examples -- `memory_met` 749, `memory_moment` 413, `route_order` 158,
`route_who` 146, `route_past` 88, `route_kind` 63, `memory_heard` 37,
`memory_anchor` 13; 1,492 English, 175 Japanese; 1,308 train, 359 eval -- of
which 535 carry the teacher's answer too.

**Capture.** The settings panel's *Debug capture* section has "Keep
decision-model training data" (the `decision_capture` setting, also
`PUT /api/debug_capture {"decisions": true}`). Off by default. While it is on,
`decisions.capture` appends one JSON line for every request the decision model
answers -- the state, the questions with their options, the answers, the model
that answered, the story frame and step that asked, the story's language -- to
`training/decisions/<database name>/<day>.jsonl` beside the database. A
scratch or replay database writes beside itself, so its requests never mix
with the install's. `training/` is gitignored: **every line holds story text**,
and from a real chat that is the owner's story. A capture that cannot be
written costs nothing -- the decision is already made.

**What it costs.** Measured 2026-10-06 on one Saltmere beat (Mara answering a
question, routing on): 11 requests and 474 questions -- memory grades 124,
moods 40, the act and change checks, what was said and done -- **0.6 MB**, a
fifth of that gzipped. A routed ponder alone is about 165 KB. A long session
with two major characters is a few hundred megabytes; the builder reads
`.jsonl.gz`, so an old day's file can be gzipped where it lies.

**The gold labels.**

- *Router.* Each labelled question is built exactly as the engine builds it
  (`memory_routes.question_state`, `route_questions`), and each route question
  its labels decide becomes an example: `route:order` (every accepted order --
  an ambiguous question accepts two), `route:kind` and `route:past` = yes only
  for a question about a moment, `route:who` the person's option or `none`. A
  content question is never labelled with a kind or a past -- "what did Tobin
  say?" is about the past or not depending on the reader.
- *Saltmere.* A moment check (`character_jev.memory_met`, `memory_moment`,
  `memory_heard`, `memory_anchor`) on one of the bank's questions is labelled
  from its planted turns: **yes** for the planted episode; **no** for a row on
  the far side of it, which adversarial readers checked holds no instance --
  before a planted first, after a planted last, anywhere for a question nothing
  in the bank answers. Everything else stays unlabelled: a later instance of a
  first time is still an instance, and an inference written the same beat may
  only think back on the moment. The kind decides which check a label fits (a
  first meeting labels `memory_met` and `memory_moment`, never `memory_heard`).
- *Concept lab.* `bank_large.json`'s `about` -- who is physically present in
  each of 240 memories, its best-audited label (four blind relabellings,
  persons agreeing at 0.94, 178 disputes ruled) -- as `memory_met`, rendered as
  the routed ponder renders a row (`memory_line` at the verifier's length, the
  "with" tags included): every present person yes, every person the memory
  mentions who is not there no (the hard case: 232 of them), and one person it
  never mentions no.

**The seed.** What the benches paid for is kept in the repo: every example a
bench run captured that has a gold label, with the teacher's answer averaged
over its runs -- 535 from the 2026-10-06 Saltmere runs (six retrieval runs of
82 questions and a smoke test). Every build reads it first, and writing it
again (`--gold-only --captured-only --out tools/decision_data/seed_examples.jsonl`
with the new bench captures) merges rather than replaces, so it grows.

**The rulings.** Every gold label the teacher disagreed with was put to three
blind judges, each shown only the state, the question and its options. All
three against the label relabels it; two of three drops it; otherwise it
stands, marked `ruled`. Of 43 disagreements on 2026-10-06, 40 labels stood --
Jev read a memory that only talks about an act as the act, a lantern as the
Lantern Inn, the mill seen from mid-river as being there -- and 3 were
relabelled: router tuning items whose `who` said "no one in particular" for a
question that plainly names someone ("how long have you known Ilse?"). A
ruling is keyed by example id, so it applies only to the exact wording it was
made on.

**How good the teacher is, where gold says.** On the moment checks Jev agrees
with gold on 379 of 413 (`memory_moment`, 92%), 37 of 37 (`memory_heard`), 10
of 13 (`memory_anchor`); on the router examples it was asked, 59 of 63.

## Building the file

```bash
python tools/decision_data/build.py                       # install captures + seed + all gold
python tools/decision_data/build.py --summary             # counts only, writes nothing
python tools/decision_data/build.py --captures DIR --no-install-captures --out FILE
python tools/decision_data/build.py --gold-only           # only labelled examples
```

The default output is `training/decision_examples.jsonl` beside the database.
`--captures` takes request files or folders (read recursively, `.jsonl` and
`.jsonl.gz`); `--no-seed` leaves the committed seed out. The 2026-10-06
bench captures themselves (teacher answers on 15,000 synthetic questions,
most of them the graded ponder's) are kept gzipped in the main checkout's
gitignored `output/decision_data/chrono_bench_2026-10-06/`, not in the repo.

## One example

```json
{"id": "…20 hex…", "task": "character_jev.memory_moment", "key": "moment:3",
 "language": "en", "state": "Wren ASKED YOU: When did you first light the green lantern?",
 "question": {"type": "choice", "instructions": "Does what the question asks about …\n\nMEMORY (…): …",
              "criteria": {"yes": "…", "no": "…"}},
 "teacher": {"type": "choice", "probabilities": {"yes": 0.91, "no": 0.09}, "choice": "yes", "n": 3},
 "gold": {"accept": ["yes"], "source": "chrono_bench/questions.json#Q10"},
 "split": "train", "group": "chrono_bench/questions.json#Q10",
 "sources": ["capture:rep1_on/2026-10-06.jsonl"], "steps": [], "models": ["typesafe/jev-1.13"]}
```

- `id` -- a hash of the state and the question: the same question of the same
  state is one example however often it was asked.
- `task` -- the card text the instructions were filled from
  (`character_jev.route_order`); a question no card text opens is named by its
  key with the numbers taken out (`key:moment:#`).
- `split` -- `eval` for the router's held-out set, `train` for its tuning set
  (the wording was chosen on it); otherwise a group goes whole to one side (a
  Saltmere question, a concept-lab memory, a story frame), about one group in
  ten to `eval`, so nothing a model is graded on was read in training.
- `gold.ruled` -- the judges' votes, where a ruling touched the label.

## What not to trust

- A teacher answer is Jev's reading, not the truth; report a model against
  `gold`, and against `teacher` only as agreement with Jev.
- Gold covers a few kinds of question (the router and the moment checks). A
  character's beat asks about 470 questions, and most kinds -- the ponder's
  grades, moods, acts, what was said -- have only Jev's answer to learn from. A
  model that matches gold there and Jev everywhere else is the realistic aim.
- Every gold label was written by a model (agents writing the banks and their
  labels, and judges ruling the disputes), checked by code where code can, by
  adversarial readers, and -- where the teacher disagreed -- by three blind
  judges. None was written by a person.
- More gold exists in the repo and is not built yet: the mood, act, concern
  and restraint batteries (`tools/mood_battery/`, whose wording was tuned
  until Jev met about 97%, so they measure agreement with Jev more than
  truth), the concept lab's superseded pairs (30 positives for
  `memory_supersedes`), and the walk and entities probes kept only in old job
  scratch.
- The Saltmere bank is one story by one set of writers; a model tuned to it
  learns Saltmere. Real captures are what make the data the engine's.
