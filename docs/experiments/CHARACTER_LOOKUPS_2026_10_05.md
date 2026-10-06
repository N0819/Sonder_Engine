# A mind looks back while it decides: the first replays

Status: EVIDENCE, 2026-10-05. Step 1 of the agentic characters the owner asked
for that day ("making ponder and notebook reading a tool call that retrieves
immediate results with a budget, writing being part of the output"; "I want
the characters to be more capable as agents"), measured before anyone plays on
it. Built in `agents/character_tools.py`; what it is and what it is not yet is
in `docs/UNBUILT_CHARACTERS.md` §2.26 and `Design.md`'s row "A mind can look
back while it decides".

Instruments were scratch scripts, not kept: one copy of `engine.db` per arm
(`sqlite3` backup), migrated to the branch's schema, with the replica hint
allowed for NanoGPT in BOTH copies (`cache_affinity_allow`) and debug capture
on; the arms ran concurrently, identical but for `character_tools`
(`character_major` in one, unset in the other). Character model: the owner's
`character_major` route, NanoGPT `z-ai/glm-5.3:thinking`; decision model
`typesafe/jev-1.13` (OpenRouter); embeddings `pplx-embed-v1-4b` on the owner's
own server.

The code moved between runs, and each section says what it ran on: §2 on the
first build; §3 on it plus four fixes from my own reading (a cut row counted
as delivered, a repeated row returned in full, `continue` reading back over a
span, a lookup count written into the card); §4 on the build after the
adversarial review (four lenses, eight agents; ten defects confirmed and
fixed -- among them the notebook lookup reading concerns from a payload that
no longer held them, engine numbers in what came back, and any 400 switching
the lookups off for the process).

## 1. Probe: does the route do it at all

Before any engine code, a raw probe on the owner's route (scripts in the job
scratch directory):

