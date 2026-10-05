# The memory window on real cards: a replay

Status: EVIDENCE, 2026-09-28. Twelve real beats from four long chats; the
character step alone rerun from each beat's pre-turn checkpoint under the code
before the day's memory changes (087d3057, "old") and after them (40519499,
"new"), each arm from its own code snapshot against its own copy of
`engine.db`, the two arms concurrently. Character model GLM 5.2 (OpenRouter,
reasoning `medium`, `json_schema`), decision model `typesafe/jev-1.13`,
embeddings `pplx-embed-v1-4b`. Instruments were scratch scripts, not kept: a
driver that branches the chat at the beat (`web.app.turn_branch`) and reruns
`run_pipeline(only_key="interaction_loop")`, reading every character call back
from `llm_capture`; a comparer that maps each delivered memory to the turn that
formed it by its exact text; and, for time, a rerun with wall timers on the
named phases plus a stack sampler over every thread. The rulings measured are
the owner's of 2026-09-28 (`docs/guides/MEMORY.md`,
`UNBUILT_CHARACTERS.md` §6.17 "The layout").

## What differs between the arms

| | old | new |
|---|---|---|
| recent lane (calm) | newest 12 rows of the last 4 turns | every row of the last 8 turns (`RECENT_TURNS`) |
| recent lane (absorbed) | newest 8 rows (absorption >= 0.35) or 4 (>= 0.7) | the same caps, now cut from the 8-turn window |
| recall | Jev's best 24 from the net of 100; excludes the delivered recent rows | best 30; excludes the WHOLE 8-turn window |
| emotional pass reads | the best 8 recalled rows, never a recent one | every delivered row, recalled and recent |
| memory's pull on mood | as strong as its appraisal | cubic in strength, never above the present moment's pull |
| payload order | memory by type | recalled, then recent as one chronological stream with kinds, then perception |

## The beats

| chat | who | the story | beats | memory tier in both arms |
|---|---|---|---|---|
| 27 | Dr. Moon (and the Doctor, a late arrival, at 92) | an SCP-style descent | 86, 89, 92 | calm |
| 64 | Tamamo and the Doctor | an evening meal at a mountain shrine | 160, 163, 166 | absorbed >= 0.35 |
| 111 | Vexara | an adult scene | 113, 116, 119 | absorbed >= 0.7 |
| 113 | Mirelle | an adult scene | 101, 104, 107 | absorbed, both tiers |

Sixteen character calls per arm (the first call of each character per beat).
One call per arm failed outright and was rerun (see § 5).

## 1. A calm mind gets the whole window, and it shows

Dr. Moon, the only calm mind here, received every memory row formed in the last
8 turns at all three beats: 21 of 21, 25 of 25 and 22 of 22, where the old code
delivered 18, 17 and 10 of the same rows. She also had 29-30 recalled older
memories against 23-24.

Her conduct moved on two beats of three, both toward continuity:

- **86, better.** She reads the arc of the last eight turns: the Doctor's
  repeated "something is close", never made good, and Hinami's
  self-deprecation. The old arm answered the moment alone.
- **92, better.** She takes up the Doctor's just-spoken "temporal
  displacement" directly, in a short note; the old arm's note ran to 6,912
  characters.
- **89, worse.** The old arm probes Hinami's silence. The new one repeats
  "close to something", the phrase already standing in its window. A longer
  window gives a refrain more copies of itself to lean on. One beat; worth
  watching.

## 2. An absorbed mind loses the middle of its window, and that is new

Twelve of the sixteen calls ran at an absorption tier (every call in chats 64,
111 and 113). Absorption cuts the recent lane to its newest 8 or 4 rows. The new
code then keeps the WHOLE 8-turn window out of recall, so the rows between the
cut and the start of the window can reach the mind by no lane at all. The old
code kept out only the rows it had delivered.

Rows formed in the last 8 turns that reached the mind in any lane (recent,
recalled or resurfaced), both arms counted over the same span:

