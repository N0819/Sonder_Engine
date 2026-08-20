# Where a recall actually spends its time

Status: EVIDENCE. Measured 2026-08-20 against a copy of the LongMemEval
merged bank (10,960 rows, one character, real 2560-dim vectors), with query
vectors served from the harness disk cache so no provider traffic enters the
timings.

## 1. The number that started it

The LongMemEval run took roughly an hour of wall clock for 500 probes and
pinned a core the whole time. That is not a benchmark artefact: it is the cost
a character pays per beat, and it scales with the size of its own memory.

| | median |
|---|---|
| `search_memories`, 10,960-row bank | **4,732 ms** |
| `recall_confidence`, same bank | 467 ms |
| a beat paying both | **5,199 ms per character** |

Extrapolated by row count: about **312 ms** on the largest real bank in the
live corpus (657 rows), and about **23.7 s** at 50,000 rows.

## 2. The diagnosis I got wrong first, and the profile that corrected it

The obvious reading -- and the one this document originally asserted -- was
that the vector scan is the wall. `memory_retrieval.py` decodes every row's
embedding from a SQLite BLOB and cosines it in a Python loop, with no cache
anywhere in the module, so a query at 10,960 rows touches 56 million float32
values.

**The 10x gap between the two timings above refutes that.** `recall_confidence`
performs the same full-bank vector scan and costs 467 ms. If vectors were the
wall, the two numbers would be close.

`cProfile` over 8 queries, sorted cumulative:

```
128,458,936 function calls in 89.952 seconds
      8    0.746    89.719   search_memories
 87,680    1.947    79.937   _exact_cue_score      <- 89% of all retrieval time
```

**`_exact_cue_score` is 89% of retrieval.** The vector scan is roughly 10%.

## 3. Why that function is expensive

It runs once per row per query, and for each of a row's entities (up to 12) it
built a fresh pattern string, ran `re.escape`, and performed a regex search:

```python
if el and re.search(rf"(?<![A-Za-z0-9]){re.escape(el)}(?![A-Za-z0-9])", ql):
```

At 10,960 rows that is on the order of a million regex constructions per eight
queries. The word-boundary rule itself is correct and load-bearing -- a stored
"Mara" must not fire inside "marathon", and the ASCII-alphanumeric class rather
than `\w` is what keeps the cue alive for Japanese banks. The cost was never
the rule; it was rebuilding the matcher for every row.

## 4. The fix, and why it cannot change a verdict

Two changes, both semantics-preserving by construction:

1. **A necessary-condition guard.** The boundary regex can only match if the
   literal appears as a plain substring, so `el in ql` is tested first. It is a
   C-speed scan against a regex search, and every match the regex would have
   found still reaches it.
2. **Compiled patterns cached by literal.** Cues repeat constantly across a
   bank, so the distinct set is small; the cache is bounded at 20,000 entries
   so a pathological bank cannot grow it without limit.

| | before | after |
|---|---|---|
| `search_memories`, 10,960 rows | 4,732 ms | **968 ms** |
| speedup | | **4.9x** |
| per beat, 657-row bank | ~312 ms | **~58 ms** |
| at 50,000 rows | ~23.7 s | **~4.4 s** |

Verified on the instrument rather than argued: the full 470-probe LongMemEval
run returns the identical verdict set. A performance change that moves a single
probe is a behaviour change wearing a benchmark's clothes.

## 5. What is left, and what is not claimed

The vector scan is now the largest remaining term, and it is still a Python
loop over BLOB-decoded rows with no cache. Holding a bank's vectors as one
contiguous matrix and doing a single `matmul` is the standard fix and would
take the remaining cost down again -- but it is a storage-format change, it
needs its own measurement, and after this fix it is worth roughly a tenth of
what it was worth this morning.

Not claimed: that 4.4 s at 50,000 rows is acceptable. It is not. It is merely
five times less unacceptable than 23.7 s, and a thousand-turn story is the
case this project is being built for.
