# Maze experiment: the arm registry

Every arm of the spatial-learning experiment, what question it was run to
answer, and what changed between it and the arm before. Findings live in
[`SPATIAL_LEARNING_EXPERIMENT.md`](SPATIAL_LEARNING_EXPERIMENT.md); routes
live in [`MAZE_RUNS.md`](MAZE_RUNS.md). This file exists so that no result is
ever compared against a baseline it does not belong to.

That is not hypothetical. Two mistakes on this experiment came from exactly
that: `shortest_path` bound its endpoints as default arguments, so every
resized maze silently measured the distance to the 6×6 corner, and
`render_maze_runs.py` hardcoded the 9×9 seed, so any other arm's real routes
were drawn against invented walls. Both produced numbers that looked fine.

## Reading an arm

Each results file (`--out`) opens with a `meta` line carrying grid, start,
goal, optimal, the models, the commit, the exact argv, and — since A11 — the
maze's own `edges` plus a `maze` fingerprint. Render its document with:

```bash
python tools/render_maze_runs.py <runs.jsonl> -o docs/maze/A9-9x9-trinity.md
```

**One document per arm, named for the arm, never a shared filename.** An arm's
document is a record of runs that happened once: the models are not
deterministic and the accumulated memory is part of the experiment, so it
cannot be reproduced. Rendering a new arm onto an old path destroys evidence —
done once already, to the sight arm, whose traces were replaced by A8's and had
to be recovered from git. The renderer now refuses to overwrite. Index each new
document in [`MAZE_RUNS.md`](MAZE_RUNS.md).

The same rule applies to findings: add a new section to
[`SPATIAL_LEARNING_EXPERIMENT.md`](SPATIAL_LEARNING_EXPERIMENT.md) for a new
arm rather than editing an earlier arm's numbers into it. A result that is
revised rather than added to loses the thing that made it worth having, which
is what was believed before.

Arms recorded before that header existed are marked *pre-header* below; their
maze parameters here are the reconstruction, and the renderer will refuse them
until a `meta` line is added by hand.

## Authored mazes

Up to A10 every maze was generated: a seed plus a carver name, regenerated on
demand by the harness and by the renderer. That is reproducible only for as
long as nobody touches a carver, the braid loop or the Python RNG — and the
renderer rebuilding walls from a recipe is exactly the mechanism that drew A5's
real routes against A8's invented walls.

`--svg` takes the maze from a file instead:

```bash
python tools/maze_experiment.py --svg tools/mazes/maze7x7-a11.svg ...
```

It parses the `<line>`-per-wall SVG that mazegenerator.net emits, and takes
**start and goal from the gaps in the outer border** — the generator's entrance
and exit — so the start is wherever the author put it rather than always
`(0,0)`. Exactly two openings are required; a maze with none, or three, is
rejected rather than guessed at, as are diagonal segments, a walled-off exit,
and a file with no `<line>` elements at all. Every one of those produced a
plausible-looking maze during development.

Two things follow. A maze can now be *chosen for its shape* rather than
accepted from a seed — which is how A11 exists. And results files now carry
their own `edges`, so a rendered arm is reconstructed from what was recorded
rather than re-derived from a recipe. `--resume` guards on a hash of those
edges instead of on grid-size-plus-carver-name, which was only ever a proxy:
two arms at the same size and algo but different seeds are different mazes,
and an authored maze has no algo at all.

The parse of the checked-in fixture is pinned by `tests/test_maze_svg.py`. If
it drifts, an old arm's routes would render against different walls — silently,
and with every derived annotation still looking like measurement.

## Fixing code mid-experiment

A Python process cannot reload its own modules, so a bug found at beat 60 used
to mean choosing between finishing an arm you know is wrong and throwing away
hours of accumulated memory to fix one line. Neither is a good trade, and the
second is why `--state` exists.

```bash
# run with a checkpoint (rewritten after every beat, costs nothing unused)
python tools/maze_experiment.py ... --state /tmp/arm.json --out /tmp/arm.jsonl

# stop it, fix the code, then carry on from the beat after the last completed one
python tools/maze_experiment.py ... --state /tmp/arm.json --resume /tmp/arm.json
```

Everything the character *is* — memory, mind models, `chat_chars.state`, route
knowledge, his position — already lives in the run's SQLite database, so resume
only has to rescue this process's own bookkeeping: which run and beat, the
route so far, finished-run metrics, and the RNG stream. It refuses to resume
onto a different maze, since that would carry one maze's route knowledge into
another.