| beat | who | rows in the span | old reached (rows / turns) | new reached | turns the new code cannot reach |
|---|---|---|---|---|---|
| 27:86 | Dr. Moon | 21 / 8 turns | 18 / 8 | 21 / 8 | none |
| 27:89 | Dr. Moon | 25 / 8 | 17 / 7 | 25 / 8 | none |
| 27:92 | Dr. Moon | 22 / 8 | 10 / 5 | 22 / 8 | none |
| 64:160 | Tamamo | 33 / 8 | 10 / 4 | 8 / 3 | 152-156 |
| 64:160 | the Doctor | 29 / 8 | 11 / 7 | 8 / 4 | 152-155 |
| 64:163 | Tamamo | 27 / 8 | 10 / 5 | 8 / 3 | 155-159 |
| 64:163 | the Doctor | 30 / 8 | 12 / 5 | 8 / 2 | 155-160 |
| 64:166 | Tamamo | 33 / 8 | 12 / 3 | 8 / 2 | 158-163 |
| 64:166 | the Doctor | 28 / 8 | 12 / 5 | 8 / 2 | 158-163 |
| 111:113 | Vexara | 38 / 8 | 7 / 2 | 5 / 2 | 105, 107-111 |
| 111:116 | Vexara | 33 / 8 | 7 / 3 | 4 / 1 | 108-114 |
| 111:119 | Vexara | 30 / 8 | 5 / 2 | 4 / 1 | 111-117 |
| 113:101 | Mirelle | 25 / 8 | 11 / 5 | 8 / 5 | 94, 95, 98 |
| 113:104 | Mirelle | 24 / 8 | 12 / 5 | 11 / 5 | 98-100 |
| 113:107 | Mirelle | 29 / 8 | 7 / 4 | 4 / 2 | 99-104 |

In every absorbed call the new code reached fewer of those rows than the old,
and at worst seven of eight turns were unreachable (Vexara at 119).

**No fiction failure in these twelve beats can be laid at its door.** An
earlier reading blamed it for Tamamo gathering the dinner bowls at 166 "a
second time"; the committed narration says otherwise (at 164 the Doctor's
fingers still rest on his empty bowl, and nothing clears the table before 166),
so that claim is withdrawn. Absorbed scenes are carried by the present (an act
in progress, a meal in progress), and a thread can cross the gap by channels
other than memory: Vexara's "dinner would have worked", formed at 109 and
unreachable as a memory at 113, reached her in both arms as a held belief
(`self.learned_beliefs`) and in her record of her own recent lines
(`self.recent_self_lines`). Conduct barely moved: Mirelle's first line at 104
is all but identical in both arms. The loss is of access, measured above. It
will cost fiction the first time an absorbed mind needs something from two to
seven turns back that no belief, note or line of its own carries.

## 3. The emotional pass

- **It reads twice as much.** Memories it kept a habit for: median 8 to 16 per
  call, and up to 54 for the calm mind.
- **The present held.** In all sixteen calls, in both arms, the feeling handed
  to the mind as "now" came from a perceived event or its own act, never from a
  memory. The one exception is 113:107, in both arms, which had no new event.
