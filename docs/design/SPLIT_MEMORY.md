# Split plan — `mind/memory.py`

Status: BUILT (2026-08-19, twelve commits). Companion to [`DESIGN_MODULE_LAYOUT.md`](DESIGN_MODULE_LAYOUT.md),
third of its kind after [`SPLIT_COMMIT.md`](SPLIT_COMMIT.md) and
[`SPLIT_SPATIAL.md`](SPLIT_SPATIAL.md).

5,676 lines · 154 top-level defs · 47 module-level constants. 12 new modules plus
`mind/memory.py`.

Lines 1–19 are the docstring and the top-level import block. They are RETAINED
by the facade (see below) and reproduced in each sibling to the extent that
sibling needs them, so they are the one part of the file that is not moved.
The twelve modules partition **lines 20–5676 exactly once** — ranges sum to
5,657, verified by the range table below.

## The section markers are 16 seams and 2 lies

The file carries 18 labelled sections. Sixteen are honest module boundaries or
sub-boundaries within one. Two are not, and both would mislead an implementer
who trusted them:

- **`memory.py:2354 # ---- Memory Summaries ----` swallows a second subsystem.**
  Its nominal span runs to the snapshot marker at 3536, but
  `build_character_memory_context` (2908–3194, 287 lines with its four helpers
  from 2678) is not a summary function. It is the assembly seam where retrieval,
  summaries, relationships and the active state become one character payload —
  the single most-read function in the file. It becomes
  `mind/memory_context.py`, and that makes `mind/memory_summaries.py` two
  non-contiguous ranges (2354–2677 and 3195–3535). Splitting a marker is the
  right call here for the same reason it was in `commit.py`: the label records
  where someone stopped scrolling, not where the subsystem ends.

- **`memory.py:5533 # ---- Why there is no vector index ----` is an essay
  heading, not a section.** It reads as a note about the *preceding* rebuild
  code and in fact heads 144 lines of belief-confidence reconciliation
  (`_mint_confidence_of`, `_abandoned_confidence`,
  `reconcile_inference_confidence`) that have nothing to do with vectors. That
  block is `mind/memory_inference.py`. Keep the essay with the vector code it
  is about.

## Modules

| module | lines | ranges | owns |
| --- | --- | --- | --- |
| `mind/memory_common.py` | 180 | 20–195, 2395–2398 | Leaf helpers used by more than one domain: the language-pack recognizer, every category/provenance vocabulary, blob/base64/vector codecs, the FTS query builder, cosine. Under target deliberately — this is the module that makes the graph acyclic. |
| `mind/memory_lorebooks.py` | 563 | 196–676, 4003–4084 | The lorebook *graph*: hierarchy, moves, links, cycle refusal, inheritance resolution, per-chat attachment and weights, the manifest, monitoring subtrees, and the link snapshot pair. |
| `mind/memory_write.py` | 574 | 677–1250 | How a memory becomes a row: normalisation, gist/entity/key-phrase extraction, FTS mirroring, importance and dispute, embedding, the upsert, batch add, turn deletion — and the failed-embedding repair thread. |
| `mind/memory_read.py` | 325 | 1251–1575 | The one seam a mind reads its own memory through (`visible_memory_rows`), plus the host-facing reads that deliberately cross character boundaries. |
| `mind/memory_retrieval.py` | 778 | 1576–2353 | Hybrid retrieval: lexical ranking, RRF fusion, mood congruence, rank-normalised importance, stranded-embedding warning, `search_memories`, and contrast (unbidden) recall. |
| `mind/memory_summaries.py` | 661 | 2354–2394, 2399–2677, 3195–3535 | Autobiographical/hearsay/surmise summaries: read, search, support derivation, save, event-key backfill, window coverage and backfill, and consolidation. |
| `mind/memory_context.py` | 517 | 2678–3194 | The character memory payload — `build_character_memory_context` and the reading/beats-ago/origin-drift helpers only it uses. |
| `mind/memory_snapshot.py` | 563 | 3536–4002, 4085–4180 | Checkpoint and archive: vector address/put/get, dump and restore for memories, summaries and lorebooks, and the prepare/apply restore split. |
| `mind/memory_lore_entries.py` | 501 | 4181–4681 | Lore *entries* as opposed to lore books: canon book, embedding stamps, add/update/delete, tree duplication, `search_lore`, embedding health, knowledge scoping. |
| `mind/memory_relationships.py` | 208 | 4682–4889 | The relationship graph: dataclasses, axes, event recording, history, updates from conduct and from inference. |
| `mind/memory_vectors.py` | 643 | 4890–5532 | Rebuilding vectors after the embedding model changes: bank status, the rebuild itself, checkpoint rebuild, and the host-facing background rebuild with its progress state. |
| `mind/memory_inference.py` | 144 | 5533–5676 | Belief confidence at mint and at abandonment, and the reconciliation pass over a mind's inferences. |
| `mind/memory.py` (stays) | ~140 | — | Facade only. Its import block, and an explicit re-export of every moved name. |

