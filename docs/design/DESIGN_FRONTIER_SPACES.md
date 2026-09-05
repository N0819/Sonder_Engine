# Design: a frontier is a space held open, not a space spent

**Status: BUILT 2026-09-05**, all five parts, in `world/structure.py`,
`story/plot_packages.py` and `story/room_tools.py`
(`tests/test_structure_frontier_claims.py`, 24). From the owner: "plans
should have expansion spaces potentially for future plans; it's fine if it
gets a different name at this point though, as these are both important
features." Two features shared one mechanism and only the first worked.

## 1. What was true, read in `world/structure.py`

A `frontier` is an axis label on a planned room — "the upland road" — saying
that something lies that way. When a body stands in the room,
`prepare_frontier_expansion` either draws an EDGE (when the axis names a room
the plan already has, which is right and stays) or MINTS a stub through
`mint_frontier`, named from the structure's grammar and seeded so a replay is
identical.

Three things followed, and each was the gap:

  * **The axis was spent.** It was dropped from `spec["frontier"]` at the
    moment it minted; only a refused or over-cap axis was retained. Nothing
    on the stub recorded that it was ever a placeholder.
  * **The stub was a dead end.** `mint_frontier` returned `"frontier": []`,
    so the world opened exactly one ring past whatever a plan drew and no
    further.
  * **A later plan could not claim it, so it built a rival beside it.** This
    is measured and it was in the module's own comment: on the Harrowmere
    replay the axis "upland road" minted `bridge_road_2` beside the real
    Bridge Road, and the Director, shown a stub called "bridge road", minted
    `upland_road` next to it. `slate_lane_2`, `market_square_2` and
    `market_square_3` were the same class — *every duplicate room of that
    run*.

## 2. The rule

> **A minted stub is the space the plan reserved, standing in until a plan
> claims it. Claiming it renames the room; it never mints a second one.**

## 3. What was built

**A stub remembers what it stands for.** *Built.* `mint_frontier`'s spec
keeps `provisional: True` and `frontier_of: {room, axis}`, and the HOLDER's
plan keeps `frontier_standing: {axis: room_uid}` instead of simply dropping
the axis. That is what makes the space addressable later, and it is the fact
the engine already had and threw away. An axis that drew an edge to a room
the plan already has is recorded standing too, and is `filled` rather than
`provisional`.

**A plan addresses a frontier directly, never by prose.** *Built.* A
`plan_rooms` room may carry `claims: {room, axis}` — the holder's uid and the
axis, both ids `inspect_structures` hands the Room. No name matching and no
similarity score: the Room asks for the slot by its identity, the way every
other reference in this engine works. `claim_frontier_spaces` resolves it and
rekeys the planned room onto the room that holds the space, remapping every
`adjacent.to` inside the same operation.

