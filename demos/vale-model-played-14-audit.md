# vale-model-played-14: what a real model actually declares

14 turns · persona **Corin** · cast **Sera, Bryn, Maelor, Wren** · 2026-08-10

The first playthrough of this engine in which **the model side is not
authored**. Only the opening scene is scripted — establishing a world is what
a user does before play starts. From beat one on, every stage is a real
provider call: interpret, resolve, perception per perceiver, each character,
narrator, mapping, and the off-screen rungs. `llm_quality` parsed, validated,
repaired and fell back exactly as it does for a paying user, so every
rejection below is a real rejection.

    director / character / narrator / mapping / utility   minimax/minimax-m3
    perception (beats 1-5)                                inclusionai/ling-3.0-flash
    perception (beats 6-14)                               mistral-code-agent-latest
    embeddings                                            perplexity/pplx-embed-v1-4b

Reproduce with `tools/model_playthrough.py`. Player inputs are written to be
**occasions**, never instructions: "I pay him two coins to carry word to Siege
Town" is a thing a player types. Whether that becomes a `courier_ops` entry is
the measurement.

## The headline: the player is not in the information-carrier network

Eleven Director resolves, each given an explicit occasion. What the model
wrote into `state_diff`:

| op | occasions given | declared | accepted |
|---|---|---|---|
| `courier_ops` | 1 (pay a rider to carry word east) | **1** | **0** |
| `crowd_ops` | 2 (a packed market; listening to it) | 0 | — |
| `artifact_ops` | 2 (nail a notice up; watch it be read) | 0 | — |
| `tell_ops` | 2 (tell Sera; ask for news) | 0 | — |
| `project_ops` | 1 (reach the Keep before the week is out) | 0 | — |

The one op the model did write was well-formed and **correct**:

```json
{"op": "send", "sender": "Corin", "to_room": "siege_town",
 "claim": "the wells of the Vale market are sealed",
 "method": "word", "pace": "riding",
 "description": "a lean man on a short-coupled bay pony with a leather satchel"}
```

It was refused, and the reason is structural rather than a bad encoding.
`couriers.run_couriers` resolves the sender through `carriers._cast_index`
(`carriers.py:311`), which iterates `extant_cast` — **cast rows only**. Corin
is a persona; the cast is Sera, Bryn, Maelor and Wren. So the sender check at
`couriers.py:851` refuses with *"courier sender 'Corin' is not a registered
character; a message starts in somebody's hands"*.

This is not a one-line fix, and that is the important part. Carried reports
are persisted per cast row — `state[STATE_KEY] = reports[-REPORT_CAP:]` then
`set_char_state(cid, cast_row["id"], …)` (`carriers.py:236-239`). **The player
has no `chat_chars` row, so there is nowhere to store a report the player
holds.** The same `_cast_index` gates `apply_tellings` and the artifact
poster, which is why tellings and bills also never registered.

The consequence: **from the player's seat the entire information-carrier
network is unreachable.** The player cannot hold a report, tell anyone
anything through the ledger, send a rider, or nail up a bill. Every mechanism
in that layer is reachable only NPC-to-NPC. In a single-player engine, the
most likely sender of news is the one participant structurally excluded from
sending it.

That is a design item, not a bug to patch quietly: it needs a decision about
where a persona's held information lives.

## Fire rates

    world epoch opportunity              8.33%   1/12
    seeded tick batch wrote events     100.00%    1/1
    public event surface emitted       100.00%    1/1
    a courier or caravan op accepted     0.00%    0/1     <- refused, see above
    destination residue delivered        0.00%    0/1
    profile / full-agent candidate       0.00%    0/1
    crowds, tellings, artifacts, caravans        no chances
    has ever held a project              0.00%    0/3

Read the `no chances` rows precisely: they mean the model never offered one,
so the engine was never asked. That is a statement about the **prompts**, not
about the commit path — the hand-authored `ashen-quest-51` run drove all of
these mechanisms to 100% acceptance on the same code.

## Two hard failures, both the same shape

Two of fourteen beats died, and neither is a schema-design problem:

- **beat 10** `mapping_stage failed JSON validation: Expecting ',' delimiter
  at position 5042` — the model wrote a long `why_relevant` prose field per
  lore entry and the object was cut off mid-string.
- **beat 14** `character failed JSON validation: Expecting ',' delimiter at
  position 10054` — same truncation, further in.

Both are output-ceiling truncation. This is the failure mode
`llm_quality.complete_validated_json` already carries a comment about, from
the maze benchmarks: a model that spends its output budget before closing the
JSON kills the beat. A 14% hard-failure rate on a fresh model is worth a
guard that the repair pass can act on.

## Latency, measured

Wall-clock per beat, whole turn, real providers:

    beats 1-5   (perception: ling-3.0-flash)         118 / 133 / 231 / 354 / 249 s
    beats 6-14  (perception: mistral-code-agent)     122 / 80 / 134 / 203 / 29 / 157 / 62 / 235 / 53 s

Two findings, both independently confirmed against a separate 751-call
telemetry regression:

1. **Latency is generation-bound, not prefill-bound.** Input tokens cost
   essentially nothing in wall-clock; duration tracks output tokens almost
   linearly. Prompt-prefix caching is a **cost** lever, not a latency lever.
2. **Perception is the right place to spend a fast model.** It is 46% of all
   stage calls (234 of 505 in a captured 51-beat story) because it runs once
   per perceiver. Swapping only that role visibly moved whole-turn times.

Both `:thinking` variants were deliberately avoided — reasoning is billed as
output, and output is what wall-clock is made of.

## What this does not say

This is one model family, one story, fourteen beats. It does not show that
another model would do the same, and it does not show the prompts are
unfixable — five of the six mechanisms have never had a prompt-efficacy
measurement at all, and now they have one to improve against.
