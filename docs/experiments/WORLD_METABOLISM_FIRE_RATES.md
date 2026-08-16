# The world metabolism has never fired

**Measured 2026-08-16** with `tools/fire_rates.py` against the live corpus
(2,451 pipeline turns, 2,383 stored `director_resolve` variants, 65 live
scenes). Everything below is a reading of that tool's output plus two
supporting measurements taken the same night; nothing here is inferred from
reading code.

This exists because a reader of the project said the characters felt far more
alive than the world, and asked whether that was a real asymmetry or an
impression. It is real, it is measurable, and the numbers are stark enough to
change what should be built next.

## The asymmetry

Minds:

| mechanism | fire rate | |
|---|---|---|
| `unbidden_probe` | **100.00%** | 852/852 |
| `present_evidence_used` | **100.00%** | 604/604 |
| `manifest` | 98.16% | 2029/2067 |
| `mind_model_updates` | 97.11% | 2354/2424 |
| `relationship_updates` | 90.30% | 2188/2423 |
| `memory_evidence_used` | 85.93% | 519/604 |
| `intent_ops` | 69.67% | 1440/2067 |

Off-screen life:

| mechanism | fire rate |
|---|---|
| seeded tick batch wrote events | **no chances** |
| full-agent candidate selected | **no chances** |
| reactive plan op accepted | **no chances** |
| reactive stage fired | **no chances** |
| reactive effect minted | **no chances** |
| a courier or caravan op was accepted | **no chances** |
| a caravan traded news at a stop | **no chances** |
| a crowd op was accepted | **no chances** |
| a crowd moved on the graph | **no chances** |
| a crowd took up public talk | **no chances** |
| character acquired carried report | **no chances** |
| a report was passed on | **no chances** |
| an artifact op was accepted | **no chances** |
| destination residue delivered | **no chances** |
| public event surface emitted | 0.00% (0/3) |
| profile candidate selected | 0.00% (0/37) |
| profile job scheduled | 0.00% (0/37) |
| world epoch opportunity | 10.82% (37/342) |

The mind layer runs at 90–100%. The world layer has not run.

## The finding: not thin, inert

The natural reading of a sparse world is that the substrate is deliberately
thin — that lazy minting keeps bookkeeping cheap and there is simply not much
there to act. That reading is wrong here, and the distinction matters because
it points at a different fix.

`offscreen.py` is 2,158 lines. `affect.py` 2,148. `couriers.py` 1,090.
`weather.py` 808. `crowds.py` 608. `living_world.py` 608. `gaps.py` 550.
`paradox.py` 489. `pipeline_trace.py` 413. `canon_provenance.py` 360.
`routines.py` 200. `degradation.py` 171. Roughly five thousand lines of world
metabolism, built, documented, tested, and at zero.

The substrate is not thin. It is INERT, and inert is a different problem.

## Where the bottleneck is: the mint, not the machinery

The gate descriptions name their own precondition, and read together they say
the same thing. *"a crowd op was accepted — a populous place declared as one
object rather than as extras."* **No chances** means the precondition never
arose: the Director never declares a crowd. The same holds for couriers,
caravans, artifacts and carried reports. The machinery is not failing. It is
never handed anything to run on.

Two supporting measurements from the same night agree:

**Minting.** Across 2,383 stored `director_resolve` variants —
`contact_ops` on 15.4% of monolith-era resolves and 19.2% under orchestration;
`substance_ops` on 0.05% and 2.4% (a ~50x improvement, from almost nothing to
very little); `scales` 25 then 0; weather declared 3 times in the entire
corpus. Of 65 live scenes, contacts stand in 10, weather in 7, substances in 1.

**Delivery.** Where the substrate IS minted it was frequently not delivered.
`spatial.substances_for` — the standing-substance reader — had zero production
callers. `spatial.scent_level` computes graded scent propagation that gates no
percept. `weather.py` computes per room AND per channel, with sight words and
sound words separated by construction so a cellar can hear rain it cannot see,
and reached only `backdrops.py` and `ambience.py`; every reference under
`agents/` was a comment until the `sensory_channels` manifest landed on
2026-08-16. Standing contact sensations are rebuilt every beat and suppressed
after first render by the composer's delta dedupe.

So the world layer is starved at both ends: rarely minted, and when minted,
often not delivered to anyone who could act on it.

## The capacity finding

From the same run:

| | |
|---|---|
| has ever held a project | **9.68%** (3/31) |
| projects at cap (2) | 0.00%, mean 0.03 |
| wants at cap (3) | 72.86%, mean 2.59 |
| intentions at cap (4) | 27.14%, mean 2.40 |

The row's own note reads *"the tier is unreachable if this is zero."* Three
characters in the corpus have ever formed a project.

`CLAUDE.md` records that projects are the tier between eternal drives and
completable intentions — durable, able to name a place, immune to the three
ways the courier's aims died — and that they are **what made NPCs pass the maze
without any alteration to their drives**. They carry the ordinary long
intentions a life has: take the injured one to a doctor, go home, go to the bar.

An NPC with a project walks somewhere for a reason. That is the oldest
spontaneous-event engine in fiction, it reuses the layer that already works,
and it is currently reachable by under a tenth of the cast.

## What this implies for a story-driver sidecar

A design under discussion adds a powerful sidecar that pre-plans low-resolution
world layout beyond the declared horizon and plants material for drama
according to genre. The split proposed is a genre-aware "Dramaturge" that only
emits pressure, and a "Geographer" that only does physical planning — genre
biases, physics decides.

These numbers do not argue against it. They argue about **sequencing**, and
the tool that produced them states the rule in its own docstring:

> **no mechanism should be enriched before its fire rate is known.** Enriching
> something that never runs is how a system grows machinery nobody can observe.

Read against the table, the two halves of the proposal have very different
standing:

- The **Geographer** looks better justified than the drama argument makes it,
  and for a different reason. Its value is not excitement. It would be the
  thing that finally DECLARES the substrate — crowds, routes, standing
  conditions, populated places — so that five thousand lines of existing
  metabolism have something to metabolise. It addresses the measured
  bottleneck directly.
- The **Dramaturge** is the speculative half. Tilting weather toward dread
  tilts a system that reached no character's senses until this week. It should
  follow evidence that the tilt can be felt.

**The acceptance test is already written.** The sidecar works when the rows
above stop reading `no chances`. If a Geographer ships and `a crowd op was
accepted` is still `no chances`, it has built a second inert layer on top of
the first.

## Cheaper things to try first

Ranked by measured evidence rather than by appeal:

1. **Raise the project rate.** 3 of 31 is the smallest number here with the
   largest documented effect, and projects are the only tier that makes an NPC
   walk somewhere for a durable reason. Whether the gap is adoption
   deliberation, probation lapse, or prompt reach is unmeasured and should be
   the next measurement.
2. **Find out why the Director never declares a crowd or a courier.** The ops
   exist and are contracted. Nothing in this measurement says whether the
   contracts are unreachable, unread, or simply never applicable to the stories
   played so far — and those have very different fixes.
3. **Keep closing the delivery gaps**, which are cheap and already yielding:
   `substances_for` has a consumer now, weather has an agent-side path, and
   scent remains computed and undelivered.

## Provenance

Fire rates: `tools/fire_rates.py`, unmodified, default corpus scope. Minting
and delivery figures: read-only queries over `engine.db` the same night, and
the code audit recorded in `docs/UNBUILT.md` §1.45. The Dramaturge/Geographer
framing comes from a design conversation the owner had with another model; it
is summarised here only as the proposal these numbers bear on.
