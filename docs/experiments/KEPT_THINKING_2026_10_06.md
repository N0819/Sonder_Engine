# A mind keeps its thinking for a few turns: why in the packet, and what it does

Status: EVIDENCE, 2026-10-06. The owner, 2026-10-05: "maybe preserving the
reasoning block in context for about 5 turns, but it should be
chronologically ordered with recent episodes"; and of the mind itself, "be up
front that ... only five turns of reasoning are preserved". Built in
`mind/thoughts.py`, off unless the `character_thoughts_kept` setting names a
number of turns; what it is and is not yet is in
`docs/UNBUILT_CHARACTERS.md` §2.26.

## 1. Why the thinking is in the packet and not a multi-turn history

The shape first proposed was a multi-turn conversation -- each kept turn a
user/assistant pair, oldest first, evicted in chunks -- because it is the one
shape in which one beat's request could reuse the previous beat's cached
prefix. Two measurements took that reason away:

- **The card is not the same from beat to beat.** A prefix cache holds up to
  the first byte that differs, and the bare card's gated sections (an answer
  owed, the speech budget, finding the way, a dispute, the lookups count...)
  come and go with the moment, near the card's end. A history placed after a
  card that changed is never read from cache.
- **NanoGPT's cache does not survive the gap between beats reliably.** One
  ~12,100-token request with the replica hint, repeated unchanged:

  | gap | prompt tokens | read from cache |
  |---|---|---|
  | first | 12,137 | 0 |
  | 30 s | 12,109 | 0 |
  | 90 s | 12,109 | **12,096** |
  | 3 min | 12,109 | 0 |
  | 5 min | 12,109 | 0 |
  | 8 min | 12,109 | 0 |

  One hit in five, at 90 s; the same text counted 12,137 tokens once and
  12,109 after, which reads as requests landing on different replicas with
  their own caches. Tool rounds seconds apart, inside one call, did read the
  packet from cache (`CHARACTER_LOOKUPS_2026_10_05.md` §4: 13,187 of
  14,618); a beat a few minutes later cannot count on it.

So the thinking goes where the owner asked for it and nothing more: on the
recent past in the packet, `what_you_were_thinking` on the row of the turn it
was had in, oldest first.

## 2. Off and on over a replayed stretch of a real story

Chat 74 (the Doctor and Hinami, a two-hander) branched at turn 49 on two
copies of the owner's database (`web.app.turn_branch`), and the source's
recorded player lines of turns 50-62 submitted again as new turns
(`turn_new`, every stage as in play): leaving the hotel lobby, the lift, room
312, one bed, the kettle, late-night television, and Hinami asking what he
sees when he looks at reality. The owner's routing (character on NanoGPT
`z-ai/glm-5.3:thinking`); lookups off in both; `character_thoughts_kept` 5 in
one arm and unset in the other.

The first run with kept thinking OFF died on its seventh turn -- `UnboundLocalError:
MemoryClock` -- the defect this work fixed before its commit (the commit
message tells it); every later turn of that run was refused behind the
broken one. It was rerun whole on a fresh copy.

| | kept thinking off | kept thinking on (5 turns) |
|---|---|---|
| character calls | 14 | 14 |
| prompt tokens a call | 21,486 | 25,123 (+17%) |
| output tokens a call | 3,624 | 3,781 |
| seconds a call | 67.9 | 68.8 |
| thinking held at the end | -- | 5 turns, 27,697 characters |
| 4-word phrases he says on two or more turns | 9 | 9 |

**Three blind readers** (each given the two runs as A and B, the assignment
rotated and withheld; asked to judge the Doctor alone, as one character across
thirteen turns) agreed on every question:

| | reader 1 | reader 2 | reader 3 |
|---|---|---|---|
| continuity of his own threads | off | off | off |
| refrains worse | on | on | on |
| callbacks that develop | off | off | off |
| answers what Hinami says and does | on | on | on |
| **overall, the more continuous and alive** | **off** | **off** | **off** |

What they saw, in their words. With kept thinking the Doctor is "the better
scene partner", "warmer", answering "nearly every word and act" of hers, with
the sharpest single payoffs ("Mischief face, delivered right on schedule; I
did say plan it after tea") -- and from turn 8 he "cycles the same patter":
"customs desk" four turns running, "in that order", "biscuit's turn-down
service", "national treasure", while the threads he started himself (the
desk, the voice in the lift, the missing TARDIS) "fade after turn 5". Without
it he "has a life of his own": a too-smooth check-in noticed in turn 1, shelved
on purpose so she can sleep, paid off in turns 10-13 ("three impossibilities
and a variety hour"; "That's not surveillance, Hinami. That's
correspondence"), at the cost of four turns of goodnights in the middle.

## 3. What this says, and what it does not

- **On this stretch, keeping thinking made the mind warmer and more
  repetitive, and not more its own.** The refrains look like the mechanism's
  own: a mind re-reading its earlier phrasing leans on it -- the warning the
  memory window's replay already gave (a longer window gave a refrain "more
  copies of itself to lean on", `MEMORY_WINDOW_REPLAY_2026_09_28.md`).
- **Part of the continuity gap is the world, not the thinking.** The runs'
  worlds diverged with their Directors: in the run without kept thinking the
  key card opened a stranger's room first, which handed that Doctor a mystery
  the other never had. Thirteen turns of one story, three readers: a
  direction, not a rate.
- **It costs little time.** +17% prompt tokens, +1% seconds a call: a
  reasoning model's time is in what it writes, not what it reads.
- **Recommendation: leave it off.** If it is tried again: fewer turns, or only
  the end of each trace (the decision, not the deliberation), on a story whose
  minds carry plans across many beats -- the descent, a maze -- and read for
  refrains first.
- The off arm's Doctor, at turn 10, said the television "switched itself on --
  nobody's touched a thing" while Hinami had used the remote. Checked stage by
  stage: the encoder carried her act, and his view did not, because she was
  out of his sight; he heard her and saw the screen light. The firewall
  working, not a defect; the readers were told a character only knows what
  reached him.
