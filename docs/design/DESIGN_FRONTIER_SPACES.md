# Design: a frontier is a space held open, not a space spent

**Status: DESIGN, 2026-09-05, not built.** From the owner: "plans should have
expansion spaces potentially for future plans; it's fine if it gets a
different name at this point though, as these are both important features."
Two features share one mechanism today and only the first works.

## 1. What is true now, read in `world/structure.py`

A `frontier` is an axis label on a planned room — "the upland road" — saying
that something lies that way. When a body stands in the room,
`prepare_frontier_expansion` either draws an EDGE (when the axis names a room
the plan already has, which is right and stays) or MINTS a stub through
`mint_frontier`, named from the structure's grammar and seeded so a replay is
identical.

Three things follow, and each is the gap:

  * **The axis is spent.** It is dropped from `spec["frontier"]` at the moment
    it mints; only a refused or over-cap axis is retained. Nothing on the stub
    records that it was ever a placeholder.
  * **The stub is a dead end.** `mint_frontier` returns `"frontier": []`, so
    the world opens exactly one ring past whatever a plan drew and no further.
  * **A later plan cannot claim it, so it builds a rival beside it.** This is
    measured and it is in the module's own comment: on the Harrowmere replay
    the axis "upland road" minted `bridge_road_2` beside the real Bridge Road,
    and the Director, shown a stub called "bridge road", minted `upland_road`
    next to it. `slate_lane_2`, `market_square_2` and `market_square_3` were
    the same class — *every duplicate room of that run*.

## 2. The rule

> **A minted stub is the space the plan reserved, standing in until a plan
> claims it. Claiming it renames the room; it never mints a second one.**

## 3. What that needs

**A stub remembers what it stands for.** Its spec keeps the axis it was minted
from and a `provisional` mark. That is what makes it addressable later, and it
is a fact the engine already had and threw away.

**A plan addresses a frontier directly, never by prose.** `plan_rooms` gains a
way to say *this room fills that space* — the holder's uid and the axis, which
are both ids the Room can already see. No name matching, no similarity score:
the Room asks for the slot by its identity, the way every other reference in
this engine works.

**Claiming renames, and the old name survives as an alias**, so a reference
written before the claim still resolves. The room's uid never changes, which
is what keeps edges, the registry projection and anything already standing
there intact.

**A room somebody has been in cannot be renamed out from under them.** If the
stub has been entered or narrated, the claim takes the purpose, the geometry
and the onward axes and LEAVES THE NAME, and says so. A name is what the
player knows the place by; changing it is a lie about their own memory. An
unvisited stub is nobody's yet and renames freely.

**A stub inherits an onward axis**, so the frontier keeps moving as the player
walks and the world does not stop one ring out. Bounded by the existing
`max_planned` (200 per structure) and by occupancy — nothing mints until
somebody is near it — so the chain cannot run away.

**The Room can see the open spaces.** Its room tools should list unfilled
frontiers as what they are: an axis, the room it hangs off, and whether a
provisional stub already stands there. A planner that cannot see the slot
plans beside it, which is exactly what the corpus measured.

## 4. What argues against it

  * **Renaming is a real risk** even with the alias, because prose already
    written keeps the old word. The visited-room rule is the mitigation and it
    is deliberately conservative.
  * **An onward axis makes the world infinite in principle.** The caps are the
    answer, and they are the owner's: `max_planned` 200 per structure, and
    minting still only on approach.
  * **A claimed stub may have been described already**, and a description that
    suited a lane may not suit the guildhall a plan turns it into. The engine
    cannot retract prose. This is the strongest argument for the visited rule
    and for a claim carrying its own reason into the register.
  * **Two plans may claim one space.** First claim wins and the second is
    refused naming the holder, because a space is a place and a place cannot
    be two things.