Unlike `persist/commit.py`, the facade keeps **no domain code at all**. There is
no per-turn lock here and no orchestrator; every top-level definition belongs to
exactly one of the twelve.

## Two moves that exist only to break a cycle

The naive range split has exactly two cycles. Both are one small symbol each,
and both resolve downward rather than by merging modules:

1. **`_summary_retrieval_text` (2395–2398) moves to `memory_common.py`.** It is
   a three-line string join, and it is read by five of the twelve modules
   (`write`, `summaries`, `snapshot`, `vectors`, and quoted in four docstrings)
   because it defines what text a summary's *vector* is computed from. Leaving
   it in `summaries` makes `write → summaries → write`.

2. **`dump_lorebook_links` / `restore_lorebook_links` (4003–4084) move from the
   snapshot block to `memory_lorebooks.py`.** They are link-graph functions that
   happen to be filed under a snapshot marker; leaving them makes
   `lore_entries ↔ snapshot`. `restore_lorebook` (4085–4180) stays in snapshot —
   it calls `add_lore`, so it is genuinely a restore function.

With those two moves the graph is a DAG, verified:

```
common         -> []
lorebooks      -> common
write          -> common
read           -> common, write
retrieval      -> common, read, write
summaries      -> common, read, retrieval, write
context        -> common, retrieval, summaries, write
lore_entries   -> common, lorebooks, write
snapshot       -> common, lore_entries, summaries, write
relationships  -> common, write
vectors        -> common, retrieval, write
inference      -> write
```

**No extracted module references any symbol retained in `mind/memory.py`** — the
dependency is strictly `memory.py → extracted`, never back.

## Module-level mutable state

Three clusters. This is the part of a split that fails silently if it is wrong,
so it was checked symbol-by-symbol rather than by module — and one of the three
turned out to have a second writer in another module:

| state | home | why it is safe |
| --- | --- | --- |
| `_REPAIR_LOCK`, `_REPAIR_THREAD`, `_REPAIR_DELAY`, `_REPAIR_MAX_PENDING`, `_REPAIR_MAX_DELAY`, `_REPAIR_MAX_ROUNDS` | `memory_write` | The repair thread rebinds `_REPAIR_THREAD` under `global`. Every reader (`note_failed_embedding_write`, `_ensure_repair_thread`, `_repair_loop`, `repair_pending_embeddings`, `queue_fallback_rows_for_repair`) is in the same range. |
| `_STRANDED_REPORTED` | `memory_retrieval` | Written by `_warn_stranded_embeddings` ten lines below it, and **cleared from `memory_vectors`** at the end of a successful rebuild (5256) so the warning may speak again. That second writer is a `.clear()`, a mutation of the imported set object, not a rebind — the two modules share one set, which is what the code intends. A rebind there would have been the silent failure. |
| `_REBUILD_LOCK`, `_REBUILD_STATE` | `memory_vectors` | Read by `rebuild_progress`, `_run_rebuild`, `start_rebuild_if_needed`, all in range. |

A `global` rebind across modules would not raise — it would bind a *second*
name in the wrong module and leave the first at its initial value forever.
There is none.

## Facade

`mind/memory.py` keeps its **entire existing top-level import block (1–19)
unchanged**. Not tidiness: `payload_legacy` is imported there from
`llm.prompts` and re-imported *out* of `mind.memory` by another module, so the
block is part of the contract; and fifteen test files monkeypatch
`memory.<imported-name>` (`chat_complete`, `embed_texts`, `embed_texts_meta`,
`embedding_model_key`). Those patches go inert at the facade and are repointed
per step below — but the names must still resolve.

Then re-export every moved symbol, private names included. **105 distinct names
are imported from `mind.memory` across the repository**, but the re-export is
not limited to those: `getattr(memory, …)` and monkeypatch targets are not
visible to an import scan. Explicit imports, not `import *` —
`project_check`'s undefined-name check skips any module containing a
star-import. Do **not** add `__all__`; there is none today.

All 105 contract names map to a home; unmapped: none.

## Execution order

Leaf-first, one module per commit: 1 `memory_common` · 2 `memory_lorebooks` ·
3 `memory_write` · 4 `memory_read` · 5 `memory_retrieval` · 6 `memory_summaries` ·
7 `memory_context` · 8 `memory_lore_entries` · 9 `memory_snapshot` ·
10 `memory_relationships` · 11 `memory_vectors` · 12 `memory_inference` ·
13 tooling + docs.

