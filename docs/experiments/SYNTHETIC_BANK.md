# A fiction bank built to ask what a borrowed one cannot

Status: EVIDENCE. Measured 2026-08-20. Three independently generated worlds,
270 rows each, 71 positive probes and 36 negatives, scored through the
production `search_memories` seam by `tools/memory_probe_harness.py`.

## 1. Why build one at all, with 470 borrowed probes already in hand

LongMemEval answered what it could (`CRC32_CONTROL.md`, `RETRIEVAL_COST.md`,
UNBUILT 1.76): retrieval is scale-robust to 10,960 rows, embeddings buy +61
probes over pure lexical, and the abstention signal is blind. It is
task-oriented user/assistant chat, so three things are structurally out of its
reach:

- **Nothing in it was witnessed, and nothing was told by a third party.** No
  borrowed corpus carries provenance, because no other system has the
  firewall.
- **No fact in it is superseded in a way its pass rule can score.** Its
  knowledge-update class scores 94.4%, and that number is an artefact: the
  rule accepts ANY evidence row, so retrieving the stale fact passes exactly
  like retrieving the current one.
- **Its preferences are stated to an assistant**, not lived.

## 2. How the answer key is kept honest

The plan is generated first. Prose is generated from a plan entry. The probe
question is generated from the SAME entry by a separate call that never sees
the prose. Question and answer are siblings rather than parent and child.

**That is weaker independence than LongMemEval's and it should be read as
weaker.** Both descend from the same one-line `summary`, so they can share
vocabulary the summary forced. LongMemEval's questions were written by people
about real conversations, with no shared ancestor at all. Where the two
disagree, believe LongMemEval.

Three worlds rather than one bank, because a single generated world can be
idiosyncratic in a way that looks like a finding.

## 3. What was measured

| fact kind | reached payload | median rank |
|---|---|---|
| preference | 18/18 (100%) | 2 |
| channel (hearsay) | 17/18 (94%) | 1 |
| superseded | 16/18 (89%) | 2 |
| event | 15/17 (88%) | 1 |
| **all** | **66/71 (93%)** | |

### Belief revision: retrieval finds the correction and reads it second

| | |
|---|---|
| current row outranks its stale predecessor | **8/18 (44%)** |
| median rank of the STALE row | **2** |

A `superseded` fact plants a belief and, 60-400 beats later, the observation
that overturns it. The probe targets the correction and antitargets the
belief. Retrieval delivers the correction 89% of the time -- so this is not a
recall failure -- but ranks the outdated row above it in a majority of cases,
typically at position 2.

The mechanism is structural rather than incidental, and is visible in the
code: the four fused rankings (semantic 1.0, cue-vector 1.15, keyword 1.1,
exact 1.25) contain **no recency term at all**. Recency enters only when the
QUERY carries a temporal cue. So a belief and its correction compete on text
alone, and a question about a belief matches the statement of that belief more
closely than it matches the later observation that overturns it. Nothing
prefers the newer row because nothing knows which is newer.

**What this does NOT establish.** Both rows usually reach the payload, and
every recalled row carries `when` ("about N beats ago"). So the character is
given the material to prefer the newer one. Whether it does is a CONDUCT
question and is unmeasured here. Ordering matters because payload order
influences what a model reads first; it is not the same as the answer being
absent.

### Provenance survives retrieval

17/18 hearsay rows came back still stamped `told`. A `channel` fact happens
while the bank's owner is elsewhere, so the observer's direct sighting never
enters this bank and the only row that does is the telling. What comes back
still knows how it was learned.

### Preferences retrieve perfectly here, and that is the least trustworthy
number in the file

18/18 against LongMemEval's 15/30. Two reasons to discount it: this bank is
270 rows against 10,960, so there is far less to compete with; and the shared
`summary` ancestry described in section 2 helps preferences most, because a
preference IS its summary in a way an event is not. Read this as "the
generator can plant a retrievable preference", not as "preference recall is
solved".

## 4. The mechanism worth acting on

`record_dispute` exists, is wired end to end -- commit path, storage, and
`i_now_read_this_differently` in the character payload -- and has fired
**once in 9,608 live memories**. The gate is that `memory_disputes` comes from
the character's own output (`agents/character.py`): a mind must spontaneously
volunteer that it now reads a memory differently. Nothing detects a
contradiction and offers the occasion.

So the engine already has the right shape for belief revision and never
reaches it. That is a better place to intervene than reranking: the ordering
result above says retrieval hands the mind both versions; the dispute lane is
how the mind is supposed to say which one it now believes.

## 5. What would falsify the reading

- A conduct measurement in which characters, given both rows and their `when`
  stamps, answer with the current fact anyway. That would make the ordering
  result cosmetic.
- A larger `superseded` set. Eighteen probes across three worlds is small, and
  is reported with its denominator for that reason.
- A rerun with questions authored by something that never saw the plan.

---

## 6. What characters DO with a contradiction, measured

Added 2026-08-20. `tools/benchmark_memory_rationality.py` hands a character
the belief and the observation that overturned it, through the production
payload, and asks. A judge that never sees the payload classifies the answer
against the plan's two facts. The character prompt carries NO instruction to
look for conflicts -- an arm run WITH such a clause scored LOWER on `conflict`
(4/6 against 6/6), so the behaviour is not prompt-induced and the invitation
slightly got in the way.

| world | conflict | current | stale | neither |
|---|---|---|---|---|
| 1 | 6 | 0 | 0 | 0 |
| 2 | 6 | 0 | 0 | 0 |
| 3 | 3 | 2 | 0 | 1 |
| 4 | 1 | 3 | **1** | 1 |
| 6 | 4 | 1 | 0 | 1 |
| **all** | **20** | **6** | **1** | **3** |

**Reasoned from the newer evidence: 26/30 (87%). Named the contradiction
aloud: 20/30 (67%). Took the superseded belief: 1/30 (3%).**

**The two numbers behave differently, and that is the most useful thing here.**
Getting it RIGHT converges -- 88% at n=24, 87% at n=30. Saying so ALOUD does
not: the per-world conflict rate runs 100%, 100%, 50%, 17%, 67%, a six-fold
spread across worlds built by one tool with identical parameters.

So whether a mind reasons past a contradiction looks like a property of the
engine, and whether it announces the revision looks like a property of the
material. That distinction matters because the dispute channel depends on the
announcement, not on the reasoning -- `record_dispute` can only receive what a
character volunteers. A capability that varies 17% to 100% with the story is
not one to build a mechanism on top of without knowing what moves it.

**The per-world spread is the finding, not the total.** Worlds 1 and 2 named
the contradiction 6 times out of 6; world 4 managed 1 and produced the only
outright failure. Any single world would have supported a confident and wrong
general claim -- and the first three did, which is why this table exists. The
rate is a property of the material, not of the engine.

The failure is legible rather than mysterious, which is what a good instrument
buys: the judge records that the answer *"affirms the earlier belief that the
canal water level was dangerously low, citing specific memories, and does not
mention any later change from heavy rains."* A plain case of taking the first
thing read.

### What this does and does not license

It DOES establish the capability. A mind handed both rows, with the stale one
usually ranked higher, gets it right 88% of the time and articulates the
contradiction in two thirds of cases without being asked. Whatever is wrong
with belief revision here, the reasoning is not it.

It does NOT establish a rate for ordinary play. Every case aims a question
squarely at the contradicted fact; a beat that merely happens near one does
not. The gap between those two situations is `2.24`'s remaining open half, and
the deterministic detector built to close it is measured not to work (same
entry).
