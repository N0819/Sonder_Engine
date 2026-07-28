# Spatial learning: can a character get better at a maze?

An experiment run against the live engine to answer a question raised by
observed NPC backtracking: **does a character accumulate usable spatial
knowledge across repeated attempts, or does it re-derive everything each time?**

Harness: [`tools/maze_experiment.py`](../tools/maze_experiment.py). Reproduce
with `--agent random` (free) or `--agent llm --preset fast --go` (spends
tokens).

---

## 1. Method

The pipeline is cut to the stages that bear on the question:

```
perception_act → character:<id> → mapping_quick → director_resolve
    → perception_outcome → commit
```

No player, no narrator, no loops. `director_interpret` is stubbed with an empty
sequence and the character listed in `flow.reactors`, so the beat is purely the
character's own. Everything that could carry knowledge between runs — memory,
mind models, `chat_chars.state` — is left exactly as the real engine writes it,
because that carry-over IS the thing under test.

**Maze.** 9×9 randomised-Kruskal, fixed seed: 81 rooms, 21 junctions, 25 dead
ends, 74% of rooms off-route, 16 false branches 3+ deep, optimal 20 moves. Every
room carries a distinct authored landmark ("walls furred with pale lichen"), so
recognition is possible before memory can be blamed.

**Models** (`--preset fast`): character on `x-ai/grok-4.20`; director,
perception, mapping and utility on `inception/mercury-2`; reasoning `low`
throughout. Character is the only role that *deliberates*; everything else
transforms. See §5.

**Metrics.** `moves` (position changes), `idle_beats` (beats without moving),
`backtracks` (re-entering a seen room), `reversals` (immediate `A→B→A`),
`unique` (coverage), `excess` (moves over optimal). Beats and moves are reported
separately — summing a beat spent deliberating with one spent walking made the
navigation score unreadable.

---

## 2. Results

All arms: same maze, same seed, same models. Each adds one capability.

| arm | run | moves | unique | backtracks | reversals | idle | reached |
|---|---|---|---|---|---|---|---|
| **random control** | 1–3 | 60 (cap) | 8–9 | ~52 | ~33 | 0 | **0/3** |
| **blind** | 1 | 56 | 29 | 32 | 22 | 4 | No |
| **+ frontier** | 1 | 51 | 25 | 36 | **11** | 9 | No |
| **+ sight** | 1 | 28 | 22 | 7 | 6 | 0 | **Yes** (excess 8) |
| | 2 | **20** | 21 | **0** | **0** | **0** | **Yes — exact optimal** |
| | 3 | 56 | 20 | 41 | 12 | 4 | No |
| | 4 | 52 | 35 | 26 | 2 | 8 | No |
| | 5 | 59 | 37 | 24 | 6 | 1 | No |

The memoryless control never reached the goal and saw 8–9 rooms: the maze is
genuinely hard, and any arm beating it is doing something.

Move-by-move traces of all five sight-arm runs, with the maze drawn and each
move annotated, are in [`docs/MAZE_RUNS.md`](MAZE_RUNS.md) — regenerate with
`python tools/render_maze_runs.py <runs.jsonl>`.

### 2.1 Retention is real

**Run 2 walked the exact optimal path** — byte-identical to the 20-move shortest
route through 81 rooms, zero backtracks, zero reversals. Context is wiped at the
run boundary, so this can only come from persisted state. He did not re-derive
the route; he executed it.

Corroborated by openings, which occur before any in-run exploration could help:

| | run 1 | run 2 | run 3 | run 5 |
|---|---|---|---|---|
| opening | `r0001 r0000 r0001 r0000 r0001 …` | 8 optimal moves | 7 optimal moves | 10 optimal moves |
| `r0403` dead end | entered once | never | never | never |

Run 1 spent six beats oscillating before committing. Every later run opened
clean. The dead end probed once in run 1 was never re-entered.

### 2.2 Preference does not exist

Runs 3–5 each **opened on the learned route and then abandoned it**, and never
arrived. Coverage over those runs: **20 → 35 → 37**. Run 4 had the widest
coverage of any run with only *2* reversals — systematic exploration, not
thrashing. He is not lost; he is choosing to look elsewhere.

Every affordance built during this experiment reports **where he has been** —
`been_there`, `times_entered`, `turned_back_here`, `no_route_onward`,
`no_new_ground_that_way`. **Nothing reports that a route worked.** So on the
correct path, the next optimal room is flagged `been_there: true`,
indistinguishable from a dead end already checked except that the dead end
carries extra warnings. A proven route accumulates no weight, and every run
re-opens the same question.