A beat inserts its turn row before any stage runs and checkpoints only once it
completes, so killing the process in between — exactly what stopping to fix
code does — leaves a turn for a beat that never happened. Resume discards those
rather than colliding on them.

## Standing constraints

- **Arms run on current code.** An experiment with a known flaw in it is not
  cheaper than one that was restarted — it is worthless, and worse, it looks
  like data. When a fix lands mid-arm, stop and `--resume`; when the arm
  predates checkpointing, restart it.
- **One variable per arm** wherever possible. Where an arm bundles two, it
  says so and says what that costs.
- **Maze size is capped at 10×10.** Larger grids cost hours per arm for
  little extra signal — the 12×12 has nearly double the junctions of the 9×9
  at the same mean trap depth, so it tests endurance rather than navigation.
  The one 12×12 arm below predates the cap and was stopped on cost once it
  had banked the comparison only it could supply.
- **Room count is not difficulty, and it is not cost either.** Both are set by
  the optimal path and the trap profile. The 7×7 of A11 holds 60% of the 9×9's
  rooms and yet needs *more* moves to solve (28 against 20), because more than
  half its rooms are on the route. Read the `traps:` line the harness prints
  before assuming a smaller grid is a cheaper or easier one.

## Models and providers

Character is the only *deliberating* role; director, perception, mapping and
utility transform rather than decide. So the character model is where quality
and cost both concentrate, and it is the only one worth arguing about.

Measured on this workload (not vendor figures), per character beat:

| | in/beat | out/beat | $/beat | $/5-run arm |
|---|---|---|---|---|
| `arcee-ai/trinity-large-thinking` @ 0.22/0.85 | 9,502 | 6,265 | **$0.0074** | **$2.22** |
| `x-ai/grok-4.20` @ 1.25/2.50 | 15,407 | 5,398 | $0.0328 | $9.83 |

Trinity's input figure is lower partly because it had fewer beats and so less
accumulated route history; normalising it to grok's input still leaves it
**3.8× cheaper**. Note it emits MORE output tokens than grok — a reasoning
model's cost is the tokens it chooses to think in, not merely its rate.

**Provider.** Two endpoints serve trinity. Direct A/B, same prompt, four calls
each:

| | measured | quantization |
|---|---|---|
| Arcee AI | **184 tok/s** (median 200) | full |
| Parasail | 145 tok/s (median 145) | fp4 |

Arcee wins throughput by ~27% and serves unquantized weights, which matters
more for a reasoning-dependent model than the speed does. Parasail is better
only on time-to-first-token (412ms vs 477ms) — irrelevant here, since a
character call generates 5–7k tokens and TTFT is under 2% of it.

Routing is set to `{"sort": "throughput", "order": ["arcee-ai"]}`. `order`
rather than `only`, because the routing block is GLOBAL and rides every
OpenRouter request in the app: `only` would hard-restrict mercury and grok
calls to a provider that does not serve them.

Beware comparing throughput across log windows. An earlier reading made pinned
Arcee look *slower* than mixed routing; a controlled A/B reversed it. Load
varies, and two samples taken an hour apart are not an experiment.

---

## Arms