- **Native tool calls work from inside the thinking.** The model reasons,
  stops with `finish_reason: tool_calls`, and given the result carries the
  line of thought on -- two chained lookups (the key is "in the box I gave
  Oren", then where Oren put the box) and an answer combining both.
- **A grammar beside the tools silences them.** With `response_format:
  json_schema` in the same request no tool is ever called; the model
  performed the lookup in the fiction instead (`"let me think back before I
  answer that"`). Hence the shape the engine uses: rounds with no grammar,
  and, once the model stops calling, a closing round on the grammar with
  `tool_choice: "none"` (schema-valid, 4.6 s).
- **The rounds cache only with the replica hint.** On a real stored character
  call the closing round read 10 of 5,591 prompt tokens from cache with no
  hint and 5,515 of 5,870 with `user: "sonder:character_major"` (8.1 s against
  33 s). The hint is the engine's own `providers._apply_cache_affinity`,
  opt-in through `cache_affinity_allow`, which is unset on the owner's
  install.

## 2. Replay: three stored beats, lookups off and on

`run_pipeline(only_key="interaction_loop")` from each beat's pre-turn
checkpoint, the restored rows re-embedded before the step (a restore puts the
pre-switch embedding key back). Beats: chat 27 turn 89 (Dr. Moon walking an
exhausted Hinami through the dark, 298 memories), chat 64 turns 160 and 163
(Tamamo and the Doctor at the shrine's evening meal, 135 and 657 memories).

| | lookups off | lookups on |
|---|---|---|
| character calls | 9 | 7 |
| lookups made | -- | **0 of 7 calls** |
| mean seconds per call | 27.0 | 23.2 |
| mean output tokens per call | 1,378 | 969 |
| answers that needed a repair | 0 | 0 |

- **No mind looked anything up.** Every call with lookups on answered in its
  first round, and that answer -- written with no grammar on the wire --
  validated as the first attempt, so no call was paid for twice. These are
  beats about the present (a meal, a walk in the dark): nothing in them asked
  the past for anything, and declining a tool there is the right behaviour,
  not a failure of it.
- **Offering the lookups costs nothing when they go unused.** 23.2 s a call
  against 27.0 s under the grammar; the difference is inside one beat's noise
  (19-39 s either arm) and is not claimed as a saving.
- **The packet is ~20,000 prompt tokens, not the probe's ~5,800.** A real
  character call carries 19-23k tokens of payload (30 recalled memories, eight
  whole recent turns, the notebook, perception). Every round after the first
  resends all of it, so the replica hint is worth four times what the probe
  said once a mind looks something up -- and nothing in these beats did, so
  the replay measured no round after a first one.
- The lines in both arms are in character and answer the moment; neither arm
  wrote a line the other could not have.

## 3. New turns: a question about the distant past, recall intact

Chat 74 (the Doctor and Hinami, 186 memories), two new turns submitted through
`web.app.turn_new` on each arm's copy, every stage run as in play: Hinami asks
what her very first words to him were, the night they met sixty turns ago, and
then how old she told him she was on that beach.

Both arms answered both questions right and near word for word -- "Hick!"
and then "W-who are you?"; "198 ... Normally I just say I'm 20" -- and
neither arm's Doctor looked anything up: recall had put the meeting in the
packet already (35 and 11 recalled rows; the heard-question recall did its
job). Two calls with lookups on, 0 lookups, 24 s and 31 s, against 38 s and
31 s under the grammar.

So across the nine real calls of §2 and §3 the model used the lookups exactly
when it needed them -- which was never.

## 4. New turns: the same questions to a mind whose recall missed

Recall does miss in play. Here it was made to: the probe wrapped
`build_character_memory_context` for the probe turn so every memory lane but
the eight recent turns came back empty -- the meeting was not in the packet --
while the bank the lookups read was untouched. Same two arms, fresh copies.
The second question changed to what she told him about Kaa Sama that night.

**Lookups off, the Doctor confabulates, fluently.** Her first words become "an
accusation. Delivered at volume", after a TARDIS landing the story never had
(he fell out of the dark onto her). Kaa Sama becomes "the smartest person you
know", who lives "up a mountain that doesn't want visitors" and "guards
something up there".

**Lookups on:**

- *First question: no lookup -- the search performed in the fiction instead.*
  "The night we met. Hold on -- hold on, it's here. It's just... filed
  somewhere behind the fall of the Byzantine Empire... Give me a second, I'm
  not losing this one." No call, so nothing found -- but nothing invented
  either. The same move the probe of §1 saw when a grammar made calling
  impossible; here calling was possible and the model did not.
- *Second question: two `ponder` calls in one round, queries in its own
  words* ("The night I first met Hinami -- her very first words to me, the
  scene, where we were, what happened"; "What Hinami told me about Kaa Sama the
  first night we met"), 0.4 s each, then the answer in a second round.
  - **Kaa Sama, right.** The ponder brought exactly the rows: turn 6 ("Kaa
    Sama has nine tails"), turn 11 ("Okaa Sama lives in a mountain shrine"),
    16 and 41. He said nine tails -- "three more than you" -- and a mountain
    shrine.
  - **The scene, right; the first words, wrong.** "Moonlit shoreline. Sand.
    ... six tails going like festival lanterns" is the meeting. But "Your
    first words to me: 'You've been to the stars! C-Can I come mister!?'" is
    Hinami at turn 15. The ponder returned turns 15, 22, 56, 57 and 63 and
    never turn 1, and the model took the earliest line it was given for the
    first one. Turn 1 calls her "the young woman": it was written before he
    knew her name, and 186 of the bank's 190 rows carry no `memories.about`
    tag (minted before v43, never backfilled -- `UNBUILT_CHARACTERS.md`
    §6.17), so the ponder's ABOUT lane, built for exactly this row, could not
    reach it. Ordinary recall did, in §3. He also filed a re-reading on the
    turn-15 row on the strength of the mistake.
  - **The packet stayed in the cache.** The answering round read 13,187 of
    its 14,618 prompt tokens from cache (90%; the first round 3,096 of
    13,188) -- the whole packet, in the engine's own path, with the replica
    hint allowed.

| | lookups off | lookups on |
|---|---|---|
| first words (turn 1: "Hick!", "W-who are you?") | invented: an accusation | none given -- "give me a second" |
| Kaa Sama (turn 6: nine tails; turn 11: a mountain shrine) | invented: the smartest person, guards something | **right** |
| scene of the meeting | invented: a TARDIS landing | **right** |
| lookups | -- | 0, then 2 |
| seconds in the character calls | 51, 34 | 21, 6 + 43 |

## 5. What this says, and what it does not

- The mechanism works end to end on the owner's route: streamed calls, results
  handed back with the reasoning, the answering round validated without a
  second call, the closing ladder unused, the packet cached across rounds.
- Offered and not needed, it costs nothing measurable (§2, §3).
- Where recall missed, it turned two confabulations into one right answer and
  one honest stall, and its one wrong claim was a retrieval miss the engine
  already registers (§6.17's untagged rows), taken on trust.
- Two behaviours to watch, both the model's choice and neither a defect:
  it may act out searching instead of calling `ponder` (1 of 2 beats here),
  and it reads the earliest memory a ponder returns as the earliest there is,
  without the `continue` that would check.
- Sample sizes are one story's two beats for §4; nothing here is a rate.