> **Finding.** The engine builds durable, precise spatial knowledge and cannot
> act on it preferentially. The first half is a real validation of pointing the
> belief machinery at places. The second half is unbuilt.

---

## 3. What had to be fixed before the question could be asked

Three defects each independently made the experiment unmeasurable. All were in
the engine or harness, not the model.

**The character was blind.** `character_step` reads its view from
`perception_act`, which was absent from the chain; and `perception_act` builds a
perceiver only for characters in `flow.reactors`, which the stub left empty. He
received `"You register nothing new this beat."` on **6 of 6** beats, navigating
purely from an exit list. Every measurement before this was of a blind agent.

**Spatial beliefs suppressed each other.** He filed all 81 rooms under one
umbrella entity (`"maze layout in this sector"`). Hypotheses group by
`(about_entity, kind)` and explain each other away within a group — right for a
mind, backwards for space. Learning one chamber actively suppressed another;
confidences sat at 0.68 and 0.28 for rooms with nothing to do with each other.
The map dismantled itself as fast as it was built.
Fixed by `theory_of_mind.rekey_place_claims`.

**The subject counted as evidence of sameness.** `claim_similarity` counted
shared subject tokens, so *"Chamber 0505 has a toppled bench"* and *"Chamber
0505 is empty and swept"* scored as one belief on `chamber` and `0505` alone —
the second silently overwriting the first. True of people too (`"Vorne is
afraid"` / `"Vorne wants to leave"`). Fixed by `claim_similarity(..., ignore=)`.

### 3.1 Experimental-design errors worth recording

- **The character sheet distorted the measurement twice.** Authored to survive
  repetition, he studied each room for 2–5 beats before moving one. Rewritten to
  reward arriving, he then rejected *"deliberate on paths"* as a norm violation
  (inhibition 0.8), optimising for stride rather than arrival. Settled on
  "decide as you walk".
- **A perfect maze cannot measure learning.** One path between any two cells
  means no better route to discover, and reversing out of a dead end is correct
  play indistinguishable from being lost. Randomised DFS also produces corridors
  with few branch points — the original 6×6 had **3 junctions**, and the model
  walked it optimally first try. Kruskal/Prim roughly triple junctions at the
  same size.
- **Silent instrument bugs.** `shortest_path` bound `START`/`GOAL` as *argument
  defaults*, evaluated at definition time, so every resized maze measured
  distance to the original 6×6 corner. `_rid` concatenated row and column
  without a separator, so at grid ≥ 10 `(1,11)` and `(11,1)` collided and rooms
  silently merged. Room features exhausted their combinations above 108, so
  large grids reused descriptions — destroying the one property the experiment
  depends on.
- **Coverage is not competence.** `unique` measures wandering. The blind arm
  covered *more* ground than the sighted one by drifting; the sighted arm
  committed, tested, and returned.

---

## 4. Schema robustness found along the way

Five instances of one failure: a field typed `str` receiving a structured
object, discarding the entire stage output and costing a whole beat. Each
surfaced only as a crash.

| field | what arrived |
|---|---|
| `observations_used` / `evidence` | bare strings |
| `association_updates[].cue` | missing |
| `initial_state.goals` | plain strings (silently produced **no** standing intentions) |
| `response_candidates[].response` | a sequence element |
| `changes_asserted[].change` | a structured object (**still open**) |

Coercing `response_candidates[].response` took a live model from **9 stalls in
22 beats (41%)** to **2 in 60 (3.3%)**, neither of which was a schema failure.

---

## 5. Model routing

Measured per-role, same beat structure:

| role | grok-4.20 | mercury-2 |
|---|---|---|
| character | 14–25s | 2.15s |
| director | 7.7–10.4s | 1.28s |
| perception | 7.8–12.1s | 1.29s |
| utility | 3.0–3.3s | 0.68s |

- **Mercury on every role:** 0/2 goals, 12–15 backtracks, 15–18 rooms —
  churning, not exploring. ~5s/beat.
- **Grok on every role:** exact optimal path on the 6×6. ~39s/beat.
- **Mercury + grok character:** optimal, **~13.4s/beat**.

**Character is the only role that deliberates**; the rest transform. After the
split, character is ~95% of remaining latency, so it is the only role worth
paying for. This also defuses the per-observer perception split, whose cost
scales with room occupancy: at 1.1s per observer a six-person room costs six
seconds, not sixty.

