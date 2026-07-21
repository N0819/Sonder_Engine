# Future Ideas (parked — not scheduled)

Deferred ideas kept here so they aren't lost or accidentally built into the
current phased work. Nothing in this file is committed to a phase.

## Optional minimap (deferred)

A small, opt-in minimap for the player — a visualization of the tracked spatial
model (rooms, adjacency, containment).

**Status:** idea only. NOT part of the movement/space phased implementation
(Phases 0–3). Earliest it could sensibly be built is *after* Phase 1 lands the
room registry + monitoring subtree-walk, since it reads from those. Even then it
is optional and independent — build only if wanted.

**Why it's nearly free:** it is a *read/visualization* of the ledger the
movement/space architecture already maintains. The hard part (a coherent, tracked
spatial model) is what the phased work builds; rendering it is mostly a query.

**The one non-negotiable design constraint — it MUST be an epistemic view, not an
omniscient one.** The minimap shows what the *player character* legitimately
knows: rooms they've explored, remember, or can currently perceive — never the
raw objective scene. A minimap drawn from objective truth would be a **spatial
information leak** (showing a corridor you can't see, a deck you've never
visited) — the exact failure the perception firewall exists to prevent, just
rendered visually. So it rides on the `known`-map / perception (epistemic) layer,
never on the raw scene. In other words: it is the character's *mental map*, i.e.
fog-of-war — which is an information barrier made visual.

**Shape:** topological, not geometric (the model tracks connections + barriers +
containment, not coordinates). Nodes = rooms; edges = adjacency with barrier
state (open door vs sealed vs wall — the transit/derived-edge state shows
naturally, e.g. a moving elevator's exits change as it transits); plus a
containment breadcrumb (Ship › Deck 3 › Cargo Bay) from the lorebook-tree
registry subtree-walk. Opt-in; degrades gracefully to nothing when the space
isn't well-structured.

**Bonus:** doubles as a coherence/debug view — e.g. the stray duplicate `deck_3`
room bug found during transit testing would have shown instantly as two nodes.