| # | maze | question | code state | status |
|---|---|---|---|---|
| A1 | 6×6 dfs | does anything carry across runs at all? | pre-header | done — retention proven, run 2 replayed the exact 20-move optimum from a wiped context |
| A2 | 9×9 kruskal | does it hold at triple the junctions? | pre-header | done — the baseline table in the experiment doc |
| A3 | 9×9 kruskal, affordances ablated | how much of A2 was the visited-exit markers? | pre-header | done |
| A4 | 9×9 kruskal + frontier arm | does `no_new_ground_that_way` break dead-end corridors? | pre-header | done |
| A5 | 9×9 kruskal + sight arm | do corridor sightlines help? | pre-header | done — best arm; reached the goal |
| **A6** | **12×12 kruskal** | does it scale, and does `worked_before` stop the run-3 drift? | `f8678f2^` → killed at 70 beats | **baseline** for A7 (bearings absent) |
| **A7** | **12×12 kruskal** | same maze, bearings fix present | `f8678f2` | stopped at run 2 — cost |
| **A8** | **9×9 kruskal** | replication of A2's maze with everything since | `994c815` | **done — 2/5 reached, run 5 an exact optimal traversal** |
| **A9** | **9×9 kruskal** | can a cheaper character model do the job? | `af92270` | stopped — superseded by A10 after a harness crash and a resume onto carried-over memory |
| **A10** | **9×9 kruskal** | A9 again from a blank state, all fixes present | `b0d2c13` | stopped at run 2 beat 34, checkpoint intact — run 1 matched grok's run 1 almost exactly |
| **A11** | **7×7 authored** | does a durable place graph fix the repeat-run opening thrash? | `124b717` → `94637dd`+ | **done — development arm; four fixes landed mid-arm, see below** |
| **A12** | **7×7 authored** | A11's question again, on settled code | `94637dd`+ | **done** — the clean arm; see below |
| **A13** | **7×7 authored** | a second subject, and cross-affordance interaction | post-A12 | **done** — the richest arm for psychology; see below |
| **A15** | **7×7 authored** | project tier under boundary review | post-A13 | **done** — run 5 measured prompt-normative boundary review NOT holding, which is why v2 is engine-gated |
| **A14** | **7×7 authored** | one configuration end to end, no mid-arm fixes | — | **not run** — the only thing missing from this table ([`UNBUILT.md`](UNBUILT.md) §7) |

### A6 / A7 — the bearings pair

The only clean single-variable pair in the set: same maze, same seed, same
models, same everything, differing solely in whether a visible onward exit is
named by bearing or only counted. A6 was stopped at 70 beats of run 1 when the
cause was found, so the pair is complete only for the opening stretch.

A6's failure is the one A7 exists to retest. Between beats 41 and 53 he
oscillated in the `0505`/`0504`/`0605` pocket, and the Director answered him
four separate times with *"moves west into Chamber 0504 and stops, as no
further west exit exists"* — he had been given `onward_exits: 1` for that
chamber with no bearing, and read it as a promise to continue west. The one
other way out went north.

Matched-beat comparison through beat 20:

| | A6 (no bearings) | A7 (bearings) |
|---|---|---|
| immediate reversals | 4 (22%) | 2 (11%) |
| rooms found | 12 | 14 |

A6 in full, before it was stopped: 70 beats, 31 rooms, 18 reversals (26%).

At 47 beats, the fullest matched comparison the pair reached:

| | A6 (no bearings) | A7 (bearings) |
|---|---|---|
| immediate reversals | 10 (22%) | **3 (7%)** |
| rooms found | 22 | **26** |
| new-ground rate | 47% | **55%** |
| beats in the `0505` pocket | 19 of 70 | 0 of 47 |

Reversals fell by two thirds while discovery ROSE, which is the signature
worth having: not a more cautious character, but one no longer spending beats
re-deciding what sight had already settled. The pocket figure is weaker
evidence than it looks — he routed elsewhere entirely and never faced that
trap, so he did not resist it.

**A7 was stopped during run 2, on cost.** Final: run 1 85 beats / 33 rooms /
24% reversals; run 2 29 beats / 8 rooms / 37% reversals, locked. 114 character
calls and 60 minutes of generation time for those two runs. A 12×12 costs
roughly triple a 9×9 per run and, at the same mean trap depth, buys endurance
rather than navigation — which is why the standing cap is 10×10. The bearings
result above was already banked; run 2 was buying nothing but a demonstration
of the circling lock, which is now reproduced far more cheaply as a unit test.

### A9 — the cheap-character arm

Same maze as A8, same support models (`inception/mercury-2`) at the same
reasoning (`low`), differing only in the character: `arcee-ai/trinity-large-thinking`
in place of `x-ai/grok-4.20`. Character is the sole deliberating role, so it is
the only one where model choice should show, and it is also the expensive one
— if a cheaper model navigates comparably, that is the whole cost profile of a
session.

Reasoning is deliberately NOT matched: trinity runs at `medium` against grok's
`low`. Trinity is a thinking model and reasoning-dependent, so pinning it to
`low` would measure a handicap rather than the model. The arm therefore answers
"is trinity good enough at the setting one would actually use" and not "is
trinity better than grok at equal effort" — a different and less useful
question, since nobody would run it at low.

A first launch had to be discarded: `--reasoning default=low` leaves
per-role entries already in `engine.db` standing, so `perception` was running
at `high` while A8 ran it at `low`. Perception is the character's entire input,
so that would have made the two arms incomparable while looking like a clean
model swap. Every support role is now pinned explicitly.