Two findings independent of the maze: `reasoning_effort` for perception was
`high`, set before perception became one call per observer — on Mercury that
cost 1997 response tokens against 229 at `minimal` for a view no better. And
`inception/mercury-2` reached 482 tok/s on OpenRouter against 7.4 tok/s on
nanogpt with the *same* ~5% prompt-cache rate, so the bottleneck was endpoint
throughput, not prompt reprocessing.

---

## 6. Improvements, in priority order

### 6.1 Outcome feedback — the one missing mechanism

Nothing anywhere records that a belief was **right**. Confidence tracks how
often a claim is restated and how recently, never whether acting on it worked.
A character who concludes "the steward is lying", acts, and is wrong will have
that belief decay from disuse exactly as fast as a correct one. It is revised
only by *another claim*, never by *reality*.

The maze makes this concrete because it has ground truth. Concretely:

- At commit, when a traversal reaches its goal, mark the rooms on the **actual
  path taken** — not the optimal one, which the character has no access to.
- Surface as `this way reached the goal` / `reached_goal_via: N` alongside
  `been_there`, so a proven route can outweigh novelty.
- Derived entirely from the character's own successful traversal. No oracle
  knowledge.

This is the counterweight the entire affordance set lacks, and it is the only
item that changes the *kind* of system this is rather than the amount of
information in it. **Predicted effect:** runs 3–5 stop drifting; arrivals go
from 2/5 toward 5/5.

Generalises past the maze: any goal the engine can check — a promise kept, an
intention discharged, an obligation met — is an outcome signal for the beliefs
that led to it.

### 6.2 Distant landmark → memory matching

He *sees* "the green-glazed chamber two rooms west" and separately *remembers*
Chamber 0202. Nothing joins them. `search_memories(here=)` cues on the room he
is standing in; the high-value moment is recognising a room he is **not** in
yet. Extending the cue to visible room names would let him rule out a direction
without walking it. Cheap: `location` is already on every memory row.

### 6.3 Explore/exploit as an authored trait

Runs 3–5 are not malfunction — exploring after mastering a route is reasonable,
and the sheet explicitly said *"beat your own best time"*. But the balance is
currently implicit and unauthored. A character's willingness to leave a known
route is a **personality** property (curious vs. methodical) and belongs on the
card next to the other psychology, where an author can set it.

### 6.4 Hierarchical spatial belief

He already reaches for region-level abstraction unprompted (`"maze layout in
this sector"`, `"shrine-maze layout"`). Per-room keying cleared space for both
levels to coexist. Region beliefs would compress 81 rooms into something
holdable — but sequence this **after** 6.1: hierarchy over unvalidated beliefs
amplifies error, producing confident wrong region-beliefs supported by five
children.

Prefer **structure-triggered** to time-triggered: "N inferences about different
subjects share a pattern" is detectable with `claim_similarity` and self-pacing,
where fixed turn windows are not — a character crossing eight rooms in five
turns and one pacing the same room eight times have learned very different
amounts.

### 6.5 Smaller items

- **Sight past a bend.** Sight currently stops dead at a turn. Realistically one
  still sees *that* the passage continues, distinguishing "bends and goes on"
  from "bends into who-knows-what".
- **Strict-field sweep.** Enumerate remaining `str`-typed fields that models
  populate structurally and coerce them as a set, rather than one crash at a
  time (§4).
- **Attribution debt.** The sight arm bundles `onward_exits`, corridor
  sightlines, and graded detail. One ablation would separate them.
- **Empty-`choices` retry.** Mercury returned a payload with no `choices` at a
  ~2.6% beat rate. Fine unattended, visible to a player as a dead turn; belongs
  in `providers.py`.

---

## 7. Conclusion

A character in this engine **can** build durable, precise spatial knowledge from
experience, and did: an exact optimal path through an 81-room maze, from wiped
context, after one prior traversal. That knowledge is built by the same
`mind_models` machinery that tracks what a character believes about a *person* —
kind-capped confidence, similarity-matched reinforcement, explaining-away,
decay — pointed at rooms. It is a real validation of the design.

What it cannot yet do is **prefer** what it knows. Remembering a route and
choosing it are separate mechanisms, and only the first exists. The engine
learns from **observation** but not from **consequence**: it records that a room
was there, never that a way through worked.

That is one signal, and it is the next thing to build.
