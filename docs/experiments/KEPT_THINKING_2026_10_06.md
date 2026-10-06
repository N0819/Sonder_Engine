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

(Results go here.)