Early latency is far more variable than grok's steady 25–35s — observed 7s to
79s per call — so the throughput question needs a full run to answer, not a
sample.

### A11 — the authored 7×7

The first arm on a maze chosen rather than generated:
[`tools/mazes/maze7x7-a11.svg`](../tools/mazes/maze7x7-a11.svg), entrance at
the top of column 3, exit at the bottom of the same column.

```
+---+---+---+   +---+---+---+     S start (entrance gap)
|     *   *   S     |       |     X goal  (exit gap)
+---+   +---+---+   +   +   +     * the 28-move optimum
| *   * |           |   |   |
+   +---+   +---+---+   +---+
| * |       | *   *   *   * |
+   +---+---+   +---+---+   +
| *   *   * | *   * | *   * |
+---+---+   +---+   +   +   +
|         *   *   * | * |   |
+   +---+---+---+---+   +---+
|   |       | *   * | *   * |
+   +   +   +   +   +---+   +
|       |   | X | *   *   * |
+---+---+---+   +---+---+---+
```

49 rooms, 4 junctions, 6 dead ends, no loops. **Optimal 28 moves** — and that
number is the point of the maze. Measured against the arms it will be compared
with:

| | rooms | junctions | optimal | on route | worst trap | deep traps |
|---|---|---|---|---|---|---|
| A2/A8/A10 9×9 kruskal | 81 | 21 | 20 | 25% | 15 | 16 |
| A11 7×7 authored | 49 | 4 | **28** | **57%** | 8 | 3 |

So it is **not** a smaller version of the 9×9; it is a different instrument,
and expecting it to be cheaper or easier because it has fewer rooms would be
wrong on both counts. The 9×9 is a trap maze — a quarter of it is route and
sixteen branches run three-plus rooms deep, so it measures whether a character
resists committing to a wrong turn. A11 is a **corridor** maze: four junctions
in the whole grid, but the correct answer is a 28-move sequence through 57% of
the rooms. Getting lost there is not misreading a junction, it is losing the
thread of a long route — which is precisely what the durable place graph is
built to prevent, and what the run-2 opening thrash looks like.

The cheapness is real but comes from the room count, not the run length: less
accumulated route history per beat, so a smaller prompt. A successful run is
*longer* than a 9×9 run, so `--max-steps` should not be cut proportionally.

**A11 is a development arm, not a controlled one.** It was run while the code
under it was being fixed, and four things landed mid-arm. Recorded here so no
one later reads its five runs as a series:

| from | change | why it could not wait |
|---|---|---|
| run 1, beat 20 | characters get an egocentric heading (`22bbef8`) | the Director was moving him backward and narrating it as the direction he asked for |
| run 1, beat 40 | `max_output_tokens` reaches the caller (`c976385`) | beats were dying on truncated JSON at exactly 16000 tokens |
| run 2, beat ~2 | Director gets compass bearings (`94637dd`) | one movement event in seven still named a bearing the rooms contradicted |
| run 2, beat ~25 | running: multiple rooms per beat ([`DESIGN_RUNNING.md`](DESIGN_RUNNING.md)) | a courier whose craft is speed could only ever walk |
| run 3, beat 29 | `unentered` splits from `closed` | the shrine is a cul-de-sac, so the affordance layer argued against the destination for being a destination — it was never entered in any run |

A11 also produced two findings that are about the ARM rather than the engine,
and both bear on how its numbers should be read.

**Running was measurably unavailable.** Of 96 runnable passages, 72 allowed
exactly one room and `winded` never fired anywhere — the maze is a perfect
maze whose corridor cells are mostly bends, and the first version of the rule
stopped a run at a bend. So for the whole of A11 the capability existed and had
almost nothing to act on. The rule is now bounded by decision rather than
sight; see [`DESIGN_RUNNING.md`](DESIGN_RUNNING.md) §3.

