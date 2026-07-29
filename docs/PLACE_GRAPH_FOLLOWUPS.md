# Place graph — review findings and follow-ups

Written after reviewing the durable place graph (`124b717`, implemented by
Fable against [`DESIGN_PLACE_PURPOSE.md`](DESIGN_PLACE_PURPOSE.md)'s
dependency). `make check` was green — 2651 passed — so nothing here blocked the
commit. These are the things that survived review as real, recorded before they
evaporate.

---

## 1. See-through barriers mint walkable edges

**Status: open. Real in story play, cannot affect the maze arms.**

`update_place_graph`'s doorway filter excludes only `wall`:

```python
if isinstance(e, dict) and e.get("to") \
        and normalize_barrier(e.get("barrier")) != "wall":
```

But `_SIGHT_BARRIERS` is `{"open", "open_door", "window", "bars"}`
(`spatial.py:139`), and `visible_adjacent_rooms` returns everything in it. So a
barred window or a pane of glass between two rooms records a graph edge.
Confirmed directly — a `window` between A and B yields:

```
edges from A: {'B': {'last_confirmed': 1, 'bearing': 'e', 'basis': 'seen'}}
```

You can see through a barred window. You cannot walk through one.

**Why it matters more now than it did before.** The old `_frontier_beyond`
answered a boolean — *is there any new ground that way* — and a wrong boolean is
merely vague. `_frontier_hops` answers a distance, rendered to the character as
*"the nearest door you have never taken lies about 3 rooms down that way"*. A
wrong distance is a specific falsehood about their own remembered ground, and it
is the kind a character would act on.

**Scope.** The legacy `known_exits` ledger is worse and always has been: it
records every declared adjacency including solid `wall` edges, and
`_annotate_known_exits` merges it into the same BFS adjacency. So the graph is a
strict improvement rather than a regression, and this predates the place graph
entirely. It cannot touch A11 or any maze arm — generated and authored mazes
alike have only `open` edges.

**Why it was not fixed in passing.** It is not a one-line filter. It requires
deciding what a *route* means to a remembering mind, and the existing sets both
answer a different question:

| set | means | wrong here because |
|---|---|---|
| `_SIGHT_BARRIERS` | can be seen through | includes glass and bars |
| `_PASSABLE_BARRIERS` | passable **this beat** | excludes `closed_door`, which a character can simply open |

The set wanted is roughly `_PASSABLE_BARRIERS | {"closed_door"}` — *a way I
could go through, now or by opening it* — and possibly `locked_door` too, since
a remembered route past a locked door is still a route if you expect to get a
key. That is a judgement about the character's model of a route, so it wants
deciding rather than defaulting.

Fixing it should also cover the legacy `known_exits` writer in
`record_spatial_experience`, or the wall edges simply re-enter through the merge.

## 2. `basis: "told"` is declared but has no writer

**Status: documented, deliberate. Fable's own finding.**

The approved design had hearsay edges derived from `stated_fact` place claims
already rekeyed by `rekey_place_claims`. Implementing it revealed that deriving
*connectivity* from free-text claims means text-mining them — exactly the
non-deterministic derivation this engine refuses everywhere else.

`told` remains an accepted value with no code path. A future testimony writer
needs a **structured claim field** naming the two places and the direction, not
a parser over prose. Worth knowing before someone reads the node shape and
assumes hearsay edges exist.

This is the design document being wrong, not the implementation: the proposal
overstated what commit can legitimately extract.

## 3. A-core made the legacy keys nearly redundant

**Status: accepted, watch it.** Fable's finding.

With the pruning gone, unpruned `known_exits` + `known_dead_ends` carry most of
the routing information by themselves. The graph's distinct contributions in
this scope are narrower than the proposal implied:

- `disproven` retraction (which also retracts the stale legacy copy)
- walkedness that survives the recency window
- reverse-declared `seen` edges
- bounded eviction, which now also bounds the legacy keys

They were kept as graph-bounded *views* rather than promoted to a second
authority. That is the right call while both exist, but two representations of
one fact is the shape that produced `rekey_place_claims` and
`reconcile_inference_confidence`. If a third consumer appears, collapse them.

## 4. Live sight already outranks the gradient

**Status: no action. Recorded because it looked like a gap and was not.**

Two of Fable's own fixtures failed because `visibly_no_way_through` correctly
pre-empted the distance verdict. The existing verdict precedence in `_VERDICTS`
handles the interaction, and the design neither needed nor added anything.
Present perception beating remembered distance is the correct order.

## 5. Three-valued frontier semantics are load-bearing

`_frontier_hops` returns `None` (spent), `0` (live but unmeasurable), or `N`.
The middle value exists for saves written before the graph — a walked room with
no recorded exits can honestly be called neither spent nor near. It is not
defensive padding; removing it would make old saves read as exhausted.

---

## The experiment that settles the whole thing

Arm **A11** on the authored 7×7 (`tools/mazes/maze7x7-a11.svg`), registered in
[`MAZE_ARMS.md`](MAZE_ARMS.md).

The prediction under test, stated before the run: **repeat-run openings stop
oscillating.** The observed failure was that at the start of every repeat run
every neighbouring exit read `known` — nothing untried, nothing proven — so the
verdicts had nothing to say and the character thrashed (north, back, north,
back). Local history can rank doors it has seen; it cannot point toward ground
it has not. The graded distance is the fact that can.

The 7×7 tests this harder than the 9×9 did. Its difficulty is a 28-move thread
through 57% of its rooms rather than deep traps, so losing the route is the
dominant failure mode — which is exactly what the graph is for. Read **excess
moves over 28**, not reversals: it is a perfect maze, so backing out of a dead
end is correct play and cannot be told from being lost.