Steps 2, 3 commute after 1. 4 follows 3; 5 follows 4; 6 follows 5; 7 follows 6.
8 follows 2 and 3; 9 follows 8 and 6. 10, 11, 12 commute after their listed
inputs.

**Monkeypatch repoints, in the same commit as their step.** 71 `setattr` sites
across 17 test files patch a name on `mind.memory`; every one of them is
inert the moment its reader moves. Grouped by the name patched:

| step | name patched | repoint to |
| --- | --- | --- |
| 3 | `embed_texts_meta`, `embed_texts`, `embedding_model_key`, `_ensure_repair_thread`, `repair_pending_embeddings` (write-path readers) | `memory_write` |
| 5 | `_STRANDED_REPORTED` | `memory_retrieval` |
| 6 | `chat_complete`, `embed_texts_meta` (consolidation readers) | `memory_summaries` |
| 8 | `_kw_scores`, `embed_texts`, `embed_texts_meta` (lore readers) | `memory_lore_entries` |
| 9 | `embed_texts_meta` (restore readers) | `memory_snapshot` |
| 2 | `add_lorebook_link` | `memory_lorebooks` |
| 11 | `embed_texts_meta` (rebuild readers) | `memory_vectors` |

`memory.time` (patched in `tests/test_embedding_write_repair.py`) needs no
repoint — it resolves to the `time` module object itself, which every module
shares.

**The dangerous case is a patch that goes inert and the test still passes.**
`embed_texts_meta` is patched 42 times and has readers in five different
modules; a fake that is never installed usually surfaces as a real provider
call, but not always. After each step, every test file touching that step's
names is run and its assertions read, not just its exit status.

**Step 13 is not optional.** `mind.memory` joins `FACADE_FAMILIES` in
`tools/project_check.py` (which is what makes the outside-in and inside-out
import rules apply to it at all), a `MODULE_PURPOSES` entry per module in
`tools/generate_code_map.py`, the `AGENTS.md` routing table, and
`DESIGN_MODULE_LAYOUT.md`. `EXTENSION_DEEP_IMPORTS` needs no change — it
matches on the first path component and `mind` is already a subsystem package,
so the new siblings are covered the moment they exist. That is the one hole the
`commit.py` split had and this one does not.

## What actually happened

Twelve commits, one module each, `make structure` and a 3,389-test focused
selection per step, the full 8,450 at the end. No line of logic was written,
deleted or reordered: 5,676 lines in, 5,994 out across thirteen files, and the
difference is twelve docstrings and twelve import headers.

**The extraction tool was wrong twice, both in the dangerous direction.** Its
free-name analysis collected every binding anywhere in the subtree into one
flat set, so it under-reported what a module needed:

- A function-local `import hashlib, uuid` marked the name bound for the whole
  module, and `vector_address`'s module-scope `hashlib.sha1()` 436 lines
  earlier was emitted without the import. 26 tests, `NameError`.
- `_walk_free` never visited `node.returns` or `arg.annotation`, so `-> Optional[Relationship]`
  did not count as reading `Optional`. That one fails at IMPORT, because an
  annotation is evaluated when the def executes.

Both were fixed in the analysis rather than in the file, and after each fix
every module already landed was REGENERATED and diffed against what was
committed. Both times: all prior modules byte-identical, only the current one
differed, by exactly the missing import. Nothing latent went in.

**`tools/project_check.py` already had the inert-patch check** — nothing
needed writing. Registering `mind.memory` in `FACADE_FAMILIES` fired it on
seven sites in four files that every grep had missed, because they use a third
call layout (`monkeypatch.setattr(\n    memory,\n    "embed_texts",`) and
because they PASS either way: the stub exists only to avoid needing an API
key, and without it the real embedder falls back silently. The static check
saw what 8,450 tests could not.

**`patch_seam` in `tests/helpers.py`** is the general answer, generalised from
`forbid_model_calls` rather than invented: rebind a name wherever the ORIGINAL
object is bound, which is the set of readers by definition, and raise when
that set is empty. Enumerating modules instead would be correct today and
stale after the next move — silently, which is the failure being fixed.

## Defects noticed — do not fix here

Two, both found while mapping the file. Recorded so the split stays a move:

1. **`_kw_scores` (memory.py:170) discards BM25.** It orders by `rank` — which
   *is* bm25() — and then throws the score away for a positional decay,
   `1.0 - i / max(len(rows), 1)`. A single weak match scores 1.0, the same as
   the best match in a field of fifty. It is the keyword half of both
   `search_memories` and `search_lore`.

2. **Stale-dimension vectors compete on the keyword term alone.** The comment
   above the 0.65/0.35 blend records the measurement. A vector at the old
   dimension cannot contribute to `_cos`, so the entry's whole score comes from
   a keyword term that (per 1) has no magnitude.

Both belong to the audit that follows the split, not to any of the 13 steps.