**His goals decayed while the bug was live.** By run 3 `ia1` ("reach the shrine
as fast as possible") was **abandoned** and `ia3` ("beat your own best time")
**blocked** — the intention system correctly retiring goals that had yielded
nothing for 150 beats. But the reason they yielded nothing was the `closed`
verdict on the shrine. A defect that persists long enough stops being a defect
and becomes a belief, and then an abandoned goal; fixing the world does not
fix the character. Any arm that runs long enough to decay its own subject needs
its intention state inspected before its numbers are believed.

Runs 1 and 2 also differ in an unglamorous way: run 1's first nineteen beats
were **discarded and restarted from blank**, because the Director's bearing
errors had taught him the maze rearranged itself ("the maze layout sometimes
differs from memory") and a mind that has concluded that will discount its own
true map for the rest of the arm. The place graph was *not* corrupted -- it
reads the committed scene, not the prose -- but memory and belief are minted
from the prose, and that is what he reasons with.

So the comparable numbers here are **run 3 onward**, and even those are not
comparable to A8 or A10: running changes what a move costs, so `moves` and
`excess` mean something different once it lands. The learning question A11 was
built to answer -- do repeat-run openings stop oscillating -- wants a clean
arm on settled code. That is A12.

What A11 is genuinely evidence for is the bugs it found, each of which was
invisible in ordinary play and none of which any test had caught.

It is a perfect maze (0 loops), so the braiding argument in `build_maze`
applies: reversing out of a dead end is correct play, and the reversal count
cannot distinguish it from being lost. With six dead ends and a 28-move
optimum the headroom is in **excess moves over 28**, which is the metric to
read here — not reversals, and not room coverage, since a full traversal covers
most of the grid either way.

### A12 — the same character, given something to want

**In progress.** The rerun is live; every number below marked *baseline* is
final, everything else is provisional.

A12 is not a new character. It is A11's Vesk continued — same database, same
46-node place graph, same 211 memories — which makes it the first arm to ask
whether a mind can *use* a map rather than build one. His snapshot before it
began is `~/sonder-maze-characters/vesk-a12-pre.db`.

**The reward was paired first, and had never been paired before.** In three
runs he had reached the shrine once (run 3, 28 moves, excess 0) — and the
interlude's `reached=True` branch had still never fired, because it is guarded
by `if run < args.runs` and run 3 was the last. Both interludes he had ever
received were the consolation branch: *"they fed you anyway, and you ate it
standing, chewing over where the way had gone wrong,"* valence 0.3. The
association he actually held was that running the maze ends in a mediocre meal.
Firing the reached branch by hand (valence 0.8, salience 0.85, eaten sitting
down) is what makes A12 an arm about a wanted destination at all.

Two errors in doing it by hand, both worth the warning. `--runs 3` made run 3
the last run and suppressed the interlude entirely. And calling `run_interlude`
from an imported module leaves `START` at its `(0,0)` default, so the memory was
location-tagged `r0000` instead of the entrance `r0003` — location-cued recall
would have surfaced his reward in the wrong corner and stayed silent at the
threshold where he starts. Set `GRID`/`START`/`GOAL` before calling any harness
function that reads them.

**The finding: he had no way to use a map he had.** BFS over his own place
graph — walked edges only — reproduces the true optimal path exactly, 28 rooms.
While holding that, he spent five beats at the entrance working out which way to
go, and walked into a wall. The affordance layer answers *"where have I not
been"* and nothing answers *"how do I reach the room I want."*

For a wanted **known** room that layer is actively wrong-signed. Every step of
his correct route reads `spent` or `circling` *because* he has walked it, which
is exactly why it is the route. He was overruling it in prose to move at all —
*"a known path toward Chamber 0603, despite 0203 being marked 'spent'"* — and
where he failed to overrule it he drifted backwards. He also could not derive
the direction by reasoning, placing the shrine back through Chamber 0403,
sixteen rooms the wrong way. Fixed in `6022d6d`; see the commit for the
scoping, which turns on `active_state.goal` rather than intentions.

**Only a character who wants something can find this.** Run 3's optimal 28 moves
were not route knowledge — his run-3 appraisals name Chambers 0606 and 0506 and
never 0603 at all, because `ia1` was abandoned. He was frontier-following, and
by run 3 the unexplored ground happened to lie along the optimal route. Every
prior arm was blind to this gap for the same reason.

| | A12 baseline (pre-`6022d6d`) | run 3, for contrast |
|---|---|---|
| beats | 34, never reached | 31, reached |
| idle / repeats | **14** | 3 |
| off-route rooms | 3 | 0 |
| furthest | optimal index 16, ended at 12 | — |

The baseline is the same character, same maze, same goal text, one variable.
Giving him something to want made him **worse** than the run where he wanted
nothing, which is the sharpest statement of the gap available.

**Running works, and this arm is where it first fired.** He declared *"Continue
east through Chamber 0204,"* resolved `r0203 → r0205`, two rooms in one beat —
and `r0204` was recorded `basis: walked`, a room he never stopped in, via
`passable_path`. Without that reconstruction the corridor he ran would have
stayed a hole in his map exactly where his feet went
([`DESIGN_RUNNING.md`](DESIGN_RUNNING.md) §4).

**Open, and not a navigation problem.** Removing *"never breaking stride"* from
his sheet did not remove it from him: it survives in 69 of his 222 memories and
he writes more of them every run. A character can revise a belief about the
world — that is what `disproven` edges are for — and has no mechanism whatever
for revising a belief about himself. He did reconcile it rather than obey it
(*"maintaining running stride"*), so it did not block running; but a sheet edit
cannot retract a disposition already lived, and that is worth its own design
note.

Two infrastructure notes. `max_output_tokens = 40000` plus a system prompt that
has grown to ~17.5k collides with the context ceiling of whichever OpenRouter
endpoint the request lands on — intermittent by routing, and it worsens as
memory grows, since the input side climbs every run. It is the far end of the
`c976385` tension: too low truncates his JSON mid-reasoning, too high collides.
And the live viewer was reading position out of block-buffered stdout, so it sat
kilobytes behind a healthy arm and read as a stall — twice. It now reads the
checkpoint (`17ad2ae`).

### A8 — the 9×9 replication

Reproduces A2's maze exactly (81 rooms, 21 junctions, 25 dead ends, 16 false
branches 3+ deep, optimal 20) against the current tree. It bundles two changes
versus A2 — `worked_before` outcome feedback and the bearings fix — so it is
not single-variable. It is still worth running because the two act on
different things and the A2 table separates them: bearings change how
efficiently unknown ground is cleared, whereas the run-3-to-5 *drift* in A2
was a route-retention failure, which bearings cannot explain. If the drift is
gone, `worked_before` is the credible cause.

### A13 — a second subject, and the day the affordances learned to talk to each other

Same maze as A11/A12 (`maze7x7-a11.svg`, 49 rooms, optimal 28). New subject:
**Orrin**, `--subject orrin`, a maze-solver rather than a courier. Vesk was
retired first, and the reason is the finding that produced the arm: his drive
essence was *"being the one who gets there — motion as proof of worth"*, so
motion IS the proof, any step satisfies it, and a step into unseen ground pays
more than a step along a proved route. Three correct sheet edits failed to move
that. Orrin's drive is solving, and a maze's solution IS the shrine, so the goal
is drive-serving by construction rather than by authored priority.

| run | beats | moves | idle | unique | backtracks | reversals | reached | excess |
|---|---|---|---|---|---|---|---|---|
| 1 | 60 | 45 | 15 | 24 | 37 | 6 | no | — |
| 2 | 58 | 41 | 17 | 23 | 36 | 5 | no | — |
| 3 | 66 | 48 | 18 | 32 | 35 | 9 | **yes** | +20 |
| 4 | 55 | 50 | 5 | 31 | 25 | 7 | **yes** | +22 |
| 5 | 31 | 26 | 5 | 20 | 12 | 2 | **yes** | **−2** |

Run 5's excess is negative because `moves` counts movement BEATS and a run
covers several rooms in one: 26 beats of movement across a 28-room path. The
first arrival in the whole experiment is run 3 — no Vesk arm ever entered the
shrine.

**Read this table with the caveats below.** It is not a clean five-run arm.

#### What the arm actually found

**A solving drive decodes whatever it is given.** Run 1 cost fourteen
consecutive beats standing under a rope ladder; by run 3 it had become a
symbolic theory of the whole maze — mirrors and feathers and a chalk circle as
an ordered *sequence*, with "decision-point chambers" as a category he invented,
and an association (*entering a decision-point chamber → speculate*) that made
it self-extending. Every one of his 10 learned associations rewarded the
behaviour that produced it. The full ledger of 18 beliefs shows the turn
precisely: the first five are plain observation, and from b44 every one carries
a reading the world never supplied.

The behaviour is not stupid, which is why the sheet is what changed: a maze
thick with authored detail is a reasonable place to look for encoded meaning,
and `expression` said *"reads every wall as information"*. It now says
CONNECTIVITY, and the taboo covers studying a room instead of testing a corridor.

**The scenery was winning because the shrine was empty.** After his first
arrival his state read `pleasure 0.45, source "hot barley and dark beer after
the run"` and not one belief anywhere mentioning the shrine. He walked 48 moves
to the object of the experiment and what registered was dinner, because the
reward was paid at the run BOUNDARY. A chalk circle rewarded attention with a
theory to build; the shrine rewarded it with nothing. Studying the chalk circle
was the better-reasoned choice and he made it for three runs. `reward_on_contact`
now pays in the room, on the beat, and the interlude states that another reward
is waiting.

**Three affordances, each locally correct, none talking to each other.** All
three surfaced inside one run and all three had the same shape:
- the exits carried the route to Chamber 0603 while the run offers carried
  nothing, so a 3-room `full_reach` run beat a 1-room step that named his
  destination — and ended four rooms further out;
- a stale intention naming Chamber 0504 outvoted his own goal, pointing 17
  beats of salience at the wrong room;
- a goal naming the WAYPOINT he was standing in silenced the standing shrine
  intention entirely.

**A finished maze was illegible.** With all 49 rooms walked, `_frontier_hops`
returns None everywhere, so every exit read `spent` — which also outranks
`proven` and `known` in precedence — plus `beats_since_new_ground: 26` on a
counter that can never reset. Forty-nine local "nothing new that way"s do not
sum, in a model's reading, to "there is nothing new ANYWHERE"; they sum to *I am
in the wrong part of the maze*. He invented an "unexplored eastern corridor" out
of a sightline that bends, and chased it. The payload was manufacturing the
phantom the character was blamed for. Same defect reaches any resident who has
walked their whole home — `tests/test_place_graph.py` had three fixtures
PINNING `spent` as the correct reading of an ordinary character's known world.

**Motivation needed a tier that outlives a task.** `ia4` ("walk the proved line
to the shrine") was marked *satisfied* by the character the beat after his first
arrival; Vesk's commission decayed dormant after 150 barren beats. Projects
(cap 2, weight 1.0, no dormancy, closed only by their own criterion or a stated
displacement) answered it, and the effect is the idle column: 18 → 5 between
runs 3 and 4.

#### The principle that produced every fix that worked

State the fact; leave the choice. `ground_fully_known`, `en_route`, `ends_in`,
`unentered`, `adrift` — not one removes an option. The evidence they work is a
sentence he wrote unprompted after `closer_than_last_room` went false:
**"Rejoin the proven route to the shrine."** The first self-correction in the
experiment, and nothing forced it. He kept his curiosity; it stopped being the
only thing that paid.

#### What the numbers cannot claim

- **Heavily intervened in.** Run 4 was restarted from beat 0 five times and run
  5 twice, each time to put a newly-built mechanism live. Runs are therefore not
  independent trials of one configuration.
- **Hand-written state.** Beliefs, an association, a goal, an intention and a
  project were written directly into `chat_chars.state` at various points, and
  six concerns, four beliefs and ten associations were surgically deleted once.
  All of it is recorded in the git log, none of it is a natural history.
- **`--max-steps` changed mid-arm**, 60 → 120 from run 3 onward, so beat counts
  are not comparable across the whole table.
- **A snapshot was taken wrong.** Copying only the `.db` file of a WAL-mode
  SQLite database silently lost 15 turns; a rollback intended for the run-2/3
  boundary landed mid-run-2. Use `VACUUM INTO`.
- **Two arrivals paid no contact reward at all** — `add_memory` takes `salience`
  positionally and the guard swallowed the TypeError into a log nobody read. The
  fix landed before run 5 and the run-4 reward was applied by hand afterwards.

None of that weakens what the arm actually established, which is the most it
has produced about how these minds work rather than how fast they walk. Every
defect above was found by watching a character behave sensibly and being forced
to ask what the world had told him: the theory-building came from set dressing
plus a drive to decode, the phantom frontier came from a payload that could say
"nothing that way" 49 times and never "nothing anywhere", the drift came from a
commitment nothing re-asserted, and the scenery won because the shrine had never
once been worth arriving at. Those are findings about psychology, and they
replicate as reasoning traces — quoted verbatim throughout — rather than as
summary statistics.

What the table specifically cannot support is a clean before/after performance
claim, because the configuration changed underneath it. Treat the rows as five
different experiments that happen to share a character, and the prose as the
result. A14 should run one configuration end to end without intervention, which
is the only thing missing.