- **Memory rides underneath, and in character.** The new arm's undercurrents
  come from memories: protectiveness toward Hinami (Dr. Moon; Mirelle, from her
  conclusion that Hinami is still recovering), tenderness (Tamamo, from her
  reading of Hinami's open affection), mastery (Vexara, from her conclusion
  about Hinami's composure). That is the "subtler but noticeable" the ruling
  asked for.
- **Surface mood barely moved.** New minus old, surface valence median +0.005
  (range -0.19 to +0.12), arousal median -0.003 (range -0.09 to +0.07). The
  widest swings are Dr. Moon's (valence -0.17 at 86 and -0.15 at 89), the calls
  that read 51 to 54 memories (0 to 8 in the old arm).
- **A standing sensation is never "now"** (pre-existing; one beat).
  `affect_pass.events_from` skips standing observations, so a beat inside a
  continuing act with no new event gives the present slot to a memory, and
  under the new rule it counts as a quiet present. At 113:107 (a sustained
  touch at intensity 0.53, no new event) the new arm's mood read less aroused
  (0.38 against 0.43; "calm" and "drained" among its words) while her conduct
  stayed exactly as aroused as the old arm's. Flagged, not concluded.

## 4. Cost and time

- **Decision model input per character call:** median x1.10, but x2.5 for the
  calm mind (91k to 232k and 94k to 237k tokens at 27:86 and 27:89). Its calls
  are 0.2-0.5 s each; summed per beat, median 3.0 s to 4.1 s.
- **Local cost, timed on 27:89 with the bank healed (below), one arm after the
  other:** building the memory context 0.69 s old, 0.72 s new; the emotional
  pass 0.63 s against 0.62 s; decision calls 10 (3.0 s) against 15 (4.8 s). The
  change costs about two seconds of decision time on a calm mind and nothing
  measurable otherwise.
- **The character's own call is unchanged** (median 15 s old, 12 s new), set by
  output length and by the retries in § 5.

The comparison runs' step times (50-330 s) are NOT a measure of the change.
They are dominated by three things that are the same in both arms: the
checkpoint restore (23 s for a 292-row bank, § 5), an embedding rebuild running
in the background (§ 6), and character-call retries the ledger does not see
(§ 5).

## 5. Found along the way (both arms; not caused by the change)

- **A failed attempt leaves no trace in the ledger or the log.** `chat_complete`
  retries a failed attempt (`llm/providers.py:3355`), but only the successful
  attempt reaches `record_llm_call` and the `llm_call` log line; a failure emits
  a UI `generation_reset` notice and nothing else. Only `llm_capture.duration`
  times the whole call. In 10 of the 24 reruns the two disagree: **388 s of
  827 s of character-call time (47%) went to attempts no ledger recorded**
  (worst: old 113:107, 95 s whole against 24 s recorded; new 64:160, 67 s
  against 12 s). The two calls that exhausted every attempt both died on the
  degenerate-repetition guard ("repeating output fragment", "repeating
  138-character phrase"), so it is the likeliest cause of the rest, but no
  record of an intermediate failure's reason exists to confirm it. Anyone timing
  turns from the ledger or the log is reading the successful attempt alone.
  `UNBUILT_PLATFORM.md` §1.171.
- **Every memory write scans the whole retrieval index.**
  `_replace_memory_fts` and `_delete_memory_fts` find a memory's row in
  `memory_retrieval_fts` by `memory_id`, an UNINDEXED FTS5 column, so each
  lookup is a full scan of the index for every chat: 40.3 ms per lookup at
  25,384 rows, against 0.021 ms by rowid. Every new memory at commit pays one
  scan; a checkpoint restore (every reroll and every rerun from a stage) pays
  two per row of the chat's bank: 23 s for chat 27's 292 rows here, measured,
  and by extrapolation about 80 s for chat 64's 1,009. It grows with the whole
  database, not the chat. `UNBUILT_PLATFORM.md` §1.172.
- **Runaway notes.** Seven notes over 1,500 characters in the old arm, five in
  the new; the longest (16,206) is the model's own deliberation written into
  the field, and one (113:101 new) ends in a repeated mantra. Stored notes are
  cut to 300 characters (`character_jev.NOTE_CHARS`), so nothing carries
  forward; the cost is the call's own time.
- **No fallback for the character role.** Two calls (old 27:89, new 113:101)
  failed outright on the repetition guard and killed the step; both succeeded
  when rerun.

## 6. What this measurement cannot say

**Recall quality between the arms is not comparable here.** A rerun restores
the beat's pre-turn checkpoint, and the restore puts back each memory row's
vector with the key it had when the checkpoint was taken. These turns were
played before the embedding provider moved from `openrouter:3` to `generic:7`
(the same model), so the restored rows carried the old key, and
`search_memories` scores a key-mismatched row 0.0 on both vector lanes. The
reconciler re-embedded them in the background while the steps ran. Still
stranded after the runs, so certainly stranded during them: in the old arm, Dr.
Moon's whole bank at 27:86 and 27:92, and Tamamo's and the Doctor's at 64:160
and 64:163 (99 to 635 rows each); in the new arm, Dr. Moon's at 27:86 and part of
it at 27:89. The window findings (§ 1, § 2) are set by code, not retrieval, and
stand; which older memories each arm recalled does not. A replay that must
compare recall has to heal the branch after the restore and before the step, as
the timed runs in § 4 did (292 rows, 17-28 s).

Also: one rerun per beat per arm, so a single beat's difference is within model
variance; the reading of conduct is one reader's, not blind.

## Recommendations

1. **Keep out of recall only the recent rows actually delivered**, not the
   whole window (`mind/memory_context.py`: `recent_ids` from `recent`, not
   `window`). It restores what the old code did for the undelivered rows, and it
   is right whichever way (2) goes: when the whole window is delivered, the two
   sets are the same. `UNBUILT_CHARACTERS.md` §1.170.
   (Landed 2026-10-05 by way of (2): the whole window is now always
   delivered, so the two sets are one.)
2. **The owner's call: should absorption still cut the recent lane?**
   Decided 2026-10-05: no -- "absorption should be adjusted to apply to
   recall only". In these
   chats it did so on 12 of 16 calls, so "8 turns of recent memory" holds in
   practice for calm minds only.
3. Watch refrains under the full window (27:89).
4. Record failed attempts in the per-call ledger, with their reason (§ 5).
5. Key `memory_retrieval_fts` rows by rowid. It needs a migration, so it waits
   for owner policy 4 (`UNBUILT_PLATFORM.md` §1.58).
