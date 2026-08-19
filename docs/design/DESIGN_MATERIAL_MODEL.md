# Design: does the engine grow a material model at all?

**Status: not built, and deliberately open.** Moved out of
[`docs/UNBUILT.md`](../UNBUILT.md) §4.7 and §4.8 on 2026-08-19, because both are
one undecided question rather than two defects: whether matter in this engine
gets a magnitude and a miscibility, or stays a ledger of described deposits.
Everything below is blocked on that answer rather than on difficulty. The
register keeps a pointer at §4.

---

## 1. Matter has no volume, so nothing can wash anything away

The substance ledger accumulates. Coalescing landed (`9a6bc3c`) — same material,
same source, same region, same body is one pool a later release re-describes —
and conservation landed, so swallowing empties the mouth. What is missing is
DISPLACEMENT: a more abundant fluid arriving on a region carrying away what was
already there.

It was deliberately not built, twice, for reasons that still hold:

- **The amount vocabulary is not a magnitude.** Of 39 stored terms, `trace`,
  `moderate`, `small` and `copious` order as English, but `coating` is a
  distribution, `oozing` a rate, `remainder` purely relative with no magnitude
  at all, `dustpan full` container-relative, and `hot, viscous torrent` buries
  its magnitude among temperature and viscosity.
- **The precedent makes it a no-op on the reported case.** Following
  `affect.CAPACITY_LADDER`, an unreadable term takes the mildest rung — and the
  reported case is spelled `coating` versus `light coating`, so neither would
  ever displace the other. Making it fire requires ruling that a distributed
  film outranks a droplet, which is a physical model of fluids, not a reading
  of a word.
- **The reported case is cross-substance** (one fluid washing away a different
  one). `_same_pool` deliberately keeps different substances apart, and
  deciding that A dilutes B needs a miscibility model the engine has no
  representation for and § Genre boundary forbids hard-coding.

Separately and much cheaper: **wiping already works and is almost never used.**
`op: remove` / `op: clear` exist and the Director can emit them. Measured
corpus-wide: 38 adds and deposits against 5 removes, and zero removes after
turn 38 of the reference story. That is prompt efficacy, not a missing
mechanism, and it is worth trying before any material model is designed.

**Open question this section exists to force: does the engine grow a material
model at all?** Everything above is blocked on that answer rather than on
difficulty.


---

## 2. Two regions on one body, spelled differently, are two regions

`mouth` and `oral cavity` mint separate substance rows on the same body.
`AGENTS.md` forbids a body-part synonym table with a measured reason
(`tail_spade` is a nameable place on a tail, not `tail` blurred), and that pair
shares no word, so no structural rule reaches it.

`spatial.canonical_region` is now the single fold point for every region
comparison in the ledger, so if the substance ledger is judged to warrant an
exception the contact ledger does not, there is exactly one place to add it.
Explicitly NOT made moot by `owned_region`: qualifying which body owns a region
is orthogonal to folding two spellings of one region on one body.


---

## 3. Why these are one question

§1's displacement rule needs an ordering over `amount`, and §2's fold needs a
ruling that two spellings name one place. Both are the engine deciding facts
about MATTER that no channel delivered — which is the thing `AGENTS.md`
§ Genre boundary refuses to hard-code, and the reason `spatial.canonical_region`
is a single fold point rather than a synonym table. If the answer is "no
material model", §1 closes as prompt efficacy (`op: remove` already works and is
almost never used) and §2 closes as a per-ledger exception with exactly one
place to write it.