**Claiming renames, and the old name survives as an alias.** *Built.* The
room's uid never changes, which keeps edges, the registry projection and
anything already standing there intact; `plant_structure(claims=…)` writes
the new name into `room_registry.name` and accumulates BOTH spellings into
`aliases` in the same statement.

  * **What keys off a room's name, surveyed before relying on the alias.**
    Room identity in this engine is uid-first almost everywhere: regions,
    charter placements, `knowledge_locations`, `world_events.location_id`,
    plot packages' own room fields and every spatial reader are uids and are
    unaffected. Four things read `room_registry.aliases` already
    (`commit_room_registry._registry_alias_index`, `subjects.resolve_subject`,
    `prepare_frontier_expansion`'s reservation map, `web/story_view`), and
    **the plan's own spelling tables did not** — so a rename would have made
    the Director speaking the old name mint `coastal_lane_2`, which is the
    very class this closes. `_planned_spellings` now folds id, name and every
    alias, and `planned_room_spellings` (the table `dedup_minted_rooms`
    redirects a minted room through), `planned_context` and
    `planned_rooms_named_in` all read it.
  * **The registry name is a PROJECTION of the scene** — `_prepare_room_registry`
    reads `scene.rooms[uid]["name"]` every commit — so a registry-only rename
    of a stub the fringe has already materialised would be written back on the
    next beat and the claim would silently un-happen. `materialize_planned_fringe`
    now carries the plan's name, purpose and measurements onto a live room
    that is still the plan's prose-free stub, and touches nothing that carries
    prose.
  * **Not fixed, and the strongest argument for the visited rule:**
    `memories.location` stores a room's display NAME, and
    `memory_retrieval` matches "did this happen here" against it by name with
    no alias path. A rename would silently weaken recall for every memory
    written in that room. The visited rule covers it exactly — a memory is
    only ever written under the name of a room its owner was standing in —
    but a room whose prose was never written and whose occupant left before
    the claim is a hole the rule cannot see. See §5.

**A room somebody has been in cannot be renamed out from under them.**
*Built.* If the stub has been described or a body stands in it now, the claim
takes the purpose, the geometry and the onward axes and LEAVES THE NAME, and
the preview says so. A name is what the player knows the place by; changing
it is a lie about their own memory.

  * **What "has been in" means, decided from the engine's own record.** The
    room CARRIES PROSE — the live `desc`, or `planned.resolved`, which
    `_prepare_room_registry` maintains from it every commit — or a body
    stands in it NOW (`scene.positions`). Those are the two the engine can
    answer honestly. It was tempting to ask "was a position ever held here",
    and the engine cannot: `visited_rooms` is a bounded recency window per
    character (`commit_place_graph.VISITED_ROOMS_CAP`) that forgets, and
    `last_seen` is offscreen bookkeeping about people, not a room's record.
    Prose is the closest honest proxy, because a stub is furnished the beat a
    beat reaches it.

**A stub inherits an onward axis.** *Built.* `mint_frontier` carries the axis
onward, so the frontier keeps moving as the player walks and the world does
not stop one ring out. Two rules make it work rather than loop:

  * **An axis a room was minted from names the way ON, not the room it
    made.** Read as a reference the inherited label would resolve to the very
    room it named, so one ring out the road would draw an edge back to its own
    first segment and stop. `prepare_frontier_expansion` skips the name lookup
    for a room's own `frontier_of.axis` and mints; `mint_frontier`'s existing
    ordinal gives Upland Road, Upland Road 2, Upland Road 3.
  * **A bearing does not chain.** ONE RULE, ONE OWNER: the onward axis is
    refused exactly where the plan-side gate refuses it
    (`frontier_refusal`). A bearing is not the name of a place, so it cannot
    be the name of what lies beyond the place it named — "north" off a square
    draws North Lane from the grammar, and North Lane's own north is not
    "north" again.

**MEASURED, on a fixture, twenty beats of walking** (`/tmp` harness,
reproduced by `test_twenty_beats_of_walking_open_a_bounded_number_of_rooms`):

| plan | planted | rooms after 20 beats |
|---|---|---|
| one road, one axis | 1 | 21 |
| a square with four ways out | 1 | 24 |
| the road run's own three-room plan | 3 | 24 |
| a bearing axis (does not chain) | 1 | 2 |

Growth is **one room per beat walked into new ground**, whatever the fan-out:
each beat a body stands in exactly one room, and a room mints its frontiers
once. Nothing mints ahead of a body. The bound is the existing `max_planned`
(200 per structure), which a continuous walk would reach after ~200 beats;
the chain then stops and the axis is retained and reported, exactly as an
over-cap axis always was.

**The Room can see the open spaces.** *Built.* `frontier_spaces(cid)` lists
every unfilled space — the axis, the room it hangs off, whether it is `open`
(nothing minted) or `provisional` (a stub stands there), and the stub's id
and name — and `inspect_structures` returns it under `frontiers`. A filled
space is not a space and is not listed. A planner that cannot see the slot
plans beside it, which is exactly what the corpus measured.

## 4. What argues against it

  * **Renaming is a real risk** even with the alias, because prose already
    written keeps the old word. The visited rule is the mitigation and it is
    deliberately conservative.
  * **An onward axis makes the world infinite in principle.** The caps are
    the answer, and they are the owner's: `max_planned` 200 per structure,
    and minting still only on approach. **No new cap was added** — see §5.
  * **A claimed stub may have been described already**, and a description
    that suited a lane may not suit the guildhall a plan turns it into. The
    engine cannot retract prose. The preview warns in exactly that case.
  * **Two plans may claim one space.** First claim wins and the second is
    refused naming the holder and the room that fills it. A claim that cannot
    be honoured plants NOTHING — falling back to planting the room anyway
    would rebuild the rival beside the space, which is the whole defect.

## 5. Left out, and named to the owner

  * **NO NEW CAP WAS CHOSEN.** The chain is bounded by `max_planned` (200 per
    structure) and by occupancy, as the note asked. **Recommendation:** a
    per-axis chain depth would be the honest second bound — a road that runs
    20 segments because somebody walked 20 beats is fine, one that runs 200
    and eats a structure's whole allowance so no plan can plant in it again
    is not. Suggested shape if wanted: a `chain_depth` on `frontier_of`,
    refused above a structure-level dial. Not built, because it is a cap and
    caps are the owner's.
  * **A durable "was ever occupied" mark for a room.** The visited rule reads
    prose or present occupancy; a stub somebody walked through, that no beat
    described, and left before the claim would be renamed. **Recommendation:**
    one boolean on `room_registry.payload.planned` written by the scene commit
    the first time a position names the room. Not built here because it is a
    write in `persist/commit_*` and would change the mutation stream for every
    plan, including ones with no frontier at all.
  * **`memories.location` is still a NAME** (§3). Making it a uid, or giving
    `memory_retrieval`'s here-match an alias path, is a memory-schema decision
    and was not taken.
  * **A claim cannot move a stub's edges.** It adds ways out and keeps every
    one the frontier gave it, the same rule `protect_planned_edges` keeps for
    a developed room. Removing the way back to the holder is not expressible.
